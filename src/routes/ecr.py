"""
ECR Simulator Main Module - Refactored with Modular Architecture
Clean separation of concerns with dedicated modules for different functionalities
"""

import logging
import os
import time
from flask import Blueprint, request, jsonify, send_file, session

# Import our modular components
from .ecr_core import EcrCore
from .serial_comm import SerialComm, get_available_ports
from .socket_comm import SocketComm
from .ecr_config import EcrConfig, EcrUtils
from .message_protocol import TransactionProcessor, ConnectionManager

# Create blueprint
ecr_bp = Blueprint("ecr", __name__)

# Setup logging
BASE_DIR = os.path.dirname(__file__)
EXECUTABLE_DIR = EcrUtils.get_executable_dir()
LOG_FILE_PATH = os.path.join(EXECUTABLE_DIR, "ecr_simulator.log")

# Setup logging
EcrUtils.setup_logging(LOG_FILE_PATH)
logger = logging.getLogger(__name__)

# Log initialization paths
logger.info(f"Executable directory: {EXECUTABLE_DIR}")
logger.info(f"Log file path: {LOG_FILE_PATH}")

# Initialize modular components
config = EcrConfig(BASE_DIR)
ecr_core = EcrCore(BASE_DIR)
serial_comm = SerialComm(ecr_core)
socket_comm = SocketComm(ecr_core)  # Pass ecr_core for native socket support
transaction_processor = TransactionProcessor(ecr_core, serial_comm, socket_comm, config)
connection_manager = ConnectionManager(serial_comm, socket_comm, config)

logger.info("ECR Simulator modules initialized successfully")


# Flask route handlers
@ecr_bp.route("/settings", methods=["GET", "POST"])
def handle_settings():
    """Handle settings management"""
    if request.method == "GET":
        return jsonify(config.get_settings())

    data = request.get_json()
    if data:
        if config.update_settings(data):
            # Update communication modules with new config
            if config.is_serial_mode():
                serial_comm.update_config(config.get_serial_config())
            else:
                socket_comm.update_config(config.get_socket_config())

            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "Failed to update settings"}), 500

    return jsonify({"error": "No data"}), 400


@ecr_bp.route("/connection_status", methods=["GET"])
def get_connection_status():
    """Get current connection status"""
    return jsonify(connection_manager.get_connection_status())


@ecr_bp.route("/connect", methods=["POST"])
def handle_connection():
    """Handle connection/disconnection requests"""
    data = request.get_json()
    action = data.get("action", "connect")

    try:
        if action == "disconnect":
            result = connection_manager.disconnect()
            transaction_processor.update_connection_status(False)
            return jsonify(result)
        else:
            result = connection_manager.connect()
            transaction_processor.update_connection_status(True)
            return jsonify(result)

    except Exception as e:
        error_message = str(e)
        if config.is_socket_mode():
            socket_config = config.get_socket_config()
            ip = socket_config.get("socket_ip", "127.0.0.1")
            port = socket_config.get("socket_port", "9001")
            if socket_config.get("enable_rest_api", False):
                return (
                    jsonify({"error": f"REST API connection failed: {error_message}"}),
                    400,
                )
            else:
                return (
                    jsonify(
                        {"error": f"Failed to connect to {ip}:{port} - {error_message}"}
                    ),
                    400,
                )
        else:
            serial_config = config.get_serial_config()
            serial_port = serial_config.get("serial_port", "")
            return (
                jsonify(
                    {"error": f"Failed to connect to {serial_port} - {error_message}"}
                ),
                400,
            )


@ecr_bp.route("/build_request", methods=["POST"])
def build_request():
    """Build a human-readable transaction request"""
    try:
        data = request.get_json()
        transaction_type = data.get("transaction_type", "SALE")
        amount = data.get("amount", "0.00")
        invoice_no = data.get("invoiceNo", "")
        card_no = data.get("cardNo", "")
        add_amount = data.get("addAmount", "0")

        result = transaction_processor.build_request(
            transaction_type, amount, invoice_no, card_no, add_amount
        )
        return jsonify(result)

    except ValueError as e:
        logger.error(f"Build request error: {str(e)}")
        return jsonify({"error": str(e)}), 400


@ecr_bp.route("/process", methods=["POST"])
def process_transaction():
    """Process a transaction"""
    try:
        # Get current user's ID from session
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.get_json()
        transaction_type = data.get("transaction_type", "SALE")
        amount = data.get("amount", "0.00")
        invoice_no = data.get("invoiceNo", "")
        card_no = data.get("cardNo", "")
        add_amount = data.get("addAmount", "0")

        result = transaction_processor.process_transaction(
            transaction_type, amount, invoice_no, card_no, add_amount, user_id=user_id
        )
        return jsonify(result)

    except Exception as e:
        logger.error(f"Process transaction error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@ecr_bp.route("/transaction_status/<trx_id>", methods=["GET"])
def get_transaction_status(trx_id):
    """Get transaction status by ID"""
    try:
        status_info = transaction_processor.get_transaction_status(trx_id)
        return jsonify(status_info)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@ecr_bp.route("/history", methods=["GET"])
def get_history():
    """Get transaction history"""
    # Get current user's ID from session
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    history_list = []
    visible_history = config.get_visible_transaction_history(user_id=user_id)

    for trx_id, data in visible_history.items():
        history_item = EcrUtils.format_transaction_for_history(trx_id, data)
        history_list.append(history_item)

    # Sort by timestamp, most recent first
    history_list.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify(history_list)


@ecr_bp.route("/history", methods=["DELETE"])
def clear_history():
    """Clear transaction history from UI display"""
    # Get current user's ID from session
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    config.clear_ui_transaction_history(user_id=user_id)
    return jsonify(
        {"status": "success", "message": "Transaction history cleared from display"}
    )


@ecr_bp.route("/detect_serial", methods=["POST"])
def detect_serial():
    """Try to detect the correct EDC serial number"""
    try:
        if not config.get_setting("enable_rest_api", False):
            return jsonify({"error": "REST API mode not enabled"}), 400

        socket_comm.update_config(config.get_socket_config())
        result = socket_comm.auto_detect_serial_number()

        if result.get("status") == "success":
            # Update settings with working serial
            working_serial = result.get("working_serial")
            config.set_setting("edc_serial_number", working_serial)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Serial detection error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@ecr_bp.route("/serial_ports", methods=["GET"])
def get_serial_ports():
    """Get available serial ports"""
    try:
        ports = get_available_ports()
        return jsonify({"ports": ports})
    except Exception as e:
        logger.error(f"Error getting serial ports: {str(e)}")
        return jsonify({"error": str(e)}), 500


@ecr_bp.route("/download_log", methods=["GET"])
def download_log():
    """Download the ECR simulator log file"""
    try:
        from datetime import datetime

        # Check password parameter
        password = request.args.get("password", "")
        if not EcrUtils.validate_daily_password(password):
            return (
                jsonify(
                    {
                        "error": "Invalid password. Please use today's date in ddmmyyyy format."
                    }
                ),
                401,
            )

        # Create log file if it doesn't exist
        if not os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, "w") as f:
                f.write(
                    f"ECR Simulator Log - Created {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
            logger.info(f"Created new log file at: {LOG_FILE_PATH}")

        return send_file(
            LOG_FILE_PATH,
            as_attachment=True,
            download_name="ecr_simulator.log",
            mimetype="text/plain",
        )

    except Exception as e:
        logger.error(f"Download log error: {str(e)}")
        return jsonify({"error": f"Could not create/download log file: {str(e)}"}), 500


@ecr_bp.route("/download_history", methods=["GET"])
def download_history():
    """Download the transaction history JSON file"""
    try:
        from datetime import datetime
        import json
        import tempfile

        # Get current user's ID from session
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        # Check password parameter
        password = request.args.get("password", "")
        if not EcrUtils.validate_daily_password(password):
            return (
                jsonify(
                    {
                        "error": "Invalid password. Please use today's date in ddmmyyyy format."
                    }
                ),
                401,
            )

        # Get only current user's transactions
        all_history = config.get_transaction_history()
        user_history = {trx_id: data for trx_id, data in all_history.items()
                       if data.get('user_id') == user_id}

        # Create a temporary file with filtered history
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        json.dump(user_history, temp_file, indent=2)
        temp_file.close()

        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name="transaction_history.json",
            mimetype="application/json",
        )

    except Exception as e:
        logger.error(f"Download history error: {str(e)}")
        return (
            jsonify({"error": f"Could not create/download history file: {str(e)}"}),
            500,
        )


# Health check endpoint
@ecr_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "modules": {
                "ecr_core": ecr_core is not None,
                "serial_comm": serial_comm is not None,
                "socket_comm": socket_comm is not None,
                "config": config is not None,
                "transaction_processor": transaction_processor is not None,
                "connection_manager": connection_manager is not None,
            },
            "connection": {
                "active": connection_manager.is_connection_active(),
                "mode": config.get_communication_mode(),
            },
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


# Module information endpoint
@ecr_bp.route("/module_info", methods=["GET"])
def module_info():
    """Get information about loaded modules"""
    return jsonify(
        {
            "architecture": "modular",
            "modules": {
                "ecr_core": {
                    "description": "Core ECR functionality - library management and message processing",
                    "native_library": ecr_core.ecr_lib is not None,
                    "use_library": ecr_core.use_library,
                },
                "serial_comm": {
                    "description": "Serial communication handling",
                    "connected": serial_comm.is_connected,
                    "use_pyserial_fallback": serial_comm.use_pyserial_listener,
                },
                "socket_comm": {
                    "description": "Socket and REST API communication",
                    "connected": socket_comm.is_connected,
                },
                "config": {
                    "description": "Configuration and settings management",
                    "settings_loaded": bool(config.app_settings),
                    "history_entries": len(config.transaction_history),
                },
                "message_protocol": {
                    "description": "Transaction processing and protocol handling",
                    "connection_active": connection_manager.is_connection_active(),
                },
            },
            "original_file_size_reduced": "~1800 lines -> ~200 lines + 5 modules",
            "benefits": [
                "Separated concerns",
                "Better maintainability",
                "Easier testing",
                "Cleaner code organization",
                "Modular development",
            ],
        }
    )


logger.info("ECR Blueprint routes registered successfully")
