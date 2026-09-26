#!/bin/sh
# Generates media/sample.mp4: a 6 s stand-in clip (Mandelbrot zoom + a soft chord).
# Replace it with your own footage and point Studio.setup({ footage }) at it.
cd "$(dirname "$0")" && mkdir -p media && ffmpeg -v error -y \
  -f lavfi -i "mandelbrot=s=960x540:r=30:start_scale=3:end_scale=0.02:end_pts=180,hue=H=t*0.6" \
  -f lavfi -i "aevalsrc='0.25*sin(2*PI*220*t)+0.2*sin(2*PI*277.18*t)+0.2*sin(2*PI*329.63*t)':d=6" \
  -t 6 -c:v libx264 -crf 26 -preset slow -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart media/sample.mp4
