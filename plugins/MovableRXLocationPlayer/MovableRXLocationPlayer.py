import gpxpy
import socket
import math
import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox
from geopy.distance import geodesic

# --- network config ---
UDP_IP = "127.0.0.1"
UDP_PORT = 8886
DB_FILE = "cities.db" # local db, place in app folder

# --- localisation ---
LANG = {
    "DE": {
        "wait": "WARTE AUF GPX...", "load": "GPX LADEN", "start": "START", "pause": "PAUSE", 
        "zone": "STADT / LAND", "inner": "Stadt", "outer": "Land", "dist": "Distanz", "err": "LANDSTRASSE"
    },
    "EN": {
        "wait": "WAITING FOR GPX...", "load": "LOAD GPX", "start": "START", "pause": "PAUSE", 
        "zone": "CITY / HWY", "inner": "City", "outer": "Hwy", "dist": "Distance", "err": "RURAL ROAD"
    },
    "JA": {
        "wait": "GPXを待機中...", "load": "ファイルを読込", "start": "開始", "pause": "一時停止", 
        "zone": "市街地 / 郊外", "inner": "市街地", "outer": "郊外", "dist": "距離", "err": "郊外"
    }
}

class Movable_RX_Location_Player:
    def __init__(self, root):
        self.root = root
        self.root.title("Movable RX Location Player")
        self.root.geometry("900x320")
        self.root.configure(bg="#050505")
        self.root.resizable(False, False)

        self.lang = "EN"
        self.full_path = [] 
        self.total_dist = 0
        self.dist_covered = 0
        self.is_playing = False
        self.is_innerorts = False
        self.current_curve_angle = 0
        
        self.profiles = {"Car": (50, 100), "Semi": (40, 80), "Bicycle": (15, 25)}
        self.active_profile = "Car"
        
        self.setup_ui()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def setup_ui(self):
        top_frame = tk.Frame(self.root, bg="#050505")
        top_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        bottom_frame = tk.Frame(self.root, bg="#050505")
        bottom_frame.pack(fill="x", side="bottom", padx=20, pady=15)

        left_f = tk.Frame(top_frame, bg="#050505", width=200)
        left_f.pack(side="left", fill="y", padx=10)
        left_f.pack_propagate(False)

        mid_f = tk.Frame(top_frame, bg="#050505", width=400)
        mid_f.pack(side="left", fill="both", expand=True, padx=10)

        right_f = tk.Frame(top_frame, bg="#050505", width=200)
        right_f.pack(side="right", fill="y", padx=10)

        # --- LEFT: direction / heading ---
        self.lbl_arrow = tk.Label(left_f, text="▽", font=("Arial", 110), fg="#00e5ff", bg="#050505")
        self.lbl_arrow.pack(expand=True)

        # --- center: dashboard ---
        self.lbl_city = tk.Label(mid_f, text=LANG[self.lang]["wait"], font=("Arial", 22, "bold"), fg="#ffffff", bg="#050505")
        self.lbl_city.pack(anchor="w", pady=(10, 0))

        self.lbl_speed = tk.Label(mid_f, text="0 km/h", font=("Courier", 38, "bold"), fg="#00e5ff", bg="#050505")
        self.lbl_speed.pack(anchor="w")

        self.lbl_coords = tk.Label(mid_f, text="LAT: 0.000000 | LON: 0.000000", font=("Courier", 11), fg="#666", bg="#050505")
        self.lbl_coords.pack(anchor="w", pady=(5,0))
        
        self.lbl_stats = tk.Label(mid_f, text=f"{LANG[self.lang]['dist']}: 0.0 / 0.0 km", font=("Arial", 11), fg="#aaa", bg="#050505")
        self.lbl_stats.pack(anchor="w")

        # --- right: controls ---
        self.var_lang = tk.StringVar(value=self.lang)
        tk.OptionMenu(right_f, self.var_lang, "DE", "EN", "JA", command=self.change_lang).pack(fill="x", pady=2)
        
        self.btn_load = tk.Button(right_f, text=LANG[self.lang]["load"], command=self.load_file, bg="#222", fg="#00e5ff")
        self.btn_load.pack(fill="x", pady=2)
        
        self.btn_play = tk.Button(right_f, text=LANG[self.lang]["start"], command=self.toggle_play, state="disabled", bg="#111", fg="white")
        self.btn_play.pack(fill="x", pady=2)

        self.btn_zone = tk.Button(right_f, text=LANG[self.lang]["zone"], command=self.toggle_zone, bg="#222", fg="white")
        self.btn_zone.pack(fill="x", pady=2)

        self.var_prof = tk.StringVar(value="Car")
        tk.OptionMenu(right_f, self.var_prof, *self.profiles.keys(), command=self.set_profile).pack(fill="x", pady=2)

        self.slider = tk.Scale(bottom_frame, from_=0, to=100, orient="horizontal", command=self.on_slider_change,
                               bg="#111", fg="#00e5ff", highlightthickness=0, showvalue=False)
        self.slider.pack(fill="x")

    def get_city_offline(self, lat, lon):
        """Sucht in der lokalen SQLite DB nach dem nächsten Ort im 5km Umkreis."""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            limit = 0.045 # ca. 5km distance
            query = "SELECT name FROM cities WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ? LIMIT 1"
            cursor.execute(query, (lat-limit, lat+limit, lon-limit, lon+limit))
            row = cursor.fetchone()
            conn.close()
            return (True, row[0].upper()) if row else (False, LANG[self.lang]["err"])
        except:
            return (False, "DB FEHLT!")

    def change_lang(self, selection):
        self.lang = selection
        self.btn_load.config(text=LANG[self.lang]["load"])
        self.btn_zone.config(text=LANG[self.lang]["zone"])
        self.btn_play.config(text=LANG[self.lang]["pause"] if self.is_playing else LANG[self.lang]["start"])
        self.update_display(self.dist_covered)

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("GPX Files", "*.gpx")])
        if not path: return
        try:
            with open(path, 'r') as f:
                gpx = gpxpy.parse(f)
                pts = [p for t in gpx.tracks for s in t.segments for p in s.points]
                self.full_path = []
                acc = 0
                for i in range(len(pts)):
                    d = geodesic((pts[i-1].latitude, pts[i-1].longitude), (pts[i].latitude, pts[i].longitude)).meters if i > 0 else 0
                    acc += d
                    self.full_path.append({'pos': (pts[i].latitude, pts[i].longitude), 'dist': acc})
                
                self.total_dist = acc
                self.slider.config(to=acc)
                self.btn_play.config(state="normal")
                self.update_display(0)
        except Exception as e: messagebox.showerror("Error", str(e))

    def toggle_play(self):
        self.is_playing = not self.is_playing
        self.btn_play.config(text=LANG[self.lang]["pause"] if self.is_playing else LANG[self.lang]["start"])
        if self.is_playing: self.run_sim()

    def toggle_zone(self):
        self.is_innerorts = not self.is_innerorts
        self.update_display(self.dist_covered)

    def set_profile(self, val):
        self.active_profile = val
        self.update_display(self.dist_covered)

    def on_slider_change(self, val):
        self.dist_covered = float(val)
        self.root.after_idle(lambda: self.update_display(self.dist_covered))

    def interpolate_at_dist(self, d):
        for i in range(len(self.full_path)-1):
            p1, p2 = self.full_path[i], self.full_path[i+1]
            if p1['dist'] <= d <= p2['dist']:
                s_len = p2['dist'] - p1['dist']
                f = (d - p1['dist']) / s_len if s_len > 0 else 0
                lat = p1['pos'][0] + (p2['pos'][0] - p1['pos'][0]) * f
                lon = p1['pos'][1] + (p2['pos'][1] - p1['pos'][1]) * f
                l1, n1 = map(math.radians, p1['pos'])
                l2, n2 = map(math.radians, p2['pos'])
                x = math.sin(n2-n1) * math.cos(l2)
                y = math.cos(l1)*math.sin(l2)-math.sin(l1)*math.cos(l2)*math.cos(n2-n1)
                b = (math.degrees(math.atan2(x, y)) + 360) % 360
                return (lat, lon), b
        return self.full_path[-1]['pos'] if self.full_path else (0,0), 0

    def update_display(self, d):
        if not self.full_path: return
        pos, bearing = self.interpolate_at_dist(d)
        _, f_bearing = self.interpolate_at_dist(min(d + 80, self.total_dist))
        
        # 1. driving direction / heading
        self.current_curve_angle = (f_bearing - bearing + 180) % 360 - 180
        if self.current_curve_angle > 20: self.lbl_arrow.config(text="➜")
        elif self.current_curve_angle < -20: self.lbl_arrow.config(text="⬅")
        else: self.lbl_arrow.config(text="↑")

        # 2. offline zone & name check
        is_near, city_name = self.get_city_offline(pos[0], pos[1])
        self.is_innerorts = is_near
        self.lbl_city.config(text=city_name)

        # 3. speed
        v_in, v_out = self.profiles[self.active_profile]
        speed = v_in if self.is_innerorts else v_out
        if abs(self.current_curve_angle) > 20:
            speed = min(speed, 30)
            
        self.lbl_speed.config(text=f"{speed} km/h")
        self.lbl_coords.config(text=f"LAT: {pos[0]:.6f} | LON: {pos[1]:.6f}")
        
        z_text = LANG[self.lang]['inner'] if self.is_innerorts else LANG[self.lang]['outer']
        self.lbl_stats.config(text=f"[{z_text}] {LANG[self.lang]['dist']}: {d/1000:.2f} / {self.total_dist/1000:.2f} km")

        # 4. UDP
        try: self.sock.sendto(f"{pos[0]:.6f},{pos[1]:.6f}".encode(), (UDP_IP, UDP_PORT))
        except: pass

    def run_sim(self):
        if not self.is_playing: return
        cur_v = int(self.lbl_speed.cget("text").split()[0])
        self.dist_covered += (cur_v / 3.6)
        
        if self.dist_covered >= self.total_dist:
            self.dist_covered = self.total_dist
            self.is_playing = False
            self.btn_play.config(text=LANG[self.lang]["start"])
        
        self.slider.set(self.dist_covered)
        self.root.after(1000, self.run_sim)

if __name__ == "__main__":
    root = tk.Tk()
    app = Movable_RX_Location_Player(root)
    root.mainloop()