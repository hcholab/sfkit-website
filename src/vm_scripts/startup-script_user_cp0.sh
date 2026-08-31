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

METADATA_URL="http://metadata.google.internal/computeMetadata/v1/instance/attributes"

SFKIT_API_URL=$(curl -H "Metadata-Flavor: Google" "$METADATA_URL/SFKIT_API_URL" )
export SFKIT_API_URL
echo "SFKIT_API_URL: $SFKIT_API_URL"

SFKIT_PROXY_ARGS=$(curl -H "Metadata-Flavor: Google" "$METADATA_URL/SFKIT_PROXY_ARGS" )
export SFKIT_PROXY_ARGS

SFKIT_CLI_IMAGE=$(curl -H "Metadata-Flavor: Google" "$METADATA_URL/SFKIT_CLI_IMAGE" )

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

docker run \
    -e SFKIT_API_URL \
    -e SFKIT_PROXY_ARGS \
    -v "$PWD/sfkit:/sfkit/.sfkit" \
    -v "$PWD/auth_key.txt:/sfkit/auth_key.txt:ro" \
    "${SFKIT_CLI_IMAGE}" run
