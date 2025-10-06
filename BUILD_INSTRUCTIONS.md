# Build Instructions for CIMB ECR Simulator (Windows)

## Quick Start
1. **Copy the entire `EcrSimulator_web` folder to your Windows machine**
2. **Double-click `BUILD_HERE.bat`** (NOT `build_windows.cmd` directly)
3. Wait for the build to complete
4. Find your executable in the `dist` folder

## Requirements
- Windows 10/11
- Python 3.8 or newer installed from [python.org](https://python.org)
- Python must be added to PATH during installation

## Build Process

### Method 1: Automated (Recommended)
```cmd
# Double-click BUILD_HERE.bat
# This automatically runs from the correct directory
```

### Method 2: Manual
```cmd
# Open Command Prompt in the EcrSimulator_web folder
# (Right-click in folder, select "Open in Terminal" or type cmd in address bar)
cd path\to\EcrSimulator_web
build_windows.cmd
```

## Common Issues & Solutions

### Error: "No such file or directory: 'build_requirements.txt'"
**Problem**: Running from wrong directory (likely C:\Windows\System32)
**Solution**: 
- Use `BUILD_HERE.bat` instead
- OR manually navigate to EcrSimulator_web folder first

### Error: "Do not run pyinstaller from C:\Windows\System32"
**Problem**: Command prompt opened in System32 instead of project folder
**Solution**:
1. Navigate to EcrSimulator_web folder in File Explorer
2. Type `cmd` in the address bar
3. Run `build_windows.cmd`

### Error: "Python is not installed or not in PATH"
**Problem**: Python not installed or not accessible
**Solution**:
1. Download Python from [python.org](https://python.org)
2. **IMPORTANT**: Check "Add Python to PATH" during installation
3. Restart command prompt and try again

### Error: Missing module during build
**Problem**: Dependencies not installed
**Solution**: The script should handle this automatically, but you can manually run:
```cmd
pip install -r build_requirements.txt
```

## Output Files
- **Executable**: `dist\cimb-ecr-simulator.exe`
- **Build logs**: Check console output for any warnings
- **Distribution**: Share the entire `dist` folder or just the `.exe` file

## Antivirus Warnings
The built executable may trigger false positives. This is normal for PyInstaller executables.
- See `ANTIVIRUS_README.txt` for detailed information
- Add to antivirus whitelist if needed
- The executable is safe - it's just how PyInstaller packages Python apps

## File Structure After Build
```
EcrSimulator_web/
├── BUILD_HERE.bat          ← Use this to build
├── build_windows.cmd       ← Main build script
├── cimb_ecr.spec          ← PyInstaller config
├── build_requirements.txt ← Dependencies
├── src/                   ← Source code
├── build/                 ← Temporary build files
└── dist/                  ← Final executable here
    └── cimb-ecr-simulator.exe
```

## Troubleshooting
If you encounter issues:
1. Make sure you're in the right directory (`EcrSimulator_web`)
2. Check that all required files exist (script will verify)
3. Try running as Administrator if permission issues occur
4. Check Python installation: `python --version`

## Contact
For build issues, check the console output for specific error messages.