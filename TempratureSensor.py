import socket, struct, time, random

server_address = ('127.0.0.1', 9999)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

device_id = 1
sensor_type = 1  
seq = 0

msg_type = 0
timestamp = int(time.time())
packet = struct.pack('!BBBHHIf', 1, msg_type, sensor_type, device_id, seq, timestamp, 0.0)
sock.sendto(packet, server_address)
print("[INIT] Temperature sensor started")

while True:
    seq += 1
    timestamp = int(time.time())

    if seq % 5 == 0:
        msg_type = 2 
        value = 0.0
        print("[HEARTBEAT] Temperature sensor alive")
    else:
        msg_type = 1  
        value = random.uniform(20.0, 30.0)
        print(f"[DATA] Temp={value:.2f}°C seq={seq}")

    packet = struct.pack('!BBBHHIf', 1, msg_type, sensor_type, device_id, seq, timestamp, value)
    sock.sendto(packet, server_address)
    time.sleep(1)
