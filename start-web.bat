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
REM Kill all python processes listening on port 9000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%.*LISTENING" 2^>nul') do (
    echo   Killing PID %%a on port %PORT%...
    taskkill /F /PID %%a >nul 2>&1
)
REM Kill by window title
taskkill /F /FI "WINDOWTITLE eq GPU-Insight-Web" >nul 2>&1
REM Kill any uvicorn remnants
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%uvicorn%%src.web.app%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul
REM Double check port is free
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%.*LISTENING" 2^>nul') do (
    echo   [!] Port %PORT% still occupied by PID %%a, force killing...
    taskkill /F /PID %%a >nul 2>&1
    timeout /t 1 /nobreak >nul
)
echo   OK
echo.

echo [2/4] Check environment...
if not exist "%PYTHON%" (
    echo   [!] Python not found: %PYTHON%
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
start "GPU-Insight-Web" /min "%PYTHON%" -m uvicorn src.web.app:app --host 0.0.0.0 --port %PORT% --reload
echo   Waiting for server...
timeout /t 5 /nobreak >nul
"%PYTHON%" -c "import httpx; r=httpx.get('http://127.0.0.1:%PORT%/api/health',timeout=5); print('  Status:', r.json()['status'])" 2>nul
if errorlevel 1 (
    echo   Retrying...
    timeout /t 3 /nobreak >nul
    "%PYTHON%" -c "import httpx; r=httpx.get('http://127.0.0.1:%PORT%/api/health',timeout=5); print('  Status:', r.json()['status'])" 2>nul
    if errorlevel 1 (
        echo   [!] Server may still be starting, check browser manually
    )
)
echo.

echo [4/4] Opening browser...
start http://localhost:%PORT%
echo.
echo ==========================================
echo   Dashboard:  http://localhost:%PORT%
echo   Admin:      http://localhost:%PORT%/admin
echo   History:    http://localhost:%PORT%/history
echo   Trends:     http://localhost:%PORT%/trends
echo   GPU Models: http://localhost:%PORT%/gpu-models
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
