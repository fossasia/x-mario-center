#!/bin/sh

export SOFTWARE_CENTER_REVIEWS_HOST="http://127.0.0.1:8000/reviews/api/1.0"
export SOFTWARE_CENTER_FORCE_NON_SSL=1
export SOFTWARE_CENTER_FORCE_DISABLE_CERTS_CHECK=1

# sso
export USSOC_SERVICE_URL="https://login.staging.ubuntu.com/api/1.0"
pkill -f ubuntu-sso-login
python /usr/lib/ubuntu-sso-client/ubuntu-sso-login &

# s-c
if [ -n "$PYTHONPATH" ]; then
    export PYTHONPATH=$(pwd):$PYTHONPATH
else
    export PYTHONPATH=$(pwd)
fi


if [ ! -d "./build" ]; then
    echo "Please run: 'python setup.py build' before $0"
fi

./software-center $@
