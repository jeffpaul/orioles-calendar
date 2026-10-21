"""Pure functions that turn normalized game rows into calendar events."""

from collections import defaultdict

from . import config

POSTSEASON = ("wildcard", "divisionseries", "lcs", "worldseries")


def score_text(g):
    us = config.nickname(g["season"])
    return f"{us} {g['rs']}, {g['opp_name']} {g['ra']}"


def is_walkoff(g):
    """Home win where the winning run scored in the home team's last turn at bat."""
    us, them = g["line_us"], g["line_them"]
    if not g["home"] or g["rs"] <= g["ra"] or not us or len(us) != len(them):
        return False
    return sum(us[:-1]) <= g["ra"]


def clinch_date(results, team, rivals, tiebreak_h2h=False):
    """First date after which no rival can finish ahead of `team`.

    results: [(date, num, vis, home, vscore, hscore), ...] for every game
    involving the teams (ties and unfinished games count for nobody).
    Before 2022 a tie meant a playoff game, so `team` must clear every rival's
    best possible win total. From 2022 ties are broken by head-to-head record
    (tiebreak_h2h=True), so matching a rival is enough once `team` has
    clinched the season series.
    Returns None if `team` never clinches.
    """
    teams = set(rivals) | {team}
    results = sorted((r for r in results if r[2] in teams or r[3] in teams), key=lambda r: (r[0], r[1]))
    total = defaultdict(int)
    for r in results:
        total[r[2]] += 1
        total[r[3]] += 1
    h2h_total = defaultdict(int)
    for r in results:
        if team in (r[2], r[3]):
            h2h_total[r[3] if r[2] == team else r[2]] += 1
    wins, played, h2h = defaultdict(int), defaultdict(int), defaultdict(int)
    by_date = defaultdict(list)
    for r in results:
        by_date[r[0]].append(r)
    for date in sorted(by_date):
        for _, _, vis, home, vs, hs in by_date[date]:
            played[vis] += 1
            played[home] += 1
            winner = vis if vs > hs else home if hs > vs else None
            if winner:
                wins[winner] += 1
                if winner == team:
                    h2h[home if vis == team else vis] += 1
        safe = True
        for r in rivals:
            if r == team:
                continue
            best = wins[r] + total[r] - played[r]
            if wins[team] > best:
                continue
            if tiebreak_h2h and wins[team] == best and h2h[r] * 2 > h2h_total[r]:
                continue
            safe = False
            break
        if safe:
            return date
    return None


def final_standing_first(results, team, rivals):
    wins, losses = defaultdict(int), defaultdict(int)
    for _, _, vis, home, vs, hs in results:
        if vs > hs:
            wins[vis] += 1; losses[home] += 1
        elif hs > vs:
            wins[home] += 1; losses[vis] += 1
    pct = lambda t: wins[t] / max(1, wins[t] + losses[t])
    return all(pct(team) >= pct(r) for r in rivals if r != team)


def game_events(games, walkoffs, itp, names):
    """Events that come from whole games: walk-offs, long games, big wins,
    triple plays, no-hitters, ballpark firsts and lasts, postseason series."""
    ev = []
    for g in games:
        us = config.nickname(g["season"])
        base = {"d": g["date"], "detail": score_text(g), "gid": g["gid"], "link": g["link"],
                "opp": g["opp_name"], "score": [g["rs"], g["ra"]]}
        if is_walkoff(g):
            who, kind = walkoffs.get(g["gid"], (None, None))
            if who and kind and kind != "other":
                title = f"{names(who)} draws a walk-off walk" if kind == "walk" else f"{names(who)} hits a walk-off {kind}"
                ids = [who]
            elif who:
                title, ids = f"{us} win on a walk-off by {names(who)}", [who]
            else:
                title, ids = f"{us} win in walk-off fashion", []
            ev.append({**base, "t": "walk_off", "title": title, "ids": ids})
        if g["innings"] >= config.LONG_GAME_INNINGS:
            verb = "win" if g["rs"] > g["ra"] else "lose" if g["rs"] < g["ra"] else "tie"
            ev.append({**base, "t": "long_game", "title": f"{us} {verb} a {g['innings']}-inning game", "ids": []})
        if g["rs"] - g["ra"] >= config.BIG_WIN_MARGIN:
            ev.append({**base, "t": "big_win", "title": f"{us} win by {g['rs'] - g['ra']} runs", "ids": []})
        if g["tp"]:
            ev.append({**base, "t": "triple_play", "title": f"{us} turn a triple play", "ids": []})
        if g["p_h"] == 0 and g["p_outs"] >= 27:
            perfect = g["p_bfp"] == g["p_outs"]
            ev.append({**base, "t": "perfect_game" if perfect else "no_hitter",
                       "title": f"{us} throw a {'perfect game' if perfect else 'no-hitter'}", "ids": [],
                       "_pitchers_of": g["gid"]})
    for gid, who in itp:
        g = next((x for x in games if x["gid"] == gid), None)
        if g:
            ev.append({"d": g["date"], "t": "inside_the_park_hr", "title": f"{names(who)} hits an inside-the-park home run",
                       "detail": score_text(g), "ids": [who], "gid": gid, "link": g["link"],
                       "opp": g["opp_name"], "score": [g["rs"], g["ra"]]})
    ev += ballpark_events(games)
    ev += series_events(games)
    return ev


def ballpark_events(games, park_names=None):
    homes = sorted((g for g in games if g["home"] and g["type"] == "regular"), key=lambda g: (g["date"], g["num"]))
    by_site = defaultdict(list)
    for g in homes:
        by_site[g["site"]].append(g)
    current = homes[-1]["site"] if homes else None
    ev = []
    for site, gs in by_site.items():
        if len(gs) < 20:  # neutral-site or one-off home games
            continue
        name = gs[0].get("site_name") or site
        for g, kind, word in ((gs[0], "ballpark_first", "First"), (gs[-1], "ballpark_last", "Last")):
            if kind == "ballpark_last" and site == current:
                continue
            ev.append({"d": g["date"], "t": kind, "title": f"{word} {config.nickname(g['season'])} home game at {{park:{site}}}",
                       "detail": score_text(g), "ids": [], "gid": g["gid"], "link": g["link"],
                       "opp": g["opp_name"], "score": [g["rs"], g["ra"]], "site": site})
    return ev


SERIES_TITLES = {"wildcard": "win the {y} AL Wild Card {kind}", "divisionseries": "win the {y} ALDS",
                 "lcs": "win the {y} AL pennant", "worldseries": "win the {y} World Series"}


def series_events(games):
    ev = []
    by_series = defaultdict(list)
    for g in games:
        if g["type"] in POSTSEASON:
            by_series[(g["season"], g["type"])].append(g)
    for (season, typ), gs in sorted(by_series.items()):
        gs.sort(key=lambda g: (g["date"], g["num"]))
        w = sum(g["rs"] > g["ra"] for g in gs)
        l = sum(g["rs"] < g["ra"] for g in gs)
        if w > l and gs[-1]["rs"] > gs[-1]["ra"]:
            g = gs[-1]
            kind = "Game" if len(gs) == 1 else "Series"
            title = f"{config.nickname(season)} " + SERIES_TITLES[typ].format(y=season, kind=kind)
            ev.append({"d": g["date"], "t": {"worldseries": "world_series", "lcs": "pennant"}.get(typ, "series_win"),
                       "title": title, "detail": f"{score_text(g)} · series {w}–{l}", "ids": [], "gid": g["gid"],
                       "link": g["link"], "opp": g["opp_name"], "score": [g["rs"], g["ra"]]})
    return ev


def player_game_events(games, bats, pits, names):
    by_gid = {g["gid"]: g for g in games}
    ev = []
    for b in bats:
        g = by_gid.get(b["gid"])
        if not g:
            continue
        base = {"d": b["date"], "detail": score_text(g), "ids": [b["pid"]], "gid": g["gid"], "link": g["link"],
                "opp": g["opp_name"], "score": [g["rs"], g["ra"]]}
        singles = b["h"] - b["d"] - b["t"] - b["hr"]
        if singles >= 1 and b["d"] >= 1 and b["t"] >= 1 and b["hr"] >= 1:
            ev.append({**base, "t": "cycle", "title": f"{names(b['pid'])} hits for the cycle"})
        if b["hr"] >= 4:
            ev.append({**base, "t": "four_homer_game", "title": f"{names(b['pid'])} hits {b['hr']} home runs"})
        elif b["hr"] >= config.HOMER_GAME:
            ev.append({**base, "t": "three_homer_game", "title": f"{names(b['pid'])} hits three home runs"})
    for p in pits:
        g = by_gid.get(p["gid"])
        if g and p["k"] >= config.STRIKEOUT_GAME:
            ev.append({"d": p["date"], "t": "strikeout_game", "title": f"{names(p['pid'])} strikes out {p['k']}",
                       "detail": score_text(g), "ids": [p["pid"]], "gid": g["gid"], "link": g["link"],
                       "opp": g["opp_name"], "score": [g["rs"], g["ra"]]})
    return ev


def name_no_hitters(events, pits, names):
    """Fill in the pitchers on team no-hitters."""
    by_gid = defaultdict(list)
    for p in pits:
        by_gid[p["gid"]].append(p)
    for e in events:
        gid = e.pop("_pitchers_of", None)
        if not gid:
            continue
        ps = [p["pid"] for p in sorted(by_gid[gid], key=lambda p: -p["outs"]) if p["outs"] > 0]
        e["ids"] = ps
        what = "perfect game" if e["t"] == "perfect_game" else "no-hitter"
        if len(ps) == 1:
            e["title"] = f"{names(ps[0])} throws a {what}"
        elif ps:
            e["title"] = f"{', '.join(names(p) for p in ps[:-1])} and {names(ps[-1])} combine on a {what}"


def career_crossings(lines, baseline, stat, thresholds):
    """Walk game lines in order and report where a career total crosses a
    threshold. lines: [(date, gid, value)], baseline: total before them."""
    out, total = [], baseline
    for date, gid, value in sorted(lines):
        before, total = total, total + value
        for t in thresholds:
            if before < t <= total:
                out.append((date, gid, t))
    return out


FILL_IN_GAMES = 20  # a shorter spell inside another manager's season is a fill-in
STINT_WORDS = ["first", "second", "third", "fourth"]


def manager_stints(games):
    """Runs of consecutive franchise games under one manager, oldest first:
    [{"mgr": pid, "games": [...], "fill_in": bool}]. When a manager hands the
    team to someone for fewer than FILL_IN_GAMES games and takes it back the
    same season (an ejection, a suspension, a sick day), his stint carries on
    and includes those games, the way official records credit them; the other
    spell is kept as a fill-in."""
    stints = []
    for g in sorted((g for g in games if g.get("mgr")), key=lambda g: (g["date"], g["num"])):
        if stints and stints[-1]["mgr"] == g["mgr"]:
            stints[-1]["games"].append(g)
            continue
        if (len(stints) >= 2 and stints[-2]["mgr"] == g["mgr"] and len(stints[-1]["games"]) < FILL_IN_GAMES
                and stints[-2]["games"][-1]["season"] == g["season"]):
            stints[-1]["fill_in"] = True
            stints[-2]["games"] += stints[-1]["games"] + [g]
            stints.append(stints.pop(-2))
            continue
        stints.append({"mgr": g["mgr"], "games": [g], "fill_in": False})
    return sorted(stints, key=lambda s: (s["games"][0]["date"], s["games"][0]["num"]))


def credited_games(games):
    """[(manager, game)] in date order, fill-in games credited to the manager
    whose stint they fall in."""
    out = [(s["mgr"], g) for s in manager_stints(games) if not s["fill_in"] for g in s["games"]]
    return sorted(out, key=lambda x: (x[1]["date"], x[1]["num"]))


def manager_records(games):
    """{pid: {"y": seasons, "g": games, "w": wins, "l": losses, "pw":, "pl":}}
    over the franchise games credited to him, regular season and postseason apart."""
    out = {}
    for mgr, g in credited_games(games):
        r = out.setdefault(mgr, {"y": set(), "g": 0, "w": 0, "l": 0, "pw": 0, "pl": 0})
        r["y"].add(g["season"])
        post = g["type"] in POSTSEASON
        if not post:
            r["g"] += 1
        if g["rs"] != g["ra"]:
            r[("p" if post else "") + ("w" if g["rs"] > g["ra"] else "l")] += 1
    for r in out.values():
        r["y"] = sorted(r["y"])
        if not r["pw"] + r["pl"]:
            del r["pw"], r["pl"]
    return out


def _wl(gs):
    reg = [g for g in gs if g["type"] not in POSTSEASON]
    return f"{sum(g['rs'] > g['ra'] for g in reg):,}–{sum(g['rs'] < g['ra'] for g in reg):,}"


def manager_events(games, names, thresholds):
    """First and last games of each managing stint (fill-ins left out) and
    round-number franchise wins as manager. The current stint gets no end."""
    if not games:
        return []
    last_gid = max(games, key=lambda g: (g["date"], g["num"]))["gid"]
    ev = []

    def event(g, t, title, detail, pid, n):
        return {"d": g["date"], "t": t, "title": title, "detail": detail, "ids": [pid], "gid": g["gid"],
                "link": g["link"], "opp": g["opp_name"], "score": [g["rs"], g["ra"]], "n": n}

    by_mgr = defaultdict(list)
    for s in manager_stints(games):
        if not s["fill_in"]:
            by_mgr[s["mgr"]].append(s)
    for pid, stints in by_mgr.items():
        for i, s in enumerate(stints):
            first, last, n = s["games"][0], s["games"][-1], len(s["games"])
            us = config.nickname(first["season"])
            if i == 0:
                ev.append(event(first, "mgr_first", f"{names(pid)} manages his first game for the {us}",
                                score_text(first), pid, n))
            else:
                ev.append(event(first, "mgr_return", f"{names(pid)} returns to manage the {us}",
                                score_text(first), pid, n))
            if last["gid"] == last_gid:
                continue
            us = config.nickname(last["season"])
            detail = f"{score_text(last)} · {_wl(s['games'])} in {'the stint' if len(stints) > 1 else 'his tenure'}"
            if i == len(stints) - 1:
                ev.append(event(last, "mgr_last", f"{names(pid)} manages his final game for the {us}", detail, pid, n))
            else:
                word = STINT_WORDS[i] if i < len(STINT_WORDS) else f"{i + 1}th"
                ev.append(event(last, "mgr_stint_end", f"{names(pid)}'s {word} stint as {us} manager ends",
                                detail, pid, n))
    wins = defaultdict(int)
    for mgr, g in credited_games(games):
        if g["type"] in POSTSEASON or g["rs"] <= g["ra"]:
            continue
        wins[mgr] += 1
        if wins[mgr] in thresholds:
            n = wins[mgr]
            ev.append(event(g, "mgr_milestone", f"{names(mgr)} earns his {n:,}th win as {config.nickname(g['season'])} manager",
                            score_text(g), mgr, n))
    return ev


def records(games):
    """{"MM-DD": [[year, w, l, t, pw, pl], ...]} sorted by year."""
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0, 0]))
    for g in games:
        r = acc[g["date"][5:]][g["season"]]
        post = g["type"] in POSTSEASON
        if g["rs"] > g["ra"]:
            r[3 if post else 0] += 1
        elif g["rs"] < g["ra"]:
            r[4 if post else 1] += 1
        elif not post:
            r[2] += 1
    return {k: [[y, *v] for y, v in sorted(years.items())] for k, years in sorted(acc.items())}
