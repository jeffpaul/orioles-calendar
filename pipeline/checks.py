"""Validation run before any data is written. Each check targets a problem
found in the White Sox calendar's data."""

import re
from collections import Counter

DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
FULL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def run(players, events, records, games, meta):
    problems = []
    ids = {p["id"] for p in players}

    dupes = [i for i, n in Counter(p["id"] for p in players).items() if n > 1]
    if dupes:
        problems.append(f"duplicate player ids: {dupes[:5]}")

    dangling = sorted({(e["d"], i) for e in events for i in e["ids"] if i not in ids})
    if dangling:
        problems.append(f"{len(dangling)} events name players missing from players.json, e.g. {dangling[:3]}")

    for p in players:
        for field in ("b", "x"):
            if p.get(field) and not DATE.match(p[field]):
                problems.append(f"{p['id']} has a malformed {field} date: {p[field]}")
    # Franchise WAR can exceed career WAR (negative seasons elsewhere), so
    # check coverage instead: nearly every player with a B-Ref ID has WAR.
    with_bbref = [p for p in players if p.get("bbref")]
    no_war = [p["id"] for p in with_bbref if "w" not in p]
    if with_bbref and len(no_war) > 0.02 * len(with_bbref):
        problems.append(f"{len(no_war)} of {len(with_bbref)} players with a B-Ref ID have no WAR, e.g. {no_war[:3]}")

    bad_dates = [e for e in events if not FULL_DATE.match(e["d"])]
    if bad_dates:
        problems.append(f"{len(bad_dates)} events without a full date, e.g. {bad_dates[0]['title']}")

    # Events and records come from the same game rows, so the newest game
    # event can't be older than the newest record by more than a few days.
    last_game = meta["last_game"]
    game_events = [e["d"] for e in events if e.get("gid")]
    if game_events and max(game_events) < last_game[:7]:
        problems.append(f"newest game event {max(game_events)} lags the last game {last_game}")
    record_games = sum(sum(r[1:]) for rows in records.values() for r in rows)
    decided = sum(1 for g in games if g["rs"] != g["ra"] or g["type"] == "regular")
    if record_games != decided:
        problems.append(f"records count {record_games} games but there are {decided}")

    seasons = {g["season"] for g in games}
    missing = [y for y in range(1901, max(seasons) + 1) if y not in seasons]
    if missing:
        problems.append(f"no games for seasons {missing[:10]}")
    return problems


SCHEDULE_FIELDS = {"d", "t", "home", "opp", "abbr", "time", "venue", "status", "pk"}


def schedule(games):
    """The upcoming season's schedule: full dates, every field, no duplicates."""
    problems = []
    for g in games:
        if not FULL_DATE.match(g.get("d", "")) or not SCHEDULE_FIELDS <= g.keys():
            problems.append(f"malformed schedule entry: {g}")
            break
    dupes = [pk for pk, n in Counter(g["pk"] for g in games).items() if n > 1]
    if dupes:
        problems.append(f"schedule lists games more than once: {dupes[:5]}")
    return problems
