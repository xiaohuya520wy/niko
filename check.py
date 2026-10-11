"""Smoke-check the generated page: JSON block, JS syntax, DOM id wiring."""
import json
import re
import subprocess
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
html = (ROOT / "index.html").read_text(encoding="utf-8")
node = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-2\node.exe"
ok = True

# 1. embedded data block parses
m = re.search(r'<script id="niko-data" type="application/json">(.*?)</script>', html, re.S)
data = json.loads(m.group(1))
print("[ok] data block parses:", len(data["recent_matches"]), "matches,",
      len(data["upcoming_tournaments"]), "upcoming")

# 2. JS syntax
scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
tmp = ROOT / "_tmp_check.js"
tmp.write_text(scripts[-1], encoding="utf-8")
r = subprocess.run([node, "--check", str(tmp)], capture_output=True, text=True)
print("[ok] js syntax" if r.returncode == 0 else "[FAIL] js syntax")
if r.returncode:
    ok = False
    print(r.stderr[:800])
tmp.unlink(missing_ok=True)

# 3. every getElementById target exists in the markup
ids_html = set(re.findall(r'id="([^"]+)"', html))
ids_js = set(re.findall(r"getElementById\('([^']+)'\)", html))
missing = ids_js - ids_html
print("[ok] dom ids" if not missing else f"[FAIL] missing ids: {missing}")
if missing:
    ok = False

# 4. data completeness
for i, mt in enumerate(data["recent_matches"]):
    for k in ("date", "opponent", "score", "result", "event"):
        if k not in mt or mt[k] in (None, ""):
            print(f"[FAIL] match {i} missing {k}")
            ok = False
    if mt["result"] not in ("W", "L"):
        print(f"[FAIL] match {i} bad result {mt['result']}")
        ok = False
    if mt["score"].count("-") != 1:
        print(f"[FAIL] match {i} bad score {mt['score']}")
        ok = False
print("[ok] match fields" if ok else "[FAIL] match fields")

# 5. sanity: ratings within plausible range
for mt in data["recent_matches"]:
    for r_ in (mt.get("niko") or {}).get("ratings", []):
        if not (0.2 <= r_ <= 3.0):
            print(f"[WARN] odd rating {r_} in {mt['opponent']}")

sys.exit(0 if ok else 1)
