"""
Human Decision Making App v32.4.4
09/October/2023 updated 06/Nov/2025
@authors: Lara Rakocevic and Raquel Ibáñez Alcalá and Joshua Xiong
"""

## Webserver-related imports
import itertools
import json
import os

## Utility imports
import re
import sys
import time
import csv
import io
from argparse import ArgumentParser
from ast import literal_eval
from configparser import ConfigParser as cfgp
from copy import deepcopy
from datetime import datetime
from random import randint, sample, shuffle
from secrets import token_hex
from shutil import copy2
from subprocess import Popen
from zoneinfo import ZoneInfo

## Custom libraries
from flask import (
    Flask,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    template_rendered,
    url_for,
)
from flask_session import Session

# from flask_limiter import Limiter
# from flask_limiter.util import get_remote_address
from markupsafe import Markup
from pdf_signer import PDFSigner
from waitress import serve

# -------------------------- Configure flask session --------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
# Delcare rate limiter to prevent DDoS or server overload;
# Deactivate this when debugging...
# limiter = Limiter(
#     get_remote_address,
#     app=app,
#     default_limits=["5 per day"] )
# Create a secret key to protect client side sessions. The secret key is needed
# to decode cookies information transfered to and from the host.
app.secret_key = token_hex(32)
app.config["SESSION_PERMANENT"] = False  # Session data is deleted after session expires
app.config["SESSION_TYPE"] = "filesystem"  # Session data is stored in the host
# Initialise the app with server-side sessions to handle user data
Session(app)
# -----------------------------------------------------------------------------


# ------------------------------ App functions --------------------------------
def parse_ini(filename="bin/settings2.ini", section="postgresql", eval_datatype=False):
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
        raise Exception(
            "\nSection {0} not found in the {1} file".format(section, filename)
        )

    if eval_datatype:
        for key, value in db.items():
            if value.isnumeric():
                db[key] = literal_eval(value)
            elif value.startswith("["):
                db[key] = literal_eval(value)
            elif value.startswith("$"):
                db[key] = os.environ.get(value.split("$")[-1])

    return db


def without_keys(d, keys):
    return {x: d[x] for x in d if x not in keys}


def create_data_dir(pid):
    path = os.getcwd()
    dir_to_create = os.path.abspath(f"{path}/graph_data/{str(pid)}")
    try:
        os.mkdir(dir_to_create)
    finally:
        return dir_to_create


def get_new_id(reference_from="database"):
    subjectidnumber = str(randint(10000, 99999))

    return subjectidnumber


## Functions start getting messy here, revise? Namely, make them less dependent
## on globally declared variables where possible (f.e. remove implicit
## use of Session object and app settings).

def write_to_db(response):
    trial_start = session.get("trial_start", (None, None))
    trial_end = session.get("trial_end", (None, None))

    start_ts = trial_start[0]
    end_ts = trial_end[0]
    page = trial_start[1]

    if start_ts is not None and end_ts is not None:
        elapsed = end_ts - start_ts
        trial_start_str = start_ts.strftime("%a %b %d %H:%M:%S.%f %Y %Z")
        trial_end_str = end_ts.strftime("%a %b %d %H:%M:%S.%f %Y %Z")
        trial_elapsed_str = str(elapsed)
    else:
        trial_start_str = None
        trial_end_str = None
        trial_elapsed_str = None

    record = {
        "subjectidnumber": session.get("subjectidnumber"),
        "sex": session.get("sex"),
        "phase": session.get("phase"),
        "question_id": session.get("question_id"),
        "question_order": session.get("question_order"),
        "option_order": json.dumps(session.get("option_order")),
        "response": json.dumps(response),
        "trial_start": trial_start_str,
        "trial_end": trial_end_str,
        "trial_elapsed": trial_elapsed_str,
        "page": page
    }
    print("RECORD TO WRITE: " + str(record))

    records = session.get("csv_records", [])
    records.append(record)

    session["csv_records"] = records

def set_session_params(data=None, op="update", exclude=[], verbose=False):
    # Allocates a dictionary in memory to save data into the flask-session data
    # structure.
    expected_op = [r"set/reset", r"update"]
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
            sesh.update(
                {
                    # Update data table-relevant entries to initialize them to the
                    # correct data type.
                    "question_id": None,
                    "trial_start": (None, None),
                    "trial_end": (None, None),
                    "option_order": None,
                    # Performance entries
                    "exclude": [],  # Keys to exclude from database uploads and demographic data writes.
                }
            )
            data = sesh
        else:
            print("\nPlease pass a list of keys to 'data' to set session parameters.")
            return False
    elif op == "update":
        # Do not accept None, non-dictionary types, or empty dictionaries
        if data is None or not isinstance(data, dict) or data == {}:
            print(
                f"\nCannot write '{data}' to session data, please pass a dictionary with data to parameter 'data'."
            )
            return False
        else:
            for key in exclude:
                del data[key]
    else:
        print(f"\nValid inputs to parameter 'op' are {expected_op}.")
        return False

    try:
        print(
            f"\n{'Updating' if op == 'update' else 'Allocating/Resetting'} session parameters{':' if op == 'update' else ''}",
            end="",
        )
        if op == "update" and verbose:
            print("")
            i = 1
            for key, value in sorted(data.items()):
                print(f"{i}. {key}: {value}")
                i += 1
            print("")
        print("..................", end="")

        if op == "set/reset":
            session.clear()

        session.update(data)

    except Exception as e:
        print(f"failed!\nSession data was not written successfully due to error:\n{e}")
        return False
    else:
        print("success!")
        if op == "update" and verbose:
            print("\nSession has been updated to:")
            i = 1
            for key, value in sorted(session.items()):
                print(f"{i}. {key}: {value}")
                i += 1
        else:
            print(f"\nSet {len(list(session.keys()))} entries in session.")
        print("\n")
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
    observed_paths = app_settings.get("observed_urls", tuple(r"/p"))
    print(f"[SIGNAL.TEMPLATE_RENDERED] Rendered template {template.name or 'string template'} at timestamp {timestamp} in url {page}")

    session["trial_start"] = (timestamp, page)
    session["trial_end"] = (None, None)
    print(f"[SIGNAL.TEMPLATE_RENDERED] Logged 'trial_start'\n Start: {str(session['trial_start'])}\n End: {str(session['trial_end'])}")


def sign_pdf(
    idno,
    name,
    signature,
    proxysignature=None,
    stamp_document=True,
    include_timestamp=True,
):
    signer = PDFSigner(
        output_dir=os.path.abspath(f"{os.getcwd()}/graph_data/{idno}"),
        output_name=f"informed_consent_signed_{idno}",
        ts_region=app_settings.get("timestamp_timezone", "UTC"),
    )

    if not os.path.isdir(signer.output_dir):
        signer.make_directory()

    try:
        document = signer.open_pdf()

        # Sign participant's name
        signer.sign_name(document, name, line_index=[0])
        # Sign date in both "Date" lines
        signer.sign_date(document, signer.ts_short, line_index=[2, 4])
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
            signer.writeonpdf(
                document,
                datetime.now(signer.ts_region).strftime(signer.ts_format),
                x=230,
                y=730,
                use_selfcoords=False,
            )

        signer.save_pdf()
    finally:
        signer.close_pdf()
        del document, signer


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Helper functions for parsing the new question format

def tsv_to_dict(filepath):
    result = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            key = int(row[0])
            value = row[1].strip()
            result[key] = value
    return result

def reverse_map(map):
    reversed_map = {}
    for k in map:
        reversed_map[map[k]] = "indiv_" + str(k)
    return reversed_map

def multi_tsv_to_dict(filepath):
    result = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            key = int(row[0])

            # Split on |
            choices = row[1].split("|")

            parsed_choices = []
            for choice in choices:
                choice = choice.strip()
                parsed_choices.append(choice)

            result[key] = parsed_choices
    return result

def get_rand_order(qmap):
    ordermap = {}
    for k in qmap:
        choices = qmap[k]
        perm_order = list(range(len(choices)))
        shuffle(perm_order)
        print(choices)
        print(perm_order)
        indiv_qids = [qid_map[choices[i]] for i in perm_order]
        ordermap[k] = (perm_order, indiv_qids)
    return ordermap

def get_phase_map(idxs, orders):
    phases = {
        "indiv": {
            "qs": indiv_qs,
            "template": "indiv_prefs.html",
            "next": "pairs",
            "instructions": "instructions.html"
        },
        "pairs": {
            "qs": pairs_qs,
            "template": "pairs_prefs.html",
            "next": "rerate",
            "instructions": "pairs_instructions.html"
        },
        "radio": {
            "qs": radio_qs,
            "template": "mult_choice.html",
            "next": "finished",
            "instructions": "radio_instructions.html"
        },
        "rerate": {
            "qs": indiv_qs,
            "template": "indiv_prefs.html",
            "next": "radio",
            "instructions": "rerate_instructions.html"
        },
        "rerate2": {
            "qs": indiv_qs,
            "template": "indiv_prefs.html",
            "next": "finished",
            "instructions": "rerate_instructions.html"
        }
    }
    for key in idxs:
        phases[key]["idx"] = idxs[key]
    for key in orders:
        phases[key]["order"] = orders[key]
    return phases
    
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

# ------------------------------- Initialize app ------------------------------
print("\nPerforming initial setup operations, please wait...")

# 2. Determine the current working directory and scan the "data" folder
wd = os.getcwd()
# Create a 'data' directory if it doesn't exist in case app is run for the
# first time.
if not os.path.isdir(os.path.abspath(wd + "/graph_data")):
    os.mkdir(os.path.abspath(wd + "/graph_data"))

# 3. Parse app settings
# Parse bin\settings.ini
server = without_keys(
    parse_ini(section="postgresql", eval_datatype=True), {}
)  # Parse server credentials from ini.
app_settings = without_keys(
    parse_ini(section="app_settings", eval_datatype=True), {}
)  # Parse app settings from ini.

timezone = ZoneInfo(app_settings.get("timestamp_timezone", "UTC"))
# Tweak settings
app_settings["exclude_columns"].append("num_stories")
app_settings["observed_urls"] = tuple(rf"{i}" for i in app_settings["observed_urls"])

# 4. Parse db_cols_2.json to figure out what data to upload
try:
    with open("bin/db_cols_2.json", "r") as f:
        data_cols = json.load(f)
except Exception as e:
    print(
        f"\nUnable to parse what data to upload to database, please provide a JSON file with column names in /bin/.\nError when parsing JSON file: {e}"
    )
    sys.exit(1)


# 6. Get the questions as a dictionary, where the key is the question number as an int.
indiv_qs = tsv_to_dict("survey/indiv.txt")
pairs_qs = multi_tsv_to_dict("survey/pairs.txt")
radio_qs = multi_tsv_to_dict("survey/radio.txt")
qid_map = reverse_map(indiv_qs)

# 7. Define the workflow
submit_timeout_ms = 5000

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
    referrer = (
        request.referrer.split(":".join([host_ip, str(host_port)]))[-1]
        if not request.referrer is None
        else "None"
    )  # The url path from the previous page
    retrival = (
        request.headers["Accept"].split(",")[0] if request.method == "GET" else None
    )  # The content (either html or css) that was downloaded, typically 'text/css' or 'text/html'

    if True:
        if request.method == "POST":
            session["trial_end"] = (timestamp, request.path)
            print(
                f"[BEFORE, POST] Logged 'trial_end'\n Start: {str(session['trial_start'])}\n End: {str(session['trial_end'])}\n Elapsed: {str(session['trial_end'][0] - session['trial_start'][0])}"
            )
            print(
                f"[BEFORE, POST] Timestamp: {timestamp.strftime('%a %b %d %H:%M:%S.%f %Y %Z')} on path {request.path}, referred from {referrer}"
            )
            if app_settings["data_upload"] and not request.path.startswith(r"/trial/"):
                print("[BEFORE, POST] Writing to database...")
                write_to_db(request.form.to_dict())

        elif (
            request.method == "GET"
            and retrival != r"text/css"
            and not referrer == "None"
            and session["trial_end"][0] is None
            and not session["trial_start"][0] is None
        ):
            session["trial_end"] = (timestamp, referrer)
            print(
                f"[BEFORE, GET] Logged 'trial_end'\n Start: {str(session['trial_start'])}\n End: {str(session['trial_end'])}\n Elapsed: {str(session['trial_end'][0] - session['trial_start'][0])}"
            )
            print(
                f"[BEFORE, GET] Timestamp: {timestamp.strftime('%a %b %d %H:%M:%S.%f %Y %Z')} on path {request.path}, referred from {referrer}, retrieved {retrival}"
            )
            if app_settings["data_upload"] and not request.path.startswith(r"/trial/"):
                print("[BEFORE, GET] Writing to database...")
                write_to_db({})


# Login
@app.route("/", methods=["GET", "POST"])
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
    excluded = app_settings["exclude_columns"]
    if request.method == "POST":
        if "new_participant" in request.form:
            # Try to set up a session
            if not set_session_params(
                data=list(data_cols.keys()),
                op="set/reset",
                verbose=bool(app_settings.get("verbose", 0)),
            ):
                flash("Could not initialize a session for user.", "danger")
                redirect("/new")

            # Create a new id
            print(session.get("subjectidnumber", None))
            if session.get("subjectidnumber", None) is None:
                new_id = get_new_id(reference_from=app_settings["unique_ids_from"])
                print(f"\nCreated user ID: {str(new_id)}.\n")

            rand_num = randint(10**8, (10**9) - 1)
            # Save to session
            set_session_params(
                data={"subjectidnumber": new_id, "rand_num": rand_num, "phase": "register", "csv_records": []},
                op="update",
                verbose=bool(app_settings.get("verbose", 0)),
            )
            # return redirect("/new")
            return redirect(url_for("consent"))

    return render_template("start_age_gate.html")


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
        pattern_names = r"^[A-Za-z]+(?:[ -][A-Za-z]+)*$"
        # Pattern explanation: String must start with one or more letters
        # and contain 2 or more all-letter-words separated by a hyphen (-)
        # or a space.
        pattern_initials = r"\b(?:[A-Z]\.?){2,}\b"
        # Pattern explanation: String must be two or more capital letters
        # optionally separated by a period (.).
        for key, value in data.items():
            value = value.strip()
            if key == "lname" and value == "":
                # Allow empty last name field (some cultures don't include this in their names).
                data['lname'] = " "
            elif not value == "" and not bool(re.search(pattern_names, value)):
                # If the string does not match this pattern for names, check if
                # it's initials...
                if not bool(re.search(pattern_initials, value)):
                    print(
                        f"Detected non-compliant string in key '{key}' with value '{value}'"
                    )
                    flash(
                        "Name fields must have one or more words containing only letters, separated by either a space or a hyphen (-). Initials fields must be only capital letters optionally separated by a period (.).",
                        "danger",
                    )
                    return render_template("consent_form.html")

        # Check if the file exists
        if not os.path.exists(
            os.path.abspath(
                rf"{os.getcwd()}/graph_data/informed_consent_signed_{session['subjectidnumber']}.pdf"
            )
        ):
            sign_pdf(
                session.get("subjectidnumber"),
                f"{data['fname']} {data['lname']}",
                data["initials"],
                proxysignature=data["proxyinit"]
                if not data["proxyinit"] == "" or None
                else None,
                stamp_document=True,
                include_timestamp=True,
            )

        if "continue" in request.form:
            if "phase_map" in session:
                return redirect("/new")
            idxs = {
                "indiv": sample(range(1, len(indiv_qs) + 1), len(indiv_qs)),
                "rerate": sample(range(1, len(indiv_qs) + 1), len(indiv_qs)),
                "rerate2": sample(range(1, len(indiv_qs) + 1), len(indiv_qs)),
                "pairs": sample(range(1, len(pairs_qs) + 1), len(pairs_qs)),
                "radio": sample(range(1, len(radio_qs) + 1), len(radio_qs))
            }
            orders = {
                "pairs": get_rand_order(pairs_qs),
                "radio": get_rand_order(radio_qs)
            }
            phase_map = get_phase_map(idxs, orders)
            starting_params = {
                "phase": "indiv",
                "question_order": 0,
                "phase_map": phase_map
            }
            set_session_params(
                data=starting_params, op="update", verbose=bool(app_settings.get("verbose", 0))
            )
            return redirect("/new")
        elif "download" in request.form:
            path = os.path.abspath(f"{os.getcwd()}/graph_data/{session['subjectidnumber']}")
            return send_from_directory(
                path,
                f"informed_consent_signed_{session['subjectidnumber']}.pdf",
                as_attachment=True,
            )

    return render_template("consent_form_survey.html")

@app.route("/new", methods=["GET", "POST"])
def new_participant():
    excluded = app_settings["exclude_columns"]
    subjectidnumber = session["subjectidnumber"]
    print("Subjectidnumber: " + subjectidnumber)

    if request.method == "POST":
        args = request.form.to_dict()

        # Update session
        set_session_params(
            data=args, op="update", verbose=bool(app_settings.get("verbose", 0))
        )

        return redirect("/instructions")

    return render_template("get_demographic_info.html")

@app.route("/instructions", methods=["GET", "POST"])
def instructions():
    if request.method == "POST":
        return redirect("/trial")
    return render_template(session["phase_map"][session["phase"]]["instructions"])

@app.route("/trial", methods=["GET", "POST"])
def trial_handler():
    phases = session["phase_map"]
    phase = session["phase"]
    qs = phases[phase]["qs"]
    idxs = phases[phase]["idx"]

    idx = int(session["question_order"])
    question = qs[idxs[idx]]
    session["question_id"] = phase + "_" + str(idxs[idx])

    shuffled_choices = None
    if phase == "radio" or phase == "pairs":
        perm_order = phases[phase]["order"][idxs[idx]][0]
        shuffled_choices = [question[i] for i in perm_order]
        session["option_order"] = phases[phase]["order"][idxs[idx]][1]

    if request.method == "POST":
        if (idx + 1 < len(qs)):
            set_session_params(
                data = {
                    "phase": phase,
                    "question_order": idx + 1,
                    "response": request.form.to_dict()
                }, 
                op="update", 
                verbose=bool(app_settings.get("verbose", 0))
            )
        else:
            set_session_params(
                data={
                    "phase": phases[phase]["next"],
                    "question_order": 0,
                    "question_id": None,
                    "response": request.form.to_dict()
                }, 
                op="update", 
                verbose=bool(app_settings.get("verbose", 0))
            )
            if phases[phase]["next"] == "finished":
                return redirect("/finished")
            else:
                return redirect("/instructions")
        return redirect("/trial")
    return render_template(
        phases[phase]["template"],
        trial_number = idx + 1,
        timeout = submit_timeout_ms,
        question = question,
        choices = shuffled_choices
    )


# Page which appears when user logs into app but has completed all their stories.
@app.route("/finished", methods=["GET", "POST"])
def final_end():
    if request.method == "POST":
        return redirect("/download_csv")
    return render_template(
        "end_confirm.html",
        rand_num = session["rand_num"]
    )

@app.route("/download_csv")
def download_csv():
    records = session.get("csv_records", [])
    output = io.StringIO()

    if records:
        writer = csv.DictWriter(
            output,
            fieldnames=records[0].keys()
        )

        writer.writeheader()
        for row in records:
            writer.writerow(row)

    response = make_response(output.getvalue())
    response.headers["Content-type"] = "text/csv"
    response.headers[
        "Content-Disposition"
    ] = f"attachment; filename=participant_{session['subjectidnumber']}.csv"

    return response

# -----------------------------------------------------------------------------

# --------------------- Run this when app.py is executed ----------------------
if __name__ == "__main__":
    # ----------------------- Parse commandline arguments -------------------------
    # Define the parser
    argparser = ArgumentParser(add_help=False)
    # Declare an argument, using a default value if the argument
    # isn't given
    argparser.add_argument("-h", "--host", dest="host_ip", default=r"127.0.0.1")
    argparser.add_argument("-p", "--port", dest="host_port", default="5000")
    argparser.add_argument("-md", "--mode", dest="mode", default="dev")
    argparser.add_argument("-v", "--verbose", dest="verbose", default="0")
    argparser.add_argument("-th", "--threads", dest="threads", default="4")
    # Now, parse the command line arguments and store the values in the 'args'
    # variable.
    args = argparser.parse_args()
    # -----------------------------------------------------------------------------

    # ------------------- Decide what server to run the app in --------------------
    print(f"Running {'Waitress' if args.mode == 'prod' else 'Flask'} WSGI server.\n")
    if args.mode == "prod":
        host_ip = args.host_ip
        host_port = int(args.host_port)
        threads = int(args.threads)
        print(
            f"Forced 'academic_version' from {app_settings['academic_version']} to 0."
        )
        app_settings.update({"academic_version": 0, "verbose": int(args.verbose)})

        print("Waitress")
        serve(
            app, host=host_ip, port=host_port, threads=threads, url_prefix="/humans-app"
        )
    elif args.mode == "local":
        host_ip = args.host_ip
        host_port = int(args.host_port)
        app_settings.update({"verbose": int(args.verbose)})

        print("Flask")
        # Runs regular flask server with debug=False
        app.run(host=host_ip, port=host_port)
    else:
        host_ip = r"127.0.0.1"
        host_port = int(args.host_port)
        app_settings.update({"verbose": int(args.verbose)})

        print("Flask (debug)")
        # Runs local flask server in debug mode
        app.run(host=host_ip, port=host_port, debug=True)
# -----------------------------------------------------------------------------
