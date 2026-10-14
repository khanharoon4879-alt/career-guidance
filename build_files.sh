#!/bin/bash
set -e
echo "BUILD START"
export PIP_BREAK_SYSTEM_PACKAGES=1
python3 -m pip install -r requirements.txt --break-system-packages
python3 manage.py collectstatic --noinput --clear
echo "BUILD END"
