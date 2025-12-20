// Dashboard functionality
document.addEventListener('DOMContentLoaded', async () => {
    // Check authentication
    const token = localStorage.getItem('authToken');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    // Load user data
    await loadUserProfile();
    await loadAccounts();
    await loadBalance();
    await loadLoans();
});

async function loadUserProfile() {
    try {
        const response = await fetch(API_ENDPOINTS.userProfile, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const data = await response.json();
            const userNameEl = document.getElementById('userName');
            if (userNameEl && data.name) {
                userNameEl.textContent = data.name;
            }
            if (data.customer_id) {
                customerId = data.customer_id.toString();
                localStorage.setItem('customerId', customerId);
            }
        }
    } catch (error) {
        console.error('Failed to load user profile:', error);
    }
}

async function loadAccounts() {
    const accountsList = document.getElementById('accountsList');
    if (!accountsList) return;

    try {
        const response = await fetch(API_ENDPOINTS.userAccounts, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const data = await response.json();
            const accounts = data.accounts || [];

            if (accounts.length === 0) {
                accountsList.innerHTML = '<p class="empty-state">No accounts found</p>';
                return;
            }

            accountsList.innerHTML = accounts.map(account => `
                <div class="account-item">
                    <div class="account-info">
                        <div class="account-number">${maskAccountNumber(account.account_number || 'N/A')}</div>
                        <div class="account-type">${account.type || 'Account'}</div>
                    </div>
                    <div class="account-balance">₹${formatCurrency(account.balance || 0)}</div>
                </div>
            `).join('');
        } else {
            accountsList.innerHTML = '<p class="empty-state">Failed to load accounts</p>';
        }
    } catch (error) {
        console.error('Failed to load accounts:', error);
        accountsList.innerHTML = '<p class="empty-state">Error loading accounts</p>';
    }
}

async function loadBalance() {
    const totalBalanceEl = document.getElementById('totalBalance');
    if (!totalBalanceEl) return;

    try {
        const response = await fetch(API_ENDPOINTS.userBalance, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const data = await response.json();
            const balance = data.balance || 0;
            totalBalanceEl.innerHTML = `₹${formatCurrency(balance)}`;
        } else {
            totalBalanceEl.innerHTML = '₹0.00';
        }
    } catch (error) {
        console.error('Failed to load balance:', error);
        totalBalanceEl.innerHTML = '₹0.00';
    }
}

async function loadLoans() {
    const loansList = document.getElementById('loansList');
    if (!loansList) return;

    // This would typically call a loans API endpoint
    // For now, show empty state
    loansList.innerHTML = '<p class="empty-state">No active loans</p>';
}

function maskAccountNumber(accountNumber) {
    if (!accountNumber || accountNumber.length < 4) return '****';
    const last4 = accountNumber.slice(-4);
    return `****${last4}`;
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}
