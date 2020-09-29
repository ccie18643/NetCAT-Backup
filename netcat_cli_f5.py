#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.5 - 2020, Sebastian Majewski

f5_cli.py - module used to access cli of F5 devices

"""

from typing import Dict, Tuple, Any

import netcat
import netcat_cli


OUTPUT_FORMATS_F5: Tuple[Dict[str, Any], ...] = (
    {
        "format_name": "backup",
        "output_start": 2,
        "output_end": -1,
        "pre_commands": [],
        "commands": ["list"],
        "post_commands": [],
    },
    {
        "format_name": "info",
        "output_start": 4,
        "output_end": -2,
        "pre_commands": [],
        "commands": [
            "show sys clock",
            "show sys version",
            "show sys hardware",
        ],
        "post_commands": [],
    },
)


class F5CliAccess(netcat_cli.NetCatCliAccess):
    """ CLI access class for F5 devices """

    def __init__(self, device_info: Dict[str, str]) -> None:

        super().__init__(device_info)

        self.cli_prompt = rf"{self.username}@\({self.name.upper()}\)\(cfg-sync [\w,\s]+\)\((Active|Standby)\)\(\/Common\)\(tmos\)# ")
        self.password_prompt = "Password: "
        self.output_formats = OUTPUT_FORMATS_F5

    def setup_cli(self) -> None:
        """ Setup CLI to make it usable for automated operation """

        netcat.LOGGER.info("Configuring initial cli setup")

        self.send_command("modify cli preference pager disabled")
        self.send_command("modify cli preference display-threshold 0")
        self.send_command("modify cli preference list-all-properties enabled")
