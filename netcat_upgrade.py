#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.5 - 2020, Sebastian Majewski

netcat_upgrade.py - program used to upgrade software on Palo Alto firewalls

"""

import sys
import time
import datetime
import argparse

from typing import List, Dict, Any, Optional

import netcat

from netcat_cli_pa import PACliAccess


REQUESTED_SOFTWARE_VERSION: str = "9.0.7"


def upgrade_software(device_info: Dict[str, Any], requested_software_version: str, upgrade: bool) -> None:
    """ Access PA and upgrade software on it  """

    if device_info["device_type"] == "paloalto":
        with PACliAccess(device_info) as cli:

            cli.download_software(requested_software_version)

            if upgrade:
                cli.create_config_snapshot()
                cli.upgrade_software(requested_software_version)

    else:
        netcat.LOGGER.error(f"Unknown device type '{device_info['device_type']}'")
        raise netcat.CustomException


@netcat.exception_handler
def cli_process(device_info: Dict[str, str], timestamp: int, upgrade: bool) -> List[str]:
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

    upgrade_software(device_info, REQUESTED_SOFTWARE_VERSION, upgrade)

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
    parser.add_argument("-S", "--single-process", action="store_true", help="enable single procss operation for debuging purposes")
    parser.add_argument("-u", "--upgrade", action="store_true", help="perform upgrade, otherwise download software only")
    group = parser.add_mutually_exclusive_group(required=True)
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

    print("\nNetCAT Upgrade, ver 5.5 - 2020, Sebastian Majewski\n")

    # Setup logger
    netcat.setup_logger("netcat_upgrade", debug=arguments.debug)
    netcat.LOGGER.info(f"Starting upgrade program, timestamp={timestamp}")

    arguments.debug and netcat.LOGGER.opt(ansi=True).info("<magenta>Debug mode enabled</magenta>")
    arguments.single_process and netcat.LOGGER.opt(ansi=True).info("<magenta>Single process mode enabled</magenta>")
    arguments.upgrade or netcat.LOGGER.opt(ansi=True).info("<magenta>Download software only mode enabled</magenta>")

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
    netcat.LOGGER.info(f"Executing upgrade for {len(requested_device_name_list)} device(s): {', '.join(requested_device_name_list)}")

    # Time backup execution
    start_time = time.time()

    # Execute separate process per device or continue as the same process if SINGLE_PROCESS_MODE flag is set
    successful_device_name_list = sorted(
        netcat.execute_data_processing_function([_ for _ in device_info_list if _["device_name"] in requested_device_name_list],
        cli_process, timestamp, arguments.upgrade)
    )

    # Create failed device info list
    failed_device_name_list = sorted(set(requested_device_name_list) - set(successful_device_name_list))

    # Time backup execution
    end_time = time.time()

    netcat.LOGGER.info(f"Upgrade ended, execution time: '{end_time - start_time:.2f}s'")

    # Report processe's finish status
    netcat.report_final_status(requested_device_name_list, successful_device_name_list, failed_device_name_list)

    return 0


if __name__ == "__main__":
    sys.exit(main())
