@echo off
cd /d D:\hermes-workspace\projects\football-pred-system
set DEV_MODE=true
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
