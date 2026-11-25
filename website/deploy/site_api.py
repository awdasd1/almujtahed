#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""خدمة موقع المغني الخفيفة (stdlib فقط): رسائل الزوار وعدّادات حقيقية.

تعمل خلف Nginx على 127.0.0.1:8901 وتُدير بـ systemd (almoghni-site-api).
البيانات في /var/lib/almoghni-site/ (لا تدخل مستودع الكود):
  messages.jsonl  سطر لكل رسالة زائر
  counts.json     {visits: N, downloads: {key: N}}

المسارات:
  POST /api/message   {name, type, body}  → حفظ رسالة
  POST /api/visit                         → +1 زائر
  POST /api/download  {key}               → +1 تحميل لملف
  GET  /api/stats                         → الأرقام الحالية
"""
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA_DIR = os.environ.get("ALMOGHNI_SITE_DATA", "/var/lib/almoghni-site")
COUNTS = os.path.join(DATA_DIR, "counts.json")
MESSAGES = os.path.join(DATA_DIR, "messages.jsonl")
MAX_BODY = 64 * 1024


def _counts():
    try:
        with open(COUNTS, encoding="utf-8") as fh:
            d = json.load(fh)
            return {"visits": int(d.get("visits") or 0),
                    "downloads": dict(d.get("downloads") or {})}
    except Exception:
        return {"visits": 0, "downloads": {}}


def _save_counts(d):
    tmp = COUNTS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
    os.replace(tmp, COUNTS)


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:
            n = 0
        if n <= 0 or n > MAX_BODY:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return {}

    def _admin_ok(self):
        want = os.environ.get("ALMOGHNI_ADMIN_TOKEN") or ""
        got = self.headers.get("X-Admin-Token") or ""
        return bool(want) and got == want

    def do_GET(self):
        path = self.path.rstrip("/")
        if path == "/api/stats":
            self._json(_counts())
        elif path == "/api/messages":
            if not self._admin_ok():
                self._json({"error": "unauthorized"}, 401)
                return
            rows = []
            try:
                with open(MESSAGES, encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            try:
                                rows.append(json.loads(line))
                            except Exception:
                                pass
            except FileNotFoundError:
                rows = []
            self._json({"messages": rows})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = self.path.rstrip("/")
        if path == "/api/message":
            b = self._body()
            name = str(b.get("name") or "").strip()[:120]
            kind = str(b.get("type") or "أخرى").strip()[:40]
            body = str(b.get("body") or "").strip()[:8000]
            if not name or not body:
                self._json({"ok": False, "error": "name and body required"}, 400)
                return
            rec = {"name": name, "type": kind, "body": body,
                   "at": datetime.now(timezone.utc).isoformat(),
                   "ip": self.headers.get("X-Forwarded-For", self.client_address[0])}
            with open(MESSAGES, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._json({"ok": True})
        elif path == "/api/messages/delete":
            if not self._admin_ok():
                self._json({"error": "unauthorized"}, 401)
                return
            at = str(self._body().get("at") or "")
            kept = []
            try:
                with open(MESSAGES, encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            rec = json.loads(line)
                        except Exception:
                            kept.append(line)
                            continue
                        if str(rec.get("at") or "") != at:
                            kept.append(line)
                with open(MESSAGES, "w", encoding="utf-8") as fh:
                    fh.writelines(kept)
            except FileNotFoundError:
                pass
            self._json({"ok": True})
        elif path == "/api/visit":
            d = _counts()
            d["visits"] += 1
            _save_counts(d)
            self._json({"ok": True, "visits": d["visits"]})
        elif path == "/api/download":
            key = str(self._body().get("key") or "").strip()[:80]
            if not key:
                self._json({"ok": False}, 400)
                return
            d = _counts()
            d["downloads"][key] = int(d["downloads"].get(key) or 0) + 1
            _save_counts(d)
            self._json({"ok": True})
        else:
            self._json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    ThreadingHTTPServer(("127.0.0.1", 8901), Handler).serve_forever()
