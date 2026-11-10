#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把仓库里的 JSON 数据推送到 Cloudflare KV（NikoData），打通 git -> KV 评分通道。

为什么需要它
------------
评分的唯一权威源是 HLTV，而 HLTV 对所有数据中心/Worker 出口做 Cloudflare 挑战
（直连 403）。所以评分只能由本机（家里宽带 / 住宅代理）运行的
fetch_ratings.py / fetch_hltv_ratings.py 抓回，写进仓库里的 ratings.json。
但线上站点只读 KV（由 niko-scheduler Worker 每 5 分钟 assemble）。
此前 ratings.json 只会通过 cf_deploy.py 全量部署时被动种进 KV —— 也就是说
「本地回补了评分」≠「线上立刻显示」，必须手动重跑部署。

本脚本把这道桥接上：评分脚本写完 ratings.json 后顺手 PUT 到 KV，
Worker 下一轮 assemble 自动把新评分并入 data.json / history.json（约 5 分钟内生效）。

用法
----
    python kv_push.py                  # 推送 ratings.json -> KV key "ratings.json"
    python kv_push.py --check          # 只比较本地与 KV 差异，不写入
    python kv_push.py --file photos.json --key photos.json   # 更新线上照片墙
    python kv_push.py --file foo.json --key bar.json   # 推送任意 JSON 到指定 KV key

令牌优先级：环境变量 CLOUDFLARE_API_TOKEN -> ~/.workbuddy/secrets/cloudflare_token
缺少令牌时跳过（打印警告，不报错退出），保证评分抓取流程不被打断。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ACCOUNT_ID = "aff61d5c116fb8cab7c657535424d0c1"
KV_NS = "81c9b09644de4ed7bba0c8aca5ded478"  # NikoData
ROOT = Path(__file__).resolve().parent
SECRET = Path.home() / ".workbuddy" / "secrets" / "cloudflare_token"


def get_token() -> str | None:
    t = os.environ.get("CLOUDFLARE_API_TOKEN")
    if t:
        return t.strip()
    if SECRET.exists():
        return SECRET.read_text(encoding="utf-8").strip()
    return None


def kv_get(key: str, token: str) -> str:
    url = (f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}"
           f"/storage/kv/namespaces/{KV_NS}/values/{key}")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return f"__HTTPERR__{e.code}"


def kv_put(key: str, text: str, token: str):
    url = (f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}"
           f"/storage/kv/namespaces/{KV_NS}/values/{key}")
    req = urllib.request.Request(
        url, data=text.encode("utf-8"), method="PUT",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        # 免费 KV 写操作每天仅 1000 次，常被 Worker 常规写入吃光 -> 429/10048。
        # 返回哨兵而非抛栈，让调用方给出友好提示、下次运行/明天 UTC 0 点后自动重试。
        if e.code == 429:
            return "QUOTA"
        raise


def push(path: Path, key: str, token: str, check_only: bool = False) -> bool:
    if not path.exists():
        print(f"[kv] 跳过缺失文件 {path}")
        return False
    local = path.read_text(encoding="utf-8")
    if check_only:
        remote = kv_get(key, token)
        if remote.startswith("__HTTPERR__"):
            print(f"[kv] KV {key}: {remote}（远端缺失或不可达）")
            return False
        try:
            same = json.loads(local) == json.loads(remote)
        except Exception:
            same = False
        print(f"[kv] {key}: 本地==KV ? {same}")
        return same
    status = kv_put(key, local, token)
    if status == "QUOTA":
        print(f"[kv] {key}: 今日 KV 写额度已耗尽（免费 1000 次/日，被 Worker 常规写入占用），"
              f"本次推送延后到明天 UTC 0 点后生效（下次重跑 kv_push 会重试）")
        return False
    print(f"[kv] {key} -> HTTP {status}")
    return status == 200


def push_ratings(check_only: bool = False) -> bool:
    """便捷封装：推送仓库里的 ratings.json 到 KV。无令牌则优雅跳过。"""
    token = get_token()
    if not token:
        print("[kv] 未找到 CLOUDFLARE_API_TOKEN，跳过 KV 推送"
              "（评分已写入本地 git，稍后手动同步即可）")
        return False
    return push(ROOT / "ratings.json", "ratings.json", token, check_only=check_only)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="ratings.json",
                    help="要推送的本地 JSON 文件（默认 ratings.json）")
    ap.add_argument("--key", default=None,
                    help="目标 KV key，默认与 --file 同名")
    ap.add_argument("--check", action="store_true",
                    help="只比较本地与 KV 差异，不写入")
    args = ap.parse_args()
    token = get_token()
    if not token:
        print("[kv] 未找到 CLOUDFLARE_API_TOKEN，跳过 KV 推送")
        sys.exit(0)
    key = args.key or args.file
    ok = push(ROOT / args.file, key, token, check_only=args.check)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
