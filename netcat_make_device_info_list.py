#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.5 - 2020, Sebastian Majewski

netcat_make_device_info_list.py - program creates list of all devices based on DNS entries

"""

import re
import json
import sys
import socket

from typing import List, Dict, Any

import dns.zone
import dns.query

import netcat



def zone_transfer(dns_server):
    """ Tansfers 'net.verifone.com' zone from given DNS server """

    # Resolve dns server hostname
    netcat.LOGGER.info(f"Trying to resolve '{dns_server}'")
    try:
        ns = socket.gethostbyname(dns_server)

    except socket.gaierror:
        netcat.LOGGER.warning(f"Cannot resolve '{dns_server}'")
        return

    # Transfer zone from nameserver
    netcat.LOGGER.info(f"Perfroming DNS zone transfer for 'net.verifone.com' from '{dns_server}'")
    try:
        return dns.zone.from_xfr(dns.query.xfr(ns, "net.verifone.com"))

    except OSError as exception:
        netcat.LOGGER.warning(f"DNS server didn't respond: '{exception}'")
        return

    except dns.query.TransferError as exception:
        netcat.LOGGER.warning(f"DNS zone transfer error '{exception}'")
        return


def main() -> int:
    """ Main program """

    # Setup logger
    netcat.setup_logger("netcat_make_device_info_list")

    print("\nNetCAT Make Device Info List, ver 5.5 - 2020, Sebastian Majewski\n")

    # Get localhost hostname
    local_hostname = socket.gethostname()

    if (net_verifone_com := zone_transfer("vf1ns1.net.verifone.com")) is None:
        if (net_verifone_com := zone_transfer("vf1ns2.net.verifone.com")) is None:
            netcat.LOGGER.error(f"Unable to contact either one of 'net.verifone.com' DNS servers")
            sys.exit(1)

    # Read netcat service username and password for Cisco devices
    netcat.LOGGER.info(f"Reading Cisco login from '{netcat.FILENAME_LOGIN_CISCO}' file")
    try:
        with open(netcat.FILENAME_LOGIN_CISCO, "r") as _:
            cisco_username = _.readline().strip()
            cisco_password = _.readline().strip()

    except IOError:
        netcat.LOGGER.error(f"Cannot read Cisco login from '{netcat.FILENAME_LOGIN_CISCO}' file, exiting...")
        sys.exit(3)

    # Read netcat service username and password for F5 devices
    netcat.LOGGER.info(f"Reading F5 login from '{netcat.FILENAME_LOGIN_F5}' file")
    try:
        with open(netcat.FILENAME_LOGIN_F5, "r") as _:
            f5_username = _.readline().strip()
            f5_password = _.readline().strip()

    except IOError:
        netcat.LOGGER.error(f"Cannot read F5 login from '{netcat.FILENAME_LOGIN_F5}' file, exiting...")
        sys.exit(4)

    skip = r"^(?:vf1nms.|vf2nms.|vf1n7k1|vf1n7k2|vf1mrtg1|vf1mrtg2|vf1srvlabsw[12]|vf2ravpnts|vf4ts1)$"

    device_types: List[Dict[str, Any]] = [
        {
            "regex": r"^\S+pa[12]$",
            "device_type": "paloalto",
            "device_info": {"username": local_hostname, "password": "", "device_type": "paloalto", "auth": "rsa"},
        },
        {
            "regex": r"^vf[12]lb[12](?:mgmt|dmz|int|npdmz|npint)$",
            "device_type": "f5",
            "device_info": {"username": f5_username, "password": f5_password, "device_type": "f5", "auth": "password"},
        },
        {
            "regex": r"^\S+n[579]k[1-4](?:-admin|-vfi)?$",
            "device_type": "cisco_nexus",
            "device_info": {"username": cisco_username, "password": cisco_password, "device_type": "cisco_nexus", "auth": "password"},
        },
        {
            "regex": r"^\S+(?:[abd]s[0-9]{1,2}|ms[12]|sw[12]?)$",
            "device_type": "cisco_switch",
            "device_info": {"username": local_hostname, "password": "", "device_type": "cisco_switch", "auth": "rsa"},
        },
        {
            "regex": r"^\S*(?:cr[12]|wr1|sr[12]|ir[12]|ts[12]?|rt[12]?|vf1br-conoco)$",
            "device_type": "cisco_router",
            "device_info": {"username": local_hostname, "password": "", "device_type": "cisco_router", "auth": "rsa"},
        },
        {
            "regex": r"^\S+ravpn[xt]?fw$",
            "device_type": "cisco_asa",
            "device_info": {"username": cisco_username, "password": cisco_password, "device_type": "cisco_asa", "auth": "password"},
        },
        {
            "regex": r"^vf[12]fw[12]$",
            "device_type": "cisco_asa_mc",
            "device_info": {"username": cisco_username, "password": cisco_password, "device_type": "cisco_asa_mc", "auth": "password"},
        },
    ]

    # Json list of all requested devices
    device_info_list = []
    device_name_list = []

    for node in net_verifone_com.nodes:
        # Conversion to string plus sanity formating
        device_name = str(node).split(".")[0].strip().lower()

        if re.search(skip, str(node)):
            continue

        for device_type in device_types:
            if device_type["device_type"] in netcat.SUPPORTED_DEVICE_TYPES and re.search(device_type["regex"], device_name):
                netcat.LOGGER.info(f"Creating '{device_type['device_type']}' entry for node '{device_name}'")

                device_info = dict(device_type["device_info"])
                device_info["device_name"] = device_name
                device_info_list.append(device_info)

                device_name_list.append(device_name)

    # Write device info to json file
    netcat.LOGGER.info(f"Writing device info list to '{netcat.FILENAME_DEVICE_INFO_LIST}' file")

    try:
        with open(netcat.FILENAME_DEVICE_INFO_LIST, "w") as _:
            json.dump(device_info_list, _, indent=4, sort_keys=True)

    except IOError:
        netcat.LOGGER.error(f"Cannot write device info list to '{netcat.FILENAME_DEVICE_INFO_LIST}' file, exiting...")
        sys.exit(5)

    # Write device name list to txt file
    netcat.LOGGER.info(f"Writing device name list to '{netcat.FILENAME_DEVICE_NAME_LIST}' file")

    try:
        with open(netcat.FILENAME_DEVICE_NAME_LIST, "w") as _:
            _.write("\n".join(device_name_list))

    except IOError:
        netcat.LOGGER.error(f"Cannot write device name list to '{netcat.FILENAME_DEVICE_NAME_LIST}' file, exiting...")
        sys.exit(6)

    netcat.LOGGER.info(f"Created device entries for {len(device_info_list)} devices...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
