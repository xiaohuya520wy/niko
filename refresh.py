"""One-command refresh: fetch -> parse -> merge -> build -> smoke-check.

    python refresh.py            full refresh (re-fetches pages not yet cached)
    python refresh.py --no-fetch reuse cached pages only
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent
PY = sys.executable

STEPS = [
    ("抓取 Liquipedia 页面", "fetch_all.py"),
    ("解析近一年比赛", "build_history.py"),
    ("提取选手资料与设置", "extract_player.py"),
    ("合并数据", "merge_data.py"),
    ("生成页面", "build.py"),
    ("冒烟检查", "check.py"),
]

no_fetch = "--no-fetch" in sys.argv

for label, script in STEPS:
    print(f"\n=== {label} ({script}) ===", flush=True)
    if no_fetch and script == "fetch_all.py":
        print("  跳过（--no-fetch）")
        continue
    r = subprocess.run([PY, str(ROOT / script)], cwd=ROOT)
    if r.returncode != 0:
        print(f"!! {script} 失败，退出码 {r.returncode}")
        sys.exit(r.returncode)
print("\n全部完成 ->", ROOT / "index.html")

# 同步到干净的发布目录（不含抓取缓存）
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
for f in ["index.html", "manifest.json", "sw.js", "icon.svg", "data.json"]:
    (DIST / f).write_bytes((ROOT / f).read_bytes())
print("已同步发布目录 ->", DIST)
