from .base import PropagationModel, LinkResult, C_KM_PER_MS, sun_alt
import math


class ClassicModel(PropagationModel):
    name = "Klassisch (heuristisch)"
    description = ("Urspruengliches Modell des Simulators: einfache Bodenwellen-Faustformel, "
                   "Raumwelle ueber virtuelle Hoehe, D-Schicht ~ Sonnenstand/f^2. "
                   "Ergebnisse identisch zu frueheren Versionen.")

    def prepare(self, ctx):
        self.ctx = ctx
        n_day, alt_rx = ctx.n_day, ctx.sun_alt_rx
        # --- DYNAMISCHE REFLEXIONSHÖHE (Virtual Height h_ion) ---
        # Modelliert den Übergang von E-Schicht (Tag/Sommer) zu F-Schicht (Nacht/Winter)
        seasonal_factor = (math.cos(math.radians(360 / 365 * (n_day - 172))) + 1) / 2   # 0=Sommer, 1=Winter
        night_factor = 1.0 if alt_rx < -12 else max(0, -alt_rx / 12) if alt_rx < 0 else 0
        self.h_ion = 100 + (seasonal_factor * 80) + (night_factor * 70)

    def compute(self, tx):
        c, u_lat, u_lon = self.ctx, self.ctx.rx_lat, self.ctx.rx_lon
        f, p = tx.freq, max(tx.kw, 1e-3)

        # --- DISTANZBERECHNUNG ---
        # Vereinfachte Projektion fuer lokale Radien (km)
        dist = math.sqrt((u_lat - tx.lat) ** 2 + (math.cos(math.radians(u_lat)) * (u_lon - tx.lon)) ** 2) * 111.32

        # 1. Bodenwelle
        # Basis: 107 dBuV/m @ 1km/1kW. Dämpfung: Freiraum + f-abhängige Bodenabsorption
        fs_g = 107 + 10 * math.log10(p) - (20 * math.log10(dist + 1) + (f / 180) * (dist / 25))

        # 2. Raumwelle Berechnung des tatsächlichen Signalwegs über die Ionosphäre (Dreiecksgeometrie ueber virtuelle Hoehe)
        path_rw = 2 * math.sqrt((dist / 2) ** 2 + self.h_ion ** 2)
        sky_base = 95 + 10 * math.log10(p) - (20 * math.log10(path_rw) + 15) if dist > 50 else -100

        # D-SCHICHT ABSORPTION
        # Bestimmt durch den höchsten Sonnenstand auf dem Pfad (RX vs TX)
        eff_alt = max(c.sun_alt_rx, sun_alt(tx.lat, tx.lon, c.n_day, c.time_h))
        sun_f = max(0, (eff_alt + 12) / 24) if eff_alt > -12 else 0
        sky_loss = sun_f * 85 * ((1000 / f) ** 2)

        return LinkResult(fs_g=fs_g, fs_s=sky_base - sky_loss, fs_s_pot=sky_base,
                          t_bw=dist / (C_KM_PER_MS * 0.997), t_rw=path_rw / C_KM_PER_MS)
