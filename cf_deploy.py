#!/usr/bin/env python3
"""Cloudflare Pages 一键部署（直传，不依赖 GitHub）。

用法:
    python cf_deploy.py            # 组装 _cf_dist 并直传到 CF Pages 项目 niko，随后把数据种子写入 KV
前置:
    先跑 build.py 确保页面是最新（数据内联在 HTML 里）。
说明:
    - 令牌读 ~/.workbuddy/secrets/cloudflare_token，不写进任何仓库/日志。
    - _cf_dist 以下划线开头，push_api.py 会自动跳过，不会混进 GitHub 提交。
    - 部署完成后只在 KV 缺失时种入 JSON 数据（namespace: NikoData），
      这样 Pages Function (/gh/<file>) 与 niko-scheduler Worker 立刻有数据可用，
      不必等 Worker 冷启动的首次全量抓取；已存在的 key 绝不覆盖，
      避免用本地旧快照回滚线上较新数据。主动同步请用 kv_push.py。
    - 线上地址: https://niko-8u7.pages.dev
"""
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGE = ROOT / "_cf_dist"
ACCOUNT_ID = "aff61d5c116fb8cab7c657535424d0c1"
PROJECT = "niko"
SECRET = Path.home() / ".workbuddy" / "secrets" / "cloudflare_token"
KV_NS = "81c9b09644de4ed7bba0c8aca5ded478"  # NikoData

WRANGLER = Path(r"C:\Users\Administrator\.workbuddy\binaries\node\workspace\node_modules\wrangler\bin\wrangler.js")


def _find_node() -> Path:
    """定位托管 node 可执行文件。

    不要写死版本号：WorkBuddy 升级后 node 从 22.22.2-3 变成 22.22.2-6，
    写死会让部署直接报「node 不在预期路径」（2026-10-08 踩过）。
    优先 current，其次 versions/ 下版本号最大的一个。
    """
    base = Path(r"C:\Users\Administrator\.workbuddy\binaries\node")
    cands = []
    cur = base / "current" / "node.exe"
    if cur.exists():
        cands.append(cur)
    vdir = base / "versions"
    if vdir.is_dir():
        for d in sorted(vdir.iterdir(), reverse=True):
            exe = d / "node.exe"
            if exe.exists():
                cands.append(exe)
    return cands[0] if cands else base / "versions" / "node.exe"


NODE_EXE = _find_node()

# 前端运行时真正需要的文件（构建产物 + 数据 + 静态资源）
PAGES = ["index.html", "event.html", "match.html", "team.html", "player.html",
         "icon.svg", "manifest.json"]
JSONS = ["data.json", "event.json", "photos.json", "history.json",
         "players.json", "player_profile.json"]
ASSET_DIRS = ["maps", "photos", "players", "teams", "pixel"]  # 不含 _src（开发用原图）


def stage() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir()
    for name in PAGES + JSONS:
        src = ROOT / name
        if not src.exists():
            print(f"[warn] 缺少 {name}，跳过（先跑 build.py？）")
            continue
        shutil.copy2(src, STAGE / name)
    (STAGE / "assets").mkdir(exist_ok=True)
    for d in ASSET_DIRS:
        src = ROOT / "assets" / d
        if src.exists():
            shutil.copytree(src, STAGE / "assets" / d)
    # Pages Functions：把 functions/ 原样打进 _cf_dist，wrangler pages deploy 才会作为
    # 边缘函数发布。它们提供 /gh/<file> 实时代理（国内可达，绕开 jsDelivr 12h 缓存 +
    # Pages 静态快照不自动更新），是「高频刷新」的前端数据源。
    fns = ROOT / "functions"
    if fns.exists():
        shutil.copytree(fns, STAGE / "functions")
        print("[stage] 已包含 Pages Functions (/gh/<file>)")
    n = sum(1 for _ in STAGE.rglob("*") if _.is_file())
    print(f"[stage] _cf_dist 就绪：{n} 个文件")


def kv_has(token: str, name: str) -> bool:
    """KV 里是否已有该 key。探测异常时保守返回 True（宁可跳过也不要覆盖）。"""
    url = (f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}"
           f"/storage/kv/namespaces/{KV_NS}/values/{name}")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        return e.code != 404
    except Exception:  # noqa: BLE001
        return True


def seed_kv(token: str) -> None:
    """冷启动种子：只在 KV 缺失时写入，避免用本地旧快照回滚线上较新数据。

    历史坑：本函数原先无条件 PUT 全部 8 个 JSON。本地 data.json / event.json 是
    build.py 时刻的快照（例如 10-29），而 KV 里是 Worker 每 5 分钟 assemble 的较新值；
    一次 Pages 部署就会把 /gh/*.json 回退到旧快照，ratings.json 甚至会把
    kv_push / Worker backfill 累积的新评分库整体回滚。
    需要主动同步本地数据时请显式跑 `python kv_push.py --file <name> --key <name>`。
    """
    seeds = [
        "base.json", "players.json",
        "data.json", "event.json", "photos.json", "history.json",
        "player_profile.json", "ratings.json",
    ]
    ok = skipped = 0
    for name in seeds:
        p = ROOT / name
        if not p.exists():
            print(f"[seed] 跳过缺失文件 {name}")
            continue
        if kv_has(token, name):
            print(f"[seed] {name} -> KV 已存在，跳过（避免回滚线上较新数据）")
            skipped += 1
            continue
        url = (f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}"
               f"/storage/kv/namespaces/{KV_NS}/values/{name}")
        req = urllib.request.Request(
            url, data=p.read_bytes(), method="PUT",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                print(f"[seed] {name} -> HTTP {resp.status}")
                ok += 1
        except urllib.error.HTTPError as e:
            print(f"[seed] {name} 失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
        except Exception as e:  # noqa: BLE001
            print(f"[seed] {name} 失败: {e}")
    print(f"[seed] 完成：新写入 {ok} / 跳过 {skipped} / 共 {len(seeds)}")


def main() -> None:
    if not SECRET.exists():
        sys.exit("[error] 找不到 ~/.workbuddy/secrets/cloudflare_token")
    if not NODE_EXE.exists() or not WRANGLER.exists():
        sys.exit("[error] 托管 Node 或 wrangler 不在预期路径，先 npm install wrangler")
    stage()
    token = SECRET.read_text(encoding="utf-8").strip()
    env = os.environ.copy()
    env["CLOUDFLARE_API_TOKEN"] = token
    env["CLOUDFLARE_ACCOUNT_ID"] = ACCOUNT_ID
    env["WRANGLER_SEND_METRICS"] = "false"
    r = subprocess.run(
        [str(NODE_EXE), str(WRANGLER), "pages", "deploy", STAGE.name,
         "--project-name", PROJECT, "--branch", "main", "--commit-dirty=true"],
        env=env, cwd=str(ROOT),
    )
    if r.returncode != 0:
        sys.exit(r.returncode)
    # 部署成功后写 KV 种子（幂等，可重复跑）
    print("[deploy] Pages 部署完成，开始写入 KV 种子…")
    try:
        seed_kv(token)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] KV 种子写入异常：{e}（Worker 会在数分钟内补抓，站点稍后自愈）")
    sys.exit(0)


if __name__ == "__main__":
    main()
