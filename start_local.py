#!/usr/bin/env python3
"""تشغيل المغني على ماك أو ويندوز أو لينكس.

لا مخزن متجهات ولا نموذج تضمين في التطبيق (أُزيلا نهائيًا في 1.10.553):
المكتبة هي تطبيق «المكتبة الشاملة» عند المستخدم — بحث لفظي في فهرسها
المباشر واستخراج عند اللمس — ثم تُفتح الواجهة على المنفذ 8085.
"""

import os
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def public_status(message):
    if any(word in message for word in ("تعذر", "تلف", "يلزم", "لم يرد", "غير متوقع")):
        return "تعذر تشغيل التطبيق"
    installing = ("بايثون", "Python", "مكتبات", "تنزيل", "سحب")
    if any(word in message for word in installing) and "موجود" not in message:
        return "جاري تثبيت الملفات"
    if any(word in message for word in ("الواجهة", "تم تشغيل", "يعمل", "موجود")):
        return "جاري فتح التطبيق"
    return "جاري تهيئة التطبيق"


def log(message):
    print(message, flush=True)
    status_path = os.environ.get("ALMOGHNI_STATUS_FILE", "").strip()
    if not status_path:
        return
    try:
        Path(status_path).write_text(public_status(message) + "\n", encoding="utf-8")
    except OSError:
        pass


def port_open(port):
    sock = socket.socket()
    sock.settimeout(1.0)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def prepare_env():
    env_path = ROOT / ".env"
    example = ROOT / ".env.example"
    if not env_path.exists() and example.exists():
        env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        log("تم إنشاء .env من المثال")
    os.environ["ALMOGHNI_LOCAL"] = "1"
    os.environ.pop("ALMOGHNI_DATA_DIR", None)


def shamela_ready():
    root = ROOT / "shamela4_data"
    if not root.is_dir():
        return False
    return len(list(root.glob("*/*"))) > 100


def _serve_web():
    if port_open(8085):
        return
    web_dir = ROOT / "web_ui"
    os.chdir(web_dir)
    if os.name == "nt":
        import runpy
        sys.path.insert(0, str(web_dir))
        sys.argv = ["server.py"]
        runpy.run_path(str(web_dir / "server.py"), run_name="__main__")
        return
    os.execv(sys.executable, [sys.executable, "server.py"])


def start_web():
    if port_open(8085):
        log("واجهة المغني تعمل بالفعل على http://localhost:8085")
        if os.name == "nt":
            while port_open(8085):
                time.sleep(5)
        return
    if os.name != "nt":
        _serve_web()
        return
    for attempt in range(3):
        try:
            _serve_web()
            if port_open(8085):
                while port_open(8085):
                    time.sleep(5)
                return
        except SystemExit as ex:
            if ex.code in (0, None):
                return
            print(f"تعذر فتح الواجهة: {ex}", flush=True)
        except Exception as ex:
            print(f"تعذر فتح الواجهة: {ex}", flush=True)
        log("جاري فتح التطبيق")
        time.sleep(2)
    while pid_alive("ALMOGHNI_INIT_PID_FILE"):
        time.sleep(5)
        if port_open(8085):
            return
        try:
            _serve_web()
        except Exception as ex:
            print(f"تعذر فتح الواجهة: {ex}", flush=True)


def attach_log():
    path = os.environ.get("ALMOGHNI_LOG_FILE", "").strip()
    if not path:
        return
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        handle = open(path, "a", encoding="utf-8", buffering=1)
    except OSError:
        return
    sys.stdout = handle
    sys.stderr = handle


def pid_alive(env_name):
    pid_path = os.environ.get(env_name, "").strip()
    if not pid_path or not os.path.isfile(pid_path):
        return False
    try:
        pid = int(Path(pid_path).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def apply_local_source():
    import local_bundle
    choice = local_bundle.read_source(ROOT)
    if choice.get("mode") != "local":
        return
    if local_bundle.runtime_ready(ROOT):
        log("النسخة المحلية موجودة على الجهاز")
        return
    folder = str(choice.get("path") or "").strip()
    if not folder:
        raise RuntimeError("لم يُحدد مجلد النسخة المحلية")
    log("جاري النسخ من المجلد المحلي")
    local_bundle.import_bundle(folder, ROOT)
    log("اكتمل النسخ من المجلد المحلي")


def main():
    if sys.version_info < (3, 10):
        raise SystemExit("يلزم بايثون 3.10 أو أحدث.")
    attach_log()
    log("تشغيل المغني على الجهاز المحلي")
    prepare_env()
    try:
        apply_local_source()
    except Exception as ex:
        log(f"تعذر النسخ من المجلد المحلي: {ex}")
        try:
            import local_bundle
            local_bundle._write_bootstrap(ROOT, "error", "تعذر النسخ من المجلد المحلي", 0, 0)
        except Exception:
            pass
        raise SystemExit(1)
    if not shamela_ready():
        # سياسة المنتج: لا سحب بيانات من أي مصدر خارجي إطلاقًا.
        # المكتبة = تطبيق الشاملة عند المستخدم: بحث في فهرسها مباشرة
        # واستخراج عند اللمس. لا شاملة → إرشاد، لا تنزيل صامت.
        lazy = False
        try:
            sys.path.insert(0, str(ROOT / "web_ui"))
            import shamela_link
            cen = shamela_link.census()
            if cen.get("found") and (cen.get("downloaded") or 0) > 0:
                shamela_link.set_library_source("shamela")
                lazy = True
                log(f"وُجد تطبيق الشاملة ({cen.get('downloaded')} كتابًا منزّلًا) — "
                    "المصدر: الشاملة المحلية مباشرة (بحث فوري واستخراج عند اللمس، بلا تنزيلات).")
        except Exception as ex:
            log(f"تعذر فحص الشاملة المحلية: {ex}")
        if not lazy:
            log("لا مكتبة شاملة منزّلة على هذا الجهاز — ثبّت تطبيق «المكتبة الشاملة» "
                "ونزّل كتبك فيه، وسيقرأها المغني مباشرة. لن يُنزَّل شيء من الإنترنت.")
    log("جاري تجهيز خادم التطبيق")
    start_web()


if __name__ == "__main__":
    main()
