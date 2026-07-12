/**
 * auth_guard.js - THE HARD LOCK
 * This must be the VERY FIRST script in the <head>.
 */
(function authGuard() {
    // 1. Immediately hide the body to prevent "flickering" 
    document.documentElement.style.display = 'none';

    function checkAuth() {
        const email = localStorage.getItem('regEmail');
        const isLoggedIn = localStorage.getItem('isLoggedIn');
        const status = localStorage.getItem('userStatus') || localStorage.getItem('status');

        const PUBLIC_PAGES = ['index.html', 'contact.html', 'about.html'];
        const currentPage = window.location.pathname.split('/').pop() || 'index.html';

        // 2. Not logged in → Send to landing page if trying to access internal content
        if (!email || isLoggedIn !== 'true') {
            if (!PUBLIC_PAGES.includes(currentPage)) {
                console.warn("🔐 Forbidden: Unauthorized access. Redirecting to Public Portal...");
                window.location.replace('index.html');
                return;
            }
        }

        // 3. Logged in but Pending → Send to pending page
        if (status === 'Pending' && !window.location.pathname.includes('pending.html')) {
            window.location.replace('pending.html');
            return;
        }

        // 4. All good? Show the page
        document.documentElement.style.display = 'block';
    }

    checkAuth();

    // Listen to pageshow to handle bfcache (back/forward navigation)
    window.addEventListener('pageshow', function(event) {
        checkAuth();
    });

    // 5. Global helper for secure API calls
    window.authorizedFetch = async function(url, options = {}) {
        const idToken = localStorage.getItem('idToken');
        if (!options.headers) options.headers = {};
        options.headers['Authorization'] = `Bearer ${idToken}`;
        return fetch(url, options);
    };

    // 6. Global Logout Handler (closes affairs and redirects to index)
    window.handleLogout = function() {
        if (confirm("Are you sure you want to logout from the Civil Survey Portal?")) {
            const darkMode = localStorage.getItem('darkMode');
            localStorage.clear();
            if (darkMode) {
                localStorage.setItem('darkMode', darkMode);
            }
            window.location.replace("index.html");
        }
    };

    // 7. Global Back Handler (redirects to home if logged in, index otherwise)
    window.handleBack = function() {
        if (localStorage.getItem('isLoggedIn') === 'true') {
            window.location.href = "home.html";
        } else {
            window.location.href = "index.html";
        }
    };

    // 8. Auto-apply Dark Theme to body on load
    document.addEventListener("DOMContentLoaded", function() {
        if (localStorage.getItem("darkMode") === "enabled") {
            document.body.classList.add("dark_theme");
        }
    });

    // 9. SECURITY: Anti-Copy & Anti-Screenshot Handlers
    
    // Prevent Right Click
    document.addEventListener('contextmenu', event => event.preventDefault());

    // Prevent Keyboard Shortcuts (Ctrl+P, Ctrl+S, Ctrl+C, PrintScreen)
    document.addEventListener('keydown', (e) => {
        // Prevent Print Screen key
        if (e.key === 'PrintScreen') {
            navigator.clipboard.writeText('');
            e.preventDefault();
            return false;
        }
        
        // Prevent Ctrl+P (Print), Ctrl+S (Save), Ctrl+C (Copy), Mac OS Command key
        if (e.ctrlKey || e.metaKey) {
            if (e.key === 'p' || e.key === 's' || e.key === 'c' || e.key === 'P' || e.key === 'S' || e.key === 'C') {
                e.preventDefault();
                return false;
            }
        }
    });
    
    document.addEventListener('keyup', (e) => {
        if (e.key === 'PrintScreen') {
            navigator.clipboard.writeText('');
            e.preventDefault();
        }
    });

    // Prevent Snipping Tool / OS Screenshots via Focus Loss Blur
    window.addEventListener('blur', () => {
        document.body.style.filter = 'blur(20px)';
        document.body.style.opacity = '0.3';
    });
    window.addEventListener('focus', () => {
        document.body.style.filter = 'none';
        document.body.style.opacity = '1';
    });

})();



