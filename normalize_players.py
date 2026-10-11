"""只用已有的 players.json 跑一遍汉化，不重新下载头像。

build_players.py 联网重抓时会自动调用同样的 zh_info()，所以这个函数是唯一的
汉化来源；本脚本只是给「缓存已经下好、只想改文案」的场景用。
"""
import json
import pathlib

from build_players import SQUAD, zh_info

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "players.json"


def main():
    # 备注是人工撰写的中文，以 build_players.SQUAD 为准，避免重抓时被英文覆盖
    curated = {pid: (role, note) for pid, role, note in SQUAD}
    data = json.loads(SRC.read_text(encoding="utf-8"))
    squad = []
    for p in data.get("squad", []):
        p = zh_info(p)
        if p["id"] in curated:
            p["role"], p["note"] = curated[p["id"]]
        squad.append(p)
    data["squad"] = squad
    SRC.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for p in data["squad"]:
        print(f"{p['id']:10s} {p['nationality']} | {p['born']} | "
              f"{p['status']} | {p['years_active']}")
    print(f"\nwrote {SRC}（{len(data['squad'])} 人）")


if __name__ == "__main__":
    main()
