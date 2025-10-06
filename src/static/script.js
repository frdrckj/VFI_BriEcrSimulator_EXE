class ECRSimulator {
    constructor() {
        this.settings = {};
        this.isConnected = false;
        this.transactionHistory = [];
        this.downloadType = 'log';
        this.initializeElements();
        this.bindEvents();
        this.loadSettings();
        this.checkConnectionStatus();
        this.fetchHistory();
    }
    initializeElements() {
        this.transactionTypeSelect = document.getElementById('transactionType');
        this.amountInput = document.getElementById('amount');
        this.addAmountInput = document.getElementById('addAmount');
        this.addAmountFields = document.getElementById('addAmountFields');
        this.addAmountLabel = document.getElementById('addAmountLabel');
        this.additionalFields = document.getElementById('additionalFields');
        this.invoiceNoInput = document.getElementById('invoiceNo');
        this.cardNumberInput = document.getElementById('cardNumber');
        this.cardNumberFields = document.getElementById('cardNumberFields');
        this.additionalLabel = document.getElementById('additionalLabel');
        this.requestArea = document.getElementById('requestArea');
        this.responseArea = document.getElementById('responseArea');
        this.sendBtn = document.getElementById('sendBtn');
        this.openBtn = document.getElementById('openBtn');
        this.communicationSelect = document.getElementById('communication');
        this.serialPortSelect = document.getElementById('serialPort');
        this.socketIpInput = document.getElementById('socketIp');
        this.socketPortInput = document.getElementById('socketPort');
        this.speedBaudSelect = document.getElementById('speedBaud');
        this.dataBitsInput = document.getElementById('dataBits');
        this.stopBitsSelect = document.getElementById('stopBits');
        this.paritySelect = document.getElementById('parity');
        this.enableSslCheck = document.getElementById('enableSsl');
        this.edcSerialNumberInput = document.getElementById('edcSerialNumber');
        this.saveSettingsBtn = document.getElementById('saveSettings');
        this.statusIndicator = document.getElementById('statusIndicator');
        this.historyContainer = document.getElementById('historyContainer');
        this.downloadLogBtn = document.getElementById('downloadLogBtn');
        this.downloadHistoryBtn = document.getElementById('downloadHistoryBtn');
        this.qrCodeSection = document.getElementById('qrCodeSection');
        this.qrCodeCanvas = document.getElementById('qrCodeCanvas');
    }
    bindEvents() {
        this.sendBtn.addEventListener('click', () => this.sendTransaction());
        this.openBtn.addEventListener('click', () => this.toggleConnection());
        this.saveSettingsBtn.addEventListener('click', () => this.saveSettings());
        this.downloadLogBtn.addEventListener('click', () => this.downloadLog());
        this.downloadHistoryBtn.addEventListener('click', () => this.downloadHistory());

        // Logout functionality
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', async () => {
                try {
                    await fetch('/api/auth/logout', { method: 'POST' });
                    window.location.href = '/login.html';
                } catch (error) {
                    console.error('Logout error:', error);
                    window.location.href = '/login.html';
                }
            });
        }

        // Display current user
        if (window.currentUser) {
            const userDisplay = document.getElementById('userDisplay');
            if (userDisplay) {
                userDisplay.textContent = `Logged in as: ${window.currentUser.username}${window.currentUser.is_admin ? ' (Admin)' : ''}`;
            }
        }

        const clearHistoryBtn = document.getElementById('clearHistoryBtn');
        if (clearHistoryBtn) {
            clearHistoryBtn.addEventListener('click', () => this.clearHistory());
        }
        const downloadLogConfirm = document.getElementById('downloadLogConfirm');
        if (downloadLogConfirm) {
            downloadLogConfirm.addEventListener('click', () => this.confirmDownloadLog());
        }
        this.transactionTypeSelect.addEventListener('change', () => {
            this.requestArea.value = '';
            this.responseArea.value = '';
            // Clear all input fields when transaction type changes
            this.amountInput.value = '';
            this.invoiceNoInput.value = '';
            if (this.cardNumberInput) {
                this.cardNumberInput.value = '';
            }
            this.showAdditionalFields();
            // Don't automatically update request when transaction type changes
            // User needs to enter values first
        });
        this.amountInput.addEventListener('keydown', (e) => this.validateNumberKeydown(e));
        this.amountInput.addEventListener('input', (e) => {
            this.cleanNumberInput(e.target);
            this.updateRequest();
        });
        this.amountInput.addEventListener('blur', () => this.formatAmount());
        this.addAmountInput.addEventListener('keydown', (e) => this.validateNumberKeydown(e));
        this.addAmountInput.addEventListener('input', (e) => {
            this.cleanNumberInput(e.target);
            this.updateRequest();
        });
        this.addAmountInput.addEventListener('blur', () => this.formatAddAmount());
        this.invoiceNoInput.addEventListener('keydown', (e) => this.validateNumberKeydown(e));
        this.invoiceNoInput.addEventListener('input', (e) => {
            this.cleanNumberInput(e.target);
            this.updateRequest();
        });
        this.cardNumberInput.addEventListener('keydown', (e) => this.validateNumberKeydown(e));
        this.cardNumberInput.addEventListener('input', (e) => {
            this.cleanNumberInput(e.target);
            this.updateRequest();
        });
        this.communicationSelect.addEventListener('change', () => this.toggleCommunicationFields());

        // Add number validation for settings fields
        this.socketPortInput.addEventListener('keydown', (e) => this.validateNumberKeydown(e));
        this.socketPortInput.addEventListener('input', (e) => this.cleanNumberInput(e.target));
        this.dataBitsInput.addEventListener('keydown', (e) => this.validateNumberKeydown(e));
        this.dataBitsInput.addEventListener('input', (e) => this.cleanNumberInput(e.target));
        this.edcSerialNumberInput.addEventListener('keydown', (e) => this.validateAlphanumericKeydown(e));
        this.edcSerialNumberInput.addEventListener('input', (e) => this.cleanAlphanumericInput(e.target));
    }

    validateNumberKeydown(event) {
        // Allow only numbers, backspace, delete, tab, escape, enter
        const allowedKeys = ['Backspace', 'Delete', 'Tab', 'Escape', 'Enter', 'Home', 'End', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'];

        if (allowedKeys.includes(event.key)) {
            return;
        }

        // Allow Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+Z
        if (event.ctrlKey && ['a', 'c', 'v', 'x', 'z'].includes(event.key.toLowerCase())) {
            return;
        }

        // Only allow digits 0-9
        if (!/^[0-9]$/.test(event.key)) {
            event.preventDefault();
            return;
        }

        // BRI FMS v3.3 - Length validation based on transaction type for invoice/trace/reference fields
        if (event.target === this.invoiceNoInput) {
            const currentValue = event.target.value.replace(/\D/g, ''); // Remove non-digits
            const type = this.transactionTypeSelect.value;
            let maxLength = 6; // Default max length

            // Set max length based on transaction type (matching desktop BriMainFrame.java)
            if (type === 'QRIS STATUS TRANSAKSI') {
                maxLength = 12;
            } else if (type === 'QRIS REFUND') {
                maxLength = 10;
            }

            if (currentValue.length >= maxLength && !allowedKeys.includes(event.key)) {
                event.preventDefault();
                return;
            }
        }

        // Amount and add amount fields - max 10 digits
        if (event.target === this.amountInput || event.target === this.addAmountInput) {
            const currentValue = event.target.value.replace(/\D/g, '');
            if (currentValue.length >= 10 && !allowedKeys.includes(event.key)) {
                event.preventDefault();
                return;
            }
        }

        // Card number field - max 19 digits
        if (event.target === this.cardNumberInput) {
            const currentValue = event.target.value.replace(/\D/g, '');
            if (currentValue.length >= 19 && !allowedKeys.includes(event.key)) {
                event.preventDefault();
                return;
            }
        }
    }

    cleanNumberInput(input) {
        const cursorPosition = input.selectionStart;
        const originalValue = input.value;
        const cleanedValue = originalValue.replace(/[^0-9]/g, ''); // Remove all non-digits

        // BRI FMS v3.3 - Apply max length based on field type
        if (input === this.invoiceNoInput) {
            const type = this.transactionTypeSelect.value;
            let maxLength = 6; // Default max length

            if (type === 'QRIS STATUS TRANSAKSI') {
                maxLength = 12;
            } else if (type === 'QRIS REFUND') {
                maxLength = 10;
            }

            input.value = cleanedValue.substring(0, maxLength);
        } else if (input === this.amountInput || input === this.addAmountInput) {
            // Amount fields - max 10 digits
            input.value = cleanedValue.substring(0, 10);
        } else if (input === this.cardNumberInput) {
            // Card number field - max 19 digits
            input.value = cleanedValue.substring(0, 19);
        } else {
            input.value = cleanedValue;
        }

        // Restore cursor position (adjust if characters were removed)
        const removedChars = originalValue.length - input.value.length;
        const newPosition = Math.max(0, cursorPosition - removedChars);
        input.setSelectionRange(newPosition, newPosition);
    }

    validateAlphanumericKeydown(event) {
        // Allow only alphanumeric characters, backspace, delete, tab, escape, enter
        const allowedKeys = ['Backspace', 'Delete', 'Tab', 'Escape', 'Enter', 'Home', 'End', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'];

        if (allowedKeys.includes(event.key)) {
            return;
        }

        // Allow Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+Z
        if (event.ctrlKey && ['a', 'c', 'v', 'x', 'z'].includes(event.key.toLowerCase())) {
            return;
        }

        // Only allow alphanumeric characters
        if (!/^[A-Za-z0-9]$/.test(event.key)) {
            event.preventDefault();
            return;
        }
    }

    cleanAlphanumericInput(input) {
        const cursorPosition = input.selectionStart;
        const originalValue = input.value;
        const cleanedValue = originalValue.replace(/[^A-Za-z0-9]/g, ''); // Remove all non-alphanumeric characters

        input.value = cleanedValue;

        // Restore cursor position (adjust if characters were removed)
        const removedChars = originalValue.length - input.value.length;
        const newPosition = Math.max(0, cursorPosition - removedChars);
        input.setSelectionRange(newPosition, newPosition);
    }
    showAdditionalFields() {
        const type = this.transactionTypeSelect.value;

        // Reset all fields first
        this.amountInput.disabled = false;
        this.addAmountInput.disabled = false;
        this.invoiceNoInput.disabled = false;
        this.cardNumberInput.disabled = false;
        this.additionalFields.style.display = 'none';
        this.addAmountFields.style.display = 'none';
        this.cardNumberFields.style.display = 'none';

        // Reset amount label to default
        const amountLabel = document.querySelector('label[for="amount"]');
        if (amountLabel) amountLabel.textContent = 'Amount';

        // Configure fields based on exact requirements from user list
        // Format: transaction -> fields shown

        // 1. SALE - Amount
        if (type === 'SALE') {
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 2. INSTALLMENT - Amount
        else if (type === 'INSTALLMENT') {
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 3. VOID - Trace no
        else if (type === 'VOID') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.cardNumberInput.disabled = true;
            this.additionalFields.style.display = 'block';
            this.additionalLabel.textContent = 'Trace No';
            this.invoiceNoInput.placeholder = '000009';
        }
        // 4. GENERATE QR - Amount, Tip Amount
        else if (type === 'GENERATE QR') {
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
            this.addAmountFields.style.display = 'block';
            this.addAmountLabel.textContent = 'Tip Amount';
            this.addAmountInput.placeholder = '0';
        }
        // 5. QRIS STATUS TRANSAKSI - Reff no
        else if (type === 'QRIS STATUS TRANSAKSI') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.cardNumberInput.disabled = true;
            this.additionalFields.style.display = 'block';
            this.additionalLabel.textContent = 'Reff No';
            this.invoiceNoInput.placeholder = '000000000001';
        }
        // 6. QRIS REFUND - Reff id
        else if (type === 'QRIS REFUND') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.cardNumberInput.disabled = true;
            this.additionalFields.style.display = 'block';
            this.additionalLabel.textContent = 'Reff Id';
            this.invoiceNoInput.placeholder = '0000000001';
        }
        // 7. INFO SALDO BRIZZI - No fields
        else if (type === 'INFO SALDO BRIZZI') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 8. PEMBAYARAN BRIZZI - Amount
        else if (type === 'PEMBAYARAN BRIZZI') {
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 9. TOPUP BRIZZI ONLINE - Amount
        else if (type === 'TOPUP BRIZZI ONLINE') {
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 10. TOPUP BRIZZI TERTUNDA - Amount, Brizzi Card
        else if (type === 'TOPUP BRIZZI TERTUNDA') {
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberFields.style.display = 'block';
            this.cardNumberInput.placeholder = 'Brizzi Card Number';
        }
        // 11. UPDATE SALDO TERTUNDA BRIZZI - No fields
        else if (type === 'UPDATE SALDO TERTUNDA BRIZZI') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 12. VOID BRIZZI - Trace no
        else if (type === 'VOID BRIZZI') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.cardNumberInput.disabled = true;
            this.additionalFields.style.display = 'block';
            this.additionalLabel.textContent = 'Trace No';
            this.invoiceNoInput.placeholder = '000009';
        }
        // 13. FARE NON-FARE - Fare, Non-Fare
        else if (type === 'FARE NON-FARE') {
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
            this.addAmountFields.style.display = 'block';
            if (amountLabel) amountLabel.textContent = 'Fare';
            this.addAmountLabel.textContent = 'Non Fare';
            this.addAmountInput.placeholder = '0';
        }
        // 14. CONTACTLESS - Amount
        else if (type === 'CONTACTLESS') {
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 15. SALE TIP - Amount, Tip Amount
        else if (type === 'SALE TIP') {
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
            this.addAmountFields.style.display = 'block';
            this.addAmountLabel.textContent = 'Tip Amount';
            this.addAmountInput.placeholder = '0';
        }
        // 16. KEY IN - Amount
        else if (type === 'KEY IN') {
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 17. LOGON - No fields
        else if (type === 'LOGON') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 18. SETTLEMENT - No fields
        else if (type === 'SETTLEMENT') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 19. SETTLEMENT BRIZZI - No fields
        else if (type === 'SETTLEMENT BRIZZI') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 20. REPRINT TRANSAKSI TERAKHIR - No fields
        else if (type === 'REPRINT TRANSAKSI TERAKHIR') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 21. REPRINT TRANSAKSI - Trace no
        else if (type === 'REPRINT TRANSAKSI') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.cardNumberInput.disabled = true;
            this.additionalFields.style.display = 'block';
            this.additionalLabel.textContent = 'Trace No';
            this.invoiceNoInput.placeholder = '000009';
        }
        // 22. DETAIL REPORT - No fields
        else if (type === 'DETAIL REPORT') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 23. SUMMARY REPORT - No fields
        else if (type === 'SUMMARY REPORT') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 24. REPRINT BRIZZI TRANSAKSI TERAKHIR - No fields
        else if (type === 'REPRINT BRIZZI TRANSAKSI TERAKHIR') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 25. REPRINT BRIZZI TRANSAKSI - Trace no
        else if (type === 'REPRINT BRIZZI TRANSAKSI') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.cardNumberInput.disabled = true;
            this.additionalFields.style.display = 'block';
            this.additionalLabel.textContent = 'Trace No';
            this.invoiceNoInput.placeholder = '000009';
        }
        // 26. BRIZZI DETAIL REPORT - No fields
        else if (type === 'BRIZZI DETAIL REPORT') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 27. BRIZZI SUMMARY REPORT - No fields
        else if (type === 'BRIZZI SUMMARY REPORT') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 28. QRIS DETAIL REPORT - No fields
        else if (type === 'QRIS DETAIL REPORT') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 29. QRIS SUMMARY REPORT - No fields
        else if (type === 'QRIS SUMMARY REPORT') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // 30. INFO KARTU BRIZZI - No fields
        else if (type === 'INFO KARTU BRIZZI') {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
        // Default: all fields disabled
        else {
            this.amountInput.disabled = true;
            this.amountInput.value = '';
            this.addAmountInput.disabled = true;
            this.invoiceNoInput.disabled = true;
            this.cardNumberInput.disabled = true;
        }
    }

    formatTraceNumber() {
        // BRI FMS v3.3 - Format trace number for VOID transactions
        if (this.transactionTypeSelect.value === 'VOID' || this.transactionTypeSelect.value === 'VOID BRIZZI') {
            let value = this.invoiceNoInput.value.replace(/\D/g, ''); // Remove non-digits
            if (value && value !== '0') {
                value = value.padStart(6, '0');
                this.invoiceNoInput.value = value;
            }
        }
        this.updateRequest();
    }

    formatReferenceId() {
        // BRI FMS v3.3 - Format reference ID for QRIS transactions
        if (['QRIS STATUS TRANSAKSI', 'QRIS REFUND'].includes(this.transactionTypeSelect.value)) {
            let value = this.invoiceNoInput.value.replace(/\D/g, ''); // Remove non-digits
            if (value && value !== '0') {
                // QRIS Status: 12 digits, QRIS Refund: 10 digits
                const padLength = this.transactionTypeSelect.value === 'QRIS STATUS TRANSAKSI' ? 12 : 10;
                value = value.padStart(padLength, '0');
                this.invoiceNoInput.value = value;
            }
        }
        this.updateRequest();
    }

    getCardNumber() {
        return this.cardNumberInput ? this.cardNumberInput.value : '';
    }

    async checkConnectionStatus() {
        try {
            // Check if already connected by attempting a status check
            const response = await fetch('/api/connection_status', {
                method: 'GET',
                headers: {'Content-Type': 'application/json'}
            });
            if (response.ok) {
                const result = await response.json();
                this.isConnected = result.connected || false;
                this.updateStatus();
            }
        } catch (error) {
            console.error('Error checking connection status:', error);
            // Default to disconnected state
            this.isConnected = false;
            this.updateStatus();
        }
    }

    async loadSettings() {
        try {
            const response = await fetch('/api/settings');
            if (response.ok) {
                this.settings = await response.json();
                this.populateSettingsForm();
            }
        } catch (error) {
            console.error('Error loading settings:', error);
            this.showNotification('Error loading settings', 'error');
        }
    }
    populateSettingsForm() {
        this.communicationSelect.value = this.settings.communication || 'Serial';
        this.serialPortSelect.value = this.settings.serial_port || '';
        this.socketIpInput.value = this.settings.socket_ip || '127.0.0.1';
        this.socketPortInput.value = this.settings.socket_port || '9001';
        this.speedBaudSelect.value = this.settings.speed_baud || '9600';
        this.dataBitsInput.value = this.settings.data_bits || '8';
        this.stopBitsSelect.value = this.settings.stop_bits || '1';
        this.paritySelect.value = this.settings.parity || 'None';
        this.enableSslCheck.checked = this.settings.enable_ssl || false;
        this.edcSerialNumberInput.value = this.settings.edc_serial_number || '';
        // Initialize field states based on communication type
        this.toggleCommunicationFields();
    }
    async saveSettings() {
        const settings = {
            communication: this.communicationSelect.value,
            serial_port: this.serialPortSelect.value,
            socket_ip: this.socketIpInput.value,
            socket_port: this.socketPortInput.value,
            speed_baud: this.speedBaudSelect.value,
            data_bits: this.dataBitsInput.value,
            stop_bits: this.stopBitsSelect.value,
            parity: this.paritySelect.value,
            enable_ssl: this.enableSslCheck.checked,
            edc_serial_number: this.edcSerialNumberInput.value
        };
        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(settings)
            });
            if (response.ok) {
                this.settings = settings;
                this.showNotification('Settings saved successfully', 'success');
                const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
                modal.hide();
            } else {
                this.showNotification('Error saving settings', 'error');
            }
        } catch (error) {
            this.showNotification('Error saving settings', 'error');
        }
    }
    async updateRequest() {
        const transaction_type = this.transactionTypeSelect.value;
        const amount = (this.amountInput.value || '0').replace(/,/g, '');
        const addAmount = (this.addAmountInput.value || '0').replace(/,/g, '');
        const invoiceNo = this.invoiceNoInput.value || '';
        const cardNo = this.getCardNumber();
        try {
            const response = await fetch('/api/build_request', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ transaction_type, amount, addAmount, invoiceNo, cardNo })
            });
            const result = await response.json();
            this.requestArea.value = result.request;
        } catch (error) {
            this.requestArea.value = 'Error generating request';
            this.showNotification('Error generating request', 'error');
        }
    }
    formatAmount() {
        let value = this.amountInput.value.replace(/[^0-9]/g, '');
        if (value && !isNaN(value)) {
            let formattedValue = parseInt(value).toLocaleString();
            this.amountInput.value = formattedValue;
        }
        this.updateRequest();
    }
    formatAddAmount() {
        let value = this.addAmountInput.value.replace(/[^0-9]/g, '');
        if (value && !isNaN(value)) {
            let formattedValue = parseInt(value).toLocaleString();
            this.addAmountInput.value = formattedValue;
        }
        this.updateRequest();
    }
    async sendTransaction() {
        const transaction_type = this.transactionTypeSelect.value;
        const amount = this.amountInput.value.replace(/,/g, '');
        const addAmount = this.addAmountInput.value.replace(/,/g, '');

        // BRI FMS v3.3 - Transactions that require amount (input_mode 1, 3, 4, 5)
        const transactionsRequiringAmount = [
            'SALE', 'INSTALLMENT', 'GENERATE QR', 'PEMBAYARAN BRIZZI', 'TOPUP BRIZZI ONLINE',
            'TOPUP BRIZZI TERTUNDA', 'FARE NON-FARE', 'CONTACTLESS', 'SALE TIP', 'KEY IN'
        ];

        if (transactionsRequiringAmount.includes(transaction_type) && (!amount || parseInt(amount) <= 0)) {
            this.showNotification('Please enter a valid amount', 'error');
            return;
        }

        this.setLoading(true);
        try {
            const res = await fetch('/api/process', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    transaction_type,
                    amount: amount || '0',
                    addAmount: addAmount || '0',
                    invoiceNo: this.invoiceNoInput.value || null,
                    cardNo: this.getCardNumber()
                })
            });
            const result = await res.json();
            if (!res.ok) {
                throw new Error(result.error);
            }
            if (result.status === 'processing') {
                // For serial - start polling, keep button disabled
                this.responseArea.value = result.message || 'Waiting for EDC response...';
                this.responseArea.className = 'form-control response-processing';
                this.pollTransactionStatus(result.trxId);
                // Don't call setLoading(false) here - let polling handle it
            } else if (result.status === 'success') {
                this.displayResponse(result, 'success');
                this.addToHistory(transaction_type, amount, result);
                this.setLoading(false);
            } else if (result.status === 'failed') {
                this.displayResponse(result, 'failed');
                this.addToHistory(transaction_type, amount, result);
                this.setLoading(false);
            } else {
                this.displayResponse(result, 'error');
                this.addToHistory(transaction_type, amount, result);
                this.setLoading(false);
            }
        } catch (error) {
            this.displayResponse({ error: error.message }, 'error');
            this.setLoading(false);
        }
    }
    pollTransactionStatus(trxId) {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/transaction_status/${trxId}`);
                const result = await res.json();
                if (result.status === 'processing') {
                    // Continue polling
                    return;
                }
                clearInterval(interval);
                const displayType = result.status === 'completed' ? 'success' : 'failed';
                this.displayResponse(result, displayType);
                this.addToHistory(this.transactionTypeSelect.value, this.amountInput.value, result);
                // Re-enable the send button after transaction completes
                this.setLoading(false);
            } catch (error) {
                clearInterval(interval);
                this.displayResponse({ error: `Polling error: ${error.message}` }, 'error');
                // Re-enable the send button on error
                this.setLoading(false);
            }
        }, 1000); // Poll every second
    }
    formatResponse(rsp) {
        let text = '';
        // Field order matching desktop version
        const fields = [
            {key: 'transType', label: 'Trans Type'},
            {key: 'tid', label: 'TID'},
            {key: 'mid', label: 'MID'},
            {key: 'batchNumber', label: 'Batch Number'},
            {key: 'issuerName', label: 'Issuer Name'},
            {key: 'traceNo', label: 'Trace No'},
            {key: 'invoiceNo', label: 'Invoice No'},
            {key: 'entryMode', label: 'Entry Mode'},
            {key: 'transAmount', label: 'Trans Amount'},
            {key: 'totalAmount', label: 'Total Amount'},
            {key: 'cardNo', label: 'Card No'},
            {key: 'cardholderName', label: 'Cardholder Name'},
            {key: 'date', label: 'Date'},
            {key: 'time', label: 'Time'},
            {key: 'approvalCode', label: 'Approval Code'},
            {key: 'responseCode', label: 'Response Code'},
            {key: 'refNumber', label: 'Ref Number'},
            {key: 'balancePrepaid', label: 'Balance (Prepaid)'},
            {key: 'topupCardNo', label: 'Top-up Card Number'},
            {key: 'transAddAmount', label: 'Trans Add Amount'},
            {key: 'filler', label: 'Filler'},
            {key: 'referenceId', label: 'Reference Id'},
            {key: 'term', label: 'Term'},
            {key: 'monthlyAmount', label: 'Monthly Amount'},
            {key: 'pointReward', label: 'Point Reward'},
            {key: 'redemptionAmount', label: 'Redemption Amount'},
            {key: 'pointBalance', label: 'Point Balance'},
        ];
        for (let field of fields) {
            let val = rsp[field.key] || '';
            // Show all fields even if empty, matching desktop version
            text += `${field.label}: ${val}\n`;
        }

        // Add parse error if present
        if (rsp.parse_error) {
            text += `\nParse Error: ${rsp.parse_error}\n`;
        }

        // Show message if it's a parsing error response
        if (rsp.message && rsp.responseCode === 'PARSE_ERROR') {
            text = `${rsp.message}\n\n${text}`;
        }

        return text.trim() || 'No response details';
    }
    displayResponse(response, type) {
        let responseText = '';
        let className = 'form-control ';
        this.hideQRCode();
        if (response.message) {
            responseText = response.message;
            className += (response.message === 'ACK' ? 'response-success' : 'response-error');
        } else if (response.error) {
            responseText = `ERROR: ${response.error}`;
            className += 'response-error';
        } else if (response.response) {
            const rsp = response.response;
            responseText = this.formatResponse(rsp);
            const respCode = rsp.responseCode || '';
            const isSuccess = respCode === '00' || respCode === 'Z1';
            className += isSuccess ? 'response-success' : 'response-error';
            // Just show the parsed response fields without status prefix
            this.displayQRCode(rsp);
        } else {
            responseText = 'No response data';
            className += 'response-error';
        }
        this.responseArea.value = responseText;
        this.responseArea.className = className;
    }
    displayQRCode(responseData) {
        // BRI FMS v3.3 - QR-related transaction types
        const qrTransactionTypes = ['GENERATE QR', 'QRIS STATUS TRANSAKSI', 'QRIS REFUND', 'QRIS MPM', 'QRIS CPM'];
        if (responseData && responseData.qrCode && responseData.qrCode.trim() && qrTransactionTypes.includes(this.transactionTypeSelect.value)) {
            console.log(`Attempting to display QR code, length: ${responseData.qrCode.length}`);
            if (typeof qrcode === 'undefined') {
                console.error('qrcode library not loaded');
                this.showNotification('QR code library not loaded', 'error');
                this.hideQRCode();
                return;
            }
            try {
                if (responseData.qrCode.length > 1000) {
                    console.error(`QR code string too long: ${responseData.qrCode.length} characters`);
                    this.showNotification('QR code data too long to display', 'error');
                    this.hideQRCode();
                    return;
                }
                const qrCanvas = generateQRCode(responseData.qrCode, 256);
                if (qrCanvas) {
                    this.qrCodeCanvas.width = qrCanvas.width;
                    this.qrCodeCanvas.height = qrCanvas.height;
                    const ctx = this.qrCodeCanvas.getContext('2d');
                    ctx.clearRect(0, 0, this.qrCodeCanvas.width, this.qrCodeCanvas.height);
                    ctx.drawImage(qrCanvas, 0, 0);
                    console.log('QR Code displayed successfully');
                    this.qrCodeSection.style.display = 'block';
                } else {
                    console.error('Failed to generate QR code');
                    this.showNotification('Failed to generate QR code', 'error');
                    this.hideQRCode();
                }
            } catch (error) {
                console.error('QR Code display error:', error.message);
                this.showNotification(`Error displaying QR code: ${error.message}`, 'error');
                this.hideQRCode();
            }
        } else {
            console.log('No valid QR code data or not a QRIS transaction');
            this.hideQRCode();
        }
    }
    hideQRCode() {
        this.qrCodeSection.style.display = 'none';
        const ctx = this.qrCodeCanvas.getContext('2d');
        ctx.clearRect(0, 0, this.qrCodeCanvas.width, this.qrCodeCanvas.height);
    }
    showHistoryQR(itemId, amount) {
        if (!amount || isNaN(parseInt(amount))) {
            this.showNotification('No valid amount available for this transaction', 'error');
            return;
        }
        // Find the transaction in history to get the QR code
        const transaction = this.transactionHistory.find(item => item.id === itemId);
        if (!transaction || !transaction.qr_code || transaction.qr_code.trim() === '') {
            this.showNotification('No QR code available for this transaction', 'error');
            return;
        }
        console.log(`Generating history QR code, length: ${transaction.qr_code.length}`);
        if (transaction.qr_code.length > 1000) {
            this.showNotification('QR code data too long to display', 'error');
            return;
        }
        const formattedAmount = `Rp ${parseInt(amount).toLocaleString()}`;
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = `qrModal_${itemId}`;
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">QR Code - Transaction ${itemId}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <div id="qrContainer_${itemId}">
                            <div class="spinner-border" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p>Generating QR Code...</p>
                        </div>
                        <div class="mt-3">
                            <small class="text-muted d-block" style="word-break: break-all;">${formattedAmount}</small>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        modal.addEventListener('shown.bs.modal', () => {
            if (typeof qrcode === 'undefined') {
                console.error('qrcode library not loaded');
                const container = document.getElementById(`qrContainer_${itemId}`);
                container.innerHTML = '<p class="text-danger">QR Code library not loaded</p>';
                this.showNotification('QR code library not loaded', 'error');
                return;
            }
            try {
                const qrCanvas = generateQRCode(transaction.qr_code, 300);
                const container = document.getElementById(`qrContainer_${itemId}`);
                if (qrCanvas) {
                    container.innerHTML = '';
                    container.appendChild(qrCanvas);
                    console.log('History QR Code generated successfully');
                } else {
                    container.innerHTML = '<p class="text-danger">Error generating QR code</p>';
                    this.showNotification('Failed to generate QR code', 'error');
                }
            } catch (error) {
                console.error('History QR Code error:', error.message);
                const container = document.getElementById(`qrContainer_${itemId}`);
                container.innerHTML = `<p class="text-danger">QR Code generation failed: ${error.message}</p>`;
                this.showNotification(`QR code generation failed: ${error.message}`, 'error');
            }
        });
        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
        });
        bsModal.show();
    }
    addToHistory(transactionType, amount, response) {
        let invoiceNo = '';
        let traceNo = '';
        let referenceId = '';

        if (response.response && response.response.invoiceNo) {
            invoiceNo = response.response.invoiceNo;
        } else if (this.invoiceNoInput.value) {
            invoiceNo = this.invoiceNoInput.value;
        }

        // Extract trace number and reference ID from response
        if (response.response) {
            traceNo = response.response.traceNo || '';
            referenceId = response.response.referenceId || '';
        }

        const historyItem = {
            id: response.trxId || Date.now(),
            timestamp: response.timestamp || new Date().toISOString().slice(0, 19).replace('T', ' '),
            transaction_type: transactionType,
            amount: amount,
            status: response.status || 'SUCCESS',
            transaction_id: response.trxId || 'N/A',
            invoice_no: invoiceNo,
            trace_no: traceNo,
            reference_id: referenceId,
            qr_code: response.response && response.response.qrCode ? response.response.qrCode : ''
        };
        this.transactionHistory.unshift(historyItem);
        this.updateHistoryDisplay();
    }
    async fetchHistory() {
        try {
            const response = await fetch('/api/history');
            if (response.ok) {
                this.transactionHistory = await response.json();
                this.updateHistoryDisplay();
            }
        } catch (error) {
            console.error('Error fetching history:', error);
            this.showNotification('Error fetching transaction history', 'error');
        }
    }
    updateHistoryDisplay() {
        if (this.transactionHistory.length === 0) {
            this.historyContainer.innerHTML = '<div class="history-item"><small class="text-muted">No transactions yet</small></div>';
            return;
        }
        const historyHtml = this.transactionHistory.map(item => {
            const formattedAmount = parseInt(item.amount || '0').toLocaleString();

            // Determine what to show based on transaction type
            let additionalInfo = '';
            const isQrisTransaction = ['QRIS MPM', 'QRIS CPM', 'QRIS NOTIFICATION', 'QRIS REFUND'].includes(item.transaction_type);
            const isSaleOrVoid = ['SALE', 'VOID'].includes(item.transaction_type);

            if (isQrisTransaction) {
                // For QRIS transactions, show Reference ID if available
                if (item.reference_id) {
                    additionalInfo = ` | Reference ID: ${item.reference_id}`;
                } else if (item.invoice_no) {
                    additionalInfo = ` | Reference ID: ${item.invoice_no}`;
                }
            } else if (isSaleOrVoid) {
                // For SALE and VOID transactions, show Trace No if available
                if (item.trace_no) {
                    additionalInfo = ` | Trace No: ${item.trace_no}`;
                } else if (item.invoice_no) {
                    additionalInfo = ` | Trace No: ${item.invoice_no}`;
                }
            }

            // BRI FMS v3.3 - Show QR button for QR-related transactions
            const qrTransactionTypes = ['GENERATE QR', 'QRIS STATUS TRANSAKSI', 'QRIS REFUND', 'QRIS MPM', 'QRIS CPM'];
            const qrButton = (qrTransactionTypes.includes(item.transaction_type) && item.qr_code && item.qr_code.trim()) ? `<button class="btn btn-sm btn-outline-primary ms-2" onclick="simulator.showHistoryQR('${item.id}', '${item.amount}')">Show QR</button>` : '';
            return `
            <div class="history-item">
                <div class="transaction-info">${item.transaction_type} - ${formattedAmount}${qrButton}</div>
                <div class="transaction-details">
                    ${item.timestamp} | ${item.status} | ID: ${item.transaction_id}${additionalInfo}
                </div>
            </div>
            `;
        }).join('');
        this.historyContainer.innerHTML = historyHtml;
    }
    async toggleConnection() {
        const wasConnected = this.isConnected;
        const actionText = wasConnected ? 'Disconnecting...' : 'Connecting...';

        this.showNotification(actionText, 'info');

        try {
            const response = await fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ action: wasConnected ? 'disconnect' : 'connect' })
            });

            const result = await response.json();

            if (response.ok) {
                // Update connection state based on server response
                this.isConnected = result.connected;

                // Always show notification with connection details
                const message = result.message && result.message.trim() !== ''
                    ? result.message
                    : (result.connected ? 'Connection established' : 'Connection closed');

                this.showNotification(message, result.connected ? 'success' : 'info');
            } else {
                // Connection failed - ensure we're in disconnected state
                this.isConnected = false;
                this.showNotification(result.error || 'Connection failed', 'error');
            }
        } catch (error) {
            // Network error, timeout, or other exception - ensure we're in disconnected state
            this.isConnected = false;
            const errorMsg = error.name === 'TypeError' && error.message.includes('fetch')
                ? 'Connection timeout or network error'
                : `Connection failed: ${error.message}`;
            this.showNotification(errorMsg, 'error');
        } finally {
            // Always update the UI status to reflect the current connection state
            this.updateStatus();
        }
    }
    downloadLog() {
        this.downloadType = 'log';
        // Show password modal instead of directly downloading
        const passwordModal = new bootstrap.Modal(document.getElementById('passwordModal'));
        document.getElementById('passwordModalLabel').textContent = 'Download Log - Password Required';
        document.getElementById('logPassword').value = ''; // Clear previous input
        passwordModal.show();
    }
    downloadHistory() {
        this.downloadType = 'history';
        // Show password modal instead of directly downloading
        const passwordModal = new bootstrap.Modal(document.getElementById('passwordModal'));
        document.getElementById('passwordModalLabel').textContent = 'Download History - Password Required';
        document.getElementById('logPassword').value = ''; // Clear previous input
        passwordModal.show();
    }
    confirmDownloadLog() {
        const password = document.getElementById('logPassword').value;
        const today = new Date();
        const day = String(today.getDate()).padStart(2, '0');
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const year = today.getFullYear();
        const expectedPassword = `${day}${month}${year}`;
        if (password === expectedPassword) {
            // Close modal and download
            const passwordModal = bootstrap.Modal.getInstance(document.getElementById('passwordModal'));
            passwordModal.hide();

            // Download with password verification based on type
            if (this.downloadType === 'history') {
                window.open(`/api/download_history?password=${encodeURIComponent(password)}`, '_blank');
            } else {
                window.open(`/api/download_log?password=${encodeURIComponent(password)}`, '_blank');
            }
        } else {
            this.showNotification('Invalid password. Please use today\'s date in ddmmyyyy format.', 'error');
        }
    }
    async clearHistory() {
        if (!confirm('Are you sure you want to clear all transaction history? This action cannot be undone.')) {
            return;
        }
        try {
            const response = await fetch('/api/history', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const data = await response.json();

            if (response.ok) {
                this.showNotification(data.message || 'Transaction history cleared successfully', 'success');
                // Clear the local history array and update UI
                this.transactionHistory = [];
                this.updateHistoryDisplay();
            } else {
                throw new Error(data.message || 'Failed to clear history');
            }
        } catch (error) {
            console.error('Error clearing history:', error);
            this.showNotification('Failed to clear transaction history: ' + error.message, 'error');
        }
    }
    toggleCommunicationFields() {
        const communicationType = this.communicationSelect.value;
        const isSocket = communicationType === 'Socket';

        // Socket fields - enabled when Socket is selected
        this.socketIpInput.disabled = !isSocket;
        this.socketPortInput.disabled = !isSocket;
        this.enableSslCheck.disabled = !isSocket;

        // EDC Serial Number - always enabled since REST API is mandatory for both Serial and Socket
        this.edcSerialNumberInput.disabled = false;

        // Serial fields - enabled when Serial is selected
        this.serialPortSelect.disabled = isSocket;
        this.speedBaudSelect.disabled = isSocket;
        this.dataBitsInput.disabled = isSocket;
        this.stopBitsSelect.disabled = isSocket;
        this.paritySelect.disabled = isSocket;
    }
    updateStatus() {
        const statusDot = this.statusIndicator.querySelector('.status-dot');
        const statusText = this.statusIndicator.querySelector('span:last-child');
        if (this.isConnected) {
            statusDot.className = 'status-dot online';
            statusText.textContent = 'ONLINE';
            this.openBtn.textContent = 'Close';
            this.openBtn.className = 'btn btn-warning';
        } else {
            statusDot.className = 'status-dot offline';
            statusText.textContent = 'OFFLINE';
            this.openBtn.textContent = 'Open';
            this.openBtn.className = 'btn btn-success';
        }
    }
    setLoading(loading) {
        this.sendBtn.disabled = loading;
        this.sendBtn.innerHTML = loading ? '<span class="spinner"></span> Processing...' : 'Send';
    }
    showNotification(message, type) {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        toast.innerHTML = `${message} <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
}
let simulator;
document.addEventListener('DOMContentLoaded', () => {
    simulator = new ECRSimulator();
});

function getTransactionNameFromCode(code) {
    const map = {
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
        "0E": "LOGON"
    };
    return map[code] || code;
}
