/**
 * file_manager.js - Centralized File Viewer & Sharing Engine
 * Works across desktop, tablet, and mobile devices.
 */

(function initFileManager() {
    // 1. Dynamic CSS Injection for premium styling
    const styles = `
        /* File Action Buttons */
        .file-action-btn {
            padding: 5px 12px;
            font-size: 12px;
            font-weight: 600;
            border-radius: 6px;
            border: 1px solid;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            font-family: inherit;
            margin: 2px;
            text-decoration: none !important;
        }
        
        .view-btn {
            background: rgba(52, 152, 219, 0.1);
            color: #3498db;
            border-color: rgba(52, 152, 219, 0.3);
        }
        .view-btn:hover {
            background: #3498db;
            color: #fff;
            transform: translateY(-1px);
            box-shadow: 0 4px 10px rgba(52, 152, 219, 0.2);
        }

        .share-btn {
            background: rgba(46, 204, 113, 0.1);
            color: #2ecc71;
            border-color: rgba(46, 204, 113, 0.3);
        }
        .share-btn:hover {
            background: #2ecc71;
            color: #fff;
            transform: translateY(-1px);
            box-shadow: 0 4px 10px rgba(46, 204, 113, 0.2);
        }

        /* Dark Theme adjustment for page-wide action buttons */
        body.dark_theme .view-btn {
            background: rgba(52, 152, 219, 0.2);
            color: #5dade2;
            border-color: rgba(52, 152, 219, 0.4);
        }
        body.dark_theme .share-btn {
            background: rgba(46, 204, 113, 0.2);
            color: #58d68d;
            border-color: rgba(46, 204, 113, 0.4);
        }

        /* Modal Overlay - Glassmorphic */
        .fm-modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(15, 23, 42, 0.6);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 999999;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s ease, visibility 0.3s ease;
        }

        .fm-modal-overlay.active {
            opacity: 1;
            visibility: visible;
        }

        /* Modal Box */
        .fm-modal-box {
            background: #fff;
            width: 90%;
            max-width: 800px;
            max-height: 85vh;
            border-radius: 16px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            transform: translateY(20px);
            transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
            position: relative;
        }

        body.dark_theme .fm-modal-box {
            background: #1e293b;
            color: #f1f5f9;
        }

        .fm-modal-overlay.active .fm-modal-box {
            transform: translateY(0);
        }

        /* Modal Header */
        .fm-modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 24px;
            border-bottom: 1px solid #e2e8f0;
            background: #f8fafc;
        }

        body.dark_theme .fm-modal-header {
            background: #0f172a;
            border-bottom-color: #334155;
        }

        .fm-modal-title {
            font-size: 16px;
            font-weight: 700;
            color: #1e293b;
            margin: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 80%;
        }

        body.dark_theme .fm-modal-title {
            color: #f8fafc;
        }

        .fm-close-btn {
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: #64748b;
            transition: color 0.2s;
            padding: 4px 8px;
            border-radius: 6px;
        }
        .fm-close-btn:hover {
            color: #ef4444;
            background: rgba(239, 68, 68, 0.1);
        }

        /* Modal Body */
        .fm-modal-body {
            padding: 24px;
            overflow-y: auto;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 250px;
            background: #f8fafc;
        }

        body.dark_theme .fm-modal-body {
            background: #0f172a;
        }

        /* Image Display */
        .fm-image-wrapper {
            position: relative;
            max-width: 100%;
            max-height: 60vh;
            overflow: hidden;
            display: flex;
            justify-content: center;
            align-items: center;
            border-radius: 8px;
            background: rgba(0,0,0,0.05);
            padding: 10px;
        }
        .fm-preview-img {
            max-width: 100%;
            max-height: 55vh;
            object-fit: contain;
            transition: transform 0.2s ease;
            transform-origin: center center;
        }

        /* PDF Frame Container */
        .fm-pdf-container {
            width: 100%;
            height: 60vh;
            border-radius: 8px;
            overflow: hidden;
        }

        /* Text preview */
        .fm-text-container {
            width: 100%;
            max-height: 55vh;
            overflow-y: auto;
            background: #0f172a;
            color: #38bdf8;
            padding: 16px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 13px;
            white-space: pre-wrap;
            text-align: left;
            border: 1px solid #1e293b;
        }

        /* Fallback Document Card */
        .fm-fallback-card {
            text-align: center;
            padding: 30px;
            background: #fm-modal-box;
            border: 1px solid #e2e8f0;
            max-width: 400px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            border-radius: 12px;
        }

        body.dark_theme .fm-fallback-card {
            background: #1e293b;
            border-color: #334155;
        }

        .fm-fallback-icon {
            font-size: 48px;
            margin-bottom: 16px;
            display: block;
        }

        .fm-fallback-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 700;
            text-decoration: none;
            cursor: pointer;
            margin: 6px;
            font-size: 14px;
            border: none;
            transition: all 0.2s;
        }

        .fm-fallback-btn.dl {
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
        }
        .fm-fallback-btn.dl:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        }

        .fm-fallback-btn.sh {
            background: linear-gradient(135deg, #3b82f6, #2563eb);
            color: white;
        }
        .fm-fallback-btn.sh:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }

        /* Image Toolbar controls */
        .fm-img-toolbar {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            background: rgba(255,255,255,0.9);
            padding: 6px 12px;
            border-radius: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }

        body.dark_theme .fm-img-toolbar {
            background: rgba(30, 41, 59, 0.9);
        }

        .fm-toolbar-btn {
            background: none;
            border: none;
            font-size: 16px;
            cursor: pointer;
            color: #475569;
            padding: 6px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }

        .fm-toolbar-btn:hover {
            background: rgba(0,0,0,0.05);
            color: #1e293b;
        }

        body.dark_theme .fm-toolbar-btn:hover {
            background: rgba(255,255,255,0.1);
            color: #fff;
        }

        /* Custom Share Dashboard Grid */
        .fm-share-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            width: 100%;
            margin-top: 15px;
        }

        @media (max-width: 500px) {
            .fm-share-grid {
                grid-template-columns: 1fr;
            }
        }

        .fm-share-option {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px;
            border-radius: 12px;
            background: #f8fafc;
            border: 1.5px solid #e2e8f0;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: left;
            text-decoration: none;
            color: inherit;
        }

        body.dark_theme .fm-share-option {
            background: #1e293b;
            border-color: #334155;
        }

        .fm-share-option:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            border-color: #3b82f6;
        }

        .fm-share-opt-icon {
            font-size: 24px;
        }

        .fm-share-opt-title {
            font-weight: 700;
            font-size: 14px;
            margin-bottom: 2px;
            display: block;
        }

        .fm-share-opt-desc {
            font-size: 11px;
            color: #64748b;
        }
    `;

    const styleEl = document.createElement('style');
    styleEl.innerHTML = styles;
    document.head.appendChild(styleEl);

    // 2. Inject Modal markup directly in body
    const modalMarkup = `
        <div id="fm_modal" class="fm-modal-overlay">
            <div class="fm-modal-box">
                <div class="fm-modal-header">
                    <h3 id="fm_title" class="fm-modal-title">File View</h3>
                    <button class="fm-close-btn" onclick="window.closeFileManagerModal()">✕</button>
                </div>
                <div id="fm_body" class="fm-modal-body">
                    <!-- Dynamic view content lands here -->
                </div>
            </div>
        </div>
    `;

    // Function to inject modal if not already present
    function injectModal() {
        if (!document.getElementById("fm_modal")) {
            const wrapper = document.createElement('div');
            wrapper.innerHTML = modalMarkup;
            document.body.appendChild(wrapper.firstElementChild);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", injectModal);
    } else {
        injectModal();
    }

    // Rotation and scale state
    let imgScale = 1;
    let imgRotation = 0;

    // 3. Exposed globally: preview file function
    window.previewFile = function(filePath, fileName) {
        if (!filePath) return alert("Invalid file path");
        
        injectModal(); // Ensure modal is present

        imgScale = 1;
        imgRotation = 0;

        const modal = document.getElementById("fm_modal");
        const titleEl = document.getElementById("fm_title");
        const bodyEl = document.getElementById("fm_body");

        titleEl.textContent = fileName || "Attachment Preview";
        bodyEl.innerHTML = "<p>Loading Preview...</p>";
        
        modal.classList.add("active");

        const ext = getExtension(filePath).toLowerCase();

        // Determine content renderer
        if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'].includes(ext)) {
            // Render Image
            bodyEl.innerHTML = `
                <div class="fm-image-wrapper">
                    <img id="fm_preview_img" class="fm-preview-img" src="${filePath}" alt="${fileName}">
                </div>
                <div class="fm-img-toolbar">
                    <button class="fm-toolbar-btn" onclick="window.fmZoom(1.2)" title="Zoom In">➕</button>
                    <button class="fm-toolbar-btn" onclick="window.fmZoom(0.8)" title="Zoom Out">➖</button>
                    <button class="fm-toolbar-btn" onclick="window.fmRotate(90)" title="Rotate Right">🔄</button>
                    <button class="fm-toolbar-btn" onclick="window.fmResetImg()" title="Reset Size">⚙️</button>
                </div>
            `;
        } else if (ext === 'pdf') {
            // Render PDF
            bodyEl.innerHTML = `
                <div class="fm-pdf-container">
                    <iframe src="${filePath}" width="100%" height="100%" style="border:none;"></iframe>
                </div>
            `;
        } else if (['txt', 'log', 'json', 'xml', 'csv', 'js', 'py', 'html', 'css'].includes(ext)) {
            // Render Text/Code preview
            bodyEl.innerHTML = `<div style="text-align: center;"><p>Fetching text details...</p></div>`;
            fetch(filePath)
                .then(res => {
                    if (!res.ok) throw new Error("Could not load contents");
                    return res.text();
                })
                .then(text => {
                    const escaped = escapeHtml(text);
                    bodyEl.innerHTML = `<pre id="fm_code_view" class="fm-text-container">${escaped}</pre>`;
                })
                .catch(err => {
                    bodyEl.innerHTML = `
                        <div class="fm-fallback-card">
                            <span class="fm-fallback-icon">⚠️</span>
                            <h4>Content Fetch Failed</h4>
                            <p>${err.message}</p>
                            <a href="${filePath}" download class="fm-fallback-btn dl">📥 Download Instead</a>
                        </div>
                    `;
                });
        } else {
            // Fallback Dashboard (Excel, AutoCAD .dwg, Word)
            let icon = "📄";
            if (['xls', 'xlsx'].includes(ext)) icon = "📊";
            else if (['doc', 'docx'].includes(ext)) icon = "📝";
            else if (ext === 'dwg') icon = "📐";
            else if (['zip', 'rar', '7z'].includes(ext)) icon = "📦";

            bodyEl.innerHTML = `
                <div class="fm-fallback-card" style="background:#fff; color:#333; padding: 25px; border-radius: 12px; text-align: center; border: 1px solid #ddd;">
                    <span class="fm-fallback-icon">${icon}</span>
                    <h4 style="margin: 8px 0;">${fileName || "Attachment Document"}</h4>
                    <p style="font-size:13px; color:#64748b; margin-bottom: 20px;">Browser previews are not supported for .${ext} files. You can safely download or share it below.</p>
                    <div>
                        <a href="${filePath}" download class="fm-fallback-btn dl">📥 Download File</a>
                        <button onclick="window.shareFile('${filePath}', '${fileName}')" class="fm-fallback-btn sh">📤 Share File</button>
                    </div>
                </div>
            `;
        }
    };

    // Zoom/Rotation functions
    window.fmZoom = function(factor) {
        const img = document.getElementById("fm_preview_img");
        if (img) {
            imgScale *= factor;
            if (imgScale < 0.2) imgScale = 0.2;
            if (imgScale > 5) imgScale = 5;
            applyImgTransforms(img);
        }
    };

    window.fmRotate = function(deg) {
        const img = document.getElementById("fm_preview_img");
        if (img) {
            imgRotation = (imgRotation + deg) % 360;
            applyImgTransforms(img);
        }
    };

    window.fmResetImg = function() {
        const img = document.getElementById("fm_preview_img");
        if (img) {
            imgScale = 1;
            imgRotation = 0;
            applyImgTransforms(img);
        }
    };

    function applyImgTransforms(img) {
        img.style.transform = `scale(${imgScale}) rotate(${imgRotation}deg)`;
    }

    // Close preview modal
    window.closeFileManagerModal = function() {
        const modal = document.getElementById("fm_modal");
        if (modal) {
            modal.classList.remove("active");
            // Clear body to stop any video/iframe audio if running
            document.getElementById("fm_body").innerHTML = "";
        }
    };

    // Close modal on escape or background click
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") window.closeFileManagerModal();
    });
    
    document.addEventListener("click", (e) => {
        const modal = document.getElementById("fm_modal");
        if (e.target === modal) window.closeFileManagerModal();
    });

    // 4. Global sharing function
    window.shareFile = async function(filePath, fileName) {
        if (!filePath) return alert("Invalid file details for sharing");

        injectModal(); // Ensure modal is present

        const absoluteUrl = window.location.origin + filePath;
        const cleanName = fileName || "Survey Record File";

        // Try native share sheet (primarily on iOS, Android, and Safari/Chrome Mobile)
        if (navigator.share) {
            try {
                await navigator.share({
                    title: cleanName,
                    text: `B.K Builders - Shared Survey File: ${cleanName}`,
                    url: absoluteUrl
                });
                return; // success!
            } catch (e) {
                // If user aborted or error, fall through to manual sharing modal
                console.log("Native share failed or closed, loading fallback menu.");
            }
        }

        // Desktop / Fallback Share Dashboard
        const modal = document.getElementById("fm_modal");
        const titleEl = document.getElementById("fm_title");
        const bodyEl = document.getElementById("fm_body");

        titleEl.textContent = `Send / Share - ${cleanName}`;
        modal.classList.add("active");

        const textMsg = `Shared Survey File from B.K Builders: ${cleanName}`;
        const waUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(textMsg + '\n' + absoluteUrl)}`;
        const emailUrl = `mailto:?subject=${encodeURIComponent(cleanName)}&body=${encodeURIComponent(textMsg + '\n\n' + absoluteUrl)}`;

        bodyEl.innerHTML = `
            <div style="width: 100%; max-width: 500px; text-align: center;">
                <span style="font-size: 40px; margin-bottom: 10px; display: block;">📤</span>
                <h4 style="margin-bottom: 6px;">Send Attachment</h4>
                <p style="font-size: 13px; color:#64748b; margin-bottom: 20px;">Choose a platform below to send the survey document link.</p>
                
                <div class="fm-share-grid">
                    <a href="${waUrl}" target="_blank" class="fm-share-option" style="border-left: 6px solid #25d366;">
                        <span class="fm-share-opt-icon">💬</span>
                        <div>
                            <span class="fm-share-opt-title" style="color:#25d366;">WhatsApp</span>
                            <span class="fm-share-opt-desc">Send to contacts or chats</span>
                        </div>
                    </a>
                    
                    <a href="${emailUrl}" class="fm-share-option" style="border-left: 6px solid #ea4335;">
                        <span class="fm-share-opt-icon">✉️</span>
                        <div>
                            <span class="fm-share-opt-title" style="color:#ea4335;">Email</span>
                            <span class="fm-share-opt-desc">Compose email invitation</span>
                        </div>
                    </a>
                    
                    <div onclick="window.fmCopyLink('${absoluteUrl}')" class="fm-share-option" style="border-left: 6px solid #3b82f6; cursor: pointer;">
                        <span class="fm-share-opt-icon">🔗</span>
                        <div>
                            <span class="fm-share-opt-title" style="color:#3b82f6;">Copy Link</span>
                            <span class="fm-share-opt-desc">Copy URL to clipboard</span>
                        </div>
                    </div>

                    <a href="${filePath}" download class="fm-share-option" style="border-left: 6px solid #10b981;">
                        <span class="fm-share-opt-icon">📥</span>
                        <div>
                            <span class="fm-share-opt-title" style="color:#10b981;">Download</span>
                            <span class="fm-share-opt-desc">Download directly to device</span>
                        </div>
                    </a>
                </div>
            </div>
        `;
    };

    window.fmCopyLink = function(url) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(url).then(() => {
                alert("File URL successfully copied to clipboard!");
            }).catch(() => {
                fallbackCopyText(url);
            });
        } else {
            fallbackCopyText(url);
        }
    };

    function fallbackCopyText(text) {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";  // Avoid scrolling to bottom
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy');
            alert("File URL successfully copied to clipboard!");
        } catch (err) {
            alert("Could not copy link automatically. Please copy the URL manually: " + text);
        }
        document.body.removeChild(textArea);
    }

    // Helper functions
    function getExtension(path) {
        return path.split('.').pop() || '';
    }

    function escapeHtml(string) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return string.replace(/[&<>"']/g, function(m) { return map[m]; });
    }

})();
