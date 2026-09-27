#!/usr/bin/env python3
"""Build speech-synced animated frames for InvoiceBot promo video v2.
Every visual element is timed to word-level Scribe timestamps."""
import os, math
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FPS = 30
TOTAL_DURATION = 34.0
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)
OUT = "/home/user/B00K/promo/edit/frames"
os.makedirs(OUT, exist_ok=True)

# Colors — InvoiceBot brand
BG       = (10, 10, 11)
ACCENT   = (99, 102, 241)
GREEN    = (34, 197, 94)
YELLOW   = (234, 179, 8)
RED      = (239, 68, 68)
WHITE    = (255, 255, 255)
DIM      = (100, 100, 110)
CARD_BG  = (20, 20, 24)
CARD_HI  = (28, 28, 34)

# Fonts
def load_font(size, bold=False):
    base = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    p = f"/usr/share/fonts/truetype/dejavu/{base}"
    if os.path.exists(p):
        return ImageFont.truetype(p, size)
    return ImageFont.load_default()

F96  = load_font(96, True)
F72  = load_font(72, True)
F60  = load_font(60, True)
F48  = load_font(48, True)
F40  = load_font(40, True)
F36  = load_font(36, False)
F32  = load_font(32, True)
F28  = load_font(28, False)
F24  = load_font(24, False)
F20  = load_font(20, False)

# Easing
def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3

def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    if t < 0.5: return 4 * t * t * t
    return 1 - (-2 * t + 2) ** 3 / 2

def ease_out_back(t):
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

def lerp(a, b, t):
    return a + (b - a) * t

def color_lerp(c, alpha):
    alpha = max(0.0, min(1.0, alpha))
    return tuple(int(v * alpha) for v in c)

def text_w(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]

def text_h(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]

def draw_centered(draw, y, text, font, fill):
    tw = text_w(draw, text, font)
    draw.text(((W - tw) // 2, y), text, font=font, fill=fill)

def rounded_rect(draw, xy, fill, r=16):
    draw.rounded_rectangle(xy, radius=r, fill=fill)

def rounded_rect_outline(draw, xy, outline, width=2, r=16):
    draw.rounded_rectangle(xy, radius=r, outline=outline, width=width)

# Scene timeline synced to Scribe word timestamps
# SCENE 1: Hook — 0.0 to 6.0s
# "Every invoicing tool is either too complex, too expensive, or too locked in."
# "too complex" lands at 2.28-3.00
# "too expensive" lands at 3.34-4.08
# "too locked in" lands at 4.90-5.60

# SCENE 2: Brand reveal — 6.0 to 8.3s
# "InvoiceBot is none of that."

# SCENE 3: Stats — 8.3 to 13.1s
# "Zero dependencies." 8.28-9.38
# "Zero build step." 9.88-10.94
# "One command and you're live." 11.40-13.10

# SCENE 4: Features — 13.5 to 19.7s
# "Create an invoice in thirty seconds." 13.52-15.86
# "Track revenue at a glance." 16.28-17.72
# "Let clients pay with Stripe." 18.16-19.72

# SCENE 5: Deploy + simplicity — 20.2 to 26.8s
# "Self-host it. Own your data. Deploy anywhere." 20.18-22.54
# "The entire app is four files..." 23.00-26.84

# SCENE 6: Pricing + CTA — 27.3 to 33.6s
# "Open source." 27.34-28.00
# "Free to start." 28.54-29.24
# "Pro at nineteen a month." 29.64-31.04
# "Get paid faster. InvoiceBot." 31.50-33.60

def progress(t, start, end):
    """0..1 progress of t within [start, end]"""
    if t < start: return 0.0
    if t >= end: return 1.0
    return (t - start) / (end - start)

def appear(t, trigger, dur=0.35):
    """Ease-out alpha for element appearing at trigger time"""
    return ease_out_cubic(progress(t, trigger, trigger + dur))

def slide_up(t, trigger, dur=0.4, dist=50):
    """Returns y-offset that goes from dist to 0"""
    p = ease_out_cubic(progress(t, trigger, trigger + dur))
    return int((1 - p) * dist)

# Subtle animated gradient line at bottom
def draw_accent_bar(draw, t):
    bar_y = H - 4
    phase = (t * 0.3) % 1.0
    for x in range(W):
        frac = x / W
        intensity = 0.3 + 0.7 * max(0, 1 - abs(frac - phase) * 4)
        c = color_lerp(ACCENT, intensity * 0.6)
        draw.line([(x, bar_y), (x, H)], fill=c)

# ============================================================
# RENDER ALL FRAMES
# ============================================================
for frame_i in range(TOTAL_FRAMES):
    t = frame_i / FPS
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Subtle bottom accent bar on every frame
    draw_accent_bar(draw, t)

    # ---- SCENE 1: HOOK (0.0 - 5.8s) ----
    if t < 6.0:
        # Title line fades in 0.0-0.5
        a_title = appear(t, 0.0, 0.4)
        draw_centered(draw, 200, "Every invoicing tool is...", F48, color_lerp(DIM, a_title))

        # Three pain points appear synced to speech, with strikethrough
        pains = [
            ("Too Complex",   RED,    2.28, 3.00),   # word start, word end
            ("Too Expensive",  YELLOW, 3.34, 4.08),
            ("Too Locked In",  RED,    4.90, 5.60),
        ]
        for i, (label, color, w_start, w_end) in enumerate(pains):
            y_base = 360 + i * 120
            a = appear(t, w_start - 0.1, 0.3)
            dy = slide_up(t, w_start - 0.1, 0.35, 40)

            # Text
            tw = text_w(draw, label, F72)
            x = (W - tw) // 2
            draw.text((x, y_base + dy), label, font=F72, fill=color_lerp(color, a))

            # Strikethrough wipes across after word ends
            strike_start = w_end + 0.15
            strike_prog = ease_out_cubic(progress(t, strike_start, strike_start + 0.25))
            if strike_prog > 0:
                sw = int(tw * strike_prog)
                sy = y_base + dy + 42
                draw.line([(x, sy), (x + sw, sy)], fill=color_lerp(color, a * 0.9), width=5)

        # Fade out the whole scene
        if t > 5.5:
            fade = 1.0 - progress(t, 5.5, 6.0)
            overlay = Image.new("RGB", (W, H), BG)
            img = Image.blend(img, overlay, 1.0 - fade)
            draw = ImageDraw.Draw(img)
            draw_accent_bar(draw, t)

    # ---- SCENE 2: BRAND REVEAL (6.0 - 8.3s) ----
    elif t < 8.3:
        st = t - 6.0

        # "InvoiceBot" big reveal — scale/pop effect
        a_brand = appear(t, 6.0, 0.5)
        pop = ease_out_back(progress(t, 6.0, 6.7))

        brand_text = "InvoiceBot"
        # Use pop for a slight overshoot feel via y offset
        y_offset = int((1 - pop) * 30)
        draw_centered(draw, 340 + y_offset, brand_text, F96, color_lerp(ACCENT, a_brand))

        # "is none of that." subtitle
        a_sub = appear(t, 6.9, 0.4)
        dy_sub = slide_up(t, 6.9, 0.4, 25)
        draw_centered(draw, 470 + dy_sub, "is none of that.", F40, color_lerp(WHITE, a_sub * 0.8))

        # Decorative line under brand
        line_prog = ease_out_cubic(progress(t, 6.3, 7.0))
        if line_prog > 0:
            lw = int(300 * line_prog)
            cx = W // 2
            draw.line([(cx - lw, 445), (cx + lw, 445)], fill=color_lerp(ACCENT, 0.5), width=2)

        # Fade out
        if t > 7.8:
            fade = 1.0 - progress(t, 7.8, 8.3)
            overlay = Image.new("RGB", (W, H), BG)
            img = Image.blend(img, overlay, 1.0 - fade)
            draw = ImageDraw.Draw(img)
            draw_accent_bar(draw, t)

    # ---- SCENE 3: STATS (8.3 - 13.1s) ----
    elif t < 13.5:
        # "Zero dependencies." 8.28-9.38
        # "Zero build step." 9.88-10.94
        # "One command and you're live." 11.40-13.10

        stats = [
            ("0",   "Dependencies",  8.28,  ACCENT),
            ("0",   "Build Steps",   9.88,  ACCENT),
            ("1",   "Command",       11.40, GREEN),
            ("30s", "First Invoice",  12.3, GREEN),
        ]

        # Scene title
        a_t = appear(t, 8.3, 0.3)
        draw_centered(draw, 80, "Built Different", F48, color_lerp(WHITE, a_t))

        card_w, card_h = 360, 220
        gap = 40
        total = len(stats) * card_w + (len(stats) - 1) * gap
        sx = (W - total) // 2

        for i, (num, label, trigger, color) in enumerate(stats):
            a = appear(t, trigger, 0.4)
            dy = slide_up(t, trigger, 0.45, 45)
            cx = sx + i * (card_w + gap)
            cy = 240 + dy

            # Card background
            rounded_rect(draw, (cx, cy, cx + card_w, cy + card_h), color_lerp(CARD_BG, a), r=18)

            # Number — big and colored
            nw = text_w(draw, num, F72)
            draw.text((cx + (card_w - nw) // 2, cy + 30), num, font=F72, fill=color_lerp(color, a))

            # Label
            lw = text_w(draw, label, F28)
            draw.text((cx + (card_w - lw) // 2, cy + 140), label, font=F28, fill=color_lerp(DIM, a))

        # Bottom tagline synced to "One command and you're live" at 11.40
        a_cmd = appear(t, 11.4, 0.4)
        dy_cmd = slide_up(t, 11.4, 0.4, 30)
        draw_centered(draw, 560 + dy_cmd, 'node server.js', F48, color_lerp(GREEN, a_cmd))
        a_arr = appear(t, 12.3, 0.3)
        draw_centered(draw, 640 + slide_up(t, 12.3, 0.3, 20), '→ localhost:3000', F36, color_lerp(DIM, a_arr))

        # Fade out
        if t > 13.0:
            fade = 1.0 - progress(t, 13.0, 13.5)
            overlay = Image.new("RGB", (W, H), BG)
            img = Image.blend(img, overlay, 1.0 - fade)
            draw = ImageDraw.Draw(img)
            draw_accent_bar(draw, t)

    # ---- SCENE 4: FEATURES (13.5 - 20.0s) ----
    elif t < 20.2:
        # "Create an invoice in thirty seconds." 13.52-15.86
        # "Track revenue at a glance." 16.28-17.72
        # "Let clients pay with Stripe." 18.16-19.72

        features = [
            ("Create Invoices",  "30 seconds flat",       13.52, "⚡"),
            ("Dashboard",        "Revenue at a glance",    16.28, "📊"),
            ("Stripe Payments",  "Clients pay online",     18.16, "💳"),
        ]

        # Each feature gets a full-width card that slides in on its speech cue
        for i, (title, desc, trigger, icon) in enumerate(features):
            a = appear(t, trigger, 0.45)
            dy = slide_up(t, trigger, 0.5, 60)

            card_x = 280
            card_y = 180 + i * 220 + dy
            card_w = W - 560
            card_h = 180

            # Card
            rounded_rect(draw, (card_x, card_y, card_x + card_w, card_y + card_h),
                        color_lerp(CARD_BG, a), r=16)

            # Accent bar left
            draw.rounded_rectangle((card_x, card_y, card_x + 5, card_y + card_h),
                                   radius=2, fill=color_lerp(ACCENT, a))

            # Title
            draw.text((card_x + 40, card_y + 35), title, font=F48,
                      fill=color_lerp(WHITE, a))

            # Description
            draw.text((card_x + 40, card_y + 105), desc, font=F28,
                      fill=color_lerp(DIM, a))

            # Right side accent dot
            dot_x = card_x + card_w - 60
            dot_y = card_y + card_h // 2
            dot_r = 20
            draw.ellipse((dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r),
                         fill=color_lerp(ACCENT, a * 0.3))

        # "What You Get" title
        a_title = appear(t, 13.5, 0.3)
        draw_centered(draw, 80, "What You Get", F48, color_lerp(ACCENT, a_title))

        # Fade out
        if t > 19.7:
            fade = 1.0 - progress(t, 19.7, 20.2)
            overlay = Image.new("RGB", (W, H), BG)
            img = Image.blend(img, overlay, 1.0 - fade)
            draw = ImageDraw.Draw(img)
            draw_accent_bar(draw, t)

    # ---- SCENE 5: DEPLOY + SIMPLICITY (20.2 - 27.0s) ----
    elif t < 27.3:
        # "Self-host it." 20.18-20.88
        # "Own your data." 21.08-21.60
        # "Deploy anywhere." 21.82-22.54
        # "The entire app is four files..." 23.00-26.84

        # Terminal window
        term_x, term_y = 260, 120
        term_w, term_h = 1400, 380

        a_term = appear(t, 20.2, 0.4)
        rounded_rect(draw, (term_x, term_y, term_x + term_w, term_y + term_h),
                     color_lerp((16, 16, 20), a_term), r=14)

        # Window chrome
        for di, dc in enumerate([RED, YELLOW, GREEN]):
            draw.ellipse((term_x + 20 + di * 24, term_y + 14,
                          term_x + 34 + di * 24, term_y + 28),
                         fill=color_lerp(dc, a_term * 0.8))

        # Terminal commands synced to speech
        cmds = [
            ("$ docker build -t invoicebot .",       20.18, GREEN),
            ("$ docker run -p 3000:3000 invoicebot", 21.08, GREEN),
            ("InvoiceBot running → localhost:3000",  21.82, ACCENT),
        ]
        for i, (cmd, trigger, color) in enumerate(cmds):
            if t >= trigger:
                type_dur = 0.7
                type_prog = ease_out_cubic(progress(t, trigger, trigger + type_dur))
                chars = int(len(cmd) * type_prog)
                shown = cmd[:chars]
                y = term_y + 60 + i * 55
                draw.text((term_x + 25, y), shown, font=F32, fill=color_lerp(color, a_term))

                # Cursor
                if type_prog < 1.0:
                    cx = term_x + 25 + text_w(draw, shown, F32) + 2
                    if int(t * 4) % 2 == 0:
                        draw.rectangle((cx, y, cx + 14, y + 32), fill=color_lerp(ACCENT, a_term))

        # Deploy platforms appear below terminal
        platforms = [
            ("Docker",  21.82),
            ("Railway", 22.0),
            ("Render",  22.2),
            ("Fly.io",  22.4),
        ]
        pill_y = term_y + term_h + 30
        pill_w = 180
        pill_h = 50
        pill_gap = 30
        total_pw = len(platforms) * pill_w + (len(platforms) - 1) * pill_gap
        psx = (W - total_pw) // 2

        for i, (name, trigger) in enumerate(platforms):
            a = appear(t, trigger, 0.3)
            px = psx + i * (pill_w + pill_gap)
            rounded_rect(draw, (px, pill_y, px + pill_w, pill_y + pill_h),
                         color_lerp(CARD_BG, a), r=25)
            rounded_rect_outline(draw, (px, pill_y, px + pill_w, pill_y + pill_h),
                                  color_lerp(ACCENT, a * 0.4), width=1, r=25)
            nw = text_w(draw, name, F24)
            draw.text((px + (pill_w - nw) // 2, pill_y + 12), name, font=F24,
                      fill=color_lerp(WHITE, a))

        # "The entire app is four files" — big reveal at 23.0
        a_files = appear(t, 23.0, 0.5)
        dy_files = slide_up(t, 23.0, 0.5, 35)
        draw_centered(draw, 620 + dy_files, "The entire app is 4 files.", F60,
                      color_lerp(WHITE, a_files))

        a_jr = appear(t, 24.5, 0.4)
        dy_jr = slide_up(t, 24.5, 0.4, 25)
        draw_centered(draw, 710 + dy_jr, "A junior dev can read it in an afternoon.", F36,
                      color_lerp(DIM, a_jr))

        # Fade out
        if t > 26.8:
            fade = 1.0 - progress(t, 26.8, 27.3)
            overlay = Image.new("RGB", (W, H), BG)
            img = Image.blend(img, overlay, 1.0 - fade)
            draw = ImageDraw.Draw(img)
            draw_accent_bar(draw, t)

    # ---- SCENE 6: PRICING + CTA (27.3 - 34.0s) ----
    else:
        # "Open source." 27.34-28.00
        # "Free to start." 28.54-29.24
        # "Pro at nineteen a month." 29.64-31.04
        # "Get paid faster. InvoiceBot." 31.50-33.60

        # Three pricing pills appear in sync
        plans = [
            ("Free",    "Open Source",  27.34, DIM),
            ("$0",      "Starter",      28.54, WHITE),
            ("$19/mo",  "Pro",          29.64, ACCENT),
        ]
        pill_w, pill_h = 340, 160
        gap = 50
        total_pw = len(plans) * pill_w + (len(plans) - 1) * gap
        psx = (W - total_pw) // 2

        for i, (price, name, trigger, color) in enumerate(plans):
            a = appear(t, trigger, 0.4)
            dy = slide_up(t, trigger, 0.45, 40)
            px = psx + i * (pill_w + gap)
            py = 180 + dy

            rounded_rect(draw, (px, py, px + pill_w, py + pill_h),
                         color_lerp(CARD_BG, a), r=18)

            # Highlight border for Pro
            if i == 2:
                rounded_rect_outline(draw, (px - 2, py - 2, px + pill_w + 2, py + pill_h + 2),
                                      color_lerp(ACCENT, a), width=3, r=20)

            # Price
            pw = text_w(draw, price, F48)
            draw.text((px + (pill_w - pw) // 2, py + 25), price, font=F48,
                      fill=color_lerp(color, a))

            # Name
            nw = text_w(draw, name, F28)
            draw.text((px + (pill_w - nw) // 2, py + 100), name, font=F28,
                      fill=color_lerp(DIM, a))

        # "Get paid faster." — the big CTA at 31.50
        a_cta = appear(t, 31.5, 0.4)
        dy_cta = slide_up(t, 31.5, 0.45, 35)
        draw_centered(draw, 430 + dy_cta, "Get Paid Faster.", F72, color_lerp(WHITE, a_cta))

        # "InvoiceBot" final brand at 32.9
        a_brand = appear(t, 32.9, 0.4)
        dy_brand = slide_up(t, 32.9, 0.4, 25)
        draw_centered(draw, 550 + dy_brand, "InvoiceBot", F60, color_lerp(ACCENT, a_brand))

        # CTA button
        a_btn = appear(t, 32.0, 0.4)
        btn_w, btn_h = 420, 70
        bx = (W - btn_w) // 2
        by = 680
        rounded_rect(draw, (bx, by, bx + btn_w, by + btn_h),
                     color_lerp(ACCENT, a_btn), r=35)
        btn_text = "Star on GitHub"
        btw = text_w(draw, btn_text, F32)
        draw.text(((W - btw) // 2, by + 16), btn_text, font=F32,
                  fill=color_lerp(WHITE, a_btn))

        # GitHub URL
        a_url = appear(t, 32.5, 0.3)
        draw_centered(draw, 790, "github.com/abuadamalmaliki-prog/B00K", F24,
                      color_lerp(DIM, a_url))

    img.save(os.path.join(OUT, f"frame_{frame_i:05d}.png"))

print(f"Generated {TOTAL_FRAMES} frames at {FPS}fps = {TOTAL_FRAMES/FPS:.1f}s — speech-synced")
