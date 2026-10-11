#!/usr/bin/env python3
"""Cloudflare Pages 一键部署（直传，不依赖 GitHub）。

用法:
    python cf_deploy.py            # 组装 _cf_dist 并直传到 CF Pages 项目 niko
前置:
    先跑 build.py 确保页面是最新（数据内联在 HTML 里）。
说明:
    - 令牌读 ~/.workbuddy/secrets/cloudflare_token，不写进任何仓库/日志。
    - _cf_dist 以下划线开头，push_api.py 会自动跳过，不会混进 GitHub 提交。
    - 线上地址: https://niko-8u7.pages.dev
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGE = ROOT / "_cf_dist"
ACCOUNT_ID = "aff61d5c116fb8cab7c657535424d0c1"
PROJECT = "niko"
SECRET = Path.home() / ".workbuddy" / "secrets" / "cloudflare_token"

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


def main() -> None:
    if not SECRET.exists():
        sys.exit("[error] 找不到 ~/.workbuddy/secrets/cloudflare_token")
    if not NODE_EXE.exists() or not WRANGLER.exists():
        sys.exit("[error] 托管 Node 或 wrangler 不在预期路径，先 npm install wrangler")
    stage()
    env = os.environ.copy()
    env["CLOUDFLARE_API_TOKEN"] = SECRET.read_text(encoding="utf-8").strip()
    env["CLOUDFLARE_ACCOUNT_ID"] = ACCOUNT_ID
    env["WRANGLER_SEND_METRICS"] = "false"
    r = subprocess.run(
        [str(NODE_EXE), str(WRANGLER), "pages", "deploy", STAGE.name,
         "--project-name", PROJECT, "--branch", "main", "--commit-dirty=true"],
        env=env, cwd=str(ROOT),
    )
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
