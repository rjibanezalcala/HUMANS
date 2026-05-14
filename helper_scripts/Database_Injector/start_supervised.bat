python -m ensurepip --upgrade
pip install psycopg2
pip install pandas
python -i database_injector.py -s -d ../../data -i ../../bin/settings.ini -g trial -u trial_start -l trial_end -uo 1 -lo 1 -dnm -loc
