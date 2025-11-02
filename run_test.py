import subprocess
import time

# Start the server first
server = subprocess.Popen(["python", "server.py"])
time.sleep(2)  # Wait for server to initialize

# Start the sensors
temp = subprocess.Popen(["python", "tempsensor.py"])
hum  = subprocess.Popen(["python", "humiditysensor.py"])
pres = subprocess.Popen(["python", "pressuresensor.py"])

print("✅ All components started. Running baseline local test...")

try:
    # Keep running until manually stopped
    server.wait()
except KeyboardInterrupt:
    print("\nStopping all processes...")
    temp.terminate()
    hum.terminate()
    pres.terminate()
    server.terminate()
