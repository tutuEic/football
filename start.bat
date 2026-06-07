@echo off
chcp 65001 >nul
title 鈿?灏忔潕瓒崇悆棰勬祴绯荤粺
echo.
echo 鈺斺晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晽
echo 鈺?   鈿? 灏忔潕瓒崇悆棰勬祴绯荤粺  v0.2.0        鈺?
echo 鈺氣晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨暆
echo.

cd /d "%~dp0"

echo [1/2] 鍚姩鍚庣 API (绔彛 8000)...
start "Football-API" cmd /c "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

echo [2/2] 鍚姩鍓嶇椤甸潰 (绔彛 5173)...
start "Football-Frontend" cmd /c "cd frontend && npm run dev -- --host 127.0.0.1"

timeout /t 3 /nobreak >nul

echo.
echo 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
echo 鈹? 鉁?绯荤粺宸插惎鍔?                          鈹?
echo 鈹?                                         鈹?
echo 鈹? 鍚庣 API:   http://localhost:8000/docs  鈹?
echo 鈹? 鍓嶇椤甸潰:   http://localhost:5173       鈹?
echo 鈹?                                         鈹?
echo 鈹? 鎸変换鎰忛敭鍏抽棴...                         鈹?
echo 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
echo.
pause >nul


