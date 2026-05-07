(function() {
    'use strict';

    var allPonies = [];
    var monitorList = [];
    var selectedMonitors = [];
    var activePonies = [];

    function init() {
        console.log('INIT START');

        if (window.PONIES_DATA && Array.isArray(window.PONIES_DATA)) {
            allPonies = window.PONIES_DATA;
        }
        if (window.MONITORS_DATA && Array.isArray(window.MONITORS_DATA)) {
            monitorList = window.MONITORS_DATA;
        }
        if (window.SELECTED_MONITORS && Array.isArray(window.SELECTED_MONITORS)) {
            selectedMonitors = window.SELECTED_MONITORS;
        } else if (monitorList.length > 0) {
            selectedMonitors = monitorList.map(function(m) { return m.id; });
        }

        console.log('Ponies:', allPonies.length);
        console.log('Monitors:', monitorList.length);
        console.log('Selected:', selectedMonitors);

        renderPonyList();
        renderMonitorList();
        renderActivePonies();
        updateCounters();
        bindEvents();

        console.log('INIT DONE');
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('pony-theme', theme);
        var options = document.querySelectorAll('.theme-option');
        options.forEach(function(opt) {
            if (opt.dataset.theme === theme) {
                opt.classList.add('active');
            } else {
                opt.classList.remove('active');
            }
        });
    }

    function switchTab(tabName) {
        var tabs = document.querySelectorAll('.tab-btn');
        var contents = document.querySelectorAll('.tab-content');
        tabs.forEach(function(b) { b.classList.remove('active'); });
        contents.forEach(function(c) { c.classList.remove('active'); });

        var btn = document.querySelector('.tab-btn[data-tab="' + tabName + '"]');
        var content = document.getElementById('tab-' + tabName);

        if (btn) btn.classList.add('active');
        if (content) content.classList.add('active');

        if (tabName === 'settings') renderMonitorList();
        if (tabName === 'active') renderActivePonies();
    }

    function renderPonyList(filter) {
        var container = document.getElementById('pony-list');
        if (!container) return;

        filter = filter || '';
        var filtered = allPonies.filter(function(p) {
            return p.name.toLowerCase().indexOf(filter.toLowerCase()) >= 0;
        });

        if (filtered.length === 0) {
            container.innerHTML = '<div class="empty-state">No ponies found</div>';
            return;
        }

        container.innerHTML = filtered.map(function(p) {
            return '<div class="pony-item" data-name="' + esc(p.name) + '">' +
                '<div class="pony-info">' +
                '<div class="pony-icon">P</div>' +
                '<div>' +
                '<div class="pony-name">' + esc(p.name) + '</div>' +
                '<div class="pony-behavior">' + (p.behaviors || []).slice(0,3).join(', ') + ' - ' + (p.speaks_count||0) + ' speaks</div>' +
                '</div>' +
                '</div>' +
                '<div class="pony-actions">' +
                '<button class="spawn-btn" data-name="' + esc(p.name) + '">+</button>' +
                '</div>' +
                '</div>';
        }).join('');
    }

    function renderMonitorList() {
        var container = document.getElementById('monitor-list');
        if (!container) return;

        if (monitorList.length === 0) {
            container.innerHTML = '<div class="empty-state">No monitors detected</div>';
            return;
        }

        container.innerHTML = monitorList.map(function(m) {
            var checked = selectedMonitors.indexOf(m.id) >= 0 ? 'checked' : '';
            var primaryTag = m.is_primary ? '<span class="tag tag-primary">Primary</span>' : '';

            return '<div class="pony-item">' +
                '<div class="pony-info">' +
                '<div class="pony-icon">M</div>' +
                '<div>' +
                '<div class="pony-name">' + esc(m.name) + ' ' + primaryTag + '</div>' +
                '<div class="pony-behavior">' + m.width + 'x' + m.height + ' - ' + (m.scale_factor * 100).toFixed(0) + '% scale</div>' +
                '</div>' +
                '</div>' +
                '<div class="pony-actions">' +
                '<label class="monitor-checkbox">' +
                '<input type="checkbox" class="monitor-cb" value="' + esc(m.id) + '" ' + checked + '>' +
                '<span>Active</span>' +
                '</label>' +
                '</div>' +
                '</div>';
        }).join('');

        // Привязываем события к чекбоксам
        var checkboxes = container.querySelectorAll('.monitor-cb');
        checkboxes.forEach(function(cb) {
            cb.addEventListener('change', function() {
                var id = this.value;
                if (this.checked) {
                    if (selectedMonitors.indexOf(id) < 0) {
                        selectedMonitors.push(id);
                    }
                } else {
                    selectedMonitors = selectedMonitors.filter(function(m) {
                        return m !== id;
                    });
                }
                console.log('Monitors updated:', selectedMonitors);
                setStatus(selectedMonitors.length + ' monitor(s) selected');
                // Автосохранение
                saveMonitorSettings();
            });
        });
    }

    function renderActivePonies() {
        var container = document.getElementById('active-list');
        if (!container) return;

        if (activePonies.length === 0) {
            container.innerHTML = '<div class="empty-state">No active ponies yet. Spawn some!</div>';
            return;
        }

        container.innerHTML = activePonies.map(function(p, i) {
            return '<div class="pony-item">' +
                '<div class="pony-info">' +
                '<div class="pony-icon">P</div>' +
                '<div>' +
                '<div class="pony-name">' + esc(p.name) + '</div>' +
                '<div class="pony-behavior">' + esc(p.behavior) + '</div>' +
                '</div>' +
                '</div>' +
                '<div class="pony-actions">' +
                '<button class="remove-btn" data-index="' + i + '">X</button>' +
                '</div>' +
                '</div>';
        }).join('');
    }

    function spawnPony(name) {
        if (!name) return;
        console.log('Spawning:', name);

        sendIPC('spawn:' + name);

        activePonies.push({ name: name, behavior: 'spawning...', time: Date.now() });
        renderActivePonies();
        updateCounters();
        setStatus('Spawning ' + name + '...');

        setTimeout(function() {
            var behaviors = ['walking', 'idle', 'bouncing', 'flying'];
            for (var i = 0; i < activePonies.length; i++) {
                if (activePonies[i].name === name && activePonies[i].behavior === 'spawning...') {
                    activePonies[i].behavior = behaviors[Math.floor(Math.random() * 4)];
                    renderActivePonies();
                    break;
                }
            }
        }, 1000);
    }

    function removePony(index) {
        if (index >= 0 && index < activePonies.length) {
            var removed = activePonies.splice(index, 1)[0];
            setStatus('Removed ' + removed.name);
            renderActivePonies();
            updateCounters();
        }
    }

    function removeAllPonies() {
        activePonies = [];
        renderActivePonies();
        updateCounters();
        setStatus('All ponies removed');
    }

    function saveMonitorSettings() {
        var msg = JSON.stringify({ selected_monitors: selectedMonitors });
        console.log('Saving settings:', msg);
        sendIPC('settings:' + msg);
        setStatus('Settings saved: ' + selectedMonitors.length + ' monitor(s)');
    }

    function updateCounters() {
        var counter = document.getElementById('pony-count');
        if (counter) {
            counter.textContent = allPonies.length + ' ponies - ' + activePonies.length + ' active';
        }
    }

    function setStatus(text) {
        var el = document.getElementById('status-text');
        if (el) el.textContent = text;
    }

    function sendIPC(msg) {
        console.log('IPC:', msg);
        try {
            if (window.ipc && window.ipc.postMessage) {
                window.ipc.postMessage(msg);
                console.log('IPC sent');
                return true;
            }
        } catch(e) {
            console.log('IPC error:', e);
        }
        try {
            if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.ipc) {
                window.webkit.messageHandlers.ipc.postMessage(msg);
                console.log('IPC sent via webkit');
                return true;
            }
        } catch(e) {
            console.log('IPC webkit error:', e);
        }
        console.log('IPC NOT AVAILABLE');
        return false;
    }

    function bindEvents() {
        console.log('Binding events...');

        // Табы
        document.querySelectorAll('.tab-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                switchTab(this.dataset.tab);
            });
        });

        // Поиск пони
        var search = document.getElementById('search');
        if (search) {
            search.addEventListener('input', function() {
                renderPonyList(this.value);
            });
        }

        // Клики по списку пони
        var ponyList = document.getElementById('pony-list');
        if (ponyList) {
            ponyList.addEventListener('click', function(e) {
                var spawnBtn = e.target.closest('.spawn-btn');
                if (spawnBtn) {
                    e.stopPropagation();
                    spawnPony(spawnBtn.dataset.name);
                    return;
                }
                var item = e.target.closest('.pony-item');
                if (item && item.dataset.name) {
                    var input = document.getElementById('pony-name');
                    if (input) input.value = item.dataset.name;
                    switchTab('spawn');
                }
            });
        }

        // Кнопка спавна
        var spawnBtn = document.getElementById('btn-spawn');
        if (spawnBtn) {
            spawnBtn.addEventListener('click', function() {
                var input = document.getElementById('pony-name');
                if (input && input.value.trim()) {
                    spawnPony(input.value.trim());
                }
            });
        }

        // Enter в поле ввода
        var spawnInput = document.getElementById('pony-name');
        if (spawnInput) {
            spawnInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && this.value.trim()) {
                    spawnPony(this.value.trim());
                }
            });
        }

        // Активные пони
        var activeList = document.getElementById('active-list');
        if (activeList) {
            activeList.addEventListener('click', function(e) {
                var removeBtn = e.target.closest('.remove-btn');
                if (removeBtn) {
                    removePony(parseInt(removeBtn.dataset.index));
                }
            });
        }

        // Удалить всех
        var removeAllBtn = document.getElementById('btn-remove-all');
        if (removeAllBtn) {
            removeAllBtn.addEventListener('click', removeAllPonies);
        }

        // Сохранить настройки мониторов
        var saveMonitorsBtn = document.getElementById('btn-save-monitors');
        if (saveMonitorsBtn) {
            saveMonitorsBtn.addEventListener('click', saveMonitorSettings);
        }

        // Обновить мониторы
        var refreshBtn = document.getElementById('btn-refresh-monitors');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', function() {
                sendIPC('reload_monitors');
                setStatus('Refreshing monitors...');
                setTimeout(function() {
                    location.reload();
                }, 500);
            });
        }

        // Тема
        document.querySelectorAll('.theme-option').forEach(function(opt) {
            opt.addEventListener('click', function() {
                applyTheme(this.dataset.theme);
            });
        });

        console.log('Events bound');
    }

    function esc(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // Запуск
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();