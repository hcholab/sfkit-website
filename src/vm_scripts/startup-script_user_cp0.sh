#!/bin/bash

sudo -s
export HOME=/root

if [[ -f startup_was_launched ]]; then exit 0; fi
touch startup_was_launched

echo $(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/auth_key" -H "Metadata-Flavor: Google") > auth_key.txt

# Misc configurations
sysctl -w net.core.rmem_max=2500000 && sysctl -w net.core.wmem_max=2500000
ulimit -n 1000000
ulimit -u 1000000
export PYTHONUNBUFFERED=TRUE

SFKIT_API_URL=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/SFKIT_API_URL" -H "Metadata-Flavor: Google")
export SFKIT_API_URL
echo "SFKIT_API_URL: $SFKIT_API_URL"

apt-get --assume-yes update
mkdir -p sfkit && chmod -R 777 sfkit

attempt=0
max_attempts=2
while [ $attempt -lt $max_attempts ]; do
  curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh ./get-docker.sh && break
  attempt=$((attempt+1))
  echo "Attempt $attempt to install Docker failed. Retrying..."
  sleep 5
done
if [ $attempt -eq $max_attempts ]; then
  echo "Failed to install Docker after $max_attempts attempts."
  exit 1
fi

docker pull us-central1-docker.pkg.dev/dsp-artifact-registry/sfkit/sfkit # Pull image once

cat > run_docker_commands.sh << 'EOF'
#!/bin/bash
commands=("auth" "networking --ports 8020,8040" "generate_keys" "run_protocol")
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