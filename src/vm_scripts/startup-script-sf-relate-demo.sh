#!/bin/bash

sudo -s
export HOME=/root

if [[ -f startup_was_launched ]]; then exit 0; fi
touch startup_was_launched

auth_key=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/auth_key" -H "Metadata-Flavor: Google")
echo $auth_key > auth_key.txt

SFKIT_API_URL=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/SFKIT_API_URL" -H "Metadata-Flavor: Google")
export SFKIT_API_URL
echo "SFKIT_API_URL: $SFKIT_API_URL"

sudo apt-get update && sudo apt-get upgrade -y 
sudo apt-get install git wget unzip python3 python3-pip python3-venv -y

curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
bash add-google-cloud-ops-agent-repo.sh --also-install

ulimit -n 1000000

# pip install --upgrade --no-cache-dir sfkit
# PATH=$PATH:~/.local/bin
git clone https://github.com/hcholab/sfkit.git
cd sfkit
pip3 install .

export PYTHONUNBUFFERED=TRUE

cd ..
sfkit auth 
sfkit networking
sfkit generate_keys
sfkit register_data --data_path demo
nohup sfkit run_protocol > output.log 2>&1 &
