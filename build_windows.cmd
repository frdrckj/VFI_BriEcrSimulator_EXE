@echo off
echo ========================================
echo BRI ECR Windows Build Script
echo ========================================

REM Change to script directory
cd /d "%~dp0"
echo Current directory: %CD%

REM Verify we're in the right directory
if not exist "src\main.py" (
    echo ERROR: Not in correct directory!
    echo This script must be run from the BriEcrSimulator folder
    echo Expected files: src\main.py, build_requirements.txt, bri_ecr.spec
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM Install build requirements
echo Installing build requirements...
echo Looking for build_requirements.txt...
if not exist "build_requirements.txt" (
    echo ERROR: build_requirements.txt not found in current directory
    echo Current directory: %CD%
    echo Please ensure you're running this from the BriEcrSimulator folder
    dir /b *.txt *.py *.spec 2>nul
    pause
    exit /b 1
)
pip install -r build_requirements.txt

REM Clean previous builds
echo Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Build the executable with optimizations
echo Building Windows executable with antivirus optimizations...
echo - Adding version information (Publisher: Verifone)
echo - Adding developer info (Frederick Armando Jerusha)
echo - Optimizing for reduced false positives
echo.
echo Checking for required files before build...
if not exist "bri_ecr.spec" (
    echo ERROR: bri_ecr.spec not found!
    pause
    exit /b 1
)
if not exist "src\main.py" (
    echo ERROR: src\main.py not found!
    pause
    exit /b 1
)
echo All required files found. Starting PyInstaller...
echo Current working directory: %CD%
pyinstaller bri_ecr.spec --clean --noconfirm

REM Check if build was successful
if exist "dist\bri-ecr-simulator.exe" (
    echo.
    echo ========================================
    echo BUILD SUCCESSFUL!
    echo ========================================
    echo Executable created at: dist\bri-ecr-simulator.exe
    echo Publisher: Verifone
    echo Developer: Frederick Armando Jerusha
    echo Version: 1.0.0
    echo.
    echo ANTIVIRUS NOTICE:
    echo This executable may trigger false positives in antivirus software.
    echo See ANTIVIRUS_README.txt for detailed information.
    echo.
    echo TO DISTRIBUTE:
    echo 1. Send dist\bri-ecr-simulator.exe to your clients
    echo 2. Include ANTIVIRUS_README.txt for antivirus information
    echo 3. Add to antivirus whitelist if needed
    echo.
) else (
    echo.
    echo ========================================
    echo BUILD FAILED!
    echo ========================================
    echo Check the output above for errors.
)

pause