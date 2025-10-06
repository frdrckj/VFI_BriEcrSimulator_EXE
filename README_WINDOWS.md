# CIMB ECR Simulator - Windows Installation

## Quick Start

1. **Download** the `cimb-ecr.exe` file
2. **Double-click** `cimb-ecr.exe` to run the application
3. **Open your web browser** and go to: `http://localhost:5001`
4. **Done!** Your ECR simulator is now running

## How to Use

1. **Start the Application:**
   - Double-click `cimb-ecr.exe`
   - A command prompt window will open showing the server is running
   - **DO NOT CLOSE** this command prompt window

2. **Access the Web Interface:**
   - Open any web browser (Chrome, Firefox, Edge, etc.)
   - Navigate to: `http://localhost:5001`
   - You should see the ECR simulator interface

3. **Stop the Application:**
   - Close the command prompt window, or
   - Press `Ctrl + C` in the command prompt window

## Troubleshooting

**Problem: "Windows protected your PC" message**
- Click "More info" → "Run anyway"
- This happens because the executable isn't digitally signed

**Problem: Antivirus blocks the file**
- Add `cimb-ecr.exe` to your antivirus whitelist
- This is common with PyInstaller-generated executables

**Problem: Browser shows "This site can't be reached"**
- Make sure `cimb-ecr.exe` is running (command prompt window should be open)
- Check the URL is exactly: `http://localhost:5001`
- Try refreshing the browser page

**Problem: Port already in use**
- Another application might be using port 5001
- Restart your computer and try again

## System Requirements

- Windows 7 or later (64-bit)
- No Python installation required
- Any modern web browser
- **For Serial Communication:**
  - COM port drivers installed (FTDI, CP210x, Prolific, etc.)
  - Administrator privileges may be required
  - USB-to-Serial cable (if needed)

## Support

If you encounter any issues, please contact your system administrator.