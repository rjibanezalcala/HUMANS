# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 14:23:43 2023

breakdown_stories.py v1.3
05/October/2023
@author: Raquel Ibáñez Alcalá and Lara Rakocevic

Use this script to break down a word document containing human decision-making
stories into four text files organised into the same directory format required
by the decision-making app. This script assumes the same template format for
every inputted word file.
"""

import os
import copy
import docx2txt
import re
import string as stri
from itertools import product

class StoryBD:
    def __init__(self):
        pass
    
    def read_dir(self, rootdir='input'):
    # Returns the structure of the 'stories/task_types' directory as a dictionary.
        
        files = os.listdir(rootdir)
        # result = []
        if len(files) > 0:
            # for filename in files:
            #     test = re.split(r'[~|\$][a-z]|[A-Z]* DM\.docx', filename)
            #     if len(test) <2:
            #         result.append(test[0])
            # result = [ x for x in files if len(re.split(r'[~|\$][a-z]|[A-Z]* DM\.docx', x)) <= 2 ]
            for file in files:
                if file.startswith('~'):
                    files.remove(file)
            return files
        else:
            return None
    
    def get_task_types(self, rootdir='input'):
    # Returns all task types present in the input folder
        tasks = os.listdir(rootdir)
        # result = []
        # If the task type directory is populated...
        if len(tasks) > 0:
            # for x in tasks:
            #     test = re.search(r'^[~|\$]*([a-z]|[A-Z])*\w\.docx', str(x))
            #     if test is None:
            #         result.append(x)
            for i, item in enumerate(tasks):
                if item.startswith('~'):
                    tasks.remove(item)
                else:
                    # Take only the first word from the directory names...
                    tasks[i] = item.lower().strip().split(' ')[0]
            
            return tasks
        else:
            
            return None
    
    def create_dir(self, new_dir):
        path = os.getcwd()
        dir_to_create = path + "\\output\\" + str(new_dir)
        if not os.path.exists(dir_to_create):
            os.mkdir(dir_to_create)
        
        return dir_to_create
    
    # def write_questions(self, reward_pref_file, cost_pref_file, output_file):
    # # Written by Lara Rakocevic
    # 	rew = open(reward_pref_file, 'r')
    # 	cost = open(cost_pref_file, 'r')

    # 	rew_dict = {}
    # 	cost_dict = {}
    # 	for i in range(1,7):
    # 		rew_line = rew.readline().split(")")[1].strip()
    # 		cost_line = cost.readline().split(")")[1].strip()
    # 		rew_dict[i] = rew_line
    # 		cost_dict[i] = cost_line

    # 	t = [list(range(1,7)) for _ in range(2)]
    # 	index_combos = list(product(*t))
    # 	# print(index_combos)
    # 	qs = []
    # 	with open(output_file, 'w') as fp:
    # 		for ind in index_combos:
    # 			r_key, c_key = ind
    # 			rew = rew_dict[r_key]
    # 			cost = cost_dict[c_key]
    # 			q = f"Would you like to {rew} but {cost}? (R{r_key},C{c_key}) \n"
    # 			fp.write(q)
    def write_questions(self, task_type, story_num):
    # Written by Lara Rakocevic
        working_dir = os.getcwd() + "\\output\\"
       
       	reward_pref_file = working_dir + task_type + "/story_" + str(story_num) + "/pref_reward.txt"
       	cost_pref_file = working_dir + task_type + "/story_" +str(story_num) + "/pref_cost.txt"
       	output_file = working_dir + task_type + "/story_" + str(story_num) +  "/questions.txt"
    
       	if task_type == "benefit_benefit":
       		with open(reward_pref_file) as f:
       			rew = [next(f) for _ in range(1,7)]
       			cost = [next(f) for _ in range(8,14)]
    
       	elif task_type == "cost_cost":
       		with open(cost_pref_file) as f:
       			rew = [next(f) for _ in range(1,7)]
       			cost = [next(f) for _ in range(8,14)]
       	else:
       		rew = open(reward_pref_file, 'r').readlines()
       		cost = open(cost_pref_file, 'r').readlines()
    
       	rew_dict = {}
       	cost_dict = {}
       	for i in range(0,6):
       		rew_dict[i] = rew[i].split(")")[1].strip()
       		cost_dict[i] = cost[i].split(")")[1].strip()
    
    
       	t = [list(range(0,6)) for _ in range(2)]
       	index_combos = list(product(*t))
       	# print(index_combos)
       	# qs = []
       	with open(output_file, 'w') as fp:
       		for ind in index_combos:
       			r_key, c_key = ind
       			rew = rew_dict[r_key]
       			cost = cost_dict[c_key]
       			if task_type in ["benefit_benefit", "cost_cost"]:
       				q = f"Would you like to {rew} or {cost}? (R{r_key+1},C{c_key+1}) \n"
       			else:
       				q = f"Would you like to {rew} but {cost}? (R{r_key+1},C{c_key+1}) \n"
       			fp.write(q)

print("Script started!\n")
bd = StoryBD()
word_files = bd.read_dir()
tasks = bd.get_task_types()

print("\n>> Detected the following Word files to break down:")
print('\n'.join(word_files))
print("\n>> Detected the following task types:")
print('\n'.join(tasks))
# print(os.path.dirname(os.path.realpath(__file__)))
stories = {}

# Repeat this for every Word file in '/input/'...
for index, name in enumerate(word_files):
    # Provided that the current file is a Word file...
    current_path = os.path.dirname(__file__)+f"\\input\\{name}"
    print('\n---------------------------')
    print(f"Currently working on file: { current_path }")
    # Open the file and import it as a huge string
    text = docx2txt.process(current_path)
    # Each line in the text will be separated by each new line
    text = text.split('\n')
    # Trim out all the whitespace
    text = [ x for i,x in enumerate(text) if (x!='' and x!=' ') ]
    # And get the length of the resulting list
    text_length = range(len(text))
    current_task = tasks[index]
    # I then start to scan the text. Provided the user uses the
    # template provided, this sould work.
    stories.update( { current_task : {} } )
    for i, line in enumerate(text):
        line = line.replace("’", "'")
        # Scan each line of text until you find the header that marks
        # the start of a new story context.
        if line.lower().startswith('story'):
            # Clean the text up a bit and modify it until you have a
            # key that resembles the directory format the DM app
            # accepts ('story_{ story number }').
            story_index = line.lower().replace('.', '')
            story_index = story_index.lower().replace(' ', '')
            story_index = story_index.lower().replace('no', '_')
            story_index = story_index.lower().replace('No', '_')
            # Stick that into a dictionary of dictionaries where the
            # generated key marks the context of one story.
            stories[current_task].update( { story_index : {  } } )
            # Make a copy of the index of where you found the header.
            a = copy.deepcopy(i) + 1
            # Then grab the 'story context'. This will *hopefully*
            # come right after the story index. Halt the scan when you
            # see the next header.
            while a in text_length and not text[a].lower().startswith('preference'):
                story_context = list()
                # Until you see the next header, just grab whatever is
                # there.
                if text[a] != '':
                    story_context.append( text[a] )
                a += 1
            # When you're done, you'll have a list of strings. Join the
            # strings into one single string separated by spaces. This
            # takes any new lines into account.
            stories[current_task][story_index].update({ 'context' : [ '\n'.join([ str(x).strip() for x in story_context ]) ]\
                                         if len(story_context) > 1 else story_context })
        # Continues scanning for cost and reward preferences...
        elif line.lower().startswith('preference'):
            a = copy.deepcopy(i) + 1
            prefs = []
            item_number = 1
            # Take whatever is after this header until you reach the task questions.
            while a in text_length and not (text[a].lower().startswith('preference') or text[a].lower().startswith('task questions') or text[a].lower().startswith('story')):
                # Ignore anything that starts with a non-numeric
                # character and take it in for processing.
                string = re.split('\.|\)', text[a])[0]
                if string.isnumeric() or len(string) > 1:
                #if not (text[a].startswith('A.') or text[a].startswith('A)')):
                    # Take the number and parenthesis/dot out of string
                    prefs.append( str(item_number) + ') ' + re.sub(r'^[A-Z][^?!.]*[?.!]$', '', re.split(r'^([0-9]|[a-z])\.|\)', text[a].strip())[-1].strip()) )
                    item_number += 1
                a += 1
            stories[current_task][story_index].update({ line.strip().lower().replace('preference', 'pref').replace(' ', '_').replace('(', '').replace(')', '').replace(':', ''):\
                                          prefs })
        elif line.lower().replace(' ', '').replace(':', '').startswith('task'):
            a = copy.deepcopy(i) + 1
            questions = []
            while (a in text_length and not text[a].lower().startswith('story')):
                questions.append( re.split(r'^([0-9]|[a-z])\.|\) ', text[a].strip())[-1].strip() )
                a += 1
            stories[current_task][story_index].update({ 'questions' : questions })

# Create directories in output for each one of the stories...
print('\n---------------------------')
print("Creating directories and text files, please wait...")
for task in tasks:
    # Figure out which task you're on and create a directory under the task type's name.
    rootdirectory = bd.create_dir(task)
    for story, values in stories[task].items():
        # Then, for each entry in the dictionary that was created above (where each entry delimits a new story), create a directory for the task type and story number
        rootdirectory = bd.create_dir(task+'\\'+story)
        for key, item in values.items():
            # Read the stories dictionary and start writing the files for each of the entries (context, pref_reward, pref_cost, and questions).
            filename = rootdirectory+'\\'+key+'.txt'
            with open(filename, 'w') as f:
                # Write each item in the list separated by a new line until the end of the list.
                for line in item:
                    if (line != '' or line != ' '):
                        if (item.index(line) != len(item)-1):
                            f.write(line+'\n')
                        else:
                            f.write(line)
        # If the story entry is missing a 'questions' entry, write the questions from the prefs_cost and pref_reward files.
        if not ('questions' in values.keys()):
            print(f"  [WARNING] No questions were found for '{task}/{story}'. Attempting to generate questions file from preferences...")
            # reward_pref_file = rootdirectory+'\\pref_reward.txt'
            # cost_pref_file   = rootdirectory+'\\pref_cost.txt'
            # output_file      = rootdirectory+'\\questions.txt'
            # bd.write_questions(reward_pref_file, cost_pref_file, output_file)
            bd.write_questions(task, int(re.findall("\d+", story)[-1]))



print("\n>>>> Finished! You can now close this window! <<<<\n\n")
                    
            
                    

