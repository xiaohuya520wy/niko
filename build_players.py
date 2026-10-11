"""从 Liquipedia 选手页 infobox 提取 Team Falcons 现役阵容资料，并把头像下载到本地。

产出的 players.json 供二级页面（队伍页 / 选手页）使用。
图片来自 Liquipedia（CC-BY-SA 3.0），本页为个人非商业用途使用。
"""
import html as H
import json
import pathlib
import re
import time
import urllib.request

ROOT = pathlib.Path(__file__).parent
CACHE = ROOT / "_cache" / "players"
ASSETS = ROOT / "assets" / "players"
UA = {
    "User-Agent": "NikoTracker/1.0 (CS2 fan page; contact: user@example.com)",
    "Accept-Encoding": "gzip",
}

# Liquipedia 无法用 id.namespace 直接判断，这里按现行阵容固化顺序
SQUAD = [
    ("NiKo", "步枪手", "核心 — 世界上最好的步枪手之一"),
    ("TeSeS", "步枪手", "自由人 — 丹麦老将，稳定输出点"),
    ("m0NESY", "狙击手", "AWP 手 — 世界顶级狙击手"),
    ("kyousuke", "步枪手", "突破手 — 新生代新星"),
    ("karrigan", "指挥", "指挥 — 传奇 IGL，队伍大脑"),
    ("zonic", "教练", "主教练 — 四届 Major 冠军教头"),
]

ROLE_MAP = {
    "AWPer": "狙击手", "Rifler": "步枪手", "Entry": "突破手",
    "Support": "辅助", "Entry Fragger": "突破手", "Lurker": "自由人",
    "In-game leader": "指挥", "IGL": "指挥", "Coach": "教练",
}

# Liquipedia 资料是英文的，展示前统一转成中文
NAT_ZH = {
    "Bosnia and Herzegovina": "波黑", "Denmark": "丹麦", "Russia": "俄罗斯",
    "Serbia": "塞尔维亚", "Croatia": "克罗地亚", "Sweden": "瑞典",
    "Norway": "挪威", "Finland": "芬兰", "France": "法国", "Germany": "德国",
    "Poland": "波兰", "Ukraine": "乌克兰", "Kazakhstan": "哈萨克斯坦",
    "Brazil": "巴西", "Argentina": "阿根廷", "United States": "美国",
    "Canada": "加拿大", "Australia": "澳大利亚", "China": "中国",
    "Korea": "韩国", "Japan": "日本", "Estonia": "爱沙尼亚",
    "Latvia": "拉脱维亚", "Lithuania": "立陶宛", "Czech Republic": "捷克",
    "Slovakia": "斯洛伐克", "Hungary": "匈牙利", "Romania": "罗马尼亚",
    "Bulgaria": "保加利亚", "Turkey": "土耳其", "Israel": "以色列",
    "Netherlands": "荷兰", "Belgium": "比利时", "Spain": "西班牙",
    "Portugal": "葡萄牙", "Italy": "意大利", "United Kingdom": "英国",
    "Austria": "奥地利", "Switzerland": "瑞士", "Mongolia": "蒙古",
}
STATUS_ZH = {"Active": "现役", "Inactive": "暂离赛场", "Retired": "已退役",
             "Banned": "禁赛中"}
MONTH_ZH = {"January": "1 月", "February": "2 月", "March": "3 月",
            "April": "4 月", "May": "5 月", "June": "6 月", "July": "7 月",
            "August": "8 月", "September": "9 月", "October": "10 月",
            "November": "11 月", "December": "12 月"}


def born_zh(s):
    """"February 16, 1997" -> "1997 年 2 月 16 日"。"""
    m = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})$", (s or "").strip())
    if not m:
        return s or ""
    return f"{m.group(3)} 年 {MONTH_ZH.get(m.group(1), m.group(1))} {m.group(2)} 日"


def years_zh(s):
    """"2009 – Present" -> "2009 年至今"。"""
    s = (s or "").strip()
    s = re.sub(r"\s*[–-]\s*Present\s*$", " 年至今", s, flags=re.I)
    s = re.sub(r"^(\d{4})\s*[–-]\s*(\d{4})$", r"\1 年 – \2 年", s)
    s = re.sub(r"^(\d{4})\s*[–-]\s*$", r"\1 年至今", s)
    return s


def zh_info(info):
    """把一条选手资料的英文残留字段转成中文（就地修改并返回）。"""
    info["nationality"] = NAT_ZH.get(info.get("nationality", ""),
                                     info.get("nationality", ""))
    info["status"] = STATUS_ZH.get(info.get("status", ""),
                                   info.get("status", ""))
    info["born"] = born_zh(info.get("born", ""))
    info["years_active"] = years_zh(info.get("years_active", ""))
    return info


def _clean(s):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", s))).strip()


JUNK = {"IMG", "e", "h", "", "|"}


def _infobox_text(h):
    """Flatten the infobox into line-per-value text, preserving order."""
    i = h.find("fo-nttax-infobox-container")
    if i < 0:
        return ""
    seg = h[i:i + 14000]
    seg = re.sub(r"<img[^>]*>", "\n", seg)      # 国籍靠国旗 img 之后的文字
    seg = re.sub(r"<[^>]+>", "\n", seg)
    seg = H.unescape(seg)
    seg = seg.replace("\xa0", " ")              # 不换行空格会让后续正则失配
    lines = [l.strip() for l in seg.split("\n")]
    return "\n".join(l for l in lines if l)


def field(text, label):
    """Value following `Label:` — skips blank lines and image placeholders."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().rstrip(":").lower() == label.lower():
            vals = []
            for nxt in lines[i + 1:i + 6]:
                v = nxt.strip()
                if v in JUNK:
                    continue
                # "(age 21)" 常被 <span> 拆到下一行，合并回主值
                if vals and re.fullmatch(r"\(.*\)", v):
                    vals[-1] = f"{vals[-1]} {v}"
                    continue
                vals.append(v)
                break
            return vals[0] if vals else ""
    return ""


def parse_history(text):
    """战队历史 `start — end` + 队名 组合，只保留干净的近期记录。"""
    out = []
    lines = [l.strip() for l in text.split("\n")]
    for i, line in enumerate(lines):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\s*—\s*(?:(\d{4}-\d{2}-\d{2}))?\s*$", line)
        if not m:
            continue
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if (not nxt or re.match(r"^\d{4}-\d{2}-\d{2}", nxt) or "<" in nxt
                or nxt in JUNK or len(nxt) < 2 or nxt.lower() == "present"):
            continue
        out.append({"from": m.group(1), "to": m.group(2) or "至今", "team": nxt})
    # 去重按队伍合并（同一队多次进出只保留最近一段）
    seen, uniq = set(), []
    for rec in out:
        if rec["team"] in seen:
            for u in uniq:
                if u["team"] == rec["team"]:
                    u["from"] = rec["from"]
                    u["to"] = rec["to"]
            continue
        seen.add(rec["team"])
        uniq.append(rec)
    return uniq[-5:]


def avatar_url(h):
    m = re.search(r'infobox-image-wrapper">.*?<img[^>]+src="([^"]+)"', h, re.S)
    if not m:
        m = re.search(r'infobox-image[^"]*">.*?<img[^>]+src="([^"]+)"', h, re.S)
    if not m:
        return []
    src = m.group(1)
    base = "https://liquipedia.net" + src if src.startswith("/") else src
    cands = [re.sub(r"/\d+px-", "/360px-", base), base]   # 缩略图可能未预生成
    return list(dict.fromkeys(cands))


def download(url, dest, tries=3):
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            r = urllib.request.urlopen(req, timeout=60)
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            dest.write_bytes(raw)
            return len(raw)
        except Exception as e:
            print(f"    retry {t+1}: {type(e).__name__}")
            time.sleep(5)
    return 0


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    result = []
    for pid, role_zh, note in SQUAD:
        fn = CACHE / f"{pid}.html"
        if not fn.exists():
            print(f"skip {pid}: no cache")
            continue
        h = fn.read_text(encoding="utf-8")
        text = _infobox_text(h)
        born = field(text, "Born")
        m = re.search(r"\(age (\d+)\)", born)
        age = int(m.group(1)) if m else None
        role = field(text, "Role")
        info = {
            "id": pid,
            "name": field(text, "Romanized Name") or field(text, "Name"),
            "native_name": field(text, "Name"),
            "nationality": field(text, "Nationality"),
            "born": re.sub(r"\s*\(age \d+\)", "", born),
            "age": age,
            "role": ROLE_MAP.get(role, role),
            "role_raw": role,
            "role_zh": role_zh,
            "note": note,
            "status": field(text, "Status"),
            "years_active": field(text, "Years Active (Player)"),
            "team": field(text, "Team"),
            "winnings": field(text, "Approx. Total Winnings"),
            "nicknames": field(text, "Nickname(s)"),
            "alt_ids": field(text, "Alternate IDs"),
            "history": parse_history(text),
            "url": f"https://liquipedia.net/counterstrike/{pid}",
        }
        info["role"] = info["role"] or role_zh
        avs = avatar_url(h)
        info["photo"] = ""
        for av in avs:
            dest = ASSETS / f"{pid}.jpg"
            size = download(av, dest)
            if size:
                info["photo"] = f"assets/players/{pid}.jpg"
                print(f"{pid:10s} photo {size/1024:.0f}KB")
                break
            print(f"{pid:10s}   ...fallback next url")
            time.sleep(2)
        if not info["photo"]:
            print(f"{pid:10s} photo FAIL")
        time.sleep(2)
        result.append(zh_info(info))

    out = ROOT / "players.json"
    out.write_text(json.dumps({"squad": result}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\nwrote {out} with {len(result)} players")


if __name__ == "__main__":
    main()
