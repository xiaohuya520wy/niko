// Port of fetch_event.py -> JS (orchestration layer for event.json).
//
// Pure logic only: no filesystem, no network. The Worker (worker.js) injects
// the raw HTML for the Falcons team page + the Liquipedia:Matches portal and
// hands cached/raw page HTML to buildEvent(). This keeps everything Node-
// testable and lets us byte-compare against the Python oracle on real fixtures.
//
// Differences from Python original (deliberate, documented):
//   * No Scrapling self-heal layer exists in JS. PE.build() is called WITHOUT
//     the `url` self-heal argument, which is exactly Python's degrade path
//     (verified byte-identical on 3 fixtures).
//   * download_logo() does NOT write to assets/teams/ (no FS in a Worker).
//     It returns the absolute Liquipedia URL so the frontend can hotlink the
//     logo. The static Pages bundle keeps whatever logos were baked at deploy.

import * as PE from "./parseEvent.js";
import * as PD from "./parseDetail.js";

// ---------------------------------------------------------------------------
// Config tables (ported verbatim from fetch_event.py)
// ---------------------------------------------------------------------------

// 近期已结束、仍需在历史板块常驻的赛事（战队页已不再列出，手动维护）
export const RECENT_CONFIG = [
  { page: "BLAST/Open/2026/Fall", zh: "BLAST 公开赛 波尔图站", short: "BLAST 波尔图",
    tag: "recent", tier: "S-Tier", match: "BLAST" },
  { page: "Intel Extreme Masters/2026/Cologne/Playoffs", zh: "IEM 科隆 Major 2026",
    short: "IEM 科隆", tag: "recent", tier: "S-Tier", match: "Cologne",
    teamsPage: "Intel Extreme Masters/2026/Cologne" },
];

// 战队页抓取失败时的兜底清单（与历史已知赛事一致），确保首次/离线也不空站
export const SEED_NEXT_CONFIG = [
  { page: "ESL/Pro League/Season 24", zh: "ESL 职业联赛 S24", short: "EPL S24",
    tag: "next", tier: "S-Tier", match: "ESL Pro League" },
  { page: "Intel Extreme Masters/2026/Beijing", zh: "IEM 北京 2026", short: "IEM 北京",
    tag: "next", tier: "S-Tier", match: "Beijing" },
  { page: "Thunderpick/World Championship/2026", zh: "Thunderpick 世界冠军赛 2026",
    short: "TWC 2026", tag: "next", tier: "S-Tier", match: "Thunderpick" },
];

// 页名 -> 中文显示名
export const ZH_MAP = {
  "ESL/Pro League/Season 24": "ESL 职业联赛 S24",
  "Intel Extreme Masters/2026/Beijing": "IEM 北京 2026",
  "Thunderpick/World Championship/2026": "Thunderpick 世界冠军赛 2026",
  "PGL/2027/Bucharest": "PGL 布加勒斯特 2027",
  "BLAST/Open/2026/Fall": "BLAST 公开赛 波尔图站",
  "Intel Extreme Masters/2026/Cologne/Playoffs": "IEM 科隆 Major 2026",
  "Intel Extreme Masters/2026/Cologne": "IEM 科隆 Major 2026",
};

// 抓取「未来赛事详情」的视野（天）
export const HORIZON_DAYS = 45;

// 日历自动发现参数
export const DISCOVER_LIMIT = 4;
export const DISCOVER_MIN_ROWS = 2;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function slug(s) {
  return (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

function nk(n) {
  return (n || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

const ROUND_DATE_RE = /^(\d{1,2})月(\d{1,2})日$/;

export function roundDateTs(name, year) {
  const m = ROUND_DATE_RE.exec((name || "").trim());
  if (!m) return null;
  try {
    return Math.floor(Date.UTC(Number(year), Number(m[1]) - 1, Number(m[2]), 0, 0, 0) / 1000);
  } catch {
    return null;
  }
}

export function normTeam(n) {
  return (n || "").replace(/^Team\s+/, "").trim();
}

// Logo path: exactly the same naming as Python download_logo()
// (thumb stem -> strip "43px-" -> slug -> ".png"), but WITHOUT the filesystem
// part. Liquipedia's image host returns 403 to any request carrying a Referer,
// so hotlinking from the browser is not an option. Instead the Worker downloads
// the bytes into KV (`logo:<fn>`) and /assets/teams/<fn> is served from the
// static bundle first, then KV. Keeping the path identical to Python means the
// baked static bundle keeps working and byte-comparison stays clean.
export function downloadLogo(logo) {
  if (!logo) return "";
  let stem = String(logo).split("?")[0];
  stem = stem.slice(stem.lastIndexOf("/") + 1); // basename
  const dot = stem.lastIndexOf(".");
  if (dot > 0) stem = stem.slice(0, dot); // drop extension (pathlib .stem)
  stem = stem.replace(/^\d+px-/, ""); // drop thumbnail prefix 43px-
  if (!stem) return "";
  return "assets/teams/" + slug(stem) + ".png";
}

export function parseEndFromDateText(dateText, year) {
  if (!dateText) return null;
  let left, right;
  const parts = dateText.split("–"); // en dash
  if (parts.length < 2) return null;
  left = parts[0]; right = parts[1];
  let lm, ld;
  try { [lm, ld] = left.trim().split("/").map(Number); } catch { return null; }
  let rm, rd;
  if (right.includes("/")) {
    try { [rm, rd] = right.trim().split("/").map(Number); } catch { return null; }
  } else {
    rm = lm; rd = Number(right.trim());
  }
  let yr = year + 1;
  if (!(rm < lm || (rm === lm && rd < ld))) yr = year;
  try {
    const e = new Date(Date.UTC(yr, rm - 1, rd, 23, 59, 59));
    return e.toISOString().replace(/\.\d{3}Z$/, "Z").slice(0, 19) + "Z";
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Detail attach (parse_detail series -> event brackets/schedule maps)
// ---------------------------------------------------------------------------

export function extractSeriesDetail(html) {
  try { return PD.extract(html); } catch { return []; }
}

function matchSeries(a, b, sa, sb, ts, series) {
  const pa = nk(a), pb = nk(b);
  if (pa === pb) return null;
  // Python: _nk(s["left"]) in (pa, pb) and _nk(s["right"]) in (pa, pb)
  const pairs = [pa, pb];
  let cands = series.filter(
    (s) => pairs.includes(nk(s.left)) && pairs.includes(nk(s.right))
  );
  if (!cands.length) return null;
  const played = sa != null && sb != null;
  if (played) {
    for (const s of cands) {
      const la = s.score[0], lb = s.score[1];
      if ((sa === la && sb === lb) || (sa === lb && sb === la)) return s;
    }
    const wm = cands.filter((s) => s.maps && s.maps.length);
    return wm.length ? wm[0] : cands[0];
  }
  // 未开打（TBD/即将开始）：优先时间戳吻合，再优先「未比赛」的（maps 为空）
  if (ts) {
    const tc = cands.filter((s) => s.ts === ts);
    if (tc.length) cands = tc;
  }
  const up = cands.filter((s) => !(s.maps && s.maps.length));
  return up.length ? up[0] : cands[0];
}

function orient(s, a, b) {
  const ka = nk(a), kl = nk(s.left), kr = nk(s.right);
  const aIsLeft = ka === kl;
  const maps = [];
  for (const mp of s.maps) {
    let lw = mp.left_win;
    if (lw == null) {
      try {
        const ar = parseInt(mp.left.rounds || 0, 10);
        const br = parseInt(mp.right.rounds || 0, 10);
        lw = ar > br ? true : (br > ar ? false : null);
      } catch { lw = null; }
    }
    let aw, m_a, m_b;
    if (aIsLeft) { aw = lw; m_a = mp.left; m_b = mp.right; }
    else { aw = (lw == null ? null : !lw); m_a = mp.right; m_b = mp.left; }
    maps.push({
      map: mp.map, vetoed: mp.vetoed, a_win: aw,
      a: { rounds: m_a.rounds || "", t: m_a.t || "", ct: m_a.ct || "" },
      b: { rounds: m_b.rounds || "", t: m_b.t || "", ct: m_b.ct || "" },
    });
  }
  return {
    maps,
    links: { hltv_match: s.hltv_match, hltv_maps: s.hltv_maps, vods: s.vods },
  };
}

function attachDetail(brackets, sched, series, evId) {
  let n = 0;
  function fix(m, aName, bName, sa, sb, ts, stage = "") {
    const s = matchSeries(aName, bName, sa, sb, ts, series);
    const tsForId = ts || (s ? s.ts : null);
    const pair = [nk(aName), nk(bName)].sort().join("-");
    m.id = `${evId}__${pair}` + (tsForId ? `__${tsForId}` : "");
    if (s) {
      const o = orient(s, aName, bName);
      m.maps = o.maps;
      m.links = o.links;
      n++;
    } else {
      m.maps = [];
      m.links = {};
    }
    if (stage) m.stage = stage;
  }
  for (const b of brackets) {
    for (const rd of b.rounds) {
      for (const m of rd.matches) {
        fix(m, m.a.name, m.b.name, m.a.score, m.b.score, m.ts, rd.name);
      }
    }
  }
  for (const m of sched) {
    fix(m, m.a, m.b, m.sa, m.sb, m.ts, m.stage || m.round);
  }
  return n;
}

// ---------------------------------------------------------------------------
// build_event: HTML -> one event object (pure)
// ---------------------------------------------------------------------------

export function buildEvent(cfg, htmlText, baseInfo, now) {
  const h = htmlText;
  const d = PE.build(cfg.page, h, cfg.zh); // no Scrapling self-heal in JS
  let parts = d.participants;

  // teams_page: prefer the full main-event page participant list
  if (cfg.teamsPageHtml) {
    try {
      const full = PE.parseParticipants(cfg.teamsPageHtml);
      if (full && full.length) parts = full;
    } catch { /* keep parsed */ }
  }

  const teams = [];
  for (const p of parts.slice(0, 24)) {
    const logo = downloadLogo(p.logo || "");
    teams.push({ name: normTeam(p.name), logo });
  }

  // date window (brackets + upcoming + round-date names)
  let tsAll = [];
  for (const b of d.brackets)
    for (const rd of b.rounds)
      for (const m of rd.matches) if (m.ts) tsAll.push(m.ts);
  for (const u of (d.upcoming || [])) if (u.ts) tsAll.push(u.ts);
  for (const b of d.brackets)
    for (const rd of b.rounds)
      for (const t of [roundDateTs(rd.name, now.getUTCFullYear())])
        if (t) tsAll.push(t);

  let startIso = "", endIso = "";
  if (tsAll.length) {
    const lo = Math.min(...tsAll), hi = Math.max(...tsAll);
    startIso = new Date(lo * 1000).toISOString().replace(/\.\d{3}Z$/, "Z").slice(0, 19) + "Z";
    endIso = new Date((hi + 4 * 3600) * 1000).toISOString().replace(/\.\d{3}Z$/, "Z").slice(0, 19) + "Z";
  }

  let dateText = "", tierOut = "", noteOut = "";
  // 修复：赛事官方开幕时间（baseInfo.start，来自 upcoming_tournaments，由 Liquipedia
  // 赛事页 date_text 解析，权威）必须优先于「解析到的最早一场比赛时间」。否则当
  // Liquipedia 只解析出部分赛程（如仅 Falcon 场次 / 仅淘汰赛）时，start 会被推到
  // 第一场被解析的比赛（IEM 北京被推到 11-06，而非真实开幕日 11-02），倒计时整整晚
  // 4 天，且与首页 upcoming_tournaments 的 Nov 02 不一致。
  if (baseInfo && baseInfo.start) {
    const bs = new Date(baseInfo.start).getTime();
    if (!isNaN(bs) && (!startIso || bs < new Date(startIso).getTime())) startIso = baseInfo.start;
  }
  if (cfg.tag === "next" && baseInfo) {
    const baseEnd = baseInfo.end;
    if (baseEnd) endIso = baseEnd;
    else {
      const de = parseEndFromDateText(baseInfo.date_text, now.getUTCFullYear());
      if (de) endIso = de;
    }
    // tier from infobox, base only fallback
    tierOut = (d.info && d.info.tier) || baseInfo.tier || cfg.tier;
    noteOut = baseInfo.note || "";
    dateText = baseInfo.date_text || "";
  } else {
    tierOut = (d.info && d.info.tier) || cfg.tier;
    noteOut = "";
    if (startIso) {
      const a = new Date(startIso), b = endIso ? new Date(endIso) : a;
      const am = a.getUTCMonth() + 1, ad = a.getUTCDate();
      const bm = b.getUTCMonth() + 1, bd = b.getUTCDate();
      dateText = `${String(am).padStart(2, "0")}/${String(ad).padStart(2, "0")}–${String(bm).padStart(2, "0")}/${String(bd).padStart(2, "0")}`;
    }
  }

  // status
  let status = "upcoming";
  if (startIso) {
    const s = new Date(startIso);
    const e = endIso ? new Date(endIso) : new Date(s.getTime() + 7 * 86400000);
    if (now < s) status = "upcoming";
    else if (now <= e) status = "live";
    else status = "done";
  } else if (cfg.tag === "recent") {
    status = "done";
  }

  // brackets
  const brackets = [];
  for (const b of d.brackets) {
    const rounds = [];
    for (const rd of b.rounds) {
      const ms = [];
      for (const m of rd.matches) {
        ms.push({
          a: { name: normTeam(m.a.name), score: m.a.score, win: m.a.win },
          b: { name: normTeam(m.b.name), score: m.b.score, win: m.b.win },
          ts: m.ts, bo: m.bo,
        });
      }
      rounds.push({ name: rd.name, matches: ms });
    }
    if (rounds.length) brackets.push({ title: b.title, rounds, count: b.count });
  }

  // schedule (+ upcoming merge, dedup by team+ts ±90s)
  const sched = [];
  for (const r of d.schedule) {
    sched.push({
      stage: r.stage, round: r.round, bo: r.bo, ts: r.ts,
      a: normTeam(r.a.name), b: normTeam(r.b.name),
      sa: r.a.score, sb: r.b.score,
    });
  }
  const seenAb = new Set(sched.map((r) => `${r.ts}|${r.a}|${r.b}`));
  for (const u of (d.upcoming || [])) {
    const a = normTeam(u.a.name), b = normTeam(u.b.name);
    if (sched.some((r) => r.a === a && r.b === b && Math.abs(u.ts - r.ts) <= 90)) continue;
    seenAb.add(`${u.ts}|${a}|${b}`);
    sched.push({
      stage: u.stage || "即将开赛", round: "小组赛", bo: u.bo, ts: u.ts,
      a, b,
      sa: (u.a || {}).score, sb: (u.b || {}).score,
    });
  }
  sched.sort((x, y) => x.ts - y.ts);

  const groups = d.groups.map((g) => ({ title: g.title, cols: g.cols, rows: g.rows }));

  // attach map-level detail
  try {
    const seriesDetail = extractSeriesDetail(h);
    const nDet = attachDetail(brackets, sched, seriesDetail, slug(cfg.page));
    if (seriesDetail.length) {
      // (debug) console.log(`[detail] ${seriesDetail.length} series, ${nDet} attached`);
    }
  } catch { /* ignore */ }

  return {
    id: slug(cfg.page),
    tag: cfg.tag,
    name: cfg.zh,
    short: cfg.short,
    tier: tierOut,
    note: noteOut,
    status,
    start: startIso,
    end: endIso,
    date_text: dateText,
    prize: (d.info && d.info.prize) || "",
    format: summarizeFormat(h),
    teams,
    groups,
    brackets,
    schedule: sched,
    // Python: urllib.parse.quote(cfg["page"]) -> safe="/" keeps slashes, space -> %20
    source: "https://liquipedia.net/counterstrike/" + cfg.page.split("/").map(encodeURIComponent).join("/"),
  };
}

export function summarizeFormat(h) {
  const seg = PE.sectionHtml(h, "Format");
  if (!seg) return "";
  let txt = PE._text(seg);
  txt = txt.replace(/^\s*Format\s*/, "");
  txt = txt.replace(/^\[\s*edit\s*\]\s*/, "").trim();
  txt = txt.split("Click here")[0].split("First Round")[0].trim();
  txt = txt.replace(/\s+/g, " ");
  return txt.slice(0, 180);
}

// ---------------------------------------------------------------------------
// Falcons team page + Liquipedia:Matches portal parsing (pure)
// ---------------------------------------------------------------------------

const MONTHS = { Jan: 1, Feb: 2, Mar: 3, Apr: 4, May: 5, Jun: 6,
  Jul: 7, Aug: 8, Sep: 9, Oct: 10, Nov: 11, Dec: 12 };

export function pageFromSource(source) {
  if (!source) return "";
  const marker = "/counterstrike/";
  if (!source.includes(marker)) return "";
  return decodeURIComponent(source.split(marker)[1]).trim().replace(/^\/+|\/+$/g, "");
}

export function parseFalconsUpcoming(html) {
  const out = [];
  const i = html.indexOf("Upcoming Tournaments");
  if (i < 0) return out;
  const seg = html.slice(i, i + 20000);
  const re = /<div class="tournaments-list-item">(.*?)(?=<div class="tournaments-list-item">|$)/gs;
  let m;
  while ((m = re.exec(seg))) {
    const b = m[1]
      .replace(/&#(\d+);/g, (_, c) => String.fromCodePoint(Number(c)))
      .replace(/&[a-z]+;/g, (e) => ({ "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'" }[e] || e));
    const nm = /tournaments-list-item__name"><a[^>]*title="([^"]+)"[^>]*>([^<]*)<\/a>/.exec(b);
    if (!nm) continue;
    let page = nm[1].trim();
    const name = (nm[2] || "").trim() || page;
    const date = /tournaments-list-item__date">(.*?)<\/div>/.exec(b);
    const tier = /tournament-badge__text">(.*?)<\//.exec(b);
    const dateText = date ? date[1].replace(/&[a-z]+;/g, (e) => ({ "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"' }[e] || e)).trim() : "";
    const tierV = tier ? tier[1].trim() : "";
    if (!page || !page.includes("/")) {
      const lk = /href="(\/counterstrike\/[^"]+)"/.exec(b);
      if (lk) {
        page = lk[1].split("/counterstrike/")[1].replace(/_/g, " ").trim().replace(/^\/+|\/+$/g, "");
      }
    }
    if (!page) continue;
    out.push({ page, name, short: name, tier: tierV, date_text: dateText, start: "", end: "" });
  }
  return out;
}

export function parseDateWindow(dateText, now) {
  if (!dateText) return [null, null];
  let txt = dateText.replace(/–/g, "-").replace(/—/g, "-").trim();
  const parts = txt.split(/\s*-\s*/);
  const m1 = /^([A-Za-z]{3})\.?\s*(\d{1,2})/.exec((parts[0] || "").trim());
  if (!m1) return [null, null];
  const mo1 = MONTHS[m1[1].replace(/\.$/, "")];
  const d1 = parseInt(m1[2], 10);
  if (!mo1) return [null, null];
  let mo2, d2;
  if (parts.length > 1) {
    const p2 = parts[1].trim();
    const m2 = /^([A-Za-z]{3})\.?\s*(\d{1,2})/.exec(p2);
    if (m2 && /^[A-Za-z]{3}/.test(p2)) {
      mo2 = MONTHS[m2[1].replace(/\.$/, "")];
      d2 = parseInt(m2[2], 10);
    } else {
      d2 = parseInt((p2.replace(/\D/g, "") || String(d1)), 10);
      mo2 = mo1;
    }
  } else { mo2 = mo1; d2 = d1; }
  const y1 = (mo1 > now.getUTCMonth() + 1 || (mo1 === now.getUTCMonth() + 1 && d1 >= now.getUTCDate())) ? now.getUTCFullYear() : now.getUTCFullYear() + 1;
  const y2 = (mo2 > mo1 || (mo2 === mo1 && d2 >= d1)) ? y1 : y1 + 1;
  try {
    const start = new Date(Date.UTC(y1, mo1 - 1, d1, 0, 0, 0));
    const end = new Date(Date.UTC(y2, mo2 - 1, d2, 23, 59, 59));
    return [start.toISOString().replace(/\.\d{3}Z$/, "Z").slice(0, 19) + "Z",
            end.toISOString().replace(/\.\d{3}Z$/, "Z").slice(0, 19) + "Z"];
  } catch {
    return [null, null];
  }
}

export function deriveUpcomingList({ falconsHtml, now, zhMap = ZH_MAP }) {
  const raw = parseFalconsUpcoming(falconsHtml);
  const out = [], seen = new Set();
  for (const t of raw) {
    const sid = slug(t.page);
    if (seen.has(sid)) continue;
    seen.add(sid);
    const [s, e] = parseDateWindow(t.date_text, now);
    out.push({
      name: t.name,
      short: zhMap[t.page] || t.short,
      zh: zhMap[t.page] || t.name,
      page: t.page,
      tier: t.tier,
      date_text: t.date_text,
      start: s || "",
      end: e || "",
      status: upStatus(s, e, now),
      url: "https://liquipedia.net/counterstrike/" + encodeURIComponent(t.page.replace(/ /g, "_")),
    });
  }
  return out;
}

export function parsePortalTournaments(h) {
  const tour = {};
  const re = /class="match-info-tournament"/g;
  let m;
  while ((m = re.exec(h))) {
    const a = /<a href="\/counterstrike\/([^"]+)"/.exec(h.slice(m.index, m.index + 500));
    if (!a) continue;
    let page = decodeURIComponent(a[1]).split("#")[0].split("?")[0];
    page = page.trim().replace(/^\/+|\/+$/g, "").replace(/_/g, " ").trim();
    if (!page || page.includes(":")) continue;
    tour[page] = (tour[page] || 0) + 1;
  }
  return tour;
}

function recomputeStatus(ev, now) {
  const s = ev.start, e = ev.end;
  if (!s) return ev;
  try {
    const st = new Date(s), en = e ? new Date(e) : new Date(st.getTime() + 7 * 86400000);
    if (now < st) ev.status = "upcoming";
    else if (now <= en) ev.status = "live";
    else ev.status = "done";
  } catch { /* keep */ }
  return ev;
}

function upStatus(s, e, now) {
  if (!s) return "upcoming";
  try {
    const st = new Date(s), en = e ? new Date(e) : new Date(st.getTime() + 7 * 86400000);
    if (now < st) return "upcoming";
    if (now <= en) return "live";
    return "done";
  } catch { return "upcoming"; }
}

// ---------------------------------------------------------------------------
// build_config: dynamic event list (pure; HTML injected by Worker)
// ---------------------------------------------------------------------------

export function buildConfig({ oldEvents = [], falconsHtml = "", portalHtml = "", rejectSet = new Set(), now = new Date() }) {
  const cfg = [];
  const seen = new Set();
  function add(c, base = null) {
    const sid = slug(c.page);
    if (seen.has(sid)) return;
    seen.add(sid);
    if (base !== null) { c = { ...c, _base: base }; }
    cfg.push(c);
  }

  const reserved = new Set([
    ...RECENT_CONFIG.map((c) => slug(c.page)),
    ...SEED_NEXT_CONFIG.map((c) => slug(c.page)),
    ...Object.keys(ZH_MAP).map((k) => slug(k)),
  ]);
  const oldIds = new Set(oldEvents.map((e) => e.id).filter(Boolean));

  // 1) dynamic future events (Falcons team page upcoming)
  for (const t of parseFalconsUpcoming(falconsHtml)) {
    const [s, e] = parseDateWindow(t.date_text, now);
    if (s) {
      try {
        const days = Math.floor((new Date(s) - now) / 86400000);
        if (days > HORIZON_DAYS) {
          // [视野外] skip detail fetch but still listed in homepage schedule
          continue;
        }
      } catch { /* keep */ }
    }
    const base = { start: s || "", end: e || "", date_text: t.date_text, tier: t.tier || "Unknown", note: "" };
    add({ page: t.page, zh: ZH_MAP[t.page] || t.name, short: ZH_MAP[t.page] || t.short,
          tag: "next", tier: t.tier || "Unknown", match: t.name }, base);
  }

  // 1.5) calendar auto-discovery
  try {
    const portal = parsePortalTournaments(portalHtml);
    let added = 0;
    const entries = Object.entries(portal).sort((a, b) => b[1] - a[1]);
    for (const [page, cnt] of entries) {
      const sid = slug(page);
      if (cnt < DISCOVER_MIN_ROWS || seen.has(sid) || reserved.has(sid)) continue;
      if (rejectSet.has(page)) continue;
      let oldEv = null;
      for (const e of oldEvents) { if (e.id === sid) { oldEv = e; break; } }
      if (oldEv !== null) {
        if (oldEv.status === "done") continue;
        add({ page, zh: oldEv.name || page, short: oldEv.short || page, tag: "next",
              tier: oldEv.tier || "Unknown", match: "", _discover: !!oldEv._discover },
            { start: oldEv.start || "", end: oldEv.end || "", date_text: oldEv.date_text || "",
              tier: oldEv.tier || "", note: oldEv.note || "" });
        continue;
      }
      if (added >= DISCOVER_LIMIT) continue;
      const pretty = page.replace(/_/g, " ");
      const short = pretty.split("/").pop();
      add({ page, zh: ZH_MAP[page] || pretty, short: ZH_MAP[page] || short, tag: "next",
            tier: "Unknown", match: "", _discover: true }, { start: "", end: "", date_text: "", tier: "", note: "" });
      added++;
      // [发现] console.log(...)
    }
  } catch { /* warn */ }

  // 2) revive live events from old event.json
  for (const ev of oldEvents) {
    if (ev.status !== "live") continue;
    const page = pageFromSource(ev.source || "");
    if (!page) continue;
    add({ page, zh: ev.name || page, short: ev.short || ev.name || page, tag: "next",
          tier: ev.tier || "Unknown", match: ev.name || "" },
        { start: ev.start || "", end: ev.end || "", date_text: ev.date_text || "", tier: ev.tier || "", note: ev.note || "" });
  }

  // 3) seed fallback if no dynamic next events
  if (!cfg.some((c) => c.tag === "next")) {
    for (const c of SEED_NEXT_CONFIG) add(c);
  }

  // 4) recent always-present
  for (const c of RECENT_CONFIG) add(c);

  return cfg;
}

// Re-export for the Worker to reuse status recompute
export { recomputeStatus, upStatus };
