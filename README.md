# Ansible Dynamic Inventory for Oracle Enterprise Manager

A python script to generate an Ansible inventory based on an Oracle Enterprise Manager (OEM) repository database.

Based on an example of the book [Ansible for DevOps](http://ansiblefordevops.com/).

Validated against OEM 13.4.

## Requirements

* Python 3.x
* cx_Oracle
* Oracle Client or Oracle Database installed on the same host

## Instructions

* Download the latest [release](releases) and unzip it on a directory. The files
  [ansible_oem_inventory.py](ansible_oem_inventory.py) and [config.ini.template](config.ini.template) must exist on the
  same directory.

* Rename [config.ini.template](config.ini.template) to `config.ini` and fill in the repository connection variables.

## Validation

```bash
./ansible_oem_inventory.py --list

ansible all -i ./ansible_oem_inventory.py -m ping
```
