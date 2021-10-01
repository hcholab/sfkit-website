#!/bin/bash

# Sanity check that the startup-script is working
touch /home/test.txt

# Many of the commands need root privileges for the VM
sudo -s 

apt-get --assume-yes update
apt-get --assume-yes install build-essential
apt-get --assume-yes install clang-3.9
apt-get --assume-yes install libgmp3-dev
apt-get --assume-yes install libssl-dev
apt-get --assume-yes install libomp-dev
apt-get --assume-yes install git
apt-get --assume-yes install python3-pip
apt-get --assume-yes install netcat
pip3 install numpy
pip3 install google-cloud-pubsub
echo "done installing packages"

cd /home
git clone https://github.com/simonjmendelsohn/secure-gwas /home/secure-gwas
echo "done cloning into repo"

curl https://libntl.org/ntl-10.3.0.tar.gz --output ntl-10.3.0.tar.gz
tar -zxvf ntl-10.3.0.tar.gz
cp secure-gwas/code/NTL_mod/ZZ.h ntl-10.3.0/include/NTL/
cp secure-gwas/code/NTL_mod/ZZ.cpp ntl-10.3.0/src/
cd ntl-10.3.0/src
./configure NTL_THREAD_BOOST=on
make all
make install
echo "done installing NTL library"

cd /home/secure-gwas/code
COMP=$(which clang++)
sed -i "s|^CPP.*$|CPP = ${COMP}|g" Makefile
sed -i "s|^INCPATHS.*$|INCPATHS = -I/usr/local/include|g" Makefile
sed -i "s|^LDPATH.*$|LDPATH = -L/usr/local/lib|g" Makefile
make
echo "done compiling secure gwas code"

# Use pubsub to announce that the startup script has finished
cd /home
git clone https://github.com/simonjmendelsohn/secure-gwas-pubsub /home/secure-gwas-pubsub
python3 secure-gwas-pubsub/publish.py
echo "done with startup-script"

role=$(hostname | tail -c 2)
# Use NetCat to wait for all VMs to be done setting up 
nc -k -l -p 8055 &
for i in 0 1 2 3 
do
    false
    while [ $? == 1 ]
    do 
        echo "Waiting for VM secure-gwas${i} to be done setting up"
        sleep 30
        nc -w 5 -v -z 10.0.0.1${i} 8055 &>/dev/null
    done
done

# Data Sharing Client and GWAS
echo "\n\nStarting DataSharing and GWAS\n\n"
cd /home/secure-gwas/code 
sleep $((5 * ${role}))
if [[ $role -eq "3" ]]
then 
    bin/DataSharingClient ${role} ../par/test.par.${role}.txt ../test_data/
else
    bin/DataSharingClient ${role} ../par/test.par.${role}.txt 
    echo "\n\nSLEEEP FOR A COUPLE MINUTES before starting GWAS\n\n"
    sleep $((120 + 15 * ${role}))
    bin/GwasClient ${role} ../par/test.par.${role}.txt 
fi

