#!/bin/sh

rm -rf log

# N f B K
echo "start.sh <N> $1 <F> <B> $3 <K>"

# pkill python
# pgrep python

i=0
while [ "$i" -lt $1 ]; do
    echo "start node $i..."
    python3 run_socket_node.py --sid 'sidA' --id $i --N $1 --f $2 --B $3 --K $4 --T 100 --P "dumbo" --F 1000000 >> experimentLogs/$5-$1-$i.log &
    i=$(( i + 1 ))
done
wait
