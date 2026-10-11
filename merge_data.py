"""Merge freshly parsed history + player profile into data.json, preserving HLTV ratings."""
import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).parent

data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
history = json.loads((ROOT / "history.json").read_text(encoding="utf-8"))
profile = json.loads((ROOT / "player_profile.json").read_text(encoding="utf-8"))

# keep the hand-verified HLTV per-series ratings keyed by (date, opponent)
known = {}
for m in data["recent_matches"]:
    known[(m["date"][:10], m["opponent"])] = m.get("niko") or {"ratings": []}

merged = []
for m in history:
    k = (m["date"][:10], m["opponent"])
    m["niko"] = known.get(k, {"ratings": []})
    merged.append(m)

merged.sort(key=lambda x: x["date"], reverse=True)

# drop placeholders that never got a real score
merged = [m for m in merged if m["score"] != "-" and m["result"] in ("W", "L")]

data["recent_matches"] = merged

w = sum(1 for m in merged if m["result"] == "W")
l = len(merged) - w
data["year_stats"] = {
    "span": "近一年",
    "from": merged[-1]["date"][:10] if merged else "",
    "to": merged[0]["date"][:10] if merged else "",
    "matches": len(merged),
    "wins": w,
    "losses": l,
    "win_rate": round(w / len(merged) * 100, 1) if merged else 0,
    "events": len(Counter(m["event"] for m in merged)),
}

data["player"].update({
    "born": profile["born"],
    "age": profile["age"],
    "years_active": profile["years_active"],
    "status": profile["status"],
    "winnings": "$" + profile["winnings"],
    "role_liq": profile["role_liq"],
    "gear": {
        "mouse": profile["mouse"],
        "mousepad": profile["mousepad"],
        "edpi": profile["edpi"],
        "dpi": profile["dpi"],
        "sens": profile["sens"],
        "polling": profile["polling"],
        "zoom_sens": profile["zoom_sens"],
        "raw_input": profile["raw_input"],
        "monitor": profile["monitor"],
        "refresh": profile["refresh"],
        "resolution": profile["resolution"],
        "keyboard": profile["keyboard"],
        "headset": profile["headset"],
    },
    "crosshair": profile["crosshair"],
    "crosshair_sharecode": profile["sharecode"],
})

(ROOT / "data.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"merged {len(merged)} matches  {w}W-{l}L  "
      f"winrate {data['year_stats']['win_rate']}%  events {data['year_stats']['events']}")
print("span", data["year_stats"]["from"], "->", data["year_stats"]["to"])
print("with ratings:", sum(1 for m in merged if m["niko"].get("ratings")))
