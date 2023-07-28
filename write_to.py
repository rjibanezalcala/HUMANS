import psycopg2
import ast
import re
import fnmatch
import os
import time
from datetime import datetime

def get_demographic_info(participant_id):
    filename = f'data/{participant_id}/demographic_info.txt'
    dem_dict = {}
    with open(filename) as f:
        for line in f:
            (key, val) = line.split(": ")
            dem_dict[key] = val.strip()

    return dem_dict

def get_story_prefs(participant_id):

	filename = f"data/{participant_id}/story_prefs.txt"
	with open(filename) as f:
		lines = f.readlines()
		story_prefs = lines[0]

	story_prefs = story_prefs.replace("}{", ", ")
	story_prefs = ast.literal_eval(story_prefs)
	
	return story_prefs


def write_to_db(r, c, dec, trial_start, trial_end, story_num_overall, reward_prefs, cost_prefs, trial_num, participant_id):

	d1 = datetime.strptime(trial_start.strip(), "%a %b %d %H:%M:%S %Y")
	d2 = datetime.strptime(trial_end.strip(), "%a %b %d %H:%M:%S %Y")
	
	trial_elapsed = (d2 - d1).seconds
	dem_dict = get_demographic_info(participant_id)
	pref_stories = dem_dict['pref stories'] if 'pref stories' in dem_dict.keys() else []
	hunger = dem_dict['hunger'] if 'hunger' in dem_dict.keys() else ''
	tired = dem_dict['tired'] if 'tired' in dem_dict.keys() else ''
	pain = dem_dict['pain'] if 'pain' in dem_dict.keys() else ''

	story_prefs = get_story_prefs(participant_id)

	sql_insert = """INSERT INTO human_dec_making_table (subjectidnumber,in_pain,tired,hungry,age_range,gender,
	    chosen_tasks,task_order,tasktypedone,reward_prefs,cost_prefs,cost_level,reward_level,
	    decision_made,trial_index,trial_start,trial_end,trial_elapsed,story_prefs) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

	to_insert = (participant_id, pain, tired, hunger,dem_dict['age'],dem_dict['sex'], pref_stories, 
	    dem_dict['story order'], story_num_overall,  str(reward_prefs), str(cost_prefs), c, r, dec, trial_num,
	    trial_start, trial_end, trial_elapsed, str(story_prefs))

	conn = None


	try:
	    print('making a connection')
	    conn = psycopg2.connect(database='live_database', host='10.10.21.18', user='postgres', port='5432', password='1234')
	    cursor = conn.cursor()

	    cursor.execute(sql_insert, to_insert)

	    conn.commit()
	    cursor.close()

	except (Exception, psycopg2.DatabaseError) as error:
	    print(error)
	finally:
	    if conn is not None:
	        conn.close()


def get_prefs(participant_id, cost_or_reward, story_num):

	filename = f"data/{participant_id}/{cost_or_reward}_for_story_{story_num}.txt"
	txt = open(filename).read()
	pref_dict = ast.literal_eval(txt)
	return pref_dict

if __name__ == "__main__":

	participant_id='98945'

	path = f"data/{participant_id}"
	num_stories_completed = len(fnmatch.filter(os.listdir(path), 'trials_for_story_*.txt'))

	dem_dict = get_demographic_info(participant_id)
	story_order = ast.literal_eval(dem_dict['story order'])

	for i in range(0, num_stories_completed):
		story_num = story_order[i]

		cost_prefs = get_prefs(participant_id, 'cost', story_num)
		reward_prefs = get_prefs(participant_id, 'reward', story_num)

		trial_file = f"data/{participant_id}/trials_for_story_{story_num}.txt"
		with open(trial_file) as f:
			lines = f.readlines()
			for l in range(0,15):
				trial_line = 2*l 
				dec_line = 2*l + 1
				trial = lines[trial_line]
				dec = lines[dec_line]

				trial, trial_start = trial.split(" at time: ")
				dec, trial_end = dec.split(" at time: ")

				r, c = re.findall("\d+", trial)
				dec = re.findall("\d+", dec)

				write_to_db(r, c, dec[0], trial_start, trial_end, story_num, reward_prefs, cost_prefs, l, participant_id)