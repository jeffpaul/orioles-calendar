"""Build site/data/*.json from Retrosheet, the MLB Stats API, B-Ref WAR and
the Chadwick register.

    python -m pipeline.build            # full build
    python -m pipeline.build --no-api   # Retrosheet only, no network calls to the Stats API
"""

import argparse
import csv
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import checks, config, derive, ical, retro, sources, statsapi

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data"
FULL_DATE = len("2000-01-01")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def load_register():
    """Chadwick register: retro -> (mlbam, bbref) and mlbam -> retro."""
    retro_to, mlbam_to = {}, {}
    for part in "0123456789abcdef":
        path = sources.fetch(sources.CHADWICK.format(part=part), f"chadwick/people-{part}.csv", max_age_hours=24 * 7)
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["key_retro"]:
                    retro_to[r["key_retro"]] = (int(r["key_mlbam"]) if r["key_mlbam"] else None, r["key_bbref"] or None)
                    if r["key_mlbam"]:
                        mlbam_to[int(r["key_mlbam"])] = r["key_retro"]
    return retro_to, mlbam_to


def load_war():
    """bbref id -> [career WAR, franchise WAR], batting and pitching WAR summed the same way for both."""
    career, ours = defaultdict(float), defaultdict(float)
    seen = set()
    for kind in ("bat", "pitch"):
        path = sources.fetch(sources.BREF_WAR.format(kind=kind), f"bref/war_daily_{kind}.txt", max_age_hours=24 * 7)
        with open(path, encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                try:
                    war = float(r["WAR"])
                except (TypeError, ValueError):
                    continue
                pid = r["player_ID"]
                seen.add(pid)
                career[pid] += war
                if r["team_ID"] in config.BREF_TEAMS:
                    ours[pid] += war
    return {pid: [round(career[pid], 1), round(ours[pid], 1)] for pid in seen if pid in ours}


def ordinal(n):
    return f"{n:,}" + ("th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-api", action="store_true", help="skip the Stats API (Retrosheet seasons only)")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD)")
    args = ap.parse_args(argv)
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    log("Loading Retrosheet…")
    zips = retro.team_zips()
    bio, teams, parks = retro.load_bio()
    opp_names = retro.opponent_names(teams, retro.opponent_codes(zips))
    games, bats, pits, apps = retro.load_games(zips, opp_names)
    rosters = retro.load_rosters(zips)
    walkoffs, itp = retro.load_plays(zips, games)
    retro_last = max(g["season"] for g in games)
    log(f"  {len(games):,} games through {retro_last}")

    log("Loading ID register and WAR…")
    retro_to, mlbam_to = load_register()
    war = load_war()

    def pid_for(mlbam):
        return mlbam_to.get(mlbam, f"mlbam:{mlbam}")

    api_people, api_positions = {}, defaultdict(lambda: defaultdict(int))
    if not args.no_api:
        for season in range(retro_last + 1, today.year + 1):
            log(f"Loading {season} from the Stats API…")
            names_by_id = statsapi.team_names(season)
            g2, b2, p2, a2, w2, i2, pos2 = statsapi.season_games(season, pid_for, names_by_id)
            games += g2; bats += b2; pits += p2; walkoffs.update(w2); itp += i2
            for pid, lst in a2.items():
                apps[pid] += lst
            for pid, pos in pos2.items():
                for k, v in pos.items():
                    api_positions[pid][k] += v
            log(f"  {len(g2)} games")
        managers = {g["mgr"] for g in games if g.get("mgr")}
        new_mlbam = [int(p.split(":")[1]) if p.startswith("mlbam:") else retro_to.get(p, (None,))[0]
                     for p in set(apps) | managers if p not in bio or p.startswith("mlbam:")]
        api_people = statsapi.people([m for m in new_mlbam if m])

    # Stats API games carry MLB venue IDs; use the Retrosheet park code when
    # the names match, so ballpark firsts and lasts span both sources.
    site_by_name = {p["name"]: site for site, p in parks.items()}
    for g in games:
        if g.get("site_name") in site_by_name:
            g["site"] = site_by_name[g.pop("site_name")]
    games.sort(key=lambda g: (g["date"], g["num"]))
    latest_season = max(g["season"] for g in games)
    game_by_gid = {g["gid"]: g for g in games}

    # Players --------------------------------------------------------------
    log("Building players…")
    trans = retro.load_transactions()
    api_trans = {} if args.no_api else statsapi.transactions(2022, today.year)
    for mlbam, lst in api_trans.items():
        trans.setdefault(pid_for(mlbam), [])
        trans[pid_for(mlbam)] += [(d, code, frm) for d, code, frm in lst]

    managed = derive.manager_records(games)
    hof_years, hof_by_name = ({}, {}) if args.no_api else statsapi.hall_of_fame()
    players, names = [], {}
    for pid in list(apps) + [pid for pid in managed if pid not in apps]:
        lst = apps.get(pid, [])
        dates = sorted(d for d, _ in lst)
        mlbam, bbref = (int(pid.split(":")[1]), None) if pid.startswith("mlbam:") else retro_to.get(pid, (None, None))
        b = bio.get(pid)
        api = api_people.get(mlbam) if mlbam else None
        if b:
            name = f"{b['usename']} {b['lastname']}".strip()
            if b["fullname"].endswith(" Jr."):
                name += " Jr."
            born, died = retro.iso(b["birthdate"]), retro.iso(b["deathdate"])
            hof = b["HOF"] == "HOF"
        elif api:
            name, born, died, hof = api["fullName"], api.get("birthDate"), api.get("deathDate"), False
        else:
            name, born, died, hof = pid, None, None, False
        names[pid] = name
        r = rosters.get(pid)
        seasons = sorted(set(r["seasons"] if r else set()) | {int(d[:4]) for d in dates})
        pos = Counter(r["pos"] if r else {})
        for k, v in api_positions.get(pid, {}).items():
            pos[k] += v
        api_games = len({gid for _, gid in lst if gid.startswith("mlb")})
        main_pos = [p for p, n in pos.most_common() if n and p not in ("PH", "PR")] or [p for p, n in pos.most_common() if n]
        acq = sorted({(d, typ, frm) for d, typ, frm in trans.get(pid, [])
                      if seasons and d and d[:4].isdigit() and int(d[:4]) <= seasons[-1]})
        players.append({
            "id": pid, "n": name, "b": born, "x": died,
            "a": [{"d": d, "how": typ, "from": frm} for d, typ, frm in acq],
            "y": seasons, "g": (r["g"] if r else 0) + api_games, "p": main_pos[:4],
            "w": war.get(bbref), "mlbam": mlbam, "bbref": bbref, "hof": hof or mlbam in hof_years or None,
            "m": managed.get(pid),
        })
    # "Cal Ripken Sr.", but only where a Jr. shares the name.
    for p in players:
        b = bio.get(p["id"])
        if b and b["fullname"].endswith(" Sr.") and p["n"] + " Jr." in names.values():
            p["n"] = names[p["id"]] = p["n"] + " Sr."
    for p in players:
        for k in [k for k, v in p.items() if v is None]:
            del p[k]
    names_fn = lambda pid: names.get(pid) or (bio[pid]["usename"] + " " + bio[pid]["lastname"] if pid in bio else pid)

    # Events ---------------------------------------------------------------
    log("Building events…")
    events = []
    first_game_on = {}
    for g in games:
        first_game_on.setdefault(g["date"], g)
    for pid, lst in apps.items():
        lst = sorted(lst)
        first, last = lst[0], lst[-1]
        g = game_by_gid[first[1]]
        us = config.nickname(g["season"])
        events.append({"d": first[0], "t": "debut", "title": f"{names_fn(pid)} plays his first game for the {us}",
                       "detail": derive.score_text(g), "ids": [pid], "gid": g["gid"], "link": g["link"],
                       "opp": g["opp_name"], "score": [g["rs"], g["ra"]]})
        if int(last[0][:4]) < latest_season:
            g = game_by_gid[last[1]]
            events.append({"d": last[0], "t": "final_game",
                           "title": f"{names_fn(pid)} plays his final game for the {config.nickname(g['season'])}",
                           "detail": derive.score_text(g), "ids": [pid], "gid": g["gid"], "link": g["link"],
                           "opp": g["opp_name"], "score": [g["rs"], g["ra"]]})
    events += derive.manager_events(games, names_fn, config.MANAGER_WIN_THRESHOLDS)
    events += hall_of_fame_events(players, hof_years, hof_by_name)
    events += derive.game_events(games, walkoffs, itp, names_fn)
    events += derive.player_game_events(games, bats, pits, names_fn)
    derive.name_no_hitters(events, pits, names_fn)
    park_names = {site: p["name"] for site, p in parks.items()}
    park_names.update({g["site"]: g["site_name"] for g in games if g.get("site_name")})
    for e in events:
        if "{park:" in e["title"]:
            e["title"] = e["title"].replace("{park:" + e["site"] + "}", park_names.get(e["site"], e["site"]))
            e.pop("site")

    log("Computing clinch dates…")
    for year in config.DIVISION_TITLES + config.PENNANTS_BEFORE_LCS:
        if year > retro_last:
            continue
        log_rows = retro.load_gamelog(year)
        team = next(code for code, (lo, hi) in config.RETRO_TEAMS.items() if lo <= year <= hi)
        if year in config.PENNANTS_BEFORE_LCS:
            rivals = sorted({r[2] for r in log_rows if r[6] == "AL"} | {r[3] for r in log_rows if r[7] == "AL"})
            label, kind = f"{year} American League pennant", "pennant"
        else:
            rivals, label, kind = config.al_east(year), f"{year} AL East title", "division_title"
        results = [r[:6] for r in log_rows]
        if not derive.final_standing_first(results, team, rivals):
            raise SystemExit(f"config lists {year} as a title season but {team} didn't finish first")
        date = derive.clinch_date(results, team, rivals, tiebreak_h2h=year >= 2022)
        events.append(clinch_event(date, year, label, kind, games))
    if not args.no_api:
        for season in range(retro_last + 1, today.year + 1):
            if statsapi.standings_clinched(season):
                results, rivals = statsapi.division_results(season)
                date = derive.clinch_date(results, str(config.MLB_TEAM_ID), rivals, tiebreak_h2h=True)
                events.append(clinch_event(date, season, f"{season} AL East title", "division_title", games))

    if not args.no_api:
        log("Finding career milestones…")
        events += career_milestones(players, bats, pits, game_by_gid, names_fn)

    appeared_on = {(pid, d) for pid, lst in apps.items() for d, _ in lst}
    for c in json.loads((Path(__file__).parent / "callouts.json").read_text()):
        present = all((pid, c["d"]) in appeared_on for pid in c["ids"])
        if (c.get("check") == "appeared") != present:
            raise SystemExit(f"callout check failed: {c['title']}")
        # The player's own game, for doubleheaders like Gaedel's.
        gid = next((gid for pid in c["ids"] for d, gid in apps.get(pid, []) if d == c["d"]), None)
        g = game_by_gid[gid] if gid else first_game_on.get(c["d"])
        if not g:
            raise SystemExit(f"callout has no franchise game on {c['d']}: {c['title']}")
        ev = {"d": c["d"], "t": "callout", "title": c["title"], "chip": c["chip"], "ids": c["ids"], "c": 1}
        if g:
            ev.update({"detail": derive.score_text(g), "gid": g["gid"], "link": g["link"]})
        events.append(ev)

    events.sort(key=lambda e: (e["d"], e["t"], e["title"]))
    recs = derive.records(games)

    meta = {
        "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "franchise": config.ERAS,
        "last_game": games[-1]["date"],
        "retrosheet_through": retro_last,
        "statsapi_seasons": sorted({g["season"] for g in games if g["src"] == "statsapi"}),
        "counts": {"players": len(players), "events": len(events), "games": len(games)},
    }
    sched = None if args.no_api else statsapi.schedule(today)
    problems = checks.run(players, events, recs, games, meta) + checks.schedule(sched or [])
    if problems:
        for p in problems:
            log("CHECK FAILED:", p)
        raise SystemExit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    players.sort(key=lambda p: (min(p["y"] + (p.get("m") or {}).get("y", [])), p["n"]))
    write(OUT / "players.json", players)
    write(OUT / "events.json", events)
    write(OUT / "records.json", recs)
    write(OUT / "meta.json", meta, indent=1)
    if sched is not None:  # --no-api keeps the last schedule
        write(OUT / "schedule.json", sched)
    stamp = meta["last_game"].replace("-", "") + "T000000Z"
    for filename, name, first_year in (("calendar.ics", "Orioles Calendar", 1901),
                                       ("calendar-orioles.ics", "Orioles Calendar (1954 on)", 1954)):
        text = ical.feed(players, events, config.SITE_URL, stamp, name, first_year)
        (ROOT / "site" / filename).write_text(text, encoding="utf-8", newline="")
    log(f"Wrote {len(players):,} players, {len(events):,} events, {len(recs)} record days (last game {meta['last_game']})")


def hall_of_fame_events(players, hof_years, hof_by_name):
    """Induction day for each franchise Hall of Famer, from config.HOF_CEREMONIES.
    People without an MLB ID (some managers) are matched by name."""
    events = []
    for p in players:
        year = hof_years.get(p.get("mlbam")) or (hof_by_name.get(p["n"]) if p.get("hof") and not p.get("mlbam") else None)
        if not p.get("hof") or not year:
            continue
        if year not in config.HOF_CEREMONIES:
            log(f"  no ceremony date for the Hall of Fame class of {year} ({p['n']}); add it to config.HOF_CEREMONIES")
            continue
        if config.HOF_CEREMONIES[year] is None:
            continue
        date, ceremony_year = config.HOF_CEREMONIES[year]
        detail = f"Class of {year}" + (f", inducted with the class of {ceremony_year}" if ceremony_year != year else "")
        events.append({"d": date, "t": "hof_induction", "title": f"{p['n']} is inducted into the Hall of Fame",
                       "detail": detail, "ids": [p["id"]]})
    return events


def clinch_event(date, year, label, kind, games):
    if not date:
        raise SystemExit(f"no clinch date found for {label}")
    ours = [g for g in games if g["date"] == date]
    ev = {"d": date, "t": kind, "title": f"{config.nickname(year)} clinch the {label}", "ids": []}
    if ours:
        g = ours[-1]
        ev.update({"detail": derive.score_text(g), "gid": g["gid"], "link": g["link"],
                   "opp": g["opp_name"], "score": [g["rs"], g["ra"]]})
    else:
        ev["detail"] = "Clinched on a day off, after a rival lost"
    return ev


STAT_WORDS = {"hits": ("gets his", "career hit"), "homeRuns": ("hits his", "career home run"),
              "wins": ("earns his", "career win"), "strikeOuts": ("records his", "career strikeout")}


def career_milestones(players, bats, pits, game_by_gid, names_fn):
    by_mlbam = {p["mlbam"]: p for p in players if p.get("mlbam")}
    totals = statsapi.career_totals(list(by_mlbam))
    lines = defaultdict(lambda: defaultdict(list))  # pid -> stat -> [(date, gid, value)]
    for b in bats:
        if b["type"] == "regular":
            lines[b["pid"]]["hits"].append((b["date"], b["gid"], b["h"]))
            lines[b["pid"]]["homeRuns"].append((b["date"], b["gid"], b["hr"]))
    for p in pits:
        if p["type"] == "regular":
            lines[p["pid"]]["wins"].append((p["date"], p["gid"], int(p["win"])))
            lines[p["pid"]]["strikeOuts"].append((p["date"], p["gid"], p["k"]))
    events = []
    for mlbam, career in totals.items():
        p = by_mlbam[mlbam]
        wanted = [s for s, th in config.CAREER_THRESHOLDS.items() if career.get(s, 0) >= th[0]]
        for stat in wanted:
            group = "pitching" if stat in ("wins", "strikeOuts") else "hitting"
            splits = statsapi.year_by_year(mlbam, group)
            for season in p["y"]:
                ours = [i for i, (s, team, _) in enumerate(splits) if s == season and team == config.MLB_TEAM_ID]
                if not ours:
                    continue
                baseline = sum(st.get(stat, 0) for i, (s, team, st) in enumerate(splits)
                               if team is not None and team != config.MLB_TEAM_ID and (s < season or (s == season and i < ours[0])))
                baseline += sum(st.get(stat, 0) for s, team, st in splits if team == config.MLB_TEAM_ID and s < season)
                season_lines = [l for l in lines[p["id"]][stat] if l[0].startswith(str(season))]
                for date, gid, t in derive.career_crossings(season_lines, baseline, stat, config.CAREER_THRESHOLDS[stat]):
                    g = game_by_gid[gid]
                    verb, noun = STAT_WORDS[stat]
                    events.append({"d": date, "t": "career_milestone", "title": f"{names_fn(p['id'])} {verb} {ordinal(t)} {noun}",
                                   "detail": derive.score_text(g), "ids": [p["id"]], "gid": gid, "link": g["link"],
                                   "opp": g["opp_name"], "score": [g["rs"], g["ra"]]})
    return events


def write(path, data, indent=None):
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":") if indent is None else None, indent=indent)
    path.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
