#!/usr/bin/env python3
"""Build animated PNG frames for InvoiceBot promo video."""
import os
import math

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FPS = 30
OUT = "/home/user/B00K/promo/edit/frames"
os.makedirs(OUT, exist_ok=True)

BG = (10, 10, 11)
ACCENT = (99, 102, 241)    # #6366f1 indigo
GREEN = (34, 197, 94)      # #22c55e
YELLOW = (234, 179, 8)
RED = (239, 68, 68)
WHITE = (255, 255, 255)
DIM = (120, 120, 130)
DARK_CARD = (22, 22, 26)

def find_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

font_big = find_font(72, bold=True)
font_med = find_font(48, bold=True)
font_sm = find_font(36)
font_xs = find_font(28)
font_tiny = find_font(22)

def ease_out_cubic(t):
    return 1 - (1 - t) ** 3

def ease_in_out_cubic(t):
    if t < 0.5:
        return 4 * t ** 3
    return 1 - (-2 * t + 2) ** 3 / 2

def draw_rounded_rect(draw, xy, fill, radius=20):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)

def text_center(draw, y, text, font, fill=WHITE):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, font=font, fill=fill)

def text_center_x(draw, y, text, font, fill=WHITE):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return tw

frame_num = 0

# === SCENE 1: HOOK (0-4s = 120 frames) ===
# "Every invoicing tool is either too complex, too expensive, or too locked in."
lines_hook = [
    ("Too Complex", RED),
    ("Too Expensive", YELLOW),
    ("Too Locked In", RED),
]
for f in range(120):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    t = f / FPS

    # Title fades in first 0.5s
    alpha_title = min(1.0, t / 0.5)
    title_y = 180
    col = tuple(int(c * ease_out_cubic(alpha_title)) for c in WHITE)
    text_center(draw, title_y, "Every invoicing tool is...", font_med, fill=col)

    # Each line appears staggered
    for i, (txt, color) in enumerate(lines_hook):
        appear_t = 1.0 + i * 0.8
        if t >= appear_t:
            prog = min(1.0, (t - appear_t) / 0.4)
            ep = ease_out_cubic(prog)
            y = 340 + i * 100
            x_offset = int((1 - ep) * 80)
            col = tuple(int(c * ep) for c in color)
            bbox = draw.textbbox((0, 0), txt, font=font_big)
            tw = bbox[2] - bbox[0]
            x = (W - tw) // 2 + x_offset
            draw.text((x, y), txt, font=font_big, fill=col)

            # Strikethrough after appearing
            if t >= appear_t + 0.5:
                strike_prog = min(1.0, (t - appear_t - 0.5) / 0.3)
                strike_w = int(tw * ease_out_cubic(strike_prog))
                ly = y + 45
                draw.line([(x, ly), (x + strike_w, ly)], fill=color, width=4)

    img.save(os.path.join(OUT, f"frame_{frame_num:05d}.png"))
    frame_num += 1

# === SCENE 2: SOLUTION (4-8s = 120 frames) ===
# "InvoiceBot is none of that. Zero dependencies. Zero build step."
stats = [
    ("0", "Dependencies"),
    ("0", "Build Steps"),
    ("4", "Files Total"),
    ("30s", "First Invoice"),
]
for f in range(120):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    t = f / FPS

    # Title
    alpha = min(1.0, t / 0.4)
    col = tuple(int(c * ease_out_cubic(alpha)) for c in WHITE)
    text_center(draw, 120, "InvoiceBot", font_big, fill=ACCENT if alpha > 0.9 else col)

    tagline_a = min(1.0, max(0, (t - 0.3) / 0.4))
    col2 = tuple(int(c * ease_out_cubic(tagline_a)) for c in DIM)
    text_center(draw, 210, "is none of that.", font_sm, fill=col2)

    # Stats cards
    card_w, card_h = 340, 200
    gap = 40
    total_w = 4 * card_w + 3 * gap
    start_x = (W - total_w) // 2
    for i, (num, label) in enumerate(stats):
        appear_t = 1.2 + i * 0.5
        if t >= appear_t:
            prog = min(1.0, (t - appear_t) / 0.5)
            ep = ease_out_cubic(prog)
            cx = start_x + i * (card_w + gap)
            cy = 380 + int((1 - ep) * 40)
            a = ep

            fill = tuple(int(c * a) for c in DARK_CARD)
            draw_rounded_rect(draw, (cx, cy, cx + card_w, cy + card_h), fill=fill, radius=16)

            num_col = tuple(int(c * a) for c in GREEN)
            bbox = draw.textbbox((0, 0), num, font=font_big)
            nw = bbox[2] - bbox[0]
            draw.text((cx + (card_w - nw) // 2, cy + 30), num, font=font_big, fill=num_col)

            lbl_col = tuple(int(c * a) for c in DIM)
            bbox2 = draw.textbbox((0, 0), label, font=font_xs)
            lw = bbox2[2] - bbox2[0]
            draw.text((cx + (card_w - lw) // 2, cy + 130), label, font=font_xs, fill=lbl_col)

    # Bottom tagline
    if t > 3.0:
        ba = min(1.0, (t - 3.0) / 0.5)
        col3 = tuple(int(c * ease_out_cubic(ba)) for c in WHITE)
        text_center(draw, 680, "One command and you're live.", font_med, fill=col3)

    img.save(os.path.join(OUT, f"frame_{frame_num:05d}.png"))
    frame_num += 1

# === SCENE 3: FEATURES (8-16s = 240 frames) ===
features = [
    ("Create invoices", "in 30 seconds", "lightning"),
    ("Dashboard", "revenue at a glance", "chart"),
    ("Stripe Payments", "clients pay online", "card"),
    ("Self-Hosted", "your data stays yours", "lock"),
    ("Deploy Anywhere", "Docker / Railway / Render", "cloud"),
    ("Open Source", "MIT License", "code"),
]
for f in range(240):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    t = f / FPS

    # Title
    text_center(draw, 60, "What You Get", font_med, fill=ACCENT)

    # Feature grid (2x3)
    card_w, card_h = 520, 160
    gap_x, gap_y = 50, 30
    grid_w = 3 * card_w + 2 * gap_x
    grid_h = 2 * card_h + gap_y
    sx = (W - grid_w) // 2
    sy = 180

    for i, (title, desc, icon) in enumerate(features):
        row = i // 3
        col_i = i % 3
        appear_t = 0.3 + i * 0.4
        if t >= appear_t:
            prog = min(1.0, (t - appear_t) / 0.5)
            ep = ease_out_cubic(prog)
            cx = sx + col_i * (card_w + gap_x)
            cy = sy + row * (card_h + gap_y) + int((1 - ep) * 30)

            fill = tuple(int(c * ep) for c in DARK_CARD)
            draw_rounded_rect(draw, (cx, cy, cx + card_w, cy + card_h), fill=fill, radius=14)

            # Accent bar on left
            bar_col = tuple(int(c * ep) for c in ACCENT)
            draw.rounded_rectangle((cx, cy, cx + 6, cy + card_h), radius=3, fill=bar_col)

            # Title
            tcol = tuple(int(c * ep) for c in WHITE)
            draw.text((cx + 30, cy + 35), title, font=font_sm, fill=tcol)

            # Description
            dcol = tuple(int(c * ep) for c in DIM)
            draw.text((cx + 30, cy + 90), desc, font=font_xs, fill=dcol)

    # Bottom: "The entire app is 4 files"
    if t > 4.0:
        ba = min(1.0, (t - 4.0) / 0.5)
        col_b = tuple(int(c * ease_out_cubic(ba)) for c in WHITE)
        text_center(draw, 600, "The entire app is 4 files.", font_med, fill=col_b)
        if t > 5.0:
            ba2 = min(1.0, (t - 5.0) / 0.5)
            col_b2 = tuple(int(c * ease_out_cubic(ba2)) for c in DIM)
            text_center(draw, 670, "A junior dev can read it in an afternoon.", font_sm, fill=col_b2)

    img.save(os.path.join(OUT, f"frame_{frame_num:05d}.png"))
    frame_num += 1

# === SCENE 4: PRICING (16-22s = 180 frames) ===
plans = [
    ("Starter", "Free", "3 invoices/mo", DIM),
    ("Pro", "$19/mo", "Unlimited everything", ACCENT),
    ("Business", "$39/mo", "Multi-currency + API", GREEN),
]
for f in range(180):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    t = f / FPS

    text_center(draw, 80, "Simple Pricing", font_med, fill=WHITE)

    card_w, card_h = 420, 400
    gap = 60
    total = 3 * card_w + 2 * gap
    sx = (W - total) // 2

    for i, (name, price, desc, color) in enumerate(plans):
        appear_t = 0.5 + i * 0.5
        if t >= appear_t:
            prog = min(1.0, (t - appear_t) / 0.6)
            ep = ease_out_cubic(prog)
            cx = sx + i * (card_w + gap)
            cy = 220 + int((1 - ep) * 50)

            fill = tuple(int(c * ep) for c in DARK_CARD)
            draw_rounded_rect(draw, (cx, cy, cx + card_w, cy + card_h), fill=fill, radius=18)

            # Highlight border for Pro
            if i == 1:
                border_col = tuple(int(c * ep) for c in ACCENT)
                draw.rounded_rectangle((cx - 2, cy - 2, cx + card_w + 2, cy + card_h + 2), radius=20, outline=border_col, width=3)

            # Plan name
            ncol = tuple(int(c * ep) for c in color)
            bbox = draw.textbbox((0, 0), name, font=font_med)
            nw = bbox[2] - bbox[0]
            draw.text((cx + (card_w - nw) // 2, cy + 40), name, font=font_med, fill=ncol)

            # Price
            pcol = tuple(int(c * ep) for c in WHITE)
            bbox2 = draw.textbbox((0, 0), price, font=font_big)
            pw = bbox2[2] - bbox2[0]
            draw.text((cx + (card_w - pw) // 2, cy + 130), price, font=font_big, fill=pcol)

            # Description
            dcol = tuple(int(c * ep) for c in DIM)
            bbox3 = draw.textbbox((0, 0), desc, font=font_xs)
            dw = bbox3[2] - bbox3[0]
            draw.text((cx + (card_w - dw) // 2, cy + 260), desc, font=font_xs, fill=dcol)

    # Bottom callout
    if t > 3.5:
        ba = min(1.0, (t - 3.5) / 0.5)
        col_b = tuple(int(c * ease_out_cubic(ba)) for c in GREEN)
        text_center(draw, 720, "22 Pro subscribers = $5,000+ ARR", font_med, fill=col_b)

    img.save(os.path.join(OUT, f"frame_{frame_num:05d}.png"))
    frame_num += 1

# === SCENE 5: DEPLOY (22-26s = 120 frames) ===
deploy_cmds = [
    "$ git clone invoicebot",
    "$ node server.js",
    "# InvoiceBot running → localhost:3000",
]
for f in range(120):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    t = f / FPS

    # Terminal window
    term_x, term_y = 260, 150
    term_w, term_h = 1400, 500
    draw_rounded_rect(draw, (term_x, term_y, term_x + term_w, term_y + term_h), fill=(18, 18, 22), radius=16)

    # Title bar dots
    for di, dc in enumerate([(RED), (YELLOW), (GREEN)]):
        draw.ellipse((term_x + 24 + di * 28, term_y + 18, term_x + 40 + di * 28, term_y + 34), fill=dc)

    # Terminal title
    draw.text((term_x + term_w // 2 - 60, term_y + 14), "Terminal", font=font_tiny, fill=DIM)

    # Commands typed out
    for i, cmd in enumerate(deploy_cmds):
        appear_t = 0.5 + i * 1.0
        if t >= appear_t:
            type_prog = min(1.0, (t - appear_t) / 0.8)
            chars = int(len(cmd) * ease_out_cubic(type_prog))
            shown = cmd[:chars]
            y = term_y + 70 + i * 60
            color = GREEN if cmd.startswith("#") else WHITE
            draw.text((term_x + 30, y), shown, font=font_sm, fill=color)

            # Blinking cursor
            if type_prog < 1.0:
                cursor_x = term_x + 30 + draw.textbbox((0, 0), shown, font=font_sm)[2]
                if int(t * 3) % 2 == 0:
                    draw.rectangle((cursor_x, y, cursor_x + 20, y + 36), fill=ACCENT)

    # "Deploy Anywhere" text
    if t > 3.0:
        ba = min(1.0, (t - 3.0) / 0.4)
        col_b = tuple(int(c * ease_out_cubic(ba)) for c in WHITE)
        text_center(draw, 720, "Deploy anywhere. Docker. Railway. Render. Fly.io.", font_sm, fill=col_b)

    img.save(os.path.join(OUT, f"frame_{frame_num:05d}.png"))
    frame_num += 1

# === SCENE 6: CTA (26-30s = 120 frames) ===
for f in range(120):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    t = f / FPS

    # Logo / brand
    if t < 0.6:
        prog = min(1.0, t / 0.6)
        ep = ease_out_cubic(prog)
        scale = 0.5 + 0.5 * ep
    else:
        scale = 1.0
        ep = 1.0

    col = tuple(int(c * ep) for c in ACCENT)
    text_center(draw, 280, "InvoiceBot", font_big, fill=col)

    if t > 0.8:
        a2 = min(1.0, (t - 0.8) / 0.5)
        col2 = tuple(int(c * ease_out_cubic(a2)) for c in WHITE)
        text_center(draw, 400, "Get Paid Faster.", font_med, fill=col2)

    if t > 1.5:
        a3 = min(1.0, (t - 1.5) / 0.5)
        col3 = tuple(int(c * ease_out_cubic(a3)) for c in DIM)
        text_center(draw, 490, "Open source. Free to start. Pro at $19/month.", font_sm, fill=col3)

    # CTA button
    if t > 2.2:
        a4 = min(1.0, (t - 2.2) / 0.4)
        ep4 = ease_out_cubic(a4)
        btn_w, btn_h = 500, 80
        bx = (W - btn_w) // 2
        by = 600
        btn_col = tuple(int(c * ep4) for c in ACCENT)
        draw_rounded_rect(draw, (bx, by, bx + btn_w, by + btn_h), fill=btn_col, radius=40)
        tcol = tuple(int(c * ep4) for c in WHITE)
        bbox = draw.textbbox((0, 0), "Star on GitHub", font=font_sm)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, by + 18), "Star on GitHub", font=font_sm, fill=tcol)

    # URL
    if t > 2.8:
        a5 = min(1.0, (t - 2.8) / 0.4)
        col5 = tuple(int(c * ease_out_cubic(a5)) for c in DIM)
        text_center(draw, 720, "github.com/abuadamalmaliki-prog/B00K", font_xs, fill=col5)

    img.save(os.path.join(OUT, f"frame_{frame_num:05d}.png"))
    frame_num += 1

print(f"Generated {frame_num} frames at {FPS}fps = {frame_num/FPS:.1f}s")
