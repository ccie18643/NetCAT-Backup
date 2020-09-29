#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.5 - 2020, Sebastian Majewski

netcat_dnscheck.py - monitor status of DNS server(s)

"""

import sys
import time
import datetime
import argparse

import asyncio

from typing import List, Dict, Any, Optional

import aiodns

import netcat

if netcat.DB_INTERFACE == "MongoDB":
    import netcat_mongodb as db

if netcat.DB_INTERFACE == "DynamoDB":
    import netcat_dynamodb as db


HOSTNAME_INTERNAL: str = "ntp.verifone.com"
HOSTNAME_EXTERNAL: str = "google.com"


async def dns_check(dns_info: Dict[str, str]) -> None:
    """ Perform DNS check """

    dns_data = {
        "description": dns_info["description"],
        "ip_address": dns_info["ip_address"],
        "results": {}
    }

    async def _(hostname):

        try:
            await resolver.query(hostname, "A")

        except aiodns.error.DNSError as exception:

            if exception.args[0] == 4:
                netcat.bind_logger(dns_info["description"])
                netcat.LOGGER.info(f"Not able to resolve '{hostname}'")
                return "FAIL [R]"

            if exception.args[0] == 12:
                netcat.bind_logger(dns_info["description"])
                netcat.LOGGER.info(f"Not able to connect to server trying to resolve '{hostname}'")
                return "FAIL [C]"

            netcat.LOGGER.info(f"Unknown error trying to resolve '{hostname}' - '{exception.args[1]}'")
            return "FAIL [U]"

        netcat.bind_logger(dns_info["description"])
        netcat.LOGGER.info(f"Successfully resolved '{hostname}'")
        return "OK [CR]"

    resolver = aiodns.DNSResolver(timeout=0)
    resolver.nameservers = [dns_info["ip_address"]]

    netcat.bind_logger(dns_info["description"])
    netcat.LOGGER.info(f"Querrying server for '{HOSTNAME_EXTERNAL}'")
    dns_data["results"]["external"] = await _(HOSTNAME_EXTERNAL)

    netcat.bind_logger(dns_info["description"])
    netcat.LOGGER.info(f"Querrying server for '{HOSTNAME_INTERNAL}'")
    dns_data["results"]["internal"] = await _(HOSTNAME_INTERNAL)

    netcat.bind_logger("MAIN_PROG")

    return dns_data


def parse_arguments(args: Optional[List[Any]] = None) -> argparse.Namespace:
    """ Parse comand line arguments """

    parser = argparse.ArgumentParser()
    parser.add_argument("-D", "--debug", action="store_true", help="enable debug logs")
    parser.add_argument("-T", "--test-run", action="store_true", help="test run, dns status checked but not sent to database")
    parser.add_argument("-a", "--all", action="store_true", required=True, help="all devices")

    return parser.parse_args(args)


async def main() -> int:
    """ Main program """

    timestamp = int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1,0,0,0)).total_seconds())

    arguments = parse_arguments()

    print("\nNetCat DNS Check, ver 5.5 - 2020, Sebastian Majewski\n")

    # Setup logger
    netcat.setup_logger("netcat_dnscheck", process_name_length=15, debug=arguments.debug)
    netcat.LOGGER.info(f"Starting DNS check program, timestamp={timestamp}")

    if arguments.test_run:
        netcat.LOGGER.opt(ansi=True).info("<magenta>Test mode enabled, no information will be saved to database</magenta>")

    if arguments.debug:
        netcat.LOGGER.opt(ansi=True).info("<magenta>Debug mode enabled</magenta>")

    dns_info_list = netcat.read_info_list_file(netcat.FILENAME_DNS_INFO_LIST)

    netcat.LOGGER.info(f"Executing DNS check for {len(dns_info_list)} server(s): '{', '.join([_['ip_address'] for _ in dns_info_list])}'")

    # Check if database tables exist, if not then create them
    db.create_tables()

    # Time processes execution
    start_time = time.monotonic()

    dns_status_document = {
        "snapshot_name": "dns_status",
        "snapshot_timestamp": timestamp,
    }

    dns_status_document["dns_data"] = await asyncio.gather(*[dns_check(_) for _ in dns_info_list])


    netcat.LOGGER.info("Saving dns status document to database")

    # Cannot use netcat.exception_handler decorator due to its lack of compatibility with asyncio
    try:
        db.write(db.netcat.DBT_STATUS, dns_status_document)

    except netcat.CustomException as exception:
        netcat.LOGGER.error(f"{exception}")
        sys.exit()

    # Time processes execution
    end_time = time.monotonic()

    netcat.bind_logger("MAIN_PROG")
    netcat.LOGGER.info(f"DNS check ended, execution time: '{end_time - start_time:.2f}s'")

    return 0


if __name__ == "__main__":
    asyncio.run(main())
