const EditorAPI = {
    send: function(message) {
        console.log('[API] Sending:', message);
        try {
            if (window.ipc && window.ipc.postMessage) {
                window.ipc.postMessage(message);
                return true;
            }
        } catch(e) { console.warn('IPC via window.ipc failed:', e); }
        try {
            if (window.webkit?.messageHandlers?.ipc) {
                window.webkit.messageHandlers.ipc.postMessage(message);
                return true;
            }
        } catch(e) { console.warn('IPC via webkit failed:', e); }
        try {
            if (window.external && typeof window.external.sendMessage === 'function') {
                window.external.sendMessage(message);
                return true;
            }
        } catch(e) {}
        console.warn('[Editor] No IPC handler found, message not sent:', message);
        return false;
    },
    loadPonies: function() { this.send('editor:load_ponies'); },
    loadPony: function(name) { this.send('editor:load_pony:' + name); },
    savePony: function(config) {
        const saveData = {
            name: config.name,
            display_name: config.display_name || config.name,
            categories: config.categories || [],
            tags: config.tags || [],
            behaviors: config.behaviors || [],
            speaks: config.speaks || [],
            interactions: config.interactions || [],
            effects: config.effects || []
        };
        this.send('editor:save_pony:' + JSON.stringify(saveData));
    },
    showNewBehaviorDialog: function(onSave) { DialogManager.showBehaviorDialog(null, onSave); },
    showEditBehaviorDialog: function(behavior, onSave) { DialogManager.showBehaviorDialog(behavior, onSave); },
    showNewSpeechDialog: function(onSave) { DialogManager.showSpeechDialog(null, onSave); },
    showEditSpeechDialog: function(speech, onSave) { DialogManager.showSpeechDialog(speech, onSave); },
    deletePony: function(ponyName) { this.send('editor:delete_pony:' + ponyName); },
    showNewEffectDialog: function(behaviors, onSave) { DialogManager.showEffectDialog(null, behaviors, onSave); },
    showEditEffectDialog: function(effect, behaviors, onSave) { DialogManager.showEffectDialog(effect, behaviors, onSave); },
    showNewInteractionDialog: function(targets, behaviors, onSave) { DialogManager.showInteractionDialog(null, targets, behaviors, onSave); },
    showEditInteractionDialog: function(interaction, targets, behaviors, onSave) { DialogManager.showInteractionDialog(interaction, targets, behaviors, onSave); }
};