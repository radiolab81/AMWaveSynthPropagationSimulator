import tkinter as tk
from tkinter import simpledialog
import socket
import json
import threading
import math
import os
from tkintermapview import TkinterMapView
from PIL import Image, ImageTk
from tkinter import messagebox

class TraineeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DFmap")
        self.root.geometry("900x900")

        try:
            if os.path.exists("tower.png"):
                tower_img = Image.open("tower.png").resize((32, 32))
                self.tower_icon = ImageTk.PhotoImage(tower_img)
            else:
                self.tower_icon = None
        except Exception as e:
            print(f"Konnte tower.png nicht laden: {e}")
            self.tower_icon = None

        self.teacher_ip = "127.0.0.1" 
        self.teacher_port = 8887

        self.map_widget = TkinterMapView(self.root, width=900, height=700)
        self.map_widget.pack(fill="both", expand=True)
        self.map_widget.set_position(51.1657, 10.4515) 
        self.map_widget.set_zoom(6)

        self.tx_markers = []
        
        # --- State-Variablen und native Event-Bindings ---
        self.rotating_marker = None
        self.draw_pending = False        # Verhindert Frame-Stau
        self.last_mouse_event = None     # Merkt sich die letzte Mausposition
        # Schlichtungsstelle für den TkinterMapView-Klick-Bug
        self.click_job = None
        self.clicked_marker_this_frame = None
        self.clicked_map_this_frame = None
        
        # 1. Klick auf den Kartenhintergrund = Strahl fixieren
        self.map_widget.add_left_click_map_command(self.lock_bearing)
        
        # 2. Mausbewegung generell überwachen (add="+" verhindert das Überschreiben interner Events)
        self.map_widget.canvas.bind("<Motion>", self.update_live_bearing, add="+")

        self.btn_sync = tk.Button(
            self.map_widget, text="🔴 SYNC", font=("Arial", 12, "bold"),
            bg="white", fg="red", command=self.start_sync, relief="raised", padx=10
        )
        self.btn_sync.place(relx=0.02, rely=0.02)

    # --- GEODÄTISCHE BERECHNUNGEN ---
    def get_destination_point(self, lat, lon, bearing_deg, distance_km):
        R = 6378.1
        brng = math.radians(bearing_deg)
        lat1 = math.radians(lat)
        lon1 = math.radians(lon)

        lat2 = math.asin(math.sin(lat1) * math.cos(distance_km / R) +
                         math.cos(lat1) * math.sin(distance_km / R) * math.cos(brng))
        lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(distance_km / R) * math.cos(lat1),
                                 math.cos(distance_km / R) - math.sin(lat1) * math.sin(lat2))
        
        return math.degrees(lat2), math.degrees(lon2)

    def create_compass_rose_path(self, lat, lon, radius_km=40):
        points = []
        for angle in range(0, 360, 10):
            pt = self.get_destination_point(lat, lon, angle, radius_km)
            points.append(pt)
        points.append(points[0]) 
        return points

    def calculate_bearing(self, lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.atan2(y, x)
        return (math.degrees(bearing) + 360) % 360

    def get_geodesic_line(self, lat, lon, bearing, distance_km, steps=15):
        points = []
        for i in range(steps + 1):
            d = (distance_km / steps) * i
            points.append(self.get_destination_point(lat, lon, bearing, d))
        return points

    # --- INTERAKTION ---
    def update_live_bearing(self, event):
        """Drosselt die Maus-Updates auf ca. 30 FPS, damit Tkinter nicht einfriert."""
        if not self.rotating_marker:
            return
            
        self.last_mouse_event = event
        
        # Wenn aktuell kein Zeichen-Befehl in der Warteschlange ist, neuen starten
        if not self.draw_pending:
            self.draw_pending = True
            # Führt die Berechnung erst in 30ms aus (entspricht flüssigen ~30 FPS)
            self.root.after(30, self.process_live_bearing)


    def process_live_bearing(self):
        """Führt die eigentliche Berechnung nach der Drosselung aus."""
        self.draw_pending = False
        if not self.rotating_marker or not self.last_mouse_event:
            return
            
        event = self.last_mouse_event
        mouse_gps = self.map_widget.convert_canvas_coords_to_decimal_coords(event.x, event.y)
        
        if mouse_gps and None not in mouse_gps:
            lat_tx, lon_tx = self.rotating_marker.position
            current_heading = self.calculate_bearing(lat_tx, lon_tx, mouse_gps[0], mouse_gps[1])
            self.draw_bearing_lines(self.rotating_marker, current_heading)

    def on_marker_click(self, marker):
        """Wird aufgerufen, wenn ein Sender-Marker angeklickt wird."""
        # 1. Den geklickten Marker sofort für diesen Frame abspeichern
        self.clicked_marker_this_frame = marker
        
        # 2. Kurze Pause einlegen, um den Event-Stau von Tkinter abzuwarten
        if not self.click_job:
            self.click_job = self.root.after(20, self.handle_combined_clicks)

    def lock_bearing(self, coords):
        """Wird aufgerufen, wenn auf den Kartenhintergrund geklickt wird."""
        # 1. Die geklickten Map-Koordinaten sofort abspeichern
        self.clicked_map_this_frame = coords
        
        # 2. Kurze Pause einlegen, um ggf. den Event-Stau von Tkinter abzuwarten
        if not self.click_job:
            self.click_job = self.root.after(20, self.handle_combined_clicks)

    def handle_combined_clicks(self):
        """Entscheidet nach 20ms logisch, ob ein Marker oder die Map gemeint war."""
        self.click_job = None
        
        marker = self.clicked_marker_this_frame
        coords = self.clicked_map_this_frame
        
        self.clicked_marker_this_frame = None
        self.clicked_map_this_frame = None
        
        # FALL 1: Es wurde ein Marker getroffen!
        if marker is not None:
            if self.rotating_marker == marker:
                # Wenn genau dieser Sender schon aktiv war -> Strahl fest einrasten lassen
                self.rotating_marker = None
            else:
                # Diesen Sender als neuen aktiven Peilsender wählen
                self.rotating_marker = marker
                
                # Sofort beim Klick genordeten Peilstrahl (0°) zeichnen ---
                self.draw_bearing_lines(marker, 0.0)
                
        # FALL 2: Kein Marker getroffen, aber die leere Landkarte wurde angeklickt
        elif coords is not None:
            if self.rotating_marker is not None:
                # Aktiven Peilstrahl fest einrasten lassen
                self.rotating_marker = None

    # --- NETZWERK & ZEICHNEN ---
    def start_sync(self):
        self.btn_sync.config(text="🟡 SYNCING...", fg="orange", state="disabled")
        threading.Thread(target=self.udp_sync_thread, daemon=True).start()

    def udp_sync_thread(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3.0) 
        
        try:
            sock.sendto("GET_TRANSMITTERS".encode('utf-8'), (self.teacher_ip, self.teacher_port))
            data, _ = sock.recvfrom(65535)
            response = json.loads(data.decode('utf-8'))
            
            if response.get("status") == "OK":
                self.root.after(0, self.draw_transmitters, response.get("transmitters", []))
            else:
                self.root.after(0, self.sync_failed)
        except Exception as e:
            print(f"Fehler beim Sync: {e}")
            self.root.after(0, self.sync_failed)
        finally:
            sock.close()

    def draw_transmitters(self, tx_list):
        for marker in self.tx_markers:
            if hasattr(marker, 'bearing_path') and marker.bearing_path: marker.bearing_path.delete()
            if hasattr(marker, 'rose_path') and marker.rose_path: marker.rose_path.delete()
            marker.delete()
        self.tx_markers.clear()
        
        for tx in tx_list:
            lat, lon, freq = tx.get("lat"), tx.get("lon"), tx.get("freq")
            
            if lat and lon:
                if self.tower_icon:
                    m = self.map_widget.set_marker(lat, lon, text=f"{freq} kHz", icon=self.tower_icon, command=self.on_marker_click)
                else:
                    m = self.map_widget.set_marker(lat, lon, text=f"{freq} kHz", marker_color_circle="black", marker_color_outside="red", command=self.on_marker_click)
                
                m.data = tx
                self.tx_markers.append(m)
        
        self.btn_sync.config(text=f"🟢 SYNCED ({len(tx_list)})", fg="green", state="normal")
        self.root.after(4000, self.reset_button)

    def sync_failed(self):
        self.btn_sync.config(text="❌ ERROR", fg="red", state="normal")
        self.root.after(4000, self.reset_button)
        
    def reset_button(self):
        self.btn_sync.config(text="🔴 SYNC", fg="red", state="normal")

    def draw_bearing_lines(self, marker, heading):
        """Zeichnet die Standlinie. Die Kompassrose wird nur 1x gezeichnet."""
        # 1. Nur die blaue Peillinie löschen
        if hasattr(marker, 'bearing_path') and marker.bearing_path:
            marker.bearing_path.delete()
            
        lat, lon = marker.position
        
        points_back = self.get_geodesic_line(lat, lon, (heading + 180) % 360, 600, steps=12)
        points_forward = self.get_geodesic_line(lat, lon, heading, 600, steps=12)
        full_path = points_back[::-1] + [(lat, lon)] + points_forward
        
        marker.bearing_path = self.map_widget.set_path(full_path, color="#0055ff", width=3)
        
        # 2. PERFORMANCE-BOOST: Kompassrose NUR zeichnen, wenn sie noch nicht existiert!
        if not hasattr(marker, 'rose_path') or marker.rose_path is None:
            rose_points = self.create_compass_rose_path(lat, lon, radius_km=40)
            marker.rose_path = self.map_widget.set_path(rose_points, color="#ffaa00", width=2)
            
        # Text-Label am Marker live mit der Gradzahl aktualisieren
        freq = marker.data.get("freq", "")
        marker.set_text(f"{freq} kHz\n➔ {heading:.1f}°")

if __name__ == "__main__":
    root = tk.Tk()
    app = TraineeApp(root)
    root.mainloop()