"""
Transaction types mapping for BRI ECR Simulator
Matching desktop version BriMessage.java
"""

# Transaction type mapping - matching desktop version exactly
TRANSACTION_TYPES = {
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

# Reverse mapping
TRANSACTION_CODES = {v: k for k, v in TRANSACTION_TYPES.items()}

# Field configuration for each transaction type (matching desktop BriMainFrame.java)
# Format: (input_mode, amount_label, add_amount_label, invoice_label, card_label, max_invoice_length)
# input_mode: 0=none, 1=amount only, 2=invoice only, 3=amount+add_amount+invoice, 4=amount+add_amount, 5=amount+card
TRANSACTION_FIELD_CONFIG = {
    "SALE": (1, "Amount", "", "", "", 6),
    "INSTALLMENT": (1, "Amount", "", "", "", 6),
    "VOID": (2, "", "", "Trace No", "", 6),
    "GENERATE QR": (4, "Amount", "Tip Amount", "", "", 6),
    "QRIS STATUS TRANSAKSI": (2, "", "", "Reff No", "", 12),
    "QRIS REFUND": (2, "", "", "Reff Id", "", 10),
    "INFO SALDO BRIZZI": (0, "", "", "", "", 6),
    "PEMBAYARAN BRIZZI": (1, "Amount", "", "", "", 6),
    "TOPUP BRIZZI TERTUNDA": (5, "Amount", "", "", "Brizzi Card", 6),
    "TOPUP BRIZZI ONLINE": (1, "Amount", "", "", "", 6),
    "UPDATE SALDO TERTUNDA BRIZZI": (0, "", "", "", "", 6),
    "VOID BRIZZI": (2, "", "", "Trace No", "", 6),
    "FARE NON-FARE": (4, "Fare", "Non Fare", "", "", 6),
    "CONTACTLESS": (1, "Amount", "", "", "", 6),
    "SALE TIP": (4, "Amount", "Tip Amount", "", "", 6),
    "KEY IN": (1, "Amount", "", "", "", 6),
    "LOGON": (0, "", "", "", "", 6),
    "SETTLEMENT": (0, "", "", "", "", 6),
    "SETTLEMENT BRIZZI": (0, "", "", "", "", 6),
    "REPRINT TRANSAKSI TERAKHIR": (0, "", "", "", "", 6),
    "REPRINT TRANSAKSI": (2, "", "", "Trace No", "", 6),
    "DETAIL REPORT": (0, "", "", "", "", 6),
    "SUMMARY REPORT": (0, "", "", "", "", 6),
    "REPRINT BRIZZI TRANSAKSI TERAKHIR": (0, "", "", "", "", 6),
    "REPRINT BRIZZI TRANSAKSI": (2, "", "", "Trace No", "", 6),
    "BRIZZI DETAIL REPORT": (0, "", "", "", "", 6),
    "BRIZZI SUMMARY REPORT": (0, "", "", "", "", 6),
    "QRIS DETAIL REPORT": (0, "", "", "", "", 6),
    "QRIS SUMMARY REPORT": (0, "", "", "", "", 6),
    "INFO KARTU BRIZZI": (0, "", "", "", "", 6),
}


def get_trans_type_code(trans_name: str) -> str:
    """Get transaction type code from transaction name"""
    return TRANSACTION_TYPES.get(trans_name, "00")


def get_trans_type_name(trans_code: str) -> str:
    """Get transaction name from transaction type code"""
    return TRANSACTION_CODES.get(trans_code.upper(), trans_code)


def get_field_config(trans_name: str):
    """Get field configuration for a transaction type"""
    return TRANSACTION_FIELD_CONFIG.get(trans_name, (0, "", "", "", "", 6))


def requires_amount(trans_name: str) -> bool:
    """Check if transaction requires amount input"""
    config = get_field_config(trans_name)
    input_mode = config[0]
    return input_mode in [1, 3, 4, 5]


def requires_add_amount(trans_name: str) -> bool:
    """Check if transaction requires additional amount (tip/non-fare)"""
    config = get_field_config(trans_name)
    input_mode = config[0]
    return input_mode in [3, 4]


def requires_invoice(trans_name: str) -> bool:
    """Check if transaction requires invoice/trace/reference number"""
    config = get_field_config(trans_name)
    input_mode = config[0]
    return input_mode in [2, 3]


def requires_card(trans_name: str) -> bool:
    """Check if transaction requires card number"""
    config = get_field_config(trans_name)
    input_mode = config[0]
    return input_mode == 5


def get_max_invoice_length(trans_name: str) -> int:
    """Get maximum invoice/trace/reference number length"""
    config = get_field_config(trans_name)
    return config[5]
