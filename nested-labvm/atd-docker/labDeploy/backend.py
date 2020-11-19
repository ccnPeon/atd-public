#!/usr/bin/python3

# TODO: Update file structure in production to match the topo_build.yaml topology type and move these files to 'all'

import json
import tornado.websocket
from datetime import timedelta, datetime, timezone, date
from ruamel.yaml import YAML
from ConfigureTopology import ConfigureTopology
import syslog
import tornado.ioloop
import asyncio
import sys

DEBUG = False

class BackEnd(tornado.websocket.WebSocketHandler):
    connections = set()

    def open(self):
        self.connections.add(self)
        self.send_to_syslog('OK', 'Connection opened from {0}'.format(self.request.remote_ip))
        with open('/var/log/socket_connections.log', 'w+') as connections_file:
            connections_file.write(self.request.remote_ip)
            connections_file.close()
        self.schedule_update()

    def close(self):
        self.connections.remove(self)
        self.send_to_syslog('INFO', 'Connection closed from {0}'.format(self.request.remote_ip))

    def on_message(self, message):
        data = json.loads(message)
        self.send_to_syslog("INFO", 'Received message {0} in socket.'.format(message))
        if data['type'] == 'openMessage':
            pass
        elif data['type'] == 'serverData':
            pass
        elif data['type'] == 'clientData':
            ConfigureTopology(selected_menu=data['selectedMenu'],selected_lab=data['selectedLab'],bypass_input=True,socket=self)


    def send_to_syslog(self,mstat,mtype):
        """
        Function to send output from service file to Syslog
        Parameters:
        mstat = Message Status, ie "OK", "INFO" (required)
        mtype = Message to be sent/displayed (required)
        """
        mmes = "\t" + mtype
        syslog.syslog("[{0}] {1}".format(mstat,mmes.expandtabs(7 - len(mstat))))
        if DEBUG:
            print("[{0}] {1}".format(mstat,mmes.expandtabs(7 - len(mstat))))

    def schedule_update(self):
        self.timeout = tornado.ioloop.IOLoop.instance().add_timeout(timedelta(seconds=60),self.keep_alive)
          
    def keep_alive(self):
        try:
            self.write_message(json.dumps({
                'type': 'keepalive',
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'data': 'ping'
            }))
        finally:
            self.schedule_update()

    def on_close(self):
        tornado.ioloop.IOLoop.instance().remove_timeout(self.timeout)
  
    def check_origin(self, origin):
      return True

    def send_to_socket(self,message):
        self.send_to_syslog("INFO", "Sending message: {0} to socket.".format(message))
        self.write_message(json.dumps({
            'type': 'serverData',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'status': message
        }))



def create_app():
    return tornado.web.Application([
        (r"/",BackEnd)])



if __name__ == '__main__':
    app = create_app()
    app.listen(80)
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        tornado.ioloop.IOLoop.instance().stop()