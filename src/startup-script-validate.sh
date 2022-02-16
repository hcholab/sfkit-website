#!/bin/bash

# Only run the startup-script on creation (otherwise, it will run every time the VM is restarted)
if [[ -f /home/startup_was_launched ]]; then exit 0; fi
touch /home/startup_was_launched

# Many of the commands need root privileges for the VM
sudo -s

topic_id=$(hostname)
bucket=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/bucketname" -H "Metadata-Flavor: Google")
message=$(gsutil du -s gs://${bucket} | awk '{print $1}')

gcloud pubsub topics publish ${topic_id} --message="${topic_id}-${message}" --ordering-key="1" --project="broad-cho-priv1"
printf "\n\n Done installing dependencies \n\n"
