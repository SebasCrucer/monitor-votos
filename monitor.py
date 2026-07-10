#!/usr/bin/env python3
"""Monitor de votos — Platanus Hack 26-MX.

Sondea https://hack.platan.us/26-mx/vote cada POLL_SECONDS, extrae el conteo
de votos embebido en cada página de proyecto ("initialCount":N), guarda el
histórico en history.jsonl y sirve un dashboard en http://localhost:8477.
"""
import json, re, threading, time, urllib.request, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = "https://hack.platan.us/26-mx/vote"
POLL_SECONDS = 60
PORT = 8477
HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.join(HERE, "history.jsonl")
MY_PROJECT = "ikarus"

UA = {"User-Agent": "Mozilla/5.0 (vote-monitor)"}

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def discover_slugs():
    html = fetch(BASE)
    slugs = sorted(set(re.findall(r'/26-mx/vote/([a-z0-9-]+)', html)))
    return [s for s in slugs if not s.startswith("opengraph")]

def scrape_project(slug):
    html = fetch(f"{BASE}/{slug}")
    m = re.search(r'\\"initialCount\\":(\d+)', html) or re.search(r'"initialCount":(\d+)', html)
    name = slug
    nm = re.search(r'\\"projectSlug\\":\\"%s\\",\\"projectName\\":\\"(.*?)\\"' % re.escape(slug), html)
    if nm:
        name = nm.group(1)
    return name, (int(m.group(1)) if m else None)

state = {"snapshots": [], "names": {}, "last_error": None}
lock = threading.Lock()

def load_history():
    if not os.path.exists(HISTORY):
        return
    with open(HISTORY) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    snap = json.loads(line)
                    state["snapshots"].append(snap)
                    state["names"].update(snap.get("names", {}))
                except json.JSONDecodeError:
                    pass

def poll_loop():
    slugs = None
    while True:
        try:
            if slugs is None:
                slugs = discover_slugs()
            counts, names = {}, {}
            for s in slugs:
                try:
                    name, c = scrape_project(s)
                    if c is not None:
                        counts[s] = c
                        names[s] = name
                except Exception:
                    pass
            if counts:
                snap = {"t": int(time.time()), "counts": counts, "names": names}
                with lock:
                    state["snapshots"].append(snap)
                    state["names"].update(names)
                    state["last_error"] = None
                with open(HISTORY, "a") as f:
                    f.write(json.dumps(snap) + "\n")
        except Exception as e:
            with lock:
                state["last_error"] = str(e)
            slugs = None  # re-descubrir por si cambió la lista
        time.sleep(POLL_SECONDS)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/data"):
            with lock:
                payload = json.dumps({
                    "snapshots": state["snapshots"],
                    "names": state["names"],
                    "my": MY_PROJECT,
                    "pollSeconds": POLL_SECONDS,
                    "lastError": state["last_error"],
                })
            self._send(payload, "application/json")
        else:
            with open(os.path.join(HERE, "dashboard.html")) as f:
                self._send(f.read(), "text/html; charset=utf-8")

if __name__ == "__main__":
    load_history()
    threading.Thread(target=poll_loop, daemon=True).start()
    print(f"Dashboard: http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
