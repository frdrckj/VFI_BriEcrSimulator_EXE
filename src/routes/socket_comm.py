"""
Socket Communication Module
Handles socket connections, REST API communication, and socket-specific functionality
"""

import socket
import time
import requests
import binascii
import threading
import logging
import os
from typing import Dict, Any, Optional, Callable
import ssl

logger = logging.getLogger(__name__)


class SocketCommListener:
    """Socket communication listener for native socket mode"""

    def __init__(self, callback: Optional[Callable] = None):
        self.callback = callback
        self.show_data = False
        self.is_listening = False

    def set_show_data(self, show: bool):
        """Control whether to show response data"""
        self.show_data = show


class SocketComm:
    """Main socket communication class - matching desktop version behavior"""

    def __init__(self, ecr_core=None):
        self.socket_config = {}
        self.is_connected = False
        self.listener = None
        self.ecr_core = ecr_core  # ECR core for native protocol
        self.listener_thread = None
        self.stop_listener = False

    def set_ecr_core(self, ecr_core):
        """Set ECR core instance for native protocol operations"""
        self.ecr_core = ecr_core

    def update_config(self, config: Dict[str, Any]):
        """Update socket configuration"""
        self.socket_config = config

    def test_connection(self) -> bool:
        """Test socket connection"""
        if self.socket_config.get("enable_rest_api", False):
            return self._test_rest_api_connection()
        else:
            return self._test_native_socket_connection()

    def connect(self) -> bool:
        """Connect to socket endpoint - matching desktop version"""
        if self.socket_config.get("enable_rest_api", False):
            # REST API mode - just test connection
            return self._test_rest_api_connection()
        else:
            # Native socket mode - open socket connection using library
            return self._connect_native_socket()

    def disconnect(self):
        """Disconnect from socket endpoint - matching desktop version"""
        if self.is_connected:
            if self.socket_config.get("enable_rest_api", False):
                # REST API mode - just mark as disconnected
                self.is_connected = False
            else:
                # Native socket mode - close socket using library
                self._disconnect_native_socket()

    def send_transaction(
        self, trans_type: str, amount: str, invoice_no: str, card_no: str = "", add_amount: str = "0"
    ) -> Dict[str, Any]:
        """Send transaction via socket communication - matching desktop version"""
        if self.socket_config.get("enable_rest_api", False):
            return self._send_rest_api_transaction(trans_type, amount, invoice_no, card_no)
        else:
            return self._send_native_socket_transaction(trans_type, amount, invoice_no, card_no, add_amount)

    def _connect_native_socket(self) -> bool:
        """Connect using native socket protocol - matching desktop version"""
        if not self.ecr_core:
            logger.error("ECR core not initialized for native socket")
            return False

        try:
            ip = self.socket_config.get("socket_ip", "127.0.0.1")
            port = int(self.socket_config.get("socket_port", 9001))
            ssl_enabled = self.socket_config.get("enable_ssl", False)

            logger.info(f"Opening native socket: {ip}:{port}, SSL={ssl_enabled}")

            # Use ecr_core to open socket connection
            success = self.ecr_core.open_socket(ip, port, ssl_enabled)

            if success:
                self.is_connected = True
                # Don't start background listener - use synchronous polling in transaction method
                logger.info("Native socket connected successfully (synchronous mode)")
                return True
            else:
                logger.error("Failed to open native socket")
                return False

        except Exception as e:
            logger.error(f"Native socket connection failed: {e}")
            return False

    def _disconnect_native_socket(self):
        """Disconnect native socket - matching desktop version"""
        try:
            # Stop listener thread
            self._stop_listener()

            # Use ecr_core to close socket
            if self.ecr_core:
                self.ecr_core.close_socket()

            self.is_connected = False
            logger.info("Native socket disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting native socket: {e}")

    def _start_listener(self):
        """Start background listener thread for socket responses"""
        if self.listener_thread and self.listener_thread.is_alive():
            return  # Already running

        self.stop_listener = False
        self.listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
        self.listener_thread.start()
        logger.info("Socket listener thread started")

    def _stop_listener(self):
        """Stop background listener thread"""
        self.stop_listener = True
        if self.listener_thread:
            self.listener_thread.join(timeout=2)
            self.listener_thread = None
        logger.info("Socket listener thread stopped")

    def _listener_loop(self):
        """Background listener loop for socket responses - matching desktop version"""
        while not self.stop_listener and self.is_connected:
            try:
                if self.ecr_core:
                    # Try to receive data (non-blocking with timeout)
                    data = self.ecr_core.recv_socket(9999)

                    if len(data) > 0:
                        if len(data) == 1:
                            # ACK/NACK response
                            if data[0] == 0x06:
                                logger.info("Received ACK")
                            elif data[0] == 0x15:
                                logger.info("Received NACK")
                            else:
                                logger.warning(f"Unknown single byte response: {data[0]:02X}")
                        else:
                            # Full response message
                            logger.info(f"Received response data: {len(data)} bytes")
                            # Response will be handled by the transaction method
                    else:
                        # No data, sleep briefly
                        time.sleep(0.1)
                else:
                    break

            except Exception as e:
                logger.error(f"Listener loop error: {e}")
                time.sleep(0.5)

    def _send_native_socket_transaction(
        self, trans_type: str, amount: str, invoice_no: str, card_no: str, add_amount: str
    ) -> Dict[str, Any]:
        """Send transaction using native socket protocol - matching desktop version"""
        if not self.ecr_core:
            raise ValueError("ECR core not initialized")

        if not self.is_connected:
            raise ValueError("Not connected to socket")

        try:
            # Pack request message
            req_data = self.ecr_core.pack_request_message(
                trans_type=trans_type,
                amount=amount,
                invoice_no=invoice_no,
                card_no=card_no,
                add_amount=add_amount,
                use_serial_multiplier=False  # Don't multiply for socket communication
            )

            logger.info(f"Sending {len(req_data)} bytes via native socket")
            logger.debug(f"Request data: {binascii.hexlify(req_data).decode()}")

            # Flush any stale data from socket buffer before sending new request
            # This prevents old/duplicate responses from interfering with new transactions
            # Use very short timeout (0.1s) to avoid delays when buffer is empty
            flushed_bytes = 0
            while True:
                stale_data = self.ecr_core.recv_socket(9999, timeout=0.1)
                if len(stale_data) == 0:
                    break  # No more data in buffer
                flushed_bytes += len(stale_data)
                logger.warning(f"Flushed {len(stale_data)} stale bytes from socket buffer")

            if flushed_bytes > 0:
                logger.warning(f"Total flushed: {flushed_bytes} bytes of stale data before new request")

            # Send via socket
            success = self.ecr_core.send_socket(req_data)

            if not success:
                raise ValueError("Failed to send data via socket")

            # Initialize data accumulator
            accumulated_data = b""  # Accumulate response data chunks

            # Wait for ACK
            time.sleep(0.5)
            ack_data = self.ecr_core.recv_socket(1)

            if len(ack_data) == 1 and ack_data[0] == 0x06:
                logger.info("Received ACK (0x06), waiting for response...")
            elif len(ack_data) == 1 and ack_data[0] == 0x15:
                raise ValueError("Received NACK (0x15) from device")
            elif len(ack_data) == 1 and ack_data[0] == 0x02:
                # Received STX instead of ACK - response came immediately
                # This is the start of the actual response, not ACK
                logger.info("Response started immediately (no separate ACK), STX received")
                accumulated_data = ack_data  # Start accumulating from this STX
            else:
                logger.warning(f"Unexpected ACK response: {binascii.hexlify(ack_data).decode() if ack_data else 'empty'}")

            # Wait for full response - matching desktop SocketCommListener behavior
            # Desktop polls every 100ms indefinitely; set 10 minute timeout for safety
            max_wait = 600  # 10 minutes (matching REST API timeout)
            start_time = time.time()
            poll_count = 0

            logger.info(f"Starting response polling loop, max_wait={max_wait}s")

            while time.time() - start_time < max_wait:
                poll_count += 1
                elapsed = time.time() - start_time

                # Log every 10 polls (1 second) to track progress
                if poll_count % 10 == 0:
                    logger.info(f"Poll #{poll_count} - Elapsed: {elapsed:.1f}s / {max_wait}s")

                response_data = self.ecr_core.recv_socket(9999)

                if len(response_data) == 0:
                    # No data received this poll
                    if poll_count % 50 == 0:  # Log every 5 seconds
                        logger.debug(f"No data received yet (poll #{poll_count}, {elapsed:.1f}s elapsed)")
                elif len(response_data) == 1:
                    # Could be STX or other single byte - accumulate it
                    accumulated_data += response_data
                    logger.debug(f"Received single byte: 0x{response_data[0]:02X}, accumulated: {len(accumulated_data)} bytes")

                    # If it's just an ACK/NACK by itself, ignore it (already logged earlier)
                    if response_data[0] in [0x06, 0x15] and len(accumulated_data) == 1:
                        accumulated_data = b""  # Reset for actual response
                elif len(response_data) > 1:
                    # Received multi-byte data - accumulate it
                    accumulated_data += response_data
                    logger.info(f"Received {len(response_data)} bytes, accumulated total: {len(accumulated_data)} bytes")

                # Check if we have a complete response (305 bytes: STX + 2 len + 300 data + ETX + LRC)
                if len(accumulated_data) >= 305:
                    logger.info(f"✓ Received complete response: {len(accumulated_data)} bytes after {elapsed:.1f}s and {poll_count} polls")
                    logger.debug(f"Response hex: {binascii.hexlify(accumulated_data).decode()}")

                    try:
                        parsed = self.ecr_core.parse_response_message(accumulated_data)
                        logger.info(f"✓ Response parsed successfully - Response Code: {parsed.get('responseCode', 'N/A')}")

                        return {
                            "status": "success",
                            "response": parsed,
                            "raw_response": binascii.hexlify(accumulated_data).decode()
                        }
                    except Exception as parse_error:
                        logger.error(f"✗ Failed to parse response: {parse_error}")
                        raise ValueError(f"Response parsing failed: {parse_error}")

                time.sleep(0.1)  # 100ms like desktop SocketCommListener.java

            logger.error(f"✗ Timeout waiting for response after {max_wait}s ({poll_count} polls)")
            raise ValueError(f"Timeout waiting for response after {max_wait} seconds")

        except Exception as e:
            logger.error(f"Native socket transaction failed: {e}")
            raise

    def _test_rest_api_connection(self) -> bool:
        """Test REST API connection"""
        try:
            ip = self.socket_config.get("socket_ip", "127.0.0.1")
            port = int(self.socket_config.get("socket_port", 9001))
            ssl_enabled = self.socket_config.get("enable_ssl", False)

            # First, test basic TCP connectivity
            logger.info(f"Testing TCP connection to {ip}:{port}")
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.settimeout(3)

            try:
                test_sock.connect((ip, port))
                test_sock.close()
                logger.info(f"TCP connection successful to {ip}:{port}")
            except Exception as tcp_error:
                logger.error(f"TCP connection failed to {ip}:{port}: {tcp_error}")
                return False

            # TCP connection works, now mark as connected
            # Don't send test transaction during connection - just verify port is open
            self.is_connected = True
            logger.info(f"REST API connection successful to {ip}:{port}")
            return True

        except Exception as e:
            logger.error(f"REST API connection test failed: {e}")
            return False

    def _test_native_socket_connection(self) -> bool:
        """Test native socket connection"""
        try:
            ip = self.socket_config.get("socket_ip", "127.0.0.1")
            port = int(self.socket_config.get("socket_port", 9001))

            test_sock = socket.socket()
            test_sock.settimeout(5)
            test_sock.connect((ip, port))
            test_sock.close()

            self.is_connected = True
            logger.info(f"Native socket connection successful to {ip}:{port}")
            return True

        except Exception as e:
            logger.error(f"Native socket connection test failed: {e}")
            return False

    def _send_rest_api_transaction(
        self, trans_type: str, amount: str, invoice_no: str, card_no: str, add_amount: str = "0"
    ) -> Dict[str, Any]:
        """Send transaction via REST API - matching desktop BriMainFrame.java"""
        try:
            ip = self.socket_config.get("socket_ip", "127.0.0.1")
            port = self.socket_config.get("socket_port", "9001")
            ssl_enabled = self.socket_config.get("enable_ssl", False)
            protocol = "https" if ssl_enabled else "http"
            base_url = f"{protocol}://{ip}:{port}"

            username = "VfiF4BRI"
            serial_number = self.socket_config.get("edc_serial_number", "V1E1012320")
            if not serial_number:
                raise ValueError("EDC serial number not configured in settings")
            password = "VFI" + serial_number

            # Format amounts (preserve original value without conversion)
            amount_str = str(amount).replace(",", "")
            add_amount_str = str(add_amount).replace(",", "")

            # Format invoice number as 12-digit zero-padded string (matching desktop line 327)
            invoice_str = invoice_no if invoice_no else "0"
            invoice_formatted = f"{int(invoice_str):012d}"

            logger.info(f"Using REST API auth: {username}:{password}")
            logger.info(f"Connecting to ECR adaptor at: {base_url}")

            # Match exact desktop format (BriMainFrame.java lines 325-329)
            req_json = {
                "transType": trans_type,
                "transAmount": amount_str,
                "invoiceNo": invoice_formatted,
                "transAddAmount": add_amount_str,
                "cardNumber": card_no if card_no else "",
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            # Convert to JSON string to log exact payload
            import json
            json_body = json.dumps(req_json)

            logger.info(f"Sending transaction request to: {base_url}/transaction/bri")
            logger.info(f"Request JSON: {json_body}")
            logger.info(f"Request dict: {req_json}")
            logger.info(f"Authorization: Basic {username}:{password}")

            # Send transaction request with 60s timeout (matching desktop line 126/160)
            r = requests.post(
                f"{base_url}/transaction/bri",
                json=req_json,
                auth=(username, password),
                headers=headers,
                verify=False,
                timeout=60,  # Desktop uses 60 seconds
            )

            logger.info(f"Transaction response: {r.status_code} - {r.text}")

            if r.status_code == 401:
                raise ValueError(
                    f"Authentication failed. Check EDC serial number in settings. "
                    f"Expected auth: {username}:{password}"
                )
            elif r.status_code != 200:
                raise ValueError(f"Transaction failed: {r.status_code} {r.text}")

            resp = r.json()
            trx_id_terminal = resp.get("trxId")
            if not trx_id_terminal:
                raise ValueError("No transaction ID received from ECR adapter")

            logger.info(f"Transaction initiated with ID: {trx_id_terminal}")

            # Poll for results
            return self._poll_rest_api_result(
                base_url, username, password, headers, trx_id_terminal
            )

        except Exception as e:
            logger.error(f"REST API transaction failed: {e}")
            raise

    def _poll_rest_api_result(
        self,
        base_url: str,
        username: str,
        password: str,
        headers: Dict[str, str],
        trx_id_terminal: str,
    ) -> Dict[str, Any]:
        """Poll for REST API transaction results - matching desktop SocketCommListener.java behavior"""
        poll_count = 0
        # Desktop version polls indefinitely with 100ms interval (line 118)
        # Set very high timeout (10 minutes) to match desktop's no-timeout behavior
        max_polls = 6000  # 10 minutes at 100ms intervals (matching desktop behavior)
        poll_interval = 0.1  # 100ms like desktop (SocketCommListener.java line 118: Thread.sleep(100))
        start_time = time.time()

        logger.info(f"Starting REST API polling for trxId: {trx_id_terminal}, max_polls={max_polls}")

        while poll_count < max_polls:
            poll_count += 1
            elapsed = time.time() - start_time
            time.sleep(poll_interval)

            # Log progress every 10 polls (1 second)
            if poll_count % 10 == 0:
                logger.info(f"REST API Poll #{poll_count}/{max_polls} - Elapsed: {elapsed:.1f}s")
            elif poll_count == 1:
                logger.info(f"REST API Poll #{poll_count} - Starting...")

            try:
                r = requests.post(
                    f"{base_url}/result/bri",
                    json={"trxId": trx_id_terminal},
                    auth=(username, password),
                    headers=headers,
                    verify=False,
                    timeout=5,
                )

                # Only log full response on non-503 status or every 50 polls
                if r.status_code != 503 or poll_count % 50 == 0:
                    logger.info(f"Poll #{poll_count} response: {r.status_code} - {r.text[:200]}")

                if r.status_code == 503:
                    if poll_count % 50 == 0:  # Log every 5 seconds
                        logger.info(f"Transaction still processing after {elapsed:.1f}s ({poll_count} polls)...")
                    continue
                elif r.status_code == 200:
                    response_dict = r.json()

                    # Switch traceNo and invoiceNo values for consistency with serial parsing
                    if "traceNo" in response_dict and "invoiceNo" in response_dict:
                        original_trace_no = response_dict["traceNo"]
                        original_invoice_no = response_dict["invoiceNo"]
                        response_dict["traceNo"] = original_invoice_no
                        response_dict["invoiceNo"] = original_trace_no
                        logger.info(f"Switched fields: traceNo={original_invoice_no}, invoiceNo={original_trace_no}")

                    logger.info(f"✓ Transaction completed after {elapsed:.1f}s ({poll_count} polls) - Response Code: {response_dict.get('responseCode', 'N/A')}")
                    return {
                        "status": "success",
                        "response": response_dict,
                        "transaction_succeeded": self._check_transaction_success(
                            response_dict
                        ),
                    }
                else:
                    logger.error(f"✗ Unexpected poll response at poll #{poll_count}: {r.status_code} {r.text}")
                    break

            except requests.exceptions.RequestException as e:
                logger.error(f"✗ Poll request failed at poll #{poll_count}: {str(e)}")
                if poll_count % 10 == 0:
                    logger.error(f"Network error persisting after {poll_count} attempts")
                continue

        elapsed_minutes = max_polls * poll_interval / 60
        logger.error(f"✗ REST API polling timeout after {elapsed_minutes:.1f} minutes ({poll_count} polls)")
        raise ValueError(f"Polling timeout after {elapsed_minutes:.1f} minutes")

    def _check_transaction_success(
        self, response_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if transaction actually succeeded based on response code"""
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

        return {"failed": transaction_failed, "failure_reason": failure_reason}

    def auto_detect_serial_number(self) -> Dict[str, Any]:
        """Try to detect the correct EDC serial number"""
        if not self.socket_config.get("enable_rest_api", False):
            return {"error": "REST API mode not enabled"}

        ip = self.socket_config.get("socket_ip", "127.0.0.1")
        port = self.socket_config.get("socket_port", "9001")
        ssl_enabled = self.socket_config.get("enable_ssl", False)
        protocol = "https" if ssl_enabled else "http"
        base_url = f"{protocol}://{ip}:{port}"

        # Common serial numbers to try
        common_serials = [
            "V1E0212639",  # From BRI collection
            "V1E1012320",  # User provided
            "V1E0000001",  # Common test serial
            "V1E0000000",  # Another test serial
        ]

        username = "VfiF4BRI"
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
                    f"{base_url}/transaction/bri",
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
                    results.append(result)
                    return {
                        "status": "success",
                        "working_serial": serial,
                        "all_results": results,
                    }
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

        return {
            "status": "failed",
            "message": "No working serial number found",
            "results": results,
        }


def check_network_connectivity() -> bool:
    """Check if network/internet connection is available"""
    try:
        # Try to reach a reliable external server
        import urllib.request

        urllib.request.urlopen("http://www.google.com", timeout=3)
        return True
    except Exception:
        try:
            # Alternative check - try to reach local gateway
            import subprocess
            import platform

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
