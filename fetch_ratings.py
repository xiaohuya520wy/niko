"""NiKo 逐图 rating 回补工具（本地 / GitHub Actions 通用）。

背景：data.json 里 NiKo 每图 Rating 2.1 大量缺失。HLTV（唯一公开数据源）
对数据中心 IP 全线上 Cloudflare 挑战（本机沙箱、GitHub Actions、公共代理
都实测 403），所以本工具设计成「能抓就抓、抓不到就优雅退出」的幂等工具。

2026-10-03 升级（Scrapling 融入 / 方案 B）
----------------------------------------
实测对比同一台机器同一个 HLTV mapstats 链接：
    urllib               -> HTTP 403（Cloudflare Interstitial）
    Scrapling StealthyFetcher -> HTTP 200，486KB 真实页面，含 NiKo 评分行
所以现在优先走 StealthyFetcher，失败自动回退 urllib。
结果写入 ratings.json（仓库内持久保存），pipeline.assemble 每次构建都会合并
——因此「本机跑一次 = 线上永久生效」，不要求 Actions 也能突破 Cloudflare。

用法：
    python fetch_ratings.py            # 尝试回补（网络不通时静默失败）
    python fetch_ratings.py --report   # 只打印覆盖率报告
    python fetch_ratings.py --no-stealth  # 禁用反爬浏览器，只用 urllib
    python fetch_ratings.py --max 30   # 单次最多请求 30 张图（控制耗时）
"""
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CACHE = ROOT / "_cache" / "ratings"
STORE = ROOT / "ratings.json"


def opp_key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load_store():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": []}


def missing_list():
    """data.json 中缺 rating 的（date10, opponent, [mapids]）。"""
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    have = {(e.get("date"), opp_key(e.get("opponent") or ""))
            for e in load_store().get("entries", [])}
    out = []
    for m in data.get("recent_matches", []):
        d10 = m["date"][:10]
        k = opp_key(m["opponent"])
        if any(d10 == a and (k == b or k.startswith(b) or b.startswith(k))
               for a, b in have):
            continue
        maps = (m.get("links") or {}).get("hltv_maps") or []
        ids = []
        for mp in (m.get("maps") or []):
            if not mp.get("vetoed"):
                ids.append(None)
        # hltv_maps 的 game 序号对应非 veto 图的顺序
        game_to_url = {x["game"]: x["url"] for x in maps}
        idx = 0
        urls = []
        for mp in (m.get("maps") or []):
            if mp.get("vetoed"):
                continue
            idx += 1
            urls.append(game_to_url.get(idx))
        out.append({"date": d10, "opponent": m["opponent"], "urls": urls})
    return out


def mapid_from_url(u):
    if not u:
        return None
    q = urllib.parse.urlparse(u).query
    mm = re.search(r"matchid=(\d+)", q)
    if mm:
        return mm.group(1)
    mm = re.search(r"mapstatsid/(\d+)", u)
    return mm.group(1) if mm else None


def stealth_available() -> bool:
    try:
        from scrapling.fetchers import StealthyFetcher   # noqa: F401
        return True
    except Exception:
        return False


def _stealth_get(url: str) -> str:
    """用隐身浏览器突破 Cloudflare，返回 HTML；仍被挑战则抛异常。"""
    from scrapling.fetchers import StealthyFetcher
    r = StealthyFetcher.fetch(
        url,
        headless=True,
        # 关键：主动处理 CF Turnstile / Interstitial。漏了它 = 停在 403；
        # 也绝不能配 disable_resources（会连 CF 的验证 JS 一起屏蔽）。
        solve_cloudflare=True,
        block_images=True,          # 图片不影响表格文本，省带宽即可
        network_idle=True,
        retries=1,
        timeout=90000,
    )
    html = getattr(r, "html_content", "") or ""
    if not html or "Just a moment" in html[:5000]:
        raise RuntimeError("still challenged")
    return html


def plain_fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def fetch(url, use_stealth=True, state=None):
    """优先走反爬浏览器；失败自动回退 urllib。

    state 用于「当天 stealth 走不通就别每次都等浏览器」：连续失败 3 次后
    本次运行直接改用 urllib，避免每次请求都白等几十秒。
    """
    if not use_stealth or not stealth_available():
        return plain_fetch(url)
    if state is not None and state.get("stealth_fail", 0) >= 3:
        return plain_fetch(url)
    return _stealth_get(url)


def parse_niko_row(html):
    """从 mapstats 页抽 NiKo 那一行的 (kd, adr, rating2.1)。"""
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        if not re.search(r">NiKo<", row):
            continue
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) >= 6:
            rating = cells[-1]
            try:
                return {"kd": cells[1], "adr": cells[3], "rating": float(rating)}
            except ValueError:
                return None
    return None


def try_backfill(dry=False, use_stealth=True, max_req=40):
    todo = missing_list()
    total_missing_maps = sum(len([u for u in t["urls"] if u]) for t in todo)
    print(f"缺 rating 的场次：{len(todo)} 场 / 约 {total_missing_maps} 图")
    print(f"抓取方式：{'StealthyFetcher（突破 Cloudflare）' if (use_stealth and stealth_available()) else 'urllib（直连）'}")
    if dry:
        return

    CACHE.mkdir(parents=True, exist_ok=True)
    store = load_store()
    entries = store.setdefault("entries", [])
    got, fail_streak, state = 0, 0, {}
    for t in todo:
        per_map = []
        ok_all = True
        for u in t["urls"]:
            mid = mapid_from_url(u)
            if not u or not mid:
                ok_all = False
                continue
            cf = CACHE / f"{mid}.json"
            if cf.exists():
                per_map.append(json.loads(cf.read_text(encoding="utf-8")))
                continue
            if fail_streak >= 2:
                print("  连续被 CF 挑战，本次停止（下次运行会继续尝试）")
                return
            if got >= max_req:
                print(f"  已达本次上限 {max_req} 图，剩余下次再补")
                return
            try:
                html = fetch(u, use_stealth=use_stealth, state=state)
            except Exception as e:
                state["stealth_fail"] = state.get("stealth_fail", 0) + 1
                print(f"  {u} -> {type(e).__name__}: {e}")
                fail_streak += 1
                ok_all = False
                continue
            if "Just a moment" in html or "challenge" in html[:4000].lower():
                print(f"  mapstatsid={mid} 被 Cloudflare 挑战")
                fail_streak += 1
                ok_all = False
                time.sleep(2)
                continue
            fail_streak = 0
            row = parse_niko_row(html)
            if row:
                cf.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
                per_map.append(row)
                got += 1
                print(f"  {t['date']} vs {t['opponent']} map {mid}: rating {row['rating']}")
            else:
                print(f"  mapstatsid={mid} 未找到 NiKo 行")
                ok_all = False
            time.sleep(2.5)
        if ok_all and per_map:
            entries.append({
                "date": t["date"],
                "opponent": t["opponent"],
                "ratings": [r["rating"] for r in per_map],
                "kd": "/".join(r["kd"] for r in per_map if r.get("kd")) or None,
                "adr": round(sum(float(r["adr"]) for r in per_map
                                 if str(r.get("adr", "")).replace('.', '').isdigit())
                             / max(1, len(per_map)), 1) if per_map else None,
            })
            STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    print(f"本次回补 {got} 图")


def report():
    todo = missing_list()
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    rm = data.get("recent_matches", [])
    have = len(rm) - len(todo)
    print(f"rating 覆盖：{have}/{len(rm)} 场（缺 {len(todo)}）")
    for t in todo[:8]:
        print(f"  - {t['date']} vs {t['opponent']}")


def merge_into_data():
    """把 ratings.json 的评分合并进 data.json（等价于 pipeline.assemble 的评分步骤）。

    幂等、可反复运行，且**只动评分不动比赛数据本身**。
    用途：本机回补完评分后，不用等 Actions 重跑，立刻让页面显示出来。
    """
    import pipeline as PL
    base = json.loads((ROOT / "base.json").read_text(encoding="utf-8"))
    store = PL._load_ratings_store(base)
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    hit = 0
    for m in data.get("recent_matches", []):
        src = PL._match_ratings(store, m["date"][:10], m["opponent"])
        niko = {"ratings": (src or {}).get("ratings", [])}
        for k in ("kd", "adr", "note"):
            if src and src.get(k):
                niko[k] = src[k]
        if niko["ratings"]:
            hit += 1
        m["niko"] = niko
    (ROOT / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    total = len(data.get("recent_matches", []))
    print(f"已合并评分：{hit}/{total} 场（{(hit / total * 100):.0f}%）")


if __name__ == "__main__":
    if "--report" in sys.argv:
        report()
    elif "--merge" in sys.argv:
        merge_into_data()
    else:
        def _num(flag, default):
            return int(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default
        try_backfill(
            dry="--dry" in sys.argv,
            use_stealth="--no-stealth" not in sys.argv,
            max_req=_num("--max", 40),
        )
        report()
