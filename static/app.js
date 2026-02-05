const API_URL = "";

// Toast notifications
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) {
        // Fallback for login page where toast container doesn't exist
        alert(message);
        return;
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

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
            showError('Registration successful! Please login.');
            document.getElementById('error-msg').style.color = 'var(--success)';
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
let searchTimeout = null;
let currentPage = 0;

function getPerPage() {
    const el = document.getElementById('per-page');
    return el ? parseInt(el.value, 10) : 50;
}

function initSearch() {
    const searchInput = document.getElementById('search-input');
    const statusFilter = document.getElementById('status-filter');
    const perPage = document.getElementById('per-page');
    if (!searchInput) return;

    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        currentPage = 0;
        searchTimeout = setTimeout(loadECOs, 300);
    });
    statusFilter.addEventListener('change', () => { currentPage = 0; loadECOs(); });
    perPage.addEventListener('change', () => { currentPage = 0; loadECOs(); });
}

function changePage(direction) {
    currentPage += direction;
    if (currentPage < 0) currentPage = 0;
    loadECOs();
}

async function loadECOs() {
    const token = localStorage.getItem('eco_token');
    const limit = getPerPage();
    const offset = currentPage * limit;
    const params = new URLSearchParams();
    params.set('limit', limit);
    params.set('offset', offset);
    const searchInput = document.getElementById('search-input');
    const statusFilter = document.getElementById('status-filter');
    if (searchInput && searchInput.value.trim()) {
        params.set('search', searchInput.value.trim());
    }
    if (statusFilter && statusFilter.value) {
        params.set('status', statusFilter.value);
    }

    const tbody = document.getElementById('eco-list');
    // Show loading state
    tbody.innerHTML = '';
    const loadingRow = document.createElement('tr');
    loadingRow.className = 'loading-row';
    const loadingTd = document.createElement('td');
    loadingTd.colSpan = 6;
    loadingTd.innerHTML = '<span class="spinner"></span> Loading...';
    loadingRow.appendChild(loadingTd);
    tbody.appendChild(loadingRow);

    const url = `${API_URL}/ecos?${params.toString()}`;
    const res = await fetch(url, {
        headers: { 'X-API-Token': token }
    });

    if (res.status === 401) logout();

    const list = await res.json();
    tbody.innerHTML = '';

    if (list.length === 0) {
        const emptyRow = document.createElement('tr');
        const emptyTd = document.createElement('td');
        emptyTd.colSpan = 6;
        emptyTd.style.cssText = 'text-align: center; padding: 2rem; color: var(--text-muted);';
        emptyTd.textContent = 'No ECOs found. Create one or adjust your search filters.';
        emptyRow.appendChild(emptyTd);
        tbody.appendChild(emptyRow);
    }

    list.forEach(eco => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid var(--border)';

        const tdId = document.createElement('td');
        tdId.style.padding = '1rem';
        tdId.textContent = `#${eco.id}`;

        const tdTitle = document.createElement('td');
        tdTitle.style.padding = '1rem';
        tdTitle.style.fontWeight = '600';
        tdTitle.textContent = eco.title;

        const tdCreator = document.createElement('td');
        tdCreator.style.padding = '1rem';
        tdCreator.style.color = 'var(--text-muted)';
        tdCreator.textContent = eco.created_by;

        const tdStatus = document.createElement('td');
        tdStatus.style.padding = '1rem';
        const badge = document.createElement('span');
        badge.className = `badge ${getStatusClass(eco.status)}`;
        badge.textContent = eco.status;
        tdStatus.appendChild(badge);

        const tdDate = document.createElement('td');
        tdDate.style.padding = '1rem';
        tdDate.style.color = 'var(--text-muted)';
        tdDate.textContent = new Date(eco.created_at).toLocaleDateString();

        const tdAction = document.createElement('td');
        tdAction.style.padding = '1rem';
        const viewBtn = document.createElement('button');
        viewBtn.className = 'btn btn-primary';
        viewBtn.style.padding = '0.5rem 1rem';
        viewBtn.style.fontSize = '0.8rem';
        viewBtn.textContent = 'View';
        viewBtn.onclick = () => openDetail(eco.id);
        tdAction.appendChild(viewBtn);

        tr.append(tdId, tdTitle, tdCreator, tdStatus, tdDate, tdAction);
        tbody.appendChild(tr);
    });

    // Update pagination controls
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const pageInfo = document.getElementById('page-info');
    if (prevBtn) prevBtn.disabled = currentPage === 0;
    if (nextBtn) nextBtn.disabled = list.length < limit;
    if (pageInfo) pageInfo.textContent = `Page ${currentPage + 1}`;
}

function getStatusClass(status) {
    switch (status) {
        case 'DRAFT': return 'badge-draft';
        case 'SUBMITTED': return 'badge-submitted';
        case 'APPROVED': return 'badge-approved';
        case 'REJECTED': return 'badge-rejected';
        default: return '';
    }
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
        showToast('ECO created successfully');
        loadECOs();
    } else {
        showToast('Failed to create ECO', 'error');
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
        li.style.marginBottom = '0.5rem';
        const link = document.createElement('a');
        link.href = '#';
        link.textContent = f.filename;
        link.onclick = (e) => { e.preventDefault(); viewAttachment(f.filename); };
        const uploader = document.createElement('span');
        uploader.style.color = 'var(--text-muted)';
        uploader.style.fontSize = '0.9em';
        uploader.textContent = ` (${f.uploaded_by})`;
        li.append(link, uploader);
        fileList.appendChild(li);
    });

    // History
    const historyDiv = document.getElementById('detail-history');
    historyDiv.innerHTML = '';
    data.history.forEach(h => {
        const entry = document.createElement('div');
        entry.style.cssText = 'margin-bottom: 0.5rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border);';
        const actionEl = document.createElement('strong');
        actionEl.textContent = h.action;
        const infoText = document.createTextNode(` by ${h.username} at ${new Date(h.performed_at).toLocaleString()}`);
        entry.append(actionEl, infoText);
        if (h.comment) {
            entry.appendChild(document.createElement('br'));
            const commentEl = document.createElement('em');
            commentEl.textContent = `"${h.comment}"`;
            entry.appendChild(commentEl);
        }
        historyDiv.appendChild(entry);
    });

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

    // Admin actions: Edit and Delete
    if (localStorage.getItem('eco_is_admin') === 'true') {
        const sep = document.createElement('hr');
        sep.style.cssText = 'border: 0; border-top: 1px solid var(--border); margin: 0.75rem 0;';
        actionsDiv.appendChild(sep);

        const editBtn = document.createElement('button');
        editBtn.className = 'btn';
        editBtn.style.cssText = 'background: rgba(255,255,255,0.1); border: 1px solid var(--border); width: 100%; margin-bottom: 0.5rem;';
        editBtn.textContent = 'Edit ECO';
        editBtn.onclick = () => openEditModal(data);
        actionsDiv.appendChild(editBtn);

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn btn-danger';
        deleteBtn.style.width = '100%';
        deleteBtn.textContent = 'Delete ECO';
        deleteBtn.onclick = () => handleDeleteECO(data.id);
        actionsDiv.appendChild(deleteBtn);
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
        showToast(d.detail || 'Action failed', 'error');
    }
}

function openEditModal(data) {
    document.getElementById('edit-eco-title').value = data.title;
    document.getElementById('edit-eco-desc').value = data.description;
    document.getElementById('edit-modal').classList.remove('hidden');
}

function hideEditModal() {
    document.getElementById('edit-modal').classList.add('hidden');
}

async function handleEditECO(e) {
    e.preventDefault();
    const title = document.getElementById('edit-eco-title').value;
    const desc = document.getElementById('edit-eco-desc').value;
    const token = localStorage.getItem('eco_token');

    const res = await fetch(`${API_URL}/ecos/${currentEcoId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Token': token
        },
        body: JSON.stringify({ title: title, description: desc })
    });

    if (res.ok) {
        hideEditModal();
        openDetail(currentEcoId);
    } else {
        const d = await res.json();
        showToast(d.detail || 'Failed to update ECO', 'error');
    }
}

async function handleDeleteECO(ecoId) {
    if (!confirm('Are you sure you want to permanently delete this ECO? This cannot be undone.')) return;

    const token = localStorage.getItem('eco_token');
    const res = await fetch(`${API_URL}/ecos/${ecoId}`, {
        method: 'DELETE',
        headers: { 'X-API-Token': token }
    });

    if (res.ok) {
        hideDetailModal();
    } else {
        const d = await res.json();
        showToast(d.detail || 'Failed to delete ECO', 'error');
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
        showToast('File uploaded successfully');
        openDetail(currentEcoId);
    } else {
        showToast('Upload failed', 'error');
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
        showToast('Download failed', 'error');
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
            showToast('Failed to view attachment', 'error');
        }
    } catch (e) {
        showToast('Error fetching attachment', 'error');
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
        showToast('Failed to load users', 'error');
        return;
    }

    const users = await res.json();
    const tbody = document.getElementById('user-list');
    tbody.innerHTML = '';

    users.forEach(u => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid var(--border)';
        const fullName = [u.first_name, u.last_name].filter(Boolean).join(' ');
        const cellStyle = 'padding: 0.5rem;';

        const cells = [
            u.id || '',
            u.username,
            fullName,
            u.email || '',
        ];
        cells.forEach(text => {
            const td = document.createElement('td');
            td.style.cssText = cellStyle;
            td.textContent = text;
            tr.appendChild(td);
        });

        // Role cell
        const roleTd = document.createElement('td');
        roleTd.style.cssText = cellStyle;
        if (u.is_admin) {
            const roleSpan = document.createElement('span');
            roleSpan.style.color = 'var(--success)';
            roleSpan.textContent = 'Admin';
            roleTd.appendChild(roleSpan);
        } else {
            roleTd.textContent = 'User';
        }
        tr.appendChild(roleTd);

        // Delete cell
        const actionTd = document.createElement('td');
        actionTd.style.cssText = cellStyle;
        if (!u.is_admin) {
            const delBtn = document.createElement('button');
            delBtn.className = 'btn btn-danger';
            delBtn.style.cssText = 'padding: 0.25rem 0.5rem; font-size: 0.8rem;';
            delBtn.textContent = 'Delete';
            delBtn.onclick = () => deleteUser(u.id);
            actionTd.appendChild(delBtn);
        }
        tr.appendChild(actionTd);

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
        showToast('User deleted');
        loadUsers();
    } else {
        showToast('Failed to delete user', 'error');
    }
}

async function handleAdminAddUser(e) {
    e.preventDefault();
    const userIn = document.getElementById('admin-new-user');
    const passIn = document.getElementById('admin-new-pass');
    const firstIn = document.getElementById('admin-new-first');
    const lastIn = document.getElementById('admin-new-last');
    const emailIn = document.getElementById('admin-new-email');

    const payload = {
        username: userIn.value,
        password: passIn.value,
        first_name: firstIn.value,
        last_name: lastIn.value,
        email: emailIn.value
    };

    try {
        const res = await fetch(`${API_URL}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            userIn.value = '';
            passIn.value = '';
            firstIn.value = '';
            lastIn.value = '';
            emailIn.value = '';
            showToast('User added successfully');
            loadUsers();
        } else {
            const data = await res.json();
            showToast(data.detail || 'Failed to create user', 'error');
        }
    } catch (err) {
        showToast('Connection error', 'error');
    }
}

// Help
function openHelp() {
    document.getElementById('help-modal').classList.remove('hidden');
}

function hideHelp() {
    document.getElementById('help-modal').classList.add('hidden');
}

// Close modals on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('#help-modal, #edit-modal, #detail-modal, #create-modal, #admin-modal').forEach(modal => {
            modal.classList.add('hidden');
        });
    }
});
