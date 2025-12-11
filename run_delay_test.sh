#!/usr/bin/env bash
set -e

# Clear old settings
sudo tc qdisc del dev lo root 2>/dev/null || true

# Apply delay and jitter
sudo tc qdisc add dev lo root netem delay 100ms 10ms

echo "[DELAY TEST] Applied 100ms delay with ±10ms jitter on loopback."


# ---- 60-second packet capture ----
OUTPUT="delay_trace.pcap"

echo "[CAPTURE] Starting packet capture for 60 seconds..."
sudo tcpdump -i lo -w "$OUTPUT" >/dev/null 2>&1 &
TCPDUMP_PID=$!

sleep 60

echo "[CAPTURE] Stopping capture..."
sudo kill "$TCPDUMP_PID" 2>/dev/null || true

echo "[CAPTURE] Saved as $OUTPUT"