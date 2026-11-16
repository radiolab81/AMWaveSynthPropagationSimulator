"""Gemeinsame Schnittstelle aller Ausbreitungsmodelle.

Ein Modell ist reine Physik: Es bekommt Empfaenger/Sender/Zeit und liefert Feldstaerken
in dBuV/m (fuer 1 Sender, OHNE Empfangsantennen-Richtwirkung - die wendet die Engine an).
Es greift nie auf die UI zu und haelt keinen Zustand ueber einen Rechenlauf hinaus.
Dadurch kann das Modell zur Laufzeit gewechselt werden.

Neues Modell: Datei in diesem Ordner anlegen, von PropagationModel erben, `name` setzen,
`compute()` implementieren. Es erscheint beim naechsten Start automatisch im Dropdown.
"""
import math
from dataclasses import dataclass

C_KM_PER_MS = 299.792   # Lichtgeschwindigkeit in km/ms


@dataclass
class SimContext:
    """Alles, was fuer einen Rechenlauf gleich bleibt."""
    rx_lat: float
    rx_lon: float
    n_day: int          # Tag im Jahr (1..366)
    time_h: float       # UTC in Stunden (0..24)
    sun_alt_rx: float   # Sonnenhoehe am Empfaenger in Grad


@dataclass
class Tx:
    lat: float
    lon: float
    freq: float         # kHz
    kw: float           # Sendeleistung kW


@dataclass
class LinkResult:
    fs_g: float         # Bodenwelle dBuV/m
    fs_s: float         # Raumwelle JETZT dBuV/m
    fs_s_pot: float     # Raumwelle "Potential" (Nacht-Bestwert) dBuV/m
    t_bw: float         # Laufzeit Bodenwelle ms
    t_rw: float         # Laufzeit Raumwelle ms
    # Wie stark die Richtwirkung der Empfangsantenne auf die Raumwelle wirkt (0..1).
    # 1.0 = volle Wirkung wie auf die Bodenwelle (Standard); kleiner bei steilem Einfall
    # (kurze Distanz), z.B. min(1, d/800 km) -> Nachteffekt: Peilnullen fuellen sich.
    sky_ant_factor: float = 1.0


class PropagationModel:
    name = ""           # Anzeigename im Dropdown (leer = kein Modell, wird ignoriert)
    description = ""

    def prepare(self, ctx):
        """Einmal pro Rechenlauf vor den compute()-Aufrufen."""
        self.ctx = ctx

    def compute(self, tx):
        raise NotImplementedError


# ---------------------------------------------------------------- Hilfsfunktionen
def sun_alt(lat, lon, n_day, time_h):
    decl = 23.45 * math.sin(math.radians(360 / 365 * (n_day - 81)))
    hour_angle = (time_h - 12) * 15 + lon
    return math.degrees(math.asin(math.sin(math.radians(lat)) * math.sin(math.radians(decl)) +
                                  math.cos(math.radians(lat)) * math.cos(math.radians(decl)) * math.cos(math.radians(hour_angle))))


def sun_decl(n_day):
    return 23.45 * math.sin(math.radians(360 / 365 * (n_day - 81)))


def gc_distance(lat1, lon1, lat2, lon2):
    """Grosskreisdistanz in km (Haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def gc_intermediate(lat1, lon1, lat2, lon2, frac):
    """Punkt auf der Grosskreisroute bei Anteil frac (0..1) -> (lat, lon)."""
    p1, l1, p2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    d = gc_distance(lat1, lon1, lat2, lon2) / 6371.0
    if d < 1e-9: return lat1, lon1
    a = math.sin((1 - frac) * d) / math.sin(d)
    b = math.sin(frac * d) / math.sin(d)
    x = a * math.cos(p1) * math.cos(l1) + b * math.cos(p2) * math.cos(l2)
    y = a * math.cos(p1) * math.sin(l1) + b * math.cos(p2) * math.sin(l2)
    z = a * math.sin(p1) + b * math.sin(p2)
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))
