# WWV Doppler (Pythonista)

Phone-side tools for recording and analyzing the WWV 10 MHz carrier via public KiwiSDR receivers.

## Pipeline

1. **iSH**: clone `jks-prv/kiwiclient`, tarball, serve over HTTP
2. **Pythonista**: pull tarball, run `kiwirecorder.py` (USB at 9999 kHz → ~1 kHz tone)
3. **Analysis**: `wwv_ui.py` — UI with Doppler / spectrogram / SNR views + solar context
4. **Catalog + stack**: `run_stack.py` builds a metadata cache and terminator-aligned deep-field stacks

## Recording kinds

- `carrier` — continuous-tone KiwiSDR captures. These are the only files that enter the terminator stack.
- `wwv_tick` / `reference` — native WWV tick-and-tone format (5 ms pulses + 500/600 Hz tones). Useful for format checks and detector tests; **do not catalog as Doppler**.

`wwv10.wav` (12 kHz, 30 s, tick-and-tone) is a format-verification reference only. Three independent detectors failed to extract a clean 1.000 s tick train. 1000 Hz is gated-but-mostly-continuous at this sample rate; 500 Hz is present but ~30× weaker. Not a Doppler source.

## First carrier result

30 s recording from Ohio Kiwi (`22511.proxy.kiwisdr.com`):

- mean Doppler +0.120 Hz
- std 0.008 Hz
- 5/5 windows >10 dB SNR

## Files

- `wwv_ui.py` — interactive UI (edit `RX_LAT`/`RX_LON` for your site)
- `wwv_catalog.py` — metadata cache (`.npz` per recording, `manifest.json`); includes `kind`
- `wwv_stack.py` — terminator-aligned stacking (filters to `kind == 'carrier'`)
- `run_stack.py` — driver: scan → align sunrise/sunset → PNG stacks
