#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.5 - 2020, Sebastian Majewski

pa_cli.py - module used to access cli of Palo Alto devices

"""

import time
import datetime

from typing import Dict, Any, Tuple

import netcat
import netcat_cli


OUTPUT_FORMATS_PALOALTO: Tuple[Dict[str, Any], ...] = (
    {
        "format_name": "backup_set",
        "output_start": 1,
        "output_end": -2,
        "pre_commands": ["set cli config-output-format set", "configure"],
        "commands": ["show"],
        "post_commands": ["exit"],
    },
    {
        "format_name": "backup_xml",
        "output_start": 1,
        "output_end": -2,
        "pre_commands": ["set cli config-output-format xml", "configure"],
        "commands": ["show"],
        "post_commands": ["exit"],
    },
    {
        "format_name": "backup_running",
        "output_start": 2,
        "output_end": -2,
        "pre_commands": [],
        "commands": ["show config running"],
        "post_commands": [],
    },
    {
        "format_name": "info",
        "output_start": 2,
        "output_end": -2,
        "pre_commands": [],
        "commands": [
            "show clock",
            "show system info",
            "show high-availability all",
            "show routing protocol bgp summary",
            "show interface all",
            "show arp all",
            "show dhcp server lease interface all",
        ],
        "post_commands": [],
    },
)


class PACliAccess(netcat_cli.NetCatCliAccess):
    """ CLI access class for PA devices """

    def __init__(self, device_info: Dict[str, str]) -> None:

        super().__init__(device_info)

        self.cli_prompt = rf"{self.username}@{self.name.upper()}\(?(active-primary|active-secondary|active|passive|non-functional|suspended|)\)?[#>] "
        self.password_prompt = r"Password: "
        self.output_formats = OUTPUT_FORMATS_PALOALTO

    @netcat_cli.exception_handler
    def validate_ha_state(self, snippet: str, timeout: int = 30) -> Any:
        """ Validate if HA state of the device is as expected in snipped file """

        netcat.LOGGER.info("Reading expected HA state from iconfiguration snippet")

        # Read expected HA status from snippet
        for line in snippet.split("\n"):
            if line.find(r"# Expected HA state: ") >= 0:
                expected_ha_state = line[20:].strip().lower()
                break
        else:
            netcat.LOGGER.info("Configuration snippet doesn't contain information about expected HA state, assuming 'active' state")
            expected_ha_state = "active"

        netcat.LOGGER.info(f"Expected HA state: '{expected_ha_state}'")

        netcat.LOGGER.info("Validating device's HA state")

        self.cli.sendline("")  # type: ignore

        expect_output_index = self.cli.expect(  # type: ignore
            [rf"{self.username}@{self.name.upper()}\(?({expected_ha_state})\)?[#>] ", self.cli_prompt], timeout=timeout
        )

        if expect_output_index == 0:
            return self.cli.before  # type: ignore

        if expect_output_index == 1:
            raise netcat.CustomException(f"HA state in cli prompt '{self.cli.after}' is not as expected")  # type: ignore

        raise netcat.CustomException(f"Problem with expect when sending command, expect_output_index = {expect_output_index} is out of range")

    def setup_cli(self) -> None:
        """ Setup CLI to make it usable for automated operation """

        netcat.LOGGER.info("Configuring initial cli setup")

        self.send_command("set cli scripting-mode on")

        self.clear_pexpect_buffer()

        self.send_command("set cli terminal width 500")
        self.send_command("set cli terminal height 500")
        self.send_command("set cli pager off")
        self.send_command("set cli confirmation-prompt off")

    @netcat_cli.exception_handler
    def clear_commit_in_progress(self) -> None:
        """ Check if there is any commit in progress and wait till finishes or time out after 3 minutes"""

        netcat.LOGGER.info("Checking for any other commit in progress")

        for _ in range(6):
            if netcat.find_regex_sl(self.send_command("show jobs processed"), r"(^[^ ]+ [^ ]+ +[^ ]+ +\d+ +Commit +ACT .*$)"):
                netcat.LOGGER.warning("Another commit in progress, will wait 30s and recheck")
                time.sleep(30)
                continue
            break

        else:
            raise netcat.CustomException("Another commit in progress takes over 3 minutes")

        netcat.LOGGER.info("No other commit in progress")

    @netcat_cli.exception_handler
    def get_site_id(self) -> str:
        """ Detect site ID """

        if site_id := netcat.find_regex_sl(self.send_command("show routing protocol bgp summary"), r"^ +router id: +\d+\.(\d+)\.\d+\.\d+$"):
            netcat.LOGGER.info(f"Detected Site ID: {site_id}")
            return site_id

        raise netcat.CustomException("Cannot detect site id in 'show routing protocol bgp summary' command output")

    @netcat_cli.exception_handler
    def get_inet_gw(self) -> str:
        """ Detect Internet default gateway """

        netcat.LOGGER.info("Detecting Internet default gateway IP address")

        if inet_gw := netcat.find_regex_sl(self.send_config_command(
                "show network virtual-router VR_GLOBAL routing-table ip static-route SR_DEFAULT nexthop"), r"^.+ (\d+\.\d+\.\d+.\d+)$"):
            netcat.LOGGER.info(f"Detected Internet default IP address: {inet_gw}")
            return inet_gw

        raise netcat.CustomException("Cannot find 'desitnation' == '0.0.0.0/0 in 'show routing route type static virtual-router VR_GLOBAL' command output")

    def enter_config_mode(self) -> None:
        """ Enter PA configuration mode """

        netcat.LOGGER.debug("Entering configuration mode")
        self.send_command("configure")

    def exit_config_mode(self) -> None:
        """ Exit PA configuration mode """

        netcat.LOGGER.debug("Exiting configuration mode")
        self.send_command("exit")

    @netcat_cli.exception_handler
    def download_software(self, requested_software_version: str) -> None:
        """ Download software """

        major = requested_software_version.split(".")[0]
        minor = requested_software_version.split(".")[1]
        patch = requested_software_version.split(".")[2]

        requested_software_version_dependencies = [f"{major}.0.0"]
        if minor != "0":
            requested_software_version_dependencies.append(f"{major}.{minor}.0")
        if patch != "0":
            requested_software_version_dependencies.append(f"{major}.{minor}.{patch}")

        netcat.LOGGER.info("Detected software version dependencies: {}", " -> ".join(requested_software_version_dependencies))

        # Download latest software list
        netcat.LOGGER.info("Refreshing available software versions")
        available_software_versions = self.send_command("request system software check", timeout=120)
        if server_error := netcat.find_regex_sl(available_software_versions, r"(Server error)"):
            raise netcat.CustomException(f"Received: '{server_error}'")

        # Download all the software versions from dependency list
        for software_version_dependency in requested_software_version_dependencies:
            if netcat.find_regex_sl(available_software_versions, rf"^{software_version_dependency}\s+\S+\s+\S+\s+\S+\s+(\S+)\s*$") == "yes":
                netcat.LOGGER.info(f"Software version {software_version_dependency} already downloaded")
                continue

            # Make up to three attempts to download software
            for _ in range(3):
                netcat.LOGGER.info(f"Attempting to download software version: {software_version_dependency}")

                # Wait up to five minutes in case any other download is in progress
                for _ in range(30):
                    command_output = self.send_command(f"request system software download version {software_version_dependency}")
                    if netcat.find_regex_sl(command_output, r"(^.*Server error.*$)"):
                        if netcat.find_regex_sl(command_output, r"(^.*Server error : Another download is in progress.*$)"):
                            netcat.LOGGER.info("Another download in progress, waiting...")
                            time.sleep(10)
                            continue
                        raise netcat.CustomException(f"Received: '{netcat.find_regex_sl(command_output, r'(^.*Server error.*$)')}'")
                    break
                else:
                    raise netcat.CustomException("Another download in progress for over 5 minutes")

                job_id = netcat.find_regex_sl(command_output, r"^Download job enqueued with jobid (\d+)$")
                netcat.LOGGER.info(f"Download of software version {software_version_dependency} started with job id '{job_id}'")

                time.sleep(5)

                while ((command_output := self.send_command(f"show jobs id {job_id}")) and
                        netcat.find_regex_sl(command_output, rf"^\d\S+\s+\S+\s+(?:\S+\s+)?\d+\s+Downld\s+(\S+)\s+\S+\s+\S+\s*$") in {"ACT", "QUEUED"}):
                   
                    download_progress = netcat.find_regex_sl(command_output, rf"^\d\S+\s+\S+\s+\S+\s+\d+\s+Downld\s+\S+\s+\S+\s+(\S+)\s*$")
                    
                    if download_progress == "99%":
                        netcat.LOGGER.info(f"Preloading software version {software_version_dependency} into software manager")
                        time.sleep(20)

                    else:
                        netcat.LOGGER.info(f"Downloading software version {software_version_dependency}, progress {download_progress}")
                        time.sleep(5)

                if netcat.find_regex_sl(command_output, rf"^\d\S+\s+\S+\s+\S+\s+{job_id}\s+Downld\s+FIN\s+(\S+)\s+\S+\s*$") == "OK":
                    netcat.LOGGER.info(f"Download of version {software_version_dependency} completed")
                    break

                netcat.LOGGER.warning(f"Download of version {software_version_dependency} failed, will retry up to three times...")
                print("***", command_output, "***")

            else:
                raise netcat.CustomException(f"Failed three attempts to download version {software_version_dependency}")

        netcat.LOGGER.info("Download of all required software versions completed")

    @netcat_cli.exception_handler
    def upgrade_software(self, requested_software_version: str) -> None:
        """ Upgrade software """

        # Make up to three attempts to install software
        for _ in range(3):
            for _ in range(30):
                command_output = self.send_command(f"request system software install version {requested_software_version}")
                if netcat.find_regex_sl(command_output, r"(Server error)"):
                    if netcat.find_regex_sl(command_output, r"(install is in progress)"):
                        netcat.LOGGER.info("Another installation in progress, waiting...")
                        time.sleep(10)
                        continue
                    if netcat.find_regex_sl(command_output, r"(pending jobs in the commit task queue)"):
                        netcat.LOGGER.info("Pending jobs in commit task queue, waiting...")
                        time.sleep(10)
                        continue
                    if netcat.find_regex_sl(command_output, r"(commit is in progress)"):
                        netcat.LOGGER.info("Commit is in progress, waiting...")
                        time.sleep(10)
                        continue
                    raise netcat.CustomException(f"Received: '{netcat.find_regex_sl(command_output, r'(Server error)')}'")
                break
            else:
                raise netcat.CustomException("Another installation in progress for over 5 minutes")

            job_id = netcat.find_regex_sl(command_output, r"^Software install job enqueued with jobid (\d+)\.\s+.*$")

            netcat.LOGGER.info(f"Installation of software version {requested_software_version} started with job id '{job_id}'")

            time.sleep(5)

            while ((command_output := self.send_command(f"show jobs id {job_id}")) and
                    netcat.find_regex_sl(command_output, rf"^\d\S+\s+\S+\s+(?:\S+\s+)?\d+\s+SWInstall\s+(\S+)\s+\S+\s+\S+\s*$") in {"ACT", "QUEUED"}):
                
                installation_progress = netcat.find_regex_sl(command_output, rf"^\d\S+\s+\S+\s+\S+\s+\d+\s+SWInstall\s+\S+\s+\S+\s+(\S+)\s*$")

                netcat.LOGGER.info(f"Installing software version {requested_software_version}, progress {installation_progress}")
                time.sleep(5)

            if netcat.find_regex_sl(command_output, rf"^\d\S+\s+\S+\s+\S+\s+\d+\s+SWInstall\s+FIN\s+(\S+)\s+\S+\s*$") == "OK":
                netcat.LOGGER.info(f"Installation of software version {requested_software_version} completed")
                break

            netcat.LOGGER.warning(f"Installation of version {requested_software_version} failed, will retry up to three times...")
            print("***", command_output, "***")

        else:
            raise netcat.CustomException(f"Failed three attempts to install version {requested_software_version}")

        # Wait till both of the firewalls have ha working properly and then reboot
        for _ in range(30):
            command_output = self.send_command("show high-availability all")
            ha_states = netcat.find_regex_ml(command_output, r"^\s+State:\s+(\S+).*$")
            if len(ha_states) < 2:
                raise netcat.CustomException(f"Cannot properly read firewalls HA state '{ha_states}'")

            if ha_states[0] in {"active", "passive"} and ha_states[1] in {"active", "passive"}:
                netcat.LOGGER.info(f"Firewalls HA states look okay: {ha_states}")
                break

            netcat.LOGGER.info(f"Firewalls HA states do not look okay yet: {ha_states}, waiting one more minute...")
            time.sleep(60)

        else:
            raise netcat.CustomException("Firewalls HA states do not look okay after 30 minutes of waiting")

        netcat.LOGGER.info("Rebooting system")
        self.send_command("request restart system", alternate_expect_string="The system is going down for reboot NOW!")

    @netcat_cli.exception_handler
    def send_commit_command(self, timeout: int = 300) -> str:
        """ Send commit command to device and wait for it to execute, then return command output """

        netcat.LOGGER.info("Configuration commit started")

        self.cli.sendline("commit")  # type: ignore

        expect_output_index = self.cli.expect([self.cli_prompt,
                f"Please synchronize the peers by running 'request high-availability sync-to-remote running-config' first\.\r\n"
                + f"Would you like to proceed with commit\? \(y or n\)"], timeout=timeout)  # type: ignore

        if expect_output_index == 0:
            return str(self.cli.before)  # type: ignore

        if expect_output_index == 1:
            netcat.LOGGER.warning("Need to synchronise configuration to the other node")
            self.send_command("n")
            self.exit_config_mode()
            self.send_command("request high-availability sync-to-remote running-config")
            time.sleep(120)
            netcat.LOGGER.info("Restarting commit")
            return self.commit_config()

        raise netcat.CustomException(f"Problem with expect when executing configuration commit, expect_output_index = {expect_output_index} is out of range")

    @netcat_cli.exception_handler
    def deploy_config_snippet(self, snippet: str, no_commit: bool = False) -> None:
        """ Deploy config line by line i and commit """

        # Validate device's HA state
        self.validate_ha_state(snippet)

        # Wait for another commit to finish, if any
        self.clear_commit_in_progress()

        # Deploy configuration
        netcat.LOGGER.info("Configuration deployment started")

        snippet_lines = snippet.split("\n")

        self.enter_config_mode()

        for line in snippet_lines:
            if line and line[0].lstrip() != "#":
                netcat.LOGGER.opt(ansi=True).info("Deploying line '<cyan>{}</cyan>'", line)
                self.send_command(line)

        netcat.LOGGER.info("Configuration deployment finished")

        self.exit_config_mode()

        # Exit if configuration is not supposed to be commited
        if no_commit:
            netcat.LOGGER.warning("Configuration loaded but not commited (per user request)")
            return

        # Wait for another commit to finish, if any
        self.clear_commit_in_progress()

        # Commit configuration
        self.enter_config_mode()
        command_output = self.send_commit_command()

        commit_output = command_output.split("\n")[3:-2]

        # Check output for commit validation error and report on commit results
        commit_validation_error = False

        for line in commit_output:
            if line.lower().find("error") != -1:
                commit_validation_error = True

        for line in commit_output:
            netcat.LOGGER.opt(ansi=True).info("Commit output: <magenta>{}</magenta>", line)

        netcat.LOGGER.info("Configuration commit finished")

        if commit_validation_error:
            self.send_command("revert config")
            raise netcat.CustomException("Commit validation error detected, reverted to previous configuration")

        self.exit_config_mode()

        netcat.LOGGER.opt(ansi=True).info("<green>Commit validation successful</green>")

    def send_config_command(self, command) -> str:
        """ Send configuration mode command """

        self.send_command("set cli config-output-format set")
        self.enter_config_mode()
        command_output = self.send_command(command)
        self.exit_config_mode()
        self.send_command("set cli config-output-format default")

        return command_output

    def create_config_snapshot(self) -> None:
        """ Create local configuration snapshot on the device """

        config_name = datetime.datetime.now().strftime("%Y%m%d_%H%M_netcat")
        netcat.LOGGER.info(f"Saving configuration snapshot '{config_name}'")
        self.enter_config_mode()
        self.send_command(f"save config to {config_name}")
        self.exit_config_mode()
