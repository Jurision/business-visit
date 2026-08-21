#!/usr/bin/env python3
"""Tiny sync service for the Guangzhou trip plan and pre-departure checklist.
Serves and accepts one small JSON document. Nothing else is writable."""
import http.server
import json
import os
import socketserver
import threading
from urllib.parse import urlsplit

STORE = os.environ.get(
    "TRIP_PLAN_STORE", "/opt/caddy-gateway/caddy_data/trip/nate/plan.json"
)
HOST = os.environ.get("TRIP_PLAN_HOST", "172.19.0.1")
PORT = int(os.environ.get("TRIP_PLAN_PORT", "8791"))
KEYS  = {"us", "machines", "zhigong", "hongtai", "bright", "tube"}
CHECKS = {"c%d" % i for i in range(1, 8)}
DAYS  = 5
MAXPD = 3
LOCK  = threading.Lock()

def load():
    try:
        with open(STORE) as f:
            d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("plan", [["tube"], ["bright"], ["machines"], ["hongtai", "us"], []])
    d.setdefault("check", {})
    d.setdefault("rev", 1)
    return d

def valid_plan(plan):
    if not isinstance(plan, list) or len(plan) != DAYS:
        return False
    seen = set()
    for day in plan:
        if not isinstance(day, list) or len(day) > MAXPD:
            return False
        for k in day:
            if k not in KEYS or k in seen:
                return False
            seen.add(k)
    return seen == KEYS

def valid_check(check):
    if not isinstance(check, dict):
        return False
    for k, v in check.items():
        if k not in CHECKS or not isinstance(v, bool):
            return False
    return True

def write(d):
    tmp = STORE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, separators=(",", ":"))
    os.replace(tmp, STORE)
    os.chmod(STORE, 0o644)

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TripPlanSync"
    sys_version = ""

    def _is_plan_path(self):
        return urlsplit(self.path).path.rstrip("/") == "/plan"

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self._is_plan_path():
            with LOCK:
                d = load()
            self._send(200, {"plan": d["plan"], "check": d["check"], "rev": d["rev"]})
        else:
            self._send(404, {"error": "not found"})

    def do_PUT(self):
        if not self._is_plan_path():
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            return self._send(400, {"error": "bad content length"})
        if n <= 0 or n > 8192:
            return self._send(413, {"error": "too big"})
        try:
            body = json.loads(self.rfile.read(n))
        except Exception:
            return self._send(400, {"error": "bad json"})
        has_plan = "plan" in body
        has_check = "check" in body
        if not has_plan and not has_check:
            return self._send(400, {"error": "nothing to update"})
        if has_plan and not valid_plan(body["plan"]):
            return self._send(400, {"error": "bad plan"})
        if has_check and not valid_check(body["check"]):
            return self._send(400, {"error": "bad check"})
        with LOCK:
            d = load()
            changed = False
            if has_plan and body["plan"] != d["plan"]:
                d["plan"] = body["plan"]
                changed = True
            if has_check and body["check"] != d["check"]:
                d["check"] = body["check"]
                changed = True
            if changed:
                d["rev"] = int(d.get("rev", 1)) + 1
                write(d)
        self._send(200, {"ok": True, "rev": d["rev"]})

    def log_message(self, *a):
        pass

class S(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    S((HOST, PORT), H).serve_forever()
