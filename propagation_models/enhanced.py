"""Klassisch+ : das klassische Modell mit korrigierter Physik, gleiche Dramaturgie.

Behaelt das Verhalten des klassischen Modells bei, was fuer eine Hoerer-Simulation zaehlt
(Raumwelle ueber virtuelle Hoehe, D-Schicht ~ Sonnenstand/f^2 -> Baender oeffnen in der
Daemmerung von oben nach unten), und behebt die Schwaechen, die beim Pruefen aufgefallen sind:

  1. Bodenwelle: Norton/Rolf-Naeherung (numerische Distanz, Bodenleitfaehigkeit) statt eines
     linearen dB/km-Terms. Der alte Term stimmte bis ca. 100 km, lag bei 200 km um ~13 dB, bei
     300 km um ~31 dB und bei 500 km um ~70 dB (1000 kHz) zu tief -> Tagband zu leer.
  2. Entfernung: Grosskreis (Haversine) statt ebener Projektion.
  3. Raumwelle: Hop-Modell ab HOP_LEN_KM (Zusatzverlust je weiterem Hop) statt unbegrenzt
     fortgesetztem Einzelhop (bei 4000 km lieferte das alte Modell noch 8 dBuV/m). Die Hop-Zahl
     ist STETIG (d/HOP_LEN_KM), damit der Pegel an den Hop-Grenzen nicht um HOP_LOSS_DB springt;
     bei ganzzahligen Vielfachen von HOP_LEN_KM identisch zum diskreten Hop-Modell.
  4. D-Schicht: optional 1/(f+fL)^2 statt 1/f^2 (FL_KHZ, Standard 0 = wie bisher), und fuer
     Langwelle ein Deckel der Tagesabsorption (D-Schicht reflektiert dort, absorbiert nicht).
  5. SKY_OFFSET_DB: Pegelkorrektur der Raumwelle. Gemessen lag das klassische Modell nachts
     (50 kW, ca. 700 km) rund 20 dB unter dem ITU-R-P.1147-Modell dieses Programms. Standard 0
     (= unveraendertes Niveau); ein Wert um +10..+20 holt die Raumwelle in diese Naehe.

fL, HOP_LOSS_DB, LW-Deckel und SKY_OFFSET_DB sind Schaetzwerte, nicht gegen ITU-R
P.1147/P.368 nachgerechnet. Die Konstanten sind unten einstellbar.
"""
import math
from .base import PropagationModel, LinkResult, C_KM_PER_MS, sun_alt, gc_distance


class EnhancedClassicModel(PropagationModel):
    name = "Klassisch+ (Norton, Hops)"
    description = ("Klassisches Modell mit Norton-Bodenwelle, Grosskreisdistanz und Hop-Modell; "
                   "Daemmerungsverhalten (von oben nach unten) wie das klassische Modell.")

    GROUND_SIGMA  = 0.005    # S/m, mittlerer Boden
    FL_KHZ        = 0.0      # 0 = 1/f^2 (wie bisher); ~1400 = flacherer Verlauf 1/(f+fL)^2
    LW_SKY_CAP_DB = 35.0     # LW (< 300 kHz): Obergrenze der D-Schicht-Dämpfung
    HOP_LEN_KM    = 2000.0   # maximale Laenge eines MW-Hops
    HOP_LOSS_DB   = 10.0     # Zusatzverlust je weiterem Hop (Schaetzwert)
    SKY_OFFSET_DB = 0.0      # Pegelkorrektur Raumwelle (Standard: unveraendert)
    SKY_ANT_REF_KM = 800.0   # RX-Richtwirkung wirkt auf die Raumwelle mit min(1, d/800 km) (steiler Einfall nah)

    def prepare(self, ctx):
        self.ctx = ctx
        n_day, alt_rx = ctx.n_day, ctx.sun_alt_rx
        # Reflexionshoehe: E-Schicht (Tag/Sommer) -> F-Schicht (Nacht/Winter), wie klassisch
        seasonal = (math.cos(math.radians(360 / 365 * (n_day - 172))) + 1) / 2   # 0=Sommer, 1=Winter
        night = 1.0 if alt_rx < -12 else max(0, -alt_rx / 12) if alt_rx < 0 else 0
        self.h_ion = 100 + seasonal * 80 + night * 70

    # ---------------------------------------------------------------- Bodenwelle
    def ground_wave(self, d_km, f_khz, p_kw):
        """107 dBuV/m @ 1 km/1 kW, Dämpfung nach Norton/Rolf; unter 1 km nicht weiter ansteigend."""
        d = max(d_km, 1.0)
        f_mhz = f_khz / 1000.0
        lam_km = 0.299792 / f_mhz
        x = 1.8e4 * self.GROUND_SIGMA / f_mhz
        p = math.pi * d / (lam_km * x)                       # numerische Distanz
        att = (2 + 0.3 * p) / (2 + p + 0.6 * p * p)
        return 107 + 10 * math.log10(p_kw) - 20 * math.log10(d) + 20 * math.log10(att)

    def sky_ant(self, d_km):
        return min(1.0, d_km / self.SKY_ANT_REF_KM)

    # ---------------------------------------------------------------- Link
    def compute(self, tx):
        c = self.ctx
        f, p_kw = tx.freq, max(tx.kw, 1e-3)
        dist = gc_distance(c.rx_lat, c.rx_lon, tx.lat, tx.lon)

        fs_g = self.ground_wave(dist, f, p_kw)
        t_bw = dist / (C_KM_PER_MS * 0.997)

        if dist <= 50:                                       # wie klassisch: kein Raumwellenpfad
            path = 2 * math.sqrt((dist / 2) ** 2 + self.h_ion ** 2)
            return LinkResult(fs_g, -100.0, -100.0, t_bw, path / C_KM_PER_MS, self.sky_ant(dist))

        hops = max(1.0, dist / self.HOP_LEN_KM)              # stetige Hop-Zahl (kein Sprung an der Grenze)
        hop_d = dist / hops
        path = hops * 2 * math.sqrt((hop_d / 2) ** 2 + self.h_ion ** 2)
        base = (95 + 10 * math.log10(p_kw) - (20 * math.log10(path) + 15)
                - (hops - 1) * self.HOP_LOSS_DB + self.SKY_OFFSET_DB)

        # D-Schicht: bei 1 MHz wie klassisch kalibriert (85 dB * sun_f)
        eff_alt = max(c.sun_alt_rx, sun_alt(tx.lat, tx.lon, c.n_day, c.time_h))
        sun_f = max(0, (eff_alt + 12) / 24) if eff_alt > -12 else 0
        loss = sun_f * 85.0 * ((1000.0 + self.FL_KHZ) / (f + self.FL_KHZ)) ** 2
        if f < 300.0:
            loss = min(loss, self.LW_SKY_CAP_DB)

        return LinkResult(fs_g, base - loss, base, t_bw, path / C_KM_PER_MS, self.sky_ant(dist))
