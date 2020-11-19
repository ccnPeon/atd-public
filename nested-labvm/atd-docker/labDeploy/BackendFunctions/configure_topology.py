#!/usr/bin/env python

from rcvpapi.rcvpapi import *
import syslog, time
from ruamel.yaml import YAML
import paramiko
from scp import SCPClient
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


DEBUG = False

# Cmds to copy bare startup to running
cp_run_start = """enable
copy running-config startup-config
"""
cp_start_run = """enable
copy startup-config running-config
"""
# Cmds to grab ZTP status
ztp_cmds = """enable
show zerotouch | grep ZeroTouch
"""
# Cancel ZTP
ztp_cancel = """enable
zerotouch cancel
"""

def connect_to_cvp(access_info):
    # Adding new connection to CVP via rcvpapi
    cvp_clnt = ''
    for c_login in access_info['login_info']['cvp']['shell']:
        if c_login['user'] == 'arista':
            while not cvp_clnt:
                try:
                    cvp_clnt = CVPCON(access_info['nodes']['cvp'][0]['ip'],c_login['user'],c_login['pw'])
                    send_to_syslog("OK","Connected to CVP at {0}".format(access_info['nodes']['cvp'][0]['ip']))
                    return cvp_clnt
                except:
                    send_to_syslog("ERROR", "CVP is currently unavailable....Retrying in 30 seconds.")
                    time.sleep(30)

def remove_configlets(device,lab_configlets):
    """
    Removes all configlets except the ones defined as 'base'
    Define base configlets that are to be untouched
    """
    base_configlets = ['ATD-INFRA']
    
    configlets_to_remove = []
    configlets_to_remain = base_configlets

    configlets = client.getConfigletsByNetElementId(device)
    for configlet in configlets['configletList']:
        if configlet['name'] in base_configlets:
            configlets_to_remain.append(configlet['name'])
            send_to_syslog("INFO", "Configlet {0} is part of the base on {1} - Configlet will remain.".format(configlet['name'], device.hostname))
        elif configlet['name'] not in lab_configlets:
            configlets_to_remove.append(configlet['name'])
            send_to_syslog("INFO", "Configlet {0} not part of lab configlets on {1} - Removing from device".format(configlet['name'], device.hostname))
        else:
            pass
    if len(configlets_to_remain) > 0:
        device.removeConfiglets(client,configlets_to_remove)
        client.addDeviceConfiglets(device, configlets_to_remain)
        client.applyConfiglets(device)
    else:
        pass

def get_public_ip():
    """
    Function to get Public IP.
    """
    response = requests.get('http://ipecho.net/plain')
    return(response.text)

def create_websocket():
    
    try:
        url = "ws://127.0.0.1:8888/backend"
        send_to_syslog("INFO", "Connecting to web socket on {0}.".format(url))
        ws = create_connection(url)
        ws.send(json.dumps({
            'type': 'openMessage',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'status': 'ConfigureTopology Opened.'
        }))
        send_to_syslog("OK", "Connected to web socket for ConfigureTopology.")
        ws.name = 'ConfigureTopology'
        return ws
    except:
        send_to_syslog("ERROR", "ConfigureTopology cannot connect to web socket.")

def close_websocket():
    ws.send(json.dumps({
            'type': 'closeMessage',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'status': 'ConfigureTopology Closing.'
        }))
    ws.close()

def get_device_info():
    eos_devices = []
    for dev in client.inventory:
        tmp_eos = client.inventory[dev]
        tmp_eos_sw = CVPSWITCH(dev, tmp_eos['ipAddress'])
        tmp_eos_sw.updateDevice(client)
        eos_devices.append(tmp_eos_sw)
    return(eos_devices)

def update_topology(selected_lab,configlets):
    # Get all the devices in CVP
    devices = get_device_info()
    # Loop through all devices
    
    for device in devices:
        # Get the actual name of the device
        device_name = device.hostname
        
        # Define a list of configlets built off of the lab yaml file
        lab_configlets = []
        for configlet_name in configlets[selected_lab][device_name]:
            lab_configlets.append(configlet_name)

        # Remove unnecessary configlets
        remove_configlets(device, lab_configlets)

        # Apply the configlets to the device
        client.addDeviceConfiglets(device, lab_configlets)
        client.applyConfiglets(device)

    # Perform a single Save Topology by default
    client.saveTopology()


def push_bare_config(veos_host, veos_ip, veos_config):
    """
    Pushes a bare config to the EOS device.
    """
    # Write config to tmp file
    device_config = "/tmp/" + veos_host + ".cfg"
    with open(device_config,"a") as tmp_config:
        tmp_config.write(veos_config)

    DEVREBOOT = False
    veos_ssh = paramiko.SSHClient()
    veos_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    veos_ssh.connect(hostname=veos_ip, username="root", password="", port="50001")
    scp = SCPClient(veos_ssh.get_transport())
    scp.put(device_config,remote_path="/mnt/flash/startup-config")
    scp.close()
    veos_ssh.exec_command('FastCli -c "{0}"'.format(cp_start_run))
    veos_ssh.exec_command('FastCli -c "{0}"'.format(cp_run_start))
    stdin, stdout, stderr = veos_ssh.exec_command('FastCli -c "{0}"'.format(ztp_cmds))
    ztp_out = stdout.readlines()
    if 'Active' in ztp_out[0]:
        DEVREBOOT = True
        send_to_syslog("INFO", "Rebooting {0}...This will take a couple minutes to come back up".format(veos_host))
        #veos_ssh.exec_command("/sbin/reboot -f > /dev/null 2>&1 &")
        veos_ssh.exec_command('FastCli -c "{0}"'.format(ztp_cancel))
    veos_ssh.close()
    return(DEVREBOOT)

def check_for_tasks():
    client.getRecentTasks(50)
    tasks_in_progress = False
    for task in client.tasks['recent']:
        if 'in progress' in task['workOrderUserDefinedStatus'].lower():
            send_to_syslog('INFO', 'Task Check: Task {0} status: {1}'.format(task['workOrderId'],task['workOrderUserDefinedStatus']))
            tasks_in_progress = True
        else:
            pass
    
    if tasks_in_progress:
        send_to_syslog('INFO', 'Tasks in progress. Waiting for 10 seconds.')
        print('Tasks are currently executing. Waiting 10 seconds...')
        time.sleep(10)
        check_for_tasks()

    else:
        return

def deploy_lab(selected_menu,selected_lab,bypass_input=False):

    # Check for additional commands in lab yaml file
    lab_file = open('/home/arista/menus/{0}'.format(selected_menu + '.yaml'))
    lab_info = YAML().load(lab_file)
    lab_file.close()

    additional_commands = []
    if 'additional_commands' in lab_info['lab_list'][selected_lab]:
        additional_commands = lab_info['lab_list'][selected_lab]['additional_commands']

    # Get access info for the topology
    f = open('/etc/atd/ACCESS_INFO.yaml')
    access_info = YAML().load(f)
    f.close()

    # List of configlets
    lab_configlets = lab_info['labconfiglets']

    # Send message that deployment is beginning
    send_to_syslog('INFO', 'Starting deployment for {0} - {1} lab...'.format(selected_menu,selected_lab))
    print("Starting deployment for {0} - {1} lab...".format(selected_menu,selected_lab))

    # Check if the topo has CVP, and if it does, create CVP connection
    if 'cvp' in access_info['nodes']:
        client = connect_to_cvp(access_info)

        check_for_tasks()

        # Config the topology
        update_topology(selected_lablab_configlets)
        
        # Execute all tasks generated from reset_devices()
        print('Gathering task information...')
        send_to_syslog("INFO", 'Gathering task information')
        client.getAllTasks("pending")
        tasks_to_check = client.tasks['pending']
        send_to_syslog('INFO', 'Relevant tasks: {0}'.format([task['workOrderId'] for task in tasks_to_check]))
        client.execAllTasks("pending")
        send_to_syslog("OK", 'Completed setting devices to topology: {}'.format(selected_lab))

        print('Waiting on change control to finish executing...')
        all_tasks_completed = False
        while not all_tasks_completed:
            tasks_running = []
            for task in tasks_to_check:
                if client.getTaskStatus(task['workOrderId'])['taskStatus'] != 'Completed':
                    tasks_running.append(task)
                elif client.getTaskStatus(task['workOrderId'])['taskStatus'] == 'Failed':
                    print('Task {0} failed.'.format(task['workOrderId']))
                else:
                    pass
            
            if len(tasks_running) == 0:

                # Execute additional commands in linux if needed
                if len(additional_commands) > 0:
                    print('Running additional setup commands...')
                    send_to_syslog('INFO', 'Running additional setup commands.')

                    for command in additional_commands:
                        os.system(command)

                if not bypass_input:
                    input('Lab Setup Completed. Please press Enter to continue...')
                    send_to_syslog("OK", 'Lab Setup Completed.')
                else:
                    send_to_syslog("OK", 'Lab Setup Completed.')
                all_tasks_completed = True
            else:
                pass
    else:
        # Open up defaults
        f = open('/home/arista/cvp/cvp_info.yaml')
        cvp_info = YAML().load(f)
        f.close()

        cvp_configs = cvp_info["cvp_info"]["configlets"]
        infra_configs = cvp_configs["containers"]["Tenant"]

        send_to_syslog("INFO","Setting up {0} lab".format(selected_lab))
        for node in access_info["nodes"]["veos"]:
            device_config = ""
            hostname = node["hostname"]
            base_configs = cvp_configs["netelements"]
            configs = base_configs[hostname] + infra_configs + lab_configlets[selected_lab][hostname]
            configs = list(dict.fromkeys(configs))
            for config in configs:
                with open('/tmp/atd/topologies/{0}/configlets/{1}'.format(access_info['topology'], config), 'r') as configlet:
                    device_config += configlet.read()
            send_to_syslog("INFO","Pushing {0} config for {1} on IP {2} with configlets: {3}".format(selected_lab,hostname,node["ip"],configs))
            push_bare_config(hostname, node["ip"], device_config)

            # Execute additional commands in linux if needed
            if len(additional_commands) > 0:
                print('Running additional setup commands...')

                for command in additional_commands:
                    os.system(command)

            input("Lab Setup Completed. Please press Enter to continue...")