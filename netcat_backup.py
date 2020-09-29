#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.0 - 2020, Sebastian Majewski

netcat_backup.py - program retrieves backup and command output data from devices and saves it to database

"""

import sys
import time
import datetime
import argparse

from typing import List, Dict, Any, Optional

import netcat

if netcat.DB_INTERFACE == "MongoDB":
    import netcat_mongodb as db

if netcat.DB_INTERFACE == "DynamoDB":
    import netcat_dynamodb as db

if netcat.DB_INTERFACE == "FsDB":
    import netcat_fsdb as db

from netcat_cli_f5 import F5CliAccess
from netcat_cli_pa import PACliAccess
from netcat_cli_cisco import CiscoCliAccess


def save_device_data(device_data: dict, timestamp: int, config_change: bool = False, force_backup: bool = False) -> None:
    """ Save current config backup and command output data into database """

    def _(table_name):

        document = { 
            "snapshot_timestamp": timestamp,
            "device_name": device_data["device_name"],
            "device_type": device_data["device_type"],
            "output_formats": {_: device_data["output_formats"][_] for _ in device_data["output_formats"] if _.startswith(table_name[7:])},
        }

        db.write(table_name, document)

    if config_change or force_backup:

        if force_backup:
            netcat.LOGGER.info("Option 'force backup' set, saving device configuration regardless of detected changes")

        netcat.LOGGER.info("Saving config backup to database")
        _(db.netcat.DBT_BACKUP)

    netcat.LOGGER.info("Saving command output to database")
    _(db.netcat.DBT_INFO)


def save_final_status(device_info_list: List[Dict[str, Any]], timestamp: int, successful_device_name_list: List[str], failed_device_name_list: List[str]) -> None:
    """ Save timestamp and device status lists """

    netcat.LOGGER.info("Saving final backup status to database")

    device_info_dict = {
        __: {
            "device_type": _.get("device_type"),
            "failed": _.get("device_name") in failed_device_name_list,
            "successful": _.get("device_name") in successful_device_name_list,
            } for _ in device_info_list if (__ := _.get("device_name"))
    }

    document = {
        "snapshot_name": "info_status",
        "snapshot_timestamp": timestamp,
        "device_info_dict": device_info_dict,
    }

    db.write(db.netcat.DBT_STATUS, document)


def compare_command_outputs(output_a: str, output_b: str) -> bool:
    """ Compare two configuration snapshots and return 'True' when they are the same, 'False' if they are different """

    exclusions = {"!Time:", "no ip domain-lookup", "state up", "state down"}

    output_a_lines = output_a.split("\n")
    output_b_lines = output_b.split("\n")

    if len(output_a_lines) != len(output_b_lines):
        return False

    for output_a_line, output_b_line in zip(output_a_lines, output_b_lines):
        if output_a_line != output_b_line:
            for exclusion in exclusions:
                if output_a_line.find(exclusion) >= 0 or output_b_line.find(exclusion) >= 0:
                    break
            else:
                return False

    return True


def detect_config_change(device_info: Dict[str, Any]) -> bool:
    """ Get list of previous configuration backups stored localy and load latest set for comparision with current ones """

    if not (previous_formats := (db.load_latest_backup(device_info["device_name"]) or {}).get("output_formats", {})):
        netcat.LOGGER.info("Unable to find any previous config backups")
        return True

    current_formats = {_: __ for _, __ in device_info["output_formats"].items() if _.startswith("backup")}

    config_change_detected = False

    for format_key in current_formats:
        for command_output_key in current_formats[format_key]:
            if not compare_command_outputs(
                current_formats[format_key][command_output_key],
                previous_formats.get(format_key, {}).get(command_output_key, "")
            ):
                config_change_detected = True
                netcat.LOGGER.info(f"Config change detected in '{format_key}' - '{command_output_key}' section")

    if not config_change_detected:
        netcat.LOGGER.info("No config change detected between current and previous configs")

    return config_change_detected


def get_device_data(device_info: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    """ Access device and retrieve its current info """

    if device_info["device_type"].startswith("paloalto"):
        with PACliAccess(device_info) as cli:
            return cli.get_device_data()

    if device_info["device_type"].startswith("cisco"):
        with CiscoCliAccess(device_info) as cli:
            return cli.get_device_data()

    if device_info["device_type"].startswith("f5"):
        with F5CliAccess(device_info) as cli:
            return cli.get_device_data()

    raise netcat.CustomException(f"Unsupported device type '{device_info['device_type']}'")


@netcat.exception_handler
def cli_process(device_info: Dict[str, str], timestamp: int, force_backup: bool = False, test_run: bool = False) -> List[str]:
    """ Command line process, ready to run as separate thread or process """

    # Setup logger to show process name
    netcat.bind_logger(device_info["device_name"].upper())

    # Time process execution
    start_time = time.time()

    # Log initial status
    if netcat.SINGLE_PROCESS_MODE:
        netcat.LOGGER.opt(ansi=True).info("<green>Executing CLI operations as part of main process </green>")

    else:
        netcat.LOGGER.opt(ansi=True).info("<green>Executing CLI operations as child process</green>")

    # Access device and retrieve its current configuration in all formats, update existing device_dat structure
    device_data = get_device_data(device_info)

    if not test_run:
        # Get list of previous configuration backups stored localy and compare latest of them with current config set
        config_change = detect_config_change(device_data)

        # Save device info to databae
        save_device_data(device_data, timestamp, config_change, force_backup)

    # Time process execution
    end_time = time.time()

    # Log process end status and execution time
    netcat.LOGGER.opt(ansi=True).info(f"<green>CLI process ended normaly, execution time: {end_time - start_time:.2f}s</green>")

    # Return device name to indicate successfuly executed operation for given device
    return [device_info["device_name"]]


def parse_arguments(args: Optional[List[Any]] = None) -> argparse.Namespace:
    """ Parse comand line arguments """

    parser = argparse.ArgumentParser()
    parser.add_argument("-D", "--debug", action="store_true", help="enable debug logs")
    parser.add_argument("-S", "--single-process", action="store_true", help="enable single process operation for debuging purposes")
    parser.add_argument("-F", "--force-backup", action="store_true", help="force backup to be taken even if no changes are detected")
    parser.add_argument("-T", "--test-run", action="store_true", help="test run, info retrieved from devices but not sent to database")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-a", "--all", action="store_true", help="all devices")
    group.add_argument("-g", "--group", action="store", choices=netcat.SUPPORTED_DEVICE_TYPES, help="chose group of devices")
    group.add_argument("-d", "--device", action="store", nargs="+", help="specify device or device list")
    group.add_argument("-r", "--regexp", action="store", help="specify device(s) by regular expression")

    return parser.parse_args(args)


@netcat.exception_handler
def main() -> int:
    """ Main program """

    timestamp = int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1,0,0,0)).total_seconds())

    arguments = parse_arguments()
    netcat.SINGLE_PROCESS_MODE = arguments.single_process

    print("\nNetCat Backup, ver 5.5 - 2020, Sebastian Majewski\n")

    # Setup logger
    netcat.setup_logger("netcat_backup", debug=arguments.debug)
    netcat.LOGGER.info(f"Starting backup program, timestamp={timestamp}")

    arguments.test_run and netcat.LOGGER.opt(ansi=True).info("<magenta>Test mode enabled, no information will be saved to database</magenta>")
    arguments.debug and netcat.LOGGER.opt(ansi=True).info("<magenta>Debug mode enabled</magenta>")
    arguments.single_process and netcat.LOGGER.opt(ansi=True).info("<magenta>Single process mode enabled</magenta>")
    arguments.force_backup and netcat.LOGGER.opt(ansi=True).info("<magenta>Forced backup requested</magenta>")

    # Check if database tables exist, if not then create them
    db.create_tables()

    # Read device info list file
    if not (device_info_list := netcat.read_info_list_file(netcat.FILENAME_DEVICE_INFO_LIST)):
        netcat.LOGGER.error(f"Device info list is empty, exiting...")
        sys.exit()

    # Create all devices name list
    all_device_name_list = sorted([_["device_name"] for _ in device_info_list])

    # Create list of requested devices and check if there is any valid device name on it
    if not (requested_device_name_list := sorted(netcat.get_requested_device_name_list(device_info_list, arguments))):
        netcat.LOGGER.error(f"No valid device names requested, exiting...")
        sys.exit()

    # Run CLI processes
    netcat.LOGGER.info(f"Executing backup for {len(requested_device_name_list)} device(s): {', '.join(requested_device_name_list)}")

    # Time backup execution
    start_time = time.time()

    # Execute separate process per device or continue as the same process if SINGLE_PROCESS_MODE flag is set
    successful_device_name_list = sorted(
        netcat.execute_data_processing_function([_ for _ in device_info_list if _["device_name"] in requested_device_name_list],
        cli_process, timestamp, arguments.force_backup, arguments.test_run)
    )

    # Create failed device info list
    failed_device_name_list = sorted(set(requested_device_name_list) - set(successful_device_name_list))

    # Time backup execution
    end_time = time.time()

    netcat.LOGGER.info(f"Backup ended, execution time: '{end_time - start_time:.2f}s'")

    # Save snapshot status to database
    if not arguments.test_run:
        save_final_status(device_info_list, timestamp, successful_device_name_list, failed_device_name_list)

    # Report processe's finish status
    netcat.report_final_status(requested_device_name_list, successful_device_name_list, failed_device_name_list)

    return 0


if __name__ == "__main__":
    sys.exit(main())
