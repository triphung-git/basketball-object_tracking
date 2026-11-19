@echo off
setlocal
set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

set "VENV_DIR=%ROOT_DIR%\codebase\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "REQ_FILE=%ROOT_DIR%\codebase\requirements.txt"
set "PREPARE_SCRIPT=%ROOT_DIR%\codebase\scripts\prepare_environment.py"
set "CHECK_PYTHON=import struct,sys; sys.exit(sys.version_info[:2] != (3,12) or struct.calcsize('P') != 8)"

echo ======================================================================
echo   BASKETBALL OBJECT TRACKING SETUP
echo   Target: Windows CPU Local Video and Spatial Dashboard
echo ======================================================================

:: 1. Check or create virtual environment
if exist "%VENV_PYTHON%" (
    echo [*] Found existing virtual environment:
    echo     "%VENV_DIR%"
    call :checkInterpreter "%VENV_PYTHON%"
    if errorlevel 1 (
        echo [ERROR] The existing environment must use Python 3.12 64-bit.
        echo Move codebase\.venv aside, then run setup.bat again.
        endlocal & exit /b 1
    )
    goto :installDeps
)

echo [*] Virtual environment not found. Locating suitable system Python...
set "SYS_PYTHON="

:: 0. Check if caller provided explicit PYTHON or PYTHON_EXE
if defined PYTHON_EXE if exist "%PYTHON_EXE%" (
    set "SYS_PYTHON=%PYTHON_EXE%"
    goto :FOUND_SYS_PYTHON
)
if defined PYTHON if exist "%PYTHON%" (
    set "SYS_PYTHON=%PYTHON%"
    goto :FOUND_SYS_PYTHON
)

:: Try py -3.12, then Python on PATH.
for /f "delims=" %%i in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "SYS_PYTHON=%%i"
if defined SYS_PYTHON goto :FOUND_SYS_PYTHON

for /f "delims=" %%i in ('python -c "import struct,sys; print(sys.executable) if sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8 else sys.exit(1)" 2^>nul') do set "SYS_PYTHON=%%i"
if defined SYS_PYTHON goto :FOUND_SYS_PYTHON

:: Try uv python find 3.12
for /f "delims=" %%i in ('uv python find 3.12 2^>nul') do set "SYS_PYTHON=%%i"
if defined SYS_PYTHON goto :FOUND_SYS_PYTHON

echo [ERROR] Python 3.12 64-bit was not found.
echo Please install Python 3.12 64-bit from python.org and add it to your PATH.
endlocal & exit /b 1

:FOUND_SYS_PYTHON
call :checkInterpreter "%SYS_PYTHON%"
if errorlevel 1 (
    echo [ERROR] This interpreter does not run Python 3.12 64-bit: "%SYS_PYTHON%"
    endlocal & exit /b 1
)
echo [*] Using system interpreter: "%SYS_PYTHON%"
echo [*] Creating virtual environment in codebase\.venv...
"%SYS_PYTHON%" -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment in "%VENV_DIR%".
    endlocal & exit /b 1
)

:installDeps
if not exist "%REQ_FILE%" (
    echo [ERROR] Requirements file not found: "%REQ_FILE%"
    endlocal & exit /b 1
)

echo [*] Installing / verifying runtime dependencies...
"%VENV_PYTHON%" -m pip install -r "%REQ_FILE%" --quiet
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    endlocal & exit /b 1
)
"%VENV_PYTHON%" -m pip check
if errorlevel 1 (
    echo [ERROR] Installed dependencies are inconsistent.
    endlocal & exit /b 1
)

:: 2. Verify models and prepare demo assets
if not exist "%PREPARE_SCRIPT%" (
    echo [ERROR] Preparation script not found: "%PREPARE_SCRIPT%"
    endlocal & exit /b 1
)

echo [*] Verifying model weights and demo integrity...
set "PYTHONPATH=%ROOT_DIR%\codebase\src;%ROOT_DIR%\codebase\scripts;%PYTHONPATH%"
"%VENV_PYTHON%" "%PREPARE_SCRIPT%"
if errorlevel 1 (
    echo [ERROR] Environment preparation or model verification failed.
    endlocal & exit /b 1
)

echo ======================================================================
echo   SETUP COMPLETED SUCCESSFULLY!
echo   You can now start the dashboard server by running:
echo     .\start_dashboard.bat
echo ======================================================================
endlocal & exit /b 0

:checkInterpreter
"%~1" -c "%CHECK_PYTHON%" >nul 2>&1
exit /b %ERRORLEVEL%
