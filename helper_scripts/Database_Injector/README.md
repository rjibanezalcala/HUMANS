# database_injector.py README
-----------------------------------------------------------------------------------
## What this script is

This script will walk through the HUMANS app 'data' directory and will upload the
CSV data for each heart rate dump file into the 'heart_rate_data' column in a 
PostgreSQL database.

Records of the user must exist in the database prior to injecting data.

-----------------------------------------------------------------------------------
## What this script is not

This script does not inject demographic data or decision-making data to the
database. It will not create a data table nor a data column. The script assumes
that a database and table have been set up prior.

-----------------------------------------------------------------------------------
## How to use this script

Running the script is as easy as opening one of the included batch files:
  - start_supervised
  - start_unsupervised

Execution time will vary depending on
  - Connection latency to the database
  - Size of the 'data' directory
  - System specifications

### Prerequisits
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

Only files with a '.csv' file extension delimited by the ';' character will be
processed. The CSV file must contain at least a column named 'time' where each
record's timestamp is stored. These timestamps should be formatted[^1] as
~~~
mm/dd/yyyy hh:mm:ss AM|PM
~~~
[^1]: Compatible timestamp formatting can be changed within the \_\_init\_\_() function of the Injector class and follows standard datetime formatting.

Files that do not comply with these requirements and subdirectories of the numeric
directory will be skipped.

### Running the script with supervision
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

### Running the script unsupervised
If the script is started in unsupervised mode, no user interaction is required.
The script will scan through the entirety of the data folder for data, then filter
and upload the data to the database.

### Running script from the command line
The script accepts a short list of optional parameters. If running the script
through the command line, one may use these parameters to change the script's
behaviour. Note that all parameters are optional, but some may be useful when
doing a test run of the script.

To run the script using command line arguments, follow the usage example below.

If running directly from Python, use
~~~
database_injector.py [-h] [-s] [-dnu] [-d DATA_DIR] [-i SET_DIR] [-cwd] [-dnm]
~~~
If running from CMD or Windows Powershell, use
~~~
python -i database_injector.py [-h] [-s] [-dnu] [-d DATA_DIR] [-i SET_DIR] [-cwd] [-dnm]
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

The list of script parameters is included below:

| Shorthand argument | Extended argument |     Description     |
| :----:               |       :----:       | :--- |
| -h  | --help  | show help message and exit   |
| -s   | --supervised | whether to wait for user input upon processing each file (default: False)      |   
|  -dnu| --donotupload |  if true, data is not uploaded to database (default: False) |
|  -d DATA_DIR | --datafolder DATA_DIR | Location of data in disk (default: ../../data)|
|  -i SET_DIR | --ini SET_DIR | Location of app settings file (default: ../../bin/settings.ini) |
|  -cwd | --usecurrentdir | Use the current working directory as --datafolder (default: False) |
|-dnm | --donotmoveprocessedfiles | prevents the program from moving already processed files to the _PROCESSED_FILES directory, also program will also not create the directory (default: False)|

### Epilogue
After reading a CSV file and updating the selected database records, the script
will move the processed CSV file to a folder named _PROCESSED_FILES in the same
directory where the file was found. This folder is completely skipped while
scannng through the data directory. This ensures that the same file isn't
processed more than once.

