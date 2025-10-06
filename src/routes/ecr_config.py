"""
ECR Configuration and Utilities Module
Handles settings management, logging configuration, and utility functions
"""

import json
import os
import sys
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EcrConfig:
    """ECR Configuration Management"""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.settings_file = os.path.join(base_dir, "settings.json")
        self.history_file = os.path.join(base_dir, "transaction_history.json")
        self.app_settings = {}
        self.transaction_history = {}
        self.ui_hidden_transactions = set()

        self._load_settings()
        self._load_transaction_history()

    def _load_settings(self):
        """Load application settings from JSON file"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    self.app_settings = json.load(f)
                logger.info(f"Settings loaded: {self.app_settings}")
            except Exception as e:
                logger.error(f"Error loading settings: {e}")
                self.app_settings = {}
        else:
            logger.info("No settings file found, using defaults")

    def _load_transaction_history(self):
        """Load transaction history from JSON file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    self.transaction_history = json.load(f)
                logger.info(
                    f"Transaction history loaded: {len(self.transaction_history)} transactions"
                )
            except Exception as e:
                logger.error(f"Error loading transaction history: {e}")
                self.transaction_history = {}
        else:
            logger.info("No existing transaction history file found")

    def get_settings(self) -> Dict[str, Any]:
        """Get current application settings"""
        return self.app_settings.copy()

    def update_settings(self, new_settings: Dict[str, Any]) -> bool:
        """Update application settings"""
        try:
            self.app_settings.update(new_settings)
            with open(self.settings_file, "w") as f:
                json.dump(self.app_settings, f, indent=2)
            logger.info(f"Settings updated: {new_settings}")
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a specific setting value"""
        return self.app_settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> bool:
        """Set a specific setting value"""
        return self.update_settings({key: value})

    def get_transaction_history(self) -> Dict[str, Any]:
        """Get transaction history"""
        return self.transaction_history.copy()

    def add_transaction(self, trx_id: str, transaction_data: Dict[str, Any], user_id: Optional[int] = None) -> bool:
        """Add a transaction to history"""
        try:
            # Add user_id to transaction data if provided
            if user_id is not None:
                transaction_data['user_id'] = user_id
            self.transaction_history[trx_id] = transaction_data
            self.save_transaction_history()
            return True
        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            return False

    def update_transaction(self, trx_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing transaction"""
        try:
            if trx_id in self.transaction_history:
                self.transaction_history[trx_id].update(updates)
                self.save_transaction_history()
                return True
            else:
                logger.error(f"Transaction {trx_id} not found")
                return False
        except Exception as e:
            logger.error(f"Error updating transaction: {e}")
            return False

    def get_transaction(self, trx_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific transaction"""
        return self.transaction_history.get(trx_id)

    def save_transaction_history(self) -> bool:
        """Save transaction history to JSON file"""
        try:
            with open(self.history_file, "w") as f:
                json.dump(self.transaction_history, f, indent=2)
            logger.debug("Transaction history saved to file")
            return True
        except Exception as e:
            logger.error(f"Error saving transaction history: {e}")
            return False

    def clear_ui_transaction_history(self, user_id: Optional[int] = None):
        """Clear transaction history from UI display only"""
        if user_id is not None:
            # Only hide transactions belonging to this user
            user_transactions = [trx_id for trx_id, data in self.transaction_history.items()
                               if data.get('user_id') == user_id]
            self.ui_hidden_transactions.update(user_transactions)
            logger.info(
                f"Transaction history cleared from UI for user {user_id} ({len(user_transactions)} transactions hidden)"
            )
        else:
            # Hide all transactions (backward compatibility)
            self.ui_hidden_transactions.update(self.transaction_history.keys())
            logger.info(
                f"Transaction history cleared from UI ({len(self.transaction_history)} transactions hidden)"
            )

    def get_visible_transaction_history(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get transaction history visible to UI"""
        visible = {}
        for trx_id, data in self.transaction_history.items():
            if trx_id not in self.ui_hidden_transactions:
                # Filter by user_id if provided
                if user_id is not None:
                    if data.get('user_id') == user_id:
                        visible[trx_id] = data
                else:
                    # Return all visible transactions (backward compatibility)
                    visible[trx_id] = data
        return visible

    def get_communication_mode(self) -> str:
        """Get current communication mode"""
        return self.app_settings.get("communication", "Socket")

    def is_serial_mode(self) -> bool:
        """Check if in serial communication mode"""
        return self.get_communication_mode() == "Serial"

    def is_socket_mode(self) -> bool:
        """Check if in socket communication mode"""
        return self.get_communication_mode() == "Socket"

    def get_serial_config(self) -> Dict[str, Any]:
        """Get serial port configuration"""
        return {
            "serial_port": self.app_settings.get("serial_port", ""),
            "speed_baud": self.app_settings.get("speed_baud", 9600),
            "data_bits": self.app_settings.get("data_bits", 8),
            "stop_bits": self.app_settings.get("stop_bits", "1"),
            "parity": self.app_settings.get("parity", "N"),
        }

    def get_socket_config(self) -> Dict[str, Any]:
        """Get socket connection configuration"""
        return {
            "socket_ip": self.app_settings.get("socket_ip", "127.0.0.1"),
            "socket_port": self.app_settings.get("socket_port", "9001"),
            "enable_ssl": self.app_settings.get("enable_ssl", False),
            "enable_rest_api": self.app_settings.get("enable_rest_api", False),
            "edc_serial_number": self.app_settings.get(
                "edc_serial_number", "V1E1012320"
            ),
        }


class EcrUtils:
    """ECR Utility Functions"""

    @staticmethod
    def get_executable_dir() -> str:
        """Get the directory where the executable or script is located"""
        if getattr(sys, "frozen", False):
            # PyInstaller executable
            return os.path.dirname(sys.executable)
        else:
            # Development mode - use the project root
            return os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )

    @staticmethod
    def setup_logging(log_file_path: str, level: int = logging.DEBUG):
        """Setup logging configuration"""
        # Ensure the directory exists
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

        logging.basicConfig(
            filename=log_file_path,
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Also log the paths for debugging
        logger.info(f"Log file path: {log_file_path}")

    @staticmethod
    def get_transaction_name_from_code(trans_code: str) -> str:
        """Convert transaction code to human-readable name - BRI FMS v3.3"""
        code_to_name_map = {
            "01": "SALE",
            "02": "INSTALLMENT",
            "03": "VOID",
            "04": "GENERATE QR",
            "05": "QRIS STATUS TRANSAKSI",
            "06": "QRIS REFUND",
            "07": "INFO SALDO BRIZZI",
            "08": "PEMBAYARAN BRIZZI",
            "09": "TOPUP BRIZZI TERTUNDA",
            "0A": "TOPUP BRIZZI ONLINE",
            "0B": "UPDATE SALDO TERTUNDA BRIZZI",
            "0C": "VOID BRIZZI",
            "0D": "FARE NON-FARE",
            "0E": "CONTACTLESS",
            "0F": "SALE TIP",
            "10": "KEY IN",
            "11": "LOGON",
            "12": "SETTLEMENT",
            "13": "SETTLEMENT BRIZZI",
            "14": "REPRINT TRANSAKSI TERAKHIR",
            "15": "REPRINT TRANSAKSI",
            "16": "DETAIL REPORT",
            "17": "SUMMARY REPORT",
            "18": "REPRINT BRIZZI TRANSAKSI TERAKHIR",
            "19": "REPRINT BRIZZI TRANSAKSI",
            "1A": "BRIZZI DETAIL REPORT",
            "1B": "BRIZZI SUMMARY REPORT",
            "1C": "QRIS DETAIL REPORT",
            "1D": "QRIS SUMMARY REPORT",
            "1E": "INFO KARTU BRIZZI",
        }
        return code_to_name_map.get(trans_code.upper(), trans_code)

    @staticmethod
    def get_transaction_type_mapping() -> Dict[str, str]:
        """Get mapping of transaction names to codes - BRI FMS v3.3"""
        return {
            "SALE": "01",
            "INSTALLMENT": "02",
            "VOID": "03",
            "GENERATE QR": "04",
            "QRIS STATUS TRANSAKSI": "05",
            "QRIS REFUND": "06",
            "INFO SALDO BRIZZI": "07",
            "PEMBAYARAN BRIZZI": "08",
            "TOPUP BRIZZI TERTUNDA": "09",
            "TOPUP BRIZZI ONLINE": "0A",
            "UPDATE SALDO TERTUNDA BRIZZI": "0B",
            "VOID BRIZZI": "0C",
            "FARE NON-FARE": "0D",
            "CONTACTLESS": "0E",
            "SALE TIP": "0F",
            "KEY IN": "10",
            "LOGON": "11",
            "SETTLEMENT": "12",
            "SETTLEMENT BRIZZI": "13",
            "REPRINT TRANSAKSI TERAKHIR": "14",
            "REPRINT TRANSAKSI": "15",
            "DETAIL REPORT": "16",
            "SUMMARY REPORT": "17",
            "REPRINT BRIZZI TRANSAKSI TERAKHIR": "18",
            "REPRINT BRIZZI TRANSAKSI": "19",
            "BRIZZI DETAIL REPORT": "1A",
            "BRIZZI SUMMARY REPORT": "1B",
            "QRIS DETAIL REPORT": "1C",
            "QRIS SUMMARY REPORT": "1D",
            "INFO KARTU BRIZZI": "1E",
        }

    @staticmethod
    def parse_response_datetime(response_data: Dict[str, Any]) -> Optional[str]:
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
            dt = datetime(year, month, day, hour, minute, second)
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        except (ValueError, TypeError):
            return None

    @staticmethod
    def format_transaction_for_history(
        trx_id: str, transaction_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format transaction data for history display"""
        request_data = transaction_data.get("request", {})
        response_data = transaction_data.get("response", {})

        # Get transaction type name
        trans_type = request_data.get("transType", "")
        # BRI FMS v3.3 supports 0x01 to 0x1E
        if trans_type.upper() in [f"{i:02X}" for i in range(1, 31)]:
            trans_type = EcrUtils.get_transaction_name_from_code(trans_type)

        # Get invoice number from response first, then fall back to request
        invoice_no = ""
        if response_data.get("invoiceNo"):
            invoice_no = response_data["invoiceNo"]
        elif request_data.get("invoiceNo"):
            invoice_no = request_data["invoiceNo"]

        # Get trace number from response - should not fall back to invoice number
        trace_no = ""
        if response_data.get("traceNo"):
            trace_no = response_data["traceNo"]

        # Use response datetime if available, otherwise fall back to original timestamp
        display_timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(transaction_data.get("timestamp", time.time())),
        )
        if response_data:
            parsed_datetime = EcrUtils.parse_response_datetime(response_data)
            if parsed_datetime:
                display_timestamp = parsed_datetime

        history_item = {
            "id": trx_id,
            "transaction_id": trx_id,
            "timestamp": display_timestamp,
            "transaction_type": trans_type,
            "amount": request_data.get("amount", ""),
            "status": transaction_data.get("status", "unknown"),
            "invoice_no": invoice_no,
            "trace_no": trace_no,
        }

        if response_data:
            history_item["response"] = response_data
            # Include QR code if available in response
            if response_data.get("qrCode"):
                history_item["qr_code"] = response_data["qrCode"]

        if "error" in transaction_data:
            history_item["error"] = transaction_data["error"]

        return history_item

    @staticmethod
    def build_human_readable_request(
        transaction_type: str, amount: str, invoice_no: str, card_no: str = "", add_amount: str = "0"
    ) -> str:
        """Build human-readable request format"""
        human_readable_request = f"Transaction Type: {transaction_type}"

        # Only show amount for transactions that need it
        # Transactions that don't require amount: VOID, INFO SALDO, SETTLEMENT, REPRINT, REPORT, LOGON
        if transaction_type.upper() not in [
            "VOID",
            "INFO SALDO BRIZZI",
            "VOID BRIZZI",
            "LOGON",
            "SETTLEMENT",
            "SETTLEMENT BRIZZI",
            "REPRINT TRANSAKSI TERAKHIR",
            "REPRINT TRANSAKSI",
            "DETAIL REPORT",
            "SUMMARY REPORT",
            "REPRINT BRIZZI TRANSAKSI TERAKHIR",
            "REPRINT BRIZZI TRANSAKSI",
            "BRIZZI DETAIL REPORT",
            "BRIZZI SUMMARY REPORT",
            "QRIS DETAIL REPORT",
            "QRIS SUMMARY REPORT",
            "INFO KARTU BRIZZI",
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
            if transaction_type.upper() in ["VOID", "VOID BRIZZI"]:
                human_readable_request += f"\nTrace Number: {invoice_no.strip()}"
            elif transaction_type.upper() == "QRIS STATUS TRANSAKSI":
                human_readable_request += f"\nReference ID: {invoice_no.strip()}"
            else:
                human_readable_request += f"\nInvoice Number: {invoice_no.strip()}"

        # Add additional amount (tip/non-fare) if provided for applicable transaction types
        if add_amount and add_amount != "0":
            try:
                add_amount_float = float(add_amount.replace(",", ""))
                if add_amount_float > 0:
                    if transaction_type.upper() in ["SALE TIP", "GENERATE QR"]:
                        human_readable_request += f"\nTip Amount: {add_amount_float:,.0f}"
                    elif transaction_type.upper() == "FARE NON-FARE":
                        human_readable_request += f"\nNon-Fare Amount: {add_amount_float:,.0f}"
                    else:
                        human_readable_request += f"\nAdditional Amount: {add_amount_float:,.0f}"
            except (ValueError, TypeError):
                pass

        # Add card number if provided
        if card_no and card_no.strip():
            human_readable_request += f"\nCard Number: {card_no.strip()}"

        return human_readable_request

    @staticmethod
    def validate_daily_password(provided_password: str) -> bool:
        """Validate password based on today's date (ddmmyyyy format)"""
        today = datetime.now()
        expected_password = today.strftime("%d%m%Y")
        return provided_password == expected_password

    @staticmethod
    def generate_transaction_id() -> str:
        """Generate a unique transaction ID"""
        import uuid

        return uuid.uuid4().hex[:8].upper()

    @staticmethod
    def get_entry_mode_description(entry_mode: str) -> str:
        """Get entry mode description - BRI FMS v3.3 spec"""
        entry_mode_map = {
            "D": "Dip (EMV Chip)",
            "S": "Swipe (Magnetic Stripe)",
            "F": "Fallback",
            "M": "Manual (Key In)",
            "T": "Tap (Contactless)",
            "`": "QRIS MPM",  # 0x60
        }
        return entry_mode_map.get(entry_mode.upper(), entry_mode)

    @staticmethod
    def check_transaction_success(response_dict: Dict[str, Any]) -> Dict[str, Any]:
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
