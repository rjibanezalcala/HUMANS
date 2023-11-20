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
