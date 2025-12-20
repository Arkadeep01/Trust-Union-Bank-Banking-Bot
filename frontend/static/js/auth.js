// auth.js - improved: consistent storage of tokens and customerId, safe fetch options

// keep customerIdForOTP for the OTP flow, but also persist the canonical 'customerId' key used elsewhere
let customerIdForOTP = null;

async function handleLoginStart() {
  const identifier = document.getElementById('identifier').value;
  try {
    const resp = await fetch(API_ENDPOINTS.loginStart, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include', // allow cookies if server sets them
      body: JSON.stringify({ identifier })
    });
    const data = await resp.json();
    if (resp.ok && data.success) {
      customerIdForOTP = data.customer_id;
      localStorage.setItem('customerId', String(data.customer_id)); // persist canonical key
      document.getElementById('otpSection') && (document.getElementById('otpSection').style.display = 'block');
      showMessage('OTP sent successfully! Please check your registered mobile/email.', 'success');
    } else {
      showMessage(data.message || 'Failed to send OTP. Please try again.', 'error');
    }
  } catch (err) {
    console.error('Login start error:', err);
    showMessage('An error occurred while starting login. Please try again.', 'error');
  }
}

async function handleOTPVerify() {
  const otp = document.getElementById('otp').value;
  if (!customerIdForOTP && !localStorage.getItem('customerId')) {
    showMessage('Please start the login process first.', 'error');
    return;
  }
  const cid = customerIdForOTP || parseInt(localStorage.getItem('customerId'), 10);

  try {
    const resp = await fetch(API_ENDPOINTS.loginVerify, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ customer_id: cid, otp_code: otp })
    });
    const data = await resp.json();
    if (resp.ok && data.success && data.access_token) {
      localStorage.setItem('authToken', data.access_token);
      if (data.refresh_token) localStorage.setItem('refreshToken', data.refresh_token);
      localStorage.setItem('customerId', String(cid));
      // update globals used by chat/dashboard
      window.authToken = data.access_token;
      window.customerId = String(cid);
      // redirect or close login modal
      window.location.href = '/personal-banking';
    } else {
      showMessage(data.reason || 'Invalid OTP. Please try again.', 'error');
    }
  } catch (err) {
    console.error('OTP verify error:', err);
    showMessage('An error occurred verifying OTP. Please try again.', 'error');
  }
}

function showMessage(message, type) {
  const form = document.querySelector('.auth-form');
  const existingMessage = document.querySelector('.error-message, .success-message');
  if (existingMessage) existingMessage.remove();
  const messageDiv = document.createElement('div');
  messageDiv.className = type === 'error' ? 'error-message' : 'success-message';
  messageDiv.textContent = message;
  if (form) form.insertBefore(messageDiv, form.firstChild);
}

document.addEventListener('DOMContentLoaded', () => {
  // wire up forms (if present)
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      await handleLoginStart();
    });
  }
  const otpForm = document.getElementById('otpForm');
  if (otpForm) {
    otpForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      await handleOTPVerify();
    });
  }
});
