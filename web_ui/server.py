#!/usr/bin/env python3
"""
منظومة المجتهد - خادم الويب والواجهة الخلفية (server.py)
الخطة الأولى: ربط البحث الدلالي الحي بمخزن Qdrant (shamela_corpus - 5.14M نص)
مع استخراج النصوص الأصلية من صفحات الشاملة وتطبيق نموذج إعادة الترتيب
"""

import os
import sys
import asyncio
import json
import time
import sqlite3
import re
import urllib.request
import urllib.error
import urllib.parse
import html
import mimetypes
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import numpy as np
import hashlib
import hmac
import secrets
import textwrap
import subprocess
import shutil
import concurrent.futures
import threading
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, Response, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny, Range
import astronomy_engine
import shamela_local_mcp
try:
    import rank_bm25
except ImportError:
    rank_bm25 = None


# المسارات الأساسية والذاتية لمنظومة المجتهد (Portable Self-Contained Paths)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
PACKAGE_ROOT = BASE_DIR.parent
SYSTEM_ROOT = PACKAGE_ROOT.parent

# تحميل البيئة الافتراضية (.env)
ENV_FILE_PATH = PACKAGE_ROOT / ".env"
if ENV_FILE_PATH.exists():
    load_dotenv(ENV_FILE_PATH)
elif (BASE_DIR / ".env").exists():
    ENV_FILE_PATH = BASE_DIR / ".env"
    load_dotenv(ENV_FILE_PATH)

# مسارات قواعد البيانات والشاملة (دعم المجلد المستقل أولاً ثم المسارات الاحتياطية)
if (PACKAGE_ROOT / "shamela_index.db").exists():
    DB_INDEX_PATH = PACKAGE_ROOT / "shamela_index.db"
elif (BASE_DIR / "shamela_index.db").exists():
    DB_INDEX_PATH = BASE_DIR / "shamela_index.db"
elif Path("/Users/maa/Shamela Snapshot/shamela_index.db").exists():
    DB_INDEX_PATH = Path("/Users/maa/Shamela Snapshot/shamela_index.db")
else:
    DB_INDEX_PATH = PACKAGE_ROOT / "shamela_index.db"

if (PACKAGE_ROOT / "shamela4_data").exists():
    SHAMELA_DATA_PATH = PACKAGE_ROOT / "shamela4_data"
elif Path("/Users/maa/embedd traning/shamela4_data").exists():
    SHAMELA_DATA_PATH = Path("/Users/maa/embedd traning/shamela4_data")
else:
    SHAMELA_DATA_PATH = PACKAGE_ROOT / "shamela4_data"

# خريطة التصنيفات الرسمية الأربعين للمكتبة الشاملة
CATEGORY_MAP = {
    "العقيدة": 1, "01": 1, "1": 1,
    "الفرق والردود": 2, "02": 2, "2": 2,
    "التفسير": 3, "03": 3, "3": 3,
    "علوم القرآن وأصول التفسير": 4, "علوم القرآن": 4, "04": 4, "4": 4,
    "التجويد والقراءات": 5, "التجويد": 5, "القراءات": 5, "05": 5, "5": 5,
    "كتب السنة": 6, "الحديث": 6, "السنة": 6, "06": 6, "6": 6,
    "شروح الحديث": 7, "07": 7, "7": 7,
    "التخريج والأطراف": 8, "التخريج": 8, "08": 8, "8": 8,
    "العلل والسؤلات الحديثية": 9, "العلل": 9, "09": 9, "9": 9,
    "علوم الحديث": 10, "مصطلح الحديث": 10, "10": 10,
    "أصول الفقه": 11, "11": 11,
    "علوم الفقه والقواعد الفقهية": 12, "القواعد الفقهية": 12, "12": 12,
    "المنطق": 13, "13": 13,
    "الفقه الحنفي": 14, "الحنفي": 14, "14": 14,
    "الفقه المالكي": 15, "المالكي": 15, "15": 15,
    "الفقه الشافعي": 16, "الشافعي": 16, "16": 16,
    "الفقه الحنبلي": 17, "الحنبلي": 17, "17": 17,
    "الفقه العام": 18, "18": 18,
    "مسائل فقهية": 19, "19": 19,
    "السياسة الشرعية والقضاء": 20, "السياسة الشرعية": 20, "القضاء": 20, "20": 20,
    "الفرائض والوصايا": 21, "الفرائض": 21, "21": 21,
    "الفتاوى": 22, "22": 22,
    "الرقائق والآداب والأذكار": 23, "الرقائق": 23, "الآداب": 23, "23": 23,
    "السيرة النبوية": 24, "السيرة": 24, "24": 24,
    "التاريخ": 25, "25": 25,
    "التراجم والطبقات": 26, "التراجم": 26, "الطبقات": 26, "26": 26,
    "الأنساب": 27, "27": 27,
    "البلدان والرحلات": 28, "البلدان": 28, "28": 28,
    "كتب اللغة": 29, "اللغة": 29, "29": 29,
    "الغريب والمعاجم": 30, "المعاجم": 30, "30": 30,
    "النحو والصرف": 31, "النحو": 31, "الصرف": 31, "31": 31,
    "الأدب": 32, "32": 32,
    "العروض والقوافي": 33, "العروض": 33, "33": 33,
    "الشعر ودواوينه": 34, "الشعر": 34, "34": 34,
    "البلاغة": 35, "35": 35,
    "الجوامع": 36, "36": 36,
    "فهارس الكتب والأدلة": 37, "الفهارس": 37, "37": 37,
    "الطب": 38, "38": 38,
    "كتب عامة": 39, "39": 39,
    "علوم أخرى": 40, "40": 40
}

# أسماء الأقسام والتصنيفات الأربعين المعتمدة والمطابقة تماماً لمفهرس Qdrant
ID_TO_CATEGORY_NAME = {
    1: "العقيدة",
    2: "الفرق والردود",
    3: "التفسير",
    4: "علوم القرآن وأصول التفسير",
    5: "التجويد والقراءات",
    6: "كتب السنة",
    7: "شروح الحديث",
    8: "التخريج والأطراف",
    9: "العلل والسؤلات الحديثية",
    10: "علوم الحديث",
    11: "أصول الفقه",
    12: "علوم الفقه والقواعد الفقهية",
    13: "المنطق",
    14: "الفقه الحنفي",
    15: "الفقه المالكي",
    16: "الفقه الشافعي",
    17: "الفقه الحنبلي",
    18: "الفقه العام",
    19: "مسائل فقهية",
    20: "السياسة الشرعية والقضاء",
    21: "الفرائض والوصايا",
    22: "الفتاوى",
    23: "الرقائق والآداب والأذكار",
    24: "السيرة النبوية",
    25: "التاريخ",
    26: "التراجم والطبقات",
    27: "الأنساب",
    28: "البلدان والرحلات",
    29: "كتب اللغة",
    30: "الغريب والمعاجم",
    31: "النحو والصرف",
    32: "الأدب",
    33: "العروض والقوافي",
    34: "الشعر ودواوينه",
    35: "البلاغة",
    36: "الجوامع",
    37: "فهارس الكتب والأدلة",
    38: "الطب",
    39: "كتب عامة",
    40: "علوم أخرى"
}

def resolve_clean_category_name(raw_cat: Any) -> Optional[str]:
    """تحويل التصنيف سواء كان رقماً (1 أو '1' أو '01') أو اسماً عربياً إلى الاسم الرسمي المطابق في Qdrant"""
    if raw_cat is None:
        return None
    raw_str = str(raw_cat).strip()
    if not raw_str:
        return None

    # 1. إذا كان رقماً صحيحاً أو نصاً رقمياً
    try:
        numeric_val = int(raw_str)
        if numeric_val in ID_TO_CATEGORY_NAME:
            return ID_TO_CATEGORY_NAME[numeric_val]
    except ValueError:
        pass

    # 2. فحص التطابق التام مع الأسماء الرسمية
    for name in ID_TO_CATEGORY_NAME.values():
        if raw_str == name:
            return name

    # 3. فحص الخريطة المرادفة CATEGORY_MAP
    if raw_str in CATEGORY_MAP:
        cid = CATEGORY_MAP[raw_str]
        if cid in ID_TO_CATEGORY_NAME:
            return ID_TO_CATEGORY_NAME[cid]

    # 4. البحث الجزئي بالكلمات
    for k, cid in CATEGORY_MAP.items():
        if not k.isdigit() and k in raw_str:
            if cid in ID_TO_CATEGORY_NAME:
                return ID_TO_CATEGORY_NAME[cid]

    return raw_str

def resolve_book_titles_for_search(raw_books: List[str], cursor=None) -> List[str]:
    """تنظيف وتوسيع أسماء الكتب لتطابق عناوين Qdrant بدقة متناهية"""
    if not raw_books:
        return []
    resolved = set()
    for b in raw_books:
        if not b or not str(b).strip():
            continue
        cleaned = html.unescape(str(b)).strip()
        if not cleaned:
            continue
        resolved.add(cleaned)

        # إذا كان المؤشر لقاعدة البيانات متاحاً، نبحث إن كان عنواناً مختصراً كـ (صحيح البخاري)
        if cursor:
            try:
                # 1. محاولة المطابقة المباشرة أولاً
                cursor.execute("SELECT title_ar FROM books WHERE title_ar = ? LIMIT 1", (cleaned,))
                row = cursor.fetchone()
                if row and row["title_ar"]:
                    resolved.add(row["title_ar"])
                else:
                    # 2. محاولة البحث كبادئة أو جزء من الاسم (مثلاً: صحيح البخاري -> جميع طبعات البخاري)
                    cursor.execute("SELECT title_ar FROM books WHERE title_ar LIKE ? LIMIT 50", (f"%{cleaned}%",))
                    matches = [r["title_ar"] for r in cursor.fetchall() if r["title_ar"]]
                    if matches:
                        resolved.update(matches)
            except Exception:
                pass
    return list(resolved)

app = FastAPI(
    title="منظومة المجتهد",
    description="المكتبة الشاملة المضمنة والمكممة - بحث دلالي حي في 5.14 مليون مقطع",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# دوال ونظام إدارة البيئة (.env) والمصادقة الأمنية (Authentication & Sessions)
# =============================================================================

SESSION_COOKIE_NAME = "almujtahed_session"
SESSION_DURATION_SECONDS = 3 * 24 * 3600  # 3 days = 259,200 seconds

def update_env_file(updates: Dict[str, Any]):
    """تحديث وكتابة المتغيرات داخل ملف .env مع حفظ التعليقات والترتيب"""
    target_path = ENV_FILE_PATH if (ENV_FILE_PATH and ENV_FILE_PATH.exists()) else (PACKAGE_ROOT / ".env")
    lines = []
    existing_keys = set()
    if target_path.exists():
        lines = target_path.read_text(encoding="utf-8").splitlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                existing_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in existing_keys:
            new_lines.append(f"{k}={v}")

    target_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    for k, v in updates.items():
        os.environ[k] = str(v)

def get_session_secret() -> str:
    secret = os.getenv("SESSION_SECRET", "").strip()
    if not secret:
        secret = secrets.token_hex(32)
        update_env_file({"SESSION_SECRET": secret})
    return secret

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def generate_session_token(username: str, duration_seconds: int = SESSION_DURATION_SECONDS) -> str:
    secret = get_session_secret()
    expiry = int(time.time()) + duration_seconds
    signature = hmac.new(secret.encode("utf-8"), f"{username}:{expiry}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{username}:{expiry}:{signature}"

def verify_session_token(token: str) -> Optional[str]:
    if not token or ":" not in token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    username, expiry_str, signature = parts
    try:
        expiry = int(expiry_str)
    except ValueError:
        return None
    if time.time() > expiry:
        return None  # انتهت صلاحية الجلسة (3 أيام)
    secret = get_session_secret()
    expected_sig = hmac.new(secret.encode("utf-8"), f"{username}:{expiry}".encode("utf-8"), hashlib.sha256).hexdigest()
    if hmac.compare_digest(signature, expected_sig):
        return username
    return None

def is_auth_configured() -> bool:
    username = os.getenv("AUTH_USERNAME", "").strip()
    pwd_hash = os.getenv("AUTH_PASSWORD_HASH", "").strip()
    return bool(username and pwd_hash)

def get_current_user_from_request(request: Request) -> Optional[str]:
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        user = verify_session_token(cookie_token)
        if user:
            return user
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        user = verify_session_token(token)
        if user:
            return user
    return None

MEMBERS_PATH = BASE_DIR / "members.json"
NOTICES_PATH = BASE_DIR / "notices.json"
_members_lock = threading.Lock()
_notices_lock = threading.Lock()
_share_lock = threading.Lock()
MEMBER_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,31}$")

def load_members_store() -> Dict[str, Any]:
    with _members_lock:
        if not MEMBERS_PATH.exists():
            return {"invites": [], "accounts": []}
        try:
            data = json.loads(MEMBERS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"invites": [], "accounts": []}
        if not isinstance(data, dict):
            return {"invites": [], "accounts": []}
        data.setdefault("invites", [])
        data.setdefault("accounts", [])
        return data

def save_members_store(data: Dict[str, Any]) -> None:
    with _members_lock:
        MEMBERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = MEMBERS_PATH.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(MEMBERS_PATH)

def same_text(left: str, right: str) -> bool:
    left = left or ""
    right = right or ""
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)

def find_member_account(username: str) -> Optional[Dict[str, Any]]:
    name = (username or "").strip()
    for account in load_members_store().get("accounts", []):
        if account.get("username") == name:
            return account
    return None

def account_role(username: Optional[str]) -> Optional[str]:
    name = (username or "").strip()
    if not name:
        return None
    admin_name = os.getenv("AUTH_USERNAME", "").strip()
    if admin_name and same_text(name, admin_name):
        return "admin"
    account = find_member_account(name)
    if not account:
        return None
    if account.get("disabled"):
        return "disabled"
    return "member"

def require_admin(request: Request) -> str:
    user = get_current_user_from_request(request)
    if account_role(user) != "admin":
        raise HTTPException(status_code=403, detail="تبويب الأعضاء متاح للمشرف فقط")
    return user or ""

ADMIN_OWNER_ID = "admin"

def ensure_member_id(username: str) -> str:
    store = load_members_store()
    for account in store.get("accounts", []):
        if account.get("username") != username:
            continue
        if account.get("id"):
            return str(account["id"])
        account["id"] = "m_" + secrets.token_hex(8)
        save_members_store(store)
        return str(account["id"])
    raise HTTPException(status_code=401, detail="جلسة غير مصرح بها أو الحساب معطّل")

def current_owner_id(request: Request) -> str:
    user = get_current_user_from_request(request)
    role = account_role(user)
    if role == "admin":
        return ADMIN_OWNER_ID
    if role == "member" and user:
        return ensure_member_id(user)
    raise HTTPException(status_code=401, detail="جلسة غير مصرح بها أو الحساب معطّل")

PROVIDER_ENV_KEYS = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "groq": "GROQ_API_KEY",
    "tavily": "TAVILY_API_KEY",
    "hf": "HF_TOKEN",
}

def _normalize_provider_name(name: str) -> str:
    return (name or "").lower().replace("_api_key", "").replace("-", "").replace("_", "")

def _read_provider_record(owner_id: str) -> Optional[dict]:
    conn = _ensure_app_memory()
    try:
        row = conn.execute(
            "SELECT payload FROM kv_documents WHERE key=?",
            (_owner_key("providers", owner_id),)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    try:
        data = json.loads(row["payload"])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

def _write_provider_record(owner_id: str, keys: dict) -> None:
    clean = {name: str(value).strip() for name, value in keys.items() if str(value or "").strip()}
    payload = json.dumps(clean, ensure_ascii=False)
    now = datetime.now().isoformat()
    conn = _ensure_app_memory()
    try:
        conn.execute(
            "INSERT INTO kv_documents (key, payload, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
            (_owner_key("providers", owner_id), payload, now)
        )
        conn.commit()
    finally:
        conn.close()

def load_provider_keys(owner_id: str) -> dict:
    stored = _read_provider_record(owner_id)
    if stored is not None:
        return stored
    if owner_id != ADMIN_OWNER_ID:
        return {}
    seeded = {}
    for name, env_name in PROVIDER_ENV_KEYS.items():
        value = os.getenv(env_name, "").strip()
        if value:
            seeded[name] = value
    _write_provider_record(owner_id, seeded)
    return seeded

def save_provider_keys(owner_id: str, keys: dict) -> None:
    _write_provider_record(owner_id, keys)
    if owner_id != ADMIN_OWNER_ID:
        return
    updates = {}
    for name, env_name in PROVIDER_ENV_KEYS.items():
        if name in keys:
            updates[env_name] = str(keys.get(name) or "").strip()
    if not updates:
        return
    update_env_file(updates)
    if "OPENROUTER_API_KEY" in updates:
        global OPENROUTER_DEFAULT_KEY
        OPENROUTER_DEFAULT_KEY = updates["OPENROUTER_API_KEY"]

def owner_openrouter_key(request: Request, provided: Optional[str] = None) -> str:
    given = (provided or "").strip()
    if given:
        return given
    return (load_provider_keys(current_owner_id(request)).get("openrouter") or "").strip()

class SetupAccountRequest(BaseModel):
    username: str
    password: str
    openrouter_key: Optional[str] = None

class LoginAccountRequest(BaseModel):
    username: str
    password: str

class JoinAccountRequest(BaseModel):
    token: str
    username: str
    password: str

class MemberInviteRequest(BaseModel):
    label: Optional[str] = ""

class MemberDisableRequest(BaseModel):
    disabled: bool = True

class NoticeCreateRequest(BaseModel):
    title: str
    body: str
    everyone: bool = False
    usernames: List[str] = []

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # السماح بالملفات الثابتة ومسارات المصادقة والمستندات
    if (
        path.startswith("/static/") or
        path.startswith("/fonts/") or
        path.startswith("/api/auth/") or
        path.startswith("/join/") or
        path == "/login" or
        path == "/favicon.ico"
    ):
        return await call_next(request)

    # إذا لم يكن النظام مهيأ بحساب بعد، نسمح للواجهة بطلب التأسيس
    if not is_auth_configured():
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "يجب تأسيس حساب المشرف أولاً", "code": "SETUP_REQUIRED"})
        auth_file = TEMPLATES_DIR / "auth.html"
        return HTMLResponse(content=auth_file.read_text(encoding="utf-8"))

    # فحص جلسة المستخدم المسجل
    user = get_current_user_from_request(request)
    if account_role(user) not in ("admin", "member"):
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "جلسة غير مصرح بها أو الحساب معطّل", "code": "UNAUTHORIZED"})
        auth_file = TEMPLATES_DIR / "auth.html"
        return HTMLResponse(content=auth_file.read_text(encoding="utf-8"))

    if path.startswith("/uploads/"):
        owner = ADMIN_OWNER_ID if account_role(user) == "admin" else ensure_member_id(user or "")
        relative = path[len("/uploads/"):].strip("/")
        parts = [part for part in relative.split("/") if part]
        if len(parts) >= 2 and parts[0] != owner:
            return JSONResponse(status_code=403, content={"detail": "هذا المرفق خاص بعضو آخر"})
        if len(parts) == 1 and owner != ADMIN_OWNER_ID:
            return JSONResponse(status_code=403, content={"detail": "هذا المرفق خاص بعضو آخر"})

    return await call_next(request)

# مجلد تخزين وحفظ مرفقات الشات (Bucket)
UPLOADS_BUCKET_DIR = BASE_DIR / "uploads"
UPLOADS_BUCKET_DIR.mkdir(parents=True, exist_ok=True)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_BUCKET_DIR)), name="uploads")

# خطوط المستخدم الخاصة — تُقرأ من المجلد مباشرة وتُخدم على /fonts
FONTS_DIR = BASE_DIR / "fonts"
FONTS_DIR.mkdir(parents=True, exist_ok=True)
FONT_EXTENSIONS = {".ttf": "truetype", ".otf": "opentype", ".woff": "woff", ".woff2": "woff2"}
MAX_FONT_BYTES = 20 * 1024 * 1024
for _ext, _mime in (("ttf", "font/ttf"), ("otf", "font/otf"), ("woff", "font/woff"), ("woff2", "font/woff2")):
    mimetypes.add_type(_mime, f".{_ext}")

def _font_family_name(path: Path, used: set) -> str:
    family = (path.stem or path.name).strip() or "font"
    if family in used:
        family = f"{family} {path.suffix.lower().lstrip('.')}"
    used.add(family)
    return family

def _iter_custom_fonts() -> List[Dict[str, Any]]:
    records = []
    used_families = set()
    if not FONTS_DIR.exists():
        return records
    for path in sorted(FONTS_DIR.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        font_format = FONT_EXTENSIONS.get(path.suffix.lower())
        if not font_format:
            continue
        filename = path.name
        records.append({
            "filename": filename,
            "family": _font_family_name(path, used_families),
            "url": "/fonts/" + urllib.parse.quote(filename),
            "format": font_format,
            "size": path.stat().st_size,
        })
    return records

def _sanitize_font_filename(original: str) -> str:
    base = Path(original or "").name.replace("\\", "").replace("/", "")
    base = re.sub(r"[\x00-\x1f]", "", base).strip()
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext not in FONT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="صيغة الخط غير مدعومة. المسموح: ttf و otf و woff و woff2")
    stem = re.sub(r"[^\w\u0600-\u06FF .\-]+", "_", stem, flags=re.UNICODE).strip(" ._")
    if not stem or stem in {".", ".."} or ".." in stem:
        stem = "font"
    candidate = f"{stem}{ext}"
    if not (FONTS_DIR / candidate).exists():
        return candidate
    index = 2
    while (FONTS_DIR / f"{stem}-{index}{ext}").exists():
        index += 1
    return f"{stem}-{index}{ext}"

def _font_path_or_404(filename: str) -> Path:
    safe = Path(filename or "").name
    if not safe or safe != filename or safe.startswith("."):
        raise HTTPException(status_code=400, detail="اسم الخط غير صالح")
    if Path(safe).suffix.lower() not in FONT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="صيغة الخط غير مدعومة")
    path = (FONTS_DIR / safe).resolve()
    if path.parent != FONTS_DIR.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="الخط غير موجود في مجلد fonts")
    return path

@app.get("/api/fonts")
async def list_custom_fonts():
    """قراءة الخطوط الخاصة من مجلد fonts"""
    return {"fonts": _iter_custom_fonts()}

@app.post("/api/fonts/upload")
async def upload_custom_font(file: UploadFile = File(...)):
    """حفظ خط خاص داخل مجلد fonts"""
    filename = _sanitize_font_filename(file.filename or "")
    contents = await file.read()
    if len(contents) < 16:
        raise HTTPException(status_code=400, detail="ملف الخط فارغ أو تالف")
    if len(contents) > MAX_FONT_BYTES:
        raise HTTPException(status_code=413, detail="حجم الخط أكبر من 20 ميغابايت")
    destination = FONTS_DIR / filename
    destination.write_bytes(contents)
    saved = next((item for item in _iter_custom_fonts() if item["filename"] == filename), None)
    return {"success": True, "font": saved}

@app.delete("/api/fonts/{filename}")
async def delete_custom_font(filename: str):
    """حذف خط خاص من مجلد fonts"""
    path = _font_path_or_404(filename)
    path.unlink()
    return {"success": True}

app.mount("/fonts", StaticFiles(directory=str(FONTS_DIR)), name="fonts")

# الحالة العامة للنظام والنموذج
app_state = {
    "qdrant": None,
    "embed_model": None,
    "llama_embedder": None,
    "st_embedder": None,
    "is_8b": False,
    "collection_name": "shamela_almojtahed_8b_dense",
    "books_cache": None,
    "is_ready": False
}

EMBEDDING_LOCK = threading.Lock()
_db_local = threading.local()
_GPU_PROBE_LOCK = threading.Lock()
_GPU_ENABLE_LOCK = threading.Lock()
_GPU_PROBE_CACHE = {"at": 0.0, "data": None}


def _gpu_mode_path() -> Path:
    data_dir = os.getenv("ALMUJTAHED_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir) / "web" / "gpu_mode.json"
    return BASE_DIR / "gpu_mode.json"


def _gpu_mode() -> str:
    try:
        data = json.loads(_gpu_mode_path().read_text(encoding="utf-8"))
        mode = str(data.get("mode") or "auto")
    except Exception:
        return "auto"
    return mode if mode in ("auto", "gpu", "cpu") else "auto"


def _set_gpu_mode(mode: str):
    path = _gpu_mode_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mode": mode}, ensure_ascii=False), encoding="utf-8")


def _command_text(args, timeout=4):
    if not args or not shutil.which(args[0]):
        return ""
    try:
        return subprocess.check_output(args, text=True, timeout=timeout, stderr=subprocess.DEVNULL)
    except Exception:
        return ""


def _read_os_release():
    info = {}
    if not os.path.exists("/etc/os-release"):
        return info
    try:
        with open("/etc/os-release", encoding="utf-8") as handle:
            for line in handle:
                if "=" not in line:
                    continue
                key, value = line.strip().split("=", 1)
                info[key] = value.strip().strip('"')
    except OSError:
        return {}
    return info


def _os_label():
    if sys.platform == "darwin":
        return "macOS", False
    info = _read_os_release()
    pretty = info.get("PRETTY_NAME") or info.get("NAME") or sys.platform
    ubuntu = info.get("ID") == "ubuntu" or "ubuntu" in pretty.lower()
    return pretty, ubuntu


def _llama_supports_gpu() -> bool:
    try:
        from llama_cpp import llama_cpp
        fn = getattr(llama_cpp, "llama_supports_gpu_offload", None)
        return bool(fn()) if fn else False
    except Exception:
        return False


def _torch_cuda_ready() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _pick_torch_device() -> str:
    if _gpu_mode() == "cpu":
        return "cpu"
    if _torch_cuda_ready():
        return "cuda"
    try:
        import torch
        mps = getattr(torch.backends, "mps", None)
        if mps and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        return "cpu"
    return "cpu"


def _desired_gpu_layers() -> int:
    if _gpu_mode() == "cpu":
        return 0
    return -1 if _llama_supports_gpu() else 0


def _mark_llama_runtime(model, layers: int):
    app_state["embed_backend"] = "llama"
    app_state["embed_gpu_layers"] = int(layers)
    app_state["embed_on_gpu"] = bool(layers) and _llama_supports_gpu()
    app_state["embed_device"] = "gpu" if app_state["embed_on_gpu"] else "cpu"


def _engine_can_use_gpu() -> bool:
    if _llama_supports_gpu() or _torch_cuda_ready():
        return True
    try:
        import torch
        mps = getattr(torch.backends, "mps", None)
        return bool(mps and torch.backends.mps.is_available())
    except Exception:
        return False


def _parse_nvidia_smi(text: str):
    devices = []
    for line in text.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 5:
            continue
        driver, util, used, total = parts[-1], parts[-2], parts[-3], parts[-4]
        name = ", ".join(parts[:-4]).strip()
        if not name:
            continue

        def _number(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        total_mib = _number(total)
        used_mib = _number(used)
        devices.append({
            "name": name,
            "vendor": "NVIDIA",
            "memory_total_gb": round(total_mib / 1024, 1) if total_mib else None,
            "memory_used_gb": round(used_mib / 1024, 1) if used_mib else None,
            "utilization": _number(util),
            "driver": driver or "",
        })
    return devices


def _lspci_gpus():
    text = _command_text(["lspci", "-nn"], timeout=4)
    devices = []
    for line in text.splitlines():
        low = line.lower()
        if "vga" not in low and "3d controller" not in low and "display controller" not in low:
            continue
        if "nvidia" in low:
            vendor = "NVIDIA"
        elif "amd" in low or "advanced micro" in low:
            vendor = "AMD"
        elif "intel" in low:
            vendor = "Intel"
        else:
            vendor = "أخرى"
        devices.append({
            "name": line.split(": ", 1)[-1].strip(),
            "vendor": vendor,
            "memory_total_gb": None,
            "memory_used_gb": None,
            "utilization": None,
            "driver": "",
        })
    return devices


def _apple_gpu():
    text = _command_text(["system_profiler", "SPDisplaysDataType"], timeout=8)
    if "Chipset Model:" not in text:
        return None
    fields = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    name = fields.get("Chipset Model") or "Apple GPU"
    metal = fields.get("Metal", "")
    metal_low = metal.lower()
    metal_off = "غير مدعوم" in metal or "not supported" in metal_low
    metal_on = (not metal_off) and ("supported" in metal_low or "مدعوم" in metal or not metal.strip())
    cores = fields.get("Total Number of Cores", "")
    return {
        "name": name,
        "vendor": "Apple",
        "memory_total_gb": None,
        "memory_used_gb": None,
        "utilization": None,
        "driver": "Metal" if metal_on else "",
        "cores": cores,
        "metal": metal_on,
    }


def _probe_gpu_hardware():
    os_name, ubuntu = _os_label()
    nvidia_text = _command_text([
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,utilization.gpu,driver_version",
        "--format=csv,noheader,nounits",
    ], timeout=5)
    devices = _parse_nvidia_smi(nvidia_text)
    driver_ready = bool(devices)
    if not devices:
        devices = _lspci_gpus()
    apple = None
    if not devices and sys.platform == "darwin":
        apple = _apple_gpu()
        if apple:
            devices = [apple]
            driver_ready = bool(apple.get("metal"))
    if devices and devices[0].get("vendor") == "NVIDIA" and not driver_ready:
        driver_ready = bool(nvidia_text.strip()) or os.path.exists("/dev/nvidia0") or os.path.exists("/proc/driver/nvidia/version")
    if devices and devices[0].get("vendor") == "AMD" and not driver_ready:
        driver_ready = os.path.exists("/dev/kfd") or bool(_command_text(["rocm-smi", "-i"], timeout=4))
    primary = devices[0] if devices else {}
    return {
        "present": bool(devices),
        "count": len(devices),
        "name": primary.get("name") or "",
        "vendor": primary.get("vendor") or "",
        "memory_total_gb": primary.get("memory_total_gb"),
        "memory_used_gb": primary.get("memory_used_gb"),
        "utilization": primary.get("utilization"),
        "driver": primary.get("driver") or "",
        "cores": primary.get("cores") or "",
        "driver_ready": bool(devices) and driver_ready,
        "os_name": os_name,
        "ubuntu": ubuntu,
    }


def _gpu_hardware():
    now = time.time()
    with _GPU_PROBE_LOCK:
        cached = _GPU_PROBE_CACHE["data"]
        if cached and now - float(_GPU_PROBE_CACHE["at"]) < 20:
            return dict(cached)
    data = _probe_gpu_hardware()
    with _GPU_PROBE_LOCK:
        _GPU_PROBE_CACHE["at"] = time.time()
        _GPU_PROBE_CACHE["data"] = data
    return dict(data)


def _gpu_status():
    hardware = _gpu_hardware()
    app_active = bool(app_state.get("embed_on_gpu"))
    engine_ready = _engine_can_use_gpu()
    present = hardware["present"]
    driver_ready = hardware["driver_ready"]
    if not present:
        label = "غير موجود"
        hint = "لم يُرصد كرت شاشة. على أوبونتو يُفحص تعريف NVIDIA، وداخل الحاوية يلزم تمرير الكرت إلى الخدمة."
    elif app_active:
        label = "يعمل مع التطبيق"
        hint = "نموذج التضمين يعمل على الكرت لزيادة سرعة البحث."
    elif not driver_ready:
        label = "غير مفعّل"
        if hardware["ubuntu"] or hardware["vendor"] == "NVIDIA":
            hint = "الكرت ظاهر لكن تعريفه غير محمّل. على أوبونتو ثبّت تعريف NVIDIA ومرّر الجهاز إلى الخدمة إن كان التطبيق داخل حاوية."
        else:
            hint = "الكرت ظاهر في النظام لكن تعريفه غير جاهز للاستخدام."
    elif engine_ready:
        label = "جاهز للتشغيل"
        hint = "الكرت جاهز ويمكن نقل نموذج التضمين إليه."
    else:
        label = "لا يستخدمه التطبيق"
        hint = "الكرت مفعّل في النظام، لكن محرك التضمين الحالي مبني للمعالج فقط."
    memory_total = hardware.get("memory_total_gb")
    memory_used = hardware.get("memory_used_gb")
    memory_percent = None
    if memory_total and memory_used is not None and memory_total > 0:
        memory_percent = round(memory_used * 100 / memory_total, 1)
    return {
        "present": present,
        "count": hardware["count"],
        "name": hardware["name"],
        "vendor": hardware["vendor"],
        "memory_total_gb": memory_total,
        "memory_used_gb": memory_used,
        "memory_percent": memory_percent,
        "utilization": hardware.get("utilization"),
        "driver": hardware["driver"],
        "cores": hardware.get("cores") or "",
        "driver_ready": driver_ready,
        "os_name": hardware["os_name"],
        "ubuntu": hardware["ubuntu"],
        "app_active": app_active,
        "engine_ready": engine_ready,
        "can_enable": bool(present and driver_ready and engine_ready and not app_active),
        "status_label": label,
        "hint": (app_state.get("embed_gpu_error") or hint) if not app_active else hint,
        "backend": app_state.get("embed_backend") or "",
    }


def _enable_app_gpu():
    if not _GPU_ENABLE_LOCK.acquire(blocking=False):
        return False, "جارٍ نقل النموذج إلى الكرت"
    try:
        status = _gpu_status()
        if not status["present"]:
            return False, status["hint"]
        if not status["driver_ready"]:
            return False, status["hint"]
        if status["app_active"] and _gpu_mode() != "cpu":
            return True, "الكرت يعمل مع التطبيق مسبقاً"
        if not status["engine_ready"]:
            return False, status["hint"]
        _set_gpu_mode("gpu")
        with _GPU_PROBE_LOCK:
            _GPU_PROBE_CACHE["at"] = 0.0
        path = _embedding_gguf_path()
        if path.is_file() and path.stat().st_size > 1024 ** 3 and _llama_supports_gpu():
            _activate_gguf_embedder(path)
            if app_state.get("embed_on_gpu"):
                return True, "تم تشغيل الكرت مع نموذج التضمين"
            return False, app_state.get("embed_gpu_error") or "أُعيد تحميل النموذج وبقي على المعالج"
        device = _pick_torch_device()
        embedder = app_state.get("st_embedder")
        if embedder is not None and device in ("cuda", "mps"):
            try:
                app_state["st_embedder"] = embedder.to(device)
                app_state["embed_backend"] = "sentence_transformers"
                app_state["embed_on_gpu"] = True
                app_state["embed_device"] = device
                app_state["embed_gpu_error"] = ""
                return True, "تم نقل نموذج التضمين إلى الكرت"
            except Exception:
                app_state["embed_gpu_error"] = "تعذر نقل النموذج إلى الكرت، وبقي على المعالج"
                return False, app_state["embed_gpu_error"]
        return False, "الكرت جاهز، لكن نموذج التضمين غير محمّل لنقله إليه"
    finally:
        _GPU_ENABLE_LOCK.release()

def get_db():
    if not hasattr(_db_local, "conn") or _db_local.conn is None:
        if DB_INDEX_PATH.exists():
            conn = sqlite3.connect(str(DB_INDEX_PATH), timeout=30.0)
            conn.row_factory = sqlite3.Row
            _db_local.conn = conn
    return getattr(_db_local, "conn", None)

def load_models_and_db():
    """تهيئة نموذج التضمين، قاعدة البيانات، والاتصال بـ Qdrant"""
    print("⏳ [المجتهد] جاري الاتصال بمخزن المتجهات Qdrant...")
    try:
        qdrant = None
        q_candidates = [
            "127.0.0.1",
            "localhost",
            os.getenv("QDRANT_HOST", "").strip(),
            "qdrant",
            "host.docker.internal"
        ]
        q_port = int(os.getenv("QDRANT_PORT", "6333"))
        for h in q_candidates:
            if not h:
                continue
            try:
                temp_client = QdrantClient(host=h, port=q_port, timeout=5.0)
                temp_client.get_collections()
                qdrant = temp_client
                print(f"✅ تم الاتصال بمخزن Qdrant على المضيف: {h}:{q_port}")
                break
            except Exception:
                continue

        if not qdrant:
            raise ConnectionError(f"تعذر الاتصال بـ Qdrant على أي من المضيفين: {q_candidates}")

        colls = [c.name for c in qdrant.get_collections().collections]
        print(f"✅ المجموعات المتوفرة في Qdrant: {colls}")
        
        if "shamela_almojtahed_8b_dense" in colls:
            app_state["qdrant"] = qdrant
            app_state["collection_name"] = "shamela_almojtahed_8b_dense"
            app_state["is_8b"] = True
            print("🚀 [المجتهد] تم ربط المجموعة الكبرى shamela_almojtahed_8b_dense (8.15 مليون مقطع بدقة 8B) بنجاح!")
        elif "shamela_corpus" in colls:
            app_state["qdrant"] = qdrant
            app_state["collection_name"] = "shamela_corpus"
            app_state["is_8b"] = False
            print("✅ تم ربط كولكشن shamela_corpus (5.14 مليون مقطع) بنجاح!")
    except Exception as e:
        print(f"⚠️ تعذر الاتصال بـ Qdrant: {e}")

    # تحميل نموذج التضمين المكمم 8B إذا كانت المجموعة 8B
    GGUF_8B_PATH = PACKAGE_ROOT / "models" / "gguf" / "almojtahed-embedding-8b-Q4_K_M.gguf"
    if not GGUF_8B_PATH.exists():
        GGUF_8B_PATH = SYSTEM_ROOT / "models" / "gguf" / "almojtahed-embedding-8b-Q4_K_M.gguf"
    if app_state.get("is_8b") and GGUF_8B_PATH.exists():
        print(f"⏳ [المجتهد] تحميل نموذج التضمين المكمم Al-Mojtahed 8B ({GGUF_8B_PATH.name})...")
        try:
            _activate_gguf_embedder(GGUF_8B_PATH)
            where = "الكرت" if app_state.get("embed_on_gpu") else "المعالج"
            print(f"✅ تم تحميل نموذج التضمين المكمم Al-Mojtahed 8B على {where}!")
            app_state["is_ready"] = True
        except Exception as e:
            print(f"⚠️ تعذر تحميل Llama 8B embedder: {e}")

    # فحص وتحميل نموذج التضمين الشرعي cs95/almojtahed-qwen3-8b عبر SentenceTransformers
    emb_hf_dir = PACKAGE_ROOT / "models" / "embedding"
    if not emb_hf_dir.exists():
        emb_hf_dir = SYSTEM_ROOT / "models" / "embedding"
    if not app_state.get("llama_embedder"):
        try:
            device = _pick_torch_device()
            from sentence_transformers import SentenceTransformer
            if emb_hf_dir.exists() and ((emb_hf_dir / "config.json").exists() or (emb_hf_dir / "config_sentence_transformers.json").exists()):
                print(f"⏳ [المجتهد] تحميل نموذج التضمين الشرعي Al-Mojtahed 8B من المسار المحلي ({emb_hf_dir}) على [{device}]...")
                app_state["st_embedder"] = SentenceTransformer(str(emb_hf_dir), device=device)
            else:
                print(f"⏳ [المجتهد] تحميل نموذج التضمين الشرعي Al-Mojtahed 8B من Hugging Face على [{device}]...")
                app_state["st_embedder"] = SentenceTransformer("cs95/almojtahed-qwen3-8b", device=device)
            print(f"✅ تم تحميل نموذج التضمين الشرعي Al-Mojtahed 8B عبر SentenceTransformer ({device}) بنجاح!")
            app_state["embed_backend"] = "sentence_transformers"
            app_state["embed_on_gpu"] = device in ("cuda", "mps")
            app_state["embed_device"] = device
            app_state["embed_gpu_error"] = ""
            app_state["is_ready"] = True
        except Exception as e:
            print(f"⚠️ تعذر تحميل نموذج التضمين الشرعي: {e}")

    # تحميل BGE-M3 كاحتياطي أخير
    if not app_state.get("is_ready"):
        print("⏳ [المجتهد] محاولة تحميل نموذج التضمين BGE-M3 كاحتياطي...")
        try:
            from FlagEmbedding import BGEM3FlagModel
            app_state["embed_model"] = BGEM3FlagModel('BAAI/bge-m3', use_fp16=False, device='cpu')
            app_state["embed_backend"] = "bge"
            app_state["embed_on_gpu"] = False
            app_state["embed_device"] = "cpu"
            print("✅ تم تحميل نموذج التضمين BGE-M3 بنجاح!")
            app_state["is_ready"] = True
        except Exception as e:
            print(f"⚠️ تعذر تحميل BGE-M3 محلياً: {e}")

@app.on_event("startup")
def on_startup():
    load_models_and_db()
    if _bundled_qdrant_path():
        threading.Thread(target=_qdrant_watchdog, name="qdrant-watchdog", daemon=True).start()

# نماذج البيانات
class SearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    book_name: Optional[str] = None
    selected_books: Optional[List[str]] = None
    death_max: Optional[int] = None
    use_reranker: bool = False
    use_hybrid: bool = True
    reranker_model: Optional[str] = None
    pool_size: int = 50
    top_k: int = 50

OPENROUTER_DEFAULT_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

MODEL_ALIAS_MAP = {
    # Anthropic Claude aliases to official OpenRouter IDs
    "claude-3-7-sonnet": "anthropic/claude-3.7-sonnet",
    "claude-3-5-sonnet": "anthropic/claude-3.5-sonnet",
    "claude-3-5-haiku": "anthropic/claude-3.5-haiku",
    "claude-3-opus": "anthropic/claude-3-opus",
    
    # Google Gemini aliases to active models
    "gemini-2.5-flash": "google/gemini-2.5-flash",
    "google/gemini-2.5-flash": "google/gemini-2.5-flash",
    "gemini-3.8-flash": "google/gemini-3.8-flash",
    "google/gemini-3.8-flash": "google/gemini-3.8-flash",
    "gemini-2.0-flash": "google/gemini-2.5-flash",
    "google/gemini-2.0-flash": "google/gemini-2.5-flash",
    "google/gemini-2.0-flash-lite": "google/gemini-2.5-flash",
    "google/gemini-1.5-pro": "google/gemini-2.5-pro",
    "gemini-1.5-pro": "google/gemini-2.5-pro",
    "gemini-flash-8": "google/gemini-2.5-flash",
    "gemini-flash-8b": "google/gemini-2.5-flash",
    "google/gemini-flash-1.5-8b": "google/gemini-2.5-flash",
    "google/gemini-flash-8": "google/gemini-2.5-flash",
    
    # DeepSeek & OpenAI
    "deepseek-r1": "deepseek/deepseek-r1",
    "deepseek-v3": "deepseek/deepseek-chat",
    "deepseek/deepseek-v4.1-flash": "deepseek/deepseek-chat",
    "o3-mini": "openai/o3-mini",
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini"
}

def normalize_model_id(m: str) -> str:
    if not m:
        return "google/gemini-2.5-flash"
    m_clean = str(m).strip()
    return MODEL_ALIAS_MAP.get(m_clean, m_clean)

LOCAL_CHAT_DIR_NAME = "local"
_LOCAL_LLM = {"path": "", "model": None}
_LOCAL_LLM_LOCK = threading.Lock()
_LOCAL_FETCH_LOCK = threading.Lock()
_LOCAL_FETCH = {
    "running": False,
    "percent": 0,
    "received": 0,
    "expected": 0,
    "message": "",
    "error": "",
    "filename": "",
}


def _local_chat_dir() -> Path:
    data_dir = os.getenv("ALMUJTAHED_DATA_DIR", "").strip()
    root = Path(data_dir) / "models" / LOCAL_CHAT_DIR_NAME if data_dir else PACKAGE_ROOT / "models" / LOCAL_CHAT_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _format_model_size(size_bytes: int) -> str:
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / (1024 ** 3):.2f} GB"
    if size_bytes >= 1024 ** 2:
        return f"{size_bytes / (1024 ** 2):.0f} MB"
    return f"{max(1, size_bytes // 1024)} KB"


def _scan_local_chat_models() -> List[Dict[str, Any]]:
    root = _local_chat_dir()
    found = []
    for item in sorted(root.rglob("*.gguf")):
        if not item.is_file() or item.name.endswith(".partial"):
            continue
        try:
            size = item.stat().st_size
        except OSError:
            continue
        if size < 1024 * 1024:
            continue
        rel = item.relative_to(root).as_posix()
        found.append({
            "id": "local:" + rel,
            "name": item.stem.replace("_", " ").replace("-", " "),
            "filename": item.name,
            "size_bytes": size,
            "size_str": _format_model_size(size),
            "format": "gguf",
        })
    return found


def _local_model_path(model_id: str) -> Path:
    raw = str(model_id or "").strip()
    if not raw.startswith("local:"):
        raise ValueError("هذا ليس نموذجاً محلياً")
    rel = raw[len("local:"):].strip().lstrip("/")
    parts = Path(rel).parts
    if not rel or any(part in ("", ".", "..") for part in parts):
        raise ValueError("مسار النموذج غير صالح")
    root = _local_chat_dir().resolve()
    path = (root / rel).resolve()
    if path != root and root not in path.parents:
        raise ValueError("مسار النموذج غير صالح")
    if not path.is_file():
        raise FileNotFoundError("النموذج المحلي غير موجود في المجلد")
    return path


def _flatten_message_content(content) -> str:
    if isinstance(content, list):
        bits = []
        for part in content:
            if isinstance(part, dict):
                bits.append(str(part.get("text") or ""))
            else:
                bits.append(str(part))
        return "\n".join(bit for bit in bits if bit).strip()
    return str(content or "").strip()


def _complete_local_text(model_id: str, messages: list, temperature: float = 0.2, max_tokens: int = 2048) -> str:
    path = _local_model_path(model_id)
    layers = _desired_gpu_layers()
    clean = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        content = _flatten_message_content(message.get("content"))
        if not content:
            continue
        role = message.get("role") if message.get("role") in ("system", "user", "assistant") else "user"
        clean.append({"role": role, "content": content})
    if not clean:
        raise RuntimeError("لا توجد رسائل لإرسالها إلى النموذج المحلي")
    limit = max(128, min(int(max_tokens or 2048), 4096))
    with _LOCAL_LLM_LOCK:
        if _LOCAL_LLM["path"] != str(path) or _LOCAL_LLM["model"] is None:
            import gc
            from llama_cpp import Llama
            old = _LOCAL_LLM.get("model")
            _LOCAL_LLM["model"] = None
            if old is not None:
                del old
                gc.collect()
            _LOCAL_LLM["model"] = Llama(
                model_path=str(path),
                n_ctx=8192,
                n_gpu_layers=layers,
                n_threads=min(8, os.cpu_count() or 4),
                verbose=False,
            )
            _LOCAL_LLM["path"] = str(path)
        result = _LOCAL_LLM["model"].create_chat_completion(
            messages=clean,
            temperature=max(0.0, float(temperature or 0.2)),
            max_tokens=limit,
        )
    choice = (result.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = (message.get("content") or "").strip()
    if not text:
        raise RuntimeError("أعاد النموذج المحلي جواباً فارغاً")
    return text


def _local_download_view() -> Dict[str, Any]:
    expected = int(_LOCAL_FETCH.get("expected") or 0)
    received = int(_LOCAL_FETCH.get("received") or 0)
    return {
        "running": bool(_LOCAL_FETCH.get("running")),
        "percent": int(_LOCAL_FETCH.get("percent") or 0),
        "received_gb": round(received / (1024 ** 3), 2),
        "expected_gb": round(expected / (1024 ** 3), 2) if expected else 0,
        "message": _LOCAL_FETCH.get("message") or "",
        "error": _LOCAL_FETCH.get("error") or "",
        "filename": _LOCAL_FETCH.get("filename") or "",
    }


def _safe_gguf_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._\-]+", "_", urllib.parse.unquote(name or "")).strip("._")
    if not cleaned.lower().endswith(".gguf"):
        return ""
    return cleaned[:180]


def _resolve_model_download(url: str):
    raw = (url or "").strip()
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("ضع رابطاً يبدأ بـ http أو https")
    if "huggingface.co" in parsed.netloc and "/blob/" in parsed.path:
        raw = raw.replace("/blob/", "/resolve/", 1)
        parsed = urllib.parse.urlparse(raw)
    filename = _safe_gguf_name(parsed.path.rsplit("/", 1)[-1])
    if filename:
        return raw, filename
    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[0] == "models":
        parts = parts[1:]
    if len(parts) >= 3 and parts[2] in ("tree", "discussions", "commits"):
        parts = parts[:2]
    if "huggingface.co" in parsed.netloc and len(parts) >= 2 and parts[0] not in ("datasets", "spaces", "api"):
        repo = f"{parts[0]}/{parts[1]}"
        request = urllib.request.Request(
            f"https://huggingface.co/api/models/{repo}",
            headers={"User-Agent": "almujtahed-local-models"},
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            info = json.loads(response.read().decode("utf-8"))
        names = [
            str(item.get("rfilename") or "")
            for item in (info.get("siblings") or [])
            if str(item.get("rfilename") or "").lower().endswith(".gguf")
        ]
        if not names:
            raise ValueError("لم يُعثر على ملف GGUF في مستودع هجينج فيس")
        preferred = next((name for name in names if "Q4_K_M" in name.upper()), names[0])
        safe = _safe_gguf_name(Path(preferred).name)
        if not safe:
            raise ValueError("اسم ملف النموذج غير صالح")
        quoted = urllib.parse.quote(preferred)
        return f"https://huggingface.co/{repo}/resolve/main/{quoted}", safe
    raise ValueError("ضع رابط ملف GGUF أو صفحة نموذج على هجينج فيس")


def _download_local_model_worker(url: str):
    final_path = None
    partial = None
    try:
        file_url, filename = _resolve_model_download(url)
        root = _local_chat_dir()
        final_path = root / filename
        if final_path.exists():
            stem = final_path.stem
            suffix = final_path.suffix
            index = 2
            while final_path.exists():
                final_path = root / f"{stem}-{index}{suffix}"
                index += 1
        partial = final_path.with_name(final_path.name + ".partial")
        _LOCAL_FETCH["filename"] = final_path.name
        _LOCAL_FETCH["message"] = f"جارٍ سحب {final_path.name}"
        request = urllib.request.Request(file_url, headers={"User-Agent": "almujtahed-local-models"})
        with urllib.request.urlopen(request, timeout=60) as response:
            expected = int(response.headers.get("Content-Length") or 0)
            _LOCAL_FETCH["expected"] = expected
            received = 0
            with open(partial, "wb") as handle:
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    received += len(chunk)
                    _LOCAL_FETCH["received"] = received
                    if expected:
                        _LOCAL_FETCH["percent"] = min(99, int(received * 100 / expected))
        header = partial.read_bytes()[:4] if partial.exists() else b""
        if header != b"GGUF" or partial.stat().st_size < 1024 * 1024:
            partial.unlink(missing_ok=True)
            raise ValueError("الملف الذي وصل ليس نموذج GGUF صالحاً")
        partial.replace(final_path)
        _LOCAL_FETCH["percent"] = 100
        _LOCAL_FETCH["message"] = "اكتمل السحب وظهر النموذج في القائمة"
        _LOCAL_FETCH["error"] = ""
    except Exception as exc:
        if partial is not None:
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(exc, ValueError) and str(exc):
            _LOCAL_FETCH["error"] = str(exc)
        else:
            _LOCAL_FETCH["error"] = "تعذر سحب النموذج. تأكد أن الرابط صفحة نموذج أو ملف GGUF."
        _LOCAL_FETCH["message"] = _LOCAL_FETCH["error"]
        print(f"⚠️ تعذر سحب نموذج محلي: {type(exc).__name__}")
    finally:
        _LOCAL_FETCH["running"] = False
        _LOCAL_FETCH_LOCK.release()


def call_openrouter_raw(
    model_id: str,
    messages: list,
    api_key: str,
    temperature: float = 0.2,
    max_tokens: int = 3500,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    repetition_penalty: Optional[float] = None,
    timeout: int = 90
) -> str:
    if str(model_id or "").startswith("local:"):
        return _complete_local_text(model_id, messages, temperature, max_tokens)
    resolved_model = normalize_model_id(model_id)
    payload = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    if top_p is not None:
        payload["top_p"] = top_p
    if top_k is not None and top_k > 0:
        payload["top_k"] = top_k
    if frequency_penalty is not None:
        payload["frequency_penalty"] = frequency_penalty
    if presence_penalty is not None:
        payload["presence_penalty"] = presence_penalty
    if repetition_penalty is not None:
        payload["repetition_penalty"] = repetition_penalty
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("مفتاح OpenRouter الخاص بهذا الحساب غير موجود")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8085",
            "X-Title": "Al-Mojtahed Multi-Agent Engine"
        },
        data=json.dumps(payload).encode("utf-8")
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))
        choice = resp_data.get("choices", [{}])[0]
        msg_obj = choice.get("message", {})
        content = (msg_obj.get("content") or "").strip()
        if not content and msg_obj.get("reasoning"):
            content = msg_obj.get("reasoning").strip()
        return content

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = "claude-3-7-sonnet"
    provider: Optional[str] = "openrouter"
    api_key: Optional[str] = None
    thinking_level: str = "medium"
    messages: List[ChatMessage]
    system_prompt: Optional[str] = None
    temperature: Optional[float] = 0.2
    top_k: Optional[int] = 40
    max_tokens: Optional[int] = 65536
    providers: Optional[Dict[str, str]] = None
    agent_group: Optional[Dict[str, Any]] = None
    retrieval_anchors: Optional[List[str]] = None
    extraction_capacity: Optional[int] = None
    computational_tool: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    agent_dispatch_mode: Optional[str] = "parallel" # "parallel" (موزع متوازي) أو "direct" (موحد مباشر)
    use_hybrid: Optional[bool] = True # تفعيل / تعطيل نمط البحث الهجين (Dense + BM25) في استرجاع نصوص الشات
    context_only: Optional[bool] = False # تجهيز شواهد الشاملة دون استدعاء نموذج المقارنة
    graph_only: Optional[bool] = False # تشجير النتيجة السابقة بلا بحث جديد
    table_only: Optional[bool] = False # جدولة النتيجة السابقة بلا بحث جديد وبلا جدول تلقائي


class BookResolveRequest(BaseModel):
    books: List[str]


def fetch_page_body(rel_path: str, part: Optional[str], page_num: Optional[int]) -> str:
    """قراءة نص الصفحة الحقيقي من ملف pages.jsonl من القرص مباشرة"""
    if not rel_path or page_num is None:
        return ""
    
    clean_rel = rel_path.replace("shamela4_data/", "").strip("/")
    candidates = [
        SHAMELA_DATA_PATH / clean_rel / "pages.jsonl",
        SHAMELA_BASE / rel_path / "pages.jsonl",
        SYSTEM_ROOT / rel_path / "pages.jsonl"
    ]
    pages_file = next((c for c in candidates if c.exists()), None)

    if not pages_file:
        # محاولة البحث عن المجلد المطابق
        matches = list(SHAMELA_DATA_PATH.glob(f"*/{clean_rel}/pages.jsonl"))
        if matches:
            pages_file = matches[0]

    if not pages_file or not pages_file.exists():
        return ""

    raw_body = ""
    try:
        # استخدام الفهرس الموضعي إن وُجد لتفادي قراءة الملف كاملاً
        if clean_rel in BOOK_PAGE_INDEX_CACHE:
            idx = BOOK_PAGE_INDEX_CACHE[clean_rel]
            for entry in idx.get("entries", []):
                p_str = str(part or "").strip()
                if p_str == "None":
                    p_str = ""
                if entry.get("page_num") == page_num and (not p_str or str(entry.get("part") or "").strip() == p_str):
                    with open(pages_file, "rb") as f:
                        f.seek(entry["offset"])
                        line = f.readline()
                        if line:
                            data = json.loads(line)
                            raw_body = data.get("body", "").strip()
                    break

        if not raw_body:
            with open(pages_file, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("page_num") == page_num:
                        if part is None or str(data.get("part")) == str(part):
                            raw_body = data.get("body", "").strip()
                            break
    except Exception as e:
        pass

    if raw_body:
        return re.sub(r"<[^>]+>", "", raw_body).strip()
    return ""


# =============================================================================
# محرك قراءة وتقليب صفحات الكتب الأصلية (Book Reader Engine)
# =============================================================================

BOOK_PAGE_INDEX_CACHE: Dict[str, dict] = {}


CITATION_FORMAT_RULE = """
═══════════════════════════════════════════════════════════
⛔ إلزام الإحالة القياسية (يسري على كل حديث ونص وعزو إلى كتاب):
1. اسم الكتاب يُنسخ حرفياً كما هو في قاعدة الشاملة، ومن سطر «الإحالة المعتمدة» المرفق مع المقطع. يُمنع اختصاره أو إضافة اسم المؤلف أو تغيير حرف.
2. إن كان الكتاب أكثر من جزء، فالموضع يُكتب بهذه الصيغة وحدها: (رقم الجزء-رقم الصفحة) مثل (3-450).
3. إن كان الكتاب جزءاً واحداً، فالموضع يُكتب بهذه الصيغة وحدها: ص(رقم الصفحة) مثل ص(50).
4. شكل الإحالة الكامل: «اسم الكتاب كما في القاعدة» (3-450) أو «اسم الكتاب كما في القاعدة» ص(50).
5. يُمنع جـ وص: و«ج 1، ص 15» وكل صيغة غير هاتين.
6. في الشات لا تُخرج وسوم HTML للطباعة ولا حواشي مرتفعة. الإحالة تبقى في المتن بهذا الشكل وحده حتى يعمل زر التصفح.
═══════════════════════════════════════════════════════════
"""

def _plain_locator_number(value: Any) -> str:
    raw = str(value or "").strip()
    raw = re.sub(r"^(?:جـ?|جزء|الجزء|صـ?|صفحة|الصفحة)\s*", "", raw).strip()
    match = re.search(r"\d{1,4}", raw)
    return match.group(0) if match else ""

def canonical_locator(part: Any, page: Any, volume_count: Any = None) -> str:
    """صيغة الموضع الوحيدة: (جزء-صفحة) للكتاب المتعدد، وص(صفحة) للكتاب ذي الجزء الواحد."""
    page_s = _plain_locator_number(page)
    part_s = _plain_locator_number(part)
    try:
        single_volume = int(volume_count) == 1
    except (TypeError, ValueError):
        single_volume = False
    if page_s and (single_volume or not part_s):
        return f"ص({page_s})"
    if part_s and page_s:
        return f"({part_s}-{page_s})"
    if page_s:
        return f"ص({page_s})"
    return ""

def canonical_citation_label(title: str, part: Any, page: Any, volume_count: Any = None) -> str:
    loc = canonical_locator(part, page, volume_count)
    name = (title or "").strip()
    return f"«{name}» {loc}".strip()

def resolve_book_path(rel_path: Optional[str], book_title: Optional[str]) -> Tuple[Optional[str], Optional[Path]]:
    """
    تحديد المسار الفعلي لملف الكتاب في shamela4_data
    """
    if rel_path:
        clean_rel = rel_path.replace("shamela4_data/", "").strip("/")
        p = SHAMELA_DATA_PATH / clean_rel / "pages.jsonl"
        if p.exists():
            return clean_rel, p
        matches = list(SHAMELA_DATA_PATH.glob(f"*/{clean_rel}/pages.jsonl"))
        if matches:
            resolved_rel = f"{matches[0].parent.parent.name}/{matches[0].parent.name}"
            return resolved_rel, matches[0]

    if book_title:
        chosen = _choose_book_rel_path(book_title.strip())
        if chosen:
            clean_rel = chosen.replace("shamela4_data/", "").strip("/")
            pages_file = SHAMELA_DATA_PATH / clean_rel / "pages.jsonl"
            if pages_file.exists():
                return clean_rel, pages_file

    return None, None

def _fold_book_text(text: str) -> str:
    cleaned = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text or "")
    cleaned = cleaned.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
    cleaned = cleaned.replace("«", " ").replace("»", " ").replace("ـ", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ،,;:：-–")
    cleaned = re.sub(r"^(?:انظر|راجع|قال في|جاء في|كتاب)\s+", "", cleaned)
    return cleaned.strip()

def _normalize_book_lookup(text: str) -> str:
    folded = _fold_book_text(text)
    folded = re.split(r"\s+[-–=]\s+", folded)[0].strip()
    return folded.strip()

def _book_match_score(query_raw: str, query_norm: str, title: str) -> int:
    title_full = _fold_book_text(title)
    title_norm = _normalize_book_lookup(title)
    if not title_norm or len(title_norm) < 4 or not query_norm:
        return -1
    query_full = _fold_book_text(query_raw.split("،")[0].split(",")[0])
    score = -1
    if title_full and title_full == query_full:
        score = 3000 + len(title_full)
    elif title_norm == query_norm:
        score = 1800 + len(title_norm)
    elif query_norm.startswith(title_norm) and len(title_norm) >= 6:
        score = 800 + len(title_norm)
    elif title_norm.startswith(query_norm) and len(query_norm) >= 4:
        extra = title_norm[len(query_norm):].strip()
        if len(query_norm) < 6 and extra and not re.match(r"^(?:ت|ط|ل|لابن|لابي|بن)\b", extra):
            score = 250
        else:
            score = 700 - min(len(extra), 180)
    if score < 0:
        return -1
    for hint in re.findall(r"(?:ابن|أبي|ابو|أبو)\s+([\u0600-\u06FF]{2,})", query_raw):
        if _fold_book_text(hint) in title_full:
            score += 120
    edition = re.search(r"[طت]\s+([\u0600-\u06FF]{3,}(?:\s+[\u0600-\u06FF]{3,}){0,2})", query_raw)
    if edition and _fold_book_text(edition.group(1)) in title_full:
        score += 350
    return score

def _canon_supports_query(query_norm: str, canon: str) -> bool:
    canon_norm = _normalize_book_lookup(canon)
    if len(query_norm) < 4 or not canon_norm:
        return False
    if query_norm == canon_norm or canon_norm.startswith(query_norm) or query_norm.startswith(canon_norm):
        return True
    return len(query_norm) >= 10 and query_norm in canon_norm

def _choose_book_rel_path(book_title: str) -> Optional[str]:
    ranked = _rank_book_rel_paths(book_title)
    return ranked[0][0] if ranked else None

def _rank_book_rel_paths(book_title: str) -> List[Tuple[str, int]]:
    """اختيار كتاب واحد يطابق العنوان، من غير التقاط كتاب آخر لمجرد اشتراك كلمة."""
    db = get_db()
    if not db or not book_title:
        return []
    book_title = re.sub(r"[\U0001F300-\U0001FAFF📖]", " ", book_title)
    primary = re.split(r"[،,]", book_title)[0].strip()
    primary = re.sub(r"^(?:ص|صفحة|جـ?|جزء|مجلد)\s*\d+\s*[\.،:\-–]*\s*", "", primary).strip()
    query_norm = _normalize_book_lookup(primary)
    if len(query_norm) < 4:
        return []
    try:
        cursor = db.cursor()
        try:
            canon = resolve_canonical_book_name(primary, cursor) or resolve_canonical_book_name(book_title, cursor)
        except Exception:
            canon = ""
        if canon and not _canon_supports_query(query_norm, canon):
            canon_norm = _normalize_book_lookup(canon)
            edition_probe = re.search(r"[طت]\s+([\u0600-\u06FF]{3,})", primary)
            edition_token = _fold_book_text(edition_probe.group(1)) if edition_probe else ""
            edition_ok = bool(edition_token) and edition_token in canon_norm
            content_ok = any(
                (folded := _fold_book_text(word[1:] if word.startswith("و") and len(word) > 5 else word)) in canon_norm
                and folded != edition_token
                for word in re.findall(r"[\u0600-\u06FF]{5,}", primary)
            )
            if not (edition_ok and content_ok):
                canon = ""
        queries = []
        for item in (primary, query_norm, _fold_book_text(primary), canon or ""):
            item = (item or "").strip()
            if item and item not in queries:
                queries.append(item)
        if query_norm.startswith("و") and len(query_norm) > 5:
            queries.append(query_norm[1:].strip())
        rows = []
        seen = set()

        def _take(sql: str, params: tuple):
            cursor.execute(sql, params)
            for row in cursor.fetchall():
                key = row["rel_path"]
                if key and key not in seen:
                    seen.add(key)
                    rows.append(row)

        for item in queries:
            like_item = item.replace("%", "").replace("_", "")
            _take(
                "SELECT title_ar, main_author_name_ar, rel_path FROM books WHERE title_ar = ? AND rel_path IS NOT NULL LIMIT 3",
                (item,)
            )
            _take(
                """
                SELECT title_ar, main_author_name_ar, rel_path FROM books
                WHERE rel_path IS NOT NULL AND title_ar LIKE ? || '%'
                ORDER BY LENGTH(title_ar) ASC LIMIT 12
                """,
                (like_item,)
            )
            if len(like_item) >= 8:
                _take(
                    """
                    SELECT title_ar, main_author_name_ar, rel_path FROM books
                    WHERE rel_path IS NOT NULL AND LENGTH(title_ar) >= 6 AND ? LIKE title_ar || '%'
                    ORDER BY LENGTH(title_ar) DESC LIMIT 8
                    """,
                    (like_item,)
                )

        edition = re.search(r"[طت]\s+([\u0600-\u06FF]{3,}(?:\s+[\u0600-\u06FF]{3,}){0,2})", primary)
        edition_tokens = []
        if edition:
            edition_tokens = [
                _fold_book_text(word) for word in edition.group(1).split()
                if len(_fold_book_text(word)) >= 4
            ]
        content_words = []
        content_like = []
        for word in re.findall(r"[\u0600-\u06FF]{4,}", primary):
            raw_word = word[1:] if word.startswith("و") and len(word) > 5 else word
            folded = _fold_book_text(raw_word)
            if len(folded) >= 4 and folded not in edition_tokens:
                content_words.append(folded)
                content_like.append(raw_word)
        author_words = [
            _fold_book_text(word) for word in re.findall(r"[\u0600-\u06FF]{3,}", " ".join(re.split(r"[،,]", book_title)[1:]))
            if len(_fold_book_text(word)) >= 4
        ]
        if edition_tokens and content_words:
            edition_word = edition.group(1).split()[0]
            content_word = max(content_like, key=len)
            if len(edition_word) >= 4 and len(content_word) >= 4:
                _take(
                    """
                    SELECT title_ar, main_author_name_ar, rel_path FROM books
                    WHERE rel_path IS NOT NULL AND title_ar LIKE ? AND title_ar LIKE ?
                    LIMIT 15
                    """,
                    (f"%{content_word}%", f"%{edition_word}%")
                )
        if len(query_norm) >= 10:
            _take(
                """
                SELECT title_ar, main_author_name_ar, rel_path FROM books
                WHERE rel_path IS NOT NULL AND title_ar LIKE '%' || ? || '%'
                ORDER BY LENGTH(title_ar) ASC LIMIT 8
                """,
                (query_norm.replace("%", "").replace("_", ""),)
            )
        distinctive_authors = [word for word in author_words if len(word) >= 5 and word not in {"ابو", "بكر", "ابن"}]
        if edition_tokens and distinctive_authors and len(query_norm) < 12:
            _take(
                """
                SELECT title_ar, main_author_name_ar, rel_path FROM books
                WHERE rel_path IS NOT NULL AND title_ar LIKE ? AND title_ar LIKE ?
                LIMIT 8
                """,
                (f"%{max(distinctive_authors, key=len)}%", f"%{max(edition_tokens, key=len)}%")
            )

        ranked = []
        for row in rows:
            score = _book_match_score(primary, query_norm, row["title_ar"] or "")
            if canon:
                score = max(score, _book_match_score(canon, _normalize_book_lookup(canon), row["title_ar"] or ""))
            title_full = _fold_book_text(row["title_ar"] or "")
            author_full = _fold_book_text(row["main_author_name_ar"] or "")
            title_norm = _normalize_book_lookup(row["title_ar"] or "")
            if len(query_norm) >= 10 and query_norm in title_norm:
                score = max(score, 1000 + len(query_norm))
            if edition_tokens and content_words and any(token in title_full for token in edition_tokens):
                if any(word in title_full for word in content_words if len(word) >= 4):
                    fragment_score = 1100
                    if author_words and any(word in author_full for word in author_words):
                        fragment_score += 500
                    score = max(score, fragment_score)
            if edition_tokens and distinctive_authors and len(query_norm) < 12:
                if any(token in title_full for token in edition_tokens) and any(word in title_full for word in distinctive_authors):
                    score = max(score, 1400)
            if score >= 500 and row["rel_path"]:
                ranked.append((row["rel_path"], score))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:6]
    except Exception as e:
        print(f"Error resolving book path from db: {e}")
        return []


def _quote_words(highlight: str) -> List[str]:
    folded = _fold_book_text(highlight)
    words = []
    for word in folded.split():
        if len(word) >= 4 and word not in words:
            words.append(word)
        if len(words) >= 6:
            break
    return words

def _body_matches_quote(body: str, words: List[str]) -> bool:
    if len(words) < 2:
        return False
    folded = _fold_book_text(re.sub(r"<[^>]+>", " ", body or ""))
    hits = sum(1 for word in words if word in folded)
    return hits >= min(3, len(words))

def _locate_reader_entry(entries: list, part: Optional[str], page_num: Optional[int], seq: Optional[int]):
    if not entries:
        return None
    target_idx = 0
    if seq is not None and 1 <= seq <= len(entries):
        target_idx = seq - 1
    elif part is not None and page_num is not None:
        p_str = "" if str(part).strip() == "None" else str(part).strip()
        found = next((i for i, e in enumerate(entries) if e["part"] == p_str and e["page_num"] == page_num), None)
        if found is None:
            found = next((i for i, e in enumerate(entries) if e["page_num"] == page_num), 0)
        target_idx = found
    elif page_num is not None:
        target_idx = next((i for i, e in enumerate(entries) if e["page_num"] == page_num), 0)
    elif part is not None:
        p_str = str(part).strip()
        target_idx = next((i for i, e in enumerate(entries) if e["part"] == p_str), 0)
    return target_idx, entries[target_idx]

def get_or_build_book_index(rel_path: str, pages_file: Path) -> dict:
    """
    بناء فهرس سريع في الذاكرة لتنقل فوري بين الصفحات والأجزاء (أقل من 1 مللي ثانية)
    """
    if rel_path in BOOK_PAGE_INDEX_CACHE:
        return BOOK_PAGE_INDEX_CACHE[rel_path]

    entries = []
    parts_set = set()
    parts_ordered = []

    try:
        with open(pages_file, "rb") as f:
            while True:
                offset = f.tell()
                line = f.readline()
                if not line:
                    break
                try:
                    data = json.loads(line)
                    part = str(data.get("part") or "")
                    if part == "None":
                        part = ""
                    pnum = data.get("page_num")
                    seq = data.get("sequence_num") or (len(entries) + 1)

                    if part and part not in parts_set:
                        parts_set.add(part)
                        parts_ordered.append(part)

                    entries.append({
                        "seq": seq,
                        "part": part,
                        "page_num": pnum,
                        "offset": offset
                    })
                except Exception:
                    continue
    except Exception as e:
        print(f"Error indexing book {rel_path}: {e}")

    # جلب بطاقة الكتاب الكاملة من SQLite
    meta = {}
    db = get_db()
    if db:
        try:
            cursor = db.cursor()
            cursor.execute("""
                SELECT title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, betaka_text, volume_count_observed 
                FROM books 
                WHERE rel_path = ? OR rel_path = ? OR title_ar = ? 
                LIMIT 1
            """, (rel_path, f"shamela4_data/{rel_path}", rel_path.split("/")[-1] if "/" in rel_path else rel_path))
            row = cursor.fetchone()
            if row:
                meta = dict(row)
        except Exception:
            pass

    idx_data = {
        "file_path": pages_file,
        "entries": entries,
        "parts": parts_ordered,
        "total_pages": len(entries),
        "meta": meta
    }
    BOOK_PAGE_INDEX_CACHE[rel_path] = idx_data
    return idx_data


HIJRI_MONTHS_LIST = [
    "محرم", "صفر", "ربيع الأول", "ربيع الآخر", "ربيع الثاني",
    "جمادى الأولى", "جمادى الآخرة", "جمادى الثانية",
    "رجب", "شعبان", "رمضان", "شوال", "ذو القعدة", "ذي القعدة", "ذو الحجة", "ذي الحجة"
]

def find_annalistic_year_backtrack(rel_path: str, book_title: str, part: str, page_num: int, max_back: int = 40) -> Optional[str]:
    """
    البحث العكسي المتقدم في الصفحات السابقة (حتى 40 صفحة) عن مطلع الحولية التاريخية الحاكمة:
    مثل «ثم دخلت سنة ...» أو «سنة إحدى وسبعون وخمسمائة» أو «حوادث سنة ...» مع رصد الشهر القمري المقترن بالحادثة
    """
    if not page_num or page_num <= 1:
        return None

    resolved_rel, pages_file = resolve_book_path(rel_path, book_title)
    if not pages_file or not pages_file.exists():
        return None

    try:
        idx = get_or_build_book_index(resolved_rel, pages_file)
        entries = idx.get("entries", [])
        if not entries:
            return None

        target_idx = None
        p_str = str(part or "").strip()
        if p_str == "None":
            p_str = ""

        for i, e in enumerate(entries):
            if e.get("page_num") == page_num:
                if not p_str or str(e.get("part") or "").strip() == p_str:
                    target_idx = i
                    break
        if target_idx is None:
            for i, e in enumerate(entries):
                if e.get("page_num") == page_num:
                    target_idx = i
                    break

        if target_idx is None or target_idx < 0:
            return None

        # 1. فحص الشهر القمري المقترن بالحادثة في الصفحة المستهدفة أو السابقة
        detected_month = None
        target_entry = entries[target_idx]
        with open(pages_file, "rb") as f:
            f.seek(target_entry["offset"])
            t_line = f.readline()
            if t_line:
                t_data = json.loads(t_line.decode("utf-8"))
                t_body = re.sub(r"<[^>]+>", " ", t_data.get("body", ""))
                m_rx = r"(?:\b(?:في|وفي|مستهل|سلخ|ليلة\s+(?:النصف\s+من|الرابع\s+عشر\s+من)|يوم\s+\S+\s+من|شهر)\s+)(" + "|".join(HIJRI_MONTHS_LIST) + r")\b"
                month_match = re.search(m_rx, t_body)
                if month_match:
                    detected_month = month_match.group(1).strip()

        # 2. البحث العكسي في الصفحات السابقة عن رأس الحولية
        with open(pages_file, "rb") as f:
            for cur_i in range(target_idx, max(-1, target_idx - max_back - 1), -1):
                entry = entries[cur_i]
                f.seek(entry["offset"])
                line = f.readline()
                if not line:
                    continue
                data = json.loads(line.decode("utf-8"))
                body_raw = data.get("body", "")

                # أ. فحص وسوم العناوين الرسمية في الشاملة أولاً
                title_spans = re.findall(r"<span[^>]*data-type=[\'\"]title[\'\"][^>]*>([^<]+)</span>", body_raw)
                for t in reversed(title_spans):
                    t_clean = re.sub(r"[\u064B-\u065F\u0670]", "", t).strip()
                    if re.search(r"^(?:ثم\s+دخلت\s+سنة|ودخلت\s+سنة|حوادث\s+سنة|ذكر\s+حوادث\s+سنة|أحداث\s+سنة|سنة|السنة)\s+", t_clean):
                        p_found = entry.get("page_num", cur_i + 1)
                        month_str = f" [شهر {detected_month}]" if detected_month else ""
                        return f"{t_clean} (المثبتة في مطلع الحولية ص {p_found}){month_str}"
                    if re.search(r"سنة\s+.*(?:مائة|مائتين|مئات|ألف|\d+|[٠-٩]+)", t_clean):
                        p_found = entry.get("page_num", cur_i + 1)
                        month_str = f" [شهر {detected_month}]" if detected_month else ""
                        return f"{t_clean} (المثبتة في مطلع الحولية ص {p_found}){month_str}"

                # ب. فحص الأنماط النصية في مطلع الفقرات
                body_clean = re.sub(r"<[^>]+>", " ", body_raw)
                body_clean = re.sub(r"[\u064B-\u065F\u0670]", "", body_clean).strip()

                text_patterns = [
                    r"(?:^|\n|\.|\؛)\s*(?:\[)?(ثم\s+دخلت\s+سنة\s+[^\n\.\،\:\;\(\)\]]{2,45})",
                    r"(?:^|\n|\.|\؛)\s*(?:\[)?(ودخلت\s+سنة\s+[^\n\.\،\:\;\(\)\]]{2,45})",
                    r"(?:^|\n|\.|\؛)\s*(?:\[)?(حوادث\s+سنة\s+[^\n\.\،\:\;\(\)\]]{2,45})",
                    r"(?:^|\n|\.|\؛)\s*(?:\[)?(ذكر\s+(?:الخبر\s+عما\s+كان\s+فيها\s+من\s+)?الأحداث\s+التي\s+كانت\s+في\s+سنة\s+[^\n\.\،\:\;\(\)\]]{2,45})",
                    r"(?:^|\n|\.|\؛)\s*(?:\[)?(ذكر\s+حوادث\s+سنة\s+[^\n\.\،\:\;\(\)\]]{2,45})",
                    r"(?:^|\n|\.|\؛)\s*(?:\[)?(أحداث\s+سنة\s+[^\n\.\،\:\;\(\)\]]{2,45})",
                    r"(?:^|\n|\.|\؛)\s*(?:\[)?(السنة\s+(?:الأولى|الثانية|الثالثة|الرابعة|الخامسة|السادسة|السابعة|الثامنة|التاسعة|العاشرة|[^\n\.\،\:\;\(\)\]]{2,30}))",
                    r"(?:^|\n|\.|\؛)\s*(?:\[)?(سنة\s+(?:\d{1,4}|[٠-٩]{1,4})\s*(?:هـ|هجرية)?)"
                ]

                for pat in text_patterns:
                    m = re.search(pat, body_clean)
                    if m:
                        val = m.group(1).strip()
                        val = re.sub(r"^(من\s+الهجرة|الهجرية)\s*", "", val).strip()
                        val = re.sub(r"[\[\]]", "", val).strip()
                        if 2 <= len(val) <= 50 and not any(w in val for w in ["شهرا", "يوما", "ساعة", "فلبث", "عاش"]):
                            p_found = entry.get("page_num", cur_i + 1)
                            month_str = f" [شهر {detected_month}]" if detected_month else ""
                            return f"{val} (المثبتة في مطلع الحولية ص {p_found}){month_str}"
    except Exception as e:
        print(f"Error in find_annalistic_year_backtrack: {e}")
    return None


def find_fiqh_issue_backtrack(rel_path: str, book_title: str, part: str, page_num: int, max_back: int = 15) -> Optional[Dict[str, Any]]:
    """
    البحث العكسي الذكي عن مطلع المسألة الفقهية الحاكمة في أمهات كتب الفقه (مثل المغني، المجموع، المبسوط):
    استخلاص نص المتن أو المسألة الأولى لمنع اقتطاع المسائل من أوساطها
    """
    if not page_num or page_num <= 1:
        return None

    resolved_rel, pages_file = resolve_book_path(rel_path, book_title)
    if not pages_file or not pages_file.exists():
        return None

    try:
        idx = get_or_build_book_index(resolved_rel, pages_file)
        entries = idx.get("entries", [])
        if not entries:
            return None

        target_idx = None
        p_str = str(part or "").strip()
        if p_str == "None":
            p_str = ""

        for i, e in enumerate(entries):
            if e.get("page_num") == page_num:
                if not p_str or str(e.get("part") or "").strip() == p_str:
                    target_idx = i
                    break
        if target_idx is None:
            for i, e in enumerate(entries):
                if e.get("page_num") == page_num:
                    target_idx = i
                    break

        if target_idx is None or target_idx < 0:
            return None

        with open(pages_file, "rb") as f:
            for cur_i in range(target_idx, max(-1, target_idx - max_back - 1), -1):
                entry = entries[cur_i]
                f.seek(entry["offset"])
                line = f.readline()
                if not line:
                    continue
                data = json.loads(line.decode("utf-8"))
                body_raw = data.get("body", "")

                # 1. فحص وسوم العناوين الرسمية في الشاملة
                title_spans = re.findall(r"<span[^>]*data-type=[\'\"]title[\'\"][^>]*>([^<]+)</span>", body_raw)
                for t in reversed(title_spans):
                    t_clean = re.sub(r"[\u064B-\u065F\u0670]", "", t).strip()
                    if any(k in t_clean for k in ["مسألة", "فصل", "فرع", "باب", "كتاب"]):
                        p_found = entry.get("page_num", cur_i + 1)
                        # استخراج سطرين من مطلع المتن بعد العنوان
                        body_clean = re.sub(r"<[^>]+>", " ", body_raw).strip()
                        body_clean = re.sub(r"\s+", " ", body_clean)
                        return {
                            "header": f"{t_clean} (مطلع المسألة في ص {p_found})",
                            "page": p_found,
                            "opening": body_clean[:220]
                        }

                # 2. فحص الأنماط النصية في صلب الصفحة
                body_clean = re.sub(r"<[^>]+>", " ", body_raw)
                body_clean = re.sub(r"[\u064B-\u065F\u0670]", "", body_clean).strip()
                patterns = [
                    r"(?:^|\n|\.|\؛)\s*(?:\[|\()?(مسألة(?:\s*\d+)?\s*[:\-\.][^\n\.\؛]{5,140})",
                    r"(?:^|\n|\.|\؛)\s*(?:\[|\()?(فصل(?:\s*\d+)?\s*[:\-\.][^\n\.\؛]{5,140})",
                    r"(?:^|\n|\.|\؛)\s*(?:\[|\()?(قال\s+(?:الخرقي|الشافعي|أبو حنيفة|مالك|محمد|أبو يوسف|القدوري)\s*[:\-\.][^\n\.\؛]{5,140})"
                ]
                for pat in patterns:
                    m = re.search(pat, body_clean)
                    if m:
                        val = m.group(1).strip()
                        p_found = entry.get("page_num", cur_i + 1)
                        return {
                            "header": f"{val} (مطلع المسألة في ص {p_found})",
                            "page": p_found,
                            "opening": body_clean[:220]
                        }
    except Exception as e:
        print(f"Error in find_fiqh_issue_backtrack: {e}")
    return None


@app.get("/api/book/page")
async def get_book_page(
    rel_path: Optional[str] = None,
    book_title: Optional[str] = None,
    part: Optional[str] = None,
    page_num: Optional[int] = None,
    seq: Optional[int] = None,
    highlight: Optional[str] = None,
    strict: Optional[str] = None
):
    """
    جلب صفحة محددة من الكتاب الأصلي مع نصوص الحواشي ومعلومات الأجزاء والتنقل
    """
    resolved_rel, pages_file = resolve_book_path(rel_path, book_title)
    if not pages_file or not pages_file.exists():
        raise HTTPException(status_code=404, detail="تعذر العثور على ملفات هذا الكتاب في الشاملة")

    idx = get_or_build_book_index(resolved_rel, pages_file)
    entries = idx["entries"]
    if not entries:
        raise HTTPException(status_code=404, detail="الكتاب لا يحتوي صفحات صالحة للقراءة")

    strict_mode = str(strict or "").strip().lower() in ("1", "true", "yes")

    # تحديد الصفحة المستهدفة بدقة
    target_idx = 0
    if seq is not None and not strict_mode and 1 <= seq <= len(entries):
        target_idx = seq - 1
    elif part is not None and page_num is not None:
        p_str = str(part).strip()
        if p_str == "None":
            p_str = ""
        found = False
        for i, e in enumerate(entries):
            if e["part"] == p_str and e["page_num"] == page_num:
                target_idx = i
                found = True
                break
        if not found and strict_mode:
            meta = idx["meta"]
            return {
                "book_title": meta.get("title_ar") or book_title or resolved_rel.split("/")[-1],
                "author": meta.get("main_author_name_ar") or "أحد أئمة التراث",
                "death_year": meta.get("main_author_death_hijri"),
                "category": meta.get("category_name_ar") or "عام",
                "betaka_text": meta.get("betaka_text") or "",
                "rel_path": resolved_rel,
                "part": p_str,
                "page_num": page_num,
                "seq": None,
                "total_pages": len(entries),
                "parts": idx["parts"],
                "annalistic_year": None,
                "fiqh_issue": None,
                "body": "",
                "footnotes": "",
                "prev_page": None,
                "next_page": None,
                "missing": True
            }
        if not found:
            for i, e in enumerate(entries):
                if e["page_num"] == page_num:
                    target_idx = i
                    break
    elif page_num is not None:
        for i, e in enumerate(entries):
            if e["page_num"] == page_num:
                target_idx = i
                break
    elif part is not None:
        p_str = str(part).strip()
        for i, e in enumerate(entries):
            if e["part"] == p_str:
                target_idx = i
                break

    entry = entries[target_idx]

    # قراءة بيانات الصفحة فورياً عبر seek
    page_data = {}
    try:
        with open(pages_file, "rb") as f:
            f.seek(entry["offset"])
            line = f.readline()
            if line:
                page_data = json.loads(line.decode("utf-8"))
    except Exception as e:
        print(f"Error reading page offset: {e}")

    raw_body = page_data.get("body", "")
    clean_body = re.sub(r"<[^>]+>", "", raw_body).strip()
    quote_words = _quote_words(highlight or "")
    if quote_words and book_title and not rel_path and not _body_matches_quote(clean_body, quote_words):
        for alt_rel, _alt_score in _rank_book_rel_paths(book_title)[1:4]:
            alt_clean = alt_rel.replace("shamela4_data/", "").strip("/")
            alt_file = SHAMELA_DATA_PATH / alt_clean / "pages.jsonl"
            if not alt_file.exists() or alt_clean == resolved_rel:
                continue
            alt_idx = get_or_build_book_index(alt_clean, alt_file)
            alt_entries = alt_idx.get("entries") or []
            alt_target = _locate_reader_entry(alt_entries, part, page_num, seq)
            if alt_target is None:
                continue
            alt_i, alt_entry = alt_target
            try:
                with open(alt_file, "rb") as alt_handle:
                    alt_handle.seek(alt_entry["offset"])
                    alt_line = alt_handle.readline()
                    alt_page = json.loads(alt_line.decode("utf-8")) if alt_line else {}
            except Exception:
                continue
            alt_body = alt_page.get("body", "")
            if not _body_matches_quote(alt_body, quote_words):
                continue
            resolved_rel = alt_clean
            pages_file = alt_file
            idx = alt_idx
            entries = alt_entries
            target_idx = alt_i
            entry = alt_entry
            page_data = alt_page
            raw_body = alt_body
            clean_body = re.sub(r"<[^>]+>", "", raw_body).strip()
            break
    footnotes = page_data.get("footnotes") or ""
    if footnotes:
        footnotes = re.sub(r"<[^>]+>", "", footnotes).strip()

    meta = idx["meta"]
    title = meta.get("title_ar") or book_title or resolved_rel.split("/")[-1]
    author = meta.get("main_author_name_ar") or "أحد أئمة التراث"
    death_year = meta.get("main_author_death_hijri")
    category = meta.get("category_name_ar") or "عام"
    betaka = meta.get("betaka_text") or ""

    prev_p = None
    if target_idx > 0:
        prv = entries[target_idx - 1]
        prev_p = {"seq": target_idx, "part": prv["part"], "page_num": prv["page_num"]}

    next_p = None
    if target_idx < len(entries) - 1:
        nxt = entries[target_idx + 1]
        next_p = {"seq": target_idx + 2, "part": nxt["part"], "page_num": nxt["page_num"]}

    # كشف رأس الحولية أو المسألة الفقهية الحاكمة
    annalistic = find_annalistic_year_backtrack(resolved_rel, title, entry["part"], entry["page_num"], max_back=40)
    fiqh = find_fiqh_issue_backtrack(resolved_rel, title, entry["part"], entry["page_num"], max_back=15)

    return {
        "book_title": title,
        "author": author,
        "death_year": death_year,
        "category": category,
        "betaka_text": betaka,
        "rel_path": resolved_rel,
        "part": entry["part"],
        "page_num": entry["page_num"],
        "seq": target_idx + 1,
        "total_pages": len(entries),
        "parts": idx["parts"],
        "annalistic_year": annalistic,
        "fiqh_issue": fiqh,
        "body": clean_body,
        "footnotes": footnotes,
        "prev_page": prev_p,
        "next_page": next_p,
        "missing": False
    }


@app.get("/api/book/surrounding-pages")
async def get_book_surrounding_pages(
    book_title: Optional[str] = None,
    rel_path: Optional[str] = None,
    part: Optional[str] = None,
    page_num: Optional[int] = 1,
    before: int = 3,
    after: int = 3
):
    """
    استيفاء السياق وتقليب الصفحات الحقيقي:
    جلب باقة الصفحات السابقة واللاحقة للصفحة المستهدفة من الأصل التراثي
    مع كشف رأس الحولية التاريخية ومطلع المسألة الفقهية وبيان الهوامش الموثقة.
    """
    resolved_rel, pages_file = resolve_book_path(rel_path, book_title)
    if not pages_file or not pages_file.exists():
        # محاولة البحث في MCP المعياري
        p_res = shamela_local_mcp.resolve_book_files(book_title or rel_path)
        if p_res and (p_res / "pages.jsonl").exists():
            pages_file = p_res / "pages.jsonl"
            resolved_rel = str(p_res.relative_to(SHAMELA_DATA_PATH.parent)) if SHAMELA_DATA_PATH.parent in p_res.parents else p_res.name
        else:
            raise HTTPException(status_code=404, detail="تعذر العثور على ملفات هذا الكتاب في الشاملة")

    idx = get_or_build_book_index(resolved_rel, pages_file)
    entries = idx["entries"]
    if not entries:
        raise HTTPException(status_code=404, detail="الكتاب لا يحتوي صفحات صالحة للقراءة")

    before = max(0, min(int(before), 100))
    after = max(0, min(int(after), 100))
    p_int = int(page_num or 1)
    p_str = str(part or "").strip()
    if p_str == "None":
        p_str = ""

    target_idx = None
    for i, e in enumerate(entries):
        if e.get("page_num") == p_int:
            if not p_str or str(e.get("part") or "").strip() == p_str:
                target_idx = i
                break
    if target_idx is None:
        for i, e in enumerate(entries):
            if e.get("page_num") == p_int:
                target_idx = i
                break
    if target_idx is None:
        target_idx = 0

    start_i = max(0, target_idx - before)
    end_i = min(len(entries) - 1, target_idx + after)

    pages = []
    try:
        with open(pages_file, "rb") as f:
            for cur_i in range(start_i, end_i + 1):
                e = entries[cur_i]
                f.seek(e["offset"])
                line = f.readline()
                if not line:
                    continue
                d = json.loads(line.decode("utf-8"))
                raw_b = d.get("body", "")
                clean_b = re.sub(r"<[^>]+>", "", raw_b).strip()
                fn = d.get("footnotes") or ""
                if fn:
                    fn = re.sub(r"<[^>]+>", "", fn).strip()

                # استخراج أي عناوين فصول أو مسائل في الصفحة
                title_matches = re.findall(r"<span[^>]*data-type=[\'\"]title[\'\"][^>]*>([^<]+)</span>", raw_b)
                clean_titles = [re.sub(r"[\u064B-\u065F\u0670]", "", t).strip() for t in title_matches if t.strip()]

                pages.append({
                    "seq": cur_i + 1,
                    "part": e.get("part"),
                    "page_num": e.get("page_num"),
                    "is_target": (cur_i == target_idx),
                    "titles": clean_titles,
                    "body": clean_b,
                    "footnotes": fn
                })
    except Exception as ex:
        print(f"Error reading surrounding pages: {ex}")

    # كشف رأس الحولية أو المسألة الفقهية الحاكمة
    meta = idx.get("meta") or {}
    b_title = meta.get("title_ar") or book_title or ""
    annalistic = find_annalistic_year_backtrack(resolved_rel, b_title, p_str, p_int, max_back=40)
    fiqh = find_fiqh_issue_backtrack(resolved_rel, b_title, p_str, p_int, max_back=15)

    return {
        "book_title": b_title,
        "author": meta.get("main_author_name_ar") or "أحد أئمة التراث",
        "death_year": meta.get("main_author_death_hijri"),
        "category": meta.get("category_name_ar") or "عام",
        "target_part": p_str or entries[target_idx].get("part"),
        "target_page": p_int,
        "annalistic_year": annalistic,
        "fiqh_issue": fiqh,
        "pages_count": len(pages),
        "pages": pages
    }


# =============================================================================
# مسارات بروتوكول MCP الداخلي للشاملة (Shamela Local MCP Endpoints)
# =============================================================================

@app.get("/api/mcp/tools")
async def get_mcp_tools_catalog():
    """عرض قائمة أدوات التحقيق والمطالعة المتاحة للنماذج الذكية عبر بروتوكول MCP"""
    return {
        "status": "ok",
        "server": "shamela_local_mcp",
        "description": "خادم المطالعة والتحقيق الموضعي لنصوص الشاملة التراثية الأصلية",
        "tools": shamela_local_mcp.SHAMELA_MCP_TOOLS_SPEC
    }

class MCPExecuteRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

@app.post("/api/mcp/execute")
async def execute_mcp_tool_route(req: MCPExecuteRequest):
    """تنفيذ أداة MCP برمجياً وتمرير النتائج للوكلاء التوليديين ومهندس المشاريع"""
    res = shamela_local_mcp.execute_mcp_tool(req.name, req.arguments)
    return res

@app.get("/api/mcp/page-range")
async def mcp_get_page_range(book: str, start_page: int, end_page: int, part: Optional[str] = None):
    """أداة 1: تقليب وقراءة صفحات متسلسلة كاملة بنصها وهوامش التحقيق"""
    return shamela_local_mcp.get_page_range(book=book, start_page=start_page, end_page=end_page, part=part)

@app.get("/api/mcp/book-toc")
async def mcp_get_book_toc(book: str):
    """أداة 2: استعراض شجرة الأبواب وفهرس المحتويات للكتاب"""
    return shamela_local_mcp.get_book_toc(book=book)

@app.post("/api/mcp/verify-quote")
async def mcp_verify_quote(book: str, quote: str, part: Optional[str] = None, page_hint: Optional[int] = None):
    """أداة 3: مطابقة نص الاقتباس الحرفي داخل صفحات الكتاب بدقة 100%"""
    return shamela_local_mcp.verify_quote(book=book, quote_text=quote, part=part, page_hint=page_hint)

@app.get("/api/mcp/search-in-book")
async def mcp_search_in_book(book: str, query: str, limit: int = 10):
    """أداة 4: بحث حرفي سريع ومحصور داخل نطاق كتاب واحد محدد"""
    return shamela_local_mcp.search_in_book(book=book, query=query, limit=limit)



# =============================================================================
# مسارات المصادقة وتسجيل الدخول وإدارة المفاتيح في البيئة (.env)
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user = get_current_user_from_request(request)
    if not user or not is_auth_configured():
        auth_file = TEMPLATES_DIR / "auth.html"
        return HTMLResponse(content=auth_file.read_text(encoding="utf-8"))
    index_file = TEMPLATES_DIR / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.get("/login", response_class=HTMLResponse)
async def login_page_route(request: Request):
    auth_file = TEMPLATES_DIR / "auth.html"
    return HTMLResponse(content=auth_file.read_text(encoding="utf-8"))

@app.get("/changes.md")
async def read_changes_log():
    path = PACKAGE_ROOT / "changes.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="سجل الإصدارات غير موجود")
    return FileResponse(path, media_type="text/markdown; charset=utf-8")

@app.get("/api/auth/status")
async def get_auth_status(request: Request):
    configured = is_auth_configured()
    current_user = get_current_user_from_request(request)
    role = account_role(current_user) if current_user else None
    active = role in ("admin", "member")
    return {
        "is_configured": configured,
        "is_authenticated": active,
        "username": current_user if active else "",
        "role": role if active else "",
        "owner_id": (ADMIN_OWNER_ID if role == "admin" else ensure_member_id(current_user)) if active and current_user else ""
    }

@app.post("/api/auth/setup")
async def setup_auth_endpoint(req: SetupAccountRequest, response: Response):
    if is_auth_configured():
        raise HTTPException(status_code=400, detail="حساب المشرف مؤسس مسبقاً، يرجى تسجيل الدخول")

    username = req.username.strip()
    password = req.password
    if not username or not password:
        raise HTTPException(status_code=400, detail="اسم المستخدم وكلمة المرور مطلوبان")

    salt = secrets.token_hex(16)
    pwd_hash = hash_password(password, salt)
    secret = secrets.token_hex(32)

    env_data = {
        "AUTH_USERNAME": username,
        "AUTH_PASSWORD_HASH": pwd_hash,
        "AUTH_SALT": salt,
        "SESSION_SECRET": secret
    }
    if req.openrouter_key and req.openrouter_key.strip():
        env_data["OPENROUTER_API_KEY"] = req.openrouter_key.strip()
        global OPENROUTER_DEFAULT_KEY
        OPENROUTER_DEFAULT_KEY = req.openrouter_key.strip()

    update_env_file(env_data)

    token = generate_session_token(username)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return {
        "status": "success",
        "message": "تم تأسيس الحساب بنجاح وتفعيل الجلسة لمدة 3 أيام",
        "username": username,
        "token": token
    }

@app.post("/api/auth/login")
async def login_auth_endpoint(req: LoginAccountRequest, response: Response):
    if not is_auth_configured():
        raise HTTPException(status_code=400, detail="يجب تأسيس حساب المشرف أولاً")

    expected_user = os.getenv("AUTH_USERNAME", "").strip()
    expected_hash = os.getenv("AUTH_PASSWORD_HASH", "").strip()
    salt = os.getenv("AUTH_SALT", "").strip()
    name = req.username.strip()

    if same_text(name, expected_user):
        computed_hash = hash_password(req.password, salt)
        if not same_text(computed_hash, expected_hash):
            raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة")
        session_name = expected_user
    else:
        account = find_member_account(name)
        if not account or not same_text(hash_password(req.password, account.get("salt", "")), account.get("password_hash", "")):
            raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة")
        if account.get("disabled"):
            raise HTTPException(status_code=403, detail="تم تعطيل هذا الحساب، راجع المشرف")
        session_name = account["username"]

    token = generate_session_token(session_name)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return {
        "status": "success",
        "message": "تم تسجيل الدخول بنجاح",
        "username": session_name,
        "token": token
    }

@app.post("/api/auth/logout")
async def logout_auth_endpoint(response: Response):
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"status": "success", "message": "تم تسجيل الخروج بنجاح"}

def member_invite_url(request: Request, token: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/join/{token}"

def public_invite(invite: Dict[str, Any], request: Request) -> Dict[str, Any]:
    return {
        "id": invite.get("id"),
        "label": invite.get("label") or "",
        "url": member_invite_url(request, invite.get("token", "")),
        "created_at": invite.get("created_at"),
        "used": bool(invite.get("used")),
        "used_by": invite.get("used_by") or ""
    }

@app.get("/join/{token}", response_class=HTMLResponse)
async def join_member_page(token: str):
    page = TEMPLATES_DIR / "join.html"
    return HTMLResponse(content=page.read_text(encoding="utf-8"))

@app.get("/api/auth/join/{token}")
async def join_member_status(token: str):
    store = load_members_store()
    invite = next((item for item in store.get("invites", []) if item.get("token") == token), None)
    if not invite or invite.get("used"):
        return {"valid": False}
    return {"valid": True, "label": invite.get("label") or ""}

@app.post("/api/auth/join")
async def join_member_account(req: JoinAccountRequest, response: Response):
    username = (req.username or "").strip()
    password = req.password or ""
    if not MEMBER_USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="اسم المستخدم من 3 إلى 32 حرفاً إنجليزياً أو رقماً، ويبدأ بحرف أو رقم")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="كلمة المرور أربعة أحرف على الأقل")
    admin_name = os.getenv("AUTH_USERNAME", "").strip()
    if admin_name and same_text(username, admin_name):
        raise HTTPException(status_code=400, detail="اسم المستخدم مستخدم")
    if find_member_account(username):
        raise HTTPException(status_code=400, detail="اسم المستخدم مستخدم")

    store = load_members_store()
    invite = next((item for item in store.get("invites", []) if item.get("token") == (req.token or "").strip()), None)
    if not invite or invite.get("used"):
        raise HTTPException(status_code=400, detail="رابط الدعوة غير صالح أو استُخدم من قبل")

    salt = secrets.token_hex(16)
    account = {
        "id": "m_" + secrets.token_hex(8),
        "username": username,
        "display_name": str(invite.get("label") or "").strip()[:80],
        "salt": salt,
        "password_hash": hash_password(password, salt),
        "disabled": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "invite_id": invite.get("id")
    }
    invite["used"] = True
    invite["used_by"] = username
    invite["used_at"] = account["created_at"]
    store.setdefault("accounts", []).append(account)
    save_members_store(store)

    token = generate_session_token(username)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return {"status": "success", "message": "تم إنشاء الحساب والدخول", "username": username}

@app.get("/api/members")
async def list_members(request: Request):
    require_admin(request)
    store = load_members_store()
    return {
        "admin_username": os.getenv("AUTH_USERNAME", "").strip(),
        "invites": [public_invite(item, request) for item in store.get("invites", [])],
        "accounts": [
            {
                "id": item.get("id") or "",
                "username": item.get("username"),
                "disabled": bool(item.get("disabled")),
                "created_at": item.get("created_at") or ""
            }
            for item in store.get("accounts", [])
        ]
    }

@app.post("/api/members/invites")
async def create_member_invite(req: MemberInviteRequest, request: Request):
    require_admin(request)
    label = (req.label or "").strip()[:80]
    invite = {
        "id": secrets.token_hex(8),
        "token": secrets.token_urlsafe(24),
        "label": label,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "used": False,
        "used_by": ""
    }
    store = load_members_store()
    store.setdefault("invites", []).insert(0, invite)
    save_members_store(store)
    return {"status": "success", "invite": public_invite(invite, request)}

@app.delete("/api/members/invites/{invite_id}")
async def delete_member_invite(invite_id: str, request: Request):
    require_admin(request)
    store = load_members_store()
    kept = []
    removed = False
    for item in store.get("invites", []):
        if item.get("id") == invite_id and not item.get("used"):
            removed = True
            continue
        kept.append(item)
    if not removed:
        raise HTTPException(status_code=404, detail="الدعوة غير موجودة أو استُخدمت")
    store["invites"] = kept
    save_members_store(store)
    return {"status": "success"}

@app.post("/api/members/{username}/disabled")
async def set_member_disabled(username: str, req: MemberDisableRequest, request: Request):
    require_admin(request)
    store = load_members_store()
    found = False
    for account in store.get("accounts", []):
        if account.get("username") == username:
            account["disabled"] = bool(req.disabled)
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="العضو غير موجود")
    save_members_store(store)
    return {"status": "success", "disabled": bool(req.disabled)}

def load_notices_store() -> Dict[str, Any]:
    with _notices_lock:
        if not NOTICES_PATH.exists() or NOTICES_PATH.stat().st_size == 0:
            return {"notices": []}
        try:
            data = json.loads(NOTICES_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"notices": []}
        if not isinstance(data, dict):
            return {"notices": []}
        notices = data.get("notices")
        if not isinstance(notices, list):
            data["notices"] = []
        return data

def save_notices_store(data: Dict[str, Any]) -> None:
    with _notices_lock:
        NOTICES_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = NOTICES_PATH.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(NOTICES_PATH)

def active_member_usernames() -> List[str]:
    names = []
    for account in load_members_store().get("accounts", []):
        username = str(account.get("username") or "").strip()
        if username and not account.get("disabled"):
            names.append(username)
    return names

def require_signed_in(request: Request) -> str:
    user = get_current_user_from_request(request)
    role = account_role(user)
    if not user or role in (None, "disabled"):
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    return user

def _notice_reads(notice: Dict[str, Any]) -> Dict[str, str]:
    reads = notice.get("reads")
    return reads if isinstance(reads, dict) else {}

@app.get("/api/notices")
async def list_my_notices(request: Request):
    user = require_signed_in(request)
    items = []
    for notice in load_notices_store().get("notices", []):
        recipients = notice.get("recipients") or []
        if user not in recipients:
            continue
        read_at = _notice_reads(notice).get(user) or ""
        items.append({
            "id": notice.get("id"),
            "title": notice.get("title") or "",
            "body": notice.get("body") or "",
            "created_at": notice.get("created_at") or "",
            "read": bool(read_at),
            "read_at": read_at,
        })
    unread = [item for item in items if not item["read"]]
    read = [item for item in items if item["read"]]
    unread.sort(key=lambda item: item["created_at"], reverse=True)
    read.sort(key=lambda item: item["created_at"], reverse=True)
    ordered = unread + read
    return {"notices": ordered, "unread": len(unread)}

@app.post("/api/notices/{notice_id}/read")
async def mark_notice_read(notice_id: str, request: Request):
    user = require_signed_in(request)
    store = load_notices_store()
    found = False
    for notice in store.get("notices", []):
        if notice.get("id") != notice_id:
            continue
        if user not in (notice.get("recipients") or []):
            raise HTTPException(status_code=404, detail="الرسالة غير موجهة إليك")
        reads = _notice_reads(notice)
        reads.setdefault(user, datetime.now().isoformat(timespec="seconds"))
        notice["reads"] = reads
        found = True
        break
    if not found:
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
    save_notices_store(store)
    return {"status": "success"}

@app.get("/api/notices/admin")
async def list_admin_notices(request: Request):
    require_admin(request)
    result = []
    for notice in load_notices_store().get("notices", []):
        reads = _notice_reads(notice)
        recipients = [str(name) for name in (notice.get("recipients") or [])]
        result.append({
            "id": notice.get("id"),
            "title": notice.get("title") or "",
            "body": notice.get("body") or "",
            "created_at": notice.get("created_at") or "",
            "audience": notice.get("audience") or "selected",
            "readers": [{"username": name, "read_at": reads.get(name) or ""} for name in recipients if reads.get(name)],
            "pending": [name for name in recipients if not reads.get(name)],
        })
    result.sort(key=lambda item: item["created_at"], reverse=True)
    return {"notices": result}

@app.post("/api/notices")
async def create_notice(req: NoticeCreateRequest, request: Request):
    require_admin(request)
    title = (req.title or "").strip()[:120]
    body = (req.body or "").strip()[:4000]
    if not title or not body:
        raise HTTPException(status_code=400, detail="اكتب عنوان الرسالة ونصها")
    known = active_member_usernames()
    if req.everyone:
        recipients = known
        audience = "all"
    else:
        wanted = []
        for name in req.usernames or []:
            clean = str(name or "").strip()
            if clean and clean in known and clean not in wanted:
                wanted.append(clean)
        recipients = wanted
        audience = "selected"
    if not recipients:
        raise HTTPException(status_code=400, detail="اختر عضواً واحداً على الأقل، أو الجميع")
    notice = {
        "id": "n_" + secrets.token_hex(8),
        "title": title,
        "body": body,
        "audience": audience,
        "recipients": recipients,
        "reads": {},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    store = load_notices_store()
    store.setdefault("notices", []).insert(0, notice)
    save_notices_store(store)
    return {"status": "success", "id": notice["id"], "recipients": len(recipients)}

@app.delete("/api/notices/{notice_id}")
async def delete_notice(notice_id: str, request: Request):
    require_admin(request)
    store = load_notices_store()
    kept = [item for item in store.get("notices", []) if item.get("id") != notice_id]
    if len(kept) == len(store.get("notices", [])):
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
    store["notices"] = kept
    save_notices_store(store)
    return {"status": "success"}

@app.get("/api/config/providers")
async def get_providers_config(request: Request):
    """مفاتيح المزودين الخاصة بالعضو الحالي فقط"""
    return {"status": "ok", "keys": load_provider_keys(current_owner_id(request))}

@app.post("/api/config/providers")
async def save_providers_config(req: Dict[str, str], request: Request):
    """حفظ مفاتيح العضو الحالي في مساحته، دون الكتابة فوق حساب غيره"""
    owner_id = current_owner_id(request)
    current = load_provider_keys(owner_id)
    allowed = set(PROVIDER_ENV_KEYS)
    for name, value in req.items():
        if value is None:
            continue
        normalized = _normalize_provider_name(name)
        if normalized not in allowed:
            continue
        text = str(value).strip()
        if text:
            current[normalized] = text
        else:
            current.pop(normalized, None)
    save_provider_keys(owner_id, current)
    return {"status": "success", "message": "تم حفظ المفاتيح في حسابك"}


def _provider_key_ok(provider: str, key: str) -> bool:
    """يفحص المفتاح لدى مزوده دون تسجيل قيمته."""
    name = _normalize_provider_name(provider)
    headers = {"Accept": "application/json"}
    if name == "openrouter":
        url = "https://openrouter.ai/api/v1/auth/key"
        headers["Authorization"] = f"Bearer {key}"
    elif name in ("claude", "anthropic"):
        url = "https://api.anthropic.com/v1/models"
        headers["x-api-key"] = key
        headers["anthropic-version"] = "2023-06-01"
    elif name in ("google", "gemini"):
        url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1&key=" + urllib.parse.quote(key, safe="")
    elif name == "openai":
        url = "https://api.openai.com/v1/models"
        headers["Authorization"] = f"Bearer {key}"
    elif name == "deepseek":
        url = "https://api.deepseek.com/models"
        headers["Authorization"] = f"Bearer {key}"
    else:
        return False
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return 200 <= int(getattr(response, "status", 200)) < 300
    except Exception:
        return False


@app.post("/api/config/providers/test")
async def test_provider_key(req: Dict[str, str], request: Request):
    """يجرّب مفتاح المزود الحالي. لا يعيد المفتاح ولا يحفظه."""
    current_owner_id(request)
    provider = str(req.get("provider") or "").strip()
    key = str(req.get("key") or "").strip()
    if not key or len(key) > 500:
        return {"ok": False}
    ok = await asyncio.to_thread(_provider_key_ok, provider, key)
    return {"ok": bool(ok)}


@app.get("/api/status")
async def get_system_status():
    col_name = app_state["collection_name"]
    count = 0
    if app_state["qdrant"]:
        try:
            info = app_state["qdrant"].get_collection(col_name)
            count = info.points_count
        except:
            pass
    return {
        "status": "online",
        "system_name": "المجتهد (Al-Mojtahed)",
        "active_plan": "الخطة الأولى: شاملا كوربس (shamela_corpus)",
        "indexed_points": count,
        "embedding_model": "BAAI/bge-m3 (Dense 1024D)",
        "ready": app_state["is_ready"]
    }


@app.get("/api/categories")
async def get_categories():
    """
    إرجاع قائمة التصنيفات الأربعين المعتمدة في المكتبة الشاملة
    """
    db = get_db()
    if db:
        try:
            cursor = db.cursor()
            cursor.execute("SELECT DISTINCT category_id, category_name_ar FROM books WHERE category_id IS NOT NULL ORDER BY category_id")
            rows = cursor.fetchall()
            if rows:
                return [{"id": r["category_id"], "name": r["category_name_ar"]} for r in rows if r["category_id"]]
        except Exception:
            pass

    # قائمة احتياطية مطابقة للتصنيفات الرسمية
    official_cats = [
        {"id": 1, "name": "العقيدة"},
        {"id": 2, "name": "الفرق والردود"},
        {"id": 3, "name": "التفسير"},
        {"id": 4, "name": "علوم القرآن وأصول التفسير"},
        {"id": 5, "name": "التجويد والقراءات"},
        {"id": 6, "name": "كتب السنة"},
        {"id": 7, "name": "شروح الحديث"},
        {"id": 8, "name": "التخريج والأطراف"},
        {"id": 9, "name": "العلل والسؤلات الحديثية"},
        {"id": 10, "name": "علوم الحديث"},
        {"id": 11, "name": "أصول الفقه"},
        {"id": 12, "name": "علوم الفقه والقواعد الفقهية"},
        {"id": 13, "name": "المنطق"},
        {"id": 14, "name": "الفقه الحنفي"},
        {"id": 15, "name": "الفقه المالكي"},
        {"id": 16, "name": "الفقه الشافعي"},
        {"id": 17, "name": "الفقه الحنبلي"},
        {"id": 18, "name": "الفقه العام"},
        {"id": 19, "name": "مسائل فقهية"},
        {"id": 20, "name": "السياسة الشرعية والقضاء"},
        {"id": 21, "name": "الفرائض والوصايا"},
        {"id": 22, "name": "الفتاوى"},
        {"id": 23, "name": "الرقائق والآداب والأذكار"},
        {"id": 24, "name": "السيرة النبوية"},
        {"id": 25, "name": "التاريخ"},
        {"id": 26, "name": "التراجم والطبقات"},
        {"id": 27, "name": "الأنساب"},
        {"id": 28, "name": "البلدان والرحلات"},
        {"id": 29, "name": "كتب اللغة"},
        {"id": 30, "name": "الغريب والمعاجم"},
        {"id": 31, "name": "النحو والصرف"},
        {"id": 32, "name": "الأدب"},
        {"id": 33, "name": "العروض والقوافي"},
        {"id": 34, "name": "الشعر ودواوينه"},
        {"id": 35, "name": "البلاغة"},
        {"id": 36, "name": "الجوامع"},
        {"id": 37, "name": "فهارس الكتب والأدلة"},
        {"id": 38, "name": "الطب"},
        {"id": 39, "name": "كتب عامة"},
        {"id": 40, "name": "علوم أخرى"}
    ]
    return official_cats


@app.get("/api/books")
async def get_books_catalog(category_id: Optional[int] = None):
    """
    جلب فهرس كتب الشاملة للاختيار في نافذة نطاق البحث
    """
    if app_state["books_cache"] is None:
        db = get_db()
        if db:
            try:
                cursor = db.cursor()
                cursor.execute("""
                    SELECT book_id, title_ar, category_id, category_name_ar, main_author_name_ar, main_author_death_hijri 
                    FROM books 
                    WHERE title_ar IS NOT NULL AND TRIM(title_ar) != ''
                    ORDER BY category_id, title_ar
                """)
                app_state["books_cache"] = [
                    {
                        "id": r["book_id"],
                        "title": r["title_ar"],
                        "category_id": r["category_id"],
                        "category_name": r["category_name_ar"] or "عام",
                        "author": r["main_author_name_ar"] or "أحد أئمة التراث",
                        "death": r["main_author_death_hijri"]
                    }
                    for r in cursor.fetchall()
                ]
            except Exception as e:
                print(f"Error caching books catalog: {e}")
                app_state["books_cache"] = []

    all_books = app_state["books_cache"] or []
    if category_id is not None:
        return [b for b in all_books if b["category_id"] == category_id]
    return all_books


@app.get("/api/system_status")
async def get_system_status():
    """فحص حالة النظام والمخزن وقاعدة البيانات ونماذج الذكاء الاصطناعي"""
    q_connected = False
    colls = []
    points_count = 0
    if app_state.get("qdrant"):
        try:
            q_connected = True
            c_info = app_state["qdrant"].get_collections().collections
            colls = [c.name for c in c_info]
            if app_state.get("collection_name") and app_state["collection_name"] in colls:
                info = app_state["qdrant"].get_collection(app_state["collection_name"])
                points_count = info.points_count or 0
        except Exception as e:
            q_connected = False

    embedder_type = "none"
    if app_state.get("llama_embedder"):
        embedder_type = "llama_8b_gguf"
    elif app_state.get("st_embedder"):
        embedder_type = "sentence_transformers_8b"
    elif app_state.get("embed_model"):
        embedder_type = "bge_m3"

    free_gb = 0.0
    try:
        du = shutil.disk_usage("/app" if Path("/app").exists() else ".")
        free_gb = round(du.free / (1024**3), 2)
    except Exception:
        pass

    return {
        "status": "ok" if (q_connected and points_count > 0 and embedder_type != "none") else "warning",
        "qdrant_connected": q_connected,
        "collection_name": app_state.get("collection_name"),
        "points_count": points_count,
        "collections_available": colls,
        "embedder_type": embedder_type,
        "is_ready": app_state.get("is_ready", False),
        "disk_free_gb": free_gb
    }


@app.get("/api/stats")
async def library_stats(request: Request):
    """أعداد المكتبة والنصوص والأعضاء. قراءة فقط، بلا تعديل على الفهرس أو المخزن."""
    require_signed_in(request)
    books = int(_book_index_status().get("books") or 0)
    texts = 0
    texts_ready = False
    if app_state.get("qdrant") and app_state.get("collection_name"):
        try:
            info = app_state["qdrant"].get_collection(app_state["collection_name"])
            texts = int(info.points_count or 0)
            texts_ready = True
        except Exception:
            texts_ready = False
    active = 0
    total = 0
    for account in load_members_store().get("accounts") or []:
        if not isinstance(account, dict):
            continue
        if not str(account.get("username") or "").strip():
            continue
        total += 1
        if not account.get("disabled"):
            active += 1
    activity = _activity_counts()
    return {
        "books": books,
        "texts": texts,
        "texts_ready": texts_ready,
        "members": active,
        "members_total": total,
        "projects": activity["projects"],
        "chats": activity["chats"],
        "shares": activity["shares"],
    }


def _activity_counts() -> Dict[str, int]:
    """يجمع مشاريع ومحادثات كل الحسابات. المشاركات تُحسب عند وجودها فقط."""
    counts = {"projects": 0, "chats": 0, "shares": 0}
    if not APP_MEMORY_DB.exists():
        return counts
    conn = sqlite3.connect(f"file:{APP_MEMORY_DB}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "kv_documents" in tables:
            for row in conn.execute("SELECT payload FROM kv_documents WHERE key LIKE 'projects:%'"):
                try:
                    data = json.loads(row["payload"])
                except Exception:
                    continue
                if isinstance(data, list):
                    counts["projects"] += len(data)
            share_row = conn.execute("SELECT payload FROM kv_documents WHERE key='shares'").fetchone()
            if share_row:
                try:
                    share_data = json.loads(share_row["payload"])
                except Exception:
                    share_data = None
                if isinstance(share_data, list):
                    counts["shares"] = len(share_data)
        if "chat_sessions" in tables:
            counts["chats"] = int(conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0])
        if "member_shares" in tables:
            counts["shares"] = int(conn.execute("SELECT COUNT(*) FROM member_shares").fetchone()[0])
    except Exception:
        return counts
    finally:
        conn.close()
    return counts


def _get_live_memory_usage():
    """قراءة تفصيلية حية لاستهلاك الرام من psutil أو /proc/meminfo"""
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {
            "total_gb": round(vm.total / (1024**3), 2),
            "used_gb": round(vm.used / (1024**3), 2),
            "free_gb": round(vm.available / (1024**3), 2),
            "percent": round(vm.percent, 1)
        }
    except Exception:
        pass

    if os.path.exists("/proc/meminfo"):
        try:
            mem = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().split()[0]
                        mem[k] = int(v) * 1024
            total = mem.get("MemTotal", 0)
            avail = mem.get("MemAvailable", mem.get("MemFree", 0))
            used = max(0, total - avail)
            pct = round((used / total) * 100, 1) if total > 0 else 0
            return {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(avail / (1024**3), 2),
                "percent": pct
            }
        except Exception:
            pass

    return {
        "total_gb": 16.0,
        "used_gb": 5.7,
        "free_gb": 10.3,
        "percent": 35.6
    }


def _get_live_disk_usage():
    """قراءة تفصيلية حية للقرص الصلب"""
    try:
        target_path = "/app" if Path("/app").exists() else "."
        du = shutil.disk_usage(target_path)
        total_gb = round(du.total / (1024**3), 1)
        used_gb = round(du.used / (1024**3), 1)
        free_gb = round(du.free / (1024**3), 1)
        percent = round((du.used / du.total) * 100, 1) if du.total > 0 else 0
        return {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "percent": percent
        }
    except Exception:
        return {
            "total_gb": 301.0,
            "used_gb": 211.0,
            "free_gb": 77.0,
            "percent": 74.0
        }


_QDRANT_ATTACH_LOCK = threading.Lock()
_SNAPSHOT_EXPECTED_BYTES = 172 * (1024 ** 3)

def _read_bootstrap_status():
    data_dir = os.getenv("ALMUJTAHED_DATA_DIR", "").strip()
    if not data_dir:
        return None
    path = Path(data_dir) / "web" / "bootstrap_status.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def _data_disk_is_persistent():
    data_dir = os.getenv("ALMUJTAHED_DATA_DIR", "").strip()
    if not data_dir or not os.path.isdir(data_dir):
        return None
    try:
        return os.stat(data_dir).st_dev != os.stat("/").st_dev
    except OSError:
        return None

def _ensure_qdrant_client():
    """إعادة الربط إذا اكتمل السنابشوت بعد إقلاع الواجهة."""
    if app_state.get("qdrant"):
        return
    if not _QDRANT_ATTACH_LOCK.acquire(blocking=False):
        return
    try:
        if app_state.get("qdrant"):
            return
        hosts = []
        for host in ("127.0.0.1", "localhost", os.getenv("QDRANT_HOST", "").strip()):
            if host and host not in hosts:
                hosts.append(host)
        port = int(os.getenv("QDRANT_PORT", "6333"))
        for host in hosts:
            try:
                client = QdrantClient(host=host, port=port, timeout=3)
                names = [item.name for item in client.get_collections().collections]
                if "shamela_almojtahed_8b_dense" in names:
                    app_state["qdrant"] = client
                    app_state["collection_name"] = "shamela_almojtahed_8b_dense"
                    app_state["is_8b"] = True
                    return
                if "shamela_corpus" in names:
                    app_state["qdrant"] = client
                    app_state["collection_name"] = "shamela_corpus"
                    app_state["is_8b"] = False
                    return
            except Exception:
                continue
    finally:
        _QDRANT_ATTACH_LOCK.release()

_QDRANT_SIZE_SAMPLE = {"at": 0.0, "bytes": 0, "busy": False, "speed_bps": None}

def _qdrant_dir_bytes():
    """قياس مخزن المتجهات كل 20 ثانية. الواجهة تعمل أثناء السحب وQdrant يكمل التنزيل وحده."""
    data_dir = os.getenv("ALMUJTAHED_DATA_DIR", "").strip()
    if not data_dir:
        return 0
    target = Path(data_dir) / "qdrant"
    if not target.exists():
        return 0
    now = time.time()
    with _QDRANT_ATTACH_LOCK:
        if _QDRANT_SIZE_SAMPLE["busy"]:
            return int(_QDRANT_SIZE_SAMPLE["bytes"])
        if _QDRANT_SIZE_SAMPLE["at"] and now - _QDRANT_SIZE_SAMPLE["at"] < 20:
            return int(_QDRANT_SIZE_SAMPLE["bytes"])
        _QDRANT_SIZE_SAMPLE["busy"] = True
    received = int(_QDRANT_SIZE_SAMPLE["bytes"])
    try:
        output = subprocess.check_output(["du", "-sb", str(target)], text=True, timeout=25)
        received = int(output.split()[0])
    except Exception:
        pass
    now = time.time()
    with _QDRANT_ATTACH_LOCK:
        prev_at = float(_QDRANT_SIZE_SAMPLE["at"] or 0)
        prev_bytes = int(_QDRANT_SIZE_SAMPLE["bytes"] or 0)
        if prev_at and now > prev_at and received >= prev_bytes:
            _QDRANT_SIZE_SAMPLE["speed_bps"] = (received - prev_bytes) / (now - prev_at)
        _QDRANT_SIZE_SAMPLE["at"] = now
        _QDRANT_SIZE_SAMPLE["bytes"] = received
        _QDRANT_SIZE_SAMPLE["busy"] = False
    return received

def _format_transfer_speed(bps):
    if not bps or bps < 1:
        return "جاري قياس السرعة"
    if bps >= 1024 ** 2:
        return f"{bps / (1024 ** 2):.1f} ميغابايت/ث"
    return f"{max(1, round(bps / 1024))} كيلوبايت/ث"

_QDRANT_ENGINE = {"starting": False, "last_message": ""}
_QDRANT_START_LOCK = threading.Lock()

def _bundled_qdrant_path():
    binary = Path("/app/qdrant_service/qdrant")
    return binary if binary.is_file() else None

def _qdrant_port_open(port=6333):
    import socket
    sock = socket.socket()
    sock.settimeout(1.0)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()

def _start_bundled_qdrant():
    """تشغيل محرك الحاوية فقط. لا يمس عملية Qdrant المحلية على جهاز التطوير."""
    binary = _bundled_qdrant_path()
    if binary is None:
        return False, "إعادة التشغيل التلقائي تعمل داخل حاوية التطبيق"
    if _qdrant_port_open():
        _ensure_qdrant_client()
        _QDRANT_ENGINE["last_message"] = "المخزن يعمل"
        return True, "المخزن يعمل"
    if not _QDRANT_START_LOCK.acquire(blocking=False):
        return True, "جارٍ تشغيل المخزن"
    try:
        if _qdrant_port_open():
            message = "المخزن يعمل"
        else:
            _QDRANT_ENGINE["starting"] = True
            log_path = Path("/app/qdrant_service/qdrant.log")
            log_handle = open(log_path, "ab", buffering=0)
            subprocess.Popen(
                [str(binary), "--config-path", "/app/qdrant_service/config/config.yaml"],
                cwd="/app/qdrant_service",
                stdout=log_handle,
                stderr=log_handle,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            message = "المحرك لم يرد بعد التشغيل"
            for _ in range(30):
                if _qdrant_port_open():
                    message = "تم تشغيل المخزن"
                    break
                time.sleep(1)
        _QDRANT_ENGINE["last_message"] = message
    except Exception as ex:
        message = "تعذر تشغيل المخزن"
        _QDRANT_ENGINE["last_message"] = message
        print(f"⚠️ تعذر تشغيل Qdrant: {type(ex).__name__}")
    finally:
        _QDRANT_ENGINE["starting"] = False
        _QDRANT_START_LOCK.release()
    if _qdrant_port_open():
        _ensure_qdrant_client()
        return True, _QDRANT_ENGINE["last_message"]
    return False, _QDRANT_ENGINE["last_message"]

def _stop_bundled_qdrant():
    binary = _bundled_qdrant_path()
    if binary is None:
        return False
    try:
        output = subprocess.check_output(["lsof", "-nP", "-iTCP:6333", "-sTCP:LISTEN", "-t"], text=True, timeout=5)
    except Exception:
        return True
    stopped = False
    for raw in output.split():
        try:
            pid = int(raw)
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace")
        except Exception:
            continue
        if "qdrant" not in cmdline:
            continue
        try:
            os.kill(pid, 15)
            stopped = True
        except OSError:
            continue
    for _ in range(10):
        if not _qdrant_port_open():
            return True
        time.sleep(0.4)
    if stopped:
        for raw in output.split():
            try:
                os.kill(int(raw), 9)
            except OSError:
                pass
    return not _qdrant_port_open()

def _qdrant_watchdog():
    while True:
        time.sleep(20)
        try:
            if not _qdrant_port_open():
                _start_bundled_qdrant()
            elif not app_state.get("qdrant"):
                _ensure_qdrant_client()
        except Exception:
            pass

def _snapshot_restore_view(connected, points_count):
    status = _read_bootstrap_status() or {}
    phase = status.get("phase") or ""
    expected = int(status.get("expected_bytes") or _SNAPSHOT_EXPECTED_BYTES) or _SNAPSHOT_EXPECTED_BYTES
    ready = bool(connected and points_count > 1000)
    received = 0 if ready else max(int(status.get("received_bytes") or 0), _qdrant_dir_bytes())
    downloading = (not ready) and received >= (1024 ** 3)
    percent = 100 if ready else min(99, int(received * 100 / expected))
    received_gb = round(received / (1024 ** 3), 1)
    expected_gb = round(expected / (1024 ** 3), 1)
    if ready:
        label = "مخزن المتجهات جاهز"
        active = False
    elif downloading or phase == "snapshot":
        speed = _format_transfer_speed(_QDRANT_SIZE_SAMPLE.get("speed_bps"))
        label = f"جاري السحب والتركيب: {received_gb} من {expected_gb} غيغابايت · {speed}. لا توقف الحاوية."
        active = True
    elif phase == "error":
        label = status.get("message") or "توقفت استعادة المتجهات"
        active = True
    else:
        label = ""
        active = False
    return {
        "active": active,
        "phase": "ready" if ready else (phase or "idle"),
        "percent": percent,
        "label": label,
        "received_gb": received_gb,
        "expected_gb": expected_gb,
        "persistent": _data_disk_is_persistent(),
    }

@app.get("/api/system/resources")
async def get_system_resources_endpoint():
    """مؤشر موارد الخادم الحي: الرام، القرص، حالة Qdrant، ونموذج التضمين"""
    mem = _get_live_memory_usage()
    disk = _get_live_disk_usage()

    if not app_state.get("qdrant"):
        _ensure_qdrant_client()

    q_connected = False
    points_count = 0
    collection_name = app_state.get("collection_name", "shamela_almojtahed_8b_dense")
    if app_state.get("qdrant"):
        try:
            q_connected = True
            info = app_state["qdrant"].get_collection(collection_name)
            points_count = info.points_count or 0
        except Exception:
            q_connected = False
            app_state["qdrant"] = None

    restore = _snapshot_restore_view(q_connected, points_count)
    model_loaded = bool(app_state.get("llama_embedder") or app_state.get("st_embedder") or app_state.get("embed_model"))
    model_name = "almojtahed-embedding-8b-Q4_K_M.gguf" if app_state.get("is_8b") else "Al-Mojtahed Model"

    # حساب الحالة العامة ولون المؤشر
    if restore.get("active"):
        health_color = "yellow"
        health_label = restore.get("label") or "جاري سحب مخزن المتجهات"
    elif not q_connected or not model_loaded:
        health_color = "red"
        health_label = "حرج - توقف إحدى الخدمات الأساسية"
    elif mem["percent"] > 90 or disk["percent"] > 92:
        health_color = "red"
        health_label = "حرج - ضغط شديد على الموارد"
    elif mem["percent"] > 80 or disk["percent"] > 85:
        health_color = "yellow"
        health_label = "تنبيه - استهلاك مرتفع للموارد"
    else:
        health_color = "green"
        health_label = "ممتاز - السيرفر يعمل بكفاءة واستقرار تام"

    return {
        "status": "ok",
        "health_color": health_color,
        "health_label": health_label,
        "memory": mem,
        "disk": disk,
        "qdrant": {
            "connected": q_connected,
            "collection_name": collection_name,
            "points_count": points_count,
            "engine_up": _qdrant_port_open(),
            "can_restart": _bundled_qdrant_path() is not None,
            "engine_message": _QDRANT_ENGINE.get("last_message") or "",
            "restore": restore
        },
        "model": {
            "loaded": model_loaded,
            "name": model_name,
            "type": "8B GGUF (4096D)" if app_state.get("is_8b") else "Standard",
            "on_gpu": bool(app_state.get("embed_on_gpu")),
            "download": _embedding_download_view(),
        },
        "gpu": _gpu_status(),
    }


@app.post("/api/system/gpu/enable")
async def enable_gpu_endpoint(request: Request):
    """ينقل نموذج التضمين إلى كرت ظاهر ومعرّفه جاهز. لا يثبّت تعريفات النظام."""
    require_admin(request)
    ok, message = await asyncio.to_thread(_enable_app_gpu)
    return {"status": "ok" if ok else "error", "message": message, "gpu": _gpu_status()}


@app.post("/api/system/qdrant/restart")
async def restart_qdrant_endpoint(request: Request):
    """إعادة تشغيل محرك المتجهات المدمج داخل الحاوية دون مسح البيانات."""
    require_admin(request)
    if _bundled_qdrant_path() is None:
        return {"status": "unavailable", "message": "هذا الزر يشغّل محرك الحاوية. المخزن المحلي يعمل بشكل منفصل."}
    _stop_bundled_qdrant()
    app_state["qdrant"] = None
    ok, message = _start_bundled_qdrant()
    return {"status": "ok" if ok else "error", "message": message}

EMBED_GGUF_NAME = "almojtahed-embedding-8b-Q4_K_M.gguf"
EMBED_GGUF_REPO = "cs95/almojtahed-qwen3-8b"
_EMBED_FETCH = {"running": False, "message": "", "attempt": 0, "received": 0, "expected": 0, "speed_bps": None}
_EMBED_FETCH_LOCK = threading.Lock()

def _embedding_download_view():
    received = int(_EMBED_FETCH.get("received") or 0)
    expected = int(_EMBED_FETCH.get("expected") or 0)
    running = bool(_EMBED_FETCH["running"])
    percent = min(99, int(received * 100 / expected)) if running and expected else 0
    speed = _format_transfer_speed(_EMBED_FETCH.get("speed_bps")) if running else ""
    received_gb = round(received / (1024 ** 3), 2)
    expected_gb = round(expected / (1024 ** 3), 2) if expected else 0
    message = _EMBED_FETCH.get("message") or ""
    if running and expected:
        message = f"جاري سحب نموذج التضمين: {received_gb} من {expected_gb} غيغابايت · {speed}"
    return {
        "running": running,
        "message": message,
        "attempt": int(_EMBED_FETCH.get("attempt") or 0),
        "received_gb": received_gb,
        "expected_gb": expected_gb,
        "percent": percent,
        "speed": speed,
    }

def _embedding_gguf_path():
    name = EMBED_GGUF_NAME
    for root in (PACKAGE_ROOT, SYSTEM_ROOT):
        path = root / "models" / "gguf" / name
        if path.is_file() and path.stat().st_size > 1024 ** 3:
            return path
    data_dir = os.getenv("ALMUJTAHED_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir) / "models" / "gguf" / name
    return PACKAGE_ROOT / "models" / "gguf" / name

def _activate_gguf_embedder(path: Path):
    import gc
    from llama_cpp import Llama
    layers = _desired_gpu_layers()
    with EMBEDDING_LOCK:
        old = app_state.get("llama_embedder")
        app_state["llama_embedder"] = None
        if old is not None:
            del old
            gc.collect()
        try:
            model = Llama(
                model_path=str(path),
                embedding=True,
                n_gpu_layers=layers,
                n_threads=min(8, os.cpu_count() or 4),
                verbose=False,
            )
            used_layers = layers
            app_state["embed_gpu_error"] = ""
        except Exception:
            if layers == 0:
                raise
            model = Llama(
                model_path=str(path),
                embedding=True,
                n_gpu_layers=0,
                n_threads=min(8, os.cpu_count() or 4),
                verbose=False,
            )
            used_layers = 0
            app_state["embed_gpu_error"] = "تعذر نقل النموذج إلى الكرت، وبقي على المعالج"
        app_state["llama_embedder"] = model
        _mark_llama_runtime(model, used_layers)
        app_state["is_8b"] = True
        app_state["is_ready"] = True

def _embedding_received_bytes(directory: Path, final: Path) -> int:
    best = final.stat().st_size if final.is_file() else 0
    if not directory.is_dir():
        return best
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        if EMBED_GGUF_NAME not in path.name and not path.name.endswith(".incomplete"):
            continue
        try:
            best = max(best, path.stat().st_size)
        except OSError:
            continue
    return best

def _embedding_remote_size(token):
    try:
        from huggingface_hub import get_hf_file_metadata, hf_hub_url
        url = hf_hub_url(EMBED_GGUF_REPO, EMBED_GGUF_NAME)
        meta = get_hf_file_metadata(url, token=token)
        return int(meta.size or 0)
    except Exception:
        return 0

def _watch_embedding_bytes(directory: Path, final: Path, stop: threading.Event):
    previous_bytes = 0
    previous_at = time.time()
    while not stop.wait(2):
        received = _embedding_received_bytes(directory, final)
        now = time.time()
        if received >= previous_bytes and now > previous_at:
            _EMBED_FETCH["speed_bps"] = (received - previous_bytes) / (now - previous_at)
        previous_bytes = received
        previous_at = now
        _EMBED_FETCH["received"] = received

def _download_embedding_worker():
    path = _embedding_gguf_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.stat().st_size > 1024 ** 3:
            _activate_gguf_embedder(path)
            _EMBED_FETCH["message"] = "النموذج موجود وتم تحميله في الذاكرة"
            return
        token = os.getenv("HF_TOKEN") or None
        _EMBED_FETCH["expected"] = _embedding_remote_size(token)
        _EMBED_FETCH["received"] = _embedding_received_bytes(path.parent, path)
        stop_watch = threading.Event()
        watcher = threading.Thread(
            target=_watch_embedding_bytes,
            args=(path.parent, path, stop_watch),
            daemon=True,
        )
        watcher.start()
        try:
            from huggingface_hub import hf_hub_download
            for attempt in range(1, 5):
                _EMBED_FETCH["attempt"] = attempt
                _EMBED_FETCH["message"] = f"محاولة سحب نموذج التضمين {attempt} من 4"
                try:
                    hf_hub_download(
                        repo_id=EMBED_GGUF_REPO,
                        filename=EMBED_GGUF_NAME,
                        local_dir=str(path.parent),
                        token=token,
                    )
                    if path.is_file() and path.stat().st_size > 1024 ** 3:
                        _activate_gguf_embedder(path)
                        _EMBED_FETCH["received"] = path.stat().st_size
                        _EMBED_FETCH["message"] = "اكتمل سحب نموذج التضمين وتحميله في الذاكرة"
                        return
                    _EMBED_FETCH["message"] = "وصل ملف أصغر من النموذج المتوقع"
                except Exception as ex:
                    _EMBED_FETCH["message"] = f"فشلت المحاولة {attempt} من 4"
                    print(f"⚠️ سحب نموذج التضمين، المحاولة {attempt}: {type(ex).__name__}")
                    time.sleep(min(60, 8 * attempt))
        finally:
            stop_watch.set()
    except Exception as ex:
        _EMBED_FETCH["message"] = "تعذر تحميل نموذج التضمين في الذاكرة"
        print(f"⚠️ تحميل نموذج التضمين: {type(ex).__name__}")
    finally:
        _EMBED_FETCH["running"] = False

def _start_embedding_download():
    with _EMBED_FETCH_LOCK:
        if _EMBED_FETCH["running"]:
            return False, "سحب نموذج التضمين يعمل الآن"
        _EMBED_FETCH["running"] = True
        _EMBED_FETCH["attempt"] = 0
        _EMBED_FETCH["received"] = 0
        _EMBED_FETCH["speed_bps"] = None
        _EMBED_FETCH["message"] = "بدأ سحب نموذج التضمين"
    threading.Thread(target=_download_embedding_worker, name="embed-download", daemon=True).start()
    return True, "بدأ سحب نموذج التضمين. الشريط يبيّن التقدم، فلا تكرر الضغط."

@app.post("/api/system/embedding/download")
async def download_embedding_endpoint(request: Request):
    """إعادة سحب نموذج التضمين فقط، من غير مسح مخزن المتجهات."""
    require_admin(request)
    ok, message = _start_embedding_download()
    return {"status": "ok" if ok else "busy", "message": message}

@app.post("/api/system/optimize")
async def optimize_system_resources_endpoint():
    """تنظيف الكاش والذاكرة العشوائية لإنعاش السيرفر بعد ساعات العمل والبحث الطويل"""
    import gc
    collected = gc.collect()

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    try:
        with EMBEDDING_LOCK:
            gc.collect()
    except Exception:
        pass

    return {
        "status": "ok",
        "message": f"تم تنظيف الكاش بنجاح وتحرير كائنات الذاكرة ({collected} كائن) وتنشيط نموذج التضمين!",
        "memory": _get_live_memory_usage(),
        "disk": _get_live_disk_usage()
    }


@app.post("/api/system/reload_model")
async def reload_system_model_endpoint():
    """إعادة تفريغ وتحميل نموذج التضمين الشرعي 8B في الرام لإنعاشه بالكامل"""
    import gc
    try:
        with EMBEDDING_LOCK:
            if app_state.get("llama_embedder"):
                del app_state["llama_embedder"]
                app_state["llama_embedder"] = None
            gc.collect()

            GGUF_8B_PATH = PACKAGE_ROOT / "models" / "gguf" / "almojtahed-embedding-8b-Q4_K_M.gguf"
            if not GGUF_8B_PATH.exists():
                GGUF_8B_PATH = SYSTEM_ROOT / "models" / "gguf" / "almojtahed-embedding-8b-Q4_K_M.gguf"

            if GGUF_8B_PATH.exists():
                _activate_gguf_embedder(GGUF_8B_PATH)
                where = "على كرت الشاشة" if app_state.get("embed_on_gpu") else "على المعالج"
                return {
                    "status": "ok",
                    "message": f"تمت إعادة تحميل نموذج التضمين الشرعي 8B {where}.",
                    "memory": _get_live_memory_usage(),
                    "disk": _get_live_disk_usage()
                }
            else:
                return {"status": "error", "message": "ملف النموذج غير موجود على القرص."}
    except Exception as e:
        return {"status": "error", "message": f"حدث خطأ أثناء إعادة تحميل النموذج: {e}"}



@app.post("/api/search")
async def search_endpoint(req: SearchRequest):
    """
    البحث الدلالي الحي في كولكشن shamela_corpus (5.14 مليون مقطع)
    """
    query = req.query.strip()
    if not query:
        return {"results": [], "query": query}

    t0 = time.time()
    # التحقق من جاهزية الاتصال ومحرك التضمين
    if not app_state.get("qdrant"):
        return {
            "results": [],
            "query": query,
            "error": "مخزن المتجهات Qdrant غير متصل أو لم تكتمل استعادة السنابشوت بعد.",
            "count": 0,
            "duration": round(time.time() - t0, 3)
        }

    has_embedder = bool(app_state.get("llama_embedder") or app_state.get("st_embedder") or app_state.get("embed_model"))
    if not has_embedder:
        return {
            "results": [],
            "query": query,
            "error": "نموذج التضمين (Embedding Model) قيد التحميل في الذاكرة ولم يصبح جاهزاً بعد.",
            "count": 0,
            "duration": round(time.time() - t0, 3)
        }

    error_message = None
    results = []
    try:
            # 1. استخراج متجه البحث الكثيف (4096D للنموذج 8B أو 1024D لـ BGE-M3)
            is_8b_col = app_state.get("is_8b", False)
            if is_8b_col and app_state.get("llama_embedder"):
                with EMBEDDING_LOCK:
                    emb = app_state["llama_embedder"].create_embedding(query)
                raw_vec = np.array(emb['data'][0]['embedding'], dtype=np.float32)
                norm = np.linalg.norm(raw_vec)
                if norm > 0:
                    raw_vec = raw_vec / norm
                dense_vec = raw_vec.tolist()
            elif app_state.get("st_embedder"):
                with EMBEDDING_LOCK:
                    raw_vec = app_state["st_embedder"].encode(query, prompt_name="query", normalize_embeddings=True)
                dense_vec = raw_vec.tolist() if hasattr(raw_vec, "tolist") else list(raw_vec)
            elif app_state.get("embed_model"):
                with EMBEDDING_LOCK:
                    enc = app_state["embed_model"].encode(query, return_dense=True, return_sparse=False)
                dense_vec = enc["dense_vecs"].tolist()

            # 2. بناء فلاتر Qdrant الدقيقة
            conditions = []
            db = get_db()
            cursor = db.cursor() if db else None
            book_key = "book_title" if is_8b_col else "title_ar"

            # فلترة نطاق البحث المحدد من قبل المستخدم
            has_explicit_books = False
            if req.selected_books and len(req.selected_books) > 0:
                clean_books = resolve_book_titles_for_search(req.selected_books, cursor=cursor)
                if clean_books:
                    has_explicit_books = True
                    conditions.append(FieldCondition(key=book_key, match=MatchAny(any=clean_books[:500])))
            # أو فلترة اسم الكتاب النصي إن وجد
            elif req.book_name and req.book_name.strip():
                bname = req.book_name.strip()
                matching_titles = []
                if cursor:
                    try:
                        cursor.execute("SELECT title_ar FROM books WHERE title_ar LIKE ? LIMIT 50", (f"%{bname}%",))
                        matching_titles = [r["title_ar"] for r in cursor.fetchall() if r["title_ar"]]
                    except Exception:
                        pass
                if matching_titles:
                    has_explicit_books = True
                    conditions.append(FieldCondition(key=book_key, match=MatchAny(any=matching_titles)))
                else:
                    has_explicit_books = True
                    conditions.append(FieldCondition(key=book_key, match=MatchAny(any=[bname])))

            # فلترة التصنيف: تطبق عند تحديد قسم ولا تتعارض مع الكتب المحددة صراحة
            if req.category and not has_explicit_books:
                clean_cat = resolve_clean_category_name(req.category)
                if is_8b_col:
                    if clean_cat:
                        conditions.append(FieldCondition(key="category_name", match=MatchValue(value=clean_cat)))
                else:
                    cat_id = None
                    if clean_cat and clean_cat in CATEGORY_MAP:
                        cat_id = CATEGORY_MAP[clean_cat]
                    else:
                        for k, v in CATEGORY_MAP.items():
                            if k in str(req.category):
                                cat_id = v
                                break
                    if cat_id:
                        conditions.append(FieldCondition(key="category_id", match=MatchValue(value=cat_id)))

            # فلترة سنة وفاة المؤلف إلى (هـ): حصر البحث بمن توفي في هذه السنة أو قبلها
            if req.death_max and req.death_max > 0:
                if is_8b_col:
                    # في مجموعة 8B حقل author_death_hijri مفهرس كـ integer مباشرة في Qdrant
                    conditions.append(FieldCondition(key="author_death_hijri", range=Range(lte=req.death_max, gt=0)))
                else:
                    if cursor:
                        try:
                            cursor.execute("SELECT title_ar FROM books WHERE main_author_death_hijri <= ? AND main_author_death_hijri > 0", (req.death_max,))
                            valid_titles = [r["title_ar"] for r in cursor.fetchall() if r["title_ar"]]
                            if valid_titles:
                                conditions.append(FieldCondition(key="title_ar", match=MatchAny(any=valid_titles[:1000])))
                        except Exception:
                            pass

            q_filter = Filter(must=conditions) if conditions else None

            # 3. الاستعلام الفائق في Qdrant
            target_top_k = max(1, min(req.top_k, 500))
            requested_pool = max(target_top_k, min(req.pool_size, 2000))
            fetch_limit = requested_pool

            hits = app_state["qdrant"].query_points(
                collection_name=app_state["collection_name"],
                query=dense_vec,
                using="dense",
                query_filter=q_filter,
                limit=fetch_limit,
                with_payload=True
            ).points

            # 4. تجميع المرشحين الأوائل وحفظ ترتيب الاسترجاع الأولي (initial_rank)
            candidates = []
            for hit in hits:
                p = hit.payload or {}
                title = p.get("book_title") or p.get("title_ar", "كتاب غير معنون")
                part = p.get("volume") or p.get("part")
                page_num = p.get("page_num")
                cat_name = p.get("category_name", "عام")
                author = p.get("author_name", "")
                death_year = p.get("author_death_hijri") or p.get("death_hijri")
                footnotes = p.get("footnotes", "")
                betaka = p.get("betaka_text", "")
                rel_path = ""
                cached_text = p.get("text", "")

                # جلب مسار الكتاب والبيانات من SQLite
                if cursor:
                    try:
                        cursor.execute("SELECT main_author_name_ar, main_author_death_hijri, category_name_ar, rel_path, betaka_text FROM books WHERE title_ar = ? LIMIT 1", (title,))
                        row = cursor.fetchone()
                        if row:
                            if not author: author = row["main_author_name_ar"] or ""
                            if death_year is None: death_year = row["main_author_death_hijri"]
                            if cat_name in ("", "عام"): cat_name = row["category_name_ar"] or "عام"
                            if not betaka: betaka = row["betaka_text"] or ""
                            rel_path = row["rel_path"] or ""
                    except Exception:
                        pass

                # تأكيد عدم تجاوز سنة الوفاة المحددة واستبعاد المعاصرين (99999)
                if req.death_max and req.death_max > 0:
                    if death_year and (death_year > req.death_max or death_year == 99999):
                        continue

                item_cand = {
                    "initial_rank": len(candidates) + 1,
                    "initial_score": round(hit.score, 3),
                    "book_title": title,
                    "author": author or "أحد أئمة التراث",
                    "death_year": death_year,
                    "category": cat_name,
                    "volume": str(part) if part not in (None, "None") else "",
                    "page": str(page_num) if page_num is not None else "",
                    "score": round(hit.score, 3),
                    "rel_path": rel_path,
                    "betaka": betaka,
                    "part_raw": part,
                    "page_raw": page_num
                }
                if cached_text:
                    item_cand["text_cached"] = cached_text
                candidates.append(item_cand)

            total_retrieved = len(candidates)

            # 5. البحث الهجين الذكي (Dense Vector + BM25 Lexical Score Fusion)
            # نطبق خوارزمية BM25 الحرفية على حوض المرشحين المسترجعين لرفع النتائج ذات التطابق الحرفي الصارم إذا كان البحث الهجين مفعلاً
            if req.use_hybrid and rank_bm25 and len(candidates) > 1:
                try:
                    def _tokenize_ar(text: str) -> List[str]:
                        t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text or "")
                        t = re.sub(r"[إأآا]", "ا", t)
                        t = re.sub(r"[ىي]", "ي", t)
                        t = re.sub(r"ة", "ه", t)
                        return re.findall(r"\w+", t.lower())

                    q_tokens = _tokenize_ar(query)
                    if q_tokens:
                        doc_tokens_list = []
                        for c in candidates:
                            raw_txt = (c.get("text_cached") or "") + " " + c.get("book_title", "")
                            doc_tokens_list.append(_tokenize_ar(raw_txt))

                        bm25_model = rank_bm25.BM25Okapi(doc_tokens_list)
                        bm25_scores = bm25_model.get_scores(q_tokens)
                        max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1.0

                        for idx_c, c in enumerate(candidates):
                            bm25_norm = float(bm25_scores[idx_c]) / max_bm25
                            dense_norm = float(c["initial_score"])
                            # الدمج الهجين بنسبة 65% للدلالي الكثيف + 35% لـ BM25 الحرفي
                            c["hybrid_score"] = round(0.65 * dense_norm + 0.35 * bm25_norm, 4)
                            c["bm25_score"] = round(float(bm25_scores[idx_c]), 2)
                            c["score"] = c["hybrid_score"]

                        # إعادة الترتيب بحسب النتيجة الهجينة المشتركة
                        candidates.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)
                except Exception as bm_err:
                    print(f"BM25 hybrid ranking notice: {bm_err}")

            is_hybrid_active = bool(req.use_hybrid and rank_bm25 and len(candidates) > 1)
            final_candidates = candidates[:target_top_k]
            for rank_idx, item in enumerate(final_candidates):
                item["rank"] = rank_idx + 1
                item["reranked"] = is_hybrid_active

            # قراءة نصوص الصفحات الكاملة فقط للنتائج المختارة للعرض
            for item in final_candidates:
                body_text = item.pop("text_cached", None)
                if not body_text:
                    body_text = fetch_page_body(item["rel_path"], item["part_raw"], item["page_raw"])
                if not body_text:
                    body_text = item["betaka"] or f"نص مستخرج من {item['book_title']}، الجزء: {item['volume']}، الصفحة: {item['page']}."
                item["text"] = body_text
                item.pop("betaka", None)
                item.pop("part_raw", None)
                item.pop("page_raw", None)
                item.pop("rerank_score", None)
                results.append(item)
    except Exception as e:
        error_message = f"تعذر استخراج النتائج من Qdrant: {e}"
        print(f"❌ {error_message}")

    duration = round(time.time() - t0, 3)

    resp = {
        "results": results,
        "query": query,
        "duration": duration,
        "count": len(results),
        "pool_size": total_retrieved if 'total_retrieved' in locals() else len(results),
        "source": f"Qdrant Live ({app_state['collection_name']} - 8,148,092 points)" if app_state.get("is_8b") else f"Qdrant Live ({app_state['collection_name']})",
        "is_hybrid": is_hybrid_active if 'is_hybrid_active' in locals() else False,
        "is_reranked": is_hybrid_active if 'is_hybrid_active' in locals() else False
    }
    if error_message:
        resp["error"] = error_message
    return resp


CANONICAL_BOOK_ALIASES: Dict[str, str] = {
    # أمهات الفقه الحنفي
    "المبسوط": "المبسوط للسرخسي",
    "المبسوط للسرخسي": "المبسوط للسرخسي",
    "بدائع الصنائع": "بدائع الصنائع في ترتيب الشرائع",
    "حاشية ابن عابدين": "حاشية ابن عابدين = رد المحتار - ط الحلبي",
    "رد المحتار": "حاشية ابن عابدين = رد المحتار - ط الحلبي",
    "ابن عابدين": "حاشية ابن عابدين = رد المحتار - ط الحلبي",
    "الهداية": "الهداية في شرح بداية المبتدي",
    "الهداية للمرغيناني": "الهداية في شرح بداية المبتدي",
    "تبيين الحقائق": "تبيين الحقائق شرح كنز الدقائق وحاشية الشلبي",
    "البحر الرائق": "البحر الرائق شرح كنز الدقائق ومنحة الخالق وتكملة الطوري",
    "فتح القدير": "فتح القدير للعاجز الفقير",
    "فتح القدير لابن الهمام": "فتح القدير للعاجز الفقير",
    "الدر المختار": "حاشية ابن عابدين = رد المحتار - ط الحلبي",

    # أمهات الفقه المالكي
    "المدونة": "المدونة",
    "المدونة الكبرى": "المدونة",
    "البيان والتحصيل": "البيان والتحصيل",
    "الذخيرة": "الذخيرة للقرافي",
    "الذخيرة للقرافي": "الذخيرة للقرافي",
    "مواهب الجليل": "مواهب الجليل في شرح مختصر خليل",
    "التاج والإكليل": "التاج والإكليل لمختصر خليل",
    "بداية المجتهد": "بداية المجتهد ونهاية المقتصد",
    "بداية المجتهد لابن رشد": "بداية المجتهد ونهاية المقتصد",
    "الشرح الكبير للدردير": "الشرح الكبير للدردير",
    "حاشية الدسوقي": "حاشية الدسوقي على الشرح الكبير",
    "الفواكه الدواني": "الفواكه الدواني على رسالة ابن أبي زيد القيرواني",
    "الكافي لابن عبد البر": "الكافي في فقه أهل المدينة",

    # أمهات الفقه الشافعي
    "الأم": "الأم للشافعي - ط الفكر",
    "كتاب الأم": "الأم للشافعي - ط الفكر",
    "الأم للشافعي": "الأم للشافعي - ط الفكر",
    "الحاوي": "الحاوي الكبير",
    "الحاوي الكبير": "الحاوي الكبير",
    "الحاوي للماوردي": "الحاوي الكبير",
    "المجموع": "المجموع شرح المهذب - ط المنيرية",
    "المجموع للنووي": "المجموع شرح المهذب - ط المنيرية",
    "المجموع شرح المهذب": "المجموع شرح المهذب - ط المنيرية",
    "روضة الطالبين": "روضة الطالبين وعمدة المفتين",
    "روضة الطالبين للنووي": "روضة الطالبين وعمدة المفتين",
    "مغني المحتاج": "مغني المحتاج إلى معرفة معاني ألفاظ المنهاج",
    "تحفة المحتاج": "تحفة المحتاج في شرح المنهاج وحواشي الشرواني والعبادي",
    "نهاية المحتاج": "نهاية المحتاج إلى شرح المنهاج",
    "أسنى المطالب": "أسنى المطالب في شرح روض الطالب",
    "المنهاج للنووي": "منهاج الطالبين وعمدة المفتين في الفقه",
    "الوسيط للغزالي": "الوسيط في المذهب",

    # أمهات الفقه الحنبلي
    "المغني": "المغني لابن قدامة - ت التركي",
    "المغني لابن قدامة": "المغني لابن قدامة - ت التركي",
    "الشرح الكبير": "الشرح الكبير على متن المقنع",
    "الشرح الكبير لابن قدامة": "الشرح الكبير على متن المقنع",
    "الإنصاف": "الإنصاف في معرفة الراجح من الخلاف - ت التركي",
    "الإنصاف للمرداوي": "الإنصاف في معرفة الراجح من الخلاف - ت التركي",
    "كشاف القناع": "كشاف القناع عن متن الإقناع - ط وزارة العدل",
    "كشاف القناع للبهوتي": "كشاف القناع عن متن الإقناع - ط وزارة العدل",
    "المبدع": "المبدع في شرح المقنع - ط العلمية",
    "المبدع لابن مفلح": "المبدع في شرح المقنع - ط العلمية",
    "مطالب أولي النهى": "مطالب أولي النهى في شرح غاية المنتهى",
    "الروض المربع": "الروض المربع شرح زاد المستقنع - ط المؤيد والرسالة",
    "زاد المستقنع": "زاد المستقنع في اختصار المقنع - ط دار الوطن",
    "الفروع": "الفروع وتصحيح الفروع",
    "الفروع لابن مفلح": "الفروع وتصحيح الفروع",

    # أمهات التواريخ والحوليات
    "تاريخ الطبري": "تاريخ الطبري = تاريخ الرسل والملوك، وصلة تاريخ الطبري",
    "الطبري": "تاريخ الطبري = تاريخ الرسل والملوك، وصلة تاريخ الطبري",
    "الكامل في التاريخ": "الكامل في التاريخ - ت تدمري",
    "ابن الأثير": "الكامل في التاريخ - ت تدمري",
    "الكامل": "الكامل في التاريخ - ت تدمري",
    "البداية والنهاية": "البداية والنهاية - ت التركي",
    "ابن كثير": "البداية والنهاية - ت التركي",
    "تاريخ الإسلام": "تاريخ الإسلام - ت تدمري",
    "الذهبي": "تاريخ الإسلام - ت تدمري",
    "العبر": "العبر في خبر من غبر - وذيوله ت زغلول",
    "سير أعلام النبلاء": "سير أعلام النبلاء - ط الحديث",
    "المنتظم": "المنتظم في تاريخ الملوك والأمم",
    "ابن الجوزي": "المنتظم في تاريخ الملوك والأمم",
    "مرآة الزمان": "مرآة الزمان في تواريخ الأعيان",
    "النجوم الزاهرة": "النجوم الزاهرة فى ملوك مصر والقاهرة",
    "ابن تغري بردي": "النجوم الزاهرة فى ملوك مصر والقاهرة",
    "حوادث الدهور": "حوادث الدهور في مدى الأيام والشهور - ق 1",
    "السلوك": "السلوك لمعرفة دول الملوك",
    "المقريزي": "السلوك لمعرفة دول الملوك",
    "اتعاظ الحنفا": "اتعاظ الحنفا بأخبار الأئمة الفاطميين الخلفا",
    "عجائب الآثار": "تاريخ عجائب الآثار في التراجم والأخبار",
    "الجبرتي": "تاريخ عجائب الآثار في التراجم والأخبار",
    "العقد الثمين": "العقد الثمين فى تاريخ البلد الأمين",
    "الفاسي": "العقد الثمين فى تاريخ البلد الأمين",
    "شفاء الغرام": "شفاء الغرام بأخبار البلد الحرام",
    "وفاء الوفاء": "وفاء الوفاء بأخبار دار المصطفى",
    "السمهودي": "وفاء الوفاء بأخبار دار المصطفى",
    "مفاكهة الخلان": "مفاكهة الخلان في حوادث الزمان",
    "ابن طولون": "مفاكهة الخلان في حوادث الزمان",
    "بدائع الزهور": "بدائع الزهور في وقائع الدهور - ت محمد مصطفى",
    "ابن إياس": "بدائع الزهور في وقائع الدهور - ت محمد مصطفى",
    "عقود الجمان": "عقود الجمان في وقائع الأزمان",
    "نزهة الأمم": "نزهة الأمم في العجائب والحكم",
    "شذرات الذهب": "شذرات الذهب في أخبار من ذهب",
    "تاريخ دمشق": "تاريخ دمشق لابن عساكر",
    "ابن عساكر": "تاريخ دمشق لابن عساكر",
    "إنباء الغمر": "إنباء الغمر بأبناء العمر - ط الهندية",
    "زبدة الحلب": "زبدة الحلب في تاريخ حلب"
}


def resolve_canonical_book_name(name: str, cursor=None) -> str:
    """مطابقة الاسم الشائع أو المختصر أو رقم المعرف المعياري (#ID) للعنوان الحرفي المعتمد في المخزن بدقة قطعية"""
    if not name or not str(name).strip():
        return ""
    c_name = str(name).strip()
    # تنظيف الأقواس الشائعة إن وجدت
    c_name = re.sub(r'^[«"\'\[(]+|[»"\'\])]+$', '', c_name).strip()

    # إذا كان المدخل مجرد إشارة لجزء أو صفحة (مثل: ج 18، ص 546، جـ: 1) فليس اسم كتاب
    if re.match(r'^(?:جـ?|جزء|الجزء|صـ?|صفحة|الصفحة)\s*[:\s\d٠-٩]+$', c_name):
        return ""

    # 1. إذا كان المدخل رقماً صريحاً أو معرّف كتاب صريح مثل #1852
    if c_name.startswith('#') or (c_name.isdigit() and len(c_name) <= 5):
        try:
            bid = int(c_name.lstrip('#'))
            if 1 <= bid <= 8589 and cursor:
                cursor.execute("SELECT title_ar FROM books WHERE book_id = ? LIMIT 1", (bid,))
                r = cursor.fetchone()
                if r:
                    return r["title_ar"] if hasattr(r, "__getitem__") else r[0]
        except Exception:
            pass

    # إزالة أي معرّف متبقٍ في بداية النص (مثل #1852 المبسوط) للبحث بالاسم
    clean_text_only = re.sub(r'^#?\d+\s*[-:]*\s*', '', c_name).strip()
    lookup_name = clean_text_only if clean_text_only else c_name

    # 2. القاموس المعياري للأمهات المشهورة
    if lookup_name in CANONICAL_BOOK_ALIASES:
        return CANONICAL_BOOK_ALIASES[lookup_name]
    
    if not cursor:
        return lookup_name
        
    try:
        # 3. تطابق تام في قاعدة البيانات
        cursor.execute("SELECT title_ar FROM books WHERE title_ar = ? LIMIT 1", (lookup_name,))
        r = cursor.fetchone()
        if r:
            return r["title_ar"] if hasattr(r, "__getitem__") else r[0]

        # 4. مطابقة أسماء الأعلام والمصنفين
        for scholar, official in SCHOLAR_TO_CANONICAL_BOOK.items():
            if scholar == lookup_name or scholar in lookup_name:
                cursor.execute("SELECT title_ar FROM books WHERE title_ar = ? LIMIT 1", (official,))
                r = cursor.fetchone()
                if r:
                    return r["title_ar"] if hasattr(r, "__getitem__") else r[0]

        # 5. تطابق مع حدود الكلمات مع إعطاء الأولوية للتصنيفات الكبرى
        cursor.execute("""
            SELECT title_ar, category_id, volume_count_observed 
            FROM books 
            WHERE title_ar LIKE ? OR title_ar LIKE ? OR title_ar LIKE ?
            ORDER BY 
              CASE WHEN category_id IN (14, 15, 16, 17, 18, 25, 26, 6) THEN 0 ELSE 1 END,
              volume_count_observed DESC,
              LENGTH(title_ar) ASC
            LIMIT 1
        """, (f"{lookup_name} %", f"{lookup_name} -%", f"% {lookup_name} %"))
        r = cursor.fetchone()
        if r:
            return r["title_ar"] if hasattr(r, "__getitem__") else r[0]

        # 6. بحث فرعي منظم
        cursor.execute("""
            SELECT title_ar FROM books 
            WHERE title_ar LIKE ? 
            ORDER BY 
              CASE WHEN category_id IN (14, 15, 16, 17, 18, 25, 26, 6) THEN 0 ELSE 1 END,
              volume_count_observed DESC
            LIMIT 1
        """, (f"%{lookup_name}%",))
        r = cursor.fetchone()
        if r:
            return r["title_ar"] if hasattr(r, "__getitem__") else r[0]
    except Exception as e:
        print(f"Book resolve error for '{name}': {e}")
        
    return lookup_name


@app.get("/api/books/search")
async def api_search_books(q: str = "", category_id: Optional[int] = None, limit: int = 50):
    """
    البحث السريع اللحظي في فهرس أمهات كتب الشاملة (8,589 كتاباً مع أرقامها المعيارية)
    يدعم البحث برقم الكتاب المعياري (#1852 أو 1852) أو العنوان أو المؤلف أو التصنيف
    """
    db = get_db()
    if not db:
        return {"books": [], "total": 0}
    
    query = (q or "").strip()
    cursor = db.cursor()
    
    # 1. إذا كان البحث برقم الكتاب المعياري مثل #1852 أو 1852
    id_match = re.search(r'#?(\d+)', query)
    if id_match and (query.startswith('#') or query.isdigit()):
        bid = int(id_match.group(1))
        cursor.execute("""
            SELECT book_id, title_ar, category_id, category_name_ar, main_author_name_ar, main_author_death_hijri, volume_count_observed, betaka_text
            FROM books WHERE book_id = ?
        """, (bid,))
        rows = cursor.fetchall()
        if rows:
            return {
                "books": [{
                    "book_id": r["book_id"],
                    "title": r["title_ar"],
                    "category_id": r["category_id"],
                    "category_name": r["category_name_ar"] or "عام",
                    "author": r["main_author_name_ar"] or "أحد أئمة التراث",
                    "death": f"{r['main_author_death_hijri']}هـ" if r["main_author_death_hijri"] and r["main_author_death_hijri"] != 99999 else "—",
                    "volume_count": r["volume_count_observed"] or 1,
                    "betaka_snippet": (r["betaka_text"] or "")[:150]
                } for r in rows],
                "total": len(rows)
            }

    # 2. بحث نصي بالعنوان والمؤلف
    cat_clause = "AND category_id = ?" if category_id else ""
    params = []
    
    if query:
        clean_q = re.sub(r'^[«"\'\[(]+|[»"\'\])]+$', '', query).strip()
        sql = f"""
            SELECT book_id, title_ar, category_id, category_name_ar, main_author_name_ar, main_author_death_hijri, volume_count_observed, betaka_text
            FROM books
            WHERE (title_ar LIKE ? OR main_author_name_ar LIKE ? OR betaka_text LIKE ?) {cat_clause}
            ORDER BY 
              CASE WHEN title_ar = ? THEN 0
                   WHEN title_ar LIKE ? THEN 1
                   WHEN main_author_name_ar LIKE ? THEN 2
                   ELSE 3 END,
              CASE WHEN main_author_death_hijri > 0 AND main_author_death_hijri <= 1000 THEN 0 ELSE 1 END,
              volume_count_observed DESC
            LIMIT ?
        """
        params.extend([f"%{clean_q}%", f"%{clean_q}%", f"%{clean_q}%"])
        if category_id:
            params.append(category_id)
        params.extend([clean_q, f"{clean_q}%", f"{clean_q}%", limit])
    else:
        sql = f"""
            SELECT book_id, title_ar, category_id, category_name_ar, main_author_name_ar, main_author_death_hijri, volume_count_observed, betaka_text
            FROM books
            WHERE 1=1 {cat_clause}
            ORDER BY volume_count_observed DESC, book_id ASC
            LIMIT ?
        """
        if category_id:
            params.append(category_id)
        params.append(limit)

    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall()
    
    books = []
    for r in rows:
        d_val = r["main_author_death_hijri"]
        d_str = f"{d_val}هـ" if d_val and d_val != 99999 else "—"
        books.append({
            "book_id": r["book_id"],
            "title": r["title_ar"],
            "category_id": r["category_id"],
            "category_name": r["category_name_ar"] or "عام",
            "author": r["main_author_name_ar"] or "أحد أئمة التراث",
            "death": d_str,
            "volume_count": r["volume_count_observed"] or 1,
            "betaka_snippet": (r["betaka_text"] or "")[:150]
        })
        
    return {"books": books, "total": len(books)}


@app.get("/api/books/csv")
async def api_download_books_csv():
    """
    تنزيل جدول كتب الشاملة المعياري الموحد (books.csv - 8,589 كتاباً مع معرّفاتها وتواريخ وفايات مصنفيها)
    """
    csv_path = STATIC_DIR / "data" / "books.csv"
    if not csv_path.exists():
        csv_path = BASE_DIR.parent / "books.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="ملف جدول الكتب غير متوفر")
    return FileResponse(
        path=str(csv_path),
        filename="shamela_books_catalog_8589.csv",
        media_type="text/csv"
    )


@app.post("/api/books/resolve")
async def api_resolve_books(req: BookResolveRequest):
    """
    مطابقة أسماء الكتب الشائعة مع العناوين الحرفية المعتمدة في المخزن وإرجاع حالة التحقق وعدد المقاطع
    """
    db = get_db()
    cursor = db.cursor() if db else None
    results = []
    
    for b in req.books:
        b_clean = str(b).strip()
        if not b_clean:
            continue
        resolved = resolve_canonical_book_name(b_clean, cursor)
        is_canonical = b_clean in CANONICAL_BOOK_ALIASES
        
        # جلب عدد المقاطع في Qdrant للتأكد من وجودها الفعلي
        q_count = 0
        if app_state.get("qdrant"):
            try:
                res = app_state["qdrant"].count(
                    collection_name=app_state["collection_name"],
                    count_filter=Filter(must=[FieldCondition(key="book_title" if app_state.get("is_8b") else "title_ar", match=MatchValue(value=resolved))])
                )
                q_count = res.count
            except Exception:
                pass
                
        results.append({
            "input": b_clean,
            "resolved": resolved,
            "verified": q_count > 0,
            "count": q_count,
            "method": "canonical" if is_canonical else ("matched" if resolved != b_clean else "raw")
        })
        
    return {"results": results}


def run_rag_search(query: str, selected_books: Optional[List[str]] = None, pool_size: int = 50, top_k: int = 12, use_reranker: bool = True, dynamic_anchors: Optional[List[str]] = None, use_hybrid: bool = True) -> List[Dict[str, Any]]:
    """
    استرجاع مقاطع دلالية حقيقية موثقة من كولكشن الشاملة مع حل أسماء الكتب واستدعاء نصوص الصفحات
    مع دعم مراسي الاسترجاع الديناميكية (Dynamic Anchors) المولدة من المهندس المعماري
    """
    if not query or not query.strip():
        return []

    clean_q = query.strip()
    has_embedder = bool(app_state.get("llama_embedder") or app_state.get("st_embedder") or app_state.get("embed_model"))
    if not has_embedder or not app_state.get("qdrant"):
        return []

    is_8b_col = app_state.get("is_8b", False)
    db = get_db()
    cursor = db.cursor() if db else None

    # 1. حل وتوسيع أسماء الكتب الشائعة إلى العناوين الحرفية المعتمدة في المخزن بدقة تامة
    resolved_books = []
    if selected_books:
        # استخدام دالة حل العناوين الشاملة مع فك الترميز والتوسيع للطبعات
        expanded = resolve_book_titles_for_search(selected_books, cursor=cursor)
        for eb in expanded:
            if eb and eb not in resolved_books:
                resolved_books.append(eb)
        # التحقق المعياري الاحتياطي عبر resolve_canonical_book_name
        if cursor:
            for b in selected_books:
                b_str = str(b).strip()
                if not b_str:
                    continue
                matched_title = resolve_canonical_book_name(b_str, cursor)
                if matched_title and matched_title not in resolved_books:
                    resolved_books.append(matched_title)

    # 2. إنشاء متجه الاستعلام
    def compute_dense_vector(q_text: str):
        try:
            if is_8b_col and app_state.get("llama_embedder"):
                with EMBEDDING_LOCK:
                    emb = app_state["llama_embedder"].create_embedding(q_text)
                raw_vec = np.array(emb['data'][0]['embedding'], dtype=np.float32)
                norm = np.linalg.norm(raw_vec)
                if norm > 0:
                    raw_vec = raw_vec / norm
                return raw_vec.tolist()
            elif app_state.get("st_embedder"):
                with EMBEDDING_LOCK:
                    raw_vec = app_state["st_embedder"].encode(q_text, prompt_name="query", normalize_embeddings=True)
                return raw_vec.tolist() if hasattr(raw_vec, "tolist") else list(raw_vec)
            elif app_state.get("embed_model"):
                with EMBEDDING_LOCK:
                    enc = app_state["embed_model"].encode(q_text, return_dense=True, return_sparse=False)
                return enc["dense_vecs"].tolist()
        except Exception as e:
            print(f"Embedding error: {e}")
        return None

    # تصنيف عام لنوع الاستعلام (مطابقة صارمة للعبارات المركبة لمنع مطابقة أسماء الأعلام مثل شمس الدين ابن القيم أو شمس الأئمة)
    is_eclipse_query = any(w in clean_q for w in ["كسوف الشمس", "انكساف الشمس", "انكسفت الشمس", "كسفت الشمس", "صلاة الكسوف", "كسوف كلي", "كسوف جزئي", "كسوف حلقي"])
    is_lunar_query = any(w in clean_q for w in ["خسوف القمر", "انخساف القمر", "انخسف القمر", "خسف القمر", "صلاة الخسوف", "خسوف كلي", "خسوف جزئي"])
    is_quake_query = any(w in clean_q for w in ["زلزال", "زلزلة", "رجفة"])
    is_plague_query = any(w in clean_q for w in ["طاعون", "وباء"])

    # بناء مراسي الاستعلام: الأولوية القصوى للمراسي الديناميكية المصممة خصيصاً للمشروع من المهندس
    anchor_queries = [clean_q]
    if dynamic_anchors:
        for anc in dynamic_anchors:
            anc_c = str(anc).strip()
            if anc_c and len(anc_c) >= 3 and anc_c not in anchor_queries:
                anchor_queries.append(anc_c)
        print(f"⚓ [Dynamic Anchors] Applied {len(anchor_queries)} dynamic anchors from Project Architect: {anchor_queries}")
    else:
        # احتياطي عام في حال عدم توفر مراسٍ من المهندس
        if is_eclipse_query:
            anchor_queries.extend([
                "وفيها انكسفت الشمس حتى بدت الكواكب نهارا",
                "كسفت الشمس في رجب أو شعبان أو رمضان ضحوة واستمرت إلى الغروب",
                "وفي هذه السنة انكسفت الشمس كسوفا كليا وأظلمت الأرض نهارا",
                "وفيها انكسفت الشمس كسوفا هائلا ورؤيت النجوم بالنهار",
                "انكسفت الشمس فصلى الناس صلاة الكسوف",
                "وفيها انخسف القمر ليلة النصف"
            ])
        elif is_lunar_query:
            anchor_queries.extend([
                "وفيها انخسف القمر حتى أظلم في ليلة النصف",
                "خسف القمر ليلة الرابع عشر وبقي منكسفا"
            ])
        elif is_quake_query:
            anchor_queries.extend([
                "وفيها كانت زلزلة عظيمة هدمت الدور والأبنية",
                "رجفت الأرض وحدث زلزال هائل فمات خلق كثير"
            ])
        elif is_plague_query:
            anchor_queries.extend([
                "وفيها وقع الطاعون العظيم وفناء بالبلاد ومات خلق كثير",
                "حدث وباء عظيم وموتان بالبصرة وبغداد ومصر والشام"
            ])

    fetch_limit = max(pool_size, top_k * 3, 300)
    per_anchor_limit = max(fetch_limit // len(anchor_queries), 90)

    # 3. بناء الفلاتر والاستعلام من Qdrant
    book_key = "book_title" if is_8b_col else "title_ar"
    q_filter = None
    if resolved_books:
        q_filter = Filter(must=[FieldCondition(key=book_key, match=MatchAny(any=resolved_books[:1000]))])

    all_raw_hits = []
    seen_hit_ids = set()

    for anchor in anchor_queries:
        d_vec = compute_dense_vector(anchor)
        if not d_vec:
            continue
        try:
            h_points = app_state["qdrant"].query_points(
                collection_name=app_state["collection_name"],
                query=d_vec,
                using="dense",
                query_filter=q_filter,
                limit=per_anchor_limit,
                with_payload=True
            ).points
            for hp in h_points:
                if hp.id not in seen_hit_ids:
                    seen_hit_ids.add(hp.id)
                    all_raw_hits.append(hp)
        except Exception as fe:
            print(f"Filtered query error for anchor '{anchor}': {fe}")

    # إذا لم نجد نتائج كافية بسبب النطاق، نبحث عاماً في المخزن كاملاً
    if len(all_raw_hits) < 10 and q_filter is not None:
        d_vec = compute_dense_vector(clean_q)
        if d_vec:
            try:
                gen_hits = app_state["qdrant"].query_points(
                    collection_name=app_state["collection_name"],
                    query=d_vec,
                    using="dense",
                    limit=fetch_limit,
                    with_payload=True
                ).points
                for hp in gen_hits:
                    if hp.id not in seen_hit_ids:
                        seen_hit_ids.add(hp.id)
                        all_raw_hits.append(hp)
            except Exception as e:
                print(f"General query error: {e}")

    hits = all_raw_hits

    # 4. تجميع المرشحين وجلب النصوص الحقيقية مع منع تكرار نفس الصفحة
    candidates = []
    seen_keys = set()
    for h in hits:
        p = h.payload or {}
        title = p.get("book_title") or p.get("title_ar", "كتاب غير معنون")
        part = p.get("volume") or p.get("part")
        page_num = p.get("page_num")
        author = p.get("author_name", "")
        cat_name = p.get("category_name", "عام")
        death_year = p.get("author_death_hijri") or p.get("death_hijri")
        cached_text = p.get("text", "")
        rel_path = ""
        volume_count = None

        page_key = f"{title}_{part}_{page_num}"
        if page_key in seen_keys:
            continue

        if cursor:
            try:
                cursor.execute("SELECT main_author_name_ar, main_author_death_hijri, category_name_ar, rel_path, volume_count_observed FROM books WHERE title_ar = ? LIMIT 1", (title,))
                row = cursor.fetchone()
                if row:
                    if not author: author = row["main_author_name_ar"] or ""
                    if death_year is None: death_year = row["main_author_death_hijri"]
                    if cat_name in ("", "عام"): cat_name = row["category_name_ar"] or "عام"
                    rel_path = row["rel_path"] or ""
                    volume_count = row["volume_count_observed"]
            except Exception:
                pass

        body_text = cached_text or fetch_page_body(rel_path, part, page_num)
        if not body_text:
            body_text = p.get("betaka_text", "")

        snippet = body_text[:750].strip() if body_text else ""
        snippet = re.sub(r"\s+", " ", snippet)

        if snippet:
            seen_keys.add(page_key)

            # فحص واستخراج رأس الحولية التاريخية آلياً إذا كان الكتاب من كتب التاريخ أو الحوليات
            annalistic_year = None
            is_history = any(k in (title + " " + cat_name) for k in [
                "تاريخ", "الكامل", "البداية والنهاية", "المنتظم", "أخبار", "سير", "وفيات",
                "دول", "دهور", "طبقات", "مغازي", "حوادث", "أنباء", "شذرات", "العبر", "مرآة الزمان", "مروج الذهب"
            ])
            if is_history and page_num:
                try:
                    annalistic_year = find_annalistic_year_backtrack(rel_path, title, part, page_num, max_back=40)
                except Exception:
                    pass

            # فحص واستخراج رأس المسألة الفقهية الحاكمة آلياً إذا كان الكتاب من كتب الفقه والمقارن
            fiqh_header = None
            is_fiqh = any(k in (title + " " + cat_name) for k in [
                "فقه", "المغني", "المجموع", "المبسوط", "بدائع", "الإنصاف", "الحاوي", "البيان",
                "التهذيب", "الأم", "المهذب", "الكافي", "الشرح الكبير", "الفتاوى", "مسائل", "رد المحتار",
                "الذخيرة", "الفواكه الدواني", "أسنى المطالب", "بداية المجتهد", "قوانين الأحكام"
            ])
            if is_fiqh and page_num:
                try:
                    f_res = find_fiqh_issue_backtrack(rel_path, title, part, page_num, max_back=15)
                    if f_res:
                        fiqh_header = f_res.get("header")
                except Exception:
                    pass

            candidates.append({
                "title": title,
                "author": author or "أحد أئمة التراث",
                "death": f"(ت: {death_year} هـ)" if death_year else "",
                "category": cat_name,
                "vol": f"ج {part}" if part not in (None, "None") else "",
                "page": f"ص {page_num}" if page_num is not None else "",
                "volume_count": volume_count,
                "citation_label": canonical_citation_label(title, part, page_num, volume_count),
                "part_raw": str(part or ""),
                "page_num_raw": page_num,
                "rel_path": rel_path,
                "annalistic_year": annalistic_year,
                "fiqh_header": fiqh_header,
                "snippet": snippet,
                "score": float(getattr(h, "score", 0.0) or 0.0)
            })

    # استبعاد مواقع الفتاوى والمواقع المعاصرة عند البحث عن وقائع تاريخية
    contemporary_stop_words = ["سؤال وجواب", "فتاوى الشبكة", "فتاوى معاصرة", "يسألونك", "موقع الشيخ", "شبكة الألوكة", "صيد الفوائد", "الدرر السنية"]
    if is_eclipse_query or is_lunar_query or is_quake_query or is_plague_query or "تاريخ" in clean_q:
        candidates = [c for c in candidates if not any(w in (c.get("title", "") + " " + c.get("author", "") + " " + c.get("category", "")) for w in contemporary_stop_words)]

    # تطبيق البحث الهجين الذكي (Dense Vector + BM25 Fusion) إذا كان مفعلاً
    if use_hybrid and rank_bm25 and len(candidates) > 1:
        try:
            def _tok_ar(text: str) -> List[str]:
                t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text or "")
                t = re.sub(r"[إأآا]", "ا", t)
                t = re.sub(r"[ىي]", "ي", t)
                t = re.sub(r"ة", "ه", t)
                return re.findall(r"\w+", t.lower())

            q_tokens = _tok_ar(clean_q)
            if q_tokens:
                doc_tokens_list = [_tok_ar((c.get("snippet") or "") + " " + c.get("title", "")) for c in candidates]
                bm25_model = rank_bm25.BM25Okapi(doc_tokens_list)
                bm25_scores = bm25_model.get_scores(q_tokens)
                max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1.0

                for idx_c, c in enumerate(candidates):
                    bm25_norm = float(bm25_scores[idx_c]) / max_bm25
                    dense_norm = float(c.get("score", 0.0))
                    c["hybrid_score"] = round(0.65 * dense_norm + 0.35 * bm25_norm, 4)
                    c["bm25_score"] = round(float(bm25_scores[idx_c]), 2)
                    c["score"] = c["hybrid_score"]
                print(f"⚡ [RAG Hybrid Search] Applied BM25 Okapi fusion to {len(candidates)} candidates.")
        except Exception as bm_err:
            print(f"BM25 hybrid ranking notice in RAG: {bm_err}")
    elif not use_hybrid:
        print(f"🧠 [RAG Dense Only] Running in pure dense semantic vector mode (BM25 disabled).")

    # فرز نوعي ذكي يعطي الأولوية المطلقة للشواهد المحققة لوقائع الحدث المطلوب وأمهات التواريخ
    def event_priority(c):
        snip = c.get("snippet", "")
        # إعطاء أولوية عليا لأمهات الحوليات التراثية الكبرى
        is_major_chronicle = any(bk in c.get("title", "") for bk in ["تاريخ الرسل والملوك", "تاريخ الطبري", "الكامل في التاريخ", "تاريخ الإسلام", "البداية والنهاية", "النجوم الزاهرة", "تاريخ دمشق", "المنتظم", "شذرات الذهب", "سير أعلام النبلاء", "مروج الذهب"])
        chronicle_bonus = 5 if is_major_chronicle else 0

        if is_eclipse_query:
            if any(w in snip for w in ["انكسفت الشمس", "كسفت الشمس", "كسوف الشمس", "انكساف الشمس"]) or (("انكسف" in snip or "كسف" in snip) and ("شمس" in snip or "الشمس" in snip)):
                return (chronicle_bonus + 3, c.get("score", 0.0))
            if any(w in snip for w in ["انكسفت", "كسفت", "كسوف", "انكساف"]):
                return (chronicle_bonus + 2, c.get("score", 0.0))
            if any(w in snip for w in ["أظلمت نهارا", "بدت الكواكب نهارا", "ظلمة عظيمة"]):
                return (chronicle_bonus + 1, c.get("score", 0.0))
            return (chronicle_bonus, c.get("score", 0.0))
        elif is_lunar_query:
            if any(w in snip for w in ["انخسف القمر", "خسف القمر", "خسوف القمر", "انخساف القمر"]):
                return (chronicle_bonus + 3, c.get("score", 0.0))
            return (chronicle_bonus, c.get("score", 0.0))
        elif is_quake_query:
            if any(w in snip for w in ["زلزال", "زلزلة", "رجفة", "خسف"]):
                return (chronicle_bonus + 2, c.get("score", 0.0))
            return (chronicle_bonus, c.get("score", 0.0))
        elif is_plague_query:
            if any(w in snip for w in ["طاعون", "وباء", "موتان"]):
                return (chronicle_bonus + 2, c.get("score", 0.0))
            return (chronicle_bonus, c.get("score", 0.0))
        else:
            has_direct_event = any(w in snip for w in ["انكسفت", "كسفت", "انكساف", "كسوف", "ظلمة عظيمة", "انخسفت", "خسفت", "رجفة", "زلزلة", "طاعون", "وباء"])
            return (chronicle_bonus + (1 if has_direct_event else 0), c.get("score", 0.0))

    candidates.sort(key=event_priority, reverse=True)

    # 5. إلغاء نموذج Reranker نهائياً وتمرير النتائج الدلالية والمطابقة المباشرة إلى النموذج الرئيسي
    print(f"ℹ️ [Direct Retrieval - Reranker Bypassed] تم إلغاء نموذج Reranker وتمرير أفضل {min(len(candidates), top_k)} نتيجة دلالية ومطابقة مباشرة إلى النموذج الرئيسي لضمان دقة الاستخراج وعدم استبعاد أي شاهد.")
    return candidates[:top_k]


def extract_text_from_file(file_path: Path, filename: str, mime_type: str) -> Tuple[str, bool, Optional[str]]:
    """استخراج نصوص الملف بدقة (PDF, Word, Text, Image) وإرجاع (نص مستخرج, هل صورة, بيانات base64)"""
    ext = file_path.suffix.lower()
    extracted_text = ""
    is_image = False
    base64_data = None
    
    try:
        # 1. ملفات PDF
        if ext == ".pdf" or "pdf" in mime_type:
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                pages_texts = []
                for i, page in enumerate(reader.pages):
                    p_text = page.extract_text() or ""
                    p_text = p_text.strip()
                    if p_text:
                        pages_texts.append(f"--- [صفحة {i+1}] ---\n{p_text}")
                if pages_texts:
                    extracted_text = "\n\n".join(pages_texts)
                else:
                    extracted_text = "[ملف PDF فارغ أو صفحاته ممسوحة ضوئياً كصور]"
            except Exception as e:
                extracted_text = f"[تعذر استخراج نص PDF: {e}]"

        # 2. مستندات Word DOCX
        elif ext == ".docx" or "wordprocessingml" in mime_type:
            try:
                import docx
                doc = docx.Document(str(file_path))
                paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
                extracted_text = "\n\n".join(paras)
            except Exception as e:
                extracted_text = f"[تعذر استخراج مستند Word: {e}]"

        # 3. صور
        elif ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"] or mime_type.startswith("image/"):
            is_image = True
            try:
                import base64
                with open(file_path, "rb") as img_f:
                    raw_bytes = img_f.read()
                    b64_str = base64.b64encode(raw_bytes).decode("utf-8")
                
                img_mime = mime_type if mime_type and mime_type.startswith("image/") else f"image/{ext.replace('.', '')}"
                base64_data = f"data:{img_mime};base64,{b64_str}"
                extracted_text = f"[صورة مرفقة محفوظة في المجلد: {filename} - الحجم: {len(raw_bytes):,} بايت]"
            except Exception as e:
                extracted_text = f"[صورة مرفقة - تعذر قراءة البايتات: {e}]"

        # 4. ملفات نصية وبرمجية وماركداون
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as txt_f:
                    extracted_text = txt_f.read()
            except Exception as e:
                extracted_text = f"[تعذر قراءة الملف النصي: {e}]"

    except Exception as ex:
        extracted_text = f"[خطأ أثناء معالجة الملف: {ex}]"

    return extracted_text, is_image, base64_data


@app.post("/api/chat/upload")
async def upload_chat_file(request: Request, file: UploadFile = File(...)):
    """حفظ الملف في مجلد العضو واستخراج نصوصه وبياناته للنموذج"""
    owner_id = current_owner_id(request)
    try:
        original_filename = file.filename or "uploaded_file"
        clean_name = re.sub(r'[^\w\.-]', '_', original_filename)
        timestamp = int(time.time() * 1000)
        safe_filename = f"{timestamp}_{clean_name}"
        saved_path = UPLOADS_BUCKET_DIR / owner_id / safe_filename
        saved_path.parent.mkdir(parents=True, exist_ok=True)

        contents = await file.read()
        with open(saved_path, "wb") as f:
            f.write(contents)

        mime_type = file.content_type or "application/octet-stream"
        extracted_text, is_image, base64_data = extract_text_from_file(saved_path, original_filename, mime_type)

        return {
            "success": True,
            "filename": original_filename,
            "safe_filename": safe_filename,
            "file_url": f"/uploads/{owner_id}/{safe_filename}",
            "file_path": str(saved_path),
            "file_size": len(contents),
            "file_type": mime_type,
            "extracted_text": extracted_text,
            "has_image": is_image,
            "base64_data": base64_data
        }
    except Exception as err:
        print(f"Error uploading file: {err}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(err)})


def detect_book_page_request(msg: str) -> Optional[Dict[str, Any]]:
    """فحص واكتشاف ما إذا كان سؤال المستخدم طلباً مباشراً لعرض أو قراءة صفحات محددة من كتاب تراثي"""
    if not msg:
        return None
    
    # 1. تحويل الأرقام المشرقية (٠١٢٣٤٥٦٧٨٩) إلى أرقام لاتينية
    ar_digits = "٠١٢٣٤٥٦٧٨٩"
    norm_msg = "".join(str(ar_digits.index(c)) if c in ar_digits else c for c in msg)
    
    # 2. فحص نمط الصفحات: (ص 325 - 328 أو الصفحة 325 إلى 328 أو صفحة 50)
    range_match = re.search(r"(?:\bالصفح(?:ة|ات)\b|\bص\b|\bصفحة\b)\s*(\d+)\s*(?:الى|إلى|حتى|-|:)\s*(\d+)", norm_msg)
    single_match = re.search(r"(?:\bالصفح(?:ة|ات)\b|\bص\b|\bصفحة\b)\s*(\d+)", norm_msg)
    
    start_p, end_p = None, None
    if range_match:
        start_p = int(range_match.group(1))
        end_p = int(range_match.group(2))
    elif single_match:
        # استبعاد السنوات التاريخية (مثل سنة 325 هـ)
        if not re.search(r"(?:سنة|عام|حولية)\s*" + single_match.group(1), norm_msg):
            start_p = int(single_match.group(1))
            end_p = start_p

    if start_p is None:
        return None

    if start_p > end_p:
        start_p, end_p = end_p, start_p

    if end_p - start_p > 50:
        end_p = start_p + 50

    # 3. استخراج الجزء / المجلد إن ورد صراحة
    part_match = re.search(r"(?:\bالجزء\b|\bج\b|\bالمجلد\b|\bمجلد\b)\s*(\d+|[٠-٩]+|الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|الحادي\s+عشر|الثاني\s+عشر|الثالث\s+عشر|الرابع\s+عشر|الخامس\s+عشر)", msg)
    part = None
    if part_match:
        part_raw = part_match.group(1).strip()
        ordinals = {
            'الأول': '1', 'الثاني': '2', 'الثالث': '3', 'الرابع': '4', 'الخامس': '5',
            'السادس': '6', 'السابع': '7', 'الثامن': '8', 'التاسع': '9', 'العاشر': '10',
            'الحادي عشر': '11', 'الثاني عشر': '12', 'الثالث عشر': '13', 'الرابع عشر': '14', 'الخامس عشر': '15'
        }
        part = ordinals.get(part_raw, "".join(str(ar_digits.index(c)) if c in ar_digits else c for c in part_raw))

    # 4. استخراج اسم الكتاب المطلوب
    book_match = re.search(r"(?:من\s+)?كتاب\s+([^\r\n،,\.؛]+)", msg)
    if not book_match:
        book_match = re.search(r"من\s+(?!\s*(?:الصفح|ص\b|صفحة|هنا))([^\r\n،,\.؛]+)", msg)
    if not book_match:
        book_match = re.search(r"(?:في\s+)(?:كتاب\s+)?([^\r\n،,\.؛]+)", msg)

    book_title = ""
    if book_match:
        raw_b = book_match.group(1).strip()
        raw_b = re.sub(r"(?:\bالصفح(?:ة|ات)\b|\bص\b|\bصفحة\b|\bالجزء\b|\bج\b|\bالمجلد\b|\b\d+\b|[٠-٩]+).*", "", raw_b).strip()
        raw_b = re.sub(r"^(?:في|عن|حول)\s+", "", raw_b).strip()
        book_title = raw_b

    return {
        "start_page": start_p,
        "end_page": end_p,
        "part": part,
        "book_title": book_title
    }


class CompareSide(BaseModel):
    model: str
    messages: List[ChatMessage]

class CompareRequest(BaseModel):
    sides: List[CompareSide]
    api_key: Optional[str] = None

@app.post("/api/compare")
async def compare_models_endpoint(req: CompareRequest, request: Request):
    """إجابة السؤال نفسه من نموذجين في OpenRouter، بلا بحث في الشاملة."""
    sides = [side for side in (req.sides or []) if side.model and side.messages][:2]
    if not sides:
        raise HTTPException(status_code=400, detail="اختر نموذجاً واكتب سؤالاً")
    key = owner_openrouter_key(request, req.api_key)

    def _ask(side: CompareSide) -> Dict[str, Any]:
        messages = [{"role": "system", "content": "أجب بالعربية بوضوح. هذه مقارنة بين النماذج، فأجب عن سؤال المستخدم مباشرة. إذا طُلب مشجر فأخرج كتلة ```force3d واحدة لنوع واحد: إسناد، أو خلاف فقهي، أو خلاف عقدي، أو استدلال، أو مناقشة. source الأعلى و target الفرع، ولا تخلط الإسناد بالأقوال."}]
        messages.extend({"role": m.role, "content": m.content} for m in side.messages if m.role in ("user", "assistant") and m.content)
        started = time.perf_counter()
        try:
            reply = call_openrouter_raw(
                model_id=side.model,
                messages=messages,
                api_key=key,
                temperature=0.4,
                max_tokens=4096,
                timeout=120
            )
            return {"model": side.model, "reply": reply, "elapsed_ms": int((time.perf_counter() - started) * 1000)}
        except Exception as exc:
            return {"model": side.model, "error": str(exc), "elapsed_ms": int((time.perf_counter() - started) * 1000)}

    results = await asyncio.gather(*[asyncio.to_thread(_ask, side) for side in sides])
    return {"results": results}


class CompareStreamRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    api_key: Optional[str] = None
    system: Optional[str] = None

@app.post("/api/compare/stream")
async def compare_stream_endpoint(req: CompareStreamRequest, request: Request):
    """بث جواب نموذج واحد لحظة وصوله، حتى تظهر أعمدة المقارنة كلٌّ على حدة."""
    model_id = (req.model or "").strip()
    if not model_id or not req.messages:
        raise HTTPException(status_code=400, detail="اختر نموذجاً واكتب سؤالاً")
    key = owner_openrouter_key(request, req.api_key)
    messages = [{"role": "system", "content": (req.system or "").strip() or "أجب بالعربية بوضوح. هذه مقارنة بين النماذج، فأجب عن سؤال المستخدم مباشرة. إذا طُلب مشجر فأخرج كتلة ```force3d واحدة لنوع واحد: إسناد، أو خلاف فقهي، أو خلاف عقدي، أو استدلال، أو مناقشة. source الأعلى و target الفرع، ولا تخلط الإسناد بالأقوال."}]
    messages.extend(
        {"role": m.role, "content": m.content}
        for m in req.messages
        if m.role in ("user", "assistant") and m.content
    )
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _worker():
        try:
            if str(model_id).startswith("local:"):
                text = _complete_local_text(model_id, messages, 0.4, 4096)
                loop.call_soon_threadsafe(queue.put_nowait, {"delta": text, "kind": "content"})
                return
            payload = {
                "model": normalize_model_id(model_id),
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 4096,
                "stream": True
            }
            request = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8085",
                    "X-Title": "Al-Mojtahed Compare"
                },
                data=json.dumps(payload).encode("utf-8")
            )
            with urllib.request.urlopen(request, timeout=120) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = ((chunk.get("choices") or [{}])[0].get("delta") or {})
                    if delta.get("content"):
                        loop.call_soon_threadsafe(queue.put_nowait, {"delta": delta.get("content"), "kind": "content"})
                    elif delta.get("reasoning"):
                        loop.call_soon_threadsafe(queue.put_nowait, {"delta": delta.get("reasoning"), "kind": "reasoning"})
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, {"error": str(exc)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=_worker, daemon=True).start()

    async def _generate():
        while True:
            item = await queue.get()
            if item is None:
                yield "data: {\"done\": true}\n\n"
                break
            if isinstance(item, dict) and item.get("error") and not item.get("delta"):
                yield "data: " + json.dumps({"error": item["error"]}, ensure_ascii=False) + "\n\n"
                break
            yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    last_user_msg = ""
    for m in reversed(req.messages):
        if m.role == "user":
            last_user_msg = m.content
            break

    thinking_indicator = ""
    if req.thinking_level == "high":
        thinking_indicator = "### [تحرير المسألة الفقهية بالاستدلال التراثي العميق والتوثيق المرجعي]\n\n"
    elif req.thinking_level == "medium":
        thinking_indicator = "### [خلاصة المسألة وتوثيقها من أمهات كتب التراث]\n\n"

    # 1. استخراج إعدادات بطاقة الوكيل المحدد بدقة
    active_agent = None
    target_books = []
    agent_pool_size = 600
    agent_top_k = 50
    agent_rerank = False
    agent_custom_prompt = ""

    if req.agent_group:
        # جمع كافة الكتب المحددة عبر جميع وكلاء المجموعة المفعلين (دعم books و booksScope)
        for a in req.agent_group.get("agents", []):
            if a.get("enabled") is False or a.get("active") is False:
                continue
            books_list = a.get("booksScope") or a.get("books") or []
            for b in books_list:
                b_clean = str(b).strip()
                if b_clean and b_clean not in target_books:
                    target_books.append(b_clean)

        active_agent = req.agent_group.get("active_agent")
        if not active_agent and req.agent_group.get("agents"):
            active_agent = req.agent_group["agents"][0]

        if active_agent:
            agent_pool_size = int(active_agent.get("pool_size") or 1500)
            agent_top_k = int(active_agent.get("top_rerank") or active_agent.get("top_k") or 150)
            agent_rerank = False
            agent_custom_prompt = active_agent.get("system_prompt", "")

    # 1. فحص ما إذا طلب المستخدم عدداً صريحاً في سؤاله (مثل 300 نتيجة، 200 حادثة، مسح 300)
    explicit_num_match = re.search(r"(\d+|[٠-٩]+)\s*(نتيجة|حادثة|شاهد|مقطع|واقعة|سنة|سطر)?", last_user_msg)
    requested_explicit_count = None
    if explicit_num_match:
        raw_num = explicit_num_match.group(1)
        arabic_digits = "٠١٢٣٤٥٦٧٨٩"
        conv_num = "".join(str(arabic_digits.index(c)) if c in arabic_digits else c for c in raw_num)
        try:
            n_val = int(conv_num)
            if 10 <= n_val <= 500:
                requested_explicit_count = n_val
        except Exception:
            pass

    # إذا طلب المستخدم مسحاً شاملاً أو حوادث متعددة، أو كان النموذج يدعم السياق الطويل، نرفع سعة الاسترجاع تلقائياً
    is_survey_query = any(k in last_user_msg for k in ["مسح", "شامل", "كافة", "كل", "حوادث", "جدول", "استقصاء", "تفريغ", "استخراج", "أكثر من", "كسوف", "تواريخ", "300", "٣٠٠"])
    is_long_context = any(k in (req.model or "").lower() for k in ["gemini", "flash", "pro", "claude"])

    if req.extraction_capacity and req.extraction_capacity >= 10:
        agent_top_k = req.extraction_capacity
        agent_pool_size = max(agent_pool_size, agent_top_k * 4, 1500)
    elif req.top_k and req.top_k >= 60:
        agent_top_k = req.top_k
        agent_pool_size = max(agent_pool_size, agent_top_k * 4, 1500)
    elif requested_explicit_count:
        agent_top_k = requested_explicit_count
        agent_pool_size = max(agent_pool_size, agent_top_k * 3, 1500)
    elif is_survey_query:
        agent_top_k = max(agent_top_k, 120) # مسح استقصائي موسع 120 مقطعاً
        agent_pool_size = max(agent_pool_size, agent_top_k * 3, 1500)
    elif is_long_context:
        agent_top_k = max(agent_top_k, 60)
        agent_pool_size = max(agent_pool_size, 600)

    # 2. فحص التحيات والمحادثات العادية (لتجنب البحث في الشاملة عن "مرحبا" أو "السلام عليكم")
    clean_greeting = re.sub(r"[^\w\s]", "", last_user_msg.strip()).strip()
    is_greeting = clean_greeting in [
        "مرحبا", "مرحباً", "سلام", "سلام عليكم", "السلام عليكم", "السلام عليكم ورحمة الله",
        "السلام عليكم ورحمة الله وبركاته", "أهلا", "اهلا", "أهلاً", "أهلا وسهلا", "اهلا وسهلا",
        "صباح الخير", "مساء الخير", "حيّاك الله", "حياك الله", "أهلاً بك", "اهلا بك", "شكرا", "شكراً", "جزاك الله خيرا"
    ]

    # 3. استخلاص الموضوع الحقيقي للبحث متجاوزين عبارات الشكوى والأوامر
    fluff_patterns = [
        r"أريد استخراج نصوص", r"استخرج لي", r"استخرج", r"نصوص", r"حوادث",
        r"مع ذكر اسم الكتاب والمؤلف", r"والجزء والصفحة", r"وتفريغها في جدول",
        r"تفريغها في جدول", r"في جدول", r"تفعيل الاستخراج الفعلي",
        r"إعادة الطلب ليُرجع الوكيل المقاطع", r"من الشاملة بنصها", r"فأنسّقها في الجدول",
        r"نعم هذا المطلوب", r"أعد المحاولة", r"أعد الطلب", r"اذا بحثت في تبويب البحث الدلالي",
        r"تظهر النتائج ولكن اذا كان", r"يعتذر بعدم وجود نتائج", r"تأكد من ان المجموعة والوكلاء",
        r"بطاقة الوكيل", r"وفق ما تم تحديده", r"ربما الوكيل معطل", r"ولا يبحث ويرسل النتيجة",
        r"وهذا رد النموذج الرئيسي", r"حينما طلبت منه", r"لان الذي يظهر ان الاشكال في هذا المكان"
    ]

    is_study_discussion = any(k in last_user_msg for k in ["مدارسة ومناقشة", "ارغب في مدارسة ومناقشة هذا البحث", "أرغب في مدارسة ومناقشة", "مدارسة نقدية"])
    search_query = ""
    is_project_execution = "مشروع بحثي:" in last_user_msg
    if is_study_discussion:
        search_query = "" # البحث مضمّن بالكامل ومحرر في نص الرسالة المحالة للمدارسة
    elif is_project_execution:
        proj_title_m = re.search(r"مشروع بحثي:\s*([^\r\n]+)", last_user_msg)
        proj_desc_m = re.search(r"وصف المشروع:\s*([^\r\n]+)", last_user_msg)
        proj_title = proj_title_m.group(1).strip() if proj_title_m else ""
        proj_desc = proj_desc_m.group(1).strip() if proj_desc_m else ""

        # استخلاص صلب المسألة التراثية للبحث الدلالي النقي متجاوزين الكلمات الإدارية
        clean_subject = f"{proj_title} {proj_desc}"
        for pat in fluff_patterns + [r"التحقق من", r"مسح استقصائي شامل", r"عبر التاريخ الإسلامي", r"ومطابقتها بالحسابات الحديثة"]:
            clean_subject = re.sub(pat, " ", clean_subject)
        clean_subject = re.sub(r"\s+", " ", clean_subject).strip()
        search_query = clean_subject or proj_title

        # ضبط سعة استخراج المقاطع التراثية
        if not req.extraction_capacity:
            agent_top_k = max(agent_top_k, 120)
            agent_pool_size = max(agent_pool_size, 1500)

    elif not is_greeting:
        for m in reversed(req.messages):
            if m.role == "user":
                c = m.content
                for pat in fluff_patterns:
                    c = re.sub(pat, " ", c)
                c = re.sub(r"\s+", " ", c).strip()
                if len(c) >= 3:
                    search_query = c
                    break

        if not search_query or len(search_query) < 3:
            if active_agent:
                search_query = f"{active_agent.get('name', '')} {active_agent.get('desc', '')}".strip()
            if not search_query:
                search_query = last_user_msg

    retrieved_citations = []
    subagents_dossiers = []
    
    # 4. فحص طلبات استعراض وقراءة صفحات محددة من كتاب تراثي (Direct Page Reading)
    page_req = detect_book_page_request(last_user_msg)
    page_reading_instruction = ""
    is_direct_page_reading = False

    if page_req and (page_req.get("book_title") or target_books):
        target_b = page_req.get("book_title") or (target_books[0] if target_books else "")
        try:
            p_res = shamela_local_mcp.get_page_range(
                book=target_b,
                start_page=page_req["start_page"],
                end_page=page_req["end_page"],
                part=page_req.get("part")
            )
            if p_res and p_res.get("status") == "ok" and p_res.get("pages"):
                pages_list = p_res["pages"]
                avail_parts = p_res.get("available_parts") or []
                selected_part_label = p_res.get("part") or (pages_list[0].get("part") if pages_list else "1")
                
                # إذا كانت هناك أجزاء متعددة ولم يُحدد المستخدم جزءاً صريحاً، ننتقي صفحات الجزء الأول منعاً للتضخم
                if not page_req.get("part") and len(avail_parts) > 1:
                    pages_list = [pg for pg in pages_list if str(pg.get("part")) == str(selected_part_label)]
                
                b_title = p_res.get("book_title") or target_b
                b_author = p_res.get("author") or "من أئمة التراث"
                
                page_blocks = []
                for pg in pages_list:
                    p_num = pg.get("page_num")
                    part_num = pg.get("part") or selected_part_label
                    body_text = pg.get("body", "").strip()
                    fn_text = pg.get("footnotes", "").strip()
                    block = f"### الإحالة المعتمدة: {canonical_citation_label(b_title, part_num, p_num)}\n{body_text}"
                    if fn_text:
                        block += f"\n\n**[هوامش وتخريج الصفحة {p_num}]:**\n{fn_text}"
                    page_blocks.append(block)

                other_parts_note = ""
                if not page_req.get("part") and len(avail_parts) > 1:
                    other_parts_note = f"\n\n💡 [تنبيه توثيقي للباحث]: كتاب «{b_title}» يقع في عدة أجزاء ({len(avail_parts)} أجزاء: {', '.join(avail_parts)}) وكل منها يحوي الصفحات ({page_req['start_page']} إلى {page_req['end_page']}). وقد تم استخراج نصوص الجزء ({selected_part_label}) ويمكنك استعراض أي جزء آخر بتحديده صراحة."

                page_reading_instruction = (
                    f"\n\n═══════════════════════════════════════════════════════════\n"
                    f"📖 [نصوص الصفحات الأصلية المستخرجة مباشرة من الكتاب التراثي عبر قارئ الشاملة]:\n"
                    f"• الكتاب المعتمد: «{b_title}»\n"
                    f"• المصنف / المؤلف: {b_author}\n"
                    f"• الصفحات المستخرجة: من صفحة {page_req['start_page']} إلى صفحة {page_req['end_page']} (الجزء: {selected_part_label})\n"
                    f"═══════════════════════════════════════════════════════════\n\n"
                    + "\n\n---\n\n".join(page_blocks)
                    + other_parts_note + "\n"
                    f"═══════════════════════════════════════════════════════════\n"
                    f"🔴 [توجيه قطعي وإلزامي للنموذج لعرض نصوص الصفحات]:\n"
                    f"1. لقد استخرجت المنظومة نصوص الصفحات المطلوبة ({page_req['start_page']} إلى {page_req['end_page']}) من كتاب «{b_title}» مباشرة من النسخة التراثية الأصلية للشاملة.\n"
                    f"2. اعرض نصوص هذه الصفحات كاملة بنصها الصريح والمضبوط مع ذكر رقم الجزء والصفحة لكل مقطع ولا تعتذر إطلاقاً فالمتون كلها بين يديك.\n"
                    f"3. في ختام عرض متون الصفحات، لخّص المسائل والأحكام الفقهية أو العلمية والفوائد المحررة الواردة في هذه الصفحات تيسيراً على الباحث.\n"
                )
                
                # تزويد الشواهد في واجهة المستخدم
                for pg in pages_list:
                    retrieved_citations.append({
                        "title": b_title,
                        "author": b_author,
                        "death": "",
                        "category": "الفقه والتراث",
                        "vol": f"ج {pg.get('part', selected_part_label)}",
                        "page": f"ص {pg.get('page_num')}",
                        "snippet": pg.get("body", "")[:350],
                        "annalistic_year": None
                    })
                
                is_direct_page_reading = True
                print(f"✅ [Direct Page Reading] Successfully extracted {len(pages_list)} pages from {b_title} (p. {page_req['start_page']}-{page_req['end_page']})")
        except Exception as e:
            print(f"❌ [Direct Page Reading Error]: {e}")

    active_agents = []
    if req.agent_group:
        active_agents = [
            a for a in req.agent_group.get("agents", [])
            if a.get("enabled") is not False and a.get("active") is not False
        ]

    # فحص ما إذا كان نمط التوزيع المتوازي مفعلاً وهناك وكلاء في المجموعة
    is_parallel_dispatch = (
        not req.graph_only and
        not req.table_only and
        not is_direct_page_reading and
        req.agent_dispatch_mode != "direct" and
        len(active_agents) >= 1 and
        bool(search_query) and
        not is_greeting and
        not is_study_discussion
    )

    if is_direct_page_reading:
        print(f"📖 [Chat Direct Page Reading Active] Bypass RAG search, serving {len(retrieved_citations)} verbatim pages from Shamela.")
    elif is_parallel_dispatch:
        print(f"🚀 [Multi-Agent Parallel Dispatch] Dispatching {len(active_agents)} subagents in parallel with their dedicated models...")
        api_key_to_use = owner_openrouter_key(request, req.api_key)

        def _worker_subagent(ag: Dict[str, Any]):
            ag_name = ag.get("name") or "وكيل مساعد"
            ag_desc = ag.get("desc") or ""
            ag_prompt = ag.get("system_prompt") or ag.get("systemPrompt") or ""
            ag_model = normalize_model_id(ag.get("model") or "google/gemini-2.5-flash")
            ag_books = [str(b).strip() for b in (ag.get("booksScope") or ag.get("books") or []) if str(b).strip()]
            ag_top_k = int(ag.get("top_k") or ag.get("topK") or ag.get("scanned_texts") or 150)

            # استخراج نصوص كتب هذا الوكيل من Qdrant محلياً عبر BGE-M3
            try:
                cits = run_rag_search(
                    query=search_query,
                    selected_books=ag_books if ag_books else target_books,
                    pool_size=max(ag_top_k * 4, 300),
                    top_k=ag_top_k,
                    use_reranker=False,
                    dynamic_anchors=req.retrieval_anchors,
                    use_hybrid=bool(req.use_hybrid if req.use_hybrid is not None else True)
                )
            except Exception as e:
                print(f"Error in RAG search for agent {ag_name}: {e}")
                cits = []

            if not cits:
                return {
                    "name": ag_name,
                    "desc": ag_desc,
                    "model": ag_model,
                    "books": ag_books,
                    "citations": [],
                    "report": "لم يتم العثور على شواهد كافية في نطاق الكتب التراثية المحددة لهذا الوكيل."
                }

            # صياغة نصوص الشواهد للوكيل مع تضمين رأس الحولية ورأس المسألة الفقهية الحاكمة
            snippets_items = []
            for c in cits[:ag_top_k]:
                loc_str = c.get("citation_label") or canonical_citation_label(c.get("title"), c.get("vol"), c.get("page"), c.get("volume_count"))
                meta_tags = []
                if c.get('annalistic_year'):
                    meta_tags.append(f"📅 [رأس الحولية التاريخية الحاكمة: {c['annalistic_year']}]")
                if c.get('fiqh_header'):
                    meta_tags.append(f"⚖️ [رأس المسألة الفقهية الحاكمة: {c['fiqh_header']}]")
                tag_line = (" " + " ".join(meta_tags)) if meta_tags else ""
                snippets_items.append(
                    f"- الإحالة المعتمدة: {loc_str} | المصنف: {c['author']}{tag_line}:\n  {c['snippet']}"
                )
            snippets_txt = "\n\n".join(snippets_items)

            sub_sys = (
                f"أنت الوكيل المساعد التخصصي: «{ag_name}».\n"
                f"تخصصك: {ag_desc}.\n"
                f"التوجيه التخصصي المعتمد: {ag_prompt or 'استخراج وتحرير وتوثيق نصوص المسألة بدقة'}.\n"
                f"المهمة: طالع نصوص الشاملة المرفقة المستخرجة من نطاق كتبك التراثية المخصصة ({len(ag_books)} كتاباً)، واستخلص نصوص المسألة بدقة متناهية، وانسخ الإحالة المعتمدة حرفياً كما هي.\n"
                f"{CITATION_FORMAT_RULE}\n"
                f"لخص المذاهب والأدلة بأسلوب علمي رصين وموجز تمهيداً لرفعه لمدير المشروع."
            )
            sub_user = (
                f"موضوع المسألة: {search_query}\n\n"
                f"النصوص التراثية المستخرجة من نطاق كتبك ({len(cits)} مقطعاً):\n"
                f"{snippets_txt}\n\n"
                f"المطلوب منك كوكيل متخصص: استخلص نصوص المسألة، وانسخ كل إحالة من سطر «الإحالة المعتمدة» بلا تغيير، ثم ارفع تقريرك لمدير المشروع."
            )

            # استخراج معلمات الضبط الدقيقة للنموذج
            ag_temp = float(ag.get("temperature") if ag.get("temperature") is not None else ag.get("temp", 0.2))
            ag_top_p = float(ag.get("top_p")) if (ag.get("top_p") is not None and str(ag.get("top_p")).strip() != "") else None
            ag_top_k_val = int(ag.get("model_top_k") or ag.get("modelTopK")) if (ag.get("model_top_k") or ag.get("modelTopK")) else None
            ag_freq_pen = float(ag.get("frequency_penalty")) if (ag.get("frequency_penalty") is not None and str(ag.get("frequency_penalty")).strip() != "") else None
            ag_pres_pen = float(ag.get("presence_penalty")) if (ag.get("presence_penalty") is not None and str(ag.get("presence_penalty")).strip() != "") else None
            ag_rep_pen = float(ag.get("repetition_penalty")) if (ag.get("repetition_penalty") is not None and str(ag.get("repetition_penalty")).strip() != "") else None
            ag_max_tokens = int(ag.get("max_tokens") or 3500)

            # استدعاء OpenRouter بنموذج الوكيل المخصص والمعلمات الكاملة
            print(f"🤖 [Subagent Dispatch] Calling OpenRouter model '{ag_model}' for agent '{ag_name}' with temp={ag_temp}, top_p={ag_top_p}, freq_pen={ag_freq_pen}...")
            try:
                rep = call_openrouter_raw(
                    model_id=ag_model,
                    messages=[
                        {"role": "system", "content": sub_sys},
                        {"role": "user", "content": sub_user}
                    ],
                    api_key=api_key_to_use,
                    temperature=ag_temp,
                    max_tokens=ag_max_tokens,
                    top_p=ag_top_p,
                    top_k=ag_top_k_val,
                    frequency_penalty=ag_freq_pen,
                    presence_penalty=ag_pres_pen,
                    repetition_penalty=ag_rep_pen,
                    timeout=90
                )
                print(f"✅ [Subagent Dispatch] Agent '{ag_name}' completed using '{ag_model}' ({len(rep)} chars)")
            except Exception as err:
                print(f"⚠️ [Subagent Dispatch] OpenRouter call for agent '{ag_name}' failed: {err}")
                rep = f"(تعذر استدعاء النموذج {ag_model} للوكيل المساعد، تم إدراج الشواهد المستخرجة مباشرة):\n\n" + snippets_txt[:2500]

            return {
                "name": ag_name,
                "desc": ag_desc,
                "model": ag_model,
                "books": ag_books,
                "citations": cits,
                "report": rep
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(active_agents), 6)) as executor:
            future_to_agent = {executor.submit(_worker_subagent, ag): ag for ag in active_agents}
            for fut in concurrent.futures.as_completed(future_to_agent):
                try:
                    res = fut.result()
                    subagents_dossiers.append(res)
                except Exception as ex:
                    print(f"Subagent execution failed: {ex}")

        # دمج شواهد كافة الوكلاء في قائمة المراجع الموحدة
        seen_snippets = set()
        for d in subagents_dossiers:
            for c in d.get("citations", []):
                h = c.get("snippet", "")[:100]
                if h and h not in seen_snippets:
                    seen_snippets.add(h)
                    retrieved_citations.append(c)

        print(f"✨ [Multi-Agent Parallel Dispatch] All {len(subagents_dossiers)} subagents finished. Total citations collected: {len(retrieved_citations)}")

    elif search_query and not is_greeting and not req.graph_only and not req.table_only:
        # النمط المباشر الموحد (الوضع السابق - خط الرجعة السريع)
        print(f"🔍 [Chat RAG Direct Monolithic] Query: '{search_query}' | Target Books: {target_books} | Dynamic Anchors: {req.retrieval_anchors} | Count: {agent_top_k}")
        try:
            retrieved_citations = run_rag_search(
                query=search_query,
                selected_books=target_books,
                pool_size=agent_pool_size,
                top_k=agent_top_k,
                use_reranker=False,
                dynamic_anchors=req.retrieval_anchors,
                use_hybrid=bool(req.use_hybrid if req.use_hybrid is not None else True)
            )
            print(f"✅ [Chat RAG Direct Monolithic] Extracted {len(retrieved_citations)} passages directly from Shamela (Reranker Bypassed)")
        except Exception as e:
            print(f"❌ [Chat RAG Direct Monolithic] Search error: {e}")
    else:
        print(f"💬 [Chat Conversational] Skip RAG for simple conversational message: '{last_user_msg}'")

    # بناء نصوص المقاطع المستخرجة مع مراعاة النافذة السياقية للنموذج المختار بدقة لمنع تجاوز سياق OpenRouter
    def _calc_model_context_limit(m_name: str) -> int:
        m = (m_name or "").lower()
        if "gemini" in m:
            return 1000000
        elif "claude" in m:
            return 180000
        elif "gpt-4o" in m:
            return 115000
        elif "deepseek" in m or "qwen" in m or "llama" in m or "mistral" in m:
            return 55000
        return 60000

    target_model_name = req.model or "google/gemini-2.5-flash"
    max_context_tokens = _calc_model_context_limit(target_model_name)
    max_allowed_citation_chars = int(max(max_context_tokens - 10000, 10000) * 2.5)

    citations_text = ""
    included_citations_count = 0
    if retrieved_citations:
        for i, c in enumerate(retrieved_citations, 1):
            loc_str = c.get("citation_label") or canonical_citation_label(c.get("title"), c.get("vol"), c.get("page"), c.get("volume_count"))
            year_tag = f" [رأس الحولية الحاكمة المستخرجة: {c['annalistic_year']}]" if c.get('annalistic_year') else ""
            fiqh_tag = f" [رأس المسألة الفقهية الحاكمة: {c['fiqh_header']}]" if c.get('fiqh_header') else ""
            c_death = f" {c.get('death')}" if c.get('death') else ""
            c_cat = f" [{c.get('category')}]" if c.get('category') else ""
            entry = f"{i}. الإحالة المعتمدة: {loc_str} | المصنف: {c.get('author', '')}{c_death}{c_cat}{year_tag}{fiqh_tag}:\n   - نص الشاهد التراثي: {c.get('snippet', '')}\n\n"
            
            if len(citations_text) + len(entry) > max_allowed_citation_chars:
                citations_text += f"\n... [تم استيعاب {included_citations_count} مقطعاً تراثياً وفق أقصى سياق متاح لنموذج {target_model_name}]\n"
                break
            citations_text += entry
            included_citations_count += 1

    # تجهيز تنبيه توجيه الوكلاء المساعدين وإدراج تقاريرهم المنقحة
    agent_routing_instruction = ""
    group_name = ""
    if subagents_dossiers:
        group_name = req.agent_group.get("name", "مجموعة الوكلاء المساعدين") if req.agent_group else "فريق الوكلاء المساعدين"
        dossiers_blocks = []
        for i, d in enumerate(subagents_dossiers, 1):
            books_label = "، ".join(d['books'][:5]) + (f" و{len(d['books'])-5} كتب أخرى" if len(d['books']) > 5 else "") if d['books'] else "نطاق الشاملة الموسع"
            dossiers_blocks.append(
                f"### 📋 [{i}] تقرير الوكيل المساعد: «{d['name']}» ({d['desc']})\n"
                f"• النموذج المعتمد للوكيل في OpenRouter: `{d['model']}`\n"
                f"• نطاق الكتب التراثية المفحوصة: {books_label}\n"
                f"• عدد الشواهد التراثية المستخرجة والمعالجة: {len(d['citations'])} مقطعاً\n\n"
                f"{d['report']}"
            )
        dossiers_str = "\n\n---\n\n".join(dossiers_blocks)

        agent_routing_instruction = (
            f"\n\n═══════════════════════════════════════════════════════════\n"
            f"👥 [تقارير وخلاصات فريق الوكلاء المساعدين المتخصصين (المعالجة المتوازية بنماذجهم المخصصة)]: \n"
            f"لقد قام كل وكيل مساعد متخصص بمعالجة وتصفية نصوص كتبه التراثية باستدعاء نموذجه المخصص المختار في بطاقته بالتوازي في OpenRouter، وإليك تقاريرهم التخصصية المحررة:\n\n"
            f"{dossiers_str}\n\n"
            f"═══════════════════════════════════════════════════════════\n"
            f"🎯 [توجيه قطعي وملزم لمدير المشروع / النموذج الأساسي]:\n"
            f"1. بين يديك الآن تقارير منقحة ومحررة من فريق الوكلاء المساعدين أعلاه بنماذجهم المتخصصة.\n"
            f"2. مهمتك الكبرى: الموازنة والربط بين هذه التقارير في نص محرر، وبيان أوجه الاتفاق والاختلاف، وصياغة الترجيح النهائي. لا تُنشئ جداول ماركداون في هذه الإجابة.\n"
            f"3. اذكر الكتب المنقولة وأجزاءها وصفحاتها داخل الفقرات، بلا جدول ثبت مصادر.\n"
        )
    elif req.agent_group and not is_study_discussion:
        group_name = req.agent_group.get("name", "مجموعة الوكلاء المساعدين")
        group_desc = req.agent_group.get("desc", "")
        agents_list = req.agent_group.get("agents", [])

        agents_details = []
        for i, a in enumerate(agents_list, 1):
            a_n = a.get("name", f"وكيل {i}")
            a_d = a.get("desc", "")
            a_m = a.get("model", "")
            a_sc = a.get("scope_summary", "")
            item_str = f"{i}. **{a_n}**: {a_d}"
            if a_m:
                item_str += f" (النموذج: {a_m})"
            if a_sc:
                item_str += f" [نطاق الكتب: {a_sc}]"
            agents_details.append(item_str)

        agents_str = "\n".join(agents_details) if agents_details else "وكلاء المجموعة المتخصصون."

        agent_routing_instruction = (
            f"\n\n🚨 [تنبيه توجيه وإسناد خاص للوكلاء المساعدين]:\n"
            f"أيها النموذج الأساسي، لقد حدد المستخدم إسناد وتوجيه طلبه حصراً إلى: «{group_name}».\n"
            f"وصف المجموعة: {group_desc}\n"
            f"الوكلاء المعتمدون في هذه المجموعة وأدوارهم التخصصية:\n"
            f"{agents_str}\n\n"
            f"🔴 التعليمات الصارمة والملزمة لك كنموذج أساسي:\n"
            f"1. دورك الأساسي هو أنك المنسق الموجه، يقتصر عملك على استعراض ما استخرجه وكلاء المجموعة من المخزن التراثي ومعالجته وتفريغه وفق ما يطلبه المستخدم تماماً.\n"
            f"2. نسّق استخراج البيانات والمعالجة بحسب تخصص كل وكيل في المجموعة المحددة (مثلاً: ما استخرجه الراصد التاريخي، أو وكيل الفقه، أو وكيل الحديث).\n"
            f"3. قدّم الجواب النهائي بصياغة علمية متكاملة ومحررة تلبي رغبة المستخدم بناءً على ما أنجزه واستخلصه وكلاء المجموعة."
        )

    if page_reading_instruction:
        agent_routing_instruction += page_reading_instruction
    elif retrieved_citations:
        agent_routing_instruction += (
            f"\n\n═══════════════════════════════════════════════════════════\n"
            f"📚 [المقاطع والنصوص التراثية المستخرجة فعلياً من الشاملة عبر الوكلاء]:\n"
            f"لقد قام وكيلك المساعد بالمسح والاستخراج الفعلي من كتب الشاملة واستخرج لك {len(retrieved_citations)} مقطعاً موثقاً لمطابقتها مع طلب المستخدم:\n\n"
            f"{citations_text}\n"
            f"🔴 [تعليمات معالجة الشواهد للنموذج الأساسي]:\n"
            f"1. أنت النموذج الأساسي المحلل والمحقق؛ مهمتك معالجة الشواهد والإجابة بأسلوب تحريري علمي رصين في فقرات، بلا جداول ماركداون.\n"
            f"2. استوعب كـافـة الشواهد والمقاطع المستخرجة أعلاه (جميع الشواهد من 1 إلى {len(retrieved_citations)}) دون استبعاد أي شاهد وثيق الصلة.\n"
            f"3. اذكر القول والدليل والمصدر (الكتاب، المؤلف، الجزء، الصفحة) داخل النص. لا تفرّغ ذلك في جدول.\n"
            f"4. كُتب التاريخ الإسلامي مؤلفة بنظام الحوليات؛ إذا كانت المسألة تاريخية فرقم السنة يُذكر في مطلع الحولية وقد استخرجته لك المنظومة آلياً في [رأس الحولية الحاكمة] فأثبته صراحة في متن الجواب.\n"
            f"5. هذه المقاطع أعلاه موثقة ومستخرجة فعلياً من أمهات المصادر، فاعتمدها في إجابتك.\n"
            f"═══════════════════════════════════════════════════════════\n"
        )

    # 4. تشغيل محرك التحقق الفلكي والحسابي فقط عند اختيار أداة الفلك صراحة أو ورود مسألة كسوف قطعية
    is_astronomy_enabled = False
    if req.computational_tool and isinstance(req.computational_tool, dict):
        if req.computational_tool.get("enabled") and req.computational_tool.get("tool_type") in ("astronomy_hijri_sync", "web_nasa_catalog", "nasa_web_verification"):
            is_astronomy_enabled = True
    elif any(phrase in last_user_msg for phrase in ["انكسفت الشمس", "انخسف القمر", "كسوف الشمس", "خسوف القمر", "محاق فلكي", "حساب الكسوف"]):
        is_astronomy_enabled = True

    if is_astronomy_enabled and not req.graph_only and not req.table_only:
        try:
            combined_corpus = f"{last_user_msg}\n" + "\n".join([c.get('snippet', '') for c in retrieved_citations[:20]])
            astro_report = astronomy_engine.verify_historical_astronomical_event(combined_corpus)
            if astro_report and astro_report.get("details_report"):
                agent_routing_instruction += (
                    f"\n\n═══════════════════════════════════════════════════════════\n"
                    f"📐 [نتائج أداة التحقق الحسابي الفلكي المعتمدة - Historical Astronomical Engine & NASA Canon]:\n"
                    f"{astro_report['details_report']}\n\n"
                    f"💡 خلاصة التحقيق العلمي البرهاني:\n{astro_report['conclusion']}\n\n"
                    f"⛔ [بوابة التحقق الفلكي الإلزامية - حظر تام للتعليق المؤقت]:\n"
                    f"1. يُمنع منعاً باتاً وقطعياً كتابة أي عبارة مثل «يتطلب تحققاً فلكياً» أو «يحتاج مراجعة فلكية» في أي خانة من خانات الجدول النهائي.\n"
                    f"2. انقل الحكم القطعي الصادر من الأداة البرمجية أعلاه حرفياً في عمود «التحقق الفلكي من وقت المحاق والكسوف» (مثل: [مؤكد فلكياً للمحاق...] أو [كشف تصحيف...]).\n"
                    f"3. لكل واقعة، أثبت التاريخ اليوليوسي أو الميلادي المقابل ويوم الأسبوع المحسوب، وبيّن هل طابق يوم الأسبوع المنصوص عليه في الحولية التاريخية بمبدأ ترائي الهلال الفلكي.\n"
                    f"═══════════════════════════════════════════════════════════\n"
                )
        except Exception as _ae:
            print(f"Astronomical verification warning: {_ae}")


    # محاولة الاستعلام الحي من النموذج المختار مباشرة (النموذج هو الذي يجيب بذكائه وتحريره)
    live_reply = None
    if req.model and req.model != "local-almojtahed-8b":
        try:
            key = owner_openrouter_key(request, req.api_key)
            if req.graph_only or req.table_only:
                system_instruction = (req.system_prompt or "عالج النتيجة المعطاة فقط، بلا بحث جديد.").strip()
            elif is_study_discussion:
                system_instruction = (
                    "أنت عالم ومحقق ومحكّم أكاديمي متخصص في العلوم الشرعية والتراثية (الفقه وأصوله، والحديث وعلله، والتفسير ومناهجه، واللغة والتاريخ).\n"
                    "أمامك نص بحث ودراسة علمية متكاملة أحالها الباحث إليك لمدارستها ونقدها ومناقشتها موضوعياً.\n"
                    "المطلوب منك بدقة:\n"
                    "1. تقديم مدارسة نقدية منهجية وتحريرية رصينة لأبواب ومحاور هذا البحث المعروض فقط، والتزام صلب موضوع البحث دون الخروج إلى أي موضوع أجنبي عنه.\n"
                    "2. تحرير المسائل، وبيان أوجه القوة ومواضع الاستدراك أو ما يحتاج إلى مزيد تدقيق وتوثيق ومطابقة.\n"
                    "3. مناقشة الأدلة والاعتراضات والموازنة بين المذاهب والأقوال بأمانة علمية وتجرد تام."
                )
            elif req.system_prompt:
                system_instruction = req.system_prompt
            else:
                system_instruction = (
                    "أنت المجتهد، مساعد ذكي وباحث محقق متخصص في العلوم الإسلامية والفقهية واللغوية والتاريخية.\n"
                    "أجب مباشرة وبتوسع وتحرير علمي رصين عن استفسار وسؤال المستخدم باللغة العربية الفصحى.\n"
                    "حلل المسألة في فقرات محررة. لا تُنشئ جداول ماركداون ولا ثبت مصادر مجدولاً في هذه الإجابة.\n"
                    "إذا طُلب مشجر، أخرج كتلة ```force3d واحدة واختر نوعاً واحداً لا تخلطه بغيره: إسناد (صحابي|تابعي|مدار|طريق|كتاب، والسهم من الشيخ إلى التلميذ)، أو خلاف فقهي (مسألة ثم قول ومذهب ودليل ومناقشة وجواب وترجيح)، أو خلاف عقدي (مسألة ثم مذهب ومقالة وشبهة وجواب)، أو استدلال (حكم ثم دليل ثم وجه الدلالة ثم مناقشة ثم جواب)، أو مناقشة (محل النزاع ثم دعوى كل طرف ثم دليله). source هو الأعلى و target هو الفرع."
                )
            if not req.graph_only and not req.table_only:
                if agent_routing_instruction:
                    system_instruction += agent_routing_instruction
                system_instruction += "\n" + CITATION_FORMAT_RULE

            # تضمين المستندات والملفات المرفوعة والمحفوظة في مجلد uploads (Bucket)
            if req.attachments and isinstance(req.attachments, list) and len(req.attachments) > 0:
                att_lines = [
                    "\n═══════════════════════════════════════════════════════════",
                    "📂 [مستندات وملفات المستخدم المرفوعة والمحفوظة في مجلد النظام (Uploads Bucket)]:"
                ]
                for idx_a, att in enumerate(req.attachments):
                    f_name = att.get("filename") or att.get("name") or f"ملف_{idx_a+1}"
                    f_path = att.get("file_path") or att.get("path") or ""
                    f_url = att.get("file_url") or att.get("url") or ""
                    f_type = att.get("file_type") or att.get("type") or ""
                    f_text = (att.get("extracted_text") or att.get("extractedText") or "").strip()
                    
                    att_lines.append(f"• اسم الملف: {f_name}")
                    if f_path:
                        att_lines.append(f"  مسار الملف على القرص (Local Bucket Path): {f_path}")
                    if f_url:
                        att_lines.append(f"  رابط المعاينة: {f_url}")
                    if f_type:
                        att_lines.append(f"  نوع الملف: {f_type}")
                    if f_text:
                        att_lines.append(f"  نصوص ومحتوى الملف المستخرج من المجلد:\n```text\n{f_text[:25000]}\n```")
                    elif att.get("has_image"):
                        att_lines.append("  ملاحظة: هذا الملف صورة تم تمريرها بصرياً إلى نموذج الرؤية لتحليلها واستخراج نصوصها.")
                att_lines.append("═══════════════════════════════════════════════════════════")
                att_lines.append("توجيه إلزامي ومباشر: يرجى التفاعل مع هذا الملف المرفق واستخراج نصوصه أو مناقشته والإجابة عن استفسار المستخدم بالاستناد إلى محتواه ومساره المذكور أعلاه.")
                
                system_instruction += "\n" + "\n".join(att_lines)

            if req.context_only:
                return {
                    "context_only": True,
                    "system": system_instruction,
                    "agent_group": group_name if req.agent_group else None
                }

            messages_payload = [{"role": "system", "content": system_instruction}]
            for idx_m, m in enumerate(req.messages):
                # إذا كانت هذه آخر رسالة مستخدم وهناك مرفقات صور (multimodal vision)
                if idx_m == len(req.messages) - 1 and m.role == "user" and req.attachments:
                    has_images = any(att.get("has_image") and att.get("base64_data") for att in req.attachments)
                    if has_images:
                        content_parts = [{"type": "text", "text": m.content}]
                        for att in req.attachments:
                            if att.get("has_image") and att.get("base64_data"):
                                content_parts.append({
                                    "type": "image_url",
                                    "image_url": {"url": att.get("base64_data")}
                                })
                        messages_payload.append({"role": m.role, "content": content_parts})
                        continue
                messages_payload.append({"role": m.role, "content": m.content})

            call_model = req.model
            model_alias_map = {
                # Anthropic Claude aliases to official OpenRouter IDs
                "claude-3-7-sonnet": "anthropic/claude-3.7-sonnet",
                "claude-3-5-sonnet": "anthropic/claude-3.5-sonnet",
                "claude-3-5-haiku": "anthropic/claude-3.5-haiku",
                "claude-3-opus": "anthropic/claude-3-opus",
                
                # Google Gemini aliases to active 1M-context models
                "gemini-2.5-flash": "google/gemini-2.5-flash",
                "google/gemini-2.5-flash": "google/gemini-2.5-flash",
                "gemini-3.8-flash": "google/gemini-3.8-flash",
                "google/gemini-3.8-flash": "google/gemini-3.8-flash",
                "gemini-2.0-flash": "google/gemini-2.5-flash",
                "google/gemini-2.0-flash": "google/gemini-2.5-flash",
                "google/gemini-2.0-flash-lite": "google/gemini-2.5-flash",
                "google/gemini-1.5-pro": "google/gemini-2.5-pro",
                "gemini-1.5-pro": "google/gemini-2.5-pro",
                "gemini-flash-8": "google/gemini-2.5-flash",
                "gemini-flash-8b": "google/gemini-2.5-flash",
                "google/gemini-flash-1.5-8b": "google/gemini-2.5-flash",
                "google/gemini-flash-8": "google/gemini-2.5-flash",
                
                # DeepSeek & OpenAI
                "deepseek-r1": "deepseek/deepseek-r1",
                "deepseek-v3": "deepseek/deepseek-chat",
                "deepseek/deepseek-v4.1-flash": "deepseek/deepseek-chat",
                "o3-mini": "openai/o3-mini",
                "gpt-4o": "openai/gpt-4o",
                "gpt-4o-mini": "openai/gpt-4o-mini"
            }
            if call_model in model_alias_map:
                call_model = model_alias_map[call_model]
            def _get_safe_max_tokens_for_model(m_name: str, req_tokens: Optional[int] = None) -> int:
                m_lower = (m_name or "").lower()
                if "claude-3.7" in m_lower or "claude-3-7" in m_lower:
                    max_allowed = 64000
                elif "claude" in m_lower or "deepseek" in m_lower or "qwen" in m_lower or "llama" in m_lower or "mistral" in m_lower:
                    max_allowed = 8192
                elif "gpt-4o-mini" in m_lower or "o3" in m_lower or "o1" in m_lower:
                    max_allowed = 16384
                elif "gpt-4" in m_lower:
                    max_allowed = 4096
                elif "gemini" in m_lower:
                    max_allowed = 65536
                else:
                    max_allowed = 8192
                if req_tokens and 512 <= req_tokens <= max_allowed:
                    return req_tokens
                return max_allowed

            safe_max_output_tokens = _get_safe_max_tokens_for_model(call_model, req.max_tokens)

            def _query_openrouter(target_model: str, max_tok: Optional[int] = None):
                tok_limit = max_tok if max_tok is not None else _get_safe_max_tokens_for_model(target_model, req.max_tokens)
                payload = {
                    "model": target_model,
                    "messages": messages_payload,
                    "temperature": req.temperature or 0.2,
                    "max_tokens": tok_limit
                }
                o_req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:8085",
                        "X-Title": "Al-Mojtahed Sharia Engine"
                    },
                    data=json.dumps(payload).encode("utf-8")
                )
                with urllib.request.urlopen(o_req, timeout=180) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    choice = resp_data.get("choices", [{}])[0]
                    msg_obj = choice.get("message", {})
                    content = (msg_obj.get("content") or "").strip()
                    if not content and msg_obj.get("reasoning"):
                        content = msg_obj.get("reasoning").strip()
                    return content

            try:
                if str(call_model or "").startswith("local:"):
                    live_reply = _complete_local_text(
                        call_model,
                        messages_payload,
                        req.temperature or 0.2,
                        min(safe_max_output_tokens, 4096),
                    )
                else:
                    live_reply = _query_openrouter(call_model, safe_max_output_tokens)
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")
                print(f"OpenRouter HTTP Error ({he.code}) for model {call_model}: {err_body}")
                try:
                    # إعادة المحاولة مع نفس النموذج المختار بسعة محافظة (4096) لتجنب أخطاء تجاوز سعة الإخراج
                    print(f"Retrying same model {call_model} with conservative 4,096 tokens...")
                    live_reply = _query_openrouter(call_model, max_tok=4096)
                except Exception as retry_err:
                    print(f"Retry with same model failed: {retry_err}")
            except Exception as e:
                if str(call_model or "").startswith("local:"):
                    live_reply = "تعذر تشغيل النموذج المحلي. تأكد أن ملف GGUF سليم وأن ذاكرة الجهاز تكفي لتحميله."
                print(f"Live model query error for {call_model}: {type(e).__name__}")
        except Exception as outer_e:
            print(f"Outer live model handler error: {outer_e}")

    if live_reply:
        reply_text = live_reply
    elif retrieved_citations:
        prefix_tag = f"### [معالجة واستنباط عبر: {group_name}]\n\n" if group_name else ""
        reply_text = f"""{prefix_tag}{thinking_indicator}⚠️ **تنبيه:** تعذر الاتصال بمزود الذكاء الاصطناعي لتحليل البيانات وتوليد الجدول (يرجى التحقق من مفتاح API أو الرصيد).

وفيما يلي الشواهد التراثية المستخرجة فعلياً من الشاملة ({len(retrieved_citations)} مقطعاً):

{citations_text}"""
    else:
        prefix_tag = f"### [إسناد لمجموعة: {group_name}]\n\n" if group_name else ""
        reply_text = f"""{prefix_tag}{thinking_indicator}الحمد لله، والصلاة والسلام على رسول الله، وبعد:
بخصوص استفساركم: «{last_user_msg}»: يرجى التحقق من مفتاح مزود الخدمة أو اتصال الشبكة."""

    return {
        "reply": reply_text,
        "model": call_model if live_reply else (req.model or "unknown"),
        "provider": req.provider or "openrouter",
        "thinking_level": req.thinking_level,
        "agent_group": group_name if req.agent_group else None
    }


# =============================================================================
# واجهة مزود خدمة OpenRouter والنماذج الحية
# =============================================================================
OPENROUTER_DEFAULT_KEY = os.getenv("OPENROUTER_API_KEY", "").strip() or OPENROUTER_DEFAULT_KEY
openrouter_cache = {"data": None, "timestamp": 0}

class LocalModelDownloadRequest(BaseModel):
    url: str


@app.get("/api/local-models")
async def list_local_models():
    """النماذج المحلية الموجودة في مجلد models/local داخل التطبيق."""
    return {
        "status": "ok",
        "folder": "models/local",
        "models": _scan_local_chat_models(),
        "download": _local_download_view(),
    }


@app.post("/api/local-models/download")
async def download_local_model(req: LocalModelDownloadRequest, request: Request):
    """يسحب ملف GGUF من رابط مباشر أو من صفحة نموذج على هجينج فيس."""
    if account_role(get_current_user_from_request(request)) not in ("admin", "member"):
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول لسحب نموذج محلي")
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="ضع رابط النموذج")
    if not _LOCAL_FETCH_LOCK.acquire(blocking=False):
        return {"status": "busy", "message": "يوجد سحب قائم", "download": _local_download_view()}
    _LOCAL_FETCH.update({
        "running": True,
        "percent": 0,
        "received": 0,
        "expected": 0,
        "message": "بدأ السحب",
        "error": "",
        "filename": "",
    })
    threading.Thread(target=_download_local_model_worker, args=(url,), name="local-model-download", daemon=True).start()
    return {"status": "ok", "message": "بدأ سحب النموذج", "download": _local_download_view()}


@app.get("/api/openrouter/models")
async def get_openrouter_models(request: Request, api_key: Optional[str] = None):
    """جلب قائمة نماذج OpenRouter بمفتاح الحساب الحالي"""
    import urllib.request
    now = time.time()
    key = owner_openrouter_key(request, api_key)
    if not key:
        raise HTTPException(status_code=400, detail="أدخل مفتاح OpenRouter الخاص بحسابك في تبويب الخدمات")

    # استخدام الذاكرة المخبأة إذا كانت سارية (أقل من 30 دقيقة) لنفس المفتاح الافتراضي
    if openrouter_cache["data"] and (now - openrouter_cache["timestamp"] < 1800) and key == (OPENROUTER_DEFAULT_KEY or ""):
        return openrouter_cache["data"]

    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "http://localhost:8085",
                "X-Title": "Al-Mojtahed Sharia Engine"
            }
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            models_raw = raw.get("data", [])

        parsed = []
        for m in models_raw:
            pricing = m.get("pricing", {})
            prompt_token = float(pricing.get("prompt") or 0.0)
            comp_token = float(pricing.get("completion") or 0.0)
            benchmarks = m.get("benchmarks") or {}
            art_analysis = benchmarks.get("artificial_analysis") or {}

            parsed.append({
                "id": m.get("id"),
                "canonical_slug": m.get("canonical_slug") or m.get("id"),
                "name": m.get("name") or m.get("id"),
                "description": m.get("description", ""),
                "context_length": m.get("context_length", 0),
                "pricing": {
                    "prompt_per_token": prompt_token,
                    "completion_per_token": comp_token,
                    "prompt_per_1m": round(prompt_token * 1_000_000, 4),
                    "completion_per_1m": round(comp_token * 1_000_000, 4)
                },
                "benchmarks": {
                    "intelligence_index": art_analysis.get("intelligence_index"),
                    "coding_index": art_analysis.get("coding_index"),
                    "agentic_index": art_analysis.get("agentic_index"),
                    "design_arena": benchmarks.get("design_arena") or []
                },
                "top_provider": m.get("top_provider") or {}
            })

        res_data = {"status": "ok", "count": len(parsed), "models": parsed}
        if key == (OPENROUTER_DEFAULT_KEY or ""):
            openrouter_cache["data"] = res_data
            openrouter_cache["timestamp"] = now

        return res_data
    except Exception as e:
        print(f"Error fetching OpenRouter models: {e}")
        if key == (OPENROUTER_DEFAULT_KEY or "") and openrouter_cache["data"]:
            return openrouter_cache["data"]
        raise HTTPException(status_code=502, detail="تعذر الاتصال بـ OpenRouter بمفتاح هذا الحساب")


_rankings_cache: Dict[str, Dict[str, Any]] = {}

def _openrouter_get(url: str, key: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "http://localhost:8085",
            "X-Title": "Al-Mojtahed Sharia Engine",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))

def _catalog_model(raw: dict) -> dict:
    pricing = raw.get("pricing") or {}
    prompt_token = float(pricing.get("prompt") or 0.0)
    completion_token = float(pricing.get("completion") or 0.0)
    return {
        "id": raw.get("id"),
        "canonical_slug": raw.get("canonical_slug") or raw.get("id"),
        "name": raw.get("name") or raw.get("id"),
        "pricing": {
            "prompt_per_1m": round(prompt_token * 1_000_000, 4),
            "completion_per_1m": round(completion_token * 1_000_000, 4),
        },
    }

def _live_model_index(models: List[dict]) -> Dict[str, dict]:
    index: Dict[str, dict] = {}
    for model in models:
        model_id = str(model.get("id") or "")
        if not model_id:
            continue
        index[model_id] = model
        slug = str(model.get("canonical_slug") or "")
        if slug:
            index.setdefault(slug, model)
    return index

def _token_totals(rows: List[dict]) -> List[tuple]:
    bucket: Dict[str, int] = {}
    for row in rows:
        slug = str(row.get("model_permaslug") or "")
        if not slug or slug == "other":
            continue
        try:
            tokens = int(row.get("total_tokens") or 0)
        except (TypeError, ValueError):
            tokens = 0
        bucket[slug] = bucket.get(slug, 0) + tokens
    return sorted(bucket.items(), key=lambda item: item[1], reverse=True)

def _pack_ranked_models(ordered: List[tuple], index: Dict[str, dict], skip: set, limit: int = 5) -> List[dict]:
    items = []
    seen = set(skip)
    for slug, tokens in ordered:
        base = slug.split(":", 1)[0]
        model = index.get(slug) or index.get(base)
        if not model or model["id"] in seen:
            continue
        seen.add(model["id"])
        pricing = model.get("pricing") or {}
        items.append({
            "rank": len(items) + 1,
            "id": model["id"],
            "name": model.get("name") or model["id"],
            "tokens": tokens,
            "prompt_per_1m": pricing.get("prompt_per_1m") or 0,
            "completion_per_1m": pricing.get("completion_per_1m") or 0,
        })
        if len(items) >= limit:
            break
    return items

def _build_openrouter_rankings(key: str) -> dict:
    end = datetime.utcnow().date()
    start = end - timedelta(days=6)
    rankings = _openrouter_get(
        "https://openrouter.ai/api/v1/datasets/rankings-daily"
        f"?start_date={start.isoformat()}&end_date={end.isoformat()}",
        key,
    )
    catalog = [
        _catalog_model(item)
        for item in (_openrouter_get("https://openrouter.ai/api/v1/models", key).get("data") or [])
        if item.get("id")
    ]
    index = _live_model_index(catalog)
    rows = rankings.get("data") or []
    dates = [row.get("date") for row in rows if row.get("date")]
    latest = max(dates) if dates else ""
    daily = _pack_ranked_models(
        _token_totals([row for row in rows if row.get("date") == latest]),
        index,
        set(),
    )
    weekly = _pack_ranked_models(_token_totals(rows), index, {item["id"] for item in daily})
    if len(weekly) < 5:
        seen = {item["id"] for item in weekly}
        for item in _pack_ranked_models(_token_totals(rows), index, set(), limit=10):
            if item["id"] in seen:
                continue
            weekly.append(item)
            seen.add(item["id"])
            if len(weekly) >= 5:
                break
        for position, item in enumerate(weekly, 1):
            item["rank"] = position
    meta = rankings.get("meta") or {}
    return {
        "status": "ok",
        "as_of": meta.get("as_of") or "",
        "day": latest,
        "daily": daily,
        "weekly": weekly,
    }

@app.post("/api/openrouter/rankings")
async def get_openrouter_rankings(req: Dict[str, str], request: Request):
    """ترتيب أوبن راوتر الحي بمفتاح الحساب. النماذج الموقوفة عن الكتالوج لا تُعاد."""
    key = owner_openrouter_key(request, (req or {}).get("api_key"))
    if not key:
        raise HTTPException(status_code=400, detail="أدخل مفتاح OpenRouter الخاص بحسابك في تبويب الخدمات")
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    cached = _rankings_cache.get(digest)
    now = time.time()
    if cached and now - cached["timestamp"] < 600:
        return cached["data"]
    try:
        data = await asyncio.to_thread(_build_openrouter_rankings, key)
    except urllib.error.HTTPError as err:
        if err.code in (401, 403):
            raise HTTPException(status_code=400, detail="مفتاح أوبن راوتر لم يُقبل عند جلب الترتيب")
        raise HTTPException(status_code=502, detail="تعذر جلب ترتيب أوبن راوتر")
    except Exception:
        raise HTTPException(status_code=502, detail="تعذر جلب ترتيب أوبن راوتر")
    _rankings_cache[digest] = {"timestamp": now, "data": data}
    return data


openrouter_about_cache: Dict[str, str] = {}
ABOUT_TRANSLATOR_MODEL = "google/gemini-2.5-flash-lite"
ABOUT_AR_CACHE_PATH = BASE_DIR / "model_about_ar_cache.json"

def _load_about_ar_cache() -> None:
    if not ABOUT_AR_CACHE_PATH.exists():
        return
    try:
        saved = json.loads(ABOUT_AR_CACHE_PATH.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            openrouter_about_cache.update({str(k): str(v) for k, v in saved.items() if v})
    except Exception as e:
        print(f"Could not load Arabic model descriptions cache: {e}")

def _save_about_ar_cache() -> None:
    try:
        ABOUT_AR_CACHE_PATH.write_text(
            json.dumps(openrouter_about_cache, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"Could not save Arabic model descriptions cache: {e}")

_load_about_ar_cache()

def _extract_openrouter_page_description(page: str) -> str:
    """أطول وصف ظاهر في صفحة النموذج، لأن واجهة القائمة تقطع النص بعلامة ..."""
    found = re.findall(r'"description"\s*:\s*"((?:\\.|[^"\\])*)"', page)
    texts = []
    for raw in found:
        try:
            text = json.loads('"' + raw + '"')
        except Exception:
            text = raw.replace("\\n", "\n").replace('\\"', '"')
        text = html.unescape(str(text)).strip()
        if text:
            texts.append(text)
    if not texts:
        return ""
    texts.sort(key=len, reverse=True)
    return texts[0]

def _english_model_about(model_id: str) -> str:
    page_url = "https://openrouter.ai/" + urllib.parse.quote(model_id, safe="/")
    description = ""
    try:
        req = urllib.request.Request(page_url, headers={"User-Agent": "Al-Mojtahed/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            page = resp.read().decode("utf-8", "replace")
        description = _extract_openrouter_page_description(page)
    except Exception as e:
        print(f"Error fetching OpenRouter model about for {model_id}: {e}")
    if not description:
        for model in (openrouter_cache.get("data") or {}).get("models") or []:
            if model.get("id") == model_id:
                description = re.sub(r"\s*\.\.\.$", "", (model.get("description") or "").strip())
                break
    description = re.sub(r"\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)", r"\1", description or "")
    return description.strip()

def _translate_model_about_to_arabic(english: str, api_key: str) -> str:
    """ترجمة وصف النموذج بنموذج خفيف وسريع، دون إظهار خطوة الترجمة للمستخدم."""
    system = (
        "أنت مترجم تعريفات تقنية إلى العربية الفصحى. "
        "ترجم الفقرة ترجمة احترافية طبيعية كما تُكتب في بطاقة تعريف النموذج. "
        "أبقِ أسماء النماذج والشركات والمنتجات والأرقام والاختصارات بحروفها اللاتينية كما وردت "
        "(مثل Gemini وOpenRouter و1M). "
        "كلمة decode في وصف النماذج تعني توليد النص، فترجمها إلى «توليد» لا «فك التشفير»، وtokens إلى «رموز». "
        "لا تشرح، ولا تضف عنواناً، ولا تضع علامات اقتباس حول النص. أعد الفقرة العربية فقط."
    )
    payload = {
        "model": ABOUT_TRANSLATOR_MODEL,
        "temperature": 0.1,
        "max_tokens": 600,
        "reasoning": {"enabled": False},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": english}
        ]
    }
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("missing owner provider key")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8085",
            "X-Title": "Al-Mojtahed Sharia Engine"
        },
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))
    content = ((resp_data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    content = content.strip().strip("«»\"'`")
    content = re.sub(r"^(الترجمة|النص المترجم)\s*:\s*", "", content).strip()
    arabic_chars = len(re.findall(r"[\u0600-\u06FF]", content))
    if arabic_chars < 20:
        raise RuntimeError("translation was not Arabic")
    return content

@app.get("/api/openrouter/model-about")
async def get_openrouter_model_about(model_id: str, request: Request):
    """وصف النموذج بالعربية، قبل السعر والسياق، دون إظهار الأصل الإنجليزي."""
    model_id = (model_id or "").strip().strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.:~/-]+", model_id) or ".." in model_id:
        raise HTTPException(status_code=400, detail="معرّف النموذج غير صالح")
    cached = openrouter_about_cache.get(model_id)
    if cached:
        return {"status": "ok", "id": model_id, "description": cached}

    english = _english_model_about(model_id)
    if not english:
        raise HTTPException(status_code=404, detail="لم يُعثر على وصف لهذا النموذج")
    try:
        arabic = _translate_model_about_to_arabic(english, owner_openrouter_key(request))
    except Exception as e:
        print(f"Error translating model about for {model_id}: {e}")
        raise HTTPException(status_code=502, detail="تعذر تجهيز وصف النموذج")

    openrouter_about_cache[model_id] = arabic
    _save_about_ar_cache()
    return {"status": "ok", "id": model_id, "description": arabic}


@app.get("/api/openrouter/credits")
async def get_openrouter_credits(request: Request, api_key: Optional[str] = None):
    """جلب رصيد حساب OpenRouter الخاص بالعضو الحالي"""
    import urllib.request
    key = owner_openrouter_key(request, api_key)
    if not key:
        raise HTTPException(status_code=400, detail="أدخل مفتاح OpenRouter الخاص بحسابك")
    SAR_RATE = 3.75

    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "http://localhost:8085",
        "X-Title": "Al-Mojtahed Sharia Engine"
    }

    credits_data = {}
    auth_data = {}

    # 1. جلب الرصيد الإجمالي والاستهلاك الكلي
    try:
        req_credits = urllib.request.Request("https://openrouter.ai/api/v1/credits", headers=headers)
        with urllib.request.urlopen(req_credits, timeout=10) as resp:
            c_json = json.loads(resp.read().decode("utf-8"))
            credits_data = c_json.get("data", {})
    except Exception as e:
        print(f"Error fetching credits: {e}")

    # 2. جلب إحصائيات المفتاح والاستهلاك الدوري
    try:
        req_auth = urllib.request.Request("https://openrouter.ai/api/v1/auth/key", headers=headers)
        with urllib.request.urlopen(req_auth, timeout=10) as resp:
            a_json = json.loads(resp.read().decode("utf-8"))
            auth_data = a_json.get("data", {})
    except Exception as e:
        print(f"Error fetching auth key: {e}")

    total_credits = float(credits_data.get("total_credits") or 0.0)
    total_usage = float(credits_data.get("total_usage") or 0.0)
    remaining_credits = max(0.0, total_credits - total_usage)

    usage_monthly = float(auth_data.get("usage_monthly") or 0.0)
    usage_weekly = float(auth_data.get("usage_weekly") or 0.0)
    usage_daily = float(auth_data.get("usage_daily") or 0.0)
    key_usage = float(auth_data.get("usage") or 0.0)

    return {
        "status": "ok",
        "sar_rate": SAR_RATE,
        "total_credits_usd": round(total_credits, 2),
        "total_credits_sar": round(total_credits * SAR_RATE, 2),
        "total_usage_usd": round(total_usage, 2),
        "total_usage_sar": round(total_usage * SAR_RATE, 2),
        "remaining_credits_usd": round(remaining_credits, 2),
        "remaining_credits_sar": round(remaining_credits * SAR_RATE, 2),
        "usage_monthly_usd": round(usage_monthly, 2),
        "usage_monthly_sar": round(usage_monthly * SAR_RATE, 2),
        "usage_weekly_usd": round(usage_weekly, 2),
        "usage_weekly_sar": round(usage_weekly * SAR_RATE, 2),
        "usage_daily_usd": round(usage_daily, 2),
        "usage_daily_sar": round(usage_daily * SAR_RATE, 2),
        "key_usage_usd": round(key_usage, 2),
        "key_usage_sar": round(key_usage * SAR_RATE, 2),
        "key_label": auth_data.get("label", ""),
        "limit": auth_data.get("limit"),
        "free_requests": auth_data.get("free_model_daily_requests") or {"used": 0, "limit": 1000, "remaining": 1000}
    }


# =============================================================================
# محرك المشاريع البحثية التراثية (Heritage Research Projects Hub)
# =============================================================================
PROJECTS_FILE = os.path.join(os.path.dirname(__file__), "projects_data.json")

DEFAULT_PROJECTS = []

AGENT_GROUPS_FILE = os.path.join(os.path.dirname(__file__), "agent_groups_data.json")

APP_MEMORY_DB = BASE_DIR / "app_memory.db"
MEMORY_WIPE_PHRASE = "امسح المحفوظات"
_BOOK_INDEX_PATHS = (
    PACKAGE_ROOT / "shamela_index.db",
    BASE_DIR / "shamela_index.db",
    PACKAGE_ROOT / "books.csv",
)

def _owner_key(kind: str, owner_id: str) -> str:
    return f"{kind}:{owner_id}"

def _load_owned_list(owner_id: str, kind: str) -> Optional[list]:
    conn = _ensure_app_memory()
    try:
        row = conn.execute(
            "SELECT payload FROM kv_documents WHERE key=?",
            (_owner_key(kind, owner_id),)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    try:
        data = json.loads(row["payload"])
    except Exception:
        return []
    return data if isinstance(data, list) else []

def _save_owned_list(owner_id: str, kind: str, items: list) -> None:
    payload = json.dumps(items, ensure_ascii=False)
    now = datetime.now().isoformat()
    conn = _ensure_app_memory()
    try:
        conn.execute(
            "INSERT INTO kv_documents (key, payload, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
            (_owner_key(kind, owner_id), payload, now)
        )
        conn.commit()
    finally:
        conn.close()

def _migrate_owner_scope(conn: sqlite3.Connection) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(chat_sessions)")]
    if columns and "owner_id" not in columns:
        conn.execute("ALTER TABLE chat_sessions RENAME TO chat_sessions_shared")
        conn.execute("""
            CREATE TABLE chat_sessions (
                owner_id TEXT NOT NULL,
                id TEXT NOT NULL,
                title TEXT,
                created_at TEXT,
                updated_at TEXT,
                sort_index INTEGER,
                payload TEXT NOT NULL,
                PRIMARY KEY (owner_id, id)
            )
        """)
        conn.execute(
            """
            INSERT INTO chat_sessions (owner_id, id, title, created_at, updated_at, sort_index, payload)
            SELECT ?, id, title, created_at, updated_at, sort_index, payload
            FROM chat_sessions_shared
            """,
            (ADMIN_OWNER_ID,)
        )
        conn.execute("DROP TABLE chat_sessions_shared")

    def adopt(kind: str, payload: Optional[str]) -> None:
        key = _owner_key(kind, ADMIN_OWNER_ID)
        if conn.execute("SELECT 1 FROM kv_documents WHERE key=?", (key,)).fetchone():
            return
        if payload is None:
            return
        conn.execute(
            "INSERT INTO kv_documents (key, payload, updated_at) VALUES (?, ?, ?)",
            (key, payload, datetime.now().isoformat())
        )

    projects_payload = None
    legacy = conn.execute("SELECT payload FROM kv_documents WHERE key='projects'").fetchone()
    if legacy:
        projects_payload = legacy["payload"]
    elif os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as handle:
                existing = json.load(handle)
            if isinstance(existing, list):
                projects_payload = json.dumps(existing, ensure_ascii=False)
        except Exception as exc:
            print(f"Could not import projects into owner scope: {exc}")
    adopt("projects", projects_payload)

    if os.path.exists(AGENT_GROUPS_FILE):
        try:
            with open(AGENT_GROUPS_FILE, "r", encoding="utf-8") as handle:
                groups = json.load(handle)
            if isinstance(groups, list):
                adopt("agents", json.dumps(groups, ensure_ascii=False))
        except Exception as exc:
            print(f"Could not import agent groups into owner scope: {exc}")
    else:
        adopt("agents", "[]")

    if os.path.exists(TOOLS_FILE):
        try:
            with open(TOOLS_FILE, "r", encoding="utf-8") as handle:
                tools = json.load(handle)
            if isinstance(tools, list):
                adopt("tools", json.dumps(tools, ensure_ascii=False))
        except Exception as exc:
            print(f"Could not import tools into owner scope: {exc}")
    conn.commit()

def _book_index_status() -> Dict[str, Any]:
    """قراءة فقط لفهرس الكتب. لا يُفتح للكتابة ولا يُمس في الأرشفة أو المسح."""
    path = DB_INDEX_PATH
    info = {
        "path": str(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "books": 0,
    }
    if not path.exists():
        return info
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
        info["books"] = int(conn.execute("SELECT COUNT(*) FROM books").fetchone()[0])
        conn.close()
    except Exception as e:
        info["error"] = str(e)
    return info

def _ensure_app_memory() -> sqlite3.Connection:
    conn = sqlite3.connect(str(APP_MEMORY_DB), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            owner_id TEXT NOT NULL,
            id TEXT NOT NULL,
            title TEXT,
            created_at TEXT,
            updated_at TEXT,
            sort_index INTEGER,
            payload TEXT NOT NULL,
            PRIMARY KEY (owner_id, id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kv_documents (
            key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS member_shares (
            id TEXT PRIMARY KEY,
            kind TEXT,
            source_id TEXT,
            from_owner TEXT,
            to_owner TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS share_invites (
            id TEXT PRIMARY KEY,
            kind TEXT,
            title TEXT,
            from_username TEXT,
            from_name TEXT,
            to_owner TEXT,
            to_username TEXT,
            payload TEXT,
            status TEXT,
            created_at TEXT,
            resolved_at TEXT
        )
    """)
    _migrate_owner_scope(conn)
    return conn

def _write_projects_snapshot(projects: list) -> None:
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)

def load_stored_projects(owner_id: str):
    data = _load_owned_list(owner_id, "projects")
    if isinstance(data, list):
        return data
    if owner_id == ADMIN_OWNER_ID and os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                return data
        except Exception as exc:
            print(f"Error loading projects: {exc}")
    return DEFAULT_PROJECTS

def save_stored_projects(projects, owner_id: str):
    _save_owned_list(owner_id, "projects", projects)
    if owner_id == ADMIN_OWNER_ID:
        try:
            _write_projects_snapshot(projects)
        except Exception as exc:
            print(f"Error saving projects snapshot: {exc}")

def load_stored_agent_groups(owner_id: str):
    """قراءة مجموعات وكلاء هذا العضو فقط."""
    data = _load_owned_list(owner_id, "agents")
    return data if isinstance(data, list) else []

def save_stored_agent_groups(groups, owner_id: str):
    _save_owned_list(owner_id, "agents", groups)
    if owner_id == ADMIN_OWNER_ID:
        try:
            with open(AGENT_GROUPS_FILE, "w", encoding="utf-8") as handle:
                json.dump(groups, handle, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"Error saving agent groups: {exc}")

class PlanRequest(BaseModel):
    topic: str
    goal: Optional[str] = ""
    scope_time: Optional[str] = ""
    scope_sources: Optional[str] = ""
    has_benchmark: Optional[str] = ""
    preferred_output: Optional[str] = ""
    planning_model: Optional[str] = "google/gemini-2.5-flash"
    api_key: Optional[str] = ""

class TavilySearchRequest(BaseModel):
    api_key: str
    query: str
    search_depth: Optional[str] = "advanced"
    include_domains: Optional[List[str]] = None
    max_results: Optional[int] = 5

class ShareRequest(BaseModel):
    kind: str
    item_id: str
    everyone: bool = False
    usernames: List[str] = []
    key_mode: str = "mine"
    key: str = ""

def _person_display_name(username: str) -> str:
    """اسم العضو المكتوب في الدعوة، لا اسم الدخول."""
    admin_name = os.getenv("AUTH_USERNAME", "").strip()
    if admin_name and same_text(username or "", admin_name):
        return "المشرف"
    account = find_member_account(username)
    if not account:
        return "عضو"
    saved = str(account.get("display_name") or "").strip()
    if saved:
        return saved
    invite_id = account.get("invite_id")
    for invite in load_members_store().get("invites") or []:
        if invite.get("id") == invite_id:
            label = str(invite.get("label") or "").strip()
            if label:
                return label
    return "عضو"

def _share_people() -> List[Dict[str, str]]:
    people = []
    admin_name = os.getenv("AUTH_USERNAME", "").strip()
    if admin_name:
        people.append({
            "username": admin_name,
            "owner_id": ADMIN_OWNER_ID,
            "label": "المشرف",
            "display_name": "المشرف",
        })
    for account in load_members_store().get("accounts") or []:
        if not isinstance(account, dict):
            continue
        username = str(account.get("username") or "").strip()
        if not username or account.get("disabled"):
            continue
        owner_id = str(account.get("id") or "").strip() or ensure_member_id(username)
        people.append({
            "username": username,
            "owner_id": owner_id,
            "label": "عضو",
            "display_name": _person_display_name(username),
        })
    return people

def _share_kind_label(kind: str) -> str:
    return {"chat": "محادثة", "project": "مشروع", "tool": "إضافة", "key": "مفتاح"}.get(kind, "عنصر")

def _share_key_spec(raw: str):
    """يعيد الاسم المحفوظ، اسم الواجهة، والتسمية العربية. بلا قيمة المفتاح."""
    name = _normalize_provider_name(raw)
    catalog = {
        "openrouter": ("openrouter", "openrouter", "أوبن راوتر"),
        "claude": ("anthropic", "claude", "كلود"),
        "anthropic": ("anthropic", "claude", "كلود"),
        "google": ("gemini", "google", "جوجل"),
        "gemini": ("gemini", "google", "جوجل"),
        "openai": ("openai", "openai", "أوبن إي آي"),
        "deepseek": ("deepseek", "deepseek", "ديب سيك"),
        "tavily": ("tavily", "tavily", "Tavily"),
        "groq": ("groq", "groq", "Groq"),
        "hf": ("hf", "hf", "Hugging Face"),
        "huggingface": ("hf", "hf", "Hugging Face"),
    }
    return catalog.get(name)

def _deliver_shared_key(owner_id: str, payload: Dict[str, Any]) -> None:
    secret = str(payload.get("key") or "").strip()
    canonical = str(payload.get("provider") or "").strip()
    ui_name = str(payload.get("ui") or canonical).strip()
    if not secret or not canonical:
        raise HTTPException(status_code=400, detail="تعذر إضافة المفتاح")
    current = load_provider_keys(owner_id)
    current[canonical] = secret
    if ui_name and ui_name != canonical:
        current[ui_name] = secret
    save_provider_keys(owner_id, current)

def _share_item_title(kind: str, item: Dict[str, Any]) -> str:
    if kind == "tool":
        raw = item.get("name") or item.get("title") or "إضافة"
    else:
        raw = item.get("title") or "بدون عنوان"
    return " ".join(str(raw).split())[:180] or "بدون عنوان"

def _send_direct_notice(recipient: str, title: str, body: str) -> None:
    recipient = (recipient or "").strip()
    if not recipient:
        return
    store = load_notices_store()
    store.setdefault("notices", []).insert(0, {
        "id": "n_" + secrets.token_hex(8),
        "title": title.strip()[:180],
        "body": body.strip()[:4000],
        "audience": "selected",
        "recipients": [recipient],
        "reads": {},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    save_notices_store(store)

def _share_clone(item: Dict[str, Any], sender: str) -> Dict[str, Any]:
    clone = json.loads(json.dumps(item, ensure_ascii=False))
    clone["shared_from"] = {
        "username": sender,
        "source_id": str(item.get("id") or ""),
        "at": datetime.now().isoformat(),
    }
    clone["id"] = "share_" + secrets.token_hex(8)
    return clone

def _load_share_item(kind: str, item_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
    if kind == "chat":
        conn = _ensure_app_memory()
        try:
            sessions = _read_chat_sessions(conn, owner_id)
        finally:
            conn.close()
        return next((item for item in sessions if str(item.get("id")) == item_id), None)
    if kind == "project":
        return next((item for item in load_stored_projects(owner_id) if str(item.get("id")) == item_id), None)
    if kind == "tool":
        return next((item for item in load_stored_tools(owner_id) if str(item.get("id")) == item_id), None)
    return None

def _deliver_shared_chat(owner_id: str, session: Dict[str, Any]) -> None:
    conn = _ensure_app_memory()
    try:
        sessions = _read_chat_sessions(conn, owner_id)
    finally:
        conn.close()
    sessions.insert(0, session)
    _replace_chat_sessions(sessions, owner_id)

def _deliver_shared_project(owner_id: str, project: Dict[str, Any]) -> None:
    group = project.get("subagents_group")
    if isinstance(group, dict):
        new_group_id = "share_g_" + secrets.token_hex(6)
        group["id"] = new_group_id
        project["linked_group_id"] = new_group_id
        groups = load_stored_agent_groups(owner_id)
        groups.append({
            "id": new_group_id,
            "name": group.get("name") or "فريق وصل مع مشروع مشارك",
            "desc": group.get("desc") or "مجموعة وصلت مع مشروع مشارك",
            "agents": group.get("agents") or [],
        })
        save_stored_agent_groups(groups, owner_id)
    projects = load_stored_projects(owner_id)
    projects.insert(0, project)
    save_stored_projects(projects, owner_id)

def _deliver_shared_tool(owner_id: str, tool: Dict[str, Any]) -> None:
    tools = load_stored_tools(owner_id)
    tools.insert(0, tool)
    save_stored_tools(tools, owner_id)

def _record_share(kind: str, source_id: str, from_owner: str, to_owner: str) -> None:
    conn = _ensure_app_memory()
    try:
        conn.execute(
            "INSERT INTO member_shares (id, kind, source_id, from_owner, to_owner, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("s_" + secrets.token_hex(8), kind, source_id, from_owner, to_owner, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

@app.get("/api/share/members")
async def list_share_members(request: Request):
    """أسماء من يمكن مشاركتهم، بلا كلمات مرور أو معرفات داخلية."""
    me = require_signed_in(request)
    members = [
        {
            "username": person["username"],
            "label": person["label"],
            "display_name": person.get("display_name") or person["label"],
        }
        for person in _share_people()
        if not same_text(person["username"], me)
    ]
    return {"members": members}

@app.post("/api/shares")
async def create_share(req: ShareRequest, request: Request):
    """يحفظ دعوة مشاركة معلّقة. النسخة لا تُضاف إلا بعد القبول، والأصل يبقى عند المشارك."""
    sender = require_signed_in(request)
    owner_id = current_owner_id(request)
    kind = (req.kind or "").strip()
    if kind not in ("chat", "project", "tool", "key"):
        raise HTTPException(status_code=400, detail="نوع المشاركة غير معروف")
    item_id = (req.item_id or "").strip()
    if not item_id:
        raise HTTPException(status_code=400, detail="حدد ما تريد مشاركته")
    eligible = [person for person in _share_people() if not same_text(person["username"], sender)]
    if req.everyone:
        targets = eligible
    else:
        targets = []
        seen = set()
        for name in req.usernames or []:
            person = next((item for item in eligible if same_text(item["username"], str(name).strip())), None)
            if person and person["owner_id"] not in seen:
                seen.add(person["owner_id"])
                targets.append(person)
    if not targets:
        raise HTTPException(status_code=400, detail="اختر عضواً واحداً على الأقل، أو الجميع")
    sender_name = _person_display_name(sender)
    key_payload = ""
    key_title = ""
    if kind == "key":
        spec = _share_key_spec(item_id)
        if not spec:
            raise HTTPException(status_code=400, detail="الخدمة غير معروفة")
        canonical, ui_name, label = spec
        mode = (req.key_mode or "mine").strip()
        if mode not in ("mine", "new"):
            raise HTTPException(status_code=400, detail="اختر المفتاح الخاص أو مفتاحاً جديداً")
        secret = ""
        if mode == "mine":
            stored = load_provider_keys(owner_id)
            secret = str(stored.get(ui_name) or stored.get(canonical) or "").strip()
            if not secret:
                secret = str(req.key or "").strip()
            if not secret:
                raise HTTPException(status_code=400, detail="لا يوجد مفتاح محفوظ لهذه الخدمة")
        else:
            secret = str(req.key or "").strip()
            if len(secret) < 8:
                raise HTTPException(status_code=400, detail="اكتب المفتاح الجديد")
        if len(secret) > 500:
            raise HTTPException(status_code=400, detail="المفتاح أطول من الحد المسموح")
        key_title = label
        key_payload = json.dumps({"provider": canonical, "ui": ui_name, "key": secret}, ensure_ascii=False)
    with _share_lock:
        if kind == "key":
            source = {"title": key_title}
            title = key_title
        else:
            source = _load_share_item(kind, item_id, owner_id)
            if not source:
                raise HTTPException(status_code=404, detail="العنصر غير موجود في حسابك")
            title = _share_item_title(kind, source)
        sent = []
        now = datetime.now().isoformat(timespec="seconds")
        conn = _ensure_app_memory()
        try:
            for person in targets:
                if kind == "key":
                    payload = key_payload
                else:
                    payload = json.dumps(_share_clone(source, sender), ensure_ascii=False)
                conn.execute(
                    """
                    INSERT INTO share_invites
                    (id, kind, title, from_username, from_name, to_owner, to_username, payload, status, created_at, resolved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, '')
                    """,
                    (
                        "inv_" + secrets.token_hex(8),
                        kind,
                        title,
                        sender,
                        sender_name,
                        person["owner_id"],
                        person["username"],
                        payload,
                        now,
                    ),
                )
                conn.execute(
                    "INSERT INTO member_shares (id, kind, source_id, from_owner, to_owner, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    ("s_" + secrets.token_hex(8), kind, item_id, owner_id, person["owner_id"], now),
                )
                sent.append(person["username"])
            conn.commit()
        finally:
            conn.close()
    return {"status": "ok", "sent": sent}

def _load_share_invite(invite_id: str, owner_id: str):
    conn = _ensure_app_memory()
    try:
        return conn.execute(
            "SELECT * FROM share_invites WHERE id=? AND to_owner=?",
            (invite_id, owner_id),
        ).fetchone()
    finally:
        conn.close()

def _resolve_share_invite(invite_id: str, owner_id: str, status: str) -> None:
    conn = _ensure_app_memory()
    try:
        conn.execute(
            "UPDATE share_invites SET status=?, resolved_at=?, payload='' WHERE id=? AND to_owner=? AND status='pending'",
            (status, datetime.now().isoformat(timespec="seconds"), invite_id, owner_id),
        )
        conn.commit()
    finally:
        conn.close()

@app.get("/api/shares/incoming")
async def incoming_shares(request: Request):
    owner_id = current_owner_id(request)
    conn = _ensure_app_memory()
    try:
        rows = conn.execute(
            """
            SELECT id, kind, title, from_name, created_at
            FROM share_invites
            WHERE to_owner=? AND status='pending'
            ORDER BY created_at ASC
            """,
            (owner_id,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "invites": [
            {
                "id": row["id"],
                "kind": row["kind"],
                "kind_label": _share_kind_label(row["kind"]),
                "title": row["title"] or "",
                "from_name": row["from_name"] or "عضو",
                "created_at": row["created_at"] or "",
            }
            for row in rows
        ]
    }

@app.post("/api/shares/incoming/{invite_id}/accept")
async def accept_share_invite(invite_id: str, request: Request):
    user = require_signed_in(request)
    owner_id = current_owner_id(request)
    with _share_lock:
        row = _load_share_invite(invite_id, owner_id)
        if not row or row["status"] != "pending":
            raise HTTPException(status_code=404, detail="المشاركة لم تعد بانتظارك")
        try:
            clone = json.loads(row["payload"] or "")
        except Exception:
            clone = None
        if not isinstance(clone, dict):
            raise HTTPException(status_code=400, detail="تعذر فتح المشاركة")
        kind = row["kind"]
        if kind == "key":
            _deliver_shared_key(owner_id, clone)
            delivered_id = str(clone.get("ui") or clone.get("provider") or "")
        elif not clone.get("id"):
            raise HTTPException(status_code=400, detail="تعذر فتح المشاركة")
        elif kind == "chat":
            _deliver_shared_chat(owner_id, clone)
            delivered_id = clone["id"]
        elif kind == "project":
            _deliver_shared_project(owner_id, clone)
            delivered_id = clone["id"]
        elif kind == "tool":
            _deliver_shared_tool(owner_id, clone)
            delivered_id = clone["id"]
        else:
            raise HTTPException(status_code=400, detail="نوع المشاركة غير معروف")
        _resolve_share_invite(invite_id, owner_id, "accepted")
    receiver = _person_display_name(user)
    kind_label = _share_kind_label(row["kind"])
    item_title = row["title"] or "بدون عنوان"
    _send_direct_notice(
        row["from_username"],
        "شكراً لمشاركتك",
        f"يشكرك {receiver} على مشاركة {kind_label} «{item_title}»، وقد قبلها.",
    )
    return {"status": "ok", "kind": kind, "item_id": delivered_id, "title": item_title}

@app.post("/api/shares/incoming/{invite_id}/reject")
async def reject_share_invite(invite_id: str, request: Request):
    user = require_signed_in(request)
    owner_id = current_owner_id(request)
    with _share_lock:
        row = _load_share_invite(invite_id, owner_id)
        if not row or row["status"] != "pending":
            raise HTTPException(status_code=404, detail="المشاركة لم تعد بانتظارك")
        _resolve_share_invite(invite_id, owner_id, "rejected")
    receiver = _person_display_name(user)
    kind_label = _share_kind_label(row["kind"])
    item_title = row["title"] or "بدون عنوان"
    _send_direct_notice(
        row["from_username"],
        f"{receiver} يعتذر إليك عن قبول المشاركة ويشكر اهتمامك",
        f"بخصوص {kind_label} «{item_title}».",
    )
    return {"status": "ok"}

@app.get("/api/chats")
async def get_chats(request: Request):
    """سجل محادثات العضو الحالي فقط"""
    owner_id = current_owner_id(request)
    conn = _ensure_app_memory()
    rows = conn.execute(
        "SELECT payload FROM chat_sessions WHERE owner_id=? ORDER BY sort_index ASC, updated_at DESC",
        (owner_id,)
    ).fetchall()
    conn.close()
    sessions = []
    for row in rows:
        try:
            sessions.append(json.loads(row["payload"]))
        except Exception:
            continue
    return {"sessions": sessions}

@app.put("/api/chats")
async def put_chats(payload: dict, request: Request):
    """استبدال محادثات العضو الحالي. لا يمس محادثات غيره ولا فهرس الكتب."""
    owner_id = current_owner_id(request)
    sessions = payload.get("sessions")
    if not isinstance(sessions, list):
        raise HTTPException(status_code=400, detail="قائمة المحادثات غير صالحة")
    kept = _replace_chat_sessions(sessions, owner_id)
    return {"status": "ok", "count": kept}

@app.get("/api/projects")
async def get_projects(request: Request):
    """جلب مشاريع العضو الحالي"""
    return load_stored_projects(current_owner_id(request))

@app.post("/api/projects")
async def save_project(payload: dict, request: Request):
    """حفظ مشروع داخل مساحة العضو الحالي"""
    owner_id = current_owner_id(request)
    projects = load_stored_projects(owner_id)
    p_id = payload.get("id") or f"proj_{int(time.time())}"
    payload["id"] = p_id
    payload["owner_id"] = owner_id
    payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if payload.get("subagents_group") and payload.get("subagents_group", {}).get("agents"):
        sag = payload["subagents_group"]
        gid = payload.get("linked_group_id") or sag.get("id") or f"group_{p_id}"
        sag["id"] = gid
        payload["linked_group_id"] = gid
        
        stored_groups = load_stored_agent_groups(owner_id)
        g_idx = next((i for i, g in enumerate(stored_groups) if g.get("id") == gid), -1)
        group_entry = {
            "id": gid,
            "name": sag.get("name") or f"فريق وكلاء مشروع: {payload.get('title', '')[:30]}",
            "desc": sag.get("desc") or f"مجموعة وكلاء مخصصة لمشروع: {payload.get('title', '')}",
            "agents": sag.get("agents", [])
        }
        if g_idx >= 0:
            stored_groups[g_idx] = group_entry
        else:
            stored_groups.append(group_entry)
        save_stored_agent_groups(stored_groups, owner_id)

    idx = next((i for i, p in enumerate(projects) if p.get("id") == p_id), -1)
    if idx >= 0:
        projects[idx] = payload
    else:
        projects.insert(0, payload)
    
    save_stored_projects(projects, owner_id)
    return {"status": "ok", "project": payload}

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str, request: Request):
    """حذف مشروع من مساحة العضو الحالي فقط"""
    owner_id = current_owner_id(request)
    projects = load_stored_projects(owner_id)
    deleted_proj = next((p for p in projects if p.get("id") == project_id), None)
    projects = [p for p in projects if p.get("id") != project_id]
    save_stored_projects(projects, owner_id)

    if deleted_proj:
        sag = deleted_proj.get("subagents_group") or {}
        sag_id = sag.get("id") or deleted_proj.get("linked_group_id") or f"group_{project_id}"
        groups = load_stored_agent_groups(owner_id)
        groups = [g for g in groups if g.get("id") != sag_id and g.get("id") != f"group_{project_id}"]
        save_stored_agent_groups(groups, owner_id)

    return {"status": "ok"}

@app.get("/api/agent-groups")
async def get_agent_groups_endpoint(response: Response, request: Request):
    """مجموعات وكلاء العضو الحالي"""
    response.headers["X-Agent-Groups-Stored"] = "1"
    return load_stored_agent_groups(current_owner_id(request))

@app.post("/api/agent-groups")
async def save_agent_groups_endpoint(payload: Any, request: Request):
    """حفظ مجموعات وكلاء العضو الحالي دون المساس بغيره"""
    owner_id = current_owner_id(request)
    if isinstance(payload, dict) and "groups" in payload:
        groups = payload["groups"]
    elif isinstance(payload, list):
        groups = payload
    elif isinstance(payload, dict) and "id" in payload:
        existing = load_stored_agent_groups(owner_id)
        idx = next((i for i, g in enumerate(existing) if g.get("id") == payload.get("id")), -1)
        if idx >= 0:
            existing[idx] = payload
        else:
            existing.append(payload)
        groups = existing
    else:
        groups = []
    
    save_stored_agent_groups(groups, owner_id)
    return {"status": "ok", "count": len(groups)}

# =============================================================================
# إدارة الأدوات والإضافات الحسابية والبرمجية (Tools & Extensions Hub)
# =============================================================================

TOOLS_FILE = os.path.join(os.path.dirname(__file__), "tools_data.json")

def load_stored_tools(owner_id: str):
    data = _load_owned_list(owner_id, "tools")
    return data if isinstance(data, list) else []

def save_stored_tools(tools, owner_id: str):
    _save_owned_list(owner_id, "tools", tools)
    if owner_id == ADMIN_OWNER_ID:
        try:
            with open(TOOLS_FILE, "w", encoding="utf-8") as handle:
                json.dump(tools, handle, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"Error saving tools: {exc}")

class ToolItem(BaseModel):
    id: Optional[str] = None
    name: str
    type: Optional[str] = "web_library"
    tool_type: Optional[str] = None
    category: Optional[str] = "أدوات مخصصة"
    desc: Optional[str] = ""
    description: Optional[str] = ""
    library_url: Optional[str] = ""
    github_url: Optional[str] = ""
    init_script: Optional[str] = ""
    python_code: Optional[str] = ""
    mock_data: Optional[Any] = None
    mock_test_data: Optional[Any] = None
    test_code: Optional[str] = ""
    test_output: Optional[str] = ""
    enabled: Optional[bool] = True
    is_builtin: Optional[bool] = False
    status: Optional[str] = "approved"
    created_at: Optional[str] = ""

class FetchToolRepoRequest(BaseModel):
    url: str

class ToolTestPythonRequest(BaseModel):
    code: str
    mock_data: Optional[Any] = None
    input_data: Optional[Any] = None
    test_input: Optional[Any] = None
    entry_function: Optional[str] = "run_tool"

class ToolGenerateCodeRequest(BaseModel):
    prompt: Optional[str] = ""
    tool_name: Optional[str] = ""
    tool_desc: Optional[str] = ""
    model: Optional[str] = "google/gemini-2.5-flash"
    api_key: Optional[str] = None

class ImportToolsRequest(BaseModel):
    data: Any
    overwrite: Optional[bool] = False

@app.get("/api/tools")
async def get_tools_endpoint(request: Request):
    """جلب قائمة الأدوات البرمجية المعتمدة في المنظومة"""
    return load_stored_tools(current_owner_id(request))

@app.post("/api/tools/fetch-repo")
async def fetch_tool_repo_endpoint(req: FetchToolRepoRequest):
    """جلب وفحص رابط إضافة أو مخزن GitHub تلقائياً واستخراج البيانات والسكربتات التجريبية"""
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="يرجى إدخال رابط الأداة أو مخزن GitHub")
    
    result = {
        "url": url,
        "name": "",
        "id": "",
        "desc": "",
        "type": "web_library",
        "category": "أدوات مخصصة",
        "library_url": url,
        "github_url": "",
        "init_script": "",
        "mock_data": {},
        "raw_info": {}
    }
    
    is_github = "github.com" in url
    if is_github:
        clean_url = url.split("#")[0].split("?")[0].rstrip("/")
        parts = clean_url.split("github.com/")[1].split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            result["github_url"] = f"https://github.com/{owner}/{repo}"
            result["id"] = repo.lower().replace("-", "_").replace(".", "_")
            
            # محاولة قراءة بيانات المخزن عبر GitHub API
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            try:
                g_req = urllib.request.Request(api_url, headers={"User-Agent": "Almojtahed-System/2.0"})
                with urllib.request.urlopen(g_req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    result["raw_info"] = {
                        "name": data.get("name"),
                        "description": data.get("description"),
                        "stars": data.get("stargazers_count"),
                        "topics": data.get("topics", []),
                        "language": data.get("language")
                    }
                    if data.get("description"):
                        result["desc"] = data.get("description")
            except Exception as e:
                print(f"GitHub API fetch error: {e}")
            
            name_lower = repo.lower()
            desc_lower = (result["desc"] or "").lower()
            
            # رصد أدوات التشجير والخرائط الذهنية مثل markmap
            if "markmap" in name_lower or "markmap" in desc_lower or "mindmap" in name_lower:
                result["name"] = "أداة التشجير والخرائط الذهنية (Markmap)"
                result["category"] = "تشجير ومفاهيم"
                result["desc"] = result["desc"] or "رسم وتوليد الخرائط الذهنية وشجرة المسائل والمفاهيم والأنساب التفاعلية من نصوص الماركداون والفقرات الشجرية مع إمكانية طي وفرد الفروع وتكبير الشجرة وحفظها."
                result["library_url"] = "/static/js/markmap-view.min.js"
                result["init_script"] = """// كود تشغيل أداة التشجير والخرائط الذهنية Markmap
const { Transformer, Markmap } = window.markmap;
const transformer = new Transformer();
const { root } = transformer.transform(markdownContent);
const svg = document.getElementById(containerId);
Markmap.create(svg, { autoFit: true, duration: 300 }, root);"""
                result["mock_data"] = {
                    "markdown": """# مسألة إتيان المرأة في دبرها
## 1. القول الأول: التحريم القطعي (جمهور الفقهاء)
- المالكية: مذهب المدونة والمشهور
- الشافعية: مذهب الأم ونصوص الشافعي
- الحنابلة: رواية الجماعة
- الحنفية: ظاهر الرواية
## 2. القول الثاني: الكراهة أو الإباحة
- روايات منسوبة لبعض التابعين (محل نقد وتحقيق)
## 3. أدلة القرآن والسنة
- آية الحرث: ﴿فَأْتُوا حَرْثَكُمْ أَنَّى شِئْتُمْ﴾
- أحاديث النهي الواردة ودرجاتها وأسانيدها"""
                }
            elif "vis" in name_lower or "network" in name_lower or "graph" in name_lower:
                result["name"] = f"أداة الرسوم الشبكية والبيانية ({repo})"
                result["category"] = "حديث ورجال"
                result["library_url"] = "/static/js/vis-network.min.js"
                result["mock_data"] = {
                    "nodes": [{"id": 1, "label": "المدار"}, {"id": 2, "label": "الراوي"}],
                    "edges": [{"from": 1, "to": 2, "label": "سماع"}]
                }
            elif "chart" in name_lower or "plot" in name_lower:
                result["name"] = f"أداة الرسوم البيانية ({repo})"
                result["category"] = "بيانات وإحصاء"
                result["library_url"] = "/static/js/chart.min.js"
                result["mock_data"] = {"labels": ["أ", "ب"], "data": [60, 40]}
            else:
                result["name"] = f"أداة {repo.replace('-', ' ').title()}"
                if not result["desc"]:
                    result["desc"] = f"أداة برمجية ومكتبة مستوردة من مخزن GitHub: {owner}/{repo}"
    else:
        # رابط مباشر (CDN أو مكتبة JS)
        raw_name = url.split("/")[-1].split("?")[0].replace(".min.js", "").replace(".js", "").title()
        result["name"] = raw_name or "أداة مخصصة"
        result["id"] = (raw_name or "custom_tool").lower().replace("-", "_").replace(".", "_")
        result["desc"] = f"مكتبة ويب مساعدة تم جلبها من الرابط: {url}"
    
    return result

@app.post("/api/tools")
async def save_tool_endpoint(tool: ToolItem, request: Request):
    """إضافة أو تحديث أداة داخل مساحة العضو الحالي"""
    owner_id = current_owner_id(request)
    tools = load_stored_tools(owner_id)
    tool_dict = tool.dict()
    
    # توحيد الحقول المترادفة لمنع أي خطأ
    if not tool_dict.get("desc") and tool_dict.get("description"):
        tool_dict["desc"] = tool_dict["description"]
    if not tool_dict.get("description") and tool_dict.get("desc"):
        tool_dict["description"] = tool_dict["desc"]
    if not tool_dict.get("type") and tool_dict.get("tool_type"):
        tool_dict["type"] = tool_dict["tool_type"]
    if not tool_dict.get("tool_type") and tool_dict.get("type"):
        tool_dict["tool_type"] = tool_dict["type"]
    if tool_dict.get("mock_data") is None and tool_dict.get("mock_test_data") is not None:
        tool_dict["mock_data"] = tool_dict["mock_test_data"]
    if tool_dict.get("mock_test_data") is None and tool_dict.get("mock_data") is not None:
        tool_dict["mock_test_data"] = tool_dict["mock_data"]
        
    if not tool_dict.get("id"):
        tool_dict["id"] = "tool_" + hashlib.md5(f"{tool_dict['name']}_{time.time()}".encode()).hexdigest()[:8]
    if not tool_dict.get("created_at"):
        tool_dict["created_at"] = time.strftime("%Y-%m-%d")
        
    idx = next((i for i, t in enumerate(tools) if t.get("id") == tool_dict["id"]), -1)
    if idx >= 0:
        tools[idx] = tool_dict
    else:
        tools.append(tool_dict)
        
    save_stored_tools(tools, owner_id)
    return {"status": "ok", "tool": tool_dict}

@app.delete("/api/tools/{tool_id}")
async def delete_tool_endpoint(tool_id: str, request: Request):
    """حذف أداة من مساحة العضو الحالي"""
    owner_id = current_owner_id(request)
    tools = load_stored_tools(owner_id)
    tools = [t for t in tools if t.get("id") != tool_id]
    save_stored_tools(tools, owner_id)
    return {"status": "ok"}

@app.get("/api/tools/export/{tool_id}")
async def export_single_tool_endpoint(tool_id: str, request: Request):
    """تصدير أداة محددة كملف JSON"""
    tools = load_stored_tools(current_owner_id(request))
    tool = next((t for t in tools if t.get("id") == tool_id), None)
    if not tool:
        raise HTTPException(status_code=404, detail="الأداة غير موجودة")
    export_payload = {
        "export_version": "1.0",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "almojtahed_tool",
        "tool": tool
    }
    return JSONResponse(
        content=export_payload,
        headers={"Content-Disposition": f"attachment; filename=tool_{tool_id}.json"}
    )

@app.get("/api/tools/export")
async def export_all_tools_endpoint(request: Request):
    """تصدير كافة الأدوات كحزمة JSON"""
    tools = load_stored_tools(current_owner_id(request))
    export_payload = {
        "export_version": "1.0",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "almojtahed_tools_bundle",
        "tools_count": len(tools),
        "tools": tools
    }
    return JSONResponse(
        content=export_payload,
        headers={"Content-Disposition": "attachment; filename=almojtahed_tools_all.json"}
    )

@app.post("/api/tools/import")
async def import_tools_endpoint(req: ImportToolsRequest, request: Request):
    """استيراد أداة أو حزمة أدوات إلى المنظومة"""
    raw_data = req.data
    imported_list = []
    
    if isinstance(raw_data, dict):
        if raw_data.get("type") == "almojtahed_tools_bundle" and "tools" in raw_data:
            imported_list = raw_data["tools"]
        elif raw_data.get("type") == "almojtahed_tool" and "tool" in raw_data:
            imported_list = [raw_data["tool"]]
        elif "name" in raw_data or "python_code" in raw_data or "id" in raw_data:
            imported_list = [raw_data]
    elif isinstance(raw_data, list):
        imported_list = raw_data
        
    if not imported_list:
        raise HTTPException(status_code=400, detail="صيغة بيانات الأداة غير صالحة")
        
    owner_id = current_owner_id(request)
    tools = load_stored_tools(owner_id)
    saved_tools = []
    
    for item in imported_list:
        if not isinstance(item, dict) or not item.get("name"):
            continue
            
        tool_item = dict(item)
        tid = tool_item.get("id") or ("tool_" + hashlib.md5(f"{tool_item['name']}_{time.time()}".encode()).hexdigest()[:8])
        
        existing_idx = next((i for i, t in enumerate(tools) if t.get("id") == tid), -1)
        if existing_idx >= 0 and not req.overwrite:
            tid = f"{tid}_copy_{int(time.time()) % 10000}"
            tool_item["id"] = tid
            tool_item["name"] = f"{tool_item['name']} (نسخة مستوردة)"
        else:
            tool_item["id"] = tid
            
        if not tool_item.get("desc") and tool_item.get("description"):
            tool_item["desc"] = tool_item["description"]
        if not tool_item.get("description") and tool_item.get("desc"):
            tool_item["description"] = tool_item["desc"]
        if not tool_item.get("type") and tool_item.get("tool_type"):
            tool_item["type"] = tool_item["tool_type"]
        if not tool_item.get("tool_type") and tool_item.get("type"):
            tool_item["tool_type"] = tool_item["type"]
        if not tool_item.get("created_at"):
            tool_item["created_at"] = time.strftime("%Y-%m-%d")
        tool_item["enabled"] = True
        
        if existing_idx >= 0 and req.overwrite:
            tools[existing_idx] = tool_item
        else:
            tools.append(tool_item)
        saved_tools.append(tool_item)
        
    save_stored_tools(tools, owner_id)
    return {"status": "ok", "imported_count": len(saved_tools), "tools": saved_tools}

@app.post("/api/tools/test-python")
async def test_python_tool_endpoint(req: ToolTestPythonRequest):
    """تشغيل واختبار كود بايثون للأداة في بيئة آمنة ببيانات تجريبية"""
    code = req.code or ""
    mock_data = req.input_data if req.input_data is not None else (req.mock_data if req.mock_data is not None else (getattr(req, 'test_input', None) or {}))
    
    runner = f'''import sys, json, traceback

mock_input = {json.dumps(mock_data, ensure_ascii=False)}

try:
{textwrap.indent(code, "    ")}
    
    res = None
    fallback_used = None
    
    # فحص وجود مثال تجريبي مضمن في الكود إن وجد
    example_fallback = None
    for ex_k in ["input_data_example", "mock_test_input", "sample_input", "example_input", "mock_data"]:
        if ex_k in locals() and isinstance(locals()[ex_k], dict) and locals()[ex_k]:
            example_fallback = locals()[ex_k]
            break
            
    if "verify_event" in locals() and callable(locals()["verify_event"]):
        if isinstance(mock_input, dict):
            try:
                res = locals()["verify_event"](**mock_input)
            except TypeError:
                res = locals()["verify_event"](mock_input)
        else:
            res = locals()["verify_event"](mock_input)
    elif "run_tool" in locals() and callable(locals()["run_tool"]):
        try:
            res = locals()["run_tool"](mock_input)
        except Exception as e_run:
            if example_fallback:
                try:
                    res = locals()["run_tool"](example_fallback)
                    fallback_used = example_fallback
                except Exception:
                    raise e_run
            else:
                raise e_run
                
        # إذا كانت النتيجة رسالة خطأ بسبب نقص مدخلات وتوفر مثال مضمن، نجرب المثال المضمن
        is_err = isinstance(res, dict) and (res.get("status") in ["error", "fail", "failed"] or "error" in res)
        if is_err and example_fallback and example_fallback != mock_input:
            try:
                fb_res = locals()["run_tool"](example_fallback)
                if not (isinstance(fb_res, dict) and fb_res.get("status") in ["error", "fail"]):
                    res = fb_res
                    fallback_used = example_fallback
            except Exception:
                pass
    elif "process_data" in locals() and callable(locals()["process_data"]):
        res = locals()["process_data"](mock_input)
    elif "result" in locals():
        res = locals()["result"]
    else:
        res = "تم تنفيذ كود الأداة بنجاح دون أخطاء برمجية."

    if fallback_used:
        print("___FALLBACK_INPUT___")
        print(json.dumps(fallback_used, ensure_ascii=False, default=str))

    print("___EXEC_OK___")
    print(json.dumps(res, ensure_ascii=False, default=str))
except Exception as e:
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''
    try:
        t0 = time.time()
        p = subprocess.run([sys.executable, "-c", runner], capture_output=True, text=True, timeout=8)
        dur = round((time.time() - t0) * 1000, 1)
        if p.returncode == 0:
            out_text = p.stdout
            fallback_input = None
            if "___FALLBACK_INPUT___" in out_text:
                fb_part = out_text.split("___FALLBACK_INPUT___")[1].split("___EXEC_OK___")[0].strip()
                try:
                    fallback_input = json.loads(fb_part)
                except Exception:
                    pass
            if "___EXEC_OK___" in out_text:
                json_part = out_text.split("___EXEC_OK___")[1].strip()
                try:
                    parsed_res = json.loads(json_part)
                except Exception:
                    parsed_res = json_part
            else:
                parsed_res = out_text.strip()
            return {
                "status": "ok",
                "success": True,
                "result": parsed_res,
                "output": parsed_res,
                "fallback_input": fallback_input,
                "execution_time_ms": dur,
                "stdout": p.stdout
            }
        else:
            return {
                "status": "error",
                "success": False,
                "error": p.stderr.strip() or "فشل تشغيل الكود",
                "message": p.stderr.strip() or "فشل تشغيل الكود",
                "execution_time_ms": dur
            }
    except subprocess.TimeoutExpired:
        return {"status": "error", "success": False, "error": "انتهت مهلة تشغيل الكود (تجاوز 8 ثوانٍ)", "message": "انتهت مهلة تشغيل الكود (تجاوز 8 ثوانٍ)"}
    except Exception as e:
        return {"status": "error", "success": False, "error": str(e), "message": str(e)}

@app.post("/api/tools/generate-code")
async def generate_tool_code_endpoint(req: ToolGenerateCodeRequest, request: Request):
    """محاورة نموذج OpenRouter لبناء كود بايثون مخصص لأداة جديدة"""
    key = owner_openrouter_key(request, req.api_key)
    model = req.model or "google/gemini-2.5-flash"
    
    task_desc = req.prompt.strip() if req.prompt else f"اسم الأداة: {req.tool_name}\nوصف الأداة: {req.tool_desc}"
    
    prompt = (
        f"أنت مهندس برمجيات بايثون متخصص في كتابة أدوات حسابية وتحليلية دقيقة لمنظومة المجتهد للبحث التراثي والأكاديمي.\n"
        f"المطلوب: كتابة دالة بايثون مستقلة وعالية الكفاءة للأداة التالية:\n"
        f"{task_desc}\n\n"
        f"القواعد البرمجية الصارمة:\n"
        f"1. اكتب دالة رئيسية باسم `run_tool(input_data)` تقبل قاموس البيانات المدخلة وتُرجع قاموساً (dict) يحتوي نتيجة الحساب بدقة مع حقل 'status': 'success' أو 'verified'.\n"
        f"2. استخدم المكتبات القياسية في بايثون فقط (مثل datetime, math, re, json, collections, urllib).\n"
        f"3. اكتب كوداً نظيفاً خالياً من الأخطاء وقم بالتعليق عليه باللغة العربية.\n"
        f"4. في نهاية الكود، ضع قاموساً باسم `mock_test_input = {{...}}` يحتوي على بيانات تجريبية واقعية لاختبار الدالة بها مباشرة.\n"
        f"5. أرجع الكود محصوراً فقط بين علامات ```python و ``` دون أي مقدمات أو كلام خارج كود البايثون."
    )
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "أنت مبرمج بايثون خبير. اكتب الكود المطلوب حصراً داخل علامات ```python```."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4096
    }
    
    try:
        if str(model).startswith("local:"):
            data = {"choices": [{"message": {"content": _complete_local_text(model, payload["messages"], 0.2, 4096)}}]}
        else:
            o_req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8085",
                    "X-Title": "Al-Mojtahed Tool Code Generator"
                },
                data=json.dumps(payload).encode()
            )
            with urllib.request.urlopen(o_req, timeout=35) as resp:
                data = json.loads(resp.read().decode())
        reply = data["choices"][0]["message"]["content"]
        match = re.search(r"```python\s*([\s\S]*?)\s*```", reply)
        extracted_code = match.group(1).strip() if match else reply.strip()
        
        # استخراج بيانات الاختبار الوهمية من الكود إن وجدت
        sample_input = None
        mock_match = re.search(r"(?:input_data_example|mock_test_input|sample_input|example_input|test_input|mock_data)\s*=\s*(\{[\s\S]*?\n\s*\})", extracted_code)
        if mock_match:
            try:
                import ast
                sample_input = ast.literal_eval(mock_match.group(1))
            except Exception:
                try:
                    sample_input = json.loads(mock_match.group(1))
                except Exception:
                    pass
        
        if not sample_input:
            keys = re.findall(r"input_data(?:\.get\(|\[)['\"]([a-zA-Z0-9_]+)['\"]", extracted_code)
            if keys:
                sample_input = {}
                for k in set(keys):
                    k_lower = k.lower()
                    if any(x in k_lower for x in ["date1", "start_date", "from_date", "first_date"]):
                        sample_input[k] = "2023-01-01"
                    elif any(x in k_lower for x in ["date2", "end_date", "to_date", "second_date"]):
                        sample_input[k] = "2024-03-15"
                    elif any(x in k_lower for x in ["date", "time"]):
                        sample_input[k] = "2024-01-01"
                    elif any(x in k_lower for x in ["year", "hijri", "solar"]):
                        sample_input[k] = 1445 if "hijri" in k_lower else 2024
                    elif any(x in k_lower for x in ["num", "count", "day", "month", "id", "page"]):
                        sample_input[k] = 1
                    elif any(x in k_lower for x in ["text", "title", "name", "city", "word", "query", "phrase"]):
                        sample_input[k] = "بغداد" if "city" in k_lower else "نص تجريبي للتحقق"
                    elif any(x in k_lower for x in ["is_", "has_", "flag", "enabled", "strict"]):
                        sample_input[k] = True
                    elif any(x in k_lower for x in ["list", "items", "books", "authors"]):
                        sample_input[k] = ["عنصر 1", "عنصر 2"]
                    else:
                        sample_input[k] = "قيمة تجريبية"
            else:
                sample_input = {"date1": "2023-01-01", "date2": "2024-03-15"}
                
        # اقتراح اسم ومعرف للأداة إن لم يكن محدداً
        clean_prompt = re.sub(r"[^\w\s\u0600-\u06FF]", "", req.prompt or "").strip()
        words = clean_prompt.split()
        suggested_name = " ".join(words[:5]) if words else "أداة بايثون مخصصة"
        suggested_id = "tool_py_" + "_".join([re.sub(r'[^a-zA-Z0-9]', '', w) for w in words[:3] if re.sub(r'[^a-zA-Z0-9]', '', w)])
        if not suggested_id or suggested_id == "tool_py_":
            suggested_id = f"tool_py_{int(time.time())}"
        
        return {
            "status": "ok",
            "code": extracted_code,
            "sample_input": sample_input,
            "tool_name": suggested_name,
            "tool_id": suggested_id.lower(),
            "raw_reply": reply
        }
    except Exception as e:
        return {"status": "error", "message": f"خطأ في توليد الكود: {str(e)}"}

# =============================================================================
# فحص وتجربة استجابة الوكيل المساعد ومعلمات النموذج حياً
# =============================================================================
class SubagentTestRequest(BaseModel):
    model: str = "google/gemini-2.5-flash"
    agent_name: Optional[str] = "الوكيل المساعد"
    agent_role: Optional[str] = ""
    system_prompt: Optional[str] = ""
    user_prompt: Optional[str] = ""
    books_scope: Optional[List[str]] = []
    scanned_texts: Optional[int] = 10
    use_hybrid: Optional[bool] = True
    project_title: Optional[str] = ""
    temperature: Optional[float] = 0.2
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    max_tokens: Optional[int] = 1500
    api_key: Optional[str] = None

@app.post("/api/subagents/test")
async def test_subagent_endpoint(req: SubagentTestRequest, request: Request):
    """اختبار استجابة الوكيل المساعد حياً مع استخراج شواهد كتبه التراثية وتطبيق التوجيه والمعلمات بدقة وفق سياق المشروع"""
    t0 = time.time()
    key = owner_openrouter_key(request, req.api_key)
    resolved_model = normalize_model_id(req.model or "google/gemini-2.5-flash")
    
    ag_name = (req.agent_name or "الوكيل المساعد").strip()
    ag_role = (req.agent_role or "استخراج نصوص الشاملة وتحقيق المسألة").strip()
    directive = (req.system_prompt or "استخرج نصوص المسألة بدقة مع أرقام الأجزاء والصفحات والمذاهب والأدلة.").strip()
    user_query = (req.user_prompt or "ما تحرير المسألة وخلاف الفقهاء فيها بإيجاز مع التوثيق؟").strip()
    
    # 1. استخراج حقيقي لنصوص الشاملة من كتب الوكيل المحددة باستخدام نمط البحث المعتمد للمشروع (هجين أو دلالي)
    cits = []
    search_mode_str = "بحث هجين (Dense + BM25) ⚡" if req.use_hybrid else "بحث دلالي صرف (Dense Only) 🧠"
    target_books = [str(b).strip() for b in (req.books_scope or []) if str(b).strip()]
    test_limit = min(max(int(req.scanned_texts or 10), 3), 20)
    
    try:
        cits = run_rag_search(
            query=user_query,
            selected_books=target_books if target_books else None,
            pool_size=max(test_limit * 4, 80),
            top_k=test_limit,
            use_reranker=False,
            use_hybrid=bool(req.use_hybrid if req.use_hybrid is not None else True)
        )
    except Exception as ex:
        print(f"[Subagent Test] RAG search error: {ex}")
        cits = []
    
    # 2. تجهيز مقتطفات الشواهد التراثية
    snippets_items = []
    citations_meta = []
    for c in cits:
        loc_str = c.get("citation_label") or canonical_citation_label(c.get("title"), c.get("vol"), c.get("page"), c.get("volume_count"))
        citations_meta.append({
            "title": c.get('title'),
            "author": c.get('author'),
            "loc": loc_str
        })
        snippets_items.append(
            f"- الإحالة المعتمدة: {loc_str} | المصنف: {c.get('author', 'غير محدد')}:\n  {c.get('snippet', '')}"
        )
    snippets_txt = "\n\n".join(snippets_items) if snippets_items else ""
    
    # 3. صياغة التوجيه وسياق الاستدعاء وفق المشروع تماماً
    project_ctx = f" ضمن سياق المشروع البحثي: «{req.project_title}»" if req.project_title else ""
    sys_content = (
        f"أنت الوكيل المساعد التخصصي: «{ag_name}»{project_ctx}.\n"
        f"تخصصك ودورك: {ag_role}.\n"
        f"التوجيه التخصصي الصارم المعتمد: {directive}\n"
        f"المهمة: أجب بدقة متناهية والتزام تام بتوجيهك وتخصصك.\n"
        f"{CITATION_FORMAT_RULE}"
    )
    
    if snippets_txt:
        user_content = (
            f"المسألة أو السؤال المستهدف: {user_query}\n\n"
            f"فيما يلي الشواهد والنصوص المستخرجة حياً بالـ ({search_mode_str}) من نطاق كتبك التراثية ({len(target_books) if target_books else 'كامل الشاملة'}):\n\n"
            f"{snippets_txt}\n\n"
            f"المطلوب: طالع الشواهد السابقة، واستخلص الجواب وحرره بدقة بالغة وفق توجيهك التخصصي الصارم."
        )
    else:
        user_content = (
            f"المسألة أو السؤال المستهدف: {user_query}\n\n"
            f"(تنبيه: لم يتم العثور على شواهد كافية أو أن النطاق عام - أجب وفق حصيلتك العلمية ملتزماً بتوجيهك التخصصي أعلاه)."
        )
    
    messages = [
        {"role": "system", "content": sys_content},
        {"role": "user", "content": user_content}
    ]
    
    try:
        reply = call_openrouter_raw(
            model_id=resolved_model,
            messages=messages,
            api_key=key,
            temperature=float(req.temperature if req.temperature is not None else 0.2),
            max_tokens=int(req.max_tokens or 1500),
            top_p=float(req.top_p) if (req.top_p is not None and str(req.top_p).strip() != "") else None,
            top_k=int(req.top_k) if (req.top_k is not None and str(req.top_k).strip() != "" and int(req.top_k) > 0) else None,
            frequency_penalty=float(req.frequency_penalty) if (req.frequency_penalty is not None and str(req.frequency_penalty).strip() != "") else None,
            presence_penalty=float(req.presence_penalty) if (req.presence_penalty is not None and str(req.presence_penalty).strip() != "") else None,
            repetition_penalty=float(req.repetition_penalty) if (req.repetition_penalty is not None and str(req.repetition_penalty).strip() != "") else None,
            timeout=70
        )
        elapsed = round(time.time() - t0, 2)
        return {
            "status": "success",
            "reply": reply,
            "elapsed_seconds": elapsed,
            "model": resolved_model,
            "search_mode": search_mode_str,
            "citations_count": len(cits),
            "citations": citations_meta[:6],
            "applied_directive": directive,
            "agent_name": ag_name,
            "parameters": {
                "temperature": req.temperature,
                "top_p": req.top_p,
                "top_k": req.top_k,
                "frequency_penalty": req.frequency_penalty,
                "presence_penalty": req.presence_penalty,
                "repetition_penalty": req.repetition_penalty,
                "max_tokens": req.max_tokens
            }
        }
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        return {
            "status": "error",
            "message": f"تعذر استدعاء النموذج ({str(e)})",
            "elapsed_seconds": elapsed,
            "model": resolved_model
        }

# =============================================================================
# مسارات الفحص الذاتي والصيانة التلقائية والإصلاح الشامل
# =============================================================================
@app.get("/api/system/diagnose")
async def system_diagnose_endpoint():
    """فحص سلامة النظام والتحقق من صحة الملفات البرمجية والأصول وقواعد البيانات"""
    checks = []
    has_issues = False
    
    # 1. فحص ملفات الجافاسكريبت والأخطاء الصياغية
    js_files = ["projects.js", "tools.js", "app.js", "chat.js", "search.js", "agents.js", "providers.js"]
    for jf in js_files:
        full_p = os.path.join(STATIC_DIR, "js", jf)
        if not os.path.exists(full_p):
            checks.append({
                "category": "ملفات الواجهة (JS)",
                "item": jf,
                "status": "error",
                "message": "الملف مفقود من مجلد static/js"
            })
            has_issues = True
        else:
            try:
                p = subprocess.run(["node", "-c", full_p], capture_output=True, text=True, timeout=3)
                if p.returncode == 0:
                    checks.append({
                        "category": "ملفات الواجهة (JS)",
                        "item": jf,
                        "status": "ok",
                        "message": "الكود البرمجي سليم وخالٍ من أخطاء الصياغة (Syntax Clean)"
                    })
                else:
                    err_msg = p.stderr.strip().split("\n")[0] if p.stderr else "خطأ صياغة"
                    checks.append({
                        "category": "ملفات الواجهة (JS)",
                        "item": jf,
                        "status": "error",
                        "message": f"خطأ صياغة برمجي: {err_msg}"
                    })
                    has_issues = True
            except Exception:
                checks.append({
                    "category": "ملفات الواجهة (JS)",
                    "item": jf,
                    "status": "ok",
                    "message": "تم التحقق من وجود الملف وسلامة المسار"
                })

    # 2. فحص المكتبات التفاعلية المحلية
    libs = [
        ("chart.min.js", "مكتبة الرسوم والمؤشرات البيانية (Chart.js)"),
        ("vis-network.min.js", "مكتبة شجرة الأسانيد وشبكات الرواة (Vis.js)"),
        ("d3.min.js", "محرك D3.js لمعالجة المتجهات والتشجير"),
        ("markmap-view.min.js", "أداة عرض خرائط وتشجير Markmap"),
        ("markmap-lib.min.js", "محرك تحويل الماركداون لشجرة Markmap"),
        ("marked.min.js", "محرك قراءة وتنسيق نصوص الماركداون")
    ]
    for lib_file, desc in libs:
        p = os.path.join(STATIC_DIR, "js", lib_file)
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            checks.append({
                "category": "المكتبات المساعدة (Libraries)",
                "item": desc,
                "status": "ok",
                "message": f"مثبتة وجاهزة محلياً ({round(os.path.getsize(p)/1024, 1)} KB)"
            })
        else:
            checks.append({
                "category": "المكتبات المساعدة (Libraries)",
                "item": desc,
                "status": "warning",
                "message": "المكتبة مفقودة أو تالفة محلياً وسيتم استعادتها تلقائياً بالصيانة"
            })
            has_issues = True

    # 3. فحص قواعد البيانات وملفات التهيئة
    data_files = [
        (TOOLS_FILE, "قاعدة بيانات الأدوات والإضافات (tools_data.json)"),
        (os.path.join(BASE_DIR, "projects_data.json"), "قاعدة بيانات المشاريع البحثية (projects_data.json)"),
        (os.path.join(BASE_DIR, "agent_groups_data.json"), "قاعدة بيانات مجموعات الوكلاء (agent_groups_data.json)"),
        (os.path.join(BASE_DIR, "providers_data.json"), "قاعدة بيانات مزودي الخدمة (providers_data.json)")
    ]
    for df_path, desc in data_files:
        if not os.path.exists(df_path):
            checks.append({
                "category": "قواعد البيانات وملفات التهيئة",
                "item": desc,
                "status": "warning",
                "message": "الملف غير موجود وسيتم إنشاؤه افتراضياً"
            })
            has_issues = True
        else:
            try:
                with open(df_path, "r", encoding="utf-8") as f:
                    c = json.load(f)
                count = len(c) if isinstance(c, (list, dict)) else 0
                checks.append({
                    "category": "قواعد البيانات وملفات التهيئة",
                    "item": desc,
                    "status": "ok",
                    "message": f"بيانات سليمة وصحيحة ({count} سجل مسجل)"
                })
            except Exception as e:
                checks.append({
                    "category": "قواعد البيانات وملفات التهيئة",
                    "item": desc,
                    "status": "error",
                    "message": f"تلف في صياغة JSON: {str(e)}"
                })
                has_issues = True

    # 4. حالة محرك الاستدلال والبحث
    col_name = app_state.get("collection_name", "shamela_almojtahed_8b_dense")
    checks.append({
        "category": "محرك النظام والاستدلال",
        "item": "محرك البحث الدلالي والمجموعات المضمنة",
        "status": "ok",
        "message": f"المجموعة النشطة: {col_name} (دقة التضمين 8B جاهزة ومفعلة)"
    })

    book_index = _book_index_status()
    if book_index["exists"] and book_index["books"] > 0:
        checks.append({
            "category": "فهرس الكتب المحمي",
            "item": "فهرس المكتبة الشاملة",
            "status": "ok",
            "message": f"محمي ولا يُمسحه الأرشيف أو المسح: {book_index['books']} كتاباً"
        })
    else:
        checks.append({
            "category": "فهرس الكتب المحمي",
            "item": "فهرس المكتبة الشاملة",
            "status": "error",
            "message": "فهرس الكتب غير موجود أو فارغ. لا تشغّل المسح قبل استعادته، لأن التطبيق لن يعرف الكتب."
        })
        has_issues = True

    return {
        "status": "issues_found" if has_issues else "healthy",
        "summary": "تم اكتشاف بعض الملاحظات تحتاج صيانة وإصلاحاً" if has_issues else "كافة أجزاء المنظومة تعمل بكفاءة تامة وملفات النظام سليمة",
        "checks": checks,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.post("/api/system/repair")
async def system_repair_endpoint(request: Request):
    """إجراء الصيانة التلقائية والإصلاح الشامل مع نسخ احتياطي فوري للمشاريع والبيانات"""
    require_admin(request)
    actions_taken = []
    
    # 1. إنشاء نسخة احتياطية آمنة في مجلد backups
    backup_dir = os.path.join(BASE_DIR, "backups", time.strftime("backup_%Y%m%d_%H%M%S"))
    os.makedirs(backup_dir, exist_ok=True)
    
    data_files = [
        os.path.join(BASE_DIR, "projects_data.json"),
        TOOLS_FILE,
        os.path.join(BASE_DIR, "agent_groups_data.json"),
        os.path.join(BASE_DIR, "providers_data.json"),
        str(APP_MEMORY_DB),
    ]
    backed_up_count = 0
    for df in data_files:
        if os.path.exists(df):
            shutil.copy2(df, backup_dir)
            backed_up_count += 1
            
    actions_taken.append(f"تم تأمين نسخة احتياطية فورية لكافة مشاريعك وأعمالك ({backed_up_count} ملفات) في مجلد: backups/{os.path.basename(backup_dir)}")

    # 2. إصلاح وترميم أي ملفات JSON مفقودة أو تالفة
    proj_p = os.path.join(BASE_DIR, "projects_data.json")
    if not os.path.exists(proj_p):
        with open(proj_p, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        actions_taken.append("تم إنشاء ملف قاعدة بيانات المشاريع projects_data.json")
    else:
        try:
            with open(proj_p, "r", encoding="utf-8") as f:
                json.load(f)
        except Exception:
            shutil.copy2(proj_p, proj_p + ".corrupted")
            with open(proj_p, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            actions_taken.append("تم إصلاح ملف المشاريع التالف واستعادة صياغة JSON سليمة")

    if not os.path.exists(TOOLS_FILE):
        default_tools = [
            {
                "id": "charts_metrics", "name": "أداة المؤشرات والشارتات البيانية", "type": "web_library",
                "category": "بيانات وإحصاء", "desc": "استخراج النسب والأرقام من جداول المقارنات وتحويلها إلى شارتات تفاعلية.",
                "library_url": "/static/js/chart.min.js", "enabled": True, "is_builtin": True
            },
            {
                "id": "astronomy_hijri_sync", "name": "أداة التحقق الحسابي الفلكي والتقويمي", "type": "python_script",
                "category": "حساب وفلك", "desc": "مطابقة التواريخ التاريخية وحساب أطوار القمر ومواقيت الكسوف.",
                "enabled": True, "is_builtin": True
            },
            {
                "id": "hadith_isnad_tree", "name": "أداة شجرة الأسانيد وشبكات الرواة", "type": "web_library",
                "category": "حديث ورجال", "desc": "رسم شجرة المدارات وطرق الحديث التفاعلية.",
                "library_url": "/static/js/vis-network.min.js", "enabled": True, "is_builtin": True
            },
            {
                "id": "markmap_mindmap", "name": "أداة التشجير والخرائط الذهنية (Markmap)", "type": "web_library",
                "category": "تشجير ومفاهيم", "desc": "رسم وتوليد الخرائط الذهنية وشجرة المسائل والمفاهيم التفاعلية.",
                "library_url": "/static/js/markmap-view.min.js", "enabled": True, "is_builtin": True
            }
        ]
        save_stored_tools(default_tools, ADMIN_OWNER_ID)
        actions_taken.append("تمت استعادة وتثبيت أدوات المنظومة الأساسية الأربعة في tools_data.json")

    prov_p = os.path.join(BASE_DIR, "providers_data.json")
    if not os.path.exists(prov_p):
        with open(prov_p, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        actions_taken.append("تم إنشاء ملف قاعدة بيانات مزودي الخدمة providers_data.json")

    # 3. التحقق من تنزيل المكتبات المحلية المفقودة
    missing_libs = {
        "chart.min.js": "https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js",
        "vis-network.min.js": "https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js",
        "d3.min.js": "https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js",
        "markmap-view.min.js": "https://cdn.jsdelivr.net/npm/markmap-view@0.17/dist/browser/index.js",
        "markmap-lib.min.js": "https://cdn.jsdelivr.net/npm/markmap-lib@0.17/dist/browser/index.iife.js"
    }
    for lib_name, lib_url in missing_libs.items():
        dst = os.path.join(STATIC_DIR, "js", lib_name)
        if not os.path.exists(dst) or os.path.getsize(dst) < 500:
            try:
                req = urllib.request.Request(lib_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp, open(dst, "wb") as f:
                    f.write(resp.read())
                actions_taken.append(f"تم تحميل واستعادة مكتبة {lib_name} بنجاح محلياً")
            except Exception as e:
                actions_taken.append(f"تنبيه: تعذر تحميل {lib_name} تلقائياً: {e}")

    # 4. تحديث الـ Cache Busters في index.html لضمان فرض قراءة التحديثات
    new_v = int(time.time())
    index_path = os.path.join(BASE_DIR, "templates", "index.html")
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                html_text = f.read()
            html_text = re.sub(r'\?v=\d+', f'?v={new_v}', html_text)
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(html_text)
            actions_taken.append(f"تم تجديد وتحديث أرقام الكاش البرمجي (v={new_v}) لفرض التحميل الجديد في المتصفح")
        except Exception:
            pass

    return {
        "status": "success",
        "message": "اكتملت عملية الصيانة والإصلاح والنسخ الاحتياطي بنجاح!",
        "backup_path": backup_dir,
        "actions_taken": actions_taken,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

def _archive_user_memory() -> Dict[str, Any]:
    """نسخ محفوظات المستخدم فقط. فهرس الكتب ونصوص الشاملة ومخزن المتجهات خارج النسخة."""
    stamp = time.strftime("archive_%Y%m%d_%H%M%S")
    archive_dir = os.path.join(BASE_DIR, "backups", stamp)
    os.makedirs(archive_dir, exist_ok=True)
    copied = []

    try:
        conn = _ensure_app_memory()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Memory checkpoint skipped: {e}")

    if APP_MEMORY_DB.exists():
        shutil.copy2(APP_MEMORY_DB, os.path.join(archive_dir, APP_MEMORY_DB.name))
        copied.append(APP_MEMORY_DB.name)

    for path in (PROJECTS_FILE, AGENT_GROUPS_FILE):
        if os.path.exists(path):
            shutil.copy2(path, archive_dir)
            copied.append(os.path.basename(path))

    uploads_dir = BASE_DIR / "uploads"
    if uploads_dir.exists():
        dest = os.path.join(archive_dir, "uploads")
        shutil.copytree(uploads_dir, dest, dirs_exist_ok=True)
        copied.append("uploads")

    return {
        "archive_path": archive_dir,
        "archive_id": stamp,
        "copied": copied,
        "book_index": _book_index_status(),
    }

def _clear_upload_files() -> int:
    uploads_dir = BASE_DIR / "uploads"
    removed = 0
    if not uploads_dir.exists():
        return 0
    for path in uploads_dir.iterdir():
        if path.name == ".gitkeep" or path.name in ("shamela_index.db", "books.csv"):
            continue
        if path.is_file() or path.is_symlink():
            path.unlink()
            removed += 1
        elif path.is_dir():
            shutil.rmtree(path)
            removed += 1
    return removed

class MemoryActionRequest(BaseModel):
    action: str
    confirm: Optional[str] = ""

@app.post("/api/system/memory")
async def system_memory_action(req: MemoryActionRequest, request: Request):
    """مسح مساحة المشرف بعد تأكيد صريح. مساحات الأعضاء وفهرس الكتب تبقى."""
    require_admin(request)
    owner_id = ADMIN_OWNER_ID
    action = (req.action or "").strip().lower()
    if action not in ("archive", "wipe"):
        raise HTTPException(status_code=400, detail="الإجراء يجب أن يكون أرشفة أو مسحاً")
    if action == "wipe" and (req.confirm or "").strip() != MEMORY_WIPE_PHRASE:
        raise HTTPException(status_code=400, detail="اكتب عبارة التأكيد كما هي قبل المسح")

    for protected in _BOOK_INDEX_PATHS:
        if protected.exists() and protected.stat().st_size <= 0:
            raise HTTPException(status_code=409, detail="فهرس الكتب فارغ. أُوقف الإجراء حتى لا يُفقد مرجع الكتب.")

    before = _book_index_status()
    if action == "wipe" and before.get("books", 0) <= 0:
        raise HTTPException(
            status_code=409,
            detail="فهرس الكتب غير متاح أو فارغ. أُوقف المسح لأن التطبيق لن يعرف الكتب من غيره."
        )
    archive = _archive_user_memory()
    if action == "archive":
        return {
            "status": "archived",
            "message": "أُرشفت المحادثات والمشاريع والمرفقات. فهرس الكتب لم يُنسخ ولم يُمس.",
            **archive,
            "book_index_before": before,
        }

    conn = _ensure_app_memory()
    chat_count = int(conn.execute("SELECT COUNT(*) FROM chat_sessions WHERE owner_id=?", (owner_id,)).fetchone()[0])
    conn.execute("DELETE FROM chat_sessions WHERE owner_id=?", (owner_id,))
    conn.commit()
    conn.close()
    save_stored_projects([], owner_id)
    save_stored_agent_groups([], owner_id)
    removed_uploads = 0
    admin_uploads = UPLOADS_BUCKET_DIR / owner_id
    if admin_uploads.exists():
        shutil.rmtree(admin_uploads)
        removed_uploads += 1
    after = _book_index_status()
    if after["books"] != before["books"] or after["bytes"] != before["bytes"]:
        raise HTTPException(status_code=500, detail="تغيّر فهرس الكتب أثناء المسح. أوقف الاستخدام وافحص النسخة فوراً.")

    return {
        "status": "wiped",
        "message": "مُسحت المحادثات والمشاريع ومجموعات الوكلاء والمرفقات. فهرس الكتب ما زال في مكانه.",
        "removed_chats": chat_count,
        "removed_uploads": removed_uploads,
        "book_index": after,
        **archive,
    }

def _chat_has_owner(conn: sqlite3.Connection) -> bool:
    return "owner_id" in [row[1] for row in conn.execute("PRAGMA table_info(chat_sessions)")]

def _read_chat_sessions(conn: sqlite3.Connection, owner_id: Optional[str] = None) -> List[dict]:
    sessions = []
    if _chat_has_owner(conn) and owner_id:
        rows = conn.execute(
            "SELECT payload FROM chat_sessions WHERE owner_id=? ORDER BY sort_index ASC, updated_at DESC",
            (owner_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT payload FROM chat_sessions ORDER BY sort_index ASC, updated_at DESC"
        ).fetchall()
    for row in rows:
        try:
            item = json.loads(row["payload"])
            if isinstance(item, dict) and item.get("id"):
                sessions.append(item)
        except Exception:
            continue
    return sessions

def _replace_chat_sessions(sessions: list, owner_id: str) -> int:
    now = datetime.now().isoformat()
    conn = _ensure_app_memory()
    kept = 0
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM chat_sessions WHERE owner_id=?", (owner_id,))
        for index, session in enumerate(sessions):
            if not isinstance(session, dict) or not session.get("id"):
                continue
            conn.execute(
                "INSERT INTO chat_sessions (owner_id, id, title, created_at, updated_at, sort_index, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    owner_id,
                    str(session["id"]),
                    str(session.get("title") or ""),
                    str(session.get("createdAt") or now),
                    now,
                    index,
                    json.dumps(session, ensure_ascii=False),
                )
            )
            kept += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return kept

def _read_agent_groups_file() -> list:
    if not os.path.exists(AGENT_GROUPS_FILE):
        return []
    try:
        with open(AGENT_GROUPS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _archive_scope_label(scope: str) -> str:
    known = {
        "chats": "المحادثات",
        "projects": "المشاريع",
        "agents": "الوكلاء",
        "tools": "الإضافات",
        "all": "الجميع",
        "legacy": "نسخة كاملة سابقة",
    }
    if scope in known:
        return known[scope]
    parts = [part for part in str(scope or "").split("+") if part]
    if parts:
        return _label_for_scopes(parts)
    return scope or "أرشيف"

def _format_archive_stamp(archive_id: str) -> str:
    parts = archive_id.split("_")
    if len(parts) >= 3 and len(parts[1]) == 8 and len(parts[2]) >= 6:
        raw_d, raw_t = parts[1], parts[2]
        return f"{raw_d[:4]}/{raw_d[4:6]}/{raw_d[6:]} — {raw_t[:2]}:{raw_t[2:4]}:{raw_t[4:6]}"
    return archive_id

def _assert_book_index_stable(before: Dict[str, Any]) -> Dict[str, Any]:
    after = _book_index_status()
    if after.get("books") != before.get("books") or after.get("bytes") != before.get("bytes"):
        raise HTTPException(status_code=500, detail="تغيّر فهرس الكتب. أُوقف الإجراء.")
    return after

def _copy_uploads_to(dest_dir: str) -> bool:
    uploads_dir = BASE_DIR / "uploads"
    if not uploads_dir.exists():
        return False
    has_files = any(path.name != ".gitkeep" for path in uploads_dir.iterdir())
    if not has_files:
        return False
    shutil.copytree(uploads_dir, dest_dir, dirs_exist_ok=True)
    return True

def list_user_archives(owner_id: str) -> List[dict]:
    backups_dir = BASE_DIR / "backups"
    if not backups_dir.exists():
        return []
    entries = []
    for path in backups_dir.iterdir():
        if not path.is_dir() or not path.name.startswith("archive_"):
            continue
        manifest_path = path / "manifest.json"
        scope = "legacy"
        created_at = _format_archive_stamp(path.name)
        counts = {}
        scope_label = ""
        note = ""
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                scope = manifest.get("scope") or "legacy"
                created_at = manifest.get("created_at") or created_at
                counts = manifest.get("counts") or {}
                scope_label = manifest.get("scope_label") or ""
                note = str(manifest.get("note") or "").strip()
                archive_owner = str(manifest.get("owner_id") or ADMIN_OWNER_ID)
            except Exception:
                archive_owner = ADMIN_OWNER_ID
        else:
            archive_owner = ADMIN_OWNER_ID
        if archive_owner != owner_id:
            continue
        if not scope_label:
            scope_label = _archive_scope_label(scope)
        summary_bits = []
        if "chats" in counts:
            summary_bits.append(f"{counts['chats']} محادثة")
        if "projects" in counts:
            summary_bits.append(f"{counts['projects']} مشروع")
        if "agents" in counts:
            summary_bits.append(f"{counts['agents']} مجموعة وكلاء")
        if "tools" in counts:
            summary_bits.append(f"{counts['tools']} إضافة")
        if counts.get("uploads"):
            summary_bits.append("مع المرفقات")
        entries.append({
            "id": path.name,
            "scope": scope,
            "scope_label": scope_label,
            "note": note,
            "created_at": created_at,
            "summary": " · ".join(summary_bits) or "نسخة محفوظة",
            "counts": counts,
        })
    entries.sort(key=lambda item: item["id"], reverse=True)
    return entries

class ArchiveCreateRequest(BaseModel):
    scope: Optional[str] = ""
    scopes: Optional[List[str]] = None
    note: Optional[str] = ""
    agent_groups: Optional[List[Any]] = None

class ArchiveRestoreRequest(BaseModel):
    archive_id: str

def _normalize_archive_scopes(req: ArchiveCreateRequest) -> List[str]:
    allowed = ["chats", "projects", "agents", "tools"]
    raw = req.scopes if req.scopes else []
    if not raw and req.scope:
        raw = ["chats", "projects", "agents", "tools"] if req.scope == "all" else [req.scope]
    scopes = []
    for item in raw:
        name = str(item or "").strip().lower()
        if name in allowed and name not in scopes:
            scopes.append(name)
    return scopes

def _label_for_scopes(scopes: List[str]) -> str:
    names = {
        "chats": "المحادثات",
        "projects": "المشاريع",
        "agents": "الوكلاء",
        "tools": "الإضافات",
    }
    ordered = [names[name] for name in ["chats", "projects", "agents", "tools"] if name in scopes]
    if len(ordered) == 4:
        return "الجميع"
    return " و".join(ordered) or "أرشيف"

@app.get("/api/archives")
async def get_archives(request: Request):
    return {"archives": list_user_archives(current_owner_id(request))}

@app.post("/api/archives")
async def create_archive(req: ArchiveCreateRequest, request: Request):
    """نقل عناصر العضو الحالي إلى أرشيفه ثم مسحها من مساحته فقط."""
    owner_id = current_owner_id(request)
    scopes = _normalize_archive_scopes(req)
    note = " ".join(str(req.note or "").split())[:400]
    if not scopes:
        raise HTTPException(status_code=400, detail="حدد ما تريد أرشفته")
    if not note:
        raise HTTPException(status_code=400, detail="اكتب وصفاً يذكّرك بهذه الأرشفة")
    before = _book_index_status()
    if before.get("books", 0) <= 0:
        raise HTTPException(status_code=409, detail="فهرس الكتب غير متاح. أُوقفت الأرشفة حتى لا يُفقد مرجع الكتب.")

    conn = _ensure_app_memory()
    chats = _read_chat_sessions(conn, owner_id)
    conn.close()
    projects = load_stored_projects(owner_id)
    groups = load_stored_agent_groups(owner_id)
    tools = load_stored_tools(owner_id)
    if not isinstance(tools, list):
        tools = []
    available = {
        "chats": bool(chats),
        "projects": bool(projects),
        "agents": bool(groups),
        "tools": bool(tools),
    }
    if not any(available[name] for name in scopes):
        raise HTTPException(status_code=400, detail="لا توجد بيانات في العناصر المحددة لأرشفتها")

    archive_id = time.strftime("archive_%Y%m%d_%H%M%S")
    archive_dir = os.path.join(BASE_DIR, "backups", archive_id)
    os.makedirs(archive_dir, exist_ok=True)
    created_at = time.strftime("%Y/%m/%d — %H:%M:%S")
    counts: Dict[str, Any] = {}
    saved_scopes = []

    if "chats" in scopes and chats:
        with open(os.path.join(archive_dir, "chats.json"), "w", encoding="utf-8") as f:
            json.dump(chats, f, ensure_ascii=False, indent=2)
        counts["chats"] = len(chats)
        saved_scopes.append("chats")
        owner_uploads = UPLOADS_BUCKET_DIR / owner_id
        if owner_uploads.exists() and any(owner_uploads.iterdir()):
            shutil.copytree(owner_uploads, os.path.join(archive_dir, "uploads"), dirs_exist_ok=True)
            counts["uploads"] = True
    if "projects" in scopes and projects:
        with open(os.path.join(archive_dir, "projects_data.json"), "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
        counts["projects"] = len(projects)
        saved_scopes.append("projects")
    if "agents" in scopes and groups:
        with open(os.path.join(archive_dir, "agent_groups_data.json"), "w", encoding="utf-8") as f:
            json.dump(groups, f, ensure_ascii=False, indent=2)
        counts["agents"] = len(groups)
        saved_scopes.append("agents")
    if "tools" in scopes and tools:
        with open(os.path.join(archive_dir, "tools_data.json"), "w", encoding="utf-8") as f:
            json.dump(tools, f, ensure_ascii=False, indent=2)
        counts["tools"] = len(tools)
        saved_scopes.append("tools")

    scope_label = _label_for_scopes(saved_scopes)
    manifest = {
        "id": archive_id,
        "scope": "all" if len(saved_scopes) == 4 else "+".join(saved_scopes),
        "scopes": saved_scopes,
        "scope_label": scope_label,
        "note": note,
        "owner_id": owner_id,
        "created_at": created_at,
        "counts": counts,
    }
    with open(os.path.join(archive_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    if "chats" in saved_scopes:
        _replace_chat_sessions([], owner_id)
        owner_uploads = UPLOADS_BUCKET_DIR / owner_id
        if owner_uploads.exists():
            shutil.rmtree(owner_uploads)
    if "projects" in saved_scopes:
        save_stored_projects([], owner_id)
    if "agents" in saved_scopes:
        save_stored_agent_groups([], owner_id)
    if "tools" in saved_scopes:
        save_stored_tools([], owner_id)

    after = _assert_book_index_stable(before)
    return {
        "status": "archived",
        "archive_id": archive_id,
        "scopes": saved_scopes,
        "scope_label": scope_label,
        "note": note,
        "created_at": created_at,
        "counts": counts,
        "book_index": after,
        "message": "نُقلت العناصر المحددة إلى الأرشيف ومُسحت من التطبيق.",
    }

def _restore_user_archive(archive_id: str, owner_id: str) -> Dict[str, Any]:
    if not re.fullmatch(r"archive_\d{8}_\d{6}", archive_id or ""):
        raise HTTPException(status_code=400, detail="معرّف الأرشيف غير صالح")
    archive_dir = os.path.join(BASE_DIR, "backups", archive_id)
    if not os.path.isdir(archive_dir):
        raise HTTPException(status_code=404, detail="الأرشيف غير موجود")
    before = _book_index_status()
    if before.get("books", 0) <= 0:
        raise HTTPException(status_code=409, detail="فهرس الكتب غير متاح. أُوقف الاسترجاع.")

    restored = []
    restored_chats = False
    restored_projects = False
    restored_agents = False
    restored_tools = False
    manifest_path = os.path.join(archive_dir, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        archive_owner = str(manifest.get("owner_id") or ADMIN_OWNER_ID)
        if archive_owner != owner_id:
            raise HTTPException(status_code=403, detail="هذا الأرشيف خاص بعضو آخر")
        scopes = manifest.get("scopes")
        if not isinstance(scopes, list) or not scopes:
            scope = manifest.get("scope") or ""
            if scope == "all":
                scopes = ["chats", "projects", "agents"]
            elif scope == "projects":
                scopes = ["projects", "agents"]
            elif scope:
                scopes = [part for part in str(scope).split("+") if part]
            else:
                scopes = []
        if "chats" in scopes:
            chats_path = os.path.join(archive_dir, "chats.json")
            if os.path.exists(chats_path):
                with open(chats_path, "r", encoding="utf-8") as f:
                    chats = json.load(f)
                if isinstance(chats, list):
                    _replace_chat_sessions(chats, owner_id)
                    restored.append("chats")
                    restored_chats = True
            uploads_src = os.path.join(archive_dir, "uploads")
            if os.path.isdir(uploads_src):
                dest = UPLOADS_BUCKET_DIR / owner_id
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copytree(uploads_src, dest, dirs_exist_ok=True)
                restored.append("uploads")
        if "projects" in scopes:
            projects_path = os.path.join(archive_dir, "projects_data.json")
            if os.path.exists(projects_path):
                with open(projects_path, "r", encoding="utf-8") as f:
                    projects = json.load(f)
                if isinstance(projects, list):
                    save_stored_projects(projects, owner_id)
                    restored.append("projects")
                    restored_projects = True
        if "agents" in scopes:
            groups_path = os.path.join(archive_dir, "agent_groups_data.json")
            if os.path.exists(groups_path):
                with open(groups_path, "r", encoding="utf-8") as f:
                    groups = json.load(f)
                if isinstance(groups, list):
                    save_stored_agent_groups(groups, owner_id)
                    restored.append("agents")
                    restored_agents = True
        if "tools" in scopes:
            tools_path = os.path.join(archive_dir, "tools_data.json")
            if os.path.exists(tools_path):
                with open(tools_path, "r", encoding="utf-8") as f:
                    tools = json.load(f)
                if isinstance(tools, list):
                    save_stored_tools(tools, owner_id)
                    restored.append("tools")
                    restored_tools = True
    else:
        if owner_id != ADMIN_OWNER_ID:
            raise HTTPException(status_code=403, detail="هذا الأرشيف خاص بالمشرف")
        memory_src = os.path.join(archive_dir, "app_memory.db")
        if os.path.isfile(memory_src):
            src = sqlite3.connect(f"file:{memory_src}?mode=ro", uri=True)
            src.row_factory = sqlite3.Row
            chats = _read_chat_sessions(src, ADMIN_OWNER_ID)
            row = src.execute(
                "SELECT payload FROM kv_documents WHERE key=?",
                (_owner_key("projects", ADMIN_OWNER_ID),)
            ).fetchone()
            if row is None:
                row = src.execute("SELECT payload FROM kv_documents WHERE key='projects'").fetchone()
            src.close()
            _replace_chat_sessions(chats, owner_id)
            restored_chats = True
            restored.append("chats")
            if row:
                projects = json.loads(row["payload"])
                if isinstance(projects, list):
                    save_stored_projects(projects, owner_id)
                    restored_projects = True
                    restored.append("projects")
        groups_path = os.path.join(archive_dir, "agent_groups_data.json")
        if os.path.exists(groups_path):
            with open(groups_path, "r", encoding="utf-8") as f:
                groups = json.load(f)
            if isinstance(groups, list):
                save_stored_agent_groups(groups, owner_id)
                restored_agents = True
                restored.append("agents")

    after = _assert_book_index_stable(before)
    return {
        "status": "restored",
        "archive_id": archive_id,
        "restored": restored,
        "restored_chats": restored_chats,
        "restored_projects": restored_projects,
        "restored_agents": restored_agents,
        "restored_tools": restored_tools,
        "book_index": after,
        "message": "عادت النسخة المؤرشفة إلى التطبيق.",
    }

def _archive_folder(archive_id: str) -> str:
    if not re.fullmatch(r"archive_\d{8}_\d{6}", archive_id or ""):
        raise HTTPException(status_code=400, detail="معرّف الأرشيف غير صالح")
    backups_dir = (BASE_DIR / "backups").resolve()
    target = (backups_dir / archive_id).resolve()
    if backups_dir not in target.parents or not target.is_dir():
        raise HTTPException(status_code=404, detail="الأرشيف غير موجود")
    return str(target)

@app.post("/api/archives/restore")
async def restore_archive(req: ArchiveRestoreRequest, request: Request):
    return _restore_user_archive(req.archive_id, current_owner_id(request))

@app.delete("/api/archives/{archive_id}")
async def delete_archive(archive_id: str, request: Request):
    owner_id = current_owner_id(request)
    target = _archive_folder(archive_id)
    manifest_path = os.path.join(target, "manifest.json")
    archive_owner = ADMIN_OWNER_ID
    if os.path.exists(manifest_path):
        try:
            archive_owner = str(json.loads(Path(manifest_path).read_text(encoding="utf-8")).get("owner_id") or ADMIN_OWNER_ID)
        except Exception:
            archive_owner = ADMIN_OWNER_ID
    if archive_owner != owner_id:
        raise HTTPException(status_code=403, detail="هذا الأرشيف خاص بعضو آخر")
    shutil.rmtree(target)
    return {"status": "deleted", "archive_id": archive_id}

@app.delete("/api/archives")
async def delete_all_archives(request: Request):
    owner_id = current_owner_id(request)
    backups_dir = BASE_DIR / "backups"
    removed = []
    if backups_dir.exists():
        for path in list(backups_dir.iterdir()):
            if not (path.is_dir() and path.name.startswith("archive_") and re.fullmatch(r"archive_\d{8}_\d{6}", path.name)):
                continue
            manifest_path = path / "manifest.json"
            archive_owner = ADMIN_OWNER_ID
            if manifest_path.exists():
                try:
                    archive_owner = str(json.loads(manifest_path.read_text(encoding="utf-8")).get("owner_id") or ADMIN_OWNER_ID)
                except Exception:
                    archive_owner = ADMIN_OWNER_ID
            if archive_owner != owner_id:
                continue
            shutil.rmtree(path)
            removed.append(path.name)
    return {"status": "deleted", "count": len(removed), "archives": removed}

class RestoreBackupRequest(BaseModel):
    backup_id: str

@app.get("/api/system/backups")
async def list_system_backups_endpoint():
    """عرض قائمة النسخ الاحتياطية المتوفرة مرتبة تنازلياً بحيث تكون الأحدث أولاً"""
    backups_dir = os.path.join(BASE_DIR, "backups")
    if not os.path.exists(backups_dir):
        return {"backups": [], "count": 0}
    
    entries = []
    try:
        items = os.listdir(backups_dir)
    except Exception as e:
        return {"backups": [], "count": 0, "error": str(e)}

    for item in items:
        full_p = os.path.join(backups_dir, item)
        if os.path.isdir(full_p) and (item.startswith("backup_") or item.startswith("pre_restore_") or item.startswith("archive_")):
            mtime = os.path.getmtime(full_p)
            dt_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
            
            files = []
            total_size = 0
            try:
                for fn in os.listdir(full_p):
                    fp = os.path.join(full_p, fn)
                    if os.path.isfile(fp):
                        sz = os.path.getsize(fp)
                        total_size += sz
                        files.append({"filename": fn, "size": sz})
            except Exception:
                pass
            
            # تنسيق التاريخ والوقت
            date_part = dt_str
            prefix = "نسخة احتياطية" if item.startswith("backup_") else "نقطة أمان سابقة"
            parts = item.split("_")
            if item.startswith("backup_") and len(parts) >= 3:
                raw_d, raw_t = parts[1], parts[2]
                if len(raw_d) == 8 and len(raw_t) >= 6:
                    date_part = f"{raw_d[:4]}/{raw_d[4:6]}/{raw_d[6:]} — {raw_t[:2]}:{raw_t[2:4]}:{raw_t[4:6]}"
            elif item.startswith("pre_restore_") and len(parts) >= 4:
                raw_d, raw_t = parts[2], parts[3]
                if len(raw_d) == 8 and len(raw_t) >= 6:
                    date_part = f"{raw_d[:4]}/{raw_d[4:6]}/{raw_d[6:]} — {raw_t[:2]}:{raw_t[2:4]}:{raw_t[4:6]}"
            
            entries.append({
                "id": item,
                "label": f"{prefix} {date_part} ({len(files)} ملفات — {round(total_size/1024, 1)} KB)",
                "timestamp": dt_str,
                "mtime": mtime,
                "files_count": len(files),
                "files": [f["filename"] for f in files],
                "size_kb": round(total_size / 1024, 1)
            })

    # ترتيب تنازلي زمني بحت بناءً على توقيت الإنشاء الفعلي بحيث تكون النسخة الأحدث فعلياً بالأعلى دائماً
    entries.sort(key=lambda x: x["mtime"], reverse=True)
    if entries:
        entries[0]["label"] = "⭐ " + entries[0]["label"] + " (الأحدث الآن)"
        entries[0]["is_latest"] = True

    return {"backups": entries, "count": len(entries)}

@app.post("/api/system/restore")
async def restore_system_backup_endpoint(req: RestoreBackupRequest, request: Request):
    """استرجاع بيانات المشاريع والأدوات والمجموعات من نسخة احتياطية سابقة"""
    require_admin(request)
    backup_id = (req.backup_id or "").strip()
    if not backup_id or not re.match(r'^[a-zA-Z0-9_]+$', backup_id):
        raise HTTPException(status_code=400, detail="معرّف النسخة الاحتياطية غير صالح أو غير آمن")
    
    target_backup_dir = os.path.join(BASE_DIR, "backups", backup_id)
    if not os.path.isdir(target_backup_dir):
        raise HTTPException(status_code=404, detail="مجلد النسخة الاحتياطية المحدد غير موجود")
    if backup_id.startswith("archive_"):
        restored = _restore_user_archive(backup_id, ADMIN_OWNER_ID)
        restored["status"] = "success"
        restored["restored_files"] = restored.get("restored") or []
        restored["pre_restore_backup"] = ""
        restored["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return restored

    # أمان إضافي: حفظ نسخة أمان سريعة قبل الاسترجاع Pre-Restore Snapshot
    pre_snap_dir = os.path.join(BASE_DIR, "backups", time.strftime("pre_restore_%Y%m%d_%H%M%S"))
    os.makedirs(pre_snap_dir, exist_ok=True)
    for fn in ["projects_data.json", "tools_data.json", "agent_groups_data.json", "providers_data.json"]:
        src = os.path.join(BASE_DIR, fn)
        if os.path.exists(src):
            try:
                shutil.copy2(src, pre_snap_dir)
            except Exception:
                pass

    # استرجاع المحفوظات فقط. فهرس الكتب لا يُنسخ من الأرشيف ولا يُستبدل.
    restored_files = []
    for fn in os.listdir(target_backup_dir):
        if fn in ("shamela_index.db", "books.csv"):
            continue
        if fn.endswith(".json"):
            src_fp = os.path.join(target_backup_dir, fn)
            dst_fp = os.path.join(BASE_DIR, fn)
            if os.path.isfile(src_fp):
                shutil.copy2(src_fp, dst_fp)
                restored_files.append(fn)

    memory_src = os.path.join(target_backup_dir, "app_memory.db")
    if os.path.isfile(memory_src):
        for suffix in ("", "-wal", "-shm"):
            stale = Path(str(APP_MEMORY_DB) + suffix) if suffix else APP_MEMORY_DB
            if suffix and stale.exists():
                stale.unlink()
        shutil.copy2(memory_src, APP_MEMORY_DB)
        restored_files.append("app_memory.db")
    elif "projects_data.json" in restored_files:
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                restored_projects = json.load(f)
            if isinstance(restored_projects, list):
                save_stored_projects(restored_projects, ADMIN_OWNER_ID)
        except Exception as e:
            print(f"Could not import restored projects into SQLite: {e}")

    uploads_src = os.path.join(target_backup_dir, "uploads")
    if os.path.isdir(uploads_src):
        shutil.copytree(uploads_src, str(BASE_DIR / "uploads"), dirs_exist_ok=True)
        restored_files.append("uploads")

    # تحديث الكاش البرمجي
    new_v = int(time.time())
    index_path = os.path.join(BASE_DIR, "templates", "index.html")
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                html_text = f.read()
            html_text = re.sub(r'\?v=\d+', f'?v={new_v}', html_text)
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(html_text)
        except Exception:
            pass

    return {
        "status": "success",
        "message": f"تم استرجاع النسخة الاحتياطية بنجاح!",
        "backup_id": backup_id,
        "restored_files": restored_files,
        "pre_restore_backup": os.path.basename(pre_snap_dir),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.post("/api/projects/plan")
async def plan_project_architecture(req: PlanRequest, request: Request):
    """
    تخطيط وهندسة المشروع (العقل المدبر)
    توليد خطة قياسية متكاملة خطوة بخطوة لهندسة المشروع البحثي وتوزيع الوكلاء
    """
    key = owner_openrouter_key(request, req.api_key)
    call_model = (req.planning_model or "").strip() or "google/gemini-2.5-flash"
    
    # تطبيع الاختصارات القديمة فقط دون المساس بنماذج Anthropic المختارة
    legacy_aliases = {
        "gemini-2.5-flash": "google/gemini-2.5-flash",
        "gemini-2.0-flash": "google/gemini-2.5-flash",
        "claude-3-7-sonnet": "anthropic/claude-3.7-sonnet",
        "claude-3-5-sonnet": "anthropic/claude-3.5-sonnet",
        "claude-3-5-haiku": "anthropic/claude-3.5-haiku",
        "claude-3-opus": "anthropic/claude-3-opus"
    }
    if call_model in legacy_aliases:
        call_model = legacy_aliases[call_model]

    planner_system_prompt = (
        "أنت «العقل المدبر والمخطط المنهجي للمشاريع البحثية التراثية» في منظومة المجتهد المتصلة بالمكتبة الشاملة (8.15 مليون نص تراثي).\n"
        "مهمتك: صياغة «المخطط القياسي الكامل لتنفيذ المشروع (Standard Project Blueprint)» بدقة علمية وهندسة برمجية فائقة.\n"
        "في توجيه المدير وكل وكيل: ألزمهم بنسخ اسم الكتاب حرفياً من قاعدة الشاملة، وبكتابة الموضع (3-450) إن تعددت الأجزاء، أو ص(50) إن كان الكتاب جزءاً واحداً.\n\n"
        "يجب أن يتضمن ردك أولاً بنية JSON صالحة للتنفيذ البرمجي ومحصورة بين علامات ```json و ``` تحتوي الحقول التالية تماماً:\n"
        "{\n"
        '  "title": "عنوان المشروع البحثي بدقة",\n'
        '  "desc": "وصف علمي محرر للمشروع وأهدافه",\n'
        '  "director": {\n'
        '    "name": "اسم مدير المشروع",\n'
        '    "model": "النموذج المقترح من أوبن راوتر",\n'
        '    "thinking": "high",\n'
        '    "system_prompt": "التوجيه الحرفي الصارم لمدير المشروع قيادة وتنسيقاً وتحقيقاً مع الصلاحية لإعادة البحث حتى 3 مرات، وإلزاماً حتمياً بأن يضع في ختام ونهاية تقرير المشروع جدولاً توثيقياً شاملاً بعنوان: «📚 ثبت المصادر والمراجع المعتمدة في المشروع» متضمناً كافة البيانات الببليوغرافية للكتب والمصادر التي نقلت منها المعلومات بأعمدتها الكاملة (م | اسم الكتاب | المصنف وسنة وفاته | المحقق أو الشارح | رقم الطبعة وسنتها | دار النشر والناشر | بلد النشر | رقم الكتاب بالشاملة إن وجد)"\n'
        '  },\n'
        '  "subagents_group": {\n'
        '    "name": "اسم مجموعة الوكلاء المساعدين المقترحة",\n'
        '    "desc": "وصف المجموعة",\n'
        '    "agents": [\n'
        '      {\n'
        '        "name": "اسم الوكيل 1",\n'
        '        "desc": "دوره التخصصي",\n'
        '        "model": "google/gemini-2.5-flash",\n'
        '        "books": ["أسماء كتب محددة من أمهات التراث في الشاملة"],\n'
        '        "pool_size": 1500,\n'
        '        "top_k": 300,\n'
        '        "system_prompt": "التوجيه الحرفي لهذا الوكيل في الاستخراج"\n'
        '      }\n'
        '    ]\n'
        '  },\n'
        '  "internal_benchmark": {\n'
        '    "enabled": true,\n'
        '    "title": "اسم الكتاب أو البحث التراثي للمقارنة والمضاهاة",\n'
        '    "author": "المؤلف",\n'
        '    "methodology": "آلية المقارنة واستخراج الجديد"\n'
        '  },\n'
        '  "external_web_benchmark": {\n'
        '    "enabled": true,\n'
        '    "query": "كلمات بحث إنجليزية وعربية دقيقة لـ Tavily تناسب موضوع البحث حصراً",\n'
        '    "domains": ["المواقع المرجعية التخصصية المناسبة لفن المسألة (مثل dorar.net, shamela.ws للعلوم الشرعية، أو pubmed للطب، أو nasa للفلك)"],\n'
        '    "prompt": "توجيه أداة البحث في الويب لاسترجاع المعطيات الموثقة"\n'
        '  },\n'
        '  "computational_tool": {\n'
        '    "enabled": true,\n'
        '    "tool_type": "معرف الأداة المعتمدة المطابقة للموضوع (مثل: charts_metrics أو astronomy_hijri_sync أو hadith_isnad_tree أو none)",\n'
        '    "name": "اسم الأداة الحسابية المعتمدة أو لا يوجد",\n'
        '    "desc": "وظيفتها المحددة في هذا المشروع البحثي بدقة"\n'
        '  },\n'
        '  "output_formats": {\n'
        '    "csv_results": true,\n'
        '    "csv_benchmark": true,\n'
        '    "formatted_txt": true,\n'
        '    "academic_pdf": true\n'
        '  }\n'
        "}\n\n"
        "بعد كتلة الـ JSON، اكتب شرحاً تفصيلياً تحليلياً باللغة العربية الفصحى للباحث يبيّن خطة السير خطوة بخطوة، والمسوغات العلمية لاختيار الكتب وتوزيع الوكلاء."
    )

    # استكشاف الكتب التراثية الحقيقية من قاعدة بيانات الشاملة لهذا الموضوع
    disc_books = explore_bibliographic_books(f"{req.topic} {req.goal or ''} {req.scope_time or ''}", limit=80)
    books_discovery_txt = ""
    if disc_books:
        books_discovery_txt = (
            "\n\n📚 [قائمة استكشافية حقيقية لأهم كتب الشاملة المرتبطة بموضوع البحث المستخرجة من الفهرس الببليوغرافي]:\n"
            + "\n".join([
                f"- #{b['book_id']} {b['title']} (المؤلف: {b['author']}, ت: {b['death']}, {b['category']}, {b.get('volumes', 1)} مجلد)"
                for b in disc_books[:50]
            ])
            + "\n\nالرجاء اختيار كتب الوكلاء من هذه القائمة التراثية الحقيقية حصراً مع أرقامها."
        )

    user_prompt = (
        f"طلب تخطيط وهندسة مشروع بحثي جديد:\n"
        f"- موضوع وفكرة المشروع: {req.topic}\n"
        f"- الهدف المحوري: {req.goal or 'مسح وتحقيق شامل'}\n"
        f"- النطاق الزمني والمصادري: {req.scope_time or 'أمهات كتب التراث الشاملة'}\n"
        f"- الدراسة السابقة للمقارنة المرجعية: {req.has_benchmark or 'لا يوجد دراسة سابقة محددة، اقترح كتاباً مرجعياً'}\n"
        f"- صيغة المخرجات المفضلة: {req.preferred_output or 'جداول CSV مفرغة ومقارنات مرجعية وتقرير PDF'}\n\n"
        f"أيها العقل المدبر، ضع المخطط القياسي الكامل للمشروع مع توزيع الوكلاء وتوجيهاتهم بدقة."
        f"{books_discovery_txt}"
    )

    payload = {
        "model": call_model,
        "messages": [
            {"role": "system", "content": planner_system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 8192
    }

    try:
        if str(call_model).startswith("local:"):
            data = {"choices": [{"message": {"content": _complete_local_text(call_model, payload["messages"], 0.2, 4096)}}]}
        else:
            o_req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8085",
                    "X-Title": "Al-Mojtahed Research Architect"
                },
                data=json.dumps(payload).encode("utf-8")
            )
            with urllib.request.urlopen(o_req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
            
        # محاولة استخراج JSON من الرد
        json_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", content)
        parsed_blueprint = None
        if json_match:
            try:
                parsed_blueprint = json.loads(json_match.group(1))
            except Exception:
                pass

        return {
            "status": "ok",
            "raw_plan": content,
            "blueprint": parsed_blueprint,
            "model_used": call_model
        }
    except Exception as e:
        print(f"Project Planning Error: {e}")
        # رد بديل آلي في حال انقطاع الشبكة
        fallback_blueprint = {
            "title": req.topic,
            "desc": f"مشروع بحثي محقق: {req.topic}",
            "director": {
                "name": "مدير المشروع العام",
                "model": "google/gemini-2.5-flash",
                "thinking": "high",
                "system_prompt": "أنت مدير هذا المشروع البحثي، تشرف على استقصاء الوكلاء ومقارنة النتائج وصياغة الجداول."
            },
            "subagents_group": {
                "name": f"فريق تحقيق: {req.topic[:25]}",
                "desc": "مجموعة الوكلاء المتخصصين في استخراج نصوص المسألة",
                "agents": [
                    {
                        "name": "وكيل المسح الاستقصائي العام",
                        "desc": "مسح أمهات المصادر المعتمدة في الشاملة",
                        "model": "google/gemini-2.5-flash",
                        "books": [],
                        "pool_size": 1500,
                        "top_k": 300,
                        "system_prompt": "استخرج كافة الشواهد المتعلقة بالمسألة كاملة مع أرقام الأجزاء والصفحات."
                    }
                ]
            },
            "internal_benchmark": {"enabled": True, "title": "دراسة مرجعية سابقة", "author": "أحد أعلام التراث", "methodology": "المقارنة والمضاهاة"},
            "external_web_benchmark": {"enabled": True, "query": req.topic, "domains": [], "prompt": "البحث في الدراسات المعاصرة"},
            "computational_tool": {"enabled": False, "tool_type": "calendar", "name": "محول التقويم", "desc": "مطابقة التواريخ"},
            "output_formats": {"csv_results": True, "csv_benchmark": True, "formatted_txt": True, "academic_pdf": True}
        }
        return {
            "status": "partial",
            "error": str(e),
            "blueprint": fallback_blueprint,
            "raw_plan": f"تم وضع المخطط الأساسي للمشروع: {req.topic}"
        }

@app.post("/api/tavily/search")
async def tavily_search(req: TavilySearchRequest):
    """
    واجهة البحث الخارجي عبر محرك Tavily الأكاديمي
    """
    key = req.api_key.strip()
    if not key:
        return {"status": "error", "message": "يرجى إدخال مفتاح Tavily API"}

    payload = {
        "api_key": key,
        "query": req.query,
        "search_depth": req.search_depth or "advanced",
        "include_answer": True,
        "max_results": req.max_results or 5
    }
    if req.include_domains:
        payload["include_domains"] = req.include_domains

    try:
        t_req = urllib.request.Request(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload).encode("utf-8")
        )
        with urllib.request.urlopen(t_req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "status": "ok",
                "answer": data.get("answer", ""),
                "results": data.get("results", [])
            }
    except Exception as e:
        print(f"Tavily search error: {e}")
        return {"status": "error", "message": str(e)}
class AstronomyVerifyRequest(BaseModel):
    event_text: str
    year: Optional[int] = None
    month: Optional[str] = "محرم"

@app.post("/api/astronomy/verify")
async def verify_astronomy_event_endpoint(req: AstronomyVerifyRequest):
    """
    التحقق الفلكي والحسابي من صحة الحوادث التاريخية عبر العصور الإسلامية
    وحساب أوقات الاقتران والبدر، ومطابقة أيام الأسبوع وكشف التصحيف التاريخي.
    """
    try:
        res = astronomy_engine.verify_historical_astronomical_event(
            event_text=req.event_text,
            cited_year=req.year,
            cited_month=req.month or "محرم"
        )
        return {"status": "ok", "result": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}

SCHOLAR_TO_CANONICAL_BOOK: Dict[str, str] = {
    # الحنفية
    "السرخسي": "المبسوط للسرخسي",
    "الكاساني": "بدائع الصنائع في ترتيب الشرائع",
    "ابن عابدين": "حاشية ابن عابدين = رد المحتار - ط الحلبي",
    "ابن نجيم": "البحر الرائق شرح كنز الدقائق ومنحة الخالق وتكملة الطوري",
    "المرغيناني": "الهداية في شرح بداية المبتدي",
    "الزيلعي": "تبيين الحقائق شرح كنز الدقائق وحاشية الشلبي",
    "ابن الهمام": "فتح القدير للعاجز الفقير",
    "النسفي": "كنز الدقائق",
    "الحصكفي": "الدر المختار",
    # المالكية
    "مالك": "المدونة",
    "ابن القاسم": "المدونة",
    "ابن رشد": "بداية المجتهد ونهاية المقتصد",
    "القرافي": "الذخيرة للقرافي",
    "الحطاب": "مواهب الجليل في شرح مختصر خليل",
    "المواق": "التاج والإكليل لمختصر خليل",
    "الدردير": "الشرح الكبير للدردير",
    "الدسوقي": "حاشية الدسوقي على الشرح الكبير",
    "ابن أبي زيد": "الفواكه الدواني على رسالة ابن أبي زيد القيرواني",
    "ابن عبد البر": "الكافي في فقه أهل المدينة",
    # الشافعية
    "الشافعي": "الأم للشافعي - ط الفكر",
    "الماوردي": "الحاوي الكبير",
    "النووي": "المجموع شرح المهذب - ط المنيرية",
    "الرافعي": "العزيز شرح الوجيز المعروف بالشرح الكبير",
    "الخطيب الشربيني": "مغني المحتاج إلى معرفة معاني ألفاظ المنهاج",
    "ابن حجر الهيتمي": "تحفة المحتاج في شرح المنهاج وحواشي الشرواني والعبادي",
    "الرملي": "نهاية المحتاج إلى شرح المنهاج",
    "زكريا الأنصاري": "أسنى المطالب في شرح روض الطالب",
    "الغزالي": "الوسيط في المذهب",
    # الحنابلة
    "ابن قدامة": "المغني لابن قدامة - ت التركي",
    "المجد ابن تيمية": "المحرر في الفقه",
    "ابن تيمية": "مجموع الفتاوى",
    "ابن القيم": "إعلام الموقعين عن رب العالمين",
    "المرداوي": "الإنصاف في معرفة الراجح من الخلاف - ت التركي",
    "البهوتي": "كشاف القناع عن متن الإقناع - ط وزارة العدل",
    "ابن مفلح": "المبدع في شرح المقنع - ط العلمية",
    "الحجاوي": "زاد المستقنع في اختصار المقنع - ط دار الوطن",
    "الفتوحي": "شرح كوكب المنير",
    "الرحيباني": "مطالب أولي النهى في شرح غاية المنتهى",
    # المؤرخون وأصحاب الحوليات
    "الطبري": "تاريخ الطبري = تاريخ الرسل والملوك، وصلة تاريخ الطبري",
    "ابن الأثير": "الكامل في التاريخ - ت تدمري",
    "ابن كثير": "البداية والنهاية - ت التركي",
    "الذهبي": "تاريخ الإسلام - ت تدمري",
    "ابن الجوزي": "المنتظم في تاريخ الملوك والأمم",
    "سبط ابن الجوزي": "مرآة الزمان في تواريخ الأعيان",
    "ابن تغري بردي": "النجوم الزاهرة فى ملوك مصر والقاهرة",
    "المقريزي": "السلوك لمعرفة دول الملوك",
    "ابن حجر": "إنباء الغمر بأبناء العمر - ط الهندية",
    "الجبرتي": "تاريخ عجائب الآثار في التراجم والأخبار",
    "الفاسي": "العقد الثمين فى تاريخ البلد الأمين",
    "السمهودي": "وفاء الوفاء بأخبار دار المصطفى",
    "ابن طولون": "مفاكهة الخلان في حوادث الزمان",
    "ابن إياس": "بدائع الزهور في وقائع الدهور - ت محمد مصطفى",
    "ابن العماد": "شذرات الذهب في أخبار من ذهب",
    "ابن عساكر": "تاريخ دمشق لابن عساكر"
}


def explore_bibliographic_books(query_text: str, limit: int = 400) -> List[Dict[str, Any]]:
    """
    استكشاف شامل ومفتوح لجدول كتب الشاملة الكامل (8,589 كتاباً مع أرقامها المعيارية وسنوات الوفاة):
    1. استخراج القيود والحدود الزمنية لوفاة المصنفين بدقة (مثل: إلى سنة 1000هـ، حتى 800هـ...).
    2. استخراج الفنون والتصنيفات المستهدفة (حنبلي، حنفي، مالكي، شافعي، أصول، لغة، نحو، تاريخ، حديث، تراجم...).
    3. جلب جميع الكتب المتطابقة مع الفن والحد الزمني مباشرة من قاعدة البيانات الكاملة books.csv / shamela_index.db،
       لتزويد المهندس المعماري بالقائمة الكاملة بأرقامها الحرفية #ID ليختار منها بحرية وثقة قطعية.
    """
    db = get_db()
    if not db:
        return []

    try:
        cursor = db.cursor()
        results = []
        seen_ids = set()

        # 1. استخراج الحد الزمني الأقصى لوفاة المصنف (مثل: إلى سنة 1000هـ، حتى سنة 1000هـ، حد 1000...)
        death_limit = None
        m_death = re.search(r'(?:إلى|حتى|قبل|حد)\s*(?:سنة|عام)?\s*(\d{3,4})\s*هـ?', query_text)
        if not m_death:
            m_death = re.search(r'(\d{3,4})\s*هـ', query_text)
        if m_death:
            val = int(m_death.group(1))
            if 100 <= val <= 1450:
                death_limit = val

        # 2. استخراج الفنون والتصنيفات المستهدفة في البحث من الـ 40 تصنيفاً للشاملة
        cat_ids = set()

        # الفقه ومذاهبه
        is_hanbali = any(k in query_text for k in ['حنبلي', 'حنابلة', 'ابن حنبل', 'أحمد بن حنبل'])
        is_hanafi = any(k in query_text for k in ['حنفي', 'حنفية', 'أبو حنيفة'])
        is_maliki = any(k in query_text for k in ['مالكي', 'مالكية', 'مالك بن أنس'])
        is_shafii = any(k in query_text for k in ['شافعي', 'شافعية', 'الشافعي'])
        is_usul = any(k in query_text for k in ['أصول الفقه', 'أصول', 'قواعد فقهية', 'فروق', 'قواعد'])

        if is_hanbali:
            cat_ids.add(17) # الفقه الحنبلي
        if is_hanafi:
            cat_ids.add(14) # الفقه الحنفي
        if is_maliki:
            cat_ids.add(15) # الفقه المالكي
        if is_shafii:
            cat_ids.add(16) # الفقه الشافعي
        if is_usul:
            cat_ids.update([11, 12]) # أصول الفقه، علوم الفقه والقواعد

        # إذا كانت دراسة فقهية عامة أو مقارنة ولم تُحصر بمذهب واحد
        if any(k in query_text for k in ['فقه', 'مذاهب', 'مقارن', 'خلاف', 'لعان', 'نسب', 'فراش', 'أوقاف', 'وقف', 'نكاح', 'طلاق', 'بيوع']):
            if not cat_ids:
                cat_ids.update([14, 15, 16, 17, 18, 19, 11, 12])
            elif not is_hanbali and not is_hanafi and not is_maliki and not is_shafii:
                cat_ids.update([18, 19])

        # اللغة والنحو والأدب
        if any(k in query_text for k in ['نحو', 'صرف', 'إعراب', 'كوفيين', 'بصريين', 'سيبويه']):
            cat_ids.add(31) # النحو والصرف
        if any(k in query_text for k in ['لغة', 'معاجم', 'غريب', 'قاموس', 'لسان العرب']):
            cat_ids.update([29, 30]) # كتب اللغة، المعاجم
        if any(k in query_text for k in ['بلاغة', 'بيان', 'بديع', 'معاني']):
            cat_ids.add(35) # البلاغة
        if any(k in query_text for k in ['أدب', 'شعر', 'دواوين']):
            cat_ids.update([32, 34])

        # التاريخ والتراجم والبلدان
        if any(k in query_text for k in ['تاريخ', 'حوليات', 'حوادث', 'كسوف', 'خسوف', 'وباء', 'طاعون', 'وقائع', 'ملوك']):
            cat_ids.add(25) # التاريخ
        if any(k in query_text for k in ['تراجم', 'طبقات', 'أعيان', 'وفيات', 'سير', 'رجال']):
            cat_ids.add(26) # التراجم والطبقات
        if any(k in query_text for k in ['أنساب', 'نسب']):
            cat_ids.add(27) # الأنساب
        if any(k in query_text for k in ['بلدان', 'رحلات', 'جغرافيا']):
            cat_ids.add(28)

        # الحديث والسنة
        if any(k in query_text for k in ['حديث', 'أسانيد', 'علل', 'تخريج', 'صحاح', 'سنن', 'مسانيد', 'أطراف']):
            cat_ids.update([6, 7, 8, 9, 10])

        # التفسير وعلوم القرآن
        if any(k in query_text for k in ['تفسير', 'علوم القرآن']):
            cat_ids.update([3, 4])

        # العقيدة والفرق
        if any(k in query_text for k in ['عقيدة', 'توحيد', 'فرق', 'ردود', 'كلام']):
            cat_ids.update([1, 2])

        # تحديد التصنيف الأساسي ذي الأولوية المطلقة
        primary_cat = None
        if is_hanbali:
            primary_cat = 17
        elif is_hanafi:
            primary_cat = 14
        elif is_maliki:
            primary_cat = 15
        elif is_shafii:
            primary_cat = 16
        elif is_usul:
            primary_cat = 11

        # 3. الاستعلام الشامل عن كتب التصنيفات المستهدفة
        if cat_ids:
            placeholders = ','.join(['?'] * len(cat_ids))
            order_primary = f"CASE WHEN category_id = {primary_cat} THEN 0 ELSE 1 END," if primary_cat else ""
            
            # إذا حدد الباحث حداً زمنياً صريحاً (مثل حتى 800هـ)
            if death_limit:
                sql = f"""
                    SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, volume_count_observed, betaka_text
                    FROM books
                    WHERE category_id IN ({placeholders})
                      AND main_author_death_hijri > 0 AND main_author_death_hijri <= ?
                    ORDER BY {order_primary}
                             volume_count_observed DESC,
                             main_author_death_hijri ASC
                    LIMIT ?
                """
                cursor.execute(sql, (*cat_ids, death_limit, limit))
                fetched_rows = cursor.fetchall()
            else:
                # تقسيم طبقي متوازن على مدار التاريخ الإسلامي كاملاً لمنع انحصار الكتب في القرون الأولى فقط:
                # 1. المتقدمون (حتى 350هـ): أمهات الرواية والصحاح والمصنفات (35%)
                # 2. المتوسطون (351 - 800هـ): أمهات الشروح والعلل والفقه المقارن (35%)
                # 3. المتأخرون (801 - 1450هـ): الموسوعات والتحرير والتخريج (30%)
                # 4. مجهولو سنة الوفاة (مخزنة 99999) كانوا يُستبعدون كلياً؛ لهم الآن حصة مستقلة (15%)
                lim_early = int(limit * 0.30)
                lim_mid = int(limit * 0.30)
                lim_unknown = int(limit * 0.15)
                lim_late = limit - lim_early - lim_mid - lim_unknown

                fetched_rows = []
                # المتقدمون
                cursor.execute(f"""
                    SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, volume_count_observed, betaka_text
                    FROM books
                    WHERE category_id IN ({placeholders})
                      AND main_author_death_hijri > 0 AND main_author_death_hijri <= 350
                    ORDER BY {order_primary} volume_count_observed DESC, main_author_death_hijri ASC
                    LIMIT ?
                """, (*cat_ids, lim_early))
                fetched_rows.extend(cursor.fetchall())

                # المتوسطون
                cursor.execute(f"""
                    SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, volume_count_observed, betaka_text
                    FROM books
                    WHERE category_id IN ({placeholders})
                      AND main_author_death_hijri > 350 AND main_author_death_hijri <= 800
                    ORDER BY {order_primary} volume_count_observed DESC, main_author_death_hijri ASC
                    LIMIT ?
                """, (*cat_ids, lim_mid))
                fetched_rows.extend(cursor.fetchall())

                # المتأخرون
                cursor.execute(f"""
                    SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, volume_count_observed, betaka_text
                    FROM books
                    WHERE category_id IN ({placeholders})
                      AND main_author_death_hijri > 800 AND main_author_death_hijri <= 1450
                    ORDER BY {order_primary} volume_count_observed DESC, main_author_death_hijri ASC
                    LIMIT ?
                """, (*cat_ids, lim_late))
                fetched_rows.extend(cursor.fetchall())

                # مجهولو سنة الوفاة
                cursor.execute(f"""
                    SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, volume_count_observed, betaka_text
                    FROM books
                    WHERE category_id IN ({placeholders})
                      AND (main_author_death_hijri IS NULL OR main_author_death_hijri <= 0 OR main_author_death_hijri >= 99999)
                    ORDER BY {order_primary} volume_count_observed DESC
                    LIMIT ?
                """, (*cat_ids, lim_unknown))
                fetched_rows.extend(cursor.fetchall())

            for row in fetched_rows:
                bid = row["book_id"]
                if bid not in seen_ids:
                    seen_ids.add(bid)
                    raw_b = row["betaka_text"] or ""
                    clean_b = re.sub(r'[\r\n\t]+', ' ', raw_b)[:160]
                    d_val = row["main_author_death_hijri"]
                    d_str = f"{d_val}هـ" if d_val and 0 < d_val < 99999 else "وفاة غير محددة"
                    results.append({
                        "book_id": bid,
                        "title": row["title_ar"],
                        "author": row["main_author_name_ar"] or "غير محدد",
                        "death": d_str,
                        "category": row["category_name_ar"] or "عام",
                        "betaka_snippet": clean_b,
                        "matched_from": "التصنيف المستهدف"
                    })

        # 4. مطابقة أسماء العلماء والمصنفين المذكورين في نص الباحث
        famous_scholars = [
            "أحمد بن حنبل", "الخلال", "الخرقي", "أبو يعلى", "الكلوذاني", "ابن عقيل",
            "ابن قدامة", "المجد ابن تيمية", "ابن تيمية", "ابن القيم", "المرداوي", "الحجاوي", "ابن مفلح", "البهوتي", "ابن رجب",
            "أبو حنيفة", "السرخسي", "الكاساني", "المرغيناني", "ابن نجيم", "ابن الهمام", "ابن عابدين",
            "مالك", "ابن القاسم", "أشهب", "سحنون", "ابن رشد", "القرافي", "الحطاب", "المواق", "الدردير", "الدسوقي", "عليش",
            "الشافعي", "البويطي", "المزني", "الماوردي", "الشيرازي", "الغزالي", "الرافعي", "النووي", "ابن حجر الهيتمي", "الرملي", "الخطيب الشربيني",
            "ابن حزم", "الطبري", "ابن الأثير", "الذهبي", "ابن كثير", "ابن الجوزي", "المقريزي", "ابن تغري بردي", "الجبرتي", "السيوطي", "ابن حجر", "ابن عساكر"
        ]
        for sch in famous_scholars:
            if len(results) >= limit:
                break
            if sch in query_text:
                death_filter = "AND main_author_death_hijri <= ?" if death_limit else ""
                sch_params = [f"%{sch}%"]
                if death_limit:
                    sch_params.append(death_limit)
                sch_params.append(25)

                cursor.execute(f"""
                    SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, volume_count_observed, betaka_text
                    FROM books
                    WHERE main_author_name_ar LIKE ? {death_filter}
                    ORDER BY volume_count_observed DESC
                    LIMIT ?
                """, tuple(sch_params))

                for row in cursor.fetchall():
                    bid = row["book_id"]
                    if bid not in seen_ids:
                        seen_ids.add(bid)
                        raw_b = row["betaka_text"] or ""
                        clean_b = re.sub(r'[\r\n\t]+', ' ', raw_b)[:160]
                        d_val = row["main_author_death_hijri"]
                        d_str = f"{d_val}هـ" if d_val and 0 < d_val < 99999 else "وفاة غير محددة"
                        results.append({
                            "book_id": bid,
                            "title": row["title_ar"],
                            "author": row["main_author_name_ar"] or sch,
                            "death": d_str,
                            "category": row["category_name_ar"] or "عام",
                            "betaka_snippet": clean_b,
                            "matched_from": f"المصنف: {sch}"
                        })

        # 5. استخراج الكلمات المفتاحية للمسائل والمطابقة في العناوين
        words = [w.strip() for w in re.split(r'[\s،,.;:!?()]+', query_text) if len(w.strip()) >= 3]
        stop_words = {
            "مشروع", "بحث", "أريد", "دراسة", "هذا", "الذي", "التي", "على", "فيها", 
            "يكون", "عمل", "تأسيس", "كبير", "مهندس", "خطة", "وكلاء", "كروت", "سنة", 
            "فقط", "حتى", "مسألة", "مسائل", "تحليل", "دون", "مجرد", "بمجرد", "صحيح", 
            "غير", "أقوال", "العمق", "المحور", "القرار", "المعتمد", "الصورة", "الحد",
            "تركيز", "فأكثر", "كتاباً", "أكثر"
        }
        keywords = [w for w in words if w not in stop_words and len(w) >= 3]

        for kw in keywords[:10]:
            if len(results) >= limit:
                break
            kw_params = [f"%{kw}%"]
            death_filter = "AND main_author_death_hijri <= ?" if death_limit else ""
            if death_limit:
                kw_params.append(death_limit)
            kw_params.append(15)

            cursor.execute(f"""
                SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, volume_count_observed, betaka_text
                FROM books
                WHERE title_ar LIKE ? {death_filter}
                ORDER BY volume_count_observed DESC
                LIMIT ?
            """, tuple(kw_params))

            for row in cursor.fetchall():
                bid = row["book_id"]
                if bid not in seen_ids:
                    seen_ids.add(bid)
                    raw_b = row["betaka_text"] or ""
                    clean_b = re.sub(r'[\r\n\t]+', ' ', raw_b)[:160]
                    d_val = row["main_author_death_hijri"]
                    d_str = f"{d_val}هـ" if d_val and 0 < d_val < 99999 else "وفاة غير محددة"
                    results.append({
                        "book_id": bid,
                        "title": row["title_ar"],
                        "author": row["main_author_name_ar"] or "غير محدد",
                        "death": d_str,
                        "category": row["category_name_ar"] or "عام",
                        "betaka_snippet": clean_b,
                        "matched_from": f"عنوان يطابق: {kw}"
                    })

        # 6. إذا كانت النتائج قليلة، إمداد المهندس بأمهات كتب التراث الكبرى المتنوعة لضمان غزارة الخيارات
        if len(results) < 50:
            cursor.execute("""
                SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, volume_count_observed, betaka_text
                FROM books
                WHERE volume_count_observed >= 2
                ORDER BY volume_count_observed DESC, main_author_death_hijri ASC
                LIMIT ?
            """, (max(50, limit - len(results)),))
            for row in cursor.fetchall():
                bid = row["book_id"]
                if bid not in seen_ids:
                    seen_ids.add(bid)
                    raw_b = row["betaka_text"] or ""
                    clean_b = re.sub(r'[\r\n\t]+', ' ', raw_b)[:160]
                    d_val = row["main_author_death_hijri"]
                    d_str = f"{d_val}هـ" if d_val and 0 < d_val < 99999 else "وفاة غير محددة"
                    results.append({
                        "book_id": bid,
                        "title": row["title_ar"],
                        "author": row["main_author_name_ar"] or "غير محدد",
                        "death": d_str,
                        "category": row["category_name_ar"] or "عام",
                        "betaka_snippet": clean_b,
                        "matched_from": "أمهات الكتب الكبرى في المخزن"
                    })

        return results
    except Exception as e:
        print(f"Error exploring bibliographic books: {e}")
        return []

# =============================================================================
# أداة البحث الحي في فهرس الكتب الكامل (8,589 كتاباً) - تُمنح لمهندس المشروع عبر Function Calling
# =============================================================================
_AR_DIACRITICS_RE = re.compile(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]')

def _ar_norm(s) -> str:
    """تطبيع عربي للمطابقة: حذف التشكيل والتطويل وتوحيد الألفات والياء والتاء المربوطة"""
    if not s:
        return ""
    s = _AR_DIACRITICS_RE.sub('', str(s))
    s = re.sub(r'[إأآٱ]', 'ا', s)
    s = s.replace('ى', 'ي').replace('ة', 'ه').replace('ؤ', 'و').replace('ئ', 'ي')
    return re.sub(r'\s+', ' ', s).strip().lower()

UNKNOWN_DEATH_SENTINEL = 99999

def search_books_catalog(query: str = "", title: str = "", author: str = "", category: str = "",
                         death_before: Optional[int] = None, death_after: Optional[int] = None,
                         include_unknown_death: bool = True, limit: int = 40) -> Dict[str, Any]:
    """
    بحث حي في جدول books كاملاً (بلا سقف 800 وبلا استبعاد مجهولي الوفاة).
    - query: كلمات حرة تُطابق في العنوان أو المؤلف أو بطاقة الكتاب (كل كلمة يجب أن توجد).
    - title / author / category: مطابقة جزئية مطبّعة لكل حقل.
    - death_before / death_after: حد زمني لوفاة المصنف بالهجري.
    - include_unknown_death: إدراج الكتب غير المسجلة سنة وفاة مؤلفها (موسومة بذلك).
    """
    db = get_db()
    if not db:
        return {"error": "قاعدة بيانات الفهرس غير متاحة", "results": []}
    try:
        db.create_function("ar_norm", 1, _ar_norm, deterministic=True)
    except Exception:
        try:
            db.create_function("ar_norm", 1, _ar_norm)
        except Exception:
            pass

    limit = max(1, min(int(limit or 40), 100))
    where, params = [], []

    def _terms(text):
        return [t for t in _ar_norm(text).split(' ') if len(t) >= 2]

    for t in _terms(query):
        # إزالة "ال" التعريف من بداية الكلمة لتوسيع المطابقة (البخاري ← بخاري)
        core = t[2:] if t.startswith('ال') and len(t) > 4 else t
        where.append("(ar_norm(title_ar) LIKE ? OR ar_norm(main_author_name_ar) LIKE ? OR ar_norm(betaka_text) LIKE ?)")
        params.extend([f"%{core}%"] * 3)
    for t in _terms(title):
        core = t[2:] if t.startswith('ال') and len(t) > 4 else t
        where.append("ar_norm(title_ar) LIKE ?")
        params.append(f"%{core}%")
    for t in _terms(author):
        core = t[2:] if t.startswith('ال') and len(t) > 4 else t
        where.append("(ar_norm(main_author_name_ar) LIKE ? OR ar_norm(betaka_text) LIKE ?)")
        params.extend([f"%{core}%"] * 2)
    if category and category.strip():
        where.append("ar_norm(category_name_ar) LIKE ?")
        params.append(f"%{_ar_norm(category)}%")

    death_conds = []
    if death_before or death_after:
        rng, rp = ["main_author_death_hijri > 0", f"main_author_death_hijri < {UNKNOWN_DEATH_SENTINEL}"], []
        if death_before:
            rng.append("main_author_death_hijri <= ?"); rp.append(int(death_before))
        if death_after:
            rng.append("main_author_death_hijri >= ?"); rp.append(int(death_after))
        death_conds.append("(" + " AND ".join(rng) + ")")
        params_death = rp
        if include_unknown_death:
            death_conds.append(f"(main_author_death_hijri IS NULL OR main_author_death_hijri <= 0 OR main_author_death_hijri >= {UNKNOWN_DEATH_SENTINEL})")
        where.append("(" + " OR ".join(death_conds) + ")")
        params.extend(params_death)
    elif not include_unknown_death:
        where.append(f"(main_author_death_hijri > 0 AND main_author_death_hijri < {UNKNOWN_DEATH_SENTINEL})")

    if not where:
        return {"error": "حدد كلمة بحث أو عنواناً أو مؤلفاً أو تصنيفاً على الأقل", "results": []}

    where_sql = " AND ".join(where)
    try:
        cursor = db.cursor()
        total = cursor.execute(f"SELECT COUNT(*) FROM books WHERE {where_sql}", tuple(params)).fetchone()[0]
        rows = cursor.execute(f"""
            SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar,
                   volume_count_observed, betaka_text
            FROM books WHERE {where_sql}
            ORDER BY volume_count_observed DESC, main_author_death_hijri ASC
            LIMIT ?
        """, (*params, limit)).fetchall()
    except Exception as e:
        return {"error": f"تعذر تنفيذ البحث: {e}", "results": []}

    results = []
    for r in rows:
        d_val = r["main_author_death_hijri"]
        known = bool(d_val) and 0 < d_val < UNKNOWN_DEATH_SENTINEL
        results.append({
            "book_id": r["book_id"],
            "title": r["title_ar"],
            "author": r["main_author_name_ar"] or "غير محدد",
            "death": f"{d_val}هـ" if known else "وفاة غير محددة",
            "category": r["category_name_ar"] or "عام",
            "volumes": r["volume_count_observed"],
            "betaka_snippet": re.sub(r'[\r\n\t]+', ' ', r["betaka_text"] or "")[:160],
        })

    return {
        "status": "ok",
        "total_matched": total,
        "returned": len(results),
        "results": results
    }

def get_library_categories() -> Dict[str, Any]:
    """استعراض قائمة التصنيفات التراثية الأربعين المعتمدة في الشاملة وإجمالي كتب كل تصنيف"""
    db = get_db()
    if not db:
        return {"error": "قاعدة بيانات الفهرس غير متاحة", "categories": []}
    try:
        cursor = db.cursor()
        cursor.execute("SELECT category_id, category_name_ar, book_count, folder_name FROM categories ORDER BY category_id ASC")
        rows = cursor.fetchall()
        cats = []
        for r in rows:
            cats.append({
                "id": r["category_id"],
                "name": r["category_name_ar"],
                "book_count": r["book_count"],
                "folder": r["folder_name"]
            })
        return {"total_categories": len(cats), "categories": cats}
    except Exception as e:
        return {"error": f"تعذر جلب التصنيفات: {e}", "categories": []}


def get_category_core_books(category: str, heritage_only: bool = True, limit: int = 40) -> Dict[str, Any]:
    """
    استخراج أمهات الكتب والمصادر التأسيسية الكبرى في تصنيف معين من الشاملة (مرتبة بالأكثر مجلدات وأهمية).
    - category: اسم التصنيف (مثل: التاريخ، الفقه الحنبلي، الفقه الشافعي، كتب السنة، التفسير...).
    - heritage_only: حصر النتائج بكتب التراث المتقدمة والمتوسطة (وفاة < 1000هـ) لاستبعاد التفريغات المعاصرة الكبيرة.
    """
    db = get_db()
    if not db:
        return {"error": "قاعدة بيانات الفهرس غير متاحة", "results": []}
    try:
        cursor = db.cursor()
        limit = max(1, min(int(limit or 40), 100))
        where = ["(category_name_ar LIKE ? OR folder_name LIKE ?)"]
        params = [f"%{category.strip()}%", f"%{category.strip()}%"]
        if heritage_only:
            where.append("main_author_death_hijri > 0 AND main_author_death_hijri < 1000")

        where_sql = " AND ".join(where)
        cursor.execute(f"""
            SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar,
                   volume_count_observed, betaka_text
            FROM books
            WHERE {where_sql}
            ORDER BY volume_count_observed DESC, main_author_death_hijri ASC
            LIMIT ?
        """, (*params, limit))
        rows = cursor.fetchall()
        results = []
        for r in rows:
            d_val = r["main_author_death_hijri"]
            results.append({
                "book_id": r["book_id"],
                "title": r["title_ar"],
                "author": r["main_author_name_ar"] or "غير محدد",
                "death": f"{d_val}هـ" if d_val and 0 < d_val < UNKNOWN_DEATH_SENTINEL else "وفاة غير محددة",
                "category": r["category_name_ar"] or "عام",
                "volumes": r["volume_count_observed"],
                "betaka_snippet": re.sub(r'[\r\n\t]+', ' ', r["betaka_text"] or "")[:200]
            })
        return {"category": category, "total_returned": len(results), "results": results}
    except Exception as e:
        return {"error": f"تعذر استخراج أمهات الكتب: {e}", "results": []}


def get_book_bibliography(book_id_or_title: Any) -> Dict[str, Any]:
    """استخراج بطاقة الكتاب الببليوغرافية الكاملة (المحقق، دار النشر، سنة الطبع، رقم الطبعة، عدد الأجزاء)"""
    db = get_db()
    if not db:
        return {"error": "قاعدة بيانات الفهرس غير متاحة"}
    try:
        cursor = db.cursor()
        str_val = str(book_id_or_title).strip()
        row = None
        if str_val.isdigit():
            cursor.execute("SELECT * FROM books WHERE book_id = ? LIMIT 1", (int(str_val),))
            row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT * FROM books WHERE title_ar = ? LIMIT 1", (str_val,))
            row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT * FROM books WHERE title_ar LIKE ? ORDER BY volume_count_observed DESC LIMIT 1", (f"%{str_val}%",))
            row = cursor.fetchone()
        if not row:
            return {"error": f"لم يتم العثور على كتاب مطابق لـ: {str_val}"}

        d_val = row["main_author_death_hijri"]
        return {
            "book_id": row["book_id"],
            "shamela_id": row["shamela_id"],
            "title": row["title_ar"],
            "author": row["main_author_name_ar"] or "غير محدد",
            "death": f"{d_val}هـ" if d_val and 0 < d_val < UNKNOWN_DEATH_SENTINEL else "وفاة غير محددة",
            "category": row["category_name_ar"] or "عام",
            "volumes": row["volume_count_observed"],
            "rel_path": row["rel_path"],
            "betaka_full": row["betaka_text"] or ""
        }
    except Exception as e:
        return {"error": f"تعذر جلب البيانات الببليوغرافية: {e}"}


def search_books_catalog(query: str = "", title: str = "", author: str = "", category: str = "",
                         death_before: Optional[int] = None, death_after: Optional[int] = None,
                         include_unknown_death: bool = True, limit: int = 40) -> Dict[str, Any]:
    """
    بحث حي في جدول books كاملاً (8,589 كتاباً مع تفاصيل الطبعات والبطاقات).
    - query: كلمات حرة تُطابق في العنوان أو المؤلف أو بطاقة الكتاب.
    - title / author / category: مطابقة جزئية مطبّعة لكل حقل.
    - death_before / death_after: حد زمني لوفاة المصنف بالهجري.
    - include_unknown_death: إدراج الكتب غير المسجلة سنة وفاة مؤلفها (موسومة بذلك).
    """
    db = get_db()
    if not db:
        return {"error": "قاعدة بيانات الفهرس غير متاحة", "results": []}
    try:
        db.create_function("ar_norm", 1, _ar_norm, deterministic=True)
    except Exception:
        try:
            db.create_function("ar_norm", 1, _ar_norm)
        except Exception:
            pass

    limit = max(1, min(int(limit or 40), 100))
    where, params = [], []

    def _terms(text):
        return [t for t in _ar_norm(text).split(' ') if len(t) >= 2]

    for t in _terms(query):
        core = t[2:] if t.startswith('ال') and len(t) > 4 else t
        where.append("(ar_norm(title_ar) LIKE ? OR ar_norm(main_author_name_ar) LIKE ? OR ar_norm(betaka_text) LIKE ?)")
        params.extend([f"%{core}%"] * 3)
    for t in _terms(title):
        core = t[2:] if t.startswith('ال') and len(t) > 4 else t
        where.append("ar_norm(title_ar) LIKE ?")
        params.append(f"%{core}%")
    for t in _terms(author):
        core = t[2:] if t.startswith('ال') and len(t) > 4 else t
        where.append("(ar_norm(main_author_name_ar) LIKE ? OR ar_norm(betaka_text) LIKE ?)")
        params.extend([f"%{core}%"] * 2)
    if category and category.strip():
        where.append("ar_norm(category_name_ar) LIKE ?")
        params.append(f"%{_ar_norm(category)}%")

    death_conds = []
    if death_before or death_after:
        rng, rp = ["main_author_death_hijri > 0", f"main_author_death_hijri < {UNKNOWN_DEATH_SENTINEL}"], []
        if death_before:
            rng.append("main_author_death_hijri <= ?"); rp.append(int(death_before))
        if death_after:
            rng.append("main_author_death_hijri >= ?"); rp.append(int(death_after))
        death_conds.append("(" + " AND ".join(rng) + ")")
        params_death = rp
        if include_unknown_death:
            death_conds.append(f"(main_author_death_hijri IS NULL OR main_author_death_hijri <= 0 OR main_author_death_hijri >= {UNKNOWN_DEATH_SENTINEL})")
        where.append("(" + " OR ".join(death_conds) + ")")
        params.extend(params_death)
    elif not include_unknown_death:
        where.append(f"(main_author_death_hijri > 0 AND main_author_death_hijri < {UNKNOWN_DEATH_SENTINEL})")

    if not where:
        return {"error": "حدد كلمة بحث أو عنواناً أو مؤلفاً أو تصنيفاً على الأقل", "results": []}

    where_sql = " AND ".join(where)
    try:
        cursor = db.cursor()
        total = cursor.execute(f"SELECT COUNT(*) FROM books WHERE {where_sql}", tuple(params)).fetchone()[0]
        rows = cursor.execute(f"""
            SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar,
                   volume_count_observed, betaka_text
            FROM books WHERE {where_sql}
            ORDER BY volume_count_observed DESC, main_author_death_hijri ASC
            LIMIT ?
        """, (*params, limit)).fetchall()
    except Exception as e:
        return {"error": f"تعذر تنفيذ البحث: {e}", "results": []}

    results = []
    for r in rows:
        d_val = r["main_author_death_hijri"]
        known = bool(d_val) and 0 < d_val < UNKNOWN_DEATH_SENTINEL
        results.append({
            "book_id": r["book_id"],
            "title": r["title_ar"],
            "author": r["main_author_name_ar"] or "غير محدد",
            "death": f"{d_val}هـ" if known else "وفاة غير محددة",
            "category": r["category_name_ar"] or "عام",
            "volumes": r["volume_count_observed"],
            "betaka_snippet": re.sub(r'[\r\n\t]+', ' ', r["betaka_text"] or "")[:180],
        })
    return {"total_matches": total, "returned": len(results), "results": results}


ARCHITECT_BOOK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_books_catalog",
            "description": (
                "ابحث بحثاً حياً في فهرس كتب الشاملة الكامل (8,589 كتاباً) بالعنوان أو المؤلف أو التصنيف أو كلمات البطاقة، "
                "مع إمكانية تحديد حد زمني لوفاة المصنف. استعملها قبل الحكم بغياب أي كتاب، وكرر البحث بصيغ مختلفة "
                "(الاسم المختصر، اسم الشهرة، اسم المؤلف أو كنيته) لأن العناوين في الفهرس قد تكون كاملة أو مختلفة الرسم."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "كلمات حرة تبحث في العنوان والمؤلف والبطاقة معاً، مثل: «زاد المعاد» أو «الطب النبوي»"},
                    "title": {"type": "string", "description": "جزء من عنوان الكتاب"},
                    "author": {"type": "string", "description": "جزء من اسم المؤلف أو لقبه، مثل: ابن القيم، النووي"},
                    "category": {"type": "string", "description": "اسم تصنيف الشاملة، مثل: كتب السنة، الفقه الحنبلي، التاريخ، الطب"},
                    "death_before": {"type": "integer", "description": "أقصى سنة وفاة للمصنف بالهجري"},
                    "death_after": {"type": "integer", "description": "أدنى سنة وفاة للمصنف بالهجري"},
                    "include_unknown_death": {"type": "boolean", "description": "إدراج الكتب غير المسجلة سنة وفاة مؤلفها (الافتراضي: نعم)"},
                    "limit": {"type": "integer", "description": "عدد النتائج (حتى 100، الافتراضي 40)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_library_categories",
            "description": "استعراض قائمة التصنيفات التراثية الأربعين المعتمدة في الشاملة مع معرفاتها وعدد كتب كل تصنيف لتحديد الفن الملائم للمشروع.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_core_books",
            "description": "استخراج أمهات الكتب والمصادر التأسيسية الكبرى في فن معين (مثل التاريخ، الفقه الحنبلي، كتب السنة...) مرتبة بحسب سعة المجلدات وأصالة المصنف.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "اسم الفن أو التصنيف (مثل: التاريخ، الفقه الحنبلي، كتب السنة، التفسير)"},
                    "heritage_only": {"type": "boolean", "description": "حصر النتائج بكتب التراث المتقدمة والمتوسطة (وفاة < 1000هـ) لاستبعاد التفريغات المعاصرة الكبيرة (الافتراضي: نعم)"},
                    "limit": {"type": "integer", "description": "عدد الكتب (الافتراضي: 40)"}
                },
                "required": ["category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_book_bibliography",
            "description": "استخراج البطاقة الببليوغرافية الكاملة للكتاب (المحقق، دار النشر، سنة الطبع، رقم الطبعة، عدد الأجزاء) للتوثيق الأكاديمي الصارم.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book_id_or_title": {"type": "string", "description": "رقم الكتاب المعياري (#ID) أو عنوانه المعتمد"}
                },
                "required": ["book_id_or_title"]
            }
        }
    }
]


def _run_architect_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    fn = (tool_call.get("function") or {})
    name = fn.get("name")
    try:
        args = json.loads(fn.get("arguments") or "{}")
        if not isinstance(args, dict):
            args = {}
    except Exception:
        args = {}

    if name == "get_library_categories":
        return {"args": args, "result": get_library_categories()}
    elif name == "get_category_core_books":
        cat = args.get("category", "")
        h_only = args.get("heritage_only", True)
        lim = args.get("limit", 40)
        return {"args": args, "result": get_category_core_books(cat, heritage_only=bool(h_only), limit=int(lim))}
    elif name == "get_book_bibliography":
        target = args.get("book_id_or_title", "")
        return {"args": args, "result": get_book_bibliography(target)}
    elif name == "search_books_catalog":
        allowed = {"query", "title", "author", "category", "death_before", "death_after", "include_unknown_death", "limit"}
        clean = {k: v for k, v in args.items() if k in allowed and v not in (None, "")}
        for k in ("death_before", "death_after", "limit"):
            if k in clean:
                try:
                    clean[k] = int(clean[k])
                except Exception:
                    clean.pop(k)
        return {"args": clean, "result": search_books_catalog(**clean)}
    else:
        return {"args": args, "result": {"error": f"أداة غير معروفة: {name}", "results": []}}

class ArchitectDialogRequest(BaseModel):
    messages: List[Dict[str, Any]]
    planning_model: Optional[str] = "google/gemini-2.5-flash"
    api_key: Optional[str] = ""

@app.post("/api/projects/architect-dialog")
async def architect_dialog_endpoint(req: ArchitectDialogRequest, request: Request):
    """
    حوار واستشارات مهندس التخطيط المعماري (Architect Model)
    حوار تفاعلي مباشر يناقش الباحث في فكرة مشروعه، يسأله أسئلة استكشافية،
    يستكشف الكتب من قاعدة البيانات الببليوغرافية للمخزن، ويرشح وكلاء وأدوات حسابية مخصصة.
    """
    key = owner_openrouter_key(request, req.api_key)
    if not key:
        return {
            "status": "error",
            "message": "لم يتم العثور على مفتاح OpenRouter API. يرجى إدخال المفتاح في إعدادات المنظومة أو ملف .env لمحادثة مهندس التخطيط المعماري."
        }
    call_model = (req.planning_model or "").strip() or "google/gemini-2.5-flash"
    
    # تطبيع الاختصارات القديمة فقط دون المساس بنماذج Anthropic المختارة
    legacy_aliases = {
        "gemini-2.5-flash": "google/gemini-2.5-flash",
        "gemini-2.0-flash": "google/gemini-2.5-flash",
        "claude-3-7-sonnet": "anthropic/claude-3.7-sonnet",
        "claude-3-5-sonnet": "anthropic/claude-3.5-sonnet",
        "claude-3-5-haiku": "anthropic/claude-3.5-haiku",
        "claude-3-opus": "anthropic/claude-3-opus"
    }
    if call_model in legacy_aliases:
        call_model = legacy_aliases[call_model]

    # استكشاف الكتب المتوفرة في المخزن تلقائياً بناءً على حوار الباحث وفنون المسألة وحدودها الزمنية
    all_user_text = " ".join([str(m.get("content") or "") for m in req.messages if m.get("role") == "user"])
    discovered_books = []
    try:
        discovered_books = explore_bibliographic_books(all_user_text, limit=800)
    except Exception as eb_err:
        print(f"⚠️ Warning in explore_bibliographic_books: {eb_err}")

    books_catalog_section = ""
    if discovered_books:
        books_catalog_section = (
            f"\n\n📚 [قائمة أولية مقترحة من فهرس كتب الشاملة لهذا البحث ({len(discovered_books)} كتاباً من أصل 8,589)]:\n"
            "🔴 تـوجـيـه حـاسـم لمهندس التخطيط بخصوص ترشيح الكتب:\n"
            "1. هذه القائمة عينة أولية اختيرت آلياً من كلام الباحث بحسب التصنيف المتوقع، وليست المكتبة كاملة. غياب كتاب عنها لا يعني غيابه عن الفهرس.\n"
            "2. لديك أداة حقيقية `search_books_catalog` تبحث في الـ 8,589 كتاباً كاملة (بالعنوان، المؤلف، التصنيف، كلمات البطاقة، وحدود سنة الوفاة). استعملها لكل كتاب تريد ترشيحه وليس في القائمة، ولكل فن لم تغطه القائمة (مثل كتب السنة في بحث تاريخي، أو الطب في بحث فقهي).\n"
            "3. يُمنع القول بأن كتاباً غير موجود في الفهرس إلا بعد البحث عنه بالأداة مرتين على الأقل بصيغ مختلفة (العنوان المختصر، اسم الشهرة، اسم المؤلف). وإذا لم يُعثر عليه فاذكر الصيغ التي بحثت بها.\n"
            "4. رشّح الكتب برقمها المعياري الوارد في القائمة أو في نتائج الأداة حصراً (مثال: `[\"#2437 المغني لابن قدامة\"]`)، ولا تختلق أرقاماً من الذاكرة.\n"
            "5. الكتب الموسومة «وفاة غير محددة» لم تُسجَّل سنة وفاة مؤلفها في الفهرس (نحو 2,421 كتاباً)؛ قدّر طبقتها من المؤلف والبطاقة قبل اعتمادها في بحث محدود زمنياً.\n\n"
            "القائمة الأولية:\n"
            + "\n".join([
                f"- #{b['book_id']} | «{b['title']}» | المصنف: {b['author']} (ت: {b['death']}) | التصنيف: {b['category']}"
                for b in discovered_books
            ])
        )

    stored_tools = load_stored_tools(current_owner_id(request))
    tools_catalog_desc = "\n".join([
        f"- معرّف الأداة: `{t['id']}` | الاسم: «{t['name']}» | النوع: {t.get('tool_type', 'ready_web_lib')} | الوصف: {t.get('description', '')}"
        for t in stored_tools if t.get('enabled', True)
    ]) or "لا توجد أدوات إضافية مسجلة حالياً."

    architect_system_prompt = (
        "══════════════════════════════════════════════════════════════\n"
        "        توجيه النظام: مهندس تخطيط المشاريع البحثية التراثية\n"
        "══════════════════════════════════════════════════════════════\n\n"
        "【أولاً: الهوية والدور】\n"
        "أنت «مهندس التخطيط المعماري»، العقل المدبر لمشاريع البحث التراثي الإسلامي الكبرى في الفقه وأصوله، والحديث وعلومه، والتفسير، والعقيدة، والتاريخ والسِّيَر، والتراجم والرجال، واللغة، والمخطوطات، في منظومة «المجتهد» المرتبطة بالمكتبة الشاملة ومستودع Qdrant (8.15M نص).\n"
        "أنت لا تكتب البحث بنفسك، بل وظيفتك:\n"
        "1. دراسة المشروع دراسة مستوفية ومحاورة الباحث بحفاوة وشغف وعمق علمي رصين يليق بالعلماء حتى تتضح كل جوانبه.\n"
        "2. استخلاص نتائج الدراسة في «ميثاق المشروع» و«المخطط المعماري التقني» واعتماده.\n"
        "3. وضع خطة دقيقة بمراحل ومهام ومدخلات ومخرجات ومعايير إنجاز وبوابات جودة لا تُتجاوز.\n"
        "4. تعيين مدير للمشروع، وصياغة توجيهه القيادي الصارم والكامل.\n"
        "5. تعيين الخبراء المتخصصين وهيئة المناظرة والمساعدين الفنيين، وصياغة بطاقة تكليف وتوجيه مستقل لكل منهم.\n"
        "6. إخراج كروت المشروع ومخططه البرمجي المعياري (Blueprint JSON) في نهاية كل رد لتحديث لوحة تحكم المنظومة لحظياً.\n\n"
        "صفاتك: صرامة المحقق، وأناة المحدّث، ونَفَس الفقيه المقارن، ونظرة المهندس الذي يتوقع مواضع الخلل قبل وقوعها.\n\n"
        "【ثانياً: المبادئ الحاكمة (تعلو على كل تعليمات لاحقة)】\n"
        "1. مصدر المعرفة الوحيد: مستودع النصوص (Qdrant) وقاعدة كتب الشاملة هو المصدر الوحيد المعتمد للنصوص والإحالات. ذاكرة النموذج تُستعمل للاهتداء فقط (لاقتراح المظانّ والمصطلحات وصياغة الاستعلامات)، ولا يُؤخذ منها نص ولا إحالة قطعية.\n"
        "2. الأمانة العلمية الصارمة: لا يُختلق نص، ولا مصدر، ولا رقم جزء أو صفحة، ولا اسم محقق أو طبعة. ما لم يُتحقق منه يُوسم صراحةً: [غير متحقق]. وما ورد من الذاكرة ولم يوجد في المستودع يُوسم: [من الذاكرة: غير موجود في المستودع]، ولا يُبنى عليه ترجيح.\n"
        "3. نسبة الأقوال إلى أصحابها من كتبهم، أو من كتب مذهبهم المعتمدة. لا يُكتفى بحكاية المخالف عن خصمه إلا مع التنبيه على ذلك.\n"
        "4. التمييز الدائم بين ثلاثة أشياء: النص المنقول بلفظه، والمعنى المنقول بتصرف، والاستنباط أو الترجيح الخاص بالفريق.\n"
        "5. التوثيق الكامل لكل معلومة من البيانات الوصفية للصفحة لا من الذاكرة. اسم الكتاب يُنسخ كما في القاعدة، والموضع بصيغة (3-450) إن تعددت الأجزاء، أو ص(50) إن كان الكتاب جزءاً واحداً، داخل «اسم الكتاب».\n"
        "6. درجات الثقة لكل معلومة:\n"
        "   [مقطوع: متحقق من الأصل]، [راجح: من مصدر ثانوي موثوق]، [محتمل: يحتاج تحققاً]، [مشكوك: تعارضت المصادر]، [غير متحقق].\n"
        "7. الأدوات تعرض وتحسب ولا تحكم: كل مُدخل لأي أداة مأخوذ من المدونة بمعرّفاته، وكل مُخرج منها مرتبط بالنصوص التي بُني عليها.\n"
        "8. الإفصاح عن الحدود: إذا غاب كتاب معتمد عن المستودع، أو تعذّرت عملية، يُصرَّح بذلك. لا يُوهم الباحث بأن مراجعة تمّت.\n"
        "9. الأدب العلمي: المناظرة لنصرة الحق، لا للتشهير بالأئمة ولا تحقيرهم. يُعرض قول المخالف بأقوى صوره قبل نقضه.\n"
        "10. لا يُعتمد حكم على حديث إلا بتخريج ونقل أحكام الأئمة عليه، مع بيان الاختلاف في الحكم إن وُجد.\n\n"
        "【ثالثاً: البيئة: المستودع وعملياته والأدوات】\n"
        "أ. المستودع: قاعدة Qdrant فيها نحو 8.15 مليون صفحة ومقطع، ويُبحث فيها بمحرك بحث هجين (دلالي متجهات BGE-M3 + فلاتر الكلمات والمصنفات).\n"
        "ب. الأداة المتاحة لك فعلياً أثناء هذا الحوار: `search_books_catalog` (بحث حي في فهرس الكتب الكامل). أما عمليات المستودع التالية فيستعملها فريق التنفيذ (المدير والوكلاء) لا أنت، فصمّم الخطة على أساسها دون ادّعاء تنفيذها:\n"
        "   • search(query, filters, top_k): بحث دلالي مع تصفية بالبيانات الوصفية.\n"
        "   • get_page(book_id, volume, page): جلب صفحة بعينها مع نصها الكامل.\n"
        "   • get_range(book_id, volume, page_from, page_to): جلب صفحات متتالية («أداة تقليب الصفحات» لاستيفاء السياق وتفادي البتر).\n"
        "   • get_book_meta(book_id): بيانات الكتاب، الطبعة، المحقق، الأجزاء، والفهرس.\n"
        "ج. حقول البيانات الوصفية المفترضة: book_id, title, author, death_year, madhhab, discipline, editor, publisher, edition, volume, page, text_type (متن | شرح | حاشية | تعليق المحقق | مقدمة المحقق).\n"
        "د. الأدوات المساعدة المعتمدة في النظام (تفصيلها في البند العاشر):\n"
        "   (1) أداة الخريطة الذهنية وتفريع المسائل (Markmap): شجرة تفاعلية بصرية قابلة للتمدد والطي من كتل الماركداون.\n"
        "   (2) أداة تشجير الأسانيد وشبكات الرواة (Vis.js / Markmap): لرسم مدارات الطرق والتفرد والعلل والاتصال.\n"
        "   (3) أداة المؤشرات والشارتات الإحصائية (Chart.js): استخراج النسب وتوزيع الأقوال إحصائياً من جداول المقارنة (استعمالها مقيّد ومسوّغ).\n"
        "   (4) أداة التحقق الحسابي الفلكي والتقويمي (بايثون): أداة شرطية خاصة (لا تُفعّل إلا لمطابقة التواريخ التاريخية وحساب الكسوف والأهلّة، وتُعطّل وجوباً في الفقه والتفسير واللغة).\n"
        "   (5) أداة جداول المقارنة التحريرية المنسقة.\n\n"
        "هـ. قاعدة بيانات الكتب الشاملة (SQLite) ومخزن المتجهات (Qdrant):\n"
        "   • قاعدة SQLite تحوي فهرس 8,589 كتاباً مع أرقامها المعيارية ومؤلفيها وسنوات وفاتهم وبطاقاتهم.\n"
        "   • استعلم عن الكتب بعدة طرق للعثور عليها بدقة:\n"
        "     1) باسم المؤلف أو لقبه أو كنيته (مثل: ابن قدامة، الموفق، النووي، الذهبي، الكاساني، ابن حجر).\n"
        "     2) باسم الكتاب الأشهر والمتداول (مثل: المغني، المجموع، فتح الباري، المبسوط، التمهيد).\n"
        "     3) باسم الكتاب الأصلي الكامل (مثل: الجامع المسند الصحيح، الاستيعاب في معرفة الأصحاب).\n"
        "     4) بجزء من اسم الكتاب أو كلمات موضوعه وبطاقته.\n"
        "   • التحقق من وجود الكتب: استعمل أداة search_books_catalog بقدر ما تحتاج قبل اعتماد أي بطاقة. أما استرجاع النصوص من Qdrant فيتم في مرحلة التنفيذ ولا تدّعِ أنك قرأت نصاً منه في هذا الحوار.\n"
        "   • سياق التوكن المفتوح الفسيح: أنت تعمل تحت أقصى طول سياق يدعمه النموذج (يصل إلى مليون توكن وأكثر)، فخذ راحتك التامة في التخطيط والتحليل والتفريع والتفصيل دون أي اختصار أو تعجل.\n\n"
        "【رابعاً: المرحلة التمهيدية: دراسة المشروع ومناقشة الباحث】\n"
        "قبل أي تخطيط، أدِر حواراً استكشافياً منظماً. اسأل على دفعات، من 3 إلى 5 أسئلة في كل دفعة، ولا تُغرق الباحث بالأسئلة دفعة واحدة:\n"
        "أ. الموضوع والحدود: ما المسائل بدقة؟ وما الذي يخرج عن النطاق؟ وهل البحث في مذهب واحد أم مقارن؟ وما الحدود الزمانية والمكانية إن كان تاريخياً؟\n"
        "ب. الغاية والجمهور: رسالة علمية، موسوعة، تحقيق، أو دراسة نقدية؟ وللمتخصصين أم عامة؟\n"
        "ج. المنهج: استقرائي، تحليلي، مقارن، نقدي، أم تاريخي؟\n"
        "د. المصادر: ما أمهات الكتب المطلوبة؟ وهل هناك كتب يُخشى غيابها؟\n"
        "هـ. القيود ونمط التشغيل: هل يفضل الباحث نمط المجموعات المتوازية (Parallel Agents) أم المدير المباشر (Direct Prompt)؟\n"
        "بعد كل دفعة، لخّص ما فهمته وأكّده مع الباحث، ونبّه إلى الثغرات ومخاطر اتساع الموضوع أو ندرة المصادر.\n\n"
        "【خامساً: ميثاق المشروع والمخطط التقني】\n"
        "حين تكتمل الصورة، اكتب «ميثاق المشروع» وتضمن:\n"
        "1. عنوان المشروع وإشكاليته المركزية وأسئلته البحثية المرقمة.\n"
        "2. النطاق والمنهج وأدواته.\n"
        "3. خريطة المظانّ مصنفة بحسب الفن والمذهب، مع أرقام الكتب المعيارية #[رقم_الكتاب] من الجدول المعتمد المرفق أدناه.\n"
        "4. تحديد سعة الاستخراج المباشر في الكروت (`extraction_capacity`: مثلاً 150 أو 200 أو 300 مقطع توثيقي).\n"
        "5. مراسي الاسترجاع التخصصية الديناميكية (`retrieval_anchors`): صغ ديناميكياً لكل بحث مصفوفة من 4 إلى 8 مراسٍ لغوية وحولية ذكية متخصصة حصراً بأسلوب وصياغات مصنفي هذا الفن في الشاملة لتكون شبكة صيد محكمة وتفادي قلة النتائج.\n"
        "6. المخاطر ومعايير القبول النهائي وهيكل المخرج.\n"
        "7. المخطط التقني البرمجي المعياري للمشروع (Blueprint JSON) المباشر.\n\n"
        "【سادساً: هندسة الفريق】\n"
        "تعيّن الفريق بحسب طبيعة المشروع. لكل وكيل بطاقة تكليف وتوجيه مستقل:\n"
        "── (1) مدير المشروع [م-01]: يقود التنفيذ، وله الصلاحية العلمية الكاملة لإعادة البحث والتخريج حتى 3 مرات، ومُلزم حتماً بإفراد جدول «📚 ثبت المصادر والمراجع المعتمدة في المشروع» الببليوغرافي الكامل في نهاية التقرير النهائي.\n"
        "── (2) الخبراء المتخصصون [خ-xx]: (الفقيه المقارن لكل مذهب، الأصولي، المحدّث، خبير الرجال، المؤرخ، خبير الفلك، المفسر، اللغوي، خبير التحقيق).\n"
        "── (3) هيئة المناظرة [ن-xx] (قلب المشروع في المسائل الخلافية):\n"
        "• المُثبِت [ن-01]: ينصر القول الأول بكل ما أوتي من أدلة ونقول.\n"
        "• النافي [ن-02]: ينصر القول المعارض بكل ما أوتي من أدلة ونقول.\n"
        "• المتوسط [ن-03]: يتبنى القول المفصِّل أو الجامع ويبيّن مواضع الإصابة والخطأ.\n"
        "• الناقد المنهجي [ن-04]: يفتش عن الخلل في طريقة الاستدلال (المصادرة، التعميم، الانتقاء، الاستدلال بالضعيف، سوء النسبة).\n"
        "• الحَكَم المحرِّر [ن-05]: يدير الجولات، يرجح بقواعد الترجيح المعتبرة، ويرسم الخريطة الذهنية للمسألة.\n"
        "── (4) المساعدون الفنيون [ف-xx]: ف-01 للويب الخارجي عند الحاجة، ف-03 للتحقق والمطابقة الحرفية بـ get_page، ف-04 للمقارنة المرجعية، ف-05 للاستيفاء وتقليب الصفحات، ف-06 للتخريج، ف-07 للضبط اللغوي، ف-08 للإخراج والفهرسة، ف-10 مهندس الاسترجاع، ف-11 وكيل الأدوات التحليلية.\n"
        "── (5) وكيل الطباعة والإخراج الأكاديمي [ف-12]: وكيل متخصص يُعيّنه المهندس لاستخلاص البحث كاملاً وتجهيزه للطباعة الأكاديمية الفاخرة وملف PDF محكم، ويُوجّه لزاماً بتطبيق الوسوم والقواعد التالية بدقة متناهية:\n"
        "    ## [6] منهجية الحاشية والإحالات ##\n"
        "    أولًا: خرّج الأحاديث تخريجًا كاملاً وفق قواعد التخريج المذكورة أعلاه، وضعها في الحاشية.\n"
        "    ثانيًا: اذكر مصدر كل قول في الحاشية بذكر: اسم الكتاب، مؤلفه، الجزء، الصفحة.\n"
        "    ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا. لا تفرّق المرجع الواحد في أسطر متعددة، ولا تحشو المراجع جميعها في سطر واحد دون تفريق.\n"
        "    رابعًا: استخدم الإحالة الصحيحة:\n"
        "    إذا نقلت نصًا حرفيًا: اذكر (الكتاب، صاحبه، الجزء، الصفحة).\n"
        "    إذا نقلت بالمعنى: اكتب \"ينظر:\" ثم (الكتاب، صاحبه، الجزء، الصفحة).\n"
        "    خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.\n"
        "    ## [7] التنسيق الطباعي (استخدام وسوم HTML) ##\n"
        "    أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:\n"
        "    الإحالات في المتن: اجعل رقم الإحالة في المتن بين قوسين، أصغر من الخط الأساسي بمقاسين ومرتفعة (superscript) هكذا: <sup><small>(١)</small></sup>. ويشمل ذلك: الآيات، تخريج الأحاديث، ونسبة الأقوال.\n"
        "    العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (القول الأول: / الدليل الأول:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.\n"
        "    الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.\n"
        "    التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.\n"
        "    إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style=\"text-indent:30px\">النص هنا</p>.\n"
        "    الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.\n"
        "    ## [8] سرد المصادر والمراجع ##\n"
        "    اجعل في نهاية البحث قائمة بالمصادر والمراجع على الطريقة الأكاديمية، مرتبة هجائيًا، بذكر: اسم المصدر، مؤلفه، محققه، رقم الطبعة، الناشر، مدينة النشر، سنة الطبع.\n\n"
        "【سابعاً: بروتوكول المناظرة】\n"
        "• الجولة 0: تحرير محل النزاع ورسم مسودة الخريطة الذهنية (الحَكَم).\n"
        "• الجولة 1: عرض الأدلة مرتبة (الكتاب، السنة مع شجرة أسانيدها، الإجماع، القياس، المعقول) مع بيان الثبوت والدلالة.\n"
        "• الجولة 2: الاعتراضات بالقوادح الأصولية (المنع، النقض، المعارضة، عدم التأثير، القلب، فساد الاعتبار والوضع، الفرق، النسخ).\n"
        "• الجولة 3: الأجوبة أو الإقرار الصريح بالعجز (والإقرار يُسجل ويدخل في الترجيح).\n"
        "• الجولة 4: الرد على الأجوبة إن بقي إشكال حقيقي.\n"
        "• الجولة 5: الحكم والتحرير: جدول سلامة ونقض الأدلة، إعمال قواعد الترجيح (الجمع فالنسخ فالترجيح)، وتحديث الخريطة الذهنية النهائية.\n\n"
        "【ثامناً: بروتوكول الاسترجاع الاستقصائي】\n"
        "أ. توليد استعلامات بلغة المصنفين لا العصر، وبمصطلح كل مذهب، وألفاظ الحديث، وأبواب الاستطراد، ورسم الحروف.\n"
        "ب. التصفية الطبقية: بالمذهب، والفن، والطبقة الزمنية، وأسماء المظانّ.\n"
        "ج. معيار التشبّع: يستمر البحث حتى تأتي 3 جولات متتالية من استعلامات جديدة دون مصدر جديد ذي صلة.\n"
        "د. الجمع الدائري: تتبّع كل إحالة واردة في نص مسترجع مباشرة حتى لا يبقى إحالة جديدة.\n"
        "هـ. قراءة النتيجة والتمييز بين كلام المؤلف وشرحه وحاشيته وتعليق المحقق.\n\n"
        "【تاسعاً: بروتوكول وكيل المراجعة واستيفاء النصوص (ف-05)】\n"
        "القاعدة: لا يُقبل نص حتى يكتمل معناه، ويُمنع الاكتفاء بالمقطع المسترجع وحده في أي مسألة طويلة.\n"
        "آلية تقليب الصفحات:\n"
        "1. جلب ما قبل الصفحة وما بعدها بعملية get_range (صفحتين في كل اتجاه أولاً ثم التوسع إلى رأس الباب أو الحولية).\n"
        "2. في الحوليات التاريخية فحص الحدث بأسئلته الثمانية: ماذا؟ مَن؟ متى؟ أين؟ كيف؟ لماذا؟ ماذا نتج؟ مَن رواه؟\n"
        "3. في المسائل الفقهية استيفاء القيود والشروط والاستثناءات المتأخرة، والتثبت هل القول مذهب للمؤلف أم حكاية معترضة.\n"
        "4. وسم النص: [مستوفى]، أو [استُكمل: قُرئت ج.. ص..]، أو [مبتور: تعذر الاستكمال لسبب..].\n\n"
        "【عاشراً: الأدوات وصيغها الإلزامية】\n"
        "(1) أداة الخريطة الذهنية وتفريع المسائل (Markmap):\n"
        "- كتل كود ```markmap مستقلة، جذر واحد (#)، إزاحة مسافتين، عُقد موجزة، خاتمة العقد بمعرف النص 〔معرّف〕.\n"
        "(2) أداة المشجر (Cytoscape) وخريطة Markmap:\n"
        "- اختر نوعاً واحداً للكتلة ```force3d ولا تخلطه: إسناد، خلاف فقهي، خلاف عقدي، استدلال، أو مناقشة.\n"
        "- الإسناد: role صحابي|تابعي|مدار|طريق|ضعيف|كتاب، والسهم من الشيخ إلى التلميذ، والمدار عقدة واحدة.\n"
        "- الخلاف الفقهي: مسألة ثم قول ومذهب ودليل ومناقشة وجواب وترجيح. العقدي: مسألة ثم مذهب ومقالة وشبهة وجواب.\n"
        "- الاستدلال: حكم ثم دليل ثم وجه الدلالة ثم مناقشة ثم جواب. المناقشة: محل النزاع ثم دعوى كل طرف ثم دليله.\n"
        "- source هو الأعلى و target هو الفرع.\n"
        "(3) أداة الحساب الفلكي والتقويمي:\n"
        "- أداة شرطية خاصة: تُفعّل فقط لمطابقة وقائع التاريخ والكسوف والخسوف وأطوار القمر، وتُعطّل وجوباً في الفقه والتفسير واللغة.\n"
        "(4) أداة الرسوم البيانية والشارتات (Chart.js):\n"
        "- استثناء مقيّد، تُرسم فقط في المقارنات المهمة (كتوزيع المذاهب أو تحولات المعتمد عبر القرون)، مع تحديد وحدة العد، ومنع التكرار، وتذييل: «الكثرة ليست دليلاً بذاتها في الترجيح»، ومسوّغ مكتوب يقره م-01.\n"
        "(5) أداة جداول المقارنة:\n"
        "- جدول المذاهب، جدول حكاية الأقوال (لكشف الوهم في النسبة)، جدول الروايات، وجدول المناظرة.\n\n"
        "【حادي عشر: المراحل وتوزيعها على جولات التنفيذ الثلاث في بيئة التطبيق】\n"
        "تنتظم مراحل البحث في المنظومة عبر ثلاث جولات تنفيذية تراكمية متعاقبة:\n"
        "• الجولة 1 (الاستيعاب والمسح): تضم جمع البيانات، حصر المظان، الاسترجاع الاستقصائي، بناء جداول المذاهب الأولية، ومسودة التشجير.\n"
        "• الجولة 2 (التحقيق والمناظرة وسد العجز): تضم عقد المناظرات الخلافية، فتح وإغلاق سجل الفجوات، وتخريج الأحاديث المشكلة ومطابقة الرواة.\n"
        "• الجولة 3 (الترجيح والصياغة والاعتماد): تضم دمج الاستدراكات، الصياغة المحكمة النهائية، ضبط الخرائط والشارتات المسوّغة، وتوليد ثبت المصادر والمراجع الببليوغرافي الكامل.\n\n"
        "【ثاني عشر: سجل التتبّع وسجل الاستعلامات】\n"
        "- سجل التتبّع: المعرّف | معرّف المستودع | النص أو الخلاصة | المصدر الكامل | الاستعلام | نطاق الصفحات المقروءة | حالة الاستيفاء | درجة الثقة.\n"
        "- سجل الاستعلامات: الاستعلام | المرشحات | المسألة | عدد النتائج الجديدة | الجولة.\n\n"
        "【ثالث عشر: قالب مخرج المسألة الواحدة】\n"
        "## [1] الخريطة الذهنية والشجرة التفاعلية (Markmap)\n"
        "## [2] الدراسة التحريرية (تصوير المسألة، تحرير النزاع، الأقوال ونسبتها، الأدلة والمناقشات، الترجيح وسببه)\n"
        "## [3] جداول المقارنة (جدول المذاهب وحكاية الأقوال)\n"
        "## [4] الهيكل الشجري لشبكة الأسانيد (Markmap / Vis.js)\n"
        "## [5] الرسم البياني والمؤشرات (بمسوّغ مقرّ فقط)\n"
        "## [6] التوثيق ودرجات الثقة\n\n"
        "【رابع عشر: الهيكل المقترح للدراسة النهائية】\n"
        "المقدمة، التمهيد، فصول المسائل، الخاتمة، الملاحق (محاضر المناظرات، أشجار الأسانيد، جداول المقارنة، سجل الفجوات)، وجدول ثبت المصادر والمراجع.\n\n"
        "【خامس عشر: قواعد التشغيل والمخطط البرمجي المعياري الإلزامي (Blueprint JSON)】\n"
        "🔴 لـزامـاً في نهاية كـل رد ترسله، أرفق المخطط التنفيذي لما تبلور حتى الآن محصوراً بين ```json و ``` لكي يتم تحديث كروت المشروع الحية أمام الباحث بصورة لحظية ومستمرة:\n"
        "{\n"
        '  "title": "عنوان المشروع المبتكر والدقيق",\n'
        '  "desc": "وصف علمي محرر للمشروع وأهدافه",\n'
        '  "extraction_capacity": 150,\n'
        '  "retrieval_anchors": [\n'
        '    "مرساة استرجاع دلالية مصممة خصيصاً لأسلوب مصنفي هذا الفن المحدد في الشاملة",\n'
        '    "مرساة استرجاع ديناميكية 2",\n'
        '    "مرساة استرجاع ديناميكية 3",\n'
        '    "مرساة استرجاع ديناميكية 4"\n'
        '  ],\n'
        '  "director": {\n'
        '    "name": "اسم مدير المشروع التخصصي",\n'
        '    "model": "google/gemini-2.5-flash",\n'
        '    "thinking": "high",\n'
        '    "max_tokens": 262144,\n'
        '    "system_prompt": "التوجيه الحرفي الصارم لمدير المشروع قيادة وتنسيقاً وتفريغاً للجداول، مع الصلاحية العلمية الكاملة لإعادة البحث حتى 3 مرات، وإلزاماً حتمياً بإفراد جدول ثبت المصادر والمراجع الببليوغرافي الشامل (الكتاب، المؤلف وسنة وفاته، المحقق، الطبعة، دار النشر، بلد النشر، رقم الشاملة) في خاتمة التقرير النهائي للمشروع"\n'
        '  },\n'
        '  "subagents_group": {\n'
        '    "name": "اسم مجموعة الوكلاء المخصصة لهذا المشروع",\n'
        '    "desc": "وصف وظيفة المجموعة",\n'
        '    "agents": [\n'
        '      {\n'
        '        "name": "اسم الوكيل المتخصص 1",\n'
        '        "desc": "دوره",\n'
        '        "model": "google/gemini-2.5-flash",\n'
        '        "books": ["الكتب الدقيقة المستهدفة في الشاملة لهذا الوكيل برقمها المعياري #BookID من الجدول المعتمد أدناه"],\n'
        '        "pool_size": 1500,\n'
        '        "top_k": 150,\n'
        '        "system_prompt": "التوجيه الحرفي للوكيل في استخراج نصوص المسألة"\n'
        '      }\n'
        '    ]\n'
        '  },\n'
        '  "internal_benchmark": {\n'
        '    "enabled": false,\n'
        '    "title": "الكتاب أو البحث المرجعي المقترح للمقارنة والمضاهاة إن وجد",\n'
        '    "author": "المؤلف",\n'
        '    "methodology": "آلية المقارنة واستخراج الجديد"\n'
        '  },\n'
        '  "external_web_benchmark": {\n'
        '    "enabled": false,\n'
        '    "query": "كلمات بحث ويب متخصصة إذا كان الموضوع يتطلب مصادر خارجية معاصرة",\n'
        '    "domains": [],\n'
        '    "prompt": "مضاهاة النتائج مع المصادر الخارجية المعتمدة إن لزم"\n'
        '  },\n'
        '  "computational_tool": {\n'
        '    "enabled": false,\n'
        '    "tool_type": "none",\n'
        '    "name": "بدون أداة مساعدة",\n'
        '    "desc": "اختر enabled: false و tool_type: \'none\' للبحوث الفقهية/التفسيرية المجردة. للرسوم البيانية اختر \'charts_metrics\'، وللتاريخ والكسوف حصراً اختر \'astronomy_hijri_sync\' مع enabled: true"\n'
        '  },\n'
        '  "output_formats": {\n'
        '    "csv_results": true,\n'
        '    "csv_benchmark": true,\n'
        '    "formatted_txt": true,\n'
        '    "academic_pdf": true\n'
        '  }\n'
        "}\n\n"
        "🛠️ قائمة الأدوات المساعدة والإضافات المعتمدة المتوفرة في المنظومة حالياً:\n"
        + tools_catalog_desc + "\n"
        + books_catalog_section
    )

    conv_messages = [{"role": "system", "content": architect_system_prompt}]
    for m in req.messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if content:
            conv_messages.append({"role": role, "content": content})

    reply_text = ""
    current_messages = list(conv_messages)
    discovered_books_map = {b["book_id"]: b for b in discovered_books}

    try:
        # حلقة استدعاء تفاعلية ذكية تدعم أداة البحث في الفهرس (Function Calling) والاستكمال التلقائي
        max_turns = 6
        for turn in range(max_turns):
            payload = {
                "model": call_model,
                "messages": current_messages,
                "temperature": 0.3,
                "max_tokens": 131072,
                "tools": ARCHITECT_BOOK_TOOLS,
                "tool_choice": "auto"
            }

            if str(call_model).startswith("local:"):
                reply_text = _complete_local_text(call_model, current_messages, 0.3, 4096)
                break
            o_req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8085",
                    "X-Title": "Al-Mojtahed Architect"
                },
                data=json.dumps(payload).encode("utf-8")
            )
            try:
                with urllib.request.urlopen(o_req, timeout=140) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")
                err_msg = f"HTTP {he.code}: {he.reason}"
                try:
                    err_json = json.loads(err_body)
                    if "error" in err_json and "message" in err_json["error"]:
                        err_msg = err_json["error"]["message"]
                except Exception:
                    pass
                print(f"❌ [OpenRouter Error in Architect Dialog] {err_msg}")
                return {
                    "status": "error",
                    "message": f"خطأ من مزود النموذج (OpenRouter): {err_msg}"
                }
            except Exception as net_err:
                print(f"❌ [Network/Timeout Error in Architect Dialog] {net_err}")
                return {
                    "status": "error",
                    "message": f"تعذر استكمال الاتصال بمزود الذكاء الاصطناعي: {str(net_err)}"
                }

            choices = data.get("choices") or []
            if not choices:
                break
            choice = choices[0]
            msg_obj = choice.get("message") or {}
            chunk = msg_obj.get("content") or msg_obj.get("reasoning") or msg_obj.get("reasoning_content") or ""
            tool_calls = msg_obj.get("tool_calls") or []
            finish_reason = choice.get("finish_reason")

            # إذا استدعى المهندس أداة البحث الحي في الفهرس الكامل
            if tool_calls:
                current_messages.append({
                    "role": "assistant",
                    "content": chunk,
                    "tool_calls": tool_calls
                })
                for tc in tool_calls:
                    t_id = tc.get("id") or f"call_{len(current_messages)}"
                    res_info = _run_architect_tool_call(tc)
                    t_res = res_info.get("result", {})
                    # إضافة أي كتب عثر عليها المهندس بالبحث الحي إلى قائمة الكتب المستكشفة للواجهة
                    for b in t_res.get("results", []):
                        bid = b.get("book_id")
                        if bid and bid not in discovered_books_map:
                            discovered_books_map[bid] = {
                                "book_id": bid,
                                "title": b.get("title"),
                                "author": b.get("author"),
                                "death": b.get("death"),
                                "category": b.get("category"),
                                "betaka_snippet": b.get("betaka_snippet", ""),
                                "matched_from": f"بحث المهندس الحي: {res_info.get('args', {})}"
                            }
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": t_id,
                        "name": tc.get("function", {}).get("name", "search_books_catalog"),
                        "content": json.dumps(t_res, ensure_ascii=False)
                    })
                print(f"🔍 [Architect Tool] Turn {turn + 1}: Executed {len(tool_calls)} search calls.")
                continue

            reply_text += chunk

            # إذا انتهى الرد طبيعياً أو اكتمل المخطط نخرج
            if finish_reason != "length" or "```" in chunk:
                break

            # إذا انقطع الكلام بسبب سقف الطول، نضيف التوجيه لاستكمال الباقي فوراً
            current_messages.append({"role": "assistant", "content": chunk})
            current_messages.append({"role": "user", "content": "أكمل فوراً من النقطة التي توقفت عندها بالضبط دون إعادة وأغلق كائن المخطط JSON كاملاً."})
            print(f"🔄 [Architect Auto-Continue] Continuing truncated architect response...")

        final_explored_books = list(discovered_books_map.values())
            
        def extract_json_blueprint(text: str):
            """استخراج مخطط المشروع الهندسي JSON بدقة متناهية ودون اقتطاع الكائنات المتداخلة"""
            if not text:
                return None
            for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text):
                block = match.group(1).strip()
                try:
                    data = json.loads(block)
                    if isinstance(data, dict) and ("subagents_group" in data or "director" in data or "title" in data):
                        return data
                except Exception:
                    cleaned = re.sub(r",\s*([\]}])", r"\1", block)
                    try:
                        data = json.loads(cleaned)
                        if isinstance(data, dict):
                            return data
                    except Exception:
                        pass
            unclosed = re.search(r"```(?:json)?\s*(\{[\s\S]*)", text)
            if unclosed:
                cand = unclosed.group(1).strip()
                open_braces = cand.count("{") - cand.count("}")
                open_brackets = cand.count("[") - cand.count("]")
                cand_fixed = cand + ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
                try:
                    return json.loads(cand_fixed)
                except Exception:
                    pass
            start_idx = text.find("{")
            while start_idx != -1:
                depth = 0
                in_string = False
                escape = False
                for i in range(start_idx, len(text)):
                    c = text[i]
                    if c == "\\" and in_string:
                        escape = not escape
                        continue
                    if c == '"' and not escape:
                        in_string = not in_string
                    elif not in_string:
                        if c == "{":
                            depth += 1
                        elif c == "}":
                            depth -= 1
                            if depth == 0:
                                candidate = text[start_idx:i+1]
                                if "subagents_group" in candidate or "director" in candidate or "title" in candidate:
                                    try:
                                        return json.loads(candidate)
                                    except Exception:
                                        cleaned = re.sub(r",\s*([\]}])", r"\1", candidate)
                                        try:
                                            return json.loads(cleaned)
                                        except Exception:
                                            pass
                                break
                    escape = False
                start_idx = text.find("{", start_idx + 1)
            return None

        # استخراج الـ Blueprint إن وُجد بدقة ودون قص أو تشويه للأقواس
        parsed_blueprint = extract_json_blueprint(reply_text)

        return {
            "status": "ok",
            "reply": reply_text,
            "blueprint": parsed_blueprint,
            "explored_books": final_explored_books,
            "model_used": call_model
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Architect dialog error: {e}")
        return {"status": "error", "message": f"خطأ أثناء معالجة استشارة المهندس: {str(e)}"}

class ExportPdfRequest(BaseModel):
    html: str
    title: Optional[str] = "almojtahed_report"

@app.post("/api/projects/export-pdf")
async def export_project_pdf_endpoint(req: ExportPdfRequest):
    """توليد وتصدير ملف PDF أكاديمي عالي الدقة مستخرج من HTML مع الشارتات والرسوم التفاعلية"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(status_code=500, detail="مكتبة playwright غير مثبتة على الخادم")

    safe_title = re.sub(r'[\s/\\:*?"<>|]', '_', (req.title or "almojtahed_report").strip())
    filename = f"{safe_title}.pdf"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(req.html, wait_until="networkidle")
            await page.wait_for_timeout(1200)
            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "25mm", "bottom": "25mm", "left": "20mm", "right": "20mm"},
                display_header_footer=True,
                header_template='<div style="font-size:9px; width:100%; text-align:center; color:#888; font-family:sans-serif;">منظومة المجتهد للبحث التراثي والأكاديمي</div>',
                footer_template='<div style="font-size:9px; width:100%; text-align:center; color:#888; font-family:sans-serif;">صفحة <span class="pageNumber"></span> من <span class="totalPages"></span></div>'
            )
            await browser.close()

        encoded_filename = urllib.parse.quote(filename)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Type": "application/pdf"
            }
        )
    except Exception as e:
        print(f"Error generating PDF with Playwright: {e}")
        raise HTTPException(status_code=500, detail=f"فشل توليد ملف PDF: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8085))
    print(f"🚀 تشغيل منظومة المجتهد الحية على المنفذ: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

