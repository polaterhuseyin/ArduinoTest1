"""
Arduino GUI Test Interface — Arduino UNO R4 WiFi Edition
---------------------------------------------------------
Requirements:
    pip install pyserial matplotlib

Target board : Arduino UNO R4 WiFi (Renesas RA4M1, 14-bit ADC)
Connection   : USB-C  ->  COMx (Windows)  |  /dev/ttyACM0 (Linux/Mac)

Serial format from board:
    ADC0:8192,ADC1:4096,ADC2:16000        (14-bit: 0-16383)

Commands to board:
    GPIO:<pin>:<0|1>    e.g.  GPIO:3:1
    PWM:<pin>:<0-255>   e.g.  PWM:9:128
    DAC:<0-255>         e.g.  DAC:200     (true DAC on A0)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import queue
import time
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import matplotlib

matplotlib.use("TkAgg")

# ======================================================
#  Config
# ======================================================
BAUD_RATE    = 115200
MAX_SAMPLES  = 200
ADC_CHANNELS = ["A1", "A2", "A3"]   # A0 = DAC output, ADC reads from A1/A2/A3
GPIO_PINS    = [2, 3, 4, 5]
ADC_MAX      = 16383                 # UNO R4 WiFi: 14-bit (classic UNO = 1023)

COLORS = {
    "bg":      "#0f1117",
    "panel":   "#1a1d27",
    "border":  "#2a2d3a",
    "accent":  "#00d4ff",
    "accent2": "#ff6b35",
    "text":    "#e8eaf0",
    "dimtext": "#6b7080",
    "green":   "#00ff88",
    "red":     "#ff4466",
    "yellow":  "#ffd700",
}
PLOT_COLORS = ["#00d4ff", "#ff6b35", "#7fff00"]


# ──────────────────────────────────────────────
#  Serial Manager  (runs in background thread)
# ──────────────────────────────────────────────
class SerialManager:
    def __init__(self, data_queue):
        self.q       = data_queue
        self.ser     = None
        self.running = False
        self._thread = None

    @staticmethod
    def list_ports():
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port):
        try:
            self.ser = serial.Serial(port, BAUD_RATE, timeout=1)
            time.sleep(2)
            self.ser.reset_input_buffer()
            self.running = True
            self._thread = threading.Thread(target=self._reader, daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            self.q.put(("error", str(e)))
            return False

    def disconnect(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def send(self, cmd):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((cmd + "\n").encode())
            except Exception as e:
                self.q.put(("error", str(e)))

    def _reader(self):
        while self.running:
            try:
                if self.ser and self.ser.in_waiting:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        self.q.put(("data", line))
            except Exception as e:
                self.q.put(("error", str(e)))
                self.running = False
                break
            time.sleep(0.005)


# ──────────────────────────────────────────────
#  Main Application
# ──────────────────────────────────────────────
class ArduinoGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Arduino UNO R4 WiFi -- Test Interface")
        self.root.configure(bg=COLORS["bg"])
        self.root.geometry("1100x750")
        self.root.minsize(900, 650)

        self.data_queue     = queue.Queue()
        self.serial_mgr     = SerialManager(self.data_queue)
        self.connected      = False
        self.adc_history    = {ch: deque([0] * MAX_SAMPLES, maxlen=MAX_SAMPLES)
                               for ch in ADC_CHANNELS}
        self.adc_vars       = {ch: tk.StringVar(value="0") for ch in ADC_CHANNELS}
        self.rx_count       = 0
        self.running        = True
        self._poll_after_id = None

        self._build_ui()
        self._start_plot()
        self._poll_queue()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # =============================================
    #  UI Construction
    # =============================================
    def _build_ui(self):
        title_bar = tk.Frame(self.root, bg=COLORS["bg"])
        title_bar.pack(fill="x", padx=16, pady=(12, 0))

        tk.Label(title_bar, text="ARDUINO UNO R4 WiFi -- TEST INTERFACE",
                 font=("Courier New", 13, "bold"),
                 bg=COLORS["bg"], fg=COLORS["accent"]).pack(side="left")

        self.status_dot = tk.Label(title_bar, text="●", font=("Courier New", 16),
                                   bg=COLORS["bg"], fg=COLORS["red"])
        self.status_dot.pack(side="right", padx=(0, 4))
        self.status_label = tk.Label(title_bar, text="DISCONNECTED",
                                     font=("Courier New", 10, "bold"),
                                     bg=COLORS["bg"], fg=COLORS["red"])
        self.status_label.pack(side="right")

        main = tk.Frame(self.root, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=16, pady=10)
        main.columnconfigure(0, weight=0, minsize=240)
        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=0, minsize=240)
        main.rowconfigure(0, weight=1)

        left_inner   = self._make_panel(main, "CONNECTION & CONTROL")
        left_inner.master.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        center_inner = self._make_panel(main, "ADC WAVEFORM")
        center_inner.master.grid(row=0, column=1, sticky="nsew", padx=(0, 8))

        right_inner  = self._make_panel(main, "GPIO OUTPUT")
        right_inner.master.grid(row=0, column=2, sticky="nsew")

        self._build_connection(left_inner)
        self._build_plot(center_inner)
        self._build_gpio(right_inner)

        log_inner = self._make_panel(self.root, "SERIAL LOG")
        log_inner.master.pack(fill="x", padx=16, pady=(0, 12))

        self.log_text = tk.Text(
            log_inner, height=6, bg=COLORS["bg"], fg=COLORS["dimtext"],
            font=("Courier New", 9), bd=0, relief="flat", state="disabled",
            insertbackground=COLORS["accent"])
        scroll = ttk.Scrollbar(log_inner, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log_text.pack(fill="x", expand=True)

        self.log_text.tag_config("rx",    foreground=COLORS["accent"])
        self.log_text.tag_config("tx",    foreground=COLORS["accent2"])
        self.log_text.tag_config("info",  foreground=COLORS["green"])
        self.log_text.tag_config("error", foreground=COLORS["red"])

    def _make_panel(self, parent, title):
        outer = tk.Frame(parent, bg=COLORS["border"])
        header = tk.Frame(outer, bg=COLORS["panel"])
        header.pack(fill="x")
        tk.Label(header, text=title, font=("Courier New", 8, "bold"),
                 bg=COLORS["panel"], fg=COLORS["dimtext"],
                 padx=10, pady=6).pack(side="left")
        inner = tk.Frame(outer, bg=COLORS["panel"], padx=12, pady=10)
        inner.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        return inner  # inner.master == outer

    def _build_connection(self, parent):
        def lbl(text):
            tk.Label(parent, text=text, bg=COLORS["panel"],
                     fg=COLORS["dimtext"], font=("Courier New", 8)).pack(anchor="w")

        lbl("PORT")
        port_row = tk.Frame(parent, bg=COLORS["panel"])
        port_row.pack(fill="x", pady=(2, 8))

        self.port_var   = tk.StringVar()
        self.port_combo = ttk.Combobox(port_row, textvariable=self.port_var,
                                       width=14, state="readonly")
        self.port_combo.pack(side="left")
        self._style_combobox()
        self._btn(port_row, "R", self._refresh_ports, small=True).pack(
            side="left", padx=(6, 0))

        self.connect_btn = self._btn(parent, "CONNECT", self._toggle_connection)
        self.connect_btn.pack(fill="x", pady=(0, 16))

        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x", pady=(0, 12))
        lbl("ADC READINGS  (A1, A2, A3)  —  A0 = DAC")

        for i, ch in enumerate(ADC_CHANNELS):
            row = tk.Frame(parent, bg=COLORS["panel"])
            row.pack(fill="x", pady=3)
            tk.Label(row, text=ch, font=("Courier New", 9, "bold"),
                     bg=COLORS["panel"], fg=PLOT_COLORS[i], width=5).pack(side="left")
            tk.Label(row, textvariable=self.adc_vars[ch],
                     font=("Courier New", 14, "bold"),
                     bg=COLORS["panel"], fg=COLORS["text"], width=6).pack(side="left")
            bar = ttk.Progressbar(row, length=75, maximum=ADC_MAX, mode="determinate")
            bar.pack(side="left", padx=(6, 0))
            self.adc_vars[ch].trace_add(
                "write",
                lambda *_, b=bar, v=self.adc_vars[ch]: b.configure(value=_safe_int(v.get())))

        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x", pady=(16, 8))
        lbl("RAW COMMAND")
        cmd_row = tk.Frame(parent, bg=COLORS["panel"])
        cmd_row.pack(fill="x")
        self.cmd_var = tk.StringVar()
        e = tk.Entry(cmd_row, textvariable=self.cmd_var,
                     bg=COLORS["bg"], fg=COLORS["text"],
                     font=("Courier New", 10), bd=0, relief="flat",
                     insertbackground=COLORS["accent"])
        e.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))
        e.bind("<Return>", lambda _: self._send_raw())
        self._btn(cmd_row, "SEND", self._send_raw, small=True).pack(side="left")

        self._refresh_ports()

    def _build_plot(self, parent):
        self.fig, self.ax = plt.subplots(figsize=(5, 3.2))
        self.fig.patch.set_facecolor(COLORS["bg"])
        self.ax.set_facecolor(COLORS["panel"])
        self.ax.set_ylim(0, ADC_MAX)
        self.ax.set_xlim(0, MAX_SAMPLES)
        self.ax.tick_params(colors=COLORS["dimtext"], labelsize=7)
        for spine in self.ax.spines.values():
            spine.set_edgecolor(COLORS["border"])
        self.ax.set_ylabel("ADC (0-16383, 14-bit)", color=COLORS["dimtext"], fontsize=8)
        self.ax.grid(True, color=COLORS["border"], linewidth=0.5, alpha=0.6)

        self.plot_lines = {}
        for i, ch in enumerate(ADC_CHANNELS):
            line, = self.ax.plot(range(MAX_SAMPLES), list(self.adc_history[ch]),
                                 color=PLOT_COLORS[i], linewidth=1.5, label=ch)
            self.plot_lines[ch] = line

        self.ax.legend(loc="upper right", facecolor=COLORS["panel"],
                       labelcolor=COLORS["text"], fontsize=8,
                       edgecolor=COLORS["border"])

        canvas = FigureCanvasTkAgg(self.fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas = canvas

    def _build_gpio(self, parent):
        tk.Label(parent, text="DIGITAL OUTPUT PINS",
                 font=("Courier New", 8, "bold"),
                 bg=COLORS["panel"], fg=COLORS["dimtext"]).pack(anchor="w", pady=(0, 8))

        for pin in GPIO_PINS:
            frame = tk.Frame(parent, bg=COLORS["bg"], padx=10, pady=8)
            frame.pack(fill="x", pady=3)
            tk.Label(frame, text=f"PIN {pin}", font=("Courier New", 10, "bold"),
                     bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w")
            indicator = tk.Label(frame, text="LOW", font=("Courier New", 9, "bold"),
                                  bg=COLORS["bg"], fg=COLORS["red"])
            indicator.pack(anchor="w")
            btn_row = tk.Frame(frame, bg=COLORS["bg"])
            btn_row.pack(fill="x", pady=(4, 0))
            self._btn(btn_row, "HIGH",
                      lambda p=pin, ind=indicator: self._set_gpio(p, 1, ind),
                      color=COLORS["green"], small=True).pack(side="left", padx=(0, 4))
            self._btn(btn_row, "LOW",
                      lambda p=pin, ind=indicator: self._set_gpio(p, 0, ind),
                      color=COLORS["red"], small=True).pack(side="left")

        # PWM
        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x", pady=(14, 8))
        tk.Label(parent, text="PWM OUTPUT (PIN 9)",
                 font=("Courier New", 8, "bold"),
                 bg=COLORS["panel"], fg=COLORS["dimtext"]).pack(anchor="w")
        self.pwm_var = tk.IntVar(value=0)
        pwm_row = tk.Frame(parent, bg=COLORS["panel"])
        pwm_row.pack(fill="x", pady=(6, 0))
        self.pwm_label = tk.Label(pwm_row, text="  0", font=("Courier New", 12, "bold"),
                                   bg=COLORS["panel"], fg=COLORS["yellow"], width=4)
        self.pwm_label.pack(side="left")
        ttk.Scale(pwm_row, from_=0, to=255, variable=self.pwm_var, orient="horizontal",
                  command=self._on_pwm_change).pack(
            side="left", fill="x", expand=True, padx=(6, 0))
        self._btn(parent, "SEND PWM", self._send_pwm).pack(fill="x", pady=(8, 0))

        # DAC
        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x", pady=(14, 8))
        tk.Label(parent, text="DAC OUTPUT (A0)  -- UNO R4 WiFi",
                 font=("Courier New", 8, "bold"),
                 bg=COLORS["panel"], fg=COLORS["accent"]).pack(anchor="w")
        self.dac_var = tk.IntVar(value=0)
        dac_row = tk.Frame(parent, bg=COLORS["panel"])
        dac_row.pack(fill="x", pady=(6, 0))
        self.dac_label = tk.Label(dac_row, text="  0", font=("Courier New", 12, "bold"),
                                   bg=COLORS["panel"], fg=COLORS["accent"], width=4)
        self.dac_label.pack(side="left")
        ttk.Scale(dac_row, from_=0, to=255, variable=self.dac_var, orient="horizontal",
                  command=self._on_dac_change).pack(
            side="left", fill="x", expand=True, padx=(6, 0))
        self._btn(parent, "SEND DAC", self._send_dac).pack(fill="x", pady=(8, 0))

    # =============================================
    #  Widget helpers
    # =============================================
    def _btn(self, parent, text, cmd, color=None, small=False):
        c = color or COLORS["accent"]
        b = tk.Button(parent, text=text, command=cmd,
                      bg=COLORS["border"], fg=c,
                      font=("Courier New", 8 if small else 9, "bold"),
                      activebackground=c, activeforeground=COLORS["bg"],
                      bd=0, relief="flat", cursor="hand2",
                      padx=6 if small else 10, pady=3 if small else 6)
        b.bind("<Enter>", lambda e: b.config(bg=c, fg=COLORS["bg"]))
        b.bind("<Leave>", lambda e: b.config(bg=COLORS["border"], fg=c))
        return b

    def _style_combobox(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TCombobox",
                    fieldbackground=COLORS["bg"], background=COLORS["border"],
                    foreground=COLORS["text"], selectbackground=COLORS["accent"],
                    selectforeground=COLORS["bg"], font=("Courier New", 9))

    # =============================================
    #  Actions
    # =============================================
    def _refresh_ports(self):
        ports = SerialManager.list_ports()
        self.port_combo["values"] = ports
        self.port_var.set(ports[0] if ports else "")

    def _toggle_connection(self):
        if not self.connected:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("No Port", "Select a serial port first.")
                return
            if self.serial_mgr.connect(port):
                self.connected = True
                self.connect_btn.config(text="DISCONNECT")
                self.status_dot.config(fg=COLORS["green"])
                self.status_label.config(text="CONNECTED", fg=COLORS["green"])
                self._log(f"Connected to {port} @ {BAUD_RATE} baud", "info")
            else:
                try:
                    _, err_msg = self.data_queue.get_nowait()
                except queue.Empty:
                    err_msg = "Unknown error"
                self._log(f"ERR: {err_msg}", "error")
                messagebox.showerror(
                    "Connection Failed",
                    f"{err_msg}\n\nTips:\n"
                    "  - Close Arduino IDE Serial Monitor\n"
                    "  - Unplug and replug the USB-C cable\n"
                    "  - Make sure no other app is using the port")
        else:
            self.serial_mgr.disconnect()
            self.connected = False
            self.connect_btn.config(text="CONNECT")
            self.status_dot.config(fg=COLORS["red"])
            self.status_label.config(text="DISCONNECTED", fg=COLORS["red"])
            self._log("Disconnected.", "info")

    def _set_gpio(self, pin, state, indicator):
        cmd = f"GPIO:{pin}:{state}"
        self.serial_mgr.send(cmd)
        indicator.config(text="HIGH" if state else "LOW",
                         fg=COLORS["green"] if state else COLORS["red"])
        self._log(f"TX -> {cmd}", "tx")

    def _on_pwm_change(self, val):
        self.pwm_label.config(text=f"{int(float(val)):3d}")

    def _send_pwm(self):
        cmd = f"PWM:9:{self.pwm_var.get()}"
        self.serial_mgr.send(cmd)
        self._log(f"TX -> {cmd}", "tx")

    def _on_dac_change(self, val):
        self.dac_label.config(text=f"{int(float(val)):3d}")

    def _send_dac(self):
        cmd = f"DAC:{self.dac_var.get()}"
        self.serial_mgr.send(cmd)
        self._log(f"TX -> {cmd}", "tx")

    def _send_raw(self):
        cmd = self.cmd_var.get().strip()
        if cmd:
            self.serial_mgr.send(cmd)
            self._log(f"TX -> {cmd}", "tx")
            self.cmd_var.set("")

    def _on_closing(self):
        self.running = False
        if self._poll_after_id is not None:
            self.root.after_cancel(self._poll_after_id)
        self.serial_mgr.disconnect()
        self.root.destroy()

    # =============================================
    #  Data pipeline
    # =============================================
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.data_queue.get_nowait()
                if kind == "data":
                    self._parse_data(payload)
                    self._log(f"RX <- {payload}", "rx")
                elif kind == "error":
                    self._log(f"ERR: {payload}", "error")
                    if self.connected:
                        self.connected = False
                        self.connect_btn.config(text="CONNECT")
                        self.status_dot.config(fg=COLORS["red"])
                        self.status_label.config(text="ERROR", fg=COLORS["red"])
        except queue.Empty:
            pass
        except tk.TclError:
            return

        if self.running:
            try:
                self._poll_after_id = self.root.after(50, self._poll_queue)
            except tk.TclError:
                pass

    def _parse_data(self, line):
        """Parse:  ADC0:8192,ADC1:4096,ADC2:16000
        Arduino sends ADC0/ADC1/ADC2 — mapped to display labels A1/A2/A3"""
        key_map = {"ADC0": "A1", "ADC1": "A2", "ADC2": "A3"}
        self.rx_count += 1
        for token in line.split(","):
            key, _, val = token.strip().partition(":")
            key = key_map.get(key.strip().upper(), key.strip().upper())
            if key in self.adc_history:
                try:
                    iv = int(val.strip())
                    self.adc_history[key].append(iv)
                    self.adc_vars[key].set(str(iv))
                except ValueError:
                    pass

    # =============================================
    #  Plot animation
    # =============================================
    def _start_plot(self):
        def update(_frame):
            for ch, line in self.plot_lines.items():
                line.set_ydata(list(self.adc_history[ch]))
            return list(self.plot_lines.values())

        self._anim = FuncAnimation(self.fig, update, interval=100,
                                   blit=True, cache_frame_data=False)

    # =============================================
    #  Log
    # =============================================
    def _log(self, msg, tag="info"):
        ts = time.strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{ts}] {msg}\n", tag)
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 200:
            self.log_text.delete("1.0", f"{lines - 200}.0")
        self.log_text.see("end")
        self.log_text.config(state="disabled")


def _safe_int(s):
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


if __name__ == "__main__":
    root = tk.Tk()
    app = ArduinoGUI(root)
    try:
        root.mainloop()
    except tk.TclError:
        pass