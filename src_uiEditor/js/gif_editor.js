// Состояние редактора
let frames = [];
let currentFrame = 0;
let width = 128;
let height = 128;
let zoom = 1;
let tool = 'pencil';
let currentColor = '#cba6f7';
let isDrawing = false;
let ponyName = '';
let spriteName = '';
let previewInterval = null;

// Цвета
const colors = [
    '#FFFFFF', '#000000', '#cba6f7', '#f38ba8', '#a6e3a1',
    '#89b4fa', '#f9e2af', '#fab387', '#94e2d5', '#585b70',
    '#f2cdcd', '#b4befe', '#eba0ac', '#f5c2e7'
];

// DOM элементы
const canvas = document.getElementById('main-canvas');
const ctx = canvas.getContext('2d');
const timeline = document.getElementById('timeline');
const statusEl = document.getElementById('status');

// Инициализация палитры
const palette = document.getElementById('color-palette');
colors.forEach(color => {
    const swatch = document.createElement('div');
    swatch.className = 'color-swatch';
    swatch.style.backgroundColor = color;
    swatch.addEventListener('click', () => {
        document.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('selected'));
        swatch.classList.add('selected');
        currentColor = color;
    });
    palette.appendChild(swatch);
});
if (palette.children[0]) palette.children[0].classList.add('selected');

// Инициализация пустого GIF
function initEmptyGif(w, h) {
    width = w || 128;
    height = h || 128;
    frames = [];
    for (let i = 0; i < 2; i++) {
        const data = new Uint8ClampedArray(width * height * 4);
        for (let j = 0; j < data.length; j += 4) {
            data[j] = 255;
            data[j+1] = 192;
            data[j+2] = 203;
            data[j+3] = 255;
        }
        frames.push({ data, delay: 10 });
    }
    currentFrame = 0;
    drawCanvas();
    updateTimeline();
    statusEl.textContent = `New GIF: ${frames.length} frames, ${width}x${height}`;
}

// Загрузка GIF из данных
function loadGifFromData(gifData) {
    console.log('[GIF] loadGifFromData called');

    if (!gifData.frames || gifData.frames.length === 0) {
        console.log('[GIF] No frames, creating empty');
        initEmptyGif(128, 128);
        return;
    }

    // Сохраняем данные
    ponyName = gifData.pony_name || ponyName;
    spriteName = gifData.sprite_name || spriteName;
    width = gifData.width;
    height = gifData.height;

    frames = [];

    for (let i = 0; i < gifData.frames.length; i++) {
        const srcFrame = gifData.frames[i];
        console.log(`[GIF] Frame ${i}: data length=${srcFrame.data?.length}, delay=${srcFrame.delay}`);

        // Убеждаемся что data существует
        if (!srcFrame.data || srcFrame.data.length === 0) {
            console.error(`[GIF] Frame ${i} has no data!`);
            continue;
        }

        // Копируем данные
        const data = new Uint8ClampedArray(srcFrame.data.length);
        for (let j = 0; j < srcFrame.data.length; j++) {
            data[j] = srcFrame.data[j];
        }

        frames.push({
            data: data,
            delay: srcFrame.delay || 10
        });
    }

    if (frames.length === 0) {
        console.error('[GIF] No valid frames loaded');
        initEmptyGif(128, 128);
        return;
    }

    currentFrame = 0;
    drawCanvas();
    updateTimeline();
    updateStatus(`Loaded ${frames.length} frames, ${width}x${height}`);
    console.log('[GIF] Load complete, frames:', frames.length);
}

// Отправка GIF в Rust
function saveGif() {
    const framesData = frames.map(f => ({
        data: Array.from(f.data),
        width: width,
        height: height,
        delay: f.delay
    }));
    const saveData = {
        pony_name: ponyName,
        sprite_name: spriteName,
        frames: framesData,
        width: width,
        height: height
    };
    sendToRust('gif:save:' + JSON.stringify(saveData));
}

// Рисование на canvas
function drawCanvas() {
    if (!frames[currentFrame]) return;

    const frame = frames[currentFrame];
    const ctx = canvas.getContext('2d');

    canvas.width = width * zoom;
    canvas.height = height * zoom;
    canvas.style.width = (width * zoom) + 'px';
    canvas.style.height = (height * zoom) + 'px';

    // Создаём ImageData с правильным порядком байт
    const imgData = new ImageData(width, height);

    // Конвертируем RGBA из u32 в правильный порядок R,G,B,A
    for (let i = 0; i < frame.data.length; i++) {
        const pixel = frame.data[i];
        const r = (pixel >> 16) & 0xFF;
        const g = (pixel >> 8) & 0xFF;
        const b = pixel & 0xFF;
        const a = (pixel >> 24) & 0xFF;

        imgData.data[i * 4] = r;
        imgData.data[i * 4 + 1] = g;
        imgData.data[i * 4 + 2] = b;
        imgData.data[i * 4 + 3] = a;
    }

    ctx.putImageData(imgData, 0, 0);

    if (zoom !== 1) {
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(canvas, 0, 0, width, height, 0, 0, width * zoom, height * zoom);
    }

    updateStatus();
}

// Обновление таймлайна
function updateTimeline() {
    timeline.innerHTML = '';
    frames.forEach((frame, idx) => {
        const div = document.createElement('div');
        div.className = 'timeline-frame' + (idx === currentFrame ? ' selected' : '');

        const previewCanvas = document.createElement('canvas');
        previewCanvas.width = 64;
        previewCanvas.height = 64;
        const previewCtx = previewCanvas.getContext('2d');
        const imgData = new ImageData(frame.data, width, height);
        previewCtx.putImageData(imgData, 0, 0);
        div.appendChild(previewCanvas);

        const label = document.createElement('span');
        label.textContent = `${frame.delay}cs`;
        div.appendChild(label);

        div.addEventListener('click', () => {
            if (previewInterval) {
                clearInterval(previewInterval);
                previewInterval = null;
                document.getElementById('btn-preview').textContent = '▶️ Preview';
            }
            currentFrame = idx;
            drawCanvas();
            updateTimeline();
        });

        timeline.appendChild(div);
    });
}

// Установка пикселя
function setPixel(x, y) {
    if (!frames[currentFrame]) return;
    const frame = frames[currentFrame];
    const px = Math.floor(x / zoom);
    const py = Math.floor(y / zoom);
    if (px < 0 || px >= width || py < 0 || py >= height) return;

    const idx = (py * width + px) * 4;
    const color = hexToRgb(currentColor);

    if (tool === 'eraser') {
        frame.data[idx] = 0;
        frame.data[idx+1] = 0;
        frame.data[idx+2] = 0;
        frame.data[idx+3] = 0;
    } else if (tool === 'pencil') {
        frame.data[idx] = color.r;
        frame.data[idx+1] = color.g;
        frame.data[idx+2] = color.b;
        frame.data[idx+3] = 255;
    }

    drawCanvas();
    updateTimeline();
}

// Заливка
function floodFill(x, y) {
    if (!frames[currentFrame]) return;
    const frame = frames[currentFrame];
    const px = Math.floor(x / zoom);
    const py = Math.floor(y / zoom);
    if (px < 0 || px >= width || py < 0 || py >= height) return;

    const idx = (py * width + px) * 4;
    const targetColor = {
        r: frame.data[idx],
        g: frame.data[idx+1],
        b: frame.data[idx+2],
        a: frame.data[idx+3]
    };
    const newColor = hexToRgb(currentColor);

    if (targetColor.r === newColor.r && targetColor.g === newColor.g &&
        targetColor.b === newColor.b) return;

    const stack = [{x: px, y: py}];
    while (stack.length) {
        const {x: cx, y: cy} = stack.pop();
        const cidx = (cy * width + cx) * 4;
        if (frame.data[cidx] !== targetColor.r || frame.data[cidx+1] !== targetColor.g ||
            frame.data[cidx+2] !== targetColor.b) continue;

        frame.data[cidx] = newColor.r;
        frame.data[cidx+1] = newColor.g;
        frame.data[cidx+2] = newColor.b;
        frame.data[cidx+3] = 255;

        if (cx > 0) stack.push({x: cx-1, y: cy});
        if (cx < width-1) stack.push({x: cx+1, y: cy});
        if (cy > 0) stack.push({x: cx, y: cy-1});
        if (cy < height-1) stack.push({x: cx, y: cy+1});
    }
    drawCanvas();
    updateTimeline();
}

// Пипетка
function pickColor(x, y) {
    if (!frames[currentFrame]) return;
    const frame = frames[currentFrame];
    const px = Math.floor(x / zoom);
    const py = Math.floor(y / zoom);
    if (px < 0 || px >= width || py < 0 || py >= height) return;

    const idx = (py * width + px) * 4;
    const color = `#${frame.data[idx].toString(16).padStart(2,'0')}${frame.data[idx+1].toString(16).padStart(2,'0')}${frame.data[idx+2].toString(16).padStart(2,'0')}`;
    currentColor = color;
    statusEl.textContent = `Picked color: ${color}`;
}

function hexToRgb(hex) {
    return {
        r: parseInt(hex.slice(1,3), 16),
        g: parseInt(hex.slice(3,5), 16),
        b: parseInt(hex.slice(5,7), 16)
    };
}

// Отправка сообщения в Rust
function sendToRust(message) {
    if (window.ipc && window.ipc.postMessage) {
        window.ipc.postMessage(message);
    } else if (window.external && typeof window.external.sendMessage === 'function') {
        window.external.sendMessage(message);
    }
}

// Получение параметров из URL
const urlParams = new URLSearchParams(window.location.search);
ponyName = urlParams.get('pony') || '';
spriteName = urlParams.get('sprite') || '';

// Загружаем GIF если есть параметры
if (ponyName && spriteName) {
    sendToRust(`gif:load:${ponyName}:${spriteName}`);
}

// Получение сообщений от Rust
window.editorReceive = function(message) {
    try {
        const data = JSON.parse(message);
        if (data.type === 'gif_data') {
            loadGifFromData(data);
        } else if (data.type === 'gif_save_success') {
            statusEl.textContent = 'Saved!';
            setTimeout(() => statusEl.textContent = 'Ready', 2000);
        } else if (data.type === 'gif_save_error') {
            statusEl.textContent = 'Save failed: ' + (data.message || '');
        } else if (data.type === 'error') {
            statusEl.textContent = 'Error: ' + data.message;
        }
    } catch(e) {
        console.error('[GIF] Parse error:', e);
    }
};

// Кнопки инструментов
document.getElementById('btn-pencil').addEventListener('click', () => {
    tool = 'pencil';
    document.querySelectorAll('.toolbar button').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-pencil').classList.add('active');
});
document.getElementById('btn-eraser').addEventListener('click', () => {
    tool = 'eraser';
    document.querySelectorAll('.toolbar button').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-eraser').classList.add('active');
});
document.getElementById('btn-fill').addEventListener('click', () => {
    tool = 'fill';
    document.querySelectorAll('.toolbar button').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-fill').classList.add('active');
});
document.getElementById('btn-eye').addEventListener('click', () => {
    tool = 'eye';
    document.querySelectorAll('.toolbar button').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-eye').classList.add('active');
});

// Очистка кадра
document.getElementById('btn-clear').addEventListener('click', () => {
    if (frames[currentFrame]) {
        const data = frames[currentFrame].data;
        for (let i = 0; i < data.length; i += 4) {
            data[i] = 0;
            data[i+1] = 0;
            data[i+2] = 0;
            data[i+3] = 0;
        }
        drawCanvas();
        updateTimeline();
    }
});

// Добавление кадра
document.getElementById('btn-add-frame').addEventListener('click', () => {
    const newData = new Uint8ClampedArray(width * height * 4);
    for (let i = 0; i < newData.length; i += 4) {
        newData[i] = 255;
        newData[i+1] = 192;
        newData[i+2] = 203;
        newData[i+3] = 255;
    }
    frames.push({ data: newData, delay: 10 });
    currentFrame = frames.length - 1;
    drawCanvas();
    updateTimeline();
});

// Удаление кадра
document.getElementById('btn-delete-frame').addEventListener('click', () => {
    if (frames.length > 1) {
        frames.splice(currentFrame, 1);
        if (currentFrame >= frames.length) currentFrame = frames.length - 1;
        drawCanvas();
        updateTimeline();
    }
});

// Предпросмотр
document.getElementById('btn-preview').addEventListener('click', () => {
    if (previewInterval) {
        clearInterval(previewInterval);
        previewInterval = null;
        document.getElementById('btn-preview').textContent = '▶️ Preview';
    } else {
        previewInterval = setInterval(() => {
            currentFrame = (currentFrame + 1) % frames.length;
            drawCanvas();
            updateTimeline();
        }, frames[currentFrame]?.delay * 10 || 100);
        document.getElementById('btn-preview').textContent = '⏸️ Stop';
    }
});

// Сохранение
document.getElementById('btn-save').addEventListener('click', saveGif);

// Закрытие
document.getElementById('btn-close').addEventListener('click', () => {
    if (window.close) window.close();
    else sendToRust('editor:close');
});

// Зум
document.getElementById('zoom-in').addEventListener('click', () => {
    zoom = Math.min(zoom + 0.25, 8);
    drawCanvas();
});
document.getElementById('zoom-out').addEventListener('click', () => {
    zoom = Math.max(zoom - 0.25, 0.5);
    drawCanvas();
});

// События мыши для рисования
canvas.addEventListener('mousedown', (e) => {
    isDrawing = true;
    const rect = canvas.getBoundingClientRect();
    const scaleX = width / rect.width;
    const scaleY = height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    if (tool === 'fill') floodFill(x, y);
    else if (tool === 'eye') pickColor(x, y);
    else setPixel(x, y);
});

canvas.addEventListener('mousemove', (e) => {
    if (!isDrawing || tool === 'fill' || tool === 'eye') return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = width / rect.width;
    const scaleY = height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    setPixel(x, y);
});

canvas.addEventListener('mouseup', () => isDrawing = false);
canvas.addEventListener('mouseleave', () => isDrawing = false);

// Инициализация
initEmptyGif(128, 128);