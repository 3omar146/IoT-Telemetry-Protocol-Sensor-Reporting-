import socket, struct, time, csv

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 9999))
print("Server started...")

last_seq = {}          
last_heartbeat = {}

with open('log.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        'sensor_type', 'device_id', 'seq', 'timestamp', 
        'arrival_time', 'msg_type', 'temperature', 'humidity', 'pressure', 'loss_detected'
    ])

    while True:
        data, addr = sock.recvfrom(200)
        version, msg_type, sensor_type, device_id, seq, timestamp, value = struct.unpack('!BBBHHIf', data)

        temp, hum, pres = "", "", ""
        loss_detected = ""

        key = (sensor_type, device_id)
        last_seq_val = last_seq.get(key)

        last_seq[key] = seq

        if msg_type == 0:
            print(f"[INIT] Type={sensor_type} Device={device_id} registered from {addr}")

        elif msg_type == 1:
            if last_seq_val is not None and seq != last_seq_val + 1:
                loss_detected = f"Missing {seq - last_seq_val - 1} packet(s)"
                print(f"[LOSS] {loss_detected} from (Type={sensor_type}, ID={device_id})")


            if sensor_type == 1:
                temp = value
            elif sensor_type == 2:
                hum = value
            elif sensor_type == 3:
                pres = value

            print(f"[DATA] Type={sensor_type} ID={device_id} seq={seq} value={value:.2f}")

        elif msg_type == 2:
            last_heartbeat[device_id] = time.time()
            print(f"[HEARTBEAT] Device {device_id} is alive")

        writer.writerow([
            sensor_type, device_id, seq, timestamp, time.time(),
            msg_type, temp, hum, pres, loss_detected
        ])
        f.flush()

        for d, last_time in list(last_heartbeat.items()):
            if time.time() - last_time > 10:
                print(f"[WARNING] Device {d} stopped sending heartbeats!")
                del last_heartbeat[d]
