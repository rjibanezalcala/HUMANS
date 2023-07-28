import ast
from matplotlib import pyplot as plt
from matplotlib import cm
import numpy as np
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
from mpl_toolkits.axes_grid1 import make_axes_locatable
import statistics
from collections import Counter
from scipy.sparse import coo_matrix
import psycopg2
import pandas as pd
import itertools
import copy
from scipy import stats
import time
import sys
import math

###############
# syncing prefs across trials
###############

def get_meta_data(trial_table, col_name):

	return trial_table[col_name].iloc[-1]

def get_total_time(trial_table):
	# the total time it took for participant to complete all their trials

	return trial_table['trial_elapsed'].apply(lambda x: float(x)).sum()

def get_total_stories(trial_table, participant_id):

	trial_table = trial_table[trial_table['subjectidnumber'] == str(participant_id)]

	return len(set(trial_table['tasktypedone']))

def get_total_participants_for_story(trial_table):

	return len(set(trial_df['subjectidnumber']))

def get_prefs(trial_table, story_num, participant_id):

	trial_table = trial_table[(trial_table['tasktypedone'] == story_num) & (trial_table['subjectidnumber'] == str(participant_id))]

	trial_date = trial_table['trial_start'].iloc[0].strip()
	if len(trial_date) == 1:
		trial_date = "Mon May 22 00:00:00 1998"
	trial_tup = time.strptime(trial_date, "%a %b %d %H:%M:%S %Y")
	trial_date = time.mktime(trial_tup)

	## date of the switch = june 8, 2023
	time_tup = (2023,6,8,0,0,0,3,159,-1)
	switch_date = time.mktime(time_tup)

	reward_prefs = ast.literal_eval(trial_table['reward_prefs'].iloc[0])
	cost_prefs = ast.literal_eval(trial_table['cost_prefs'].iloc[0])

	return reward_prefs, cost_prefs, trial_date < switch_date

def get_story_order(trial_table, participant_id):

	trial_table = trial_table[trial_table['subjectidnumber']==str(participant_id)]

	return ast.literal_eval(trial_table['task_order'].iloc[0])

def get_story_prefs(trial_table, participant_id):

	trial_table = trial_table[trial_table['subjectidnumber']==str(participant_id)]

	story_prefs = trial_table['story_prefs'].unique()

	fin = {}
	for d in story_prefs:
		d = ast.literal_eval(d)
		fin.update(d)

	return fin

def choose_prefs(trial_table, participant_id, story_num, pref_dict, cost_or_reward, use_old_prefs):

	if use_old_prefs:
		return choose_prefs_old(trial_table, participant_id, story_num, pref_dict, cost_or_reward)
	return choose_prefs_new(pref_dict)

def choose_prefs_old(trial_table, participant_id, story_num, pref_dict, cost_or_reward):

	trial_table = trial_table[(trial_table['tasktypedone'] == str(story_num)) & (trial_table['subjectidnumber'] == str(participant_id))]

	trial_prefs = trial_table[cost_or_reward].unique()

	#print('trial prefs', cost_or_reward, trial_prefs)
	prefs = {int(k):int(v) for k,v in pref_dict.items() if k in trial_prefs}

	return prefs

def choose_prefs_new(pref_dict):
    
    pref_dict = {int(k):int(v) for k,v in pref_dict.items()}
    vals = sorted(list(pref_dict.values()))

    max_diff = 0
    index_combos = [i for i in itertools.combinations(range(0,6), 2)]

    best_diff_list = [] 
    for c in index_combos:
        ind1, ind2 = c
        copy_vals = copy.deepcopy(vals)
        del copy_vals[ind1]
        del copy_vals[ind2-1]

        new_diffs = [abs(e[1] - e[0]) for e in itertools.permutations(copy_vals, 2)]
        new_diff = sum(new_diffs)/len(new_diffs)

        if new_diff > max_diff: 
            max_diff = new_diff
            best_diff_list = copy_vals

    prefs = {k:v for (k,v) in pref_dict.items() if v in best_diff_list}

    return prefs

def map_prefs(trial_table, participant_id, story_num, pref_dict, cost_or_reward, use_old_prefs):

	chosen_pref_dict = choose_prefs(trial_table, participant_id, story_num, pref_dict, cost_or_reward, use_old_prefs)
	chosen_prefs = sorted(chosen_pref_dict, key=chosen_pref_dict.get)

	choice_range = list(range(1,5))
	pref_map = dict(zip(chosen_prefs, choice_range))

	return pref_map

def get_val(pref_map,x):

	return pref_map[int(x)]

def sync_trials(trial_table, story_num, participant_id):

	r_pref_dict, c_pref_dict, use_old_prefs = get_prefs(trial_table, story_num, participant_id)

	reward_pref_map = map_prefs(trial_table, participant_id, story_num, r_pref_dict, 'reward_level', use_old_prefs)
	cost_pref_map = map_prefs(trial_table, participant_id, story_num, c_pref_dict, 'cost_level', use_old_prefs)

	reward_keys = [str(x) for x in reward_pref_map.keys()] 
	cost_keys = [str(x) for x in cost_pref_map.keys()]

	trial_table = trial_table[trial_table['tasktypedone'] == str(story_num)]

	trial_table = trial_table[trial_table['reward_level'].isin(reward_keys)]
	trial_table  = trial_table[trial_table['cost_level'].isin(cost_keys)]

	trial_table['real_r'] = trial_table['reward_level'].apply(lambda x: get_val(reward_pref_map,x))
	trial_table['real_c'] = trial_table['cost_level'].apply(lambda x: get_val(cost_pref_map,x))

	trial_table['r_c_pair'] = list(zip(trial_table.real_r, trial_table.real_c))
	trial_table['decision_made'] = trial_table['decision_made'].apply(lambda x: int(x))

	dec_dict = dict(zip(trial_table['r_c_pair'], trial_table['decision_made']))

	return dec_dict

###############
# getting data
###############

def combine_normalize_rescale(trial_table, participant_ids, story_threshold):

	final_vals = Counter()
	tot_stories = 0
	for participant_id in participant_ids:
		story_prefs = get_story_prefs(trial_table,participant_id)
		story_order = get_story_order(trial_table,participant_id)

		n_stories = get_total_stories(trial_table, participant_id)

		for i in range(0,n_stories):
			story_num = story_order[i]
			
			story_score = int(story_prefs[str(story_num)]) if story_prefs else 50

			d = sync_trials(trial_table, story_num, participant_id)

			tot_vals = sum([v for k, v in d.items()])
			tot_qs = len(d)

			per_q = tot_vals / tot_qs

			scaled = {k:(v*story_score) for k,v in d.items()}
			renorm = {k: v/per_q for k,v in scaled.items()}

			tot_stories += 1
			final_vals += Counter(renorm)

	## play with the normalization here 
	final_vals = {(k[0]-1, k[1]-1):v/(tot_stories*100) for (k,v) in final_vals.items()}

	final_vals_fix = {}
	for i in range(0,4):
		for j in range(0,4):
			if (i,j) in final_vals.keys():
				final_vals_fix[(i,j)] = final_vals[(i,j)]
			else:
				final_vals_fix[(i,j)] = 0.5

	row, col, fill = zip(*[(*k, v) for k, v in final_vals_fix.items()])
	result = coo_matrix((fill, (col, row)), shape=(4, 4)).toarray()

	return result, tot_stories

def combine_n_normalize(trial_table, participant_ids, story_threshold):

	final_vals = Counter()
	tot_stories = 0
	for participant_id in participant_ids:
		story_order = get_story_order(trial_table,participant_id)

		n_stories = get_total_stories(trial_table, participant_id)
		for i in range(0,n_stories):
			story_num = story_order[i]

			d = sync_trials(trial_table,story_num, participant_id)
			tot_qs = len(d)

			tot_vals = sum([v for k, v in d.items()])
			per_q = tot_vals / tot_qs

			renorm = {k: v/per_q for k,v in d.items()}

			tot_stories += 1
			final_vals += Counter(renorm)

		## play with the normalization here 

	final_vals = {(k[0]-1, k[1]-1):v/(tot_stories) for (k,v) in final_vals.items()}

	final_vals_fix = {}
	for i in range(0,4):
		for j in range(0,4):
			if (i,j) in final_vals.keys():
				final_vals_fix[(i,j)] = final_vals[(i,j)]
			else:
				final_vals_fix[(i,j)] = 0.5

	row, col, fill = zip(*[(*k, v) for k, v in final_vals_fix.items()])
	result = coo_matrix((fill, (col, row)), shape=(4, 4)).toarray()

	return result, tot_stories

def combine_n_scale(trial_table, participant_ids, story_threshold):

	final_vals = Counter()
	tot_stories = 0
	for participant_id in participant_ids:
		story_order = get_story_order(trial_table,participant_id)
		story_prefs = get_story_prefs(trial_table,participant_id)

		n_stories = get_total_stories(trial_table, participant_id)

		for i in range(0,n_stories):
			story_num = story_order[i]
			
			story_score = int(story_prefs[str(story_num)]) if story_prefs else 50

			d = sync_trials(trial_table,story_num, participant_id)
			scaled = {k:(v*story_score) for k,v in d.items()}

			tot_stories += 1
			final_vals += Counter(scaled)

	## play with the normalization here 

	final_vals = {(k[0]-1, k[1]-1):v/(tot_stories*100*100) for (k,v) in final_vals.items()}

	final_vals_fix = {}
	for i in range(0,4):
		for j in range(0,4):
			if (i,j) in final_vals.keys():
				final_vals_fix[(i,j)] = final_vals[(i,j)]
			else:
				final_vals_fix[(i,j)] = 0.5

	row, col, fill = zip(*[(*k, v) for k, v in final_vals_fix.items()])
	result = coo_matrix((fill, (col, row)), shape=(4, 4)).toarray()

	return result, tot_stories

def combine_n_convert(trial_table, participant_ids, story_threshold):

	final_vals = Counter()
	pref_stories = 0

	for participant_id in participant_ids:
		story_order = get_story_order(trial_table, participant_id)
		story_prefs = get_story_prefs(trial_table, participant_id)

		n_stories = get_total_stories(trial_table, participant_id)

		for i in range(0,n_stories):
			story_num = story_order[i]
			
			story_score = int(story_prefs[str(story_num)]) if story_prefs else 50
			if story_score > int(story_threshold):
				pref_stories +=1
			
			final_vals += Counter(sync_trials(trial_table,story_num, participant_id))
						
		## play with the normalization here 

	final_vals = {(k[0]-1, k[1]-1):v/(pref_stories*100) for (k,v) in final_vals.items()}

	final_vals_fix = {}
	for i in range(0,4):
		for j in range(0,4):
			if (i,j) in final_vals.keys():
				final_vals_fix[(i,j)] = final_vals[(i,j)]
			else:
				final_vals_fix[(i,j)] = 0.5

	row, col, fill = zip(*[(*k, v) for k, v in final_vals_fix.items()])
	result = coo_matrix((fill, (col, row)), shape=(4, 4)).toarray()

	return result, pref_stories

def combine_n_convert_group_by_stories(trial_table, n_participants, story_num):

	unique_ids = trial_table['subjectidnumber'].unique()

	num_ids = len(unique_ids)
	final_vals = Counter()
	for i in range(0,num_ids):
		participant_id = unique_ids[i]

		final_vals += Counter(sync_trials(trial_table,story_num,participant_id))

	## play with the normalization here 

	final_vals = {(k[0]-1, k[1]-1):v/(num_ids*100) for (k,v) in final_vals.items()}

	row, col, fill = zip(*[(*k, v) for k, v in final_vals.items()])
	result = coo_matrix((fill, (col, row)), shape=(4, 4)).toarray()

	return result

###############
# new viz
###############

def viz_individual_stories(trial_table, participant_ids, n_stories):

	for participant_id in participant_ids:
		story_order = get_story_order(trial_table, participant_id)
		n_stories = get_total_stories(trial_table, participant_id)

		for i in range(0,n_stories):
			story_num = story_order[i]
			final_vals = sync_trials(trial_table, story_num, participant_id)

			final_vals = {(k[0]-1, k[1]-1):v/100 for (k,v) in final_vals.items()}

			final_vals_fix = {}
			for i in range(0,4):
				for j in range(0,4):
					if (i,j) in final_vals.keys():
						final_vals_fix[(i,j)] = final_vals[(i,j)]
					else:
						final_vals_fix[(i,j)] = 0.5

			row, col, fill = zip(*[(*k, v) for k, v in final_vals_fix.items()])

			result = coo_matrix((fill, (col, row)), shape=(4, 4)).toarray()

			title = "id: " + str(participant_id) + " story: " + str(story_num)
			imgName = str(participant_id) + "_story_" + str(story_num)
			figName =  f"all_maps/by_story/single_story_maps/{imgName}"

			viz(result, title, figName, 0, 1)


def viz(data, title, figName, vmin, vmax):

	fig = plt.figure()

	top = cm.get_cmap('Reds_r', 128)
	bottom = cm.get_cmap('Greens', 128)

	newcolors = np.vstack((top(np.linspace(0, 1, 128)), bottom(np.linspace(0, 1, 128))))
	ax = fig.add_subplot()

	newcmp = ListedColormap(newcolors, name='RedGreen')

	divider = make_axes_locatable(ax)
	cax = divider.append_axes("right", size="5%", pad=0.05)

	x = np.arange(1,5)
	y = np.arange(1,5)
	X,Y = np.meshgrid(x,y)
	
	psm = ax.pcolormesh(X, Y, data, cmap=newcmp, rasterized=True, vmin=vmin, vmax=vmax)
	fig.colorbar(psm, cax = cax)
	ax.set_xlabel('reward')
	ax.set_ylabel('cost')
	ax.set_title(title)
	fig.savefig(figName)


if __name__ == "__main__":

	group_by_stories = False
	group_by_participants = True

	new_combined = True
	re_normalized_combined = False
	scaled_by_relevance_combined = False
	scaled_normalized_combined = False

	num_participant_stories = 5
	session_timing = 25

	if group_by_participants:
		participant_id = sys.argv[1].rstrip()

		ids = pd.read_excel('ids.xlsx')
		id_dict = ids.set_index('ID').T.to_dict('list')

		for i in id_dict.items():
		    k,v = i
		    id_dict[k] = [str(int(x)) for x in v if not math.isnan(x)]

		int_id = int(participant_id)
		## all the keys of id dict are "primary ids", so if it looks for a secondary (or tertiary id) it'll fail - 
		## which is good bc that data will already be included in the primary id map
		if int_id in id_dict:
			participant_ids = id_dict[int_id]
		
		insert = "('" + "','".join(participant_ids) + "')"

		qry = f"SELECT * FROM public.human_dec_making_table where subjectidnumber in {insert}" 

	if group_by_stories:
		tasktypedone = sys.argv[1].strip()
		figName = f"all_maps/by_story/grouped_by_story_maps/{tasktypedone}"
		qry = f"SELECT * FROM public.human_dec_making_table where tasktypedone='{tasktypedone}'" 

	story_threshold = sys.argv[2]

	conn = psycopg2.connect(database='live_database', host='10.10.21.18', user='postgres', port='5432', password='1234')
	trial_cursor = conn.cursor()

	trial_cursor.execute(qry)
	trial_table = trial_cursor.fetchall()
	trial_df = pd.DataFrame(trial_table)
	trial_df.columns = ['subjectidnumber', 'in_pain', 'tired', 'hungry', 'age_range', 'gender', 'chosen_tasks','task_order','tasktypedone', 'reward_prefs','cost_prefs','cost_level','reward_level', 'decision_made','trial_index','trial_start','trial_end','trial_elapsed','story_prefs']

	if group_by_stories:
		num_participants = get_total_participants_for_story(trial_table)
		unique_ids = trial_df['subjectidnumber'].unique()
		a = combine_n_convert_group_by_stories(trial_df, unique_ids, tasktypedone)

	if group_by_participants:
		age_range = get_meta_data(trial_df, 'age_range')
		session_timing = get_total_time(trial_df)
		gender = get_meta_data(trial_df, 'gender')

		if re_normalized_combined:
			figName = f"all_maps/combined/new_combined_maps/{participant_id}"
			a, num_participant_stories = combine_n_normalize(trial_df, participant_ids, int(story_threshold))
		if scaled_by_relevance_combined:
			figName = f"all_maps/combined/scaled_by_relevance_combined_maps/{participant_id}"
			a, num_participant_stories = combine_n_scale(trial_df, participant_ids, int(story_threshold))
		if scaled_normalized_combined:
			figName = f"all_maps/combined/scaled_normalized_combined_maps/{participant_id}"
			a, num_participant_stories = combine_normalize_rescale(trial_df, participant_ids, int(story_threshold))
		if new_combined:
			figName = f"all_maps/combined/new_combined_maps/{participant_id}"
			a, num_participant_stories = combine_normalize_rescale(trial_df, participant_ids, int(story_threshold))

	if num_participant_stories > 2 and session_timing > 20:
		#viz_individual_stories(trial_df, participant_ids, num_participant_stories)
		if group_by_participants:
			title_str = "stories: " + str(num_participant_stories) + " timing (s): "+ str(session_timing) + " age : " + str(age_range) + " sex: " + str(gender)
			viz(a, title_str, figName, 0, 1)
		if group_by_stories:
			viz(a, "num participants: " + str(num_participants), figName, 0, 1)