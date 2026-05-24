// src_uiEditor/js/state.js
const EditorState = {
    currentPony: null,
    originalConfig: null,
    modified: false,
    allPonies: [],
    currentTab: 'basic',

    setPony(pony, config) {
        console.log('[State] setPony called:', pony);
        console.log('[State] Config received:', config);
        console.log('[State] Config behaviors:', config?.behaviors?.length);

        this.currentPony = pony;
        this.originalConfig = JSON.parse(JSON.stringify(config));
        this.modified = false;
        this.updateModifiedStatus();

        console.log('[State] State updated, currentPony:', this.currentPony);
        console.log('[State] Config stored, behaviors:', this.originalConfig?.behaviors?.length);
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