#!/usr/bin/env bash
set -e

# Reset network conditions
sudo tc qdisc del dev lo root 2>/dev/null || true
echo "[BASELINE] Network reset: no loss, no delay, no jitter."

# ---- 60-second packet capture ----
OUTPUT="baseline_trace.pcap"

echo "[CAPTURE] Starting packet capture for 60 seconds..."
sudo tcpdump -i lo -w "$OUTPUT" >/dev/null 2>&1 &
TCPDUMP_PID=$!

sleep 60

echo "[CAPTURE] Stopping capture..."
sudo kill "$TCPDUMP_PID" 2>/dev/null || true

echo "[CAPTURE] Saved as $OUTPUT"
