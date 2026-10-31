// niko-scheduler —— Cloudflare Worker，全量替代 GitHub Actions 的数据管线。
//
// 设计：
//   - 每次 cron（每 5 分钟）只抓取【1 个】最旧的赛事/战队页（不 sleep）。
//     5 分钟间隔天然满足 Liquipedia「1 次 / 30 秒」限流，且单次调用墙钟仅数秒，
//     稳过 Workers 的任何时限。原始 HTML 缓存进 KV，永不丢失。
//   - 当「赛事中心」所需的页全部新鲜 -> assemble event.json；
//     当「比赛列表」所需的页全部新鲜 -> assemble data.json（含 upcoming + 选手刷新）。
//     两者独立判定，互不阻塞。
//   - 写 KV 前带 write-guard（数量骤降则保留旧数据，宁旧不空）。
//   - 零 GitHub 依赖：抓取=Worker fetch，存储=KV，服务=Pages Function，部署=wrangler。

import * as FE from "../worker_pipeline/fetchEvent.js";
import * as PE from "../worker_pipeline/parseEvent.js";
import * as PL from "../worker_pipeline/pipeline.js";
import * as PD from "../worker_pipeline/parseDetail.js";
import * as PLAYER from "../worker_pipeline/player.js";

const API = "https://liquipedia.net/counterstrike/api.php?";
const UA = {
  "User-Agent":
    "NikoTracker/1.0 (CS2 fan page; contact: user@example.com)",
  // Liquipedia API 强制要求 Accept-Encoding: gzip，否则一律返回 406
  // （详见 liquipedia.net/api-terms-of-use）。Cloudflare Workers 的 fetch 会自动
  // 解压 gzip，这里显式声明以满足对端校验 —— 这是此前整条管线卡死的根因。
  "Accept-Encoding": "gzip",
};
const KV = "NikoData"; // wrangler.toml 中绑定的 KV namespace 名

// 历史/常驻赛事页（与 pipeline.py PAGES 一致）。这些页决定 data.json 的比赛列表。
const PAGES = [
  "BLAST/Open/2025/Fall",
  "FISSURE/Playground/2",
  "FISSURE/Playground/3",
  "ESL/Pro_League/Season_22",
  "BLAST/Bounty/2026/Winter",
  "Intel_Extreme_Masters/2026/Kraków",
  "PGL/2026/Cluj-Napoca",
  "BLAST/Open/2026/Spring",
  "BLAST/Open/2026/Fall",
  "Intel_Extreme_Masters/2026/Rio",
  "PGL/2026/Astana",
  "CS_Asia_Championships/2026",
  "Esports_World_Cup/2026",
  "Intel_Extreme_Masters/2026/Cologne",
  "BLAST/Bounty/2026/Summer",
  "Intel_Extreme_Masters/2026/Cologne/Stage_3",
  "Intel_Extreme_Masters/2026/Cologne/Playoffs",
  "BLAST/Bounty/2026/Summer/Qualifier",
];

const SPECIAL = ["Team Falcons", "Liquipedia:Matches", "NiKo"];

// ---- 安全阀 / 时效阈值（与 run.py 对齐）----
const MIN_KEEP = 0.8;
const EVENT_MAX_AGE_HOURS = 2; // 已缓存页超过该年龄才回捞刷新
const EVENT_MAX_AGE_LIVE_HOURS = 0.2; // 直播页超过 12min 即强制高频刷新
const ASSEMBLE_MAX_AGE_HOURS = 6; // 凑齐判定的宽限：允许部分页 ≤6h 旧仍能 assemble
const BATCH = 2; // 每轮最多抓几页（兼顾 Liquipedia 限流与刷新速度）

// ---------------------------------------------------------------------------
// KV 辅助
// ---------------------------------------------------------------------------
function kvGet(env, key) {
  return env[KV].get(key, { type: "json" });
}
function kvPut(env, key, obj) {
  return env[KV].put(key, JSON.stringify(obj));
}
function htmlKey(page) {
  return "html:" + encodeURIComponent(page);
}
function getHtml(env, page) {
  return kvGet(env, htmlKey(page));
}
function putHtml(env, page, html) {
  return kvPut(env, htmlKey(page), { html, ts: Date.now() });
}

// ---------------------------------------------------------------------------
// Liquipedia 抓取（Worker 原生 fetch 自动处理 gzip）
// ---------------------------------------------------------------------------
async function fetchLiquipedia(page) {
  const url =
    API +
    new URLSearchParams({ action: "parse", page, prop: "text", format: "json" });
  const res = await fetch(url, { headers: UA, signal: AbortSignal.timeout(20000) });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${page}`);
  const json = await res.json();
  // Liquipedia 偶发返回错误体（如限流/缺页）而非 {parse:{text}} —— 给清晰报错，便于定位。
  if (!json || !json.parse || json.parse.text == null) {
    const keys = json ? Object.keys(json).join(",") : "(无 JSON)";
    throw new Error(`Liquipedia 无 parse.text：${page}（响应键：${keys}）`);
  }
  return json.parse.text["*"];
}

// ---------------------------------------------------------------------------
// 工具
// ---------------------------------------------------------------------------
function ageHours(entry, now) {
  if (!entry || !entry.ts) return Infinity;
  return (now - entry.ts) / 3600000;
}
function pagesFromEvents(oldEventJson) {
  const out = [];
  const marker = "/counterstrike/";
  for (const e of (oldEventJson && oldEventJson.events) || []) {
    const src = e.source || "";
    if (!src.includes(marker)) continue;
    const page = decodeURIComponent(src.split(marker)[1])
      .trim()
      .replace(/^\/+|\/+$/g, "");
    if (page) out.push(page);
  }
  return out;
}
function recomputeStatus(ev, now) {
  const s = ev.start,
    e = ev.end;
  if (!s) return ev;
  try {
    const st = new Date(s),
      en = e ? new Date(e) : new Date(st.getTime() + 7 * 86400000);
    if (now < st) ev.status = "upcoming";
    else if (now <= en) ev.status = "live";
    else ev.status = "done";
  } catch {
    /* keep */
  }
  return ev;
}
function isoNow(nowDt) {
  return nowDt.toISOString().replace(/\.\d{3}Z$/, "+00:00");
}

// ---------------------------------------------------------------------------
// event.json 组装（忠实复刻 fetch_event.main）
// ---------------------------------------------------------------------------
export async function assembleEvent(env, nowDt, oldEvent, oldData, rejectSet) {
  const oldEvents = (oldEvent && oldEvent.events) || [];
  const oldById = {};
  const knownStatus = {};
  for (const e of oldEvents)
    if (e.id) {
      oldById[e.id] = e;
      knownStatus[e.id] = e.status;
    }

  const falconsEntry = await getHtml(env, "Team Falcons");
  const portalEntry = await getHtml(env, "Liquipedia:Matches");
  if (
    !falconsEntry ||
    !falconsEntry.html ||
    !portalEntry ||
    !portalEntry.html
  ) {
    return { ok: false, reason: "falcons/portal 尚未缓存" };
  }

  const CONFIG = FE.buildConfig({
    oldEvents,
    falconsHtml: falconsEntry.html,
    portalHtml: portalEntry.html,
    rejectSet,
    now: nowDt,
  });

  const events = [];
  const usedIds = new Set();
  const rejectedIds = new Set();
  const degraded = [];
  let fetched = 0;

  const base = {};
  if (oldData && oldData.upcoming_tournaments) {
    for (const t of oldData.upcoming_tournaments) {
      base[t.short] = t;
      base[t.name] = t;
    }
  }

  for (const cfg of CONFIG) {
    const sid = FE.slug(cfg.page);
    const skipFetch = knownStatus[sid] === "done";
    if (skipFetch) {
      const old = oldById[sid];
      if (old) {
        const ev = recomputeStatus({ ...old }, nowDt);
        if (ev.status === "done") ev.tag = "recent";
        events.push(ev);
        usedIds.add(sid);
      }
      continue;
    }
    const entry = await getHtml(env, cfg.page);
    if (!entry || !entry.html) continue; // 本轮还没抓到
    fetched++;
    // Worker 不 sleep：cron 间隔天然限流
    let info = cfg._base || null;
    if (!info && !cfg._discover) {
      for (const [k, v] of Object.entries(base)) {
        if (cfg.match && cfg.match.toLowerCase().includes((k || "").toLowerCase())) {
          info = v;
          break;
        }
        if (
          cfg.short &&
          cfg.short.toLowerCase().includes((k || "").toLowerCase())
        ) {
          info = v;
          break;
        }
      }
    }
    let ev;
    try {
      ev = FE.buildEvent(cfg, entry.html, info, nowDt);
    } catch {
      continue;
    }
    const warns = PE.parseHealth(entry.html, ev);
    if (warns && warns.length) {
      const evOld = oldById[ev.id];
      const oldAlive =
        evOld && (evOld.groups || evOld.schedule || evOld.brackets);
      if (oldAlive) {
        evOld.parse_warning = warns;
        events.push(evOld);
        usedIds.add(ev.id);
        degraded.push(ev.id);
        continue;
      }
      events.push(ev);
      usedIds.add(ev.id);
      degraded.push(ev.id);
      continue;
    }
    if (cfg._discover) {
      const t = (ev.tier || "").toLowerCase();
      if (
        !t.includes("s-tier") &&
        !t.includes("a-tier") &&
        !t.includes("premier")
      ) {
        rejectSet.add(cfg.page);
        continue;
      }
      const tnames = (ev.teams || []).map((x) => (x.name || "").toLowerCase());
      if (tnames.length && !tnames.some((n) => n.includes("falcons"))) {
        rejectSet.add(cfg.page);
        rejectedIds.add(sid);
        continue;
      }
    }
    events.push(ev);
    usedIds.add(ev.id);
    if (cfg._discover) ev._discover = true;
  }

  // 携带历史归档：旧 event.json 里本轮没抓到的赛事原样补回
  for (const e of oldEvents) {
    const sid = e.id;
    if (!sid || usedIds.has(sid) || rejectedIds.has(sid)) continue;
    if (e._discover) {
      const tn = (e.teams || []).map((x) => (x.name || "").toLowerCase());
      if (tn.length && !tn.some((n) => n.includes("falcons"))) continue;
    }
    const ev = recomputeStatus({ ...e }, nowDt);
    if (ev.status === "done") ev.tag = "recent";
    events.push(ev);
    usedIds.add(sid);
  }

  events.sort((a, b) => {
    // next 赛事优先；同级再按开赛时间升序。
    // 旧写法 `tagDiff || a.start < b.start ? -1 : ...` 因 || 优先级高于三元，
    // 会把非 next 排到 next 前（方向写反）。此处显式分两步比较。
    const ta = a.tag === "next" ? 0 : 1;
    const tb = b.tag === "next" ? 0 : 1;
    if (ta !== tb) return ta - tb;
    const sa = a.start || "9999";
    const sb = b.start || "9999";
    return sa < sb ? -1 : sa > sb ? 1 : 0;
  });
  for (const ev of events)
    if (ev.status === "done" && ev.tag === "next") ev.tag = "recent";
  const featured =
    events.find((e) => e.status === "live") ||
    events.find((e) => e.status === "upcoming") ||
    events.find((e) => e.tag === "next") ||
    events[0] ||
    null;

  const data = {
    updated: isoNow(nowDt),
    featured,
    events,
    source_note: "赛事分组、分支图与赛程抓取自 Liquipedia（CC BY-SA 3.0）。",
  };

  const oldN = oldEvents.length;
  const newN = events.length;
  if (newN === 0 || newN < oldN) {
    return { ok: false, reason: `赛事数骤降 ${oldN}->${newN}，保留旧数据` };
  }
  await kvPut(env, "event.json", data);
  await kvPut(env, "reject", [...rejectSet]);
  return { ok: true, events: newN, degraded, fetched };
}

// ---------------------------------------------------------------------------
// data.json 组装（忠实复刻 run.py main 的比赛列表 + upcoming + 选手刷新）
// ---------------------------------------------------------------------------
export async function assembleData(env, nowDt, oldData) {
  const base = await kvGet(env, "base.json");
  if (!base) return { ok: false, reason: "缺少 base.json 种子" };
  const players = await kvGet(env, "players.json");
  const squad = (players && players.squad) || [];

  const oldEvent = (await kvGet(env, "event.json")) || { events: [] };
  const matchPages = [...new Set([...pagesFromEvents(oldEvent), ...PAGES])];

  const pages = {};
  for (const p of matchPages) {
    const entry = await getHtml(env, p);
    if (entry && entry.html) pages[p] = entry.html;
  }

  const matches = PL.buildMatches(pages, PL.EVENT_NAMES, PD.extract);

  // ★ A 修复：从 KV 读取 ratings.json（NiKo 逐场 HLTV Rating 持久库）并合并进比赛列表。
  //   旧逻辑传 null → 线上 data.json 评分骤降到 ~5/68；现在合并后回到 65/68，
  //   且每次重新 assemble 都不会再「越更新越少」。
  const ratingsKV = await kvGet(env, "ratings.json");
  const ratingsEntries = (ratingsKV && Array.isArray(ratingsKV.entries))
    ? ratingsKV.entries
    : [];
  const data = PL.assemble(base, matches, squad, ratingsEntries);

  // 战队页 upcoming -> data.json.upcoming_tournaments
  const falconsEntry = await getHtml(env, "Team Falcons");
  if (falconsEntry && falconsEntry.html) {
    const up = FE.deriveUpcomingList({
      falconsHtml: falconsEntry.html,
      now: nowDt,
    });
    if (up && up.length) data.upcoming_tournaments = up;
  }

  // 选手基础信息刷新（奖金/年龄/状态）
  const nikoEntry = await getHtml(env, "NiKo");
  if (nikoEntry && nikoEntry.html && data.player) {
    try {
      PLAYER.refresh(data.player, PLAYER.parse(nikoEntry.html));
    } catch {
      /* 抓不到就保留旧值 */
    }
  }

  data.meta = data.meta || {};
  data.meta.updated = isoNow(nowDt);

  const oldN =
    oldData && oldData.recent_matches ? oldData.recent_matches.length : 0;
  const newN = matches.length;
  if (newN === 0 || (oldN && newN < oldN * MIN_KEEP)) {
    return { ok: false, reason: `比赛数骤降 ${oldN}->${newN}，保留旧数据` };
  }
  await kvPut(env, "data.json", data);

  // ★ 历史赛事（history.json / 选手页）同步合并评分：只读改写，绝不改动比赛数据本身。
  //   这样「比赛一结束」后只要 ratings.json 里有这场评分，历史记录立刻带 rating 显示。
  let historyRated = 0;
  try {
    const hist = await kvGet(env, "history.json");
    if (Array.isArray(hist) && ratingsEntries.length) {
      const store = PL.loadRatingsStore(base, ratingsEntries);
      for (const m of hist) {
        const src = PL.matchRatings(store, (m.date || "").slice(0, 10), m.opponent);
        const niko = { ratings: (src && src.ratings) || [] };
        for (const k of ["kd", "adr", "note"]) if (src && src[k]) niko[k] = src[k];
        if (niko.ratings.length) historyRated++;
        m.niko = niko;
      }
      await kvPut(env, "history.json", hist);
    }
  } catch {
    /* 历史合并失败不影响主流程 */
  }

  return { ok: true, matches: newN, historyRated };
}

// ---------------------------------------------------------------------------
// NiKo 评分自动回补（未来/缺失场次）
// ---------------------------------------------------------------------------
// 评分的唯一权威源是 HLTV，而 HLTV 对所有数据中心/Worker 出口做 Cloudflare 挑战
// （直连 403 "Just a moment"）。本环境实测连本机办公 IP 也被挡，故纯免费出口无法
// 自动拿到评分。解决路径：在 Worker 配置反爬代理（env RATING_PROXY_URL，形如
// `https://api.scrapingbee.com/?api_key=KEY&url={url}` 或 ZenRows 同类），Worker
// 即可在比赛结束后抓取 HLTV 每图 stats 页、解析 NiKo 的 Rating 2.1 并写回
// ratings.json —— 下一次 assemble 会自动并入 data.json / history.json。
// 未配置代理时本模块静默跳过，站点照常运行（仅新比赛暂时缺评分，待手动回补）。
async function fetchRatingHtml(target, env) {
  const u = env.RATING_PROXY_URL
    ? env.RATING_PROXY_URL.replace("{url}", encodeURIComponent(target))
    : target;
  try {
    const r = await fetch(u, {
      headers: env.RATING_PROXY_URL ? {} : UA,
      signal: AbortSignal.timeout(15000),
    });
    if (!r.ok) return null;
    const t = await r.text();
    // HLTV 仍回挑战页 → 视为失败
    return t && /just a moment/i.test(t) ? null : t;
  } catch {
    return null;
  }
}

// 从 HLTV 单图 stats 页解析 NiKo 那一行的 Rating 2.1（末列）。
function parseNikoRating(html) {
  const trs = html.match(/<tr[^>]*>[\s\S]*?<\/tr>/g) || [];
  for (const tr of trs) {
    if (!/>NiKo</.test(tr)) continue;
    const cells = [...tr.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((c) =>
      c[1].replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ").trim()
    );
    if (cells.length >= 6) {
      const r = parseFloat(cells[cells.length - 1]);
      if (!isNaN(r)) return r;
    }
  }
  return null;
}

const oppKey2 = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]/g, "");

export async function backfillRatings(env, limit = 50) {
  const ratingsKV = await kvGet(env, "ratings.json");
  const entries = (ratingsKV && Array.isArray(ratingsKV.entries))
    ? ratingsKV.entries.slice()
    : [];
  const have = new Set(
    entries.map((e) => (e.date || "").slice(0, 10) + " " + oppKey2(e.opponent))
  );
  const data = await kvGet(env, "data.json");
  const rm = (data && data.recent_matches) || [];
  let processed = 0,
    got = 0;
  for (const m of rm) {
    if (processed >= limit) break;
    const d10 = (m.date || "").slice(0, 10);
    const opp = oppKey2(m.opponent);
    if (!d10 || !opp) continue;
    if (m.score === "0-0") continue; // 还没开打
    if (have.has(d10 + " " + opp)) continue; // 已有评分
    const hm = (m.links && m.links.hltv_maps) || [];
    if (!hm.length) continue;
    const urls = hm
      .slice()
      .sort((a, b) => (a.game || 0) - (b.game || 0))
      .map((x) => x.url)
      .filter(Boolean);
    if (!urls.length) continue;
    processed++;
    const ratings = [];
    let ok = true;
    for (const url of urls) {
      const html = await fetchRatingHtml(url, env);
      const r = html ? parseNikoRating(html) : null;
      if (r == null) {
        ok = false;
        break;
      }
      ratings.push(r);
    }
    if (ok && ratings.length) {
      entries.push({ date: d10, opponent: m.opponent, ratings });
      got++;
      have.add(d10 + " " + opp);
    }
  }
  let updated = null;
  if (got > 0) {
    updated = isoNow(new Date());
    await kvPut(env, "ratings.json", { updated, entries });
  }
  return { processed, got, total: entries.length, updated };
}

// ---------------------------------------------------------------------------
// 单次 cron：抓 1 页 + 视情况 assemble
// ---------------------------------------------------------------------------
export async function runTick(env) {
  const now = Date.now();
  const nowDt = new Date(now);
  const oldEvent = (await kvGet(env, "event.json")) || { events: [] };
  const oldData = await kvGet(env, "data.json");
  const rejectArr = (await kvGet(env, "reject")) || [];
  const rejectSet = new Set(rejectArr);

  // 计算所需页集合
  const matchPages = [...new Set([...pagesFromEvents(oldEvent), ...PAGES])];
  const needed = new Set([...SPECIAL, ...matchPages]);

  // 若 falcons/portal 已缓存，算出 eventPages 一并纳入抓取
  const falconsEntry = await getHtml(env, "Team Falcons");
  const portalEntry = await getHtml(env, "Liquipedia:Matches");
  if (falconsEntry && falconsEntry.html && portalEntry && portalEntry.html) {
    const CONFIG = FE.buildConfig({
      oldEvents: oldEvent.events || [],
      falconsHtml: falconsEntry.html,
      portalHtml: portalEntry.html,
      rejectSet,
      now: nowDt,
    });
    for (const c of CONFIG) needed.add(c.page);
  }

  // 计算「正在直播」的赛事页（实时比分需高频刷新）
  const livePages = new Set();
  for (const e of oldEvent.events || []) {
    if (e.status === "live") {
      const p = FE.pageFromSource(e.source || "");
      if (p) livePages.add(p);
    }
  }

  // 选定本次要抓的页：score 越大越优先。
  //   - 未缓存页：基础分 1e9（SPECIAL 再 +3，确保 Falcons/Portal/NiKo 优先起底）
  //   - 已缓存页：score = 真实年龄(小时)，越大越旧、越该刷新
  //   - 直播页：无论是否旧，score 拉满 1e15（每轮优先抓，保证实时比分 ≈5min 新鲜）
  // ⚠️ 之前的致命 bug：用「score 越小越先抓 + 未缓存记 -1e9」，
  //    导致全部缓存后永远挑【最新】的一页(age 最小)、从不回捞旧页，
  //    旧页老化越过 ASSEMBLE 时限后 assemble 永久失败 → 站点冻结。
  //    正确做法：挑【最旧】的页（score 取最大）。
  const priority = new Set(SPECIAL);
  const cands = [];
  for (const p of needed) {
    const entry = await getHtml(env, p);
    const age = ageHours(entry, now);
    const live = livePages.has(p);
    let score, need;
    if (!entry) {
      score = priority.has(p) ? 1e12 : 1e9;
      need = true;
    } else if (live && age > EVENT_MAX_AGE_LIVE_HOURS) {
      score = 1e15;
      need = true;
    } else {
      score = age; // 已缓存非直播：按真实年龄排序
      need = age > EVENT_MAX_AGE_HOURS; // 仅当超过 2h 才回捞刷新
    }
    cands.push({ p, age, score, need });
  }
  cands.sort((a, b) => b.score - a.score);

  let fetchedPage = null;
  let fetchErr = null;
  let picked = 0;
  for (const c of cands) {
    if (picked >= BATCH) break;
    if (!c.need) break; // 后续都是新鲜页，无需抓取
    try {
      const html = await fetchLiquipedia(c.p);
      await putHtml(env, c.p, html);
      if (!fetchedPage) fetchedPage = c.p;
      picked++;
    } catch (e) {
      fetchErr = String(e);
    }
  }

  // 判定是否可 assemble
  const falconsFresh =
    falconsEntry && ageHours(falconsEntry, now) <= ASSEMBLE_MAX_AGE_HOURS;
  const portalFresh =
    portalEntry && ageHours(portalEntry, now) <= ASSEMBLE_MAX_AGE_HOURS;

  let eventResult = { ok: false, reason: "未达 assemble 条件" };
  if (falconsFresh && portalFresh) {
    const CONFIG = FE.buildConfig({
      oldEvents: oldEvent.events || [],
      falconsHtml: falconsEntry.html,
      portalHtml: portalEntry.html,
      rejectSet,
      now: nowDt,
    });
    const eventPages = CONFIG.map((c) => c.page);
    // 严格判定：每个 eventPage 都需有缓存且在宽限内
    let ready = true;
    for (const p of eventPages) {
      const en = await getHtml(env, p);
      if (ageHours(en, now) > ASSEMBLE_MAX_AGE_HOURS) {
        ready = false;
        break;
      }
    }
    if (ready) {
      eventResult = await assembleEvent(
        env,
        nowDt,
        oldEvent,
        oldData,
        rejectSet
      );
    }
  }

  let dataResult = { ok: false, reason: "未达 assemble 条件" };
  {
    let ready = true;
    for (const p of matchPages) {
      const en = await getHtml(env, p);
      if (ageHours(en, now) > ASSEMBLE_MAX_AGE_HOURS) {
        ready = false;
        break;
      }
    }
    const nikoFresh =
      (await getHtml(env, "NiKo")) &&
      ageHours(await getHtml(env, "NiKo"), now) <= ASSEMBLE_MAX_AGE_HOURS;
    if (ready && nikoFresh) {
      dataResult = await assembleData(env, nowDt, oldData);
    }
  }

  // 评分自动回补：仅当配置了反爬代理（RATING_PROXY_URL）才执行，否则静默跳过，
  // 绝不拖慢或打断主管线。每次 cron 最多补 2 场，避免触发 HLTV 限流。
  let ratingResult = {
    ok: false,
    reason: "RATING_PROXY_URL 未配置：HLTV 对自动化出口全量 403，需配置反爬代理才能自动回补评分",
    skipped: true,
  };
  if (env.RATING_PROXY_URL) {
    try {
      ratingResult = await backfillRatings(env, 2);
      ratingResult.ok = true;
    } catch (e) {
      ratingResult = { ok: false, reason: String(e) };
    }
  }

  const result = {
    at: isoNow(nowDt),
    fetchedPage,
    fetchErr,
    event: eventResult,
    data: dataResult,
    rating: ratingResult,
    neededCount: needed.size,
  };

  // 心跳：每次 cron 都把本次结果写入 KV（含 fetchErr），便于在无法直连
  // workers.dev 时远程观测管线是否在跑、抓取是否被 Liquipedia 拒绝。
  try {
    await kvPut(env, "last_tick", {
      at: result.at,
      fetchedPage,
      fetchErr,
      event: {
        ok: eventResult.ok,
        reason: eventResult.reason,
        events: eventResult.events,
        degraded: eventResult.degraded,
      },
      data: {
        ok: dataResult.ok,
        reason: dataResult.reason,
        matches: dataResult.matches,
        historyRated: dataResult.historyRated,
      },
      rating: ratingResult,
      neededCount: needed.size,
    });
  } catch {
    /* 心跳写入失败不影响主流程 */
  }

  return result;
}

export async function tick(env) {
  try {
    return await runTick(env);
  } catch (e) {
    const msg = String(e);
    try {
      await kvPut(env, "last_tick", {
        at: new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00"),
        fatal: true,
        error: msg,
      });
    } catch {
      /* ignore */
    }
    return { at: new Date().toISOString(), fatal: msg };
  }
}

// ---------------------------------------------------------------------------
// fetch 处理器（手动触发 / 健康检查 / 状态）
// ---------------------------------------------------------------------------
function json(o, status) {
  return new Response(JSON.stringify(o, null, 2), {
    status: status || 200,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
    },
  });
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(tick(env));
  },

  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return json({
        ok: true,
        name: "niko-scheduler",
        cron: "*/5 * * * *",
        kv: KV,
        note: "全量 Cloudflare 管线，无 GitHub 依赖",
      });
    }
    if (url.pathname === "/trigger") {
      // 手动抓一页并尽量 assemble（用于测试 / 紧急刷新）
      return json(await tick(env));
    }
    if (url.pathname === "/assemble") {
      // 强制用当前缓存 assemble（忽略时效），用于调试
      const nowDt = new Date();
      const oldEvent = (await kvGet(env, "event.json")) || { events: [] };
      const oldData = await kvGet(env, "data.json");
      const rejectSet = new Set((await kvGet(env, "reject")) || []);
      const ev = await assembleEvent(env, nowDt, oldEvent, oldData, rejectSet);
      const da = await assembleData(env, nowDt, oldData);
      return json({ event: ev, data: da });
    }
    if (url.pathname === "/backfill-ratings") {
      // 手动触发评分回补（默认 50 场，可 ?limit=N）。需先配置 RATING_PROXY_URL。
      const limit = parseInt(url.searchParams.get("limit") || "50", 10);
      return json(await backfillRatings(env, limit));
    }
    if (url.pathname === "/status") {
      const now = Date.now();
      const oldEvent = (await kvGet(env, "event.json")) || { events: [] };
      const matchPages = [...new Set([...pagesFromEvents(oldEvent), ...PAGES])];
      const pages = [...new Set([...SPECIAL, ...matchPages])];
      const rows = [];
      for (const p of pages) {
        const en = await getHtml(env, p);
        rows.push({ page: p, ageH: +ageHours(en, now).toFixed(2) });
      }
      const ev = await kvGet(env, "event.json");
      const da = await kvGet(env, "data.json");
      return json({
        pages: rows,
        event_updated: ev && ev.updated,
        data_updated: da && da.meta && da.meta.updated,
        event_count: ev && ev.events ? ev.events.length : 0,
        match_count: da && da.recent_matches ? da.recent_matches.length : 0,
      });
    }
    return json({
      ok: true,
      message: "niko-scheduler (Cloudflare-only pipeline)",
      endpoints: ["/health", "/trigger", "/assemble", "/status"],
    });
  },
};
