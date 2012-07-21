#!/bin/sh

export SOFTWARE_CENTER_FAKE_REVIEW_API="1"

# s-c
export PYTHONPATH=$(pwd)
./software-center $@
