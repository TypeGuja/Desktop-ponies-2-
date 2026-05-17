const SpeechEditor = {
    speeches: [],

    render(speeches) {
        this.speeches = speeches || [];

        if (this.speeches.length === 0) {
            return `<div class="card"><div class="empty-state">No speeches defined</div>
                    <button class="btn-secondary" id="add-speech">+ Add Speech</button></div>`;
        }

        let html = `<button class="btn-secondary" id="add-speech" style="margin-bottom:16px">+ Add Speech</button>`;

        this.speeches.forEach((speech, i) => {
            html += `<div class="card" data-speech-index="${i}">
                        <div class="card-header">
                            <h3>${escapeHtml(speech.name || 'Unnamed')}</h3>
                            <button class="btn-icon delete-speech" data-index="${i}">🗑️</button>
                        </div>
                        <div class="form-group">
                            <label>Name</label>
                            <input type="text" class="speech-name" value="${escapeHtml(speech.name)}" data-index="${i}">
                        </div>
                        <div class="form-group">
                            <label>Text</label>
                            <textarea class="speech-text" data-index="${i}" rows="2">${escapeHtml(speech.text)}</textarea>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Sound File</label>
                                <input type="text" class="speech-sound" value="${escapeHtml(speech.sound_files?.[0] || '')}" data-index="${i}">
                            </div>
                            <div class="form-group">
                                <label>Skip random</label>
                                <input type="checkbox" class="speech-skip" ${speech.skip ? 'checked' : ''} data-index="${i}">
                            </div>
                            <div class="form-group">
                                <label>Frequency</label>
                                <input type="number" step="0.1" class="speech-frequency" value="${speech.frequency || 0}" data-index="${i}">
                            </div>
                        </div>
                    </div>`;
        });
        return html;
    },

    bindEvents(container) {
        if (!container) return;

        // Add speech button
        const addBtn = container.querySelector('#add-speech');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                this.speeches.push({
                    name: 'New Speech',
                    text: 'Hello!',
                    sound_files: [],
                    skip: false,
                    frequency: 0
                });
                EditorState.markModified();
                PonyEditor.render(EditorState.getConfig());
            });
        }

        // Delete buttons
        container.querySelectorAll('.delete-speech').forEach(btn => {
            btn.addEventListener('click', () => {
                const index = parseInt(btn.dataset.index);
                this.speeches.splice(index, 1);
                EditorState.markModified();
                PonyEditor.render(EditorState.getConfig());
            });
        });

        // Update name
        container.querySelectorAll('.speech-name').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                this.speeches[idx].name = input.value;
                EditorState.markModified();
            });
        });

        // Update text
        container.querySelectorAll('.speech-text').forEach(textarea => {
            textarea.addEventListener('change', () => {
                const idx = parseInt(textarea.dataset.index);
                this.speeches[idx].text = textarea.value;
                EditorState.markModified();
            });
        });

        // Update sound
        container.querySelectorAll('.speech-sound').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                this.speeches[idx].sound_files = input.value ? [input.value] : [];
                EditorState.markModified();
            });
        });

        // Update skip
        container.querySelectorAll('.speech-skip').forEach(cb => {
            cb.addEventListener('change', () => {
                const idx = parseInt(cb.dataset.index);
                this.speeches[idx].skip = cb.checked;
                EditorState.markModified();
            });
        });

        // Update frequency
        container.querySelectorAll('.speech-frequency').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                this.speeches[idx].frequency = parseFloat(input.value) || 0;
                EditorState.markModified();
            });
        });
    }
};