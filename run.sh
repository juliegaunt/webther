#!/bin/sh

python -m venv venv
. venv/bin/activate

pip install -r requirements.txt
#pip install flask requests pytz astral

python app.py
