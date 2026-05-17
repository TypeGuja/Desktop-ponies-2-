// Точка входа
document.addEventListener('DOMContentLoaded', () => {
    console.log('Pony Editor initializing...');

    // Инициализация компонентов
    PonyList.init();
    PonyEditor.init();

    // Загрузка списка пони
    EditorAPI.loadPonies();

    // Кнопка сохранения
    const saveBtn = document.getElementById('btn-save');
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            if (EditorState.currentPony && EditorState.originalConfig) {
                console.log('[Editor] Saving pony:', EditorState.currentPony);
                EditorAPI.savePony(EditorState.originalConfig);
                EditorState.modified = false;
                EditorState.updateModifiedStatus();
                showStatus(`Saved ${EditorState.currentPony}`);
            }
        });
    }

    // Кнопка закрытия
    const closeBtn = document.getElementById('btn-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            if (EditorState.hasChanges()) {
                if (confirm('Save changes before closing?')) {
                    saveBtn?.click();
                }
            }
            // Отправляем сообщение о закрытии окна
            EditorAPI.send('editor:close');
        });
    }

    // Получение сообщений от Rust
    window.editorReceive = (message) => {
        console.log('[Editor] Received from Rust:', message);
        try {
            const data = typeof message === 'string' ? JSON.parse(message) : message;
            switch (data.type) {
                case 'ponies_list':
                    console.log('[Editor] Ponies list:', data.data);
                    PonyList.updateList(data.data);
                    break;
                case 'pony_config':
                    console.log('[Editor] Pony config for:', data.pony_name);
                    EditorState.setPony(data.pony_name, data.data);
                    PonyEditor.render(data.data);
                    showStatus(`Loaded ${data.pony_name}`);
                    break;
                case 'save_success':
                    showStatus(`Saved successfully!`);
                    break;
                case 'save_error':
                    showStatus(`Error: ${data.message}`, true);
                    break;
                case 'error':
                    showStatus(`Error: ${data.message}`, true);
                    break;
                default:
                    console.log('[Editor] Unknown message type:', data.type);
            }
        } catch(e) {
            console.error('[Editor] Failed to parse message:', message, e);
        }
    };

    showStatus('Ready');
    console.log('[Editor] Initialization complete');
});