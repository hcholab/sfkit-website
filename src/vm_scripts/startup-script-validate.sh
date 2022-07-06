#!/bin/bash

# Only run the startup-script on creation (otherwise, it will run every time the VM is restarted)
if [[ -f /home/startup_was_launched ]]; then exit 0; fi
touch /home/startup_was_launched

# Many of the commands need root privileges for the VM
sudo -s

topic_id=$(hostname)
data_path=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/data_path" -H "Metadata-Flavor: Google")
size=$(gsutil du -s gs://${data_path} | awk '{print $1}')
files=$(gsutil ls gs://${data_path})

gcloud pubsub topics publish ${topic_id} --message="${topic_id}-validate|${size}|${files}" --ordering-key="1" --project="broad-cho-priv1"
printf "\n\n Done getting dataset size \n\n"
