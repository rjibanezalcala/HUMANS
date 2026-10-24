py -m ensurepip --upgrade
py -m pip install flask flask_session tzdata waitress

py -m app2_offline --host 127.0.0.1 --port 5000 --mode local