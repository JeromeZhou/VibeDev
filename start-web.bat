@echo off
title GPU-Insight Web Dashboard
echo.
echo ==========================================
echo   GPU-Insight Web Dashboard
echo ==========================================
echo.
set PYTHON=C:\Users\Jerome\AppData\Local\Programs\Python\Python312\python.exe
set PORT=9000
set PROJECT=D:\SarmTest
echo [1/4] Stop old services...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq GPU-Insight*" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":9000.*LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8088.*LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo   OK
echo.
echo [2/4] Check environment...
if not exist "%PYTHON%" (
    echo   [!] Python not found
    pause
    exit /b 1
)
echo   Python: OK
"%PYTHON%" -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
    echo   Installing dependencies...
    "%PYTHON%" -m pip install fastapi uvicorn jinja2 httpx -q
)
echo   Dependencies: OK
if exist "%PROJECT%\data\gpu_insight.db" (
    echo   Database: OK
) else (
    echo   [!] No database. Run: python main.py
    pause
    exit /b 1
)
echo.
echo [3/4] Starting server on port %PORT%...
cd /d %PROJECT%
start "GPU-Insight-Web" /min "%PYTHON%" -m uvicorn src.web.app:app --host 0.0.0.0 --port %PORT%
timeout /t 3 /nobreak >nul
"%PYTHON%" -c "import httpx; r=httpx.get('http://127.0.0.1:%PORT%/api/health',timeout=5); print('  Status:', r.json()['status'])" 2>nul
if errorlevel 1 (
    echo   [!] Port %PORT% failed, trying 9000...
    set PORT=9000
    start "GPU-Insight-Web" /min "%PYTHON%" -m uvicorn src.web.app:app --host 0.0.0.0 --port 9000
    timeout /t 3 /nobreak >nul
)
echo.
echo [4/4] Opening browser...
start http://localhost:%PORT%
timeout /t 1 /nobreak >nul
start http://localhost:%PORT%/history
timeout /t 1 /nobreak >nul
start http://localhost:%PORT%/trends
echo.
echo ==========================================
echo   Dashboard:  http://localhost:%PORT%
echo   History:    http://localhost:%PORT%/history
echo   Trends:     http://localhost:%PORT%/trends
echo ==========================================
echo.
echo Press any key to stop server...
pause >nul
echo Stopping server...
taskkill /F /FI "WINDOWTITLE eq GPU-Insight-Web" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%.*LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo Done!
