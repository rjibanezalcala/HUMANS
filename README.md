
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
 
# distribute_stories.py README
Distribute_stories.py is the same algorithm that the dm app uses to create a user's story order upon beginning their first-ever session. It is a command line script that will take a list of at least X topics, where X is defined as the minimum amount of stories that users are required to select from the dm app; this is defined by the 'minimum_topics' parameter in 'bin\settings.ini'. If no parameters are entered, the script will use a hard-coded list of topics as an execution example. The script will fail if less than X topics are passed. You may pass more than X topics at a time, as long as they exist in the 'Human DM Topics.xlsx' file.

Assuming no errors are found in the code execution, this script will spit out a freshly-made story order following the same instructions the 'settings.ini' file gives. This means that you must modify and save
the appropriate parameters in 'settings.ini', this is a list of parameters that will affect the outcome of this script:

	1. approach_avoid
	2. benefit_benefit
	3. cost_cost
	4. moral
	5. multi_choice
	6. probability
	7. social
	Which indicate how many stories to pull from each task type, and...
	8. minimum_topics
To specify which topics to pick stories from, add them as command line arguments by writing them one-by-one after 'python distribute_stories.py ', each inside single quotes and separated by a space.

---
**USAGE EXAMPLE**
> in 'settings.ini': (approach_avoid=12, benefit_benefit=0, cost_cost=0, moral=0, multi_choice=0, probability=0
social=12, and minimum_topics=4)

	python distribute_stories.py 'Education-Post-Education Life' 'Food' 'Vehicle/Transportation' 'Entertainment'
Output:
> ['/social/story_20', '/approach_avoid/story_16', '/social/story_23', '/approach_avoid/story_14', '/social/story_24',
'/social/story_7', '/social/story_8', '/approach_avoid/story_9', '/social/story_11', '/approach_avoid/story_19',
'/social/story_12', '/approach_avoid/story_24', '/approach_avoid/story_15', '/approach_avoid/story_20', '/social/story_6',
'/approach_avoid/story_2', '/approach_avoid/story_10', '/social/story_22', '/social/story_3', '/approach_avoid/story_6',
'/approach_avoid/story_21', '/social/story_10', '/social/story_21', '/approach_avoid/story_5']
---
Keep in mind that the topics must be written exactly as they are in the 'Human DM Topics.xlsx' file!

If you are generating an additional story order for a particular user, access their demographic data by navigating to '\data\{user_id}\demographic_info.txt', and reference the 'pref_stories' line.

Once the new story order is generated, copy it from the command line window and *append* it to the *end* of the user's 'story_order' line. Do not delete the existing story order!!

When pasting, make sure to delete the original closing square bracket (']'), add a comma and a space, and paste the new story order without the opening square bracket ('['). Also make sure you have not accidentally added an empty line to the end of the file.

Finally, save the demographics info file and close it. The app will from the last story it left off on. This is indicated by the user's 'next_story_index' (if '`next_story_from=local`'), or by the number of different stories gone through registered in the database (if '`next_story_from=database`').

> Code within this repository is a collaborative effort between [lrakocev](https://github.com/lrakocev) and [Raquel Ibáñez Alcalá](https://github.com/rjibanezalcala)
> 
> README Written with [StackEdit](https://stackedit.io/).
<!--stackedit_data:
eyJoaXN0b3J5IjpbLTc3NTU3ODQyMywtNzA0MTgwNTY1XX0=
-->