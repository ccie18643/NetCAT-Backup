#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.5 - 2020, Sebastian Majewski

netcatdynamodb.py (App version) - module containing shared functions for AWS DynamoDB support

"""

from typing import List, Dict, Tuple, Any, Callable, Optional, Union

import botocore.session  # type: ignore
import botocore.exceptions  # type: ignore
import amazondax  # type: ignore

import netcat


# For connetcion to DynamoDB to work the AWS CLI needs to be installed and configured with apropriate connectivity key
DB_CLIENT = botocore.session.get_session().create_client("dynamodb")

# For use with DAX accelerator
#DB_CLIENT = amazondax.AmazonDaxClient(botocore.session.get_session(), endpoints=["netcat.qrzev9.clustercfg.dax.use1.cache.amazonaws.com:8111"])


def _get_list(query_params: Dict[str, Any], search_depth: int = 0) -> List[Any]:
    """ Get list of records (up to given serch depth) based on given query params """

    results: List[Any] = []

    query_params["ScanIndexForward"] = False

    if search_depth:
        query_params["Limit"] = search_depth

    while True:
        response = DB_CLIENT.query(**query_params)
        results += [_fold(_) for _ in response.get("Items", [])]

        if "LastEvaluatedKey" not in response:
            break

        if search_depth:
            query_params["Limit"] -= len(response.get("Items"))

            if query_params["Limit"] == 0:
                break

        query_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    return results


def _fold(z: Any) -> Any:
    """ Fold DynamoDB low level interface query result into its original json format """

    def _trl(x, y):
        if y == "N":
            return int(x[y])
        if y == "NULL":
            return None
        return x[y]

    def _trd(z, x, y):
        if y == "N":
            return int(z[x][y])
        if y == "NULL":
            return None
        return z[x][y]

    if type(z) is list:
        return [_fold(x[y]) if (y := next(iter(x))) in {"M", "L"} else _trl(x, y) for x in z]

    elif type(z) is dict:
        return {x: _fold(z[x][y]) if (y := next(iter(z[x]))) in {"M", "L"} else _trd(z, x, y) for x in z}  # type: ignore


def _unfold(old_struct):
    """ Unfold json format into DynamoDB low level interface format """

    if type(old_struct) == list:
        new_struct = []

        for item in old_struct:
            if type(item) is dict:
                new_struct.append({"M": _unfold(item)})

            elif type(item) is list:
                new_struct.append({"L": _unfold(item)})

            elif type(item) is str:
                new_struct.append({"S": item})

            elif type(item) is int:
                new_struct.append({"N": str(item)})

            elif type(item) is bytes:
                new_struct.append({"B": item})

            elif type(item) is bool:
                new_struct.append({"BOOL": item})

            elif item is None:
                new_struct.append({"NULL": True})

    elif type(old_struct) == dict:
        new_struct = {}

        for key in old_struct:
            if type(old_struct[key]) is dict:
                new_struct[key] = {"M": _unfold(old_struct[key])}

            elif type(old_struct[key]) is list:
                new_struct[key] = {"L": _unfold(old_struct[key])}

            elif type(old_struct[key]) is str:
                new_struct[key] = {"S": old_struct[key]}

            elif type(old_struct[key]) is int:
                new_struct[key] = {"N": str(old_struct[key])}

            elif type(old_struct[key]) is bytes:
                new_struct[key] = {"B": old_struct[key]}

            elif type(old_struct[key]) is bool:
                new_struct[key] = {"BOOL": old_struct[key]}

            elif old_struct[key] is None:
                new_struct[key] = {"NULL": True}

    return new_struct


def _projection(command_list: Optional[List[str]] = []) -> str:
    """ Create DynamoDB projection from provided command list, '[]' for all commands to be included, 'None' for no commands to be included """

    if command_list:
        return f"#1, #2, #3, formats.info.{', formats.info.'.join([netcat.encode_command(_) for _ in command_list])}"

    if command_list == []:
        return "#1, #2, #3, formats.info"

    return "#1, #2, #3"


def create_tables():
    """ Create AWS DynamoDB tables in case any is missing """

    db_client = botocore.session.get_session().create_client("dynamodb")

    try:
        db_client.create_table(
            TableName=netcat.DBT_STATUS,
            AttributeDefinitions=[{"AttributeName": "snapshot_name", "AttributeType": "S"}, {"AttributeName": "snapshot_timestamp", "AttributeType": "N"}],
            KeySchema=[{"AttributeName": "snapshot_name", "KeyType": "HASH"}, {"AttributeName": "snapshot_timestamp", "KeyType": "RANGE"}],
            ProvisionedThroughput={"ReadCapacityUnits": 100, "WriteCapacityUnits": 1}
        )

        netcat.LOGGER.warning(f"Botocore: Creating '{netcat.DBT_STATUS}' table")

    except db_client.exceptions.ResourceInUseException:
        pass

    try:
        db_client.create_table(
            TableName=netcat.DBT_INFO,
            AttributeDefinitions=[
                {"AttributeName": "device_name", "AttributeType": "S"},
                {"AttributeName": "device_type", "AttributeType": "S"},
                {"AttributeName": "snapshot_timestamp", "AttributeType": "N"}],
            KeySchema=[{"AttributeName": "device_name", "KeyType": "HASH"}, {"AttributeName": "snapshot_timestamp", "KeyType": "RANGE"}],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "type-timestamp-index",
                    "KeySchema": [{"AttributeName": "device_type", "KeyType": "HASH"}, {"AttributeName": "snapshot_timestamp", "KeyType": "RANGE"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 300, "WriteCapacityUnits": 50}
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 300, "WriteCapacityUnits": 50}
        )

        netcat.LOGGER.warning(f"Botocore: Creating '{netcat.DBT_INFO}' table")

    except db_client.exceptions.ResourceInUseException:
        pass

    try:
        db_client.create_table(
            TableName=netcat.DBT_BACKUP,
            AttributeDefinitions=[{"AttributeName": "device_name", "AttributeType": "S"}, {"AttributeName": "snapshot_timestamp", "AttributeType": "N"}],
            KeySchema=[{"AttributeName": "device_name", "KeyType": "HASH"}, {"AttributeName": "snapshot_timestamp", "KeyType": "RANGE"}],
            ProvisionedThroughput={"ReadCapacityUnits": 20, "WriteCapacityUnits": 25}
        )

        netcat.LOGGER.warning(f"Botocore: Creating '{netcat.DBT_BACKUP}' table")

    except db_client.exceptions.ResourceInUseException:
        pass

    db_client.get_waiter('table_exists').wait(TableName=netcat.DBT_STATUS)
    db_client.get_waiter('table_exists').wait(TableName=netcat.DBT_INFO)
    db_client.get_waiter('table_exists').wait(TableName=netcat.DBT_BACKUP)


def write(table_name, document, max_attempts=15, max_sleep_time=10):
    """ Write document into database table """

    from time import sleep
    from random import uniform

    if table_name in {netcat.DBT_INFO, netcat.DBT_BACKUP}:
        document = netcat.compress_device_data(document)

    attempts = max_attempts

    while attempts:
        try:
            DB_CLIENT.put_item(
                TableName=table_name,
                Item=_unfold(document),
            )
            break

        except botocore.exceptions.ClientError as exception:
            if exception.response["Error"]["Code"] not in {"ProvisionedThroughputExceededException", "ThrottlingException"}:
                raise netcat.CustomException(f"Botocore: Unable to write document into '{table_name}' table, Botocore exception: '{exception}'")

            sleep_time = uniform(0.1, max_sleep_time)
            attempts -= 1
            netcat.LOGGER.warning(f"Botocore: Unable to write document into '{table_name}', attempt {max_attempts - attempts}, will retry in {sleep_time:.2f} seconds")
            sleep(sleep_time)

    else:
        raise netcat.CustomException(f"Botocore: Unable to write device data document into database table '{table_name}' after {max_attempts} attempts")


def load_latest_backup(device_name: str) -> Dict[str, Any]:
    """ Returns latest config backup for given device name """

    query_params = {
        "TableName": netcat.DBT_BACKUP,
        "KeyConditionExpression": "device_name = :device_name",
        "ExpressionAttributeValues": {":device_name": {"S": device_name}},
    }

    netcat.LOGGER.debug(f"{netcat.fn()}: {query_params=}")

    return netcat.decompress_device_data(next(iter(_get_list(query_params, search_depth=1)), {}))


def exception_handler(function: Callable[..., Any]) -> Any:
    """ Decorator to log botocore exceptions and exit process """

    from sys import exit
    from functools import wraps

    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)

        except botocore.exceptions.ClientError as exception:
            netcat.LOGGER.error(f"Botocore exception: '{exception}'")
            exit()

    return wrapper
