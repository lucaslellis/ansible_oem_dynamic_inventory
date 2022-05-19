# Ansible Dynamic Inventory for Oracle Enterprise Manager

A python script to generate an Ansible inventory based on an Oracle Enterprise Manager (OEM) repository database.

Based on an example of the book [Ansible for DevOps](http://ansiblefordevops.com/).

Validated against OEM 13.4.

## Requirements

* Python 3.x
* cx_Oracle
* Oracle Client or Oracle Database installed on the same host

## Instructions

* Place the files [ansible_oem_inventory.py](ansible_oem_inventory.py), [config.ini.template](config.ini.template) and
  [static_vars.json.template](static_vars.json.template) on a directory (all of them must be on the same directory).

* Rename [config.ini.template](config.ini.template) to `config.ini` and fill in the repository connection variables.

* Rename [static_vars.json.template](static_vars.json.template) to `static_vars.json` and fill in the static variables.
  In case you don't need static variables, just leave it as an empty [JSON](https://en.wikipedia.org/JSON).

## Validation

```bash
./ansible_oem_inventory.py --list

ansible all -i ./ansible_oem_inventory.py -m ping
```
