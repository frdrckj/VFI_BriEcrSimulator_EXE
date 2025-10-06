@echo off
echo ========================================
echo CIMB ECR BUILD HELPER
echo ========================================
echo.
echo This will ensure you build from the correct directory.
echo.
echo INSTRUCTIONS:
echo 1. Copy this entire EcrSimulator_web folder to your Windows machine
echo 2. Double-click this BUILD_HERE.bat file (not build_windows.cmd directly)
echo 3. This will automatically run build_windows.cmd from the correct location
echo.
pause
echo.
echo Starting build process...
call build_windows.cmd