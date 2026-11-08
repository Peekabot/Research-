# WWV Doppler (Pythonista)

Phone-side tools for recording and analyzing the WWV 10 MHz carrier via public KiwiSDR receivers.

## Pipeline

1. **iSH**: clone `jks-prv/kiwiclient`, tarball, serve over HTTP
2. **Pythonista**: pull tarball, run `kiwirecorder.py` (USB at 9999 kHz → ~1 kHz tone)
3. **Analysis**: `wwv_ui.py` — UI with Doppler / spectrogram / SNR views + solar context

## First result

30 s recording from Ohio Kiwi (`22511.proxy.kiwisdr.com`):

- mean Doppler +0.120 Hz
- std 0.008 Hz
- 5/5 windows >10 dB SNR

## Files

- `wwv_ui.py` — interactive UI (edit `RX_LAT`/`RX_LON` for your site)
