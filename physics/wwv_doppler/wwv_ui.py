# wwv_ui.py - Pythonista UI for WWV recordings, solar-context aware
import os, re, glob, io, wave, logging, math
from datetime import datetime, timezone
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Wedge
import ui

logging.getLogger('matplotlib').setLevel(logging.WARNING)

DIR     = os.path.expanduser('~/Documents/kiwiclient')
F0      = 1000.0        # Hz  — WWV 10 MHz downmixed to ~1 kHz
WIN     = 10.0          # s   — analysis window
SEARCH  = 5.0           # Hz  — search half-width around F0
MODES   = ['Doppler', 'Spectrogram', 'SNR']

# WWV transmitter (Fort Collins, CO) and a default receiver.
# Override RX_LAT/RX_LON if you know your site.
TX_LAT, TX_LON =  40.68, -105.04
RX_LAT, RX_LON =  40.00, -105.00   # <-- edit me


# ---------- I/O ----------

def load(path):
    with wave.open(path) as w:
        if w.getsampwidth() != 2:
            raise ValueError(f'{path}: expected 16-bit PCM, got {w.getsampwidth()*8}-bit')
        fs, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float)
    return (x.reshape(-1, ch).mean(axis=1) if ch > 1 else x), fs


def parse_utc(path):
    """Try filename timestamp; fall back to file mtime."""
    m = re.search(r'(\d{4}-\d{2}-\d{2}[T_]\d{2}[:-]\d{2}[:-]\d{2})',
                  os.path.basename(path))
    if m:
        s = m.group(1).replace('_', 'T').replace(':', '')
        # normalize to ISO 8601: 2024-01-15T123000
        s = re.sub(r'T(\d{2})(\d{2})(\d{2})', r'T\1:\2:\3', s)
        try:
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)


# ---------- Spectral tracking ----------

def track(x, fs):
    N   = int(WIN * fs)
    hop = N // 2
    win = np.hanning(N)
    f   = np.fft.rfftfreq(N, 1/fs)
    idx = np.where(np.abs(f - F0) < SEARCH)[0]

    if len(x) < N or len(idx) < 3:
        return np.array([]), np.array([]), np.array([])

    t, df, snr = [], [], []
    for s in range(0, len(x) - N, hop):
        P = np.abs(np.fft.rfft(x[s:s+N] * win))**2
        k = idx[np.argmax(P[idx])]
        a, b, c = np.log(P[k-1:k+2] + 1e-12)
        denom = a - 2*b + c
        delta = 0.5*(a - c)/denom if abs(denom) > 1e-12 else 0.0
        df.append(f[k] + delta*(f[1] - f[0]) - F0)
        snr.append(10*np.log10(P[k] / (np.median(P[idx]) + 1e-12)))
        t.append((s + N/2) / fs)
    return np.array(t), np.array(df), np.array(snr)


# ---------- Solar / geometry ----------

def subsolar(dt_utc):
    """Return (lat_deg, lon_deg) of the sub-solar point. Spencer 1971."""
    n  = dt_utc.timetuple().tm_yday
    B  = 2*np.pi*(n - 1) / 365.0
    decl = (0.006918 - 0.399912*np.cos(B) + 0.070257*np.sin(B)
            - 0.006758*np.cos(2*B) + 0.000907*np.sin(2*B)
            - 0.002697*np.cos(3*B) + 0.001480*np.sin(3*B))
    hours  = dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600
    sub_lon = -15.0 * (hours - 12.0)
    return math.degrees(decl), sub_lon


def _to_unit(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return np.array([math.cos(la)*math.cos(lo),
                     math.cos(la)*math.sin(lo),
                     math.sin(la)])


def great_circle_mid(lat1, lon1, lat2, lon2):
    """Midpoint of the great circle between two ground points."""
    a, b = _to_unit(lat1, lon1), _to_unit(lat2, lon2)
    s = a + b
    s /= np.linalg.norm(s)
    return math.degrees(math.asin(s[2])), math.degrees(math.atan2(s[1], s[0]))


def solar_zenith(lat, lon, sub_lat, sub_lon):
    """Angle between local zenith and the Sun direction, in degrees."""
    cos_z = (math.sin(math.radians(lat)) * math.sin(math.radians(sub_lat))
             + math.cos(math.radians(lat)) * math.cos(math.radians(sub_lat))
             * math.cos(math.radians(lon - sub_lon)))
    return math.degrees(math.acos(np.clip(cos_z, -1, 1)))


# ---------- Sky-context inset (no external libs) ----------

def sky_inset(ax, dt_utc, sub_lat, sub_lon, rx_lat, rx_lon):
    """Draw an all-sky 'where was the Sun' mini-map in the corner."""
    ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05)
    ax.set_aspect('equal'); ax.axis('off')
    ax.add_patch(Circle((0, 0), 1.0, fc='#101820', ec='#444', lw=0.6))
    ax.add_patch(Circle((0, 0), 0.33, fc='none', ec='#333', lw=0.4))
    ax.add_patch(Circle((0, 0), 0.66, fc='none', ec='#333', lw=0.4))
    # cardinal ticks
    for lab, (x, y) in {'N': (0, 1.03), 'E': (1.03, 0), 'S': (0, -1.03), 'W': (-1.03, 0)}.items():
        ax.text(x, y, lab, color='#888', fontsize=6, ha='center', va='center')

    # Sun projected onto the sky dome from the receiver's viewpoint
    z  = solar_zenith(rx_lat, rx_lon, sub_lat, sub_lon)
    # approximate azimuth from great-circle bearing to subsolar point
    la1, lo1 = math.radians(rx_lat), math.radians(rx_lon)
    la2, lo2 = math.radians(sub_lat), math.radians(sub_lon)
    dlon = lo2 - lo1
    y = math.sin(dlon) * math.cos(la2)
    x = (math.cos(la1)*math.sin(la2)
         - math.sin(la1)*math.cos(la2)*math.cos(dlon))
    az = math.atan2(y, x)  # 0 = N, + = E

    r   = (90.0 - z) / 90.0            # 0 at zenith, 1 at horizon
    sun = (r * math.sin(az), r * math.cos(az))
    up  = z < 90.0
    ax.scatter(*sun, s=28, c='#ffcc33' if up else '#665522',
               edgecolors='none', zorder=3)
    # terminator shading across the dome (simple)
    theta0 = math.degrees(az)
    ax.add_patch(Wedge((0, 0), 1.0, theta0 + 90, theta0 + 270,
                       fc='#000', alpha=0.35, ec='none'))
    ax.set_title('sky @ rec.', fontsize=6, color='#888', pad=2)


# ---------- Renderer ----------

def render(path, mode):
    x, fs = load(path)
    t, df, snr = track(x, fs)
    good = snr > 10

    # solar context
    dt       = parse_utc(path)
    sub_lat, sub_lon = subsolar(dt)
    ref_lat, ref_lon = great_circle_mid(TX_LAT, TX_LON, RX_LAT, RX_LON)
    zen      = solar_zenith(ref_lat, ref_lon, sub_lat, sub_lon)

    plt.style.use('dark_background')
    fig = plt.figure(figsize=(6, 4.4), dpi=120)
    ax  = fig.add_axes([0.10, 0.12, 0.76, 0.76])

    if mode == 'Doppler' and good.any():
        d = df[good] - np.median(df[good])
        # color each point by solar zenith at the reflection midpoint over time
        cmap = plt.get_cmap('plasma')
        zens = []
        for tt in t[good]:
            dtt = dt.replace(microsecond=0)
            # small per-window subsolar drift (typically negligible, but cheap)
            sl, so = subsolar(dtt)
            zens.append(solar_zenith(ref_lat, ref_lon, sl, so))
        zens = np.array(zens)
        sc = ax.scatter(t[good]/60, d, c=zens, cmap=cmap, vmin=0, vmax=180,
                        s=10, edgecolors='none')
        ax.plot(t[good]/60, d, '-', color='#4fc3f7', lw=0.6, alpha=0.5)
        cb = fig.colorbar(sc, ax=ax, pad=0.01, fraction=0.04)
        cb.set_label('solar zenith @ reflection (°)', fontsize=7, color='#bbb')
        cb.ax.tick_params(labelsize=6, colors='#bbb')
        ax.set_ylabel('Doppler change (Hz)')
        ax.set_xlabel('minutes')
    elif mode == 'Spectrogram':
        ax.specgram(x, NFFT=4096, Fs=fs, noverlap=2048, cmap='magma')
        ax.set_ylim(F0 - SEARCH, F0 + SEARCH)
        ax.set_ylabel('Hz'); ax.set_xlabel('seconds')
    else:
        ax.plot(t/60, snr, color='#aed581', lw=0.8)
        ax.axhline(10, ls='--', color='gray', lw=0.6)
        ax.set_ylabel('SNR (dB)'); ax.set_xlabel('minutes')

    ax.set_title(f'{os.path.basename(path)} — {mode}', fontsize=9, color='#ddd')

    # sky inset
    inset_ax = fig.add_axes([0.87, 0.62, 0.12, 0.28])
    sky_inset(inset_ax, dt, sub_lat, sub_lon, RX_LAT, RX_LON)

    fig.tight_layout(rect=[0, 0, 0.86, 1])

    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=fig.get_facecolor())
    plt.close(fig)

    if good.any():
        stats = (f'{len(x)/fs:.0f} s | std {df[good].std():.3f} Hz | '
                 f'{good.sum()}/{len(good)} good | '
                 f'☉ {sub_lat:+.1f}°, {sub_lon:+.1f}° | '
                 f'z@mid {zen:.0f}°')
    else:
        stats = 'no clean windows'
    return ui.Image.from_data(buf.getvalue()), stats


# ---------- UI ----------

class App(ui.View):
    def __init__(self):
        self.name = 'WWV Doppler'
        self.background_color = '#111'
        self.files = sorted(glob.glob(os.path.join(DIR, 'wwv10*.wav')),
                            reverse=True)
        self.mode = ui.SegmentedControl(segments=MODES, selected_index=0,
                                        action=self.redraw)
        self.img  = ui.ImageView(content_mode=ui.CONTENT_SCALE_ASPECT_FIT)
        self.info = ui.Label(text_color='#ccc', font=('Menlo', 11),
                             alignment=ui.ALIGN_CENTER, number_of_lines=2)
        ds = ui.ListDataSource([os.path.basename(f) for f in self.files])
        ds.action = self.pick; ds.text_color = '#ddd'
        self.table = ui.TableView(data_source=ds, delegate=ds,
                                  background_color='#1a1a1a', row_height=34)
        for v in (self.mode, self.img, self.info, self.table):
            self.add_subview(v)
        self.sel = self.files[0] if self.files else None
        if self.sel:
            self.redraw(None)
        else:
            self.info.text = 'no wwv10*.wav in ' + DIR

    def layout(self):
        w, h, p = self.width, self.height, 8
        self.mode.frame  = (p, p, w - 2*p, 32)
        self.img.frame   = (0, 48, w, h*0.5)
        self.info.frame  = (0, 48 + h*0.5, w, 34)
        self.table.frame = (0, 82 + h*0.5, w, h - (82 + h*0.5))

    def pick(self, ds):
        self.sel = self.files[ds.selected_row]
        self.redraw(None)

    @ui.in_background
    def redraw(self, sender):
        if not self.sel:
            return
        self.info.text = 'rendering...'
        try:
            img, stats = render(self.sel, MODES[self.mode.selected_index])
            self.img.image, self.info.text = img, stats
        except Exception as e:
            self.info.text = f'error: {e}'


App().present('fullscreen')
