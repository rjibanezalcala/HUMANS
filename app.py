"""
Human Decision Making App v32.2
09/October/2023
@authors: Lara Rakocevic and Raquel Ibáñez Alcalá
"""
from flask import Flask, render_template, redirect, Markup, request
import re
from ast import literal_eval
import itertools
from random import shuffle, randint, sample
import time
from subprocess import Popen
#import numpy as np
from copy import deepcopy
import os
#import fnmatch
import psycopg2
import pandas as pd
from shutil import copy2
from datetime import datetime
import pytz
import sys
from configparser import ConfigParser as cfgp
from eyetracker_lib import EyeTracker
from heartrate_lib import HRMonitorThread

app = Flask(__name__, static_folder='static', template_folder='templates')

def parse_ini(filename='bin/settings.ini',
              section='postgresql',
              eval_datatype=False):
# Returns server credentials from ini file.

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
                demdata.update({ key: participant_data[key] })
    except Exception as error:
        print("\nCould not import demographic data due to error:", error)
        
        return None
    else:
        print("\nUser's demographic info was successfully imported from database!")
        return demdata

def create_data_dir(pid):
    path = os.getcwd()
    dir_to_create = path + "\\data\\" + str(pid)
    os.mkdir(dir_to_create)
    
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
        return path

def replace_demdata(user, target_entries, make_backup=True):
# Makes a backup and replaces the demographic data entries indicated by the
# keys in (target_entries) in the user's demographic_info.txt with each key's
# value. Returns the path to the modified file.
    path = os.getcwd()
    data_dir = path + "\\data\\" + str(user)
    
    # Create backup of old file if it doesn't exit.
    if make_backup:
        if not os.path.exists(data_dir+"\demographic_info_old.txt"):
            copy2(data_dir+"\demographic_info.txt", data_dir+"\demographic_info_old.txt")
    
    # Open the original file
    with open(data_dir+"\demographic_info.txt", 'r') as f:
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
    with open(data_dir+"\demographic_info.txt", 'w') as f:
        f.writelines(data)
    
    return data_dir+"\demographic_info.txt"
    
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
        path += "\\data\\" 
        unique_ids = set([ int(x) for x in re.findall("\d+", ' '.join(os.listdir(path))) ])
    elif reference_from == 'file':
        pass # Haven't done this yet
    
    else:
        raise Exception(f"\nParameter 'reference_from' was not recognised. Received {reference_from}, expected {str(expected_refs)}!")
        
    while True:
        participant_id = str(randint(10000,99999))
        if participant_id not in unique_ids:
            break

    return participant_id

def get_story_order():
# Retrieves the story order from the uder's demographic info. Returns 0 if the
# user's story order was not altered, but returns 1 if it was.
    global story_order
    global STO_CH
    filename = f"data/{participant_id}/demographic_info.txt"
    with open(filename) as f:
        lines = f.readlines()
        story_order = lines[-1]
        story_order_split = story_order.split(": ")
        order = story_order_split[1]
        # pref_topics = lines[len(lines)-1].split(": ")[1]

    story_order = literal_eval(order)
    
    # Check the format of the user's story data. Check if the list elements are numeric (legacy story data),
    # if this returns the same list, then the user's story data is in the old format.
    if (len([ s for s in story_order if str(s).isnumeric() ]) == len(story_order)):
        if app_settings['ignore_legacy_story_data']:
            STO_CH = 1
            story_order = []
            print("\nStory data for this user was found to be formatted for a legacy version of the DM app; story order" +\
                  f" and preferences have been reset and will be re-generated. This can be turned off in { os.path.abspath('bin/settings.ini') }"+\
                  " under 'ignore_legacy_story_data'.")
            return 1
        else:
            story_order = [ f"/approach_avoid/story_{ str(s) }" for s in story_order ]
            print("\nStory data for this user was found to be formatted for a legacy version of the DM app; story order" +\
                  f" and preferences have been adapted to the format needed by this version. This can be turned off in { os.path.abspath('bin/settings.ini') }"+\
                  " under 'ignore_legacy_story_data'.")
            return 0
    else:
        return 0


def get_starting_story_indx(participant_id, reference_from='database'):
    global max_story_indx
    global current_story_indx
    expected_refs = ['database', 'local']
    if reference_from == 'database':
        try:
            sql_qry = f"""SELECT COUNT(distinct tasktypedone) FROM { app_settings['data_table'] } WHERE subjectidnumber = '{str(participant_id)}'"""
            print(f"\nMaking a connection to database with query {sql_qry}...")
            data = []
        
            conn = psycopg2.connect(**server)
        
            cursor = conn.cursor()
            cursor.execute(sql_qry, data)
        
            raw_num_stories = cursor.fetchone()
            print(f"Retrieved {raw_num_stories}.")
        
            cursor.close()
            conn.close()
        
            num_stories_completed = raw_num_stories[0] if raw_num_stories is not None else 0
        except Exception as error:
            print(f"\nStarting story index could not be retreived from database due to error: {error}.\nAttempting to read from local file...")
            try:
                num_stories_completed = int(get_demographic_info(participant_id)['next_story_index'])
            except Exception as error:
                print(f"\nStarting story index could not be retreived from local file, exception raised: {error}\n")
            else:
                print(f"\nRetrieved starting story index: {num_stories_completed}.\n")
        else:
            print(f"\nRetrieved starting story index: {num_stories_completed}.\n")
    
    elif reference_from == 'local':
        try:
            num_stories_completed = int(get_demographic_info(participant_id)['next_story_index'])
        except Exception as error:
            print(f"\nStarting story index could not be retreived from local file, exception raised: {error}\n")
        else:
            print(f"\nRetrieved starting story index: {num_stories_completed}.\n")
    else:
        raise Exception(f"\nParameter 'reference_from' was not recognised. Received {reference_from}, expected {str(expected_refs)}!\n")
        

    current_story_indx = num_stories_completed
    max_story_indx = min(total_number_of_stories, num_stories_completed + stories_in_session)
    
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

def choose_questions():
    task_type = story_num_overall.strip().split('/')[1]
    story_num = int(story_num_overall.strip().split('/')[-1].split('_')[-1])
    print(f"\nCurrent story: { str(current_story_indx+1) }.\nStory: { story_num_overall }.")    # Should help with debugging
    # path = f"stories/story_{story_num_overall}/questions.txt"
    path = f"stories/task_types{story_num_overall}/questions.txt"
    txt = open(path).read()
    lines = txt.split("\n")
    quest_dict = {}
    # Pattern to match all sentences, regardless of punctuation (curly brace included for debugging with example stories).
    pattern = re.compile(r'([A-Z][^\.!?}]*[\.!?}])', re.M)
    for l in lines: 
        # linelist = l.split("?") 
        # question = linelist[0] + "?"
        linelist = ['', '']
        linelist[0] = ' '.join(pattern.findall(l)) # Find all sentences in the question
        linelist[1] = re.findall('\(.*?\)', l)[-1]  # Find everything in parenthesis and take the last element.
        question = linelist[0]
        if task_type == 'social':
            if app_settings['randomise_relation_levels'] and story_num in app_settings['relation_level_stories']:
                question, _ = replace_all(question, app_settings['relation_levels'], replace_with=relationship_lvl)
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
    # print('\n[choose_questions] quest_dict', list(quest_dict.keys()))

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

def get_demographic_info(participant_id):
    filename = f'data/{participant_id}/demographic_info.txt'
    dem_dict = {}
    with open(filename) as f:
        for line in f:
            (key, val) = line.split(": ")
            dem_dict[key] = val.strip()

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

def write_trial_to_db(current_question, dec=None, trial_start=None, trial_end=None, exclude_keys=[]):
    global CREATE_DATA_TABLE
    task_type = story_num_overall.split('/')[1]
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
    # dem_dict = get_demographic_info(participant_id)
    dem_dict = deepcopy(participant_data)
    dem_dict.update({ 'tasktypedone' : story_num_overall,
                      'reward_prefs' : str(reward_prefs),
                      'cost_prefs'   : str(cost_prefs),
                      'cost_level'   : c if not task_type in ['multi_choice'] else [c1, c2],
                      'reward_level' : r if not task_type in ['multi_choice'] else [r1, r2],
                      'decision_made': dec,
                      'trial_index'  : trial_num,
                      'trial_start'  : trial_start,
                      'trial_end'    : trial_end,
                      'trial_elapsed': trial_elapsed,
                      'story_prefs'  : str(story_prefs),
                      'subjectidnumber':participant_id,
                      'eye_tracker_data': {'gaze_data': eyetracker.gaze if eye_settings['use_eyetracker'] else None,\
                                           'eye_openness_data':eyetracker.openness if eye_settings['use_eyetracker'] else None,\
                                           'user_position_data':eyetracker.user_pos  if eye_settings['use_eyetracker'] else None},
                      'relationship_level': relationship_lvl
                      #'heart_rate_data' : hr_monitor.container
                    })
    
    if CREATE_DATA_TABLE:
        query = f"CREATE TABLE { app_settings['data_table'] }("
        i = 0
        for key in dem_dict:
            if key not in exclude_keys:
                start = ', ' if i != 0 else ' '
                query += start+str(key)+" VARCHAR"
                i += 1
        query += r" );"
        
        print(f"\nCreating data table in database with name { app_settings['data_table'] } using query { query }...")
        conn = psycopg2.connect(**server)
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
        cursor.close()
        CREATE_DATA_TABLE = 0
    
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

def distribute_stories(topics_pool):
    global story_order
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
                    
                    # print("Sample from:", pool, end="")
                    # print(" (topics:"+str(topics_pool)+")"+" (task:"+task+")")
                    # print("Sample size:", app_settings[task.replace('-','_').lower()])
                    print(f"\n  Task type: {task}\n  Stories in pool: {pool}\n  Length of story pool: {len(pool)}\n  Attempting to sample: {app_settings[task.replace('-','_').lower()]}\n\n")
                    samp = sample(pool, app_settings[task.replace('-','_').lower()])
                    # print("Result:", sample)
                    # print("---------")
                    story_order.append([ f"/{task.replace('-','_').lower()}/story_" + i for i in samp ])
                    
            except Exception as error:
                print(f"\nCould not sample stories for the selected task type '{task}', this is usually because the amount of stories to sample for this exceeds the number of stories available for the task type. Please make sure there are enough stories to sample from for the user's selected topics: {topics_pool}")
                print(f"Raised exception: {error}")
                sys.exit()
            else:
                print("  Successfully generated story order!\n")
            finally:
                story_order = sum(story_order, []) # story_order will be a list of lists, this joins everything so that the list is uniform.
                #random.shuffle(story_order) # Shuffle the story_order list to create more randomness.
        else:
            # Return back to topic selection screen.
            print(f"\nPlease select at least { app_settings['minimum_topics'] } topics!")
    else:
        print("\nStory data for this user was found to be formatted for a legacy version of the DM app; the data"+\
              f" has been conserved and reformatted to fit this version's needs. This can be turned off in { os.path.abspath('bin/settings.ini') }"+\
              " under 'ignore_legacy_story_data'.")
    
def write_userdata_to_file(user_id, filename, user_data, end_line='\n', include_keys='all', exclude_keys=[], data_format='records'):
# Writes the contents of 'data' to a file in inside data/'user_id'/'filename'
# as long the keys in data are included in 'include_keys'. Every line will
# terminate with the character(s) indicated by 'end_line'. If 'include_keys'
# is set to 'all' (default), then the whole data dictionary will be written.
# If 'data_format' is set to 'records', the data will be written as
# {data_key}: {data_value}{end_line}, otherwise the data will be written raw.
    data = deepcopy(user_data)
    filepath = f"data/{participant_id}/{filename}"
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
            
def reset_app_params():
# Reinitialises all relevant global parameters that affect the app's
# functionality to their default values.
# This can be used to allow the app to be used and reused without having to
# restart the flask server.

    global current_story_indx
    global stories_in_session
    global max_story_indx
    global story_num_overall
    global trial_num
    global relevant_questions
    global story_order
    global current_task_type
    global STO_CH
    global NEED_RESET
    
    current_story_indx = 0
    stories_in_session = 3
    max_story_indx = stories_in_session
    story_num_overall = 1
    trial_num = 0
    relevant_questions = []
    story_order = []
    current_task_type = ''
    STO_CH = 0
    NEED_RESET = 0
    
    print("\nApp parameters were reset!")
    return True

def reset_user_params():
# Reinitialises all relevant global parameters that store any kind of
# information about the user their default values.
# This can be used to allow the app to be used and reused without having to
# restart the flask server.

    global participant_id
    global participant_data
    global cost_prefs
    global reward_prefs
    global story_prefs
    global relationship_lvl
    global trial_start
    global trial_end
    global current_question
    
    participant_id = ''
    participant_data = {'session_notes':'','num_stories':stories_in_session,'hunger':None,'tired':None,\
                        'pain':None,'stress':None,'sex':None,'genderid':None,'menstruation':None,\
                        'age':None,'weight':None,'race':None,'ethnicity':None,'relationship_status':None,\
                        'sexual_orientation':None,'education':None,'college':None,'major':None,\
                        'exercise':None,'exercise_time_min':None,'exercise_time_max':None,\
                        'caffeine':None,'nicotine':None,'alcohol':None,'vis_media':None,\
                        'hobbies':None,'next_story_index':current_story_indx,\
                        'eye_tracker_data':{'gaze_data':None,'eye_openness_data':None,'user_position_data':None},\
                        'heart_rate_data':[],\
                        'pref_stories':None,'story_order':None}
    cost_prefs = []
    reward_prefs = []
    story_prefs = {}
    relationship_lvl = ''
    trial_start = None 
    trial_end = None 
    current_question = None
    
    print("\nUser parameters were reset!")
    return True

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
    
    # Remove "'s" from text and split words into list
    split_text = [ re.split(r"'s", word)[0] for word in text.split(' ') ]
    # If any word (where each word has punctuation removed) in the text appears in the word bank, process the text
    if any(word in [ re.sub(r'[^\w\s\d]', '', x).lower() for x in split_text] for word in word_bank):
        if replace_from is None:
            results = []
            # Find all of those words and save them in a list
            for i, word in enumerate(split_text):
                if re.sub(r'[^\w\s\d]', '', word).lower() in word_bank:
                    # Get only unique results. Save the word without punctuation
                    if not word in results: results.append(re.sub(r'[^\w\s\d]', '', word))
            print(f"\nFound matches in text! {results}")
            # Sample as many words from the word bank as there are results
            pick = sample(word_bank, len(results)) if replace_with is None else replace_with
            print(f"Replacing matching results with: {pick}\n")
            for i, word in enumerate(results):
                # Replace all words with the sampled word
                text = text.replace(word, pick[i].title() if word[0].isupper() else pick[i])
            
            return text, pick
        else:
            return text.replace(replace_from, replace_with), replace_with
    else:
        return text, None
    

# -----------------------------------------------------------------------------
print("\nPerforming initial setup operations, please wait...")
# Global app params
current_story_indx = 0
stories_in_session = 3  # How many stories the subject selects to view per session
max_story_indx = stories_in_session
story_num_overall = 1
trial_num = 0
relevant_questions = []
story_order = []
current_task_type = ''
relationship_lvl = ''   # Only used by social tasks.
eyetracker = None
hr_monitor = None
STO_CH = 0  # Flag that indicates that story order had to be changed.
NEED_RESET = 0 # Flag to reset all global parameters for consecutive users.
CREATE_DATA_TABLE = 0
EYE_TRACKER_STATUS = 0
HR_TRACKER_STATUS = 0

# These are not changed throughout the server's lifetime.
topics = []           # Existing topics.
task_types = []       # Existing task types.
story_relations = {}  # What topic and task type each story correponds to
dir_map = {}          # Will contain the a dictionary structure that describes the contents of 'stories/task_types'.

server = without_keys( parse_ini(section='postgresql'), {} ) # Parse server credentials from ini.
app_settings = without_keys( parse_ini(section='app_settings', eval_datatype=True), {} ) # Parse app settings from ini.
eye_settings = without_keys( parse_ini(section='eye_tracker', eval_datatype=True), {} ) # Parse app settings from ini.
hr_settings = without_keys( parse_ini(section='hr_tracker', eval_datatype=True), {} ) # Parse app settings from ini.
timezone = pytz.timezone(app_settings.get('timestamp_timezone', 'UTC'))

# Initialise biometrics hardware
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
        stop_hr_monitor(hr_monitor)
    
# Check if target data table exists in the database:
if (not exists(app_settings['data_table'])) and app_settings['auto_create_table']:
    CREATE_DATA_TABLE = 1

story_relations = read_topic_table(file='Human DM Topics.xlsx') # Import relationship between topics, task types, and stories from Excel file.
dir_map = read_dir_tree(rootdir='stories/task_types')   # Get a dictionary representation of the /stories/task_types directory

# Check if all stories exist. Those that don't exist will be deleted from the pool of stories to be sampled for the subject.
if app_settings['validate_stories']:   
    validate(story_relations, dir_map, inplace=True)

topics = list(story_relations.keys())   # Get a list of all the topics
task_types = [ x for x in list(story_relations[sample(list(story_relations.keys()), 1)[-1]].keys()) if x not in ['topic_id'] ] # Get a list of all the task types

num_qs_in_story = app_settings['questions_per_story']   # No. of questions selected per story.
total_number_of_stories = 0    # How many stories currently exist (calculated from contents of 'stories/task_types').
for x in dir_map: total_number_of_stories = total_number_of_stories + len(dir_map[x])
min_stories_to_choose = app_settings['minimum_topics']  # The least amount of topics the user will be allowed to choose.

# Global subject params
participant_id = ''
cost_prefs = []
reward_prefs = []
story_prefs = {}
participant_data = {'session_notes':'','num_stories':stories_in_session,'hunger':None,'tired':None,\
                    'pain':None,'stress':None,'sex':None,'genderid':None,'menstruation':None,\
                    'age':None,'weight':None,'race':None,'ethnicity':None,'relationship_status':None,\
                    'sexual_orientation':None,'education':None,'college':None,'major':None,\
                    'exercise':None,'exercise_time_min':None,'exercise_time_max':None,\
                    'caffeine':None,'nicotine':None,'alcohol':None,'vis_media':None,\
                    'hobbies':None,'next_story_index':current_story_indx,\
                    'eye_tracker_data':{'gaze_data':None,'eye_openness_data':None,'user_position_data':None},\
                    'heart_rate_data':[],\
                    'pref_stories':None,'story_order':None}
trial_start = None 
trial_end = None 
current_question = None

# --------- Setup ends here --------- 

# page for are you a new participant? 
@app.route('/',methods=['GET', 'POST'])
def select_stories():
    global stories_in_session
    global max_story_indx
    
    print(f"\nSession variables {'need ' if NEED_RESET else 'do not need '}to be reset.\n'enable_consecutive_users' is {'enabled ' if app_settings['enable_consecutive_users'] else 'not enabled '}in settings.\n")
    
    if NEED_RESET:
        if app_settings['enable_consecutive_users']:
            reset_app_params()
            reset_user_params()
            ALERT = 0
        else:
            ALERT = 1
    else:
        ALERT = 0
        
    if request.method=="POST":
        # Get subject's "feeling" data
        feeling = request.form.to_dict()
        participant_data.update(feeling)
        
        # Get selected amount of stories in session.
        #num_stories = request.form['num_stories']
        num_stories = participant_data['num_stories']
        stories_in_session = int(num_stories)-1
        max_story_indx = stories_in_session
        
        print(participant_data)
        
        return redirect('/welcome')

    return render_template('setup_session.html', ALERT_FLAG=ALERT)


@app.route('/welcome')
def welcome_participant():
    global eye_settings
    global eyetracker
    global EYE_TRACKER_STATUS
    global hr_settings
    global hrtracker
    global hr_monitor
    global HR_TRACKER_STATUS
    print("\nCalling eye tracker manager to initiate calibration!\n")
    # Re-check app settings to see if biometric devices will be used
    new_eye_settings = without_keys( parse_ini(section='eye_tracker', eval_datatype=True), {} ) # Parse app settings from ini.
    new_hr_settings = without_keys( parse_ini(section='hr_tracker', eval_datatype=True), {} ) # Parse app settings from ini.
    
    if new_eye_settings != eye_settings:
        print("\nEye tracker settings were changed from last session! Reinitialising eye tracker with new settings.")
        eye_settings.update(new_eye_settings)
        EYE_TRACKER_STATUS = 0
        if eye_settings['use_eyetracker']:
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
            hr_monitor = initialise_device('hrtracker', emulate_hr=bool(hr_settings['emulate_device']), as_daemon=bool(hr_settings['run_thread_as_daemon']), verbose=bool(hr_settings['verbose']), timezone=app_settings['timestamp_timezone'])    
            start_hr_monitor(thread=hr_monitor)
            hr_monitor.set_flag(data_capture=False, flush_data=False)
        else:
            hr_monitor = Popen(hr_settings['external_app_install_path'])
    # Open eye tracker manager (blocking)
    if EYE_TRACKER_STATUS:
        eyetracker.call_eye_tracker_manager()
        
    return render_template('welcome_participant.html')

@app.route("/new", methods=['GET', 'POST'])
def new_participant():
    global participant_id

    if request.method=="POST":
        create_data_dir(participant_id)
        args = request.form.to_dict()
        # Grab these in this this way since they're arrays of checkboxes.
        args['vis_media'] = request.form.getlist('vis_media')
        args['hobbies'] = request.form.getlist('hobbies')
        participant_data.update(args)

        return redirect('/choose_stories')
    
    if participant_id == '':
        participant_id = get_new_id(reference_from=app_settings['unique_ids_from'])
    print(f"\nCreated user ID: { str(participant_id) }.\n")
    return render_template('give_new_id.html', participant_id=participant_id)

@app.route("/choose_stories", methods=['GET','POST'])
def choose_stories():
    global story_order
    global story_num_overall
    global current_story_indx
    global STO_CH
    # story_blurbs = get_blurbs()
    story_blurbs = get_blurbs(story_relations)
    # Empty story order in case the user backtracks through the windows.
    # story_order = []
    if request.method=="POST":

        prefs = request.form.to_dict()
        pref_stories = [int(k) for (k,v) in prefs.items() if v]
        not_pref_stories = [int(k) for k in range(1,len(story_blurbs)+1) if k not in pref_stories]
        if len(pref_stories) < min_stories_to_choose:
            return render_template("choose_stories_try_again.html", story_blurbs=story_blurbs,\
                                   num_blurbs=len(story_blurbs), prev_yes=pref_stories, min_stories_to_choose = min_stories_to_choose)

        pref_stories = [ story_blurbs[k] for k in pref_stories ]
        print(f"\nUser preferred topics: { pref_stories }")
        participant_data.update({  })
        not_pref_topics = [ story_blurbs[k] for k in not_pref_stories ]
        distribute_stories(pref_stories)
        shuffle(story_order)
        print(f"\nUser's generated story order: { story_order }\n")
        participant_data.update({ 'next_story_index':current_story_indx,
                                  'pref_stories': pref_stories,
                                  'story_order': story_order })

        ## add back in the rest of the stories at the end
        # story_order = story_order + not_pref_stories
        story_order = story_order + not_pref_topics
        
        # If the user was re-routed here because their story preferences had
        # to be remade...
        if STO_CH:
            # Make a copy of their demographic data and overwrite 'story order'
            # and 'pref stories' to the new format.
            replace_demdata(participant_id, {'story_order': story_order, 'pref_stories': pref_stories})
            # Then reset the story index to have them start their stories from
            # the first one again.
            current_story_indx = 0
            STO_CH = 0
        else:
            write_userdata_to_file(participant_id, 'demographic_info.txt', participant_data, exclude_keys=['session_notes', 'eye_tracker_data'], data_format='records')
        
        story_num_overall = story_order[current_story_indx]

        return redirect('/story_num_overall')

    return render_template('choosing_stories.html', story_blurbs = story_blurbs, num_blurbs = len(story_blurbs), min_stories_to_choose = min_stories_to_choose)


@app.route("/not_new", methods=['GET','POST'])
def not_new_participant():
    global participant_id
    global story_num_overall
    global participant_data
    
    if request.method == "POST":
        participant_id = request.form['participant_id']
        print(f"\nRetrieved user ID: { str(participant_id) }.")
        if participant_id not in os.listdir("data"):
            demographics = import_demdata(participant_id, server)
            parse_demdata(demographics, participant_id)
                
        get_starting_story_indx(participant_id, reference_from=app_settings['next_story_from'])
        replace_demdata(participant_id, {'hunger':participant_data['hunger'],
                                         'tired':participant_data['tired'],
                                         'pain':participant_data['pain'],
                                         'stress':participant_data['stress'],
                                         'next_story_index':current_story_indx}, make_backup=False)
        participant_data.update(get_demographic_info(participant_id))
        # Attempt to get the story order. If the story order gets modified
        # because it needs to be remade...
        if get_story_order():
            print("\nRedirecting user to /choose_stories...\n")
            return redirect("/choose_stories")
        # Otherwise continue as normal
        else:
            story_num_overall = story_order[current_story_indx]
            return redirect("/story_num_overall")
    
    return render_template('welcome_back.html')

@app.route('/story_num_overall')
def story_num_refresh():
    global story_num_overall
    # blurbs = get_blurbs()
    # blurb = blurbs[story_num_overall]
    story_num_overall = story_order[current_story_indx]
    
    print(f"\nStarting story { story_num_overall }")
    story_info = get_story_info(story_num_overall, story_relations)
    blurb = f"{ story_info['topic'] }"
    print(f"Current topic: { story_info['topic'] } ({ story_info['topic_id'] })\n")
    
    return render_template('story_num.html', number=current_story_indx+1, content=blurb)

## context - read from file, click next -> to reward pref
@app.route('/context')
def context():
    global relationship_lvl
    # Determine the task type to know whether to proceed directly to cost if
    # the task type is cost_cost
    task_type = story_num_overall.strip().split('/')[1]
    story_num = int(story_num_overall.strip().split('/')[-1].split('_')[-1])
    
    print(f"\nCurrent story number: { str(current_story_indx+1) }.\nStory: { story_num_overall }.\n")    # Should help with debugging
    # path = f"stories/story_{story_num_overall}/context.txt"
    path = f"stories/task_types{story_num_overall}/context.txt"
    txt = open(path).read()
    if task_type == 'social':
        if app_settings['randomise_relation_levels'] and story_num in app_settings['relation_level_stories']:
            txt, relationship_lvl = replace_all(txt, app_settings['relation_levels'])
    print(f"replaced word {relationship_lvl}")
    return render_template('context.html', content=txt, next_prefs=( 'cost' if task_type=='cost_cost' else 'reward' ))

## enter values (+ save), click next -> to cost pref
## enter values (+ save), click next -> to context refresh
@app.route('/prefs/<cost_or_reward>', methods=['GET', 'POST'])
def rank_prefs(cost_or_reward):
    global cost_prefs
    global reward_prefs

    print(f"\nCurrent story number: { str(current_story_indx+1) }.\nStory: { story_num_overall }.\n")    # Should help with debugging
    task_type = story_num_overall.split('/')[1]
    story_num = int(story_num_overall.strip().split('/')[-1].split('_')[-1])
    path = f"stories/task_types{story_num_overall}/pref_{cost_or_reward}.txt"
    txt = open(path).read()
    
    options = txt.split("\n")
    opt_dict = {}
    for option in options:
        if option != '':
            line = option.split(")")
            opt_num = int(line[0])
            opt_description = line[1]
            if task_type == 'social':
                if app_settings['randomise_relation_levels'] and story_num in app_settings['relation_level_stories']:
                    txt, _ = replace_all(opt_description, app_settings['relation_levels'], replace_with=relationship_lvl)
            opt_dict[opt_num] = txt.strip()

    if request.method == "POST":
        data = request.form.to_dict()
        vals = list(data.values())
        if len(vals) != len(set(vals)):
            try_again = f"{cost_or_reward}_try_again.html"
            return render_template(try_again, len = len(options), opt_dict=opt_dict, vals=vals)

        if cost_or_reward == "cost":
            cost_prefs = data
        else:
            reward_prefs = data

        return redirect("/prefs/cost") if (cost_or_reward == 'reward' and task_type != 'benefit_benefit') else redirect("/refresh")

    html = f"{cost_or_reward}_prefs.html"
    return render_template(html, len = len(options), opt_dict=opt_dict)

## context refresh, click next -> trials
@app.route('/refresh')
def context_refresh():
    global relevant_questions
    task_type = story_num_overall.strip().split('/')[1]
    story_num = int(story_num_overall.strip().split('/')[-1].split('_')[-1])
    
    print(f"\nCurrent story number: { str(current_story_indx+1) }.\nStory: { story_num_overall }.\n")    # Should help with debugging
    path = f"stories/task_types{story_num_overall}/context.txt"
    txt = open(path).read()
    if task_type == 'social':
        if app_settings['randomise_relation_levels'] and story_num in app_settings['relation_level_stories']:
            txt, _ = replace_all(txt, app_settings['relation_levels'], replace_with=relationship_lvl)
    relevant_questions = choose_questions()
    return render_template('refresh.html', content=txt)

@app.route('/want_change_prefs', methods=['GET'])
def ask_if_change_prefs():
    task_type = story_num_overall.split('/')[1]

    return render_template('want_change_prefs.html', next_prefs=( 'cost' if task_type=='cost_cost' else 'reward' ))


# after finishing trials, re-rank the prefs
@app.route('/refresh_prefs/<cost_or_reward>', methods=['GET', 'POST'])
def rank_prefs_again(cost_or_reward):
    global cost_prefs
    global reward_prefs
    task_type = story_num_overall.strip().split('/')[1]
    story_num = int(story_num_overall.strip().split('/')[-1].split('_')[-1])
    
    print(f"\nCurrent story number: { str(current_story_indx+1) }.\nStory: { story_num_overall }.\n")    # Should help with debugging
    path = f"stories/task_types{story_num_overall}/pref_{cost_or_reward}.txt"
    task_type = story_num_overall.split('/')[1]
    txt = open(path).read()

    options = txt.split("\n")
    opt_dict = {}
    for option in options: 
        if option != '':
            line = option.split(")")
            opt_num = int(line[0])
            opt_description = line[1]
            if task_type == 'social':
                if app_settings['randomise_relation_levels'] and story_num in app_settings['relation_level_stories']:
                    txt, _ = replace_all(txt, app_settings['relation_levels'], replace_with=relationship_lvl)
            opt_dict[opt_num] = opt_description.strip()

    if request.method == "POST":
        data = request.form.to_dict()
        vals = list(data.values())
        if len(vals) != len(set(vals)):
            try_again = f"{cost_or_reward}_try_again.html"
            return render_template(try_again, len = len(options), opt_dict=opt_dict, vals=vals)

        if cost_or_reward == "cost":
            cost_prefs = data
        else:
            reward_prefs = data
        
        if app_settings['data_upload']:
            write_trial_to_db((7,7), exclude_keys=['num_stories'])

        return redirect("/refresh_prefs/cost") if (cost_or_reward == 'reward' and task_type != 'benefit_benefit') else redirect("/trial_end")

    html = f"refresh_{cost_or_reward}_prefs.html"
    return render_template(html, len = len(options), opt_dict=opt_dict)

@app.route('/trial/<loc_trial_num>', methods=['GET', 'POST'])
def trial_html(loc_trial_num):
    global current_story_indx
    global trial_num
    global max_story_indx
    global trial_start
    global trial_end
    global current_question
    global participant_data
    global relationship_lvl
            
    tup, q = relevant_questions[trial_num-1]

    # trial_start = time.gmtime()
    # Changing this to a datetime timestamp with timezone data to get
    # microsecond precision and be able to track when timestamps were made.
    trial_start = timezone.localize(datetime.now())
    current_question = tup
    
    # Start collecting eye tracker data
    if EYE_TRACKER_STATUS:
        eyetracker.subscribe(to=eye_settings['subscriptions'])
    
    if HR_TRACKER_STATUS and not hr_settings['use_external_app']:
        # Start capturing heart rate data
        hr_monitor.set_flag(data_capture=True)
    
    if request.method == "POST":
        data = request.form.to_dict()
        vals = list(data.values())

        dec = vals[0]
        # trial_end = time.gmtime()
        trial_end = timezone.localize(datetime.now())
        
        # Retrieve hr data, stop the data collection, and flush he container
        if HR_TRACKER_STATUS and not hr_settings['use_external_app']:
            participant_data['heart_rate_data'] = deepcopy(hr_monitor.container)
            hr_monitor.set_flag(flush_data=True)
            # participant_data.update({'heart_rate_data': hr_data})
            print(f"\nUpdated participant data with: {participant_data['heart_rate_data']}\nWith length: {len(participant_data['heart_rate_data'])}\n")

        # Stop collecting eye tracker data before uploading data
        if EYE_TRACKER_STATUS:
            eyetracker.unsubscribe(frm=eye_settings['subscriptions'])        
            
        if app_settings['data_upload']:
            write_trial_to_db(current_question, dec, trial_start, trial_end, exclude_keys=['num_stories'])

        next_trial = trial_num + 1
        next_trial_str = '/trial/'+str(next_trial)
        
        if trial_num + 1 < num_qs_in_story:
            trial_num += 1
            return redirect(next_trial_str)
        else:
            current_story_indx += 1
            participant_data.update({'next_story_index':current_story_indx})
            replace_demdata(participant_id, {'next_story_index':current_story_indx}, make_backup=False)
            trial_num = 0
            relationship_lvl = ''
            return redirect('/want_change_prefs')
    
    task_type = story_num_overall.split('/')[1]
    if task_type in ['multi_choice', 'benefit_benefit', 'cost_cost']:
        split_question = q.split(' or ')
        optn_a = Markup(split_question[0])
        optn_b = Markup(split_question[-1])
        return render_template('trial_a_or_b.html', trial_number=trial_num+1, optn_a=optn_a, optn_b=optn_b)
    else:
        q = Markup(q)
        return render_template('trial_n_y.html', trial_number=trial_num+1, question=q)

@app.route('/trial_end', methods=['GET','POST'])
def get_story_relevance():
    global story_prefs
    global story_num_overall

    if request.method == "POST":
        data = request.form.to_dict()
        vals = list(data.values())
        rel = vals[0]
        
        story_prefs[story_num_overall] = rel

        return redirect('/story_num_overall') if current_story_indx <= max_story_indx else redirect('/total_end')

    return render_template('trial_end.html', story_num=current_story_indx)


@app.route('/total_end', methods = ['GET', 'POST'])
def total_end():
    global NEED_RESET
    global participant_data
    # print(f"\n{story_prefs}")
    task_type = story_num_overall.split('/')[1]
    if app_settings['data_upload']:
        write_trial_to_db((0,0) if not task_type in ['multi_choice'] else (0,0,0,0), exclude_keys=['num_stories'])

    NEED_RESET = 1  # Signal that the app parameters need to be reset.
    
    if request.method == "POST":
        data = request.form.to_dict()
        print(f"\nRetreived data: {data}\n")
        participant_data.update(data)
        # replace_demdata(participant_id, data)
        if app_settings['data_upload']:
            write_trial_to_db((0,0) if not task_type in ['multi_choice'] else (0,0,0,0), exclude_keys=['num_stories'])
        
        if hr_settings['use_hrtracker'] and not hr_settings['use_external_app']:
            if (not hr_monitor is None) and (hr_monitor.is_alive()):
                stop_hr_monitor(hr_monitor)
        
        return redirect('/')
    
    return render_template('total_end.html')