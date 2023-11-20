
# Human Decision-Making App (name pending)
The purpose of our Human Decision-Making App (HDMA) is to measure decision-making (DM) in human subjects by presenting them with a complex questionnaire specifically designed to elicit DM behaviours in the subject while also collecting biometric data as the subject goes through the different trials.
## Data collected
Subjects are not directly identified by name in the data produced by this application. Rather, a randomised ID number between 10000 and 99999 is generated and assigned to the subject. We then collect demographic information including but not limited to sex, gender identity, age range, race and ethnicity, and education. We also collect interests such as hobbies and what kind of media they consume. We use this data to classify subjects into clusters to attempt to identify any meaningful trends.

During trials, we collect biometric data, including gaze (where the subject is looking at on the screen, pupil dilation (estimated, in millimeters), and heart rate (measured in beats per minute), to potentially measure attentiveness and stress response. All trials are timestamped from when the question is presented (trial start), to when the subject submits their answer (trial_end). 

All data is packed into a [PostgreSQL](https://www.postgresql.org/) table and uploaded as soon as the subject submits their answer. Additionally, demographic information (identified by ID number) is stored in a local text file.
## How it works
Each subject is presented with a selected number of scenarios, in which a scenario (story) *context* is given. The subject must then put themself in that particular situation and think about how they would react.

Next, a list of potentially rewarding options to solve the problem at hand is presented to the subject. The subject then chooses which options would be most preferrable by ranking them on a continuous 0 - 100 scale. This is then repeated for a list of potentially costly or unpleasant options to solve the problem and the subject must then rank them from least unpleasant to most unpleasant on the same continuous 0 - 100 scale. We call these rewarding and costly options "preferences".

Finally, the subject is presented with a predetermined number of questions that pertain to the preferences that were previously chosen in the actual trials. The subject must then answer the question with yes, no, or maybe on a scale. In the case where two different options are presented in the trial, the subject must indicate which option they lean toward the most (this is not the same as ranking preferences). As subject answer these questions, we collect biometric data (see "Data collected" section).
### App operation
The app is written using mostly [Python](https://python.org), and runs within a [Flask](https://flask.palletsprojects.com/en/3.0.x/) webserver. All webpage templates are written in [HTTP](https://developer.mozilla.org/en-US/docs/Web/HTTP) and styled with [CSS](https://developer.mozilla.org/en-US/docs/Web/CSS). All data is stored in a local or remote [PostgreSQL](https://www.postgresql.org/) database (depending on how the app is set up).
## What is included in this repository
### App elements
This includes files and scripts that critically pertain to the operation of the application. This includes Python scripts, HTML sheets, and CSS styling. This also critically includes the settings INI file.
### Helper scripts
These are scripts that isolate certain functionalities that are built into the app, but are not referenced from the app's code. Such scripts can be changed and run independently from the app without any impact. The following is a full list of these scripts:
 - create_map.py
 - distribute_stories.py (see README below)
 - grab_ids.py
 - import_demodata.py
 - randomise_relationship_levels.py
 - write_to.py
 - Story_Breakdown folder with breakdown_stories.py
 
<!--stackedit_data:
eyJoaXN0b3J5IjpbLTc3NTU3ODQyMywtNzA0MTgwNTY1XX0=
-->
