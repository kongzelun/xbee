#!/usr/bin/python3

"""
2018-04-10 18:36
"""

import os
import time
import json
import logging
import struct
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice, XBee64BitAddress
from digi.xbee.exception import TimeoutException


PORT = '/dev/ttyUSB0'

PRIORITY_FILE = 'priority.txt'

DATA_FORMAT = {
    'sequence': ('temperature', 'humidity', 'soil_moisture', 'light'),
    'temperature': 4,
    'humidity': 4,
    'soil_moisture': 4,
    'light': 4
}

THRESHOLDS = {
    '0013A200410809DD': {
        'soil_moisture': 800.0,
        'light_up': 300.0,
        'light_down': 50.0
    },
    '0013A200410809E3': {
        'soil_moisture': 800.0,
        'light_up': 300.0,
        'light_down': 50.0
    },
    '0013A200410809D8': {
        'soil_moisture': 800.0,
        'light_up': 300.0,
        'light_down': 50.0
    }
}

PLANTS = {
    '1': '0013A200410809DD',
    '2': '0013A200410809E3',
    '3': '0013A200410809D8'
}

PUMP_STATUS = {'0013A200410809DD': False, '0013A200410809E3': False, '0013A200410809D8': False}
LIGHT_STATUS = {'0013A200410809DD': False, '0013A200410809E3': False, '0013A200410809D8': False}

IRRIGATION_ADDRESS = '0013A200415D76BF'
LIGHT_ADDRESS = '0013A200415B8CBA'


def setup_logger(level=logging.DEBUG):
    """
    Setup logger.

    `return`: logger
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def write_to_json(address, data):
    """
    Write data to json file.
    ------------------------
    `address`: The remote devidebugce address.
    `data`: dict
    """

    logger = logging.getLogger(__name__)
    logger.info("Data to be writen: %s", data)

    json_data = None

    with open('data.json', mode='r') as json_file:

        try:
            json_data = json.load(json_file)
        except json.JSONDecodeError:
            logger.warning("Cannot load json data.")
            json_data = {}

    with open('data.json', mode='w')as json_file:

        if address in json_data:
            json_data[address].append(data)
        else:
            json_data[address] = []
            json_data[address].append(data)

        json.dump(json_data, json_file)


def main():
    """
    The procedure of detecting packet and process the message.
    ----------------------------------------------------------
    """

    setup_logger(level=logging.INFO)

    device = XBeeDevice(port=PORT, baud_rate=9600)
    device.open()

    logger = logging.getLogger(__name__)

    light_on = False

    light_system = RemoteXBeeDevice(device, XBee64BitAddress.from_hex_string(LIGHT_ADDRESS))
    irrigation_system = RemoteXBeeDevice(device, XBee64BitAddress.from_hex_string(IRRIGATION_ADDRESS))

    while True:

        try:
            message = device.read_data(timeout=60)
        except TimeoutException:
            logger.info("It seems the end device have not send any message for 1 minute.")
        else:
            message = message.to_dict()
            address = message['Sender: ']
            data = message['Data: ']

            logger.info("Address: %s", address)
            logger.debug("Data: %s", data)

            sensor_data = {}

            for part in DATA_FORMAT['sequence']:
                sensor_data[part] = round(struct.unpack('f', data[:DATA_FORMAT[part]])[0], 2)
                # delete the value data
                data = data[DATA_FORMAT[part]:]

            sensor_data['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')

            write_to_json(address, sensor_data)

            # ligth
            light_message = bytearray.fromhex(address)

            if sensor_data['light'] < THRESHOLDS[address]['light_down'] and not LIGHT_STATUS[address]:
                light_message.append(1)
                LIGHT_STATUS[address] = True
                logger.info('Light will turn on.')
                device.send_data_async(light_system, light_message)

            if sensor_data['light'] > THRESHOLDS[address]['light_up'] and LIGHT_STATUS[address]:
                light_message.append(0)
                LIGHT_STATUS[address] = False
                logger.info('Light will turn off.')
                device.send_data_async(light_system, light_message)

            # if True in LIGHT_STATUS.values() and not light_on:
            #     light_message.append(1)
            #     light_on = True
            #     logger.debug('Light will turn on.')
            #     device.send_data_async(light_system, light_message)
            # if True not in LIGHT_STATUS.values() and light_on:
            #     light_message.append(0)
            #     light_on = False
            #     logger.debug('Light will turn off.')
            #     device.send_data_async(light_system, light_message)

            # pump
            irrigation_message = bytearray.fromhex(address)

            if sensor_data['soil_moisture'] > THRESHOLDS[address]['soil_moisture'] and not PUMP_STATUS[address]:
                irrigation_message.append(1)
                PUMP_STATUS[address] = True
                logger.info('Pump will turn on.')
                device.send_data_async(irrigation_system, irrigation_message)

            if sensor_data['soil_moisture'] <= THRESHOLDS[address]['soil_moisture'] and PUMP_STATUS[address]:
                irrigation_message.append(0)
                PUMP_STATUS[address] = False
                logger.info('Pump will turn off.')
                device.send_data_async(irrigation_system, irrigation_message)

        #
        # App message
        #
        try:
            with open(PRIORITY_FILE, mode='r+') as f:
                m = list(f.read())
                if len(m) == 3:
                    f.truncate(0)
                    logger.info("App: %s", m)

                    priority_message = bytearray.fromhex(PLANTS[m[0]])
                    priority_message.append(int(m[2]))

                    if m[1] == 0:
                        # irrigation
                        device.send_data_async(irrigation_system, priority_message)
                    elif m[1] == 1:
                        # light
                        device.send_data_async(light_system, priority_message)
                else:
                    f.truncate(0)
                    logger.warning("App message error! (%s)", m)

        except FileNotFoundError:
            pass

    device.close()


if __name__ == '__main__':
    main()
