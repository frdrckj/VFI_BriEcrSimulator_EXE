class ECRSimulator {
    constructor() {
        this.settings = {};
        this.isConnected = false;
        this.transactionHistory = [];
        this.initializeElements();
        this.bindEvents();
        this.loadSettings();
        this.updateStatus();
        this.fetchHistory();
    }

    initializeElements() {
        this.transactionTypeSelect = document.getElementById('transactionType');
        this.amountInput = document.getElementById('amount');
        this.additionalFields = document.getElementById('additionalFields');
        this.invoiceNoInput = document.getElementById('invoiceNo');
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
        this.enableRestApiCheck = document.getElementById('enableRestApi');
        this.enableSslCheck = document.getElementById('enableSsl');
        this.edcSerialNumberInput = document.getElementById('edcSerialNumber');
        this.saveSettingsBtn = document.getElementById('saveSettings');
        this.statusIndicator = document.getElementById('statusIndicator');
        this.historyContainer = document.getElementById('historyContainer');
        this.downloadLogBtn = document.getElementById('downloadLogBtn');
        this.qrCodeSection = document.getElementById('qrCodeSection');
        this.qrCodeCanvas = document.getElementById('qrCodeCanvas');
    }

    bindEvents() {
        this.sendBtn.addEventListener('click', () => this.sendTransaction());
        this.openBtn.addEventListener('click', () => this.toggleConnection());
        this.saveSettingsBtn.addEventListener('click', () => this.saveSettings());
        this.downloadLogBtn.addEventListener('click', () => this.downloadLog());
        const testConnectionBtn = document.getElementById('testConnection');
        if (testConnectionBtn) {
            testConnectionBtn.addEventListener('click', () => this.testConnection());
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
            this.showAdditionalFields();
            this.updateRequest();
        });
        this.amountInput.addEventListener('input', () => this.updateRequest());
        this.amountInput.addEventListener('blur', () => this.formatAmount());
        this.invoiceNoInput.addEventListener('input', () => this.updateRequest());
        this.communicationSelect.addEventListener('change', () => this.toggleCommunicationFields());
    }

    showAdditionalFields() {
        const type = this.transactionTypeSelect.value;
        if (type === 'VOID' || type === 'REFUND' || type === 'REPRINT' || type === 'QRIS REFUND') {
            this.additionalFields.style.display = 'block';
            if (type === 'QRIS REFUND') {
                this.additionalLabel.textContent = 'Reference Number';
            } else {
                this.additionalLabel.textContent = 'Invoice No';
            }
        } else {
            this.additionalFields.style.display = 'none';
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
        // REST API is always enabled/mandatory  
        this.enableRestApiCheck.checked = true;
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
            // enable_rest_api removed - REST API is now mandatory
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
        const invoiceNo = this.invoiceNoInput.value || '';
        try {
            const response = await fetch('/api/build_request', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ transaction_type, amount, invoiceNo })
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

    async sendTransaction() {
        const transaction_type = this.transactionTypeSelect.value;
        const amount = this.amountInput.value.replace(/,/g, '');
        if (!amount || parseInt(amount) <= 0) {
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
                    amount,
                    invoiceNo: this.invoiceNoInput.value || null
                })
            });
            const result = await res.json();
            if (!res.ok) {
                throw new Error(result.error);
            }
            if (result.status === 'failed') {
                this.displayResponse(result, 'failed');
            } else {
                this.displayResponse(result, 'success');
            }
            this.addToHistory(transaction_type, amount, result);
            this.setLoading(false);
        } catch (error) {
            this.displayResponse({ error: error.message }, 'error');
            this.setLoading(false);
        }
    }

    displayResponse(response, type) {
        let responseText;
        if (type === 'success') {
            responseText = JSON.stringify(response.response, null, 2);
            this.responseArea.className = 'form-control response-success';
            this.displayQRCode(response.response);
        } else if (type === 'failed') {
            const errorMsg = response.error || 'Transaction failed';
            responseText = `TRANSACTION FAILED: ${errorMsg}\n\nResponse Details:\n${JSON.stringify(response.response, null, 2)}`;
            this.responseArea.className = 'form-control response-error';
            this.displayQRCode(response.response);
        } else {
            responseText = `ERROR: ${response.error || 'Unknown error occurred'}`;
            this.responseArea.className = 'form-control response-error';
            this.hideQRCode();
        }
        this.responseArea.value = responseText;
    }

    displayQRCode(responseData) {
        if (responseData && responseData.qrCode && responseData.qrCode.trim() && ['QRIS MPM', 'QRIS CPM'].includes(this.transactionTypeSelect.value)) {
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
        if (response.response && response.response.invoiceNo) {
            invoiceNo = response.response.invoiceNo;
        } else if (this.invoiceNoInput.value) {
            invoiceNo = this.invoiceNoInput.value;
        }
        const historyItem = {
            id: response.trxId || Date.now(),
            timestamp: new Date().toLocaleString(),
            transaction_type: transactionType,
            amount: amount,
            status: response.status || 'SUCCESS',
            transaction_id: response.trxId || 'N/A',
            invoice_no: invoiceNo,
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
            const invoiceDisplay = item.invoice_no ? ` | Invoice: ${item.invoice_no}` : '';
            const qrButton = item.qr_code && item.qr_code.trim() ? `<button class="btn btn-sm btn-outline-primary ms-2" onclick="simulator.showHistoryQR('${item.id}', '${item.amount}')">Show QR</button>` : '';
            return `
            <div class="history-item">
                <div class="transaction-info">${item.transaction_type} - ${formattedAmount}${qrButton}</div>
                <div class="transaction-details">
                    ${item.timestamp} | ${item.status} | ID: ${item.transaction_id}${invoiceDisplay}
                </div>
            </div>
            `;
        }).join('');
        this.historyContainer.innerHTML = historyHtml;
    }

    async toggleConnection() {
        this.showNotification(this.isConnected ? 'Disconnecting...' : 'Connecting...', 'info');
        try {
            const response = await fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ action: this.isConnected ? 'disconnect' : 'connect' })
            });
            const result = await response.json();
            if (response.ok) {
                this.isConnected = result.connected;
                this.showNotification(result.message, result.connected ? 'success' : 'info');
            } else {
                this.isConnected = false;
                this.showNotification(result.error, 'error');
            }
        } catch (error) {
            this.isConnected = false;
            this.showNotification(`Failed: ${error.message}`, 'error');
        }
        this.updateStatus();
    }

    async testConnection() {
        this.showNotification('Testing connection to ECR adapter...', 'info');
        const settings = {
            communication: this.communicationSelect.value,
            serial_port: this.serialPortSelect.value,
            socket_ip: this.socketIpInput.value,
            socket_port: this.socketPortInput.value,
            speed_baud: this.speedBaudSelect.value,
            data_bits: this.dataBitsInput.value,
            stop_bits: this.stopBitsSelect.value,
            parity: this.paritySelect.value,
            // enable_rest_api removed - REST API is now mandatory
            enable_ssl: this.enableSslCheck.checked,
            edc_serial_number: this.edcSerialNumberInput.value
        };
        try {
            const response = await fetch('/api/test_connection', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(settings)
            });
            const result = await response.json();
            if (response.ok) {
                this.showNotification(`${result.message} (${result.mode})`, 'success');
                this.isConnected = true;
            } else {
                this.showNotification(`Connection failed: ${result.message}`, 'error');
                this.isConnected = false;
            }
        } catch (error) {
            this.showNotification(`Connection test failed: ${error.message}`, 'error');
            this.isConnected = false;
        }
        this.updateStatus();
    }

    downloadLog() {
        // Show password modal instead of directly downloading
        const passwordModal = new bootstrap.Modal(document.getElementById('passwordModal'));
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
            
            // Download with password verification
            window.open(`/api/download_log?password=${encodeURIComponent(password)}`, '_blank');
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
        
        // REST API - mandatory for both Serial and Socket communication
        this.enableRestApiCheck.checked = true;
        this.enableRestApiCheck.disabled = true;
        
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
