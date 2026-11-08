# run_stack.py — build catalog, align, plot
import os, traceback
from wwv_catalog import scan, save_manifest
from wwv_stack import align_on_terminator, stack_plot, catalog_digest

OUT = os.path.expanduser('~/Documents/kiwiclient/stacks')
os.makedirs(OUT, exist_ok=True)

recs = scan()                       # builds/updates the cache
print(catalog_digest(recs))
save_manifest(recs)

for sunrise in (True, False):
    tag = 'sunrise' if sunrise else 'sunset'
    aligned = align_on_terminator(recs, sunrise=sunrise)
    if not aligned:
        print(f'no {tag} alignments'); continue
    try:
        png, n, _, _ = stack_plot(aligned, os.path.join(OUT, f'{tag}_stack.png'),
                                  sunrise=sunrise)
        print(f'{tag}: {n} traces -> {png}')
    except Exception as e:
        print(f'{tag} failed: {e}'); traceback.print_exc()
