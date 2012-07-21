#!/bin/sh

python-coverage  run --parallel $1
./gen-coverage-report.sh 
