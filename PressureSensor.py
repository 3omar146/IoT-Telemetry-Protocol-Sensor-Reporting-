import socket, struct, time, random

server_address = ('127.0.0.1', 9999)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

device_id = 3
sensor_type = 3  
seq = 0

msg_type = 0  
timestamp = int(time.time())
packet = struct.pack('!BBBHHIf', 1, msg_type, sensor_type, device_id, seq, timestamp, 0.0)
sock.sendto(packet, server_address)
print("[INIT] Pressure sensor started")

while True:
    seq += 1
    timestamp = int(time.time())

    if seq % 5 == 0:
        msg_type = 2  
        value = 0.0
        print("[HEARTBEAT] Pressure sensor alive")
    else:
        msg_type = 1  
        value = random.uniform(0.8, 1.2)  
        print(f"[DATA] Pressure={value:.2f} bar seq={seq}")
    packet = struct.pack('!BBBHHIf', 1, msg_type, sensor_type, device_id, seq, timestamp, value)
    sock.sendto(packet, server_address)
    time.sleep(1)
