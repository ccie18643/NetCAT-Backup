#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.5 - 2020, Sebastian Majewski

netcat_mongodb.py (Backup version) - module containing shared functions used to access MongoDB

"""

import sys

from typing import List, Dict, Tuple, Any, Callable, Optional

import pymongo  # type: ignore

import netcat


DB_URI: str = "mongodb://127.0.0.1/netcat"


def create_tables():
    """ Create MongoDB tables in case any is missing """

    db =  pymongo.MongoClient(DB_URI).get_default_database()
    tables = db.list_collection_names()

    if netcat.DBT_STATUS not in tables:
        db[netcat.DBT_INFO].create_index([("device_name", pymongo.ASCENDING), ("snapshot_timestamp", pymongo.DESCENDING)])
        netcat.LOGGER.warning(f"Pymongo: Created '{netcat.DBT_STATUS}' table")

    if netcat.DBT_INFO not in tables:
        db[netcat.DBT_INFO].create_index([("snapshot_timestamp", pymongo.DESCENDING)])
        db[netcat.DBT_INFO].create_index([("device_name", pymongo.ASCENDING)])
        db[netcat.DBT_INFO].create_index([("device_type", pymongo.ASCENDING)])
        db[netcat.DBT_INFO].create_index([("device_name", pymongo.ASCENDING), ("snapshot_timestamp", pymongo.DESCENDING)])
        db[netcat.DBT_INFO].create_index([("device_type", pymongo.ASCENDING), ("snapshot_timestamp", pymongo.DESCENDING)])
        netcat.LOGGER.warning(f"Pymongo: Created '{netcat.DBT_INFO}' table")

    if netcat.DBT_BACKUP not in tables:
        db[netcat.DBT_BACKUP].create_index([("snapshot_timestamp", pymongo.DESCENDING)])
        db[netcat.DBT_BACKUP].create_index([("device_name", pymongo.ASCENDING)])
        db[netcat.DBT_BACKUP].create_index([("device_name", pymongo.ASCENDING), ("snapshot_timestamp", pymongo.DESCENDING)])
        netcat.LOGGER.warning(f"Pymongo: Created '{netcat.DBT_BACKUP}' table")


def write(table_name, document, max_attempts=15, max_sleep_time=10):
    """ Write document into table, wait and retry if unsuccessful """

    if table_name in {netcat.DBT_INFO, netcat.DBT_BACKUP}:
        document = netcat.compress_device_data(document)

    with pymongo.MongoClient(DB_URI) as client:

        attempts = max_attempts

        while attempts:
            try:
                client.get_default_database()[table_name].insert_one(document)
                break

            except pymongo.errors.WriteError:
                sleep_time = random.uniform(0.1, max_sleep_time)
                netcat.LOGGER.warning(f"Unable to write document into '{table_name}' table, will retry in {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
                attempts -= 1

            except pymongo.errors.PyMongoError as exception:
                raise CustomException(f"Unable to write document into '{table_name}' table, PyMongo exception: '{exception}'")

        else:
            raise CustomException("Unable to write device data document into database table '{table_name}' after {max_attempts} attempts")


def load_latest_backup(device_name: str) -> Dict[str, Any]:
    """ Returns latest config backup for given device name """

    try:
        with pymongo.MongoClient(DB_URI) as client:
            return netcat.decompress_device_data(client.get_default_database()[netcat.DBT_BACKUP].find_one(filter={"device_name": device_name},
                    sort=[("snapshot_timestamp", pymongo.DESCENDING)], projection={"_id": False}) or {})

    except pymongo.errors.PyMongoError as exception:
        raise netcat.CustomException(f"Unable to load latest config backup, PyMongo exception: '{exception}'")


def exception_handler(function: Callable[..., Any]) -> Any:
    """ Decorator to log pymongo exceptions and exit process """

    from sys import exit
    from functools import wraps

    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)

        except pymongo.errors.PyMongoError as exception:
            netcat.LOGGER.error(f"PyMongo exception: '{exception}'")
            exit()

    return wrapper
