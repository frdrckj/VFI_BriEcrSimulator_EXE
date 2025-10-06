# Version file info for Windows executable
# This helps reduce false positive antivirus detections

VSVersionInfo(
  ffi=FixedFileInfo(
    # File version in format: major.minor.build.revision
    filevers=(1,0,0,0),
    # Product version in format: major.minor.build.revision  
    prodvers=(1,0,0,0),
    # File flags: VS_FF_DEBUG, VS_FF_PRERELEASE, etc.
    mask=0x3f,
    flags=0x0,
    # Operating system type
    OS=0x40004,
    # File type: VFT_APP for application
    fileType=0x1,
    # File subtype
    subtype=0x0,
    # Creation date and time
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',  # Language: US English, Character set: Unicode
        [
        StringStruct(u'CompanyName', u'Verifone'),
        StringStruct(u'FileDescription', u'BRI ECR Simulator - Payment Terminal Simulator'),
        StringStruct(u'FileVersion', u'1.0.0.0'),
        StringStruct(u'InternalName', u'bri-ecr-simulator'),
        StringStruct(u'LegalCopyright', u'Copyright (c) 2024 Verifone. Developed by Frederick Armando Jerusha'),
        StringStruct(u'LegalTrademarks', u'Verifone'),
        StringStruct(u'OriginalFilename', u'bri-ecr-simulator.exe'),
        StringStruct(u'ProductName', u'BRI ECR Simulator'),
        StringStruct(u'ProductVersion', u'1.0.0.0'),
        StringStruct(u'Author', u'Frederick Armando Jerusha'),
        StringStruct(u'Comments', u'ECR Payment Terminal Simulator for BRI Bank Integration Testing')
        ])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)