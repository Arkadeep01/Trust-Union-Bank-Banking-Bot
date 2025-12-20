// Main application logic
document.addEventListener('DOMContentLoaded', () => {
    // Initialize contact form
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(contactForm);
            const data = {
                name: formData.get('name') || contactForm.querySelector('input[type="text"]').value,
                email: formData.get('email') || contactForm.querySelector('input[type="email"]').value,
                message: formData.get('message') || contactForm.querySelector('textarea').value
            };

            // Here you would typically send this to your backend
            alert('Thank you for your message! We will get back to you soon.');
            contactForm.reset();
        });
    }

    // Add smooth scroll to anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Add intersection observer for animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fade-in-up');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe service cards and other elements
    document.querySelectorAll('.service-card, .rbi-card, .feature-item').forEach(el => {
        observer.observe(el);
    });

    // Check authentication status
    checkAuthStatus();
});

function checkAuthStatus() {
    const token = localStorage.getItem('authToken');
    const navActions = document.querySelector('.nav-actions');
    
    if (token && navActions) {
        // User is logged in
        const loginBtn = navActions.querySelector('a[href="/login"]');
        const registerBtn = navActions.querySelector('a[href="/register"]');
        
        if (loginBtn) loginBtn.textContent = 'Dashboard';
        if (loginBtn) loginBtn.href = '/personal-banking';
        if (registerBtn) registerBtn.textContent = 'Logout';
        if (registerBtn) {
            registerBtn.href = '#';
            registerBtn.addEventListener('click', (e) => {
                e.preventDefault();
                logout();
            });
        }
    }
}

function logout() {
    localStorage.removeItem('authToken');
    localStorage.removeItem('customerId');
    localStorage.removeItem('sessionId');
    window.location.href = '/';
}

// Export for use in other scripts
if (typeof window !== 'undefined') {
    window.logout = logout;
    window.checkAuthStatus = checkAuthStatus;
}
