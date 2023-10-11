# -*- coding: utf-8 -*-
"""
Created on Wed Oct  4 15:51:42 2023

randomise_relationship_levels.py v0.1
@author: Raquel Ibáñez Alcalá

"""

from os import path
from random import sample
import re

def read_file(root_dir, story, file):
    # Open, read, and process text lines
    file_path = root_dir + f"{story}\\{file}.txt"
    lines = open(file_path).read().split("\n")
    lines = [line.strip() for line in lines if (line != '' and line != ' ')]
    
    # Process each file differently:
    if file in ['pref_cost', 'pref_reward']:
        opt_dict = {}
        for option in lines:
            line = option.split(")")
            opt_num = int(line[0])
            opt_description = line[1]
            opt_dict[opt_num] = opt_description.strip()
        return opt_dict
    elif file == 'context':
        return ' '.join(lines)
    elif file == 'questions':
        quest_dict = {}
        # Pattern to match all sentences, regardless of punctuation (curly brace included for debugging with example stories).
        pattern = re.compile(r'([A-Z][^\.!?}]*[\.!?}])', re.M)
        for l in lines:
            linelist = ['', '']
            linelist[0] = ' '.join(pattern.findall(l)) # Find all sentences in the question
            linelist[1] = re.findall('\(.*?\)', l)[-1]  # Find everything in parenthesis and take the last element.
            question = linelist[0]
            RC = re.findall("\d+", linelist[1]) # Take only the numeric values in this part of the string.
            # RC will contain a variable length list of string numbers. A length of
            # 4 will more than likely indicate that the current task is the
            # multi-choice task. This is the only task type where the questions are
            # tagged as (RxCy RaCb). I want to consider all posibilities though!
            keytup = ()
            for x in RC:
                keytup = keytup + (int(x),)
            quest_dict.update({ keytup: question })
        return quest_dict
    else:
        return None

def replace_one(text, word_bank, replace_from=None, replace_with=None):
# Replace the first relationship word with one from the word bank

    if any(word in text for word in word_bank):
        if replace_from is None:
            pick = sample(word_bank, 1)[0] if replace_with is None else replace_with
            text = text.split(' ')
            for i, word in enumerate(text):
                no_punctuation = re.sub(r'[^\w\s\d]', '', word)
                if no_punctuation in word_bank:
                    punctuation = re.findall(r'[^\w\s\d]', word)
                    text[i] = pick if len(punctuation) == 0 else pick+punctuation[-1]
                    break
            
            return ' '.join(text), pick
        else:
            return text.replace(replace_from, replace_with, 1), replace_with
    else:
        return text, None
    
def replace_all(text, word_bank, replace_from=None, replace_with=None):
# Replace the relationship word with one from the word bank
    
    # Remove "'s" from text and split words into list
    split_text = [ re.split(r"'s", word)[0] for word in text.split(' ') ]
    # If any word (where each word has punctuation removed) in the text appears in the word bank, process the text
    if any(word in [ re.sub(r'[^\w\s\d]', '', x).lower() for x in split_text] for word in word_bank):
        if replace_from is None:
            results = []
            # Find all of those words and save them in a list
            for i, word in enumerate(split_text):
                if re.sub(r'[^\w\s\d]', '', word).lower() in word_bank:
                    # Get only unique results. Save the word without punctuation
                    if not word in results: results.append(re.sub(r'[^\w\s\d]', '', word))
            print(f"\nFound matches in text! {results}")
            # Sample as many words from the word bank as there are results
            pick = sample(word_bank, len(results)) if replace_with is None else replace_with
            print(f"Replacing matching results with: {pick}\n")
            for i, word in enumerate(results):
                # Replace all words with the sampled word
                text = text.replace(word, pick[i].title() if word[0].isupper() else pick[i])
            
            return text, pick
        else:
            return text.replace(replace_from, replace_with), replace_with
    else:
        return text, None
    
    
    
    
    
# -----------------------------------------------------------------------------
""" Library usage example """
if __name__ == "__main__":
    relationship_pool = ['father', 'mother', 'brother', 'sister', 'cousin', 'uncle', 'aunt', 'grandfather', 'grandmother', 'friend', 'friends', 'close friend', 'family', 'son', 'daughter', 'children']
    valid_stories = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24]
    root_dir = path.dirname(__file__)+"\\stories\\task_types\\social\\"
    
    # story_6, two different words to replace
    # story_17, 'friend' appears thrice
    # story_18, 'friend' appears twice
    # story_19, 'friend' appears twice
    # story_22, 'friend' appears twice
    # story_23, 'friend' appears twice
    # story_24, 'friend' appears twice
    
    # story_num = 'story_'+str(choice(valid_stories))
    story_num = 'story_17'
    text = read_file(root_dir, story_num, 'pref_cost')
    text = text[6]
    print(f"\n>> Picking random story: {story_num}")
    print("\n>> Run replace_one with randomly picked relationship level:")
    print(f'>>> Text before replacement:\n"{text}"')
    new_text, replaced = replace_one(text, relationship_pool, replace_with="cousin")
    if new_text != text:
        print(f'\n>>> After replacement with replaced word "{replaced}":\n"{new_text}"')
    else:
        print("\n>>> No changes were made.")
    
    print("\n>> Run replace_all with randomly picked relationship level:")
    print(f'>>> Text before replacement:\n"{text}"')
    new_text, replaced = replace_all(text, relationship_pool)
    if new_text != text:
        print(f'\n>>> After replacement with replaced word(s) "{replaced}":\n"{new_text}"')
    else:
        print("\n>>> No changes were made.")
