"""
Human Decision Making App v32.4.4
09/October/2023 updated 06/Nov/2025
@authors: Lara Rakocevic and Raquel Ibáñez Alcalá
"""
## Webserver-related imports
from flask import Flask, render_template, redirect, request, session, flash, url_for, template_rendered, make_response, send_from_directory
from flask_session import Session
#from flask_limiter import Limiter
#from flask_limiter.util import get_remote_address
from markupsafe import Markup
from waitress import serve
## Utility imports
import re
from ast import literal_eval
import itertools
from random import shuffle, randint, sample
import time
from subprocess import Popen
import json
from copy import deepcopy
import os
#import fnmatch
import psycopg2
import pandas as pd
from shutil import copy2
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
from configparser import ConfigParser as cfgp
from argparse import ArgumentParser
from secrets import token_hex
## Custom libraries
from eyetracker_lib import EyeTracker
from heartrate_lib import HRMonitorThread
from pdf_signer import PDFSigner

# -------------------------- Configure flask session --------------------------
app = Flask(__name__, static_folder='static', template_folder='templates')
# Delcare rate limiter to prevent DDoS or server overload;
# Deactivate this when debugging...
# limiter = Limiter(
#     get_remote_address,
#     app=app,
#     default_limits=["5 per day"] )
# Create a secret key to protect client side sessions. The secret key is needed
# to decode cookies information transfered to and from the host.
app.secret_key = token_hex(32)
app.config["SESSION_PERMANENT"] = False # Session data is deleted after session expires
app.config["SESSION_TYPE"] = "filesystem" # Session data is stored in the host
# Initialise the app with server-side sessions to handle user data
Session(app)
# -----------------------------------------------------------------------------

# ------------------------------ App functions --------------------------------
def parse_ini(filename='bin/settings.ini',
              section='postgresql',
              eval_datatype=False):
# Returns settings from ini file as dictionary.

    # Create a parser
    parser = cfgp()
    # Read config file
    parser.read(filename)

    # Find the appropriate section, defaults to postgresql
    db = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception('\nSection {0} not found in the {1} file'.format(section, filename))

    if eval_datatype:
        for key, value in db.items():
            if value.isnumeric():
                db[key] = literal_eval(value)
            elif value.startswith('['):
                db[key] = literal_eval(value)
            elif value.startswith('$'):
                db[key] = os.environ.get(value.split('$')[-1])
            
    return db

def without_keys(d, keys):
        return {x: d[x] for x in d if x not in keys}

def read_topic_table(file='Human DM Topics.xlsx'):
# Retrieves the relationship between topics, task types, and story IDs from
# Excel file. Returns a dictionary that contains this information where the
# top-level keys are each topic. Each of these keys will contain a dictionary
# where each key-value pair is task type and the stories that correspond
# to that task type.

    # Read Excel file
    dftopic = pd.read_excel(file, sheet_name='RefTable', header=0, index_col=0)
    
    def parse_as_list(x):
    # Converts the contents of each input string of comma-separated numbers as 
    # a list string.
        return str(x).replace(" ","").split(',')
    # Apply the above function to the whole retreived dataframe. This will
    # convert each cell in the dataframe as a list string.
    dftopic = dftopic.applymap(parse_as_list)
    # Add a topic ID row. The topic ID will be dependent on the table read from
    # the input Excel file.
    newrow = {}
    for key in dftopic.columns:
        newrow.update({key:1+dftopic.columns.get_loc(key)})
    dftopic = pd.concat([dftopic, pd.DataFrame(data=newrow, index=['topic_id'])])

    # Convert dataframe to dictionary for ease of access.
    relations = dftopic.to_dict()

    return relations

def read_dir_tree(rootdir='stories/task_types'):
# Returns the structure of the 'stories/task_types' directory as a dictionary.
    
    dir_map = {}
    # Get the task types directories as a list.
    task_types = os.listdir(rootdir)
    
    for key in task_types:
        # Get the directories inside each task type directory as a list.
        dirs = os.listdir(rootdir+'/'+key)
        if len(dirs) > 0:
            # If the task type directory is populated...
            for i in range(len(dirs)):
                # Take only the story number from the directory names...
                dirs[i] = dirs[i].split('_')[-1]
        # ...then populate the dictionary with 'task type': 'stories
        # in that task type'.
        dir_map.update({key: dirs})

    return dir_map

def validate(theoretical, real, inplace=False):
# Validates that the contents of the 'theoretical' dictionary exist in the
# 'real' dictionary. Useful to check that stories described in the story
# relations table exist in the actual app. Returns a copy of the 'theoretical'
# dictionary where all the values that do not exist in 'real' have been removed

    if inplace:
        validated = theoretical
    else:
        validated = deepcopy(theoretical)
        
    for mkey, sdict in validated.items():
        for key, target in sdict.items():
            if key!='topic_id':
                validated_list = [ x for x in target if x in real[key.replace('-','_').lower()] ]
                validated[mkey][key] = validated_list
    
    return validated

def query_database(query, credentials):
        try:
            data = []
            conn = psycopg2.connect(**credentials)
            cursor = conn.cursor()
            cursor.execute(query, data)
            # Execute query
            cursor.execute(query)
            # Fetch all results
            raw_data = cursor.fetchall()
            # Close connection
            cursor.close()
            conn.close()
            
            # Check if anything came back
            if raw_data:
                # Create a list of keys from the table headers in the database
                keys = [i[0] for i in cursor.description]
                # And prepare to parse the data.
                data_row = dict()
                data_table = list()
                row_index = 0
                # cell_index = 0
                # Place all fetched rows into list of dictionaries
                for row in raw_data: # For each row fetched...
                    for i,item in enumerate(row): # Then for each item in the row...
                        # Update the row dictionary with a key/value pair using the list of keys created before
                        data_row.update({keys[i]: item})
                        # Then move on to the next item
                        # cell_index += 1
                    # When done with this row, append the resulting dictionary to the list
                    data_table.append(data_row)
                    # Then empty the row dictionary
                    data_row = dict()
                    # And move on to the next row
                    row_index += 1
                    
                return data_table
            
            else:
                # If no results, return nothing
                return None
        
        except (Exception, psycopg2.DatabaseError) as error:
            print("\nQuery did not complete successfully.\n"+str(error))
            
            return False

def import_demdata(subjectid, credentials, exclude_keys=['num_stories', 'next_story_index']):
    # Queries database to extract demographic data from the input subject id
    # number. Returns the database's response.
    
    dem_keys =  [ 'num_stories',
                  'hunger',
                  'tired',
                  'pain',
                  'stress',
                  'sex',
                  'genderid',
                  'menstruation',
                  'age',
                  'weight',
                  'race',
                  'ethnicity',
                  'relationship_status',
                  'sexual_orientation',
                  'education',
                  'college',
                  'major',
                  'exercise',
                  'exercise_time_min',
                  'exercise_time_max',
                  'caffeine',
                  'nicotine',
                  'alcohol',
                  'vis_media',
                  'hobbies',
                  'next_story_index',
                  'pref_stories',
                  'story_order'
                ]
    
    demdata = {}
    try: 
        for key in dem_keys:
            if not key in exclude_keys:
                # Build query. Get unique records where the necessary data is contained
                sql_qry = f"""SELECT DISTINCT ({key}) FROM { app_settings['data_table'] }\
                    WHERE subjectidnumber='{str(subjectid)}'"""
                # Query database
                raw_data = query_database(sql_qry, credentials)
                # Store last result in dictionary
                demdata.update(raw_data[len(raw_data)-1])
            else:
                demdata.update({ key: 0 })
    except Exception as error:
        print("\nCould not import demographic data due to error:", error)
        
        return None
    else:
        print("\nUser's demographic info was successfully imported from database!")
        return demdata

def create_data_dir(pid):
    path = os.getcwd()
    dir_to_create = os.path.abspath(f"{path}/data/{str(pid)}")
    try:
        os.mkdir(dir_to_create)
    finally:
        return dir_to_create

def parse_demdata(data, subjectid):
    # Parses demographic data returned by 'import_demdata()' and generates a
    # dictionary where the keys correspond to the demographic data text file
    # format.
    
    # db_to_dem = { 'gender':'sex',
    #               'age_range':'age',
    #               'hungry':'hunger',
    #               'tired':'tired',
    #               'in_pain':'pain',
    #               'story_prefs':'pref_stories',
    #               'task_order':'story_order'
    #              }
    try:
        # Parse certain values so they can be manipulated.
        data['vis_media'] = literal_eval(data['vis_media'])
        data['hobbies'] = literal_eval(data['hobbies'])
        data['pref_stories'] = literal_eval(data['pref_stories'])
        data['story_order'] = literal_eval(data['story_order'])
    # Converts all elements in list into ints (removed due to new format being
    # only strings).
    # data['story_prefs'] = list(map(int, data['story_prefs'].keys()))
    # data['story_prefs'] = str(sorted(data['story_prefs']))
    
    # Begin parsing:
        path = create_data_dir(subjectid)
        
        with open(path+"\demographic_info.txt", 'w') as f: 
            for key, value in data.items():
                # If not at the last key...
                if key != list(data.keys())[-1]:
                    # Follow line with a newline.
                    # f.write('%s: %s\n' % (db_to_dem[key], value))
                    f.write('%s: %s\n' % (key, value))
                else:
                    # Otherwise don't follow line with anything.
                    # f.write('%s: %s' % (db_to_dem[key], value))
                    f.write('%s: %s' % (key, value))
        
    except Exception as error:
        print('\nCould not parse demographic data, exception raised:', error)
        
        return None
    
    else:
        print(f"\nSuccessfully parsed user's demographic information; you may find it in { path }.")
        return (path, data)

def replace_demdata(user, target_entries, make_backup=True):
# Makes a backup and replaces the demographic data entries indicated by the
# keys in (target_entries) in the user's demographic_info.txt with each key's
# value. Returns the path to the modified file.
    path = os.getcwd()
    data_dir = path + "/data/" + str(user)

    # Create backup of old file if it doesn't exit.
    if make_backup:
        if not os.path.exists(data_dir+"/demographic_info_old.txt"):
            copy2(data_dir+"/demographic_info.txt", data_dir+"/demographic_info_old.txt")
    
    # Open the original file
    with open(data_dir+"/demographic_info.txt", 'r') as f:
        data = f.readlines()
    # Search the document from the bottom up for each entry in target_entries
    for i in range(len(data)-1, -1, -1):
        for key, value in target_entries.items():
            # Replace the entries only if the match the keys
            if data[i].startswith(key):
                if i != len(data)-1:
                    data[i] = f"{ key }: { str(value) }\n"
                else:
                    data[i] = f"{ key }: { str(value) }"
    # Replace everything in the original file with the new information.
    with open(data_dir+"/demographic_info.txt", 'w', errors=app_settings.get('encoder_error', 'ignore')) as f:
        f.writelines(data)
    
    return data_dir+"/demographic_info.txt"
    
def get_story_info(search_term, dictionary):
# Since story blurbs were replaced with topics, it is necessary to know what
# topic each story belongs to. This can be done by searching the
# story_relations dictionary. This function will accept a term coming directly
# from the story order in the format '/{task_type}/story_{story number}'. It
# then breaks the search term up and uses it to find the topic the story is
# about. The search returns topic_id, a numerical representation of the topic,
# 'topic', the topic description, 'task_type', the type of task the story is
# and 'story', the story itself as just the story number.

    task_search = search_term.split('/')[1]
    task_search = task_search.replace('_', '-').title().replace(' ', '-')
    story_search = search_term.split('/')[-1]
    story_search = story_search.split('_')[-1]
    
    result = {}
    
    for key in dictionary:
        for x in dictionary[key][task_search]:
            if int(x) == int(story_search):
                result.update({ 'topic_id': dictionary[key]['topic_id'],
                                'topic': key,
                                'task_type': search_term.split('/')[1],
                                'story': story_search })
    
    return result

def get_blurbs(data):
    opt_dict={}
    for key, values in data.items():
        opt_dict.update({ values['topic_id']: key })
    
    return opt_dict

def get_new_id(reference_from='database'):
    
    expected_refs = ['database', 'local', 'file']
    if reference_from == 'database':
        sql_qry = f"SELECT DISTINCT(subjectidnumber) FROM { app_settings['data_table'] } ORDER BY subjectidnumber"
        data = []
    
        conn = psycopg2.connect(**server)
        cursor = conn.cursor()
        cursor.execute(sql_qry, data)
    
        raw_data = cursor.fetchall()
    
        cursor.close()
        conn.close()
        
        unique_ids = set([ row[0] for row in raw_data ])
        
    elif reference_from == 'local':
        path = os.getcwd()
        path += "/data/" 
        unique_ids = set([ int(x) for x in re.findall("\d+", ' '.join(os.listdir(path))) ])
    elif reference_from == 'file':
        pass # Haven't done this yet
    
    else:
        raise Exception(f"\nParameter 'reference_from' was not recognised. Received {reference_from}, expected {str(expected_refs)}!")
        
    while True:
        subjectidnumber = str(randint(10000,99999))
        if subjectidnumber not in unique_ids:
            break

    return subjectidnumber

## Functions start getting messy here, revise? Namely, make them less dependent
## on globally declared variables where possible (f.e. remove implicit
## use of Session object and app settings).

def get_story_order(subjectidnumber, ignore_legacy_story_data=0, validate_only=False, to_validate=[]):
# Validates the story order from the user's demographic info. Returns a
# dictionary with the story order and the STO_CH flag which signals that the
# story order needs to be changed (if it is in an incompatible format).
    if not validate_only:
        # This will hopefully reduce the number of senseless file reads.
        filename = f"data/{ subjectidnumber }/demographic_info.txt"
        with open(filename) as f:
            lines = f.readlines()
            story_order = lines[-1]
            story_order_split = story_order.split(": ")
            order = story_order_split[1]
        story_order = literal_eval(order)
    else:
        if isinstance(to_validate, list):
            story_order = to_validate
        else:
            story_order = literal_eval(str(to_validate))
    
    result = {}
    
    # Check the format of the user's story data. Check if the list elements are numeric (legacy story data),
    # if this returns the same list, then the user's story data is in the old format.
    if (len([ s for s in story_order if str(s).isnumeric() ]) == len(story_order)):
        if ignore_legacy_story_data:
            result.update( { 'STO_CH': 1, 
                             'story_order': [] } )
            print("\nStory data for this user was found to be formatted for a legacy version of the DM app; story order" +\
                  f" and preferences have been reset and will be re-generated. This can be turned off in { os.path.abspath('bin/settings.ini') }"+\
                  " under 'ignore_legacy_story_data'.")
            return result
        else:
            result.update( { 'STO_CH': 0,
                             'story_order': [ f"/approach_avoid/story_{ str(s) }" for s in story_order ] } )
            print("\nStory data for this user was found to be formatted for a legacy version of the DM app; story order" +\
                  f" and preferences have been adapted to the format needed by this version. This can be turned off in { os.path.abspath('bin/settings.ini') }"+\
                  " under 'ignore_legacy_story_data'.")
            return result
    else:
        result.update( { 'STO_CH': 0,
                         'story_order': story_order } )
        return result


def get_starting_story_indx(subjectidnumber, stories_in_session, reference_from='database', db_method='count'):
    expected_refs = ['database', 'local']
    
    if db_method not in ['count', 'direct']:
        print("\nMethod entered in parameter 'db_method = {db_method}' does not match an expected value, defaulting to 'count' instead.")
        db_method = 'count'
    
    num_stories_completed = None
    max_story_indx = None
    if reference_from == 'database':
        # If referencing from the database with 'count', the starting index
        # will be obtained by getting a RAW COUNT OF STORIES THAT HAVE BEEN
        # COMPLETED. This can cause a discrepancy with the next_story_index
        # parameter, which is retrieved from the demographic info. Use 'direct'
        # instead if this becomes an issue.
        try:
            if db_method == 'count':
                sql_qry = f"""SELECT COUNT(DISTINCT tasktypedone) FROM { app_settings['data_table'] } WHERE subjectidnumber = '{str(subjectidnumber)}'"""
            elif db_method == 'direct':
                sql_qry = f"""SELECT MAX(DISTINCT next_story_index::INTEGER) FROM { app_settings['data_table'] } WHERE subjectidnumber = '{str(subjectidnumber)}'"""
            
            print(f"\nMaking a connection to database with query {sql_qry}...")
            data = []
        
            conn = psycopg2.connect(**server)
        
            cursor = conn.cursor()
            cursor.execute(sql_qry, data)
        
            raw_num_stories = cursor.fetchone()
            print(f"Retrieved {raw_num_stories}.")
        
            cursor.close()
            conn.close()
            
            num_stories_completed = int(raw_num_stories[0]) if raw_num_stories is not None else 0
            
            if db_method=='count': num_stories_completed -= 1
            
        except Exception as error:
            print(f"\nStarting story index could not be retreived from database due to error: {error}.\nAttempting to read from local file...")
            try:
                num_stories_completed = int(get_demographic_info(subjectidnumber)['next_story_index'])
            except Exception as error:
                print(f"\nStarting story index could not be retreived from local file, exception raised: {error}\n")
            else:
                print(f"\nRetrieved starting story index: {num_stories_completed}.\n")
        else:
            print(f"\nRetrieved starting story index: {num_stories_completed}.\n")
    
    elif reference_from == 'local':
        try:
            num_stories_completed = int(get_demographic_info(subjectidnumber)['next_story_index'])
        except Exception as error:
            print(f"\nStarting story index could not be retreived from local file, exception raised: {error}\n")
        else:
            print(f"\nRetrieved starting story index: {num_stories_completed}.\n")
    else:
        raise Exception(f"\nParameter 'reference_from' was not recognised. Received {reference_from}, expected {str(expected_refs)}!\n")
    
    max_story_indx = num_stories_completed + int(stories_in_session)
    return (num_stories_completed, max_story_indx)
    
def choose_prefs(pref_dict):
    
    pref_dict = {int(k):int(v) for k,v in pref_dict.items()}
    vals = sorted(list(pref_dict.values()))

    max_diff = 0
    index_combos = [i for i in itertools.combinations(range(0,6), 2)]

    best_diff_list = [] 
    for c in index_combos:
        ind1, ind2 = c
        copy_vals = deepcopy(vals)
        del copy_vals[ind1]
        del copy_vals[ind2-1]

        new_diffs = [abs(e[1] - e[0]) for e in itertools.permutations(copy_vals, 2)]
        new_diff = sum(new_diffs)/len(new_diffs)

        if new_diff > max_diff: 
            max_diff = new_diff
            best_diff_list = copy_vals

    prefs = [k for (k,v) in pref_dict.items() if v in best_diff_list]

    return prefs

def choose_questions(sesh):
    story_num_overall  = sesh['story_num_overall']
    task_type          = sesh['task_type']
    story_num          = sesh['story_num']
    reward_prefs       = sesh['reward_prefs']
    cost_prefs         = sesh['cost_prefs']
    relationship_level   = sesh['relationship_level']
    
    print(f"\nChoosing questions for current story: { story_num_overall }.")    # Should help with debugging
    path = os.path.abspath(f"stories/task_types{story_num_overall}/questions.txt")
    txt = open(path, encoding=app_settings.get('txt_encoding', 'utf-8'), errors=app_settings.get('encoder_error', 'ignore')).read()
    lines = txt.split("\n")
    lines = [line.strip() for line in lines if (line != '' and line != ' ')]
    quest_dict = {}
    # Pattern to match all sentences, regardless of punctuation (curly brace included for debugging with example stories).
    pattern = re.compile(r'([A-Z0-9][^\.!?}]*[\.!?}])', re.M)
    for l in lines:
        l = l.replace("’", "'")
        # linelist = l.split("?") 
        # question = linelist[0] + "?"
        linelist = ['', '']
        linelist[0] = ' '.join(pattern.findall(l)) # Find all sentences in the question
        linelist[1] = re.findall('\(.*?\)', l)[-1]  # Find everything in parenthesis and take the last element.
        question = linelist[0]
        if task_type == 'social':
            if app_settings['randomise_relation_levels'] and story_num in app_settings['relation_level_stories']:
                print(f"\nRandomising relationship levels in question {linelist[1]}")
                question, _ = replace_all(question, app_settings['relation_levels'], replace_with=relationship_level)
        RC = re.findall("\d+", linelist[1]) # Take only the numeric values in this part of the string.
        # RC will contain a variable length list of string numbers. A length of
        # 4 will more than likely indicate that the current task is the
        # multi-choice task. This is the only task type where the questions are
        # tagged as (RxCy RaCb). I want to consider all posibilities though!
        keytup = ()
        for x in RC:
            keytup = keytup + (int(x),)
        quest_dict.update({ keytup: question })

    # print('\n[choose_questions] quest_dict', quest_dict)
    print('\n[choose_questions] quest_dict', list(quest_dict.keys()))

    # Cost-cost and benefit-benefit tasks only have one set of prefs; I delete
    # the other set of prefs since these variables will likely contain the
    # prefs from a previous task. BB, CC, and multi-choice tasks will also
    # need the cost/reward permutations done differently.
    if task_type == 'benefit_benefit':
        rewards = choose_prefs(reward_prefs)
        costs = []
        relevant_keys = list(itertools.product(rewards, repeat=2))
    elif task_type == 'cost_cost':
        rewards = []
        costs = choose_prefs(cost_prefs)
        relevant_keys = list(itertools.product(costs, repeat=2))
    else:
        rewards = choose_prefs(reward_prefs)
        costs = choose_prefs(cost_prefs)
        relevant_keys = list(itertools.product(rewards, costs, repeat=(2 if task_type=='multi_choice' else 1)))

    # print('\n[choose_questions] reward prefs', reward_prefs)
    # print('[choose_questions] cost_prefs', cost_prefs)
    # print('\n[choose_questions] relevant keys', relevant_keys)
    # print('\n[choose_questions] rewards', rewards)
    # print('[choose_questions] costs', costs)
    
    # Since the permutations above may yield keys that don't exist in the
    # list of question tags, only take the ones that are found in the list.
    relevant_qs = { key: quest_dict[key] for key in relevant_keys if key in list(quest_dict.keys()) }

    q_list = list(relevant_qs.items())
    shuffle(q_list)
    
    # Adding this because for the task types below, the 12 preference questions
    # yield 26 question results.
    if task_type in ['cost_cost', 'benefit_benefit']:
        q_list = sample(q_list, app_settings['questions_per_story'])

    return q_list

def get_demographic_info(subjectidnumber, auto_parse=False):
    filename = f'data/{subjectidnumber}/demographic_info.txt'
    dem_dict = {}
    with open(filename) as f:
        for line in f:
            (key, val) = line.split(": ")
            dem_dict[key] = val.strip()
    
    if auto_parse:
        # Parse certain values so they can be manipulated.
        dem_dict['vis_media'] = literal_eval(dem_dict['vis_media'])
        dem_dict['hobbies'] = literal_eval(dem_dict['hobbies'])
        dem_dict['pref_stories'] = literal_eval(dem_dict['pref_stories'])
        dem_dict['story_order'] = literal_eval(dem_dict['story_order'])

    return dem_dict

def exists(dest_table):
    print(f"\n  Checking if table '{ dest_table }' exists in database...")
    
    # Build query
    query = "SELECT EXISTS ("\
            + "SELECT FROM "\
            + "pg_tables "\
            + "WHERE "\
            + "schemaname = 'public' AND "\
            + "tablename  = '"+dest_table+"'"\
            + ");"

    conn = psycopg2.connect(**server)

    cursor = conn.cursor()
    cursor.execute(query)
    resp = cursor.fetchone()
    cursor.close()
    
    if resp[0]:
        print("  Destination table '"+dest_table+"' exists!\n")
    else:
        print("  Destination table '"+dest_table+"' does not exist.\n")
        
    return resp[0]

def write_trial_to_db(current_question, dec=None, trial_start=None, trial_end=None, record_path=False, exclude_keys=[]):    
    task_type = session['task_type']
    path_start = trial_start[-1] if isinstance(trial_start, tuple) and record_path else None
    path_end = trial_end[-1] if isinstance(trial_end, tuple) and record_path else None
    trial_start = trial_start[0] if isinstance(trial_start, tuple) else trial_start
    trial_end = trial_end[0] if isinstance(trial_end, tuple) else trial_end
    
    if not task_type in ['multi_choice']:
        r, c = current_question
    else:
        r1, c1, r2, c2 = current_question
    
    if trial_start is not None:
        # trial_elapsed = time.mktime(trial_end) - time.mktime(trial_start) 
        trial_elapsed = trial_end - trial_start
        
        # Re-format timestamps...
        # trial_start = time.asctime(trial_start)
        # trial_end = time.asctime(trial_end)
        trial_start = trial_start.strftime("%a %b %d %H:%M:%S.%f %Y %Z")
        trial_end = trial_end.strftime("%a %b %d %H:%M:%S.%f %Y %Z")
        print(f"\nTrial started {trial_start}\nTrial ended {trial_end}\nTrial elapsed {trial_elapsed}\n")
    else:
        trial_elapsed, trial_end, trial_start = 0, 0, 0

    # Get subject's info, including id number and their answers.
    # dem_dict = get_demographic_info(subjectidnumber)
    dem_dict = deepcopy(session)
    dem_dict.update({ 'tasktypedone' : session['story_num_overall'],
                      'reward_prefs' : str(session['reward_prefs']),
                      'cost_prefs'   : str(session['cost_prefs']),
                      'cost_level'   : c if not task_type in ['multi_choice'] else [c1, c2],
                      'reward_level' : r if not task_type in ['multi_choice'] else [r1, r2],
                      'decision_made': dec,
                      'trial_start'  : trial_start if path_start is None else ';'.join([trial_start, path_start]),
                      'trial_end'    : trial_end if path_end is None else ';'.join([trial_end, path_end]),
                      'trial_elapsed': trial_elapsed,
                      'eye_tracker_data': {'gaze_data': eyetracker.gaze if eye_settings['use_eyetracker'] else None,\
                                           'eye_openness_data':eyetracker.openness if eye_settings['use_eyetracker'] else None,\
                                           'user_position_data':eyetracker.user_pos  if eye_settings['use_eyetracker'] else None},
                      #'heart_rate_data' : hr_monitor.container
                    })
    
    sql_insert = f"INSERT INTO { app_settings['data_table'] }("
    to_insert = ()
    placeholders = ""
    i = 0
    for key in dem_dict:
        if key not in exclude_keys:
            start = ', ' if i != 0 else ' '
            sql_insert += start+str(key)+""
            to_insert += (str(dem_dict[key]),)
            placeholders += start+r"%s"
            i += 1
    sql_insert += f" ) VALUES ( {placeholders} );"
    
    # print(f"\nQuerying database: {sql_insert}\n\nWith values: {to_insert}")
    
    conn = None

    try:
        print('\nMaking a connection...')

        conn = psycopg2.connect(**server)
    
        cursor = conn.cursor()
        cursor.execute(sql_insert, to_insert)

        conn.commit()
        cursor.close()

    except (Exception) as error:
        print(f"\nData upload to database failed due to the following error: { error }\n")
    else:
        print('\nData sucessfully uploaded!\n')
    finally:
        if conn is not None:
            conn.close()

def distribute_stories(topics_pool, order, verbose=False):
    # These variables are shared across all clients; declaring them here for
    # clarity.
    global story_relations
    global task_types
    global app_settings
    
    if isinstance(order, list):
        story_order = deepcopy(order)
    else:
        story_order = []
    # Provided that the story_order was not reset...
    if len(story_order) == 0:
        # Check that the subject selected enough stories...
        if len(topics_pool) >= app_settings['minimum_topics']:
            # Randomly sample stories out of the existing stories pool that correspond to
            # subject's topics of interest while also taking into account task type. This
            # will generate paths to the sampled stories and place them in 'story_order'.
            print("Sampling stories for each task type and topic, please wait...")
            try:
                for task in task_types:
                    pool = [] # The pool of stories to sample from. The list will be populated only with stories that fall in the scope of all the topics selected by the user.
                    for topic in topics_pool:
                        pool = pool + story_relations[topic][task]
                        print(f"  Generated story pool for {task} including topic {topic}: {pool}")
                    
                    if verbose:
                        print("Sample from:", pool, end="")
                        print(" (topics:"+str(topics_pool)+")"+" (task:"+task+")")
                        print("Sample size:", app_settings[task.replace('-','_').lower()])
                    
                    print(f"\n  Task type: {task}\n  Stories in pool: {pool}\n  Length of story pool: {len(pool)}\n  Attempting to sample: {app_settings[task.replace('-','_').lower()]}\n\n")
                    samp = sample(pool, app_settings[task.replace('-','_').lower()])
                    # print("Result:", sample)
                    # print("---------")
                    story_order.append([ f"/{task.replace('-','_').lower()}/story_" + i for i in samp ])
                    
            except Exception as error:
                print(f"\nCould not sample stories for the selected task type '{task}', this is usually because the amount of stories to sample for this exceeds the number of stories available for the task type. Please make sure there are enough stories to sample from for the user's selected topics: {topics_pool}")
                print(f"Raised exception: {error}")
                return None
            else:
                print("  Successfully generated story order!\n")
            finally:
                return sum(story_order, []) # story_order will be a list of lists, this joins everything so that the list is uniform.
                #random.shuffle(story_order) # Shuffle the story_order list to create more randomness.
        else:
            # Return back to topic selection screen.
            print(f"\nPlease select at least { app_settings['minimum_topics'] } topics!")
            return None
    else:
        print("\nStory data for this user was found to be formatted for a legacy version of the DM app; the data"+\
              f" has been conserved and reformatted to fit this version's needs. This can be turned off in { os.path.abspath('bin/settings.ini') }"+\
              " under 'ignore_legacy_story_data'.")
        return story_order
    
def write_userdata_to_file(user_id, filename, user_data, end_line='\n', include_keys='all', exclude_keys=[], data_format='records'):
# Writes the contents of 'session' to a file in inside data/'user_id'/'filename'
# as long the keys in data are included in 'include_keys'. Every line will
# terminate with the character(s) indicated by 'end_line'. If 'include_keys'
# is set to 'all' (default), then the whole data dictionary will be written.
# If 'data_format' is set to 'records', the data will be written as
# {data_key}: {data_value}{end_line}, otherwise the data will be written raw.
        
    data = deepcopy(user_data)
    filepath = f"data/{user_id}/{filename}"
    create_data_dir(user_id)

    expected_formats = ['records', 'raw']
    
    if include_keys != 'all':
        keys_to_write = [ key for key in data.keys() if (key in include_keys and not key in exclude_keys) ]
    else:
        keys_to_write = [ key for key in data.keys() if (not key in exclude_keys) ]
    
    if data_format == 'records':
        with open(filepath, 'a') as f:
            for key in keys_to_write:
                f.write(f"{str(key)}: {str(data[key])}{end_line if (keys_to_write.index(key) != len(keys_to_write)-1) else ''}")       
            f.close()
    elif data_format == 'raw':
        for i, key in enumerate(data.keys()):
            if not key in keys_to_write:
                del data[key]
        with open(filepath, 'a') as f:
            f.write(f"str(data){end_line}")
    else:
        raise Exception(f"\nParameter 'data_format' was not recognised. Received {data_format}, expected {str(expected_formats)}!")
            
def start_hr_monitor(**args):
    emulate_hr = args.get('emulate_hr', hr_settings['emulate_device'])
    as_daemon = args.get('as_daemon', hr_settings['run_thread_as_daemon'])
    verbose = args.get('verbose', hr_settings['verbose'])
    timezone = args.get('timezone', app_settings['timestamp_timezone'])
    t = args.get('thread', initialise_device('hrtracker', emulate_hr=emulate_hr, as_daemon=as_daemon, verbose=verbose, timezone=timezone))

    try:
        print("\n[MAIN] Starting HR monitor thread!\n")
        if not t.is_alive():
            t.start_thread()
        print("\n[MAIN] Waiting for device to be active...\n")
        while not t.check_flags_status('active'):
            time.sleep(0.3)
        
    except KeyboardInterrupt:
        print("\n[MAIN] Keyboard interrupt detected, stopping thread before exiting main process...\n")
        t.set_flag(stop=True)
        return None
    else:
        print("\n[MAIN] Continuing...\n")
        return t

def stop_hr_monitor(thr):
    data = None
    try:
        print("\n[MAIN] Attempting to stop thread...\n")
        thr.set_flag(stop=True)
        print("\n[MAIN] Waiting for thread to stop, retreiving data, and exiting...\n")
        data = thr.join()
    except Exception:
        raise
    finally:
        return data
    
def initialise_device(d, **kwargs):
    if d == 'eyetracker':
        global EYE_TRACKER_STATUS
        device = EyeTracker(manager_install_path=kwargs.get('manager_install_path', eye_settings['manager_install_path']))
        try:
            device.connect_eyetracker(kwargs.get('eyetracker_index', eye_settings['eyetracker_index']))
        except Exception as error:
            print(f"\nCould not connect to eye tracker due to error: {error}")
            answer = input(f"\nNo eye trackers were found in the network but 'use_eyetracker' was set to {eye_settings['use_eyetracker']} in settings.\nDo you wish to continue without the heart rate tracker (Y), or exit the session (N)?\n(Y/N) >> ")
            if answer.lower().startswith("y"):
                print("\nDisabling eye tracker and continuing session...")
            elif answer.lower().startswith("n"):
                print("\nStopping app and closing the web server. See you later!\n")
                sys.exit()
        else:
            EYE_TRACKER_STATUS = 1

    elif d == 'hrtracker':
        global HR_TRACKER_STATUS
        emulate_hr = kwargs.get('emulate_hr', hr_settings['emulate_device'])
        as_daemon = kwargs.get('as_daemon', hr_settings['run_thread_as_daemon'])
        verbose = kwargs.get('verbose', hr_settings['verbose'])
        tz = kwargs.get('timezone', app_settings['timestamp_timezone'])
        try:
            device = HRMonitorThread(emulate_hr=emulate_hr, as_daemon=as_daemon, verbose=verbose, timestamp_timezone=tz) # Declare thread wrapper and start thread
        except Exception as error:
            print(f"\nCould not initialise heart rate monitor thread. Exception raised: {error}")
        else:
            HR_TRACKER_STATUS = 1
    
    else:
        print("\nNo device to initialise!")
        device = None
    
    return device
    
def replace_all(text, word_bank, replace_from=None, replace_with=None):
# Replace the relationship word with one from the word bank
    try:
        # Remove "'s" from text and split words into list
        split_text = [ re.split(r"'s", word)[0] for word in text.split(' ') ]
        # If any word (where each word has punctuation removed) in the text appears in the word bank, process the text
        if any(word in [ re.sub(r'[^\w\s\d]', '', x).lower() for x in split_text] for word in word_bank):
            if replace_from is None:
                matches = None
                results = []
                # Find all of those words and save them in a list
                for word in word_bank:
                    matches = re.search(r'\b'+re.sub(r'[^\w\s\d]', '', word)+r'\b', ' '.join(split_text), re.IGNORECASE)
                    if not matches is None:
                        matches = matches.group(0).lower()
                        if not matches in results:
                            results.append(matches)
                print(f"\nFound matches in text! {results}")
                # Sample as many words from the word bank as there are results
                pick = sample(word_bank, len(results)) if replace_with is None else replace_with
                print(f"Replacing matching results with: {pick}\n")
                for i, word in enumerate(results):
                    # Replace EXACT match
                    text = re.sub(r'\b'+word+r'\b', pick[i], text)
                    text = re.sub(r'\b'+word.title()+r'\b', pick[i].title(), text)
                
                return text, pick
            else:
                return text.replace(replace_from, replace_with), replace_with
        else:
            return text, None
    except IndexError as e:
        # In some cases, the number of results will be larger than the number
        # of words to replace with, in this case, we simply pick another word
        # and add it to the list.
        print(f"\n[FUNCTION: replace_all()] Encountered the following error when trying to replace words for social task:\n\n{e}\nWhile replacing {results} with {pick}\n\nThis may be because the number of words to replace exceeds the number of words chosen to replace them with. Lists must be of equal lengths.\nSampling another word(s).")
        pick += sample(word_bank, abs(len(results)-len(pick)))
        set_session_params(data={'relationship_level':pick}, op='update', verbose=bool(app_settings.get('verbose', 0)))
        print(f"Replacing matching results with: {pick}\n")
        for i, word in enumerate(results):
            # Replace EXACT match
            text = re.sub(r'\b'+word+r'\b', pick[i], text)
            text = re.sub(r'\b'+word.title()+r'\b', pick[i].title(), text)
        return text, pick

def set_session_params(data=None, op="update", exclude=[], verbose=False):
# Allocates a dictionary in memory to save data into the flask-session data
# structure.
    expected_op = [r'set/reset',r'update']
    if op == "set/reset":
        sesh = {}
        if isinstance(data, list):
            for item in data:
                # To session data, add every key in data if data is a list.
                # Populate items with None. This ensures that keys correspond
                # to data table column names if data is a list of column names
                # from /bin/db_cols.json.
                if item not in exclude:
                    sesh.update({str(item): None})
            # Finally, add items that pertain to app function and are not
            # uploaded to the database.
            sesh.update({
                # Update data table-relevant entries to initialize them to the
                # correct data type.
                'story_relevance': {},
                'trial_start': (None, None),
                'trial_end': (None, None),
                # Performance entries
                'num_stories':0,          # The number of stories to be viewed this session
                'current_story_indx':0,   # The story_order index of the current story
                'next_story_index': 0,
                'trial_index': 0,
                'story_num_overall':None, # The story identifier string of the current story
                'max_story_indx':None,
                'task_type': None,
                'story_num': None,
                'relevant_questions':[],
                'exclude': [],            # Keys to exclude from database uploads and demographic data writes.
                # Flags
                'STO_CH':0,         # Flag that indicates that story order had to be changed.
                'NEED_RESET':0,     # Flag to reset all global parameters for consecutive users.
                })
            data = sesh
        else:
            print("\nPlease pass a list of keys to 'data' to set session parameters.")
            return False
    elif op == 'update':
        # Do not accept None, non-dictionary types, or empty dictionaries
        if data is None or not isinstance(data, dict) or data == {}:
           print(f"\nCannot write '{data}' to session data, please pass a dictionary with data to parameter 'data'.") 
           return False
        else:
            for key in exclude:
                del data[key]
    else:
        print(f"\nValid inputs to parameter 'op' are {expected_op}.")
        return False
          
    
    try:
        print(f"\n{'Updating' if op=='update' else 'Allocating/Resetting'} session parameters{':' if op=='update' else ''}", end="")
        if op=='update' and verbose:
            print("")
            i = 1
            for key, value in sorted(data.items()):
                print(f"{i}. {key}: {value}")
                i += 1
            print("")
        print("..................", end="")
        
        if op=='set/reset':
            session.clear()
            
        session.update(data)
            
    except Exception as e:
        print(f"failed!\nSession data was not written successfully due to error:\n{e}")
        return False
    else:
        print("success!")
        if op=='update' and verbose:
            print("\nSession has been updated to:")
            i = 1
            for key, value in sorted(session.items()):
                print(f"{i}. {key}: {value}")
                i += 1
        else:
            print(f"\nSet { len( list( session.keys() ) ) } entries in session.")
        print("\n")
        return True

def create_data_table(server_settings, table_name, json_path='bin/db_cols.json', exclude_keys=[]):
    """
    Function call to query a PostgreSQL server to create a data table. The
    column names and variable types are read from a JSON structure contained
    in a .json file in '/bin/'. 
    
    Parameters
    ----------
    server_settings: TYPE - Dict
        Dictionary containing server credentials.
    json_path : TYPE - String
        String pointing to a file containing a json structure where each key is
        a column name, and each value is the variable type for that column.

    Returns
    -------
    bool
        Returns True if table was created successfully, or false if an error is
        encountered.

    """
    # Read JSON file and store in dictionary
    try:
        with open(json_path, 'r') as f:
            table_cols = json.load(f)
    except FileNotFoundError:
        print(f"\nNo JSON file found at location '{ json_path }'.")
        return False
    except json.JSONDecodeError:
        print(f"\nUnable to decode JSON file '{ json_path }'. File may not be formatted correctly.")
        return False
    except Exception as e:
        print(f"Could not open JSON file at '{ json_path }' due to error:\n{e}")
        return False
    else:
        query = f"CREATE TABLE { table_name }("
        i = 0
        for key, value in sorted(table_cols.items()):
            if key not in exclude_keys:
                start = ', ' if i != 0 else ' '
                query += f"{ start }{ key } { value }"
                i += 1
        query += r" );"
        
        print(f"\nCreating data table in database with name { table_name } using query { query }...")
        try: 
            conn = psycopg2.connect(**server_settings)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            cursor.close()
        except Exception as e:
            print(f"\nCould not connect to database due to error:\n{e}")
        else:
            return True

def log_template_renders(sender, template, context, **extra):
    """
    Callback function to execute every time a template is rendered
    successfully.
    
    Logs a timestamp when the template was rendered.
    Timestamp is saved to session only if request.path is in the list of
    'observed' paths defined in app_settings.
    ----------
    sender : Flask object
        IDK how to describe this lol.
    template : Template object
        The template that was rendered.
    context : DICT
        A dictionary containing local context. Keys: 'g', 'request', and
        'session'.
    **extra : DICT
        Extra parameters.

    Returns
    -------
    None.
    """
    # timestamp = timezone.localize(datetime.now())
    timestamp = datetime.now(timezone)
    page = request.path
    observed_paths = app_settings.get('observed_urls', tuple( r'/trial' ))
    print(f"[SIGNAL.TEMPLATE_RENDERED] Rendered template {template.name or 'string template'} at timestamp {timestamp} in url {page}")
    
    if page.startswith(observed_paths):
        session['trial_start'] = (timestamp, page)
        session['trial_end'] = (None, None)
        print(f"[SIGNAL.TEMPLATE_RENDERED] Logged 'trial_start'\n Start: {str(session['trial_start'])}\n End: {str(session['trial_end'])}")

def sign_pdf(idno, name, signature, proxysignature=None, stamp_document=True, include_timestamp=True):
    signer = PDFSigner(output_dir=os.path.abspath(f"{os.getcwd()}/data/{idno}"),
                       output_name=f"informed_consent_signed_{idno}",
                       ts_region=app_settings.get('timestamp_timezone', 'UTC'))
    
    if not os.path.isdir(signer.output_dir):
        signer.make_directory()
    
    try:
        document = signer.open_pdf()
        
        # Sign participant's name
        signer.sign_name(document, name, line_index=[0])
        # Sign date in both "Date" lines
        signer.sign_date(document, signer.ts_short, line_index=[2,4])
        # Sign participant's initials
        signer.sign_initials(document, signature, line_index=[1])
        # Sign guardian's initials (if applicable)
        if not proxysignature is None:
            signer.sign_initials(document, proxysignature, line_index=[3])
        # Stamp document to attest that is was signed electronically
        if stamp_document:
            signer.stamp_pdf(document)
        # Add a timestamp
        if include_timestamp:
            signer.writeonpdf(document, datetime.now(signer.ts_region).strftime(signer.ts_format),
                              x=230, y=730, use_selfcoords=False)
        
        signer.save_pdf()
    finally:
        signer.close_pdf()
        del document, signer   
    
# -----------------------------------------------------------------------------

# ------------------------------- Initialize app ------------------------------
print("\nPerforming initial setup operations, please wait...")

# 1. Define global app params; these are not changed throughout the app's
#    lifetime and apply to ALL served clients.
eyetracker = None       # Eyetracker settings
hr_monitor = None       # HRM settings
EYE_TRACKER_STATUS = 0  # Flag to signal whether the eye tracker is ready
HR_TRACKER_STATUS = 0   # Flag to signal whether the HRM is ready
# Story informations, including the "Stories" filesystem
topics = []             # Existing topics.
task_types = []         # Existing task types.
story_relations = {}    # What topic and task type each story correponds to
dir_map = {}            # Will contain the a dictionary structure that describes the contents of 'stories/task_types'.

# 2. Determine the current working directory and scan the "data" folder
wd = os.getcwd()
# Create a 'data' directory if it doesn't exist in case app is run for the
# first time.
if not os.path.isdir( os.path.abspath(wd + '/data' ) ):
    os.mkdir( os.path.abspath(wd + '/data' ) )

# 3. Parse app settings
# Parse bin\settings.ini
server = without_keys( parse_ini(section='postgresql', eval_datatype=True), {} ) # Parse server credentials from ini.
app_settings = without_keys( parse_ini(section='app_settings', eval_datatype=True), {} ) # Parse app settings from ini.
eye_settings = without_keys( parse_ini(section='eye_tracker', eval_datatype=True), {} ) # Parse app settings from ini.
hr_settings = without_keys( parse_ini(section='hr_tracker', eval_datatype=True), {} ) # Parse app settings from ini.
# timezone = pytz.timezone( app_settings.get('timestamp_timezone', 'UTC') )
timezone = ZoneInfo( app_settings.get('timestamp_timezone', 'UTC') )
# Tweak settings
app_settings['exclude_columns'].append('num_stories')
app_settings['observed_urls'] = tuple( fr"{i}" for i in app_settings['observed_urls'] )
if not bool(app_settings['academic_version']):
    # If academic_version is disabled, disable the HRM and eyetracker.
    eye_settings.update( { 'use_eyetracker': 0 } )
    hr_settings.update(  { 'use_hrtracker' : 0 } )
# Parse db_cols.json to figure out what data to upload
try:
    with open('bin/db_cols.json', 'r') as f:
        data_cols = json.load(f)
except Exception as e:
    print(f"\nUnable to parse what data to upload to database, please provide a JSON file with column names in /bin/.\nError when parsing JSON file: {e}")
    sys.exit(1)

# 4. Initialise biometrics hardware
if eye_settings['use_eyetracker']:
    eyetracker = initialise_device('eyetracker')
if hr_settings['use_hrtracker'] and not hr_settings['use_external_app']:
    #hrtracker = initialise_device('hrtracker', emulate_hr=bool(hr_settings['emulate_device']), as_daemon=bool(hr_settings['run_thread_as_daemon']), verbose=bool(hr_settings['verbose']))
    print(f"\nDetected 'use_hrtracker' as {hr_settings['use_hrtracker']} in settings!\n  Please wait while I test that the device can be connected to...")
    try:
        hr_monitor = initialise_device('hrtracker', emulate_hr=bool(hr_settings['emulate_device']), as_daemon=bool(hr_settings['run_thread_as_daemon']), verbose=bool(hr_settings['verbose']), timezone=app_settings['timestamp_timezone'])
        if hr_settings['test_on_startup']:
            start_hr_monitor(thread=hr_monitor)
            hr_monitor.set_flag(data_capture=True, flush_data=False)
            time.sleep(2)
            hr_monitor.set_flag(data_capture=False, flush_data=True)
            datalen = len(hr_monitor.container)
            print(f"\nDevice generated the following dataset:\n{hr_monitor.container}\nWith length {len(hr_monitor.container)}")
            if datalen == 0:
                raise Exception("HeartRateMonitorError: Test returned empty dataset. Check device connection!")
            else:
                del datalen
    except Exception as error:
        print(f"\nCould not connect to heart rate monitor device. Please ensure that the ANT+ antenna is pluggled into the computer!\nError raised: {error}")
        answer = input(f"\nNo heart rate monitors were found in the network but 'use_hrtracker' was set to {hr_settings['use_hrtracker']} in settings.\nDo you wish to continue?\n(Y/N) >> ")
        if answer.lower().startswith("y"):
            print("\nDisabling heart rate tracker and continuing session...")
            HR_TRACKER_STATUS = 0
        elif answer.lower().startswith("n"):
            print("\nStopping app and closing the web server. See you later!\n")
            sys.exit()
    finally:
        # stop_hr_monitor(hr_monitor)
        pass
    
# 5. Check if target data table exists in the database and create one if it
#    doesn't.
if (not exists(app_settings['data_table'])) and app_settings['auto_create_table']:
    if not create_data_table(server, app_settings['data_table'], exclude_keys=app_settings['exclude_columns']):
        sys.exit("\nA valid data table could not be found or created. Please address any errors encountered above and try running the app again.")

# 6. Figure out what stories belong to what topics and task types
story_relations = read_topic_table(file='Human DM Topics.xlsx') # Import relationship between topics, task types, and stories from Excel file.
dir_map = read_dir_tree(rootdir='stories/task_types')   # Get a dictionary representation of the /stories/task_types directory
# Check if all stories exist. Those that don't exist will be deleted from the pool of stories to be sampled for the subject.
if app_settings['validate_stories']:   
    validate(story_relations, dir_map, inplace=True)
# Create a list of topics and task types
topics = list(story_relations.keys())   # Get a list of all the topics
task_types = [ x for x in list(story_relations[sample(list(story_relations.keys()), 1)[-1]].keys()) if x not in ['topic_id'] ] # Get a list of all the task types

# 7. Scan story and questions settings
num_qs_in_story = app_settings['questions_per_story']   # No. of questions selected per story.
total_number_of_stories = 0    # How many stories currently exist (calculated from contents of 'stories/task_types').
for x in dir_map: total_number_of_stories = total_number_of_stories + len(dir_map[x])
min_topics = app_settings['minimum_topics']  # The least amount of topics the user will be allowed to choose.

# 8. Connect the 'log_template_renders' callback to the 'template_rendered'
# signal so the callback executes every time a template is rendered.
template_rendered.connect(log_template_renders, app)
# ----------------------------------------------------------------------------- 

# ----------------------------- Flask routes ----------------------------------
# The following functions and routes will be what gets forked into threads.
# Each client will see their own version of each of these functions and the
# separation into threads will allow client concurrency when the app is run
# from a WSGI server.

# This executes before every HTTP request.
@app.before_request
def before_request():
    """
    Callback function to be executed BEFORE an HTTP request is processed.
    
    Logs a timestamp and saves it to session if, and only if, the page at which
    the request was made (if method is POST), or the previous page is in the 
    list of observed pages (if method is GET).
    
    The timestamp will be saved to session entry 'trial_end'. Entry
    'trial_start' is recorded by the 'log_template_renders' callback.
    
    Returns
    -------
    None.

    """
    timestamp = datetime.now(timezone)
    referrer = request.referrer.split( ':'.join([host_ip, str(host_port)]) )[-1] if not request.referrer is None else 'None'  # The url path from the previous page
    retrival = request.headers['Accept'].split(',')[0] if request.method == 'GET' else None # The content (either html or css) that was downloaded, typically 'text/css' or 'text/html'
    
    if request.path.startswith(app_settings.get('observed_urls', r'/trial')) \
    or referrer.startswith(app_settings.get('observed_urls', r'/trial')):
        if request.method == 'POST':
            session['trial_end'] = (timestamp, request.path)
            print(f"[BEFORE, POST] Logged 'trial_end'\n Start: {str(session['trial_start'])}\n End: {str(session['trial_end'])}\n Elapsed: {str(session['trial_end'][0]-session['trial_start'][0])}")
            print(f"[BEFORE, POST] Timestamp: {timestamp.strftime('%a %b %d %H:%M:%S.%f %Y %Z')} on path {request.path}, referred from { referrer }")
            if app_settings['data_upload'] and not request.path.startswith(r'/trial/'):
                print("[BEFORE, POST] Writing to database...")
                write_trial_to_db((0,0), trial_start=session['trial_start'], trial_end=session['trial_end'], record_path=bool(app_settings.get('record_path', False)), exclude_keys=session['exclude'])

        elif request.method == 'GET' \
        and retrival != r'text/css' \
        and not referrer == 'None' \
        and session['trial_end'][0] is None \
        and not session['trial_start'][0] is None:
            session['trial_end'] = (timestamp, referrer)
            print(f"[BEFORE, GET] Logged 'trial_end'\n Start: {str(session['trial_start'])}\n End: {str(session['trial_end'])}\n Elapsed: {str(session['trial_end'][0]-session['trial_start'][0])}")
            print(f"[BEFORE, GET] Timestamp: {timestamp.strftime('%a %b %d %H:%M:%S.%f %Y %Z')} on path {request.path}, referred from { referrer }, retrieved { retrival }")
            if app_settings['data_upload'] and not request.path.startswith(r'/trial/'):
                print("[BEFORE, GET] Writing to database...")
                write_trial_to_db((0,0), trial_start=session['trial_start'], trial_end=session['trial_end'], record_path=bool(app_settings.get('record_path', False)), exclude_keys=session['exclude'])



# This executes after every HTTP request
# @app.after_request
# def after_request(response):
#     referrer = request.referrer.split( ':'.join([host_ip, str(host_port)]) )[-1] if not request.referrer is None else 'None'  # The url path from the previous page
#     retrival = request.headers['Accept'].split(',')[0] if request.method == 'GET' else None # The content (either html or css) that was downloaded, typically 'text/css' or 'text/html'
#     condition = 'PASS' if ( request.path.startswith(app_settings.get('observed_urls', 'r/trial')) \
#                     or referrer.startswith(app_settings.get('observed_urls', 'r/trial')) ) \
#                     and retrival != r'text/css' \
#                     and not session['trial_end'][0] is None \
#                     and not session['trial_start'][0] is None \
#                     else 'FAIL'
#     print(f"[AFTER, {request.method}] Checking whether to upload data...\n Referrer: {referrer}\n Retrival: {retrival}\n Condition: {condition}\n Start: {str(session['trial_start'])}\n End: {str(session['trial_end'])}")
#     if condition == 'PASS':
#         print(f"[AFTER, {request.method}] Data upload on path {request.path} referred from {referrer}\n Start: {str(session['trial_start'])}\n End: {str(session['trial_end'])}\n Elapsed: {str(session['trial_end'][0]-session['trial_start'][0])}")    
#     return response

# Login
@app.route("/", methods=['GET', 'POST'])
# @limiter.limit()
def login():
    """
    This page will simply handle retreiving user data and setting up a user
    session once the "Log in" button is pressed. Once an answer is submitted
    via POST, the response is evaluated to make sure it is an ID number. If
    the number is not found within the local filesystem, the app will attempt
    to connect to the database to import the data associated with that ID,
    otherwise the data will be retrieved from the local filesystem. Once data
    is imported, the starting story index is determined (either from the local
    user data or the database), and the next story is determined from the story
    order list.
    Flash messages are used here to spawn an alert box at the top of the page
    (included in login.html from message.html using Jinja templates) with the
    purpose of alerting the user of anything important that may need their
    attention to contribute to app responsiveness.
    Redirects to:
        Itself, if log in fails
        /choose_stories, if the story order list needs to be reformated from
            the legacy format.
        /states, if login is successful
    """
    session.clear()
    excluded = app_settings['exclude_columns']
    if request.method == "POST":
        if 'existing_participant' in request.form:    
        # Do the following once the 'Log in' button on the ID form is pressed:
            # Grab the contents of the text field
            subjectidnumber = request.form['subjectidnumber']
            print(request.form)
            # Validate the response
            if not subjectidnumber.isnumeric() and not len(subjectidnumber) == 5:
                print(f"\nAnswer to form '{subjectidnumber}' is not a valid ID number.\n")
                flash("Invalid: Participant ID must be five a 5 digit number.", "danger")
                return redirect(url_for("login"))
            
            print(f"\nValid participant ID retrieved is {subjectidnumber}")
            
            if subjectidnumber not in os.listdir("data"):
            # If the participant ID does not exist in the local filesystem...
                flash(f"Fetching data for ID {subjectidnumber}, please wait...", "info")
                try: 
                    # Import the data related to that ID from the database and parse it.   
                    demographics = import_demdata(subjectidnumber, server)
                    if demographics is None:
                        raise Exception("Importing user data from database failed.")
                except Exception as e:
                    # If this process does not complete, alert the user and stay on page
                    print(f"\nCould not import data for user {subjectidnumber} due to error: {e}\n")
                    flash(f"Invalid: An error occured when loading data for user {subjectidnumber}. Please try a different user ID or select 'I'm a new participant'.", "danger")
                    return redirect(url_for("login"))
                else:
                    # If data is retrieved, save it to session data.
                    print(f"\nSuccessfully retreived data for user ID {subjectidnumber} from database!\n")
                    demographics = parse_demdata(demographics, subjectidnumber)[-1] # Parse data and save it locally
            else:
            # If the data does exist in the local filesystem...
                # Load all of the user's data to the session
                demographics = get_demographic_info(subjectidnumber, auto_parse=True)
            
            # Initialise session data, check the boolean return status of
            # set_session_params()
            if not set_session_params(data=list(data_cols.keys()), op='set/reset', verbose=bool(app_settings.get('verbose', 0)) ):
                flash("Could not initialize a session for user.", "danger")
                return redirect(url_for("login"))
            else:
                # Filter thru session data to figure out what keys NOT to upload to db
                # Find keys present in session that are not in the target database,
                # these keys will not be uploaded to the database.
                differences = list( set(session.keys()) - set(data_cols.keys()) )
                if not differences:
                    # If no differences are found
                    pass
                else:
                    # If differences are found
                    print(f"\nDifferences found between target data location in database and session information:\b{differences}\nThese entries will not be uploaded to database!")
                    excluded += differences
                
                # Validate story order (for compatibility with legacy version of
                # the app).
                story_order = get_story_order(subjectidnumber, ignore_legacy_story_data=app_settings['ignore_legacy_story_data'], validate_only=True, to_validate=demographics['story_order'])
                
                # Begin saving data to session
                demographics.update({ 'subjectidnumber': subjectidnumber,
                                      'trial_index'    : 0 } | story_order) # Joins the two dictionaries, updating the first with the contents of the second
                demographics.update( { 'exclude': excluded } )
                set_session_params( data=demographics, op='update', verbose=bool(app_settings.get('verbose', 0)) )
                
                # Start using session data;
                # Check the STO_CH flag to determine if the user needs to re-make
                # their story order.
                if session['STO_CH']:
                    print("\nRedirecting user to /choose_stories...\n")
                    return redirect("/choose_stories")
                # Otherwise continue as normal
                else:
                    return redirect("/states")
        elif 'new_participant' in request.form:
            # Try to set up a session
            if not set_session_params(data=list(data_cols.keys()), op='set/reset', verbose=bool(app_settings.get('verbose', 0))):
                flash("Could not initialize a session for user.", "danger")
                redirect("/new")
            
            # Create a new id
            if session.get('subjectidnumber', None) is None:
                new_id = get_new_id(reference_from=app_settings['unique_ids_from'])
                print(f"\nCreated user ID: { str(new_id) }.\n")
            
            # Save to session
            set_session_params(data={'subjectidnumber': new_id}, op='update', verbose=bool(app_settings.get('verbose', 0)))
            return redirect( url_for('consent') )
    
    return render_template('login.html')

# Consent form
@app.route("/consent", methods=["GET", "POST"])
def consent():
    """
    Use will be routed here upon pressing the "I'm a new participant" button
    in the login page.
    This page includes a consent form which asks for the participant's name, 
    participant's initials, and, if applicable, the initials of whomever is
    obtaining consent in their stead.
    Inputs are validated upon POST. If inputs are invalid, the page refreshes
    and a message is displayed on top of the page.
    """

    if request.method == "POST":
        data = request.form.to_dict()
        # Validate input: Input must match the following two patterns,
        # otherwise participant is not allowed to continue.
        for key, value in data.items():
            pattern_names = r'^[A-Za-z]+(?:[ -][A-Za-z]+)*$'
            # Pattern explanation: String must start with one or more letters
            # and contain 2 or more all-letter-words separated by a hyphen (-)
            # or a space.
            pattern_initials = r'\b(?:[A-Z]\.?){2,}\b'
            # Pattern explanation: String must be two or more capital letters
            # optionally separated by a period (.).
            
            if not value == '' and not bool( re.search(pattern_names, value) ):
                # If the string does not match this pattern for names, check if
                # it's initials...
                if not bool( re.search(pattern_initials, value) ):
                    print(f"Detected non-compliant string in key '{key}' with value '{value}'")
                    flash("Name and last name fields must have one or more words containing only letters, separated by either a space or a hyphen (-). Initials fields must be only capital letters optionally separated by a period (.).", "danger")
                    return render_template("consent_form.html")                
        
        # Check if the file exists
        if not os.path.exists( os.path.abspath(fr"{os.getcwd()}/data/{session['subjectidnumber']}/informed_consent_signed_{session['subjectidnumber']}.pdf") ):
            sign_pdf(session.get('subjectidnumber'), f"{data['fname']} {data['lname']}", data['initials'],
                     proxysignature=data['proxyinit'] if not data['proxyinit'] == '' or None else None,
                     stamp_document=True, include_timestamp=True)
        
        if 'continue' in request.form:
            return redirect( url_for('new_participant') )
        elif 'download' in request.form:
            path = os.path.abspath( f"{os.getcwd()}/data/{session['subjectidnumber']}" )
            return send_from_directory(path, f"informed_consent_signed_{session['subjectidnumber']}.pdf", as_attachment=True)
        
    return render_template("consent_form.html")

# Page for entering emotional/physiological state information
@app.route("/states", methods=['GET', 'POST'])
def how_feel_pls():
    """
    This function will request the contents of the 'Number of stories'
    drop-down first, validate it (leaving it blank should not be accepted and
    will trigger a pop-up alert), then it will take the state information from
    the sliders as-is. All this happens when hitting the 'Submit' button at the
    bottom of the page. This isnformation will then be saved to the session
    data.
    Redirects:
        Itself, if the number of stories answer is not valid
        /story_num_overall, if the form is submitted successfully
    """
    if request.method == "POST":
        num_stories = request.form.get('num_stories')
        # Get selected amount of stories in session
        if num_stories is None:
            flash("Please select a number of stories from the list", "danger")
            return redirect(url_for("how_feel_pls"))
        else:
            # Use the number of stories already completed and the selected 
            # number of stories to view to figure out the index of the next
            # story. Then, figure out what story is next by referencing the
            # user's story order.
            story_indices = get_starting_story_indx(session['subjectidnumber'], num_stories, reference_from=app_settings['next_story_from'], db_method='direct')
            
            # Redirect user to final_end if no more stories are left.
            if story_indices[0] - 1 >= len(session['story_order']):
                set_session_params(data={
                    'num_stories'   : int(num_stories),
                    'max_story_indx': int( story_indices[-1] ) - 1,
                    'current_story_indx': int( story_indices[0] ) - 1,
                    'next_story_index' : story_indices[0],
                    'story_num_overall': 'None'
                    }, op='update', verbose=bool(app_settings.get('verbose', 0)))
                return redirect(url_for("final_end", story_index=story_indices[0]-1))
            else:
                set_session_params(data={
                    'num_stories'   : int(num_stories),
                    'max_story_indx': int( story_indices[-1] ) - 1,
                    'current_story_indx': int( story_indices[0] ) - 1,
                    'next_story_index' : story_indices[0],
                    'story_num_overall': session['story_order'][int(session['next_story_index'])]
                    }, op='update', verbose=bool(app_settings.get('verbose', 0)))
            
            print("\nNext story found, redirecting user to story context for:")
            print(f"{session['story_num_overall']}\n")
        
        # Get subject's state data and save to session
        feeling = request.form.to_dict()
        set_session_params(data=feeling, op='update', verbose=bool(app_settings.get('verbose', 0)))
        
        # The next page will only be the biometrics page if the app is set to
        # use the biometrics hardware AND the app is set as the academic
        # version. The online version cannot possibly use the hardware.
        if (eye_settings['use_eyetracker'] or hr_settings['use_hrtracker']) and app_settings['academic_version']==1:
            return redirect(url_for("setup_biometrics"))
        else:
            return redirect('/story_num_overall')
    
    return render_template('setup_session.html')

# Page for initialising biometrics hardware
@app.route('/biometrics', methods=['GET', 'POST'])
def setup_biometrics():
    """
    Here we simply initialise both the eye tracker and heart rate monitor (if
    they have been activated in bin/setting.ini). Note that the gloab variables
    used here mean that the settings will be applied to every client's
    sessions.
    """
    global eye_settings
    global eyetracker
    global EYE_TRACKER_STATUS
    global hr_settings
    global hrtracker
    global hr_monitor
    global HR_TRACKER_STATUS
    
    if request.method == 'POST':
        # Re-check app settings to see if biometric devices will be used
        new_eye_settings = without_keys( parse_ini(section='eye_tracker', eval_datatype=True), {} ) # Parse app settings from ini.
        new_hr_settings = without_keys( parse_ini(section='hr_tracker', eval_datatype=True), {} ) # Parse app settings from ini.
        
        if new_eye_settings != eye_settings:
            print("\nEye tracker settings were changed from last session! Reinitialising eye tracker with new settings.")
            eye_settings.update(new_eye_settings)
            EYE_TRACKER_STATUS = 0
            if eye_settings['use_eyetracker']:
                if not eyetracker is None:
                    eyetracker = None
                eyetracker = initialise_device('eyetracker')
        
        if new_hr_settings != hr_settings:
            print("\nHeart rate tracker settings were changed from last session! New settings will be used upon initialisation of heart rate monitoring thread.")
            if not hr_settings['use_external_app']:
                hr_settings.update(new_hr_settings)
                HR_TRACKER_STATUS = 0
                if not hr_monitor is None:
                    if hr_monitor.is_alive():
                        stop_hr_monitor(hr_monitor)
                    hr_monitor = None
            else:
                pass
                
        # Open the heart rate monitor program (non-blocking)
        if hr_settings['use_hrtracker']:
            if not hr_settings['use_external_app']:
                if hr_monitor is None:
                    hr_monitor = initialise_device('hrtracker', emulate_hr=bool(hr_settings['emulate_device']), as_daemon=bool(hr_settings['run_thread_as_daemon']), verbose=bool(hr_settings['verbose']), timezone=app_settings['timestamp_timezone'])    
                if not hr_monitor.is_alive():
                    start_hr_monitor(thread=hr_monitor)
                hr_monitor.set_flag(data_capture=False, flush_data=False)
            else:
                hr_monitor = Popen(hr_settings['external_app_install_path'])
        
        # Open eye tracker manager (blocking)
        if EYE_TRACKER_STATUS:
            print("\nCalling eye tracker manager to initiate calibration!\n")
            flash("Remember to close the eye tracker software before continuing!", "info")
            eyetracker.call_eye_tracker_manager()
         
        return redirect('/story_num_overall')
        
    return render_template('setup_biometrics.html')

@app.route("/new", methods=['GET', 'POST'])
def new_participant():
    excluded = app_settings['exclude_columns']
    subjectidnumber = session['subjectidnumber']
    
    if request.method=="POST":
        args = request.form.to_dict()
        # Grab these in this this way since they're arrays of checkboxes.
        args['vis_media'] = request.form.getlist('vis_media')
        args['hobbies'] = request.form.getlist('hobbies')
        
        # Filter thru session data to figure out what keys NOT to upload to db
        # Find keys present in session that are not in the target database,
        # these keys will not be uploaded to the database.
        differences = list( set(session.keys()) - set(data_cols.keys()) )
        if differences:
            # If differences are found
            print(f"\nDifferences found between target data location in database and session information:\n{differences}\nThese entries will not be uploaded to database!")
            excluded += differences
        
        args.update( {'exclude' : excluded} )
        
        # Update session
        set_session_params(data=args, op='update', verbose=bool(app_settings.get('verbose', 0)))
        
        return redirect(url_for('choose_stories'))
    
    return render_template('give_new_id.html', participant_id=str(subjectidnumber) )

@app.route("/choose_stories", methods=['GET','POST'])
def choose_stories():
    story_order = session['story_order']
    STO_CH = session['STO_CH']
    subjectidnumber = session['subjectidnumber']
    
    # Fetch a list of story topics to display.
    story_blurbs = get_blurbs(story_relations)
    
    if request.method=="POST":
        prefs = request.form.to_dict()
        
        # Get topic preferences as number IDs for each checkbox
        pref_topics = [story_blurbs[int(k)] for (k,v) in prefs.items() if v]
        not_pref_topics = [story_blurbs[int(k)] for k in range(1,len(story_blurbs)+1) if story_blurbs[int(k)] not in pref_topics]
        
        # The amount of selected topics must be at least the minimum indicated
        # in settings.
        if len(pref_topics) < min_topics:
            return render_template("choose_stories_try_again.html", story_blurbs=story_blurbs,\
                                   num_blurbs=len(story_blurbs), prev_yes=[int(k) for (k,v) in prefs.items() if v], min_topics = min_topics)
        
        #print(f"\nUser preferred topics: { pref_topics }\nNon-preferences: { not_pref_topics }")
        
        # Create a story order
        story_order = distribute_stories(pref_topics, session['story_order'])
        if story_order is not None:
            shuffle(story_order)
        else:
            print(f"Could not generate story order for user { session['subjectidnumber'] }. Please see above for error.")
            return redirect(url_for('choose_stories'))
        #print(f"\nUser's generated story order: { story_order }\n")

        ## add back in the rest of the stories at the end
        ## Why??
        # story_order = story_order + not_pref_topics
        
        # If the user was re-routed here because their story preferences had
        # to be remade...
        if STO_CH:
            # Update session
            set_session_params(data = { 'pref_stories': pref_topics,
                                        'not_pref_stories': not_pref_topics,
                                        'story_order': story_order,
                                        # Reset the story index to have them start their stories from
                                        # the first one again.
                                        'current_story_indx': 0,
                                        'next_story_index': 0,
                                        'STO_CH': 0 }, op='update', verbose=bool(app_settings.get('verbose', 0)))
            
            # Make a copy of their demographic data and overwrite 'story order'
            # and 'pref stories' to the new format.
            replace_demdata(subjectidnumber, {'story_order': story_order, 'pref_stories': pref_topics})   
        else:
            # Update session
            set_session_params(data = { 'pref_stories': pref_topics,
                                        'not_pref_stories': not_pref_topics,
                                        'current_story_indx': 0,
                                        'next_story_index': 0,
                                        'story_order': story_order }, 
                               op='update',
                               verbose=bool(app_settings.get('verbose', 0)))
            # print(app_settings['exclude_columns'])
            write_userdata_to_file(subjectidnumber, 'demographic_info.txt',
                                   session,
                                   exclude_keys=session['exclude']\
                                       + ["session_notes", "eye_tracker_data"]\
                                       + ["tasktypedone", "reward_prefs",
                                          "cost_prefs", "cost_level", 
                                          "reward_level", "decision_made", 
                                          "trial_index", "trial_start", 
                                          "trial_end", "trial_elapsed", 
                                          "relationship_level", "story_relevance"],
                                   data_format='records')

        return redirect('/states')

    return render_template('choosing_stories.html', story_blurbs = story_blurbs, num_blurbs = len(story_blurbs), min_topics = min_topics)

# Shows what number story (in the session) the user is at, and the story theme
@app.route('/story_num_overall')
def story_num_refresh():
    story_order = session['story_order']
    story_num_overall  = session['story_num_overall']
    current_story_indx = session['current_story_indx']
    
    # Get the current story
    story_num_overall = story_order[current_story_indx]
    
    # Update session info so these two values are not calculated every. single.
    # time. >:C
    task_type = story_num_overall.strip().split('/')[1]
    story_num = int(story_num_overall.strip().split('/')[-1].split('_')[-1])
    
    # Save session info
    set_session_params(data={
        'story_num_overall': story_num_overall,
        'task_type': task_type,
        'story_num': story_num }, op='update', verbose=bool(app_settings.get('verbose', 0)))
    
    print(f"\nStarting story { story_num_overall }")
    story_info = get_story_info(story_num_overall, story_relations)
    blurb = f"{ story_info['topic'] }"
    print(f"Current topic: { story_info['topic'] } ({ story_info['topic_id'] })\n")
    
    return render_template('story_num.html', number=current_story_indx+1, content=blurb)

# Shows the story context.
@app.route('/context')
def context():
    # Determine the task type to know whether to proceed directly to cost if
    # the task type is cost_cost
    story_num_overall = session['story_num_overall']
    current_story_indx = session['current_story_indx']
    task_type = session['task_type']
    story_num = session['story_num']
    
    print(f"\nCurrent story number: { str(current_story_indx+1) }.\nStory: { story_num_overall }.\n")    # Should help with debugging
    # path = f"stories/story_{story_num_overall}/context.txt"
    path = f"stories/task_types{story_num_overall}/context.txt"
    txt = open(path, encoding=app_settings.get('txt_encoding', 'utf-8'), errors=app_settings.get('encoder_error', 'ignore')).read().replace("’", "'")
    if task_type == 'social':
        if app_settings['randomise_relation_levels'] and story_num in app_settings['relation_level_stories']:
            txt, relationship_level = replace_all(txt, app_settings['relation_levels'])
            set_session_params(data={'relationship_level':relationship_level}, op='update', verbose=bool(app_settings.get('verbose', 0)))
        print(f"replaced word {relationship_level}")
    return render_template('context.html', content=txt, next_prefs=( 'cost' if task_type=='cost_cost' else 'reward' ))

## enter values (+ save), click next -> to cost pref
## enter values (+ save), click next -> to context refresh
@app.route('/prefs/<cost_or_reward>', methods=['GET', 'POST'])
def rank_prefs(cost_or_reward):
    # Fetch story information from session
    current_story_indx = session['current_story_indx']
    story_num_overall = session['story_num_overall']
    task_type = session['task_type']
    story_num = session['story_num']
    relationship_level = session['relationship_level']
    
    print(f"\nCurrent story number: { str(current_story_indx+1) }.\nStory: { story_num_overall }.\n")    # Should help with debugging
    
    # Determine story identifiers and open the correct preferences file.
    path = f"stories/task_types{story_num_overall}/pref_{cost_or_reward}.txt"
    txt = open(path, encoding=app_settings.get('txt_encoding', 'utf-8'), errors=app_settings.get('encoder_error', 'ignore')).read()
    
    # Parse the preference options in the file
    options = txt.split("\n")
    options = [line.strip() for line in options if (line != '' and line != ' ')]
    opt_dict = {}
    for option in options:
        if option != '':
            line = option.split(")")
            opt_num = int(line[0])
            opt_description = line[1].replace("’", "'")
            # Social task types may require additional processing, namely
            # randomizing the social descriptor which defines a relationship
            if task_type == 'social':
                if app_settings['randomise_relation_levels'] and story_num in app_settings['relation_level_stories']:
                    opt_description, _ = replace_all(opt_description, app_settings['relation_levels'], replace_with=relationship_level)
            opt_dict[opt_num] = opt_description.strip()
    
    # Run this once the user submits their answers...
    if request.method == "POST":
        data = request.form.to_dict()
        vals = list(data.values())
        # All entered values must be different, have the user try again if they
        # are not.
        if len(vals) != len(set(vals)):
            # Redirect to try_again if values do repeat
            print(f"Warning: User entered repeated values:\n{vals}\nRendering template '{cost_or_reward}_try_again.html'...\n")
            try_again = f"{cost_or_reward}_try_again.html"
            return render_template(try_again, len = len(options), opt_dict=opt_dict, vals=vals)

        if cost_or_reward == "cost":
            set_session_params(data={'cost_prefs': data}, op='update', verbose=bool(app_settings.get('verbose', 0)))
        else:
            set_session_params(data={'reward_prefs': data}, op='update', verbose=bool(app_settings.get('verbose', 0)))

        return redirect("/prefs/cost") if (cost_or_reward == 'reward' and task_type != 'benefit_benefit') else redirect("/refresh")
    
    html = f"{cost_or_reward}_prefs.html"
    return render_template(html, len = len(options), opt_dict=opt_dict)

## context refresh, click next -> trials
@app.route('/refresh')
def context_refresh():
    current_story_indx = session['current_story_indx']
    story_num_overall = session['story_num_overall']
    task_type = session['task_type']
    story_num = session['story_num']
    relationship_level = session['relationship_level']
    
    print(f"\nCurrent story number: { str(current_story_indx+1) }.\nStory: { story_num_overall }.\n")    # Should help with debugging
    path = f"stories/task_types{story_num_overall}/context.txt"
    txt = open(path, encoding=app_settings.get('txt_encoding', 'utf-8'), errors=app_settings.get('encoder_error', 'ignore')).read().replace("’", "'")
    if task_type == 'social':
        if app_settings['randomise_relation_levels'] and story_num in app_settings['relation_level_stories']:
            txt, _ = replace_all(txt, app_settings['relation_levels'], replace_with=relationship_level)
    set_session_params(data={ 'relevant_questions': choose_questions(session)}, op='update', verbose=bool(app_settings.get('verbose', 0)))
    # session['relevant_questions'] = choose_questions(session)
    return render_template('refresh.html', content=txt)

@app.route('/want_change_prefs', methods=['GET'])
def ask_if_change_prefs():
    task_type = session['task_type']

    return render_template('want_change_prefs.html', next_prefs=( 'cost' if task_type=='cost_cost' else 'reward' ))


# After finishing trials, re-rank the prefs
@app.route('/refresh_prefs/<cost_or_reward>', methods=['GET', 'POST'])
def rank_prefs_again(cost_or_reward):
    current_story_indx = session['current_story_indx']
    story_num_overall = session['story_num_overall']
    task_type = session['task_type']
    story_num = session['story_num']
    relationship_level = session['relationship_level']
    
    print(f"\nCurrent story number: { str(current_story_indx+1) }.\nStory: { story_num_overall }.\n")    # Should help with debugging
    path = f"stories/task_types{story_num_overall}/pref_{cost_or_reward}.txt"
    task_type = story_num_overall.split('/')[1]
    txt = open(path, encoding=app_settings.get('txt_encoding', 'utf-8'), errors=app_settings.get('encoder_error', 'ignore')).read().replace("’", "'")

    options = txt.split("\n")
    opt_dict = {}
    for option in options: 
        if option != '':
            line = option.split(")")
            opt_num = int(line[0])
            opt_description = line[1]
            if task_type == 'social':
                if app_settings['randomise_relation_levels'] and story_num in app_settings['relation_level_stories']:
                    txt, _ = replace_all(txt, app_settings['relation_levels'], replace_with=relationship_level)
            opt_dict[opt_num] = opt_description.strip()

    if request.method == "POST":
        data = request.form.to_dict()
        vals = list(data.values())
        if len(vals) != len(set(vals)):
            try_again = f"{cost_or_reward}_try_again.html"
            return render_template(try_again, len = len(options), opt_dict=opt_dict, vals=vals)

        if cost_or_reward == "cost":
            set_session_params(data={'cost_prefs': data}, op='update', verbose=bool(app_settings.get('verbose', 0)))
        else:
            set_session_params(data={'reward_prefs': data}, op='update', verbose=bool(app_settings.get('verbose', 0)))
        
        if app_settings['data_upload']:
            write_trial_to_db((7,7), exclude_keys=session['exclude'])

        return redirect("/refresh_prefs/cost") if (cost_or_reward == 'reward' and task_type != 'benefit_benefit') else redirect("/trial_end")

    html = f"refresh_{cost_or_reward}_prefs.html"
    return render_template(html, len = len(options), opt_dict=opt_dict)

# Trial page, this page repeats several times.
@app.route('/trial/<loc_trial_num>', methods=['GET', 'POST'])
def trial_html(loc_trial_num):
    subjectidnumber = session['subjectidnumber']
    current_story_indx = session['current_story_indx']
    trial_index = session['trial_index']
    task_type = session['task_type']
            
    tup, q = session['relevant_questions'][trial_index-1]

    # Changing this to a datetime timestamp with timezone data to get
    # microsecond precision and be able to track when timestamps were made.
    # trial_start = timezone.localize(datetime.now())
    # session['trial_start'] = trial_start
    current_question = tup
    
    if request.method == "POST":
        data = request.form.to_dict()
        vals = list(data.values())

        dec = vals[0]
        # trial_end = time.gmtime()
        # trial_end = timezone.localize(datetime.now())
        # session['trial_end'] = trial_end
        
        # Retrieve hr data, stop the data collection, and flush he container
        if HR_TRACKER_STATUS and not hr_settings['use_external_app']:
            session['heart_rate_data'] = deepcopy(hr_monitor.container)
            hr_monitor.set_flag(flush_data=True)
            # participant_data.update({'heart_rate_data': hr_data})
            # print(f"\nUpdated participant data with: {participant_data['heart_rate_data']}\nWith length: {len(participant_data['heart_rate_data'])}\n")

        # Stop collecting eye tracker data before uploading data
        if EYE_TRACKER_STATUS:
            eyetracker.unsubscribe(frm=eye_settings['subscriptions'])        
            
        if app_settings['data_upload']:
            write_trial_to_db(current_question, dec, session['trial_start'], session['trial_end'], record_path=bool(app_settings.get('record_path', False)), exclude_keys=session['exclude'])

        next_trial = trial_index + 1
        next_trial_str = '/trial/'+str(next_trial)
        
        if next_trial < num_qs_in_story:
            set_session_params({'trial_index': next_trial }, op='update', verbose=bool(app_settings.get('verbose', 0)))
            return redirect(next_trial_str)
        else:
            # Update session to point to the next story and reset trial_index
            # and relationship level.
            next_story = int(session['next_story_index']) + 1
            set_session_params(data={ 'current_story_indx': current_story_indx + 1,
                                      'next_story_index'  : str(next_story),
                                      'trial_index' : 0,
                                      'relationship_level': '' },
                               op='update',
                               verbose=bool(app_settings.get('verbose', 0)))
            # Update demographic data file
            replace_demdata(subjectidnumber, { 'next_story_index': str(next_story) }, make_backup=False)
            
            return redirect('/want_change_prefs')
    
    # Start collecting eye tracker data
    if EYE_TRACKER_STATUS:
        eyetracker.subscribe(to=eye_settings['subscriptions'])
    
    if HR_TRACKER_STATUS and not hr_settings['use_external_app']:
        # Start capturing heart rate data
        print("\n\nSetting data_capture flag to TRUE")
        r = 0
        while not hr_monitor.check_flags_status('data_capture'):
            r += 1
            print(f"Try number {r}\n\n")
            hr_monitor.set_flag(data_capture=True)
            time.sleep(0.1)
    
    if task_type in ['multi_choice', 'benefit_benefit', 'cost_cost']:
        split_question = q.split(' or ')
        optn_a = Markup(split_question[0])
        optn_b = Markup(split_question[-1])
        return render_template('trial_a_or_b.html', trial_number=trial_index+1, optn_a=optn_a, optn_b=optn_b)
    else:
        q = Markup(q)
        return render_template('trial_n_y.html', trial_number=trial_index+1, question=q)

# Page where story relevance is requested.
@app.route('/trial_end', methods=['GET','POST'])
def get_story_relevance():
    story_num_overall = session['story_num_overall']
    current_story_indx= session['current_story_indx']
    max_story_indx    = session['max_story_indx']
    next_story_index  = int(session['next_story_index'])
    
    print(f"{current_story_indx}\n{max_story_indx}\n{str(bool(current_story_indx <= max_story_indx))}")

    if request.method == "POST":
        data = request.form.to_dict()
        vals = list(data.values())
        rel = vals[0]
        
        # Update story_relevance dictionary in session this way to not
        # overwrite the previous values
        session['story_relevance'][story_num_overall] = rel

        return redirect('/story_num_overall') if next_story_index <= max_story_indx else redirect('/total_end')

    return render_template('trial_end.html', story_num=current_story_indx)

# Page for adding session notes.
@app.route('/total_end', methods = ['GET', 'POST'])
def total_end():
    task_type  = session['task_type']
    
    if app_settings['data_upload']:
        write_trial_to_db((0,0) if not task_type in ['multi_choice'] else (0,0,0,0), record_path=bool(app_settings.get('record_path', False)), exclude_keys=session['exclude'])

    set_session_params( data={'NEED_RESET': 1}, op='update', verbose=bool(app_settings.get('verbose', 0)))  # Signal that the app parameters need to be reset.
    
    if request.method == "POST":
        data = request.form.to_dict()
        set_session_params(data={ 'session_notes': data }, op='update', verbose=bool(app_settings.get('verbose', 0)))
        if app_settings['data_upload']:
            write_trial_to_db((0,0) if not task_type in ['multi_choice'] else (0,0,0,0), record_path=bool(app_settings.get('record_path', False)), exclude_keys=session['exclude'])
        
        if hr_settings['use_hrtracker'] and not hr_settings['use_external_app']:
            if (not hr_monitor is None) and (hr_monitor.is_alive()):
                stop_hr_monitor(hr_monitor)
        
        # Clear the session.
        set_session_params(data=list(data_cols.keys()), op='set/reset', verbose=bool(app_settings.get('verbose', 0)) )
        
        resp = make_response("Delete cookie")
        resp.set_cookie('session', '', expires=0)
        
        return redirect('/')
    
    return render_template('total_end.html', app_version='academic' if app_settings.get('academic_version', 0)==1 else 'online')

# Page which appears when user logs into app but has completed all their stories.
@app.route('/finished', methods = ['GET', 'POST'])
def final_end():
    task_type = 'None'
    
    if request.method == "POST":
        data = request.form.to_dict()
        set_session_params(data={ 'session_notes': data }, op='update', verbose=bool(app_settings.get('verbose', 0)))
        if app_settings['data_upload']:
            write_trial_to_db((0,0) if not task_type in ['multi_choice'] else (0,0,0,0), record_path=bool(app_settings.get('record_path', False)), exclude_keys=session['exclude'])
                
        # Clear the session.
        set_session_params(data=list(data_cols.keys()), op='set/reset', verbose=bool(app_settings.get('verbose', 0)) )
        
        resp = make_response("Delete cookie")
        resp.set_cookie('session', '', expires=0)
        
        return redirect('/')
    
    return render_template('final_end.html', app_version='academic' if app_settings.get('academic_version', 0)==1 else 'online', completed_stories=session.get('current_story_indx', 0), total_stories=len(session.get('story_order', [])))

# -----------------------------------------------------------------------------

# --------------------- Run this when app.py is executed ----------------------
if __name__ == '__main__':
    
# ----------------------- Parse commandline arguments -------------------------
    # Define the parser
    argparser = ArgumentParser(add_help=False)
    # Declare an argument, using a default value if the argument 
    # isn't given
    argparser.add_argument('-h', '--host', dest='host_ip', default=r'127.0.0.1')
    argparser.add_argument('-p', '--port', dest='host_port', default='5000')
    argparser.add_argument('-md', '--mode', dest='mode', default='dev')
    argparser.add_argument('-v', '--verbose', dest='verbose', default='0')
    argparser.add_argument('-th', '--threads', dest='threads', default='4')
    # Now, parse the command line arguments and store the values in the 'args'
    # variable.
    args = argparser.parse_args()
# -----------------------------------------------------------------------------

# ------------------- Decide what server to run the app in --------------------
    print(f"Running {'Waitress' if args.mode=='prod' else 'Flask'} WSGI server.\n")
    if args.mode=='prod':
        host_ip = args.host_ip
        host_port = int(args.host_port)
        threads = int(args.threads)
        print(f"Forced 'academic_version' from {app_settings['academic_version']} to 0.")
        app_settings.update( { 'academic_version': 0,
                               'verbose': int(args.verbose)} )
        
        print("Waitress")
        serve(app, host=host_ip, port=host_port, threads=threads, url_prefix='/humans-app')
    elif args.mode=='local':
        host_ip = args.host_ip
        host_port = int(args.host_port)
        app_settings.update( { 'verbose': int(args.verbose) } )
       
        print("Flask")
        # Runs regular flask server with debug=False
        app.run(host=host_ip, port=host_port)
    else:
        host_ip = r"127.0.0.1"
        host_port = int(args.host_port)
        app_settings.update( { 'verbose': int(args.verbose) } )

        print("Flask (debug)")
        # Runs local flask server in debug mode
        app.run(host=host_ip, port=host_port, debug=True)
# -----------------------------------------------------------------------------
