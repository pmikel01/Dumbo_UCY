#!/bin/sh

rm -rf log

# N f B K
# echo "start.sh <N> <F> <B> <K>"

# python3 run_trusted_key_gen.py --N $1 --f $2

server_ip="$(curl ifconfig.co)"
echo $server_ip

echo "Starting node..."
python3 run_socket_node.py --sid 'sidA' --N $1 --f $2 --B $3 --K $4 --T 100 --P "sdumbo" --F 1000000 --I $server_ip > nodelogs/node-$server_ip.log
