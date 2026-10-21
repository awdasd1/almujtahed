import os
import sys
from pathlib import Path
from huggingface_hub import HfApi

def main():
    api = HfApi()
    print("👤 Authenticated as:", api.whoami()["name"])

    base_dir = Path("/Users/maa/almujtahed/models/gguf")
    emb_file = base_dir / "almojtahed-embedding-8b-Q4_K_M.gguf"
    rerank_file = base_dir / "almojtahed-reranker-8b-Q4_K_M.gguf"

    if emb_file.exists():
        size_gb = emb_file.stat().st_size / (1024**3)
        print(f"🚀 [1/2] رفع نموذج التضمين المكمم: {emb_file.name} ({size_gb:.2f} GB) إلى cs95/almojtahed-qwen3-8b...")
        api.upload_file(
            path_or_fileobj=str(emb_file),
            path_in_repo="almojtahed-embedding-8b-Q4_K_M.gguf",
            repo_id="cs95/almojtahed-qwen3-8b",
            repo_type="model",
            commit_message="Add GGUF Q4_K_M quantized weights for fast inference"
        )
        print("✅ تم رفع نموذج التضمين almojtahed-embedding-8b-Q4_K_M.gguf بنجاح!")
    else:
        print("❌ لم يتم العثور على ملف التضمين:", emb_file)

    if rerank_file.exists():
        size_gb = rerank_file.stat().st_size / (1024**3)
        print(f"🚀 [2/2] رفع نموذج الريرانكر المكمم: {rerank_file.name} ({size_gb:.2f} GB) إلى cs95/almojtahed-reranker-8b...")
        api.upload_file(
            path_or_fileobj=str(rerank_file),
            path_in_repo="almojtahed-reranker-8b-Q4_K_M.gguf",
            repo_id="cs95/almojtahed-reranker-8b",
            repo_type="model",
            commit_message="Add GGUF Q4_K_M quantized weights for reranker"
        )
        print("✅ تم رفع نموذج الريرانكر almojtahed-reranker-8b-Q4_K_M.gguf بنجاح!")

if __name__ == "__main__":
    main()
