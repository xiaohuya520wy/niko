"""Extract series + per-map detail from Liquipedia CS2 event pages.

Every bracket popup on an event page carries, for each map of a series:
  - the map name (or the vetoed map, wrapped in <s>)
  - both teams' round counts
  - each team's half split (T side / CT side)
The popup footer carries YouTube VOD links per game, the HLTV match page and
per-game HLTV stat links.
"""
import re

POPUP_START = 'brkts-popup brkts-popup-container brkts-match-info-popup"'


def _strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def split_popups(html):
    """Yield (start, end, chunk) for each bracket popup on the page."""
    idx = [m.start() for m in re.finditer(re.escape(POPUP_START), html)]
    for i, s in enumerate(idx):
        e = idx[i + 1] if i + 1 < len(idx) else len(html)
        yield s, e, html[s:e]


def parse_header(chunk):
    """Team names, series score, BO and timestamp read strictly from inside the popup.

    Reading team names from the HTML *before* a popup picks up whichever series
    happened to render earlier, which silently mislabels matches. The popup itself
    carries everything needed: two opponent blocks around the scoreholder, each
    tagged winner/loser.
    """
    hdr_end = chunk.find("</div></div>", chunk.find("scoreholder-lower"))
    head = chunk[:hdr_end] if hdr_end > 0 else chunk[:4000]

    left_seg = head.split("match-info-header-opponent-left", 1)
    if len(left_seg) < 2:
        return None
    left_seg = left_seg[1]
    left_end = left_seg.find("match-info-header-scoreholder")
    left_blk = left_seg[:left_end] if left_end > 0 else left_seg
    left_win = "match-info-header-winner" in left_blk

    right_blk = head.split("match-info-header-scoreholder", 1)[-1]

    def team(blk):
        m = re.search(r'data-team-name="([^"]+)"', blk)
        if m:
            return m.group(1)
        m = re.search(r'team-template-image-icon[^"]*"[^>]*>\s*<a[^>]+title="([^"]+)"', blk)
        return m.group(1) if m else ""

    left, right = team(left_blk), team(right_blk)
    if not left or not right:
        return None

    # 胜方的 score span 会多挂一个 match-info-header-winner class
    sc = re.findall(r'scoreholder-score[^"]*">(\d+)</span>', head)
    bo = re.search(r'scoreholder-lower">\((Bo\d)', head)
    ts = re.search(r'data-timestamp="(\d+)"', head)
    return {
        "left": left.replace("Team ", ""),
        "right": right.replace("Team ", ""),
        "score": [int(sc[0]), int(sc[1])] if len(sc) >= 2 else [0, 0],
        "bo": bo.group(1) if bo else "",
        "ts": int(ts.group(1)) if ts else None,
        "left_win": left_win,
    }


def parse_map_rows(body):
    """Return a list of maps played in this series."""
    maps_out = []
    # Locate each map block by its row-detail marker and slice by position.
    # (Splitting on the grid-row tag here also matches its own -detail sibling.)
    starts = [m.start() for m in re.finditer("brkts-popup-body-grid-row-detail\">", body)]
    for i, st in enumerate(starts):
        en = starts[i + 1] if i + 1 < len(starts) else len(body)
        blk = body[st:en]
        vetoed = "<s>" in blk
        # the left-opponent result label sits immediately before this row
        pre = body[max(0, st - 250):st]
        labels = re.findall(r'data-label-type="result-(\w+)"', pre)
        left_win = labels[-1] == "win" if labels else None
        mname = re.search(r'title="([^"]+)">([^<]*)</a>', blk)
        if not mname:
            continue
        name = mname.group(1)
        blocks = re.findall(
            r'brkts-popup-body-detailed-scores-container">'
            r'<div class="brkts-popup-body-detailed-scores-main-score">([^<]*)</div>'
            r'<div class="brkts-popup-body-detailed-scores">(.*?)</div></div>',
            blk, re.S)
        if len(blocks) < 2:
            continue
        halves = []
        for main, halves_html in blocks[:2]:
            t = re.search(r'score-color-t">(\d*)</span>', halves_html)
            ct = re.search(r'score-color-ct">(\d*)</span>', halves_html)
            halves.append({
                "rounds": main,
                "t": t.group(1) if t else "",
                "ct": ct.group(1) if ct else "",
            })
        maps_out.append({
            "map": name,
            "vetoed": vetoed,
            "left_win": left_win,
            "left": halves[0],
            "right": halves[1],
        })
    return maps_out


def parse_footer(chunk):
    """VOD links per game, HLTV match page and per-game HLTV stats links."""
    vods = re.findall(
        r'title="Watch Game (\d+)"><a href="([^"]+?)"', chunk)
    hltv_match = re.search(r'hltv\.org/matches/(\d+)/[^"]*"', chunk)
    hltv_maps = re.findall(
        r'hltv\.org/\?pageid=188&amp;matchid=(\d+)" title="Stats on HLTV for Game (\d+)"',
        chunk)
    return {
        "vods": [{"game": int(g), "url": u.replace("&amp;", "&")} for g, u in vods],
        "hltv_match": ("https://www.hltv.org/matches/%s/match" % hltv_match.group(1))
                      if hltv_match else "",
        "hltv_maps": [{"game": int(g), "url": "https://www.hltv.org/?pageid=188&matchid=%s" % i}
                      for i, g in hltv_maps],
    }


def extract(html):
    """Full series list with map-level detail for one event page."""
    out = []
    for start, end, chunk in split_popups(html):
        hdr = parse_header(chunk)
        if not hdr:
            continue
        body = ""
        if "brkts-popup-body" in chunk:
            bi = chunk.find("brkts-popup-body")
            body = chunk[bi:chunk.find("brkts-popup-footer") if "brkts-popup-footer" in chunk
                         else len(chunk)]
        rec = hdr.copy()
        rec["maps"] = parse_map_rows(body)
        rec.update(parse_footer(chunk))
        out.append(rec)
    return out


if __name__ == "__main__":
    import sys
    h = open(sys.argv[1], encoding="utf-8").read()
    rows = extract(h)
    print("total series:", len(rows))
    fal = [r for r in rows if "Falcons" in r["left"] + r["right"]]
    print("falcons series:", len(fal))
    for r in fal[:4]:
        print("-", r["left"], r["score"], r["right"], r["bo"], r["ts"])
        for mp in r["maps"]:
            print(f"    {mp['map']:10s} vetoed={mp['vetoed']} "
                  f"{mp['left']['rounds']} (T{mp['left']['t']}/CT{mp['left']['ct']}) - "
                  f"{mp['right']['rounds']} (T{mp['right']['t']}/CT{mp['right']['ct']})")
        print("    footer:", r["hltv_match"] or "-", "| vods:", len(r["vods"]),
              "| mapstats:", len(r["hltv_maps"]))
