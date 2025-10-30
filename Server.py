import os
import socket, struct, time, csv,hashlib

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 9999))
print("Server started...")

recentPacketLimit = 5
recentPackets = {} #to store last n packets of each sensor to track duplicates
last_seq = {}          
last_heartbeat = {}
type_counters = [0,0,0]   #counts number of sensors for each type(for id generation)
device_map = {}      #maps each sensor to its id to allow same sensors to restart

filename = "SensorsLogs.csv"

file_exists = os.path.isfile(filename)
with open(filename, "a", newline='') as f:
    writer = csv.writer(f)
    if not file_exists or os.stat(filename).st_size == 0:
        writer.writerow(["Sensor Type", "ID", "Seq", "timestamp", "time arrived", "msg type", "temperature", "humidity", "pressure", "packet loss","duplicated"])
        print("Created file")
    else:
        print("File exists, appending")



    while True:
        packet, addr = sock.recvfrom(200)

        if len(packet) != 31: #ignore noise
            print(f"[WARN] Ignoring invalid packet ({len(packet)} bytes) from {addr}")
            continue

        #split to actual data and checksum
        data = packet[:-16]
        checksum = packet[-16:]

        version, msg_type, sensor_type, device_id, seq, timestamp, value = struct.unpack('!BBBHHIf', data)

        temp, hum, pres = "", "", ""
        loss_detected = ""

        #handshake
        if msg_type == 0:
            #check if the sensor was already assigned an id before
            if (addr, sensor_type) not in device_map:
                #assigne a new id by incrementing
                type_counters[sensor_type] = type_counters[sensor_type]+1
                device_id = type_counters[sensor_type]
                device_map[(addr, sensor_type)] = device_id

                # Send ID assignment back to sensor
                response = struct.pack('!BBBHHIf', 1, 10, sensor_type, device_id, 0, int(time.time()), 0.0)
                sock.sendto(response, addr)

                key = (sensor_type,device_id)
                if key not in recentPackets:
                    recentPackets[key] = [] #start a recent packets list

                print(f"[HANDSHAKE] New sensor registered (Type={sensor_type}) → ID={device_id} for {addr}")
            else:
                id = device_map[(addr, sensor_type)]
                seq = last_seq.get((sensor_type,id),0)+1
                response = struct.pack('!BBBHHIf', 1, 10, sensor_type, id , seq , int(time.time()), 0.0)
                sock.sendto(response, addr)
                print(f"[INFO] Sensor (Type={sensor_type}) from {addr} already registered with ID={device_map[(addr, sensor_type)]}")

        # Replace device_id with the assigned one
        assigned_id = device_map.get((addr, sensor_type), device_id)
        key = (sensor_type, assigned_id)
        last_seq_val = last_seq.get(key,0)
        last_seq[key] = seq

        #handle duplicates
        duplicate = False
        if seq in recentPackets[key]:
            duplicate = True
            print(f"Packet {seq} is duplicate")
        else:
            if(len(recentPackets[key])>recentPacketLimit):
                recentPackets[key].pop(0)
            recentPackets[key].append(seq)
            print(recentPackets[key])


        if msg_type == 1:
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
            last_heartbeat[key] = time.time()
            print(f"[HEARTBEAT] Device {device_id} is alive")
        print(sensor_type, device_id, seq, timestamp, time.time(),
            msg_type, temp, hum, pres, loss_detected)
        

        #checksum
        if  hashlib.md5(data).digest()  == checksum: #write  only valid data

            writer.writerow([
                sensor_type, device_id, seq, timestamp, time.time(),
                msg_type, temp, hum, pres, loss_detected,duplicate
            ])

            f.flush()

        else:
            print(f"Packet {seq} failed the checksum test")


        for (type, id), last_time in list(last_heartbeat.items()):
            if time.time() - last_time > 10:
                print(f"!!!Warning!!! {sensor_type} Sensor with id ={device_id}) stopped sending heartbeats!")
                del last_heartbeat[(sensor_type, device_id)]

