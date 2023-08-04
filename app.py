from flask import Flask, render_template, redirect, Markup, request
import re
import ast
import itertools
import random
import time
import subprocess
import numpy as np
import copy
import os
import fnmatch
import psycopg2
from configparser import ConfigParser as cfgp

## global app params
app = Flask(__name__, static_folder='static', template_folder='templates')
current_story_indx = 0
stories_in_session = 3
max_story_indx = stories_in_session
story_num_overall = 1
trial_num = 0
num_qs_in_story = 16
total_number_of_stories = 22
relevant_questions = []
story_order = []
min_stories_to_choose = 12

## subject params
participant_id = ''
cost_prefs = []
reward_prefs = []
story_prefs = {}
trial_start = None 
trial_end = None 
current_question = None

def parse_ini(filename='bin/database.ini',
              section='postgresql'):
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
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))

    return db

def without_keys(d, keys):
        return {x: d[x] for x in d if x not in keys}

# This global variable will now have the server information. This can now be used wherever a
# server connection needs to be made.
server = without_keys( parse_ini(), {} )

def get_blurbs():

    path = "stories/story_blurbs.txt"
    txt = open(path).read()

    options = txt.split("\n")
    opt_dict = {}
    for option in options: 
        line = option.split(")")
        opt_num = int(line[0])
        opt_description = line[1]
        opt_dict[opt_num] = opt_description.strip()

    return opt_dict

def get_new_id():
    sql_qry = "SELECT DISTINCT(subjectidnumber) FROM human_dec_making_table ORDER BY subjectidnumber"
    data = []

    conn = psycopg2.connect(**server)
    cursor = conn.cursor()
    cursor.execute(sql_qry, data)

    raw_data = cursor.fetchall()

    cursor.close()
    conn.close()
    
    unique_ids = set([row[0] for row in raw_data])

    while True:
        participant_id = str(random.randint(10000,99999))
        if participant_id not in unique_ids:
            break

    return participant_id

# page for are you a new participant? 
@app.route('/',methods=['GET', 'POST'])
def select_stories():
    global stories_in_session
    global max_story_indx

    if request.method=="POST":
        num_stories = request.form['num_stories']
        stories_in_session = int(num_stories)-1
        max_story_indx = stories_in_session
        return redirect('/welcome')

    return render_template('setup_session.html')


@app.route('/welcome')
def welcome_participant():
    return render_template('welcome_participant.html')

def create_data_dir(pid):
    path = os.getcwd()
    dir_to_create = path + "\\data\\" + str(pid)
    os.mkdir(dir_to_create)

@app.route("/new", methods=['GET', 'POST'])
def new_participant():
    global participant_id

    if request.method=="POST":
        args = request.form.to_dict()
        filename = f"data/{participant_id}/demographic_info.txt"
        f = open(filename, 'a')
        for (k,v) in args.items():
            f.write(k + ": " + v + "\n")

        return redirect('/choose_stories')

    participant_id = get_new_id()
    create_data_dir(participant_id)
    return render_template('give_new_id.html', participant_id=participant_id)

@app.route("/choose_stories", methods=['GET','POST'])
def choose_stories():
    global story_order
    story_blurbs = get_blurbs()

    if request.method=="POST":

        ## TODO: FIX THE NOT PREF STORIES
        prefs = request.form.to_dict()
        pref_stories = [int(k) for (k,v) in prefs.items() if v]
        not_pref_stories = [int(k) for k in range(1,total_number_of_stories+1) if k not in pref_stories]

        if len(pref_stories) < min_stories_to_choose:
            return render_template("choose_stories_try_again.html", story_blurbs=story_blurbs,num_blurbs=len(story_blurbs),prev_yes=pref_stories, min_stories_to_choose = min_stories_to_choose)

        filename = f"data/{participant_id}/demographic_info.txt"
        f = open(filename, 'a')
        story_order = list(pref_stories)
        random.shuffle(story_order)

        ## add back in the rest of the stories at the end
        story_order = story_order + not_pref_stories
   
        f.write("pref stories: " + str(pref_stories) + "\n")
        f.write("story order: " + str(story_order))
        f.close()

        return redirect('/story_num_overall')

    return render_template('choosing_stories.html', story_blurbs = story_blurbs, num_blurbs = len(story_blurbs), min_stories_to_choose = min_stories_to_choose)

def get_story_order():
    global story_order
    filename = f"data/{participant_id}/demographic_info.txt"
    with open(filename) as f:
        lines = f.readlines()
        story_order = lines[-1]
        story_order_split = story_order.split(": ")
        order = story_order_split[1]

    story_order = ast.literal_eval(order)


def get_starting_story_indx(participant_id):
    global max_story_indx
    global current_story_indx

    sql_qry = f"""select count(distinct tasktypedone) from human_dec_making_table where subjectidnumber = '{str(participant_id)}'"""
    data = []

    conn = psycopg2.connect(**server)

    cursor = conn.cursor()
    cursor.execute(sql_qry, data)

    raw_num_stories = cursor.fetchone()

    cursor.close()
    conn.close()

    num_stories_completed = raw_num_stories[0] if raw_num_stories is not None else 0 

    current_story_indx = num_stories_completed
    max_story_indx = min(total_number_of_stories, num_stories_completed + stories_in_session)


@app.route("/not_new", methods=['GET','POST'])
def not_new_participant():
    global participant_id

    if request.method == "POST":
        participant_id = request.form['participant_id']
        if participant_id not in os.listdir("data"):
            create_data_dir(participant_id)
        get_starting_story_indx(participant_id)

        return redirect("/story_num_overall")

    return render_template('welcome_back.html')

@app.route('/story_num_overall')
def story_num_refresh():
    global story_num_overall
    get_story_order()
    story_num_overall = story_order[current_story_indx]

    blurbs = get_blurbs()
    blurb = blurbs[story_num_overall]
    return render_template('story_num.html', number=current_story_indx+1, content=blurb)

## context - read from file, click next -> to reward pref
@app.route('/context')
def context():
    path = f"stories/story_{story_num_overall}/context.txt"
    txt = open(path).read()
    return render_template('context.html', content=txt)

## enter values (+ save), click next -> to cost pref
## enter values (+ save), click next -> to context refresh
@app.route('/prefs/<cost_or_reward>', methods=['GET', 'POST'])
def rank_prefs(cost_or_reward):
    global cost_prefs
    global reward_prefs

    path = f"stories/story_{story_num_overall}/pref_{cost_or_reward}.txt"
    txt = open(path).read()

    options = txt.split("\n")
    opt_dict = {}
    for option in options: 
        line = option.split(")")
        opt_num = int(line[0])
        opt_description = line[1]
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

        return redirect("/prefs/cost") if cost_or_reward == 'reward' else redirect("/refresh")

    html = f"{cost_or_reward}_prefs.html"
    return render_template(html, len = len(options), opt_dict=opt_dict)

def choose_prefs(pref_dict):
    
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

    prefs = [k for (k,v) in pref_dict.items() if v in best_diff_list]

    return prefs

def choose_questions():
    path = f"stories/story_{story_num_overall}/questions.txt"
    txt = open(path).read()
    lines = txt.split("\n")
    quest_dict = {}
    for l in lines: 
        linelist = l.split("?")
        question = linelist[0] + "?"
        R, C = re.findall("\d+", linelist[1])
        quest_dict[(int(R),int(C))] = question

    print('reward prefs', reward_prefs)

    rewards = choose_prefs(reward_prefs)
    costs = choose_prefs(cost_prefs)

    relevant_keys = list(itertools.product(rewards, costs))

    print('relevant keys', relevant_keys)

    relevant_qs = {key: quest_dict[key] for key in relevant_keys}

    q_list = list(relevant_qs.items())
    random.shuffle(q_list)

    return q_list

## context refresh, click next -> trials
@app.route('/refresh')
def context_refresh():
    global relevant_questions
    path = f"stories/story_{story_num_overall}/context.txt"
    txt = open(path).read()
    relevant_questions = choose_questions()
    return render_template('refresh.html', content=txt)

def get_demographic_info(participant_id):
    filename = f'data/{participant_id}/demographic_info.txt'
    dem_dict = {}
    with open(filename) as f:
        for line in f:
            (key, val) = line.split(": ")
            dem_dict[key] = val.strip()

    return dem_dict


def write_trial_to_db(current_question, dec=None, trial_start=None, trial_end=None):

    r, c = current_question 
    if trial_start is not None:
        trial_elapsed = time.mktime(trial_end) - time.mktime(trial_start) 

        trial_start = time.asctime(trial_start)
        trial_end = time.asctime(trial_end)
    else:
        trial_elapsed, trial_end, trial_start = 0, 0, 0

    dem_dict = get_demographic_info(participant_id)

    sql_insert = """INSERT INTO human_dec_making_table (subjectidnumber,in_pain,tired,hungry,age_range,gender,
        chosen_tasks,task_order,tasktypedone,reward_prefs,cost_prefs,cost_level,reward_level,
        decision_made,trial_index,trial_start,trial_end,trial_elapsed,story_prefs) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

    to_insert = (participant_id, dem_dict['pain'], dem_dict['tired'], dem_dict['hunger'],dem_dict['age'],dem_dict['sex'], dem_dict['pref stories'], 
        dem_dict['story order'], story_num_overall,  str(reward_prefs), str(cost_prefs), c, r, dec, trial_num,
        trial_start, trial_end, trial_elapsed, str(story_prefs))
    
    conn = None

    try:
        print('making a connection')

        conn = psycopg2.connect(**server)
    
        cursor = conn.cursor()
        cursor.execute(sql_insert, to_insert)

        conn.commit()
        cursor.close()

    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()


def get_blurbs():

    path = "stories/story_blurbs.txt"
    txt = open(path).read()

    options = txt.split("\n")
    opt_dict = {}
    for option in options: 
        line = option.split(")")
        opt_num = int(line[0])
        opt_description = line[1]
        opt_dict[opt_num] = opt_description.strip()

    return opt_dict


@app.route('/want_change_prefs', methods=['GET'])
def ask_if_change_prefs():

    return render_template('want_change_prefs.html')


# after finishing trials, re-rank the prefs
@app.route('/refresh_prefs/<cost_or_reward>', methods=['GET', 'POST'])
def rank_prefs_again(cost_or_reward):
    global cost_prefs
    global reward_prefs

    path = f"stories/story_{story_num_overall}/pref_{cost_or_reward}.txt"
    txt = open(path).read()

    options = txt.split("\n")
    opt_dict = {}
    for option in options: 
        line = option.split(")")
        opt_num = int(line[0])
        opt_description = line[1]
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

        write_trial_to_db((7,7))

        if cost_or_reward == "reward":
            return redirect("/refresh_prefs/cost") 
        else:
            return redirect('/trial_end')

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

    if request.method == "POST":
        data = request.form.to_dict()
        vals = list(data.values())

        dec = vals[0]
        trial_end = time.gmtime()
        write_trial_to_db(current_question, dec, trial_start, trial_end)

        next_trial = trial_num + 1
        next_trial_str = '/trial/'+str(next_trial)

        if trial_num + 1 < num_qs_in_story:
            trial_num += 1
            return redirect(next_trial_str)
        else:
            current_story_indx += 1
            trial_num = 0
            return redirect('/want_change_prefs')
            
    tup, q = relevant_questions[trial_num-1]
    q = Markup(q)

    trial_start = time.gmtime()
    current_question = tup

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

    print(story_prefs)
    write_trial_to_db((0,0))

    return render_template('total_end.html')