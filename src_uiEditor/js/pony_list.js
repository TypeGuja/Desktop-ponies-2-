// src_uiEditor/js/pony_list.js
const PonyList = {
    container: null,
    searchInput: null,
    currentSelected: null,
    init: function() {
        this.container = document.getElementById('pony-list');
        this.searchInput = document.getElementById('search-pony');
        if (this.searchInput) {
            this.searchInput.addEventListener('input', debounce(() => this.render(), 300));
        }
    },
    render: function() {
        if (!this.container) return;
        const searchTerm = this.searchInput?.value.toLowerCase() || '';
        const filtered = EditorState.allPonies.filter(p => p.toLowerCase().includes(searchTerm));
        if (filtered.length === 0) {
            this.container.innerHTML = '<div class="empty-state">No ponies found</div>';
            return;
        }
        this.container.innerHTML = filtered.map(name => `
            <div class="pony-item ${this.currentSelected === name ? 'selected' : ''}" data-name="${escapeHtml(name)}">
                <div class="pony-info">
                    <div class="pony-icon">🦄</div>
                    <div class="pony-name">${escapeHtml(name)}</div>
                </div>
                <div class="pony-actions">
                    <button class="edit-btn" data-name="${escapeHtml(name)}">✏️</button>
                </div>
            </div>
        `).join('');
        this.container.querySelectorAll('.pony-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.edit-btn')) this.selectPony(item.dataset.name);
            });
            const editBtn = item.querySelector('.edit-btn');
            if (editBtn) {
                editBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.selectPony(editBtn.dataset.name);
                });
            }
        });
    },
    selectPony: function(name) {
        if (EditorState.hasChanges() && !confirm('You have unsaved changes. Load another pony anyway?')) return;
        this.currentSelected = name;
        this.render();
        showStatus(`Loading ${name}...`);
        EditorAPI.loadPony(name);
    },
    updateList: function(ponies) {
        EditorState.allPonies = ponies || [];
        const countEl = document.getElementById('pony-count');
        if (countEl) countEl.textContent = `${EditorState.allPonies.length} ponies loaded`;
        this.render();
    }
};