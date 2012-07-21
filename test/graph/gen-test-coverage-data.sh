#/bin/sh

LOGFILE=test-coverage.dat
SUMMARY="coverage_summary"
BASE_BZR=lp:software-center
FIRST_BZR_REV=2570
LAST_BZR_REV=$(bzr revno $BASE_BZR)

if [ ! -e "$LOGFILE" ]; then 
    echo "# test coverage log" > $LOGFILE
    echo "#revno coverage" >> $LOGFILE
fi

i=$LAST_BZR_REV
while [ $i -gt $FIRST_BZR_REV ]; do
    # stop if we have a copy of this already, it means we
    # have tested that dir already
    if [ -d rev-$i ]; then
        break
    fi
    # test the new revision
    bzr branch -r $i $BASE_BZR rev-$i
    cd rev-$i/test
    # run the full unit test suite
    make
    c=`tail -1 $SUMMARY | awk '{ print $NF }'`
    echo "$i $c" >> ../../$LOGFILE
    cd ../../
    i=$((i-1))
done

# plot it
./plot-test-coverage.py
