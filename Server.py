import os
import socket, struct, time, csv, hashlib

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 9999))
print("Server started...")

recentPacketLimit = 5
recentPackets = {}
last_heartbeat = {}
type_counters = [0,0,0]
device_map = {}

filename = "SensorsLogs.csv"

def msg_label(t):
    return {0:"INIT",1:"DATA",2:"HEARTBEAT"}.get(t,str(t))

# ---------- FILE INITIALIZE ----------
file_exists = os.path.isfile(filename)
with open(filename, "a", newline='') as f:
    writer = csv.writer(f)
    if not file_exists or os.stat(filename).st_size == 0:
        writer.writerow(["Sensor Type","ID","Seq","Timestamp","Arrival","Msg Type",
                         "Temperature","Humidity","Pressure","Packet Loss","Duplicate","ReadingCount"])
        print("Created file")
    else:
        print("File exists, appending")

# ---------- MAIN LOOP ----------
while True:
    packet, addr = sock.recvfrom(200)

    data = packet[:-16]
    checksum = packet[-16:]

    version, msg_type, count, sensor_type, dev_id, seq, timestamp = \
    struct.unpack('!BBBBHHI', data[:struct.calcsize('!BBBBHHI')])

    index = struct.calcsize('!BBBBHHI')

    temp = hum = pres = ""
    loss_detected = 0
    duplicate = False

    key = (sensor_type, dev_id)
    label = msg_label(msg_type)  # text for CSV only

    # ---------- HANDSHAKE ----------
    if msg_type == 0:
        if (addr, sensor_type) not in device_map:
            type_counters[sensor_type] += 1
            dev_id = type_counters[sensor_type]
            device_map[(addr, sensor_type)] = dev_id

            response = struct.pack('!BBBBHHI', 1, 10, 0, sensor_type, dev_id, 0, int(time.time()))
            sock.sendto(response, addr)

            recentPackets[key] = []
            print(f"[HANDSHAKE] New device Type={sensor_type} → ID={dev_id}")

        else:
            dev_id = device_map[(addr, sensor_type)]
            seq = max(recentPackets.get(key, [0])) + 1
            response = struct.pack('!BBBBHHI', 1, 10, 0, sensor_type, dev_id, seq, int(time.time()))
            sock.sendto(response, addr)
            print(f"[INFO] Device already registered (Type={sensor_type}, ID={dev_id})")

    # ---------- DUPLICATE & LOSS CHECK ----------
    if seq in recentPackets.get(key, []):
        duplicate = True
        print(f"[DUPLICATE] Type={sensor_type} ID={dev_id} seq={seq}")
    else:
        if key in recentPackets and recentPackets[key]:
            max_seq = max(recentPackets[key])
            if seq > max_seq + 1:
                loss_detected = seq - max_seq - 1
                print(f"[LOSS] Missing {loss_detected} packets (Type={sensor_type}, ID={dev_id})")

        recentPackets.setdefault(key, []).append(seq)
        if len(recentPackets[key]) > recentPacketLimit:
            recentPackets[key].pop(0)

    # ---------- DATA ----------
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
            print(f"[DATA] Single → Type={sensor_type} ID={dev_id} seq={seq} = {v:.2f}")
        else:
            print(f"[DATA BATCH] seq={seq}, count={count}, values={[round(v,2) for v in values]}")
            values_str = ",".join([f"{v:.2f}" for v in values])

            with open(filename, "a", newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    sensor_type, dev_id, seq, round(timestamp,3),
                    round(time.time(),3), label,
                    values_str, "", "", loss_detected, duplicate, count
                ])
            continue  # batch already logged

    # ---------- HEARTBEAT ----------
    if msg_type == 2:
        last_heartbeat[key] = time.time()
        print(f"[HEARTBEAT] Device {dev_id} alive")

    # ---------- CHECKSUM + CSV LOG (single or INIT/Heartbeat) ----------
    if hashlib.md5(data).digest() == checksum:
        with open(filename, "a", newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                sensor_type, dev_id, seq, round(timestamp,3),
                round(time.time(),3), label,
                f"{temp:.2f}" if temp != "" else "",
                f"{hum:.2f}" if hum != "" else "",
                f"{pres:.2f}" if pres != "" else "",
                loss_detected, duplicate, count
            ])
    else:
        print(f"[CHECKSUM ERROR] seq={seq}")

    # ---------- HEARTBEAT TIMEOUT ----------
    for (stype, did), last in list(last_heartbeat.items()):
        if time.time() - last > 10:
            print(f"[WARNING] Device Type={stype} ID={did} missed heartbeat!")
            del last_heartbeat[(stype, did)]
