"""MLB Stats API loaders for seasons Retrosheet hasn't published yet."""

import hashlib
from collections import defaultdict

from . import config, sources

GAME_TYPES = {"R": "regular", "F": "wildcard", "D": "divisionseries", "L": "lcs", "W": "worldseries"}
FINAL_AGE = 24 * 365  # a final game's box score never changes
ACQUIRE_CODES = {"TR", "SFA", "CLW", "PUR", "R5", "DR"}


def _digest(s):
    return hashlib.sha1(s.encode()).hexdigest()[:12]


def season_games(season, ids, team_names):
    """Franchise games, bat lines, pitch lines, appearances, walk-offs and
    inside-the-park homers for one season, in the same shapes as retro.py."""
    sched = sources.statsapi("/schedule", sportId=1, teamId=config.MLB_TEAM_ID, season=season,
                             gameType="R,F,D,L,W", hydrate="linescore,team")
    games, bats, pits, apps = [], [], [], defaultdict(list)
    walkoffs, itp, positions = {}, [], defaultdict(lambda: defaultdict(int))
    for day in sched.get("dates", []):
        for g in day["games"]:
            if g["status"]["detailedState"] not in ("Final", "Completed Early", "Game Over"):
                continue
            pk = g["gamePk"]
            home = g["teams"]["home"]["team"]["id"] == config.MLB_TEAM_ID
            us_side, them_side = ("home", "away") if home else ("away", "home")
            opp = g["teams"][them_side]["team"]
            innings = g.get("linescore", {}).get("innings", [])
            line = lambda side: [inn.get(side, {}).get("runs") for inn in innings if inn.get(side, {}).get("runs") is not None]
            gid = f"mlb{pk}"
            date = g["officialDate"]
            box = sources.statsapi(f"/game/{pk}/boxscore", name=f"statsapi/box_{pk}", max_age_hours=FINAL_AGE)
            pbp = sources.statsapi(f"/game/{pk}/playByPlay", name=f"statsapi/pbp_{pk}", max_age_hours=FINAL_AGE)
            us_team = box["teams"][us_side]
            them_team = box["teams"][them_side]
            games.append({
                "gid": gid, "date": date, "num": g.get("gameNumber", 1) if g.get("doubleHeader") != "N" else 0,
                "type": GAME_TYPES[g["gameType"]], "season": season, "team": "BAL", "home": home,
                "opp": opp.get("abbreviation", str(opp["id"])), "opp_name": team_names.get(opp["id"], opp["name"]),
                "rs": g["teams"][us_side].get("score", 0), "ra": g["teams"][them_side].get("score", 0),
                "line_us": line(us_side), "line_them": line(them_side), "innings": len(innings),
                "site": str(g["venue"]["id"]), "site_name": g["venue"]["name"],
                "tp": 0, "p_h": them_team["teamStats"]["batting"].get("hits", 0),
                "p_bfp": us_team["teamStats"]["pitching"].get("battersFaced", 0),
                "p_outs": us_team["teamStats"]["pitching"].get("outs", 0),
                "link": f"https://www.mlb.com/gameday/{pk}", "src": "statsapi",
            })
            for key, p in us_team["players"].items():
                pid = ids(p["person"]["id"])
                st = p.get("stats", {})
                b, pi, f = st.get("batting") or {}, st.get("pitching") or {}, st.get("fielding") or {}
                if not (b or pi or f):
                    continue
                apps[pid].append((date, gid))
                for pos in p.get("allPositions", []):
                    positions[pid][pos["abbreviation"]] += 1
                if b:
                    bats.append({"gid": gid, "date": date, "season": season, "pid": pid, "h": b.get("hits", 0),
                                 "d": b.get("doubles", 0), "t": b.get("triples", 0), "hr": b.get("homeRuns", 0),
                                 "type": GAME_TYPES[g["gameType"]]})
                if pi:
                    pits.append({"gid": gid, "date": date, "season": season, "pid": pid, "outs": pi.get("outs", 0),
                                 "h": pi.get("hits", 0), "k": pi.get("strikeOuts", 0), "win": pi.get("wins", 0) > 0,
                                 "type": GAME_TYPES[g["gameType"]]})
            us_batting = "bottom" if home else "top"
            for play in pbp.get("allPlays", []):
                res = play.get("result", {})
                half = play.get("about", {}).get("halfInning")
                if res.get("eventType") == "triple_play" and half != us_batting:
                    games[-1]["tp"] += 1
                if half != us_batting:
                    continue
                batter = ids(play["matchup"]["batter"]["id"])
                if res.get("eventType") == "home_run" and "inside-the-park" in res.get("description", "").lower():
                    itp.append((gid, batter))
                if home and play.get("about", {}).get("isScoringPlay"):
                    kind = {"home_run": "home run", "triple": "triple", "double": "double", "single": "single",
                            "walk": "walk", "intent_walk": "walk", "sac_fly": "sacrifice fly"}.get(res.get("eventType"), "other")
                    walkoffs[gid] = (batter, kind)
    return games, bats, pits, apps, walkoffs, itp, positions


def team_names(season):
    data = sources.statsapi("/teams", sportId=1, season=season, max_age_hours=24 * 7)
    return {t["id"]: t["name"] for t in data["teams"]}


def people(mlbam_ids):
    """Bio rows from the Stats API, in batches of 100."""
    out = {}
    ids = sorted(set(mlbam_ids))
    for i in range(0, len(ids), 100):
        chunk = ",".join(map(str, ids[i:i + 100]))
        data = sources.statsapi("/people", name=f"statsapi/people_{_digest(chunk)}", max_age_hours=24 * 7,
                                personIds=chunk)
        for p in data.get("people", []):
            out[p["id"]] = p
    return out


def career_totals(mlbam_ids):
    """{mlbam: {"hits":, "homeRuns":, "wins":, "strikeOuts":}} career totals."""
    out = {}
    ids = sorted(set(mlbam_ids))
    for i in range(0, len(ids), 100):
        chunk = ",".join(map(str, ids[i:i + 100]))
        data = sources.statsapi("/people", name=f"statsapi/career_{_digest(chunk)}", max_age_hours=24,
                                personIds=chunk, hydrate="stats(group=[hitting,pitching],type=[career])")
        for p in data.get("people", []):
            t = {}
            for s in p.get("stats", []):
                stat = s["splits"][0]["stat"] if s.get("splits") else {}
                if s["group"]["displayName"] == "hitting":
                    t["hits"], t["homeRuns"] = stat.get("hits", 0), stat.get("homeRuns", 0)
                else:
                    t["wins"], t["strikeOuts"] = stat.get("wins", 0), stat.get("strikeOuts", 0)
            out[p["id"]] = t
    return out


def year_by_year(mlbam, group):
    """Season splits in API order: [(season, team_id or None, stat)]."""
    data = sources.statsapi(f"/people/{mlbam}/stats", name=f"statsapi/yby_{mlbam}_{group}", max_age_hours=24,
                            stats="yearByYear", group=group, sportId=1)
    out = []
    for s in data.get("stats", []):
        for sp in s.get("splits", []):
            if sp.get("sport", {}).get("id", 1) != 1:
                continue
            out.append((int(sp["season"]), sp.get("team", {}).get("id"), sp["stat"]))
    return out


def transactions(first_year, last_year):
    """Franchise acquisitions from the Stats API: {mlbam: [(date, code, from_team)]}."""
    out = defaultdict(list)
    for year in range(first_year, last_year + 1):
        data = sources.statsapi("/transactions", name=f"statsapi/transactions_{year}", max_age_hours=24,
                                teamId=config.MLB_TEAM_ID, startDate=f"{year}-01-01", endDate=f"{year}-12-31")
        for t in data.get("transactions", []):
            if t.get("toTeam", {}).get("id") != config.MLB_TEAM_ID or "person" not in t:
                continue
            code = t.get("typeCode")
            if code in ACQUIRE_CODES or "Rule 5" in t.get("typeDesc", ""):
                out[t["person"]["id"]].append((t["date"], code, t.get("fromTeam", {}).get("name", "")))
    return out


def standings_clinched(season):
    """True if the franchise clinched its division this season."""
    data = sources.statsapi("/standings", leagueId=103, season=season)
    for rec in data.get("records", []):
        for t in rec["teamRecords"]:
            if t["team"]["id"] == config.MLB_TEAM_ID:
                return t.get("clinchIndicator") in ("z", "y") and t.get("divisionRank") == "1"
    return False


def division_results(season):
    """AL East results for clinch math: [(date, num, vis, home, vscore, hscore)]."""
    data = sources.statsapi("/standings", leagueId=103, season=season)
    division = next(rec for rec in data["records"]
                    if any(t["team"]["id"] == config.MLB_TEAM_ID for t in rec["teamRecords"]))
    out = []
    for t in division["teamRecords"]:
        sched = sources.statsapi("/schedule", name=f"statsapi/sched_{t['team']['id']}_{season}", sportId=1,
                                 teamId=t["team"]["id"], season=season, gameType="R")
        for day in sched["dates"]:
            for g in day["games"]:
                if g["status"]["abstractGameState"] == "Final" and "score" in g["teams"]["home"]:
                    out.append((g["officialDate"], g["gamePk"], str(g["teams"]["away"]["team"]["id"]),
                                str(g["teams"]["home"]["team"]["id"]), g["teams"]["away"]["score"],
                                g["teams"]["home"]["score"]))
    return sorted(set(out)), [str(t["team"]["id"]) for t in division["teamRecords"]]
