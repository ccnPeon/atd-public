#!/usr/bin/env python
import os
import sys
import re
from ruamel.yaml import YAML
import requests
from websocket import create_connection



######################################
########## Global Variables ##########
######################################
DEBUG = False
__version__ = "2.1"

# Open ACCESS_INFO.yaml and load the variables
f = open('/etc/atd/ACCESS_INFO.yaml')
access_info = YAML().load(f)
f.close()

# Set Main Script Variables
topology = access_info['topology']
login_info = access_info['login_info']


# Open topo_build.yaml and load
try:
  f = open('/opt/atd/topologies/{0}/topo_build.yml'.format(topology))
  topoinfo = YAML().load(f)
  f.close()
except:
  sys.exit("topo_build not available")

veos_info = topoinfo['nodes']
print(veos_info)
additional_ssh_nodes = topoinfo['additional_ssh_nodes']

# Set default menu mode
menu_mode = 'MAIN'
previous_menu = ''

###################################################
#################### Functions ####################
###################################################

def text_to_int(text):
  return int(text) if text.isdigit() else text

def natural_keys(text):
  return [ text_to_int(char) for char in re.split(r'(\d+)', text) ]

def sort_veos(vd):
    if vd == None:
        return
    tmp_l = []
    tmp_d = {}
    fin_l = []
    for t_veos in vd:
        t_veos_name = list(t_veos.keys())[0]
        tmp_l.append(t_veos_name)
        tmp_d[t_veos_name] = dict(t_veos[t_veos_name])
        tmp_d[t_veos_name]['hostname'] = t_veos_name
    tmp_l.sort(key=natural_keys)
    # If cvx in list, move to end
    if 'cvx' in tmp_l[0]:
        tmp_cvx = tmp_l[0]
        tmp_l.pop(0)
        tmp_l.append(tmp_cvx)
    for t_veos in tmp_l:
        fin_l.append(tmp_d[t_veos])
    return(fin_l)

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

def close_websocket(ws):
    ws.send(json.dumps({
            'type': 'closeMessage',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'status': 'ConfigureTopology Closing.'
        }))
    ws.close()

def send_to_socket(ws,selected_lab,selected_menu):
    message = {}
    message['type'] = 'clientData'
    message['selectedMenu'] = selected_menu;
    message['selectedLab'] = selected_lab;
    ws.send(json.dumps(message))

def device_menu():
    global menu_mode
    global previous_menu
    os.system("clear")
    # Create Device Dict to save devices and later execute based on matching the counter to a dict key
    device_dict = {}

    # Sort veos instances
    veos_info_sorted = sort_veos(veos_info)
    additional_ssh_nodes_sorted = sort_veos(additional_ssh_nodes)
    
    print("\n\n*****************************************")
    print("*****Jump Host for Arista Test Drive*****")
    print("*****************************************")
    print("\n\n==========Device SSH Menu==========\n")
    print("Screen Instructions:\n")

    print("* Select specific screen - Ctrl + a <number>")
    print("* Select previous screen - Ctrl + a p")
    print("* Select next screen - Ctrl + a n")
    print("* Exit all screens (return to menu) - Ctrl + a \\")

    print("\nPlease select from the following options:")

    counter = 1
    for veos in veos_info_sorted:
        print("{0}. {1} ({2})".format(str(counter),veos['hostname'],veos['hostname']))
        device_dict[str(counter)] = { 'ip_addr': veos['ip_addr'] }
        device_dict[veos['hostname']] = { 'ip_addr': veos['ip_addr'] }
        counter += 1
    if additional_ssh_nodes_sorted != None:
      for additional_ssh_node in additional_ssh_nodes_sorted:
          print("{0}. {1} ({2})".format(str(counter),additional_ssh_node['hostname'],additional_ssh_node['hostname']))
          device_dict[str(counter)] = { 'ip_addr': additional_ssh_node['ip_addr'] }
          device_dict[additional_ssh_node['hostname']] = { 'ip_addr': additional_ssh_node['ip_addr'] }
          if 'port' in additional_ssh_node:
              device_dict[str(counter)]['port'] = additional_ssh_node['port']
              device_dict[additional_ssh_node['hostname']]['port'] = additional_ssh_node['port']
          counter += 1


    
    print("\nOther Options: ")
    print("96. Screen (screen) - Opens a screen session to each of the hosts")
    print("97. Back to Previous Menu (back)")
    print("98. Shell (shell/bash)")
    print("99. Back to Main Menu (main/exit) - CTRL + c")
    print("")
    user_input = input("What would you like to do? ")

    # Check to see if input is in device_dict
    counter = 1
    # try:
    if user_input.lower() in device_dict:
        ssh_command = 'ssh -o StrictHostKeyChecking=no arista@{0}'.format(device_dict[user_input]['ip_addr'])
        previous_menu = menu_mode
        if 'port' in device_dict[user_input]:
            ssh_command += ' -p {0}'.format(device_dict[user_input]['port'])
        else:
          pass
        # Execute ssh command
        os.system(ssh_command)
    elif user_input == '96' or user_input.lower() == 'screen':
        os.system('/usr/bin/screen')
    elif user_input == '97' or user_input.lower() == 'back':
        if menu_mode == previous_menu:
            menu_mode = 'MAIN'
        else:
            menu_mode = previous_menu
    elif user_input == '98' or user_input.lower() == 'bash' or user_input.lower() == 'shell':
        os.system('/bin/bash')
    elif user_input == '99' or user_input.lower() == 'main' or user_input == '99' or user_input.lower() == 'exit':
        menu_mode = 'MAIN'
    else:
        print("Invalid Input")
    # except:
    #   print("Invalid Input")



def lab_options_menu():
    global menu_mode
    global previous_menu

    os.system("clear")
    print("\n\n*****************************************")
    print("*****Jump Host for Arista Test Drive*****")
    print("*****************************************")

    if menu_mode == 'LAB_OPTIONS':
      # Get Yaml Files in /home/arista/menus
      menu_files = os.listdir('/opt/atd/topologies/{0}/files/menus'.format(topology))
      menu_files.sort()
      
    # Create Lab Options dict to save lab and later navigate to that menu of labs
      lab_options_dict = {}

      # Display Lab Options
      counter = 1
      print('\n\n==========Lab Options Menu==========\n')
      print("Please select from the following options: \n")
      
      # Iterate through lab menu files and print names without .yaml - Increment counter to reflect choices
      counter = 1
      for menu_type in menu_files:
          if menu_type != 'default.yaml':
            # Print Lab Menu and add options to lab options dict
            print('{0}. {1} ({2})'.format(str(counter),menu_type.replace('-', ' ').replace('.yaml', ''), menu_type.replace('.yaml', '').lower() ))
            lab_options_dict[str(counter)] = menu_type
            lab_options_dict[menu_type.replace('.yaml', '').lower()] = menu_type
            counter += 1

      # Additional Menu Options
      print("\nOther Options: ")
      print("97. Back to Previous Menu (back)")
      print("98. SSH to Devices (ssh)")
      print("99. Back to Main Menu (main/exit) - CTRL + c\n")
      
      user_input = input("\nWhat would you like to do?: ").replace(' ', '')

      # Check to see if digit is in lab_options dict
      # try:
      if user_input.lower() in lab_options_dict:
          previous_menu = menu_mode
          menu_mode = 'LAB_' + lab_options_dict[user_input]
      elif user_input == '97' or user_input.lower() == 'back':
          if menu_mode == previous_menu:
              menu_mode = 'MAIN'
          else:
              menu_mode = previous_menu
      elif user_input == '98' or user_input.lower() == 'ssh':
          previous_menu = menu_mode
          menu_mode = 'DEVICE_SSH'
      elif user_input == '99' or user_input.lower() == 'main' or user_input == '99' or user_input.lower() == 'exit':
          menu_mode = 'MAIN'
      else:
          print("Invalid Input")
      # except:
      #     print("Invalid Input")



    elif 'LAB_' in menu_mode and menu_mode != 'LAB_OPTIONS':
      
      # Create Commands dict to save commands and later execute based on matching the counter to a dict key
      options_dict = {}

      # Open yaml for the lab option (minus 'LAB_' from menu mode) and load the variables
      menu_file = open('/opt/atd/topologies/{0}/files/menus/{1}'.format(topology,menu_mode[4:]))
      menu_info = YAML().load(menu_file)
      menu_file.close()

      print('\n\n==========Lab Options Menu - {0}==========\n'.format(menu_mode[4:].replace('-', ' ').replace('.yaml', '')))
      print("Please select from the following options: \n")
      
      counter = 1
      for lab in menu_info['lab_list']:
        print("{0}. {1}".format(str(counter),menu_info['lab_list'][lab]['description']))
        options_dict[str(counter)] = {'selected_lab': lab, 'selected_menu': menu_mode[4:].replace('.yaml', '')}
        options_dict[lab] = {'selected_lab': lab, 'selected_menu': menu_mode[4:].replace('.yaml', '')}
        counter += 1
      print('\n')

      # Additional Menu Options
      print("Other Options: ")
      print("97. Back to Previous Menu (back)")
      print("98. SSH to Devices (ssh)")
      print("99. Back to Main Menu (main/exit) - CTRL + c\n")

      # User Input
      user_input = input("What would you like to do?: ").replace(' ', '')

      # Check to see if input is in commands_dict
      # try:
      if user_input.lower() in options_dict:
          previous_menu = menu_mode
          ws = create_websocket(get_public_ip())
          send_to_socket(selected_menu=options_dict[user_input]['selected_menu'],selected_lab=options_dict[user_input]['selected_lab'])
          ws.close()
      elif user_input == '97' or user_input.lower() == 'back':
          if menu_mode == previous_menu:
              menu_mode = 'MAIN'
          else:
              menu_mode = previous_menu
      elif user_input == '98' or user_input.lower() == 'ssh':
          previous_menu = menu_mode
          menu_mode = 'DEVICE_SSH'
      elif user_input == '99' or user_input.lower() == 'main' or user_input == '99' or user_input.lower() == 'exit':
          menu_mode = 'MAIN'
      else:
          print("Invalid Input")
      # except:
      #     print("Invalid Input")

def main_menu():
    global menu_mode
    global previous_menu

    os.system("clear")
    print("\n\n*****************************************")
    print("*****Jump Host for Arista Test Drive*****")
    print("*****************************************")
    print("\n\n==========Main Menu==========\n")
    print("Please select from the following options: ")

    # Create options dict to later send to deploy_lab
    options_dict = {}

    # Open yaml for the default yaml and read what file to lookup for default menu
    default_menu_file = open('/opt/atd/topologies/{0}/files/menus/default.yaml'.format(topology))
    default_menu_info = YAML().load(default_menu_file)
    default_menu_file.close()


    # Open yaml for the lab option (minus 'LAB_' from menu mode) and load the variables
    menu_file = open('/opt/atd/topologies/{0}/files/menus/{1}'.format(topology,default_menu_info['default_menu']))
    menu_info = YAML().load(menu_file)
    menu_file.close()


    
    counter = 1
    menu = default_menu_info['default_menu'].replace('.yaml', '')
    for lab in menu_info['lab_list']:
      print("{0}. {1}".format(str(counter),menu_info['lab_list'][lab]['description']))
      options_dict[str(counter)] = {'selected_lab': lab, 'selected_menu': menu}
      options_dict[lab] = {'selected_lab': lab, 'selected_menu': menu}
      counter += 1
    print('\n')



    print("97. Additional Labs (labs)")
    print("98. SSH to Devices (ssh)")
    print("99. Exit LabVM (quit/exit) - CTRL + c")
    print("")

    user_input = input("What would you like to do?: ").replace(' ', '')
    
    # Check user input to see which menu to change to
    # try:
    if user_input.lower() in options_dict:
        ws = create_websocket(get_public_ip())
        send_to_socket(selected_menu=options_dict[user_input]['selected_menu'],selected_lab=options_dict[user_input]['selected_lab'])
        ws.close()
    elif user_input == '98' or user_input.lower() == 'ssh':
        previous_menu = menu_mode
        menu_mode = 'DEVICE_SSH'
    elif user_input == '97' or user_input.lower() == 'labs':
        previous_menu = menu_mode
        menu_mode = 'LAB_OPTIONS'
    elif user_input == '99' or user_input.lower() == 'exit' or user_input.lower() == 'quit':
        menu_mode = 'EXIT'
    else:
        print("Invalid Input")
    # except:
    #     print("Invalid Input")



##############################################
#################### Main ####################
##############################################

def main():
    if os.getuid() != 0:
        global menu_mode
        # Create Menu Manager

        if sys.stdout.isatty():
            while menu_mode:
                try:
                    if menu_mode == 'MAIN':
                      main_menu()
                    elif menu_mode == 'DEVICE_SSH':
                      device_menu()
                    elif 'LAB_' in menu_mode:
                      lab_options_menu()
                    elif menu_mode == 'EXIT':
                      print('User exited.')
                      quit()
                except KeyboardInterrupt:
                    if menu_mode == 'MAIN':
                      print('User exited.')
                      quit()
                    else:
                      menu_mode = 'MAIN'

        else:
            os.system("/usr/lib/openssh/sftp-server")
    
    else:

      os.system("/bin/bash")
        
if __name__ == '__main__':
    main()
