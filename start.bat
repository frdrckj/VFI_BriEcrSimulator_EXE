@echo off
setlocal EnableDelayedExpansion

echo Starting BRI ECR Web Application...
echo.

REM Function to check if a command exists
:check_command
where %1 >nul 2>&1
exit /b %errorlevel%

REM Check if Python is installed
echo Checking Python installation...
call :check_command python
if errorlevel 1 (
    call :check_command python3
    if errorlevel 1 (
        echo Python is not installed. Installing Python...
        call :install_python
        if errorlevel 1 (
            echo Failed to install Python. Please install manually from https://python.org
            pause
            exit /b 1
        )
    ) else (
        set PYTHON_CMD=python3
    )
) else (
    set PYTHON_CMD=python
)

REM Verify Python version
echo Checking Python version...
%PYTHON_CMD% --version
%PYTHON_CMD% -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo Python 3.11 or later is required. Please update Python from https://python.org
    pause
    exit /b 1
)

REM Check if pip is installed
echo Checking pip installation...
%PYTHON_CMD% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo pip is not installed. Installing pip...
    call :install_pip
    if errorlevel 1 (
        echo Failed to install pip. Please install manually.
        pause
        exit /b 1
    )
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call venv\Scripts\activate
if errorlevel 1 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Installing/updating requirements...
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements.
    pause
    exit /b 1
)

echo Starting Flask application...
set PYTHONPATH=%cd%
cd src
if not exist "main.py" (
    echo main.py not found in src directory.
    pause
    exit /b 1
)

%PYTHON_CMD% main.py

pause
exit /b 0

REM Function to install Python
:install_python
echo.
echo Attempting to install Python using winget...
winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo Winget installation failed. Trying Chocolatey...
    call :install_with_chocolatey python
    if errorlevel 1 (
        echo.
        echo Automatic installation failed. Please install Python manually:
        echo 1. Go to https://python.org/downloads/
        echo 2. Download Python 3.11 or later
        echo 3. Run the installer and make sure to check "Add Python to PATH"
        echo 4. Restart this script after installation
        exit /b 1
    )
)

REM Refresh PATH
call :refresh_path
exit /b 0

REM Function to install pip
:install_pip
echo.
echo Downloading get-pip.py...
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'"
if errorlevel 1 (
    echo Failed to download get-pip.py
    exit /b 1
)

echo Installing pip...
%PYTHON_CMD% get-pip.py
set pip_result=%errorlevel%
del get-pip.py 2>nul
exit /b %pip_result%

REM Function to install with Chocolatey
:install_with_chocolatey
where choco >nul 2>&1
if errorlevel 1 (
    echo Installing Chocolatey...
    powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
    if errorlevel 1 (
        echo Failed to install Chocolatey
        exit /b 1
    )
    call :refresh_path
)

choco install %1 -y
exit /b %errorlevel%

REM Function to refresh PATH environment variable
:refresh_path
echo Refreshing environment variables...
for /f "tokens=2*" %%i in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SysPath=%%j"
for /f "tokens=2*" %%i in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "UserPath=%%j"
set "PATH=%SysPath%;%UserPath%"
exit /b 0
