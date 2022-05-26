Speeding Dumbo BFT. The code is forked from the implementation of Honeybadger protocols.

# HoneyBadgerBFT
The Honey Badger of BFT Protocols.

<img width=200 src="http://i.imgur.com/wqzdYl4.png"/>


Most fault tolerant protocols (including RAFT, PBFT, Zyzzyva, Q/U) don't guarantee 
good performance when there are Byzantine faults. Even the so-called "robust" BFT protocols 
(like UpRight, RBFT, Prime, Spinning, and Stellar) have various hard-coded timeout parameters, 
and can only guarantee performance when the network behaves approximately as expected - hence they 
are best suited to well-controlled settings like corporate data centers.

HoneyBadgerBFT is a leaderless and completely asynchronous BFT consensus protocols.
This makes it a good fit for blockchains deployed over wild wild wide area networks
or when adversarial conditions are expected.
HoneyBadger nodes can even stay hidden behind anonymizing relays like Tor, and
the purely-asynchronous protocol will make progress at whatever rate the
network supports.

This repository contains a Python implementation of the Dumbo protocol based on HoneyBadgerBFT.
It is still a prototype, and is not approved for production use. It is intended
to serve as a useful reference and alternative implementations for other projects.

Speeding Dumbo introduces two new ACS protocols, both of which improve the running time
asymptotically and practically. Their experimental results demonstrate a multi-fold 
improvements over HoneyBadgerBFT when they are run back to back in
the same environment on Amazon AWS.



## License
This is released under the CRAPL academic license. See ./CRAPL-LICENSE.txt
Other licenses may be issued at the authors' discretion.

### Docker

Build the docker image first.

    cd docker_build
    docker build -t honeybadgerbft .

Then for example you want to run an instance with N=8, t=2 and B=16:

    docker run -e N="8" -e t="2" -e B="16" -it honeybadgerbft
    
To run a socket Test:

    sudo docker run local-network-benchmark
    

### Installation && How to run the code

Working directory is usually the **parent directory** of HoneyBadgerBFT. All the bold vars are experiment parameters:

+ **N** means the total number of parties;
+ **t** means the tolerance, usually N/4 in our experiments;
+ **B** means the maximum number of transactions committed in a block (by default N log N). And therefore each party proposes B/N transactions.

#### Install dependencies (maybe it is faster to do a snapshot on EC2 for these dependencies)
+ Run installDependencies.sh (Every requirement can be found in the file)

        sudo sh installDependencies.sh


Clone the code:

    git clone https://github.com/pmikel01/Dumbo_UCY.git
+ For local experiments

        git checkout ucy
+ For ec2 experiments

        git checkout ucy_ec2

Generate the keys

    python3 run_trusted_key_gen.py --N "N" --f "f"

### How to deploy the Amazon EC2 experiment

+ Create a .pem file for each region and run

        mv nameHere.pem ~/.ssh
        sudo apt install awscli
        aws configure

+ Create security groups for each region

+ Install boto3 and fabric

+ At Dumbo_UCY/ec2/ folder, run

        python3 utility.py

In this interactive ipython environment, run the following:

+ Launch new machines
        
        launch_new_instances(region, number_of_machine)

+ Query IPs

        ipAll()

+ Install Dependencies
    
        id()

+ Clone and repo

    	gp()

+ Fix Crypto files

    	fixc()

+ Launch experiment for 1 configuration

    	runEC2experiment(N, F, B, K)
where N, F, B, K are experiment parameters (replace them with numbers).

+ Launch experiment with multiple configurations

    	runMultipleEC2experiments()


