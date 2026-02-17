@echo off
chcp 65001 >nul 2>&1
title GPU-Insight Web Dashboard
echo.
echo ==========================================
echo   GPU-Insight Web Dashboard 启动器
echo ==========================================
echo.

:: 1. 停止旧服务
echo [1/4] 停止旧服务...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080.*LISTENING" 2^>nul') do (
    echo   杀掉 PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul
echo   完成
echo.

:: 2. 检查环境
echo [2/4] 检查环境...
set PYTHON=C:\Users\Jerome\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYTHON%" (
    echo   [!] Python 未找到: %PYTHON%
    echo   请修改脚本中的 PYTHON 路径
    pause
    exit /b 1
)
echo   Python: %PYTHON%

:: 检查依赖
"%PYTHON%" -c "import fastapi, uvicorn; print('  FastAPI + Uvicorn: OK')" 2>nul
if errorlevel 1 (
    echo   [!] 缺少依赖，正在安装...
    "%PYTHON%" -m pip install fastapi uvicorn jinja2 python-multipart aiofiles -q
)

:: 检查数据库
if exist "data\gpu_insight.db" (
    echo   数据库: OK
) else (
    echo   [!] 数据库不存在，请先运行 pipeline: python main.py
)
echo.

:: 3. 启动服务
echo [3/4] 启动 Web 服务 (端口 8080)...
cd /d D:\SarmTest
start /b "" "%PYTHON%" -m uvicorn src.web.app:app --host 0.0.0.0 --port 8080 --log-level warning
timeout /t 3 /nobreak >nul

:: 验证服务是否启动
"%PYTHON%" -c "import httpx; r=httpx.get('http://127.0.0.1:8080/api/health',timeout=3); print('  服务状态:', r.json()['status'])" 2>nul
if errorlevel 1 (
    echo   [!] 服务启动失败，请检查端口 8080 是否被占用
    pause
    exit /b 1
)
echo.

:: 4. 打开浏览器
echo [4/4] 打开浏览器...
start http://localhost:8080
timeout /t 1 /nobreak >nul
start http://localhost:8080/history
timeout /t 1 /nobreak >nul
start http://localhost:8080/trends
echo.
echo ==========================================
echo   Dashboard: http://localhost:8080
echo   趋势分析: http://localhost:8080/trends
echo   历史轮次: http://localhost:8080/history
echo ==========================================
echo.
echo 按任意键停止服务并退出...
pause >nul

:: 停止服务
echo.
echo 正在停止服务...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080.*LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo 已停止，再见！
