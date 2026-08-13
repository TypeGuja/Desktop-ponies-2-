// src_uiEditor/js/interaction_editor.js
//
// ИСПРАВЛЕНО: раньше этот модуль не хранил своё состояние (не было
// this.interactions) и bindEvents(container) была пустой заглушкой — ни
// кнопки "+ Add Interaction"/"🗑️ Delete", ни одно из полей формы не были
// никак подключены. Вкладка Interactions визуально существовала, но не
// работала вообще: ничего нельзя было ни добавить, ни изменить, ни удалить.
// Реализация приведена в соответствие с рабочим паттерном speech_editor.js /
// effect_editor.js, а main.js теперь берёт InteractionEditor.interactions
// при сохранении (раньше сохранение читало устаревший, не связанный со
// вкладкой снимок конфига).
const InteractionEditor = {
    interactions: [],

    render(interactions) {
        this.interactions = interactions || [];

        if (this.interactions.length === 0) {
            return `<div class="card"><div class="empty-state">No interactions defined</div>
                    <button class="btn-secondary" id="add-interaction">+ Add Interaction</button></div>`;
        }
        let html = `<button class="btn-secondary" id="add-interaction" style="margin-bottom:16px">+ Add Interaction</button>`;
        this.interactions.forEach((interaction, i) => {
            html += `<div class="card"><div class="card-header"><h3>${escapeHtml(interaction.name || 'Unnamed')}</h3>
                    <button class="btn-icon delete-interaction" data-index="${i}">🗑️</button></div>
                    <div class="form-row"><div class="form-group"><label>Name</label>
                    <input type="text" class="interaction-name" value="${escapeHtml(interaction.name || '')}" data-index="${i}"></div>
                    <div class="form-group"><label>Chance (0-1)</label>
                    <input type="number" step="0.01" min="0" max="1" class="interaction-chance" value="${interaction.probability || 0}" data-index="${i}"></div></div>
                    <div class="form-row"><div class="form-group"><label>Proximity (px)</label>
                    <input type="number" class="interaction-proximity" value="${interaction.cooldown || 125}" data-index="${i}"></div>
                    <div class="form-group"><label>Target Activation</label>
                    <select class="interaction-target-activation" data-index="${i}">
                        <option ${interaction.target_count === 'One' ? 'selected' : ''}>One</option>
                        <option ${interaction.target_count === 'Any' ? 'selected' : ''}>Any</option>
                        <option ${interaction.target_count === 'All' ? 'selected' : ''}>All</option>
                    </select></div></div>
                    <div class="form-group"><label>Targets (comma separated)</label>
                    <input type="text" class="interaction-targets" value="${escapeHtml((interaction.targets || []).join(', '))}" data-index="${i}"></div>
                    <div class="form-group"><label>Behaviors (comma separated)</label>
                    <input type="text" class="interaction-behaviors" value="${escapeHtml((interaction.behaviors || []).join(', '))}" data-index="${i}"></div>
                    <div class="form-group"><label>Duration (sec)</label>
                    <input type="number" class="interaction-duration" value="${interaction.duration || 60}" data-index="${i}"></div></div>`;
        });
        return html;
    },

    bindEvents(container) {
        if (!container) return;

        const addBtn = container.querySelector('#add-interaction');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                this.interactions.push({
                    name: 'New Interaction',
                    probability: 0.1,
                    cooldown: 125,
                    targets: [],
                    target_count: 'One',
                    behaviors: [],
                    duration: 60,
                    reactivation_delay: 0,
                    initiator_name: ''
                });
                EditorState.markModified();
                PonyEditor.render(EditorState.getConfig());
            });
        }

        container.querySelectorAll('.delete-interaction').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = parseInt(btn.dataset.index);
                this.interactions.splice(idx, 1);
                EditorState.markModified();
                PonyEditor.render(EditorState.getConfig());
            });
        });

        container.querySelectorAll('.interaction-name').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                if (this.interactions[idx]) {
                    this.interactions[idx].name = input.value;
                    EditorState.markModified();
                }
            });
        });

        container.querySelectorAll('.interaction-chance').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                if (this.interactions[idx]) {
                    this.interactions[idx].probability = parseFloat(input.value) || 0;
                    EditorState.markModified();
                }
            });
        });

        container.querySelectorAll('.interaction-proximity').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                if (this.interactions[idx]) {
                    this.interactions[idx].cooldown = parseFloat(input.value) || 0;
                    EditorState.markModified();
                }
            });
        });

        container.querySelectorAll('.interaction-target-activation').forEach(select => {
            select.addEventListener('change', () => {
                const idx = parseInt(select.dataset.index);
                if (this.interactions[idx]) {
                    this.interactions[idx].target_count = select.value;
                    EditorState.markModified();
                }
            });
        });

        container.querySelectorAll('.interaction-targets').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                if (this.interactions[idx]) {
                    this.interactions[idx].targets = input.value.split(',').map(s => s.trim()).filter(s => s);
                    EditorState.markModified();
                }
            });
        });

        container.querySelectorAll('.interaction-behaviors').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                if (this.interactions[idx]) {
                    this.interactions[idx].behaviors = input.value.split(',').map(s => s.trim()).filter(s => s);
                    EditorState.markModified();
                }
            });
        });

        container.querySelectorAll('.interaction-duration').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                if (this.interactions[idx]) {
                    this.interactions[idx].duration = parseFloat(input.value) || 0;
                    EditorState.markModified();
                }
            });
        });
    }
};
