// src_uiEditor/js/main.js - БЕЗ TRACE

document.addEventListener('DOMContentLoaded', () => {
    console.log('[MAIN] Pony Editor initializing...');

    PonyList.init();
    PonyEditor.init();

    EditorAPI.loadPonies();

    const saveBtn = document.getElementById('btn-save');
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            if (EditorState.currentPony && EditorState.originalConfig) {
                const updatedConfig = {
                    name: EditorState.currentPony,
                    display_name: EditorState.originalConfig.display_name || EditorState.currentPony,
                    categories: EditorState.originalConfig.categories || [],
                    tags: EditorState.originalConfig.tags || [],
                    behaviors: BehaviorEditor.behaviors || [],
                    speaks: SpeechEditor.speeches || [],
                    effects: EffectEditor.effects || [],
                    interactions: EditorState.originalConfig.interactions || []
                };
                console.log('[Editor] Saving pony:', EditorState.currentPony);
                EditorAPI.savePony(updatedConfig);
                EditorState.modified = false;
                EditorState.updateModifiedStatus();
                showStatus(`Saved ${EditorState.currentPony}`);
            }
        });
    }

    const newPonyBtn = document.getElementById('btn-new-pony');
    if (newPonyBtn) {
        newPonyBtn.addEventListener('click', () => {
            DialogManager.showNewPonyDialog((ponyData) => {
                const newConfig = {
                    name: ponyData.name,
                    display_name: ponyData.display_name,
                    categories: ponyData.categories,
                    tags: [],
                    behaviors: [],
                    speaks: [],
                    interactions: [],
                    effects: []
                };
                EditorAPI.savePony(newConfig);
                setTimeout(() => {
                    EditorAPI.loadPonies();
                    showStatus(`Created pony: ${ponyData.name}`);
                }, 500);
            });
        });
    }

    const closeBtn = document.getElementById('btn-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            if (EditorState.hasChanges()) {
                if (confirm('Save changes before closing?')) {
                    saveBtn?.click();
                    setTimeout(() => EditorAPI.send('editor:close'), 500);
                } else {
                    EditorAPI.send('editor:close');
                }
            } else {
                EditorAPI.send('editor:close');
            }
        });
    }

    window.editorReceive = (message) => {
        console.log('[Editor] Received from Rust:', message.substring(0, 200));
        try {
            const data = typeof message === 'string' ? JSON.parse(message) : message;
            console.log('[Editor] Parsed data type:', data.type);

            switch (data.type) {
                case 'ponies_list':
                    console.log('[Editor] Ponies list received, count:', data.data?.length);
                    PonyList.updateList(data.data);
                    showStatus(`Loaded ${data.data?.length || 0} ponies`);
                    break;
                case 'pony_config':
                    console.log('[Editor] Pony config received for:', data.pony_name);
                    console.log('[Editor] Behaviors count:', data.data?.behaviors?.length);
                    EditorState.setPony(data.pony_name, data.data);
                    PonyEditor.render(data.data);
                    showStatus(`Loaded ${data.pony_name}`);
                    break;
                case 'save_success':
                    showStatus(`✓ ${data.message}`);
                    EditorState.modified = false;
                    EditorState.updateModifiedStatus();
                    break;
                case 'save_error':
                    showStatus(`✗ Error: ${data.message}`, true);
                    break;
                case 'delete_success':
                    showStatus(`✓ ${data.message}`);
                    EditorAPI.loadPonies();
                    if (EditorState.currentPony) {
                        EditorState.currentPony = null;
                        EditorState.originalConfig = null;
                        PonyEditor.render(null);
                    }
                    break;
                case 'gif_data':
                    console.log('[Editor] GIF DATA RECEIVED - frames:', data.frames?.length);
                    console.log('[Editor] Sprite name:', data.sprite_name);
                    console.log('[Editor] Pony name:', data.pony_name);

                    if (window.GifEditorState) {
                        console.log('[Editor] Found active GIF editor, loading data...');
                        if (window.GifEditorState.loadGif) {
                            window.GifEditorState.loadGif(data);
                        } else {
                            window._pendingGifData = data;
                            console.log('[Editor] Stored pending GIF data');
                        }
                    } else {
                        window._pendingGifData = data;
                        console.log('[Editor] No active editor, stored for later');
                    }

                    if (BehaviorEditor && data.pony_name) {
                        const cacheKey = `${data.pony_name}/${data.sprite_name}`;
                        BehaviorEditor.gifCache.set(cacheKey, data);
                        console.log('[Editor] Cached GIF for:', cacheKey);

                        const previews = document.querySelectorAll('.sprite-preview');
                        previews.forEach(preview => {
                            const previewSprite = preview.dataset.sprite;
                            if (previewSprite === data.sprite_name) {
                                const canvas = preview.querySelector('.preview-canvas');
                                if (canvas) {
                                    console.log('[Editor] Updating canvas for sprite:', data.sprite_name);
                                    BehaviorEditor.drawPreviewOnCanvas(canvas, data);
                                }
                            }
                        });
                    }
                    break;
                case 'gif_list':
                    console.log('[Editor] GIF list received:', data.gifs);
                    if (window._pendingGifListCallback) {
                        window._pendingGifListCallback(data.gifs);
                        window._pendingGifListCallback = null;
                    }
                    break;
                case 'gif_save_success':
                    showStatus(`✓ ${data.message}`);
                    if (window.GifEditorState && window.GifEditorState.ponyName && window.GifEditorState.spriteName) {
                        EditorAPI.send(`gif:load:${window.GifEditorState.ponyName}:${window.GifEditorState.spriteName}`);
                    }
                    break;
                case 'gif_save_error':
                    showStatus(`✗ ${data.message}`, true);
                    break;
                case 'error':
                    showStatus(`✗ Error: ${data.message}`, true);
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