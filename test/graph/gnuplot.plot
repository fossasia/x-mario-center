#set title "Startup times"
set xlabel "Revision number"
set ylabel "Startup time [seconds]"
set term png size 1600,1200
set out 'startup-times.png'
# start with y-xais on 0
set yrange [0:]
set grid
set multiplot

# plot 1
set size 1, 0.3
set origin 0, 0.6
plot "startup-times-gnuplot.dat" using 1:2 smooth csplines \
 with lines lt 3 title "Startup time trend"

# plot 2
set size 1, 0.3
set origin 0, 0.3
plot "startup-times-gnuplot.dat" using 1:2:3:4 with yerrorbars linestyle 1\
 title "Starteup time data (with error bars)"

# plot 3
set size 1, 0.3
set origin 0, 0
plot "startup-times.dat" using 1:2 with dots\
 title "Starteup time raw data"

