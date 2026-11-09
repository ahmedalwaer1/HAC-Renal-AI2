@echo off
title HAC-Renal AI Launcher

cd /d "%~dp0"

echo Starting Python Backend...
start "HAC Backend" cmd /k "python -m uvicorn api_bridge:app --reload --port 8000"

timeout /t 5 /nobreak >nul

echo Starting React Frontend...
start "HAC Frontend" cmd /k "cd /d frontend && npm run dev"

timeout /t 5 /nobreak >nul

echo Opening HAC-Renal AI...
start http://127.0.0.1:5173

exit 