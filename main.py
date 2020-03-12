#!/usr/bin/python3

import requests
import json
import argparse
import os

def print_json(obj):
    """Parse JSON objects"""
    print(json.dumps(obj, sort_keys=True, indent=4))

# vm management
def get_vms():
    """Returns a list of VM IDs and paths for all VMs"""
    return requests.get(api_url + '/vms', headers=headers).json()


def get_vm_by_name(name):
    """Returns the VM setting information of a VM"""
    for vm in get_vms():
        if os.path.split(vm['path'])[1].split('.')[0] == name:
            r = requests.get(api_url + '/vms/' + vm['id'], headers=headers).json()
            r['name'] = name
            return r


def get_vm_by_id(id):
    """Returns the VM setting information of a VM"""
    r = requests.get(api_url + '/vms/' + id, headers=headers).json()

    # populate name
    for vm in get_vms():
        if vm['id'] == id:
            r['name'] = os.path.split(vm['path'])[1].split('.')[0]
    
    return r


def update_vm(name, processors=None, memory=None):
    """Updates the VM settings"""

    vm = get_vm_by_name(name)

    # Get current values to avoid empty parameters
    if processors is None or memory is None:
        if processors is None:
            print("[DEBUG] Inheriting processor spec")
            processors = int(vm['cpu']['processors'])
        if memory is None:
            print("[DEBUG] Inheriting memory spec")
            memory = int(vm['memory'])

    payload = {
        "processors": int(processors),
        "memory": int(memory)
    }

    return requests.put(url=api_url + '/vms/' + vm['id'], headers=headers, json=payload).json()


def create_vm(parent_name, name, processors, memory, vmnet):
    """Creates a copy of the VM"""

    parent_vm = get_vm_by_name(parent_name)

    print("[DEBUG] Arguments: %s, %s, %s, %s" % (str(parent_name), str(name), str(processors), str(memory)))

    # Set default values
    if processors is None or memory is None:
        if processors is None:
            print("[DEBUG] Inheriting processor spec")
            processors = int(parent_vm['cpu']['processors'])
        if memory is None:
            print("[DEBUG] Inheriting memory spec")
            memory = int(parent_vm['memory'])

    payload = {
        "cpu": {
            "processors": int(processors)
        },
        "memory": int(memory),
        "name": str(name),
        "parentId": str(parent_vm['id'])
    }

    r = requests.post(url=api_url + '/vms', headers=headers, json=payload).json()

    # BUG: cannot manipulate processor count on cloning. must update after
    if parent_vm['cpu']['processors'] is not processors:
        r = update_vm(name, processors, memory)

    return r


def delete_vm(name):
    """Deletes a VM"""
    r = requests.delete(api_url + '/vms/' + get_vm_by_name(name)['id'], headers=headers)
    if r.status_code == 204:
        print("[INFO] Deleted VM %s" % name)
    return None


# vm power management
def get_power(name):
    """Returns power state of VM"""
    return requests.get(api_url + '/vms/' + get_vm_by_name(name)['id'] + '/power', headers=headers).json()


def power_vm(name, state):
    """Power on or off a VM"""
    r = requests.put(api_url + '/vms/' + get_vm_by_name(name)['id'] + '/power', headers=headers, data=state)
    if r.status_code == 200:
        print("[INFO] Powered %s %s" % (state, name))
    return None


# vm network adapters management
def get_ip(name):
    """Returns current IP of (assuming) first NIC"""
    return requests.get(api_url + '/vms/' + get_vm_by_name(name)['id'] + '/ip', headers=headers).json()


def get_nics(name):
    """Returns list of NICs for the VM"""
    return requests.get(api_url + '/vms/' + get_vm_by_name(name)['id'] + '/nic', headers=headers).json()


def get_nic(name, index):
    """List specs of specific NIC of VM"""
    for nic in get_nics(name)['nics']:
        print("[DEBUG] Current Index: %s, Expected Index: %s" % (str(nic['index']), str(index)))
        if nic['index'] == index:
            return nic


def update_nic(name, index, type):
    """Updates a network adapter in the VM"""

    nic = get_nic(name, int(index))

    # Set default values
    if type is None:
        print("[DEBUG] Inheriting type key")
        type = nic['type']
    if mac_addr is None:
        print("[DEBUG] Inheriting mac_addr")
        mac_addr = nic['macAddress']

    payload = {
        "index": nic['index'],
        "type": type,
        "vmnet": vmnet,
        "macAddress": mac_addr
    }

    return requests.put(url=api_url + '/vms/' + get_vm_by_name(name)['id'] + '/nic/' + str(nic['index']), headers=headers, json=payload).json()


def create_nic(name, index, type):
    """Creates a network adapter in the VM"""

    # Set next index if not defined
    if index is None:
        index = 0
        for nic in get_nics(name)['nics']:
            if int(nic['index']) >= index:
                index = int(nic['index']) + 1

    payload = {
        "index": index,
        "type": type,
        "vmnet": vmnet,
        "macAddress": mac_addr
    }

    return requests.post(url=api_url + '/vms/' + get_vm_by_name(name)['id'] + '/nic', headers=headers, json=payload).json()


def delete_nic(name, index):
    """Deletes a VM network adapter"""
    r = requests.delete(api_url + '/vms/' + get_vm_by_name(name)['id'] + '/nic/' + str(index), headers=headers)
    if r.status_code == 204:
        print("[INFO] Deleted NIC %s on %s" % (index, name))
    return None


if __name__ == '__main__':

    # parse positional arguments
    parser = argparse.ArgumentParser(description="Wrapper script for VMware Fusion REST API")
    parser.add_argument("method", choices=['get','create','update','delete', 'power'], default='get', help="Execute API operation")
    parser.add_argument("resource", nargs='?', default='vm')

    # api options
    parser.add_argument("--api-key", type=str, help="Your VMware Fusion REST API key")

    # vm management options
    parser.add_argument("--name", type=str, help="Resource identifier")
    parser.add_argument("--parent-name", type=str, help="Target VM for cloning")
    parser.add_argument("--processors", type=int, help="Set vCPUs for VM")
    parser.add_argument("--memory", type=int, help="Set system memory for VM")

    # vm power management options
    parser.add_argument("--state", type=str, help="Set power state of VM")

    # vm net adapter options
    parser.add_argument("--index", type=int, help="Adapter identifier")
    parser.add_argument("--type", type=str, help="Set adapter type (hostonly, nat, bridged, etc.)")

    # finalize parsing
    args = parser.parse_args()

    # Check for API URL
    if os.getenv('VMWARE_FUSION_REST_API_URL') is not None:
        api_url = os.getenv('VMWARE_FUSION_REST_API_URL')
    else:
        api_url = 'http://127.0.0.1:8697/api'

    # Check/prompt for API key
    if os.getenv('VMWARE_FUSION_REST_API_KEY') is not None:
        api_key = os.getenv('VMWARE_FUSION_REST_API_KEY')
    else:
        if args.api_key is not None:
            api_key = args.api_key
        else:
            api_key = input("VMware Fusion REST API Key: ")

    # Boilerplate header
    headers = {
        "Content-Type": "application/vnd.vmware.vmw.rest-v1+json",
        "Accept": "application/vnd.vmware.vmw.rest-v1+json",
        "Authorization": "Basic " + api_key
    }

    # switchboard
    if args.method == 'get':
        if args.resource == 'vm':
            if args.name is None:
                print("[INFO] List all VMs")
                print_json(get_vms())
            else:
                print("[INFO] Get VM (Name: %s)" % str(args.name))
                print_json(get_vm_by_name(args.name))
        elif args.resource == 'ip':
            print("[INFO] Get VM IP")
            print_json(get_ip(args.name))
        elif args.resource == 'nics':
            print("[INFO] Get network adapters for VM")
            print_json(get_nics(args.name))
    elif args.method == 'update':
        if args.resource == 'vm':
            print("[INFO] Update VM (Name: %s)" % str(args.name))
            print_json(update_vm(args.name, args.processors, args.memory))
        elif args.resource == 'nic':
            print("[INFO] Update NIC (VM: %s, Index %s)" % (str(args.name), str(args.index)))
            print_json(update_nic(args.name, args.index, args.type))
    elif args.method == 'create':
        if args.resource == 'vm':
            print("[INFO] Create VM (Name: %s)" % str(args.name))
            print_json(create_vm(args.parent_name, args.name, args.processors, args.memory, args.vmnet))
        elif args.resource == 'nic':
            print("[INFO] Create NIC (Name: %s)" % str(args.name))
            print_json(create_nic(args.name, args.index, args.type))
    elif args.method == 'delete':
        if args.resource == 'vm':
            print("[INFO] Delete VM (Name: %s)" % str(args.name))
            delete_vm(args.name)
        elif args.resource == 'nic':
            print("[INFO] Delete NIC (VM: %s, Index: %s)" % (str(args.name), str(args.index)))
            delete_nic(args.name, args.index)
    elif args.method == 'power':
        if args.resource == 'on' or args.resource == 'off':
            print("[DEBUG] power_vm(%s, %s)" % (str(args.name), str(args.resource)))
            power_vm(args.name, args.resource)
        elif args.resource == 'state':
            if args.name is not None:
                if args.state == None:
                    print("[DEBUG] get_power(%s)" % str(args.name))
                    print_json(get_power(args.name))
                else:
                    print("[DEBUG] power_vm(%s, %s)" % (str(args.name), str(args.state)))
                    print_json(power_vm(args.name, args.state))
            else:
                for vm in get_vms():
                    print("[DEBUG] get_power(get_vm_by_id(%s))" % str(vm['id']))
                    print_json(get_power(get_vm_by_id(vm['id'])['name']))
