"""Pull NiKo's bio + gear/crosshair settings out of the cached Liquipedia player page."""
import html as H
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
h = H.unescape((ROOT / "_cache" / "events" / "NiKo.html").read_text(encoding="utf-8"))
h = re.sub(r"<img[^>]*>", "", h)
t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))


def g(pat, group=1, default=""):
    m = re.search(pat, t)
    return m.group(group).strip() if m else default


profile = {
    "born": g(r"Born: ([A-Z][a-z]+ \d+, \d{4})"),
    "age": int(g(r"\(age (\d+)\)", 1, "0") or 0),
    "status": g(r"Status: (\w+)"),
    "years_active": (lambda m: f"{m.group(1)} – {m.group(2)}" if m else "")(
        re.search(r"Years Active \(Player\): (\d{4}) – (\w+)", t)),
    "role_liq": g(r"Role: (\w+)"),
    "winnings": g(r"Approx\. Total Winnings: \$([\d,]+)"),
    "mouse": g(r"(Razer DeathAdder V3 Pro) \d+ \d+ \d+ Hz"),
    "edpi": g(r"Razer DeathAdder V3 Pro (\d+) \d+ \d+ Hz"),
    "dpi": g(r"Razer DeathAdder V3 Pro \d+ (\d+) \d+ Hz"),
    "polling": g(r"Razer DeathAdder V3 Pro \d+ \d+ (\d+ Hz)"),
    "sens": g(r"Razer DeathAdder V3 Pro \d+ \d+ \d+ Hz ([\d.]+)"),
    "zoom_sens": g(r"Razer DeathAdder V3 Pro \d+ \d+ \d+ Hz [\d.]+ (\d) "),
    "raw_input": g(r"Razer DeathAdder V3 Pro \d+ \d+ \d+ Hz [\d.]+ \d (On|Off)"),
    "mousepad": g(r"Razer DeathAdder V3 Pro (Razer Gigantus V2 \(Large\))"),
    "monitor": g(r"(ZOWIE [A-Z0-9]+) (\d+ Hz)"),
    "refresh": g(r"ZOWIE [A-Z0-9]+ (\d+ Hz)"),
    "resolution": (lambda mm: f"{mm.group(1)} {mm.group(2)}" if mm else "")(
        re.search(r"(\d+×\d+) (Stretched|Black bars|Native)", t)),
    "keyboard": g(r"Keyboard Headset (.+?) Razer BlackShark"),
    "headset": g(r"(Razer BlackShark V2 Pro)"),
    "crosshair": (lambda mm: {
        "style": mm.group(1), "size": mm.group(2), "thickness": mm.group(3),
        "sniper_width": mm.group(4), "gap": mm.group(5), "outline": mm.group(6),
        "dot": mm.group(7), "color": mm.group(10), "alpha": mm.group(11),
    } if mm else {})(re.search(
        r"Style Size Thickness Sniper Gap Outline Dot Color Alpha "
        r"([\d\-]+) (\d+) (\d+) (\d+) ([\d\-]+) (Yes|No) (Yes|No) "
        r"\( ?(\d) ?\) (\w+) \( ?(\d+) ?\) (\d+)", t)),
    "sharecode": g(r"Sharecode (CSGO-[\w-]+)"),
}

if not profile["mousepad"]:
    profile["mousepad"] = g(r"Mousepad ([A-Z][\w .()]+?) [A-Z][a-z]+ [A-Z]")
if not profile["headset"]:
    profile["headset"] = g(r"(Razer BlackShark V2 Pro)")

(ROOT / "player_profile.json").write_text(
    json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
for k, v in profile.items():
    print(f"{k:12} {v}")
