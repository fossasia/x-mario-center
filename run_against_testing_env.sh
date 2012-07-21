#!/bin/sh

export SOFTWARE_CENTER_REVIEWS_HOST="http://184.82.116.62/reviews/api/1.0"
export SOFTWARE_CENTER_RECOMMENDER_HOST="http://rec.staging.ubuntu.com"

# sso
export USSOC_SERVICE_URL="https://login.staging.ubuntu.com/api/1.0/"
pkill -f ubuntu-sso-login
python /usr/lib/ubuntu-sso-client/ubuntu-sso-login &

# s-c
export PYTHONPATH=$(pwd)
./software-center $@
