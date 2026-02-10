document.addEventListener('DOMContentLoaded', () => {
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const clearBtn = document.getElementById('clear-chat');
    const stopBtn = document.getElementById('stop-btn');
    const agentStatus = document.getElementById('agent-status');
    
    // Model select
    const modelSelect = document.getElementById('model-select');
    const planningBtn = document.getElementById('planning-mode-btn');

    // Sidebar elements
    const sidebarLeft = document.querySelector('.sidebar-left');
    const sidebarRight = document.querySelector('.sidebar-right');

    // Image upload elements
    const imageInput = document.getElementById('image-input');
    const uploadBtn = document.getElementById('upload-btn');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const imagePreview = document.getElementById('image-preview');
    const removeImageBtn = document.getElementById('remove-image');
    const imageName = document.getElementById('image-name');
    
    // Global State
    let currentImageData = null;
    let currentImageMime = null;
    let conversationHistory = [];
    let pendingContent = '';
    let currentContentDiv = null;
    let updateInterval = null;

    let modelMap = {}; // Cache model info

    // Unified Chat Stream State
    let currentBlockType = null;  // 'text' | 'thinking' | 'tool'
    let currentBlockElement = null;
    let currentTurnContainer = null;
    let currentToolBlock = null;

    // Tool visibility preference
    let autoExpandTools = localStorage.getItem('autoExpandTools') === 'true';

    // Block creation functions for unified chat stream
    function createTurnContainer() {
        const container = document.createElement('div');
        container.className = 'turn-container active';
        chatHistory.appendChild(container);
        return container;
    }

    function createThinkingBlock(parent) {
        const details = document.createElement('details');
        details.className = 'thinking-block';
        details.innerHTML = `<summary>Thinking...</summary><div class="thinking-content"></div>`;
        parent.appendChild(details);
        return details.querySelector('.thinking-content');
    }

    function createToolBlock(parent, toolName) {
        const block = document.createElement('div');
        block.className = 'tool-block running' + (autoExpandTools ? ' expanded' : '');
        block.innerHTML = `
            <div class="tool-block-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="tool-block-name">🔧 ${escapeHtml(toolName)}</span>
                <span class="tool-block-status">running...</span>
                <span class="tool-block-toggle">▼</span>
            </div>
            <div class="tool-block-content"></div>
        `;
        parent.appendChild(block);
        return block;
    }

    function createTextBlock(parent) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant';
        const contentDiv = document.createElement('div');
        contentDiv.className = 'content-block';
        msgDiv.appendChild(contentDiv);
        parent.appendChild(msgDiv);
        return contentDiv;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initial load
    fetchModels();
    fetchBackups();
    fetchSessionHistory();
    fetchWorkspace();
    fetchBalance();
    initSidebar();
    restoreConversation();

    // Planning mode toggle
    if (planningBtn) {
        planningBtn.addEventListener('click', () => {
            planningBtn.classList.toggle('active');
        });
    }

    // Restore conversation from server on page load
    async function restoreConversation() {
        try {
            const res = await fetch('/api/conversation');
            const data = await res.json();
            if (data.success && data.messages && data.messages.length > 0) {
                // Clear default welcome message
                chatHistory.innerHTML = '';

                // Render each message
                data.messages.forEach(msg => {
                    if (msg.role === 'user') {
                        const content = typeof msg.content === 'string' ? msg.content : '[Image message]';
                        appendMessage('user', content);
                        conversationHistory.push(msg);
                    } else if (msg.role === 'assistant') {
                        if (msg.content) {
                            appendMessage('assistant', msg.content);
                            conversationHistory.push(msg);
                        }
                    }
                    // Skip tool messages for display
                });

                console.log(`Restored ${data.count} messages from server`);
                updateContextPulse(conversationHistory);
            }
        } catch (e) {
            console.error('Failed to restore conversation:', e);
        }
    }

    // Event Listeners
    modelSelect.addEventListener('change', async () => {
        const model = modelSelect.value;
        updateCapabilitiesDisplay(model);
        updateContextPulse(conversationHistory); // Refresh gauge with new limit
        await fetch('/api/models', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({model})
        });
    });

    let isProcessing = false;

    function setButtonState(processing) {
        isProcessing = processing;
        const sendBtn = document.getElementById('send-btn');
        const icon = document.getElementById('send-icon');
        
        if (processing) {
            sendBtn.classList.add('stop-state');
            // Square icon for STOP
            icon.innerHTML = '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/>';
        } else {
            sendBtn.classList.remove('stop-state');
            // Up arrow icon for SEND
            icon.innerHTML = '<path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor"/>';
        }
    }

    sendBtn.addEventListener('click', () => {
        if (isProcessing) {
            fetch('/api/interrupt', { method: 'POST' });
        } else {
            sendMessage();
        }
    });

    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!isProcessing) sendMessage();
        }
    });

    // Auto-resize textarea
    function adjustTextareaHeight() {
        userInput.style.height = '44px';
        const newHeight = Math.min(userInput.scrollHeight, 314);
        userInput.style.height = newHeight + 'px';
        userInput.style.overflowY = userInput.scrollHeight > 314 ? 'auto' : 'hidden';
    }
    userInput.addEventListener('input', adjustTextareaHeight);

    // --- Sidebar Initialization ---
    function initSidebar() {
        // Workspace Selector (Dropdown)
        const workspaceSelect = document.getElementById('workspace-select');

        // Populate workspace dropdown
        async function loadWorkspaces() {
            try {
                const res = await fetch('/api/workspaces');
                const data = await res.json();
                if (data.success && workspaceSelect) {
                    workspaceSelect.innerHTML = '';
                    data.workspaces.forEach(ws => {
                        const opt = document.createElement('option');
                        opt.value = ws.path;
                        opt.textContent = ws.name;
                        if (ws.is_current) opt.selected = true;
                        workspaceSelect.appendChild(opt);
                    });
                }
            } catch (e) {
                console.error('Failed to load workspaces:', e);
            }
        }
        loadWorkspaces();

        // Handle workspace change
        workspaceSelect?.addEventListener('change', async () => {
            const newPath = workspaceSelect.value;
            if (!newPath) return;
            const res = await fetch('/api/workspace', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: newPath})
            });
            const data = await res.json();
            if (data.success) {
                // Clear conversation history on workspace switch
                conversationHistory = [];
                chatHistory.innerHTML = '';
                appendMessage('system', `Workspace changed to: ${workspaceSelect.options[workspaceSelect.selectedIndex].text}`);
            } else {
                alert('Error: ' + data.error);
                loadWorkspaces(); // Reload to reset selection
            }
        });

        // Left Sidebar Tab switching
        const leftTabBtns = document.querySelectorAll('.sidebar-left .tab-btn');
        const leftTabPanels = document.querySelectorAll('.sidebar-left .tab-panel');

        leftTabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabId = btn.dataset.tab;
                leftTabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                leftTabPanels.forEach(p => p.classList.remove('active'));
                const targetPanel = document.querySelector(`.sidebar-left #tab-${tabId}`);
                if (targetPanel) targetPanel.classList.add('active');
                if (tabId === 'git') refreshGitStatus();
            });
        });

        // Right Sidebar Tab switching
        const rightTabBtns = document.querySelectorAll('.sidebar-right .tab-btn');
        const rightTabPanels = document.querySelectorAll('.sidebar-right .tab-panel');

        rightTabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabId = btn.dataset.tab;
                rightTabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                rightTabPanels.forEach(p => p.classList.remove('active'));
                const targetPanel = document.querySelector(`.sidebar-right #tab-${tabId}`);
                if (targetPanel) targetPanel.classList.add('active');
                if (tabId === 'backups') {
                    fetchBackups();
                    fetchSessionHistory();
                }
            });
        });

        // Macro Buttons
        document.querySelectorAll('.macro-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const text = btn.querySelector('.macro-text')?.textContent;
                if (text === 'Forget') {
                    if (confirm('Are you sure you want to clear all memory and conversation history?')) {
                        try {
                            const res = await fetch('/api/forget', { method: 'POST' });
                            const data = await res.json();
                            if (data.success) {
                                conversationHistory = [];
                                chatHistory.innerHTML = '<div class="message system">Memory cleared.</div>';
                                updateContextPulse([]);
                            } else {
                                alert('Error: ' + data.error);
                            }
                        } catch (e) {
                            alert('Failed to clear memory: ' + e.message);
                        }
                    }
                    return;
                }
                userInput.value = btn.dataset.prompt;
                sendMessage();
            });
        });

        // Git Refresh
        document.getElementById('git-refresh')?.addEventListener('click', refreshGitStatus);

        // Auto-expand tools toggle
        const autoExpandToggle = document.getElementById('auto-expand-tools');
        if (autoExpandToggle) {
            autoExpandToggle.checked = autoExpandTools;
            autoExpandToggle.addEventListener('change', () => {
                autoExpandTools = autoExpandToggle.checked;
                localStorage.setItem('autoExpandTools', autoExpandTools);
            });
        }

        // Save Session Button
        const saveSessionBtn = document.getElementById('save-session-btn');
        if (saveSessionBtn) {
            saveSessionBtn.addEventListener('click', async () => {
                saveSessionBtn.classList.add('saving');
                saveSessionBtn.textContent = 'Saving...';

                try {
                    const res = await fetch('/api/save-session', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            history: conversationHistory
                        })
                    });
                    const data = await res.json();

                    if (data.success) {
                        saveSessionBtn.classList.remove('saving');
                        saveSessionBtn.classList.add('saved');
                        saveSessionBtn.innerHTML = '<span class="macro-icon">✓</span> Saved!';
                        appendMessage('system', `Session saved: ${data.summary || 'No summary'}`);
                        fetchSessionHistory(); // Refresh the session list

                        setTimeout(() => {
                            saveSessionBtn.classList.remove('saved');
                            saveSessionBtn.innerHTML = '<span class="macro-icon">💾</span> Save Session';
                        }, 2000);
                    } else {
                        throw new Error(data.error || 'Save failed');
                    }
                } catch (e) {
                    saveSessionBtn.classList.remove('saving');
                    saveSessionBtn.innerHTML = '<span class="macro-icon">💾</span> Save Session';
                    alert('Failed to save session: ' + e.message);
                }
            });
        }

        // Lagoon-style Upload Button
        const uploadBtn = document.getElementById('upload-btn');
        const imageInput = document.getElementById('image-input');
        uploadBtn?.addEventListener('click', () => imageInput.click());

        // Screenshot Button
        const screenshotBtn = document.getElementById('screenshot-btn');
        if (screenshotBtn) {
            screenshotBtn.addEventListener('click', async () => {
                try {
                    const stream = await navigator.mediaDevices.getDisplayMedia({ 
                        video: { cursor: "always" }, 
                        audio: false 
                    });
                    const video = document.createElement('video');
                    video.srcObject = stream;
                    video.onloadedmetadata = async () => {
                        await video.play();
                        // Capture frame
                        const canvas = document.createElement('canvas');
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                        
                        // Stop stream
                        stream.getTracks().forEach(track => track.stop());

                        // Set as current image
                        currentImageData = canvas.toDataURL('image/png').split(',')[1];
                        currentImageMime = 'image/png';
                        imagePreview.src = canvas.toDataURL('image/png');
                        imageName.textContent = "Screenshot " + new Date().toLocaleTimeString();
                        imagePreviewContainer.style.display = 'flex';
                        document.getElementById('upload-btn').classList.add('has-image');
                    };
                } catch (err) {
                    console.error("Error capturing screenshot: " + err);
                }
            });
        }

        // Image Editor Logic
        const editorDropzone = document.getElementById('editor-dropzone');
        const editorInput = document.getElementById('editor-image-input');
        const editorSource = document.getElementById('editor-source-image');
        const editorPreviewArea = document.getElementById('editor-preview-area');
        const editorUploadArea = document.getElementById('editor-upload-area');
        const editorClearBtn = document.getElementById('editor-clear-image');
        const editorPrompt = document.getElementById('editor-prompt');
        const editorSubmit = document.getElementById('editor-submit');
        const editorResultArea = document.getElementById('editor-result-area');
        const editorResultImg = document.getElementById('editor-result-image');
        const editorDownload = document.getElementById('editor-download');
        const editorStatus = document.getElementById('editor-status');

        let editorImageB64 = null;

        if (editorDropzone) {
            editorInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                handleEditorFile(file);
            });

            editorDropzone.addEventListener('dragover', (e) => {
                e.preventDefault();
                editorDropzone.classList.add('dragover');
            });

            editorDropzone.addEventListener('dragleave', () => editorDropzone.classList.remove('dragover'));

            editorDropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                editorDropzone.classList.remove('dragover');
                if (e.dataTransfer.files.length) handleEditorFile(e.dataTransfer.files[0]);
            });
        }

        function handleEditorFile(file) {
            if (!file || !file.type.startsWith('image/')) return;
            const reader = new FileReader();
            reader.onload = (e) => {
                editorSource.src = e.target.result;
                editorImageB64 = e.target.result.split(',')[1];
                editorUploadArea.style.display = 'none';
                editorPreviewArea.style.display = 'block';
                checkEditorReady();
            };
            reader.readAsDataURL(file);
        }

        if (editorClearBtn) {
            editorClearBtn.addEventListener('click', () => {
                editorImageB64 = null;
                editorInput.value = '';
                editorSource.src = '';
                editorPreviewArea.style.display = 'none';
                editorUploadArea.style.display = 'block';
                checkEditorReady();
            });
        }

        if (editorPrompt) {
            editorPrompt.addEventListener('input', checkEditorReady);
        }

        function checkEditorReady() {
            // Enable submit if we have a prompt (image is optional for text-to-image)
            const hasPrompt = editorPrompt.value.trim().length > 0;
            if (editorSubmit) editorSubmit.disabled = !hasPrompt;
        }

        if (editorSubmit) {
            editorSubmit.addEventListener('click', async () => {
                if (editorSubmit.disabled) return;
                
                editorStatus.textContent = "Generating...";
                editorSubmit.disabled = true;
                editorResultArea.style.display = 'none';

                try {
                    const res = await fetch('/api/image/edit', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            prompt: editorPrompt.value.trim(),
                            image: editorImageB64 
                        })
                    });
                    
                    const data = await res.json();
                    
                    if (data.success) {
                        editorResultImg.src = data.image_url;
                        editorResultArea.style.display = 'block';
                        editorStatus.textContent = "Done!";
                        
                        // Setup download
                        editorDownload.onclick = () => {
                            const a = document.createElement('a');
                            a.href = data.image_url;
                            a.download = `venice_edit_${Date.now()}.png`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                        };
                    } else {
                        editorStatus.textContent = "Error: " + data.error;
                    }
                } catch (e) {
                    editorStatus.textContent = "Error: " + e.message;
                } finally {
                    editorSubmit.disabled = false;
                }
            });
        }

        // Vertical Splitter Logic (sidebar resizing)
        let isDraggingVertical = false;
        let activeVerticalSplitter = null;
        const splitterLeft = document.getElementById('splitter-left');
        const splitterRight = document.getElementById('splitter-right');

        if (splitterLeft) {
            splitterLeft.addEventListener('mousedown', (e) => {
                isDraggingVertical = true;
                activeVerticalSplitter = splitterLeft;
                document.body.style.cursor = 'col-resize';
                splitterLeft.classList.add('dragging');
                e.preventDefault();
            });
        }

        if (splitterRight) {
            splitterRight.addEventListener('mousedown', (e) => {
                isDraggingVertical = true;
                activeVerticalSplitter = splitterRight;
                document.body.style.cursor = 'col-resize';
                splitterRight.classList.add('dragging');
                e.preventDefault();
            });
        }

        document.addEventListener('mousemove', (e) => {
            if (isDraggingVertical && activeVerticalSplitter) {
                const containerWidth = document.querySelector('.app-container').offsetWidth;
                if (activeVerticalSplitter === splitterLeft) {
                    const newWidth = e.clientX;
                    if (newWidth > 100 && newWidth < 500) sidebarLeft.style.width = `${newWidth}px`;
                } else if (activeVerticalSplitter === splitterRight) {
                    const newWidth = containerWidth - e.clientX;
                    if (newWidth > 100 && newWidth < 500) sidebarRight.style.width = `${newWidth}px`;
                }
            }
        });

        document.addEventListener('mouseup', () => {
            isDraggingVertical = false;
            activeVerticalSplitter = null;
            document.body.style.cursor = 'default';
            if (splitterLeft) splitterLeft.classList.remove('dragging');
            if (splitterRight) splitterRight.classList.remove('dragging');
        });
    }

    // --- Core Functions ---

    async function fetchModels() {
        try {
            const res = await fetch('/api/models');
            const data = await res.json();
            modelSelect.innerHTML = '';
            modelMap = data.models; // Store map
            
            Object.entries(data.models).forEach(([id, info]) => {
                const option = document.createElement('option');
                option.value = id;
                option.textContent = info.name;
                if (id === data.current) option.selected = true;
                modelSelect.appendChild(option);
            });
            
            updateCapabilitiesDisplay(data.current);
            updateContextPulse(conversationHistory);
        } catch (e) {
            console.error('Failed to fetch models', e);
        }
    }

    function updateCapabilitiesDisplay(modelId) {
        const capSpan = document.getElementById('model-capabilities');
        const rankBadge = document.getElementById('model-rank-badge');
        const priceBadge = document.getElementById('model-price-badge');
        
        if (modelMap[modelId]) {
            const m = modelMap[modelId];
            
            // 1. Rank Badge
            if (rankBadge) {
                let rankClass = 'rank-3';
                if (m.rank === 1) rankClass = 'rank-1';
                else if (m.rank === 2) rankClass = 'rank-2';
                else if (m.rank === 4) rankClass = 'rank-4';
                else if (m.rank === 0) rankClass = 'rank-0';
                
                rankBadge.innerHTML = m.strength ? `<span class="model-strength ${rankClass}">${m.strength}</span>` : '';
            }

            // 2. Price Badge (Top Header)
            if (priceBadge) {
                if (m.price_in !== undefined && m.price_out !== undefined) {
                    priceBadge.innerHTML = `<span class="model-price">[${m.price_in}/${m.price_out}]</span>`;
                } else {
                    priceBadge.innerHTML = '';
                }
            }

            // 3. Capabilities (Console Header)
            if (capSpan) {
                capSpan.innerHTML = m.description;
            }
        }
    }

    async function fetchWorkspace() {
        // Workspace is now managed by dropdown - this syncs the selection
        try {
            const res = await fetch('/api/workspace');
            const data = await res.json();
            if (data.success) {
                const select = document.getElementById('workspace-select');
                if (select) select.value = data.path;
            }
        } catch (e) {}
    }

    async function refreshGitStatus() {
        const gitLog = document.getElementById('git-status-log');
        const gitStatusInfo = document.getElementById('git-status-info');
        const gitTreeLog = document.getElementById('git-tree-log');
        
        if (!gitLog || !gitStatusInfo || !gitTreeLog) return;
        
        gitLog.innerHTML = '<em>Loading status...</em>';
        gitTreeLog.innerHTML = '<em>Loading tree...</em>';

        try {
            // 1. Fetch structured status
            const statusRes = await fetch('/api/git/status');
            const statusData = await statusRes.json();
            
            if (statusData.success) {
                let infoHtml = `<div><strong>Branch:</strong> <span class="git-branch-tag">${statusData.branch}</span></div>`;
                if (statusData.ahead_behind) {
                    infoHtml += `<div><strong>Sync:</strong> Ahead ${statusData.ahead_behind.ahead}, Behind ${statusData.ahead_behind.behind}</div>`;
                }
                infoHtml += `<div><strong>Status:</strong> ${statusData.is_clean ? '<span class="ansi-green">Clean</span>' : '<span class="ansi-yellow">Modified</span>'}</div>`;
                gitStatusInfo.innerHTML = infoHtml;

                // Build a summary for the log area
                let statusLog = `Staged: ${statusData.staged.length}\nUnstaged: ${statusData.unstaged.length}\nUntracked: ${statusData.untracked.length}`;
                gitLog.textContent = statusLog;
            } else {
                gitStatusInfo.innerHTML = `<div class="ansi-red">Error: ${statusData.error}</div>`;
                gitLog.textContent = 'Failed to get status';
            }

            // 2. Fetch Git Graph
            const graphRes = await fetch('/api/git/graph');
            const graphData = await graphRes.json();
            
            if (graphData.success) {
                renderGitTree(graphData.output);
            } else {
                gitTreeLog.textContent = 'Failed to load tree';
            }

        } catch (e) {
            console.error('Git refresh error:', e);
            gitLog.textContent = 'Error connecting to Git API';
        }
    }

    function renderGitTree(rawGraph) {
        const container = document.getElementById('git-tree-log');
        container.innerHTML = '';
        
        const lines = rawGraph.split('\n');
        lines.forEach(line => {
            if (!line.trim()) return;
            
            const lineEl = document.createElement('div');
            lineEl.className = 'git-tree-line';
            
            // Highlight current HEAD
            if (line.includes('(HEAD ->')) {
                lineEl.classList.add('current-head');
            }

            // Make commit hashes clickable
            const commitMatch = line.match(/([0-9a-f]{7,})/);
            if (commitMatch) {
                const hash = commitMatch[1];
                lineEl.dataset.hash = hash;
                lineEl.title = `Click to checkout ${hash}`;
                lineEl.onclick = () => handleGitCheckout(hash);
                
                // Colorize components
                let formatted = line
                    .replace(/([0-9a-f]{7,})/, '<span class="git-commit-hash">$1</span>')
                    .replace(/\(([^)]+)\)/, '<span class="git-branch-tag">($1)</span>');
                
                lineEl.innerHTML = formatted;
            } else {
                lineEl.textContent = line;
            }
            
            container.appendChild(lineEl);
        });
    }

    async function handleGitCheckout(target) {
        if (!confirm(`Are you sure you want to checkout ${target}?`)) return;
        
        try {
            const res = await fetch('/api/git/checkout', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({target})
            });
            const data = await res.json();
            
            if (data.success) {
                appendMessage('system', `Git: Checked out ${target}`);
                refreshGitStatus();
            } else {
                alert('Checkout failed: ' + data.error);
            }
        } catch (e) {
            alert('Error during checkout: ' + e.message);
        }
    }

    // Git Action Listeners
    document.getElementById('git-diff-btn')?.addEventListener('click', () => {
        userInput.value = "Show me the current git diff";
        sendMessage();
    });

    document.getElementById('git-commit-btn')?.addEventListener('click', async () => {
        const msg = prompt('Enter commit message:');
        if (!msg) return;
        
        // This would need a /api/git/commit endpoint which we'll add if needed
        // For now, let's just use a macro-like approach or suggest it to the agent
        userInput.value = `Stage all changes and commit with message: "${msg}"`;
        sendMessage();
    });

    document.getElementById('git-branch-btn')?.addEventListener('click', () => {
        const name = prompt('Enter new branch name:');
        if (!name) return;
        userInput.value = `Create and switch to new git branch: "${name}"`;
        sendMessage();
    });

    document.getElementById('git-checkout-btn')?.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/git/branches');
            const data = await res.json();
            if (data.success) {
                const names = data.branches.map(b => b.name).join(', ');
                const target = prompt(`Enter branch or commit to checkout (Available: ${names}):`);
                if (target) handleGitCheckout(target);
            }
        } catch (e) {}
    });

    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text && !currentImageData) return;

        if (currentImageData) {
            appendMessageWithImage('user', text, `data:${currentImageMime};base64,${currentImageData}`);
        } else {
            appendMessage('user', text);
        }
        
        const payload = {
            message: text || '',
            image: currentImageData,
            image_mime: currentImageMime,
            model: modelSelect.value,
            planning_mode: planningBtn ? planningBtn.classList.contains('active') : false
        };
        
        conversationHistory.push({ role: 'user', content: payload.message });
        userInput.value = '';
        userInput.style.height = '44px';
        userInput.style.overflowY = 'hidden';
        clearImageUpload();
        userInput.disabled = true;
        userInput.parentElement.classList.add('thinking');
        sendBtn.disabled = false; // Keep enabled for STOP
        setButtonState(true);
        agentStatus.textContent = 'Processing...';

        // Create turn container for unified chat stream
        currentTurnContainer = createTurnContainer();
        currentBlockType = null;
        currentBlockElement = null;
        currentToolBlock = null;
        scrollToBottom();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split('\n\n');
                buffer = parts.pop();

                for (const part of parts) {
                    if (!part.trim()) continue;
                    const lines = part.split('\n');
                    let event = '', data = '';
                    for (const line of lines) {
                        if (line.startsWith('event: ')) event = line.slice(7).trim();
                        else if (line.startsWith('data: ')) data = line.slice(6).trim();
                    }
                    if (event && data) {
                        try {
                            handleSSEEvent(event, JSON.parse(data));
                        } catch (e) {}
                    }
                }
            }
        } catch (e) {
            appendMessage('system', 'Error: ' + e.message);
        } finally {
            stopBuffering();
            userInput.disabled = false;
            userInput.placeholder = "Describe a task (e.g., 'Create a flask app in app.py')...";
            userInput.parentElement.classList.remove('thinking');
            setButtonState(false);
            agentStatus.textContent = 'Idle';
            userInput.focus();
        }
    }

    function finalizeCurrentBlock() {
        // Finalize any active block before switching to a new type
        if (currentBlockType === 'text' && currentBlockElement) {
            flushBuffers();
            stopBuffering();
        }
        // For thinking and tool blocks, just clear the references
        currentBlockElement = null;
        currentBlockType = null;
    }

    function handleSSEEvent(event, data) {
        switch (event) {
            case 'metadata':
                if (data.usd_balance !== undefined) updateBalanceDisplay(data.usd_balance);
                if (data.usd_cost !== undefined && parseFloat(data.usd_cost) > 0) {
                     document.getElementById('balance-vcu').textContent = '$' + data.usd_cost;
                     const unitLabel = document.querySelector('#balance-display .balance-label:last-child');
                     if(unitLabel) unitLabel.textContent = '';
                } else if (data.vcu_cost !== undefined && parseFloat(data.vcu_cost) > 0) {
                    document.getElementById('balance-vcu').textContent = data.vcu_cost;
                    const unitLabel = document.querySelector('#balance-display .balance-label:last-child');
                    if(unitLabel) unitLabel.textContent = ' VCU';
                }
                break;

            case 'reasoning':
                // Skip thinking/reasoning content - don't display it
                break;

            case 'content':
                // Switch to text block if not already
                if (currentBlockType !== 'text') {
                    finalizeCurrentBlock();  // Close any previous block
                    currentBlockElement = createTextBlock(currentTurnContainer);
                    currentBlockType = 'text';
                    startBuffering(currentBlockElement);
                }
                pendingContent += data;
                break;

            case 'terminal':
                // Tool output goes to current tool block
                if (currentToolBlock) {
                    const content = currentToolBlock.querySelector('.tool-block-content');
                    content.innerHTML += ansiToHtml(data);
                    scrollToBottom();
                }
                break;

            case 'status':
                // Status updates can indicate tool execution
                if (data.startsWith('Executing ')) {
                    const toolName = data.replace('Executing ', '').replace('...', '');
                    finalizeCurrentBlock();  // Close any previous block before tool
                    currentToolBlock = createToolBlock(currentTurnContainer, toolName);
                    currentBlockType = 'tool';
                }
                agentStatus.textContent = data;
                // Flash status in the main text box
                if (userInput) {
                    userInput.placeholder = ">> " + data;
                }
                break;

            case 'tool_done':
                // Mark tool as complete
                if (currentToolBlock) {
                    const success = data.success !== false;
                    currentToolBlock.classList.remove('running');
                    currentToolBlock.classList.add(success ? 'success' : 'error');
                    const statusEl = currentToolBlock.querySelector('.tool-block-status');
                    statusEl.textContent = success ? '✓' : '✗ ' + (data.error || 'failed');
                    // Auto-collapse successful (unless auto-expand on), always expand errors
                    if (!success) {
                        currentToolBlock.classList.add('expanded');
                    } else if (!autoExpandTools) {
                        currentToolBlock.classList.remove('expanded');
                    }
                    currentToolBlock = null;
                }
                // Clear block tracking after tool completes
                currentBlockType = null;
                currentBlockElement = null;
                break;

            case 'error':
                appendMessage('system', 'Backend Error: ' + data);
                break;

            case 'done':
                flushBuffers();
                stopBuffering();
                if (currentTurnContainer) currentTurnContainer.classList.remove('active');
                if (currentContentDiv && currentContentDiv.dataset.raw) {
                    conversationHistory.push({ role: 'assistant', content: currentContentDiv.dataset.raw });
                }
                currentBlockType = null;
                currentBlockElement = null;
                currentToolBlock = null;
                updateContextPulse(conversationHistory);
                break;
        }
    }

    // --- UI Helpers ---

    function startBuffering(contentDiv) {
        currentContentDiv = contentDiv;
        pendingContent = '';
        if (updateInterval) clearInterval(updateInterval);
        updateInterval = setInterval(flushBuffers, 50);
    }

    function stopBuffering() {
        if (updateInterval) clearInterval(updateInterval);
        updateInterval = null;
        flushBuffers();
        currentContentDiv = null;
    }

    function flushBuffers() {
        if (pendingContent && currentContentDiv) {
            currentContentDiv.dataset.raw = (currentContentDiv.dataset.raw || '') + pendingContent;
            currentContentDiv.innerHTML = marked.parse(currentContentDiv.dataset.raw);
            pendingContent = '';
            scrollToBottom();
        }
    }

    function updateContextPulse(history) {
        if (!history) return;
        let totalChars = 0;
        history.forEach(msg => {
            if (typeof msg.content === 'string') totalChars += msg.content.length;
            else if (Array.isArray(msg.content)) {
                msg.content.forEach(c => { if (c.text) totalChars += c.text.length; });
            }
        });
        const tokens = Math.round(totalChars / 4);
        
        // Dynamic limit
        const currentModelId = modelSelect.value;
        const maxTokens = (modelMap[currentModelId] && modelMap[currentModelId].context_limit) ? modelMap[currentModelId].context_limit : 200000;
        
        const percent = Math.min(100, (tokens / maxTokens) * 100);
        const fill = document.getElementById('pulse-fill');
        const count = document.getElementById('pulse-count');
        
        // Update label with max tokens
        const metaDiv = document.querySelector('.pulse-meta');
        if (metaDiv) {
            // Rebuild the text "X / Y tokens"
            metaDiv.innerHTML = `<span id="pulse-count">${tokens.toLocaleString()}</span> / ${maxTokens.toLocaleString()} <span class="pulse-unit">tokens</span>`;
        }

        if (fill) {
            fill.style.width = percent + '%';
            if (percent > 90) fill.style.backgroundColor = '#f44747';
            else if (percent > 75) fill.style.backgroundColor = '#d7ba7d';
            else fill.style.backgroundColor = '#6a9955';
        }
    }

    function ansiToHtml(text) {
        const colors = { '30': 'ansi-black', '31': 'ansi-red', '32': 'ansi-green', '33': 'ansi-yellow', '34': 'ansi-blue', '35': 'ansi-magenta', '36': 'ansi-cyan', '37': 'ansi-white', '90': 'ansi-grey', '1': 'ansi-bold' };
        let html = text.replace(/[&<>'"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m]);
        html = html.replace(/\u001b\[([0-9;]+)m/g, (match, codes) => {
            if (codes === '0') return '</span>';
            const classes = codes.split(';').map(c => colors[c]).filter(Boolean);
            return classes.length ? `<span class="${classes.join(' ')}">` : '';
        });
        const openSpans = (html.match(/<span/g) || []).length;
        const closeSpans = (html.match(/<\/span/g) || []).length;
        for (let i = 0; i < openSpans - closeSpans; i++) html += '</span>';
        return html;
    }

    function createMessageDiv(role) {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        return div;
    }

    function appendMessage(role, text) {
        const div = createMessageDiv(role);
        // Render Markdown for BOTH user and assistant to preserve lists/formatting
        div.innerHTML = marked.parse(text);
        chatHistory.appendChild(div);
        scrollToBottom();
    }

    function appendMessageWithImage(role, text, imageSrc) {
        const div = createMessageDiv(role);
        const img = document.createElement('img');
        img.src = imageSrc;
        img.className = 'chat-image';
        div.appendChild(img);
        if (text) {
            // Also markdown for image captions
            const textDiv = document.createElement('div');
            textDiv.innerHTML = marked.parse(text);
            div.appendChild(textDiv);
        }
        chatHistory.appendChild(div);
        scrollToBottom();
    }

    // SMART AUTO-SCROLL LOGIC
    let chatAutoScroll = true;
    let userScrolledUp = false;
    const SCROLL_THRESHOLD = 100; // pixels from bottom to trigger auto-scroll
    
    // Check if user is near bottom
    function isNearBottom() {
        // Reduced threshold to 10px for stricter auto-scroll
        const scrollBottom = chatHistory.scrollHeight - chatHistory.scrollTop - chatHistory.clientHeight;
        return scrollBottom <= 10;
    }
    
    // Smart scroll handler - detects user intent
    chatHistory.addEventListener('scroll', () => {
        const wasNearBottom = chatAutoScroll;
        const nearBottom = isNearBottom();
        
        // Update auto-scroll state
        chatAutoScroll = nearBottom;
        
        // Detect if user scrolled up (manually)
        if (!nearBottom && wasNearBottom) {
            userScrolledUp = true;
            showScrollIndicator();
        }
        
        // Detect if user scrolled back to bottom
        if (nearBottom && userScrolledUp) {
            userScrolledUp = false;
            hideScrollIndicator();
        }
    });
    
    // Mouse wheel handler - pause auto-scroll on wheel up
    chatHistory.addEventListener('wheel', (e) => {
        if (e.deltaY < 0) {
            // Only pause if actually moving away from bottom
            if (!isNearBottom()) {
                userScrolledUp = true;
                chatAutoScroll = false;
                showScrollIndicator();
            }
        } else if (e.deltaY > 0 && isNearBottom()) {
            userScrolledUp = false;
            chatAutoScroll = true;
            hideScrollIndicator();
        }
    }, { passive: true });
    
    // Scroll indicator element
    let scrollIndicator = null;
    function showScrollIndicator() {
        if (!scrollIndicator) {
            scrollIndicator = document.createElement('div');
            scrollIndicator.className = 'scroll-indicator';
            scrollIndicator.innerHTML = '↓ New messages';
            scrollIndicator.onclick = () => {
                chatAutoScroll = true;
                userScrolledUp = false;
                scrollToBottom(true);
                hideScrollIndicator();
            };
            chatHistory.parentElement.appendChild(scrollIndicator);
        }
        scrollIndicator.classList.add('visible');
    }
    
    function hideScrollIndicator() {
        if (scrollIndicator) {
            scrollIndicator.classList.remove('visible');
        }
    }
    
    // Enhanced scroll to bottom with force option
    function scrollToBottom(force = false) {
        if (chatAutoScroll || force) {
            // Set twice to ensure layout engine catches up
            chatHistory.scrollTop = chatHistory.scrollHeight;
            requestAnimationFrame(() => {
                chatHistory.scrollTop = chatHistory.scrollHeight;
            });
        }
    }

    function clearImageUpload() {
        currentImageData = null; currentImageMime = null;
        imageInput.value = ''; imagePreviewContainer.style.display = 'none';
        document.getElementById('upload-btn').classList.remove('has-image');
    }

    imageInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file || !file.type.startsWith('image/')) return;
        const reader = new FileReader();
        reader.onload = (event) => {
            currentImageData = event.target.result.split(',')[1];
            currentImageMime = file.type;
            imagePreview.src = event.target.result;
            imageName.textContent = file.name;
            imagePreviewContainer.style.display = 'flex';
            document.getElementById('upload-btn').classList.add('has-image');
        };
        reader.readAsDataURL(file);
    });

    removeImageBtn.addEventListener('click', clearImageUpload);
    clearBtn.addEventListener('click', () => { if(confirm('Clear history?')) { fetch('/api/chat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message: 'clear'}) }).then(() => { chatHistory.innerHTML = '<div class="message system">Cleared.</div>'; conversationHistory = []; updateContextPulse([]); }); } });
    if (stopBtn) stopBtn.addEventListener('click', () => fetch('/api/interrupt', { method: 'POST' }));

    // Backups/History Functions
    async function fetchBackups() {
        try {
            const res = await fetch('/api/backups');
            const data = await res.json();
            const backupsList = document.getElementById('backups-list');
            const backupCount = document.getElementById('backup-count');
            if (data.success && data.backups.length > 0) {
                backupsList.innerHTML = '';
                backupCount.textContent = `${data.backups.length} backups`;
                data.backups.forEach(b => {
                    const div = document.createElement('div');
                    div.className = 'backup-item';
                    div.innerHTML = `<div class="backup-filename">${b.name}</div><div class="backup-meta"><span>${b.size} • ${b.modified}</span><button class="btn-restore" data-backup="${b.name}">Restore</button></div>`;
                    backupsList.appendChild(div);
                });
                backupsList.querySelectorAll('.btn-restore').forEach(btn => btn.addEventListener('click', () => restoreBackup(btn.dataset.backup)));
            } else { backupsList.innerHTML = 'None'; backupCount.textContent = '0'; }
        } catch (e) {}
    }

    async function restoreBackup(name) {
        if (!confirm(`Restore ${name}?`)) return;
        const res = await fetch('/api/backups/restore', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({backup_name: name}) });
        const data = await res.json();
        if (data.success) alert('Restored');
    }

    async function fetchSessionHistory() {
        try {
            const res = await fetch('/api/memory');
            const data = await res.json();
            const sessionList = document.getElementById('session-list');
            if (data.success && data.sessions.length > 0) {
                sessionList.innerHTML = '';
                data.sessions.slice().reverse().forEach(s => {
                    const div = document.createElement('div');
                    div.className = 'session-item';
                    div.innerHTML = `<div class="session-date">${s.timestamp.slice(0,10)}</div><div class="session-summary">${s.summary || 'No summary'}</div>`;
                    sessionList.appendChild(div);
                });
            }
        } catch (e) {}
    }

    function updateBalanceDisplay(usd) {
        if (usd === undefined) return;
        
        // Update Header Balance
        const headerBal = document.getElementById('balance-usd');
        if (headerBal) headerBal.textContent = usd;
    }

    async function fetchBalance() {
        try {
            const res = await fetch('/api/balance');
            const data = await res.json();
            if (data.success && data.usd_balance) {
                updateBalanceDisplay(data.usd_balance);
            }
        } catch (e) {}
    }

}); // End DOMContentLoaded
