"""Raumwelle nach ITU-R P.1147-2 (150-1705 kHz), Bodenwelle nach Norton (flache Erde).

UMGESETZT (P.1147-2, Gl. 1-13): E = V + A - 20 log p - La - Lt - Lr
  - p = sqrt(d^2 + 200^2), La = k*p/1000, k = 2*pi + 4.95*tan^2(Phi) (Phi = geomagn. Breite
    des Pfadmittelpunkts, max. +-60 Grad; Pfade > 3000 km: Mittel aus zwei Pfadhaelften)
  - A = 110.2 (LF) bzw. 107 (MF), Lr (Sonnenflecken, nur MF und |Phi| > 45 Grad)
  - Lt: Stundenfaktor um Sonnenuntergang/-aufgang (Polynome aus Anhang 1)
NICHT UMGESETZT (-> 0 dB): vertikaler Gewinn GV (Fig. 1), Seegewinn GS, Polarisationskopplung Lp
  (braucht magn. Inklination), Richtantennen GH, Sonnenfleckenzahl R (Standard 0).
VEREINFACHT: Lt-Kontrollpunkt = Pfadmitte auch bei d >= 2000 km; Lt am Tag = konstanter
  Tageswert (MF 43 dB laut Anhang 2, LF Schaetzwert) mit weichem Uebergang zu den Polynomen.
JAHRESZEITEN: P.1147-2 liefert den Jahresmedian und beschreibt die Saison nur qualitativ
  (Anhang 1/2: MF nachts Maxima Fruehjahr/Herbst, Sommerminimum ausgepraegter, Schwankung
  bis 15 dB bei niedrigem MF -> ca. 3 dB bei 1700 kHz; LF nachts Sommermaximum; MF mittags
  Wintermaximum, Wintermittel ca. +10 dB; in den Tropen deutlich kleiner). Daraus wird hier
  eine parametrische, jahresmittelwertfreie Korrektur gebildet (siehe season_delta()); die
  Amplituden folgen dem Text, Phasenlage/Form und der LF-Wert (8 dB) sind Annahmen.
Bodenwelle: Norton-Naeherung A = (2+0.3p)/(2+p+0.6p^2) mit numerischer Distanz p, Leitfaehigkeit
  und Permittivitaet als Konstanten. Erdkruemmung/Beugung nicht enthalten -> bei > ca. 300 km
  zu optimistisch; die echten P.368-Kurven werden NICHT reproduziert.
"""
import math
from .base import PropagationModel, LinkResult, C_KM_PER_MS, gc_distance, gc_intermediate, sun_decl


class ITUP1147Model(PropagationModel):
    name = "ITU-R P.1147-2 (mit Jahreszeiten)"
    description = "Raumwelle nach P.1147-2 inkl. Tag/Nacht-Verlauf und Jahreszeiten, Bodenwelle nach Norton."

    GROUND_SIGMA = 0.005      # S/m  (mittlerer Boden)
    GROUND_EPS = 15.0
    SUNSPOT_R = 0.0           # 12-Monats-Sonnenfleckenzahl
    LF_MF_BORDER_KHZ = 300.0
    LT_DAY_MF = 43.0          # dB, Anhang 2: MF-Mittag ~43 dB unter Nachtwert
    LT_DAY_LF = 26.0          # dB, Schaetzwert (Anhang 2: LF 7..45 dB)

    SKY_ANT_REF_KM = 800.0    # Richtwirkung der RX-Antenne wirkt auf die Raumwelle mit min(1, d/800 km)

    SEASONAL = True           # Jahreszeitenkorrektur ein/aus
    SEASON_NIGHT_MF_PK = (530.0, 15.0, 1700.0, 3.0)   # (f1 kHz, dB, f2 kHz, dB) Spitze-Spitze
    SEASON_NIGHT_LF_PK = 8.0  # dB Spitze-Spitze, Sommermaximum (Annahme, im Text ohne Wert)
    SEASON_DAY_MF_AMP = 11.0  # dB Amplitude: Wintermaximum (Wintermittel ~ +10 dB)

    # ------------------------------------------------------------ Bodenwelle
    def ground_wave(self, d, f_khz, p_kw):
        d = max(d, 1.0)
        lam_m = 299792.458 / f_khz
        x = 1.8e4 * self.GROUND_SIGMA / (f_khz / 1000.0)
        cosb = 1.0 / math.sqrt(1.0 + ((self.GROUND_EPS + 1.0) / x) ** 2)
        pn = math.pi * d * 1000.0 * cosb / (lam_m * x)          # numerische Distanz
        att = (2 + 0.3 * pn) / (2 + pn + 0.6 * pn * pn)
        return 109.5 + 10 * math.log10(p_kw) - 20 * math.log10(d) + 20 * math.log10(att)

    # ------------------------------------------------------------ Raumwelle
    @staticmethod
    def geomag_lat(lat, lon):
        a = math.radians(lat)
        s = (math.sin(a) * math.sin(math.radians(78.5)) +
             math.cos(a) * math.cos(math.radians(78.5)) * math.cos(math.radians(69 + lon)))
        return max(-60.0, min(60.0, math.degrees(math.asin(max(-1, min(1, s))))))

    def k_factor(self, lat, lon):
        return 2 * math.pi + 4.95 * math.tan(math.radians(self.geomag_lat(lat, lon))) ** 2

    @staticmethod
    def _poly_ss(t): return max(0.0, 12.40 - 9.248 * t + 2.892 * t ** 2 - 0.3343 * t ** 3)
    @staticmethod
    def _poly_sr(t): return max(0.0, 9.6 + 12.2 * t + 5.62 * t ** 2 + 0.86 * t ** 3)

    def lt_loss(self, lat, lon, lf):
        """Stundenfaktor Lt (dB) am Kontrollpunkt; 0 um Mitternacht."""
        ctx = self.ctx
        T = (ctx.time_h + lon / 15.0) % 24.0                     # lokale Sonnenzeit
        l_day = self.LT_DAY_LF if lf else self.LT_DAY_MF
        phi, dec = math.radians(lat), math.radians(sun_decl(ctx.n_day))
        cosh0 = (math.sin(math.radians(-0.833)) - math.sin(phi) * math.sin(dec)) / (math.cos(phi) * math.cos(dec) + 1e-12)
        if cosh0 >= 1: return 0.0                                # Polarnacht
        if cosh0 <= -1: return l_day                             # Polartag
        h = math.degrees(math.acos(cosh0)) / 15.0                # halbe Tageslaenge in h
        tr, ts = 12 - h, 12 + h
        if tr <= T <= ts:                                        # Tag
            t_sr, t_ss = T - tr, T - ts
            if t_ss > -1: return self._poly_ss(t_ss)
            if t_sr < 1: return self._poly_sr(t_sr)
            e_sr, e_ss = self._poly_sr(1.0), self._poly_ss(-1.0)
            r_sr = e_sr + (l_day - e_sr) * min(1.0, (t_sr - 1) / 2)
            r_ss = e_ss + (l_day - e_ss) * min(1.0, (-t_ss - 1) / 2)
            return min(r_sr, r_ss)
        if T > ts:                                               # Abend/Nacht
            t = T - ts
            return self._poly_ss(t) if t < 4 else 0.0
        t = T - tr                                               # Nacht vor Sonnenaufgang (t < 0)
        return self._poly_sr(t) if t > -3 else 0.0

    # ------------------------------------------------------------ Jahreszeiten
    @staticmethod
    def _night_mf_shape(n):
        # Halbjahres-Anteil (Maxima Fruehjahr/Herbst) + Jahresanteil (Sommer tiefer als Winter)
        return 0.7 * math.cos(4 * math.pi * (n - 80) / 365.0) + 0.3 * math.cos(2 * math.pi * (n - 355) / 365.0)

    def _norm_night_mf(self, n):
        if not hasattr(ITUP1147Model, "_nm_stats"):
            vals = [self._night_mf_shape(i) for i in range(1, 366)]
            ITUP1147Model._nm_stats = (sum(vals) / len(vals), min(vals), max(vals))
        mean, lo, hi = ITUP1147Model._nm_stats
        return (self._night_mf_shape(n) - mean) / (hi - lo)       # Spitze-Spitze = 1, Mittel = 0

    def season_delta(self, n_day, f_khz, mid_lat, lf, w_day):
        """Abweichung vom Jahresmedian in dB (Mittel ueber das Jahr = 0).
        w_day: 0 = Nacht ... 1 = Tag (aus dem Stundenfaktor Lt)."""
        if not self.SEASONAL: return 0.0, 0.0
        n = n_day + (182.6 if mid_lat < 0 else 0.0)               # Suedhalbkugel: Jahreszeiten vertauscht
        n = (n - 1) % 365 + 1
        lat_w = 0.2 + 0.8 * min(1.0, abs(mid_lat) / 35.0)         # Tropen: deutlich kleiner
        if lf:
            night = 0.5 * self.SEASON_NIGHT_LF_PK * math.cos(2 * math.pi * (n - 172) / 365.0)
            day = 0.0
        else:
            f1, a1, f2, a2 = self.SEASON_NIGHT_MF_PK
            pk = a1 + (a2 - a1) * (min(max(f_khz, f1), f2) - f1) / (f2 - f1)
            night = pk * self._norm_night_mf(n)
            day = self.SEASON_DAY_MF_AMP * math.cos(2 * math.pi * (n - 355) / 365.0)
        return lat_w * night, lat_w * ((1 - w_day) * night + w_day * day)

    def sky_ant(self, d_km):
        return min(1.0, d_km / self.SKY_ANT_REF_KM)

    def compute(self, tx):
        c = self.ctx
        d = gc_distance(c.rx_lat, c.rx_lon, tx.lat, tx.lon)
        f = tx.freq
        p_kw = max(tx.kw, 1e-3)
        pdb = 10 * math.log10(p_kw)
        lf = f < self.LF_MF_BORDER_KHZ

        fs_g = self.ground_wave(d, f, p_kw)
        t_bw = d / (C_KM_PER_MS * 0.997)

        p = math.sqrt(d * d + 40000.0)
        t_rw = p / C_KM_PER_MS
        if d < 50.0:                                             # P.1147 gilt ab 50 km
            return LinkResult(fs_g, -100.0, -100.0, t_bw, t_rw, self.sky_ant(d))

        if d > 3000.0:
            pts = [gc_intermediate(c.rx_lat, c.rx_lon, tx.lat, tx.lon, q) for q in (0.25, 0.75)]
            k = sum(self.k_factor(*pt) for pt in pts) / 2
        else:
            k = self.k_factor(*gc_intermediate(c.rx_lat, c.rx_lon, tx.lat, tx.lon, 0.5))
        mid_lat, mid_lon = gc_intermediate(c.rx_lat, c.rx_lon, tx.lat, tx.lon, 0.5)

        a_const = 110.2 if lf else 107.0
        la = k * p / 1000.0
        lr = 0.0
        if not lf:
            phi = abs(self.geomag_lat(mid_lat, mid_lon))
            if phi > 45: lr = ((phi - 45) / 3.0) * (self.SUNSPOT_R / 100.0) * (p / 1000.0)
        e_night = pdb + a_const - 20 * math.log10(p) - la - lr
        lt = self.lt_loss(mid_lat, mid_lon, lf)
        l_day = self.LT_DAY_LF if lf else self.LT_DAY_MF
        d_night, d_now = self.season_delta(c.n_day, f, mid_lat, lf, min(1.0, lt / l_day))
        return LinkResult(fs_g, e_night - lt + d_now, e_night + d_night, t_bw, t_rw, self.sky_ant(d))
