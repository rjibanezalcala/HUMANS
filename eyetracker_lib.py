# -*- coding: utf-8 -*-
"""
Created on Fri Sep  1 20:20:40 2023
eyetracker_lib.py v0.1
@author: Raquel Ibáñez Alcalá
"""

import tobii_research as tr
from time import sleep
from os import path
from subprocess import run

class EyeTracker:
    def __init__(self, **kwargs):
        self.manager_install_path = kwargs.get('manager_install_path', '')
        self.gaze     = 'not_subscribed'
        self.openness = 'not_subscribed'
        self.user_pos = 'not_subscribed'
        self.flags    = { 'active':False }   # Flags to show device status
        self.my_eyetracker = None
    
    def connect_eyetracker(self, tracker_index=0):
        # Search local system and network for connected eye trackers...
        print("\n  Finding all eye trackers in network...")
        found_eyetrackers = tr.find_all_eyetrackers()

        # Access metadata and print to console.
        print(f"\n  Detected {str(len(found_eyetrackers))} eye trackers in network! Connecting to tracker with index 0...")
        self.my_eyetracker = found_eyetrackers[tracker_index]
        print("    Address: " + self.my_eyetracker.address)
        print("    Model: " + self.my_eyetracker.model)
        print("    Name (It's OK if this is empty): " + self.my_eyetracker.device_name)
        print("    Serial number: " + self.my_eyetracker.serial_number)
        
    def call_eye_tracker_manager(self):
        print("\nCalling Tobii Eye Tracker Manager for calibration routine...\n  App will hang until the Manager is closed.")
        # Calibrate eye tracker using UI, run the exe as a subprocess...
        calibration_process = run(self.manager_install_path)
        # If calibration program reutns a non-zero, raise a CalledProcessError.
        return_code = calibration_process.check_returncode()
        print(f"Manager returned with exit code {return_code}.")
        return  return_code
        
    """ 
    Data callbacks: These functions are called whenever a particular data
        stream has been subscribed to and data are available. 
        # The eye tracker outputs a gaze data sample at a regular interval (30, 60, 120,
        # 300, etc, times per seconds, depending on model). To get hold of this data,
        # you tell the Tobii Pro SDK that you want to subscribe to the gaze data, and
        # then provide the SDK with what is known as a callback function. The callback
        # function is a function like any other, with the exception that you never need
        # to call it yourself; instead it gets called every time there is a new gaze
        # data sample. So, in this callback function, you do whatever it is that you
        # want to do with the gaze data, for example printing some parts of it.
    """
    def gaze_data_callback(self, gaze_data):
        
        self.gaze.append(gaze_data)
    
    def eye_openness_data_callback(self, eye_openness_data):
        
        self.openness.append(eye_openness_data)
        
    def user_position_guide_callback(self, user_position_data):
        
        self.user_pos.append(user_position_data)
    
    def reset_data(self, data_type='all'):
        self.gaze     = 'not_subscribed'
        self.openness = 'not_subscribed'
        self.user_pos = 'not_subscribed'
    
    """
    Subscribe/Unsubscribe: These functions will 'listen in' on particular data
        streams. There are three data streams; gaze, eye openness, and user
        position.
    """
    def subscribe(self, to='all', max_attempts=2):
        expected_in = ['gaze', 'openness', 'position', 'all']
        attempts = 0
        while attempts < max_attempts:
            print(f"[EYE TRACKER] Attempt number {attempts}")
            try:
                if to != 'all':
                    for x in to:
                        print(f"[EYE TRACKER] Subscribing to...{x}")
                        if x == "gaze":
                            self.gaze = []
                            self.my_eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback, as_dictionary=True)
                        elif x == "openness":
                            self.openness = []
                            self.my_eyetracker.subscribe_to(tr.EYETRACKER_EYE_OPENNESS_DATA, self.eye_openness_data_callback, as_dictionary=True)
                        elif x == "position":
                            self.user_pos = []
                            self.my_eyetracker.subscribe_to(tr.EYETRACKER_USER_POSITION_GUIDE, self.user_position_guide_callback, as_dictionary=True)
                        else:
                            raise Exception(f"\nParameter 'to' was not recognised. Received {x}, expected {str(expected_in)}!")
                            break
                else:
                    print("[EYE TRACKER] Subscribing to...all")
                    self.my_eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback, as_dictionary=True)
                    self.my_eyetracker.subscribe_to(tr.EYETRACKER_EYE_OPENNESS_DATA, self.eye_openness_data_callback, as_dictionary=True)
                    self.my_eyetracker.subscribe_to(tr.EYETRACKER_USER_POSITION_GUIDE, self.user_position_guide_callback, as_dictionary=True)
            except Exception as error:
                print(f"[EYE TRACKER ERROR] Could not subscribe to data stream(s) '{to}' due to the following error: {error}\n\nAttempting to unsubscribe and retrying...")
                if self.unsubscribe(frm=to):
                    print("[EYE TRACKER ERROR] Unsubscribe failed! Returning with error code '1'")
                    return 1
                attempts += 1
            else:
                self.flags['active'] = True
                attempts = max_attempts + 1
        return 0
    
    def unsubscribe(self, frm):
        expected_in = ['gaze', 'openness', 'position', 'all']
        try:
            if frm != 'all':
                for x in frm:
                    print(f"[EYE TRACKER] Unsubscribing from...{x}")
                    if x == "gaze":
                        self.my_eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback)
                    elif x == "openness":
                        self.my_eyetracker.unsubscribe_from(tr.EYETRACKER_EYE_OPENNESS_DATA, self.eye_openness_data_callback)
                    elif x == "position":
                        self.my_eyetracker.unsubscribe_from(tr.EYETRACKER_USER_POSITION_GUIDE, self.user_position_guide_callback)
                    else:
                        raise Exception(f"\nParameter 'frm' was not recognised. Received {x}, expected {str(expected_in)}!")
            else:
                print("[EYE TRACKER] Unsubscribing from...all")
                self.my_eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback)
                self.my_eyetracker.unsubscribe_from(tr.EYETRACKER_EYE_OPENNESS_DATA, self.eye_openness_data_callback)
                self.my_eyetracker.unsubscribe_from(tr.EYETRACKER_USER_POSITION_GUIDE, self.user_position_guide_callback)
        except Exception as error:
            print(f"[EYE TRACKER ERROR] Could not unsubscribe to data stream(s) '{frm}' due to the following error: {error}\n\nExiting program...")
            return 1
        else:
            self.flags['active'] = False
            return 0

""" Library usage example """
if __name__ == "__main__":
    # Setup -----------------------------------------------------------------------
    USER = ''
    INSTALL_PATH = r'C:\Users\{USER}\AppData\Local\Programs\TobiiProEyeTrackerManager\TobiiProEyeTrackerManager.exe'
    tracker = EyeTracker(manager_install_path=path.abspath(INSTALL_PATH))
    tracker.connect_eyetracker()
    # END Setup -------------------------------------------------------------------
    
    # # Calibrate eye tracker using UI, run the exe as a subprocess...
    tracker.call_eye_tracker_manager()
    
    # Now we just need to tell the SDK that this function should be called when
    # there is new gaze data. And tell the eye tracker to start tracking! This is
    # done by one single call to the subscribe_to function of the eye tracker
    # object:
    tracker.subscribe(to=['gaze'])
    
    # The first input parameter is a constant that tells the SDK that it's gaze
    # data we want. There are other constants for the other types of data that you
    # can get from the eye tracker (see SDK reference guide for details).
    # The second parameter is the callback function that we just defined, and the
    # third parameter tells the SDK that we want the data as a dictionary.
    # That's all that's needed to get gaze data from the eye tracker, so now just
    # let the program print the data for a while:
    sleep(5)
    
    print(tracker.gaze)
    print(tracker.openness)
    print(tracker.user_pos)
    
    # Now that we have collected the gaze data that we want, we should let the eye
    # tracker (and SDK) know that we're done. You do this by unsubscribing from
    # gaze data, in almost the same way as you subscribed:
    tracker.unsubscribe(frm=['gaze'])

# %%
# Tracker data format
# Gaze - (x, y) for each eye
# Pupil diam. - actual, internal physical size of the pupil and not the size it
#   appears to be when looking at the eye from the outside, estimated in mm,
#   both eyes)
# Eye openness -  the diameter in millimeters of the largest sphere that can be
#   fitted between the upper and lower eyelids. Upper and lower eyelids are
#   defined by the contrast lines between the sclera and the lashes/lid
#   structure. For each eye.
# Time - In the Tobii Pro SDK there are two kinds of time stamps: device time
#   stamp and system time stamp. The source of the device time stamp is the
#   internal clock in the eye tracker hardware while the system time stamp uses
#   the computer on which the application is running as the source.
#   Time stamps in the Tobii Pro SDK are generally given in microseconds.
# Validity codes - each individual kind of data relating to the eye is provided
#   with its own validity code which can only have one out of two possible
#   values: valid or invalid.