#!/bin/bash

sudo -s

if [[ -f startup_was_launched ]]; then exit 0; fi
touch startup_was_launched

role=$(hostname | tail -c 2)
study_title=$(hostname | awk -F'-secure-gwas' '{print $1}')
ports=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/ports" -H "Metadata-Flavor: Google")
geno_binary_file_prefix=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/geno_binary_file_prefix" -H "Metadata-Flavor: Google")
data_path=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/data_path" -H "Metadata-Flavor: Google")
demo_study=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/demo" -H "Metadata-Flavor: Google")

auth_key=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/auth_key" -H "Metadata-Flavor: Google")
echo $auth_key > auth_key.txt

apt-get --assume-yes update
apt-get --assume-yes install build-essential
apt-get install python3-pip python3-numpy wget git zip unzip -y 

# install google-cloud-ops-agent
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
bash add-google-cloud-ops-agent-repo.sh --also-install

pip install --upgrade --no-cache-dir sfkit
PATH=$PATH:~/.local/bin
export PYTHONUNBUFFERED=TRUE

sfkit auth 
sfkit networking --ports ${ports} 
sfkit generate_keys

if [[ $demo_study == "true" ]]; then
    sfkit register_data --geno_binary_file_prefix demo --data_path demo
    nohup sfkit run_protocol --demo > output.log 2>&1 &
    exit 0
fi

if [[ $role != "0" ]]; then
    mkdir -p data_path

    gsutil -m cp -r gs://${data_path}/* data_path >/dev/null 2>&1 &
    gsutil_pid=$!
    while kill -0 "$gsutil_pid" >/dev/null 2>&1; do printf '.' -n; sleep 1; done

    # copy dummy file to the gs bucket to make sure we have write access
    touch .dummy_file && gsutil cp .dummy_file gs://${data_path}/.dummy_file && rm .dummy_file
    
    geno_absolute_path=$(pwd)/data_path/${geno_binary_file_prefix}
    sfkit register_data --geno_binary_file_prefix ${geno_absolute_path} --data_path $(pwd)/data_path 
fi

# increase allowed number of open file and processes; had an issue once with sfgwas where it seems that this was the problem
ulimit -n 1000000
ulimit -u 1000000

nohup sfkit run_protocol > output.log 2>&1 &