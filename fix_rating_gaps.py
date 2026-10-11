"""逐图补洞：把 data.json 里「某场只抓到部分地图评分」的空缺补上。

背景
----
fetch_ratings.py 的 try_backfill 只处理「整场都没评分」的比赛，遇到部分地图
抓取失败的场次就不再重试了（missing_list 会把它们当成已完成直接跳过）。
结果是 ratings.json 里躺着几条半截数据，例如 MOUZ 那场打了 3 张图却只存了
1 个评分 [0.38]，页面上就少两块评分。

本脚本反过来做：找出评分数与实打图数对不上的比赛，**整场重新抓一遍**
（而不是只抓缺的那张），这样评分数组与地图顺序严格对齐，不会错位。

用法（需要能跑 StealthyFetcher 的那个 Python 环境）：
    <default 环境>/Scripts/python.exe fix_rating_gaps.py            # 补齐并合并
    <default 环境>/Scripts/python.exe fix_rating_gaps.py --dry      # 只看缺什么
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

import fetch_ratings as FR  # noqa: E402  复用它的抓取/解析/告警实现

def opp_key(s: str) -> str:
    """对手名归一化，和 pipeline._opp_key 保持一致。"""
    fn = getattr(FR, "opp_key", None)
    if fn:
        return fn(s or "")
    import re
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def played_maps(m: dict) -> list[dict]:
    return [x for x in (m.get("maps") or []) if not x.get("vetoed")]


def plan() -> list[dict]:
    """列出所有评分数 < 实打图数的比赛，带上每张图的 HLTV 链接。"""
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    out = []
    for m in data.get("recent_matches", []):
        played = played_maps(m)
        if not played:
            continue
        rs = ((m.get("niko") or {}).get("ratings")) or []
        if len(rs) >= len(played):
            continue
        links = (m.get("links") or {}).get("hltv_maps") or []
        game_to_url = {x.get("game"): x.get("url") for x in links}
        urls = [game_to_url.get(i + 1) for i in range(len(played))]
        out.append({
            "date": m["date"][:10],
            "opponent": m["opponent"],
            "maps": played,
            "urls": urls,
            "have": rs,
        })
    return out


def main() -> int:
    dry = "--dry" in sys.argv
    todo = plan()
    if not todo:
        print("没有发现评分空缺的比赛。")
        return 0

    print(f"=== 需要补齐 {len(todo)} 场比赛的评分 ===")
    for t in todo:
        playable = sum(1 for u in t["urls"] if u)
        print(f"  {t['date']} vs {t['opponent']}: "
              f"实打 {len(t['maps'])} 图，现存 {len(t['have'])} 个评分，"
              f"其中可抓取链接 {playable} 张")
    if dry:
        return 0

    stealth_ok = FR.stealth_available()
    print(f"\n抓取方式：{'StealthyFetcher' if stealth_ok else 'urllib（直连，多半会被 CF 挡）'}")

    store = FR.load_store()
    entries = store.setdefault("entries", [])
    state, fail_streak, got = {}, 0, 0

    for t in todo:
        per_map = []
        for i, u in enumerate(t["urls"]):
            mid = FR.mapid_from_url(u) if u else None
            label = f"{t['date']} vs {t['opponent']} 图{i+1}"
            if not u or not mid:
                per_map.append(None)
                print(f"  {label}: 无 HLTV 链接，跳过")
                continue
            cf = FR.CACHE / f"{mid}.json"
            if cf.exists():
                per_map.append(json.loads(cf.read_text(encoding="utf-8")))
                continue
            if fail_streak >= 2:
                print("  连续被 CF 挑战，停止（下次再跑会继续）")
                per_map.append(None)
                continue
            try:
                html = FR.fetch(u, use_stealth=True, state=state)
            except Exception as e:
                FR_state = state
                FR_state["stealth_fail"] = FR_state.get("stealth_fail", 0) + 1
                print(f"  {label}: {type(e).__name__}: {e}")
                fail_streak += 1
                per_map.append(None)
                continue
            if "Just a moment" in html or "challenge" in html[:4000].lower():
                print(f"  {label}: 被 Cloudflare 挑战")
                fail_streak += 1
                per_map.append(None)
                time.sleep(2)
                continue
            fail_streak = 0
            row = FR.parse_niko_row(html)
            if row:
                cf.parent.mkdir(parents=True, exist_ok=True)
                cf.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
                per_map.append(row)
                got += 1
                print(f"  {label}: rating {row['rating']}")
            else:
                print(f"  {label}: 未找到 NiKo 行")
                per_map.append(None)
            time.sleep(2.5)

        ratings = [r["rating"] if r else None for r in per_map]
        # 之前已经有的评分不要丢：优先用这次抓到的，抓不到的沿用旧值
        for i in range(min(len(ratings), len(t["have"]))):
            if ratings[i] is None and t["have"][i] is not None:
                ratings[i] = t["have"][i]
        if not any(r is not None for r in ratings):
            print(f"  -> {t['date']} vs {t['opponent']} 一张都没抓到，暂不落库")
            continue

        key = opp_key(t["opponent"])
        ent = None
        for e in entries:
            if e.get("date") == t["date"] and opp_key(e.get("opponent") or "") == key:
                ent = e
                break
        if ent is None:
            ent = {"date": t["date"], "opponent": t["opponent"]}
            entries.append(ent)
        ent["ratings"] = ratings
        rows = [r for r in per_map if r]
        if rows:
            ent["kd"] = "/".join(r["kd"] for r in rows if r.get("kd")) or ent.get("kd")
            adrs = [float(r["adr"]) for r in rows
                    if str(r.get("adr", "")).replace(".", "").isdigit()]
            if adrs:
                ent["adr"] = round(sum(adrs) / len(adrs), 1)
        FR.STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        print(f"  -> 已更新 {t['date']} vs {t['opponent']}: {ratings}")

    print(f"\n本次补到 {got} 张图的评分")
    FR.merge_into_data()
    return 0


if __name__ == "__main__":
    sys.exit(main())
