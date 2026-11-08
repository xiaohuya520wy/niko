#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_hltv_ratings.py —— NiKo 逐图 Rating 抓取器
================================================
架构参考用户提供的 MediaCrawler 项目（真实浏览器 + 代理池）：
  - 用 Playwright 驱动本机 Microsoft Edge（channel="msedge"），
    让浏览器自己跑完 Cloudflare 的 JS 校验、拿到 cf_clearance。
  - 支持通过环境变量 RATING_PROXY 注入住宅代理
    （格式 http://user:pass@host:port，与 MediaCrawler 代理池产出一致）。
  - 解析 HLTV 比赛页里 NiKo 的逐图 Rating 2.1，写回 ratings.json。

为什么必须这么做：
  HLTV 被 Cloudflare 护着，纯 HTTP 客户端（curl / curl_cffi 模拟 TLS）
  一律拿到 "Just a moment..." 校验页；无头浏览器也只能靠「干净 IP」
  或「住宅代理」才能通过。办公室机器出口 IP 已进 Cloudflare 黑名单，
  故本机直接跑会卡在挑战页——需从家里宽带或挂代理运行。

用法：
  # 默认：扫描 data.json 里所有缺评分的已完成比赛，逐个补
  RATING_PROXY=http://user:pass@host:port .venv/Scripts/python.exe fetch_hltv_ratings.py

  # 只补某一场（给 HLTV 比赛页 URL）
  .venv/Scripts/python.exe fetch_hltv_ratings.py --match-url "https://www.hltv.org/matches/2399416/match"

  # 跑完打印诊断信息（不写文件）
  .venv/Scripts/python.exe fetch_hltv_ratings.py --dry-run
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NIKO_ID = 3741  # HLTV 上 NiKo 的 player id
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def log(*a):
    print("[hltv]", *a, flush=True)


def launch_browser(proxy: str | None):
    """启动 Edge，返回 (browser, context)。"""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    args = ["--no-sandbox", "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled"]
    if proxy:
        args.append(f"--proxy-server={proxy}")
    browser = pw.chromium.launch(channel="msedge", headless=True, args=args)
    ctx = browser.new_context(user_agent=UA, locale="en-US",
                              viewport={"width": 1366, "height": 768})
    ctx.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    return pw, browser, ctx


def solve_cf(page, url: str, timeout=60) -> bool:
    """打开页面并等待 Cloudflare 校验自行解开。返回是否拿到真实内容。"""
    page.goto(url, wait_until="load", timeout=45000)
    for _ in range(timeout):
        body = page.content()
        if "Just a moment" not in body and ("NiKo" in body or "Player" in body):
            return True
        time.sleep(1)
    return False


def parse_niko_ratings(page) -> list[float]:
    """
    从已加载的 HLTV 比赛统计页解析 NiKo 的逐图 Rating。
    返回如 [1.17, 1.35, 1.02]；解析失败返回 []。
    策略：定位所有 stats 表 -> 找表头里 Rating 列索引 -> 找 NiKo 行 -> 取该列。
    """
    data = page.evaluate("""() => {
        const out = [];
        // HLTV 每张地图一个 stats 表，class 含 'stats-table'
        const tables = Array.from(document.querySelectorAll('table.stats-table'));
        for (const t of tables) {
            const rows = Array.from(t.querySelectorAll('tr'));
            if (!rows.length) continue;
            // 表头
            const head = Array.from(rows[0].querySelectorAll('th,td')).map(
                c => (c.textContent||'').trim().toLowerCase());
            let rIdx = head.indexOf('rating');
            if (rIdx < 0) {
                // 有些版本 Rating 写成 'rating 2.1'
                rIdx = head.findIndex(h => h.startsWith('rating'));
            }
            if (rIdx < 0) continue;
            // 玩家行
            for (const r of rows.slice(1)) {
                const cells = Array.from(r.querySelectorAll('td'));
                if (cells.length <= rIdx) continue;
                const name = (cells[0].textContent||'').trim();
                if (name.toLowerCase().includes('niko')) {
                    const val = (cells[rIdx].textContent||'').trim();
                    const m = val.match(/[0-9]+\\.[0-9]+/);
                    if (m) out.push(parseFloat(m[0]));
                    break;
                }
            }
        }
        return out;
    }""")
    return data


def load_ratings_store():
    rp = HERE / "ratings.json"
    if rp.exists():
        return json.loads(rp.read_text(encoding="utf-8"))
    return {"updated": "", "entries": []}


def save_ratings_store(store):
    (HERE / "ratings.json").write_text(
        json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_opponent(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def backfill_one(ctx, match_url: str, date10: str, opponent: str) -> list[float]:
    page = ctx.new_page()
    try:
        log(f"抓取 {date10} vs {opponent} -> {match_url}")
        ok = solve_cf(page, match_url)
        if not ok:
            log(f"  ✗ 未过 Cloudflare（IP 被标记？需住宅代理/家里宽带）")
            return []
        ratings = parse_niko_ratings(page)
        log(f"  ✓ 解析到 NiKo 评分: {ratings}")
        return ratings
    except Exception as e:
        log(f"  ✗ 异常: {e!r}")
        return []
    finally:
        page.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match-url", help="只补这一场 HLTV 比赛页 URL")
    ap.add_argument("--dry-run", action="store_true", help="只诊断，不写文件")
    args = ap.parse_args()

    proxy = os.environ.get("RATING_PROXY") or None
    log(f"代理: {proxy or '无（直连，办公室 IP 大概率被 CF 拦）'}")

    pw, browser, ctx = launch_browser(proxy)
    try:
        store = load_ratings_store()
        existing = {(e["date"][:10], normalize_opponent(e.get("opponent", "")))
                    for e in store["entries"]}

        # 收集需要补的比赛
        targets = []
        if args.match_url:
            targets.append(("unknown", "unknown", [args.match_url]))
        else:
            d = json.loads((HERE / "data.json").read_text(encoding="utf-8"))
            for m in d["recent_matches"]:
                if (m.get("niko") or {}).get("ratings"):
                    continue
                if m["score"] in ("0-0", "", None):
                    continue  # 还没打
                links = m.get("links", {}) or {}
                hm = links.get("hltv_maps")
                # hltv_maps 是 list[dict]（[{"game":1,"url":...}, ...]），
                # 旧代码直接把它当 URL 传给 page.goto -> TypeError 被 except 吞掉，
                # 所有缺评分场次静默失败。这里按 game 顺序展开成真正的 URL 列表。
                if hm:
                    urls = [x["url"] for x in sorted(
                        (v for v in hm if isinstance(v, dict) and v.get("url")),
                        key=lambda v: v.get("game") or 0)]
                elif links.get("hltv_match"):
                    urls = [links["hltv_match"]]
                else:
                    urls = []
                if not urls:
                    continue
                key = (m["date"][:10], normalize_opponent(m["opponent"]))
                if key in existing:
                    continue
                targets.append((m["date"][:10], m["opponent"], urls))

        log(f"待补比赛数: {len(targets)}")
        updated = 0
        for date10, opp, urls in targets:
            ratings = []
            for url in urls:
                ratings.extend(backfill_one(ctx, url, date10, opp) or [])
            if ratings and not args.dry_run:
                store["entries"].append({
                    "date": date10, "opponent": opp,
                    "ratings": ratings,
                    "source": "hltv-live",
                })
                updated += 1
        if updated and not args.dry_run:
            store["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            save_ratings_store(store)
            log(f"已写入 {updated} 场到 ratings.json")
            # 接上 git -> KV 桥：本地写入评分后立刻推到 KV，Worker 下一轮 assemble 自动并入
            # data.json / history.json（约 5 分钟内线上可见），不必再手动跑 cf_deploy。
            try:
                sys.path.insert(0, str(HERE))
                import kv_push
                kv_push.push_ratings()
            except Exception as e:  # noqa: BLE001
                log(f"评分已写本地，但推送到 KV 失败：{e}（稍后跑 python kv_push.py 补救）")
        else:
            log("无新增（dry-run 或全被 CF 拦）。")
    finally:
        ctx.close()
        browser.close()
        pw.stop()


if __name__ == "__main__":
    main()
