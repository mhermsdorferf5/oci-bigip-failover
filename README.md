# OCI Failover Setup

Note, this is for OCI failover with Instance Principals, for standard OCI failover please use the scripts located here: https://github.com/f5devcentral/f5-oci-failover

## Instance Principal setup:
* These failover scripts run on the BIG-IP instances running in the OCI environment.  They use OCI “Instance Principal” credentials to interact with the OCI API and perform the failover calls to move OCI IP addresses.  By default, instance principal accounts have no authorization, they’re granted authorization to the OCI API by the creation of IAM Dynamic Groups & Matching Rules which apply IAM Policies that grant access.
* You'll need to create IAM Dynamic Groups & Matching rules that match the OCI instances and assign a IAM Policy to them.
* The IAM Policy will define what permissions the OCI has for it's interactions with the OCI API.
* Minimum set of required permissions for instance principal IAM Policy:
    * inspect vnics
    * inspect vnic-attachments
    * inspect private-ips
    * use private-ips
    * use ons-topics

## Configure Management Routing for BIG-IP to talk to OCI API over Management:
* OCI API endpoints live on rfc3927 link-local IP addresses.
* By default BIG-IP does not allow for the configuration of routes for rfc3927 addresses.
* To create the appropriate management routes, we must modify a sys db flag 'config.allow.rfc3927' to enable.
    * see: https://support.f5.com/csp/article/K11650

```
tmsh modify sys db config.allow.rfc3927  { value enable }
tmsh create sys management-route oci-169.254.0.0_16 { network 169.254.0.0/16 gateway <management-gateway-ip> }
tmsh save sys config
```


## Download OCI Failover scripts & Install:
* Legacy failover scripts & instructions:
    * Code: https://github.com/f5devcentral/f5-oci-failover
    * Instructions: https://clouddocs.f5.com/cloud/public/v1/oracle/oracle_deploy.html#oci-ha
    * Note: This does not use instance principals for authentication to OCI API.
    * Note: that selinux restorecon needs to be used to restore selinux permissions across the failover files.
* This script has been developed by Oracle for OCI BIG-IP failover using Instance Principals.
    * Updated script has since been modified by F5 to support additional functionality, such as multiple VNICs.
    * Updated script uses a rather large python environment with OCI libraries to interact with API using instance principal authentication.
    * Can be downloaded from here: https://github.com/mhermsdorferf5/oci-bigip-failover/raw/main/release-artifacts/oci-f5-failover_v1.4.tar.gz
* Note: The configuration will be unique per BIG-IP.

### Install Commands:
```
cd /config/failover/
curl -L -o oci-f5-failover_v1.4.tar.gz https://github.com/mhermsdorferf5/oci-bigip-failover/raw/main/release-artifacts/oci-f5-failover_v1.4.tar.gz
tar -xzf oci-f5-failover_v1.4.tar.gz
restorecon -vr /config/failover
chmod 755 /config/failover/tgactive /config/failover/tgrefresh /config/failover/tgstandby
vi /config/failover/f5-vip/settings.json
```


### Update the settings file with approprate configuration, see example below:
* topic_id: This can either be "null" in which case no messages will be sent, or it can be the OCID for a Topic created in the notification section of OCI.  Useful for having other OCI consumer applications learn when failover happens.
* multiprocess: on/off, multiprocess on enables faster failover by having multiple processes execute teh API calls in parallel.
* vnics: An array of one or more vnics to failover IPs on.
    * name: simple identifier to make reading the config easier, not used for anything.
    * move_to_vnic: This should be the OCID of the local VNIC on which floating IP addresses live.
    * ip_to_move: An array of one or more private IPs that float between the BIG-IPs and need to be moved upon failover.

```json
{
    "topic_id": "null",
    "multiprocess": "on",
    "timeout_seconds": "30",
    "vnics": [ 
        { 
            "name": "external",
            "move_to_vnic": "ocid1.vnic.oc1.phx.abyhqljrvp57t35fz6rlfcx2fqzbdlvqtvj755twrdhq2rkfvhecnbl5y7jq",
            "ip_to_move": [ 
                "ocid1.privateip.oc1.phx.aaaaaaaakvdcypwjn3fjiwt4obf2wawerv66rrn2wulsnmo2t34jkmdgt73a",
                "ocid1.privateip.oc1.phx.aaaaaaaaxrvo6pvew3wdko436jfbxymmddexxtevvpfhrgieczajpwe3qmnq",
                "ocid1.privateip.oc1.phx.aaaaaaaahger7g5rtteosh4sk7cn3qw2j756imnuneiqjlpvnirrgxf5lx5q"
            ]
        },
        { 
            "name": "internal",
            "move_to_vnic": "ocid1.vnic.oc1.phx.anyhqljrszvyosac7xutgnffxf5k3zlbf6x7vrmjkj4bmgct65mvjdrjiw2q",
            "ip_to_move": [
                "ocid1.privateip.oc1.phx.aaaaaaaac7gjtdk3z2izlevodfz745dsnpouzb5vusmxzilkzv2f4gwbobua"
            ]
        },
        { 
            "name": "foo",
            "move_to_vnic": "ocid1.vnic.oc1.phx.abuw4ljrlsfiqw6vzzxb43vyypt4pkodawglp3wqxjqofakrwvou52gb6s5a",
            "ip_to_move": [ 
                "ocid1.privateip.oc1.phx.aaaaaaaaba3pv6wkcr4jqae5f44n2b2m2yt2j6rx32uzr4h25vqstifsfdsq"
            ]
        }
  ]
}
```


## Enable failover script execution upon failover:
* starting in v14.x BIG-IP does not execute failover scripts to move public cloud IPs over automatically.
* A sys db flag 'failover.selinuxallowscripts' needs to be enabled. 
* See: https://support.f5.com/csp/article/K71557891
    * Note this article applies to OCI as well
```
tmsh modify sys db failover.selinuxallowscripts value enable
tmsh save sys config
reboot
```

## Discovery Script to aid settings.json file creation:
* f5-vip-discovery.py is a helper script that uses the OCI API to discover all the OCIDs for vnic, and private ip objects.
* The script also attempts to build a settings.json file that is appropriate.
    * If the automatically generated settings.json is not ideal, you can still use the script to get all the required OCIDs you need to create your own settings.json
* Script is also useful for matching up BIG-IP interfaces to OCI VNICs/Subnets.
```
cd /config/failover/f5-vip/
./run-discovery.sh
```

Example output:
```json
[root@hermsdorfer-iperf-bigip-1:Active:Changes Pending] f5-vip # ./run-discovery.sh
Hostname: hermsdorfer-iperf-bigip-1
Instance ID: ocid1.instance.oc1.phx.anyhqljrszvyosac3xo5e5dmvev3thpaxrl3v2xybivj27c6a7rzpok6j76q
VNIC Count: 3

    VNIC: ocid1.vnic.oc1.phx.abyhqljrzgwvrp2gykk2wruexmsk6cy5exhdqilv4imqgwx5ryr7e6m2opta
        MAC Addr: 02:00:17:09:D0:0B
        Subnet Name: Public Subnet2-hermsdorfer_vcn
        BIG-IP Interface: mgmt
        Primary Private IP: 10.12.3.222
            ocid: ocid1.privateip.oc1.phx.abyhqljrpu6zerwesrevlnoezyo6n33gcqj73ueb52dw24rttbg6xctvugyq

    VNIC: ocid1.vnic.oc1.phx.abyhqljrz7ilcb6hyxzftuewafrtbofbg46xsubgcc273f4nbrjmhsbimk4a
        MAC Addr: 02:00:17:08:6A:31
        Subnet Name: Public Subnet-hermsdorfer_vcn
        BIG-IP Interface: 1.1
        Additional Secondary Private IP: 10.12.0.32
            ocid: ocid1.privateip.oc1.phx.aaaaaaaaxrvo6pvew3wdko436jfbxymmddexxtevvpfhrgieczajpwe3qmnq
        Additional Secondary Private IP: 10.12.0.219
            ocid: ocid1.privateip.oc1.phx.aaaaaaaac7gjtdk3z2izlevodfz745dsnpouzb5vusmxzilkzv2f4gwbobua
        Primary Private IP: 10.12.0.23
            ocid: ocid1.privateip.oc1.phx.abyhqljrktukxotxynsrl5olfosht4iqxvu7ongn4w47a3klw3ax4pag4ppa

    VNIC: ocid1.vnic.oc1.phx.abyhqljrejjsdhehi2gwyfjt5eh6amdrctzsb22fuf6z7xcycpcsn22z7caa
        MAC Addr: 02:00:17:08:3D:8F
        Subnet Name: Private Subnet-hermsdorfer_vcn
        BIG-IP Interface: 1.2
        Primary Private IP: 10.12.1.182
            ocid: ocid1.privateip.oc1.phx.abyhqljrmiasjluoqltzjtbyae3frslejivetfwyhwubd47z7tf3gnpgbeuq

Example settings.json config:
{
    "multiprocess": "off",
    "timeout_seconds": "30",
    "topic_id": "null",
    "vnics": [
        {
            "ip_to_move": [
                "ocid1.privateip.oc1.phx.aaaaaaaaxrvo6pvew3wdko436jfbxymmddexxtevvpfhrgieczajpwe3qmnq",
                "ocid1.privateip.oc1.phx.aaaaaaaac7gjtdk3z2izlevodfz745dsnpouzb5vusmxzilkzv2f4gwbobua"
            ],
            "move_to_vnic": "ocid1.vnic.oc1.phx.abyhqljrz7ilcb6hyxzftuewafrtbofbg46xsubgcc273f4nbrjmhsbimk4a",
            "name": "Public Subnet-hermsdorfer_vcn"
        }
    ]
}
```

## Troubleshooting:
* Instance Principal authentication only works if the API call is coming from the primary vnic of the instance.
    * If you see errors such as the following:
        * Script failed at "signer" with this error: ...
    * This is an indication that your routing to 169.254.0.0/16 is not setup correctly.
    * Most likely routing is going out a TMM VNIC, due to the TMM default route, management route needs to be added.
* Errors such as the following indicate that the instance principal doesn't have permissions to modify vnics/self-ips.
    * Script failed at "assign_to_different_vnic" with this error: {'status': 404, 'message': u'Authorization failed or requested resource not found.', 'code': u'NotAuthorizedOrNotFound', 'opc-request-id': '0F4DCDB137714583AD6D2214F75AFB4F/D29A1B68D3F3DF4A3D884E91ACFE44BF/9B259C0A6CA87BBD5247E2E51340FB9A'}
    * oci.exceptions.ServiceError: {'status': 404, 'message': u'Authorization failed or requested resource not found.', 'code': u'NotAuthorizedOrNotFound', 'opc-request-id': '4AF285F8804F42A4A14D0E434C5F4DB8/26B840642196953615D11373AE6A7F48/078EB5CB32C6BE5740D027F171E0BF90'}
* Log files are: /config/failover/f5-vip/error.log
    * Note both errors and success messages are written to error.log
    * Upon failover, you should see log messages in that log for ever moved IP.
* You can manually execute teh failover scripts by calling:
    * /config/failover/tgactive or /config/failover/tgrefresh
    * These scripts get called by SOD (the big-ip failover daemon):
        * /usr/lib/failover/f5tgrefresh in turn calls => /config/failover/tgrefresh
        * /usr/lib/failover/f5active in turn calls => /config/failover/tgactive


## Python Environment
This tool uses python to interact with the OCI API and perform failover.  To that end, it needs it's own python environment with OCI libraries, etc.  The python venv build process is documented here: [python-venv.md](python-venv.md)