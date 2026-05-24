// src_uiEditor/js/behavior_editor.js - ИСПРАВЛЕННАЯ ВЕРСИЯ

const BehaviorEditor = {
    behaviors: [],
    ponyName: null,
    gifCache: new Map(),
    customColors: ['#cba6f7', '#f38ba8', '#a6e3a1', '#89b4fa', '#f9e2af', '#fab387', '#94e2d5'],

    render(behaviors, ponyName) {
        console.log('[BehaviorEditor] render called with behaviors:', behaviors?.length);
        this.behaviors = behaviors || [];
        this.ponyName = ponyName;

        if (this.behaviors.length === 0) {
            return `
                <div class="card">
                    <div class="empty-state">No behaviors defined</div>
                    <button class="btn-secondary" id="add-behavior">+ Add Behavior</button>
                </div>
            `;
        }

        let html = `
            <div style="margin-bottom: 16px;">
                <button class="btn-secondary" id="add-behavior">+ Add Behavior</button>
            </div>
        `;

        this.behaviors.forEach((behavior, index) => {
            html += `
                <div class="card behavior-card" data-index="${index}">
                    <div class="card-header">
                        <h3>${escapeHtml(behavior.name || 'Unnamed')}</h3>
                        <div>
                            <button class="btn-icon edit-behavior" data-index="${index}" title="Edit behavior">✏️</button>
                            <button class="btn-icon delete-behavior" data-index="${index}" title="Delete">🗑️</button>
                        </div>
                    </div>
                    <div class="behavior-preview" style="display: flex; gap: 12px; margin-bottom: 16px;">
                        <div class="sprite-preview" data-sprite="${escapeHtml(behavior.sprite_right || '')}" data-side="right" data-behavior-index="${index}">
                            <div class="sprite-label">▶️ Right</div>
                            <canvas class="preview-canvas" width="64" height="64" style="background: repeating-conic-gradient(#2a2a3a 0% 25%, #1a1a2a 0% 50%) 50% / 16px 16px; border-radius: 8px; image-rendering: crisp-edges; image-rendering: pixelated;"></canvas>
                            <div class="sprite-filename">${escapeHtml(behavior.sprite_right || '—')}</div>
                        </div>
                        <div class="sprite-preview" data-sprite="${escapeHtml(behavior.sprite_left || '')}" data-side="left" data-behavior-index="${index}">
                            <div class="sprite-label">◀️ Left</div>
                            <canvas class="preview-canvas" width="64" height="64" style="background: repeating-conic-gradient(#2a2a3a 0% 25%, #1a1a2a 0% 50%) 50% / 16px 16px; border-radius: 8px; image-rendering: crisp-edges; image-rendering: pixelated;"></canvas>
                            <div class="sprite-filename">${escapeHtml(behavior.sprite_left || '—')}</div>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Name</label>
                            <input type="text" class="behavior-name" value="${escapeHtml(behavior.name)}" data-index="${index}">
                        </div>
                        <div class="form-group">
                            <label>Chance (0-1)</label>
                            <input type="number" step="0.01" min="0" max="1" class="behavior-chance" 
                                   value="${behavior.probability || 0}" data-index="${index}">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Min Duration (sec)</label>
                            <input type="number" step="0.5" class="behavior-min-duration" 
                                   value="${behavior.min_duration || 5}" data-index="${index}">
                        </div>
                        <div class="form-group">
                            <label>Max Duration (sec)</label>
                            <input type="number" step="0.5" class="behavior-max-duration" 
                                   value="${behavior.max_duration || 15}" data-index="${index}">
                        </div>
                        <div class="form-group">
                            <label>Speed</label>
                            <input type="number" step="0.5" class="behavior-speed" 
                                   value="${behavior.speed || 3}" data-index="${index}">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Right Sprite</label>
                            <input type="text" class="behavior-sprite-right" 
                                   value="${escapeHtml(behavior.sprite_right || '')}" data-index="${index}"
                                   placeholder="filename_right.gif">
                        </div>
                        <div class="form-group">
                            <label>Left Sprite</label>
                            <input type="text" class="behavior-sprite-left" 
                                   value="${escapeHtml(behavior.sprite_left || '')}" data-index="${index}"
                                   placeholder="filename_left.gif">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Movement Type</label>
                            <select class="behavior-movement" data-index="${index}">
                                ${this.renderMovementOptions(behavior.movement)}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Group</label>
                            <input type="number" class="behavior-group" 
                                   value="${behavior.group || 0}" data-index="${index}">
                        </div>
                        <div class="form-group">
                            <label>Skip (random selection)</label>
                            <input type="checkbox" class="behavior-skip" 
                                   ${behavior.skip ? 'checked' : ''} data-index="${index}">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Linked Behavior</label>
                        <input type="text" class="behavior-linked" 
                               value="${escapeHtml(behavior.linked_behavior || '')}" data-index="${index}"
                               placeholder="next_behavior_name">
                    </div>
                </div>
            `;
        });

        return html;
    },

    renderMovementOptions(current) {
        const movements = ['None', 'All', 'HorizontalOnly', 'VerticalOnly', 'DiagonalOnly', 'Sleep', 'Dragged'];
        return movements.map(m => `<option value="${m}" ${current === m ? 'selected' : ''}>${m}</option>`).join('');
    },

    loadSpritePreview(ponyName, spriteName, canvas, behaviorIndex = null) {
        if (!ponyName || !spriteName || !canvas) return;

        const cacheKey = `${ponyName}/${spriteName}`;
        console.log('[BehaviorEditor] Loading preview for:', cacheKey, 'behaviorIndex:', behaviorIndex);

        if (this.gifCache.has(cacheKey)) {
            console.log('[BehaviorEditor] Using cached GIF for:', cacheKey);
            this.drawPreviewOnCanvas(canvas, this.gifCache.get(cacheKey));
            return;
        }

        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#2a2a3a';
        ctx.fillRect(0, 0, 64, 64);
        ctx.fillStyle = '#a6adc8';
        ctx.font = '10px monospace';
        ctx.fillText('Loading...', 8, 35);

        console.log('[BehaviorEditor] Requesting GIF load:', `gif:load:${ponyName}:${spriteName}`);
        canvas._pendingSprite = { ponyName, spriteName, behaviorIndex };
        EditorAPI.send(`gif:load:${ponyName}:${spriteName}`);
    },

    drawPreviewOnCanvas(canvas, gifData) {
        console.log('[BehaviorEditor] drawPreviewOnCanvas called');

        if (!canvas || !gifData || !gifData.frames || gifData.frames.length === 0) {
            console.log('[BehaviorEditor] No valid GIF data');
            const ctx = canvas?.getContext('2d');
            if (ctx) {
                ctx.fillStyle = '#f38ba8';
                ctx.fillRect(0, 0, 64, 64);
                ctx.fillStyle = '#ffffff';
                ctx.font = '10px monospace';
                ctx.fillText('No GIF', 12, 35);
            }
            return;
        }

        const ctx = canvas.getContext('2d');
        const frame = gifData.frames[0];
        const w = gifData.width;
        const h = gifData.height;

        console.log('[BehaviorEditor] Frame size:', w, 'x', h);

        let rgbaData;
        if (frame.data instanceof Uint8Array || frame.data instanceof Uint8ClampedArray) {
            rgbaData = new Uint8ClampedArray(frame.data);
        } else if (Array.isArray(frame.data)) {
            rgbaData = new Uint8ClampedArray(frame.data);
        } else {
            console.error('[BehaviorEditor] Invalid frame data type');
            return;
        }

        if (rgbaData.length !== w * h * 4) {
            console.error('[BehaviorEditor] Data size mismatch:', rgbaData.length, 'vs', w * h * 4);
            if (rgbaData.length === w * h) {
                const converted = new Uint8ClampedArray(w * h * 4);
                for (let i = 0; i < rgbaData.length; i++) {
                    const pixel = rgbaData[i];
                    converted[i * 4] = (pixel >> 16) & 0xFF;
                    converted[i * 4 + 1] = (pixel >> 8) & 0xFF;
                    converted[i * 4 + 2] = pixel & 0xFF;
                    converted[i * 4 + 3] = (pixel >> 24) & 0xFF;
                }
                rgbaData = converted;
            } else {
                return;
            }
        }

        const imgData = new ImageData(rgbaData, w, h);

        ctx.clearRect(0, 0, 64, 64);
        ctx.imageSmoothingEnabled = false;

        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = w;
        tempCanvas.height = h;
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.putImageData(imgData, 0, 0);
        ctx.drawImage(tempCanvas, 0, 0, w, h, 0, 0, 64, 64);

        if (canvas._animationId) {
            cancelAnimationFrame(canvas._animationId);
            canvas._animationId = null;
        }

        if (gifData.frames.length > 1) {
            console.log('[BehaviorEditor] Starting animation with', gifData.frames.length, 'frames');
            canvas._frames = gifData.frames;
            canvas._frameIndex = 0;
            canvas._frameDelay = (gifData.frames[0]?.delay || 10) * 10;
            canvas._lastFrameTime = performance.now();
            canvas._width = w;
            canvas._height = h;
            canvas._tempCanvas = document.createElement('canvas');
            canvas._tempCanvas.width = w;
            canvas._tempCanvas.height = h;

            const animate = (now) => {
                if (!canvas.isConnected) {
                    if (canvas._animationId) cancelAnimationFrame(canvas._animationId);
                    canvas._animationId = null;
                    return;
                }

                if (now - canvas._lastFrameTime >= canvas._frameDelay) {
                    canvas._lastFrameTime = now;
                    canvas._frameIndex = (canvas._frameIndex + 1) % canvas._frames.length;

                    const frameData = canvas._frames[canvas._frameIndex];
                    if (frameData && frameData.data) {
                        let frameRgba;
                        if (frameData.data instanceof Uint8Array || frameData.data instanceof Uint8ClampedArray) {
                            frameRgba = new Uint8ClampedArray(frameData.data);
                        } else if (Array.isArray(frameData.data)) {
                            frameRgba = new Uint8ClampedArray(frameData.data);
                        } else {
                            return;
                        }

                        if (frameRgba.length === canvas._width * canvas._height) {
                            const converted = new Uint8ClampedArray(canvas._width * canvas._height * 4);
                            for (let i = 0; i < frameRgba.length; i++) {
                                const pixel = frameRgba[i];
                                converted[i * 4] = (pixel >> 16) & 0xFF;
                                converted[i * 4 + 1] = (pixel >> 8) & 0xFF;
                                converted[i * 4 + 2] = pixel & 0xFF;
                                converted[i * 4 + 3] = (pixel >> 24) & 0xFF;
                            }
                            frameRgba = converted;
                        }

                        const imgData = new ImageData(frameRgba, canvas._width, canvas._height);
                        const tempCtx = canvas._tempCanvas.getContext('2d');
                        tempCtx.putImageData(imgData, 0, 0);

                        const ctx = canvas.getContext('2d');
                        ctx.clearRect(0, 0, 64, 64);
                        ctx.imageSmoothingEnabled = false;
                        ctx.drawImage(canvas._tempCanvas, 0, 0, canvas._width, canvas._height, 0, 0, 64, 64);
                    }
                }

                canvas._animationId = requestAnimationFrame(animate);
            };

            canvas._animationId = requestAnimationFrame(animate);
        }
    },

    loadAllPreviews() {
        if (!this.ponyName) return;

        const sprites = new Set();
        this.behaviors.forEach(behavior => {
            if (behavior.sprite_right && behavior.sprite_right.trim()) {
                sprites.add(behavior.sprite_right);
            }
            if (behavior.sprite_left && behavior.sprite_left.trim()) {
                sprites.add(behavior.sprite_left);
            }
        });

        console.log('[BehaviorEditor] Loading previews for sprites:', Array.from(sprites));

        sprites.forEach(spriteName => {
            EditorAPI.send(`gif:load:${this.ponyName}:${spriteName}`);
        });
    },

    bindEvents(container) {
        if (!container) return;

        if (this.ponyName) {
            setTimeout(() => {
                const previews = container.querySelectorAll('.sprite-preview');
                previews.forEach(preview => {
                    const spriteName = preview.dataset.sprite;
                    if (spriteName && spriteName.trim()) {
                        const canvas = preview.querySelector('.preview-canvas');
                        const behaviorIndex = preview.dataset.behaviorIndex;
                        this.loadSpritePreview(this.ponyName, spriteName, canvas, behaviorIndex);
                    }
                });
            }, 100);
        }

        const addBtn = container.querySelector('#add-behavior');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                EditorAPI.showNewBehaviorDialog((newBehavior) => {
                    this.behaviors.push(newBehavior);
                    EditorState.markModified();
                    PonyEditor.render(EditorState.getConfig());
                });
            });
        }

        container.querySelectorAll('.edit-behavior').forEach(btn => {
            btn.addEventListener('click', () => {
                const index = parseInt(btn.dataset.index);
                const behavior = this.behaviors[index];
                EditorAPI.showEditBehaviorDialog(behavior, (updatedBehavior) => {
                    this.behaviors[index] = updatedBehavior;
                    EditorState.markModified();
                    PonyEditor.render(EditorState.getConfig());
                });
            });
        });

        container.querySelectorAll('.delete-behavior').forEach(btn => {
            btn.addEventListener('click', () => {
                const index = parseInt(btn.dataset.index);
                this.behaviors.splice(index, 1);
                EditorState.markModified();
                PonyEditor.render(EditorState.getConfig());
            });
        });

        // Слушаем изменения полей спрайтов для перезагрузки превью
        container.querySelectorAll('.behavior-sprite-right, .behavior-sprite-left').forEach(input => {
            input.addEventListener('change', (e) => {
                const idx = parseInt(input.dataset.index);
                const field = input.classList.contains('behavior-sprite-right') ? 'sprite_right' : 'sprite_left';
                const newSprite = input.value;

                if (this.behaviors[idx]) {
                    this.behaviors[idx][field] = newSprite;
                    EditorState.markModified();

                    // Перезагружаем превью для этого спрайта
                    if (newSprite && newSprite.trim()) {
                        const side = field === 'sprite_right' ? 'right' : 'left';
                        const previewDiv = container.querySelector(`.sprite-preview[data-behavior-index="${idx}"][data-side="${side}"]`);
                        if (previewDiv) {
                            const canvas = previewDiv.querySelector('.preview-canvas');
                            this.loadSpritePreview(this.ponyName, newSprite, canvas, idx);
                        }
                    }
                }
            });
        });

        const updateField = (selector, field, parseAsFloat = false) => {
            container.querySelectorAll(selector).forEach(input => {
                input.addEventListener('change', () => {
                    const idx = parseInt(input.dataset.index);
                    let value = input.value;
                    if (input.type === 'checkbox') {
                        value = input.checked;
                    } else if (parseAsFloat) {
                        value = parseFloat(value) || 0;
                    }
                    if (this.behaviors[idx]) {
                        this.behaviors[idx][field] = value;
                        EditorState.markModified();
                    }
                });
            });
        };

        updateField('.behavior-name', 'name');
        updateField('.behavior-chance', 'probability', true);
        updateField('.behavior-min-duration', 'min_duration', true);
        updateField('.behavior-max-duration', 'max_duration', true);
        updateField('.behavior-speed', 'speed', true);
        updateField('.behavior-movement', 'movement');
        updateField('.behavior-group', 'group', true);
        updateField('.behavior-skip', 'skip');
        updateField('.behavior-linked', 'linked_behavior');
    }
};