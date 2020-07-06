#!/bin/bash
PUBLIC_IP=`wget -qO- ipinfo.io/ip`
echo "Starting cardano-node with IP: $PUBLIC_IP"
cardano-node run \
  --topology /opt/node/shelley_testnet-topology.json \
  --database-path /opt/node/db \
  --socket-path /opt/node/db/node.socket \
  --host-addr $PUBLIC_IP \
  --port 3001 \
  --config /opt/node/shelley_testnet-config.json
