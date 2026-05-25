@echo off
:: ============================================================================
:: setup_task_scheduler.bat — PropAgent Windows Task Scheduler setup
:: ============================================================================
:: Creates a daily scheduled task that runs run_scraper.py at 07:00.
::
:: REQUIREMENTS:
::   • Run this script as Administrator (right-click → Run as administrator)
::   • Python must be on PATH (test: python --version)
::   • Docker Desktop must be running before 07:00 for DB access
::
:: TO CHANGE THE SCHEDULE TIME:
::   Edit the /ST value below (format HH:MM, 24-hour clock)
::   Example: /ST 06:30  → run at 06:30 every day
::
:: TO CHANGE THE PYTHON EXECUTABLE:
::   Replace `pythonw.exe` with the full path, e.g.:
::   C:\Users\YourName\AppData\Local\Programs\Python\Python311\pythonw.exe
::
:: TO REMOVE THE TASK LATER:
::   schtasks /Delete /TN "PropAgent_Scraper" /F
::
:: ============================================================================

setlocal enabledelayedexpansion

set TASK_NAME=PropAgent_Scraper
set SCRIPT_DIR=%~dp0
set SCRIPT_PATH=%SCRIPT_DIR%run_scraper.py
set SCHEDULE_TIME=21:00

echo.
echo  PropAgent — Task Scheduler Setup
echo  ==================================
echo.
echo  Task name : %TASK_NAME%
echo  Script    : %SCRIPT_PATH%
echo  Schedule  : Daily at %SCHEDULE_TIME%
echo.

:: Resolve pythonw.exe (no console window on task run)
for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do (
    set PYTHON_EXE=%%i
    goto :found_python
)
:: Fallback: try python.exe from PATH
for /f "delims=" %%i in ('where python.exe 2^>nul') do (
    set PYTHON_EXE=%%i
    goto :found_python
)
echo  [ERROR] python.exe not found on PATH. Install Python and try again.
pause
exit /b 1

:found_python
echo  Python    : %PYTHON_EXE%
echo.

:: NOTE: Docker Desktop should be running by %SCHEDULE_TIME%.
:: If it isn't, the spider DB writes will fail. Start Docker at login via
:: Docker Desktop → Settings → General → "Start Docker Desktop when you log in".
echo  [NOTE] Make sure Docker Desktop is running before %SCHEDULE_TIME%.
echo.

:: Create (or overwrite) the scheduled task
schtasks /Create ^
    /TN "%TASK_NAME%" ^
    /TR "\"%PYTHON_EXE%\" \"%SCRIPT_PATH%\"" ^
    /SC DAILY ^
    /ST %SCHEDULE_TIME% ^
    /F ^
    /RL HIGHEST

if %ERRORLEVEL% EQU 0 (
    echo.
    echo  [OK] Task "%TASK_NAME%" created successfully.
    echo  It will run every day at %SCHEDULE_TIME%.
    echo.
    echo  To verify: open Task Scheduler and look for "%TASK_NAME%"
    echo  Or run:   schtasks /Query /TN "%TASK_NAME%" /FO LIST
) else (
    echo.
    echo  [ERROR] Failed to create task (exit code %ERRORLEVEL%).
    echo  Make sure you are running this script as Administrator.
)

echo.
pause
endlocal
