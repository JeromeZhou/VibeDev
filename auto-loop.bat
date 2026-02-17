@echo off
REM GPU-Insight 自动循环脚本 (Windows)
REM 每 4 小时执行一次分析循环
REM
REM 使用方式：
REM   双击运行此脚本
REM   或在命令行执行：auto-loop.bat
REM
REM 或配置 Windows 任务计划程序：
REM   - 创建基本任务
REM   - 触发器：每 4 小时
REM   - 操作：启动程序 auto-loop.bat

setlocal enabledelayedexpansion

REM 设置变量
set PYTHON_PATH=C:\Users\Jerome\AppData\Local\Programs\Python\Python312\python.exe
set WORK_DIR=D:\SarmTest
set LOG_DIR=%WORK_DIR%\logs
set INTERVAL=14400
set CYCLE=1

REM 切换到工作目录
cd /d "%WORK_DIR%"

REM 创建日志目录
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM 检查 Python 是否可用
echo.
echo 🚀 GPU-Insight 自动循环启动
echo    间隔：%INTERVAL%s (4h)
echo    日志：%LOG_DIR%\
echo    Python：%PYTHON_PATH%
echo.

if not exist "%PYTHON_PATH%" (
    echo ❌ 错误：Python 未找到
    echo    路径：%PYTHON_PATH%
    echo.
    pause
    exit /b 1
)

"%PYTHON_PATH%" --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：Python 不可用
    pause
    exit /b 1
)

echo ✅ Python 检查通过
echo.

REM 主循环
:loop

REM 生成时间戳和日志文件名
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set LOG_FILE=%LOG_DIR%\cycle_%mydate%_%mytime%.log

REM 获取当前时间戳
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set current_time=%%a:%%b)
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set current_date=%%c-%%a-%%b)

echo [%current_date% %current_time%] 第 %CYCLE% 轮开始... >> "%LOG_FILE%"
echo [%current_date% %current_time%] 第 %CYCLE% 轮开始...

REM 执行主程序
"%PYTHON_PATH%" main.py >> "%LOG_FILE%" 2>&1

REM 检查退出码
if errorlevel 1 (
    for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set current_time=%%a:%%b)
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set current_date=%%c-%%a-%%b)
    echo [%current_date% %current_time%] 第 %CYCLE% 轮异常 (exit=!errorlevel!) ⚠️ >> "%LOG_FILE%"
    echo [%current_date% %current_time%] 第 %CYCLE% 轮异常 (exit=!errorlevel!) ⚠️
) else (
    for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set current_time=%%a:%%b)
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set current_date=%%c-%%a-%%b)
    echo [%current_date% %current_time%] 第 %CYCLE% 轮完成 ✅ >> "%LOG_FILE%"
    echo [%current_date% %current_time%] 第 %CYCLE% 轮完成 ✅
)

echo.

REM 计算下次运行时间
set /a next_cycle=%CYCLE%+1
echo ⏳ 等待 %INTERVAL%s 后开始第 %next_cycle% 轮...
echo    下次运行时间：约 4 小时后

REM 等待 4 小时（14400 秒）
timeout /t %INTERVAL% /nobreak

REM 更新循环计数
set /a CYCLE=%CYCLE%+1

REM 继续循环
goto loop

endlocal
