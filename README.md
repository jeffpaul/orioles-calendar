# Orioles Calendar

Birthdays, debuts, trades, milestones and great games from franchise history, day by day: the Milwaukee Brewers (1901), the St. Louis Browns (1902–1953) and the Baltimore Orioles (1954–). Modelled on a friend's [White Sox calendar](https://sox-ink-calendar.vercel.app/).

The site is static: `site/index.html` plus five JSON files in `site/data/`, built offline by the Python pipeline in `pipeline/`. A scheduled GitHub Action rebuilds the data (daily in season, weekly in the off-season) and deploys `site/` to GitHub Pages.

## Run it locally

```sh
python -m pipeline.build           # downloads sources into .cache/, writes site/data/*.json
python -m pipeline.cards           # optional: share pages and preview images in site/day/ (needs Pillow)
python -m http.server -d site      # then open http://localhost:8000
python -m unittest discover -s tests -t .
```

Python 3.11+ with no third-party packages, except Pillow for the share cards. The first build downloads about 170 MB (Retrosheet team files, Baseball-Reference WAR tables, the Chadwick register) and makes a few hundred Stats API calls for the current season; later builds reuse `.cache/`. `--no-api` builds from Retrosheet alone.

## Where the data comes from

| Data | Source |
| --- | --- |
| Games, line scores, box-score lines, play-by-play (through the last published season) | Retrosheet team files for `MLA`, `SLA`, `BAL` |
| Current season games, box scores, play-by-play | MLB Stats API (team 110) |
| Upcoming schedule (spring training, regular season, postseason) | MLB Stats API schedule |
| Birth and death dates, names | Retrosheet biofile, Stats API for new players |
| Acquisitions | Retrosheet transactions database, Stats API transactions from 2022 |
| WAR | Baseball-Reference `war_daily_bat` and `war_daily_pitch` (franchise = `MLA`, `SLB`, `BAL`) |
| Career totals for milestones | Stats API career and year-by-year stats, walked game by game through franchise box scores |
| Player ID mapping | Chadwick Baseball Bureau register |
| Managers | Retrosheet box scores (`mgr` in `teamstats.csv`), Stats API coaching staff by date for the current season |
| Hall of Fame classes | Stats API `MLBHOF` award list; ceremony dates in `pipeline/config.py` |

Managing stints come from the manager listed for each game. When a manager hands the team to someone for fewer than 20 games and takes it back the same season (an ejection, a suspension, a sick day), those games count toward his stint and record, which matches the official totals (Earl Weaver 1,480–1,060). Hall of Fame induction days come from `HOF_CEREMONIES` in `pipeline/config.py`; when a new franchise member is elected, the build logs a reminder to add that class's ceremony date.

Clinch dates are computed from Retrosheet game logs (or Stats API schedules for the current season). The seasons to check are listed in `pipeline/config.py`; the build fails if the franchise didn't finish first in one of them. Hand-picked moments live in `pipeline/callouts.json` with a short `chip` label for day cells. The build fails unless the franchise played that day and each named player appeared (or, with `"check": "absent"`, sat out).

## Data files

- `players.json`: `id` (Retrosheet ID), `n` name, `b`/`x` birth and death dates, `a` acquisitions `{d, how, from}`, `y` franchise seasons as a player, `g` games, `p` positions, `w` [career WAR, franchise WAR], `mlbam`, `bbref`, `hof`, and `m` for managers: `{y, g, w, l, pw, pl}` seasons, regular-season games and record, postseason record. People who only managed have empty `y` and `p` and `g: 0`.
- `events.json`: `d` date, `t` type, `title`, `detail`, `ids` players, plus `gid`, `link` (box score), `opp` and `score` [franchise runs, opponent runs] for game events. `c: 1` marks a hand-picked moment. Manager events (`mgr_first`, `mgr_return`, `mgr_last`, `mgr_stint_end`, `mgr_milestone`) carry `n`, the games in that stint (or the win count for a milestone); stints under 100 games are scored as interim spells.
- `records.json`: `"MM-DD": [[year, W, L, T, postseason W, postseason L], …]`.
- `schedule.json`: the coming season's games once MLB publishes them, until its last game is final: `d` date, `t` game type (`S` spring training, `R` regular season, postseason codes), `home`, `opp`, `abbr`, `time` (Eastern, `null` when not yet set), `venue`, `status`, `pk` (MLB game ID), `score` [Orioles, opponent] once final, `split` for split-squad games.
- `meta.json`: build time, last game date, and which seasons came from which source.

`site/calendar.ics` and `site/calendar-orioles.ics` (1954 on) are subscribable iCalendar feeds: one all-day event per date, repeating yearly, titled with that date's most notable item. Routine debuts and lesser players' birthdays stay on the site only.

`site/day/MM-DD.html` is a shareable page for each date: its Open Graph tags carry a 1200×630 preview image (`site/day/MM-DD.png`) led by the date's best story, and it forwards visitors to that date on the calendar. `pipeline/cards.py` builds them at deploy time; they aren't committed. The "Share this day" button in the day panel links to them.

`pipeline/checks.py` runs before anything is written and fails the build on dangling player IDs, malformed dates, missing WAR, missing seasons, or record totals that don't match the games.

## Credits

The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at [www.retrosheet.org](https://www.retrosheet.org).
