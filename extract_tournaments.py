"""Extract upcoming tournaments from a Liquipedia team page."""
import re
import sys
import html as H

html = H.unescape(open(sys.argv[1], encoding="utf-8").read())
i = html.find("Upcoming Tournaments")
seg = html[i:i + 12000] if i >= 0 else html
for m in re.finditer(r'<div class="tournaments-list-item">(.*?)(?=<div class="tournaments-list-item">|$)',
                     seg, re.S):
    b = m.group(1)
    name = re.search(r'tournaments-list-item__name"><a[^>]*>([^<]+)</a>', b)
    date = re.search(r'tournaments-list-item__date">([^<]+)</a?', b)
    date = re.search(r'tournaments-list-item__date">([^<]*)<', b) if not date else date
    tier = re.search(r'tournament-badge__text">([^<]+)<', b)
    link = re.search(r'href="(/counterstrike/[^"]+)"', b)
    if name:
        print(f"{name.group(1)} | {date.group(1) if date else '?'} | "
              f"{tier.group(1) if tier else '?'} | {link.group(1) if link else '?'}")
