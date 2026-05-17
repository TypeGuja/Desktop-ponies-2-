// Основной редактор параметров пони
const PonyEditor = {
    container: null,

    init() {
        this.container = document.getElementById('editor-panel');
    },

    render(config) {
        if (!this.container) return;

        if (!config) {
            this.container.innerHTML = '<div class="empty-state"><p>✨ Select a pony from the list to edit</p></div>';
            return;
        }

        const html = `
            <div class="editor-tabs">
                <button class="tab-btn active" data-tab="basic">📝 Basic</button>
                <button class="tab-btn" data-tab="behaviors">🏃 Behaviors (${config.behaviors?.length || 0})</button>
                <button class="tab-btn" data-tab="speeches">💬 Speeches (${config.speaks?.length || 0})</button>
                <button class="tab-btn" data-tab="effects">✨ Effects (${config.effects?.length || 0})</button>
                <button class="tab-btn" data-tab="interactions">🤝 Interactions (${config.interactions?.length || 0})</button>
            </div>
            
            <div id="tab-basic" class="tab-pane active">
                ${this.renderBasicTab(config)}
            </div>
            <div id="tab-behaviors" class="tab-pane">
                ${BehaviorEditor.render(config.behaviors || [])}
            </div>
            <div id="tab-speeches" class="tab-pane">
                ${SpeechEditor.render(config.speaks || [])}
            </div>
            <div id="tab-effects" class="tab-pane">
                ${EffectEditor.render(config.effects || [])}
            </div>
            <div id="tab-interactions" class="tab-pane">
                ${InteractionEditor.render(config.interactions || [])}
            </div>
        `;

        this.container.innerHTML = html;

        // Привязываем события табов
        this.container.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });

        // Привязываем события форм
        this.bindEvents(config);

        // Привязываем события для редакторов
        BehaviorEditor.bindEvents(this.container);
        SpeechEditor.bindEvents(this.container);
        EffectEditor.bindEvents(this.container);
        InteractionEditor.bindEvents(this.container);
    },

    renderBasicTab(config) {
        return `
            <div class="card">
                <div class="card-header">
                    <h3>General Information</h3>
                </div>
                <div class="form-group">
                    <label>Display Name</label>
                    <input type="text" id="display-name" value="${escapeHtml(config.name || '')}" 
                           placeholder="Pony display name">
                </div>
                <div class="form-group">
                    <label>Categories (comma separated)</label>
                    <input type="text" id="categories" value="${escapeHtml((config.categories || []).join(', '))}" 
                           placeholder="Main Ponies, Mares, Unicorns">
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <h3>Colors (visual selection)</h3>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Body Color</label>
                        <input type="color" id="body-color" value="#d4a574">
                    </div>
                    <div class="form-group">
                        <label>Mane Color</label>
                        <input type="color" id="mane-color" value="#8b4513">
                    </div>
                    <div class="form-group">
                        <label>Eye Color</label>
                        <input type="color" id="eye-color" value="#4a90d9">
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <h3>Preview</h3>
                </div>
                <div class="preview-area">
                    <canvas id="pony-preview" width="200" height="200" 
                            style="background: var(--bg-tertiary); border-radius: 12px;"></canvas>
                </div>
            </div>
        `;
    },

    bindEvents(config) {
        // Basic info
        const displayName = document.getElementById('display-name');
        const categories = document.getElementById('categories');

        const saveField = (field, value) => {
            config[field] = value;
            EditorState.markModified();
        };

        if (displayName) {
            displayName.addEventListener('change', () => saveField('name', displayName.value));
        }
        if (categories) {
            categories.addEventListener('change', () => {
                config.categories = categories.value.split(',').map(c => c.trim()).filter(c => c);
                EditorState.markModified();
            });
        }

        // Color preview
        const bodyColor = document.getElementById('body-color');
        const maneColor = document.getElementById('mane-color');
        const eyeColor = document.getElementById('eye-color');
        const canvas = document.getElementById('pony-preview');

        const drawPreview = () => {
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const w = canvas.width, h = canvas.height;
            ctx.clearRect(0, 0, w, h);

            // Простой SVG-подобный рендер пони
            ctx.fillStyle = bodyColor?.value || '#d4a574';
            ctx.beginPath();
            ctx.ellipse(w/2, h/2 + 20, 50, 35, 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = bodyColor?.value || '#d4a574';
            ctx.beginPath();
            ctx.ellipse(w/2, h/2 - 20, 30, 28, 0, 0, Math.PI * 2);
            ctx.fill();

            // Грива
            ctx.fillStyle = maneColor?.value || '#8b4513';
            ctx.beginPath();
            ctx.ellipse(w/2 - 20, h/2 - 25, 15, 20, -0.3, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.ellipse(w/2 + 20, h/2 - 25, 15, 20, 0.3, 0, Math.PI * 2);
            ctx.fill();

            // Глаза
            ctx.fillStyle = eyeColor?.value || '#4a90d9';
            ctx.beginPath();
            ctx.arc(w/2 - 12, h/2 - 28, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(w/2 + 12, h/2 - 28, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = 'white';
            ctx.beginPath();
            ctx.arc(w/2 - 14, h/2 - 30, 2, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(w/2 + 10, h/2 - 30, 2, 0, Math.PI * 2);
            ctx.fill();
        };

        if (bodyColor) bodyColor.addEventListener('input', drawPreview);
        if (maneColor) maneColor.addEventListener('input', drawPreview);
        if (eyeColor) eyeColor.addEventListener('input', drawPreview);
        drawPreview();
    },

    switchTab(tabName) {
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
        });
        const targetPane = document.getElementById(`tab-${tabName}`);
        if (targetPane) targetPane.classList.add('active');

        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
            }
        });
    }
};