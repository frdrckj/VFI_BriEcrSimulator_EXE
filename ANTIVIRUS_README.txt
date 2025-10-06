CIMB ECR SIMULATOR - ANTIVIRUS INFORMATION
==========================================

Application Name: CIMB ECR Simulator
Publisher: Verifone
Developer: Frederick Armando Jerusha
Version: 1.0.0
Copyright: (c) 2024 Verifone

ABOUT FALSE POSITIVE DETECTIONS:
--------------------------------
This application may be flagged by some antivirus software as potentially suspicious.
This is a common occurrence with PyInstaller-generated executables and is a FALSE POSITIVE.

REASONS FOR FALSE POSITIVES:
---------------------------
1. The application is packaged with PyInstaller, which bundles Python runtime
2. It creates network connections (for ECR communication)
3. It accesses serial ports (for hardware communication)
4. It logs transactions to files
5. It's a newly compiled executable without established reputation

WHAT THIS APPLICATION DOES:
---------------------------
- Simulates Electronic Cash Register (ECR) communication
- Connects to CIMB bank payment terminals
- Processes payment transactions for testing purposes
- Logs transaction data for debugging
- Provides a web interface for transaction testing

SECURITY MEASURES:
-----------------
- Source code is available for inspection
- No malicious code is present
- Application only communicates with configured ECR endpoints
- All network traffic is for legitimate payment processing
- File operations are limited to logging and configuration

TO REDUCE FALSE POSITIVES:
-------------------------
1. Add this executable to your antivirus whitelist/exceptions
2. Submit the file to your antivirus vendor for analysis
3. Use Windows Defender exclusions if needed
4. Contact your IT department for enterprise environments

DIGITAL SIGNATURE:
-----------------
For production use, this executable should be code-signed with a valid certificate.
Contact Frederick Armando Jerusha or Verifone for signed versions.

SUPPORT CONTACT:
---------------
Developer: Frederick Armando Jerusha
Company: Verifone
Purpose: ECR Testing and Integration

This software is intended for authorized personnel only and should be used 
in secure testing environments for payment system integration.