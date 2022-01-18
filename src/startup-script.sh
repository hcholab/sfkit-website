#!/bin/bash

# Only run the startup-script on creation (otherwise, it will run every time the VM is restarted)
if [[ -f /home/startup_was_launched ]]; then exit 0; fi
touch /home/startup_was_launched

# Many of the commands need root privileges for the VM
sudo -s

printf "\n\n Begin installing dependencies \n\n"
apt-get --assume-yes update
apt-get --assume-yes install build-essential
apt-get --assume-yes install clang-3.9
apt-get --assume-yes install libgmp3-dev
apt-get --assume-yes install libssl-dev
apt-get --assume-yes install libsodium-dev
apt-get --assume-yes install libomp-dev
apt-get --assume-yes install netcat
apt-get --assume-yes install git
apt-get --assume-yes install python3-pip
pip3 install numpy
topic_id=$(hostname)
gcloud pubsub topics publish ${topic_id} --message="Done installing dependencies" --ordering-key="1" --project="broad-cho-priv1"
printf "\n\n Done installing dependencies \n\n"

printf "\n\n Begin installing GWAS repo \n\n"
cd /home
git clone https://github.com/simonjmendelsohn/secure-gwas /home/secure-gwas
printf "\n\n Done installing GWAS repo \n\n"

role=$(hostname | tail -c 2)

printf "\n\n Download data from storage bucket"
mkdir -p /home/secure-gwas/test_data
gsutil cp gs://secure-gwas-data${role}/g.bin /home/secure-gwas/test_data/g.bin
gsutil cp gs://secure-gwas-data${role}/m.bin /home/secure-gwas/test_data/m.bin
gsutil cp gs://secure-gwas-data${role}/p.bin /home/secure-gwas/test_data/p.bin
gsutil cp gs://secure-gwas-data${role}/other_shared_key.bin /home/secure-gwas/test_data/other_shared_key.bin
gsutil cp gs://secure-gwas-data${role}/pos.txt /home/secure-gwas/test_data/pos.txt
printf "\n\n Done downloading data from storage bucket \n\n"

printf "\n\n Begin installing NTL library \n\n"
curl https://libntl.org/ntl-10.3.0.tar.gz --output ntl-10.3.0.tar.gz
tar -zxvf ntl-10.3.0.tar.gz
cp secure-gwas/code/NTL_mod/ZZ.h ntl-10.3.0/include/NTL/
cp secure-gwas/code/NTL_mod/ZZ.cpp ntl-10.3.0/src/
cd ntl-10.3.0/src
./configure NTL_THREAD_BOOST=on
make all
make install
cd /home
gcloud pubsub topics publish ${topic_id} --message="Done installing NTL library" --ordering-key="1" --project="broad-cho-priv1"
printf "\n\n Done installing NTL library \n\n"

printf "\n\n Begin compiling secure gwas code \n\n"
cd /home/secure-gwas/code
COMP=$(which clang++)
sed -i "s|^CPP.*$|CPP = ${COMP}|g" Makefile
sed -i "s|^INCPATHS.*$|INCPATHS = -I/usr/local/include|g" Makefile
sed -i "s|^LDPATH.*$|LDPATH = -L/usr/local/lib|g" Makefile
make
cd /home
gcloud pubsub topics publish ${topic_id} --message="Done compiling GWAS" --ordering-key="1" --project="broad-cho-priv1"
printf "\n\n done compiling secure gwas code \n\n"

printf "\n\n Waiting for all other VMs to be ready for GWAS \n\n"
nc -k -l -p 8055 &
for i in 0 1 2; do
    false
    while [ $? == 1 ]; do
        printf "Waiting for VM secure-gwas${i} to be done setting up \n"
        sleep 5
        nc -w 5 -v -z 10.0.${i}.10 8055 &>/dev/null
    done
done
gcloud pubsub topics publish ${topic_id} --message="All VMs are ready" --ordering-key="1" --project="broad-cho-priv1"
printf "\n\n All VMs are ready to begin GWAS \n\n"

printf "\n\n Starting DataSharing and GWAS \n\n"
cd /home/secure-gwas/code
sleep $((30 * ${role}))
if [[ $role -eq "0" ]]; then
    bin/DataSharingClient ${role} ../par/test.par.${role}.txt
else
    bin/DataSharingClient ${role} ../par/test.par.${role}.txt ../test_data/
fi
gcloud pubsub topics publish ${topic_id} --message="DataSharing Completed!" --ordering-key="1" --project="broad-cho-priv1"

printf "\n\n Waiting a couple minutes between DataSharing and GWAS... \n\n"
sleep $((100 + 30 * ${role}))
bin/GwasClient ${role} ../par/test.par.${role}.txt
gcloud pubsub topics publish ${topic_id} --message="GWAS Completed!" --ordering-key="1" --project="broad-cho-priv1"

printf "\n\n Done with GWAS \n\n"
