#!/bin/bash
set -e
echo "BUILD START"
python3 -m pip install -r requirements.txt --break-system-packages
python3 manage.py collectstatic --noinput --clear
echo "BUILD END"
