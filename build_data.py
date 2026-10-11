"""从 _cache/events 的缓存页面生成完整 data.json（含地图详情与阵容），不联网。

用于本机快速迭代；GitHub Actions 上由 run.py 走联网版，产出逻辑完全一致。
"""
import json
import pathlib
import sys

import pipeline

ROOT = pathlib.Path(__file__).parent
CACHE = ROOT / "_cache" / "events"


def main():
    pages = {}
    # 缓存文件名 = 事件页名把 / 换成 _
    for path in pipeline.EVENT_NAMES:
        fn = CACHE / (path.replace("/", "_") + ".html")
        pages[path] = fn.read_text(encoding="utf-8") if fn.exists() else None
    missing = [p for p, h in pages.items() if not h]
    if missing:
        print("缓存缺失（将被跳过）:", missing, file=sys.stderr)

    matches = pipeline.build_matches(pages)
    base = json.loads((ROOT / "base.json").read_text(encoding="utf-8"))
    squad = json.loads((ROOT / "players.json").read_text(encoding="utf-8"))["squad"]
    data = pipeline.assemble(base, matches, squad)

    out = ROOT / "data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    withmaps = sum(1 for m in matches if m["maps"])
    st = data["year_stats"]
    print(f"OK matches={len(matches)} {st['wins']}W-{st['losses']}L "
          f"winrate={st['win_rate']}% events={st['events']}")
    print(f"   有地图详情的比赛: {withmaps}/{len(matches)}")
    print(f"   阵容: {len(data['squad'])} 人")


if __name__ == "__main__":
    main()
