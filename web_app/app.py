import os
import re
import json
import time
import math
import asyncio
import threading
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from web_app.ai_service import (
    fetch_provider_models,
    call_ai_chat,
    reformulate_fiqh_query,
    plan_supplementary_searches,
    generate_word_report,
    export_to_craftmypdf,
    run_multi_agent_pipeline
)
from FlagEmbedding import BGEM3FlagModel
from sentence_transformers import SentenceTransformer, CrossEncoder
from transformers import AutoModelForSequenceClassification, AutoTokenizer, PreTrainedModel
from qdrant_client import QdrantClient
from qdrant_client.models import (
    SparseVector, Prefetch, FusionQuery, Fusion,
    Filter, FieldCondition, MatchValue, MatchAny
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SHAMELA_DATA_DIR", str(BASE_DIR / "shamela4_data")))
DB_PATH = Path(os.environ.get("SHAMELA_INDEX_DB", str(BASE_DIR / "shamela_index.db")))
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "shamela_corpus"
BADR_COLLECTION_NAME = "badr_corpus"
BADR_TCH_COLLECTION_NAME = "badr_tch_corpus"
BADR_ALL_TSH_COLLECTION_NAME = "badr_all_tsh_corpus"
BADR_MODEL_ID = "somayaeltanbouly/Badr_embedding_v0"
RERANKER_MODEL_ID = "BAAI/bge-reranker-v2-m3"

# Global state
state: Dict[str, Any] = {
    "model": None,
    "badr_model": None,
    "badr_model_status": "idle",
    "badr_model_error": None,
    "hf_token": None,
    "bm25_model": None,
    "reranker": None,
    "loaded_rerankers": {},
    "qdrant": None,
    "device": "mps" if torch.backends.mps.is_available() else "cpu",
    "db_conn": None
}

def get_hf_token() -> Optional[str]:
    """استرجاع توكن Hugging Face من الذاكرة أو متغيرات البيئة أو الملفات المحفوظة"""
    if state.get("hf_token"):
        return state["hf_token"]

    for k in ["BADR_HF_TOKEN", "HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HF_AUTH_TOKEN"]:
        val = (os.environ.get(k) or "").strip().strip("\"'")
        if val and not val.startswith("hf_..."):
            return val

    # البحث في ملفات التخزين الدائم
    paths_to_check = [
        Path(os.environ.get("DATA_DIR", "/app/data")) / "hf_token.txt",
        Path("/app/hf_token.txt"),
        Path("./data/hf_token.txt"),
        Path.home() / ".cache" / "huggingface" / "token",
        Path.home() / ".huggingface" / "token"
    ]
    for p in paths_to_check:
        try:
            if p.exists() and p.is_file():
                content = p.read_text(encoding="utf-8").strip().strip("\"'")
                if content and not content.startswith("hf_..."):
                    return content
        except Exception:
            pass
    return None

SUPPORTED_RERANKERS: Dict[str, Dict[str, Any]] = {
    "BAAI/bge-reranker-v2-m3": {
        "id": "BAAI/bge-reranker-v2-m3",
        "name": "BGE-Reranker-v2-m3 (متعدد اللغات - الافتراضي 8k)",
        "badge": "⭐ الافتراضي 8k",
        "short_name": "BGE-M3",
        "type": "cross_encoder",
        "description": "نموذج Cross-Encoder قوي جداً يدعم سياق نصوص حتى 8192 توكن مع 100+ لغة بما فيها العربية بدقة عالية."
    },
    "NAMAA-Space/Namaa-ARA-Reranker-V1": {
        "id": "NAMAA-Space/Namaa-ARA-Reranker-V1",
        "aliases": ["wahidmounir/Namaa-ARA-Reranker-V1-Q4_K_M-GGUF", "wahidmounir/Namaa-ARA-Reranker-V1", "Namaa-ARA-Reranker-V1"],
        "name": "نماء Namaa ARA Reranker V1 (مخصص للعربية)",
        "badge": "🇸🇦 نماء عربي",
        "short_name": "Namaa-ARA",
        "type": "cross_encoder",
        "description": "نموذج مدرب خصيصاً على مجموعات بيانات عربية ضخمة ومصادر شرعية ولغوية لإعادة تقييم النصوص."
    },
    "AzeerDev/arabic-reranker": {
        "id": "AzeerDev/arabic-reranker",
        "name": "AzeerDev Arabic Reranker (فائق السرعة - AraBERT)",
        "badge": "⚡ عربي سريع",
        "short_name": "AzeerDev",
        "type": "cross_encoder",
        "description": "نموذج خفيف وفائق السرعة مبني على معمارية AraBERT لإعادة ترتيب النصوص العربية فورياً."
    },
    "oddadmix/arabic-reranker-v1": {
        "id": "oddadmix/arabic-reranker-v1",
        "name": "oddadmix Arabic Reranker v1 (ثلاثيات عربية دقيقة)",
        "badge": "🔍 عربي دقيق",
        "short_name": "oddadmix",
        "type": "cross_encoder",
        "description": "نموذج مخصص للمحتوى العربي مدرب على أكثر من مليون ثلاثية نصية لتحقيق تطابق دلالي عالي."
    },
    "Alibaba-NLP/gte-multilingual-reranker-base": {
        "id": "Alibaba-NLP/gte-multilingual-reranker-base",
        "name": "Alibaba GTE Multilingual Base (علي بابا)",
        "badge": "🌐 Alibaba GTE",
        "short_name": "Alibaba-GTE",
        "type": "custom_gte",
        "description": "نموذج إعادة ترتيب متقدم من علي بابا يدعم سياق متعدد اللغات ونصوص طويلة مع معمارية RoPE."
    },
    "ZakariaAlMoktar/presto-qwen3-reranker-0.6b-arabic-ecommerce": {
        "id": "ZakariaAlMoktar/presto-qwen3-reranker-0.6b-arabic-ecommerce",
        "name": "Presto Qwen3 0.6B Arabic Reranker (مبني على Qwen3)",
        "badge": "🛍️ Presto Qwen3",
        "short_name": "Presto-Qwen3",
        "type": "cross_encoder",
        "description": "نموذج مبني على Qwen3 0.6B مع محول LoRA لترتيب النصوص العربية بكفاءة عالية."
    },
    "Qwen/Qwen3-Reranker-4B": {
        "id": "Qwen/Qwen3-Reranker-4B",
        "name": "Qwen3 Reranker 4B (النموذج العملاق - أقصى دقة)",
        "badge": "🚀 Qwen3 4B",
        "short_name": "Qwen3-4B",
        "type": "cross_encoder",
        "description": "أكبر وأقوى نموذج لترتيب النصوص مبني على معمارية Qwen3 الحديثة لتقديم أعلى استدلال دلالي."
    }
}

class GTERerankerWrapper:
    """مغلف متقدم لتشغيل نموذج Alibaba GTE Multilingual Reranker مع transformers 5+ بدقة كاملة وتوافق تام"""
    def __init__(self, model_id: str = "Alibaba-NLP/gte-multilingual-reranker-base", device: str = "cpu"):
        def get_extended_attention_mask(self, attention_mask, input_shape=None, device=None, dtype=None):
            if attention_mask.dim() == 3:
                extended = attention_mask[:, None, :, :]
            elif attention_mask.dim() == 2:
                extended = attention_mask[:, None, None, :]
            else:
                raise ValueError(f"Wrong shape for attention_mask {attention_mask.shape}")
            target_dtype = dtype or getattr(self, "dtype", torch.float32)
            extended = extended.to(dtype=target_dtype)
            return (1.0 - extended) * -1e4
        PreTrainedModel.get_extended_attention_mask = get_extended_attention_mask
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        # Use CPU or MPS with float32 to prevent half-precision NaN
        self.device = device
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_id, 
            trust_remote_code=True, 
            dtype=torch.float32
        ).to(self.device)
        self.model.eval()
        if hasattr(self.model, "new") and hasattr(self.model.new, "embeddings"):
            self.model.new.embeddings.register_buffer(
                "position_ids", 
                torch.arange(self.model.config.max_position_embeddings, device=self.device), 
                persistent=False
            )
        
    def predict(self, pairs: List[List[str]]) -> List[float]:
        if not pairs:
            return []
        inputs = self.tokenizer(pairs, padding=True, truncation=True, return_tensors="pt", max_length=512)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            out = self.model(**inputs)
            scores = torch.sigmoid(out.logits.view(-1)).float().cpu().tolist()
            if isinstance(scores, float):
                scores = [scores]
            return scores

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def create_resilient_qdrant_client() -> QdrantClient:
    """إنشاء اتصال مرن بمحرك Qdrant يكتشف تلقائياً العنوان الصحيح في بيئة Docker / Coolify / Localhost"""
    configured_url = os.environ.get("QDRANT_URL", "").strip()
    candidates = []
    if configured_url:
        candidates.append(configured_url)
        
    candidates.extend([
        "http://localhost:6333",
        "http://172.17.0.1:6333",        # Docker default bridge gateway to host (Linux/VPS)
        "http://host.docker.internal:6333", # Docker Desktop / Host internal
        "http://qdrant:6333",            # Docker Compose service name
    ])
    
    # محاولة استخدام الدومين أو الآي بي الخارجي للسيرفر (Hetzner / Coolify)
    for env_key in ("COOLIFY_FQDN", "DOMAIN", "SERVER_IP", "HOST_IP"):
        val = os.environ.get(env_key, "").strip()
        if val:
            clean = val.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
            if clean and f"http://{clean}:6333" not in candidates:
                candidates.append(f"http://{clean}:6333")

    # إضافة آي بي خادم المغني الفعلي
    if "http://5.75.141.129:6333" not in candidates:
        candidates.append("http://5.75.141.129:6333")
    if "http://mj.majalat.ai:6333" not in candidates:
        candidates.append("http://mj.majalat.ai:6333")

    for cand in candidates:
        try:
            client = QdrantClient(url=cand, timeout=2.5, check_compatibility=False)
            client.get_collections()
            print(f"✅ [Qdrant] Connected successfully to: {cand}")
            return client
        except Exception:
            continue
            
    fallback = configured_url or "http://localhost:6333"
    print(f"⚠️ [Qdrant] Failed to connect to probed candidates, fallback to: {fallback}")
    return QdrantClient(url=fallback, check_compatibility=False)

_badr_model_lock = threading.Lock()

def get_badr_model(force_reload: bool = False):
    """الحصول على نموذج تضمين بدر (768 أبعاد) مع قفل تزامن ودعم التوكن المباشر"""
    if not force_reload and state.get("badr_model") is not None:
        return state["badr_model"]
        
    with _badr_model_lock:
        if not force_reload and state.get("badr_model") is not None:
            return state["badr_model"]
            
        state["badr_model_status"] = "loading"
        token = get_hf_token()
        
        if token:
            try:
                print(f"⏳ Loading {BADR_MODEL_ID} with authenticated Hugging Face token...")
                model = SentenceTransformer(BADR_MODEL_ID, token=token, device="cpu")
                state["badr_model"] = model
                state["badr_model_status"] = "ready"
                state["badr_model_error"] = None
                print("✅ Badr Embedding Model loaded successfully!")
                return model
            except Exception as be:
                print(f"⚠️ Authenticated load of {BADR_MODEL_ID} failed: {be}")
                state["badr_model_error"] = f"فشلت المصادقة بالتوكن المقدم: {be}"
                state["badr_model_status"] = "error"
                return None
        else:
            # محاولة تحميل بدون توكن كاحتياط
            try:
                print(f"⏳ Trying {BADR_MODEL_ID} without token...")
                model = SentenceTransformer(BADR_MODEL_ID, device="cpu")
                state["badr_model"] = model
                state["badr_model_status"] = "ready"
                state["badr_model_error"] = None
                print("✅ Badr Embedding Model loaded anonymously!")
                return model
            except Exception as be2:
                print(f"⚠️ Anonymous load failed: {be2}")
                state["badr_model_error"] = (
                    "النموذج مقيّد (Gated Model) ويتطلب توكن Hugging Face مصرحاً به. "
                    "يرجى إدخال التوكن في لوحة الإعدادات أو عبر متغير البيئة HF_TOKEN."
                )
                state["badr_model_status"] = "error"
                return None

def get_bm25_model():
    """الحصول على نموذج FastEmbed BM25 مع تحميله عند الطلب"""
    if state.get("bm25_model") is None:
        try:
            from fastembed import SparseTextEmbedding
            print("⏳ Loading FastEmbed Qdrant/bm25 model...")
            state["bm25_model"] = SparseTextEmbedding(model_name="Qdrant/bm25")
            print("✅ FastEmbed BM25 Model loaded successfully!")
        except Exception as bme:
            print(f"⚠️ Error loading FastEmbed BM25 model: {bme}")
    return state.get("bm25_model")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 Initializing Shamela Search Engine on device: {state['device']}...")
    state["qdrant"] = create_resilient_qdrant_client()
    state["db_conn"] = get_db()
    
    # Preload Badr & BM25 models
    get_badr_model()
    get_bm25_model()

    # Load BGE-M3 model
    t0 = time.time()
    print("⏳ Loading BAAI/bge-m3 model...")
    try:
        state["model"] = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True, device=state["device"])
        print(f"✅ BGE-M3 Model loaded in {time.time()-t0:.2f}s!")
    except Exception as me:
        print(f"⚠️ Error loading BGE-M3 model: {me}")

    # Load BGE-Reranker-v2-m3 model
    t2 = time.time()
    print(f"⏳ Loading {RERANKER_MODEL_ID} cross-encoder reranker...")
    try:
        state["reranker"] = CrossEncoder(RERANKER_MODEL_ID, max_length=512, device=state["device"])
        state["loaded_rerankers"][RERANKER_MODEL_ID] = state["reranker"]
        print(f"✅ BGE Reranker Model loaded in {time.time()-t2:.2f}s!")
    except Exception as re:
        print(f"⚠️ Error loading Reranker model: {re}")
    
    yield
    
    if state["db_conn"]:
        state["db_conn"].close()
    print("Shutting down engine...")

app = FastAPI(title="المكتبة الشاملة — البحث الدلالي والهجين", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HFTokenPayload(BaseModel):
    token: str

@app.get("/healthz")
@app.get("/health")
@app.get("/api/health")
async def health_check():
    tok = get_hf_token()
    return {
        "status": "ok",
        "app": "shamela",
        "version": "v4.2-badr768",
        "badr_model_loaded": state.get("badr_model") is not None,
        "badr_model_status": state.get("badr_model_status", "unknown"),
        "badr_model_error": state.get("badr_model_error"),
        "hf_token_present": bool(tok),
        "hf_token_prefix": (tok[:7] + "..." + tok[-4:]) if (tok and len(tok) > 12) else None,
        "device": state.get("device", "cpu")
    }

@app.get("/api/settings/hf-token")
async def get_hf_token_status():
    tok = get_hf_token()
    return {
        "has_token": bool(tok),
        "token_prefix": (tok[:7] + "..." + tok[-4:]) if (tok and len(tok) > 12) else None,
        "model_status": state.get("badr_model_status", "unknown"),
        "model_loaded": state.get("badr_model") is not None,
        "error": state.get("badr_model_error")
    }

@app.post("/api/settings/hf-token")
async def save_hf_token(payload: HFTokenPayload):
    new_token = payload.token.strip().strip("\"'")
    if not new_token or not new_token.startswith("hf_"):
        raise HTTPException(status_code=400, detail="صيغة التوكن غير صحيحة. يجب أن يبدأ بـ hf_")
        
    state["hf_token"] = new_token
    os.environ["HF_TOKEN"] = new_token
    os.environ["BADR_HF_TOKEN"] = new_token
    
    # حفظ في ملف دائم للتخزين
    for d_path in [Path(os.environ.get("DATA_DIR", "/app/data")), Path("./data")]:
        try:
            d_path.mkdir(parents=True, exist_ok=True)
            (d_path / "hf_token.txt").write_text(new_token, encoding="utf-8")
        except Exception:
            pass
            
    # إعادة تحميل النموذج فوراً
    model = get_badr_model(force_reload=True)
    if not model:
        err = state.get("badr_model_error") or "فشلت المصادقة مع Hugging Face"
        raise HTTPException(status_code=400, detail=f"تم حفظ التوكن ولكن فشل تحميل النموذج: {err}")
        
    return {
        "status": "success",
        "message": "تم حفظ التوكن ومصادقته وتحميل نموذج بدر (768 أبعاد) بنجاح!",
        "model_id": BADR_MODEL_ID,
        "dimension": 768
    }

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status": "error"}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "status": "error"}
    )

# Mount static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

class SearchRequest(BaseModel):
    query: str
    mode: str = "hybrid" # hybrid, dense, sparse
    collection_name: Optional[str] = "badr_all_tsh_corpus"
    category_id: Optional[int] = None
    book_titles: Optional[List[str]] = None
    limit: int = 15
    use_reranker: Optional[bool] = False
    reranker_limit: Optional[int] = None
    reranker_model: Optional[str] = "BAAI/bge-reranker-v2-m3"

def normalize_reranker_id(model_id: Optional[str]) -> str:
    if not model_id:
        return RERANKER_MODEL_ID
    model_id = model_id.strip()
    for key, info in SUPPORTED_RERANKERS.items():
        if model_id == key or model_id in info.get("aliases", []):
            return key
    return model_id

def get_or_load_reranker(model_id: Optional[str] = None):
    """استرجاع نموذج الفرز المتقاطع المطلوب أو تحميله بالطلب (Lazy Loading) مع التخزين المؤقت"""
    canonical_id = normalize_reranker_id(model_id)
    if "loaded_rerankers" not in state:
        state["loaded_rerankers"] = {}
    
    if canonical_id in state["loaded_rerankers"]:
        return state["loaded_rerankers"][canonical_id], canonical_id
        
    if canonical_id == RERANKER_MODEL_ID and state.get("reranker"):
        state["loaded_rerankers"][canonical_id] = state["reranker"]
        return state["reranker"], canonical_id

    print(f"⏳ Lazy-loading reranker model: {canonical_id} on {state['device']}...")
    t_load = time.time()
    try:
        model_info = SUPPORTED_RERANKERS.get(canonical_id, {})
        if model_info.get("type") == "custom_gte" or "gte" in canonical_id.lower():
            reranker = GTERerankerWrapper(model_id=canonical_id, device=state["device"])
        else:
            reranker = CrossEncoder(canonical_id, max_length=512, device=state["device"])
        
        state["loaded_rerankers"][canonical_id] = reranker
        print(f"✅ Reranker model {canonical_id} loaded successfully in {time.time()-t_load:.2f}s!")
        return reranker, canonical_id
    except Exception as e:
        print(f"⚠️ Failed to load reranker {canonical_id}: {e}. Falling back to default {RERANKER_MODEL_ID}.")
        if state.get("reranker"):
            return state["reranker"], RERANKER_MODEL_ID
        return None, canonical_id

def apply_reranking(query: str, items: List[Dict[str, Any]], limit: int, model_name: Optional[str] = None) -> Tuple[List[Dict[str, Any]], float, str]:
    """إعادة ترتيب النتائج بدقة فائقة باستخدام نموذج الـ Reranker المختار"""
    reranker, used_model_id = get_or_load_reranker(model_name)
    if not items or not reranker:
        return items[:limit], 0.0, (used_model_id or RERANKER_MODEL_ID)
    
    t0 = time.time()
    pairs = []
    for item in items:
        text = item.get("full_body") or item.get("snippet") or item.get("title_ar") or ""
        clean_text = re.sub(r"<[^>]+>", " ", text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        pairs.append([query, clean_text[:1200]])
    
    try:
        rerank_scores = reranker.predict(pairs)
        for idx, item in enumerate(items):
            s = float(rerank_scores[idx])
            if s > 1.0 or s < 0.0:
                prob = 1.0 / (1.0 + math.exp(-s)) if s > -50 else 0.0
                item["rerank_score"] = round(prob, 4)
                item["raw_rerank_score"] = round(s, 4)
            else:
                item["rerank_score"] = round(s, 4)
            item["vector_score"] = item.get("score", 0.0)
            item["score"] = item["rerank_score"]
            
        items.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    except Exception as e:
        print(f"⚠️ Error during reranking with {used_model_id}: {e}")
        
    t_rerank = time.time() - t0
    return items[:limit], t_rerank, used_model_id

def normalize_arabic(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text) # tashkeel
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"[ى]", "ي", text)
    text = re.sub(r"[ة]", "ه", text)
    return text

def highlight_terms(text: str, query: str) -> str:
    if not text or not query:
        return text
    # Clean HTML tags first
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    
    words = [w for w in re.findall(r"[\u0621-\u064A]{3,}", query) if w not in {
        "في", "من", "على", "إلى", "عن", "مع", "هذا", "هذه", "ذلك", "كان", "قال", "ماذا", "هل"
    }]
    if not words:
        return clean[:450] + ("..." if len(clean) > 450 else "")
    
    # Locate first occurrence of any keyword for snippet window
    norm_clean = normalize_arabic(clean)
    first_idx = -1
    for w in words:
        idx = norm_clean.find(normalize_arabic(w))
        if idx != -1:
            if first_idx == -1 or idx < first_idx:
                first_idx = idx
                
    start = max(0, first_idx - 100) if first_idx != -1 else 0
    end = min(len(clean), start + 450)
    snippet = clean[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(clean):
        snippet = snippet + "..."

    # Highlight occurrences
    pattern = "|".join(re.escape(w) for w in words)
    highlighted = re.sub(f"({pattern})", r"<mark>\1</mark>", snippet, flags=re.IGNORECASE)
    return highlighted

def fetch_page_content(rel_path: str, part: Optional[str], page_num: Optional[int], footnotes_match: Optional[str] = None) -> Dict[str, Any]:
    """Finds exact page content from pages.jsonl on disk."""
    if not rel_path:
        return {"body": "", "footnotes": None}
    
    pages_file = BASE_DIR / rel_path / "pages.jsonl"
    if not pages_file.exists():
        return {"body": "", "footnotes": None}
    
    part_str = str(part) if part is not None else None
    
    try:
        with open(pages_file, "r", encoding="utf-8") as f:
            for line in f:
                p = json.loads(line)
                p_page = p.get("page_num")
                p_part = str(p.get("part")) if p.get("part") is not None else None
                
                # Check page match
                if page_num is not None and p_page == page_num:
                    if part_str is None or p_part == part_str or part_str == "None":
                        # If footnotes match is given, verify it to be 100% sure in multi-page collisions
                        if footnotes_match and p.get("footnotes"):
                            if footnotes_match[:30] in p.get("footnotes")[:60]:
                                return p
                        return p
        
        # Fallback by page_num only
        if page_num is not None:
            with open(pages_file, "r", encoding="utf-8") as f:
                for line in f:
                    p = json.loads(line)
                    if p.get("page_num") == page_num:
                        return p
    except Exception as e:
        print(f"Error reading page {rel_path}: {e}")
        
    return {"body": "", "footnotes": None}

def find_book_page(rel_path: str, page_num: Any, text_hint: Optional[str] = None, part: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Locates page in book's pages.jsonl with text priority then page_num/part."""
    if not rel_path:
        return None
    pages_file = BASE_DIR / rel_path / "pages.jsonl"
    if not pages_file.exists():
        return None
        
    part_str = str(part).strip() if part not in (None, "", "None", "null", "undefined") else None
    page_int = int(page_num) if page_num not in (None, "", "None") else None
    
    phrases = []
    if text_hint:
        clean_sub = re.sub(r"<[^>]+>", " ", text_hint)
        phrases = [p.strip()[:35] for p in re.findall(r'[\u0621-\u064A\s]{12,}', clean_sub) if len(p.strip()) >= 12]

    first_page_match = None
    try:
        with open(pages_file, "r", encoding="utf-8") as f:
            for line in f:
                if phrases:
                    for phrase in phrases[:3]:
                        if phrase in line:
                            return json.loads(line)
                if page_int is not None and f'"page_num":{page_int},' in line:
                    p = json.loads(line)
                    if part_str is not None:
                        if str(p.get("part")).strip() == part_str:
                            return p
                    elif first_page_match is None:
                        first_page_match = p
    except Exception as e:
        print(f"Error in find_book_page: {e}")
        
    return first_page_match

@app.get("/api/stats")
async def get_stats():
    if state.get("qdrant") is None:
        state["qdrant"] = create_resilient_qdrant_client()
    qdrant = state["qdrant"]
    cur = state["db_conn"].cursor()
    cur.execute("SELECT COUNT(*) FROM books")
    total_books = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM categories")
    total_cats = cur.fetchone()[0]
    
    colls_info = {}
    for c_name in [BADR_ALL_TSH_COLLECTION_NAME, BADR_COLLECTION_NAME, BADR_TCH_COLLECTION_NAME, COLLECTION_NAME]:
        try:
            c = qdrant.get_collection(c_name)
            colls_info[c_name] = {
                "status": str(c.status),
                "points_count": c.points_count,
                "vectors_count": c.indexed_vectors_count
            }
        except Exception:
            pass

    badr_all_data = colls_info.get(BADR_ALL_TSH_COLLECTION_NAME, {})
    badr_data = colls_info.get(BADR_COLLECTION_NAME, {})
    shamela_data = colls_info.get(COLLECTION_NAME, {})
    total_pts = badr_all_data.get("points_count") or badr_data.get("points_count") or shamela_data.get("points_count") or 7577481
    
    return {
        "status": "green",
        "indexed_points": total_pts,
        "indexed_vectors": total_pts,
        "total_books": total_books,
        "total_categories": total_cats,
        "device": state["device"],
        "active_collection": BADR_ALL_TSH_COLLECTION_NAME,
        "collections": colls_info,
        "models": {
            "badr_all_tsh": f"{BADR_MODEL_ID} + FastEmbed BM25 (Dense 768 + Sparse RRF - بالتشكيل)",
            "badr": f"{BADR_MODEL_ID} (768d Cosine - مشكول)",
            "badr_tch": f"{BADR_MODEL_ID} (768d Cosine - بدون تشكيل)",
            "shamela": "BAAI/bge-m3 (Dense 1024 + Sparse RRF)",
            "reranker": f"{RERANKER_MODEL_ID} (Cross-Encoder 8k)",
            "available_rerankers": list(SUPPORTED_RERANKERS.keys())
        }
    }

@app.get("/api/rerankers")
async def get_rerankers():
    """الحصول على قائمة نماذج إعادة الترتيب (Rerankers) المدعومة وحالة تحميلها"""
    loaded_list = list(state.get("loaded_rerankers", {}).keys())
    models_res = []
    for m_id, info in SUPPORTED_RERANKERS.items():
        item = dict(info)
        item["is_loaded"] = m_id in loaded_list
        item["is_default"] = m_id == RERANKER_MODEL_ID
        models_res.append(item)
    return {
        "models": models_res,
        "default": RERANKER_MODEL_ID,
        "loaded": loaded_list
    }

@app.get("/api/categories")
async def get_categories():
    cur = state["db_conn"].cursor()
    cur.execute("SELECT category_id, category_name_ar, folder_name, book_count FROM categories ORDER BY category_id ASC")
    rows = cur.fetchall()
    return [{"category_id": r[0], "category_name_ar": r[1], "folder_name": r[2], "book_count": r[3]} for r in rows]

@app.get("/api/books")
async def get_books(category_id: Optional[int] = None, q: Optional[str] = None, limit: int = 3000):
    cur = state["db_conn"].cursor()
    query_parts = ["SELECT book_id, title_ar, category_name_ar, main_author_name_ar, main_author_death_hijri, volume_count_observed, rel_path FROM books WHERE 1=1"]
    params = []
    
    if category_id is not None and category_id > 0:
        query_parts.append("AND category_id = ?")
        params.append(category_id)
        
    if q:
        query_parts.append("AND (title_ar LIKE ? OR main_author_name_ar LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
        
    query_parts.append("ORDER BY book_id ASC LIMIT ?")
    params.append(limit)
    
    cur.execute(" ".join(query_parts), params)
    rows = cur.fetchall()
    return [{
        "book_id": r[0],
        "title_ar": r[1],
        "category_name_ar": r[2],
        "author_name": r[3],
        "death_hijri": r[4],
        "volume_count": r[5],
        "rel_path": r[6]
    } for r in rows]

def execute_search_sync(req: Union[SearchRequest, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(req, dict):
        req = SearchRequest(**req)
    t0 = time.time()
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    if state.get("qdrant") is None:
        state["qdrant"] = create_resilient_qdrant_client()
    if state.get("db_conn") is None:
        state["db_conn"] = get_db()
    qdrant = state["qdrant"]

    def safe_query_points(**kwargs):
        nonlocal qdrant
        try:
            return qdrant.query_points(**kwargs)
        except Exception as q_err:
            err_str = str(q_err)
            if "Connection refused" in err_str or "111" in err_str or "ResponseHandlingException" in type(q_err).__name__:
                print(f"⚠️ [Qdrant] Connection refused on active endpoint. Auto-discovering reachable Qdrant...")
                qdrant = create_resilient_qdrant_client()
                state["qdrant"] = qdrant
                return qdrant.query_points(**kwargs)
            raise q_err

    target_coll = req.collection_name or BADR_ALL_TSH_COLLECTION_NAME
    # توجيه جميع استعلامات الشاملة التراثية إلى مجموعة بدر badr_all_tsh_corpus (768 أبعاد)
    is_badr_target = target_coll in (BADR_ALL_TSH_COLLECTION_NAME, BADR_COLLECTION_NAME, BADR_TCH_COLLECTION_NAME, COLLECTION_NAME, "badr_all_tsh_colc")
    if is_badr_target:
        target_coll = BADR_ALL_TSH_COLLECTION_NAME
        
    final_limit = req.reranker_limit if (req.use_reranker and req.reranker_limit) else req.limit
    fetch_limit = min(max(req.limit, final_limit * 3, 30), 200) if req.use_reranker else req.limit
    
    # ===================== مسار 1: لقطات بدر (badr_all_tsh_corpus الهجين، badr_corpus، badr_tch_corpus) =====================
    if is_badr_target or target_coll in (BADR_ALL_TSH_COLLECTION_NAME, BADR_COLLECTION_NAME, BADR_TCH_COLLECTION_NAME):
        badr_model = get_badr_model()
        if not badr_model:
            err_detail = state.get("badr_model_error") or "النموذج قيد التنزيل الأولي من Hugging Face في الذاكرة"
            raise HTTPException(
                status_code=503,
                detail=f"نموذج التضمين (Badr Embedding 768) غير جاهز بعد: {err_detail}. يرجى الانتظار ثوانٍ معدودة."
            )
        t_enc0 = time.time()
        enc_query = normalize_arabic(query) if target_coll == BADR_TCH_COLLECTION_NAME else query
        dense_vec = badr_model.encode(enc_query).tolist()
        
        sparse_vec = None
        bm25_model = get_bm25_model()
        if target_coll == BADR_ALL_TSH_COLLECTION_NAME and bm25_model:
            try:
                sparse_emb = list(bm25_model.embed([query]))[0]
                sparse_vec = SparseVector(indices=sparse_emb.indices.tolist(), values=sparse_emb.values.tolist())
            except Exception as se:
                print(f"Error generating BM25 sparse vector: {se}")
        t_enc = time.time() - t_enc0
        
        # 2. بناء فلاتر الكتب والتصنيفات لـ badr (حقل book بصيغة slug)
        must_conditions = []
        if req.book_titles and len(req.book_titles) > 0:
            matching_slugs = set()
            cur_slugs = state["db_conn"].cursor()
            for bt in req.book_titles:
                bt_clean = bt.strip()
                if not bt_clean:
                    continue
                cur_slugs.execute("""
                    SELECT rel_path FROM books 
                    WHERE title_ar = ? 
                       OR title_ar LIKE ? 
                       OR title_ar LIKE ? 
                       OR title_ar LIKE ? 
                       OR title_ar LIKE ?
                    LIMIT 30
                """, (bt_clean, f"{bt_clean} - %", f"{bt_clean} = %", f"% = {bt_clean}%", f"{bt_clean} %"))
                for r in cur_slugs.fetchall():
                    val = r["rel_path"] if hasattr(r, "keys") else r[0]
                    if val:
                        matching_slugs.add(val.split("/")[-1])
            if matching_slugs:
                must_conditions.append(
                    FieldCondition(key="book", match=MatchAny(any=list(matching_slugs)))
                )
        elif req.category_id and req.category_id > 0:
            cur_cat = state["db_conn"].cursor()
            cur_cat.execute("SELECT rel_path FROM books WHERE category_id = ?", (req.category_id,))
            cat_slugs = [r["rel_path"].split("/")[-1] for r in cur_cat.fetchall() if r["rel_path"]]
            if cat_slugs:
                must_conditions.append(
                    FieldCondition(key="book", match=MatchAny(any=cat_slugs))
                )
                
        qdrant_filter = Filter(must=must_conditions) if must_conditions else None
        
        # 3. الاستعلام من Qdrant
        t_search0 = time.time()
        if target_coll == BADR_ALL_TSH_COLLECTION_NAME:
            if req.mode == "dense" or not sparse_vec:
                search_res = safe_query_points(
                    collection_name=target_coll,
                    query=dense_vec,
                    using="text-dense",
                    query_filter=qdrant_filter,
                    limit=fetch_limit,
                    with_payload=True
                )
            elif req.mode == "sparse":
                search_res = safe_query_points(
                    collection_name=target_coll,
                    query=sparse_vec,
                    using="text-sparse",
                    query_filter=qdrant_filter,
                    limit=fetch_limit,
                    with_payload=True
                )
            else: # hybrid (default)
                search_res = safe_query_points(
                    collection_name=target_coll,
                    prefetch=[
                        Prefetch(query=dense_vec, using="text-dense", filter=qdrant_filter, limit=fetch_limit),
                        Prefetch(query=sparse_vec, using="text-sparse", filter=qdrant_filter, limit=fetch_limit),
                    ],
                    query=FusionQuery(fusion=Fusion.RRF),
                    limit=fetch_limit,
                    with_payload=True
                )
        else:
            # badr_corpus / badr_tch_corpus (unnamed dense vector)
            search_res = safe_query_points(
                collection_name=target_coll,
                query=dense_vec,
                query_filter=qdrant_filter,
                limit=fetch_limit,
                with_payload=True
            )
        # في حال لم يرجع فلتر التصنيف أو الكتب أي نتيجة نظراً لاختلاف صيغة المعرفات في السناب شوت، نعيد الاستعلام الموسع تلقائياً
        if not search_res.points and qdrant_filter is not None:
            if target_coll == BADR_ALL_TSH_COLLECTION_NAME:
                if req.mode == "dense" or not sparse_vec:
                    search_res = safe_query_points(
                        collection_name=target_coll,
                        query=dense_vec,
                        using="text-dense",
                        limit=fetch_limit,
                        with_payload=True
                    )
                elif req.mode == "sparse":
                    search_res = safe_query_points(
                        collection_name=target_coll,
                        query=sparse_vec,
                        using="text-sparse",
                        limit=fetch_limit,
                        with_payload=True
                    )
                else:
                    search_res = safe_query_points(
                        collection_name=target_coll,
                        prefetch=[
                            Prefetch(query=dense_vec, using="text-dense", limit=fetch_limit),
                            Prefetch(query=sparse_vec, using="text-sparse", limit=fetch_limit),
                        ],
                        query=FusionQuery(fusion=Fusion.RRF),
                        limit=fetch_limit,
                        with_payload=True
                    )
            else:
                search_res = safe_query_points(
                    collection_name=target_coll,
                    query=dense_vec,
                    limit=fetch_limit,
                    with_payload=True
                )

        t_search = time.time() - t_search0
        
        # 4. إثراء النتائج ببيانات SQLite والمتن
        cur = state["db_conn"].cursor()
        enriched = []
        for hit in search_res.points:
            p = hit.payload or {}
            b_slug = str(p.get("book") or p.get("book_slug") or "").strip()
            
            # 1. استخراج معرف الكتاب (book_id)
            book_id = 0
            if p.get("book_id") is not None:
                try:
                    book_id = int(p.get("book_id"))
                except (ValueError, TypeError):
                    book_id = 0
            if not book_id and b_slug:
                if "__" in b_slug:
                    try:
                        book_id = int(b_slug.split("__")[0])
                    except (ValueError, TypeError):
                        book_id = 0
                elif b_slug.isdigit():
                    book_id = int(b_slug)
            
            # 2. استخراج الصفحة والجزء والنص
            raw_page = p.get("page") if p.get("page") is not None else p.get("page_num")
            page_num = str(raw_page).strip() if raw_page is not None else ""
            raw_part = p.get("part") if p.get("part") is not None else p.get("volume")
            resolved_part = str(raw_part).strip() if raw_part not in (None, "None", "null", "") else ""
            raw_body = p.get("text") or p.get("body") or p.get("full_body") or p.get("snippet") or ""

            # 3. جلب بيانات التوثيق من SQLite
            b_row = None
            if book_id > 0:
                try:
                    cur.execute(
                        "SELECT book_id, title_ar, category_name_ar, main_author_name_ar, main_author_death_hijri, rel_path, betaka_text FROM books WHERE book_id = ? LIMIT 1",
                        (book_id,)
                    )
                    b_row = cur.fetchone()
                except Exception:
                    b_row = None

            cand_title = p.get("title_ar") or p.get("title") or p.get("book_title") or ""
            if not b_row and cand_title:
                try:
                    cur.execute(
                        "SELECT book_id, title_ar, category_name_ar, main_author_name_ar, main_author_death_hijri, rel_path, betaka_text FROM books WHERE title_ar = ? LIMIT 1",
                        (cand_title,)
                    )
                    b_row = cur.fetchone()
                except Exception:
                    b_row = None

            if not b_row and b_slug and "__" in b_slug:
                slug_clean = b_slug.split("__", 1)[1].replace("-", " ").strip()
                try:
                    cur.execute(
                        "SELECT book_id, title_ar, category_name_ar, main_author_name_ar, main_author_death_hijri, rel_path, betaka_text FROM books WHERE title_ar LIKE ? LIMIT 1",
                        (f"%{slug_clean}%",)
                    )
                    b_row = cur.fetchone()
                except Exception:
                    b_row = None

            if b_row:
                book_id = b_row["book_id"]
                title = b_row["title_ar"] or cand_title or b_slug
                cat_name = b_row["category_name_ar"] or p.get("category_name_ar") or p.get("category_name") or ""
                author_name = b_row["main_author_name_ar"] or p.get("author_name") or p.get("author") or ""
                death_hijri = b_row["main_author_death_hijri"] if b_row["main_author_death_hijri"] is not None else p.get("death_hijri")
                rel_path = b_row["rel_path"] or p.get("rel_path") or ""
                betaka_text = b_row["betaka_text"] if (b_row and "betaka_text" in b_row.keys() and b_row["betaka_text"]) else (p.get("betaka_text") or "")
            else:
                clean_slug_title = b_slug.split("__", 1)[1].replace("-", " ") if "__" in b_slug else b_slug
                title = cand_title or clean_slug_title or (f"كتاب رقم {book_id}" if book_id else "كتاب من الشاملة")
                cat_name = p.get("category_name_ar") or p.get("category_name") or ""
                author_name = p.get("author_name") or p.get("author") or ""
                death_hijri = p.get("death_hijri")
                rel_path = p.get("rel_path") or ""
                betaka_text = p.get("betaka_text") or p.get("betaka") or ""

            footnotes = p.get("footnotes") or ""
            if rel_path:
                try:
                    found_page = find_book_page(rel_path, page_num, raw_body)
                    if found_page:
                        if found_page.get("part"):
                            resolved_part = str(found_page.get("part"))
                        if found_page.get("page_num") is not None:
                            page_num = found_page.get("page_num")
                        if found_page.get("footnotes"):
                            footnotes = found_page.get("footnotes")
                        if found_page.get("body"):
                            raw_body = found_page.get("body")
                    elif not raw_body or len(raw_body) <= 300:
                        page_data = fetch_page_content(rel_path, "", page_num, "")
                        if page_data and page_data.get("body"):
                            raw_body = page_data.get("body")
                            footnotes = page_data.get("footnotes", "")
                except Exception:
                    pass

            snippet = highlight_terms(raw_body, query) if raw_body else ""
            
            enriched.append({
                "point_id": hit.id,
                "score": round(hit.score, 4) if hit.score else 0.0,
                "book_id": book_id,
                "title_ar": title,
                "category_id": req.category_id or p.get("category_id"),
                "category_name_ar": cat_name,
                "author_name": author_name,
                "death_hijri": death_hijri,
                "part": resolved_part,
                "page_num": page_num,
                "snippet": snippet,
                "full_body": raw_body,
                "footnotes": footnotes,
                "has_footnotes": bool(footnotes),
                "betaka_text": betaka_text,
                "rel_path": rel_path
            })
            
        t_rerank = 0.0
        used_reranker_id = None
        if req.use_reranker:
            enriched, t_rerank, used_reranker_id = apply_reranking(query, enriched, final_limit, req.reranker_model)
            
        if target_coll == BADR_ALL_TSH_COLLECTION_NAME:
            mode_prefix = f"Hybrid (Badr Dense 768 + BM25 Sparse - {req.mode})"
        elif target_coll == BADR_TCH_COLLECTION_NAME:
            mode_prefix = "dense (Badr بدون تشكيل)"
        else:
            mode_prefix = "dense (Badr Fiqh مشكول)"
            
        reranker_short = SUPPORTED_RERANKERS.get(used_reranker_id, {}).get("short_name", "Reranker") if used_reranker_id else "Reranker"
        mode_label = f"{mode_prefix} + Reranker ({reranker_short})" if (req.use_reranker and used_reranker_id) else mode_prefix

        return {
            "took_ms": round((time.time() - t0) * 1000, 1),
            "encoding_ms": round(t_enc * 1000, 1),
            "search_ms": round(t_search * 1000, 1),
            "rerank_ms": round(t_rerank * 1000, 1) if req.use_reranker else None,
            "reranker_used": bool(req.use_reranker and used_reranker_id),
            "reranker_model": used_reranker_id if req.use_reranker else None,
            "mode": mode_label,
            "collection": target_coll,
            "total": len(enriched),
            "results": enriched
        }

    # ===================== مسار 2: فهرس الشاملة BGE-M3 (shamela_corpus) =====================
    model = state["model"]
    
    # 1. Encode query
    t_enc0 = time.time()
    enc_res = model.encode(query, return_dense=True, return_sparse=True)
    dense_vec = enc_res['dense_vecs'].tolist()
    lex_weights = enc_res['lexical_weights']
    sparse_indices = [int(k) for k in lex_weights.keys()]
    sparse_values = [float(v) for v in lex_weights.values()]
    t_enc = time.time() - t_enc0
    
    # 2. Build filters if specified
    must_conditions = []
    if req.book_titles and len(req.book_titles) > 0:
        expanded_titles = set()
        cur_expand = state["db_conn"].cursor()
        for bt in req.book_titles:
            bt_clean = bt.strip()
            if not bt_clean:
                continue
            expanded_titles.add(bt_clean)
            try:
                cur_expand.execute("""
                    SELECT title_ar FROM books 
                    WHERE title_ar = ? 
                       OR title_ar LIKE ? 
                       OR title_ar LIKE ? 
                       OR title_ar LIKE ? 
                       OR title_ar LIKE ?
                    LIMIT 30
                """, (bt_clean, f"{bt_clean} - %", f"{bt_clean} = %", f"% = {bt_clean}%", f"{bt_clean} %"))
                for r in cur_expand.fetchall():
                    val = r["title_ar"] if hasattr(r, "keys") else r[0]
                    expanded_titles.add(val)
            except Exception as expand_err:
                print(f"Error expanding book title '{bt_clean}': {expand_err}")

        must_conditions.append(
            FieldCondition(key="title_ar", match=MatchAny(any=list(expanded_titles)))
        )
    elif req.category_id and req.category_id > 0:
        must_conditions.append(
            FieldCondition(key="category_id", match=MatchValue(value=req.category_id))
        )
        
    qdrant_filter = Filter(must=must_conditions) if must_conditions else None
        
    # 3. Query Qdrant
    t_search0 = time.time()
    
    # فحص أسماء المتجهات في المجموعة لتفادي Wrong input: Not existing vector name error
    coll_dense_name = "dense"
    coll_sparse_name = "sparse"
    try:
        coll_info = qdrant.get_collection(target_coll or COLLECTION_NAME)
        v_dict = coll_info.config.params.vectors if coll_info and coll_info.config and coll_info.config.params else {}
        if isinstance(v_dict, dict):
            if "text-dense" in v_dict:
                coll_dense_name = "text-dense"
            elif "dense" in v_dict:
                coll_dense_name = "dense"
        sv_dict = coll_info.config.params.sparse_vectors if coll_info and coll_info.config and coll_info.config.params else {}
        if isinstance(sv_dict, dict) and "text-sparse" in sv_dict:
            coll_sparse_name = "text-sparse"
    except Exception:
        pass
    
    if req.mode == "dense":
        search_res = safe_query_points(
            collection_name=target_coll or COLLECTION_NAME,
            query=dense_vec,
            using=coll_dense_name,
            query_filter=qdrant_filter,
            limit=fetch_limit,
            with_payload=True
        )
    elif req.mode == "sparse":
        search_res = safe_query_points(
            collection_name=target_coll or COLLECTION_NAME,
            query=SparseVector(indices=sparse_indices, values=sparse_values),
            using=coll_sparse_name,
            query_filter=qdrant_filter,
            limit=fetch_limit,
            with_payload=True
        )
    else: # Hybrid RRF
        search_res = safe_query_points(
            collection_name=target_coll or COLLECTION_NAME,
            prefetch=[
                Prefetch(query=dense_vec, using=coll_dense_name, filter=qdrant_filter, limit=fetch_limit * 2),
                Prefetch(query=SparseVector(indices=sparse_indices, values=sparse_values), using=coll_sparse_name, filter=qdrant_filter, limit=fetch_limit * 2),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=fetch_limit,
            with_payload=True
        )
    t_search = time.time() - t_search0
    
    # 4. Enrich results with SQLite metadata and text on disk
    cur = state["db_conn"].cursor()
    enriched = []
    
    for hit in search_res.points:
        p = hit.payload or {}
        title = p.get("title_ar", "")
        part = p.get("part")
        page_num = p.get("page_num")
        cat_id = p.get("category_id")
        footnotes = p.get("footnotes")
        betaka = p.get("betaka_text")
        
        # Find book in SQLite
        cur.execute(
            "SELECT book_id, title_ar, category_name_ar, main_author_name_ar, main_author_death_hijri, rel_path, betaka_text FROM books WHERE title_ar = ? LIMIT 1",
            (title,)
        )
        b_row = cur.fetchone()
        
        book_id = b_row["book_id"] if b_row else 0
        cat_name = b_row["category_name_ar"] if b_row else ""
        author_name = b_row["main_author_name_ar"] if b_row else ""
        death_hijri = b_row["main_author_death_hijri"] if b_row else None
        rel_path = b_row["rel_path"] if b_row else ""
        if not betaka and b_row and "betaka_text" in b_row.keys():
            betaka = b_row["betaka_text"] or ""
        
        # Fetch page text
        page_data = fetch_page_content(rel_path, part, page_num, footnotes)
        raw_body = page_data.get("body", "")
        snippet = highlight_terms(raw_body, query) if raw_body else ""
        
        enriched.append({
            "point_id": hit.id,
            "score": round(hit.score, 4) if hit.score else 0.0,
            "book_id": book_id,
            "title_ar": title,
            "category_id": cat_id,
            "category_name_ar": cat_name,
            "author_name": author_name,
            "death_hijri": death_hijri,
            "part": part if part not in (None, "None") else "",
            "page_num": page_num,
            "snippet": snippet,
            "full_body": raw_body,
            "footnotes": page_data.get("footnotes") or footnotes or "",
            "has_footnotes": bool(page_data.get("footnotes") or footnotes),
            "betaka_text": betaka or "",
            "rel_path": rel_path
        })
        
    t_rerank = 0.0
    used_reranker_id = None
    if req.use_reranker:
        enriched, t_rerank, used_reranker_id = apply_reranking(query, enriched, final_limit, req.reranker_model)

    reranker_short = SUPPORTED_RERANKERS.get(used_reranker_id, {}).get("short_name", "Reranker") if used_reranker_id else "Reranker"
    mode_label = f"{req.mode} + Reranker ({reranker_short})" if (req.use_reranker and used_reranker_id) else req.mode

    return {
        "took_ms": round((time.time() - t0) * 1000, 1),
        "encoding_ms": round(t_enc * 1000, 1),
        "search_ms": round(t_search * 1000, 1),
        "rerank_ms": round(t_rerank * 1000, 1) if req.use_reranker else None,
        "reranker_used": bool(req.use_reranker and used_reranker_id),
        "reranker_model": used_reranker_id if req.use_reranker else None,
        "mode": mode_label,
        "collection": COLLECTION_NAME,
        "total": len(enriched),
        "results": enriched
    }

@app.post("/api/search")
async def search(req: SearchRequest):
    return execute_search_sync(req)

@app.get("/api/page")
async def get_page(
    rel_path: str = Query(...),
    part: Optional[str] = Query(None),
    page_num: Optional[int] = Query(None),
    point_id: Optional[str] = Query(None),
    text_hint: Optional[str] = Query(None)
):
    pages_file = BASE_DIR / rel_path / "pages.jsonl"
    if not pages_file.exists():
        raise HTTPException(status_code=404, detail="Book pages file not found")
        
    part_str = str(part).strip() if part not in (None, "", "None", "null", "undefined") else None

    # If point_id is given and no text_hint, retrieve text from Qdrant as hint
    if point_id and not text_hint:
        for c_cand in [BADR_ALL_TSH_COLLECTION_NAME, BADR_COLLECTION_NAME, BADR_TCH_COLLECTION_NAME, COLLECTION_NAME]:
            try:
                if state.get("qdrant"):
                    pt = state["qdrant"].retrieve(collection_name=c_cand, ids=[point_id])
                    if pt and pt[0].payload:
                        text_hint = pt[0].payload.get("text")
                        if text_hint:
                            break
            except Exception:
                pass

    clean_hint = None
    if text_hint:
        sub = re.sub(r"<[^>]+>", " ", text_hint)
        for segment in sub.splitlines():
            seg_clean = segment.strip()
            if len(seg_clean) >= 10:
                clean_hint = seg_clean[:50]
                break
        if not clean_hint:
            sub_clean = re.sub(r"\s+", " ", sub).strip()
            if len(sub_clean) >= 6:
                clean_hint = sub_clean[:50]
    
    all_pages = []
    target_idx = -1
    with open(pages_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            p = json.loads(line)
            all_pages.append(p)
            
            # 1. Match by clean text hint (highest precision)
            if clean_hint and target_idx == -1 and clean_hint in (p.get("body") or ""):
                target_idx = idx

            # 2. Match by page_num and part if specified
            if target_idx == -1 and page_num is not None:
                if p.get("page_num") == page_num:
                    p_part = str(p.get("part")).strip() if p.get("part") is not None else None
                    if part_str is not None:
                        if p_part == part_str:
                            target_idx = idx
                    else:
                        target_idx = idx

    # Fallback search if still not found
    if target_idx == -1 and page_num is not None:
        for idx, p in enumerate(all_pages):
            if p.get("page_num") == page_num:
                target_idx = idx
                break
            elif p.get("shamela_page_id") == page_num or p.get("sequence_num") == page_num:
                target_idx = idx
                break

    if target_idx == -1:
        raise HTTPException(status_code=404, detail="Page not found")
        
    curr = all_pages[target_idx]
    prev_page = all_pages[target_idx - 1] if target_idx > 0 else None
    next_page = all_pages[target_idx + 1] if target_idx < len(all_pages) - 1 else None
    
    return {
        "current": curr,
        "prev": {"page_num": prev_page.get("page_num"), "part": prev_page.get("part")} if prev_page else None,
        "next": {"page_num": next_page.get("page_num"), "part": next_page.get("part")} if next_page else None,
        "total_pages": len(all_pages)
    }

@app.get("/api/book/{book_id}")
async def get_book(book_id: int):
    cur = state["db_conn"].cursor()
    cur.execute("SELECT * FROM books WHERE book_id = ?", (book_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Book not found")
        
    rel_path = row["rel_path"]
    toc = []
    if rel_path:
        toc_file = BASE_DIR / rel_path / "toc.jsonl"
        if toc_file.exists():
            try:
                with open(toc_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            toc.append(json.loads(line))
            except Exception as e:
                print(f"Error reading TOC: {e}")
                
    return {
        "book_id": row["book_id"],
        "shamela_id": row["shamela_id"],
        "title_ar": row["title_ar"],
        "category_id": row["category_id"],
        "category_name_ar": row["category_name_ar"],
        "author_name": row["main_author_name_ar"],
        "death_hijri": row["main_author_death_hijri"],
        "volume_count": row["volume_count_observed"],
        "betaka_text": row["betaka_text"],
        "rel_path": rel_path,
        "toc_count": len(toc),
        "toc": toc[:200] # First 200 sections
    }

# --- نماذج ونقاط نهاية الذكاء الاصطناعي والتصدير ---

class AIChatRequest(BaseModel):
    provider: str = "openrouter" # openai, google, anthropic, openrouter, ollama, lmstudio
    api_key: Optional[str] = ""
    model: str
    endpoint_url: Optional[str] = None
    base_url: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: float = 0.3
    repetition_penalty: float = 0.0
    max_tokens: int = 3000
    structured_format: Optional[str] = None
    structured_output: Optional[str] = None
    rag_enabled: Optional[bool] = None
    use_rag: Optional[bool] = None
    rag_query: Optional[str] = None
    rag_limit: int = 5
    rag_mode: str = "hybrid" # hybrid, dense, sparse, full
    collection_name: Optional[str] = "badr_corpus"
    category_id: Optional[int] = None
    book_titles: Optional[List[str]] = None
    selected_books: Optional[List[str]] = None
    helper_model: Optional[str] = "google/gemini-2.5-flash"
    helper_provider: Optional[str] = None
    reformulate_query: Optional[bool] = True
    iterative_research: Optional[bool] = False
    max_research_hops: Optional[int] = 2
    use_reranker: Optional[bool] = True
    reranker_limit: Optional[int] = 10
    reranker_model: Optional[str] = "BAAI/bge-reranker-v2-m3"
    # بروتوكول أدوات التحقيق الشرعي (MCP)
    mcp_enabled: Optional[bool] = False
    mcp_mode: Optional[str] = "autonomous" # autonomous, context_injection, hybrid
    mcp_reformulate: Optional[bool] = True
    mcp_iterative: Optional[bool] = True
    mcp_max_hops: Optional[int] = 2
    mcp_limit: Optional[int] = 20
    mcp_use_reranker: Optional[bool] = True
    mcp_reranker_limit: Optional[int] = 10
    mcp_reranker_model: Optional[str] = "BAAI/bge-reranker-v2-m3"
    mcp_category_id: Optional[Union[int, str]] = None
    mcp_book_filter: Optional[str] = None
    mcp_active_tools: Optional[List[str]] = None

class DocxExportRequest(BaseModel):
    title: str = "تقرير بحث المكتبة الشاملة"
    query: str
    answer: str
    sources: List[Dict[str, Any]] = []

class CraftMyPdfExportRequest(BaseModel):
    api_key: str
    template_id: str
    title: Optional[str] = "تقرير بحث المكتبة الشاملة"
    query: Optional[str] = None
    prompt: Optional[str] = None
    answer: Optional[str] = None
    content: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = []
    custom_data_schema: Optional[Union[Dict[str, Any], str]] = None

class AssistantModelConfig(BaseModel):
    id: str
    name: str
    role: Optional[str] = "مساعد تخصصي"
    output_format: Optional[str] = "تقرير تحقيقي علمي رصين ومستوفٍ مع العزو المكتبي الصريح (الكتاب، المؤلف، الجزء، الصفحة) وقائمة المصادر والمراجع."
    enabled: bool = True
    provider: Optional[str] = "openrouter" # openrouter, ollama, lmstudio, openai, etc.
    api_key: Optional[str] = ""
    endpoint_url: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 3500
    rag_limit: int = 10
    rag_mode: str = "hybrid"
    collection_name: Optional[str] = "badr_all_tsh_corpus"
    scope_type: Optional[str] = "all"
    collection_id: Optional[str] = None
    section_name: Optional[str] = None
    category_id: Optional[int] = None
    book_titles: Optional[List[str]] = []
    system_prompt: Optional[str] = ""
    use_reranker: Optional[bool] = True
    reranker_limit: Optional[int] = 10
    reranker_model: Optional[str] = "BAAI/bge-reranker-v2-m3"

class MultiAgentPipelineRequest(BaseModel):
    query: str
    api_key: Optional[str] = ""
    cloud_api_key: Optional[str] = ""
    openrouter_api_key: Optional[str] = ""
    provider: str = "openrouter"
    endpoint_url: Optional[str] = None
    base_url: Optional[str] = None
    main_model: str = "anthropic/claude-3.5-sonnet"
    main_system_prompt: Optional[str] = ""
    main_temperature: float = 0.3
    main_max_tokens: int = 8000
    collection_name: Optional[str] = "badr_all_tsh_corpus"
    assistants: List[AssistantModelConfig] = []
    enable_gap_fill: bool = True
    structured_format: Optional[str] = None
    use_reranker: Optional[bool] = True
    reranker_limit: Optional[int] = 10
    reranker_model: Optional[str] = "BAAI/bge-reranker-v2-m3"

@app.get("/api/ai/models")
async def get_ai_models(
    provider: str = Query(...),
    api_key: Optional[str] = Query(None),
    endpoint_url: Optional[str] = Query(None),
    base_url: Optional[str] = Query(None)
):
    target_base = endpoint_url or base_url or ""
    models = await fetch_provider_models(provider, api_key or "", base_url=target_base)
    return {"provider": provider, "models": models}

@app.post("/api/ai/chat")
async def ai_chat(req: AIChatRequest):
    t0 = time.time()
    try:
        effective_prov = (req.provider or "openrouter").lower().strip()
        effective_key = (req.api_key or "").strip()
        effective_base_url = req.endpoint_url or req.base_url or None

        if effective_prov not in ["ollama", "lmstudio", "local", "huggingface", "gguf"] and not effective_key:
            raise HTTPException(status_code=400, detail="يرجى توفير مفتاح API للمزود المحدد")
            
        # تطبيع الحقول والبدائل
        effective_rag_enabled = req.rag_enabled if req.rag_enabled is not None else (req.use_rag if req.use_rag is not None else True)
        effective_structured = req.structured_format or req.structured_output or None
        effective_book_titles = req.book_titles or req.selected_books or None

        # بناء رسائل المحادثة
        active_messages: List[Dict[str, str]] = list(req.messages) if req.messages else []
        if not active_messages and req.prompt:
            active_messages = [{"role": "user", "content": req.prompt}]
            
        if not active_messages:
            raise HTTPException(status_code=400, detail="يرجى كتابة نص الرسالة أو السؤال لإرساله للنموذج")

        sources = []
        reformulated_query_text = None
        supplementary_rounds_log = []

        # استرجاع سياق الشاملة إن تم تفعيل RAG
        if effective_rag_enabled:
            user_query = req.rag_query or ""
            if not user_query:
                for m in reversed(active_messages):
                    if m.get("role") == "user":
                        user_query = m.get("content", "").strip()
                        break
                    
            if user_query:
                # تحديد نموذج المهام المساعدة السريعة (إعادة الصياغة والبحث التكميلي)
                effective_helper_model = (req.helper_model or "").strip()
                if not effective_helper_model or effective_helper_model == "same_as_main":
                    effective_helper_model = req.model.strip()
                effective_helper_prov = (req.helper_provider or "").strip().lower() or effective_prov

                # 1. تعديل وصياغة السؤال بالألفاظ التراثية بالنموذج المساعد السريع
                search_query = user_query
                if req.reformulate_query:
                    try:
                        search_query = await reformulate_fiqh_query(
                            provider=effective_helper_prov,
                            api_key=effective_key,
                            model=effective_helper_model,
                            user_query=user_query,
                            system_prompt=req.system_prompt or "",
                            base_url=effective_base_url
                        )
                        reformulated_query_text = search_query
                    except Exception as e:
                        print(f"Query reformulation error: {e}")

                # 2. تنفيذ البحث الأولي في الشاملة
                search_req = SearchRequest(
                    query=search_query,
                    mode=req.rag_mode if req.rag_mode != "full" else "hybrid",
                    collection_name=req.collection_name or BADR_ALL_TSH_COLLECTION_NAME,
                    category_id=req.category_id,
                    book_titles=effective_book_titles,
                    limit=req.rag_limit,
                    use_reranker=req.use_reranker if req.use_reranker is not None else True,
                    reranker_limit=req.reranker_limit,
                    reranker_model=req.reranker_model
                )
                search_res = await search(search_req)
                sources = search_res.get("results", [])

                # 3. خيار البحث التكميلي الذكي بالنموذج المساعد السريع
                if req.iterative_research and sources:
                    max_hops = min(3, max(1, req.max_research_hops or 2))
                    seen_signatures = {
                        (s.get("title_ar", ""), str(s.get("part", "")), str(s.get("page_num", "")))
                        for s in sources
                    }

                    for hop in range(1, max_hops + 1):
                        plan = await plan_supplementary_searches(
                            provider=effective_helper_prov,
                            api_key=effective_key,
                            model=effective_helper_model,
                            user_query=user_query,
                            sources=sources,
                            system_prompt=req.system_prompt or "",
                            base_url=effective_base_url
                        )

                        if not plan.get("needs_more") or not plan.get("queries"):
                            break

                        round_queries = plan.get("queries", [])
                        round_reason = plan.get("reason", "")
                        added_in_round = 0

                        for supp_q in round_queries:
                            supp_limit = max(5, min(req.rag_limit, 40))
                            supp_req = SearchRequest(
                                query=supp_q,
                                mode=req.rag_mode if req.rag_mode != "full" else "hybrid",
                                collection_name=req.collection_name or BADR_ALL_TSH_COLLECTION_NAME,
                                category_id=req.category_id,
                                book_titles=effective_book_titles,
                                limit=supp_limit,
                                use_reranker=req.use_reranker if req.use_reranker is not None else True,
                                reranker_limit=req.reranker_limit,
                                reranker_model=req.reranker_model
                            )
                            supp_res = await search(supp_req)
                            for item in supp_res.get("results", []):
                                sig = (item.get("title_ar", ""), str(item.get("part", "")), str(item.get("page_num", "")))
                                if sig not in seen_signatures:
                                    seen_signatures.add(sig)
                                    sources.append(item)
                                    added_in_round += 1

                        supplementary_rounds_log.append({
                            "hop": hop,
                            "round": hop,
                            "reason": round_reason,
                            "queries": round_queries,
                            "retrieved_count": added_in_round,
                            "added_count": added_in_round
                        })

        # صياغة نص السياق التراثي للنموذج
        augmented_messages = [dict(m) for m in active_messages]
        
        # تنفيذ أدوات التحقيق الشرعي (MCP) إن كانت مفعلة
        mcp_context_parts = []
        if req.mcp_enabled:
            mcp_query = req.prompt or ""
            if not mcp_query:
                for m in reversed(active_messages):
                    if m.get("role") == "user":
                        mcp_query = m.get("content", "").strip()
                        break
            
            if mcp_query:
                limit_val = max(1, min(int(req.mcp_limit or 10), 50))
                active_tools = req.mcp_active_tools or [
                    "get_narrator_isnads", "takhrij_hadith", "search_narrators",
                    "tahrir_madhab", "search_shamela_text", "search_quran_and_tafsir",
                    "get_page_context", "lookup_word_root"
                ]
                norm_q = mcp_query.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
                
                # 1. أداة الأسانيد (get_narrator_isnads)
                if "get_narrator_isnads" in active_tools and any(w in norm_q for w in ["سند", "اسناد", "اسانيد", "طريق", "سفيان", "احمد بن حنبل", "مالك بن انس", "شعبة"]):
                    try:
                        narrator_cand = None
                        m_narrator = re.search(r'(?:راوي|الراوي|سنده|في سنده|عن|طريق)\s+([^\d\n،,]{3,35})', mcp_query)
                        if m_narrator:
                            narrator_cand = m_narrator.group(1).strip()
                        else:
                            for known in ["سفيان الثوري", "أحمد بن حنبل", "مالك بن أنس", "الشافعي", "شعبة بن الحجاج", "سفيان بن عيينة", "الأعمش", "الزهري", "قتادة", "نافع"]:
                                if known in mcp_query:
                                    narrator_cand = known
                                    break
                        if not narrator_cand:
                            narrator_cand = mcp_query.split()[0] if mcp_query else "سفيان الثوري"
                        
                        isnad_res = execute_tool("get_narrator_isnads", {
                            "narrator": narrator_cand,
                            "limit": min(limit_val, 4),
                            "book_title": req.mcp_book_filter or None
                        })
                        if isnad_res and "result" in isnad_res:
                            res_data = isnad_res["result"]
                            isnads_list = res_data.get("isnads", [])
                            if isnads_list:
                                part_txt = f"=== أداة MCP: استخراج أسانيد الراوي ({res_data.get('narrator', narrator_cand)}) ===\n"
                                for k, isn in enumerate(isnads_list[:4]):
                                    part_txt += f"[{k+1}] كتاب: {isn.get('book_title', 'الحديث')} (صـ {isn.get('page_num', '')}) | السند: {isn.get('chain_text', '')}\n"
                                mcp_context_parts.append(part_txt)
                    except Exception as err_isnad:
                        print(f"MCP isnad error: {err_isnad}")
                
                # 2. أداة التراجم (search_narrators)
                if "search_narrators" in active_tools and any(w in norm_q for w in ["ترجمة", "راوي", "الجرح والتعديل", "تعديل", "ثقة", "ضعيف", "طبقة"]):
                    try:
                        cand = mcp_query
                        m_narrator = re.search(r'(?:ترجمة|راوي|الراوي|عن)\s+([^\d\n،,]{3,35})', mcp_query)
                        if m_narrator: cand = m_narrator.group(1).strip()
                        narr_res = execute_tool("search_narrators", {"query": cand, "limit": min(limit_val, 4)})
                        res_val = narr_res.get("result") if isinstance(narr_res, dict) else None
                        narr_list = []
                        if isinstance(res_val, list):
                            narr_list = res_val
                        elif isinstance(res_val, dict):
                            narr_list = res_val.get("narrators") or res_val.get("results") or []
                        if narr_list:
                            part_txt = f"=== أداة MCP: تراجم الرواة والجرح والتعديل ({cand}) ===\n"
                            for k, nr in enumerate(narr_list[:3]):
                                part_txt += f"[{k+1}] الاسم: {nr.get('short_name') or nr.get('name', '')} | الرتبة: {nr.get('ibn_hajar_rank') or nr.get('grade', '')} | الطبقة: {nr.get('generation', '')}\n"
                            mcp_context_parts.append(part_txt)
                    except Exception as err_narr:
                        print(f"MCP narrators error: {err_narr}")

                # 3. أداة تحرير المذاهب (tahrir_madhab)
                if "tahrir_madhab" in active_tools and any(w in norm_q for w in ["مذهب", "مذاهب", "فقه", "حنفية", "شافعية", "مالكية", "حنابلة", "حكم", "يجوز", "حرام"]):
                    try:
                        madhab_res = execute_tool("tahrir_madhab", {"issue": mcp_query, "limit": min(limit_val, 10)})
                        if madhab_res and "result" in madhab_res:
                            m_res = madhab_res["result"]
                            if isinstance(m_res, dict):
                                comps = m_res.get("madhab_comparison")
                                recs = m_res.get("recommended_references") or []
                                part_txt = f"=== أداة MCP: تحرير المسائل والمذاهب الفقهية ({m_res.get('madhab', 'المذاهب الأربعة')}) ===\n"
                                if m_res.get("tahrir_guideline"):
                                    part_txt += f"ضابط التحرير: {m_res['tahrir_guideline']}\n"
                                if comps and isinstance(comps, dict):
                                    for m_name, m_data in comps.items():
                                        part_txt += f"- مذهب {m_name}: المعتمد ({m_data.get('standard_verdict', '')}) | الأدلة والمصادر: {m_data.get('sources_count', 0)} مصدر\n"
                                elif recs:
                                    part_txt += "المراجع المعتمدة للتحرير:\n"
                                    for k, bk in enumerate(recs[:4]):
                                        part_txt += f"[{k+1}] {bk.get('title', '')} ({bk.get('category', '')}) - {bk.get('era_label', '')} (وفاة: {bk.get('author_death_hijri', '')}هـ)\n"
                                mcp_context_parts.append(part_txt)
                    except Exception as err_madhab:
                        print(f"MCP madhab error: {err_madhab}")

                # 4. أداة تخريج الحديث (takhrij_hadith)
                if "takhrij_hadith" in active_tools and any(w in norm_q for w in ["حديث", "تخريج", "صحيح", "متن", "رواه", "الرسول", "النبي"]):
                    try:
                        cand = mcp_query
                        m_h = re.search(r'(?:حديث|متن|قوله|في حديث)\s+([^\d\n،,]{3,50})', mcp_query)
                        if m_h: cand = m_h.group(1).strip()
                        h_res = execute_tool("takhrij_hadith", {"query": cand, "limit": 3})
                        h_data = h_res.get("result") or []
                        if isinstance(h_data, list) and h_data:
                            part_txt = f"=== أداة MCP: تخريج الأحاديث والمتون ({cand}) ===\n"
                            for k, h_item in enumerate(h_data[:3]):
                                snippet = (h_item.get('text_snippet') or h_item.get('text') or '')[:160].strip()
                                part_txt += f"[{k+1}] {snippet}... | كتاب: {h_item.get('book_title', '')}\n"
                            mcp_context_parts.append(part_txt)
                    except Exception as err_hadith:
                        print(f"MCP hadith error: {err_hadith}")

                # 5. أداة شواهد القرآن والتفاسير (search_quran_and_tafsir)
                if "search_quran_and_tafsir" in active_tools and any(w in norm_q for w in ["قران", "اية", "ايات", "سورة", "تفسير"]):
                    try:
                        q_res = execute_tool("search_quran_and_tafsir", {"query": mcp_query, "limit": 2})
                        q_data = q_res.get("result") or []
                        if isinstance(q_data, list) and q_data:
                            part_txt = "=== أداة MCP: شواهد الآيات والتفاسير ===\n"
                            for k, q_item in enumerate(q_data[:2]):
                                part_txt += f"[{k+1}] سورة {q_item.get('surah_name', '')} (آية {q_item.get('ayah_num', '')}): «{q_item.get('text', '')[:180]}»\n"
                            mcp_context_parts.append(part_txt)
                    except Exception as err_quran:
                        print(f"MCP quran error: {err_quran}")

                # 6. أداة معجم الجذور (lookup_word_root)
                if "lookup_word_root" in active_tools and any(w in norm_q for w in ["جذر", "اشتقاق", "معجم", "لغة"]):
                    try:
                        token_cand = mcp_query.split()[0]
                        r_res = execute_tool("lookup_word_root", {"token": token_cand})
                        if r_res and "result" in r_res and isinstance(r_res["result"], dict) and r_res["result"]:
                            r_info = r_res["result"]
                            part_txt = f"=== أداة MCP: معجم الجذور والمعاني ({r_info.get('root', token_cand)}) ===\n"
                            part_txt += f"المعاني الأصول: {str(r_info.get('meanings', ''))[:180]}\n"
                            mcp_context_parts.append(part_txt)
                    except Exception as err_root:
                        print(f"MCP root error: {err_root}")

        combined_context_block = ""
        if sources:
            context_parts = []
            for i, s in enumerate(sources[:6]):
                head = f"المصدر [{i+1}]: كتاب: {s.get('title_ar', 'الشاملة')}"
                if s.get('author_name'): head += f" | المؤلف: {s['author_name']}"
                if s.get('part'): head += f" | جـ {s['part']}"
                if s.get('page_num'): head += f" | صـ {s['page_num']}"
                
                body_txt = (s.get('full_body') or s.get('snippet') or '').strip()[:1100]
                fn_txt = (s.get('footnotes') or '').strip()[:250]
                
                entry = f"{head}\nالنص:\n«{body_txt}»"
                if fn_txt:
                    entry += f"\nالحواشي والتخريج:\n{fn_txt}"
                context_parts.append(entry)

            combined_context_block += "\n\n=== نصوص ووثائق المكتبة الشاملة المعتمدة المسترجعة بالبحث الهجين والتكميلي ===\n"
            combined_context_block += "\n---\n".join(context_parts)
            combined_context_block += "\n=======================================================\n"
            combined_context_block += "استند بدقة وعناية تامة إلى النصوص والوثائق أعلاه لتوثيق الجواب وبيان أقوال الأئمة وتخريج الأحاديث والمصادر.\n"

        if mcp_context_parts:
            mcp_full_txt = "\n\n".join(mcp_context_parts)
            if len(mcp_full_txt) > 2800:
                mcp_full_txt = mcp_full_txt[:2800] + "\n... [تم تلخيص بقية نتائج الأدوات لحفظ كفاءة وسرعة الاستجابة]"
            combined_context_block += "\n\n=== أدوات التحقيق الشرعي المستدعاة عبر بروتوكول MCP (Model Context Protocol) ===\n"
            combined_context_block += mcp_full_txt
            combined_context_block += "\n=======================================================\n"

        if combined_context_block and augmented_messages:
            # حقن السياق في آخر رسالة للمستخدم
            last_user_idx = -1
            for idx in range(len(augmented_messages) - 1, -1, -1):
                if augmented_messages[idx].get("role") == "user":
                    last_user_idx = idx
                    break
                    
            if last_user_idx != -1:
                augmented_messages[last_user_idx]["content"] = augmented_messages[last_user_idx]["content"] + combined_context_block

        ai_resp = await call_ai_chat(
            provider=req.provider,
            api_key=effective_key,
            model=req.model.strip(),
            messages=augmented_messages,
            system_prompt=req.system_prompt or "",
            temperature=req.temperature,
            repetition_penalty=req.repetition_penalty,
            max_tokens=req.max_tokens,
            structured_format=effective_structured,
            base_url=effective_base_url,
            enforce_fiqh_template=not bool(req.system_prompt and req.system_prompt.strip())
        )
        
        return {
            "status": "success",
            "reply": ai_resp["content"],
            "answer": ai_resp["content"],
            "sources": sources,
            "reformulated_query": reformulated_query_text,
            "supplementary_rounds": supplementary_rounds_log,
            "usage": ai_resp.get("usage", {}),
            "finish_reason": ai_resp.get("finish_reason"),
            "took_ms": round((time.time() - t0) * 1000, 1),
            "model_used": req.model
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        err_msg = str(e)
        if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
            if effective_prov in ("ollama", "lmstudio", "local"):
                err_msg = f"انتهت مهلة محاولة الاتصال بالخادم المحلي ({effective_base_url or '192.168.100.134:1234'}). إذا كان التطبيق يعمل على سيرفر سحابي (Coolify)، فلا يمكنه الوصول إلى الشبكة المنزلية أو جهازك المنزلي دون نفق عام (Tunnel). يرجى اختيار مزود سحابي مثل OpenRouter أو Gemini."
            else:
                err_msg = f"انتهت مهلة استجابة مزود الذكاء الاصطناعي ({effective_prov}). يرجى التحقق من مفتاح API أو اختيار نموذج أسرع."
        return JSONResponse(
            status_code=400,
            content={"status": "error", "detail": err_msg, "message": err_msg}
        )

@app.post("/api/export/docx")
async def export_docx(req: DocxExportRequest):
    try:
        buf = generate_word_report(req.title, req.query, req.answer, req.sources)
        filename = f"shamela_report_{int(time.time())}.docx"
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل توليد ملف Word: {str(e)}")

@app.post("/api/export/craftmypdf")
async def export_craftmypdf(req: CraftMyPdfExportRequest):
    if not req.api_key or not req.api_key.strip():
        raise HTTPException(status_code=400, detail="يرجى إدخال مفتاح API الخاص بـ CraftMyPDF")
    if not req.template_id or not req.template_id.strip():
        raise HTTPException(status_code=400, detail="يرجى إدخال معرف القالب (Template ID) الخاص بـ CraftMyPDF")

    effective_query = (req.query or req.prompt or "مسألة بحثية في الشاملة").strip()
    effective_answer = (req.answer or req.content or "").strip()
    effective_title = (req.title or "تقرير بحث المكتبة الشاملة").strip()
    effective_sources = req.sources or []

    try:
        # عدم تضمين نصوص الشاملة الخام والاكتفاء حصراً بإجابة النموذج لتفادي تضخم الحجم وأخطاء التنسيق
        res = await export_to_craftmypdf(
            api_key=req.api_key.strip(),
            template_id=req.template_id.strip(),
            title=effective_title,
            query=effective_query,
            answer=effective_answer,
            sources=[],
            custom_data_schema=req.custom_data_schema
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ai/assistants/default")
def get_default_assistants():
    """جلب النماذج المساعدة التراثية القياسية الافتراضية (سيبويه، البخاري، مالك، الشاطبي)."""
    json_path = Path(__file__).parent / "default_assistants.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@app.post("/api/ai/pipeline")
async def run_pipeline_endpoint(req: MultiAgentPipelineRequest):
    """نقطة نهاية تشغيل خط أنابيب النماذج المساعدة المتخصصة (Multi-Agent Pipeline)."""
    effective_prov = (req.provider or "openrouter").lower().strip()
    effective_key = (req.api_key or "").strip()
    effective_base_url = req.endpoint_url or req.base_url or None

    if effective_prov not in ["ollama", "lmstudio", "local", "huggingface", "gguf"] and not effective_key:
        raise HTTPException(status_code=400, detail="يرجى توفير مفتاح API للمزود المحدد")
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="يرجى إدخال مسألة أو سؤال للبحث")
    if not req.assistants:
        raise HTTPException(status_code=400, detail="يرجى تحديد أو تفعيل نموذج مساعد واحد على الأقل")

    async def search_adapter(params: Dict[str, Any]) -> Dict[str, Any]:
        s_req = SearchRequest(
            query=params["query"],
            mode=params.get("mode", "hybrid"),
            collection_name=params.get("collection_name") or req.collection_name or BADR_ALL_TSH_COLLECTION_NAME,
            category_id=params.get("category_id"),
            book_titles=params.get("book_titles"),
            limit=params.get("limit", 10),
            use_reranker=params.get("use_reranker", req.use_reranker if hasattr(req, "use_reranker") else True),
            reranker_limit=params.get("reranker_limit") or (req.reranker_limit if hasattr(req, "reranker_limit") else None),
            reranker_model=params.get("reranker_model") or getattr(req, "reranker_model", RERANKER_MODEL_ID)
        )
        return await search(s_req)

    try:
        assistants_dict_list = [a.model_dump() for a in req.assistants]
        effective_cloud_key = (req.cloud_api_key or req.openrouter_api_key or effective_key or "").strip()
        result = await run_multi_agent_pipeline(
            provider=req.provider,
            api_key=effective_key,
            main_model=req.main_model.strip(),
            main_system_prompt=req.main_system_prompt or "",
            query=req.query.strip(),
            assistants=assistants_dict_list,
            search_fn=search_adapter,
            enable_gap_fill=req.enable_gap_fill,
            structured_format=req.structured_format,
            temperature=req.main_temperature,
            max_tokens=req.main_max_tokens,
            base_url=effective_base_url,
            cloud_api_key=effective_cloud_key
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Pipeline error: {e}")
        return JSONResponse(
            status_code=400,
            content={"status": "error", "detail": str(e), "message": str(e)}
        )

@app.get("/api/ai/collections/default")
def get_default_fiqh_collection():
    """جلب بيانات التجميعة القياسية المعتمدة للفقه المقارن التراثي الموسع."""
    json_path = Path(__file__).parent / "default_fiqh_collection.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
# -------------------------------------------------------------
# مسارات استدعاء الوكلاء المساعدين والذكاء الاصطناعي (Agent API Endpoints)
# -------------------------------------------------------------

class AgentQueryRequest(BaseModel):
    query: str
    agent_id: Optional[str] = None
    agent_ids: Optional[List[str]] = None
    custom_assistants: Optional[List[Dict[str, Any]]] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    limit: Optional[int] = 8
    use_reranker: Optional[bool] = True
    temperature: Optional[float] = None

def _load_all_assistants(custom_list: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """جلب قائمة الوكلاء المساعدين: دمج الوكلاء الـ 15 مع وكلاء الجلسة والمستخدم مع استبعاد أي بيانات اختبارية."""
    assistants_map = {}

    # 1. تحميل الوكلاء الـ 15 المعتمدين من default_assistants.json كقاعدة أساسية
    default_json = Path(__file__).parent / "default_assistants.json"
    if default_json.exists():
        try:
            with open(default_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for a in data:
                        if a.get("id"):
                            assistants_map[str(a["id"]).lower()] = a
        except Exception:
            pass

    # 2. فحص ملف وكلاء الجلسة user_assistants.json لتحديث الإعدادات أو إضافة وكلاء مخصصين
    user_json = Path(__file__).parent / "user_assistants.json"
    if user_json.exists():
        try:
            with open(user_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for a in data:
                        aid = str(a.get("id", "")).lower()
                        if not aid or aid == "ast_usul_jadid": # استبعاد الوكيل التجريبي
                            continue
                        assistants_map[aid] = a
        except Exception as e:
            logger.error(f"Error loading user_assistants.json: {e}")

    # 3. إذا تم تمرير قائمة صريحة في جسم الطلب
    if custom_list and isinstance(custom_list, list):
        for a in custom_list:
            aid = str(a.get("id", "")).lower()
            if aid and aid != "ast_usul_jadid":
                assistants_map[aid] = a

    return list(assistants_map.values())

@app.post("/api/ai/agents/sync")
async def sync_user_assistants(request: Request):
    """مزامنة وحفظ الوكلاء المساعدين المنشأين من قبل المستخدم في الجلسة المفتوحة."""
    try:
        data = await request.json()
        assistants = data.get("assistants", [])
        if isinstance(assistants, list):
            user_json = Path(__file__).parent / "user_assistants.json"
            with open(user_json, "w", encoding="utf-8") as f:
                json.dump(assistants, f, ensure_ascii=False, indent=2)
            return {"status": "success", "count": len(assistants)}
    except Exception as e:
        logger.error(f"Error syncing user assistants: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "error", "detail": "Invalid format"}

@app.get("/api/ai/agents")
def list_available_agents():
    """قائمة بكافة الوكلاء المساعدين المتاحين (وكلاء الجلسة المنشأين أو الافتراضيين)."""
    assistants = _load_all_assistants()
    summary = []
    for a in assistants:
        aid = a.get("id", "")
        summary.append({
            "id": aid,
            "name": a.get("name"),
            "role": a.get("role"),
            "default_model": a.get("model"),
            "default_provider": a.get("provider", "openrouter"),
            "books_count": len(a.get("book_titles", [])),
            "book_titles": a.get("book_titles", []),
            "enabled": a.get("enabled", True),
            "is_custom": a.get("is_custom", False) or str(aid).startswith("ast_")
        })
    return {"status": "success", "total": len(summary), "agents": summary}

async def _execute_single_agent(
    ast_cfg: Dict[str, Any],
    clean_q: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 8,
    use_reranker: bool = True,
    temperature: Optional[float] = None,
    auth_header: Optional[str] = None
) -> Dict[str, Any]:
    t0 = time.time()
    effective_prov = (provider or ast_cfg.get("provider") or "openrouter").lower().strip()
    effective_key = (api_key or "").strip()
    
    if not effective_key and auth_header and "bearer " in auth_header.lower():
        effective_key = auth_header.split(" ")[-1].strip()
        
    if not effective_key:
        if effective_prov == "openrouter":
            effective_key = os.environ.get("OPENROUTER_API_KEY", "")
        elif effective_prov in ("gemini", "google"):
            effective_key = os.environ.get("GEMINI_API_KEY", "")

        if not effective_key:
            try:
                keys_file = Path(__file__).resolve().parent / "api_keys.json"
                if keys_file.exists():
                    with open(keys_file, "r", encoding="utf-8") as f:
                        kdata = json.load(f)
                        effective_key = kdata.get(effective_prov, "") or kdata.get("openrouter", "")
            except Exception:
                pass
            
    target_model = (model or ast_cfg.get("model") or "google/gemini-2.5-flash").strip()
    eff_temp = temperature if temperature is not None else float(ast_cfg.get("temperature", 0.2))

    # استرجاع نصوص الشاملة المعتمدة لهذا الوكيل
    book_titles = ast_cfg.get("book_titles") or []
    cat_id = ast_cfg.get("category_id")
    fetch_lim = max(2, min(limit or ast_cfg.get("rag_limit", 8), 50))
    
    s_req = SearchRequest(
        query=clean_q,
        mode="hybrid",
        collection_name=ast_cfg.get("collection_name") or BADR_ALL_TSH_COLLECTION_NAME,
        category_id=cat_id,
        book_titles=book_titles if book_titles else None,
        limit=fetch_lim,
        use_reranker=use_reranker,
        reranker_limit=fetch_lim
    )

    search_output = await search(s_req)
    raw_results = search_output.get("results", [])

    context_blocks = []
    sources = []
    from web_app.mcp_service import parse_betaka_metadata, format_scholarly_citation

    for idx, r in enumerate(raw_results, start=1):
        b_title = r.get("title_ar", "")
        b_author = r.get("author_name", "")
        d_hijri = r.get("death_hijri")
        b_part = r.get("part", "")
        b_page = r.get("page_num", "")
        b_text = r.get("betaka_text", "")
        
        meta = parse_betaka_metadata(b_text) if b_text else {}
        cit = format_scholarly_citation(
            title=b_title,
            author=b_author,
            death_hijri=d_hijri,
            part=b_part,
            page_num=b_page,
            meta=meta
        )
        
        body_text = r.get("full_body") or r.get("snippet") or ""
        clean_body = re.sub(r'<[^>]+>', ' ', body_text).strip()
        fn = r.get("footnotes", "")
        if fn and str(fn).strip():
            clean_fn = re.sub(r'<[^>]+>', ' ', str(fn)).strip()
            if clean_fn:
                clean_body += f"\n[الحاشية]: {clean_fn}"

        context_blocks.append(f"[{idx}] {cit}:\n{clean_body}")
        sources.append({
            "index": idx,
            "book_id": r.get("book_id"),
            "book_title": b_title,
            "author": b_author,
            "author_death_hijri": d_hijri,
            "part": b_part,
            "page_num": b_page,
            "publisher": meta.get("publisher", ""),
            "edition": meta.get("edition", ""),
            "investigator": meta.get("investigator", ""),
            "citation": cit,
            "snippet": clean_body[:300] + ("..." if len(clean_body) > 300 else "")
        })

    joined_context = "\n\n---\n\n".join(context_blocks) if context_blocks else "لم يُعثر على نصوص مباشرة مطابقة في نطاق الكتب المحدد لهذا الوكيل."

    system_prompt = ast_cfg.get("system_prompt", "")
    user_prompt = f"المسألة أو السؤال:\n{clean_q}\n\nنصوص المكتبة الشاملة المعتمدة المرفقة:\n{joined_context}"
    
    messages = [
        {"role": "user", "content": user_prompt}
    ]

    answer_text = ""
    if effective_key or effective_prov in ("ollama", "lmstudio", "local", "gguf"):
        ai_res = await call_ai_chat(
            provider=effective_prov,
            api_key=effective_key,
            model=target_model,
            messages=messages,
            system_prompt=system_prompt,
            temperature=eff_temp
        )
        answer_text = ai_res.get("content", "")
    else:
        answer_text = f"تم استرجاع نصوص الشاملة المعتمدة بنجاح ({len(sources)} مصدر موثق)."
    duration = round(time.time() - t0, 2)

    return {
        "status": "success",
        "agent": {
            "id": ast_cfg.get("id"),
            "name": ast_cfg.get("name"),
            "role": ast_cfg.get("role"),
            "provider": effective_prov,
            "model": target_model,
            "books_count": len(book_titles)
        },
        "answer": answer_text,
        "sources_count": len(sources),
        "sources": sources,
        "duration_seconds": duration
    }

async def _execute_agent_query(
    query_text: str,
    agent_id: Optional[str] = None,
    agent_ids: Optional[List[str]] = None,
    custom_assistants: Optional[List[Dict[str, Any]]] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 8,
    use_reranker: bool = True,
    temperature: Optional[float] = None,
    auth_header: Optional[str] = None
) -> Dict[str, Any]:
    t0 = time.time()
    clean_q = (query_text or "").strip()
    if not clean_q:
        raise HTTPException(status_code=400, detail="حقل query مطلوب ولا يمكن أن يكون فارغاً.")

    all_assistants = _load_all_assistants(custom_assistants)
    
    # تحديد قائمة المعرفات المطلوبة
    target_ids = []
    if agent_ids and isinstance(agent_ids, list):
        target_ids = [str(aid).lower().strip() for aid in agent_ids if str(aid).strip()]
    elif agent_id:
        req_id_str = str(agent_id).lower().strip()
        if req_id_str in ("all", "الجميع", "كل_الوكلاء", "all_agents", "كل الوكلاء"):
            target_ids = [str(a.get("id")).lower().strip() for a in all_assistants if a.get("id")]
        else:
            target_ids = [req_id_str]
        
    if not target_ids:
        target_ids = [str(all_assistants[0].get("id")).lower().strip()] if all_assistants else ["bukhari"]

    matched_assistants = []
    for aid in target_ids:
        found = None
        for a in all_assistants:
            if a.get("id", "").lower() == aid:
                found = a
                break
        if not found:
            for a in all_assistants:
                if aid in a.get("name", "").lower() or aid in a.get("role", "").lower():
                    found = a
                    break
        if found and found not in matched_assistants:
            matched_assistants.append(found)

    if not matched_assistants:
        if all_assistants:
            matched_assistants = [all_assistants[0]]
        else:
            matched_assistants = [{
                "id": "general_scholar",
                "name": "المحقق التراثي العام",
                "role": "تحقيق المسائل العلمية من أمهات كتب الشاملة",
                "system_prompt": "أنت باحث ومحقق شرعي متخصص، تجيب بالاعتماد على نصوص الشاملة المرفقة بالسياق.",
                "model": "google/gemini-2.5-flash",
                "provider": "openrouter",
                "temperature": 0.2,
                "book_titles": []
            }]

    # تنفيذ الاستعلام بالتوازي لكافة الوكلاء المحددين
    tasks = [
        _execute_single_agent(
            ast_cfg=ast,
            clean_q=clean_q,
            provider=provider,
            api_key=api_key,
            model=model,
            limit=limit,
            use_reranker=use_reranker,
            temperature=temperature,
            auth_header=auth_header
        )
        for ast in matched_assistants
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    valid_results = []
    for idx, r in enumerate(results):
        if isinstance(r, Exception):
            valid_results.append({
                "status": "error",
                "agent": {
                    "id": matched_assistants[idx].get("id"),
                    "name": matched_assistants[idx].get("name")
                },
                "error": str(r),
                "answer": f"تعذر استنطاق الوكيل: {str(r)}",
                "sources_count": 0,
                "sources": [],
                "duration_seconds": 0
            })
        else:
            valid_results.append(r)

    total_duration = round(time.time() - t0, 2)

    # إذا كان وكيلاً واحداً نرجع البنية المباشرة مع التوافق التام
    if len(valid_results) == 1:
        first = valid_results[0]
        return {
            "status": first.get("status", "success"),
            "query": clean_q,
            "mode": "single_agent",
            "agent": first.get("agent"),
            "answer": first.get("answer"),
            "sources_count": first.get("sources_count", 0),
            "sources": first.get("sources", []),
            "duration_seconds": total_duration,
            "results": valid_results
        }

    # تجميع وتوحيد المصادر والأجوبة لكافة الوكلاء
    combined_sources = []
    seen_sources = set()
    combined_answers = []
    for vr in valid_results:
        a_info = vr.get("agent", {})
        a_name = a_info.get("name", "وكيل")
        ans = vr.get("answer", "")
        if ans:
            combined_answers.append(f"### 🎙️ [تحرير: {a_name}]:\n{ans}")
        for s in vr.get("sources", []):
            s_key = (s.get("book_id"), s.get("part"), s.get("page_num"))
            if s_key not in seen_sources:
                seen_sources.add(s_key)
                combined_sources.append(s)

    return {
        "status": "success",
        "query": clean_q,
        "mode": "multi_agent",
        "agent": {
            "id": "all",
            "name": f"جميع الوكلاء المساعدين ({len(valid_results)} وكلاء)",
            "role": "استيعاب وتحقيق شامل يجمع كافة مسارات الوكلاء المحددين"
        },
        "agents_count": len(valid_results),
        "answer": "\n\n---\n\n".join(combined_answers),
        "sources_count": len(combined_sources),
        "sources": combined_sources,
        "results": valid_results,
        "duration_seconds": total_duration
    }

@app.post("/api/ai/agent/query")
async def api_query_agent_post(req: AgentQueryRequest, request: Request):
    """إرسال استعلام إلى وكيل أو عدة وكلاء مساعدين والحصول على الإجابات التحريرية والمراجع (POST JSON)."""
    auth_header = request.headers.get("Authorization")
    return await _execute_agent_query(
        query_text=req.query,
        agent_id=req.agent_id,
        agent_ids=req.agent_ids,
        custom_assistants=req.custom_assistants,
        provider=req.provider,
        api_key=req.api_key,
        model=req.model,
        limit=req.limit or 8,
        use_reranker=req.use_reranker if req.use_reranker is not None else True,
        temperature=req.temperature,
        auth_header=auth_header
    )

@app.get("/api/ai/agent/query")
async def api_query_agent_get(
    request: Request,
    query: str = Query(..., description="نص السؤال أو المسألة"),
    agent_id: Optional[str] = Query(None, description="معرف وكيل واحد (اختياري)"),
    agent_ids: Optional[str] = Query(None, description="معرفات عدة وكلاء مفصولة بفاصلة مثل shatibi,bukhari"),
    provider: Optional[str] = Query(None, description="المزود (openrouter, gemini, ollama, local)"),
    api_key: Optional[str] = Query(None, description="مفتاح API إن لم يكن محفوظاً بالنظام"),
    model: Optional[str] = Query(None, description="اسم النموذج (اختياري)"),
    limit: int = Query(8, ge=1, le=50, description="عدد نصوص الشاملة المسترجعة"),
    use_reranker: bool = Query(True, description="تفعيل إعادة الترتيب الدلالي بالريرانكر")
):
    """إرسال استعلام إلى وكيل أو عدة وكلاء مباشرة عبر رابط URL (GET)."""
    auth_header = request.headers.get("Authorization")
    ids_list = None
    if agent_ids:
        ids_list = [s.strip() for s in agent_ids.split(",") if s.strip()]
    elif agent_id:
        ids_list = [agent_id.strip()]

    return await _execute_agent_query(
        query_text=query,
        agent_ids=ids_list,
        provider=provider,
        api_key=api_key,
        model=model,
        limit=limit,
        use_reranker=use_reranker,
        auth_header=auth_header
    )

@app.get("/api/ai/agent/code-examples")
def get_agent_code_examples(request: Request, agent_ids: Optional[str] = None, agent_id: Optional[str] = "bukhari"):
    """أمثلة برمجية لنسخها واستدعاء وكيل واحد أو عدة وكلاء بالتوازي من Python أو JavaScript أو cURL."""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost:8000"
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    base_url = f"{proto}://{host}".rstrip("/")

    ids = []
    if agent_ids:
        ids = [i.strip() for i in agent_ids.split(",") if i.strip()]
    elif agent_id:
        ids = [agent_id.strip()]
    if not ids:
        ids = ["bukhari"]

    is_multi = len(ids) > 1
    ids_json = json.dumps(ids, ensure_ascii=False)
    ids_str = ",".join(ids)

    if is_multi:
        py_code = f"""import requests

url = "{base_url}/api/ai/agent/query"
payload = {{
    "agent_ids": {ids_json},  # استدعاء {len(ids)} وكلاء مساعدين بالتوازي
    "query": "ما حكم المسألة الفقهية أو الأثر في مختلف العلوم؟",
    "provider": "openrouter",
    "api_key": "YOUR_OPENROUTER_KEY",  # أو اتركه فارغاً إن كان مضبوطاً في بيئة الخادم
    "limit": 8
}}

response = requests.post(url, json=payload).json()

# استعراض إجابات كافة الوكلاء المحددين ومراجعهم التراثية
for item in response.get("results", []):
    agent_info = item.get("agent", {{}})
    print("\\n" + "=" * 50)
    print(f"📖 إجابة الوكيل: {{agent_info.get('name')}} ({{agent_info.get('role')}})")
    print("=" * 50)
    print(item.get("answer"))
    
    print("\\n--- المصادر والمراجع المعزوة بالطبعة والمحقق ---")
    for s in item.get("sources", []):
        print(f"- {{s['citation']}}")
"""
        js_code = f"""// استدعاء {len(ids)} وكلاء مساعدين بالتوازي من الويب (JavaScript)
async function askScholars(query) {{
  const response = await fetch('{base_url}/api/ai/agent/query', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{
      agent_ids: {ids_json},
      query: query,
      api_key: 'YOUR_OPENROUTER_KEY'
    }})
  }});
  
  const data = await response.json();
  data.results.forEach(item => {{
    console.log(`=== إجابة ${{item.agent.name}} ===`);
    console.log(item.answer);
    console.log('المراجع:', item.sources);
  }});
  return data;
}}
"""
        curl_code = f"""curl -X POST "{base_url}/api/ai/agent/query" \\
  -H "Content-Type: application/json" \\
  -d '{{"agent_ids": {ids_json}, "query": "ما حكم المسألة؟", "api_key": "YOUR_KEY"}}'"""
        url_example = f"{base_url}/api/ai/agent/query?agent_ids={ids_str}&query=ما+حكم+المسألة&api_key=YOUR_KEY"
    else:
        single_id = ids[0]
        py_code = f"""import requests

url = "{base_url}/api/ai/agent/query"
payload = {{
    "agent_id": "{single_id}",
    "query": "ما حكم المسألة الفقهية أو نص الحديث؟",
    "provider": "openrouter",
    "api_key": "YOUR_OPENROUTER_KEY"
}}

response = requests.post(url, json=payload).json()
print("=== إجابة الوكيل المساعد ===")
print(response.get("answer"))

print("\\n=== المصادر والمراجع المعزوة ===")
for s in response.get("sources", []):
    print(f"- {{s['citation']}}")
"""
        js_code = f"""async function askAgent(query) {{
  const response = await fetch('{base_url}/api/ai/agent/query', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{
      agent_id: '{single_id}',
      query: query,
      api_key: 'YOUR_KEY'
    }})
  }});
  const data = await response.json();
  console.log("الإجابة:", data.answer);
  return data;
}}
"""
        curl_code = f"""curl -X POST "{base_url}/api/ai/agent/query" \\
  -H "Content-Type: application/json" \\
  -d '{{"agent_id": "{single_id}", "query": "ما حكم المسألة؟", "api_key": "YOUR_KEY"}}'"""
        url_example = f"{base_url}/api/ai/agent/query?agent_id={single_id}&query=ما+حكم+المسألة&api_key=YOUR_KEY"

    return {
        "status": "success",
        "agent_ids": ids,
        "is_multi": is_multi,
        "python": py_code,
        "javascript": js_code,
        "curl": curl_code,
        "get_url": url_example
    }

# -------------------------------------------------------------
# التوافق مع معيار OpenAI API (/v1/chat/completions)
# -------------------------------------------------------------
@app.post("/v1/chat/completions")
async def openai_chat_completions_endpoint(request: Request):
    """واجهة متوافقة 100% مع معيار OpenAI لربط وكلاء الشاملة مع أي تطبيق محادثة خارجي."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Messages array cannot be empty")
        
    user_query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_query = m.get("content", "")
            break
            
    if not user_query:
        user_query = messages[-1].get("content", "")

    model_name = body.get("model", "bukhari")
    auth_header = request.headers.get("Authorization")
    
    agent_res = await _execute_agent_query(
        query_text=user_query,
        agent_id=model_name,
        provider=body.get("provider"),
        api_key=body.get("api_key"),
        model=body.get("ai_model"),
        auth_header=auth_header
    )
    
    answer_text = agent_res.get("answer", "")
    sources = agent_res.get("sources", [])
    
    if sources:
        answer_text += "\n\n---\n### المراجع ونصوص التوثيق المعتمدة:\n"
        for s in sources:
            answer_text += f"- {s.get('citation')}\n"
            
    req_id = f"chatcmpl-{int(time.time())}"
    return {
        "id": req_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": answer_text
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": len(user_query.split()) * 2,
            "completion_tokens": len(answer_text.split()) * 2,
            "total_tokens": (len(user_query.split()) + len(answer_text.split())) * 2
        }
    }

@app.get("/v1/models")
def openai_models_endpoint():
    """عرض قائمة الوكلاء المتاحين كنموذج متوافق مع معيار OpenAI."""
    agents_res = list_available_agents()
    models_list = []
    for a in agents_res.get("agents", []):
        models_list.append({
            "id": a["id"],
            "object": "model",
            "created": 1700000000,
            "owned_by": "shamela-scholar",
            "root": a["id"]
        })
    return {"object": "list", "data": models_list}

# -------------------------------------------------------------
# مسارات محطة MCP والتحقيق الشرعي (Model Context Protocol Hub)
# -------------------------------------------------------------
from web_app.mcp_service import (
    mcp_server,
    MCP_TOOLS_SPEC, execute_tool, search_narrators,
    takhrij_hadith, search_quran_and_tafsir, tahrir_madhab,
    lookup_word_root, get_narrator_isnads, get_all_mcp_tools,
    load_custom_mcp_tools, save_custom_mcp_tools,
    set_direct_search_callable
)
set_direct_search_callable(execute_search_sync)

try:
    _mcp_sse_app = mcp_server.sse_app()
    app.mount("/mcp", _mcp_sse_app)
    # Register /sse and /messages natively at root level for universal MCP client compatibility
    for _r in getattr(_mcp_sse_app, "routes", []):
        app.router.routes.append(_r)
except Exception as _e:
    print(f"Error mounting MCP SSE app: {_e}")

class MCPExecuteRequest(BaseModel):
    tool: Optional[str] = None
    tool_name: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    custom_tool_spec: Optional[Dict[str, Any]] = None

@app.get("/api/mcp/tools")
def get_mcp_tools():
    """عرض قائمة أدوات التحقيق الشرعي المتاحة عبر بروتوكول MCP (الرسمية والمخصصة)"""
    return {
        "tools": get_all_mcp_tools(),
        "status": "active",
        "version": "1.2.0"
    }

@app.get("/api/mcp/custom-tools")
def get_custom_tools_endpoint():
    """عرض قائمة أدوات MCP المخصصة"""
    return {"status": "success", "tools": load_custom_mcp_tools()}

class CustomMCPToolRequest(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    icon: Optional[str] = "🔧"
    category: Optional[str] = "أدوات مخصصة"
    topic: Optional[str] = ""
    description: Optional[str] = ""
    engine_type: Optional[str] = "semantic_hybrid" # semantic_hybrid, custom_python
    category_id: Optional[Union[int, str, None]] = None
    book_titles: Optional[List[str]] = []
    default_limit: Optional[int] = 30
    max_limit: Optional[int] = 1000
    enabled: Optional[bool] = True
    python_code: Optional[str] = ""
    tool: Optional[Dict[str, Any]] = None

@app.post("/api/mcp/custom-tools")
def save_custom_tool_endpoint(req: CustomMCPToolRequest):
    """إنشاء أو تحديث أداة MCP مخصصة"""
    if req.tool and isinstance(req.tool, dict):
        raw = req.tool
        raw_name = str(raw.get("name") or raw.get("id") or req.name or "")
        raw_title = str(raw.get("title") or req.title or raw_name)
        raw_icon = str(raw.get("icon") or req.icon or "🔧")
        raw_category = str(raw.get("category") or req.category or "أدوات مخصصة")
        raw_topic = str(raw.get("topic") or req.topic or "")
        raw_desc = str(raw.get("description") or req.description or f"أداة مخصصة في {raw_topic}")
        raw_engine = str(raw.get("engine_type") or req.engine_type or "semantic_hybrid")
        raw_cat_id = raw.get("category_id", req.category_id)
        raw_books = raw.get("book_titles", req.book_titles) or []
        raw_def_limit = raw.get("default_limit", req.default_limit) or 30
        raw_max_limit = raw.get("max_limit", req.max_limit) or 1000
        raw_enabled = raw.get("enabled", req.enabled)
        raw_py = str(raw.get("python_code") or req.python_code or "")
    else:
        raw_name = str(req.name or req.id or "")
        raw_title = str(req.title or raw_name)
        raw_icon = str(req.icon or "🔧")
        raw_category = str(req.category or "أدوات مخصصة")
        raw_topic = str(req.topic or "")
        raw_desc = str(req.description or f"أداة مخصصة في {raw_topic}")
        raw_engine = str(req.engine_type or "semantic_hybrid")
        raw_cat_id = req.category_id
        raw_books = req.book_titles or []
        raw_def_limit = req.default_limit or 30
        raw_max_limit = req.max_limit or 1000
        raw_enabled = req.enabled
        raw_py = str(req.python_code or "")

    slug = re.sub(r'[^a-zA-Z0-9_]', '_', raw_name.strip().lower())
    if not slug:
        slug = f"custom_tool_{int(time.time())}"
    
    tools = load_custom_mcp_tools()
    tool_dict = {
        "id": slug,
        "name": slug,
        "title": raw_title.strip() or slug,
        "icon": raw_icon or "🔧",
        "category": raw_category or "أدوات مخصصة",
        "topic": raw_topic or "",
        "description": raw_desc or f"أداة مخصصة في {raw_topic}",
        "engine_type": raw_engine or "semantic_hybrid",
        "category_id": int(raw_cat_id) if raw_cat_id and str(raw_cat_id).isdigit() else None,
        "book_titles": raw_books or [],
        "default_limit": max(1, min(int(raw_def_limit or 30), 1000)),
        "max_limit": max(1, min(int(raw_max_limit or 1000), 1000)),
        "enabled": raw_enabled if raw_enabled is not None else True,
        "is_custom": True,
        "python_code": raw_py or ""
    }
    
    idx = next((i for i, t in enumerate(tools) if (t.get("name") == slug or t.get("id") == slug)), None)
    if idx is not None:
        tools[idx] = tool_dict
    else:
        tools.append(tool_dict)
    
    save_custom_mcp_tools(tools)
    return {"status": "success", "tool": tool_dict, "tools": tools}

@app.delete("/api/mcp/custom-tools/{tool_name}")
def delete_custom_tool_endpoint(tool_name: str):
    """حذف أداة MCP مخصصة"""
    tools = load_custom_mcp_tools()
    filtered = [t for t in tools if t.get("name") != tool_name and t.get("id") != tool_name]
    save_custom_mcp_tools(filtered)
    return {"status": "success", "deleted": tool_name, "tools": filtered}

@app.post("/api/mcp/execute")
def run_mcp_tool(req: MCPExecuteRequest):
    """تنفيذ أداة MCP تفاعلياً من واجهة الويب"""
    tool_target = req.tool or req.tool_name or ""
    return execute_tool(tool_target, req.arguments or {}, dynamic_spec=req.custom_tool_spec)

@app.get("/api/system/endpoints")
def get_system_endpoints(request: Request):
    """التعرف الديناميكي على عناوين ومنافذ الخدمات (Claude Web، Qdrant، MCP) وفقاً للبيئة والدومين"""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost:8000"
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    hostname = host.split(":")[0]
    
    claude_web_url = os.environ.get("CLAUDE_WEB_URL", "")
    if not claude_web_url:
        if hostname in ("localhost", "127.0.0.1"):
            claude_web_url = "http://localhost:5173"
        else:
            claude_web_url = f"{proto}://{hostname}:5173"

    qdrant_url = os.environ.get("QDRANT_DASHBOARD_URL", os.environ.get("QDRANT_PUBLIC_URL", ""))
    if not qdrant_url:
        if hostname in ("localhost", "127.0.0.1"):
            qdrant_url = "http://localhost:6333/dashboard"
        else:
            qdrant_url = f"http://{hostname}:6333/dashboard"
            
    return {
        "claude_web_url": claude_web_url,
        "qdrant_dashboard_url": qdrant_url,
        "mcp_sse_url": f"{proto}://{host}/sse",
        "api_base_url": f"{proto}://{host}"
    }

@app.get("/api/mcp/config")
def get_mcp_config(request: Request):
    """توليد إعدادات جاهزة لـ Claude Desktop و Cursor للربط المباشر مع دعم الدومين والآي بي الديناميكي"""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost:8000"
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    base_url = f"{proto}://{host}".rstrip("/")

    mcp_sse_url = f"{base_url}/sse"
    python_path = str(BASE_DIR / ".venv" / "bin" / "python")
    server_script = str(BASE_DIR / "shamela_mcp.py")
    
    # Remote HTTP SSE config (لربط Claude Desktop و LibreChat و Cursor عبر الرابط السحابي المباشر)
    remote_claude_config = {
        "mcpServers": {
            "shamela-scholarly": {
                "url": mcp_sse_url
            }
        }
    }

    local_claude_config = {
        "mcpServers": {
            "shamela-scholarly": {
                "command": python_path,
                "args": [server_script],
                "env": {
                    "PYTHONUNBUFFERED": "1"
                }
            }
        }
    }
    
    cursor_config = {
        "mcpServers": {
            "shamela-scholarly": {
                "url": mcp_sse_url
            }
        }
    }
    
    return {
        "mcp_url": mcp_sse_url,
        "sse_url": mcp_sse_url,
        "claude_desktop": json.dumps(remote_claude_config, indent=2, ensure_ascii=False),
        "claude_desktop_local": json.dumps(local_claude_config, indent=2, ensure_ascii=False),
        "cursor": json.dumps(cursor_config, indent=2, ensure_ascii=False),
        "python_path": python_path,
        "server_script": server_script
    }

@app.get("/api/mcp/narrators")
def api_search_narrators(q: str = Query(..., description="اسم الراوي"), limit: int = Query(20, ge=1, le=1000)):
    return search_narrators(q, limit)

@app.get("/api/mcp/takhrij")
def api_takhrij(q: str = Query(..., description="رقم أو مفتاح الحديث"), limit: int = Query(20, ge=1, le=1000)):
    return takhrij_hadith(q, limit)

@app.get("/api/mcp/quran")
def api_quran(q: str = Query(..., description="لفظ الآية"), limit: int = Query(20, ge=1, le=1000)):
    return search_quran_and_tafsir(q, limit)

@app.get("/api/mcp/madhab")
def api_madhab(
    issue: str = Query(..., description="المسألة الفقهية"),
    madhab: str = Query("all", description="المذهب"),
    era: str = Query("late", description="الحقبة"),
    limit: int = Query(20, ge=1, le=1000)
):
    return tahrir_madhab(issue, madhab, era, limit)

@app.get("/api/mcp/root")
def api_root(token: str = Query(..., description="الكلمة المراد كشف جذرها")):
    return lookup_word_root(token)

@app.get("/api/mcp/narrator_isnads")
def api_narrator_isnads(
    narrator: str = Query(..., description="اسم الراوي أو لقبه"),
    limit: int = Query(100, ge=1, le=1000, description="عدد الأسانيد المطلوبة (حتى 1000)"),
    book_title: Optional[str] = Query(None, description="فلترة بكتاب محدد"),
    unique_chains: bool = Query(True, description="سلاسل متمايزة")
):
    return get_narrator_isnads(narrator, limit, book_title, unique_chains)

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = Path(__file__).parent / "templates" / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Index template not created yet</h1>")
    return HTMLResponse(index_file.read_text(encoding="utf-8"))

