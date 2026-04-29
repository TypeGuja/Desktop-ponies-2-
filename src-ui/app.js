// src-ui/app.js (обновлённый, без Tauri)
let allPonies = [];

// Забираем данные из встроенного JSON
if (typeof PONIES_DATA !== 'undefined') {
    allPonies = PONIES_DATA;
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('pony-count').textContent = `${allPonies.length} ponies`;
    initTabs();
    initSpawnForm();
    initPonyActions();
    initInteractions();
    initSettings();
    renderBrowseList(allPonies);
    populateSpawnDatalist();
});

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const target = document.getElementById(`tab-${tab.dataset.tab}`);
            if (target) target.classList.add('active');
            if (tab.dataset.tab === 'browse') renderBrowseList(allPonies);
            if (tab.dataset.tab === 'active') refreshActivePonies();
            if (tab.dataset.tab === 'spawn') populateSpawnDatalist();
        });
    });
}

function renderBrowseList(ponies) {
    const container = document.getElementById('pony-list');
    if (!container) return;
    if (!ponies.length) {
        container.innerHTML = '<p class="empty-state">No ponies found</p>';
        return;
    }
    container.innerHTML = ponies.map(p => `
        <div class="pony-item" onclick="selectPony('${p.name}')">
            <div class="pony-info">
                <div class="pony-icon">🦄</div>
                <div>
                    <div class="pony-name">${p.name}</div>
                    <div class="pony-behavior">${p.behaviors.slice(0,5).join(', ')}${p.behaviors.length > 5 ? '...' : ''} · ${p.speaks_count} phrases</div>
                </div>
            </div>
        </div>
    `).join('');
}

function selectPony(name) {
    document.getElementById('pony-name').value = name;
    populateBehaviors(name);
    document.getElementById('status-text').textContent = `Selected: ${name}`;
    document.querySelector('.tab-btn[data-tab="spawn"]').click();
}

function populateBehaviors(name) {
    const sel = document.getElementById('pony-behavior');
    const pony = allPonies.find(p => p.name === name);
    if (pony) {
        sel.innerHTML = pony.behaviors.map(b => `<option value="${b}">${b}</option>`).join('');
    }
}

function populateSpawnDatalist() {
    const dl = document.getElementById('pony-list-datalist');
    if (!dl) return;
    dl.innerHTML = allPonies.map(p => `<option value="${p.name}">`).join('');
}

function initSpawnForm() {
    document.getElementById('btn-spawn')?.addEventListener('click', () => {
        const name = document.getElementById('pony-name').value;
        const behavior = document.getElementById('pony-behavior').value;
        const x = document.getElementById('pos-x').value;
        const y = document.getElementById('pos-y').value;
        setStatus(`Spawning ${name} (${behavior}) at (${x},${y}) — coming soon`);
    });
}

function initPonyActions() {
    document.getElementById('btn-remove-all')?.addEventListener('click', () => {
        setStatus('Remove all — coming soon');
    });
}

function initInteractions() {}
function initSettings() {}
function refreshActivePonies() {}

function setStatus(msg) {
    const el = document.getElementById('status-text');
    if (!el) return;
    el.textContent = msg;
}