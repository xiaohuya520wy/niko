// Port of fetch_player.py -> JS (pure logic, no FS, no network).
//
// Liquipedia NiKo player infobox -> { winnings, age, born, status,
// years_active, role_liq }.
//
// Same conservative auto-overwrite policy as the Python original: only
// AUTO_KEYS (winnings / age) are written back into base.json. Everything else
// stays hand-maintained, because:
//   * born / status  -- Liquipedia's values are English (February 16, 1997 /
//     Active); overwriting would regress the site's Chinese copy.
//   * career / major / rating_3m -- HLTV data, not present in the infobox.
//   * years_active   -- the online value drops "Present".
// The Worker fetches the page HTML (rate-limited) and passes it in; this module
// only parses, so it stays Node-testable against the Python oracle.

import { htmlUnescape } from "./parseEvent.js";

export const PLAYER_PAGE = "NiKo";
export const AUTO_KEYS = ["winnings", "age"];

// Flatten the infobox into one-value-per-line text (same approach as
// build_players._infobox_text in the Python pipeline).
export function infoboxText(h) {
  const i = (h || "").indexOf("fo-nttax-infobox-container");
  if (i < 0) return "";
  let seg = String(h).slice(i, i + 16000);
  seg = seg.replace(/<img[^>]*>/g, "\n");
  seg = seg.replace(/<[^>]+>/g, "\n");
  // \u00a0 (non-breaking space) breaks the label match, so normalise it first.
  seg = htmlUnescape(seg).replace(/\u00a0/g, " ");
  return seg
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
    .join("\n");
}

// First real value following `Label:` (skipping image placeholders).
export function field(text, label) {
  const lines = String(text || "").split("\n");
  const want = String(label || "").trim().toLowerCase();
  for (let i = 0; i < lines.length; i++) {
    const cur = lines[i].trim().replace(/:$/, "").toLowerCase();
    if (cur !== want) continue;
    for (const nxt of lines.slice(i + 1, i + 6)) {
      const v = nxt.trim();
      if (v && v !== "IMG" && v !== "e" && v !== "h") return v;
    }
    return "";
  }
  return "";
}

// HTML -> profile dict (or null when the infobox is missing).
export function parse(html) {
  const text = infoboxText(html);
  if (!text) return null;
  const born = field(text, "Born");
  const mAge = /\(age (\d+)\)/.exec(born);
  const winningsRaw = field(text, "Approx. Total Winnings");

  const prof = {
    age: mAge ? parseInt(mAge[1], 10) : null,
    born: born.replace(/\s*\(age \d+\)/g, "").trim(),
    status: field(text, "Status"),
    years_active: field(text, "Years Active (Player)"),
    role_liq: field(text, "Role"),
    winnings: null,
  };

  // "$2,011,746" -> 2011746 -> "$2,011,746" (same normalisation as Python)
  const mw = /\$?([\d,]+)/.exec(winningsRaw || "");
  if (mw) {
    const n = parseInt(mw[1].replace(/,/g, ""), 10);
    prof.winnings = Number.isFinite(n) ? "$" + n.toLocaleString("en-US") : null;
  }
  return prof;
}

// In-place update of the auto fields. Returns the list of changed keys
// (empty array == nothing to do, same semantics as Python's bool).
export function refresh(player, prof) {
  if (!player || !prof) return [];
  const changed = [];
  for (const k of AUTO_KEYS) {
    const v = prof[k];
    if (v === null || v === undefined || v === "") continue;
    if (player[k] !== v) {
      player[k] = v;
      changed.push(k);
    }
  }
  return changed;
}
