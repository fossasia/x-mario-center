#!/usr/bin/python

import subprocess
import sys

if __name__ == "__main__":

    # write out gnuplot
    f=open("test-coverage.gnuplot", "w")
    f.write("""
set title "Software Center Test Coverage"
set xlabel "Revision Number"
set ylabel "Test Coverage (%)"
set term png size 800,600
set out 'software-center-test-coverage.png'
set yrange [0:100]
set ytics 5
set grid
set size 1, 1
set origin 0, 0

plot "test-coverage.dat" using 1:2 with lines title ""
""")
    f.close()

    # run it
    res = subprocess.call(["gnuplot", "test-coverage.gnuplot"])
    sys.exit(res)
