@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

if not exist .venv (
  echo إنشاء بيئة بايثون المحلية .venv ...
  %PY% -m venv .venv
  if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python -c "import fastapi, uvicorn, qdrant_client, huggingface_hub, dotenv, llama_cpp" >nul 2>&1
if errorlevel 1 (
  echo تثبيت مكتبات التشغيل لأول مرة. قد يأخذ هذا عدة دقائق...
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  if errorlevel 1 exit /b 1
)

python start_local.py
