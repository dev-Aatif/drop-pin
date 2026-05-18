document.addEventListener('DOMContentLoaded', () => {
    
    // --- Navigation Logic ---
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            const targetId = item.getAttribute('data-target');
            views.forEach(v => v.classList.remove('active'));
            document.getElementById(targetId).classList.add('active');

            if (targetId === 'view-queue') loadQueue();
            if (targetId === 'view-activity') loadActivity();
            if (targetId === 'view-settings') loadStats();
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
        
        setTimeout(() => {
            if(toast.parentElement) toast.remove();
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
            
            for (const [board, count] of Object.entries(data.data)) {
                let percent = (count / 50) * 100;
                if (percent > 100) percent = 100;
                let fillClass = count < 5 ? 'empty' : (count < 15 ? 'low' : '');

                const html = `
                    <div class="queue-item" onclick="openBoardModal('${board}')">
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

    // --- Modal Logic ---
    const modal = document.getElementById('board-modal');
    const modalClose = document.getElementById('close-modal');
    const modalGrid = document.getElementById('modal-grid');
    const modalBoardName = document.getElementById('modal-board-name');
    let currentModalBoard = '';

    window.openBoardModal = async function(boardName) {
        currentModalBoard = boardName;
        modalBoardName.textContent = boardName;
        modalGrid.innerHTML = '<div class="loading">Loading images...</div>';
        modal.classList.add('active');

        try {
            const res = await fetch(`/api/board/${encodeURIComponent(boardName)}/pins`);
            const data = await res.json();
            
            if (data.data.length === 0) {
                modalGrid.innerHTML = '<p class="text-muted" style="grid-column: 1/-1; text-align: center;">No images found.</p>';
                loadQueue(); // Refresh background queue
                return;
            }

            modalGrid.innerHTML = data.data.map(filename => `
                <div class="masonry-item" id="pin-${filename.replace(/[^a-zA-Z0-9]/g, '-')}">
                    <img src="/pins/${encodeURIComponent(boardName)}/${encodeURIComponent(filename)}" alt="Pin" loading="lazy">
                    <button class="delete-btn" onclick="deletePin('${boardName}', '${filename}')" title="Delete">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            `).join('');
        } catch(e) {
            modalGrid.innerHTML = '<p class="text-danger">Error loading pins.</p>';
        }
    };

    modalClose.addEventListener('click', () => {
        modal.classList.remove('active');
        loadQueue();
    });

    window.deletePin = async function(boardName, filename) {
        if(!confirm('Delete this image?')) return;
        try {
            const res = await fetch('/api/delete_pin', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({board_name: boardName, filename: filename})
            });
            const data = await res.json();
            if (data.status === 'success') {
                document.getElementById(`pin-${filename.replace(/[^a-zA-Z0-9]/g, '-')}`).remove();
                showToast('Deleted', 'success');
            } else {
                showToast(data.message, 'error');
            }
        } catch(e) {
            showToast('Failed to delete', 'error');
        }
    };

    // --- View 2: Add Logic ---
    const fileInput = document.getElementById('image-upload');
    const fileNameDisplay = document.getElementById('file-name');
    const boardSelect = document.getElementById('board-select');
    const boardDesc = document.getElementById('board-description');
    
    fileInput.addEventListener('change', (e) => {
        const count = e.target.files.length;
        if (count > 0) {
            fileNameDisplay.textContent = count === 1 ? e.target.files[0].name : `${count} files selected`;
            fileNameDisplay.style.color = 'var(--success)';
        } else {
            fileNameDisplay.textContent = 'No files chosen';
            fileNameDisplay.style.color = 'var(--danger)';
        }
    });

    let boardDescTimeout;
    const fetchBoardContext = async (boardName) => {
        if(!boardName) return;
        boardDesc.value = 'Loading...';
        try {
            const res = await fetch(`/api/boards/description?board_name=${encodeURIComponent(boardName)}`);
            const data = await res.json();
            if(data.status === 'success' && data.data.description) {
                boardDesc.value = data.data.description;
            } else {
                boardDesc.value = '';
            }
        } catch(e) {
            boardDesc.value = '';
        }
    };

    boardSelect.addEventListener('change', (e) => fetchBoardContext(e.target.value));
    boardSelect.addEventListener('input', (e) => {
        clearTimeout(boardDescTimeout);
        boardDescTimeout = setTimeout(() => fetchBoardContext(e.target.value), 600);
    });

    document.getElementById('save-desc-btn').addEventListener('click', async () => {
        const boardName = boardSelect.value;
        if(!boardName) return showToast('Select a board first', 'error');
        try {
            const res = await fetch('/api/boards/description', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({board_name: boardName, description: boardDesc.value})
            });
            const data = await res.json();
            if(data.status === 'success') showToast('Context saved');
            else showToast(data.message, 'error');
        } catch(e) {
            showToast('Failed to save context', 'error');
        }
    });

    document.getElementById('upload-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const btn = document.getElementById('upload-btn');
        const progressContainer = document.getElementById('upload-progress-container');
        const progressFill = document.getElementById('upload-progress-fill');
        const progressText = document.getElementById('upload-progress-text');
        
        btn.disabled = true;
        btn.textContent = 'Uploading...';
        progressContainer.style.display = 'block';
        progressFill.style.width = '0%';
        progressText.textContent = '0%';

        const formData = new FormData();
        for(let i = 0; i < fileInput.files.length; i++) {
            formData.append('image', fileInput.files[i]);
        }
        formData.append('board_name', boardSelect.value);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/upload', true);

        // Upload progress listener
        xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                progressFill.style.width = `${percent}%`;
                progressText.textContent = `${percent}%`;
            }
        });

        xhr.onload = () => {
            let data = {};
            try {
                data = JSON.parse(xhr.responseText);
            } catch(err) {}

            if (xhr.status === 200 && data.status === 'success') {
                showToast(data.message, 'success');
                fileInput.value = '';
                fileNameDisplay.textContent = 'No files chosen';
                fileNameDisplay.style.color = 'var(--text-muted)';
            } else {
                showToast(data.message || 'Upload failed', 'error');
            }
            
            // Clean up state
            setTimeout(() => {
                progressContainer.style.display = 'none';
            }, 1000);
            btn.disabled = false;
            btn.textContent = 'Upload to Queue';
        };

        xhr.onerror = () => {
            showToast('Upload failed', 'error');
            progressContainer.style.display = 'none';
            btn.disabled = false;
            btn.textContent = 'Upload to Queue';
        };

        xhr.send(formData);
    });



    // --- View 3: Activity Logic ---
    const actModal = document.getElementById('activity-modal');
    const actModalClose = document.getElementById('close-activity-modal');
    const actModalContent = document.getElementById('activity-modal-content');
    
    window.openActivityModal = function(index) {
        if (!window.activityData || !window.activityData[index]) return;
        const item = window.activityData[index];
        
        let formattedTime = item.time;
        try {
            const date = new Date(item.time.replace(' ', 'T'));
            const options = { year: 'numeric', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true };
            formattedTime = date.toLocaleString('en-US', options);
        } catch(e) {}
        
        actModalContent.innerHTML = `
            <div style="width: 100%; border-radius: 8px; overflow: hidden; margin-bottom: 8px; border: 1px solid var(--border-color);">
                <img src="/done/${encodeURIComponent(item.filename)}" alt="Thumbnail" style="width: 100%; height: 240px; object-fit: contain; background: #000;" onerror="this.src=''">
            </div>
            <h4 style="font-size: 1.1rem; color: var(--text-main); margin-bottom: 4px;">${item.title || 'No Title'}</h4>
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 12px; display: flex; flex-direction: column; gap: 6px;">
                <span><i class="fa-solid fa-folder-open" style="width: 16px;"></i> ${item.board}</span>
                <span><i class="fa-regular fa-clock" style="width: 16px;"></i> ${formattedTime}</span>
            </div>
            <div style="background: var(--bg-main); padding: 12px; border-radius: 8px; font-size: 0.85rem; line-height: 1.5; color: var(--text-main); max-height: 150px; overflow-y: auto;">
                ${item.description ? item.description.replace(/\n/g, '<br>') : 'No description available.'}
            </div>
            <div style="text-align: right; margin-top: 8px;">
                <span style="font-size: 0.8rem; padding: 4px 10px; border-radius: 12px; background: ${item.status.toLowerCase().includes('success') ? 'var(--success)' : 'var(--danger)'}; color: #000; font-weight: 700;">${item.status}</span>
            </div>
        `;
        actModal.classList.add('active');
    };
    
    if (actModalClose) {
        actModalClose.addEventListener('click', () => {
            actModal.classList.remove('active');
        });
    }

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
            window.activityData = data.data; // Store globally for modal access
            
            data.data.forEach((item, index) => {
                const isSuccess = item.status.toLowerCase().includes('success');
                const iconClass = isSuccess ? 'success' : 'error';
                const iconName = isSuccess ? 'fa-check' : 'fa-xmark';
                
                const html = `
                    <div class="activity-item" style="cursor: pointer;" onclick="openActivityModal(${index})">
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
            const res = await fetch(`/api/test_bot?force=true`, { method: 'POST' });
            const data = await res.json();
            showToast(data.message, data.status === 'success' ? 'success' : 'error');
            setTimeout(loadActivity, 1500);
        } catch (e) {
            showToast('Failed to trigger bot', 'error');
        }
    });

    // --- View 4: Settings/Stats Logic ---
    async function loadStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();
            if (data.status === 'success') {
                document.getElementById('stat-total').textContent = data.data.total_posts;
                document.getElementById('stat-queued').textContent = data.data.total_queued;
                
                // Storage Logic
                const storageFill = document.getElementById('stat-storage-fill');
                if(storageFill) {
                    storageFill.style.width = `${data.data.storage.percent}%`;
                    if (data.data.storage.percent > 85) storageFill.style.background = 'var(--danger)';
                    document.getElementById('stat-storage-used').textContent = `${data.data.storage.used_mb} MB Used`;
                }
                
                // Queue Breakdown Logic
                const qb = document.getElementById('stat-queue-breakdown');
                if(qb) {
                    qb.innerHTML = '';
                    if (Object.keys(data.data.queue_breakdown).length === 0) {
                        qb.innerHTML = '<div class="text-muted">No images queued.</div>';
                    } else {
                        for (const [board, count] of Object.entries(data.data.queue_breakdown)) {
                            qb.innerHTML += `<div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.05);"><span style="color: var(--text-main);">${board}</span><span style="color: var(--accent); font-weight: bold;">${count}</span></div>`;
                        }
                    }
                }
            }
        } catch (e) {
            console.error('Failed to load stats');
        }
    }

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
