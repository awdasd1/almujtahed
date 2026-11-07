#!/usr/bin/env python3
"""عامل جسر الشاملة: عملية مستقلة بـ JVM وقارئ Lucene خاص بها (1.10.270).

تعدد الجسور: فهرس الشاملة للقراءة فقط ومُخزَّن بالذاكرة المُصفَّحة (mmap)،
فعدة عمليات تقرأه معًا بأمان ويتشارك نظام التشغيل صفحاته بينها. كل عامل
يجيب طلبًا واحدًا في كل مرة، والعملية الأم توزّع الطلبات على العمال
وتجمع الأجوبة — فتتضاعف طاقة البحث بعدد العمال بدل أن تتسلسل كلها على
عبور JPype واحد. البروتوكول: سطر JSON في stdin وسطر JSON في stdout.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
os.environ["ALMUJTAHED_BRIDGE_WORKER"] = "1"

_PROTO = sys.stdout


def main():
    # مطبوعات المكتبات كلها إلى stderr حتى لا تلوّث قناة البروتوكول
    sys.stdout = sys.stderr
    import shamela_search as SS

    try:
        SS._search_local("الغناء", mode="words", limit=1)  # تسخين JVM والقارئ
    except Exception:
        pass
    for raw in sys.stdin:
        raw = (raw or "").strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except Exception:
            continue
        if req.get("ping"):
            resp = {"status": "ok", "pong": True, "results": []}
        else:
            try:
                resp = SS._search_local(
                    req.get("q") or "", mode=req.get("mode") or "phrase",
                    death_max=req.get("death_max"), death_min=req.get("death_min"),
                    categories=req.get("categories"),
                    book_ids=req.get("book_ids"),
                    include_alive=bool(req.get("include_alive")),
                    limit=int(req.get("limit") or 10))
            except Exception as exc:
                resp = {"status": "error", "message": str(exc)[:200], "results": []}
        try:
            _PROTO.write(json.dumps(resp, ensure_ascii=False) + "\n")
            _PROTO.flush()
        except Exception:
            break


if __name__ == "__main__":
    main()
