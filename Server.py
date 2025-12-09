import json
import os
import socket, struct, time, csv, hashlib

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 9999))
print("Server started...", flush=True)

######GLOBALS#########
HEADER_FORMAT = '!BBBBHHQ'

payload_limit_bytes = 200
recentPacketLimit = 5
recentPackets = {}
last_heartbeat = {}
counter = 0
device_map = {}

loss_tolerance = 0.05
losses = 0
packets_received = 0
total_report_size = 0
total_duplicates = 0
sequence_gap_count = 0
cpu_ms_per_report = 0
total_cpu_time = 0

#delay
avg_delay = 0
total_delay = 0

# -------- Reporting Interval --------
last_arrival = {}
reporting_interval_sum = 0
reporting_interval_count = 0

readings_file = "SensorsLogs.csv"
metrics_file = "Metrics.csv"



# ---------------------- send_metrics ----------------------
def send_metrics(bytes_per_report, packets_received, duplicate_rate,
                 sequence_gap_count, cpu_ms_per_report, loss_percent,
                 avg_reporting_interval,avg_delay):
    
    metrics_data = {
        "bytes_per_report": round(bytes_per_report, 2),
        "packets_received": packets_received,
        "duplicate_rate": round(duplicate_rate, 3),
        "sequence_gap_count": sequence_gap_count,
        "cpu_ms_per_report": round(cpu_ms_per_report, 3),
        "packet_loss": round(loss_percent, 3),
        "avg_reporting_interval": round(avg_reporting_interval, 3),
        "avg_delay": round(avg_delay, 3)
    }

    with open(metrics_file, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "bytes_per_report", "packets_received", "duplicate_rate",
            "sequence_gap_count", "cpu_ms_per_report",
            "packet_loss", "avg_reporting_interval", "avg_delay"
        ])
        writer.writerow([
            metrics_data["bytes_per_report"],
            metrics_data["packets_received"],
            metrics_data["duplicate_rate"],
            metrics_data["sequence_gap_count"],
            metrics_data["cpu_ms_per_report"],
            metrics_data["packet_loss"],
            metrics_data["avg_reporting_interval"],
            metrics_data["avg_delay"]
        ])


def msg_label(t):
    return {0:"INIT",1:"DATA",2:"HEARTBEAT"}.get(t,str(t))


# ---------------------- Initialize CSV (overwrite) ----------------------
with open(readings_file, "w", newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        "Sensor Type","ID","Seq","Timestamp","Arrival","Msg Type",
        "Temperature","Humidity","Pressure","Packet Loss","Duplicate","ReadingCount"
    ])
print("[CSV] SensorsLogs.csv overwritten.", flush=True)



header_size = struct.calcsize(HEADER_FORMAT)

# ========================= MAIN LOOP =========================
while True:
    try:
        packet, addr = sock.recvfrom(200)
        
        start = time.perf_counter()

        data = packet[:-16]
        checksum = packet[-16:]

        version, msg_type, count, sensor_type, dev_id, seq, timestamp = struct.unpack(
            HEADER_FORMAT, data[:header_size]
        )

        time_received = int(time.time()*1000)
        delay = time_received - timestamp
        
        # -------- Reporting Interval --------
        if dev_id in last_arrival:
            interval = time_received - last_arrival[dev_id]
            reporting_interval_sum += interval
            reporting_interval_count += 1
        last_arrival[dev_id] = time_received

        if reporting_interval_count > 0:
            avg_reporting_interval = reporting_interval_sum / reporting_interval_count
        else:
            avg_reporting_interval = 0


        # -------- Noise Check --------
        expected_size = count * 4 + header_size
        if expected_size != len(data) or len(packet) > 200:
            print("[NOISE] Invalid payload size", flush=True)
            continue
        else:
            total_report_size += len(packet)

        total_delay += delay
        index = header_size
        temp = hum = pres = ""
        loss_detected = 0
        duplicate = False
        label = msg_label(msg_type)


        # ---------- HANDSHAKE ----------
        if msg_type == 0:
            if (addr, sensor_type) not in device_map:
                counter += 1
                dev_id = counter
                device_map[(addr, sensor_type)] = dev_id

                response = struct.pack(HEADER_FORMAT, 1, 10, 0, sensor_type, dev_id, 0, int(time.time()))
                sock.sendto(response, addr)

                recentPackets[dev_id] = []
                print(f"[HANDSHAKE] Type={sensor_type} assigned ID={dev_id}", flush=True)

            else:
                dev_id = device_map[(addr, sensor_type)]
                seq = max(recentPackets.get(dev_id, [0])) + 1
                response = struct.pack(HEADER_FORMAT, 1, 10, 0, sensor_type, dev_id, seq, int(time.time()))
                sock.sendto(response, addr)
                print(f"[INFO] Device already registered (ID={dev_id})", flush=True)


        # ---------- DUPLICATE + LOSS ----------
        if seq in recentPackets.get(dev_id, []):
            duplicate = True
            total_duplicates += 1
            print(f"[DUPLICATE] seq={seq}", flush=True)
        else:
            if dev_id in recentPackets and recentPackets[dev_id]:
                max_seq = max(recentPackets[dev_id])
                if seq > max_seq + 1:
                    loss_detected = seq - max_seq - 1
                    losses += loss_detected
                    sequence_gap_count += 1
                    print(f"[LOSS] Missing {loss_detected} packets", flush=True)

            recentPackets.setdefault(dev_id, []).append(seq)
            if len(recentPackets[dev_id]) > recentPacketLimit:
                recentPackets[dev_id].pop(0)

        packets_received += 1


        # ---------- DATA ----------
        batch_values_str = None

        if msg_type == 1:
            values = []
            for _ in range(count):
                v = struct.unpack('!f', data[index:index+4])[0]
                index += 4
                values.append(v)

            if count == 1:
                v = values[0]
                if sensor_type == 0: temp = v
                if sensor_type == 1: hum = v
                if sensor_type == 2: pres = v
                print(f"[DATA] Single: Type={sensor_type} ID={dev_id} seq={seq} = {v:.2f}", flush=True)

            else:
                batch_values_str = ",".join([f"{v:.2f}" for v in values])
                print(f"[BATCH seq={seq}] {batch_values_str}", flush=True)


        # ---------- HEARTBEAT ----------
        if msg_type == 2:
            last_heartbeat[dev_id] = time.time()
            print(f"[HEARTBEAT] Device {dev_id} alive", flush=True)


        # ---------- CHECKSUM & CSV ----------
        if hashlib.md5(data).digest() == checksum:

            with open(readings_file, "a", newline='') as f:
                writer = csv.writer(f)

                if batch_values_str is not None:
                    if sensor_type == 0: temp = batch_values_str
                    elif sensor_type == 1: hum = batch_values_str
                    elif sensor_type == 2: pres = batch_values_str

                    writer.writerow([
                        sensor_type, dev_id, seq, round(timestamp,3), round(time.time(),3),
                        label, temp, hum, pres, loss_detected, duplicate, count
                    ])
                else:
                    writer.writerow([
                        sensor_type, dev_id, seq, round(timestamp,3), round(time.time(),3),
                        label,
                        f"{temp:.2f}" if temp != "" else "",
                        f"{hum:.2f}" if hum != "" else "",
                        f"{pres:.2f}" if pres != "" else "",
                        loss_detected, duplicate, count
                    ])

        else:
            print(f"[CHECKSUM ERROR] seq={seq}", flush=True)


        # ---------- METRICS ----------
        avg_delay = total_delay / packets_received if packets_received else 0
        loss_percent = (losses / (losses + packets_received)) * 100 if packets_received + losses > 0 else 0
        bytes_per_report = total_report_size / packets_received if packets_received else 0
        duplicate_rate = total_duplicates / packets_received if packets_received else 0

        end = time.perf_counter()
        total_cpu_time += (end - start) * 1000
        cpu_ms_per_report = total_cpu_time / packets_received if packets_received else 0

        send_metrics(bytes_per_report, packets_received, duplicate_rate,
                     sequence_gap_count, cpu_ms_per_report,
                     loss_percent, avg_reporting_interval,avg_delay)


        # ---------- HEARTBEAT TIMEOUT ----------
        for id, last in list(last_heartbeat.items()):
            if time.time() - last > 20:
                print(f"[WARNING] ID={id} missed heartbeat!", flush=True)
                del last_heartbeat[id]

    except Exception as e:
        print(f"[SERVER ERROR] {e}", flush=True)
