# Orioles Calendar

Birthdays, debuts, trades, milestones and great games from franchise history, day by day: the Milwaukee Brewers (1901), the St. Louis Browns (1902–1953) and the Baltimore Orioles (1954–). Modelled on a friend's [White Sox calendar](https://sox-ink-calendar.vercel.app/).

The site is static: `site/index.html` plus four JSON files in `site/data/`, built offline by the Python pipeline in `pipeline/`. A scheduled GitHub Action rebuilds the data (daily in season, weekly in the off-season) and deploys `site/` to GitHub Pages.

## Run it locally

```sh
python -m pipeline.build           # downloads sources into .cache/, writes site/data/*.json
python -m http.server -d site      # then open http://localhost:8000
python -m unittest discover -s tests -t .
```

Python 3.11+ with no third-party packages. The first build downloads about 170 MB (Retrosheet team files, Baseball-Reference WAR tables, the Chadwick register) and makes a few hundred Stats API calls for the current season; later builds reuse `.cache/`. `--no-api` builds from Retrosheet alone.

## Where the data comes from

| Data | Source |
| --- | --- |
| Games, line scores, box-score lines, play-by-play (through the last published season) | Retrosheet team files for `MLA`, `SLA`, `BAL` |
| Current season games, box scores, play-by-play | MLB Stats API (team 110) |
| Birth and death dates, names | Retrosheet biofile, Stats API for new players |
| Acquisitions | Retrosheet transactions database, Stats API transactions from 2022 |
| WAR | Baseball-Reference `war_daily_bat` and `war_daily_pitch` (franchise = `MLA`, `SLB`, `BAL`) |
| Career totals for milestones | Stats API career and year-by-year stats, walked game by game through franchise box scores |
| Player ID mapping | Chadwick Baseball Bureau register |

Clinch dates are computed from Retrosheet game logs (or Stats API schedules for the current season). The seasons to check are listed in `pipeline/config.py`; the build fails if the franchise didn't finish first in one of them. Hand-picked moments live in `pipeline/callouts.json`, and each one is checked against box scores.

## Data files

- `players.json`: `id` (Retrosheet ID), `n` name, `b`/`x` birth and death dates, `a` acquisitions `{d, how, from}`, `y` franchise seasons, `g` games, `p` positions, `w` [career WAR, franchise WAR], `mlbam`, `bbref`, `hof`.
- `events.json`: `d` date, `t` type, `title`, `detail`, `ids` players, plus `gid`, `link` (box score), `opp` and `score` [franchise runs, opponent runs] for game events. `c: 1` marks a hand-picked moment.
- `records.json`: `"MM-DD": [[year, W, L, T, postseason W, postseason L], …]`.
- `meta.json`: build time, last game date, and which seasons came from which source.

`site/calendar.ics` and `site/calendar-orioles.ics` (1954 on) are subscribable iCalendar feeds: one all-day event per date, repeating yearly, titled with that date's most notable item. Routine debuts and lesser players' birthdays stay on the site only.

`pipeline/checks.py` runs before anything is written and fails the build on dangling player IDs, malformed dates, missing WAR, missing seasons, or record totals that don't match the games.

## Credits

The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at [www.retrosheet.org](https://www.retrosheet.org).
