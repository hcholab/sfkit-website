# WORK IN PROGRESS

#!/bin/bash

sudo -s
export HOME=/root

if [[ -f startup_was_launched ]]; then exit 0; fi
touch startup_was_launched

echo $(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/auth_key" -H "Metadata-Flavor: Google") > auth_key.txt

# Misc configurations
sysctl -w net.core.rmem_max=2500000 && sysctl -w net.core.wmem_max=2500000 # increase network buffer size
ulimit -n 1000000 # increase max open files
ulimit -u 1000000 # increase max user processes
export PYTHONUNBUFFERED=TRUE

mkdir -p sfkit && chmod -R 777 sfkit # create sfkit directory and make it writable
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh ./get-docker.sh 
docker pull us-central1-docker.pkg.dev/dsp-artifact-registry/sfkit/sfkit # Pull image once

cat > run_docker_commands.sh << 'EOF'
#!/bin/bash
