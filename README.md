# NetCAT Backup

Set of Python programs used to backup configurations, poll command output status, deploy config snippets and perform automatic software upgrades on Cisco, PaloAlto and F5 devices. Results can be saved into either local/remote MongoDB database, AWS DynamoDB or Azure CosmosDB. Multiprocessing is implemented to work on multiple devices in parallel.

### Sample log showing configuration backup done on 600+ devices in a little bit over two minutes
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/bak_01.jpg)
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/bak_02.png)
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/bak_03.png)
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/bak_04.jpg)


### Sample log showing configuraton snippet being deployed on PaloAlto firewall
Configuration snippets can have hundreds or even thousands lines and they can be deployed
simultanously to multiple devices in a very short time.
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/dep_01.png)
![Sample inventory screenshot](https://github.com/ccie18643/NetCAT-Backup/blob/master/pictures/dep_02.png)

