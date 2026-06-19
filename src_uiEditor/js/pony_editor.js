// src_uiEditor/js/pony_editor.js - ИСПРАВЛЕННАЯ ВЕРСИЯ С ТРЕЙСОМ

const PonyEditor = {
    container: null,
    currentPonyName: null,
    currentPonyConfig: null,

    init() {
        this.container = document.getElementById('editor-panel');
        console.log('[PonyEditor] Initialized, container:', this.container);

        this.addGlobalCreateButton();
        this.addTraceButton();

        if (window.EditorAPI && EditorAPI.on) {
            EditorAPI.on('pony:reloaded', (data) => this.onPonyReloaded(data));
            EditorAPI.on('gif:created', (data) => this.onGifCreated(data));
        }
    },

    onPonyReloaded(ponyConfig) {
        console.log('[PonyEditor] Pony reloaded:', ponyConfig);
        if (ponyConfig && ponyConfig.name === this.currentPonyName) {
            this.currentPonyConfig = ponyConfig;
            this.render(ponyConfig);
            showStatus(`✅ Pony "${ponyConfig.display_name || ponyConfig.name}" reloaded`);
        }
    },

    onGifCreated(data) {
        console.log('[PonyEditor] GIF created:', data);
        if (data && data.pony_name === this.currentPonyName) {
            showStatus(`✅ Sprite "${data.sprite_name}" created successfully! Refreshing...`);
            setTimeout(() => {
                EditorAPI.send('pony:reload:' + this.currentPonyName);
            }, 300);
        }
    },

    addGlobalCreateButton() {
        const checkToolbar = setInterval(() => {
            const toolbar = document.querySelector('.editor-toolbar');
            if (toolbar && !document.getElementById('global-create-pony-btn')) {
                clearInterval(checkToolbar);
                const createBtn = document.createElement('button');
                createBtn.id = 'global-create-pony-btn';
                createBtn.className = 'btn-primary';
                createBtn.style.marginLeft = 'auto';
                createBtn.innerHTML = '➕ Create New Pony';
                createBtn.addEventListener('click', () => this.showCreatePonyModal());
                toolbar.appendChild(createBtn);
            }
        }, 100);
    },

    showCreatePonyModal() {
        const existing = document.getElementById('create-pony-modal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.id = 'create-pony-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.95);
            z-index: 30000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;

        modal.innerHTML = `
            <div style="background: #1e1e2e; border-radius: 20px; padding: 30px; width: 500px; max-width: 90%; border: 1px solid #313244;">
                <h2 style="color: #cba6f7; margin-bottom: 20px;">✨ Create New Pony</h2>
                
                <div class="form-group" style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 6px; color: #cdd6f4;">Folder Name (ID)</label>
                    <input type="text" id="new-pony-name" placeholder="e.g., twilight_sparkle" style="width: 100%; padding: 10px; background: #11111b; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4;">
                    <small style="color: #a6adc8;">This will be the folder name (no spaces, use underscores)</small>
                </div>
                
                <div class="form-group" style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 6px; color: #cdd6f4;">Display Name</label>
                    <input type="text" id="new-pony-display" placeholder="e.g., Twilight Sparkle" style="width: 100%; padding: 10px; background: #11111b; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4;">
                </div>
                
                <div class="form-group" style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 6px; color: #cdd6f4;">Categories (comma separated)</label>
                    <input type="text" id="new-pony-categories" placeholder="Main Ponies, Mares, Unicorns" style="width: 100%; padding: 10px; background: #11111b; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4;">
                </div>
                
                <div style="display: flex; gap: 12px; margin-top: 24px;">
                    <button id="cancel-create-pony" style="flex: 1; padding: 10px; background: #313244; border: none; border-radius: 8px; color: #cdd6f4; cursor: pointer;">Cancel</button>
                    <button id="confirm-create-pony" style="flex: 1; padding: 10px; background: #a6e3a1; border: none; border-radius: 8px; color: #1e1e2e; cursor: pointer; font-weight: bold;">Create Pony</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        document.getElementById('cancel-create-pony')?.addEventListener('click', () => modal.remove());
        document.getElementById('confirm-create-pony')?.addEventListener('click', () => {
            const name = document.getElementById('new-pony-name')?.value.trim();
            const displayName = document.getElementById('new-pony-display')?.value.trim();
            const categories = document.getElementById('new-pony-categories')?.value.trim();

            if (!name) {
                showStatus('Please enter a folder name', true);
                return;
            }

            if (!/^[a-zA-Z0-9_]+$/.test(name)) {
                showStatus('Folder name can only contain letters, numbers, and underscores', true);
                return;
            }

            const config = {
                name: name,
                display_name: displayName || name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                categories: categories ? categories.split(',').map(c => c.trim()).filter(c => c) : ['New Ponies'],
                behaviors: [],
                speaks: [],
                effects: [],
                interactions: []
            };

            EditorAPI.send('pony:create:' + JSON.stringify(config));
            modal.remove();
            showStatus(`Creating pony: ${name}...`);

            setTimeout(() => {
                if (window.refreshPoniesList) window.refreshPoniesList();
                else if (window.PonyListManager && window.PonyListManager.refresh) window.PonyListManager.refresh();
            }, 1000);
        });
    },

    showCreateGifModal(ponyName) {
        const existing = document.getElementById('create-gif-modal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.id = 'create-gif-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.95);
            z-index: 30000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;

        modal.innerHTML = `
            <div style="background: #1e1e2e; border-radius: 20px; padding: 30px; width: 500px; max-width: 90%; border: 1px solid #313244;">
                <h2 style="color: #cba6f7; margin-bottom: 20px;">🎨 Create New Sprite/GIF</h2>
                <p style="color: #a6adc8; margin-bottom: 20px;">For pony: <strong style="color: #cba6f7;">${escapeHtml(ponyName)}</strong></p>
                
                <div class="form-group" style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 6px; color: #cdd6f4;">Sprite Name</label>
                    <input type="text" id="new-sprite-name" placeholder="e.g., idle_right, walk_left, jump" style="width: 100%; padding: 10px; background: #11111b; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4;">
                    <small style="color: #a6adc8;">Use underscores, e.g., "idle_right"</small>
                </div>
                
                <div class="form-group" style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 6px; color: #cdd6f4;">GIF Width</label>
                    <input type="number" id="new-gif-width" value="128" min="16" max="512" step="16" style="width: 100%; padding: 10px; background: #11111b; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4;">
                </div>
                
                <div class="form-group" style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 6px; color: #cdd6f4;">GIF Height</label>
                    <input type="number" id="new-gif-height" value="128" min="16" max="512" step="16" style="width: 100%; padding: 10px; background: #11111b; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4;">
                </div>
                
                <div class="form-group" style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 6px; color: #cdd6f4;">Initial Frames</label>
                    <select id="new-gif-frames" style="width: 100%; padding: 10px; background: #11111b; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4;">
                        <option value="1">1 frame (static)</option>
                        <option value="2" selected>2 frames (basic animation)</option>
                        <option value="4">4 frames</option>
                        <option value="8">8 frames</option>
                    </select>
                </div>
                
                <div class="form-group" style="margin-bottom: 16px;">
                    <label style="display: block; margin-bottom: 6px; color: #cdd6f4;">Background Color</label>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <input type="color" id="new-gif-bg-color" value="#000000" style="width: 50px; height: 40px; border-radius: 8px; cursor: pointer;">
                        <span style="color: #a6adc8;">(transparent = alpha 0)</span>
                    </div>
                </div>
                
                <div class="form-group" style="margin-bottom: 16px;">
                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                        <input type="checkbox" id="new-gif-transparent" checked style="width: 18px; height: 18px;">
                        <span style="color: #cdd6f4;">Use transparent background (recommended)</span>
                    </label>
                </div>
                
                <div style="display: flex; gap: 12px; margin-top: 24px;">
                    <button id="cancel-create-gif" style="flex: 1; padding: 10px; background: #313244; border: none; border-radius: 8px; color: #cdd6f4; cursor: pointer;">Cancel</button>
                    <button id="confirm-create-gif" style="flex: 1; padding: 10px; background: #a6e3a1; border: none; border-radius: 8px; color: #1e1e2e; cursor: pointer; font-weight: bold;">Create Sprite & Edit</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        const bgColorInput = document.getElementById('new-gif-bg-color');
        const transparentCheck = document.getElementById('new-gif-transparent');

        if (transparentCheck && bgColorInput) {
            transparentCheck.addEventListener('change', (e) => {
                bgColorInput.disabled = e.target.checked;
            });
        }

        document.getElementById('cancel-create-gif')?.addEventListener('click', () => modal.remove());
        document.getElementById('confirm-create-gif')?.addEventListener('click', () => {
            const spriteName = document.getElementById('new-sprite-name')?.value.trim();
            const width = parseInt(document.getElementById('new-gif-width')?.value) || 128;
            const height = parseInt(document.getElementById('new-gif-height')?.value) || 128;
            const frameCount = parseInt(document.getElementById('new-gif-frames')?.value) || 2;
            const useTransparent = document.getElementById('new-gif-transparent')?.checked || true;
            const bgColor = bgColorInput?.value || '#000000';

            if (!spriteName) {
                showStatus('Please enter a sprite name', true);
                return;
            }

            if (!/^[a-zA-Z0-9_]+$/.test(spriteName)) {
                showStatus('Sprite name can only contain letters, numbers, and underscores', true);
                return;
            }

            let bgR = 0, bgG = 0, bgB = 0, bgA = 0;
            if (!useTransparent) {
                bgR = parseInt(bgColor.slice(1,3), 16);
                bgG = parseInt(bgColor.slice(3,5), 16);
                bgB = parseInt(bgColor.slice(5,7), 16);
                bgA = 255;
            }

            const frames = [];
            for (let f = 0; f < frameCount; f++) {
                const data = new Uint8ClampedArray(width * height * 4);
                for (let i = 0; i < data.length; i += 4) {
                    data[i] = bgR;
                    data[i + 1] = bgG;
                    data[i + 2] = bgB;
                    data[i + 3] = bgA;
                }
                frames.push({ data: Array.from(data), delay: 10 });
            }

            const gifData = {
                pony_name: ponyName,
                sprite_name: spriteName,
                frames: frames,
                width: width,
                height: height
            };

            EditorAPI.send('gif:create:' + JSON.stringify(gifData));
            modal.remove();
            showStatus(`Creating sprite: ${spriteName}...`);

            setTimeout(() => {
                showInlineGifEditor(ponyName, spriteName);
            }, 1500);
        });
    },

    refreshSpritesList(config) {
        const sprites = [];
        if (config.behaviors) {
            config.behaviors.forEach(behavior => {
                if (behavior.sprite_right && !sprites.includes(behavior.sprite_right)) sprites.push(behavior.sprite_right);
                if (behavior.sprite_left && !sprites.includes(behavior.sprite_left)) sprites.push(behavior.sprite_left);
            });
        }

        const spriteSelect = document.getElementById('sprite-select');
        if (spriteSelect) {
            const currentValue = spriteSelect.value;
            spriteSelect.innerHTML = '<option value="">-- Select sprite to edit --</option>' +
                sprites.map(s => `<option value="${escapeHtml(s)}" ${s === currentValue ? 'selected' : ''}>${escapeHtml(s)}</option>`).join('');
        }

        const statsGrid = document.querySelector('.stats-grid');
        if (statsGrid) {
            statsGrid.innerHTML = `
                <div class="stat-item"><span class="stat-label">Behaviors:</span><span class="stat-value">${config.behaviors?.length || 0}</span></div>
                <div class="stat-item"><span class="stat-label">Speeches:</span><span class="stat-value">${config.speaks?.length || 0}</span></div>
                <div class="stat-item"><span class="stat-label">Effects:</span><span class="stat-value">${config.effects?.length || 0}</span></div>
                <div class="stat-item"><span class="stat-label">Interactions:</span><span class="stat-value">${config.interactions?.length || 0}</span></div>
            `;
        }

        return sprites;
    },

    render(config) {
        console.log('[PonyEditor] render called with config:', config);

        if (config && config.name) {
            this.currentPonyName = config.name;
            this.currentPonyConfig = config;
        }

        if (!this.container) {
            console.error('[PonyEditor] Container not found!');
            return;
        }

        if (!config) {
            this.container.innerHTML = `
                <div class="empty-state">
                    <p>✨ Select a pony from the list to edit</p>
                    <button id="empty-state-create-btn" class="btn-primary" style="margin-top: 16px;">➕ Create New Pony</button>
                </div>
            `;
            const createBtn = document.getElementById('empty-state-create-btn');
            if (createBtn) createBtn.addEventListener('click', () => this.showCreatePonyModal());
            return;
        }

        const sprites = [];
        if (config.behaviors) {
            config.behaviors.forEach(behavior => {
                if (behavior.sprite_right && !sprites.includes(behavior.sprite_right)) sprites.push(behavior.sprite_right);
                if (behavior.sprite_left && !sprites.includes(behavior.sprite_left)) sprites.push(behavior.sprite_left);
            });
        }

        const html = `
            <div class="editor-tabs">
                <button class="tab-btn active" data-tab="basic">📝 Basic</button>
                <button class="tab-btn" data-tab="behaviors">🏃 Behaviors (${config.behaviors?.length || 0})</button>
                <button class="tab-btn" data-tab="speeches">💬 Speeches (${config.speaks?.length || 0})</button>
                <button class="tab-btn" data-tab="effects">✨ Effects (${config.effects?.length || 0})</button>
                <button class="tab-btn" data-tab="interactions">🤝 Interactions (${config.interactions?.length || 0})</button>
            </div>
            
            <div id="tab-basic" class="tab-pane active">
                ${this.renderBasicTab(config, sprites)}
            </div>
            <div id="tab-behaviors" class="tab-pane">
                ${BehaviorEditor.render(config.behaviors || [], config.name)}
            </div>
            <div id="tab-speeches" class="tab-pane">
                ${SpeechEditor.render(config.speaks || [])}
            </div>
            <div id="tab-effects" class="tab-pane">
                ${EffectEditor.render(config.effects || [])}
            </div>
            <div id="tab-interactions" class="tab-pane">
                ${InteractionEditor.render(config.interactions || [])}
            </div>
        `;

        this.container.innerHTML = html;

        this.container.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });

        this.bindEvents(config);

        if (BehaviorEditor.bindEvents) BehaviorEditor.bindEvents(this.container);
        if (SpeechEditor.bindEvents) SpeechEditor.bindEvents(this.container);
        if (EffectEditor.bindEvents) EffectEditor.bindEvents(this.container);
        if (InteractionEditor.bindEvents) InteractionEditor.bindEvents(this.container);
    },

    renderBasicTab(config, sprites) {
        const displayName = config.display_name || config.name;
        const categories = (config.categories || []).join(', ');

        return `
            <div class="card">
                <div class="card-header">
                    <h3>General Information</h3>
                </div>
                <div class="form-group">
                    <label>Name (folder)</label>
                    <input type="text" id="pony-name-folder" value="${escapeHtml(config.name || '')}" readonly disabled>
                    <small class="form-hint">Directory name</small>
                </div>
                <div class="form-group">
                    <label>Display Name</label>
                    <input type="text" id="display-name-display" value="${escapeHtml(displayName)}" 
                           placeholder="Display name (optional)">
                </div>
                <div class="form-group">
                    <label>Categories</label>
                    <input type="text" id="categories" value="${escapeHtml(categories)}" 
                           placeholder="Main Ponies, Mares, Unicorns">
                </div>
                <div class="form-group">
                    <label>Sprites / GIFs</label>
                    <select id="sprite-select" style="margin-bottom: 8px; width: 100%;">
                        <option value="">-- Select sprite to edit --</option>
                        ${sprites.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join('')}
                    </select>
                    <div style="display: flex; gap: 8px;">
                        <button id="btn-edit-gif" class="btn-secondary" style="flex: 1;">🎨 Edit Selected Sprite</button>
                        <button id="btn-create-gif" class="btn-primary" style="flex: 1;">➕ Create New Sprite</button>
                    </div>
                    <small class="form-hint" style="display: block; margin-top: 6px;">💡 Tip: After creating a sprite, add it to a behavior in the Behaviors tab</small>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header"><h3>Statistics</h3></div>
                <div class="stats-grid">
                    <div class="stat-item"><span class="stat-label">Behaviors:</span><span class="stat-value">${config.behaviors?.length || 0}</span></div>
                    <div class="stat-item"><span class="stat-label">Speeches:</span><span class="stat-value">${config.speaks?.length || 0}</span></div>
                    <div class="stat-item"><span class="stat-label">Effects:</span><span class="stat-value">${config.effects?.length || 0}</span></div>
                    <div class="stat-item"><span class="stat-label">Interactions:</span><span class="stat-value">${config.interactions?.length || 0}</span></div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header"><h3>Quick Actions</h3></div>
                <button id="quick-add-behavior" class="btn-secondary" style="width: 100%; margin-bottom: 8px;">🏃 Add New Behavior</button>
                <button id="quick-add-speech" class="btn-secondary" style="width: 100%; margin-bottom: 8px;">💬 Add New Speech</button>
                <button id="quick-add-effect" class="btn-secondary" style="width: 100%; margin-bottom: 8px;">✨ Add New Effect</button>
                <button id="quick-add-interaction" class="btn-secondary" style="width: 100%;">🤝 Add New Interaction</button>
            </div>
        `;
    },

    bindEvents(config) {
        const displayNameInput = document.getElementById('display-name-display');
        const categoriesInput = document.getElementById('categories');
        const editGifBtn = document.getElementById('btn-edit-gif');
        const createGifBtn = document.getElementById('btn-create-gif');
        const spriteSelect = document.getElementById('sprite-select');

        const quickAddBehavior = document.getElementById('quick-add-behavior');
        const quickAddSpeech = document.getElementById('quick-add-speech');
        const quickAddEffect = document.getElementById('quick-add-effect');
        const quickAddInteraction = document.getElementById('quick-add-interaction');

        if (displayNameInput) {
            displayNameInput.addEventListener('change', () => {
                config.display_name = displayNameInput.value;
                EditorState.markModified();
            });
        }

        if (categoriesInput) {
            categoriesInput.addEventListener('change', () => {
                config.categories = categoriesInput.value.split(',').map(c => c.trim()).filter(c => c);
                EditorState.markModified();
            });
        }

        if (editGifBtn && spriteSelect) {
            editGifBtn.addEventListener('click', () => {
                const selectedSprite = spriteSelect.value;
                if (!selectedSprite) {
                    showStatus('Please select a sprite first', true);
                    return;
                }
                console.log('[PonyEditor] Opening GIF editor for:', config.name, selectedSprite);
                showInlineGifEditor(config.name, selectedSprite);
            });
        }

        if (createGifBtn) {
            createGifBtn.addEventListener('click', () => {
                this.showCreateGifModal(config.name);
            });
        }

        if (quickAddBehavior) {
            quickAddBehavior.addEventListener('click', () => {
                if (!config.behaviors) config.behaviors = [];
                config.behaviors.push({
                    name: "new_behavior",
                    sprite_right: "idle_right",
                    sprite_left: "idle_left",
                    frames: 2,
                    frame_time: 10,
                    loop: true,
                    mode: "idle"
                });
                EditorState.markModified();
                this.render(config);
                this.switchTab('behaviors');
                showStatus('Added new behavior');
            });
        }

        if (quickAddSpeech) {
            quickAddSpeech.addEventListener('click', () => {
                if (!config.speaks) config.speaks = [];
                config.speaks.push({
                    text: "New speech line",
                    trigger: "click",
                    cooldown: 5
                });
                EditorState.markModified();
                this.render(config);
                this.switchTab('speeches');
                showStatus('Added new speech');
            });
        }

        if (quickAddEffect) {
            quickAddEffect.addEventListener('click', () => {
                if (!config.effects) config.effects = [];
                config.effects.push({
                    name: "new_effect",
                    type: "sparkle",
                    duration: 30
                });
                EditorState.markModified();
                this.render(config);
                this.switchTab('effects');
                showStatus('Added new effect');
            });
        }

        if (quickAddInteraction) {
            quickAddInteraction.addEventListener('click', () => {
                if (!config.interactions) config.interactions = [];
                config.interactions.push({
                    with_pony: "target_pony",
                    response: "Hello there!",
                    condition: "always"
                });
                EditorState.markModified();
                this.render(config);
                this.switchTab('interactions');
                showStatus('Added new interaction');
            });
        }
    },

    switchTab(tabName) {
        document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
        const targetPane = document.getElementById(`tab-${tabName}`);
        if (targetPane) targetPane.classList.add('active');
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.tab === tabName) btn.classList.add('active');
        });
    },

    // ============================================================
    // ФУНКЦИОНАЛ ТРЕЙСА - ИСПРАВЛЕННАЯ ВЕРСИЯ
    // ============================================================

    showTracePanel: function() {
        const state = window.GifEditorState;
        if (!state || !state.modal) {
            showStatus('❌ Please open GIF editor first', true);
            return;
        }

        if (document.getElementById('trace-panel')) {
            this.closeTracePanel();
            return;
        }

        const modal = state.modal;

        // Находим контейнер с канвасом
        let canvasContainer = modal.querySelector('.gif-canvas-wrapper');
        if (!canvasContainer) {
            canvasContainer = modal.querySelector('div[style*="flex: 1; display: flex; justify-content: center;"]') ||
                modal.querySelector('div[style*="position: relative;"]') ||
                modal.querySelector('div[style*="flex:1"]') ||
                modal.querySelector('div[style*="display: flex;"][style*="justify-content: center;"]');
        }

        if (!canvasContainer) {
            showStatus('❌ Cannot find canvas container', true);
            return;
        }

        canvasContainer.style.position = 'relative';
        canvasContainer.style.display = 'flex';
        canvasContainer.style.justifyContent = 'center';
        canvasContainer.style.alignItems = 'center';

        const mainCanvas = document.getElementById('gif-main-canvas');
        if (!mainCanvas) {
            showStatus('❌ Main canvas not found', true);
            return;
        }

        // Удаляем старый трейс-канвас
        const oldTrace = document.getElementById('trace-render-canvas');
        if (oldTrace) oldTrace.remove();

        // Создаем канвас для трейса ПОД основным
        const traceCanvas = document.createElement('canvas');
        traceCanvas.id = 'trace-render-canvas';
        traceCanvas.style.cssText = `
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        pointer-events: none;
        z-index: 1;
        image-rendering: crisp-edges;
        image-rendering: pixelated;
        border: 1px solid rgba(203, 166, 247, 0.1);
        border-radius: 8px;
    `;

        canvasContainer.insertBefore(traceCanvas, mainCanvas);

        // Основной канвас поверх
        mainCanvas.style.position = 'relative';
        mainCanvas.style.zIndex = '2';

        // Панель управления
        const panel = document.createElement('div');
        panel.id = 'trace-panel';
        panel.style.cssText = `
        position: absolute;
        bottom: 20px;
        right: 20px;
        z-index: 150;
        background: rgba(30,30,46,0.95);
        border: 1px solid #45475a;
        border-radius: 16px;
        padding: 16px 18px;
        min-width: 340px;
        max-width: 420px;
        backdrop-filter: blur(16px);
        box-shadow: 0 12px 48px rgba(0,0,0,0.7);
        pointer-events: all;
        font-size: 12px;
        user-select: none;
        transition: all 0.2s ease;
    `;

        panel.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <span style="color: #cba6f7; font-weight: bold; font-size: 14px; display: flex; align-items: center; gap: 8px;">
                <span>🎯</span> Trace Reference
            </span>
            <div style="display: flex; gap: 6px;">
                <button id="trace-load-file" class="btn-secondary" style="font-size: 11px; padding: 4px 12px; background: #313244; border: 1px solid #45475a; border-radius: 6px; color: #cdd6f4; cursor: pointer; transition: all 0.2s;">
                    📁 Load GIF
                </button>
                <button id="trace-use-main" class="btn-primary" style="font-size: 11px; padding: 4px 12px; background: #cba6f7; border: none; border-radius: 6px; color: #1e1e2e; cursor: pointer; font-weight: bold; transition: all 0.2s;">
                    📋 Main GIF
                </button>
                <button id="trace-close-btn" class="btn-secondary" style="font-size: 11px; padding: 4px 12px; background: #313244; border: 1px solid #45475a; border-radius: 6px; color: #f38ba8; cursor: pointer; transition: all 0.2s;">
                    ✕
                </button>
            </div>
        </div>
        
        <div id="trace-file-status" style="font-size: 10px; color: #a6adc8; margin-bottom: 10px; padding: 4px 8px; background: #11111b; border-radius: 6px; border: 1px solid #313244; display: flex; justify-content: space-between;">
            <span id="trace-file-name">No file loaded</span>
            <span id="trace-file-info">—</span>
        </div>
        
        <div style="display: flex; gap: 14px; margin-bottom: 12px;">
            <div style="flex: 1;">
                <label style="font-size: 10px; color: #a6adc8; display: block; margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.5px;">Size</label>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <input type="range" id="trace-size" min="0.1" max="3" step="0.05" value="1" style="flex: 1; height: 4px; background: #313244; border-radius: 2px; outline: none; -webkit-appearance: none; appearance: none;">
                    <span id="trace-size-value" style="font-size: 10px; color: #cba6f7; font-family: monospace; min-width: 36px; text-align: right;">100%</span>
                </div>
            </div>
            <div style="flex: 1;">
                <label style="font-size: 10px; color: #a6adc8; display: block; margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.5px;">Opacity</label>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <input type="range" id="trace-opacity" min="0.05" max="1" step="0.01" value="0.35" style="flex: 1; height: 4px; background: #313244; border-radius: 2px; outline: none; -webkit-appearance: none; appearance: none;">
                    <span id="trace-opacity-value" style="font-size: 10px; color: #cba6f7; font-family: monospace; min-width: 36px; text-align: right;">35%</span>
                </div>
            </div>
        </div>
        
        <div style="display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 10px;">
            <button id="trace-flip-h" class="trace-control-btn" style="font-size: 10px; padding: 3px 10px; background: #313244; border: 1px solid #45475a; border-radius: 5px; color: #cdd6f4; cursor: pointer; transition: all 0.2s;">↔ Flip H</button>
            <button id="trace-flip-v" class="trace-control-btn" style="font-size: 10px; padding: 3px 10px; background: #313244; border: 1px solid #45475a; border-radius: 5px; color: #cdd6f4; cursor: pointer; transition: all 0.2s;">↕ Flip V</button>
            <button id="trace-grid" class="trace-control-btn" style="font-size: 10px; padding: 3px 10px; background: #313244; border: 1px solid #45475a; border-radius: 5px; color: #cdd6f4; cursor: pointer; transition: all 0.2s;">📐 Grid</button>
            <button id="trace-reset" class="trace-control-btn" style="font-size: 10px; padding: 3px 10px; background: #313244; border: 1px solid #45475a; border-radius: 5px; color: #cdd6f4; cursor: pointer; transition: all 0.2s;">↺ Reset</button>
            <span style="color: #a6adc8; font-size: 10px; display: flex; align-items: center; margin-left: auto; gap: 4px;">
                <span id="trace-frame-count">0</span> frames
            </span>
        </div>
        
        <div id="trace-frames-container" style="display: flex; gap: 6px; overflow-x: auto; padding: 6px 0; max-height: 80px; min-height: 60px; background: #11111b; border-radius: 8px; border: 1px solid #313244; align-items: center;">
            <div style="color: #a6adc8; font-size: 11px; padding: 6px 12px; width: 100%; text-align: center;">Load a GIF or use Main GIF</div>
        </div>
        
        <div id="trace-extra-controls" style="display: none; margin-top: 8px; border-top: 1px solid #313244; padding-top: 8px;">
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                <button id="trace-extract-all" class="trace-btn-extract" style="font-size: 10px; padding: 4px 12px; background: #1e1e2e; border: 1px solid #89b4fa; border-radius: 5px; color: #89b4fa; cursor: pointer; transition: all 0.2s;">
                    📥 Extract All Frames
                </button>
                <button id="trace-extract-current" class="trace-btn-extract" style="font-size: 10px; padding: 4px 12px; background: #1e1e2e; border: 1px solid #89b4fa; border-radius: 5px; color: #89b4fa; cursor: pointer; transition: all 0.2s;">
                    📥 Extract Current
                </button>
                <span style="font-size: 9px; color: #a6adc8;">(copy to main editor)</span>
            </div>
        </div>
    `;

        canvasContainer.appendChild(panel);

        // Стили
        const style = document.createElement('style');
        style.textContent = `
        .trace-control-btn:hover {
            background: #45475a;
            border-color: #cba6f7;
        }
        .trace-control-btn.active {
            border-color: #cba6f7;
            background: rgba(203, 166, 247, 0.15);
            box-shadow: 0 0 12px rgba(203, 166, 247, 0.1);
        }
        .trace-control-btn.active:hover {
            background: rgba(203, 166, 247, 0.25);
        }
        #trace-frames-container::-webkit-scrollbar {
            height: 4px;
        }
        #trace-frames-container::-webkit-scrollbar-track {
            background: #1e1e2e;
            border-radius: 2px;
        }
        #trace-frames-container::-webkit-scrollbar-thumb {
            background: #45475a;
            border-radius: 2px;
        }
        #trace-frames-container::-webkit-scrollbar-thumb:hover {
            background: #cba6f7;
        }
        .trace-frame-item {
            flex-shrink: 0;
            cursor: pointer;
            border: 2px solid #313244;
            border-radius: 6px;
            padding: 4px;
            background: #0a0a0f;
            transition: all 0.15s ease;
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 56px;
        }
        .trace-frame-item:hover {
            border-color: #89b4fa;
            transform: scale(1.05);
        }
        .trace-frame-item.active {
            border-color: #cba6f7;
            box-shadow: 0 0 16px rgba(203, 166, 247, 0.2);
        }
        .trace-frame-item canvas {
            border-radius: 3px;
            image-rendering: crisp-edges;
            image-rendering: pixelated;
        }
        .trace-frame-label {
            font-size: 8px;
            color: #a6adc8;
            margin-top: 2px;
            font-family: monospace;
        }
        #trace-file-status.loaded {
            border-color: #a6e3a1;
        }
        #trace-file-status.loaded #trace-file-name {
            color: #a6e3a1;
        }
        .trace-btn-extract {
            background: #1e1e2e !important;
            border: 1px solid #89b4fa !important;
            color: #89b4fa !important;
        }
        .trace-btn-extract:hover {
            background: #313244 !important;
        }
    `;
        document.head.appendChild(style);
        panel._styleElement = style;

        // Состояние трейса
        const traceState = {
            loaded: false,
            frames: [],
            currentFrame: 0,
            width: 0,
            height: 0,
            size: 1,
            opacity: 0.35,
            flipH: false,
            flipV: false,
            showGrid: false,
            canvas: traceCanvas,
            ctx: traceCanvas.getContext('2d'),
            panel: panel,
            animationId: null,
            frameDelay: 100,
            lastFrameTime: 0,
            fileName: '',
            _mainCanvas: mainCanvas,
            _stateManager: state,
            _resizeHandler: null,
            _mainCanvasObserver: null,
            _useMainGif: false,
            _renderPending: false,
            _forceUpdateCount: 0
        };

        window._traceState = traceState;

        // === ФУНКЦИЯ ПРИНУДИТЕЛЬНОГО ОБНОВЛЕНИЯ ===
        function forceUpdateTrace() {
            console.log('[Trace] Force update trace, attempt:', traceState._forceUpdateCount++);

            if (!state || !traceState) return;

            const mainCanvas = document.getElementById('gif-main-canvas');
            const traceCanvas = document.getElementById('trace-render-canvas');

            if (mainCanvas && traceCanvas) {
                // Принудительно устанавливаем размеры
                const mainWidth = mainCanvas.width || mainCanvas.getBoundingClientRect().width || 128;
                const mainHeight = mainCanvas.height || mainCanvas.getBoundingClientRect().height || 128;

                traceCanvas.width = mainWidth;
                traceCanvas.height = mainHeight;
                traceCanvas.style.width = mainWidth + 'px';
                traceCanvas.style.height = mainHeight + 'px';

                // Убеждаемся что позиционирование правильное
                traceCanvas.style.position = 'absolute';
                traceCanvas.style.top = '50%';
                traceCanvas.style.left = '50%';
                traceCanvas.style.transform = 'translate(-50%, -50%)';
                traceCanvas.style.zIndex = '1';
                traceCanvas.style.pointerEvents = 'none';

                // Обновляем state
                if (traceState._mainCanvas) {
                    traceState._mainCanvas = mainCanvas;
                }
            }

            // Перерисовываем основной канвас
            if (state.drawCanvas) {
                state.drawCanvas();
            }

            // Перерисовываем трейс
            renderTrace();

            // Обновляем таймлайн
            if (state.updateTimeline) {
                state.updateTimeline();
            }

            // Принудительный reflow
            if (mainCanvas) {
                mainCanvas.getBoundingClientRect();
            }
        }

        // === ФУНКЦИЯ ЗАГРУЗКИ ВНЕШНЕЙ GIF ПО ПУТИ ===
        function loadExternalGif(file) {
            if (!file) return;

            // Пытаемся получить путь к файлу
            let filePath = null;

            if (file.path) {
                filePath = file.path;
            } else if (file.webkitRelativePath) {
                filePath = file.webkitRelativePath;
            }

            console.log('[Trace] File path:', filePath);
            const fileName = file.name;

            if (filePath) {
                const encodedPath = encodeURIComponent(filePath);
                console.log('[Trace] Sending path to Rust:', encodedPath);

                const tempHandler = function(msg) {
                    try {
                        const data = typeof msg === 'string' ? JSON.parse(msg) : msg;
                        if (data.type === 'trace_gif_data') {
                            console.log('[Trace] Received decoded GIF from Rust, frames:', data.frames?.length);

                            if (data.frames && data.frames.length > 0) {
                                const frames = data.frames.map(f => ({
                                    data: new Uint8ClampedArray(f.data),
                                    delay: f.delay || 10
                                }));
                                applyTraceFrames(frames, data.width, data.height, fileName);
                            } else {
                                showStatus('❌ No frames in GIF', true);
                            }

                            if (window._originalEditorReceive) {
                                window.editorReceive = window._originalEditorReceive;
                                window._originalEditorReceive = null;
                            }
                        } else if (data.type === 'trace_gif_error') {
                            showStatus('❌ Error decoding GIF: ' + (data.message || ''), true);
                            if (window._originalEditorReceive) {
                                window.editorReceive = window._originalEditorReceive;
                                window._originalEditorReceive = null;
                            }
                        } else if (window._originalEditorReceive) {
                            window._originalEditorReceive(msg);
                        }
                    } catch(e) {
                        console.error('[Trace] Error in temp handler:', e);
                        if (window._originalEditorReceive) {
                            window._originalEditorReceive(msg);
                        }
                    }
                };

                window._originalEditorReceive = window.editorReceive;
                window.editorReceive = tempHandler;

                EditorAPI.send('trace:load_gif_path:' + encodedPath);

                setTimeout(() => {
                    if (window.editorReceive === tempHandler) {
                        window.editorReceive = window._originalEditorReceive;
                        window._originalEditorReceive = null;
                        showStatus('❌ Timeout waiting for GIF decode', true);
                    }
                }, 30000);

                return;
            }

            // Fallback: base64
            console.log('[Trace] No path available, using base64 fallback');
            const reader = new FileReader();
            reader.onload = function(e) {
                try {
                    const arrayBuffer = e.target.result;
                    const bytes = new Uint8Array(arrayBuffer);

                    let binary = '';
                    for (let i = 0; i < bytes.length; i++) {
                        binary += String.fromCharCode(bytes[i]);
                    }
                    const base64 = btoa(binary);

                    const tempHandler = function(msg) {
                        try {
                            const data = typeof msg === 'string' ? JSON.parse(msg) : msg;
                            if (data.type === 'trace_gif_data') {
                                console.log('[Trace] Received decoded GIF from Rust, frames:', data.frames?.length);

                                if (data.frames && data.frames.length > 0) {
                                    const frames = data.frames.map(f => ({
                                        data: new Uint8ClampedArray(f.data),
                                        delay: f.delay || 10
                                    }));
                                    applyTraceFrames(frames, data.width, data.height, fileName);
                                } else {
                                    showStatus('❌ No frames in GIF', true);
                                }

                                if (window._originalEditorReceive) {
                                    window.editorReceive = window._originalEditorReceive;
                                    window._originalEditorReceive = null;
                                }
                            } else if (data.type === 'trace_gif_error') {
                                showStatus('❌ Error decoding GIF: ' + (data.message || ''), true);
                                if (window._originalEditorReceive) {
                                    window.editorReceive = window._originalEditorReceive;
                                    window._originalEditorReceive = null;
                                }
                            } else if (window._originalEditorReceive) {
                                window._originalEditorReceive(msg);
                            }
                        } catch(e) {
                            console.error('[Trace] Error in temp handler:', e);
                            if (window._originalEditorReceive) {
                                window._originalEditorReceive(msg);
                            }
                        }
                    };

                    window._originalEditorReceive = window.editorReceive;
                    window.editorReceive = tempHandler;

                    EditorAPI.send('trace:load_gif:' + base64);

                } catch(e) {
                    console.error('[Trace] Error loading GIF:', e);
                    showStatus('❌ Error loading GIF: ' + e.message, true);
                }
            };
            reader.readAsArrayBuffer(file);
        }

        function applyTraceFrames(frames, width, height, fileName) {
            console.log('[Trace] applyTraceFrames called, frames:', frames.length);

            traceState.frames = frames;
            traceState.width = width;
            traceState.height = height;
            traceState.currentFrame = 0;
            traceState.loaded = true;
            traceState.fileName = fileName || 'External GIF';
            traceState.frameDelay = (frames[0]?.delay || 10) * 10;
            traceState._useMainGif = false;
            traceState._forceUpdateCount = 0;

            const infoText = frames.length + ' frames, ' + width + '×' + height;
            document.getElementById('trace-file-name').textContent = fileName || 'External GIF';
            document.getElementById('trace-file-info').textContent = infoText;
            document.getElementById('trace-file-status').classList.add('loaded');

            // Обновляем UI с кадрами
            PonyEditor._updateTraceUI(traceState, renderTrace);

            // ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ - множество попыток
            setTimeout(function() { forceUpdateTrace(); }, 10);
            setTimeout(function() { forceUpdateTrace(); }, 50);
            setTimeout(function() { forceUpdateTrace(); }, 100);
            setTimeout(function() { forceUpdateTrace(); }, 200);
            setTimeout(function() { forceUpdateTrace(); }, 300);
            setTimeout(function() { forceUpdateTrace(); }, 500);
            setTimeout(function() { forceUpdateTrace(); }, 800);
            setTimeout(function() { forceUpdateTrace(); }, 1200);

            document.getElementById('trace-extra-controls').style.display = 'flex';

            // Запускаем анимацию если больше 1 кадра
            if (traceState.frames.length > 1) {
                if (traceState.animationId) {
                    cancelAnimationFrame(traceState.animationId);
                    traceState.animationId = null;
                }
                traceState.lastFrameTime = 0;
                animateFrames();
            }

            showStatus(`✅ Trace loaded: ${width}×${height}, ${frames.length} frames from "${fileName}"`);
        }

        function animateFrames() {
            if (!traceState.loaded || traceState.frames.length <= 1) {
                traceState.animationId = requestAnimationFrame(animateFrames);
                return;
            }

            const now = performance.now();
            if (!traceState.lastFrameTime) traceState.lastFrameTime = now;
            const delta = now - traceState.lastFrameTime;

            if (delta >= traceState.frameDelay) {
                traceState.lastFrameTime = now;
                traceState.currentFrame = (traceState.currentFrame + 1) % traceState.frames.length;
                renderTrace();
                updateFrameSelection();
            }

            traceState.animationId = requestAnimationFrame(animateFrames);
        }

        // === ОБРАБОТЧИК ЗАГРУЗКИ ФАЙЛА ===
        document.getElementById('trace-load-file').addEventListener('click', function() {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/gif';
            input.onchange = function(e) {
                if (this.files && this.files.length > 0) {
                    loadExternalGif(this.files[0]);
                }
            };
            input.click();
        });

        // === ФУНКЦИЯ ЗАГРУЗКИ ИЗ ОСНОВНОЙ GIF ===
        function loadTraceFromMainGif() {
            if (!state || !state.frames || state.frames.length === 0) {
                showStatus('❌ Main GIF has no frames', true);
                return;
            }

            console.log('[Trace] Loading from main GIF, frames:', state.frames.length);

            traceState.frames = state.frames.map(f => ({
                data: new Uint8ClampedArray(f.data),
                delay: f.delay || 10
            }));
            traceState.width = state.width;
            traceState.height = state.height;
            traceState.currentFrame = state.currentFrame || 0;
            traceState.loaded = true;
            traceState.frameDelay = (state.frames[0]?.delay || 10) * 10;
            traceState.fileName = 'Main GIF';
            traceState._useMainGif = true;
            traceState._forceUpdateCount = 0;

            document.getElementById('trace-file-name').textContent = 'Main GIF';
            document.getElementById('trace-file-info').textContent = traceState.frames.length + ' frames, ' + traceState.width + '×' + traceState.height;
            document.getElementById('trace-file-status').classList.add('loaded');

            PonyEditor._updateTraceUI(traceState, renderTrace);

            // ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ
            setTimeout(function() { forceUpdateTrace(); }, 10);
            setTimeout(function() { forceUpdateTrace(); }, 50);
            setTimeout(function() { forceUpdateTrace(); }, 100);
            setTimeout(function() { forceUpdateTrace(); }, 200);
            setTimeout(function() { forceUpdateTrace(); }, 500);

            document.getElementById('trace-extra-controls').style.display = 'flex';

            if (traceState.frames.length > 1) {
                if (traceState.animationId) {
                    cancelAnimationFrame(traceState.animationId);
                    traceState.animationId = null;
                }
                traceState.lastFrameTime = 0;
                animateFrames();
            }

            showStatus(`✅ Trace loaded: ${traceState.width}×${traceState.height}, ${traceState.frames.length} frames from main GIF`);
        }

        // === ЭКСПОРТ КАДРОВ В ОСНОВНОЙ РЕДАКТОР ===
        function extractFramesToMain(mode) {
            if (!traceState.loaded || traceState.frames.length === 0) {
                showStatus('❌ No trace frames to extract', true);
                return;
            }

            const stateManager = window.GifEditorState;
            if (!stateManager) {
                showStatus('❌ GIF editor not found', true);
                return;
            }

            const indices = mode === 'all'
                ? Array.from({length: traceState.frames.length}, (_, i) => i)
                : [traceState.currentFrame];

            let added = 0;
            for (const idx of indices) {
                if (idx >= 0 && idx < traceState.frames.length) {
                    const srcFrame = traceState.frames[idx];
                    let data = new Uint8ClampedArray(srcFrame.data);

                    if (stateManager.width !== traceState.width || stateManager.height !== traceState.height) {
                        data = resizeFrameData(data, traceState.width, traceState.height,
                            stateManager.width, stateManager.height);
                    }

                    stateManager.frames.push({
                        data: data,
                        delay: srcFrame.delay || 10
                    });
                    added++;
                }
            }

            if (added > 0) {
                stateManager.currentFrame = stateManager.frames.length - 1;
                stateManager.hasChanges = true;
                stateManager.drawCanvas();
                stateManager.updateTimeline();
                showStatus(`✅ Extracted ${added} frame(s) from trace to main editor`);
            } else {
                showStatus('❌ No frames extracted', true);
            }
        }

        function resizeFrameData(data, srcW, srcH, dstW, dstH) {
            const newData = new Uint8ClampedArray(dstW * dstH * 4);
            newData.fill(0);

            const scaleX = srcW / dstW;
            const scaleY = srcH / dstH;

            for (let y = 0; y < dstH; y++) {
                for (let x = 0; x < dstW; x++) {
                    const srcX = Math.floor(x * scaleX);
                    const srcY = Math.floor(y * scaleY);
                    if (srcX < srcW && srcY < srcH) {
                        const srcIdx = (srcY * srcW + srcX) * 4;
                        const dstIdx = (y * dstW + x) * 4;
                        newData[dstIdx] = data[srcIdx];
                        newData[dstIdx + 1] = data[srcIdx + 1];
                        newData[dstIdx + 2] = data[srcIdx + 2];
                        newData[dstIdx + 3] = data[srcIdx + 3];
                    }
                }
            }
            return newData;
        }

        // === ОБРАБОТЧИКИ ЭКСПОРТА ===
        document.getElementById('trace-extract-all').addEventListener('click', function() {
            extractFramesToMain('all');
        });

        document.getElementById('trace-extract-current').addEventListener('click', function() {
            extractFramesToMain('current');
        });

        // === ФУНКЦИЯ РЕНДЕРИНГА ТРЕЙСА ===
        function renderTrace() {
            const canvas = traceState.canvas;
            const ctx = traceState.ctx;
            const mainCanvas = traceState._mainCanvas;

            if (!mainCanvas) {
                console.warn('[Trace] No main canvas');
                return;
            }

            // Принудительно синхронизируем размеры с основным канвасом
            const mainWidth = mainCanvas.width || mainCanvas.getBoundingClientRect().width || 128;
            const mainHeight = mainCanvas.height || mainCanvas.getBoundingClientRect().height || 128;

            if (canvas.width !== mainWidth || canvas.height !== mainHeight) {
                canvas.width = mainWidth;
                canvas.height = mainHeight;
                canvas.style.width = mainWidth + 'px';
                canvas.style.height = mainHeight + 'px';

                // Обновляем позиционирование
                canvas.style.position = 'absolute';
                canvas.style.top = '50%';
                canvas.style.left = '50%';
                canvas.style.transform = 'translate(-50%, -50%)';
                canvas.style.zIndex = '1';
                canvas.style.pointerEvents = 'none';
            }

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            if (!traceState.loaded || traceState.frames.length === 0) {
                return;
            }

            const frameIndex = traceState.currentFrame % traceState.frames.length;
            const frameData = traceState.frames[frameIndex];
            if (!frameData) {
                console.warn('[Trace] No frame data for index:', frameIndex);
                return;
            }

            const targetWidth = state.width || traceState.width;
            const targetHeight = state.height || traceState.height;

            const baseSize = Math.min(canvas.width / targetWidth, canvas.height / targetHeight);
            const scale = baseSize * traceState.size;

            const drawW = traceState.width * scale;
            const drawH = traceState.height * scale;

            const offsetX = (canvas.width - drawW) / 2;
            const offsetY = (canvas.height - drawH) / 2;

            ctx.globalAlpha = traceState.opacity;

            let sx = 1, sy = 1;
            if (traceState.flipH) sx = -1;
            if (traceState.flipV) sy = -1;

            ctx.save();
            ctx.translate(canvas.width/2, canvas.height/2);
            ctx.scale(sx, sy);
            ctx.translate(-canvas.width/2, -canvas.height/2);

            try {
                const imgData = new ImageData(frameData.data, traceState.width, traceState.height);
                const tempCanvas = document.createElement('canvas');
                tempCanvas.width = traceState.width;
                tempCanvas.height = traceState.height;
                const tempCtx = tempCanvas.getContext('2d');
                tempCtx.putImageData(imgData, 0, 0);
                ctx.imageSmoothingEnabled = false;
                ctx.drawImage(tempCanvas, offsetX, offsetY, drawW, drawH);
            } catch(e) {
                console.warn('[Trace] Render error:', e);
            }

            ctx.restore();
            ctx.globalAlpha = 1;

            if (traceState.showGrid) {
                ctx.strokeStyle = 'rgba(203, 166, 247, 0.15)';
                ctx.lineWidth = 1;
                const gridSize = 32 * scale;
                for (let x = offsetX % gridSize; x < canvas.width; x += gridSize) {
                    ctx.beginPath();
                    ctx.moveTo(x, 0);
                    ctx.lineTo(x, canvas.height);
                    ctx.stroke();
                }
                for (let y = offsetY % gridSize; y < canvas.height; y += gridSize) {
                    ctx.beginPath();
                    ctx.moveTo(0, y);
                    ctx.lineTo(canvas.width, y);
                    ctx.stroke();
                }
            }
        }

        // === УПРАВЛЕНИЕ ===
        const sizeSlider = document.getElementById('trace-size');
        const opacitySlider = document.getElementById('trace-opacity');
        const sizeValue = document.getElementById('trace-size-value');
        const opacityValue = document.getElementById('trace-opacity-value');

        sizeSlider.addEventListener('input', function() {
            traceState.size = parseFloat(this.value);
            sizeValue.textContent = Math.round(traceState.size * 100) + '%';
            renderTrace();
        });

        opacitySlider.addEventListener('input', function() {
            traceState.opacity = parseFloat(this.value);
            opacityValue.textContent = Math.round(traceState.opacity * 100) + '%';
            renderTrace();
        });

        function setupToggleButton(id, property) {
            const btn = document.getElementById(id);
            if (!btn) return;
            btn.addEventListener('click', function() {
                traceState[property] = !traceState[property];
                this.classList.toggle('active');
                renderTrace();
            });
        }

        setupToggleButton('trace-flip-h', 'flipH');
        setupToggleButton('trace-flip-v', 'flipV');
        setupToggleButton('trace-grid', 'showGrid');

        document.getElementById('trace-reset').addEventListener('click', function() {
            traceState.size = 1;
            traceState.opacity = 0.35;
            traceState.flipH = false;
            traceState.flipV = false;
            traceState.showGrid = false;
            sizeSlider.value = 1;
            opacitySlider.value = 0.35;
            sizeValue.textContent = '100%';
            opacityValue.textContent = '35%';
            document.getElementById('trace-flip-h').classList.remove('active');
            document.getElementById('trace-flip-v').classList.remove('active');
            document.getElementById('trace-grid').classList.remove('active');
            renderTrace();
        });

        document.getElementById('trace-use-main').addEventListener('click', function() {
            loadTraceFromMainGif();
            this.textContent = '✅ Loaded';
            setTimeout(() => { this.textContent = '📋 Main GIF'; }, 2000);
        });

        document.getElementById('trace-close-btn').addEventListener('click', function() {
            PonyEditor.closeTracePanel();
        });

        // Наблюдатель за изменением размера основного канваса
        const resizeObserver = new ResizeObserver(() => {
            console.log('[Trace] ResizeObserver triggered');
            if (!traceState._renderPending) {
                traceState._renderPending = true;
                requestAnimationFrame(() => {
                    traceState._renderPending = false;
                    renderTrace();
                });
            }
        });
        resizeObserver.observe(mainCanvas);
        traceState._mainCanvasObserver = resizeObserver;

        const resizeHandler = () => {
            console.log('[Trace] Window resize triggered');
            if (!traceState._renderPending) {
                traceState._renderPending = true;
                requestAnimationFrame(() => {
                    traceState._renderPending = false;
                    renderTrace();
                });
            }
        };
        window.addEventListener('resize', resizeHandler);
        traceState._resizeHandler = resizeHandler;

        function updateFrameSelection() {
            const items = document.querySelectorAll('.trace-frame-item');
            items.forEach((el, idx) => {
                el.classList.toggle('active', idx === traceState.currentFrame);
            });
            const activeItem = document.querySelector('.trace-frame-item.active');
            const container = document.getElementById('trace-frames-container');
            if (activeItem && container) {
                activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            }
        }

        // Автозагрузка из основной GIF при открытии
        if (state.frames && state.frames.length > 0) {
            setTimeout(loadTraceFromMainGif, 100);
        }

        showStatus('✅ Trace panel opened. Load external GIF or use Main GIF.');
    },

    closeTracePanel: function() {
        const panel = document.getElementById('trace-panel');
        const traceCanvas = document.getElementById('trace-render-canvas');

        if (window._traceState) {
            if (window._traceState.animationId) {
                cancelAnimationFrame(window._traceState.animationId);
                window._traceState.animationId = null;
            }
            if (window._traceState._resizeHandler) {
                window.removeEventListener('resize', window._traceState._resizeHandler);
            }
            if (window._traceState._mainCanvasObserver) {
                window._traceState._mainCanvasObserver.disconnect();
            }
            if (window._traceState._styleElement) {
                window._traceState._styleElement.remove();
            }
        }

        if (panel) panel.remove();
        if (traceCanvas) traceCanvas.remove();

        const traceBtn = document.getElementById('gif-trace-btn');
        if (traceBtn) traceBtn.style.borderColor = '#313244';

        window._traceState = null;
    },

    _updateTraceUI: function(traceState, renderFn) {
        const frameCount = document.getElementById('trace-frame-count');
        const container = document.getElementById('trace-frames-container');

        if (frameCount) frameCount.textContent = traceState.frames.length;

        if (container) {
            container.innerHTML = '';

            traceState.frames.forEach((frame, idx) => {
                const div = document.createElement('div');
                div.className = 'trace-frame-item' + (idx === traceState.currentFrame ? ' active' : '');

                const previewCanvas = document.createElement('canvas');
                previewCanvas.width = 48;
                previewCanvas.height = 48;
                const previewCtx = previewCanvas.getContext('2d');
                try {
                    const imgData = new ImageData(frame.data, traceState.width, traceState.height);
                    const tempCanvas = document.createElement('canvas');
                    tempCanvas.width = traceState.width;
                    tempCanvas.height = traceState.height;
                    const tempCtx = tempCanvas.getContext('2d');
                    tempCtx.putImageData(imgData, 0, 0);
                    previewCtx.imageSmoothingEnabled = false;
                    previewCtx.drawImage(tempCanvas, 0, 0, traceState.width, traceState.height, 0, 0, 48, 48);
                } catch(e) {
                    console.warn('[Trace] Preview render error:', e);
                }

                div.appendChild(previewCanvas);

                const label = document.createElement('span');
                label.className = 'trace-frame-label';
                label.textContent = `#${idx + 1}`;
                div.appendChild(label);

                div.addEventListener('click', function() {
                    traceState.currentFrame = idx;
                    renderFn();
                    document.querySelectorAll('.trace-frame-item').forEach(el => el.classList.remove('active'));
                    this.classList.add('active');
                });

                container.appendChild(div);
            });
        }
    },

    addTraceButton: function() {
        const checkInterval = setInterval(() => {
            const modal = document.getElementById('gif-editor-modal');
            if (!modal) return;

            const toolbar = modal.querySelector('div[style*="padding: 8px 16px;"]') ||
                modal.querySelector('div[style*="padding: 8px"]');
            if (toolbar && !document.getElementById('gif-trace-btn')) {
                clearInterval(checkInterval);

                const traceBtn = document.createElement('button');
                traceBtn.id = 'gif-trace-btn';
                traceBtn.style.cssText = `
                padding: 6px 14px;
                background: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 8px;
                color: #cdd6f4;
                cursor: pointer;
                font-size: 13px;
                transition: all 0.2s;
                margin-left: 4px;
            `;
                traceBtn.innerHTML = '🎯 Trace';
                traceBtn.title = 'Open trace panel - load external GIF or use main';

                traceBtn.addEventListener('click', function() {
                    const panel = document.getElementById('trace-panel');
                    if (panel) {
                        PonyEditor.closeTracePanel();
                        this.style.borderColor = '#313244';
                        return;
                    }
                    this.style.borderColor = '#cba6f7';
                    PonyEditor.showTracePanel();
                });

                const saveBtn = document.getElementById('gif-save');
                if (saveBtn) {
                    saveBtn.parentNode.insertBefore(traceBtn, saveBtn);
                } else {
                    toolbar.appendChild(traceBtn);
                }

                console.log('[Trace] Button added to GIF editor');
            }
        }, 500);

        setTimeout(() => clearInterval(checkInterval), 30000);
    }
};

// ============================================================
// ОСТАЛЬНОЙ КОД (GifEditorStateManager, showInlineGifEditor, initGifEditor, resizeGif)
// ============================================================

// Глобальное состояние GIF редактора
window.GifEditorState = null;

// === КЛАСС ДЛЯ УПРАВЛЕНИЯ СОСТОЯНИЕМ GIF РЕДАКТОРА ===
class GifEditorStateManager {
    constructor(ponyName, spriteName, modal) {
        this.ponyName = ponyName;
        this.spriteName = spriteName;
        this.modal = modal;
        this.frames = [];
        this.currentFrame = 0;
        this.width = 128;
        this.height = 128;
        this.zoom = 1;
        this.tool = 'pencil';
        this.currentColor = { r: 203, g: 166, b: 247, a: 255 };
        this.currentHue = 260;
        this.previewInterval = null;
        this.playSpeed = 1.0;
        this.hasChanges = false;
        this.isLoading = false;
        this.isPickingColor = false;
        this.isDrawing = false;
        this.pipetteActive = false;
        this.resizeHandler = null;
        this.eventListeners = [];
        this.cleanupFunctions = [];
    }

    addEventListener(element, event, handler) {
        element.addEventListener(event, handler);
        this.eventListeners.push({ element, event, handler });
    }

    cleanup() {
        if (this.previewInterval) {
            clearInterval(this.previewInterval);
            this.previewInterval = null;
        }

        this.eventListeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });
        this.eventListeners = [];

        if (this.resizeHandler) {
            window.removeEventListener('resize', this.resizeHandler);
            this.resizeHandler = null;
        }

        if (window.GifEditorState === this) {
            window.GifEditorState = null;
        }
    }

    getCurrentFrameData() {
        if (!this.frames[this.currentFrame]) return null;
        return this.frames[this.currentFrame];
    }

    setFrameData(frameIndex, data) {
        if (frameIndex >= 0 && frameIndex < this.frames.length) {
            this.frames[frameIndex].data = data;
            this.hasChanges = true;
        }
    }

    addFrame(data, delay = 10) {
        this.frames.push({ data, delay });
        this.hasChanges = true;
    }

    removeFrame(index) {
        if (this.frames.length > 1 && index >= 0 && index < this.frames.length) {
            this.frames.splice(index, 1);
            if (this.currentFrame >= this.frames.length) {
                this.currentFrame = this.frames.length - 1;
            }
            this.hasChanges = true;
        }
    }

    duplicateFrame(index) {
        if (index >= 0 && index < this.frames.length) {
            const frame = this.frames[index];
            const newData = new Uint8ClampedArray(frame.data.length);
            newData.set(frame.data);
            this.frames.splice(index + 1, 0, { data: newData, delay: frame.delay });
            this.hasChanges = true;
        }
    }

    clearFrame(index) {
        if (index >= 0 && index < this.frames.length) {
            this.frames[index].data.fill(0);
            this.hasChanges = true;
        }
    }

    setFrameDelay(index, delay) {
        if (index >= 0 && index < this.frames.length) {
            this.frames[index].delay = Math.max(1, parseInt(delay) || 10);
            this.hasChanges = true;
        }
    }

    getFrameDelay(index) {
        if (index >= 0 && index < this.frames.length) {
            return (this.frames[index].delay || 10) * 10 / this.playSpeed;
        }
        return 100;
    }

    loadGif(gifData) {
        console.log('[GIF] loadGif called with data:', gifData ? 'yes' : 'no');
        console.log('[GIF] frames count:', gifData?.frames?.length);

        if (this.isLoading) return;
        this.isLoading = true;

        if (this.previewInterval) {
            clearInterval(this.previewInterval);
            this.previewInterval = null;
        }

        if (!gifData || !gifData.frames || gifData.frames.length === 0) {
            console.log('[GIF] No frames, creating empty');
            this.createEmptyGif();
            this.isLoading = false;
            return;
        }

        this.width = gifData.width || 128;
        this.height = gifData.height || 128;
        this.frames = [];

        console.log('[GIF] Processing', gifData.frames.length, 'frames, size:', this.width, 'x', this.height);

        for (let i = 0; i < gifData.frames.length; i++) {
            const srcFrame = gifData.frames[i];
            let byteData;

            if (srcFrame.data instanceof Uint8Array || srcFrame.data instanceof Uint8ClampedArray) {
                byteData = new Uint8ClampedArray(srcFrame.data);
            } else if (Array.isArray(srcFrame.data)) {
                byteData = new Uint8ClampedArray(srcFrame.data);
            } else {
                console.warn('[GIF] Frame', i, 'has unknown data type');
                continue;
            }

            const expectedSize = this.width * this.height * 4;

            if (byteData.length !== expectedSize) {
                console.warn('[GIF] Frame', i, 'size mismatch:', byteData.length, 'vs', expectedSize);
                if (byteData.length === this.width * this.height) {
                    const converted = new Uint8ClampedArray(expectedSize);
                    for (let j = 0; j < byteData.length; j++) {
                        const val = byteData[j];
                        converted[j*4] = val;
                        converted[j*4+1] = val;
                        converted[j*4+2] = val;
                        converted[j*4+3] = 255;
                    }
                    byteData = converted;
                } else {
                    continue;
                }
            }

            this.frames.push({
                data: byteData,
                delay: srcFrame.delay || 10
            });
        }

        if (this.frames.length === 0) {
            console.log('[GIF] No valid frames, creating empty');
            this.createEmptyGif();
            this.isLoading = false;
            return;
        }

        this.currentFrame = 0;
        this.drawCanvas();
        this.updateTimeline();
        const statusEl = document.getElementById('gif-status');
        if (statusEl) statusEl.textContent = `Loaded ${this.frames.length} frames, ${this.width}x${this.height}`;
        this.isLoading = false;
    }

    createEmptyGif() {
        this.width = 128;
        this.height = 128;
        this.frames = [];
        for (let i = 0; i < 2; i++) {
            const data = new Uint8ClampedArray(this.width * this.height * 4);
            for (let j = 0; j < data.length; j += 4) {
                data[j] = 255; data[j+1] = 192; data[j+2] = 203; data[j+3] = 255;
            }
            this.frames.push({ data, delay: 10 });
        }
        this.currentFrame = 0;
        this.drawCanvas();
        this.updateTimeline();
        const statusEl = document.getElementById('gif-status');
        if (statusEl) statusEl.textContent = `New GIF: ${this.frames.length} frames, ${this.width}x${this.height}`;
    }

    drawCanvas() {
        if (!this.frames[this.currentFrame]) return;

        const canvas = document.getElementById('gif-main-canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const frame = this.frames[this.currentFrame];
        const displayWidth = this.width * this.zoom;
        const displayHeight = this.height * this.zoom;

        if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
            canvas.width = displayWidth;
            canvas.height = displayHeight;
            canvas.style.width = displayWidth + 'px';
            canvas.style.height = displayHeight + 'px';
            canvas.style.imageRendering = 'crisp-edges';
            canvas.style.imageRendering = 'pixelated';
        }

        ctx.clearRect(0, 0, displayWidth, displayHeight);

        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = this.width;
        tempCanvas.height = this.height;
        const tempCtx = tempCanvas.getContext('2d');
        try {
            const imgData = new ImageData(frame.data, this.width, this.height);
            tempCtx.putImageData(imgData, 0, 0);
            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(tempCanvas, 0, 0, this.width, this.height, 0, 0, displayWidth, displayHeight);
        } catch(e) {
            console.warn('[Draw] Error drawing frame:', e);
        }

        const zoomLevel = document.getElementById('gif-zoom-level');
        if (zoomLevel) zoomLevel.textContent = Math.round(this.zoom * 100) + '%';

        const delayInput = document.getElementById('gif-frame-delay');
        if (delayInput && this.frames[this.currentFrame]) {
            delayInput.value = this.frames[this.currentFrame].delay;
        }

        // Обновляем трейс после отрисовки
        if (window._traceState && window._traceState.loaded) {
            // Синхронизируем текущий кадр трейса с основным
            if (window._traceState.frames.length > 0) {
                window._traceState.currentFrame = this.currentFrame % window._traceState.frames.length;
                if (!window._traceState._renderPending) {
                    window._traceState._renderPending = true;
                    requestAnimationFrame(() => {
                        window._traceState._renderPending = false;
                        if (window._traceState && window._traceState.loaded) {
                            renderTrace();
                        }
                    });
                }
            }
        }
    }

    updateTimeline() {
        const timeline = document.getElementById('gif-timeline');
        if (!timeline) return;

        timeline.innerHTML = '';
        const self = this;
        this.frames.forEach((frame, idx) => {
            const div = document.createElement('div');
            div.style.cssText = `width: 90px; height: 105px; background: #11111b; border: 2px solid ${idx === self.currentFrame ? '#cba6f7' : '#313244'}; border-radius: 8px; cursor: pointer; display: flex; flex-direction: column; align-items: center; padding: 8px; flex-shrink: 0;`;

            const previewCanvas = document.createElement('canvas');
            previewCanvas.width = 72;
            previewCanvas.height = 72;
            const previewCtx = previewCanvas.getContext('2d');
            try {
                const imgData = new ImageData(frame.data, self.width, self.height);
                previewCtx.putImageData(imgData, 0, 0);
            } catch(e) {}

            div.appendChild(previewCanvas);

            const label = document.createElement('span');
            label.textContent = `${idx+1} | ${frame.delay}cs`;
            label.style.fontSize = '10px';
            label.style.marginTop = '6px';
            div.appendChild(label);

            div.addEventListener('click', function() {
                if (self.previewInterval) {
                    clearInterval(self.previewInterval);
                    self.previewInterval = null;
                    const previewBtn = document.getElementById('gif-preview');
                    if (previewBtn) previewBtn.textContent = '▶️ Preview';
                }
                self.currentFrame = idx;
                self.drawCanvas();
                self.updateTimeline();
            });
            timeline.appendChild(div);
        });
    }
}

// Функция для открытия редактора GIF
function showInlineGifEditor(ponyName, spriteName) {
    console.log('[GIF] Opening inline editor for:', ponyName, spriteName);

    const existingModal = document.getElementById('gif-editor-modal');
    if (existingModal) {
        if (window.GifEditorState && window.GifEditorState.previewInterval) {
            clearInterval(window.GifEditorState.previewInterval);
        }
        if (window.GifEditorState) {
            window.GifEditorState.cleanup();
        }
        existingModal.remove();
        window.GifEditorState = null;
    }

    const modal = document.createElement('div');
    modal.id = 'gif-editor-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.95);
        z-index: 20000;
        display: flex;
        flex-direction: column;
    `;

    modal.innerHTML = `
        <div style="padding: 12px 20px; background: #181825; border-bottom: 1px solid #313244; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0;">
            <div>
                <span style="font-size: 20px; font-weight: bold;">🎨 GIF Editor</span>
                <span style="color: #a6adc8; margin-left: 16px; font-size: 14px;">${escapeHtml(ponyName)} / ${escapeHtml(spriteName)}</span>
            </div>
            <button id="gif-editor-close" style="background: none; border: none; color: #f38ba8; font-size: 28px; cursor: pointer; padding: 4px 12px;">✕</button>
        </div>
        
        <div style="padding: 8px 16px; background: #11111b; border-bottom: 1px solid #313244; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; flex-shrink: 0;">
            <button id="gif-tool-pencil" class="gif-tool-btn active" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">✏️ Pencil</button>
            <button id="gif-tool-eraser" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">🧽 Eraser</button>
            <button id="gif-tool-fill" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">🪣 Fill</button>
            <button id="gif-tool-smooth" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">✨ Smooth Edges</button>
            
            <div style="width: 1px; height: 28px; background: #313244;"></div>
            
            <button id="gif-resize-canvas" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">📏 Resize Canvas</button>
            <button id="gif-tween-frames" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">🔄 Tween Frames</button>
            <button id="gif-smooth-animation" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">🎞️ Smooth Anim</button>
            
            <div style="width: 1px; height: 28px; background: #313244;"></div>
            
            <button id="gif-preview" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">▶️ Preview</button>
            <button id="gif-save" style="padding: 6px 14px; background: #a6e3a1; border: none; border-radius: 8px; color: #1e1e2e; cursor: pointer; font-weight: bold; font-size: 13px;">💾 Save</button>
            
            <div style="display: flex; align-items: center; gap: 6px; background: #1e1e2e; padding: 3px 10px; border-radius: 20px; border: 1px solid #313244;">
                <span style="font-size: 11px; color: #a6adc8;">-</span>
                <input type="range" id="gif-speed-slider" min="0.25" max="4" step="0.05" value="1" style="width: 90px; cursor: pointer; height: 4px;">
                <span style="font-size: 11px; color: #a6adc8;">+</span>
                <span id="gif-speed-value" style="font-size: 10px; color: #cba6f7; min-width: 40px; font-family: monospace;">1.00x</span>
            </div>
            
            <div style="flex:1"></div>
            
            <div style="position: relative;">
                <button id="gif-color-btn" style="padding: 6px 14px; background: #cba6f7; border: none; border-radius: 8px; color: #1e1e2e; cursor: pointer; display: flex; align-items: center; gap: 8px; font-weight: bold; font-size: 13px;">
                    <span id="gif-color-preview-mini" style="display: inline-block; width: 16px; height: 16px; border-radius: 4px; background: #cba6f7;"></span>
                    🎨 Color
                </button>
                
                <div id="gif-color-dropdown" style="display: none; position: absolute; right: 0; top: 100%; margin-top: 10px; background: #1e1e2e; border: 1px solid #313244; border-radius: 16px; padding: 16px; width: 700px; height: 400px; z-index: 20001; box-shadow: 0 12px 40px rgba(0,0,0,0.6); display: flex; flex-direction: column;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-shrink: 0;">
                        <div style="font-size: 16px; font-weight: bold; color: #cdd6f4;">🎨 Color Picker</div>
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <div id="gif-current-color-preview" style="width: 48px; height: 48px; border-radius: 8px; border: 2px solid #313244; background: #cba6f7;"></div>
                            <div>
                                <div style="font-size: 12px; font-weight: bold; color: #cdd6f4;"><span id="gif-current-rgb">RGB(203,166,247)</span></div>
                                <div style="font-size: 11px; color: #a6adc8;"><span id="gif-current-hex">#CBA6F7</span></div>
                            </div>
                        </div>
                        <button id="gif-pipette-btn" style="background: #313244; border: none; border-radius: 8px; padding: 8px 12px; cursor: pointer; font-size: 13px; color: #cdd6f4; display: flex; align-items: center; gap: 6px;">🔍 Pipette</button>
                    </div>
                    
                    <div style="display: flex; gap: 16px; flex: 1; min-height: 0;">
                        <div style="flex: 2;">
                            <canvas id="gif-color-square" width="380" height="240" style="width: 100%; height: auto; border-radius: 10px; border: 1px solid #313244; cursor: crosshair; background: #11111b;"></canvas>
                        </div>
                        <div style="flex: 1.2; display: flex; flex-direction: column; gap: 12px;">
                            <div>
                                <div style="font-size: 11px; color: #a6adc8; margin-bottom: 4px;">🌈 Hue</div>
                                <input type="range" id="gif-hue-slider" min="0" max="360" value="260" style="width: 100%;">
                            </div>
                            <div>
                                <div style="font-size: 11px; color: #a6adc8; margin-bottom: 4px;">🎭 Alpha <span id="gif-alpha-value" style="color: #cba6f7;">255</span></div>
                                <input type="range" id="gif-alpha-slider" min="0" max="255" value="255" style="width: 100%;">
                            </div>
                            <div style="height: 1px; background: #313244;"></div>
                            <div>
                                <div style="font-size: 11px; color: #a6adc8; margin-bottom: 4px;">🎨 RGBA</div>
                                <input type="text" id="gif-rgba-input" value="rgba(203,166,247,1)" style="width:100%; background:#11111b; border:1px solid #313244; border-radius: 8px; padding: 6px 8px; color:#cdd6f4; font-size: 11px; font-family: monospace;">
                            </div>
                            <div>
                                <div style="font-size: 11px; color: #a6adc8; margin-bottom: 4px;">📋 HEX</div>
                                <input type="text" id="gif-hex-input" value="#CBA6F7" maxlength="7" style="width:100%; background:#11111b; border:1px solid #313244; border-radius: 8px; padding: 6px 8px; color:#cdd6f4; font-size: 11px; font-family: monospace;">
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div style="display: flex; gap: 5px; align-items: center; background: #1e1e2e; padding: 3px 8px; border-radius: 20px; border: 1px solid #313244;">
                <span style="font-size: 11px; color: #a6adc8;">🔍</span>
                <button id="gif-zoom-out" style="padding: 3px 6px; background: #313244; border: none; border-radius: 5px; cursor: pointer; font-size: 12px; color: #cdd6f4;">−</button>
                <span id="gif-zoom-level" style="min-width: 45px; text-align: center; font-size: 11px; font-family: monospace; color: #cba6f7;">100%</span>
                <button id="gif-zoom-in" style="padding: 3px 6px; background: #313244; border: none; border-radius: 5px; cursor: pointer; font-size: 12px; color: #cdd6f4;">+</button>
                <div style="width: 1px; height: 18px; background: #313244;"></div>
                <button id="gif-zoom-reset" style="padding: 3px 6px; background: #313244; border: none; border-radius: 5px; cursor: pointer; font-size: 10px; color: #cdd6f4;">1:1</button>
                <button id="gif-zoom-fit" style="padding: 3px 6px; background: #313244; border: none; border-radius: 5px; cursor: pointer; font-size: 10px; color: #cdd6f4;">Fit</button>
            </div>
            
            <div style="display: flex; gap: 6px; align-items: center;"> 
                <span style="font-size: 11px; color: #a6adc8;">⏱️ Delay:</span>
                <input type="number" id="gif-frame-delay" value="10" min="1" max="100" style="width: 55px; background: #1e1e2e; border: 1px solid #313244; border-radius: 5px; padding: 4px; color: #cdd6f4; text-align: center; font-size: 12px;">
                <span style="font-size: 11px;">cs</span>
            </div>
            
            <button id="gif-trace-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px; transition: all 0.2s;">🎯 Trace</button>
        </div>
        
        <div style="padding: 8px 16px; background: #0f0f17; border-bottom: 1px solid #313244; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; flex-shrink: 0;">
            <button id="gif-clear-frame" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">🗑️ Clear Frame</button>
            <button id="gif-add-frame" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">➕ Add Frame</button>
            <button id="gif-duplicate-frame" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">📋 Duplicate Frame</button>
            <button id="gif-delete-frame" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">➖ Delete Frame</button>
        </div>
        
        <div style="flex: 1; display: flex; justify-content: center; align-items: center; background: #0a0a0f; overflow: auto; min-height: 0; padding: 20px; position: relative;" class="gif-canvas-wrapper">
            <canvas id="gif-main-canvas" style="image-rendering: crisp-edges; image-rendering: pixelated; border: 2px solid #313244; border-radius: 8px; cursor: crosshair; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"></canvas>
        </div>
        
        <div style="height: 130px; background: #181825; border-top: 1px solid #313244; padding: 10px; overflow-x: auto; flex-shrink: 0;">
            <div id="gif-timeline" style="display: flex; gap: 10px; height: 100%;"></div>
        </div>
        
        <div style="padding: 6px 16px; font-size: 12px; color: #a6adc8; background: #11111b; border-top: 1px solid #313244; flex-shrink: 0;">
            <span id="gif-status">Loading GIF...</span>
        </div>
    `;

    document.body.appendChild(modal);

    const stateManager = new GifEditorStateManager(ponyName, spriteName, modal);
    window.GifEditorState = stateManager;

    // Добавляем обработчик для кнопки Trace
    const traceBtn = document.getElementById('gif-trace-btn');
    if (traceBtn) {
        traceBtn.addEventListener('click', function() {
            const panel = document.getElementById('trace-panel');
            if (panel) {
                PonyEditor.closeTracePanel();
                this.style.borderColor = '#313244';
                return;
            }
            this.style.borderColor = '#cba6f7';
            PonyEditor.showTracePanel();
        });
    }

    // Инициализируем редактор
    initGifEditor(stateManager);
}

// === ИНИЦИАЛИЗАТОР GIF РЕДАКТОРА ===
function initGifEditor(stateManager) {
    console.log('[GIF] initGifEditor for:', stateManager.ponyName, stateManager.spriteName);

    const modal = stateManager.modal;
    const canvas = document.getElementById('gif-main-canvas');
    const statusEl = document.getElementById('gif-status');
    const delayInput = document.getElementById('gif-frame-delay');
    const currentColorPreview = document.getElementById('gif-current-color-preview');
    const currentRgbSpan = document.getElementById('gif-current-rgb');
    const currentHexSpan = document.getElementById('gif-current-hex');
    const colorPreviewMini = document.getElementById('gif-color-preview-mini');
    const colorBtn = document.getElementById('gif-color-btn');
    const colorDropdown = document.getElementById('gif-color-dropdown');
    const colorSquare = document.getElementById('gif-color-square');
    const hueSlider = document.getElementById('gif-hue-slider');
    const alphaSlider = document.getElementById('gif-alpha-slider');
    const alphaValue = document.getElementById('gif-alpha-value');
    const hexInput = document.getElementById('gif-hex-input');
    const rgbaInput = document.getElementById('gif-rgba-input');
    const speedSlider = document.getElementById('gif-speed-slider');
    const speedValue = document.getElementById('gif-speed-value');
    const previewBtn = document.getElementById('gif-preview');

    if (!canvas) {
        console.error('[GIF] Canvas not found!');
        return;
    }

    const ctx = canvas.getContext('2d');
    let isDrawingSquare = false;

    // === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
    function getPixelFromMouseEvent(e) {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        const pixelX = Math.floor((mouseX / canvas.width) * stateManager.width);
        const pixelY = Math.floor((mouseY / canvas.height) * stateManager.height);
        return {
            x: Math.max(0, Math.min(stateManager.width - 1, pixelX)),
            y: Math.max(0, Math.min(stateManager.height - 1, pixelY))
        };
    }

    function setPixelAt(px, py) {
        if (!stateManager.frames[stateManager.currentFrame] || stateManager.isPickingColor) return;
        if (px < 0 || px >= stateManager.width || py < 0 || py >= stateManager.height) return;

        const frame = stateManager.frames[stateManager.currentFrame];
        const idx = (py * stateManager.width + px) * 4;

        if (stateManager.tool === 'eraser') {
            frame.data[idx] = 0;
            frame.data[idx + 1] = 0;
            frame.data[idx + 2] = 0;
            frame.data[idx + 3] = 0;
        } else if (stateManager.tool === 'pencil') {
            const targetAlpha = stateManager.currentColor.a / 255;
            const currentAlpha = frame.data[idx + 3] / 255;
            const resultAlpha = targetAlpha + currentAlpha * (1 - targetAlpha);

            if (resultAlpha > 0) {
                frame.data[idx] = Math.round(
                    (stateManager.currentColor.r * targetAlpha + frame.data[idx] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[idx + 1] = Math.round(
                    (stateManager.currentColor.g * targetAlpha + frame.data[idx + 1] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[idx + 2] = Math.round(
                    (stateManager.currentColor.b * targetAlpha + frame.data[idx + 2] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[idx + 3] = Math.round(resultAlpha * 255);
            } else {
                frame.data[idx] = 0;
                frame.data[idx + 1] = 0;
                frame.data[idx + 2] = 0;
                frame.data[idx + 3] = 0;
            }
        }

        stateManager.hasChanges = true;
        stateManager.drawCanvas();
        stateManager.updateTimeline();
    }

    function floodFillAt(px, py) {
        if (!stateManager.frames[stateManager.currentFrame] || stateManager.isPickingColor) return;
        if (px < 0 || px >= stateManager.width || py < 0 || py >= stateManager.height) return;

        const frame = stateManager.frames[stateManager.currentFrame];
        const idx = (py * stateManager.width + px) * 4;

        const target = {
            r: frame.data[idx],
            g: frame.data[idx + 1],
            b: frame.data[idx + 2],
            a: frame.data[idx + 3]
        };

        if (target.r === stateManager.currentColor.r &&
            target.g === stateManager.currentColor.g &&
            target.b === stateManager.currentColor.b &&
            target.a === stateManager.currentColor.a) return;

        const queue = [{ x: px, y: py }];
        const visited = new Set();
        let processed = 0;
        const maxProcessed = stateManager.width * stateManager.height;

        while (queue.length > 0 && processed < maxProcessed) {
            const { x: cx, y: cy } = queue.shift();
            const key = `${cx},${cy}`;
            if (visited.has(key)) continue;
            visited.add(key);
            processed++;

            const cidx = (cy * stateManager.width + cx) * 4;

            if (Math.abs(frame.data[cidx] - target.r) > 5 ||
                Math.abs(frame.data[cidx + 1] - target.g) > 5 ||
                Math.abs(frame.data[cidx + 2] - target.b) > 5 ||
                Math.abs(frame.data[cidx + 3] - target.a) > 10) continue;

            const targetAlpha = stateManager.currentColor.a / 255;
            const currentAlpha = frame.data[cidx + 3] / 255;
            const resultAlpha = targetAlpha + currentAlpha * (1 - targetAlpha);

            if (resultAlpha > 0) {
                frame.data[cidx] = Math.round(
                    (stateManager.currentColor.r * targetAlpha + frame.data[cidx] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[cidx + 1] = Math.round(
                    (stateManager.currentColor.g * targetAlpha + frame.data[cidx + 1] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[cidx + 2] = Math.round(
                    (stateManager.currentColor.b * targetAlpha + frame.data[cidx + 2] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[cidx + 3] = Math.round(resultAlpha * 255);
            }

            if (cx > 0) queue.push({ x: cx - 1, y: cy });
            if (cx < stateManager.width - 1) queue.push({ x: cx + 1, y: cy });
            if (cy > 0) queue.push({ x: cx, y: cy - 1 });
            if (cy < stateManager.height - 1) queue.push({ x: cx, y: cy + 1 });
        }

        stateManager.hasChanges = true;
        stateManager.drawCanvas();
        stateManager.updateTimeline();
    }

    function smoothEdges() {
        if (!stateManager.frames[stateManager.currentFrame]) return;

        const frame = stateManager.frames[stateManager.currentFrame];
        const width = stateManager.width;
        const height = stateManager.height;
        const data = frame.data;

        const original = new Uint8ClampedArray(data);
        const alphaThreshold = 30;

        function getPixel(x, y, source) {
            if (x < 0 || x >= width || y < 0 || y >= height) return null;
            const idx = (y * width + x) * 4;
            return {
                r: source[idx],
                g: source[idx + 1],
                b: source[idx + 2],
                a: source[idx + 3]
            };
        }

        function isSolid(x, y, source) {
            const p = getPixel(x, y, source);
            return p && p.a >= alphaThreshold;
        }

        function getAverageColor(x, y, source) {
            let r = 0, g = 0, b = 0, a = 0;
            let count = 0;

            for (let dy = -1; dy <= 1; dy++) {
                for (let dx = -1; dx <= 1; dx++) {
                    const p = getPixel(x + dx, y + dy, source);
                    if (p && p.a >= alphaThreshold) {
                        r += p.r;
                        g += p.g;
                        b += p.b;
                        a += p.a;
                        count++;
                    }
                }
            }

            if (count > 0) {
                return {
                    r: Math.round(r / count),
                    g: Math.round(g / count),
                    b: Math.round(b / count),
                    a: 255
                };
            }
            return null;
        }

        function setPixelColor(x, y, color, targetData) {
            if (x < 0 || x >= width || y < 0 || y >= height) return;
            const idx = (y * width + x) * 4;
            if (color) {
                targetData[idx] = color.r;
                targetData[idx + 1] = color.g;
                targetData[idx + 2] = color.b;
                targetData[idx + 3] = color.a;
            }
        }

        const cornersToAdd = [];
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                if (!isSolid(x, y, original)) continue;
                const n = isSolid(x, y-1, original);
                const s = isSolid(x, y+1, original);
                const w = isSolid(x-1, y, original);
                const e = isSolid(x+1, y, original);
                const nw = isSolid(x-1, y-1, original);
                const ne = isSolid(x+1, y-1, original);
                const sw = isSolid(x-1, y+1, original);
                const se = isSolid(x+1, y+1, original);
                if (!n && !w && nw) cornersToAdd.push({ x: x-1, y: y-1 });
                if (!n && !e && ne) cornersToAdd.push({ x: x+1, y: y-1 });
                if (!s && !w && sw) cornersToAdd.push({ x: x-1, y: y+1 });
                if (!s && !e && se) cornersToAdd.push({ x: x+1, y: y+1 });
            }
        }
        for (const corner of cornersToAdd) {
            const avgColor = getAverageColor(corner.x, corner.y, original);
            if (avgColor) setPixelColor(corner.x, corner.y, avgColor, data);
        }

        const afterExternal = new Uint8ClampedArray(data);
        const pitsToFill = [];
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                if (isSolid(x, y, afterExternal)) continue;
                const n = isSolid(x, y-1, afterExternal);
                const s = isSolid(x, y+1, afterExternal);
                const w = isSolid(x-1, y, afterExternal);
                const e = isSolid(x+1, y, afterExternal);
                const nw = isSolid(x-1, y-1, afterExternal);
                const ne = isSolid(x+1, y-1, afterExternal);
                const sw = isSolid(x-1, y+1, afterExternal);
                const se = isSolid(x+1, y+1, afterExternal);
                let solidCount = (n?1:0) + (s?1:0) + (w?1:0) + (e?1:0);
                let diagonalSolidCount = (nw?1:0) + (ne?1:0) + (sw?1:0) + (se?1:0);
                const isInnerCorner = (n && w && !nw) || (n && e && !ne) || (s && w && !sw) || (s && e && !se);
                const isDiagonalHole = (n && w && s && e && !nw && !ne && !sw && !se);
                const isPocket = (solidCount >= 2 && diagonalSolidCount >= 1 && !isSolid(x, y, afterExternal));
                if (isInnerCorner || isDiagonalHole || isPocket) pitsToFill.push({ x, y });
            }
        }
        for (const pit of pitsToFill) {
            const avgColor = getAverageColor(pit.x, pit.y, afterExternal);
            if (avgColor) setPixelColor(pit.x, pit.y, avgColor, data);
        }

        const afterInternal = new Uint8ClampedArray(data);
        const spikesToRemove = [];
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                if (!isSolid(x, y, afterInternal)) continue;
                let neighbors = 0;
                for (let dy = -1; dy <= 1; dy++) {
                    for (let dx = -1; dx <= 1; dx++) {
                        if (dx === 0 && dy === 0) continue;
                        if (isSolid(x + dx, y + dy, afterInternal)) neighbors++;
                    }
                }
                if (neighbors < 2) spikesToRemove.push({ x, y });
            }
        }
        for (const spike of spikesToRemove) {
            setPixelColor(spike.x, spike.y, null, data);
            const idx = (spike.y * width + spike.x) * 4;
            data[idx] = 0; data[idx+1] = 0; data[idx+2] = 0; data[idx+3] = 0;
        }

        stateManager.hasChanges = true;
        stateManager.drawCanvas();
        stateManager.updateTimeline();

        if (statusEl) {
            statusEl.textContent = `✓ Smooth complete`;
            setTimeout(() => {
                if (statusEl.textContent === `✓ Smooth complete`) {
                    statusEl.textContent = `Frame ${stateManager.currentFrame+1}/${stateManager.frames.length} | Delay: ${stateManager.frames[stateManager.currentFrame]?.delay || 10}cs | ${stateManager.width}x${stateManager.height}`;
                }
            }, 3000);
        }
    }

    // === ЦВЕТОВЫЕ ФУНКЦИИ ===
    function hslToRgb(h, s, l) {
        h = h / 360;
        let r, g, b;
        if (s === 0) {
            r = g = b = l;
        } else {
            const hue2rgb = (p, q, t) => {
                if (t < 0) t += 1;
                if (t > 1) t -= 1;
                if (t < 1/6) return p + (q - p) * 6 * t;
                if (t < 1/2) return q;
                if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
                return p;
            };
            const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
            const p = 2 * l - q;
            r = hue2rgb(p, q, h + 1/3);
            g = hue2rgb(p, q, h);
            b = hue2rgb(p, q, h - 1/3);
        }
        return {
            r: Math.round(r * 255),
            g: Math.round(g * 255),
            b: Math.round(b * 255)
        };
    }

    function rgbToHex(r, g, b) {
        return '#' + [r, g, b].map(c => c.toString(16).padStart(2, '0')).join('').toUpperCase();
    }

    function updateCurrentColorDisplay() {
        const bgColor = `rgba(${stateManager.currentColor.r}, ${stateManager.currentColor.g}, ${stateManager.currentColor.b}, ${stateManager.currentColor.a / 255})`;
        if (currentColorPreview) currentColorPreview.style.backgroundColor = bgColor;
        if (colorPreviewMini) colorPreviewMini.style.backgroundColor = bgColor;
        if (currentRgbSpan) currentRgbSpan.textContent = `RGB(${stateManager.currentColor.r},${stateManager.currentColor.g},${stateManager.currentColor.b})`;
        const hex = rgbToHex(stateManager.currentColor.r, stateManager.currentColor.g, stateManager.currentColor.b);
        if (currentHexSpan) currentHexSpan.textContent = hex;
        if (hexInput) hexInput.value = hex;
        if (rgbaInput) rgbaInput.value = `rgba(${stateManager.currentColor.r},${stateManager.currentColor.g},${stateManager.currentColor.b},${(stateManager.currentColor.a/255).toFixed(2)})`;
        if (alphaSlider) alphaSlider.value = stateManager.currentColor.a;
        if (alphaValue) alphaValue.textContent = stateManager.currentColor.a;
    }

    function drawColorSquare() {
        if (!colorSquare) return;
        const ctxSquare = colorSquare.getContext('2d');
        const w = 380, h = 240;
        colorSquare.width = w;
        colorSquare.height = h;
        for (let x = 0; x < w; x++) {
            for (let y = 0; y < h; y++) {
                const sat = x / w;
                const light = 1 - (y / h);
                const rgb = hslToRgb(stateManager.currentHue, sat, light);
                ctxSquare.fillStyle = `rgb(${rgb.r},${rgb.g},${rgb.b})`;
                ctxSquare.fillRect(x, y, 1, 1);
            }
        }
    }

    // === ОБРАБОТЧИКИ СОБЫТИЙ ===
    // Tools
    document.getElementById('gif-tool-pencil')?.addEventListener('click', function() {
        stateManager.tool = 'pencil';
        document.querySelectorAll('.gif-tool-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
    });

    document.getElementById('gif-tool-eraser')?.addEventListener('click', function() {
        stateManager.tool = 'eraser';
        document.querySelectorAll('.gif-tool-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
    });

    document.getElementById('gif-tool-fill')?.addEventListener('click', function() {
        stateManager.tool = 'fill';
        document.querySelectorAll('.gif-tool-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
    });

    document.getElementById('gif-tool-smooth')?.addEventListener('click', function() {
        smoothEdges();
        this.classList.add('active');
        setTimeout(() => this.classList.remove('active'), 500);
    });

    // Zoom
    document.getElementById('gif-zoom-in')?.addEventListener('click', () => {
        stateManager.zoom = Math.min(8, stateManager.zoom + 0.25);
        stateManager.drawCanvas();
    });

    document.getElementById('gif-zoom-out')?.addEventListener('click', () => {
        stateManager.zoom = Math.max(0.25, stateManager.zoom - 0.25);
        stateManager.drawCanvas();
    });

    document.getElementById('gif-zoom-reset')?.addEventListener('click', () => {
        stateManager.zoom = 1;
        stateManager.drawCanvas();
    });

    document.getElementById('gif-zoom-fit')?.addEventListener('click', () => {
        const container = canvas.parentElement;
        if (container) {
            const containerWidth = container.clientWidth - 40;
            const containerHeight = container.clientHeight - 40;
            const fitZoom = Math.min(containerWidth / stateManager.width, containerHeight / stateManager.height, 4);
            stateManager.zoom = Math.max(0.25, fitZoom);
            stateManager.drawCanvas();
        }
    });

    // Canvas wheel zoom
    canvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (e.deltaY < 0) {
            stateManager.zoom = Math.min(8, stateManager.zoom + 0.1);
        } else {
            stateManager.zoom = Math.max(0.25, stateManager.zoom - 0.1);
        }
        stateManager.drawCanvas();
    });

    // Canvas drawing
    canvas.addEventListener('mousedown', (e) => {
        if (stateManager.isPickingColor) return;
        stateManager.isDrawing = true;
        e.preventDefault();
        const { x, y } = getPixelFromMouseEvent(e);
        if (stateManager.tool === 'fill') floodFillAt(x, y);
        else setPixelAt(x, y);
    });

    canvas.addEventListener('mousemove', (e) => {
        if (!stateManager.isDrawing || stateManager.tool === 'fill' || stateManager.isPickingColor) return;
        e.preventDefault();
        const { x, y } = getPixelFromMouseEvent(e);
        setPixelAt(x, y);
    });

    canvas.addEventListener('mouseup', () => {
        stateManager.isDrawing = false;
    });

    canvas.addEventListener('mouseleave', () => {
        stateManager.isDrawing = false;
    });

    // Frame operations
    document.getElementById('gif-clear-frame')?.addEventListener('click', () => {
        if (stateManager.frames[stateManager.currentFrame]) {
            stateManager.frames[stateManager.currentFrame].data.fill(0);
            stateManager.drawCanvas();
            stateManager.updateTimeline();
            stateManager.hasChanges = true;
        }
    });

    document.getElementById('gif-add-frame')?.addEventListener('click', () => {
        const newData = new Uint8ClampedArray(stateManager.width * stateManager.height * 4);
        for (let i = 3; i < newData.length; i+=4) newData[i] = 255;
        stateManager.addFrame(newData, 10);
        stateManager.currentFrame = stateManager.frames.length - 1;
        stateManager.drawCanvas();
        stateManager.updateTimeline();
    });

    document.getElementById('gif-duplicate-frame')?.addEventListener('click', () => {
        stateManager.duplicateFrame(stateManager.currentFrame);
        stateManager.currentFrame = Math.min(stateManager.currentFrame + 1, stateManager.frames.length - 1);
        stateManager.drawCanvas();
        stateManager.updateTimeline();
    });

    document.getElementById('gif-delete-frame')?.addEventListener('click', () => {
        stateManager.removeFrame(stateManager.currentFrame);
        stateManager.drawCanvas();
        stateManager.updateTimeline();
    });

    // Preview
    let previewInterval = null;

    function startPreview() {
        if (previewInterval) stopPreview();
        previewInterval = setInterval(() => {
            stateManager.currentFrame = (stateManager.currentFrame + 1) % stateManager.frames.length;
            stateManager.drawCanvas();
            stateManager.updateTimeline();
        }, stateManager.getFrameDelay(stateManager.currentFrame));
        previewBtn.textContent = '⏸️ Stop';
    }

    function stopPreview() {
        if (previewInterval) {
            clearInterval(previewInterval);
            previewInterval = null;
        }
        previewBtn.textContent = '▶️ Preview';
    }

    previewBtn?.addEventListener('click', () => {
        if (previewInterval) stopPreview();
        else startPreview();
        stateManager.previewInterval = previewInterval;
    });

    // Speed slider
    speedSlider?.addEventListener('input', (e) => {
        stateManager.playSpeed = parseFloat(e.target.value);
        speedValue.textContent = stateManager.playSpeed.toFixed(2) + 'x';
        if (previewInterval) {
            stopPreview();
            startPreview();
        }
    });

    // Delay input
    delayInput?.addEventListener('change', () => {
        if (stateManager.frames[stateManager.currentFrame]) {
            stateManager.setFrameDelay(stateManager.currentFrame, parseInt(delayInput.value));
            stateManager.updateTimeline();
        }
    });

    // Color picker
    colorBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        const isVisible = colorDropdown.style.display === 'flex';
        colorDropdown.style.display = isVisible ? 'none' : 'flex';
        if (!isVisible) {
            drawColorSquare();
            updateCurrentColorDisplay();
        }
    });

    document.addEventListener('click', (e) => {
        if (!colorBtn?.contains(e.target) && !colorDropdown?.contains(e.target)) {
            colorDropdown.style.display = 'none';
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && colorDropdown?.style.display === 'flex') {
            colorDropdown.style.display = 'none';
        }
    });

    colorSquare?.addEventListener('mousedown', (e) => {
        isDrawingSquare = true;
        const rect = colorSquare.getBoundingClientRect();
        const scaleX = colorSquare.width / rect.width;
        const scaleY = colorSquare.height / rect.height;
        let x = (e.clientX - rect.left) * scaleX;
        let y = (e.clientY - rect.top) * scaleY;
        x = Math.min(Math.max(0, x), colorSquare.width - 1);
        y = Math.min(Math.max(0, y), colorSquare.height - 1);
        const sat = x / colorSquare.width;
        const light = 1 - (y / colorSquare.height);
        const rgb = hslToRgb(stateManager.currentHue, sat, light);
        stateManager.currentColor = { r: rgb.r, g: rgb.g, b: rgb.b, a: stateManager.currentColor.a };
        updateCurrentColorDisplay();
    });

    colorSquare?.addEventListener('mousemove', (e) => {
        if (!isDrawingSquare) return;
        const rect = colorSquare.getBoundingClientRect();
        const scaleX = colorSquare.width / rect.width;
        const scaleY = colorSquare.height / rect.height;
        let x = (e.clientX - rect.left) * scaleX;
        let y = (e.clientY - rect.top) * scaleY;
        x = Math.min(Math.max(0, x), colorSquare.width - 1);
        y = Math.min(Math.max(0, y), colorSquare.height - 1);
        const sat = x / colorSquare.width;
        const light = 1 - (y / colorSquare.height);
        const rgb = hslToRgb(stateManager.currentHue, sat, light);
        stateManager.currentColor = { r: rgb.r, g: rgb.g, b: rgb.b, a: stateManager.currentColor.a };
        updateCurrentColorDisplay();
    });

    colorSquare?.addEventListener('mouseup', () => isDrawingSquare = false);

    hueSlider?.addEventListener('input', (e) => {
        stateManager.currentHue = parseInt(e.target.value);
        drawColorSquare();
    });

    alphaSlider?.addEventListener('input', (e) => {
        stateManager.currentColor.a = parseInt(e.target.value);
        updateCurrentColorDisplay();
    });

    hexInput?.addEventListener('change', () => {
        let hex = hexInput.value;
        if (!hex.startsWith('#')) hex = '#' + hex;
        if (/^#[0-9A-Fa-f]{6}$/.test(hex)) {
            const r = parseInt(hex.slice(1,3), 16);
            const g = parseInt(hex.slice(3,5), 16);
            const b = parseInt(hex.slice(5,7), 16);
            stateManager.currentColor = { r, g, b, a: stateManager.currentColor.a };
            updateCurrentColorDisplay();
        }
    });

    rgbaInput?.addEventListener('change', () => {
        const match = rgbaInput.value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([0-9.]+))?\)/);
        if (match) {
            const r = parseInt(match[1]);
            const g = parseInt(match[2]);
            const b = parseInt(match[3]);
            const a = match[4] ? Math.round(parseFloat(match[4]) * 255) : 255;
            stateManager.currentColor = { r, g, b, a };
            updateCurrentColorDisplay();
        }
    });

    // Pipette
    document.getElementById('gif-pipette-btn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        if (stateManager.pipetteActive) return;
        stateManager.pipetteActive = true;
        stateManager.isPickingColor = true;
        if (colorDropdown) colorDropdown.style.display = 'none';
        if (statusEl) statusEl.textContent = '🔍 Pipette active: Click on canvas to pick color, ESC to cancel';
        canvas.style.cursor = 'crosshair';

        const pipetteOverlay = document.createElement('div');
        pipetteOverlay.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: transparent; z-index: 20010; cursor: crosshair;';

        const pipetteLoupe = document.createElement('div');
        pipetteLoupe.style.cssText = 'position: fixed; width: 150px; height: 150px; border-radius: 75px; border: 2px solid #cba6f7; background: rgba(30,30,46,0.9); box-shadow: 0 0 20px rgba(0,0,0,0.5); pointer-events: none; z-index: 20011; overflow: hidden; backdrop-filter: blur(2px);';

        const loupeCanvas = document.createElement('canvas');
        loupeCanvas.width = 150;
        loupeCanvas.height = 150;
        loupeCanvas.style.width = '150px';
        loupeCanvas.style.height = '150px';
        loupeCanvas.style.imageRendering = 'crisp-edges';
        loupeCanvas.style.imageRendering = 'pixelated';
        pipetteLoupe.appendChild(loupeCanvas);

        const loupeInfo = document.createElement('div');
        loupeInfo.style.cssText = 'position: absolute; bottom: 5px; left: 5px; right: 5px; background: rgba(0,0,0,0.8); color: #cba6f7; font-size: 9px; text-align: center; border-radius: 4px; padding: 3px; font-family: monospace; font-weight: bold;';
        loupeInfo.id = 'pipette-loupe-info';
        pipetteLoupe.appendChild(loupeInfo);

        pipetteOverlay.appendChild(pipetteLoupe);
        document.body.appendChild(pipetteOverlay);

        const loupeCtx = loupeCanvas.getContext('2d');
        const loupeSize = 150;
        const sampleSize = 15;
        const pixelDrawSize = loupeSize / sampleSize;

        function updateLoupe(e) {
            if (!stateManager.isPickingColor) return;
            const x = e.clientX;
            const y = e.clientY;
            pipetteLoupe.style.left = (x - loupeSize/2) + 'px';
            pipetteLoupe.style.top = (y - loupeSize/2) + 'px';
            const rect = canvas.getBoundingClientRect();
            if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
                const canvasX = (x - rect.left) / canvas.width;
                const canvasY = (y - rect.top) / canvas.height;
                let px = Math.floor(canvasX * stateManager.width);
                let py = Math.floor(canvasY * stateManager.height);
                px = Math.max(0, Math.min(stateManager.width - 1, px));
                py = Math.max(0, Math.min(stateManager.height - 1, py));
                if (stateManager.frames[stateManager.currentFrame]) {
                    const frame = stateManager.frames[stateManager.currentFrame];
                    loupeCtx.clearRect(0, 0, loupeSize, loupeSize);
                    const cellSize = pixelDrawSize;
                    for (let i = 0; i < sampleSize; i++) {
                        for (let j = 0; j < sampleSize; j++) {
                            const isEven = (i + j) % 2 === 0;
                            loupeCtx.fillStyle = isEven ? '#2a2a3a' : '#1a1a2a';
                            loupeCtx.fillRect(i * cellSize, j * cellSize, cellSize, cellSize);
                        }
                    }
                    const offset = Math.floor(sampleSize / 2);
                    for (let dy = 0; dy < sampleSize; dy++) {
                        for (let dx = 0; dx < sampleSize; dx++) {
                            const sampleX = Math.max(0, Math.min(stateManager.width - 1, px + (dx - offset)));
                            const sampleY = Math.max(0, Math.min(stateManager.height - 1, py + (dy - offset)));
                            const idx = (sampleY * stateManager.width + sampleX) * 4;
                            const r = frame.data[idx];
                            const g = frame.data[idx+1];
                            const b = frame.data[idx+2];
                            const a = frame.data[idx+3];
                            const drawX = dx * pixelDrawSize;
                            const drawY = dy * pixelDrawSize;
                            if (a > 0) {
                                loupeCtx.fillStyle = `rgb(${r},${g},${b})`;
                                loupeCtx.fillRect(drawX, drawY, pixelDrawSize, pixelDrawSize);
                            }
                            if (dx === offset && dy === offset) {
                                loupeInfo.textContent = `RGB(${r},${g},${b}) A:${a}`;
                                loupeInfo.style.color = (r + g + b) < 384 ? '#cba6f7' : '#1e1e2e';
                            }
                        }
                    }
                    loupeCtx.beginPath();
                    loupeCtx.strokeStyle = '#cba6f7';
                    loupeCtx.lineWidth = 1;
                    for (let i = 0; i <= sampleSize; i++) {
                        const pos = i * pixelDrawSize;
                        loupeCtx.beginPath();
                        loupeCtx.moveTo(pos, 0);
                        loupeCtx.lineTo(pos, loupeSize);
                        loupeCtx.stroke();
                        loupeCtx.beginPath();
                        loupeCtx.moveTo(0, pos);
                        loupeCtx.lineTo(loupeSize, pos);
                        loupeCtx.stroke();
                    }
                    loupeCtx.strokeStyle = '#f38ba8';
                    loupeCtx.lineWidth = 2;
                    const centerX = offset * pixelDrawSize;
                    const centerY = offset * pixelDrawSize;
                    loupeCtx.strokeRect(centerX, centerY, pixelDrawSize, pixelDrawSize);
                }
            } else {
                loupeCtx.fillStyle = '#1e1e2e';
                loupeCtx.fillRect(0, 0, loupeSize, loupeSize);
                loupeInfo.textContent = 'Move to canvas';
                loupeInfo.style.color = '#a6adc8';
            }
        }

        function pickColor(e) {
            if (!stateManager.isPickingColor) return;
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX;
            const y = e.clientY;
            if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
                const canvasX = (x - rect.left) / canvas.width;
                const canvasY = (y - rect.top) / canvas.height;
                let px = Math.floor(canvasX * stateManager.width);
                let py = Math.floor(canvasY * stateManager.height);
                px = Math.max(0, Math.min(stateManager.width - 1, px));
                py = Math.max(0, Math.min(stateManager.height - 1, py));
                if (stateManager.frames[stateManager.currentFrame]) {
                    const frame = stateManager.frames[stateManager.currentFrame];
                    const idx = (py * stateManager.width + px) * 4;
                    stateManager.currentColor = {
                        r: frame.data[idx],
                        g: frame.data[idx+1],
                        b: frame.data[idx+2],
                        a: frame.data[idx+3]
                    };
                    updateCurrentColorDisplay();
                    if (statusEl) {
                        statusEl.textContent = `✓ Picked: rgba(${stateManager.currentColor.r},${stateManager.currentColor.g},${stateManager.currentColor.b},${stateManager.currentColor.a})`;
                    }
                }
            }
            stopPipette();
        }

        function stopPipette() {
            if (!stateManager.pipetteActive) return;
            stateManager.pipetteActive = false;
            stateManager.isPickingColor = false;
            if (pipetteOverlay) pipetteOverlay.remove();
            if (pipetteLoupe) pipetteLoupe.remove();
            document.removeEventListener('mousemove', updateLoupe);
            document.removeEventListener('click', pickColor);
            document.removeEventListener('keydown', escHandler);
            canvas.style.cursor = 'crosshair';
        }

        function escHandler(e) {
            if (e.key === 'Escape') {
                stopPipette();
                if (statusEl) statusEl.textContent = 'Pipette cancelled';
            }
        }

        document.addEventListener('mousemove', updateLoupe);
        document.addEventListener('click', pickColor);
        document.addEventListener('keydown', escHandler);
    });

    // Resize canvas
    document.getElementById('gif-resize-canvas')?.addEventListener('click', () => {
        const newWidth = prompt(`Enter new width (current: ${stateManager.width}px):`, stateManager.width);
        const newHeight = prompt(`Enter new height (current: ${stateManager.height}px):`, stateManager.height);
        if (newWidth && newHeight) {
            const w = parseInt(newWidth);
            const h = parseInt(newHeight);
            if (!isNaN(w) && !isNaN(h) && w > 0 && h > 0 && w <= 1024 && h <= 1024) {
                resizeGif(stateManager, w, h, statusEl);
                stateManager.drawCanvas();
                stateManager.updateTimeline();
            } else {
                if (statusEl) statusEl.textContent = '❌ Invalid dimensions (max 1024)';
            }
        }
    });

    // Tween frames
    document.getElementById('gif-tween-frames')?.addEventListener('click', () => {
        if (stateManager.frames.length < 2) {
            if (statusEl) statusEl.textContent = '⚠️ Need at least 2 frames to tween';
            return;
        }

        const frameList = stateManager.frames.map((_, idx) => `${idx + 1}: Frame ${idx + 1} (delay: ${_.delay}cs)`).join('\n');
        let fromFrame = prompt(`🎬 TWEENING - Create smooth in-between frames\n\nEnter START frame number (1-${stateManager.frames.length}):\n\n${frameList}`, '1');
        if (!fromFrame) return;

        let toFrame = prompt(`Enter END frame number (1-${stateManager.frames.length}):`, String(stateManager.frames.length));
        if (!toFrame) return;

        let fromIdx = parseInt(fromFrame) - 1;
        let toIdx = parseInt(toFrame) - 1;

        if (isNaN(fromIdx) || isNaN(toIdx) || fromIdx < 0 || toIdx >= stateManager.frames.length || fromIdx === toIdx) {
            if (statusEl) statusEl.textContent = '❌ Invalid frame numbers';
            return;
        }

        let steps = prompt(`How many in-between frames to generate? (1-20)`, '3');
        if (!steps) return;
        steps = parseInt(steps);
        if (isNaN(steps) || steps < 1 || steps > 20) {
            if (statusEl) statusEl.textContent = '❌ Steps must be between 1 and 20';
            return;
        }

        const frameA = stateManager.frames[fromIdx];
        const frameB = stateManager.frames[toIdx];

        const dataA = new Uint8ClampedArray(frameA.data);
        const dataB = new Uint8ClampedArray(frameB.data);
        const totalPixels = stateManager.width * stateManager.height * 4;

        const newFrames = [];

        for (let step = 1; step <= steps; step++) {
            const t = step / (steps + 1);
            const newData = new Uint8ClampedArray(totalPixels);

            for (let i = 0; i < totalPixels; i += 4) {
                const aAlpha = dataA[i + 3] / 255;
                const bAlpha = dataB[i + 3] / 255;
                const resultAlpha = aAlpha * (1 - t) + bAlpha * t;

                if (resultAlpha === 0) {
                    newData[i] = 0;
                    newData[i + 1] = 0;
                    newData[i + 2] = 0;
                    newData[i + 3] = 0;
                    continue;
                }

                newData[i] = Math.round(((dataA[i] * aAlpha * (1 - t) + dataB[i] * bAlpha * t) / resultAlpha));
                newData[i + 1] = Math.round(((dataA[i + 1] * aAlpha * (1 - t) + dataB[i + 1] * bAlpha * t) / resultAlpha));
                newData[i + 2] = Math.round(((dataA[i + 2] * aAlpha * (1 - t) + dataB[i + 2] * bAlpha * t) / resultAlpha));
                newData[i + 3] = Math.round(resultAlpha * 255);
            }

            const delayA = frameA.delay || 10;
            const delayB = frameB.delay || 10;
            const interpolatedDelay = Math.round(lerp(delayA, delayB, t));

            newFrames.push({
                data: newData,
                delay: Math.max(1, interpolatedDelay)
            });
        }

        if (newFrames.length === 0) {
            if (statusEl) statusEl.textContent = '❌ No frames generated';
            return;
        }

        const insertPosition = fromIdx < toIdx ? fromIdx + 1 : toIdx + 1;
        const sortedNewFrames = fromIdx < toIdx ? newFrames : newFrames.reverse();

        stateManager.frames.splice(insertPosition, 0, ...sortedNewFrames);
        stateManager.currentFrame = insertPosition;
        stateManager.hasChanges = true;

        stateManager.drawCanvas();
        stateManager.updateTimeline();

        if (statusEl) {
            statusEl.textContent = `✓ Generated ${newFrames.length} in-between frames`;
            setTimeout(() => {
                if (statusEl.textContent?.includes('Generated')) {
                    statusEl.textContent = `Frame ${stateManager.currentFrame+1}/${stateManager.frames.length} | ${stateManager.width}x${stateManager.height}`;
                }
            }, 3000);
        }
    });

    function lerp(a, b, t) {
        return a + (b - a) * t;
    }

    // Smooth animation
    document.getElementById('gif-smooth-animation')?.addEventListener('click', () => {
        if (stateManager.frames.length < 2) {
            if (statusEl) statusEl.textContent = '⚠️ Need at least 2 frames to smooth animation';
            return;
        }

        const passes = prompt('Smooth animation (temporal anti-aliasing)\nHow many smoothing passes? (1-5, recommended 2)', '2');
        if (!passes) return;
        const numPasses = Math.min(5, Math.max(1, parseInt(passes)));
        if (isNaN(numPasses)) return;

        const originalFrames = stateManager.frames.map(f => ({
            data: new Uint8ClampedArray(f.data),
            delay: f.delay
        }));

        for (let pass = 0; pass < numPasses; pass++) {
            const newFrames = [];

            for (let i = 0; i < stateManager.frames.length; i++) {
                const current = originalFrames[i];
                const prev = i > 0 ? originalFrames[i - 1] : null;
                const next = i < originalFrames.length - 1 ? originalFrames[i + 1] : null;

                const newData = new Uint8ClampedArray(current.data.length);
                const totalPixels = current.data.length;

                for (let j = 0; j < totalPixels; j += 4) {
                    let r = current.data[j];
                    let g = current.data[j + 1];
                    let b = current.data[j + 2];
                    let a = current.data[j + 3];
                    let weightSum = 1;

                    if (prev) {
                        r += prev.data[j];
                        g += prev.data[j + 1];
                        b += prev.data[j + 2];
                        a += prev.data[j + 3];
                        weightSum++;
                    }

                    if (next) {
                        r += next.data[j];
                        g += next.data[j + 1];
                        b += next.data[j + 2];
                        a += next.data[j + 3];
                        weightSum++;
                    }

                    newData[j] = Math.round(r / weightSum);
                    newData[j + 1] = Math.round(g / weightSum);
                    newData[j + 2] = Math.round(b / weightSum);
                    newData[j + 3] = Math.round(a / weightSum);
                }

                newFrames.push({
                    data: newData,
                    delay: current.delay
                });
            }

            for (let i = 0; i < stateManager.frames.length; i++) {
                originalFrames[i].data.set(newFrames[i].data);
            }

            for (let i = 0; i < stateManager.frames.length; i++) {
                stateManager.frames[i].data.set(newFrames[i].data);
            }
        }

        stateManager.hasChanges = true;
        stateManager.drawCanvas();
        stateManager.updateTimeline();

        if (statusEl) {
            statusEl.textContent = `✓ Animation smoothed with ${numPasses} pass(es)`;
            setTimeout(() => {
                if (statusEl.textContent?.includes('smoothed')) {
                    statusEl.textContent = `Frame ${stateManager.currentFrame+1}/${stateManager.frames.length} | ${stateManager.width}x${stateManager.height}`;
                }
            }, 3000);
        }
    });

    // Save
    document.getElementById('gif-save')?.addEventListener('click', () => {
        const framesData = stateManager.frames.map(f => ({
            data: Array.from(f.data),
            width: stateManager.width,
            height: stateManager.height,
            delay: f.delay
        }));
        try {
            EditorAPI.send('gif:save:' + JSON.stringify({
                pony_name: stateManager.ponyName,
                sprite_name: stateManager.spriteName,
                frames: framesData,
                width: stateManager.width,
                height: stateManager.height
            }));
            if (statusEl) statusEl.textContent = 'Saving...';
            stateManager.hasChanges = false;
        } catch(e) {
            if (statusEl) statusEl.textContent = '❌ Error saving: ' + e.message;
        }
    });

    // Close
    document.getElementById('gif-editor-close')?.addEventListener('click', () => {
        stateManager.cleanup();
        modal.remove();
        window.GifEditorState = null;
        PonyEditor.closeTracePanel();
    });

    // === ЗАГРУЗКА GIF ===
    stateManager.createEmptyGif();

    setTimeout(() => {
        EditorAPI.send(`gif:load:${stateManager.ponyName}:${stateManager.spriteName}`);
    }, 100);

    stateManager.resizeHandler = () => {
        stateManager.drawCanvas();
    };
    window.addEventListener('resize', stateManager.resizeHandler);

    console.log('[GIF] Editor initialized');
}

// === ФУНКЦИЯ РЕСАЙЗА CANVAS ===
function resizeGif(stateManager, newWidth, newHeight, statusEl) {
    if (!stateManager.frames || stateManager.frames.length === 0) return;

    const oldWidth = stateManager.width;
    const oldHeight = stateManager.height;

    if (newWidth === oldWidth && newHeight === oldHeight) {
        if (statusEl) statusEl.textContent = 'Size unchanged';
        return;
    }

    const scaleX = newWidth / oldWidth;
    const scaleY = newHeight / oldHeight;

    for (let f = 0; f < stateManager.frames.length; f++) {
        const oldData = stateManager.frames[f].data;
        const newData = new Uint8ClampedArray(newWidth * newHeight * 4);
        newData.fill(0);

        for (let y = 0; y < newHeight; y++) {
            for (let x = 0; x < newWidth; x++) {
                const srcX = Math.floor(x / scaleX);
                const srcY = Math.floor(y / scaleY);

                if (srcX >= 0 && srcX < oldWidth && srcY >= 0 && srcY < oldHeight) {
                    const srcIdx = (srcY * oldWidth + srcX) * 4;
                    const dstIdx = (y * newWidth + x) * 4;

                    newData[dstIdx] = oldData[srcIdx];
                    newData[dstIdx + 1] = oldData[srcIdx + 1];
                    newData[dstIdx + 2] = oldData[srcIdx + 2];
                    newData[dstIdx + 3] = oldData[srcIdx + 3];
                }
            }
        }

        stateManager.frames[f].data = newData;
    }

    stateManager.width = newWidth;
    stateManager.height = newHeight;
    stateManager.hasChanges = true;

    if (statusEl) statusEl.textContent = `✅ Resized to ${newWidth}x${newHeight}`;
}

// Функция для рендеринга трейса из глобального состояния
function renderTrace() {
    if (window._traceState) {
        const canvas = window._traceState.canvas;
        const ctx = window._traceState.ctx;
        const mainCanvas = window._traceState._mainCanvas;
        const state = window._traceState._stateManager;

        if (!mainCanvas) return;

        // Синхронизируем размеры с основным канвасом
        canvas.width = mainCanvas.width;
        canvas.height = mainCanvas.height;
        canvas.style.width = mainCanvas.style.width || mainCanvas.width + 'px';
        canvas.style.height = mainCanvas.style.height || mainCanvas.height + 'px';

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!window._traceState.loaded || window._traceState.frames.length === 0) return;

        const frameIndex = window._traceState.currentFrame % window._traceState.frames.length;
        const frameData = window._traceState.frames[frameIndex];
        if (!frameData) return;

        const targetWidth = state.width || window._traceState.width;
        const targetHeight = state.height || window._traceState.height;

        const baseSize = Math.min(canvas.width / targetWidth, canvas.height / targetHeight);
        const scale = baseSize * window._traceState.size;

        const drawW = window._traceState.width * scale;
        const drawH = window._traceState.height * scale;

        const offsetX = (canvas.width - drawW) / 2;
        const offsetY = (canvas.height - drawH) / 2;

        ctx.globalAlpha = window._traceState.opacity;

        let sx = 1, sy = 1;
        if (window._traceState.flipH) sx = -1;
        if (window._traceState.flipV) sy = -1;

        ctx.save();
        ctx.translate(canvas.width/2, canvas.height/2);
        ctx.scale(sx, sy);
        ctx.translate(-canvas.width/2, -canvas.height/2);

        try {
            const imgData = new ImageData(frameData.data, window._traceState.width, window._traceState.height);
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = window._traceState.width;
            tempCanvas.height = window._traceState.height;
            const tempCtx = tempCanvas.getContext('2d');
            tempCtx.putImageData(imgData, 0, 0);
            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(tempCanvas, offsetX, offsetY, drawW, drawH);
        } catch(e) {
            console.warn('[Trace] Render error:', e);
        }

        ctx.restore();
        ctx.globalAlpha = 1;

        if (window._traceState.showGrid) {
            ctx.strokeStyle = 'rgba(203, 166, 247, 0.15)';
            ctx.lineWidth = 1;
            const gridSize = 32 * scale;
            for (let x = offsetX % gridSize; x < canvas.width; x += gridSize) {
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, canvas.height);
                ctx.stroke();
            }
            for (let y = offsetY % gridSize; y < canvas.height; y += gridSize) {
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(canvas.width, y);
                ctx.stroke();
            }
        }
    }
}

// Делаем renderTrace глобальной для вызова из drawCanvas
window.renderTrace = renderTrace;

console.log('[PonyEditor] Full version with trace panel and external GIF load loaded');