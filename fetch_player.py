"""从 Liquipedia 选手页实时抓取 NiKo 的生涯基础信息（奖金 / 年龄 / 状态等）。

接进 run.py 自动流水线，替代 base.json 里手写、会过期的静态值。

只抓 Liquipedia 球员 infobox 里**确实有的**字段：
    winnings（生涯总奖金）、age（年龄）、born（出生日期）、
    status（现役/退役）、years_active（活跃年份）、role_liq（位置）。

HLTV 的 career（生涯击杀/KD/ADR）、Major 冠军、近三月 rating 不在
infobox 里，保持 base.json 手动维护，不在此覆盖。

抓取失败（限流 / 离线）时返回 None，调用方保留旧值、不报错、不覆盖。
"""
import datetime as dt
import gzip
import html as H
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent
CACHE = ROOT / "_cache" / "events"
CACHE.mkdir(parents=True, exist_ok=True)
UA = {
    "User-Agent": "NikoTracker/1.0 (CS2 fan page; contact: user@example.com)",
    "Accept-Encoding": "gzip",
}
API = "https://liquipedia.net/counterstrike/api.php?"
PLAYER_PAGE = "NiKo"

# 只自动覆盖这两个字段——都是 Liquipedia 球员 infobox 里确实有、且会过期、
# 且格式稳定不会回退的：
#   · winnings（生涯奖金）：随赛事奖金增长，base 手写值会过期（实测已从
#     2,011,746 → 2,013,746）；
#   · age（年龄）：逐年变化，int 格式稳定。
# 其余字段保留 base.json 手写值，原因是：
#   · born / status：Liquipedia 在线是英文（February 16, 1997 / Active），
#     覆盖会把站点上已调好的中文（1997 年 2 月 16 日 / 现役）回退成英文；
#   · career / major / rating_3m：属 HLTV 数据，infobox 里没有；
#   · years_active：在线解析会丢「Present」；role_liq：站点未展示且在线值不一致。
AUTO_KEYS = ("winnings", "age")


def _fetch(page, tries=4):
    """抓一个 Liquipedia 页面渲染后的 HTML（与 run.py 同款重试 + 限流退避）。"""
    url = API + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json"})
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            r = urllib.request.urlopen(req, timeout=90)
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8"))["parse"]["text"]["*"]
        except Exception as e:                      # noqa: BLE001
            last = e
            time.sleep(10)
    print(f"  [player] 抓取 {page} 失败：{type(last).__name__}: {last}",
          file=sys.stderr)
    return None


def _infobox_text(h):
    """把 infobox 拍平成逐行文本（与 build_players._infobox_text 同思路）。"""
    i = h.find("fo-nttax-infobox-container")
    if i < 0:
        return ""
    seg = h[i:i + 16000]
    seg = re.sub(r"<img[^>]*>", "\n", seg)
    seg = re.sub(r"<[^>]+>", "\n", seg)
    seg = H.unescape(seg).replace("\xa0", " ")     # 不换行空格会让正则失配
    return "\n".join(l.strip() for l in seg.split("\n") if l.strip())


def _field(text, label):
    """取 `Label:` 之后的第一个有效值（跳过 IMG/e/h 等图片占位）。"""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().rstrip(":").lower() == label.lower():
            for nxt in lines[i + 1:i + 6]:
                v = nxt.strip()
                if v and v not in {"IMG", "e", "h", ""}:
                    return v
            return ""
    return ""


def _parse(html):
    text = _infobox_text(html)
    if not text:
        return None
    born = _field(text, "Born")
    m_age = re.search(r"\(age (\d+)\)", born)
    winnings_raw = _field(text, "Approx. Total Winnings")
    prof = {
        "age": int(m_age.group(1)) if m_age else None,
        "born": re.sub(r"\s*\(age \d+\)", "", born).strip(),
        "status": _field(text, "Status"),
        "years_active": _field(text, "Years Active (Player)"),
        "role_liq": _field(text, "Role"),
    }
    # 归一化奖金："$2,011,746" -> 整数 -> "$2,011,746"
    mw = re.search(r"\$?([\d,]+)", winnings_raw or "")
    if mw:
        try:
            prof["winnings"] = "${:,}".format(int(mw.group(1).replace(",", "")))
        except ValueError:
            prof["winnings"] = None
    else:
        prof["winnings"] = None
    return prof


def fetch_profile(allow_net=True):
    """返回 {winnings, age, born, status, years_active, role_liq} 或 None。"""
    html = _fetch(PLAYER_PAGE) if allow_net else None
    if not html:
        c = CACHE / f"{PLAYER_PAGE}.html"           # 退回本机缓存
        if c.exists():
            html = c.read_text(encoding="utf-8")
    if not html:
        return None
    # 顺手缓存，供 extract_player.py 这类手动脚本使用
    (CACHE / f"{PLAYER_PAGE}.html").write_text(html, encoding="utf-8")
    return _parse(html)


def refresh(player, allow_net=True):
    """就地更新 player 字典里的自动字段；失败则原样返回。返回是否有变更。"""
    prof = fetch_profile(allow_net=allow_net)
    if not prof:
        print("  [player] 未拿到在线数据，保留 base.json 旧值")
        return False
    changed = []
    for k in AUTO_KEYS:
        v = prof.get(k)
        if v in (None, ""):
            continue
        if player.get(k) != v:
            player[k] = v
            changed.append(k)
    if changed:
        print(f"  [player] 自动刷新：{', '.join(changed)}")
    else:
        print("  [player] 在线数据与 base 一致，无需更新")
    return bool(changed)


if __name__ == "__main__":
    p = fetch_profile()
    print(json.dumps(p, ensure_ascii=False, indent=2))
