#!/bin/bash

touch /home/test.txt
sudo apt-get --assume-yes update
sudo apt-get --assume-yes install build-essential
sudo apt-get --assume-yes install clang-3.9
sudo apt-get --assume-yes install libgmp3-dev
sudo apt-get --assume-yes install libssl-dev
sudo apt-get --assume-yes install libomp-dev
sudo apt-get --assume-yes install git
sudo apt-get --assume-yes install python3-pip
pip3 install numpy
echo done installing packages

cd /home
git clone https://github.com/simonjmendelsohn/secure-gwas /home/secure-gwas
echo done cloning into repo

curl https://libntl.org/ntl-10.3.0.tar.gz --output ntl-10.3.0.tar.gz
tar -zxvf ntl-10.3.0.tar.gz
cp secure-gwas/code/NTL_mod/ZZ.h ntl-10.3.0/include/NTL/
cp secure-gwas/code/NTL_mod/ZZ.cpp ntl-10.3.0/src/
cd ntl-10.3.0/src
./configure NTL_THREAD_BOOST=on
make all
sudo make install
echo done installing NTL library

cd /home/secure-gwas/code
COMP=$(which clang++-3.9)
sed -i "s|^CPP.*$|CPP = ${COMP}|g" Makefile
sed -i "s|^INCPATHS.*$|INCPATHS = -I/usr/local/include|g" Makefile
sed -i "s|^LDPATH.*$|LDPATH = -L/usr/local/lib|g" Makefile
make
echo done compiling secure gwas code
