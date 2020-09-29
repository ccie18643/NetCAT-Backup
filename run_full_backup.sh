#!/bin/bash

cd ~netcat_backup/devel/netcat_backup

# Create DNS report
~netcat_backup/python3.8/bin/python netcat_dnscheck.py -a

# Make current device list based on DNS
~netcat_backup/python3.8/bin/python netcat_make_device_info_list.py

# Create backup of all devices in the device list
~netcat_backup/python3.8/bin/python netcat_backup.py -a

cd -
