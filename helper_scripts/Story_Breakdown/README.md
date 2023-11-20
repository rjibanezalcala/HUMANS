# breakdown_stories.py README
-----------------------------------------------------------------------------------
WHAT THIS SCRIPT IS:

This script takes a Word document (with a '.docx' extension) and breaks it down
into several text files that comply with the format the decision-making (DM) app
accepts. For each story in the Word file, it'll produce the following files:
	
	- context.txt
	- pref_cost.txt
	- pref_reward.txt
	- questions.txt

The script will also create the same folder structure the DM app needs, so each
story will be contained in '/output/{task type}/story_{story #}/', where the
curly braces ( {} ) represent a placeholder. Each of the text files will be
contained in '/output/{task type}/story_{story #}/', just how the app needs them.

-----------------------------------------------------------------------------------
WHAT THIS SCRIPT IS NOT:

This script does not check for grammar, spelling, or punctuation. Whatever is in
the Word file you give it, it will take directly. It will only remove certain
pieces of text (for example the numbers on a list), but it will make no other
modifications to whatever is in the Word file. This means that if the Word document
is missing anything, it will be missing in the generated text files as well.

For this reason, make sure that your Word documents are complete before passing them
through this script, or you will get blank or incomplete text documents.

-----------------------------------------------------------------------------------
HOW TO USE THIS SCRIPT:

SETUP:

1. Use the template I've provided to write your stories.
2. Finish writing all stories, preferences, and questions throughout the whole
	document.
3. Follow this naming convention: '{Task_type} DM.docx'. The first few words in
	the file name should describe the task type. You do not need to capitalise
	the first letter, but do separate each word with an underscore (_). Follow
	the task type with a space and 'DM'. Save the Word file as a .docx ONLY.
4. Place this file in the '/input/' folder.

RUNNING THE SCRIPT:

5. Double click on the file 'startup.bat'. A black command window will pop up.
6. Sit back and relax while the script does its job!
	The script might take longer if you feed it many word files, but it'll do
	its best to finish all the work. You'll see what Word files it's working on
	and when it's done processing each one.
7. Open up the '/output/' folder to find all the stories separated into the files
	the app accepts, formatted exactly how it wants them to be. Look over the text
	files make sure they all look good.
	Take the contents of the '/output/' folder and transfer them to the DM app.
8. In the DM app folder, navigate to '/stories/task_types/'. Place the contents of
	'/output/' in here.
9. You're done! You just did several hours of work in just a few seconds!
