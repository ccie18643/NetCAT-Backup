#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.0 - 2020, Sebastian Majewski

netcat.py (Core ver) - module containing global variables, exceptions and shared functions

"""

import os
import re
import sys
import json
import time
import socket
import random
import argparse
import functools
import concurrent.futures

from typing import List, Dict, Tuple, Any, Callable, Optional

import loguru  # type: ignore


FILENAME_DEVICE_INFO_LIST: str = "device_info_list.json"
FILENAME_DEVICE_NAME_LIST: str = "device_name_list.txt"
FILENAME_DNS_INFO_LIST: str = "dns_info_list.json"
FILENAME_LOGIN_CISCO: str = "login_cisco.txt"
FILENAME_LOGIN_F5: str = "login_f5.txt"

SUPPORTED_DEVICE_TYPES: Tuple[str, ...] = ("paloalto", "f5", "cisco_nexus", "cisco_router", "cisco_switch", "cisco_asa", "cisco_asa_mc")

DEBUG_MODE: bool = False
SINGLE_PROCESS_MODE: bool = False
LOGGER: Any = None

# Number of simultaneously ran processes, 240 is right number for 4 CPU cores and 4GB of ram at 50% of average load
MAX_WORKERS: int = 120

#DB_INTERFACE = "MongoDB"
DB_INTERFACE = "DynamoDB"
#DB_INTERFACE = "FsDB"

DBT_INFO = "netcat_info"
DBT_BACKUP = "netcat_backup"
DBT_STATUS = "netcat_status"


class CustomException(Exception):
    """ Custom exception class used to raise NetCAT specific exception whenever unrecoverable error occurs """


def encode_command(command_name):
    """ Encode command name to ensure it doesnt contain any weird characters """

    from binascii import hexlify

    return hexlify(command_name.encode("utf-8")).decode("utf-8").translate(str.maketrans("1234567890", "ghijklmnop"))


def decode_command(command_name):
    """ Decode command name previously encoded by 'encode_command_name' function """

    from binascii import unhexlify

    return str(unhexlify(command_name.translate(str.maketrans("ghijklmnop", "1234567890"))), "utf-8")


def compress_device_data(device_data):
    """ Compress command outputs in device data structure """

    from bz2 import compress
    from base64 import b85encode

    if not device_data:
        return {}

    compressed_device_data = {
        "snapshot_timestamp": device_data.get("snapshot_timestamp"),
        "device_name": device_data.get("device_name"),
        "device_type": device_data.get("device_type"),
        "output_formats": {},
    }

    for format_name, format_data in device_data.get("output_formats",{}).items():
        compressed_device_data["output_formats"][format_name] = {}
        for command_name, command_data in format_data.items():
            compressed_device_data["output_formats"][format_name][encode_command(command_name)]  = str(b85encode(compress(bytes(command_data, "utf-8"))), "utf-8")

    return compressed_device_data


def decompress_device_data(compressed_device_data):
    """ Decompress command outputs in device data structure """

    from bz2 import decompress
    from base64 import b85decode

    if not compressed_device_data:
        return {}

    device_data = {
        "snapshot_timestamp": compressed_device_data.get("snapshot_timestamp"),
        "device_name":  compressed_device_data.get("device_name"),
        "device_type": compressed_device_data.get("device_type"),
        "output_formats": {},
    }

    for format_name, format_data in compressed_device_data.get("output_formats",{}).items():
        device_data["output_formats"][format_name] = {}
        for command_name, command_data in format_data.items():
            device_data["output_formats"][format_name][decode_command(command_name)]  = str(decompress(b85decode(command_data)), "utf-8")

    return device_data


def find_regex_sl(*args: Any, **kwargs: Any) -> str:
    """ Wrapper for find_regex_ml() function to easily handle cases when we only expect to pull the value(s) from single line of text """

    return (find_regex_ml(*args, **kwargs) or [""])[0]


def find_regex_ml(text: str, regex: str, /, *, hint: Optional[str] = None, optional: bool = True) -> List[str]:
    """ Find single or multiple values per each of the lines of text. Uses regex grouping mechanism to mark interesting values. """

    if hint:
        if optional and hint not in text:
            return []

        if not (text_lines := [_ for _ in text.split("\n") if hint in _]):
            return []

    else:
        text_lines = text.split("\n")

    cregex = re.compile(regex)

    return [_.groups() if len(_.groups()) > 1 else _.group(1) for __ in text_lines if (_ := cregex.search(__.rstrip("\r")))]


def fn() -> str:
    """ Returns name of current function. Goes deeper if current fuction name is _, __ or ___ """

    for depth in range(1, 4):
        name = sys._getframe(depth).f_code.co_name
        if name in {"_", "__", "___"}:
            return name + "()"

    return "unknown()"


def validate_ip_address(ip_address: str) -> bool:
    """ Validate IP address """

    if re.search(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_address):
        try:
            socket.inet_aton(ip_address)
        except OSError:
            return False
        return True
    return False


def read_info_list_file(info_list_filename) -> List[Dict[str, str]]:
    """ Reads info list file and returns list of info structures """

    LOGGER.info(f"Reading info list file '{info_list_filename}'")

    try:
        with open(info_list_filename) as _:
            info_list: List[Dict[str, str]] = json.load(_)
            return info_list

    except IOError:
        LOGGER.error(f"{fn()}: Cannot read info list from '{info_list_filename}' file")
        return []

    except json.decoder.JSONDecodeError as exception:
        LOGGER.error(f"{fn()}: Cannot parse json info list file '{info_list_filename}', error '{exception}'")
        return []


def setup_logger(app_name: str, debug: bool = False, process_name_length: int = 14, stdout: bool = True, file: bool = True) -> None:
    """ Setting up logger """

    log_level = "DEBUG" if debug else "INFO"

    loguru.logger.remove(0)

    if stdout:
        loguru.logger.add(sys.stdout, colorize=True, level=log_level, format=f"<green>{{time:YYYY-MM-DD HH:mm:ss}}</green> <level>| {{level:7}} "
                + f"|</level> <level>{{extra[process_name]:{process_name_length}}} | {{message}}</level>")

    if file:
        path = "/var/log/netcat_backup"

        if os.getcwd().split("/")[-2] == "devel":
            path += "_devel"

        loguru.logger.add(os.path.join(path, app_name + ".log"), mode="a", rotation="1 day", retention="1 month", level=log_level,
                format=f"{{time:YYYY-MM-DD HH:mm:ss}} <level>| {{level:7}} |</level> <level>{{extra[process_name]:"
                + f"{process_name_length}}} | {{message}}</level>")

    bind_logger("MAIN_PROG")


def bind_logger(process_name: str) -> None:
    """ Bind specific process name to logger """

    global LOGGER

    LOGGER = loguru.logger.bind(process_name=process_name)


def report_final_status(requested_device_name_list: List[str], successful_device_name_list: List[str], failed_device_name_list: List[str]) -> None:
    """ Report final status showing successful and failed device count and lists"""

    if successful_device_name_list:
        LOGGER.opt(ansi=True).info(
            f"<green>Operation executed successfully for {len(successful_device_name_list)}/{len(requested_device_name_list)} device(s): " +
            f"{', '.join(successful_device_name_list)}</green>")

    if failed_device_name_list:
        LOGGER.warning(f"Operation failed for {len(failed_device_name_list)}/{len(requested_device_name_list)} device(s): {', '.join(failed_device_name_list)}")


def get_requested_device_name_list(device_info_list: List[Dict[str, str]], args: argparse.Namespace) -> List[str]:
    """ Create list of device names based on command line arguments (already parsed) """

    if hasattr(args, "all") and args.all:
        return [_["device_name"] for _ in device_info_list]

    if hasattr(args, "group") and args.group in SUPPORTED_DEVICE_TYPES:
        return [_["device_name"] for _ in device_info_list if _["device_type"] == args.group]

    if hasattr(args, "device") and args.device:
        return [_["device_name"] for _ in device_info_list if _["device_name"] in {_.strip(",") for _ in args.device}]

    if hasattr(args, "regexp") and args.regexp:
        try:
            return [_["device_name"] for _ in device_info_list if re.search(args.regexp, _["device_name"])]

        except re.error:
            LOGGER.warning(f"Unable to parse regex string '{args.regexp}'")
            return []

    return []


def validate_ip_address(ip_address: str) -> bool:
    """ Validate IP address """

    from socket import inet_aton

    if re.search(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_address):
        try:
            inet_aton(ip_address)
        except OSError:
            return False
        return True
    return False


def exception_handler(function):
    """ Decorator to log exceptions """

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)

        except CustomException as exception:
            LOGGER.error(f"{exception}")
            sys.exit(1)

        except KeyboardInterrupt:
           LOGGER.error("Program aborted by user...") 
           sys.exit(1)

        except SystemExit:
            raise

        except:
            LOGGER.error(f"Unknown exception '{sys.exc_info()}'")
            raise

    return wrapper


def execute_data_processing_function(data_list: List[Any], data_processing_function: Callable[..., List[Any]],
        *args: Any, max_workers: int = MAX_WORKERS, **kwargs: Any) -> List[Any]:
    """ Execute generic data processing function in single or multiprocess manner and return merged list of results """

    if not data_list:
        return []

    if SINGLE_PROCESS_MODE:
        results = [data_processing_function(_, *args, **kwargs) for _ in data_list]

    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=min(max_workers, len(data_list))) as executor:
            process_pool = [executor.submit(data_processing_function, _, *args, **kwargs) for _ in data_list]

        results = [_.result() for _ in process_pool if not _.exception() and _.result()]

    return [_ for __ in results for _ in __]


