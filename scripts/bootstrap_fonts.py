"""Fetch the approved font assets into assets/fonts/. Font binaries are intentionally not committed."""
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/fonts'; OUT.mkdir(parents=True,exist_ok=True)
VAZIR_COMMIT='6e553e33489a8f9dfaccc76860a2e3f3c1e66de7'
PLEX_COMMIT='78cd4223d8de9fcb78cba84eadecb269c56093c5'
FILES={
 'Vazirmatn-Regular.ttf':f'https://raw.githubusercontent.com/rastikerdar/vazirmatn/{VAZIR_COMMIT}/fonts/ttf/Vazirmatn-Regular.ttf',
 'Vazirmatn-Medium.ttf':f'https://raw.githubusercontent.com/rastikerdar/vazirmatn/{VAZIR_COMMIT}/fonts/ttf/Vazirmatn-Medium.ttf',
 'Vazirmatn-Bold.ttf':f'https://raw.githubusercontent.com/rastikerdar/vazirmatn/{VAZIR_COMMIT}/fonts/ttf/Vazirmatn-Bold.ttf',
 'IBMPlexSans-Regular.ttf':f'https://raw.githubusercontent.com/IBM/plex/{PLEX_COMMIT}/packages/plex-sans/fonts/complete/ttf/IBMPlexSans-Regular.ttf',
 'IBMPlexSans-Bold.ttf':f'https://raw.githubusercontent.com/IBM/plex/{PLEX_COMMIT}/packages/plex-sans/fonts/complete/ttf/IBMPlexSans-Bold.ttf',
}
for name,url in FILES.items():
    dst=OUT/name
    if dst.exists():
        print('OK',name); continue
    print('GET',name)
    with urlopen(url,timeout=30) as r: data=r.read()
    if len(data)<50000: raise RuntimeError(f'Font download too small: {name}')
    dst.write_bytes(data)
print('Fonts ready:',OUT)
