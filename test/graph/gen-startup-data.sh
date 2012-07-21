#/bin/sh

LOGFILE=startup-times.dat
BASE_BZR=lp:software-center
FIRST_BZR_REV=1277
LAST_BZR_REV=$(bzr revno $BASE_BZR)

if [ ! -e "$LOGFILE" ]; then 
    echo "# statup time log" > $LOGFILE
    echo "#revno    startup-time" >> $LOGFILE
fi

i=$LAST_BZR_REV
while [ $i -gt $FIRST_BZR_REV ]; do
    # stop if we have a copy of this already, it means we
    # have tested that dir already
    if [ -d rev-$i ]; then
        break
    fi
    # test the new revision
    bzr get -r $i $BASE_BZR rev-$i
    cd rev-$i
    # first run is to warm up the cache and rebuild the DB (if needed)
    PYTHONPATH=. ./software-center --measure-startup-time
    # 3 runs with the given revision
    for testrun in 1 2 3 4 5; do
        echo -n "$i   " >> ../$LOGFILE
        PYTHONPATH=. ./software-center --measure-startup-time >> ../$LOGFILE
    done
    cd ..
    i=$((i-1))
done

# plot it
./plot-startup-data.py
