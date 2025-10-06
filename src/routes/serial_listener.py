import threading
import time
import binascii
import logging
from .serial_callback import SerialCallback

logger = logging.getLogger("ecr.serial")


class SerialListener:
    """Serial listener implementation matching desktop SerialListener.java pattern"""
    
    def __init__(self, ecr_library, callback=None):
        self.show_data = False
        self.do_stop = False
        self.callback = callback
        self.ecr_library = ecr_library
        self.thread = None
        
    def do_show_data(self, status):
        """Set show_data flag - synchronized in desktop"""
        self.show_data = status
        
    def is_show_data(self):
        """Check if show_data is True - synchronized in desktop"""
        return self.show_data
        
    def do_stop(self):
        """Signal the listener to stop - synchronized in desktop"""
        self.do_stop = True
        
    def keep_running(self):
        """Check if the listener should keep running - synchronized in desktop"""
        return not self.do_stop
        
    def start_listening(self):
        """Start the serial listener thread"""
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            logger.info("Serial listener thread started")
        
    def run(self):
        """Main listener loop - matches desktop SerialListener.run() method"""
        from .ecr import transaction_history, save_transaction_history
        
        logger.info("Serial listener loop started - polling for responses like desktop")
        
        while self.keep_running():
            try:
                # Poll for data exactly like desktop SerialListener.run() line 36
                # Increased buffer size to handle any length response
                recv_buf = bytearray(65536)  # 64KB buffer to handle large responses
                byte_len = self.ecr_library.ecrRecvSerialPort(recv_buf, 65536)

                if byte_len > 0:
                    if byte_len == 1:
                        # Single byte response - ACK/NAK like desktop lines 38-48
                        recv_data = bytes(recv_buf[:byte_len])
                        if not self.is_show_data():
                            if recv_data[0] == 0x06:
                                logger.info("Received ACK - waiting for full response...")
                                # Continue waiting for the actual response - don't stop here
                                # In desktop this would update textAreaRsp.setText("ACK")
                            elif recv_data[0] == 0x15:
                                logger.info("Received NACK")
                                # In desktop this would update textAreaRsp.setText("NACK")
                            else:
                                logger.info("Received UNKNOWN response")
                                # In desktop this would update textAreaRsp.setText("UNKNOWN")
                    else:
                        # Multi-byte response - process like desktop lines 49-52
                        self.do_show_data(True)
                        
                        # Parse the response message
                        response_data = bytes(recv_buf[:byte_len])
                        logger.info(f"Received multi-byte response: {binascii.hexlify(response_data).decode()}")
                        
                        # Find processing transaction in history
                        processing_trxs = [
                            k for k, v in transaction_history.items()
                            if v["status"] == "processing"
                        ]
                        
                        if processing_trxs:
                            latest_trx = max(
                                processing_trxs,
                                key=lambda k: transaction_history[k]["timestamp"],
                            )
                            
                            # Parse response using message protocol
                            try:
                                parsed_response = self.parse_response(response_data)
                                transaction_history[latest_trx]["status"] = "completed"
                                transaction_history[latest_trx]["response"] = parsed_response
                                save_transaction_history()
                                logger.info(f"Updated transaction {latest_trx} with parsed response")
                            except Exception as e:
                                logger.error(f"Error parsing response: {str(e)}")
                                transaction_history[latest_trx]["status"] = "error"
                                transaction_history[latest_trx]["error"] = str(e)
                                save_transaction_history()
                        else:
                            logger.warning("Received response but no processing transaction")
                            
                        # Stop listening after receiving response and store raw response
                        # Store ONLY raw response without any parsing for serial
                        raw_response_hex = binascii.hexlify(response_data).decode().upper()
                        
                        # Update transaction history with raw response only
                        processing_trxs = [
                            k for k, v in transaction_history.items()
                            if v["status"] == "processing"
                        ]
                        
                        if processing_trxs:
                            latest_trx = max(
                                processing_trxs,
                                key=lambda k: transaction_history[k]["timestamp"],
                            )
                            
                            transaction_history[latest_trx]["status"] = "completed"
                            transaction_history[latest_trx]["raw_response"] = raw_response_hex
                            save_transaction_history()
                            logger.info(f"Updated transaction {latest_trx} with raw response")
                        else:
                            logger.warning("Received response but no processing transaction")
                        
                        # Stop listening immediately after receiving response
                        logger.info("Response received - stopping listener")
                        self.do_stop()
                        
                elif byte_len == -3:
                    logger.error("INVALID LENGTH")  # Like desktop line 57
                elif byte_len == -4:
                    logger.error("INVALID LRC")     # Like desktop line 59
                elif byte_len < 0:
                    logger.error("Serial error, stopping listener")  # Like desktop lines 60-65
                    self.do_stop()
                    if self.callback and hasattr(self.callback, 'on_socket_closed'):
                        self.callback.on_socket_closed()
                    break
                else:
                    # No data, sleep like desktop line 67
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Serial listener error: {str(e)}")
                # Like desktop lines 69-71
                break
                
        logger.info("Serial listener loop ended")
        
    def parse_response(self, response_bytes):
        """Parse response message similar to desktop CimbMessage.parseResponse()"""
        from .ecr import parse_response_msg
        return parse_response_msg(response_bytes)