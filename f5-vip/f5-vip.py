# =====================================
# description: F5 Failover Script
# author: ionut.neubauer@oracle.com
# date: 22-Jul-2020
# version: 1.4
# Updated: 03-Nov-2021
# Updates: 
# 1.2: 25-Oct-2021 - m.hermsdorfer@f5.com - Added support multiple vnics & optional topic setting of 'null'
# 1.3: 03-Nov-2021 - m.hermsdorfer@f5.com - Removed exits causing script to bail prior to all vnics, cleaned up logging a bit.
# 1.4: 23-Mar-2022 - m.hermsdorfer@f5.com - Additional cleanup, improved logging, etc.
# =====================================
from datetime import datetime
import json
import multiprocessing
import os
import signal
import sys
import time
import oci

def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

# Error Log sub
# writes logs to the error.log file
def error_log(message):
    log_error = open(os.path.dirname(os.path.realpath(sys.argv[0])) + '/error.log', 'a')
    log_error.write(str(datetime.now().strftime('%Y-%B-%d %H:%M:%S')) + ' ---> ' + message + '\n')
    log_error.close()
# END Error Log sub

# Assign to diferent vnic
# Moves the secondary IP to a different VNIC (actual failover)
def assign_to_different_vnic(private_ip_id, vnic_ocid):
    update_private_ip_details = oci.core.models.UpdatePrivateIpDetails(vnic_id=vnic_ocid)
    try:
        network.update_private_ip(private_ip_id, update_private_ip_details)
    except Exception as error:
        print('Script failed  at "assign_to_different_vnic" with this error: ' + str(error))
        error_log('Script failed  at "assign_to_different_vnic" with this error: ' + str(error))
# END Assign to diferent vnic

# Send Message sub
# Sends message via OCI's notification system to a topic.
def send_message(title, body):
    message_details = oci.ons.models.MessageDetails(body=body, title=title)
    if topic_id == "null":
        print('WARNING: Null TopicID not logging message: '+str(title)+str(body))
        error_log('WARNING: Null TopicID not logging message: '+str(title)+str(body))
    else:
        try:
            notification.publish_message(topic_id, message_details)
        except Exception as error:
            print('Script failed  at "send_message" with this error: ' + str(error))
            error_log('Script failed  at "send_message" with this error: ' + str(error))
# END send_message sub

# Check Config sub
# Checks that we successfully pulled the required elements from the config file.
def check_config():
    status_list = []
    variable_list = ['topic_id', 'multiprocess', 'vnics']
    for variable_item in variable_list:
        if not settings[variable_item]:
            print('Variable ' + variable_item + ' is empty in settings.json')
            error_log('Variable ' + variable_item + ' is empty in settings.json')
            status_list.append('nok')
        else:
            status_list.append('ok')
    if 'nok' in status_list:
        sys.exit(1)
    else:
        pass
# END Check Config sub


# main sub, 'stage 1'
def main():
    if multiprocess == "on":
        # multiprocessing.cpu_count() will create processes based on the number of cores available.
        # If you want, this option can be changed to an integer.
        pool = multiprocessing.Pool(multiprocessing.cpu_count(), init_worker)
        try:
            for vnic in vnics:
                vnic_id = vnic['move_to_vnic']
                ip_to_move = vnic['ip_to_move']
                for ip_ocid in range(len(ip_to_move)):
                    print('Moving IP ' + ip_to_move[ip_ocid])
                    error_log('Moving IP ' + ip_to_move[ip_ocid])
                    pool.apply_async(assign_to_different_vnic, args=(ip_to_move[ip_ocid], vnic_id))
            pool.close()
            pool.join()
            print('Stage 1 completed.')
        except Exception as error:
            print('Script failed  at "Stage 1" with this error: ' + str(error))
            error_log('Script failed  at "Stage 1" with this error: ' + str(error))
            # Continue on, logging the exception, but keep trying to move IPs.
            #pool.terminate()
            #sys.exit(1)
        except KeyboardInterrupt:
            print('\nInterrupted. Exiting...')
            pool.terminate()
            sys.exit(1)
    elif multiprocess == "off":
        for vnic in vnics:
            vnic_id = vnic['move_to_vnic']
            ip_to_move = vnic['ip_to_move']
            for ip_ocid in range(len(ip_to_move)):
                print('Moving IP ' + ip_to_move[ip_ocid])
                error_log('Moving IP ' + ip_to_move[ip_ocid])
                try:
                    assign_to_different_vnic(ip_to_move[ip_ocid], vnic_id)
                except Exception as error:
                    print('Script failed  at "Stage 1" with this error: ' + str(error))
                    error_log('Script failed  at "Stage 1" with this error: ' + str(error))
                    #sys.exit(1)
        print('Stage 1 completed.')
# END main

# First thing first, check for config args & config file:
try:
    if len(sys.argv) > 1:
        if os.path.exists(sys.argv[1]):
            print('Using ' + sys.argv[1] + ' as a configuration file.')
            error_log('Using ' + sys.argv[1] + ' as a configuration file.')
            my_file = open(os.path.dirname(os.path.realpath(sys.argv[0])) + '/' + sys.argv[1], 'r')
            settings = json.load(my_file)
            my_file.close()
        else:
            print('\n!!! No ' + sys.argv[1] + ' file !!!')
            error_log('No ' + sys.argv[1] + ' file')
            sys.exit(1)
    else:
        print('Using settings.json as a configuration file.')
        error_log('Using settings.json as a configuration file.')
        my_file = open(os.path.dirname(os.path.realpath(sys.argv[0])) + '/settings.json', 'r')
        settings = json.load(my_file)
        my_file.close()
except IOError:
    if len(sys.argv) > 2:
        print('\n!!! No ' + sys.argv[1] + ' file !!!')
        error_log('No ' + sys.argv[1] + ' file')
        sys.exit(1)
    else:
        print('\n!!! No settings.json file !!!')
        error_log('No settings.json file')
        sys.exit(1)

check_config()

vnics = settings['vnics']
multiprocess = settings['multiprocess']
topic_id = settings['topic_id']

start_timer = time.time()
status = True
not_completed = []

try:
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
except Exception as e:
    print('Script failed to get OCI instance principal "signer" token with this error, check routing to ensure request leaves primary instance VNIC: ' + str(e))
    error_log('Script failed to get OCI instance principal "signer" token with this error, check routing to ensure request leaves primary instance VNIC: ' + str(e))
    sys.exit(1)

network = oci.core.VirtualNetworkClient(config={}, signer=signer)
notification = oci.ons.NotificationDataPlaneClient(config={}, signer=signer)

# Stage 1 - First attempt to move the IPs.
if __name__ == '__main__':
    print('Executing Stage 1.')
    error_log('Executing Stage 1.')
    main()

# Stage 2 - Check if Stage 1 was successful. If not, trying to move again the IPs.
while status:
    print('Checking Stage 2.')
    for vnic in vnics:
        vnic_id = vnic['move_to_vnic']
        ip_to_move = vnic['ip_to_move']
        for item in range(len(ip_to_move)):
            if network.get_private_ip(ip_to_move[item]).data.vnic_id != vnic_id:
                print('Found IP not yet moved to Active BIG-IP, attempting to move the following IP now: ' + ip_to_move[item] )
                error_log('Found IP not yet moved to Active BIG-IP, attempting to move the following IP now: ' + ip_to_move[item] )
                try:
                    assign_to_different_vnic(ip_to_move[item], vnic_id)
                    not_completed.append(ip_to_move[item])
                    time.sleep(2)
                except Exception as e:
                    print('Script failed at "Stage 2"  with this error: ' + str(e))
                    error_log('Script failed at "Stage 2"  with this error: ' + str(e))
                    #sys.exit(1)
        if not_completed:
            not_completed = []
            if int(time.time() - start_timer) < int(settings['timeout_seconds']):
                continue
            else:
                print('Failover not completed to ' + network.get_vnic(
                    vnic_id).data.display_name + '. Check error.log file!')
                error_log(
                    'Failover not completed to ' + network.get_vnic(vnic_id).data.display_name + '. Check error.log file!')
                try:
                    send_message('F5 Failover Cluster', 'Failover not completed to ' + network.get_vnic(
                        vnic_id).data.display_name + '. Check error.log file!')
                    status = False
                    #sys.exit(0)
                except Exception as e:
                    print('Script failed at "failover timeout notification"  with this error: ' + str(e))
                    error_log('Script failed at "failover timeout notification"  with this error: ' + str(e))
                    #sys.exit(1)

        else:
            print('Failover completed to ' + network.get_vnic(vnic_id).data.display_name + '.')
            error_log('Failover completed to ' + network.get_vnic(vnic_id).data.display_name + '.')
            try:
                send_message('F5 Failover Cluster',
                             'Failover completed to ' + network.get_vnic(vnic_id).data.display_name + '.')
                status = False
                #sys.exit(1)
            except Exception as e:
                print('Script failed at "failover notification"  with this error: ' + str(e))
                error_log('Script failed at "failover notification"  with this error: ' + str(e))
                #sys.exit(1)
