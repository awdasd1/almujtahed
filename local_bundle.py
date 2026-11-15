#!/usr/bin/env python3
"""نسخ المكتبة الشاملة من مجلد محلي وإليه (لا نموذج تضمين ولا مخزن متجهات في التطبيق)."""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

BUNDLE_NAME = "المغني-محلي"
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
    candidates = [folder, folder / BUNDLE_NAME, folder / "المجتهد-محلي"]
    for root in candidates:
        found = _describe(root, minimum)
        if found and not found["missing"]:
            found["root"] = root
            return found
    return None


def _describe(root: Path, minimum: int) -> dict | None:
    if not root.is_dir():
        return None
    shamela = _first_dir([root / "shamela", root / "shamela4_data"])
    if not shamela:
        return None
    return {
        "shamela": shamela,
        "missing": [],
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
    return _dir_ok(root / "shamela4_data")


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
        raise RuntimeError("المجلد لا يحتوي على المكتبة الشاملة")
    expected = _measure([found["shamela"]])
    message = "جاري استيراد النسخة المحلية"
    progress = _Progress(root, expected, message)
    write_job(root, state="copying", message=message, received=0, expected=expected, error="", path=str(found["root"]))
    _copy_tree(found["shamela"], root / "shamela4_data", progress)
    write_job(root, state="done", message="اكتمل الاستيراد. أعد فتح التطبيق.", received=expected, expected=expected, error="")
    _write_bootstrap(root, "ready", "اكتمل النسخ من المجلد المحلي", expected, expected)


def _export_sources(root: Path) -> dict:
    shamela = root / "shamela4_data"
    found = {
        "shamela": shamela if _dir_ok(shamela) else None,
    }
    missing = []
    if not found["shamela"]:
        missing.append("المكتبة الشاملة")
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
    expected = _measure([found["shamela"]])
    free = shutil.disk_usage(destination).free
    if free < expected + 1024 ** 3:
        raise RuntimeError("المساحة في مجلد الحفظ لا تكفي لهذه النسخة")
    message = "جاري تصدير النسخة المحلية"
    progress = _Progress(root, expected, message)
    write_job(root, state="copying", message=message, received=0, expected=expected, error="", path=str(bundle))
    _copy_tree(found["shamela"], bundle / "shamela", progress)
    manifest = {
        "kind": "almoghni-local",
        "version": 2,
        "parts": ["shamela"],
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
        write_job(root, state="error", message="المجلد غير مكتمل", error="يلزم أن يحتوي المجلد على المكتبة الشاملة")
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
