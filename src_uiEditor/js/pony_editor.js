// src_uiEditor/js/pony_editor.js - ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ
// + СОЗДАНИЕ НОВЫХ ПЕРСОНАЖЕЙ И GIF + АВТООБНОВЛЕНИЕ СПИСКА СПРАЙТОВ

const PonyEditor = {
    container: null,
    currentPonyName: null,
    currentPonyConfig: null,

    init() {
        this.container = document.getElementById('editor-panel');
        console.log('[PonyEditor] Initialized, container:', this.container);

        // Добавляем глобальную кнопку создания нового персонажа
        this.addGlobalCreateButton();

        // Подписываемся на события перезагрузки пони
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
            // Запрашиваем перезагрузку конфига пони
            setTimeout(() => {
                EditorAPI.send('pony:reload:' + this.currentPonyName);
            }, 300);
        }
    },

    addGlobalCreateButton() {
        // Ждем появления тулбара
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

            // Обновляем список пони в левой панели через секунду
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

            // Открываем редактор для нового спрайта после его создания
            const checkAndOpen = setInterval(() => {
                // Проверяем, появился ли спрайт в конфиге
                if (this.currentPonyConfig && this.currentPonyConfig.behaviors) {
                    const spriteExists = this.currentPonyConfig.behaviors.some(b =>
                        b.sprite_right === spriteName || b.sprite_left === spriteName
                    );
                    // Или просто ждем 1.5 секунды и открываем редактор
                }
            }, 500);

            setTimeout(() => {
                clearInterval(checkAndOpen);
                // Пытаемся открыть редактор для нового спрайта
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
    }
};

// Глобальное состояние GIF редактора
window.GifEditorState = null;

// === СТИЛИ ДЛЯ ПАНЕЛИ ТРАССИРОВКИ ===
const traceStyles = `
<style id="trace-styles">
.trace-panel {
    position: fixed;
    bottom: 160px;
    right: 20px;
    background: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 12px;
    padding: 12px;
    width: 260px;
    z-index: 20005;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.trace-panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid #313244;
}
.trace-panel-title {
    font-size: 13px;
    font-weight: bold;
    color: #cba6f7;
}
.trace-panel-close {
    background: none;
    border: none;
    color: #a6adc8;
    cursor: pointer;
    font-size: 16px;
}
.trace-panel-close:hover { color: #f38ba8; }
.trace-preview {
    width: 100%;
    height: 60px;
    background: #11111b;
    border-radius: 6px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}
.trace-preview img, .trace-preview canvas {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}
.trace-slider {
    width: 100%;
    margin: 8px 0;
}
.trace-slider label {
    font-size: 11px;
    color: #a6adc8;
    display: block;
    margin-bottom: 4px;
}
.trace-slider input {
    width: 100%;
    cursor: pointer;
}
.trace-checkbox {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 8px 0;
    font-size: 11px;
}
.trace-checkbox input {
    width: auto;
    margin: 0;
}
.trace-load-buttons {
    display: flex;
    gap: 6px;
    margin-top: 8px;
}
.trace-load-buttons button {
    flex: 1;
    padding: 4px;
    font-size: 10px;
}
.divider {
    height: 1px;
    background: #313244;
    margin: 8px 0;
}
.ref-timeline-container {
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid #313244;
    display: none;
}
.ref-timeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 10px;
    color: #cba6f7;
    margin-bottom: 6px;
}
.ref-timeline-controls {
    display: flex;
    gap: 6px;
    align-items: center;
}
.ref-timeline-controls button {
    background: #313244;
    border: none;
    border-radius: 4px;
    color: #cdd6f4;
    cursor: pointer;
    padding: 2px 6px;
    font-size: 9px;
}
.ref-timeline {
    display: flex;
    gap: 4px;
    overflow-x: auto;
    padding: 4px;
    background: #11111b;
    border-radius: 6px;
}
.ref-frame {
    width: 40px;
    height: 40px;
    background: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 4px;
    cursor: pointer;
    flex-shrink: 0;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
}
.ref-frame canvas {
    width: 100%;
    height: 100%;
    object-fit: contain;
}
.ref-frame.active {
    border-color: #cba6f7;
    box-shadow: 0 0 4px #cba6f7;
}
</style>
`;

// Функция открытия редактора GIF
function showInlineGifEditor(ponyName, spriteName) {
    console.log('[GIF] Opening inline editor for:', ponyName, spriteName);

    const existingModal = document.getElementById('gif-editor-modal');
    if (existingModal) {
        if (window.GifEditorState && window.GifEditorState.previewInterval) {
            clearInterval(window.GifEditorState.previewInterval);
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

    modal.innerHTML = traceStyles + `
        <div style="padding: 12px 20px; background: #181825; border-bottom: 1px solid #313244; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="font-size: 20px; font-weight: bold;">🎨 GIF Editor</span>
                <span style="color: #a6adc8; margin-left: 16px; font-size: 14px;">${escapeHtml(ponyName)} / ${escapeHtml(spriteName)}</span>
            </div>
            <button id="gif-editor-close" style="background: none; border: none; color: #f38ba8; font-size: 28px; cursor: pointer; padding: 4px 12px;">✕</button>
        </div>
        
        <div style="padding: 8px 16px; background: #11111b; border-bottom: 1px solid #313244; display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
            <button id="gif-tool-pencil" class="gif-tool-btn active" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">✏️ Pencil</button>
            <button id="gif-tool-eraser" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">🧽 Eraser</button>
            <button id="gif-tool-fill" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">🪣 Fill</button>
            <button id="gif-tool-smooth" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">✨ Smooth Edges</button>
            
            <div style="width: 1px; height: 28px; background: #313244;"></div>
            
            <button id="gif-resize-canvas" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">📏 Resize Canvas</button>
            <button id="gif-tween-frames" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">🔄 Tween Frames</button>
            <button id="gif-smooth-animation" class="gif-tool-btn" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">🎞️ Smooth Anim</button>
            
            <div style="width: 1px; height: 28px; background: #313244;"></div>
            
            <button id="gif-trace-reference" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">🖼️ Trace Reference</button>
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
        </div>
        
        <div style="padding: 8px 16px; background: #0f0f17; border-bottom: 1px solid #313244; display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
            <button id="gif-clear-frame" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">🗑️ Clear Frame</button>
            <button id="gif-add-frame" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">➕ Add Frame</button>
            <button id="gif-duplicate-frame" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">📋 Duplicate Frame</button>
            <button id="gif-delete-frame" style="padding: 6px 14px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; cursor: pointer; font-size: 13px;">➖ Delete Frame</button>
        </div>
        
        <div style="flex: 1; display: flex; justify-content: center; align-items: center; background: #0a0a0f; overflow: auto; min-height: 0; padding: 20px;">
            <canvas id="gif-main-canvas" style="image-rendering: crisp-edges; image-rendering: pixelated; border: 2px solid #313244; border-radius: 8px; cursor: crosshair; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"></canvas>
        </div>
        
        <div style="height: 130px; background: #181825; border-top: 1px solid #313244; padding: 10px; overflow-x: auto;">
            <div id="gif-timeline" style="display: flex; gap: 10px; height: 100%;"></div>
        </div>
        
        <div style="padding: 6px 16px; font-size: 12px; color: #a6adc8; background: #11111b; border-top: 1px solid #313244;">
            <span id="gif-status">Loading GIF...</span>
        </div>
    `;

    document.body.appendChild(modal);
    initGifEditorEnhanced(ponyName, spriteName, modal);
}

// Функция ресайза canvas
function resizeGif(state, newWidth, newHeight, statusEl) {
    if (!state.frames || state.frames.length === 0) return;

    const oldWidth = state.width;
    const oldHeight = state.height;

    if (newWidth === oldWidth && newHeight === oldHeight) {
        if (statusEl) statusEl.textContent = 'Size unchanged';
        return;
    }

    const scaleX = newWidth / oldWidth;
    const scaleY = newHeight / oldHeight;

    for (let f = 0; f < state.frames.length; f++) {
        const oldData = state.frames[f].data;
        const newData = new Uint8ClampedArray(newWidth * newHeight * 4);

        for (let i = 0; i < newData.length; i += 4) {
            newData[i] = 0;
            newData[i + 1] = 0;
            newData[i + 2] = 0;
            newData[i + 3] = 0;
        }

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

        state.frames[f].data = newData;
    }

    state.width = newWidth;
    state.height = newHeight;
    state.hasChanges = true;

    if (statusEl) statusEl.textContent = `✅ Resized to ${newWidth}x${newHeight}`;
}

// ИНИЦИАЛИЗАТОР GIF РЕДАКТОРА
function initGifEditorEnhanced(ponyName, spriteName, modal) {
    console.log('[GIF] initGifEditorEnhanced for:', ponyName, spriteName);

    const state = {
        frames: [],
        currentFrame: 0,
        width: 128,
        height: 128,
        zoom: 1,
        tool: 'pencil',
        currentColor: { r: 203, g: 166, b: 247, a: 255 },
        currentHue: 260,
        previewInterval: null,
        playSpeed: 1.0,
        ponyName: ponyName,
        spriteName: spriteName,
        hasChanges: false,
        isLoading: false,
        isPickingColor: false
    };

    const canvas = document.getElementById('gif-main-canvas');
    const timeline = document.getElementById('gif-timeline');
    const statusEl = document.getElementById('gif-status');
    const delayInput = document.getElementById('gif-frame-delay');
    const zoomLevel = document.getElementById('gif-zoom-level');
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

    function getPixelFromMouseEvent(e) {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        const pixelX = Math.floor((mouseX / canvas.width) * state.width);
        const pixelY = Math.floor((mouseY / canvas.height) * state.height);
        return {
            x: Math.max(0, Math.min(state.width - 1, pixelX)),
            y: Math.max(0, Math.min(state.height - 1, pixelY))
        };
    }

    function setPixelAt(px, py) {
        if (!state.frames[state.currentFrame] || state.isPickingColor) return;
        if (px < 0 || px >= state.width || py < 0 || py >= state.height) return;

        const frame = state.frames[state.currentFrame];
        const idx = (py * state.width + px) * 4;

        if (state.tool === 'eraser') {
            frame.data[idx] = 0;
            frame.data[idx + 1] = 0;
            frame.data[idx + 2] = 0;
            frame.data[idx + 3] = 0;
        } else if (state.tool === 'pencil') {
            const targetAlpha = state.currentColor.a / 255;
            const currentAlpha = frame.data[idx + 3] / 255;
            const resultAlpha = targetAlpha + currentAlpha * (1 - targetAlpha);

            if (resultAlpha > 0) {
                frame.data[idx] = Math.round(
                    (state.currentColor.r * targetAlpha + frame.data[idx] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[idx + 1] = Math.round(
                    (state.currentColor.g * targetAlpha + frame.data[idx + 1] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[idx + 2] = Math.round(
                    (state.currentColor.b * targetAlpha + frame.data[idx + 2] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[idx + 3] = Math.round(resultAlpha * 255);
            } else {
                frame.data[idx] = 0;
                frame.data[idx + 1] = 0;
                frame.data[idx + 2] = 0;
                frame.data[idx + 3] = 0;
            }
        }

        state.hasChanges = true;
        drawCanvas();
        updateTimeline();
    }

    function floodFillAt(px, py) {
        if (!state.frames[state.currentFrame] || state.isPickingColor) return;
        if (px < 0 || px >= state.width || py < 0 || py >= state.height) return;

        const frame = state.frames[state.currentFrame];
        const idx = (py * state.width + px) * 4;

        const target = {
            r: frame.data[idx],
            g: frame.data[idx + 1],
            b: frame.data[idx + 2],
            a: frame.data[idx + 3]
        };

        if (target.r === state.currentColor.r &&
            target.g === state.currentColor.g &&
            target.b === state.currentColor.b &&
            target.a === state.currentColor.a) return;

        const stack = [{ x: px, y: py }];
        const visited = new Set();

        while (stack.length) {
            const { x: cx, y: cy } = stack.pop();
            const key = `${cx},${cy}`;
            if (visited.has(key)) continue;
            visited.add(key);

            const cidx = (cy * state.width + cx) * 4;

            if (Math.abs(frame.data[cidx] - target.r) > 5 ||
                Math.abs(frame.data[cidx + 1] - target.g) > 5 ||
                Math.abs(frame.data[cidx + 2] - target.b) > 5 ||
                Math.abs(frame.data[cidx + 3] - target.a) > 10) continue;

            const targetAlpha = state.currentColor.a / 255;
            const currentAlpha = frame.data[cidx + 3] / 255;
            const resultAlpha = targetAlpha + currentAlpha * (1 - targetAlpha);

            if (resultAlpha > 0) {
                frame.data[cidx] = Math.round(
                    (state.currentColor.r * targetAlpha + frame.data[cidx] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[cidx + 1] = Math.round(
                    (state.currentColor.g * targetAlpha + frame.data[cidx + 1] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[cidx + 2] = Math.round(
                    (state.currentColor.b * targetAlpha + frame.data[cidx + 2] * currentAlpha * (1 - targetAlpha)) / resultAlpha
                );
                frame.data[cidx + 3] = Math.round(resultAlpha * 255);
            }

            if (cx > 0) stack.push({ x: cx - 1, y: cy });
            if (cx < state.width - 1) stack.push({ x: cx + 1, y: cy });
            if (cy > 0) stack.push({ x: cx, y: cy - 1 });
            if (cy < state.height - 1) stack.push({ x: cx, y: cy + 1 });
        }

        state.hasChanges = true;
        drawCanvas();
        updateTimeline();
    }

    // TWEENING FRAMES
    function tweenFrames() {
        if (state.frames.length < 2) {
            if (statusEl) statusEl.textContent = '⚠️ Need at least 2 frames to tween';
            return;
        }

        const frameList = state.frames.map((_, idx) => `${idx + 1}: Frame ${idx + 1} (delay: ${_.delay}cs)`).join('\n');
        let fromFrame = prompt(`🎬 TWEENING - Create smooth in-between frames\n\nEnter START frame number (1-${state.frames.length}):\n\n${frameList}`, '1');
        if (!fromFrame) return;

        let toFrame = prompt(`Enter END frame number (1-${state.frames.length}):`, String(state.frames.length));
        if (!toFrame) return;

        let fromIdx = parseInt(fromFrame) - 1;
        let toIdx = parseInt(toFrame) - 1;

        if (isNaN(fromIdx) || isNaN(toIdx) || fromIdx < 0 || toIdx >= state.frames.length || fromIdx === toIdx) {
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

        const frameA = state.frames[fromIdx];
        const frameB = state.frames[toIdx];

        const dataA = new Uint8ClampedArray(frameA.data);
        const dataB = new Uint8ClampedArray(frameB.data);
        const totalPixels = state.width * state.height * 4;

        const newFrames = [];

        function lerp(a, b, t) {
            return Math.round(a + (b - a) * t);
        }

        function interpolatePixel(idx, t) {
            const aAlpha = dataA[idx + 3] / 255;
            const bAlpha = dataB[idx + 3] / 255;
            const resultAlpha = aAlpha * (1 - t) + bAlpha * t;

            if (resultAlpha === 0) {
                return [0, 0, 0, 0];
            }

            const r = ((dataA[idx] * aAlpha * (1 - t) + dataB[idx] * bAlpha * t) / resultAlpha);
            const g = ((dataA[idx + 1] * aAlpha * (1 - t) + dataB[idx + 1] * bAlpha * t) / resultAlpha);
            const b = ((dataA[idx + 2] * aAlpha * (1 - t) + dataB[idx + 2] * bAlpha * t) / resultAlpha);

            return [
                Math.round(Math.min(255, Math.max(0, r))),
                Math.round(Math.min(255, Math.max(0, g))),
                Math.round(Math.min(255, Math.max(0, b))),
                Math.round(resultAlpha * 255)
            ];
        }

        for (let step = 1; step <= steps; step++) {
            const t = step / (steps + 1);
            const newData = new Uint8ClampedArray(totalPixels);

            for (let i = 0; i < totalPixels; i += 4) {
                const interpolated = interpolatePixel(i, t);
                newData[i] = interpolated[0];
                newData[i + 1] = interpolated[1];
                newData[i + 2] = interpolated[2];
                newData[i + 3] = interpolated[3];
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

        state.frames.splice(insertPosition, 0, ...sortedNewFrames);
        state.currentFrame = insertPosition;
        state.hasChanges = true;

        drawCanvas();
        updateTimeline();

        if (statusEl) {
            statusEl.textContent = `✓ Generated ${newFrames.length} in-between frames between frame ${fromFrame} and ${toFrame}`;
            setTimeout(() => {
                if (statusEl.textContent?.includes('Generated')) {
                    statusEl.textContent = `Frame ${state.currentFrame+1}/${state.frames.length} | ${state.width}x${state.height}`;
                }
            }, 3000);
        }
    }

    // SMOOTH ANIMATION
    function smoothAnimation() {
        if (state.frames.length < 2) {
            if (statusEl) statusEl.textContent = '⚠️ Need at least 2 frames to smooth animation';
            return;
        }

        const passes = prompt('Smooth animation (temporal anti-aliasing)\nHow many smoothing passes? (1-5, recommended 2)', '2');
        if (!passes) return;
        const numPasses = Math.min(5, Math.max(1, parseInt(passes)));
        if (isNaN(numPasses)) return;

        const originalFrames = state.frames.map(f => ({
            data: new Uint8ClampedArray(f.data),
            delay: f.delay
        }));

        for (let pass = 0; pass < numPasses; pass++) {
            const newFrames = [];

            for (let i = 0; i < state.frames.length; i++) {
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

            for (let i = 0; i < state.frames.length; i++) {
                originalFrames[i].data.set(newFrames[i].data);
            }

            for (let i = 0; i < state.frames.length; i++) {
                state.frames[i].data.set(newFrames[i].data);
            }
        }

        state.hasChanges = true;
        drawCanvas();
        updateTimeline();

        if (statusEl) {
            statusEl.textContent = `✓ Animation smoothed with ${numPasses} pass(es) (temporal blending)`;
            setTimeout(() => {
                if (statusEl.textContent?.includes('smoothed')) {
                    statusEl.textContent = `Frame ${state.currentFrame+1}/${state.frames.length} | ${state.width}x${state.height}`;
                }
            }, 3000);
        }
    }

    // SMOOTH EDGES
    function smoothEdges() {
        if (!state.frames[state.currentFrame]) return;

        const frame = state.frames[state.currentFrame];
        const width = state.width;
        const height = state.height;
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

        const afterSpikes = new Uint8ClampedArray(data);
        const stairSmooths = [];
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const p = getPixel(x, y, afterSpikes);
                if (!p || p.a < alphaThreshold) continue;
                const n = isSolid(x, y-1, afterSpikes);
                const s = isSolid(x, y+1, afterSpikes);
                const w = isSolid(x-1, y, afterSpikes);
                const e = isSolid(x+1, y, afterSpikes);
                const nw = isSolid(x-1, y-1, afterSpikes);
                const ne = isSolid(x+1, y-1, afterSpikes);
                const sw = isSolid(x-1, y+1, afterSpikes);
                const se = isSolid(x+1, y+1, afterSpikes);
                if (n && w && !nw) stairSmooths.push({ x: x-1, y: y-1 });
                if (n && e && !ne) stairSmooths.push({ x: x+1, y: y-1 });
                if (s && w && !sw) stairSmooths.push({ x: x-1, y: y+1 });
                if (s && e && !se) stairSmooths.push({ x: x+1, y: y+1 });
            }
        }
        for (const stair of stairSmooths) {
            if (!isSolid(stair.x, stair.y, afterSpikes)) {
                const avgColor = getAverageColor(stair.x, stair.y, afterSpikes);
                if (avgColor) setPixelColor(stair.x, stair.y, avgColor, data);
            }
        }

        const finalData = new Uint8ClampedArray(data);
        const toClean = [];
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                if (!isSolid(x, y, finalData)) continue;
                let neighborCount = 0, diagonalCount = 0;
                for (let dy = -1; dy <= 1; dy++) {
                    for (let dx = -1; dx <= 1; dx++) {
                        if (dx === 0 && dy === 0) continue;
                        if (isSolid(x + dx, y + dy, finalData)) {
                            if (Math.abs(dx) + Math.abs(dy) === 2) diagonalCount++;
                            else neighborCount++;
                        }
                    }
                }
                if (neighborCount === 1 && diagonalCount === 1) toClean.push({ x, y });
            }
        }
        for (const clean of toClean) {
            const idx = (clean.y * width + clean.x) * 4;
            data[idx] = 0; data[idx+1] = 0; data[idx+2] = 0; data[idx+3] = 0;
        }

        state.hasChanges = true;
        drawCanvas();
        updateTimeline();

        if (statusEl) {
            statusEl.textContent = `✓ Smooth complete: +${cornersToAdd.length} outer, +${pitsToFill.length} inner, -${spikesToRemove.length} spikes, -${toClean.length} sharp`;
            setTimeout(() => {
                if (statusEl.textContent === `✓ Smooth complete: +${cornersToAdd.length} outer, +${pitsToFill.length} inner, -${spikesToRemove.length} spikes, -${toClean.length} sharp`) {
                    statusEl.textContent = `Frame ${state.currentFrame+1}/${state.frames.length} | Delay: ${state.frames[state.currentFrame]?.delay || 10}cs | ${state.width}x${state.height}`;
                }
            }, 3000);
        }
    }

    function hslToRgb(h, s, l) {
        h = h / 360;
        let r, g, b;
        if (s === 0) r = g = b = l;
        else {
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
        return { r: Math.round(r * 255), g: Math.round(g * 255), b: Math.round(b * 255) };
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
                const rgb = hslToRgb(state.currentHue, sat, light);
                ctxSquare.fillStyle = `rgb(${rgb.r},${rgb.g},${rgb.b})`;
                ctxSquare.fillRect(x, y, 1, 1);
            }
        }
    }

    function updateAlphaSlider() {
        if (alphaSlider) alphaSlider.value = state.currentColor.a;
        if (alphaValue) alphaValue.textContent = state.currentColor.a;
    }

    function rgbToHex(r, g, b) {
        return '#' + [r, g, b].map(x => {
            const hex = x.toString(16);
            return hex.length === 1 ? '0' + hex : hex;
        }).join('').toUpperCase();
    }

    function updateCurrentColorDisplay() {
        const bgColor = `rgba(${state.currentColor.r}, ${state.currentColor.g}, ${state.currentColor.b}, ${state.currentColor.a / 255})`;
        if (currentColorPreview) currentColorPreview.style.backgroundColor = bgColor;
        if (colorPreviewMini) colorPreviewMini.style.backgroundColor = bgColor;
        if (currentRgbSpan) currentRgbSpan.textContent = `RGB(${state.currentColor.r},${state.currentColor.g},${state.currentColor.b})`;
        const hex = rgbToHex(state.currentColor.r, state.currentColor.g, state.currentColor.b);
        if (currentHexSpan) currentHexSpan.textContent = hex;
        if (hexInput) hexInput.value = hex;
        if (rgbaInput) rgbaInput.value = `rgba(${state.currentColor.r},${state.currentColor.g},${state.currentColor.b},${(state.currentColor.a/255).toFixed(2)})`;
        updateAlphaSlider();
    }

    function setColorFromRgb(r, g, b, a) {
        state.currentColor = { r, g, b, a: a !== undefined ? a : state.currentColor.a };
        updateCurrentColorDisplay();
    }

    function onColorSquareClick(e) {
        const rect = colorSquare.getBoundingClientRect();
        const scaleX = colorSquare.width / rect.width;
        const scaleY = colorSquare.height / rect.height;
        let x = (e.clientX - rect.left) * scaleX;
        let y = (e.clientY - rect.top) * scaleY;
        x = Math.min(Math.max(0, x), colorSquare.width - 1);
        y = Math.min(Math.max(0, y), colorSquare.height - 1);
        const sat = x / colorSquare.width;
        const light = 1 - (y / colorSquare.height);
        const rgb = hslToRgb(state.currentHue, sat, light);
        setColorFromRgb(rgb.r, rgb.g, rgb.b);
    }

    if (colorSquare) {
        colorSquare.addEventListener('mousedown', (e) => {
            isDrawingSquare = true;
            onColorSquareClick(e);
        });
        colorSquare.addEventListener('mousemove', (e) => {
            if (isDrawingSquare) onColorSquareClick(e);
        });
        colorSquare.addEventListener('mouseup', () => isDrawingSquare = false);
    }

    if (hueSlider) {
        hueSlider.addEventListener('input', (e) => {
            state.currentHue = parseInt(e.target.value);
            drawColorSquare();
        });
    }

    if (alphaSlider) {
        alphaSlider.addEventListener('input', (e) => {
            state.currentColor.a = parseInt(e.target.value);
            updateCurrentColorDisplay();
        });
    }

    if (hexInput) {
        hexInput.addEventListener('change', () => {
            let hex = hexInput.value;
            if (!hex.startsWith('#')) hex = '#' + hex;
            if (/^#[0-9A-Fa-f]{6}$/.test(hex)) {
                const r = parseInt(hex.slice(1,3), 16);
                const g = parseInt(hex.slice(3,5), 16);
                const b = parseInt(hex.slice(5,7), 16);
                setColorFromRgb(r, g, b);
            }
        });
    }

    if (rgbaInput) {
        rgbaInput.addEventListener('change', () => {
            const match = rgbaInput.value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([0-9.]+))?\)/);
            if (match) {
                const r = parseInt(match[1]);
                const g = parseInt(match[2]);
                const b = parseInt(match[3]);
                const a = match[4] ? Math.round(parseFloat(match[4]) * 255) : 255;
                setColorFromRgb(r, g, b, a);
            }
        });
    }

    if (colorBtn && colorDropdown) {
        colorBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isVisible = colorDropdown.style.display === 'flex';
            colorDropdown.style.display = isVisible ? 'none' : 'flex';
            if (!isVisible) {
                drawColorSquare();
                updateCurrentColorDisplay();
            }
        });
        document.addEventListener('click', (e) => {
            if (!colorBtn.contains(e.target) && !colorDropdown.contains(e.target)) {
                colorDropdown.style.display = 'none';
            }
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && colorDropdown.style.display === 'flex') {
                colorDropdown.style.display = 'none';
            }
        });
    }

    // Pipette
    let pipetteOverlay = null;
    let pipetteLoupe = null;
    let pipetteActive = false;

    function startPipette() {
        if (pipetteActive) return;
        pipetteActive = true;
        state.isPickingColor = true;
        if (colorDropdown) colorDropdown.style.display = 'none';
        if (statusEl) statusEl.textContent = '🔍 Pipette active: Click on canvas to pick color, ESC to cancel';
        canvas.style.cursor = 'crosshair';

        pipetteOverlay = document.createElement('div');
        pipetteOverlay.style.cssText = `position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: transparent; z-index: 20010; cursor: crosshair;`;
        pipetteLoupe = document.createElement('div');
        pipetteLoupe.style.cssText = `position: fixed; width: 150px; height: 150px; border-radius: 75px; border: 2px solid #cba6f7; background: rgba(30,30,46,0.9); box-shadow: 0 0 20px rgba(0,0,0,0.5); pointer-events: none; z-index: 20011; overflow: hidden; backdrop-filter: blur(2px);`;
        const loupeCanvas = document.createElement('canvas');
        loupeCanvas.width = 150;
        loupeCanvas.height = 150;
        loupeCanvas.style.width = '150px';
        loupeCanvas.style.height = '150px';
        loupeCanvas.style.imageRendering = 'crisp-edges';
        loupeCanvas.style.imageRendering = 'pixelated';
        pipetteLoupe.appendChild(loupeCanvas);
        const loupeInfo = document.createElement('div');
        loupeInfo.style.cssText = `position: absolute; bottom: 5px; left: 5px; right: 5px; background: rgba(0,0,0,0.8); color: #cba6f7; font-size: 9px; text-align: center; border-radius: 4px; padding: 3px; font-family: monospace; font-weight: bold;`;
        loupeInfo.id = 'pipette-loupe-info';
        pipetteLoupe.appendChild(loupeInfo);
        pipetteOverlay.appendChild(pipetteLoupe);
        document.body.appendChild(pipetteOverlay);

        const loupeCtx = loupeCanvas.getContext('2d');
        const loupeSize = 150;
        const sampleSize = 15;
        const pixelDrawSize = loupeSize / sampleSize;

        function updateLoupe(e) {
            if (!state.isPickingColor) return;
            const x = e.clientX;
            const y = e.clientY;
            pipetteLoupe.style.left = (x - loupeSize/2) + 'px';
            pipetteLoupe.style.top = (y - loupeSize/2) + 'px';
            const rect = canvas.getBoundingClientRect();
            if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
                const canvasX = (x - rect.left) / canvas.width;
                const canvasY = (y - rect.top) / canvas.height;
                let px = Math.floor(canvasX * state.width);
                let py = Math.floor(canvasY * state.height);
                px = Math.max(0, Math.min(state.width - 1, px));
                py = Math.max(0, Math.min(state.height - 1, py));
                if (state.frames[state.currentFrame]) {
                    const frame = state.frames[state.currentFrame];
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
                            const sampleX = Math.max(0, Math.min(state.width - 1, px + (dx - offset)));
                            const sampleY = Math.max(0, Math.min(state.height - 1, py + (dy - offset)));
                            const idx = (sampleY * state.width + sampleX) * 4;
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
            if (!state.isPickingColor) return;
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX;
            const y = e.clientY;
            if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
                const canvasX = (x - rect.left) / canvas.width;
                const canvasY = (y - rect.top) / canvas.height;
                let px = Math.floor(canvasX * state.width);
                let py = Math.floor(canvasY * state.height);
                px = Math.max(0, Math.min(state.width - 1, px));
                py = Math.max(0, Math.min(state.height - 1, py));
                if (state.frames[state.currentFrame]) {
                    const frame = state.frames[state.currentFrame];
                    const idx = (py * state.width + px) * 4;
                    const newColor = {
                        r: frame.data[idx],
                        g: frame.data[idx+1],
                        b: frame.data[idx+2],
                        a: frame.data[idx+3]
                    };
                    state.currentColor = newColor;
                    updateCurrentColorDisplay();
                    if (statusEl) {
                        statusEl.textContent = `✓ Picked: rgba(${newColor.r},${newColor.g},${newColor.b},${newColor.a})`;
                        setTimeout(() => {
                            if (statusEl.textContent === `✓ Picked: rgba(${newColor.r},${newColor.g},${newColor.b},${newColor.a})`) {
                                statusEl.textContent = `Frame ${state.currentFrame+1}/${state.frames.length} | Delay: ${state.frames[state.currentFrame]?.delay || 10}cs | ${state.width}x${state.height}`;
                            }
                        }, 2000);
                    }
                    const rgb = { r: newColor.r, g: newColor.g, b: newColor.b };
                    let hue = 0;
                    const max = Math.max(rgb.r, rgb.g, rgb.b);
                    const min = Math.min(rgb.r, rgb.g, rgb.b);
                    if (max !== min) {
                        if (max === rgb.r) hue = 60 * (0 + (rgb.g - rgb.b) / (max - min));
                        else if (max === rgb.g) hue = 60 * (2 + (rgb.b - rgb.r) / (max - min));
                        else hue = 60 * (4 + (rgb.r - rgb.g) / (max - min));
                        if (hue < 0) hue += 360;
                    }
                    state.currentHue = Math.round(hue);
                    if (hueSlider) hueSlider.value = state.currentHue;
                    drawColorSquare();
                }
            }
            stopPipette();
        }

        function stopPipette() {
            if (!pipetteActive) return;
            pipetteActive = false;
            state.isPickingColor = false;
            if (pipetteOverlay) pipetteOverlay.remove();
            if (pipetteLoupe) pipetteLoupe.remove();
            pipetteOverlay = null;
            pipetteLoupe = null;
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
    }

    const pipetteBtn = document.getElementById('gif-pipette-btn');
    if (pipetteBtn) {
        const newBtn = pipetteBtn.cloneNode(true);
        pipetteBtn.parentNode.replaceChild(newBtn, pipetteBtn);
        newBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            startPipette();
        });
    }

    let previewInterval = null;

    function getFrameDelay() {
        if (!state.frames[state.currentFrame]) return 100;
        const baseDelay = (state.frames[state.currentFrame].delay || 10) * 10;
        return Math.max(20, baseDelay / state.playSpeed);
    }

    function startPreview() {
        if (previewInterval) stopPreview();
        const frameDelay = getFrameDelay();
        previewInterval = setInterval(() => {
            state.currentFrame = (state.currentFrame + 1) % state.frames.length;
            drawCanvas();
            updateTimeline();
        }, frameDelay);
        if (previewBtn) previewBtn.textContent = '⏸️ Stop';
    }

    function stopPreview() {
        if (previewInterval) {
            clearInterval(previewInterval);
            previewInterval = null;
        }
        if (previewBtn) previewBtn.textContent = '▶️ Preview';
    }

    if (previewBtn) {
        previewBtn.addEventListener('click', () => {
            if (previewInterval) stopPreview();
            else startPreview();
            state.previewInterval = previewInterval;
        });
    }

    if (speedSlider && speedValue) {
        speedSlider.addEventListener('input', (e) => {
            state.playSpeed = parseFloat(e.target.value);
            speedValue.textContent = state.playSpeed.toFixed(2) + 'x';
            if (previewInterval) startPreview();
        });
    }

    function centerCanvas() {
        const container = canvas.parentElement;
        if (container) {
            container.scrollLeft = (canvas.width - container.clientWidth) / 2;
            container.scrollTop = (canvas.height - container.clientHeight) / 2;
        }
    }

    function drawCanvas() {
        if (!state.frames[state.currentFrame]) return;
        const frame = state.frames[state.currentFrame];
        const displayWidth = state.width * state.zoom;
        const displayHeight = state.height * state.zoom;
        canvas.width = displayWidth;
        canvas.height = displayHeight;
        canvas.style.width = displayWidth + 'px';
        canvas.style.height = displayHeight + 'px';
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = state.width;
        tempCanvas.height = state.height;
        const tempCtx = tempCanvas.getContext('2d');
        const imgData = new ImageData(frame.data, state.width, state.height);
        tempCtx.putImageData(imgData, 0, 0);
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(tempCanvas, 0, 0, state.width, state.height, 0, 0, displayWidth, displayHeight);
        if (zoomLevel) zoomLevel.textContent = Math.round(state.zoom * 100) + '%';
        if (delayInput && state.frames[state.currentFrame]) delayInput.value = state.frames[state.currentFrame].delay;
        if (statusEl && state.frames[state.currentFrame] && !state.isPickingColor) {
            statusEl.textContent = `Frame ${state.currentFrame+1}/${state.frames.length} | Delay: ${state.frames[state.currentFrame].delay}cs | Speed: ${state.playSpeed.toFixed(2)}x | Zoom: ${Math.round(state.zoom * 100)}% | ${state.width}x${state.height}`;
        }
    }

    const zoomInBtn = document.getElementById('gif-zoom-in');
    const zoomOutBtn = document.getElementById('gif-zoom-out');
    const zoomResetBtn = document.getElementById('gif-zoom-reset');
    const zoomFitBtn = document.getElementById('gif-zoom-fit');
    const resizeCanvasBtn = document.getElementById('gif-resize-canvas');

    if (zoomInBtn) {
        zoomInBtn.addEventListener('click', () => {
            let newZoom = state.zoom + 0.25;
            if (newZoom > 8) newZoom = 8;
            state.zoom = newZoom;
            drawCanvas();
            centerCanvas();
        });
    }

    if (zoomOutBtn) {
        zoomOutBtn.addEventListener('click', () => {
            let newZoom = state.zoom - 0.25;
            if (newZoom < 0.25) newZoom = 0.25;
            state.zoom = newZoom;
            drawCanvas();
        });
    }

    if (zoomResetBtn) {
        zoomResetBtn.addEventListener('click', () => {
            state.zoom = 1;
            drawCanvas();
            centerCanvas();
        });
    }

    if (zoomFitBtn) {
        zoomFitBtn.addEventListener('click', () => {
            const container = canvas.parentElement;
            if (container) {
                const containerWidth = container.clientWidth - 40;
                const containerHeight = container.clientHeight - 40;
                const fitZoomX = containerWidth / state.width;
                const fitZoomY = containerHeight / state.height;
                const fitZoom = Math.min(fitZoomX, fitZoomY, 4);
                state.zoom = Math.max(0.25, fitZoom);
                drawCanvas();
                centerCanvas();
            }
        });
    }

    if (resizeCanvasBtn) {
        resizeCanvasBtn.addEventListener('click', () => {
            const newWidth = prompt(`Enter new width (current: ${state.width}px):`, state.width);
            const newHeight = prompt(`Enter new height (current: ${state.height}px):`, state.height);
            if (newWidth && newHeight) {
                const w = parseInt(newWidth);
                const h = parseInt(newHeight);
                if (!isNaN(w) && !isNaN(h) && w > 0 && h > 0 && w <= 1024 && h <= 1024) {
                    resizeGif(state, w, h, statusEl);
                    drawCanvas();
                    updateTimeline();
                } else {
                    if (statusEl) statusEl.textContent = '❌ Invalid dimensions (max 1024)';
                }
            }
        });
    }

    if (canvas) {
        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            if (e.deltaY < 0) {
                let newZoom = state.zoom + 0.1;
                if (newZoom > 8) newZoom = 8;
                state.zoom = newZoom;
            } else {
                let newZoom = state.zoom - 0.1;
                if (newZoom < 0.25) newZoom = 0.25;
                state.zoom = newZoom;
            }
            drawCanvas();
            if (e.deltaY < 0) centerCanvas();
        });
    }

    function updateTimeline() {
        if (!timeline) return;
        timeline.innerHTML = '';
        state.frames.forEach((frame, idx) => {
            const div = document.createElement('div');
            div.style.cssText = `width: 90px; height: 105px; background: #11111b; border: 2px solid ${idx === state.currentFrame ? '#cba6f7' : '#313244'}; border-radius: 8px; cursor: pointer; display: flex; flex-direction: column; align-items: center; padding: 8px; flex-shrink: 0;`;
            const previewCanvas = document.createElement('canvas');
            previewCanvas.width = 72;
            previewCanvas.height = 72;
            const previewCtx = previewCanvas.getContext('2d');
            try {
                const imgData = new ImageData(frame.data, state.width, state.height);
                previewCtx.putImageData(imgData, 0, 0);
            } catch(e) {}
            div.appendChild(previewCanvas);
            const label = document.createElement('span');
            label.textContent = `${idx+1} | ${frame.delay}cs`;
            label.style.fontSize = '10px';
            label.style.marginTop = '6px';
            div.appendChild(label);
            div.onclick = () => {
                if (previewInterval) stopPreview();
                state.currentFrame = idx;
                drawCanvas();
                updateTimeline();
            };
            timeline.appendChild(div);
        });
    }

    function loadGifData(gifData) {
        console.log('[GIF] loadGifData called');
        if (state.isLoading) return;
        state.isLoading = true;
        if (previewInterval) stopPreview();
        state.playSpeed = 1.0;
        if (speedSlider) speedSlider.value = '1';
        if (speedValue) speedValue.textContent = '1.00x';
        state.zoom = 1;
        if (zoomLevel) zoomLevel.textContent = '100%';
        if (!gifData.frames || gifData.frames.length === 0) {
            createEmptyGif();
            state.isLoading = false;
            return;
        }
        state.width = gifData.width;
        state.height = gifData.height;
        state.frames = [];
        for (let i = 0; i < gifData.frames.length; i++) {
            const srcFrame = gifData.frames[i];
            let byteData;
            if (srcFrame.data instanceof Uint8Array || srcFrame.data instanceof Uint8ClampedArray) {
                byteData = new Uint8ClampedArray(srcFrame.data);
            } else if (Array.isArray(srcFrame.data)) {
                byteData = new Uint8ClampedArray(srcFrame.data);
            } else { continue; }
            const expectedSize = state.width * state.height * 4;
            if (byteData.length !== expectedSize && byteData.length === state.width * state.height) {
                const converted = new Uint8ClampedArray(expectedSize);
                for (let j = 0; j < byteData.length; j++) {
                    const pixel = byteData[j];
                    converted[j*4] = (pixel>>16)&0xFF;
                    converted[j*4+1] = (pixel>>8)&0xFF;
                    converted[j*4+2] = pixel&0xFF;
                    converted[j*4+3] = (pixel>>24)&0xFF;
                }
                byteData = converted;
            }
            state.frames.push({ data: byteData, delay: srcFrame.delay || 10 });
        }
        if (state.frames.length === 0) { createEmptyGif(); state.isLoading = false; return; }
        state.currentFrame = 0;
        drawCanvas();
        updateTimeline();
        if (statusEl) statusEl.textContent = `Loaded ${state.frames.length} frames, ${state.width}x${state.height}`;
        state.isLoading = false;
    }

    function createEmptyGif() {
        if (previewInterval) stopPreview();
        state.playSpeed = 1.0;
        if (speedSlider) speedSlider.value = '1';
        if (speedValue) speedValue.textContent = '1.00x';
        state.zoom = 1;
        if (zoomLevel) zoomLevel.textContent = '100%';
        state.width = 128;
        state.height = 128;
        state.frames = [];
        for (let i = 0; i < 2; i++) {
            const data = new Uint8ClampedArray(state.width * state.height * 4);
            for (let j = 0; j < data.length; j += 4) {
                data[j] = 255; data[j+1] = 192; data[j+2] = 203; data[j+3] = 255;
            }
            state.frames.push({ data, delay: 10 });
        }
        state.currentFrame = 0;
        drawCanvas();
        updateTimeline();
        if (statusEl) statusEl.textContent = `New GIF: ${state.frames.length} frames, ${state.width}x${state.height}`;
    }

    function saveGif() {
        const framesData = state.frames.map(f => ({ data: Array.from(f.data), width: state.width, height: state.height, delay: f.delay }));
        EditorAPI.send('gif:save:' + JSON.stringify({ pony_name: ponyName, sprite_name: spriteName, frames: framesData, width: state.width, height: state.height }));
        if (statusEl) statusEl.textContent = 'Saving...';
        state.hasChanges = false;
    }

    let isDrawing = false;
    canvas.addEventListener('mousedown', (e) => {
        if (state.isPickingColor) return;
        isDrawing = true;
        e.preventDefault();
        const { x, y } = getPixelFromMouseEvent(e);
        if (state.tool === 'fill') floodFillAt(x, y);
        else setPixelAt(x, y);
    });
    canvas.addEventListener('mousemove', (e) => {
        if (!isDrawing || state.tool === 'fill' || state.isPickingColor) return;
        e.preventDefault();
        const { x, y } = getPixelFromMouseEvent(e);
        setPixelAt(x, y);
    });
    canvas.addEventListener('mouseup', () => isDrawing = false);
    canvas.addEventListener('mouseleave', () => isDrawing = false);

    document.getElementById('gif-tool-pencil')?.addEventListener('click', () => {
        state.tool = 'pencil';
        document.querySelectorAll('.gif-tool-btn').forEach(b => b.classList.remove('active'));
        document.getElementById('gif-tool-pencil')?.classList.add('active');
    });
    document.getElementById('gif-tool-eraser')?.addEventListener('click', () => {
        state.tool = 'eraser';
        document.querySelectorAll('.gif-tool-btn').forEach(b => b.classList.remove('active'));
        document.getElementById('gif-tool-eraser')?.classList.add('active');
    });
    document.getElementById('gif-tool-fill')?.addEventListener('click', () => {
        state.tool = 'fill';
        document.querySelectorAll('.gif-tool-btn').forEach(b => b.classList.remove('active'));
        document.getElementById('gif-tool-fill')?.classList.add('active');
    });
    document.getElementById('gif-tool-smooth')?.addEventListener('click', () => {
        smoothEdges();
        document.getElementById('gif-tool-smooth')?.classList.add('active');
        setTimeout(() => document.getElementById('gif-tool-smooth')?.classList.remove('active'), 500);
    });
    document.getElementById('gif-tween-frames')?.addEventListener('click', () => {
        tweenFrames();
        document.getElementById('gif-tween-frames')?.classList.add('active');
        setTimeout(() => document.getElementById('gif-tween-frames')?.classList.remove('active'), 500);
    });
    document.getElementById('gif-smooth-animation')?.addEventListener('click', () => {
        smoothAnimation();
        document.getElementById('gif-smooth-animation')?.classList.add('active');
        setTimeout(() => document.getElementById('gif-smooth-animation')?.classList.remove('active'), 500);
    });
    document.getElementById('gif-clear-frame')?.addEventListener('click', () => {
        if (state.frames[state.currentFrame]) {
            state.frames[state.currentFrame].data.fill(0);
            drawCanvas();
            updateTimeline();
            state.hasChanges = true;
        }
    });
    document.getElementById('gif-add-frame')?.addEventListener('click', () => {
        const newData = new Uint8ClampedArray(state.width * state.height * 4);
        for (let i = 3; i < newData.length; i+=4) newData[i] = 255;
        state.frames.push({ data: newData, delay: 10 });
        state.currentFrame = state.frames.length - 1;
        drawCanvas();
        updateTimeline();
        state.hasChanges = true;
    });
    document.getElementById('gif-duplicate-frame')?.addEventListener('click', () => {
        if (state.frames[state.currentFrame]) {
            const newData = new Uint8ClampedArray(state.frames[state.currentFrame].data.length);
            newData.set(state.frames[state.currentFrame].data);
            state.frames.splice(state.currentFrame + 1, 0, { data: newData, delay: state.frames[state.currentFrame].delay });
            state.currentFrame++;
            drawCanvas();
            updateTimeline();
            state.hasChanges = true;
        }
    });
    document.getElementById('gif-delete-frame')?.addEventListener('click', () => {
        if (state.frames.length > 1) {
            state.frames.splice(state.currentFrame, 1);
            if (state.currentFrame >= state.frames.length) state.currentFrame = state.frames.length - 1;
            drawCanvas();
            updateTimeline();
            state.hasChanges = true;
        }
    });
    if (delayInput) {
        delayInput.addEventListener('change', () => {
            if (state.frames[state.currentFrame]) {
                state.frames[state.currentFrame].delay = parseInt(delayInput.value) || 10;
                updateTimeline();
                state.hasChanges = true;
            }
        });
    }
    document.getElementById('gif-save')?.addEventListener('click', saveGif);
    document.getElementById('gif-editor-close')?.addEventListener('click', () => {
        if (previewInterval) clearInterval(previewInterval);
        modal.remove();
        window.GifEditorState = null;
    });

    window.GifEditorState = state;
    window.GifEditorState.loadGif = loadGifData;
    createEmptyGif();
    setTimeout(() => EditorAPI.send(`gif:load:${ponyName}:${spriteName}`), 100);
    updateCurrentColorDisplay();

    // Trace Reference Feature
    function setupTracePanel() {
        const existingPanel = document.getElementById('trace-panel');
        if (existingPanel) existingPanel.remove();

        let traceImage = null;
        let traceVisible = true;
        let traceOpacity = 0.5;
        let traceScale = 1;
        let traceOffsetX = 0;
        let traceOffsetY = 0;
        let traceFrames = null;
        let traceCurrentFrame = 0;
        let traceAnimationInterval = null;

        const panel = document.createElement('div');
        panel.id = 'trace-panel';
        panel.className = 'trace-panel';
        panel.innerHTML = `
        <div class="trace-panel-header">
            <span class="trace-panel-title">🖼️ Trace Reference</span>
            <button class="trace-panel-close" id="trace-panel-close">✕</button>
        </div>
        <div class="trace-preview" id="trace-preview">
            <span style="color: #a6adc8; font-size: 11px;">No reference loaded</span>
        </div>
        <div class="trace-slider">
            <label>Opacity: <span id="trace-opacity-value">50</span>%</label>
            <input type="range" id="trace-opacity-slider" min="0" max="100" value="50">
        </div>
        <div class="trace-slider">
            <label>Scale: <span id="trace-scale-value">100</span>%</label>
            <input type="range" id="trace-scale-slider" min="25" max="200" value="100">
        </div>
        <div class="trace-checkbox">
            <input type="checkbox" id="trace-visible-checkbox" checked>
            <label>Show reference</label>
        </div>
        <div class="ref-timeline-container" id="ref-timeline-container" style="display:none">
            <div class="ref-timeline-header">
                <span>🎞️ GIF Frames</span>
                <div class="ref-timeline-controls">
                    <button id="ref-prev-frame">◀</button>
                    <span id="ref-frame-info">1/1</span>
                    <button id="ref-next-frame">▶</button>
                    <label><input type="checkbox" id="ref-animate"> Auto</label>
                </div>
            </div>
            <div id="ref-timeline" class="ref-timeline"></div>
        </div>
        <div class="divider"></div>
        <div class="trace-load-buttons">
            <button id="trace-load-image" class="btn-secondary">🖼️ Load Image</button>
            <button id="trace-load-gif" class="btn-secondary">🎞️ Load GIF</button>
        </div>
        <button id="trace-reset-btn" class="btn-secondary" style="width:100%; margin-top:8px; padding:4px;">⟳ Reset Position</button>
        <div style="font-size: 9px; color: #6c7086; margin-top: 8px; text-align: center;">💡 Drag image to move | Shift+Scroll to scale</div>
    `;
        modal.appendChild(panel);

        const originalDraw = drawCanvas;

        function redrawWithTrace() {
            if (!state.frames[state.currentFrame]) return;
            const displayWidth = state.width * state.zoom;
            const displayHeight = state.height * state.zoom;
            canvas.width = displayWidth;
            canvas.height = displayHeight;
            canvas.style.width = displayWidth + 'px';
            canvas.style.height = displayHeight + 'px';
            ctx.clearRect(0, 0, displayWidth, displayHeight);

            if (traceVisible && traceImage && traceImage.complete) {
                ctx.save();
                ctx.globalAlpha = traceOpacity;
                const refW = traceImage.width * traceScale * state.zoom;
                const refH = traceImage.height * traceScale * state.zoom;
                const refX = traceOffsetX * state.zoom;
                const refY = traceOffsetY * state.zoom;
                ctx.drawImage(traceImage, refX, refY, refW, refH);
                ctx.restore();
            }

            const frame = state.frames[state.currentFrame];
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = state.width;
            tempCanvas.height = state.height;
            const tempCtx = tempCanvas.getContext('2d');
            const imgData = new ImageData(frame.data, state.width, state.height);
            tempCtx.putImageData(imgData, 0, 0);
            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(tempCanvas, 0, 0, state.width, state.height, 0, 0, displayWidth, displayHeight);

            if (zoomLevel) zoomLevel.textContent = Math.round(state.zoom * 100) + '%';
            if (delayInput && state.frames[state.currentFrame]) delayInput.value = state.frames[state.currentFrame].delay;
            if (statusEl && state.frames[state.currentFrame] && !state.isPickingColor) {
                statusEl.textContent = `Frame ${state.currentFrame+1}/${state.frames.length} | Delay: ${state.frames[state.currentFrame].delay}cs | Speed: ${state.playSpeed.toFixed(2)}x | Zoom: ${Math.round(state.zoom * 100)}% | ${state.width}x${state.height}`;
            }
        }

        drawCanvas = redrawWithTrace;

        function updatePreview() {
            const previewDiv = document.getElementById('trace-preview');
            if (!previewDiv) return;
            if (traceImage) {
                previewDiv.innerHTML = `<img src="${traceImage.src}" style="max-width:100%; max-height:100%; object-fit:contain;">`;
            } else {
                previewDiv.innerHTML = '<span style="color: #a6adc8; font-size: 11px;">No reference loaded</span>';
            }
        }

        function updateTimelineUI() {
            const container = document.getElementById('ref-timeline');
            const infoSpan = document.getElementById('ref-frame-info');
            if (!container || !traceFrames) return;
            container.innerHTML = '';
            traceFrames.forEach((frame, idx) => {
                const div = document.createElement('div');
                div.className = 'ref-frame';
                if (idx === traceCurrentFrame) div.classList.add('active');
                const fcanvas = document.createElement('canvas');
                fcanvas.width = 30;
                fcanvas.height = 30;
                const fctx = fcanvas.getContext('2d');
                if (frame.imageData) {
                    fctx.putImageData(frame.imageData, 0, 0);
                } else if (frame.canvas) {
                    fctx.drawImage(frame.canvas, 0, 0, 30, 30);
                }
                div.appendChild(fcanvas);
                div.onclick = () => {
                    if (traceAnimationInterval) clearInterval(traceAnimationInterval);
                    traceCurrentFrame = idx;
                    updateImageFromFrames();
                    updateTimelineUI();
                    redrawWithTrace();
                };
                container.appendChild(div);
            });
            if (infoSpan) infoSpan.textContent = `${traceCurrentFrame+1}/${traceFrames.length}`;
            const timelineContainer = document.getElementById('ref-timeline-container');
            if (timelineContainer) timelineContainer.style.display = 'block';
        }

        function updateImageFromFrames() {
            if (!traceFrames || !traceFrames[traceCurrentFrame]) return;
            const frame = traceFrames[traceCurrentFrame];
            if (frame.imageData) {
                const fcanvas = document.createElement('canvas');
                fcanvas.width = frame.imageData.width;
                fcanvas.height = frame.imageData.height;
                const fctx = fcanvas.getContext('2d');
                fctx.putImageData(frame.imageData, 0, 0);
                const img = new Image();
                img.onload = () => {
                    traceImage = img;
                    updatePreview();
                    redrawWithTrace();
                };
                img.src = fcanvas.toDataURL();
            } else if (frame.canvas) {
                const img = new Image();
                img.onload = () => {
                    traceImage = img;
                    updatePreview();
                    redrawWithTrace();
                };
                img.src = frame.canvas.toDataURL();
            }
        }

        function startAnimation() {
            if (traceAnimationInterval) clearInterval(traceAnimationInterval);
            if (!traceFrames || traceFrames.length <= 1) return;
            traceAnimationInterval = setInterval(() => {
                traceCurrentFrame = (traceCurrentFrame + 1) % traceFrames.length;
                updateImageFromFrames();
                updateTimelineUI();
                redrawWithTrace();
            }, 100);
        }

        function stopAnimation() {
            if (traceAnimationInterval) {
                clearInterval(traceAnimationInterval);
                traceAnimationInterval = null;
            }
        }

        // Улучшенный парсер GIF
        function parseGifFrames(arrayBuffer) {
            try {
                const data = new Uint8Array(arrayBuffer);
                let pos = 0;

                // Проверяем заголовок GIF
                if (data[0] !== 0x47 || data[1] !== 0x49 || data[2] !== 0x46) {
                    console.warn('Not a valid GIF');
                    return null;
                }

                const version = String.fromCharCode(data[3], data[4], data[5]);
                console.log(`GIF version: ${version}`);
                pos = 6;

                // Логический дескриптор экрана
                const width = data[pos] | (data[pos+1] << 8);
                const height = data[pos+2] | (data[pos+3] << 8);
                const packed = data[pos+4];
                const backgroundColorIndex = data[pos+5];
                pos += 7;

                console.log(`GIF dimensions: ${width}x${height}`);

                // Глобальная палитра
                let globalColorTable = null;
                const hasGlobalColorTable = (packed & 0x80) !== 0;
                if (hasGlobalColorTable) {
                    const colorTableSize = 2 << (packed & 0x07);
                    globalColorTable = [];
                    for (let i = 0; i < colorTableSize; i++) {
                        globalColorTable.push({
                            r: data[pos++],
                            g: data[pos++],
                            b: data[pos++]
                        });
                    }
                }

                // Функция для пропуска блоков расширений
                function skipExtension() {
                    let subBlockSize = data[pos++];
                    while (subBlockSize > 0 && pos < data.length) {
                        pos += subBlockSize;
                        subBlockSize = data[pos++];
                    }
                }

                // ИСПРАВЛЕННЫЙ LZW декодер
                function decodeLZW(byteStream, minCodeSize, pixelCount) {
                    const clearCode = 1 << minCodeSize;
                    const eoiCode = clearCode + 1;
                    let codeSize = minCodeSize + 1;

                    // Инициализация таблицы
                    let codeTable = [];
                    for (let i = 0; i < (1 << minCodeSize); i++) {
                        codeTable.push([i]);
                    }
                    let availableCode = clearCode + 2;

                    let oldCode = -1;
                    let output = [];
                    let bitPos = 0;
                    let bytePos = 0;
                    let currentByte = 0;

                    function readBits(bitsToRead) {
                        let value = 0;
                        let bitsRead = 0;

                        while (bitsRead < bitsToRead) {
                            if (bytePos >= byteStream.length) return -1;

                            if (bitPos === 0) {
                                currentByte = byteStream[bytePos++];
                            }

                            const bitsRemainingInByte = 8 - bitPos;
                            const bitsToTake = Math.min(bitsToRead - bitsRead, bitsRemainingInByte);
                            const mask = (1 << bitsToTake) - 1;
                            const shifted = (currentByte >> bitPos) & mask;

                            value |= shifted << bitsRead;
                            bitsRead += bitsToTake;
                            bitPos += bitsToTake;

                            if (bitPos >= 8) {
                                bitPos = 0;
                            }
                        }

                        return value;
                    }

                    while (output.length < pixelCount) {
                        let code = readBits(codeSize);
                        if (code === -1 || code === eoiCode) break;

                        if (code === clearCode) {
                            // Сброс таблицы
                            codeSize = minCodeSize + 1;
                            codeTable = [];
                            for (let i = 0; i < (1 << minCodeSize); i++) {
                                codeTable.push([i]);
                            }
                            availableCode = clearCode + 2;
                            oldCode = -1;
                            continue;
                        }

                        if (oldCode === -1) {
                            if (code < codeTable.length) {
                                const entry = codeTable[code];
                                output.push(...entry);
                                oldCode = code;
                            }
                            continue;
                        }

                        let entry;
                        if (code < codeTable.length) {
                            entry = codeTable[code];
                        } else if (code === availableCode) {
                            // Специальный случай: код равен новому доступному
                            const prevEntry = codeTable[oldCode];
                            entry = [...prevEntry, prevEntry[0]];
                        } else {
                            break;
                        }

                        output.push(...entry);

                        // Добавляем новую запись в таблицу
                        if (availableCode < 4096) {
                            const prevEntry = codeTable[oldCode];
                            const newEntry = [...prevEntry, entry[0]];
                            codeTable[availableCode] = newEntry;
                            availableCode++;

                            // Увеличиваем размер кода при необходимости
                            if (availableCode >= (1 << codeSize) && codeSize < 12) {
                                codeSize++;
                            }
                        }

                        oldCode = code;
                    }

                    return output;
                }

                const frames = [];
                let frameCount = 0;

                // Создаём canvas для текущего состояния
                let currentCanvas = document.createElement('canvas');
                currentCanvas.width = width;
                currentCanvas.height = height;
                let currentCtx = currentCanvas.getContext('2d');
                currentCtx.clearRect(0, 0, width, height);

                // Храним предыдущий кадр для disposal
                let previousFrameData = null;
                let disposalMethod = 0;

                while (pos < data.length) {
                    const blockType = data[pos++];

                    if (blockType === 0x21) { // Extension
                        const extensionType = data[pos++];

                        if (extensionType === 0xF9) { // Graphic Control Extension
                            const blockSize = data[pos++];
                            const packed2 = data[pos++];
                            disposalMethod = (packed2 >> 2) & 0x07;
                            const transparentColorFlag = (packed2 & 0x01) !== 0;
                            const delayTime = data[pos] | (data[pos+1] << 8);
                            const transparentColorIndex = data[pos+2];
                            pos += 3;
                            const terminator = data[pos++];

                            // Если есть ожидающий кадр, обновляем его информацию
                            if (frameCount > 0 && frameCount <= frames.length) {
                                const lastFrame = frames[frames.length - 1];
                                if (lastFrame) {
                                    lastFrame.delay = delayTime || 10;
                                    lastFrame.disposalMethod = disposalMethod;
                                    lastFrame.transparentColorIndex = transparentColorFlag ? transparentColorIndex : -1;
                                }
                            }
                        } else {
                            skipExtension();
                        }
                        continue;
                    } else if (blockType === 0x2C) { // Image Descriptor
                        const left = data[pos] | (data[pos+1] << 8);
                        const top = data[pos+2] | (data[pos+3] << 8);
                        const frameWidth = data[pos+4] | (data[pos+5] << 8);
                        const frameHeight = data[pos+6] | (data[pos+7] << 8);
                        const packed2 = data[pos+8];
                        const hasLocalColorTable = (packed2 & 0x80) !== 0;
                        const interlaceFlag = (packed2 & 0x40) !== 0;
                        const colorTableSize = 2 << (packed2 & 0x07);
                        pos += 9;

                        // Локальная палитра
                        let localColorTable = null;
                        if (hasLocalColorTable) {
                            localColorTable = [];
                            for (let i = 0; i < colorTableSize; i++) {
                                localColorTable.push({
                                    r: data[pos++],
                                    g: data[pos++],
                                    b: data[pos++]
                                });
                            }
                        }

                        const colorTable = localColorTable || globalColorTable;
                        if (!colorTable) {
                            console.warn('No color table available');
                            continue;
                        }

                        // Читаем LZW минимальный код
                        const lzwMinCodeSize = data[pos++];

                        // Собираем данные изображения
                        let imageDataBytes = [];
                        let subBlockSize = data[pos++];
                        while (subBlockSize > 0 && pos < data.length) {
                            for (let i = 0; i < subBlockSize; i++) {
                                imageDataBytes.push(data[pos + i]);
                            }
                            pos += subBlockSize;
                            subBlockSize = data[pos++];
                        }

                        // Декодируем LZW
                        const pixelCount = frameWidth * frameHeight;
                        const decodedIndices = decodeLZW(imageDataBytes, lzwMinCodeSize, pixelCount);

                        if (!decodedIndices || decodedIndices.length < pixelCount) {
                            console.warn('Failed to decode LZW data');
                            continue;
                        }

                        // Создаём новый canvas для кадра
                        const frameCanvas = document.createElement('canvas');
                        frameCanvas.width = width;
                        frameCanvas.height = height;
                        const frameCtx = frameCanvas.getContext('2d');

                        // Применяем disposal method к предыдущему кадру
                        if (disposalMethod === 2) {
                            // Очищаем до фона
                            frameCtx.clearRect(0, 0, width, height);
                        } else if (disposalMethod === 3 && previousFrameData) {
                            // Восстанавливаем предыдущее состояние (сложно, используем предыдущий кадр)
                            if (frames.length > 1) {
                                const prevFrame = frames[frames.length - 1];
                                if (prevFrame && prevFrame.imageData) {
                                    frameCtx.putImageData(prevFrame.imageData, 0, 0);
                                }
                            }
                        } else {
                            // Копируем текущее состояние
                            if (currentCanvas) {
                                frameCtx.drawImage(currentCanvas, 0, 0);
                            }
                        }

                        // Получаем прозрачный индекс
                        let transparentIdx = -1;
                        if (frameCount > 0) {
                            const lastFrame = frames[frames.length - 1];
                            if (lastFrame) {
                                transparentIdx = lastFrame.transparentColorIndex || -1;
                            }
                        }

                        // Создаём данные изображения для текущего кадра
                        const imageData = frameCtx.createImageData(frameWidth, frameHeight);
                        const dataArray = imageData.data;

                        // Рисуем пиксели с правильной интерпретацией палитры
                        if (interlaceFlag) {
                            // Интерлейс: 4 прохода
                            const passOffsets = [0, 4, 2, 1];
                            const passIncrements = [8, 8, 4, 2];
                            let pixelIndex = 0;
                            for (let pass = 0; pass < 4; pass++) {
                                for (let y = passOffsets[pass]; y < frameHeight; y += passIncrements[pass]) {
                                    for (let x = 0; x < frameWidth; x++) {
                                        const colorIndex = decodedIndices[pixelIndex++];
                                        const idx = (y * frameWidth + x) * 4;

                                        if (colorIndex >= 0 && colorIndex < colorTable.length) {
                                            const color = colorTable[colorIndex];
                                            if (colorIndex === transparentIdx) {
                                                dataArray[idx] = 0;
                                                dataArray[idx+1] = 0;
                                                dataArray[idx+2] = 0;
                                                dataArray[idx+3] = 0;
                                            } else {
                                                dataArray[idx] = color.r;
                                                dataArray[idx+1] = color.g;
                                                dataArray[idx+2] = color.b;
                                                dataArray[idx+3] = 255;
                                            }
                                        }
                                    }
                                }
                            }
                        } else {
                            // Обычный вывод
                            for (let y = 0; y < frameHeight; y++) {
                                for (let x = 0; x < frameWidth; x++) {
                                    const colorIndex = decodedIndices[y * frameWidth + x];
                                    const idx = (y * frameWidth + x) * 4;

                                    if (colorIndex >= 0 && colorIndex < colorTable.length) {
                                        const color = colorTable[colorIndex];
                                        if (colorIndex === transparentIdx) {
                                            dataArray[idx] = 0;
                                            dataArray[idx+1] = 0;
                                            dataArray[idx+2] = 0;
                                            dataArray[idx+3] = 0;
                                        } else {
                                            dataArray[idx] = color.r;
                                            dataArray[idx+1] = color.g;
                                            dataArray[idx+2] = color.b;
                                            dataArray[idx+3] = 255;
                                        }
                                    }
                                }
                            }
                        }

                        // Накладываем изображение на canvas
                        frameCtx.putImageData(imageData, left, top);

                        // Сохраняем полный кадр
                        const fullFrameData = frameCtx.getImageData(0, 0, width, height);

                        // Сохраняем кадр
                        frames.push({
                            imageData: fullFrameData,
                            canvas: frameCanvas,
                            delay: 10,
                            disposalMethod: disposalMethod,
                            transparentColorIndex: transparentIdx,
                            width: width,
                            height: height
                        });

                        // Обновляем текущий canvas для следующего кадра
                        currentCanvas = frameCanvas;
                        currentCtx = frameCtx;
                        previousFrameData = fullFrameData;
                        frameCount++;

                        console.log(`Extracted frame ${frameCount}`);

                    } else if (blockType === 0x3B) { // Trailer
                        break;
                    } else {
                        console.warn(`Unknown block type: 0x${blockType.toString(16)}`);
                        break;
                    }
                }

                if (frames.length === 0) {
                    console.warn('No frames extracted from GIF');
                    return null;
                }

                console.log(`Successfully extracted ${frames.length} frames from GIF`);
                return frames;

            } catch (error) {
                console.error('Error parsing GIF:', error);
                return null;
            }
        }

        function loadReference(type) {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = type === 'gif' ? 'image/gif' : 'image/*';
            input.onchange = (e) => {
                const file = e.target.files[0];
                if (!file) return;

                if (type === 'gif' && file.name.toLowerCase().endsWith('.gif')) {
                    const reader = new FileReader();
                    reader.onload = (ev) => {
                        try {
                            const arrayBuffer = ev.target.result;
                            const frames = parseGifFrames(arrayBuffer);

                            if (frames && frames.length > 0) {
                                traceFrames = frames;
                                traceCurrentFrame = 0;
                                updateImageFromFrames();
                                updatePreview();
                                updateTimelineUI();
                                redrawWithTrace();
                                if (statusEl) statusEl.textContent = `✓ Loaded GIF: ${file.name} (${frames.length} frames)`;
                            } else {
                                // Fallback: загружаем как статическое изображение
                                const imgUrl = URL.createObjectURL(file);
                                const img = new Image();
                                img.onload = () => {
                                    traceImage = img;
                                    traceFrames = null;
                                    traceCurrentFrame = 0;
                                    updatePreview();
                                    const timelineContainer = document.getElementById('ref-timeline-container');
                                    if (timelineContainer) timelineContainer.style.display = 'none';
                                    redrawWithTrace();
                                    if (statusEl) statusEl.textContent = `✓ Loaded image (fallback): ${file.name}`;
                                };
                                img.onerror = () => {
                                    if (statusEl) statusEl.textContent = `❌ Failed to load ${file.name}`;
                                };
                                img.src = imgUrl;
                            }
                        } catch (error) {
                            console.error('Error loading GIF:', error);
                            if (statusEl) statusEl.textContent = `❌ Error loading GIF: ${error.message}`;
                        }
                    };
                    reader.onerror = () => {
                        if (statusEl) statusEl.textContent = `❌ Failed to read file: ${file.name}`;
                    };
                    reader.readAsArrayBuffer(file);
                } else {
                    const reader = new FileReader();
                    reader.onload = (ev) => {
                        const img = new Image();
                        img.onload = () => {
                            traceImage = img;
                            traceFrames = null;
                            traceCurrentFrame = 0;
                            updatePreview();
                            const timelineContainer = document.getElementById('ref-timeline-container');
                            if (timelineContainer) timelineContainer.style.display = 'none';
                            redrawWithTrace();
                            if (statusEl) statusEl.textContent = `✓ Loaded image: ${file.name}`;
                        };
                        img.onerror = () => {
                            if (statusEl) statusEl.textContent = `❌ Failed to load ${file.name}`;
                        };
                        img.src = ev.target.result;
                    };
                    reader.onerror = () => {
                        if (statusEl) statusEl.textContent = `❌ Failed to read file: ${file.name}`;
                    };
                    reader.readAsDataURL(file);
                }
            };
            input.click();
        }

        // Добавляем обработчики событий
        document.getElementById('trace-panel-close')?.addEventListener('click', () => {
            drawCanvas = originalDraw;
            panel.remove();
            redrawWithTrace();
        });
        document.getElementById('trace-load-image')?.addEventListener('click', () => loadReference('image'));
        document.getElementById('trace-load-gif')?.addEventListener('click', () => loadReference('gif'));
        document.getElementById('trace-reset-btn')?.addEventListener('click', () => {
            traceOffsetX = 0;
            traceOffsetY = 0;
            traceScale = 1;
            document.getElementById('trace-scale-slider').value = 100;
            document.getElementById('trace-scale-value').textContent = '100';
            updatePreview();
            redrawWithTrace();
            if (statusEl) statusEl.textContent = 'Reference reset';
        });
        document.getElementById('trace-opacity-slider')?.addEventListener('input', (e) => {
            traceOpacity = e.target.value / 100;
            document.getElementById('trace-opacity-value').textContent = e.target.value;
            redrawWithTrace();
        });
        document.getElementById('trace-scale-slider')?.addEventListener('input', (e) => {
            traceScale = e.target.value / 100;
            document.getElementById('trace-scale-value').textContent = e.target.value;
            redrawWithTrace();
        });
        document.getElementById('trace-visible-checkbox')?.addEventListener('change', (e) => {
            traceVisible = e.target.checked;
            redrawWithTrace();
        });
        document.getElementById('ref-prev-frame')?.addEventListener('click', () => {
            if (traceFrames && traceFrames.length > 0) {
                if (traceAnimationInterval) clearInterval(traceAnimationInterval);
                traceCurrentFrame = Math.max(0, traceCurrentFrame - 1);
                updateImageFromFrames();
                updateTimelineUI();
                redrawWithTrace();
            }
        });
        document.getElementById('ref-next-frame')?.addEventListener('click', () => {
            if (traceFrames && traceFrames.length > 0) {
                if (traceAnimationInterval) clearInterval(traceAnimationInterval);
                traceCurrentFrame = Math.min(traceFrames.length - 1, traceCurrentFrame + 1);
                updateImageFromFrames();
                updateTimelineUI();
                redrawWithTrace();
            }
        });
        document.getElementById('ref-animate')?.addEventListener('change', (e) => {
            if (e.target.checked) startAnimation();
            else stopAnimation();
        });

        // Drag and drop для перемещения референса
        let isDraggingRef = false;
        let dragStartX = 0, dragStartY = 0;
        let refStartX = 0, refStartY = 0;

        canvas.addEventListener('mousedown', (e) => {
            if (e.shiftKey && traceImage) {
                isDraggingRef = true;
                dragStartX = e.clientX;
                dragStartY = e.clientY;
                refStartX = traceOffsetX;
                refStartY = traceOffsetY;
                canvas.style.cursor = 'grabbing';
                e.preventDefault();
            }
        });
        canvas.addEventListener('mousemove', (e) => {
            if (isDraggingRef) {
                const dx = (e.clientX - dragStartX) / state.zoom;
                const dy = (e.clientY - dragStartY) / state.zoom;
                traceOffsetX = refStartX + dx;
                traceOffsetY = refStartY + dy;
                redrawWithTrace();
            }
        });
        canvas.addEventListener('mouseup', () => {
            isDraggingRef = false;
            canvas.style.cursor = 'crosshair';
        });
        canvas.addEventListener('wheel', (e) => {
            if (e.shiftKey && traceImage) {
                e.preventDefault();
                const delta = e.deltaY > 0 ? -0.05 : 0.05;
                traceScale = Math.max(0.25, Math.min(3, traceScale + delta));
                const slider = document.getElementById('trace-scale-slider');
                if (slider) {
                    slider.value = traceScale * 100;
                    document.getElementById('trace-scale-value').textContent = Math.round(traceScale * 100);
                }
                redrawWithTrace();
                if (statusEl) statusEl.textContent = `Scale: ${Math.round(traceScale * 100)}%`;
            }
        });
    }

    const traceBtn = document.getElementById('gif-trace-reference');
    if (traceBtn) traceBtn.addEventListener('click', () => setupTracePanel());
}

console.log('[PonyEditor] Loaded with enhanced GIF editor, pony creation, GIF creation, resize, smooth edges, tweening, and temporal smoothing');