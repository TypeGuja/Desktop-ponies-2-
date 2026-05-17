// Управление состоянием редактора
const EditorState = {
    currentPony: null,
    originalConfig: null,
    modified: false,
    allPonies: [],
    currentTab: 'basic',

    setPony(pony, config) {
        this.currentPony = pony;
        this.originalConfig = JSON.parse(JSON.stringify(config));
        this.modified = false;
        this.updateModifiedStatus();
    },

    markModified() {
        this.modified = true;
        this.updateModifiedStatus();
    },

    updateModifiedStatus() {
        const saveBtn = document.getElementById('btn-save');
        if (saveBtn) {
            saveBtn.disabled = !this.modified;
        }
        const title = document.querySelector('.editor-header h1');
        if (title && this.currentPony) {
            title.innerHTML = this.modified ? `🦄 ✏️ ${this.currentPony}` : `🦄 ${this.currentPony}`;
        }
    },

    hasChanges() {
        return this.modified;
    },

    getConfig() {
        return this.originalConfig;
    }
};