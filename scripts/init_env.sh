#!/bin/bash
if [ ! -e venv ]; then
    virtualenv venv
fi;
source venv/bin/activate
pip install -r requirements.txt
