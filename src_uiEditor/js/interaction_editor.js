// src_uiEditor/js/interaction_editor.js
const InteractionEditor = {
    render(interactions) {
        if (!interactions || interactions.length === 0) {
            return `<div class="card"><div class="empty-state">No interactions defined</div>
                    <button class="btn-secondary" id="add-interaction">+ Add Interaction</button></div>`;
        }
        let html = `<button class="btn-secondary" id="add-interaction" style="margin-bottom:16px">+ Add Interaction</button>`;
        interactions.forEach((interaction, i) => {
            html += `<div class="card"><div class="card-header"><h3>${escapeHtml(interaction.name || 'Unnamed')}</h3>
                    <button class="btn-icon delete-interaction" data-index="${i}">🗑️</button></div>
                    <div class="form-row"><div class="form-group"><label>Name</label>
                    <input type="text" class="interaction-name" value="${escapeHtml(interaction.name)}" data-index="${i}"></div>
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
    bindEvents(container) {}
};