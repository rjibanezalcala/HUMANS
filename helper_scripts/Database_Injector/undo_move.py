# -*- coding: utf-8 -*-
"""
Created on Mon May 11 14:44:43 2026

@author: Raquel
"""

from os import path, getcwd, listdir
from shutil import move
from sys import exit

def read_dir_map(rootdir, restrict_numeric=False, get_full_filenames=False):
# Returns the structure of the given directory as a dictionary.
    
    dir_map = {}
    # Get the task types directories as a list.
    # folders = listdir(rootdir)
    folders = [ name for name in listdir(rootdir) if path.isdir(path.join(rootdir, name)) and (name.isnumeric() if restrict_numeric else True) ]
    
    for folder in folders:
        # Get the directories inside each task type directory as a list.
        dirs = listdir(rootdir+'/'+folder)
        if len(dirs) > 0:
            # If the directory is populated...
            for i in range(len(dirs)):
                # Take only the story number from the directory names...
                full_path = path.join(rootdir, f"{folder}/{dirs[i]}")
                if path.isdir(full_path):
                    dirs[i] = { dirs[i]: listdir(path.abspath(full_path)) }
                else:
                    dirs[i] = dirs[i]
        # ...then populate the dictionary with 'task type': 'stories for
        # in that task type'.
        dir_map.update({path.abspath(path.join(rootdir, folder)): dirs})

    return dir_map


target_dir = path.abspath( 
            path.join(getcwd(), '../../data')
           )
dirs = read_dir_map( target_dir, restrict_numeric=False, get_full_filenames=True )
for k, i in dirs.items():
    for item in i:
        if isinstance(item, dict):
            for source, files in item.items():
                if source == "_PROCESSED_FILES":
                    source_path = path.abspath(path.join(k, source))
                    dest_path   = path.abspath(path.join(source_path, '..'))
                    for file in files:
                        move(path.abspath(path.join(source_path, file)), path.abspath(path.join(dest_path, file)))
        else:
            pass

exit()