#!/usr/bin/python3

"""Ansible OEM Inventory

Author: Lucas Pimentel Lellis
Description: A python script to create an Ansible dynamic inventory
             based on Oracle Enterprise Manager repository.
             Validated against OEM 13.4.

Requires: cx_Oracle

TODO multiple repository support
"""

import argparse
import configparser
import json
import os
import sys

import cx_Oracle

_CONFIG_FILE = "config.ini"
_STATIC_VARS_FILE = "static_vars.json"

_JSON_INDENT_SPACES = 4
_ERR_RET_CODE = 1
_SUC_RET_CODE = 0
_EMPTY_INVENTORY = {'_meta': {'hostvars': {}}}


def connect_oracle(host_name, port, username, password, service_name):
    """Returns a connection to an Oracle Database.

    Returns:
        Connection: oracle database connection
    """
    dsn_fmt = """
              (DESCRIPTION =
                  (ADDRESS_LIST =
                      (ADDRESS = (PROTOCOL = TCP)(HOST = {0})(PORT = {1}))
                  )
                  (CONNECT_DATA = (SERVICE_NAME = {2}))
              )"""
    conn = cx_Oracle.Connection(user=username, password=password,
                                dsn=dsn_fmt.format(host_name,
                                                   port,
                                                   service_name))

    return conn


def retrieve_oem_targets(repo_connection):
    """Retrieves a list of OEM host targets

    Each list item is a tuple of:
    - Host name
    - IP Address
    - Lifecycle Status
    - Line of Business

    Args:
        repo_connection (cx_Oracle.Connection): a connection to OEM repository

    Returns:
        list - list of tuples of OEM targets
    """
    query_txt = """
        select
            lower(tgt.target_name) target_name,
            lower(ipadr.property_value) ip_address,
            lower(lfcl.property_value) lifecycle_status,
            lower(lnbus.property_value) line_of_business,
            lower(tgt.type_qualifier1) operating_system,
            regexp_replace(
                lower(tgt.type_qualifier2),
                '[(). ]+', '_') os_version
        from
            mgmt$target tgt
            join mgmt$target_properties ipadr
                on tgt.target_name = ipadr.target_name
                and tgt.target_type = ipadr.target_type
                and tgt.target_guid = ipadr.target_guid
            left outer join mgmt$target_properties lfcl
                on tgt.target_name = lfcl.target_name
                and tgt.target_type = lfcl.target_type
                and tgt.target_guid = lfcl.target_guid
            left outer join mgmt$target_properties lnbus
                on tgt.target_name = lnbus.target_name
                and tgt.target_type = lnbus.target_type
                and tgt.target_guid = lnbus.target_guid
        where
            tgt.target_type = 'host'
            and ipadr.property_name = 'IP_address'
            and (
                lfcl.property_name = 'orcl_gtp_lifecycle_status'
                or lfcl.property_name is null
            )
            and (
                lnbus.property_name = 'orcl_gtp_line_of_bus'
                or lnbus.property_name is null
            )
        order by
            tgt.target_name
    """

    query_cursor = repo_connection.cursor()
    query_cursor.execute(query_txt)

    results = query_cursor.fetchall()

    query_cursor.close()

    return results


def build_dictionary(list_oem_targets, static_vars):
    """Builds the dictionary for ansible

    Args:
        list_oem_targets (list): list of OEM targets containing a 6-member
                                 tuple of
                                 - Host name
                                 - IP Address
                                 - Lifecycle Status
                                 - Line of Business
                                 - Operating System (OS)
                                 - OS version
        static_vars (dict): Dictionary of hardcoded variables

    Returns:
        dictionary - a dictionary of targets and groups for Ansible
    """

    ansible_dict = build_lnbus_lfcycle_groups(list_oem_targets, static_vars)

    build_meta_group(list_oem_targets, static_vars, ansible_dict)

    build_line_business_groups(list_oem_targets, static_vars, ansible_dict)
    build_os_version_groups(list_oem_targets, static_vars, ansible_dict)
    build_oper_system_groups(list_oem_targets, static_vars, ansible_dict)

    return ansible_dict

def build_meta_group(list_oem_targets, static_vars, ansible_dict):
    """Builds the _meta group.

    Args:
        list_oem_targets (list): list of OEM targets containing a 6-member
                                 tuple of
                                 - Host name
                                 - IP Address
                                 - Lifecycle Status
                                 - Line of Business
                                 - Operating System (OS)
                                 - OS version
        static_vars (dict): Dictionary of hardcoded variables
        ansible_dict (dictionary): the ansible dictionary under construction
    """

    hostvars = {}
    for tgt in list_oem_targets:
        host_vars_item = {}
        try:
            host_vars_item = static_vars[tgt[0]]
        except KeyError:
            pass

        host_vars_item["ansible_host"] = tgt[1]
        hostvars[tgt[0]] = host_vars_item

    ansible_dict["_meta"] = {"hostvars": hostvars}


def build_line_business_groups(list_oem_targets, static_vars, ansible_dict):
    """Builds parent groups based on Line of Business.

    Args:
        list_oem_targets (list): list of OEM targets containing a 6-member
                                 tuple of
                                 - Host name
                                 - IP Address
                                 - Lifecycle Status
                                 - Line of Business
                                 - Operating System (OS)
                                 - OS version
        static_vars (dictionary): Dictionary of hardcoded variables
        ansible_dict (dictionary): the ansible dictionary under construction
    """
    line_business_set = {lnbus[3] for lnbus in list_oem_targets}
    for lnbus in line_business_set:
        try:
            static_vars_grp = static_vars[lnbus]
        except KeyError:
            static_vars_grp = {}
        ansible_dict[lnbus] = {"children":
                               [grp for grp in
                                ansible_dict
                                if grp.startswith(lnbus)
                                   and grp != lnbus
                                ],
                               "vars": static_vars_grp}


def build_oper_system_groups(list_oem_targets, static_vars, ansible_dict):
    """Builds parent groups based on Operating Systems.

    Args:
        list_oem_targets (list): list of OEM targets containing a 6-member
                                 tuple of
                                 - Host name
                                 - IP Address
                                 - Lifecycle Status
                                 - Line of Business
                                 - Operating System (OS)
                                 - OS version
        static_vars (dictionary): Dictionary of hardcoded variables
        ansible_dict (dictionary): the ansible dictionary under construction
    """
    oper_syst_set = {oper_syst[4] for oper_syst in list_oem_targets}
    for oper_syst in oper_syst_set:
        try:
            static_vars_grp = static_vars[oper_syst]
        except KeyError:
            static_vars_grp = {}
        ansible_dict[oper_syst] = {"children":
                                   list({vers[5] for vers in list_oem_targets
                                     if vers[4] == oper_syst
                                     }),
                                   "vars": static_vars_grp}


def build_os_version_groups(list_oem_targets, static_vars, ansible_dict):
    """Builds oper groups based on Operating Systems Versions.

    Args:
        list_oem_targets (list): list of OEM targets containing a 6-member
                                 tuple of
                                 - Host name
                                 - IP Address
                                 - Lifecycle Status
                                 - Line of Business
                                 - Operating System (OS)
                                 - OS version
        static_vars (dictionary): Dictionary of hardcoded variables
        ansible_dict (dictionary): the ansible dictionary under construction
    """
    os_version_set = {os_version_set[5] for os_version_set in list_oem_targets}
    for os_version in os_version_set:
        try:
            static_vars_grp = static_vars[os_version]
        except KeyError:
            static_vars_grp = {}
        ansible_dict[os_version] = {"hosts":
                                    [tgt[0]
                                     for tgt in list_oem_targets
                                     if tgt[5] == os_version],
                                    "vars": static_vars_grp}


def build_lnbus_lfcycle_groups(list_oem_targets, static_vars):
    """Builds oper groups based on Line of business and lifecycle status.
       Returns the initial dictionary.

    Args:
        list_oem_targets (list): list of OEM targets containing a 6-member
                                 tuple of
                                 - Host name
                                 - IP Address
                                 - Lifecycle Status
                                 - Line of Business
                                 - Operating System (OS)
                                 - OS version
        static_vars (dict): Dictionary of hardcoded variables
    """
    groups = {(tgt[3], tgt[2]) for tgt in list_oem_targets}
    ansible_dict = {}
    for grp in groups:
        grp_name = define_group_name(grp)
        try:
            static_vars_grp = static_vars[grp_name]
        except KeyError:
            static_vars_grp = {}
        ansible_dict[grp_name] = {"hosts":
                                  [tgt[0]
                                   for tgt in list_oem_targets
                                   if (tgt[3] == grp[0] and tgt[2] == grp[1])],
                                  "vars": static_vars_grp}

    return ansible_dict


def define_group_name(group_tuple):
    """Generates a group name based on a tuple containing the lifecycle status
       and the line of business.

    Args:
        group_tuple (tuple): a tuple containing (lifecycle status, line of
                                                 business)

    Returns:
        string: a string for the group name
    """
    # grp_name = (grp[0] + "_" + grp[1])
    if group_tuple[0] and group_tuple[1]:
        grp_name = group_tuple[0] + "_" + group_tuple[1]
    elif group_tuple[0] and group_tuple[1] is None:
        grp_name = group_tuple[0]
    elif group_tuple[0] is None and group_tuple[1]:
        grp_name = group_tuple[1]
    else:
        grp_name = "ungrouped"

    return grp_name


def read_cli_args():
    """ Reads the command-line arguments

    Ansible inventory requires that the script responds to two arguments:
    --host
    --list

    Returns:
        namespace - populated namespace of arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--host", action="store")
    return parser.parse_args()


def print_dictionary(dict_name):
    """Prints the JSON dictionary in a formatted way.

    Args:
        dict_name (dictionary) - the dictionary to be printed
    """
    print(json.dumps(dict_name, indent=_JSON_INDENT_SPACES, sort_keys=True))


def main(argv=None):
    """Script's entry point."""
    if argv is None:
        argv = sys.argv

    try:
        with open(os.path.join(sys.path[0], _STATIC_VARS_FILE), encoding="utf-8") as st_vars_file:
            static_vars = json.load(st_vars_file)
    except OSError as excep:
        print("Error reading static vars file: " + excep, file=sys.stderr)
        return _ERR_RET_CODE
    except json.JSONDecodeError as excep:
        print("Error decoding static vars file: " + excep, file=sys.stderr)
        return _ERR_RET_CODE

    config = configparser.ConfigParser()
    try:
        config.read(os.path.join(sys.path[0], _CONFIG_FILE))
    except configparser.Error as excep:
        print("Error reading the configuration file: " + excep,
              file=sys.stderr)
        return _ERR_RET_CODE

    try:
        repo_conn = connect_oracle(
            config["OEM_REPOSITORY_CONNECTION"]["HOST_NAME"],
            config["OEM_REPOSITORY_CONNECTION"]["PORT"],
            config["OEM_REPOSITORY_CONNECTION"]["USERNAME"],
            config["OEM_REPOSITORY_CONNECTION"]["PASSWORD"],
            config["OEM_REPOSITORY_CONNECTION"]["SERVICE_NAME"])

        targets = retrieve_oem_targets(repo_conn)

        cli_args = read_cli_args()
        if cli_args.list:
            ansible_dict = build_dictionary(targets, static_vars)
            print_dictionary(ansible_dict)
        elif cli_args.host:
            # Not implemented as --list is returned with the _meta group.
            print_dictionary(_EMPTY_INVENTORY)
        else:
            print_dictionary(_EMPTY_INVENTORY)

        repo_conn.close()

        return _SUC_RET_CODE
    except cx_Oracle.DatabaseError as excep:
        print("Error connecting to OEM Repository: " + excep, file=sys.stderr)
        return _ERR_RET_CODE


if __name__ == "__main__":
    sys.exit(main())
