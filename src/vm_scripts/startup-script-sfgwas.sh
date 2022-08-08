if [[ -f /home/startup_was_launched ]]; then exit 0; fi
touch /home/startup_was_launched

sudo -s

study_title=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/study_title" -H "Metadata-Flavor: Google")

apt-get --assume-yes update
apt-get --assume-yes install build-essential
apt-get install python3-pip -y 
pip install sfkit 
PATH=$PATH:~/.local/bin
sfkit run_protocol --study_title ${study_title}