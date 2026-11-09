# wwv_catalog.py - metadata cache for WWV recordings
import os, re, glob, wave, hashlib
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
import numpy as np

# --- reuse the geometry from wwv_ui, or import it ---
try:
    from wwv_ui import (F0, WIN, SEARCH, TX_LAT, TX_LON, RX_LAT, RX_LON,
                        load, track, parse_utc, subsolar,
                        great_circle_mid, solar_zenith)
except ImportError:
    raise SystemExit('place wwv_catalog.py next to wwv_ui.py')


CACHE_DIR = os.path.expanduser('~/Documents/kiwiclient/.cache')
os.makedirs(CACHE_DIR, exist_ok=True)


@dataclass
class Rec:
    path:      str
    mtime:     float
    dt_utc:    str           # ISO
    dur_s:     float
    fs:        int
    kind:      str = 'carrier'   # 'carrier' | 'wwv_tick' | 'reference' | 'other'
    sub_lat:   float = 0.0
    sub_lon:   float = 0.0
    mid_lat:   float = 0.0
    mid_lon:   float = 0.0
    zen_mid:   float = 0.0         # solar zenith at midpoint at start
    season:    str = 'other'      # 'equinox' | 'solstice' | 'other'
    n_windows: int = 0
    n_good:    int = 0
    std_df:    float = float('nan')  # Hz, over good windows
    median_snr: float = float('nan')
    t:         np.ndarray = field(repr=False, default=None)
    df:        np.ndarray = field(repr=False, default=None)
    snr:       np.ndarray = field(repr=False, default=None)


def _season(dt):
    """Crude season tag by solar declination."""
    lat, _ = subsolar(dt)
    if abs(lat) < 8:   return 'equinox'
    if abs(lat) > 20:  return 'solstice'
    return 'other'


def classify(x, fs):
    """Rough classifier. carrier = continuous tone suitable for Doppler."""
    N = min(len(x), int(5 * fs))
    if N < 1024:
        return 'other'
    P = np.abs(np.fft.rfft(x[:N] * np.hanning(N)))**2
    f = np.fft.rfftfreq(N, 1/fs)

    def band_power(lo, hi):
        m = (f >= lo) & (f <= hi)
        return float(P[m].sum()) if m.any() else 0.0

    total = P.sum() + 1e-12
    p_500  = band_power(450,  550)
    p_1000 = band_power(950, 1050)

    # both tones present → classic WWV tick-and-tone
    if p_500 / total > 0.05 and p_1000 / total > 0.2:
        return 'wwv_tick'
    if p_1000 / total > 0.4:
        # mostly continuous 1000 Hz — treat as carrier unless filename says otherwise
        return 'carrier'
    return 'other'


def _cache_path(src):
    h = hashlib.sha1(os.path.basename(src).encode()).hexdigest()[:12]
    return os.path.join(CACHE_DIR, f'{h}.npz')


def _build(src):
    x, fs = load(src)
    t, df, snr = track(x, fs)
    dt = parse_utc(src)
    sub_lat, sub_lon = subsolar(dt)
    mid_lat, mid_lon = great_circle_mid(TX_LAT, TX_LON, RX_LAT, RX_LON)
    zen = solar_zenith(mid_lat, mid_lon, sub_lat, sub_lon)
    good = snr > 10
    kind = classify(x, fs)

    rec = Rec(
        path=src, mtime=os.path.getmtime(src),
        dt_utc=dt.isoformat(),
        dur_s=len(x)/fs, fs=fs,
        kind=kind,
        sub_lat=sub_lat, sub_lon=sub_lon,
        mid_lat=mid_lat, mid_lon=mid_lon,
        zen_mid=zen, season=_season(dt),
        n_windows=int(len(snr)), n_good=int(good.sum()),
        std_df=float(df[good].std()) if good.any() else float('nan'),
        median_snr=float(np.median(snr)) if len(snr) else float('nan'),
        t=t, df=df, snr=snr,
    )
    # persist scalars + arrays
    scalar = {k: v for k, v in asdict(rec).items()
              if k not in ('t', 'df', 'snr')}
    np.savez_compressed(_cache_path(src),
                        **{k: np.array(v) for k, v in scalar.items()},
                        t=t, df=df, snr=snr)
    return rec


def _load_cached(src):
    p = _cache_path(src)
    if not os.path.exists(p):
        return None
    z = np.load(p, allow_pickle=False)
    rec = Rec(
        path=str(z['path']), mtime=float(z['mtime']),
        dt_utc=str(z['dt_utc']), dur_s=float(z['dur_s']), fs=int(z['fs']),
        kind=str(z['kind']) if 'kind' in z else 'carrier',
        sub_lat=float(z['sub_lat']), sub_lon=float(z['sub_lon']),
        mid_lat=float(z['mid_lat']), mid_lon=float(z['mid_lon']),
        zen_mid=float(z['zen_mid']), season=str(z['season']),
        n_windows=int(z['n_windows']), n_good=int(z['n_good']),
        std_df=float(z['std_df']), median_snr=float(z['median_snr']),
        t=z['t'], df=z['df'], snr=z['snr'],
    )
    return rec


def get(src, force=False):
    """Return cached Rec if mtime matches, else rebuild."""
    p = _cache_path(src)
    if not force and os.path.exists(p):
        try:
            rec = _load_cached(src)
            if rec and abs(rec.mtime - os.path.getmtime(src)) < 1.0:
                return rec
        except Exception:
            pass
    return _build(src)


def scan(pattern='wwv10*.wav'):
    """Build/refresh the catalog. Returns list[Rec] sorted by time."""
    files = sorted(glob.glob(os.path.join(
        os.path.expanduser('~/Documents/kiwiclient'), pattern)))
    out = []
    for i, f in enumerate(files):
        try:
            out.append(get(f))
            print(f'[{i+1}/{len(files)}] {os.path.basename(f)}')
        except Exception as e:
            print(f'skip {os.path.basename(f)}: {e}')
    out.sort(key=lambda r: r.dt_utc)
    return out


def save_manifest(recs, path=None):
    path = path or os.path.join(CACHE_DIR, 'manifest.json')
    import json
    rows = [{k: (v if not isinstance(v, float) or np.isfinite(v) else None)
             for k, v in asdict(r).items() if k not in ('t', 'df', 'snr')}
            for r in recs]
    with open(path, 'w') as f:
        json.dump(rows, f, indent=2)
    return path
