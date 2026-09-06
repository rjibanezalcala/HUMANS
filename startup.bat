py -3.10 -m ensurepip --upgrade
py -3.10 -m pip install flask
py -3.10 -m pip install flask_session
py -3.10 -m pip install flask_limiter
py -3.10 -m pip install numpy
py -3.10 -m pip install psycopg2
py -3.10 -m pip install pandas
py -3.10 -m pip install openpyxl
py -3.10 -m pip install tobii_research
py -3.10 -m pip install openant
py -3.10 -m pip install pymupdf
py -3.10 -m pip install waitress

py -3.10 -m app --host 127.0.0.1 --port 5000 --mode local