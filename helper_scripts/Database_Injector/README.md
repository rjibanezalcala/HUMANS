# Database injector
1. [Script overview](#script-overview)
2. [Prerequisits](#prerequisits)
3. [Running the script with supervision](#running-the-script-with-supervision)
4. [Running the script unsupervised](#running-the-script-unsupervised)
5. [Running the script from the command line](#running-the-script-from-the-command-line)
   - [Available parameters](#available-parameters)
7. [Data upload instructions](#data-upload-instructions)
8. [Troubleshooting](#troubleshooting)

# Script overview

**What this script is**

This script will walk through the HUMANS app 'data' directory and will upload the
CSV data for each heart rate dump file into the 'heart_rate_data' column in a 
PostgreSQL database.

Records of the user must exist in the database prior to injecting data.

**What this script is not**

This script does not inject demographic data or decision-making data to the
database. It will not create a data table nor a data column. The script assumes
that a database and table have been set up prior.

**How to use this script**

Running the script is as easy as opening one of the included batch files:
  - start_supervised
  - start_unsupervised

Execution time will vary depending on
  - Connection latency to the database
  - Size of the 'data' directory
  - System specifications

# Prerequisits
CSV files must be contained directly within a subfolder of the specified data
folder. The containing folder MUST be named using numeric characters ONLY.

For example
~~~
D:\{path_to_decision_making_app}\dec-making-app\data\32083\32083_12_01_2023_15_29.csv
~~~
or
~~~
{path_to_data_folder}\32083\32083_12_01_2023_15_29.csv
~~~
Where '{path_to_data_folder}' is the path given by the '-d' parameter (see [list of available parameters](#available-parameters)).

Only files with a '.csv' file extension delimited by the ';' character will be
processed. The CSV file must contain at least a column named 'time' where each
record's timestamp is stored. These timestamps should be formatted[^1] as
~~~
mm/dd/yyyy hh:mm:ss AM|PM
~~~
[^1]: Compatible timestamp formatting can be changed within the \_\_init\_\_() function of the Injector class and follows standard datetime formatting.

Files that do not comply with these requirements and subdirectories of the numeric
directory will be skipped.

After reading a CSV file and updating the selected database records, the script
will move the processed CSV file to a folder named _PROCESSED_FILES in the same
directory where the file was found. This folder is completely skipped while
scannng through the data directory. This ensures that the same file isn't
processed more than once. This can be avoided by using the '-dnm' command line
parameter, however the parameter is not passed in either of the batch files 
provided (see [list of available parameters](#available-parameters)).

# Running the script with supervision
The script can run under supervision of a human 'user'. The script will carry its
function normally, but will ask for confirmation before uploading records to the
database.

This is to ensure that the data that will be uploaded to the database is accurate,
namely that the heart rate records that are filtered from each heart rate dataset
fall between the trial_start and trial_end timestamps retrieved from a subject's
stored records.

The user must simply press enter when the message
~~~
> Press enter to continue to upload, or enter Ctrl+C to cancel script.
~~~
is displayed on the screen. If data is inaccurate, the user should enter the
key combination CTRL+C to stop the script.

# Running the script unsupervised
If the script is started in unsupervised mode, no user interaction is required.
The script will scan through the entirety of the data folder for data, then filter
and upload the data to the database.

# Running the script from the command line
The script accepts a short list of optional parameters. If running the script
through the command line, one may use these parameters to change the script's
behaviour. Note that all parameters are optional, but some may be useful when
doing a test run of the script.

To run the script using command line arguments, follow the usage example below.

If running directly from Python, use
~~~
database_injector.py [-h] [-s] [-dnu] [-d DATA_DIR] [-i SET_DIR] [-cwd] [-dnm] [-g GROUPING] [-u UPPER_BOUND] [-l LOWER_BOUND] [-uo UPPER_BOUND_OFFSET] [-lo LOWER_BOUND_OFFSET]
~~~
If running from CMD/Windows Powershell, use
~~~
python -i database_injector.py [-h] [-s] [-dnu] [-d DATA_DIR] [-i SET_DIR] [-cwd] [-dnm] [-g GROUPING] [-u UPPER_BOUND] [-l LOWER_BOUND] [-uo UPPER_BOUND_OFFSET] [-lo LOWER_BOUND_OFFSET]
~~~
Running the 'display_help' batch file will display the script's help message,
where a script description and a list of parameters with their default values
are given. Alternatively, one may execute the command
~~~
database_injector.py --help
~~~
or
~~~
python -i database_injector.py --help
~~~
from the containing directory.

## Available parameters

| Shorthand argument | Extended argument |     Description     |
| :----:               |       :----:       | :--- |
| -h  | --help  | show help message and exit   |
| -s   | --supervised | whether to wait for user input upon processing each file (default: False)      |   
|  -dnu| --do_not_upload |  if true, data is not uploaded to database (default: False) |
|  -d DATA_DIR | --data_folder DATA_DIR | Location of data in disk (default: ../../data)|
|  -i SET_DIR | --ini SET_DIR | Location of app settings file (default: ../../bin/settings.ini) |
|  -cwd | --use_current_dir | Use the current working directory as --datafolder (default: False) |
|-dnm | --do_not_move | prevents the program from moving already processed files to the _PROCESSED_FILES directory, also program will also not create the directory (default: False)|
|-g GROUP_METHOD| --group_by GROUP_METHOD| Preferred method to segment the HR data. Segmenting by 'trial' gives the most granularity, but HR records will be small; this takes the trial_start and trial_end timestamps of each record and uses them as the time bounds. Grouping by 'story' will take the trial_start timestamp of the story's first trial, and the trial_end of the last. Grouping by session will take the day's first trial_start time, and the last trial_end (default: trial) |
|-u TIMESTAMP_NAME|--upper_bound TIMESTAMP_NAME|Selects the first time stamp to use for the time bounds' upper bound. Selecting 'start' will use the n<sup>th</sup> trial's 'trial_start' time stamp, and 'end' will use 'trial_end'. (default: trial_start)|
|-l TIMESTAMP_NAME|--lower_bound TIMESTAMP_NAME|Selects the n<sup>th</sup> time stamp to use for the time bounds' lower bound. Selecting 'start' will use the n<sup>th</sup> trial's 'trial_start' time stamp, and 'end' will use the n+1<sup>th</sup> 'trial_end' timestamp. (default: trial_end)|
|-uo SECONDS|--upper_offset SECONDS|Indicates the time offset to subtract from the upper time bound, in seconds. Must be integer value. (default: 1)|
|-lo SECONDS|--lower_offset SECONDS|Indicates the time offset to add to the lower time bound, in seconds. Must be integer value. (default: 1)|
|-loc|--localize_timestamps|Indicates whether to parse timestamps so in a way that makes them timezone-aware. This is useful if there is a timezone mismatch timestamps in the database and in the dataset to be segmented. (default: False)|
|-ltz LOCAL_TZ|--local_timezone LOCAL_TZ|The timezone to use to localize timestamps in the dataset to be segmented. The timezone used to generate timestamps from the app is taken for bin/settings.ini. Must be identifiable from the IANA Time Zone Database, but can be either the full 'TZ Identifier' or the abbreviation. (default: America/Denver)|

> [!NOTE]
> If -u and -l are the same, the injector will generate the time bounds using the indicated upper bound (set by -u) from trial n, and the indicated lower bound (set by -l) from trial n+1. Otherwise, both upper and lower time bounds are taken from trial n.

---

# Data upload instructions

## Step 1: Organize HR data

1. Open Pulse Monitor
2. On the main window, under the "Last trainings" panel: Double-click a record, this will open a new window.
3. Single-click the entry(ies) that appears under the "Participants" panel. This *should* bring up a graph to the right if there is data.
4. If there is data, right-click each entry and select "Save full HR data"; this should open a file explorer window, and the file should appear as a CSV (.csv) file.
5. Refer to the summary graph under "Participant", this should show the participant's ID number. Save the HR data directly into the participant's data folder (for example, to /data/51198, NOT /data/51198/_PROCESSED_FILES). MAKE SURE YOU'RE SAVING TO THE CORRECT APP'S DIRECTORY.
6. You may name this file however you see fit, but ideally it should be named after the session's timestamp that appears on the summary graph with the format "yyyy-mm-dd_hh-mm-ss.csv" (for example, 2026-4-30_12-00-00.csv). Saving the file with this format helps the data upload process go a little bit smoother.
7. Finally, close the Pulse Monitor window and move on to the next record.

> [!CAUTION]
> The injector uses the first and last *date* (year, month, and calendar day) listed in the HRM data to fetch records from the database to update them with the data. If two or more HRM files contain timestamps from the same day, the injector may erroneously think that the some of the records from that day have no HRM data that match them, even if they were contained in another file. This will result in it overwriting records it had previously updated with an empty list of HRM records ('[]'). If you created more than one HRM data file from the same day, you should manually merge them together so that all records follow chronological order *before* continuing to running the injector.

## Step 2: Begin data upload

Once you are done organizing the data, navigate to "/helper_scripts/Database_Injector" and double-click "start_unsupervised.bat" This should start uploading all the .csv files contained in "/data"; this should take about 5 to 10 minutes, depending on how much data needs to be uploaded. You can also run "start_supervised.bat" if you want to check each upload individually :).

> [!TIP]
> If you suspect there is data in the "/_PROCESSED_FILES" data directory for any given participant, you can run the following command in a terminal window open at "/helper_scripts/Database_Injector" BEFORE initiating the upload: ``python -m undo_move``. This will move every file out of the "/_PROCESSED_FILES" directory and into the participant's base data directory.

---

# Troubleshooting

There are many things that may go wrong, but here are a couple of most-likely failures:

## Upload hangs or is stuck on "Checking if data table exists..."

This is likely because the injector cannot connect to the PostgreSQL database. If the server where the database is hosted is active, this can usually be resolved by providing the injector with the correct database credentials.

On versions > v3.4, this is done through a runtime environment variable (recommended) or a persistent, user-level environment variable:

1. Open "start_supervised.bat" or "start_unsupervised.bat" in any text editor.
2. Before the python call, set the following environment variables at runtime using ``SET VARIABLE_NAME=VALUE`` for Windows, or ``EXPORT VARIABLE_NAME=VALUE`` for Linux:
 - DBHST=[DATABASE_IP_OR_DOMAIN]
 - DBNAME=[DATABASE_NAME]
 - DBPRT=[DATABASE_PORT]
 - DBUSR=[DATABASE_ADMIN_USERNAME]
 - DBPASS=[DATABASE_ADMIN_PASSWORD]
 - DBDATATABLE=[DESTINATION_DATA_TABLE]
3. Try starting the injector up again. If it fails again, check that the database server is active and that you have the correct credentials.

On versions < v3.4, these parameters are defined in the settings.ini file. Please see the user manual to understand how to configure this.

> [!WARNING]
> It is not recommended to define the database credentials directs in settings.ini as this poses a security risk!

## Upload skips every HR data file

This may be either because the HR data file is not a CSV file (with extension .csv), or because the file contents are not formatted correctly.

To resolve the former, go back to Pulse Monitor and make sure you are saving the data with "Save full HR data" and not with "Save in TCX format". 

For the latter case, make sure that the contents of the data are formatted as follows:

~~~
hr;time
94;4/30/2026 12:05:52 PM
94;4/30/2026 12:05:53 PM
93;4/30/2026 12:05:54 PM
92;4/30/2026 12:05:56 PM
..;......... ........ ..
~~~

If the HR data file is in XML format, the file will be skipped and a message will be displayed.

It is also possible that the files are being skipped because the filename is non-numeric. Try renaming the file using the format ``yyyy-mm-dd_hh-mm-ss.csv`` in reference to when the HR data was recorded.

## No HR data appears on each upload

This can be a more complex issue. One possibility is that the time difference (time delta) between the trial timestamps for each of the retrieved records is very short (under 1 second), or the timestamps are formatted differently than what the injector expects.

In the first case, it is likely that "heart_rate_data" will be equal to "[]". This may be because the app itself is not saving timestamps correctly. The injector relies on "trial_start" and/or "trial_end" timestamps to segment the continuous HR data recordings. If the time difference between the timestamp bounds (either trial_start or trial_end, depending on how the injector was configured at runtime) is < 1 second, no HR records will match these bounds. Please contact me if this is the case!

In the second case, you may see the message "Could not update database records". The most likely answer to this is that something in the database is not formatted in the way the injector expects. You can verify this by looking at the constructed queries made to the database on each upload attempt. Check the portion after the "WHERE" operator and look at each condition, make sure these match the formats in the database.

## I keep seeing the message ">> Data was not uploaded to database <<<"

Make sure you are not setting the ``-dnu`` or ``--do_not_upload`` comand line parameter when running the injector!

## The injector crashed because it can't parse the timestamps fetched from the database

This one should not appear unless you have changed the way timestamps get saved in the database.

The injector expects timestamps that it can match with the regular expression ``^[A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d{4}\s+[A-Z]{3,4}``. This typically can look like this:

``Tue May 12 18:51:20.914628 2026 UTC``

or like this:

``Tue May 12 18:51:20.914628 2026 UTC;/trial_end``

If timestamps are not saved as such in the database, the injector will fail to find the timestamp in the fetched records.

To resolve this, make sure that the app is parsing timestamps in this way. This is done through the ``datetime.strftime()`` method in the app, every time a timestamp is taken.

To modify how timestamps are parsed in the injector, first refer to the injector's source code and look for the parameter ``self.db_ts_format`` within the ``__init__()`` function of the injector class; this by default is set to ``%a %b %d %H:%M:%S.%f %Y``. You may modify this, but you must also make sure that timestamps are parsed the same way in the app. Then, find the parameter ``self.ts_pattern`` and modify it so that ``re.match()`` is able to find the timestamp in the fetched string.
