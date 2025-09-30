Documented herein are changes made to the app since version 32.3.0 which was [published in Cell Protocols](https://doi.org/10.1016/j.xpro.2025.104077). All changes must be committed to the [for-website branch in the HUMANS repo](https://github.com/rjibanezalcala/HUMANS/tree/for_website) and will live within this branch only, not the main branch.

# Version 32.4.0: Preparation for production version deployment on web.

### Internal code changes
- App can now be run behind the Web Server Gateway Interface (WSGI) "waitress", and thus must be imported prior to running the app. Startup.bat will download the package automatically.
- Changed the way the app is run from startup.bat, now simply runs the app.py file directly with commandline arguments. Host IP and port must be defined in commandline arguments, otherwise will default to localhost:5000.
	- `--host` or `-h` is the IP address on which the host will listen to for HTTP requests. Defaults to `127.0.0.1`.
	- `--port` or `-p` is the port on which the host listens. Defaults to `5000`.
	- `--mode` or `-md` determines the mode in which the app runs. Options are 'prod' for production deployment using Waitress, 'local' for local deployment using a simple Flask server, and 'dev' for local deployment with Flask in debug mode. Defaults to `prod`.
	- `--threads` or `-th` determines the number of threads to use to serve client requests. Only relevant if '-md prod' as it is a Waitress-relevant argument only. If all threads are busy when a new client initiates a request, they are put into a queue until a thread is freed up. Defaults to `4`, which is the Waitress default. See the [waitress.serve() documentation](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html) for more information.
	- An example use-case to deploy the app in production mode could be `python -m app --host 0.0.0.0 --port 3001 --threads 4`. This will launch the app in production mode behind a Waitress server servicing all addresses on the host, listening on port 3001, and 4 threads to service clients.
- Some global funcionality variables and all global user variables have been replaced by Session handling using the "flask_session" add-on. This resolves an issue where a new user id could not be created and the app would crash if a trial session was previously started by another client. This enables client concurrency for online participants.
- Added the ability to control what columns get created when making a new postgresql table by adding a JSON file with column names and datatypes. This file is accessed by the new function 'create_data_table()' (see below).
- Moved script to handle postgresql query that creates a data table, outside of write_trial_to_db(). Checks for a valid data table are done only once at app startup. This is to prevent a rare potential conflict in the case where the app is run for the first time and a client completes a trial before a table is created.
### UI elements and app flow
- The flow of the app pages was changed to show a Sign-In page at the beginning instead of as the second page. This will allow the Flask-Session functionality to work and save the clients' story order, story index, etc. A session is created upon successfuly entering an existing ID.
- Added status messages using Flask flash messages. This requires a new template to be included into the header of other HTML templates.
- Added the `academic_version` settings which hides certain UI elements that are relevant only in a lab setting and not online:
	- Modified the '/total_end' template to optionally display the final 'session_notes' form if `academic_version` is set to `1`.
	- Biometrics will only be set up if `user_eyetracker` or `use_hrtracker` are `1` AND if `academic_version` is `1`.
	- **IMPORTANT:** Running the app in production mode will force this setting to `0` as it is assumed that the app will be deployed online. Use `--mode local` to circumvent this.
### Security
- App now retrieves sentitive settings from OS environment variables. These must be set prior to running the app.
- Uses a cryptographically strong secret key to handle session cookies.
- Session data is stored server-side and are not persistent.