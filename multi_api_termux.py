# -*- coding: utf-8 -*-
"""
LDC Multi API Caller - Termux / PC version

Add one or more APIs (e.g. Free Fire info APIs), choose a count (1-200),
and every API is called that many times with a live progress bar.

Termux setup:
    pkg install python -y
    pip install requests
    python multi_api_termux.py

Non-interactive usage:
    python multi_api_termux.py -c 100 "https://api1/info?uid=1" "https://api2/info?uid=1"
"""

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

try:
    import requests
except ImportError:
    print("Missing 'requests'. Run:  pip install requests")
    sys.exit(1)

MAX_COUNT = 200
TIMEOUT = 20

# colors (work in Termux)
R, G, Y, C, B, X = "\033[91m", "\033[92m", "\033[93m", "\033[96m", "\033[1m", "\033[0m"


def banner():
    print(f"""{Y}{B}
  ╔══════════════════════════════════╗
  ║     LDC  MULTI  API  CALLER      ║
  ╚══════════════════════════════════╝{X}""")


def ask_apis():
    apis = []
    print(f"{C}Paste your APIs one by one. Press ENTER on an empty line when done.{X}")
    while True:
        url = input(f"{B}API {len(apis) + 1}:{X} ").strip()
        if not url:
            if apis:
                break
            print(f"{R}Add at least one API.{X}")
            continue
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        apis.append(url)
        print(f"{G}  ✔ Added API {len(apis)}{X}")
    return apis


def ask_int(prompt, default, lo, hi):
    while True:
        raw = input(f"{B}{prompt} [{default}]:{X} ").strip()
        if not raw:
            return default
        if raw.isdigit() and lo <= int(raw) <= hi:
            return int(raw)
        print(f"{R}Enter a number between {lo} and {hi}.{X}")


class Stats:
    def __init__(self, apis, count):
        self.lock = threading.Lock()
        self.count = count
        self.total = len(apis) * count
        self.done = 0
        self.ok = 0
        self.err = 0
        self.per_api = {i: {"done": 0, "ok": 0, "err": 0, "last": ""} for i in range(len(apis))}


def call(session, idx, url, stats, delay, stop):
    if stop.is_set():
        return
    t0 = time.time()
    try:
        r = session.get(url, timeout=TIMEOUT)
        ok = 200 <= r.status_code < 400
        info = f"HTTP {r.status_code} {int((time.time() - t0) * 1000)}ms"
    except requests.RequestException as e:
        ok = False
        info = type(e).__name__
    with stats.lock:
        p = stats.per_api[idx]
        p["done"] += 1
        p["last"] = info
        stats.done += 1
        if ok:
            p["ok"] += 1
            stats.ok += 1
        else:
            p["err"] += 1
            stats.err += 1
    if delay:
        time.sleep(delay / 1000)


def draw(stats, start, final=False):
    pct = stats.done * 100 // stats.total if stats.total else 0
    width = 30
    fill = width * pct // 100
    bar = "█" * fill + "░" * (width - fill)
    elapsed = int(time.time() - start)
    line = (f"\r{Y}[{bar}]{X} {B}{pct:3d}%{X}  {stats.done}/{stats.total}  "
            f"{G}✔{stats.ok}{X} {R}✖{stats.err}{X}  {elapsed}s   ")
    sys.stdout.write(line)
    sys.stdout.flush()
    if final:
        print()


def run(apis, count, threads, delay):
    stats = Stats(apis, count)
    stop = threading.Event()
    # interleave APIs so all of them progress together
    jobs = [(i, u) for _ in range(count) for i, u in enumerate(apis)]

    print(f"\n{C}Starting: {len(apis)} API(s) × {count} = {stats.total} calls, "
          f"{threads} parallel. Press Ctrl+C to stop.{X}\n")
    start = time.time()
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (Linux; Android 12) LDC-MultiAPI/1.0"
    adapter = requests.adapters.HTTPAdapter(pool_connections=threads, pool_maxsize=threads)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    pool = ThreadPoolExecutor(max_workers=threads)
    futures = [pool.submit(call, session, i, u, stats, delay, stop) for i, u in jobs]
    try:
        while any(not f.done() for f in futures):
            draw(stats, start)
            time.sleep(0.2)
    except KeyboardInterrupt:
        stop.set()
        for f in futures:
            f.cancel()
        print(f"\n{Y}Stopping...{X}")
    pool.shutdown(wait=True)
    draw(stats, start, final=True)

    print(f"\n{B}Result per API:{X}")
    for i, url in enumerate(apis):
        p = stats.per_api[i]
        short = url if len(url) <= 60 else url[:57] + "..."
        print(f"  {B}API {i + 1}{X} {short}")
        print(f"      {p['done']}/{count}  {G}✔ {p['ok']}{X}  {R}✖ {p['err']}{X}  last: {p['last']}")
    secs = int(time.time() - start)
    state = "Stopped" if stop.is_set() else "Finished"
    print(f"\n{G}{B}{state}: ✔ {stats.ok} ok, ✖ {stats.err} failed in {secs}s{X}\n")


def main():
    ap = argparse.ArgumentParser(description="Call multiple APIs N times each.")
    ap.add_argument("apis", nargs="*", help="API URLs (leave empty for interactive mode)")
    ap.add_argument("-c", "--count", type=int, help=f"calls per API (1-{MAX_COUNT})")
    ap.add_argument("-t", "--threads", type=int, default=5, help="parallel requests (default 5)")
    ap.add_argument("-d", "--delay", type=int, default=100, help="delay per call in ms (default 100)")
    args = ap.parse_args()

    banner()
    if args.apis:
        apis = [u if u.lower().startswith(("http://", "https://")) else "https://" + u for u in args.apis]
        count = max(1, min(MAX_COUNT, args.count or 10))
        threads = max(1, min(20, args.threads))
        delay = max(0, args.delay)
    else:
        apis = ask_apis()
        count = ask_int(f"Count per API (1-{MAX_COUNT})", 10, 1, MAX_COUNT)
        threads = ask_int("Parallel requests (1-20)", 5, 1, 20)
        delay = ask_int("Delay per call in ms (0-10000)", 100, 0, 10000)
        total = len(apis) * count
        ans = input(f"{Y}Confirm: {len(apis)} API(s) × {count} = {total} calls. Start? (y/n):{X} ")
        if ans.strip().lower() not in ("y", "yes", ""):
            print("Cancelled.")
            return

    run(apis, count, threads, delay)


if __name__ == "__main__":
    main()
