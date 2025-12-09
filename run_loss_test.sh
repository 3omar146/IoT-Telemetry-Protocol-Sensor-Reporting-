#!/usr/bin/env bash
set -e

# Clear old settings
sudo tc qdisc del dev lo root 2>/dev/null || true

# Apply 5% packet loss
sudo tc qdisc add dev lo root netem loss 5%

echo "[LOSS TEST] Applied 5% packet loss on loopback."
