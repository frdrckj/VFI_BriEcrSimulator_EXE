# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

# Helper function to safely add files that may not exist
def safe_add_data(file_path, dest_path):
    if os.path.exists(file_path):
        return [(file_path, dest_path)]
    else:
        print(f"Warning: {file_path} not found, skipping...")
        return []

# Build the datas list
datas = [
    ('src/static/*', 'src/static'),
]

# Add database files if they exist
if os.path.exists('src/database'):
    datas.append(('src/database/*', 'src/database'))

# Add optional configuration files
datas.extend(safe_add_data('src/routes/settings.json', 'src/routes'))
datas.extend(safe_add_data('src/routes/transaction_history.json', 'src/routes'))

# Add ECR library files
datas.extend(safe_add_data('src/routes/BriEcrLibrary.dll', 'src/routes'))
datas.extend(safe_add_data('src/routes/libBriEcrLibrary.so', 'src/routes'))

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'flask',
        'flask_cors',
        'flask_sqlalchemy',
        'flask_session',
        'src.routes.ecr',
        'src.routes.auth',
        'src.routes.user',
        'src.models.user',
        # New modular ECR components
        'src.routes.ecr_core',
        'src.routes.serial_comm',
        'src.routes.socket_comm',
        'src.routes.ecr_config',
        'src.routes.message_protocol',
        # Additional dependencies for the new modules
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'ctypes',
        'requests',
        'ssl',
        'socket',
        'threading',
        'binascii',
        'uuid',
        'datetime',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce false positives
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'cv2',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='bri-ecr-simulator.exe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.py',  # Add version information
    icon=None,  # You can add an .ico file path here later
    # Additional executable metadata
    manifest=None,
)