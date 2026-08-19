#!/usr/bin/env python3
"""Tiny sync service for the Guangzhou trip plan.
Serves and accepts exactly one small JSON document. Nothing else is writable."""
import json, os, threading, http.server, socketserver

STORE = "/opt/caddy-gateway/caddy_data/trip/nate/plan.json"
KEYS  = {"us", "machines", "zhigong", "hongtai", "bright", "tube"}
DAYS  = 5
MAXPD = 3
LOCK  = threading.Lock()

def load():
    try:
        with open(STORE) as f:
            d = json.load(f)
        d.setdefault("rev", 1)
        return d
    except Exception:
        return {"plan": [["tube"], ["bright"], ["machines"], ["hongtai", "us"], []], "rev": 1}

def valid(plan):
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
    return True

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/plan"):
            with LOCK:
                d = load()
            self._send(200, {"plan": d["plan"], "rev": d["rev"]})
        else:
            self._send(404, {"error": "not found"})

    def do_PUT(self):
        if not self.path.rstrip("/").endswith("/plan"):
            return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 4096:
            return self._send(413, {"error": "too big"})
        try:
            body = json.loads(self.rfile.read(n))
        except Exception:
            return self._send(400, {"error": "bad json"})
        plan = body.get("plan")
        if not valid(plan):
            return self._send(400, {"error": "bad plan"})
        with LOCK:
            d = load()
            d["plan"] = plan
            d["rev"] = int(d.get("rev", 1)) + 1
            tmp = STORE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(d, f, separators=(",", ":"))
            os.replace(tmp, STORE)
            os.chmod(STORE, 0o644)
        self._send(200, {"ok": True, "rev": d["rev"]})

    def log_message(self, *a):
        pass

class S(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    S(("172.19.0.1", 8791), H).serve_forever()
