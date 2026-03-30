let generatedCaptcha = "";

// Firebase Configuration
const firebaseConfig = {
    apiKey: "AIzaSyDwWaMZOWjvNVNt0F6oy8_j8TIvi0KghkI",
    authDomain: "civix-2fad9.firebaseapp.com",
    projectId: "civix-2fad9",
    storageBucket: "civix-2fad9.firebasestorage.app",
    messagingSenderId: "969275853188",
    appId: "1:969275853188:web:0543ec053371f71ecab5d1",
    measurementId: "G-23NJY8HHKV"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const provider = new firebase.auth.GoogleAuthProvider();

function generateCaptcha() {
    const chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    generatedCaptcha = "";
    for (let i = 0; i < 6; i++) {
        generatedCaptcha += chars[Math.floor(Math.random() * chars.length)];
    }
    document.getElementById("captchaBox").innerText = generatedCaptcha;
}

// Initial Captcha Load
if (document.getElementById("captchaBox")) {
    generateCaptcha();
}

let authMode = 'owner';

function setAuthMode(mode) {
    authMode = mode;
    document.getElementById('toggleOwner').classList.toggle('active', mode === 'owner');
    document.getElementById('toggleEmployee').classList.toggle('active', mode === 'employee');
    
    document.getElementById('ownerFields').classList.toggle('hidden', mode !== 'owner');
    document.getElementById('employeeFields').classList.toggle('hidden', mode !== 'employee');
    
    document.getElementById('googleSection').classList.toggle('hidden', mode === 'employee');
    document.getElementById('submitBtn').innerText = mode === 'owner' ? 'Enter Portal (Owner)' : 'Login (Employee)';
}

document.getElementById("mainForm").addEventListener("submit", async function(e) {
    e.preventDefault();
    
    // 1. Captcha Verification
    const userInput = document.getElementById("captchaInput").value;
    if (userInput.toUpperCase() !== generatedCaptcha) {
        alert("Incorrect Captcha. Please try again.");
        generateCaptcha();
        return;
    }

    // 2. Capture details based on mode
    let email, password, name;
    if (authMode === 'owner') {
        email = document.getElementById("ownerEmail").value;
        password = document.getElementById("ownerPass").value;
        name = document.getElementById("ownerName").value || "Company Owner";
    } else {
        email = document.getElementById("empEmail").value;
        password = document.getElementById("empPass").value;
        name = document.getElementById("empNameDisplay").value || "Employee";
    }

    if (!email || !password) {
        alert("Please fill out your Email and Password.");
        return;
    }

    // 3. Authenticate with Firebase
    try {
        let userCredential;
        
        // Strategy: Try to sign in. If it fails with 'auth/user-not-found' (and it's Owner mode), try to create.
        try {
            userCredential = await auth.signInWithEmailAndPassword(email, password);
            console.log("Firebase Login (Email/Pass) Successful");
        } catch (signInError) {
            console.log("Sign-in failed, checking if registration is needed:", signInError.code);
            
            // Allow registration for both Owners (first user) and Employees (creates Pending request)
            if (signInError.code === 'auth/user-not-found' || signInError.code === 'auth/invalid-credential') {
                console.log("Trying to register new user...");
                userCredential = await auth.createUserWithEmailAndPassword(email, password);
                console.log("Firebase Registration Successful");
            } else {
                throw signInError; // Re-throw for general error handler
            }
        }

        const user = userCredential.user;
        const idToken = await user.getIdToken();

        // 4. Send token to Backend for verification & session
        await verifyWithBackend(idToken, name);

    } catch (err) {
        console.error("Firebase Auth Error:", err);
        let msg = "❌ Auth Failed: " + err.message;
        
        if (err.code === 'auth/wrong-password') {
            msg = "Wrong password. Please try again.";
        } else if (err.code === 'auth/invalid-credential') {
            msg = "Wrong email or password. Please try again.";
        } else if (err.code === 'auth/email-already-in-use') {
            msg = "Wrong password. Please try again.";
        } else if (err.code === 'auth/invalid-email') {
            msg = "Please enter a valid email address.";
        } else if (err.code === 'auth/user-disabled') {
            msg = "This account has been disabled.";
        }
        
        alert(msg);
        generateCaptcha();
    }
});

// Refactored Verification Logic
async function verifyWithBackend(idToken, displayName = null) {
    console.log("Verifying with backend...");
    try {
        const response = await fetch('/api/auth/firebase', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                idToken: idToken,
                name: displayName // Optional: Pass name if Firebase doesn't have it yet (for new users)
            })
        });

        const data = await response.json();

        if (response.ok) {
            const verifiedUser = data.user;
            
            if (data.status === "Pending") {
                alert("Your account is pending approval. You will be able to log in once an Admin approves your request.");
                window.location.href = "pending.html";
                return;
            }

            // Save to localStorage
            localStorage.setItem("idToken", idToken);
            localStorage.setItem("registeredCompany", verifiedUser.name || verifiedUser.email);
            localStorage.setItem("regCompany", verifiedUser.name || verifiedUser.email);
            localStorage.setItem("regEmail", verifiedUser.email);
            localStorage.setItem("userRole", verifiedUser.role);
            localStorage.setItem("isLoggedIn", "true");
            if (verifiedUser.picture) localStorage.setItem("userPhoto", verifiedUser.picture);

            // Redirect based on role
            if (verifiedUser.role === "Admin") {
                window.location.href = "admin.html";
            } else {
                window.location.href = "home.html";
            }
        } else {
            console.error("Backend error:", data.message);
            alert("❌ " + data.message + "\n\n(Make sure 'server/firebase-adminsdk.json' is present on the server)");
        }
    } catch (err) {
        console.error("Fetch error:", err);
        alert("Server connection failed. Please ensure the backend is running.");
    }
}

async function logout() {
    await auth.signOut();
    localStorage.clear();
    window.location.href = "index.html";
}

// Preview Image function... (kept as is)
function previewImage(event) {
    const reader = new FileReader();
    const file = event.target.files[0];
    reader.onload = function() {
        const imageData = reader.result;
        document.getElementById('profilePreview').src = imageData;
        localStorage.setItem("companyLogo", imageData);
        document.getElementById('sidebarLogo').innerHTML = `<img src="${imageData}" style="width:100%; height:100%; border-radius:12px; object-fit:cover;">`;
    };
    if (file) reader.readAsDataURL(file);
}

function loadSavedLogo() {
    const savedLogo = localStorage.getItem("companyLogo");
    const sidebarLogoDiv = document.getElementById('sidebarLogo');
    if (savedLogo && sidebarLogoDiv) {
        sidebarLogoDiv.innerHTML = `<img src="${savedLogo}" style="width:100%; height:100%; border-radius:12px; object-fit:cover;">`;
    }
}

// Google Login Integration
document.addEventListener('DOMContentLoaded', function() {
    const googleBtn = document.getElementById('googleLoginBtn');
    if (googleBtn) {
        googleBtn.addEventListener('click', async function() {
            try {
                const result = await auth.signInWithPopup(provider);
                const user = result.user;
                const idToken = await user.getIdToken();
                console.log("Firebase Google Login Successful");
                await verifyWithBackend(idToken);
            } catch (error) {
                console.error("Google Login Error:", error);
                let msg = "Google login failed: " + error.message;
                const currentOrigin = window.location.origin;
                
                if (error.code === 'auth/unauthorized-domain') {
                    msg = `❌ Domain Not Authorized!\n\nYou are on: ${currentOrigin}\n\nPlease add this to your Firebase Console:\nAuthentication > Settings > Authorized Domains.`;
                    
                    if (window.location.hostname !== 'localhost') {
                        msg += "\n\nTIP: Try using http://localhost:5000 instead of the IP address.";
                    }
                } else if (error.code === 'auth/popup-closed-by-user') {
                    msg = "Login popup closed. Please try again.";
                }
                alert(msg);
            }
        });
    }
});

// Run on load
window.addEventListener('DOMContentLoaded', loadSavedLogo);