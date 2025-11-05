import json
import os
import socket, struct, time, csv, hashlib
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 9999))
console.print("[bold green]Server started...[/bold green]")

######GLOBALS#########
payload_limit_bytes = 200
recentPacketLimit = 5
recentPackets = {}
last_heartbeat = {}
counter = 0
device_map = {}
#constrains and metrics
loss_tolerance = 0.05
losses = 0
packets_sent = 0
packets_received = 0
total_report_size = 0
total_duplicates = 0
sequence_gap_count = 0
cpu_ms_per_report = 0
total_cpu_time = 0

readings_file = "SensorsLogs.csv"
metrics_file = "Metrics.csv"


dashboard_addr = ('127.0.0.1', 9998)  # Dashboard IP and port

def send_metrics(bytes_per_report,packets_received,duplicate_rate,sequence_gap_count,cpu_ms_per_report,loss_percent):
    metrics_data = {
        "bytes_per_report": round(bytes_per_report, 2),
        "packets_received": packets_received,
        "duplicate_rate": round(duplicate_rate, 3),
        "sequence_gap_count": sequence_gap_count,
        "cpu_ms_per_report": round(cpu_ms_per_report, 3),
        "packet_loss":  round(loss_percent, 3)
    }
    sock.sendto(json.dumps(metrics_data).encode(),dashboard_addr)

    #store in csv
    with open(metrics_file, "w", newline='') as f:  # 'w' mode clears previous content
        writer = csv.writer(f)
        # Write header
        writer.writerow(["bytes_per_report",
                         "packets_received",
                         "duplicate_rate",
                         "sequence_gap_count",
                         "cpu_ms_per_report",
                         "packet_loss"])
        # Write the latest metrics
        writer.writerow([
            metrics_data["bytes_per_report"],
            metrics_data["packets_received"],
            metrics_data["duplicate_rate"],
            metrics_data["sequence_gap_count"],
            metrics_data["cpu_ms_per_report"],
            metrics_data["packet_loss"]
        ])

def msg_label(t):
    return {0:"INIT",1:"DATA",2:"HEARTBEAT"}.get(t,str(t))

# ---------- FILE INITIALIZE ----------
file_exists = os.path.isfile(readings_file)
with open(readings_file, "a", newline='') as f:
    writer = csv.writer(f)
    if not file_exists or os.stat(readings_file).st_size == 0:
        writer.writerow(["Sensor Type","ID","Seq","Timestamp","Arrival","Msg Type",
                         "Temperature","Humidity","Pressure","Packet Loss","Duplicate","ReadingCount"])
        console.print("[yellow]Created new CSV file.[/yellow]")
    else:
        console.print("[cyan]File exists, appending to it.[/cyan]")

file_exists = os.path.isfile(metrics_file)

header_size = struct.calcsize('!BBBBHHI')
# -------- MAIN LOOP ---------
while True:
    packet, addr = sock.recvfrom(200)

    total_cpu_time = 0
    start = time.perf_counter() #for cpu time

    data = packet[:-16]
    checksum = packet[-16:]

    version, msg_type, count, sensor_type, dev_id, seq, timestamp = struct.unpack('!BBBBHHI', data[:struct.calcsize('!BBBBHHI')])

    #------NOISE AND MAXIMUM PAYLOAD-------
    expected_size = count*4 + header_size
    if(expected_size != len(data) or len(packet)>200): #detect noise data and maximum payload
        print(f"[red][NOISE]Noise detected or data may have exceeded the maximum payload")
        continue
    else:
        total_report_size += len(packet)

        index = header_size

        temp = hum = pres = ""
        loss_detected = 0
        duplicate = False

        label = msg_label(msg_type)

        # ---------- HANDSHAKE --------
        if msg_type == 0:
            if (addr, sensor_type) not in device_map:
                counter += 1
                dev_id = counter
                device_map[(addr, sensor_type)] = dev_id

                response = struct.pack('!BBBBHHI', 1, 10, 0, sensor_type, dev_id, 0, int(time.time()))
                sock.sendto(response, addr)

                recentPackets[dev_id] = []
                console.print(f"[bold blue][HANDSHAKE][/bold blue] New device Type={sensor_type} → ID={dev_id}")

            else:
                dev_id = device_map[(addr, sensor_type)]
                seq = max(recentPackets.get(dev_id, [0])) + 1
                response = struct.pack('!BBBBHHI', 1, 10, 0, sensor_type, dev_id, seq, int(time.time()))
                sock.sendto(response, addr)
                console.print(f"[dim cyan][INFO][/dim cyan] Device already registered (Type={sensor_type}, ID={dev_id})")

        # ---------- DUPLICATE & LOSS CHECK --------
        if seq in recentPackets.get(dev_id, []):
            duplicate = True
            total_duplicates +=1
            console.print(f"[red][DUPLICATE][/red] Type={sensor_type} ID={dev_id} seq={seq}")
        else:
            if dev_id in recentPackets and recentPackets[dev_id]:
                max_seq = max(recentPackets[dev_id])
                if seq > max_seq + 1:
                    loss_detected = seq - max_seq - 1
                    losses += loss_detected
                    sequence_gap_count+=1
                    packets_sent+=loss_detected #coungt lost packets as sent packets
                    console.print(f"[yellow][LOSS][/yellow] Missing {loss_detected} packets (Type={sensor_type}, ID={dev_id})")

            recentPackets.setdefault(dev_id, []).append(seq)
            if len(recentPackets[dev_id]) > recentPacketLimit:
                recentPackets[dev_id].pop(0)

        packets_sent +=1
        packets_received +=1

        # -------- DATA ----------
        batch_values_str = None
        if msg_type == 1:
            values = []
            for _ in range(count):
                value = struct.unpack('!f', data[index:index+4])[0]
                index += 4
                values.append(value)

            if count == 1:
                v = values[0]
                if sensor_type == 0: temp = v
                if sensor_type == 1: hum = v
                if sensor_type == 2: pres = v
                console.print(f"[green][DATA][/green] Single → Type={sensor_type} ID={dev_id} seq={seq} = {v:.2f}")
            else:
                batch_values_str = ",".join([f"{v:.2f}" for v in values])
                # pretty-print the batch in a mini table
                table = Table(title=f"[bold cyan]BATCH DATA seq={seq}[/bold cyan]", box=box.MINIMAL_DOUBLE_HEAD)
                table.add_column("Index", justify="center")
                table.add_column("Value", justify="center")
                for i, v in enumerate(values, 1):
                    table.add_row(str(i), f"{v:.2f}")
                console.print(table)

        # -------- HEARTBEAT ----------
        if msg_type == 2:
            last_heartbeat[dev_id] = time.time()
            console.print(f"[magenta][HEARTBEAT][/magenta] Device {dev_id} alive")

        # ---------- CHECKSUM + CSV LOG ----------
        if hashlib.md5(data).digest() == checksum:
            with open(readings_file, "a", newline='') as f:
                writer = csv.writer(f)
                if batch_values_str is not None:
                    if sensor_type == 0:
                        temp = batch_values_str
                    elif sensor_type == 1:
                        hum = batch_values_str
                    elif sensor_type == 2:
                        pres = batch_values_str

                    writer.writerow([sensor_type, dev_id, seq, round(timestamp,3),
                                    round(time.time(),3), label,
                                    temp, hum, pres, loss_detected, duplicate, count])
                else:
                    writer.writerow([sensor_type, dev_id, seq, round(timestamp,3),
                                    round(time.time(),3), label,
                                    f"{temp:.2f}" if temp != "" else "",
                                    f"{hum:.2f}" if hum != "" else "",
                                    f"{pres:.2f}" if pres != "" else "",
                                    loss_detected, duplicate, count])
        else:
            console.print(f"[red][CHECKSUM ERROR][/red] seq={seq}")

        loss_percent = losses/packets_sent
        if(loss_percent > loss_tolerance): #check packet loss percentage
            print(f"[red][Packet loss limit exceeded] packet loss = {losses/packets_sent}")

        bytes_per_report = total_report_size/packets_received
        duplicate_rate = total_duplicates/packets_received
        send_metrics(bytes_per_report,packets_received,duplicate_rate,sequence_gap_count,cpu_ms_per_report,loss_percent)

        #--------- HEARTBEAT TIMEOUT ----------
        for id, last in list(last_heartbeat.items()):
            if time.time() - last > 20:
                console.print(f"[bold yellow][WARNING][/bold yellow] ID={id} missed heartbeat!")
                del last_heartbeat[id]

        end = time.perf_counter()    #stop timing
        total_cpu_time += (end - start) * 1000
        cpu_ms_per_report = total_cpu_time / packets_received if packets_received else 0
