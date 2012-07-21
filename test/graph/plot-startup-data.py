#!/usr/bin/python

# numpy is love
import numpy
import subprocess
import string
import sys

# get the filename
if len(sys.argv) > 1:
    fname = sys.argv[1]
else:
    fname = "startup-times.dat"

# read the data
revno_to_times = {}
for line in map(string.strip, open(fname)):
    if line.startswith("#") or line == "":
        continue
    try:
        (revno, time) = line.split()
        time = float(time)
    except:
        #print "invalid line: '%s'" % line
        continue
    if not revno in revno_to_times:
        revno_to_times[revno] = []
    revno_to_times[revno].append(float(time))

# generate data suitable for gnuplot
outfile = open("startup-times-gnuplot.dat", "w")
outfile.write("#revno   average-time ymin, ymax\n")
for revno, times in sorted(revno_to_times.iteritems()):
    #print revno, numpy.mean(times), numpy.std(times), numpy.var(times)
    outfile.write("%s %s %s %s\n" % (
            revno, numpy.mean(times), numpy.min(times), numpy.max(times)))
outfile.close()

# call gnuplot
subprocess.call(["gnuplot","gnuplot.plot"])

