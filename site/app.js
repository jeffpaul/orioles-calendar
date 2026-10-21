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
    callout: 100, world_series: 95, pennant: 90, division_title: 85, perfect_game: 85, no_hitter: 75,
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
  const eraTag = year => eraOf(year) ? `<span class="era">${eraOf(year)}</span>` : "";
  const playerUrl = p => p.bbref
    ? `https://www.baseball-reference.com/players/${p.bbref[0]}/${p.bbref}.shtml`
    : p.mlbam ? `https://www.mlb.com/player/${p.mlbam}` : null;
  const war = p => (p.w || [null, null])[1];

  let players = [], events = [], records = {}, meta = {};
  let playerById = new Map(), byDay = new Map(), eventsByPlayer = new Map(), searchIndex = [];
  const now = new Date();
  const todayKey = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}`;
  const show = { m: true, g: true, d: true, b: true, a: true, x: false, early: true };
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

  // Is an item inside the selected era range?
  function inEra(item) {
    if (show.early) return true;
    if (item.kind === "b" || item.kind === "x") return item.player.y.at(-1) >= ORIOLES_FIRST;
    return item.year >= ORIOLES_FIRST;
  }

  function itemsOn(year, month, day) {
    const key = `${pad(month + 1)}-${pad(day)}`;
    let list = (byDay.get(key) || []).slice();
    if (month === 1 && day === 28 && !isLeap(year)) list = list.concat(byDay.get("02-29") || []);
    return list
      .filter(i => i.year <= year && show[i.kind] && inEra(i))
      .sort((x, y) => y.score - x.score || x.year - y.year);
  }

  function recordOn(year, month, day) {
    const r = { w: 0, l: 0, t: 0, pw: 0, pl: 0 };
    for (const [y, w, l, t, pw, pl] of records[`${pad(month + 1)}-${pad(day)}`] || []) {
      if (y > year) break;
      if (!show.early && y < ORIOLES_FIRST) continue;
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
    if (e.c) return e.title.split(",")[0];
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

  // Rendering -------------------------------------------------------------------

  const grid = $("grid"), panel = $("panel"), title = $("title");
  const monthSel = $("month"), yearInput = $("year");
  MONTHS.forEach((m, i) => monthSel.add(new Option(m, i)));

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
      const cls = ["day"];
      if (`${view.year}-${view.month}-${d}` === todayKey) cls.push("today");
      if (selected.year === view.year && selected.month === view.month && selected.day === d) cls.push("selected");
      const chips = items.slice(0, 3).map(i => `<span class="chip ${i.kind}">${esc(chipLabel(i))}</span>`).join("");
      const more = items.length > 3 ? `<span class="more">+${items.length - 3} more</span>` : "";
      const rec = recordOn(view.year, view.month, d);
      const recShort = rec.w + rec.l + rec.t ? wl(rec.w, rec.l, rec.t) : "";
      const label = `${MONTHS[view.month]} ${d}: ${recShort ? `all-time record ${recShort}, ` : ""}` +
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

  function renderPanel() {
    const { year, month, day } = selected;
    const items = itemsOn(year, month, day);
    let html = focusPlayer ? playerCard(focusPlayer) : "";
    html += `<h3>${MONTHS[month]} ${day}, ${year}</h3>`;
    const r = recordOn(year, month, day);
    if (!r.games) {
      html += `<p class="record meta">The franchise has never played on ${MONTHS[month]} ${day}${show.early ? "" : " since 1954"}.</p>`;
    } else {
      const parts = [];
      if (r.w + r.l + r.t) parts.push(`<strong>${wl(r.w, r.l, r.t)}</strong> (${pct(r.w, r.l)}) in the regular season`);
      if (r.pw + r.pl) parts.push(`<strong>${wl(r.pw, r.pl)}</strong> in the postseason`);
      html += `<p class="record">All-time on ${MONTHS[month]} ${day}${show.early ? "" : " since 1954"}: ${parts.join(" · ")}</p>`;
    }
    if (!items.length) {
      html += `<p class="empty">${KINDS.some(k => show[k]) ? "Nothing on this day with the current filters." : "All filters are off."}</p>`;
    }
    for (const k of KINDS) {
      const list = items.filter(i => i.kind === k);
      if (!list.length) continue;
      const line = i => i.event ? eventLine(i, year) : playerLine(i, year);
      html += `<h4><span class="swatch ${k}"></span>${KIND_HEADINGS[k]} (${list.length})</h4><ul>${list.map(line).join("")}</ul>`;
    }
    panel.innerHTML = html;
  }

  // Navigation and state ----------------------------------------------------------

  function readHash() {
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

  function render() { renderGrid(); renderPanel(); writeHash(); }

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
    const btn = e.target.closest("[data-goto]");
    if (btn) goToAnniversary(btn.dataset.goto);
  });
  $("prev").onclick = () => { const d = new Date(view.year, view.month - 1, 1); goTo(d.getFullYear(), d.getMonth(), 1); };
  $("next").onclick = () => { const d = new Date(view.year, view.month + 1, 1); goTo(d.getFullYear(), d.getMonth(), 1); };
  $("today").onclick = () => { focusPlayer = null; goTo(now.getFullYear(), now.getMonth(), now.getDate()); };
  monthSel.onchange = () => goTo(view.year, +monthSel.value, 1);
  yearInput.onchange = () => { const y = parseInt(yearInput.value, 10); if (y) goTo(y, view.month, selected.day); };
  for (const k of KINDS) $(`show-${k}`).onchange = e => { show[k] = e.target.checked; render(); };
  $("show-early").onchange = e => {
    show.early = e.target.checked;
    try { localStorage.setItem("oc-early", show.early ? "1" : "0"); } catch {}
    render();
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
    matches = searchIndex
      .filter(([n]) => n.includes(q))
      .sort((x, y) => (y[0].startsWith(q) - x[0].startsWith(q)) || y[1].g - x[1].g)
      .slice(0, 12).map(([, p]) => p);
    active = -1;
    results.innerHTML = matches.length
      ? matches.map((p, i) => `<li role="option"><button data-i="${i}">${esc(p.n)} <small>${eraOf(p.y[0]) ? eraOf(p.y[0]) + " · " : ""}${span(p.y)}</small></button></li>`).join("")
      : `<li class="empty" style="padding:6px 8px">No players found</li>`;
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

  // Boot -----------------------------------------------------------------------------

  async function load(name) {
    const res = await fetch(`data/${name}.json`);
    if (!res.ok) throw new Error(`${name}.json: ${res.status}`);
    return res.json();
  }

  Promise.all(["players", "events", "records", "meta"].map(load)).then(([p, e, r, m]) => {
    players = p; events = e; records = r; meta = m;
    try { if (localStorage.getItem("oc-early") === "0") { show.early = false; $("show-early").checked = false; } } catch {}
    buildIndex();
    const withAcq = players.filter(p => (p.a || []).length).length;
    $("summary").textContent = `${players.length.toLocaleString()} players · ${withAcq.toLocaleString()} with acquisition dates · ` +
      `${events.length.toLocaleString()} moments, 1901–${meta.last_game.slice(0, 4)}`;
    $("built").textContent = `Data through ${fmtDate(meta.last_game)}, refreshed ${new Date(meta.built).toLocaleDateString()}.`;
    readHash();
    render();
  }).catch(err => {
    $("summary").textContent = "The calendar data didn't load. Reload the page to try again.";
    console.error(err);
  });
})();
