#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.5 - 2020, Sebastian Majewski

cisco_cli.py - module used to access cli of Cisco devices

"""

import datetime

from typing import Dict, Tuple, Any

import netcat
import netcat_cli


OUTPUT_FORMATS_CISCO_NEXUS: Tuple[Dict[str, Any], ...] = (
    {
        "format_name": "backup_running",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": [],
        "commands": ["show running-config"],
        "post_commands": [],
    },
    {
        "format_name": "backup_startup",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": [],
        "commands": ["show startup-config"],
        "post_commands": [],
    },
    {
        "format_name": "info",
        "output_start": 1,
        "output_end": -1,
        "pre_commands": [],
        "commands": [
            "show clock",
            "show version",
            "show processes cpu history",
            "show mac address-table",
            "show interface status",
        ],
        "post_commands": [],
    },
)

OUTPUT_FORMATS_CISCO_ROUTER: Tuple[Dict[str, Any], ...] = (
    {
        "format_name": "backup_running",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": [],
        "commands": ["show running-config"],
        "post_commands": [],
    },
    {
        "format_name": "backup_startup",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": [],
        "commands": ["show startup-config"],
        "post_commands": [],
    },
    {
        "format_name": "info",
        "output_start": 1,
        "output_end": -1,
        "pre_commands": [],
        "commands": [
            "show clock",
            "show version",
            "show processes cpu history",
            "show ip bgp summary",
            "show ip interface brief",
            "show ip arp",
            "show ip dhcp binding",
            "show vrf brief",
            "show crypto isakmp sa detail",
            "show crypto ikev2 sa detail",
            "show crypto session detail",
            "show crypto ipsec sa",
        ],
        "post_commands": [],
    },
)

OUTPUT_FORMATS_CISCO_SWITCH: Tuple[Dict[str, Any], ...] = (
    {
        "format_name": "backup_running",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": [],
        "commands": ["show running-config"],
        "post_commands": [],
    },
    {
        "format_name": "backup_startup",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": [],
        "commands": ["show startup-config"],
        "post_commands": [],
    },
    {
        "format_name": "info",
        "output_start": 1,
        "output_end": -1,
        "pre_commands": [],
        "commands": [
            "show clock",
            "show version",
            "show processes cpu history",
            "show mac address-table",
            "show interfaces status",
            "show ip dhcp snooping binding",
        ],
        "post_commands": [],
    },
)

OUTPUT_FORMATS_CISCO_ASA: Tuple[Dict[str, Any], ...] = (
    {
        "format_name": "backup_running",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": [],
        "commands": ["show running-config"],
        "post_commands": [],
    },
    {
        "format_name": "backup_startup",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": [],
        "commands": ["show startup-config"],
        "post_commands": [],
    },
    {
        "format_name": "info",
        "output_start": 1,
        "output_end": -1,
        "pre_commands": [],
        "commands": [
            "show clock",
            "show version",
        ],
        "post_commands": [],
    },
)

OUTPUT_FORMATS_CISCO_ASA_MC: Tuple[Dict[str, Any], ...] = (
    {
        "format_name": "backup_running",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": ["changeto system"],
        "commands": ["show running-config"],
        "post_commands": [],
    },
    {
        "format_name": "backup_startup",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": ["changeto system"],
        "commands": ["show startup-config"],
        "post_commands": [],
    },
    {
        "format_name": "info",
        "output_start": 1,
        "output_end": -1,
        "pre_commands": ["changeto system"],
        "commands": [
            "show clock",
            "show version",
        ],
        "post_commands": [],
    },
    {
        "format_name": "backup_admin_running",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": ["changeto context ADMIN"],
        "commands": ["show running-config"],
        "post_commands": [],
    },
    {
        "format_name": "backup_admin_startup",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": ["changeto context ADMIN"],
        "commands": ["show startup-config"],
        "post_commands": [],
    },
    {
        "format_name": "info_admin",
        "output_start": 1,
        "output_end": -1,
        "pre_commands": ["changeto context ADMIN"],
        "commands": [
            "show clock",
            "show version",
        ],
        "post_commands": [],
    },
    {
        "format_name": "backup_vfi_running",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": ["changeto context VFI"],
        "commands": ["show running-config"],
        "post_commands": [],
    },
    {
        "format_name": "backup_vfi_startup",
        "output_start": 4,
        "output_end": -1,
        "pre_commands": ["changeto context VFI"],
        "commands": ["show startup-config"],
        "post_commands": [],
    },
    {
        "format_name": "info_vfi",
        "output_start": 1,
        "output_end": -1,
        "pre_commands": ["changeto context VFI"],
        "commands": [
            "show clock",
            "show version",
        ],
        "post_commands": [],
    },
)


class CiscoCliAccess(netcat_cli.NetCatCliAccess):
    """ CLI access class for Cisco devices """

    def __init__(self, device_info: Dict[str, str]) -> None:

        super().__init__(device_info)

        if self.type == "cisco_nexus":
            self.cli_prompt = rf"{self.name.upper()}(\(conf.*\))?# "
            self.password_prompt = "[Pp]assword: "
            self.output_formats = OUTPUT_FORMATS_CISCO_NEXUS

        elif self.type == "cisco_router":
            self.cli_prompt = rf"{self.name.upper()}(\(conf.*\))?#"
            self.password_prompt = "Password: "
            self.output_formats = OUTPUT_FORMATS_CISCO_ROUTER

        elif self.type == "cisco_switch":
            self.cli_prompt = rf"{self.name.upper()}(\(conf.*\))?#"
            self.password_prompt = "[Pp]assword: "
            self.output_formats = OUTPUT_FORMATS_CISCO_SWITCH

        elif self.type == "cisco_asa":
            self.cli_prompt = rf"{self.name.upper()}(\(config\))?# "
            self.password_prompt = "password: "
            self.output_formats = OUTPUT_FORMATS_CISCO_ASA

        elif self.type == "cisco_asa_mc":
            self.cli_prompt = rf"VF(1|2)FW1\/(pri|sec)\/act\/?[A-Z]*(\(config\))?# "
            self.password_prompt = "password: "
            self.output_formats = OUTPUT_FORMATS_CISCO_ASA_MC

        else:
            raise netcat.CustomException(f"Unknown device type: {self.type}")

    def setup_cli(self) -> None:
        """ Setup CLI to make it usable for automated operation """

        netcat.LOGGER.info("Configuring initial cli setup")

        self.clear_pexpect_buffer()

        if self.type in {"cisco_asa", "cisco_asa_mc"}:
            self.send_command("terminal pager 0")
        else:
            self.send_command("terminal length 0")
            self.send_command("terminal width 500")

    @netcat_cli.exception_handler
    def get_site_id(self) -> str:
        """ Detect site ID """

        netcat.LOGGER.info("Detecting Site ID")

        # We do it for routers only, makes little sense to do for other devices
        if self.type == "cisco_router":
            if site_id := netcat.find_regex_sl(self.send_command("show ip bgp summary"), r"^BGP router identifier \d+\.(\d+).\d+.\d+,.*$"):
                netcat.LOGGER.info(f"Detected Site ID: {site_id}")
                return site_id

        raise netcat.CustomException("Cannot site id in 'show ip bgp summary' comman output")

    @netcat_cli.exception_handler
    def get_inet_gw(self) -> str:
        """ Detect Internet default gateway """

        netcat.LOGGER.info("Detecting Internet default gateway IP address")

        # We do it for routers only, makes little sense to do for other devices
        if self.type == "cisco_router":

            if inet_gw := netcat.find_regex_sl(self.send_command("show running-config | include 0.0.0.0 0.0.0.0"),
                    r"^ip route (?:vrf INTERNET )?0\.0\.0\.0 0\.0\.0\.0 (\d+\.\d+\.\d+\.\d+) .*$"):
                netcat.LOGGER.info("Detected Internet default gateway IP address: {}", inet_gw)
                return inet_gw

        raise netcat.CustomException("Cannot detect Site ID")

    def enter_config_mode(self) -> None:
        """ Enter Cisco configuration mode """

        netcat.LOGGER.debug("Entering configuration mode")
        self.send_command("configure terminal")
        self.clear_pexpect_buffer()

    def exit_config_mode(self) -> None:
        """ Exit Cisco configuration mode """

        netcat.LOGGER.debug("Exiting configuration mode")
        self.send_command("end")
        self.clear_pexpect_buffer()

    @netcat_cli.exception_handler
    def deploy_config_snippet(self, snippet: str) -> None:
        """ Deploy config line by line """

        netcat.LOGGER.info("Configuration deployment started")

        snippet_lines = snippet.split("\n")

        self.enter_config_mode()

        for line in snippet_lines:
            if line and line[0].lstrip() != "#":
                netcat.LOGGER.opt(ansi=True).info("Deploying line '<cyan>{}</cyan>'", line)

                # Need to push additional Enter after each line to account for some config commands requring confiramation, eg. 'no username'
                self.send_command(line + "\r")

        netcat.LOGGER.info("Configuration deployment finished")

        netcat.LOGGER.info("Saving configuration on device")

        self.exit_config_mode()

        self.send_command("copy running-config startup-config\r\r\r\r\r")

        netcat.LOGGER.info("Configuration saved on device")

        netcat.LOGGER.opt(ansi=True).info("<green>Configuration deployment successful</green>")

    def create_config_snapshot(self) -> None:
        """ Create local configuration snapshot on the device """

        config_name = datetime.datetime.now().strftime("%Y%m%d_%H%M_netcat")
        netcat.LOGGER.info(f"Saving configuration snapshot '{config_name}'")
        self.send_command(f"copy running-config flash:/{config_name}\r\r\r\r\r")
