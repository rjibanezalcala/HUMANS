"""
Human Decision Making App v32.4.4
09/October/2023 updated 06/Nov/2025
@authors: Lara Rakocevic and Raquel Ibáñez Alcalá and Joshua Xiong
"""

## Webserver-related imports
import json
import os

## Utility imports
import re
import sys
import csv
import io

from argparse import ArgumentParser
from ast import literal_eval
from configparser import ConfigParser as cfgp
from datetime import datetime
from itertools import combinations
from math import comb, inf
from random import randint, sample, shuffle
from secrets import token_hex
from shutil import copy2
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

# import fnmatch
import psycopg2

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
from waitress import serve
from werkzeug.middleware.proxy_fix import ProxyFix

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
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1) # Use relative file paths
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
            for row in raw_data:  # For each row fetched...
                for i, item in enumerate(row):  # Then for each item in the row...
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
        print("\nQuery did not complete successfully.\n" + str(error))

        return False


def create_data_dir(pid):
    path = os.getcwd()
    dir_to_create = os.path.abspath(f"{path}/graph_data/{str(pid)}")
    try:
        os.mkdir(dir_to_create)
    finally:
        return dir_to_create


def get_new_id(reference_from="database"):
    expected_refs = ["database", "local", "file"]
    if reference_from == "database":
        sql_qry = f"SELECT DISTINCT(subjectidnumber) FROM {app_settings['data_table']} ORDER BY subjectidnumber"
        data = []

        conn = psycopg2.connect(**server)
        cursor = conn.cursor()
        cursor.execute(sql_qry, data)

        raw_data = cursor.fetchall()

        cursor.close()
        conn.close()

        unique_ids = set([row[0] for row in raw_data])

    elif reference_from == "local":
        path = os.getcwd()
        path += "/graph_data/"
        unique_ids = set(
            [int(x) for x in re.findall("\d+", " ".join(os.listdir(path)))]
        )
    elif reference_from == "file":
        pass  # Haven't done this yet

    else:
        raise Exception(
            f"\nParameter 'reference_from' was not recognised. Received {reference_from}, expected {str(expected_refs)}!"
        )

    while True:
        subjectidnumber = str(randint(10000, 99999))
        if subjectidnumber not in unique_ids:
            break

    return subjectidnumber


## Functions start getting messy here, revise? Namely, make them less dependent
## on globally declared variables where possible (f.e. remove implicit
## use of Session object and app settings).


def exists(dest_table):
    print(f"\n  Checking if table '{dest_table}' exists in database...")

    # Build query
    query = (
        "SELECT EXISTS ("
        + "SELECT FROM "
        + "pg_tables "
        + "WHERE "
        + "schemaname = 'public' AND "
        + "tablename  = '"
        + dest_table
        + "'"
        + ");"
    )

    conn = psycopg2.connect(**server)

    cursor = conn.cursor()
    cursor.execute(query)
    resp = cursor.fetchone()
    cursor.close()

    if resp[0]:
        print("  Destination table '" + dest_table + "' exists!\n")
    else:
        print("  Destination table '" + dest_table + "' does not exist.\n")

    return resp[0]

def write_to_db(response):
    trial_start = session.get("trial_start", (None, None))
    trial_end = session.get("trial_end", (None, None))

    start_ts = trial_start[0]
    end_ts = trial_end[0]
    page = trial_start[1]

    if start_ts is not None and end_ts is not None:
        trial_start_str = int(start_ts.timestamp() * 1000)
        trial_end_str = int(end_ts.timestamp() * 1000)
        elapsed = trial_end_str - trial_start_str
        trial_elapsed_str = str(elapsed)
    else:
        trial_start_str = None
        trial_end_str = None
        trial_elapsed_str = None

    record = {
        "subjectidnumber": session.get("subjectidnumber"),
        "sex": session.get("sex"),
        "phase": session.get("phase"),
        "page": page,
        "question_id": session.get("question_id"),
        "question_phase_id": session.get("question_phase_id"),
        "question_display_order": session.get("question_order"),
        "option_display_order": json.dumps(session.get("option_order")),
        "response": json.dumps(response),
        "trial_start": trial_start_str,
        "trial_end": trial_end_str,
        "trial_elapsed": trial_elapsed_str
    }
    print("RECORD TO WRITE: " + str(record))

    columns = ",".join(record.keys())
    placeholders = ",".join(["%s"] * len(record))

    sql = f"""
        INSERT INTO {app_settings['data_table']}
        ({columns})
        VALUES ({placeholders})
    """

    try:
        print("\nMaking a connection...")
        conn = psycopg2.connect(**server)
        cursor = conn.cursor()

        cursor.execute(sql, tuple(record.values()))

        conn.commit()
        cursor.close()

    except Exception as error:
        print(f"\nData upload to database failed due to the following error: {error}\n")
    else:
        print("\nData sucessfully uploaded!\n")
    finally:
        if conn is not None:
            conn.close()

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
                    "question_phase_id": None,
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


def create_data_table(
    server_settings, table_name, json_path="bin/db_cols_2.json", exclude_keys=[]
):
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
        with open(json_path, "r") as f:
            table_cols = json.load(f)
    except FileNotFoundError:
        print(f"\nNo JSON file found at location '{json_path}'.")
        return False
    except json.JSONDecodeError:
        print(
            f"\nUnable to decode JSON file '{json_path}'. File may not be formatted correctly."
        )
        return False
    except Exception as e:
        print(f"Could not open JSON file at '{json_path}' due to error:\n{e}")
        return False
    else:
        query = f"CREATE TABLE {table_name}("
        i = 0
        for key, value in sorted(table_cols.items()):
            if key not in exclude_keys:
                start = ", " if i != 0 else " "
                query += f"{start}{key} {value}"
                i += 1
        query += r" );"

        print(
            f"\nCreating data table in database with name {table_name} using query {query}..."
        )
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
    print(f"[SIGNAL.TEMPLATE_RENDERED] Rendered template {template.name or 'string template'} at timestamp {timestamp} in url {page}")

    session["trial_start"] = (timestamp, page)
    session["trial_end"] = (None, None)
    print(f"[SIGNAL.TEMPLATE_RENDERED] Logged 'trial_start'\n Start: {str(session['trial_start'])}\n End: {str(session['trial_end'])}")


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Helper functions for parsing the new question format

def tsv_to_dict(filepath):
    result = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            key = row[0]
            value = row[1].strip()
            result[key] = value
    return result

# select the items that are closest to 50
def select_indiv_items(ratings, n_items=24):
    ranked = sorted(ratings.items(), key=lambda x: abs(x[1] - 100))
    return [k for k, v in ranked[:n_items]]

# input: list of qids, output: map of index to list of qids
def generate_combinations(qids, n):
    return {
        i: list(combo)
        for i, combo in enumerate(combinations(qids, n), start=1)
    }

# input: map of index to list of qids, output: map of index to permutation of range(len(qids))
def get_rand_order(combo_map):
    ordermap = {}
    for k in combo_map:
        qids = combo_map[k]
        rand_order = list(range(len(qids)))
        shuffle(rand_order)
        indiv_qids = [qids[i] for i in rand_order]
        ordermap[k] = (rand_order, indiv_qids)
    return ordermap

def update_map(map, phase, field_data):
    for key in field_data:
        map[phase][key] = field_data[key]
    return map

# input: map of qid to rating, map of (qid,qid) to rating, output: map of idx to qids
def select_radio_items(selected_items, indiv_ratings, pair_ratings, n_items = 32):

    def get_edge_weight(r1, r2, p):
        return int(p) - 100 * (1 - (1 - int(r1)/200.) * (1 - int(r2)/200.))

    edge_weights = {i: {} for i in selected_items}
    for qid1, v in pair_ratings.items():
        for qid2, rating in v.items():
            edge_weights[qid1][qid2] = get_edge_weight(indiv_ratings[qid1], indiv_ratings[qid2], rating)

    # list of qids, sorted by their rating
    ranked_items = sorted(selected_items, key = lambda x: indiv_ratings[x], reverse = True)

    candidates = []
    n = len(ranked_items)

    for i in range(n):
        A = ranked_items[i]
        rating_A = indiv_ratings[A]/2.

        for j in range(i+1, n):
            B = ranked_items[j]
            rating_B = indiv_ratings[B]/2.

            best_metric, best_C = -100, None
            best2_metric, best2_C = -100, None

            for k in range(j+1, n):
                C = ranked_items[k]
                metric = rating_B + edge_weights[B][C] - rating_A - edge_weights[A][C]

                if metric > best_metric:
                    best2_metric, best2_C = best_metric, best2_C
                    best_metric, best_C = metric, C
                elif metric > best2_metric:
                    best2_metric, best2_C = metric, C

            if best2_C is not None:
                candidates.append({"items": [A, B, best_C, best2_C], "metric": best_metric})

    candidates.sort(key = lambda x: x["metric"], reverse = True)

    qs = {}
    idx = 1
    for item in candidates[:n_items]:
        A, B, C, D = item["items"]
        qs[idx] = [A, B]
        qs[idx+1] = [A, B, C]
        qs[idx+2] = [A, B, D]
        qs[idx+3] = [A, B, C, D]
        idx += 4

    return qs


def get_question_id(prefix, qids):
    idxs = sorted(rev_qid_map[qid] for qid in qids)

    N = len(rev_qid_map)
    k = len(idxs)

    rank = 1  # 1-based

    prev = 0
    for i, idx in enumerate(idxs):
        for j in range(prev + 1, idx):
            rank += comb(N - j, k - i - 1)
        prev = idx

    return f"{prefix}_{k}_{rank}"


# currently unused function, but could be useful
def is_ingroup(qid1, qid2):
    return qid1.split("_")[0] == qid2.split("_")[0]
    
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
verb = bool(app_settings.get("verbose", 0))

# 4. Parse db_cols_2.json to figure out what data to upload
try:
    with open("bin/db_cols_2.json", "r") as f:
        data_cols = json.load(f)
except Exception as e:
    print(
        f"\nUnable to parse what data to upload to database, please provide a JSON file with column names in /bin/.\nError when parsing JSON file: {e}"
    )
    sys.exit(1)

# 5. Check if target data table exists in the database and create one if it
#    doesn't.
if (not exists(app_settings["data_table"])) and app_settings["auto_create_table"]:
    if not create_data_table(
        server, app_settings["data_table"], exclude_keys=app_settings["exclude_columns"]
    ):
        sys.exit(
            "\nA valid data table could not be found or created. Please address any errors encountered above and try running the app again."
        )

# 6. Get the questions as a dictionary, where the key is the question number as an int.
q_map = tsv_to_dict("survey/indiv.txt")
indiv_qs = {i: text for i, (qid, text) in enumerate(q_map.items(), start = 1)}
qid_map = {i: qid for i, (qid, text) in enumerate(q_map.items(), start = 1)}
rev_qid_map = {qid: i for i, qid in qid_map.items()}

# 7. Define the workflow
submit_timeout_ms = 4500
require_slider = True

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
    if request.endpoint == "static":
        return
    timestamp = datetime.now(timezone)

    referrer = (
        urlparse(request.referrer).path
        if request.referrer
        else "None"
    )  # The url path from the previous page
    retrival = (
        request.headers["Accept"].split(",")[0] if request.method == "GET" else None
    )  # The content (either html or css) that was downloaded, typically 'text/css' or 'text/html'

    if request.method == "POST":
        session["trial_end"] = (timestamp, request.path)
        print(
            f"[BEFORE, POST] Logged 'trial_end'\n Start: {str(session['trial_start'])}\n End: {str(session['trial_end'])}\n Elapsed: {str(session['trial_end'][0] - session['trial_start'][0])}"
        )
        print(
            f"[BEFORE, POST] Timestamp: {timestamp.strftime('%a %b %d %H:%M:%S.%f %Y %Z')} on path {request.path}, referred from {referrer}"
        )
        if request.path.startswith(r"/instructions") and session["phase"] == "pairs":
            write_to_db({"selected": session["selected"]})

        elif app_settings["data_upload"]:
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
    session.clear()
    excluded = app_settings["exclude_columns"]
    if request.method == "POST":
        if "new_participant" in request.form:
            # Try to set up a session
            if not set_session_params(
                data=list(data_cols.keys()),
                op="set/reset",
                verbose=verb,
            ):
                flash("Could not initialize a session for user.", "danger")
                redirect(url_for("login"))

            # Create a new id
            if session.get("subjectidnumber", None) is None:
                new_id = get_new_id(reference_from=app_settings["unique_ids_from"])
                print(f"\nCreated user ID: {str(new_id)}.\n")
                rand_num = randint(10**8, (10**9) - 1)

            # Save to session
            set_session_params(
                data={"subjectidnumber": new_id, "rand_num": rand_num, "phase": "register"},
                op="update",
                verbose=verb,
            )
            return redirect(url_for("consent"))

    return render_template("start_age_gate.html")


# Consent form
@app.route("/consent", methods=["GET", "POST"])
def consent():
    if request.method == "POST":
        if "continue" in request.form:
            # if user accidentally goes back to this page, do not reset state and continue to next page
            if "phase_map" in session:
                return redirect(url_for("info"))
            # if user opts out, return them to the starting page
            if request.form.to_dict()["value"] == "optout":
                return redirect(url_for("login"))

            phase_map = {
                "indiv": {
                    "qs": indiv_qs,
                    "q_order": sample(range(1, len(indiv_qs) + 1), len(indiv_qs)),
                    "template": "indiv_prefs.html",
                    "next": "rerate",
                    "instructions": "instructions.html"
                },
                "rerate": {
                    "qs": indiv_qs,
                    "q_order": sample(range(1, len(indiv_qs) + 1), len(indiv_qs)),
                    "template": "indiv_prefs.html",
                    "next": "pairs",
                    "instructions": "rerate_instructions.html"
                },
                "pairs": {
                    "template": "pairs_prefs.html",
                    "next": "radio",
                    "instructions": "pairs_instructions.html"
                },
                "radio": {
                    "template": "radio_prefs.html",
                    "next": "finalrate",
                    "instructions": "radio_instructions.html"
                },
                "finalrate": {
                    "template": "indiv_prefs.html",
                    "next": "finished",
                    "instructions": "finalrate_instructions.html"
                }
            }
            starting_params = {
                "phase": "indiv",
                "question_order": 0,
                "phase_map": phase_map,
                "indiv_ratings": {}
            }
            set_session_params(
                data=starting_params, op="update", verbose=verb
            )
            return redirect(url_for("info"))

    return render_template("consent_form_survey.html")

@app.route("/info", methods=["GET", "POST"])
def info():
    if request.method == "POST":
        args = request.form.to_dict()
        set_session_params(data=args, op="update", verbose=verb)
        return redirect(url_for("acknowledgement"))
    return render_template("get_demographic_info.html")

@app.route("/acknowledgement", methods=["GET", "POST"])
def acknowledgement():
    if request.method == "POST":
        return redirect(url_for("instructions"))
    return render_template("pre_instructions.html", id_num = session["subjectidnumber"])

@app.route("/instructions", methods=["GET", "POST"])
def instructions():
    if session["phase"] == "pairs":
        # check to see if questions need to be generated
        if session["phase_map"]["pairs"].get("qs", None) is None:
            items = select_indiv_items(session["indiv_ratings"])
            pair_combos = generate_combinations(items, 2)
            qs = {i: [q_map[qid] for qid in v] for i, v in pair_combos.items()}
            option_orders = get_rand_order(pair_combos)
            pmap = update_map(session["phase_map"], "pairs", 
                {"qs": qs, "o_order": option_orders, "q_order": sample(range(1, len(qs) + 1), len(qs))})
            edges = {i: {} for i in items}
            set_session_params(
                data = {"phase_map": pmap, "pair_ratings": edges, "selected": items}, 
                op="update", 
                verbose=verb
            )
    elif session["phase"] == "radio":
        # check to see if questions need to be generated
        if session["phase_map"]["radio"].get("qs", None) is None:
            indiv_ratings = {}
            mult_combos = select_radio_items(session["selected"], session["indiv_ratings"], session["pair_ratings"])
            qs = {i: [q_map[qid] for qid in v] for i, v in mult_combos.items()}
            option_orders = get_rand_order(mult_combos)
            pmap = update_map(session["phase_map"], "radio", 
                {"qs": qs, "o_order": option_orders, "q_order": sample(range(1, len(qs) + 1), len(qs))})
            set_session_params(
                data = {"phase_map": pmap},
                op="update",
                verbose=verb
            )
    elif session["phase"] == "finalrate":
        # check to see if questions need to be generated
        if session["phase_map"]["finalrate"].get("qs", None) is None:
            qs = {i: q_map[qid] for i, qid in enumerate(session["selected"], start = 1)}
            pmap = update_map(session["phase_map"], "finalrate", 
                {"qs": qs, "q_order": sample(range(1, len(qs) + 1), len(qs))})
            set_session_params(
                data = {"phase_map": pmap},
                op="update",
                verbose=verb
            )
    if request.method == "POST":
        return redirect(url_for("trial_handler"))
    return render_template(session["phase_map"][session["phase"]]["instructions"])

@app.route("/trial", methods=["GET", "POST"])
def trial_handler():
    phase_map = session["phase_map"]
    phase = session["phase"]
    idx = int(session["question_order"])

    qs = phase_map[phase]["qs"]
    q_order = phase_map[phase]["q_order"]    
    question = qs[q_order[idx]]

    session["question_phase_id"] = phase + "_phase_" + str(q_order[idx])

    shuffled_choices = None
    if phase == "indiv" or phase == "rerate":
        session["question_id"] = qid_map[q_order[idx]]
    elif phase == "radio" or phase == "pairs":
        rand_order = phase_map[phase]["o_order"][q_order[idx]][0]
        shuffled_choices = [question[i] for i in rand_order]
        session["option_order"] = phase_map[phase]["o_order"][q_order[idx]][1]
        session["question_id"] = get_question_id(phase, session["option_order"])
    elif phase == "finalrate":
        session["question_id"] = session["selected"][q_order[idx]-1]

    if request.method == "POST":
        if phase == "indiv" or phase == "rerate":
            indiv_rating = request.form.to_dict().get("value")
            qid = qid_map[q_order[idx]]
            session["indiv_ratings"][qid] = session["indiv_ratings"].get(qid, 0) + int(indiv_rating)
        if phase == "pairs":
            pair = session["option_order"]
            val = request.form.to_dict().get("value")
            session["pair_ratings"][pair[0]][pair[1]] = int(val)
            session["pair_ratings"][pair[1]][pair[0]] = int(val)

        if (idx + 1 < len(qs)):        
            set_session_params(
                data = {
                    "phase": phase, 
                    "question_order": idx + 1, 
                    "response": request.form.to_dict()
                }, 
                op="update", 
                verbose=verb
            )
        else:
            set_session_params(
                data={
                    "phase": phase_map[phase]["next"],
                    "question_order": 0,
                    "response": request.form.to_dict()
                }, 
                op="update", 
                verbose=verb
            )
            if phase_map[phase]["next"] == "finished":
                return redirect(url_for("final_end"))
            else:
                return redirect(url_for("instructions"))
        return redirect(url_for("trial_handler"))
    return render_template(
        phase_map[phase]["template"],
        trial_number = idx + 1,
        timeout = submit_timeout_ms,
        require_slider = require_slider,
        question = question,
        choices = shuffled_choices
    )


@app.route("/finished", methods=["GET", "POST"])
def final_end():
    try:
        if "phase" not in session:
            return redirect(url_for("login"))

        if session["phase_map"]["finalrate"].get("qs", None) is not None:
            return render_template(
                "end_confirm.html",
                rand_num = session["rand_num"]
            )
    except:
        return redirect(url_for("consent"))


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
    argparser.add_argument("-md", "--mode", dest="mode", default="prod")
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
            app, host=host_ip, port=host_port, threads=threads
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
