#!/bin/sh

set -e

if [ ! -x /usr/bin/python-coverage ]; then
    echo "please install python-coverage"
    exit 1
fi

if [ ! -x /usr/bin/xvfb-run ]; then
    echo "please install xvfb"
    exit 1
fi

if ! python -c 'import mock'; then
    echo "please install python-mock"
    exit 1
fi

if ! python -c 'import unittest2'; then
    echo "please install python-unittest2"
    exit 1
fi

if ! python -c 'import aptdaemon.test'; then
    echo "please install python-aptdaemon.test"
    exit 1
fi

if ! python -c 'import lxml'; then
    echo "please install python-lxml"
    exit 1
fi

if ! python -c 'import PyQt4'; then
    echo "please install python-qt4"
    exit 1
fi


# clear coverage data
# coverage erase will not erase the files from --parallel-mode 
rm -f .coverage*

# run with xvfb and coverage
PYTHON="python-coverage run --parallel-mode"
#PYTHON="xvfb-run $PYTHON"

# and record failures here
OUTPUT="./output"
rm -rf $OUTPUT

FAILED=""
FILES=$(find . -name 'test_*.py')
for file in $FILES; do 
    if [ -f $file ]; then
	echo -n "Testing $file"
        mkdir -p ${OUTPUT}/$(dirname $file)
	if ! $PYTHON $file  >output/$file.out 2>&1 ; then
	    FAILED="$FAILED $file"
	    echo " FAIL"
	else 
            echo " success"
	    rm -f ${OUTPUT}/$file.out; 
	fi 
    fi 
done; 

# gather the coverage data
./gen-coverage-report.sh

if [ -n "$FAILED" ]; then 
    echo "FAILED: $FAILED"; 
    echo "Check ${OUTPUT}/ directory for the details"; 
    exit 1; 
fi

