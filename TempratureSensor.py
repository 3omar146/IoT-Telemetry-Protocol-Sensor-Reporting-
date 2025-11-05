import socket, struct, time, random, hashlib

server_address = ('127.0.0.1', 9999)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3)

reporting_intervals = 1
device_id = 0
sensor_type = 0
seq = 0

HEADER_FORMAT = '!BBBBHHI'  # version,msg_type,count,sensor,device,seq,timestamp
VALUE_FORMAT  = '!f'
MAX_BATCH     = 3
#msg type 0=>init/1=>data/2=>heartbeat

def send_handshake():
    global device_id, seq
    packet = struct.pack(HEADER_FORMAT, 1, 0, 0, sensor_type, device_id, seq, int(time.time()))
    checksum = hashlib.md5(packet).digest()
    sock.sendto(packet + checksum, server_address)

    data, _ = sock.recvfrom(200)
    version, msg_type, _, sensor_type_recv, device_id_recv, last_seq, ts = struct.unpack(
        HEADER_FORMAT, data[:struct.calcsize(HEADER_FORMAT)]
    )

    device_id = device_id_recv
    seq = last_seq

    print(f"[INIT OK] Device={device_id}, Resume seq={seq}")

def send_single(value):
    global seq
    seq += 1
    packet = struct.pack(HEADER_FORMAT, 1, 1, 1, sensor_type, device_id, seq, int(time.time()))#header
    packet += struct.pack(VALUE_FORMAT, value)#payload

    checksum = hashlib.md5(packet).digest()
    sock.sendto(packet + checksum, server_address)

    print(f"[SINGLE] seq={seq}, value={value:.2f}")

def send_heartbeat():
    global seq
    seq += 1
    packet = struct.pack(HEADER_FORMAT, 1, 2, 0, sensor_type, device_id, seq, int(time.time()))
    
    checksum = hashlib.md5(packet).digest()
    sock.sendto(packet + checksum, server_address)

    print(f"[HEARTBEAT] seq={seq}")

def send_batch(values):
    global seq
    seq += 1
    count = len(values)

    header = struct.pack(HEADER_FORMAT, 1, 1, count, sensor_type, device_id, seq, int(time.time()))

    body = b''.join(struct.pack(VALUE_FORMAT, v) for v in values)
    packet = header + body

    checksum = hashlib.md5(packet).digest()
    sock.sendto(packet + checksum, server_address)

    print(f"[BATCH] seq={seq}, count={count}, values={[round(v,2) for v in values]}")

# ---------------- Start ----------------
send_handshake()

while True:
    next_seq = seq + 1

    # HEARTBEAT every 5th send -> heartbeat stands alone
    if next_seq % 5 == 0:
        send_heartbeat()
        time.sleep(reporting_intervals)
        continue
    # BATCH every 10th send → generate 3 readings with 3-second delay each
    if next_seq % 7 == 0:
        vals = []
        for _ in range(MAX_BATCH):
            val = random.uniform(20.0, 30.0)
            vals.append(val)
            print(f"[BATCH COLLECTION] {val:.2f}°C")
            time.sleep(reporting_intervals)  # wait 3 seconds between readings
        
        send_batch(vals)
        time.sleep(reporting_intervals)
        continue


    # Otherwise send a single reading
    value = random.uniform(20.0, 30.0)
    send_single(value)
    time.sleep(reporting_intervals)
