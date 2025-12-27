// API Configuration
const API_URL = '';

// State
let token = localStorage.getItem('token');
let isSignUp = false;
let files = [];
let activeTab = 'files';
let selectedFileIds = []; // Track selected files for chat filtering
let pollingTimer = null; // For file status polling

// DOM Elements
const authContainer = document.getElementById('auth-container');
const dashboardContainer = document.getElementById('dashboard-container');
const authForm = document.getElementById('auth-form');
const authError = document.getElementById('auth-error');
const authTitle = document.getElementById('auth-title');
const authSubtitle = document.getElementById('auth-subtitle');
const authBtn = document.getElementById('auth-btn');
const authToggle = document.getElementById('auth-toggle');
const authToggleText = document.getElementById('auth-toggle-text');
const logoutBtn = document.getElementById('logout-btn');
const profileToggle = document.getElementById('profile-toggle');
const profileMenu = document.getElementById('profile-menu');
const userProfileBtn = document.getElementById('user-profile-btn');
const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const uploadProgress = document.getElementById('upload-progress');
const progressFill = document.getElementById('progress-fill');
const progressPercent = document.getElementById('progress-percent');
const filesGrid = document.getElementById('files-grid');
const emptyState = document.getElementById('empty-state');
const fileCount = document.getElementById('file-count');
const storageFill = document.getElementById('storage-fill');
const refreshBtn = document.getElementById('refresh-btn');
const uploadBtn = document.getElementById('upload-btn');
const filesTab = document.getElementById('files-tab');
const chatTab = document.getElementById('chat-tab');
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const toast = document.getElementById('toast');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();

    // Check for verification token
    const urlParams = new URLSearchParams(window.location.search);
    const verifyToken = urlParams.get('token');

    if (verifyToken) {
        verifyEmail(verifyToken);
        return; // Skip other checks
    }

    if (token) {
        showDashboard();
        fetchFiles();
    } else {
        showAuth();
    }
});

// Event Listeners
function setupEventListeners() {
    // Auth
    authForm.addEventListener('submit', handleAuth);
    authToggle.addEventListener('click', toggleAuthMode);
    logoutBtn.addEventListener('click', logout);

    // Profile Dropdown
    if (profileToggle && profileMenu) {
        profileToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            profileMenu.classList.toggle('show');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!profileMenu.contains(e.target) && !profileToggle.contains(e.target)) {
                profileMenu.classList.remove('show');
            }
        });

        // User Profile button
        if (userProfileBtn) {
            userProfileBtn.addEventListener('click', () => {
                showUserProfile();
            });
        }
    }

    // Upload
    uploadZone.addEventListener('click', () => fileInput.click());
    uploadZone.addEventListener('dragover', handleDragOver);
    uploadZone.addEventListener('dragleave', handleDragLeave);
    uploadZone.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', handleFileSelect);
    uploadBtn.addEventListener('click', () => fileInput.click());
    refreshBtn.addEventListener('click', fetchFiles);

    // Sidebar tabs
    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.addEventListener('click', () => switchTab(item.dataset.tab));
    });

    // Chat
    chatForm.addEventListener('submit', handleChat);
    chatInput.addEventListener('input', () => {
        chatForm.querySelector('button').disabled = !chatInput.value.trim();
    });

    // Suggestion buttons
    document.querySelectorAll('.suggestion-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            chatInput.value = btn.textContent;
            chatInput.focus();
            chatForm.querySelector('button').disabled = false;
        });
    });
}

// Auth Functions
function toggleAuthMode(e) {
    e.preventDefault();
    isSignUp = !isSignUp;
    authError.style.display = 'none';

    if (isSignUp) {
        authTitle.textContent = 'Create Account';
        authSubtitle.textContent = 'Start storing and searching your files with AI';
        authBtn.textContent = 'Get Started';
        authToggleText.textContent = 'Already have an account?';
        authToggle.textContent = 'Sign in';
    } else {
        authTitle.textContent = 'Welcome back';
        authSubtitle.textContent = 'Sign in to access your cloud drive';
        authBtn.textContent = 'Sign In';
        authToggleText.textContent = "Don't have an account?";
        authToggle.textContent = 'Sign up';
    }
}

async function handleAuth(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    authBtn.innerHTML = '<span class="loading"></span>';
    authBtn.disabled = true;
    authError.style.display = 'none';
    authError.className = 'auth-error';

    try {
        if (isSignUp) {
            // SIGNUP FLOW
            const res = await fetch(`${API_URL}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await res.json();
            console.log('DEBUG: Register response status:', res.status);
            console.log('DEBUG: Register response data:', data);

            if (!res.ok) {
                let errorMsg = 'Registration failed';
                if (data.detail) {
                    if (Array.isArray(data.detail)) {
                        // Handle Pydantic validation errors
                        errorMsg = data.detail.map(e => e.msg).join(', ');
                    } else if (typeof data.detail === 'object') {
                        errorMsg = JSON.stringify(data.detail);
                    } else {
                        errorMsg = data.detail;
                    }
                } else if (data.error) {
                    errorMsg = data.error;
                }

                console.log('DEBUG: Final error message:', errorMsg);
                throw new Error(errorMsg);
            }

            // Signup successful - show verification message
            authError.style.display = 'block';
            authError.className = 'auth-error success';
            authError.innerHTML = '✅ Account created! 📧 Check your email inbox to verify your account before logging in.';
            authBtn.innerHTML = 'Get Started';
            authBtn.disabled = false;
            setTimeout(() => switchToLogin(), 4000);
            return; // STOP HERE - don't try to login

        } else {
            // LOGIN FLOW
            const formData = new FormData();
            formData.append('username', email);
            formData.append('password', password);

            const response = await fetch(`${API_URL}/auth/login`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            console.log('DEBUG: Login response status:', response.status);
            console.log('DEBUG: Login response data:', data);

            if (!response.ok) {
                // Get the actual error message from backend
                const errorMsg = data.detail || data.error || 'Login failed';
                console.log('DEBUG: Extracted errorMsg:', errorMsg);
                throw new Error(errorMsg);
            }

            // Login successful
            token = data.access_token;
            localStorage.setItem('token', token);
            showDashboard();
            fetchFiles();
        }
    } catch (err) {
        console.log('DEBUG: Caught error:', err);
        const errorMsg = err.message;

        // Check if it's a verification needed message
        if (errorMsg.includes('verify') || errorMsg.includes('email')) {
            authError.className = 'auth-error verification';
            // Add Resend Link
            authError.innerHTML = `
                📧 ${errorMsg.replace('📧', '').trim()}<br>
                <div style="margin-top: 10px;">
                    <a href="#" onclick="resendVerification(event)" style="text-decoration: underline; font-weight: bold;">
                        Request a new verification link
                    </a>
                </div>
            `;
        } else {
            authError.className = 'auth-error';
            authError.textContent = errorMsg;
        }
        authError.style.display = 'block';
    } finally {
        if (authBtn.disabled) {
            authBtn.innerHTML = isSignUp ? 'Get Started' : 'Sign In';
            authBtn.disabled = false;
        }
    }
}

// Resend Verification Function
async function resendVerification(e) {
    if (e) e.preventDefault();
    const email = document.getElementById('email').value;

    if (!email) {
        alert('Please enter your email address first.');
        return;
    }

    const link = e.target;
    const originalText = link.textContent;
    link.textContent = 'Sending...';
    link.style.pointerEvents = 'none'; // Disable click

    try {
        const response = await fetch(`${API_URL}/auth/resend-verification?email=${encodeURIComponent(email)}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            link.textContent = '✅ Sent! Check your inbox.';
            link.style.color = '#155724';
            link.style.textDecoration = 'none';
        } else {
            throw new Error(data.detail || 'Failed to send');
        }
    } catch (err) {
        console.error('Resend failed:', err);
        link.textContent = '❌ Failed. Try again.';
        link.style.color = '#721c24';
        setTimeout(() => {
            link.textContent = originalText;
            link.style.pointerEvents = 'auto';
            link.style.color = '';
        }, 3000);
    }
}


async function verifyEmail(tokenStr) {
    // Show loading state
    authContainer.style.display = 'flex';
    dashboardContainer.style.display = 'none';
    authTitle.textContent = 'Verifying Email...';
    authSubtitle.textContent = 'Please wait while we verify your account';
    authForm.style.display = 'none';
    authError.style.display = 'none';

    try {
        const response = await fetch(`${API_URL}/auth/verify-email?token=${tokenStr}`);
        const data = await response.json();

        if (response.ok) {
            // Auto Login
            if (data.access_token) {
                token = data.access_token;
                localStorage.setItem('token', token);
                authError.className = 'auth-error success';
                authError.innerHTML = `✅ ${data.message}<br>Redirecting to dashboard...`;
                authError.style.display = 'block';

                setTimeout(() => {
                    // Remove query params
                    window.history.replaceState({}, document.title, window.location.pathname);
                    showDashboard();
                    fetchFiles();
                }, 2000);
            } else {
                // Fallback if no token returned (legacy)
                authError.className = 'auth-error success';
                authError.textContent = data.message;
                authError.style.display = 'block';
                setTimeout(() => switchToLogin(), 2000);
            }
        } else {
            throw new Error(data.detail || 'Verification failed');
        }
    } catch (err) {
        authTitle.textContent = 'Verification Failed';
        authSubtitle.textContent = 'Please try again or request a new link';
        authError.className = 'auth-error';
        authError.textContent = err.message;
        authError.style.display = 'block';

        // Show login button just in case
        setTimeout(() => {
            authForm.style.display = 'block';
            switchToLogin();
        }, 3000);
    }
}

function logout() {
    token = null;
    localStorage.removeItem('token');
    files = [];
    showAuth();
}

function showAuth() {
    authContainer.style.display = 'flex';
    dashboardContainer.style.display = 'none';
}

function showDashboard() {
    authContainer.style.display = 'none';
    dashboardContainer.style.display = 'flex';
    chatInput.disabled = false;
}



// File Functions
async function fetchFiles() {
    if (pollingTimer) clearTimeout(pollingTimer);

    try {
        const response = await fetch(`${API_URL}/api/files`, {
            headers: { Authorization: `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Failed to fetch files');

        files = await response.json();
        renderFiles();
        updateDocumentList(); // Update chat document selector

        // Poll if any file is still processing
        const hasProcessing = files.some(f => !f.is_indexed);
        if (hasProcessing) {
            console.log('Files processing... polling in 3s');
            pollingTimer = setTimeout(fetchFiles, 3000);
        }
    } catch (err) {
        console.error(err);
        showToast('Failed to load files: ' + err.message, true);
    }
}

function renderFiles() {
    fileCount.textContent = files.length;
    storageFill.style.width = `${Math.min(files.length * 5, 100)}%`;

    if (files.length === 0) {
        filesGrid.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';
    filesGrid.innerHTML = files.map(file => {
        const ext = file.filename.split('.').pop().toLowerCase();
        const icon = ext === 'pdf' ? '📄' : ext === 'txt' ? '📝' : '📋';
        const size = formatSize(file.size);
        const date = new Date(file.upload_date).toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric'
        });

        return `
            <div class="file-card" data-id="${file.id}">
                <div class="file-icon ${ext}">${icon}</div>
                <p class="file-name" title="${file.filename}">${file.filename}</p>
                <p class="file-meta">${size} • ${date}</p>
                <div class="file-footer">
                    <span class="file-status ${file.is_indexed ? 'indexed' : 'processing'}">
                        ${file.is_indexed ? '✓ Indexed' : '⏳ Processing'}
                    </span>
                    <div class="file-actions">
                        <button class="file-action-btn" onclick="shareFile(${file.id})" title="Share">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
                                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
                                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
                            </svg>
                        </button>
                        <button class="file-action-btn" onclick="downloadFile(${file.id}, '${file.filename}')" title="Download">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                        </button>
                        <button class="file-action-btn delete" onclick="deleteFile(${file.id})" title="Delete">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

// Upload Functions
function handleDragOver(e) {
    e.preventDefault();
    uploadZone.classList.add('dragging');
}

function handleDragLeave() {
    uploadZone.classList.remove('dragging');
}

function handleDrop(e) {
    e.preventDefault();
    uploadZone.classList.remove('dragging');
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) uploadFile(file);
}

async function uploadFile(file) {
    uploadProgress.style.display = 'block';
    progressFill.style.width = '0%';
    progressPercent.textContent = '0';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                progressFill.style.width = percent + '%';
                progressPercent.textContent = percent;
            }
        });

        xhr.onload = () => {
            uploadProgress.style.display = 'none';
            fileInput.value = '';

            if (xhr.status >= 200 && xhr.status < 300) {
                showToast('File uploaded successfully!');
                fetchFiles();
            } else {
                const err = JSON.parse(xhr.responseText);
                showToast(err.detail || 'Upload failed', true);
            }
        };

        xhr.onerror = () => {
            uploadProgress.style.display = 'none';
            showToast('Upload failed', true);
        };

        xhr.open('POST', `${API_URL}/api/upload`);
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        xhr.send(formData);
    } catch (err) {
        uploadProgress.style.display = 'none';
        showToast(err.message, true);
    }
}

// File Actions
async function shareFile(fileId) {
    try {
        const response = await fetch(`${API_URL}/api/share`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`
            },
            body: JSON.stringify({ file_id: fileId })
        });

        if (!response.ok) throw new Error('Share failed');

        const data = await response.json();
        const shareUrl = window.location.origin + data.share_url;
        await navigator.clipboard.writeText(shareUrl);
        showToast('Link copied to clipboard!');
    } catch (err) {
        showToast(err.message, true);
    }
}

function downloadFile(fileId, filename) {
    const token = localStorage.getItem('token');

    fetch(`${API_URL}/api/download/${fileId}`, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Download failed');
            }
            return response.blob();
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
            showToast('File downloaded successfully');
        })
        .catch(error => {
            console.error('Download error:', error);
            showToast('Failed to download file', true);
        });
}

async function deleteFile(fileId) {
    if (!confirm('Are you sure you want to delete this file?')) return;

    try {
        const response = await fetch(`${API_URL}/api/delete/${fileId}`, {
            method: 'DELETE',
            headers: { Authorization: `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Delete failed');

        showToast('File deleted');
        fetchFiles();
    } catch (err) {
        showToast(err.message, true);
    }
}

// Chat Functions
async function handleChat(e) {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query) return;

    // Clear empty state
    const chatEmpty = chatMessages.querySelector('.chat-empty');
    if (chatEmpty) chatEmpty.remove();

    // Add user message
    addChatMessage(query, 'user');
    chatInput.value = '';
    chatForm.querySelector('button').disabled = true;

    // Add typing indicator
    const typingId = addTypingIndicator();

    try {
        // Build request with optional file filtering
        const requestBody = { query };
        if (selectedFileIds.length > 0) {
            requestBody.file_ids = selectedFileIds;
        }

        const response = await fetch(`${API_URL}/api/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`
            },
            body: JSON.stringify(requestBody)
        });

        removeTypingIndicator(typingId);

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Query failed');
        }

        const data = await response.json();
        addChatMessage(data.answer, 'assistant', data.sources);
    } catch (err) {
        removeTypingIndicator(typingId);
        addChatMessage('Sorry, I encountered an error. Please try again.', 'assistant', null, true);
        console.error('Chat error:', err);
    }
}

function addChatMessage(content, role, sources = null, isError = false) {
    const div = document.createElement('div');
    div.className = `chat-message ${role}`;

    let sourcesHtml = '';
    if (sources && sources.length > 0) {
        sourcesHtml = `
            <div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border-light);font-size:0.75rem;color:var(--text-muted)">
                <strong>Sources:</strong>
                ${sources.slice(0, 2).map((s, i) => `<div>📄 Chunk #${s.metadata?.chunk_index || i}</div>`).join('')}
            </div>
        `;
    }

    div.innerHTML = `
        <div class="message-bubble" ${isError ? 'style="background:#fef2f2;color:#991b1b"' : ''}>
            ${content.replace(/\n/g, '<br>')}
            ${sourcesHtml}
        </div>
    `;

    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addTypingIndicator() {
    const id = Date.now();
    const div = document.createElement('div');
    div.className = 'chat-message assistant';
    div.id = `typing-${id}`;
    div.innerHTML = `
        <div class="message-bubble">
            <div class="typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
            </div>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

function removeTypingIndicator(id) {
    const el = document.getElementById(`typing-${id}`);
    if (el) el.remove();
}

// Tab Switching
function switchTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.classList.toggle('active', item.dataset.tab === tab);
    });

    filesTab.style.display = tab === 'files' ? 'block' : 'none';
    chatTab.style.display = tab === 'chat' ? 'block' : 'none';
}

// Toast Notifications
function showToast(message, isError = false) {
    toast.textContent = message;
    toast.className = 'toast show';
    if (isError) toast.classList.add('error');

    setTimeout(() => {
        toast.classList.remove('show');
        if (isError) toast.classList.remove('error');
    }, 3000);
}


// Document Selector Functions
function updateDocumentList() {
    const docList = document.getElementById('doc-list');
    if (!files || files.length === 0) {
        docList.innerHTML = '<div style="padding: 8px; color: var(--text-muted); font-size: 0.8125rem;">No files uploaded yet</div>';
        return;
    }

    docList.innerHTML = files.map(file => `
        <label class="doc-checkbox ${selectedFileIds.includes(file.id) ? 'selected' : ''}">
            <input type="checkbox" 
                   value="${file.id}" 
                   ${selectedFileIds.includes(file.id) ? 'checked' : ''}
                   onchange="toggleFileSelection(${file.id})">
            ${file.filename}
        </label>
    `).join('');

    updateSelectedCount();
}

function toggleFileSelection(fileId) {
    const index = selectedFileIds.indexOf(fileId);
    if (index > -1) {
        selectedFileIds.splice(index, 1);
    } else {
        selectedFileIds.push(fileId);
    }
    updateDocumentList();
}

function selectAllDocs() {
    selectedFileIds = files.map(f => f.id);
    updateDocumentList();
}

function clearAllDocs() {
    selectedFileIds = [];
    updateDocumentList();
}

function updateSelectedCount() {
    const countEl = document.getElementById('selected-count');
    if (selectedFileIds.length === 0) {
        countEl.textContent = 'All documents';
    } else if (selectedFileIds.length === files.length) {
        countEl.textContent = `All ${files.length} documents`;
    } else {
        countEl.textContent = `${selectedFileIds.length} of ${files.length} documents`;
    }
}

// Add event listeners for document selector
document.getElementById('select-all-docs')?.addEventListener('click', selectAllDocs);
document.getElementById('clear-all-docs')?.addEventListener('click', clearAllDocs);

/* User Profile Logic */
function showUserProfile() {
    // Hide dropdown
    const profileMenu = document.getElementById('profile-menu');
    if (profileMenu) profileMenu.classList.remove('show');

    // Show Modal
    const modal = document.getElementById('profile-modal');
    if (modal) {
        modal.classList.add('show');
        modal.style.visibility = 'visible';
        modal.style.opacity = '1';
    }

    // Fetch Data
    const token = localStorage.getItem('token');
    // Ensure API_URL is defined (it is global constant at top usually, but verify)
    // Assuming API_URL is global. If not, use relative /api/
    const url = typeof API_URL !== 'undefined' ? `${API_URL}/auth/me` : '/auth/me';

    fetch(url, {
        headers: { Authorization: `Bearer ${token}` }
    })
        .then(res => res.json())
        .then(data => {
            if (data.email) {
                document.getElementById('profile-email').textContent = data.email;
                document.getElementById('profile-role').textContent = data.role === 'admin' ? 'Administrator' : 'Standard User';
                document.getElementById('profile-date').textContent = new Date(data.created_at).toLocaleDateString();
            } else {
                showToast('Failed to load profile data', true);
            }
        })
        .catch(err => {
            showToast('Failed to load profile', true);
            console.error(err);
        });
}

function closeProfileModal() {
    const modal = document.getElementById('profile-modal');
    if (modal) {
        modal.classList.remove('show');
        modal.style.visibility = 'hidden';
        modal.style.opacity = '0';
    }
}
