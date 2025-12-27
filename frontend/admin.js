
const API_URL = '';
let adminToken = localStorage.getItem('admin_token');
let usersData = [];
let filesData = [];
let chatsData = [];

// Elements
const loginContainer = document.getElementById('admin-login-container');
const dashboardContainer = document.getElementById('admin-dashboard');
const loginForm = document.getElementById('admin-login-form');
const authError = document.getElementById('auth-error');
const logoutBtn = document.getElementById('logout-btn');
const toast = document.getElementById('toast');

// Init
document.addEventListener('DOMContentLoaded', () => {
    if (adminToken) {
        showDashboard();
        loadAllData();
    } else {
        showLogin();
    }
});

// Auth
if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        e.stopPropagation();

        authError.style.display = 'none';

        const username = document.getElementById('admin-username').value;
        const password = document.getElementById('admin-password').value;

        try {
            const response = await fetch(`${API_URL}/auth/admin/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || errorData.detail || 'Invalid credentials');
            }

            const data = await response.json();

            if (!data.access_token) {
                throw new Error('No access token received');
            }

            adminToken = data.access_token;
            localStorage.setItem('admin_token', adminToken);

            showDashboard();
            loadAllData();

        } catch (error) {
            console.error('Login error:', error);
            authError.textContent = error.message;
            authError.style.display = 'block';
        }

        return false;
    });
}

if (logoutBtn) {
    logoutBtn.addEventListener('click', (e) => {
        e.preventDefault();
        adminToken = null;
        localStorage.removeItem('admin_token');
        showLogin();
    });
}

function showLogin() {
    if (loginContainer) loginContainer.style.display = 'flex';
    if (dashboardContainer) dashboardContainer.style.display = 'none';
}

function showDashboard() {
    if (loginContainer) loginContainer.style.display = 'none';
    if (dashboardContainer) dashboardContainer.style.display = 'block';
}

// Load all data
async function loadAllData() {
    try {
        const fetchWithAuth = async (url) => {
            const res = await fetch(url, {
                headers: { Authorization: `Bearer ${adminToken}` }
            });

            if (!res.ok) {
                if (res.status === 401 || res.status === 403) {
                    throw new Error('UNAUTHORIZED');
                }
                throw new Error(`HTTP ${res.status}`);
            }
            return res.json();
        };

        const [users, files, chats, logs] = await Promise.all([
            fetchWithAuth(`${API_URL}/api/admin/users`),
            fetchWithAuth(`${API_URL}/api/admin/files`),
            fetchWithAuth(`${API_URL}/api/admin/chats`),
            fetchWithAuth(`${API_URL}/api/admin/audit-logs`)
        ]);

        usersData = Array.isArray(users) ? users : [];
        filesData = Array.isArray(files) ? files : [];
        chatsData = Array.isArray(chats) ? chats : [];
        const logsData = Array.isArray(logs) ? logs : [];

        updateKPIs();
        renderUsersTable(usersData);
        renderFilesTable(filesData);
        renderAuditLogs(logsData);

    } catch (err) {
        console.error('Load data error:', err);

        if (err.message === 'UNAUTHORIZED') {
            showToast('Session expired. Please login again.', true);
            setTimeout(() => {
                adminToken = null;
                localStorage.removeItem('admin_token');
                showLogin();
            }, 1500);
        } else {
            showToast('Failed to load data: ' + err.message, true);
        }
    }
}

function updateKPIs() {
    document.getElementById('totalUsers').textContent = usersData.length || 0;
    document.getElementById('totalFiles').textContent = filesData.length || 0;
    document.getElementById('totalChats').textContent = chatsData.length || 0;
}

function renderUsersTable(users) {
    const tbody = document.getElementById('usersTable');
    if (!tbody) return;

    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No users found</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(user => {
        const created = user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A';
        const lastLogin = user.last_login ? new Date(user.last_login).toLocaleString() : 'Never';
        const storageMB = (user.storage_used / (1024 * 1024)).toFixed(1);

        // Status Logic
        let statusBadge = '';
        if (!user.is_verified) statusBadge += '<span class="badge warning">Unverified</span> ';
        if (!user.is_active) statusBadge += '<span class="badge error">Suspended</span> ';
        if (user.is_active && user.is_verified) statusBadge += '<span class="badge success">Active</span> ';
        if (!user.can_upload) statusBadge += '<span class="badge warning">No Upload</span>';

        return `
            <tr>
                <td>
                    <strong>${escapeHtml(user.email)}</strong><br>
                    <span class="text-muted" style="font-size: 11px;">Joined: ${created}</span>
                </td>
                <td>${statusBadge}</td>
                <td>
                    <div style="font-size: 12px;">
                        <div>Queries: <strong>${user.queries_total}</strong> (${user.queries_24h} today)</div>
                        <div class="text-muted">Storage: ${storageMB} MB</div>
                        ${user.failed_queries > 0 ? `<div style="color: var(--error);">Failed: ${user.failed_queries}</div>` : ''}
                    </div>
                </td>
                <td class="text-muted">${lastLogin}</td>
                <td>
                    <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                        <button class="btn btn-small" onclick="showUserProfile(${user.id})" title="Profile">👤</button>
                        <button class="btn btn-small" onclick="showUserChats('${escapeHtml(user.email)}')" title="Chats">💬</button>
                        
                        ${!user.is_verified ?
                `<button class="btn btn-small" onclick="verifyUser(${user.id})" title="Verify" style="color: var(--success);">✅</button>` : ''}
                        
                        ${user.is_active ?
                `<button class="btn btn-small" onclick="toggleSuspend(${user.id}, true)" title="Suspend" style="color: var(--error);">⏸️</button>` :
                `<button class="btn btn-small" onclick="toggleSuspend(${user.id}, false)" title="Unsuspend" style="color: var(--success);">▶️</button>`}
                            
                        ${user.can_upload ?
                `<button class="btn btn-small" onclick="toggleUpload(${user.id}, false)" title="Disable Upload">🚫</button>` :
                `<button class="btn btn-small" onclick="toggleUpload(${user.id}, true)" title="Enable Upload">☁️</button>`}

                        <button class="btn btn-small" onclick="deleteUser(${user.id})" title="Delete" style="color: var(--error);">🗑️</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function renderAuditLogs(logs) {
    const tbody = document.getElementById('auditTable');
    if (!tbody) return;

    if (logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No logs found</td></tr>';
        return;
    }

    tbody.innerHTML = logs.map(log => `
        <tr>
            <td class="text-muted">${new Date(log.timestamp).toLocaleString()}</td>
            <td>${escapeHtml(log.actor_email)}</td>
            <td><strong>${escapeHtml(log.action)}</strong></td>
            <td>${log.target_type} #${log.target_id}</td>
            <td class="text-muted" style="font-family: monospace; font-size: 11px;">${escapeHtml(log.metadata_json || '')}</td>
        </tr>
    `).join('');
}

function renderFilesTable(files) {
    const tbody = document.getElementById('filesTable');
    if (!tbody) return;

    if (files.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No files found</td></tr>';
        return;
    }

    tbody.innerHTML = files.map(file => {
        const uploaded = file.upload_date ? new Date(file.upload_date).toLocaleString() : 'N/A';
        const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
        const sizeKB = (file.size / 1024).toFixed(1);
        const sizeDisplay = file.size > 1024 * 1024 ? `${sizeMB} MB` : `${sizeKB} KB`;
        const fileType = file.content_type || 'Unknown';

        return `
            <tr>
                <td>
                    <strong>${escapeHtml(file.filename)}</strong>
                </td>
                <td class="text-muted">${escapeHtml(file.owner_email)}</td>
                <td>${sizeDisplay}</td>
                <td><span class="badge">${escapeHtml(fileType.split('/')[1] || fileType)}</span></td>
                <td class="text-muted">${uploaded}</td>
                <td>
                    <button class="btn btn-small" onclick="downloadFile(${file.id}, '${escapeHtml(file.filename)}')" title="Download">⬇️</button>
                </td>
            </tr>
        `;
    }).join('');
}

function filterFiles() {
    const search = document.getElementById('searchFiles').value.toLowerCase();
    if (!search) {
        renderFilesTable(filesData);
        return;
    }
    const filtered = filesData.filter(file =>
        file.filename.toLowerCase().includes(search) ||
        file.owner_email.toLowerCase().includes(search)
    );
    renderFilesTable(filtered);
}

function filterUsers() {
    const search = document.getElementById('searchUsers').value.toLowerCase();
    if (!search) {
        renderUsersTable(usersData);
        return;
    }
    const filtered = usersData.filter(user => user.email.toLowerCase().includes(search));
    renderUsersTable(filtered);
}

function showUserProfile(userId) {
    const user = usersData.find(u => u.id === userId);
    if (!user) return;

    const userFiles = filesData.filter(f => f.owner_email === user.email);
    const userChats = chatsData.filter(c => c.user_email === user.email);

    const created = new Date(user.created_at);
    const accountAge = Math.floor((new Date() - created) / (1000 * 60 * 60 * 24));
    const lastLogin = user.last_login ? new Date(user.last_login) : null;
    const daysSinceLogin = lastLogin ? Math.floor((new Date() - lastLogin) / (1000 * 60 * 60 * 24)) : null;

    const totalStorage = userFiles.reduce((sum, f) => sum + (f.size || 0), 0);
    const storageGB = (totalStorage / (1024 * 1024 * 1024)).toFixed(2);
    const storageMB = (totalStorage / (1024 * 1024)).toFixed(1);

    const recentChats = userChats.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)).slice(0, 3);

    const modal = document.getElementById('profileModal');
    const title = document.getElementById('profileModalTitle');
    const content = document.getElementById('profileModalContent');

    title.textContent = `Profile: ${user.email}`;

    content.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px;">
            <div>
                <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">Account Information</div>
                <div style="background: var(--bg); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
                    <div style="margin-bottom: 12px;">
                        <div style="font-size: 11px; color: var(--text-muted);">Email</div>
                        <div style="font-size: 14px; font-weight: 500;">${escapeHtml(user.email)}</div>
                    </div>
                    <div style="margin-bottom: 12px;">
                        <div style="font-size: 11px; color: var(--text-muted);">Account Created</div>
                        <div style="font-size: 13px;">${created.toLocaleDateString()} (${accountAge} days ago)</div>
                    </div>
                    <div style="margin-bottom: 12px;">
                        <div style="font-size: 11px; color: var(--text-muted);">Last Login</div>
                        <div style="font-size: 13px;">
                            ${lastLogin ? `${lastLogin.toLocaleString()} <span style="color: var(--text-faint);">(${daysSinceLogin} days ago)</span>` : '<span style="color: var(--text-faint);">Never</span>'}
                        </div>
                    </div>
                    <div>
                        <div style="font-size: 11px; color: var(--text-muted);">Status</div>
                        <div style="font-size: 13px;">
                            <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${user.is_active ? 'var(--success)' : 'var(--error)'}; margin-right: 6px;"></span>
                            ${user.is_active ? 'Active' : 'Inactive'}
                        </div>
                    </div>
                </div>
            </div>
            <div>
                <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">Usage Statistics</div>
                <div style="background: var(--bg); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
                    <div style="margin-bottom: 16px;">
                        <div style="font-size: 24px; font-weight: 600; color: var(--accent);">${userFiles.length}</div>
                        <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Total Files</div>
                    </div>
                    <div style="margin-bottom: 16px;">
                        <div style="font-size: 24px; font-weight: 600; color: var(--accent);">${totalStorage > 1073741824 ? storageGB + ' GB' : storageMB + ' MB'}</div>
                        <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Storage Used</div>
                    </div>
                    <div>
                        <div style="font-size: 24px; font-weight: 600; color: var(--accent);">${userChats.length}</div>
                        <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Total Queries</div>
                    </div>
                </div>
            </div>
        </div>
        ${recentChats.length > 0 ? `
        <div>
            <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">Recent Activity</div>
            <div style="background: var(--bg); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
                ${recentChats.map(chat => `
                    <div style="margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--border-light);">
                        <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">
                            ${escapeHtml(chat.query.substring(0, 80))}${chat.query.length > 80 ? '...' : ''}
                        </div>
                        <div style="font-size: 11px; color: var(--text-faint);">${new Date(chat.timestamp).toLocaleString()}</div>
                    </div>
                `).join('')}
                ${userChats.length > 3 ? `<div style="text-align: center; margin-top: 8px;">
                    <button class="btn btn-small" onclick="closeProfileModal(); showUserChats('${escapeHtml(user.email)}')">View All ${userChats.length} Queries</button>
                </div>` : ''}
            </div>
        </div>
        ` : '<div class="empty-state">No activity yet</div>'}
    `;

    modal.style.display = 'flex';
}

function closeProfileModal() {
    document.getElementById('profileModal').style.display = 'none';
}

function showUserChats(userEmail) {
    const userChats = chatsData.filter(chat => chat.user_email === userEmail);
    const modal = document.getElementById('chatModal');
    const title = document.getElementById('chatModalTitle');
    const content = document.getElementById('chatModalContent');

    title.textContent = `Chats for ${userEmail}`;

    if (userChats.length === 0) {
        content.innerHTML = '<div class="empty-state">No chat history for this user</div>';
    } else {
        content.innerHTML = userChats.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)).map(chat => `
            <div class="chat-message">
                <div class="chat-query">${escapeHtml(chat.query)}</div>
                <div class="chat-answer">${escapeHtml(chat.answer)}</div>
                <div class="chat-time">${new Date(chat.timestamp).toLocaleString()}</div>
            </div>
        `).join('');
    }

    modal.style.display = 'flex';
}

function closeChatModal() {
    document.getElementById('chatModal').style.display = 'none';
}

window.onclick = function (event) {
    const chatModal = document.getElementById('chatModal');
    const profileModal = document.getElementById('profileModal');
    if (event.target === chatModal) closeChatModal();
    if (event.target === profileModal) closeProfileModal();
}

function downloadFile(fileId, filename) {
    console.log('Downloading file:', fileId, filename);
    console.log('Admin token:', adminToken ? 'Present' : 'Missing');

    if (!adminToken) {
        showToast('Please login first', true);
        return;
    }

    fetch(`${API_URL}/api/download/${fileId}`, {
        headers: { Authorization: `Bearer ${adminToken}` }
    })
        .then(res => {
            console.log('Download response status:', res.status);
            if (!res.ok) {
                return res.json().then(err => {
                    throw new Error(err.detail || 'Download failed');
                });
            }
            return res.blob();
        })
        .then(blob => {
            console.log('Downloaded blob size:', blob.size);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            showToast('Downloaded ' + filename);
        })
        .catch(err => {
            console.error('Download error:', err);
            showToast(err.message || 'Failed to download file', true);
        });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, isError = false) {
    if (!toast) return;
    toast.textContent = message;
    toast.className = 'toast show';
    if (isError) toast.classList.add('error');
    setTimeout(() => {
        toast.classList.remove('show');
        if (isError) toast.classList.remove('error');
    }, 3000);
}

function verifyUser(userId) {
    if (!confirm('Manually verify this user? They will be able to log in immediately.')) {
        return;
    }

    if (!adminToken) {
        showToast('Please login first', true);
        return;
    }

    fetch(`${API_URL}/api/admin/users/${userId}/verify`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${adminToken}` }
    })
        .then(res => {
            if (!res.ok) throw new Error('Failed to verify user');
            return res.json();
        })
        .then(data => {
            showToast(data.message);
            loadAllData(); // Refresh list
        })
        .catch(err => {
            console.error('Verification error:', err);
            showToast(err.message, true);
        });
}
function deleteUser(userId) {
    if (!confirm('Are you sure you want to delete this user? This action cannot be undone and will delete all their files and chats.')) {
        return;
    }

    if (!adminToken) {
        showToast('Please login first', true);
        return;
    }

    fetch(`${API_URL}/api/admin/users/${userId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${adminToken}` }
    })
        .then(res => {
            if (!res.ok) throw new Error('Failed to delete user');
            return res.json();
        })
        .then(() => {
            showToast('User deleted successfully');
            loadAllData(); // Refresh list
        })
        .catch(err => {
            console.error('Delete error:', err);
            showToast(err.message, true);
        });
}

function toggleSuspend(userId, suspend) {
    const action = suspend ? 'suspend' : 'unsuspend';

    if (!adminToken) return;

    fetch(`${API_URL}/api/admin/users/${userId}/${action}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${adminToken}` }
    })
        .then(res => {
            if (!res.ok) throw new Error('Action failed');
            return res.json();
        })
        .then(data => {
            showToast(data.message);
            loadAllData();
        })
        .catch(err => showToast(err.message, true));
}

function toggleUpload(userId, disable) {
    const action = disable ? 'disable-upload' : 'enable-upload';

    if (!adminToken) return;

    fetch(`${API_URL}/api/admin/users/${userId}/${action}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${adminToken}` }
    })
        .then(res => {
            if (!res.ok) throw new Error('Action failed');
            return res.json();
        })
        .then(data => {
            showToast(data.message);
            loadAllData();
        })
        .catch(err => showToast(err.message, true));
}
