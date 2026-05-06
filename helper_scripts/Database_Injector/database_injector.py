# -*- coding: utf-8 -*-
"""
Created on Tue Nov 21 12:50:26 2023

database_injector.py v0.1.1
@author: Raquel Ibáñez Alcalá
"""
# %% Imports
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

#%% ------------------------ Class definition -----------------------------------
class Injector:
    def __init__(self, target_directory=r"../../data", settings=r"../../bin/settings.ini"):
        self.wd            = path.abspath(target_directory)    # Directory where data is located
        self.settings_path = path.abspath(settings)            # Relative path to the app's settings file

        self.ds_ts_format = r"%m/%d/%Y %I:%M:%S %p"      # Dataset timestamp format
        self.fn_ts_format = r"%m_%d_%Y_%H_%M"            # File name timestamp format
        self.db_ts_format = r"%a %b %d %H:%M:%S.%f %Y"   # Database timestamp format
        self.pb_ts_format = r"^%a %b %d .* %Y"           # Partial database timestamp format for 'LIKE' matching
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
        
        self.credentials = self.pt.parse_ini(section='postgresql', eval_datatype=True, exclude_keys=[])
        self.db_settings = self.pt.parse_ini(section='app_settings', eval_datatype=True, exclude_keys=exclusions)
        self.tz = timezone(self.db_settings['timestamp_timezone'])
        if self.credentials is None:
            return -1
        else:
            return 0
    
    def generate_dir_map(self):
        return self.pt.read_dir_map(self.wd, restrict_numeric=True, get_full_filenames=True)
    
    def fetch_user_records(self, id_num, select=['trial_start', 'trial_end', 'trial_index', 'subjectidnumber', 'tasktypedone', 'next_story_index'], equals={}, like={}, matches={}):
        return self.dt.get_user_records(id_num, self.credentials, self.db_settings['data_table'], select, equals, like, matches)
        
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

#%% ---------------------------- Main code --------------------------------------
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
    argparser.add_argument('-d', '--datafolder', dest='data_dir', help='Location of data in disk (default: %(default)s)', default=path.abspath(path.join(getcwd(),r"../../data")) )
    argparser.add_argument('-i', '--ini', dest="set_dir", help='Location of app settings file (default: %(default)s)', default=path.abspath(path.join(getcwd(),r"../../bin/settings.ini")) )
    argparser.add_argument('-g', '--group_by', dest='group_by', help='Indicates timestamps should be grouped, whether by trial, story, or session (default: %(default)s)', default='trial')
    argparser.add_argument('-cwd', '--usecurrentdir', action="store_true", dest="usecwd", help='Use the current working directory as --datafolder (default: %(default)s)', default=False)
    argparser.add_argument('-dnm', '--donotmoveprocessedfiles', action='store_true', dest='donotmove', default=False, help='prevents the program from moving already processed files to the _PROCESSED_FILES directory, also program will also not create the directory (default: %(default)s)')
    # Now, parse the command line arguments and store the 
    # values in the 'args' variable
    args = argparser.parse_args()

#%% ------------------------------ Setup ----------------------------------------
    
    inj = Injector(target_directory=getcwd() if args.usecwd else args.data_dir,
                   settings=args.set_dir)       # Declare injector class
    
    inj.get_server_settings()                   # Parse server credentials and settings
    dir_map = inj.generate_dir_map()            # Generate a directory map
    root_dir = inj.wd                           # Working directory (data folder)

#%% --------------------------- Start upload ------------------------------------
    
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
                    # user_data = inj.fetch_user_records(user_id, like={'trial_start':\
                    #             datetime.strftime(datetime.strptime(start_time, inj.ds_ts_format), inj.pb_ts_format)})
                    date_pattern = datetime.strftime(datetime.strptime(start_time, inj.ds_ts_format), inj.pb_ts_format)
                    user_data = inj.fetch_user_records(user_id, matches={'trial_start':date_pattern})
                    
                    if not user_data is None:
                        print(f"\n[Injector] Retrieved {len(user_data)} records where date matches pattern '{date_pattern}'.", end="")
                        # Parse fetched user records and sort fetched user records
                        for record_num, record in enumerate(user_data):
                            # Parse trial index and next story index as int
                            record.update({'trial_index': int(record['trial_index']),
                                           'next_story_index': int(record['next_story_index'])})
                            # Parse timestamps so they can be used to filter
                            # the HRM data.
                            new_record = inj.parse_time_strings(record, inplace=False)[1]
                            user_data[record_num] = new_record
                        # Finally, sort the fetched records.    
                        user_data = sorted(user_data, key=lambda d: (d['next_story_index'], 
                                                                     d['tasktypedone'],
                                                                     d['trial_index'])
                                           )
                        print(f" Total elapsed time of fetched records is {int((user_data[-1]['trial_end'] - user_data[0]['trial_start']).total_seconds() // 60)} minutes.")
                        
                        # Create time bounds to filter the HRM data with.
                        # This can be done in one of three ways, depending on
                        # what the -g parameter is set to.
                        # "story" will segment the HRM dataset by the first
                        # story's trial_start through its last trial_end.
                        # "session" will simply take the first trial_start
                        # and last trial_end of the fetched records,
                        # "trial" will segment by each trial question by taking
                        # the trial_start and trial_end timestamps of each
                        # record.
                        #
                        # Note: All time bounds are generated without millisec
                        # information as this does not exist in the HRM
                        # dataset. Moreover, timestamps are offset by 1 second
                        # (-1 for trial_start and +1 for trial_end) to better
                        # capture the block of samples within the target group.
                        
                        print(f"\n[Injector] Generating time bounds by '{args.group_by}'...")
                        for_upload = []
                        time_bounds = []
                        if args.group_by == "story":
                            # Figure out where each story starts and ends
                            story_ranges  = []
                            current_story = (user_data[0]['tasktypedone'], 0)
                            for record_num, record in enumerate(user_data):
                                # As soon as the tasktypedone (story) changes
                                # from the previous iteration, create the range
                                # and the time bounds.
                                if not record['tasktypedone'] == current_story[0]:
                                    print(f"\n  Time bounds for story {current_story[0]}: ", end="")
                                    story_range = (current_story[1], record_num)
                                    current_story = (record['tasktypedone'], record_num)
                                    story_bounds  = user_data[ story_range[0] : story_range[-1] ]
                                    time_bounds.append( (story_bounds[0]['trial_start'].replace(microsecond=0)-timedelta(0,1),
                                                         story_bounds[-1][ 'trial_end'].replace(microsecond=0)+timedelta(0,1)) )
                                    for_upload.append( {'records'    : story_bounds,
                                                        'time_bounds': time_bounds[-1],
                                                        'time_delta' : int((time_bounds[-1][1] - time_bounds[-1][0]).total_seconds()),
                                                        'hr_data'    : []
                                                        } )
                                    print(f"{for_upload[-1]['time_bounds'][0].strftime(inj.db_ts_format)} - {for_upload[-1]['time_bounds'][1].strftime(inj.db_ts_format)} ({for_upload[-1]['time_delta']} seconds) corresponding to records {story_range[0]} through {story_range[1]}.")
                                elif record_num == len(user_data)-1:
                                    print(f"\n  Time bounds for story {current_story[0]}: ", end="")
                                    story_range = (current_story[1], record_num)
                                    story_bounds  = user_data[ story_range[0] : story_range[-1]+1 ]
                                    time_bounds.append( (story_bounds[0]['trial_start'].replace(microsecond=0)-timedelta(0,1),
                                                         story_bounds[-1][ 'trial_end'].replace(microsecond=0)+timedelta(0,1)) )
                                    for_upload.append( {'records'    : story_bounds,
                                                        'time_bounds': time_bounds[-1],
                                                        'time_delta' : int((time_bounds[-1][1] - time_bounds[-1][0]).total_seconds()),
                                                        'hr_data'    : []
                                                        } )
                                    print(f"{for_upload[-1]['time_bounds'][0].strftime(inj.db_ts_format)} - {for_upload[-1]['time_bounds'][1].strftime(inj.db_ts_format)} ({for_upload[-1]['time_delta']} seconds) corresponding to records {story_range[0]} through {story_range[1]}.")
                                else:
                                    continue
                            print(f"\n[Injector] Detected {len(time_bounds)} stories in fetched records.")
                                
                        elif args.group_by == "session":
                            # Take the first trial_start and last trial_end of
                            # the fetched records.
                            time_bounds.append( (user_data[0]['trial_start'].replace(microsecond=0)-timedelta(0,1),
                                                 user_data[-1][ 'trial_end'].replace(microsecond=0)+timedelta(0,1)) )
                            for_upload.append( {'records'    : user_data,
                                                'time_bounds': time_bounds[-1],
                                                'time_delta' : int((time_bounds[-1][1] - time_bounds[-1][0]).total_seconds()),
                                                'hr_data'    : []
                                                } )
                            print(f"\n  Time bounds for session: {for_upload[-1]['time_bounds'][0].strftime(inj.db_ts_format)} - {for_upload[-1]['time_bounds'][1].strftime(inj.db_ts_format)} ({for_upload[-1]['time_delta']} seconds).")
                        
                        elif args.group_by == "trial":
                            # Get the trial_start and trial_end of each record.
                            for record in user_data:
                                time_bounds.append( (record['trial_start'].replace(microsecond=0)-timedelta(0,1),
                                                     record[ 'trial_end' ].replace(microsecond=0)+timedelta(0,1)) )
                                for_upload.append( {'records'    : [record],
                                                    'time_bounds': time_bounds[-1],
                                                    'time_delta' : int((time_bounds[-1][1] - time_bounds[-1][0]).total_seconds()),
                                                    'hr_data'    : []
                                                    } )
                                print(f"\n  Time bounds for trial {for_upload[-1]['time_bounds'][0].strftime(inj.db_ts_format)} - {for_upload[-1]['time_bounds'][1].strftime(inj.db_ts_format)} ({for_upload[-1]['time_delta']} seconds).")

                        # Begin filtering hr data by the time bounds
                        print("\n[Injector] Segmenting HRM dataset using generated time bounds...")
                        filtered_hr = []
                        for indx, item in enumerate(for_upload):
                            print(f"  Upper bound: {item['time_bounds'][0]}\n  Lower bound: {item['time_bounds'][1]}\n  Time elapsed: {item['time_delta']} seconds")
                            # Filter HRM data by each of the defined bounds to
                            # extract only the samples whose timestamps fall
                            # within the bounds.
                            filtered_hr = inj.filter_dataset_by_time(df_hr, 'time', item['time_bounds']).to_dict(orient='records')
                            
                            # Convert all hr dataset timestamps to database format
                            for x in filtered_hr:
                                # Convert to datetime
                                inj.parse_time_strings(x, inplace=True)
                                # Then convert to database timestamp string
                                inj.parse_time_stamps(x, inj.db_ts_format,
                                                      inplace=True,
                                                      localize=True)
                            
                            if len(filtered_hr) != 0:
                                print(f"  Isolated {len(filtered_hr)} HRM samples from dataset!")
                                if args.supervised:
                                    input("\n  > Press enter to continue to upload, or enter Ctrl+C to cancel script.\n")
                                for_upload[indx]['hr_data'] = filtered_hr
                            else:
                                print(f"  No records in file {file} matched generated time bounds.")
                            
                            if not indx == len(for_upload)-1:
                                print("  Continuing to the next generated time bounds...\n")
                            else:
                                print("\n  Finished!\n")
                        # Finish filtering hr data
                        
                        # Upload filtered HR data to database...
                        # The result of this processing should be a list of
                        # dicts each with key 'records' containing records
                        # fetched from the database, 'time_bounds' containing
                        # the time bounds used for the HRM data segmentation,
                        # and 'hr_data' containing the corresponding segment.
                        # The following will update all records under 'records'
                        # writing the list in the 'hr_data' key to the
                        # 'hr_data' column in the database.
                        # If grouping was done by trial, each trial will have
                        # a different segment of HRM data, but if grouping was
                        # done by story, all records that were detected to
                        # belong to the same story will have a copy of the
                        # story-wide segment of HRM data generated. This is
                        # similar to when grouping is done by session, but at a
                        # the scale of a session.
                        if not args.donotupload:
                            print("[Injector] Updating database with segmented HRM data...")
                            for item in for_upload:
                                for record in item['records']:
                                    up_rows = inj.dt.update_row(inj.db_settings['data_table'], inj.credentials, 'heart_rate_data', str(dumps(item['hr_data'])), where_equals=record)
                                print(f"\n  >>> Updated {up_rows} row(s) <<<") if up_rows >= 1 and not up_rows is None else print("\n   Could not update database records.")
                        else:
                            print("\n   >>> Data was not uploaded to database <<<")

                        if not args.donotmove:    
                            print(f"\n  Moving {file}\n  from '{ root_dir }\\{ user_id }'\n  to '{processed_dir}'")
                            move(f"{ root_dir }\\{ user_id }\\{ file }", f"{processed_dir}\\{ file }")
                    else:
                        print(f"\n  No user records were found for query. Skipped file {file}.\n")
            else:
                print(f"\n  File {file} is not a CSV file. Skipped file.\n")

# ----------------------------- End upload ------------------------------------
                    
                    
                    
            
    
    
    
    
    