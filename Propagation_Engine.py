import math
import tkinter as tk
from propagation_models import (SimContext, Tx, sun_alt, create_model, DEFAULT_MODEL)

class PropagationEngine:
    """Rahmen um austauschbare Ausbreitungsmodelle (siehe Ordner propagation_models/).

    Die Engine kuemmert sich um UI-Parsing, Antennen-Richtwirkung, Listenanzeige und den
    UDP-Versand; die Physik (Boden-/Raumwelle, Laufzeiten) liefert das aktive Modell.
    """
    def __init__(self, app):
        self.app = app
        self.c = 299.792  # Lichtgeschwindigkeit in km/ms
        self.last_active_stations = set()
        self.model = create_model(DEFAULT_MODEL)

    def set_model(self, name):
        """Modell zur Laufzeit wechseln (Modelle sind zustandslos)."""
        self.model = create_model(name)

    def get_sun_alt(self, lat, lon, n_day, time_h):
        return sun_alt(lat, lon, n_day, time_h)

    def gain_from_level(self, level, sens):
        """Feldstaerke (dBuV/m) -> Modulator-Gain 0..1 (UDP 8888).

        Der Modulator skaliert die Traegeramplitude LINEAR (Spannung) mit dem Gain:
        dB = 20*log10(gain).
          'compat'  : (Pegel - Schwelle)/40  -> linear in dB, stark gestaucht (altes Verhalten)
          'physical': Pegel relativ zu (Schwelle + Fenster), gain = 10^(dB/20), 1.0 = Vollaussteuerung
        """
        if getattr(self.app, 'gain_mode', 'compat') == 'physical':
            win = float(getattr(self.app, 'gain_window', 28))
            return max(0.0, min(1.0, 10 ** ((level - sens - win) / 20.0)))
        return max(0.0, min(1.0, (level - sens) / 40.0))

    def run_simulation(self, send_udp=False):
        """Berechnet fuer alle Sender-Marker die Feldstaerken mit dem aktiven Modell."""
        if not hasattr(self.app, 'list_max') or not self.app.list_max.winfo_exists(): return
        
        try:
            from datetime import datetime
            # --- Zeit- & Datums-Parsing ---
            date_raw = self.app.ent_date.get().strip().rstrip('.')
            if len(date_raw.split('.')) == 2: date_raw += ".1975" # Standardjahr für n_day Kalkulation
            dt = datetime.strptime(date_raw, "%d.%m.%Y")
            n_day, time_h = dt.timetuple().tm_yday, float(self.app.time_slider.get())
            
            self.app.list_max.delete(0, tk.END)
            self.app.list_now.delete(0, tk.END)
            
            # --- RX Standort & Sonnenstand --- Chapman-Schicht-Modell (vereinfacht).
            u_lat, u_lon = self.app.receiver_coords
            alt_rx = self.get_sun_alt(u_lat, u_lon, n_day, time_h)
            self.app.lbl_sun.config(text=f"{self.app.LANGUAGES[self.app.cur_lang]['sun']} {alt_rx:.2f}°", 
                               fg="blue" if alt_rx < -0.83 else "orange")

            self.model.prepare(SimContext(u_lat, u_lon, n_day, time_h, alt_rx))

        except Exception as e: 
            print(f"Sim Error: {e}")
            return

        res_list = []; sens = self.app.sens_slider.get()
        
        for marker in self.app.map_widget.canvas_marker_list:
            d = getattr(marker, 'data', None)
            if isinstance(d, dict) and "freq" in d:
                m_lat, m_lon = marker.position
                
                f, p = float(d["freq"]), float(d["kw"])
                try:
                    lr = self.model.compute(Tx(m_lat, m_lon, f, p))
                except Exception as e:
                    print(f"Modellfehler ({d.get('prog')}): {e}")
                    continue

                # --- ANTENNEN-RICHTCHARAKTERISTIK ---
                # Berechnet die Dämpfung basierend auf Azimut und Antennendrehung
                ant_loss = self.app.antenna_engine.get_attenuation(u_lat, u_lon, m_lat, m_lon)
                sky_ant = ant_loss * lr.sky_ant_factor   # Modell bestimmt die Wirkung auf die Raumwelle
                fs_g = lr.fs_g + ant_loss
                cur_sky = lr.fs_s + sky_ant
                sky_base = lr.fs_s_pot + sky_ant

                res_list.append({
                    "p": d["prog"], "f": f,
                    "pot": max(fs_g, sky_base),
                    "now": max(fs_g, cur_sky),
                    "fs_g": fs_g, "fs_s": cur_sky,
                    "t_bw": lr.t_bw, "t_rw": lr.t_rw
                })

        # SORTIERUNG & ANZEIGE
        # 1. Potential-Liste (Was wäre nachts möglich?)
        res_list.sort(key=lambda x: x["pot"], reverse=True)
        for r in res_list: 
            self.app.list_max.insert(tk.END, f"{r['pot']:4.1f} | {int(r['f']):4} kHz | {r['p'][:25]}")
        
        # 2. Aktuelle Empfangsliste (Was ist JETZT hörbar?)
        res_list.sort(key=lambda x: x["now"], reverse=True)

        # Set für diesen Durchlauf vorbereiten
        now_active_stations = set()

        for r in res_list:
            if r['now'] > sens:
                # Modus-Erkennung: Welcher Pfad dominiert oder gibt es Interferenz (Fading)?
                m = "GrW+SkW" if abs(r['fs_g'] - r['fs_s']) < 10 else ("SkW   " if r['fs_s'] > r['fs_g'] else "GrW   ")
                # Anzeige der Delays je nach aktivem Pfad
                t_disp = f"{r['t_bw']:.2f}/{r['t_rw']:.2f}" if "GrW+SkW" in m else (f"{r['t_rw']:.2f}" if "SkW" in m else f"{r['t_bw']:.2f}")

                self.app.list_now.insert(tk.END, f"{r['now']:4.1f} | {int(r['f']):4}k | {r['p'][:15]} | {m} | {t_disp}ms")
                
                # --- UDP-VERSAND AN MODULATOR ---
                if send_udp:
                    freq_hz = int(r['f'] * 1000)
                    now_active_stations.add(freq_hz)  # Im aktuellen Durchlauf als aktiv registrieren
                    
                    gain_norm = self.gain_from_level(r['now'], sens)
                    # Format: Frequenz in Hz : Linearer Gain (0.0-1.0)
                    msg = f"{freq_hz}:{round(gain_norm, 6)}"
                    try: 
                        self.app.sock_gain.sendto(msg.encode(), (self.app.udp_ip, self.app.udp_port_gain))
                    except: 
                        pass

        # --- AUFRÄUMEN --- EFFIZIENTER GEDÄCHTNIS-RESET (ERSETZT DAS GANZE BAND ZU NULLEN) ---
        if send_udp:
            # Welche Frequenzen waren LETZTES MAL aktiv, sind es JETZT aber nicht mehr?
            droped_stations = self.last_active_stations - now_active_stations

            # NUR für diese stumm gewordenen Sender schicken wir exakt EINMAL 0.0!
            for f_hz in droped_stations:
                try: 
                    self.app.sock_gain.sendto(f"{f_hz}:0.0".encode(), (self.app.udp_ip, self.app.udp_port_gain))
                except: 
                    pass

            # Das Gedächtnis für den nächsten Schritt aktualisieren
            self.last_active_stations = now_active_stations


        # Aktualisiert das optische Antennen-Polygon, falls eine Richtcharakteristik aktiv ist
        if hasattr(self.app, 'antenna_engine'):
            self.app.antenna_engine.update_visuals()

