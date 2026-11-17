@echo off
setlocal
set "ROOT_DIR=%~dp0"
set "PYTHON_EXE=%ROOT_DIR%codebase\.venv\Scripts\python.exe"
set "DASHBOARD_SCRIPT=%ROOT_DIR%codebase\scripts\run_dashboard.py"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python environment not found:
    echo   "%PYTHON_EXE%"
    endlocal & exit /b 1
)

if not exist "%DASHBOARD_SCRIPT%" (
    echo [ERROR] Dashboard script not found:
    echo   "%DASHBOARD_SCRIPT%"
    endlocal & exit /b 1
)

set "PYTHONPATH=%ROOT_DIR%codebase\src;%ROOT_DIR%codebase\scripts;%PYTHONPATH%"
set "PYTHONIOENCODING=utf-8"
echo Starting the local video and spatial dashboard...
"%PYTHON_EXE%" "%DASHBOARD_SCRIPT%" --host 127.0.0.1 --port 8081
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
