# -*- coding: utf-8 -*-
"""
Created on Mon Dec  1 15:27:30 2025

@author: Raquel
"""

## Webserver-related imports
from flask import Flask, render_template, redirect, request, session, flash, url_for, template_rendered, make_response, send_from_directory
from flask_session import Session
from markupsafe import Markup
## System and file management
from os import listdir, path, getcwd
## Argument and settings parsing
from configparser import ConfigParser as cfgp
from argparse import ArgumentParser
from ast import literal_eval
## Other
from secrets import token_hex
import re
from datetime import datetime

# --------------------------- Classes and functions ---------------------------
class StoryVerify:
    def __init__(self, **kwargs):
        # Path where stories are located
        self.sto_dir   = path.abspath( kwargs.get('sto_dir', fr"{getcwd()}/stories/task_types") )
        # Containers for each story's file's raw text
        self.container = { 'context': None,
                           'pref_cost': None,
                           'pref_reward': None,
                           'questions': None }
        self.story_queue = None
        # Character encoder to use when opening files
        self.encoder   = kwargs.get('encoder', 'utf-8')
        self.encoderErrorHandle = kwargs.get('encoder_error', 'ignore')
        # General settings
        self.verbose = bool( kwargs.get('verbose', 0) )
    
    def absolute_filepath(self, directory, story_range=None):
        # Creates an iterable generator object containing the absolute path to
        # each of the files in the specified directory
        if story_range is None:
            for file in listdir( directory ):
                yield path.abspath( path.join(directory, file) )
        else:
            for i in story_range:
                yield path.abspath( fr"{directory}/story_{i}" )
        
    def open_story(self, task_type, number):
        # Opens all files associated with a story and loads them into their
        # respective containters
        files = self.absolute_filepath( path.abspath(fr"{self.sto_dir}/{task_type}/story_{str(number)}") )
        # Open each file
        for file in files:
            if self.verbose: print(f"\nFile: {file}")
            try:
                with open(file, 'r', encoding=self.encoder, errors=self.encoderErrorHandle) as f:
                    txt = f.read()
                    self.container[path.basename(file).split(r'.')[0]] = txt
            except Exception as e:
                print(f"\nCould not open file in path\n '{file}'\nException raised:\n {e}")
            else:
                pass
    
    def parse_context(self):
        try:
            return self.container['context'].replace("’", "'")
        except Exception as e:
            return f"Exception: '{e}'"
    
    def parse_cost(self):
        opt_dict = {}
        try:
            options = self.container['pref_cost'].split("\n")
            options = [line.strip() for line in options if (line != '' and line != ' ')]
            for option in options:
                if option != '':
                    line = option.split(")")
                    opt_num = int(line[0])
                    opt_description = line[1].replace("’", "'")
                    opt_dict[opt_num] = opt_description.strip()
        except Exception as e:
            opt_dict.update( {'Exception': f"Exception: '{e}'"} )
        finally:
            return opt_dict
    
    def parse_reward(self):
        opt_dict = {}
        try:
            options = self.container['pref_reward'].split("\n")
            options = [line.strip() for line in options if (line != '' and line != ' ')]
            for option in options:
                if option != '':
                    line = option.split(")")
                    opt_num = int(line[0])
                    opt_description = line[1].replace("’", "'")
                    opt_dict[opt_num] = opt_description.strip()
        except Exception as e:
            opt_dict.update( {'Exception': f"Exception: '{e}'"} )
        finally:
            return opt_dict
    
    def parse_questions(self):
        quest_dict = {}
        try:
            lines = self.container['questions'].split("\n")
            lines = [line.strip() for line in lines if (line != '' and line != ' ')]
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
                RC = re.findall("\d+", linelist[1]) # Take only the numeric values in this part of the string.
                # RC will contain a variable length list of string numbers. A length of
                # 4 will more than likely indicate that the current task is the
                # multi-choice task. This is the only task type where the questions are
                # tagged as (RxCy RaCb). I want to consider all posibilities though!
                keytup = ()
                for x in RC:
                    keytup = keytup + (int(x),)
                quest_dict.update({ keytup: Markup(question) })
        except Exception as e:
            quest_dict.update( {'Exception': f"Exception: '{e}'"} )
        finally:
            return list( quest_dict.items() )
    
    def check_range(self, x, y):
        return y[0] >= x[0] and y[-1] <= x[-1] if len(y) > 1 else True
# --------------------------------- end class ---------------------------------
    
class ParserTools:
    def __init__(self, **kwargs):
        self.settings_path = path.abspath(kwargs.get('settings_path', r'bin/settings.ini'))
        
    def parser(self, section, eval_datatype):
    # Returns settings from ini file as dict
    
        # Create a parser
        parser = cfgp()
        # Read config file
        parser.read(self.settings_path)
    
        # Find the appropriate section, defaults to postgresql
        db = {}
        if parser.has_section(section):
            params = parser.items(section)
            for param in params:
                db[param[0]] = param[1]
        else:
            raise Exception('\n[ParserTools] Section {0} not found in the {1} file'.format(section, self.settings_path))
    
        if eval_datatype:
            for key, value in db.items():
                if value.isnumeric():
                    db[key] = literal_eval(value)
                elif value.startswith('['):
                    db[key] = literal_eval(value)
                
        return db
    
    def without_keys(self, d, keys):
    # Removes key-value pairs from dictionary
        return {x: d[x] for x in d if x not in keys}
    
    def parse_ini(self, section='app_settings',
                        eval_datatype=False,
                        exclude_keys=[] ):
        return self.without_keys( self.parser( section=section,\
                                               eval_datatype=eval_datatype),\
                                 exclude_keys)
    
    def read_dir_map(self, rootdir, restrict_numeric=False, get_full_filenames=False):
    # Returns the structure of the given directory as a dictionary.
        
        dir_map = {}
        # Get the task types directories as a list.
        # folders = listdir(rootdir)
        folders = [ name for name in listdir(rootdir) if path.isdir(path.join(rootdir, name)) and (name.isnumeric() if restrict_numeric else True) ]
        
        for folder in folders:
            # Get the directories inside each task type directory as a list.
            dirs = listdir(rootdir+'/'+folder)
            if len(dirs) > 0:
                # If the directory is populated...
                for i in range(len(dirs)):
                    # Take only the story number from the directory names...
                    dirs[i] = dirs[i] if get_full_filenames else dirs[i].split('_')[-1]
            # ...then populate the dictionary with 'task type': 'stories for
            # in that task type'.
            dirs.sort(reverse=True)
            dir_map.update({folder: dirs})
    
        return dir_map
# --------------------------------- end class ---------------------------------

# ------------------------------ Configure flask ------------------------------
app = Flask(__name__, static_folder='static', template_folder='templates')
# Create a secret key to protect client side sessions. The secret key is needed
# to decode cookies information transfered to and from the host.
app.secret_key = token_hex(32)
app.config["SESSION_PERMANENT"] = False # Session data is deleted after session expires
app.config["SESSION_TYPE"] = "filesystem" # Session data is stored in the host
# Initialise the app with server-side sessions to handle user data
Session(app)

# ----------------------------- Flask routes ----------------------------------
# The following functions and routes will be what gets forked into threads.
# Each client will see their own version of each of these functions and the
# separation into threads will allow client concurrency when the app is run
# from a WSGI server.

@app.route('/', methods=['GET', 'POST'])
def setup():
    """
    -------
    Home page.
    
    Page has three inputs; the task type to verify, the first number
    of the first story to check, and the number of the last story to check.
    
    Upon submitting, the given range will be checked against the actual number
    of stories present in the indicated stories directory. If it is not within
    the range { 1 : <number of story folder in given task type> }, a message
    will be displayed indicating that the selected storry number are out of
    range.
    -------
    """
    session.clear()
    if request.method == 'POST':
        # Get inputs as dictionary
        settings = request.form.to_dict()
        # Get the number of folders present in the task type directories
        task_length = len(listdir( path.join(verify.sto_dir, settings['task']) ))
        # Create range objects (the '+ 1' creates an inclusive range)
        real_story_range = range(1, task_length + 1)
        input_story_range = range(int(settings['story0']), int(settings['story1']) + 1)
        # Check if given range is in range
        if not verify.check_range(list(real_story_range), list(input_story_range)):
            # Display error message
            flash(f"Stories out of range. Task type '{settings['task']}' has {task_length} stories.", 'danger')
        else:
            # Save the story range as an iterable to iterate through stories
            verify.story_queue = iter(input_story_range)
            session.update( { 'story0'  : settings['story0'],
                              'story1'  : settings['story1'],
                              'task'    : settings['task'],
                              'next'    : int(settings['story0']),
                              'ts'      : datetime.now().strftime('%d%b%Y-%H%M%S'),
                              'results' : {} } )
   
            return redirect( f"/story/{next(verify.story_queue)}" )
    
    return render_template('verify-setup.html', 
                           default_dir=verify.sto_dir,
                           task_types=listdir(verify.sto_dir) )

@app.route('/story/<story_num>', methods=['GET', 'POST'])
def display_story(story_num):
    """
    ----------
    Display a story.
    
    Renders every story element (context, preference items, and trial
    questions) in the same way that the app does.
    
    The user may then flag a particular element or the content of the story as
    a whole.
    ----------
    Parameters
    ----------
    story_num : STR or INT
        The story number to display. This is passed on by the redirecting
        page.
    """
    # Open story files
    verify.open_story(session['task'], story_num)
    # Parse the different files according to their type
    context      = verify.parse_context()
    pref_cost    = verify.parse_cost()
    pref_reward  = verify.parse_reward()
    questions    = [ q[-1] for q in verify.parse_questions() ]
    
    button_label = "Next" if int(story_num)+1 <= int(session['story1']) else "Finished"
    
    if request.method == 'POST':
        # Get all user flags (if any)
        content = request.form.to_dict()
        flags = {}
        notes = {}
        for key, item in content.items():
            if key.startswith('notes'):
                notes.update( { key.split('-')[-1]: item } )
                try:
                    flags.update( { key.split('-')[-1]: content[f"flag-{key.split('-')[-1]}"] } )
                except:
                    flags.update( { key.split('-')[-1]: False } )
        
        session['results'].update( { story_num: [flags, notes] } )
                
        # Redirect to the next story, if there is one
        try:
            return redirect( f"/story/{next(verify.story_queue)}" )
        except:
            return redirect( "/summary" )
    
    return render_template('verify-display.html',
                           story_num   = story_num,
                           task_type   = session['task'],
                           context     = context,
                           pref_cost   = pref_cost,
                           pref_reward = pref_reward,
                           questions   = questions,
                           button_lab  = Markup(button_label))

@app.route('/summary', methods=['GET', 'POST'])
def summary():
    msg = f"Task type: {session.get('task')}\n"
    for key, item in session['results'].items():
        msg += f"\n Story {str(key)} ({verify.sto_dir}\{session.get('task')}\story_{key})\n"
        msg += "  Flagged items:\n"
        for k in item[0]:
            if item[0][k] == 'True':
                msg += f"   '{k}'\n"
        msg += "  Notes:\n"
        for k in item[1]:
            msg += f"   {k}: '{item[1][k]}'\n"
    
    with open( path.abspath(fr"{getcwd()}/verify-log_{session.get('ts')}.txt"), 'a' ) as f:
        f.write(msg)
    
    if request.method == 'POST':
        return redirect("/")
    return render_template('verify-summary.html',
                           summary = f"Summary log has been written to {getcwd()}\verify-log_{session.get('ts')}.txt" )

# --------------------- Run this when script is executed ----------------------
if __name__ == '__main__':

# ----------------------- Parse commandline arguments -------------------------
    # Define the parser
    argparser = ArgumentParser(add_help=False)
    # Declare an argument, using a default value if the argument 
    # isn't given
    argparser.add_argument('-e', '--encoder', dest='encoder', default='utf-8')
    argparser.add_argument('-i', '--story_path', dest='story_path', default=path.join(getcwd(), r"stories\task_types") )
    argparser.add_argument('-v', '--verbose', dest='verbose', default=False, action='store_true')
    argparser.add_argument('-err', '--enc_err', dest='encoder_error', default='ignore')


    # Now, parse the command line arguments and store the values in the 'args'
    # variable.
    args = argparser.parse_args()
    # Convert Namespace args to dictionary
    # args = vars(args)
    
    verify = StoryVerify( **vars(args) )
    
    host_ip = r"127.0.0.1"
    host_port = 5000

    print("Flask (debug)")
    # Runs local flask server in debug mode
    app.run(host=host_ip, port=host_port, debug=True)
# -----------------------------------------------------------------------------