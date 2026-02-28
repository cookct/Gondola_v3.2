// Global function to make an image the avatar
async function makeAvatar(imgSrc) {
    if (!confirm('Set this image as your avatar?')) return;

    try {
        // Fetch the image and convert to base64
        let imageB64;
        if (imgSrc.startsWith('data:')) {
            imageB64 = imgSrc.split(',')[1];
        } else {
            const response = await fetch(imgSrc);
            const blob = await response.blob();
            imageB64 = await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result.split(',')[1]);
                reader.readAsDataURL(blob);
            });
        }

        const res = await fetch('/api/make-avatar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageB64 })
        });

        const data = await res.json();
        if (data.success) {
            alert('Avatar saved!');
        } else {
            alert('Error: ' + data.error);
        }
    } catch (e) {
        alert('Failed to save avatar: ' + e.message);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Configure marked to make expression images clickable for lightbox
    const renderer = new marked.Renderer();
    const originalImage = renderer.image.bind(renderer);
    renderer.image = function(href, title, text) {
        if (href && (href.includes('/workspace-expressions/') || href.includes('/workspace-images/'))) {
            return `<div class="image-with-avatar-btn">
                <img src="${href}" alt="${text || ''}" class="expression-image" style="max-width: 400px; max-height: 400px; border-radius: 12px; cursor: pointer;" onclick="document.getElementById('lightbox-img').src='${href}'; document.getElementById('image-lightbox').classList.add('active'); document.body.style.overflow='hidden';">
                <button class="make-avatar-btn" onclick="makeAvatar('${href}')">Make Avatar</button>
            </div>`;
        }
        return originalImage(href, title, text);
    };
    marked.setOptions({ renderer });

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
    let currentDocContext = null;  // For PDF/TXT content
    let currentDocName = null;
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

    // Session stats state
    let sessionStartTime = null;
    let sessionTimerInterval = null;
    let sessionPriceIn = 0;  // $ per million tokens
    let sessionPriceOut = 0;
    let sessionTokensIn = 0;
    let sessionTokensOut = 0;
    let currentTurn = 0;
    let maxTurns = 50;

    // Lightbox state
    const lightbox = {
        el: null,
        img: null,
        isZoomed: false,
        isDragging: false,
        wasDragged: false,
        posX: 0,
        posY: 0,
        startX: 0,
        startY: 0,
        scale: 1,
        baseScale: 2.5,
        dragThreshold: 5,

        init() {
            this.el = document.getElementById('image-lightbox');
            this.img = document.getElementById('lightbox-img');
            if (!this.el || !this.img) return;

            // Close button
            this.el.querySelector('.lightbox-close')?.addEventListener('click', () => this.close());

            // Overlay click to close
            this.el.querySelector('.lightbox-overlay')?.addEventListener('click', () => {
                if (this.scale <= 1) this.close();
            });

            // Wheel zoom
            this.el.addEventListener('wheel', (e) => {
                if (!this.el.classList.contains('active')) return;
                e.preventDefault();
                const delta = e.deltaY > 0 ? 0.9 : 1.1;
                const newScale = Math.max(1, Math.min(5, this.scale * delta));
                if (newScale === this.scale) return;
                this.scale = newScale;
                if (this.scale > 1) {
                    this.img.classList.add('zoomed');
                } else {
                    this.img.classList.remove('zoomed');
                    this.posX = 0;
                    this.posY = 0;
                }
                this.img.style.transition = 'transform 0.1s ease-out';
                this.img.style.transform = `translate(${this.posX}px, ${this.posY}px) scale(${this.scale})`;
            }, { passive: false });

            // Image click to toggle zoom
            this.img.addEventListener('click', (e) => {
                if (this.wasDragged) { this.wasDragged = false; return; }
                e.stopPropagation();
                if (this.scale > 1) {
                    this.resetZoom();
                } else {
                    this.scale = this.baseScale;
                    this.img.classList.add('zoomed');
                    this.img.style.transition = 'transform 0.3s ease';
                    this.img.style.transform = `scale(${this.scale})`;
                }
            });

            // Drag
            this.el.addEventListener('mousedown', (e) => {
                if (this.scale <= 1) return;
                this.isDragging = true;
                this.wasDragged = false;
                this.startX = e.clientX - this.posX;
                this.startY = e.clientY - this.posY;
                this.img.classList.add('dragging');
                this.img.style.transition = 'none';
                e.preventDefault();
            });

            window.addEventListener('mousemove', (e) => {
                if (!this.isDragging || this.scale <= 1) return;
                this.posX = e.clientX - this.startX;
                this.posY = e.clientY - this.startY;
                this.img.style.transform = `translate(${this.posX}px, ${this.posY}px) scale(${this.scale})`;
                this.wasDragged = true;
            });

            window.addEventListener('mouseup', () => {
                if (this.isDragging) {
                    this.isDragging = false;
                    this.img.classList.remove('dragging');
                }
            });

            // Escape to close
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.el.classList.contains('active')) this.close();
            });
        },

        open(src) {
            if (!this.el) this.init();
            this.img.src = src;
            this.el.classList.add('active');
            document.body.style.overflow = 'hidden';
            this.resetZoom();
        },

        close() {
            this.el.classList.remove('active');
            document.body.style.overflow = '';
            this.resetZoom();
        },

        resetZoom() {
            this.scale = 1;
            this.posX = 0;
            this.posY = 0;
            this.img.classList.remove('zoomed', 'dragging');
            this.img.style.transition = 'none';
            this.img.style.transform = 'translate(0px, 0px) scale(1)';
        }
    };

    // Initialize lightbox
    lightbox.init();

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
    window.createToolBlock = createToolBlock;

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
        updateSessionPricing(model); // Update pricing for cost calculations
        await fetch('/api/models', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({model})
        });
    });

    // Update session pricing when model changes
    function updateSessionPricing(modelId) {
        if (modelMap[modelId]) {
            const m = modelMap[modelId];
            sessionPriceIn = m.price_in || 0;
            sessionPriceOut = m.price_out || 0;
            // Recalculate cost with new pricing
            updateSessionStats();
        }
    }

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
    window.setButtonState = setButtonState;

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
                if (tabId === 'add-model') {
                    refreshActiveModels();
                }
            });
        });

        // === ADD MODEL PANEL FUNCTIONALITY ===
        initAddModelPanel();

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
                if (text === 'Summarize') {
                    await handleSummarize();
                    return;
                }
                if (text === 'Compact') {
                    await handleCompact();
                    return;
                }
                if (text === 'Personality' || btn.id === 'personality-btn') {
                    // This is handled by a separate listener at the bottom
                    return;
                }
                
                const prompt = btn.dataset.prompt;
                if (!prompt) return;
                
                userInput.value = prompt;
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
                
                // Use explicit provider field from model config
                const provider = info.provider || 'venice'; // Default to Venice
                const providerSuffix = provider === 'together' ? ' (T)' : ' (V)';
                
                option.textContent = info.name + providerSuffix;
                option.dataset.provider = provider;
                if (id === data.current) option.selected = true;
                modelSelect.appendChild(option);
            });
            
            updateCapabilitiesDisplay(data.current);
            updateContextPulse(conversationHistory);
            updateSessionPricing(data.current); // Set initial pricing
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

    function addSystemMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system';
    messageDiv.innerHTML = `<div class="message-content">${text}</div>`;
    chatHistory.appendChild(messageDiv);
    scrollToBottom();
}

async function displayConversationHistory() {
    // Clear current display
    chatHistory.innerHTML = '';
    
    // Re-render all messages
    for (const message of conversationHistory) {
        if (message.role === 'user') {
            appendMessage('user', message.content);
        } else if (message.role === 'assistant') {
            appendMessage('assistant', message.content);
        } else if (message.role === 'system') {
            addSystemMessage(message.content);
        }
    }
    
    scrollToBottom();
}

async function handleSummarize() {
    if (!conversationHistory || conversationHistory.length === 0) {
        alert('No conversation to summarize');
        return;
    }

    if (!confirm('This will summarize the current session and keep only the last 10 user messages. Continue?')) {
        return;
    }

    try {
        // Show loading state
        const summarizeBtn = document.getElementById('summarize-btn');
        const originalText = summarizeBtn.innerHTML;
        summarizeBtn.innerHTML = '<span class="macro-icon">⏳</span><span class="macro-text">Summarizing...</span>';
        summarizeBtn.disabled = true;

        // Call the summarize API
        const res = await fetch('/api/summarize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                history: conversationHistory,
                keep_last_messages: 10
            })
        });

        const data = await res.json();
        
        if (data.success) {
            // Update conversation history with summary + last 10 messages
            conversationHistory = data.new_history;
            
            // Update the chat display
            await displayConversationHistory();
            
            // Update context pulse
            updateContextPulse(conversationHistory);
            
            // Show success message
            addSystemMessage('Session summarized. Context cleared, keeping last 10 messages and summary.');
        } else {
            alert('Error: ' + data.error);
        }
    } catch (e) {
        alert('Failed to summarize: ' + e.message);
    } finally {
        // Restore button state
        const summarizeBtn = document.getElementById('summarize-btn');
        summarizeBtn.innerHTML = '<span class="macro-icon">📋</span><span class="macro-text">Summarize</span>';
        summarizeBtn.disabled = false;
    }
}

async function handleCompact() {
    if (!conversationHistory || conversationHistory.length === 0) {
        alert('No conversation to compact');
        return;
    }

    try {
        const compactBtn = document.getElementById('compact-btn');
        compactBtn.innerHTML = '<span class="macro-icon">⏳</span><span class="macro-text">Compacting...</span>';
        compactBtn.disabled = true;

        const res = await fetch('/api/summarize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                history: conversationHistory,
                keep_last_messages: 2
            })
        });

        const data = await res.json();

        if (data.success) {
            conversationHistory = data.new_history;
            await displayConversationHistory();
            updateContextPulse(conversationHistory);
            addSystemMessage('Context compacted. Keeping last 2 messages + summary.');
        } else {
            alert('Error: ' + data.error);
        }
    } catch (e) {
        alert('Failed to compact: ' + e.message);
    } finally {
        const compactBtn = document.getElementById('compact-btn');
        compactBtn.innerHTML = '<span class="macro-icon">📦</span><span class="macro-text">Compact</span>';
        compactBtn.disabled = false;
    }
}

async function sendMessage() {
        const text = userInput.value.trim();
        if (!text && !currentImageData && !currentDocContext) return;

        // Build the message - prepend document context if present
        let fullMessage = text;
        if (currentDocContext) {
            const docHeader = `[ATTACHED FILE: ${currentDocName}]\n\`\`\`\n${currentDocContext}\n\`\`\`\n\n`;
            fullMessage = docHeader + (text || 'Please analyze this document.');
        }

        if (currentImageData) {
            appendMessageWithImage('user', text, `data:${currentImageMime};base64,${currentImageData}`);
        } else if (currentDocContext) {
            appendMessage('user', `📄 [${currentDocName}] ${text || '(analyze document)'}`);
        } else {
            appendMessage('user', text);
        }

        const payload = {
            message: fullMessage,
            image: currentImageData,
            image_mime: currentImageMime,
            model: modelSelect.value,
            planning_mode: planningBtn ? planningBtn.classList.contains('active') : false
        };
        
        // Match server's message format - multimodal when image present
        if (currentImageData) {
            conversationHistory.push({
                role: 'user',
                content: [
                    { type: 'text', text: payload.message || '' },
                    { type: 'image_url', image_url: { url: `data:${currentImageMime};base64,${currentImageData}` } }
                ]
            });
        } else {
            conversationHistory.push({ role: 'user', content: payload.message });
        }
        userInput.value = '';
        userInput.style.height = '44px';
        userInput.style.overflowY = 'hidden';
        clearImageUpload();
        userInput.disabled = true;
        userInput.parentElement.classList.add('thinking');
        sendBtn.disabled = false; // Keep enabled for STOP
        window.setButtonState(true);
        agentStatus && (agentStatus.textContent = 'Processing...');
        
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
                        } catch (e) {
                            console.error('SSE event error:', event, e);
                        }
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
            window.setButtonState(false);
            agentStatus && (agentStatus.textContent = 'Idle');
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
        console.log('SSE event received:', event, typeof data === 'object' ? JSON.stringify(data).slice(0,100) : data);
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
                let toolMatch = data.match(/Executing (.*)\.\.\./) || data.match(/\(using (.*)\)/);
                if (toolMatch) {
                    const toolName = toolMatch[1];
                    finalizeCurrentBlock();  // Close any previous block before tool
                    currentToolBlock = window.createToolBlock(currentTurnContainer, toolName);
                    currentBlockType = 'tool';
                }
                agentStatus && (agentStatus.textContent = data);
                // Flash status in the main text box
                if (userInput) {
                    userInput.placeholder = ">> " + data;
                }
                break;

            case 'tool_done':
                console.log('tool_done event:', data);
                console.log('currentToolBlock:', currentToolBlock);
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
                    } else if (!autoExpandTools && !data.url) {
                        currentToolBlock.classList.remove('expanded');
                    }
                    currentToolBlock = null;
                }
                // Display expression image in chat if URL present
                if (data.url && currentTurnContainer) {
                    const imgDiv = document.createElement('div');
                    imgDiv.className = 'expression-image-container image-with-avatar-btn';
                    imgDiv.innerHTML = `<img src="${data.url}" class="expression-image" style="max-width: 350px; max-height: 350px; border-radius: 12px; cursor: pointer; margin: 10px 0;" onclick="document.getElementById('lightbox-img').src='${data.url}'; document.getElementById('image-lightbox').classList.add('active'); document.body.style.overflow='hidden';">
                        <button class="make-avatar-btn" onclick="makeAvatar('${data.url}')">Make Avatar</button>`;
                    currentTurnContainer.appendChild(imgDiv);
                    chatHistory.scrollTop = chatHistory.scrollHeight;
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

            case 'session_info':
                // Initialize session with pricing info
                sessionPriceIn = data.price_in || 0;
                sessionPriceOut = data.price_out || 0;
                maxTurns = data.max_turns || 50;
                document.getElementById('turn-counter').textContent = `0 / ${maxTurns}`;
                // Start session timer if not already running
                if (!sessionStartTime) {
                    sessionStartTime = Date.now();
                    startSessionTimer();
                }
                break;

            case 'turn_start':
                currentTurn = data.turn || 0;
                document.getElementById('turn-counter').textContent = `${currentTurn} / ${data.max_turns || maxTurns}`;
                break;

            case 'turn_complete':
                currentTurn = data.turn || 0;
                sessionTokensIn = data.session_tokens_in || 0;
                sessionTokensOut = data.session_tokens_out || 0;
                updateSessionStats();
                break;
        }
    }

    // Session timer functions
    function startSessionTimer() {
        if (sessionTimerInterval) clearInterval(sessionTimerInterval);
        sessionTimerInterval = setInterval(updateSessionTimer, 1000);
        updateSessionTimer();
    }

    function updateSessionTimer() {
        if (!sessionStartTime) return;
        const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        document.getElementById('session-timer').textContent =
            `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    function updateSessionStats() {
        // Update token displays (with null checks)
        const tokensInEl = document.getElementById('tokens-in');
        const tokensOutEl = document.getElementById('tokens-out');
        const turnCounterEl = document.getElementById('turn-counter');
        const sessionCostEl = document.getElementById('session-cost');

        if (tokensInEl) tokensInEl.textContent = sessionTokensIn.toLocaleString();
        if (tokensOutEl) tokensOutEl.textContent = sessionTokensOut.toLocaleString();
        if (turnCounterEl) turnCounterEl.textContent = `${currentTurn} / ${maxTurns}`;

        // Calculate cost (prices are per million tokens)
        const costIn = (sessionTokensIn / 1000000) * sessionPriceIn;
        const costOut = (sessionTokensOut / 1000000) * sessionPriceOut;
        const totalCost = costIn + costOut;
        if (sessionCostEl) sessionCostEl.textContent = `$${totalCost.toFixed(4)}`;
    }

    function resetSessionStats() {
        sessionStartTime = null;
        sessionTokensIn = 0;
        sessionTokensOut = 0;
        currentTurn = 0;
        if (sessionTimerInterval) {
            clearInterval(sessionTimerInterval);
            sessionTimerInterval = null;
        }
        document.getElementById('session-timer').textContent = '00:00';
        document.getElementById('turn-counter').textContent = '0 / --';
        document.getElementById('tokens-in').textContent = '0';
        document.getElementById('tokens-out').textContent = '0';
        document.getElementById('session-cost').textContent = '$0.00';
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
        let maxTokens = 200000; // Default fallback
        
        if (modelMap[currentModelId] && modelMap[currentModelId].context_limit) {
            maxTokens = modelMap[currentModelId].context_limit;
        } else if (currentModelId) {
            // Try to get from the selected option's data or use a reasonable default
            const selectedOption = modelSelect.options[modelSelect.selectedIndex];
            if (selectedOption && selectedOption.dataset && selectedOption.dataset.contextLimit) {
                maxTokens = parseInt(selectedOption.dataset.contextLimit);
            }
        }
        
        const percent = Math.min(100, (tokens / maxTokens) * 100);
        const fill = document.getElementById('pulse-fill');
        const count = document.getElementById('pulse-count');
        
        // Update label with max tokens
        const pulseCount = document.getElementById('pulse-count');
        const pulseMax = document.getElementById('pulse-max');
        if (pulseCount && pulseMax) {
            pulseCount.textContent = tokens.toLocaleString();
            pulseMax.textContent = maxTokens.toLocaleString();
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

        // Container for image + button
        const imgContainer = document.createElement('div');
        imgContainer.className = 'image-with-avatar-btn';

        const img = document.createElement('img');
        img.src = imageSrc;
        img.className = 'chat-image';
        img.style.cursor = 'pointer';
        img.onclick = () => {
            document.getElementById('lightbox-img').src = imageSrc;
            document.getElementById('image-lightbox').classList.add('active');
            document.body.style.overflow = 'hidden';
        };
        imgContainer.appendChild(img);

        // Make Avatar button
        const avatarBtn = document.createElement('button');
        avatarBtn.className = 'make-avatar-btn';
        avatarBtn.textContent = 'Make Avatar';
        avatarBtn.onclick = () => makeAvatar(imageSrc);
        imgContainer.appendChild(avatarBtn);

        div.appendChild(imgContainer);

        if (text) {
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
        currentDocContext = null; currentDocName = null;
        imageInput.value = ''; imagePreviewContainer.style.display = 'none';
        imagePreview.style.display = 'block';
        document.getElementById('upload-btn').classList.remove('has-image');
    }

    imageInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const ext = file.name.split('.').pop().toLowerCase();

        // Handle PDF and TXT files - parse server-side
        if (ext === 'pdf' || ext === 'txt') {
            try {
                const formData = new FormData();
                formData.append('file', file);

                imageName.textContent = `Parsing ${file.name}...`;
                imagePreviewContainer.style.display = 'flex';
                imagePreview.src = '';
                imagePreview.style.display = 'none';

                const response = await fetch('/api/parse_file', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Failed to parse file');
                }

                const result = await response.json();
                currentDocContext = result.content;
                currentDocName = file.name;
                currentImageData = null;
                currentImageMime = null;

                imageName.textContent = `📄 ${file.name} (${result.content.length.toLocaleString()} chars)`;
                document.getElementById('upload-btn').classList.add('has-image');
                console.log(`[PDF/TXT] Loaded ${file.name}: ${result.content.length} chars`);

            } catch (err) {
                alert(`Error parsing file: ${err.message}`);
                clearImageUpload();
            }
            return;
        }

        // Handle images - existing flow
        if (!file.type.startsWith('image/')) {
            alert('Unsupported file type. Use images, PDF, or TXT.');
            return;
        }

        const reader = new FileReader();
        reader.onload = (event) => {
            currentImageData = event.target.result.split(',')[1];
            currentImageMime = file.type;
            currentDocContext = null;
            currentDocName = null;
            imagePreview.src = event.target.result;
            imagePreview.style.display = 'block';
            imageName.textContent = file.name;
            imagePreviewContainer.style.display = 'flex';
            document.getElementById('upload-btn').classList.add('has-image');
        };
        reader.readAsDataURL(file);
    });

    removeImageBtn.addEventListener('click', clearImageUpload);
    clearBtn.addEventListener('click', () => { if(confirm('Clear history?')) { fetch('/api/chat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message: 'clear'}) }).then(() => { chatHistory.innerHTML = '<div class="message system">Cleared.</div>'; conversationHistory = []; updateContextPulse([]); resetSessionStats(); }); } });
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

    // === ADD MODEL PANEL ===
    let providerModelsCache = [];
    let selectedProviderModel = null;

    function initAddModelPanel() {
        const providerSelect = document.getElementById('provider-select');
        const refreshBtn = document.getElementById('refresh-provider-models');
        const modelFilter = document.getElementById('model-filter');
        const addModelBtn = document.getElementById('add-model-btn');

        // Refresh provider models on button click
        refreshBtn?.addEventListener('click', () => {
            const provider = providerSelect?.value || 'together';
            fetchProviderModels(provider);
        });

        // Filter models as user types
        modelFilter?.addEventListener('input', () => {
            renderProviderModels(providerModelsCache, modelFilter.value);
        });

        // Provider change
        providerSelect?.addEventListener('change', () => {
            // Clear the list and show loading
            const listEl = document.getElementById('provider-models-list');
            if (listEl) {
                listEl.innerHTML = '<div class="loading-indicator">Click refresh to load models...</div>';
            }
            selectedProviderModel = null;
            hideModelDetails();
        });

        // Add model button
        addModelBtn?.addEventListener('click', () => {
            if (selectedProviderModel) {
                addSelectedModel(selectedProviderModel);
            }
        });

        // Initial load of active models
        refreshActiveModels();
    }

    async function fetchProviderModels(provider) {
        const listEl = document.getElementById('provider-models-list');
        const filterInput = document.getElementById('model-filter');

        if (listEl) {
            listEl.innerHTML = '<div class="loading-indicator">Loading models from ' + provider + '...</div>';
        }

        try {
            const res = await fetch(`/api/provider-models?provider=${provider}`);
            const data = await res.json();

            if (data.success) {
                providerModelsCache = data.models;
                renderProviderModels(data.models, filterInput?.value || '');
                showStatus(`Loaded ${data.count} models from ${provider}`, 'success');
            } else {
                listEl.innerHTML = `<div class="loading-indicator" style="color: var(--ansi-red);">Error: ${data.error}</div>`;
                showStatus(data.error, 'error');
            }
        } catch (e) {
            listEl.innerHTML = `<div class="loading-indicator" style="color: var(--ansi-red);">Failed to fetch models</div>`;
            showStatus('Failed to fetch models: ' + e.message, 'error');
        }
    }

    function renderProviderModels(models, filterText = '') {
        const listEl = document.getElementById('provider-models-list');
        if (!listEl) return;

        const filter = filterText.toLowerCase();
        const filtered = models.filter(m =>
            m.name.toLowerCase().includes(filter) ||
            m.id.toLowerCase().includes(filter) ||
            (m.organization || '').toLowerCase().includes(filter)
        );

        if (filtered.length === 0) {
            listEl.innerHTML = '<div class="loading-indicator">No models match your filter</div>';
            return;
        }

        listEl.innerHTML = '';

        filtered.forEach(model => {
            const div = document.createElement('div');
            div.className = 'provider-model-item';

            // Check if already added
            if (modelMap[model.id]) {
                div.classList.add('already-added');
            }

            // Mark selected
            if (selectedProviderModel && selectedProviderModel.id === model.id) {
                div.classList.add('selected');
            }

            const contextK = Math.round(model.context_length / 1000);
            
            // Check if model is free (0.0 price) or paid
            let priceStr;
            if (model.price_in === 0 && model.price_out === 0) {
                priceStr = 'Free';
            } else {
                priceStr = `$${model.price_in.toFixed(2)}/$${model.price_out.toFixed(2)}`;
            }

            div.innerHTML = `
                <div class="provider-model-name">${escapeHtml(model.name)}</div>
                <div class="provider-model-meta">
                    <span>📐 ${contextK}K</span>
                    <span>💰 ${priceStr}</span>
                    <span>🏢 ${model.organization || 'Unknown'}</span>
                </div>
            `;

            div.addEventListener('click', () => {
                if (modelMap[model.id]) {
                    showStatus('Model already added', 'error');
                    return;
                }
                selectProviderModel(model);
            });

            listEl.appendChild(div);
        });
    }

    function selectProviderModel(model) {
        selectedProviderModel = model;

        // Update selection visual
        document.querySelectorAll('.provider-model-item').forEach(el => {
            el.classList.remove('selected');
        });
        event.currentTarget?.classList.add('selected');

        // Show details
        showModelDetails(model);
    }

    function showModelDetails(model) {
        const section = document.getElementById('model-details-section');
        const detailsEl = document.getElementById('model-details');

        if (!section || !detailsEl) return;

        section.style.display = 'block';

        const provider = document.getElementById('provider-select')?.value || 'together';
        const contextK = Math.round(model.context_length / 1000);

        detailsEl.innerHTML = `
            <div class="model-detail-row">
                <span class="model-detail-label">ID:</span>
                <span class="model-detail-value">${escapeHtml(model.id)}</span>
            </div>
            <div class="model-detail-row">
                <span class="model-detail-label">Name:</span>
                <span class="model-detail-value">${escapeHtml(model.name)}</span>
            </div>
            <div class="model-detail-row">
                <span class="model-detail-label">Provider:</span>
                <span class="model-detail-value">${provider.toUpperCase()}</span>
            </div>
            <div class="model-detail-row">
                <span class="model-detail-label">Type:</span>
                <span class="model-detail-value">${model.type || 'chat'}</span>
            </div>
            <div class="model-detail-row">
                <span class="model-detail-label">Context:</span>
                <span class="model-detail-value">${contextK}K tokens</span>
            </div>
            <div class="model-detail-row">
                <span class="model-detail-label">Price (in/out):</span>
                <span class="model-detail-value">$${(model.price_in || 0).toFixed(2)} / $${(model.price_out || 0).toFixed(2)}</span>
            </div>
        `;
    }

    function hideModelDetails() {
        const section = document.getElementById('model-details-section');
        if (section) section.style.display = 'none';
    }

    async function addSelectedModel(model) {
        const provider = document.getElementById('provider-select')?.value || 'together';
        const addBtn = document.getElementById('add-model-btn');

        if (addBtn) {
            addBtn.disabled = true;
            addBtn.textContent = 'Adding...';
        }

        try {
            const res = await fetch('/api/models/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_id: model.id,
                    name: model.name,
                    provider: provider,
                    type: model.type || 'chat',
                    context_length: model.context_length,
                    price_in: model.price_in || 0,
                    price_out: model.price_out || 0,
                    description: `${model.type || 'Chat'} model from ${provider}`,
                    strength: model.organization || 'Custom'
                })
            });

            const data = await res.json();

            if (data.success) {
                // Build status message with auto-configured info
                let statusMsg = `Added ${model.name}`;
                if (data.auto_configured) {
                    const ac = data.auto_configured;
                    const fcStatus = ac.native_function_calling ? '✓ Tools' : '✗ Tools';
                    // Shorten the inference source for display
                    let source = '';
                    if (ac.inferred_from.includes('verified')) {
                        source = 'verified';
                    } else if (ac.inferred_from.includes('Venice')) {
                        source = 'OpenAI-compat';
                    } else {
                        source = 'inferred';
                    }
                    statusMsg += ` | ${fcStatus} (${source}) | ${ac.max_agent_turns} turns`;
                }
                showStatus(statusMsg, 'success');

                // Update local model map
                modelMap[model.id] = data.model;

                // Refresh the model dropdown in header
                fetchModels();

                // Refresh active models list
                refreshActiveModels();

                // Re-render provider models to show checkmark
                const filterInput = document.getElementById('model-filter');
                renderProviderModels(providerModelsCache, filterInput?.value || '');

                // Clear selection
                selectedProviderModel = null;
                hideModelDetails();
            } else {
                showStatus(data.error, 'error');
            }
        } catch (e) {
            showStatus('Failed to add model: ' + e.message, 'error');
        } finally {
            if (addBtn) {
                addBtn.disabled = false;
                addBtn.textContent = '➕ Add to My Models';
            }
        }
    }

    function refreshActiveModels() {
        const listEl = document.getElementById('active-models-list');
        if (!listEl) return;

        listEl.innerHTML = '';

        Object.entries(modelMap).forEach(([id, model]) => {
            const div = document.createElement('div');
            div.className = 'active-model-item';

            const provider = model.provider || 'venice';
            const providerClass = provider === 'together' ? 'together' : 'venice';

            div.innerHTML = `
                <span class="active-model-name" title="${id}">${escapeHtml(model.name)}</span>
                <span class="active-model-provider ${providerClass}">${provider.charAt(0).toUpperCase()}</span>
                <button class="remove-model-btn" data-model-id="${escapeHtml(id)}" title="Remove">✕</button>
            `;

            // Remove button handler
            div.querySelector('.remove-model-btn')?.addEventListener('click', async (e) => {
                e.stopPropagation();
                const modelId = e.target.dataset.modelId;
                if (confirm(`Remove ${model.name} from your models?`)) {
                    await removeModel(modelId);
                }
            });

            listEl.appendChild(div);
        });

        if (Object.keys(modelMap).length === 0) {
            listEl.innerHTML = '<div class="loading-indicator">No models configured</div>';
        }
    }

    async function removeModel(modelId) {
        try {
            const res = await fetch('/api/models/remove', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId })
            });

            const data = await res.json();

            if (data.success) {
                delete modelMap[modelId];
                fetchModels();
                refreshActiveModels();

                // Re-render provider models to remove checkmark
                const filterInput = document.getElementById('model-filter');
                renderProviderModels(providerModelsCache, filterInput?.value || '');

                showStatus('Model removed', 'success');
            } else {
                showStatus(data.error, 'error');
            }
        } catch (e) {
            showStatus('Failed to remove model: ' + e.message, 'error');
        }
    }

    function showStatus(message, type = 'success') {
        const statusEl = document.getElementById('add-model-status');
        if (!statusEl) return;

        statusEl.textContent = message;
        statusEl.className = 'add-model-status ' + type;
        statusEl.style.display = 'block';

        setTimeout(() => {
            statusEl.style.display = 'none';
        }, 3000);
    }

    // ============================================
    // PERSONALITY MODAL
    // ============================================

    const personalityModal = document.getElementById('personality-modal');
    const personalityText = document.getElementById('personality-text');
    const personalityBtn = document.getElementById('personality-btn');
    const personalityCloseBtn = document.getElementById('personality-modal-close');
    const personalityCancelBtn = document.getElementById('personality-modal-cancel');
    const personalitySaveBtn = document.getElementById('personality-modal-save');

    // Load personality from localStorage on init
    let currentPersonality = localStorage.getItem('personality') || '';

    function openPersonalityModal() {
        personalityText.value = currentPersonality;
        personalityModal.style.display = 'flex';
        personalityText.focus();
    }

    function closePersonalityModal() {
        personalityModal.style.display = 'none';
    }

    async function savePersonality() {
        const text = personalityText.value.trim();
        currentPersonality = text;
        localStorage.setItem('personality', text);

        // Also save to server for persistence across server restarts
        try {
            const res = await fetch('/api/personality', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({personality: text})
            });
            const data = await res.json();
            if (data.success) {
                showStatus('Personality saved', 'success');
            } else {
                showStatus('Saved locally only', 'error');
            }
        } catch (e) {
            showStatus('Saved locally only', 'error');
        }

        closePersonalityModal();
    }

    // Modal event listeners
    if (personalityBtn) {
        personalityBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            openPersonalityModal();
        });
    }
    if (personalityCloseBtn) {
        personalityCloseBtn.addEventListener('click', closePersonalityModal);
    }
    if (personalityCancelBtn) {
        personalityCancelBtn.addEventListener('click', closePersonalityModal);
    }
    if (personalitySaveBtn) {
        personalitySaveBtn.addEventListener('click', savePersonality);
    }

    // Close modal on backdrop click
    if (personalityModal) {
        personalityModal.addEventListener('click', (e) => {
            if (e.target === personalityModal) {
                closePersonalityModal();
            }
        });
    }

    // Close modal on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && personalityModal.style.display === 'flex') {
            closePersonalityModal();
        }
    });

    // Load personality from server on init (server is source of truth)
    async function loadPersonalityFromServer() {
        try {
            const res = await fetch('/api/personality');
            const data = await res.json();
            if (data.success && data.personality !== undefined) {
                currentPersonality = data.personality;
                localStorage.setItem('personality', data.personality);
            }
        } catch (e) {
            // Use localStorage value if server fails
            console.log('Failed to load personality from server:', e);
        }
    }
    loadPersonalityFromServer();

    // Edit Model & Style Settings
    const editModelToggle = document.getElementById('edit-model-toggle');
    const stylePresetInput = document.getElementById('style-preset-input');

    async function loadEditModelSetting() {
        try {
            const res = await fetch('/api/edit-model');
            const data = await res.json();
            if (data.success) {
                if (editModelToggle) editModelToggle.checked = data.model === 'seedream-v4-edit';
                if (stylePresetInput) stylePresetInput.value = data.style_preset || 'Pixel Art';
            }
        } catch (e) {
            console.log('Failed to load edit model setting:', e);
        }
    }

    async function saveSettings() {
        try {
            const model = editModelToggle.checked ? 'seedream-v4-edit' : 'qwen-edit';
            const style = stylePresetInput.value.trim();
            await fetch('/api/edit-model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model, style_preset: style })
            });
        } catch (e) {
            console.log('Failed to save settings:', e);
        }
    }

    if (editModelToggle) editModelToggle.addEventListener('change', saveSettings);
    if (stylePresetInput) stylePresetInput.addEventListener('change', saveSettings);

    loadEditModelSetting();

    // === Avatar Expression System ===

    const AVATAR_TOOL_MAPPING = {
        'read_file': 'read_file',
        'search_file_content': 'search_file_content', 
        'edit_file': 'edit_file',
        'write_file': 'write_file',
        'run_command': 'run_command',
        'done': 'done',
        'thinking': 'thinking',
        'search_docs': 'search_docs',
        'web_search': 'web_search',
        'save_knowledge': 'write_file'
    };

    let currentAvatarState = 'initial';
    let avatarCycleTimer = null;
    let toolStartTime = null;
    let currentToolImages = [];
    let currentImageIndex = 0;
    let cyclingThresholdTimer = null;

    const BLANK_IMAGE = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";

    function getAvatarElement() {
        return document.getElementById('avatar-image');
    }

    function getAvatarStatusElement() {
        return document.getElementById('avatar-status');
    }

    function updateAvatarStatus(text) {
        const statusEl = getAvatarStatusElement();
        if (statusEl) {
            statusEl.textContent = text;
        }
    }

    function stopAvatarCycle() {
        if (avatarCycleTimer) {
            clearTimeout(avatarCycleTimer);
            avatarCycleTimer = null;
        }
        if (cyclingThresholdTimer) {
            clearTimeout(cyclingThresholdTimer);
            cyclingThresholdTimer = null;
        }
    }

    function getRandomInterval() {
        return 2000; // Fixed 2 second interval
    }

    function cycleAvatarImage() {
        if (currentToolImages.length === 0) return;
        
        currentImageIndex = (currentImageIndex + 1) % currentToolImages.length;
        const avatarEl = getAvatarElement();
        if (avatarEl) {
            const newSrc = currentToolImages[currentImageIndex];
            const cacheBustedSrc = newSrc + (newSrc.includes('?') ? '&' : '?') + 't=' + Date.now();
            
            // Fade out
            avatarEl.style.opacity = '0';
            
            // Wait for fade-out, then change image and fade in when loaded
            setTimeout(() => {
                avatarEl.onload = () => {
                    avatarEl.onload = null;
                    avatarEl.style.opacity = '1';
                };
                avatarEl.src = cacheBustedSrc;
            }, 250);
            
            // Set next interval randomly (add 300ms for fade time)
            avatarCycleTimer = setTimeout(cycleAvatarImage, getRandomInterval() + 300);
        }
    }

    function startAvatarCycle() {
        stopAvatarCycle();
        if (currentToolImages.length > 1) {
            // Start cycling after 5 seconds
            cyclingThresholdTimer = setTimeout(() => {
                avatarCycleTimer = setTimeout(cycleAvatarImage, getRandomInterval());
            }, 5000);
        }
    }

    async function loadToolImages(toolName) {
        console.log('[AVATAR DEBUG] loadToolImages called for:', toolName);
        try {
            const response = await fetch(`/api/avatar-images/${toolName}`);
            const data = await response.json();
            console.log('[AVATAR DEBUG] API response:', data);
            if (data.success && data.images && data.images.length > 0) {
                currentToolImages = data.images;
                currentImageIndex = 0;
                console.log('[AVATAR DEBUG] Loaded', data.images.length, 'images');
                return true;
            }
        } catch (e) {
            console.log('[AVATAR DEBUG] Failed to load avatar images:', e);
        }
        currentToolImages = [];
        return false;
    }

    async function setAvatarState(toolName, statusText) {
        console.log('[AVATAR DEBUG] setAvatarState called:', toolName, statusText);
        const avatarEl = getAvatarElement();
        if (!avatarEl) {
            console.log('[AVATAR DEBUG] No avatar element found!');
            return;
        }
        
        stopAvatarCycle();
        currentAvatarState = toolName;
        updateAvatarStatus(statusText);
        
        // Load images for this tool state
        let hasImages = await loadToolImages(toolName);
        
        // Generic Fallback: If requested folder is empty, use 'initial' state
        if (!hasImages) {
            console.log('[AVATAR] No images for', toolName, '- falling back to initial');
            hasImages = await loadToolImages('initial');
            // If even initial fails, we have a bigger problem (handled by hasImages check below)
        }
        
        if (hasImages && currentToolImages.length > 0) {
            // Pick a random image from the folder
            currentImageIndex = Math.floor(Math.random() * currentToolImages.length);
            const newSrc = currentToolImages[currentImageIndex];
            const cacheBustedSrc = newSrc + (newSrc.includes('?') ? '&' : '?') + 't=' + Date.now();
            
            // Fade out
            avatarEl.style.opacity = '0';
            
            // Wait for fade-out, then change image and fade in when loaded
            setTimeout(() => {
                avatarEl.onload = () => {
                    avatarEl.onload = null;
                    avatarEl.style.opacity = '1';
                };
                avatarEl.src = cacheBustedSrc;
            }, 250);
            console.log('[AVATAR DEBUG] Setting avatar src to:', cacheBustedSrc);

            // Start cycling if we have multiple images and operation is long
            if (currentToolImages.length > 1) {
                startAvatarCycle();
            }
        } else {
            console.log('[AVATAR DEBUG] No images, setting blank');
            avatarEl.style.opacity = '0';
            setTimeout(() => {
                avatarEl.onload = () => {
                    avatarEl.onload = null;
                    avatarEl.style.opacity = '1';
                };
                avatarEl.src = BLANK_IMAGE;
            }, 250);
        }
    }

    function handleToolStart(toolName) {
        toolStartTime = Date.now();
        // Dynamic fallback: Use mapping if exists, otherwise try tool name directly
        const mappedTool = AVATAR_TOOL_MAPPING[toolName] || toolName;
        const statusText = toolName.replace(/_/g, ' ').toUpperCase();
        setAvatarState(mappedTool, statusText);
    }

    function handleToolEnd() {
        // Show completion state with specific sequence
        showDoneSequence();
    }

    async function showDoneSequence() {
        console.log('[AVATAR DEBUG] Starting done sequence');
        
        // Load done images first
        const hasDoneImages = await loadToolImages('done');
        if (!hasDoneImages || currentToolImages.length === 0) {
            // Fallback to simple done state if no images
            setAvatarState('done', 'COMPLETED');
            setTimeout(() => {
                setAvatarState('initial', 'Ready');
            }, 2000);
            return;
        }

        // Custom sequence: 1.png, 2.png, 3.png, 2.png, 4.png
        const sequence = ['1.png', '2.png', '3.png', '2.png', '4.png'];
        const timings = [1000, 1000, 1000, 1000, 1000]; // Total: 5 seconds
        
        for (let i = 0; i < sequence.length; i++) {
            const targetImage = sequence[i];
            const timing = timings[i];
            
            // Find the image in currentToolImages
            const imageIndex = currentToolImages.findIndex(img => img.includes(targetImage));
            
            if (imageIndex !== -1) {
                currentImageIndex = imageIndex;
                const newSrc = currentToolImages[currentImageIndex];
                const cacheBustedSrc = newSrc + (newSrc.includes('?') ? '&' : '?') + 't=' + Date.now();
                
                const avatarEl = getAvatarElement();
                if (avatarEl) {
                    avatarEl.src = cacheBustedSrc;
                    console.log(`[AVATAR DEBUG] Done sequence ${i+1}/6: ${targetImage} (${timing}ms)`);
                }
            } else {
                console.log(`[AVATAR DEBUG] Image ${targetImage} not found in done folder`);
            }
            
            // Wait for the specified timing
            await new Promise(resolve => setTimeout(resolve, timing));
        }
        
        console.log('[AVATAR DEBUG] Done sequence complete');
        
        // Return to initial state
        setAvatarState('initial', 'Ready');
    }

    // MONKEY PATCHING (Surgical) - Use local references to avoid infinite recursion
    const localCreateToolBlock = createToolBlock;
    window.createToolBlock = function(parent, toolName) {
        const block = localCreateToolBlock.call(this, parent, toolName);
        handleToolStart(toolName);
        return block;
    };

    const localSetButtonState = setButtonState;
    window.setButtonState = function(state) {
        console.log('[AVATAR DEBUG] setButtonState called with:', state);
        localSetButtonState.call(this, state);
        if (state === true) {
            console.log('[AVATAR DEBUG] Setting THINKING state');
            setAvatarState('thinking', 'THINKING...');
        } else if (state === false || state === 'ready') {
            console.log('[AVATAR DEBUG] Calling handleToolEnd');
            handleToolEnd();
        }
    };

    // Initialize
    setAvatarState('initial', 'Ready');

}); // End DOMContentLoaded
