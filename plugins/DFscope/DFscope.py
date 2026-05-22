import tkinter as tk
import socket
import json
import math
import threading

class StudentConsole:
    def __init__(self, root):
        self.root = root
        self.root.title("DF scope (Trainee Console)")
        self.root.geometry("700x800")
        self.root.configure(bg="#0f172a") # Dark Slate / Glass Cockpit Background
        self.root.resizable(False, False)

        # --- NETWORK CONFIG ---
        self.target_ip = "127.0.0.1" # Ausbilder IP
        self.target_port = 8887
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Timeout für Receive, damit das UI beim Warten auf die Antenne nicht einfriert
        self.sock.settimeout(2.0) 

        # --- DATA STATE ---
        self.antenna_pattern = {} # Hier landen die 360 Werte (Winkel -> dB)
        self.filename = "NO DATA"
        self.current_heading = 0.0

        self.setup_ui()
        self.draw_compass_rose()

    def setup_ui(self):
        # Top Bar (Status & Sync)
        top_frame = tk.Frame(self.root, bg="#1e293b", pady=10)
        top_frame.pack(fill="x")

        self.btn_sync = tk.Button(top_frame, text="SYNC: LOAD DATA", bg="#0ea5e9", fg="white", 
                                  font=("Courier", 12, "bold"), command=self.request_config, relief="flat", padx=10)
        self.btn_sync.pack(side="left", padx=20)

        self.lbl_status = tk.Label(top_frame, text="ANTENNA: NO DATA", bg="#1e293b", fg="#94a3b8", 
                                   font=("Courier", 14, "bold"))
        self.lbl_status.pack(side="right", padx=20)

        # Canvas for Radar/Compass Display
        self.canvas_size = 600
        self.cx = self.canvas_size / 2
        self.cy = self.canvas_size / 2
        self.radius = 250

        self.canvas = tk.Canvas(self.root, width=self.canvas_size, height=self.canvas_size, 
                                bg="#0f172a", highlightthickness=0)
        self.canvas.pack(pady=20)

        # Bottom Controls
        bot_frame = tk.Frame(self.root, bg="#0f172a")
        bot_frame.pack(fill="x", padx=40, pady=10)

        tk.Label(bot_frame, text="HEADING SELECT [DEG]:", bg="#0f172a", fg="#0ea5e9", 
                 font=("Courier", 12, "bold")).pack(anchor="w")

        self.slider_hdg = tk.Scale(bot_frame, from_=0, to=359, orient="horizontal", 
                                   bg="#0f172a", fg="#f8fafc", troughcolor="#334155", 
                                   highlightthickness=0, font=("Courier", 14), 
                                   command=self.on_heading_change, showvalue=1, length=620)
        self.slider_hdg.pack()

    def request_config(self):
        """Sendet GET_CONFIG an Ausbilder und wartet auf JSON in einem eigenen Thread."""
        self.btn_sync.config(text="WAITING...", bg="#f59e0b") # Orange loading
        threading.Thread(target=self._network_request_thread, daemon=True).start()

    def _network_request_thread(self):
        try:
            self.sock.sendto("GET_CONFIG".encode('utf-8'), (self.target_ip, self.target_port))
            data, _ = self.sock.recvfrom(65536) # Großer Buffer für den JSON String
            
            response = json.loads(data.decode('utf-8'))
            
            if response.get("status") == "OK":
                self.filename = response.get("filename", "UNKNOWN")
                
                # JSON Keys sind Strings (z.B. "14"). Wir machen Integers draus.
                raw_pattern = response.get("pattern", {})
                self.antenna_pattern = {int(k): float(v) for k, v in raw_pattern.items()}

                # --- AUTOMATISCHES NULLSTELLEN-SCANNING ---
                # Wir suchen den Winkel mit der geringsten Signalstärke (dB)
                self.null_centers = [] # Liste aller gefundenen Zentren
                if self.antenna_pattern:
                    min_val = min(self.antenna_pattern.values())
                    threshold = min_val + 3.0 # Alles, was innerhalb von 3dB des Minimums liegt
                    
                    # 1. Finde alle Punkte unter Schwelle
                    low_points = [a for a, v in self.antenna_pattern.items() if v <= threshold]
                    
                    # 2. Gruppiere zusammenhängende Winkel (berücksichtigt Wrap-around 359->0)
                    groups = []
                    if low_points:
                        current_group = [low_points[0]]
                        for i in range(1, len(low_points)):
                            if low_points[i] == low_points[i-1] + 1 or (low_points[i] == 0 and low_points[i-1] == 359):
                                current_group.append(low_points[i])
                            else:
                                groups.append(current_group)
                                current_group = [low_points[i]]
                        groups.append(current_group)
                    
                    # 3. Berechne Zentrum pro Gruppe
                    for g in groups:
                        # Geometrischer Mittelwert der Winkel (mit Wrap-around Handling)
                        # Um den Mittelwert korrekt zu berechnen, nehmen wir Sin/Cos
                        sum_x = sum([math.sin(math.radians(a)) for a in g])
                        sum_y = sum([math.cos(math.radians(a)) for a in g])
                        center_angle = math.degrees(math.atan2(sum_x, sum_y)) % 360
                        self.null_centers.append(center_angle)
                
                # UI Update muss im Main-Thread passieren
                self.root.after(0, self.on_config_received_success)
            else:
                self.root.after(0, self.on_config_received_error)
                
        except socket.timeout:
            print("Timeout: Ausbilderapp antwortet nicht.")
            self.root.after(0, self.on_config_received_error)
        except Exception as e:
            print(f"Fehler beim Sync: {e}")
            self.root.after(0, self.on_config_received_error)

    def on_config_received_success(self):
        self.btn_sync.config(text="SYNC: READY", bg="#10b981") # Green success
        self.lbl_status.config(text=f"ANTENNA: {self.filename}", fg="#38bdf8")
        self.update_display()

    def on_config_received_error(self):
        self.btn_sync.config(text="SYNC FAILED", bg="#ef4444") # Red error
        self.lbl_status.config(text="ANTENNA: OFFLINE", fg="#ef4444")
        self.root.after(2000, lambda: self.btn_sync.config(text="SYNC: LOAD DATA", bg="#0ea5e9"))

    def on_heading_change(self, val):
        """Slider Callback. Sendet UDP Paket und rotiert das lokale Diagramm."""
        self.current_heading = float(val)
        
        # 1. Lokales Zeichnen
        self.update_display()
        
        # 2. UDP Paket an Operator (Feuert wild beim Sliden, was völlig okay ist!)
        msg = f"HDG:{self.current_heading}"
        try:
            self.sock.sendto(msg.encode('utf-8'), (self.target_ip, self.target_port))
        except:
            pass

    def draw_compass_rose(self):
        """Zeichnet die statischen Ringe und Grad-Striche (Glass Cockpit Style)."""
        self.canvas.delete("static")
        
        # Äußerer und Innerer Ring
        self.canvas.create_oval(self.cx - self.radius, self.cy - self.radius, 
                                self.cx + self.radius, self.cy + self.radius, 
                                outline="#334155", width=2, tags="static")
        self.canvas.create_oval(self.cx - 10, self.cy - 10, 
                                self.cx + 10, self.cy + 10, 
                                outline="#334155", width=2, tags="static")

        # Ticks und Labels
        for angle in range(0, 360, 10):
            rad = math.radians(angle)
            # Y wird abgezogen, da im Tkinter Canvas Y nach unten wächst
            cos_a = math.sin(rad) # X 
            sin_a = math.cos(rad) # Y
            
            inner_r = self.radius - (15 if angle % 30 == 0 else 5)
            x1, y1 = self.cx + inner_r * cos_a, self.cy - inner_r * sin_a
            x2, y2 = self.cx + self.radius * cos_a, self.cy - self.radius * sin_a
            
            self.canvas.create_line(x1, y1, x2, y2, fill="#475569", width=2, tags="static")

            # Beschriftung alle 30 Grad
            if angle % 30 == 0:
                tx = self.cx + (self.radius + 20) * cos_a
                ty = self.cy - (self.radius + 20) * sin_a
                label = ["N", "030", "060", "E", "120", "150", "S", "210", "240", "W", "300", "330"][int(angle/30)]
                color = "#38bdf8" if label in ["N", "E", "S", "W"] else "#64748b"
                self.canvas.create_text(tx, ty, text=label, fill=color, font=("Courier", 10, "bold"), tags="static")

    def update_display(self):
        """Löscht dynamische Elemente und zeichnet Polygon und Nadel neu."""
        self.canvas.delete("dynamic")

        # 1. Antennen-Polygon zeichnen (wenn Daten da sind)
        if self.antenna_pattern:
            points = []
            for angle_deg in range(0, 360, 2):
                # Der Trick: Wir addieren unseren eingestellten Heading-Wert zum Original-Winkel!
                rotated_angle = (angle_deg + self.current_heading) % 360
                rad = math.radians(rotated_angle)
                
                # Dämpfungswert aus dem Dictionary holen (-30 dB als Floor)
                att = self.antenna_pattern.get(angle_deg, 0.0)
                clamped_att = max(-30.0, att)
                factor = (clamped_att + 30.0) / 30.0 # 0dB = Rand (1.0), -30dB = Mitte (0.0)
                
                r = max(5.0, self.radius * factor) # Minimum 5px Radius, damit Nullstellen nicht kollabieren
                
                x = self.cx + r * math.sin(rad)
                y = self.cy - r * math.cos(rad)
                points.append((x, y))


            self.canvas.create_polygon(points, fill="#022c22", outline="#2dd4bf", width=2, smooth=True, tags="dynamic")

        # 2. Die HDG-Nadel (Lubber Line / Current Heading Indicator)
        rad_hdg = math.radians(self.current_heading)
        nx = self.cx + (self.radius + 5) * math.sin(rad_hdg)
        ny = self.cy - (self.radius + 5) * math.cos(rad_hdg)
        
        self.canvas.create_line(self.cx, self.cy, nx, ny, fill="#f97316", width=3, arrow=tk.LAST, tags="dynamic")

        # --- PEIL-FADENKREUZ ---
        if hasattr(self, 'null_centers'):
            for center in self.null_centers:
                # Winkel rotieren
                bearing_angle = (center + self.current_heading) % 360
                rad = math.radians(bearing_angle)
                
                # Linie zeichnen
                lx = self.cx + self.radius * math.sin(rad)
                ly = self.cy - self.radius * math.cos(rad)
                
                # Linie für die Nullstelle
                self.canvas.create_line(self.cx, self.cy, lx, ly, 
                                        fill="#2dd4bf", width=2, dash=(4, 4), tags="dynamic")
                
                # Kleiner Kreis am Ende der Linie, damit man sie besser sieht
                self.canvas.create_oval(lx-4, ly-4, lx+4, ly+4, fill="#2dd4bf", outline="#0f172a", tags="dynamic")

                # --- GRADZAHL-LABEL (Alpha-Numeric Readout) ---
                # Wir platzieren den Text leicht außerhalb des Kreises (Radius + 30)
                text_r = self.radius + 30 
                tx = self.cx + text_r * math.sin(rad)
                ty = self.cy - text_r * math.cos(rad)
                
                # Text als kleiner "Tag" am Ende der Linie
                self.canvas.create_text(tx, ty, 
                                        text=f"{int(bearing_angle % 360)}°", 
                                        fill="#2dd4bf", 
                                        font=("Courier", 10, "bold"), 
                                        tags="dynamic")

if __name__ == "__main__":
    root = tk.Tk()
    app = StudentConsole(root)
    root.mainloop()