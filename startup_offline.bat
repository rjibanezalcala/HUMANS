py -m ensurepip --upgrade
py -m pip install flask
py -m pip install flask_session
py -m pip install pymupdf
py -m pip install waitress

py -m app2_offline --host 127.0.0.1 --port 5000 --mode local