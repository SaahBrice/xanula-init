/**
 * Django Admin Upload Progress Enhancement
 * Shows loading indicator during file uploads
 */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        // Create overlay element
        const overlay = document.createElement('div');
        overlay.id = 'upload-overlay';
        overlay.innerHTML = `
            <div class="upload-modal">
                <div class="upload-spinner"></div>
                <h3>Uploading Files...</h3>
                <p class="upload-message">This may take a few minutes for large files.</p>
                <p class="upload-warning">Please do not close this page.</p>
                <div class="upload-progress-container">
                    <div class="upload-progress-bar"></div>
                </div>
                <p class="upload-percent">0%</p>
            </div>
        `;
        document.body.appendChild(overlay);

        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            #upload-overlay {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.7);
                z-index: 99999;
                justify-content: center;
                align-items: center;
            }
            #upload-overlay.active {
                display: flex;
            }
            .upload-modal {
                background: white;
                padding: 40px 60px;
                border-radius: 12px;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 400px;
            }
            .upload-spinner {
                width: 50px;
                height: 50px;
                border: 4px solid #e0e0e0;
                border-top-color: #417690;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 20px;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .upload-modal h3 {
                margin: 0 0 10px;
                color: #333;
                font-size: 20px;
            }
            .upload-message {
                color: #666;
                margin: 0 0 5px;
                font-size: 14px;
            }
            .upload-warning {
                color: #c9302c;
                font-weight: bold;
                margin: 0 0 20px;
                font-size: 13px;
            }
            .upload-progress-container {
                background: #e0e0e0;
                border-radius: 10px;
                height: 10px;
                overflow: hidden;
                margin-bottom: 10px;
            }
            .upload-progress-bar {
                background: linear-gradient(90deg, #8B2635, #2D4739);
                height: 100%;
                width: 0%;
                transition: width 0.3s ease;
                border-radius: 10px;
            }
            .upload-percent {
                color: #417690;
                font-weight: bold;
                margin: 0;
                font-size: 18px;
            }
        `;
        document.head.appendChild(style);

        // Find forms with file inputs
        const forms = document.querySelectorAll('form');
        forms.forEach(function (form) {
            const fileInputs = form.querySelectorAll('input[type="file"]');
            if (fileInputs.length === 0) return;

            // Check if any file is selected
            let hasFiles = false;
            fileInputs.forEach(function (input) {
                input.addEventListener('change', function () {
                    hasFiles = this.files.length > 0;
                });
            });

            // Intercept form submission for progress tracking
            form.addEventListener('submit', function (e) {
                // Check if there are files to upload
                let filesExist = false;
                let totalSize = 0;
                fileInputs.forEach(function (input) {
                    if (input.files.length > 0) {
                        filesExist = true;
                        for (let i = 0; i < input.files.length; i++) {
                            totalSize += input.files[i].size;
                        }
                    }
                });

                // Only show overlay for actual file uploads
                if (filesExist && totalSize > 1000000) { // > 1MB
                    e.preventDefault();

                    overlay.classList.add('active');
                    const progressBar = overlay.querySelector('.upload-progress-bar');
                    const percentText = overlay.querySelector('.upload-percent');

                    // Create FormData and XMLHttpRequest for progress tracking
                    const formData = new FormData(form);
                    const xhr = new XMLHttpRequest();

                    xhr.upload.addEventListener('progress', function (e) {
                        if (e.lengthComputable) {
                            const percent = Math.round((e.loaded / e.total) * 100);
                            progressBar.style.width = percent + '%';
                            percentText.textContent = percent + '%';
                        }
                    });

                    xhr.addEventListener('load', function () {
                        if (xhr.status >= 200 && xhr.status < 400) {
                            // Success - redirect or reload
                            progressBar.style.width = '100%';
                            percentText.textContent = '100% - Complete!';
                            setTimeout(function () {
                                window.location.href = xhr.responseURL || window.location.href;
                            }, 500);
                        } else {
                            // Error
                            overlay.classList.remove('active');
                            alert('Upload failed. Please try again.');
                        }
                    });

                    xhr.addEventListener('error', function () {
                        overlay.classList.remove('active');
                        alert('Upload failed. Please check your connection and try again.');
                    });

                    xhr.open(form.method || 'POST', form.action || window.location.href);
                    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                    xhr.send(formData);
                }
            });
        });
    });
})();
