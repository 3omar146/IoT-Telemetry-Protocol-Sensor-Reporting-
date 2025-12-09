#!/usr/bin/env bash
set -e

# Reset network conditions
sudo tc qdisc del dev lo root 2>/dev/null || true

echo "[BASELINE] Network reset: no loss, no delay, no jitter."
