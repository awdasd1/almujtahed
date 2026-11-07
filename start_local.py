#!/usr/bin/env python3
"""تشغيل المجتهد على ماك أو ويندوز أو لينكس بعد سحب نسخة المستودع.

يسحب محرك Qdrant، ونموذج التضمين، ونصوص الشاملة، وسنابشوت المتجهات
من مواضعها على Hugging Face، ثم يفتح الواجهة على المنفذ 8085.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# قرار المنتج (1.10.255): Qdrant موقوف كليًا — لا يُشغَّل ولا تُسحب
# سنابشوتاته ولا نموذج التضمين من أجله. إعادة التفعيل: ALMUJTAHED_QDRANT=on
QDRANT_OFF = os.getenv("ALMUJTAHED_QDRANT", "off").strip().lower() not in ("on", "1", "enabled", "yes")
QDRANT_VERSION = "1.19.1"
QDRANT_DIR = ROOT / "qdrant_service"
EMBED_PATH = ROOT / "models" / "gguf" / "almojtahed-embedding-8b-Q4_K_M.gguf"
COLLECTION_DIR = QDRANT_DIR / "storage" / "collections" / "shamela_almojtahed_8b_dense"
SNAPSHOT_FILE = QDRANT_DIR / "snapshots" / "shamela_almojtahed_8b_dense-2735741993374707-2026-10-15-02-17-32.snapshot"


def public_status(message):
    if any(word in message for word in ("تعذر", "تلف", "يلزم", "لم يرد", "غير متوقع")):
        return "تعذر تشغيل التطبيق"
    installing = ("بايثون", "Python", "مكتبات", "تنزيل", "سحب", "نموذج", "تضمين", "سنابشوت", "قاعدة")
    if any(word in message for word in installing) and "موجود" not in message:
        return "جاري تثبيت الملفات"
    if any(word in message for word in ("الواجهة", "تم تشغيل", "يعمل", "موجود")):
        return "جاري فتح التطبيق"
    return "جاري تهيئة التطبيق"


def log(message):
    print(message, flush=True)
    status_path = os.environ.get("ALMUJTAHED_STATUS_FILE", "").strip()
    if not status_path:
        return
    try:
        Path(status_path).write_text(public_status(message) + "\n", encoding="utf-8")
    except OSError:
        pass


def write_pid(env_name, pid):
    pid_path = os.environ.get(env_name, "").strip()
    if not pid_path:
        return
    try:
        Path(pid_path).write_text(str(pid), encoding="utf-8")
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


def qdrant_binary_name():
    return "qdrant.exe" if os.name == "nt" else "qdrant"


def qdrant_asset_name():
    machine = os.uname().machine.lower() if hasattr(os, "uname") else os.environ.get("PROCESSOR_ARCHITECTURE", "")
    machine = machine.lower()
    if sys.platform == "darwin":
        arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
        return f"qdrant-{arch}-apple-darwin.tar.gz"
    if sys.platform == "win32":
        return "qdrant-x86_64-pc-windows-msvc.zip"
    if machine in ("aarch64", "arm64"):
        return "qdrant-aarch64-unknown-linux-musl.tar.gz"
    return "qdrant-x86_64-unknown-linux-gnu.tar.gz"


def prepare_env():
    env_path = ROOT / ".env"
    example = ROOT / ".env.example"
    if not env_path.exists() and example.exists():
        text = example.read_text(encoding="utf-8").replace("QDRANT_HOST=qdrant", "QDRANT_HOST=127.0.0.1")
        env_path.write_text(text, encoding="utf-8")
        log("تم إنشاء .env من المثال، ومضيف Qdrant صار 127.0.0.1")
    os.environ["ALMUJTAHED_LOCAL"] = "1"
    os.environ["QDRANT_HOST"] = "127.0.0.1"
    os.environ.setdefault("QDRANT_PORT", "6333")
    os.environ.pop("ALMUJTAHED_DATA_DIR", None)


def download(url, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": "almujtahed-local"})
    with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    temporary.replace(destination)


def ensure_qdrant_binary():
    destination = QDRANT_DIR / qdrant_binary_name()
    if destination.is_file() and destination.stat().st_size > 1_000_000:
        log(f"محرك Qdrant موجود: {destination.name}")
        return destination
    asset = qdrant_asset_name()
    url = f"https://github.com/qdrant/qdrant/releases/download/v{QDRANT_VERSION}/{asset}"
    archive = QDRANT_DIR / asset
    log(f"جاري تنزيل محرك Qdrant {QDRANT_VERSION} للجهاز المحلي...")
    download(url, archive)
    extract_dir = QDRANT_DIR / "_qdrant_extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    wanted = {"qdrant", "qdrant.exe"}
    extracted = None
    if asset.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            member = next(name for name in bundle.namelist() if Path(name).name.lower() in wanted and ".." not in Path(name).parts)
            bundle.extract(member, extract_dir)
            extracted = extract_dir / member
    else:
        with tarfile.open(archive) as bundle:
            member = next(item for item in bundle.getmembers() if Path(item.name).name in wanted and item.isreg())
            if ".." in Path(member.name).parts:
                raise SystemExit("أرشيف Qdrant غير متوقع")
            extract_kwargs = {"filter": "data"} if sys.version_info >= (3, 12) else {}
            bundle.extract(member, extract_dir, **extract_kwargs)
            extracted = extract_dir / member.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    shutil.move(str(extracted), destination)
    shutil.rmtree(extract_dir, ignore_errors=True)
    archive.unlink(missing_ok=True)
    if os.name != "nt":
        destination.chmod(0o755)
    log("تم وضع محرك Qdrant في qdrant_service/")
    return destination


def stop_stale_qdrant():
    """قتل أي نسخة Qdrant يتيمة من جلسة سابقة (تحتجز القفل والذاكرة)."""
    killed = []
    pid_path = os.environ.get("ALMUJTAHED_QDRANT_PID_FILE", "").strip()
    pids = set()
    if pid_path:
        try:
            pids.add(int(Path(pid_path).read_text(encoding="utf-8").strip()))
        except (OSError, ValueError):
            pass
    if os.name != "nt":
        try:
            out = subprocess.run(["pgrep", "-f", "qdrant_service/qdrant"],
                                 capture_output=True, text=True, timeout=8).stdout
            pids.update(int(x) for x in out.split() if x.strip().isdigit())
        except Exception:
            pass
    for pid in pids:
        if pid == os.getpid():
            continue
        try:
            os.kill(pid, 15)
            killed.append(pid)
        except OSError:
            continue
    if killed:
        time.sleep(2)
        for pid in killed:
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        log(f"أُوقفت نسخة Qdrant سابقة عالقة: {killed}")


def start_qdrant(binary):
    if port_open(6333):
        log("Qdrant يعمل على المنفذ 6333")
        return
    QDRANT_DIR.mkdir(parents=True, exist_ok=True)
    (QDRANT_DIR / "storage").mkdir(parents=True, exist_ok=True)
    (QDRANT_DIR / "snapshots").mkdir(parents=True, exist_ok=True)
    log_handle = open(QDRANT_DIR / "qdrant.log", "ab", buffering=0)
    kwargs = {
        "cwd": str(QDRANT_DIR),
        "stdout": log_handle,
        "stderr": log_handle,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000 | 0x00000200 | 0x01000000
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(
        [str(binary), "--config-path", str(QDRANT_DIR / "config" / "config.yaml")],
        **kwargs,
    )
    write_pid("ALMUJTAHED_QDRANT_PID_FILE", process.pid)
    for _ in range(45):
        if port_open(6333):
            log("تم تشغيل Qdrant على http://127.0.0.1:6333")
            return
        time.sleep(1)
    raise SystemExit("Qdrant لم يرد خلال 45 ثانية. راجع qdrant_service/qdrant.log")


def embedding_ready():
    return EMBED_PATH.is_file() and EMBED_PATH.stat().st_size > 1024 ** 3


def snapshot_ready():
    try:
        return SNAPSHOT_FILE.is_file() and SNAPSHOT_FILE.stat().st_size > 1024 ** 3
    except OSError:
        return False


def collection_on_disk():
    try:
        return COLLECTION_DIR.is_dir() and any(COLLECTION_DIR.iterdir())
    except OSError:
        return False


def live_collection_ready():
    if not port_open(6333):
        return False
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:6333/collections/shamela_almojtahed_8b_dense",
            timeout=3,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        points = int(((payload.get("result") or {}).get("points_count") or 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False
    return points > 1000


def database_ready():
    return collection_on_disk() or snapshot_ready() or live_collection_ready()


def shamela_ready():
    root = ROOT / "shamela4_data"
    if not root.is_dir():
        return False
    return len(list(root.glob("*/*"))) > 100


def quiet_executable():
    if os.name != "nt":
        return sys.executable
    path = Path(sys.executable)
    if path.name.lower() == "python.exe":
        windowless = path.with_name("pythonw.exe")
        if windowless.is_file():
            return str(windowless)
    return sys.executable


def mark_database_present():
    path = ROOT / "web_ui" / "bootstrap_status.json"
    payload = {
        "phase": "ready",
        "message": "قاعدة البيانات موجودة",
        "received_bytes": 0,
        "expected_bytes": 0,
        "needs_reinstall": False,
        "updated_at": time.time(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


def our_qdrant_listening():
    if not port_open(6333):
        return False
    binary = str((QDRANT_DIR / qdrant_binary_name()).resolve())
    try:
        if os.name == "nt":
            output = subprocess.check_output(["netstat", "-ano", "-p", "tcp"], text=True, timeout=5, errors="replace")
            pids = []
            for line in output.splitlines():
                if ":6333" in line and "LISTENING" in line.upper():
                    parts = line.split()
                    if parts and parts[-1].isdigit():
                        pids.append(parts[-1])
        else:
            output = subprocess.check_output(["lsof", "-nP", "-iTCP:6333", "-sTCP:LISTEN", "-t"], text=True, timeout=5)
            pids = [item for item in output.split() if item.isdigit()]
    except Exception:
        return False
    for pid in pids:
        try:
            if os.name == "nt":
                command = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                    text=True,
                    timeout=8,
                    errors="replace",
                )
            else:
                command = subprocess.check_output(["ps", "-p", pid, "-o", "command="], text=True, timeout=5)
        except Exception:
            continue
        if binary in command.replace("\\", "/"):
            return True
    return False


def spawn_remaining_downloads(snapshot_only=False, texts_only=False):
    if pid_alive("ALMUJTAHED_INIT_PID_FILE"):
        log("تجهيز قاعدة البيانات يعمل بالفعل")
        return
    log_path = ROOT / "web_ui" / "init.log"
    log_handle = open(log_path, "ab", buffering=0)
    kwargs = {
        "cwd": str(ROOT),
        "stdout": log_handle,
        "stderr": log_handle,
        "stdin": subprocess.DEVNULL,
        "env": os.environ.copy(),
    }
    command = [quiet_executable(), "-u", str(ROOT / "init_coolify_data.py"), "--local", "--skip-models"]
    if snapshot_only:
        command.append("--snapshot-only")
    if texts_only:
        command.append("--texts-only")
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000 | 0x00000200 | 0x01000000
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    write_pid("ALMUJTAHED_INIT_PID_FILE", process.pid)
    if snapshot_only:
        log("تركيب قاعدة البيانات من الملف الموجود يعمل في الخلفية")
    elif texts_only:
        log("سحب نصوص الشاملة يعمل في الخلفية. السجل: web_ui/init.log")
    else:
        log("سحب السنابشوت ونصوص الشاملة يعمل في الخلفية. السجل: web_ui/init.log")


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
        log("واجهة المجتهد تعمل بالفعل على http://localhost:8085")
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
    while pid_alive("ALMUJTAHED_INIT_PID_FILE"):
        time.sleep(5)
        if port_open(8085):
            return
        try:
            _serve_web()
        except Exception as ex:
            print(f"تعذر فتح الواجهة: {ex}", flush=True)


def attach_log():
    path = os.environ.get("ALMUJTAHED_LOG_FILE", "").strip()
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
    if local_bundle.runtime_ready(ROOT) or (embedding_ready() and shamela_ready() and database_ready()):
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
    log("تشغيل المجتهد على الجهاز المحلي")
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
    stop_stale_qdrant()
    if QDRANT_OFF:
        log("Qdrant موقوف بقرار المنتج — لا محرك دلالة ولا سنابشوتات؛ البحث اللفظي هو الأساس.")
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
                    "ونزّل كتبك فيه، وسيقرأها المجتهد مباشرة. لن يُنزَّل شيء من الإنترنت.")
        log("الواجهة: http://localhost:8085")
        start_web()
        return
    start_qdrant(ensure_qdrant_binary())
    import init_coolify_data
    if not embedding_ready():
        log("جاري سحب نموذج التضمين إلى models/gguf/ ...")
        init_coolify_data.init_ai_models()
    else:
        log("نموذج التضمين موجود في models/gguf/")
    if collection_on_disk() or live_collection_ready():
        log("قاعدة البيانات موجودة. لن يُعاد سحبها أو تركيبها.")
        mark_database_present()
    elif snapshot_ready():
        if port_open(6333) and not our_qdrant_listening():
            log("ملف قاعدة البيانات موجود، والمنفذ مشغول بمخزن آخر. لن يُعاد السحب.")
            mark_database_present()
        elif collection_on_disk():
            log("قاعدة البيانات موجودة. لن يُعاد سحبها أو تركيبها.")
            mark_database_present()
        else:
            log("ملف قاعدة البيانات موجود. سيُركّب مرة واحدة من غير إعادة سحب.")
            spawn_remaining_downloads(snapshot_only=True)
    elif shamela_ready():
        log("نصوص الشاملة موجودة، وملف قاعدة البيانات غير موجود.")
        spawn_remaining_downloads()
    else:
        spawn_remaining_downloads()
    log("الواجهة: http://localhost:8085")
    start_web()


if __name__ == "__main__":
    main()
