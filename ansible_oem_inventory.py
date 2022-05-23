#!/usr/bin/python3

"""Ansible OEM Inventory

Author: Lucas Pimentel Lellis
Description: A python script to create an Ansible dynamic inventory
             based on Oracle Enterprise Manager repository.
             Validated against OEM 13.4.

Requires: cx_Oracle

Version: $Id$
"""

import argparse
import configparser
import json
import os
import sys

import cx_Oracle

_CONFIG_FILE = "config.ini"

_JSON_INDENT_SPACES = 4
_ERR_RET_CODE = 1
_SUC_RET_CODE = 0
_EMPTY_INVENTORY = {"_meta": {"hostvars": {}}}

_PROPERTY_TUPLE_START_POS = 2
_PROPERTY_TUPLE_LAST_POS = 6


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
    conn = cx_Oracle.Connection(
        user=username,
        password=password,
        dsn=dsn_fmt.format(host_name, port, service_name),
    )

    return conn


def retrieve_oem_targets(repo_connection, repo_name):
    """Retrieves a list of OEM host targets

    Each list item is a tuple of:
    - Host name
    - IP Address
    - Lifecycle Status
    - Line of Business
    - Operating System family
    - Operating System version
    - Repository Name

    Args:
        repo_connection (cx_Oracle.Connection): a connection to OEM repository

    Returns:
        list - list of tuples of OEM targets
    """
    query_txt = """
        select
            lower(tgt.target_name) target_name,
            lower(ipadr.property_value) ip_address,
            regexp_replace(
                regexp_replace(
                    lower(lfcl.property_value), '[^0-9a-z_]+', '_'),
                    '^([0-9])', :lfcl_ld_num
                ) lifecycle_status,
            regexp_replace(regexp_replace(lower(lnbus.property_value),
                '[^0-9a-z_]+', '_'), '^([0-9])',
                :lnbus_ld_num) line_of_business,
            regexp_replace(regexp_replace(lower(tgt.type_qualifier1),
                '[^0-9a-z_]+', '_'), '^([0-9])', :os_ld_num) operating_system,
            regexp_replace(regexp_replace(lower(tgt.type_qualifier2),
                '[^0-9a-z_]+', '_'), '^([0-9])', :os_ver_ld_num) os_version,
            regexp_replace(regexp_replace(lower(:repo_name_bind),
                '[^0-9a-z_]+', '_'), '^([0-9])', :repo_name_backref)
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
    # The backreference is escaped as a bind variable due to a limitation
    # on how \1 is escaped directly on a query text
    query_cursor.execute(
        query_txt,
        lfcl_ld_num="_\\1",
        lnbus_ld_num="_\\1",
        os_ld_num="_\\1",
        os_ver_ld_num="_\\1",
        repo_name_bind=repo_name,
        repo_name_backref="_\\1",
    )

    results = query_cursor.fetchall()

    query_cursor.close()

    return results


def build_dictionary(list_oem_targets):
    """Builds the dictionary for ansible

    Args:
        list_oem_targets (list): list of OEM targets containing a
                                 tuple of
                                 - Host name
                                 - IP Address
                                 - Lifecycle Status
                                 - Line of Business
                                 - Operating System (OS)
                                 - OS version
                                 - Repository Name

    Returns:
        dictionary - a dictionary of targets and groups for Ansible
    """

    ansible_dict = {}

    build_meta_group(list_oem_targets, ansible_dict)
    for property_pos in range(
        _PROPERTY_TUPLE_START_POS, _PROPERTY_TUPLE_LAST_POS
    ):
        build_property_groups(list_oem_targets, ansible_dict, property_pos)

    return ansible_dict


def build_meta_group(list_oem_targets, ansible_dict):
    """Builds the _meta group.

    Args:
        list_oem_targets (list): list of OEM targets containing a
                                 tuple of
                                 - Host name
                                 - IP Address
                                 - Lifecycle Status
                                 - Line of Business
                                 - Operating System (OS)
                                 - OS version
                                 - Repository Name
        ansible_dict (dictionary): the ansible dictionary under construction
    """

    hostvars = {}
    for tgt in list_oem_targets:
        host_vars_item = {}
        host_vars_item["ansible_host"] = tgt[1]
        hostvars[tgt[0]] = host_vars_item

    ansible_dict["_meta"] = {"hostvars": hostvars}


def build_property_groups(list_oem_targets, ansible_dict, property_tuple_pos):
    """Builds groups based on Line of Business.

    Args:
        list_oem_targets (list): list of OEM targets containing a
                                 tuple of
                                 - Host name
                                 - IP Address
                                 - Lifecycle Status
                                 - Line of Business
                                 - Operating System (OS)
                                 - OS version
                                 - Repository Name
        ansible_dict (dictionary): the ansible dictionary under construction
        property_tuple_pos: the property position on the list of targets tuple
    """
    property_set = {tgt[property_tuple_pos] for tgt in list_oem_targets}
    for property_name in property_set:
        ansible_dict[property_name] = {
            "hosts": [
                tgt[0]
                for tgt in list_oem_targets
                if tgt[property_tuple_pos] == property_name
            ]
        }


def build_repo_name_groups(list_oem_targets, ansible_dict):
    """Builds groups based on repository name.
       Returns the initial dictionary.

    Args:
        list_oem_targets (list): list of OEM targets containing a
                                 tuple of
                                 - Host name
                                 - IP Address
                                 - Lifecycle Status
                                 - Line of Business
                                 - Operating System (OS)
                                 - OS version
                                 - Repository Name
    """
    groups = {tgt[6] for tgt in list_oem_targets}
    for grp in groups:
        ansible_dict[grp] = {
            "hosts": [tgt[0] for tgt in list_oem_targets if tgt[6] == grp]
        }


def read_cli_args():
    """Reads the command-line arguments

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

    config = configparser.ConfigParser()
    try:
        config.read(os.path.join(sys.path[0], _CONFIG_FILE))
    except configparser.Error as excep:
        print(
            "Error reading the configuration file: " + str(excep),
            file=sys.stderr,
        )
        return _ERR_RET_CODE

    try:
        targets = []
        for repo_name in config.sections():
            repo_conn = connect_oracle(
                config[repo_name]["HOST_NAME"],
                config[repo_name]["PORT"],
                config[repo_name]["USERNAME"],
                config[repo_name]["PASSWORD"],
                config[repo_name]["SERVICE_NAME"],
            )
            targets_repo = retrieve_oem_targets(repo_conn, repo_name)
            targets = targets + targets_repo

        cli_args = read_cli_args()
        if cli_args.list:
            ansible_dict = build_dictionary(targets)
            print_dictionary(ansible_dict)
        elif cli_args.host:
            # Not implemented as --list is returned with the _meta group.
            print_dictionary(_EMPTY_INVENTORY)
        else:
            print_dictionary(_EMPTY_INVENTORY)

        repo_conn.close()

        return _SUC_RET_CODE
    except cx_Oracle.DatabaseError as excep:
        print(
            "Error connecting to OEM Repository: " + str(excep),
            file=sys.stderr,
        )
        return _ERR_RET_CODE


if __name__ == "__main__":
    sys.exit(main())
