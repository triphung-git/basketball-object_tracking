@echo off
setlocal

:: Get root directory of the repository
set "ROOT_DIR=%~dp0"
:: Remove trailing backslash if present
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

set "PYTHON_EXE=%ROOT_DIR%\codebase\.venv\Scripts\python.exe"
set "DEMO_SCRIPT=%ROOT_DIR%\codebase\scripts\run_demo.py"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment Python not found at:
    echo   "%PYTHON_EXE%"
    echo Please make sure the virtual environment codebase\.venv is installed.
    exit /b 1
)

if not exist "%DEMO_SCRIPT%" (
    echo [ERROR] Demo runner script not found at:
    echo   "%DEMO_SCRIPT%"
    exit /b 1
)

:: Set PYTHONPATH for local imports
set "PYTHONPATH=%ROOT_DIR%\codebase\src;%ROOT_DIR%\codebase\scripts;%PYTHONPATH%"
set "PYTHONIOENCODING=utf-8"

:: If no arguments provided, default to launching the interactive demo bundle dashboard
if "%~1"=="" (
    echo ======================================================================
    echo   BASKETBALL VIDEO AND SPATIAL DEMO
    echo   Starting the default spatial-analysis bundle dashboard...
    echo   Tip: To run automated end-to-end analysis on raw video, run:
    echo        run_demo.bat --mode video-analysis --video VIDEO_PATH --output OUTPUT_DIR
    echo ======================================================================
    "%PYTHON_EXE%" "%DEMO_SCRIPT%" --preset default --mode view --open-browser
) else (
    "%PYTHON_EXE%" "%DEMO_SCRIPT%" %*
)

set "DEMO_EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %DEMO_EXIT_CODE%
