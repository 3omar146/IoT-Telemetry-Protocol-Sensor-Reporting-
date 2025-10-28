import socket, struct, time, random

server_address = ('127.0.0.1', 9999)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3)

device_id = 0
sensor_type = 0  
seq = 0

#handshake
msg_type = 0
timestamp = int(time.time())
packet = struct.pack('!BBBHHIf', 1, msg_type, sensor_type, device_id, seq, timestamp, 0.0)
sock.sendto(packet, server_address)
print("Temprature sensor initilializing...")

data, _ = sock.recvfrom(200)
version, msg_type, sensor_type, new_id, last_seq, timestamp, value = struct.unpack('!BBBHHIf', data)
device_id = new_id #assign new/existing id
seq = last_seq  # resume from last known sequence
print(f"Sensor started, id={device_id}, seq={seq}")

while True:
    seq += 1
    timestamp = int(time.time())

    if seq % 5 == 0:
        msg_type = 2  #heartbeat
        value = 0.0
        print("[HEARTBEAT] Temperature sensor alive")
    else:
        msg_type = 1 
        value = random.uniform(20.0, 30.0)
        print(f"[DATA] Temp={value:.2f}°C seq={seq}")

    packet = struct.pack('!BBBHHIf', 1, msg_type, sensor_type, device_id, seq, timestamp, value)
    sock.sendto(packet, server_address)
    time.sleep(1)
