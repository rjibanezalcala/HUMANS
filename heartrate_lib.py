# -*- coding: utf-8 -*-
"""
Created on Thu Sep  7 13:42:41 2023

@author: Raquel
"""
# Heart rate monitor (ANT+ enabled) library
from openant.easy.node import Node
from openant.devices import ANTPLUS_NETWORK_KEY
from openant.devices.heart_rate import HeartRate, HeartRateData
# Timestamps
from datetime import datetime
import pytz
# System operations
import sys
# Delays
from time import sleep
# For heart rate emulation
from random import randint
# For multithreading
from threading import Thread
try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty  # python 2.x

# -----------------------------------------------------------------------------
# This class provides functions for connecting and reading from the heart rate
# device.
class HeartRateTracker:
    def __init__(self, hr_data_container, **kwargs):
        self.device = None  # The device index to connect to
        self.node = None    # The device node data will be streamed to
        self.sys_flags = {
                          'stop': False,   # Signals the hr monitor library to stop collecting data, activated via thread event
                          'active' : False # If true, means that device is active.
                         }
        self.hr_data = hr_data_container # A data container to be returned by join()
        self.verbose = kwargs.get('verbose', False)     # Prints output to console
        self.reconnects = kwargs.get('reconnects', 3)   # Maximum number of attempts to reconnect to the HR device
        self.emulate = kwargs.get('emulate_hr', False)  # Whether to emulate heart rate data (for development without device)
        self.device_id = kwargs.get('device_id', 0)     # If there are more than one devices connected, take the first device by default
        self.timezone = pytz.timezone(kwargs.get('timestamp_timezone', 'UTC')) # Timezone to collect timestamps in
    
    def check_flag(self, flag_type):
        return self.sys_flags[flag_type]
    
    def set_flag(self, flag_type, value):
        if type(value) == bool:
            self.sys_flags[flag_type] = value
            return 0
        else:
            return -1
        
    def connect_hr_device(self, device_id):
        self.node = Node()
        self.node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)
    
        self.device = HeartRate(self.node, device_id=device_id)
        
        self.set_hr_device_callbacks(on_device_found = self.on_found,
                                           on_data = self.on_device_data)
        
    def on_found(self):
        if self.verbose: print(f"Device {self.device} found and receiving...")

    def on_device_data(self, page: int, page_name: str, data):
        if isinstance(data, HeartRateData):
            if self.check_flag('stop'):
                if self.verbose: print("Stop flag has been raised, exiting...")
                self.clean_and_exit()
            data = {'hr': str(data.heart_rate)+' bpm', 'time':self.timezone.localize(datetime.now()).strftime("%a %b %d %H:%M:%S.%f %Y %Z")}
            self.hr_data.append(data)
            # print(f"Heart rate update {data.heart_rate} bpm")
            if self.verbose: 
                print("Device generated:", data)
            
    def set_hr_device_callbacks(self, on_device_found, on_data):
        self.device.on_found = on_device_found
        self.device.on_device_data = on_data
    
    def activate_device(self):
        if not self.emulate:
            number_of_tries = 0
            while (number_of_tries <= self.reconnects):
                try:
                    if self.verbose: print(f"\nAttempt number {number_of_tries} out of {self.reconnects}:\n  Attempting to connect to ANT+ device...")
                    self.connect_hr_device(device_id=self.device_id)
                except Exception as error:
                    number_of_tries += 1
                    if self.verbose: print(f"Heart rate monitor process returned the following error: {error}", "Reconnecting..." if number_of_tries < self.reconnects else "Maximum reconnection attempts exceeded.")
                else:
                    self.set_flag('active', True)
                    print("Device connected!")
                    break
            
            if number_of_tries >= self.reconnects:
                if self.verbose: print(f"Could not connect to device after {self.reconnects} tries. Exiting...")
                self.clean_and_exit()
        else:
            self.set_flag('active', True)
    
    def start_data_collection(self):
        try:
            if self.verbose: print(f"Starting {self.device}, raise stop flag to exit")
            self.node.start()
        except KeyboardInterrupt:
            if self.verbose: print("Closing ANT+ device...")
        except Exception as error:
            if self.verbose: print(f"Heart rate monitor process raised exception: {error}")
        finally:
            self.device.close_channel()
            self.node.stop()
    
    def start_heart_rate_emulation(self):
        try:
            if self.verbose: print("Starting emulation device, raise stop flag to exit")
            while True:
                if self.check_flag('stop'):
                    if self.verbose: print("Stop flag has been raised, exiting...")
                    break
                bpm = str(randint(65,80))
                data = {'hr': bpm+' bpm', 'time':self.timezone.localize(datetime.now()).strftime("%a %b %d %H:%M:%S.%f %Y %Z")}
                self.hr_data.append(data)
                # print(f"Heart rate update {data.heart_rate} bpm")
                if self.verbose:
                    print("Emulation device generated:", data)
                sleep(0.5)
        except KeyboardInterrupt:
            if self.verbose: print("Closing ANT+ device...")
        except Exception as error:
            if self.verbose: print(f"Heart rate monitor process raised exception: {error}")
        finally:
            return
            
    def main_process(self):
        self.activate_device()
        
        try:
            if not self.emulate: self.start_data_collection()
            else: self.start_heart_rate_emulation()
        except Exception as error:
            if self.verbose: print(f"\nData collection process returned with error: {error}")
        finally:
            self.clean_and_exit()
            
    def clean_and_exit(self):
        # Do something to clean up
        self.set_flag('active', False)
        self.set_flag('stop', False)
        return
    
# -----------------------------------------------------------------------------
# This class is a thread wrapper for running the heart rate monitor functions
# as a separate thread concurrently with the main code.
class HRMonitorThread(Thread):
    # Initialise thread parameters
    def __init__(self, name='hr-monitor-thread', **kwargs):
        self.container = [] # Will contain the output data
        self.msg = None
        # Get rest of parameters
        self.records = kwargs.get('records', None)
        self.emulate = kwargs.get('emulate', False)
        self.maximum_tries = kwargs.get('max_reconnects', 3)
        self.device_id = kwargs.get('device_id', 0)
        # Decalre HR device
        self.hr_tracker = HeartRateTracker(verbose=kwargs.get('verbose', True),\
                                           emulate_hr=kwargs.get('emulate_hr', False),\
                                           records=kwargs.get('reconnects', 3),\
                                           hr_data_container=self.container) # Declare heart rate device
        # Initialise thread
        super(HRMonitorThread, self).__init__(name=name)
        self.daemon = kwargs.get('as_daemon', False)
    
    # Override 'run' function, this will run in the thread
    def run(self):
        self.hr_tracker.main_process()
    
    # Use join if thread has a finite execution (f.e. records is some integer)
    # This will wait for the thread to finish and return the result.
    def join(self, *args):
        Thread.join(self, *args)
        return self.container
    
    def start_thread(self):
        self.queue = Queue()
        self.start()
    
    def set_flag(self, **flags):
        for flag, value in flags.items():
            self.hr_tracker.sys_flags[flag] = value if type(value) == bool else False
    
    def check_flags_status(self, flag):
        return self.hr_tracker.sys_flags[flag]

# -----------------------------------------------------------------------------

if __name__ == "__main__":
# Example: Connects to heart rate device and collects data for a few seconds,
# disconnects, and repeats once before stopping the thread and exiting.
    try:
        print("\n[MAIN] Starting thread!\n")
        t = HRMonitorThread(emulate_hr=True, as_daemon=False, verbose=True) # Declare thread wrapper
        t.start_thread()
        print("\n[MAIN] Waiting for device to be active...\n")
        while not t.check_flags_status('active'):
            sleep(1)
        # Wait and stop thread by raising the "STOP" flag.
        print("\n[MAIN] Continuing execution of main...\n")
        sleep(3)
        # Attempt to stop thread
        print("\n[MAIN] Attempting to stop thread...\n")
        t.set_flag(stop=True)
        print("\n[MAIN] Waiting for thread to stop, retreiving data, and exiting...\n")
        print(t.join())
        
        sleep(1)
        
        print("\n[MAIN] Re-starting thread!\n")
        t = HRMonitorThread(emulate_hr=True, as_daemon=False, verbose=True) # Declare thread wrapper
        t.start_thread()
        print("\n[MAIN] Waiting for device to be active...\n")
        while not t.check_flags_status('active'):
            sleep(1)
        # Wait and stop thread by raising the "STOP" flag.
        print("\n[MAIN] Continuing execution of main...\n")
        sleep(3)
        # Attempt to stop thread
        print("\n[MAIN] Attempting to stop thread...\n")
        t.set_flag(stop=True)
        # Send info to thread via the queue
        # print("[Main] Sending 'f'.")
        # t.queue.put(b'f')
        # print("[Main] Sending 'n'.")
        # t.queue.put(b'n')
    except KeyboardInterrupt:
        print("\n[MAIN] Keyboard interrupt detected, stopping thread before exiting main process...\n")
        t.set_flag(stop=True)
    finally:
        print("\n[MAIN] Waiting for thread to stop, retreiving data, and exiting...\n")
        print(t.join())
        sys.exit()
