#!/usr/bin/env python3
"""
Script to check ECR library loading and serial port access
"""
import os
import sys
import platform
import ctypes
import serial
import serial.tools.list_ports

def check_library_loading():
    """Check if ECR library can be loaded"""
    print("=" * 50)
    print("CHECKING ECR LIBRARY LOADING")
    print("=" * 50)
    
    # Determine library name based on platform
    lib_name = "CimbEcrLibrary.dll" if platform.system() == "Windows" else "libCimbEcrLibrary.so"
    print(f"Platform: {platform.system()}")
    print(f"Looking for library: {lib_name}")
    
    # Get base directory (where this script is located)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_routes_dir = os.path.join(base_dir, "src", "routes")
    
    # Search paths (same as in ecr.py)
    search_paths = [
        os.path.join(src_routes_dir, lib_name),  # src/routes/
        os.path.join(base_dir, "src", lib_name),  # src/
        os.path.join(base_dir, lib_name),  # project root
        lib_name,  # system PATH
    ]
    
    print(f"\nSearch paths:")
    for i, path in enumerate(search_paths, 1):
        exists = os.path.exists(path)
        print(f"  {i}. {path} - {'✓ EXISTS' if exists else '✗ NOT FOUND'}")
        if exists:
            # Check file permissions
            readable = os.access(path, os.R_OK)
            executable = os.access(path, os.X_OK)
            print(f"     Readable: {'✓' if readable else '✗'}")
            print(f"     Executable: {'✓' if executable else '✗'}")
            
            # Get file size
            size = os.path.getsize(path)
            print(f"     Size: {size} bytes")
    
    # Try to load the library
    print(f"\nTrying to load library...")
    lib_path = None
    for path in search_paths:
        if os.path.exists(path):
            lib_path = path
            break
    
    if lib_path:
        try:
            print(f"Attempting to load: {lib_path}")
            ecr_lib = ctypes.CDLL(lib_path)
            print("✓ Library loaded successfully!")
            
            # Try to get version
            try:
                version_buf = ctypes.create_string_buffer(20)
                ecr_lib.ecrGetVersion.argtypes = [ctypes.c_char_p]
                ecr_lib.ecrGetVersion.restype = None
                ecr_lib.ecrGetVersion(version_buf)
                version = version_buf.value.decode('ascii')
                print(f"✓ Library version: {version}")
                return True, None
            except Exception as e:
                print(f"⚠ Library loaded but version check failed: {e}")
                return True, f"Version check failed: {e}"
                
        except Exception as e:
            print(f"✗ Failed to load library: {e}")
            return False, str(e)
    else:
        error_msg = f"Library file {lib_name} not found in any search path"
        print(f"✗ {error_msg}")
        return False, error_msg

def check_serial_access():
    """Check serial port access"""
    print("\n" + "=" * 50)
    print("CHECKING SERIAL PORT ACCESS")
    print("=" * 50)
    
    # List available serial ports
    print("Available serial ports:")
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("  No serial ports found")
        return False, "No serial ports available"
    
    for port in ports:
        print(f"  - {port.device}: {port.description}")
    
    # Try to access each port
    accessible_ports = []
    for port in ports:
        try:
            print(f"\nTesting access to {port.device}...")
            ser = serial.Serial(
                port=port.device,
                baudrate=9600,
                bytesize=8,
                stopbits=1,
                parity='N',
                timeout=1
            )
            ser.close()
            print(f"  ✓ Can access {port.device}")
            accessible_ports.append(port.device)
        except serial.SerialException as e:
            print(f"  ✗ Cannot access {port.device}: {e}")
        except Exception as e:
            print(f"  ✗ Unexpected error accessing {port.device}: {e}")
    
    if accessible_ports:
        print(f"\n✓ Accessible ports: {', '.join(accessible_ports)}")
        return True, accessible_ports
    else:
        print(f"\n✗ No accessible serial ports")
        return False, "No accessible serial ports"

def check_permissions():
    """Check process permissions"""
    print("\n" + "=" * 50)
    print("CHECKING PROCESS PERMISSIONS")
    print("=" * 50)
    
    print(f"Running as user: {os.getlogin() if hasattr(os, 'getlogin') else 'Unknown'}")
    print(f"Process UID: {os.getuid() if hasattr(os, 'getuid') else 'N/A'}")
    print(f"Process GID: {os.getgid() if hasattr(os, 'getgid') else 'N/A'}")
    
    # Check if running as root/admin
    if platform.system() == "Windows":
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            print(f"Running as administrator: {'✓' if is_admin else '✗'}")
        except:
            print("Cannot determine admin status")
    else:
        is_root = os.getuid() == 0 if hasattr(os, 'getuid') else False
        print(f"Running as root: {'✓' if is_root else '✗'}")
        
        # Check dialout group membership (Linux)
        try:
            import grp
            import pwd
            username = pwd.getpwuid(os.getuid()).pw_name
            dialout_group = grp.getgrnam('dialout')
            in_dialout = username in dialout_group.gr_mem
            print(f"User '{username}' in dialout group: {'✓' if in_dialout else '✗'}")
        except:
            print("Cannot check dialout group membership")

def main():
    print("ECR LIBRARY AND SERIAL PORT DIAGNOSTIC TOOL")
    print("=" * 60)
    
    # Check library loading
    lib_success, lib_error = check_library_loading()
    
    # Check serial port access
    serial_success, serial_result = check_serial_access()
    
    # Check permissions
    check_permissions()
    
    # Summary
    print("\n" + "=" * 50)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 50)
    
    print(f"Library Loading: {'✓ SUCCESS' if lib_success else '✗ FAILED'}")
    if not lib_success:
        print(f"  Error: {lib_error}")
    
    print(f"Serial Port Access: {'✓ SUCCESS' if serial_success else '✗ FAILED'}")
    if not serial_success:
        print(f"  Error: {serial_result}")
    elif isinstance(serial_result, list):
        print(f"  Accessible ports: {', '.join(serial_result)}")
    
    # Recommendations
    print("\nRECOMMENDations:")
    if not lib_success:
        print("- Check if library file exists and has correct permissions")
        print("- Ensure all library dependencies are installed")
        print("- Try running as administrator/root")
    
    if not serial_success:
        if platform.system() == "Linux":
            print("- Add user to 'dialout' group: sudo usermod -a -G dialout $USER")
            print("- Then logout and login again")
        elif platform.system() == "Windows":
            print("- Try running as administrator")
        print("- Ensure no other application is using the serial port")
        print("- Check if serial port drivers are installed")

if __name__ == "__main__":
    main()