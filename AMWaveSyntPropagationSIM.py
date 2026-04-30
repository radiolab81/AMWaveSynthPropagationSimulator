import tkinter as tk
from tkinter import ttk, simpledialog
import os, glob, csv, sqlite3, re, time, math, socket, threading, random
from datetime import datetime
from tkintermapview import TkinterMapView
from geopy.geocoders import ArcGIS

# --- LOKALISIERUNGSDATEN (Inkl. Gewitter-Erweiterungen) ---
LANGUAGES = {
    "DE": {
        "title": "Ausbreitungssimulator für HF-Modulator Steuerung (UDP 8888)",
        "date": "Datum (TT.MM):", "time": "Uhrzeit:", "sens": "Schwelle (dBµV/m):",
        "sun": "Sonne (RX):", "pot_head": "Potential (Nacht)", "cur_head": "AKTUELLER Empfang",
        "list_hdr": "dB | Hz | Name | Modus | ms", "fast": "⏩ Fast-Forward",
        "fast_stop": "■ Stop Fast", "real": "▶ Echtzeit Start", "real_stop": "■ Echtzeit Stop",
        "rec_marker": "🏠 Empfänger", "rec_menu": "Empfänger hierher",
        "mod_menu": "Modulator", "mod_off": "Alle AUS (0.0)", "mod_max": "Alle MAX (1.0)", "mod_custom": "Gain Wert setzen...",
        "sf_title": "⛈ Gewitter-Zelle", "sf_place": "⛈ Gewitter setzen", "sf_click": "👉 Klick in Karte...",
        "sf_on": "QRN Start", "sf_off": "QRN Stop", "sf_dir": "Richtung (°):", "sf_spd": "Speed (km/h):",
        "sf_amp": "Basis-Power:", "sf_rate": "Häufigkeit:"
    },
    "EN": {
        "title": "HF Modulator Propagation Simulator Control (UDP 8888)",
        "date": "Date (DD.MM):", "time": "Time:", "sens": "Threshold (dBµV/m):",
        "sun": "Sun (RX):", "pot_head": "Potential (Night)", "cur_head": "CURRENT Reception",
        "list_hdr": "dB | Hz | Name | Mode | ms", "fast": "⏩ Fast-Forward",
        "fast_stop": "■ Stop Fast", "real": "▶ Start Realtime", "real_stop": "■ Stop Realtime",
        "rec_marker": "🏠 Receiver", "rec_menu": "Receiver here",
        "mod_menu": "Modulator", "mod_off": "All OFF (0.0)", "mod_max": "All MAX (1.0)", "mod_custom": "Set Gain Value...",
        "sf_title": "⛈ Storm Cell", "sf_place": "⛈ Place Storm", "sf_click": "👉 Click Map...",
        "sf_on": "QRN Start", "sf_off": "QRN Stop", "sf_dir": "Dir (°):", "sf_spd": "Speed (km/h):",
        "sf_amp": "Base Power:", "sf_rate": "Frequency:"
    },
    "FR": {
        "title": "Simulateur de propagation HF (UDP 8888)",
        "date": "Date (JJ.MM):", "time": "Heure:", "sens": "Seuil (dBµV/m):",
        "sun": "Soleil (RX):", "pot_head": "Potentiel (Nuit)", "cur_head": "Réception ACTUELLE",
        "list_hdr": "dB | Hz | Nom | Mode | ms", "fast": "⏩ Avance rapide",
        "fast_stop": "■ Arrêter", "real": "▶ Temps réel", "real_stop": "■ Arrêter",
        "rec_marker": "🏠 Récepteur", "rec_menu": "Récepteur ici",
        "mod_menu": "Modulateur", "mod_off": "Tous OFF (0.0)", "mod_max": "Tous MAX (1.0)", "mod_custom": "Régler le Gain...",
        "sf_title": "⛈ Orage", "sf_place": "⛈ Placer l'orage", "sf_click": "👉 Cliquer sur carte",
        "sf_on": "Démarrer QRN", "sf_off": "Arrêter QRN", "sf_dir": "Dir (°):", "sf_spd": "Vitesse (km/h):",
        "sf_amp": "Puissance:", "sf_rate": "Fréquence:"
    },
    "IT": {
        "title": "Simulatore di propagazione HF (UDP 8888)",
        "date": "Data (GG.MM):", "time": "Ora:", "sens": "Soglia (dBµV/m):",
        "sun": "Sole (RX):", "pot_head": "Potenziale (Notte)", "cur_head": "Ricezione ATTUALE",
        "list_hdr": "dB | Hz | Nome | Modo | ms", "fast": "⏩ Avanti veloce",
        "fast_stop": "■ Ferma", "real": "▶ Tempo reale", "real_stop": "■ Ferma",
        "rec_marker": "🏠 Ricevitore", "rec_menu": "Ricevitore qui",
        "mod_menu": "Modulatore", "mod_off": "Tutto OFF (0.0)", "mod_max": "Tutto MAX (1.0)", "mod_custom": "Imposta Gain...",
        "sf_title": "⛈ Temporale", "sf_place": "⛈ Piazza temporale", "sf_click": "👉 Clicca sulla mappa",
        "sf_on": "Avvia QRN", "sf_off": "Ferma QRN", "sf_dir": "Dir (°):", "sf_spd": "Velocità:",
        "sf_amp": "Potenza:", "sf_rate": "Frequenza:"
    },
    "JP": {
        "title": "HFモジュレーター伝搬シミュレーター (UDP 8888)",
        "date": "日付 (日.月):", "time": "時刻:", "sens": "しきい値 (dBµV/m):",
        "sun": "太陽 (RX):", "pot_head": "ポテンシャル (夜間)", "cur_head": "現在の受信状態",
        "list_hdr": "dB | Hz | 放送局名 | モード | ms", "fast": "⏩ 早送り",
        "fast_stop": "■ 停止", "real": "▶ リアルタイム開始", "real_stop": "■ 停止",
        "rec_marker": "🏠 受信機", "rec_menu": "受信機をここに設置",
        "mod_menu": "変調器", "mod_off": "全オフ (0.0)", "mod_max": "全最大 (1.0)", "mod_custom": "ゲイン値を設定...",
        "sf_title": "⛈ 雷雨セル", "sf_place": "⛈ 雷雨を配置", "sf_click": "👉 地図をクリック...",
        "sf_on": "QRN 開始", "sf_off": "QRN 停止", "sf_dir": "方向 (°):", "sf_spd": "速度 (km/h):",
        "sf_amp": "基本電力:", "sf_rate": "頻度:"
    }
}


SFERICS_LIFETIME = 120.0  # Die Zelle lebt 2 Stunden Simulationszeit

class RadioMapApp:
    def __init__(self, root):
        self.root = root
        self.cur_lang = "DE"
        self.root.title(LANGUAGES[self.cur_lang]["title"])
        self.root.geometry("1200x850")

        self.last_pc_minute = -1

        # UDP Setup für externen Modulator (Gain & Sferics Split)
        self.udp_ip = "127.0.0.1"
        self.udp_port_gain = 8888
        self.udp_port_sferics = 8889
        self.sock_gain = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_sferics = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.is_realtime_running = False
        self.is_fast_running = False

        # Status & Storm Variablen
        self.storm_active = False
        self.storm_placement_mode = False
        self.storm_pos = [50.0, 10.0]
        self.storm_life_minutes = SFERICS_LIFETIME
        self.storm_polygon = None
        self.storm_icons = []

        # 1. Datenbank & Geocoder Initialisierung
        self.db_path = "geocache_radio.db"
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('CREATE TABLE IF NOT EXISTS locations (key TEXT PRIMARY KEY, lat REAL, lon REAL)')
        self.conn.commit()
        self.geolocator = ArcGIS(timeout=10)

        # 2. Karten-Widget Setup
        self.map_widget = TkinterMapView(self.root, width=1200, height=600)
        self.map_widget.pack(fill="both", expand=True)
        self.receiver_coords = (52.52, 13.40) 
        self.receiver_marker = None
        self.map_widget.set_position(52.52, 13.40)
        self.map_widget.set_zoom(5)
        self.map_widget.add_left_click_map_command(self.place_storm_callback)
        
        self.setup_menu()

        self.open_simulation_window()
        self.load_all_from_folder("tx_sites")
        self.change_language("DE") # Initialisierung der Labels

    def setup_menu(self):
        self.menubar = tk.Menu(self.root)
        
        # 1. Sprachen-Menü
        lang_menu = tk.Menu(self.menubar, tearoff=0)
        for c, n in [("DE","Deutsch"),("EN","English"),("FR","Français"),("IT","Italiano"),("JP","日本語")]:
            lang_menu.add_command(label=n, command=lambda code=c: self.change_language(code))
        self.menubar.add_cascade(label="Language / Sprache", menu=lang_menu)

        # 2. Modulator-Menü
        self.mod_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(menu=self.mod_menu)
        self.root.config(menu=self.menubar)


    def change_language(self, code):
        self.cur_lang = code
        T = LANGUAGES[code]
        
        # UI-Updates im Simulationsfenster
        self.root.title(T["title"])
        self.sim_win.title(T["title"])
        self.lbl_date_desc.config(text=T["date"])
        self.lbl_time_desc.config(text=T["time"])
        self.lbl_sens_desc.config(text=T["sens"])
        self.lbl_pot_title.config(text=T["pot_head"])
        self.lbl_cur_title.config(text=f"{T['cur_head']} ({T['list_hdr']})")
        
        # Gewitter-UI Updates
        self.sf_frame.config(text=T["sf_title"])
        self.lbl_sf_dir.config(text=T["sf_dir"])
        self.lbl_sf_spd.config(text=T["sf_spd"])
        self.lbl_sf_amp.config(text=T["sf_amp"])
        self.lbl_sf_rate.config(text=T["sf_rate"])
        
        if not self.storm_placement_mode:
            self.btn_place_storm.config(text=T["sf_place"])
        self.btn_sferics.config(text=T["sf_off"] if self.storm_active else T["sf_on"])
        
        # Button-Texte
        self.btn_fast.config(text=T["fast_stop"] if self.is_fast_running else T["fast"])
        self.btn_realtime.config(text=T["real_stop"] if self.is_realtime_running else T["real"])
        
        # --- FIX FÜR RECHTSKLICK-MENÜ ---
        self.map_widget.right_click_menu_commands = [] 
        self.map_widget.add_right_click_menu_command(label=T["rec_menu"], 
                                                     command=self.set_receiver, 
                                                     pass_coords=True)

        # --- NEU: MODULATOR MENÜ AKTUALISIEREN ---
        self.mod_menu.delete(0, tk.END)
        self.mod_menu.add_command(label=T["mod_off"], command=lambda: self.set_global_gain_value(0.0))
        self.mod_menu.add_command(label=T["mod_max"], command=lambda: self.set_global_gain_value(1.0))
        self.mod_menu.add_separator()
        self.mod_menu.add_command(label=T["mod_custom"], command=self.set_global_gain_dialog)
        
        # Setzt den Titel des 2. Menü-Eintrags
        self.menubar.entryconfig(2, label=T["mod_menu"])        

        # Marker-Text anpassen
        if self.receiver_marker: 
            self.receiver_marker.set_text(T["rec_marker"])
            
        self.run_simulation()

    # --- GEWITTER STEUERUNG ---
    def enable_storm_placement(self):
        self.storm_placement_mode = True
        self.btn_place_storm.config(text=LANGUAGES[self.cur_lang]["sf_click"], bg="yellow")

    def place_storm_callback(self, coords):
        if self.storm_placement_mode:
            self.storm_pos = [coords[0], coords[1]]
            self.storm_placement_mode = False
            self.btn_place_storm.config(text=LANGUAGES[self.cur_lang]["sf_place"], bg="#f0f0f0")
            self.btn_sferics.config(state="normal")
            if not self.storm_active: self.toggle_sferics()

    def toggle_storm_panel(self):
        """Klappt das Gewitter-Panel auf oder zu."""
        if getattr(self, 'storm_visible', False):
            self.sf_frame.pack_forget()
            self.btn_toggle_storm.config(text="⛈ Sferics ▼")
        else:
            self.sf_frame.pack(fill="x", padx=10, pady=5, after=self.btn_toggle_storm)
            self.btn_toggle_storm.config(text="Sferics ▲ ")
        self.storm_visible = not getattr(self, 'storm_visible', False)

    def apply_storm_profile(self, event=None):
        """Setzt Slider-Werte basierend auf ITU-Profilvorgaben."""
        profile = self.storm_profile.get()
        if profile == "ITU Weak":
            self.sl_sf_amp.set(800)
            self.sl_sf_rate.set(2)
        elif profile == "ITU Medium":
            self.sl_sf_amp.set(2200)
            self.sl_sf_rate.set(7)
        elif profile == "ITU Strong":
            self.sl_sf_amp.set(4500)
            self.sl_sf_rate.set(15)

    def toggle_sferics(self):
        self.storm_active = not self.storm_active
        self.change_language(self.cur_lang)
        if self.storm_active:
            self.storm_icons = []
            self.storm_last_ui_update = 0.0  # Wichtig für Entkopplung
            self.storm_life_minutes = SFERICS_LIFETIME
            threading.Thread(target=self.storm_engine, daemon=True).start()
        else:
            if self.storm_polygon: 
                self.storm_polygon.delete()
                self.storm_polygon = None
            for icon in self.storm_icons:
                icon.delete()
            self.storm_icons = []

            if hasattr(self, 'storm_vector') and self.storm_vector:
                for line in self.storm_vector:
                    line.delete()
                self.storm_vector = [] # Liste leeren


    def storm_engine(self):
        last_time = time.time()
        self.storm_last_ui_update = 0
    
        while self.storm_active:
            current_time = time.time()
            # Die echte vergangene Zeit (meist ~0.1s wegen sleep)
            real_dt = current_time - last_time
            last_time = current_time
        
            # --- DER FAST-FORWARD FIX ---
            # Wenn Fast-Forward aktiv ist, multiplizieren wir die Zeit mal 60
            time_factor = 60.0 if self.is_fast_running else 1.0
            dt = real_dt * time_factor
        
            # 1. Bewegung (dt ist nun entweder 0.1s oder 6.0s effektiv)
            speed_deg_s = (self.sl_sf_spd.get() / 3600.0) / 111.0
            rad = math.radians(self.sl_sf_dir.get())
        
            self.storm_pos[0] += math.cos(rad) * speed_deg_s * dt
            self.storm_pos[1] += math.sin(rad) * speed_deg_s * dt
        
            # 2. Grafik-Update (bleibt bei realen 0.5s, sonst flimmert es)
            if current_time - getattr(self, 'storm_last_ui_update', 0) > 0.5:
                self.storm_last_ui_update = current_time
                self.root.after(0, self.draw_storm_circle)
        
            # 3. UDP-Sferics (Häufigkeit bei Fast-Forward ebenfalls anpassen?)
            # Optional: Blitze bei Fast-Forward seltener senden, da sie sonst alles fluten
            rate_limit = 0.05 if not self.is_fast_running else 0.01
        
            dist_km = math.sqrt(((self.storm_pos[0]-self.receiver_coords[0])*111.0)**2 + 
                               ((self.storm_pos[1]-self.receiver_coords[1])*85.0)**2)
        
            if random.random() < (self.sl_sf_rate.get() * rate_limit):
                attenuation = 1.0 / (1.0 + (max(0, dist_km - 20) / 80.0)**2)
                amp = int(self.sl_sf_amp.get() * attenuation * random.uniform(0.7, 1.3))
                if amp > 10:
                    try:
                        self.sock_sferics.sendto(f"{amp}:{random.uniform(5,45):.1f}".encode(), 
                                               (self.udp_ip, self.udp_port_sferics))
                    except: pass

                time.sleep(0.1)

    def draw_storm_circle(self):
        """
        Zeichnet eine runde Zone inkl. Symbolen und Vektorpfeil für Zugrichtung.
        """
        if not self.storm_active:
            return
        
        # 1. Kreis-Geometrie mit Mercator-Korrektur
        cos_lat = math.cos(math.radians(self.storm_pos[0]))
        aspect_korrektur = 1.0 / cos_lat
        r_deg = 0.7 
        
        pts = []
        for i in range(0, 360, 10):
            rad = math.radians(i)
            lat = self.storm_pos[0] + math.cos(rad) * r_deg
            lon = self.storm_pos[1] + math.sin(rad) * r_deg * aspect_korrektur
            pts.append((lat, lon))
        
        if self.storm_polygon:
            self.storm_polygon.delete()
        
        self.storm_polygon = self.map_widget.set_polygon(
            pts, fill_color="", outline_color="#ff3333", border_width=3
        )

        # 2. Symbole zentrieren
        symbols = ["⚡", "☁️", "⛈️", "⚡", "☁️"]
        inner_r = r_deg * 0.6 
        
        offsets = [(0,0), (0.4, 0.4), (-0.4, -0.4), (0.3, -0.5), (-0.3, 0.5)]
                
        if not self.storm_icons:
            for i, (off_lat, off_lon) in enumerate(offsets):
                s_lat = self.storm_pos[0] + off_lat * inner_r
                s_lon = self.storm_pos[1] + off_lon * inner_r * aspect_korrektur
                
                icon = self.map_widget.set_marker(
                    s_lat, s_lon,
                    text=symbols[i % len(symbols)],
                    font=("Arial", 20, "bold"),
                    marker_color_circle="#ffcc00",
                    marker_color_outside="#ffcc00" 
                )
                icon.image_hidden = True 
                self.storm_icons.append(icon)
        else:
            for i, (off_lat, off_lon) in enumerate(offsets):
                new_lat = self.storm_pos[0] + off_lat * inner_r
                new_lon = self.storm_pos[1] + off_lon * inner_r * aspect_korrektur
                self.storm_icons[i].set_position(new_lat, new_lon)
                
                if random.random() > 0.98:
                    self.storm_icons[i].set_text(random.choice(["⚡", " ", "⛈️"]))

        # 3. Zugrichtung und Geschwindigkeit (Vektorpfeil)
        # Alte Pfeil-Linien löschen
        if getattr(self, 'storm_vector', None):
            for line in self.storm_vector:
                line.delete()
        self.storm_vector = []
        
        speed = self.sl_sf_spd.get()
        if speed > 0:  # Pfeil nur zeichnen, wenn die Zelle zieht
            direction = self.sl_sf_dir.get()
            rad_dir = math.radians(direction)
            
            # Pfeillänge skalieren (z.B. 100 km/h = voller Radius)
            arrow_length = (speed / 100.0) * r_deg 
            
            # Endpunkt des Hauptvektors
            end_lat = self.storm_pos[0] + math.cos(rad_dir) * arrow_length
            end_lon = self.storm_pos[1] + math.sin(rad_dir) * arrow_length * aspect_korrektur
            
            # Hauptlinie zeichnen
            main_line = self.map_widget.set_path(
                [(self.storm_pos[0], self.storm_pos[1]), (end_lat, end_lon)],
                color="#0055ff", width=4
            )
            self.storm_vector.append(main_line)
            
            # Pfeilspitze zeichnen (zwei Linien, abgewinkelt um +/- 150 Grad)
            tip_length = 0.15 * r_deg  # Größe der Pfeilspitze
            for angle_offset in [150, -150]:
                tip_rad = rad_dir + math.radians(angle_offset)
                tip_lat = end_lat + math.cos(tip_rad) * tip_length
                tip_lon = end_lon + math.sin(tip_rad) * tip_length * aspect_korrektur
                
                tip_line = self.map_widget.set_path(
                    [(end_lat, end_lon), (tip_lat, tip_lon)],
                    color="#0055ff", width=4
                )
                self.storm_vector.append(tip_line)

    def set_receiver(self, coords):
        self.receiver_coords = coords
        if self.receiver_marker: self.receiver_marker.delete()
        self.receiver_marker = self.map_widget.set_marker(*coords, text=LANGUAGES[self.cur_lang]["rec_marker"], marker_color_outside="blue")
        self.run_simulation()

    def load_all_from_folder(self, folder):
        if not os.path.exists(folder): os.makedirs(folder); return
        for file in glob.glob(os.path.join(folder, "*.csv")):
            with open(file, mode='r', encoding='utf-8-sig') as f:
                for row in csv.reader(f):
                    if len(row) >= 5:
                        stadt, land, freq, kw, prog = [item.strip() for item in row[:5]]
                        cache_key = f"{stadt},{land}".upper()
                        self.cursor.execute("SELECT lat, lon FROM locations WHERE key=?", (cache_key,))
                        res = self.cursor.fetchone()
                        if not res:
                            try:
                                loc = self.geolocator.geocode(f"{stadt}, {land}")
                                if loc: 
                                    res = (loc.latitude, loc.longitude)
                                    self.cursor.execute("INSERT INTO locations VALUES (?,?,?)", (cache_key, *res))
                                    self.conn.commit()
                            except: continue
                        if res:
                            m = self.map_widget.set_marker(*res, text=f"{prog}\n{freq} kHz")
                            m.data = {"freq": freq, "kw": kw, "prog": prog}

    def open_simulation_window(self):
        self.sim_win = tk.Toplevel(self.root)
        self.sim_win.geometry("1050x700")

        ctrl = tk.Frame(self.sim_win, pady=10)
        ctrl.pack(fill="x")

        # UI Elemente für Lokalisation als Instanzvariablen
        self.lbl_date_desc = tk.Label(ctrl); self.lbl_date_desc.grid(row=0, column=0, padx=5)
        self.ent_date = tk.Entry(ctrl, width=10); self.ent_date.insert(0, "15.10."); self.ent_date.grid(row=0, column=1)
        self.ent_date.bind("<Return>", lambda e: self.run_simulation())

        self.lbl_time_desc = tk.Label(ctrl); self.lbl_time_desc.grid(row=0, column=2, padx=10)
        self.lbl_time_val = tk.Label(ctrl, text="12:00", font=("Arial", 10, "bold"), width=6)
        self.lbl_time_val.grid(row=0, column=3)
        
        self.time_slider = tk.Scale(ctrl, from_=0, to=23.99, resolution=0.01, orient="horizontal", length=200, showvalue=0, command=self.update_time_label)
        self.time_slider.set(12.0); self.time_slider.grid(row=0, column=4, padx=5)
        self.time_slider.bind("<ButtonRelease-1>", lambda e: self.run_simulation())

        self.btn_realtime = tk.Button(ctrl, command=self.toggle_realtime, width=14); self.btn_realtime.grid(row=0, column=5, padx=5)
        
        # Fast-Forward Button
        self.btn_fast = tk.Button(ctrl, command=self.toggle_fastforward, width=14)
        self.btn_fast.grid(row=0, column=6, padx=10)

        self.lbl_sens_desc = tk.Label(ctrl); self.lbl_sens_desc.grid(row=1, column=2, padx=10)
        self.sens_slider = tk.Scale(ctrl, from_=10, to=90, orient="horizontal", length=200)
        self.sens_slider.set(44); self.sens_slider.grid(row=1, column=4)
        self.sens_slider.bind("<ButtonRelease-1>", lambda e: self.run_simulation())

        self.lbl_sun = tk.Label(ctrl, font=("Arial", 10)); self.lbl_sun.grid(row=1, column=0, columnspan=2)

        # --- COLLAPSIBLE STORM PANEL ---
        self.storm_visible = False
        self.btn_toggle_storm = tk.Button(self.sim_win, text="⛈ Sferics ▼", 
                                          command=self.toggle_storm_panel, bg="#d5dbdb")
        self.btn_toggle_storm.pack(fill="x", padx=10, pady=2)

        self.sf_frame = tk.LabelFrame(self.sim_win, text="⛈ Gewitter-Zelle (Simulator)", pady=5, padx=10)

        row1 = tk.Frame(self.sf_frame); row1.pack(fill="x")
        self.btn_place_storm = tk.Button(row1, command=self.enable_storm_placement, width=18); self.btn_place_storm.pack(side="left", padx=5)
        self.btn_sferics = tk.Button(row1, command=self.toggle_sferics, width=12, state="disabled"); self.btn_sferics.pack(side="left", padx=5)
        
        tk.Label(row1, text="ITU-Profil:").pack(side="left", padx=10)
        self.storm_profile = ttk.Combobox(row1, values=["Manual", "ITU Weak", "ITU Medium", "ITU Strong"], state="readonly", width=12)
        self.storm_profile.current(0)
        self.storm_profile.bind("<<ComboboxSelected>>", self.apply_storm_profile)
        self.storm_profile.pack(side="left")

        # Richtung/Speed
        row2 = tk.Frame(self.sf_frame); row2.pack(fill="x", pady=5)
        self.lbl_sf_dir = tk.Label(row2); self.lbl_sf_dir.pack(side="left", padx=5)
        self.sl_sf_dir = tk.Scale(row2, from_=0, to=360, orient="horizontal", length=150); self.sl_sf_dir.set(90); self.sl_sf_dir.pack(side="left")
        self.lbl_sf_spd = tk.Label(row2); self.lbl_sf_spd.pack(side="left", padx=15)
        self.sl_sf_spd = tk.Scale(row2, from_=0, to=200, orient="horizontal", length=150); self.sl_sf_spd.set(50); self.sl_sf_spd.pack(side="left")

        # Power/Rate
        row3 = tk.Frame(self.sf_frame); row3.pack(fill="x", pady=5)
        self.lbl_sf_amp = tk.Label(row3); self.lbl_sf_amp.pack(side="left", padx=5)
        self.sl_sf_amp = tk.Scale(row3, from_=50, to=5000, orient="horizontal", length=250); self.sl_sf_amp.set(2500); self.sl_sf_amp.pack(side="left")
        self.lbl_sf_rate = tk.Label(row3); self.lbl_sf_rate.pack(side="left", padx=15)
        self.sl_sf_rate = tk.Scale(row3, from_=1, to=20, orient="horizontal", length=250); self.sl_sf_rate.set(6); self.sl_sf_rate.pack(side="left")

        # --- LISTEN-BEREICH ---
        list_f = tk.Frame(self.sim_win); list_f.pack(expand=True, fill="both", padx=10)
        self.lbl_pot_title = tk.Label(list_f); self.lbl_pot_title.grid(row=0, column=0)
        self.lbl_cur_title = tk.Label(list_f); self.lbl_cur_title.grid(row=0, column=1)
        
        f_style = ("MS Gothic", 9) if os.name == 'nt' else ("Courier", 9)
        self.list_max = tk.Listbox(list_f, width=45, font=f_style); self.list_max.grid(row=1, column=0, sticky="nsew", padx=5)
        self.list_now = tk.Listbox(list_f, width=80, font=f_style); self.list_now.grid(row=1, column=1, sticky="nsew", padx=5)
        list_f.rowconfigure(1, weight=1); list_f.columnconfigure(0, weight=1); list_f.columnconfigure(1, weight=2)

    def toggle_realtime(self):
        self.is_realtime_running = not self.is_realtime_running
        self.change_language(self.cur_lang)
        
        if self.is_realtime_running:
            # WICHTIG: Den Anker auf -1 setzen, damit er beim 
            # nächsten Check sofort die aktuelle Minute als Basis nimmt.
            self.last_pc_minute = -1
            self.realtime_tick()

    def realtime_tick(self):
        if self.is_realtime_running and self.sim_win.winfo_exists():
            now = datetime.now()
            
            # PRÜFUNG: Hat die PC-Uhr gerade auf eine neue Minute gewechselt?
            if now.minute != self.last_pc_minute:
                # Falls es der allererste Start ist (-1), setzen wir nur den Anker
                if self.last_pc_minute == -1:
                    self.last_pc_minute = now.minute

                    # Optional: Hier sofort einmal rechnen, damit der Start flüssig ist
                    self.run_simulation(send_udp=True)
                else:
                    self.last_pc_minute = now.minute
                    
                    # 1. Den aktuellen Stand vom Slider holen (User-Wunschzeit)
                    current_val = float(self.time_slider.get())
                    
                    # 2. Exakt eine Minute (1/60 Stunde) addieren
                    new_val = (current_val + (1/60)) % 24
                    
                    # 3. Slider und Label aktualisieren
                    # Der Slider "springt" jetzt sauber jede Minute ein Stück weiter
                    self.time_slider.set(new_val)
                    self.update_time_label(new_val)
                    
                    # 4. Simulation neu berechnen
                    self.run_simulation(send_udp=True)

                    # 5. GEWITTER-LEBENSDAUER REDUZIEREN
                    if self.storm_active:
                        self.storm_life_minutes -= 1.0
                        #print("sferice_active_for: \n",self.storm_life_minutes)
                        if self.storm_life_minutes <= 0:
                            self.toggle_sferics() # Schaltet QRN aus und löscht Icons/Pfeile
                            #print("⛈ Gewitter hat sich aufgelöst.")
                    
                    #print(f"PC-Uhr Minute gewechselt ({now.minute}) -> Simulation rückt vor.")

            # Wir prüfen häufig (alle 0.5s), damit wir den Moment 
            # des Umspringens präzise (max. 0.5s Verzögerung) erwischen.
            self.root.after(500, self.realtime_tick)

    def toggle_fastforward(self):
        self.is_fast_running = not self.is_fast_running
        if self.is_fast_running: self.is_realtime_running = False 
        self.change_language(self.cur_lang)
        if self.is_fast_running: self.fast_tick()

    def fast_tick(self):
        if self.is_fast_running and self.sim_win.winfo_exists():
            new_val = (float(self.time_slider.get()) + (1/60)) % 24
            self.time_slider.set(new_val); self.update_time_label(new_val)
            self.run_simulation(send_udp=True)
            self.root.after(1000, self.fast_tick)

    def update_time_label(self, val):
        v = float(val); self.lbl_time_val.config(text=f"{int(v):02d}:{int((v*60)%60):02d}")

    def get_sun_alt(self, lat, lon, n_day, time_h):
        decl = 23.45 * math.sin(math.radians(360 / 365 * (n_day - 81)))
        hour_angle = (time_h - 12) * 15 + lon
        return math.degrees(math.asin(math.sin(math.radians(lat)) * math.sin(math.radians(decl)) +
                                     math.cos(math.radians(lat)) * math.cos(math.radians(decl)) * math.cos(math.radians(hour_angle))))

    def set_global_gain_dialog(self):
        from tkinter import simpledialog
        val = simpledialog.askfloat("Gain", "0.0 - 1.0:", minvalue=0.0, maxvalue=1.0, parent=self.root)
        if val is not None:
            for freq_hz in range(100000, 1701000, 1000):
                msg = f"{freq_hz}:{round(val, 6)}"
                try: self.sock_gain.sendto(msg.encode(), (self.udp_ip, self.udp_port_gain))
                except: pass

    def set_global_gain_value(self, val):
        for freq_hz in range(100000, 1701000, 1000):
            msg = f"{freq_hz}:{round(float(val), 6)}"
            try: self.sock_gain.sendto(msg.encode(), (self.udp_ip, self.udp_port_gain))
            except: pass

    def run_simulation(self, send_udp=False):
        """
        WELLENAUSBREITUNGS-MODELL (MF/LF):
        
        1. BODENWELLE (Groundwave) nach ITU-R P.368-10:
           Berechnung der Feldstärke über Grund (σ = 5mS/m, Mittelwert).
           Basis: 107 dBµV/m @ 1km/1kW. Dämpfung erfolgt frequenzabhängig (f/180).
        
        2. RAUMWELLE (Skywave) nach ITU-R P.1147-2:
           Reflexion an der Ionosphäre (E-Schicht @100km bis F-Schicht @250km).
           Pfadverlust basierend auf der tatsächlichen Wegstrecke (Slant Range).
           
        3. D-SCHICHT ABSORPTION (Appleton-Hartree Vereinfachung):
           Berücksichtigt die solare Absorption in der D-Schicht.
           Dämpfungsfaktor steigt linear mit dem Sonnenstand (Elevation) 
           und quadratisch mit sinkender Frequenz (1/f²).
           
        4. LAUFZEIT-DIFFERENZIERUNG:
           Berechnung der Gruppenlaufzeit (Group Delay) für Boden- und Raumwelle,
           wichtig für die Simulation von Nah-Schwund (Fading/Phasing).
        """
        if not hasattr(self, 'list_max') or not self.list_max.winfo_exists(): return
        
        try:
            # --- Zeit- & Datums-Parsing ---
            date_raw = self.ent_date.get().strip().rstrip('.')
            if len(date_raw.split('.')) == 2: date_raw += ".1975" # Standardjahr für n_day Kalkulation
            dt = datetime.strptime(date_raw, "%d.%m.%Y")
            n_day, time_h = dt.timetuple().tm_yday, float(self.time_slider.get())
            
            self.list_max.delete(0, tk.END)
            self.list_now.delete(0, tk.END)
            
            # --- RX Standort & Sonnenstand --- Chapman-Schicht-Modell (vereinfacht).
            u_lat, u_lon = self.receiver_coords
            alt_rx = self.get_sun_alt(u_lat, u_lon, n_day, time_h)
            self.lbl_sun.config(text=f"{LANGUAGES[self.cur_lang]['sun']} {alt_rx:.2f}°", 
                               fg="blue" if alt_rx < -0.83 else "orange")

            # --- DYNAMISCHE REFLEXIONSHÖHE (Virtual Height h_ion) ---
            # Modelliert den Übergang von E-Schicht (Tag/Sommer) zu F-Schicht (Nacht/Winter)
            # h_ion variiert zwischen ~100km (Sommer-Mittag) und ~250km (Winter-Nacht)
            seasonal_factor = (math.cos(math.radians(360 / 365 * (n_day - 172))) + 1) / 2 # 0=Sommer, 1=Winter
            night_factor = 1.0 if alt_rx < -12 else max(0, -alt_rx / 12) if alt_rx < 0 else 0
            h_ion = 100 + (seasonal_factor * 80) + (night_factor * 70) 

        except Exception as e: 
            print(f"Sim Error: {e}")
            return

        res_list = []; sens = self.sens_slider.get(); c = 299.792 # Lichtgeschwindigkeit in km/ms
        
        for marker in self.map_widget.canvas_marker_list:
            d = getattr(marker, 'data', None)
            if isinstance(d, dict) and "freq" in d:
                m_lat, m_lon = marker.position
                
                # --- DISTANZBERECHNUNG ---
                # Vereinfachte Projektion für lokale Radien (km)
                dist = math.sqrt((u_lat - m_lat)**2 + (math.cos(math.radians(u_lat)) * (u_lon - m_lon))**2) * 111.32
                f, p = float(d["freq"]), float(d["kw"])
                
                # --- 1. BODENWELLE (Groundwave) ---
                # Basis: 107 dBuV/m @ 1km/1kW. Dämpfung: Freiraum + f-abhängige Bodenabsorption
                fs_g = 107 + 10*math.log10(p) - (20*math.log10(dist+1) + (f/180)*(dist/25))
                
                # --- 2. RAUMWELLE (Skywave) ---
                # Berechnung des tatsächlichen Signalwegs über die Ionosphäre (Dreiecksgeometrie)
                path_rw = 2 * math.sqrt((dist/2)**2 + h_ion**2)
                sky_base = 95 + 10*math.log10(p) - (20*math.log10(path_rw) + 15) if dist > 50 else -100
                
                # D-SCHICHT ABSORPTION: Findet nur statt, wenn die Sonne scheint
                # Bestimmt durch den höchsten Sonnenstand auf dem Pfad (RX vs TX)
                eff_alt = max(alt_rx, self.get_sun_alt(m_lat, m_lon, n_day, time_h))
                sun_f = max(0, (eff_alt + 12) / 24) if eff_alt > -12 else 0
                
                # Absorption steigt quadratisch mit sinkender Frequenz (1/f^2)
                sky_loss = sun_f * 85 * ((1000 / f) ** 2)
                cur_sky = sky_base - sky_loss
                
                # --- LAUFZEITEN (Delays) ---
                t_bw = dist / (c * 0.997) # Bodenwelle (leicht verzögert durch Erdnähe)
                t_rw = path_rw / c        # Raumwelle (direkter Pfad durch Luft/Vakuum)
                
                res_list.append({
                    "p": d["prog"], "f": f, 
                    "pot": max(fs_g, sky_base), 
                    "now": max(fs_g, cur_sky), 
                    "fs_g": fs_g, "fs_s": cur_sky, 
                    "t_bw": t_bw, "t_rw": t_rw
                })

        # --- SORTIERUNG & ANZEIGE ---
        # 1. Potential-Liste (Was wäre nachts möglich?)
        res_list.sort(key=lambda x: x["pot"], reverse=True)
        for r in res_list: 
            self.list_max.insert(tk.END, f"{r['pot']:4.1f} | {int(r['f']):4} kHz | {r['p'][:25]}")
        
        # 2. Aktuelle Empfangsliste (Was ist JETZT hörbar?)
        res_list.sort(key=lambda x: x["now"], reverse=True)
        for r in res_list:
            if r['now'] > sens:
                # Modus-Erkennung: Welcher Pfad dominiert oder gibt es Interferenz (Fading)?
                m = "GrW+SkW" if abs(r['fs_g'] - r['fs_s']) < 10 else ("SkW   " if r['fs_s'] > r['fs_g'] else "GrW   ")
                # Anzeige der Delays je nach aktivem Pfad
                t_disp = f"{r['t_bw']:.2f}/{r['t_rw']:.2f}" if "GrW+SkW" in m else (f"{r['t_rw']:.2f}" if "SkW" in m else f"{r['t_bw']:.2f}")
                
                self.list_now.insert(tk.END, f"{r['now']:4.1f} | {int(r['f']):4}k | {r['p'][:15]} | {m} | {t_disp}ms")
                
                # --- UDP-VERSAND AN MODULATOR ---
                if send_udp:
                    # Dynamik: 40 dB Fenster oberhalb der eingestellten Schwelle
                    gain_norm = max(0.0, min(1.0, (r['now'] - sens) / 40.0))
                    # Format: Frequenz in Hz : Linearer Gain (0.0-1.0)
                    msg = f"{int(r['f'] * 1000)}:{round(gain_norm, 6)}"
                    try: 
                        self.sock_gain.sendto(msg.encode(), (self.udp_ip, self.udp_port_gain))
                    except: 
                        pass


if __name__ == "__main__":
    root = tk.Tk(); app = RadioMapApp(root); root.mainloop()
