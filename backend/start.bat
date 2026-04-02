@echo off
echo ============================================
echo   Chatbot Backend Startup
echo ============================================

cd /d "%~dp0"

REM ── Check .env exists ──────────────────────────────────────────────────────
if not exist ".env" (
    echo [ERROR] .env file not found. Copy .env and fill in credentials.
    pause
    exit /b 1
)

REM ── Check OPENAI_API_KEY is set ────────────────────────────────────────────
findstr /C:"OPENAI_API_KEY=sk-" .env >nul 2>&1
if errorlevel 1 (
    echo [WARN] OPENAI_API_KEY looks like a placeholder. Embeddings will fail.
    echo        Edit .env and set your real OpenAI API key.
)

REM ── Initialize App DB (idempotent) ─────────────────────────────────────────
echo [1/3] Initializing App DB...
.venv\Scripts\python.exe -m scripts.init_db
if errorlevel 1 (
    echo [ERROR] App DB initialization failed. Check APP_DB_URL in .env.
    pause
    exit /b 1
)

REM ── Start MCP Server in background ────────────────────────────────────────
echo [2/3] Starting MCP server on port 5433...
start "MCP Server" /min .venv\Scripts\python.exe mcp_server.py

REM ── Wait briefly for MCP server to bind ───────────────────────────────────
timeout /t 2 /nobreak >nul

REM ── Start FastAPI backend ──────────────────────────────────────────────────
echo [3/3] Starting FastAPI backend on port 8000...
echo.
echo   API:    http://localhost:8000
echo   Health: http://localhost:8000/health
echo   Docs:   http://localhost:8000/docs
echo   WS:     ws://localhost:8000/ws/chat/{session_id}
echo.
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
