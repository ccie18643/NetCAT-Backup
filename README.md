# NetCAT Backup

### Network automation tool
<br>

NetCAT stands for Network Configuration Automation Tool. The set of Python programs can be used to backup configurations, poll command output status, deploy config snippets, and perform automatic software upgrades on Cisco, Palo Alto, and F5 devices. Results can be saved into either local/remote MongoDB database, AWS DynamoDB or Azure CosmosDB. Multiprocessing is implemented to work on multiple devices in parallel. Other brands of devices can be added easily as just another CLI modules.

---

### Examples

#### Sample log showing configuration backup done on 600+ devices in just over two minutes.
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/bak_01.jpg)
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/bak_02.png)
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/bak_03.png)
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/bak_04.jpg)


#### Sample log showing configuration snippet being deployed on Palo Alto firewall.
Configuration snippets can have hundreds or even thousands of lines and can be deployed
simultaneously to multiple devices in a short time.
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/dep_01.png)
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/dep_02.png)



#### Sample log showing software being upgraded on HA pair of Palo Alto firewalls.
The second firewall reboot process waits until the primary one boots up after reboot, so at least one
is operational at a time. This process obviously can be started for multiple devices in parallel.
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/upg_01.png)
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/upg_02.png)
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/upg_03.png)
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/upg_04.png)
