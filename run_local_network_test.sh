#!/bin/sh

rm -rf log

# N f B K
echo "start.sh <N> <F> <B> <K>"

python3 run_trusted_key_gen.py --N $1 --f $2

# llall python3
i=0
while [ "$i" -lt $1 ]; do
    echo "start node $i..."
    # python3 run_socket_node.py --sid 'sidA' --id $i --N $1 --f $2 --B $3 --K $4 --S 2000 --T 1 --F 1000000 --P "hotstuff1" &
    python3 run_socket_node.py --sid 'sidA' --id $i --N $1 --f $2 --B $3 --K $4 --T 100 --P "dumbo" --F 1000000 > nodelogs/node-$i.log &
    i=$(( i + 1 ))
done
wait