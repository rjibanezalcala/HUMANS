# -*- coding: utf-8 -*-
"""
Created on Tue Nov 21 13:22:57 2023

HUMANS_tools.py v0.0.0
@author: Raquel Ibáñez Alcalá
"""

import pandas as pd
from os import listdir, path
from ast import literal_eval
from copy import deepcopy
import psycopg2 as sql
from configparser import ConfigParser as cfgp

class ParserTools:
    def __init__(self, **kwargs):
        self.settings_path = path.abspath(kwargs.get('settings_path', r'bin/settings.ini'))
        
    def parser(self, section, eval_datatype):
    # Returns server credentials from ini file.
    
        # Create a parser
        parser = cfgp()
        # Read config file
        parser.read(self.settings_path)
    
        # Find the appropriate section, defaults to postgresql
        db = {}
        if parser.has_section(section):
            params = parser.items(section)
            for param in params:
                db[param[0]] = param[1]
        else:
            raise Exception('\n[ParserTools] Section {0} not found in the {1} file'.format(section, self.settings_path))
    
        if eval_datatype:
            for key, value in db.items():
                if value.isnumeric():
                    db[key] = literal_eval(value)
                elif value.startswith('['):
                    db[key] = literal_eval(value)
                
        return db
    
    def without_keys(self, d, keys):
    # Removes key-value pairs from dictionary
        return {x: d[x] for x in d if x not in keys}
    
    def parse_ini(self, section='postgresql',
                        eval_datatype=False,
                        exclude_keys=[] ):
        
        return self.without_keys( self.parser( section=section,\
                                               eval_datatype=eval_datatype),\
                                 exclude_keys)
            
    def read_dir_map(self, rootdir, restrict_numeric=False, get_full_filenames=False):
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
                    dirs[i] = dirs[i] if get_full_filenames else dirs[i].split('_')[-1]
            # ...then populate the dictionary with 'task type': 'stories for
            # in that task type'.
            dirs.sort(reverse=True)
            dir_map.update({folder: dirs})
    
        return dir_map


class DatabaseTools:
        
    def query_database(self, query, credentials):
        print("[DatabaseTools] Attempting to query database...")
        try:
            data = []
            conn = sql.connect(**credentials)
            cursor = conn.cursor()
            #cursor.execute(query, data)
            # Execute query
            cursor.execute(query)
            # Fetch all results
            raw_data = cursor.fetchall()
            # Close connection
            cursor.close()
            conn.close()
            
            # Check if anything came back
            if raw_data:
                # Create a list of keys from the table headers in the database
                keys = [i[0] for i in cursor.description]
                # And prepare to parse the data.
                data_row = dict()
                data_table = list()
                row_index = 0
                # cell_index = 0
                # Place all fetched rows into list of dictionaries
                for row in raw_data: # For each row fetched...
                    for i,item in enumerate(row): # Then for each item in the row...
                        # Update the row dictionary with a key/value pair using the list of keys created before
                        data_row.update({keys[i]: item})
                        # Then move on to the next item
                        # cell_index += 1
                    # When done with this row, append the resulting dictionary to the list
                    data_table.append(data_row)
                    # Then empty the row dictionary
                    data_row = dict()
                    # And move on to the next row
                    row_index += 1
                
                print("  Query completed successfully!\n")
                return data_table
            
            else:
                # If no results, return nothing
                print("  Query returned no results.\n")
                return None
        
        except (Exception, sql.DatabaseError) as error:
            print(f"  Query did not complete successfully.\n  {error}")
            
            return None
    
    def exists(self, dest_table, credentials):
        print(f"[DatabaseTools] Checking if table '{ dest_table }' exists in database...")
        
        # Build query
        query = "SELECT EXISTS ("\
                + "SELECT FROM "\
                + "pg_tables "\
                + "WHERE "\
                + "schemaname = 'public' AND "\
                + "tablename  = '"+dest_table+"'"\
                + ");"

        conn = sql.connect(**credentials)

        cursor = conn.cursor()
        cursor.execute(query)
        resp = cursor.fetchone()
        cursor.close()
        
        if resp[0]:
            print("  Destination table '"+dest_table+"' exists!\n")
        else:
            print("  Destination table '"+dest_table+"' does not exist.\n")
            
        return resp[0]
    
    def get_user_records(self, id_num, credentials, data_table, select=['*'], equals={}, like={}):
        print(f"[DatabaseTools] Fetching records for user {id_num}...")
        if self.exists(data_table, credentials):
            query = "SELECT "
            
            for i, item in enumerate(select):
                if i != len(select)-1:
                    query += f"{ str(item) }, "
                else:
                    query += f"{ str(item) } "
            
            query += f"FROM { data_table } "+\
                     f"WHERE subjectidnumber='{ str(id_num) }'"
        
            for key, value in equals.items():
                query += f" AND { str(key) }='{ str(value) }'"
            
            for key, value in like.items():
                query += f" AND { str(key) } LIKE '{ str(value)+'%' }'"
            
            query += ";"
            
            print(f"  Constructed query:\n  {query}\n")
            return self.query_database(query, credentials)
        
        else:
            return -1
    
    def update_row(self, data_table, credentials, column, new_data, where_equals):
        print("[DatabaseTools] Updating database row...")
        # Construct query
        query = f"UPDATE { data_table } "+\
                f"SET { column }='{ new_data }' "+\
                "WHERE "
        i = 0
        for key, value in where_equals.items():
            query += f"{ key }='{ value }'"
            query += " AND " if i != len(where_equals)-1 else ';'
            i += 1
        
        print(f"  Constructed query:\n  {query}\n")
        
        try:
            conn = sql.connect(**credentials)
    
            cursor = conn.cursor()
            cursor.execute(query)
        
        except Exception as error:
            print(f"  Update did not complete successfully:\n  {error}\n")
            
            return False
        else:
            conn.commit()
            cursor.close()
            
            return True


class StoryTools:
    def __init__(self):
        pass

    def read_topic_table(self, file='../../Human DM Topics.xlsx'):
    # Retrieves the relationship between topics, task types, and story IDs from
    # Excel file. Returns a dictionary that contains this information where the
    # top-level keys are each topic. Each of these keys will contain a dictionary
    # where each key-value pair is task type and the stories that correspond
    # to that task type.
    
        # Read Excel file
        dftopic = pd.read_excel(file, sheet_name='RefTable', header=0, index_col=0)
        
        def parse_as_list(x):
        # Converts the contents of each input string of comma-separated numbers as 
        # a list string.
            return str(x).replace(" ","").split(',')
        # Apply the above function to the whole retreived dataframe. This will
        # convert each cell in the dataframe as a list string.
        dftopic = dftopic.applymap(parse_as_list)
        # Add a topic ID row. The topic ID will be dependent on the table read from
        # the input Excel file.
        newrow = {}
        for key in dftopic.columns:
            newrow.update({key:1+dftopic.columns.get_loc(key)})
        dftopic = pd.concat([dftopic, pd.DataFrame(data=newrow, index=['topic_id'])])
    
        # Convert dataframe to dictionary for ease of access.
        relations = dftopic.to_dict()
    
        return relations
        
    def validate(self, theoretical, real, inplace=False):
    # Validates that the contents of the 'theoretical' dictionary exist in the
    # 'real' dictionary. Useful to check that stories described in the story
    # relations table exist in the actual app. Returns a copy of the 'theoretical'
    # dictionary where all the values that do not exist in 'real' have been removed
    
        if inplace:
            validated = theoretical
        else:
            validated = deepcopy(theoretical)
            
        for mkey, sdict in validated.items():
            for key, target in sdict.items():
                if key!='topic_id':
                    # print(f"{mkey}/{key}:")
                    # print('theoretical story list:', target)
                    # print('real story list:', real[key.replace('-','_').lower()])
                    # [ x if x in real[key.replace('-','_').lower()] else removed_items.append( target.pop(target.index(x)) ) for x in target ]
                    validated_list = [ x for x in target if x in real[key.replace('-','_').lower()] ]
                    # print("validated list:", validated_list)
                    validated[mkey][key] = validated_list
        
        return validated
    
    def get_story_info(self, search_term, dictionary):
    # Since story blurbs were replaced with topics, it is necessary to know what
    # topic each story belongs to. This can be done by searching the
    # story_relations dictionary. This function will accept a term coming directly
    # from the story order in the format '/{task_type}/story_{story number}'. It
    # then breaks the search term up and uses it to find the topic the story is
    # about. The search returns topic_id, a numerical representation of the topic,
    # 'topic', the topic description, 'task_type', the type of task the story is
    # and 'story', the story itself as just the story number.
    
        task_search = search_term.split('/')[1]
        task_search = task_search.replace('_', '-').title().replace(' ', '-')
        story_search = search_term.split('/')[-1]
        story_search = story_search.split('_')[-1]
        
        result = {}
        
        for key in dictionary:
            for x in dictionary[key][task_search]:
                if int(x) == int(story_search):
                    result.update({ 'topic_id': dictionary[key]['topic_id'],
                                    'topic': key,
                                    'task_type': search_term.split('/')[1],
                                    'story': story_search })
        
        return result