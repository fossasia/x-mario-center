#!/bin/sh

if [ -z "$1" ]; then
    NETDEV=$(route -n|grep ^0.0.0.0|awk '{print $8}')
else
    NETDEV="$1"
fi

if [ "$(id -u)" != "0" ]; then
    echo "You need to be root to run this script"
    exit 1
fi

if [ -z "$NETDEV" ]; then
    echo "Can not find a default netdev, please specifcy one"
    exit 1
fi

echo "Simulating slow network for default gateway device $NETDEV"

# reset
tc qdisc del dev $NETDEV root 2> /dev/null

# make it slow
tc qdisc add dev $NETDEV root handle 1: tbf rate 64kbit buffer 1600 limit 3000
tc qdisc add dev $NETDEV parent 1: handle 10: netem delay 1000ms
