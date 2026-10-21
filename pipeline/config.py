"""Franchise facts the pipeline can't derive from the data itself."""

MLB_TEAM_ID = 110
SITE_URL = "https://jeffpaul.github.io/orioles-calendar/"

# Retrosheet team codes for the franchise, with the seasons each was used.
RETRO_TEAMS = {"MLA": (1901, 1901), "SLA": (1902, 1953), "BAL": (1954, 9999)}
# Baseball-Reference team codes, used by the WAR tables.
BREF_TEAMS = {"MLA", "SLB", "BAL"}

ERAS = [
    {"key": "brewers", "name": "Milwaukee Brewers", "short": "Brewers", "first": 1901, "last": 1901},
    {"key": "browns", "name": "St. Louis Browns", "short": "Browns", "first": 1902, "last": 1953},
    {"key": "orioles", "name": "Baltimore Orioles", "short": "Orioles", "first": 1954, "last": 9999},
]


def era_for(year):
    return next(e for e in ERAS if e["first"] <= year <= e["last"])


def nickname(year):
    return era_for(year)["short"]


# Seasons the franchise won its division, and pre-1969 seasons it won the
# pennant outright. Clinch dates are computed from game logs; build.py
# fails if the franchise didn't actually finish first in a listed season.
DIVISION_TITLES = [1969, 1970, 1971, 1973, 1974, 1979, 1983, 1997, 2014, 2023]
PENNANTS_BEFORE_LCS = [1944, 1966]

# AL East membership by season range, in Retrosheet codes.
AL_EAST = [
    ((1969, 1971), ["BAL", "BOS", "CLE", "DET", "NYA", "WS2"]),
    ((1972, 1976), ["BAL", "BOS", "CLE", "DET", "MIL", "NYA"]),
    ((1977, 1993), ["BAL", "BOS", "CLE", "DET", "MIL", "NYA", "TOR"]),
    ((1994, 1997), ["BAL", "BOS", "DET", "NYA", "TOR"]),
    ((1998, 9999), ["BAL", "BOS", "NYA", "TBA", "TOR"]),
]


def al_east(year):
    return next(teams for (lo, hi), teams in AL_EAST if lo <= year <= hi)


# Round-number career totals that count as milestones when reached in a
# franchise uniform.
CAREER_THRESHOLDS = {
    "hits": [2000, 2500, 3000],
    "homeRuns": [300, 400, 500],
    "wins": [200, 250, 300],
    "strikeOuts": [2000, 2500, 3000],
}

# Thresholds for single-game events.
LONG_GAME_INNINGS = 18
BIG_WIN_MARGIN = 15
STRIKEOUT_GAME = 15
HOMER_GAME = 3

# Franchise wins as manager that count as milestones.
MANAGER_WIN_THRESHOLDS = {500, 1000, 1500}

# Hall of Fame induction ceremonies, by class: (ceremony date, ceremony year).
# Checked against each year's Wikipedia "Baseball Hall of Fame balloting"
# article. Only classes with a franchise member are listed; a new one logs
# a reminder at build time. None means no ceremony on record (wartime
# classes), so no calendar event.
HOF_CEREMONIES = {
    1939: ("1939-06-12", 1939), 1942: None, 1945: None, 1946: ("1947-07-21", 1947),
    1953: ("1953-07-27", 1953), 1964: ("1964-07-27", 1964), 1967: ("1967-07-24", 1967),
    1968: ("1968-07-22", 1968), 1971: ("1971-08-09", 1971), 1974: ("1974-08-12", 1974),
    1976: ("1976-08-09", 1976), 1982: ("1982-08-01", 1982), 1983: ("1983-07-31", 1983),
    1984: ("1984-08-12", 1984), 1985: ("1985-07-28", 1985), 1990: ("1990-08-06", 1990),
    1993: ("1993-08-01", 1993), 1996: ("1996-08-04", 1996), 2003: ("2003-07-27", 2003),
    2006: ("2006-07-30", 2006), 2007: ("2007-07-29", 2007), 2008: ("2008-07-27", 2008),
    2010: ("2010-07-25", 2010), 2011: ("2011-07-24", 2011), 2017: ("2017-07-30", 2017),
    2018: ("2018-07-29", 2018), 2019: ("2019-07-21", 2019),
}
