@echo off
setlocal
set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

set "PYTHON_EXE=%ROOT_DIR%\codebase\.venv\Scripts\python.exe"
set "DASHBOARD_SCRIPT=%ROOT_DIR%\codebase\scripts\run_dashboard.py"

if not exist "%PYTHON_EXE%" (
    echo ======================================================================
    echo [ERROR] Virtual environment not found at:
    echo   "%PYTHON_EXE%"
    echo Please run setup.bat first to install the environment and models:
    echo   .\setup.bat
    echo ======================================================================
    endlocal & exit /b 1
)

if not exist "%DASHBOARD_SCRIPT%" (
    echo [ERROR] Dashboard script not found at:
    echo   "%DASHBOARD_SCRIPT%"
    endlocal & exit /b 1
)

set "PYTHONPATH=%ROOT_DIR%\codebase\src;%ROOT_DIR%\codebase\scripts;%PYTHONPATH%"
set "PYTHONIOENCODING=utf-8"
echo ======================================================================
echo   BASKETBALL VIDEO AND SPATIAL DASHBOARD
echo   Starting local dashboard server ...
echo ======================================================================
"%PYTHON_EXE%" "%DASHBOARD_SCRIPT%" --host 127.0.0.1 --port 8081 --open-browser %*
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
