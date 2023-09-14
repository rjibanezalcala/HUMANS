# -*- coding: utf-8 -*-
"""
Created on Thu Sep  7 13:42:41 2023

@author: Raquel
"""

from openant.easy.node import Node
from openant.devices import ANTPLUS_NETWORK_KEY
from openant.devices.heart_rate import HeartRate, HeartRateData
import datetime
import pytz
import subprocess

class HeartRateTracker:
    def __init__(self, **kwargs):
        self.timezone = pytz.timezone(kwargs.get('timestamp_timezone', 'UTC'))
        self.device = None
        self.node = None
        self.hr_data = []
        
    def connect_hr_device(self, device_id=0):
        self.node = Node()
        self.node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)
    
        self.device = HeartRate(self.node, device_id=device_id)
        
        self.set_hr_device_callbacks(on_device_found = self.on_found,
                                           on_data = self.on_device_data)
        
    def on_found(self):
        print(f"Device {self.device} found and receiving...")

    def on_device_data(self, page: int, page_name: str, data):
        if isinstance(data, HeartRateData):
            data = {'hr': str(data.heart_rate)+' bpm', 'time':self.timezone.localize(datetime.datetime.now()).strftime("%a %b %d %H:%M:%S.%f %Y %Z")}
            self.hr_data.append(data)
            # print(f"Heart rate update {data.heart_rate} bpm")
            print(f"Heart rate update: {data}")
            
    def set_hr_device_callbacks(self, on_device_found, on_data):
        self.device.on_found = on_device_found
        self.device.on_device_data = on_data
    
    def start_data_collection(self):
        try:
            print(f"Starting {self.device}, press Ctrl-C to finish")
            self.node.start()
        except KeyboardInterrupt:
            print("Closing ANT+ device...")
        except Exception as error:
            print(f"Heart rate monitor process raised exception: {error}")
        finally:
            self.device.close_channel()
            self.node.stop()


if __name__ == "__main__":
    
    hr_tracker = HeartRateTracker()
    hr_tracker.connect_hr_device(device_id=0)
    number_of_tries = 3
    while number_of_tries > 0:
        try:
            hr_tracker.start_data_collection()
        except Exception as error:
            print(f"Heart rate monitor kernel returned the following error: {error}")
            number_of_tries -= 1
        else:
            break
print(hr_tracker.hr_data)