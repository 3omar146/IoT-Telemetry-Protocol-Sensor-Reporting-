#!/usr/bin/env bash
set -e

# Clear old settings
sudo tc qdisc del dev lo root 2>/dev/null || true

# Apply delay and jitter
sudo tc qdisc add dev lo root netem delay 100ms 10ms

echo "[DELAY TEST] Applied 100ms delay with ±10ms jitter on loopback."
