// src_uiEditor/js/dialogs.js - основной файл

// ==================== DialogManager ====================
const DialogManager = {
    currentDialog: null,

    showModal: function(html, onSave, wide = false) {
        if (this.currentDialog) {
            this.currentDialog.remove();
        }

        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        const dialog = tempDiv.firstElementChild;
        if (wide) dialog.classList.add('wide');
        document.body.appendChild(dialog);
        this.currentDialog = dialog;

        dialog.querySelector('.dialog-close')?.addEventListener('click', () => this.closeDialog());
        dialog.querySelector('.dialog-cancel')?.addEventListener('click', () => this.closeDialog());
        dialog.querySelector('.dialog-save')?.addEventListener('click', () => {
            if (onSave) onSave();
            this.closeDialog();
        });

        dialog.addEventListener('click', (e) => {
            if (e.target === dialog) this.closeDialog();
        });
    },

    closeDialog: function() {
        if (this.currentDialog) {
            this.currentDialog.remove();
            this.currentDialog = null;
        }
    },

    // ==================== Behavior Dialog ====================
    // src_uiEditor/js/dialogs.js - добавить в DialogManager

// ==================== New Pony Dialog ====================
    showNewPonyDialog: function(onSave) {
        const html = `
        <div class="dialog-overlay" id="new-pony-dialog">
            <div class="dialog-content">
                <div class="dialog-header">
                    <h3>✨ Create New Pony</h3>
                    <button class="dialog-close">&times;</button>
                </div>
                <div class="dialog-body">
                    <div class="form-group">
                        <label>Pony Name</label>
                        <input type="text" id="new-pony-name" placeholder="Enter pony name..." autofocus>
                    </div>
                    <div class="form-group">
                        <label>Display Name (optional)</label>
                        <input type="text" id="new-pony-display-name" placeholder="Display name">
                    </div>
                    <div class="form-group">
                        <label>Categories (comma separated)</label>
                        <input type="text" id="new-pony-categories" placeholder="Main Ponies, Unicorns">
                    </div>
                    <div class="form-note">
                        <small>⚠️ The pony folder will be created in the Ponies directory.</small>
                    </div>
                </div>
                <div class="dialog-footer">
                    <button class="btn-secondary dialog-cancel">Cancel</button>
                    <button class="btn-primary dialog-save">Create</button>
                </div>
            </div>
        </div>
    `;

        this.showModal(html, () => {
            const name = document.getElementById('new-pony-name').value.trim();
            if (!name) {
                showStatus('Please enter a pony name', true);
                return;
            }

            // Проверка на недопустимые символы
            const invalidChars = /[<>:"/\\|?*{}\[\],]/;
            if (invalidChars.test(name)) {
                showStatus('Pony name contains invalid characters', true);
                return;
            }

            onSave({
                name: name,
                display_name: document.getElementById('new-pony-display-name').value.trim() || name,
                categories: document.getElementById('new-pony-categories').value.split(',').map(c => c.trim()).filter(c => c)
            });
        });
    },

    showBehaviorDialog: function(behavior, onSave) {
        const html = `
        <div class="dialog-overlay" id="behavior-dialog">
            <div class="dialog-content">
                <div class="dialog-header">
                    <h3>${behavior ? '✏️ Edit Behavior' : '✨ New Behavior'}</h3>
                    <button class="dialog-close">&times;</button>
                </div>
                <div class="dialog-body">
                    <div class="form-group">
                        <label>Name</label>
                        <input type="text" id="behavior-name" value="${escapeHtml(behavior?.name || '')}" placeholder="Behavior name">
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Chance (%)</label>
                            <input type="number" step="0.1" id="behavior-chance" value="${(behavior?.probability || 0.1) * 100}">
                        </div>
                        <div class="form-group">
                            <label>Speed</label>
                            <input type="number" step="0.5" id="behavior-speed" value="${behavior?.speed || 3}">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Min Duration (sec)</label>
                            <input type="number" step="0.5" id="behavior-min-duration" value="${behavior?.min_duration || 5}">
                        </div>
                        <div class="form-group">
                            <label>Max Duration (sec)</label>
                            <input type="number" step="0.5" id="behavior-max-duration" value="${behavior?.max_duration || 15}">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Right Sprite</label>
                            <input type="text" id="behavior-sprite-right" value="${escapeHtml(behavior?.sprite_right || '')}" placeholder="filename_right.gif">
                        </div>
                        <div class="form-group">
                            <label>Left Sprite</label>
                            <input type="text" id="behavior-sprite-left" value="${escapeHtml(behavior?.sprite_left || '')}" placeholder="filename_left.gif">
                        </div>
                    </div>
                    <div class="form-row sprite-preview-dialog">
                        <div class="form-group" style="text-align: center;">
                            <div class="sprite-preview-container">
                                <canvas id="sprite-preview-right" width="80" height="80" style="background: repeating-conic-gradient(#2a2a3a 0% 25%, #1a1a2a 0% 50%) 50% / 16px 16px; border-radius: 8px; image-rendering: crisp-edges;"></canvas>
                                <div><small>Right preview</small></div>
                            </div>
                        </div>
                        <div class="form-group" style="text-align: center;">
                            <div class="sprite-preview-container">
                                <canvas id="sprite-preview-left" width="80" height="80" style="background: repeating-conic-gradient(#2a2a3a 0% 25%, #1a1a2a 0% 50%) 50% / 16px 16px; border-radius: 8px; image-rendering: crisp-edges;"></canvas>
                                <div><small>Left preview</small></div>
                            </div>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Movement Type</label>
                            <select id="behavior-movement">
                                <option value="None">None</option>
                                <option value="All" ${behavior?.movement === 'All' ? 'selected' : ''}>All</option>
                                <option value="HorizontalOnly" ${behavior?.movement === 'HorizontalOnly' ? 'selected' : ''}>Horizontal Only</option>
                                <option value="VerticalOnly" ${behavior?.movement === 'VerticalOnly' ? 'selected' : ''}>Vertical Only</option>
                                <option value="DiagonalOnly" ${behavior?.movement === 'DiagonalOnly' ? 'selected' : ''}>Diagonal Only</option>
                                <option value="Sleep" ${behavior?.movement === 'Sleep' ? 'selected' : ''}>Sleep</option>
                                <option value="Dragged" ${behavior?.movement === 'Dragged' ? 'selected' : ''}>Dragged</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Group</label>
                            <input type="number" id="behavior-group" value="${behavior?.group || 0}">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Linked Behavior</label>
                        <input type="text" id="behavior-linked" value="${escapeHtml(behavior?.linked_behavior || '')}" placeholder="Next behavior in chain">
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Start Speech</label>
                            <input type="text" id="behavior-start-speech" value="${escapeHtml(behavior?.start_speech || '')}">
                        </div>
                        <div class="form-group">
                            <label>End Speech</label>
                            <input type="text" id="behavior-end-speech" value="${escapeHtml(behavior?.end_speech || '')}">
                        </div>
                    </div>
                    <div class="form-check">
                        <input type="checkbox" id="behavior-skip" ${behavior?.skip ? 'checked' : ''}>
                        <label>Skip (don't use randomly)</label>
                    </div>
                    <div class="form-check">
                        <input type="checkbox" id="behavior-no-repeat" ${behavior?.do_not_repeat_animations ? 'checked' : ''}>
                        <label>Don't repeat animations</label>
                    </div>
                </div>
                <div class="dialog-footer">
                    <button class="btn-secondary dialog-cancel">Cancel</button>
                    <button class="btn-primary dialog-save">Save</button>
                </div>
            </div>
        </div>
    `;

        this.showModal(html, () => {
            onSave({
                name: document.getElementById('behavior-name').value,
                probability: parseFloat(document.getElementById('behavior-chance').value) / 100,
                speed: parseFloat(document.getElementById('behavior-speed').value),
                min_duration: parseFloat(document.getElementById('behavior-min-duration').value),
                max_duration: parseFloat(document.getElementById('behavior-max-duration').value),
                sprite_right: document.getElementById('behavior-sprite-right').value,
                sprite_left: document.getElementById('behavior-sprite-left').value,
                movement: document.getElementById('behavior-movement').value,
                group: parseInt(document.getElementById('behavior-group').value),
                linked_behavior: document.getElementById('behavior-linked').value,
                start_speech: document.getElementById('behavior-start-speech').value,
                end_speech: document.getElementById('behavior-end-speech').value,
                skip: document.getElementById('behavior-skip').checked,
                do_not_repeat_animations: document.getElementById('behavior-no-repeat').checked,
            });
        });

        // Загружаем превью спрайтов
        const ponyName = EditorState.currentPony;
        if (ponyName) {
            const rightSprite = document.getElementById('behavior-sprite-right').value;
            const leftSprite = document.getElementById('behavior-sprite-left').value;

            if (rightSprite && rightSprite.trim()) {
                EditorAPI.send(`gif:load:${ponyName}:${rightSprite}`);
            }
            if (leftSprite && leftSprite.trim()) {
                EditorAPI.send(`gif:load:${ponyName}:${leftSprite}`);
            }
        }

        // Слушаем изменения полей спрайтов для обновления превью
        const rightInput = document.getElementById('behavior-sprite-right');
        const leftInput = document.getElementById('behavior-sprite-left');
        const rightPreview = document.getElementById('sprite-preview-right');
        const leftPreview = document.getElementById('sprite-preview-left');
        const ponyName2 = EditorState.currentPony;

        if (rightInput && rightPreview && ponyName2) {
            rightInput.addEventListener('change', () => {
                const newSprite = rightInput.value;
                if (newSprite && newSprite.trim()) {
                    EditorAPI.send(`gif:load:${ponyName2}:${newSprite}`);
                } else {
                    const ctx = rightPreview.getContext('2d');
                    ctx.clearRect(0, 0, 80, 80);
                    ctx.fillStyle = '#2a2a3a';
                    ctx.fillRect(0, 0, 80, 80);
                    ctx.fillStyle = '#a6adc8';
                    ctx.font = '10px monospace';
                    ctx.fillText('No sprite', 15, 45);
                }
            });
        }

        if (leftInput && leftPreview && ponyName2) {
            leftInput.addEventListener('change', () => {
                const newSprite = leftInput.value;
                if (newSprite && newSprite.trim()) {
                    EditorAPI.send(`gif:load:${ponyName2}:${newSprite}`);
                } else {
                    const ctx = leftPreview.getContext('2d');
                    ctx.clearRect(0, 0, 80, 80);
                    ctx.fillStyle = '#2a2a3a';
                    ctx.fillRect(0, 0, 80, 80);
                    ctx.fillStyle = '#a6adc8';
                    ctx.font = '10px monospace';
                    ctx.fillText('No sprite', 15, 45);
                }
            });
        }
    },

    // ==================== Speech Dialog ====================
    showSpeechDialog: function(speech, onSave) {
        const html = `
            <div class="dialog-overlay" id="speech-dialog">
                <div class="dialog-content">
                    <div class="dialog-header">
                        <h3>${speech ? '💬 Edit Speech' : '💬 New Speech'}</h3>
                        <button class="dialog-close">&times;</button>
                    </div>
                    <div class="dialog-body">
                        <div class="form-group">
                            <label>Name</label>
                            <input type="text" id="speech-name" value="${escapeHtml(speech?.name || '')}" placeholder="Speech name">
                        </div>
                        <div class="form-group">
                            <label>Text</label>
                            <textarea id="speech-text" rows="3" placeholder="What the pony says...">${escapeHtml(speech?.text || '')}</textarea>
                        </div>
                        <div class="form-group">
                            <label>Sound File (MP3/OGG)</label>
                            <input type="text" id="speech-sound" value="${escapeHtml(speech?.sound_files?.[0] || '')}" placeholder="sound.mp3">
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Group</label>
                                <input type="number" id="speech-group" value="${speech?.group || 0}">
                            </div>
                            <div class="form-group">
                                <label>Frequency</label>
                                <input type="number" step="0.1" id="speech-frequency" value="${speech?.frequency || 0}">
                            </div>
                        </div>
                        <div class="form-check">
                            <input type="checkbox" id="speech-skip" ${speech?.skip ? 'checked' : ''}>
                            <label>Skip (use only for specific behaviors)</label>
                        </div>
                    </div>
                    <div class="dialog-footer">
                        <button class="btn-secondary dialog-cancel">Cancel</button>
                        <button class="btn-primary dialog-save">Save</button>
                    </div>
                </div>
            </div>
        `;

        this.showModal(html, () => {
            onSave({
                name: document.getElementById('speech-name').value,
                text: document.getElementById('speech-text').value,
                sound_files: document.getElementById('speech-sound').value ? [document.getElementById('speech-sound').value] : [],
                group: parseInt(document.getElementById('speech-group').value),
                frequency: parseFloat(document.getElementById('speech-frequency').value),
                skip: document.getElementById('speech-skip').checked,
            });
        });
    },

    // ==================== Effect Dialog ====================
    showEffectDialog: function(effect, behaviors, onSave) {
        const directionOptions = (selected) => {
            const dirs = ['TopLeft', 'TopCenter', 'TopRight', 'MiddleLeft', 'MiddleCenter', 'MiddleRight', 'BottomLeft', 'BottomCenter', 'BottomRight'];
            return dirs.map(d => `<option value="${d}" ${selected === d ? 'selected' : ''}>${d}</option>`).join('');
        };

        const html = `
            <div class="dialog-overlay" id="effect-dialog">
                <div class="dialog-content wide">
                    <div class="dialog-header">
                        <h3>${effect ? '✨ Edit Effect' : '✨ New Effect'}</h3>
                        <button class="dialog-close">&times;</button>
                    </div>
                    <div class="dialog-body">
                        <div class="form-group">
                            <label>Name</label>
                            <input type="text" id="effect-name" value="${escapeHtml(effect?.name || '')}" placeholder="Effect name">
                        </div>
                        <div class="form-group">
                            <label>Linked Behavior</label>
                            <select id="effect-linked">
                                <option value="">None</option>
                                ${behaviors.map(b => `<option value="${b}" ${effect?.linked === b ? 'selected' : ''}>${b}</option>`).join('')}
                            </select>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Right Sprite</label>
                                <input type="text" id="effect-sprite-right" value="${escapeHtml(effect?.sprite_right || '')}" placeholder="effect_right.gif">
                            </div>
                            <div class="form-group">
                                <label>Left Sprite</label>
                                <input type="text" id="effect-sprite-left" value="${escapeHtml(effect?.sprite_left || '')}" placeholder="effect_left.gif">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Duration (sec)</label>
                                <input type="number" step="0.5" id="effect-duration" value="${effect?.duration || 5}">
                            </div>
                            <div class="form-group">
                                <label>Repeat Delay (sec)</label>
                                <input type="number" step="0.5" id="effect-repeat-delay" value="${effect?.repeat_delay || 0}">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Placement Right</label>
                                <select id="effect-placement-right">${directionOptions(effect?.placement_right || 'MiddleCenter')}</select>
                            </div>
                            <div class="form-group">
                                <label>Placement Left</label>
                                <select id="effect-placement-left">${directionOptions(effect?.placement_left || 'MiddleCenter')}</select>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Centering Right</label>
                                <select id="effect-centering-right">${directionOptions(effect?.centering_right || 'MiddleCenter')}</select>
                            </div>
                            <div class="form-group">
                                <label>Centering Left</label>
                                <select id="effect-centering-left">${directionOptions(effect?.centering_left || 'MiddleCenter')}</select>
                            </div>
                        </div>
                        <div class="form-check">
                            <input type="checkbox" id="effect-follow" ${effect?.follow ? 'checked' : ''}>
                            <label>Effect follows pony</label>
                        </div>
                        <div class="form-check">
                            <input type="checkbox" id="effect-no-repeat" ${effect?.do_not_repeat_animations ? 'checked' : ''}>
                            <label>Don't repeat animations</label>
                        </div>
                    </div>
                    <div class="dialog-footer">
                        <button class="btn-secondary dialog-cancel">Cancel</button>
                        <button class="btn-primary dialog-save">Save</button>
                    </div>
                </div>
            </div>
        `;

        this.showModal(html, () => {
            onSave({
                name: document.getElementById('effect-name').value,
                linked: document.getElementById('effect-linked').value,
                sprite_right: document.getElementById('effect-sprite-right').value,
                sprite_left: document.getElementById('effect-sprite-left').value,
                duration: parseFloat(document.getElementById('effect-duration').value),
                repeat_delay: parseFloat(document.getElementById('effect-repeat-delay').value),
                placement_right: document.getElementById('effect-placement-right').value,
                placement_left: document.getElementById('effect-placement-left').value,
                centering_right: document.getElementById('effect-centering-right').value,
                centering_left: document.getElementById('effect-centering-left').value,
                follow: document.getElementById('effect-follow').checked,
                do_not_repeat_animations: document.getElementById('effect-no-repeat').checked,
            });
        }, true);
    },

    // ==================== Interaction Dialog ====================
    showInteractionDialog: function(interaction, targets, behaviors, onSave) {
        const html = `
            <div class="dialog-overlay" id="interaction-dialog">
                <div class="dialog-content wide">
                    <div class="dialog-header">
                        <h3>${interaction ? '🤝 Edit Interaction' : '🤝 New Interaction'}</h3>
                        <button class="dialog-close">&times;</button>
                    </div>
                    <div class="dialog-body">
                        <div class="form-group">
                            <label>Name</label>
                            <input type="text" id="interaction-name" value="${escapeHtml(interaction?.name || '')}" placeholder="Interaction name">
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Chance (%)</label>
                                <input type="number" step="0.1" id="interaction-chance" value="${(interaction?.probability || 0.25) * 100}">
                            </div>
                            <div class="form-group">
                                <label>Proximity (px)</label>
                                <input type="number" id="interaction-proximity" value="${interaction?.cooldown || 125}">
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Targets</label>
                            <div id="interaction-targets-list" class="checkbox-group">
                                ${targets.map(t => `
                                    <label class="checkbox-label">
                                        <input type="checkbox" value="${t}" ${interaction?.targets?.includes(t) ? 'checked' : ''}>
                                        ${t}
                                    </label>
                                `).join('')}
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Activation Type</label>
                            <select id="interaction-activation">
                                <option value="One" ${interaction?.activation === 'One' ? 'selected' : ''}>One - Only nearest pony</option>
                                <option value="Any" ${interaction?.activation === 'Any' ? 'selected' : ''}>Any - Any available pony</option>
                                <option value="All" ${interaction?.activation === 'All' ? 'selected' : ''}>All - All targets must be available</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Behaviors to trigger</label>
                            <div id="interaction-behaviors-list" class="checkbox-group">
                                ${behaviors.map(b => `
                                    <label class="checkbox-label">
                                        <input type="checkbox" value="${b}" ${interaction?.behaviors?.includes(b) ? 'checked' : ''}>
                                        ${b}
                                    </label>
                                `).join('')}
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Reactivation Delay (sec)</label>
                            <input type="number" step="0.5" id="interaction-delay" value="${interaction?.reactivation_delay || 60}">
                        </div>
                    </div>
                    <div class="dialog-footer">
                        <button class="btn-secondary dialog-cancel">Cancel</button>
                        <button class="btn-primary dialog-save">Save</button>
                    </div>
                </div>
            </div>
        `;

        this.showModal(html, () => {
            const selectedTargets = Array.from(document.querySelectorAll('#interaction-targets-list input:checked'))
                .map(cb => cb.value);
            const selectedBehaviors = Array.from(document.querySelectorAll('#interaction-behaviors-list input:checked'))
                .map(cb => cb.value);

            onSave({
                name: document.getElementById('interaction-name').value,
                probability: parseFloat(document.getElementById('interaction-chance').value) / 100,
                cooldown: parseInt(document.getElementById('interaction-proximity').value),
                targets: selectedTargets,
                activation: document.getElementById('interaction-activation').value,
                behaviors: selectedBehaviors,
                reactivation_delay: parseFloat(document.getElementById('interaction-delay').value),
            });
        }, true);
    }
};