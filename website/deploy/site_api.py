#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""خدمة موقع المغني الخفيفة (stdlib فقط): رسائل وعدّادات ولوحة تحكم.

تعمل خلف Nginx على 127.0.0.1:8901 وتُدير بـ systemd (almoghni-site-api).
البيانات في /var/lib/almoghni-site/ (خارج جذر الويب والمستودع):
  site.db         SQLite: أخبار وإصدارات وبنود الأقسام (لوحة التحكم)
  messages.jsonl  سطر لكل رسالة زائر
  counts.json     {visits: N, downloads: {key: N}}

مسارات عامة:  GET /api/stats · GET /api/content
  POST /api/message {name,type,body} · POST /api/visit · POST /api/download {key}
مسارات الإدارة (جلسة بكلمة مرور):
  POST /api/login {password} → {token}
  GET  /api/messages · POST /api/messages/delete
  POST /api/news {title,body} · /api/news/update · /api/news/delete
  POST /api/items {category,name,desc,file,size} · /api/items/update · /api/items/delete
  POST /api/releases {version,notes} · /api/releases/delete
  POST /api/upload?category=X&filename=Y  (جسم خام = بايتات الملف)
"""
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DATA_DIR = os.environ.get("ALMOGHNI_SITE_DATA", "/var/lib/almoghni-site")
SITE_ROOT = os.environ.get("ALMOGHNI_SITE_ROOT", "/var/www/almoghni")
DB_PATH = os.path.join(DATA_DIR, "site.db")
COUNTS = os.path.join(DATA_DIR, "counts.json")
MESSAGES = os.path.join(DATA_DIR, "messages.jsonl")
MAX_BODY = 64 * 1024
MAX_UPLOAD = 400 * 1024 * 1024
CATEGORIES = ("projects", "chats", "manuscripts", "agents",
              "reading", "tools", "patterns")
UPLOAD_CATEGORIES = CATEGORIES + ("newsimg",)


def _db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS news(
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT,
        created_at TEXT)""")
    cols = [r[1] for r in con.execute("PRAGMA table_info(news)")]
    if "image" not in cols:
        con.execute("ALTER TABLE news ADD COLUMN image TEXT DEFAULT ''")
    con.execute("""CREATE TABLE IF NOT EXISTS releases(
        id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT, notes TEXT,
        created_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, name TEXT,
        desc TEXT, file TEXT, size TEXT, date TEXT,
        downloads_base INTEGER DEFAULT 0, created_at TEXT)""")
    return con


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


def _now():
    return datetime.now(timezone.utc).isoformat()


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self, limit=MAX_BODY):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:
            n = 0
        if n <= 0 or n > limit:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return {}

    def _session_token(self):
        import hashlib
        pw_hash = os.environ.get("ALMOGHNI_ADMIN_PASSWORD_SHA256") or ""
        if not pw_hash:
            return ""
        return hashlib.sha256((pw_hash + ":almoghni-session").encode()).hexdigest()

    def _admin_ok(self):
        want = self._session_token()
        got = self.headers.get("X-Admin-Token") or ""
        return bool(want) and got == want

    def _need_admin(self):
        if self._admin_ok():
            return True
        self._json({"error": "unauthorized"}, 401)
        return False

    # ---------- قراءات ----------
    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")
        if path == "/api/stats":
            self._json(_counts())
        elif path == "/api/content":
            counts = _counts().get("downloads") or {}
            con = _db()
            news = [dict(r) for r in con.execute(
                "SELECT id,title,body,image,created_at FROM news "
                "ORDER BY id DESC")]
            releases = []
            for r in con.execute(
                    "SELECT id,version,notes,created_at FROM releases "
                    "ORDER BY id DESC"):
                d = dict(r)
                d["notes"] = [ln.strip() for ln in
                              str(d.get("notes") or "").splitlines() if ln.strip()]
                releases.append(d)
            cats = {c: [] for c in CATEGORIES}
            for r in con.execute(
                    "SELECT * FROM items ORDER BY id DESC"):
                d = dict(r)
                d["key"] = f"item-{d['id']}"
                d["downloads"] = int(d.get("downloads_base") or 0) + int(
                    counts.get(d["key"]) or 0)
                cats.setdefault(d["category"], []).append(d)
            con.close()
            self._json({"news": news, "releases": releases,
                        "categories": cats})
        elif path == "/api/messages":
            if not self._need_admin():
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

    # ---------- كتابات ----------
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/api/message":
            b = self._body()
            name = str(b.get("name") or "").strip()[:120]
            kind = str(b.get("type") or "أخرى").strip()[:40]
            body = str(b.get("body") or "").strip()[:8000]
            if not name or not body:
                self._json({"ok": False, "error": "name and body required"}, 400)
                return
            rec = {"name": name, "type": kind, "body": body, "at": _now(),
                   "ip": self.headers.get("X-Forwarded-For",
                                          self.client_address[0])}
            with open(MESSAGES, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._json({"ok": True})
        elif path == "/api/login":
            import hashlib
            pw_hash = os.environ.get("ALMOGHNI_ADMIN_PASSWORD_SHA256") or ""
            given = hashlib.sha256(
                str(self._body().get("password") or "").encode()).hexdigest()
            if pw_hash and given == pw_hash:
                self._json({"ok": True, "token": self._session_token()})
            else:
                self._json({"ok": False, "error": "bad password"}, 401)
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
        elif path == "/api/upload":
            if not self._need_admin():
                return
            q = parse_qs(parsed.query)
            cat = (q.get("category") or [""])[0]
            fname = os.path.basename((q.get("filename") or ["file"])[0])
            fname = re.sub(r"[^\w.\-]+", "_", fname, flags=re.UNICODE) or "file"
            if cat not in UPLOAD_CATEGORIES:
                self._json({"ok": False, "error": "bad category"}, 400)
                return
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except Exception:
                n = 0
            if n <= 0 or n > MAX_UPLOAD:
                self._json({"ok": False, "error": "bad size"}, 400)
                return
            dest_dir = os.path.join(
                SITE_ROOT, "files", "news" if cat == "newsimg" else cat)
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, fname)
            with open(dest, "wb") as fh:
                left = n
                while left > 0:
                    chunk = self.rfile.read(min(1024 * 256, left))
                    if not chunk:
                        break
                    fh.write(chunk)
                    left -= len(chunk)
            try:
                os.chown(dest, 33, 33)  # www-data
            except Exception:
                pass
            size_mb = n / (1024 * 1024)
            size = f"{size_mb:.1f} MB" if size_mb >= 0.1 else f"{max(1, n // 1024)} KB"
            shown_dir = "news" if cat == "newsimg" else cat
            self._json({"ok": True, "file": f"files/{shown_dir}/{fname}",
                        "size": size})
        elif path.startswith("/api/news") or path.startswith("/api/items") \
                or path.startswith("/api/releases"):
            if not self._need_admin():
                return
            self._admin_write(path)
        elif path == "/api/messages/delete":
            if not self._need_admin():
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
        else:
            self._json({"error": "not found"}, 404)

    def _admin_write(self, path):
        b = self._body()
        con = _db()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if path == "/api/news":
            con.execute("INSERT INTO news(title,body,image,created_at) "
                        "VALUES(?,?,?,?)",
                        (str(b.get("title") or "")[:300],
                         str(b.get("body") or "")[:20000],
                         str(b.get("image") or "")[:400], _now()))
        elif path == "/api/news/update":
            con.execute("UPDATE news SET title=?, body=?, image=? "
                        "WHERE id=?",
                        (str(b.get("title") or "")[:300],
                         str(b.get("body") or "")[:20000],
                         str(b.get("image") or "")[:400],
                         int(b.get("id") or 0)))
        elif path == "/api/news/delete":
            con.execute("DELETE FROM news WHERE id=?",
                        (int(b.get("id") or 0),))
        elif path == "/api/items":
            if str(b.get("category") or "") not in CATEGORIES:
                con.close()
                self._json({"ok": False, "error": "bad category"}, 400)
                return
            con.execute(
                "INSERT INTO items(category,name,desc,file,size,date,"
                "downloads_base,created_at) VALUES(?,?,?,?,?,?,0,?)",
                (b["category"], str(b.get("name") or "")[:300],
                 str(b.get("desc") or "")[:2000],
                 str(b.get("file") or "")[:400],
                 str(b.get("size") or "")[:40], today, _now()))
        elif path == "/api/items/update":
            con.execute(
                "UPDATE items SET name=?, desc=?, file=?, size=? WHERE id=?",
                (str(b.get("name") or "")[:300],
                 str(b.get("desc") or "")[:2000],
                 str(b.get("file") or "")[:400],
                 str(b.get("size") or "")[:40], int(b.get("id") or 0)))
        elif path == "/api/items/delete":
            row = con.execute("SELECT file FROM items WHERE id=?",
                              (int(b.get("id") or 0),)).fetchone()
            con.execute("DELETE FROM items WHERE id=?",
                        (int(b.get("id") or 0),))
            con.commit()
            if row and str(row[0]).startswith("files/"):
                target = os.path.join(SITE_ROOT, row[0])
                if os.path.isfile(target):
                    try:
                        os.remove(target)
                    except Exception:
                        pass
            con.close()
            self._json({"ok": True})
            return
        elif path == "/api/releases":
            con.execute("INSERT INTO releases(version,notes,created_at) "
                        "VALUES(?,?,?)",
                        (str(b.get("version") or "")[:40],
                         str(b.get("notes") or "")[:20000], _now()))
        elif path == "/api/releases/delete":
            con.execute("DELETE FROM releases WHERE id=?",
                        (int(b.get("id") or 0),))
        else:
            con.close()
            self._json({"error": "not found"}, 404)
            return
        con.commit()
        con.close()
        self._json({"ok": True})

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    _db().close()
    ThreadingHTTPServer(("127.0.0.1", 8901), Handler).serve_forever()
