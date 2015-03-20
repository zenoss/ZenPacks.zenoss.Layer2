#!/bin/bash

PY_FILES=$(find . -name '*.py' -not -path "*./build*" -not -path "./simulation/env/*" -not -path "*mock.py")
pep8 --show-source $PY_FILES --max-line-length=80
