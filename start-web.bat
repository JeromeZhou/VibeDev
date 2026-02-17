@echo off
chcp 65001 >nul 2>&1
title GPU-Insight Web Dashboard
echo.
echo ==========================================
echo   GPU-Insight Web Dashboard
echo ==========================================
echo.

set PYTHON=C:\Users\Jerome\AppData\Local\Programs\Python\Python312\python.exe
set PORT=8088
set PROJECT=D:\SarmTest

:: 1. 停止旧服务（杀所有 uvicorn 进程）
echo [1/4] 停止旧服务...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq GPU-Insight*" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%.*LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo   OK
echo.

:: 2. 检查环境
echo [2/4] 检查环境...
if not exist "%PYTHON%" (
    echo   [!] Python not found: %PYTHON%
    pause
    exit /b 1
)
echo   Python: OK

"%PYTHON%" -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
    echo   安装依赖...
    "%PYTHON%" -m pip install fastapi uvicorn jinja2 httpx -q
)
echo   依赖: OK

if exist "%PROJECT%\data\gpu_insight.db" (
    echo   数据库: OK
) else (
    echo   [!] 数据库不存在，先运行: python main.py
    pause
    exit /b 1
)
echo.

:: 3. 启动服务
echo [3/4] 启动服务 (端口 %PORT%)...
cd /d %PROJECT%
start "GPU-Insight-Web" /min "%PYTHON%" -m uvicorn src.web.app:app --host 0.0.0.0 --port %PORT%
timeout /t 3 /nobreak >nul

:: 验证
"%PYTHON%" -c "import httpx; r=httpx.get('http://127.0.0.1:%PORT%/api/health',timeout=5); print('  状态:', r.json()['status'])" 2>nul
if errorlevel 1 (
    echo   [!] 启动失败! 尝试换端口...
    set PORT=9000
    start "GPU-Insight-Web" /min "%PYTHON%" -m uvicorn src.web.app:app --host 0.0.0.0 --port 9000
    timeout /t 3 /nobreak >nul
    "%PYTHON%" -c "import httpx; r=httpx.get('http://127.0.0.1:9000/api/health',timeout=5); print('  状态:', r.json()['status'])" 2>nul
    if errorlevel 1 (
        echo   [!] 启动失败，请手动检查
        pause
        exit /b 1
    )
)
echo.

:: 4. 打开浏览器
echo [4/4] 打开浏览器...
start http://localhost:%PORT%
timeout /t 1 /nobreak >nul
start http://localhost:%PORT%/history
timeout /t 1 /nobreak >nul
start http://localhost:%PORT%/trends
echo.
echo ==========================================
echo   Dashboard:  http://localhost:%PORT%
echo   历史轮次:   http://localhost:%PORT%/history
echo   趋势分析:   http://localhost:%PORT%/trends
echo ==========================================
echo.
echo 按任意键停止服务...
pause >nul

:: 停止
echo 停止服务...
taskkill /F /FI "WINDOWTITLE eq GPU-Insight-Web" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%.*LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo 已停止!
