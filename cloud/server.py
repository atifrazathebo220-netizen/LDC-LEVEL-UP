# -*- coding: utf-8 -*-
"""
LDC Multi API Caller - CLOUD version

The server makes the API calls itself, so you can close your browser/phone
after pressing Start. Open the page again any time to see progress.

Run locally:
    pip install -r requirements.txt
    python server.py                      # http://localhost:8000

Host (Render / Railway / Koyeb / VPS):
    start command:  gunicorn server:app --workers 1 --threads 8 --bind 0.0.0.0:$PORT
    (keep --workers 1: jobs live in this one process's memory)

Optional password: set env var ADMIN_KEY=yourpassword. The page will ask for it.
"""

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Flask, jsonify, request, send_from_directory

MAX_COUNT = 200
MAX_APIS = 50
MAX_THREADS = 20
TIMEOUT = 20
KEEP_JOBS = 30                      # finished jobs kept in memory
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
HERE = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
jobs = {}                           # id -> job dict
jobs_lock = threading.Lock()


# ---------------- helpers ----------------

@app.after_request
def cors(resp):
    # lets the HTML page work even when hosted on a different site (e.g. GitHub Pages)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Admin-Key"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


def authorized():
    return not ADMIN_KEY or request.headers.get("X-Admin-Key") == ADMIN_KEY


def public(job):
    """Snapshot of a job that is safe to send as JSON."""
    with job["lock"]:
        return {
            "id": job["id"], "status": job["status"], "count": job["count"],
            "threads": job["threads"], "delay": job["delay"],
            "total": job["total"], "done": job["done"], "ok": job["ok"], "err": job["err"],
            "percent": int(job["done"] * 100 / job["total"]) if job["total"] else 0,
            "created": job["created"], "finished": job["finished"],
            "elapsed": int((job["finished"] or time.time()) - job["created"]),
            "apis": [dict(a) for a in job["apis"]],
        }


def prune():
    with jobs_lock:
        finished = sorted((j for j in jobs.values() if j["status"] != "running"),
                          key=lambda j: j["created"])
        for j in finished[:-KEEP_JOBS] if len(finished) > KEEP_JOBS else []:
            jobs.pop(j["id"], None)


# ---------------- worker ----------------

def run_job(job):
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (Linux; Android 12) LDC-MultiAPI/1.0"
    adapter = requests.adapters.HTTPAdapter(pool_connections=job["threads"], pool_maxsize=job["threads"])
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    def call(idx):
        if job["stop"].is_set():
            return
        api = job["apis"][idx]
        t0 = time.time()
        try:
            r = session.get(api["url"], timeout=TIMEOUT)
            ok = 200 <= r.status_code < 400
            info = f"HTTP {r.status_code} {int((time.time() - t0) * 1000)}ms"
        except requests.RequestException as e:
            ok, info = False, type(e).__name__
        with job["lock"]:
            api["done"] += 1
            api["last"] = info
            job["done"] += 1
            if ok:
                api["ok"] += 1
                job["ok"] += 1
            else:
                api["err"] += 1
                job["err"] += 1
        if job["delay"]:
            time.sleep(job["delay"] / 1000)

    # interleave APIs so all of them progress together
    order = [i for _ in range(job["count"]) for i in range(len(job["apis"]))]
    with ThreadPoolExecutor(max_workers=job["threads"]) as pool:
        list(pool.map(call, order))

    with job["lock"]:
        job["status"] = "stopped" if job["stop"].is_set() else "finished"
        job["finished"] = time.time()
    prune()


# ---------------- routes ----------------

@app.route("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.route("/api/<path:_>", methods=["OPTIONS"])
def preflight(_):
    return "", 204


@app.route("/api/ping")
def ping():
    return jsonify({"ok": True, "needs_key": bool(ADMIN_KEY), "authorized": authorized(),
                    "max_count": MAX_COUNT})


@app.route("/api/jobs", methods=["GET"])
def list_jobs():
    if not authorized():
        return jsonify({"error": "wrong admin key"}), 401
    with jobs_lock:
        items = sorted(jobs.values(), key=lambda j: j["created"], reverse=True)
    return jsonify([public(j) for j in items])


@app.route("/api/jobs", methods=["POST"])
def create_job():
    if not authorized():
        return jsonify({"error": "wrong admin key"}), 401
    data = request.get_json(silent=True) or {}
    urls = []
    for u in data.get("apis") or []:
        u = str(u).strip()
        if not u:
            continue
        if not u.lower().startswith(("http://", "https://")):
            u = "https://" + u
        urls.append(u)
    if not urls:
        return jsonify({"error": "add at least one API"}), 400
    if len(urls) > MAX_APIS:
        return jsonify({"error": f"max {MAX_APIS} APIs"}), 400

    def num(key, default, lo, hi):
        try:
            return max(lo, min(hi, int(data.get(key, default))))
        except (TypeError, ValueError):
            return default

    count = num("count", 10, 1, MAX_COUNT)
    job = {
        "id": uuid.uuid4().hex[:8], "status": "running", "count": count,
        "threads": num("threads", 5, 1, MAX_THREADS), "delay": num("delay", 100, 0, 10000),
        "total": len(urls) * count, "done": 0, "ok": 0, "err": 0,
        "created": time.time(), "finished": None,
        "apis": [{"url": u, "done": 0, "ok": 0, "err": 0, "last": ""} for u in urls],
        "lock": threading.Lock(), "stop": threading.Event(),
    }
    with jobs_lock:
        jobs[job["id"]] = job
    threading.Thread(target=run_job, args=(job,), daemon=True).start()
    return jsonify(public(job)), 201


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    if not authorized():
        return jsonify({"error": "wrong admin key"}), 401
    job = jobs.get(job_id)
    return (jsonify(public(job)), 200) if job else (jsonify({"error": "not found"}), 404)


@app.route("/api/jobs/<job_id>/stop", methods=["POST"])
def stop_job(job_id):
    if not authorized():
        return jsonify({"error": "wrong admin key"}), 401
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    job["stop"].set()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"LDC Multi API Cloud running on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
