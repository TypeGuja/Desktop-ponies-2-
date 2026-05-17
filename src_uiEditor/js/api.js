// IPC коммуникация с Rust
const EditorAPI = {
    send: function(message) {
        console.log('[Editor] Sending IPC:', message);
        try {
            if (window.ipc && window.ipc.postMessage) {
                window.ipc.postMessage(message);
                return true;
            }
        } catch(e) {
            console.warn('IPC via window.ipc failed:', e);
        }
        try {
            if (window.webkit?.messageHandlers?.ipc) {
                window.webkit.messageHandlers.ipc.postMessage(message);
                return true;
            }
        } catch(e) {
            console.warn('IPC via webkit failed:', e);
        }
        try {
            if (window.external && typeof window.external.sendMessage === 'function') {
                window.external.sendMessage(message);
                return true;
            }
        } catch(e) {}

        console.warn('[Editor] No IPC handler found, message not sent:', message);
        return false;
    },

    loadPonies: function() {
        this.send('editor:load_ponies');
    },

    loadPony: function(name) {
        this.send('editor:load_pony:' + name);
    },

    savePony: function(config) {
        this.send('editor:save_pony:' + JSON.stringify(config));
    }
};