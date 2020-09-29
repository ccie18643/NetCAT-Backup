#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.5 - 2020, Sebastian Majewski

netcat_deploy.py - program used to deploy config snippets on network devices

"""

import sys
import time
import datetime
import argparse

from typing import List, Dict, Tuple, Any, Optional

import netcat

from netcat_cli_pa import PACliAccess
from netcat_cli_cisco import CiscoCliAccess


def confirm_deployment_validity(snippet: str, requested_device_name_list: List[str]) -> bool:
    """ Validate snippet and device list with user """

    # Print snippet and ask user for confirmation
    netcat.LOGGER.info("Displaying snippet and asking user for confirmation")
    print()
    print("******************** CONFIGURATION SNIPPET ********************")
    print()
    print(snippet)
    print()
    print("***************************************************************")
    print()
    confirmation = input("Type 'yes' if the above snippet is correct: ")
    print()

    if confirmation.lower() != "yes":
        netcat.LOGGER.error("User haven't confirmed validity of snippet")
        return False

    netcat.LOGGER.info("User confirmed validity of snippet")

    # Print device list and ask user for confirmation
    netcat.LOGGER.info("Displaying list of devices and asking user for confirmation")
    print()
    print()
    print("************************* DEVICE LIST *************************")
    print()
    print(", ".join(requested_device_name_list))
    print()
    print("***************************************************************")
    print()
    confirmation = input("Type 'yes' if the above device list is correct: ")
    print()

    if confirmation.lower() != "yes":
        netcat.LOGGER.error("User haven't confirmed validity of device list")
        return False

    netcat.LOGGER.info("User confirmed validity of device list")

    return True


def read_snippet_files(snippet_filenames: List[str]) -> Tuple[str, bool, bool]:
    """ Read snippet file """

    snippet = ""

    for snippet_filename in snippet_filenames:
        netcat.LOGGER.info(f"Reading configuration snippet file '{snippet_filename}'")

        try:
            with open(snippet_filename, "r") as _:
                snippet += _.read() + "\n\n"

        except IOError:
            netcat.LOGGER.error(f"Cannot read configuration snippet file '{snippet_filename}'")
            return "", False, False

    if not snippet:
        netcat.LOGGER.error(f"Configuration snippet file '{snippet_filename}' is empty")
        return "", False, False

    # Check formating integrity of snippet files
    netcat.LOGGER.info("Checking formating integrity of snippet file")

    try:
        snippet.format(site_name="", site_id="", inet_gw="")

    except ValueError as exception:
        netcat.LOGGER.error(f"Formating error found in snipet: '{exception}'")
        return "", False, False

    except KeyError as exception:
        netcat.LOGGER.error(f"Invalid key found in snipet: '{exception}'")
        return "", False, False

    except IndexError:
        netcat.LOGGER.error("Empty key found in snipet")
        return "", False, False

    # Check snippet for any required formating parameters
    netcat.LOGGER.info("Checking snippet file for any formating parameters that will need to be obtained from devices")

    # Check if Site ID detection is required
    if snippet.find("{site_id}") >= 0:
        site_id_check = True
        netcat.LOGGER.info("Site ID from each device will be required to format snippet")

    else:
        site_id_check = False
        netcat.LOGGER.info("Site ID from each device will not be required to format snippet")

    # Check if Internet gateway IP detection is required
    if snippet.find("{inet_gw}") >= 0:
        inet_gw_check = True
        netcat.LOGGER.info("Internet gateway IP from each device will be required to format snippet")

    else:
        inet_gw_check = False
        netcat.LOGGER.info("Internet gateway IP from  each device will not be required to format snippet")

    return snippet, site_id_check, inet_gw_check


def deploy_config_snippet(device_info: Dict[str, str], snippet: str, site_id_check: bool, inet_gw_check: bool, no_commit: bool) -> None:
    """ Access device, read all neccessary local settings and deploy snippet  """

    def _(cli: Any, snippet: str, site_id_check: bool, inet_gw_check: bool, no_commit: bool = False) -> None:

        site_name = ""
        site_id = ""
        inet_gw = ""

        if site_id_check:
            site_id = cli.get_site_id()

        if inet_gw_check:
            inet_gw = cli.get_inet_gw()

        if device_info["device_type"] == "paloalto":
            site_name = device_info["device_name"][0:-3].upper()

        snippet = snippet.format(site_name=site_name, site_id=site_id, inet_gw=inet_gw)
        cli.create_config_snapshot()
        cli.deploy_config_snippet(snippet, no_commit)

    if device_info["device_type"] == "paloalto":
        with PACliAccess(device_info) as cli:
            _(cli, snippet, site_id_check, inet_gw_check, no_commit)

    elif device_info["device_type"] == "cisco_router":
        with CiscoCliAccess(device_info) as cli:
            _(cli, snippet, site_id_check, inet_gw_check)

    elif device_info["device_type"] == "cisco_switch":
        with CiscoCliAccess(device_info) as cli:
            _(cli, snippet, site_id_check, inet_gw_check)

    else:
        raise netcat.CustomException(f"Unsupported device type '{device_info['type']}'")


@netcat.exception_handler
def cli_process(device_info: Dict[str, str], snippet: str, site_id_check: bool, inet_gw_check: bool, no_commit: bool) -> List[Dict[str, str]]:
    """ Command line process, ready to run as separate thread or process """

    # Setup logger to show process name
    netcat.bind_logger(device_info["device_name"].upper())

    # Time process execution
    start_time = time.time()

    # Log initial status
    netcat.LOGGER.opt(ansi=True).info("<green>Starting CLI process</green>")

    # Deploy configuration snippet
    deploy_config_snippet(device_info, snippet, site_id_check, inet_gw_check, no_commit)

    # Time process execution
    end_time = time.time()

    # Log process end status and execution time
    netcat.LOGGER.opt(ansi=True).info(f"<green>CLI process ended normaly, execution time: {end_time - start_time:.2f}s</green>")

    return [device_info["device_name"]]


def parse_arguments(args: Optional[List[Any]] = None) -> argparse.Namespace:
    """ Parse comand line arguments """

    parser = argparse.ArgumentParser()
    parser.add_argument("-D", "--debug", action="store_true", help="enable debug logs")
    parser.add_argument("-S", "--single-process", action="store_true", help="enable single procss operation for debuging purposes")
    parser.add_argument("-n", "--non-interactive", action="store_true", help="disable interactive mode")
    parser.add_argument("-c", "--no-commit", action="store_true", help="do not commit configuration on PA")
    parser.add_argument("-s", "--snippet", action="store", nargs="+", help="configuration snippet file", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-g", "--group", action="store", choices=("cisco_router", "cisco_switch"), help="chose group of devices")
    group.add_argument("-d", "--device", action="store", nargs="+", help="specify device or device list")
    group.add_argument("-i", "--ip-address", action="store", help="specify device IP address (local subnet PA azure WAN deployments only)")
    group.add_argument("-r", "--regexp", action="store", nargs="+", help="specify device(s) by regular expression")

    return parser.parse_args(args)


def main() -> int:
    """ Main program """

    arguments = parse_arguments()
    netcat.SINGLE_PROCESS_MODE = arguments.single_process

    print("\nNetCat Deploy, ver 5.5 - 2020, Sebastian Majewski\n")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S EDT")

    # Setup logger
    netcat.setup_logger("netcat_deploy", debug=arguments.debug)
    netcat.LOGGER.info(f"Starting deployment program at '{timestamp}'")

    arguments.debug and netcat.LOGGER.opt(ansi=True).info("<magenta>Debug mode enabled</magenta>")
    arguments.single_process and netcat.LOGGER.opt(ansi=True).info("<magenta>Single process mode enabled</magenta>")

    # Handle device passed by IP address (for PA Azure WAN upgrades from local management network)
    if arguments.ip_address:
        if not netcat.validate_ip_address(arguments.ip_address):
            netcat.LOGGER.error(f"Invalid IP address: {arguments.ip_address}")
            sys.exit()

        requested_device_name_list = [arguments.ip_address]

        device_info_list = [
            {
                "auth": "password",
                "device_name": arguments.ip_address,
                "device_type": "paloalto",
                "password": "azurewan",
                "username": "azurewan"
            },
        ]

    else:

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

    # Read snippet file
    snippet, site_id_check, inet_gw_check = read_snippet_files(arguments.snippet)

    # If there was issue reading snippet file quit program
    if not snippet:
        sys.exit()

    # If required confirm validity of snippet and device list with user, quit program if not confirmed
    if not arguments.non_interactive:
        if not confirm_deployment_validity(snippet, requested_device_name_list):
            sys.exit()

    # Run CLI processes
    netcat.LOGGER.info(f"Executing backup for {len(requested_device_name_list)} device(s): {', '.join(requested_device_name_list)}")

    # Time deployment execution
    start_time = time.time()

    # Execute separate process per device or continue as the same process if SINGLE_PROCESS_MODE flag is set
    successful_device_name_list = sorted(
        netcat.execute_data_processing_function([_ for _ in device_info_list if _["device_name"] in requested_device_name_list],
        cli_process, snippet, site_id_check, inet_gw_check, arguments.no_commit)
    )

    # Create failed device info list
    failed_device_name_list = sorted(set(requested_device_name_list) - set(successful_device_name_list))

    # Time backup execution
    end_time = time.time()

    netcat.LOGGER.info(f"Deployment ended, execution time: '{end_time - start_time:.2f}s'")

    # Report processe's finish status
    netcat.report_final_status(requested_device_name_list, successful_device_name_list, failed_device_name_list)

    return 0


if __name__ == "__main__":
    sys.exit(main())
