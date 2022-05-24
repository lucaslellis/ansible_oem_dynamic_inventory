# Ansible Dynamic Inventory for Oracle Enterprise Manager

A python script to generate an Ansible inventory based on an Oracle Enterprise Manager (OEM) repository database.

Based on an example of the book [Ansible for DevOps](http://ansiblefordevops.com/).

Validated against OEM 13.4.

Groups are dynamically created based on the following properties:

* Repository name (section name in the config.ini file)
* Lifecycle Status
* Line of Business
* Operating System family (e.g.: AIX, Linux, Windows)
* Operating System version (e.g.: Windows Server 2012 Enterprise, Oracle Linux 6.4, Oracle Linux 7.9)

## Requirements

* Python 3.x
* cx_Oracle
* Oracle Client or Oracle Database installed on the same host
* Repository User Privileges:
  * select on ```"REPOSITORY_OWNER".mgmt$target```
  * select on ```"REPOSITORY_OWNER".mgmt$target_properties```
  * Synonyms for ```"REPOSITORY_OWNER".mgmt$target``` and ```"REPOSITORY_OWNER".mgmt$target_properties```

## Instructions

* Ensure that the packages `python3` and `python3-pip` are installed (RHEL 7.x / OEL 7.x).
* Install cx_Oracle with `pip3`. If you don't have root access, a local install for your user is enough.

```bash
pip3 install -U cx_Oracle --user
```

* Download the latest [release](../../releases/latest) and unzip it on a
  directory. The files [ansible_oem_inventory.py](ansible_oem_inventory.py) and
  [config.ini.template](config.ini.template) must exist on the same directory.
* Rename [config.ini.template](config.ini.template) to `config.ini` and fill in the repository connection variables.
* If you need additional static variables, the `group_vars` and `host_vars` directories must be created on the same
  directory that the [ansible_oem_inventory.py](ansible_oem_inventory.py) is stored.

## Validation

```bash
./ansible_oem_inventory.py --list

ansible all -i ./ansible_oem_inventory.py -m ping
```
