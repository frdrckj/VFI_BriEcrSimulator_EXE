@echo off

echo Building BRI ECR executable...

REM Install build requirements
pip install -r build_requirements.txt

REM Clean previous builds
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

REM Build the executable
pyinstaller bri_ecr.spec

REM Check if build was successful
if exist "dist\bri-ecr-simulator.exe" (
    echo Build successful! Executable created at: dist\bri-ecr-simulator.exe
    echo You can now distribute the 'dist\bri-ecr-simulator.exe' file to your clients.
) else (
    echo Build failed. Check the output above for errors.
    exit /b 1
)