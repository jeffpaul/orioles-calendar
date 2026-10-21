(() => {
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
                  "August", "September", "October", "November", "December"];
  const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const ORIOLES_FIRST = 1954;
  const KINDS = ["m", "g", "d", "b", "a", "x"];
  const KIND_HEADINGS = {
    m: "On this day in franchise history", g: "Games to remember", d: "Debuts & final games",
    b: "Birthdays", a: "Acquired on this date", x: "Died on this date",
  };
  const TYPE_KIND = {
    walk_off: "g", inside_the_park_hr: "g", triple_play: "g", long_game: "g", big_win: "g",
    three_homer_game: "g", strikeout_game: "g", ballpark_first: "g", ballpark_last: "g",
    debut: "d", final_game: "d",
  };
  // How interesting each event type is, used to pick which items a day cell shows.
  const TYPE_SCORE = {
    world_series: 95, pennant: 90, division_title: 85, perfect_game: 85, callout: 80, no_hitter: 75,
    four_homer_game: 75, career_milestone: 70, series_win: 65, cycle: 60, ballpark_first: 55, ballpark_last: 50,
    three_homer_game: 45, strikeout_game: 45, long_game: 40, triple_play: 40, big_win: 35, walk_off: 30,
    inside_the_park_hr: 28,
  };
  const HOW = {
    T: "Trade", Tp: "Added to a trade", P: "Purchase", F: "Free agent signing", Fa: "Amateur free agent",
    Fb: "Bonus baby signing", Fo: "Free agent signing", W: "Waiver claim", Wf: "Waiver claim", D: "Rule 5 draft",
    Da: "Amateur draft", X: "Expansion draft", Xe: "Expansion draft", Xm: "Expansion draft", Xp: "Expansion draft",
    V: "Assigned by the league", A: "Assigned", C: "Conditional deal", J: "Jumped leagues", M: "Working agreement",
    TR: "Trade", SFA: "Free agent signing", CLW: "Waiver claim", PUR: "Purchase", R5: "Rule 5 draft", DR: "Draft",
  };
  const FULL_DATE = /^\d{4}-\d{2}-\d{2}$/;

  const $ = id => document.getElementById(id);
  const pad = n => String(n).padStart(2, "0");
  const isLeap = y => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
  const esc = s => String(s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const ordinal = n => {
    const s = ["th", "st", "nd", "rd"], v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
  };
  const fmtDate = iso => {
    const [y, m, d] = iso.split("-").map(Number);
    if (!m) return `${y} (date unknown)`;
    if (!d) return `${MONTHS[m - 1]} ${y} (day unknown)`;
    return `${MONTHS[m - 1].slice(0, 3)} ${d}, ${y}`;
  };
  const yearsAgo = n => n === 0 ? "This year" : n === 1 ? "1 year ago" : `${n} years ago`;
  const span = years => years[0] === years.at(-1) ? String(years[0]) : `${years[0]}–${years.at(-1)}`;
  const eraOf = year => year < 1902 ? "Brewers" : year < ORIOLES_FIRST ? "Browns" : "";
  const ERAS = ["Brewers", "Browns", "Orioles"];
  const eraName = year => eraOf(year) || "Orioles";
  const eraTag = year => eraOf(year) ? `<span class="era">${eraOf(year)}</span>` : "";
  const playerUrl = p => p.bbref
    ? `https://www.baseball-reference.com/players/${p.bbref[0]}/${p.bbref}.shtml`
    : p.mlbam ? `https://www.mlb.com/player/${p.mlbam}` : null;
  const war = p => (p.w || [null, null])[1];

  let players = [], events = [], records = {}, meta = {}, schedule = new Map();
  let playerById = new Map(), byDay = new Map(), eventsByPlayer = new Map(), searchIndex = [];
  const now = new Date();
  const todayKey = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}`;
  const show = { s: true, m: true, g: true, d: true, b: true, a: true, x: false };
  const eras = new Set(ERAS);  // franchise eras to show, all by default
  let view = { year: now.getFullYear(), month: now.getMonth() };
  let selected = { year: now.getFullYear(), month: now.getMonth(), day: now.getDate() };
  let focusPlayer = null;

  // Index -------------------------------------------------------------------

  function score(item) {
    if (item.event) return TYPE_SCORE[item.event.t] ??
      10 + Math.min(40, Math.max(0, (war(item.player || {}) || 0) * 1.5));
    const w = Math.max(0, war(item.player) || 0);
    const base = { b: 8, a: 6, x: 5 }[item.kind];
    return base + Math.min(item.kind === "b" ? 45 : 30, w * 1.5) + (item.player.hof ? 15 : 0);
  }

  function addItem(date, kind, extra) {
    if (!FULL_DATE.test(date)) return;  // month- or year-only dates can't be placed
    const key = date.slice(5);
    if (!byDay.has(key)) byDay.set(key, []);
    const item = { kind, year: +date.slice(0, 4), date, ...extra };
    item.score = score(item);
    byDay.get(key).push(item);
  }

  function buildIndex() {
    playerById = new Map(players.map(p => [p.id, p]));
    for (const p of players) {
      if (p.b) addItem(p.b, "b", { player: p });
      for (const a of p.a || []) addItem(a.d, "a", { player: p, acq: a });
      if (p.x) addItem(p.x, "x", { player: p });
    }
    for (const e of events) {
      const kind = e.c ? "m" : TYPE_KIND[e.t] || "m";
      const player = e.ids.length === 1 ? playerById.get(e.ids[0]) : null;
      addItem(e.d, kind, { event: e, player });
      for (const id of e.ids) {
        if (!eventsByPlayer.has(id)) eventsByPlayer.set(id, []);
        eventsByPlayer.get(id).push(e);
      }
    }
    const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    searchIndex = players.map(p => [norm(p.n), p]);
    searchIndex.norm = norm;
  }

  // Is an item inside the selected eras? Birthdays and deaths belong to every
  // era the player played in; everything else to the era it happened in.
  const allEras = () => eras.size === ERAS.length;
  const playedIn = p => p.y.some(y => eras.has(eraName(y)));
  function inEra(item) {
    if (allEras()) return true;
    if (item.kind === "b" || item.kind === "x") return playedIn(item.player);
    return eras.has(eraName(item.year));
  }
  // " in Browns and Orioles years", for sentences that count only some eras.
  const eraNote = () => allEras() ? "" : ` in ${ERAS.filter(e => eras.has(e)).join(" and ")} years`;

  function itemsOn(year, month, day) {
    const key = `${pad(month + 1)}-${pad(day)}`;
    let list = (byDay.get(key) || []).slice();
    if (month === 1 && day === 28 && !isLeap(year)) list = list.concat(byDay.get("02-29") || []);
    return groupRoutine(list.filter(i => i.year <= year && show[i.kind] && inEra(i)))
      .sort((x, y) => y.score - x.score || x.year - y.year);
  }

  // A player is notable enough for his own debut or final-game line with
  // this much franchise WAR, or a Hall of Fame plaque.
  const NOTABLE_WAR = 5;
  const isNotable = p => p && (p.hof || (war(p) || 0) >= NOTABLE_WAR);

  // Fold each date's debuts (or final games) of non-notable players, across
  // all seasons, into one line, so September call-ups don't bury the rare moments.
  function groupRoutine(items) {
    const out = [], groups = new Map();
    for (const i of items) {
      const t = i.event?.t;
      if ((t !== "debut" && t !== "final_game") || isNotable(i.player)) { out.push(i); continue; }
      const key = t;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(i);
    }
    for (const members of groups.values()) {
      if (members.length === 1) { out.push(members[0]); continue; }
      members.sort((x, y) => x.year - y.year);
      const best = Math.max(...members.map(m => m.score));
      out.push({ ...members.at(-1), group: members, score: best });
    }
    return out;
  }

  const groupTitle = item => `${item.group.length} players ${item.event.t === "debut"
    ? "made their franchise debut" : "played their final franchise game"} on this date`;

  function recordOn(year, month, day) {
    const r = { w: 0, l: 0, t: 0, pw: 0, pl: 0 };
    for (const [y, w, l, t, pw, pl] of records[`${pad(month + 1)}-${pad(day)}`] || []) {
      if (y > year) break;
      if (!eras.has(eraName(y))) continue;
      r.w += w; r.l += l; r.t += t; r.pw += pw; r.pl += pl;
    }
    r.games = r.w + r.l + r.t + r.pw + r.pl;
    return r;
  }
  const wl = (w, l, t) => `${w}–${l}${t ? `–${t}` : ""}`;
  const pct = (w, l) => w + l ? (w / (w + l)).toFixed(3).replace(/^0/, "") : "";

  // Labels --------------------------------------------------------------------

  const lastName = id => (playerById.get(id)?.n || "").replace(/ (Jr\.|Sr\.|II|III)$/, "").split(" ").at(-1);

  function chipLabel(item) {
    const e = item.event;
    if (!e) return item.player.n;
    if (item.group) return `${item.group.length} ${e.t === "debut" ? "debuts" : "final games"}`;
    if (e.c) return e.chip || e.title.split(",")[0];
    const who = e.ids.map(lastName).filter(Boolean);
    const short = {
      no_hitter: "No-hitter", perfect_game: "Perfect game", cycle: "Cycle", four_homer_game: "4 HR game",
      three_homer_game: "3 HR game", walk_off: "Walk-off", inside_the_park_hr: "Inside-the-park HR",
      triple_play: "Triple play", debut: "Debut", final_game: "Final game",
      strikeout_game: `${(e.title.match(/\d+$/) || [""])[0]} K`,
      long_game: (e.title.match(/\d+-inning game/) || ["Long game"])[0],
      big_win: e.title.replace(/^\S+ win/, "Won"),
      career_milestone: e.title.replace(/^.* (gets|hits|earns|records) his /, "").replace(" career ", " "),
      world_series: "World Series title", pennant: "Pennant", division_title: "Division title",
      series_win: e.title.replace(/^\S+ win the \d+ /, "Won "),
      ballpark_first: "First game at " + e.title.replace(/^First \S+ home game at /, ""),
      ballpark_last: "Last game at " + e.title.replace(/^Last \S+ home game at /, ""),
    }[e.t] || e.title;
    const teamOnly = ["world_series", "pennant", "division_title", "series_win", "long_game", "big_win",
                      "ballpark_first", "ballpark_last", "triple_play"];
    return teamOnly.includes(e.t) || !who.length ? short : `${short}: ${who.join("/")}`;
  }

  const warText = (p, short) => {
    const [career, ours] = p.w || [];
    if (ours == null) return "";
    if (short) return `${ours.toFixed(1)} WAR`;
    return career != null && career !== ours
      ? `${ours.toFixed(1)} WAR with the franchise (${career.toFixed(1)} career)`
      : `${ours.toFixed(1)} WAR`;
  };
  const nameLink = p => {
    const url = playerUrl(p);
    return url ? `<a href="${url}" target="_blank" rel="noopener">${esc(p.n)}</a>` : esc(p.n);
  };

  // Schedule ------------------------------------------------------------------

  const SCHEDULE_TYPES = { S: "Spring training", R: "Regular season", F: "Wild Card Series",
                           D: "Division Series", L: "ALCS", W: "World Series" };
  const gamesOn = (year, month, day) => show.s && eras.has("Orioles") ? schedule.get(`${year}-${pad(month + 1)}-${pad(day)}`) || [] : [];
  const gameResult = g => {
    const [us, them] = g.score;
    return `${us > them ? "W" : us < them ? "L" : "T"} ${us}–${them}`;
  };
  const gameChip = g => `${g.home ? "vs" : "@"} ${g.abbr || g.opp}` +
    (g.score ? ` ${gameResult(g)}` : g.status !== "Scheduled" ? ` (${g.status.toLowerCase()})` : g.time ? ` ${g.time.replace(":00", "").replace(" PM", "p").replace(" AM", "a")}` : "");
  const gameText = g => {
    const when = g.score ? gameResult(g) : g.status !== "Scheduled" ? g.status
      : g.time ? `${g.time} ET` : "Time to be announced";
    return `${g.home ? "vs" : "at"} ${g.opp} · ${when}`;
  };
  const gameMeta = g => [SCHEDULE_TYPES[g.t] || "", g.split ? "split squad" : "", g.venue, g.note && !g.note.startsWith("at ") ? g.note : ""]
    .filter(Boolean).join(" · ");
  const gameLink = g => `https://www.mlb.com/gameday/${g.pk}`;

  // Rendering -------------------------------------------------------------------

  const grid = $("grid"), panel = $("panel"), title = $("title");
  const monthSel = $("month"), yearInput = $("year");
  MONTHS.forEach((m, i) => monthSel.add(new Option(m, i)));

  // Shade a day by its best game or milestone: 0 nothing shown, 1 only
  // people (birthdays, debuts, trades), 2 a memorable game, 3 a milestone,
  // 4 a title, no-hitter or hand-picked moment.
  const HEAT_STEPS = [28, 60, 75];
  const heatLevel = items => {
    if (!items.length) return 0;
    const best = Math.max(0, ...items.filter(i => i.kind === "m" || i.kind === "g").map(i => i.score));
    return best ? 1 + HEAT_STEPS.filter(s => best >= s).length : 1;
  };

  function renderGrid() {
    title.textContent = `${MONTHS[view.month]} ${view.year}`;
    monthSel.value = view.month;
    yearInput.value = view.year;
    const first = new Date(view.year, view.month, 1).getDay();
    const days = new Date(view.year, view.month + 1, 0).getDate();
    const parts = DOW.map(d => `<div class="dow" role="columnheader">${d}</div>`);
    for (let i = 0; i < first; i++) parts.push(`<div class="day blank" aria-hidden="true"></div>`);
    for (let d = 1; d <= days; d++) {
      const items = itemsOn(view.year, view.month, d);
      const counts = KINDS.map(k => [k, items.filter(i => i.kind === k).length]).filter(([, n]) => n);
      const cls = ["day", `heat-${heatLevel(items)}`];
      if (gamesOn(view.year, view.month, d).length) cls.push("game");
      if (`${view.year}-${view.month}-${d}` === todayKey) cls.push("today");
      if (selected.year === view.year && selected.month === view.month && selected.day === d) cls.push("selected");
      const sched = gamesOn(view.year, view.month, d);
      const room = sched.length ? 2 : 3;
      const chips = sched.map(g => `<span class="chip s">${esc(gameChip(g))}</span>`).join("") +
        items.slice(0, room).map(i => `<span class="chip ${i.kind}">${esc(chipLabel(i))}</span>`).join("");
      const more = items.length > room ? `<span class="more">+${items.length - room} more</span>` : "";
      const rec = recordOn(view.year, view.month, d);
      const recShort = rec.w + rec.l + rec.t ? wl(rec.w, rec.l, rec.t) : "";
      const label = `${MONTHS[view.month]} ${d}: ${sched.map(g => `Orioles ${gameText(g)}, `).join("")}${recShort ? `all-time record ${recShort}, ` : ""}` +
        counts.map(([k, n]) => `${n} ${KIND_HEADINGS[k].toLowerCase()}`).join(", ");
      parts.push(
        `<button class="${cls.join(" ")}" data-day="${d}" aria-label="${esc(label)}">
           <span class="num"><span>${d}</span><span class="counts">
             ${counts.map(([k, n]) => `<span class="${k}">${n}</span>`).join("")}
           </span></span>${chips}${more}${recShort ? `<span class="rec">${recShort}</span>` : ""}
         </button>`);
    }
    grid.innerHTML = parts.join("");
    grid.setAttribute("aria-busy", "false");
  }

  function eventLine(item, year) {
    const e = item.event;
    const box = e.link ? ` · <a href="${e.link}" target="_blank" rel="noopener">box score</a>` : "";
    return `<li>
      <div>${esc(e.title)}${eraTag(item.year)}</div>
      <div class="tag ${item.kind}">${yearsAgo(year - item.year)} · ${fmtDate(e.d)}</div>
      ${e.detail ? `<div class="meta">${esc(e.detail)}${box}</div>` : ""}
    </li>`;
  }

  function playerLine(item, year) {
    const p = item.player;
    const n = year - item.year;
    let what;
    if (item.kind === "b") {
      what = n === 0 ? `Born ${fmtDate(item.date)}`
        : p.x ? `Born ${yearsAgo(n).toLowerCase()} · ${item.year}–${p.x.slice(0, 4)}`
        : `${ordinal(n)} birthday · born ${item.year}`;
    } else if (item.kind === "x") {
      what = `Died ${yearsAgo(n).toLowerCase()} · ${fmtDate(item.date)}`;
    } else {
      const how = HOW[item.acq.how] || "Acquired";
      what = (n === 0 ? `${how} today` : `${ordinal(n)} anniversary · ${how.toLowerCase()}, ${fmtDate(item.date)}`) +
        (item.acq.from ? ` from ${esc(item.acq.from)}` : "");
    }
    return `<li>
      <div>${nameLink(p)}${p.hof ? ` <span class="era">HOF</span>` : ""}${eraTag(p.y[0]) && p.y.at(-1) < ORIOLES_FIRST ? eraTag(p.y[0]) : ""}</div>
      <div class="tag ${item.kind}">${what}</div>
      <div class="meta">${span(p.y)} · ${p.g.toLocaleString()} G · ${esc((p.p || []).join(", ") || "—")}${warText(p, true) ? ` · ${warText(p, true)}` : ""}</div>
    </li>`;
  }

  function playerCard(p) {
    const dates = [];
    const showBtn = d => FULL_DATE.test(d) ? `<button class="linkish" data-goto="${d}">show</button>` : "";
    if (p.b) dates.push(`<div><span class="tag b">Born</span> ${fmtDate(p.b)} ${showBtn(p.b)}</div>`);
    for (const a of p.a || []) {
      dates.push(`<div><span class="tag a">${esc(HOW[a.how] || "Acquired")}</span> ${fmtDate(a.d)}${a.from ? ` from ${esc(a.from)}` : ""} ${showBtn(a.d)}</div>`);
    }
    if (!(p.a || []).length) dates.push(`<div class="meta">How he joined the franchise isn't recorded</div>`);
    for (const e of (eventsByPlayer.get(p.id) || []).slice().sort((x, y) => x.d.localeCompare(y.d))) {
      const kind = e.c ? "m" : TYPE_KIND[e.t] || "m";
      dates.push(`<div><span class="tag ${kind}">${esc(e.c ? "Moment" : chipLabel({ event: e }).split(":")[0])}</span> ${fmtDate(e.d)} ${showBtn(e.d)}</div>`);
    }
    if (p.x) dates.push(`<div><span class="tag x">Died</span> ${fmtDate(p.x)} ${showBtn(p.x)}</div>`);
    const eras = [...new Set(p.y.map(y => eraOf(y) || "Orioles"))].join(", ");
    return `<div class="player-card">
      <h3>${nameLink(p)}${p.hof ? ` <span class="era">Hall of Fame</span>` : ""}</h3>
      <div class="meta">${eras} · ${span(p.y)} · ${p.g.toLocaleString()} games · ${esc((p.p || []).join(", ") || "—")}</div>
      ${warText(p) ? `<div class="meta">${warText(p)}</div>` : ""}
      <div class="dates">${dates.join("")}</div>
    </div><hr>`;
  }

  // Each date has a page with a link preview image (built by pipeline/cards.py)
  // that forwards to this calendar, so a shared link shows the day's best story.
  const shareUrl = (month, day) => new URL(`day/${pad(month + 1)}-${pad(day)}.html`, location.href).href.replace(/#.*$/, "");
  const shareButton = (month, day) => `<button class="linkish share" data-share="${shareUrl(month, day)}">Share this day</button>`;

  async function share(url, btn) {
    const title = `${MONTHS[selected.month]} ${selected.day} in Orioles history`;
    try {
      if (navigator.share) { await navigator.share({ title, url }); return; }
      await navigator.clipboard.writeText(url);
      btn.textContent = "Link copied";
    } catch (err) {
      if (err.name === "AbortError") return;
      btn.outerHTML = `<input class="share-url" readonly value="${esc(url)}" aria-label="Link to this day">`;
      panel.querySelector(".share-url")?.select();
    }
  }

  function renderPanel() {
    const { year, month, day } = selected;
    const items = itemsOn(year, month, day);
    let html = focusPlayer ? playerCard(focusPlayer) : "";
    html += `<div class="panel-head"><h3>${MONTHS[month]} ${day}, ${year}</h3>${shareButton(month, day)}</div>`;
    const sched = gamesOn(year, month, day);
    if (sched.length) {
      html += `<h4><span class="swatch s"></span>On the schedule</h4><ul>${sched.map(g => `<li>
        <div>${esc(gameText(g))}</div>
        <div class="meta">${esc(gameMeta(g))} · <a href="${gameLink(g)}" target="_blank" rel="noopener">${g.score ? "box score" : "Gameday"}</a></div>
      </li>`).join("")}</ul>`;
    }
    const r = recordOn(year, month, day);
    if (!eras.size) {
      // No eras chosen: the empty-state line below says so.
    } else if (!r.games) {
      html += `<p class="record meta">The franchise has never played on ${MONTHS[month]} ${day}${eraNote()}.</p>`;
    } else {
      const parts = [];
      if (r.w + r.l + r.t) parts.push(`<strong>${wl(r.w, r.l, r.t)}</strong> (${pct(r.w, r.l)}) in the regular season`);
      if (r.pw + r.pl) parts.push(`<strong>${wl(r.pw, r.pl)}</strong> in the postseason`);
      html += `<p class="record">All-time on ${MONTHS[month]} ${day}${eraNote()}: ${parts.join(" · ")}</p>`;
    }
    if (!items.length) {
      html += `<p class="empty">${KINDS.some(k => show[k]) && eras.size ? "Nothing on this day with the current filters." : eras.size ? "All filters are off." : "No franchise eras are selected below the calendar."}</p>`;
    }
    for (const k of KINDS) {
      const list = items.filter(i => i.kind === k);
      if (!list.length) continue;
      const line = i => i.group ? groupLine(i, year) : i.event ? eventLine(i, year) : playerLine(i, year);
      html += `<h4><span class="swatch ${k}"></span>${KIND_HEADINGS[k]} (${list.length})</h4><ul>${list.map(line).join("")}</ul>`;
    }
    panel.innerHTML = html;
  }

  // Navigation and state ----------------------------------------------------------

  function readHash() {
    // "#10-01" (from the calendar feed) opens that date in the current year.
    const md = location.hash.match(/^#(\d{2})-(\d{2})$/);
    if (md) {
      view = { year: now.getFullYear(), month: Math.min(11, Math.max(0, +md[1] - 1)) };
      selected = { ...view, day: +md[2] };
      return;
    }
    const m = location.hash.match(/^#(\d{4})-(\d{2})(?:-(\d{2}))?(?:\/([\w:.-]+))?$/);
    if (!m) return;
    view = { year: +m[1], month: Math.min(11, Math.max(0, +m[2] - 1)) };
    selected = { ...view, day: m[3] ? +m[3] : 1 };
    focusPlayer = m[4] ? playerById.get(m[4]) || null : null;
  }

  function writeHash() {
    const h = `#${selected.year}-${pad(selected.month + 1)}-${pad(selected.day)}${focusPlayer ? `/${focusPlayer.id}` : ""}`;
    if (location.hash !== h) history.replaceState(null, "", h);
  }

  function groupLine(item, year) {
    const names = item.group.map(i => `${i.player ? nameLink(i.player) : esc(i.event.title)} (${i.year})`).join(", ");
    return `<li>
      <div>${esc(groupTitle(item))}</div>
      <div class="tag ${item.kind}">${span(item.group.map(i => i.year))}</div>
      <div class="meta">${names}</div>
    </li>`;
  }

  // The day's single best story, above the grid.
  function renderStory() {
    const { year, month, day } = selected;
    const items = itemsOn(year, month, day);
    const story = $("story");
    const isToday = `${year}-${month}-${day}` === todayKey;
    const sched = gamesOn(year, month, day);
    const gameLine = sched.length ? `<p class="meta story-game"><span class="swatch s"></span>${isToday ? "Today" : "This day"}: ` +
      `${esc(SCHEDULE_TYPES[sched[0].t])}, ${sched.map(g => esc(gameText(g))).join(" and ")}</p>` : "";
    const heading = isToday ? "Today in franchise history" : `On ${MONTHS[month]} ${day}`;
    if (!items.length) {
      story.innerHTML = `<p class="story-kicker">${heading}</p><p class="story-title">Nothing on this day with the current filters.</p>${gameLine}`;
      return;
    }
    const [top, ...rest] = items;
    let title, detail = "", link = "";
    if (top.group) {
      title = groupTitle(top);
      detail = top.group.map(i => `${i.player?.n} (${i.year})`).join(", ");
    } else if (top.event) {
      title = top.event.title;
      detail = top.event.detail || "";
      link = top.event.link || "";
    } else {
      const p = top.player, n = year - top.year;
      title = top.kind === "b" ? `${p.n} ${p.x ? `was born ${n} years ago` : `turns ${n}`}`
        : top.kind === "x" ? `${p.n} died ${yearsAgo(n).toLowerCase()}`
        : `${p.n} joined the ${eraOf(top.year) || "Orioles"} ${yearsAgo(n).toLowerCase()}`;
      detail = `${span(p.y)} · ${p.g.toLocaleString()} games${warText(p) ? ` · ${warText(p)}` : ""}`;
    }
    const when = top.year === year ? fmtDate(top.date) : `${yearsAgo(year - top.year)} · ${top.year}`;
    const also = rest.slice(0, 2).map(i => esc(i.group ? groupTitle(i) : i.event ? i.event.title : i.player.n));
    story.innerHTML = `
      <p class="story-kicker"><span class="swatch ${top.kind}"></span>${heading} · ${when}${eraOf(top.year) && top.kind !== "b" && top.kind !== "x" ? ` · ${eraOf(top.year)}` : ""}</p>
      <p class="story-title">${esc(title)}</p>
      ${detail ? `<p class="meta">${esc(detail)}${link ? ` · <a href="${link}" target="_blank" rel="noopener">box score</a>` : ""}</p>` : ""}
      ${also.length ? `<p class="meta story-also">Also: ${also.join(" · ")}${rest.length > 2 ? ` · and ${rest.length - 2} more` : ""}</p>` : ""}
      ${gameLine}`;
  }

  // The header's counts and years, for the selected eras only.
  function renderSummary() {
    if (!eras.size) { $("summary").textContent = "No franchise eras selected below the calendar"; return; }
    const shown = players.filter(playedIn);
    const withAcq = shown.filter(p => (p.a || []).length).length;
    const moments = events.filter(e => eras.has(eraName(+e.d.slice(0, 4)))).length;
    const bounds = { Brewers: [1901, 1901], Browns: [1902, ORIOLES_FIRST - 1],
                     Orioles: [ORIOLES_FIRST, +meta.last_game.slice(0, 4)] };
    // Join neighbouring eras, so Browns + Orioles reads 1902–2026 and Brewers + Orioles 1901 and 1954–2026.
    const ranges = [];
    for (const e of ERAS.filter(e => eras.has(e))) {
      const [lo, hi] = bounds[e];
      if (ranges.length && ranges.at(-1)[1] === lo - 1) ranges.at(-1)[1] = hi; else ranges.push([lo, hi]);
    }
    $("summary").textContent = `${shown.length.toLocaleString()} players · ${withAcq.toLocaleString()} with acquisition dates · ` +
      `${moments.toLocaleString()} moments, ${ranges.map(([lo, hi]) => span([lo, hi])).join(" and ")}`;
  }

  function render() { renderSummary(); renderStory(); renderGrid(); renderPanel(); writeHash(); }

  function goTo(year, month, day) {
    year = Math.max(1901, Math.min(2100, year));
    view = { year, month };
    const days = new Date(year, month + 1, 0).getDate();
    selected = { year, month, day: Math.min(day || 1, days) };
    render();
  }

  function goToAnniversary(iso) {
    const [, m, d] = iso.split("-").map(Number);
    const year = view.year;
    goTo(year, m - 1, m === 2 && d === 29 && !isLeap(year) ? 28 : d);
  }

  grid.addEventListener("click", e => {
    const cell = e.target.closest(".day[data-day]");
    if (!cell) return;
    selected = { year: view.year, month: view.month, day: +cell.dataset.day };
    render();
  });
  grid.addEventListener("keydown", e => {
    const steps = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    if (!(e.key in steps) || !e.target.closest(".day[data-day]")) return;
    e.preventDefault();
    const d = new Date(selected.year, selected.month, selected.day + steps[e.key]);
    goTo(d.getFullYear(), d.getMonth(), d.getDate());
    grid.querySelector(`.day[data-day="${d.getDate()}"]`)?.focus();
  });
  panel.addEventListener("click", e => {
    const shareBtn = e.target.closest("[data-share]");
    if (shareBtn) { share(shareBtn.dataset.share, shareBtn); return; }
    const btn = e.target.closest("[data-goto]");
    if (btn) goToAnniversary(btn.dataset.goto);
  });
  $("prev").onclick = () => { const d = new Date(view.year, view.month - 1, 1); goTo(d.getFullYear(), d.getMonth(), 1); };
  $("next").onclick = () => { const d = new Date(view.year, view.month + 1, 1); goTo(d.getFullYear(), d.getMonth(), 1); };
  $("today").onclick = () => { focusPlayer = null; goTo(now.getFullYear(), now.getMonth(), now.getDate()); };
  monthSel.onchange = () => goTo(view.year, +monthSel.value, 1);
  yearInput.onchange = () => { const y = parseInt(yearInput.value, 10); if (y) goTo(y, view.month, selected.day); };
  for (const k of ["s", ...KINDS]) $(`show-${k}`).onchange = e => { show[k] = e.target.checked; render(); };
  const eraBoxes = [...$("eras").querySelectorAll("input")];
  $("eras").onchange = e => {
    if (e.target.checked) eras.add(e.target.value); else eras.delete(e.target.value);
    try { localStorage.setItem("oc-eras", [...eras].join(",")); } catch {}
    render();
    if (!results.hidden) showResults();
  };
  window.addEventListener("hashchange", () => { readHash(); render(); });

  // Player search -------------------------------------------------------------------

  const search = $("search"), results = $("results");
  let matches = [], active = -1;
  function closeResults() { results.hidden = true; search.setAttribute("aria-expanded", "false"); active = -1; }
  function pick(p) {
    focusPlayer = p;
    search.value = p.n;
    closeResults();
    const target = p.b || (p.a || []).map(a => a.d).find(d => FULL_DATE.test(d));
    if (target && FULL_DATE.test(target)) goToAnniversary(target); else render();
  }
  function showResults() {
    const q = searchIndex.norm(search.value.trim());
    if (q.length < 2) { closeResults(); return; }
    const found = searchIndex.filter(([n]) => n.includes(q));
    const inView = found.filter(([, p]) => playedIn(p));
    matches = inView
      .sort((x, y) => (y[0].startsWith(q) - x[0].startsWith(q)) || y[1].g - x[1].g)
      .slice(0, 12).map(([, p]) => p);
    active = -1;
    const hidden = found.length - inView.length;
    results.innerHTML = (matches.length
      ? matches.map((p, i) => `<li role="option"><button data-i="${i}">${esc(p.n)} <small>${eraOf(p.y[0]) ? eraOf(p.y[0]) + " · " : ""}${span(p.y)}</small></button></li>`).join("")
      : `<li class="empty" style="padding:6px 8px">No players found</li>`) +
      (hidden ? `<li class="empty" style="padding:6px 8px">${hidden} more from eras that are turned off below the calendar</li>` : "");
    results.hidden = false;
    search.setAttribute("aria-expanded", "true");
  }
  search.addEventListener("input", showResults);
  search.addEventListener("keydown", e => {
    if (results.hidden) return;
    const buttons = results.querySelectorAll("button");
    if ((e.key === "ArrowDown" || e.key === "ArrowUp") && buttons.length) {
      e.preventDefault();
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
      buttons.forEach((b, i) => b.classList.toggle("active", i === active));
    } else if (e.key === "Enter" && matches.length) {
      e.preventDefault();
      pick(matches[Math.max(active, 0)]);
    } else if (e.key === "Escape") {
      closeResults();
    }
  });
  results.addEventListener("click", e => {
    const b = e.target.closest("button[data-i]");
    if (b) pick(matches[+b.dataset.i]);
  });
  document.addEventListener("click", e => { if (!e.target.closest(".search")) closeResults(); });

  // A link to the next scheduled game, so the coming season is easy to find.
  function showNextGame() {
    const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    const next = [...schedule.values()].flat().filter(g => g.d >= today && !g.score).sort((x, y) => x.d.localeCompare(y.d))[0];
    if (!next) return;
    const el = $("next-game");
    el.innerHTML = `Next game: <button class="linkish" data-day="${next.d}">${fmtDate(next.d)}, ${esc(gameText(next))}</button> · ${esc(SCHEDULE_TYPES[next.t])}`;
    el.querySelector("button").onclick = () => {
      const [y, m, d] = next.d.split("-").map(Number);
      focusPlayer = null;
      goTo(y, m - 1, d);
    };
  }

  // Boot -----------------------------------------------------------------------------

  async function load(name) {
    const res = await fetch(`data/${name}.json`);
    if (!res.ok) throw new Error(`${name}.json: ${res.status}`);
    return res.json();
  }

  // The schedule is optional: builds without the Stats API don't write it.
  const loadSchedule = () => load("schedule").catch(() => []);
  Promise.all([...["players", "events", "records", "meta"].map(load), loadSchedule()]).then(([p, e, r, m, sc]) => {
    players = p; events = e; records = r; meta = m;
    for (const g of sc) {
      if (!schedule.has(g.d)) schedule.set(g.d, []);
      schedule.get(g.d).push(g);
    }
    // Restore the chosen eras; "oc-early" is the old Browns & Brewers on/off switch.
    try {
      const saved = localStorage.getItem("oc-eras");
      const picked = saved != null ? saved.split(",").filter(e => ERAS.includes(e))
        : localStorage.getItem("oc-early") === "0" ? ["Orioles"] : ERAS;
      eras.clear();
      picked.forEach(e => eras.add(e));
    } catch {}
    eraBoxes.forEach(b => { b.checked = eras.has(b.value); });
    buildIndex();
    $("built").textContent = `Data through ${fmtDate(meta.last_game)}, refreshed ${new Date(meta.built).toLocaleDateString()}.`;
    // webcal:// opens the subscribe dialog in Apple Calendar and Outlook.
    $("ical-url").textContent = new URL("calendar.ics", location.href).href.replace(/#.*$/, "");
    for (const id of ["ical-all", "ical-orioles"]) {
      const a = $(id);
      a.href = new URL(a.getAttribute("href"), location.href).href.replace(/^https?:/, "webcal:");
    }
    showNextGame();
    readHash();
    render();
  }).catch(err => {
    $("summary").textContent = "The calendar data didn't load. Reload the page to try again.";
    console.error(err);
  });
})();
