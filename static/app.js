const API_URL = "";

// Auth
function toggleAuth() {
    const login = document.getElementById('login-form');
    const register = document.getElementById('register-form');
    if (login.classList.contains('hidden')) {
        login.classList.remove('hidden');
        register.classList.add('hidden');
    } else {
        login.classList.add('hidden');
        register.classList.remove('hidden');
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const user = document.getElementById('username').value;
    const pass = document.getElementById('password').value;

    try {
        const res = await fetch(`${API_URL}/token`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user, password: pass })
        });

        if (res.ok) {
            const data = await res.json();
            localStorage.setItem('eco_token', data.token);
            localStorage.setItem('eco_user', user);
            localStorage.setItem('eco_is_admin', data.is_admin);
            window.location.href = 'dashboard.html';
        } else {
            showError('Invalid credentials');
        }
    } catch (err) {
        showError('Connection error');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const user = document.getElementById('reg-username').value;
    const pass = document.getElementById('reg-password').value;

    try {
        const res = await fetch(`${API_URL}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user, password: pass })
        });

        if (res.ok) {
            alert('Registration successful! Please login.');
            toggleAuth();
        } else {
            const data = await res.json();
            showError(data.detail || 'Registration failed');
        }
    } catch (err) {
        showError('Connection error');
    }
}

function showError(msg) {
    const el = document.getElementById('error-msg');
    el.textContent = msg;
    el.classList.remove('hidden');
}

function logout() {
    localStorage.clear();
    window.location.href = 'index.html';
}

// Dashboard
async function loadECOs() {
    const token = localStorage.getItem('eco_token');
    const res = await fetch(`${API_URL}/ecos`, {
        headers: { 'X-API-Token': token }
    });

    if (res.status === 401) logout();

    const list = await res.json();
    const tbody = document.getElementById('eco-list');
    tbody.innerHTML = '';

    list.forEach(eco => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid var(--border)';
        tr.innerHTML = `
            <td style="padding: 1rem;">#${eco.id}</td>
            <td style="padding: 1rem; font-weight: 600;">${eco.title}</td>
            <td style="padding: 1rem;"><span class="badge ${getStatusClass(eco.status)}">${eco.status}</span></td>
            <td style="padding: 1rem; color: var(--text-muted);">${new Date(eco.created_at).toLocaleDateString()}</td>
            <td style="padding: 1rem;">
                <button onclick="openDetail(${eco.id})" class="btn btn-primary" style="padding: 0.5rem 1rem; font-size: 0.8rem;">View</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function getStatusClass(status) {
    // Just returning status for now, could act as class name hook
    return '';
}

// Create
function showCreateModal() {
    document.getElementById('create-modal').classList.remove('hidden');
}

function hideCreateModal() {
    document.getElementById('create-modal').classList.add('hidden');
}

async function handleCreateECO(e) {
    e.preventDefault();
    const title = document.getElementById('eco-title').value;
    const desc = document.getElementById('eco-desc').value;
    const token = localStorage.getItem('eco_token');

    const res = await fetch(`${API_URL}/ecos`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Token': token
        },
        body: JSON.stringify({ title: title, description: desc })
    });

    if (res.ok) {
        hideCreateModal();
        loadECOs();
    } else {
        alert('Failed to create ECO');
    }
}

// Detail & Actions
let currentEcoId = null;

async function openDetail(id) {
    currentEcoId = id;
    const token = localStorage.getItem('eco_token');
    const res = await fetch(`${API_URL}/ecos/${id}`, {
        headers: { 'X-API-Token': token }
    });

    if (!res.ok) return;

    const data = await res.json();

    document.getElementById('detail-id').textContent = data.id;
    document.getElementById('detail-title').textContent = data.title;
    document.getElementById('detail-desc').textContent = data.description;
    document.getElementById('detail-status').textContent = data.status;

    // Attachments
    const fileList = document.getElementById('detail-files');
    fileList.innerHTML = '';
    data.attachments.forEach(f => {
        const li = document.createElement('li');
        li.innerHTML = `<a href="#" onclick="viewAttachment('${f.filename}'); return false;">📎 ${f.filename}</a> <span style="color: var(--text-muted); font-size: 0.9em;">(${f.uploaded_by})</span>`;
        li.style.marginBottom = '0.5rem';
        fileList.appendChild(li);
    });

    // History
    const historyDiv = document.getElementById('detail-history');
    historyDiv.innerHTML = data.history.map(h =>
        `<div style="margin-bottom: 0.5rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border);">
            <strong>${h.action}</strong> by ${h.performed_by} at ${new Date(h.performed_at).toLocaleString()}
            ${h.comment ? `<br><em>"${h.comment}"</em>` : ''}
         </div>`
    ).join('');

    // Actions
    const actionsDiv = document.getElementById('actions-area');
    actionsDiv.innerHTML = '';

    if (data.status === 'DRAFT') {
        const btn = document.createElement('button');
        btn.className = 'btn btn-primary';
        btn.textContent = 'Submit for Approval';
        btn.onclick = () => performAction('submit');
        actionsDiv.appendChild(btn);
    } else if (data.status === 'SUBMITTED') {
        const approveBtn = document.createElement('button');
        approveBtn.className = 'btn btn-success';
        approveBtn.textContent = 'Approve';
        approveBtn.style.marginBottom = '0.5rem';
        approveBtn.onclick = () => performAction('approve');

        const rejectBtn = document.createElement('button');
        rejectBtn.className = 'btn btn-danger';
        rejectBtn.textContent = 'Reject';
        rejectBtn.onclick = () => performAction('reject', true);

        actionsDiv.appendChild(approveBtn);
        actionsDiv.appendChild(rejectBtn);
    }

    document.getElementById('detail-modal').classList.remove('hidden');
}

function hideDetailModal() {
    document.getElementById('detail-modal').classList.add('hidden');
    loadECOs(); // Refresh list
}

async function performAction(action, requireComment = false) {
    let comment = null;
    if (requireComment || action !== 'submit') { // submit can vary, but generally good to ask
        comment = prompt('Add a comment (optional for submit/approve, required for reject):');
        if (requireComment && !comment) return;
    }

    const token = localStorage.getItem('eco_token');
    const res = await fetch(`${API_URL}/ecos/${currentEcoId}/${action}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Token': token
        },
        body: JSON.stringify({ comment: comment })
    });

    if (res.ok) {
        openDetail(currentEcoId); // Refresh details
    } else {
        const d = await res.json();
        alert(d.detail || 'Action failed');
    }
}

async function handleUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById('upload-file');
    if (!fileInput.files[0]) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    const token = localStorage.getItem('eco_token');
    const res = await fetch(`${API_URL}/ecos/${currentEcoId}/attachments`, {
        method: 'POST',
        headers: { 'X-API-Token': token },
        body: formData
    });

    if (res.ok) {
        fileInput.value = '';
        openDetail(currentEcoId);
    } else {
        alert('Upload failed');
    }
}

async function downloadReport() {
    const token = localStorage.getItem('eco_token');
    const res = await fetch(`${API_URL}/ecos/${currentEcoId}/report`, {
        headers: { 'X-API-Token': token }
    });

    if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `eco_${currentEcoId}_report.md`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
    } else {
        alert('Download failed');
    }
}

async function viewAttachment(filename) {
    const token = localStorage.getItem('eco_token');
    try {
        const res = await fetch(`${API_URL}/ecos/${currentEcoId}/attachments/${filename}`, {
            headers: { 'X-API-Token': token }
        });

        if (res.ok) {
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            window.open(url, '_blank');
            // Note: ObjectURL revocation is tricky with window.open, usually browser handles it on close or timeout, 
            // but strict memory management might require tracking. For now, letting browser handle.
        } else {
            alert('Failed to view attachment');
        }
    } catch (e) {
        alert('Error fetching attachment');
    }
}

// Admin
function openAdmin() {
    loadUsers();
    document.getElementById('admin-modal').classList.remove('hidden');
}

function hideAdminModal() {
    document.getElementById('admin-modal').classList.add('hidden');
}

async function loadUsers() {
    const token = localStorage.getItem('eco_token');
    const res = await fetch(`${API_URL}/admin/users`, {
        headers: { 'X-API-Token': token }
    });

    if (!res.ok) {
        alert("Failed to load users");
        return;
    }

    const users = await res.json();
    const tbody = document.getElementById('user-list');
    tbody.innerHTML = '';

    users.forEach(u => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid var(--border)';
        const isAdminIdx = u.is_admin ? '<span style="color:var(--success)">Admin</span>' : 'User';
        const deleteBtn = u.is_admin ? '' : `<button onclick="deleteUser(${u.id})" class="btn btn-danger" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;">Delete</button>`;

        tr.innerHTML = `
            <td style="padding: 0.5rem;">${u.id || ''}</td>
            <td style="padding: 0.5rem;">${u.username}</td>
            <td style="padding: 0.5rem;">${isAdminIdx}</td>
            <td style="padding: 0.5rem;">${deleteBtn}</td>
        `;
        tbody.appendChild(tr);
    });
}

async function deleteUser(userId) {
    if (!confirm("Are you sure you want to delete this user?")) return;

    const token = localStorage.getItem('eco_token');
    const res = await fetch(`${API_URL}/admin/users/${userId}`, {
        method: 'DELETE',
        headers: { 'X-API-Token': token }
    });

    if (res.ok) {
        loadUsers();
    } else {
        alert("Failed to delete user");
    }
}

async function handleAdminAddUser(e) {
    e.preventDefault();
    const userIn = document.getElementById('admin-new-user');
    const passIn = document.getElementById('admin-new-pass');

    try {
        const res = await fetch(`${API_URL}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: userIn.value, password: passIn.value })
        });

        if (res.ok) {
            userIn.value = '';
            passIn.value = '';
            loadUsers(); // Refresh list to see new user
        } else {
            const data = await res.json();
            alert(data.detail || "Failed to create user");
        }
    } catch (err) {
        alert("Connection error");
    }
}
