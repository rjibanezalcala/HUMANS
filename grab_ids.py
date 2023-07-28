import psycopg2
import pandas as pd
import math

sql_qry = "SELECT DISTINCT(subjectidnumber) FROM human_dec_making_table ORDER BY subjectidnumber"
data = []

conn = psycopg2.connect(database='live_database', host='10.10.21.18', user='postgres', port='5432', password='1234')
cursor = conn.cursor()
cursor.execute(sql_qry, data)

raw_data = cursor.fetchall()

cursor.close()
conn.close()

unique_ids = set([row[0] for row in raw_data])

for i in unique_ids:
    print(i)