"""
Message Protocol Handling Module
Handles message formatting, transaction processing, and protocol-specific logic
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
from .ecr_core import EcrCore
from .serial_comm import SerialComm
from .socket_comm import SocketComm, check_network_connectivity
from .ecr_config import EcrConfig, EcrUtils

logger = logging.getLogger(__name__)


class TransactionProcessor:
    """Main transaction processing coordinator"""

    def __init__(
        self,
        ecr_core: EcrCore,
        serial_comm: SerialComm,
        socket_comm: SocketComm,
        config: EcrConfig,
    ):
        self.ecr_core = ecr_core
        self.serial_comm = serial_comm
        self.socket_comm = socket_comm  # FIX: Use the passed socket_comm, not create new one
        self.config = config
        self.is_connected = False

        # Set up response callbacks
        self.serial_comm.set_response_callback(self._handle_serial_response)

    def update_connection_status(self, connected: bool):
        """Update connection status"""
        self.is_connected = connected

    def build_request(
        self, transaction_type: str, amount: str, invoice_no: str, card_no: str = "", add_amount: str = "0"
    ) -> Dict[str, Any]:
        """Build a human-readable transaction request"""
        try:
            # Get transaction code
            trans_type_map = EcrUtils.get_transaction_type_mapping()
            trans_code = trans_type_map.get(transaction_type.upper(), "01")

            # Validate by attempting to pack the message
            use_serial_multiplier = self.config.is_serial_mode()
            self.ecr_core.pack_request_message(
                trans_code, amount, invoice_no, card_no, add_amount, use_serial_multiplier
            )

            # Build human-readable format
            human_readable_request = EcrUtils.build_human_readable_request(
                transaction_type, amount, invoice_no, card_no, add_amount
            )

            return {"request": human_readable_request, "type": "human"}

        except ValueError as e:
            logger.error(f"Build request error: {str(e)}")
            raise

    def process_transaction(
        self, transaction_type: str, amount: str, invoice_no: str, card_no: str = "", add_amount: str = "0", user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process a transaction"""
        if not self.is_connected:
            raise ValueError("Not connected")

        # Check network connectivity for socket connections
        if self.config.is_socket_mode() and not check_network_connectivity():
            self.is_connected = False
            raise ValueError("Network connection lost - automatically disconnected")

        # Get transaction code
        trans_type_map = EcrUtils.get_transaction_type_mapping()
        trans_code = trans_type_map.get(transaction_type.upper(), "01")

        # Create transaction record
        trx_id = EcrUtils.generate_transaction_id()
        transaction_data = {
            "status": "processing",
            "request": {
                "transType": transaction_type,
                "transCode": trans_code,
                "amount": amount,
                "invoiceNo": invoice_no,
                "cardNo": card_no,
                "addAmount": add_amount,
            },
            "timestamp": time.time(),
        }

        self.config.add_transaction(trx_id, transaction_data, user_id=user_id)

        try:
            if self.config.is_serial_mode():
                return self._process_serial_transaction(
                    trx_id, trans_code, amount, invoice_no, card_no, add_amount
                )
            else:
                return self._process_socket_transaction(
                    trx_id, trans_code, amount, invoice_no, card_no, add_amount
                )

        except Exception as e:
            # Update transaction with error
            self.config.update_transaction(trx_id, {"status": "error", "error": str(e)})

            local_timestamp = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(transaction_data["timestamp"]),
            )

            raise ValueError(str(e))

    def _process_serial_transaction(
        self, trx_id: str, trans_code: str, amount: str, invoice_no: str, card_no: str, add_amount: str = "0"
    ) -> Dict[str, Any]:
        """Process transaction via serial communication - exactly like desktop"""
        # Check listener health before processing
        if not self.serial_comm.is_listener_alive():
            logger.warning("Serial listener not alive, restarting...")
            self.serial_comm._start_native_listener()
            time.sleep(0.5)  # Give listener time to start

        # Pack message for serial (with amount multiplication)
        packed_message = self.ecr_core.pack_request_message(
            trans_code, amount, invoice_no, card_no, add_amount, use_serial_multiplier=True
        )

        try:
            # Send message via native library only - like desktop Serial.send()
            if self.serial_comm.send_message(packed_message):
                # Transaction sent successfully, response will be handled by native listener
                self.config.update_transaction(
                    trx_id, {"status": "processing", "note": "Waiting for EDC response"}
                )

                logger.info(
                    f"Transaction {trx_id} sent successfully via native library"
                )

                return {
                    "status": "processing",
                    "trxId": trx_id,
                    "message": "Waiting for EDC response",
                }
            else:
                raise ValueError("Failed to send message via native library")

        except Exception as e:
            logger.error(f"Serial transaction failed: {e}")
            self.config.update_transaction(trx_id, {"status": "error", "error": str(e)})
            raise

    def _process_socket_transaction(
        self, trx_id: str, trans_code: str, amount: str, invoice_no: str, card_no: str, add_amount: str = "0"
    ) -> Dict[str, Any]:
        """Process transaction via socket communication"""
        try:
            # Update socket comm config
            self.socket_comm.update_config(self.config.get_socket_config())

            # Send transaction (supports both REST API and native socket protocol)
            result = self.socket_comm.send_transaction(
                trans_code, amount, invoice_no, card_no, add_amount
            )

            if result["status"] == "success":
                response_dict = result["response"]

                # Check if transaction actually succeeded
                success_check = EcrUtils.check_transaction_success(response_dict)

                # Parse timestamp
                local_timestamp = time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(self.config.get_transaction(trx_id)["timestamp"]),
                )
                parsed_timestamp = EcrUtils.parse_response_datetime(response_dict)
                timestamp = parsed_timestamp if parsed_timestamp else local_timestamp

                if success_check["failed"]:
                    # Transaction failed
                    self.config.update_transaction(
                        trx_id,
                        {
                            "status": "failed",
                            "error": success_check["failure_reason"],
                            "response": response_dict,
                        },
                    )

                    return {
                        "status": "failed",
                        "trxId": trx_id,
                        "response": response_dict,
                        "error": success_check["failure_reason"],
                        "timestamp": timestamp,
                    }
                else:
                    # Transaction succeeded
                    self.config.update_transaction(
                        trx_id, {"status": "success", "response": response_dict}
                    )

                    return {
                        "status": "success",
                        "trxId": trx_id,
                        "response": response_dict,
                        "timestamp": timestamp,
                    }
            else:
                raise ValueError(f"Socket transaction failed: {result}")

        except Exception as e:
            logger.error(f"Socket transaction failed: {e}")
            self.config.update_transaction(trx_id, {"status": "error", "error": str(e)})
            raise

    def _handle_serial_response(
        self, response_type: str, response_data: Optional[Dict[str, Any]]
    ):
        """Handle responses from serial communication"""
        logger.info(
            f"_handle_serial_response called with type: {response_type}, data: {response_data is not None}"
        )
        try:
            if (
                response_type == "RESPONSE" or response_type == "RAW_RESPONSE"
            ) and response_data:
                logger.info("Processing valid response data")
                # Find the latest processing transaction
                processing_trxs = []
                transaction_history = self.config.get_transaction_history()
                logger.info(
                    f"Current transaction history has {len(transaction_history)} transactions"
                )

                for trx_id, trx_data in transaction_history.items():
                    logger.info(
                        f"Transaction {trx_id}: status = {trx_data.get('status')}"
                    )
                    if trx_data.get("status") == "processing":
                        processing_trxs.append((trx_id, trx_data["timestamp"]))

                logger.info(f"Found {len(processing_trxs)} processing transactions")
                if processing_trxs:
                    # Get the most recent processing transaction
                    latest_trx_id = max(processing_trxs, key=lambda x: x[1])[0]
                    logger.info(f"Updating transaction {latest_trx_id} with response")

                    # Parse the raw response data
                    raw_response_hex = response_data["raw_response"]
                    try:
                        # Convert hex string to bytes for parsing
                        response_bytes = bytes.fromhex(raw_response_hex)

                        # For responses that don't have proper ETX termination,
                        # try to extract just the main response part (305 bytes: STX + length + 300 data + ETX + LRC)
                        if len(response_bytes) >= 305:
                            main_response = response_bytes[:305]
                            # Try to parse just the main response first
                            try:
                                parsed_response = self.ecr_core.parse_response_message(
                                    main_response
                                )
                            except Exception as main_parse_error:
                                # If main response parsing fails, try with the full response
                                logger.warning(
                                    f"Main response parse failed: {main_parse_error}, trying full response"
                                )
                                parsed_response = self.ecr_core.parse_response_message(
                                    response_bytes
                                )
                        else:
                            # Parse the full response if it's shorter
                            parsed_response = self.ecr_core.parse_response_message(
                                response_bytes
                            )

                        # Don't add raw hex data for successful parsing (keep response clean)
                        # parsed_response["raw_hex"] = raw_response_hex

                        # Handle QR code data from collected bytes if available
                        if (
                            "unknown_bytes" in response_data
                            and response_data["unknown_bytes"]
                        ):
                            qr_bytes = response_data["unknown_bytes"]
                            try:
                                # Convert collected QR bytes to hex string first
                                qr_hex_string = qr_bytes.hex().upper()
                                # logger.info(f"Collected QR bytes as hex: {qr_hex_string[:50]}...")

                                # Add "3030" (00 in ASCII) prefix to the hex string for QR code parsing
                                prefixed_qr_hex = "3030" + qr_hex_string

                                # Convert back to bytes and then decode as ASCII for display
                                try:
                                    prefixed_qr_bytes = bytes.fromhex(prefixed_qr_hex)
                                    qr_display_string = prefixed_qr_bytes.decode(
                                        "ascii", errors="ignore"
                                    )
                                    parsed_response["qrCode"] = qr_display_string
                                    logger.info(
                                        f"Final QR code with 00 prefix: {qr_display_string[:50]}..."
                                    )
                                except:
                                    # Fallback: just show hex with 00 prefix
                                    parsed_response["qrCode"] = "00" + qr_hex_string
                                    logger.info(
                                        f"QR code (hex format): 00{qr_hex_string[:50]}..."
                                    )

                            except Exception as e:
                                logger.error(f"Failed to process QR data: {e}")

                        # Also check if QR code data is in parsed response itself
                        elif (
                            "qrCode" in parsed_response
                            and parsed_response["qrCode"].strip()
                        ):
                            # For QR code, add "00" prefix if it doesn't already exist
                            qr_data = parsed_response["qrCode"].strip()
                            if not qr_data.startswith("00"):
                                parsed_response["qrCode"] = "00" + qr_data
                                logger.info(
                                    f"Added 00 prefix to QR code: {qr_data[:20]}..."
                                )

                        # Determine status based on response code
                        success_check = EcrUtils.check_transaction_success(parsed_response)
                        status = "failed" if success_check["failed"] else "success"
                        
                        update_data = {
                            "status": status,
                            "raw_response": raw_response_hex,
                            "response": parsed_response,
                        }
                        if success_check["failed"]:
                            update_data["error"] = success_check["failure_reason"]
                        logger.info(
                            "Successfully parsed raw response into structured data"
                        )

                    except Exception as parse_error:
                        logger.error(f"Failed to parse raw response: {parse_error}")
                        # Still save the raw response even if parsing fails
                        # Create a basic response object to show the raw data
                        basic_response = {
                            "raw_hex": raw_response_hex,
                            "parse_error": str(parse_error),
                            "message": "Raw response received but parsing failed",
                            "responseCode": "PARSE_ERROR",
                        }
                        update_data = {
                            "status": "error parsing",
                            "raw_response": raw_response_hex,
                            "response": basic_response,
                            "parse_error": str(parse_error),
                            "error": f"Parse error: {str(parse_error)}",
                        }

                    self.config.update_transaction(latest_trx_id, update_data)
                    logger.info(
                        f"Updated transaction {latest_trx_id} with response data"
                    )
                else:
                    logger.warning(
                        "Received response but no processing transaction found"
                    )
            else:
                logger.warning(
                    f"Invalid response: type={response_type}, has_data={response_data is not None}"
                )

        except Exception as e:
            logger.error(f"Error handling serial response: {str(e)}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")

    def get_transaction_status(self, trx_id: str) -> Dict[str, Any]:
        """Get transaction status by ID"""
        transaction = self.config.get_transaction(trx_id)
        if not transaction:
            raise ValueError("Transaction not found")

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
            parsed_timestamp = EcrUtils.parse_response_datetime(transaction["response"])
            if parsed_timestamp:
                status_info["timestamp"] = parsed_timestamp
        elif "raw_response" in transaction:
            # Try to parse raw response if no parsed response exists (backward compatibility)
            try:
                raw_response_hex = transaction["raw_response"]
                response_bytes = bytes.fromhex(raw_response_hex)
                parsed_response = self.ecr_core.parse_response_message(response_bytes)

                # For backward compatibility, don't modify existing QR data parsing
                # QR data should already be properly formatted from the original parsing

                status_info["response"] = parsed_response

                # Update the transaction with the parsed response for future use
                self.config.update_transaction(trx_id, {"response": parsed_response})
                logger.info(f"Parsed and cached response for transaction {trx_id}")

            except Exception as parse_error:
                logger.error(
                    f"Failed to parse raw response for transaction {trx_id}: {parse_error}"
                )
                # Create a basic response object to show the raw data
                basic_response = {
                    "raw_hex": raw_response_hex,
                    "parse_error": str(parse_error),
                    "message": "Raw response received but parsing failed",
                    "responseCode": "PARSE_ERROR",
                }
                status_info["response"] = basic_response
                status_info["parse_error"] = str(parse_error)

        if "raw_response" in transaction:
            status_info["raw_response"] = transaction["raw_response"]

        if "error" in transaction:
            status_info["error"] = transaction["error"]

        if "note" in transaction:
            status_info["note"] = transaction["note"]

        return status_info


class ConnectionManager:
    """Manages connections for both serial and socket modes"""

    def __init__(
        self, serial_comm: SerialComm, socket_comm: SocketComm, config: EcrConfig
    ):
        self.serial_comm = serial_comm
        self.socket_comm = socket_comm
        self.config = config
        self.is_connected = False

    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status"""
        network_available = (
            check_network_connectivity() if self.config.is_socket_mode() else True
        )
        return {
            "connected": self.is_connected,
            "network_available": network_available,
            "auto_disconnect_on_offline": True,
        }

    def connect(self) -> Dict[str, Any]:
        """Connect to the appropriate communication method"""
        # Check network connectivity for socket connections
        if self.config.is_socket_mode() and not check_network_connectivity():
            raise ValueError("Cannot connect: Network is offline")

        try:
            if self.config.is_socket_mode():
                return self._connect_socket()
            else:
                return self._connect_serial()

        except Exception as e:
            self.is_connected = False
            raise

    def disconnect(self) -> Dict[str, Any]:
        """Disconnect from current connection"""
        disconnect_message = "Disconnected"

        if self.config.is_socket_mode():
            socket_config = self.config.get_socket_config()
            ip = socket_config.get("socket_ip", "127.0.0.1")
            port = socket_config.get("socket_port", "9001")
            disconnect_message = f"Disconnected from {ip}:{port}"
        else:
            # Stop serial communication
            self.serial_comm.disconnect()
            serial_config = self.config.get_serial_config()
            serial_port = serial_config.get("serial_port", "")
            disconnect_message = (
                f"Disconnected from {serial_port}"
                if serial_port
                else "Disconnected from serial port"
            )

        self.is_connected = False
        return {"connected": False, "message": disconnect_message}

    def _connect_socket(self) -> Dict[str, Any]:
        """Connect via socket communication"""
        socket_config = self.config.get_socket_config()
        self.socket_comm.update_config(socket_config)

        if self.socket_comm.connect():
            self.is_connected = True
            ip = socket_config.get("socket_ip", "127.0.0.1")
            port = socket_config.get("socket_port", "9001")
            return {
                "connected": True,
                "message": f"Successfully connected to {ip}:{port}",
            }
        else:
            raise ValueError("Socket connection failed")

    def _connect_serial(self) -> Dict[str, Any]:
        """Connect via serial communication - exactly like desktop"""
        serial_config = self.config.get_serial_config()
        serial_port = serial_config.get("serial_port", "")

        if not serial_port:
            raise ValueError("No serial port specified")

        # Update serial comm config
        self.serial_comm.update_config(serial_config)

        try:
            if self.serial_comm.connect(serial_port):
                self.is_connected = True
                return {
                    "connected": True,
                    "message": f"Successfully connected to {serial_port}",
                }
            else:
                raise ValueError(f"Failed to connect to {serial_port}")
        except Exception as e:
            raise ValueError(f"Failed to connect to {serial_port} - {str(e)}")

    def is_connection_active(self) -> bool:
        """Check if connection is active"""
        return self.is_connected
