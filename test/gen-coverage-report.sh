#/bin/sh

set -e

# combine the reports
python-coverage combine

if [ -d coverage_html ]; then
    rm -rf coverage_html
fi

# generate the coverage data 
OMIT="/usr/share/pyshared/*,*piston*,*test_"
python-coverage report --omit=$OMIT | tee coverage_summary | tail

DIR="coverage_html"
python-coverage html   --omit=$OMIT -d $DIR
echo "see $DIR/index.html for the coverage details"