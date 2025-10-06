# BRI ECR Simulator Web App

## Key Changes Made

### 1. Updated Backend Implementation
- **Backend file**: `src/routes/ecr.py` - Complete implementation following the documentation
- **ReqData Structure**: Implemented proper fixed-length data structure as per documentation:
  - `chTransType` (1 byte) - Transaction type
  - `szAmount` (12 bytes) - Transaction amount
  - `szInvNo` (6 bytes) - Invoice number
  - `szCardNo` (19 bytes) - Card number

- **RspData Structure**: Implemented comprehensive response parsing with all 25+ fields as per documentation:
  - Terminal ID, Merchant ID, Trace Number, Invoice Number
  - Entry Mode, Transaction Amounts, Card Details
  - Date/Time, Approval Code, Response Code
  - Reference Numbers, Installment Details, Point Rewards, etc.

### 2. Communication Protocol
- **Serial Communication**: Direct communication with ECR adaptor via serial port
- **Socket Communication**: Network communication with ECR adaptor via TCP/IP
- **Message Format**: Follows the exact byte-level protocol described in documentation
- **Error Handling**: Comprehensive error handling for communication failures

### 3. API Endpoints
- `POST /api/build_request` - Build request message in ReqData format
- `POST /api/process` - Process complete transaction (build request + send + parse response)
- `GET/POST /api/settings` - Manage ECR communication settings
- `GET /api/history` - Get transaction history
- `POST /api/test_connection` - Test connection to ECR adaptor

### 4. Frontend Updates
- Updated to use the new `/api/process` endpoint
- Maintains compatibility with existing UI
- Shows proper request/response data in ReqData/RspData format

## Installation and Setup

### Prerequisites
- Python 3.11+
- pip3

### Installation Steps

1. **Install Dependencies**
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Run the Application**
   ```bash
   cd /path/to/bri-ecr-simulator
   chmod +x start.sh
   ./start.sh
   ```

   The start script will automatically:
   - Create a virtual environment if it doesn't exist
   - Install/update dependencies
   - Start the Flask application

   **Note**: When you run the application, you'll see:
   ```
   * Serving Flask app 'main'
   * Debug mode: off
   ```
   This is normal behavior. The server is running successfully and ready to accept requests. The application will be accessible at `http://localhost:5001` even though no additional output is shown in the console.

3. **Access the Web Interface**
   - Open browser to `http://localhost:5001`
   - Configure settings via the Settings button
   - Test transactions

## Configuration

### Serial Communication
- **Serial Port**: Select appropriate COM port (e.g., COM1, COM2, etc.)
- **Baud Rate**: 9600, 19200, 38400, 57600, or 115200
- **Data Bits**: 8 (default)
- **Stop Bits**: 1 or 2
- **Parity**: None, Even, or Odd

### Socket Communication
- **IP Address**: IP of the ECR adaptor (default: 127.0.0.1)
- **Port**: Port number (default: 9001)
- **SSL**: Enable/disable SSL encryption

## Usage

1. **Configure Connection**
   - Click "Settings" button
   - Choose communication type (Serial or Socket)
   - Configure connection parameters
   - Save settings

2. **Perform Transaction**
   - Select transaction type (SALE, VOID, REFUND, etc.)
   - Enter amount
   - Click "Send" to process transaction
   - View response in the Response area

3. **Monitor Results**
   - Check transaction history on the right panel
   - View detailed response data in JSON format
   - Monitor connection status

## Transaction Types Supported

- **SALE** (01) - Standard sale transaction
- **INSTALLMENT** (02) - Installment payment
- **VOID** (03) - Void previous transaction
- **REFUND** (04) - Refund transaction
- **QRIS MPM** (05) - QRIS Merchant Presented Mode
- **QRIS CPM** (0A) - QRIS Customer Presented Mode
- **QRIS NOTIFICATION** (06) - QRIS notification
- **QRIS REFUND** (07) - QRIS refund
- **POINT REWARD** (08) - Point reward transaction
- **TEST HOST** (09) - Test host connection
- **SETTLEMENT** (0B) - Settlement
- **REPRINT** (0C) - Reprint receipt
- **REPORT** (0D) - Generate report
- **LOGON** (11) - Logon to system
  - **Note**: LOGON transactions may take longer to complete (typically 30-60 seconds)
  - The simulator will continuously poll for results until completion (up to 10 minutes)

## Technical Details

### Message Structure
The application now follows the exact `ReqData` and `RspData` structures as documented in `BriEcrSimulator.exe`:

**Request Message (ReqData)**:
```
Offset | Size | Field        | Description
-------|------|--------------|------------------
0      | 1    | chTransType  | Transaction type
1      | 12   | szAmount     | Amount (padded)
13     | 6    | szInvNo      | Invoice number
19     | 19   | szCardNo     | Card number
```

**Response Message (RspData)**:
Contains 25+ fields including transaction details, card information, approval codes, and additional data as per the documentation.

### Communication Flow
1. **Build Request**: Create ReqData structure with transaction details
2. **Send Request**: Transmit via serial port or socket connection
3. **Receive Response**: Get response from ECR adaptor
4. **Parse Response**: Extract RspData structure from response bytes
5. **Display Results**: Show parsed data in JSON format

## Troubleshooting

### Common Issues

1. **"No serial port specified in settings"**
   - Configure serial port in Settings
   - Ensure correct COM port is selected

2. **"Serial communication error"**
   - Check serial port availability
   - Verify baud rate and other serial parameters
   - Ensure ECR adaptor is connected

3. **"Socket communication error"**
   - Verify IP address and port
   - Check network connectivity
   - Ensure ECR adaptor is listening on specified port

4. **"Error parsing response"**
   - Check ECR adaptor response format
   - Verify communication protocol compatibility

### Logging
- Application logs are written to `ecr_simulator.log`
- Check logs for detailed error information
- Log level can be adjusted in the code

## Compatibility

This implementation is designed to be compatible with:
- **BRI ECR Adaptor** on Verifone EDC devices via REST API
- **android_id_ecradaptor** Android application
- **BriEcrSimulator.exe** protocol and data structures
- **Serial and Socket communication** methods
- **Windows and Linux** environments (with appropriate native libraries)

## How the ECR Adaptor Communication Works

### 1. ECR Adaptor Input (What it expects from external applications)
The android_id_ecradaptor accepts input via two methods:

**A. Intent-based communication** (for other Android apps):
- Action: `com.verifone.app.bri`
- Intent extras with encrypted message containing:
  ```json
  {
    "version": "A00",
    "transType": "SALE|VOID|REFUND|etc",
    "transData": {
      "paymentType": "CARD",
      "amt": "amount_in_rupiah",
      "orgTraceNo": "trace_number",
      "pan": "card_number",
      "authCode": "approval_code"
    }
  }
  ```

**B. REST API** (for external systems like this simulator):
- Endpoints: `/transaction/bri` and `/result/bri`
- Authentication: Basic Auth (`VfiF4BRI` : `VFI{SERIAL_NUMBER}`)
- Request format:
  ```json
  {
    "transType": "01-0E (hex codes)",
    "transAmount": "amount_in_cents",
    "invoiceNo": "invoice_number",
    "cardNumber": "card_number"
  }
  ```

### 2. ECR Adaptor Output (What it provides back)
The adaptor returns standardized response data:
```json
{
  "version": "A00",
  "transType": "SALE|VOID|etc",
  "result": "0=success, -1=failed",
  "resultMsg": "status_message",
  "transData": {
    "respCode": "00=approved",
    "respMsg": "response_message",
    "paymentType": "CARD",
    "amt": "transaction_amount",
    "tid": "terminal_id",
    "mid": "merchant_id",
    "transDate": "YYYYMMDD",
    "transTime": "HHMMSS",
    "invoiceNo": "invoice_number",
    "traceNo": "trace_number",
    "authCode": "approval_code",
    "refNo": "reference_number"
  }
}
```

### 3. How this Simulator Works with ECR Adaptor
1. **Configuration**: Set `enable_rest_api: true` in settings.json
2. **Authentication**: Uses `VfiF4BRI` : `VFIV1E0212639` (configurable serial number)
3. **Transaction Flow**:
   - Simulator sends POST to `/transaction/bri` with transaction data
   - ECR adaptor validates request and returns transaction ID
   - ECR adaptor launches BRI app via Intent with encrypted message
   - User performs transaction on BRI app
   - BRI app returns result to ECR adaptor
   - **Simulator polls `/result/bri` every 100ms with transaction ID until completion**
   - **Polling timeout: 10 minutes (matching desktop version's behavior)**
   - **Desktop version polls indefinitely; web version uses 10-minute safety timeout**
4. **Response Processing**: ECR adaptor returns standardized JSON response

### 4. Differences from .exe Behavior
- **.exe approach**: Uses native binary protocol over serial/socket
- **This simulator**: Uses REST API for easier integration and debugging
- **Both methods**: Achieve the same result - launching BRI app and getting transaction results

## Files Structure

```
bri-ecr-simulator/
├── src/
│   ├── main.py                 # Flask application entry point
│   ├── routes/
│   │   └── ecr.py             # ECR implementation with REST API and native protocol support
│   └── static/
│       ├── index.html         # Web interface
│       ├── script.js          # Frontend JavaScript
│       └── style.css          # Styling
├── requirements.txt           # Python dependencies
└── README.md                 # This file
```

## Support

For issues or questions regarding this implementation, please refer to:
- The original `DocumentationforBriEcrSimulator.md`
- Application logs in `ecr_simulator.log`
- Source code comments in `src/routes/ecr.py`

# bri-ecr-simulator
# VFI-bri-ecr-simulator
# VFI-Bri_ECR_Simulator
# VFI-Bri_ECR_Simulator
# VFI_BriEcrSimulator
