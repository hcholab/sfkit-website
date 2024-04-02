# WORK IN PROGRESS

#!/bin/bash

handle_error() {
    error_type=${1:-"GCP startup script"}
    auth_key=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/auth_key" -H "Metadata-Flavor: Google")

    msg="update_firestore::status=FAILED - $error_type failed in an unknown manner. Please reach out if this problem persists."

    encoded_msg=$(echo "$msg" | curl -Gso /dev/null -w %{url_effective} --data-urlencode @- "" | cut -c 3-)
    curl -s -o /dev/null -w "%{http_code}" -H "Authorization: $auth_key" -H "Content-Type: application/json" "https://sfkit.org/update_firestore?msg=${encoded_msg}"
    exit 1
}

trap handle_error ERR

sudo -s
export HOME=/root

if [[ -f startup_was_launched ]]; then exit 0; fi
touch startup_was_launched

role=$(hostname | tail -c 2)
study_id=$(hostname | awk -F'-secure-gwas' '{print $1}')
ports=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/ports" -H "Metadata-Flavor: Google")
geno_binary_file_prefix=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/geno_binary_file_prefix" -H "Metadata-Flavor: Google")
data_path=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/data_path" -H "Metadata-Flavor: Google")
demo_study=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/demo" -H "Metadata-Flavor: Google")

auth_key=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/auth_key" -H "Metadata-Flavor: Google")
echo $auth_key > auth_key.txt

# Misc configurations
sysctl -w net.core.rmem_max=2500000 && sysctl -w net.core.wmem_max=2500000 # increase network buffer size
ulimit -n 1000000 # increase max open files
ulimit -u 1000000 # increase max user processes
export PYTHONUNBUFFERED=TRUE

SFKIT_API_URL=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/SFKIT_API_URL" -H "Metadata-Flavor: Google")
export SFKIT_API_URL
echo "SFKIT_API_URL: $SFKIT_API_URL"

apt-get --assume-yes update && apt-get --assume-yes upgrade
mkdir -p sfkit && chmod -R 777 sfkit # create sfkit directory and make it writable

# install google-cloud-ops-agent
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
bash add-google-cloud-ops-agent-repo.sh --also-install

# DOCKER
# Add Docker's official GPG key
apt-get install -y ca-certificates curl gnupg lsb-release 
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
# Set up the repository:
echo \ 
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null 
# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
# Test Docker installation
sudo docker run hello-world

# Pull image
docker pull us-central1-docker.pkg.dev/dsp-artifact-registry/sfkit/sfkit 

cat > run_docker_commands.sh << 'EOF'
#!/bin/bash
commands=("auth" "networking --ports ${ports}" "generate_keys" "register_data "run_protocol")
for cmd in "${commands[@]}"
do
    docker run --net host --cap-add net_admin \
    -e "SFKIT_API_URL=$SFKIT_API_URL" \
    -e "SFKIT_PROXY_ON=true" \
    -e "PYTHONUNBUFFERED=TRUE" \
    -v $PWD/sfkit:/sfkit/.sfkit \
    -v $PWD/auth_key.txt:/sfkit/auth_key.txt:ro \
    us-central1-docker.pkg.dev/dsp-artifact-registry/sfkit/sfkit $cmd
done
EOF

chmod +x run_docker_commands.sh
nohup ./run_docker_commands.sh > output.log 2>&1 &