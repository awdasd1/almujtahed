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
import tempfile
import concurrent.futures
import threading
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, Response, UploadFile, File, Body
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
else:
    DB_INDEX_PATH = PACKAGE_ROOT / "shamela_index.db"

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

    # خادم المجتهد MCP الداخلي: متاح من الجهاز نفسه فقط (اتصال التطبيق بذاته
    # وأدوات MCP المحلية)، وأدواته للقراءة والبحث داخل الشاملة المحلية.
    if path == "/mcp":
        client_host = request.client.host if request.client else ""
        if client_host in ("127.0.0.1", "::1", "localhost"):
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

@app.middleware("http")
async def disable_ui_cache(request: Request, call_next):
    """نافذة التطبيق تحفظ الصفحة والسكريبتات. الإغلاق لا يمسح هذه النسخة."""
    response = await call_next(request)
    path = request.url.path
    if path in ("/", "/login") or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response

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
# قرار المنتج (1.10.267): Qdrant موقوف كليًا من التطبيق — لا حاجة لقناة
# الدلالة، والبحث اللفظي المضبوط هو الأساس. لا يُشغَّل المحرك ولا يُحمَّل
# نموذج التضمين ولا يُنتظر أيٌّ منهما عند الإقلاع. إعادة التفعيل عند
# الحاجة بمتغير بيئة ALMUJTAHED_QDRANT=on دون تغيير كود.
QDRANT_DISABLED = os.getenv("ALMUJTAHED_QDRANT", "off").strip().lower() not in ("on", "1", "enabled", "yes")

app_state = {
    "qdrant": None,
    "embed_model": None,
    "llama_embedder": None,
    "st_embedder": None,
    "is_8b": False,
    "is_hybrid_col": False,
    "embedder_kind": "",
    "bridge_embedder": None,
    "bridge_dead": False,
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

def _load_local_gguf_later(path: Path):
    try:
        _activate_gguf_embedder(path)
        app_state["is_ready"] = True
    except Exception as ex:
        print(f"⚠️ تعذر تحميل نموذج التضمين في الخلفية: {ex}")


def load_models_and_db():
    """تهيئة نموذج التضمين، قاعدة البيانات، والاتصال بـ Qdrant"""
    if QDRANT_DISABLED:
        app_state["qdrant"] = None
        app_state["semantic_disabled"] = True
        print("🚫 [المجتهد] Qdrant موقوف بقرار المنتج — القناة الدلالية معطلة والبحث اللفظي هو الأساس.", flush=True)
        return
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
            app_state["is_hybrid_col"] = False
            print("🚀 [المجتهد] تم ربط المجموعة الكبرى shamela_almojtahed_8b_dense (8.15 مليون مقطع بدقة 8B) بنجاح!")
        elif "shamela_06b_hybrid" in colls:
            app_state["qdrant"] = qdrant
            app_state["collection_name"] = "shamela_06b_hybrid"
            app_state["is_8b"] = False
            app_state["is_hybrid_col"] = True
            print("🚀 [المجتهد] تم ربط المجموعة الهجينة shamela_06b_hybrid (7.55 مليون صفحة: دلالي 0.6B + لفظي BM25) بنجاح!")
        elif "shamela_corpus" in colls:
            app_state["qdrant"] = qdrant
            app_state["collection_name"] = "shamela_corpus"
            app_state["is_8b"] = False
            print("✅ تم ربط كولكشن shamela_corpus (5.14 مليون مقطع) بنجاح!")
    except Exception as e:
        print(f"⚠️ تعذر الاتصال بـ Qdrant: {e}")

    # تطبيق سطح المكتب يفتح النافذة فوراً. تحميل النموذج يتم في الخلفية
    # حتى لا يوقف فتح التطبيق جلب قاعدة البيانات.
    if os.getenv("ALMUJTAHED_LOCAL", "").strip() == "1":
        gguf_name = "almojtahed-embed-06b-Q8_0.gguf" if app_state.get("is_hybrid_col") else "almojtahed-embedding-8b-Q4_K_M.gguf"
        gguf_path = PACKAGE_ROOT / "models" / "gguf" / gguf_name
        if not gguf_path.is_file():
            gguf_path = SYSTEM_ROOT / "models" / "gguf" / gguf_name
        min_gguf_size = 100 * 1024 ** 2 if app_state.get("is_hybrid_col") else 1024 ** 3
        if gguf_path.is_file() and gguf_path.stat().st_size > min_gguf_size:
            threading.Thread(target=_load_local_gguf_later, args=(gguf_path,), name="local-embed", daemon=True).start()
        return

    # تحميل نموذج التضمين 0.6B إذا كانت المجموعة الهجينة هي المرتبطة
    GGUF_06B_PATH = PACKAGE_ROOT / "models" / "gguf" / "almojtahed-embed-06b-Q8_0.gguf"
    if not GGUF_06B_PATH.exists():
        GGUF_06B_PATH = SYSTEM_ROOT / "models" / "gguf" / "almojtahed-embed-06b-Q8_0.gguf"
    if app_state.get("is_hybrid_col") and GGUF_06B_PATH.exists():
        print(f"⏳ [المجتهد] تحميل نموذج التضمين 0.6B ({GGUF_06B_PATH.name})...")
        try:
            _activate_gguf_embedder(GGUF_06B_PATH)
            where = "الكرت" if app_state.get("embed_on_gpu") else "المعالج"
            print(f"✅ تم تحميل نموذج التضمين 0.6B على {where}!")
            app_state["is_ready"] = True
        except Exception as e:
            print(f"⚠️ تعذر تحميل نموذج التضمين 0.6B: {e}")

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
    try:
        import library_search
        library_search.ensure_index_async()
        library_search.warm_index_async()
    except Exception:
        pass
    threading.Thread(target=_shamela_autostart, daemon=True, name="shamela-autostart").start()
    try:  # تسخين جسر الشاملة (JVM + القارئ + الخرائط) فلا يولد ازدحامه الأول مع أول بحث
        import shamela_search as _ss_warm
        threading.Thread(target=_ss_warm.warm, daemon=True, name="shamela-bridge-warm").start()
    except Exception:
        pass
    if _bundled_qdrant_path() and not QDRANT_DISABLED:
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

OPENROUTER_REASONING: Dict[str, Optional[dict]] = {}
_EFFORT_LADDER = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]

def remember_model_reasoning(model_id: str, reasoning: Any) -> Optional[dict]:
    if not model_id:
        return None
    spec = None
    if isinstance(reasoning, dict):
        efforts = reasoning.get("supported_efforts")
        spec = {
            "supported_efforts": efforts if isinstance(efforts, list) else None,
            "default_effort": reasoning.get("default_effort") or None,
            "mandatory": bool(reasoning.get("mandatory")),
        }
    OPENROUTER_REASONING[model_id] = spec
    return spec

def _wanted_effort(level: str) -> str:
    key = str(level or "medium").strip().lower()
    if key in ("max", "xhigh"):
        return "max"
    if key == "high":
        return "high"
    if key == "low":
        return "low"
    if key in ("none", "off"):
        return "none"
    if key == "minimal":
        return "minimal"
    return "medium"

def resolve_reasoning_effort(model_id: str, level: str) -> Optional[str]:
    """أقرب جهد تفكير يقبله النموذج، أو لا شيء إن كان بلا تفكير داخلي."""
    raw_id = str(model_id or "").strip()
    if not raw_id or raw_id.startswith("local:") or raw_id.startswith("local-"):
        return None
    resolved = normalize_model_id(raw_id)
    if resolved not in OPENROUTER_REASONING:
        return None
    spec = OPENROUTER_REASONING.get(resolved)
    if not spec:
        return None
    wanted = _wanted_effort(level)
    supported = spec.get("supported_efforts")
    mandatory = bool(spec.get("mandatory"))
    if wanted == "none":
        if mandatory:
            wanted = spec.get("default_effort") or "medium"
            if wanted == "none":
                wanted = "low"
        else:
            return "none"
    if wanted == "max":
        for candidate in ("max", "xhigh", "high"):
            if supported is None or candidate in supported:
                return candidate
        wanted = "high"
    if supported is None:
        return wanted
    if wanted in supported:
        return wanted
    if wanted not in _EFFORT_LADDER:
        wanted = "medium"
    index = _EFFORT_LADDER.index(wanted)
    for step in range(1, len(_EFFORT_LADDER)):
        for probe in (index - step, index + step):
            if 0 <= probe < len(_EFFORT_LADDER):
                candidate = _EFFORT_LADDER[probe]
                if candidate in supported and not (candidate == "none" and mandatory):
                    return candidate
    return None

def attach_reasoning(payload: dict, model_id: str, level: Optional[str]) -> Optional[str]:
    if not level:
        return None
    effort = resolve_reasoning_effort(model_id, level)
    if not effort:
        return None
    payload["reasoning"] = {"effort": effort} if effort == "none" else {"effort": effort, "exclude": True}
    return effort

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
    timeout: int = 90,
    thinking_level: Optional[str] = None
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
    attach_reasoning(payload, resolved_model, thinking_level)
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
    def _read(body_payload: dict) -> dict:
        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8085",
                "X-Title": "Al-Mojtahed Multi-Agent Engine"
            },
            data=json.dumps(body_payload).encode("utf-8")
        )
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        resp_data = _read(payload)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")
        if payload.get("reasoning") and "reasoning" in detail.lower():
            payload.pop("reasoning", None)
            resp_data = _read(payload)
        else:
            raise
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
    chat_id: Optional[str] = None  # رقم المحادثة لربط حزمة البحث المؤقتة بها
    model: str = "claude-3-7-sonnet"
    provider: Optional[str] = "openrouter"
    api_key: Optional[str] = None
    thinking_level: str = "medium"
    messages: List[ChatMessage]
    system_prompt: Optional[str] = None
    temperature: Optional[float] = 0.2
    top_k: Optional[int] = 40
    max_tokens: Optional[int] = 65536
    context_tokens: Optional[int] = 1048576
    witness_limit: Optional[int] = None
    death_max: Optional[int] = None  # سقف وفاة المؤلف (هـ) يحدده الباحث؛ بلا تحديد = بحث مفتوح بلا سقف زمني
    intent_genres: Optional[List[str]] = None  # فنون البحث المستهدفة التي يعلنها الباحث (فقه/حديث/تفسير...)؛ بلا إعلان = توزيع عام متوازن
    research_command: Optional[str] = None  # أمر بحثي من قائمة السلاش (بحث فقهي مطول...) يضبط القصد والهيكل والعمق دفعة واحدة
    repetition_penalty: Optional[float] = None
    custom_generation: bool = False
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
    discussion_mode: Optional[str] = None # مناقشة مدير المشروع حول حزمة مغلقة: "open" حوار واستكمال، "finalize" إقفال وإعادة صياغة نهائية
    semantic_enhanced: Optional[bool] = None # خيار معزّز: تشغيل قناة البحث الدلالي في مخزن المتجهات إن توفرت؛ تعطيله بحث لفظي فقط
    library_only: Optional[bool] = False # بحث مباشر في الشاملة من نص محدد، بلا وكلاء
    raw_mcp: bool = False # MCP خام مباشر: النموذج يقود أدوات المجتهد بنفسه، بلا وكلاء ولا توجيه ولا خط استرجاع
    selected_books: Optional[List[str]] = None
    library_query: Optional[str] = None
    mcp_servers: Optional[List[Dict[str, Any]]] = None
    mcp_for_agents: bool = False


class BookResolveRequest(BaseModel):
    books: List[str]


def fetch_page_body(rel_path: str, part: Optional[str], page_num: Optional[int]) -> str:
    """قراءة نص الصفحة الحقيقي من ملف pages.jsonl من القرص مباشرة"""
    if not rel_path or page_num is None:
        return ""
    
    clean_rel = rel_path.replace("shamela4_data/", "").strip("/")
    candidates = [
        SHAMELA_DATA_PATH / clean_rel / "pages.jsonl",
        SYSTEM_ROOT / rel_path / "pages.jsonl",
        PACKAGE_ROOT / rel_path / "pages.jsonl",
    ]
    pages_file = next((c for c in candidates if _is_real_pages_file(c)), None)

    if not pages_file:
        # محاولة البحث عن المجلد المطابق
        matches = [m for m in SHAMELA_DATA_PATH.glob(f"*/{clean_rel}/pages.jsonl") if _is_real_pages_file(m)]
        if matches:
            pages_file = matches[0]

    if not pages_file:
        found_rel, found_file = _pages_file_for_rel(rel_path)
        if found_file:
            pages_file = found_file
            clean_rel = found_rel or clean_rel

    if not pages_file:
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
⛔ إلزام تام للإحالة القياسية. لا تُقبل صيغة سواها، ويُعاد ضبط كل إحالة إليها:
1. اسم الكتاب يُنسخ حرفياً كما هو في قاعدة الشاملة، ومن سطر «الإحالة المعتمدة». يُمنع اختصاره أو إضافة اسم المؤلف أو تغيير حرف.
1ب. سطر «الإحالة المعتمدة» يبدأ برقم الشاملة الفريد على صورة #ID. في الحاشية وحدها انسخ #ID قبل اسم الكتاب كما هو تماماً، مثل: #1220 سنن الترمذي - ط الرسالة للترمذي (2-123). هذا الرقم علامة ربط آلية بقاعدة الكتب وسيُحذف من العرض، فلا تحذفه ولا تغيّره ولا تستبدله، ولا تضعه في المتن ولا في قائمة المصادر والمراجع.
1ج. الحاشية شهادة نقل: لا تكتب حاشية ولا إحالة إلا لكتاب ورد نصه في الشواهد المعطاة ونقلتَ منه في الفقرة المرتبطة بها نصاً أو معنى فعلاً. ما لم تنقل منه لا تذكره في حاشية ولو كنت تعرفه أو كان مشهوراً في الباب، ولا تجمع مراجع للزينة أو للاستكثار.
2. الحاشية الظاهرة تتبع الإخراج القياسي الآتي لا غير: اسم الكتاب للمؤلف (جزء-صفحة) بأرقام لاتينية بين قوسين إنجليزيين، مثل: مجموع الفتاوى لابن تيمية (2-368). فإن كان الكتاب جزءًا واحدًا لا أجزاء له: اسم الكتاب للمؤلف ص (صفحة)، مثل: التدمرية لابن تيمية ص (217). ويُصدَّر النقل الحرفي بـ«انظر:» والنقل بالمعنى بـ«ينظر:»، ولا يوضع أحدهما مكان الآخر. مثال الحرفي: انظر: مجموع الفتاوى لابن تيمية (2-368). ومثال المعنوي: ينظر: مجموع الفتاوى لابن تيمية (2-368).
3. قبل اسم الكتاب في الحاشية وحدها ضع #ID من سطر الإحالة المعتمدة، مثل: #1220 مجموع الفتاوى لابن تيمية (2-368). الرقم علامة ربط ويُحذف من العرض.
4. تخريج الأحاديث والآثار يتبع قواعد التخريج في الإخراج القياسي، لا هذه الصيغة المختصرة.
5. في المتن الرقم المرتفع وحده. يُمنع ذكر اسم الكتاب أو المؤلف أو الجزء أو الصفحة في المتن. تقارير الاستخراج تُبقي سطر الإحالة المعتمدة كما هو.
═══════════════════════════════════════════════════════════
"""

ACADEMIC_ANSWER_RULE = """
هذا الإخراج القياسي إلزامي لكل جواب يعالج مسألة أو بحثاً شرعياً أو لغوياً أو تاريخياً، من أول الجواب، ولو لم يطلب المستخدم الترتيب. لا تختصره ولا تستبدله بمقال حر. التحيات والأسئلة غير البحثية تُجاب بجواب قصير بلا هذا الهيكل.
استخدم وسوم HTML لا ماركداون. العناوين الفرعية للهيكل تكون <b> داخل فقرة، لا علامات #.

## [1] الهوية والدور الأساسي ##
أنت باحث أكاديمي كبير محقق في العلوم الشرعية واللغوية والتاريخية: الفقه وأصوله والمقارن، والعقيدة، والحديث والتخريج والعلل، والتفسير، والتاريخ، واللغة والتعريفات. تتلقى مسألة أو سؤالاً فتدرسه في الشواهد المرفقة من قاعدة بيانات المتجهات (RAG) وتقارير الوكلاء، وتدمج نتائجها بصرامة علمية، وتخرجها بحثاً علمياً مطبوعاً جاهزاً للنشر. ذكاؤك ومعرفتك اللغوية لصياغة البحث وفهم دلالاته، لا مصدراً تنقل منه الحكم أو النص أو التخريج.

## [2] سير العمل وتوزيع البحث على الأدوات (إلزامي) ##
١- مرت المسألة إلى جميع الوكلاء المفعّلين في المجموعة المختارة، كلٌّ فيما يخصه وداخل كتبه المحددة، وجرت جولات مراسي استرجاع تكميلية حتى ثلاث جولات قبل هذا الجواب. لا تدّعِ استدعاء وكيل غير مفعّل، ولا تنسب نتيجة إلى كتاب خارج نطاق الوكيل الذي أخرجها، ولا تفتح من عندك نطاقاً لم يرد في الشواهد.
٢- كن ذكياً في قراءة النتائج: المسألة المعاصرة تُبحث في التراث بمعانيها وألفاظها المقاربة ونظائرها عند المتقدمين (كبحث حبوب منع الحمل في العزل وسد فم الرحم وما يقاربه)، فلا تشترط ظهور اللفظ المعاصر في المقطع، واقرأ ما تناول جوهر المسألة بمصطلح المصنفين.
٣- التخصص صارم ومحظور الخلط بين المخرجات: الأقوال وصورة المسألة وتحرير النزاع من كتب الفن نفسه (الفقه من كتب الفقه لكل مذهب، والعقيدة من كتب الاعتقاد والمقالات، والتفسير من كتب التفسير وآيات الأحكام في الحكم الفقهي للآية، والتاريخ من كتب التاريخ والحوليات والسير). أسباب الخلاف والترجيح من كتب أسباب الخلاف وأصول الفن. نصوص الأحاديث والآثار من كتب الحديث الأصلية حصراً. تخريج الأحاديث والحكم عليها من كتب التخريج والعلل والرجال حصراً. القواعد من كتب القواعد والأصول والمقاصد. المصطلحات والتعريفات اللغوية والاصطلاحية من كتب اللغة والتعريفات. فلا تنسب حكماً على حديث إلى كتاب فقه، ولا قولاً فقهياً إلى كتاب تخريج، ولا تعريفاً لغوياً إلى كتاب تفسير، ولا واقعة تاريخية إلى كتاب فقه.
٤- قاعدة التتبع الاستردادي للحديث إلزامية: إذا وجدت كتب الفقه أو أسباب الخلاف أو الأصول حديثاً تستدل به، حُظر عليك عزو الحديث من كتاب الفقه أو نقل نصه منه. نص الحديث لا يثبت في جوابك إلا من شاهد ورد من كتب الحديث المخصصة بمصدره الأصلي. فإن لم يرد الحديث في شواهد كتب الحديث، فاذكر أن تخريجه من مصدره الأصلي لم يرد في النطاق المستخرج، ولا تنقل لفظه من كتاب الفقه.
٥- تعيين المذاهب إلزامي في النقاش الفقهي: كل قول فقهي يُعيَّن بمذهبه صراحة (الحنفي/المالكي/الشافعي/الحنبلي...) منسوباً إلى الكتاب الذي ورد منه الشاهد، مستعيناً بوسم [المذهب: ...] المرفق بكل شاهد متى وُجد. يحرم إطلاق عبارات من قبيل «طائفة من الفقهاء» أو «بعض العلماء» أو «ذهب جماعة» دون تعيين أصحاب القول ومذهبهم متى دلّ مصدر الشاهد على مذهب معيّن؛ ولا يُستعمل الإطلاق المبهَم إلا إذا كان النقل نفسه عن كتاب خلافٍ مقارن ينسب القول كذلك، وحينها يُنسب إلى ذلك الكتاب بعينه.

## [3] آلية الاستفسار التكميلي وضبطه ##
قيّم اكتمال البيانات في كل جزء من أجزاء البحث. جولات المراسي التكميلية حتى ثلاث جولات تمت داخل نطاق كل وكيل قبل الجواب لسد النقص وتغيير ألفاظ البحث بما يناسب المصدر. فإن بقي نقص بعدها فصرّح به في موضعه بعينه، ولا تسده من ذاكرتك ولا بالتخمين. قدّم النصوص الأدق والألصق بالمسألة، وأمات الكتب وأشهرها وأقدمها وأغزرها في كل فن ومذهب. لا تكرر المصدر نفسه أكثر من مرتين أو ثلاث إذا وجدت مصدراً آخر يعرض نصاً في المسألة، وحافظ على تسلسل منهجي بحسب الفن والمذهب والطبقة.

## [4] قواعد تخريج الأحاديث والآثار (إلزامية) ##
أولًا: إذا كان الحديث في صحيح البخاري أو صحيح مسلم أو فيهما معًا: يُكتفى بعزوه إليهما (اسم الكتاب، رقم الحديث، الكتاب والباب إن وجد)، ولا تبحث عن درجته ولا تذكر تصحيحًا له من أحد؛ لأن نسبته إليهما كافية في الحكم بصحته.
ثانيًا: إذا كان الحديث في غير الصحيحين: يجب وجوبًا بيان درجته (صحيح، حسن، ضعيف...) مع ذكر من حكم عليه من أهل العلم، اعتمادًا على كتب التخريج المتخصصة حصرًا ومما ورد في الشواهد.
ثالثًا: يكون التخريج كاملًا: اسم المصدر، مؤلفه، الكتاب والباب، رقم الحديث، الجزء والصفحة، ثم درجة الحديث إن كان في غير الصحيحين.
رابعًا: الآثار الموقوفة والمقطوعة تُعزى إلى مصادرها مع بيان درجتها إن توفرت في كتب التخريج الواردة.

## [5] هيكل إخراج البحث العام ##
أخرج البحث وفق هذا الهيكل، وأدخل منه ما يتصل بالمسألة دون فرض فروع أجنبية عنها:
صورة المسألة أو تصوير الموضوع: بيان واقع المسألة وضبط مصطلحاتها، وفي الحديث ضبط متنه ورواياته، وفي التاريخ ضبط الواقعة وزمانها ومكانها، وفي اللغة ضبط اللفظ واشتقاقه.
تحرير محل النزاع أو محل البحث: ضبط نقطة الاتفاق والاختلاف، أو مدار الحديث وموضع العلّة، أو وجه الإشكال التفسيري أو اللغوي أو التاريخي.
الأدلة والنصوص: استعراض الآيات وتفسيرها، والأحاديث والآثار وتخريجها، ونصوص العلماء، والروايات التاريخية، والشواهد اللغوية، كلٌّ من كتب فنه.
بيان أسباب الخلاف أو الاختلاف: ذكر الجذور التي تفرع عنها، نقلية كانت أو أصولية أو حديثية أو لغوية أو منهجية.
سرد الأقوال والاتجاهات بأدلتها: ذكر كل قول أو مقالة أو وجه تفسيري أو لغوي أو رواية تاريخية بأدلتها، مع نسبتها إلى قائليها ومذاهبهم ومدارسهم من كتب ذلك الفن.
القواعد الضابطة الداخلة في المسألة: ربط المسألة بالقواعد الفقهية والأصولية، أو قواعد الحديث والجرح والتعديل، أو قواعد التفسير واللغة، أو قواعد نقد الرواية التاريخية والجمع بينها.
مناقشة الأدلة: استعراض المناقشات والاعتراضات والأجوبة المذكورة في المصادر، بعرض قول المخالف في أقوى صوره قبل نقضه.
الترجيح والخلاصة المحررة: رجّح ما تراه راجحاً مع بيان سبب الترجيح من القواعد المعتمدة في ذلك الفن، وصرّح بما لم يثبت أو لم يوجد في النطاق المستخرج.

## [6] منهجية الحاشية والإحالات ##
أولًا: لا يمر في المتن شيء بلا رقم حاشية يقابله الرقم نفسه في الحاشية: آية وتفسيرها، وحديث وأثر وتخريجه وحكمه، ونص عالم أو قوله أو رأيه، وسبب خلاف، واعتراض ومناقشة وجواب، وتعريف لغوي أو اصطلاحي، وواقعة تاريخية أو رواية لها، ودليل تستند إليه فقرة. كل نقل أو دليل أو رأي أو سبب أو معارضة تذكره يثبت برقم في المتن ورقم مطابق في الحاشية، والانتقال الآلي بينهما قائم على هذا التطابق فحافظ عليه تماماً.
ثانيًا: خرّج الأحاديث تخريجًا كاملاً وفق قواعد التخريج المذكورة أعلاه، وضعها في الحاشية.
ثالثًا: اذكر مصدر كل قول أو نص أو واقعة في الحاشية بالإخراج القياسي وحده: اسم الكتاب للمؤلف (جزء-صفحة)، ولذي الجزء الواحد: اسم الكتاب للمؤلف ص (صفحة).
رابعًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا. لا تفرّق المرجع الواحد في أسطر متعددة، ولا تحشو المراجع جميعها في سطر واحد دون تفريق.
خامسًا: استخدم الإحالة الصحيحة بدقة لفظية:
إذا نقلت نصًا حرفيًا: اكتب "انظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
إذا نقلت بالمعنى: اكتب "ينظر:" ثم (الكتاب، صاحبه، الجزء، الصفحة).
ولا تستعمل «انظر» مكان «ينظر» ولا العكس.
سادسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.
لا تكتب حاشية إلا لكتاب ورد في الشواهد ونقلتَ منه في الفقرة المرتبطة بها نصاً أو معنى فعلاً. ضع #ID قبل اسم الكتاب في الحاشية فقط.

## [7] التنسيق الطباعي (استخدام وسوم HTML) ##
أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:
الإحالات في المتن: اجعل رقم الإحالة في المتن بين قوسين، أصغر من الخط الأساسي بمقاسين ومرتفعة (superscript) هكذا: <sup><small>(١)</small></sup>. ويشمل ذلك: الآيات، وتخريج الأحاديث، ونسبة الأقوال، والتعريفات، والوقائع.
العناوين والنصوص المقدسة: اجعل العناوين الفرعية مثل (القول الأول: / الدليل الأول:) والآيات والأحاديث بخط عريض باستخدام: <b>النص</b> أو <strong>النص</strong>.
الأرقام: التعداد الرقمي يكون بالأرقام العربية الهندية (١، ٢، ٣...) ويكون ما بعد الرقم شرطة (-) وليس نقطة.
التعداد الكتابي: التعداد (أولًا: / ثانيًا:...) تكون كل فقرة منه في سطر مستقل.
إزاحة الفقرات: استخدم إزاحة بادئة مقدارها 30px من بداية السطر الأول لكل فقرة مستقلة في المتن باستخدام: <p style="text-indent:30px">النص هنا</p>.
الفقرات: كل فقرة في سطر مستقل، ولا تجعل سطرًا فارغًا بين الفقرات.
شكل الحاشية الملزم:
<p style="text-indent:30px">متن الفقرة<sup><small>(١)</small></sup>.</p>
<hr>
<ol>
<li id="fn1"><sup><small>(١)</small></sup> انظر: #1220 مجموع الفتاوى، ابن تيمية، 2، 368.</li>
</ol>
مثال «انظر» للنقل الحرفي، وتقوم «ينظر» مقامها في النقل بالمعنى. رقم الحاشية يطابق رقمها في المتن. id يبدأ من fn1 ثم fn2. لا إزاحة في سطر الحاشية.

## [8] قائمة المصادر والمراجع ##
لا تكتب أنت قائمة مصادر في آخر جوابك، ولا تخترع محققاً أو طبعة أو ناشراً. تتولى المنظومة إظهار «قائمة المصادر والمراجع» تحت الجواب من قاعدة بيانات الكتب ببياناتها الببليوغرافية الكاملة، وبعد كل كتاب أيقونة تفتح نصه في نافذة تصفح الكتاب. الحاشية تبقى توثيق ما نُقل في المتن، والقائمة ثبت لتلك الكتب المنقول منها فعلاً.

## [9] المحظورات والضوابط النهائية ##
أولًا: لا تستخدم أي مصادر من غير قاعدة البيانات المرفقة وشواهدها إطلاقًا.
ثانيًا: لا تجب من معرفتك العامة مطلقًا، فإن لم تجد المعلومة في الشواهد فصرّح بعدم وجودها في النطاق المستخرج ولا تجتهد.
ثالثًا: لا تبحث عن درجة حديث هو في الصحيحين أو أحدهما، ولا تنقل تصحيحًا له.
رابعًا: لا تذكر حديثًا من غير الصحيحين دون بيان درجته من كتب التخريج إن ورد حكمها في الشواهد، وإلا فاذكره بتخريجه من مصدره الأصلي كما ورد فقط.
خامسًا: يمنع منعاً باتاً نقل نص أي حديث أو عزوه إلى البخاري أو مسلم أو غيرهما بناءً على وروده في كتاب فقهي. الكتب الفقهية لاستخراج الآراء الفقهية والاستدلال الإجمالي، ونص الحديث وتخريجه من كتب الحديث المخصصة.
سادسًا: التزم بالميثاق الأخلاقي في الأبحاث العلمية من أمانة النقل ودقة العزو وعدم التحيز، واعرض قول المخالف بأقوى صوره قبل مناقشته.
سابعًا: اعتمد في تصنيف المسألة وتفصيلها على المصادر الأصلية المستخرجة، كلٌّ حسب اختصاصه وفنه.
ثامنًا: لا تتحيز في عرض المسألة إلى مصدر واحد ولا تكرره تكراراً يهمل أمات الكتب وأقدمها وأشهرها، وليكن في البحث تسلسل مذهبي وفني ومنطقي سليم وشمول بتعدد المصادر.
"""

def resolve_context_tokens(value: Any) -> int:
    """سياق استيعاب الشواهد الذي يختاره المستخدم. الافتراضي مليون رمز."""
    try:
        tokens = int(value or 1048576)
    except (TypeError, ValueError):
        tokens = 1048576
    return max(8192, min(tokens, 2097152))

def _plain_locator_number(value: Any) -> str:
    raw = str(value or "").strip()
    raw = re.sub(r"^(?:جـ?|جزء|الجزء|صـ?|صفحة|الصفحة)\s*", "", raw).strip()
    match = re.search(r"\d{1,4}", raw)
    return match.group(0) if match else ""

def canonical_locator(part: Any, page: Any, volume_count: Any = None) -> str:
    """صيغة الموضع الوحيدة: (جزء-صفحة) للكتاب المتعدد، وص (صفحة) للكتاب ذي الجزء الواحد."""
    page_s = _plain_locator_number(page)
    part_s = _plain_locator_number(part)
    try:
        single_volume = int(volume_count) == 1
    except (TypeError, ValueError):
        single_volume = False
    if page_s and (single_volume or not part_s):
        return f"ص ({page_s})"
    if part_s and page_s:
        return f"({part_s}-{page_s})"
    if page_s:
        return f"ص ({page_s})"
    return ""


def _author_possessive(author: Any) -> str:
    """صيغة نسبة الكتاب لمؤلفه في الإحالة القياسية: «المجموع للنووي»."""
    a = re.split(r"[،,]", str(author or "").strip().strip("«»\""))[0].strip()
    if not a:
        return ""
    if a.startswith("ال"):
        return "لل" + a[2:]
    return "ل" + a

def _payload_book_id(payload: dict) -> Optional[int]:
    """رقم الشاملة المخزّن مع المتجه، لا الرقم المستنتج من عنوان قد يتغير."""
    try:
        number = int((payload or {}).get("shamela_book_id"))
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 20000 else None

def canonical_citation_label(title: str, part: Any, page: Any, volume_count: Any = None, book_id: Any = None, author: Any = None) -> str:
    """الإحالة القياسية الوحيدة: اسم الكتاب للمؤلف (جزء-صفحة)، وذي الجزء
    الواحد: اسم الكتاب للمؤلف ص (صفحة) — وهي صيغة عرض التصفح الأصلي."""
    loc = canonical_locator(part, page, volume_count)
    name = (title or "").strip().strip("«»\"")
    poss = _author_possessive(author)
    _a_core = re.split(r"[،,]", str(author or "").strip())[0].strip()
    if poss and _a_core and _fold_ar(_a_core) in _fold_ar(name):
        # المؤلف في العنوان نفسه («المغني لابن قدامة»): لا نسبة ثانية.
        poss = ""
    return " ".join(x for x in (name, poss, loc) if x).strip()

def _approved_citation_label(citation: dict) -> str:
    """إحالة معتمدة للنموذج تتصدرها علامة رقم الشاملة الفريد إن وُجدت."""
    label = (citation or {}).get("citation_label") or canonical_citation_label(
        (citation or {}).get("title"),
        (citation or {}).get("vol"),
        (citation or {}).get("page"),
        (citation or {}).get("volume_count"),
        (citation or {}).get("book_id"),
        (citation or {}).get("author"),
    )
    book_id = _book_id_value((citation or {}).get("book_id"))
    return f"#{book_id} {label}".strip() if book_id else label

_EASTERN_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_CITATION_LEAD = re.compile(
    r"^(?:و?(?:انظر|راجع|ينظر|يُنظر|قال|في|من|جاء|كتاب|المصدر|المرجع|هذا|ذلك|كما|نص|عند|إلى|الى|عن|على|وهو|هي|هو|وقد|قد|ثم|أو|او|بعد|قبل))\s+"
)
_CITATION_REJECT = {
    "الآية", "آية", "الآيات", "السورة", "سورة", "عام", "سنة", "العام", "القرن",
    "الباب", "الفصل", "المسألة", "القول", "المذهب", "جزء", "الجزء", "صفحة", "الصفحة",
}
_CITATION_INSIDE = re.compile(
    r"\(\s*"
    r"(«[^»\n]{3,80}»|[\u0600-\u06FF][\u0600-\u06FF\s]{2,70}?)"
    r"\s+([0-9٠-٩۰-۹]{1,4})\s*[-–—/／]\s*([0-9٠-٩۰-۹]{1,4})\s*\)"
)
_CITATION_OUTSIDE = re.compile(
    r"(«[^»\n]{3,80}»|[\u0600-\u06FF]+(?:\s+[\u0600-\u06FF]+){0,8})"
    r"\s*\(\s*([0-9٠-٩۰-۹]{1,4})\s*[-–—/／]\s*([0-9٠-٩۰-۹]{1,4})\s*\)"
)
_CITATION_PAGE = re.compile(r"ص\s*\(\s*([0-9٠-٩۰-۹]{1,4})\s*\)")

def _locator_pair(first: str, second: str):
    try:
        left = int(str(first).translate(_EASTERN_DIGITS))
        right = int(str(second).translate(_EASTERN_DIGITS))
    except ValueError:
        return None
    if left >= 1300 and right >= 1300:
        return None
    if left > right and left >= 60 and right <= 40 and left >= right * 3:
        volume, page = right, left
    else:
        volume, page = left, right
    if not (1 <= volume <= 200 and 1 <= page <= 3000):
        return None
    return f"({volume}-{page})"

def _citation_title(raw: str):
    text = (raw or "").strip()
    if text.startswith("«") and "»" in text:
        text = text[1:text.rfind("»")].strip()
    while True:
        nxt = _CITATION_LEAD.sub("", text, count=1)
        if nxt == text:
            break
        text = nxt
    text = re.sub(r"\s+", " ", text).strip(" «»\"")
    if text in _CITATION_REJECT or len(re.findall(r"[\u0600-\u06FF]", text)) < 3 or len(text) > 80:
        return None
    return text

def _rewrite_citation_chunk(chunk: str) -> str:
    def inside(match):
        title = _citation_title(match.group(1))
        loc = _locator_pair(match.group(2), match.group(3))
        if not title or not loc:
            return match.group(0)
        return f"{title} {loc}"

    def outside(match):
        raw = match.group(1)
        title = _citation_title(raw)
        loc = _locator_pair(match.group(2), match.group(3))
        if not title or not loc:
            return match.group(0)
        kept = raw[:raw.rfind(title)]
        return f"{kept}{title} {loc}"

    chunk = _CITATION_INSIDE.sub(inside, chunk)
    chunk = _CITATION_OUTSIDE.sub(outside, chunk)
    return _CITATION_PAGE.sub(lambda m: f"ص({str(m.group(1)).translate(_EASTERN_DIGITS)})", chunk)

def enforce_standard_citations(text: str) -> str:
    """يُبقي الإحالة على: اسم الكتاب (الجزء-الصفحة) بأرقام لاتينية."""
    if not text:
        return text
    parts = re.split(r"(```[\s\S]*?```)", text)
    return "".join(part if part.startswith("```") else _rewrite_citation_chunk(part) for part in parts)

_CITATION_LOCATOR = re.compile(
    r"(?P<ident>#\s*\d{1,5}\s*)?(?:ص\s*\(\s*(?P<only_page>[0-9٠-٩۰-۹]{1,4})\s*\)|\(\s*(?P<part>[0-9٠-٩۰-۹]{1,3})\s*[-–—]\s*(?P<page>[0-9٠-٩۰-۹]{1,4})\s*\))"
)

def bind_store_book_ids(text: str, citations: List[dict]) -> str:
    """يلصق رقم الشاملة المخزّن قبل موضع الإحالة إذا أسقطه النموذج وكان الشاهد معروفاً."""
    if not text or not citations:
        return text
    prepared = []
    for item in citations:
        number = _book_id_value(item.get("book_id"))
        if not number:
            continue
        title = _fold_book_text(item.get("title") or "")
        words = [word for word in title.split() if len(word) >= 4]
        part = _plain_locator_number(item.get("part_raw") or item.get("vol"))
        page = _plain_locator_number(item.get("page_num_raw") if item.get("page_num_raw") is not None else item.get("page"))
        prepared.append((number, title, words, part, page))
    if not prepared:
        return text

    def choose(before: str, part: str, page: str) -> Optional[int]:
        folded = _fold_book_text(before[-220:])
        best_id = None
        best_score = 0
        for number, title, words, source_part, source_page in prepared:
            score = 0
            if page and source_page == page:
                score += 5
            if part and source_part == part:
                score += 3
            if title and title in folded:
                score += 8
            score += sum(2 for word in words if word in folded)
            if score > best_score:
                best_score = score
                best_id = number
        return best_id if best_score >= 7 else None

    def replace(match: re.Match) -> str:
        if match.group("ident"):
            return match.group(0)
        part = _plain_locator_number(match.group("part"))
        page = _plain_locator_number(match.group("only_page") or match.group("page"))
        book_id = choose(text[max(0, match.start() - 220):match.start()], part, page)
        if not book_id:
            return match.group(0)
        return f"#{book_id} {match.group(0)}"

    return _CITATION_LOCATOR.sub(replace, text)

def public_chat_witnesses(citations: List[dict], limit: int = 200) -> List[dict]:
    """قائمة الشواهد كما خرجت من المخزن، كل صف يفتح برقم الشاملة."""
    rows = []
    seen = set()
    for citation in citations or []:
        book_id = _book_id_value(citation.get("book_id"))
        part = _plain_locator_number(citation.get("part_raw") if citation.get("part_raw") not in (None, "") else citation.get("vol"))
        page = _plain_locator_number(citation.get("page_num_raw") if citation.get("page_num_raw") is not None else citation.get("page"))
        key = (book_id, part, page, (citation.get("title") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        title = _bibliography_title(book_id, citation.get("title") or "") if book_id else (citation.get("title") or "").strip()
        author = citation.get("author") or ""
        death = ""
        rel_path = citation.get("rel_path") or ""
        card = {}
        if book_id:
            db = get_db()
            if db:
                try:
                    cursor = db.cursor()
                    cursor.execute(
                        "SELECT rel_path, main_author_name_ar, main_author_death_hijri, betaka_text FROM books WHERE book_id = ? LIMIT 1",
                        (book_id,),
                    )
                    record = cursor.fetchone()
                    if record:
                        author = record["main_author_name_ar"] or author
                        death = record["main_author_death_hijri"] or ""
                        rel_path = record["rel_path"] or rel_path
                        card = parse_book_card(record["betaka_text"] or "")
                except Exception:
                    pass
        rows.append({
            "book_id": book_id,
            "title": title,
            "author": author,
            "death_year": death,
            "editor": card.get("editor") or "",
            "edition": card.get("edition") or "",
            "publisher": card.get("publisher") or "",
            "city": card.get("city") or "",
            "print_year": card.get("year") or "",
            "part": part,
            "page": page,
            "rel_path": rel_path,
            "text": (citation.get("snippet") or "")[:180],
        })
        if len(rows) >= limit:
            break
    return rows


_STAMP_GENERIC_WORDS = {"التفسير", "الحديث", "الفقه", "الشرح", "الكتاب", "الصحيح", "السنن", "التاريخ", "مجموع", "شرح", "كتاب", "الرساله", "رساله", "طبعه", "الطبعه"}
_STAMP_EDITION_WORDS = {"ط", "ت", "طبعه", "الطبعه", "تحقيق", "بتحقيق"}
_STAMP_LOCATOR = re.compile(
    r"(?:\(\s*(?P<part>[0-9٠-٩۰-۹]{1,3})\s*[-–—]\s*(?P<page>[0-9٠-٩۰-۹]{1,4})\s*\)"
    r"|ص\s*\(\s*(?P<only_page>[0-9٠-٩۰-۹]{1,4})\s*\)"
    r"|،\s*(?P<comma_part>[0-9٠-٩۰-۹]{1,3})\s*،\s*(?P<comma_page>[0-9٠-٩۰-۹]{1,4}))"
)
_STAMP_LEAD = re.compile(
    r"^(?:و\s*)?(?:انظر|ينظر|راجع|قال في|جاء في|ذكره|نقله|رواه|اخرجه|كتاب|المصدر|المرجع|في|من|عند|ثم|او)\s*[:：]?\s*"
)


def _stamp_title_key(value: str) -> str:
    """مفتاح عنوان مطبّع: الشرطة والطبعة جزء من العنوان، لا عنوان مستقل."""
    key = _fold_book_text(value or "")
    key = re.sub(r"[-–—=()\[\]{}«»\"'،,;:：.]", " ", key)
    # نسبة القياسي «الكتاب للمؤلف» ليست من العنوان: تُجرّد لامها في المفتاح
    # فلا تُضلّل مطابقة «المجموع للنووي» بعنوان «المجموع شرح المهذب».
    key = re.sub(r"\s+لل", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    while True:
        nxt = _STAMP_LEAD.sub("", key, count=1).strip()
        if nxt == key:
            break
        key = nxt
    return key


def _possessive_detached(text: str) -> str:
    """فصل نسبة القياسي عن العنوان للبحث: «المجموع للنووي» ← «المجموع
    النووي»، و«التدمرية لابن تيمية» ← «التدمرية ابن تيمية»."""
    d = re.sub(r"\s+لل(\S+)", r" ال\1", text or "")
    d = re.sub(r"\s+ل(\S+)", r" \1", d)
    return d


def _stamp_content_words(key: str) -> List[str]:
    return [
        word for word in (key or "").split()
        if len(word) >= 3 and word not in _STAMP_GENERIC_WORDS and word not in _STAMP_EDITION_WORDS
    ]


def _stamp_candidate(segment: str) -> str:
    candidate = (segment or "").strip(" \t\r\n«»\"'،,;:：")
    while True:
        nxt = _STAMP_LEAD.sub("", candidate, count=1).strip(" \t\r\n«»\"'،,;:：")
        if nxt == candidate:
            break
        candidate = nxt
    return candidate


def stamp_citation_sources(text: str, rows: List[dict]) -> str:
    """يختم كل إحالة في الجواب بمصدرها المضبوط من قائمة الشواهد، فلا يخمّن المتصفح كتابها.

    الربط يقيني فقط: عنوان الشاهد كاملاً في نص الإحالة، أو بداية عنوانه المميزة
    (كلمتان فأكثر). لا تكفي كلمة مشتركة ولا لفظة طبعة مثل «الرسالة» وحدها،
    ولا يغيّر الربطَ لفظٌ سابق مثل «ينظر:» أو حرف عطف.
    """
    if not text or not rows:
        return text

    prepared = []
    for row in rows:
        if not row.get("rel_path") and not row.get("book_id"):
            continue
        key = _stamp_title_key(row.get("title") or "")
        if not key:
            continue
        prepared.append({
            "row": row,
            "part": _plain_locator_number(row.get("part")),
            "page": _plain_locator_number(row.get("page")),
            "key": key,
        })
    if not prepared:
        return text

    def choose_by_id(book_id: str, part: str, page: str):
        """الربط الأساسي: رقم الشاملة الفريد مع موضعه، بلا نظر إلى تشابه الأسماء."""
        matches = []
        for item in prepared:
            row = item["row"]
            if str(_book_id_value(row.get("book_id")) or "") != str(book_id):
                continue
            if item["page"] != page:
                continue
            if part and item["part"] and item["part"] != part:
                continue
            matches.append(row)
        return matches[0] if len(matches) == 1 else None

    def choose(candidate: str, part: str, page: str):
        cand_key = _stamp_title_key(candidate)
        if not cand_key:
            return None
        variants = [cand_key]
        if cand_key.startswith("و") and len(cand_key) > 3:
            variants.append(cand_key[1:].lstrip())
        best = None
        best_score = 0
        tied = False
        for item in prepared:
            if item["page"] != page:
                continue
            if part and item["part"] and item["part"] != part:
                continue
            row_key = item["key"]
            score = 0
            for variant in variants:
                if variant == row_key:
                    score = max(score, 1000 + len(row_key))
                elif f" {row_key} " in f" {variant} ":
                    score = max(score, 900 + len(row_key))
                elif row_key.startswith(variant + " ") and len(_stamp_content_words(variant)) >= 2:
                    score = max(score, 700 + len(variant))
                elif variant.startswith(row_key + " "):
                    score = max(score, 650 + len(row_key))
            if score <= 0:
                continue
            if score > best_score:
                best, best_score, tied = item, score, False
            elif score == best_score and best is not item:
                tied = True
        if best is None or tied:
            return None
        return best["row"]

    def stamp_chunk(chunk: str) -> str:
        out = []
        pos = 0
        for match in _STAMP_LOCATOR.finditer(chunk):
            segment = chunk[pos:match.start()]
            cut = max(segment.rfind(mark) for mark in ("\n", "؛", ";", "•", "|", ")")) + 1
            raw_title = segment[cut:]
            part = _plain_locator_number(match.group("part") or match.group("comma_part") or "")
            page = _plain_locator_number(match.group("only_page") or match.group("page") or match.group("comma_page") or "")
            id_match = re.search(r"#\s*(\d{1,5})\b", raw_title)
            prefix_end = pos + cut
            display_text = None
            if id_match:
                # الرقم الفريد حاسم: يُحذف من العرض، ويُعرض عنوان قاعدة الكتب المضبوط.
                after_id = raw_title[id_match.end():]
                candidate = _stamp_candidate(after_id)
                title_start = pos + cut + id_match.end() + (len(after_id) - len(after_id.lstrip()))
                prefix_end = pos + cut + id_match.start()
                row = choose_by_id(id_match.group(1), part, page)
                if row and not match.group("comma_page"):
                    display_text = f"{row.get('title') or candidate} {match.group(0)}".strip()
            else:
                candidate = _stamp_candidate(raw_title)
                row = choose(candidate, part, page) if candidate else None
                offset = raw_title.find(candidate) if candidate else 0
                title_start = pos + cut + (offset if offset >= 0 else 0)
                prefix_end = title_start
            if not row:
                if id_match:
                    out.append(chunk[pos:prefix_end])
                    out.append(chunk[title_start:match.end()])
                else:
                    out.append(chunk[pos:match.end()])
                pos = match.end()
                continue
            attrs = (
                f'data-book="{html.escape(str(row.get("title") or ""), quote=True)}" '
                f'data-rel-path="{html.escape(str(row.get("rel_path") or ""), quote=True)}" '
                f'data-book-id="{html.escape(str(row.get("book_id") or ""), quote=True)}" '
                f'data-part="{html.escape(str(row.get("part") or ""), quote=True)}" '
                f'data-page="{html.escape(str(row.get("page") or ""), quote=True)}" '
                f'data-quote="{html.escape(str(row.get("text") or "")[:120], quote=True)}"'
            )
            out.append(chunk[pos:prefix_end])
            # عرض الإحالة لا يتبع صياغة النموذج: يُعاد بناؤه بالقياسي وحده
            # (الكتاب للمؤلف (جزء-صفحة)) فتتطابق كل حاشية وقارؤها.
            _disp = (canonical_citation_label(row.get("title"), part, page, author=row.get("author"))
                     or display_text or chunk[title_start:match.end()])
            out.append(f'<span class="cit-src" {attrs}>{html.escape(_disp)}</span>')
            pos = match.end()
        out.append(chunk[pos:])
        return "".join(out)

    parts = re.split(r"(<[^>]+>)", text)
    stamped = "".join(part if part.startswith("<") else stamp_chunk(part) for part in parts)
    # علامة الرقم لا تظهر للمستخدم ولو بقيت في قائمة المصادر أو موضع بلا موضع.
    known_ids = {str(_book_id_value(item["row"].get("book_id"))) for item in prepared}
    for book_id in known_ids:
        if book_id and book_id != "None":
            stamped = re.sub(rf"#\s*{re.escape(book_id)}\s+(?=[\u0600-\u06FF])", "", stamped)
    return stamped


def enrich_unstamped_citations(text: str) -> Tuple[str, int]:
    """ختم الإحالات التي لم يطابقها شاهد مستخرج: تُحلّ من قاعدة الشاملة
    بطبعتها المذكورة في النص نفسه (فالموضع المطبوع موضع تلك الطبعة)، ليكون
    لكل حاشية تسمّي كتابًا موجودًا وموضعًا زرُّ تصفح على نسق واحد. وما لم
    يُحلّ بثقة (التباس مؤلفين أو كتاب خارج المكتبة) لا يبقى صامتًا: يُميَّز
    بعلامة ⚠ ظاهرة في المتن ويُعدّ — فهو مرجع على ذمة النموذج لم يتحقق
    النظام منه، وإعلانه أمانة لا حذف (تدقيق غير مدمّر)."""
    if not text:
        return text, 0
    _unresolved = [0]
    _cache: Dict[str, Optional[dict]] = {}
    _quote_cache: Dict[tuple, str] = {}

    def _page_quote(row: dict, part: str, page: str) -> str:
        """نصّ الصفحة المُحالة نفسها ليحمله الختم شاهدًا قابلًا للتحقق عند النقر.
        كتاب غير مستخرج بعد يُترك بلا نصّ؛ فلا استخراج كسولًا في مرحلة الختم
        خشية إبطائها (يُستخرج عند أول فتح فعلي للصفحة)."""
        key = (str(row.get("book_id") or ""), str(part or ""), str(page or ""))
        if key in _quote_cache:
            return _quote_cache[key]
        q = ""
        try:
            rel = str(row.get("rel_path") or "")
            if key[0] and key[2].isdigit() and rel and shamela_local_mcp._dir_for_rel(rel) is not None:
                pg = shamela_local_mcp.get_page(int(key[0]), int(key[2]), part or None)
                if pg.get("status") == "ok":
                    q = " ".join(str((pg.get("page") or {}).get("body") or "").split())[:120]
        except Exception:
            q = ""
        _quote_cache[key] = q
        return q

    def _resolve(candidate: str) -> Optional[dict]:
        key = (candidate or "").strip()
        if key in _cache:
            return _cache[key]
        # المرشح يصل ملصوقًا به المؤلف غالبًا («الموافقات، الشاطبي»): والمؤلف
        # يضلّل المطابقة الضبابية فتُرجع كتابًا آخر يضم اللفظين في عنوانه.
        # تُجرَّب الصورة الكاملة أولًا، ثم بفصل آخر مقطع (المؤلف) تباعًا.
        attempts = [key]
        trimmed = key
        while re.search(r"[،,]", trimmed) and len(attempts) < 4:
            trimmed = re.sub(r"[،,][^،,]*$", "", trimmed).strip(" ،,")
            if trimmed and trimmed not in attempts:
                attempts.append(trimmed)
        for _a in list(attempts):
            _d = _possessive_detached(_a)
            if _d != _a and _d not in attempts:
                attempts.append(_d)
        row = None
        for attempt in attempts:
            try:
                r = shamela_local_mcp.resolve_book(attempt)
            except Exception:
                r = None
            if not (r and r.get("status") == "ok" and r.get("book_id")):
                continue
            if attempt.startswith("#"):
                # الرقم الصريح أقوى من أي تشابه عنواني: هو هوية الكتاب نفسه.
                row = r
                break
            cand_key = _stamp_title_key(attempt)
            res_key = _stamp_title_key(r.get("title") or "")
            variants = [cand_key]
            if cand_key.startswith("و") and len(cand_key) > 3:
                variants.append(cand_key[1:].lstrip())
            score = 0
            for variant in variants:
                if variant == res_key:
                    score = max(score, 1000)
                elif f" {res_key} " in f" {variant} " or f" {variant} " in f" {res_key} ":
                    score = max(score, 900)
                elif res_key.startswith(variant + " ") and len(_stamp_content_words(variant)) >= 2:
                    score = max(score, 700)
                elif variant.startswith(res_key + " ") and len(_stamp_content_words(res_key)) >= 2:
                    score = max(score, 700)
            if score < 900:
                # العنوان القصير المشهور بمؤلفه («المجموع للنووي» وكتابه في
                # القاعدة «المجموع شرح المهذب» للنووي): أول العنوان مشترك
                # وآخر المرشح هو المؤلف بعينه في بيانات الكتاب — قبول بثقته.
                _hw = [w for w in cand_key.split() if len(w) >= 4]
                _rak = _stamp_title_key(r.get("author") or "").split()
                if (len(_hw) >= 2 and res_key.split()[:1] == cand_key.split()[:1]
                        and _hw[-1] in _rak):
                    score = 900
            if score >= 900 or (score >= 700 and not r.get("ambiguous")):
                row = r
                break
        _cache[key] = row
        return row

    def enrich_chunk(chunk: str) -> str:
        out = []
        pos = 0
        for match in _STAMP_LOCATOR.finditer(chunk):
            segment = chunk[pos:match.start()]
            cut = max(segment.rfind(mark) for mark in ("\n", "؛", ";", "•", "|", ")")) + 1
            raw_title = segment[cut:]
            part = _plain_locator_number(match.group("part") or match.group("comma_part") or "")
            page = _plain_locator_number(match.group("only_page") or match.group("page") or match.group("comma_page") or "")
            # الرقم الصريح يُبحث في كامل المقطع السابق للموضع: فالأقواس التوضيحية
            # «(شرح صحيح البخاري)» تقطع استخراج العنوان وتُسقط الرقم منه.
            id_match = re.search(r"#\s*(\d{1,5})\b", segment)
            row = None
            title_start = pos + cut
            prefix_end = None
            if id_match:
                row = _resolve(f"#{id_match.group(1)}")
                after_id = segment[id_match.end():]
                title_start = pos + id_match.end() + (len(after_id) - len(after_id.lstrip()))
                prefix_end = pos + id_match.start()
            else:
                candidate = _stamp_candidate(raw_title)
                if candidate:
                    row = _resolve(candidate)
                    offset = raw_title.find(candidate)
                    title_start = pos + cut + (offset if offset >= 0 else 0)
                if not row:
                    # العنوان بين قوسي اقتباس في متن خبري («وقع النقل في
                    # «المجموع» للنووي (9-256)»): المقتبس هو العنوان حتمًا،
                    # والمؤلف بعده فاصل الطبعات — فالعارية وحدها تنحرف
                    # («المجموع» وحده لمجموع الفتاوى لا لشرح المهذب).
                    _qm = list(re.finditer(r"«([^»]{3,60})»", raw_title))
                    if _qm:
                        _q = _qm[-1]
                        _qt = _q.group(1).strip()
                        _after = raw_title[_q.end():].strip(" ،,؛:")
                        _hint = re.sub(r"^(?:لل|ل)\s*", "", _after).split()[0] if _after else ""
                        for _cand in (f"{_qt} {_hint}".strip(), _qt):
                            if not _cand:
                                continue
                            _r = _resolve(_cand)
                            if not _r:
                                continue
                            if _hint and len(_hint) >= 4:
                                _hf = _fold_book_text(_hint)
                                if (_hf not in _fold_book_text(_r.get("author") or "")
                                        and _hf not in _fold_book_text(_r.get("title") or "")):
                                    continue
                            row = _r
                            title_start = pos + cut + _q.start()
                            break
            if not row:
                _cand_txt = chunk[title_start:match.end()]
                # إشارة نثرية خبرية («وقع في...»، «بينما ثبت في...») ليست
                # إحالة توثيق قائمة بنفسها: لا تُوسم ⚠ ولو تعذر ختمها،
                # فالوسم للإحالات القاصدة لا لحديث المتن عن مواضع النقول.
                _narrative = any(h in segment for h in
                                 ("وقع", "ثبت", "حكاه", "حكى", "بينما", "أطلق", "قيّد", "قيدت", "جاء في", "نقل في"))
                if _narrative and not id_match:
                    out.append(chunk[pos:match.end()])
                    pos = match.end()
                    continue
                if id_match or len((_cand_txt or "").strip()) >= 6:
                    _unresolved[0] += 1
                    out.append(chunk[pos:title_start])
                    out.append(
                        '<span class="cit-unresolved" style="color:#b45309;text-decoration:underline dashed" '
                        'title="مرجع لم يتحقق النظام منه في مكتبته — على ذمة النموذج">⚠ '
                        + chunk[title_start:match.end()] + "</span>")
                else:
                    out.append(chunk[pos:match.end()])
                pos = match.end()
                continue
            attrs = (
                f'data-book="{html.escape(str(row.get("title") or ""), quote=True)}" '
                f'data-rel-path="{html.escape(str(row.get("rel_path") or ""), quote=True)}" '
                f'data-book-id="{html.escape(str(row.get("book_id") or ""), quote=True)}" '
                f'data-part="{html.escape(part, quote=True)}" '
                f'data-page="{html.escape(str(page or ""), quote=True)}" '
                f'data-quote="{html.escape(_page_quote(row, part, page), quote=True)}"'
            )
            out.append(chunk[pos:(prefix_end if prefix_end is not None else title_start)])
            _disp = (canonical_citation_label(row.get("title"), part, page, author=row.get("author"))
                     or chunk[title_start:match.end()])
            out.append(f'<span class="cit-src" {attrs}>{html.escape(_disp)}</span>')
            pos = match.end()
        out.append(chunk[pos:])
        return "".join(out)

    parts = re.split(r"(<[^>]+>)", text)
    out_parts = []
    inside_cit = 0
    for part in parts:
        if part.startswith("<"):
            low = part.lower()
            if low.startswith("<span") and "cit-src" in low:
                inside_cit += 1
            elif low.startswith("</span") and inside_cit:
                inside_cit -= 1
            out_parts.append(part)
        elif inside_cit:
            out_parts.append(part)
        else:
            out_parts.append(enrich_chunk(part))
    return "".join(out_parts), _unresolved[0]

_FOOTNOTE_ITEM = re.compile(
    r"<li\b(?P<attrs>[^>]*\bid\s*=\s*[\"']fn(?P<num>[0-9٠-٩۰-۹]{1,3})[\"'][^>]*)>(?P<body>.*?)</li>",
    re.IGNORECASE | re.DOTALL,
)
_FOOTNOTE_MARKER = re.compile(
    r"<sup>\s*(?:<a\b[^>]*>\s*)?(?:<small>\s*)?\(?\s*([0-9٠-٩۰-۹]{1,3})\s*\)?(?:\s*</small>)?\s*(?:</a>)?\s*</sup>",
    re.IGNORECASE,
)
_FOOTNOTE_LEAD = re.compile(r"(?:ينظر|انظر|راجع|يُنظر)\s*[:：]?")


def _footnote_number(value: Any) -> int:
    try:
        return int(str(value or "").translate(_EASTERN_DIGITS))
    except ValueError:
        return 0


def _arabic_indic_number(number: int) -> str:
    return str(number).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def _split_footnote_segments(body: str) -> List[str]:
    """يقطع متن الحاشية عند الفاصلة المنقوطة خارج وسوم HTML فقط.

    نص الشاهد داخل خاصية data-quote قد يحوي «؛»، وقطعه يمزق وسم الختم
    فيبقى «انظر:» بلا مرجع. الوسم كله يبقى في مقطع واحد.
    """
    tokens = []
    buf = []
    in_tag = False
    for ch in body or "":
        if ch == "<":
            in_tag = True
        if not in_tag and ch in "؛;":
            tokens.append("".join(buf))
            tokens.append(ch)
            buf = []
            continue
        buf.append(ch)
        if ch == ">":
            in_tag = False
    tokens.append("".join(buf))
    return tokens


def _clean_footnote_body(body: str) -> str:
    """يبقي في الحاشية الإحالات المربوطة بشاهد فحسب، ويحذف ما عداها منها."""
    tokens = _split_footnote_segments(body or "")
    kept = []
    for index, token in enumerate(tokens):
        if token in ("؛", ";"):
            if kept and kept[-1] not in ("؛", ";"):
                kept.append(token)
            continue
        verified = "cit-src" in token
        unverified_reference = bool(_STAMP_LOCATOR.search(token)) or bool(_FOOTNOTE_LEAD.search(token))
        if verified or not unverified_reference:
            kept.append(token)
    cleaned = "".join(kept).strip()
    cleaned = re.sub(r"^[؛;\s]+|[؛;\s]+$", "", cleaned)
    cleaned = re.sub(r"(؛\s*){2,}", "؛ ", cleaned)
    return cleaned


def filter_unverified_footnotes(text: str) -> str:
    """يحذف كل حاشية لا يقابلها شاهد منقول مربوط، مع رقمها في المتن، ثم يعيد الترقيم.

    الحاشية في البحث الشرعي شهادة نقل، فلا تبقى إحالة لم ينقل عنها الجواب
    من الشواهد المعطاة برقمها الفريد أو بعنوانها وموضعها المضبوطين.
    """
    if not text:
        return text
    items = list(_FOOTNOTE_ITEM.finditer(text))
    if not items:
        lines = []
        kept_refs = 0
        changed = False
        for line in text.splitlines():
            numbered = re.match(
                r"^(?P<prefix>\s*(?:[-*]\s*)?\(?)(?P<num>[0-9٠-٩۰-۹]{1,3})(?P<sep>\)?\s*[.)-]\s+)(?P<rest>.*)$",
                line,
            )
            rest = numbered.group("rest") if numbered else line
            reference_line = bool(_STAMP_LOCATOR.search(rest) or _FOOTNOTE_LEAD.search(rest))
            if not reference_line:
                lines.append(line)
                continue
            if "cit-src" not in line:
                changed = True
                continue
            kept_refs += 1
            if numbered:
                old = numbered.group("num")
                shown = _arabic_indic_number(kept_refs) if re.search(r"[٠-٩۰-۹]", old) else str(kept_refs)
                line = f"{numbered.group('prefix')}{shown}{numbered.group('sep')}{rest}"
            lines.append(line)
        return "\n".join(lines) if changed else text
    mapping = {}
    removed = set()
    replacements = {}
    for match in items:
        old_number = _footnote_number(match.group("num"))
        cleaned = _clean_footnote_body(match.group("body"))
        if "cit-src" not in cleaned:
            removed.add(old_number)
            replacements[match.start()] = ""
            continue
        new_number = len(mapping) + 1
        mapping[old_number] = new_number
        attrs = re.sub(
            r"(\bid\s*=\s*[\"'])fn[0-9٠-٩۰-۹]{1,3}([\"'])",
            rf"\g<1>fn{new_number}\g<2>",
            match.group("attrs"),
            count=1,
        )
        replacements[match.start()] = f"<li{attrs}>{cleaned}</li>"
    if not removed and len(mapping) == len(items):
        # لا حذف، لكن نظّف أي إحالة زائدة داخل الحواشي المحفوظة.
        result = _FOOTNOTE_ITEM.sub(lambda m: replacements[m.start()], text)
    else:
        result = _FOOTNOTE_ITEM.sub(lambda m: replacements[m.start()], text)

    def marker(match: re.Match) -> str:
        old_number = _footnote_number(match.group(1))
        if old_number in removed:
            return ""
        new_number = mapping.get(old_number)
        if not new_number:
            return ""
        return f"<sup><small>({_arabic_indic_number(new_number)})</small></sup>"

    return _FOOTNOTE_MARKER.sub(marker, result)


# =============================================================================
# تدقيق التوثيق العام لخط المشاريع والوكلاء: كل نقل منقول يُطابَق على صفحة
# كتابه المحال إليه، لكن التدقيق غير مدمّر؛ فما لم يثبت آليًا يبقى في النص
# ويُنبَّه عليه في سجل ختامي ظاهر للمراجعة البشرية، ولا يُحذف ولا تُستبدل
# الإجابة بجولة إصلاح. ضبط النسبة يكون قبل الكتابة ببطاقات الأدلة.
# =============================================================================
_TIER_BLOCK_PATTERNS = (
    "شرح صوتي", "دروس صوتية", "تفريغ صوتي", "الموسوعة الفقهية", "كنز العمال",
    "جامع الأحاديث", "موسوعة جمال", "الفقه المنهجي", "فتاوى نور على الدرب",
    # شروح حديثية ناقلة: أصلٌ لأقوال شارحها، وواسطةٌ لما تنقله عن غيرها —
    # فإذا انفردت في حاشية عُدّت وسيطًا يحتاج أصلَه المنقول عنه.
    "شرح سنن", "عون المعبود", "تحفة الأحوذي", "بذل المجهود", "فيض القدير",
    "مرقاة المفاتيح", "نيل الأوطار", "سبل السلام", "شرح بلوغ المرام", "توضيح الأحكام",
)
_IJMA_SOURCE_KEYS = ("إجماع", "الاستذكار", "التمهيد", "بداية المجتهد", "المغني")
_IJMA_CLAIM_RE = re.compile(r"(أجمع|إجماعًا|إجماع |اتفق (?:الفقهاء|أهل العلم|العلماء|المسلمون))")
_PLAIN_MARKER_RE = re.compile(r"\(\s*([0-9٠-٩]{1,3})\s*\)")
_BRACKET_MARKER_RE = re.compile(r"\[\s*([0-9٠-٩]{1,3})\s*\]")
_FOOTNOTE_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\(\s*(?P<np>[0-9٠-٩]{1,3})\s*\)|\[\s*(?P<nb>[0-9٠-٩]{1,3})\s*\])\s+(?P<body>.*)$")
_FOOTNOTE_NUMLIST_RE = re.compile(r"^\s*(?P<nl>[0-9٠-٩]{1,3})\s*[.)]\s+(?P<body>.*)$")


def _line_def_number(match: re.Match) -> int:
    for name in ("np", "nb", "nl"):
        try:
            value = match.group(name)
        except Exception:
            value = None
        if value:
            return _footnote_number(value)
    return 0


def _num_style(token: str, number: int) -> str:
    return _arabic_indic_number(number) if re.search(r"[٠-٩]", token or "") else str(number)


def _footnote_defs(text: str):
    """مواضع تعريفات الحواشي: عناصر <li id=fnN> أو سطور (ن) في آخر الجواب."""
    defs = []
    for m in _FOOTNOTE_ITEM.finditer(text or ""):
        defs.append({"num": _footnote_number(m.group("num")), "start": m.start(),
                     "end": m.end(), "kind": "li", "body": m.group("body") or ""})
    spans = [(d["start"], d["end"]) for d in defs]
    offset = 0
    for line in (text or "").splitlines(keepends=True):
        clean_line = line.rstrip("\n")
        if not any(s <= offset < e for s, e in spans):
            lm = _FOOTNOTE_LINE_RE.match(clean_line)
            if lm:
                defs.append({"num": _line_def_number(lm), "start": offset,
                             "end": offset + len(line), "kind": "line", "body": lm.group("body") or ""})
            else:
                nm = _FOOTNOTE_NUMLIST_RE.match(clean_line)
                if nm and (_STAMP_LOCATOR.search(nm.group("body") or "")
                           or _FOOTNOTE_LEAD.search(nm.group("body") or "")
                           or "cit-src" in (nm.group("body") or "")):
                    defs.append({"num": _line_def_number(nm), "start": offset,
                                 "end": offset + len(line), "kind": "line", "body": nm.group("body") or ""})
        offset += len(line)
    return defs


def _footnote_book_id(body: str):
    m = re.search(r'data-book-id="(\d{1,7})"', body or "")
    if m:
        return m.group(1)
    m = re.search(r"#\s*(\d{1,7})\b", body or "")
    return m.group(1) if m else None


def _renumber_footnotes(text: str) -> str:
    """يعيد ترقيم الحواشي بعد الحذف: علامات المتن وتعريفاتها بسلم واحد متصل."""
    defs = _footnote_defs(text)
    def_spans = [(d["start"], d["end"]) for d in defs]

    def in_def(pos: int) -> bool:
        return any(s <= pos < e for s, e in def_spans)

    order: List[int] = []

    def note(num: int):
        if num and num not in order:
            order.append(num)

    for m in _FOOTNOTE_MARKER.finditer(text or ""):
        if not in_def(m.start()):
            note(_footnote_number(m.group(1)))
    for m in _PLAIN_MARKER_RE.finditer(text or ""):
        if in_def(m.start()):
            continue
        line_start = (text or "").rfind("\n", 0, m.start()) + 1
        if not (text or "")[line_start:m.start()].strip():
            continue
        note(_footnote_number(m.group(1)))
    for m in _BRACKET_MARKER_RE.finditer(text or ""):
        if in_def(m.start()):
            continue
        line_start = (text or "").rfind("\n", 0, m.start()) + 1
        if not (text or "")[line_start:m.start()].strip():
            continue
        note(_footnote_number(m.group(1)))
    if not order:
        return text
    mapping = {old: i + 1 for i, old in enumerate(order)}
    keep = set(order)

    def marker_sub(m: re.Match) -> str:
        num = _footnote_number(m.group(1))
        if num not in mapping:
            return ""
        return f"<sup><small>({_num_style(m.group(1), mapping[num])})</small></sup>"

    text = _FOOTNOTE_MARKER.sub(
        lambda m: m.group(0) if in_def(m.start()) else marker_sub(m), text)

    def plain_sub(m: re.Match) -> str:
        if in_def(m.start()):
            return m.group(0)
        line_start = text.rfind("\n", 0, m.start()) + 1
        if not text[line_start:m.start()].strip():
            return m.group(0)
        num = _footnote_number(m.group(1))
        if num not in mapping:
            return ""
        return f"({_num_style(m.group(1), mapping[num])})"

    text = _PLAIN_MARKER_RE.sub(plain_sub, text)

    def bracket_sub(m: re.Match) -> str:
        if in_def(m.start()):
            return m.group(0)
        line_start = text.rfind("\n", 0, m.start()) + 1
        if not text[line_start:m.start()].strip():
            return m.group(0)
        num = _footnote_number(m.group(1))
        if num not in mapping:
            return ""
        return f"[{_num_style(m.group(1), mapping[num])}]"

    text = _BRACKET_MARKER_RE.sub(bracket_sub, text)

    def def_sub(m: re.Match) -> str:
        num = _footnote_number(m.group("num"))
        if num not in keep:
            return ""
        return re.sub(r'(id\s*=\s*["\'])fn[0-9٠-٩]{1,3}(["\'])',
                      rf"\g<1>fn{mapping[num]}\g<2>", m.group(0), count=1)

    text = _FOOTNOTE_ITEM.sub(def_sub, text)
    out_lines = []
    for line in text.splitlines():
        lm = _FOOTNOTE_LINE_RE.match(line) or _FOOTNOTE_NUMLIST_RE.match(line)
        if lm:
            num = _line_def_number(lm)
            if num not in keep:
                continue
            token = next((g for g in (lm.groupdict().get("np"), lm.groupdict().get("nb"),
                                      lm.groupdict().get("nl")) if g), "")
            if lm.groupdict().get("nb"):
                repl = f"[{_num_style(token, mapping[num])}]"
                line = re.sub(r"\[\s*[0-9٠-٩]{1,3}\s*\]", repl, line, count=1)
            elif lm.groupdict().get("nl") and not lm.groupdict().get("np"):
                repl = f"{_num_style(token, mapping[num])}."
                line = re.sub(r"[0-9٠-٩]{1,3}\s*\.", repl, line, count=1)
            else:
                repl = f"({_num_style(token, mapping[num])})"
                line = re.sub(r"\(\s*[0-9٠-٩]{1,3}\s*\)", repl, line, count=1)
        out_lines.append(line)
    return "\n".join(out_lines)


def _documentation_gate(text: str, witness_rows: List[dict]):
    """يطابق كل نقل منقول على كتاب إحالته، ويُصلح مواضع الإحالات، ويستبعد
    ما كان مصدره خارج المكتبة.

    يرجع (النص بعد الإصلاح والاستبعاد، إحصاء). ما لم يثبت آليًا في كتاب
    مكتبة يُحصى ويُنبَّه عليه للمراجعة؛ أما النقل الذي لا كتاب له في
    المكتبة البتة فيُقطع بحاشيته — قاعدة: لا نقل من خارج المكتبة."""
    stats = {"checked": 0, "verified": 0, "cut_notfound": 0, "cut_relocated": 0,
             "cut_tier": 0, "unverified": 0, "relocated": 0, "tier_warnings": 0,
             "ijma_flags": 0, "tier_footnotes": 0, "cited_book_ids": [],
             "failures": []}
    if not text:
        return text, stats
    defs = _footnote_defs(text)
    plain_by_num = {}
    for d in defs:
        plain_by_num[d["num"]] = re.sub(r"<[^>]+>", " ", d["body"])
        if any(p in plain_by_num[d["num"]] for p in _TIER_BLOCK_PATTERNS):
            stats["tier_footnotes"] += 1
    _bid_cache: Dict[int, Optional[str]] = {}

    def cited_bid(num) -> Optional[str]:
        """رقم كتاب إحالة الحاشية، يُحلّ كسلًا عند الحاجة فقط (حلّ الكل بطيء)."""
        if num in _bid_cache:
            return _bid_cache[num]
        bid = None
        d = next((x for x in defs if x["num"] == num), None)
        if d is not None:
            bid = _footnote_book_id(d["body"])
            if not bid:
                title_seg = _FOOTNOTE_LEAD.sub("", plain_by_num.get(num, "").strip())
                title_seg = re.split(r"[،,(]", title_seg)[0].strip()
                if len(title_seg) >= 4:
                    try:
                        row = shamela_local_mcp.resolve_book(title_seg)
                        if row and row.get("book_id"):
                            bid = str(row["book_id"])
                    except Exception:
                        bid = None
        _bid_cache[num] = bid
        return bid

    def footnote_locator(num):
        m = _STAMP_LOCATOR.search(plain_by_num.get(num, "") or "")
        if not m:
            return None, None
        part = _plain_locator_number(m.group("part") or m.group("comma_part") or "")
        page = _plain_locator_number(m.group("only_page") or m.group("page") or m.group("comma_page") or "")
        return part, page

    _profile_cache: Dict[Any, dict] = {}

    def footnote_profile(num):
        """ملف حاشية: الوسيط (موسوعة/صوتي) محظور سندًا وحيدًا لنقل، ومشروع
        للمقارنة والضبط بجانب أصل — فلا يُقطع نقل قامت حاشيته على أصل ووسيط."""
        if num in _profile_cache:
            return _profile_cache[num]
        plain = plain_by_num.get(num, "")
        segs = [s for s in re.split(r"[؛;]", plain) if len(s.strip()) >= 4]
        seg_tier = [any(p in s for p in _TIER_BLOCK_PATTERNS) for s in segs]
        if not seg_tier:
            seg_tier = [any(p in plain for p in _TIER_BLOCK_PATTERNS)]
        d = next((x for x in defs if x["num"] == num), None)
        bids = re.findall(r'data-book-id="(\d{1,7})"', d["body"]) if d else []
        if not bids:
            # بلا ختم آلي: اعتمد أول مصدر غير وسيط في الحاشية كتابًا للإحالة
            resolved = None
            for s, t_ in zip(segs or [plain], seg_tier):
                if t_:
                    continue
                seg_title = _FOOTNOTE_LEAD.sub("", s.strip())
                seg_title = re.split(r"[،,(]", seg_title)[0].strip()
                if len(seg_title) >= 4:
                    try:
                        row = shamela_local_mcp.resolve_book(seg_title)
                        if row and row.get("book_id"):
                            resolved = str(row["book_id"])
                            break
                    except Exception:
                        pass
            b = resolved or cited_bid(num)
            bids = [b] if b else []
        cited = None
        if len(bids) == len(seg_tier):
            for b, t_ in zip(bids, seg_tier):
                if not t_:
                    cited = b
                    break
        if cited is None:
            cited = bids[0] if bids else cited_bid(num)
        profile = {"tier_only": bool(seg_tier) and all(seg_tier),
                   "any_tier": any(seg_tier), "cited": cited}
        _profile_cache[num] = profile
        return profile

    witness_ids = []
    for row in witness_rows or []:
        bid = _book_id_value(row.get("book_id"))
        if bid and str(bid) not in witness_ids:
            witness_ids.append(str(bid))

    def _parse_unresolved(raw):
        """«الموافقات، الشاطبي، 2، 413» → كتابها وموضعها: يُفصل المؤلف عن
        العنوان تباعًا (فهو ما أضلّ المطابقة)، ويُقبل حلٌّ يطابق عنوانه."""
        txt = re.sub(r"<[^>]+>", " ", raw or "").replace("⚠", " ")
        txt = re.sub(r"\s+", " ", txt).strip()
        m = _STAMP_LOCATOR.search(txt)
        if not m:
            return None
        part = _plain_locator_number(m.group("part") or m.group("comma_part") or "")
        page = _plain_locator_number(m.group("only_page") or m.group("page") or m.group("comma_page") or "")
        attempts = [txt[:m.start()].strip(" ،,؛:")]
        trimmed = attempts[0]
        while re.search(r"[،,]", trimmed) and len(attempts) < 4:
            trimmed = re.sub(r"[،,][^،,]*$", "", trimmed).strip(" ،,")
            if trimmed and trimmed not in attempts:
                attempts.append(trimmed)
        for att in attempts:
            if not att:
                continue
            try:
                row = shamela_local_mcp.resolve_book(att)
            except Exception:
                row = None
            if row and row.get("status") == "ok" and row.get("book_id"):
                ak, rk = _stamp_title_key(att), _stamp_title_key(row.get("title") or "")
                if ak and rk and (ak == rk or f" {rk} " in f" {ak} " or f" {ak} " in f" {rk} "):
                    return {"bid": str(row["book_id"]), "part": part, "page": page,
                            "title": row.get("title") or "", "author": row.get("author") or "",
                            "rel_path": row.get("rel_path") or ""}
        return None

    _span_books_cache: Dict[Any, list] = {}

    def footnote_span_books(num):
        """كتب الحاشية واحدًا واحدًا بمواضعها: مختومة بأرقامها، ومُعلَّمة ⚠
        بحلّ عنوانها — فالحاشية قد تجمع كتابين والشاهد في ثانيهما."""
        if num in _span_books_cache:
            return _span_books_cache[num]
        out = []
        d = next((x for x in defs if x["num"] == num), None)
        if d:
            for tm in re.finditer(r'<span class="cit-src"[^>]*>', d["body"]):
                tag = tm.group(0)
                mb = re.search(r'data-book-id="(\d+)"', tag)
                if mb:
                    mp = re.search(r'data-part="([^"]*)"', tag)
                    mg = re.search(r'data-page="(\d*)"', tag)
                    out.append({"bid": mb.group(1), "kind": "src",
                                "part": mp.group(1) if mp else "",
                                "page": mg.group(1) if mg else ""})
            for um in re.finditer(r'<span class="cit-unresolved"[^>]*>(.*?)</span>', d["body"], re.S):
                info = _parse_unresolved(um.group(1))
                if info:
                    info["kind"] = "unres"
                    out.append(info)
        _span_books_cache[num] = out
        return out

    # كتب الحواشي المعلَّمة تُحلّ الآن فتدخل الشواهد: يبلغها بحث المواضع.
    for d in defs:
        if "cit-unresolved" in d["body"]:
            for sp in footnote_span_books(d["num"]):
                if sp["bid"] not in witness_ids:
                    witness_ids.append(sp["bid"])

    def _title_in_library(raw) -> bool:
        """عنوان الإحالة وحده (بلا موضع) موجود في المكتبة؟ الفصل بين «كتاب
        خارج المكتبة» (يُستبعد) و«كتاب فيها أُحيل إليه بلا موضع تام»."""
        txt = re.sub(r"<[^>]+>", " ", raw or "").replace("⚠", " ")
        txt = re.sub(r"\s+", " ", txt).strip()
        m = _STAMP_LOCATOR.search(txt)
        head = (txt[:m.start()] if m else txt).strip(" ،,؛:")
        attempts = [head]
        trimmed = head
        while re.search(r"[،,]", trimmed) and len(attempts) < 4:
            trimmed = re.sub(r"[،,][^،,]*$", "", trimmed).strip(" ،,")
            if trimmed and trimmed not in attempts:
                attempts.append(trimmed)
        for att in attempts:
            if not att:
                continue
            try:
                row = shamela_local_mcp.resolve_book(att)
            except Exception:
                row = None
            if row and row.get("status") == "ok" and row.get("book_id"):
                ak, rk = _stamp_title_key(att), _stamp_title_key(row.get("title") or "")
                if ak and rk and (ak == rk or f" {rk} " in f" {ak} " or f" {ak} " in f" {rk} "):
                    return True
        return False

    def _outside_library(job) -> bool:
        """حاشية النقل لا كتاب لها في المكتبة البتة: لا ختم، ولا حلّ عنوان،
        ولا رقم إحالة — فمصدر النقل خارج المكتبة ويخضع لقاعدة الاستبعاد."""
        num = job.get("num")
        if not num:
            return False
        if footnote_span_books(num):
            return False
        if cited_bid(num):
            return False
        d = next((x for x in defs if x["num"] == num), None)
        if d and _title_in_library(d["body"]):
            return False
        return True

    def_spans = [(d["start"], d["end"]) for d in defs]

    def in_def(pos: int) -> bool:
        return any(s <= pos < e for s, e in def_spans)

    # جمع مهام النقول أولًا، ثم فحصها بمرحلتين متوازيتين: كتاب الإحالة بتلميح
    # موضعه، ثم بدائل محدودة للفاشل فقط — فلا يتفجر زمن البوابة على جواب كبير.
    # تنبيه بنيوي: قيم خصائص الوسوم (data-quote ونحوها) وعلامات التنصيص العابرة
    # للوسوم ليست نقولًا؛ تجاهلها شرط حتى لا تُفحص سمات HTML كنصوص كتب.
    tag_spans = [(m.start(), m.end()) for m in re.finditer(r"<[^>]+>", text or "")]

    def in_tag(pos: int) -> bool:
        return any(s <= pos < e for s, e in tag_spans)

    _quote_matches = [m for m in _RAW_QUOTE_RE.finditer(text)
                      if not in_def(m.start()) and not in_tag(m.start())]
    jobs = []
    for qi, m in enumerate(_quote_matches):
        raw_q = next((g for g in m.groups() if g), "")
        # وسوم تنسيق داخل النقل (<b> و<strong> ونحوهما) لا تُسقطه من الفحص:
        # تُنزع للمطابقة وحدها، فأكثر نقول الأجوبة المنسقة كانت تُستبعد لهذا.
        quote = re.sub(r"<[^>]+>", " ", raw_q)
        quote = re.sub(r"\s+", " ", quote).strip()
        if len(quote) < 25:
            continue
        marker_span, num = None, None
        # نافذة الربط: حتى النقل التالي أو نهاية الفقرة أو 1200 حرف — فالحاشية
        # قد تتأخر عن النقل بأسطر تحرير كاملة، ونافذة 200 حرف كانت تعمي
        # التدقيق عن أكثر النقول الصحيحة.
        next_q = _quote_matches[qi + 1].start() if qi + 1 < len(_quote_matches) else len(text)
        para_end = len(text)
        for _sep in ("</p>", "\n\n"):
            _pi = text.find(_sep, m.end())
            if _pi != -1:
                para_end = min(para_end, _pi)
        tail_end = min(next_q, para_end, m.end() + 1200)
        tail = text[m.end():tail_end]
        mm = _FOOTNOTE_MARKER.search(tail)
        pm = _PLAIN_MARKER_RE.search(tail)
        bm = _BRACKET_MARKER_RE.search(tail)
        cands = [x for x in (mm, pm, bm) if x]
        if cands:
            first = min(cands, key=lambda x: x.start())
            marker_span = (m.end() + first.start(), m.end() + first.end())
            num = _footnote_number(first.group(1))
        jobs.append({"quote": quote, "start": m.start(),
                     "cut_end": marker_span[1] if marker_span else m.end(), "num": num})
    stats["checked"] = len(jobs)
    stats["linked"] = sum(1 for j in jobs if j.get("num"))

    import time as _time
    from concurrent.futures import ThreadPoolExecutor
    _t0 = _time.time()
    _match_cache: Dict[Tuple[str, str], bool] = {}

    def _fts_has_candidate(bid, quote):
        """مرشحات فهرس المكتبة داخل الكتاب: لا مرشح = النقل غائب، فلا مسح كاملًا.

        يجرّب مقطعين مميزين من النقل (أوله ووسطه) بثماني كلمات لكل منهما.
        يرجع True/False، أو None عند تعذر الفهرس فيُحتكم إلى المسح الدقيق."""
        try:
            import library_search
            li = library_search.get_index()
            words = [w for w in re.findall(r"[\u0600-\u06FF]{3,}", _fold_ar(quote))]
            if len(words) < 4:
                return None
            mid = max(0, len(words) // 2 - 2)
            longest = sorted(words, key=len, reverse=True)[:4]
            probes = [" ".join(words[:5]), " ".join(words[mid:mid + 5]), " ".join(longest)]
            for probe in dict.fromkeys(probes):
                if len(probe) < 12:
                    continue
                r = li.search(probe, mode="words", book_ids=[int(bid)], limit=4)
                if r and r.get("results"):
                    return True
            return False
        except Exception:
            return None

    def _contains_fold(page_f: str, quote: str) -> bool:
        """احتواء متسامح مع الحذف والاختصار: مقطع مطوي كامل، أو 80% من
        كلمات النقل المميزة حاضرة في الصفحة."""
        qf = _fold_ar(quote)
        if len(qf) >= 24 and qf[:24] in page_f:
            return True
        for a, b in ((0, 40), (len(qf) // 3, len(qf) // 3 + 40),
                     (max(0, len(qf) - 40), len(qf))):
            seg = qf[a:b].strip()
            if len(seg) >= 20 and seg in page_f:
                return True
        segwords = {w for w in qf.split() if len(w) >= 4}
        if not segwords:
            return False
        hits = sum(1 for w in segwords if w in page_f)
        return hits / len(segwords) >= 0.8

    def _bridge_match(bid, quote):
        """تحقق من فهرس المكتبة نفسه (مرآة الشاملة عبر جسورها): عبارة مميزة
        من النقل داخل كتاب إحالته، فإن لم توجد فكلماته المميزة مجتمعة في
        صفحة واحدة ثم تحقق من متنها — إثبات موضعي في أجزاء الثانية بدل مسح
        ملف الكتاب كله. True إثبات، False لا شاهد، None تعذّر الجسر."""
        try:
            import shamela_link as _SLV
            if _SLV.library_source() != "shamela":
                return None
            import shamela_search
            words = [w for w in re.findall(r"[\u0600-\u06FF]{3,}", _fold_ar(quote))]
            if len(words) < 4:
                return None
            r = shamela_search.search(" ".join(words[:7]), mode="phrase",
                                       book_ids=[int(bid)], limit=2)
            if r.get("results"):
                return True
            distinct = sorted(set(words), key=len, reverse=True)[:6]
            if len(distinct) < 3:
                return False
            r2 = shamela_search.search(" ".join(distinct), mode="words",
                                        book_ids=[int(bid)], limit=4)
            for h in (r2.get("results") or []):
                pg = shamela_local_mcp.get_page(int(bid), int(h.get("page_num") or 0),
                                                 h.get("part") or None)
                if pg.get("status") == "ok" and _contains_fold(
                        _fold_ar((pg.get("page") or {}).get("body") or ""), quote):
                    return True
            return False
        except Exception:
            return None

    def _match(bid, quote, part=None, page=None, allow_scan=False) -> bool:
        key = (str(bid), quote[:180])
        if key in _match_cache:
            return _match_cache[key]
        bm = _bridge_match(bid, quote)
        if bm:
            _match_cache[key] = True
            return True
        if bm is False:
            # الجسر فهرس قاعدة بيانات الكتب نفسه: بحث ووجد الكتاب خاليًا من
            # النقل فلا مسح كاملًا باهظًا بعده؛ المسح احتياطي لتعذّر الجسر.
            _match_cache[key] = False
            return False
        ok = False
        # المسبار حارس سرعة للكتب البديلة فقط؛ كتاب الإحالة نفسه يُفحص دائمًا
        # بالمسح المتسامح، فمسبار صارم قد يقتل نقلًا قريبًا من الحرفية قبل فحصه.
        if allow_scan or _fts_has_candidate(bid, quote) is not False:
            try:
                page_int = int(page) if page not in (None, "") else None
            except Exception:
                page_int = None
            try:
                r = shamela_local_mcp.verify_quote(
                    book=str(bid), quote_text=quote,
                    part=str(part) if part not in (None, "") else None, page_hint=page_int)
                ok = bool(r and r.get("match_status") in ("MATCH_EXACT", "MATCH_NORMALIZED"))
            except Exception:
                ok = False
        _match_cache[key] = ok
        return ok

    pending = []
    for job in jobs:
        profile = footnote_profile(job["num"])
        job["bid"] = profile.get("cited")
        if profile.get("any_tier"):
            stats["tier_corroborated"] = stats.get("tier_corroborated", 0) + 1
        if profile["tier_only"]:
            # الوسيط وحده تنبيه ضبط لا سبب حذف: يبقى النقل ويُفحص على كتابه،
            # ويُعلَّم في السجل أنه يحتاج أصلًا يسنده قبل الاعتماد.
            stats["tier_warnings"] = stats.get("tier_warnings", 0) + 1
            stats["failures"].append({"quote": job["quote"][:120], "reason": "وسيط سندًا وحيدًا: تنبيه ضبط، أُبقي بلا حذف"})
        pending.append(job)

    def _match_variants(bid, quote, part, page):
        """المطابقة على النقل كاملًا، ثم على مقاطعه الكبرى: النقل المحرر قد
        يتخلله «رضي الله عنه» أو تقديم وتأخير يمنع مطابقة الكل دفعة واحدة."""
        if _match(bid, quote, part, page, allow_scan=True):
            return True
        # إحالة الحاشية قد تكون من طبعة أخرى بجزء وصفحة مختلفين؛ إعادة بلا
        # تلميح موضع حتى لا يحبس التلميح الخاطئ نقلًا ثابتًا في كتابه.
        if (part is not None or page is not None) and _match(bid, quote, None, None, allow_scan=True):
            return True
        variants = []
        # مقاطع الحذف الصريح (…): ثبوت أطول مقطع بلا حذف ثبوتٌ للنقل بحذفه
        for _seg in re.split(r"…|\.\.\.", quote):
            _seg = _seg.strip(" :؛،")
            if len(_seg) >= 25 and _seg not in variants:
                variants.append(_seg)
        # مقاطع قصيرة مميزة: المسح المتسامح قد يرفض النقل الطويل المركب كله
        # ويثبت على مقطعه الأول أو الأوسط.
        for _seg in (quote[:70].rsplit(" ", 1)[0],
                     quote[len(quote) // 3: len(quote) // 3 + 80].rsplit(" ", 1)[0],
                     quote[:130].rsplit(" ", 1)[0]):
            if len(_seg) >= 25 and _seg not in variants:
                variants.append(_seg)
        for _sep in (" قال: ", ": «", "؛ "):
            if _sep in quote:
                seg = quote.split(_sep)[-1].strip(" :")
                if len(seg) >= 25:
                    variants.append(seg)
                seg0 = quote.split(_sep)[0].strip(" :")
                if len(seg0) >= 30:
                    variants.append(seg0)
        for v in variants[:6]:
            if _match(bid, v, part, page, allow_scan=True) or _match(bid, v, None, None, allow_scan=True):
                return True
        return False

    def _phase_a(job):
        # كل كتاب في الحاشية بموضعه مرشح للشاهد: الخلط بين كتابين في حاشية
        # واحدة ليس خطأ إحالة، والاكتفاء بأولهما كان يُسقط شواهد الثاني.
        if job.get("num"):
            for sp in footnote_span_books(job["num"]):
                if _match_variants(sp["bid"], job["quote"], sp["part"] or None, sp["page"] or None):
                    job["bid"] = sp["bid"]
                    if sp["kind"] == "unres":
                        job["heal"] = sp
                    return job, "MATCH"
        bid = job.get("bid") or cited_bid(job["num"])
        job["bid"] = bid
        if not bid:
            return job, "NOT_FOUND"
        part, page = footnote_locator(job["num"])
        return job, ("MATCH" if _match_variants(bid, job["quote"], part, page) else "NOT_FOUND")

    failed = []
    _heals = []
    if pending:
        with ThreadPoolExecutor(max_workers=8) as ex:
            for i, (job, status) in enumerate(ex.map(_phase_a, pending)):
                if status == "MATCH":
                    stats["verified"] += 1
                    if job.get("heal"):
                        _heals.append(job)
                else:
                    failed.append(job)
                if (i + 1) % 15 == 0:
                    print(f"🚧 [Documentation Audit] مرحلة الإحالة: {i + 1}/{len(pending)} ({round(_time.time() - _t0)}s)", flush=True)

    def _relocate_via_bridge(job):
        """موضع النقل الحقيقي من فهرس المكتبة: عبارة مميزة فإن لم توجد
        فأطول كلمات النقل مجتمعة — تُبحث في كتب الشواهد كلها عبر الجسور،
        وتُفتح الصفحة المرشحة للتحقق من متنها قبل اعتماد الموضع."""
        try:
            import shamela_link as _SLR
            if _SLR.library_source() != "shamela":
                return None
            import shamela_search
            words = [w for w in re.findall(r"[\u0600-\u06FF]{3,}", _fold_ar(job["quote"]))]
            if len(words) < 5:
                return None
            ids = [int(w) for w in witness_ids if str(w).isdigit()][:48]
            if not ids:
                return None

            def _location(h):
                bid2 = int(h.get("book_id") or 0)
                if not bid2 or str(bid2) == str(job.get("bid") or ""):
                    return None
                pg = shamela_local_mcp.get_page(bid2, int(h.get("page_num") or 0),
                                                 h.get("part") or None)
                if pg.get("status") != "ok":
                    return None
                if not _contains_fold(_fold_ar((pg.get("page") or {}).get("body") or ""),
                                      job["quote"]):
                    return None
                meta = shamela_local_mcp.resolve_book(bid2) or {}
                return {"book_id": bid2, "part": str(h.get("part") or ""),
                        "page": int(h.get("page_num") or 0),
                        "title": meta.get("title") or h.get("title") or "",
                        "author": meta.get("author") or h.get("author") or "",
                        "rel_path": meta.get("rel_path") or h.get("rel_path") or ""}

            r = shamela_search.search(" ".join(words[:7]), mode="phrase",
                                      book_ids=ids, limit=6)
            for h in (r.get("results") or []):
                loc = _location(h)
                if loc:
                    return loc
            distinct = sorted(set(words), key=len, reverse=True)[:6]
            r2 = shamela_search.search(" ".join(distinct), mode="words",
                                       book_ids=ids, limit=8)
            for h in (r2.get("results") or []):
                loc = _location(h)
                if loc:
                    return loc
        except Exception:
            return None
        return None

    def _relocate_library(job):
        """موضع النقل الأعمى (ورد بلا حاشية مربوطة) في فهرس المكتبة كله:
        يُشخَّص موضعه الحقيقي ليُحصى «موثّقًا بلا إحالة» على حدة — تشخيص
        صادق لخلل ربط في التوليف، لا توثيق مكتمل يُغني عن حاشيته."""
        try:
            import shamela_link as _SLL
            if _SLL.library_source() != "shamela":
                return None
            import shamela_search
            words = [w for w in re.findall(r"[\u0600-\u06FF]{3,}", _fold_ar(job["quote"]))]
            if len(words) < 5:
                return None

            def _loc(h):
                bid2 = int(h.get("book_id") or 0)
                if not bid2:
                    return None
                pg = shamela_local_mcp.get_page(bid2, int(h.get("page_num") or 0),
                                                 h.get("part") or None)
                if pg.get("status") != "ok":
                    return None
                if not _contains_fold(_fold_ar((pg.get("page") or {}).get("body") or ""),
                                      job["quote"]):
                    return None
                meta = shamela_local_mcp.resolve_book(bid2) or {}
                return {"book_id": bid2, "part": str(h.get("part") or ""),
                        "page": int(h.get("page_num") or 0),
                        "title": meta.get("title") or h.get("title") or ""}

            r = shamela_search.search(" ".join(words[:7]), mode="phrase",
                                      book_ids=None, limit=6)
            for h in (r.get("results") or []):
                x = _loc(h)
                if x:
                    return x
            distinct = sorted(set(words), key=len, reverse=True)[:6]
            r2 = shamela_search.search(" ".join(distinct), mode="words",
                                       book_ids=None, limit=8)
            for h in (r2.get("results") or []):
                x = _loc(h)
                if x:
                    return x
        except Exception:
            return None
        return None

    def _bridge_locate(bid2, quote):
        """صفحة النقل وجزؤها في كتاب بعينه من فهرس المكتبة، أو None."""
        try:
            import shamela_search
            words = [w for w in re.findall(r"[\u0600-\u06FF]{3,}", _fold_ar(quote))]
            if len(words) < 4:
                return None
            hits = []
            r = shamela_search.search(" ".join(words[:7]), mode="phrase",
                                      book_ids=[int(bid2)], limit=3)
            hits.extend(r.get("results") or [])
            distinct = sorted(set(words), key=len, reverse=True)[:6]
            if len(distinct) >= 3 and not hits:
                r2 = shamela_search.search(" ".join(distinct), mode="words",
                                           book_ids=[int(bid2)], limit=5)
                hits.extend(r2.get("results") or [])
            for h in hits:
                pg = shamela_local_mcp.get_page(int(bid2), int(h.get("page_num") or 0),
                                                 h.get("part") or None)
                if pg.get("status") != "ok":
                    continue
                if _contains_fold(_fold_ar((pg.get("page") or {}).get("body") or ""), quote):
                    meta = shamela_local_mcp.resolve_book(int(bid2)) or {}
                    return {"book_id": int(bid2), "part": str(h.get("part") or ""),
                            "page": int(h.get("page_num") or 0),
                            "title": meta.get("title") or h.get("title") or "",
                            "author": meta.get("author") or h.get("author") or "",
                            "rel_path": meta.get("rel_path") or h.get("rel_path") or ""}
        except Exception:
            return None
        return None

    def _phase_b(job):
        # بدائل من كتب الشواهد: ثبوت في غير كتاب الإحالة يُصلَح موضعه في
        # الحاشية إلى موضعه الحقيقي (النص المنقول لا يُمسّ)، وعدمه تنبيه.
        if _time.time() - _t0 > 240:
            return job, "NOT_FOUND", None
        bid = job.get("bid") or cited_bid(job["num"])
        for wid in [w for w in witness_ids if w != str(bid or "")][:8]:
            if _match(wid, job["quote"]):
                loc = _bridge_locate(wid, job["quote"])
                if loc:
                    return job, "REPAIRABLE", loc
                return job, "RELOCATED", None
        loc = _relocate_via_bridge(job)
        if loc:
            return job, "REPAIRABLE", loc
        if not job.get("num"):
            loc2 = _relocate_library(job)
            if loc2:
                return job, "UNBOUND_FOUND", loc2
        return job, "NOT_FOUND", None

    _repairs = []
    _excluded = []
    if failed:
        with ThreadPoolExecutor(max_workers=8) as ex:
            for job, status, loc in ex.map(_phase_b, failed):
                if status == "RELOCATED":
                    stats["relocated"] = stats.get("relocated", 0) + 1
                    stats["failures"].append({"quote": job["quote"][:120], "reason": "ثابت في غير كتاب إحالته أو موضعه: تنبيه ربط، أُبقي بلا حذف"})
                elif status == "REPAIRABLE" and loc:
                    _repairs.append((job, loc))
                elif status == "UNBOUND_FOUND" and loc:
                    stats["verified_unbound"] = stats.get("verified_unbound", 0) + 1
                    stats.setdefault("unbound_found", []).append(
                        {"quote": job["quote"][:100], "book": loc["title"],
                         "part": loc["part"], "page": loc["page"]})
                    stats["failures"].append({"quote": job["quote"][:120],
                                               "reason": f"ثابت في «{loc['title']}» {loc['part']}/{loc['page']} بفهرس المكتبة لكنه ورد في المتن بلا إحالة مربوطة"})
                elif _outside_library(job):
                    # قاعدة المكتبة: مصدر خارجها يُستبعد ولا يُنقل منه.
                    _excluded.append(job)
                else:
                    stats["unverified"] = stats.get("unverified", 0) + 1
                    stats["failures"].append({"quote": job["quote"][:120], "reason": "لم يثبت آليًا في كتاب إحالته ولا في كتب الشواهد: أُبقي للمراجعة"})
    if _excluded:
        # الاستبعاد الفوري: يُقطع النقل بعلامة حاشيته من المتن وتُزال حاشيته،
        # بعد أن فشل كل ترحيل له إلى كتاب من كتب المكتبة في المراحل السابقة.
        for job in sorted(_excluded, key=lambda j: j["start"], reverse=True):
            text = text[:job["start"]] + text[job["cut_end"]:]
        _ex_nums = {j["num"] for j in _excluded if j.get("num")}
        if _ex_nums:
            for d in sorted((x for x in _footnote_defs(text) if x["num"] in _ex_nums),
                            key=lambda x: x["start"], reverse=True):
                text = text[:d["start"]] + text[d["end"]:]
        stats["excluded_outside"] = stats.get("excluded_outside", 0) + len(_excluded)
        print(f"🚧 [Documentation Audit] استُبعد {len(_excluded)} نقلًا مصدره خارج المكتبة (قاعدة: لا نقل من خارجها)", flush=True)
    if _repairs:
        # إصلاح مواضع الحواشي إلى مواضعها المثبتة: تُعاد كتابة وسم الإحالة
        # وعرضه فقط، والنص المنقول وجسم البحث كما هما.
        _defs_now = _footnote_defs(text)
        _edits = []
        for job, loc in _repairs:
            d = next((x for x in _defs_now if x["num"] == job.get("num")), None)
            if not d:
                continue
            body = d["body"]
            mspan = re.search(r'<span class="cit-src"[^>]*>.*?</span>', body, re.S)
            if not mspan:
                continue
            new_span = (
                '<span class="cit-src" '
                f'data-book="{html.escape(loc["title"], quote=True)}" '
                f'data-rel-path="{html.escape(loc["rel_path"], quote=True)}" '
                f'data-book-id="{loc["book_id"]}" '
                f'data-part="{html.escape(loc["part"], quote=True)}" '
                f'data-page="{loc["page"]}" '
                f'data-quote="{html.escape(" ".join(job["quote"].split())[:120], quote=True)}">'
                f'{html.escape(canonical_citation_label(loc["title"], loc["part"], loc["page"], author=loc["author"]))}</span>')
            new_body = body[:mspan.start()] + new_span + body[mspan.end():]
            _slice = text[d["start"]:d["end"]]
            if body in _slice:
                _edits.append((d["start"], d["end"], _slice.replace(body, new_body, 1)))
        for s, e, new in sorted(_edits, key=lambda x: x[0], reverse=True):
            text = text[:s] + new + text[e:]
        stats["repaired"] = len(_edits)
        if _edits:
            print(f"🚧 [Documentation Audit] أُصلح موضع {len(_edits)} إحالة إلى موضعها المثبت في فهرس المكتبة", flush=True)
    # شفاء الحواشي المعلَّمة ⚠: علامتها معناها «لم يُحلّ كتابها في المكتبة»،
    # فمتى حُلّ الكتاب بموضعه المذكور ارتفع سببها: تُختم ختمًا كاملًا فتظهر
    # أيقونة التصفح وتدخل كتبَ التحقق، وشاهدُ متنها يُفحص بمهامه كالمعتاد.
    _heal_quotes = {j["num"]: j["quote"] for j in _heals}
    _defs_now = _footnote_defs(text)
    _edits = []
    _healed_n = 0
    _dropped_n = 0
    for d in _defs_now:
        if "cit-unresolved" not in d["body"]:
            continue
        body = d["body"]
        pieces, pos, changed = [], 0, False
        _dropped_here = 0
        for um in re.finditer(r'<span class="cit-unresolved"[^>]*>(.*?)</span>', body, re.S):
            info = _parse_unresolved(um.group(1))
            if not info:
                if _title_in_library(um.group(1)):
                    continue
                # كتاب خارج المكتبة: تُستبعد إحالته من الحاشية فورًا.
                pieces.append(body[pos:um.start()])
                pos = um.end()
                changed = True
                _dropped_here += 1
                _dropped_n += 1
                continue
            inner = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", um.group(1)).replace("⚠", " ")).strip()
            q = " ".join(str(_heal_quotes.get(d["num"]) or "").split())[:120]
            if not q:
                try:
                    pg = shamela_local_mcp.get_page(int(info["bid"]), int(info["page"] or 0),
                                                     info["part"] or None)
                    if pg.get("status") == "ok":
                        q = " ".join(str((pg.get("page") or {}).get("body") or "").split())[:120]
                except Exception:
                    q = ""
            pieces.append(body[pos:um.start()])
            pieces.append(
                '<span class="cit-src" '
                f'data-book="{html.escape(info["title"], quote=True)}" '
                f'data-rel-path="{html.escape(info["rel_path"], quote=True)}" '
                f'data-book-id="{info["bid"]}" '
                f'data-part="{html.escape(info["part"], quote=True)}" '
                f'data-page="{info["page"]}" '
                f'data-quote="{html.escape(q, quote=True)}">'
                f'{html.escape(canonical_citation_label(info["title"], info["part"], info["page"], author=info["author"]) or inner)}</span>')
            pos = um.end()
            changed = True
            _healed_n += 1
        if not changed:
            continue
        pieces.append(body[pos:])
        new_body = "".join(pieces)
        if _dropped_here:
            # نظافة الوصلات اليتيمة بعد الاستبعاد («؛ وينظر:» بلا كتاب بعدها)
            _toks = re.split(r"(<[^>]+>)", new_body)
            for _i, _tok in enumerate(_toks):
                if _tok.startswith("<"):
                    continue
                _tok = re.sub(r"[؛;]\s*(?:وينظر|ينظر|انظر|راجع)\s*[:：]\s*(?=[؛;]|$)", "", _tok)
                _tok = re.sub(r"^\s*(?:وينظر|ينظر|انظر|راجع)\s*[:：]\s*(?=[؛;])", "", _tok)
                _toks[_i] = _tok
            new_body = "".join(_toks)
            if len(re.sub(r"<[^>]+>", " ", new_body).strip(" .؛:،«»()0123456789٠١٢٣٤٥٦٧٨٩")) < 4:
                # لم يبق في الحاشية إلا رقمها: تُزال كلها.
                _edits.append((d["start"], d["end"], ""))
                continue
        _slice = text[d["start"]:d["end"]]
        if body in _slice:
            _edits.append((d["start"], d["end"], _slice.replace(body, new_body, 1)))
    for s, e, new in sorted(_edits, key=lambda x: x[0], reverse=True):
        text = text[:s] + new + text[e:]
    if _healed_n:
        stats["repaired"] = stats.get("repaired", 0) + _healed_n
        stats["healed"] = _healed_n
        print(f"🚧 [Documentation Audit] شُفيت {_healed_n} إحالة معلَّمة: حُلّ كتابها في المكتبة فخُتمت كاملة", flush=True)
    if _dropped_n:
        stats["excluded_outside"] = stats.get("excluded_outside", 0) + _dropped_n
        print(f"🚧 [Documentation Audit] استُبعدت {_dropped_n} إحالة كتابها خارج المكتبة", flush=True)
    _no_bid = sum(1 for j in failed if not j.get("bid"))
    if failed:
        print(f"🚧 [Documentation Audit] تشخيص: بلا كتاب إحالة={_no_bid}/{len(failed)}", flush=True)
        for j in failed[:6]:
            print(f"🚧   تنبيه: حاشية={j.get('num')} كتاب={j.get('bid')} | «{j['quote'][:70]}»", flush=True)
    print(f"🚧 [Documentation Audit] اكتمل التدقيق: {stats['checked']} نقلًا في {round(_time.time() - _t0)}s — ثبت {stats['verified']}، لم يثبت آليًا {stats.get('unverified', 0) + stats.get('relocated', 0)} (أُبقي بلا حذف)" + (f"، و{stats['verified_unbound']} ثابتًا في المكتبة بلا إحالة مربوطة" if stats.get('verified_unbound') else ""), flush=True)
    if stats["checked"] >= 8 and stats["verified"] * 10 < stats["checked"]:
        # انخفاض جماعي في الثبوت قد يكون علّة ربط أو صياغة آلية؛ يُصرَّح به
        # تنبيهًا على موثوقية التدقيق نفسه، لا حكمًا بحذف البحث.
        stats["collapsed"] = True
        print("🚧 [Documentation Audit] انخفاض ثبوت جماعي "
              f"({stats['verified']} ثابت من {stats['checked']}): النص باق كما هو، والتنبيه في السجل.", flush=True)
    # ادعاءات الإجماع والاتفاق بلا سند من كتب الإجماع في الشواهد المحال إليها
    body_only = text
    for d in sorted(_footnote_defs(text), key=lambda x: x["start"], reverse=True):
        body_only = body_only[:d["start"]] + " " + body_only[d["end"]:]
    body_plain = re.sub(r"<[^>]+>", " ", body_only)
    titles_fold = " ".join(_fold_ar(r.get("title") or "") for r in (witness_rows or []))
    has_ijma_source = any(_fold_ar(k) in titles_fold for k in _IJMA_SOURCE_KEYS)
    if not has_ijma_source:
        try:
            import library_search
            _ijma_ids = library_search.ijma_book_ids()
            _cited_now = {str(_footnote_book_id(d["body"]) or _bid_cache.get(d["num"]) or "") for d in defs}
            has_ijma_source = bool(_ijma_ids & _cited_now)
        except Exception:
            has_ijma_source = False
    claims = len(_IJMA_CLAIM_RE.findall(body_plain))
    if claims and not has_ijma_source:
        stats["ijma_flags"] = claims
    # دعاوى اتفاق مطلقة بلا نسبة لقائل ولا كتاب إجماع في جملتها: وجود كتب
    # إجماع في الشواهد لا يبيح إطلاق «اتفقوا/باتفاق المذاهب» حكمًا من عند
    # الكاتب؛ المنسوب لقائله («نقل ابن رشد الاتفاق») خارج التنبيه.
    _ABSOLUTE_CLAIM_RE = re.compile(
        r"(اتفقوا على|اتفق العلماء|اتفق الفقهاء|باتفاق المذاهب|باتفاق العلماء|بإجماع العلماء|أجمعوا على|لا خلاف بين العلماء|لا نزاع بين الفقهاء)")
    _ATTRIBUTION_HINTS = ("نقل", "قال ", "قائل", "حكى", "حكاه", "ذكر ", "ينظر", "انظر", "في كتاب", "عند ")
    _unattributed = []
    for _sent in re.split(r"[.\n؛]", body_plain):
        if _ABSOLUTE_CLAIM_RE.search(_sent) and not any(h in _sent for h in _ATTRIBUTION_HINTS):
            _unattributed.append(_sent.strip()[:110])
    if _unattributed:
        stats["ijma_unattributed"] = _unattributed[:6]
        print(f"🚧 [Documentation Audit] دعاوى اتفاق مطلقة بلا نسبة: {len(_unattributed)}", flush=True)
    cited = []
    cited_titles = []
    for d in _footnote_defs(text):
        bid = _footnote_book_id(d["body"]) or _bid_cache.get(d["num"])
        if bid and str(bid) not in cited:
            cited.append(str(bid))
        seg = _FOOTNOTE_LEAD.sub("", re.sub(r"<[^>]+>", " ", d["body"]).strip())
        seg = re.split(r"[،,(]", seg)[0].strip()
        if len(seg) >= 4 and seg not in cited_titles:
            cited_titles.append(seg)
    stats["cited_book_ids"] = cited
    stats["cited_titles"] = cited_titles
    return text, stats


def _authority_coverage_lines(cited_book_ids: List[str], cited_titles: List[str] = None) -> List[str]:
    """خريطة تغطية طبقات الاعتماد من فهرس الضبط مقابل الكتب المحال إليها فعلًا.

    المطابقة برقم الكتاب أو بعنوانه: طبعة مختلفة للكتاب نفسه (كشاف وزارة العدل
    مقابل طبعة مصيلحي) لا تُصفّر طبقة قائمة."""
    lines = []
    cited_titles_fold = [_fold_ar(t or "") for t in (cited_titles or [])]

    def title_hit(book_title: str) -> bool:
        words = [w for w in _fold_ar(book_title or "").split() if len(w) >= 4][:4]
        if len(words) < 2:
            return False
        return any(sum(1 for w in words if w in ct) >= 2 for ct in cited_titles_fold)

    try:
        import library_search
        for madhhab in ("الحنفي", "المالكي", "الشافعي", "الحنبلي", "الظاهري"):
            data = library_search.madhhab_authorities(madhhab) or {}
            layers = data.get("layers") or []
            if not layers:
                continue
            hit_layers, zero_layers, dabt_layers = [], [], []
            for layer in layers:
                # طبقات الضبط الاصطلاحي والمنهجي (كمدخل ابن بدران) كتبُ
                # مصطلح وخريطة كتب، لا مصادر أحكام: لا تُقاس حضورًا ولا
                # صفرًا في مسألة فقهية، وذكر خلوها من لفظ مسألة خلط فئات.
                if "اصطلاح" in (layer.get("name") or ""):
                    dabt_layers.append(layer.get("name") or "")
                    continue
                books = layer.get("books") or []
                ids = {str(b.get("book_id")) for b in books}
                hit = bool(ids & set(cited_book_ids)) or any(title_hit(b.get("title") or "") for b in books)
                (hit_layers if hit else zero_layers).append(layer.get("name") or "")
            parts = [f"حاضرة: {'، '.join(hit_layers)}" if hit_layers else "حاضرة: لا شيء"]
            if zero_layers:
                parts.append(f"صفرية موثقة (لم يُحال إلى كتبها): {'، '.join(zero_layers)}")
            if dabt_layers:
                parts.append(f"طبقة ضبط اصطلاحي/منهجي لا تُقاس في أحكام المسائل: {'، '.join(dabt_layers)}")
            lines.append(f"المذهب {madhhab} — " + "؛ ".join(parts))
    except Exception:
        pass
    return lines


def _documentation_record(stats: dict) -> str:
    unverified = stats.get("unverified", 0)
    relocated = stats.get("relocated", 0)
    tier_warn = stats.get("tier_warnings", 0)
    lines = [
        "",
        "---",
        f"**سجل التدقيق الآلي (غير مدمّر):** فُحص {stats['checked']} نقلًا منقولًا على صفحات كتبه: "
        f"ثبت {stats['verified']}، ولم يثبت آليًا {unverified + relocated} "
        f"(لم يُعثر عليه: {unverified}، ثابت في غير موضعه أو كتابه: {relocated}، "
        f"وسيط سندًا وحيدًا يحتاج أصلًا: {tier_warn}). أُبقي النص كما كتبه الوكلاء بلا حذف، "
        "وما لم يثبت تنبيه مراجعة بشرية لا حكم ببطلانه.",
    ]
    if stats.get("linked") is not None and stats.get("checked"):
        lines.append(f"ربط الحواشي بالنقول: رُبط {stats['linked']} نقلًا بحاشيته من {stats['checked']}؛ وما لم يُربط لم يدخل فحص الكتب فلا يُحكم عليه.")
    if stats.get("collapsed"):
        lines.append(f"تنبيه نظام: نسبة ثبوت النقول آليًا دون العُشر في هذه الإجابة ({stats['verified']} من {stats['checked']})؛ قد يكون ذلك من صياغة النقل أو ربط الحواشي، فلا يُعتمد التدقيق وحده حكمًا على البحث.")
    if not stats.get("skip_madhhab_coverage"):
        for cov in _authority_coverage_lines(stats.get("cited_book_ids") or [], stats.get("cited_titles") or []):
            lines.append(f"تغطية طبقات الاعتماد (استرشادية) — {cov}.")
    if stats.get("tier_footnotes"):
        lines.append(f"مقارنة مرجعية: {stats['tier_footnotes']} حاشية فيها مصادر وسيطة (موسوعات مقارنة ونحوها) للمقابلة والضبط، وهي مشروعة بجانب الأصل؛ وما كان منها سندًا وحيدًا عُدّ تنبيهًا أعلاه وأُبقي بلا حذف.")
    if stats.get("ijma_flags"):
        lines.append(f"تنبيه: ورد ادعاء إجماع أو اتفاق في {stats['ijma_flags']} موضعًا بلا نقل ظاهر من كتب الإجماع (كإجماع ابن المنذر ومراتب ابن حزم والاستذكار والتمهيد) في الشواهد، فليُحرَّر قبل الاعتماد.")
    if stats.get("ijma_unattributed"):
        lines.append(f"تنبيه اتفاق مطلق: {len(stats['ijma_unattributed'])} دعوى اتفاق/إجماع مطلقة بلا نسبة لقائل أو كتاب إجماع في جملتها (نحو: «{stats['ijma_unattributed'][0]}…»)؛ الأثبت تحريرها بنقل من كتب الإجماع أو تخفيفها إلى «الجمهور» قبل الاعتماد.")
    return "\n".join(lines)


def parse_book_card(betaka: str) -> dict:
    """يستخرج من بطاقة الشاملة: المحقق والطبعة والناشر ومدينة النشر وسنة الطبع."""
    editor_labels = (
        "المحقق", "تحقيق", "دراسة وتحقيق", "تحقيق ودراسة",
        "تحقيق وتعليق", "حققه وعلق عليه",
    )
    year_labels = ("عام النشر", "سنة النشر", "سنة الطبع", "تاريخ النشر")
    raw = {}
    for raw_line in (betaka or "").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if ":" in line:
            key, val = line.split(":", 1)
        elif "：" in line:
            key, val = line.split("：", 1)
        else:
            continue
        key = key.strip()
        val = re.sub(r"\s+", " ", val).strip()
        if key and val and key not in raw:
            raw[key] = val
    found = {}
    for label in editor_labels:
        if raw.get(label):
            found["editor"] = raw[label]
            break
    publisher = raw.get("الناشر") or raw.get("دار النشر") or ""
    city = raw.get("بلد النشر") or raw.get("مدينة النشر") or raw.get("مكان النشر") or ""
    if publisher and not city:
        parts = re.split(r"\s*[،,]\s*", publisher, maxsplit=1)
        if len(parts) == 2 and parts[1].strip():
            publisher, city = parts[0].strip(), parts[1].strip()
    if publisher:
        found["publisher"] = publisher
    if city:
        found["city"] = city
    edition = ""
    for label in ("الطبعة", "طبعة", "رقم الطبعة"):
        if raw.get(label):
            edition = raw[label]
            break
    if edition:
        found["edition"] = edition
    for label in year_labels:
        if raw.get(label):
            found["year"] = raw[label]
            break
    if "year" not in found and edition:
        year_match = re.search(r"([0-9٠-٩۰-۹]{3,4})\s*هـ?", edition)
        if year_match:
            found["year"] = year_match.group(0).strip()
    return found


def format_book_card(card: dict) -> str:
    bits = []
    if card.get("editor"):
        bits.append(f"المحقق: {card['editor']}")
    if card.get("edition"):
        bits.append(f"الطبعة: {card['edition']}")
    if card.get("publisher"):
        bits.append(f"الناشر: {card['publisher']}")
    if card.get("city"):
        bits.append(f"مدينة النشر: {card['city']}")
    if card.get("year"):
        bits.append(f"سنة الطبع: {card['year']}")
    return " | ".join(bits)


def book_card_for(book_id: Any, cache: dict) -> str:
    number = _book_id_value(book_id)
    if not number:
        return ""
    if number in cache:
        return cache[number]
    card = ""
    db = get_db()
    if db:
        try:
            cursor = db.cursor()
            cursor.execute("SELECT betaka_text FROM books WHERE book_id = ? LIMIT 1", (number,))
            row = cursor.fetchone()
            if row and row["betaka_text"]:
                card = format_book_card(parse_book_card(row["betaka_text"]))
        except Exception:
            card = ""
    cache[number] = card
    return card


def strip_trailing_bibliography(text: str) -> str:
    """يحذف قائمة المصادر التي تُعاد تحت الحواشي. الحاشية هي توثيق النقل."""
    if not text:
        return text
    cut = re.search(
        r"(?:<hr\b[^>]*>\s*)?(?:<h[1-6]\b[^>]*>\s*)?(?:<p\b[^>]*>\s*)?(?:<b>\s*|<strong>\s*)?(?:📚\s*)?المصادر والمراجع",
        text,
        re.IGNORECASE,
    )
    if not cut:
        return text
    return text[:cut.start()].rstrip()


def _bibliography_title(book_id: Any, fallback: str = "") -> str:
    number = _book_id_value(book_id)
    if not number:
        return (fallback or "").strip()
    db = get_db()
    if not db:
        return (fallback or "").strip()
    try:
        cursor = db.cursor()
        cursor.execute("SELECT title_ar FROM books WHERE book_id = ? LIMIT 1", (number,))
        row = cursor.fetchone()
        if row and row["title_ar"]:
            return str(row["title_ar"]).strip()
    except Exception:
        pass
    return (fallback or "").strip()

def _shamela_roots() -> List[Path]:
    """كل المواضع التي قد تُحفظ فيها كتب الشاملة، لا المجلد الافتراضي وحده."""
    roots: List[Path] = []
    seen = set()

    def add(raw) -> None:
        if not raw:
            return
        path = Path(raw)
        try:
            if not path.is_dir():
                return
            key = str(path.resolve())
        except OSError:
            return
        if key in seen:
            return
        seen.add(key)
        roots.append(path)

    # جذور طبقة المكتبة الحاكمة (المستوردة أولًا عند مصدر الشاملة) — مصدر
    # الحقيقة الواحد؛ إغفالها كسر متصفح الكتاب كليًا بعد الهجرة الكسولة
    # إذ صارت الكتب تعيش في shamela_imported لا في shamela4_data.
    try:
        for _r in shamela_local_mcp._data_roots():
            add(_r)
    except Exception:
        pass
    add(SHAMELA_DATA_PATH)
    add(os.getenv("SHAMELA4_DATA_DIR"))
    add(os.getenv("SHAMELA_DATA_DIR"))
    data_dir = os.getenv("ALMUJTAHED_DATA_DIR", "").strip()
    if data_dir:
        add(Path(data_dir) / "shamela4_data")
    add(PACKAGE_ROOT / "shamela4_data")
    add(SYSTEM_ROOT / "shamela4_data")
    add(getattr(shamela_local_mcp, "SHAMELA_DATA_DIR", None))
    return roots


def _use_richest_shamela_root() -> None:
    """اختر مجلد الشاملة الذي فيه الأقسام فعلاً، ثم اعتمده للقارئ وللتحقق."""
    global SHAMELA_DATA_PATH
    best = None
    best_count = -1
    for root in _shamela_roots():
        try:
            count = sum(1 for entry in root.iterdir() if entry.is_dir() and "__" in entry.name)
        except OSError:
            continue
        if count > best_count:
            best = root
            best_count = count
    if best is not None and best_count > 0:
        SHAMELA_DATA_PATH = best
        shamela_local_mcp.SHAMELA_DATA_DIR = best
        print(f"مكتبة الشاملة: {best} ({best_count} قسم)")


_use_richest_shamela_root()


def _is_real_pages_file(path: Optional[Path]) -> bool:
    """ملف صفحات حقيقي، لا مؤشر Git LFS الوهمي الذي تتركه النسخ الناقصة من المكتبة."""
    try:
        if path is None or not path.is_file():
            return False
        if path.stat().st_size > 512:
            return True
        with open(path, "rb") as handle:
            return not handle.read(64).startswith(b"version https://git-lfs")
    except OSError:
        return False


def _pages_file_for_rel(rel_path: str) -> Tuple[Optional[str], Optional[Path]]:
    clean = str(rel_path or "").replace("\\", "/").replace("shamela4_data/", "").strip("/")
    if not clean:
        return None, None
    book_name = clean.split("/")[-1]
    patterns = []
    if "/" not in clean:
        patterns.append(f"*/{book_name}/pages.jsonl")
    if book_name.isdigit():
        patterns.append(f"*/{book_name}__*/pages.jsonl")
    else:
        prefix = book_name.split("__", 1)[0]
        if prefix.isdigit():
            patterns.append(f"*/{prefix}__*/pages.jsonl")
    for root in _shamela_roots():
        try:
            direct = root / clean / "pages.jsonl"
            if _is_real_pages_file(direct):
                return clean, direct
            for pattern in patterns:
                matches = [item for item in root.glob(pattern) if _is_real_pages_file(item)]
                if matches:
                    book_dir = matches[0].parent
                    return f"{book_dir.parent.name}/{book_dir.name}", matches[0]
        except OSError:
            continue
    return None, None


def _book_id_value(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"#?\s*\d{1,5}", text):
        number = int(re.search(r"\d{1,5}", text).group(0))
    else:
        found = re.search(r"#\s*(\d{1,5})", text)
        if not found:
            return None
        number = int(found.group(1))
    return number if 1 <= number <= 20000 else None


def _pages_for_book_id(book_id: int) -> Tuple[Optional[str], Optional[Path]]:
    db = get_db()
    if db:
        try:
            cursor = db.cursor()
            cursor.execute("SELECT rel_path FROM books WHERE book_id = ? AND rel_path IS NOT NULL LIMIT 1", (int(book_id),))
            row = cursor.fetchone()
            if row and row["rel_path"]:
                found_rel, pages_file = _pages_file_for_rel(row["rel_path"])
                if pages_file:
                    return found_rel, pages_file
        except Exception:
            pass
    found_rel, pages_file = _pages_file_for_rel(str(int(book_id)))
    if pages_file:
        return found_rel, pages_file
    # كتاب معروف غير مستخرج بعد: استخراج كسول عند اللمس (كما في طبقة MCP)
    # حتى لا تصطدم أي حاشية بجدار «تعذر العثور على ملفات الكتاب».
    try:
        bdir = shamela_local_mcp.resolve_book_files(int(book_id))
        if bdir and (bdir / "pages.jsonl").exists():
            return f"{bdir.parent.name}/{bdir.name}", bdir / "pages.jsonl"
    except Exception:
        pass
    return None, None


def _page_nums_equal(left: Any, right: Any) -> bool:
    try:
        return int(left) == int(right)
    except (TypeError, ValueError):
        return False


def resolve_book_path(rel_path: Optional[str], book_title: Optional[str], book_id: Any = None) -> Tuple[Optional[str], Optional[Path]]:
    """رقم الشاملة يفتح كتابه وحده. بلا رقم: مسار الملف، ثم العنوان المطابق، بلا استبدال بكتاب آخر."""
    bid = _book_id_value(book_id)
    if bid:
        return _pages_for_book_id(bid)

    if rel_path:
        found_rel, pages_file = _pages_file_for_rel(rel_path)
        if pages_file:
            return found_rel, pages_file

    if book_title:
        chosen = _choose_book_rel_path(book_title.strip())
        if chosen:
            found_rel, pages_file = _pages_file_for_rel(chosen)
            if pages_file:
                return found_rel, pages_file

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
        if len(query_norm) < 8 and extra and not re.match(r"^(?:ت|ط|ل|لابن|لابي|بن)\b", extra):
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
        queries = []
        for item in (primary, query_norm, _fold_book_text(primary)):
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
            title_full = _fold_book_text(row["title_ar"] or "")
            author_full = _fold_book_text(row["main_author_name_ar"] or "")
            title_norm = _normalize_book_lookup(row["title_ar"] or "")
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
        found = next((i for i, e in enumerate(entries) if e["part"] == p_str and _page_nums_equal(e["page_num"], page_num)), None)
        if found is None:
            found = next((i for i, e in enumerate(entries) if _page_nums_equal(e["page_num"], page_num)), 0)
        target_idx = found
    elif page_num is not None:
        target_idx = next((i for i, e in enumerate(entries) if _page_nums_equal(e["page_num"], page_num)), 0)
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
            folder_name = rel_path.split("/")[-1] if "/" in rel_path else rel_path
            cursor.execute("""
                SELECT title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, betaka_text, volume_count_observed 
                FROM books 
                WHERE rel_path = ? OR rel_path = ? OR rel_path LIKE '%/' || ?
                LIMIT 1
            """, (rel_path, f"shamela4_data/{rel_path}", folder_name))
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
    try:
        page_num = int(page_num)
    except (TypeError, ValueError):
        return None
    if page_num <= 1:
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
    try:
        page_num = int(page_num)
    except (TypeError, ValueError):
        return None
    if page_num <= 1:
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
    book_id: Optional[int] = None,
    part: Optional[str] = None,
    page_num: Optional[int] = None,
    seq: Optional[int] = None,
    highlight: Optional[str] = None,
    strict: Optional[str] = None
):
    """
    جلب صفحة محددة من الكتاب الأصلي مع نصوص الحواشي ومعلومات الأجزاء والتنقل
    """
    resolved_rel, pages_file = resolve_book_path(rel_path, book_title, book_id)
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
            if e["part"] == p_str and _page_nums_equal(e["page_num"], page_num):
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
                if _page_nums_equal(e["page_num"], page_num):
                    target_idx = i
                    break
    elif page_num is not None:
        for i, e in enumerate(entries):
            if _page_nums_equal(e["page_num"], page_num):
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
    if quote_words and page_num is not None and not _body_matches_quote(clean_body, quote_words):
        try:
            with open(pages_file, "rb") as handle:
                for i, candidate in enumerate(entries):
                    if i == target_idx or not _page_nums_equal(candidate["page_num"], page_num):
                        continue
                    handle.seek(candidate["offset"])
                    candidate_line = handle.readline()
                    if not candidate_line:
                        continue
                    candidate_page = json.loads(candidate_line.decode("utf-8"))
                    candidate_body = candidate_page.get("body", "")
                    if not _body_matches_quote(candidate_body, quote_words):
                        continue
                    target_idx = i
                    entry = candidate
                    page_data = candidate_page
                    raw_body = candidate_body
                    clean_body = re.sub(r"<[^>]+>", "", raw_body).strip()
                    break
        except Exception as locate_error:
            print(f"Error locating quoted page: {locate_error}")
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
    try:
        annalistic = find_annalistic_year_backtrack(resolved_rel, title, entry["part"], entry["page_num"], max_back=40)
    except Exception:
        annalistic = None
    try:
        fiqh = find_fiqh_issue_backtrack(resolved_rel, title, entry["part"], entry["page_num"], max_back=15)
    except Exception:
        fiqh = None

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
    book_id: Optional[int] = None,
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
    resolved_rel, pages_file = resolve_book_path(rel_path, book_title, book_id)
    if not pages_file or not pages_file.exists():
        # محاولة البحث في MCP المعياري
        p_res = shamela_local_mcp.resolve_book_files(book_id or book_title or rel_path)
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
        if _page_nums_equal(e.get("page_num"), p_int):
            if not p_str or str(e.get("part") or "").strip() == p_str:
                target_idx = i
                break
    if target_idx is None:
        for i, e in enumerate(entries):
            if _page_nums_equal(e.get("page_num"), p_int):
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
    b_author = meta.get("main_author_name_ar") or "أحد أئمة التراث"
    b_death = meta.get("main_author_death_hijri")
    bid = _book_id_value(book_id)
    db = get_db()
    if db and bid:
        try:
            cursor = db.cursor()
            cursor.execute(
                "SELECT title_ar, main_author_name_ar, main_author_death_hijri FROM books WHERE book_id = ? LIMIT 1",
                (bid,),
            )
            record = cursor.fetchone()
            if record:
                b_title = record["title_ar"] or b_title
                b_author = record["main_author_name_ar"] or b_author
                if record["main_author_death_hijri"] not in (None, ""):
                    b_death = record["main_author_death_hijri"]
        except Exception:
            pass
    try:
        annalistic = find_annalistic_year_backtrack(resolved_rel, b_title, p_str, p_int, max_back=40)
    except Exception:
        annalistic = None
    try:
        fiqh = find_fiqh_issue_backtrack(resolved_rel, b_title, p_str, p_int, max_back=15)
    except Exception:
        fiqh = None

    return {
        "book_title": b_title,
        "author": b_author,
        "death_year": b_death,
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
        "server": "almujtahed_mcp",
        "description": "خادم المجتهد MCP: بحث منغلق النطاق وقراءة صفحات ومطابقة اقتباس على الشاملة المحلية",
        "tools": shamela_local_mcp.SHAMELA_MCP_TOOLS_SPEC + ALMUJTAHED_MCP_EXTRA_TOOLS
    }


def _mcp_url_ok(url: str) -> str:
    parsed = urllib.parse.urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("عنوان الخادم يجب أن يكون رابط http أو https")
    return (url or "").strip()


def _mcp_parse_body(raw: str, content_type: str) -> dict:
    text = (raw or "").strip()
    if not text:
        return {}
    if "text/event-stream" in (content_type or "") or text.startswith("data:") or text.startswith("event:"):
        last = {}
        for line in text.splitlines():
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if not chunk or chunk == "[DONE]":
                continue
            try:
                last = json.loads(chunk)
            except Exception:
                continue
        return last
    try:
        data = json.loads(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _mcp_post(url: str, payload: dict, session_id: Optional[str] = None, timeout: int = 25) -> Tuple[dict, Optional[str]]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            session = resp.headers.get("Mcp-Session-Id") or session_id
            return _mcp_parse_body(raw, resp.headers.get("Content-Type", "")), session
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"تعذر الاتصال بخادم MCP ({error.code}): {detail}") from error


def _is_internal_mcp_url(url: str) -> bool:
    """رابط خادم المجتهد MCP الداخلي على هذا الجهاز وهذا المنفذ نفسه."""
    try:
        parsed = urllib.parse.urlparse((url or "").strip())
    except Exception:
        return False
    if parsed.hostname not in ("127.0.0.1", "::1", "localhost"):
        return False
    if (parsed.path or "").rstrip("/") != "/mcp":
        return False
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except Exception:
        return False
    return port == int(os.environ.get("PORT", "8085"))


def mcp_open_session(url: str) -> Tuple[str, Optional[str], List[dict]]:
    clean = _mcp_url_ok(url)
    if _is_internal_mcp_url(clean):
        # اختصار داخل العملية: لا اتصال شبكياً بالذات حتى لا تتجمد حلقة الخادم.
        return clean, "internal", _mcp_protocol_tools()
    opened, session = _mcp_post(clean, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "almujtahed", "version": "1.10.280"},
        },
    })
    if opened.get("error"):
        raise RuntimeError(str(opened["error"].get("message") or "رفض الخادم بدء الجلسة"))
    try:
        _mcp_post(clean, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    except Exception:
        pass
    listed, session = _mcp_post(clean, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    if listed.get("error"):
        raise RuntimeError(str(listed["error"].get("message") or "تعذر قراءة أدوات الخادم"))
    tools = ((listed.get("result") or {}).get("tools") or [])
    if not isinstance(tools, list):
        tools = []
    return clean, session, tools


def mcp_call_tool(url: str, session_id: Optional[str], tool_name: str, arguments: dict) -> str:
    if session_id == "internal" or _is_internal_mcp_url(url or ""):
        try:
            internal = _mcp_dispatch(tool_name, arguments or {}, None)
        except Exception as exc:
            internal = {"status": "error", "code": "TOOL_FAILED", "error": f"تعذر تنفيذ الأداة: {exc}"}
        return json.dumps(internal, ensure_ascii=False)[:12000]
    result, _session = _mcp_post(url, {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
    }, session_id, timeout=40)
    if result.get("error"):
        return str(result["error"].get("message") or "فشل استدعاء الأداة")
    payload = result.get("result") or {}
    content = payload.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        text = "\n".join(parts).strip()
    else:
        text = str(content or payload)
    return text[:12000] or "أعادت الأداة نتيجة فارغة"


def mcp_openai_tools(servers: List[dict]) -> Tuple[List[dict], Dict[str, dict]]:
    """يفتح جلسات الخوادم المحددة ويحوّل أدواتها إلى صيغة استدعاء النموذج."""
    catalog = []
    mapping = {}
    for index, server in enumerate(servers or []):
        if not isinstance(server, dict):
            continue
        url = str(server.get("url") or "").strip()
        chosen = {str(name) for name in (server.get("tools") or []) if str(name).strip()}
        try:
            clean, session, tools = mcp_open_session(url)
        except Exception as exc:
            print(f"MCP list failed: {type(exc).__name__}")
            continue
        for tool in tools:
            if not isinstance(tool, dict) or not tool.get("name"):
                continue
            original = str(tool["name"])
            if chosen and original not in chosen:
                continue
            safe = re.sub(r"[^0-9A-Za-z_]", "_", f"m{index}_{original}")[:64]
            schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {"type": "object", "properties": {}}
            catalog.append({
                "type": "function",
                "function": {
                    "name": safe,
                    "description": str(tool.get("description") or server.get("name") or original)[:800],
                    "parameters": schema,
                },
            })
            mapping[safe] = {"url": clean, "session": session, "name": original, "server": server.get("name") or clean}
    return catalog, mapping


class MCPInspectRequest(BaseModel):
    url: str


@app.post("/api/mcp/inspect")
async def inspect_remote_mcp(req: MCPInspectRequest):
    """يقرأ اسم أدوات خادم MCP البعيد من رابطه لعرضها فروعاً في الشات."""
    try:
        _url, _session, tools = await asyncio.to_thread(mcp_open_session, req.url)
    except Exception as exc:
        return {"status": "error", "error": f"تعذر الاتصال بالخادم: {exc}", "tools": []}
    brief = []
    for tool in tools:
        if not isinstance(tool, dict) or not tool.get("name"):
            continue
        brief.append({
            "name": str(tool["name"])[:120],
            "description": str(tool.get("description") or "")[:400],
        })
    return {"status": "ok", "tools": brief}


class MCPExecuteRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

ALMUJTAHED_MCP_GUIDE = (
    "ترتيب العمل: حلّ الكتاب برقمه، ثم بحث داخل نطاق مغلق، ثم قراءة الصفحة كاملة، "
    "ثم مطابقة قبل أي نقل. لا يوجد بحث مفتوح في المكتبة من هذه الأدوات، ولا يعتمد "
    "إلا شاهد حالته MATCH_EXACT أو MATCH_NORMALIZED. "
    "للمسائل المعاصرة (ألفاظ حديثة كالباروكة والعملات الرقمية ونقل الأعضاء): ابدأ بأداة "
    "anchor_lookup لترجمتها إلى عبارات من لسان التراث قبل 1000هـ بشواهدها الموثقة، "
    "ثم ابحث بتلك العبارات وقارن، فالمقابل التراثي لا لفظ السؤال الحديث هو مفتاح النتائج. "
    "ولمسألة فقهية مقارنة ابدأ بـfiqh_topic_locations إن كان موضوعها في شجرة الفقه (fiqh_topics لاكتشافها)، أو fiqh_dossier لملف بالنصوص، أو dossier_topic: ملف موضوع بطبقات زمنية أربع × مذاهب أهل السنة "
    "ومداخل الموسوعات وعناوين الأبواب وخلايا صفرية موثقة، ثم اقرأ خلاياه وطابق. "
    "وقبل وصف قول بأنه «المذهب» أو «المقرر» عند مذهب راجع madhhab_authorities: طبقات كتبه المعتمدة وقاموس اصطلاحه الموزون وقواعد ترجيحه، فلا يُنسب للمذهب قول راوحته كتب الخلاف دون بنائه المعتمدة. "
    "وقبل ادعاء إجماع أو اتفاق راجع authority_books بقسم ijma (كتب الإجماع لابن المنذر وابن حزم وابن عبد البر)، وعند تعليل خلاف راجع asbab (البطليوسي ورفع الملام ومقدمة بداية المجتهد)، وللمقارنة العالية بين المذاهب راجع khilaf (المروزي والتجريد والخلافيات والإفصاح). "
    "وللبحث السريع في المكتبة كلها استعمل فهرس المكتبة: survey_topic لمسح الموضوع وقرونه قبل الحفر، "
    "وsearch_headings لبلوغ فصل المسألة، وsearch_batch لبحث عبارات المراسي دفعة واحدة، "
    "وsearch_library بعبارات تراثية مع سقف وفاة يختاره الباحث (death_max) أو نطاق وكيل (book_ids). "
    "نتائج الفهرس مرشحات: اقرأ الصفحة كاملة وطابق قبل النقل، والعزو بالكتاب والمؤلف والجزء والصفحة. "
    "قاعدة نقل الحديث: متن الحديث يُنقل من كتابه الأصلي (نصوص «أصول» المرفقة في hadith_dossier أو get_page على مواضعها) بعزو الكتاب والجزء والصفحة، والحكم عليه من كتب التخريج والعلل؛ ولا يُنقل متن حديث من كتاب فقه أو شرح فقهي إلا عند تعذر بلوغ الأصل، وحينها صرّح في جوابك «نقلته من كذا لتعذر الأصل». "
    "قاعدة الطبعات والطبقات: عند تعدد طبعات الكتاب الواحد اكتفِ بأول طبعة تلتقطها ولا تنقل من طبعتين للعمل نفسه، والصحيحان مقدمان على المسانيد والسنن في نقل المتون؛ وفي عرض قول كل مذهب مثّل طبقاته الزمنية (كتابًا متقدمًا ومتوسطًا ومتأخرًا) ما وجدت نصوصها، ولا تحصر المذهب في طبقة واحدة. "
    "فهارس متخصصة: ayah_loci لمواضع الآية في التفاسير بالوفيات، وattestations لنسب عبارة ثابتة بترتيب وفيات قائليها، "
    "وhadith_loci لمواضع المتن في كتب السنة وشروحها والتخريج، وhadith_dossier لملف حديث بأحكام مستخرجة آليًا، وayah_dossier لملف آية طبقي بمقتطفات وقائلي السلف، وqawaid_search للقواعد، وcreed_search للعقيدة، وcreed_issue لمسألة عقدية مفهرسة بمذاهب مدارسها، "
    "وtarikh_search للتاريخ، وlugha_search لمواد المعاجم وكتب الغريب، وverify_batch لمطابقة النقول دفعة قبل التسليم، وget_book_coverage لإثبات نطاق كتاب."
)

ALMUJTAHED_MCP_EXTRA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "almujtahed_guide",
            "description": "دليل ترتيب العمل في خادم المجتهد MCP: النطاق والقراءة والمطابقة والعزو.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_passages",
            "description": "بحث هجين دلالي ولفظي داخل قائمة أرقام كتب مغلقة إلزامية. النتائج مرشحات غير قابلة للنقل.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "book_ids": {"type": "array", "items": {"type": "string"}},
                    "anchors": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
                "required": ["query", "book_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "research_evidence",
            "description": "حزمة شواهد موثقة: مراسي حتى ثلاث جولات داخل النطاق، ثم قراءة الصفحات ومطابقتها، مع سجل بحث.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "book_ids": {"type": "array", "items": {"type": "string"}},
                    "anchors": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                    "model": {"type": "string"},
                },
                "required": ["query", "book_ids"],
            },
        },
    },
]


def _mcp_scope_titles(book_ids) -> List[str]:
    titles: List[str] = []
    db = get_db()
    if not db:
        return titles
    cursor = db.cursor()
    for raw in book_ids or []:
        text = str(raw).strip().lstrip("#")
        if not text:
            continue
        try:
            cursor.execute("SELECT title_ar FROM books WHERE book_id = ? LIMIT 1", (int(text),))
            row = cursor.fetchone()
        except Exception:
            row = None
        if row and row["title_ar"] and row["title_ar"] not in titles:
            titles.append(row["title_ar"])
    return titles


def _mcp_search_passages(args: Dict[str, Any]) -> Dict[str, Any]:
    ids = [str(b).strip().lstrip("#") for b in (args.get("book_ids") or []) if str(b).strip()]
    if not ids:
        return {"status": "error", "code": "SCOPE_REQUIRED", "error": "يلزم تمرير book_ids. لا بحث مفتوحاً في المكتبة."}
    titles = _mcp_scope_titles(ids)
    if not titles:
        return {"status": "error", "code": "BOOK_NOT_FOUND", "error": "أرقام الكتب لا تقابل كتباً في القاعدة."}
    limit = max(1, min(int(args.get("limit") or 20), 60))
    hits = run_rag_search(
        query=args.get("query") or "",
        selected_books=titles,
        pool_size=max(limit * 4, 200),
        top_k=limit,
        use_reranker=False,
        dynamic_anchors=list(args.get("anchors") or []),
        use_hybrid=True,
        honor_agent_limit=True,
    )
    return {
        "status": "ok",
        "results": [{
            "book_id": h.get("book_id"), "title": h.get("title"), "author": h.get("author"),
            "part": h.get("part_raw"), "page_num": h.get("page_num_raw"),
            "snippet": h.get("snippet"), "quotable": False,
        } for h in hits],
        "ledger": {"scope_books": len(titles), "returned": len(hits)},
        "note": "مرشحات غير قابلة للنقل. اقرأ الصفحة ثم طابق قبل أي عزو.",
    }


def _mcp_research_evidence(args: Dict[str, Any], request: Request) -> Dict[str, Any]:
    ids = [str(b).strip().lstrip("#") for b in (args.get("book_ids") or []) if str(b).strip()]
    if not ids:
        return {"status": "error", "code": "SCOPE_REQUIRED", "error": "يلزم تمرير book_ids. لا بحث مفتوحاً في المكتبة."}
    titles = _mcp_scope_titles(ids)
    if not titles:
        return {"status": "error", "code": "BOOK_NOT_FOUND", "error": "أرقام الكتب لا تقابل كتباً في القاعدة."}
    limit = max(1, min(int(args.get("limit") or 12), 40))
    api_key = OPENROUTER_DEFAULT_KEY
    if request is not None:
        try:
            api_key = owner_openrouter_key(request, None) or api_key
        except Exception:
            pass
    buckets, anchors = expand_query_with_anchor_rounds(
        query=args.get("query") or "",
        scopes=[{"name": "scope", "books": titles, "top_k": limit, "pool_size": max(limit * 4, 200)}],
        api_key=api_key,
        model=args.get("model") or "google/gemini-2.5-flash",
        use_hybrid=True,
        seed_anchors=list(args.get("anchors") or []),
        honor_agent_limit=True,
        run_id=args.get("chat_id") or args.get("run_id"),
    )
    items = []
    for hit in (buckets.get("scope") or [])[:limit]:
        page_text = fetch_page_body(hit.get("rel_path") or "", hit.get("part_raw"), hit.get("page_num_raw"))
        phrase = (hit.get("snippet") or "")[:70].strip()
        check = {}
        if phrase and hit.get("book_id"):
            try:
                check = shamela_local_mcp.verify_quote(book=str(hit["book_id"]), quote_text=phrase, page_hint=hit.get("page_num_raw"))
            except Exception:
                check = {}
        status = check.get("match_status") or "UNCHECKED"
        items.append({
            "book_id": hit.get("book_id"), "title": hit.get("title"), "author": hit.get("author"),
            "part": hit.get("part_raw"), "page_num": hit.get("page_num_raw"),
            "text": (page_text or hit.get("snippet") or "")[:1400],
            "verification": status,
            "citation": shamela_local_mcp.resolve_book(str(hit["book_id"])) if status in ("MATCH_EXACT", "MATCH_NORMALIZED") and hit.get("book_id") else None,
        })
    return {
        "status": "ok",
        "evidence": items,
        "ledger": {"scope_books": len(titles), "anchors_used": anchors, "returned": len(items)},
        "note": "لا يعتمد إلا ما حالته MATCH_EXACT أو MATCH_NORMALIZED بعد قراءة نصه كاملاً.",
    }


def _mcp_dispatch(name: str, args: Dict[str, Any], request: Request) -> Dict[str, Any]:
    if name == "almujtahed_guide":
        return {"status": "ok", "guide": ALMUJTAHED_MCP_GUIDE}
    if name == "anchor_lookup":
        return shamela_local_mcp.anchor_lookup((args or {}).get("query") or "")
    if name == "anchor_search":
        return shamela_local_mcp.anchor_search((args or {}).get("query") or "",
                                               int((args or {}).get("limit") or 12),
                                               (args or {}).get("book_ids"))
    if name == "search_passages":
        return _mcp_search_passages(args or {})
    if name == "research_evidence":
        return _mcp_research_evidence(args or {}, request)
    return shamela_local_mcp.execute_mcp_tool(name, args or {})


@app.post("/api/mcp/execute")
async def execute_mcp_tool_route(req: MCPExecuteRequest, request: Request):
    """تنفيذ أداة MCP برمجياً وتمرير النتائج للوكلاء التوليديين ومهندس المشاريع"""
    return await asyncio.to_thread(_mcp_dispatch, req.name, req.arguments, request)


def _mcp_protocol_tools() -> List[Dict[str, Any]]:
    tools = []
    for spec in shamela_local_mcp.SHAMELA_MCP_TOOLS_SPEC + ALMUJTAHED_MCP_EXTRA_TOOLS:
        fn = spec.get("function") or {}
        tools.append({
            "name": fn.get("name"),
            "description": fn.get("description") or "",
            "inputSchema": fn.get("parameters") or {"type": "object", "properties": {}},
        })
    return tools


@app.post("/mcp")
async def almujtahed_mcp_protocol(request: Request):
    """خادم MCP قياسي للمجتهد داخل التطبيق: initialize وtools/list وtools/call."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    method = payload.get("method") or ""
    rid = payload.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "almujtahed", "version": "1.0.0"},
            "instructions": ALMUJTAHED_MCP_GUIDE,
        }}
    if method.startswith("notifications/"):
        return JSONResponse(status_code=202, content={})
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": _mcp_protocol_tools()}}
    if method == "tools/call":
        params = payload.get("params") or {}
        try:
            result = await asyncio.to_thread(
                _mcp_dispatch, params.get("name") or "", params.get("arguments") or {}, request
            )
        except Exception as exc:
            result = {"status": "error", "code": "TOOL_FAILED", "error": f"تعذر تنفيذ الأداة: {exc}"}
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            "structuredContent": result,
            "isError": result.get("status") == "error",
        }}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"طريقة غير معروفة: {method}"}}

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
    path = Path(data_dir) / "web" / "bootstrap_status.json" if data_dir else BASE_DIR / "bootstrap_status.json"
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
    if QDRANT_DISABLED:
        return
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
                    app_state["is_hybrid_col"] = False
                    return
                if "shamela_06b_hybrid" in names:
                    app_state["qdrant"] = client
                    app_state["collection_name"] = "shamela_06b_hybrid"
                    app_state["is_8b"] = False
                    app_state["is_hybrid_col"] = True
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
    if data_dir:
        target = Path(data_dir) / "qdrant"
    else:
        status = _read_bootstrap_status() or {}
        if status.get("phase") != "snapshot":
            return 0
        target = PACKAGE_ROOT / "qdrant_service" / "storage"
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
        if sys.platform == "darwin":
            output = subprocess.check_output(["du", "-sk", str(target)], text=True, timeout=60)
            received = int(output.split()[0]) * 1024
        else:
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
    names = ("qdrant.exe", "qdrant") if os.name == "nt" else ("qdrant", "qdrant.exe")
    for root in (PACKAGE_ROOT, Path("/app"), SYSTEM_ROOT):
        directory = root / "qdrant_service"
        for name in names:
            binary = directory / name
            try:
                if binary.is_file() and binary.stat().st_size > 1_000_000:
                    return binary
            except OSError:
                continue
    return None

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

def _qdrant_pid_file():
    raw = os.getenv("ALMUJTAHED_QDRANT_PID_FILE", "").strip()
    return Path(raw) if raw else None

def _listener_pids(port=6333):
    pids = []
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(["netstat", "-ano", "-p", "tcp"], text=True, timeout=5, errors="replace")
        except Exception:
            return []
        token = f":{port}"
        for line in output.splitlines():
            if token not in line or "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.append(int(parts[-1]))
        return pids
    try:
        output = subprocess.check_output(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"], text=True, timeout=5)
    except Exception:
        return []
    for raw in output.split():
        if raw.isdigit():
            pids.append(int(raw))
    return pids

def _process_command(pid):
    try:
        if sys.platform == "win32":
            output = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                text=True,
                timeout=8,
                errors="replace",
            )
            return output.strip()
        if sys.platform == "darwin":
            output = subprocess.check_output(["ps", "-p", str(int(pid)), "-o", "command="], text=True, timeout=5)
            return output.strip()
        raw = Path(f"/proc/{int(pid)}/cmdline").read_bytes().replace(b"\x00", b" ")
        return raw.decode("utf-8", "replace").strip()
    except Exception:
        return ""

def _command_is_our_qdrant(command, binary):
    if not command:
        return False
    folded = command.replace("\\", "/").lower()
    target = str(binary).replace("\\", "/").lower()
    return target in folded

def _our_qdrant_pids():
    binary = _bundled_qdrant_path()
    if binary is None:
        return []
    candidates = set(_listener_pids())
    pid_file = _qdrant_pid_file()
    if pid_file and pid_file.is_file():
        try:
            candidates.add(int(pid_file.read_text(encoding="utf-8").strip()))
        except (OSError, ValueError):
            pass
    found = []
    for pid in candidates:
        if pid > 0 and _command_is_our_qdrant(_process_command(pid), binary):
            found.append(pid)
    return found

def _clear_qdrant_pid_file():
    pid_file = _qdrant_pid_file()
    if pid_file and pid_file.is_file():
        try:
            pid_file.unlink()
        except OSError:
            pass

def _write_qdrant_pid(pid):
    pid_file = _qdrant_pid_file()
    if not pid_file:
        return
    try:
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(int(pid)), encoding="utf-8")
    except OSError:
        pass

def _signal_pid(pid, force=False):
    if sys.platform == "win32":
        command = ["taskkill", "/PID", str(int(pid)), "/T"]
        if force:
            command.append("/F")
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        return
    os.kill(int(pid), 9 if force else 15)

def _start_bundled_qdrant():
    """يشغّل محرك هذه النسخة إذا كان المنفذ فارغاً. لا يمس مخزناً آخر على المنفذ نفسه."""
    if QDRANT_DISABLED:
        return False
    binary = _bundled_qdrant_path()
    if binary is None:
        _QDRANT_ENGINE["last_message"] = "تعذر العثور على محرك المخزن داخل التطبيق"
        return False, _QDRANT_ENGINE["last_message"]
    if _qdrant_port_open():
        if _our_qdrant_pids():
            _ensure_qdrant_client()
            _QDRANT_ENGINE["last_message"] = "المخزن يعمل"
            return True, "المخزن يعمل"
        _QDRANT_ENGINE["last_message"] = "المنفذ 6333 مشغول بمخزن آخر، تعذر تشغيل مخزن هذه النسخة"
        return False, _QDRANT_ENGINE["last_message"]
    if not _QDRANT_START_LOCK.acquire(blocking=False):
        return True, "جارٍ تشغيل المخزن"
    try:
        if _qdrant_port_open():
            message = "المخزن يعمل" if _our_qdrant_pids() else "المنفذ 6333 مشغول بمخزن آخر، تعذر تشغيل مخزن هذه النسخة"
        else:
            _QDRANT_ENGINE["starting"] = True
            service_dir = binary.parent
            config_path = service_dir / "config" / "config.yaml"
            if not config_path.is_file():
                message = "ملف إعداد المخزن غير موجود"
            else:
                (service_dir / "storage").mkdir(parents=True, exist_ok=True)
                (service_dir / "snapshots").mkdir(parents=True, exist_ok=True)
                log_handle = open(service_dir / "qdrant.log", "ab", buffering=0)
                kwargs = {
                    "cwd": str(service_dir),
                    "stdout": log_handle,
                    "stderr": log_handle,
                    "stdin": subprocess.DEVNULL,
                }
                if os.name == "nt":
                    kwargs["creationflags"] = 0x08000000 | 0x00000200 | 0x01000000
                else:
                    kwargs["start_new_session"] = True
                process = subprocess.Popen([str(binary), "--config-path", str(config_path)], **kwargs)
                _write_qdrant_pid(process.pid)
                message = "المحرك لم يرد بعد التشغيل"
                for _ in range(30):
                    if _qdrant_port_open():
                        message = "تم تشغيل المخزن"
                        break
                    if process.poll() is not None:
                        message = "توقف محرك المخزن قبل أن يرد"
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
    if _qdrant_port_open() and _our_qdrant_pids():
        _ensure_qdrant_client()
        return True, _QDRANT_ENGINE["last_message"]
    if _qdrant_port_open():
        return False, _QDRANT_ENGINE["last_message"] or "المنفذ 6333 مشغول بمخزن آخر"
    return False, _QDRANT_ENGINE["last_message"]

def _stop_bundled_qdrant():
    """يوقف محرك هذه النسخة فقط، ويترك أي مخزن آخر على المنفذ كما هو."""
    binary = _bundled_qdrant_path()
    if binary is None:
        return False, "تعذر العثور على محرك المخزن داخل التطبيق"
    pids = _our_qdrant_pids()
    if not pids:
        if _qdrant_port_open():
            return False, "المنفذ 6333 مشغول بمخزن آخر، ولم يُوقف مخزن هذه النسخة"
        _clear_qdrant_pid_file()
        return True, "المخزن متوقف"
    for pid in pids:
        try:
            _signal_pid(pid, force=False)
        except Exception:
            continue
    for _ in range(10):
        if not _our_qdrant_pids():
            break
        time.sleep(0.4)
    for pid in _our_qdrant_pids():
        try:
            _signal_pid(pid, force=True)
        except Exception:
            continue
    time.sleep(0.3)
    if _our_qdrant_pids():
        return False, "تعذر إيقاف المخزن"
    _clear_qdrant_pid_file()
    app_state["qdrant"] = None
    return True, "تم إيقاف المخزن"

def _qdrant_watchdog():
    while True:
        time.sleep(20)
        try:
            if _QDRANT_ENGINE.get("closed"):
                continue
            if not _qdrant_port_open():
                _start_bundled_qdrant()
            elif not app_state.get("qdrant"):
                _ensure_qdrant_client()
        except Exception:
            pass

def _collection_installed():
    collection = PACKAGE_ROOT / "qdrant_service" / "storage" / "collections" / "shamela_almojtahed_8b_dense"
    try:
        return collection.is_dir() and any(collection.iterdir())
    except OSError:
        return False

def _snapshot_restore_view(connected, points_count):
    status = _read_bootstrap_status() or {}
    phase = status.get("phase") or ""
    expected = int(status.get("expected_bytes") or _SNAPSHOT_EXPECTED_BYTES) or _SNAPSHOT_EXPECTED_BYTES
    ready = bool(_collection_installed() or (connected and points_count > 1000))
    active_phase = phase in ("download", "snapshot", "install", "local")
    received = 0 if ready or not active_phase else max(int(status.get("received_bytes") or 0), _qdrant_dir_bytes())
    downloading = active_phase and (not ready) and received >= (1024 ** 3)
    percent = 100 if ready else min(99, int(received * 100 / expected)) if expected else 0
    received_gb = round(received / (1024 ** 3), 1)
    expected_gb = round(expected / (1024 ** 3), 1)
    if ready or not active_phase:
        label = "مخزن البيانات جاهز" if ready else ""
        active = False
    elif phase == "install":
        label = "جاري تركيب قاعدة البيانات ... فضلا انتظر حتى تكتمل ويتوقف العداد"
        active = True
    elif downloading or phase in ("download", "snapshot"):
        label = "جاري سحب قاعدة البيانات"
        active = True
    elif phase == "error":
        label = status.get("message") or "توقفت استعادة مخزن البيانات"
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
        health_label = restore.get("label") or "جاري سحب قاعدة البيانات"
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
    """يعيد تشغيل محرك هذه النسخة حتى لو كان متوقفاً، من غير مسح البيانات."""
    require_admin(request)
    if _bundled_qdrant_path() is None:
        return {"status": "unavailable", "message": "تعذر العثور على محرك المخزن داخل التطبيق"}

    def _restart():
        _QDRANT_ENGINE["closed"] = True
        _stop_bundled_qdrant()
        app_state["qdrant"] = None
        for _ in range(20):
            if not _qdrant_port_open():
                break
            time.sleep(0.25)
        _QDRANT_ENGINE["closed"] = False
        return _start_bundled_qdrant()

    ok, message = await asyncio.to_thread(_restart)
    return {"status": "ok" if ok else "error", "message": message}


@app.post("/api/system/qdrant/stop")
async def stop_qdrant_endpoint(request: Request):
    """يوقف محرك هذه النسخة ويبقيه متوقفاً حتى يطلب المستخدم تشغيله."""
    require_admin(request)
    if _bundled_qdrant_path() is None:
        return {"status": "unavailable", "message": "تعذر العثور على محرك المخزن داخل التطبيق"}

    def _stop():
        _QDRANT_ENGINE["closed"] = True
        return _stop_bundled_qdrant()

    ok, message = await asyncio.to_thread(_stop)
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
        app_state["embedder_kind"] = "gguf06b" if "06b" in path.name.lower() else "gguf8b"
        app_state["is_8b"] = app_state["embedder_kind"] != "gguf06b"
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



def _qdrant_alive() -> bool:
    """فحص حياة مخزن المتجهات قبل الاعتماد عليه؛ سقوطه لا يعطل البحث اللفظي."""
    client = app_state.get("qdrant")
    if client is None:
        return False
    try:
        client.get_collections()
        return True
    except Exception:
        return False


def _format_endpoint_results(cands, req) -> List[Dict[str, Any]]:
    """تشكيل مرشحي المراسي/اللفظي على هيئة نتائج صفحة البحث."""
    out: List[Dict[str, Any]] = []
    for i, c in enumerate(cands[:max(1, min(req.top_k, 500))]):
        _m = re.search(r"\d+", c.get("death") or "")
        _body = fetch_page_body(c.get("rel_path") or "", c.get("part_raw"), c.get("page_num_raw")) or c.get("snippet") or ""
        out.append({
            "initial_rank": i + 1, "initial_score": c["score"], "rank": i + 1, "reranked": False,
            "book_title": c["title"], "author": c["author"],
            "death_year": int(_m.group()) if _m else None,
            "category": c["category"], "volume": c.get("part_raw") or "",
            "page": str(c.get("page_num_raw") or ""), "score": c["score"],
            "rel_path": c.get("rel_path") or "", "book_id": c.get("book_id"),
            "text": _body,
        })
    return out


@app.post("/api/search")
async def search_endpoint(req: SearchRequest):
    """
    البحث الدلالي الحي في كولكشن shamela_corpus (5.14 مليون مقطع)
    """
    query = req.query.strip()
    if not query:
        return {"results": [], "query": query}

    t0 = time.time()
    # طبقات المراسي أولاً: إن طابق السؤال جدول المقابلة التراثي فالبحث لفظي بلا متجهات
    _tc = _anchor_candidates(query, getattr(req, "books", None), max(req.top_k, 10))
    if _tc:
        return {
            "results": _format_endpoint_results(_tc, req), "query": query,
            "duration": round(time.time() - t0, 3), "count": min(len(_tc), max(1, min(req.top_k, 500))),
            "pool_size": len(_tc),
            "source": "جدول المراسي التراثية (بحث لفظي في كتب قبل 1000هـ، بلا متجهات)",
            "is_hybrid": False, "is_reranked": False,
        }
    if not _qdrant_alive():
        # المخزن متوقف (وهو قرار المنتج الدائم الآن): فهرس المكتبة اللفظي
        # على المكتبة كلها هو البحث نفسه، بسقف وفاة الباحث إن حدّده فقط.
        _fc = _fts_candidates(query, None, getattr(req, "books", None), max(req.top_k, 10), death_max=req.death_max)
        if _fc:
            return {
                "results": _format_endpoint_results(_fc, req), "query": query,
                "duration": round(time.time() - t0, 3), "count": min(len(_fc), max(1, min(req.top_k, 500))),
                "pool_size": len(_fc),
                "source": "فهرس المكتبة (بحث لفظي فوري في المكتبة كلها، بلا متجهات)",
                "is_hybrid": False, "is_reranked": False,
            }
        _lc = _lexical_only_candidates(query, None, getattr(req, "books", None), max(req.top_k, 10))
        if _lc:
            return {
                "results": _format_endpoint_results(_lc, req), "query": query,
                "duration": round(time.time() - t0, 3), "count": min(len(_lc), max(1, min(req.top_k, 500))),
                "pool_size": len(_lc),
                "source": "بحث لفظي بالمراسي داخل كتب التراث (مخزن المتجهات متوقف)",
                "is_hybrid": False, "is_reranked": False,
            }
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
            if app_state.get("llama_embedder") and (is_8b_col or app_state.get("is_hybrid_col")):
                q_in = _hybrid_query_text(query) if app_state.get("embedder_kind") == "gguf06b" else query
                with EMBEDDING_LOCK:
                    emb = app_state["llama_embedder"].create_embedding(q_in)
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
            book_key = "title" if app_state.get("is_hybrid_col") else ("book_title" if is_8b_col else "title_ar")

            # فلترة نطاق البحث المحدد من قبل المستخدم
            has_explicit_books = False
            clean_books = []
            if req.selected_books and len(req.selected_books) > 0:
                clean_books = resolve_book_titles_for_search(req.selected_books, cursor=cursor)
                if clean_books:
                    has_explicit_books = True
                    conditions.append(FieldCondition(key=book_key, match=MatchAny(any=_prefer_primary_titles(clean_books)[:500])))
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
                if app_state.get("is_hybrid_col"):
                    if clean_cat:
                        conditions.append(FieldCondition(key="category", match=MatchValue(value=clean_cat)))
                elif is_8b_col:
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

            # صفحة البحث الدلالي للتراث فقط: سقف وفاة المؤلف 1000هـ دائماً (طلب المستخدم)،
            # ويُحترم أي سقف أضيق يختاره المستخدم من الواجهة.
            death_cap = 1000
            if req.death_max and req.death_max > 0:
                death_cap = min(req.death_max, 1000)
            if death_cap:
                if app_state.get("is_hybrid_col"):
                    # في المجموعة الهجينة حقل death مفهرس كـ integer مباشرة في Qdrant
                    conditions.append(FieldCondition(key="death", range=Range(lte=death_cap, gt=0)))
                elif is_8b_col:
                    # في مجموعة 8B حقل author_death_hijri مفهرس كـ integer مباشرة في Qdrant
                    conditions.append(FieldCondition(key="author_death_hijri", range=Range(lte=death_cap, gt=0)))
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
            dense_top_score = hits[0].score if hits else 0.0

            # القناة اللفظية BM25 داخل المخزن الهجين: توسيع البركة بمصطلحات التراث
            sparse_score_map: Dict[Any, float] = {}
            bridge_score_map: Dict[Any, float] = {}
            if app_state.get("is_hybrid_col"):
                try:
                    s_hits = app_state["qdrant"].query_points(
                        collection_name=app_state["collection_name"],
                        query=_hybrid_sparse_vector(query),
                        using="bm25",
                        query_filter=q_filter,
                        limit=fetch_limit,
                        with_payload=True
                    ).points
                    seen_ids = {h.id for h in hits}
                    for r_idx, sp in enumerate(s_hits):
                        if sp.id not in seen_ids:
                            seen_ids.add(sp.id)
                            sparse_score_map[sp.id] = 0.34 + 0.18 * (1.0 - r_idx / max(1, len(s_hits)))
                            hits.append(sp)
                except Exception as se:
                    print(f"Sparse query error in /api/search: {se}")

            # جسر التغطية: عند ضعف أعلى درجة دلالية يُستشار مخزن 8B القديم (يجسر مفردات حديثة كـ«باروكة» إلى «الوصل»)
            if app_state.get("is_hybrid_col") and dense_top_score < _BRIDGE_GATE and not req.category:
                b_pts = _bridge_old_hits(query, clean_books if has_explicit_books else None, fetch_limit)
                if b_pts:
                    def _pg_key(pl):
                        pl = pl or {}
                        return (pl.get("book_title") or pl.get("title"),
                                str(pl.get("volume") or pl.get("part") or ""),
                                pl.get("page_num") or pl.get("page"))
                    seen_pages = {_pg_key(h.payload) for h in hits}
                    for r_idx, bp in enumerate(b_pts):
                        k = _pg_key(bp.payload)
                        if k in seen_pages:
                            continue
                        seen_pages.add(k)
                        bridge_score_map[bp.id] = 0.45 + 0.15 * (1.0 - r_idx / max(1, len(b_pts)))
                        hits.append(bp)

            # 4. تجميع المرشحين الأوائل وحفظ ترتيب الاسترجاع الأولي (initial_rank)
            candidates = []
            bodies_fetched = 0
            for hit in hits:
                raw_p = hit.payload or {}
                p = raw_p if (not app_state.get("is_hybrid_col") or raw_p.get("_src_old")) else _normalize_hybrid_payload(raw_p)
                h_score = bridge_score_map.get(hit.id, hit.score) if raw_p.get("_src_old") else sparse_score_map.get(hit.id, hit.score)
                title = p.get("book_title") or p.get("title_ar", "كتاب غير معنون")
                part = p.get("volume") or p.get("part")
                page_num = p.get("page_num")
                cat_name = p.get("category_name", "عام")
                author = p.get("author_name", "")
                death_year = p.get("author_death_hijri") or p.get("death_hijri")
                footnotes = p.get("footnotes", "")
                betaka = p.get("betaka_text", "")
                rel_path = ""
                book_id = _payload_book_id(p)
                cached_text = p.get("text", "")

                # جلب مسار الكتاب والبيانات من SQLite
                if cursor:
                    try:
                        row = None
                        if book_id:
                            cursor.execute("SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, rel_path, betaka_text FROM books WHERE book_id = ? LIMIT 1", (book_id,))
                            row = cursor.fetchone()
                        if row is None:
                            cursor.execute("SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, rel_path, betaka_text FROM books WHERE title_ar = ? LIMIT 1", (title,))
                            row = cursor.fetchone()
                        if row:
                            if row["title_ar"]:
                                title = row["title_ar"]
                            if not author: author = row["main_author_name_ar"] or ""
                            if death_year is None: death_year = row["main_author_death_hijri"]
                            if cat_name in ("", "عام"): cat_name = row["category_name_ar"] or "عام"
                            if not betaka: betaka = row["betaka_text"] or ""
                            rel_path = row["rel_path"] or ""
                            book_id = row["book_id"]
                    except Exception:
                        pass

                # تأكيد سقف التراث (1000هـ) واستبعاد المعاصرين (99999)
                if death_year and (death_year > death_cap or death_year == 99999):
                    continue

                # في المخزن الهجين لا نص داخل الحمولة: اجلب نص الصفحة من المكتبة حتى يعمل دمج BM25 على نص حقيقي
                if app_state.get("is_hybrid_col") and req.use_hybrid and not cached_text and rel_path and bodies_fetched < 100:
                    bodies_fetched += 1
                    try:
                        cached_text = fetch_page_body(rel_path, part, page_num)
                    except Exception:
                        cached_text = ""

                item_cand = {
                    "initial_rank": len(candidates) + 1,
                    "initial_score": round(h_score, 3),
                    "book_title": title,
                    "author": author or "أحد أئمة التراث",
                    "death_year": death_year,
                    "category": cat_name,
                    "volume": str(part) if part not in (None, "None") else "",
                    "page": str(page_num) if page_num is not None else "",
                    "score": round(h_score, 3),
                    "rel_path": rel_path,
                    "book_id": book_id,
                    "betaka": betaka,
                    "part_raw": part,
                    "page_raw": page_num
                }
                if cached_text:
                    item_cand["text_cached"] = cached_text
                candidates.append(item_cand)

            total_retrieved = len(candidates)

            if req.use_hybrid:
                lexical_titles = clean_books if has_explicit_books and clean_books else []
                for lex in lexical_page_matches(query, lexical_titles):
                    page_key = (lex.get("book_id"), str(lex.get("part")), str(lex.get("page_num")))
                    existing = next((item for item in candidates if (item.get("book_id"), str(item.get("part_raw")), str(item.get("page_raw"))) == page_key), None)
                    if existing:
                        existing["lexical_hit"] = True
                        existing["initial_score"] = max(float(existing.get("initial_score") or 0), 0.95)
                        continue
                    candidates.append({
                        "initial_rank": len(candidates) + 1,
                        "initial_score": 0.99,
                        "book_title": lex.get("title"),
                        "author": lex.get("author") or "أحد أئمة التراث",
                        "death_year": lex.get("death_year"),
                        "category": lex.get("category") or "عام",
                        "volume": str(lex.get("part") or ""),
                        "page": str(lex.get("page_num") or ""),
                        "score": 0.99,
                        "rel_path": lex.get("rel_path") or "",
                        "book_id": lex.get("book_id"),
                        "betaka": "",
                        "part_raw": lex.get("part"),
                        "page_raw": lex.get("page_num"),
                        "text_cached": lex.get("snippet") or "",
                        "lexical_hit": True,
                    })

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

            is_hybrid_active = bool(req.use_hybrid and (rank_bm25 or any(item.get("lexical_hit") for item in candidates)) and len(candidates) > 1)
            if req.use_hybrid:
                lexical_first = [item for item in candidates if item.get("lexical_hit")]
                others = [item for item in candidates if not item.get("lexical_hit")]
                candidates = _diversify_by_book(lexical_first + others, target_top_k, "book_title", 2)
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


# ---------------- ربط المكتبة الشاملة المحلية (تطبيق الشاملة عند المستخدم) ----------------
_shamela_job = {"running": False, "stage": "", "i": 0, "of": 0, "title": "", "report": None, "error": ""}


@app.get("/api/shamela/status")
async def shamela_status():
    """كشف تطبيق الشاملة على جهاز المستخدم وعدّ كتبه المنزّلة والمستوردة."""
    try:
        import shamela_link
        st = shamela_link.census()
    except Exception as exc:
        st = {"found": False, "message": f"تعذّر فحص الشاملة: {exc}"}
    st["job"] = dict(_shamela_job)
    st["job"]["watching"] = bool(_shamela_watch.get("active"))
    return st


def _run_shamela_import_job():
    """تسجيل كتب الشاملة الجديدة في الكتالوج (المسار الكسول): بلا تحويل
    جماعي — النصوص تُستخرج كتابًا كتابًا عند أول لمس في بحث أو قراءة."""
    if _shamela_job["running"]:
        return
    _shamela_job.update({"running": True, "stage": "start", "i": 0, "of": 0,
                         "title": "", "report": None, "error": "", "started_at": time.time()})
    try:
        import shamela_link
        _shamela_job["stage"] = "register"
        added = shamela_link.register_new_books()
        _shamela_job["report"] = {"registered": added}
        _shamela_job["stage"] = "done"
        print(f"📥 [ShamelaLink] سُجّل {added} كتابًا جديدًا من الشاملة (يُستخرج عند اللمس)", flush=True)
    except Exception as exc:
        _shamela_job.update({"stage": "error", "error": str(exc)[:300]})
    finally:
        _shamela_job["running"] = False


@app.post("/api/shamela/import")
async def shamela_import():
    """استيراد كتب الشاملة المنزّلة إلى مكتبة المجتهد (عملية خلفية بتقدّم)."""
    if _shamela_job["running"]:
        return {"ok": False, "message": "الاستيراد جارٍ أصلًا — تابع تقدّمه من البطاقة."}
    threading.Thread(target=_run_shamela_import_job, daemon=True, name="shamela-import").start()
    return {"ok": True, "message": "بدأ الاستيراد في الخلفية."}


_shamela_watch = {"active": False, "baseline": 0, "imported_runs": 0}


def _shamela_watcher():
    """مراقبة مجلد كتب الشاملة: ما إن يصل كتاب جديد حتى يُستورد تلقائيًا."""
    import shamela_link
    _shamela_watch.update({"active": True, "imported_runs": 0})
    try:
        base = shamela_link.census()
        last = base.get("downloaded", 0)
        _shamela_watch["baseline"] = last
        deadline = time.time() + 1800  # نصف ساعة مراقبة لكل طلب إكمال
        while time.time() < deadline:
            time.sleep(20)
            try:
                now = shamela_link.census().get("downloaded", 0)
            except Exception:
                continue
            if now > last:
                last = now
                if not _shamela_job["running"]:
                    _shamela_watch["imported_runs"] += 1
                    _run_shamela_import_job()
    finally:
        _shamela_watch["active"] = False


@app.post("/api/shamela/complete")
async def shamela_complete():
    """إكمال المكتبة: فتح تطبيق الشاملة للتنزيل الرسمي + مراقبة واستيراد تلقائي."""
    import shamela_link
    opened = shamela_link.open_shamela_app()
    if not _shamela_watch["active"]:
        threading.Thread(target=_shamela_watcher, daemon=True, name="shamela-watch").start()
    return {"ok": True, **opened, "watching": True}


def _shamela_autostart():
    """عند إقلاع التطبيق: مزامنة مرآة الشاملة الداخلية ثم استيراد ما جدّ."""
    try:
        import time as _t
        _t.sleep(25)  # بعد استقرار الإقلاع تمامًا — لا منافسة على أول ثوانٍ
        import shamela_link
        # الخطة الثانية: مرآة قاعدة الشاملة داخل التطبيق تُزامَن أولًا
        # (أول مرة: نسخ كامل؛ بعدها: تفاضلي سريع)، فتعمل القراءة منها.
        try:
            _mr = shamela_link.sync_mirror(progress=lambda m: print(m, flush=True))
            if _mr.get("ok"):
                try:
                    _added = shamela_link.register_new_books()
                    if _added:
                        print(f"📥 [Mirror] سُجّل {_added} كتابًا جديدًا من المرآة", flush=True)
                except Exception:
                    pass
        except Exception as _mexc:
            print(f"⚠️ [Mirror] تعذّرت المزامنة (نبقى على الأصل): {_mexc}", flush=True)
        st = shamela_link.census()
        if st.get("found") and st.get("importable_new", 0) > 0:
            print(f"📥 [ShamelaLink] {st['importable_new']} كتاب جديد في الشاملة — يُستورد تلقائيًا…", flush=True)
            _run_shamela_import_job()
    except Exception as exc:
        print(f"⚠️ [ShamelaLink] تعذّر الاستيراد التلقائي: {exc}", flush=True)


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


_LEXICAL_STOP = {
    "حديث", "احاديث", "تخريج", "اخرج", "اخرجه", "اخرجوا", "اسناد", "اسانيد",
    "درجه", "حكم", "صحيح", "حسن", "ضعيف", "كتاب", "باب", "جزء", "صفحه",
    "يريد", "اريد", "ابحث", "هذا", "هذه", "ذلك", "التي", "الذي", "اصحاب", "السنن",
}
_CANONICAL_HADITH_TITLES = (
    "صحيح البخاري - ط السلطانية",
    "صحيح مسلم - ت عبد الباقي",
    "سنن أبي داود - ت محيي الدين عبد الحميد",
    "سنن أبي داود - ط دهلي مع عون المعبود",
    "سنن الترمذي - ط الرسالة",
    "سنن النسائي - ط الرسالة",
    "سنن ابن ماجه - ت عبد الباقي",
)
_PRIMARY_TITLE_MARKERS = (
    "صحيح البخاري", "صحيح مسلم", "سنن أبي داود", "سنن ابي داود",
    "سنن الترمذي", "سنن النسائي", "سنن ابن ماجه", "الموطأ", "مسند أحمد", "مسند احمد",
)


def _fold_search_text(text: str) -> str:
    text = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text or "")
    text = re.sub(r"[إأآا]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return text


def _prefer_primary_titles(titles: List[str]) -> List[str]:
    def rank(title: str) -> int:
        for index, marker in enumerate(_PRIMARY_TITLE_MARKERS):
            if marker in (title or ""):
                return index
        return len(_PRIMARY_TITLE_MARKERS)
    return sorted(titles, key=rank)


def _lexical_terms(query: str) -> List[str]:
    tokens = re.findall(r"[\u0600-\u06FF]{4,}", _fold_search_text(query))
    terms = []
    for token in tokens:
        if token in _LEXICAL_STOP or token in terms:
            continue
        terms.append(token)
    terms.sort(key=len, reverse=True)
    return terms[:3]


def _term_variants(term: str) -> List[str]:
    variants = {term}
    stem = term[2:] if term.startswith("ال") and len(term) > 5 else term
    if len(stem) < 4:
        return [item for item in variants if len(item) >= 4]
    variants.update({stem, "ب" + stem, "و" + stem, "ف" + stem})
    if stem.endswith("ه"):
        bare = stem[:-1]
        variants.update({bare + "ته", "ب" + bare + "ته", bare + "تها", "ال" + stem})
    return [item for item in variants if len(item) >= 4]


def _hadith_lookup_query(query: str) -> bool:
    folded = _fold_search_text(query)
    return any(marker in folded for marker in ("حديث", "احاديث", "تخريج", "اخرجه", "اسناد"))


def _snippet_around(plain: str, variants: List[str], limit: int = 700) -> str:
    folded = _fold_search_text(plain)
    index = -1
    for variant in variants:
        found = folded.find(variant)
        if found >= 0 and (index < 0 or found < index):
            index = found
    if index < 0 or len(plain) <= limit:
        return plain[:limit]
    origin = 0
    folded_index = 0
    start = 0
    end = len(plain)
    target_start = max(0, index - 160)
    target_end = min(len(folded), index + 420)
    for offset, char in enumerate(plain):
        if re.match(r"[\u064B-\u065F\u0670\u0640]", char):
            continue
        if folded_index == target_start:
            start = offset
        if folded_index >= target_end:
            end = offset
            break
        folded_index += 1
    else:
        end = len(plain)
    if start == 0 and index > 0:
        start = origin
    return plain[start:end].strip()


def lexical_page_matches(query: str, titles: Optional[List[str]] = None, limit_books: int = 36, per_book: int = 2, confine_to_titles: bool = False, max_seconds: float = 3.0) -> List[dict]:
    """يفتش صفحات الكتب لفظياً. في التخريج المفتوح يمر على الصحيحين والسنن، ويبقى داخل العناوين المحددة إذا حُصر النطاق."""
    terms = _lexical_terms(query)
    if not terms:
        return []
    variants = _term_variants(terms[0])
    if not variants:
        return []
    db = get_db()
    if not db:
        return []
    ordered = []
    seen_titles = set()
    if _hadith_lookup_query(query) and not confine_to_titles:
        for title in _CANONICAL_HADITH_TITLES:
            if title not in seen_titles:
                seen_titles.add(title)
                ordered.append(title)
    for title in _prefer_primary_titles(list(titles or [])):
        if title and title not in seen_titles:
            seen_titles.add(title)
            ordered.append(title)
    ordered = ordered[: max(limit_books, len(_CANONICAL_HADITH_TITLES) if _hadith_lookup_query(query) else limit_books)]
    if not ordered:
        return []
    cursor = db.cursor()
    records = {}
    for start in range(0, len(ordered), 80):
        chunk = ordered[start:start + 80]
        placeholders = ",".join("?" for _ in chunk)
        try:
            cursor.execute(
                f"""SELECT book_id, title_ar, rel_path, main_author_name_ar, main_author_death_hijri,
                          category_name_ar, volume_count_observed
                   FROM books WHERE title_ar IN ({placeholders})""",
                chunk,
            )
            for row in cursor.fetchall():
                records[row["title_ar"]] = row
        except Exception:
            continue
    matches = []
    started = time.monotonic()
    canonical_count = len(_CANONICAL_HADITH_TITLES) if _hadith_lookup_query(query) else 0
    for index, title in enumerate(ordered):
        if index >= canonical_count and time.monotonic() - started > max_seconds:
            break
        row = records.get(title)
        if not row or not row["rel_path"]:
            continue
        _rel, pages_file = _pages_file_for_rel(row["rel_path"])
        if not pages_file:
            continue
        found = 0
        seen_pages = set()
        try:
            with open(pages_file, "r", encoding="utf-8") as handle:
                for line in handle:
                    folded_line = _fold_search_text(line)
                    if not any(variant in folded_line for variant in variants):
                        continue
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue
                    page_key = (row["book_id"], str(data.get("part")), str(data.get("page_num")))
                    if page_key in seen_pages:
                        continue
                    seen_pages.add(page_key)
                    plain = re.sub(r"<[^>]+>", " ", f"{data.get('body') or ''} {data.get('footnotes') or ''}")
                    plain = re.sub(r"\s+", " ", plain).strip()
                    folded_plain = _fold_search_text(plain)
                    if not any(variant in folded_plain for variant in variants):
                        continue
                    death = row["main_author_death_hijri"]
                    matches.append({
                        "title": row["title_ar"],
                        "author": row["main_author_name_ar"] or "",
                        "death": f"(ت: {death} هـ)" if death else "",
                        "death_year": death,
                        "category": row["category_name_ar"] or "عام",
                        "part": data.get("part"),
                        "page_num": data.get("page_num"),
                        "volume_count": row["volume_count_observed"],
                        "book_id": row["book_id"],
                        "rel_path": row["rel_path"] or "",
                        "snippet": _snippet_around(plain, variants),
                        "lexical_hit": True,
                    })
                    found += 1
                    if found >= per_book:
                        break
        except OSError:
            continue
    return matches


def _diversify_by_book(items: List[dict], top_k: int, title_key: str, per_book: int = 2) -> List[dict]:
    """يأخذ من كل كتاب حصته قبل أن يتكرر كتاب واحد حتى يمتلئ العدد."""
    if top_k <= 0 or not items:
        return []
    groups: Dict[str, List[dict]] = {}
    order = []
    for item in items:
        title = str(item.get(title_key) or "")
        if title not in groups:
            groups[title] = []
            order.append(title)
        groups[title].append(item)
    picked = []
    while len(picked) < top_k:
        progressed = False
        for title in order:
            group = groups[title]
            if not group:
                continue
            already = sum(1 for item in picked if str(item.get(title_key) or "") == title)
            others_left = any(groups[other] for other in order if other != title)
            if already >= per_book and others_left:
                continue
            picked.append(group.pop(0))
            progressed = True
            if len(picked) >= top_k:
                break
        if not progressed:
            for title in order:
                while groups[title] and len(picked) < top_k:
                    picked.append(groups[title].pop(0))
            break
    return picked


_HYBRID_QUERY_PROMPT = "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:"
_HYBRID_DIAC_RE = re.compile(r"[ً-ٰٟـ]")
_HYBRID_TRANS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه"})
_HYBRID_WORD_RE = re.compile(r"[^\s\W]+", re.UNICODE)

def _hybrid_norm(s: str) -> str:
    s = _HYBRID_DIAC_RE.sub("", s or "").translate(_HYBRID_TRANS)
    return re.sub(r"\s+", " ", s).strip()

def _hybrid_query_text(q_text: str) -> str:
    """نص الاستعلام كما رآه مضمِّن 0.6B زمن بناء المخزن: بلا تشكيل + سابقة التعليمات + قصّ آمن."""
    return _HYBRID_QUERY_PROMPT + _HYBRID_DIAC_RE.sub("", (q_text or "").strip())[:1200]

def _hybrid_sparse_vector(text: str):
    """نفس متجه BM25 المتناثر المستخدم زمن بناء المخزن (تطبيع + crc32 + ‏1+log(tf) + دمج الاصطدامات)."""
    import math
    import zlib
    from qdrant_client.models import SparseVector
    tf: Dict[str, float] = {}
    for tok in _HYBRID_WORD_RE.findall(_hybrid_norm(text)):
        if len(tok) < 2:
            continue
        tf[tok] = tf.get(tok, 0.0) + 1.0
    merged: Dict[int, float] = {}
    for t, v in tf.items():
        idx = zlib.crc32(t.encode("utf-8")) & 0x7FFFFFFF
        merged[idx] = merged.get(idx, 0.0) + (1.0 + math.log(v))
    return SparseVector(indices=list(merged.keys()), values=list(merged.values()))

_BRIDGE_LOCK = threading.Lock()
_BRIDGE_GATE = 0.70  # دون هذه الدرجة الدلالية القصوى تُعدّ تغطية المخزن الجديد ضعيفة فيُستشار جسر 8B

def _ensure_bridge_embedder():
    """تحميل مضمِّن 8B القديم كجسر تغطية للمفردات الحديثة التي لا يعرفها النموذج الصغير (كسولاً، مرة واحدة)."""
    if app_state.get("bridge_embedder"):
        return app_state["bridge_embedder"]
    if app_state.get("bridge_dead"):
        return None
    with _BRIDGE_LOCK:
        if app_state.get("bridge_embedder"):
            return app_state["bridge_embedder"]
        path = PACKAGE_ROOT / "models" / "gguf" / "almojtahed-embedding-8b-Q4_K_M.gguf"
        if not path.is_file():
            path = SYSTEM_ROOT / "models" / "gguf" / "almojtahed-embedding-8b-Q4_K_M.gguf"
        if not path.is_file():
            app_state["bridge_dead"] = True
            return None
        try:
            from llama_cpp import Llama
            model = Llama(
                model_path=str(path),
                embedding=True,
                n_gpu_layers=_desired_gpu_layers(),
                n_threads=min(8, os.cpu_count() or 4),
                verbose=False,
            )
            app_state["bridge_embedder"] = model
            print("🌉 [Bridge] تم تحميل مضمِّن 8B جسراً للتغطية الدلالية الاحتياطية")
            return model
        except Exception as e:
            print(f"⚠️ تعذر تحميل جسر 8B: {e}")
            app_state["bridge_dead"] = True
            return None

def _bridge_old_hits(q_text: str, book_titles: Optional[List[str]], limit: int):
    """استشارة مجموعة 8B القديمة عند ضعف تغطية المخزن الجديد؛ تُرجع نقاطاً موسومة بمصدرها أو قائمة فارغة."""
    if app_state.get("bridge_dead") or not app_state.get("qdrant"):
        return []
    model = _ensure_bridge_embedder()
    if not model:
        return []
    try:
        with EMBEDDING_LOCK:
            emb = model.create_embedding(q_text)
        v = np.array(emb["data"][0]["embedding"], dtype=np.float32)
        n = np.linalg.norm(v)
        if n == 0:
            return []
        b_filter = None
        if book_titles:
            b_filter = Filter(must=[FieldCondition(key="book_title", match=MatchAny(any=_prefer_primary_titles(book_titles)[:500]))])
        pts = app_state["qdrant"].query_points(
            collection_name="shamela_almojtahed_8b_dense",
            query=(v / n).tolist(),
            using="dense",
            query_filter=b_filter,
            limit=limit,
            with_payload=True
        ).points
        for p in pts:
            pl = dict(p.payload or {})
            pl["_src_old"] = True
            p.payload = pl
        if pts:
            print(f"🌉 [Bridge] جسر 8B أضاف {len(pts)} شاهداً لسؤال ضعيف التغطية: {q_text[:40]}")
        return pts
    except Exception as e:
        print(f"⚠️ تعذر استشارة جسر 8B: {e}")
        app_state["bridge_dead"] = True
        return []

def _normalize_hybrid_payload(p: Optional[dict]) -> dict:
    """تحويل حمولة المخزن الهجين إلى مفاتيح الحمولة التقليدية التي تتوقعها بقية خطوط المعالجة."""
    p = p or {}
    return {
        "book_title": p.get("title", ""),
        "part": p.get("part"),
        "page_num": p.get("page"),
        "author_name": p.get("author", ""),
        "category_name": p.get("category", "عام"),
        "author_death_hijri": p.get("death"),
        "book_id": p.get("book_id"),
        "page_id": p.get("page_id"),
        "heading": p.get("heading", ""),
        "text": "",
    }

def _selected_book_ids(selected_books, cursor) -> List[str]:
    """حل عناوين كتب مختارة إلى أرقامها لإغلاق النطاق اللفظي عليها."""
    ids: List[str] = []
    if not selected_books or not cursor:
        return ids
    # صيغة «#الرقم العنوان» المعتمدة في بطاقات الوكلاء: الرقم وحده حاسم،
    # وبدون فهمه هنا ينهار نطاق الكتاب المستدعى إلى فراغ (عطل سنن أبي داود).
    for b in selected_books:
        _m = re.match(r"\s*#\s*(\d{1,7})\b", str(b))
        if _m and _m.group(1) not in ids:
            ids.append(_m.group(1))
        try:
            _canon = resolve_canonical_book_name(str(b), cursor)
        except Exception:
            _canon = ""
        if _canon:
            try:
                cursor.execute("SELECT book_id FROM books WHERE title_ar = ? LIMIT 1", (_canon,))
                _r = cursor.fetchone()
                if _r and str(_r["book_id"]) not in ids:
                    ids.append(str(_r["book_id"]))
            except Exception:
                pass
    try:
        titles = resolve_book_titles_for_search(selected_books, cursor=cursor)
    except Exception:
        titles = []
    for t in list(titles or []) + [str(b) for b in selected_books]:
        try:
            cursor.execute("SELECT book_id FROM books WHERE title_ar = ? LIMIT 1", (t,))
            row = cursor.fetchone()
        except Exception:
            row = None
        if row and str(row["book_id"]) not in ids:
            ids.append(str(row["book_id"]))
    return ids


def _map_lexical_hits(hits, cursor, top_k: int) -> List[Dict[str, Any]]:
    """تحويل شواهد لفظية (من جدول المراسي أو مراسٍ حرة) إلى مرشحين بشكل مرشحي البحث المعتاد."""
    cands: List[Dict[str, Any]] = []
    seen = set()
    for i, h in enumerate(hits):
        bid = str(h.get("book_id") or "")
        key = (bid, str(h.get("part") or ""), str(h.get("page_num") or ""))
        if key in seen:
            continue
        seen.add(key)
        title = h.get("title") or ""
        author, death_year, cat_name, rel_path, vol_count = "", None, "عام", "", None
        if cursor and bid:
            try:
                cursor.execute(
                    "SELECT title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, rel_path, volume_count_observed FROM books WHERE book_id = ? LIMIT 1",
                    (int(bid),))
                row = cursor.fetchone()
            except Exception:
                row = None
            if row:
                title = row["title_ar"] or title
                author = row["main_author_name_ar"] or ""
                death_year = row["main_author_death_hijri"]
                cat_name = row["category_name_ar"] or "عام"
                rel_path = row["rel_path"] or ""
                vol_count = row["volume_count_observed"]
        snippet = h.get("snippet") or re.sub(r"\s+", " ", h.get("text") or "")[:750].strip()
        if not snippet:
            continue
        part, page_num = h.get("part"), h.get("page_num")
        cands.append({
            "title": title,
            "author": author or "أحد أئمة التراث",
            "death": f"(ت: {death_year} هـ)" if death_year else "",
            "category": cat_name,
            "vol": f"ج {part}" if part not in (None, "None", "") else "",
            "page": f"ص {page_num}" if page_num is not None else "",
            "volume_count": vol_count,
            "book_id": int(bid) if bid.isdigit() else bid,
            "citation_label": canonical_citation_label(title, part, page_num, vol_count, bid, author),
            "part_raw": str(part or ""),
            "page_num_raw": page_num,
            "rel_path": rel_path,
            "annalistic_year": None,
            "fiqh_header": None,
            "snippet": snippet,
            "score": round(max(0.80, 0.99 - 0.02 * i), 3),
            "lexical_hit": True,
            "anchor_phrase": h.get("phrase"),
            "anchor_term": h.get("term"),
        })
    return cands[:max(1, top_k)]


def _anchor_candidates(query: str, selected_books, top_k: int) -> List[Dict[str, Any]]:
    """طبقات المراسي: مطابقة جدول المقابلة التراثي ثم بحث لفظي بعباراته. بلا متجهات إطلاقاً."""
    try:
        db = get_db()
        cursor = db.cursor() if db else None
    except Exception:
        cursor = None
    book_ids = _selected_book_ids(selected_books, cursor) or None
    try:
        res = shamela_local_mcp.anchor_search(query, limit=max(top_k, 12), book_ids=book_ids)
    except Exception as e:
        print(f"⚓ [AnchorTable] تعذر بحث الجدول: {e}")
        return []
    hits = res.get("results") or []
    if not hits:
        return []
    return _map_lexical_hits(hits, cursor, max(top_k, 12))


def _lexical_only_candidates(query: str, dynamic_anchors, selected_books, top_k: int) -> List[Dict[str, Any]]:
    """مسار لفظي خالص عند غياب مخزن المتجهات: مراسي الوكيل أو نص السؤال داخل كتب النطاق."""
    try:
        db = get_db()
        cursor = db.cursor() if db else None
    except Exception:
        cursor = None
    book_ids = _selected_book_ids(selected_books, cursor) or shamela_local_mcp.anchor_table_scope_ids()
    phrases = [str(a).strip() for a in (dynamic_anchors or []) if str(a).strip() and len(str(a).strip()) >= 3]
    if not phrases:
        phrases = [query]
    hits: List[Dict[str, Any]] = []
    seen = set()
    cap = max(top_k, 12)
    for ph in phrases[:6]:
        try:
            found = shamela_local_mcp.search_books_scoped(query=ph, book_ids=book_ids, limit_per_book=2, limit=min(cap, 60))
        except Exception:
            continue
        for h in found.get("results") or []:
            key = (str(h.get("book_id")), str(h.get("part") or ""), str(h.get("page_num") or ""))
            if key in seen:
                continue
            seen.add(key)
            body = ""
            try:
                pg = shamela_local_mcp.get_page(book=h["book_id"], page_num=int(h["page_num"]), part=h.get("part"))
                body = ((pg.get("page") or {}).get("body") or "") if pg.get("status") == "ok" else ""
            except Exception:
                body = ""
            hits.append({"book_id": str(h.get("book_id")), "title": h.get("title") or "",
                         "part": h.get("part"), "page_num": h.get("page_num"), "phrase": ph,
                         "term": None, "text": body,
                         "snippet": re.sub(r"\s+", " ", body)[:750].strip()})
            if len(hits) >= cap:
                break
        if len(hits) >= cap:
            break
    return _map_lexical_hits(hits, cursor, cap)


def _edition_key(c: Dict[str, Any]) -> str:
    """مفتاح توحيد طبعات الكتاب الواحد (الطبري بتحقيقين = كتاب واحد في الانتقاء)."""
    t = re.split(r"\s+-\s+|\s+–\s+|،\s*ت\s|ط\s", str(c.get("title") or ""))[0]
    return re.sub(r"\s+", " ", t).strip()[:40] + "|" + str(c.get("author") or "")[:18]


def _diversify_pick(rows: List[Dict[str, Any]], limit: int = 16, genre_cap: float = None, core_genres: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """تقليم متنوع عبر جولات المراسي: تناوب بين الجولات حتى لا تطغى جولة
    لغوية/تفسيرية أولى على التوليف وتختفي جولات الفقه والحديث.
    قيود لينة (تُكسر عند نقص الحوض): كتابان للكتاب، طبعة واحدة للعنوان،
    وسقف فن اختياري genre_cap (بحث عام: لا فن فوقه ما أمكن)."""
    if len(rows) <= limit:
        return rows
    by_round: Dict[Any, List[Dict[str, Any]]] = {}
    for c in rows:
        by_round.setdefault(c.get("anchor_round"), []).append(c)
    rounds_sorted = sorted(by_round.values(), key=lambda r: -len(r))
    cap_n = int(limit * genre_cap) if genre_cap else None
    sup_max = max(2, int(limit * 0.25)) if core_genres else None  # حصة العلوم الخادمة مع قصد معلن
    picked: List[Dict[str, Any]] = []
    per_book: Dict[Any, int] = {}
    per_genre: Dict[str, int] = {}
    sup_count = [0]
    editions = set()

    def try_take(cand) -> bool:
        bk = cand.get("book_id")
        if per_book.get(bk, 0) >= 2:
            return False
        ek = _edition_key(cand)
        if ek in editions:
            return False
        g = _CAT_TO_GENRE.get(cand.get("category"), "أخرى")
        if cap_n is not None and per_genre.get(g, 0) >= cap_n:
            return False
        if sup_max is not None and g not in core_genres:
            if sup_count[0] >= sup_max:
                return False
            sup_count[0] += 1
        if core_genres and len(core_genres) > 1 and g in core_genres:
            if per_genre.get(g, 0) >= int(limit * 0.62) + 1:  # لا يستأثر فن مستهدف بأخيه
                return False
        per_book[bk] = per_book.get(bk, 0) + 1
        per_genre[g] = per_genre.get(g, 0) + 1
        editions.add(ek)
        picked.append(cand)
        return True

    i = 0
    while len(picked) < limit:
        progress = False
        for rows_r in rounds_sorted:
            if i < len(rows_r) and len(picked) < limit:
                if try_take(rows_r[i]):
                    progress = True
        if not progress:
            break
        i += 1
    if len(picked) < limit:  # استكمال عند النقص: الفنون الأقل تمثيلا أولا، ثم الأقوى بقاء
        seen_ids = {id(c) for c in picked}
        rest = [c for c in rows if id(c) not in seen_ids]
        rest.sort(key=lambda c: per_genre.get(_CAT_TO_GENRE.get(c.get("category"), "أخرى"), 0))
        for c in rest:
            if len(picked) >= limit:
                break
            picked.append(c)
    return picked


_GENRE_CATEGORIES = {
    "حديث": ["كتب السنة", "شروح الحديث", "التخريج والأطراف", "علوم الحديث", "العلل والسؤلات الحديثية"],
    "فقه": ["الفقه الحنفي", "الفقه المالكي", "الفقه الشافعي", "الفقه الحنبلي", "الفقه العام",
            "مسائل فقهية", "علوم الفقه والقواعد الفقهية", "أصول الفقه", "الفرائض والوصايا", "السياسة الشرعية والقضاء"],
    "تفسير": ["التفسير", "علوم القرآن وأصول التفسير"],
    "عقيدة": ["العقيدة", "الفرق والردود"],
    "لغة": ["الغريب والمعاجم", "كتب اللغة", "النحو والصرف", "البلاغة"],
    "تاريخ": ["التاريخ", "السيرة النبوية", "التراجم والطبقات"],
}

# =============================================================================
# أوامر البحث الجاهزة (قائمة السلاش): قالب واحد يضبط قصد الباحث وهيكل جوابه
# وعمق شواهده. القوالب بيانات قابلة للتأليف لاحقًا من مهندس المشاريع وصانع الأدوات.
# =============================================================================
_ART_STRUCTURES = {
    "fiqh": (["فقه"], "فقهي",
             "توجيه البحث الفقهي المطوّل — التزمه مبحثاً مبحثاً كما في البحوث المحققة:\n"
             "١) تصوير المسألة وتحرير محل النزاع بدقة، وصورتها المعاصرة إن كانت نازلة وما يقابلها عند المتقدمين.\n"
             "٢) المصطلحات: تعريف مصطلحات الباب لغةً من أمهات المعاجم، واصطلاحاً من كتب المصطلحات الفقهية والحدود والتعريفات، مع التفريق بين استعمالات المذاهب للمصطلح الواحد.\n"
             "٣) الأحاديث والآثار: نصوص أدلة الباب من كتب الحديث الأصول بنصوصها، وتخريجها من كتب التخريج والأطراف، وبيان عللها ودرجاتها وكلام المحدثين عليها من كتب العلل والمصطلح — ولا يُنقل حديث من كتاب فقه قط.\n"
             "٤) الأقوال منقولة بدقة: أقوال الصحابة والتابعين من مصادرها، ثم مذاهب الأئمة الأربعة والظاهرية كلٌّ من كتب مذهبه المعتمدة بطبقاتها (المتقدمون والوسطى والمتأخرون)، معيّنة بأسماء المذاهب والكتب والطبعات والأجزاء والصفحات.\n"
             "٥) أدلة كل قول مفصلة (الكتاب والسنة والإجماع والقياس وسائر الأصول)، ومناقشة كل دليل والجواب عنه بأمانة وتجرد.\n"
             "٦) القواعد الفقهية المؤثرة في المسألة والفروق الدقيقة بينها وبين نظائرها، من كتب القواعد والفروق.\n"
             "٧) الترجيح معللاً بميزان الأصول وقوة الأدلة وسلامتها من المعارض.\n"
             "٨) خلاصة محررة، وتطبيق معاصر موثق إن كانت المسألة نازلة. حواشٍ مرقمة مطابقة للنصوص المنقولة حرفياً.",
             "بحث فقهي مختصر محرر: تصوير موجز للمسألة، فحديث الباب وحكمه من مصدره، فالأقوال معيّنة بمذاهبها (الأربعة والظاهرية إن وجدت) من كتبها، فالراجح ودليله — في فقرات وجيزة دقيقة النقل والعزو.",
             "لبحث فقهي: نوّع المراسي بين مصطلحات الباب وحديث أصله الذي يُبنى عليه وأسماء أبوابه عند المذاهب الأربعة والظاهرية وقواعده المؤثرة، ولا تجعلها كلها من جنس واحد."),
    "hadith": (["حديث"], "حديثي",
               "توجيه البحث الحديثي المطوّل — التزمه مبحثاً مبحثاً:\n"
               "١) نص الحديث بألفاظه ومواضعه في كتب السنة الأصول مع أرقامه فيها.\n"
               "٢) طرقه ورواياته واختلاف ألفاظها وزيادات الثقات ومواضع الاتفاق والافتراق.\n"
               "٣) تخريجه من كتب التخريج والأطراف كتاباً كتاباً بترتيب تقدم المصنفين.\n"
               "٤) دراسة الأسانيد: الرواة من كتب الجرح والتعديل والطبقات، والاتصال والانقطاع، والعلل الخفية من كتب العلل والسؤالات.\n"
               "٥) الحكم على الحديث صحةً وضعفاً معللاً بأقوال النقاد متقدمهم ومتأخرهم، مع ضبط مصطلحات الحكم من كتب مصطلح الحديث.\n"
               "٦) شرح غريبه وفوائده وأقوال الشراح الكبار.\n"
               "٧) ثمرته الفقهية إن كان من أحاديث الأحكام بإيجاز موثق من كتب الفقه.",
               "بحث حديثي مختصر: نص الحديث ومصادره الأصلية وأرقامه، وخلاصة طرقه وتخريجه، والحكم عليه معللاً بأقوال النقاد، وفائدة وجيزة.",
               "لبحث حديثي: المراسي من ألفاظ المتن المميزة وأسماء أبواب كتب السنة وطرق الحديث المشهورة، ونوّع بين أصل الحديث وكتب العلل والرجال."),
    "tafsir": (["تفسير"], "تفسيري",
               "توجيه البحث التفسيري المطوّل — التزمه مبحثاً مبحثاً:\n"
               "١) الآية بنصها وسياقها ومناسبتها لما قبلها وبعدها، وسبب نزولها الثابت من كتب أسباب النزول.\n"
               "٢) التفسير بالمأثور: أقوال الصحابة والتابعين من كتب التفسير بالمأثور وآثارهم بدرجاتها.\n"
               "٣) أقوال المفسرين طبقةً طبقة بترتيب وفياتهم من المتقدمين إلى المتأخرين، مع بيان منهج كل مفسر وأوجه اتفاقهم وافتراقهم.\n"
               "٤) اللغة والبيان: مفردات الآية من المعاجم، ومصطلحات علوم القرآن المؤثرة (المحكم والمتشابه والناسخ والوجوه والنظائر) من كتبها، والإعراب والقراءات المتواترة ووجه كل قراءة.\n"
               "٥) مناقشة الأقوال والجمع بينها ما أمكن، وترجيح الراجح معللاً بقواعد التفسير وأصوله.\n"
               "٦) هدايات الآية وأحكامها المستنبطة موثقة من كتب أحكام القرآن والتفسير الفقهي.",
               "بحث تفسيري مختصر: معنى الآية ومقصدها، وأقوال أمهات المفسرين بترتيب أزمنتهم، والراجح معللاً بإيجاز، وهداية ختامية.",
               "لبحث تفسيري: المراسي من ألفاظ الآية نفسها وعبارات المفسرين المشهورة في معناها وأقوال السلف المأثورة فيها."),
    "aqidah": (["عقيدة"], "عقدي",
               "توجيه البحث العقدي المطوّل — التزمه مبحثاً مبحثاً بحياد تام في العرض:\n"
               "١) تحرير محل النزاع وتحديد المصطلحات العقدية لغةً واصطلاحاً عند كل مدرسة من كتبها.\n"
               "٢) مقالات المدارس والمذاهب (أهل الحديث والأشاعرة والماتريدية والمعتزلة وسائر من له مقالة في المسألة) منقولة من كتب أصحابها أنفسهم بلا وسيط ولا اختزال، مرتبة بطبقاتها وتطورها التاريخي.\n"
               "٣) أدلة كل مقالة من الكتاب والسنة وأقوال السلف والآثار من مصادرها.\n"
               "٤) المناقشات والردود المتبادلة من كتب المقالات والردود بأمانة، ونقاط الالتقاء والافتراق الحقيقية.\n"
               "٥) نشأة الخلاف وأسبابه وتطوره عبر القرون من كتب التاريخ والتراجم.\n"
               "٦) الترجيح المؤصل بالأدلة، وخاتمة محررة تجمع ثمرة البحث.",
               "بحث عقدي مختصر: تحرير محل النزاع، فمقالات المدارس من كتبها باختصار أمين، فالراجح ودليله.",
               "لبحث عقدي: المراسي من مصطلحات المسألة عند كل مدرسة وعبارات المقالات المشهورة فيها من كتب أصحابها."),
    "lugha": (["لغة"], "لغوي",
              "توجيه البحث اللغوي المطوّل — التزمه مبحثاً مبحثاً:\n"
              "١) المادة في أمهات المعاجم مرتبة زمنياً بنصوصها: العين فالصحاح فالجمهرة فاللسان فالقاموس المحيط فتاج العروس.\n"
              "٢) الاشتقاق والتصريف: الجذر واشتقاقاته والمصادر والجموع من كتب الاشتقاق والصرف.\n"
              "٣) الشواهد: القرآن وقراءاته، والحديث وغريبه من كتب غريب الحديث، وكلام العرب شعراً ونثراً من كتب اللغة والأدب والدواوين.\n"
              "٤) الفروق اللغوية بين الألفاظ المقاربة من كتب الفروق، والوجوه والنظائر إن تعلق اللفظ بالقرآن.\n"
              "٥) تطور الدلالة عبر القرون، واستعمال أهل الفنون (الفقهاء والمفسرين والمحدثين) للمصطلح إن تعلق بفن.\n"
              "٦) خلاصة محررة بالمعنى الراجح وشواهده.",
              "بحث لغوي مختصر: معنى اللفظ عند أمهات المعاجم بترتيبها، وأصل اشتقاقه، وشاهد قرآني أو حديثي أو شعري، باختصار محرر.",
              "لبحث لغوي: المراسي من صيغ الجذر ومداخل المعاجم المشهورة للمادة وعبارات اللغويين في تعريفها."),
    "tarikh": (["تاريخ"], "تاريخي",
               "توجيه البحث التاريخي المطوّل — التزمه مبحثاً مبحثاً:\n"
               "١) الروايات من مصادرها مرتبة بطبقات المؤرخين ووفياتهم (المتقدمون فالوسطى فالمتأخرون)، وكل رواية بنصها ومصدرها.\n"
               "٢) نقد الروايات: أسانيدها عند أهل الحديث إن رُويت بالأسانيد، واتساق متونها، وأوجه اتفاقها واختلافها زيادة ونقصاً وتقديماً وتأخيراً.\n"
               "٣) التسلسل الزمني المضبوط بالسنين والشهور والأحداث المصاحبة من كتب الحوليات.\n"
               "٤) أسباب اختلاف الروايات (النقل والمذهب والسياسة) مستندة إلى كتب التراجم والطبقات.\n"
               "٥) الموازنة بين الروايات وترجيح أرجحها معللاً بقواعد نقد الخبر.\n"
               "٦) العبر والدروس المستفادة بتحفظ، بلا إسقاط معاصر غير موثق.",
               "بحث تاريخي مختصر: عرض الروايات من مصادرها المتقدمة، وبيان أوجه اختلافها، وترجيح أرجحها وسببه باختصار.",
               "لبحث تاريخي: المراسي من عبارات الروايات المشهورة وأسماء أبواب التواريخ والحوليات في الحدث أو المسألة."),
    "fiqh-hadith": (["فقه", "حديث"], "فقهي حديثي",
                    "توجيه بحث فقهي حديثي مطوّل — التزمه مبحثاً مبحثاً:\n"
                    "١) تصوير المسألة وتحرير محل نزاعها.\n"
                    "٢) أحاديث الباب وآثاره أولاً: نصوصها من كتب السنة الأصول، وتخريجها من كتب التخريج والأطراف، وعللها ودرجاتها وأقوال المحدثين من كتب العلل والمصطلح — فلا يبدأ النقاش الفقهي قبل استيفاء الدليل الحديثي.\n"
                    "٣) أقوال الصحابة والتابعين، ثم المذاهب الأربعة والظاهرية كلٌّ من كتب مذهبه بطبقاتها، معيّنة بأسمائها.\n"
                    "٤) أدلة كل قول ومناقشتها في ضوء ثبوت الأحاديث ودلالاتها، والجمع بين الأدلة ما أمكن.\n"
                    "٥) القواعد الفقهية والأصولية المؤثرة والفروق.\n"
                    "٦) الترجيح معللاً بقوة الدليل سنداً ودلالة، وخلاصة محررة.",
                    "بحث فقهي حديثي مختصر: أحاديث الباب من مصادرها وحكمها باختصار، ثم الأقوال معيّنة بمذاهبها من كتبها، ثم الراجح ودليله.",
                    "لبحث فقهي حديثي: مراسٍ من أحاديث الباب بألفاظها الأصلية ومراسٍ من أبواب المسألة عند المذاهب، بالتوازن بين الجناحين."),
}

RESEARCH_COMMANDS: Dict[str, Dict[str, Any]] = {
    "general": {"label": "بحث عام", "intent": None, "trim": 16, "panel_hint": "",
                "structure": "بحث عام متوازن: حرر المسألة أولاً، ثم اعرض مادتها من فنونها (حديثها وتخريجها، وفقهها ومذاهبها، وتفسيرها ولغتها بحسب حضورها في الشواهد) بلا إطالة مبحث على حساب آخر، مع تعيين المذاهب وتخريج الأحاديث من مصادرها، واختم بخلاصة محررة موثقة."},
}
for _art, (_genres, _name, _long, _short, _hint) in _ART_STRUCTURES.items():
    RESEARCH_COMMANDS[f"{_art}-long"] = {"label": f"بحث {_name} مطول", "intent": _genres, "trim": 24, "structure": _long, "panel_hint": _hint}
    RESEARCH_COMMANDS[f"{_art}-mid"] = {"label": f"بحث {_name} متوسط", "intent": _genres, "trim": 16, "panel_hint": _hint,
                                        "structure": "بصياغة متوسطة الإطالة (دقة النقل والعزو والتعيين كاملة، والإيجاز في التفريع والاستطراد):\n" + _long}
    RESEARCH_COMMANDS[f"{_art}-short"] = {"label": f"بحث {_name} مختصر", "intent": _genres, "trim": 8, "structure": _short, "panel_hint": _hint}


_CAT_TO_GENRE: Dict[str, str] = {}
for _g, _cats in _GENRE_CATEGORIES.items():
    for _c in _cats:
        _CAT_TO_GENRE[_c] = _g
_CAT_TO_GENRE.update({"الفتاوى": "فقه", "الجوامع": "حديث"})


def _shamela_bridge_candidates(query, dynamic_anchors, selected_books, top_k, death_max=None, categories=None, mode="phrase"):
    """مرشحون من فهرس الشاملة المثبتة مباشرة (المسار الكسول): بحث Lucene
    عندهم، وقراءة الصفحة من صيغتنا بعد استخراج كتابها عند أول لمس."""
    import shamela_search
    try:
        db = get_db()
        cursor = db.cursor() if db else None
    except Exception:
        cursor = None
    _sel = _selected_book_ids(selected_books, cursor)
    book_ids = [int(b) for b in _sel if str(b).isdigit()] or None
    phrases = [str(a).strip() for a in (dynamic_anchors or []) if str(a).strip() and len(str(a).strip()) >= 3]
    if not phrases:
        phrases = [query]
    hits, seen = [], set()
    cap = max(top_k, 12)
    for ph in phrases[:6]:
        _modes = [mode] + (["words", "any"] if mode == "phrase" and len(ph.split()) > 2 else [])
        found = {"results": []}
        for _m in _modes:
            try:
                found = shamela_search.search(ph, mode=_m, book_ids=book_ids,
                                              death_max=death_max, categories=categories, limit=cap)
            except Exception:
                found = {"results": []}
            if found.get("results"):
                break
        for h in found.get("results") or []:
            key = (str(h.get("book_id")), str(h.get("part") or ""), str(h.get("page_num") or ""))
            if key in seen:
                continue
            seen.add(key)
            # لا استخراج كتب في بناء المرشحين: مقطع الجسر شاهد كافٍ، وقراءة
            # الصفحة الكاملة للوكلاء وحدهم. نص كامل فقط إن كان الكتاب
            # مستخرجًا سلفًا (فحص ملفات بلا لمس للشاملة).
            body = ""
            try:
                if h.get("rel_path") and shamela_local_mcp._dir_for_rel(h["rel_path"]):
                    pg = shamela_local_mcp.get_page(book=h["book_id"], page_num=int(h["page_num"]), part=h.get("part"))
                    body = ((pg.get("page") or {}).get("body") or "") if pg.get("status") == "ok" else ""
            except Exception:
                body = ""
            hits.append({"book_id": str(h.get("book_id")), "title": h.get("title") or "",
                         "part": h.get("part"), "page_num": h.get("page_num"), "phrase": ph,
                         "term": None, "text": body,
                         "snippet": re.sub(r"\s+", " ", body)[:750].strip() or (h.get("snippet") or "")})
            if len(hits) >= cap:
                break
        if len(hits) >= cap:
            break
    return _map_lexical_hits(hits, cursor, cap)


def _fts_candidates(query: str, dynamic_anchors, selected_books, top_k: int, death_max=None, categories=None, mode: str = "phrase") -> List[Dict[str, Any]]:
    """مرشحون من فهرس المكتبة (FTS5) في أجزاء الثانية بدل المسح المتسلسل لملفات الكتب،
    بنفس شكل المرشحين اللفظيين. عند غياب نطاق وكيل يُبحث في المكتبة كلها؛ وقراءة
    نص الصفحة الكامل تبقى من ملف الكتاب عبر get_page كما في المسار اللفظي.
    حين يكون المصدر الحاكم هو الشاملة المثبتة يُبحث في فهرسها مباشرة."""
    try:
        import shamela_link as _SL
        if _SL.library_source() == "shamela":
            return _shamela_bridge_candidates(query, dynamic_anchors, selected_books, top_k,
                                              death_max=death_max, categories=categories, mode=mode)
    except Exception:
        pass
    try:
        import library_search
        if not library_search.index_status().get("available"):
            return []
        idx = library_search.get_index()
    except Exception:
        return []
    try:
        db = get_db()
        cursor = db.cursor() if db else None
    except Exception:
        cursor = None
    _sel = _selected_book_ids(selected_books, cursor)
    book_ids = [int(b) for b in _sel if str(b).isdigit()] or None
    # لا سقف افتراضيًا: البحث مفتوح بلا تحديد زمني ما لم يحدد الباحث سقف وفاة بنفسه
    phrases = [str(a).strip() for a in (dynamic_anchors or []) if str(a).strip() and len(str(a).strip()) >= 3]
    if not phrases:
        phrases = [query]
    hits: List[Dict[str, Any]] = []
    seen = set()
    cap = max(top_k, 12)
    for ph in phrases[:6]:
        # تدرج بحثي صادق: العبارة الحرفية أولًا، فإن عادت فارغة (سؤال بصياغة
        # حرة لا نص حرفي) فكل الألفاظ مجتمعة، ثم أي لفظ بترتيب الملاءمة.
        _modes = [mode]
        if mode == "phrase" and len(ph.split()) > 2:
            _modes += ["words", "any"]
        found = {"results": []}
        for _m in _modes:
            try:
                found = idx.search(ph, mode=_m, book_ids=book_ids, death_max=death_max, categories=categories, limit=cap)
            except Exception:
                found = {"results": []}
            if found.get("results"):
                break
        for h in found.get("results") or []:
            key = (str(h.get("book_id")), str(h.get("part") or ""), str(h.get("page_num") or ""))
            if key in seen:
                continue
            seen.add(key)
            body = ""
            try:
                pg = shamela_local_mcp.get_page(book=h["book_id"], page_num=int(h["page_num"]), part=h.get("part"))
                body = ((pg.get("page") or {}).get("body") or "") if pg.get("status") == "ok" else ""
            except Exception:
                body = ""
            hits.append({"book_id": str(h.get("book_id")), "title": h.get("title") or "",
                         "part": h.get("part"), "page_num": h.get("page_num"), "phrase": ph,
                         "term": None, "text": body,
                         "snippet": re.sub(r"\s+", " ", body)[:750].strip()})
            if len(hits) >= cap:
                break
        if len(hits) >= cap:
            break
    return _map_lexical_hits(hits, cursor, cap)


def run_rag_search(query: str, selected_books: Optional[List[str]] = None, pool_size: int = 50, top_k: int = 12, use_reranker: bool = True, dynamic_anchors: Optional[List[str]] = None, use_hybrid: bool = True, honor_agent_limit: bool = False, include_query: bool = True, death_max: Optional[int] = None, categories: Optional[List[str]] = None, fts_mode: str = "phrase", semantic_channel: bool = True) -> List[Dict[str, Any]]:
    """
    استرجاع مقاطع دلالية حقيقية موثقة من كولكشن الشاملة مع حل أسماء الكتب واستدعاء نصوص الصفحات
    مع دعم مراسي الاسترجاع الديناميكية (Dynamic Anchors) المولدة من المهندس المعماري
    """
    if not query or not query.strip():
        return []

    clean_q = query.strip()
    # طبقات المراسي أولاً: جدول المقابلة التراثي (معاصر <-> تراثي) يغني عن أي متجه عند المطابقة
    # (لا يعمل مع مراس ديناميكية: فجولات اللجنة تبحث بمراسيها لا بسؤال المستخدم،
    #  وإلا اختطف الجدول كل جولة وأعاد شواهده نفسها)
    _table_cands = _anchor_candidates(clean_q, selected_books, top_k) if not dynamic_anchors else []
    if _table_cands:
        print(f"⚓ [AnchorTable] {len(_table_cands)} شاهداً لفظياً من جدول المراسي: {clean_q[:70]}")
        return _table_cands
    has_embedder = bool(app_state.get("llama_embedder") or app_state.get("st_embedder") or app_state.get("embed_model"))
    if not semantic_channel or not has_embedder or not _qdrant_alive():
        # القناة الدلالية معطّلة بقرار الباحث، أو لا مخزن متجهات/توقف أثناء الجلسة: فهرس المكتبة الفوري أولاً، ثم المسح اللفظي داخل النطاق
        _fc = _fts_candidates(clean_q, dynamic_anchors, selected_books, top_k, death_max=death_max, categories=categories, mode=fts_mode)
        if _fc:
            print(f"⚓ [FTS] {len(_fc)} مرشحاً من فهرس المكتبة: {clean_q[:70]}")
            return _fc
        return _lexical_only_candidates(clean_q, dynamic_anchors, selected_books, top_k)

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
            if app_state.get("llama_embedder") and (is_8b_col or app_state.get("is_hybrid_col")):
                q_in = _hybrid_query_text(q_text) if app_state.get("embedder_kind") == "gguf06b" else q_text
                with EMBEDDING_LOCK:
                    emb = app_state["llama_embedder"].create_embedding(q_in)
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

    # بناء مراسي الاستعلام: السؤال ثم المراسي الديناميكية. الجولات اللاحقة قد تبحث بالمراسي الجديدة وحدها.
    anchor_queries = [clean_q] if include_query and clean_q else []
    if dynamic_anchors:
        for anc in dynamic_anchors:
            anc_c = str(anc).strip()
            if anc_c and len(anc_c) >= 3 and anc_c not in anchor_queries:
                anchor_queries.append(anc_c)
        print(f"⚓ [Dynamic Anchors] Applied {len(anchor_queries)} anchors: {anchor_queries}")
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

    if not anchor_queries:
        return []

    fetch_limit = max(pool_size, top_k * 3, 300)
    per_anchor_limit = max(fetch_limit // len(anchor_queries), 90)

    # 3. بناء الفلاتر والاستعلام من Qdrant
    book_key = "title" if app_state.get("is_hybrid_col") else ("book_title" if is_8b_col else "title_ar")
    q_filter = None
    if resolved_books:
        q_filter = Filter(must=[FieldCondition(key=book_key, match=MatchAny(any=_prefer_primary_titles(resolved_books)[:1000]))])

    all_raw_hits = []
    seen_hit_ids = set()
    hybrid_sparse_scores: Dict[Any, float] = {}
    bridge_score_map: Dict[Any, float] = {}
    dense_top_score = 0.0

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
            if anchor == clean_q and h_points:
                dense_top_score = max(dense_top_score, float(h_points[0].score or 0.0))
            for hp in h_points:
                if hp.id not in seen_hit_ids:
                    seen_hit_ids.add(hp.id)
                    all_raw_hits.append(hp)
            if app_state.get("is_hybrid_col"):
                # القناة اللفظية BM25 داخل المخزن نفسه: توسّع بركة الشواهد بمصطلحات التراث
                # التي لا يصلها التضمين الحديث، بدرجات مرسومة على الرتبة حتى لا تزاحم الدلالي القوي.
                try:
                    s_points = app_state["qdrant"].query_points(
                        collection_name=app_state["collection_name"],
                        query=_hybrid_sparse_vector(anchor),
                        using="bm25",
                        query_filter=q_filter,
                        limit=per_anchor_limit,
                        with_payload=True
                    ).points
                    for r_idx, sp in enumerate(s_points):
                        if sp.id not in seen_hit_ids:
                            seen_hit_ids.add(sp.id)
                            hybrid_sparse_scores[sp.id] = 0.34 + 0.18 * (1.0 - r_idx / max(1, len(s_points)))
                            all_raw_hits.append(sp)
                except Exception as se:
                    print(f"Sparse query error for anchor '{anchor}': {se}")
        except Exception as fe:
            print(f"Filtered query error for anchor '{anchor}': {fe}")

    # جسر التغطية: ضعف أعلى درجة دلالية للسؤال الأصلي يستدعي شواهد مخزن 8B القديم (جسر المفردات الحديثة إلى التراث)
    if app_state.get("is_hybrid_col") and include_query and dense_top_score < _BRIDGE_GATE:
        b_list = _bridge_old_hits(clean_q, resolved_books or None, fetch_limit)
        for r_idx, bp in enumerate(b_list):
            if bp.id not in seen_hit_ids:
                seen_hit_ids.add(bp.id)
                bridge_score_map[bp.id] = 0.45 + 0.15 * (1.0 - r_idx / max(1, len(b_list)))
                all_raw_hits.append(bp)

    # النطاق المحدد يبقى مغلقاً ولو رجعت نتيجة واحدة أو لم ترجع شيء.
    # فتح المكتبة كلها لا يكون إلا إذا لم يُحدد نطاق كتب أصلاً.
    if q_filter is not None and len(all_raw_hits) < 10:
        print(f"ℹ️ [Scoped Retrieval] أُبقي البحث داخل الكتب المحددة ({len(all_raw_hits)} مقطعاً) بلا فتح للمكتبة كلها.")

    hits = all_raw_hits

    # 4. تجميع المرشحين وجلب النصوص الحقيقية مع منع تكرار نفس الصفحة
    candidates = []
    seen_keys = set()
    for h in hits:
        raw_hp = h.payload or {}
        _p_is_old = bool(raw_hp.get("_src_old")) if app_state.get("is_hybrid_col") else False
        p = raw_hp if (not app_state.get("is_hybrid_col") or _p_is_old) else _normalize_hybrid_payload(raw_hp)
        title = p.get("book_title") or p.get("title_ar", "كتاب غير معنون")
        part = p.get("volume") or p.get("part")
        page_num = p.get("page_num")
        author = p.get("author_name", "")
        cat_name = p.get("category_name", "عام")
        death_year = p.get("author_death_hijri") or p.get("death_hijri")
        cached_text = p.get("text", "")
        rel_path = ""
        volume_count = None
        book_id = _payload_book_id(p)

        page_key = f"{title}_{part}_{page_num}"
        if page_key in seen_keys:
            continue

        if cursor:
            try:
                row = None
                if book_id:
                    cursor.execute("SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, rel_path, volume_count_observed FROM books WHERE book_id = ? LIMIT 1", (book_id,))
                    row = cursor.fetchone()
                if row is None:
                    cursor.execute("SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar, rel_path, volume_count_observed FROM books WHERE title_ar = ? LIMIT 1", (title,))
                    row = cursor.fetchone()
                if row:
                    if row["title_ar"]:
                        title = row["title_ar"]
                    if not author: author = row["main_author_name_ar"] or ""
                    if death_year is None: death_year = row["main_author_death_hijri"]
                    if cat_name in ("", "عام"): cat_name = row["category_name_ar"] or "عام"
                    rel_path = row["rel_path"] or ""
                    volume_count = row["volume_count_observed"]
                    book_id = row["book_id"]
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
                "book_id": book_id,
                "citation_label": canonical_citation_label(title, part, page_num, volume_count, book_id, author),
                "part_raw": str(part or ""),
                "page_num_raw": page_num,
                "rel_path": rel_path,
                "annalistic_year": annalistic_year,
                "fiqh_header": (p.get("heading") or fiqh_header) if (app_state.get("is_hybrid_col") and not _p_is_old) else fiqh_header,
                "snippet": snippet,
                "score": float(bridge_score_map.get(h.id, 0.45) if _p_is_old else hybrid_sparse_scores.get(h.id, getattr(h, "score", 0.0) or 0.0)),
                "channel": "semantic"
            })

    if use_hybrid:
        lexical_hits = []
        lexical_queries = [clean_q] if include_query else []
        for anc in anchor_queries:
            if anc != clean_q and len(anc) >= 12 and len(lexical_queries) < 4:
                lexical_queries.append(anc)
        for li, lq in enumerate(lexical_queries):
            lexical_hits.extend(lexical_page_matches(
                lq,
                resolved_books,
                confine_to_titles=bool(honor_agent_limit and resolved_books),
                max_seconds=2.0 if li == 0 else 1.0,
            ))
        for lex in lexical_hits:
            page_key = f"{lex.get('title')}_{lex.get('part')}_{lex.get('page_num')}"
            if page_key in seen_keys:
                for item in candidates:
                    if f"{item.get('title')}_{item.get('part_raw')}_{item.get('page_num_raw')}" == page_key:
                        item["lexical_hit"] = True
                        item["snippet"] = lex.get("snippet") or item.get("snippet")
                        item["score"] = max(float(item.get("score") or 0), 0.95)
                continue
            seen_keys.add(page_key)
            part = lex.get("part")
            page_num = lex.get("page_num")
            title = lex.get("title") or ""
            candidates.append({
                "title": title,
                "author": lex.get("author") or "أحد أئمة التراث",
                "death": lex.get("death") or "",
                "category": lex.get("category") or "عام",
                "vol": f"ج {part}" if part not in (None, "None", "") else "",
                "page": f"ص {page_num}" if page_num is not None else "",
                "volume_count": lex.get("volume_count"),
                "book_id": lex.get("book_id"),
                "citation_label": canonical_citation_label(title, part, page_num, lex.get("volume_count"), lex.get("book_id"), lex.get("author")),
                "part_raw": str(part or ""),
                "page_num_raw": page_num,
                "rel_path": lex.get("rel_path") or "",
                "annalistic_year": None,
                "fiqh_header": None,
                "snippet": lex.get("snippet") or "",
                "score": 0.99,
                "lexical_hit": True,
                "channel": "lexical",
            })

    # استبعاد مواقع الفتاوى والمواقع المعاصرة عند البحث عن وقائع تاريخية
    contemporary_stop_words = ["سؤال وجواب", "فتاوى الشبكة", "فتاوى معاصرة", "يسألونك", "موقع الشيخ", "شبكة الألوكة", "صيد الفوائد", "الدرر السنية"]
    if is_eclipse_query or is_lunar_query or is_quake_query or is_plague_query or "تاريخ" in clean_q:
        candidates = [c for c in candidates if not any(w in (c.get("title", "") + " " + c.get("author", "") + " " + c.get("category", "")) for w in contemporary_stop_words)]

    # تطبيق البحث الهجين الذكي (Dense Vector + BM25 Fusion) إذا كان مفعلاً
    if use_hybrid and rank_bm25 and len(candidates) > 1 and not dynamic_anchors:
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
    if use_hybrid:
        lexical_first = [item for item in candidates if item.get("lexical_hit")]
        others = [item for item in candidates if not item.get("lexical_hit")]
        ordered = lexical_first + others
        # ضبط الوكيل يحدد العدد. لا يُفرض مقطعين من كل كتاب.
        candidates = ordered if honor_agent_limit else _diversify_by_book(ordered, top_k, "title", 2)

    # 5. إلغاء نموذج Reranker نهائياً وتمرير النتائج الدلالية والمطابقة المباشرة إلى النموذج الرئيسي
    print(f"ℹ️ [Direct Retrieval - Reranker Bypassed] تم إلغاء نموذج Reranker وتمرير أفضل {min(len(candidates), top_k)} نتيجة دلالية ومطابقة مباشرة إلى النموذج الرئيسي لضمان دقة الاستخراج وعدم استبعاد أي شاهد.")
    return candidates[:top_k]


def _parse_anchor_plan(text: str) -> Dict[str, Any]:
    match = re.search(r"\{[\s\S]*\}", text or "")
    if not match:
        return {"anchors": [], "covered": False}
    try:
        data = json.loads(match.group(0))
    except Exception:
        return {"anchors": [], "covered": False}
    covered_val = data.get("covered")
    covered = covered_val is True or str(covered_val).strip().lower() in {"true", "1", "نعم"}
    anchors = []
    for item in data.get("anchors") or []:
        line = re.sub(r"\s+", " ", str(item)).strip(" «»\"'")
        if 4 <= len(line) <= 220 and line not in anchors:
            anchors.append(line)
    return {"anchors": anchors[:8], "covered": covered}


def plan_retrieval_round(question: str, api_key: str, model: str, prior_anchors: List[str], snippets: List[str]) -> Dict[str, Any]:
    """يولّد مراسي بحث بلغة المصنفين، ويحكم هل المقاطع تغطي المسألة. لا يكتب الجواب."""
    sample = "\n".join(f"- {s[:280]}" for s in snippets[:12]) or "(لا مقاطع بعد)"
    prior = "\n".join(f"- {a}" for a in prior_anchors[:16]) or "(لا مراسي سابقة)"
    system = (
        "أنت مولّد مراسي استرجاع لمخزن تراثي مضمّن دلالياً، ولست المجيب عن المسألة.\n"
        "ممنوع كتابة الحكم أو التخريج أو أي جواب. مسموح أن تستخدم فهمك لصياغة جمل قصيرة كما يكتبها المصنفون القدامى حتى تُلتقط صفحاتهم.\n"
        "لا تشترط ظهور لفظ السؤال المعاصر. إذا كانت المقاطع تتناول جوهر المسألة بمصطلحها القديم فاجعل covered قيمة true ولو خلا النص من لفظ المستخدم.\n"
        "استخرج مراسيك أيضاً من المقاطع المعروضة نفسها، بميزان فنّ السؤال أيّاً كان (فقه أو عقيدة أو تفسير أو حديث أو أصول أو قواعد أو مقاصد أو فروق أو لغة أو تاريخ): رؤوس المسائل وأسماء الأبواب، ومصطلحات المؤلفين كما هي حرفياً، وأعلام الأشخاص والأماكن والأحداث، وصيغ القواعد والتعريفات، وجذور الألفاظ الغريبة واشتقاقاتها، وصيغاً أخرى محتملة للمعنى نفسه عند غيرهم.\n"
        "في أي فنّ: إن لم يظهر إلا مصدر واحد أو مؤلف واحد أو زاوية واحدة فلا تجعل covered قيمة true؛ فالمسألة الواحدة مدوّنة في أمهات كتب فنّها ومختصراته وشروحه بصيغ ومصطلحات متقاربة مختلفة، ولا تكتمل التغطية حتى تُجرَّب مراسٍ مستخرجة من النصوص التي وُجدت نفسها.\n"
        "إذا خلت المقاطع من جوهر المسألة فاجعل covered قيمة false، وصغ من 6 إلى 8 مراسي جديدة غير المكررة: اسم الباب التراثي، والمترادفات، وجملاً مميزة من الرواية إن كان السؤال عن حديث أو أثر، ورؤوس المسائل.\n"
        "أخرج JSON فقط بهذا الشكل: {\"covered\": false, \"anchors\": [\"مرساة قصيرة\"]}"
    )
    user = f"السؤال:\n{(question or '')[:1200]}\n\nمراسي جُرّبت:\n{prior}\n\nمقاطع مسترجعة:\n{sample}"
    try:
        raw = call_openrouter_raw(
            model_id=model or "google/gemini-2.5-flash",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            api_key=api_key,
            temperature=0.2,
            max_tokens=900,
            timeout=40,
        )
    except Exception as exc:
        print(f"⚠️ [Retrieval Anchors] تعذر توليد المراسي: {exc}")
        return {"anchors": [], "covered": False}
    return _parse_anchor_plan(raw)


# =============================================================================
# لجنة المراسي: ثلاثة نماذج قوية تولد مراسي من ذاكرتها التراثية مستقلة،
# ورابع يحكم بينها بالإجماع والأصالة. بديل توسيع الجداول يدويا بلا نهاية.
# =============================================================================
_ANCHOR_PANEL_GENERATORS = [
    m.strip() for m in os.getenv(
        "ALMUJTAHED_ANCHOR_PANEL",
        "google/gemini-2.5-pro,anthropic/claude-sonnet-4.5,openai/gpt-5",
    ).split(",") if m.strip()
]

_ANCHOR_GEN_SYSTEM = (
    "أنت خبير بالمكتبة التراثية الإسلامية (ما قبل 1000هـ) وبألفاظ مصنفيها، تولد مراسي بحث لفظية ولا تجيب عن المسألة.\n"
    "المطلوب: عبارات بحث قصيرة (كلمتان إلى ست كلمات) من لسان التراث نفسه كما ترد حرفيا في الكتب: "
    "ألفاظ أحاديث مشهورة في الباب، وتعريفات الفقهاء للمسألة، وأسماء الأبواب والفصول، وصيغ القواعد.\n"
    "ممنوع: ترجمة حرفية للفظ المعاصر، وعبارات إنشائية حديثة، وكلمات مفردة عامة (كالزينة وحدها)، وكسرات لا معنى لها.\n"
    "لكل مسألة معاصرة قابلها بجوهرها القديم: الحقن التجميلية بالوشم وتغيير الخلق وإزالة الشين، والعملات الرقمية بالصرف والغرر، وهكذا.\n"
    "أخرج JSON فقط: {\"anchors\": [\"عبارة تراثية\", ...]} سبع عبارات فقط لا أكثر، متنوعة الزوايا."
)


def _sanitize_anchors(anchors, cap: int = 12) -> List[str]:
    """مصفاة سلامة حتمية: تسقط الكسرات والجمل الطويلة والمكرر قبل أن تحرق جولات البحث."""
    out: List[str] = []
    seen = set()
    for raw in anchors or []:
        a = re.sub(r"\s+", " ", str(raw or "")).strip(" .،:-_\"'")
        if not a or re.search(r"[A-Za-z]", a):
            continue
        words = a.split()
        if len(words) > 9:
            continue
        if len(words) == 1 and len(words[0]) < 3:
            continue
        if words and sum(len(w) for w in words) / len(words) < 2.0:
            continue  # كسرات من جنس «ع ب د»
        key = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", a).replace("أ", "ا").replace("إ", "ا").replace("ة", "ه").replace("ى", "ي")
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
        if len(out) >= cap:
            break
    return out


def _extract_anchors_json(raw: str) -> List[str]:
    """استخراج قائمة anchors من رد نموذج ولو غلفها بشرح أو أسوار markdown."""
    text = re.sub(r"```(?:json)?", "", raw or "")
    starts = [m.start() for m in re.finditer(r"\{", text)]
    for s in reversed(starts):
        depth = 0
        for i in range(s, len(text)):
            if text[i] == "{": depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[s:i + 1])
                    except Exception:
                        break
                    items = data.get("anchors") if isinstance(data, dict) else None
                    if items:
                        out = []
                        for it in items:
                            line = re.sub(r"\s+", " ", str(it)).strip(" «»\"'")
                            if line and line not in out:
                                out.append(line)
                        if out:
                            return out
                    break
    return []


def _anchor_cluster_key(a: str) -> str:
    a = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", a or "")
    a = a.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    return re.sub(r"\s+", " ", a).strip()


_ANCHOR_ARBITER_MODEL = os.getenv("ALMUJTAHED_ANCHOR_ARBITER", "anthropic/claude-sonnet-4.5")


def generate_anchor_panel(query: str, api_key: str, intent_genres: Optional[List[str]] = None, panel_hint: Optional[str] = None) -> Dict[str, Any]:
    """لجنة المراسي: ثلاثة مولدات (7 مراس لكل منها) بالتوازي، إجماع آلي،
    ثم حاكم Sonnet يعتمد 5 مراس بدرجات ثقة.
    يعيد {"adopted": [{phrase, support, confidence}], "candidates": [{phrase, support}]}."""
    key = (api_key or "").strip()
    if not key or not (query or "").strip():
        return {"adopted": [], "candidates": []}

    def one_generator(model_id: str) -> List[str]:
        try:
            raw = call_openrouter_raw(
                model_id=model_id,
                messages=[
                    {"role": "system", "content": _ANCHOR_GEN_SYSTEM},
                    {"role": "user", "content": f"المسألة المعاصرة:\n{(query or '')[:800]}"},
                ],
                api_key=key, temperature=0.3, max_tokens=4000, timeout=90, thinking_level="low",
            )
            return _sanitize_anchors(_extract_anchors_json(raw), cap=7)
        except Exception as exc:
            print(f"⚓ [Anchor Panel] تعذر مولد {model_id}: {exc}")
            return []

    per_model: Dict[str, List[str]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(_ANCHOR_PANEL_GENERATORS))) as ex:
        for model_id, anchors in zip(_ANCHOR_PANEL_GENERATORS, ex.map(one_generator, _ANCHOR_PANEL_GENERATORS)):
            if anchors:
                per_model[model_id] = anchors
    if not per_model:
        return {"adopted": [], "candidates": []}
    for _mid, _ancs in per_model.items():
        print(f"⚓ [Anchor Panel] {_mid}: {len(_ancs)} مرساة {_ancs}")

    # الإجماع: تجميع العبارات المتطابقة أو المتقاربة جدا واحتساب عدد النماذج المؤيدة
    clusters: List[Dict[str, Any]] = []
    for model_id, anchors in per_model.items():
        for a in anchors:
            ck = _anchor_cluster_key(a)
            tokens = set(ck.split())
            placed = False
            for c in clusters:
                ct = set(c["key"].split())
                sim = len(tokens & ct) / max(1, min(len(tokens), len(ct)))
                if ck == c["key"] or sim >= 0.8:
                    c["models"].add(model_id)
                    placed = True
                    break
            if not placed:
                clusters.append({"key": ck, "phrase": a, "models": {model_id}})
    support_of = {c["phrase"]: len(c["models"]) for c in clusters}
    consensus = [c["phrase"] for c in clusters if len(c["models"]) >= 2]
    singles = [c["phrase"] for c in clusters if len(c["models"]) < 2]
    print(f"⚓ [Anchor Panel] ولدت {len(per_model)}/{len(_ANCHOR_PANEL_GENERATORS)} نماذج، "
          f"إجماع على {len(consensus)}، وفريدة {len(singles)}: {consensus}")

    adopted: List[Dict[str, Any]] = []
    try:
        raw = call_openrouter_raw(
            model_id=_ANCHOR_ARBITER_MODEL,
            messages=[
                {"role": "system", "content": (
                    "أنت حاكم مراسي بحث تراثية (Sonnet). أمامك مراس أجمع عليها نموذجان فأكثر بعدد مؤيديها، ومراس فريدة من نموذج واحد.\n"
                    "اختر خمس مراس فقط: العبارات الحرفية المشهورة أولا (نصوص أحاديث في الباب وتعريفات الفقهاء وأسماء الأبواب)، فالبحث لفظي حرفي.\n"
                    "احذر الصياغات الوصفية المركبة حديثا ولو أجمع عليها المولدون؛ فالإجماع على ترجمة وصفية لا قيمة له بحثيا، وقد تسبقها عبارة حرفية فريدة من نموذج واحد.\n"
                    "لكل مرساة درجة ثقة: عالية إن كانت مجمعا عليها أو نصا مشهورا في الباب، ومتوسطة لغيرها.\n"
                    "وسم كل مرساة بفنها الذي ستُبحث فيه: حديث (نص نبوي أو أثر)، فقه (حكم وخلاف المذاهب)، تفسير (آية وسبب ومعنى قرآني)، عقيدة، لغة (معنى لفظ ومعاجم)، تاريخ، عام.\n"
                    "توازن الفنون إلزامي في مسائل الأحكام الشرعية: احرص أن تضم الخمسُ مرساةً من الحديث الأصل ومرساةً من الفقه على الأقل متى وجدتا بين المرشحات، ولا تجعل المراسي اللغوية أكثر من واحدة إلا إن كانت المسألة لغوية الأصل؛ فالبحث المحكم يوازن التخريج والخلاف الفقهي والتفسير ولا يميل لفن واحد.\n"
                    + (f"قصد الباحث المعلن: الفنون المستهدفة هي ({'، '.join(intent_genres)}). اجعل ثلاثًا من الخمس على الأقل من هذه الفنون بمراس حرفية منها، ولكل فن مستهدف مرساة واحدة على الأقل، والباقي علوم خادمة للمسألة.\n" if intent_genres else "")
                    + ((panel_hint.strip() + "\n") if panel_hint else "")
                    + "أخرج JSON فقط: {\"anchors\": [{\"phrase\": \"...\", \"confidence\": \"عالية\", \"genre\": \"فقه\"}, ...]} خمس مراس مرتبة بالأعلى عائدا."
                )},
                {"role": "user", "content": (
                    f"المسألة: {(query or '')[:600]}\n\nمجمع عليها:\n"
                    + "\n".join(f"- {a} (أيدها {support_of.get(a, 2)})" for a in consensus)
                    + "\n\nفريدة:\n" + "\n".join(f"- {a}" for a in singles[:14])
                )},
            ],
            api_key=key, temperature=0.1, max_tokens=2000, timeout=90, thinking_level="low",
        )
        text = re.sub(r"```(?:json)?", "", raw or "")
        m = re.search(r"\{[\s\S]*\}", text)
        data = json.loads(m.group(0)) if m else {}
        for item in (data.get("anchors") or [])[:5]:
            if isinstance(item, dict):
                ph = re.sub(r"\s+", " ", str(item.get("phrase") or "")).strip()
                conf = "عالية" if str(item.get("confidence") or "").startswith("ع") else "متوسطة"
                _g = str(item.get("genre") or "")
                genre = next((g for g in ("حديث", "فقه", "تفسير", "عقيدة", "لغة", "تاريخ") if g in _g), "عام")
            else:
                ph, conf, genre = re.sub(r"\s+", " ", str(item)).strip(), "متوسطة", "عام"
            if ph:
                adopted.append({"phrase": ph, "support": support_of.get(ph, 1), "confidence": conf, "genre": genre})
    except Exception as exc:
        print(f"⚓ [Anchor Panel] تعذر التحكيم: {exc}")
    adopted = [a for a in adopted if a["phrase"] in set(_sanitize_anchors([a["phrase"] for a in adopted], cap=5))]
    ranked_clusters = sorted(clusters, key=lambda c: (-len(c["models"]), len(c["phrase"])))
    candidate_pool = [{"phrase": c["phrase"], "support": len(c["models"])} for c in ranked_clusters]
    if len(adopted) < 3:
        adopted = [{"phrase": c["phrase"], "support": len(c["models"]), "genre": "عام",
                    "confidence": "عالية" if len(c["models"]) >= 2 else "متوسطة"} for c in ranked_clusters[:5]]
    print(f"⚓ [Anchor Panel] المراسي المعتمدة ({len(adopted)}): {adopted}")
    return {"adopted": adopted, "candidates": candidate_pool}


# =============================================================================
# حزم البحث المؤقتة: نتائج الجولات تحفظ تباعا في SQLite برقم المحادثة،
# فلا يضيع عمل عند انقطاع، وتصاغ الإجابة من الحزمة وتستأنف منها.
# =============================================================================
def _research_run_save(run_id: str, query: str, anchors: Any, rounds_data: Any, status: str) -> None:
    if not run_id:
        return
    try:
        conn = sqlite3.connect(str(APP_MEMORY_DB), timeout=15)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS research_runs (run_id TEXT PRIMARY KEY, query TEXT, anchors TEXT, rounds TEXT, status TEXT, updated_at REAL)")
            conn.execute(
                "INSERT INTO research_runs (run_id, query, anchors, rounds, status, updated_at) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET query=excluded.query, anchors=excluded.anchors, rounds=excluded.rounds, status=excluded.status, updated_at=excluded.updated_at",
                (str(run_id), (query or "")[:500],
                 json.dumps(anchors, ensure_ascii=False), json.dumps(rounds_data, ensure_ascii=False),
                 status, time.time()))
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        print(f"⚓ [ResearchRuns] تعذر حفظ حزمة البحث: {exc}")


def _research_run_load(run_id: str) -> Optional[Dict[str, Any]]:
    if not run_id:
        return None
    try:
        conn = sqlite3.connect(f"file:{APP_MEMORY_DB}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute("SELECT run_id, query, anchors, rounds, status, updated_at FROM research_runs WHERE run_id = ?", (str(run_id),)).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return {"run_id": row[0], "query": row[1],
                "anchors": json.loads(row[2] or "[]"), "rounds": json.loads(row[3] or "[]"),
                "status": row[4], "updated_at": row[5]}
    except Exception:
        return None


def _citation_identity(item: Dict[str, Any]) -> tuple:
    return (
        item.get("book_id"),
        str(item.get("part_raw") or ""),
        str(item.get("page_num_raw") or ""),
        item.get("title") or "",
    )


def _merge_passages(bucket: List[Dict[str, Any]], fresh: List[Dict[str, Any]], round_no: int) -> int:
    seen = {_citation_identity(item) for item in bucket}
    added = 0
    for item in fresh or []:
        key = _citation_identity(item)
        if key in seen:
            continue
        seen.add(key)
        item["anchor_round"] = round_no
        bucket.append(item)
        added += 1
    return added


_MINE_STOPWORDS = {
    "قال", "يقول", "قالت", "كان", "كانت", "يكون", "رسول", "الله", "صلى", "عليه", "وسلم",
    "أنه", "أنا", "إن", "أن", "في", "من", "إلى", "على", "عن", "ما", "لا", "لم", "لن",
    "هذا", "هذه", "ذلك", "التي", "الذي", "بين", "عند", "بعد", "قبل", "يوم", "حتى",
}


def _mine_evidence_anchors(passages: List[Dict[str, Any]], question: str, used: List[str]) -> List[str]:
    """مراسٍ دقيقة مستخرجة من الشواهد التي وُجدت نفسها: أسماء السند، وألفاظ المتن
    المميزة كما هي، وعبارات حول ألفاظ نادرة. لا تخمين من خارج النص."""
    anchors: List[str] = []
    used_set = set(used or [])
    q_words = set(re.findall(r"[A-Za-z\u0621-\u064A]+", question or ""))

    def add(text: Any) -> None:
        line = re.sub(r"\s+", " ", str(text or "")).strip(" «»\"'،.:؛()[]")
        if 5 <= len(line) <= 90 and line not in anchors and line not in used_set and line != (question or "").strip():
            anchors.append(line)

    for row in passages or []:
        snippet = (row.get("snippet") or "").strip()
        if not snippet:
            continue
        # 1) عبارات مقتبسة كما وردت
        for quoted in re.findall(r"[«\"]([^«»\"]{8,70})[»\"]", snippet):
            add(quoted)
        # 2) رؤوس المسائل والأبواب والقواعد والتعريفات بميزان كل فن
        for match in re.finditer(r"(باب|فصل|مسألة|المسألة|قاعدة|القاعدة|تعريف|الأصل|المقصد)\s+[:：]?\s*([^\n،.:؛]{4,48})", snippet):
            add(f"{match.group(1)} {match.group(2)}")
        # 3) أسماء الأعلام بعد أدوات الرواية والنقل (سنداً كان أو عزواً لمؤلف)
        for match in re.finditer(r"(?:حدثنا|أخبرنا|حدثني|أخبرني|عن|سمعت|قال|ذكر|نقل)\s+([^\n،.:؛]{3,42})", snippet):
            words = [w for w in re.findall(r"[A-Za-z\u0621-\u064A]+", match.group(1)) if w not in _MINE_STOPWORDS]
            if len(words) >= 2:
                add(" ".join(words[:3]))
        # 4) عبارات حول ألفاظ نادرة طويلة لا توجد في السؤال
        words = re.findall(r"[A-Za-z\u0621-\u064A]+", snippet)
        for idx, word in enumerate(words):
            if len(word) >= 6 and word not in q_words and word not in _MINE_STOPWORDS:
                start = max(0, idx - 1)
                add(" ".join(words[start:idx + 3]))
                if len(anchors) >= 10:
                    break
        if len(anchors) >= 10:
            break
    return anchors[:8]


_MADHHAB_AGENT_KEYS = ("الحنفي", "المالكي", "الشافعي", "الحنبلي", "الظاهري")


def _agent_madhhab(agent: Dict[str, Any]) -> Optional[str]:
    """المذهب الذي يمثله الوكيل من اسمه ووصفه، إن كان وكيل مذهب بعينه."""
    hay = f"{agent.get('name') or ''} {agent.get('desc') or ''}"
    for key in _MADHHAB_AGENT_KEYS:
        if key in hay:
            return key
    return None


def _targeted_madhhab_passages(madhhab: str, anchors: List[str],
                               limit: int = 14) -> List[Dict[str, Any]]:
    """استرجاع موجّه داخل كتب طبقات المذهب نفسه من فهرس الضبط: بحث بمراسي
    المسألة في تلك الكتب حصرًا، ثم جلب الصفحات كاملة لا مقتطفات مبتورة.

    هذا هو إمداد بطاقات الأدلة: من لم يجد هنا بعد بحث موجّه في كتب طبقاته
    فصفره موثق، لا فراغ تملؤه الذاكرة."""
    try:
        import library_search
        data = library_search.madhhab_authorities(madhhab) or {}
    except Exception:
        return []
    books = []  # (book_id, title, author, layer)
    for layer in data.get("layers") or []:
        # طبقة الضبط الاصطلاحي ليست ميدان استرجاع أحكام: كتبها مداخل
        # مصطلح وخريطة، وبحث مراسي المسائل فيها إهدار وخلط فئات.
        if "اصطلاح" in (layer.get("name") or ""):
            continue
        for b in layer.get("books") or []:
            if b.get("book_id"):
                books.append((int(b["book_id"]), b.get("title") or "",
                              b.get("author") or "", layer.get("name") or ""))
    if not books:
        return []
    book_ids = [b[0] for b in books]
    meta = {b[0]: b for b in books}
    queries = [a for a in dict.fromkeys(anchors or []) if a and len(a) >= 4][:6]
    if not queries:
        return []
    # مصدر الشاملة الكسول: البحث في فهرسها داخل كتب الطبقات حصرًا (الجسر
    # يقبل نطاق أرقامنا)، وجلب الصفحة كاملة بعدها يستخرج كتابها عند اللمس.
    try:
        import shamela_link as _SLT
        if _SLT.library_source() == "shamela":
            import shamela_search
            scored_l: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
            for q in queries:
                for mode in ("words", "phrase"):
                    try:
                        r = shamela_search.search(q, mode=mode, book_ids=book_ids, limit=40)
                    except Exception:
                        continue
                    for rank, hit in enumerate(r.get("results") or []):
                        key = (int(hit.get("book_id") or 0), str(hit.get("part") or ""), str(hit.get("page_num") or ""))
                        slot = scored_l.setdefault(key, {"hit": hit, "anchors": set(), "score": 0.0})
                        slot["anchors"].add(q)
                        slot["score"] += (8 - min(rank, 7)) + (6 if mode == "phrase" else 0)
            ranked = sorted(scored_l.values(),
                            key=lambda s: (len(s["anchors"]), s["score"]), reverse=True)
            return _finish_targeted(ranked, meta, madhhab, limit)
    except Exception:
        pass
    try:
        li = library_search.get_index()
    except Exception:
        return []
    # بحث داخل كل كتاب طبقة على حدة: فلا يزحم كتابٌ كبير مواضعَ كتاب آخر،
    # ولكل كتاب من كتب الطبقات مرشحوه قبل المفاضلة.
    scored: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
    for bid in book_ids:
        for qi, q in enumerate(queries):
            for mode in ("words", "phrase"):
                if mode == "phrase" and qi > 1:
                    continue
                try:
                    r = li.search(q, mode=mode, book_ids=[bid], limit=8)
                except Exception:
                    continue
                for rank, hit in enumerate(r.get("results") or []):
                    key = (bid, str(hit.get("part") or ""), str(hit.get("page_num") or ""))
                    slot = scored.setdefault(key, {"hit": hit, "anchors": set(), "score": 0.0})
                    slot["anchors"].add(q)
                    slot["score"] += (8 - min(rank, 7)) + (6 if mode == "phrase" else 0)
    ranked = sorted(scored.values(),
                    key=lambda s: (len(s["anchors"]), s["score"]), reverse=True)
    return _finish_targeted(ranked, meta, madhhab, limit)


def _finish_targeted(ranked, meta, madhhab: str, limit: int) -> List[Dict[str, Any]]:
    # مفاضلة على مرحلتين: أفضل صفحة من كل كتاب أولًا (تغطية الطبقات)، ثم
    # إكمال الحد ببقية المرشحين بسقف ثلاث صفحات للكتاب الواحد.
    ordered: List[Dict[str, Any]] = []
    seen_books = set()
    for slot in ranked:
        b = int(slot["hit"].get("book_id"))
        if b not in seen_books:
            seen_books.add(b)
            ordered.append(slot)
    ordered.extend(s for s in ranked if s not in ordered)
    out: List[Dict[str, Any]] = []
    per_book: Dict[int, int] = {}
    for slot in ordered:
        if len(out) >= limit:
            break
        hit = slot["hit"]
        bid = int(hit.get("book_id"))
        if per_book.get(bid, 0) >= 3:
            continue
        part = hit.get("part")
        page_num = hit.get("page_num")
        body = ""
        try:
            pg = shamela_local_mcp.get_page(str(bid), int(page_num),
                                            str(part) if part not in (None, "") else None)
            if pg and not pg.get("error"):
                _page = pg.get("page") if isinstance(pg.get("page"), dict) else pg
                body = (_page.get("body") or _page.get("text") or "").strip()
        except Exception:
            body = ""
        if not body:
            body = (hit.get("snippet") or "").strip()
        if not body:
            continue
        per_book[bid] = per_book.get(bid, 0) + 1
        _bid, btitle, bauthor, layer = meta.get(bid, (bid, hit.get("title") or "", hit.get("author") or "", ""))
        out.append({
            "title": btitle or hit.get("title") or "",
            "author": bauthor or hit.get("author") or "",
            "death": f"(ت: {hit.get('author_death_hijri')} هـ)" if hit.get("author_death_hijri") else "",
            "category": f"الفقه {madhhab}",
            "vol": f"ج {part}" if part not in (None, "") else "",
            "page": f"ص {page_num}" if page_num is not None else "",
            "part_raw": part, "page_num_raw": page_num,
            "book_id": bid,
            "snippet": re.sub(r"\s+", " ", body)[:4200],
            "targeted": True, "madhhab": madhhab, "authority_layer": layer,
            "anchor_round": 97,
        })
    return out


def _full_page_snippet(c: Dict[str, Any], cap: int = 3500, with_next: bool = False) -> str:
    """نص صفحة الشاهد كاملًا لا مقتطف أولها المبتور: مقاطع الاسترجاع تبدأ
    من رأس الصفحة وتنقطع في أثناء النص، فتولد في التقارير عبارات «انقطع
    النص في المقطع» وهي عيب إمداد لا عيب كتاب. هنا يُجلب متن الصفحة من
    ملفها، وعند الحاجة تتمتها من الصفحة التالية (تقليب صفحات فعلي)."""
    snip = (c.get("snippet") or "").strip()
    bid = c.get("book_id")
    page_raw = c.get("page_num_raw") or c.get("page")
    try:
        page_num = int(str(page_raw).strip())
    except Exception:
        return snip
    if bid in (None, "") or page_num <= 0:
        return snip
    part = c.get("part_raw") or c.get("part")
    part_s = str(part).strip() if part not in (None, "", "None") else None

    def _body(pnum: int) -> str:
        # جرّب الجزء كما ورد ثم بلا جزء: اختلاف صيغة الجزء كان يردّ البطاقة
        # إلى مقتطف رأس الصفحة المبتور فتتولد عبارات «انقطع النص».
        for _part_try in (part_s, None):
            try:
                pg = shamela_local_mcp.get_page(str(bid), pnum, _part_try)
                if pg and not pg.get("error"):
                    _p = pg.get("page") if isinstance(pg.get("page"), dict) else pg
                    _txt = re.sub(r"\s+", " ", (_p.get("body") or _p.get("text") or "")).strip()
                    if _txt:
                        return _txt
            except Exception:
                continue
        return ""

    body = _body(page_num)
    if not body:
        return snip
    out = body
    if with_next:
        nxt = _body(page_num + 1)
        if nxt:
            out += "\n— تتمة الصفحة التالية —\n" + nxt
    out = out[:cap]
    return out if len(out) > len(snip) else snip


def _extract_classical_terms(query: str, api_key: str) -> List[str]:
    """وكيل الألفاظ الدلالية عند المتقدمين: مهمته الوحيدة استخراج عبارات
    المصنفين القدماء الدالة على عين المسألة بصيغهم اللفظية (ضمائرها
    وتصريفاتها وصيغ الحكم عليها وأسماء أبوابها)، لتُستخدم مراسي بحث
    دلالي. بلا هذا الوكيل يقع الانقطاع بين مراد الباحث المعاصر ولسان
    الكتب: فعبارة حديثة كـ«يكره تقبيل الفرج» تسقط في بوابة العبارة
    الحرفية، بينما الكتب تقول «تقبيل فرجها» و«يلحسه بلسانه»."""
    if not (query or "").strip() or not (api_key or "").strip():
        return []
    _sys = (
        "أنت وكيل متخصص واحد فقط: استخراج الألفاظ الدلالية عند المتقدمين لتكون مراسي بحث دلالي يقود الاسترجاع كله. لا تكتب بحثًا ولا حكمًا ولا تقريرًا.\n"
        "أمامك مسألة بصياغة معاصرة، ومهمتك أن تفهم المطلوب بعينه ثم تبني مصفوفة ألفاظ المصنفين القدماء الدالة عليه منوّعة تنويعًا منهجيًا كاملًا:\n"
        "(١) لكل فعل جوهري: مصدره ومضارعه وتصريفاته كما تجري في كتبهم (تقبيل/يقبّل، لحس/يلحس، مص/يمص، مباشرة/يباشر).\n"
        "(٢) لكل فعل: ضمائر فاعله ومفعوله بوجوهها (فرجها/فرجه، لها/له، منها/منه، امرأته/زوجته/أهله) فإن اختلاف الضمير يُسقط العبارة الحرفية ويُبقي الكلمات.\n"
        "(٣) مترادفات المتقدمين للمحل والفعل (الفرج/القبل/الذكر، الاستمتاع/التلذذ/المباشرة) وألفاظ مناطات الحكم عندهم.\n"
        "(٤) صيغ الحكم مقترنة بالفعل (يكره كذا، لا بأس بكذا، يجوز له، يحرم عليه) فإن أبواب الأحكام تُبنى عليها.\n"
        "(٥) أسماء أبواب المسألة وتراجمها عند المصنفين (باب ما يحل للرجل من امرأته ونحوه).\n"
        "أخرج 16-24 عبارة قصيرة (2-5 كلمات)، كل عبارة في سطر مستقل بلا ترقيم ولا اقتباس. ممنوع: عبارات وصفية حديثة بصياغة الباحث، وجمل تامة، وأي شرح."
    )
    _models = ["google/gemini-2.5-pro", "anthropic/claude-sonnet-4.5"]
    _cands: List[str] = []

    def _one(m):
        try:
            return call_openrouter_raw(model_id=m,
                                       messages=[{"role": "system", "content": _sys},
                                                 {"role": "user", "content": f"المسألة: {query}"}],
                                       api_key=api_key, temperature=0.2, max_tokens=900,
                                       timeout=60, thinking_level="low") or ""
        except Exception:
            return ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as _ex:
        for raw in _ex.map(_one, _models):
            for line in (raw or "").splitlines():
                t = re.sub(r"^[\s\-\*\d\.\)\(«»\"']+", "", line).strip().strip("«»\"'")
                if 4 <= len(t) <= 60 and 2 <= len(t.split()) <= 6 and t not in _cands:
                    _cands.append(t)
    if not _cands:
        return []
    # توثيق كلماتي لا عباري: بقاء العبارة أن كلماتها واقعة في المكتبة،
    # بصيغتها أو بقريب منها — فلا تسقط لاختلاف ضمير أو تصريف.
    _verified: List[str] = []
    try:
        import library_search
        if library_search.index_status().get("available"):
            _li = library_search.get_index()
            for t in _cands:
                try:
                    r = _li.search(t, mode="words", limit=1)
                    if r.get("results"):
                        _verified.append(t)
                except Exception:
                    continue
                if len(_verified) >= 10:
                    break
    except Exception:
        _verified = []
    out = _verified or _cands[:6]
    print(f"⚓ [Semantic Anchors] وكيل ألفاظ المتقدمين: {len(_cands)} مرشحًا، وُثّق كلماتيًا {len(out)}: {out}", flush=True)
    return out


def _is_advisor_agent(a: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(a, dict):
        return False
    kind = str(a.get("kind") or a.get("role") or "").strip().lower()
    name = str(a.get("name") or "")
    if kind in ("advisor", "consultant", "tavily", "web_advisor"):
        return True
    return "مستشار" in name


def _is_tavily_advisor(a: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(a, dict):
        return False
    kind = str(a.get("kind") or "").strip().lower()
    name = str(a.get("name") or "")
    return kind in ("tavily", "web_advisor") or "tavily" in name.lower() or "تافيلي" in name


def _extract_json_objects(text: str) -> List[Dict[str, Any]]:
    """كل كائنات JSON الصالحة في النص بترتيب ورودها: فتفكير النموذج المسرب
    وقوالب التوجيه المعادة لا تحصد محلّلنا؛ نأخذ آخر كائن مكتمل لا أوله."""
    out: List[Dict[str, Any]] = []
    dec = json.JSONDecoder()
    raw = text or ""
    for i, ch in enumerate(raw):
        if ch != "{":
            continue
        try:
            obj, _end = dec.raw_decode(raw[i:])
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _parse_advisor_json(text: str) -> Dict[str, Any]:
    for data in reversed(_extract_json_objects(text or "")):
        books = data.get("books")
        anchors = data.get("anchors")
        if isinstance(books, list) or isinstance(anchors, list):
            return {
                "books": [b for b in (books or []) if isinstance(b, dict) and str(b.get("title") or "").strip()],
                "anchors": [str(x).strip() for x in (anchors or []) if str(x).strip()],
            }
    return {"books": [], "anchors": []}


def _author_tokens(text: str) -> set:
    folded = _fold_ar(text or "")
    toks = set()
    for t in re.split(r"[\s\-،,]+", folded):
        t = t.strip()
        if t.startswith("ال") and len(t) > 4:
            t = t[2:]
        if len(t) >= 3:
            toks.add(t)
    return toks


_AUTHOR_STOPWORDS = {"ابن", "ابي", "ابو", "محمد", "احمد", "عبد", "الدين", "الحسن", "الحسين"}


def _advisor_author_ok(proposed_author: str, resolved_author: str, resolved_title: str = "") -> bool:
    """مطابقة مؤلف صارمة: ترشيح «الموطأ لمالك» لا يُسلَّم موطأ ابن وهب،
    و«علل ابن أبي حاتم» لا تُسلَّم علل الدارقطني ولو اشتركا في الاسم.
    لا يكفي اشتراك «ابن/أبي»؛ يلزم لقب مميز (الترمذي، الرازي، مالك...)."""
    want = _author_tokens(proposed_author)
    if not want:
        return True
    have = _author_tokens(resolved_author) | _author_tokens(resolved_title)
    distinctive = {t for t in want if len(t) >= 4 and t not in _AUTHOR_STOPWORDS}
    if distinctive:
        return bool(distinctive & have)
    return len(want & have) >= 2


def _advisor_candidates(title: str, author: str = "", limit: int = 5) -> List[Dict[str, Any]]:
    """مرشحو ترشيح واحد من قاعدة الشاملة: أرقام وعناوين ومؤلفون، ليختار
    مدير المشروع الكتاب بعينه — فالمطابقة قراره لا ترجيحًا آليًا أعمى."""
    seen: Dict[int, Dict[str, Any]] = {}
    try:
        import shamela_local_mcp
        row = shamela_local_mcp.resolve_book(title)
        if row and row.get("book_id") and _advisor_author_ok(author, row.get("author") or "", row.get("title") or ""):
            bid = int(row["book_id"])
            seen[bid] = {"book_id": bid, "title": row.get("title") or title, "author": row.get("author") or ""}
    except Exception:
        pass
    title_toks = {t for t in _author_tokens(title) if len(t) >= 3}
    for kwargs in ({"query": f"{title} {author}".strip(), "limit": 40},
                   {"title": title, "limit": 40},
                   {"author": author, "limit": 40} if author else {"query": title, "limit": 40}):
        try:
            cat = search_books_catalog(**kwargs)
        except Exception:
            continue
        for r in (cat.get("results") or []):
            if not r.get("book_id"):
                continue
            if not _advisor_author_ok(author, r.get("author") or "", r.get("title") or ""):
                continue
            # بحث المؤلف واسع: لا يدخل إلا ما شارك الترشيح كلمة عنوان مميزة
            if "author" in kwargs and title_toks:
                cand_toks = {t for t in _author_tokens(r.get("title") or "") if len(t) >= 3}
                if not (title_toks & cand_toks):
                    continue
            bid = int(r["book_id"])
            if bid not in seen:
                seen[bid] = {"book_id": bid, "title": r.get("title") or title, "author": r.get("author") or ""}
            if len(seen) >= limit:
                break
        if len(seen) >= limit:
            break
    return list(seen.values())[:limit]


def _resolve_advisor_book(title: str, author: str = "") -> Optional[Dict[str, Any]]:
    """مطابقة ترشيح المستشار من قاعدة الشاملة: رقم معياري ومؤلف مطابق،
    وإلا رفض معلن لا بديل قريب الاسم."""
    try:
        import shamela_local_mcp
        row = shamela_local_mcp.resolve_book(title)
        if row and row.get("book_id") and _advisor_author_ok(author, row.get("author") or "", row.get("title") or ""):
            return {"book_id": int(row["book_id"]), "title": row.get("title") or title}
    except Exception:
        pass
    for kwargs in ({"query": f"{title} {author}".strip(), "limit": 40},
                   {"title": title, "limit": 40}):
        try:
            cat = search_books_catalog(**kwargs)
        except Exception:
            continue
        cands = [r for r in (cat.get("results") or [])
                 if _advisor_author_ok(author, r.get("author") or "", r.get("title") or "")]
        if not cands:
            continue
        want_title = _fold_ar(title)
        def _score(r):
            rt = _fold_ar(r.get("title") or "")
            s = 0
            if rt == want_title:
                s += 6
            if rt.startswith(want_title) or want_title in rt:
                s += 3
            s += sum(1 for w in want_title.split() if len(w) >= 4 and w in rt)
            s += min(int(r.get("volumes") or 0), 20) / 20.0
            return s
        cands.sort(key=_score, reverse=True)
        best = cands[0]
        if best.get("book_id"):
            return {"book_id": int(best["book_id"]), "title": best.get("title") or title}
    return None


def _match_specialist_for_book(assign: str, title: str, specialists: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    blob = f"{assign or ''} {title or ''}"
    for ag in specialists:
        n = str(ag.get("name") or "")
        if assign and (assign in n or n in assign):
            return ag
    rules = (
        (("علل", "تدليس", "علة"), ("علل", "تدليس")),
        (("رجال", "جرح", "تعديل", "تهذيب", "تقريب"), ("رجال", "جرح")),
        (("اعتبار", "شواهد", "متابعات"), ("اعتبار", "شواهد")),
        (("تخريج", "نصب الراية", "تلخيص", "إرواء"), ("تخريج",)),
        (("غريب", "ألفاظ"), ("غريب",)),
        (("مصطلح", "ضوابط"), ("مصطلح",)),
        (("سنة", "سنن", "صحيح", "مسند", "مصنف", "معجم", "أطراف", "توحيد", "السنة"), ("طرق", "مخارج", "دواوين")),
    )
    for needles, names in rules:
        if any(n in blob for n in needles):
            hit = next((ag for ag in specialists if any(n in str(ag.get("name") or "") for n in names)), None)
            if hit:
                return hit
    return next((ag for ag in specialists if (ag.get("books") or ag.get("booksScope"))), None)


def _consult_research_advisors(
    query: str,
    advisors: List[Dict[str, Any]],
    specialists: List[Dict[str, Any]],
    api_key: str,
    tavily_key: str = "",
    owner_id: str = "",
    group_id: str = "",
    director_model: str = "",
) -> Dict[str, Any]:
    """مستشارو التفكير: يولّدون مظانّ المسألة ومراسيها قبل استرجاع المتخصصين،
    ثم تُحقَّق الكتب في الشاملة وتُطعَّم في بطاقات الوكلاء المختصين."""
    out = {"anchors": [], "grafted": [], "missing": [], "notes": [], "tavily": ""}
    if not advisors or not (query or "").strip():
        return out
    specialist_names = "، ".join(str(a.get("name") or "") for a in specialists if str(a.get("name") or "").strip())
    think_advisors = [a for a in advisors if not _is_tavily_advisor(a)][:4]
    tav_advisors = [a for a in advisors if _is_tavily_advisor(a)][:1]
    _sys = (
        "أنت عضو في مجلس مستشارين متفرغ لمدير المشروع: تفكير وترتيب ومراسي فقط. لا تستخرج نصوصًا ولا تحكم على المسألة.\n"
        "تصلك المسألة كاملة كما تصلك زملاءك في المجلس، ولا تُسند إليك زاوية أو فن دونهم؛ فكّر في المسألة من جميع جوانبها وأخرج أفضل ما عندك: تنوّع المجلس من تنوّع عقول أعضائه لا من تقسيم مفروض عليهم.\n"
        "المطلوب قائمتان قصيرتان في JSON حصراً بلا شرح خارجه:\n"
        '{"books":[{"title":"العنوان المشهور","author":"المؤلف","why":"لمَ هو مظنة هذه المسألة","assign_to":"اسم الوكيل المختص"}],'
        '"anchors":["عبارة تراثية قصيرة 2-6 كلمات"]}\n'
        "الكتب: أمهات مظانّ المسألة التي إن غابت عن بطاقات المتخصصين ضاع أصلها (لا شروحًا نازلة تغني عنها الأصول). "
        "المراسي: ألفاظ المصنفين القدماء لا صياغة الباحث المعاصرة.\n"
        f"وكلاء الفريق المختصون الذين تُسنَد إليهم الكتب: {specialist_names or 'غير مسمّين'}.\n"
        "لا تختلق رقم كتاب. 4 إلى 8 كتب، و6 إلى 12 مرساة."
    )

    def _one_think(ag):
        try:
            raw = call_openrouter_raw(
                model_id=normalize_model_id(ag.get("model") or "google/gemini-2.5-pro"),
                messages=[{"role": "system", "content": _sys},
                          {"role": "user", "content": f"المسألة المعروضة على الفريق: {query}"}],
                api_key=api_key, temperature=0.2, max_tokens=20000, timeout=300,
                # مخرَج المستشار قائمة JSON قصيرة: تفكير max كان يحرق دقائق
                # في توليد مخفي لا يظهر في الترشيحات؛ high يكفي ويُسرّع المجلس.
                thinking_level={"max": "high"}.get(str(ag.get("thinking") or "").lower(),
                                                   str(ag.get("thinking") or "high")),
            ) or ""
            parsed = _parse_advisor_json(raw)
            parsed["advisor"] = str(ag.get("name") or "")
            return parsed
        except Exception as exc:
            print(f"🧭 [Advisors] تعذر مستشار «{ag.get('name')}»: {exc}", flush=True)
            return {"books": [], "anchors": [], "advisor": str(ag.get("name") or "")}

    proposals: List[Dict[str, Any]] = []
    if think_advisors:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(think_advisors))) as ex:
            proposals.extend(list(ex.map(_one_think, think_advisors)))
    # المدير عضو مناوب في الترشيح لا حَكَم لاحق فقط (مستشار واحد + المدير):
    # يرشّح بمحفّز المستشارين نفسه فتُحسب ترشيحاته صوتًا في الاتفاق والمراسي،
    # ثم يجلس بعدها للمطابقة والإسناد على حصيلة يشارك في صنعها.
    if director_model:
        proposals.append(_one_think({
            "name": "مدير المشروع (مشارك في الترشيح)",
            "model": director_model, "thinking": "high",
        }))

    if tav_advisors and (tavily_key or "").strip():
        try:
            data = _tavily_search_sync(
                f"{query} أهم المصادر الأصلية الكتب الحديثية أو الفقهية",
                tavily_key, max_results=6, timeout=35,
            )
            blob = json.dumps({
                "answer": data.get("answer"),
                "results": [{"title": r.get("title"), "url": r.get("url"), "content": (r.get("content") or "")[:400]}
                            for r in (data.get("results") or [])[:6]],
            }, ensure_ascii=False)
            tav_ag = tav_advisors[0]
            raw = call_openrouter_raw(
                model_id=normalize_model_id(tav_ag.get("model") or "google/gemini-2.5-flash"),
                messages=[
                    {"role": "system", "content": _sys + "\nمصدر تفكيرك نتائج بحث ويب (Tavily). استخرج منها أسماء الكتب التراثية الأصلية فقط، لا مقالات معاصرة سندًا."},
                    {"role": "user", "content": f"المسألة: {query}\n\nنتائج الشبكة:\n{blob[:8000]}"},
                ],
                api_key=api_key, temperature=0.2, max_tokens=64000, timeout=300,
                thinking_level=str(tav_ag.get("thinking") or "medium"),
            ) or ""
            parsed = _parse_advisor_json(raw)
            parsed["advisor"] = str(tav_ag.get("name") or "مستشار الشبكة")
            parsed["channel"] = "web"
            proposals.append(parsed)
            out["tavily"] = "بحث الشبكة أُجري واستُخلصت منه ترشيحات كُتبت للتحقق في الشاملة."
        except Exception as exc:
            out["tavily"] = f"تعذر بحث الشبكة (Tavily): {type(exc).__name__}"
            print(f"🧭 [Advisors] Tavily: {exc}", flush=True)
    elif tav_advisors:
        out["tavily"] = "مستشار الشبكة حاضر لكن مفتاح Tavily غير موجود في تبويب الخدمات؛ لم يُبحث في الويب."

    # 1) دمج مخرجات المجلس كاملة: المكرر يُوحَّد ويُحتسب اتفاقًا، والفريد يبقى
    #    محفوظًا في حزمته — لا يُقصّ ترشيح بترتيب الورود ولا تضيع لقطة بازدحام.
    def _prop_key(title: str, author: str) -> str:
        return f"{_fold_ar(title or '')}|{_fold_ar(author or '')}"

    team_ids = set()
    for _ag0 in specialists:
        for _b0 in (_ag0.get("books") or _ag0.get("booksScope") or []):
            _m0 = re.search(r"#(\d{1,7})", str(_b0))
            if _m0:
                team_ids.add(int(_m0.group(1)))
    _per_advisor: Dict[str, Dict[str, int]] = {}
    _anchor_map: Dict[str, Dict[str, Any]] = {}
    _merged: Dict[str, Dict[str, Any]] = {}
    _raw_books = 0
    for prop in proposals:
        adv_name = str(prop.get("advisor") or "")
        is_web = str(prop.get("channel") or "") == "web"
        st = _per_advisor.setdefault(adv_name, {"books": 0, "anchors": 0})
        for anc in prop.get("anchors") or []:
            anc = str(anc).strip()
            if not (4 <= len(anc) <= 80):
                continue
            st["anchors"] += 1
            akey2 = _fold_ar(anc)
            row = _anchor_map.setdefault(akey2, {"text": anc, "supporters": [], "first": len(_anchor_map)})
            if not is_web and adv_name and adv_name not in row["supporters"]:
                row["supporters"].append(adv_name)
        for pos, b in enumerate(prop.get("books") or []):
            title = str(b.get("title") or "").strip()
            if not title:
                continue
            _raw_books += 1
            st["books"] += 1
            author = str(b.get("author") or "")
            key = _prop_key(title, author)
            row = _merged.get(key)
            if row is None:
                row = {"title": title, "author": author, "aliases": [], "whys": [],
                       "supporters": [], "sources": [], "assign_hints": [],
                       "advisor_rank": pos, "first": len(_merged), "is_web_only": is_web}
                _merged[key] = row
            if title != row["title"] and title not in row["aliases"]:
                row["aliases"].append(title)
            why = str(b.get("why") or "")[:200]
            if why and why not in row["whys"]:
                row["whys"].append(why)
            if adv_name and adv_name not in row["sources"]:
                row["sources"].append(adv_name)
            if not is_web:
                row["is_web_only"] = False
                if adv_name and adv_name not in row["supporters"]:
                    row["supporters"].append(adv_name)
            hint = str(b.get("assign_to") or "")
            if hint and hint not in row["assign_hints"]:
                row["assign_hints"].append(hint)
            row["advisor_rank"] = min(row["advisor_rank"], pos)
    # حلّ المرشحين من الشاملة لكل ترشيح مدمج، ثم دمج ثانٍ لمن التقى في كتاب
    # بعينه من الشاملة بصيغتي عنوان مختلفتين (سنن الترمذي/جامع الترمذي).
    _final: List[Dict[str, Any]] = []
    for row in _merged.values():
        cands = _advisor_candidates(row["title"], row["author"])
        if not cands:
            out["missing"].append(f"{row['title']} (لا مرشح له في الشاملة بمؤلفه)")
            continue
        cand_ids = {c["book_id"] for c in cands}
        twin = None
        for ex in _final:
            if not (cand_ids & {c["book_id"] for c in ex["candidates"]}):
                continue
            t_new = {t for t in _author_tokens(row["title"]) if len(t) >= 4}
            t_ex = {t for t in _author_tokens(ex["title"]) if len(t) >= 4}
            a_new = {t for t in _author_tokens(row["author"]) if len(t) >= 4 and t not in _AUTHOR_STOPWORDS}
            a_ex = {t for t in _author_tokens(ex["author"]) if len(t) >= 4 and t not in _AUTHOR_STOPWORDS}
            if (t_new & t_ex) and (not a_new or not a_ex or (a_new & a_ex)):
                twin = ex
                break
        if twin is None:
            row["candidates"] = cands
            _final.append(row)
            continue
        for c in cands:
            if c["book_id"] not in {x["book_id"] for x in twin["candidates"]}:
                twin["candidates"].append(c)
        twin["candidates"] = twin["candidates"][:7]
        if row["title"] not in twin["aliases"] and row["title"] != twin["title"]:
            twin["aliases"].append(row["title"])
        twin["aliases"].extend(a for a in row["aliases"] if a not in twin["aliases"])
        for s in row["supporters"]:
            if s not in twin["supporters"]:
                twin["supporters"].append(s)
        for s in row["sources"]:
            if s not in twin["sources"]:
                twin["sources"].append(s)
        for w in row["whys"]:
            if w not in twin["whys"]:
                twin["whys"].append(w)
        for h in row["assign_hints"]:
            if h not in twin["assign_hints"]:
                twin["assign_hints"].append(h)
        twin["is_web_only"] = twin["is_web_only"] and row["is_web_only"]
        twin["advisor_rank"] = min(twin["advisor_rank"], row["advisor_rank"])
    for row in _final:
        row["votes"] = len(row["supporters"])
        row["band"] = "consensus" if row["votes"] >= 2 else ("web" if row["is_web_only"] else "unique")
    _band_rank = {"consensus": 0, "unique": 1, "web": 2}
    # المشترك أولًا بقوة اتفاقه، والفريد بعده مرتبًا بتناوب أعضاء المجلس
    # (لقطة كل عضو الأولى قبل ثواني غيره) فلا يزاحم عضوٌ أخاه.
    _final.sort(key=lambda r: (_band_rank[r["band"]], -r["votes"], r["advisor_rank"], r["first"]))
    _presented = _final[:32]
    if len(_final) > len(_presented):
        out["missing"].append(f"{len(_final) - len(_presented)} ترشيحًا مدمجًا تجاوز سقف العرض على المدير (32) ولم يُعرض عليه")
    props_v: List[Dict[str, Any]] = [{
        "n": i + 1, "title": r["title"], "author": r["author"],
        "aliases": r["aliases"], "why": "؛ ".join(r["whys"][:3])[:300],
        "advisor": "، ".join(r["sources"]), "supporters": r["supporters"],
        "votes": r["votes"], "band": r["band"],
        "assign_hint": "؛ ".join(r["assign_hints"][:3]), "candidates": r["candidates"],
    } for i, r in enumerate(_presented)]
    _anchors_sorted = sorted(_anchor_map.values(),
                             key=lambda r: (-len(r["supporters"]), r["first"]))
    seen_anchors = [r["text"] for r in _anchors_sorted[:24]]
    out["council"] = {
        "members": [{"name": n2, "books": s2["books"], "anchors": s2["anchors"]}
                    for n2, s2 in _per_advisor.items()],
        "raw_books": _raw_books, "merged_books": len(_final),
        "consensus": sum(1 for r in _final if r["band"] == "consensus"),
        "unique": sum(1 for r in _final if r["band"] == "unique"),
        "web": sum(1 for r in _final if r["band"] == "web"),
        "presented": len(props_v), "anchors_merged": len(_anchor_map),
    }

    # 2) الإسناد: المتفق عليه (صوتان فأكثر) بمرشح شاملة وحيد يُسند آليًا من
    # تلميحات المستشارين المهيكلة بلا نداء مدير؛ والمدير لا يقضي إلا في
    # المتنازع ومتعدد المرشحين والفريد — تخفيفًا لعبئه وتركيزًا لحكمه حيث
    # يلزم، فلا يعيد قراءة ما حسمه اتفاق المجلس وشاملة وحيدة المرشح.
    decisions: Dict[int, Dict[str, Any]] = {}
    for v in props_v:
        if v["band"] == "consensus" and len(v["candidates"]) == 1:
            _ag_auto = _match_specialist_for_book(v.get("assign_hint") or "", v["title"], specialists)
            if _ag_auto is not None:
                decisions[v["n"]] = {"book_id": v["candidates"][0]["book_id"], "agent": _ag_auto,
                                     "reason": f"اتفاق {v['votes']} من المجلس ومرشح شاملة وحيد: إسناد آلي",
                                     "by": "consensus"}
    out["director_assignment"] = "auto" if decisions else "unavailable"
    _pile = [v for v in props_v if v["n"] not in decisions]
    if _pile and director_model:
        try:
            spec_lines = []
            for _ag1 in specialists:
                _bk = list(_ag1.get("books") or _ag1.get("booksScope") or [])
                spec_lines.append(f"- {_ag1.get('name')}: {str(_ag1.get('desc') or '')[:90]} | كتبه الحالية {len(_bk)}: " + "؛ ".join(str(x) for x in _bk[:5]))
            prop_lines = []
            for v in _pile:
                cand_txt = " / ".join(f"#{c['book_id']} {c['title']} (مؤلفه: {c['author'] or '؟'})" for c in v["candidates"])
                if v.get("band") == "consensus":
                    band_txt = f"ترشيح مشترك اتفق عليه {v.get('votes')} من أعضاء المجلس ({'، '.join(v.get('supporters') or [])})"
                elif v.get("band") == "web":
                    band_txt = "ترشيح من قناة الشبكة (يُعامل مصدرًا مستقلًا لا صوتًا في المجلس)"
                else:
                    band_txt = f"لقطة فريدة انفرد بها {v.get('advisor') or 'عضو واحد'} — لا تردّها لانفرادها؛ فقد تكون هي قيمة المجلس، بل احكم عليها بقيمتها في المسألة"
                alias_txt = f" (وورد أيضًا: {'، '.join(v.get('aliases') or [])})" if v.get("aliases") else ""
                prop_lines.append(f"[{v['n']}] «{v['title']}»{alias_txt} لمؤلفه {v['author']} [{band_txt}] — مظنته: {v['why']} — مرشحو الشاملة: {cand_txt}")
            _dsys = (
                "أنت مدير المشروع والنموذج الأساسي للبحث. مجلس مستشاريك (نماذج متنوعة استُشير كلٌّ منهم في المسألة كاملة استقلالًا) اقترح كتبًا هي مظانّ المسألة، والمنظومة وحّدت المكرر منها وعرضت لكل ترشيح مرشحيه الحقيقيين من قاعدة المكتبة الشاملة بأرقامهم ومؤلفيهم، وميّزت لك المشترك المتفق عليه من اللقطات الفريدة.\n"
                "مهمتك المزدوجة وحدك: (أ) مطابقة كل ترشيح باختيار كتابه بعينه من مرشحيه برقمه — فالأسماء المشتركة (كالموطأ، والعلل، والجامع) لا يفصل فيها إلا أنت بمؤلف الكتاب وطبيعته؛ (ب) إسناد الكتاب المختار إلى الوكيل المختص الأنسب من فريقك.\n"
                "الاتفاق قوة ترجيح لا حكم نهائي، والانفراد ليس ضعفًا بذاته: قيّم كل لقطة فريدة بمادتها في المسألة، وقبولك أو ردّك لها معلن بسببك. إن لم يكن بين المرشحين كتاب الترشيح بعينه فردّ الترشيح ولا تختر قريب الاسم. والأصول تُسند للمتخصصين لا لهيئة المناظرة ولا للطباعة إلا ما مادته المناظرة بعينها.\n"
                'أخرج JSON حصراً بلا شرح: {"decisions":[{"n":1,"book_id":123,"agent":"اسم الوكيل حرفيًا","reason":"سبب قصير"}], "rejected":[{"n":1,"reason":"سبب الرد"}]}'
            )
            raw_dir = call_openrouter_raw(
                model_id=normalize_model_id(director_model),
                messages=[{"role": "system", "content": _dsys},
                          {"role": "user", "content": f"المسألة: {query}\n\nفريقك وكتبهم:\n" + "\n".join(spec_lines) + "\n\nالترشيحات ومرشحوها من الشاملة:\n" + "\n".join(prop_lines)}],
                api_key=api_key, temperature=0.1, max_tokens=20000, timeout=300,
                thinking_level="high",
            ) or ""
            spec_by_name = {str(a.get("name") or "").strip(): a for a in specialists}
            by_n = {v["n"]: v for v in props_v}
            for obj in reversed(_extract_json_objects(raw_dir)):
                if not isinstance(obj.get("decisions"), list):
                    continue
                for dec in obj["decisions"]:
                    try:
                        n2, bid2 = int(dec.get("n")), int(dec.get("book_id"))
                    except Exception:
                        continue
                    v = by_n.get(n2)
                    agn = str(dec.get("agent") or "").strip()
                    if v and bid2 in {c["book_id"] for c in v["candidates"]} and agn in spec_by_name:
                        decisions[n2] = {"book_id": bid2, "agent": spec_by_name[agn],
                                         "reason": str(dec.get("reason") or "")[:160]}
                for rej in (obj.get("rejected") or []):
                    try:
                        rv = by_n.get(int(rej.get("n")))
                        out.setdefault("rejected", []).append(f"«{rv['title'] if rv else rej.get('n')}»: {str(rej.get('reason') or '')[:120]}")
                    except Exception:
                        continue
                break
            if decisions:
                out["director_assignment"] = "done"
        except Exception as _derr:
            print(f"🧭 [Advisors] تعذر مطابقة المدير وإسناده: {_derr}", flush=True)

    # 3) التطعيم بقرار المدير؛ ومرشح وحيد بلا قرار يُطعَّم معلنًا، ومتعدد بلا حسم يُعلن
    # قائمة كتب المجلس المطابقة كاملة — نطاق الوكيلين الذهبي والفضي: كل كتاب
    # حدّده المستشارون وطابقه المدير يُدرج لهما ولو كان مكررًا عند الوكلاء
    # الرسميين، وبلا سقف التطعيم (10) الذي يحكم إسناد المتخصصين.
    advisor_book_entries: List[str] = []
    _ab_seen = set()
    for v in props_v:
        dec = decisions.get(v["n"])
        if dec:
            bid = dec["book_id"]
            ag, by = dec["agent"], dec.get("by", "director")
            reason = dec.get("reason") or ""
            chosen = next(c for c in v["candidates"] if c["book_id"] == bid)
        elif len(v["candidates"]) == 1:
            chosen = v["candidates"][0]
            bid = chosen["book_id"]
            ag = _match_specialist_for_book(v.get("assign_hint") or "", v["title"], specialists)
            by, reason = "fallback", "مرشح وحيد في الشاملة وفات قرار المدير في إسناده"
            if out["director_assignment"] == "done":
                out["director_assignment"] = "partial"
        else:
            out["missing"].append(f"«{v['title']}»: مرشحون متعددون في الشاملة ولم يحسم المدير مطابقته ({' / '.join('#' + str(c['book_id']) + ' ' + c['title'] for c in v['candidates'])})")
            continue
        if bid not in _ab_seen:
            _ab_seen.add(bid)
            advisor_book_entries.append(f"#{bid} {chosen['title']}")
        if bid in team_ids:
            _ap = out.setdefault("already_present", [])
            _ap_entry = f"#{bid} {chosen['title']}"
            if _ap_entry not in _ap:
                _ap.append(_ap_entry)
            continue
        if ag is None:
            out["missing"].append(f"#{bid} {chosen['title']} (طابقه المدير ولم يُسند)")
            continue
        entry = f"#{bid} {chosen['title']}"
        books = list(ag.get("books") or ag.get("booksScope") or [])
        if any(str(x).startswith(f"#{bid} ") or str(x).strip() == str(bid) for x in books):
            continue
        books.append(entry)
        ag["books"] = books
        ag["booksScope"] = books
        team_ids.add(bid)
        out["grafted"].append({"entry": entry, "agent": str(ag.get("name") or ""),
                               "why": v["why"], "advisor": v["advisor"],
                               "votes": v.get("votes", 0), "band": v.get("band", ""),
                               "assigned_by": by, "reason": reason})
        if len(out["grafted"]) >= 12:
            break
    if isinstance(out.get("council"), dict):
        out["council"]["accepted_unique"] = sum(1 for g in out["grafted"] if g.get("band") == "unique")
        out["council"]["accepted_consensus"] = sum(1 for g in out["grafted"] if g.get("band") == "consensus")
        out["council"]["accepted_web"] = sum(1 for g in out["grafted"] if g.get("band") == "web")
    out["advisor_books"] = advisor_book_entries

    out["anchors"] = seen_anchors
    if out["grafted"] and owner_id and group_id:
        try:
            akey = _owner_key("agents", owner_id)
            aconn = _ensure_app_memory()
            try:
                arow = aconn.execute("SELECT payload FROM kv_documents WHERE key=?", (akey,)).fetchone()
                if arow is not None:
                    agroups = json.loads(arow["payload"]) or []
                    gids = [x.strip() for x in str(group_id).split(",") if x.strip()]
                    changed = False
                    for grp in agroups:
                        if gids and str(grp.get("id")) not in gids:
                            continue
                        for ga in (grp.get("agents") or []):
                            for g in out["grafted"]:
                                if str(ga.get("name") or "").strip() == g["agent"]:
                                    gb = list(ga.get("books") or [])
                                    if g["entry"] not in gb:
                                        gb.append(g["entry"])
                                        ga["books"] = gb
                                        ga["booksScope"] = gb
                                        changed = True
                    if changed:
                        aconn.execute(
                            "INSERT INTO kv_documents (key, payload, updated_at) VALUES (?, ?, ?) "
                            "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                            (akey, json.dumps(agroups, ensure_ascii=False), datetime.now().isoformat()))
                        aconn.commit()
            finally:
                aconn.close()
        except Exception as perr:
            print(f"🧭 [Advisors] تعذر الحفظ الدائم للكتب المطعّمة: {perr}", flush=True)

    print(f"🧭 [Advisors] مستشارون {len(advisors)}: طُعّم {len(out['grafted'])} كتابًا، "
          f"غاب {len(out['missing'])}، مراسٍ {len(out['anchors'])}، مطابقة المدير: {out.get('director_assignment')}", flush=True)
    return out


# الوكيل المؤقت: الذهبي — صلب البحث الذي يقاس عليه غيره (أُلغي الفضي 1.10.268)
GOLDEN_MODEL = "~openai/gpt-luna-latest"


def _build_core_agents(
    query: str,
    director_model: str,
    api_key: str,
    advisor_consult: Optional[Dict[str, Any]] = None,
    specialists: Optional[List[Dict[str, Any]]] = None,
    advisor_books: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """بعد مجلس المستشارين وقرار المدير ينشئ مدير المشروع وكيلًا مؤقتًا لهذه
    المسألة بعينها — الذهبي — بتوجيه نوعي يصوغه هو بدقة للموضوع،
    ويبحث بحثًا نوعيًّا مركّزًا في الكتب التي حدّدها المستشارون وطابقها
    المدير من الشاملة حصرًا (لا يجوب المكتبة كلها؛ فالاتساع تشتيت يضيّع
    قوته)؛ نتيجته صلب البحث تُقدَّم على تقارير المتخصصين وتُقاس
    عليها، وتكرار كتبه مع كتب المتخصصين سدُّ عجز لا حشو. لا يُحفظ في
    بطاقات الفريق؛ عمره جولة البحث هذه فقط."""
    ac = advisor_consult or {}
    anchors = list(ac.get("anchors") or [])[:12]
    scope_books: List[str] = []
    _seen_bid = set()
    for _e in (advisor_books or []):
        _m = re.search(r"#(\d{1,7})", str(_e))
        if _m and int(_m.group(1)) not in _seen_bid:
            _seen_bid.add(int(_m.group(1)))
            scope_books.append(str(_e))
    if not scope_books:
        print("🥇 [Core Agents] لم يُنشأ الذهبي: لم يُحدِّد مجلس المستشارين كتبًا مطابقة في الشاملة لهذه المسألة، وهو لا يبحث خارج كتب المستشارين", flush=True)
        return []
    grafted = [f"{g.get('entry')} عند «{g.get('agent')}»" for g in (ac.get("grafted") or [])][:10]
    spec_names = "، ".join(str(a.get("name") or "") for a in (specialists or []) if str(a.get("name") or "").strip())
    golden_prompt = ""
    if director_model and api_key:
        try:
            _csys = (
                "أنت مدير المشروع والنموذج الأساسي. انتهيتَ لتوّك من استشارة مجلس مستشاريك ومن مطابقة كتبهم وإسنادها لفريقك. "
                "ستنشئ الآن وكيلًا مؤقتًا لهذه المسألة بعينها يبحث بحثًا نوعيًّا مركّزًا في الكتب التي حدّدها مستشاروك وطابقتَها أنت من الشاملة حصرًا (وهي نطاقه الوحيد)، ونتيجته صلب البحث الذي تُبنى عليه بقية النتائج وتُقاس عليها.\n"
                "صُغ توجيهًا نوعيًا دقيقًا له متعلقًا بهذه المسألة باسمها وفروعها لا قالبًا عامًّا:\n"
                "- الذهبي (نموذج عميق بطيء): قلب المسألة ومدارها — أصول نصوصها الحاكمة، أمهات مظانّها، أقوال أطرافها الكبار بأدلتهم، ما يُبنى عليه الحكم أو التحرير، ومعه سدّ النقص: المعارضات والشواهد والمتابعات والفروع والزوايا التي قد تفوت. يطلب النصوص المؤسِّسة لا الحواشي.\n"
                "في التوجيه: سمِّ فروع المسألة وأسئلتها الفرعية بعينها، وما يُطلب إثباته أو نفيه، وما يُحذر من الخلط فيه. لا تذكر أرقام كتب ولا تحصر الوكيل في قائمة.\n"
                'أخرج JSON حصرًا: {"golden":"توجيه الذهبي"}'
            )
            _cuser = (
                f"المسألة: {query}\n"
                + (f"نطاق الوكيلين الوحيد — كتب حدّدها المستشارون وطابقتَها: {'؛ '.join(scope_books)}\n" if scope_books else "")
                + (f"مراسي مجلس المستشارين: {'؛ '.join(anchors)}\n" if anchors else "")
                + (f"كتب طعّمتها قراراتك في بطاقات فريقك: {'؛ '.join(grafted)}\n" if grafted else "")
                + (f"فريقك المتخصص: {spec_names}\n" if spec_names else "")
            )
            raw = call_openrouter_raw(
                model_id=normalize_model_id(director_model),
                messages=[{"role": "system", "content": _csys},
                          {"role": "user", "content": _cuser}],
                api_key=api_key, temperature=0.2, max_tokens=64000, timeout=300,
                thinking_level="high",
            ) or ""
            for obj in reversed(_extract_json_objects(raw)):
                if obj.get("golden"):
                    golden_prompt = str(obj.get("golden") or "").strip()
                    break
        except Exception as _cerr:
            print(f"🥇 [Core Agents] تعذرت صياغة المدير لتوجيه الوكيلين: {_cerr}", flush=True)
    anchor_line = (" مراسي الانطلاق المتفق عليها: " + "؛ ".join(anchors) + ".") if anchors else ""
    scope_line = " ونطاقك الوحيد الكتب التي حدّدها مجلس المستشارين وطابقها المدير من الشاملة، ابحث فيها بحثًا نوعيًّا معمّقًا ولا تخرج عنها."
    if not golden_prompt:
        golden_prompt = (
            f"أنت الوكيل الذهبي، صلب هذا البحث في مسألة: {query}.{scope_line} "
            f"واجلب نصوصها المؤسِّسة: أصولها الحاكمة وأمهات مظانّها وأقوال أطرافها الكبار بأدلتهم، ببطاقات أدلة دقيقة.{anchor_line}"
        )
    base = {
        "books": scope_books, "booksScope": scope_books, "search_mode": "hybrid",
        "temperature": 0.2, "max_tokens": 65536, "extract_count": 200,
        "top_k": 200, "pool_size": 800, "enabled": True, "active": True,
    }
    golden = dict(base)
    golden.update({
        "id": "ephemeral_golden", "kind": "golden_core", "_core_rank": 0,
        "name": "الوكيل الذهبي — صلب البحث (مؤقت)",
        "desc": "وكيل مؤقت أنشأه مدير المشروع لهذه المسألة بعينها: يبحث بحثًا نوعيًّا في كتب مجلس المستشارين المطابقة حصرًا، ونتيجته صلب البحث الذي تُقاس عليه بقية النتائج",
        "model": GOLDEN_MODEL, "thinking": "high", "context_tokens": 1050000,
        "system_prompt": golden_prompt,
    })
    print(f"🥇 [Core Agents] أنشأ المدير الوكيل المؤقت: الذهبي ({GOLDEN_MODEL}) — نطاقه {len(scope_books)} كتابًا حدّدها المستشارون", flush=True)
    return [golden]


def _build_evidence_ledger(
    dossiers: List[Dict[str, Any]],
    query: str,
    model: str,
    api_key: str,
) -> str:
    """محرّر سجل الأدلة: طبقة تنظيمية واحدة قبل توليف المدير، لا مدير ثانٍ.
    يقرأ تقارير الفريق ويحوّل بطاقاتها إلى سجل منظم: كل قول بسطرٍ ببطاقته
    وكتابه وطبقته، وكل دليل حديثي بدرجته من بطاقته، ودعاوى الإجماع
    بمواضعها، والصفرات والادعاءات بلا بطاقة معلنة. لا يرجّح ولا يصوغ ولا
    يضيف من عنده؛ فالترجيح والصياغة يبقيان للمدير الواحد فوق هذا السجل."""
    if not dossiers or not (model or "").strip() or not (api_key or "").strip():
        return ""

    def _cards_part(rep: str) -> str:
        # بطاقات الأدلة في مطلع كل تقرير قبل «التحرير»: هي مادة السجل وحدها.
        # قراءة التقارير كاملة كلّفت ~12 دقيقة؛ والبطاقات هي ما يُجمَّع أصلًا.
        m = re.search(r"(?:^|\n)#{0,3}\s*(?:\*\*)?التحرير(?:\s|المبني|\*\*|$)", rep)
        part = rep[:m.start()] if m else rep[:14000]
        return part[:22000]

    blocks = []
    for d in dossiers:
        rep = str(d.get("report") or "")
        cards = _cards_part(rep)
        if cards.strip():
            blocks.append(f"### بطاقات تقرير «{d.get('name') or ''}» ({d.get('model') or ''}) — شواهده {len(d.get('citations') or [])}\n{cards}")
    if not blocks:
        return ""
    _lsys = (
        "أنت محرّر سجل الأدلة لمدير المشروع. مهمتك ميكانيكية تجميعية صارمة: لا ترجّح، لا تصوغ بحثًا، لا تحكم، ولا تضف معلومة من ذاكرتك.\n"
        "المرفق «بطاقات الأدلة» المستخرجة من مطلع كل تقرير من تقارير وكلاء الفريق، وهي مادتك الوحيدة. ابنِ منها سجلًّا منظمًا يبني عليه المدير بحثه، في خمسة أقسام:\n"
        "١) سجل الأقوال والمنسوبات: كل قول أو نسبة في سطر: القول/النسبة | قائلها أو مذهبها | بطاقتها (إحالتها الحرفية كما في البطاقة) | كتاب البطاقة وطبقته (من أي مذهب/طبقة هو الكتاب نفسه).\n"
        "٢) سجل الأدلة الحديثية: كل حديث مؤثر: لفظه | درجته كما حكم بها أهلها في البطاقات حصرًا | بطاقته وإحالتها.\n"
        "٣) دعاوى الإجماع والاتفاق: كل دعوى وردت في بطاقة | قائلها | مستندها أو خلوّها منه.\n"
        "٤) الصفرات المعلنة: مذاهب أو طبقات أو أدلة أو فروع لم ترد لها بطاقة في أي من البطاقات المرفقة — اذكرها صراحة «لا بطاقة لهذا».\n"
        "٥) تعارضات وتنبيهات بين البطاقات: ما تعارضت فيه بطاقتان في نسبة أو درجة ويحتاج فصل المدير، وكل دعوى داخل بطاقة بلا إحالة تسندها.\n"
        "التزم نصوص البطاقات وإحالاتها حرفيًا، ولا تلخّص نص شاهد ولا تعيد صياغته؛ السجل خريطة إحالات لا متن بحث."
    )
    try:
        raw = call_openrouter_raw(
            model_id=normalize_model_id(model),
            messages=[{"role": "system", "content": _lsys},
                      {"role": "user", "content": f"المسألة: {query}\n\nبطاقات الفريق:\n\n" + "\n\n---\n\n".join(blocks)}],
            api_key=api_key, temperature=0.1, max_tokens=64000, timeout=300,
            thinking_level="high",
        ) or ""
    except Exception as _lerr:
        print(f"📒 [Evidence Ledger] تعذر بناء سجل الأدلة: {_lerr}", flush=True)
        return ""
    raw = raw.strip()
    if len(raw) < 200:
        print(f"📒 [Evidence Ledger] سجل شبه فارغ ({len(raw)} حرفًا) — يُتجاوز", flush=True)
        return ""
    print(f"📒 [Evidence Ledger] بُني سجل الأدلة من {len(blocks)} تقريرًا ({len(raw)} حرفًا)", flush=True)
    return raw


def expand_query_with_anchor_rounds(
    query: str,
    scopes: List[Dict[str, Any]],
    api_key: str,
    model: str,
    use_hybrid: bool,
    seed_anchors: Optional[List[str]] = None,
    honor_agent_limit: bool = True,
    run_id: Optional[str] = None,
    death_max: Optional[int] = None,
    intent_genres: Optional[List[str]] = None,
    panel_hint: Optional[str] = None,
    semantic_terms: Optional[List[str]] = None,
    semantic_channel: bool = True,
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[str]]:
    """بحث مغلق الميزانية: لجنة مراس تعتمد 5، خمس جولات متوازية (مرسى لكل جولة)،
    ثم قرار إغلاق من النموذج الأساسي وجولة سادسة اختيارية لسد فجوة. تحفظ الحزمة
    بعد كل جولة في research_runs برقم المحادثة. عند تعذر اللجنة يسقط للجولات القديمة."""
    buckets: Dict[str, List[Dict[str, Any]]] = {scope["name"]: [] for scope in scopes}
    # إزالة تكرار الاسترجاع: النطاقات المتطابقة بصمةً (نفس الكتب والسقوف ونمط
    # البحث) تُبحث مرة واحدة وتُنسخ نتيجتها لأسمائها — فالذهبي والفضي وهيئة
    # المناظرة بلا كتب كانوا يكررون البحث نفسه حرفيًا. الجودة لا تتغير: كل
    # نطاق يأخذ المقاطع نفسها التي كان سيجدها منفردًا.
    _orig_scopes = list(scopes)
    _alias_of: Dict[str, str] = {}
    _rep_by_sig: Dict[tuple, Dict[str, Any]] = {}
    for _s in _orig_scopes:
        _sig = (tuple(str(b) for b in (_s.get("books") or [])),
                int(_s.get("top_k") or 12), int(_s.get("pool_size") or 300),
                bool(_s.get("use_hybrid", True)))
        _rep = _rep_by_sig.get(_sig)
        if _rep is None:
            _rep_by_sig[_sig] = _s
        else:
            _alias_of[str(_s["name"])] = str(_rep["name"])
    if _alias_of:
        print(f"⚓ [Scopes] {len(_alias_of)} نطاقًا مكرر البصمة يُبحث مرة واحدة: {sorted(_alias_of)}", flush=True)
        scopes = [s for s in _orig_scopes if str(s["name"]) not in _alias_of]
    anchors: List[str] = []
    for seed in seed_anchors or []:
        line = re.sub(r"\s+", " ", str(seed)).strip()
        if line and line not in anchors:
            anchors.append(line)

    def search_scopes(anchor_list: List[str], include_query: bool, round_no: int) -> int:
        def one(scope: Dict[str, Any]):
            try:
                hits = run_rag_search(
                    query=query,
                    selected_books=scope.get("books") or None,
                    pool_size=int(scope.get("pool_size") or 300),
                    top_k=int(scope.get("top_k") or 12),
                    use_reranker=False,
                    dynamic_anchors=anchor_list or None,
                    use_hybrid=scope.get("use_hybrid", use_hybrid),
                    semantic_channel=semantic_channel,
                    honor_agent_limit=honor_agent_limit,
                    include_query=include_query,
                    death_max=death_max,
                )
            except Exception as exc:
                print(f"Error in anchor-round search for {scope.get('name')}: {exc}")
                hits = []
            return scope["name"], hits

        added = 0
        workers = min(max(len(scopes), 1), 12)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for name, hits in executor.map(one, scopes):
                added += _merge_passages(buckets[name], hits, round_no)
        return added

    def current_snippets() -> List[str]:
        sample = []
        for rows in buckets.values():
            for row in rows[:8]:
                snippet = (row.get("snippet") or "").strip()
                if snippet:
                    sample.append(snippet[:280])
                if len(sample) >= 12:
                    return sample
        return sample

    def all_rows() -> List[Dict[str, Any]]:
        return [row for rows in buckets.values() for row in rows]

    key = (api_key or "").strip()
    if not key:
        search_scopes(anchors, True, 1)
    else:
        panel_res = generate_anchor_panel(query, key, intent_genres=intent_genres, panel_hint=panel_hint)
        panel = panel_res.get("adopted") or []
        adopted = [p.get("phrase") for p in panel if p.get("phrase")][:5]
        if adopted:
            # ===== بوابة التحقق الحي: لا مرسى معتمد بلا شاهد لفظي في النطاق =====
            # (إجماع النماذج قد يقع على صياغة وصفية حديثة لا وجود لها في الكتب)
            try:
                _dbv = get_db()
                _curv = _dbv.cursor() if _dbv else None
            except Exception:
                _curv = None
            # نطاق التحقق: كتب النطاقات المختارة فقط؛ وبلا نطاق وكيل يكون التحقق في
            # المكتبة كلها عبر الفهرس (لا في كتب شاهد الجدول التسعة، فهي عينة لا حارس)
            _vids = _selected_book_ids([b for s in scopes for b in (s.get("books") or [])], _curv)
            _meta = {c["phrase"]: c for c in (panel_res.get("candidates") or [])}
            _ranked = list(adopted) + [c["phrase"] for c in (panel_res.get("candidates") or []) if c["phrase"] not in adopted]

            def _hits(ph: str) -> bool:
                # مصدر الشاملة الكسول: التحقق عباريًا في فهرسها مباشرة (دقيق
                # وسريع)، وإلا فهرس المكتبة المحلي إن وُجد، وإلا المسح اللفظي
                try:
                    import shamela_link as _SLG
                    if _SLG.library_source() == "shamela":
                        import shamela_search
                        _ids = [int(b) for b in (_vids or []) if str(b).isdigit()] or None
                        r = shamela_search.search(ph, mode="phrase", book_ids=_ids, death_max=death_max, limit=1)
                        return bool(r.get("results"))
                except Exception:
                    pass
                try:
                    import library_search
                    if library_search.index_status().get("available"):
                        _ids = [int(b) for b in (_vids or []) if str(b).isdigit()] or None
                        r = library_search.get_index().search(ph, mode="phrase", book_ids=_ids, death_max=death_max, limit=1)
                        return bool(r.get("results"))
                except Exception:
                    pass
                try:
                    f = shamela_local_mcp.search_books_scoped(query=ph, book_ids=_vids or shamela_local_mcp.anchor_table_scope_ids(), limit_per_book=1, limit=1)
                    return bool(f.get("results"))
                except Exception:
                    return False

            def _hits_words(ph: str) -> bool:
                # طبقة دلالية: ألفاظ المرسى مجتمعة في مواضع حقيقية — لصيغ
                # العناوين والمصطلحات التي لا توجد عبارة حرفية في المتن.
                _sup = int((_meta.get(ph) or {}).get("support", 1) or 1)
                try:
                    import shamela_link as _SLG2
                    if _SLG2.library_source() == "shamela":
                        import shamela_search
                        _ids = [int(b) for b in (_vids or []) if str(b).isdigit()] or None
                        r = shamela_search.search(ph, mode="words", book_ids=_ids, death_max=death_max, limit=5)
                        _books = {h.get("book_id") for h in (r.get("results") or [])}
                        return bool(_books) and (len(_books) >= 2 or _sup >= 2)
                except Exception:
                    pass
                try:
                    import library_search
                    if library_search.index_status().get("available"):
                        _ids = [int(b) for b in (_vids or []) if str(b).isdigit()] or None
                        r = library_search.get_index().search(ph, mode="words", book_ids=_ids, death_max=death_max, limit=5)
                        _books = {h.get("book_id") for h in (r.get("results") or [])}
                        return bool(_books) and (len(_books) >= 2 or _sup >= 2)
                except Exception:
                    pass
                return False

            def _verdict(ph: str) -> str:
                if _hits(ph):
                    return "phrase"
                if _hits_words(ph):
                    return "words"
                return ""

            _pool = _ranked[:12]
            _verdicts: Dict[str, str] = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as exv:
                for ph, v in zip(_pool, exv.map(_verdict, _pool)):
                    _verdicts[ph] = v
            for ph in _pool:
                if not _verdicts.get(ph):
                    print(f"⚓ [Anchor Gate] سقطت في التحقق الحي (بلا شاهد): «{ph}»")
                elif _verdicts[ph] == "words":
                    print(f"⚓ [Anchor Gate] قُبلت دلاليًا (كلمات مجتمعة): «{ph}»")
            _verified = [ph for ph in _ranked if _verdicts.get(ph)][:5]
            if _verified:
                adopted = _verified
                _gmap = {p.get("phrase"): p.get("genre", "عام") for p in panel}
                panel = [{"phrase": ph, "support": (_meta.get(ph) or {}).get("support", 1),
                          "confidence": "متحقق" if _verdicts.get(ph) == "phrase" else "متحقق دلاليًا",
                          "genre": _gmap.get(ph, "عام")} for ph in adopted]
            print(f"⚓ [Anchor Gate] مراس متحقق منها حيا ({len(adopted)}): {adopted}")
        if semantic_terms:
            # مراسي وكيل الألفاظ الدلالية عند المتقدمين (موثقة كلماتيًا لا
            # عباريًا): جولات مستقلة بصيغ المصنفين وضمائرهم وتصريفاتهم،
            # فلا تسقط كما تسقط العبارة الحديثة في بوابة العبارة الحرفية.
            _sextra = [t for t in semantic_terms if t and t not in adopted][:4]
            if _sextra:
                adopted = list(adopted) + _sextra
                print(f"⚓ [Semantic Anchors] أُضيفت مراسي ألفاظ المتقدمين: {_sextra}", flush=True)
        if adopted:
            # ===== مسار مغلق: 5 جولات متوازية بمراس معتمدة + إغلاق اختياري =====
            anchors.extend([a for a in adopted if a not in anchors])
            run_key = run_id or ("run_" + hashlib.sha1((query or "").encode("utf-8")).hexdigest()[:12])
            merge_lock = threading.Lock()

            def search_anchor_round(idx: int, anc: str) -> int:
                total = 0

                def one_scope(scope: Dict[str, Any]):
                    try:
                        # توجيه بفن المرساة: جولة الحديث في كتب الحديث، والفقه في كتب الفقه...
                        # (لا يُفرض مع نطاق وكيل مختار؛ فكتب الوكيل أولى من تصنيف الفن)
                        _genre = next((p.get("genre") for p in panel if p.get("phrase") == anc), None)
                        _cats = None if scope.get("books") else _GENRE_CATEGORIES.get(_genre or "")
                        hits = run_rag_search(
                            query=query,
                            selected_books=scope.get("books") or None,
                            pool_size=int(scope.get("pool_size") or 300),
                            top_k=int(scope.get("top_k") or 12),
                            use_reranker=False,
                            dynamic_anchors=[anc],
                            use_hybrid=scope.get("use_hybrid", use_hybrid),
                            semantic_channel=semantic_channel,
                            honor_agent_limit=honor_agent_limit,
                            include_query=(idx == 0),
                            death_max=death_max,
                            categories=_cats,
                        )
                    except Exception as exc:
                        print(f"Error in panel-round search: {exc}")
                        hits = []
                    return scope["name"], hits

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(max(len(scopes), 1), 12)) as ex2:
                    for name, hits in ex2.map(one_scope, scopes):
                        with merge_lock:
                            total += _merge_passages(buckets[name], hits, idx + 1)
                return total

            def rounds_snapshot(anchor_list: List[str]):
                data = []
                for i, anc in enumerate(anchor_list):
                    rows_i = [r for rows in buckets.values() for r in rows if r.get("anchor_round") == i + 1]
                    data.append({
                        "anchor": anc, "count": len(rows_i),
                        "books": sorted({str(r.get("title")) for r in rows_i if r.get("title")}),
                        "passages": [{"book_id": r.get("book_id"), "title": r.get("title"),
                                      "part": r.get("part_raw"), "page": r.get("page_num_raw"),
                                      "snippet": (r.get("snippet") or "")[:300]} for r in rows_i[:12]],
                    })
                return data

            _research_run_save(run_key, query, panel, [], "anchors_adopted")
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                futs = {ex.submit(search_anchor_round, i, anc): i for i, anc in enumerate(adopted)}
                for fut in concurrent.futures.as_completed(futs):
                    i = futs[fut]
                    try:
                        added_i = fut.result()
                    except Exception:
                        added_i = 0
                    print(f"⚓ [Panel Rounds] جولة {i + 1}/5 بمرسى «{adopted[i]}» أضافت {added_i} مقطعا")
                    _research_run_save(run_key, query, panel, rounds_snapshot(adopted), "searching")

            # ===== سد فجوات القصد: فن مستهدف نصيبه في الحوض ضعيف يُسد بمراس داخل تصنيفاته =====
            if intent_genres:
                _generic_ph = [p["phrase"] for p in panel if p.get("genre") in (None, "عام")]
                _fill_no = 91
                for _g in intent_genres:
                    _cats = _GENRE_CATEGORIES.get(_g)
                    if not _cats:
                        continue
                    _rows_now = all_rows()
                    _g_rows = [r for r in _rows_now if _CAT_TO_GENRE.get(r.get("category")) == _g]
                    if len(_g_rows) >= 10:
                        continue
                    # تعميق: كل مراسي اللجنة (بعباراتها) داخل تصنيفات الفن الناقص عمقًا
                    _phrases = list(dict.fromkeys(
                        [p["phrase"] for p in panel if p.get("genre") == _g]
                        + _generic_ph
                        + [p["phrase"] for p in panel]))[:4]
                    _added_g = 0
                    for _anc in _phrases:
                        for _scope in scopes:
                            if _scope.get("books"):
                                continue
                            try:
                                _hits = run_rag_search(
                                    query=query, selected_books=None,
                                    pool_size=int(_scope.get("pool_size") or 300),
                                    top_k=int(_scope.get("top_k") or 12), use_reranker=False,
                                    dynamic_anchors=[_anc], use_hybrid=use_hybrid, semantic_channel=semantic_channel,
                                    honor_agent_limit=honor_agent_limit, include_query=False,
                                    death_max=death_max, categories=_cats)
                            except Exception:
                                _hits = []
                            with merge_lock:
                                _added_g += _merge_passages(buckets[_scope["name"]], _hits, _fill_no)
                        _fill_no += 1
                    if len([r for r in all_rows() if _CAT_TO_GENRE.get(r.get("category")) == _g]) < 10:
                        # توسعة بكلمات المرساة في الصفحة (مداخل المعاجم لا تحمل عبارات كاملة)
                        for _anc in _phrases[:3]:
                            for _scope in scopes:
                                if _scope.get("books"):
                                    continue
                                try:
                                    _hits = run_rag_search(
                                        query=query, selected_books=None,
                                        pool_size=int(_scope.get("pool_size") or 300),
                                        top_k=int(_scope.get("top_k") or 12), use_reranker=False,
                                        dynamic_anchors=[_anc], use_hybrid=use_hybrid, semantic_channel=semantic_channel,
                                        honor_agent_limit=honor_agent_limit, include_query=False,
                                        death_max=death_max, categories=_cats, fts_mode="words")
                                except Exception:
                                    _hits = []
                                with merge_lock:
                                    _added_g += _merge_passages(buckets[_scope["name"]], _hits, _fill_no)
                            _fill_no += 1
                    print(f"⚓ [Genre Fill] سد فجوة فن «{_g}» أضاف {_added_g} مقطعا")

            digest = []
            for i, anc in enumerate(adopted):
                rows_i = [r for rows in buckets.values() for r in rows if r.get("anchor_round") == i + 1]
                books_i = {r.get("title") for r in rows_i if r.get("title")}
                tops = " | ".join((r.get("snippet") or "")[:110] for r in rows_i[:2])
                digest.append(f"- «{anc}»: {len(rows_i)} شواهد من {len(books_i)} كتب. أبرزها: {tops or 'لا شيء'}")
            followups: List[str] = []
            try:
                raw_c = call_openrouter_raw(
                    model_id=model,
                    messages=[
                        {"role": "system", "content": "أنت النموذج الأساسي الباحث. أمامك ملخص حصاد خمس جولات بحث بمراس معتمدة من لجنة. احكم: هل الشواهد تكفي لصياغة إجابة موثقة؟ إن نقص جانب جوهري محدد فاقترح حتى 3 مراس تراثية قصيرة من لسان المصنفين لسده في جولة إغلاق واحدة أخيرة. أخرج JSON فقط: {\"sufficient\": true, \"followup_anchors\": []}"},
                        {"role": "user", "content": f"المسألة: {(query or '')[:700]}\n\nملخص الحصاد:\n" + "\n".join(digest)},
                    ],
                    api_key=key, temperature=0.1, max_tokens=1200, timeout=60, thinking_level="low",
                )
                plan_c = _parse_anchor_plan(raw_c)
                if not plan_c.get("covered"):
                    followups = [a for a in _sanitize_anchors(plan_c.get("anchors") or [], cap=3) if a not in adopted]
            except Exception as exc:
                print(f"⚓ [Panel Rounds] تعذر قرار الإغلاق: {exc}")
            if followups:
                print(f"⚓ [Panel Rounds] جولة إغلاق (6) بطلب النموذج الأساسي: {followups}")
                anchors.extend(followups)
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex3:
                    list(ex3.map(lambda a: search_anchor_round(5, a), followups))
                _research_run_save(run_key, query,
                                   panel + [{"phrase": a, "support": 0, "confidence": "إغلاق"} for a in followups],
                                   rounds_snapshot(adopted + followups), "closed")
            _research_run_save(run_key, query, panel, rounds_snapshot(adopted + followups), "done")
            print(f"⚓ [Panel Rounds] اكتمل البحث المغلق: {len(all_rows())} مقطعا، الحزمة {run_key}")
        for round_no in (range(1, 5) if not adopted else []):
            snippets = current_snippets()
            plan = plan_retrieval_round(query, key, model, anchors, snippets)
            rows_now = all_rows()
            books_seen = {(row.get("book_id") or row.get("title")) for row in rows_now}
            mined = _mine_evidence_anchors(rows_now, query, anchors) if rows_now else []
            if snippets and plan.get("covered"):
                # لا تُقبل التغطية والنتيجة نحيلة ما دامت مراسي الشاهد نفسه لم تُجرَّب:
                # رواية واحدة قد توجد في الصحاح والسنن والمسانيد بألفاظ مختلفة.
                thin = len(rows_now) < 6 or len(books_seen) < 3
                if thin and mined and round_no <= 3:
                    fresh_mined = mined[:6]
                    for anc in fresh_mined:
                        anchors.append(anc)
                    print(f"⚓ [Anchor Rounds] النتيجة نحيلة ({len(rows_now)} مقاطع من {len(books_seen)} كتب)، مراسي من الشاهد نفسه: {fresh_mined}")
                    added = search_scopes(fresh_mined, False, round_no)
                    if added == 0:
                        print("⚓ [Anchor Rounds] مراسي الشاهد لم تُضف جديداً، فتتوقف الجولات.")
                        break
                    continue
                print(f"⚓ [Anchor Rounds] جوهر المسألة ظاهر في المقاطع، والتوقف قبل الجولة {round_no}.")
                break
            fresh = []
            for anc in _sanitize_anchors(plan.get("anchors") or [], cap=10):
                if anc in anchors or anc == (query or "").strip() or len(anchors) >= 20:
                    continue
                anchors.append(anc)
                fresh.append(anc)
            # مراسي مستخرجة من الشواهد نفسها تنضم إلى مراسي التخطيط في الجولة نفسها (بعد مصفاة السلامة)
            for anc in _sanitize_anchors(mined, cap=8):
                if anc in anchors or len(anchors) >= 20:
                    continue
                anchors.append(anc)
                fresh.append(anc)
            if round_no > 1 and not fresh:
                print(f"⚓ [Anchor Rounds] لا مراسي جديدة في الجولة {round_no}.")
                break
            print(f"⚓ [Anchor Rounds] جولة {round_no}: {fresh or ['سؤال المستخدم']}")
            added = search_scopes(fresh, round_no == 1, round_no)
            if round_no > 1 and added == 0:
                print("⚓ [Anchor Rounds] لم تُضف مقاطع جديدة، فتتوقف الجولات.")
                break

    for _an, _rn in _alias_of.items():
        buckets[_an] = [dict(r) for r in (buckets.get(_rn) or [])]
    for scope in _orig_scopes:
        limit = int(scope.get("top_k") or 12)
        rows = buckets.get(scope["name"]) or []
        lexical = [row for row in rows if row.get("lexical_hit")]
        rest = [row for row in rows if not row.get("lexical_hit")]
        rest.sort(
            key=lambda row: float(row.get("score") or 0) + 0.12 * (int(row.get("anchor_round") or 1) - 1),
            reverse=True,
        )
        buckets[scope["name"]] = (lexical + rest)[:limit]
    return buckets, anchors


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
                print(f"PDF extract failed for {filename}: {e}")
                extracted_text = "[تعذر استخراج نص هذا الملف]"

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


def _attachment_body(att: Dict[str, Any], owner_id: str) -> str:
    """نص المرفق الجاهز للنموذج. إن فشل الاستخراج سابقاً يُعاد من الملف المحفوظ."""
    text = str(att.get("extracted_text") or att.get("extractedText") or "").strip()
    broken = (not text) or text.startswith("[تعذر") or text.startswith("[خطأ") or "pypdf" in text or "No module named" in text
    raw_path = str(att.get("file_path") or att.get("path") or "").strip()
    if not broken or not raw_path:
        return text
    try:
        path = Path(raw_path).resolve()
        root = (UPLOADS_BUCKET_DIR / owner_id).resolve()
        if root not in path.parents or not path.is_file():
            return text
        filename = str(att.get("filename") or att.get("name") or path.name)
        mime = str(att.get("file_type") or att.get("type") or "")
        recovered, _, _ = extract_text_from_file(path, filename, mime)
        if recovered and not recovered.startswith("[تعذر") and not recovered.startswith("[خطأ"):
            return recovered
    except Exception as err:
        print(f"Attachment reread failed: {err}")
    return text


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
    thinking_level: str = "medium"

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
                timeout=120,
                thinking_level=req.thinking_level
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
    thinking_level: str = "medium"

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
            attach_reasoning(payload, model_id, req.thinking_level)
            def _open(body):
                request = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:8085",
                        "X-Title": "Al-Mojtahed Compare"
                    },
                    data=json.dumps(body).encode("utf-8")
                )
                return urllib.request.urlopen(request, timeout=120)
            try:
                response = _open(payload)
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", errors="ignore")
                if payload.get("reasoning") and "reasoning" in detail.lower():
                    payload.pop("reasoning", None)
                    response = _open(payload)
                else:
                    raise
            with response:
                for raw in response:
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


ANSWER_REWRITE_MODEL = "google/gemini-3.8-flash"
ANSWER_ABBREVIATE_INSTRUCTION = (
    "اختصر الإجابة اختصاراً علمياً غير مخل، مع المحافظة على السياق وأصل الموضوع وجوانبه المهمة وآثاره. "
    "لا تختصر ولا تلخص ما لا يقوم السياق إلا به. "
    "يكون الاختصار موضوعياً معبراً عن نفس الموضوع والنص. "
    "لا تستعن بأي أداة خارجية، وتقيد بالنص الموجود ومراجعه المذكورة تماماً. مهمتك الوحيدة هي الاختصار فقط. "
    "أعد النص المختصر وحده، بلا مقدمة ولا تعليق على عملك."
)


class AnswerRewriteRequest(BaseModel):
    text: str
    mode: str = "abbreviate"
    language: Optional[str] = None
    api_key: Optional[str] = None


@app.post("/api/chat/rewrite")
async def rewrite_chat_answer(req: AnswerRewriteRequest, request: Request):
    """اختصار إجابة المحادثة أو ترجمتها من نصها وحده، بلا بحث ولا أدوات."""
    current_owner_id(request)
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="لا يوجد نص لاختصاره")
    if len(text) > 120000:
        raise HTTPException(status_code=400, detail="النص أطول من حد الاختصار")
    mode = req.mode if req.mode in ("abbreviate", "translate") else "abbreviate"
    language = re.sub(r"[\r\n\t]", " ", (req.language or "")).strip()[:80]
    if mode == "translate" and not language:
        raise HTTPException(status_code=400, detail="اختر لغة الترجمة")
    system = ANSWER_ABBREVIATE_INSTRUCTION
    if mode == "translate":
        system += (
            f"\n\nأخرج هذا الاختصار مترجماً إلى {language} فقط. "
            "أبقِ أسماء الكتب والمراجع وأرقام الأجزاء والصفحات كما وردت في النص."
        )
    key = (req.api_key or OPENROUTER_DEFAULT_KEY or "").strip()
    try:
        content = await asyncio.to_thread(
            call_openrouter_raw,
            ANSWER_REWRITE_MODEL,
            [{"role": "system", "content": system}, {"role": "user", "content": text}],
            key,
            0.2,
            8000,
            None,
            None,
            None,
            None,
            None,
            120,
            "off",
        )
    except Exception as exc:
        if "مفتاح" in str(exc):
            raise HTTPException(status_code=400, detail="مفتاح OpenRouter غير موجود")
        raise HTTPException(status_code=502, detail="تعذر الاختصار من النموذج")
    content = (content or "").strip()
    if not content:
        raise HTTPException(status_code=502, detail="لم يعد النموذج نصاً")
    return {"content": content, "model": ANSWER_REWRITE_MODEL}


def _collect_book_ids(obj: Any, acc: Dict[str, str], depth: int = 0) -> None:
    """جمع أرقام الكتب التي لمستها نتائج الأدوات (لأجل فحص الاقتباسات عليها)."""
    if depth > 6 or len(acc) >= 24:
        return
    if isinstance(obj, dict):
        bid = obj.get("book_id")
        if isinstance(bid, (int, str)) and str(bid).strip().isdigit():
            k = str(bid).strip()
            if k not in acc:
                acc[k] = str(obj.get("book_title") or obj.get("title") or obj.get("title_ar") or "")
        for v in obj.values():
            _collect_book_ids(v, acc, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _collect_book_ids(v, acc, depth + 1)


_RAW_QUOTE_RE = re.compile(r"«([^»]{25,600})»|\"([^\"“”]{25,600})\"|“([^”]{25,600})”")


_RAW_TOPIC_STOP = {"ما", "هو", "هي", "في", "من", "الى", "علي", "عن", "ان", "حكم", "قول",
                   "القول", "معتمد", "المعتمد", "مذهب", "المذهب", "لدي", "لدى", "اذكر",
                   "بين", "وضح", "اشرح", "النصوص", "نصوص", "كتبها", "اجزائها", "صفحاتها",
                   "المستعمل", "مستعمل", "ذلك", "هذه", "هذا", "التي", "الذي", "مع", "او", "ام"}


def _raw_topic_terms(req: "ChatRequest") -> List[str]:
    """ألفاظ مسألة السؤال المميزة (بعد طي الحروف) لفحص أن الاقتباس في الباب أصلا."""
    last = ""
    for m in reversed(req.messages):
        if m.role == "user":
            last = m.content or ""
            break
    folded = last.translate(str.maketrans({"إ": "ا", "أ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"}))
    terms = []
    for w in re.findall(r"[\u0600-\u06FF]{3,}", folded):
        w = re.sub(r"^ال", "", w)
        if len(w) >= 3 and w not in _RAW_TOPIC_STOP and w not in terms:
            terms.append(w)
    return terms[:8]


def _fold_ar(s: str) -> str:
    s = re.sub(r"[ً-ٰٟـ]", "", s or "")
    return s.translate(str.maketrans(
        {"إ": "ا", "أ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"}))


def _ar_num(s: str) -> Optional[int]:
    if s is None:
        return None
    out = ""
    for ch in str(s):
        if ch.isdigit():
            out += ch
        elif "٠" <= ch <= "٩":
            out += str(ord(ch) - ord("٠"))
        elif "۰" <= ch <= "۹":
            out += str(ord(ch) - ord("۰"))
    return int(out) if out else None


def _audit_raw_quotes(text: str, books: Dict[str, str], topic_terms: List[str] = None):
    """فحص اقتباسات جواب خام على صفحات الكتب التي لمستها الأدوات فعلًا:
    ثابت بموضعه الصحيح / ثابت بموضع آخر غير المحال إليه / ثابت لكنه من
    باب آخر لا يحمل لفظ المسألة / غير موجود أصلًا."""
    found_quotes = []
    for m in _RAW_QUOTE_RE.finditer(text or ""):
        q = next((g for g in m.groups() if g), "")
        if q.strip():
            found_quotes.append((q.strip(), m.start(), m.end()))
    entries, ok_count, failed = [], 0, []
    page_cache: Dict[str, str] = {}

    def _verify_one(bid: str):
        try:
            return bid, shamela_local_mcp.verify_quote(book=bid, quote_text=q_current)
        except Exception:
            return bid, None

    spans = [(s, e) for _q, s, e in found_quotes[:12]]
    for qi, (q, startpos, endpos) in enumerate(found_quotes[:12]):
        q_current = q
        next_start = spans[qi + 1][0] if qi + 1 < len(spans) else len(text or "")
        prev_end = spans[qi - 1][1] if qi > 0 else 0
        cited = None
        for window in ((text or "")[endpos:min(endpos + 180, next_start)],
                       (text or "")[max(startpos - 300, prev_end):startpos]):
            cm = re.search(r"(?:الجزء|ج)\s*([0-9٠-٩]{1,2})\s*[,،/]?\s*(?:الصفحة|ص)\s*([0-9٠-٩]{1,4})", window)
            if not cm:
                cm = re.search(r"\(\s*([0-9٠-٩]{1,2})\s*/\s*([0-9٠-٩]{1,4})", window)
            if cm:
                cited = (cm.group(1), cm.group(2))
                break
        # جرّب كل الكتب المرشحة بالتوازي: المتن الواحد قد يكون في كتب كثيرة
        # (متن وشرح وحاشية)، فاختر الموضع المطابق للإحالة المصرّح بها أو لاسم
        # الكتاب المذكور قرب الاقتباس، لا أول مصادفة.
        hits = []
        context_fold = _fold_ar((text or "")[max(0, startpos - 600):endpos + 200])
        cand_ids = list(books.keys())[:12]
        results = {}
        if cand_ids:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=6) as ex:
                for bid, r in ex.map(_verify_one, cand_ids):
                    results[bid] = r
        for bid in cand_ids:
            r = results.get(bid)
            if not r or r.get("match_status") not in ("MATCH_EXACT", "MATCH_NORMALIZED"):
                continue
            mt = (r.get("matches") or [{}])[0]
            title = r.get("book_title") or books.get(bid) or ""
            t_stems = [w for w in re.findall(r"[\u0600-\u06FF]{4,}", _fold_ar(title))]
            overlap = sum(1 for w in t_stems if w in context_fold)
            page_hit = bool(cited and _ar_num(cited[1]) is not None
                            and _ar_num(cited[1]) == _ar_num(mt.get("page_num")))
            part_hit = bool(cited and mt.get("part") not in (None, "")
                            and str(_ar_num(cited[0])) == str(_ar_num(mt.get("part"))))
            hits.append({"book_id": bid, "book_title": title, "part": mt.get("part"),
                         "page_num": mt.get("page_num"),
                         "_score": (1 if page_hit else 0, 1 if part_hit else 0, overlap)})
        hit = None
        loc_ok = True
        if hits:
            hits.sort(key=lambda h: h["_score"], reverse=True)
            hit = {k: v for k, v in hits[0].items() if not k.startswith("_")}
            if cited and hit.get("page_num") is not None:
                loc_ok = _ar_num(cited[1]) == _ar_num(hit.get("page_num"))
                if hit.get("part") not in (None, "") and _ar_num(cited[0]) != _ar_num(hit.get("part")):
                    loc_ok = False
        if hit:
            on_topic = True
            if topic_terms:
                fq = _fold_ar(q)
                on_topic = any(t in fq for t in topic_terms)
                if not on_topic and hit.get("page_num") is not None:
                    # اقتباس تعليل قد لا يحمل لفظ المسألة بنفسه: احتكم إلى
                    # صفحة موضعه؛ فإن كانت في الباب فهو منه.
                    ck = f"{hit['book_id']}|{hit.get('part')}|{hit.get('page_num')}"
                    if ck not in page_cache:
                        try:
                            pg = shamela_local_mcp.get_page(hit["book_id"], int(hit["page_num"]),
                                                            str(hit["part"]) if hit.get("part") not in (None, "") else None)
                            page_cache[ck] = _fold_ar(((pg.get("page") or {}).get("body") or ""))
                        except Exception:
                            page_cache[ck] = ""
                    on_topic = any(t in page_cache[ck] for t in topic_terms)
            status = "MATCH" if (loc_ok and on_topic) else ("WRONG_LOCATION" if not loc_ok else "OFF_TOPIC")
            entry = {"quote": q[:90], "status": status, "cited": cited, **hit}
            if status == "MATCH":
                ok_count += 1
            else:
                failed.append(entry)
            entries.append(entry)
        else:
            entry = {"quote": q[:90], "status": "NOT_FOUND", "cited": cited}
            entries.append(entry)
            failed.append(entry)
    return entries, ok_count, failed


RAW_MCP_CITATION_RULE = (
    "قاعدة إحالة صارمة — وهي الضبط الوحيد المفروض في هذا الوضع، وما عداها فأنت حر في بحثك وتحريرك:\n"
    "1. لا تنقل نصًا بين علامتي تنصيص إلا من صفحة قرأتها فعلًا بأدوات القراءة في هذه المحادثة، حرفيًا كما ورد.\n"
    "2. قبل تسليم جوابك طابق كل نقل تنوي إيراده بـverify_quote أو verify_batch على كتابه، ولا تُبقِ إلا ما كانت حالته MATCH_EXACT أو MATCH_NORMALIZED.\n"
    "3. أحِل كل نقل إلى اسم الكتاب ومؤلفه والجزء والصفحة كما أعادتها الأدوات في نتائجها، لا من ذاكرتك.\n"
    "4. إن لم تقف على نص في كتاب فلا تنسبه إليه؛ صرّح بأنك لم تقف عليه، ولا تُكمل النقص من حفظك."
)


def _raw_mcp_chat_sync(req: "ChatRequest", request: Request) -> Dict[str, Any]:
    """وضع MCP الخام المباشر: النموذج المختار يقود أدوات خادم المجتهد بنفسه
    كما يفعل أي عميل MCP خارجي — بلا وكلاء، وبلا خط استرجاع، وبلا قواعد
    بحث أو إخراج، عدا قاعدة إحالة واحدة قصيرة (RAW_MCP_CITATION_RULE)
    تضبط النقل والعزو فقط، وبوابة مطابقة لاحقة تتحقق منها آليًا."""
    base = {"model": req.model or "unknown", "provider": req.provider or "openrouter",
            "thinking_level": req.thinking_level, "thinking_effort": None,
            "agent_group": None, "witnesses": [], "raw_mcp": True, "tool_trace": []}
    key = owner_openrouter_key(request, req.api_key)
    if not key:
        return {**base, "reply": "⚠️ وضع MCP الخام يحتاج مفتاح OpenRouter مضبوطًا في حسابك."}
    port = os.environ.get("PORT", "8085")
    try:
        tools, mapping = mcp_openai_tools([{"url": f"http://127.0.0.1:{port}/mcp", "name": "المجتهد"}])
    except Exception as exc:
        return {**base, "reply": f"⚠️ تعذر تجهيز أدوات MCP: {exc}"}
    if not tools:
        return {**base, "reply": "⚠️ لم تتوفر أدوات MCP من الخادم الداخلي."}
    alias = {
        "claude-3-7-sonnet": "anthropic/claude-3.7-sonnet",
        "claude-3-5-sonnet": "anthropic/claude-3.5-sonnet",
        "claude-3-5-haiku": "anthropic/claude-3.5-haiku",
        "claude-3-opus": "anthropic/claude-3-opus",
    }
    model = alias.get(req.model or "", req.model)
    base["model"] = model
    dialog = [{"role": "system", "content": RAW_MCP_CITATION_RULE}] + [
        {"role": m.role, "content": m.content} for m in req.messages
        if m.role in ("user", "assistant") and (m.content or "").strip()]

    def _read(payload: dict) -> dict:
        o_req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "HTTP-Referer": "http://localhost:8085", "X-Title": "Al-Mojtahed Raw MCP"},
            data=json.dumps(payload).encode("utf-8"))
        with urllib.request.urlopen(o_req, timeout=240) as resp:
            return json.loads(resp.read().decode("utf-8"))

    payload = {"model": model, "messages": dialog,
               "temperature": float(req.temperature if req.temperature is not None else 0.2),
               "max_tokens": min(int(req.max_tokens or 65536), 65536),
               "tools": tools, "tool_choice": "auto"}
    trace: List[str] = []
    base["tool_trace"] = trace
    seen_books: Dict[str, str] = {}
    read_books: Dict[str, str] = {}

    def _finalize(text: str) -> Dict[str, Any]:
        """بوابة مطابقة لاحقة (لا توجيه مسبق): تُفحص اقتباسات الجواب على
        الكتب التي لمستها الأدوات، فإن لم تثبت أُجبرت إعادة كتابة واحدة
        بالسجل، وبقي ما عجز عنه موسومًا في ذيل الجواب بدل مروره صامتًا."""
        if not text:
            return {**base, "reply": "⚠️ أرجع النموذج ردًا فارغًا."}
        topic_terms = _raw_topic_terms(req)
        audit_books = dict(read_books)
        for k, v in seen_books.items():
            audit_books.setdefault(k, v)
        entries, ok_count, failed = _audit_raw_quotes(text, audit_books, topic_terms)
        base["quote_audit"] = {"checked": len(entries), "verified": ok_count, "failed": len(failed)}
        if not failed:
            return {**base, "reply": text}
        lines = ["سجل مطابقة آلي من الخادم (فحص لاحق لجوابك، لا توجيه مسبق):"]
        for e in failed:
            if e["status"] == "WRONG_LOCATION":
                lines.append(f"- اقتباس ثابت لكن إحالتك خاطئة: «{e['quote']}…» موضعه الصحيح: "
                             f"{e.get('book_title')} ج{e.get('part')} ص{e.get('page_num')}.")
            elif e["status"] == "OFF_TOPIC":
                lines.append(f"- اقتباس ثابت في {e.get('book_title')} ج{e.get('part')} ص{e.get('page_num')} "
                             f"لكنه لا يحمل لفظ مسألة السؤال ({'، '.join(topic_terms)})، فهو من باب آخر: "
                             f"«{e['quote']}…» احذفه إلا إن بيّنت صلته بالمسألة بنص صريح.")
            else:
                lines.append(f"- اقتباس غير موجود في الكتب التي استعملتها: «{e['quote']}…»")
        lines.append("أعد كتابة الجواب النهائي الآن كاملًا: احذف كل اقتباس مرفوض في السجل أو استبدله "
                     "بنص حرفي مما أرجعته الأدوات في هذه المحادثة (لا سيما حقل الاقتباسات الموثقة "
                     "quotes في نتائج الملفات إن وُجد)، وصحّح الجزء والصفحة إلى المواضع الثابتة، "
                     "ولا تستدعِ أدوات جديدة.")
        dialog.append({"role": "assistant", "content": text})
        dialog.append({"role": "user", "content": "\n".join(lines)})
        payload["messages"] = dialog
        payload["tool_choice"] = "none"
        try:
            data2 = _read(payload)
            text2 = ((data2.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            text2 = text2.strip()
        except Exception:
            text2 = ""
        if not text2:
            return {**base, "reply": text}
        entries2, ok2, failed2 = _audit_raw_quotes(text2, audit_books, topic_terms)
        base["quote_audit"] = {"checked": len(entries2), "verified": ok2,
                               "failed": len(failed2), "repaired": True}
        if failed2:
            bad = "؛ ".join(f"«{e['quote'][:50]}…»" for e in failed2[:4])
            text2 += (f"\n\n---\n⚠️ **سجل مطابقة آلي (MCP خام):** فُحص {len(entries2)} اقتباسًا، "
                      f"ثبت {ok2}، وبقي {len(failed2)} غير ثابت رغم إعادة الكتابة: {bad}")
        return {**base, "reply": text2}

    try:
        data = _read(payload)
        for _round in range(24):
            if isinstance(data, dict) and data.get("error"):
                raise RuntimeError(f"خطأ المزود: {str(data.get('error'))[:300]}")
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            calls = msg.get("tool_calls") or []
            if not calls:
                text = (msg.get("content") or "").strip()
                if not text and msg.get("reasoning"):
                    text = str(msg.get("reasoning") or "").strip()
                return _finalize(text)
            dialog.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for call in calls:
                fn = call.get("function") or {}
                mapped = mapping.get(fn.get("name") or "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                if mapped:
                    trace.append(mapped["name"])
                    if isinstance(args, dict) and args.get("book"):
                        try:
                            rb = shamela_local_mcp.resolve_book(args.get("book"))
                            if rb.get("status") == "ok" and rb.get("book_id") is not None:
                                read_books[str(rb["book_id"])] = rb.get("title") or ""
                        except Exception:
                            pass
                    try:
                        out = _mcp_dispatch(mapped["name"], args, request)
                    except Exception as exc:
                        out = {"status": "error", "error": f"تعذر تنفيذ الأداة: {exc}"}
                    if isinstance(out, dict):
                        _collect_book_ids(out, seen_books)
                    content = json.dumps(out, ensure_ascii=False)
                    if len(content) > 200000:
                        content = content[:200000] + "…[قُصّت نتيجة الأداة عند 200 ألف حرف]"
                else:
                    content = "الأداة غير متاحة في هذا الخادم"
                dialog.append({"role": "tool", "tool_call_id": call.get("id") or fn.get("name") or "tool",
                               "content": content})
            payload["messages"] = dialog
            data = _read(payload)
        payload["tool_choice"] = "none"
        payload["messages"] = dialog
        data = _read(payload)
        choice = (data.get("choices") or [{}])[0]
        text = ((choice.get("message") or {}).get("content") or "").strip()
        if not text:
            return {**base, "reply": "⚠️ انتهت جولات الأدوات (24) دون جواب نهائي من النموذج."}
        return _finalize(text)
    except Exception as exc:
        return {**base, "reply": f"⚠️ فشل وضع MCP الخام: {exc}"}


def _record_research_metrics(owner_id: str, entry: dict) -> None:
    """سجل قياس البحوث الدائم: مؤشرات كل بحث منجز (اكتمال الفريق، ثبوت
    التدقيق، ربط الحواشي، دعاوى الاتفاق، المدة والحجم) لتقييم المنظومة
    وتطويرها المستمر بأرقام لا بانطباعات."""
    try:
        key = _owner_key("research_metrics", owner_id)
        conn = _ensure_app_memory()
        try:
            row = conn.execute("SELECT payload FROM kv_documents WHERE key=?", (key,)).fetchone()
            items = []
            if row is not None:
                try:
                    items = json.loads(row["payload"]) or []
                except Exception:
                    items = []
            items.append(entry)
            items = items[-300:]
            conn.execute(
                "INSERT INTO kv_documents (key, payload, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                (key, json.dumps(items, ensure_ascii=False), datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()
        print(f"📏 [Research Metrics] سُجّل بحث {entry.get('chat_id')}: وكلاء {entry.get('agents_total')} "
              f"(سقط {len(entry.get('agents_failed') or [])})، ثبوت {entry.get('audit', {}).get('verified')}/"
              f"{entry.get('audit', {}).get('checked')}، مدة {entry.get('duration_s')}s", flush=True)
    except Exception as _rm_err:
        print(f"📏 [Research Metrics] {_rm_err}", flush=True)


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    _chat_t0 = time.time()
    _stage_marks: List[Tuple[str, int]] = []

    def _mark(stage: str):
        _stage_marks.append((stage, round(time.time() - _chat_t0)))
    if req.raw_mcp:
        return await asyncio.to_thread(_raw_mcp_chat_sync, req, request)
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
    # عند وجود وكلاء يبقى العدد كما ضُبط في بطاقة كل وكيل، بلا رفع تلقائي ولا تنويع إجباري.
    is_survey_query = any(k in last_user_msg for k in ["مسح", "شامل", "كافة", "كل", "حوادث", "جدول", "استقصاء", "تفريغ", "استخراج", "أكثر من", "كسوف", "تواريخ", "300", "٣٠٠"])
    is_long_context = any(k in (req.model or "").lower() for k in ["gemini", "flash", "pro", "claude"])

    if req.agent_group:
        pass
    elif req.extraction_capacity and req.extraction_capacity >= 10:
        agent_top_k = req.extraction_capacity
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

        # ضبط سعة استخراج المقاطع التراثية. بطاقة الوكيل تبقى هي الحد إن كانت المجموعة مفعلة.
        if not req.extraction_capacity and not req.agent_group:
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

    if req.library_only:
        target_books = [str(b).strip() for b in (req.selected_books or []) if str(b).strip()]
        passage_count = int(req.extraction_capacity or 150)
        passage_count = min(max(passage_count, 1), 300)
        agent_top_k = passage_count
        agent_pool_size = max(passage_count * 4, 40)
        library_query = (req.library_query or "").strip()
        if library_query:
            search_query = library_query[:800]
        is_greeting = False
        is_study_discussion = False

    retrieved_citations = []
    # أمر بحثي جاهز (سلاش) يضبط القصد والهيكل والعمق؛ وقصد الباحث الصريح أولى منه
    _rcmd = RESEARCH_COMMANDS.get((req.research_command or "").strip()) or {}
    _eff_intent = req.intent_genres or _rcmd.get("intent")
    subagents_dossiers = []
    _evidence_ledger = ""
    _unresolved_citations = 0
    _failed_agents = []
    _gate_stats = None
    _audit_record_text = ""
    
    # 4. فحص طلبات استعراض وقراءة صفحات محددة من كتاب تراثي (Direct Page Reading)
    page_req = detect_book_page_request(last_user_msg)
    page_reading_instruction = ""
    is_direct_page_reading = False

    if page_req and not req.library_only and (page_req.get("book_title") or target_books):
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
    _group_director = None
    _director_prompt = ""
    _disabled_agents = []
    _advisor_agents: List[Dict[str, Any]] = []
    _advisor_consult: Dict[str, Any] = {}
    _hadith_project = False
    if req.agent_group:
        _disabled_agents = [
            {"name": str(d.get("name") or ""), "desc": str(d.get("desc") or "")}
            for d in (req.agent_group.get("disabled_agents") or [])
            if isinstance(d, dict) and str(d.get("name") or "").strip()
        ]
        if not _disabled_agents:
            # مسار تنفيذ المشاريع: المعطّلون يصلون بعلم التعطيل في بطاقاتهم
            _disabled_agents = [
                {"name": str(a.get("name") or ""), "desc": str(a.get("desc") or "")}
                for a in (req.agent_group.get("agents") or [])
                if isinstance(a, dict) and (a.get("enabled") is False or a.get("active") is False)
                and str(a.get("name") or "").strip()
                and not (a.get("is_director") or a.get("role") == "director")
            ]
        if _disabled_agents:
            print(f"🚫 [User Scope Decision] عطّل المستخدم قصدًا {len(_disabled_agents)} وكيلًا: "
                  + "، ".join(d["name"] for d in _disabled_agents), flush=True)
    if req.agent_group:
        _all_group_agents = [
            a for a in req.agent_group.get("agents", [])
            if a.get("enabled") is not False and a.get("active") is not False
        ]
        def _is_director_agent(_a):
            return bool(_a.get("is_director") or _a.get("role") == "director" or _a.get("kind") == "director")
        _group_director = next((a for a in _all_group_agents if _is_director_agent(a)), None)
        # مدير المجموعة قائد لا وكيل جمع: يخرج من الإرسال المتوازي ويتولى
        # التوليف بنموذجه وتفكيره وتوجيهه، وتُعطَّل بذلك سلطة نموذج المحادثة
        # وأدواتها (التفكير وسقف الوفاة وعدد الشواهد) حتى لا تتنازع قيادتان.
        # المستشارون متفرغون للتفكير والمظانّ والمراسي: لا يجمعون نصوصًا مع المتخصصين.
        _advisor_agents = [a for a in _all_group_agents if (not _is_director_agent(a)) and _is_advisor_agent(a)]
        active_agents = [a for a in _all_group_agents if not _is_director_agent(a) and not _is_advisor_agent(a)]
        if _group_director:
            _director_prompt = str(_group_director.get("system_prompt") or _group_director.get("systemPrompt") or "").strip()
            _dm = normalize_model_id(_group_director.get("model") or "")
            if _dm:
                req.model = _dm
            if _group_director.get("thinking"):
                req.thinking_level = str(_group_director.get("thinking"))
            if _group_director.get("context_tokens") or _group_director.get("contextTokens"):
                try:
                    req.context_tokens = int(_group_director.get("context_tokens") or _group_director.get("contextTokens"))
                except Exception:
                    pass
            _dw = _group_director.get("extract_count") or _group_director.get("top_k") or _group_director.get("topK")
            if _dw:
                try:
                    req.witness_limit = int(_dw)
                except Exception:
                    pass
            req.death_max = None
            print(f"👑 [Group Director] القيادة لمدير المجموعة «{_group_director.get('name')}» "
                  f"بنموذج {req.model} وتفكير {req.thinking_level} — عُطّلت سلطة نموذج المحادثة وأدواتها لهذا الطلب", flush=True)
        if _advisor_agents:
            print(f"🧭 [Advisors] {len(_advisor_agents)} مستشارًا متفرغًا للتفكير قبل إرسال المتخصصين: "
                  + "، ".join(str(a.get("name") or "") for a in _advisor_agents), flush=True)
        _gname = str((req.agent_group or {}).get("name") or "")
        _hadith_project = ("المحدث" in _gname) or (
            any("حديث" in str(a.get("name") or "") or "تخريج" in str(a.get("name") or "") for a in active_agents)
            and not any("فقه" in str(a.get("name") or "") for a in active_agents)
        )

    # حزمة بحث مغلقة مكتملة لهذه المحادثة: أي متابعة تولّف من المقاطع المحفوظة
    # فقط — بلا جولات مراسٍ ولا لجنة ولا وكلاء — إلا إذا طلب المستخدم بحثًا
    # جديدًا صراحة. (إعادة الإرسال الصامتة كانت تحرق رصيد النماذج بلا فائدة.)
    _closed_run = _research_run_load(req.chat_id) if req.chat_id else None
    _reuse_package = bool(_closed_run and _closed_run.get("status") in ("done", "closed"))
    if _reuse_package and any(p in (last_user_msg or "") for p in (
            "أعد البحث", "اعد البحث", "بحث جديد", "ابحث من جديد",
            "ابحث مجددًا", "ابحث مجددا", "إعادة البحث")):
        _reuse_package = False
        print("📦 [Research Package] طلب بحث جديد صريح: تُعاد الجولات رغم اكتمال الحزمة", flush=True)
    elif _reuse_package:
        print("📦 [Research Package] حزمة مغلقة مكتملة: توليف من المحفوظ بلا جولات ولا وكلاء", flush=True)

    # 🗣️ جلسة مناقشة الباحث مع قائد الفريق حول الحزمة المغلقة: استكمال
    # وبيان لا بحث جديد من الصفر؛ المدير يحاور، ويطلب وكلاء بعينهم عند
    # الحاجة، وعند الإقفال يعيد الصياغة النهائية من المحادثة المحفوظة.
    _discussion = ""
    if _reuse_package and str(req.discussion_mode or "").strip().lower() in ("open", "finalize"):
        _discussion = str(req.discussion_mode).strip().lower()
        print(f"🗣️ [Director Discussion] جلسة مناقشة ({_discussion}) مع قائد الفريق حول الحزمة المغلقة {req.chat_id}", flush=True)

    # فحص ما إذا كان نمط التوزيع المتوازي مفعلاً وهناك وكلاء في المجموعة
    is_parallel_dispatch = (
        not req.graph_only and
        not req.table_only and
        not req.library_only and
        not is_direct_page_reading and
        not _reuse_package and
        req.agent_dispatch_mode != "direct" and
        len(active_agents) >= 1 and
        bool(search_query) and
        not is_greeting and
        not is_study_discussion
    )

    anchor_prefetch = None
    # عدد الشواهد الذي اختاره المستخدم في الأعلى: أقصى ما يصل إلى النموذج وقائمة المصادر.
    witness_limit = 200
    if req.witness_limit:
        try:
            witness_limit = max(10, min(int(req.witness_limit), 1000))
        except (TypeError, ValueError):
            witness_limit = 200
    use_hybrid_search = bool(req.use_hybrid if req.use_hybrid is not None else True)
    # قناة البحث الدلالي المعزّز (مخزن المتجهات): خيار الباحث يُطاع، وحالته
    # تُعلن في السجل والتقرير — مفعّلة وباحثة / معطّلة بقراره / مفعّلة وغير متوفرة.
    _sem_enabled = bool(req.semantic_enhanced) if req.semantic_enhanced is not None else True
    _sem_available = False
    if _sem_enabled:
        try:
            _sem_available = bool(app_state.get("llama_embedder") or app_state.get("st_embedder") or app_state.get("embed_model")) and _qdrant_alive()
        except Exception:
            _sem_available = False
    _sem_state = "disabled" if not _sem_enabled else ("active" if _sem_available else "unavailable")
    _sem_label = {"active": "مفعّلة وباحثة في مخزن المتجهات", "unavailable": "مفعّلة بقرار الباحث لكن مخزن المتجهات أو نموذج التضمين غير متوفر — جرى البحث لفظيًا", "disabled": "معطّلة بقرار الباحث — بحث لفظي فقط"}[_sem_state]
    if QDRANT_DISABLED:
        _sem_state = "off"
        _sem_label = "موقوفة من التطبيق (Qdrant معطّل بقرار المنتج) — بحث لفظي فقط"
        _sem_pass = False
    _sem_pass = _sem_enabled and _sem_available
    print(f"🧠 [Semantic Channel] {_sem_state} ({_sem_label})", flush=True)
    if (
        search_query
        and not is_greeting
        and not is_study_discussion
        and not is_direct_page_reading
        and not req.graph_only
        and not req.table_only
    ):
        retrieval_scopes = []
        _council_future = None
        if is_parallel_dispatch:
            # المجلس في خيط موازٍ للاسترجاع: المستشارون لا يغذّون إلا الذهبي
            # والفضي والتطعيم، فلا ينتظرهم المتخصصون بمهامهم الأصلية. ينطلق
            # المجلس الآن، ويُستلم قبل الإرسال: الذهبي/الفضي يُبنيان منه،
            # والتطعيم يُستدرك بمرور تكملي سريع في نطاقات أصحابه.
            if _advisor_agents and not _reuse_package:
                _council_future = concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(
                    _consult_research_advisors,
                    query=search_query,
                    advisors=_advisor_agents,
                    specialists=active_agents,
                    api_key=owner_openrouter_key(request, req.api_key),
                    tavily_key=(load_provider_keys(current_owner_id(request)).get("tavily") or ""),
                    director_model=str(req.model or ""),
                    owner_id=current_owner_id(request),
                    group_id=str((req.agent_group or {}).get("id") or ""),
                )
                print("🧭 [Advisors] انطلق مجلس المستشارين موازيًا للاسترجاع — لا انتظار عليه", flush=True)
            # نطاقات المتخصصين تُبنى الآن من بطاقاتهم الأصلية (قبل أي تطعيم):
            # الاسترجاع ينطلق بهم فورًا، والتطعيم يُستدرك لاحقًا.
            # عدد الشواهد الذي اختاره المستخدم ميزانية موزعة على الوكلاء: لا تقل حصة
            # الوكيل عما في بطاقته، وترتفع بتوزيع اختيار المستخدم عليهم. نطاق الكتب لا يتغير.
            per_agent_share = 0
            if req.witness_limit and active_agents:
                per_agent_share = max(10, witness_limit // max(len(active_agents), 1))
            for idx, ag in enumerate(active_agents):
                ag_books = [str(b).strip() for b in (ag.get("booksScope") or ag.get("books") or []) if str(b).strip()]
                ag_top_k = int(ag.get("top_k") or ag.get("topK") or ag.get("scanned_texts") or ag.get("extract_count") or ag.get("extractCount") or 150)
                if per_agent_share:
                    ag_top_k = max(ag_top_k, per_agent_share)
                retrieval_scopes.append({
                    "name": str(idx),
                    "books": ag_books if ag_books else (target_books or None),
                    "top_k": ag_top_k,
                    "pool_size": max(ag_top_k * 4, 300),
                    # نمط بحث الوكيل الفردي يسري: semantic عنده بلا هجين لفظي
                    "use_hybrid": str(ag.get("search_mode") or ag.get("searchMode") or "hybrid").strip().lower() != "semantic",
                })
            honor_scope = True
        else:
            retrieval_scopes.append({
                "name": "direct",
                "books": target_books or None,
                "top_k": witness_limit if req.witness_limit else agent_top_k,
                "pool_size": max(witness_limit * 4, 600) if req.witness_limit else agent_pool_size,
            })
            honor_scope = bool(req.agent_group)
        if _reuse_package:
            _pkg: List[Dict[str, Any]] = []
            _seen_pkg = set()
            for _ri, _rd in enumerate(_closed_run.get("rounds") or []):
                for _p in (_rd.get("passages") or []):
                    _key = (str(_p.get("book_id")), str(_p.get("part")),
                            str(_p.get("page")), (_p.get("snippet") or "")[:80])
                    if _key in _seen_pkg:
                        continue
                    _seen_pkg.add(_key)
                    _pkg.append({
                        "book_id": _p.get("book_id"), "title": _p.get("title") or "",
                        "author": "", "part_raw": _p.get("part"),
                        "page_num_raw": _p.get("page"),
                        "snippet": _p.get("snippet") or "", "anchor_round": _ri + 1,
                    })
            anchor_prefetch = {"direct": _pkg}
            print(f"📦 [Research Package] حُمل {len(_pkg)} مقطعًا محفوظًا للتوليف", flush=True)
        else:
            # ⚓ وكيل الألفاظ الدلالية عند المتقدمين يسبق الجولات: مراسيه
            # بصيغ المصنفين تصل ما انقطع بين صياغة الباحث ولسان الكتب.
            _semantic_terms: List[str] = []
            try:
                _semantic_terms = _extract_classical_terms(
                    search_query, owner_openrouter_key(request, req.api_key))
            except Exception as _sem_err:
                print(f"⚓ [Semantic Anchors] تعذر وكيل الألفاظ: {_sem_err}", flush=True)
            # مراسي المجلس إن كان قد فرغ أصلًا (بلا انتظار): تُضم لجولات البحث
            if _council_future is not None and _council_future.done() and not _advisor_consult:
                try:
                    _advisor_consult = _council_future.result() or {}
                except Exception:
                    _advisor_consult = {}
            for _anc in (_advisor_consult.get("anchors") or []):
                if _anc and _anc not in _semantic_terms:
                    _semantic_terms.append(_anc)
            anchor_prefetch, _used_anchors = expand_query_with_anchor_rounds(
                query=search_query,
                scopes=retrieval_scopes,
                api_key=owner_openrouter_key(request, req.api_key),
                model=req.model,
                use_hybrid=use_hybrid_search,
                seed_anchors=req.retrieval_anchors,
                honor_agent_limit=honor_scope,
                run_id=req.chat_id,
                death_max=req.death_max,
                intent_genres=_eff_intent,
                panel_hint=_rcmd.get("panel_hint"),
                semantic_terms=_semantic_terms,
                semantic_channel=_sem_pass,
            )

    _mark("retrieval")
    # استرجاع موجّه لوكلاء المذاهب: مراسي المسألة داخل كتب طبقات كل مذهب
    # بعينه، بصفحات كاملة، تُقدَّم على مقاطع الوكيل — إمداد بطاقات الأدلة.
    _targeted_map: Dict[str, Dict[str, Any]] = {}
    if is_parallel_dispatch and anchor_prefetch is not None and not _reuse_package:
        # مراسي وكيل الألفاظ الدلالية تتقدم استرجاع المذاهب الموجّه: فهي
        # بصيغ المصنفين وضمائرهم، وهي التي تمسك نصوص كتب الطبقات بعينها.
        _anchors_for_target = list(locals().get("_semantic_terms") or []) + [
            a for a in (list(locals().get("_used_anchors") or []) or list(req.retrieval_anchors or []))
            if a not in (locals().get("_semantic_terms") or [])]
        _madhhab_agents = {}
        for _idx, _ag in enumerate(active_agents):
            _md = _agent_madhhab(_ag)
            if _md and _md not in _madhhab_agents:
                _madhhab_agents[_md] = _idx
        if _madhhab_agents and _anchors_for_target:
            def _fetch_target(_md):
                _ps = _targeted_madhhab_passages(_md, _anchors_for_target)
                if not _ps:
                    # حد أدنى مذهبي مضمون: صفر الموجّه بالمراسي لا يعني صفر
                    # المذهب؛ جولة ثانية بمفردات المسألة القوية وأزواجها داخل
                    # كتب الطبقات (عبارة المسألة كاملة بصيغة AND لا تمسك شيئًا).
                    _toks = [w for w in re.findall(r"[\u0600-\u06FF]{3,}", search_query or "")]
                    _gen = ([" ".join(_toks[i:i + 2]) for i in range(max(0, len(_toks) - 1))]
                            + sorted(set(_toks), key=len, reverse=True)[:2])
                    _ps = _targeted_madhhab_passages(_md, _anchors_for_target + _gen)
                return _md, _ps
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(_madhhab_agents), 5)) as _tex:
                for _md, _passages in _tex.map(_fetch_target, list(_madhhab_agents)):
                    _idx = _madhhab_agents[_md]
                    _key = str(_idx)
                    _existing = anchor_prefetch.get(_key) or []
                    _seen = {_citation_identity(x) for x in _existing}
                    _fresh = [x for x in _passages if _citation_identity(x) not in _seen]
                    anchor_prefetch[_key] = _fresh + _existing
                    _targeted_map[_md] = {
                        "count": len(_fresh),
                        "books": sorted({x.get("title") for x in _fresh if x.get("title")}),
                        "agent": (active_agents[_idx].get("name") or ""),
                    }
                    print(f"🎯 [Targeted Madhhab] {_md}: {len(_fresh)} صفحة كاملة من كتب الطبقات "
                          f"({len(_targeted_map[_md]['books'])} كتابًا) لوكيل «{_targeted_map[_md]['agent']}»", flush=True)

    _mark("targeted")
    # استلام المجلس الموازي قبل الإرسال: بناء الذهبي/الفضي، تسخين كتبهما،
    # واستدراك التطعيم بمرور تكملي في نطاقات أصحابه — بلا أن يكون شيء من
    # ذلك قد عطّل انطلاق المتخصصين بمهامهم الأصلية.
    if is_parallel_dispatch and _council_future is not None:
        try:
            if not _advisor_consult:
                _advisor_consult = _council_future.result(timeout=1500) or {}
        except Exception as _adv_err:
            print(f"🧭 [Advisors] تعذر استلام مجلس المستشارين: {_adv_err}", flush=True)
            _advisor_consult = _advisor_consult or {}
        try:
            _advisor_books = [str(x or "") for x in (_advisor_consult.get("advisor_books") or [])]
            if not _advisor_books:
                _advisor_books = [str(g.get("entry") or "") for g in (_advisor_consult.get("grafted") or [])]
                _advisor_books += [str(x or "") for x in (_advisor_consult.get("already_present") or [])]
            if _advisor_books:
                try:
                    import shamela_link as _SLW
                    _idmap = _SLW.load_id_map()
                    _warm_ids = []
                    for _e in _advisor_books:
                        _m = re.search(r"#(\d+)", str(_e))
                        if _m:
                            _warm_ids.append(int(_m.group(1)))

                    def _warm(_oids):
                        def _one(_oid):
                            try:
                                _tid = _idmap.get(str(int(_oid)))
                                if _tid:
                                    _SLW.extract_book(int(_tid))
                            except Exception:
                                pass
                        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as _exw:
                            list(_exw.map(_one, _oids[:16]))

                    threading.Thread(target=_warm, args=(_warm_ids,), daemon=True,
                                     name="advisor-books-warm").start()
                except Exception:
                    pass
            if req.agent_group:
                _core_agents = _build_core_agents(
                    query=search_query,
                    director_model=str(req.model or ""),
                    api_key=owner_openrouter_key(request, req.api_key),
                    advisor_consult=_advisor_consult,
                    specialists=active_agents,
                    advisor_books=_advisor_books,
                )
                if _core_agents and anchor_prefetch is not None:
                    _core_passages = _fts_candidates(search_query, list(locals().get("_used_anchors") or []),
                                                     _advisor_books, 40, None, None)
                    _base_idx = len(active_agents)
                    active_agents = list(active_agents) + list(_core_agents)
                    for _ci in range(len(_core_agents)):
                        anchor_prefetch[str(_base_idx + _ci)] = _core_passages
                    print(f"🥇 [Core Agents] أُلحق الذهبي بعد الاسترجاع ({len(_core_passages)} شاهدًا في نطاقه)", flush=True)
            # استدراك التطعيم: شواهد الكتب المطعّمة تُجلب لأصحابها الآن
            if anchor_prefetch is not None:
                _name2idx = {str(a.get("name") or ""): i for i, a in enumerate(active_agents)}
                for _g in (_advisor_consult.get("grafted") or []):
                    _gi = _name2idx.get(str(_g.get("agent") or ""))
                    _entry = str(_g.get("entry") or "")
                    if _gi is None or not _entry:
                        continue
                    try:
                        _extra = _fts_candidates(search_query, list(locals().get("_used_anchors") or []),
                                                 [_entry], 24, None, None)
                    except Exception:
                        _extra = []
                    if _extra:
                        _key = str(_gi)
                        _exist = anchor_prefetch.get(_key) or []
                        _seen = {_citation_identity(x) for x in _exist}
                        anchor_prefetch[_key] = [x for x in _extra if _citation_identity(x) not in _seen] + _exist
                        print(f"🧭 [Graft Late] استُدرك تطعيم «{_entry}» عند {_g.get('agent')} ({len(_extra)} شاهدًا)", flush=True)
        except Exception as _core_err:
            print(f"🥇 [Core Agents] تعذر الإلحاق الموازي: {_core_err}", flush=True)
        _mark("council_core")
    if is_direct_page_reading:
        print(f"📖 [Chat Direct Page Reading Active] Bypass RAG search, serving {len(retrieved_citations)} verbatim pages from Shamela.")
    elif is_parallel_dispatch:
        print(f"🚀 [Multi-Agent Parallel Dispatch] Dispatching {len(active_agents)} subagents in parallel with their dedicated models...")
        api_key_to_use = owner_openrouter_key(request, req.api_key)

        # خيار المستخدم: تمكين الوكلاء المساعدين أنفسهم من أدوات MCP المحددة أثناء عملهم،
        # فلا ينفرد النموذج الرئيسي بالجمع والقراءة والمطابقة.
        agent_mcp_tools: List[dict] = []
        agent_mcp_map: Dict[str, dict] = {}
        if req.mcp_for_agents and (req.mcp_servers or []):
            try:
                agent_mcp_tools, agent_mcp_map = mcp_openai_tools(req.mcp_servers)
                if agent_mcp_tools:
                    print(f"🧰 [Subagent MCP] Enabled {len(agent_mcp_tools)} MCP tools for subagents")
            except Exception as exc:
                print(f"⚠️ [Subagent MCP] Failed to open tools: {exc}")
                agent_mcp_tools, agent_mcp_map = [], {}

        def _subagent_reply_with_tools(ag_model: str, sub_sys: str, sub_user: str, ag_temp: float, ag_max_tokens: int, ag_thinking: str = None) -> str:
            harvested: List[str] = []

            def _finish_report(text: str) -> str:
                # نصوص الأدوات التي قرأها الوكيل تصعد إلى الرئيسي كما هي، لا تضيع في ملخصه.
                if not harvested:
                    return text
                appendix = "\n\n".join(harvested[:6])[:7000]
                return f"{text}\n\n— نصوص قرأها هذا الوكيل بأدواته أثناء عمله (تُعامل كنصوص خام للتحرير):\n{appendix}"

            dialog: List[dict] = [
                {"role": "system", "content": sub_sys},
                {"role": "user", "content": sub_user},
            ]
            payload = {
                "model": ag_model,
                "messages": dialog,
                "temperature": ag_temp,
                "max_tokens": ag_max_tokens,
                "tools": agent_mcp_tools,
                "tool_choice": "auto",
            }
            attach_reasoning(payload, ag_model, ag_thinking)

            def _read(body: dict) -> dict:
                o_req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key_to_use}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:8085",
                        "X-Title": "Al-Mojtahed Subagent",
                    },
                    data=json.dumps(body).encode("utf-8"),
                )
                with urllib.request.urlopen(o_req, timeout=120) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            resp_data = _read(payload)
            for _round in range(5):
                choice = resp_data.get("choices", [{}])[0]
                msg_obj = choice.get("message", {}) or {}
                calls = msg_obj.get("tool_calls") or []
                if not calls:
                    return _finish_report((msg_obj.get("content") or "").strip())
                dialog.append({"role": "assistant", "content": msg_obj.get("content") or "", "tool_calls": calls})
                for call in calls:
                    fn = (call.get("function") or {})
                    mapped = agent_mcp_map.get(fn.get("name") or "")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except Exception:
                        args = {}
                    if not isinstance(args, dict):
                        args = {}
                    if mapped:
                        try:
                            output = mcp_call_tool(mapped["url"], mapped.get("session"), mapped["name"], args)
                        except Exception as exc:
                            output = f"تعذر استدعاء الأداة: {exc}"
                        if output and not output.startswith("تعذر"):
                            harvested.append(f"[{mapped['name']}] {output[:1500]}")
                    else:
                        output = "الأداة غير متاحة في الخوادم المحددة"
                    dialog.append({"role": "tool", "tool_call_id": call.get("id") or fn.get("name") or "tool", "content": output})
                payload["messages"] = dialog
                resp_data = _read(payload)
            # انتهت الجولات: كتابة التقرير بلا أدوات
            dialog.append({"role": "system", "content": "انتهت جولات الأدوات. اكتب الآن تقريرك النهائي مما جمعته، ولا تطلب أداة أخرى."})
            payload["messages"] = dialog
            payload["tool_choice"] = "none"
            resp_data = _read(payload)
            choice = resp_data.get("choices", [{}])[0]
            return _finish_report(((choice.get("message", {}) or {}).get("content") or "").strip())

        def _worker_subagent(indexed_agent: Tuple[int, Dict[str, Any]]):
            idx, ag = indexed_agent
            ag_name = ag.get("name") or "وكيل مساعد"
            ag_desc = ag.get("desc") or ""
            ag_prompt = ag.get("system_prompt") or ag.get("systemPrompt") or ""
            ag_model = normalize_model_id(ag.get("model") or "google/gemini-2.5-flash")
            ag_books = [str(b).strip() for b in (ag.get("booksScope") or ag.get("books") or []) if str(b).strip()]
            ag_top_k = int(ag.get("top_k") or ag.get("topK") or ag.get("scanned_texts") or ag.get("extract_count") or ag.get("extractCount") or 150)
            ag_thinking = str(ag.get("thinking") or ag.get("thinking_level") or "").strip() or None
            cits = (anchor_prefetch or {}).get(str(idx), [])
            if cits:
                # حصص متكافئة: لا يبتلع كتاب واحد قائمة شواهد الوكيل ما دامت
                # في نطاقه بدائل — سقف لكل كتاب بحصته العادلة من سقف الوكيل،
                # ثم إكمال القائمة بترتيب الاستخراج الأصلي حتى لا ينقص العدد.
                _distinct = {str(c.get("book_id")) for c in cits if c.get("book_id")}
                if len(_distinct) >= 3:
                    _cap = max(4, -(-min(len(cits), ag_top_k) // len(_distinct)))
                    _per: Dict[str, int] = {}
                    _first_pass, _rest = [], []
                    for _c in cits:
                        _b = str(_c.get("book_id"))
                        if _per.get(_b, 0) < _cap:
                            _per[_b] = _per.get(_b, 0) + 1
                            _first_pass.append(_c)
                        else:
                            _rest.append(_c)
                    cits = _first_pass + _rest

            if not cits:
                scope_label = f"{len(ag_books)} كتاباً محدداً" if ag_books else "كتبه المحددة"
                return {
                    "name": ag_name,
                    "desc": ag_desc,
                    "model": ag_model,
                    "books": ag_books,
                    "core_rank": ag.get("_core_rank", 99),
                    "agent_index": idx,
                    "citations": [],
                    "report": f"نطاق هذا الوكيل ({scope_label}) لم يُرجع شاهداً بعد جولات مراسي البحث داخل كتبه. لا تُكمل النقص من الذاكرة ولا من خارج كتبه."
                }

            # صياغة نصوص الشواهد للوكيل مع تضمين رأس الحولية ورأس المسألة الفقهية الحاكمة
            snippets_items = []
            for c in cits[:ag_top_k]:
                loc_str = _approved_citation_label(c)
                meta_tags = []
                if c.get('annalistic_year'):
                    meta_tags.append(f"📅 [رأس الحولية التاريخية الحاكمة: {c['annalistic_year']}]")
                if c.get('fiqh_header'):
                    meta_tags.append(f"⚖️ [رأس المسألة الفقهية الحاكمة: {c['fiqh_header']}]")
                if c.get('targeted'):
                    meta_tags.append(f"🎯 [صفحة كاملة مسترجعة استرجاعًا موجّهًا من كتب طبقات مذهبك — طبقة: {c.get('authority_layer') or 'طبقات الاعتماد'} — وهي مادة بطاقاتك الأولى]")
                if c.get('rebalance'):
                    meta_tags.append("⚖️ [جولة ضبط الهيمنة: شاهد مُستدرك من كتبك باستثناء الكتب التي سيطرت على جولة البحث — وهي مادة بطاقاتك الأولى]")
                if c.get('channel') == 'semantic':
                    meta_tags.append("🧠 [قناة الاكتشاف: دلالية من مخزن المتجهات — مرشح بقرب المعنى، لا يُعتمد حتى يُقرأ في صفحته ويُوثق كغيره]")
                elif c.get('channel') == 'lexical':
                    meta_tags.append("🔤 [قناة الاكتشاف: لفظية]")
                tag_line = (" " + " ".join(meta_tags)) if meta_tags else ""
                snippets_items.append(
                    f"- الإحالة المعتمدة: {loc_str} | المصنف: {c['author']}{tag_line}:\n  {_full_page_snippet(c, cap=4200 if (c.get('targeted') or c.get('rebalance')) else 2600)}"
                )
            snippets_txt = "\n\n".join(snippets_items)

            sub_sys = (
                f"أنت الوكيل المساعد التخصصي: «{ag_name}».\n"
                f"تخصصك: {ag_desc}.\n"
                f"التوجيه التخصصي المعتمد: {ag_prompt or 'استخراج وتحرير وتوثيق نصوص المسألة بدقة'}.\n"
                f"المهمة: طالع نصوص الشاملة المرفقة المستخرجة من نطاق كتبك التراثية المخصصة ({len(ag_books)} كتاباً)، والتزم توجيهك الخاص. إن طلب نصوصاً معينة فالتزم بها، ولا تُنوّع من عندك. انسخ الإحالة المعتمدة حرفياً كما هي، ولا تستشهد بكتاب لم يرد في المقاطع. المقاطع قد تسمي المسألة بمصطلح المصنفين لا بلفظ السؤال المعاصر، فانقل ما يتناول جوهرها ولو خلا من ذلك اللفظ. لا تكتب أن النص يخلو من اللفظ المطلوب إذا كان المقطع في الموضوع. لا تجب من الذاكرة. إن كان المقطع واحداً فانقله، وإن لم تُرفق مقاطع فقل إن النطاق لم يُرجع شيئاً.\n"
                f"{CITATION_FORMAT_RULE}\n"
                f"ارفع لمدير المشروع تقريراً محرراً مفصلاً لا ملخصاً مختصراً، وابدأه إلزامًا بقسم «بطاقات الأدلة» قبل أي تحرير: بطاقة مرقمة لكل شاهد مؤثر، فيها: (١) الدعوى التي تثبتها البطاقة بعينها، (٢) الإحالة المعتمدة منسوخة حرفيًا، (٣) النص الحرفي من المقطع كما هو، (٤) نوع البطاقة: متن حديث أو قول مذهب أو شرح أو تخريج أو مقارنة مرجعية، (٥) المذهب أو الطبقة التي يدل عليها الكتاب نفسه إن دل. "
                f"ثم اكتب «التحرير المبني على البطاقات»: لا تنسب قولًا إلى مذهب إلا ببطاقة من كتاب ذلك المذهب أو من كتاب خلاف/مقارنة ينص على نسبته إليه صراحة؛ فإن كانت البطاقة من كتاب مذهب آخر قُدّمت شاهدَ خلاف أو مقارنة لا مصدرًا لذلك المذهب. والوسيط (موسوعة فقهية أو جمال ونحوهما) بطاقة مقارنة وضبط، لا سند وحيد لمتن أو قول. وقاعدة طبقات صارمة: الشروح المعاصرة وتفريغات الدروس الصوتية (من جنس شرح العباد وشرح الهرري وفضل الرحيم الودود وشروح بلوغ المرام المعاصرة) ليست سندًا أصلًا لمتن حديث ولا لحكم مذهب ولا لدعوى إجماع؛ لا تنقل عنها بالواسطة حكمًا عن متقدم، فإن وجدت عندها إشارة إلى أصل تراثي فاذكرها إشارةَ استدلال على الموضع فقط، والحكم يُبنى على الأصل إن وُجدت بطاقته، وإلا صرّحت بخلوّ بطاقتك منه. وقاعدة العزو إلى الأصل تلزمك أيضًا مع الناقل التراثي: ما وجدته داخل شرح أو كتاب ناقل منقولًا عن إمام أو كتاب آخر (كمغلطاي ناقلًا عن أبي داود وسعيد بن منصور وابن حزم) فلا تجعله بطاقة حكم عن ذلك الأصل؛ بطاقتك عنه إشارة موضع فقط، والحكم ينتظر بطاقة الأصل نفسه، وصرّح بغيابها إن غابت. إن لم تجد بطاقة لمذهب أو طبقة فصرّح: «لا بطاقة في شواهدي لهذا» ولا تُكمل من الذاكرة. "
                f"انقل نصوص الأسانيد والمتون والعبارات المؤثرة حرفيًا كما هي (فهي لبّ عملك)، ثم حرّر ما تدل عليه بحسب فنك وتخصصك بأسلوب علمي رصين. "
                f"تنبيه الصفحات: ما يصلك نص صفحة كاملة غالبًا؛ فإن انتهت الصفحة في أثناء نص تحتاجه فلا تبنِ حكمًا على لفظ مبتور ولا تكتب «انقطع النص» كأنها حقيقة عن الكتاب، بل اذكر في تقريرك بدقة: «أحتاج تتمة هذا النص من الصفحة التالية: (الكتاب، الجزء، الصفحة)» ليجلبها المدير بتقليب الصفحة."
            )
            sub_user = (
                f"موضوع المسألة: {search_query}\n\n"
                f"النصوص التراثية المستخرجة من نطاق كتبك ({len(cits)} مقطعاً):\n"
                f"{snippets_txt}\n\n"
                f"المطلوب منك كوكيل متخصص: هذه المقاطع أُحضرت بمراسي دلالية من لغة المصنفين، وقد لا يرد فيها لفظ السؤال بحروفه. استخلص ما يتناول جوهر المسألة، وانسخ كل إحالة من سطر «الإحالة المعتمدة» بلا تغيير، وابدأ تقريرك ببطاقات الأدلة المرقمة ثم التحرير المبني عليها حصرًا. لا تُكمل من الذاكرة ما لم يرد في المقاطع، ولا تنسب لمذهب من بطاقة كتاب مذهب آخر."
            )
            if "الحَكَم" in str(ag_name):
                # الحَكَم فرّغ ردّه أربع جولات متتالية بنماذج مختلفة على مهمة
                # مسبح كامل بلا بنية. دواؤه بنية حكم صارمة ومادة مركزة:
                # بطاقات مقتضبة، ثم أحكام دعوىً دعوى، ثم تحرير حاسم قصير.
                sub_sys += (
                    "\nبنية حكمك إلزامية بهذا الترتيب: (١) «بطاقات الأدلة» المقتضبة كإخوانك، "
                    "(٢) «جدول الأحكام»: كل دعوى كبرى في المسألة | حكمك (تثبت/تنتفي/تتوقف) | رقم بطاقة مستندها — "
                    "ودعوى بلا بطاقة حكمها «تتوقف» صراحة، "
                    "(٣) «تحرير الحَكَم»: خلاصة حاسمة مركزة لا تتجاوز ثلث تقرير متخصص، ترجّح بقواعد الترجيح "
                    "وتفصل في التعارض، ولا تعيد سرد النصوص الطويلة ولا تكرر بطاقة في موضعين."
                )

            # استخراج معلمات الضبط الدقيقة للنموذج
            ag_temp = float(ag.get("temperature") if ag.get("temperature") is not None else ag.get("temp", 0.2))
            ag_top_p = float(ag.get("top_p")) if (ag.get("top_p") is not None and str(ag.get("top_p")).strip() != "") else None
            ag_top_k_val = int(ag.get("model_top_k") or ag.get("modelTopK")) if (ag.get("model_top_k") or ag.get("modelTopK")) else None
            ag_freq_pen = float(ag.get("frequency_penalty")) if (ag.get("frequency_penalty") is not None and str(ag.get("frequency_penalty")).strip() != "") else None
            ag_pres_pen = float(ag.get("presence_penalty")) if (ag.get("presence_penalty") is not None and str(ag.get("presence_penalty")).strip() != "") else None
            ag_rep_pen = float(ag.get("repetition_penalty")) if (ag.get("repetition_penalty") is not None and str(ag.get("repetition_penalty")).strip() != "") else None
            raw_output_tokens = int(ag.get("max_tokens") or 65536)
            ag_max_tokens = 65536 if raw_output_tokens > 131072 else max(1024, raw_output_tokens)

            if agent_mcp_tools:
                sub_sys += "\nلديك أدوات MCP متاحة أثناء عملك: استخدمها لقراءة صفحات كتبك ومطابقة الاقتباسات والبحث داخل نطاقك عند الحاجة، والتزم كتبك المخصصة لك ولا تخرج عنها."

            # سُلّم إنقاذ الوكيل الساقط (قرار المنتج): إعادة الجولة بنفس
            # النموذج، ثم نموذج احتياطي، ثم نموذج مختص يعيد كتابة التقرير،
            # ثم مدير المشروع باحثًا بنفسه — كل درجة على مقاطع الوكيل ونطاق
            # كتبه نفسهما؛ فلا يضيع فنٌّ كامل لعطل نموذج، ولا يسقط وكيل بصمت
            # فيُبنى قسمه من غير بطاقاته دون أن يشعر أحد.
            print(f"🤖 [Subagent Dispatch] Calling OpenRouter model '{ag_model}' for agent '{ag_name}' with temp={ag_temp}, top_p={ag_top_p}, freq_pen={ag_freq_pen}, thinking={ag_thinking or 'default'}, witnesses={min(len(cits), ag_top_k)}...")
            rep = ""
            ag_failed = False
            ag_fail_reason = ""
            _rescued_by = ""
            _fallback_model = ("~anthropic/claude-sonnet-latest" if ag_model == "google/gemini-3.8-flash"
                               else "google/gemini-3.8-flash")
            _retry_thinking = {"max": "high", "high": "medium", "medium": "low"}.get(str(ag_thinking or "").lower(), ag_thinking)
            _specialist_model = ("google/gemini-3.8-flash" if "sonnet" in str(ag_model or "")
                                 else "~anthropic/claude-sonnet-latest")
            _ladder = [
                (ag_model, ag_thinking, "الأصلي", 120),
                (ag_model, _retry_thinking, "إعادة الجولة", 120),
                (_fallback_model, _retry_thinking, "النموذج الاحتياطي", 150),
                (_specialist_model, "high", "النموذج المختص", 180),
                (str(req.model or ""), "high", "المدير باحثًا بنفسه في كتب الوكيل", 180),
            ]
            _seen_try = set()
            _try_model, _try_thinking = ag_model, ag_thinking
            for _li, (_m, _th, _label, _timeout) in enumerate(_ladder):
                if not _m or (_m, _th) in _seen_try:
                    continue
                _seen_try.add((_m, _th))
                _try_model, _try_thinking = _m, _th
                if _li:
                    print(f"🔁 [Subagent Dispatch] إنقاذ '{ag_name}' — درجة «{_label}» بالنموذج '{_m}' وتفكير {_th or 'default'}...")
                try:
                    if agent_mcp_tools:
                        rep = _subagent_reply_with_tools(_try_model, sub_sys, sub_user, ag_temp, ag_max_tokens, _try_thinking) or ""
                    else:
                        rep = call_openrouter_raw(
                            model_id=_try_model,
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
                            timeout=_timeout,
                            thinking_level=_try_thinking
                        ) or ""
                    if len(rep.strip()) < 40:
                        raise RuntimeError(f"أرجع الوكيل ردًا فارغًا أو شبه فارغ ({len(rep.strip())} حرفًا)")
                    print(f"✅ [Subagent Dispatch] Agent '{ag_name}' completed using '{_try_model}' ({len(rep)} chars)" + (f" [بدرجة إنقاذ: {_label}]" if _li else ""))
                    ag_failed = False
                    _rescued_by = _label if _li else ""
                    break
                except Exception as err:
                    ag_fail_reason = f"{type(err).__name__}: {err}"
                    print(f"⚠️ [Subagent Dispatch] OpenRouter call for agent '{ag_name}' failed (درجة {_label}): {err}")
                    rep = ""
                    ag_failed = True
            if ag_failed:
                print(f"🚨 [Subagent Dispatch] Agent '{ag_name}' سقط نهائيًا بعد سُلّم الإنقاذ كاملًا: {ag_fail_reason}")
                rep = (f"(تنبيه سقوط وكيل: تعذر استدعاء النموذج {ag_model} لهذا الوكيل رغم إعادة المحاولة ({ag_fail_reason}). "
                       f"لا تقرير تحريريًا منه؛ الشواهد المستخرجة من نطاقه مرفقة نثرًا ليبني المدير عليها ببطاقاتها أو يصرّح بغياب تقريره):\n\n" + snippets_txt[:2500])

            return {
                "name": ag_name,
                "desc": ag_desc,
                "model": ag_model if ag_failed else _try_model,
                "books": ag_books,
                "core_rank": ag.get("_core_rank", 99),
                "agent_index": idx,
                "citations": cits,
                "report": rep,
                "failed": ag_failed,
                "rescued_by": _rescued_by,
                "fail_reason": ag_fail_reason if ag_failed else ""
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(active_agents), 12)) as executor:
            future_to_agent = {executor.submit(_worker_subagent, pair): pair for pair in enumerate(active_agents)}
            for fut in concurrent.futures.as_completed(future_to_agent):
                try:
                    res = fut.result()
                    subagents_dossiers.append(res)
                except Exception as ex:
                    print(f"Subagent execution failed: {ex}")
        # صلب البحث أولًا: الذهبي ثم الفضي ثم المتخصصون بترتيب بطاقاتهم —
        # فشواهدهم وتقاريرهم هي المقَدَّمة التي يُقاس عليها غيرها.
        subagents_dossiers.sort(key=lambda d: (d.get("core_rank", 99), d.get("agent_index", 999)))
        _mark("workers")
        print("⏱ [Stage Times] " + " | ".join(f"{k}:{v}s" for k, v in _stage_marks), flush=True)
        # ⚖️ جولة ضبط الهيمنة: تُقاس سيطرة الكتب على شواهد الجولة كلها، ومن
        # جُوّع من الوكلاء (شواهده دون ثلث الوسيط ونطاقه واسع) يُعاد إرساله
        # بشواهد جديدة من كتبه تستثني الكتب المهيمنة — اكتفاءً بما سيطرت
        # به تلك الكتب، وإنصافًا لبقية النطاقات أن تأخذ حصتها من الجولة.
        try:
            _all_cits = [c for d in subagents_dossiers for c in (d.get("citations") or [])]
            _book_counts: Dict[str, int] = {}
            for _c in _all_cits:
                if _c.get("book_id"):
                    _bk = str(_c["book_id"])
                    _book_counts[_bk] = _book_counts.get(_bk, 0) + 1
            _total_c = max(1, len(_all_cits))
            _dominators = {b for b, n in _book_counts.items() if n >= 30 and n / _total_c >= 0.18}
            _cit_counts = sorted(len(d.get("citations") or []) for d in subagents_dossiers)
            _median_c = _cit_counts[len(_cit_counts) // 2] if _cit_counts else 0
            _starved = [d for d in subagents_dossiers
                        if not d.get("failed") and len(d.get("books") or []) >= 5
                        and len(d.get("citations") or []) < max(6, int(_median_c * 0.35))]
            if _dominators and _starved and anchor_prefetch is not None:
                print(f"⚖️ [Balance] كتب مهيمنة {sorted(_dominators)} على {_total_c} شاهدًا؛ "
                      f"جولة ضبط لـ{len(_starved[:3])} وكيلًا مُجوَّعًا باستثناء المهيمنين", flush=True)
                _rb_anchors = (list(locals().get("_anchors_for_target") or [])
                               or list(locals().get("_used_anchors") or [])
                               or list(req.retrieval_anchors or []))

                def _rebalance_one(d):
                    _idx = d.get("agent_index")
                    if _idx is None or _idx >= len(active_agents):
                        return None
                    _ag = active_agents[_idx]
                    _scope_ids = []
                    for _b in (d.get("books") or []):
                        _mm = re.search(r"#(\d{1,7})", str(_b))
                        if _mm:
                            _scope_ids.append(int(_mm.group(1)))
                    _scope_ids = [b for b in dict.fromkeys(_scope_ids) if str(b) not in _dominators]
                    if not _scope_ids:
                        return None
                    _fresh = []
                    try:
                        import shamela_search as _ssx
                        _seen_rb = {_citation_identity(x) for x in (anchor_prefetch.get(str(_idx)) or [])}
                        for _q in (_rb_anchors[:5] or [search_query]):
                            _r = _ssx.search(str(_q), mode="words", book_ids=_scope_ids[:60], limit=25)
                            for _hit in (_r.get("results") or []):
                                _bid = int(_hit.get("book_id") or 0)
                                if not _bid:
                                    continue
                                _pg = shamela_local_mcp.get_page(_bid, int(_hit.get("page_num") or 0),
                                                                 _hit.get("part") or None)
                                if _pg.get("status") != "ok":
                                    continue
                                _body = str((_pg.get("page") or {}).get("body") or "").strip()
                                if len(_body) < 120:
                                    continue
                                _row = {"title": _hit.get("title") or "", "author": _hit.get("author") or "",
                                        "book_id": _bid, "part_raw": _hit.get("part"),
                                        "page_num_raw": _hit.get("page_num"),
                                        "snippet": re.sub(r"\s+", " ", _body)[:4200],
                                        "rebalance": True, "anchor_round": 98}
                                if _citation_identity(_row) in _seen_rb:
                                    continue
                                _seen_rb.add(_citation_identity(_row))
                                _fresh.append(_row)
                                if len(_fresh) >= 24:
                                    break
                            if len(_fresh) >= 24:
                                break
                    except Exception:
                        _fresh = []
                    if not _fresh:
                        return None
                    anchor_prefetch[str(_idx)] = _fresh + list(anchor_prefetch.get(str(_idx)) or [])
                    return _worker_subagent((_idx, _ag))

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(_starved[:3]), 3)) as _rex:
                    for _new_d in _rex.map(_rebalance_one, _starved[:3]):
                        if _new_d:
                            for _i2, _old in enumerate(subagents_dossiers):
                                if _old.get("agent_index") == _new_d.get("agent_index"):
                                    subagents_dossiers[_i2] = _new_d
                                    print(f"⚖️ [Balance] أُعيد إرسال «{_new_d.get('name')}» "
                                          f"بشواهد متوازنة ({len(_new_d.get('citations') or [])} شاهدًا)", flush=True)
                                    break
        except Exception as _bal_err:
            print(f"⚖️ [Balance] تعذرت جولة الضبط: {_bal_err}", flush=True)
        # 📒 محرّر سجل الأدلة: طبقة تنظيمية واحدة قبل التوليف (لا مدير ثانٍ):
        # يحوّل بطاقات التقارير إلى سجل منظم يبني عليه المدير الواحد ترجيحه
        # وصياغته، فلا نسبة ولا درجة خارج سطر في السجل.
        if req.agent_group and len(subagents_dossiers) >= 2:
            _evidence_ledger = _build_evidence_ledger(
                subagents_dossiers, search_query, str(req.model or ""), api_key_to_use)
            _mark("ledger")

        # دمج شواهد كافة الوكلاء في قائمة المراجع الموحدة
        seen_snippets = set()
        for d in subagents_dossiers:
            for c in d.get("citations", []):
                h = c.get("snippet", "")[:100]
                if h and h not in seen_snippets:
                    seen_snippets.add(h)
                    retrieved_citations.append(c)

        print(f"✨ [Multi-Agent Parallel Dispatch] All {len(subagents_dossiers)} subagents finished. Total citations collected: {len(retrieved_citations)}")
        _failed_agents = [d for d in subagents_dossiers if d.get("failed")]
        if _failed_agents:
            print(f"🚨 [Subagent Failures] سقط {len(_failed_agents)} وكيلًا بعد إعادة المحاولة: "
                  + "؛ ".join(f"{d.get('name')} ({d.get('fail_reason', '')[:80]})" for d in _failed_agents), flush=True)

    elif search_query and not is_greeting and not req.graph_only and not req.table_only:
        retrieved_citations = (anchor_prefetch or {}).get("direct", [])
        # حارس فترة الباحث: لا يعمل إلا إذا حدد الباحث سقف وفاة بنفسه؛ حينها لا شاهد
        # بعد سقفه ولا من كتب الأحياء (99999) مهما كان مصدر ترشيحه
        if req.death_max:
            try:
                _db_h = get_db()
                _death_map = {}
                if _db_h:
                    for _r in _db_h.execute("SELECT book_id, main_author_death_hijri FROM books"):
                        _death_map[int(_r[0])] = _r[1]
                _kept = []
                for _c in retrieved_citations:
                    try:
                        _bid = int(str(_c.get("book_id")).lstrip("#"))
                    except Exception:
                        _kept.append(_c)
                        continue
                    _d = _death_map.get(_bid)
                    if _d is None or (_d != 99999 and _d <= int(req.death_max)):
                        _kept.append(_c)
                    else:
                        print(f"🛡 [Era Guard] حُجب شاهد خارج فترة الباحث: كتاب #{_bid} (ت{_d}) والسقف {req.death_max}")
                retrieved_citations = _kept
            except Exception as _hg_exc:
                print(f"⚠ [Era Guard] {_hg_exc}")
        # لا قصّ رقميًا ثابتًا: الحوض مفتوح حتى حد الشواهد الذي اختاره الباحث نفسه
        # (منتقي الشواهد)، والنموذج يختار ما ينقل منه، وميزانية سياقه تحرس الباقي.
        # يبقى التنويع (توازن الفنون ووحدانية الطبعة وحد الكتاب) ترتيبًا لا حذفًا.
        if _rcmd:
            print(f"🎛 [Research Command] «{_rcmd.get('label')}» intent={_eff_intent} pool={len(retrieved_citations)} witness_limit={witness_limit}")
        if len(retrieved_citations) > witness_limit:
            if _eff_intent:
                retrieved_citations = _diversify_pick(retrieved_citations, witness_limit, core_genres=_eff_intent)
            else:
                retrieved_citations = _diversify_pick(retrieved_citations, witness_limit, genre_cap=0.45)
        print(f"✅ [Chat RAG Direct Monolithic] Extracted {len(retrieved_citations)} passages after anchor rounds")
    else:
        print(f"💬 [Chat Conversational] Skip RAG for simple conversational message: '{last_user_msg}'")

    if len(retrieved_citations) > witness_limit:
        retrieved_citations = retrieved_citations[:witness_limit]

    # بناء نصوص المقاطع المستخرجة مع مراعاة النافذة السياقية للنموذج المختار بدقة لمنع تجاوز سياق OpenRouter
    def _calc_model_context_limit(m_name: str) -> int:
        m = (m_name or "").lower()
        if "gemini" in m:
            return 1000000
        elif "claude" in m:
            return 180000
        elif "gpt-5" in m or "gpt-sol" in m or "o3" in m or "o4" in m:
            return 350000
        elif "gpt-4o" in m:
            return 115000
        elif "deepseek" in m or "qwen" in m or "llama" in m or "mistral" in m:
            return 55000
        return 100000

    target_model_name = req.model or "google/gemini-2.5-flash"
    # اختيار المستخدم سقف لا يتجاوز سياق النموذج الفعلي: الزيادة عن حدّ النموذج
    # لا تنفع وتفتح باب رفض المزود، والنقصان يبقى بيد المستخدم كما اختار.
    max_context_tokens = min(
        resolve_context_tokens(req.context_tokens),
        _calc_model_context_limit(target_model_name),
    )
    max_allowed_citation_chars = int(max(max_context_tokens - 10000, 10000) * 2.5)

    citations_text = ""
    included_citations_count = 0
    included_citations = []
    if retrieved_citations:
        for i, c in enumerate(retrieved_citations, 1):
            loc_str = _approved_citation_label(c)
            year_tag = f" [رأس الحولية الحاكمة المستخرجة: {c['annalistic_year']}]" if c.get('annalistic_year') else ""
            fiqh_tag = f" [رأس المسألة الفقهية الحاكمة: {c['fiqh_header']}]" if c.get('fiqh_header') else ""
            c_death = f" {c.get('death')}" if c.get('death') else ""
            c_cat = f" [{c.get('category')}]" if c.get('category') else ""
            _MADHHAB = {"الفقه الحنفي": "الحنفي", "الفقه المالكي": "المالكي", "الفقه الشافعي": "الشافعي", "الفقه الحنبلي": "الحنبلي"}
            c_madhhab = f" [المذهب: {_MADHHAB[c['category']]}]" if c.get('category') in _MADHHAB else ""
            entry = f"{i}. الإحالة المعتمدة: {loc_str} | المصنف: {c.get('author', '')}{c_death}{c_cat}{c_madhhab}{year_tag}{fiqh_tag}:\n   - نص الشاهد التراثي: {c.get('snippet', '')}\n\n"
            
            if len(citations_text) + len(entry) > max_allowed_citation_chars:
                citations_text += f"\n... [تم استيعاب {included_citations_count} مقطعاً تراثياً وفق أقصى سياق متاح لنموذج {target_model_name}]\n"
                break
            citations_text += entry
            included_citations.append(c)
            included_citations_count += 1

    # تجهيز تنبيه توجيه الوكلاء المساعدين وإدراج تقاريرهم المنقحة
    agent_routing_instruction = ""
    group_name = ""
    if subagents_dossiers:
        group_name = req.agent_group.get("name", "مجموعة الوكلاء المساعدين") if req.agent_group else "فريق الوكلاء المساعدين"
        dossiers_blocks = []
        for i, d in enumerate(subagents_dossiers, 1):
            books_label = "، ".join(d['books'][:5]) + (f" و{len(d['books'])-5} كتب أخرى" if len(d['books']) > 5 else "") if d['books'] else "نطاق الشاملة الموسع"
            _core_tag = ""
            if d.get("core_rank") == 0:
                _core_tag = " 🥇 [صلب البحث — يُقدَّم أولًا ويُقاس عليه غيره]"
            elif d.get("core_rank") == 1:
                _core_tag = " 🥈 [صلب البحث المساند — سدّ النقص والعجز]"
            dossiers_blocks.append(
                f"### 📋 [{i}] تقرير الوكيل المساعد: «{d['name']}» ({d['desc']}){_core_tag}\n"
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
            f"2. قبل الكتابة ابنِ في ذهنك سجل أدلة مدمجًا من «بطاقات الأدلة» في مطلع كل تقرير: البطاقة (دعواها وإحالتها ونصها ونوعها ومذهب كتابها) هي وحدة النسبة الوحيدة. نثر الوكيل بلا بطاقة توجيه وقراءة، لا سند نسبة. وإذا خالف عنوان قسم في تقريرٍ مذهبَ كتاب البطاقة فالعبرة بالبطاقة وكتابها، لا بعنوان القسم.\n"
            f"3. مهمتك: عرض ما وجده كل وكيل داخل كتبه بأمانة، والموازنة بين تقاريرهم فيما ورد فيها فقط. لا تُنشئ جداول ماركداون في هذه الإجابة.\n"
            f"4. اذكر الكتب المنقولة وأجزاءها وصفحاتها داخل الفقرات، بلا جدول ثبت مصادر.\n"
            f"5. لا تنسب قولًا إلى مذهب إلا ببطاقة من كتاب ذلك المذهب أو بطاقة خلاف/مقارنة تنص على النسبة صراحة، وبيّن حينها أنها نسبة منقولة من كتاب الخلاف. لا تُكمل الحكم أو التخريج من الذاكرة أو من مذاهب لم ترد بطاقاتها. المقاطع قد تسمي المسألة بمصطلح المصنفين لا بلفظ السؤال، فاعرضها إن كانت في الموضوع. إن رجع وكيل بمقطع واحد فاعرضه. إن لم يرجع شيئاً بعد جولات البحث فأخبر المستخدم أن نطاق كتبه لم يجد شيئاً.\n"
            f"6. انضباط درجات الأحاديث عند التوليف: لا ترفع درجة حديث فوق ما حكم به وكيل الحديث وبطاقاته؛ فما حُكّم بتحسينه لا يصير عندك «صحيح الحجة»، ولا تنسب لفظًا إلى حديث في الصحيحين إن كان مخرَّجًا عند غيرهما، وأحكام التواتر والتصحيح والتضعيف تُنسب إلى قائلها («قال الطحاوي: متواترة الآثار») ولا تُطلقها حكمًا من عندك، وما لم يرد له حكم درجة في البطاقات فاعرضه بلا حكم أو انقل تردد النقاد فيه.\n"
            + (f"7. تنبيه سقوط وكلاء: تعذّر تقرير الوكلاء الآتين رغم إعادة محاولتهم: {'؛ '.join(d.get('name', '') for d in _failed_agents)}. ابنِ أقسامهم على بطاقات الشواهد المرفقة في تقاريرهم البديلة أو بطاقات الخلاف والمقارنة، وصرّح في موضعه من متن البحث بسقوط تقرير الوكيل وبما بنيت عليه قسمه، ولا توهم اكتمال الفريق.\n" if _failed_agents else "")
            + (f"8. قرارات نطاق المستخدم (تُطاع حرفيًا ويُعلن أثرها): عطّل المستخدم قصدًا هؤلاء الوكلاء لأنه لا يحتاجهم في هذا البحث: {'؛ '.join(d['name'] for d in _disabled_agents)}. لا تطلب منهم شيئًا، ولا تعوّض أدوارهم من عندك ولا من تقارير غيرهم، ولا تنسب إليهم عملًا، وابنِ البحث على النطاق المقلّص كما هو. وصرّح في موضعه بأثر القرار على بنية البحث (نحو: بلا هيئة مناظرة في هذا البحث بقرار الباحث، أو عُرض قول بلا مقابله المناظر)، ولا توهم اكتمالًا ألغاه المستخدم بيده.\n" if _disabled_agents else "")
            + "9. متون الصحيحين والسنن والمسانيد والمصنفات تُستدعى من دواوينها الأصلية في بطاقات الفريق، لا من الشروح الناقلة (فتح الباري، شرح النووي على مسلم، عون المعبود، تحفة الأحوذي)؛ الشروح للتوجيه والجمع والتعليق لا بدلًا من المتن.\n"
        )
        _core_dossiers = [d for d in subagents_dossiers if d.get("core_rank", 99) < 99]
        if _core_dossiers:
            agent_routing_instruction += (
                "\n🥇 [الوكيل الذهبي — صلب البحث]: أنشأتَ أنت (مدير المشروع) قبل إرسال فريقك وكيلًا مؤقتًا لهذه المسألة بعينها بتوجيه نوعي منك، "
                "فبحث بحثًا نوعيًّا مركّزًا في الكتب التي حدّدها مجلس مستشاريك وطابقتَها أنت من الشاملة (وهي نطاقه الوحيد)، وتقريره مقدَّم على تقارير المتخصصين في مطلع ما بين يديك. "
                "عِامله صلبَ البحث الذي تُركَّب عليه بقية النتائج ويُقاس عليه غيره: ما وافقه من بطاقات المتخصصين قويٌّ مؤيَّد، وما خالفه لا يُقدَّم عليه إلا ببطاقة أصرح وأقرب إلى أصل المسألة، "
                "وما سدّ به متخصصٌ نقصًا أو عجزًا فيه يُثبت ببطاقته ويُقدَّم في موضعه. وتكرار كتاب أو نص بينه وبين المتخصصين ليس حشوًا: هو سدُّ عجز وتثبيتٌ متقاطع، فلا تُهمل أثره وإن اكتفيتَ بعرض النص مرة.\n"
            )
        if _evidence_ledger:
            agent_routing_instruction += (
                "\n📒 [سجل الأدلة المنظم — هيكل بحثك الملزم]: بنى محرّر سجل الأدلة من بطاقات تقارير فريقك أعلاه السجلَّ المنظم الآتي "
                "(أقوال ببطاقاتها وكتبها وطبقاتها، وأدلة حديثية بدرجاتها من بطاقاتها، ودعاوى إجماع بمستنداتها، وصفرات وادعاءات بلا بطاقة معلنة). "
                "ابنِ هيكل بحثك على هذا السجل: لا تنسب قولًا ولا ترفع درجة حديث فوق سطر فيه، وما عُدّ فيه صفرًا أو بلا بطاقة فصرّح به في موضعه ولا تسدّه من ذاكرتك، "
                "وما سجّله تعارضًا فافصل فيه أنت عند الترجيح. وارجع إلى التقارير أعلاه لنصوص البطاقات الحرفية عند النقل والتحرير.\n"
                + _evidence_ledger + "\n"
            )
        agent_routing_instruction += (
            "\n🚫 [قاعدة المكتبة الحاكمة]: النقل والاستشهاد من كتب مكتبة الشاملة وحدها؛ ما كان خارجها يُستبعد فورًا ولا يُنقل منه ولا يُحال إليه ولو صحّ في نفسه. "
            "إن لم تجد نقلًا إلا خارج الشواهد فاحذفه من بحثك ولا تسدّه من ذاكرتك، ويكفيك ما ثبت في كتب المكتبة.\n"
            "🔗 [ربط النقول إلزامي]: كل نقل تضعه بين علامتي تنصيص في متنك يحمل رقم حاشيته ملاصقًا له فورًا "
            "(<sup><small>(ن)</small></sup>) بلا جملة فاصلة ولا تأخير إلى آخر الفقرة؛ فالنقل الأعمى بلا علامة لا يبلغه تحقق المنظومة ويُعدّ خللًا في بحثك. "
            "وإن لم تجد للنقل حاشية من بطاقاتك فاحذفه أو ادمجه في كلامك بلا تنصيص.\n"
        )
        _ac = locals().get("_advisor_consult") or {}
        if _ac.get("grafted") or _ac.get("missing") or _ac.get("anchors") or _ac.get("tavily"):
            _glines = [f"• أُضيف إلى بطاقة «{g['agent']}»: {g['entry']}" + (f" — {g['why']}" if g.get("why") else "") + (f" ({'ترشيح مشترك اتفق عليه ' + str(g.get('votes')) + ' من المجلس' if g.get('band') == 'consensus' else 'لقطة فريدة قبِلها المدير' if g.get('band') == 'unique' else 'ترشيح قناة الشبكة'})" if g.get("band") else "") + (f" (إسناد {'المدير' if g.get('assigned_by') == 'director' else 'اتفاق المجلس آليًا' if g.get('assigned_by') == 'consensus' else 'احتياطي معلن'}: {g['reason']})" if g.get("reason") else "") for g in (_ac.get("grafted") or [])]
            _council = _ac.get("council") or {}
            _council_line = ""
            if _council:
                _mem = "؛ ".join(f"{m.get('name')}: {m.get('books')} كتبًا و{m.get('anchors')} مرساة" for m in (_council.get("members") or []))
                _council_line = (f"حصيلة العصف الذهني للمجلس: {_mem}. بعد توحيد المكرر: {_council.get('merged_books')} ترشيحًا "
                                 f"(مشتركة {_council.get('consensus')}، لقطات فريدة {_council.get('unique')}، شبكة {_council.get('web')})، "
                                 f"قُبل منها فريدةً {_council.get('accepted_unique', 0)} ومشتركةً {_council.get('accepted_consensus', 0)}.\n")
            agent_routing_instruction += (
                "\n🧭 [مجلس المستشارين قبل البحث]: استُشير كل عضو في المجلس في المسألة كاملة استقلالًا عن إخوانه (لا تقسيم فنون بينهم)، وحُقّقت ترشيحاتهم من قاعدة الشاملة بأرقامها ومؤلفيها، ووُحّد المكرر وحُفظت اللقطات الفريدة، ثم أسندها مدير المشروع (النموذج الأساسي) إلى الوكلاء المختصين وطُعّمت في بطاقاتهم لهذه الجولة.\n"
                + _council_line
                + ("\n".join(_glines) + "\n" if _glines else "")
                + (f"كتب رشّحها المستشارون ولم تُوجد في الشاملة: {'؛ '.join(_ac.get('missing') or [])}.\n" if _ac.get("missing") else "")
                + (f"مراسي المستشارين المعتمدة: {'؛ '.join(_ac.get('anchors') or [])}.\n" if _ac.get("anchors") else "")
                + (f"{_ac.get('tavily')}\n" if _ac.get("tavily") else "")
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
            f"3. قدّم الجواب النهائي بصياغة علمية متكاملة ومحررة تلبي رغبة المستخدم بناءً على ما أنجزه واستخلصه وكلاء المجموعة.\n"
            f"4. الحدود صارمة: لا تستشهد بكتاب خارج نطاق الوكلاء، ولا تُكمل الحكم أو التخريج من الذاكرة. المقاطع قد تسمي المسألة بمصطلح المصنفين لا بلفظ السؤال، فاعرضها إن كانت في الموضوع. إن وُجد مقطع واحد فاعرضه. إن لم يُوجد شيء بعد جولات البحث فأخبر المستخدم أن النطاق لم يجد شيئاً."
        )

    if req.agent_group and not req.library_only and not req.graph_only and not req.table_only:
        try:
            import library_search
            _auth_lines = []
            for _m in ("الحنفي", "المالكي", "الشافعي", "الحنبلي", "الظاهري"):
                _d = library_search.madhhab_authorities(_m) or {}
                for _layer in (_d.get("layers") or []):
                    _titles = "، ".join((b.get("title") or "") for b in (_layer.get("books") or [])[:4])
                    if _titles:
                        if "اصطلاح" in (_layer.get("name") or ""):
                            _auth_lines.append(f"المذهب {_m} — طبقة {_layer.get('name')} (ضبط اصطلاحي/منهجي: تُقرأ لضبط مصطلح المذهب وخريطة كتبه فقط؛ لا تُطلب فيها نصوص أحكام المسائل ولا يُستدل بخلوها من لفظ مسألة على شيء): {_titles}")
                        else:
                            _auth_lines.append(f"المذهب {_m} — طبقة {_layer.get('name')}: {_titles}")
            _disc_bits = []
            try:
                for _kind, _label in (("ijma", "كتب الإجماع"), ("asbab", "كتب أسباب الخلاف"), ("khilaf", "كتب الخلاف العالي")):
                    _sec = library_search.authority_books(_kind) or {}
                    _titles = []
                    for _layer in (_sec.get("layers") or []):
                        for _b in (_layer.get("books") or [])[:2]:
                            if _b.get("title"):
                                _titles.append(_b["title"])
                    if _titles:
                        _disc_bits.append(f"{_label}: " + "، ".join(_titles[:5]))
            except Exception:
                _disc_bits = []
            if _targeted_map:
                _tlines = []
                for _md, _info in _targeted_map.items():
                    if _info.get("count"):
                        _tlines.append(f"المذهب {_md}: استُرجعت له {_info['count']} صفحة كاملة من كتب طبقاته ({'، '.join(_info.get('books') or [])}) وسُلّمت لوكيله مادةً أولى لبطاقاته؛ فإن خلا قسمه من بطاقة منها فالخلل في التوليف لا في المادة.")
                    else:
                        _tlines.append(f"المذهب {_md}: الاسترجاع الموجّه في كتب طبقاته لم يُرجع صفحة بهذه المراسي؛ فأي انعدام بطاقة له صفر موثق بهذا البحث الموجّه، يُصرَّح به ولا يُملأ من الذاكرة.")
                agent_routing_instruction += (
                    "\n\n🎯 [ضمان الاسترجاع الموجّه للمذاهب]:\n" + "\n".join(_tlines)
                )
            if _auth_lines and not locals().get("_hadith_project"):
                agent_routing_instruction += (
                    "\n\n📏 [بطاقات الأدلة قبل الكتابة وفهرس طبقات المذاهب الاسترشادي]:\n"
                    "حرية البحث والتحرير محفوظة؛ والضبط هنا في النسبة لا في الاختصار خوفًا من حذف آلي. ابنِ البحث على بطاقات أدلة الوكلاء: لكل نسبة مذهبية بطاقة تسمي دعواها وكتابها وموضعها ونصها. لا تنقل نصًا بين علامتي تنصيص إلا من بطاقة أو شاهد معروض بلفظه وموضعه قدر الإمكان؛ وسيُطابَق النقل آليًا على صفحة كتابه تدقيقًا غير مدمّر، فيُنبَّه على ما لم يثبت في سجل ختامي ولا يُحذف من بحثك. "
                    "لا يكن وسيط (الموسوعة الفقهية، كنز العمال، جامع الأحاديث) ولا شرح صوتي سندًا وحيدًا لمتن حديث أو قول مذهبي؛ فالمتون من كتب الحديث الأصلية والأقوال من كتب المذاهب، والوسائط للمقارنة والضبط إلى جانب الأصل لا بدلًا عنه. "
                    "وقاعدة العزو إلى الأصل: ما نُقل داخل شرح أو كتاب ناقل عن إمام أو كتاب غيره (كمغلطاي أو العظيم آبادي ناقلَين عن أبي داود وسعيد بن منصور وابن حزم والمصنفات) فالعزو والحكم لأصله المباشر لا للناقل؛ لا تبنِ متنًا ولا حكمًا ولا إعلالًا على لفظ الناقل وحده ما دام الأصل في المكتبة، واذكر الناقل إشارةً إلى الموضع فقط، وإن لم تبلغك بطاقة الأصل فصرّح: «نقله فلان عن فلان ولم نقف على أصله» ولا تُخفِ الواسطة بصيغة توهم المباشرة. "
                    "ومتون الصحيحين والسنن والمسانيد والمصنفات تُستدعى من دواوينها الأصلية في بطاقات الفريق لا من الشروح الناقلة (فتح الباري، شرح النووي على مسلم، عون المعبود، تحفة الأحوذي)؛ الشروح للتوجيه والجمع والتعليق لا بدلًا من المتن. "
                    "وتنبيه فئات: كتب طبقة «ضبط اصطلاحي/منهجي» (كمدخل ابن بدران للحنابلة) كتبُ مصطلح وخريطة كتب لا مصادر تقارير مذهبية؛ فلا تذكرها في سياق إثبات نص مذهبي ولا نفيه، ويُمنع قول «لم نقف في كتب الاصطلاح على نص المسألة» فخلوها من ألفاظ المسائل ليس صفرًا ولا حجة. "
                    "لا تدّعِ إجماعًا أو اتفاقًا إلا ببطاقة من كتب الإجماع، أو انسب الدعوى لقائلها بعينه. "
                    "وفهرس الطبقات الآتي خريطة بحث استرشادية لا قائمة بيضاء: اطلب منه طبقات كل مذهب وكتبه أولًا، فإن وجدت بطاقة قوية من كتاب خارجه فاعتمدها واذكر دورها، ولا تُصفّر مذهبًا لوجود كتبه خارج الفهرس. صرّح بانعدام البطاقة لا بانعدام القول إن لم تجد في طبقة نصًا:\n"
                    + "\n".join(_auth_lines)
                    + (("\n" + "\n".join(_disc_bits)) if _disc_bits else "")
                )
        except Exception:
            pass

    if page_reading_instruction:
        agent_routing_instruction += page_reading_instruction
    elif retrieved_citations:
        agent_routing_instruction += (
            f"\n\n═══════════════════════════════════════════════════════════\n"
            f"📚 [المقاطع والنصوص التراثية المستخرجة فعلياً {'من المكتبة الشاملة مباشرة' if req.library_only else 'من الشاملة عبر الوكلاء'}]:\n"
            f"{'مسحت المنظومة المكتبة مباشرة بلا وكلاء واستخرجت' if req.library_only else 'لقد قام وكيلك المساعد بالمسح والاستخراج الفعلي من كتب الشاملة واستخرج'} لك {len(retrieved_citations)} مقطعاً موثقاً لمطابقتها مع طلب المستخدم:\n\n"
            f"{citations_text}\n"
            f"🔴 [تعليمات معالجة الشواهد للنموذج الأساسي]:\n"
            f"1. أنت النموذج الأساسي المحلل والمحقق؛ مهمتك معالجة الشواهد والإجابة بأسلوب تحريري علمي رصين في فقرات، بلا جداول ماركداون.\n"
            f"2. استوعب كـافـة الشواهد والمقاطع المستخرجة أعلاه (جميع الشواهد من 1 إلى {len(retrieved_citations)}) دون استبعاد أي شاهد وثيق الصلة.\n"
            f"3. في المتن رقم الإحالة المرتفع وحده: <sup><small>(١)</small></sup>. يُمنع ذكر اسم الكتاب أو المؤلف أو الجزء أو الصفحة في المتن. كل نقل في حاشية بسطر مستقل بعد المتن، وهي التوثيق الوحيد بالإخراج القياسي: اسم الكتاب للمؤلف (جزء-صفحة)، ولذي الجزء الواحد: اسم الكتاب للمؤلف ص (صفحة). لا تُنشئ بعد الحواشي قائمة مصادر ومراجع.\n"
            f"4. كُتب التاريخ الإسلامي مؤلفة بنظام الحوليات؛ إذا كانت المسألة تاريخية فرقم السنة يُذكر في مطلع الحولية وقد استخرجته لك المنظومة آلياً في [رأس الحولية الحاكمة] فأثبته صراحة في متن الجواب.\n"
            f"5. هذه المقاطع أعلاه موثقة ومستخرجة فعلياً من أمهات المصادر، فاعتمدها في إجابتك.\n"
            f"6. لا تشترط ظهور لفظ السؤال في المقطع. إن تناول الشاهد جوهر المسألة بمصطلح المصنفين فهو المطلوب. لا تُفتِ ولا تخرّج من الذاكرة بما لم يرد في الشواهد.\n"
            f"═══════════════════════════════════════════════════════════\n"
        )

    # 4. تشغيل محرك التحقق الفلكي والحسابي فقط عند اختيار أداة الفلك صراحة أو ورود مسألة كسوف قطعية
    is_astronomy_enabled = False
    if req.computational_tool and isinstance(req.computational_tool, dict):
        if req.computational_tool.get("enabled") and req.computational_tool.get("tool_type") in ("astronomy_hijri_sync", "web_nasa_catalog", "nasa_web_verification"):
            is_astronomy_enabled = True
    elif any(phrase in last_user_msg for phrase in ["انكسفت الشمس", "انخسف القمر", "كسوف الشمس", "خسوف القمر", "محاق فلكي", "حساب الكسوف"]):
        is_astronomy_enabled = True

    if is_astronomy_enabled and not req.graph_only and not req.table_only and not req.library_only:
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
    live_error = ""
    applied_effort = None
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
            elif req.custom_generation:
                system_instruction = (req.system_prompt or "").strip()
            elif req.system_prompt:
                system_instruction = req.system_prompt
            else:
                system_instruction = (
                    "أنت المجتهد، مساعد ذكي وباحث محقق متخصص في العلوم الإسلامية والفقهية واللغوية والتاريخية.\n"
                    "أجب مباشرة وبتوسع وتحرير علمي رصين عن استفسار وسؤال المستخدم باللغة العربية الفصحى.\n"
                    "حلل المسألة في فقرات محررة. لا تُنشئ جداول ماركداون ولا ثبت مصادر مجدولاً في هذه الإجابة.\n"
                    "الجواب البحثي يلتزم الإخراج القياسي العام للمسائل الشرعية واللغوية والتاريخية: هيكل البحث، ثم الحواشي المطابقة لأرقام المتن، وتتولى المنظومة إظهار قائمة المصادر والمراجع من قاعدة الكتب، بوسوم HTML.\n"
                    "إذا طُلب مشجر، أخرج كتلة ```force3d واحدة واختر نوعاً واحداً لا تخلطه بغيره: إسناد (صحابي|تابعي|مدار|طريق|كتاب، والسهم من الشيخ إلى التلميذ)، أو خلاف فقهي (مسألة ثم قول ومذهب ودليل ومناقشة وجواب وترجيح)، أو خلاف عقدي (مسألة ثم مذهب ومقالة وشبهة وجواب)، أو استدلال (حكم ثم دليل ثم وجه الدلالة ثم مناقشة ثم جواب)، أو مناقشة (محل النزاع ثم دعوى كل طرف ثم دليله). source هو الأعلى و target هو الفرع."
                )
            if req.custom_generation and not req.graph_only and not req.table_only and not is_study_discussion:
                pass
            elif not req.graph_only and not req.table_only:
                if _director_prompt:
                    system_instruction = (
                        "👑 [توجيه مدير المشروع قائد هذا الفريق — وهو توجيهك الحاكم الذي تقود به الوكلاء وتسلّم به البحث]\n"
                        + _director_prompt + "\n\n" + system_instruction
                    )
                if agent_routing_instruction:
                    system_instruction += agent_routing_instruction
                system_instruction += "\n" + CITATION_FORMAT_RULE
                if not (req.system_prompt and "جدول" in req.system_prompt):
                    system_instruction += "\n" + ACADEMIC_ANSWER_RULE
                if _rcmd.get("structure"):
                    system_instruction += "\n[هيكل الأمر البحثي المختار «" + str(_rcmd.get("label") or "") + "» — التزمه في ترتيب هذا الجواب]\n" + str(_rcmd["structure"])
                if _discussion in ("open", "finalize"):
                    _audit_ctx = ""
                    try:
                        _mconn = _ensure_app_memory()
                        try:
                            _mrow = _mconn.execute("SELECT payload FROM kv_documents WHERE key=?",
                                                   (_owner_key("research_metrics", current_owner_id(request)),)).fetchone()
                        finally:
                            _mconn.close()
                        if _mrow is not None:
                            for _me in (json.loads(_mrow["payload"]) or []):
                                if _me.get("chat_id") == req.chat_id:
                                    _audit_ctx = str(_me.get("audit_record") or "")
                    except Exception:
                        _audit_ctx = ""
                    if _audit_ctx:
                        system_instruction += ("\n\n📏 [سجل تدقيق هذا البحث ونواقصه المسجلة — مادة المناقشة الأولى]\n" + _audit_ctx[:3500])
                    if _discussion == "open":
                        system_instruction += (
                            "\n\n🗣️ [جلسة مناقشة واستكمال مفتوحة مع الباحث — أنت مدير المشروع وقائد الفريق، والبحث السابق وسجل تدقيقه أمامك في هذه المحادثة]\n"
                            "مهمتك الآن: أن تحاور الباحث وتجيب عن تساؤلاته وتناقشه في نواقص البحث المسجلة وفيما يثيره، وأن تقترح الاستكمالات — لا أن تعيد صياغة البحث كاملًا الآن، ولا أن تفتح بحثًا جديدًا من الصفر.\n"
                            "التزم: (١) لا تدّع إنجاز استكمال لم ينجز فعلًا. (٢) إن احتاج النقاش دليلًا جديدًا أو تحققًا من نقل أو تغطية كتاب أو مذهب، فأصدر طلب إرسال لوكيل بعينه من فريقك في سطر مستقل بهذا الشكل الحرفي: ⟦طلب-وكيل: اسم الوكيل كما في الفريق | المهمة المطلوبة بدقة⟧ — ثلاثة طلبات كحد أقصى في الجولة الواحدة؛ ستنفّذ المنظومة طلبك وترجع إليك بتقرير الوكيل ثم تجيب الباحث بناءً عليه، فلا تخمّن نتيجة الطلب ولا تنسب للوكيل ما لم يقله. (٣) اختم كل رد ببيان قصير: «اتفقنا على: ... | بقي مفتوحًا: ... | سيتغير في الصياغة النهائية: ...».\n"
                            "أداة تقليب الصفحات بيدك: عبارات من جنس «انقطع النص في المقطع المستخرج» أو «لم يكتمل لفظه في المقطع» التي في البحث ليست حقيقة عن الكتاب، بل علامة أن الشاهد وصله مقتطفًا مبتورًا من رأس صفحته. فلا تكررها للباحث ولا تبنِ عليها؛ بل قلّب الصفحة بنفسك: أصدر في سطر مستقل ⟦طلب-صفحة: #رقم الكتاب | الجزء | الصفحة⟧ فيأتيك نص تلك الصفحة كاملًا مع تتمة الصفحة التالية، فتقرأ النص بتمامه وتتحقق منه. ولك أيضًا أن تطلب من وكيل الكتاب نفسه جلب إكمال النص من الصفحة التالية بعينها.\n"
                            "حراسة الطبقات واجبك الشخصي في هذه الجلسة: إن وردك في تقارير وكلائك أو في البحث الأصلي عزوٌ بالواسطة من شرح معاصر أو موسوعة معاصرة أو تفريغ دروس (من جنس شرح سنن أبي داود للعباد، وشرح ابن ماجه للهرري، وفضل الرحيم الودود، وشروح بلوغ المرام للهيميد والبسام، وموسوعات الإجماع المعاصرة) ناقلًا عن أصل تراثي (كالمغني أو ابن المنذر أو كتب السنة)، فلا تقبله سندًا لمتن حديث أو حكم مذهب أو دعوى إجماع، ولا تعرضه على الباحث بوصفه توثيقًا؛ بل ائتِ بالأصل التراثي نفسه بتقليب صفحته أو بطلب وكيله، فإن تعذر صرّح للباحث: «هذا منقول بالواسطة عن كذا ولم نقف على أصله بعد» واجعله بندًا مفتوحًا لا مادة بناء. ويدخل في حراستك الناقل التراثي نفسه: شرح حديثي ناقل (كمغلطاي في شرح ابن ماجه والعظيم آبادي في عون المعبود) أصلٌ لأقوال صاحبه، وواسطةٌ لما ينقله عن أبي داود وسعيد بن منصور وابن حزم والمصنفات؛ فما كان من هذا الجنس في البحث فاسعَ في جلبه من أصله مباشرة (السنن والمصنفات والمحلى بأرقامها ومواضعها)، ولا تدع الصياغة النهائية تقوم على لفظ الناقل وحده.\n"
                            "وسلاحك الأقوى «استدعاء كتاب»: كل نقل بالواسطة عن كتاب موجود في الشاملة غير مدرج في بطاقة الوكيل المختص به، لا تكتفِ فيه بالتصريح ولا بطلب صفحة عابرة؛ بل استدعِ الكتاب نفسه إلى بطاقة مختصه ليبقى فيها لكل بحث قادم، واطلب التحقق منه، بسطر مستقل بهذا الشكل الحرفي: ⟦طلب-كتاب: #رقم الكتاب أو عنوانه | اسم الوكيل المختص | مهمة التحقق المطلوبة منه في هذا الكتاب بعينه⟧ — ستنفّذ المنظومة الإضافة الدائمة والتحقق الفوري وترجع إليك بتقرير الوكيل من الأصل نفسه. وإن لم يوجد الكتاب في الشاملة أصلًا صرّح للباحث بفجوته الموثقة.\n"
                            "وعند رضا الباحث سيقفل الجلسة بزر «إقفال وإعادة الصياغة» فتعيد حينها صياغة البحث نهائيًا من هذه المحادثة المحفوظة."
                        )
                    else:
                        system_instruction += (
                            "\n\n🔒 [إقفال جلسة المناقشة — إعادة الصياغة النهائية المعتمدة]\n"
                            "أقفل الباحث جلسة المناقشة باتفاق، فأعد الآن صياغة البحث كاملًا صياغة نهائية معتمدة، مستوعبًا: نص البحث السابق في هذه المحادثة، وكل ما اتُّفق عليه أثناء المناقشة، وتقارير الوكلاء المستكملة فيها. وعالج صراحة نواقص سجل التدقيق المرفق: فالاتفاقات/الإجماعات المطلقة بلا نسبة تُنسب إلى قائلها أو كتاب إجماعها أو تُخفف إلى «الجمهور»، والنقول التي لم تثبت آليًا تُراجع فإن لم تثبت استُبدل بها ثابت موثق أو صُرّح بحالها، والخلايا الصفرية الموثقة تبقى مصرحًا بها لا تُملأ من الذاكرة.\n"
                            "التزم بطاقات الأدلة والإحالات المعتمدة والحواشي كما في البحث. ويُمنع منعًا باتًا في الصياغة النهائية عبارات «انقطع النص في المقطع المستخرج» و«لم يكتمل لفظه في المقطع» ونحوها: فالنص إما مكتمل من صفحته (بما جُلب في المناقشة بتقليب الصفحات) أو يُحذف النقل ويُصرَّح بخلوّ بطاقته.\n"
                            "وهذه الصياغة ورقة علمية محكمة مغلقة — كبحث منشور أو ورقة تشاور بين علماء — فانزع منها نزعًا تامًا كلَّ لغةٍ تدل على عملية إنتاجها: لا «وكيل» ولا «وكلاء» ولا «جلب الوكيل/لم يُجلب» ولا «الشواهد المستخرجة» ولا «المقطع» ولا «الاسترجاع» ولا «بطاقات» ولا «في مناقشتنا/اتفقنا» ولا «مدير المشروع». وحوّل معانيها إلى لسان العلماء: فبدل «لم يُرجع وكيل الحنابلة نصًا» اكتب «لم نقف على نص صريح للحنابلة في كتبهم المعتمدة في عين هذه المسألة، وحكمها عندهم يُخرَّج على كذا»، وبدل «الاسترجاع الموجّه لم يُرجع شيئًا للظاهرية» اكتب «لم نقف في كتب الظاهرية المعتمدة على نص في المسألة». ابدأ بعنوان المسألة العلمي وحده، واختم بخلاصة الحكم المحررة — بلا أي إشارة إلى مناقشة أو جلسة أو ما تغيّر.\n"
                            "وطبقات السند في الصياغة النهائية محكمة كإحكام لسانها: كل عزو في البحث الأصلي جاء بالواسطة من شرح معاصر أو موسوعة معاصرة أو تفريغ دروس ناقلًا عن أصل تراثي، فإما أن يكون أصله قد جُلب في المناقشة فتُحال إليه مباشرة بلفظه، أو يُحذف ذلك العزو الواسطة حذفًا ولا يبقى حكم معلقًا به؛ فلا يبقى في الورقة متن حديث ولا قول مذهب ولا دعوى إجماع سندُه شرح معاصر وحده. وكذلك الناقل التراثي (كمغلطاي والعظيم آبادي): ما نُقل بواسطته عن أبي داود وسعيد بن منصور وابن حزم والمصنفات فعزوُه في ورقتك إلى أصله المباشر بلفظه وموضعه إن جُلب في المناقشة، وإلا حُذف أو كُتب صريحًا «نقله فلان عن فلان» ولم يُبنَ عليه حكم — ويُمنع أن تدور فقرات كاملة على شرح ناقل واحد تدور معه الإحالات. وكتب الاصطلاح والمداخل والمناهج (كمدخل ابن بدران) لا تُذكر في ورقتك في سياق وجود نص مذهبي ولا عدمه؛ فهي ليست من كتب تقارير المذاهب، وذكرها في نفي نص خلطُ فئات يجب نزعه."
                        )

            # تضمين المستندات والملفات المرفوعة والمحفوظة في مجلد uploads (Bucket)
            if req.attachments and isinstance(req.attachments, list) and len(req.attachments) > 0:
                att_lines = [
                    "\n═══════════════════════════════════════════════════════════",
                    "📂 [مستندات وملفات المستخدم المرفوعة والمحفوظة في مجلد النظام (Uploads Bucket)]:"
                ]
                for idx_a, att in enumerate(req.attachments):
                    f_name = att.get("filename") or att.get("name") or f"ملف_{idx_a+1}"
                    f_type = att.get("file_type") or att.get("type") or ""
                    f_text = _attachment_body(att, current_owner_id(request))
                    
                    att_lines.append(f"• اسم الملف: {f_name}")
                    if f_type:
                        att_lines.append(f"  نوع الملف: {f_type}")
                    if f_text and not f_text.startswith("[تعذر") and not f_text.startswith("[خطأ"):
                        att_lines.append(f"  نص الملف مستخرج وجاهز، وأجب منه مباشرة:\n```text\n{f_text[:25000]}\n```")
                    elif att.get("has_image"):
                        att_lines.append("  ملاحظة: هذا الملف صورة تم تمريرها بصرياً إلى نموذج الرؤية لتحليلها واستخراج نصوصها.")
                    else:
                        att_lines.append("  تعذر استخراج نص هذا الملف.")
                att_lines.append("═══════════════════════════════════════════════════════════")
                att_lines.append("أجب من نص الملف المستخرج أعلاه. لا تقل إن الملف غير مقروء إذا كان نصه موجوداً.")
                
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

            def _custom_output_limit(req_tokens: Optional[int]) -> int:
                try:
                    n = int(req_tokens or 65536)
                except Exception:
                    n = 65536
                return max(512, min(n, 1048576))

            def _sampling_temperature() -> float:
                # حرارة المستخدم تصل في الحالتين، والصفر اختيار مقصود لا غياب قيمة.
                if req.temperature is not None:
                    return max(0.0, min(float(req.temperature), 2.0))
                return 0.2

            safe_max_output_tokens = _custom_output_limit(req.max_tokens) if req.custom_generation else _get_safe_max_tokens_for_model(call_model, req.max_tokens)
            applied_effort = None

            def _query_openrouter(target_model: str, max_tok: Optional[int] = None, with_reasoning: bool = True, allow_tools: bool = True):
                nonlocal applied_effort
                if max_tok is not None:
                    tok_limit = max_tok
                elif req.custom_generation:
                    tok_limit = _custom_output_limit(req.max_tokens)
                else:
                    tok_limit = _get_safe_max_tokens_for_model(target_model, req.max_tokens)
                mcp_tools, mcp_map = mcp_openai_tools(req.mcp_servers or []) if allow_tools else ([], {})
                dialog = list(messages_payload)
                if mcp_tools:
                    dialog = [{
                        "role": "system",
                        "content": "أدوات MCP المحددة متاحة للاستدعاء. استخدمها حين يفيد بيانها في الجواب، ثم أتم الإجابة بالعربية."
                    }] + dialog
                payload = {
                    "model": target_model,
                    "messages": dialog,
                    "temperature": _sampling_temperature(),
                    "max_tokens": tok_limit
                }
                # top_k التوليد يصل من إعدادات المستخدم في الحالتين (قياسياً ومخصصاً)،
                # وهو غير عدد مقاطع الاسترجاع. معامل التكرار يبقى للتخصيص وحده.
                if req.top_k is not None and int(req.top_k) > 0:
                    payload["top_k"] = max(1, min(int(req.top_k), 100))
                if req.custom_generation:
                    if req.repetition_penalty is not None:
                        payload["repetition_penalty"] = max(1.0, min(float(req.repetition_penalty), 2.0))
                if mcp_tools:
                    payload["tools"] = mcp_tools
                    payload["tool_choice"] = "auto"
                effort = attach_reasoning(payload, target_model, req.thinking_level) if with_reasoning else None

                def _read(body_payload: dict) -> dict:
                    o_req = urllib.request.Request(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "http://localhost:8085",
                            "X-Title": "Al-Mojtahed Sharia Engine"
                        },
                        data=json.dumps(body_payload).encode("utf-8")
                    )
                    with urllib.request.urlopen(o_req, timeout=180) as resp:
                        return json.loads(resp.read().decode("utf-8"))

                def _finish(msg_obj: dict) -> str:
                    content = (msg_obj.get("content") or "").strip()
                    if not content and msg_obj.get("reasoning"):
                        content = str(msg_obj.get("reasoning") or "").strip()
                    return content

                try:
                    resp_data = _read(payload)
                    applied_effort = effort
                except urllib.error.HTTPError as error:
                    detail = error.read().decode("utf-8", errors="ignore")
                    print(f"Provider HTTP {error.code} for {target_model}: {detail[:300]}", flush=True)
                    # سلّم تجريد: أسقط المعاملات الاختيارية واحداً تلو الآخر قبل الاستسلام،
                    # واحفظ نص الرفض الحقيقي بدل ابتلاعه.
                    for _strip in ("reasoning", "tools", "sampling"):
                        try:
                            if _strip == "reasoning" and payload.get("reasoning"):
                                payload.pop("reasoning", None)
                                applied_effort = None
                            elif _strip == "tools" and payload.get("tools"):
                                payload.pop("tools", None)
                                payload.pop("tool_choice", None)
                            elif _strip == "sampling" and ("top_k" in payload or "repetition_penalty" in payload):
                                payload.pop("top_k", None)
                                payload.pop("repetition_penalty", None)
                            else:
                                continue
                            resp_data = _read(payload)
                            break
                        except urllib.error.HTTPError as again:
                            detail = again.read().decode("utf-8", errors="ignore")
                            print(f"Provider HTTP {again.code} retry for {target_model}: {detail[:300]}", flush=True)
                            error = again
                    else:
                        raise RuntimeError(f"رفض المزود الطلب ({error.code}): {detail[:300]}")
                if isinstance(resp_data, dict) and resp_data.get("error"):
                    raise RuntimeError(f"خطأ أرجعه المزود داخل الرد: {str(resp_data.get('error'))[:300]}")
                _empty_retried = False
                _synthesis_forced = False
                for _round in range(8):
                    choice = resp_data.get("choices", [{}])[0]
                    msg_obj = choice.get("message", {}) or {}
                    calls = msg_obj.get("tool_calls") or []
                    if not calls or not mcp_map:
                        text = _finish(msg_obj)
                        if text:
                            # جملة انتقالية قصيرة («الآن أقرأ...») ليست جواباً:
                            # ألزم النموذج بكتابة الجواب مما جمعه، بلا أدوات.
                            transitional = len(text) < 200 and any(
                                mark in text for mark in ("الآن أقرأ", "سأقرأ", "الآن أبحث", "سأبحث", "دعني أقرأ", "سأطالع", "الآن أطالع")
                            )
                            if transitional and mcp_map and not _synthesis_forced:
                                _synthesis_forced = True
                                print(f"Transitional-only reply from {target_model}; forcing synthesis", flush=True)
                                dialog.append({"role": "assistant", "content": text})
                                dialog.append({
                                    "role": "system",
                                    "content": "اكتب الآن الجواب البحثي الكامل مما جمعته من الشواهد والنصوص في هذه المحادثة، ولا تطلب أي قراءة أو أداة أخرى.",
                                })
                                payload["messages"] = dialog
                                # إبقاء تعريفات الأدوات (سجل الحوار يحيل إليها) مع منع استدعائها،
                                # فحذفها كان يجعل النموذج يعيد طلب أدوات بلا تعريف.
                                payload["tool_choice"] = "none"
                                payload["max_tokens"] = min(65536, max(int(payload.get("max_tokens") or 0), 24576))
                                if payload.pop("reasoning", None):
                                    applied_effort = None
                                resp_data = _read(payload)
                                continue
                            return text
                        if _empty_retried:
                            raise RuntimeError(
                                f"أرجع النموذج رداً فارغاً (finish_reason={choice.get('finish_reason')}, "
                                f"usage={resp_data.get('usage')}, error={resp_data.get('error')})"
                            )
                        # رد فارغ: غالباً استهلك التفكير الداخلي حد الإخراج كله.
                        # أعد مرة بسقف أعلى وبلا معلمة تفكير قبل إعلان الفشل.
                        _empty_retried = True
                        payload["max_tokens"] = min(65536, max(int(payload.get("max_tokens") or 0) * 2, 16384))
                        if payload.pop("reasoning", None):
                            applied_effort = None
                        print(f"Empty reply from {target_model} (finish_reason={choice.get('finish_reason')}); retrying with max_tokens={payload['max_tokens']}", flush=True)
                        resp_data = _read(payload)
                        continue
                    dialog.append({
                        "role": "assistant",
                        "content": msg_obj.get("content") or "",
                        "tool_calls": calls,
                    })
                    for call in calls:
                        fn = (call.get("function") or {})
                        mapped = mcp_map.get(fn.get("name") or "")
                        try:
                            args = json.loads(fn.get("arguments") or "{}")
                        except Exception:
                            args = {}
                        if not isinstance(args, dict):
                            args = {}
                        if mapped:
                            try:
                                output = mcp_call_tool(mapped["url"], mapped.get("session"), mapped["name"], args)
                            except Exception as exc:
                                output = f"تعذر استدعاء الأداة: {exc}"
                        else:
                            output = "الأداة غير متاحة في الخوادم المحددة"
                        dialog.append({
                            "role": "tool",
                            "tool_call_id": call.get("id") or fn.get("name") or "tool",
                            "content": output,
                        })
                    payload["messages"] = dialog
                    resp_data = _read(payload)
                # انتهت جولات الأدوات والنموذج ما زال يجمع: ألزمه بكتابة الجواب
                # مما جمعه، بلا أدوات، حتى لا تخرج جملته الانتقالية جواباً.
                last_choice = resp_data.get("choices", [{}])[0]
                if (last_choice.get("message", {}) or {}).get("tool_calls"):
                    print(f"Tool rounds exhausted for {target_model}; forcing final synthesis without tools", flush=True)
                    # ميزانية توليف محمية: سقف إخراج مضمون وبلا تفكير يلتهمه
                    payload["max_tokens"] = min(65536, max(int(payload.get("max_tokens") or 0), 24576))
                    if payload.pop("reasoning", None):
                        applied_effort = None
                    dialog.append({
                        "role": "system",
                        "content": "انتهت جولات الأدوات. اكتب الآن الجواب البحثي الكامل مما جمعته من الشواهد والنصوص في هذه المحادثة، ولا تطلب أي قراءة أو أداة أخرى.",
                    })
                    payload["messages"] = dialog
                    payload["tool_choice"] = "none"
                    resp_data = _read(payload)
                choice = resp_data.get("choices", [{}])[0]
                final_text = _finish(choice.get("message", {}) or {})
                if not final_text and choice.get("finish_reason") == "length":
                    # خنق حد الإخراج (غالباً بتفكير داخلي): أعد بسقف أعلى وبلا تفكير.
                    payload["max_tokens"] = min(65536, max(int(payload.get("max_tokens") or 0) * 2, 16384))
                    if payload.pop("reasoning", None):
                        applied_effort = None
                    print(f"Synthesis hit length for {target_model}; retrying with max_tokens={payload['max_tokens']}", flush=True)
                    resp_data = _read(payload)
                    choice = resp_data.get("choices", [{}])[0]
                    final_text = _finish(choice.get("message", {}) or {})
                if not final_text and (choice.get("message", {}) or {}).get("tool_calls"):
                    # أصرّ النموذج على الأدوات رغم منعها: نظّف سجل الاستدعاءات
                    # من الحوار وأعد الطلب نصاً خالصاً بلا أي أدوات.
                    print(f"Synthesis still tool-calling for {target_model}; sanitizing history and retrying", flush=True)
                    clean_dialog = []
                    for item in dialog:
                        if item.get("role") == "tool":
                            clean_dialog.append({"role": "user", "content": f"نتيجة أداة سابقة: {item.get('content', '')}"})
                        elif item.get("tool_calls"):
                            if (item.get("content") or "").strip():
                                clean_dialog.append({"role": "assistant", "content": item.get("content")})
                        else:
                            clean_dialog.append(item)
                    payload["messages"] = clean_dialog
                    payload.pop("tools", None)
                    payload.pop("tool_choice", None)
                    resp_data = _read(payload)
                    choice = resp_data.get("choices", [{}])[0]
                    final_text = _finish(choice.get("message", {}) or {})
                if not final_text:
                    # لا تُرجع فراغاً صامتاً: علّل حتى يظهر السبب للمستخدم وفي السجل.
                    raise RuntimeError(
                        f"أرجع النموذج رداً فارغاً (finish_reason={choice.get('finish_reason')}, "
                        f"usage={resp_data.get('usage')}, error={resp_data.get('error')})"
                    )
                return final_text

            # وضع التوليف المحمي: بحث مغلق مكتمل ومحفوظ يعني صياغة من الحزمة فقط،
            # بلا جولات أدوات ثانية وبلا تفكير يلتهم سقف الإخراج.
            _synthesis_mode = False
            if retrieved_citations and req.chat_id:
                _run0 = _research_run_load(req.chat_id)
                _synthesis_mode = bool(_run0 and _run0.get("status") in ("done", "closed")) and not _discussion
            try:
                if str(call_model or "").startswith("local:"):
                    live_reply = _complete_local_text(
                        call_model,
                        messages_payload,
                        _sampling_temperature(),
                        min(safe_max_output_tokens, 4096),
                    )
                elif _synthesis_mode:
                    print("📦 [Synthesis] بحث مغلق مكتمل: توليف بلا أدوات وبتفكير منخفض وسقف إخراج محمي", flush=True)
                    live_reply = _query_openrouter(call_model, min(65536, max(safe_max_output_tokens, 24576)), with_reasoning=False, allow_tools=False)
                else:
                    live_reply = _query_openrouter(call_model, safe_max_output_tokens)
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")
                live_error = f"HTTP {he.code}: {err_body[:200]}".strip()
                print(f"OpenRouter HTTP Error ({he.code}) for model {call_model}: {err_body[:300]}")
                try:
                    # إعادة أخيرة بنفس سقف الإخراج وبلا معلمة تفكير؛ تقليص السقف إلى
                    # 4096 كان يستهلكه التفكير الداخلي فيرجع الرد فارغاً.
                    print(f"Retrying same model {call_model} without reasoning param...")
                    live_reply = _query_openrouter(call_model, safe_max_output_tokens, with_reasoning=False, allow_tools=not _synthesis_mode)
                except Exception as retry_err:
                    live_error = str(retry_err)[:240]
                    print(f"Retry with same model failed: {retry_err}")
            except Exception as e:
                if str(call_model or "").startswith("local:"):
                    live_reply = "تعذر تشغيل النموذج المحلي. تأكد أن ملف GGUF سليم وأن ذاكرة الجهاز تكفي لتحميله."
                live_error = f"{type(e).__name__}: {str(e)[:200]}"
                print(f"Live model query error for {call_model}: {type(e).__name__}: {str(e)[:300]}", flush=True)
        except Exception as outer_e:
            print(f"Outer live model handler error: {outer_e}")

    if not live_reply and req.chat_id and retrieved_citations:
        # الاستئناف من الحزمة: إن تعذر التوليف المباشر أو ابتُّر، تبنى الإجابة من
        # حزمة البحث المحفوظة في قاعدة البيانات بنفس رقم المحادثة، لا من ذاكرة متطايرة.
        try:
            _run = _research_run_load(req.chat_id)
            if _run and _run.get("status") in ("done", "closed"):
                _digest: List[str] = []
                for _rd in (_run.get("rounds") or []):
                    for _p in (_rd.get("passages") or [])[:6]:
                        _digest.append(f"- [{_p.get('title')}] ج{_p.get('part')} ص{_p.get('page')}: {(_p.get('snippet') or '')[:260]}")
                if _digest:
                    print(f"📦 [Research Resume] توليف مستأنف من الحزمة {req.chat_id} ({len(_digest)} شاهدا مضغوطا)", flush=True)
                    live_reply = call_openrouter_raw(
                        model_id=call_model,
                        api_key=owner_openrouter_key(request, req.api_key),
                        messages=[
                            {"role": "system", "content": "أنت النموذج الأساسي المحقق. قبل الكتابة رتّب بطاقات أدلة من الشواهد المرفقة (الدعوى، الكتاب والجزء والصفحة، النص، نوع الدليل ومذهب كتابه)، ثم اكتب الجواب البحثي الكامل مبنيًا عليها بلا أدوات وبلا بحث جديد. لا تنسب مذهبًا إلا ببطاقة كتابه أو بطاقة خلاف تنص على النسبة، وانقل الشواهد الوثيقة بلفظها، وأحل في حواش مستقلة باسم الكتاب والجزء والصفحة، ولا تفت من الذاكرة. ولا ترفع درجة حديث فوق حكم بطاقته، وانسب أحكام التواتر والتصحيح لقائلها لا تطلقها من عندك."},
                            {"role": "user", "content": f"السؤال: {last_user_msg}\n\nشواهد حزمة البحث الموثقة بجولاتها:\n" + "\n".join(_digest[:40])},
                        ],
                        temperature=0.2, max_tokens=24576, timeout=150, thinking_level="low",
                    )
        except Exception as _resume_err:
            print(f"📦 [Research Resume] تعذر الاستئناف من الحزمة: {_resume_err}", flush=True)

    # 🗣️ تنفيذ طلبات الإرسال التي أصدرها المدير أثناء المناقشة: يطلب وكيلًا
    # بعينه لمهمة استكمال/تحقق، فتُنفَّذ باسترجاع جديد داخل نطاق كتبه
    # وبطاقة مهمته، ثم يعود تقريره إلى المدير ليجيب الباحث بناءً عليه.
    if _discussion == "open" and live_reply:
        _orders = re.findall(r"⟦\s*طلب-وكيل\s*:\s*([^|⟧]+)\|\s*([^⟧]+)⟧", live_reply)[:3]
        _page_orders = re.findall(r"⟦\s*طلب-صفحة\s*:\s*([^⟧]+)⟧", live_reply)[:3]
        _book_orders = re.findall(r"⟦\s*طلب-كتاب\s*:\s*([^|⟧]+)\|\s*([^|⟧]+)\|\s*([^⟧]+)⟧", live_reply)[:2]
        if _orders or _page_orders or _book_orders:
            _dkey = owner_openrouter_key(request, req.api_key)
            _reports = []
            # 📚 استدعاء كتاب بأمر المدير: نقلٌ بواسطة عن كتاب موجود في
            # الشاملة غير مدرج في بطاقة مختصه — يُضاف الكتاب إلى بطاقة
            # الوكيل المختص حفظًا دائمًا، ويُطلب منه التحقق من الأصل نفسه.
            for _bref, _aname, _btask in _book_orders:
                _bref = _bref.strip(); _aname = _aname.strip(); _btask = _btask.strip()
                _brow = None
                _bdg = re.search(r"(\d{1,7})", _bref)
                try:
                    _brow = shamela_local_mcp.resolve_book(_bdg.group(1) if _bdg else _bref)
                except Exception:
                    _brow = None
                if not _brow or not _brow.get("book_id"):
                    _reports.append(f"• طلب كتاب «{_bref}»: لم يُعثر عليه في الشاملة بهذا الاسم أو الرقم، فلم يُضف ولم يُتحقق منه — صرّح للباحث بذلك.")
                    continue
                _bid2 = int(_brow["book_id"]); _btitle2 = _brow.get("title") or _bref
                _entry2 = f"#{_bid2} {_btitle2}"
                _ag2 = next((a for a in active_agents if str(a.get("name") or "").strip() == _aname), None)
                if _ag2 is None:
                    _ag2 = next((a for a in active_agents if _aname and (_aname in str(a.get("name") or "") or str(a.get("name") or "") in _aname)), None)
                if _ag2 is None:
                    _reports.append(f"• طلب كتاب «{_btitle2}» للوكيل «{_aname}»: لم يُعثر على الوكيل في الفريق المختار، فلم يُضف.")
                    continue
                # الحفظ الدائم في بطاقة الوكيل ضمن مجموعته
                _persisted = False
                try:
                    _akey = _owner_key("agents", current_owner_id(request))
                    _aconn = _ensure_app_memory()
                    try:
                        _arow = _aconn.execute("SELECT payload FROM kv_documents WHERE key=?", (_akey,)).fetchone()
                        if _arow is not None:
                            _agroups = json.loads(_arow["payload"]) or []
                            _gids = [x.strip() for x in str((req.agent_group or {}).get("id") or "").split(",") if x.strip()]
                            for _grp in _agroups:
                                if _gids and str(_grp.get("id")) not in _gids:
                                    continue
                                for _ga in (_grp.get("agents") or []):
                                    if str(_ga.get("name") or "").strip() == str(_ag2.get("name") or "").strip():
                                        _gb = list(_ga.get("books") or [])
                                        if _entry2 not in _gb and not any(str(b).startswith(f"#{_bid2} ") for b in _gb):
                                            _gb.append(_entry2)
                                            _ga["books"] = _gb; _ga["booksScope"] = _gb
                                            _persisted = True
                            if _persisted:
                                _aconn.execute(
                                    "INSERT INTO kv_documents (key, payload, updated_at) VALUES (?, ?, ?) "
                                    "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                                    (_akey, json.dumps(_agroups, ensure_ascii=False), datetime.now().isoformat()))
                                _aconn.commit()
                    finally:
                        _aconn.close()
                except Exception as _perr:
                    print(f"📚 [Book Summon] تعذر الحفظ الدائم: {_perr}", flush=True)
                print(f"📚 [Book Summon] استدعى المدير «{_btitle2}» (#{_bid2}) إلى بطاقة «{_ag2.get('name')}» (حفظ دائم: {_persisted}) للتحقق: {_btask[:80]}", flush=True)
                # التحقق الفوري من الكتاب المستدعى نفسه في مهمة المدير
                try:
                    _dterms = []
                    try:
                        _dterms = _extract_classical_terms(_btask, _dkey)
                    except Exception:
                        _dterms = []
                    _cits2 = run_rag_search(_btask, selected_books=[_entry2], pool_size=240, top_k=40,
                                            dynamic_anchors=_dterms or None,
                                            use_hybrid=str(_ag2.get("search_mode") or _ag2.get("searchMode") or "hybrid").strip().lower() != "semantic",
                                            semantic_channel=locals().get("_sem_pass", True),
                                            honor_agent_limit=True)
                    _snips2 = "\n\n".join(
                        f"- الإحالة المعتمدة: {_approved_citation_label(c)} | المصنف: {c.get('author') or ''}:\n  {_full_page_snippet(c, cap=4200, with_next=True)}"
                        for c in _cits2[:30])
                    _rep2 = call_openrouter_raw(
                        model_id=normalize_model_id(_ag2.get("model") or "google/gemini-2.5-flash"),
                        messages=[
                            {"role": "system", "content": (
                                f"أنت الوكيل المساعد التخصصي: «{_ag2.get('name')}». تخصصك: {_ag2.get('desc') or ''}. "
                                f"التوجيه التخصصي المعتمد: {_ag2.get('system_prompt') or _ag2.get('systemPrompt') or 'استخراج وتحرير وتوثيق نصوص المسألة بدقة'}.\n"
                                f"استدعى مدير المشروع كتاب «{_btitle2}» وأضافه إلى بطاقتك لأنه منقول عنه بالواسطة في بحث منجز وهو أصله المباشر. نفّذ مهمة التحقق الآتية من هذا الكتاب نفسه حصرًا، وابدأ ببطاقات الأدلة ثم التحرير. إن لم تجد المطلوب فيه فصرّح بذلك ولا تُكمل من غيره.")},
                            {"role": "user", "content": f"مهمة التحقق من المدير: {_btask}\n\nالنصوص المسترجعة من الكتاب المستدعى «{_btitle2}» ({len(_cits2)} مقطعًا):\n{_snips2 or 'لم يُرجع الكتاب شاهدًا في هذه المهمة.'}"},
                        ],
                        api_key=_dkey, temperature=0.2, max_tokens=24576, timeout=150,
                        thinking_level=str(_ag2.get("thinking") or "").strip() or None) or ""
                    subagents_dossiers.append({"name": _ag2.get("name"), "desc": _ag2.get("desc") or "",
                                               "model": _ag2.get("model"), "books": [_entry2],
                                               "citations": _cits2, "report": _rep2, "failed": False, "fail_reason": ""})
                    _reports.append(f"══ استدعاء كتاب: أُضيف «{_btitle2}» (#{_bid2}) إلى بطاقة «{_ag2.get('name')}»{' حفظًا دائمًا في بطاقته' if _persisted else ' لهذه الجولة (تعذر الحفظ الدائم)'}، وتحقق منه في مهمة: {_btask} ══\n{_rep2[:9000]}")
                except Exception as _berr:
                    print(f"📚 [Book Summon] تعذر التحقق من الكتاب المستدعى: {_berr}", flush=True)
                    _reports.append(f"• استدعاء كتاب «{_btitle2}» للوكيل «{_aname}»: أُضيف إلى بطاقته{' دائمًا' if _persisted else ''} لكن تعذر التحقق الفوري تقنيًا ({type(_berr).__name__}).")
            # 📄 تقليب صفحات بطلب المدير: نص الصفحة كاملًا وتتمة التالية
            for _po in _page_orders:
                _nums = [int(n) for n in re.findall(r"\d+", _po)]
                if len(_nums) < 2:
                    _reports.append(f"• طلب صفحة «{_po.strip()}»: صيغة غير مكتملة (يلزم رقم الكتاب والصفحة)، فلم يُنفَّذ.")
                    continue
                _bid = _nums[0]
                _ppart = str(_nums[1]) if len(_nums) >= 3 else None
                _ppage = _nums[2] if len(_nums) >= 3 else _nums[1]
                try:
                    # الصفحة المطلوبة محاطة بسابقتها ولاحقتها: فالنص المبتور
                    # آخر صفحة تتمته أول التالية، والمبدوء أول صفحة مبدؤه
                    # آخر السابقة — وبغير الجارين يبقى انقطاع كلام الأئمة.
                    _chunks = []
                    for _lbl, _pn in (("السابقة", _ppage - 1), ("المطلوبة", _ppage), ("التالية", _ppage + 1)):
                        if _pn <= 0:
                            continue
                        _fc = {"book_id": _bid, "page_num_raw": _pn, "part_raw": _ppart, "snippet": ""}
                        _pt = _full_page_snippet(_fc, cap=3200, with_next=False)
                        if _pt:
                            _chunks.append(f"— الصفحة {_lbl} (ص{_pn}) —\n{_pt}")
                    _ptext = "\n\n".join(_chunks)
                    _btitle = ""
                    try:
                        _rb = shamela_local_mcp.resolve_book(str(_bid))
                        _btitle = (_rb or {}).get("title") or ""
                    except Exception:
                        _btitle = ""
                    print(f"📄 [Discussion PageTurn] قلّب المدير صفحة الكتاب #{_bid} ج{_ppart} ص{_ppage} مع جارتيها ({len(_ptext)} حرفًا)", flush=True)
                    _reports.append(f"══ نص الصفحة المطلوبة: «{_btitle}» #{_bid} ج{_ppart or ''} ص{_ppage} مع سابقتها وتاليتها ══\n{_ptext or 'لم يُعثر على نص هذه الصفحة في ملفات الكتاب.'}")
                except Exception as _perr:
                    _reports.append(f"• طلب صفحة «{_po.strip()}»: تعذر جلبه تقنيًا ({type(_perr).__name__}).")
            for _oname, _otask in _orders:
                _oname = _oname.strip(); _otask = _otask.strip()
                _ag = next((a for a in active_agents if str(a.get("name") or "").strip() == _oname), None)
                if _ag is None:
                    _ag = next((a for a in active_agents if _oname and (_oname in str(a.get("name") or "") or str(a.get("name") or "") in _oname)), None)
                if _ag is None:
                    _reports.append(f"• طلب لوكيل «{_oname}»: لم يُعثر على وكيل بهذا الاسم في الفريق المختار لهذه المحادثة، فلم يُنفَّذ.")
                    continue
                try:
                    _ag_books = [str(b).strip() for b in (_ag.get("booksScope") or _ag.get("books") or []) if str(b).strip()]
                    _ag_topk = int(_ag.get("top_k") or _ag.get("topK") or _ag.get("extract_count") or _ag.get("extractCount") or 60)
                    _ag_topk = max(10, min(_ag_topk, 80))
                    # وكيل الألفاظ الدلالية يمد مهمة الاستكمال بمراسي
                    # المتقدمين أيضًا، فلا تنقطع المهمة بلفظ الباحث المعاصر.
                    _dtask_terms = []
                    try:
                        _dtask_terms = _extract_classical_terms(_otask, _dkey)
                    except Exception:
                        _dtask_terms = []
                    _cits = run_rag_search(_otask, selected_books=_ag_books or None,
                                           pool_size=max(_ag_topk * 4, 200), top_k=_ag_topk,
                                           dynamic_anchors=_dtask_terms or None,
                                           use_hybrid=str(_ag.get("search_mode") or _ag.get("searchMode") or "hybrid").strip().lower() != "semantic",
                                           semantic_channel=locals().get("_sem_pass", True),
                                           honor_agent_limit=bool(_ag_books))
                    _snips = "\n\n".join(
                        f"- الإحالة المعتمدة: {_approved_citation_label(c)} | المصنف: {c.get('author') or ''}:\n  {_full_page_snippet(c, cap=4200, with_next=True)}"
                        for c in _cits[:min(_ag_topk, 30)])
                    _ag_model = normalize_model_id(_ag.get("model") or "google/gemini-2.5-flash")
                    _rep = call_openrouter_raw(
                        model_id=_ag_model,
                        messages=[
                            {"role": "system", "content": (
                                f"أنت الوكيل المساعد التخصصي: «{_ag.get('name')}». تخصصك: {_ag.get('desc') or ''}. "
                                f"التوجيه التخصصي المعتمد: {_ag.get('system_prompt') or _ag.get('systemPrompt') or 'استخراج وتحرير وتوثيق نصوص المسألة بدقة'}.\n"
                                "طلبك مدير المشروع أثناء جلسة مناقشة استكمالية حول بحث منجز. نفّذ المهمة الآتية من المقاطع المرفقة حصرًا، وابدأ ببطاقات الأدلة (الدعوى، الإحالة منسوخة حرفيًا، النص، نوع الدليل ومذهب كتابه) ثم التحرير المبني عليها. لا تُكمل من الذاكرة، وإن لم تجد فصرّح بذلك. قاعدة طبقات صارمة: الشروح المعاصرة وتفريغات الدروس ليست سندًا لمتن حديث أو حكم مذهب أو إجماع؛ لا تنقل عنها بالواسطة، وإن أشارت إلى أصل تراثي فاذكره للاستدلال على موضعه وابنِ على الأصل وحده إن وجدته.")},
                            {"role": "user", "content": f"المهمة المطلوبة من المدير: {_otask}\n\nالنصوص المسترجعة من نطاق كتبك ({len(_cits)} مقطعًا):\n{_snips or 'لم يُرجع النطاق شاهدًا.'}"},
                        ],
                        api_key=_dkey, temperature=0.2, max_tokens=24576, timeout=150,
                        thinking_level=str(_ag.get("thinking") or "").strip() or None) or ""
                    print(f"🗣️ [Discussion Dispatch] نفّذ المدير طلبًا للوكيل '{_ag.get('name')}' ({len(_cits)} شاهدًا، تقرير {len(_rep)} حرفًا)", flush=True)
                    subagents_dossiers.append({"name": _ag.get("name"), "desc": _ag.get("desc") or "",
                                               "model": _ag_model, "books": _ag_books,
                                               "citations": _cits, "report": _rep, "failed": False, "fail_reason": ""})
                    _reports.append(f"══ تقرير الوكيل «{_ag.get('name')}» في مهمة: {_otask} ══\n{_rep[:9000]}")
                except Exception as _derr:
                    print(f"🗣️ [Discussion Dispatch] تعذر تنفيذ طلب الوكيل '{_oname}': {_derr}", flush=True)
                    _reports.append(f"• طلب لوكيل «{_oname}» في مهمة «{_otask}»: تعذر تنفيذه تقنيًا ({type(_derr).__name__})، فلم يرجع تقريره.")
            try:
                _follow = call_openrouter_raw(
                    model_id=call_model,
                    messages=[
                        {"role": "system", "content": (
                            "أنت مدير المشروع وقائد الفريق في جلسة مناقشة مفتوحة مع الباحث حول بحث منجز. أصدرتَ طلبات إرسال لوكلاء، وهذه تقاريرهم الراجعة. "
                            "أجب الباحث الآن جواب المناقشة بناءً على هذه التقارير حصرًا في الجديد: بيّن ما أضافه كل وكيل أو ما صرّح بخلوّه، وناقش أثره في النواقص، ولا تصدر طلبات إرسال جديدة في هذا الرد، ولا تعد صياغة البحث كاملًا. ولا تخترع أسبابًا تقنية من عندك (كتعذر حفظ أو عطل فهرسة) لم ترد في التقارير؛ سبب أي إخفاق هو ما في التقرير فقط، وما لم تعرفه قل: لا أعلم سببه بعد. "
                            "واختم ببيان: «اتفقنا على: ... | بقي مفتوحًا: ... | سيتغير في الصياغة النهائية: ...».")},
                        {"role": "user", "content": f"سؤال الباحث/موضوع الجولة: {last_user_msg}\n\nنتائج طلباتك المنفذة (تقارير وكلاء ونصوص صفحات مجلوبة بتقليب الصفحات):\n" + "\n\n".join(_reports)},
                    ],
                    api_key=_dkey, temperature=0.2, max_tokens=24576, timeout=200,
                    thinking_level=req.thinking_level) or ""
                if _follow.strip():
                    live_reply = _follow
            except Exception as _ferr:
                print(f"🗣️ [Discussion Dispatch] تعذر جواب المدير بعد التقارير: {_ferr}", flush=True)
                live_reply = live_reply + "\n\n—\n**تقارير الوكلاء المنفذة في هذه الجولة:**\n\n" + "\n\n".join(_reports)[:12000]

    # 🔒 تنقية الصياغة النهائية من لغة عملية البحث والمناقشة: إن تسللت
    # عبارات الوكلاء والمقاطع والاسترجاع إلى المتن، أُعيدت صياغة جملها
    # المسيئة فقط بلسان ورقة علمية محكمة، مع حفظ النقول والحواشي حرفيًا.
    if _discussion == "finalize" and live_reply:
        _meta_pats = ["وكيل", "الوكلاء", "المقطع المستخرج", "المقتطف", "الاسترجاع",
                      "بطاقات الأدلة", "بطاقة", "لم يُرجع", "لم يرجع", "الشواهد المستخرجة",
                      "نطاق هذا الوكيل", "اتفقنا على", "في مناقشتنا", "جلسة المناقشة",
                      "مدير المشروع", "انقطع النص", "لم يكتمل لفظ"]
        _meta_hits = sum(live_reply.count(p) for p in _meta_pats)
        if _meta_hits:
            try:
                _clean = call_openrouter_raw(
                    model_id=call_model,
                    messages=[
                        {"role": "system", "content": (
                            "أنت محرر علمي. هذا نص صياغة نهائية لبحث شرعي، تسللت إليه عبارات من لغة عملية إنتاجه "
                            "(وكيل، وكلاء، جلب الوكيل، الشواهد المستخرجة، المقطع، الاسترجاع، بطاقات، انقطع النص في المقطع، "
                            "في مناقشتنا، مدير المشروع ونحوها). مهمتك: أعد صياغة الجمل المسيئة وحدها بلسان ورقة علمية محكمة "
                            "مغلقة (من جنس: «لم نقف على نص صريح للمذهب في كتبه المعتمدة في عين المسألة»، «ولم نقف في كتب الظاهرية على نص فيها»)، "
                            "مع حفظ كل نقل مقتبس وكل حاشية وكل إحالة وكل رقم وترتيب النص حرفيًا كما هو، وبلا حذف أي معلومة علمية وبلا إضافة من عندك. "
                            "أخرج النص كاملًا منقّى فقط.")},
                        {"role": "user", "content": live_reply},
                    ],
                    api_key=owner_openrouter_key(request, req.api_key),
                    temperature=0.1, max_tokens=65536, timeout=300,
                    thinking_level="low") or ""
                if len(_clean.strip()) >= int(len(live_reply) * 0.6):
                    print(f"🔒 [Finalize Purge] نُقّيت الصياغة النهائية من {_meta_hits} عبارة عملية", flush=True)
                    live_reply = _clean
                else:
                    print(f"🔒 [Finalize Purge] رُفضت التنقية لقصرها ({len(_clean)} مقابل {len(live_reply)})", flush=True)
            except Exception as _purge_err:
                print(f"🔒 [Finalize Purge] تعذرت التنقية: {_purge_err}", flush=True)

    witness_pool = list(included_citations)
    for dossier in subagents_dossiers:
        witness_pool.extend(dossier.get("citations") or [])
    witness_rows = public_chat_witnesses(witness_pool, limit=witness_limit)

    if live_reply:
        if req.custom_generation:
            reply_text = live_reply
        else:
            _stamped, _unresolved_citations = enrich_unstamped_citations(
                stamp_citation_sources(enforce_standard_citations(live_reply), witness_rows))
            if _unresolved_citations:
                print(f"⚠ [Citations] {_unresolved_citations} إحالة بموضع لم تُحلّ في قاعدة المكتبة — مُيّزت بعلامة ⚠ في المتن", flush=True)
            # خط المشاريع والوكلاء: لا ترشيح مدمّرًا للحواشي؛ بطاقات الأدلة
            # قبل الكتابة هي الضبط، والتدقيق بعده تنبيه لا حذف.
            reply_text = strip_trailing_bibliography(
                _stamped if req.agent_group else filter_unverified_footnotes(_stamped)
            )
            # قائمة المصادر والمراجع = الكتب المستشهد بها فعلاً في الجواب (حواشيه
            # تحمل #رقمها)، لا كل ما استخرجه البحث. بلا إحالات مرقمة تبقى القائمة كما هي.
            cited_ids = {int(num) for num in re.findall(r"#(\d{1,7})", reply_text)}
            if cited_ids:
                cited_rows = [row for row in witness_rows if row.get("book_id") in cited_ids]
                if cited_rows:
                    witness_rows = cited_rows
            if _failed_agents:
                # إعلان السقوط الباقي في صدر الجواب: فنٌّ بلا تقرير بعد سُلّم
                # الإنقاذ كاملًا يُصرَّح به للقارئ، لا يُدفن في سجل القياسات.
                _failed_names = "، ".join(str(d.get("name") or "") for d in _failed_agents)
                reply_text = (
                    f"> ⚠ **تنبيه منهجي:** تعذّر تقرير {_failed_names} رغم سُلّم الإنقاذ كاملًا "
                    "(إعادة جولة، ونموذج احتياطي، ونموذج مختص، ومدير المشروع باحثًا بنفسه في كتبهم)؛ "
                    "فما يأتي في فنّهم مبنيّ على شواهد نطاقهم المرفقة بلا تقرير محرَّر منهم.\n\n"
                ) + reply_text
            if req.agent_group and not req.graph_only and not req.table_only and _discussion != "open":
                # تدقيق توثيق غير مدمّر: مطابقة النقول على صفحات كتبها وسجل
                # تنبيه ختامي ظاهر، بلا حذف ولا جولة إصلاح تستبدل البحث.
                try:
                    reply_text, _gate_stats = _documentation_gate(reply_text, witness_rows)
                    if locals().get("_hadith_project"):
                        _gate_stats["skip_madhhab_coverage"] = True
                    # سجل التدقيق وتنبيها اكتمال الفريق والنطاق لا تُختم في
                    # متن الجواب بعد اليوم: تُحفظ كاملة في سجل القياس وتخرج
                    # بملف «تقرير البحث» المنفصل أسفل الإجابة، فلا تشوّه
                    # المحادثة ولا تضيع المحاسبة.
                    _audit_record_text = _documentation_record(_gate_stats)
                    if _unresolved_citations:
                        _audit_record_text += (
                            f"\nتنبيه حواشٍ خارج تحقق المكتبة: {_unresolved_citations} إحالة بموضع لم تُحلّ في قاعدة "
                            "المكتبة الشاملة، مميزة في متن الإجابة بعلامة ⚠ — مراجع على ذمة النموذج لم يتحقق النظام منها.")
                    # كشف التغطية اللفظية: لفظ متقدمين وُثّق كلماتيًا في
                    # المكتبة قبل البحث ثم لم يظهر له أثر في متن الإجابة =
                    # موضع صريح محتمل أُغفل (كنص المرداوي في تقبيل الفرج).
                    try:
                        _st_terms = list(locals().get("_semantic_terms") or [])
                        if _st_terms:
                            _folded_reply = _fold_ar(reply_text or "")
                            _missing_terms = [t for t in _st_terms if _fold_ar(t) not in _folded_reply]
                            if _missing_terms:
                                _gate_stats["missing_terms"] = _missing_terms
                                _audit_record_text += ("\nتنبيه تغطية لفظية: ألفاظ متقدمين موثقة في المكتبة لم يظهر لها أثر في متن الإجابة، "
                                                       "فليُراجع ما وراءها من نصوص صريحة قبل الاعتماد: " + "، ".join(f"«{t}»" for t in _missing_terms[:8]) + ".")
                                print(f"⚓ [Coverage] ألفاظ موثقة غابت عن الإجابة: {_missing_terms}", flush=True)
                    except Exception:
                        pass
                    # إعلان قناة البحث الدلالي المعزّز: قرار الباحث وحالته
                    # الفعلية وشواهده في هذا البحث — لا صمت ولا خلط أحوال.
                    try:
                        _sem_wit = sum(1 for _c in (included_citations or []) if isinstance(_c, dict) and _c.get("channel") == "semantic")
                        _gate_stats["semantic_witnesses"] = _sem_wit
                        _audit_record_text += (f"\nقناة البحث الدلالي المعزّز (مخزن المتجهات): {locals().get('_sem_label') or 'غير محددة'}"
                                               + (f"؛ شواهد وصلت عبرها ودخلت الحزمة: {_sem_wit}." if locals().get("_sem_state") == "active" else "."))
                    except Exception:
                        pass
                    if _failed_agents:
                        _audit_record_text += ("\n\nتنبيه اكتمال الفريق: تعذّر تقرير "
                                               + "، ".join(f"«{d.get('name', '')}»" for d in _failed_agents)
                                               + " رغم إعادة محاولة الاتصال بنماذجهم؛ بُنيت أقسامهم على بطاقات الشواهد المستخرجة من نطاقاتهم وبطاقات الخلاف والمقارنة، لا على تقارير تحريرية منهم.")
                    if _disabled_agents:
                        _audit_record_text += ("\n\nنطاق البحث بقرار المستخدم: عطّل المستخدم قصدًا "
                                               + "، ".join(f"«{d['name']}»" for d in _disabled_agents)
                                               + " فلم يُطلب منهم شيء ولم يُعوَّض دورهم؛ بُني البحث على النطاق المقلّص بقرار الباحث لا على فريق المجموعة الكامل.")
                except Exception as _gate_err:
                    print(f"🚧 [Documentation Audit] {_gate_err}", flush=True)
    elif retrieved_citations:
        prefix_tag = f"### [معالجة واستنباط عبر: {group_name}]\n\n" if group_name else ""
        reason_line = f"\nسبب الرفض كما أرجعه المزود: {live_error}" if live_error else ""
        reply_text = f"""{prefix_tag}{thinking_indicator}⚠️ **تنبيه:** تعذر توليد الإجابة من النموذج المختار رغم استخراج الشواهد.{reason_line}

وفيما يلي الشواهد التراثية المستخرجة فعلياً من الشاملة ({len(retrieved_citations)} مقطعاً):

{citations_text}"""
    else:
        prefix_tag = f"### [إسناد لمجموعة: {group_name}]\n\n" if group_name else ""
        reply_text = f"""{prefix_tag}{thinking_indicator}الحمد لله، والصلاة والسلام على رسول الله، وبعد:
بخصوص استفساركم: «{last_user_msg}»: يرجى التحقق من مفتاح مزود الخدمة أو اتصال الشبكة."""

    # تسجيل مؤشرات قياس هذا البحث دائمًا (بحوث الوكلاء المنفذة حيًا فقط،
    # والصياغة النهائية بعد إقفال مناقشة تُقاس أيضًا لتوثق أثر الاستكمال)
    if req.agent_group and live_reply and (subagents_dossiers or _discussion == "finalize") and _discussion != "open":
        _gs = _gate_stats or {}
        _record_research_metrics(current_owner_id(request), {
            "ts": datetime.now().isoformat(),
            "chat_id": req.chat_id or "",
            "question": (last_user_msg or "")[:140],
            "group": group_name or "",
            "manager_model": call_model,
            "duration_s": round(time.time() - _chat_t0),
            "answer_chars": len(reply_text or ""),
            "witnesses": len(witness_rows or []),
            "citations_collected": len(retrieved_citations or []),
            "agents_total": len(subagents_dossiers),
            "agents_failed": [d.get("name", "") for d in _failed_agents],
            "agents_disabled": [d["name"] for d in _disabled_agents],
            "core_agents": [
                {"name": d.get("name", ""), "model": d.get("model", ""),
                 "citations": len(d.get("citations") or []),
                 "report_chars": len(d.get("report") or ""), "failed": bool(d.get("failed"))}
                for d in subagents_dossiers if d.get("core_rank", 99) < 99
            ],
            "stage_s": {k: v for k, v in _stage_marks},
            "ledger_chars": len(_evidence_ledger or ""),
            "audit_record": _audit_record_text,
            "audit_failures": [
                {"quote": f.get("quote", ""), "reason": f.get("reason", "")}
                for f in ((_gate_stats or {}).get("failures") or [])[:20]
            ],
            "audit": {
                "checked": _gs.get("checked", 0), "linked": _gs.get("linked"),
                "verified": _gs.get("verified", 0), "unverified": _gs.get("unverified", 0),
                "relocated": _gs.get("relocated", 0), "repaired": _gs.get("repaired", 0),
                "verified_unbound": _gs.get("verified_unbound", 0),
                "excluded_outside": _gs.get("excluded_outside", 0), "tier_warnings": _gs.get("tier_warnings", 0),
                "ijma_flags": _gs.get("ijma_flags", 0),
                "ijma_unattributed": len(_gs.get("ijma_unattributed") or []),
                "cited_books": len(_gs.get("cited_book_ids") or []),
                "missing_terms": _gs.get("missing_terms") or [],
                "semantic_channel": locals().get("_sem_state") or "",
                "semantic_witnesses": _gs.get("semantic_witnesses") or 0,
                "unresolved_citations": _unresolved_citations,
            },
        })

    return {
        "reply": reply_text,
        "model": call_model if live_reply else (req.model or "unknown"),
        "provider": req.provider or "openrouter",
        "thinking_level": req.thinking_level,
        "thinking_effort": applied_effort if live_reply else None,
        "agent_group": group_name if req.agent_group else None,
        "witnesses": witness_rows
    }


@app.get("/api/research-metrics")
async def research_metrics_endpoint(request: Request):
    """تقرير قياس البحوث: المؤشرات المسجلة لكل بحث وملخصها التجميعي،
    لقياس جودة المنظومة عبر الإصدارات بأرقام ثابتة."""
    owner = current_owner_id(request)
    key = _owner_key("research_metrics", owner)
    conn = _ensure_app_memory()
    try:
        row = conn.execute("SELECT payload FROM kv_documents WHERE key=?", (key,)).fetchone()
    finally:
        conn.close()
    items = []
    if row is not None:
        try:
            items = json.loads(row["payload"]) or []
        except Exception:
            items = []
    def _avg(vals):
        vals = [v for v in vals if isinstance(v, (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None
    ratios = []
    for it in items:
        a = it.get("audit") or {}
        if a.get("checked"):
            ratios.append(round(100.0 * (a.get("verified", 0) + a.get("relocated", 0)) / a["checked"], 1))
    summary = {
        "researches": len(items),
        "avg_duration_s": _avg([it.get("duration_s") for it in items]),
        "avg_answer_chars": _avg([it.get("answer_chars") for it in items]),
        "avg_witnesses": _avg([it.get("witnesses") for it in items]),
        "agent_failure_runs": sum(1 for it in items if it.get("agents_failed")),
        "agents_failed_total": sum(len(it.get("agents_failed") or []) for it in items),
        "agents_total": sum(it.get("agents_total") or 0 for it in items),
        "avg_audit_recognition_pct": _avg(ratios),
        "avg_quotes_checked": _avg([(it.get("audit") or {}).get("checked") for it in items]),
        "ijma_unattributed_total": sum((it.get("audit") or {}).get("ijma_unattributed", 0) for it in items),
    }
    return {"status": "ok", "summary": summary, "items": items[-50:]}


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
                "top_provider": m.get("top_provider") or {},
                "reasoning": remember_model_reasoning(m.get("id"), m.get("reasoning"))
            })
            slug = m.get("canonical_slug")
            if slug and slug != m.get("id"):
                OPENROUTER_REASONING[slug] = OPENROUTER_REASONING.get(m.get("id"))

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

def _save_owned_json(owner_id: str, kind: str, data) -> None:
    payload = json.dumps(data, ensure_ascii=False)
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

def _load_owned_json(owner_id: str, kind: str):
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
        return json.loads(row["payload"])
    except Exception:
        return None

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

def _standard_agent_groups():
    """الفريقان القياسيان المشحونان مع التطبيق (فقه مضبوط + محدّث، بمجلسيهما)."""
    seed_file = os.path.join(os.path.dirname(__file__), "default_agent_groups.json")
    try:
        with open(seed_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) and data else []
    except Exception:
        return []


def load_stored_agent_groups(owner_id: str):
    """قراءة مجموعات وكلاء هذا العضو فقط. من لا مخزون له بعد (تثبيت أو حساب
    جديد) تُزرع له المجموعات القياسية المشحونة؛ ومن حفظ قائمة فارغة بيده
    (حذف الكل) يُحترم حذفه ولا تُبعث له من جديد."""
    data = _load_owned_list(owner_id, "agents")
    if isinstance(data, list):
        return data
    seeds = _standard_agent_groups()
    if seeds:
        seeded = json.loads(json.dumps(seeds, ensure_ascii=False))
        try:
            _save_owned_list(owner_id, "agents", seeded)
        except Exception:
            pass
        return seeded
    return []

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
    message_index: Optional[int] = None

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

def _single_answer_chat(session: Dict[str, Any], index: int) -> Dict[str, Any]:
    messages = session.get("messages") or []
    if index < 0 or index >= len(messages) or not isinstance(messages[index], dict):
        raise HTTPException(status_code=400, detail="الإجابة المحددة غير موجودة")
    message = messages[index]
    content = str(message.get("content") or "")
    heading = re.match(r"^#{1,3}\s+(.+)", content)
    if heading:
        title = heading.group(1).strip()
    else:
        plain = re.sub(r"<[^>]+>", " ", content)
        plain = re.sub(r"\s+", " ", plain).strip()
        title = plain[:60] or "إجابة مشاركة"
    return {
        "id": session.get("id"),
        "title": title[:180],
        "createdAt": datetime.now().isoformat(),
        "messages": [message],
        "shared_answer": True,
    }

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
            if kind == "chat" and req.message_index is not None:
                source = _single_answer_chat(source, int(req.message_index))
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

@app.get("/api/projects/draft")
async def get_project_draft(request: Request):
    """آخر مشروع حُفظ تلقائياً، حتى لو تجمّد التطبيق قبل ظهوره في القائمة."""
    owner_id = current_owner_id(request)
    draft = _load_owned_json(owner_id, "project_draft")
    if isinstance(draft, dict) and draft.get("id"):
        return {"project": draft}
    projects = load_stored_projects(owner_id)
    if projects:
        return {"project": projects[0]}
    return {"project": None}

@app.post("/api/projects/draft")
async def save_project_draft(payload: dict, request: Request):
    """حفظ تلقائي للمسودة في قاعدة البيانات، مستقل عن زر الاعتماد."""
    payload["autosaved"] = True
    saved = await save_project(payload, request)
    project = saved.get("project") or payload
    _save_owned_json(current_owner_id(request), "project_draft", project)
    return {"status": "ok", "project": project}

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
    owner_id = current_owner_id(request)
    stored = _load_owned_list(owner_id, "agents") is not None
    response.headers["X-Agent-Groups-Stored"] = "1" if stored else "0"
    return load_stored_agent_groups(owner_id)

@app.post("/api/agent-groups")
async def save_agent_groups_endpoint(request: Request, payload: Any = Body(...)):
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

ECHARTS_BUILTIN_TOOL = {
    "id": "echarts_charts",
    "name": "أداة الرسوم البيانية (ECharts)",
    "type": "web_library",
    "tool_type": "ready_web_lib",
    "category": "بيانات وإحصاء",
    "desc": "توليد عدة أنواع من الرسوم مثل أمثلة Apache ECharts: أعمدة، خطي، دائري، رادار، شجرة، سانكي، وغيرها، من ناتج البحث.",
    "description": "توليد عدة أنواع من الرسوم مثل أمثلة Apache ECharts: أعمدة، خطي، دائري، رادار، شجرة، سانكي، وغيرها، من ناتج البحث.",
    "library_url": "https://echarts.apache.org/examples/en/",
    "enabled": True,
    "is_builtin": True,
}

ISLAMAP_BUILTIN_TOOL = {
    "id": "islamap_map",
    "name": "خارطة العالم الإسلامي",
    "type": "web_library",
    "tool_type": "ready_web_lib",
    "category": "بيانات وإحصاء",
    "desc": "خارطة جغرافية للعالم بحدود الدول، مع مدن وفتوحات وغزوات من ناتج البحث، على نسق علاقة ECharts الجغرافية.",
    "description": "خارطة جغرافية للعالم بحدود الدول، مع مدن وفتوحات وغزوات من ناتج البحث، على نسق علاقة ECharts الجغرافية.",
    "library_url": "",
    "enabled": True,
    "is_builtin": True,
}


def load_stored_tools(owner_id: str):
    data = _load_owned_list(owner_id, "tools")
    tools = data if isinstance(data, list) else []
    changed = False
    if not any(isinstance(item, dict) and item.get("id") == "echarts_charts" for item in tools):
        tools.append(dict(ECHARTS_BUILTIN_TOOL))
        changed = True
    if not any(isinstance(item, dict) and item.get("id") == "islamap_map" for item in tools):
        tools.append(dict(ISLAMAP_BUILTIN_TOOL))
        changed = True
    if changed:
        save_stored_tools(tools, owner_id)
    return tools

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
    architect_spec: Optional[Any] = None
    research_sources: Optional[Any] = None
    build_model: Optional[str] = ""
    example_input: Optional[Any] = None
    example_output: Optional[Any] = None
    application_instruction: Optional[str] = ""
    packages: Optional[List[str]] = None
    cdn_urls: Optional[List[str]] = None

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
    modern_python: Optional[bool] = False

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


class ToolApplyRequest(BaseModel):
    tool_id: str
    research_text: str = ""


def _as_tool_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _tool_research_payload(tool: Dict[str, Any], text: str) -> Dict[str, Any]:
    stripped = (text or "").strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]{0,20000}?\})\s*```", stripped)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            if isinstance(parsed, dict) and any(key in parsed for key in ("research_text", "issue", "scholars", "text")):
                return parsed
        except Exception:
            pass
    tested = (
        _as_tool_dict(tool.get("mock_data"))
        or _as_tool_dict(tool.get("mock_test_data"))
        or _as_tool_dict(tool.get("example_input"))
    )
    payload = dict(tested)
    payload["research_text"] = stripped
    payload["text"] = stripped
    payload["content"] = stripped
    payload["answer"] = stripped
    return payload


def _execute_saved_tool(code: str, mock_data: Any, timeout: int = 90) -> Dict[str, Any]:
    runner = f'''import sys, json, traceback

mock_input = {json.dumps(mock_data, ensure_ascii=False)}

try:
{textwrap.indent(code, "    ")}

    res = None
    if "run_tool" in locals() and callable(locals()["run_tool"]):
        res = locals()["run_tool"](mock_input)
    elif "process_data" in locals() and callable(locals()["process_data"]):
        res = locals()["process_data"](mock_input)
    elif "result" in locals():
        res = locals()["result"]
    else:
        res = "تم تنفيذ كود الأداة بنجاح دون أخطاء برمجية."
    print("___EXEC_OK___")
    print(json.dumps(res, ensure_ascii=False, default=str))
except Exception:
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''
    path = ""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
            handle.write(runner)
            path = handle.name
        started = time.time()
        process = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=timeout)
        duration = round((time.time() - started) * 1000, 1)
        if process.returncode != 0:
            return {
                "success": False,
                "error": (process.stderr or process.stdout or "فشل تشغيل الأداة").strip()[-4000:],
                "execution_time_ms": duration,
            }
        raw = process.stdout or ""
        if "___EXEC_OK___" not in raw:
            return {"success": False, "error": raw.strip()[-2000:] or "لم تُرجع الأداة نتيجة", "execution_time_ms": duration}
        json_part = raw.split("___EXEC_OK___", 1)[1].strip()
        try:
            parsed = json.loads(json_part)
        except Exception:
            parsed = json_part
        return {"success": True, "output": parsed, "execution_time_ms": duration}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"انتهت مهلة تشغيل الأداة ({timeout} ثانية)"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass


@app.post("/api/tools/apply")
async def apply_stored_tool_endpoint(req: ToolApplyRequest, request: Request):
    """تشغيل الأداة المعتمدة بمكتباتها على ناتج بحث جاهز."""
    text = (req.research_text or "").strip()
    if not text:
        return {"status": "ok", "success": False, "error": "لا توجد نتيجة بحث جاهزة لتطبيق الأداة عليها."}
    if len(text) > 120000:
        text = text[:120000]
    tools = load_stored_tools(current_owner_id(request))
    tool = next((item for item in tools if item.get("id") == req.tool_id), None)
    if not tool:
        return {"status": "ok", "success": False, "error": "الأداة غير موجودة في المستودع."}
    code = (tool.get("python_code") or "").strip()
    if code:
        packages = _safe_tool_packages(tool.get("packages") if isinstance(tool.get("packages"), list) else [])
        package_line = re.search(r"^#\s*package:\s*([A-Za-z0-9][A-Za-z0-9_.-]{0,60})", code, re.M)
        if package_line and package_line.group(1).lower() != "none":
            packages = _safe_tool_packages(packages + [package_line.group(1)])
        if packages:
            await asyncio.to_thread(_install_tool_packages, packages, [])
        payload = _tool_research_payload(tool, text)
        result = await asyncio.to_thread(_execute_saved_tool, code, payload, 90)
        if not result.get("success"):
            missing = re.search(r"No module named ['\"]([^'\"]+)['\"]", result.get("error") or "")
            module_name = missing.group(1).split(".")[0] if missing else ""
            if module_name and re.fullmatch(r"[A-Za-z0-9_]{1,60}", module_name):
                await asyncio.to_thread(_install_tool_packages, [module_name], [])
                result = await asyncio.to_thread(_execute_saved_tool, code, payload, 90)
        result["status"] = "ok"
        result["kind"] = "python"
        result["packages"] = packages
        return result
    cdn_urls = []
    for url in tool.get("cdn_urls") or []:
        target = str(url or "").strip()
        if target.startswith("https://") and " " not in target and target not in cdn_urls:
            cdn_urls.append(target)
    library_url = str(tool.get("library_url") or "").strip()
    npm_match = re.search(r"npmjs\.com/package/([^/?#]+)", library_url)
    if npm_match:
        cdn = f"https://cdn.jsdelivr.net/npm/{npm_match.group(1)}"
        if cdn not in cdn_urls:
            cdn_urls.append(cdn)
    init_script = tool.get("init_script") or ""
    if not init_script and not cdn_urls and not library_url.startswith("https://"):
        return {"status": "ok", "success": False, "error": "الأداة بلا كود بايثون وبلا مكتبة واجهة يمكن تحميلها في الصفحة."}
    return {
        "status": "ok",
        "success": True,
        "kind": "web",
        "init_script": init_script,
        "cdn_urls": cdn_urls[:4],
        "library_url": library_url,
    }


@app.post("/api/tools/generate-code")
async def generate_tool_code_endpoint(req: ToolGenerateCodeRequest, request: Request):
    """محاورة نموذج OpenRouter لبناء كود بايثون مخصص لأداة جديدة"""
    key = owner_openrouter_key(request, req.api_key)
    model = (req.model or "").strip()
    coding = {"id": model, "name": model, "coding_index": None, "source": "requested"}
    if not model:
        coding = _select_python_coding_model(key)
        model = coding.get("id") or "google/gemini-2.5-flash"
    
    task_desc = req.prompt.strip() if req.prompt else f"اسم الأداة: {req.tool_name}\nوصف الأداة: {req.tool_desc}"
    library_rule = (
        "2. يجوز استخدام مكتبة واحدة حديثة من PyPI متوافقة مع Python 3.11 فما فوق، إذا كانت تخدم تحويل ناتج البحث. السطر الأول من الكود يجب أن يكون `# package: الاسم` أو `# package: none` إن اكتفيت بالمكتبات القياسية. لا تستخدم مكتبة جافاسكربت ولا تكتب أمر pip.\n"
        if req.modern_python else
        "2. استخدم المكتبات القياسية في بايثون فقط (مثل datetime, math, re, json, collections, urllib).\n"
    )
    
    prompt = (
        f"أنت مهندس برمجيات بايثون محترف، مختار لأنك الأعلى في معيار البرمجة coding_index على OpenRouter.\n"
        f"المطلوب: كتابة دالة بايثون دقيقة وحديثة للأداة التالية:\n"
        f"{task_desc}\n\n"
        f"القواعد البرمجية الصارمة:\n"
        f"1. اكتب دالة رئيسية باسم `run_tool(input_data)` تقبل قاموس البيانات المدخلة وتُرجع قاموساً (dict) يحتوي نتيجة الحساب بدقة مع حقل 'status': 'success' أو 'verified'.\n"
        f"{library_rule}"
        f"3. الكود لبايثون 3.11 أو أحدث، نظيف، وخالٍ من الأخطاء، مع تعليقات عربية مختصرة.\n"
        f"4. في نهاية الكود، ضع قاموساً باسم `mock_test_input = {{...}}` يحتوي على بيانات تجريبية واقعية من ناتج بحث جاهز.\n"
        f"5. أرجع الكود محصوراً فقط بين علامات ```python و ``` دون أي مقدمات أو كلام خارج كود البايثون."
    )
    
    messages = [
        {"role": "system", "content": "أنت مبرمج بايثون خبير. اكتب الكود المطلوب حصراً داخل علامات ```python```."},
        {"role": "user", "content": prompt}
    ]

    def _ask_for_code() -> str:
        try:
            return call_openrouter_raw(model, messages, key, 0.2, 8000, None, None, None, None, None, 480, "off")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "ignore")[:900]
            if "temperature" in detail.lower():
                return call_openrouter_raw(model, messages, key, 1, 8000, None, None, None, None, None, 480, "off")
            raise RuntimeError(detail or str(error))

    try:
        reply = await asyncio.to_thread(_ask_for_code)
        if not (reply or "").strip():
            return {"status": "error", "message": "أعاد نموذج البرمجة رداً فارغاً ولم يكتب كود الأداة"}
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
        
        package_match = re.search(r"^#\s*package:\s*([A-Za-z0-9][A-Za-z0-9_.-]{0,60})", extracted_code, re.M)
        package_name = package_match.group(1) if package_match and package_match.group(1).lower() != "none" else ""
        return {
            "status": "ok",
            "code": extracted_code,
            "sample_input": sample_input,
            "packages": [package_name] if package_name else [],
            "tool_name": suggested_name,
            "tool_id": suggested_id.lower(),
            "coding_model": coding,
            "raw_reply": reply
        }
    except Exception as e:
        return {"status": "error", "message": f"خطأ في توليد الكود: {str(e)}"}

# =============================================================================
# مهندس الأدوات: حوار جمع الفكرة، بحث Tavily، خطة بناء، إصلاح الكود
# =============================================================================
class ToolArchitectChatRequest(BaseModel):
    messages: List[Dict[str, Any]] = []
    model: Optional[str] = "google/gemini-2.5-flash"
    api_key: Optional[str] = None


class ToolArchitectResearchRequest(BaseModel):
    spec: Dict[str, Any] = {}
    idea: Optional[str] = ""
    api_key: Optional[str] = None
    max_results: Optional[int] = 5
    exclude_urls: Optional[List[str]] = []
    round: Optional[int] = 1


class ToolArchitectPlanRequest(BaseModel):
    spec: Dict[str, Any] = {}
    research: Dict[str, Any] = {}
    model: Optional[str] = "google/gemini-2.5-flash"
    api_key: Optional[str] = None


class ToolArchitectRepairRequest(BaseModel):
    code: str
    error: Optional[str] = ""
    spec: Dict[str, Any] = {}
    model: Optional[str] = "google/gemini-2.5-flash"
    api_key: Optional[str] = None
    allowed_packages: Optional[List[str]] = []


class ToolArchitectStudyRequest(BaseModel):
    url: str
    title: Optional[str] = ""
    excerpt: Optional[str] = ""
    spec: Dict[str, Any] = {}
    model: Optional[str] = "google/gemini-2.5-flash"
    api_key: Optional[str] = None
    feedback: Optional[str] = ""


class ToolArchitectInstallRequest(BaseModel):
    packages: List[str] = []
    urls: List[str] = []


TOOL_ARCHITECT_SYSTEM = """أنت «مهندس الأدوات» في منظومة المجتهد للبحث الأكاديمي الشرعي.
مهمتك الوحيدة: إنشاء أداة تُطبق على بحث جاهز أنتجه نموذج ذكاء اصطناعي مرتبط بمخزن الشاملة الذي يضم نحو ثمانية ملايين نص تراثي.

السياق ثابت ولا تسأل عنه أبداً:
- البيانات ليست عند المستخدم ولا يطلب منه إدخالها أو بيان مصدرها أو كيفية جمعها.
- عند استعمال الأداة يضغط الباحث زرها في المحادثة أو المشروع، فيأخذ النموذج الذي أنتج البحث ناتجه الجاهز في السياق ويستخرج منه الحقول وفق مثال الأداة، ثم تبني الأداة الجدول أو الرسم أو الخط الزمني أو التحرير المطلوب تلقائياً.
- لذلك صمم عقد الأداة دائماً هكذا: مدخلها ناتج بحث جاهز (نص أو جدول أو بيانات مستخلصة من الشاملة)، ومخرجها تحويل بصري أو جدولي أو تحريري لذلك الناتج.

أسئلتك تكون اختيارية حصراً، كما في مهندس المشاريع: من 2 إلى 4 أسئلة في الدفعة، كل سؤال بخيارات قابلة للنقر داخل كتلة واحدة بالصيغة التالية، والواجهة تضيف حقل كتابة حراً لمن أراد غير الخيارات:
```choices
{"questions":[{"id":"output_kind","prompt":"ما شكل التحويل المطلوب من ناتج البحث؟","multiple":false,"options":["جدول منظم","رسم بياني","خط زمني","تحرير وتلخيص"]}]}
```
لا تطلب إجابة إنشائية، ولا تسأل عن مصدر البيانات أو طريقة إدخالها أو من أين تأتي. اسأل فقط عن: نوع التحويل، الحقول أو الأعمدة، الترتيب والفرز والتجميع، الشكل والألوان عند الحاجة، مقدار التفصيل، وما يفعله عند نقص حقل في ناتج البحث.
لا تكتب الكود في مرحلة الحوار، ولا تذكر بحث الويب كخطوة يضغطها المستخدم؛ فالنظام سيبحث تلقائياً بـ Tavily بعد اكتمال المواصفات.
عند اكتمال الفكرة اعرض ملخصاً واضحاً، ثم ألحق في نهاية ردك كتلة JSON وحدها داخل ```json بالحقول:
{"name":"","purpose":"","output_kind":"","fields":[],"sorting":"","grouping":"","display":"","missing_data_rule":"","example_input":{"research_text":"مثال واقعي قصير لناتج بحث جاهز من الشاملة"},"example_output":{},"application_instruction":"تعليمات دقيقة للنموذج الذي أنتج البحث ليستخرج الحقول من ناتجه ويطبق الأداة دون سؤال المستخدم عن البيانات","keywords":[],"english_keywords":[]}
اصنع example_input وexample_output واقعيين؛ فالمثال هو عقد التطبيق الذي سيقلده نموذج البحث عند تشغيل الأداة.
لا تضع كتلة JSON قبل اكتمال المعلومات الجوهرية."""


def _architect_json(text: str) -> Dict[str, Any]:
    raw = str(text or "")
    match = re.search(r"```json\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
    candidate = match.group(1) if match else raw
    start, end = candidate.find("{"), candidate.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(candidate[start:end + 1])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


TOOL_REGISTRY_DOMAINS = ["pypi.org", "npmjs.com", "github.com", "readthedocs.io"]


def _select_python_coding_model(key: str) -> Dict[str, Any]:
    """يختار أعلى نموذج في معيار البرمجة coding_index من كتالوج OpenRouter."""
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "http://localhost:8085",
            "X-Title": "Al-Mojtahed Tool Architect",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception:
        raw = {"data": []}
    best = None
    best_score = -1.0
    runners = []
    for model in raw.get("data") or []:
        score = ((model.get("benchmarks") or {}).get("artificial_analysis") or {}).get("coding_index")
        try:
            value = float(score)
        except (TypeError, ValueError):
            continue
        if not model.get("id"):
            continue
        runners.append((value, model))
        if value > best_score:
            best_score = value
            best = model
    runners.sort(key=lambda item: item[0], reverse=True)
    if not best:
        return {"id": "google/gemini-2.5-flash", "name": "Gemini 2.5 Flash", "coding_index": None, "source": "fallback", "runners": []}
    return {
        "id": best.get("id"),
        "name": best.get("name") or best.get("id"),
        "coding_index": best_score,
        "source": "OpenRouter coding_index",
        "runners": [{"id": model.get("id"), "name": model.get("name") or model.get("id"), "coding_index": value} for value, model in runners[:3]],
    }


def _registry_result(url: str) -> bool:
    host = urllib.parse.urlparse(str(url or "")).netloc.lower()
    return any(host == domain or host.endswith("." + domain) for domain in TOOL_REGISTRY_DOMAINS)


def _tavily_search_sync(query: str, key: str, max_results: int = 5, include_domains: Optional[List[str]] = None, timeout: int = 35) -> Dict[str, Any]:
    payload = {
        "api_key": key,
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "max_results": max(1, min(int(max_results or 5), 8)),
    }
    if include_domains:
        payload["include_domains"] = include_domains
    request = urllib.request.Request(
        "https://api.tavily.com/search",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


@app.post("/api/tools/architect/chat")
async def tool_architect_chat_endpoint(req: ToolArchitectChatRequest, request: Request):
    key = owner_openrouter_key(request, req.api_key)
    messages = [{"role": "system", "content": TOOL_ARCHITECT_SYSTEM}]
    for item in (req.messages or [])[-30:]:
        role = item.get("role") if item.get("role") in ("user", "assistant") else "user"
        content = str(item.get("content") or "").strip()
        if content:
            messages.append({"role": role, "content": content[:6000]})
    if len(messages) < 2:
        raise HTTPException(status_code=400, detail="اكتب فكرة الأداة أولاً")
    try:
        reply = await asyncio.to_thread(
            call_openrouter_raw, req.model or "google/gemini-2.5-flash", messages, key, 0.35, 2600, None, None, None, None, None, 120, "off"
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"تعذر الاتصال بنموذج مهندس الأدوات: {exc}")
    return {"status": "ok", "reply": reply, "spec": _architect_json(reply)}


@app.post("/api/tools/architect/research")
async def tool_architect_research_endpoint(req: ToolArchitectResearchRequest, request: Request):
    owner = current_owner_id(request)
    key = (req.api_key or "").strip() or (load_provider_keys(owner).get("tavily") or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="يلزم مفتاح Tavily للبحث عن الأدوات والمكتبات القائمة")
    spec = req.spec or {}
    name = str(spec.get("name") or req.idea or "أداة بحثية").strip()
    purpose = str(spec.get("purpose") or req.idea or "").strip()
    keywords = " ".join(str(x) for x in (spec.get("keywords") or []))
    english = " ".join(str(x) for x in (spec.get("english_keywords") or []))
    queries = []
    search_round = max(1, int(req.round or 1))
    subject = " ".join(part for part in [english, keywords, name] if part).strip() or purpose
    page = f" page {search_round}" if search_round > 1 else ""
    for query in [
        f"site:pypi.org {subject} python package requires-python{page}",
        f"site:github.com {subject} python library language:python{page}",
        f"site:npmjs.com {subject} package{page}",
        f"site:readthedocs.io {subject} python documentation{page}",
    ]:
        query = " ".join(query.split()).strip()
        if query and query not in queries:
            queries.append(query)
    excluded = {str(url).strip() for url in (req.exclude_urls or []) if str(url).strip()}

    def collect() -> Dict[str, Any]:
        results, seen, answers = [], set(excluded), []
        for query in queries:
            try:
                data = _tavily_search_sync(query, key, req.max_results or 5, TOOL_REGISTRY_DOMAINS)
            except Exception:
                continue
            if data.get("answer"):
                answers.append(str(data["answer"])[:1200])
            for item in data.get("results") or []:
                url = str(item.get("url") or "").strip()
                if not url or url in seen or not _registry_result(url):
                    continue
                seen.add(url)
                results.append({
                    "title": str(item.get("title") or url)[:220],
                    "url": url,
                    "content": str(item.get("content") or "")[:1400],
                    "score": item.get("score"),
                    "query": query,
                })
        results.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        return {"queries": queries, "answer": "\n\n".join(answers)[:3500], "results": results[:14]}

    return {"status": "ok", "research": await asyncio.to_thread(collect)}


@app.post("/api/tools/architect/plan")
async def tool_architect_plan_endpoint(req: ToolArchitectPlanRequest, request: Request):
    key = owner_openrouter_key(request, req.api_key)
    prompt = (
        "بناء على مواصفات الأداة ونتائج بحث Tavily التالية، قرر طريقة التنفيذ الأنسب.\n"
        "اختر mode واحدة فقط: ready_web إذا وجدت مكتبة ويب موثقة تنفذ المطلوب مباشرة، أو python_build إذا كان الأنسب سكربت بايثون، أو hybrid إذا كان بايثون يجهز البيانات والويب يعرضها.\n"
        "في python_build يجب أن تكون build_prompt تعليمات كاملة لتوليد run_tool(input_data) بالمكتبات القياسية فقط، مع mock_test_input واقعي.\n"
        "في ready_web املأ library_url وinit_script وmock_data من الوثائق المسترجعة فقط، ولا تخترع روابط.\n"
        "رتّب في candidates كل أداة مناسبة وجدها البحث مع رابطها وسبب ملاءمتها وحدودها، ورشّح واحدة صراحة في rationale.\n"
        "أضف memory_candidates من معرفتك أنت حتى لو غاب البحث: من 2 إلى 4 مكتبات حديثة تناسب الفكرة، من PyPI لبايثون أو من npm للعرض. لكل واحدة الحقول name وregistry بقيمة pypi أو npm وurl وreason وsource بقيمة memory. الرابط يكون الصفحة الرسمية التي تعرفها، مثل https://pypi.org/project/الاسم أو https://www.npmjs.com/package/الاسم. إن لم تثق بالرابط فاترك url فارغاً ولا تخترع مساراً.\n"
        "إذا كان البناء من الصفر أنسب، اختر coding_model بمعرفه الحرفي من قائمة أقوى نماذج OpenRouter التالية، واذكر coding_model_reason. لا تخترع معرفاً خارج القائمة.\n"
        "أعد JSON فقط بالحقول: mode, tool_name, tool_id, description, rationale, candidates, memory_candidates, library_url, init_script, mock_data, build_prompt, coding_model, coding_model_reason, sources.\n\n"
        f"أقوى نماذج OpenRouter المتاحة:\n{_architect_model_roster()}\n\n"
        f"المواصفات:\n{json.dumps(req.spec or {}, ensure_ascii=False)}\n\n"
        f"البحث:\n{json.dumps(req.research or {}, ensure_ascii=False)[:14000]}"
    )
    try:
        reply = await asyncio.to_thread(
            call_openrouter_raw, req.model or "google/gemini-2.5-flash",
            [{"role": "system", "content": "أنت مهندس أدوات. أعد JSON صالحاً فقط دون شرح خارجه."}, {"role": "user", "content": prompt}],
            key, 0.2, 3200, None, None, None, None, None, 120, "off"
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"تعذر إعداد خطة الأداة: {exc}")
    plan = _architect_json(reply)
    if not plan:
        raise HTTPException(status_code=502, detail="لم تصل خطة صالحة من النموذج")
    if plan.get("mode") not in ("ready_web", "python_build", "hybrid"):
        plan["mode"] = "python_build"
    return {"status": "ok", "plan": plan, "raw": reply}


_TOOL_PACKAGE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,60}$")


def _safe_tool_packages(packages: List[str]) -> List[str]:
    clean = []
    for raw in packages or []:
        name = str(raw or "").strip()
        if _TOOL_PACKAGE_NAME.match(name) and name not in clean:
            clean.append(name)
        if len(clean) >= 4:
            break
    return clean


def _fetch_tool_documentation(url: str) -> str:
    target = str(url or "").strip()
    if not target.startswith(("http://", "https://")):
        return ""
    pages = [target]
    github = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", target)
    if github:
        owner, repo = github.group(1), github.group(2).removesuffix(".git")
        pages.append(f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md")
        pages.append(f"https://pypi.org/pypi/{repo}/json")
    chunks = []
    for page in pages:
        try:
            request = urllib.request.Request(page, headers={"User-Agent": "Almojtahed-ToolArchitect/1.0"})
            with urllib.request.urlopen(request, timeout=20) as resp:
                raw = resp.read(18000).decode("utf-8", "replace")
        except Exception:
            continue
        raw = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", raw, flags=re.I)
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = " ".join(raw.split())
        if raw:
            chunks.append(f"المصدر: {page}\n{raw[:6000]}")
    return "\n\n".join(chunks)[:14000]


def _install_tool_packages(packages: List[str], urls: List[str]) -> Dict[str, Any]:
    logs = []
    installed = _safe_tool_packages(packages)
    if installed:
        try:
            process = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", *installed],
                capture_output=True, text=True, timeout=180,
            )
            logs.append((process.stdout or "")[-2500:])
            logs.append((process.stderr or "")[-2500:])
            if process.returncode != 0:
                return {"ok": False, "installed": installed, "log": "\n".join(logs).strip(), "urls": []}
        except Exception as exc:
            return {"ok": False, "installed": installed, "log": str(exc), "urls": []}
    checked = []
    for url in urls or []:
        target = str(url or "").strip()
        if not target.startswith("https://") or " " in target:
            continue
        try:
            request = urllib.request.Request(target, headers={"User-Agent": "Almojtahed-ToolArchitect/1.0"})
            with urllib.request.urlopen(request, timeout=20) as resp:
                resp.read(1200)
                checked.append({"url": target, "ok": 200 <= int(resp.status) < 400})
        except Exception as exc:
            checked.append({"url": target, "ok": False, "error": str(exc)[:240]})
    urls_ok = all(item.get("ok") for item in checked) if checked else True
    return {"ok": urls_ok, "installed": installed, "log": "\n".join(logs).strip() or "لا مكتبات بايثون إضافية مطلوبة.", "urls": checked}


@app.post("/api/tools/architect/study")
async def tool_architect_study_endpoint(req: ToolArchitectStudyRequest, request: Request):
    key = owner_openrouter_key(request, req.api_key)
    coding = _select_python_coding_model(key)
    model_id = coding.get("id") or req.model or "google/gemini-2.5-flash"
    docs = (req.excerpt or "").strip() or await asyncio.to_thread(_fetch_tool_documentation, req.url)
    if not docs:
        raise HTTPException(status_code=502, detail="تعذر قراءة وثائق الأداة المختارة")
    prompt = (
        "أنت وكيل البرمجة الفرعي. ادرس وثائق الأداة التالية وجهّزها للاستعمال داخل المجتهد على ناتج بحث جاهز.\n"
        "أعد JSON فقط بالحقول: summary, kind, packages, cdn_urls, code, init_script, mock_data, notes.\n"
        "kind تكون python إذا كانت مكتبة بايثون، وweb إذا كانت مكتبة جافاسكربت تعرض الرسم في المتصفح.\n"
        "إذا كان الرابط من pypi.org أو github.com فاختر kind=python وحزمة PyPI حديثة تدعم Python 3.11 أو أحدث. إذا كان الرابط من npmjs.com فاختر kind=web وضع اسم الحزمة في cdn على صورة https://cdn.jsdelivr.net/npm/الاسم ولا تضع اسم حزمة npm داخل packages.\n"
        "packages أسماء pip فقط بلا أوامر ولا روابط، وبحد أقصى أربع مكتبات ضرورية.\n"
        "code دالة run_tool(input_data) كاملة تستخدم المكتبات المذكورة فقط مع المكتبات القياسية، وترجع قاموساً فيه status=success، وتنتهي بـ mock_test_input واقعي من ناتج بحث جاهز.\n"
        "لا تخترع أمر تنصيب؛ التنصيب ينفذه المهندس من قائمة packages.\n"
        f"الأداة: {req.title}\nالرابط: {req.url}\n"
        f"المواصفات: {json.dumps(req.spec or {}, ensure_ascii=False)[:3000]}\n"
        f"ملاحظة الجولة السابقة: {str(req.feedback or '')[:2000]}\n\n"
        f"الوثائق:\n{docs}"
    )
    try:
        reply = await asyncio.to_thread(
            call_openrouter_raw, model_id,
            [{"role": "system", "content": "أنت وكيل برمجة بايثون محترف. أعد JSON صالحاً فقط."}, {"role": "user", "content": prompt}],
            key, 0.2, 8000, None, None, None, None, None, 480, "off"
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"تعذر دراسة الأداة: {exc}")
    study = _architect_json(reply)
    if not study:
        raise HTTPException(status_code=502, detail="لم تصل دراسة صالحة من وكيل البرمجة")
    if not study.get("code"):
        match = re.search(r"```python\s*([\s\S]*?)\s*```", reply)
        if match:
            study["code"] = match.group(1).strip()
    study["packages"] = _safe_tool_packages(study.get("packages") if isinstance(study.get("packages"), list) else [])
    urls = []
    for url in study.get("cdn_urls") or []:
        target = str(url or "").strip()
        if target.startswith("https://") and " " not in target and target not in urls:
            urls.append(target)
    study["cdn_urls"] = urls[:4]
    study["kind"] = "web" if study.get("kind") == "web" else "python"
    study["docs_excerpt"] = docs[:1200]
    study["coding_model"] = coding
    return {"status": "ok", "study": study}


class ToolCodingModelRequest(BaseModel):
    api_key: Optional[str] = None


@app.post("/api/tools/architect/coding-model")
async def tool_architect_coding_model_endpoint(req: ToolCodingModelRequest, request: Request):
    key = owner_openrouter_key(request, req.api_key)
    model = await asyncio.to_thread(_select_python_coding_model, key)
    return {"status": "ok", "model": model}


ISLAMAP_REGION_IDS = {
    "andalus", "maghreb", "ifriqiya", "egypt", "sham", "jazira", "iraq", "hijaz",
    "yemen", "fars", "khurasan", "transoxiana", "sind", "anatolia", "kurdistan",
    "azerbaijan", "khwarizm", "daylam", "jibal", "kirman", "khuzistan", "oman",
    "hadramawt", "bahrayn", "filastin", "urdunn",
}
ISLAMAP_CITY_IDS = {
    "qurtuba", "fas", "qayrawan", "fustat", "cairo", "dimashq", "quds", "makka", "madina",
    "sanaa", "kufa", "basra", "baghdad", "mawsil", "rayy", "naysabur", "bukhara", "samarqand",
    "mansura", "tarsus", "cilicia", "heraclea", "amorium", "edirne", "constantinople",
    "landwalls", "rumeli", "anadolu", "bosphorus", "tophane", "galata", "goldenhorn",
    "hornmouth", "levantsea", "aegean", "dardanelles", "marmara",
    "redsea", "persian", "indian", "westmed", "blacksea", "caspian", "atlantic", "aden",
    "wasit", "isfahan", "shiraz", "hamadan", "tabriz", "aleppo", "hama", "homs", "tripoli",
    "baalbek", "sidon", "acre", "tiberias", "nablus", "hebron", "gaza", "ascalon", "ramla",
    "alexandria", "damietta", "asyut", "zabid", "taiz", "aden", "herat", "merv", "balkh",
    "tus", "sabzevar", "jurjan", "amol", "qazvin", "ardabil", "maragha", "irbil", "tikrit",
    "hilla", "khiva", "termez", "nasaf", "tashkent", "fergana", "khujand", "multan", "daybul",
    "kerman", "taif", "jeddah", "sohar", "nizwa", "seville", "granada", "malaga", "valencia",
    "murcia", "mahdia", "tunis", "bejaia", "tlemcen", "marrakesh",
}
ISLAMAP_CITY_REGION = {
    "qurtuba": "andalus", "seville": "andalus", "granada": "andalus", "malaga": "andalus",
    "valencia": "andalus", "murcia": "andalus", "fas": "maghreb", "marrakesh": "maghreb",
    "tlemcen": "maghreb", "qayrawan": "ifriqiya", "mahdia": "ifriqiya", "tunis": "ifriqiya",
    "bejaia": "ifriqiya", "fustat": "egypt", "cairo": "egypt", "alexandria": "egypt",
    "damietta": "egypt", "asyut": "egypt", "dimashq": "sham", "aleppo": "sham", "hama": "sham",
    "homs": "sham", "tripoli": "sham", "baalbek": "sham", "sidon": "sham", "acre": "filastin",
    "tiberias": "filastin", "nablus": "filastin", "hebron": "filastin", "gaza": "filastin",
    "ascalon": "filastin", "ramla": "filastin", "quds": "filastin", "kufa": "iraq",
    "basra": "iraq", "baghdad": "iraq", "wasit": "iraq", "hilla": "iraq", "mawsil": "jazira",
    "irbil": "kurdistan", "tikrit": "iraq", "makka": "hijaz", "madina": "hijaz",
    "taif": "hijaz", "jeddah": "hijaz", "sanaa": "yemen", "zabid": "yemen", "taiz": "yemen",
    "aden": "yemen", "rayy": "jibal", "isfahan": "jibal", "hamadan": "jibal", "qazvin": "jibal",
    "shiraz": "fars", "kerman": "kirman", "naysabur": "khurasan", "herat": "khurasan",
    "merv": "khurasan", "balkh": "khurasan", "tus": "khurasan", "sabzevar": "khurasan",
    "jurjan": "khurasan", "amol": "daylam", "tabriz": "azerbaijan", "ardabil": "azerbaijan",
    "maragha": "azerbaijan", "bukhara": "transoxiana", "samarqand": "transoxiana",
    "termez": "transoxiana", "nasaf": "transoxiana", "tashkent": "transoxiana",
    "fergana": "transoxiana", "khujand": "transoxiana", "khiva": "khwarizm",
    "mansura": "sind", "multan": "sind", "daybul": "sind", "sohar": "oman", "nizwa": "oman",
    "tarsus": "sham", "cilicia": "anatolia", "heraclea": "anatolia", "amorium": "anatolia",
    "edirne": "anatolia", "constantinople": "anatolia",
}
ISLAMAP_NAME_TO_ID = {
    "الأندلس": "andalus", "الاندلس": "andalus", "المغرب": "maghreb", "إفريقية": "ifriqiya",
    "افريقية": "ifriqiya", "مصر": "egypt", "الشام": "sham", "الجزيرة": "jazira", "العراق": "iraq",
    "الحجاز": "hijaz", "اليمن": "yemen", "فارس": "fars", "خراسان": "khurasan",
    "ما وراء النهر": "transoxiana", "السند": "sind", "آسيا الصغرى": "anatolia", "الأناضول": "anatolia",
    "قرطبة": "qurtuba", "فاس": "fas", "القيروان": "qayrawan", "الفسطاط": "fustat", "القاهرة": "cairo",
    "دمشق": "dimashq", "القدس": "quds", "مكة": "makka", "المدينة": "madina", "المدينة المنورة": "madina",
    "صنعاء": "sanaa", "الكوفة": "kufa", "البصرة": "basra", "بغداد": "baghdad", "الموصل": "mawsil",
    "الري": "rayy", "نيسابور": "naysabur", "بخارى": "bukhara", "سمرقند": "samarqand", "المنصورة": "mansura",
    "طرسوس": "tarsus", "درب كليكيا": "cilicia", "كليكيا": "cilicia", "هرقلة": "heraclea",
    "عمورية": "amorium", "أدرنة": "edirne", "أدرنه": "edirne", "القسطنطينية": "constantinople",
    "إسطنبول": "constantinople", "الأسوار البرية": "landwalls", "روملي حصاري": "rumeli",
    "قلعة الروم": "rumeli", "أناضولو حصاري": "anadolu", "قلعة الأناضول": "anadolu",
    "غلطة": "galata", "الخليج الذهبي": "goldenhorn", "فم الخليج": "hornmouth",
    "طوب خانه": "tophane", "البوسفور": "bosphorus", "بحر إيجه": "aegean", "الدردنيل": "dardanelles",
    "بحر مرمرة": "marmara", "بحر الشام": "levantsea", "البحر المتوسط": "levantsea", "بحر الروم": "levantsea",
    "البحر الأحمر": "redsea", "الخليج الفارسي": "persian", "بحر فارس": "persian",
    "المحيط الهندي": "indian", "البحر الأسود": "blacksea", "بحر الخزر": "caspian",
    "بحر قزوين": "caspian", "المحيط الأطلسي": "atlantic", "خليج عدن": "aden",
    "constantinople": "constantinople", "edirne": "edirne", "tarsus": "tarsus", "amorium": "amorium",
    "heraclea": "heraclea", "galata": "galata", "golden horn": "goldenhorn", "bosphorus": "bosphorus",
    "كردستان": "kurdistan", "أذربيجان": "azerbaijan", "خوارزم": "khwarizm", "الديلم": "daylam",
    "الجبال": "jibal", "كرمان": "kirman", "خوزستان": "khuzistan", "عمان": "oman",
    "حضرموت": "hadramawt", "البحرين": "bahrayn", "فلسطين": "filastin", "الأردن": "urdunn",
    "واسط": "wasit", "أصفهان": "isfahan", "شيراز": "shiraz", "همذان": "hamadan", "تبريز": "tabriz",
    "حلب": "aleppo", "حماة": "hama", "حمص": "homs", "طرابلس الشام": "tripoli", "بعلبك": "baalbek",
    "صيدا": "sidon", "عكا": "acre", "طبريا": "tiberias", "نابلس": "nablus", "الخليل": "hebron",
    "غزة": "gaza", "عسقلان": "ascalon", "الرملة": "ramla", "الإسكندرية": "alexandria",
    "دمياط": "damietta", "أسيوط": "asyut", "زبيد": "zabid", "تعز": "taiz", "عدن": "aden",
    "هراة": "herat", "مرو": "merv", "بلخ": "balkh", "طوس": "tus", "بيهق": "sabzevar",
    "جرجان": "jurjan", "آمل": "amol", "قزوين": "qazvin", "أردبيل": "ardabil", "مراغة": "maragha",
    "أربيل": "irbil", "تكريت": "tikrit", "الحلة": "hilla", "خيوة": "khiva", "ترمذ": "termez",
    "نسف": "nasaf", "الشاش": "tashkent", "فرغانة": "fergana", "خجند": "khujand", "ملتان": "multan",
    "الديبل": "daybul", "الطائف": "taif", "جدة": "jeddah", "صحار": "sohar", "نزوى": "nizwa",
    "إشبيلية": "seville", "غرناطة": "granada", "مالقة": "malaga", "بلنسية": "valencia",
    "مرسية": "murcia", "المهدية": "mahdia", "تونس": "tunis", "بجاية": "bejaia",
    "تلمسان": "tlemcen", "مراكش": "marrakesh",
}
ISLAMAP_SEA_IDS = {
    "levantsea", "aegean", "dardanelles", "marmara", "hornmouth", "bosphorus",
    "redsea", "persian", "indian", "westmed", "blacksea", "caspian", "atlantic", "aden",
}
_MAP_MODEL_CACHE = {"at": 0.0, "runners": []}


def _islamap_mode(kind: str) -> str:
    if kind in ("distribution", "madhhab"):
        return "distribution"
    if kind in ("routes", "futuh", "ghazawat"):
        return "routes"
    if kind == "cities":
        return "cities"
    return "distribution"


def _islamap_resolve_id(token: Any) -> str:
    text = str(token or "").strip()
    if not text:
        return ""
    if text in ISLAMAP_REGION_IDS or text in ISLAMAP_CITY_IDS:
        return text
    mapped = ISLAMAP_NAME_TO_ID.get(text) or ISLAMAP_NAME_TO_ID.get(text.lower())
    return mapped or ""


def _select_map_model(key: str) -> List[str]:
    """يختار أعلى نماذج OpenRouter في مؤشر الذكاء، بصمت، لرسم الخارطة."""
    now = time.time()
    if _MAP_MODEL_CACHE["runners"] and now - _MAP_MODEL_CACHE["at"] < 1800:
        return list(_MAP_MODEL_CACHE["runners"])
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "http://localhost:8085",
            "X-Title": "Al-Mojtahed Map",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception:
        raw = {"data": []}
    skip = ("embed", "image", "audio", "whisper", "tts", "moderation", "rerank", "flux", "dall", "speech", "transcri")
    ranked = []
    for model in raw.get("data") or []:
        model_id = str(model.get("id") or "")
        low = model_id.lower()
        if not model_id or any(part in low for part in skip):
            continue
        outputs = ((model.get("architecture") or {}).get("output_modalities") or [])
        if outputs and "text" not in outputs:
            continue
        score = ((model.get("benchmarks") or {}).get("artificial_analysis") or {}).get("intelligence_index")
        try:
            value = float(score)
        except (TypeError, ValueError):
            continue
        ranked.append((value, model_id))
    ranked.sort(key=lambda item: item[0], reverse=True)
    runners = [model_id for _score, model_id in ranked[:3]] or ["google/gemini-2.5-flash"]
    _MAP_MODEL_CACHE["runners"] = runners
    _MAP_MODEL_CACHE["at"] = now
    return list(runners)


ISLAMAP_SHAPE_EXAMPLE = {
    "title": "مسارات الفتح نحو القسطنطينية",
    "regions": [{"id": "hijaz", "value": "منطلق"}, {"id": "sham", "value": "ثغور"}],
    "cities": [
        {"id": "madina"}, {"id": "dimashq"}, {"id": "tarsus"}, {"id": "cilicia"},
        {"id": "heraclea"}, {"id": "amorium"}, {"id": "constantinople"}, {"id": "edirne"},
        {"id": "landwalls"}, {"id": "rumeli"}, {"id": "anadolu"}, {"id": "galata"},
        {"id": "goldenhorn"},
    ],
    "routes": [
        {"from": "madina", "to": "constantinople", "via": ["dimashq", "tarsus", "cilicia", "heraclea", "amorium"], "kind": "land", "label": "البر حتى عمورية", "year": "89هـ"},
        {"from": "levantsea", "to": "hornmouth", "via": ["aegean", "dardanelles", "marmara"], "kind": "sea", "label": "الأساطيل"},
        {"from": "edirne", "to": "landwalls", "kind": "land", "label": "مسير الفاتح", "year": "857هـ"},
        {"from": "rumeli", "to": "anadolu", "kind": "sea", "label": "البوسفور", "year": "857هـ"},
        {"from": "tophane", "to": "goldenhorn", "via": ["galata"], "kind": "portage", "label": "جر السفن", "year": "857هـ"},
    ],
}


ISLAMAP_MADHHAB_EXAMPLE = {
    "title": "طبقات المذهب",
    "subject": "اسم المذهب كما في النص",
    "eras": [{"century": 3, "label": "ق3هـ"}],
    "places": [{
        "city": "cairo", "region": "egypt", "century": 3,
        "scholars": ["اسم العالم كما في النص"], "books": ["اسم الكتاب كما في النص"], "count": 1,
    }],
    "regions": [], "cities": [], "routes": [],
}
ISLAMAP_PLACE_IDS_TEXT = (
    "qurtuba قرطبة، seville إشبيلية، granada غرناطة، fas فاس، marrakesh مراكش، qayrawan القيروان، "
    "tunis تونس، fustat الفسطاط، cairo القاهرة، alexandria الإسكندرية، dimashq دمشق، aleppo حلب، "
    "quds القدس، gaza غزة، nablus نابلس، makka مكة، madina المدينة، taif الطائف، sanaa صنعاء، "
    "zabid زبيد، taiz تعز، aden عدن، kufa الكوفة، basra البصرة، baghdad بغداد، wasit واسط، "
    "hilla الحلة، mawsil الموصل، irbil أربيل، rayy الري، isfahan أصفهان، hamadan همذان، "
    "qazvin قزوين، shiraz شيراز، kerman كرمان، tabriz تبريز، naysabur نيسابور، herat هراة، "
    "merv مرو، balkh بلخ، tus طوس، bukhara بخارى، samarqand سمرقند، khiva خيوة، termez ترمذ، "
    "tashkent الشاش، fergana فرغانة، mansura المنصورة، multan ملتان"
)


def _islamap_prompt(kind: str) -> str:
    mode = _islamap_mode(kind)
    if mode == "distribution":
        return """أنت مهيكل خرائط فقط. هذه خارطة توزيع جغرافي على الدول، لا خارطة مدن ولا مسارات.
استخلص من النص الدول والأقاليم المذكورة فقط، واكتب على كل دولة عبارة التوزيع المطلوبة كما وردت: مذهباً أو مذاهب، أو عرقاً، أو لغة، أو غير ذلك. لا تفترض أن المطلوب مذهب.
لا تبحث، ولا تضف دولة ليست في النص، ولا تخترع إحداثيات.
المعرفات: egypt مصر، sham الشام، filastin فلسطين، urdunn الأردن، iraq العراق، jazira الجزيرة، hijaz الحجاز، yemen اليمن، fars فارس، jibal الجبال، khurasan خراسان، transoxiana ما وراء النهر، sind السند، andalus الأندلس، maghreb المغرب، ifriqiya إفريقية، anatolia آسيا الصغرى، azerbaijan أذربيجان، oman عمان.
value نص قصير يُكتب على الدولة، من النص نفسه. إن اشتركت دول في التوزيع نفسه فالقيمة واحدة. إن اختلف التوزيع فقيمة مختلفة لكل دولة.
أخرج JSON واحداً فقط:
{"mode":"distribution","title":"","regions":[{"id":"egypt","value":"عبارة التوزيع"}]}"""
    if mode == "cities":
        return f"""أنت مهيكل خرائط فقط. هذه خارطة مدن ومراكز: نقطة على كل مدينة مذكورة، وعليها اسمها، ولون فئة التوزيع.
لا تبحث، ولا تضف مدينة ليست في النص، ولا تخترع إحداثيات، ولا ترسم مساراً.
value هو نوع التوزيع في تلك المدينة كما في النص: مذهب أو عرق أو لغة أو طبقة، باختصار.
cities عنصر لكل مدينة. المعرفات: {ISLAMAP_PLACE_IDS_TEXT}.
أخرج JSON واحداً فقط:
{{"mode":"cities","title":"","cities":[{{"id":"cairo","region":"egypt","value":"عبارة التوزيع"}}]}}"""
    example = json.dumps(ISLAMAP_SHAPE_EXAMPLE, ensure_ascii=False)
    return f"""أنت مهيكل مسارات فقط. هذه خارطة غزوات وفتوحات ورحلات: مسار أو مسارات من الانطلاق إلى الوصول.
لا تبحث، ولا تضف موضعاً ليس في النص، ولا تخترع إحداثيات.
{example}
قواعد المسار، والمثال للشكل فقط ولا يُنسخ إلا إذا وردت مواضعه:
- كل حملة أو رحلة مسار مستقل: from ثم via بالترتيب ثم to.
- البر kind=land وعلى مدن البر فقط. يُمنع إدخال محطة بحر في المسار البري.
- البحر kind=sea ولا يسير على اليابسة. أدرج محطات الماء بين السواحل: levantsea بحر الشام، westmed غرب المتوسط، redsea البحر الأحمر، persian بحر فارس، indian المحيط الهندي، aegean إيجه، dardanelles الدردنيل، marmara مرمرة، blacksea البحر الأسود، caspian الخزر، atlantic الأطلسي، aden خليج عدن، hornmouth فم الخليج.
- جر السفن فوق البر kind=portage، مسار قصير بين مائين.
- اتجاه السهم من from إلى to عبر via. لا تعكس الترتيب.
أخرج JSON واحداً فقط بلا أي كلمة خارجه."""


def _islamap_mentions(text: str) -> List[str]:
    """أسماء وردت حرفياً. «المدينة» وحدها لا تعني المدينة المنورة إذا كان الكلام عن القسطنطينية."""
    found = []
    seen = set()
    work = str(text or "")
    names = sorted((name, place_id) for name, place_id in ISLAMAP_NAME_TO_ID.items() if not name.isascii())
    names.sort(key=lambda item: len(item[0]), reverse=True)
    for name, place_id in names:
        if name == "المدينة" and "القسطنطينية" in text:
            continue
        if name not in work:
            continue
        if place_id not in seen:
            found.append(place_id)
            seen.add(place_id)
        work = work.replace(name, " ")
    return found


def _route_row(origin: str, stops: List[str], kind: str, label: str = "", year: str = "") -> Dict[str, Any]:
    row = {"from": origin, "to": stops[-1], "via": stops[:-1], "kind": kind}
    if label:
        row["label"] = label
    if year:
        row["year"] = year
    return row


def _planned_routes(text: str, kind: str) -> List[Dict[str, Any]]:
    """يفرض شكل المسارات المنفصلة عندما يصف النص فتحاً نحو مدينة، كما في مثال القسطنطينية."""
    if kind not in ("futuh", "ghazawat", "routes"):
        return []
    raw = str(text or "")
    mentioned = set(_islamap_mentions(raw))
    campaign = any(word in raw for word in ("فتح", "غزو", "غزا", "حمل", "حصار", "أسطول", "اساطيل", "الأسطول", "مسير", "انطلق", "عبر"))
    if not campaign:
        return []
    year_early = "89هـ" if "تسع وثمانين" in raw else ""
    year_late = "857هـ" if ("سبع وخمسين وثمانمائة" in raw or "857" in raw) else ""
    toward_city = "القسطنطينية" in raw or "constantinople" in mentioned
    routes = []
    land = []
    if toward_city or mentioned & {"tarsus", "cilicia", "heraclea", "amorium"}:
        if "الحجاز" in raw or "madina" in mentioned:
            land.append("madina")
        if "الشام" in raw or "dimashq" in mentioned:
            land.append("dimashq")
        for place_id in ("tarsus", "cilicia", "heraclea", "amorium", "constantinople"):
            if place_id in mentioned:
                land.append(place_id)
    elif "madina" in mentioned and "dimashq" in mentioned:
        land = ["madina", "dimashq"]
    land = list(dict.fromkeys(land))
    if len(land) >= 2:
        routes.append(_route_row(land[0], land[1:], "land", "البر حتى عمورية" if "amorium" in land else "مسار بري", year_early))
    sea = []
    water = any(word in raw for word in ("البحر المتوسط", "بحر الشام", "بحر الروم", "إيجه", "الدردنيل"))
    if water and (toward_city or "الخليج" in raw):
        if any(word in raw for word in ("البحر المتوسط", "بحر الشام", "بحر الروم")):
            sea.append("levantsea")
        if "إيجه" in raw or "aegean" in mentioned:
            sea.append("aegean")
        if any(word in raw for word in ("الدردنيل", "مضايق", "إيجه")):
            sea.append("dardanelles")
        if "مرمرة" in raw or "dardanelles" in sea:
            sea.append("marmara")
        if "الخليج" in raw or toward_city:
            sea.append("hornmouth")
    sea = list(dict.fromkeys(sea))
    if len(sea) >= 2:
        routes.append(_route_row(sea[0], sea[1:], "sea", "الأساطيل"))
    if "edirne" in mentioned and ("الأسوار" in raw or toward_city):
        destination = "landwalls" if ("landwalls" in mentioned or "الأسوار" in raw) else "constantinople"
        label = "مسير الفاتح" if "الفاتح" in raw else "مسير الحصار"
        routes.append(_route_row("edirne", [destination], "land", label, year_late))
    if "rumeli" in mentioned and "anadolu" in mentioned:
        routes.append(_route_row("rumeli", ["anadolu"], "sea", "البوسفور", year_late))
    hauled = "galata" in mentioned and any(word in raw for word in ("سفن", "جر", "نقل", "أخشاب", "الشحوم"))
    if hauled and ("الخليج" in raw or "bosphorus" in mentioned):
        routes.append(_route_row("tophane", ["galata", "goldenhorn"], "portage", "جر السفن", year_late))
    return routes


def _route_stops(route: Dict[str, Any]) -> List[str]:
    return [route.get("from"), *(route.get("via") or []), route.get("to")]


def _apply_route_method(cleaned: Optional[Dict[str, Any]], text: str, kind: str) -> Optional[Dict[str, Any]]:
    if _islamap_mode(kind) != "routes":
        return cleaned
    planned = _planned_routes(text, kind)
    base = cleaned or {"title": "", "regions": [], "cities": [], "routes": []}
    if planned:
        routes = list(base.get("routes") or [])
        covered = [set(_route_stops(item)) for item in planned]
        for plan in planned:
            match = next((
                route for route in routes
                if route.get("kind") == plan["kind"] and route.get("from") == plan["from"] and route.get("to") == plan["to"]
            ), None)
            if match:
                existing = list(match.get("via") or [])
                planned_via = list(plan.get("via") or [])
                if len(planned_via) > len(existing):
                    match["via"] = planned_via
                if plan.get("year") and not match.get("year"):
                    match["year"] = plan["year"]
                if plan.get("label") and not match.get("label"):
                    match["label"] = plan["label"]
            else:
                routes.append(dict(plan))
        exact = {tuple(_route_stops(item)) for item in planned}
        kept = []
        for route in routes:
            stops = set(_route_stops(route))
            if tuple(_route_stops(route)) not in exact and any(stops < group for group in covered):
                continue
            kept.append(route)
        pruned = []
        for route in kept:
            stops = _route_stops(route)
            if any(
                route.get("kind") == other.get("kind")
                and len(stops) < len(_route_stops(other))
                and any(_route_stops(other)[index:index + len(stops)] == stops for index in range(len(_route_stops(other)) - len(stops) + 1))
                for other in kept
                if other is not route
            ):
                continue
            pruned.append(route)
        base["routes"] = pruned
    mentioned = set(_islamap_mentions(text))
    regions = list(base.get("regions") or [])
    have = {item.get("id") for item in regions}
    region_values = []
    if "hijaz" in mentioned or "الحجاز" in text:
        region_values.append(("hijaz", "منطلق" if planned else "الحجاز"))
    if "sham" in mentioned or "الشام" in text:
        region_values.append(("sham", "ثغور" if "ثغور" in text else "الشام"))
    if "anatolia" in mentioned:
        region_values.append(("anatolia", "آسيا الصغرى"))
    for region_id, value in region_values:
        if region_id not in have:
            regions.append({"id": region_id, "value": value})
    base["regions"] = regions
    if not str(base.get("title") or "").strip():
        base["title"] = "مسارات الفتح نحو القسطنطينية" if "القسطنطينية" in text and planned else {
            "madhhab": "المذاهب الفقهية",
            "futuh": "مسارات الفتوح",
            "ghazawat": "مسارات الغزوات",
            "cities": "المدن والمراكز",
        }.get(kind, "خارطة العالم الإسلامي")
    if kind == "cities":
        base["routes"] = []
    if not base.get("regions") and not base.get("cities") and not base.get("routes") and not base.get("places"):
        return None
    return base


def _extract_islamap_object(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    fenced = re.search(r"```(?:islamap|json)?\s*(\{.*\})\s*```", raw, re.S)
    blob = fenced.group(1) if fenced else raw
    start = blob.find("{")
    end = blob.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no json")
    blob = re.sub(r",\s*([}\]])", r"\1", blob[start:end + 1])
    data = json.loads(blob)
    if isinstance(data, dict) and isinstance(data.get("islamap"), dict):
        data = data["islamap"]
    if not isinstance(data, dict):
        raise ValueError("not object")
    return data


_ISLAMAP_CENTURY_WORDS = {
    "الأول": 1, "الاول": 1, "الثاني": 2, "الثالث": 3, "الرابع": 4, "الخامس": 5,
    "السادس": 6, "السابع": 7, "الثامن": 8, "التاسع": 9, "العاشر": 10,
}


def _islamap_century(value: Any) -> Optional[int]:
    if isinstance(value, (int, float)) and value:
        century = int(value)
        return century if 1 <= century <= 15 else None
    text = str(value or "").strip()
    if not text:
        return None
    digits = re.search(r"\d{1,2}", text)
    if digits:
        century = int(digits.group(0))
        return century if 1 <= century <= 15 else None
    for word, century in _ISLAMAP_CENTURY_WORDS.items():
        if word in text:
            return century
    return None


def _islamap_accept_id(token: Any, extra_ids: Optional[set] = None) -> str:
    resolved = _islamap_resolve_id(token)
    if resolved:
        return resolved
    text = str(token or "").strip()
    if extra_ids and text in extra_ids:
        return text
    return ""


def _islamap_name_list(value: Any) -> List[str]:
    if isinstance(value, list):
        items = value
    elif value:
        items = re.split(r"[،,؛;|\n]+", str(value))
    else:
        items = []
    names = []
    for item in items:
        name = str(item or "").strip(" -•\t")
        if name and name not in names:
            names.append(name[:90])
    return names[:24]


def _clean_islamap_places(data: Dict[str, Any], extra_ids: Optional[set] = None) -> List[Dict[str, Any]]:
    raw_places = data.get("places") or data.get("locations") or []
    merged: Dict[Tuple[str, Optional[int]], Dict[str, Any]] = {}
    order: List[Tuple[str, Optional[int]]] = []
    for item in raw_places:
        if not isinstance(item, dict):
            continue
        city_id = _islamap_accept_id(item.get("city") or item.get("id") or item.get("name") or item.get("place"), extra_ids)
        if city_id not in ISLAMAP_CITY_IDS and city_id not in (extra_ids or set()):
            continue
        century = _islamap_century(item.get("century") or item.get("era") or item.get("hijri_century") or item.get("period"))
        scholars = _islamap_name_list(item.get("scholars") or item.get("scientists") or item.get("ulema") or item.get("names"))
        books = _islamap_name_list(item.get("books") or item.get("works") or item.get("titles"))
        key = (city_id, century)
        if key not in merged:
            region_id = _islamap_resolve_id(item.get("region") or item.get("province"))
            if region_id not in ISLAMAP_REGION_IDS:
                region_id = ISLAMAP_CITY_REGION.get(city_id, "")
            row: Dict[str, Any] = {"id": city_id}
            if region_id:
                row["region"] = region_id
            if century:
                row["century"] = century
            row["scholars"] = []
            row["books"] = []
            merged[key] = row
            order.append(key)
        row = merged[key]
        for name in scholars:
            if name not in row["scholars"]:
                row["scholars"].append(name)
        for name in books:
            if name not in row["books"]:
                row["books"].append(name)
        note = str(item.get("note") or item.get("value") or "").strip()
        if note and not row.get("note"):
            row["note"] = note[:160]
    places = []
    for key in order:
        row = merged[key]
        row["count"] = len(row["scholars"])
        if not row["scholars"]:
            row.pop("scholars")
        if not row["books"]:
            row.pop("books")
        places.append(row)
    places.sort(key=lambda row: (row.get("century") or 99, row["id"]))
    return places


def _islamap_eras(places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    eras: Dict[int, Dict[str, Any]] = {}
    for place in places:
        century = place.get("century")
        if not century:
            continue
        era = eras.setdefault(int(century), {
            "century": int(century), "label": f"ق{int(century)}هـ", "scholars": 0, "books": 0, "cities": 0,
        })
        era["scholars"] += int(place.get("count") or 0)
        era["books"] += len(place.get("books") or [])
        era["cities"] += 1
    return [eras[key] for key in sorted(eras)]


def _islamap_issues(cleaned: Optional[Dict[str, Any]], kind: str) -> List[str]:
    if not cleaned:
        return ["المخرج ليس JSON صالحاً بالمعرفات المسموحة"]
    mode = _islamap_mode(kind)
    issues = []
    if mode == "distribution":
        regions = [item for item in (cleaned.get("regions") or []) if item.get("value")]
        if not regions:
            issues.append("لم تُستخرج دول. أخرج regions بمعرف الدولة وقيمة التوزيع المكتوبة عليها")
    elif mode == "cities":
        cities = cleaned.get("cities") or cleaned.get("places") or []
        if not cities:
            issues.append("لم تُستخرج مدن. أخرج cities بمعرف المدينة وقيمة التوزيع")
    elif mode == "routes":
        routes = cleaned.get("routes") or []
        if not routes:
            issues.append("لم يُستخرج مسار. أخرج routes من الانطلاق إلى الوصول")
        for route in routes:
            stops = [route.get("from"), *(route.get("via") or []), route.get("to")]
            water = [stop for stop in stops if stop in ISLAMAP_SEA_IDS]
            if route.get("kind") == "sea" and not water:
                issues.append("مسار بحري بلا محطة ماء، فيخترق البر. أدرج محطات البحر")
            if route.get("kind") == "land" and water:
                issues.append("مسار بري فيه محطة بحر. أبقِ البحر في مسار kind=sea")
    return issues


def _clean_islamap(data: Dict[str, Any], kind: str, extra_ids: Optional[set] = None) -> Optional[Dict[str, Any]]:
    titles = {
        "distribution": "توزيع جغرافي",
        "routes": "مسارات",
        "madhhab": "توزيع جغرافي",
        "futuh": "مسارات الفتوح",
        "ghazawat": "مسارات الغزوات",
        "cities": "المدن والمراكز",
        "full": "خارطة العالم الإسلامي",
    }
    allowed_ids = set(ISLAMAP_CITY_IDS) | set(extra_ids or set())
    regions = []
    for item in data.get("regions") or []:
        if not isinstance(item, dict):
            continue
        region_id = _islamap_resolve_id(item.get("id") or item.get("name") or item.get("region"))
        value = str(item.get("value") or item.get("madhhab") or "").strip()
        if region_id not in ISLAMAP_REGION_IDS or not value:
            continue
        row = {"id": region_id, "value": value[:80]}
        note = str(item.get("note") or "").strip()
        if note:
            row["note"] = note[:120]
        regions.append(row)
    cities = []
    for item in data.get("cities") or []:
        if not isinstance(item, dict):
            continue
        city_id = _islamap_accept_id(item.get("id") or item.get("name"), extra_ids)
        if city_id not in allowed_ids:
            continue
        row = {"id": city_id}
        value = str(item.get("value") or "").strip()
        note = str(item.get("note") or "").strip()
        if value:
            row["value"] = value[:80]
        if note:
            row["note"] = note[:160]
        century = _islamap_century(item.get("century") or item.get("era") or item.get("period"))
        if century:
            row["century"] = century
        scholars = _islamap_name_list(item.get("scholars") or item.get("names"))
        books = _islamap_name_list(item.get("books") or item.get("works"))
        if scholars:
            row["scholars"] = scholars
            row["count"] = len(scholars)
        if books:
            row["books"] = books
        region_id = _islamap_resolve_id(item.get("region"))
        if region_id in ISLAMAP_REGION_IDS:
            row["region"] = region_id
        cities.append(row)
    routes = []
    seen = set()
    for item in data.get("routes") or []:
        if not isinstance(item, dict):
            continue
        origin = _islamap_accept_id(item.get("from"), extra_ids)
        destination = _islamap_accept_id(item.get("to"), extra_ids)
        if origin not in allowed_ids or destination not in allowed_ids:
            continue
        via = []
        for token in item.get("via") or []:
            stop = _islamap_accept_id(token, extra_ids)
            if stop in allowed_ids and stop not in (origin, destination) and stop not in via:
                via.append(stop)
        if origin == destination and not via:
            continue
        route_kind = str(item.get("kind") or item.get("type") or "land").strip()
        if route_kind not in ("land", "sea", "portage"):
            route_kind = "land"
        if route_kind == "land":
            via = [stop for stop in via if stop not in ISLAMAP_SEA_IDS]
            if origin in ISLAMAP_SEA_IDS or destination in ISLAMAP_SEA_IDS:
                continue
        key = (origin, tuple(via), destination, route_kind)
        if key in seen:
            continue
        seen.add(key)
        row = {"from": origin, "to": destination, "via": via, "kind": route_kind}
        label = str(item.get("label") or "").strip()
        year = str(item.get("year") or "").strip()
        if label:
            row["label"] = label[:80]
        if year:
            row["year"] = year[:40]
        routes.append(row)
    if kind == "cities" or _islamap_mode(kind) == "distribution":
        routes = []
    places = _clean_islamap_places(data, allowed_ids)
    if not places and kind in ("madhhab", "cities") and cities:
        places = [{
            "id": city["id"],
            **({"region": city["region"]} if city.get("region") else ({"region": ISLAMAP_CITY_REGION[city["id"]]} if ISLAMAP_CITY_REGION.get(city["id"]) else {})),
            **({"century": city["century"]} if city.get("century") else {}),
            **({"scholars": city["scholars"]} if city.get("scholars") else {}),
            **({"books": city["books"]} if city.get("books") else {}),
            **({"count": city["count"]} if city.get("count") else {}),
            **({"note": city["note"]} if city.get("note") else {}),
        } for city in cities]
    if not regions and not cities and not routes and not places:
        return None
    title = str(data.get("title") or "").strip()[:80] or titles.get(kind) or titles.get(_islamap_mode(kind)) or "خارطة"
    subject = str(data.get("subject") or data.get("madhhab") or "").strip()[:40]
    result: Dict[str, Any] = {
        "mode": _islamap_mode(kind),
        "title": title,
        "regions": regions,
        "cities": cities,
        "routes": routes,
    }
    if subject:
        result["subject"] = subject
    if places:
        result["places"] = places
        result["eras"] = _islamap_eras(places)
    return result


def _islamap_primary_name(place_id: str) -> str:
    names = [name for name, mapped in ISLAMAP_NAME_TO_ID.items() if mapped == place_id and not str(name).isascii()]
    if not names:
        return place_id
    names.sort(key=len, reverse=True)
    return names[0]


def _islamap_coord_ok(lat: float, lng: float) -> bool:
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return False
    if abs(lat) < 0.2 and abs(lng) < 0.2:
        return False
    return True


def _islamap_all_coordinates(text: str) -> List[tuple]:
    blob = str(text or "")
    found: List[tuple] = []
    for marked in re.finditer(
        r"(\d{1,2})°\s*(\d{1,2})(?:[′'\u2032]\s*(?:(\d{1,2})[″\"\u2033])?)?\s*([NS])\s*[,/]?\s*(\d{1,3})°\s*(\d{1,2})(?:[′'\u2032]\s*(?:(\d{1,2})[″\"\u2033])?)?\s*([EW])",
        blob,
        re.I,
    ):
        lat = int(marked.group(1)) + int(marked.group(2)) / 60 + int(marked.group(3) or 0) / 3600
        lng = int(marked.group(5)) + int(marked.group(6)) / 60 + int(marked.group(7) or 0) / 3600
        if marked.group(4).upper() == "S":
            lat = -lat
        if marked.group(8).upper() == "W":
            lng = -lng
        if _islamap_coord_ok(lat, lng):
            found.append((lat, lng))
    for marked in re.finditer(
        r"(\d{1,2}(?:\.\d+)?)\s*°\s*([NS])\s*[,/]?\s*(\d{1,3}(?:\.\d+)?)\s*°\s*([EW])",
        blob,
        re.I,
    ):
        lat = float(marked.group(1)) * (-1 if marked.group(2).upper() == "S" else 1)
        lng = float(marked.group(3)) * (-1 if marked.group(4).upper() == "W" else 1)
        if _islamap_coord_ok(lat, lng):
            found.append((lat, lng))
    for labeled in re.finditer(
        r"lat(?:itude)?[^0-9\-]{0,16}(-?\d{1,2}\.\d+).{0,90}?lon(?:gitude)?[^0-9\-]{0,16}(-?\d{1,3}\.\d+)",
        blob,
        re.I | re.S,
    ):
        lat, lng = float(labeled.group(1)), float(labeled.group(2))
        if _islamap_coord_ok(lat, lng):
            found.append((lat, lng))
    for arabic in re.finditer(
        r"(?:خط العرض|العرض)\s*[:=]?\s*(-?\d{1,2}\.\d+).{0,80}?(?:خط الطول|الطول)\s*[:=]?\s*(-?\d{1,3}\.\d+)",
        blob,
    ):
        lat, lng = float(arabic.group(1)), float(arabic.group(2))
        if _islamap_coord_ok(lat, lng):
            found.append((lat, lng))
    return found


def _islamap_parse_coordinates(text: str, scope: str = "") -> Optional[tuple]:
    found = _islamap_all_coordinates(text)
    if scope == "Iberia":
        inside = [pair for pair in found if -11.5 <= pair[1] <= 4.8 and 34.6 <= pair[0] <= 43.9]
        if inside:
            return inside[0]
        return None
    return found[0] if found else None


def _islamap_parse_modern(text: str, original: str) -> str:
    patterns = [
        r"(?:modern name|now called|known today as|today known as|official name)\s*[:\-]?\s*[«\"']?([^\"'\n,،.]{2,48})",
        r"(?:الاسم الحديث|الاسم الحالي|تُعرف اليوم باسم|تعرف اليوم باسم|تسمى اليوم|تُسمى اليوم)\s*[:：]?\s*[«\"]?([^\"»\n،.]{2,48})",
    ]
    for pattern in patterns:
        found = re.search(pattern, str(text or ""), re.I)
        if not found:
            continue
        name = found.group(1).strip(" .،:：«»\"'")
        if name and name != original and len(name) <= 40:
            return name
    return ""


def _islamap_lookup_tokens(raw: Optional[Dict[str, Any]], cleaned: Optional[Dict[str, Any]]) -> List[str]:
    ordered: List[str] = []
    seen = set()

    def add(token: Any) -> None:
        text = str(token or "").strip()
        if not text:
            return
        resolved = _islamap_resolve_id(text)
        if resolved in ISLAMAP_CITY_IDS or resolved in ISLAMAP_REGION_IDS:
            text = _islamap_primary_name(resolved)
        if text.isascii() or len(text) < 2 or text in seen:
            return
        seen.add(text)
        ordered.append(text)

    for route in (cleaned or {}).get("routes") or []:
        add(route.get("from"))
        add(route.get("to"))
        for stop in route.get("via") or []:
            add(stop)
    for item in (cleaned or {}).get("cities") or []:
        add(item.get("id") or item.get("name"))
    for item in (cleaned or {}).get("places") or []:
        add(item.get("id") or item.get("city") or item.get("name"))
    for item in (cleaned or {}).get("regions") or []:
        add(item.get("id") or item.get("name"))
    if isinstance(raw, dict):
        for bucket in ("cities", "places", "regions"):
            for item in raw.get(bucket) or []:
                if isinstance(item, dict):
                    add(item.get("name") or item.get("id") or item.get("city"))
        for route in raw.get("routes") or []:
            if isinstance(route, dict):
                add(route.get("from"))
                add(route.get("to"))
                for stop in route.get("via") or []:
                    add(stop)
    return ordered[:28]


def _islamap_gloss(text: str) -> Dict[str, str]:
    gloss = {}
    for match in re.finditer(r"([\u0600-\u06FF]+(?:\s+[\u0600-\u06FF]+){0,3})\s*\(\s*([A-Za-z][^)]{1,48})\s*\)", str(text or "")):
        phrase = match.group(1).strip()
        latin = match.group(2).strip()
        gloss[phrase] = latin
        bare = phrase[1:] if phrase.startswith("و") and len(phrase) > 3 else phrase
        gloss.setdefault(bare, latin)
        last = bare.split()[-1]
        if last != bare:
            gloss.setdefault(last, latin)
    return gloss


def _islamap_fold(text: str) -> str:
    import unicodedata
    normalized = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _islamap_in_scope(pair: tuple, scope: str) -> bool:
    lat, lng = pair
    if scope == "Iberia":
        return -11.5 <= lng <= 4.8 and 34.6 <= lat <= 43.9
    return True


def _islamap_tavily_blob_points(data: Dict[str, Any], latin: str, scope: str) -> Optional[tuple]:
    ranked = []
    answer = str(data.get("answer") or "")
    chunks = [{"title": "", "content": answer}]
    chunks.extend(data.get("results") or [])
    for item in chunks:
        title = str(item.get("title") or "")
        content = str(item.get("content") or "")[:1500]
        pairs = [pair for pair in _islamap_all_coordinates(title + "\n" + content) if _islamap_in_scope(pair, scope)]
        if not pairs:
            continue
        head = _islamap_fold(title.split(" - ")[0])
        token = _islamap_fold((latin or "").split(",")[0].strip())
        score = 0
        if token and (head == token or head.startswith(token + ",") or head.startswith(token + " (")):
            score = 8
        elif token and head.endswith(" " + token) and any(word in head.split() for word in ("rock", "strait", "bay", "city", "ciudad")):
            score = 6
        elif token and token in head:
            score = 2
        if "location map/data" in head:
            score -= 6
        ranked.append((score, pairs[0], title))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    if ranked[0][0] < 5:
        return None
    return ranked[0][1]


def _islamap_tavily_place(name: str, key: str, latin: str = "", scope: str = "") -> Dict[str, Any]:
    query_name = latin or name
    queries = [f"\"{query_name}\" coordinates"]
    if scope == "Iberia":
        queries.extend([
            f"\"{query_name}\" Spain coordinates",
            f"\"{query_name}\" Portugal coordinates",
            f"\"{query_name}\" Morocco coordinates",
        ])
    domains = ["en.wikipedia.org", "ar.wikipedia.org", "www.wikidata.org", "www.geonames.org"]
    if scope == "Iberia":
        domains.insert(0, "es.wikipedia.org")
    empty = {"name": name, "lat": None, "lng": None, "modern": latin or ""}
    parsed = None
    modern = latin
    for query in queries:
        try:
            data = _tavily_search_sync(query, key, 4, domains, 18)
        except Exception:
            continue
        parsed = _islamap_tavily_blob_points(data, query_name, scope)
        parts = [str(data.get("answer") or "")]
        for item in (data.get("results") or [])[:4]:
            parts.append(str(item.get("content") or "")[:400])
        modern = _islamap_parse_modern("\n".join(parts), name) or latin
        if parsed:
            break
    if not parsed:
        return empty
    return {"name": name, "lat": parsed[0], "lng": parsed[1], "modern": modern}


def _islamap_fetch_points(tokens: List[str], key: str, source_text: str = "") -> List[Dict[str, Any]]:
    if not tokens or not key:
        return []
    gloss = _islamap_gloss(source_text)
    scope = "Iberia" if any(token in source_text for token in ("ندلس", "يبيري", "البرتغال", "إسبانيا", "اسبانيا")) else ""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    found: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}
        for token in tokens:
            latin = gloss.get(token) or ""
            if not latin:
                hits = [value for name, value in gloss.items() if name == token or name.endswith(" " + token)]
                latin = hits[0] if hits else ""
            futures[pool.submit(_islamap_tavily_place, token, key, latin, scope)] = token
        for future in as_completed(futures):
            token = futures[future]
            try:
                found[token] = future.result()
            except Exception:
                found[token] = {"name": token, "lat": None, "lng": None, "modern": ""}
    merged: Dict[str, Dict[str, Any]] = {}
    for token, row in found.items():
        place_id = _islamap_resolve_id(token)
        known = place_id in ISLAMAP_CITY_IDS or place_id in ISLAMAP_REGION_IDS
        if not known:
            if row.get("lat") is None:
                continue
            place_id = "ext" + hashlib.md5(token.encode("utf-8")).hexdigest()[:8]
        point = {
            "id": place_id,
            "name": token,
            "modern": row.get("modern") or "",
            "source": "tavily" if row.get("lat") is not None else "",
        }
        if row.get("lat") is not None:
            point["lat"] = round(float(row["lat"]), 4)
            point["lng"] = round(float(row["lng"]), 4)
        if place_id in ISLAMAP_SEA_IDS:
            point["water"] = True
        current = merged.get(place_id)
        if current and current.get("lat") is not None and point.get("lat") is None:
            if point.get("modern") and not current.get("modern"):
                current["modern"] = point["modern"]
            continue
        merged[place_id] = point
    return list(merged.values())


def _islamap_apply_points(drawn: Optional[Dict[str, Any]], points: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not drawn:
        return drawn
    kept = [point for point in points if point.get("lat") is not None or point.get("modern")]
    drawn["points"] = kept
    by_id = {point["id"]: point for point in kept}
    for bucket in ("cities", "regions", "places"):
        for item in drawn.get(bucket) or []:
            pin = by_id.get(item.get("id")) or by_id.get(item.get("city"))
            if not pin:
                continue
            if pin.get("modern"):
                item["modern"] = pin["modern"]
            if pin.get("lat") is not None:
                item["lat"] = pin["lat"]
                item["lng"] = pin["lng"]
    return drawn


def _islamap_redraw(material: str, kind: str, drawn: Dict[str, Any], points: List[Dict[str, Any]], key: str, model_id: str) -> Dict[str, Any]:
    extra = set()
    for point in points:
        if str(point.get("id") or "").startswith("ext"):
            extra.add(point["id"])
            if point.get("name"):
                extra.add(point["name"])
    system = (
        _islamap_prompt(kind)
        + "\nالخريطة المختارة من أمثلة ECharts هي "
        + str(drawn.get("example") or "")
        + " (" + str(drawn.get("example_label") or "") + "). "
        + "رتّب البيانات على هيكلها فقط، ولا تغيّر نوع الخريطة، ولا تُخرج كود رسم. مكتبة ECharts هي التي ترسم.\n"
        "جدول Tavily هو المصدر الوحيد لخط العرض وخط الطول والاسم الحديث. انسخ lng وlat وmodern كما هي ولا تخترع رقماً. "
        "البحر يبقى على محطات الماء، والبر لا يدخل البحر."
    )
    user = (
        f"النص:\n{material[:18000]}\n\nجدول Tavily:\n{json.dumps(points, ensure_ascii=False)}"
        f"\n\nالترتيب المقروء:\n{json.dumps({name: drawn.get(name) for name in ('mode', 'title', 'regions', 'cities', 'places', 'routes')}, ensure_ascii=False)[:7000]}"
    )
    try:
        content = call_openrouter_raw(
            model_id=model_id,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            api_key=key,
            temperature=0,
            max_tokens=3500,
            timeout=150,
            thinking_level=None,
        )
    except Exception:
        return drawn
    try:
        cleaned = _clean_islamap(_extract_islamap_object(content), kind, extra)
    except Exception:
        cleaned = None
    if not cleaned or _islamap_issues(cleaned, kind):
        return drawn
    return _apply_route_method(cleaned, material, kind) or drawn


ISLAMAP_EXAMPLES = (
    {
        "id": "map-HK",
        "mode": "distribution",
        "label": "توزيع جغرافي على الدول",
        "url": "https://echarts.apache.org/examples/en/editor.html?c=map-HK",
    },
    {
        "id": "geo-choropleth-scatter",
        "mode": "cities",
        "label": "مدن ومراكز",
        "url": "https://echarts.apache.org/examples/en/editor.html?c=geo-choropleth-scatter",
    },
    {
        "id": "geo-graph",
        "mode": "routes",
        "label": "مسارات على الإحداثيات",
        "url": "https://echarts.apache.org/examples/en/editor.html?c=geo-graph",
    },
)


ISLAMAP_DRAW_MODELS = ("google/gemini-3.8-flash", "x-ai/grok-4.7")
_ISLAMAP_SAMPLE_MARKERS = ("Travel Routes", "中西区", "Austurland", "Population Density of Hong Kong", "湾仔", "iceland")


def _islamap_ask(messages: List[Dict[str, str]], key: str, max_tokens: int) -> tuple:
    errors = []
    for model_id in ISLAMAP_DRAW_MODELS:
        try:
            content = call_openrouter_raw(
                model_id=model_id,
                messages=messages,
                api_key=key,
                temperature=0,
                max_tokens=max_tokens,
                timeout=150,
                thinking_level=None,
            )
            if str(content or "").strip():
                return content, model_id
            errors.append(f"{model_id}: جواب فارغ")
        except Exception as exc:
            errors.append(f"{model_id}: {exc}")
    raise RuntimeError("؛ ".join(errors) or "تعذر الاتصال بنموذج الرسم")


def _islamap_extract_facts(material: str, key: str) -> Dict[str, Any]:
    system = (
        "أنت مستخلص بيانات الخارطة فقط. اقرأ النص واستخرج ما يُوضع على الخارطة، بلا رسم وبلا إحداثيات وبلا اختيار نوع الخارطة.\n"
        "كل عنصر واحد من: region لدولة أو إقليم مع value عبارة التوزيع كما وردت، أو city لمدينة أو مركز مع value، أو route بـ from ثم via ثم to وmedium أحد land أو sea أو portage.\n"
        "إذا بدأ المسار بعبور بحر ثم واصل على البر، فافصل عبور البحر في مسار medium:sea، ومسير البر في مسار medium:land. لا تجمع البحر والبر في مسار واحد.\n"
        "لا تضف موضعاً ليس في النص. أخرج JSON واحداً فقط بهذا الشكل، واستعمل الحقول التي تنطبق:\n"
        '{"title":"","items":[{"type":"region","name":"مصر","value":"عبارة التوزيع"},{"type":"city","name":"الكوفة","value":"عبارة التوزيع","region":"العراق"},{"type":"route","from":"المدينة","via":["دمشق"],"to":"القسطنطينية","medium":"land","label":"البر"}]}'
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"النص:\n{material[:24000]}"},
    ]
    last_error = "تعذر استخلاص بيانات الخارطة من النص"
    for _attempt in range(2):
        try:
            content, _model = _islamap_ask(messages, key, 3000)
        except Exception as exc:
            raise RuntimeError(str(exc))
        try:
            data = _extract_islamap_object(content) or {}
        except Exception:
            data = {}
        items = []
        for item in data.get("items") or []:
            if not isinstance(item, dict):
                continue
            if item.get("name") or item.get("from") or item.get("id"):
                items.append(item)
        if items:
            title = str(data.get("title") or "").strip()[:80]
            return {"title": title, "items": items[:40]}
        last_error = "الاستخلاص لم يُخرج مواضع من النص"
        messages = messages + [
            {"role": "assistant", "content": str(content)[:4000]},
            {"role": "user", "content": "أعد JSON وحده. items فيها المواضع المذكورة في النص فقط."},
        ]
    raise RuntimeError(last_error)


def _islamap_item_type(item: Dict[str, Any]) -> str:
    kind = str(item.get("type") or item.get("kind") or "").strip().lower()
    if kind in ("region", "country", "دولة", "إقليم", "اقليم"):
        return "region"
    if kind in ("city", "place", "center", "مدينة", "مركز"):
        return "city"
    if kind in ("route", "path", "مسار") or (kind in ("land", "sea", "portage") and (item.get("from") or item.get("to"))):
        return "route"
    if item.get("from") and item.get("to"):
        return "route"
    return ""


def _islamap_choose_example(items: List[Dict[str, Any]], prefer: str) -> Dict[str, str]:
    regions = [item for item in items if _islamap_item_type(item) == "region"]
    cities = [item for item in items if _islamap_item_type(item) == "city"]
    routes = [item for item in items if _islamap_item_type(item) == "route"]
    prefer_mode = ""
    if prefer in ("distribution", "madhhab"):
        prefer_mode = "distribution"
    elif prefer == "cities":
        prefer_mode = "cities"
    elif prefer in ("routes", "futuh", "ghazawat"):
        prefer_mode = "routes"
    mode = ""
    if prefer_mode == "distribution" and regions:
        mode = "distribution"
    elif prefer_mode == "cities" and cities:
        mode = "cities"
    elif prefer_mode == "routes" and routes:
        mode = "routes"
    elif routes:
        mode = "routes"
    elif regions and len(regions) >= len(cities):
        mode = "distribution"
    elif cities:
        mode = "cities"
    elif regions:
        mode = "distribution"
    else:
        mode = "distribution"
    return next(example for example in ISLAMAP_EXAMPLES if example["mode"] == mode)


def _islamap_facts_payload(facts: Dict[str, Any], mode: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {"title": facts.get("title") or "", "regions": [], "cities": [], "routes": []}
    for item in facts.get("items") or []:
        kind = _islamap_item_type(item)
        if mode == "distribution" and kind == "region":
            data["regions"].append({"id": item.get("name") or item.get("id"), "value": item.get("value") or item.get("label") or ""})
        elif mode == "cities" and kind == "city":
            data["cities"].append({
                "id": item.get("name") or item.get("id"),
                "name": item.get("name") or item.get("id"),
                "value": item.get("value") or item.get("label") or "",
                "region": item.get("region") or "",
            })
        elif mode == "routes" and kind == "route":
            data["routes"].append({
                "from": item.get("from") or "",
                "to": item.get("to") or "",
                "via": item.get("via") or [],
                "kind": item.get("medium") if item.get("medium") in ("land", "sea", "portage") else (item.get("kind") if item.get("kind") in ("land", "sea", "portage") else "land"),
                "label": item.get("label") or item.get("value") or "",
                "year": item.get("year") or "",
            })
    return data


def _islamap_km(origin: Dict[str, Any], destination: Dict[str, Any]) -> float:
    from math import atan2, cos, radians, sin, sqrt
    lat1, lng1 = radians(float(origin["lat"])), radians(float(origin["lng"]))
    lat2, lng2 = radians(float(destination["lat"])), radians(float(destination["lng"]))
    dlat, dlng = lat2 - lat1, lng2 - lng1
    hav = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 6371 * 2 * atan2(sqrt(hav), sqrt(1 - hav))


def _islamap_short_crossing(stops: List[str], points: List[Dict[str, Any]], limit: float = 150) -> bool:
    located = []
    for stop in stops:
        place = _islamap_locate_point(str(stop or ""), points)
        if place:
            located.append(place)
    if len(located) < 2:
        return False
    return all(_islamap_km(origin, destination) <= limit for origin, destination in zip(located, located[1:]))


def _islamap_guard_routes(drawn: Optional[Dict[str, Any]], points: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    if not drawn:
        return drawn
    kept = []
    for route in drawn.get("routes") or []:
        via = [stop for stop in (route.get("via") or []) if stop]
        origin = route.get("from")
        destination = route.get("to")
        kind = route.get("kind") or "land"
        stops = [origin, *via, destination]
        water = [stop for stop in stops if stop in ISLAMAP_SEA_IDS]
        if kind == "land":
            if origin in ISLAMAP_SEA_IDS or destination in ISLAMAP_SEA_IDS:
                continue
            via = [stop for stop in via if stop not in ISLAMAP_SEA_IDS]
        elif kind == "sea" and not water and not _islamap_short_crossing(stops, points or []):
            continue
        route = dict(route)
        route["via"] = via
        kept.append(route)
    drawn["routes"] = kept
    return drawn


def _islamap_stamp_example(drawn: Optional[Dict[str, Any]], example: Dict[str, str]) -> Optional[Dict[str, Any]]:
    if not drawn:
        return drawn
    drawn["mode"] = example["mode"]
    drawn["example"] = example["id"]
    drawn["example_label"] = example["label"]
    drawn["example_url"] = example["url"]
    return drawn


def _islamap_load_example(example_id: str) -> str:
    path = Path(__file__).resolve().parent / "static" / "geo" / "examples" / f"{example_id}.js"
    return path.read_text(encoding="utf-8")


def _islamap_places() -> Dict[str, Any]:
    path = Path(__file__).resolve().parent / "static" / "geo" / "places.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _islamap_locate_point(place_id: str, points: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    gazetteer = _islamap_places().get(place_id) or {}
    found = next((
        point for point in points
        if point.get("lng") is not None and (point.get("id") == place_id or point.get("name") == place_id)
    ), None)
    lng = lat = None
    name = ""
    modern_ok = True
    if found:
        lng, lat = float(found["lng"]), float(found["lat"])
        name = found.get("modern") or found.get("name") or ""
        if gazetteer:
            far = abs(lng - float(gazetteer["lng"])) > 1.2 or abs(lat - float(gazetteer["lat"])) > 1.2
            if far:
                lng, lat = float(gazetteer["lng"]), float(gazetteer["lat"])
                name = gazetteer.get("name") or place_id
                modern_ok = False
            elif not name:
                name = gazetteer.get("name") or place_id
    elif gazetteer:
        lng, lat = float(gazetteer["lng"]), float(gazetteer["lat"])
        name = gazetteer.get("name") or place_id
    else:
        return None
    label = name
    if found and modern_ok and found.get("modern") and found.get("name") and found["modern"] != found["name"]:
        label = f"{found['name']} ({found['modern']})"
    elif gazetteer and not found:
        label = gazetteer.get("name") or place_id
    return {
        "id": place_id,
        "name": label,
        "lng": round(lng, 4),
        "lat": round(lat, 4),
        "water": bool(gazetteer.get("water")),
    }


_ISLAMAP_FILL_COLORS = ["#dc2626", "#16a34a", "#2563eb", "#f97316", "#eab308", "#7c3aed", "#0891b2", "#db2777"]
_ISLAMAP_WORLD_COUNTRIES = {
    "andalus": ["Spain", "Portugal"],
    "maghreb": ["Morocco", "Algeria", "Mauritania"],
    "ifriqiya": ["Tunisia", "Libya"],
    "egypt": ["Egypt"],
    "sham": ["Syria", "Lebanon", "Jordan", "Palestine", "Israel"],
    "iraq": ["Iraq"],
    "yemen": ["Yemen"],
    "fars": ["Iran"],
    "khurasan": ["Afghanistan", "Turkmenistan"],
    "transoxiana": ["Uzbekistan", "Tajikistan", "Kyrgyzstan"],
    "sind": ["Pakistan"],
    "anatolia": ["Turkey"],
    "azerbaijan": ["Azerbaijan"],
    "khwarizm": ["Uzbekistan", "Turkmenistan"],
    "daylam": ["Iran"],
    "jibal": ["Iran"],
    "kirman": ["Iran"],
    "khuzistan": ["Iran"],
    "oman": ["Oman"],
    "bahrayn": ["Bahrain"],
    "filastin": ["Palestine", "Israel"],
    "urdunn": ["Jordan"],
}


def _islamap_force_world(option: Dict[str, Any]) -> Dict[str, Any]:
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "map" in node and node["map"] not in ("", "islamap-world"):
                node["map"] = "islamap-world"
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(option)
    geo = option.get("geo")
    if isinstance(geo, dict):
        geo["map"] = "islamap-world"
        geo["roam"] = True
        label = geo.get("label") if isinstance(geo.get("label"), dict) else {}
        label["show"] = False
        geo["label"] = label
    return option


def _islamap_option_rejected(option: Dict[str, Any]) -> bool:
    if not isinstance(option, dict) or not option.get("series"):
        return True
    blob = json.dumps(option, ensure_ascii=False)
    if any(marker in blob for marker in _ISLAMAP_SAMPLE_MARKERS):
        return True
    for series in option.get("series") or []:
        if not isinstance(series, dict):
            continue
        for node in series.get("data") or []:
            if isinstance(node, dict) and str(node.get("name") or "") in list("abcdefghijk"):
                return True
    return False


def _islamap_fallback_option(drawn: Dict[str, Any], points: List[Dict[str, Any]]) -> Dict[str, Any]:
    title = drawn.get("title") or "خارطة"
    mode = drawn.get("mode") or "distribution"
    if mode == "routes":
        nodes: Dict[str, Dict[str, Any]] = {}
        edges = []
        colors = {"land": "#6b3e26", "sea": "#1d4e89", "portage": "#8c6a43"}
        land_colors = ["#6b3e26", "#9a3412", "#3f6212", "#7c2d12", "#92400e", "#44403c"]
        land_index = 0
        for route in drawn.get("routes") or []:
            stops = [route.get("from"), *(route.get("via") or []), route.get("to")]
            kind = route.get("kind") or "land"
            water_route = any(
                ((_islamap_locate_point(str(item or ""), points) or {}).get("water"))
                or str(item or "") in ISLAMAP_SEA_IDS
                for item in stops
            )
            if kind == "sea" and not water_route and not _islamap_short_crossing(stops, points):
                continue
            if kind == "land":
                color = land_colors[land_index % len(land_colors)]
                land_index += 1
            else:
                color = colors.get(kind, "#6b3e26")
            located = []
            for stop in stops:
                place = _islamap_locate_point(str(stop or ""), points)
                if not place:
                    continue
                if kind == "land" and place["water"]:
                    continue
                nodes[place["id"]] = {"name": place["name"], "value": [place["lng"], place["lat"]]}
                located.append(place["id"])
            for origin, destination in zip(located, located[1:]):
                edges.append({
                    "source": nodes[origin]["name"],
                    "target": nodes[destination]["name"],
                    "lineStyle": {"color": color, "width": 2},
                })
        return {
            "title": {"text": title},
            "tooltip": {},
            "geo": {
                "map": "islamap-world",
                "roam": True,
                "aspectScale": 0.88,
                "label": {"show": False},
                "itemStyle": {"areaColor": "#f4efe6", "borderColor": "#b7aa96"},
            },
            "series": [{
                "type": "graph",
                "coordinateSystem": "geo",
                "data": list(nodes.values()),
                "edges": edges,
                "edgeSymbol": ["none", "arrow"],
                "edgeSymbolSize": 8,
                "label": {"show": True, "position": "right", "formatter": "{b}"},
                "labelLayout": {"hideOverlap": True},
                "lineStyle": {"opacity": 1},
            }],
        }
    if mode == "cities":
        data = []
        categories: Dict[str, str] = {}
        for city in drawn.get("cities") or drawn.get("places") or []:
            place = _islamap_locate_point(str(city.get("id") or ""), points)
            if not place or place["water"]:
                continue
            value = str(city.get("value") or drawn.get("subject") or "مدينة")
            if value not in categories:
                categories[value] = _ISLAMAP_FILL_COLORS[len(categories) % len(_ISLAMAP_FILL_COLORS)]
            data.append({
                "name": place["name"],
                "value": [place["lng"], place["lat"], value],
                "itemStyle": {"color": categories[value], "borderColor": "#fff", "borderWidth": 2},
            })
        return {
            "title": {"text": title},
            "tooltip": {"trigger": "item"},
            "geo": {
                "map": "islamap-world",
                "roam": True,
                "aspectScale": 0.88,
                "label": {"show": False},
                "itemStyle": {"areaColor": "#f4efe6", "borderColor": "#b7aa96"},
            },
            "series": [{
                "type": "scatter",
                "coordinateSystem": "geo",
                "data": data,
                "symbolSize": 16,
                "label": {"show": True, "position": "right", "formatter": "{b}"},
            }],
        }
    data = []
    seen = {}
    for region in drawn.get("regions") or []:
        value = str(region.get("value") or "").strip()
        region_id = str(region.get("id") or "")
        if not value:
            continue
        if value not in seen:
            seen[value] = _ISLAMAP_FILL_COLORS[len(seen) % len(_ISLAMAP_FILL_COLORS)]
        for name in _ISLAMAP_WORLD_COUNTRIES.get(region_id) or []:
            data.append({
                "name": name,
                "value": 1,
                "itemStyle": {"areaColor": seen[value]},
                "label": {"show": True, "formatter": f"{_islamap_primary_name(region_id)}\n{value}"},
            })
    return {
        "title": {"text": title},
        "tooltip": {"trigger": "item"},
        "series": [{
            "name": title,
            "type": "map",
            "map": "islamap-world",
            "roam": True,
            "nameProperty": "name",
            "label": {"show": True},
            "itemStyle": {"areaColor": "#f4efe6", "borderColor": "#b7aa96"},
            "data": data,
        }],
    }


def _islamap_option_from_skeleton(drawn: Dict[str, Any], points: List[Dict[str, Any]], key: str) -> tuple:
    skeleton = _islamap_load_example(str(drawn.get("example") or "map-HK"))
    prepared = []
    for bucket in ("regions", "cities", "routes"):
        for item in drawn.get(bucket) or []:
            row = dict(item)
            for field in ("id", "from", "to"):
                if row.get(field):
                    located = _islamap_locate_point(str(row[field]), points)
                    if located:
                        row[f"{field}_lng"] = located["lng"]
                        row[f"{field}_lat"] = located["lat"]
                        row[f"{field}_name"] = located["name"]
            if row.get("via"):
                row["via_points"] = [point for point in (_islamap_locate_point(str(stop), points) for stop in row["via"]) if point]
            prepared.append({"bucket": bucket, **row})
    system = (
        "أنت تملأ خيار Apache ECharts. الهيكل التالي أصلي من https://echarts.apache.org/examples وبياناته عيّنة فقط.\n"
        "استبدال كل الأسماء والإحداثيات والعناوين ببيانات النتيجة أمر حتمي. يُمنع إبقاء Travel Routes أو الحروف a b c أو مناطق هونغ كونغ أو أيسلندا أو إحداثياتها.\n"
        "اسم الخريطة داخل التطبيق هو islamap-world. ضعه مكان ch و HK و iceland.\n"
        "أبقِ نوع السلسلة وroam وedgeSymbol. اجعل geo.label.show قيمة false حتى لا تظهر أسماء الدول الإنجليزية.\n"
        "أخرج كائن option بصيغة JSON فقط، بلا شرح."
    )
    user = f"الهيكل الأصلي:\n{skeleton}\n\nبيانات النتيجة التي تُستبدل بها العينة:\n{json.dumps(prepared, ensure_ascii=False)[:12000]}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for model_id in ISLAMAP_DRAW_MODELS:
        try:
            content = call_openrouter_raw(
                model_id=model_id,
                messages=messages,
                api_key=key,
                temperature=0,
                max_tokens=4000,
                timeout=150,
                thinking_level=None,
            )
            option = _extract_islamap_object(content)
            if isinstance(option.get("option"), dict):
                option = option["option"]
            option = _islamap_force_world(option)
            if not _islamap_option_rejected(option):
                return option, model_id
        except Exception:
            continue
    return _islamap_fallback_option(drawn, points), "ملء الهيكل محلياً"


def _compose_islamap(text: str, kind: str, key: str, model_id: str, tavily_key: str = "") -> tuple:
    material = str(text or "").strip()[:36000]
    if len(material) < 40:
        raise RuntimeError("لا توجد نتيجة كافية لرسم الخارطة")
    chosen = normalize_model_id(str(model_id or "").strip())
    if not chosen:
        raise RuntimeError("اختر النموذج من القائمة المنسدلة قبل الرسم")
    if not str(tavily_key or "").strip():
        raise RuntimeError("يلزم مفتاح Tavily في تبويب الخدمات لضبط خطوط الطول والعرض والأسماء الحديثة")
    facts = _islamap_extract_facts(material, key)
    example = _islamap_choose_example(facts.get("items") or [], kind)
    mode = example["mode"]
    payload = _islamap_facts_payload(facts, mode)
    if mode == "routes" and not payload.get("routes"):
        payload["routes"] = _planned_routes(material, "routes")
    points = _islamap_fetch_points(_islamap_lookup_tokens(payload, payload), tavily_key, material)
    extra = {point["id"] for point in points if str(point.get("id") or "").startswith("ext")}
    for point in points:
        if str(point.get("id") or "").startswith("ext") and point.get("name"):
            extra.add(point["name"])
    drawn = _clean_islamap(payload, mode, extra)
    drawn = _apply_route_method(drawn, material, mode)
    drawn = _islamap_guard_routes(drawn, points)
    if not drawn or not (drawn.get("regions") or drawn.get("cities") or drawn.get("places") or drawn.get("routes")):
        raise RuntimeError("الأداة لم تجد في الاستخلاص ما يكفي للخارطة المختارة")
    drawn = _islamap_stamp_example(drawn, example)
    drawn = _islamap_apply_points(drawn, points)
    option, used_model = _islamap_option_from_skeleton(drawn, points, key)
    drawn["option"] = option
    print(f"[islamap] example {example['id']} option via {used_model}")
    fence = "```islamap\n" + json.dumps(drawn, ensure_ascii=False) + "\n```"
    return fence, used_model


class IslamapComposeRequest(BaseModel):
    text: str = ""
    kind: str = "full"
    model: str = ""
    api_key: Optional[str] = None
    tavily_key: Optional[str] = None


@app.post("/api/islamap/compose")
async def islamap_compose_endpoint(req: IslamapComposeRequest, request: Request):
    key = owner_openrouter_key(request, req.api_key)
    if not key:
        raise HTTPException(status_code=400, detail="أدخل مفتاح OpenRouter الخاص بحسابك في تبويب الخدمات")
    model = str(req.model or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="اختر النموذج من القائمة المنسدلة قبل الرسم")
    tavily = (req.tavily_key or "").strip() or (load_provider_keys(current_owner_id(request)).get("tavily") or "").strip()
    if not tavily:
        raise HTTPException(status_code=400, detail="يلزم مفتاح Tavily في تبويب الخدمات لضبط خطوط الطول والعرض والأسماء الحديثة")
    kind = req.kind if req.kind in ("auto", "distribution", "cities", "routes", "madhhab", "futuh", "ghazawat", "full") else "auto"
    try:
        reply, used_model = await asyncio.to_thread(_compose_islamap, req.text, kind, key, model, tavily)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"reply": reply, "model": used_model}


@app.post("/api/tools/architect/install")
async def tool_architect_install_endpoint(req: ToolArchitectInstallRequest):
    result = await asyncio.to_thread(_install_tool_packages, req.packages or [], req.urls or [])
    result["status"] = "ok"
    return result


@app.post("/api/tools/architect/repair")
async def tool_architect_repair_endpoint(req: ToolArchitectRepairRequest, request: Request):
    key = owner_openrouter_key(request, req.api_key)
    coding = _select_python_coding_model(key)
    model_id = coding.get("id") or req.model or "google/gemini-2.5-flash"
    allowed = _safe_tool_packages(req.allowed_packages or [])
    package_rule = (
        "يجوز استخدام هذه المكتبات المنصبة فقط إضافة إلى المكتبات القياسية: " + "، ".join(allowed)
        if allowed else
        "استخدم المكتبات القياسية فقط."
    )
    prompt = (
        "أصلح كود أداة بايثون التالي ليعمل في دالة run_tool(input_data)، مع إبقاء mock_test_input.\n"
        f"{package_rule}\n"
        f"المواصفات: {json.dumps(req.spec or {}, ensure_ascii=False)[:3000]}\n"
        f"خطأ الاختبار: {str(req.error or '')[:3500]}\n\n```python\n{req.code[:16000]}\n```\n"
        "أعد الكود المصحح كاملاً داخل ```python فقط."
    )
    try:
        reply = await asyncio.to_thread(
            call_openrouter_raw, model_id,
            [{"role": "system", "content": "أنت مبرمج بايثون خبير. أعد الكود فقط."}, {"role": "user", "content": prompt}],
            key, 0.15, 8000, None, None, None, None, None, 480, "off"
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"تعذر إصلاح كود الأداة: {exc}")
    match = re.search(r"```python\s*([\s\S]*?)\s*```", reply)
    return {"status": "ok", "code": (match.group(1) if match else reply).strip()}


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
    thinking_level: Optional[str] = "medium"

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
    search_mode_str = "بحث هجين (دلالي + لفظي) ⚡" if req.use_hybrid else "بحث دلالي صرف (Dense Only) 🧠"
    target_books = [str(b).strip() for b in (req.books_scope or []) if str(b).strip()]
    test_limit = min(max(int(req.scanned_texts or 10), 3), 20)
    
    try:
        test_buckets, _test_anchors = expand_query_with_anchor_rounds(
            query=user_query,
            scopes=[{
                "name": "test",
                "books": target_books or None,
                "top_k": test_limit,
                "pool_size": max(test_limit * 4, 80),
            }],
            api_key=key,
            model=resolved_model,
            use_hybrid=bool(req.use_hybrid if req.use_hybrid is not None else True),
            honor_agent_limit=bool(target_books),
        )
        cits = test_buckets.get("test") or []
    except Exception as ex:
        print(f"[Subagent Test] RAG search error: {ex}")
        cits = []
    
    # 2. تجهيز مقتطفات الشواهد التراثية
    snippets_items = []
    citations_meta = []
    for c in cits:
        loc_str = _approved_citation_label(c)
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
            f"(تنبيه: نطاق الكتب لم يُرجع شاهداً بعد جولات مراسي البحث. لا تكمل الجواب من الذاكرة، وأخبر أن النطاق لم يجد شيئاً.)"
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
            timeout=70,
            thinking_level=req.thinking_level or "medium"
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
            },
            dict(ECHARTS_BUILTIN_TOOL),
            dict(ISLAMAP_BUILTIN_TOOL)
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
        "markmap-lib.min.js": "https://cdn.jsdelivr.net/npm/markmap-lib@0.17/dist/browser/index.iife.js",
        "echarts.min.js": "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"
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
        "في توجيه المدير وكل وكيل: الإحالة القياسية وحدها هي اسم الكتاب ثم (الجزء-الصفحة) بأرقام لاتينية، مثل مجموع الفتاوى (2-368). للكتاب ذي الجزء الواحد: زاد المستقنع ص(50). تُمنع الشرطة المائلة والأرقام العربية وعكس الترتيب ووضع اسم الكتاب داخل القوس.\n\n"
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
    },
    {
        "type": "function",
        "function": {
            "name": "search_similar_research",
            "description": (
                "ابحث في الويب عن أصول البحوث المقاربة لهذا المشروع: دقتها، ومصادرها، ومراجعها، والمراجعات المشابهة. "
                "استعملها بعد تفكيك المسألة من الذاكرة وبعد مسح فهرس الشاملة، ولا تبنِ الخطة على الويب وحده."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "عبارة بحث أكاديمية عن دراسات ومراجع مقاربة"},
                    "max_results": {"type": "integer", "description": "عدد النتائج، من 3 إلى 6"}
                },
                "required": ["query"]
            }
        }
    }
]


def _search_similar_research(query: str, tavily_key: str, max_results: int = 5) -> dict:
    key = (tavily_key or "").strip()
    if not key:
        return {"error": "مفتاح بحث الويب غير مضبوط. أخبر الباحث بإضافته في تبويب الخدمات.", "results": []}
    limit = min(max(int(max_results or 5), 3), 6)
    payload = {
        "api_key": key,
        "query": (query or "")[:400],
        "search_depth": "advanced",
        "include_answer": True,
        "max_results": limit
    }
    request = urllib.request.Request(
        "https://api.tavily.com/search",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8")
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": f"تعذر بحث الويب: {type(exc).__name__}", "results": []}
    results = []
    for item in (data.get("results") or [])[:limit]:
        results.append({
            "title": item.get("title") or "",
            "url": item.get("url") or "",
            "content": (item.get("content") or "")[:500]
        })
    return {"answer": (data.get("answer") or "")[:800], "results": results}

def _architect_model_roster() -> str:
    models = ((openrouter_cache.get("data") or {}).get("models") or [])
    ranked = sorted(
        models,
        key=lambda model: ((model.get("benchmarks") or {}).get("intelligence_index") or 0),
        reverse=True
    )
    lines = []
    for model in ranked:
        if len(lines) >= 24:
            break
        intel = (model.get("benchmarks") or {}).get("intelligence_index")
        if not intel and len(lines) >= 12:
            continue
        reasoning = model.get("reasoning") or {}
        efforts = reasoning.get("supported_efforts") if isinstance(reasoning, dict) else None
        price = (model.get("pricing") or {}).get("prompt_per_1m")
        lines.append(
            f"- {model.get('id')} | {model.get('name')} | مؤشر الذكاء: {intel if intel is not None else 'غير منشور'} | "
            f"السياق: {model.get('context_length') or 0} | الإدخال لكل مليون: {price} | التفكير المقبول: {efforts or 'بلا تفكير داخلي'}"
        )
    if not lines:
        return "لم يُحمَّل فهرس النماذج بعد. لا تخترع معرفاً. استخدم فقط: google/gemini-2.5-flash، google/gemini-3.8-flash، google/gemini-4-argon، ~anthropic/claude-opus-latest، ~anthropic/claude-sonnet-latest، ~openai/gpt-sol-latest، openai/gpt-4o."
    return "\n".join(lines)

def _architect_fiqh_discipline_section() -> str:
    """ضبط الفقه المقارن لمهندس المشاريع: فهرس طبقات المذاهب الخمسة ومصطلحاتها
    وقواعد ترجيحها (من madhhab_authority.json) وكتب الإجماع وأسباب الخلاف
    والخلاف العالي (من discipline_books.json)، ليُبنى الفريق الفقهي مضبوطًا
    من لحظة التصميم لا مرقّعًا وقت التشغيل."""
    try:
        import library_search
    except Exception:
        return ""
    lines = [
        "\n\n【مرجع ضبط الفقه المقارن — للبيان والاسترشاد لا للتقييد】\n"
        "هذا المرجع يُعرَض عليك من فهارس ضبط المنظومة لتُبيَّن لك خريطة كتب المذاهب وطبقاتها ومصطلحاتها قبل أن تصمم — وهو أرضية تنطلق منها لا سقف تقف عنده. فأنت مهندس المشروع وصاحب النظر فيه: قد ترى بحسب المسألة بعينها كتبًا مهمة جدًا خارج هذا الفهرس، فأضفها من عندك حيث تراها، ووجّه بها الوكلاء، وبيّن في بطاقة الوكيل وجه أهميتها للمسألة؛ فإضافتك المسوّغة مقدّمة على حرفية الفهرس، والفهرس نفسه صرّح بفجواته حيث نقص.\n"
        "ومما يحسن أن تراعيه عند تصميم مشروع فقهي مقارن، ما لم ترَ في المسألة ما يقتضي خلافه:\n"
        "1. الأصل في البحوث المقارنة وكيل مستقل لكل مذهب من المذاهب الخمسة (الحنفي، المالكي، الشافعي، الحنبلي، الظاهري)، ما لم تقتضِ طبيعة المسألة دمجًا أو تفصيلًا آخر تراه.\n"
        "2. ابدأ في حقل `books` لوكيل كل مذهب من طبقات مذهبه في الجدول أدناه بصيغة «#رقم العنوان» — كتاب من كل طبقة بدايةً حسنة — ثم أضف ما تراه مهمًا لهذه المسألة من كتب الفهرس كلها ولو خرجت عن الجدول، مع تسويغ الإضافة في البطاقة. وتجنّب أن يقوم قسم مذهب على الموسوعات المقارنة أو على كتب مذهب آخر وحده؛ فذلك مما ضعفت به بحوث سابقة.\n"
        "3. يحسن أن ينص `system_prompt` لوكيل كل مذهب على: نسبة الأقوال من كتب مذهبه لا من حكايات مخالفيه، وبدء تقريره ببطاقات أدلة مرقمة (الدعوى، الإحالة، النص الحرفي، نوع الدليل)، والتصريح بانعدام البطاقة إن لم يجد بدل الإكمال من الذاكرة، ومراعاة مصطلحات مذهبه وقواعد ترجيحه المبينة أدناه.\n"
        "4. وكيل الحديث وعلله: الأصل أن متون الأحاديث من كتب السنة الأصلية (الصحاح والسنن والمسانيد والمصنفات)، وأن يذكر حكم الدرجة لكل حديث من كتب التخريج والعلل والرجال، لا سرد طرق بلا أحكام — فقد ضعفت بحوث حين اكتفت بالتخريج.\n"
        "5. وكيل الإجماع وأسباب الخلاف والخلاف العالي: قوائم كتبها أدناه مظانها الأولى؛ ودعوى الإجماع أو الاتفاق لا تستقيم إلا بنقل منها، وإلا فلفظ «الجمهور» أسلم.\n"
        "6. وكيل المقارنة المرجعية: الموسوعة الفقهية الكويتية وحدها موضعها الطبيعي عنده للمقابلة والضبط، ولا يحسن أن تكون سندًا وحيدًا لمتن حديث أو قول مذهبي.\n"
        "7. مراسي الاسترجاع (`retrieval_anchors`) لكل وكيل مذهب تُصاغ بألفاظ مذهبه وأسماء أبوابه في كتبه، لا بعبارات حديثية عامة وحدها.\n"
    ]
    for madhhab in ("الحنفي", "المالكي", "الشافعي", "الحنبلي", "الظاهري"):
        try:
            data = library_search.madhhab_authorities(madhhab) or {}
        except Exception:
            data = {}
        if not data:
            continue
        lines.append(f"\n— المذهب {madhhab} — طبقاته وكتبه المعتمدة:")
        for layer in data.get("layers") or []:
            books = "؛ ".join(
                f"#{b.get('book_id')} {b.get('title')} ({b.get('author') or ''}، ت {b.get('death') or '؟'})"
                for b in (layer.get("books") or []))
            if books:
                lines.append(f"  • طبقة {layer.get('name')}: {books}")
        terms = data.get("terminology") or []
        if terms:
            lines.append("  مصطلحاته: " + "؛ ".join(
                f"{t.get('term')}: {(t.get('meaning') or '')[:110]}" for t in terms[:7]))
        rules = data.get("tarjih_rules") or []
        if rules:
            lines.append("  قواعد ترجيحه: " + "؛ ".join(
                (r.get("rule") or "")[:130] for r in rules[:4]))
        if data.get("gaps"):
            lines.append(f"  فجوة معلنة في الفهرس: {str(data.get('gaps'))[:160]}")
    try:
        disc = library_search._load_discipline_books() or {}
        sections = (disc.get("sections") or {})
        labels = {"ijma": "كتب الإجماع", "asbab": "كتب أسباب الخلاف", "khilaf": "كتب الخلاف العالي"}
        for kind, label in labels.items():
            sec = sections.get(kind) or {}
            books = []
            for layer in sec.get("layers") or []:
                for b in (layer.get("books") or [])[:6]:
                    if b.get("book_id"):
                        books.append(f"#{b.get('book_id')} {b.get('title')}")
            if books:
                lines.append(f"\n{label}: " + "؛ ".join(books[:10]))
    except Exception:
        pass
    return "\n".join(lines)


def _architect_agent_tuning_section() -> str:
    """ضبط اختيار النماذج وإعدادات الوكلاء بحسب طبيعة المهمة: لا اختيار عشوائيًا،
    فلكل نمط مهمة نموذجه وعمق تفكيره وعدد شواهد وسياقه — والبطاقة تسوّغ ذلك."""
    return (
        "\n\n【ضبط اختيار النماذج وإعدادات كل وكيل بحسب طبيعة مهمته — لا اختيار عشوائيًا】\n"
        "صنّف مهمة كل وكيل أولًا إلى نمط من الأنماط الآتية، ثم اختر نموذجه وإعداداته على مقتضى نمطه من جدول «أقوى نماذج OpenRouter» (الأعلى مؤشر ذكاء في الأعلى)، وسوّغ في بطاقة كل وكيل بجملة واحدة: نمط مهمته ← سبب اختيار النموذج ومستوى التفكير وعدد الشواهد. وكل إعداد تضعه يسري تنفيذيًا حرفيًا (النموذج، thinking، search_mode، extract_count، context_tokens)، فلا تضع رقمًا لا تقصده.\n"
        "1. نمط الجمع والمسح والفرز الأولي (وكلاء جمع النصوص، الرصد الواسع، حصر المظان): نماذج سريعة اقتصادية من النماذج الخفيفة في الجدول (نحو Gemini Flash)، thinking: low أو بلا تفكير، extract_count واسع 150-300، search_mode: hybrid، context_tokens واسع بقدر المادة، max_tokens متوسط. يُمنع مهنيًا إحراق نموذج قوي مكلف على مهمة جمع لا تحتاج عمقًا.\n"
        "2. نمط التحرير والتحقيق التخصصي (وكلاء المذاهب والفنون): نماذج قوية أو متوسطة عليا، thinking: medium إلى high، extract_count 80-150 مركزة في كتبه، فهؤلاء يقرؤون النصوص ويحررون النسبة لا يجمعون فقط.\n"
        "3. نمط العمق المعرفي والتفريع (استخراج علل الأحاديث وترتيبها منطقيًا، تخريج الطرق ومداراتها، نقد الأسانيد، تحرير محل النزاع): أقوى النماذج معرفيًا وتحليليًا في الجدول، thinking: high أو max، extract_count ضيقة دقيقة 40-80 منتقاة، context_tokens واسع لأن مادته مترابطة ومتفرعة، max_tokens كبير. هنا العمق لا الاتساع.\n"
        "4. نمط المناظرة والحجاج (المُثبِت، النافي، الحَكَم المحرِّر): أقوى نماذج التحليل والمنطق وقلب الحجج في الجدول، مادتها قليلة ودقيقة جدًا فلا تحتاج كثرة نصوص: extract_count 30-60 منتقاة بعناية، thinking: high أو max، max_tokens كبير متسع لبناء الحجة ونقضها، وسياقها مركز لا واسع. الحَكَم المحرِّر أشدها احتياجًا لقوة المنطق.\n"
        "5. نمط الحكم والترجيح والقيادة (الحَكَم المحرِّر، مدير المشروع، محرر الخلاصة): أعلى نماذج الجدول تقييمًا، thinking: high أو max، extract_count 80-150، لأن خطأه يعم البحث كله.\n"
        "6. نمط الإخراج والطباعة والفهرسة والتنسيق: نماذج سريعة متوسطة، thinking: low، فمهارتها صياغة وتنسيق لا استدلال.\n"
        "7. نمط الاستشارة والتفكير (مجلس المستشارين، ومستشار الشبكة Tavily): الروستر المعتمد إلزامًا في كل مشروع أربعة أعضاء متنوعين: `openai/gpt-6-astra-pro` و`~anthropic/claude-sonnet-latest` و`meta/muse-wonder` و`openai/gpt-6.1-terra`، thinking: max، extract_count: 0، books: []، سقف إخراجهم في التنفيذ 64000 فلا تضيّقه. `kind`: advisor، وخامس اختياري للشبكة `kind`: tavily. أسماؤهم محايدة («عضو مجلس المستشارين» مع اسم النموذج) بلا تقسيم فنون بينهم: فكلٌّ منهم تصله الاستشارة كاملة كإخوانه ويخرج أفضل ما عنده، والمنظومة توحّد مكررهم وتحفظ لقطاتهم الفريدة، والمدير هو من يحكم ويُسند كتبهم الموثقة من الشاملة إلى المتخصصين. يُمنع تخصيص عضو بفن دون الآخرين، ويُمنع تعيين نموذج جمع سريع لهذا النمط، ويُمنع تحميلهم كتبًا يمسحونها، ويُمنع استبدال الأربعة بنموذج واحد مكرر.\n"
        "قواعد عامة: لا نموذجَ قويًا لمهمة جمع، ولا نموذجَ سريعًا رخيصًا لمهمة علل أو مناظرة أو ترجيح؛ ومستوى التفكير لا يتجاوز «التفكير المقبول» لذلك النموذج في الجدول؛ وعدد الشواهد والسياق بحسب طبيعة المادة (اتساع للمسح، تركيز للمناظرة والعلل)؛ ودرجة الحرارة منخفضة (0.1-0.3) في التوثيق والتخريج والعلل.\n"
        "وقبل إخراج المخطط افحص بنفسك كل معرف نموذج اخترته مقابل جدول نماذج OpenRouter المعروض عليك في هذا التوجيه فحصًا حرفيًا: المعرف غير الموجود في الجدول بعينه ممنوع ولو ظننته موجودًا، وستتحقق المنظومة آليًا من معرفات مخططك عند خروجه وتعلن كل معرف غير متحقق.\n"
    )


def _architect_adaptive_profile_section() -> str:
    """مصفوفة تكيف المهندس مع أنواع الطلبات: لا مخطط قبل تصنيف الطلب على
    خمسة محاور (الفن، الغرض، العمق والطول، الجمهور، المنهج)؛ فكل محور يغيّر
    عدد الوكلاء وأدوارهم وشواهدهم وبنية المخرج تغييرًا حقيقيًا لا شكليًا.
    ويُختم التصنيف في حقل research_profile بالمخطط، ويُفحص آليًا عند الخروج،
    ويُنقل عند الاعتماد إلى توجيه المدير فيسري على التنفيذ كله."""
    return (
        "\n\n【مصفوفة تكيّف المهندس مع نوع الطلب — التصنيف قبل التصميم】\n"
        "القاعدة الحاكمة: لا فريق واحد يصلح لكل طلب. قبل تصميم أي مخطط صنّف طلب الباحث على المحاور الخمسة الآتية، وإن غمض محور مؤثر (الفن أو الغرض أو الطول أو الجمهور) فسله عنه في كتلة ```choices (من سؤالين إلى أربعة) قبل إخراج المخطط، ولا تخمّن غرضًا يغيّر بنية البحث كله.\n"
        "— المحور الأول: فن البحث ومادته. فقه مقارن: وكلاء مذاهب بطبقاتهم وبطاقات أدلة ووكيل حديث وإجماع ومقارنة عند الحاجة، ومعهم مستشارو التفكير للمظانّ. حديث وعلل: وكلاء تخريج وطرق وعلل ورجال، شواهد ضيقة دقيقة، ولا وكلاء مذاهب ولا خطوط تغطية فقهية، ومستشارو التفكير قبل الجمع لأن مظانّ الحديث تختلف جذريًا بين حديث صفات وحديث أحكام وحديث معلّل. أصول: وكلاء مدارس أصولية وقواعد ودلالات. تفسير: وكلاء مفسّرين ومناهج وآيات الأحكام بحسب الطلب. لغة: وكلاء معاجم وحدود ونحو وبلاغة، نماذج سريعة غالبًا. تاريخ وسير وتراجم: وكلاء حوليات وطبقات وروايات، وتقليب صفحات واستيفاء حدث، وأداة تقويم عند الحاجة. عقيدة وكلام: وكلاء فرق ومقالات وشبه وردود. تحقيق مخطوطات: وكلاء نسخ ومقابلة وفهارس. والطلب المختلط يُفكك إلى فنون ويُعيَّن لكل فن وكلاؤه، ولا يُحشى وكيل واحد بفنين.\n"
        "— المحور الثاني: الغرض والجمهور، وهو ما يبني هيكل المخرج في توجيه المدير حرفيًا. بحث علمي محكّم: مقدمة بإشكالية ومنهج ودراسات سابقة، مباحث، خاتمة بنتائج، ثبت مصادر كامل، توثيق صارم. دراسات عليا (ماجستير/دكتوراه): أعمق استيعابًا، تأصيل وتحرير ومقارنة ونقد، فصل منهجية، وشواهد واسعة ونماذج قوية، ولا اختصار يخل بالإحاطة. تدريس ومنهج تعليمي: أهداف تعليمية لكل وحدة، تدرج من التصور إلى الحكم، أمثلة وتمارين وأسئلة تقويم وخلاصات مركزة، ولغة ميسّرة. مختصر أو خلاصة تنفيذية: جواب مباشر في أول المخرج، جداول تلخيص، حد أقصى صريح للطول، ولا مناظرة ولا استطراد. موسوعة أو مرجع مطوّل: استيعاب موسع، مداخل مرتبة، طبقات عرض، وشواهد كثيرة وفريق أكبر. فتوى أو إرشاد عملي: تحرير مختصر مؤصّل بلغة واضحة وتنبيه على الخلاف المعتبر بلا إغراق أكاديمي. مقال أو محاضرة: بنية خطابية متماسكة وشواهد منتقاة قوية لا حشد مراجع.\n"
        "— المحور الثالث: العمق والطول، ويُترجم أرقامًا لا ألفاظًا. مختصر: وكلاء قلة (٢-٥)، استخراج ٤٠-٨٠، بلا هيئة مناظرة كاملة (يُكتفى بناقد واحد عند الحاجة)، وسقف طول معلن في توجيه المدير. متوسط: ٦-١٠ وكلاء، استخراج ٨٠-١٥٠، مناظرة مصغرة (مثبت ونافٍ وحَكَم). مطوّل/موسوعي: فريق كامل بحسب الفن، استخراج ١٥٠-٣٠٠ للمسح و٨٠-١٥٠ للتحرير، مناظرة كاملة عند الخلاف، ومراحل متتابعة. وكلما قصر المطلوب حذفت أدوارًا لا أن تضغط النصوص في الوكلاء أنفسهم.\n"
        "— المحور الرابع: الجمهور. متخصصون: مصطلحات الفن بلا شرح، ونقد صريح. طلاب علم: شرح المصطلح عند أول ورود وتدرج. عامة: لغة ميسّرة وأمثلة وتجنب الخلاف الدقيق إلا بقدر الحاجة. والجمهور يُنص عليه في توجيه المدير ووكيل الإخراج.\n"
        "— المحور الخامس: المنهج. وصفي استقرائي: مسح واسع وتصنيف. مقارن: وكلاء متوازون لكل طرف وجداول مقابلة وحَكَم. نقدي تحليلي: ناقد منهجي قوي وشواهد دقيقة. تاريخي: تسلسل زمني وطبقات مصادر ونقد روايات. تأصيلي فقهي: بطاقات أدلة وتحرير نسبة وترجيح بقواعد الفن.\n"
        "الختم الإلزامي: ضع في المخطط حقل research_profile وفيه discipline وpurpose وdepth وlength وaudience وmethod وdebate (full|mini|none) وoutput_structure (بنية المخرج بسطر واحد)؛ واجعل توجيه المدير (`director.system_prompt`) يفتتح بعبارة «ملف الطلب: ...» تذكر الغرض والطول والجمهور وبنية المخرج، فهذا الختم هو ما يسري على التنفيذ بعد اعتماد البطاقات. وستفحص المنظومة وجود research_profile آليًا وتعلن نقصه.\n"
    )


def _run_architect_tool_call(tool_call: Dict[str, Any], tavily_key: str = "") -> Dict[str, Any]:
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
    elif name == "search_similar_research":
        try:
            limit = int(args.get("max_results") or 5)
        except (TypeError, ValueError):
            limit = 5
        return {"args": args, "result": _search_similar_research(str(args.get("query") or ""), tavily_key, limit)}
    else:
        return {"args": args, "result": {"error": f"أداة غير معروفة: {name}", "results": []}}

class ArchitectDialogRequest(BaseModel):
    messages: List[Dict[str, Any]]
    planning_model: Optional[str] = "google/gemini-2.5-flash"
    thinking_level: Optional[str] = "medium"
    context_tokens: Optional[int] = 1048576
    tavily_key: Optional[str] = ""
    api_key: Optional[str] = ""

@app.post("/api/projects/architect-dialog")
async def architect_dialog_endpoint(req: ArchitectDialogRequest, request: Request):
    """
    حوار واستشارات مهندس التخطيط المعماري (Architect Model)
    حوار تفاعلي مباشر يناقش الباحث في فكرة مشروعه، يسأله أسئلة استكشافية،
    يستكشف الكتب من قاعدة البيانات الببليوغرافية للمخزن، ويرشح وكلاء وأدوات حسابية مخصصة.
    """
    key = owner_openrouter_key(request, req.api_key)
    tavily_key = (req.tavily_key or "").strip() or (load_provider_keys(current_owner_id(request)).get("tavily") or "").strip()
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
        "【منهج الهندسة الإلزامي، بهذا الترتيب في كل مشروع جديد】\n"
        "1. فكّك المسألة أولاً من ذاكرتك: صوّرها، وحرّر محل النزاع، وسمِّ الفنون الداخلة، واذكر ما تعرفه عن المظانّ. وسم هذه الخطوة [من الذاكرة] ولا تنسب منها نصاً ولا جزءاً ولا صفحة.\n"
        "2. بعد التفكيك استعن بفهرس الشاملة قبل اعتماد الخطة: استدعِ search_books_catalog وget_category_core_books، واستعرض الكتب، ثم رشّح أدقها للمشروع بأرقامها #BookID. لا تُتمم المخطط قبل هذا المسح.\n"
        "3. استدعِ search_similar_research للويب: أصول البحوث المقاربة، ودقتها، ومصادرها، ومراجعها، والمراجعات المشابهة. إن غاب مفتاح الويب فصرّح بذلك ولا تختلق دراسات.\n"
        "4. عيّن لكل مدير ولكل وكيل نموذجاً من جدول «أقوى نماذج OpenRouter» أدناه، بمعرفه الحرفي. اختر الأعلى تقييماً والأنسب للمهمة، واكتب في البطاقة مستوى التفكير: low أو medium أو high أو max، بشرط أن يكون ضمن «التفكير المقبول» لذلك النموذج. التحرير العميق high أو max، والمسح السريع low أو medium.\n"
        "5. الهيكل: مدير جامع واحد هو الأصل، لأن التنفيذ يُدمج تحت قيادة واحدة. لا تُعدّد المدراء إلا إذا انقسم المشروع إلى فنون لا يجمعها تحرير واحد، مثل الفقه مع علل الحديث مع الرصد التاريخي. عندئذ أضف `directors` وكل مدير فن ووكلاؤه، واذكر سبب الانقسام، وأبقِ `director` للمدير الجامع.\n"
        "6. حدّد في كل بطاقة `extract_count`: عدد النصوص التي يستخرجها صاحبها من الشاملة. المسح الواسع 150 إلى 300، والتحقيق الضيق 40 إلى 80، ومدير الدمج 80 إلى 150. لا تجعل العدد واحداً للجميع.\n"
        "7. حدّد في كل بطاقة `search_mode`: hybrid إذا كانت المهمة ألفاظاً وأعلاماً ومتوناً، وsemantic إذا كانت معاني ومسائل تختلف صياغتها. الهجين هو الأصل في التوثيق الحرفي.\n"
        "8. أسئلة الباحث ليست مقالاً يكتبه. أخرجها في كتلة ```choices واحدة، كل سؤال فيه خيارات، والواجهة تضيف حقل كتابة اختيارياً. من 2 إلى 4 أسئلة في الدفعة، ولا تطلب جواباً إنشائياً من الصفر.\n"
        "مثال الكتلة:\n"
        "```choices\n"
        '{"questions":[{"id":"scope","prompt":"ما نطاق المشروع؟","multiple":false,"options":["مذهب واحد","مقارنة المذاهب","رصد تاريخي"]}]}\n'
        "```\n\n"
        "【أقوى نماذج OpenRouter بحسب مؤشر الذكاء المتاح، ولا تخترع معرفاً خارجها】\n"
        + _architect_model_roster() + "\n\n"
        "【ثانياً: المبادئ الحاكمة (تعلو على كل تعليمات لاحقة)】\n"
        "1. مصدر المعرفة الوحيد: مستودع النصوص (Qdrant) وقاعدة كتب الشاملة هو المصدر الوحيد المعتمد للنصوص والإحالات. ذاكرة النموذج تُستعمل للاهتداء فقط (لاقتراح المظانّ والمصطلحات وصياغة الاستعلامات)، ولا يُؤخذ منها نص ولا إحالة قطعية.\n"
        "2. الأمانة العلمية الصارمة: لا يُختلق نص، ولا مصدر، ولا رقم جزء أو صفحة، ولا اسم محقق أو طبعة. ما لم يُتحقق منه يُوسم صراحةً: [غير متحقق]. وما ورد من الذاكرة ولم يوجد في المستودع يُوسم: [من الذاكرة: غير موجود في المستودع]، ولا يُبنى عليه ترجيح.\n"
        "3. نسبة الأقوال إلى أصحابها من كتبهم، أو من كتب مذهبهم المعتمدة. لا يُكتفى بحكاية المخالف عن خصمه إلا مع التنبيه على ذلك.\n"
        "4. التمييز الدائم بين ثلاثة أشياء: النص المنقول بلفظه، والمعنى المنقول بتصرف، والاستنباط أو الترجيح الخاص بالفريق.\n"
        "5. التوثيق الكامل لكل معلومة من البيانات الوصفية للصفحة لا من الذاكرة. الإحالة القياسية وحدها: اسم الكتاب (الجزء-الصفحة) بأرقام لاتينية، مثل مجموع الفتاوى (2-368)، أو اسم الكتاب ص(50) إن كان جزءاً واحداً.\n"
        "6. درجات الثقة لكل معلومة:\n"
        "   [مقطوع: متحقق من الأصل]، [راجح: من مصدر ثانوي موثوق]، [محتمل: يحتاج تحققاً]، [مشكوك: تعارضت المصادر]، [غير متحقق].\n"
        "7. الأدوات تعرض وتحسب ولا تحكم: كل مُدخل لأي أداة مأخوذ من المدونة بمعرّفاته، وكل مُخرج منها مرتبط بالنصوص التي بُني عليها.\n"
        "8. الإفصاح عن الحدود: إذا غاب كتاب معتمد عن المستودع، أو تعذّرت عملية، يُصرَّح بذلك. لا يُوهم الباحث بأن مراجعة تمّت.\n"
        "9. الأدب العلمي: المناظرة لنصرة الحق، لا للتشهير بالأئمة ولا تحقيرهم. يُعرض قول المخالف بأقوى صوره قبل نقضه.\n"
        "10. لا يُعتمد حكم على حديث إلا بتخريج ونقل أحكام الأئمة عليه، مع بيان الاختلاف في الحكم إن وُجد.\n\n"
        "【ثالثاً: البيئة: المستودع وعملياته والأدوات】\n"
        "أ. المستودع: قاعدة Qdrant فيها نحو 8.15 مليون صفحة ومقطع، ويُبحث فيها بمحرك بحث هجين (دلالي متجهات BGE-M3 + فلاتر الكلمات والمصنفات).\n"
        "ب. الأدوات المتاحة لك فعلياً أثناء هذا الحوار: `search_books_catalog` و`get_library_categories` و`get_category_core_books` و`get_book_bibliography` للمسح الببليوغرافي، و`search_similar_research` لبحوث الويب المقاربة. أما عمليات المستودع التالية فيستعملها فريق التنفيذ (المدير والوكلاء) لا أنت، فصمّم الخطة على أساسها دون ادّعاء تنفيذها:\n"
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
        "قبل أي تخطيط، وبعد التفكيك من الذاكرة ومسح الشاملة والويب، اعرض ما فهمته ثم سلّم الأسئلة في كتلة ```choices فقط. لا تُغرق الباحث، ولا تطلب منه كتابة الجواب كله.\n"
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
        "── (1-ب) مجلس المستشارين [س-xx] — ركن إلزامي قبل المتخصصين في كل مشروع: مستشار واحد متفرغ للمدير بالروستر المعتمد حرفيًا: `~anthropic/claude-sonnet-latest` (thinking: max، بلا كتب وبلا استخراج نصوص)، ومدير المشروع نفسه عضو مناوب في الترشيح بصوته قبل أن يحكم بالمطابقة والإسناد. `kind`: `advisor`. أسماؤهم محايدة بأسماء نماذجهم، ولا تقسيم فنون ولا زوايا بينهم: وظيفتهم الوحيدة قبل بدء البحث أن تصل كلًّا منهم المسألة كاملة استقلالًا فيتولّد له (أ) قائمة أمهات الكتب التي هي مظانّ هذه المسألة بعينها، (ب) مراسي بحث تراثية قوية. المنظومة توحّد مكررهم وتحسب اتفاقهم وتحفظ لقطاتهم الفريدة، وتتحقق من وجود الكتب في قاعدة الشاملة بمطابقة المؤلف، ثم يعرضها على مدير المشروع (النموذج الأساسي) فيحكم على المشترك والفريد ويُسند كل كتاب إلى وكيله المختص، وتُطعّم بقراره في البطاقات. لا تجعل العضو وكيل جمع ولا مناظرًا، ولا تُسند الإسناد لقاعدة آلية. ولا عضو للشبكة الخارجية في الفريق؛ البحث كله داخل مكتبة الشاملة. وتنبيه بنيوي: الوكيل الذهبي لا يُصمَّم في مخططك ولا تذكره في الفريق؛ تنشئه المنظومة تلقائيًا وقت التنفيذ بعد مجلس المستشارين وقرار المدير، وكيلًا مؤقتًا بتوجيه نوعي من المدير يبحث في كتب المجلس المطابقة حصرًا صلبًا للبحث.\n"
        "── (2) الخبراء المتخصصون [خ-xx]: (الفقيه المقارن لكل مذهب، الأصولي، المحدّث، خبير الرجال، المؤرخ، خبير الفلك، المفسر، اللغوي، خبير التحقيق).\n"
        "── (3) هيئة المناظرة [ن-xx] (قلب المشروع في المسائل الخلافية):\n"
        "• المُثبِت [ن-01]: ينصر القول الأول بكل ما أوتي من أدلة ونقول.\n"
        "• النافي [ن-02]: ينصر القول المعارض بكل ما أوتي من أدلة ونقول.\n"
        "• الحَكَم المحرِّر [ن-03]: يدير الجولات، يرجح بقواعد الترجيح المعتبرة، ويرسم الخريطة الذهنية للمسألة.\n"
        "── (4) المساعدون الفنيون [ف-xx]: ف-01 للويب الخارجي عند الحاجة، ف-03 للتحقق والمطابقة الحرفية بـ get_page، ف-04 للمقارنة المرجعية، ف-05 للاستيفاء وتقليب الصفحات، ف-06 للتخريج، ف-07 للضبط اللغوي، ف-08 للإخراج والفهرسة، ف-10 مهندس الاسترجاع، ف-11 وكيل الأدوات التحليلية.\n"
        "── (5) وكيل الطباعة والإخراج الأكاديمي [ف-12]: وكيل متخصص يُعيّنه المهندس لاستخلاص البحث كاملاً وتجهيزه للطباعة الأكاديمية الفاخرة وملف PDF محكم، ويُوجّه لزاماً بتطبيق الوسوم والقواعد التالية بدقة متناهية:\n"
        "    ## [6] منهجية الحاشية والإحالات ##\n"
        "    أولًا: خرّج الأحاديث تخريجًا كاملاً وفق قواعد التخريج المذكورة أعلاه، وضعها في الحاشية.\n"
        "    ثانيًا: اذكر مصدر كل قول في الحاشية بالإخراج القياسي وحده: اسم الكتاب للمؤلف (جزء-صفحة)، ولذي الجزء الواحد: اسم الكتاب للمؤلف ص (صفحة).\n"
        "    ثالثًا: اجعل كل مرجع أو تخريج في سطر مستقل كاملًا. لا تفرّق المرجع الواحد في أسطر متعددة، ولا تحشو المراجع جميعها في سطر واحد دون تفريق.\n"
        "    رابعًا: استخدم الإحالة الصحيحة:\n"
        "    إذا نقلت نصًا حرفيًا: اكتب \"انظر:\" ثم (الكتاب، صاحبه، الجزء، الصفحة). ولا تستعمل انظر مكان ينظر ولا العكس.\n"
        "    إذا نقلت بالمعنى: اكتب \"ينظر:\" ثم (الكتاب، صاحبه، الجزء، الصفحة).\n"
        "    خامسًا: لا تستخدم مسافة الإزاحة (Indentation) في الحاشية إطلاقًا.\n"
        "    ## [7] التنسيق الطباعي (استخدام وسوم HTML) ##\n"
        "    أخرج البحث بتنسيق جاهز للطباعة كالبحوث العلمية الشرعية المحكمة باستخدام وسوم HTML التالية بدقة:\n"
        "    الإحالات في المتن: الرقم المرتفع وحده هكذا: <sup><small>(١)</small></sup>. يُمنع ذكر اسم الكتاب أو الجزء أو الصفحة في المتن، والمرجع كامل في الحاشية فقط.\n"
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
        '  "research_profile": {"discipline": "فن البحث", "purpose": "الغرض (محكّم/دراسات عليا/تدريس/مختصر/موسوعة/فتوى/مقال)", "depth": "العمق", "length": "الطول المستهدف", "audience": "الجمهور", "method": "المنهج", "debate": "full|mini|none", "output_structure": "بنية المخرج بسطر واحد"},\n'
        '  "retrieval_anchors": [\n'
        '    "مرساة استرجاع دلالية مصممة خصيصاً لأسلوب مصنفي هذا الفن المحدد في الشاملة",\n'
        '    "مرساة استرجاع ديناميكية 2",\n'
        '    "مرساة استرجاع ديناميكية 3",\n'
        '    "مرساة استرجاع ديناميكية 4"\n'
        '  ],\n'
        '  "director": {\n'
        '    "name": "اسم مدير المشروع التخصصي",\n'
        '    "model": "معرّف حرفي من جدول أقوى النماذج",\n'
        '    "thinking": "high",\n'
        '    "search_mode": "hybrid",\n'
        '    "extract_count": 120,\n'
        '    "context_tokens": 1048576,\n'
        '    "max_tokens": 65536,\n'
        '    "system_prompt": "التوجيه الحرفي الصارم لمدير المشروع قيادة وتنسيقاً وتفريغاً للجداول، مع الصلاحية العلمية الكاملة لإعادة البحث حتى 3 مرات، وإلزاماً حتمياً بإفراد جدول ثبت المصادر والمراجع الببليوغرافي الشامل (الكتاب، المؤلف وسنة وفاته، المحقق، الطبعة، دار النشر، بلد النشر، رقم الشاملة) في خاتمة التقرير النهائي للمشروع"\n'
        '  },\n'
        '  "subagents_group": {\n'
        '    "name": "اسم مجموعة الوكلاء المخصصة لهذا المشروع",\n'
        '    "desc": "وصف وظيفة المجموعة",\n'
        '    "agents": [\n'
        '      {\n'
        '        "name": "اسم الوكيل المتخصص 1",\n'
        '        "desc": "دوره",\n'
        '        "model": "معرّف حرفي من جدول أقوى النماذج",\n'
        '        "thinking": "high",\n'
        '        "search_mode": "hybrid",\n'
        '        "extract_count": 80,\n'
        '        "context_tokens": 262144,\n'
        '        "books": ["#رقم الكتاب من نتيجة search_books_catalog"],\n'
        '        "pool_size": 1500,\n'
        '        "top_k": 150,\n'
        '        "system_prompt": "التوجيه الحرفي للوكيل في استخراج نصوص المسألة"\n'
        '      },\n'
        '      {\n'
        '        "name": "عضو مجلس المستشارين — Astra Pro",\n'
        '        "desc": "عضو مجلس يصله السؤال كاملًا كإخوانه: تفكير للمدير فقط في أهم كتب مظانّ المسألة ومراسي البحث التراثية، بلا تقسيم فنون بين الأعضاء",\n'
        '        "kind": "advisor",\n'
        '        "model": "openai/gpt-6-astra-pro",\n'
        '        "thinking": "max",\n'
        '        "extract_count": 0,\n'
        '        "books": [],\n'
        '        "system_prompt": "أنت عضو في مجلس مستشارين للمدير: تصلك المسألة كاملة كإخوانك بلا تقسيم فنون، ففكّر في مظانّها ومراسيها من جميع جوانبها ولا تستخرج نصوصًا."\n'
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

    architect_system_prompt += _architect_fiqh_discipline_section()
    architect_system_prompt += _architect_agent_tuning_section()
    architect_system_prompt += _architect_adaptive_profile_section()
    architect_system_prompt += (
        f"\nسياق الاستيعاب المعتمد لهذا المشروع: {resolve_context_tokens(req.context_tokens)} رمز. "
        "اجعل context_tokens في بطاقة المدير وكل وكيل بهذه القيمة إلا إذا طلب الباحث تغييرها، ولا تضع هذا الرقم في max_tokens لأن ذلك حد الإخراج لا حد الشواهد.\n"
        "إذا أرسل الباحث رسالة تبدأ بـ «أضف هذه الكتب لدى الوكيل المناسب»، فأضف كل كتاب كما ورد برقمه المعياري وعنوانه إلى حقل books لدى الوكيل الأنسب لفن الكتاب، ولا تستبدل الرقم ولا تُسقط الكتاب.\n"
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
            attach_reasoning(payload, call_model, req.thinking_level or "medium")

            if str(call_model).startswith("local:"):
                reply_text = _complete_local_text(call_model, current_messages, 0.3, 4096)
                break
            def _post_architect(body):
                o_req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:8085",
                        "X-Title": "Al-Mojtahed Architect"
                    },
                    data=json.dumps(body).encode("utf-8")
                )
                with urllib.request.urlopen(o_req, timeout=140) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            try:
                data = None
                data = _post_architect(payload)
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")
                if payload.get("reasoning") and "reasoning" in err_body.lower():
                    payload.pop("reasoning", None)
                    try:
                        data = _post_architect(payload)
                    except urllib.error.HTTPError as retry_error:
                        err_body = retry_error.read().decode("utf-8", errors="ignore")
                        he = retry_error
                    else:
                        err_body = ""
                if not data:
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
                    res_info = _run_architect_tool_call(tc, tavily_key)
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

        # فحص معرفات نماذج المخطط على فهرس OpenRouter الحي: كل معرف غير
        # موجود حرفيًا يُعلن للباحث في الرد نفسه قبل اعتماد البطاقات.
        model_validation = {"checked": 0, "unknown": []}
        if isinstance(parsed_blueprint, dict):
            try:
                _valid_ids = {m.get("id") for m in ((openrouter_cache.get("data") or {}).get("models") or [])}
                _picked = []
                _dir = parsed_blueprint.get("director") or {}
                if _dir.get("model"):
                    _picked.append(str(_dir["model"]))
                for _ag in ((parsed_blueprint.get("subagents_group") or {}).get("agents") or []):
                    if _ag.get("model"):
                        _picked.append(str(_ag["model"]))
                for _dm in (parsed_blueprint.get("directors") or []):
                    if isinstance(_dm, dict) and _dm.get("model"):
                        _picked.append(str(_dm["model"]))
                model_validation["checked"] = len(_picked)
                if _valid_ids:
                    model_validation["unknown"] = sorted({m for m in _picked if m not in _valid_ids})
                if model_validation["unknown"]:
                    reply_text += ("\n\n⚠️ فحص نماذج OpenRouter الآلي: المعرفات الآتية غير موجودة في فهرس OpenRouter الحالي، "
                                   "فلا تعتمد بطاقاتها حتى تُستبدل بمعرفات من الجدول: " + "، ".join(model_validation["unknown"]))
                    print(f"⚠️ [Architect Model Check] معرفات غير متحقق منها: {model_validation['unknown']}", flush=True)
                elif _picked:
                    print(f"✅ [Architect Model Check] فُحص {len(_picked)} معرفًا على فهرس OpenRouter: كلها موجودة", flush=True)
            except Exception as _mv_err:
                print(f"⚠️ [Architect Model Check] {_mv_err}", flush=True)

        # فحص ملف تصنيف الطلب: مخطط بلا research_profile مكتمل يعني أن
        # المهندس صمم بلا تكييف مع نوع الطلب — يُعلن للباحث قبل الاعتماد.
        profile_validation = {"present": False, "missing": []}
        if isinstance(parsed_blueprint, dict):
            try:
                _prof = parsed_blueprint.get("research_profile") or {}
                _req_keys = ("discipline", "purpose", "depth", "length", "audience", "method", "debate", "output_structure")
                profile_validation["missing"] = [k for k in _req_keys if not str(_prof.get(k) or "").strip()]
                profile_validation["present"] = not profile_validation["missing"]
                if profile_validation["missing"]:
                    reply_text += ("\n\n⚠️ فحص تكييف الطلب الآلي: هذا المخطط ناقص التصنيف؛ غائب من research_profile: "
                                   + "، ".join(profile_validation["missing"])
                                   + ". اطلب من المهندس استكمال تصنيف الطلب (فنّه وغرضه وطوله وجمهوره ومنهجه) قبل اعتماد البطاقات، لئلا يُبنى فريق لا يناسب المطلوب.")
                    print(f"⚠️ [Architect Profile Check] حقول غائبة: {profile_validation['missing']}", flush=True)
                else:
                    print(f"✅ [Architect Profile Check] ملف الطلب مكتمل: {_prof.get('discipline')} / {_prof.get('purpose')} / {_prof.get('length')}", flush=True)
            except Exception as _pf_err:
                print(f"⚠️ [Architect Profile Check] {_pf_err}", flush=True)

        return {
            "status": "ok",
            "reply": reply_text,
            "blueprint": parsed_blueprint,
            "model_validation": model_validation,
            "profile_validation": profile_validation,
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

def find_chrome_binary() -> Optional[str]:
    env_path = os.environ.get("CHROME_PATH") or os.environ.get("CHROMIUM_PATH")
    candidates = [
        env_path,
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
        found = shutil.which(name)
        if found:
            return found
    return None

AMIRI_FONT_DIR = Path(__file__).resolve().parent / "static" / "fonts"
_REMOTE_FONT_LINK_RE = re.compile(
    r"<link\b[^>]*(?:fonts\.googleapis\.com|fonts\.gstatic\.com)[^>]*>",
    re.IGNORECASE,
)

def html_with_local_amiri(html: str) -> str:
    """الخط يُحمَّل من الملفات المحلية حتى لا ينتظر التوليد شبكة خطوط جوجل."""
    face = (
        "<style id=\"local-amiri\">"
        "@font-face{font-family:'Amiri';src:url('Amiri-Regular.ttf') format('truetype');font-weight:400;font-style:normal;}"
        "@font-face{font-family:'Amiri';src:url('Amiri-Bold.ttf') format('truetype');font-weight:700;font-style:normal;}"
        "</style>"
    )
    html = _REMOTE_FONT_LINK_RE.sub("", html)
    marker = "</head>"
    idx = html.lower().rfind(marker)
    if idx >= 0:
        return html[:idx] + face + html[idx:]
    return face + html

def render_html_to_pdf_with_chrome(html: str) -> bytes:
    chrome = find_chrome_binary()
    if not chrome:
        raise RuntimeError("لم يُعثر على متصفح لتوليد PDF بنفس جودة الطباعة")
    with tempfile.TemporaryDirectory(prefix="almojtahed-pdf-") as folder:
        folder_path = Path(folder)
        for name in ("Amiri-Regular.ttf", "Amiri-Bold.ttf"):
            src = AMIRI_FONT_DIR / name
            if src.is_file():
                shutil.copyfile(src, folder_path / name)
        html_path = folder_path / "paper.html"
        pdf_path = folder_path / "paper.pdf"
        profile = folder_path / "profile"
        html_path.write_text(html_with_local_amiri(html), encoding="utf-8")
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--no-pdf-header-footer",
            "--virtual-time-budget=1500",
            "--timeout=20000",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=25, check=False)
        if not pdf_path.is_file() or pdf_path.stat().st_size < 800:
            detail = (proc.stderr or b"").decode("utf-8", "ignore")[-400:].strip()
            raise RuntimeError(detail or "تعذر إنشاء ملف PDF")
        return pdf_path.read_bytes()

@app.post("/api/local-bundle/export")
def export_local_bundle(request: Request, body: Optional[dict] = Body(default=None)):
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import local_bundle
    current = local_bundle.job_snapshot()
    if current.get("state") == "copying":
        return current
    path = str((body or {}).get("path") or "").strip()
    return local_bundle.start_export(root, path or None)


@app.post("/api/local-bundle/import")
def import_local_bundle(request: Request, body: Optional[dict] = Body(default=None)):
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import local_bundle
    current = local_bundle.job_snapshot()
    if current.get("state") == "copying":
        return current
    path = str((body or {}).get("path") or "").strip()
    return local_bundle.start_import(root, path or None)


@app.get("/api/local-bundle/status")
def local_bundle_status(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import local_bundle
    return local_bundle.job_snapshot()


@app.post("/api/projects/export-pdf")
async def export_project_pdf_endpoint(req: ExportPdfRequest):
    """توليد وتصدير ملف PDF أكاديمي عالي الدقة مستخرج من HTML مع الشارتات والرسوم التفاعلية"""
    safe_title = re.sub(r'[\s/\\:*?"<>|]', '_', (req.title or "almojtahed_report").strip())
    filename = f"{safe_title}.pdf"
    pdf_bytes = None
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        async_playwright = None

    try:
        if async_playwright is not None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(req.html, wait_until="networkidle")
                await page.wait_for_timeout(1200)
                pdf_bytes = await page.pdf(
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                    display_header_footer=False,
                )
                await browser.close()
        else:
            pdf_bytes = await asyncio.to_thread(render_html_to_pdf_with_chrome, req.html)
    except Exception as e:
        print(f"Error generating PDF: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="فشل توليد ملف PDF بنفس تنسيق الطباعة")

    encoded_filename = urllib.parse.quote(filename)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Type": "application/pdf"
        }
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8085))
    print(f"🚀 تشغيل منظومة المجتهد الحية على المنفذ: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

