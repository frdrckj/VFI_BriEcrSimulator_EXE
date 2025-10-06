"""
ECR Core Logic Module
Handles message packing/parsing, transaction management, and ECR library interface
"""

import ctypes
import binascii
import logging
import os
import platform
import struct
import socket
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class SerialData(ctypes.Structure):
    """Serial port configuration structure matching spec appendices"""

    _fields_ = [
        ("szComm", ctypes.c_char * 10),  # Serial port number
        ("chBaudRate", ctypes.c_ubyte),  # Baudrate code (e.g., 3 for 9600)
        ("chDataBit", ctypes.c_ubyte),  # Data bits (e.g., 8)
        ("chStopBit", ctypes.c_ubyte),  # Stop bits (0 for 1)
        ("chParity", ctypes.c_ubyte),  # Parity (0 for none)
    ]


class ReqData(ctypes.Structure):
    """Request data structure matching BRI FMS v3.3 spec - 200 bytes total"""

    _fields_ = [
        ("chTransType", ctypes.c_ubyte),         # 1 byte - Transaction type
        ("szAmount", ctypes.c_char * 12),        # 12 bytes - Transaction Amount
        ("szAddAmount", ctypes.c_char * 12),     # 12 bytes - Transaction Tip / Non Fare Amount
        ("szInvNo", ctypes.c_char * 12),         # 12 bytes - Invoice No / Reff No
        ("szCardNo", ctypes.c_char * 19),        # 19 bytes - Brizzi Card Number
        ("szFiller", ctypes.c_char * 144),       # 144 bytes - For bank use
    ]


class RspData(ctypes.Structure):
    """Response data structure matching BRI FMS v3.3 spec - 300 bytes total"""

    _fields_ = [
        ("chTransType", ctypes.c_ubyte),             # 1 byte - Transaction type
        ("szTID", ctypes.c_char * 8),                # 8 bytes - Terminal ID
        ("szMID", ctypes.c_char * 15),               # 15 bytes - Merchant ID
        ("szBatchNumber", ctypes.c_char * 6),        # 6 bytes - Batch Number
        ("szIssuerName", ctypes.c_char * 25),        # 25 bytes - Issuer Name (Credit Card only)
        ("szTraceNo", ctypes.c_char * 6),            # 6 bytes - Trace No
        ("szInvoiceNo", ctypes.c_char * 6),          # 6 bytes - Invoice No
        ("chEntryMode", ctypes.c_ubyte),             # 1 byte - Entry Mode
        ("szTransAmount", ctypes.c_char * 12),       # 12 bytes - Trans Amount (last 2 digits decimal)
        ("szTotalAmount", ctypes.c_char * 12),       # 12 bytes - Total Amount (last 2 digits decimal)
        ("szCardNo", ctypes.c_char * 19),            # 19 bytes - Card No (masked)
        ("szCardholderName", ctypes.c_char * 26),    # 26 bytes - Cardholder Name
        ("szDate", ctypes.c_char * 8),               # 8 bytes - Date (YYYYMMDD)
        ("szTime", ctypes.c_char * 6),               # 6 bytes - Time (HHMMSS)
        ("szApprovalCode", ctypes.c_char * 8),       # 8 bytes - Approval Code
        ("szResponseCode", ctypes.c_char * 2),       # 2 bytes - Response Code
        ("szRefNumber", ctypes.c_char * 12),         # 12 bytes - Ref Number
        ("szBalancePrepaid", ctypes.c_char * 12),    # 12 bytes - Balance (Prepaid) last 2 digits decimal
        ("szTopupCardNo", ctypes.c_char * 19),       # 19 bytes - Top-up Card Number (masked)
        ("szTransAddAmount", ctypes.c_char * 12),    # 12 bytes - Trans Add Amount (last 2 digits decimal)
        ("szFiller", ctypes.c_char * 84),            # 84 bytes - For Bank Use
    ]


class EcrCore:
    """Core ECR functionality - library management and message processing"""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.ecr_lib = None
        self.use_library = True
        self._init_library()

    def _init_library(self):
        """Initialize the native ECR library"""
        # Allow disabling native library via environment variable
        if os.environ.get("DISABLE_NATIVE_LIBRARY", "").lower() == "true":
            self.use_library = False
            logger.info("Native library disabled via environment variable")
            return

        lib_name = (
            "BriEcrLibrary.dll"
            if platform.system() == "Windows"
            else "libBriEcrLibrary.so"
        )

        try:
            # Try multiple paths for library loading
            search_paths = [
                os.path.join(self.base_dir, lib_name),
                os.path.join(os.path.dirname(self.base_dir), lib_name),
                lib_name,  # Try system PATH
            ]

            lib_path = None
            for path in search_paths:
                if os.path.exists(path):
                    lib_path = path
                    break

            if lib_path:
                self.ecr_lib = ctypes.CDLL(lib_path)
                logger.info(f"Loaded {lib_name} successfully from {lib_path}")
                self._setup_library_functions()

                # Test version call
                version_buf = ctypes.create_string_buffer(20)
                self.ecr_lib.ecrGetVersion(version_buf)
                logger.info(f"Library version: {version_buf.value.decode('ascii')}")
            else:
                raise FileNotFoundError(f"Could not find {lib_name}")

        except Exception as e:
            logger.error(
                f"Failed to load {lib_name}: {e}. Falling back to native Python."
            )
            self.ecr_lib = None

    def _setup_library_functions(self):
        """Set up function signatures for the native library"""
        if not self.ecr_lib:
            return

        # Version functions
        self.ecr_lib.ecrGetVersion.argtypes = [ctypes.c_char_p]
        self.ecr_lib.ecrGetVersion.restype = None

        # Socket functions (matching desktop version)
        self.ecr_lib.ecrOpenSocket.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
        self.ecr_lib.ecrOpenSocket.restype = ctypes.c_int

        self.ecr_lib.ecrSendSocket.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.ecr_lib.ecrSendSocket.restype = ctypes.c_int

        self.ecr_lib.ecrRecvSocket.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.ecr_lib.ecrRecvSocket.restype = ctypes.c_int

        self.ecr_lib.ecrCloseSocket.argtypes = []
        self.ecr_lib.ecrCloseSocket.restype = None

        # Serial port functions
        self.ecr_lib.ecrOpenSerialPort.argtypes = [ctypes.POINTER(SerialData)]
        self.ecr_lib.ecrOpenSerialPort.restype = ctypes.c_int

        self.ecr_lib.ecrSendSerialPort.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self.ecr_lib.ecrSendSerialPort.restype = ctypes.c_int

        self.ecr_lib.ecrRecvSerialPort.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self.ecr_lib.ecrRecvSerialPort.restype = ctypes.c_int

        self.ecr_lib.ecrCloseSerialPort.argtypes = []
        self.ecr_lib.ecrCloseSerialPort.restype = None

        # Message processing functions
        self.ecr_lib.ecrPackRequest.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ReqData),
        ]
        self.ecr_lib.ecrPackRequest.restype = ctypes.c_int

        self.ecr_lib.ecrParseResponse.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(RspData),
        ]
        self.ecr_lib.ecrParseResponse.restype = ctypes.c_int

    def calculate_lrc(self, data: bytes) -> int:
        """Calculate LRC (Longitudinal Redundancy Check)"""
        lrc = 0
        for byte in data:
            lrc ^= byte
        logger.debug(f"LRC calculated: {lrc:02X}")
        return lrc

    def format_amount(self, amount_str: str) -> str:
        """Format amount string by dividing by 100 and removing leading zeros"""
        try:
            if not amount_str or not amount_str.strip():
                return ""
            amount_int = int(amount_str)
            # Divide by 100 to reverse the multiplication done during sending
            formatted_amount = amount_int / 100
            if formatted_amount == int(formatted_amount):
                return str(int(formatted_amount))
            else:
                return f"{formatted_amount:.2f}"
        except (ValueError, TypeError):
            return amount_str

    def format_date(self, date_str: str) -> str:
        """Format date from YYYYMMDD to YYYY-MM-DD"""
        try:
            if not date_str or len(date_str) != 8:
                return date_str
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            return f"{year}-{month}-{day}"
        except:
            return date_str

    def format_time(self, time_str: str) -> str:
        """Format time from HHMMSS to HH:MM"""
        try:
            if not time_str or len(time_str) != 6:
                return time_str
            hour = time_str[:2]
            minute = time_str[2:4]
            # Skip seconds
            return f"{hour}:{minute}"
        except:
            return time_str

    # Socket communication methods (matching desktop version)
    def open_socket(self, ip: str, port: int, ssl: bool = False) -> bool:
        """Open socket connection - matching desktop BriEcrLibrary.openSocket"""
        if self.ecr_lib and self.use_library:
            try:
                ip_bytes = ip.encode('ascii')
                ssl_flag = 1 if ssl else 0
                ret = self.ecr_lib.ecrOpenSocket(ip_bytes, port, ssl_flag)
                if ret != 0:
                    logger.error(f"Failed to open socket: {ret}")
                    return False
                logger.info(f"Socket opened via native library: {ip}:{port}, SSL={ssl}")
                return True
            except Exception as e:
                logger.error(f"Socket open error: {e}")
                return False
        else:
            # Fallback: Pure Python socket implementation
            logger.info("Using pure Python socket implementation (library not available)")
            try:
                import socket as sock
                self.python_socket = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
                self.python_socket.settimeout(60)
                self.python_socket.connect((ip, port))
                logger.info(f"Socket opened via Python: {ip}:{port}")
                return True
            except Exception as e:
                logger.error(f"Python socket open error: {e}")
                return False

    def send_socket(self, data: bytes) -> bool:
        """Send data via socket - matching desktop BriEcrLibrary.sendSocket"""
        if self.ecr_lib and self.use_library:
            try:
                ret = self.ecr_lib.ecrSendSocket(data, len(data))
                if ret != 0:
                    logger.error(f"Failed to send socket data: {ret}")
                    return False
                logger.info(f"Socket data sent via library: {len(data)} bytes")
                return True
            except Exception as e:
                logger.error(f"Socket send error: {e}")
                return False
        else:
            # Fallback: Pure Python socket send
            if hasattr(self, 'python_socket') and self.python_socket:
                try:
                    self.python_socket.sendall(data)
                    logger.info(f"Socket data sent via Python: {len(data)} bytes")
                    logger.debug(f"Sent data (hex): {binascii.hexlify(data).decode()}")
                    return True
                except Exception as e:
                    logger.error(f"Python socket send error: {e}")
                    return False
            else:
                logger.error("No socket connection available")
                return False

    def recv_socket(self, size: int = 9999, timeout: float = 10.0) -> bytes:
        """Receive data from socket - matching desktop BriEcrLibrary.recvSocket

        Args:
            size: Maximum bytes to receive
            timeout: Socket timeout in seconds (default 10s, use lower for flushing)
        """
        if self.ecr_lib and self.use_library:
            try:
                buffer = ctypes.create_string_buffer(size)
                ret = self.ecr_lib.ecrRecvSocket(buffer, size)
                if ret > 0:
                    data = buffer.raw[:ret]
                    logger.info(f"✓ Socket data received via library: {ret} bytes")
                    logger.debug(f"Received hex: {binascii.hexlify(data).decode()}")
                    return data
                elif ret == 0:
                    # No data - this is normal during polling
                    return b""
                elif ret == -3:
                    logger.error("✗ Invalid length received from socket")
                    return b""
                elif ret == -4:
                    logger.error("✗ Invalid LRC received from socket")
                    return b""
                else:
                    logger.error(f"✗ Socket receive error code: {ret}")
                    return b""
            except Exception as e:
                logger.error(f"✗ Socket recv exception: {e}")
                return b""
        else:
            # Fallback: Pure Python socket receive
            if hasattr(self, 'python_socket') and self.python_socket:
                try:
                    # Use configurable timeout (default 10s for normal receive, lower for flushing)
                    self.python_socket.settimeout(timeout)
                    data = self.python_socket.recv(size)
                    if len(data) > 0:
                        logger.info(f"✓ Socket data received via Python: {len(data)} bytes")
                        logger.debug(f"Received data (hex): {binascii.hexlify(data).decode()}")
                    else:
                        logger.debug("No data received (empty response)")
                    return data
                except socket.timeout:
                    # Timeout - no data available yet (this is normal during polling)
                    return b""
                except Exception as e:
                    logger.error(f"✗ Python socket recv error: {e}")
                    return b""
            else:
                logger.debug("No socket available for receiving")
                return b""

    def close_socket(self):
        """Close socket connection - matching desktop BriEcrLibrary.closeSocket"""
        if self.ecr_lib and self.use_library:
            try:
                self.ecr_lib.ecrCloseSocket()
                logger.info("Socket closed via library")
            except Exception as e:
                logger.error(f"Socket close error: {e}")
        else:
            # Fallback: Pure Python socket close
            if hasattr(self, 'python_socket') and self.python_socket:
                try:
                    self.python_socket.close()
                    self.python_socket = None
                    logger.info("Socket closed via Python")
                except Exception as e:
                    logger.error(f"Python socket close error: {e}")

    def pack_request_message(
        self,
        trans_type: str,
        amount: str,
        invoice_no: str,
        card_no: str = "",
        add_amount: str = "0",
        use_serial_multiplier: bool = True,
    ) -> bytes:
        """Pack request message following BRI FMS v3.3 protocol"""
        logger.info(
            f"Packing request: trans_type={trans_type}, amount={amount}, "
            f"add_amount={add_amount}, invoice_no={invoice_no}, card_no={card_no}"
        )

        # Validate and format inputs
        trans_type_int = self._validate_transaction_type(trans_type)
        amount_str = self._format_amount(amount, trans_type, use_serial_multiplier)
        add_amount_str = self._format_amount(add_amount, trans_type, use_serial_multiplier)
        invoice_str = self._format_invoice_number(invoice_no, trans_type)
        card_no_str = self._validate_card_number(card_no)

        # Try native library first
        if self.ecr_lib and self.use_library:
            try:
                return self._pack_with_library(
                    trans_type_int, amount_str, add_amount_str, invoice_str, card_no_str
                )
            except Exception as e:
                logger.error(f"Library pack failed: {e}. Using fallback.")

        # Fallback to manual packing
        return self._pack_manual(trans_type_int, amount_str, add_amount_str, invoice_str, card_no_str)

    def parse_response_message(self, response_bytes: bytes) -> Dict[str, str]:
        """Parse message response message from ECR device"""
        logger.info(f"Parsing response: {binascii.hexlify(response_bytes).decode()}")

        # Try native library first
        if self.ecr_lib and self.use_library:
            try:
                return self._parse_with_library(response_bytes)
            except Exception as e:
                logger.error(f"Library parse failed: {e}. Using fallback.")

        # Fallback to manual parsing
        return self._parse_manual(response_bytes)

    def _validate_transaction_type(self, trans_type: str) -> int:
        """Validate transaction type format - BRI FMS v3.3 (0x01-0x1E)"""
        try:
            trans_type_int = int(trans_type, 16)
            if trans_type_int < 0x01 or trans_type_int > 0x1E:
                raise ValueError(f"Invalid trans_type: {trans_type}")
            return trans_type_int
        except ValueError:
            logger.error(f"Invalid trans_type format: {trans_type}")
            raise ValueError("Transaction type must be a valid hex code (01-1E)")

    def _format_amount(
        self, amount: str, trans_type: str, use_serial_multiplier: bool
    ) -> str:
        """Format amount string matching desktop: %010d00 format (10 digits + '00')"""
        try:
            amount_int = int(amount.replace(",", ""))
            if amount_int < 0:
                raise ValueError("Amount must be non-negative")

            # BRI FMS v3.3: Desktop uses format "%010d00" which is 10 digits + "00" appended
            # This effectively sends amount in cents (multiply by 100)
            # Example: amount=10 -> "000000001000" (10*100)
            amount_str = f"{amount_int:010d}00"
            logger.info(
                f"Amount conversion: original='{amount}' -> int={amount_int} -> formatted='{amount_str}' (desktop format %010d00)"
            )

            if not amount_str.isdigit() or len(amount_str) != 12:
                raise ValueError("Amount must be numeric and 12 bytes")
            return amount_str
        except ValueError:
            logger.error(f"Invalid amount format: {amount}")
            raise ValueError("Amount must be a valid number")

    def _format_invoice_number(self, invoice_no: str, trans_type: str) -> str:
        """Format invoice number based on transaction type - BRI FMS v3.3

        Desktop always uses %012d format (12 bytes) regardless of transaction type.
        UI validation limits vary (6/10/12 digits) but wire format is always 12 bytes.
        """
        invoice_str = str(invoice_no or "0")
        if not invoice_str.isdigit():
            logger.error(f"Invalid invoice_no format: {invoice_no}")
            raise ValueError("Invoice number must be numeric")

        # Validate max length based on transaction type (UI validation)
        # VOID (0x03), VOID BRIZZI (0x0C) - trace number max 6 digits
        if trans_type in ["03", "0C"]:
            if len(invoice_str) > 6:
                logger.error(f"Trace number too long: {invoice_no} (max 6 digits)")
                raise ValueError("Trace number must be 6 digits or less")
            logger.info(f"VOID trace number: {invoice_no} (max 6 digits)")
        # QRIS REFUND (0x06) - reference ID max 10 digits
        elif trans_type == "06":
            if len(invoice_str) > 10:
                logger.error(f"Reference ID too long: {invoice_no} (max 10 digits)")
                raise ValueError("Reference ID must be 10 digits or less")
            logger.info(f"QRIS Refund reference ID: {invoice_no} (max 10 digits)")
        # QRIS STATUS TRANSAKSI (0x05) - reference ID max 12 digits
        elif trans_type == "05":
            if len(invoice_str) > 12:
                logger.error(f"Reference ID too long: {invoice_no} (max 12 digits)")
                raise ValueError("Reference ID must be 12 digits or less")
            logger.info(f"QRIS Status reference ID: {invoice_no} (max 12 digits)")
        # All other transactions - standard 12 digit max
        else:
            if len(invoice_str) > 12:
                logger.error(f"Invoice_no too long: {invoice_no} (max 12 digits)")
                raise ValueError("Invoice number must be 12 digits or less")

        # ALWAYS pad to 12 bytes for wire format (matches desktop %012d)
        invoice_str = invoice_str.zfill(12)
        logger.info(f"Invoice formatted to 12 bytes: {invoice_no} -> {invoice_str}")

        return invoice_str

    def _validate_card_number(self, card_no: str) -> str:
        """Validate and format card number"""
        if card_no and not all(c.isalnum() or c == " " for c in card_no):
            logger.error(f"Invalid card_no format: {card_no}")
            raise ValueError("Card number must be alphanumeric")
        return card_no

    def _pack_with_library(
        self, trans_type_int: int, amount_str: str, add_amount_str: str, invoice_str: str, card_no_str: str
    ) -> bytes:
        """Pack message using native library - BRI FMS v3.3 format"""
        req = ReqData()
        req.chTransType = trans_type_int
        req.szAmount = amount_str.encode("ascii")  # 12 bytes
        req.szAddAmount = add_amount_str.encode("ascii")  # 12 bytes - Tip/Non-Fare Amount
        req.szInvNo = invoice_str.encode("ascii")  # 12 bytes - Invoice/Reff No

        # Card number for BRIZZI transactions (19 bytes)
        if card_no_str:
            req.szCardNo = card_no_str.ljust(19, '\x00').encode("ascii")[:19]
        else:
            req.szCardNo = b"\x00" * 19

        # Filler (144 bytes) - for bank use
        req.szFiller = b"\x00" * 144

        req_msg_buf = ctypes.create_string_buffer(205)
        ret = self.ecr_lib.ecrPackRequest(req_msg_buf, ctypes.byref(req))
        if ret < 0:
            raise ValueError(f"Pack failed: {ret}")

        packed = req_msg_buf.raw[:ret]

        logger.info(f"Packed message with library: {binascii.hexlify(packed).decode()}")
        return packed

    def _pack_manual(
        self, trans_type_int: int, amount_str: str, add_amount_str: str, invoice_str: str, card_no_str: str
    ) -> bytes:
        """Manual message packing fallback - BRI FMS v3.3 format"""
        # Structure: [TransType:1][Amount:12][AddAmount:12][InvoiceNo:12][CardNo:19][Filler:144] = 200 bytes
        chTransType = trans_type_int
        szAmount = amount_str.encode("ascii")  # 12 bytes
        szAddAmount = add_amount_str.encode("ascii")  # 12 bytes - Tip/Non-Fare Amount
        szInvNo = invoice_str.encode("ascii")  # 12 bytes

        # Card number for BRIZZI transactions (19 bytes)
        if card_no_str:
            szCardNo = card_no_str.ljust(19, '\x00').encode("ascii")[:19]
        else:
            szCardNo = b"\x00" * 19

        # Filler (144 bytes) - for bank use
        szFiller = b"\x00" * 144

        # Build the message data
        message_data = bytes([chTransType]) + szAmount + szAddAmount + szInvNo + szCardNo + szFiller
        assert len(message_data) == 200, f"Invalid data length: {len(message_data)}, expected 200"

        stx = b"\x02"
        # Length in BCD format (as per protocol spec): 200 decimal = 02h 00h in BCD
        # BCD format: each byte represents two decimal digits
        # For 200: high byte = 02h (hundreds), low byte = 00h (tens and ones)
        length_bcd = bytes([0x02, 0x00])  # 200 in BCD format
        etx = b"\x03"
        # LRC calculation: Desktop includes STX despite documentation saying otherwise
        # Verified: Desktop sends LRC=0x12 (includes STX), not 0x10 (excludes STX)
        # Must match desktop for compatibility with EDC device
        to_lrc = stx + length_bcd + message_data + etx
        lrc_value = self.calculate_lrc(to_lrc)
        lrc = bytes([lrc_value])

        packed = stx + length_bcd + message_data + etx + lrc

        logger.info(f"Final packed message: {binascii.hexlify(packed).decode()}")
        return packed
    

    def _parse_with_library(self, response_bytes: bytes) -> Dict[str, str]:
        """Parse response using native library - BRI FMS v3.3"""
        rsp = RspData()
        rsp_msg_buf = ctypes.create_string_buffer(response_bytes, len(response_bytes))
        ret = self.ecr_lib.ecrParseResponse(rsp_msg_buf, ctypes.byref(rsp))
        if ret != 0:
            raise ValueError(f"Parse failed: {ret}")

        # BRI FMS v3.3 response format (300 bytes)
        return {
            "transType": f"{rsp.chTransType:02X}",
            "tid": rsp.szTID.value.decode("ascii", errors="ignore").strip(),
            "mid": rsp.szMID.value.decode("ascii", errors="ignore").strip(),
            "batchNumber": rsp.szBatchNumber.value.decode("ascii", errors="ignore").strip(),
            "issuerName": rsp.szIssuerName.value.decode("ascii", errors="ignore").strip(),
            "traceNo": rsp.szTraceNo.value.decode("ascii", errors="ignore").strip(),
            "invoiceNo": rsp.szInvoiceNo.value.decode("ascii", errors="ignore").strip(),
            "entryMode": chr(rsp.chEntryMode) if rsp.chEntryMode else "",
            "transAmount": self.format_amount(
                rsp.szTransAmount.value.decode("ascii", errors="ignore").strip()
            ),
            "totalAmount": self.format_amount(
                rsp.szTotalAmount.value.decode("ascii", errors="ignore").strip()
            ),
            "cardNo": rsp.szCardNo.value.decode("ascii", errors="ignore").strip(),
            "cardholderName": rsp.szCardholderName.value.decode("ascii", errors="ignore").strip(),
            "date": self.format_date(rsp.szDate.value.decode("ascii", errors="ignore").strip()),
            "time": self.format_time(rsp.szTime.value.decode("ascii", errors="ignore").strip()),
            "approvalCode": rsp.szApprovalCode.value.decode("ascii", errors="ignore").strip(),
            "responseCode": rsp.szResponseCode.value.decode("ascii", errors="ignore").strip(),
            "refNumber": rsp.szRefNumber.value.decode("ascii", errors="ignore").strip(),
            "balancePrepaid": self.format_amount(
                rsp.szBalancePrepaid.value.decode("ascii", errors="ignore").strip()
            ),
            "topupCardNo": rsp.szTopupCardNo.value.decode("ascii", errors="ignore").strip(),
            "transAddAmount": self.format_amount(
                rsp.szTransAddAmount.value.decode("ascii", errors="ignore").strip()
            ),
            "filler": rsp.szFiller.value.decode("ascii", errors="ignore").strip(),
            "qrCode": "",  # QR code data comes separately in serial communication
        }

    def _parse_manual(self, response_bytes: bytes) -> Dict[str, str]:
        """Manual response parsing fallback - BRI FMS v3.3 (300 bytes)"""

        def clean_field(byte_data: bytes) -> str:
            """Decode and clean field by removing null bytes and whitespace"""
            return byte_data.decode("ascii", errors="ignore").rstrip('\x00').strip()

        logger.info(f"Starting manual response parsing, received {len(response_bytes)} bytes")
        logger.debug(f"Response bytes (first 50): {response_bytes[:50].hex()}")

        # Validate message structure
        if len(response_bytes) < 5:
            logger.error(f"Response too short: {len(response_bytes)} bytes, minimum 5 required")
            raise ValueError("Response too short")
        if response_bytes[0] != 0x02:
            logger.error(f"Missing STX, found: 0x{response_bytes[0]:02X}")
            raise ValueError("Missing STX")

        length_bytes = response_bytes[1:3]
        msg_len = length_bytes[0] * 100 + length_bytes[1]
        logger.info(f"Message length from header: {msg_len} bytes (expected 300)")
        if msg_len != 300:
            logger.error(f"Invalid message length: {msg_len}, expected 300")
            raise ValueError(f"Invalid length: {msg_len}, expected 300")

        expected_total = 1 + 2 + msg_len + 1 + 1
        logger.debug(f"Expected total response size: {expected_total} bytes (STX + 2 len + {msg_len} data + ETX + LRC)")

        if len(response_bytes) < expected_total:
            logger.error(f"Response too short: {len(response_bytes)} bytes, minimum expected {expected_total} bytes")
            raise ValueError(
                f"Response too short: {len(response_bytes)}, minimum expected {expected_total}"
            )
        # Allow longer responses (with QR data appended)
        if len(response_bytes) > expected_total:
            logger.info(f"Response longer than expected: {len(response_bytes)} vs {expected_total}, may contain QR data")

        data_start = 3
        data_end = data_start + msg_len
        data = response_bytes[data_start:data_end]
        logger.debug(f"Extracting data from position {data_start} to {data_end} ({msg_len} bytes)")

        # Check for ETX - be flexible about its position for responses with QR data
        etx = response_bytes[data_end] if data_end < len(response_bytes) else 0x00
        if etx != 0x03:
            logger.warning(f"ETX not found at expected position {data_end}, value: 0x{etx:02X}")
        else:
            logger.debug(f"ETX found at position {data_end}")
            # Only validate LRC if we have proper ETX
            received_lrc = response_bytes[data_end + 1] if (data_end + 1) < len(response_bytes) else 0x00
            # LRC calculation: Include STX (matching desktop behavior, not documentation)
            stx_byte = bytes([response_bytes[0]])  # STX = 0x02
            to_lrc = stx_byte + length_bytes + data + bytes([etx])
            computed_lrc = self.calculate_lrc(to_lrc)
            logger.debug(f"LRC check: received=0x{received_lrc:02X}, computed=0x{computed_lrc:02X}")
            if received_lrc != computed_lrc:
                logger.warning(
                    f"LRC mismatch: received {received_lrc:02X}, computed {computed_lrc:02X}"
                )

        logger.info("✓ Response validation successful, unpacking data fields...")

        # Unpack data fields according to BRI FMS v3.3 spec (300 bytes)
        offset = 0
        chTransType = data[offset]
        offset += 1
        szTID = data[offset : offset + 8]
        offset += 8
        szMID = data[offset : offset + 15]
        offset += 15
        szBatchNumber = data[offset : offset + 6]
        offset += 6
        szIssuerName = data[offset : offset + 25]
        offset += 25
        szTraceNo = data[offset : offset + 6]
        offset += 6
        szInvoiceNo = data[offset : offset + 6]
        offset += 6
        chEntryMode = data[offset : offset + 1]
        offset += 1
        szTransAmount = data[offset : offset + 12]
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
        szApprovalCode = data[offset : offset + 8]
        offset += 8
        szResponseCode = data[offset : offset + 2]
        offset += 2
        szRefNumber = data[offset : offset + 12]
        offset += 12
        szBalancePrepaid = data[offset : offset + 12]
        offset += 12
        szTopupCardNo = data[offset : offset + 19]
        offset += 19
        szTransAddAmount = data[offset : offset + 12]
        offset += 12
        szFiller = data[offset : offset + 84]

        # Extract and decode fields using clean_field to remove null bytes
        trans_type = f"{chTransType:02X}"
        tid = clean_field(szTID)
        mid = clean_field(szMID)
        batch_number = clean_field(szBatchNumber)
        issuer_name = clean_field(szIssuerName)
        trace_no = clean_field(szTraceNo)
        invoice_no = clean_field(szInvoiceNo)
        entry_mode = clean_field(chEntryMode)
        trans_amount_raw = clean_field(szTransAmount)
        total_amount_raw = clean_field(szTotalAmount)
        card_no = clean_field(szCardNo)
        cardholder_name = clean_field(szCardholderName)
        date_raw = clean_field(szDate)
        time_raw = clean_field(szTime)
        approval_code = clean_field(szApprovalCode)
        response_code = clean_field(szResponseCode)
        ref_number = clean_field(szRefNumber)
        balance_prepaid_raw = clean_field(szBalancePrepaid)
        topup_card_no = clean_field(szTopupCardNo)
        trans_add_amount_raw = clean_field(szTransAddAmount)
        filler_content = clean_field(szFiller)

        # Separate message from QR code in filler field
        # For non-QR transactions, filler contains status message
        # For QR transactions, filler may contain QR data or message
        if filler_content and not filler_content.startswith("00"):
            # If filler doesn't start with "00", it's probably a status message
            message = filler_content
            qr_code = ""
        else:
            # If filler starts with "00", it might be QR data
            message = ""
            qr_code = filler_content

        # Always include all fields, even if empty, for consistent JSON structure
        result = {
            "transType": trans_type,
            "tid": tid,
            "mid": mid,
            "batchNumber": batch_number,
            "issuerName": issuer_name,
            "traceNo": trace_no,
            "invoiceNo": invoice_no,
            "entryMode": entry_mode,
            "transAmount": (
                self.format_amount(trans_amount_raw) if trans_amount_raw else ""
            ),
            "totalAmount": (
                self.format_amount(total_amount_raw) if total_amount_raw else ""
            ),
            "cardNo": card_no,
            "cardholderName": cardholder_name,
            "date": self.format_date(date_raw) if date_raw else "",
            "time": self.format_time(time_raw) if time_raw else "",
            "approvalCode": approval_code,
            "responseCode": response_code,
            "refNumber": ref_number,
            "balancePrepaid": (
                self.format_amount(balance_prepaid_raw) if balance_prepaid_raw else ""
            ),
            "topupCardNo": topup_card_no,
            "transAddAmount": (
                self.format_amount(trans_add_amount_raw) if trans_add_amount_raw else ""
            ),
            "filler": message,
            "qrCode": qr_code,
        }

        return result
