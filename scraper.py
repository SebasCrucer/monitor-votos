#!/usr/bin/env python3
"""Escrapea los votos del Platanus Hack 26-MX y apendea a docs/history.json."""
import json, re, time, os, urllib.request

BASE = "https://hack.platan.us/26-mx/vote"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "docs", "history.json")
UA = {"User-Agent": "Mozilla/5.0 (vote-monitor)"}

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")

def main():
    html = fetch(BASE)
    slugs = sorted(set(re.findall(r'/26-mx/vote/([a-z0-9-]+)', html)))
    slugs = [s for s in slugs if not s.startswith("opengraph")]

    counts, names = {}, {}
    for s in slugs:
        try:
            page = fetch(f"{BASE}/{s}")
            m = re.search(r'\\"initialCount\\":(\d+)', page) or re.search(r'"initialCount":(\d+)', page)
            if m:
                counts[s] = int(m.group(1))
            nm = re.search(r'\\"projectSlug\\":\\"%s\\",\\"projectName\\":\\"(.*?)\\"' % re.escape(s), page)
            names[s] = nm.group(1) if nm else s
        except Exception as e:
            print(f"warn: {s}: {e}")

    if not counts:
        raise SystemExit("no se obtuvo ningún conteo — abortando sin escribir")

    data = {"snapshots": [], "names": {}}
    if os.path.exists(OUT):
        with open(OUT) as f:
            data = json.load(f)

    data["snapshots"].append({"t": int(time.time()), "counts": counts})
    data["names"].update(names)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"ok: {len(counts)} proyectos, {len(data['snapshots'])} snapshots")

if __name__ == "__main__":
    main()
