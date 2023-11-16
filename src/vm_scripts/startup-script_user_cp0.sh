#!/bin/bash

if [[ -f startup_was_launched ]]; then exit 0; fi
touch startup_was_launched

echo $(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/auth_key" -H "Metadata-Flavor: Google") > auth_key.txt

mkdir -p sfkit && chmod -R 777 sfkit
commands=("auth" "networking --ports 8020,8040" "generate_keys" "run_protocol")

curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh ./get-docker.sh
sudo docker pull us-central1-docker.pkg.dev/dsp-artifact-registry/sfkit/sfkit # Pull image once

for cmd in "${commands[@]}"
do
    sudo docker run --net host --cap-add net_admin \
    -e "SFKIT_API_URL=https://sfkit-website-dev-bhj5a4wkqa-uc.a.run.app/api" \
    -e "SFKIT_PROXY_ON=true" \
    -v $PWD/sfkit:/sfkit/.sfkit \
    -v $PWD/auth_key.txt:/sfkit/auth_key.txt:ro \
    us-central1-docker.pkg.dev/dsp-artifact-registry/sfkit/sfkit $cmd
done

