#!/bin/sh
python -m ensurepip --upgrade
pip install flask
pip install numpy
pip install psycopg2
export FLASK_APP=app
flask run
