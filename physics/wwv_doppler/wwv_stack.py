# wwv_stack.py - terminator-aligned stacking ("deep field")
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone

from wwv_ui import subsolar, solar_zenith, great_circle_mid, TX_LAT, TX_LON, RX_LAT, RX_LON
from wwv_catalog import scan, Rec


def terminator_crossing(rec: Rec, threshold=90.0, sunrise=True):
    """
    Return time (s, in rec's t-array) of first terminator crossing.
    sunrise=True  -> find z going *below* threshold (Sun coming up)
    sunrise=False -> find z going *above* threshold (Sun going down)
    """
    if rec.t is None or len(rec.t) == 0:
        return None
    dt0 = datetime.fromisoformat(rec.dt_utc)
    mid_lat, mid_lon = rec.mid_lat, rec.mid_lon

    zens = np.empty_like(rec.t)
    for i, tt in enumerate(rec.t):
        sl, so = subsolar(dt0 + timedelta(seconds=float(tt)))
        zens[i] = solar_zenith(mid_lat, mid_lon, sl, so)

    delta = zens - threshold
    sign  = np.sign(delta)
    changes = np.where(np.diff(sign) != 0)[0]
    if len(changes) == 0:
        return None

    for i in changes:
        going_up = delta[i] < 0 and delta[i+1] >= 0   # z increasing -> sun setting
        if sunrise and not going_up:
            # sub-sample via linear interp for a cleaner t0
            t0 = rec.t[i] + (rec.t[i+1] - rec.t[i]) * (-delta[i])/(delta[i+1]-delta[i])
            return float(t0)
        if (not sunrise) and going_up:
            t0 = rec.t[i] + (rec.t[i+1] - rec.t[i]) * (-delta[i])/(delta[i+1]-delta[i])
            return float(t0)
    return None


def align_on_terminator(recs, sunrise=True, threshold=90.0,
                        min_good=0.3, win_min=(-30, +30)):
    """
    Returns list of (phase_minutes, df_detrended, zen_mid, dt_iso) for each
    successfully aligned recording. df is centered so 0 = quiet baseline.
    """
    lo, hi = win_min
    out = []
    for rec in recs:
        t0 = terminator_crossing(rec, threshold, sunrise=sunrise)
        if t0 is None:
            continue
        good = rec.snr > 10
        if not good.any() or good.mean() < min_good:
            continue
        phase = (rec.t - t0) / 60.0
        keep  = (phase >= lo) & (phase <= hi) & good
        if keep.sum() < 5:
            continue
        # detrend: subtract a robust baseline from the *whole* trace's quiet
        # windows, so df values across recordings are comparable.
        quiet = good & (np.abs(rec.df - np.median(rec.df[good])) <
                        3 * np.nanstd(rec.df[good]))
        baseline = np.median(rec.df[quiet]) if quiet.any() else np.median(rec.df[good])
        out.append((phase[keep], (rec.df[keep] - baseline),
                    rec.zen_mid, rec.dt_utc))
    return out


def stack_plot(aligned, out_png, sunrise=True, threshold=90.0,
               bin_width=1.0):
    """Bin by phase (minutes), draw every trace + binned median ± IQR."""
    if not aligned:
        raise ValueError('no recordings aligned on terminator')

    phase_all = np.concatenate([a[0] for a in aligned])
    df_all    = np.concatenate([a[1] for a in aligned])
    lo, hi    = phase_all.min(), phase_all.max()
    bins      = np.arange(np.floor(lo), np.ceil(hi) + bin_width, bin_width)
    centers   = 0.5*(bins[:-1] + bins[1:])

    med = np.full_like(centers, np.nan)
    q25 = np.full_like(centers, np.nan)
    q75 = np.full_like(centers, np.nan)
    for i in range(len(centers)):
        m = (phase_all >= bins[i]) & (phase_all < bins[i+1])
        if m.sum() >= 3:
            med[i] = np.median(df_all[m])
            q25[i] = np.quantile(df_all[m], 0.25)
            q75[i] = np.quantile(df_all[m], 0.75)

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=130)
    for phase, df, zen, _ in aligned:
        ax.plot(phase, df, color='#334', lw=0.5, alpha=0.5)
    ax.fill_between(centers, q25, q75, color='#4fc3f7', alpha=0.25,
                    label='IQR across recordings')
    ax.plot(centers, med, color='#4fc3f7', lw=1.6, label='median')
    ax.axvline(0, ls='--', color='#ffcc33', lw=0.8,
               label=f'z(mid) = {threshold:.0f}°')
    ax.set_xlabel('minutes from terminator at reflection midpoint')
    ax.set_ylabel('detrended Doppler (Hz)')
    direction = 'sunrise' if sunrise else 'sunset'
    ax.set_title(f'Terminator-aligned stack — {direction} '
                 f'({len(aligned)} recordings)', color='#ddd')
    ax.legend(fontsize=7, framealpha=0.15)
    ax.grid(True, alpha=0.15)
    fig.tight_layout()
    fig.savefig(out_png, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_png, len(aligned), centers, med


def catalog_digest(recs):
    """Quick sanity text: what's in the catalog?"""
    if not recs:
        return 'catalog empty'
    n = len(recs)
    seasons = {s: sum(1 for r in recs if r.season == s)
               for s in ('equinox', 'solstice', 'other')}
    return (f'{n} recs | dur {sum(r.dur_s for r in recs)/3600:.1f} h | '
            f'seasons {seasons} | '
            f'median good-frac {np.median([r.n_good/max(r.n_windows,1) for r in recs]):.2f}')
