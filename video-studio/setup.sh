#!/bin/sh
# One-time setup on a fresh Linux machine or cloud session: ffmpeg, an Arabic
# font, Playwright, and (behind a TLS-inspecting proxy) trust for its CA so
# Chromium can load Google Fonts and CDN scripts such as Three.js.
set -e
cd "$(dirname "$0")"

need_apt=""
command -v ffmpeg >/dev/null 2>&1 || need_apt="$need_apt ffmpeg"
fc-list 2>/dev/null | grep -qi amiri || need_apt="$need_apt fonts-hosny-amiri"
command -v certutil >/dev/null 2>&1 || need_apt="$need_apt libnss3-tools"
if [ -n "$need_apt" ]; then
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $need_apt
fi

npm install --no-audit --no-fund

CA="${STUDIO_PROXY_CA:-/root/.ccr/agent-proxy-ca.crt}"
if [ -f "$CA" ]; then
  mkdir -p "$HOME/.pki/nssdb"
  [ -f "$HOME/.pki/nssdb/cert9.db" ] || certutil -N -d "sql:$HOME/.pki/nssdb" --empty-password
  certutil -L -d "sql:$HOME/.pki/nssdb" -n studio-proxy-ca >/dev/null 2>&1 ||
    certutil -A -d "sql:$HOME/.pki/nssdb" -n studio-proxy-ca -t "C,," -i "$CA"
fi

[ -f examples/footage-fx/media/sample.mp4 ] || ./examples/footage-fx/make-sample.sh
echo "video-studio ready: node render.mjs examples/three-scene/index.html"
