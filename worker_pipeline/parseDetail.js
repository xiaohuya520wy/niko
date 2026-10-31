// Port of parse_detail.py -> JS (Cloudflare Worker / Node ESM).
// Extracts series + per-map detail from Liquipedia CS2 event pages.
// Pure string/regex logic; no CF-specific APIs, so it runs in Node for tests.

const POPUP_START = 'brkts-popup brkts-popup-container brkts-match-info-popup"';

function stripTags(s) {
  return s.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

// Build a global regex from a literal marker string.
function litGlobal(marker) {
  const esc = marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(esc, "g");
}

export function splitPopups(html) {
  const re = litGlobal(POPUP_START);
  const idx = [];
  let m;
  while ((m = re.exec(html)) !== null) idx.push(m.index);
  const out = [];
  for (let i = 0; i < idx.length; i++) {
    const s = idx[i];
    const e = i + 1 < idx.length ? idx[i + 1] : html.length;
    out.push([s, e, html.slice(s, e)]);
  }
  return out;
}

function parseHeader(chunk) {
  const sl = chunk.indexOf("scoreholder-lower");
  const hdrEnd = sl >= 0 ? chunk.indexOf("</div></div>", sl) : -1;
  const head = hdrEnd > 0 ? chunk.slice(0, hdrEnd) : chunk.slice(0, 4000);

  const leftParts = head.split("match-info-header-opponent-left");
  if (leftParts.length < 2) return null;
  let leftSeg = leftParts[1];
  const le = leftSeg.indexOf("match-info-header-scoreholder");
  if (le > 0) leftSeg = leftSeg.slice(0, le);
  const leftWin = leftSeg.includes("match-info-header-winner");

  const rightBlk = (() => {
    const p = head.split("match-info-header-scoreholder");
    return p[p.length - 1];
  })();

  function team(blk) {
    let m = blk.match(/data-team-name="([^"]+)"/);
    if (m) return m[1];
    m = blk.match(/team-template-image-icon[^"]*"[^>]*>\s*<a[^>]+title="([^"]+)"/);
    return m ? m[1] : "";
  }

  const left = team(leftSeg);
  const right = team(rightBlk);
  if (!left || !right) return null;

  const sc = [...head.matchAll(/scoreholder-score[^"]*">(\d+)<\/span>/g)].map((x) => x[1]);
  const bo = head.match(/scoreholder-lower">\((Bo\d)/);
  const ts = head.match(/data-timestamp="(\d+)"/);
  return {
    left: left.replace(/^Team\s+/, ""),
    right: right.replace(/^Team\s+/, ""),
    score: sc.length >= 2 ? [parseInt(sc[0], 10), parseInt(sc[1], 10)] : [0, 0],
    bo: bo ? bo[1] : "",
    ts: ts ? parseInt(ts[1], 10) : null,
    left_win: leftWin,
  };
}

function parseMapRows(body) {
  const re = litGlobal('brkts-popup-body-grid-row-detail">');
  const starts = [];
  let m;
  while ((m = re.exec(body)) !== null) starts.push(m.index);
  const maps = [];
  for (let i = 0; i < starts.length; i++) {
    const st = starts[i];
    const en = i + 1 < starts.length ? starts[i + 1] : body.length;
    const blk = body.slice(st, en);
    const vetoed = blk.includes("<s>");
    const pre = body.slice(Math.max(0, st - 250), st);
    const labels = [...pre.matchAll(/data-label-type="result-(\w+)"/g)].map((x) => x[1]);
    const left_win = labels.length ? labels[labels.length - 1] === "win" : null;
    const mname = blk.match(/title="([^"]+)">([^<]*)<\/a>/);
    if (!mname) continue;
    const name = mname[1];
    const blocks = [...blk.matchAll(
      /brkts-popup-body-detailed-scores-container">\s*<div class="brkts-popup-body-detailed-scores-main-score">([^<]*)<\/div>\s*<div class="brkts-popup-body-detailed-scores">(.*?)<\/div><\/div>/gs
    )];
    if (blocks.length < 2) continue;
    const halves = [];
    for (const b of blocks.slice(0, 2)) {
      const t = b[2].match(/score-color-t">(\d*)<\/span>/);
      const ct = b[2].match(/score-color-ct">(\d*)<\/span>/);
      halves.push({ rounds: b[1], t: t ? t[1] : "", ct: ct ? ct[1] : "" });
    }
    maps.push({
      map: name,
      vetoed,
      left_win,
      left: halves[0],
      right: halves[1],
    });
  }
  return maps;
}

function parseFooter(chunk) {
  const vods = [...chunk.matchAll(/title="Watch Game (\d+)"><a href="([^"]+?)"/g)]
    .map((x) => ({ game: parseInt(x[1], 10), url: x[2].replace(/&amp;/g, "&") }));
  const hm = chunk.match(/hltv\.org\/matches\/(\d+)\/[^"]*"/);
  const hltvMaps = [...chunk.matchAll(
    /hltv\.org\/\?pageid=188&amp;matchid=(\d+)" title="Stats on HLTV for Game (\d+)"/g
  )].map((x) => ({
    game: parseInt(x[2], 10),
    url: `https://www.hltv.org/?pageid=188&matchid=${x[1]}`,
  }));
  return {
    vods,
    hltv_match: hm ? `https://www.hltv.org/matches/${hm[1]}/match` : "",
    hltv_maps: hltvMaps,
  };
}

export function extract(html) {
  const out = [];
  for (const [, , chunk] of splitPopups(html)) {
    const hdr = parseHeader(chunk);
    if (!hdr) continue;
    let body = "";
    if (chunk.includes("brkts-popup-body")) {
      const bi = chunk.indexOf("brkts-popup-body");
      const fe = chunk.includes("brkts-popup-footer") ? chunk.indexOf("brkts-popup-footer") : chunk.length;
      body = chunk.slice(bi, fe);
    }
    const rec = { ...hdr };
    rec.maps = parseMapRows(body);
    Object.assign(rec, parseFooter(chunk));
    out.push(rec);
  }
  return out;
}

