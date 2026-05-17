const EffectEditor = {
    effects: [],

    render(effects) {
        this.effects = effects || [];

        if (this.effects.length === 0) {
            return `<div class="card"><div class="empty-state">No effects defined</div>
                    <button class="btn-secondary" id="add-effect">+ Add Effect</button></div>`;
        }

        let html = `<button class="btn-secondary" id="add-effect" style="margin-bottom:16px">+ Add Effect</button>`;

        this.effects.forEach((effect, i) => {
            html += `<div class="card">
                        <div class="card-header">
                            <h3>${escapeHtml(effect.name || 'Unnamed')}</h3>
                            <button class="btn-icon delete-effect" data-index="${i}">🗑️</button>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Name</label>
                                <input type="text" class="effect-name" value="${escapeHtml(effect.name)}" data-index="${i}">
                            </div>
                            <div class="form-group">
                                <label>Linked Behavior</label>
                                <input type="text" class="effect-linked" value="${escapeHtml(effect.linked)}" data-index="${i}">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Right Sprite</label>
                                <input type="text" class="effect-sprite-right" value="${escapeHtml(effect.sprite_right)}" data-index="${i}">
                            </div>
                            <div class="form-group">
                                <label>Left Sprite</label>
                                <input type="text" class="effect-sprite-left" value="${escapeHtml(effect.sprite_left)}" data-index="${i}">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Duration (sec)</label>
                                <input type="number" step="0.5" class="effect-duration" value="${effect.duration || 5}" data-index="${i}">
                            </div>
                            <div class="form-group">
                                <label>Delay (sec)</label>
                                <input type="number" step="0.5" class="effect-delay" value="${effect.delay || 0}" data-index="${i}">
                            </div>
                        </div>
                    </div>`;
        });
        return html;
    },

    bindEvents(container) {
        if (!container) return;

        const addBtn = container.querySelector('#add-effect');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                this.effects.push({
                    name: 'New Effect',
                    linked: '',
                    sprite_right: '',
                    sprite_left: '',
                    duration: 5,
                    delay: 0
                });
                EditorState.markModified();
                PonyEditor.render(EditorState.getConfig());
            });
        }

        container.querySelectorAll('.delete-effect').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = parseInt(btn.dataset.index);
                this.effects.splice(idx, 1);
                EditorState.markModified();
                PonyEditor.render(EditorState.getConfig());
            });
        });

        const updateField = (selector, field) => {
            container.querySelectorAll(selector).forEach(input => {
                input.addEventListener('change', () => {
                    const idx = parseInt(input.dataset.index);
                    this.effects[idx][field] = input.type === 'number' ? parseFloat(input.value) : input.value;
                    EditorState.markModified();
                });
            });
        };

        updateField('.effect-name', 'name');
        updateField('.effect-linked', 'linked');
        updateField('.effect-sprite-right', 'sprite_right');
        updateField('.effect-sprite-left', 'sprite_left');
        updateField('.effect-duration', 'duration');
        updateField('.effect-delay', 'delay');
    }
};