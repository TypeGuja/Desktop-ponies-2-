// ПАТЧ для исправления проблемы с Trace Reference не отображающейся
// Добавить этот код в initGifEditorEnhanced() ВМЕСТО старого drawCanvas()

function drawCanvas() {
    if (!stateManager.frames[stateManager.currentFrame]) return;

    const frame = stateManager.frames[stateManager.currentFrame];
    const displayWidth = stateManager.width * stateManager.zoom;
    const displayHeight = stateManager.height * stateManager.zoom;

    // ✅ ВАЖНО: Перестраиваем canvas ТОЛЬКО если размер действительно изменился
    // Это предотвращает случайное стирание содержимого при resize окна
    if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
        canvas.width = displayWidth;
        canvas.height = displayHeight;
        console.log('[Draw] Canvas resized to', displayWidth, 'x', displayHeight);
    }

    // ✅ CSS стили применяются один раз (не нужно пересчитывать каждый раз)
    if (canvas.style.width !== (displayWidth + 'px')) {
        canvas.style.width = displayWidth + 'px';
        canvas.style.height = displayHeight + 'px';
        canvas.style.imageRendering = 'crisp-edges';
        canvas.style.imageRendering = 'pixelated';
    }

    ctx.clearRect(0, 0, displayWidth, displayHeight);

    // Рисуем основное изображение
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = stateManager.width;
    tempCanvas.height = stateManager.height;
    const tempCtx = tempCanvas.getContext('2d');
    try {
        const imgData = new ImageData(frame.data, stateManager.width, stateManager.height);
        tempCtx.putImageData(imgData, 0, 0);
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(tempCanvas, 0, 0, stateManager.width, stateManager.height, 0, 0, displayWidth, displayHeight);
    } catch(e) {
        console.warn('[Draw] Error drawing frame:', e);
    }

    // ===== РИСУЕМ TRACE ПОВЕРХ =====
    const trace = stateManager.traceState;
    if (trace && trace.visible && trace.image) {
        // ✅ Используем более строгую проверку загруженности изображения
        const isImageReady = trace.image.complete && 
                           trace.image.naturalWidth > 0 && 
                           trace.image.naturalHeight > 0;
        
        if (isImageReady) {
            try {
                ctx.save();
                ctx.globalAlpha = trace.opacity || 0.5;
                
                const refW = trace.image.width * (trace.scale || 1.0) * stateManager.zoom;
                const refH = trace.image.height * (trace.scale || 1.0) * stateManager.zoom;
                const refX = (trace.offsetX || 0) * stateManager.zoom;
                const refY = (trace.offsetY || 0) * stateManager.zoom;

                // ✅ Добавляем проверку перед рисованием
                if (refW > 0 && refH > 0) {
                    ctx.drawImage(trace.image, refX, refY, refW, refH);
                    console.log('[Draw] Trace drawn at', refX, refY, refW, 'x', refH);
                }
                
                ctx.restore();
            } catch(e) {
                console.warn('[Draw] Error drawing trace:', e);
            }
        } else {
            console.log('[Draw] Trace image not ready:', {
                complete: trace.image.complete,
                naturalWidth: trace.image.naturalWidth,
                naturalHeight: trace.image.naturalHeight
            });
        }
    }

    // Обновляем UI
    const zoomLevel = document.getElementById('gif-zoom-level');
    const delayInput = document.getElementById('gif-frame-delay');
    const statusEl = document.getElementById('gif-status');

    if (zoomLevel) zoomLevel.textContent = Math.round(stateManager.zoom * 100) + '%';
    if (delayInput && stateManager.frames[stateManager.currentFrame]) {
        delayInput.value = stateManager.frames[stateManager.currentFrame].delay;
    }
    if (statusEl && stateManager.frames[stateManager.currentFrame] && !stateManager.isPickingColor) {
        const traceInfo = (trace && trace.visible && trace.image) ? ' | 🖼️ Trace ON' : '';
        statusEl.textContent = `Frame ${stateManager.currentFrame+1}/${stateManager.frames.length} | Delay: ${stateManager.frames[stateManager.currentFrame].delay}cs | Speed: ${stateManager.playSpeed.toFixed(2)}x${traceInfo}`;
    }
}

// ✅ ТАКЖЕ: Оптимизируем загрузку Trace изображения
// Заменить в функции updateImageFromFrames() эту часть:

function updateImageFromFrames_OPTIMIZED() {
    const frames = trace.frames;
    if (!frames || !frames[trace.currentFrame]) return;

    const frame = frames[trace.currentFrame];
    if (frame.imageData) {
        const fcanvas = document.createElement('canvas');
        fcanvas.width = frame.imageData.width;
        fcanvas.height = frame.imageData.height;
        const fctx = fcanvas.getContext('2d');
        fctx.putImageData(frame.imageData, 0, 0);

        const img = new Image();
        
        // ✅ Проверяем готовность изображения с задержками
        img.onload = () => {
            if (!document.getElementById('trace-panel')) return;
            
            // Проверяем, что изображение действительно загружено
            if (img.complete && img.naturalWidth > 0 && img.naturalHeight > 0) {
                trace.image = img;
                console.log('[Trace] Image loaded:', img.width, 'x', img.height);
                updatePreview();
                
                // ✅ Форсированная перерисовка с задержками
                drawCanvas();
                setTimeout(() => drawCanvas(), 10);
                setTimeout(() => drawCanvas(), 50);
                setTimeout(() => drawCanvas(), 100);
                setTimeout(() => drawCanvas(), 200);
            } else {
                console.warn('[Trace] Image loaded but invalid:', {
                    complete: img.complete,
                    naturalWidth: img.naturalWidth,
                    naturalHeight: img.naturalHeight
                });
            }
        };
        
        img.onerror = (err) => {
            console.error('[Trace] Failed to load image from frame:', err);
        };
        
        // ✅ Используем blob URL вместо data URL для больших изображений
        const blob = canvas.toBlob(blobData => {
            img.src = URL.createObjectURL(blobData);
        }, 'image/png');
    }
}

// ✅ ОКОНЧАТЕЛЬНЫЙ ВАРИАНТ: Полностью новая функция updateImageFromFrames с проверками

const updateImageFromFrames_BEST = function() {
    const frames = stateManager.traceState.frames;
    if (!frames || !frames[stateManager.traceState.currentFrame]) return;

    const frame = frames[stateManager.traceState.currentFrame];
    if (!frame.imageData) return;

    const fcanvas = document.createElement('canvas');
    fcanvas.width = frame.imageData.width;
    fcanvas.height = frame.imageData.height;
    const fctx = fcanvas.getContext('2d');
    
    try {
        fctx.putImageData(frame.imageData, 0, 0);
    } catch(e) {
        console.error('[Trace] Failed to put image data:', e);
        return;
    }

    const img = new Image();
    let loadTimeout;

    const handleImageReady = () => {
        clearTimeout(loadTimeout);
        if (!document.getElementById('trace-panel')) {
            console.log('[Trace] Panel closed, aborting');
            return;
        }
        
        if (img.complete && img.naturalWidth > 0 && img.naturalHeight > 0) {
            stateManager.traceState.image = img;
            console.log('[Trace] ✓ Image ready:', img.width, 'x', img.height);
            
            if (document.getElementById('trace-preview')) {
                updatePreview();
            }
            
            // ✅ Многократная перерисовка гарантирует отображение
            requestAnimationFrame(() => drawCanvas());
            setTimeout(() => drawCanvas(), 50);
            setTimeout(() => drawCanvas(), 150);
        } else {
            console.warn('[Trace] Image data invalid');
        }
    };

    img.onload = handleImageReady;
    
    img.onerror = () => {
        clearTimeout(loadTimeout);
        console.error('[Trace] Failed to load image');
    };

    // Таймаут на случай, если изображение не загружается
    loadTimeout = setTimeout(() => {
        console.warn('[Trace] Image load timeout');
    }, 5000);

    // ✅ Используем PNG для лучшей совместимости
    img.src = fcanvas.toDataURL('image/png');
};
