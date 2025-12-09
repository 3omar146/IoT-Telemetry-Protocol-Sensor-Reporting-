import customtkinter as ctk
import subprocess, threading, time, os, sys, pandas as pd
from tkinter import messagebox, ttk
import re
import shutil

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(PROJECT_DIR, "Logs")
os.makedirs(LOGS_DIR, exist_ok=True)

SENSORS_LOG = os.path.join(PROJECT_DIR, "SensorsLogs.csv")
METRICS_CSV = os.path.join(PROJECT_DIR, "Metrics.csv")

SENSORS = {
    "Temperature": "TemperatureSensor.py",
    "Humidity": "HumiditySensor.py",
    "Pressure": "PressureSensor.py"
}

processes = {}
running_counts = {name: 0 for name in SENSORS}
log_counters = {"Temperature": 0, "Humidity": 0, "Pressure": 0}

REFRESH_MS = 600
ansi_escape = re.compile(r'\x1b[^m]*m')


def apply_dark_theme():
    style = ttk.Style()
    style.theme_create("darktheme", parent="clam", settings={
        "TFrame": {"configure": {"background": "#222222"}},
        "Treeview": {
            "configure": {
                "background": "#1a1a1a",
                "fieldbackground": "#1a1a1a",
                "foreground": "white",
                "rowheight": 28,
                "bordercolor": "#444444",
                "borderwidth": 1
            },
            "map": {
                "background": [("selected", "#3A8DFF")],
                "foreground": [("selected", "white")]
            }
        },
        "Treeview.Heading": {
            "configure": {
                "background": "#111111",
                "foreground": "white",
                "font": ("Segoe UI", 11, "bold")
            }
        }
    })
    style.theme_use("darktheme")


def spawn_process(cmd_list, tag):
    base = tag if tag == "SERVER" else tag.split("_")[0]
    if base != "SERVER":
        log_counters[base] += 1
        logfile_path = os.path.join(LOGS_DIR, f"{base}{log_counters[base]}.log")
    else:
        logfile_path = os.path.join(LOGS_DIR, "Server.log")

    logfile = open(logfile_path, "a", buffering=1)

    p = subprocess.Popen(
        cmd_list,
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    processes[tag] = (p, logfile)
    return p, logfile


def stop_process(tag):
    item = processes.get(tag)
    if not item:
        return
    p, log = item
    try:
        if p.poll() is None:
            p.terminate()
            p.wait(timeout=2)
    except:
        try:
            p.kill()
        except:
            pass

    try:
        log.close()
    except:
        pass

    processes.pop(tag, None)


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class Dashboard(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("IoT Sensor Dashboard")
        self.geometry("1500x900")
        self.minsize(1300, 750)

        apply_dark_theme()

        self.server_running = False

        # NEW TIMER STATE FLAGS
        self.timer_running = False
        self.timer_popup_shown = False
        self.remaining_time = 0

        self.build_ui()
        self.after(REFRESH_MS, self.refresh_dashboard)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    
    def build_ui(self):
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(header, text="IoT Sensor Dashboard",
                     font=("Segoe UI", 28, "bold")).pack(side="left")

        control = ctk.CTkFrame(header)
        control.pack(side="right")

        ctk.CTkLabel(control, text="Test Time (s):").pack(side="left", padx=5)
        self.test_time_var = ctk.StringVar(value="60")
        self.test_time_entry = ctk.CTkEntry(control, textvariable=self.test_time_var, width=80)
        self.test_time_entry.pack(side="left", padx=5)

        ctk.CTkLabel(control, text="Batch Size:").pack(side="left", padx=5)
        self.batch_var = ctk.StringVar(value="3")
        self.batch_entry = ctk.CTkEntry(control, textvariable=self.batch_var, width=80)
        self.batch_entry.pack(side="left", padx=5)

        self.start_server_btn = ctk.CTkButton(
            control, text="Start Server (WSL)", width=180, command=self.start_server
        )
        self.start_server_btn.pack(side="left", padx=8)

        self.countdown_label = ctk.CTkLabel(control, text="", font=("Segoe UI", 18, "bold"))
        self.countdown_label.pack(side="left", padx=15)

        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=15, pady=15)

        left = ctk.CTkFrame(body, width=300)
        left.pack(side="left", fill="y", padx=(0, 15))

        sensor_card = ctk.CTkFrame(left)
        sensor_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(sensor_card, text="Sensors", font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, columnspan=3, padx=10, pady=10)

        row = 1
        for name, script in SENSORS.items():
            ctk.CTkLabel(sensor_card, text=name, font=("Segoe UI", 14)).grid(
                row=row, column=0, padx=10, pady=5, sticky="w")
            ctk.CTkButton(sensor_card, text="Start", width=70,
                          command=lambda n=name, s=script: self.start_sensor(n, s)).grid(row=row, column=1)
            entry = ctk.CTkEntry(sensor_card, width=60, justify="center")
            entry.insert(0, "0")
            entry.configure(state="disabled")
            entry.grid(row=row, column=2, padx=10)
            setattr(self, f"{name}_counter", entry)
            row += 1

        ctk.CTkButton(sensor_card, text="STOP ALL", fg_color="#D11A2A",
                      command=self.stop_all).grid(row=row, column=0, columnspan=3, pady=15)

        ctk.CTkButton(sensor_card, text="Clear Logs", fg_color="#8A2BE2",
                      command=self.clear_logs).grid(row=row+1, column=0, columnspan=3, pady=5)

        metrics_panel = ctk.CTkFrame(left)
        metrics_panel.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(metrics_panel, text="Server Metrics",
                     font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=10, pady=10)

        metric_keys = [
            "bytes_per_report", "packets_received", "duplicate_rate",
            "sequence_gap_count", "cpu_ms_per_report",
            "packet_loss", "avg_reporting_interval", "avg_delay"
        ]

        self.metric_labels = {}
        for m in metric_keys:
            rowf = ctk.CTkFrame(metrics_panel, fg_color="transparent")
            rowf.pack(fill="x", padx=10, pady=3)
            ctk.CTkLabel(rowf, text=f"{m}: ", width=180).pack(side="left")
            lbl = ctk.CTkLabel(rowf, text="N/A")
            lbl.pack(side="left")
            self.metric_labels[m] = lbl

        right = ctk.CTkFrame(body)
        right.pack(side="left", fill="both", expand=True)

        table_card = ctk.CTkFrame(right)
        table_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(table_card, text="Latest Readings",
                     font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=10, pady=10)

        cols = ["Sensor Type", "ID", "Seq", "Timestamp", "Arrival",
                "Msg Type", "Temperature", "Humidity", "Pressure",
                "Duplicate", "ReadingCount"]

        self.tree = ttk.Treeview(table_card, columns=cols, show="headings", height=8)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor="center", width=120)
        self.tree.pack(fill="x", padx=10, pady=10)

        term_card = ctk.CTkFrame(right)
        term_card.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(term_card, text="Server Terminal",
                     font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=10, pady=10)

        self.terminal = ctk.CTkTextbox(term_card)
        self.terminal.configure(state="disabled")
        self.terminal.pack(fill="both", expand=True, padx=10, pady=10)

    # ------------------------------- TIMER FIXES -------------------------------

    def start_test_timer(self):
        """Restart timer cleanly."""
        self.timer_running = False
        time.sleep(0.05)
        self.timer_running = True
        self.timer_popup_shown = False

        sec = int(self.test_time_var.get())
        threading.Thread(target=self.timer_thread, args=(sec,), daemon=True).start()

    def timer_thread(self, sec):
        start_time = time.time()

        while self.timer_running and (time.time() - start_time) < sec:
            time.sleep(0.2)

        if self.timer_running and not self.timer_popup_shown:
            self.timer_popup_shown = True
            self.stop_all()
            try:
                messagebox.showinfo("Timer Finished", "Test time is up.")
            except:
                pass

    def start_countdown(self, seconds):
        self.remaining_time = seconds
        self.update_countdown()

    def update_countdown(self):
        if not self.timer_running or self.remaining_time <= 0:
            self.countdown_label.configure(text="")
            return

        if self.remaining_time > 10:
            color = "green"
        elif self.remaining_time > 5:
            color = "orange"
        else:
            color = "red"

        self.countdown_label.configure(
            text=f"Time Left: {self.remaining_time}s",
            text_color=color
        )

        self.remaining_time -= 1
        self.after(1000, self.update_countdown)

    # ------------------------------- SERVER CONTROL -------------------------------

    def reset_test_environment(self):
        self.terminal.configure(state="normal")
        self.terminal.delete("1.0", "end")
        self.terminal.configure(state="disabled")

        try:
            shutil.rmtree(LOGS_DIR)
        except:
            pass
        os.makedirs(LOGS_DIR, exist_ok=True)

        for k in log_counters:
            log_counters[k] = 0

    def start_server(self):
        if self.server_running:
            messagebox.showinfo("Info", "Server already running.")
            return

        self.reset_test_environment()

        t = self.test_time_var.get().strip()
        if not t.isdigit() or int(t) <= 0:
            messagebox.showerror("Error", "Enter valid test time.")
            return

        p, logfile = spawn_process(["wsl", "python3", "Server.py"], "SERVER")
        self.server_running = True
        self.start_server_btn.configure(state="disabled")

        threading.Thread(target=self.capture_terminal, args=("SERVER", p, logfile), daemon=True).start()

        self.start_test_timer()
        self.start_countdown(int(self.test_time_var.get()))

    def capture_terminal(self, tag, p, logfile):
        try:
            for line in iter(p.stdout.readline, ''):
                if line == '':
                    break
                clean = ansi_escape.sub("", line)

                try:
                    logfile.write(clean)
                    logfile.flush()
                except:
                    pass

                try:
                    self.terminal.configure(state="normal")
                    self.terminal.insert("end", clean)
                    self.terminal.see("end")
                    self.terminal.configure(state="disabled")
                except:
                    pass
        except:
            pass
        finally:
            try:
                logfile.flush()
            except:
                pass

    # ------------------------------- SENSORS -------------------------------

    def start_sensor(self, name, script):
        try:
            batch = self.batch_var.get().strip()
            if not batch.isdigit() or int(batch) <= 0:
                messagebox.showerror("Error", "Batch size must be positive.")
                return

            tag = f"{name}_{int(time.time())}"

            p, logfile = spawn_process(
                ["wsl", "python3", script, "--batch", batch],
                tag
            )

            threading.Thread(target=self.capture_terminal, args=(tag, p, logfile), daemon=True).start()

            running_counts[name] += 1
            entry = getattr(self, f"{name}_counter")
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, str(running_counts[name]))
            entry.configure(state="disabled")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start {name}: {e}")

    # ------------------------------- STOP & CLEANUP -------------------------------

    def stop_all(self):
        """Stop server, sensors, and reset UI + timer."""
        self.timer_running = False
        self.remaining_time = 0
        self.countdown_label.configure(text="")

        for tag in list(processes.keys()):
            stop_process(tag)

        for name in running_counts:
            running_counts[name] = 0
            entry = getattr(self, f"{name}_counter")
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, "0")
            entry.configure(state="disabled")

        self.server_running = False
        self.start_server_btn.configure(state="normal")

    def clear_logs(self):
        try:
            shutil.rmtree(LOGS_DIR)
            os.makedirs(LOGS_DIR, exist_ok=True)
            for key in log_counters:
                log_counters[key] = 0
            messagebox.showinfo("Logs", "All logs cleared.")
        except:
            pass

    # ------------------------------- LIVE DASHBOARD -------------------------------

    def refresh_dashboard(self):
        self.update_table()
        self.update_metrics()
        self.after(REFRESH_MS, self.refresh_dashboard)

    def update_metrics(self):
        if not os.path.exists(METRICS_CSV):
            return
        try:
            df = pd.read_csv(METRICS_CSV)
            row = df.iloc[-1]
            for k, lbl in self.metric_labels.items():
                lbl.configure(text=str(row.get(k, "")))
        except:
            pass

    def update_table(self):
        for x in self.tree.get_children():
            self.tree.delete(x)

        if not os.path.exists(SENSORS_LOG):
            return

        try:
            df = pd.read_csv(SENSORS_LOG).tail(12)
            df = df.where(pd.notnull(df), "")
            cols = self.tree["columns"]
            for _, row in df.iterrows():
                self.tree.insert("", "end", values=[row.get(c, "") for c in cols])
        except:
            pass

    # ------------------------------- WINDOW CLOSE -------------------------------

    def on_close(self):
        self.stop_all()
        self.destroy()


if __name__ == "__main__":
    app = Dashboard()
    app.mainloop()
