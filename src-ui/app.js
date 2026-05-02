// src-ui/app.js
let allPonies = [];

// Данные вставятся из Rust перед этим скриптом
document.addEventListener('DOMContentLoaded', () => {
    if (typeof PONIES_DATA !== 'undefined' && PONIES_DATA.ponies) {
        allPonies = PONIES_DATA.ponies;
        console.log('Loaded', allPonies.length, 'ponies');
    } else {
        console.warn('PONIES_DATA not found');
    }

    document.getElementById('pony-count').textContent = allPonies.length + ' ponies';
    initTabs();
    initSpawnForm();
    initBrowse();
    populateDatalist();
});

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + btn.dataset.tab)?.classList.add('active');
        });
    });
}

function initBrowse() {
    const list = document.getElementById('pony-list');
    if (!list) return;

    // Показываем всех пони
    let html = '';
    allPonies.forEach(p => {
        html += `<div class="pony-item" onclick="selectPony('${p.name.replace(/'/g, "\\'")}')">
            <div class="pony-info">
                <div class="pony-icon">🦄</div>
                <div>
                    <div class="pony-name">${p.name}</div>
                    <div class="pony-behavior">${p.behaviors.slice(0, 5).join(', ')} · ${p.speaks_count} phrases</div>
                </div>
            </div>
        </div>`;
    });
    list.innerHTML = html || '<p class="empty-state">No ponies found</p>';

    // Поиск
    document.getElementById('search')?.addEventListener('input', e => {
        const q = e.target.value.toLowerCase();
        const filtered = allPonies.filter(p => p.name.toLowerCase().includes(q));
        list.innerHTML = filtered.map(p =>
            `<div class="pony-item" onclick="selectPony('${p.name.replace(/'/g, "\\'")}')">
                <div class="pony-info">
                    <div class="pony-icon">🦄</div>
                    <div>
                        <div class="pony-name">${p.name}</div>
                        <div class="pony-behavior">${p.behaviors.slice(0, 5).join(', ')} · ${p.speaks_count} phrases</div>
                    </div>
                </div>
            </div>`
        ).join('') || '<p class="empty-state">No matches</p>';
    });
}

function selectPony(name) {
    document.getElementById('pony-name').value = name;
    // Обновляем список поведений
    const pony = allPonies.find(p => p.name === name);
    const sel = document.getElementById('pony-behavior');
    if (pony && sel) {
        sel.innerHTML = pony.behaviors.map(b => `<option value="${b}">${b}</option>`).join('');
    }
    document.getElementById('status-text').textContent = 'Selected: ' + name;
    // Переключаем на вкладку Spawn
    document.querySelector('.tab-btn[data-tab="spawn"]')?.click();
}

function populateDatalist() {
    const dl = document.getElementById('pony-list-datalist');
    if (dl) {
        dl.innerHTML = allPonies.map(p => `<option value="${p.name}">`).join('');
    }
}

function initSpawnForm() {
    document.getElementById('btn-spawn')?.addEventListener('click', () => {
        const name = document.getElementById('pony-name').value;
        const behavior = document.getElementById('pony-behavior').value;
        const x = document.getElementById('pos-x').value;
        const y = document.getElementById('pos-y').value;
        if (!name) {
            document.getElementById('status-text').textContent = 'Select a pony first!';
            return;
        }
        document.getElementById('status-text').textContent = `Spawning ${name} (${behavior}) at (${x},${y}) — coming soon`;
    });
}