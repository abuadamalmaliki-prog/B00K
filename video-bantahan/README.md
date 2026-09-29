# video-bantahan

Video bantahan vertikal 1080×1920 (TikTok), tanpa WebGL.

**Alur:** intro kaligrafi → judul → ucapan Ustadz → [kutipan pengkritik → bantahan] × 6 → penutup.

**Stack:** HTML/CSS/JS untuk semua visual · Three.js `CSS3DRenderer` (CSS 3D, bukan WebGL) untuk intro logo berlapis ·
Canvas 2D untuk latar dan partikel emas · Python (`build.py`) untuk timeline, ekstraksi frame, dan mixing audio ·
Playwright untuk menangkap frame · ffmpeg untuk encode.

Setiap frame adalah fungsi murni dari waktu (`window.frame(t)`), jadi hasilnya deterministik.

## Menjalankan

```bash
npm install
export FFMPEG=/path/ke/ffmpeg          # atau ffmpeg ada di PATH
python3 build.py prep                  # resolve timeline + ekstrak frame klip pengkritik
python3 build.py audio                 # nasyid (ducking) + suara klip -> work/mix.m4a
python3 build.py render                # 4 worker paralel -> work/out/*.jpg
python3 build.py encode out/final.mp4
# atau semuanya: python3 build.py all out/final.mp4
node src/render.mjs --still 72 work/cek.png   # satu frame untuk cek desain
```

## Mengubah isi

Semua naskah ada di `src/project.json`:
- `quote`: `clips` = rentang detik pada video sumber, `captions` = teks terverifikasi + rentang detik ucapan.
- `rebut`: `cards` (kartu kitab; bungkus bagian yang di-highlight dengan `<m>…</m>`, waktu sapuan di `marks`) dan `beats` (pernyataan tegas; `{g|emas}`, `{d|redup}`).
- Durasi adegan kutipan dihitung otomatis; adegan lain memakai `dur`.

Audio memakai dua sumber pada `sources` (video pengkritik dan nasyid). Nasyid dinormalisasi, di-loop dengan crossfade,
dan diturunkan ke ±11% selama klip pengkritik diputar.
