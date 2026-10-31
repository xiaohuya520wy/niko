// Port of parse_event.py -> JS (build + all helpers). Pure logic (no CF APIs).
// Self-heal via Scrapling is intentionally omitted (Python degrades to pure-regex too);
// build() runs with url === undefined.

const ENT = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", ndash: "–",
  mdash: "—", rsquo: "’", lsquo: "‘", ldquo: "“", rdquo: "”", hellip: "…",
  copy: "©", reg: "®", times: "×", middot: "·", eacute: "é", aacute: "á",
  iacute: "í", oacute: "ó", uacute: "ú", ntilde: "ñ", ccedil: "ç", ouml: "ö",
  uuml: "ü", szlig: "ß", deg: "°", ordm: "º", sup2: "²", trade: "™",
  frac12: "½", frac14: "¼", frac34: "¾", bull: "•", euro: "€", pound: "£",
  cent: "¢", raquo: "»", laquo: "«",
};
export function htmlUnescape(s) {
  return (s || "").replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, (m, e) => {
    if (e[0] === "#") {
      const code = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      return String.fromCodePoint(code);
    }
    const v = ENT[e.toLowerCase()];
    return v !== undefined ? v : m;
  });
}

function _cls(attrs) {
  const m = /class="([^"]*)"/.exec(attrs || "");
  return m ? m[1] : "";
}
export function _text(s) {
  return htmlUnescape((s || "").replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
}
export function prep(h) {
  return h.replace(/&#95;/g, "_");
}

export function headings(h) {
  const out = [];
  const re = /<h([2-6])\b[^>]*>(.*?)<\/h\1>/gs;
  let m;
  while ((m = re.exec(h)) !== null) {
    let t = _text(m[2]).replace(/\[edit\]$/, "").trim();
    if (t) out.push([m.index, parseInt(m[1], 10), t]);
  }
  return out;
}
export function nearestHeading(h, pos, hs) {
  hs = hs !== undefined ? hs : headings(h);
  let best = "";
  for (const [p, lvl, t] of hs) {
    if (p < pos) best = t;
    else break;
  }
  return best;
}
export function sectionHtml(h, name, hs) {
  hs = hs !== undefined ? hs : headings(h);
  for (let i = 0; i < hs.length; i++) {
    const [p, lvl, t] = hs[i];
    if (t.toLowerCase() === name.toLowerCase()) {
      let end = h.length;
      for (let j = i + 1; j < hs.length; j++) {
        if (hs[j][1] <= lvl) { end = hs[j][0]; break; }
      }
      return h.slice(p, end);
    }
  }
  return "";
}

// ---------------------------------------------------------------- participants
export function parseParticipants(h) {
  h = prep(h);
  const seg = sectionHtml(h, "Participants");
  if (!seg) return [];
  const out = [];
  const seen = new Set();
  for (const blk of seg.split(/team-participant-card__opponent(?:"|\s)/).slice(1)) {
    const head = blk.slice(0, 1200);
    const nm = /<a href="\/counterstrike\/[^"]+" title="([^"]+)"/.exec(head);
    if (!nm) continue;
    const name = htmlUnescape(nm[1]).trim();
    if (!name || seen.has(name)) continue;
    let logo = "";
    for (const im of head.matchAll(/<img[^>]*src="([^"]+)"/g)) {
      const u = im[1];
      if (/darkmode/.test(u)) continue;
      logo = u;
      break;
    }
    seen.add(name);
    out.push({ name, logo });
  }
  return out;
}

// ---------------------------------------------------------------- group tables
function standingsRows(seg) {
  const rows = [];
  for (const rm of seg.matchAll(/<tr>(.*?)<\/tr>/gs)) {
    const r = rm[1];
    if (!/<\s*td\b/.test(r)) continue;
    let team = "";
    for (const m of r.matchAll(/data-highlightingclass="([^"]+)"/g)) {
      const v = htmlUnescape(m[1]).trim();
      if (v && v.toUpperCase() !== "TBD") { team = v; break; }
    }
    if (!team) {
      const tn = /<a href="\/counterstrike\/[^"]+" title="([^"]+)"/.exec(r);
      if (tn) team = htmlUnescape(tn[1]).trim();
    }
    if (!team || team.toUpperCase() === "TBD") continue;
    const tds = [...r.matchAll(/<\s*td\b[^>]*>(.*?)<\/td>/gs)].map((x) => x[1]);
    const nums = [];
    for (const td of tds) {
      const t = _text(td);
      if (/^\d+(?:[.:\-]\d+)?$/.test(t || "")) nums.push(t);
    }
    rows.push({ team: team.replace(/^Team\s+/, ""), nums });
  }
  return rows;
}
export function parseGroupTables(h) {
  h = prep(h);
  const out = [];
  for (const tm of h.matchAll(/<table[^>]*class="[^"]*(?:swisstable|table2__table|wikitable)[^"]*"[^>]*>/g)) {
    const start = tm.index;
    const end = h.indexOf("</table>", start);
    if (end < 0) continue;
    const seg = h.slice(start, end);
    const title = nearestHeading(h, start) || "积分榜";
    const head = /<tr>(.*?)<\/tr>/s.exec(seg);
    if (!head) continue;
    const cols = [...head[1].matchAll(/<\s*th\b[^>]*>(.*?)<\/th>/gs)].map((x) => _text(x[1])).filter(Boolean);
    const joined = cols.join(" ").toLowerCase();
    if (!/team/.test(joined) || !cols.some((c) => /matches|rounds|pts|points|w/.test(c))) continue;
    const rows = standingsRows(seg);
    if (rows.length < 2) continue;
    out.push({ title, cols, rows });
  }
  const merged = new Map();
  for (const t of out) {
    if (!merged.has(t.title)) merged.set(t.title, t);
    else {
      const have = new Set(merged.get(t.title).rows.map((r) => r.team));
      for (const r of t.rows) if (!have.has(r.team)) merged.get(t.title).rows.push(r);
    }
  }
  return [...merged.values()];
}

// ---------------------------------------------------------------- brackets
function ancestorDepth(h, pos) {
  const re = /<div\b([^>]*)>|<\/div>/gi;
  let stack = [], depth = 0, m;
  while ((m = re.exec(h.slice(0, pos))) !== null) {
    if (m[1] === undefined) {
      if (stack.length) {
        if (stack.pop()) depth--;
      }
    } else {
      const isRb = /brkts-round-body/.test(_cls(m[1]));
      stack.push(isRb);
      if (isRb) depth++;
    }
  }
  return depth;
}
function entries(blk) {
  const marks = [...blk.matchAll(/<div class="brkts-opponent-entry(?:"|\s)/g)].map((m) => m.index);
  const out = [];
  for (let i = 0; i < Math.min(2, marks.length); i++) {
    const p = blk.slice(marks[i], marks[i + 1] !== undefined ? marks[i + 1] : blk.length);
    const nm = /aria-label="([^"]*)"/.exec(p.slice(0, 400));
    const short = /data-team-shortname="([^"]*)"/.exec(p.slice(0, 1500));
    const sc = /brkts-opponent-score-inner[^>]*>\s*(?:<b>)?\s*(\d+)/.exec(p);
    const win = /brkts-opponent-entry-left[^"]*brkts-opponent-win/.test(p.slice(0, 600));
    let name = nm ? htmlUnescape(nm[1]).trim() : "";
    name = name.replace(/^Team\s+/, "");
    if (["TBD", "TO BE DETERMINED", "–", "-"].includes(name.toUpperCase())) name = "";
    out.push({
      name,
      full: name,
      short: short ? htmlUnescape(short[1]).trim() : "",
      score: sc ? parseInt(sc[1], 10) : null,
      win,
    });
  }
  return out;
}
export function parseDefaultBo(h) {
  h = prep(h);
  const seg = sectionHtml(h, "Format");
  if (!seg) return "";
  let m = /All matches are.*?<abbr[^>]*>\s*(Bo\d)/s.exec(seg);
  if (m) return m[1];
  m = /<abbr title="Best of \d">\s*(Bo\d)\s*<\/abbr>/.exec(seg);
  if (m) return m[1];
  m = /(Bo\d)/.exec(seg);
  return m ? m[1] : "";
}
function cleanLiteral(s) {
  s = (s || "").replace(/<\/?(?:sup|sub|small|b|i|em|strong|span)\b[^>]*>/gi, "");
  s = s.replace(/<[^>]+>/g, " ");
  s = htmlUnescape(s);
  return s.replace(/\s+/g, " ").trim();
}
function opponentName(row) {
  let nm = "";
  for (const am of row.matchAll(/<a href="\/counterstrike\/([^"#?]+)"[^>]*title="([^"]*)"/g)) {
    const path = am[1], title = htmlUnescape(am[2]).trim();
    if (path.includes(":")) continue;
    nm = title.replace(/^Team\s+/, "") || path.replace(/_/g, " ").trim();
    break;
  }
  if (!nm || ["TBD", "TO BE DETERMINED", "–", "-"].includes(nm.toUpperCase())) {
    const lit = /brkts-opponent-block-literal[^>]*>(.*?)<\/div>/s.exec(row);
    nm = lit ? cleanLiteral(lit[1]) : "";
  }
  if (!nm || ["TBD", "TO BE DETERMINED", "–", "-"].includes(nm.toUpperCase())) nm = "TBD";
  return nm;
}
export function parseUpcoming(h, limit = 16) {
  h = prep(h);
  let seg = sectionHtml(h, "Upcoming Matches");
  if (!seg) seg = sectionHtml(h, "Upcoming Games");
  if (!seg) return [];
  const defaultBo = parseDefaultBo(h);
  const out = [];
  for (const blk of seg.split(/<div class="match-info(?:"|\s)/).slice(1)) {
    const ts = /timer-object[^>]*data-timestamp="(\d+)"/.exec(blk);
    if (!ts) continue;
    const stage = /match-info-stage">([^<]*)</.exec(blk);
    const sides = [];
    for (const row of blk.split(/<div class="match-info-opponent-row(?:"|\s)/).slice(1, 3)) {
      const nm = opponentName(row);
      const sc = /match-info-opponent-score[^>]*>\s*(\d+)/.exec(row);
      sides.push({ name: nm, score: sc ? parseInt(sc[1], 10) : null });
    }
    if (sides.length < 2) continue;
    const bo = /\((Bo\d)\)/.exec(blk);
    const [sa, sb] = [sides[0].score, sides[1].score];
    let wa = false, wb = false;
    if (sa !== null && sb !== null && sa !== sb) [wa, wb] = [sa > sb, sb > sa];
    out.push({
      stage: stage ? stage[1].trim() : "",
      bo: bo ? bo[1] : defaultBo,
      ts: parseInt(ts[1], 10),
      a: { name: sides[0].name, full: sides[0].name, short: "", score: sa, win: wa },
      b: { name: sides[1].name, full: sides[1].name, short: "", score: sb, win: wb },
    });
  }
  if (!out.length) out.push(...upcomingGeneric(h, defaultBo, limit));
  return out.slice(0, limit);
}
export function upcomingGeneric(h, defaultBo = "", limit = 16) {
  const out = [];
  const seen = new Set();
  for (const m of h.matchAll(/timer-object[^>]*data-timestamp="(\d+)"/g)) {
    const ts = parseInt(m[1], 10);
    const blk = h.slice(m.index, m.index + 4000);
    const stage = /match-info-stage">([^<]*)</.exec(blk);
    let names = [];
    for (const row of blk.split(/<div class="match-info-opponent-row(?:"|\s)/).slice(1, 3))
      names.push(opponentName(row));
    if (names.length < 2)
      for (const x of blk.matchAll(/brkts-matchlist-opponent[^>]*aria-label="([^"]*)"/g)) {
        const v = htmlUnescape(x[1]).trim().replace(/^Team\s+/, "");
        if (v && !["TBD", "TO BE DETERMINED", "–", "-"].includes(v.toUpperCase())) {
          names.push(v);
          if (names.length === 2) break;
        }
      }
    while (names.length < 2) names.push("TBD");
    const key = `${ts}|${names[0]}|${names[1]}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      stage: stage ? stage[1].trim() : "即将开赛",
      bo: defaultBo,
      ts,
      a: { name: names[0], full: names[0], short: "", score: null, win: false },
      b: { name: names[1], full: names[1], short: "", score: null, win: false },
    });
    if (out.length >= limit) break;
  }
  return out;
}
export function parseBrackets(h) {
  const hs = headings(h);
  const starts = [...h.matchAll(/<div class="brkts-bracket[ "]/g)].map((m) => m.index);
  const brackets = [];
  for (let i = 0; i < starts.length; i++) {
    const end = i + 1 < starts.length ? starts[i + 1] : h.length;
    let body = h.slice(starts[i], end);
    const mpos = [...body.matchAll(/<div class="brkts-match[ "]/g)].map((m) => m.index);
    if (!mpos.length) continue;
    const cut = Math.min(body.length, mpos[mpos.length - 1] + 60000);
    body = body.slice(0, cut);
    const heads = [...body.matchAll(/<div class="brkts-header brkts-header-div"[^>]*>([^<]*)/g)]
      .map((x) => htmlUnescape(x[1]).trim())
      .filter((x) => x && !/^(qualified|eliminated)$/i.test(x));
    const matches = [];
    for (let k = 0; k < mpos.length; k++) {
      const blk = body.slice(mpos[k], mpos[k + 1] !== undefined ? mpos[k + 1] : body.length);
      const ent = entries(blk);
      if (ent.length < 2) continue;
      if (!ent[0].name && !ent[1].name) continue;
      const ts = /data-timestamp="(\d+)"/.exec(blk);
      const bo = /scoreholder-lower">\((Bo\d)\)/.exec(blk);
      matches.push({
        a: ent[0], b: ent[1],
        ts: ts ? parseInt(ts[1], 10) : null,
        bo: bo ? bo[1] : "",
        depth: ancestorDepth(body, mpos[k]),
      });
    }
    if (!matches.length) continue;
    const maxd = Math.max(...matches.map((m) => m.depth));
    for (const m of matches) m.round = maxd - m.depth;
    const nround = maxd;
    const rounds = [];
    for (let r = 0; r <= nround; r++) {
      const ms = matches.filter((m) => m.round === r);
      if (!ms.length) continue;
      const name = r < heads.length ? heads[r] : `第 ${r + 1} 轮`;
      ms.sort((x, y) => (x.ts || 0) - (y.ts || 0) || (x.a.name < y.a.name ? -1 : 1));
      rounds.push({ name, matches: ms });
    }
    if (rounds.length)
      brackets.push({ title: nearestHeading(h, starts[i], hs) || "分支图", rounds, count: matches.length });
  }
  const seen = new Set(), uniq = [];
  for (const b of brackets) {
    const key = `${b.title}|${b.count}`;
    if (seen.has(key)) continue;
    seen.add(key);
    uniq.push(b);
  }
  return uniq;
}

// ---------------------------------------------------------------- matchlist
const MONTHS = { January: 1, February: 2, March: 3, April: 4, May: 5, June: 6, July: 7, August: 8, September: 9, October: 10, November: 11, December: 12 };
function dateHeaderZh(t) {
  const m = /([A-Za-z]+)\s+(\d{1,2})/.exec((t || "").trim());
  const mo = m ? MONTHS[m[1].replace(/^./, (c) => c.toUpperCase())] : undefined;
  if (!mo) return (t || "").trim();
  return `${mo}月${parseInt(m[2], 10)}日`;
}
function stageOf(h, pos, hs) {
  hs = hs !== undefined ? hs : headings(h);
  let best = "";
  for (const [p, lvl, t] of hs) {
    if (p >= pos) break;
    if (/^Round\s*\d+$/.test(t) || ["High", "Mid", "Low", "Overview", "Detailed Results"].includes(t)) continue;
    best = t;
  }
  return best;
}
export function parseMatchlist(h) {
  h = prep(h);
  const miter = [...h.matchAll(/<div class="brkts-matchlist-match/g)];
  if (!miter.length) return [];
  const hdrPos = [...h.matchAll(/<div class="brkts-matchlist-header[^>]*>(.*?)<\/div>/gs)]
    .map((mh) => [mh.index, _text(mh[1]).trim()]);
  const defaultBo = parseDefaultBo(h);
  const groups = {}, order = [];
  for (const m of miter) {
    let name = "";
    for (const [hp, ht] of hdrPos) {
      if (hp < m.index) name = ht;
      else break;
    }
    const blk = h.slice(m.index, m.index + 5000);
    const names = [...blk.matchAll(/brkts-matchlist-opponent[^>]*aria-label="([^"]*)"/g)]
      .map((x) => htmlUnescape(x[1]).trim().replace(/^Team\s+/, ""))
      .filter((x) => x && !["TBD", "TO BE DETERMINED", "–", "-"].includes(x.toUpperCase()));
    if (names.length < 2) continue;
    const sc = [...blk.matchAll(/brkts-matchlist-score[^>]*>.*?cell-content">([^<]*)/gs)].map((x) => x[1].trim());
    const sa = sc.length > 0 && /^\d+$/.test(sc[0]) ? parseInt(sc[0], 10) : null;
    const sb = sc.length > 1 && /^\d+$/.test(sc[1]) ? parseInt(sc[1], 10) : null;
    const tsM = /timer-object[^>]*data-timestamp="(\d+)"/.exec(blk);
    const ts = tsM ? parseInt(tsM[1], 10) : null;
    let wa = false, wb = false;
    if (sa !== null && sb !== null && sa !== sb) [wa, wb] = [sa > sb, sb > sa];
    const md = {
      a: { name: names[0], full: names[0], short: "", score: sa, win: wa },
      b: { name: names[1], full: names[1], short: "", score: sb, win: wb },
      ts, bo: defaultBo, depth: 0,
    };
    const key = name || "对阵";
    if (!groups[key]) { groups[key] = []; order.push(key); }
    groups[key].push(md);
  }
  if (!Object.keys(groups).length) return [];
  const title = stageOf(h, miter[0].index) || "小组赛";
  const rounds = order
    .filter((k) => groups[k].length)
    .map((k) => ({
      name: /^([A-Za-z]+ \d)/.test(k) ? dateHeaderZh(k) : k,
      matches: groups[k],
    }));
  if (!rounds.length) return [];
  return [{ title, rounds, count: rounds.reduce((s, r) => s + r.matches.length, 0) }];
}

// ---------------------------------------------------------------- schedule
function dedupSort(rows, limit = 40) {
  const seen = new Set(), uniq = [];
  for (const r of rows.slice().sort((x, y) => x.ts - y.ts)) {
    const k = `${r.ts}|${r.a.name}|${r.b.name}`;
    if (seen.has(k)) continue;
    seen.add(k);
    uniq.push(r);
  }
  return uniq.slice(0, limit);
}
export function scheduleFromBrackets(brackets, limit = 40) {
  const rows = [];
  for (const b of brackets || [])
    for (const rd of b.rounds || [])
      for (const m of rd.matches || [])
        if (m.ts)
          rows.push({ stage: b.title, round: rd.name, bo: m.bo, ts: m.ts, a: m.a, b: m.b });
  return dedupSort(rows, limit);
}
export function parseSchedule(h, limit = 40) {
  return scheduleFromBrackets(parseBrackets(h), limit);
}

// ---------------------------------------------------------------- overview
export function parseOverview(h, name) {
  h = prep(h);
  const out = { name };
  const about = sectionHtml(h, "About");
  const prize = sectionHtml(h, "Prize Pool");
  const fmt = sectionHtml(h, "Format");
  const grab = (seg, pats, keys) => {
    for (let i = 0; i < pats.length; i++) {
      const m = new RegExp(pats[i], "s").exec(seg);
      if (m) out[keys[i]] = _text(m[1]).slice(0, 80);
    }
  };
  grab(about, [
    '<div class="infobox-cell-2[^"]*">Dates?</div>\\s*<div[^>]*>(.*?)</div>',
    '>Dates?</t[dh]>\\s*<td[^>]*>(.*?)</td>',
    '<div class="infobox-cell-2[^"]*">Location</div>\\s*<div[^>]*>(.*?)</div>',
    '<div class="infobox-cell-2[^"]*">Venue</div>\\s*<div[^>]*>(.*?)</div>',
    '<div class="infobox-cell-2[^"]*">Prize Pool</div>\\s*<div[^>]*>(.*?)</div>',
    '<div class="infobox-cell-2[^"]*">Teams</div>\\s*<div[^>]*>(.*?)</div>',
    '<div class="infobox-cell-2[^"]*">\\s*Liquipedia [tT]ier:?\\s*</div>\\s*<div[^>]*>(.*?)</div>',
    '>Liquipedia [tT]ier:?</t[dh]>\\s*<td[^>]*>(.*?)</td>',
  ], ["dates", "dates", "location", "venue", "prize", "teams", "tier", "tier"]);
  if (!("prize" in out) && prize) {
    const m = /[$€£][\d,.]+/.exec(_text(prize));
    if (m) out.prize = m[0];
  }
  if (fmt) out.format_raw = _text(fmt).slice(0, 400);
  if (!("tier" in out)) {
    const m = /<div class="infobox-cell-2[^"]*">\s*Liquipedia [tT]ier:?\s*<\/div>\s*<div[^>]*>(.*?)<\/div>/s.exec(h);
    if (m) out.tier = _text(m[1]).slice(0, 80);
  }
  return out;
}

// ---------------------------------------------------------------- build
export function build(pageName, htmlText, displayName = "") {
  const h = htmlText;
  const d = {
    page: pageName,
    info: parseOverview(h, displayName || pageName),
    participants: parseParticipants(h),
    groups: parseGroupTables(h),
    brackets: parseBrackets(h),
    upcoming: parseUpcoming(h),
  };
  const ml = parseMatchlist(h);
  if (ml.length) d.brackets = d.brackets.concat(ml);
  d.schedule = scheduleFromBrackets(d.brackets);
  return d;
}

export function parseHealth(h, d) {
  h = prep(h);
  const warns = [];
  const realTeams = (seg) => new Set([...seg.matchAll(/<a href="\/counterstrike\/[^"]+" title="(?!TBD)([^"]+)"/g)].map((x) => x[1]));
  if (!(d.groups || d.brackets || d.schedule)) {
    for (const m of h.matchAll(/<table class="[^"]*wikitable[^"]*"[^>]*>(.*?)<\/table>/gs)) {
      if (realTeams(m[1]).size >= 4) { warns.push("page has a standings-like wikitable but groups=0"); break; }
    }
  }
  if (!(d.brackets || []).length && h.includes("brkts-bracket")) {
    const segs = h.split("brkts-bracket").slice(1);
    if (segs.some((s) => realTeams(s.slice(0, 4000)).size >= 4))
      warns.push("page has brackets with real teams but brackets=0");
  }
  if (!(d.upcoming || []).length && !(d.schedule || []).length) {
    if ((h.includes("Upcoming Matches") || h.includes("Upcoming Games")) && /timer-object[^>]*data-timestamp/.test(h))
      warns.push("page has Upcoming Matches with timestamps but upcoming=0 and schedule=0");
  }
  return warns;
}
