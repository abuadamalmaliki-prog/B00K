"""Inline the HarfBuzz scripts into the page: python3 build.py -> mihbara.html"""
import pathlib
d = pathlib.Path(__file__).parent
page = (d / 'studio.html').read_text()
page = page.replace('/*HB_JS*/', (d / 'hb.js').read_text()).replace('/*HBJS_JS*/', (d / 'hbjs.js').read_text())
(d / 'mihbara.html').write_text(page)
print('wrote mihbara.html', len(page) // 1024, 'KB')
