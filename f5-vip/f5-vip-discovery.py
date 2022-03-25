# =====================================
# description: F5 Failover OCI Discovery Script
# author: m.hermsdorfer@f5.com
# date: 18-Jan-2022
# version: 1.2
# Updated: 23-Mar-2022
# Updates:
# 1.0: Initial release.
# 1.1: m.hermsdorfer@f5.com - 23-Mar-2022: added example settings.json
# 1.2: m.hermsdorfer@f5.com - 25-Mar-2022: added ability to write out settings.json with -w argument.
# =====================================
import requests
import json
import os
import sys
import getopt
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
        try:
            response = requests.get(uri, headers=signer.METADATA_AUTH_HEADERS)
        except Exception as e:
            print('Script failed to get instance metadata, check routing to ensure request leaves primary instance VNIC & Security Groups are in-place: ' + str(e))
            sys.exit(1)
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

def main(writeSettingsFile, activeSettingsFile):
    example_settings_json = {}
    example_settings_json['topic_id']="null"
    example_settings_json['multiprocess']="off"
    example_settings_json['timeout_seconds']="30"
    example_settings_json['vnics']=[]
    my_instance_metadata = get_current_metadata("instance")
    my_instance_vnic_metadata = get_current_metadata("vnics")
    my_bigip_interfaces = get_bigip_interfaces()
    print("Hostname: " + my_instance_metadata["hostname"])
    print("Instance ID: " + my_instance_metadata["id"])
    print("VNIC Count: " + str(len(my_instance_vnic_metadata)))
    try:
        network_client = oci.core.VirtualNetworkClient(config={}, signer=signer)
    except Exception as e:
        print('Script failed to talk to OCI API, check routing to ensure request leaves primary instance VNIC & Security Groups are in-place: ' + str(e))
        sys.exit(1)
    for vnic in my_instance_vnic_metadata:
        vnic_id = vnic['vnicId']
        primaryIP = vnic['privateIp']
        try:
            vnicDetails = network_client.get_vnic(vnic_id).data
        except Exception as e:
            print('Script failed to talk to OCI API, check routing to ensure request leaves primary instance VNIC & Security Groups are in-place: ' + str(e))
            sys.exit(1)
        vnic_name = vnicDetails.display_name
        try:
            private_ips = network_client.list_private_ips(vnic_id=vnic_id).data
        except Exception as e:
            print('Script failed to talk to OCI API, check routing to ensure request leaves primary instance VNIC & Security Groups are in-place: ' + str(e))
            sys.exit(1)
        print("\n    VNIC: " + vnic['vnicId'])
        print("        MAC Addr: " + vnic['macAddr'])
        print("        VNIC Name: " + vnic_name)
        example_config_vnics = {}
        example_config_vnics['ip_to_move'] = []
        example_config_vnics['move_to_vnic'] = vnic['vnicId']
        add_example_config = False
        for interface in my_bigip_interfaces:
            if interface['macAddress'].lower() == vnic['macAddr'].lower():
                print("        BIG-IP Interface: " + interface['name'])
                if interface['name'] != "mgmt":
                    example_config_vnics['vnic_name'] = vnic_name
                    example_config_vnics['bigip_name'] = interface['name']
        for privateIP in private_ips:
            if privateIP.is_primary:
                print("        Primary Private IP: " + privateIP.ip_address )
                print("            ocid: " + privateIP.id )
            else:
                print("        Additional Secondary Private IP: " + privateIP.ip_address )
                print("            ocid: " + privateIP.id )
                add_example_config = True
                example_config_vnics['ip_to_move'].append(privateIP.id)
        if add_example_config == True:
            example_settings_json['vnics'].append(example_config_vnics)
    print("\nExample settings.json config:")
    print(json.dumps(example_settings_json,indent=4,sort_keys=True))
    if writeSettingsFile:
        settings_file_name = os.path.dirname(os.path.realpath(sys.argv[0])) + '/settings.json'
        os.rename(settings_file_name, settings_file_name+'.bak')
        settings_file = open(settings_file_name, 'w')
        settings_file.write(json.dumps(example_settings_json,indent=4,sort_keys=True))
        settings_file.close()
        print("Wrote settings to file: " + settings_file_name + " backup created with .bak extension.")
    sys.exit(0)

# Get Instance Principal Token
try:
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
except Exception as e:
    print('Script failed to get OCI instance principal "signer" token with this error, check routing to ensure request leaves primary instance VNIC: ' + str(e))
    sys.exit(1)

# Call Main
if __name__ == '__main__':
    writeSettingsFile = False
    activeSettingsFile = ""
    try:
        opts, args = getopt.getopt(sys.argv[1:],"hwa:",["writeSettings","activeSettingsFile"])
    except getopt.GetoptError:
        print('f5-vip-discovery.py')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('f5-vip-discovery.py: A tool to discover OCIDs for BIG-IP VNICs and Secondary IPs to aid in configuration of the BIG-IP failover script.')
            print('To run discovery but not write settings file:')
            print('\t f5-vip-discovery.py')
            print('To run discovery but AND write discovered config to settings file:')
            print('\t f5-vip-discovery.py -w')
            print('To run discovery using secondary IPs from the Active device\'s settings file:')
            print('\t f5-vip-discovery.py -a <active-bigip-settings.json>')
            sys.exit()
        elif opt in ("-w", "--writeSettings"):
            writeSettingsFile = True
        elif opt in ("-a", "--activeSettingsFile"):
            activeSettingsFile = arg
    main(writeSettingsFile, activeSettingsFile)