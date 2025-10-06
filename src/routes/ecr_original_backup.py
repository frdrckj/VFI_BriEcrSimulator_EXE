import json
import time
import os
import binascii
import uuid
import serial
import serial.tools.list_ports
import socket
import requests
import logging
import sys
import traceback
import ctypes
import platform
import threading
import subprocess
from flask import Blueprint, request, jsonify, send_file

ecr_bp = Blueprint("ecr", __name__)


def get_executable_dir():
    """Get the directory where the executable or script is located"""
    if getattr(sys, "frozen", False):
        # PyInstaller executable
        return os.path.dirname(sys.executable)
    else:
        # Development mode - use the project root
        return os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )


# Configure logging with correct path
EXECUTABLE_DIR = get_executable_dir()
LOG_FILE_PATH = os.path.join(EXECUTABLE_DIR, "ecr_simulator.log")
# Ensure the directory exists
os.makedirs(EXECUTABLE_DIR, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE_PATH,
    level=logging.DEBUG,  # Changed to DEBUG for detailed logging
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
# Log the paths for debugging
logger.info(f"Executable directory: {EXECUTABLE_DIR}")
logger.info(f"Log file path: {LOG_FILE_PATH}")

# Settings file path
BASE_DIR = os.path.dirname(__file__)
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
HISTORY_FILE = os.path.join(BASE_DIR, "transaction_history.json")

# Load settings
app_settings = {}
if os.path.exists(SETTINGS_FILE):
    try:
        with open(SETTINGS_FILE, "r") as f:
            app_settings = json.load(f)
        logger.info(f"Settings loaded: {app_settings}")
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        app_settings = {}

# Load existing transaction history from file
transaction_history = {}
ui_hidden_transactions = set()  # Track transactions hidden from UI
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r") as f:
            transaction_history = json.load(f)
        logger.info(
            f"Transaction history loaded: {len(transaction_history)} transactions"
        )
    except Exception as e:
        logger.error(f"Error loading transaction history: {e}")
        transaction_history = {}
else:
    logger.info("No existing transaction history file found")

is_connected = False
serial_port_opened = False


def save_transaction_history():
    """Save transaction history to JSON file"""
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(transaction_history, f, indent=2)
        logger.debug("Transaction history saved to file")
    except Exception as e:
        logger.error(f"Error saving transaction history: {e}")


# Define C structs matching spec appendices
class SerialData(ctypes.Structure):
    _fields_ = [
        ("szComm", ctypes.c_char * 10),  # Serial port number
        ("chBaudRate", ctypes.c_ubyte),  # Baudrate code (e.g., 3 for 9600)
        ("chDataBit", ctypes.c_ubyte),  # Data bits (e.g., 8)
        ("chStopBit", ctypes.c_ubyte),  # Stop bits (0 for 1)
        ("chParity", ctypes.c_ubyte),  # Parity (0 for none)
    ]


class ReqData(ctypes.Structure):
    _fields_ = [
        ("chTransType", ctypes.c_ubyte),
        ("szAmount", ctypes.c_char * 12),
        (
            "szAddAmount",
            ctypes.c_char * 12,
        ),  # Not used in spec, but included for completeness
        ("szInvNo", ctypes.c_char * 12),
        ("szCardNo", ctypes.c_char * 19),
    ]


class RspData(ctypes.Structure):
    _fields_ = [
        ("chTransType", ctypes.c_ubyte),
        ("szTID", ctypes.c_char * 8),
        ("szMID", ctypes.c_char * 15),
        ("szTraceNo", ctypes.c_char * 6),
        ("szInvoiceNo", ctypes.c_char * 6),
        ("chEntryMode", ctypes.c_ubyte),
        ("szTransAmount", ctypes.c_char * 12),
        ("szTransAddAmount", ctypes.c_char * 12),
        ("szTotalAmount", ctypes.c_char * 12),
        ("szCardNo", ctypes.c_char * 19),
        ("szCardholderName", ctypes.c_char * 26),
        ("szDate", ctypes.c_char * 8),
        ("szTime", ctypes.c_char * 6),
        ("szApprovalCode", ctypes.c_char * 6),
        ("szResponseCode", ctypes.c_char * 2),
        ("szRefNumber", ctypes.c_char * 12),
        ("szReferenceId", ctypes.c_char * 6),
        ("szTerm", ctypes.c_char * 2),
        ("szMonthlyAmount", ctypes.c_char * 12),
        ("szPointReward", ctypes.c_char * 9),
        ("szRedemptionAmount", ctypes.c_char * 11),
        ("szPointBalance", ctypes.c_char * 9),
        ("szFiller", ctypes.c_char * 99),
    ]


# Global library handle
ecr_lib = None
use_library = True

# Allow disabling native library via environment variable for troubleshooting
if os.environ.get("DISABLE_NATIVE_LIBRARY", "").lower() == "true":
    use_library = False
    logger.info("Native library disabled via environment variable")


def init_ecr_library():
    global ecr_lib
    lib_name = (
        "CimbEcrLibrary.dll"
        if platform.system() == "Windows"
        else "libCimbEcrLibrary.so"
    )
    try:
        # Try multiple paths for library loading (development vs PyInstaller builds)
        search_paths = [
            os.path.join(BASE_DIR, lib_name),  # Development: src/routes/
            os.path.join(os.path.dirname(BASE_DIR), lib_name),  # One level up: src/
            os.path.join(
                get_executable_dir(), "src", "routes", lib_name
            ),  # PyInstaller: exe_dir/src/routes/
            lib_name,  # Try system PATH
        ]

        lib_path = None
        for path in search_paths:
            if os.path.exists(path):
                lib_path = path
                break

        if lib_path:
            ecr_lib = ctypes.CDLL(lib_path)
            logger.info(f"Loaded {lib_name} successfully from {lib_path}")
        else:
            raise FileNotFoundError(
                f"Could not find {lib_name} in any search path: {search_paths}"
            )

        # Set argtypes/restypes for key functions (matching spec appendices)
        ecr_lib.ecrGetVersion.argtypes = [ctypes.c_char_p]
        ecr_lib.ecrGetVersion.restype = None

        ecr_lib.ecrOpenSerialPort.argtypes = [ctypes.POINTER(SerialData)]
        ecr_lib.ecrOpenSerialPort.restype = ctypes.c_int

        ecr_lib.ecrSendSerialPort.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        ecr_lib.ecrSendSerialPort.restype = ctypes.c_int

        ecr_lib.ecrRecvSerialPort.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        ecr_lib.ecrRecvSerialPort.restype = ctypes.c_int

        ecr_lib.ecrCloseSerialPort.argtypes = []
        ecr_lib.ecrCloseSerialPort.restype = None

        ecr_lib.ecrPackRequest.argtypes = [ctypes.c_void_p, ctypes.POINTER(ReqData)]
        ecr_lib.ecrPackRequest.restype = ctypes.c_int

        ecr_lib.ecrParseResponse.argtypes = [ctypes.c_void_p, ctypes.POINTER(RspData)]
        ecr_lib.ecrParseResponse.restype = ctypes.c_int

        # Test version call
        version_buf = ctypes.create_string_buffer(20)
        ecr_lib.ecrGetVersion(version_buf)
        logger.info(f"Library version: {version_buf.value.decode('ascii')}")

    except Exception as e:
        logger.error(f"Failed to load {lib_name}: {e}. Falling back to native Python.")
        ecr_lib = None


# Call init at script start
init_ecr_library()


def calculate_lrc(data):
    lrc = 0
    for byte in data:
        lrc ^= byte
    logger.debug(f"LRC calculated: {lrc:02X}")
    return lrc


def calculate_crc(data):
    """Calculate CRC-16 for socket communication compatibility"""
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc.to_bytes(2, byteorder="big")


def pack_request_msg(trans_type, amount, invoice_no, card_no=""):
    """Pack request message following CIMB Native protocol."""
    logger.info(
        f"Packing request: trans_type={trans_type}, amount={amount}, invoice_no={invoice_no}, card_no={card_no}"
    )
    # Validate inputs
    try:
        trans_type_int = int(trans_type, 16)
        if trans_type_int < 0x01 or trans_type_int > 0x0E:
            raise ValueError(f"Invalid trans_type: {trans_type}")
    except ValueError:
        logger.error(f"Invalid trans_type format: {trans_type}")
        raise ValueError("Transaction type must be a valid hex code (01-0E)")
    try:
        amount_int = int(amount)
        if amount_int < 0:
            raise ValueError("Amount must be non-negative")
        # Multiply by 100 for serial communication (convert to cents)
        if app_settings.get("communication", "Serial") == "Serial":
            amount_int = amount_int * 100
            logger.info(
                f"Serial communication: multiplying amount by 100: {amount} -> {amount_int}"
            )
        amount_str = f"{amount_int:012d}"
        logger.info(
            f"Amount conversion: original='{amount}' -> int={amount_int} -> formatted='{amount_str}'"
        )
        if not amount_str.isdigit():
            raise ValueError("Amount must be numeric")
    except ValueError:
        logger.error(f"Invalid amount format: {amount}")
        raise ValueError("Amount must be a valid number")
    invoice_str = str(invoice_no or "0")
    if not invoice_str.isdigit():
        logger.error(f"Invalid invoice_no format: {invoice_no}")
        raise ValueError("Invoice number must be numeric")

    # For void and QRIS notification transactions, allow flexible input and pad to 6 digits
    if trans_type == "03":  # VOID transaction
        if len(invoice_str) > 6:
            logger.error(f"Trace number too long: {invoice_no}")
            raise ValueError("Trace number must be 6 digits or less")
        # Pad to 6 digits for void trace number
        invoice_str = invoice_str.zfill(6)
        logger.info(f"Void trace number formatted: {invoice_no} -> {invoice_str}")
    elif trans_type == "06":  # QRIS NOTIFICATION transaction
        if len(invoice_str) > 6:
            logger.error(f"Reference ID too long: {invoice_no}")
            raise ValueError("Reference ID must be 6 digits or less")
        # Pad to 6 digits for QRIS notification reference ID
        invoice_str = invoice_str.zfill(6)
        logger.info(
            f"QRIS notification reference ID formatted: {invoice_no} -> {invoice_str}"
        )
    else:
        if len(invoice_str) > 6:
            logger.error(f"Invoice_no too long: {invoice_no}")
            raise ValueError("Invoice number must be 6 digits or less")
    if card_no and not all(c.isalnum() or c == " " for c in card_no):
        logger.error(f"Invalid card_no format: {card_no}")
        raise ValueError("Card number must be alphanumeric")

    if ecr_lib and use_library:
        try:
            req = ReqData()
            req.chTransType = int(trans_type, 16)
            req.szAmount = amount_str.encode("ascii")
            req.szAddAmount = b"000000000000"
            req.szInvNo = f"{int(invoice_str):012d}".encode("ascii")[:12]  # Pad to 12
            req.szCardNo = card_no.ljust(19, " ").encode("ascii")[:19]

            req_msg_buf = ctypes.create_string_buffer(
                205
            )  # Enough for STX + 200 data + ETX + LRC
            ret = ecr_lib.ecrPackRequest(req_msg_buf, ctypes.byref(req))
            if ret < 0:
                raise ValueError(f"Pack failed: {ret}")
            return req_msg_buf.raw[:ret]  # Return packed bytes
        except Exception as e:
            logger.error(f"Library pack failed: {e}. Using fallback.")

    # Fallback manual pack
    chTransType = int(trans_type, 16)
    szAmount = amount_str.encode("ascii")
    szInvNo = f"{int(invoice_str):06d}".encode("ascii")
    szCardNo = card_no.ljust(19, " ").encode("ascii")[:19]
    szFiller = b" " * 162
    message_data = bytes([chTransType]) + szAmount + szInvNo + szCardNo + szFiller
    assert len(message_data) == 200, f"Invalid data length: {len(message_data)}"
    stx = b"\x02"
    length_bytes = b"\x02\x00"  # 200
    etx = b"\x03"
    to_lrc = length_bytes + message_data + etx
    lrc_value = calculate_lrc(to_lrc)
    lrc = bytes([lrc_value])
    packed = stx + length_bytes + message_data + etx + lrc
    logger.debug(f"Packed message: {binascii.hexlify(packed).decode()}")
    return packed


def parse_response_msg(response_bytes):
    logger.info(f"Parsing response: {binascii.hexlify(response_bytes).decode()}")

    if ecr_lib and use_library:
        try:
            rsp = RspData()
            rsp_msg_buf = ctypes.create_string_buffer(
                response_bytes, len(response_bytes)
            )
            ret = ecr_lib.ecrParseResponse(rsp_msg_buf, ctypes.byref(rsp))
            if ret != 0:
                raise ValueError(f"Parse failed: {ret}")
            return {
                "transType": f"{rsp.chTransType:02X}",
                "tid": rsp.szTID.value.decode("ascii", errors="ignore").strip(),
                "mid": rsp.szMID.value.decode("ascii", errors="ignore").strip(),
                "traceNo": rsp.szTraceNo.value.decode("ascii", errors="ignore").strip(),
                "invoiceNo": rsp.szInvoiceNo.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "entryMode": chr(rsp.chEntryMode),
                "transAmount": rsp.szTransAmount.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "transAddAmount": rsp.szTransAddAmount.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "totalAmount": rsp.szTotalAmount.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "cardNo": rsp.szCardNo.value.decode("ascii", errors="ignore").strip(),
                "cardholderName": rsp.szCardholderName.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "date": rsp.szDate.value.decode("ascii", errors="ignore").strip(),
                "time": rsp.szTime.value.decode("ascii", errors="ignore").strip(),
                "approvalCode": rsp.szApprovalCode.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "responseCode": rsp.szResponseCode.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "refNumber": rsp.szRefNumber.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "referenceId": rsp.szReferenceId.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "term": rsp.szTerm.value.decode("ascii", errors="ignore").strip(),
                "monthlyAmount": rsp.szMonthlyAmount.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "pointReward": rsp.szPointReward.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "redemptionAmount": rsp.szRedemptionAmount.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "pointBalance": rsp.szPointBalance.value.decode(
                    "ascii", errors="ignore"
                ).strip(),
                "qrCode": rsp.szFiller.value.decode("ascii", errors="ignore").strip(),
            }
        except Exception as e:
            logger.error(f"Library parse failed: {e}. Using fallback.")

    # Fallback manual parse
    if len(response_bytes) < 5:
        raise ValueError("Response too short")
    if response_bytes[0] != 0x02:
        raise ValueError("Missing STX")
    length_bytes = response_bytes[1:3]
    msg_len = length_bytes[0] * 100 + length_bytes[1]
    if msg_len != 300:
        raise ValueError(f"Invalid length: {msg_len}, expected 300")
    expected_total = 1 + 2 + msg_len + 1 + 1
    if len(response_bytes) != expected_total:
        raise ValueError(
            f"Invalid total length: {len(response_bytes)}, expected {expected_total}"
        )
    data_start = 3
    data_end = data_start + msg_len
    data = response_bytes[data_start:data_end]
    etx = response_bytes[data_end]
    if etx != 0x03:
        raise ValueError("Missing ETX")
    received_lrc = response_bytes[-1]
    to_lrc = length_bytes + data + bytes([etx])
    computed_lrc = calculate_lrc(to_lrc)
    if received_lrc != computed_lrc:
        raise ValueError(
            f"LRC mismatch: received {received_lrc:02X}, computed {computed_lrc:02X}"
        )
    logger.debug("Response validation successful, unpacking data...")
    offset = 0
    chTransType = data[offset]
    offset += 1
    szTID = data[offset : offset + 8]
    offset += 8
    szMID = data[offset : offset + 15]
    offset += 15
    szTraceNo = data[offset : offset + 6]
    offset += 6
    szInvoiceNo = data[offset : offset + 6]
    offset += 6
    chEntryMode = data[offset : offset + 1]
    offset += 1
    szTransAmount = data[offset : offset + 12]
    offset += 12
    szTransAddAmount = data[offset : offset + 12]
    offset += 12
    szTotalAmount = data[offset : offset + 12]
    offset += 12
    szCardNo = data[offset : offset + 19]
    offset += 19
    szCardholderName = data[offset : offset + 26]
    offset += 26
    szDate = data[offset : offset + 8]
    offset += 8
    szTime = data[offset : offset + 6]
    offset += 6
    szApprovalCode = data[offset : offset + 6]
    offset += 6
    szResponseCode = data[offset : offset + 2]
    offset += 2
    szRefNumber = data[offset : offset + 12]
    offset += 12
    szReferenceId = data[offset : offset + 6]
    offset += 6
    szTerm = data[offset : offset + 2]
    offset += 2
    szMonthlyAmount = data[offset : offset + 12]
    offset += 12
    szPointReward = data[offset : offset + 9]
    offset += 9
    szRedemptionAmount = data[offset : offset + 11]
    offset += 11
    szPointBalance = data[offset : offset + 9]
    offset += 9
    szFiller = data[offset : offset + 99]
    offset += 99
    return {
        "transType": f"{chTransType:02X}",
        "tid": szTID.decode("ascii", errors="ignore").strip(),
        "mid": szMID.decode("ascii", errors="ignore").strip(),
        "traceNo": szTraceNo.decode("ascii", errors="ignore").strip(),
        "invoiceNo": szInvoiceNo.decode("ascii", errors="ignore").strip(),
        "entryMode": chEntryMode.decode("ascii", errors="ignore").strip(),
        "transAmount": szTransAmount.decode("ascii", errors="ignore").strip(),
        "transAddAmount": szTransAddAmount.decode("ascii", errors="ignore").strip(),
        "totalAmount": szTotalAmount.decode("ascii", errors="ignore").strip(),
        "cardNo": szCardNo.decode("ascii", errors="ignore").strip(),
        "cardholderName": szCardholderName.decode("ascii", errors="ignore").strip(),
        "date": szDate.decode("ascii", errors="ignore").strip(),
        "time": szTime.decode("ascii", errors="ignore").strip(),
        "approvalCode": szApprovalCode.decode("ascii", errors="ignore").strip(),
        "responseCode": szResponseCode.decode("ascii", errors="ignore").strip(),
        "refNumber": szRefNumber.decode("ascii", errors="ignore").strip(),
        "referenceId": szReferenceId.decode("ascii", errors="ignore").strip(),
        "term": szTerm.decode("ascii", errors="ignore").strip(),
        "monthlyAmount": szMonthlyAmount.decode("ascii", errors="ignore").strip(),
        "pointReward": szPointReward.decode("ascii", errors="ignore").strip(),
        "redemptionAmount": szRedemptionAmount.decode("ascii", errors="ignore").strip(),
        "pointBalance": szPointBalance.decode("ascii", errors="ignore").strip(),
        "qrCode": szFiller.decode("ascii", errors="ignore").strip(),
    }


def open_serial_port():
    """Open serial port using native library exactly like desktop Serial.connect()"""
    global ecr_lib

    if not ecr_lib:
        logger.error("ECR library not available")
        return False

    serial_port = app_settings.get("serial_port", "")
    if not serial_port:
        logger.error("No serial port specified")
        return False

    try:
        sr = SerialData()
        # Configure exactly like desktop Serial.connect()
        port_bytes = serial_port.encode("ascii")
        if len(port_bytes) >= 10:
            port_bytes = port_bytes[:9]
        sr.szComm = port_bytes + b"\x00" * (10 - len(port_bytes))

        baud_map = {
            1200: 0,
            2400: 1,
            4800: 2,
            9600: 3,
            14400: 4,
            19200: 5,
            38400: 6,
            57600: 7,
            115200: 8,
        }
        sr.chBaudRate = baud_map.get(int(app_settings.get("speed_baud", 9600)), 3)
        sr.chDataBit = int(app_settings.get("data_bits", 8))

        stop_map = {"1": 0, "1.5": 1, "2": 2}
        sr.chStopBit = stop_map.get(app_settings.get("stop_bits", "1"), 0)

        parity_map = {"N": 0, "O": 1, "E": 2, "M": 3, "S": 4}
        sr.chParity = parity_map.get(app_settings.get("parity", "N")[0].upper(), 0)

        # Open serial port exactly like desktop Serial.connect() line 81
        ret = ecr_lib.ecrOpenSerialPort(ctypes.byref(sr))
        if ret != 0:
            logger.error(f"Failed to open serial port: {ret}")
            return False

        logger.info(f"Serial port {serial_port} opened successfully")
        return True

    except Exception as e:
        logger.error(f"Error opening serial port: {str(e)}")
        return False


def close_serial_port():
    """Close serial port using native library exactly like desktop Serial.disconnect()"""
    global ecr_lib, serial_port_opened

    if ecr_lib:
        try:
            ecr_lib.ecrCloseSerialPort()  # Like desktop Serial.disconnect() line 111
            serial_port_opened = False
            logger.info("Serial port closed")
        except Exception as e:
            logger.error(f"Error closing serial port: {str(e)}")


def check_network_connectivity():
    """Check if network/internet connection is available"""
    try:
        # Try to reach a reliable external server
        import urllib.request

        urllib.request.urlopen("http://www.google.com", timeout=3)
        return True
    except Exception:
        try:
            # Alternative check - try to reach local gateway
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["ping", "-n", "1", "8.8.8.8"], capture_output=True, timeout=3
                )
            else:
                result = subprocess.run(
                    ["ping", "-c", "1", "8.8.8.8"], capture_output=True, timeout=3
                )
            return result.returncode == 0
        except Exception:
            return False


def recv_full_message(sock, timeout=2):
    sock.settimeout(timeout)
    stx = sock.recv(1)
    if not stx or stx != b"\x02":
        raise ValueError("Invalid STX")
    llll = sock.recv(2)
    if len(llll) != 2:
        raise ValueError("Invalid LLLL")
    msg_len = llll[0] * 100 + llll[1]
    data = b""
    while len(data) < msg_len:
        chunk = sock.recv(msg_len - len(data))
        if not chunk:
            raise ValueError("Incomplete data")
        data += chunk
    etx = sock.recv(1)
    if etx != b"\x03":
        raise ValueError("Invalid ETX")
    lrc = sock.recv(1)
    if len(lrc) != 1:
        raise ValueError("Invalid LRC")
    full = b"\x02" + llll + data + b"\x03" + lrc
    computed_lrc = calculate_lrc(llll + data + b"\x03")
    if lrc[0] != computed_lrc:
        raise ValueError("LRC mismatch")
    return full


def send_socket_message(ip, port, message, ssl_enabled=False, timeout=2, max_retries=3):
    logger.info(f"Connecting to {ip}:{port}, SSL={ssl_enabled}")
    for attempt in range(1, max_retries + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            if ssl_enabled:
                import ssl

                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                sock = context.wrap_socket(sock)
            sock.connect((ip, port))
            logger.info("Connected successfully")
            # Small delay to ensure terminal is ready
            time.sleep(0.1)
            logger.info(
                f"Sending request (attempt {attempt}): {binascii.hexlify(message).decode()}"
            )
            sock.send(message)
            ack_nak = sock.recv(1)
            if ack_nak == b"\x15":
                logger.warning(f"Received NAK on attempt {attempt}")
                sock.close()
                if attempt < max_retries:
                    logger.info("Retrying...")
                    time.sleep(0.5)  # Wait before retry
                    continue
                raise ValueError("Received NAK after all retries")
            if ack_nak != b"\x06":
                raise ValueError(
                    f"No ACK received, got {binascii.hexlify(ack_nak).decode()}"
                )
            response = recv_full_message(sock)
            sock.send(b"\x06")
            sock.close()
            logger.info(f"Received response: {binascii.hexlify(response).decode()}")
            return response
        except Exception as e:
            logger.error(f"Socket error on attempt {attempt}: {str(e)}")
            if sock:
                sock.close()
            if attempt < max_retries:
                logger.info("Retrying...")
                time.sleep(0.5)
                continue
            raise
    raise ValueError("Failed after all retries")


# Control whether to show library responses or only EDC responses
response_library = False  # Only show responses from actual EDC device


# Serial listener globals - matching desktop SerialListener pattern
serial_listener_thread = None
is_listening = False
show_data = False
pyserial_connection = None
use_pyserial_listener = False


def start_serial_listener():
    """Start serial listener thread exactly like desktop SerialListener"""
    global serial_listener_thread, is_listening
    if is_listening:
        return
    is_listening = True
    serial_listener_thread = threading.Thread(target=serial_listener_loop, daemon=True)
    serial_listener_thread.start()
    logger.info("Serial listener thread started")


def stop_serial_listener():
    """Stop serial listener thread exactly like desktop SerialListener.doStop()"""
    global is_listening
    is_listening = False
    if serial_listener_thread:
        serial_listener_thread.join(timeout=2)
    logger.info("Serial listener thread stopped")


def send_serial_message_native_only(message):
    """Send message using native library only, exactly like desktop Serial.send()"""
    global ecr_lib, show_data

    if not ecr_lib:
        raise ValueError("ECR library not available")

    try:
        # Set show_data to false before sending like desktop Serial.send() line 97
        show_data = False

        # Send using native library exactly like desktop Serial.send() line 98
        send_buf = ctypes.create_string_buffer(message)
        ret = ecr_lib.ecrSendSerialPort(send_buf, len(message))

        if ret != 0:
            raise ValueError(f"Send failed: {ret}")

        logger.info(
            f"Message sent via native library: {binascii.hexlify(message).decode()}"
        )
        return True

    except Exception as e:
        logger.error(f"Native library send error: {str(e)}")
        raise


def serial_listener_loop():
    """Serial listener loop exactly like desktop SerialListener.run()"""
    global show_data, serial_port_opened

    # Initialize serial port using native library exactly like desktop
    if not serial_port_opened:
        if not open_serial_port():
            logger.error("Failed to open serial port for listener")
            return
        serial_port_opened = True

    logger.info("Serial listener loop started - polling for responses like desktop")

    while is_listening:
        try:
            if not ecr_lib:
                logger.error("ECR library not available")
                break

            # Poll for data exactly like desktop SerialListener.run() line 36
            recv_buf = ctypes.create_string_buffer(305)
            byte_len = ecr_lib.ecrRecvSerialPort(
                recv_buf, 305
            )  # Like desktop recvSerialPort(9999)

            if byte_len > 0:
                if byte_len == 1:
                    # Single byte response - ACK/NAK like desktop lines 38-48
                    recv_data = recv_buf.raw[:byte_len]
                    if not show_data:
                        if recv_data[0] == 0x06:
                            logger.info("Received ACK")
                            # Update UI response like desktop textAreaRsp.setText("ACK")
                        elif recv_data[0] == 0x15:
                            logger.info("Received NACK")
                            # Update UI response like desktop textAreaRsp.setText("NACK")
                        else:
                            logger.info("Received UNKNOWN response")
                            # Update UI response like desktop textAreaRsp.setText("UNKNOWN")
                else:
                    # Multi-byte response - full message like desktop lines 49-55
                    show_data = True  # Like desktop doShowData(true)

                    full_response = recv_buf.raw[:byte_len]
                    logger.info(
                        f"Received full response: {binascii.hexlify(full_response).decode()}"
                    )

                    try:
                        # Store raw response as hex string instead of parsing
                        raw_response_hex = (
                            binascii.hexlify(full_response).decode().upper()
                        )

                        # Update transaction history
                        processing_trxs = [
                            k
                            for k, v in transaction_history.items()
                            if v["status"] == "processing"
                        ]

                        if processing_trxs:
                            latest_trx = max(
                                processing_trxs,
                                key=lambda k: transaction_history[k]["timestamp"],
                            )

                            # Set status as completed for now since we have raw response
                            transaction_history[latest_trx]["status"] = "completed"
                            transaction_history[latest_trx][
                                "raw_response"
                            ] = raw_response_hex
                            save_transaction_history()
                            logger.info(
                                f"Updated transaction {latest_trx} with raw response"
                            )
                        else:
                            logger.warning(
                                "Received response but no processing transaction"
                            )

                    except Exception as e:
                        logger.error(f"Error storing raw response: {str(e)}")

            elif byte_len == -3:
                logger.error("INVALID LENGTH")  # Like desktop line 57
            elif byte_len == -4:
                logger.error("INVALID LRC")  # Like desktop line 59
            elif byte_len < 0:
                logger.error(
                    "Serial error, stopping listener"
                )  # Like desktop lines 60-65
                is_listening = False
                close_serial_port()
                break
            else:
                # No data, sleep like desktop line 67
                time.sleep(0.1)

        except Exception as e:
            logger.error(f"Serial listener error: {str(e)}")
            # Like desktop lines 69-71
            break

    # Cleanup
    close_serial_port()
    logger.info("Serial listener loop ended")


def start_pyserial_listener(serial_port):
    """Start pyserial-based listener thread for fallback mode"""
    global serial_listener_thread, is_listening, pyserial_connection
    if is_listening:
        return
    is_listening = True
    serial_listener_thread = threading.Thread(
        target=pyserial_listener_loop, args=(serial_port,), daemon=True
    )
    serial_listener_thread.start()
    logger.info("Pyserial listener thread started")


def pyserial_listener_loop(serial_port):
    """Pyserial listener loop - handles serial responses like desktop but with pyserial"""
    global show_data, pyserial_connection, is_listening

    try:
        import serial

        # Open persistent connection for listening
        pyserial_connection = serial.Serial(
            port=serial_port,
            baudrate=int(app_settings.get("speed_baud", 9600)),
            bytesize=int(app_settings.get("data_bits", 8)),
            stopbits=int(app_settings.get("stop_bits", 1)),
            parity=app_settings.get("parity", "N")[0].upper(),
            timeout=0.1,  # Short timeout for polling
        )

        logger.info("Pyserial listener loop started - polling for responses")

        while is_listening:
            try:
                if pyserial_connection.in_waiting > 0:
                    # Read single byte first to check ACK/NAK
                    first_byte = pyserial_connection.read(1)
                    if len(first_byte) == 1:
                        if first_byte[0] == 0x06:
                            logger.info("Received ACK - waiting for full response...")
                            show_data = False
                            # Continue reading for full response
                            time.sleep(0.1)  # Brief pause
                            continue
                        elif first_byte[0] == 0x15:
                            logger.info("Received NACK")
                            continue
                        elif first_byte[0] == 0x02:  # STX - start of actual response
                            logger.info("Received STX - reading full response...")
                            # Read the full message starting with STX
                            response_data = first_byte  # Start with STX

                            # Read length bytes
                            length_bytes = pyserial_connection.read(2)
                            if len(length_bytes) == 2:
                                response_data += length_bytes
                                msg_len = length_bytes[0] * 100 + length_bytes[1]

                                # Read message data
                                remaining = pyserial_connection.read(
                                    msg_len + 2
                                )  # +2 for ETX and LRC
                                response_data += remaining

                                logger.info(
                                    f"Received full response: {binascii.hexlify(response_data).decode()}"
                                )

                                # Store raw response
                                raw_response_hex = (
                                    binascii.hexlify(response_data).decode().upper()
                                )

                                # Update transaction history
                                processing_trxs = [
                                    k
                                    for k, v in transaction_history.items()
                                    if v["status"] == "processing"
                                ]

                                if processing_trxs:
                                    latest_trx = max(
                                        processing_trxs,
                                        key=lambda k: transaction_history[k][
                                            "timestamp"
                                        ],
                                    )

                                    transaction_history[latest_trx][
                                        "status"
                                    ] = "completed"
                                    transaction_history[latest_trx][
                                        "raw_response"
                                    ] = raw_response_hex
                                    save_transaction_history()
                                    logger.info(
                                        f"Updated transaction {latest_trx} with raw response"
                                    )
                                else:
                                    logger.warning(
                                        "Received response but no processing transaction"
                                    )
                else:
                    time.sleep(0.1)  # No data, brief sleep

            except Exception as e:
                logger.error(f"Pyserial listener error: {str(e)}")
                break

    except Exception as e:
        logger.error(f"Failed to start pyserial listener: {str(e)}")
    finally:
        if pyserial_connection:
            try:
                pyserial_connection.close()
                pyserial_connection = None
            except:
                pass
        logger.info("Pyserial listener loop ended")


def stop_pyserial_listener():
    """Stop pyserial listener thread"""
    global is_listening, pyserial_connection
    is_listening = False
    if pyserial_connection:
        try:
            pyserial_connection.close()
            pyserial_connection = None
        except:
            pass
    if serial_listener_thread:
        serial_listener_thread.join(timeout=2)
    logger.info("Pyserial listener thread stopped")


@ecr_bp.route("/settings", methods=["GET", "POST"])
def handle_settings():
    global app_settings
    if request.method == "GET":
        return jsonify(app_settings)
    data = request.get_json()
    if data:
        app_settings.update(data)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(app_settings, f, indent=2)
        return jsonify({"status": "success"})
    return jsonify({"error": "No data"}), 400


@ecr_bp.route("/connection_status", methods=["GET"])
def get_connection_status():
    global is_connected
    network_available = check_network_connectivity()
    return jsonify(
        {
            "connected": is_connected,
            "network_available": network_available,
            "auto_disconnect_on_offline": True,
        }
    )


@ecr_bp.route("/connect", methods=["POST"])
def handle_connection():
    global is_connected
    data = request.get_json()
    action = data.get("action", "connect")

    # Check network connectivity before attempting to connect
    if action == "connect" and not check_network_connectivity():
        return jsonify({"error": "Cannot connect: Network is offline"}), 400

    if action == "disconnect":
        # Get current connection details for disconnect message
        disconnect_message = "Disconnected"
        if app_settings.get("communication", "Socket") == "Socket":
            ip = app_settings.get("socket_ip", "127.0.0.1")
            port = app_settings.get("socket_port", "9001")
            disconnect_message = f"Disconnected from {ip}:{port}"
        else:
            # Stop both types of listeners and close port
            stop_serial_listener()
            stop_pyserial_listener()
            close_serial_port()
            global use_pyserial_listener
            use_pyserial_listener = False
            serial_port = app_settings.get("serial_port", "")
            disconnect_message = (
                f"Disconnected from {serial_port}"
                if serial_port
                else "Disconnected from serial port"
            )
        is_connected = False
        return jsonify({"connected": False, "message": disconnect_message})
    try:
        if app_settings.get("communication", "Socket") == "Socket":
            # Socket communication - check if REST API mode is enabled
            if app_settings.get("enable_rest_api", False):
                # REST API mode - test HTTP connection to ECR adapter
                ip = app_settings.get("socket_ip", "127.0.0.1")
                port = app_settings.get("socket_port", "9001")
                ssl = app_settings.get("enable_ssl", False)
                protocol = "https" if ssl else "http"
                base_url = f"{protocol}://{ip}:{port}"
                # Test connection with a simple request
                username = "VfiF4CIMB"
                serial_number = app_settings.get("edc_serial_number", "V1E1012320")
                password = "VFI" + serial_number
                headers = {"Content-Type": "application/json"}
                test_data = {
                    "transType": "09",  # TEST HOST
                    "transAmount": "0",
                    "invoiceNo": "",
                    "cardNumber": "",
                }
                response = requests.post(
                    f"{base_url}/transaction/cimb",
                    json=test_data,
                    auth=(username, password),
                    headers=headers,
                    verify=False,
                    timeout=5,
                )
                if response.status_code == 200:
                    is_connected = True
                    return jsonify(
                        {
                            "connected": True,
                            "message": f"Successfully connected to {ip}:{port}",
                        }
                    )
                else:
                    is_connected = False
                    return (
                        jsonify(
                            {
                                "error": f"REST API connection failed: {response.status_code} {response.text}"
                            }
                        ),
                        400,
                    )
            else:
                # Native socket mode - test socket connection
                ip = app_settings.get("socket_ip", "127.0.0.1")
                port = int(app_settings.get("socket_port", 9001))
                test_sock = socket.socket()
                test_sock.settimeout(5)
                test_sock.connect((ip, port))
                test_sock.close()
                is_connected = True
                return jsonify(
                    {
                        "connected": True,
                        "message": f"Successfully connected to {ip}:{port}",
                    }
                )
        else:
            # Serial communication - test actual serial port (binary protocol like Java)
            serial_port = app_settings.get("serial_port", "")
            if not serial_port:
                raise ValueError("No serial port specified")

            # Try native library first, then fallback to pyserial
            if ecr_lib and open_serial_port():
                # Native library worked, start listener thread
                start_serial_listener()
                is_connected = True
                return jsonify(
                    {
                        "connected": True,
                        "message": f"Successfully connected to {serial_port}",
                    }
                )
            else:
                # Fallback to pyserial for connection test
                logger.info("Native library failed, testing with pyserial fallback")
                global use_pyserial_listener, pyserial_connection
                import serial

                test_serial = serial.Serial(
                    port=serial_port,
                    baudrate=int(app_settings.get("speed_baud", 9600)),
                    bytesize=int(app_settings.get("data_bits", 8)),
                    stopbits=int(app_settings.get("stop_bits", 1)),
                    parity=app_settings.get("parity", "N")[0].upper(),
                    timeout=1,
                )
                test_serial.close()  # Just test connection, close immediately

                # Set up pyserial listener mode
                use_pyserial_listener = True
                start_pyserial_listener(serial_port)
                is_connected = True
                return jsonify(
                    {
                        "connected": True,
                        "message": f"Successfully connected to {serial_port}",
                    }
                )
    except Exception as e:
        is_connected = False
        if app_settings.get("communication", "Socket") == "Socket":
            ip = app_settings.get("socket_ip", "127.0.0.1")
            port = int(app_settings.get("socket_port", 9001))
            if app_settings.get("enable_rest_api", False):
                return jsonify({"error": f"REST API connection failed: {str(e)}"}), 400
            else:
                return (
                    jsonify({"error": f"Failed to connect to {ip}:{port} - {str(e)}"}),
                    400,
                )
        else:
            serial_port = app_settings.get("serial_port", "")
            return (
                jsonify({"error": f"Failed to connect to {serial_port} - {str(e)}"}),
                400,
            )


@ecr_bp.route("/build_request", methods=["POST"])
def build_request():
    data = request.get_json()
    transaction_type = data.get("transaction_type", "SALE")
    amount = data.get("amount", "0.00")
    invoice_no = data.get("invoiceNo", "")
    card_no = data.get("cardNo", "")
    trans_type_map = {
        "SALE": "01",
        "INSTALLMENT": "02",
        "VOID": "03",
        "REFUND": "04",
        "QRIS MPM": "05",
        "QRIS NOTIFICATION": "06",
        "QRIS REFUND": "07",
        "POINT REWARD": "08",
        "TEST HOST": "09",
        "QRIS CPM": "0A",
        "SETTLEMENT": "0B",
        "REPRINT": "0C",
        "REPORT": "0D",
        "LOGON": "0E",
    }
    trans_code = trans_type_map.get(transaction_type.upper(), "01")
    try:
        packed = pack_request_msg(trans_code, amount, invoice_no, card_no)

        # Create human-readable request format
        human_readable_request = f"Transaction Type: {transaction_type}"

        # Only show amount for transactions that need it
        if transaction_type.upper() not in [
            "VOID",
            "QRIS NOTIFICATION",
            "POINT REWARD",
            "TEST HOST",
            "SETTLEMENT",
            "REPRINT",
            "REPORT",
            "LOGON",
        ]:
            # Format amount with proper display
            try:
                amount_float = float(amount.replace(",", ""))
                if amount_float > 0:
                    human_readable_request += f"\nAmount: {amount_float:,.0f}"
                else:
                    human_readable_request += f"\nAmount: 0"
            except (ValueError, TypeError):
                human_readable_request += f"\nAmount: {amount}"

        # Add invoice/trace number/reference ID if provided
        if invoice_no and invoice_no.strip():
            if transaction_type.upper() == "VOID":
                human_readable_request += f"\nTrace Number: {invoice_no.strip()}"
            elif transaction_type.upper() == "QRIS NOTIFICATION":
                human_readable_request += f"\nReference ID: {invoice_no.strip()}"
            else:
                human_readable_request += f"\nInvoice Number: {invoice_no.strip()}"

        # Add card number if provided
        if card_no and card_no.strip():
            human_readable_request += f"\nCard Number: {card_no.strip()}"

        return jsonify({"request": human_readable_request, "type": "human"})
    except ValueError as e:
        logger.error(f"Build request error: {str(e)}")
        return jsonify({"error": str(e)}), 400


@ecr_bp.route("/process", methods=["POST"])
def process_transaction():
    global is_connected
    if not is_connected:
        return jsonify({"error": "Not connected"}), 400

    # Check network connectivity for socket connections
    if (
        app_settings.get("communication", "Socket") == "Socket"
        and not check_network_connectivity()
    ):
        # Auto-disconnect due to network loss
        is_connected = False
        return (
            jsonify({"error": "Network connection lost - automatically disconnected"}),
            400,
        )
    data = request.get_json()
    transaction_type = data.get("transaction_type", "SALE")
    amount = data.get("amount", "0.00")
    invoice_no = data.get("invoiceNo", "")
    card_no = data.get("cardNo", "")
    trans_type_map = {
        "SALE": "01",
        "INSTALLMENT": "02",
        "VOID": "03",
        "REFUND": "04",
        "QRIS MPM": "05",
        "QRIS NOTIFICATION": "06",
        "QRIS REFUND": "07",
        "POINT REWARD": "08",
        "TEST HOST": "09",
        "QRIS CPM": "0A",
        "SETTLEMENT": "0B",
        "REPRINT": "0C",
        "REPORT": "0D",
        "LOGON": "0E",
    }
    trans_code = trans_type_map.get(transaction_type.upper(), "01")
    trx_id = uuid.uuid4().hex[:8].upper()
    transaction_history[trx_id] = {
        "status": "processing",
        "request": {
            "transType": transaction_type,
            "transCode": trans_code,
            "amount": amount,
            "invoiceNo": invoice_no,
            "cardNo": card_no,
        },
        "timestamp": time.time(),
    }
    save_transaction_history()
    try:
        if app_settings.get("communication", "Serial") == "Serial":
            packed_message = pack_request_msg(trans_code, amount, invoice_no, card_no)

            # Try native library approach first
            if ecr_lib and is_listening and not use_pyserial_listener:
                try:
                    # Send using native library only, exactly like desktop Serial.send()
                    send_serial_message_native_only(packed_message)

                    # Transaction sent successfully, response will be handled by background listener
                    transaction_history[trx_id]["status"] = "processing"
                    transaction_history[trx_id]["note"] = "Waiting for EDC response"
                    save_transaction_history()

                    return jsonify(
                        {
                            "status": "processing",
                            "trxId": trx_id,
                            "message": "Waiting for EDC response",
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Native library failed: {e}. Using pyserial listener."
                    )

            # Use pyserial listener approach
            if use_pyserial_listener and pyserial_connection:
                try:
                    logger.info("Sending transaction via pyserial listener")
                    pyserial_connection.write(packed_message)
                    pyserial_connection.flush()

                    # Transaction sent successfully, response will be handled by background listener
                    transaction_history[trx_id]["status"] = "processing"
                    transaction_history[trx_id]["note"] = "Waiting for EDC response"
                    save_transaction_history()

                    return jsonify(
                        {
                            "status": "processing",
                            "trxId": trx_id,
                            "message": "Waiting for EDC response",
                        }
                    )
                except Exception as e:
                    logger.error(f"Pyserial listener send failed: {e}")
                    transaction_history[trx_id]["status"] = "error"
                    transaction_history[trx_id]["error"] = str(e)
                    save_transaction_history()
                    return jsonify({"error": str(e), "trxId": trx_id}), 500

            # If we get here, neither listener is working - return error
            transaction_history[trx_id]["status"] = "error"
            transaction_history[trx_id]["error"] = "No active serial listener available"
            save_transaction_history()
            return (
                jsonify(
                    {"error": "No active serial listener available", "trxId": trx_id}
                ),
                500,
            )
        else:
            # Use REST API over socket
            ip = app_settings.get("socket_ip", "127.0.0.1")
            port = app_settings.get("socket_port", "9001")
            ssl = app_settings.get("enable_ssl", False)
            protocol = "https" if ssl else "http"
            base_url = f"{protocol}://{ip}:{port}"
            username = "VfiF4CIMB"
            serial_number = app_settings.get("edc_serial_number", "V1E1012320")
            if not serial_number:
                raise ValueError("EDC serial number not configured in settings")
            password = "VFI" + serial_number
            # Preserve the original amount value without any conversion
            amount_str = str(amount).replace(",", "")
            logger.info(f"Using REST API auth: {username}:{password}")
            logger.info(f"Connecting to ECR adaptor at: {base_url}")
            req_json = {
                "transType": trans_code,
                "transAmount": amount_str,
                "invoiceNo": invoice_no,
                "cardNumber": card_no,
            }
            # Send transaction request to ECR adapter
            headers = {"Content-Type": "application/json"}
            logger.info(f"Sending transaction request to: {base_url}/transaction/cimb")
            logger.info(f"Request data: {req_json}")
            # Map the request to match ECR adaptor expectations
            ecr_request = {
                "transType": req_json["transType"],
                "transAmount": req_json["transAmount"],
                "invoiceNo": req_json.get("invoiceNo", ""),
                "cardNumber": req_json.get("cardNumber", ""),
            }
            r = requests.post(
                f"{base_url}/transaction/cimb",
                json=ecr_request,
                auth=(username, password),
                headers=headers,
                verify=False,
                timeout=10,
            )
            logger.info(f"Transaction response: {r.status_code} - {r.text}")
            if r.status_code == 401:
                raise ValueError(
                    f"Authentication failed. Check EDC serial number in settings. Expected auth: {username}:{password}"
                )
            elif r.status_code != 200:
                raise ValueError(f"Transaction failed: {r.status_code} {r.text}")
            resp = r.json()
            trx_id_terminal = resp.get("trxId")
            if not trx_id_terminal:
                raise ValueError("No transaction ID received from ECR adapter")
            logger.info(f"Transaction initiated with ID: {trx_id_terminal}")
            # Poll for results
            start_time = time.time()
            poll_count = 0
            max_polls = 60  # 60 seconds max
            while time.time() - start_time < max_polls:
                poll_count += 1
                time.sleep(1)
                logger.info(f"Polling for results (attempt {poll_count})...")
                try:
                    r = requests.post(
                        f"{base_url}/result/cimb",
                        json={"trxId": trx_id_terminal},
                        auth=(username, password),
                        headers=headers,
                        verify=False,
                        timeout=5,
                    )
                    logger.info(f"Poll response: {r.status_code} - {r.text}")
                    if r.status_code == 503:
                        logger.info(
                            "Transaction still processing, continuing to poll..."
                        )
                        continue
                    elif r.status_code == 200:
                        response_dict = r.json()
                        local_timestamp = time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime(transaction_history[trx_id]["timestamp"]),
                        )
                        parsed_timestamp = parse_response_datetime(response_dict)
                        timestamp = (
                            parsed_timestamp if parsed_timestamp else local_timestamp
                        )
                        # Check if the transaction actually succeeded by looking at response code
                        transaction_failed = False
                        failure_reason = ""
                        # Check response code in the transaction data
                        if "responseCode" in response_dict:
                            resp_code = response_dict["responseCode"]
                            if resp_code == "ER":
                                transaction_failed = True
                                failure_reason = response_dict.get(
                                    "qrCode", "Transaction failed"
                                )
                            elif resp_code not in [
                                "00",
                                "Z1",
                            ]:  # 00 and Z1 are success codes
                                transaction_failed = True
                                failure_reason = f"Response code: {resp_code}"
                        # Set status based on actual transaction result
                        if transaction_failed:
                            transaction_history[trx_id]["status"] = "failed"
                            transaction_history[trx_id]["error"] = failure_reason
                            transaction_history[trx_id]["response"] = response_dict
                            save_transaction_history()
                            logger.info(f"Transaction failed: {failure_reason}")
                            return jsonify(
                                {
                                    "status": "failed",
                                    "trxId": trx_id,
                                    "response": response_dict,
                                    "error": failure_reason,
                                    "timestamp": timestamp,
                                }
                            )
                        else:
                            transaction_history[trx_id]["status"] = "completed"
                            transaction_history[trx_id]["response"] = response_dict
                            save_transaction_history()
                            logger.info(
                                f"Transaction completed successfully: {response_dict}"
                            )
                            return jsonify(
                                {
                                    "status": "success",
                                    "trxId": trx_id,
                                    "response": response_dict,
                                    "timestamp": timestamp,
                                }
                            )
                        transaction_history[trx_id]["response"] = response_dict
                    else:
                        logger.error(
                            f"Unexpected poll response: {r.status_code} {r.text}"
                        )
                        break
                except requests.exceptions.RequestException as e:
                    logger.error(f"Poll request failed: {str(e)}")
                    continue
            raise ValueError(f"Polling timeout")

        # Check if the transaction actually succeeded by looking at response code
        transaction_failed = False
        failure_reason = ""

        if "responseCode" in response_dict:
            resp_code = response_dict["responseCode"]
            if resp_code == "ER":
                transaction_failed = True
                failure_reason = response_dict.get("qrCode", "Transaction failed")
            elif resp_code not in ["00", "Z1"]:  # 00 and Z1 are success codes
                transaction_failed = True
                failure_reason = f"Response code: {resp_code}"

        local_timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(transaction_history[trx_id]["timestamp"]),
        )
        parsed_timestamp = parse_response_datetime(response_dict)
        timestamp = parsed_timestamp if parsed_timestamp else local_timestamp

        if transaction_failed:
            transaction_history[trx_id]["status"] = "failed"
            transaction_history[trx_id]["error"] = failure_reason
            transaction_history[trx_id]["response"] = response_dict
            save_transaction_history()
            logger.info(f"Transaction failed: {failure_reason}")
            return jsonify(
                {
                    "status": "failed",
                    "trxId": trx_id,
                    "response": response_dict,
                    "error": failure_reason,
                    "timestamp": timestamp,
                }
            )
        else:
            transaction_history[trx_id]["status"] = "completed"
            transaction_history[trx_id]["response"] = response_dict
            save_transaction_history()
            return jsonify(
                {
                    "status": "success",
                    "trxId": trx_id,
                    "response": response_dict,
                    "timestamp": timestamp,
                }
            )
    except Exception as e:
        transaction_history[trx_id]["status"] = "error"
        transaction_history[trx_id]["error"] = str(e)
        save_transaction_history()
        local_timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(transaction_history[trx_id]["timestamp"]),
        )
        return (
            jsonify(
                {
                    "error": str(e),
                    "trxId": trx_id,
                    "timestamp": local_timestamp,
                }
            ),
            500,
        )


@ecr_bp.route("/detect_serial", methods=["POST"])
def detect_serial():
    """Try to detect the correct EDC serial number by testing common ones"""
    if not app_settings.get("enable_rest_api", False):
        return jsonify({"error": "REST API mode not enabled"}), 400
    ip = app_settings.get("socket_ip", "127.0.0.1")
    port = app_settings.get("socket_port", "9001")
    ssl = app_settings.get("enable_ssl", False)
    protocol = "https" if ssl else "http"
    base_url = f"{protocol}://{ip}:{port}"
    # Common serial numbers to try
    common_serials = [
        "V1E0212639",  # From BRI collection
        "V1E1012320",  # User provided
        "V1E0000001",  # Common test serial
        "V1E0000000",  # Another test serial
    ]
    username = "VfiF4CIMB"
    headers = {"Content-Type": "application/json"}
    test_data = {
        "transType": "09",  # TEST HOST
        "transAmount": "0",
        "invoiceNo": "",
        "cardNumber": "",
    }
    results = []
    for serial in common_serials:
        password = "VFI" + serial
        logger.info(f"Testing serial: {serial} with auth: {username}:{password}")
        try:
            response = requests.post(
                f"{base_url}/transaction/cimb",
                json=test_data,
                auth=(username, password),
                headers=headers,
                verify=False,
                timeout=5,
            )
            result = {
                "serial": serial,
                "auth": f"{username}:{password}",
                "status_code": response.status_code,
                "response": response.text,
            }
            if response.status_code == 200:
                result["success"] = True
                logger.info(f"SUCCESS: Found working serial: {serial}")
                # Update settings with working serial
                app_settings["edc_serial_number"] = serial
                with open(SETTINGS_FILE, "w") as f:
                    json.dump(app_settings, f, indent=2)
                results.append(result)
                return jsonify(
                    {
                        "status": "success",
                        "working_serial": serial,
                        "all_results": results,
                    }
                )
            else:
                result["success"] = False
                logger.info(f"Failed serial: {serial} - {response.status_code}")
            results.append(result)
        except Exception as e:
            results.append(
                {
                    "serial": serial,
                    "auth": f"{username}:{password}",
                    "error": str(e),
                    "success": False,
                }
            )
            logger.error(f"Error testing serial {serial}: {str(e)}")
    return jsonify(
        {
            "status": "failed",
            "message": "No working serial number found",
            "results": results,
        }
    )


def get_transaction_name_from_code(trans_code):
    """Convert transaction code to human-readable name"""
    code_to_name_map = {
        "01": "SALE",
        "02": "INSTALLMENT",
        "03": "VOID",
        "04": "REFUND",
        "05": "QRIS MPM",
        "06": "QRIS NOTIFICATION",
        "07": "QRIS REFUND",
        "08": "POINT REWARD",
        "09": "TEST HOST",
        "0A": "QRIS CPM",
        "0B": "SETTLEMENT",
        "0C": "REPRINT",
        "0D": "REPORT",
        "0E": "LOGON",
    }
    return code_to_name_map.get(trans_code, trans_code)


def parse_response_datetime(response_data):
    """Parse date and time from response data and return formatted timestamp"""
    try:
        if not response_data or not isinstance(response_data, dict):
            return None
        date_str = response_data.get("date", "").strip()
        time_str = response_data.get("time", "").strip()
        if not date_str or not time_str or len(date_str) != 8 or len(time_str) > 6:
            return None
        # Parse date: YYYYMMDD
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])
        # Parse time: HHMMSS (pad with zeros if needed)
        time_str = time_str.zfill(6)  # Ensure 6 digits
        hour = int(time_str[:2])
        minute = int(time_str[2:4])
        second = int(time_str[4:6])
        # Create datetime object and format it
        from datetime import datetime

        dt = datetime(year, month, day, hour, minute, second)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


@ecr_bp.route("/transaction_status/<trx_id>", methods=["GET"])
def get_transaction_status(trx_id):
    """Check transaction status - for asynchronous SerialListener responses"""
    if trx_id not in transaction_history:
        return jsonify({"error": "Transaction not found"}), 404

    transaction = transaction_history[trx_id]
    status_info = {
        "trxId": trx_id,
        "status": transaction["status"],
        "timestamp": time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(transaction["timestamp"])
        ),
    }

    if "response" in transaction:
        status_info["response"] = transaction["response"]
        # Parse timestamp from response if available
        parsed_timestamp = parse_response_datetime(transaction["response"])
        if parsed_timestamp:
            status_info["timestamp"] = parsed_timestamp

    if "raw_response" in transaction:
        status_info["raw_response"] = transaction["raw_response"]

    if "error" in transaction:
        status_info["error"] = transaction["error"]

    if "note" in transaction:
        status_info["note"] = transaction["note"]

    return jsonify(status_info)


@ecr_bp.route("/history", methods=["GET"])
def get_history():
    history_list = []
    for trx_id, data in transaction_history.items():
        # Skip transactions that are hidden from UI
        if trx_id in ui_hidden_transactions:
            continue
        trans_type = data["request"].get("transType", "")
        if trans_type in [
            "01",
            "02",
            "03",
            "04",
            "05",
            "06",
            "07",
            "08",
            "09",
            "0A",
            "0B",
            "0C",
            "0D",
            "0E",
        ]:
            trans_type = get_transaction_name_from_code(trans_type)
        # Get invoice number from response first, then fall back to request
        invoice_no = ""
        if "response" in data and data["response"].get("invoiceNo"):
            invoice_no = data["response"]["invoiceNo"]
        elif data["request"].get("invoiceNo"):
            invoice_no = data["request"]["invoiceNo"]
        # Use response datetime if available, otherwise fall back to original timestamp
        display_timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(data["timestamp"])
        )
        if "response" in data:
            parsed_datetime = parse_response_datetime(data["response"])
            if parsed_datetime:
                display_timestamp = parsed_datetime
        history_item = {
            "id": trx_id,
            "transaction_id": trx_id,
            "timestamp": display_timestamp,
            "transaction_type": trans_type,
            "amount": data["request"].get("amount", ""),
            "status": data["status"],
            "invoice_no": invoice_no,
        }
        if "response" in data:
            history_item["response"] = data["response"]
            # Include QR code if available in response
            if data["response"].get("qrCode"):
                history_item["qr_code"] = data["response"]["qrCode"]
        if "error" in data:
            history_item["error"] = data["error"]
        history_list.append(history_item)
    history_list.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify(history_list)


@ecr_bp.route("/history", methods=["DELETE"])
def clear_history():
    """Clear transaction history from UI display only (preserves backend data)"""
    global ui_hidden_transactions
    # Add all current transaction IDs to the hidden set
    ui_hidden_transactions.update(transaction_history.keys())
    logger.info(
        f"Transaction history cleared from UI ({len(transaction_history)} transactions hidden)"
    )
    return jsonify(
        {"status": "success", "message": "Transaction history cleared from display"}
    )


@ecr_bp.route("/download_log", methods=["GET"])
def download_log():
    """Download the ECR simulator log file"""
    from datetime import datetime

    # Check password parameter
    password = request.args.get("password", "")
    # Generate today's expected password (ddmmyyyy format)
    today = datetime.now()
    expected_password = today.strftime("%d%m%Y")
    if password != expected_password:
        return (
            jsonify(
                {
                    "error": "Invalid password. Please use today's date in ddmmyyyy format."
                }
            ),
            401,
        )
    # Use the same log file path as configured for logging
    log_file_path = LOG_FILE_PATH
    # Create log file if it doesn't exist
    if not os.path.exists(log_file_path):
        try:
            # Create an empty log file
            with open(log_file_path, "w") as f:
                f.write(
                    f"ECR Simulator Log - Created {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
            logger.info(f"Created new log file at: {log_file_path}")
        except Exception as e:
            logger.error(f"Failed to create log file: {e}")
            return jsonify({"error": f"Could not create log file: {str(e)}"}), 500
    return send_file(
        log_file_path,
        as_attachment=True,
        download_name="ecr_simulator.log",
        mimetype="text/plain",
    )


@ecr_bp.route("/download_history", methods=["GET"])
def download_history():
    """Download the transaction history JSON file"""
    from datetime import datetime

    # Check password parameter
    password = request.args.get("password", "")
    # Generate today's expected password (ddmmyyyy format)
    today = datetime.now()
    expected_password = today.strftime("%d%m%Y")
    if password != expected_password:
        return (
            jsonify(
                {
                    "error": "Invalid password. Please use today's date in ddmmyyyy format."
                }
            ),
            401,
        )
    # Use the transaction history file path
    history_file_path = HISTORY_FILE
    # Create history file if it doesn't exist
    if not os.path.exists(history_file_path):
        try:
            # Create an empty history file
            with open(history_file_path, "w") as f:
                json.dump({}, f, indent=2)
            logger.info(f"Created new history file at: {history_file_path}")
        except Exception as e:
            logger.error(f"Failed to create history file: {e}")
            return jsonify({"error": f"Could not create history file: {str(e)}"}), 500
    return send_file(
        history_file_path,
        as_attachment=True,
        download_name="transaction_history.json",
        mimetype="application/json",
    )
