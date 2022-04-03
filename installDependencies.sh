#!/bin/sh

apt-get update
apt-get -y install python3-gevent
apt-get -y install git
apt-get -y install python3-socksipychain
apt-get -y install python3-socks
apt-get -y install python3-pip
apt-get -y install python3-dev
apt-get -y install python3-gmpy2
apt-get -y install flex
apt-get -y install bison
apt-get -y install libgmp-dev
apt-get -y install libmpc-dev
apt-get -y install libssl-dev
pip3 install pycrypto
pip3 install ecdsa
pip3 install zfec
pip3 install gipc
pip3 install pysocks
pip3 install enum34
pip3 install gevent
pip3 install coincurve
pip3 install ipdb
pip3 install ipython
pip3 install numpy
pip3 install setuptools
pip3 install pyparsing
pip3 install hypothesis


wget --no-check-certificate https://crypto.stanford.edu/pbc/files/pbc-0.5.14.tar.gz
tar -xvf pbc-0.5.14.tar.gz
cd pbc-0.5.14
./configure
make
make install
export LIBRARY_PATH=$LIBRARY_PATH:/usr/local/lib
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib

git clone https://github.com/JHUISI/charm.git
cd charm
./configure.sh
make install
