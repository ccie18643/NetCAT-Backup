#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.5 - 2020, Sebastian Majewski

netcat_fs.py (Backup version) - module containing shared functions used to store date on filesystem, for experimental purposes only...

"""

import sys

from typing import List, Dict, Tuple, Any, Callable, Optional


import netcat


DB_PATH: str = "/tmp/netcat/"


def create_tables():
    """ Create tables and indexes in case any is missing """

    from pathlib import Path

    Path(DB_PATH + netcat.DBT_STATUS).mkdir(parents=True, exist_ok=True)
    Path(DB_PATH + netcat.DBT_INFO).mkdir(parents=True, exist_ok=True)
    Path(DB_PATH + netcat.DBT_BACKUP).mkdir(parents=True, exist_ok=True)


def write(table_name, document, max_attempts=15, max_sleep_time=10):
    """ Write document into table, wait and retry if unsuccessful """

    from json import dump

    if table_name in {netcat.DBT_INFO, netcat.DBT_BACKUP}:
        document = netcat.compress_device_data(document)

    with open(DB_PATH + table_name + "/" + document["device_name"] + "__" + document["snapshot_timestamp"].replace(" ", "_"), 'w') as _:
        dump(document, _, indent=4)


def load_latest_backup(device_name: str) -> Dict[str, Any]:
    """ Returns latest config backup for given device name """

    return {}

