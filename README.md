# IoT Telemetry Protocol – Sensor Reporting System

## Overview

This project implements a **custom lightweight IoT telemetry protocol over UDP** for periodic sensor reporting.  
It was developed as part of a **Computer Networks course project** with emphasis on:

- Application-layer protocol design over UDP
- Loss-tolerant telemetry (no retransmissions)
- Sensor batching and heartbeats
- Controlled network experiments (loss, delay, jitter)
- Reproducible testing and metric collection

The system consists of **sensor clients**, a **collector server**, and a **dashboard GUI**.  
All **experiments and network impairment tests are executed from the terminal**, while the **dashboard is used only for control, visualization, and orchestration**.

---

## Architecture

### Components

1. **Collector Server**
   - UDP-based telemetry collector
   - Assigns device IDs during INIT handshake
   - Maintains per-device state
   - Detects:
     - Duplicate packets
     - Sequence gaps (packet loss)
     - Packet reordering using timestamps
   - Logs all received packets to CSV
   - Computes runtime metrics (loss, delay, CPU usage)

2. **Sensor Clients**
   - Simulated IoT devices:
     - Temperature
     - Humidity
     - Pressure
   - Periodically send:
     - Single readings
     - Batched readings
     - Heartbeat messages
   - Stateless, loss-tolerant by design
   - Configurable batch size and server IP at runtime
   - Three types: Temperature, Humidity and Pressure
   

3. **Dashboard (GUI)**
   - Built using **CustomTkinter**
   - Used for:
     - Starting/stopping server and sensors
     - Setting test duration and batch size
     - Selecting server IP
     - Viewing live logs, metrics, and latest readings
   - **Does NOT apply network impairments**
   - **Does NOT replace terminal-based test scripts**

---

## Project Structure

```
.
├── Dashboard.py
├── Server.py
├── TemperatureSensor.py
├── HumiditySensor.py
├── PressureSensor.py
├──run_loss_test.sh
├──run_delay_test.sh
├──run_baseline_test.sh
├── Logs/
├── SensorsLogs.csv
├── Metrics.csv
└── README.md
```

---

## Requirements

### General
- Python **3.9+**
- Linux (native or WSL2) for testing
- Windows supported for dashboard usage

### Python Dependencies
```bash
pip install customtkinter pandas
```

---

## ⚠️ IMPORTANT: How This Project Is Intended to Be Run

### ✔ Terminal = Testing Environment  
### ✔ Dashboard = Control & Visualization Only

- **All network experiments (baseline, loss, delay, jitter)**  
  are executed **from the terminal using bash scripts**
- The **dashboard is NOT responsible** for:
  - Applying netem
  - Running bash test scripts
- The dashboard is used **after or during tests** to:
  - Launch server/sensors
  - Monitor logs
  - View metrics and live data

This separation is **intentional** and required for reproducibility.

---

## Running Experiments (Correct Workflow)

### 1️⃣ Prepare the Test Environment (Terminal)

All tests **must be executed from a Linux terminal**.

If you are on Windows:
- Install **WSL2**
- Run tests inside a **WSL terminal**
```bash
wsl
```

Install required tools:
```bash
sudo apt update
sudo apt install python3 python3-pip iproute2
pip3 install pandas
```

---

### 2️⃣ Run Test Scripts (Terminal Only)
individual scenarios:
```bash
bash run_baseline_test.sh
bash run_loss_test.sh
bash run_delay_test.sh
```

These scripts:
- Apply `tc netem` rules
- Start the server and sensors
- Collect CSV logs and metrics
- Produce a 60-seconds pcap trace capture
- Remove netem rules after completion

⚠️ **You can NOT run these scripts from the dashboard**

---

### 3️⃣ Using netem Manually (Optional)

Example commands:
```bash
sudo tc qdisc add dev eth0 root netem loss 5%
sudo tc qdisc add dev eth0 root netem delay 100ms 10ms
sudo tc qdisc del dev eth0 root
```

---

## Using the Dashboard

### Start Dashboard
```bash
python Dashboard.py
```

### Dashboard Usage Rules

- Dashboard **starts/stops**:
  - Server
  - Sensor clients
- Dashboard **visualizes**:
  - Latest readings
  - Server terminal output
  - Computed metrics
- Dashboard **does NOT**:
  - Apply netem
  - Run bash test scripts
  - Replace terminal-based testing

---

### Server IP Configuration

- Default: `127.0.0.1`
  - Used when **not running WSL**
- When running tests inside WSL:
  1. Find WSL IP:
     ```bash
     ip addr
     ```
  2. Enter the WSL IP in the dashboard **Server IP** field
  3. Start the server from the dashboard

This is required because WSL uses a dynamic virtual network.

---

## Logging & Metrics

- `Logs/` → per-process logs
- `SensorsLogs.csv` → received telemetry data
- `Metrics.csv` → performance metrics

These files are used for:
- Post-processing
- Plot generation
- Report analysis

---

## Authors

**Team Members**
- Nouran Mohamed  
- Reetaj Ahmed  
- Eslam Fawzy  
- Hassan Ghallab  
- Mohamed Wael  
- **Omar Tamer**  

**Course:** Computer Networking

---

## License

This project is for **educational use only** as part of a Computer Networking course.
