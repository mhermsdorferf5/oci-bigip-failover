# =====================================
# description: F5 Failover OCI Discovery Script
# author: m.hermsdorfer@f5.com
# date: 18-Jan-2022
# version: 1.0
# Updated: 18-Jan-2022
# Updates:
# 1.0: Initial release.
# 1.1: m.hermsdorfer@f5.com - 23-Mar-2022 added example settings.json
# =====================================
from pickle import FALSE, TRUE
import requests
import json
import os
import signal
import sys
import time
import oci

def get_current_metadata(type):
    if type == "instance":
        uri = "http://169.254.169.254/opc/v2/instance/"
    elif type == "vnics":
        uri = "http://169.254.169.254/opc/v2/vnics/"
    else:
        print('must specify type when calling get_current_metadata type can be instance or vnics')
        sys.exit(1)

    call_attempts = 0
    while call_attempts < 2:
        response = requests.get(uri, headers=signer.METADATA_AUTH_HEADERS)
        if response.ok:
            json_object = json.loads(response.content)
            json_text = json.dumps(json_object)
            return json_object
        else:
            call_attempts += 1
            if response.status_code == 401 and call_attempts < 2:
                signer.refresh_security_token()
            else:
                response.raise_for_status()

def get_bigip_interfaces():
    uri = "http://127.0.0.1/mgmt/tm/net/interface/"

    call_attempts = 0
    while call_attempts < 2:
        response = requests.get(uri, auth=('admin', 'admin'))
        if response.ok:
            json_object = json.loads(response.content)
            json_text = json.dumps(json_object)
            interfaces = json_object['items']
            return interfaces
        else:
            response.raise_for_status()

def main():
    my_example_settings_json = {}
    my_example_settings_json['topic_id']="null"
    my_example_settings_json['multiprocess']="off"
    my_example_settings_json['timeout_seconds']="30"
    my_example_settings_json['vnics']=[]
    my_instance_metadata = get_current_metadata("instance")
    my_instance_vnic_metadata = get_current_metadata("vnics")
    my_bigip_interfaces = get_bigip_interfaces()
    print("Hostname: " + my_instance_metadata["hostname"])
    print("Instance ID: " + my_instance_metadata["id"])
    print("VNIC Count: " + str(len(my_instance_vnic_metadata)))
    network_client = oci.core.VirtualNetworkClient(config={}, signer=signer)
    for vnic in my_instance_vnic_metadata:
        vnic_id = vnic['vnicId']
        primaryIP = vnic['privateIp']
        vnicDetails = network_client.get_vnic(vnic_id).data
        subnet_id = vnicDetails.subnet_id
        subnetDetails = network_client.get_subnet(subnet_id).data
        subnet_name = subnetDetails.display_name
        private_ips = network_client.list_private_ips(vnic_id=vnic_id).data
        print("\n    VNIC: " + vnic['vnicId'])
        print("        MAC Addr: " + vnic['macAddr'])
        print("        Subnet Name: " + subnet_name)
        my_example_config_vnics = {}
        my_example_config_vnics['ip_to_move'] = []
        my_example_config_vnics['move_to_vnic'] = vnic['vnicId']
        add_example_config = FALSE
        for interface in my_bigip_interfaces:
            if interface['macAddress'].lower() == vnic['macAddr'].lower():
                print("        BIG-IP Interface: " + interface['name'])
                if interface['name'] != "mgmt":
                    my_example_config_vnics['name'] = subnet_name
        for privateIP in private_ips:
            if privateIP.is_primary:
                print("        Primary Private IP: " + privateIP.ip_address )
                print("            ocid: " + privateIP.id )
            else:
                print("        Additional Secondary Private IP: " + privateIP.ip_address )
                print("            ocid: " + privateIP.id )
                if my_example_config_vnics['name']:
                    add_example_config = TRUE
                    my_example_config_vnics['ip_to_move'].append(privateIP.id)
        if add_example_config == TRUE:
            my_example_settings_json['vnics'].append(my_example_config_vnics)
    print("\nExample settings.json config:")
    print(json.dumps(my_example_settings_json,indent=4,sort_keys=True))
    sys.exit(0)

# Get Instance Principal Token
try:
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
except Exception as e:
    print('Script failed to get OCI instance principal "signer" token with this error, check routing to ensure request leaves primary instance VNIC: ' + str(e))
    sys.exit(1)

# Call Main
if __name__ == '__main__':
    main()