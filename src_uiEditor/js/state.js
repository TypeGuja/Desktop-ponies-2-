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
        // ИСПРАВЛЕНО: раньше здесь безусловно возвращался originalConfig —
        // замороженный снимок конфига, сделанный один раз при загрузке пони
        // (JSON.parse(JSON.stringify(...))). Все реальные правки (имя,
        // категории и т.д.) применяются к ДРУГОМУ объекту — PonyEditor.currentPonyConfig.
        // Из-за этого:
        //  1) PonyEditor.render(EditorState.getConfig()), вызываемый после
        //     каждого add/delete behavior/speech/effect, отбрасывал все ещё
        //     не сохранённые правки и откатывал форму к исходным данным;
        //  2) кнопка Save брала display_name/categories/interactions из
        //     этого же замороженного снимка — эти поля никогда не
        //     сохранялись, даже если пользователь их изменил.
        // Теперь возвращаем актуальный, живой объект, если он есть.
        if (window.PonyEditor && PonyEditor.currentPonyConfig) {
            return PonyEditor.currentPonyConfig;
        }
        return this.originalConfig;
    }
};