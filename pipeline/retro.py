"""Retrosheet loaders. Each returns rows in the pipeline's normalized shapes.

The information used here was obtained free of charge from and is
copyrighted by Retrosheet. Interested parties may contact Retrosheet at
www.retrosheet.org.
"""

import csv
import io
import re
import zipfile
from collections import defaultdict

from . import config, sources

POSITIONS = [("g_p", "P"), ("g_c", "C"), ("g_1b", "1B"), ("g_2b", "2B"), ("g_3b", "3B"), ("g_ss", "SS"),
             ("g_lf", "LF"), ("g_cf", "CF"), ("g_rf", "RF"), ("g_dh", "DH"), ("g_ph", "PH"), ("g_pr", "PR")]


def iso(yyyymmdd):
    """'19660409' -> '1966-04-09'; '19660400' -> '1966-04'; '19660000' -> '1966'."""
    s = (yyyymmdd or "").strip().strip('"')
    if len(s) != 8 or not s.isdigit():
        return None
    y, m, d = s[:4], s[4:6], s[6:]
    if m == "00":
        return y
    if d == "00":
        return f"{y}-{m}"
    return f"{y}-{m}-{d}"


def _rows(zf, member):
    with zf.open(member) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def team_zips():
    return {code: zipfile.ZipFile(sources.fetch(sources.RETROSHEET_TEAM.format(code=code), f"retrosheet/{code}.zip"))
            for code in config.RETRO_TEAMS}


def load_bio():
    zf = zipfile.ZipFile(sources.fetch(sources.RETROSHEET_BIO, "retrosheet/biodata.zip"))
    people = {r["id"]: r for r in _rows(zf, "biofile0.csv")}
    teams = {r["team"]: r for r in _rows(zf, "teams0.csv")}
    parks = {r["site"]: r for r in _rows(zf, "ballparks0.csv")}
    return people, teams, parks


def opponent_codes(zips):
    codes = set()
    for code, zf in zips.items():
        for r in _rows(zf, "gameinfo.csv"):
            codes.update((r["visteam"], r["hometeam"]))
    return codes


def opponent_names(teams, codes):
    """Retrosheet team code -> display name. City alone, unless two of the
    franchise's opponents share the city."""
    mlb = {code: t for code, t in teams.items() if code in codes}
    by_city = defaultdict(set)
    for code, t in mlb.items():
        by_city[t["city"]].add(code)
    names = {}
    for code, t in mlb.items():
        names[code] = t["city"]
    for city, codes in by_city.items():
        if len(codes) > 1:
            for code in codes:
                names[code] = f"{city} {mlb[code]['nickname']}".strip()
    # Fix up shared-city codes whose current nickname doesn't fit history.
    names.update({"NYA": "New York Yankees", "NYN": "New York Mets", "CHA": "Chicago White Sox",
                  "CHN": "Chicago Cubs", "SLN": "St. Louis Cardinals", "SLA": "St. Louis Browns",
                  "BOS": "Boston", "BSN": "Boston Braves", "PHA": "Philadelphia Athletics",
                  "PHI": "Philadelphia Phillies", "LAN": "Los Angeles Dodgers", "ANA": "Los Angeles Angels",
                  "CAL": "California", "LAA": "Los Angeles Angels", "OAK": "Oakland", "ATH": "Athletics",
                  "WS1": "Washington", "WS2": "Washington", "WAS": "Washington", "SFN": "San Francisco",
                  "SDN": "San Diego", "KCA": "Kansas City", "KC1": "Kansas City Athletics"})
    return names


def load_games(zips, opp_names):
    """Franchise games, bat lines, pitch lines and appearances from the team zips."""
    games, bats, pits, apps = [], [], [], defaultdict(list)
    for code, zf in zips.items():
        info = {r["gid"]: r for r in _rows(zf, "gameinfo.csv")}
        stats = defaultdict(dict)
        for r in _rows(zf, "teamstats.csv"):
            if r["stattype"] == "value":
                stats[r["gid"]][r["team"]] = r
        for gid, g in info.items():
            us_code = code if code in (g["visteam"], g["hometeam"]) else None
            if not us_code or g["gametype"] not in ("regular", "worldseries", "lcs", "divisionseries", "wildcard"):
                continue
            home = g["hometeam"] == us_code
            opp = g["visteam"] if home else g["hometeam"]
            us, them = stats[gid].get(us_code), stats[gid].get(opp)
            if not us or not them:
                continue
            line = lambda r: [int(r[f"inn{i}"]) for i in range(1, 29) if r[f"inn{i}"].lstrip("-").isdigit()]
            games.append({
                "gid": gid, "date": iso(g["date"]), "num": _int(g["number"]), "type": g["gametype"],
                "season": int(g["season"]), "team": us_code, "home": home, "opp": opp,
                "opp_name": opp_names.get(opp, opp),
                "rs": _int(us["b_r"]), "ra": _int(them["b_r"]),
                "line_us": line(us), "line_them": line(them),
                "innings": max(len(line(us)), len(line(them))),
                "site": g["site"], "tp": _int(us["d_tp"]), "mgr": us["mgr"] or None,
                "p_h": _int(us["p_h"]), "p_bfp": _int(us["p_bfp"]), "p_outs": _int(us["p_ipouts"]),
                "link": f"https://www.baseball-reference.com/boxes/{gid[:3]}/{gid}.shtml",
                "src": "retrosheet",
            })
        for r in _rows(zf, "batting.csv"):
            if r["team"] == code and r["stattype"] == "value" and r["gid"] in info:
                d = iso(r["date"])
                bats.append({"gid": r["gid"], "date": d, "season": int(r["date"][:4]), "pid": r["id"],
                             "h": _int(r["b_h"]), "d": _int(r["b_d"]), "t": _int(r["b_t"]), "hr": _int(r["b_hr"]),
                             "type": r["gametype"]})
                apps[r["id"]].append((d, r["gid"]))
        for r in _rows(zf, "pitching.csv"):
            if r["team"] == code and r["stattype"] == "value" and r["gid"] in info:
                d = iso(r["date"])
                pits.append({"gid": r["gid"], "date": d, "season": int(r["date"][:4]), "pid": r["id"],
                             "outs": _int(r["p_ipouts"]), "h": _int(r["p_h"]), "k": _int(r["p_k"]),
                             "win": r["wp"] == "1", "type": r["gametype"]})
                apps[r["id"]].append((d, r["gid"]))
        for r in _rows(zf, "fielding.csv"):
            if r["team"] == code and r["stattype"] == "value" and r["gid"] in info:
                apps[r["id"]].append((iso(r["date"]), r["gid"]))
    return games, bats, pits, apps


def load_rosters(zips):
    """Per player: franchise seasons, games and games by position."""
    out = defaultdict(lambda: {"seasons": set(), "g": 0, "pos": defaultdict(int)})
    for code, zf in zips.items():
        for r in _rows(zf, "allplayers.csv"):
            if r["team"] != code:
                continue
            p = out[r["id"]]
            p["seasons"].add(int(r["season"]))
            p["g"] += _int(r["g"])
            for col, pos in POSITIONS:
                p["pos"][pos] += _int(r[col])
    return out


IPHR = re.compile(r"^HR?\d|IPHR")


def load_plays(zips, franchise_games):
    """Walk-off batters and inside-the-park homers from play-by-play.

    Returns ({gid: (batter, kind)}, [(gid, batter)]).
    """
    ours = {g["gid"]: g for g in franchise_games}
    last_play, itp = {}, []
    for code, zf in zips.items():
        if "plays.csv" not in zf.namelist():
            continue
        with zf.open("plays.csv") as f:
            reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
            h = {k: i for i, k in enumerate(next(reader))}
            for row in reader:
                gid = row[h["gid"]]
                if gid not in ours or row[h["batteam"]] != code:
                    continue
                if row[h["hr"]] == "1" and IPHR.search(row[h["event"]]):
                    itp.append((gid, row[h["batter"]]))
                if row[h["vis_home"]] == "1" and _int(row[h["runs"]]) > 0:
                    kind = ("home run" if row[h["hr"]] == "1" else "triple" if row[h["triple"]] == "1"
                            else "double" if row[h["double"]] == "1" else "single" if row[h["single"]] == "1"
                            else "walk" if row[h["walk"]] == "1" or row[h["iw"]] == "1"
                            else "sacrifice fly" if row[h["sf"]] == "1" else "other")
                    last_play[gid] = (row[h["batter"]], kind)
    return last_play, itp


def load_transactions():
    """Franchise acquisitions: {retro_id: [(date, type, from_team)]}."""
    zf = zipfile.ZipFile(sources.fetch(sources.RETROSHEET_TRANSACTIONS, "retrosheet/tranDB.zip", max_age_hours=24 * 7))
    acquire = {"T", "Tp", "P", "F", "Fa", "Fb", "Fo", "W", "Wf", "D", "Da", "X", "Xe", "Xm", "Xp", "V", "A", "C", "J", "M"}
    out = defaultdict(list)
    with zf.open("tran.txt") as f:
        for row in csv.reader(io.TextIOWrapper(f, encoding="latin-1")):
            if len(row) < 11:
                continue
            date, player, typ, frm, to = row[0], row[6], row[7].strip(), row[8], row[10]
            if to not in config.RETRO_TEAMS or typ not in acquire or not re.fullmatch(r"[a-z0-9-]{8}", player or ""):
                continue
            lo, hi = config.RETRO_TEAMS[to]
            d = iso(date)
            if d and lo <= int(d[:4]) + (1 if date[4:] == "0000" else 0) <= hi + 1:
                out[player].append((d, typ, frm))
    return out


def load_gamelog(year):
    """League-wide results for one season: [(date, num, vis, home, vscore, hscore, vislg, homelg)]."""
    zf = zipfile.ZipFile(sources.fetch(sources.RETROSHEET_GAMELOG.format(year=year), f"retrosheet/gl{year}.zip",
                                       max_age_hours=24 * 30))
    name = next(n for n in zf.namelist() if n.upper().endswith(".TXT"))
    out = []
    with zf.open(name) as f:
        for row in csv.reader(io.TextIOWrapper(f, encoding="latin-1")):
            out.append((iso(row[0]), _int(row[1]), row[3], row[6], _int(row[9]), _int(row[10]), row[4], row[7]))
    return out
