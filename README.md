# OCI BIG-IP Failover Setup

Note, this is for OCI failover with Instance Principals, for standard OCI failover please use the scripts located here: https://github.com/f5devcentral/f5-oci-failover

* This script has been developed by Oracle for OCI BIG-IP failover using Instance Principals.
    * Updated script has since been modified by F5 to support additional functionality, such as multiple VNICs.
    * Updated script uses a rather large python environment with OCI libraries to interact with API using instance principal authentication.
    * You can find [detailed install instructions here](INSTALL.md).
    * Can be downloaded from here: https://github.com/mhermsdorferf5/oci-bigip-failover/raw/main/release-artifacts/oci-f5-failover_v1.4.tar.gz
* Standard OCI failover scripts & instructions:
    * Code: https://github.com/f5devcentral/f5-oci-failover
    * Instructions: https://clouddocs.f5.com/cloud/public/v1/oracle/oracle_deploy.html#oci-ha
    * Note: This does not use instance principals for authentication to OCI API.

## OCI Instance Principal setup:
* These failover scripts run on the BIG-IP instances running in the OCI environment.  They use OCI “Instance Principal” credentials to interact with the OCI API and perform the failover calls to move OCI IP addresses.  By default, instance principal accounts have no authorization, they’re granted authorization to the OCI API by the creation of IAM Dynamic Groups & Matching Rules which apply IAM Policies that grant access.
* You'll need to create IAM Dynamic Groups & Matching rules that match the OCI instances and assign a IAM Policy to them.
* The IAM Policy will define what permissions the OCI has for it's interactions with the OCI API.
* Minimum set of required permissions for instance principal IAM Policy:
    * inspect vnics
    * inspect vnic-attachments
    * inspect private-ips
    * use private-ips
    * use ons-topics

## Install Instructions
You can find [detailed install instructions here](INSTALL.md).
Here's the short list of commands to run, if you don't particularly care for an explication around what they do:
```
tmsh modify sys db config.allow.rfc3927  { value enable }
tmsh create sys management-route oci-169.254.0.0_16 { network 169.254.0.0/16 gateway <management-gateway-ip> }
tmsh modify sys db failover.selinuxallowscripts value enable
tmsh save sys config
cd /config/failover/
curl -L -o oci-f5-failover_v1.4.tar.gz https://github.com/mhermsdorferf5/oci-bigip-failover/raw/main/release-artifacts/oci-f5-failover_v1.4.tar.gz
tar -xzf oci-f5-failover_v1.4.tar.gz
restorecon -vr /config/failover
chmod 755 /config/failover/tgactive /config/failover/tgrefresh /config/failover/tgstandby
reboot
```
NOTE: After you finish these steps, you do need to configure the settings.json file.

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

## Python Virtual Environment
This tool uses python to interact with the OCI API and perform failover.  To that end, it needs it's own python environment with OCI libraries, etc.  The python venv build process is documented here: [python-venv.md](python-venv.md)