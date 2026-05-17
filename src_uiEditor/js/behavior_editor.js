// Редактор поведений
const BehaviorEditor = {
    behaviors: [],

    render(behaviors) {
        this.behaviors = behaviors || [];

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
                        <button class="btn-icon delete-behavior" data-index="${index}">🗑️</button>
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
        const movements = ['None', 'All', 'Horizontal_Only', 'Vertical_Only', 'Diagonal_Only', 'Sleep', 'Dragged', 'MouseOver'];
        return movements.map(m => `<option value="${m}" ${current === m ? 'selected' : ''}>${m}</option>`).join('');
    },

    bindEvents(container) {
        if (!container) return;

        // Добавление поведения
        const addBtn = container.querySelector('#add-behavior');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                this.behaviors.push({
                    name: 'New Behavior',
                    probability: 0.1,
                    min_duration: 5,
                    max_duration: 15,
                    speed: 3,
                    sprite_right: '',
                    sprite_left: '',
                    movement: 'All',
                    linked_behavior: '',
                    skip: false,
                    group: 0
                });
                EditorState.markModified();
                PonyEditor.render(EditorState.getConfig());
            });
        }

        // Удаление поведения
        container.querySelectorAll('.delete-behavior').forEach(btn => {
            btn.addEventListener('click', () => {
                const index = parseInt(btn.dataset.index);
                this.behaviors.splice(index, 1);
                EditorState.markModified();
                PonyEditor.render(EditorState.getConfig());
            });
        });

        // Обновление полей
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
                    this.behaviors[idx][field] = value;
                    EditorState.markModified();
                });
            });
        };

        updateField('.behavior-name', 'name');
        updateField('.behavior-chance', 'probability', true);
        updateField('.behavior-min-duration', 'min_duration', true);
        updateField('.behavior-max-duration', 'max_duration', true);
        updateField('.behavior-speed', 'speed', true);
        updateField('.behavior-sprite-right', 'sprite_right');
        updateField('.behavior-sprite-left', 'sprite_left');
        updateField('.behavior-movement', 'movement');
        updateField('.behavior-group', 'group', true);
        updateField('.behavior-skip', 'skip');
        updateField('.behavior-linked', 'linked_behavior');
    }
};