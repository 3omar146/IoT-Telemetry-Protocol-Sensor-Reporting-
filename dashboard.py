import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import time
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import os

# ===================== GLOBALS =====================
processes = {}
LOG_FILE = "SensorsLogs.csv"
TIMER = 60

# ===================== SERVER STARTUP =====================
def start_server():
    """Start the UDP sensor server automatically when the dashboard runs."""
    try:
        server_process = subprocess.Popen(["python", "Server.py"])
        print("Server started successfully.")
        return server_process
    except FileNotFoundError:
        messagebox.showerror("Error", "Server.py not found.")
        return None

# ===================== SENSOR CONTROL =====================
def start_sensor(name, file):
    """Start a sensor process."""
    if name not in processes:
        try:
            p = subprocess.Popen(["python", file])
            processes[name] = p
            status_labels[name].config(text=" Running", foreground="green")
        except FileNotFoundError:
            messagebox.showerror("Error", f"File {file} not found.")
    else:
        messagebox.showinfo("Info", f"{name} is already running.")

def stop_sensor(name):
    """Stop a sensor process."""
    if name in processes:
        processes[name].terminate()
        processes.pop(name)
        status_labels[name].config(text=" Stopped", foreground="red")
    else:
        messagebox.showinfo("Info", f"{name} is not running.")

def stop_all():
    """Stop all sensors."""
    for name in list(processes.keys()):
        stop_sensor(name)
    messagebox.showinfo("Info", "All sensors stopped.")

# ===================== CSV READER =====================
def load_data():
    """Load the latest data from SensorsLogs.csv."""
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame(columns=["Sensor Type","Temperature","Humidity","Pressure"])
    try:
        df = pd.read_csv(LOG_FILE)
        return df.tail(10)  # Show last 10 records
    except Exception as e:
        print(f"Error reading file: {e}")
        return pd.DataFrame(columns=["Sensor Type","Temperature","Humidity","Pressure"])

# ===================== TABLE UPDATER =====================
def update_table():
    """Refresh the data table periodically."""
    df = load_data()
    for row in tree.get_children():
        tree.delete(row)
    for _, r in df.iterrows():
        tree.insert("", "end", values=(
            r.get("Sensor Type", ""),
            r.get("ID", ""),
            r.get("Temperature", ""),
            r.get("Humidity", ""),
            r.get("Pressure", ""),
            r.get("Msg Type", ""),
            r.get("ReadingCount", "")
        ))
    root.after(2000, update_table)  # refresh every 5 seconds

# ===================== MATPLOTLIB GRAPH =====================
def update_graph():
    """Update the matplotlib graph inside Tkinter."""
    df = load_data()
    ax.clear()
    ax.set_title("Recent Sensor Readings")
    ax.set_xlabel("Time (last 10 readings)")
    ax.set_ylabel("Values")

    if not df.empty:
        if "Temperature" in df.columns:
            temp_vals = pd.to_numeric(df["Temperature"], errors="coerce")
            ax.plot(temp_vals, label="Temperature (°C)", color="red")
        if "Humidity" in df.columns:
            hum_vals = pd.to_numeric(df["Humidity"], errors="coerce")
            ax.plot(hum_vals, label="Humidity (%)", color="blue")
        if "Pressure" in df.columns:
            pres_vals = pd.to_numeric(df["Pressure"], errors="coerce")
            ax.plot(pres_vals, label="Pressure (hPa)", color="green")

        ax.legend()

    canvas.draw()
    root.after(2500, update_graph)

# ===================== GUI SETUP =====================
root = tk.Tk()
root.title("IoT Sensor Control Dashboard")
root.geometry("1000x700")
root.configure(bg="#f2f2f2")

# --- Title ---
tk.Label(root, text="IoT Sensor Control Dashboard", font=("Arial", 20, "bold"), bg="#f2f2f2").pack(pady=10)

# --- Control Frame ---
control_frame = tk.Frame(root, bg="#f2f2f2")
control_frame.pack(pady=10)

sensors = {
    "Temperature": "TempratureSensor.py",
    "Humidity": "HumiditySensor.py",
    "Pressure": "PressureSensor.py"
}

status_labels = {}

for i, (name, file) in enumerate(sensors.items()):
    tk.Label(control_frame, text=name, font=("Arial", 12), bg="#f2f2f2").grid(row=i, column=0, padx=15, pady=5)
    tk.Button(control_frame, text="Start", command=lambda n=name, f=file: start_sensor(n, f), bg="green", fg="white").grid(row=i, column=1, padx=5)
    tk.Button(control_frame, text="Stop", command=lambda n=name: stop_sensor(n), bg="red", fg="white").grid(row=i, column=2, padx=5)
    lbl = tk.Label(control_frame, text=" Stopped", fg="red", bg="#f2f2f2", font=("Arial", 10, "bold"))
    lbl.grid(row=i, column=3, padx=10)
    status_labels[name] = lbl

tk.Button(control_frame, text="Stop All", command=stop_all, bg="gray", fg="white").grid(row=len(sensors), column=1, pady=10)

# --- Data Table ---
table_frame = tk.Frame(root)
table_frame.pack(pady=15)

columns = ["Sensor Type", "ID", "Temperature", "Humidity", "Pressure", "Msg Type", "ReadingCount"]
tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=120, anchor="center")
tree.pack()

# --- Graph Frame ---
graph_frame = tk.Frame(root)
graph_frame.pack(pady=15)

fig, ax = plt.subplots(figsize=(7, 3))
canvas = FigureCanvasTkAgg(fig, master=graph_frame)
canvas.get_tk_widget().pack()

# ===================== BACKGROUND THREADS =====================
update_table()
update_graph()

# ===================== START SERVER ON LAUNCH =====================
server_process = start_server()

# ===================== TIMER =====================
def stop_all_after_timeout():
    time.sleep(TIMER)
    messagebox.showinfo("Timer","The {TIMER} seconds test timer is out")
    stop_all()
    if server_process:
        server_process.terminate()
    
    root.quit()

threading.Thread(target=stop_all_after_timeout, daemon=True).start()

# ===================== MAIN LOOP =====================
root.mainloop()

# ===================== CLEANUP ON CLOSE =====================
if server_process:
    server_process.terminate()
    print("Server stopped.")
