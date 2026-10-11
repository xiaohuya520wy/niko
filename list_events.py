"""List every tournament row (date, placement, name, url, prize) from a cached team page."""
import html as H
import re
import sys

h = H.unescape(open(sys.argv[1], encoding="utf-8").read())
i = h.find("Achievements")
seg = h[i:i + 60000] if i >= 0 else h
since = sys.argv[2] if len(sys.argv) > 2 else "2025-09-01"

rows, seen = [], set()
for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", seg, re.S):
    r = m.group(1)
    d = re.search(r"<td[^>]*>(\d{4}-\d{2}-\d{2})</td>", r)
    if not d:
        continue
    skip = ("Tournaments", "Counter-Strike", "Category:", "index.php", "Template:")
    links = re.findall(r'href="(/counterstrike/[^"]+)" title="([^"]+)"', r)
    tour = next(((u, t) for u, t in links if not any(s in t for s in skip)), None)
    if not tour:
        continue
    place = re.search(r'placement-text">([^<]+)<', r)
    tds = [re.sub(r"<[^>]+>", "", t).strip() for t in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
    tds = [t for t in tds if t]
    url, name = tour
    if url in seen:
        continue
    seen.add(url)
    rows.append({"date": d.group(1), "place": place.group(1) if place else "",
                 "name": name.split("/")[-1].replace("_", " "), "url": url, "cells": tds})

for r in sorted(rows, key=lambda x: x["date"]):
    if r["date"] < since:
        continue
    print(f"{r['date']} | {r['place']:>4} | {r['name'][:44]:44} | {r['url']} | {' / '.join(r['cells'][-2:])}")
