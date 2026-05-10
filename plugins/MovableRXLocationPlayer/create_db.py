import sqlite3
import requests
import zipfile
import io
import os

def setup_offline_db():
    db_name = 'cities.db'
    url = "https://download.geonames.org/export/dump/cities1000.zip"
    
    print("--- Minimalist Offline DB Builder ---")
    
    try:
        # 1. Download
        print("1. Lade Daten herunter...")
        r = requests.get(url, timeout=30)
        
        # 2. SQLite Initialisierung
        conn = sqlite3.connect(db_name)
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS cities")
        cur.execute("CREATE TABLE cities (name TEXT, lat REAL, lon REAL)")
        
        # 3. ZIP im Speicher entpacken und Zeile für Zeile verarbeiten
        print("2. Verarbeite Städte (Stream-Modus)...")
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            with z.open('cities1000.txt') as f:
                for line in f:
                    # Dekodieren und splitten (Tab-getrennt)
                    parts = line.decode('utf-8').split('\t')
                    
                    # GeoNames Format: 
                    # Index 1 = Name, Index 4 = Lat, Index 5 = Lon
                    name = parts[1]
                    lat = float(parts[4])
                    lon = float(parts[5])
                    
                    cur.execute("INSERT INTO cities VALUES (?, ?, ?)", (name, lat, lon))
        
        # 4. Index erstellen (WICHTIG für Speed im Navi!)
        print("3. Erstelle Such-Index...")
        cur.execute("CREATE INDEX idx_coords ON cities(lat, lon)")
        
        conn.commit()
        conn.close()
        print(f"\nFERTIG! '{db_name}' ist bereit ({os.path.getsize(db_name)/1024/1024:.1f} MB).")

    except Exception as e:
        print(f"\nFehler: {e}")

if __name__ == "__main__":
    setup_offline_db()