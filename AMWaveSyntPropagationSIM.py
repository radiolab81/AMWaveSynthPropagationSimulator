import tkinter as tk
from tkinter import ttk
import os, glob, csv, sqlite3, re, time, math, socket
from datetime import datetime
from tkintermapview import TkinterMapView
from geopy.geocoders import ArcGIS

# --- LOKALISIERUNGSDATEN ---
LANGUAGES = {
    "DE": {
        "title": "Ausbreitungssimulator für HF-Modulator Steuerung (UDP 8888)",
        "date": "Datum (TT.MM):", "time": "Uhrzeit:", "sens": "Schwelle (dBµV/m):",
        "sun": "Sonne (RX):", "pot_head": "Potential (Nacht)", "cur_head": "AKTUELLER Empfang",
        "list_hdr": "dB | Hz | Name | Modus | ms", "fast": "⏩ Fast-Forward",
        "fast_stop": "■ Stop Fast", "real": "▶ Echtzeit Start", "real_stop": "■ Echtzeit Stop",
        "rec_marker": "🏠 Empfänger", "rec_menu": "Empfänger hierher",
	"mod_menu": "Modulator", "mod_off": "Alle AUS (0.0)", "mod_max": "Alle MAX (1.0)", "mod_custom": "Gain Wert setzen..."

    },
    "EN": {
        "title": "HF Modulator Propagation Simulator Control (UDP 8888)",
        "date": "Date (DD.MM):", "time": "Time:", "sens": "Threshold (dBµV/m):",
        "sun": "Sun (RX):", "pot_head": "Potential (Night)", "cur_head": "CURRENT Reception",
        "list_hdr": "dB | Hz | Name | Mode | ms", "fast": "⏩ Fast-Forward",
        "fast_stop": "■ Stop Fast", "real": "▶ Start Realtime", "real_stop": "■ Stop Realtime",
        "rec_marker": "🏠 Receiver", "rec_menu": "Receiver here",
	"mod_menu": "Modulator", "mod_off": "All OFF (0.0)", "mod_max": "All MAX (1.0)", "mod_custom": "Set Gain Value..."
    },
    "FR": {
        "title": "Simulateur de propagation HF (UDP 8888)",
        "date": "Date (JJ.MM):", "time": "Heure:", "sens": "Seuil (dBµV/m):",
        "sun": "Soleil (RX):", "pot_head": "Potentiel (Nuit)", "cur_head": "Réception ACTUELLE",
        "list_hdr": "dB | Hz | Nom | Mode | ms", "fast": "⏩ Avance rapide",
        "fast_stop": "■ Arrêter", "real": "▶ Temps réel", "real_stop": "■ Arrêter",
        "rec_marker": "🏠 Récepteur", "rec_menu": "Récepteur ici",
	"mod_menu": "Modulateur", "mod_off": "Tous OFF (0.0)", "mod_max": "Tous MAX (1.0)", "mod_custom": "Régler le Gain..."
    },
    "IT": {
        "title": "Simulatore di propagazione HF (UDP 8888)",
        "date": "Data (GG.MM):", "time": "Ora:", "sens": "Soglia (dBµV/m):",
        "sun": "Sole (RX):", "pot_head": "Potenziale (Notte)", "cur_head": "Ricezione ATTUALE",
        "list_hdr": "dB | Hz | Nome | Modo | ms", "fast": "⏩ Avanti veloce",
        "fast_stop": "■ Ferma", "real": "▶ Tempo reale", "real_stop": "■ Ferma",
        "rec_marker": "🏠 Ricevitore", "rec_menu": "Ricevitore qui",
	"mod_menu": "Modulatore", "mod_off": "Tutto OFF (0.0)", "mod_max": "Tutto MAX (1.0)", "mod_custom": "Imposta Gain..."
    },
    "JP": {
        "title": "HFモジュレーター伝搬シミュレーター (UDP 8888)",
        "date": "日付 (日.月):", "time": "時刻:", "sens": "しきい値 (dBµV/m):",
        "sun": "太陽 (RX):", "pot_head": "ポテンシャル (夜間)", "cur_head": "現在の受信状態",
        "list_hdr": "dB | Hz | 放送局名 | モード | ms", "fast": "⏩ 早送り",
        "fast_stop": "■ 停止", "real": "▶ リアルタイム開始", "real_stop": "■ 停止",
        "rec_marker": "🏠 受信機", "rec_menu": "受信機をここに設置",
	"mod_menu": "変調器", "mod_off": "全オフ (0.0)", "mod_max": "全最大 (1.0)", "mod_custom": "ゲイン値を設定..."
    }
}

class RadioMapApp:
    def __init__(self, root):
        self.root = root
        self.cur_lang = "DE"
        self.root.title(LANGUAGES[self.cur_lang]["title"])
        self.root.geometry("1200x850")

        # UDP Setup für externen liquidDSP Modulator (Port 8888)
        self.udp_ip = "127.0.0.1"
        self.udp_port = 8888
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

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
        self.map_widget.set_position(52.52, 13.40); self.map_widget.set_zoom(5)
        
        self.setup_menu()
        self.is_realtime_running = False
        self.is_fast_running = False

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
        self.sim_win.title(T["title"])
        self.lbl_date_desc.config(text=T["date"])
        self.lbl_time_desc.config(text=T["time"])
        self.lbl_sens_desc.config(text=T["sens"])
        self.lbl_pot_title.config(text=T["pot_head"])
        self.lbl_cur_title.config(text=f"{T['cur_head']} ({T['list_hdr']})")
        
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
        
        # Setzt den Titel des 2. Menü-Eintrags (Index 2, da 0=Sprache, 1=Separator/Spacer falls vorhanden)
        self.menubar.entryconfig(2, label=T["mod_menu"])        

        # Marker-Text anpassen
        if self.receiver_marker: 
            self.receiver_marker.set_text(T["rec_marker"])
            
        self.run_simulation()


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
        if self.is_realtime_running: self.realtime_tick()

    def realtime_tick(self):
        if self.is_realtime_running and self.sim_win.winfo_exists():
            new_val = (float(self.time_slider.get()) + (1/60)) % 24
            self.time_slider.set(new_val); self.update_time_label(new_val)
            self.run_simulation(send_udp=True)
            self.root.after(60000, self.realtime_tick)

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
                try: self.sock.sendto(msg.encode(), (self.udp_ip, self.udp_port))
                except: pass

    def set_global_gain_value(self, val):
        for freq_hz in range(100000, 1701000, 1000):
            msg = f"{freq_hz}:{round(float(val), 6)}"
            try: self.sock.sendto(msg.encode(), (self.udp_ip, self.udp_port))
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
                        self.sock.sendto(msg.encode(), (self.udp_ip, self.udp_port))
                    except: 
                        pass


if __name__ == "__main__":
    root = tk.Tk(); app = RadioMapApp(root); root.mainloop()
