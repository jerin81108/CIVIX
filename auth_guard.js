/**
 * auth_guard.js - THE HARD LOCK
 * This must be the VERY FIRST script in the <head>.
 */
(function authGuard() {
    // 1. Immediately hide the body to prevent "flickering" 
    document.documentElement.style.display = 'none';

    const email = localStorage.getItem('regEmail');
    const isLoggedIn = localStorage.getItem('isLoggedIn');
    const status = localStorage.getItem('userStatus') || localStorage.getItem('status');

    // 2. Not logged in → Send to landing page
    if (!email || isLoggedIn !== 'true') {
        console.warn("🔐 Forbidden: Unauthorized access. Redirecting...");
        window.location.replace('index.html');
        return;
    }

    // 3. Logged in but Pending → Send to pending page
    if (status === 'Pending' && !window.location.pathname.includes('pending.html')) {
        window.location.replace('pending.html');
        return;
    }

    // 4. All good? Show the page
    document.documentElement.style.display = 'block';

    // 5. Global helper for secure API calls
    window.authorizedFetch = async function(url, options = {}) {
        const idToken = localStorage.getItem('idToken');
        if (!options.headers) options.headers = {};
        options.headers['Authorization'] = `Bearer ${idToken}`;
        return fetch(url, options);
    };
})();



