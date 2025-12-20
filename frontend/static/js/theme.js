// Theme management
class ThemeManager {
    constructor() {
        this.init();
    }

    init() {
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => {
                this.toggleTheme();
            });
        }

        // Set initial theme icon
        this.updateThemeIcon();
    }

    toggleTheme() {
        const currentTheme = document.body.classList.contains('dark-theme') ? 'dark' : 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        updateTheme(newTheme);
        this.updateThemeIcon();
    }

    updateThemeIcon() {
        const themeIcon = document.querySelector('.theme-icon');
        if (themeIcon) {
            const isDark = document.body.classList.contains('dark-theme');
            themeIcon.textContent = isDark ? '☀️' : '🌙';
        }
    }
}

// Initialize theme manager
const themeManager = new ThemeManager();
