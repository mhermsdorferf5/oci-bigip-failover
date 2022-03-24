# =====================================
# description: F5 Failover Script
# author: ionut.neubauer@oracle.com
# date: 08-Jul-2020
# version: 1.0
# =====================================
import oci
from datetime import datetime
import os, sys, time, json


def error_log(message):
    error_log = open(os.path.dirname(os.path.realpath(sys.argv[0])) + '/error.log', 'a')
    error_log.write(str(datetime.now().strftime('%Y-%B-%d %H:%M:%S')) + ' ---> ' + message + '\n')
    error_log.close()


try:
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
except Exception as e:
    print('Script failed at "signer" with this error: ' + str(e))
    error_log('Script failed at "signer" with this error: ' + str(e))
    sys.exit(1)


network = oci.core.VirtualNetworkClient(config={}, signer=signer)
notification = oci.ons.NotificationDataPlaneClient(config={}, signer=signer)


def no_variable():
    status_list = []
    list = ['move_to_vnic', 'topic_id', 'timeout_seconds', 'ip_to_move']
    for i in list:
        if not settings[i]:
            print('Variable ' + i + ' is empty in settings.json')
            error_log('Variable ' + i + ' is empty in settings.json')
            status_list.append('nok')
        else:
            status_list.append('ok')
    if 'nok' in status_list:
        time.sleep(2)
        sys.exit(1)
    else:
        pass


try:
    file = open(os.path.dirname(os.path.realpath(sys.argv[0])) + '/settings.json', 'r')
    settings = json.load(file)
    file.close()
except IOError:
    print('\n!!! No settings.json file !!!')
    error_log('No settings.json file')
    time.sleep(2)
    sys.exit(1)

no_variable()


def assign_to_different_vnic(private_ip_id, vnic_id):
    update_private_ip_details = oci.core.models.UpdatePrivateIpDetails(vnic_id=vnic_id)
    network.update_private_ip(private_ip_id, update_private_ip_details)


def send_message(title, body):
    message_details = oci.ons.models.MessageDetails(body=body, title=title)
    notification.publish_message(topic_id, message_details)


vnic_id = settings['move_to_vnic']
ip_to_move = settings['ip_to_move']

# Stage 1 - First attempt.
for i in range(len(ip_to_move)):
    print('Moving IP ' + ip_to_move[i])
    error_log('Moving IP ' + ip_to_move[i])
    try:
        # Test Stage 2 by omitting 1 ocid1.privateip
        # if ip_to_move[i] == 'ocid1.privateip.oc1.eu-frankfurt-1.aaaaaaaaibk2wkdsiext3jzi2vuqqmuobd3bexziksiaguird5qintli6qda':
        #     pass
        # else:
        #     assign_to_different_vnic(ip_to_move[i], vnic_id)
        assign_to_different_vnic(ip_to_move[i], vnic_id)
    except Exception as e:
        print('Script failed  at "Stage 1" with this error: ' + str(e))
        error_log('Script failed  at "Stage 1" with this error: ' + str(e))
        sys.exit(1)

status = True
not_completed = []
topic_id = settings['topic_id']
start_timer = time.time()

# Stage 2 - Check if Stage 1 was successful.
while status:
    for i in range(len(ip_to_move)):
        if network.get_private_ip(ip_to_move[i]).data.vnic_id != vnic_id:
            print('This IP was not moved ---> ' + ip_to_move[i] + '. Trying to move...')
            error_log('This IP was not moved ---> ' + ip_to_move[i] + '. Trying to move...')
            try:
                assign_to_different_vnic(ip_to_move[i], vnic_id)
                not_completed.append(ip_to_move[i])
                time.sleep(2)
                # print(not_completed)
            except Exception as e:
                print('Script failed at "Stage 2"  with this error: ' + str(e))
                error_log('Script failed at "Stage 2"  with this error: ' + str(e))
                sys.exit(1)
    if not_completed:
        not_completed = []
        if int(time.time() - start_timer) < int(settings['timeout_seconds']):
            continue
        else:
            print('Failover not completed to ' + network.get_vnic(vnic_id).data.display_name + '. Check error.log file!')
            error_log('Failover not completed to ' + network.get_vnic(vnic_id).data.display_name + '. Check error.log file!')
            try:
                send_message('F5 Failover Cluster', 'Failover not completed to ' + network.get_vnic(vnic_id).data.display_name + '. Check error.log file!')
                status = False
                sys.exit(0)
            except Exception as e:
                print('Script failed at "failover timeout notification"  with this error: ' + str(e))
                error_log('Script failed at "failover timeout notification"  with this error: ' + str(e))
                sys.exit(1)

    else:
        print('Failover completed to ' + network.get_vnic(vnic_id).data.display_name + '.')
        error_log('Failover completed to ' + network.get_vnic(vnic_id).data.display_name + '.')
        try:
            send_message('F5 Failover Cluster', 'Failover completed to ' + network.get_vnic(vnic_id).data.display_name + '.')
            status = False
            sys.exit(1)
        except Exception as e:
            print('Script failed at "failover notification"  with this error: ' + str(e))
            error_log('Script failed at "failover notification"  with this error: ' + str(e))
            sys.exit(1)
