#!/bin/bash

sudo -s
export HOME=/root

if [[ -f startup_was_launched ]]; then exit 0; fi
touch startup_was_launched

echo $(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/auth_key" -H "Metadata-Flavor: Google") > auth_key.txt

# Misc configurations
# sudo sysctl -w net.core.rmem_max=2500000 && sudo sysctl -w net.core.wmem_max=2500000
# sudo bash -c "ulimit -n 1000000 && ulimit -u 1000000"
sysctl -w net.core.rmem_max=2500000 && sysctl -w net.core.wmem_max=2500000
ulimit -n 1000000
ulimit -u 1000000
export PYTHONUNBUFFERED=TRUE

mkdir -p sfkit && chmod -R 777 sfkit
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh ./get-docker.sh
docker pull us-central1-docker.pkg.dev/dsp-artifact-registry/sfkit/sfkit # Pull image once

# TODO: don't hardcode API_URL
cat > run_docker_commands.sh << 'EOF'
#!/bin/bash
commands=("auth" "networking --ports 8020,8040" "generate_keys" "run_protocol")
for cmd in "${commands[@]}"
do
    docker run --net host --cap-add net_admin \
    -e "SFKIT_API_URL=https://sfkit-website-dev-bhj5a4wkqa-uc.a.run.app/api" \
    -e "SFKIT_PROXY_ON=true" \
    -e "PYTHONUNBUFFERED=TRUE" \
    -v $PWD/sfkit:/sfkit/.sfkit \
    -v $PWD/auth_key.txt:/sfkit/auth_key.txt:ro \
    us-central1-docker.pkg.dev/dsp-artifact-registry/sfkit/sfkit $cmd
done
EOF

chmod +x run_docker_commands.sh
nohup ./run_docker_commands.sh > output.log 2>&1 &