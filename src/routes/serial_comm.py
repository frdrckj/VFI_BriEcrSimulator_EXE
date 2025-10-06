"""
Serial Communication Module
Handles serial port operations, listeners, and serial-specific functionality
"""

import ctypes
import binascii
import logging
import threading
import time
import serial
import serial.tools.list_ports
from typing import Optional, Callable, Dict, Any
from .ecr_core import SerialData

logger = logging.getLogger(__name__)


class SerialCommListener:
    """Serial communication listener - handles incoming serial data via PySerial"""

    def __init__(self, serial_connection, callback: Optional[Callable] = None):
        self.serial_connection = serial_connection
        self.callback = callback
        self.is_listening = False
        self.show_data = False
        self.listener_thread = None
        self.last_activity_time = time.time()
        self.connection_lost = False

        # QR data collection state
        self.collecting_qr_data = False
        self.qr_data_bytes = b""
        self.pending_response_data = None
        self.qr_collection_start_time = 0

    def start_listener(self):
        """Start serial listener thread (non-daemon like desktop version)"""
        if self.is_listening:
            logger.warning("Listener already running, skipping start")
            return
        self.is_listening = True
        self.connection_lost = False
        # Use regular thread instead of daemon thread (like desktop version)
        self.listener_thread = threading.Thread(target=self._listener_loop)
        self.listener_thread.start()
        logger.info("Serial listener thread started (non-daemon)")

        # Give thread time to start and log initial messages
        time.sleep(0.2)

        # Check if thread is actually alive
        if self.listener_thread.is_alive():
            logger.info("Listener thread confirmed alive")
        else:
            logger.error("CRITICAL: Listener thread died immediately after start!")

    def stop_listener(self):
        """Stop serial listener thread"""
        self.is_listening = False
        if self.listener_thread:
            self.listener_thread.join(timeout=2)
        logger.info("Serial listener thread stopped")

    def set_show_data(self, show: bool):
        """Control whether to show response data"""
        self.show_data = show

    def _listener_loop(self):
        """Main listener loop - blocking reads like desktop version"""
        logger.info("Serial listener loop started - using blocking reads like desktop")

        # Use shorter timeout for more responsive reading
        original_timeout = self.serial_connection.timeout
        self.serial_connection.timeout = 0.1  # 100ms timeout for responsive polling

        logger.info(f"Listener using serial port: {self.serial_connection.port}, timeout: {self.serial_connection.timeout}s")

        loop_count = 0
        while self.is_listening:
            try:
                # Log heartbeat every 50 iterations (~5 seconds at 0.1s timeout)
                loop_count += 1
                if loop_count % 50 == 0:
                    logger.debug(f"Listener heartbeat - loop count: {loop_count}")
                if not self.serial_connection or not self.serial_connection.is_open:
                    logger.error("Serial connection not available, attempting to recover...")
                    self.connection_lost = True
                    if self.callback:
                        self.callback("CONNECTION_LOST", None)
                    break

                # Use blocking read (like desktop's recvSerialPort)
                # This will block up to timeout waiting for data
                first_byte = self.serial_connection.read(1)

                if len(first_byte) == 1:
                    # Check if there's more data available immediately
                    if self.serial_connection.in_waiting > 0:
                        logger.info(f"Additional {self.serial_connection.in_waiting} bytes waiting in buffer")
                    logger.info(f"Received byte: 0x{first_byte[0]:02X}")
                    self.last_activity_time = time.time()
                    if first_byte[0] == 0x06:  # ACK
                        self._handle_ack_nak(first_byte[0])
                        continue
                    elif first_byte[0] == 0x15:  # NAK
                        self._handle_ack_nak(first_byte[0])
                        continue
                    elif first_byte[0] == 0x02:  # STX - start of response
                        logger.info("Received STX - reading full response...")
                        self._read_full_message(first_byte)
                    else:
                        logger.warning(f"Received unexpected byte: 0x{first_byte[0]:02X}")
                        # Check if we're receiving QR data after a response
                        if self.show_data:
                            # We're in QR data collection mode - collect bytes until ETX+LRC
                            self._collect_qr_data(first_byte[0])
                else:
                    # No data received within timeout (like desktop's behavior)
                    # This is normal - just continue waiting
                    pass  # Don't log every timeout, too verbose

                # Check for QR collection timeout
                if (
                    self.collecting_qr_data
                    and time.time() - self.qr_collection_start_time > 3.0
                ):
                    logger.info(
                        "QR data collection timeout, sending response without QR data"
                    )
                    self._send_response_without_qr()

            except serial.SerialException as e:
                logger.error(f"Serial port error: {str(e)}")
                self.connection_lost = True
                if self.callback:
                    self.callback("CONNECTION_LOST", {"error": str(e)})
                break
            except Exception as e:
                logger.error(f"Serial listener error: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Don't break on general errors - try to continue
                time.sleep(0.1)
                continue

        # Restore original timeout
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.timeout = original_timeout

        logger.info("Serial listener loop ended")


    def _handle_ack_nak(self, byte_value: int):
        """Handle single-byte ACK/NAK responses"""
        if not self.show_data:
            if byte_value == 0x06:
                logger.info("Received ACK")
                if self.callback:
                    self.callback("ACK", None)
            elif byte_value == 0x15:
                logger.info("Received NACK")
                if self.callback:
                    self.callback("NACK", None)
            else:
                logger.info(f"Received UNKNOWN response: {byte_value:02X}")
                if self.callback:
                    self.callback("UNKNOWN", None)
        else:
            # If show_data is True, we're already processing a response
            # These additional bytes might be the unknown bytes after ETX+LRC
            logger.info(f"Received additional byte after response: {byte_value:02X}")
            # Don't process individual bytes when we're already showing response data

    def _read_full_message(self, stx_byte: bytes):
        """Read a complete message starting with STX from PySerial"""
        try:
            response_data = stx_byte  # Start with STX

            logger.info("Reading length field (2 bytes)...")

            # Read length field (2 bytes in hex format)
            length_bytes = self.serial_connection.read(2)
            logger.info(f"Read {len(length_bytes)} length bytes: {binascii.hexlify(length_bytes).decode() if length_bytes else 'NONE'}")
            if len(length_bytes) == 2:
                response_data += length_bytes
                # Length is 2 bytes in big-endian format
                msg_len = (length_bytes[0] << 8) | length_bytes[1]
                logger.info(f"Message length: {msg_len} bytes (from {binascii.hexlify(length_bytes).decode()})")

                # Read all message data + ETX + LRC
                logger.info(f"Waiting for {msg_len + 2} bytes (message + ETX + LRC)...")
                remaining = self.serial_connection.read(msg_len + 2)
                response_data += remaining
                logger.info(f"Received {len(remaining)} bytes")

                # Check if the message ends with ETX (0x03) + LRC pattern
                if len(remaining) >= 2:
                    etx_position = len(remaining) - 2
                    etx_byte = remaining[etx_position]
                    lrc_byte = remaining[etx_position + 1]

                    logger.info(
                        f"Last two bytes: ETX={etx_byte:02X}, LRC={lrc_byte:02X}"
                    )

                    if etx_byte == 0x03:  # ETX found
                        logger.info(
                            f"ETX found at position {etx_position} - complete response received"
                        )

                        # According to BRI FMS v3.3 spec, response is exactly:
                        # STX + Length + 300 bytes data + ETX + LRC = 305 bytes total
                        # No additional QR data is sent separately
                        self._handle_full_response_with_etx(response_data, b"")

                        # Stop listening after receiving complete response with ETX
                        logger.info("Complete response received - stopping listener")
                        self.is_listening = False
                        return

                # Regular response handling
                logger.info("No ETX found, treating as regular response")
                self._handle_full_response(response_data)

        except Exception as e:
            logger.error(f"Error reading full message: {str(e)}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")

    def _handle_full_response(self, response_data: bytes):
        """Handle full response messages"""
        logger.info(
            f"Received full response: {binascii.hexlify(response_data).decode()}"
        )

        try:
            # Mark that we're now showing data
            self.show_data = True

            # Store raw response as hex string
            raw_response_hex = binascii.hexlify(response_data).decode().upper()

            # Don't call callback immediately - wait for potential QR data collection
            logger.info("Response received, waiting for potential QR data collection")

            if not self.callback:
                logger.warning("No callback set for response handling")

        except Exception as e:
            logger.error(f"Error processing full response: {str(e)}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
        finally:
            # Start QR data collection mode for QRIS transactions
            # Don't reset show_data - keep it True to collect QR bytes
            self.collecting_qr_data = True
            self.qr_data_bytes = b""
            self.qr_collection_start_time = time.time()
            self.pending_response_data = {
                "raw_response": raw_response_hex,
                "response_bytes": response_data,
            }

    def _handle_full_response_with_etx(
        self, response_data: bytes, unknown_bytes: bytes
    ):
        """Handle full response messages when ETX+LRC detected"""
        response_hex = binascii.hexlify(response_data).decode()
        unknown_hex = binascii.hexlify(unknown_bytes).decode() if unknown_bytes else ""

        logger.info(f"Received response with ETX+LRC: {response_hex}")
        if unknown_bytes:
            logger.info(f"Plus {len(unknown_bytes)} unknown bytes: {unknown_hex}")

        try:
            # Mark that we're now showing data
            self.show_data = True

            # Store raw response as hex string including unknown bytes
            raw_response_hex = (response_hex + unknown_hex).upper()

            logger.info(
                f"About to call callback with RAW_RESPONSE, callback is: {self.callback is not None}"
            )
            if self.callback:
                logger.info("Calling callback with RAW_RESPONSE type")
                self.callback(
                    "RAW_RESPONSE",
                    {
                        "raw_response": raw_response_hex,
                        "response_bytes": response_data,
                        "unknown_bytes": unknown_bytes,
                        "etx_detected": True,
                    },
                )
                logger.info("ETX callback completed successfully")
            else:
                logger.warning("No callback set for ETX response handling")

        except Exception as e:
            logger.error(f"Error processing ETX response: {str(e)}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
        finally:
            # Reset show_data flag after processing
            self.show_data = False

    def _collect_qr_data(self, byte_val: int):
        """Collect QR data bytes that come after the main response"""
        if not self.collecting_qr_data:
            return

        # Check if this is ETX (0x03) indicating end of QR data
        if byte_val == 0x03:
            # Next byte should be LRC
            try:
                lrc_byte = self.serial_connection.read(1)
                if len(lrc_byte) == 1:
                    logger.info(
                        f"QR data collection ended: ETX (03) + LRC ({lrc_byte[0]:02X})"
                    )
                    logger.info(f"Collected {len(self.qr_data_bytes)} QR data bytes")

                    # Process the collected QR data
                    self._process_collected_qr_data()
                    return
            except Exception as e:
                logger.error(f"Error reading LRC after ETX: {e}")

        # Regular QR data byte
        self.qr_data_bytes += bytes([byte_val])
        # logger.info(f"Collected QR data byte: {byte_val:02X}")

    def _process_collected_qr_data(self):
        """Process the collected QR data and send complete response"""
        try:
            # Decode QR data as ASCII
            qr_string = self.qr_data_bytes.decode("ascii", errors="ignore").strip()
            logger.info(f"Decoded QR string: {qr_string[:50]}...")

            # Add QR data to pending response
            if self.pending_response_data and qr_string:
                self.pending_response_data["unknown_bytes"] = self.qr_data_bytes

                # Now send the complete response with QR data
                if self.callback:
                    logger.info("Sending complete response with QR data")
                    self.callback("RESPONSE", self.pending_response_data)

        except Exception as e:
            logger.error(f"Error processing QR data: {e}")
        finally:
            # Reset collection state
            self.collecting_qr_data = False
            self.qr_data_bytes = b""
            self.pending_response_data = None
            self.show_data = False

    def _send_response_without_qr(self):
        """Send response when no QR data is collected within timeout"""
        try:
            if self.pending_response_data and self.callback:
                logger.info("Sending response without QR data (timeout)")
                self.callback("RESPONSE", self.pending_response_data)
        except Exception as e:
            logger.error(f"Error sending response without QR: {e}")
        finally:
            # Reset collection state
            self.collecting_qr_data = False
            self.qr_data_bytes = b""
            self.pending_response_data = None
            self.show_data = False


# PySerial fallback removed - using native library only like desktop version


class SerialComm:
    """Main serial communication class - PySerial for COM port, native library for message packing"""

    def __init__(self, ecr_core):
        self.ecr_core = ecr_core
        self.serial_config = {}
        self.is_connected = False
        self.serial_connection = None
        self.serial_port = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3

        # PySerial listener for ECR responses
        self.native_listener = None
        # Store callback to set on listener when it's created
        self.pending_callback = None

    def update_config(self, config: Dict[str, Any]):
        """Update serial configuration"""
        self.serial_config = config

    def test_connection(self, serial_port: str) -> bool:
        """Test serial port connection using PySerial"""
        if not serial_port:
            raise ValueError("No serial port specified")

        try:
            self.serial_port = serial_port  # Store for reconnection

            # Use PySerial to open and manage COM port (like CIMB)
            self.serial_connection = serial.Serial(
                port=serial_port,
                baudrate=int(self.serial_config.get("speed_baud", 9600)),
                bytesize=int(self.serial_config.get("data_bits", 8)),
                stopbits=int(self.serial_config.get("stop_bits", 1)),
                parity=self.serial_config.get("parity", "N")[0].upper(),
                timeout=10.0,  # 10 second timeout for blocking reads
                write_timeout=2.0,
                inter_byte_timeout=None,
            )

            # Clear any existing data in buffers
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()

            # Start PySerial listener for ECR communication
            self._start_native_listener()

            self.is_connected = True
            self.reconnect_attempts = 0  # Reset on successful connection
            logger.info(f"Serial port {serial_port} opened successfully using PySerial")
            return True

        except Exception as e:
            logger.error(f"Failed to open serial port {serial_port}: {e}")
            raise ValueError(f"Failed to open serial port {serial_port} - {str(e)}")

    def connect(self, serial_port: str) -> bool:
        """Connect to serial port"""
        return self.test_connection(serial_port)

    def disconnect(self):
        """Disconnect from serial port - close PySerial connection"""
        self._stop_all_listeners()

        if self.serial_connection:
            try:
                self.serial_connection.close()
                self.serial_connection = None
                logger.info("Serial port closed")
            except Exception as e:
                logger.error(f"Error closing serial port: {e}")

        self.is_connected = False

    def send_message(self, message: bytes) -> bool:
        """Send message via PySerial connection"""
        if not self.serial_connection:
            raise ValueError("Serial port not connected")

        # Check if listener is alive before sending
        if not self.is_listener_alive():
            logger.warning("Listener not alive, restarting...")
            self._start_native_listener()

        try:
            logger.info(
                f"Sending message via PySerial: {binascii.hexlify(message).decode()}"
            )

            # Clear input buffer before sending to avoid old data
            self.serial_connection.reset_input_buffer()

            # Send the message
            bytes_written = self.serial_connection.write(message)
            self.serial_connection.flush()

            logger.info(f"Wrote {bytes_written} of {len(message)} bytes to serial port")

            if bytes_written != len(message):
                logger.warning(f"Only wrote {bytes_written} of {len(message)} bytes")

            # Set show_data to false for listener
            if self.native_listener:
                self.native_listener.set_show_data(False)
                self.native_listener.last_activity_time = time.time()

            return True

        except serial.SerialTimeoutException as e:
            logger.error(f"Serial write timeout: {str(e)}")
            self._handle_connection_lost()
            raise
        except Exception as e:
            logger.error(f"PySerial send error: {str(e)}")
            raise

    def set_response_callback(self, callback: Callable):
        """Set callback for handling responses"""
        # Wrap the callback to handle connection lost events
        def enhanced_callback(response_type, data):
            if response_type == "CONNECTION_LOST":
                logger.warning("Connection lost detected, attempting to reconnect...")
                self._handle_connection_lost()
            else:
                callback(response_type, data)

        self.pending_callback = enhanced_callback
        if self.native_listener:
            self.native_listener.callback = enhanced_callback
            logger.info("Callback set on existing listener")
        else:
            logger.info("Callback stored as pending - will be set when listener is created")

    def _start_native_listener(self):
        """Start PySerial listener for ECR responses (like CIMB)"""
        if not self.native_listener and self.serial_connection:
            self.native_listener = SerialCommListener(self.serial_connection)
            # Set pending callback if we have one
            if self.pending_callback:
                self.native_listener.callback = self.pending_callback
                logger.info("Applied pending callback to new listener")
        if self.native_listener:
            self.native_listener.start_listener()
            logger.info("PySerial listener started for ECR responses")

    def _stop_all_listeners(self):
        """Stop PySerial listener"""
        if self.native_listener:
            self.native_listener.stop_listener()
            self.native_listener = None

    def _handle_connection_lost(self):
        """Handle connection lost event - attempt to reconnect"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            self.is_connected = False
            return

        self.reconnect_attempts += 1
        logger.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")

        try:
            # Close current connection
            if self.serial_connection:
                try:
                    self.serial_connection.close()
                except:
                    pass

            # Wait a bit before reconnecting
            time.sleep(2)

            # Try to reconnect
            if self.serial_port:
                self.test_connection(self.serial_port)
                logger.info("Reconnection successful")
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            # Try again if we haven't reached max attempts
            if self.reconnect_attempts < self.max_reconnect_attempts:
                threading.Timer(5.0, self._handle_connection_lost).start()

    def is_listener_alive(self) -> bool:
        """Check if the listener thread is alive and running"""
        return (
            self.native_listener is not None
            and self.native_listener.listener_thread is not None
            and self.native_listener.listener_thread.is_alive()
            and not self.native_listener.connection_lost
        )


def get_available_ports():
    """Get list of available serial ports using PySerial"""
    ports = []
    try:
        for port in serial.tools.list_ports.comports():
            ports.append(
                {
                    "device": port.device,
                    "description": port.description or "Unknown",
                    "hwid": port.hwid or "Unknown",
                }
            )
    except Exception as e:
        logger.error(f"Error listing serial ports: {e}")
    return ports
