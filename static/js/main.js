document.addEventListener('DOMContentLoaded', () => {
    
    // --- Navigation Logic ---
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            // Update active nav
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            // Show target view
            const targetId = item.getAttribute('data-target');
            views.forEach(v => v.classList.remove('active'));
            document.getElementById(targetId).classList.add('active');

            // Refresh data based on view
            if (targetId === 'view-queue') loadQueue();
            if (targetId === 'view-activity') loadActivity();
        });
    });

    // --- Toast Notifications ---
    function showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = type === 'success' ? 'fa-check-circle' : 'fa-circle-exclamation';
        toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
        
        container.appendChild(toast);
        
        // Remove after animation (3s)
        setTimeout(() => {
            if(toast.parentElement) {
                toast.remove();
            }
        }, 3000);
    }

    // --- Board List Logic ---
    function updateBoardList(boardNames) {
        const datalist = document.getElementById('boards-list');
        if (!datalist) return;
        datalist.innerHTML = boardNames.map(name => `<option value="${name}">`).join('');
    }

    // --- View 1: Queue Logic ---
    async function loadQueue() {
        const container = document.getElementById('queue-container');
        try {
            const res = await fetch('/api/queue');
            const data = await res.json();
            const boards = Object.keys(data.data);
            updateBoardList(boards);

            if (boards.length === 0) {
                container.innerHTML = '<div class="glass-card text-center"><p>No boards found. Add some images!</p></div>';
                return;
            }

            container.innerHTML = '';
            // Assume 50 is a healthy queue size for the progress bar
            const MAX_HEALTHY = 50; 

            for (const [board, count] of Object.entries(data.data)) {
                let percent = (count / MAX_HEALTHY) * 100;
                if (percent > 100) percent = 100;
                
                let fillClass = '';
                if (count < 5) fillClass = 'empty';
                else if (count < 15) fillClass = 'low';

                const html = `
                    <div class="queue-item">
                        <div class="queue-header">
                            <span class="board-name">${board}</span>
                            <span class="image-count">${count} images</span>
                        </div>
                        <div class="progress-track">
                            <div class="progress-fill ${fillClass}" style="width: ${percent}%"></div>
                        </div>
                    </div>
                `;
                container.innerHTML += html;
            }
        } catch (e) {
            container.innerHTML = '<div class="glass-card text-center"><p class="text-danger">Failed to load queue.</p></div>';
        }
    }

    // --- View 2: Add Logic ---
    const fileInput = document.getElementById('image-upload');
    const fileNameDisplay = document.getElementById('file-name');
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            fileNameDisplay.textContent = e.target.files[0].name;
            fileNameDisplay.style.color = 'var(--success)';
        } else {
            fileNameDisplay.textContent = 'No file chosen';
            fileNameDisplay.style.color = 'var(--danger)';
        }
    });

    document.getElementById('upload-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('upload-btn');
        btn.disabled = true;
        btn.textContent = 'Uploading...';

        const formData = new FormData();
        formData.append('image', fileInput.files[0]);
        formData.append('board_name', document.getElementById('board-select').value);

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.status === 'success') {
                showToast(data.message, 'success');
                fileInput.value = '';
                fileNameDisplay.textContent = 'No file chosen';
                fileNameDisplay.style.color = 'var(--text-muted)';
            } else {
                showToast(data.message, 'error');
            }
        } catch (err) {
            showToast('Upload failed', 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Upload to Queue';
        }
    });

    document.getElementById('titles-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const titlesInput = document.getElementById('title-phrases');
        
        try {
            const res = await fetch('/api/titles', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ titles: titlesInput.value })
            });
            const data = await res.json();
            if (data.status === 'success') {
                showToast(data.message, 'success');
                titlesInput.value = '';
            } else {
                showToast(data.message, 'error');
            }
        } catch (err) {
            showToast('Failed to save titles', 'error');
        }
    });

    // --- View 3: Activity Logic ---
    async function loadActivity() {
        const container = document.getElementById('activity-container');
        try {
            const res = await fetch('/api/activity');
            const data = await res.json();
            
            if (data.data.length === 0) {
                container.innerHTML = '<div class="glass-card text-center"><p>No recent activity.</p></div>';
                return;
            }

            container.innerHTML = '';
            data.data.forEach(item => {
                const isSuccess = item.status.toLowerCase() === 'success';
                const iconClass = isSuccess ? 'success' : 'error';
                const iconName = isSuccess ? 'fa-check' : 'fa-xmark';
                
                const html = `
                    <div class="activity-item">
                        <div class="activity-icon ${iconClass}">
                            <i class="fa-solid ${iconName}"></i>
                        </div>
                        <div class="activity-details">
                            <h4>${item.title || item.filename}</h4>
                            <p>${item.board} • ${item.status}</p>
                            <span class="activity-time">${item.time}</span>
                        </div>
                    </div>
                `;
                container.innerHTML += html;
            });
        } catch (e) {
            container.innerHTML = '<div class="glass-card text-center"><p class="text-danger">Failed to load activity.</p></div>';
        }
    }

    document.getElementById('test-bot-btn').addEventListener('click', async () => {
        try {
            showToast('Triggering manual run...', 'success');
            const res = await fetch('/api/test_bot', { method: 'POST' });
            const data = await res.json();
            showToast(data.message, 'success');
            setTimeout(loadActivity, 1500); // Reload after brief delay
        } catch (e) {
            showToast('Failed to trigger bot', 'error');
        }
    });

    // --- View 4: Clear Done Logic ---
    document.getElementById('clear-done-btn').addEventListener('click', async () => {
        if (!confirm('Are you sure you want to permanently delete all uploaded files?')) return;
        
        try {
            const res = await fetch('/api/clear_done', { method: 'POST' });
            const data = await res.json();
            showToast(data.message, 'success');
        } catch (e) {
            showToast('Failed to clear folder', 'error');
        }
    });

    // Initial load
    loadQueue();
});
