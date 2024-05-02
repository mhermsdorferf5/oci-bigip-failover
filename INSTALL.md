# OCI Failover Script Install instructions.

Note, this is for OCI failover with Instance Principals, for standard OCI failover please use the scripts located here: https://github.com/f5devcentral/f5-oci-failover

## TLDR Summary
Here's the short list of commands to run, if you don't particularly care for an explication around what they do:
```
tmsh modify /sys db config.allow.rfc3927  { value enable }
tmsh create /sys management-route oci-169.254.0.0_16 { network 169.254.0.0/16 gateway <management-gateway-ip> }
tmsh modify /sys db failover.selinuxallowscripts value enable
tmsh modify /sys db failover.nettimeoutsec value 60
tmsh save /sys config
cd /config/failover/
curl -L -o oci-f5-failover_v1.6.tar.gz https://github.com/mhermsdorferf5/oci-bigip-failover/raw/main/release-artifacts/oci-f5-failover_v1.6.tar.gz
tar -xzf oci-f5-failover_v1.6.tar.gz
restorecon -vr /config/failover
chmod 755 /config/failover/tgactive /config/failover/tgrefresh /config/failover/tgstandby
reboot
cd /config/failover/f5-vip/
./run-discovery.sh -w
scp settings.json <standby-bigip>:/config/failover/f5-vip/settings.active.json
```

On the Standby device:
```
tmsh modify sys db config.allow.rfc3927  { value enable }
tmsh create sys management-route oci-169.254.0.0_16 { network 169.254.0.0/16 gateway <management-gateway-ip> }
tmsh modify sys db failover.selinuxallowscripts value enable
tmsh modify /sys db failover.nettimeoutsec value 60
tmsh save sys config
cd /config/failover/
curl -L -o oci-f5-failover_v1.6.tar.gz https://github.com/mhermsdorferf5/oci-bigip-failover/raw/main/release-artifacts/oci-f5-failover_v1.6.tar.gz
tar -xzf oci-f5-failover_v1.6.tar.gz
restorecon -vr /config/failover
chmod 755 /config/failover/tgactive /config/failover/tgrefresh /config/failover/tgstandby
reboot
cd /config/failover/f5-vip/
./run-discovery.sh -a settings.active.json -w
```

## Full Install Instructions

### Configure Management Routing for BIG-IP to talk to OCI API over Management:
* OCI API endpoints live on rfc3927 link-local IP addresses.
* By default BIG-IP does not allow for the configuration of routes for rfc3927 addresses.
* To create the appropriate management routes, we must modify a sys db flag 'config.allow.rfc3927' to enable.
    * see: https://support.f5.com/csp/article/K11650

```
tmsh modify sys db config.allow.rfc3927  { value enable }
tmsh create sys management-route oci-169.254.0.0_16 { network 169.254.0.0/16 gateway <management-gateway-ip> }
tmsh save sys config
```

### Enable failover script execution upon failover:
* starting in v14.x BIG-IP does not execute failover scripts to move public cloud IPs over automatically.
* A sys db flag 'failover.selinuxallowscripts' needs to be enabled. 
* See: https://support.f5.com/csp/article/K71557891
    * Note this article applies to OCI as well
```
tmsh modify sys db failover.selinuxallowscripts value enable
tmsh save sys config
reboot
```

### Modify network failover timeout to 60 seconds:
* OCI network maintenance will discard traffic between OCI Availability Domains.
* OCI hasn't publicly said what their SLA is for this, however we've seen outages as long as 30 seconds, and our informal understanding is they can last as long as 60 seconds.
* This does delay failover in the case of a real outage, but it prevents a split brain active-active situation from happening every time OCI network maintenance drops traffic between availability domains.
* See: https://my.f5.com/manage/s/article/K7249
```
tmsh modify /sys db failover.nettimeoutsec value 60
tmsh save sys config
reboot
```

### Failover Script Install:
Download the tarball that contains the venv & failover scripts to the BIG-IP, then extract the tarball and restore selinux permissions on the failover files.
```
cd /config/failover/
curl -L -o oci-f5-failover_v1.6.tar.gz https://github.com/mhermsdorferf5/oci-bigip-failover/raw/main/release-artifacts/oci-f5-failover_v1.6.tar.gz
tar -xzf oci-f5-failover_v1.6.tar.gz
restorecon -vr /config/failover
chmod 755 /config/failover/tgactive /config/failover/tgrefresh /config/failover/tgstandby
vi /config/failover/f5-vip/settings.json
```


### Configure failover settings file, see example below:
* topic_id: This can either be "null" in which case no messages will be sent, or it can be the OCID for a Topic created in the notification section of OCI.  Useful for having other OCI consumer applications learn when failover happens.
* multiprocess: on/off, multiprocess on enables faster failover by having multiple processes execute teh API calls in parallel.
* timeout_seconds: Timeout in seconds for how long allow retry attempts if the first attempt to move the IP failed.
* vnics: An array of one or more vnics to failover IPs on.
    * name: simple identifier to make reading the config easier, not used for anything.
    * move_to_vnic: This should be the OCID of the local VNIC on which floating IP addresses live.
    * ip_to_move: An array of one or more private IPs that float between the BIG-IPs and need to be moved upon failover.
* See Discovery Script section below for a helpful script to aid in the generation of this json config file.

Example:
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
```
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