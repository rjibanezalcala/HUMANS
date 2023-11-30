# database_injector.py README
-----------------------------------------------------------------------------------
## WHAT THIS SCRIPT IS:

This script will walk through the HUMANS app 'data' directory and will upload the
CSV data for each heart rate dump file into the 'heart_rate_data' column in a 
PostgreSQL database.

Records of the user must exist in the database prior to injecting data.

-----------------------------------------------------------------------------------
## WHAT THIS SCRIPT IS NOT:

This script does not inject demographic data or decision-making data to the
database. It will not create a data table nor a data column. The script assumes
that a database and table have been set up prior.

-----------------------------------------------------------------------------------
## HOW TO USE THIS SCRIPT:

Running the script is as easy as opening one of the included batch files:
  - start_supervised
  - start_unsupervised

### Start supervised
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
is displayed on the screen.
