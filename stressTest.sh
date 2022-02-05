#!/bin/sh

rm -rf log
sh clearLogs.sh

# N f B K
echo "start.sh <N> <F> <B> <K> -----Experiments"

python3 run_trusted_key_gen.py --N 7 --f 2
python3 run_trusted_key_gen.py --N 10 --f 3
python3 run_trusted_key_gen.py --N 16 --f 4
python3 run_trusted_key_gen.py --N 32 --f 8
python3 run_trusted_key_gen.py --N 40 --f 10
python3 run_trusted_key_gen.py --N 48 --f 12
python3 run_trusted_key_gen.py --N 56 --f 14
python3 run_trusted_key_gen.py --N 64 --f 16
python3 run_trusted_key_gen.py --N 80 --f 20
python3 run_trusted_key_gen.py --N 100 --f 25
python3 run_trusted_key_gen.py --N 120 --f 30
python3 run_trusted_key_gen.py --N 152 --f 38
python3 run_trusted_key_gen.py --N 200 --f 50

batchExp="batchSize"

# for bSize in 100 150 200 250 500 750 1000 2500 5000 7500 10000 50000 75000 100000 150000 200000 250000 400000 500000 1000000 1250000 1500000
for bSize in 100000 200000 500000 1000000
do
    # sh oneStressTest.sh 7 2 $bSize 10 $batchExp

    sh oneStressTest.sh 10 3 $bSize 10 $batchExp

    # sh oneStressTest.sh 16 4 $bSize 10 $batchExp

    # sh oneStressTest.sh 32 8 $bSize 10 $batchExp

    sh oneStressTest.sh 40 10 $bSize 10 $batchExp

    # sh oneStressTest.sh 48 12 $bSize 10 $batchExp

    # sh oneStressTest.sh 56 14 $bSize 10 $batchExp

    # sh oneStressTest.sh 64 16 $bSize 10 $batchExp

    # sh oneStressTest.sh 80 20 $bSize 10 $batchExp

    # sh oneStressTest.sh 100 25 $bSize 10 $batchExp

    # sh oneStressTest.sh 120 30 $bSize 10 $batchExp

    # sh oneStressTest.sh 152 38 $bSize 10 $batchExp

    # sh oneStressTest.sh 200 50 $bSize 10 $batchExp
done

sleep 2; while true; do spd-say -w 'Execution Finished'; done
