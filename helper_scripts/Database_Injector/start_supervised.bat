python -m ensurepip --upgrade
pip install psycopg2
pip install pandas
python -i database_injector.py -s -d ../../data -i ../../bin/settings.ini