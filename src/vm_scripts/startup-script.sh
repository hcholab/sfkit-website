#!/bin/bash

sudo -s

if [[ -f startup_was_launched ]]; then exit 0; fi
touch startup_was_launched

role=$(hostname | tail -c 2)
study_title=$(hostname | awk -F'-secure-gwas' '{print $1}')
ports=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/ports" -H "Metadata-Flavor: Google")
geno_binary_file_prefix=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/geno_binary_file_prefix" -H "Metadata-Flavor: Google")
data_path=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/data_path" -H "Metadata-Flavor: Google")

auth_key=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/auth_key" -H "Metadata-Flavor: Google")
echo $auth_key > auth_key.txt

apt-get --assume-yes update
apt-get --assume-yes install build-essential
apt-get install python3-pip wget git zip unzip -y 

pip install sfkit
PATH=$PATH:~/.local/bin
export PYTHONUNBUFFERED=TRUE

if [[ $role == "0" ]]; then
    sfkit auth --study_title ${study_title}
else
    sfkit auth 
fi
sfkit networking --ports ${ports} 
sfkit generate_keys
if [[ $role != "0" ]]; then
    mkdir -p data_path
    gsutil cp -r gs://${data_path}/* data_path
    
    geno_absolute_path=$(pwd)/data_path/${geno_binary_file_prefix}
    sfkit register_data --geno_binary_file_prefix ${geno_absolute_path} --data_path $(pwd)/data_path 
fi

sfkit run_protocol