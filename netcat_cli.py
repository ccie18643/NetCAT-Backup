#!/usr/bin/env python3

"""

NetCAT config backup, deployment and monitoring system version 5.5 - 2020, Sebastian Majewski

netcat_cli.py - module containing base class for accessing device's cli

"""

import time
import pexpect  # type: ignore
import functools

from typing import Dict, Any, Tuple, Optional

import netcat


def exception_handler(function: Any) -> Any:
    """ Decorator used to catch pexpect exceptions within NetCatCliAccess class """

    @functools.wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)

        except pexpect.EOF as exception:
            error_message = exception.value.split("\n")[5]

            if "Host key verification failed" in error_message:
                raise netcat.CustomException("Device identity verification failed")

            if "Authorization failed" in error_message:
                raise netcat.CustomException("Authorization failed")

            if "Connection timed out" in error_message:
                raise netcat.CustomException("Connection timeout")

            raise netcat.CustomException(f"Expect error '{error_message}'")

        except pexpect.TIMEOUT:
            raise netcat.CustomException("Connection timeout")

    return wrapper


class NetCatCliAccess:
    def __init__(self, device_info: Dict[str, str], timestamp=0) -> None:

        # Set class global variables
        self.timestamp: int = timestamp
        self.username: str = device_info["username"]
        self.password: str = device_info["password"]
        self.auth: str = device_info["auth"]
        self.name: str = device_info["device_name"]
        self.type: str = device_info["device_type"]
        self.cli_prompt: str = ""
        self.password_prompt: str = ""
        self.output_formats: Tuple[Dict[str, Any], ...] = ()
        self.cli: Any = None

    def __del__(self) -> None:
        if self.cli:
            self.cli.close()  # type: ignore

    def __enter__(self) -> Any:
        self.open_cli()
        self.setup_cli()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        netcat.LOGGER.info("Closing ssh connection to '{}@{}'", self.username, self.name)
        self.cli.close()  # type: ignore

    def setup_cli(self) -> None:
        pass

    def clear_pexpect_buffer(self) -> None:
        """ Flush out all the junk from pexpect buffer """

        while True:
            try:
                self.cli.expect(self.cli_prompt, timeout=2)  # type: ignore
            except pexpect.TIMEOUT:
                break

    @exception_handler
    def open_cli(self) -> None:
        """ Establish SSH connection to device """

        netcat.LOGGER.info("Opening ssh connection to '{}@{}'", self.username, self.name)

        # Check if we need to perform password authentication
        if self.auth == "password":

            netcat.LOGGER.info("Using password to authenticate")

            self.cli = pexpect.spawn(f"ssh -o PubkeyAuthentication=no -l {self.username} {self.name}", timeout=60, encoding="utf-8")
            expect_output_index =  self.cli.expect([self.password_prompt, "Are you sure you want to continue connecting (yes/no)?", "Connection refused"])

            # Handle situation when connection to device is established for the first time and device's signature needs to be saved
            if expect_output_index == 1:
                netcat.LOGGER.warning("Devices's authenticity record doesn't exist in ssh 'known_hosts' file, adding")
                self.cli.sendline("yes")  # type: ignore
                self.cli.expect(self.password_prompt)  # type: ignore

            # Handle situation when connection to device is being refused, ex. VTY ACL doesn't allow it
            if expect_output_index == 2:
                raise netcat.CustomException("Connection refused by device")

            # Handle situation when first password is rejected (eg. due to device's RADIUS malfunction) and second try is needed
            # No more than two tries are attempted to do not lock user out on device
            for second_password_attempt in [False, True]:
                self.cli.sendline(self.password)  # type: ignore
                netcat.LOGGER.info("Password sent, waiting for cli prompt")

                expect_output_index = self.cli.expect([self.cli_prompt, self.password_prompt])  # type: ignore

                # Cli pompt received
                if expect_output_index == 0:
                    netcat.LOGGER.info("Cli prompt received")
                    return

                # Wrong username / password on first try, will retry as that might been just a Radius glitch
                if expect_output_index == 1 and not second_password_attempt:
                    netcat.LOGGER.warning("Unsuccessful login with supplied credetnials, retrying after 5s")
                    time.sleep(5)
                    continue

                # Wrong username / password on second try, aborting
                if expect_output_index == 1 and second_password_attempt:
                    raise netcat.CustomException("Cannot login with supplied credentials")

                raise netcat.CustomException(f"Problem with expect when logging to device, expect_output_index = {expect_output_index} is out of range")

        # Check if we need to perform RSA authentication
        elif self.auth == "rsa":

            netcat.LOGGER.info("Using RSA key to authenticate")

            self.cli = pexpect.spawn(f"ssh -o PubkeyAuthentication=yes -l {self.username} {self.name}", timeout=60, encoding="utf-8")

            # Prevent hypotetical lockdown due to 'infinite authenticity record missing' event
            for known_hosts_check_happened_already in [False, True]:
                expect_output_index = self.cli.expect(  # type: ignore
                        [self.cli_prompt, "Are you sure you want to continue connecting (yes/no)?", self.password_prompt, "Connection refused"]
                )

                # Cli prompt received
                if expect_output_index == 0:
                    netcat.LOGGER.info("Cli prompt received")
                    return

                # Handle situation when connection to device is established for the first time and device's signature needs to be saved
                if expect_output_index == 1 and not known_hosts_check_happened_already:
                    netcat.LOGGER.warning("Device's authenticity record doesn't exist in ssh 'known_hosts' file, adding")
                    self.cli.sendline("yes")  # type: ignore
                    continue

                # Handle situation when password prompt is presented
                if expect_output_index == 2:
                    raise netcat.CustomException("RSA authentication error, key may not be valid")
            
                # Handle situation when connection to device is being refused, ex. VTY ACL doesn't allow it
                if expect_output_index == 3:
                    raise netcat.CustomException("Connection refused by device")

                raise netcat.CustomException(f"Problem with expect when logging to device, expect_output_index = {expect_output_index} is out of range")

        else:
            raise netcat.CustomException(f"Unknown authentication type '{self.auth}'")

    @exception_handler
    def send_command(self, command: str, timeout: int = 90, alternate_expect_string: Optional[str] = None, ) -> str:
        """ Send command to device and wait for it to execute, then return command output """

        netcat.LOGGER.debug("Executing command '{}'", command)
        self.cli.sendline(command)  # type: ignore

        if alternate_expect_string:
            self.cli.expect(alternate_expect_string, timeout=timeout)  # type: ignore
        else:
            self.cli.expect(self.cli_prompt, timeout=timeout)  # type: ignore

        return str(self.cli.before)  # type: ignore

    def get_device_data(self) -> Dict[str, Any]:
        """ Read info from device and return device_data structure """

        device_data: Dict[str, Any] = {
            "snapshot_timestamp": self.timestamp,
            "device_name": self.name,
            "device_type": self.type,
            "output_formats": {},
        }

        for output_format in self.output_formats:
            netcat.LOGGER.info(f"Reading info from device in '{output_format['format_name']}' format")

            for command in output_format["pre_commands"]:
                self.send_command(command)

            output_format_section = {}

            for command in output_format["commands"]:
                output_format_section[command] = (
                    "\n".join(self.send_command(command).split("\r\n")[output_format["output_start"]: output_format["output_end"]]) + "\n"
                )

            device_data["output_formats"][output_format["format_name"]] = output_format_section  # type: ignore

            for command in output_format["post_commands"]:
                self.send_command(command)

        return device_data


