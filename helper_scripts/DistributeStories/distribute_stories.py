# -*- coding: utf-8 -*-
"""
Created on Fri Jul 28 13:08:10 2023

distribute_stories.py v0.3
@author: Raquel Ibáñez Alcalá
"""

import pandas as pd
import os
import ast
import random
import copy
import sys
from configparser import ConfigParser as cfgp

import sys

def read_topic_table(file='../../Human DM Topics.xlsx'):
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

def read_dir_tree(rootdir='../../stories/task_types'):
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
        # ...then populate the dictionary with 'task type': 'stories for
        # in that task type'.
        dir_map.update({key: dirs})

    return dir_map

def parse_ini(filename='../../bin/settings.ini',
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
                db[key] = ast.literal_eval(value)
            elif value.startswith('['):
                db[key] = ast.literal_eval(value)
            
    return db

def without_keys(d, keys):
# Removes key-value pairs from dictionary
    return {x: d[x] for x in d if x not in keys}
    
def validate(theoretical, real, inplace=False):
# Validates that the contents of the 'theoretical' dictionary exist in the
# 'real' dictionary. Useful to check that stories described in the story
# relations table exist in the actual app. Returns a copy of the 'theoretical'
# dictionary where all the values that do not exist in 'real' have been removed

    if inplace:
        validated = theoretical
    else:
        validated = copy.deepcopy(theoretical)
        
    for mkey, sdict in validated.items():
        for key, target in sdict.items():
            if key!='topic_id':
                # print(f"{mkey}/{key}:")
                # print('theoretical story list:', target)
                # print('real story list:', real[key.replace('-','_').lower()])
                # [ x if x in real[key.replace('-','_').lower()] else removed_items.append( target.pop(target.index(x)) ) for x in target ]
                validated_list = [ x for x in target if x in real[key.replace('-','_').lower()] ]
                # print("validated list:", validated_list)
                validated[mkey][key] = validated_list
    
    return validated

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
        

# -----------------------------------------------------------------------------
args_length = len(sys.argv)-1
print(f"Detected {args_length} command line arguments: {sys.argv}")
topics = []           # Existing topics.
task_types = []       # Existing task types.
story_order = [] # How the stories will be presented across several sessions
# story_order = "[20, 7, 22, 11, 2, 16, 15, 18, 12, 5, 1, 17, 1, 2, 5, 7, 11, 12, 15, 16, 17, 18, 20, 22]"

# Get server credentials
server = without_keys( parse_ini(section='postgresql'), {} ) # Server credentials
app_settings = without_keys( parse_ini(section='app_settings', eval_datatype=True), {} ) # App settings

story_relations = read_topic_table() # Import relationship between topics, task types, and stories from Excel file.
dir_map = read_dir_tree()   # Get a dictionary representation of the /stories/task_types directory

if app_settings['validate_stories'] in [1, '1', 'True', 'true', 'y', 'yes', 'Yes']:   
    validate(story_relations, dir_map, inplace=True)
    # story_relations_new = validate(story_relations, dir_map, inplace=False)

topics = list(story_relations.keys())   # Get a list of all the topics
task_types = [ x for x in list(story_relations[random.sample(list(story_relations.keys()), 1)[-1]].keys()) if x not in ['topic_id'] ] # Get a list of all the task types

# Get topics of interest from command line.
if args_length >= app_settings['minimum_topics']:
    topics_pool = [sys.argv[x] for x in range(1, args_length+1) if sys.argv[x] in topics]
    print(f"Retrieved topics of interest {topics_pool}")
else:
    topics_pool = ['Education-Post-Education Life', 'Food', 'Vehicle/Transportation', 'Entertainment'] # Topics selected by the user
    print(f"\nDid not detect enough topics of interest in argumnets.\nUsing example topics of interest {topics_pool}")
# --------- Setup ends here --------- \
    
# Check the format of the user's story data. Check if the list elements are numeric (legacy story data),
# if this returns the same list, then the user's story data is in the old format.
if len(story_order) > 0 and (len([ s for s in ast.literal_eval(story_order) if str(s).isnumeric() ]) == len(ast.literal_eval(story_order))):
    if app_settings['ignore_legacy_story_data']:
        story_order = []
        print("\nStory data for this user was found to be formatted for a legacy version of the DM app; story order" +\
              f" and preferences have been reset and will be re-generated. This can be turned off in { os.path.abspath('bin/settings.ini') }"+\
              " under 'ignore_legacy_story_data'.")
    else:
        story_order = [ f"/approach_avoid/story_{ str(s) }" for s in ast.literal_eval(story_order) ]

# Provided that the story_order has not been set yet...
if len(story_order) == 0:
    # Check that the subject selected enough stories...
    if len(topics_pool) >= app_settings['minimum_topics']:
        # Randomly sample stories out of the existing stories pool that correspond to
        # subject's topics of interest while also taking into account task type. This
        # will generate paths to the sampled stories and place them in 'story_order'.
        print("\n\nSampling stories for each task type and topic, please wait...\n")
        try:
            for task in task_types:
                print("\n-------------------------------------------------------------")
                pool = [] # The pool of stories to sample from. The list will be populated only with stories that fall in the scope of all the topics selected by the user.
                for topic in topics_pool:
                    pool = pool + story_relations[topic][task]
                    print(f"  Generated story pool for {task} including topic {topic}: {pool}")
                
                # print("Sample from:", pool, end="")
                # print(" (topics:"+str(topics_pool)+")"+" (task:"+task+")")
                # print("Sample size:", app_settings[task.replace('-','_').lower()])
                print(f"\n  Task type: {task}\n  Stories in pool: {pool}\n  Length of story pool: {len(pool)}\n  Attempting to sample: {app_settings[task.replace('-','_').lower()]}")
                sample = random.sample(pool, app_settings[task.replace('-','_').lower()])
                # print("Result:", sample)
                # print("---------")
                story_order.append([ f"/{task.replace('-','_').lower()}/story_" + i for i in sample ])
                
        except Exception as error:
            print(f"\nCould not sample stories for the selected task type '{task}', this is usually because the amount of stories to sample for this exceeds the number of stories available for the task type. Please make sure there are enough stories to sample from for the user's selected topics: {topics_pool}")
            print(f"Raised exception: {error}")
            sys.exit()
        else:
            print("\n\n  Successfully generated story order!\n")
        finally:
            story_order = sum(story_order, []) # story_order will be a list of lists, this joins everything so that the list is uniform.
            random.shuffle(story_order) # Shuffle the story_order list to create more randomness.
    else:
        # Return back to topic selection screen.
        print(f"Please select at least { app_settings['minimum_topics'] } topics!")
else:
    print("\nStory data for this user was found to be formatted for a legacy version of the DM app; the data"+\
          f" has been conserved and reformatted to fit this version's needs. This can be turned off in { os.path.abspath('bin/settings.ini') }"+\
          " under 'ignore_legacy_story_data'.")

#print( get_story_info(story_order[4], story_relations) )
print(story_order, "\n")


