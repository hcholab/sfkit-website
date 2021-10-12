#!/bin/bash

# Sanity check that the startup-script is working
touch /home/test.txt

# Many of the commands need root privileges for the VM
sudo -s

printf "\n\n Begin installing dependencies \n\n"
apt-get --assume-yes update
apt-get --assume-yes install build-essential
apt-get --assume-yes install clang-3.9
apt-get --assume-yes install libgmp3-dev
apt-get --assume-yes install libssl-dev
apt-get --assume-yes install libomp-dev
apt-get --assume-yes install netcat
apt-get --assume-yes install git
apt-get --assume-yes install python3-pip
pip3 install numpy
pip3 install google-cloud-pubsub
printf "\n\n Done installing dependencies \n\n"

printf "\n\n Setting up pubsub to let web server know the progress \n\n"
cd /home
git clone https://github.com/simonjmendelsohn/secure-gwas-pubsub /home/secure-gwas-pubsub
python3 secure-gwas-pubsub/publish.py done_installing_dependencies

printf "\n\n Begin installing GWAS repo \n\n"
cd /home
git clone https://github.com/simonjmendelsohn/secure-gwas /home/secure-gwas
printf "\n\n Done installing GWAS repo \n\n"

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
python3 secure-gwas-pubsub/publish.py done_installing_NTL
printf "\n\n Done installing NTL library \n\n"

printf "\n\n Begin compiling secure gwas code \n\n"
cd /home/secure-gwas/code
COMP=$(which clang++)
sed -i "s|^CPP.*$|CPP = ${COMP}|g" Makefile
sed -i "s|^INCPATHS.*$|INCPATHS = -I/usr/local/include|g" Makefile
sed -i "s|^LDPATH.*$|LDPATH = -L/usr/local/lib|g" Makefile
make
cd /home
python3 secure-gwas-pubsub/publish.py done_compiling_gwas
printf "\n\n done compiling secure gwas code \n\n"

# printf "\n\n Update IP addresses in parameter files \n\n"
role=$(hostname | tail -c 2)
# gsutil cp -r gs://broad-cho-priv1-secure-gwas-data/ .
# while [ "$(ls /home/broad-cho-priv1-secure-gwas-data/ip_addresses/ | wc -l)" != "4" ]; do
#     printf "\n\n Waiting for other VMs to be created \n\n"
#     sleep 60
#     rm -r /home/broad-cho-priv1-secure-gwas-data/ip_addresses/
#     gsutil cp -r gs://broad-cho-priv1-secure-gwas-data/ .
# done
    
# cd /home/broad-cho-priv1-secure-gwas-data/ip_addresses/
# P0=$(<P0); P1=$(<P1); P2=$(<P2); P3=$(<P3);
# cd /home/secure-gwas/par/
# for i in 0 1 2 3; do
#     temp="P${i}"
#     sed -i "s/^IP_ADDR_P${i}.*$/IP_ADDR_P${i} ${!temp}/g" test.par.${role}.txt
# done
# cd /home 
# python3 secure-gwas-pubsub/publish.py IP_addresses_are_ready

printf "\n\n Waiting for all other VMs to be ready for GWAS \n\n"
nc -k -l -p 8055 &
for i in 0 1 2 3; do
    false
    while [ $? == 1 ]; do
        printf "Waiting for VM secure-gwas${i} to be done setting up \n"
        sleep 5
        nc -w 5 -v -z 10.0.${i}.10 8055 &>/dev/null
    done
done
python3 secure-gwas-pubsub/publish.py all_vms_are_ready
printf "\n\n All VMs are ready to begin GWAS \n\n"

printf "\n\n Starting DataSharing and GWAS \n\n"
cd /home/secure-gwas/code
sleep $((30 * ${role}))
if [[ $role -eq "3" ]]; then
    bin/DataSharingClient ${role} ../par/test.par.${role}.txt ../test_data/
    cd /home
    python3 secure-gwas-pubsub/publish.py DataSharing_completed
else
    bin/DataSharingClient ${role} ../par/test.par.${role}.txt

    python3 /home/secure-gwas-pubsub/publish.py DataSharing_completed

    printf "\n\n Waiting a couple minutes between DataSharing and GWAS... \n\n"
    sleep $((100 + 30 * ${role}))
    bin/GwasClient ${role} ../par/test.par.${role}.txt

    cd /home
    python3 secure-gwas-pubsub/publish.py GWAS_completed
fi
printf "\n\n Done with GWAS \n\n"

gsutil ls # TODO: remove once tested
