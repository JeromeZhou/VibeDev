@echo off
title GPU-Insight Auto Loop
setlocal enabledelayedexpansion

set PYTHON=C:\Users\Jerome\AppData\Local\Programs\Python\Python312\python.exe
set PROJECT=D:\SarmTest
set LOG_DIR=%PROJECT%\logs
set INTERVAL=14400
set CYCLE=1

cd /d "%PROJECT%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.
echo ==========================================
echo   GPU-Insight Auto Loop (4h cycle)
echo ==========================================
echo   Interval: %INTERVAL%s (4h)
echo   Logs:     %LOG_DIR%\
echo   Python:   %PYTHON%
echo.

if not exist "%PYTHON%" (
    echo   [!] Python not found: %PYTHON%
    pause
    exit /b 1
)

"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo   [!] Python not working
    pause
    exit /b 1
)
echo   [OK] Python ready
echo.

:LOOP

for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set LOG_FILE=%LOG_DIR%\cycle_%mydate%_%mytime%.log

echo [%date% %time%] Cycle %CYCLE% starting...
echo [%date% %time%] Cycle %CYCLE% starting... >> "%LOG_FILE%"

"%PYTHON%" main.py >> "%LOG_FILE%" 2>&1

if errorlevel 1 (
    echo [%date% %time%] Cycle %CYCLE% FAILED >> "%LOG_FILE%"
    echo [%date% %time%] Cycle %CYCLE% FAILED [!]
) else (
    echo [%date% %time%] Cycle %CYCLE% OK >> "%LOG_FILE%"
    echo [%date% %time%] Cycle %CYCLE% OK
)

echo.
set /a NEXT=%CYCLE%+1
echo   Waiting %INTERVAL%s for cycle %NEXT%...
echo   Press Ctrl+C to stop.
echo ------------------------------------------

timeout /t %INTERVAL% /nobreak

set /a CYCLE=%CYCLE%+1
goto LOOP

endlocal
