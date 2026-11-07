#!/usr/bin/env python3
"""نسخ نموذج التضمين والمكتبة الشاملة وقاعدة البيانات من مجلد محلي وإليه."""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

MODEL_NAME = "almojtahed-embedding-8b-Q4_K_M.gguf"
COLLECTION_NAME = "shamela_almojtahed_8b_dense"
SNAPSHOT_NAME = "shamela_almojtahed_8b_dense-2735741993374707-2026-10-15-02-17-32.snapshot"
BUNDLE_NAME = "المجتهد-محلي"
MIN_BYTES = 1024 ** 3
SKIP_DIRS = {".git", "_git_tmp", ".cache", "__pycache__", "tmp", "node_modules"}

_job_lock = threading.Lock()
_job = {"state": "idle", "message": "", "received": 0, "expected": 0, "error": "", "path": ""}


def status_path(root: Path) -> Path:
    return root / "web_ui" / "local_bundle_status.json"


def source_path(root: Path) -> Path:
    return root / "web_ui" / "local_source.json"


def read_source(root: Path) -> dict:
    path = source_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_job(root: Path, **fields):
    with _job_lock:
        _job.update(fields)
        payload = dict(_job)
        payload["updated_at"] = time.time()
    try:
        path = status_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


def job_snapshot() -> dict:
    with _job_lock:
        return dict(_job)


def _file_ok(path: Path, minimum: int | None = None) -> bool:
    if minimum is None:
        minimum = MIN_BYTES
    try:
        return path.is_file() and path.stat().st_size > minimum
    except OSError:
        return False


def _dir_ok(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        return any(path.iterdir())
    except OSError:
        return False


def locate(folder: Path, minimum: int | None = None) -> dict | None:
    if minimum is None:
        minimum = MIN_BYTES
    folder = Path(folder).expanduser()
    if not folder.is_dir():
        return None
    candidates = [folder, folder / BUNDLE_NAME]
    for root in candidates:
        found = _describe(root, minimum)
        if found and not found["missing"]:
            found["root"] = root
            return found
    return None


def _describe(root: Path, minimum: int) -> dict | None:
    if not root.is_dir():
        return None
    model = _first_file([
        root / "model" / MODEL_NAME,
        root / "models" / "gguf" / MODEL_NAME,
    ], minimum)
    shamela = _first_dir([root / "shamela", root / "shamela4_data"])
    snapshot = _first_file([
        root / "database" / "snapshot" / SNAPSHOT_NAME,
        root / "qdrant_service" / "snapshots" / SNAPSHOT_NAME,
        root / "snapshot" / SNAPSHOT_NAME,
    ], minimum)
    storage = _first_dir([
        root / "database" / "storage" / "collections" / COLLECTION_NAME,
        root / "qdrant_service" / "storage" / "collections" / COLLECTION_NAME,
    ])
    if not any((model, shamela, snapshot, storage)):
        return None
    missing = []
    if not model:
        missing.append("نموذج التضمين")
    if not shamela:
        missing.append("المكتبة الشاملة")
    if not snapshot and not storage:
        missing.append("قاعدة البيانات")
    return {
        "model": model,
        "shamela": shamela,
        "snapshot": snapshot,
        "storage": storage,
        "missing": missing,
    }


def _first_file(paths, minimum: int):
    for path in paths:
        if _file_ok(path, minimum):
            return path
    return None


def _first_dir(paths):
    for path in paths:
        if _dir_ok(path):
            return path
    return None


def runtime_ready(root: Path) -> bool:
    model = root / "models" / "gguf" / MODEL_NAME
    shamela = root / "shamela4_data"
    storage = root / "qdrant_service" / "storage" / "collections" / COLLECTION_NAME
    snapshot = root / "qdrant_service" / "snapshots" / SNAPSHOT_NAME
    return _file_ok(model) and _dir_ok(shamela) and (_dir_ok(storage) or _file_ok(snapshot))


def _iter_files(folder: Path):
    for current, dirnames, filenames in os.walk(folder):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            yield Path(current) / name


def _measure(paths) -> int:
    total = 0
    for path in paths:
        if path is None:
            continue
        if path.is_file():
            total += path.stat().st_size
        elif path.is_dir():
            for item in _iter_files(path):
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
    return total


class _Progress:
    def __init__(self, root: Path, expected: int, message: str):
        self.root = root
        self.expected = expected
        self.message = message
        self.received = 0
        self._marked = 0.0

    def add(self, count: int):
        self.received += count
        now = time.time()
        if now - self._marked < 1 and self.received < self.expected:
            return
        self._marked = now
        write_job(self.root, state="copying", message=self.message, received=self.received, expected=self.expected, error="")
        _write_bootstrap(self.root, "local", self.message, self.received, self.expected)


def _write_bootstrap(root: Path, phase: str, message: str, received: int, expected: int):
    path = root / "web_ui" / "bootstrap_status.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "phase": phase,
            "message": message,
            "received_bytes": int(received),
            "expected_bytes": int(expected),
            "needs_reinstall": False,
            "updated_at": time.time(),
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


def _copy_file(src: Path, dest: Path, progress: _Progress):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as incoming, dest.open("wb") as outgoing:
        while True:
            chunk = incoming.read(8 * 1024 * 1024)
            if not chunk:
                break
            outgoing.write(chunk)
            progress.add(len(chunk))
    try:
        shutil.copystat(src, dest, follow_symlinks=True)
    except OSError:
        pass


def _copy_tree(src: Path, dest: Path, progress: _Progress):
    for item in _iter_files(src):
        target = dest / item.relative_to(src)
        _copy_file(item, target, progress)


def import_bundle(folder: Path, root: Path):
    found = locate(folder)
    if not found:
        raise RuntimeError("المجلد لا يحتوي على نموذج التضمين والمكتبة الشاملة وقاعدة البيانات")
    expected = _measure([found["model"], found["shamela"], found["snapshot"] or found["storage"]])
    message = "جاري استيراد النسخة المحلية"
    progress = _Progress(root, expected, message)
    write_job(root, state="copying", message=message, received=0, expected=expected, error="", path=str(found["root"]))
    _copy_file(found["model"], root / "models" / "gguf" / MODEL_NAME, progress)
    _copy_tree(found["shamela"], root / "shamela4_data", progress)
    if found["storage"]:
        storage_root = found["storage"].parents[1]
        _copy_tree(storage_root, root / "qdrant_service" / "storage", progress)
    elif found["snapshot"]:
        _copy_file(found["snapshot"], root / "qdrant_service" / "snapshots" / SNAPSHOT_NAME, progress)
    write_job(root, state="done", message="اكتمل الاستيراد. أعد فتح التطبيق ليكتمل تشغيل قاعدة البيانات.", received=expected, expected=expected, error="")
    _write_bootstrap(root, "ready", "اكتمل النسخ من المجلد المحلي", expected, expected)


def _export_sources(root: Path) -> dict:
    model = root / "models" / "gguf" / MODEL_NAME
    shamela = root / "shamela4_data"
    snapshot = root / "qdrant_service" / "snapshots" / SNAPSHOT_NAME
    storage = root / "qdrant_service" / "storage"
    collection = storage / "collections" / COLLECTION_NAME
    found = {
        "model": model if _file_ok(model) else None,
        "shamela": shamela if _dir_ok(shamela) else None,
        "snapshot": snapshot if _file_ok(snapshot) else None,
        "storage": storage if _dir_ok(collection) else None,
    }
    missing = []
    if not found["model"]:
        missing.append("نموذج التضمين")
    if not found["shamela"]:
        missing.append("المكتبة الشاملة")
    if not found["snapshot"] and not found["storage"]:
        missing.append("قاعدة البيانات")
    found["missing"] = missing
    return found


def export_bundle(destination: Path, root: Path):
    found = _export_sources(root)
    if found["missing"]:
        raise RuntimeError("تعذر التصدير، ينقص: " + "، ".join(found["missing"]))
    destination = Path(destination).expanduser()
    bundle = destination / BUNDLE_NAME
    if bundle.exists():
        shutil.rmtree(bundle, ignore_errors=True)
    bundle.mkdir(parents=True, exist_ok=True)
    database = found["snapshot"] or found["storage"]
    expected = _measure([found["model"], found["shamela"], database])
    free = shutil.disk_usage(destination).free
    if free < expected + 1024 ** 3:
        raise RuntimeError("المساحة في مجلد الحفظ لا تكفي لهذه النسخة")
    message = "جاري تصدير النسخة المحلية"
    progress = _Progress(root, expected, message)
    write_job(root, state="copying", message=message, received=0, expected=expected, error="", path=str(bundle))
    _copy_file(found["model"], bundle / "model" / MODEL_NAME, progress)
    _copy_tree(found["shamela"], bundle / "shamela", progress)
    if found["snapshot"]:
        _copy_file(found["snapshot"], bundle / "database" / "snapshot" / SNAPSHOT_NAME, progress)
        kind = "snapshot"
    else:
        _copy_tree(found["storage"], bundle / "database" / "storage", progress)
        kind = "storage"
    manifest = {
        "kind": "almujtahed-local",
        "version": 1,
        "database": kind,
        "parts": ["model", "shamela", "database"],
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_job(root, state="done", message="تم حفظ النسخة المحلية", received=expected, expected=expected, error="", path=str(bundle))


def choose_folder(prompt: str) -> str | None:
    if sys.platform == "darwin":
        script = f'POSIX path of (choose folder with prompt "{prompt}")'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            return None
        path = result.stdout.strip()
        return path or None
    if os.name == "nt":
        command = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
            f"$dialog.Description = '{prompt}'; "
            "$dialog.UseDescriptionForTitle = $true; "
            "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $dialog.SelectedPath }"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", command],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        path = result.stdout.strip()
        return path or None
    return None


def start_export(root: Path, folder: str | None = None) -> dict:
    with _job_lock:
        if _job.get("state") in ("copying", "choosing"):
            return dict(_job)
        _job.update(state="choosing", message="اختر مجلد الحفظ", received=0, expected=0, error="", path="")
    if not folder:
        folder = choose_folder("اختر مجلد حفظ النسخة المحلية")
    if not folder:
        write_job(root, state="cancelled", message="أُلغي اختيار المجلد", error="")
        return job_snapshot()
    destination = Path(folder)
    if not destination.is_dir():
        write_job(root, state="error", message="تعذر حفظ النسخة المحلية", error="المجلد غير موجود")
        return job_snapshot()

    def run():
        try:
            export_bundle(destination, root)
        except Exception as exc:
            write_job(root, state="error", message="تعذر حفظ النسخة المحلية", error=str(exc))

    threading.Thread(target=run, daemon=True).start()
    return {"state": "copying", "message": "جاري تصدير النسخة المحلية", "path": str(destination / BUNDLE_NAME)}


def start_import(root: Path, folder: str | None = None) -> dict:
    with _job_lock:
        if _job.get("state") in ("copying", "choosing"):
            return dict(_job)
        _job.update(state="choosing", message="اختر مجلد النسخة المحلية", received=0, expected=0, error="", path="")
    if not folder:
        folder = choose_folder("اختر مجلد النسخة المحلية")
    if not folder:
        write_job(root, state="cancelled", message="أُلغي اختيار المجلد", error="")
        return job_snapshot()
    if locate(Path(folder)) is None:
        write_job(root, state="error", message="المجلد غير مكتمل", error="يلزم أن يحتوي المجلد على نموذج التضمين والمكتبة الشاملة وقاعدة البيانات")
        return job_snapshot()

    def run():
        try:
            import_bundle(Path(folder), root)
            source_path(root).write_text(
                json.dumps({"mode": "local", "path": folder}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            write_job(root, state="error", message="تعذر الاستيراد", error=str(exc))

    threading.Thread(target=run, daemon=True).start()
    return {"state": "copying", "message": "جاري استيراد النسخة المحلية", "path": folder}
