document.addEventListener('DOMContentLoaded', () => {
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const clearBtn = document.getElementById('clear-chat');
    const stopBtn = document.getElementById('stop-btn');
    const agentStatus = document.getElementById('agent-status');
    
    // Terminal elements
    const terminalLog = document.getElementById('terminal-log');
    const clearTerminalBtn = document.getElementById('clear-terminal');
    const modelSelect = document.getElementById('model-select');
    const splitter = document.getElementById('splitter');
    const previewSection = document.getElementById('preview-section');

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
    let pendingTerminal = [];
    let currentContentDiv = null;
    let updateInterval = null;

    let modelMap = {}; // Cache model info

    // Initial load
    fetchModels();
    fetchBackups();
    fetchSessionHistory();
    fetchWorkspace();
    fetchBalance();
    initSidebar();

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

    // --- Sidebar Initialization ---
    function initSidebar() {
        // Workspace Selector
        const workspaceBtn = document.getElementById('set-workspace');
        const workspaceInput = document.getElementById('workspace-path');
        const pathDisplay = document.getElementById('current-path-display');

        workspaceBtn?.addEventListener('click', async () => {
            const newPath = workspaceInput.value.trim();
            if (!newPath) return;
            const res = await fetch('/api/workspace', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: newPath})
            });
            const data = await res.json();
            if (data.success) {
                pathDisplay.textContent = data.path;
                workspaceInput.value = '';
                appendMessage('system', `Workspace updated to: ${data.path}`);
            } else {
                alert('Error: ' + data.error);
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
            btn.addEventListener('click', () => {
                userInput.value = btn.dataset.prompt;
                sendMessage();
            });
        });

        // Git Refresh
        document.getElementById('git-refresh')?.addEventListener('click', refreshGitStatus);

        // Lagoon-style Upload Button
        const uploadBtn = document.getElementById('upload-btn');
        const imageInput = document.getElementById('image-input');
        uploadBtn?.addEventListener('click', () => imageInput.click());

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

        // Splitter Logic (Horizontal)
        let isDragging = false;
        splitter.addEventListener('mousedown', (e) => {
            isDragging = true;
            document.body.style.cursor = 'row-resize';
            splitter.classList.add('dragging');
            e.preventDefault();
        });

        // Vertical Splitter Logic
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
            if (isDragging) {
                const containerHeight = document.querySelector('.main-content').offsetHeight;
                const newHeight = containerHeight - e.clientY;
                if (newHeight > 50 && newHeight < containerHeight * 0.8) {
                    previewSection.style.height = `${newHeight}px`;
                }
            }
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
            isDragging = false;
            isDraggingVertical = false;
            activeVerticalSplitter = null;
            document.body.style.cursor = 'default';
            splitter.classList.remove('dragging');
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
        try {
            const res = await fetch('/api/workspace');
            const data = await res.json();
            if (data.success) {
                document.getElementById('current-path-display').textContent = data.path;
            }
        } catch (e) {}
    }

    async function refreshGitStatus() {
        const gitLog = document.getElementById('git-status-log');
        if (!gitLog) return;
        gitLog.textContent = 'Loading...';
        try {
            const res = await fetch('/api/git/status');
            const data = await res.json();
            if (data.success) {
                gitLog.textContent = data.output || 'No git repository found';
            } else {
                gitLog.textContent = data.error || 'Error fetching git status';
            }
        } catch (e) {
            gitLog.textContent = 'Not a git repository or git not available';
        }
    }

    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text && !currentImageData) return;

        if (currentImageData) {
            appendMessageWithImage('user', text || 'Analyze this image', `data:${currentImageMime};base64,${currentImageData}`);
        } else {
            appendMessage('user', text);
        }
        
        const payload = {
            message: text || 'Describe this image in detail.',
            image: currentImageData,
            image_mime: currentImageMime,
            model: modelSelect.value
        };
        
        conversationHistory.push({ role: 'user', content: payload.message });
        userInput.value = '';
        clearImageUpload();
        userInput.disabled = true;
        sendBtn.disabled = false; // Keep enabled for STOP
        setButtonState(true);
        agentStatus.textContent = 'Processing...';

        let assistantMsgDiv = createMessageDiv('assistant');
        let contentDiv = document.createElement('div');
        contentDiv.className = 'content-block';
        assistantMsgDiv.appendChild(contentDiv);
        chatHistory.appendChild(assistantMsgDiv);
        scrollToBottom();

        startBuffering(contentDiv);

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
            setButtonState(false);
            agentStatus.textContent = 'Idle';
            userInput.focus();
        }
    }

    function handleSSEEvent(event, data) {
        switch (event) {
            case 'metadata':
                if (data.usd_balance !== undefined) updateBalanceDisplay(data.usd_balance);
                // Only update cost if it's non-zero/valid, to allow persistence
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
                const rLine = document.createElement('span');
                rLine.className = 'terminal-line';
                rLine.style.color = '#888';
                rLine.textContent = data;
                terminalLog.appendChild(rLine);
                scrollTerminalToBottom();
                break;
            case 'content':
                pendingContent += data;
                break;
            case 'terminal':
                pendingTerminal.push(data);
                break;
            case 'status':
                agentStatus.textContent = data;
                break;
            case 'error':
                appendMessage('system', 'Backend Error: ' + data);
                break;
            case 'done':
                if (currentContentDiv) {
                    conversationHistory.push({ role: 'assistant', content: currentContentDiv.dataset.raw });
                }
                updateContextPulse(conversationHistory);
                break;
        }
    }

    // --- UI Helpers ---

    function startBuffering(contentDiv) {
        currentContentDiv = contentDiv;
        pendingContent = '';
        pendingTerminal = [];
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
        let changed = false;
        if (pendingContent && currentContentDiv) {
            currentContentDiv.dataset.raw = (currentContentDiv.dataset.raw || '') + pendingContent;
            currentContentDiv.innerHTML = marked.parse(currentContentDiv.dataset.raw);
            pendingContent = '';
            changed = true;
        }
        if (pendingTerminal.length > 0) {
            const fragment = document.createDocumentFragment();
            pendingTerminal.forEach(data => {
                const span = document.createElement('span');
                span.className = 'terminal-line';
                span.innerHTML = ansiToHtml(data);
                fragment.appendChild(span);
            });
            terminalLog.appendChild(fragment);
            pendingTerminal = [];
            scrollTerminalToBottom();
        }
        if (changed) scrollToBottom();
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

    // Auto-scroll logic
    let chatAutoScroll = true, terminalAutoScroll = true;
    chatHistory.addEventListener('scroll', () => chatAutoScroll = (chatHistory.scrollHeight - chatHistory.scrollTop - chatHistory.clientHeight < 50));
    terminalLog.addEventListener('scroll', () => terminalAutoScroll = (terminalLog.scrollHeight - terminalLog.scrollTop - terminalLog.clientHeight < 30));
    function scrollToBottom() { if (chatAutoScroll) chatHistory.scrollTop = chatHistory.scrollHeight; }
    function scrollTerminalToBottom() { if (terminalAutoScroll) terminalLog.scrollTop = terminalLog.scrollHeight; }

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
    clearTerminalBtn.addEventListener('click', () => terminalLog.innerHTML = '');
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
        
        // Update Mini Balance (Input Area)
        const miniBal = document.getElementById('mini-balance');
        if (miniBal) {
            // Format nicely (e.g. $13.45)
            const val = parseFloat(usd);
            miniBal.textContent = '$' + (isNaN(val) ? '0.00' : val.toFixed(2));
        }
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
