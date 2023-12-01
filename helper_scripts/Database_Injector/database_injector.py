# -*- coding: utf-8 -*-
"""
Created on Tue Nov 21 12:50:26 2023

database_injector.py v0.0.1
@author: Raquel Ibáñez Alcalá
"""

from datetime import datetime, date, timedelta
from pytz import timezone
from os import path, getcwd, mkdir
from shutil import move
from copy import deepcopy
import pandas as pd
import re
from json import dumps
# from dateutil.tz import tzlocal
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from textwrap import dedent
from hdma_tools import ParserTools
from hdma_tools import DatabaseTools
import sys

# ------------------------ Class definition -----------------------------------
class Injector:
    def __init__(self, target_directory=r"../../data", settings=r"../../bin/settings.ini"):
        self.wd            = path.abspath(target_directory)    # Directory where data is located
        self.settings_path = path.abspath(settings)            # Relative path to the app's settings file

        self.ds_ts_format = r"%m/%d/%Y %I:%M:%S %p"      # Dataset timestamp format
        self.fn_ts_format = r"%m_%d_%Y_%H_%M"            # File name timestamp format
        self.db_ts_format = r"%a %b %d %H:%M:%S.%f %Y"   # Database timestamp format
        self.pb_ts_format = r"%a %b %d"                  # Partial database timestamp format for 'LIKE' matching
        self.tz           = None                         # Timezone to which database timestamps are localised
        
        self.pt = ParserTools(settings_path=self.settings_path)
        self.dt = DatabaseTools()
        
        self.credentials = None
        self.db_settings = None
        ### datetime.astimezone(datetime.now(tzlocal()), pytz.timezone('UTC'))
    
    def get_server_settings(self):
        exclusions = ['auto_create_table','enable_consecutive_users', 'data_upload', 'unique_ids_from', 'next_story_from',\
        'minimum_topics', 'questions_per_story', 'ignore_legacy_story_data', 'randomise_relation_levels', 'relation_levels',\
        'relation_level_stories', 'validate_stories', 'approach_avoid', 'benefit_benefit', 'cost_cost', 'moral',\
        'multi_choice', 'probability', 'social']
        
        self.credentials = self.pt.parse_ini(section='postgresql', eval_datatype=False, exclude_keys=[])
        self.db_settings = self.pt.parse_ini(section='app_settings', eval_datatype=False, exclude_keys=exclusions)
        self.tz = timezone(self.db_settings['timestamp_timezone'])
        if self.credentials is None:
            return -1
        else:
            return 0
    
    def generate_dir_map(self):
        return self.pt.read_dir_map(self.wd, restrict_numeric=True, get_full_filenames=True)
    
    def fetch_user_records(self, id_num, select=['trial_start', 'trial_end', 'trial_index', 'subjectidnumber', 'tasktypedone'], equals={}, like={}):
        return self.dt.get_user_records(id_num, self.credentials, self.db_settings['data_table'], select, equals, like)
        
    def find_time_data(self, dataframe):
        result = list()
        
        # For every row (as a named tuple) in the dataframe...
        for row in dataframe.itertuples():
            # Convert row to dictionary.
            dict_row = row._asdict()
            # Then, for every key in that dictionary...
            for key, value in dict_row.items():
                # If the key-value pair is a timestamp...
                if isinstance(value, date):
                    if key not in result:
                        # Record the key name into list
                        result.append(key)
        return result
    
    def parse_time_strings(self, record, inplace=False, localize=False):
        if inplace:
            # Parse date strings to datetime and save directy into the input
            data = record
        else:
            data = deepcopy(record)
            
        fmts = (self.ds_ts_format, self.fn_ts_format, self.db_ts_format if localize else self.db_ts_format+r' %Z')
        parsed = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if localize:
                    # Grab timezone from timestamp
                    tz_string = re.search(' [A-Z]{3}$', value)
                    tz = timezone(tz_string.group(0).strip()) if not tz_string is None else self.tz
                for fmt in fmts:
                    try:
                        ts = tz.localize(datetime.strptime(value.replace(tz_string.group(0), ''), fmt)) if localize\
                            else datetime.strptime(value, fmt)
                    except ValueError:
                        pass
                    except Exception:
                        pass
                    else:
                        parsed.append((key, value, ts, fmt))
                        data[key] = ts          
        
            return parsed if len(parsed) > 0 else None, data
        
        else:
            print("[Injector] Can only parse 'dict' instance.")
            return None, None
        
    def parse_time_stamps(self, record, fmt, inplace=False, localize=False):
        if inplace:
            # Parse date strings to datetime and save directy into the input
            data = record
        else:
            data = deepcopy(record)
            
        parsed = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if localize:
                    # Grab timezone from timestamp
                    tz = self.tz
                try:
                    ts = datetime.strftime(tz.localize(value, fmt), fmt+r' %Z') if localize\
                        else datetime.strftime(value, fmt)
                except ValueError:
                    pass
                except Exception:
                    pass
                else:
                    parsed.append((key, value, ts, fmt))
                    data[key] = ts          
        
            return parsed if len(parsed) > 0 else None, data
        
        else:
            print("[Injector] Can only parse 'dict' instance.")
            return None, None
        
    def filter_dataset_by_time(self, data, column, time_bounds):
        if not isinstance(time_bounds, tuple):
            raise Exception(f"[Injector] 'time_bounds' must be of instance 'tuple' but {type(time_bounds)} was given.")
        if isinstance(data, pd.DataFrame):
            data_cp = deepcopy(data)
            data_cp[column] = pd.to_datetime(data_cp[column], format=self.ds_ts_format)
            mask = (data_cp['time'] >= time_bounds[0]) & (data_cp['time'] <= time_bounds[1])
            filtered = data.loc[mask]
            
            return filtered

# class MyParser(ArgumentParser):
# # Overwrites argparser error behaviour.
#     def error(self, message):
#         sys.stderr.write('error: %s\n' % message)
#         self.print_help()
#         sys.exit(2)
                
    
# ------------------------ End class definition -------------------------------

# ---------------------------- Main code --------------------------------------
if __name__ == "__main__":

# ------------------------- Parse cmd arguments -------------------------------

    # Define the parser
    argparser = ArgumentParser(formatter_class=RawDescriptionHelpFormatter,
                               description=dedent('''\
     ----------------------------------
    |  H.U.M.A.N.S. database injector  |
    |----------------------------------|
    |                                  |
    | This script is designed to take  |
    | an external CSV file containing  |
    | heart rate data and upload it to |
    | the same database the main       |
    | HUMANS app uploads its data to.  |
    |                                  |
    | Data must be formatted as a CSV  |
    | file delimited by the ';' char-  |
    | acter. and must contain a 'time' |
    | column formatted as:             |
    |   mm/dd/yyyy hh:mm:ss am/pm      |
    |                                  |
    | The script will run through each |
    | entry, fetch records from the    |
    | of the first timestamp in the    |
    | dataset, and filter the dataset  |
    | to only records between the      |
    | trial_start and trial_end time-  |
    | stamps stored in the database.   |
    | It will then upload these rec-   |
    | ords to its matching database    |
    | entry under the column name      |
    | heart_rate_data.                 |
    |                                  |
     ----------------------------------
     '''))
    
    # Declare an argument, using a default value if the argument 
    # isn't given
    argparser.add_argument('-s', '--supervised', action="store_true", dest='supervised', help="whether to wait for user input upon processing each file (default: %(default)s)", default=False)
    argparser.add_argument('-dnu', '--donotupload', action="store_true", dest='donotupload', help="if true, data is not uploaded to database (default: %(default)s)", default=False)
    argparser.add_argument('-d', '--datafolder', dest='data_dir', help='Location of data in disk (default: %(default)s)', default=r"../../data")
    argparser.add_argument('-i', '--ini', dest="set_dir", help='Location of app settings file (default: %(default)s)', default=r"../../bin/settings.ini")
    argparser.add_argument('-cwd', '--usecurrentdir', action="store_true", dest="usecwd", help='Use the current working directory as --datafolder (default: %(default)s)', default=False)
    argparser.add_argument('-dnm', '--donotmoveprocessedfiles', action='store_true', dest='donotmove', default=False, help='prevents the program from moving already processed files to the _PROCESSED_FILES directory, also program will also not create the directory (default: %(default)s)')
    # Now, parse the command line arguments and store the 
    # values in the 'args' variable
    args = argparser.parse_args()

# ------------------------------ Setup ----------------------------------------
    
    inj = Injector(target_directory=getcwd() if args.usecwd else args.data_dir,
                   settings=args.set_dir)       # Declare injector class
    
    inj.get_server_settings()                   # Parse server credentials and settings
    dir_map = inj.generate_dir_map()            # Generate a directory map
    root_dir = inj.wd                           # Working directory (data folder)

# --------------------------- Start upload ------------------------------------
    
    # Find all files (with extension) in the target folder defined by the 
    for user_id, files in dir_map.items():
        if not args.donotmove:
            processed_dir = path.abspath(f"{root_dir}\\{str(user_id)}\\_PROCESSED_FILES")
            try:
                mkdir(processed_dir)
            except FileExistsError:
                pass
        for file in files:
            # If file is a csv file...
            if not (re.search("\.csv$", file) is None):
                print(f"\n[Injector] Reading file {file} ......", end="")
                try:
                    # Try to read the file into dataframe
                    df_hr = pd.read_csv(f"{ root_dir }\\{ user_id }\\{ file }", delimiter=';')
                    start_time = df_hr['time'].iloc[0]  # Extract first timestamp
                    # end_time   = df_hr['time'].iloc[-1] # Extract last timestamp
                except Exception:
                    # If file is not formatted correctly, skip it.
                    print(" failed!")
                    print(f"   File {file} must be a CSV with columns 'hr' and 'time'. File is in a different format. Skipped file.\n")
                else:
                    print(" success!")
                    # Get user data where trial_start matches the day, month, and year recorded in the heart rate data
                    user_data = inj.fetch_user_records(user_id, like={'trial_start':\
                                datetime.strftime(datetime.strptime(start_time, inj.ds_ts_format), inj.pb_ts_format)})
                    if not user_data is None:
                        for record_num, record in enumerate(user_data):
                            # Attempt to parse all the timestamps in the user data as datetimes
                            new_record = inj.parse_time_strings(record, inplace=False)[1]
                            time_bounds = (new_record['trial_start'].replace(microsecond=0)-timedelta(0,1), new_record[ 'trial_end' ].replace(microsecond=0)+timedelta(0,1))
                            
                            # Filter heart rate data and extract only the heart rate data that falls between
                            # the trial_start and trial_end timestamps
                            filtered_hr = inj.filter_dataset_by_time(df_hr, 'time', time_bounds).to_dict(orient='records')
                            
                            # Convert all hr dataset timestamps to database format
                            for x in filtered_hr:
                                inj.parse_time_strings(x, inplace=True)                                 # Convert to datetime
                                inj.parse_time_stamps(x, inj.db_ts_format, inplace=True, localize=True) # Then convert to database timestamp string
                            
                            print(f"\nRetrieved user record #{record_num+1} (assuming story #{int(record_num/16)+1} in session):")
                            for k, v in record.items(): print(f"   {k}: {v}")
                            print("Generated time bounds:")
                            for k, v in enumerate(time_bounds): print(f"   {k}: {v}")
                            print(f"Filtered_hr dataset from {file}:")
                            for k, v in enumerate(filtered_hr): print(f"   {k}: {v}")
                            
                            if len(filtered_hr) != 0:
                                if args.supervised:
                                    input("\n> Press enter to continue to upload, or enter Ctrl+C to cancel script.\n")
                                print("Continuing to next retrieved user record...")
                            else:
                                print(f"   No records in file {file} matched generated time bounds, skipping...")
                        
                            # Final step, upload filtered HR data to database
                            if not args.donotupload:
                                print("\n   Updating heart rate records in database...")
                                up_rows = inj.dt.update_row(inj.db_settings['data_table'], inj.credentials, 'heart_rate_data', str(dumps(filtered_hr)), where_equals=record)
                                print(f"\n   >>> Updated {up_rows} row(s) <<<") if up_rows >= 1 and not up_rows is None else print("\n   Could not update database records.")
                            else:
                                print("\n   >>> Data was not uploaded to database <<<")
                            # -- END RECORDS 'FOR' LOOP --
                        if not args.donotmove:    
                            print(f"\n   Moving {file}\n   from '{ root_dir }\\{ user_id }'\n   to '{processed_dir}'")
                            move(f"{ root_dir }\\{ user_id }\\{ file }", f"{processed_dir}\\{ file }")
                    else:
                        print(f"\n   No user records were found for query. Skipped file {file}.\n")
            else:
                print(f"\n    File {file} is not a CSV file. Skipped file.\n")

# ----------------------------- End upload ------------------------------------
                    
                    
                    
            
    
    
    
    
    