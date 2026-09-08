#!/bin/bash
set -euo pipefail

umask 077
mkdir -p /run/coturn
chmod 755 /run/coturn
cd /run/coturn

get_secret() {
  docker run --rm --network host --entrypoint sh gcr.io/google.com/cloudsdktool/google-cloud-cli:alpine \
    -c "gcloud secrets versions access latest --project=${project_id} --secret=${secret}"
}

CONF="turnserver.conf"
CONF_DIR="/etc/coturn"
PRIVATE_IP=$(hostname -i)
SECRET=$(get_secret)
USER="65534:65534"

cat > "$${CONF}" <<EOF
listening-ip=${nlb_ip}
listening-ip=$${PRIVATE_IP}
relay-ip=${nlb_ip}
tls-listening-port=${turn_port}
dtls
cert=$${CONF_DIR}/cert.pem
pkey=$${CONF_DIR}/key.pem
realm=local
use-auth-secret
static-auth-secret=$${SECRET}
log-file=stdout
pidfile=/tmp/turnserver.pid
EOF
chmod 600 "$${CONF}"

openssl genrsa -out key.pem 2048
openssl req -new -x509 -key key.pem -out cert.pem \
  -days 7 -subj "/CN=sfkit-turn-server" -nodes
chown "$${USER}" ./*

iptables_add() {
  iptables -A INPUT "$@" -j ACCEPT
}
iptables_add -p udp -m multiport --dports ${turn_port},49152:65535
for range in ${hc_ranges}; do
  iptables_add -p tcp --dport ${turn_port} -s $${range}
done
ip addr add ${nlb_ip}/32 dev lo || true

docker rm -f coturn || true
docker run -d --name coturn --restart always --net host -u "$${USER}" -v "$${PWD}:$${CONF_DIR}:ro" \
  coturn/coturn:alpine -c "$${CONF_DIR}/turnserver.conf"
