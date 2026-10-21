"""Shareable day pages: site/day/MM-DD.html with a link preview image,
site/day/MM-DD.png, for every calendar date.

    python -m pipeline.cards    # after pipeline.build; needs Pillow

Link previews can't read the calendar's #MM-DD links, so each date gets a
small page carrying Open Graph tags that forwards visitors to the calendar.
The refresh workflow builds these at deploy time; they aren't committed.
"""

import datetime as dt
import html
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config, ical

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"
OUT = ROOT / "site" / "day"
WIDTH, HEIGHT, MARGIN = 1200, 630, 72
INK, ORANGE, WHITE, MUTED = (23, 19, 15), (223, 70, 1), (255, 255, 255), (184, 172, 160)
FONT_DIRS = [os.environ.get("CARD_FONT_DIR", ""), "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu",
             "/Library/Fonts", str(Path.home() / "Library/Fonts")]


def font(bold, size):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in FONT_DIRS:
        if d and (Path(d) / name).exists():
            return ImageFont.truetype(str(Path(d) / name), size)
    raise SystemExit(f"{name} not found; install fonts-dejavu-core or set CARD_FONT_DIR")


def wrap(draw, text, face, width, max_lines):
    """Word-wrap text to width, ending with an ellipsis if it runs past max_lines."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=face) <= width:
            line = trial
            continue
        lines.append(line)
        line = word
    lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while draw.textlength(lines[-1] + "…", font=face) > width:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] += "…"
    return lines


def fit(draw, text, face, width):
    return wrap(draw, text, face, width, 1)[0]


def date_label(key):
    month, day = map(int, key.split("-"))
    return f"{dt.date(2000, month, day):%B} {day}"


def record_text(rows):
    w = sum(r[1] for r in rows)
    l = sum(r[2] for r in rows)
    return f"All-time on this date: {w}–{l}" if w + l else "No franchise games on this date"


def card(key, items, rows):
    img = Image.new("RGB", (WIDTH, HEIGHT), INK)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, WIDTH, 14], fill=ORANGE)
    kicker, big, title_face, body = font(True, 26), font(True, 84), font(True, 46), font(False, 28)
    text_w = WIDTH - 2 * MARGIN

    y = 62
    draw.ellipse([MARGIN, y + 6, MARGIN + 18, y + 24], fill=ORANGE)
    draw.text((MARGIN + 30, y), "ORIOLES CALENDAR", font=kicker, fill=MUTED)
    y += 50
    draw.text((MARGIN, y), date_label(key), font=big, fill=WHITE)
    y += 112
    if items:
        _, year, text = items[0]
        draw.text((MARGIN, y), str(year), font=kicker, fill=ORANGE)
        y += 42
        for line in wrap(draw, text, title_face, text_w, 3):
            draw.text((MARGIN, y), line, font=title_face, fill=WHITE)
            y += 58
        y += 14
        for _, year, text in items[1:4 if y < 440 else 3]:
            if y > HEIGHT - 110:
                break
            draw.text((MARGIN, y), fit(draw, f"{year}  {text}", body, text_w), font=body, fill=MUTED)
            y += 40
    else:
        for line in wrap(draw, "Birthdays, debuts, trades and great games from franchise history", title_face, text_w, 3):
            draw.text((MARGIN, y), line, font=title_face, fill=WHITE)
            y += 58
    draw.line([MARGIN, HEIGHT - 76, WIDTH - MARGIN, HEIGHT - 76], fill=(60, 52, 46), width=2)
    host = config.SITE_URL.split("//", 1)[1].rstrip("/")
    draw.text((MARGIN, HEIGHT - 58), record_text(rows), font=body, fill=MUTED)
    draw.text((WIDTH - MARGIN, HEIGHT - 58), host, font=body, fill=MUTED, anchor="ra")
    return img.quantize(colors=64)


def page(key, items, rows):
    label = date_label(key)
    title = f"{label} in Orioles history"
    if items:
        _, year, text = items[0]
        desc = f"{year}: {text}." + (f" Plus {len(items) - 1} more." if len(items) > 1 else "")
    else:
        desc = record_text(rows) + "."
    site = config.SITE_URL
    target = f"../#{key}"
    e = lambda s: html.escape(s, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Orioles Calendar">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{site}day/{key}.html">
<meta property="og:image" content="{site}day/{key}.png">
<meta property="og:image:width" content="{WIDTH}">
<meta property="og:image:height" content="{HEIGHT}">
<meta property="og:image:alt" content="{e(title)}: {e(desc)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="../favicon.png">
<link rel="apple-touch-icon" href="../apple-touch-icon.png">
<link rel="canonical" href="{site}#{key}">
<meta http-equiv="refresh" content="0; url={target}">
<script>location.replace("{target}")</script>
</head>
<body>
<p><a href="{target}">{e(title)}</a></p>
</body>
</html>
"""


def main():
    players = json.loads((DATA / "players.json").read_text(encoding="utf-8"))
    events = json.loads((DATA / "events.json").read_text(encoding="utf-8"))
    records = json.loads((DATA / "records.json").read_text(encoding="utf-8"))
    days = ical.day_items(players, events, fold_leap=False)
    OUT.mkdir(parents=True, exist_ok=True)
    day = dt.date(2000, 1, 1)
    count = 0
    while day.year == 2000:
        key = f"{day:%m-%d}"
        items, rows = days.get(key, []), records.get(key, [])
        card(key, items, rows).save(OUT / f"{key}.png", optimize=True)
        (OUT / f"{key}.html").write_text(page(key, items, rows), encoding="utf-8")
        day += dt.timedelta(days=1)
        count += 1
    print(f"Wrote {count} day pages and cards to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
