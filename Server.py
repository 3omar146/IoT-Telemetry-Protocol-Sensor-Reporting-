import os
import socket, struct, time, csv,hashlib

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 9999))
print("Server started...")

recentPacketLimit = 5
recentPackets = {} #to store last n packets of each sensor to track duplicates
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

        version, message_type, sensor_type, id, seq, timestamp, value = struct.unpack('!BBBHHIf', data)

        temp, hum, pres = "", "", ""
        loss_detected = 0

        #handshake
        if message_type == 0:
            #check if the sensor was already assigned an id before
            if (addr, sensor_type) not in device_map:
                #assigne a new id by incrementing
                type_counters[sensor_type] = type_counters[sensor_type]+1
                id = type_counters[sensor_type]
                device_map[(addr, sensor_type)] = id

                # Send ID assignment back to sensor
                response = struct.pack('!BBBHHIf', 1, 10, sensor_type, id, 0, int(time.time()), 0.0)
                sock.sendto(response, addr)

                key = (sensor_type,id)
                if key not in recentPackets:
                    recentPackets[key] = [] #start a recent packets list

                print(f"[HANDSHAKE] New sensor registered (Type={sensor_type}) → ID={id} for {addr}")
                
            else:
                id = device_map[(addr, sensor_type)]
                key = (sensor_type, id)
                if recentPackets[key]:
                    seq = max(recentPackets[key])+1
                response = struct.pack('!BBBHHIf', 1, 10, sensor_type, id , seq , int(time.time()), 0.0)
                sock.sendto(response, addr)
                print(f"[INFO] Sensor (Type={sensor_type}) from {addr} already registered with ID={device_map[(addr, sensor_type)]}")

        
        key = (sensor_type, id)
        

        #handle duplicates
        duplicate = False
        if seq in recentPackets[key]:
            duplicate = True
            print(f"Packet {seq} is duplicate")
        else:
            #check losses
            if recentPackets[key]:
                max_seq = max(recentPackets[key])
                if seq > max_seq + 1:
                    loss_detected = seq - max_seq - 1
                    print(f"There are {loss_detected} losses from type={sensor_type}, id={id})")

            #add the packet to recents
            if(len(recentPackets[key])>recentPacketLimit): 
                recentPackets[key].pop(0)
            recentPackets[key].append(seq)


        if message_type == 1: 
            if sensor_type == 0:
                temp = value
            elif sensor_type == 1:
                hum = value
            elif sensor_type == 2:
                pres = value

            print(f"[DATA] Type={sensor_type} ID={id} seq={seq} value={value:.2f}")

        elif message_type == 2:
            last_heartbeat[key] = time.time()
            print(f"[HEARTBEAT] Device {id} is alive")
        print(sensor_type, id, seq, timestamp, time.time(),
            message_type, temp, hum, pres, loss_detected)
        

        #checksum
        if  hashlib.md5(data).digest()  == checksum: #write  only valid data
            print("data valid")
            writer.writerow([
                sensor_type, id, seq, round(timestamp,3), round(time.time(),3),
                message_type, temp, hum,pres, loss_detected,duplicate
            ])

            f.flush()

        else:
            print(f"Packet {seq} failed the checksum test")


        for (type, id), last_time in list(last_heartbeat.items()):
            if time.time() - last_time > 10:
                print(f"!!!Warning!!! {sensor_type} Sensor with id ={id}) stopped sending heartbeats!")
                del last_heartbeat[(sensor_type, id)]

