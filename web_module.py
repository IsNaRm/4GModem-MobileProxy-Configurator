import json
import time
from loguru import logger
from flask import Flask

import config
import requests

import utils

app = Flask(__name__)

@app.route('/change_ip/<device>')
def change_ip(device):
    result = change_ip(device)
    if result:
        return 'success'
    else:
        return 'error'

def change_ip(device):
    try:
        settings = utils.load_settings()
        modem = None
        for mac_address in settings:
            if mac_address.replace(':', '') == device:
                modem = settings[mac_address]
        if modem == None:
            return False
        devices = json.load(open('Devices.json'))
        all_data = devices[modem['device']]
        for order in all_data['order']:
            request_data = all_data[order]

            data = None
            json_data = None
            if 'data' in request_data:
                data = request_data['data']
            if 'json' in request_data:
                json_data = request_data['json']

            if request_data['type'].upper() == 'POST':
                res = requests.post(f"http://{modem['url']}{request_data['address']}", json=json_data, data=data)
            elif request_data['type'].upper() == 'GET':
                res = requests.get(f"http://{modem['url']}{request_data['address']}", json=json_data, data=data)
            print(f'{device} {order} {res.text}')
    except Exception as ex:
        logger.error(f'Ошибка смены айпи {ex}')
def start_server():
    app.run(host=config.local_ip, port=config.local_port)

if __name__ == '__main__':
    start_server()