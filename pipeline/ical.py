"""Subscribable iCalendar feeds of franchise anniversaries.

Each calendar day gets one all-day event that repeats every year. Its
title is the day's most notable item and its description lists the rest.
"""

from collections import defaultdict

from . import config

# Mirrors TYPE_SCORE and score() in site/app.js; keep the two in step.
TYPE_SCORE = {
    "callout": 100, "world_series": 95, "pennant": 90, "division_title": 85, "perfect_game": 85, "no_hitter": 75,
    "four_homer_game": 75, "career_milestone": 70, "series_win": 65, "cycle": 60, "ballpark_first": 55,
    "ballpark_last": 50, "three_homer_game": 45, "strikeout_game": 45, "long_game": 40, "triple_play": 40,
    "big_win": 35, "walk_off": 30, "inside_the_park_hr": 28,
}
PER_DAY = 10           # items listed in each day's description
MIN_BIRTHDAY_WAR = 10  # birthdays and acquisitions of lesser players stay on the site only
ACQUIRED_HOW = {
    "T": " in a trade", "Tp": " in a trade", "TR": " in a trade", "P": " by purchase", "PUR": " by purchase",
    "F": " as a free agent", "Fo": " as a free agent", "SFA": " as a free agent", "Da": " in the amateur draft",
    "W": " on waivers", "Wf": " on waivers", "CLW": " on waivers", "D": " in the Rule 5 draft", "R5": " in the Rule 5 draft",
}


def _war(p):
    return max(0.0, (p.get("w") or [0, 0])[1] or 0)


def event_score(e, player):
    if e.get("c"):
        return TYPE_SCORE["callout"]
    if e["t"] in TYPE_SCORE:
        return TYPE_SCORE[e["t"]]
    return 10 + min(40, _war(player or {}) * 1.5)


def birthday_score(p):
    return 8 + min(45, _war(p) * 1.5) + (15 if p.get("hof") else 0)


def day_items(players, events, first_year=1901):
    """{"MM-DD": [(score, year, text), ...]} best first, Feb 29 folded into Feb 28."""
    by_id = {p["id"]: p for p in players}
    days = defaultdict(list)

    def add(date, score, text, era_year=None):
        year = int(date[:4])
        if (era_year or year) < first_year:
            return
        key = "02-28" if date[5:] == "02-29" else date[5:]
        days[key].append((score, year, text))

    for e in events:
        player = by_id.get(e["ids"][0]) if len(e["ids"]) == 1 else None
        if e["t"] in ("debut", "final_game") and not (player and (player.get("hof") or _war(player) >= 5)):
            continue
        add(e["d"], event_score(e, player), e["title"])
    for p in players:
        if p.get("b") and len(p["b"]) == 10 and (p.get("hof") or _war(p) >= MIN_BIRTHDAY_WAR):
            add(p["b"], birthday_score(p), f"{p['n']} is born", era_year=p["y"][-1])
        for a in p.get("a", []):
            if len(a["d"]) == 10 and (p.get("hof") or _war(p) >= MIN_BIRTHDAY_WAR):
                how = ACQUIRED_HOW.get(a["how"], "")
                team = config.nickname(int(a["d"][:4]))
                add(a["d"], 6 + min(30, _war(p)), f"{team} acquire {p['n']}{how}", era_year=int(a["d"][:4]))
    for key in days:
        days[key].sort(key=lambda x: (-x[0], x[1]))
    return days


def escape(text):
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    """Fold a content line to 75 octets, per RFC 5545 section 3.1."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    parts, start, limit = [], 0, 75
    while start < len(data):
        end = min(len(data), start + limit)
        while end < len(data) and (data[end] & 0xC0) == 0x80:  # don't split a UTF-8 character
            end -= 1
        parts.append(data[start:end].decode("utf-8"))
        start, limit = end, 74  # continuation lines start with a space
    return "\r\n ".join(parts)


def feed(players, events, site_url, stamp, name, first_year=1901):
    """Return the .ics text. `stamp` (YYYYMMDDTHHMMSSZ) is fixed per data
    build so an unchanged dataset produces an unchanged file."""
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//orioles-calendar//EN", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", f"X-WR-CALNAME:{escape(name)}",
        "X-WR-CALDESC:Anniversaries from franchise history\\, one event per day.",
        "REFRESH-INTERVAL;VALUE=DURATION:P1D", "X-PUBLISHED-TTL:P1D",
    ]
    suffix = "" if first_year <= 1901 else f"-{first_year}"
    for key, items in sorted(day_items(players, events, first_year).items()):
        score, year, text = items[0]
        mm, dd = key.split("-")
        rest = [f"{y}: {t}" for _, y, t in items[:PER_DAY]]
        if len(items) > PER_DAY:
            rest.append(f"…and {len(items) - PER_DAY} more")
        url = f"{site_url}#{mm}-{dd}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:oc-{mm}{dd}{suffix}@orioles-calendar",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:2000{mm}{dd}",
            "RRULE:FREQ=YEARLY",
            "TRANSP:TRANSPARENT",
            f"SUMMARY:{escape(f'{text} ({year})')}",
            f"DESCRIPTION:{escape(chr(10).join(rest) + chr(10) + chr(10) + 'More: ' + url)}",
            f"URL:{url}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"
