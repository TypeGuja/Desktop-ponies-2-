(function () {
    'use strict';

    var state = { ponies: [], tags: [], houses: [], counts: {}, options: {}, profiles: [], profile: 'default',
        monitors: [], ai: {}, active: [], houses_active: [], origin: '/', custom_tags: [], version: '' };
    var ui = { page: 0, perPage: 24, selectedTags: [], mode: 'all', search: '' };

    function $(id) { return document.getElementById(id); }
    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function send(obj) {
        try { window.ipc.postMessage(JSON.stringify(obj)); } catch (e) { console.error(e); }
    }
    function status(t) { $('status').textContent = t; }

    // ------------------------------------------------------------ tabs
    document.getElementById('tabs').addEventListener('click', function (e) {
        var b = e.target.closest('.tab'); if (!b) return;
        document.querySelectorAll('.tab').forEach(function (t) { t.classList.toggle('active', t === b); });
        document.querySelectorAll('.pane').forEach(function (p) { p.classList.toggle('active', p.id === 'tab-' + b.dataset.tab); });
    });
    function showTab(name) {
        var b = document.querySelector('.tab[data-tab="' + name + '"]'); if (b) b.click();
    }

    // ------------------------------------------------------------ ponies grid
    function ponyMatches(p) {
        if (ui.search && p.n.toLowerCase().indexOf(ui.search) < 0 && p.d.toLowerCase().indexOf(ui.search) < 0) return false;
        var sel = ui.selectedTags.map(function (t) { return t.toLowerCase(); });
        if (ui.mode === 'all' || sel.length === 0) return true;
        var tags = p.t.map(function (t) { return t.toLowerCase(); });
        var has = sel.filter(function (t) { return tags.indexOf(t) >= 0; });
        if (ui.mode === 'any') return has.length > 0;
        if (ui.mode === 'except') return has.length === 0;
        if (ui.mode === 'exactly') return has.length === sel.length && tags.length === sel.length;
        return true;
    }
    function filtered() { return state.ponies.filter(ponyMatches); }

    function renderChips() {
        var all = state.tags;
        $('tag-chips').innerHTML = all.map(function (t) {
            var on = ui.selectedTags.indexOf(t) >= 0;
            return '<span class="chip' + (on ? ' on' : '') + '" data-tag="' + esc(t) + '">' + esc(t) + '</span>';
        }).join('');
    }
    $('tag-chips').addEventListener('click', function (e) {
        var c = e.target.closest('.chip'); if (!c) return;
        var t = c.dataset.tag, i = ui.selectedTags.indexOf(t);
        if (i >= 0) ui.selectedTags.splice(i, 1); else ui.selectedTags.push(t);
        if (ui.mode === 'all') { ui.mode = 'any'; $('filter-mode').value = 'any'; }
        ui.page = 0; renderChips(); renderGrid();
    });

    function renderGrid() {
        var list = filtered();
        var pages = Math.max(1, Math.ceil(list.length / ui.perPage));
        if (ui.page >= pages) ui.page = pages - 1;
        var slice = list.slice(ui.page * ui.perPage, (ui.page + 1) * ui.perPage);
        $('pony-grid').innerHTML = slice.map(function (p) {
            var n = state.counts[p.d] || 0;
            var img = p.p ? '<img loading="lazy" src="' + state.origin + 'files/' + encodeURI(p.p) + '" alt="">' : '';
            return '<div class="pony-card' + (n > 0 ? ' has' : '') + '" data-dir="' + esc(p.d) + '">' +
                '<div class="img">' + img + '</div>' +
                '<div class="name">' + esc(p.n) + '</div>' +
                '<div class="tags">' + esc(p.t.slice(0, 3).join(', ')) + '</div>' +
                '<div class="stepper"><button data-act="dec">-</button>' +
                '<input type="number" min="0" max="999" value="' + n + '" data-act="set">' +
                '<button data-act="inc">+</button>' +
                '<button data-act="spawn" title="Spawn one now">&#9654;</button></div></div>';
        }).join('') || '<div class="hint">No ponies match the filter.</div>';
        $('pg-label').textContent = 'Page ' + (ui.page + 1) + ' of ' + pages + ' (' + list.length + ' ponies)';
        updateTotal();
    }
    function setCount(dir, n) {
        n = Math.max(0, Math.min(999, parseInt(n) || 0));
        if (n > 0) state.counts[dir] = n; else delete state.counts[dir];
        send({ cmd: 'set_count', dir: dir, count: n });
    }
    $('pony-grid').addEventListener('click', function (e) {
        var b = e.target.closest('[data-act]'); if (!b || b.tagName === 'INPUT') return;
        var card = e.target.closest('.pony-card'), dir = card.dataset.dir, cur = state.counts[dir] || 0;
        if (b.dataset.act === 'inc') setCount(dir, cur + 1);
        else if (b.dataset.act === 'dec') setCount(dir, cur - 1);
        else if (b.dataset.act === 'spawn') { send({ cmd: 'spawn', dir: dir }); status('Added ' + dir); return; }
        renderGrid();
    });
    $('pony-grid').addEventListener('change', function (e) {
        var i = e.target.closest('[data-act="set"]'); if (!i) return;
        setCount(i.closest('.pony-card').dataset.dir, i.value); renderGrid();
    });
    function updateTotal() {
        var t = 0; for (var k in state.counts) t += state.counts[k];
        $('total-label').textContent = t + ' pon' + (t === 1 ? 'y' : 'ies') + ' selected';
    }
    $('search').addEventListener('input', function () { ui.search = this.value.toLowerCase(); ui.page = 0; renderGrid(); });
    $('filter-mode').addEventListener('change', function () { ui.mode = this.value; ui.page = 0; renderGrid(); });
    $('per-page').addEventListener('change', function () { ui.perPage = parseInt(this.value); ui.page = 0; renderGrid(); });
    $('pg-first').onclick = function () { ui.page = 0; renderGrid(); };
    $('pg-prev').onclick = function () { ui.page = Math.max(0, ui.page - 1); renderGrid(); };
    $('pg-next').onclick = function () { ui.page++; renderGrid(); };
    $('pg-last').onclick = function () { ui.page = 1e9; renderGrid(); };
    $('btn-zero').onclick = function () { filtered().forEach(function (p) { delete state.counts[p.d]; }); send({ cmd: 'set_counts', counts: state.counts }); renderGrid(); };
    $('btn-one').onclick = function () { filtered().forEach(function (p) { state.counts[p.d] = 1; }); send({ cmd: 'set_counts', counts: state.counts }); renderGrid(); };
    $('btn-go').onclick = function () { send({ cmd: 'go' }); status('Starting ponies...'); };

    // ------------------------------------------------------------ active / houses
    function renderActive() {
        $('active-badge').textContent = state.active.length;
        $('active-list').innerHTML = state.active.map(function (a) {
            return '<div class="row-item"><span class="grow">' + esc(a.n) + ' <span class="muted">&middot; ' + esc(a.b) + (a.s ? ' &middot; sleeping' : '') + '</span></span>' +
                '<button class="btn small" data-act="sleep" data-id="' + a.id + '">' + (a.s ? 'Wake' : 'Sleep') + '</button>' +
                '<button class="btn small" data-act="talk" data-id="' + a.id + '">Talk</button>' +
                '<button class="btn small danger" data-act="remove" data-id="' + a.id + '">Remove</button></div>';
        }).join('') || '<div class="hint">No active ponies yet. Choose some and press GIVE ME PONIES!</div>';
        $('house-active').innerHTML = state.houses_active.map(function (h) {
            return '<div class="row-item"><span class="grow">' + esc(h.n) + '</span>' +
                '<button class="btn small danger" data-act="rmhouse" data-id="' + h.id + '">Remove</button></div>';
        }).join('') || '<div class="hint">No houses on the desktop.</div>';
    }
    $('active-list').addEventListener('click', function (e) {
        var b = e.target.closest('[data-act]'); if (!b) return;
        var id = parseInt(b.dataset.id);
        if (b.dataset.act === 'remove') send({ cmd: 'remove', id: id });
        if (b.dataset.act === 'sleep') send({ cmd: 'sleep', id: id });
        if (b.dataset.act === 'talk') send({ cmd: 'talk', id: id });
    });
    $('house-active').addEventListener('click', function (e) {
        var b = e.target.closest('[data-act="rmhouse"]'); if (b) send({ cmd: 'remove_house', id: parseInt(b.dataset.id) });
    });
    $('btn-remove-all').onclick = function () { send({ cmd: 'remove_all' }); };
    $('btn-sleep-all').onclick = function () { send({ cmd: 'sleep_all' }); };

    function renderHouses() {
        $('house-list').innerHTML = state.houses.map(function (h) {
            var img = h.p ? '<img loading="lazy" src="' + state.origin + 'files/' + encodeURI(h.p) + '" alt="" style="max-height:84px">' : '';
            return '<div class="pony-card"><div class="img">' + img + '</div><div class="name">' + esc(h.n) + '</div>' +
                '<button class="btn small" data-house="' + h.i + '">Add to desktop</button></div>';
        }).join('') || '<div class="hint">No houses found in the Houses folder.</div>';
    }
    $('house-list').addEventListener('click', function (e) {
        var b = e.target.closest('[data-house]'); if (b) { send({ cmd: 'add_house', index: parseInt(b.dataset.house) }); status('House added'); }
    });

    // ------------------------------------------------------------ options
    var SCHEMA = [
        { title: 'Ponies', items: [
            { k: 'pony_speech_enabled', l: 'Enable speech', t: 'bool' },
            { k: 'pony_speech_chance', l: 'Random speech chance (%)', t: 'pct', min: 0, max: 100, step: 0.5 },
            { k: 'pony_effects_enabled', l: 'Enable effects', t: 'bool' },
            { k: 'pony_interactions_enabled', l: 'Enable interactions', t: 'bool' },
            { k: 'pony_dragging_enabled', l: 'Enable dragging', t: 'bool' },
            { k: 'cursor_avoidance_enabled', l: 'Ponies avoid cursor / stop when hovered over', t: 'bool' },
            { k: 'cursor_avoidance_size', l: 'Radius around cursor to avoid (px)', t: 'num', min: 0, max: 10000, step: 10 },
            { k: 'max_pony_count', l: 'Max number of ponies', t: 'num', min: 0, max: 10000, step: 10 },
            { k: 'scale_factor', l: 'Pony sizes (x)', t: 'range', min: 0.25, max: 4, step: 0.25 },
            { k: 'time_factor', l: 'Time dilation (x)', t: 'range', min: 0.1, max: 10, step: 0.1 },
            { k: 'pony_avoids_ponies', l: 'Ponies try to avoid other ponies', t: 'bool' },
            { k: 'window_avoidance_enabled', l: 'Ponies try to avoid other windows', t: 'bool' },
            { k: 'window_containment', l: "Ponies don't leave windows they are inside", t: 'bool' },
            { k: 'pony_teleport_enabled', l: 'Ponies teleport back in bounds (instead of walking)', t: 'bool' },
            // Пункт "Skeletal animation" (k: 'skeletal_animation') временно убран из
            // интерфейса; логика в Rust сохранена и по умолчанию выключена.
            { k: 'no_random_duplicates', l: 'No duplicates when choosing random ponies', t: 'bool' } ] },
        { title: 'Performance', items: [
            { k: 'fps_limit', l: 'Frame rate limit (FPS): higher = smoother movement, more CPU', t: 'range', min: 10, max: 240, step: 5 } ] },
        { title: 'Windows', items: [
            { k: 'always_on_top', l: 'Ponies are always on top of other windows', t: 'bool' },
            { k: 'show_in_taskbar', l: 'Show ponies in taskbar', t: 'bool' },
            { k: 'suspend_for_fullscreen_application', l: 'Hide ponies while a full-screen application is running', t: 'bool' } ] },
        { title: 'Sound', items: [
            { k: 'sound_enabled', l: 'Enable sounds', t: 'bool' },
            { k: 'sound_volume', l: 'Sound volume', t: 'range', min: 0, max: 1, step: 0.05 },
            { k: 'sound_single_channel_only', l: 'Limit sounds to one at a time', t: 'bool' } ] }
    ];
    var draft = {};

    function optRow(it) {
        var v = draft[it.k];
        if (it.t === 'bool') return '<div class="opt-row"><label><input type="checkbox" data-k="' + it.k + '"' + (v ? ' checked' : '') + '> ' + esc(it.l) + '</label></div>';
        if (it.t === 'pct') v = Math.round(v * 1000) / 10;
        var kind = it.t === 'range' ? 'range' : 'number';
        return '<div class="opt-row"><label>' + esc(it.l) + '</label><input type="' + kind + '" data-k="' + it.k + '" data-t="' + it.t +
            '" min="' + it.min + '" max="' + it.max + '" step="' + it.step + '" value="' + v + '"><span class="val">' + (kind === 'range' ? v : '') + '</span></div>';
    }
    function renderOptions() {
        draft = JSON.parse(JSON.stringify(state.options));
        var html = SCHEMA.map(function (g) {
            return '<div class="opt-group"><h4>' + g.title + '</h4>' + g.items.map(optRow).join('') + '</div>';
        }).join('');
        // Экран
        html += '<div class="opt-group"><h4>Screen</h4><div class="hint">Select monitors on which ponies may appear:</div>' +
            state.monitors.map(function (m) {
                var on = (draft.screens || []).indexOf(m.name) >= 0;
                return '<label class="mon"><input type="checkbox" data-mon="' + esc(m.name) + '"' + (on ? ' checked' : '') + '> ' + esc(m.name) +
                    ' &mdash; ' + m.w + 'x' + m.h + ' at (' + m.x + ',' + m.y + ')' + (m.primary ? ' [primary]' : '') + '</label>';
            }).join('') +
            '<div class="opt-row"><label><input type="checkbox" id="region-on"' + (draft.allowed_region ? ' checked' : '') + '> Limit to an area (px):</label>' +
            ['x', 'y', 'w', 'h'].map(function (c, i) {
                var r = draft.allowed_region || [0, 0, 0, 0];
                return '<input type="number" style="width:76px" data-region="' + i + '" value="' + r[i] + '" title="' + c + '">';
            }).join('') + '</div>' +
            '<div class="opt-row"><label>Avoid a portion of the area (% of area x, y, w, h):</label>' +
            ['x', 'y', 'w', 'h'].map(function (c, i) {
                var z = draft.exclusion_zone || [0, 0, 0, 0];
                return '<input type="number" style="width:64px" min="0" max="100" data-excl="' + i + '" value="' + Math.round(z[i] * 100) + '" title="' + c + '">';
            }).join('') + '</div></div>';
        $('options-form').innerHTML = html;
        $('options-form').querySelectorAll('input[type=range]').forEach(function (r) { r.nextSibling.textContent = r.value; });
    }
    $('options-form').addEventListener('input', function (e) {
        var i = e.target, k = i.dataset.k;
        if (k) {
            if (i.type === 'checkbox') draft[k] = i.checked;
            else { var n = parseFloat(i.value); if (isNaN(n)) return; draft[k] = i.dataset.t === 'pct' ? n / 100 : n; if (i.type === 'range') i.nextSibling.textContent = n; }
        }
        if (i.dataset.mon) {
            var s = draft.screens || []; var idx = s.indexOf(i.dataset.mon);
            if (i.checked && idx < 0) s.push(i.dataset.mon); if (!i.checked && idx >= 0) s.splice(idx, 1);
            draft.screens = s;
        }
        if (i.dataset.region !== undefined || i.id === 'region-on') {
            var vals = Array.from(document.querySelectorAll('[data-region]')).map(function (x) { return parseInt(x.value) || 0; });
            draft.allowed_region = $('region-on').checked && vals[2] > 0 && vals[3] > 0 ? vals : null;
        }
        if (i.dataset.excl !== undefined) {
            draft.exclusion_zone = Array.from(document.querySelectorAll('[data-excl]')).map(function (x) { return Math.max(0, Math.min(1, (parseFloat(x.value) || 0) / 100)); });
        }
    });
    $('btn-options-apply').onclick = function () { send({ cmd: 'options', data: draft, save: false }); status('Options applied'); };
    $('btn-options-save').onclick = function () { send({ cmd: 'options', data: draft, save: true }); status('Options applied and saved to the profile'); };
    $('btn-options-reset').onclick = function () { send({ cmd: 'options_reset' }); };

    // ------------------------------------------------------------ profiles
    function renderProfiles() {
        var names = ['default'].concat(state.profiles.filter(function (p) { return p !== 'default'; }));
        $('profile-select').innerHTML = names.map(function (n) {
            return '<option' + (n === state.profile ? ' selected' : '') + '>' + esc(n) + '</option>';
        }).join('');
        $('custom-tags').innerHTML = state.custom_tags.map(function (t) {
            return '<span class="chip">' + esc(t) + '<span class="x" data-rmtag="' + esc(t) + '">&times;</span></span>';
        }).join('');
    }
    $('profile-select').onchange = function () { send({ cmd: 'profile', op: 'load', name: this.value }); };
    $('pf-load').onclick = function () { send({ cmd: 'profile', op: 'load', name: $('profile-select').value }); };
    $('pf-save').onclick = function () {
        var name = $('profile-select').value;
        if (name === 'default') { name = prompt('Profile name to save as:'); if (!name) return; }
        send({ cmd: 'profile', op: 'save', name: name });
    };
    $('pf-copy').onclick = function () { var n = prompt('Name for the copy:'); if (n) send({ cmd: 'profile', op: 'save', name: n }); };
    $('pf-delete').onclick = function () {
        var n = $('profile-select').value; if (n !== 'default' && confirm('Delete profile "' + n + '"?')) send({ cmd: 'profile', op: 'delete', name: n });
    };
    $('tag-add').onclick = function () { var t = $('tag-input').value.trim(); if (t) { send({ cmd: 'tag_add', tag: t }); $('tag-input').value = ''; } };
    $('custom-tags').addEventListener('click', function (e) {
        var x = e.target.closest('[data-rmtag]'); if (x) send({ cmd: 'tag_remove', tag: x.dataset.rmtag });
    });

    // ------------------------------------------------------------ AI
    function renderAi() {
        var ai = state.ai || {};
        $('ai-url').value = ai.base_url || ''; $('ai-model').value = ai.model || ''; $('ai-lang').value = ai.language || '';
        $('ai-spont').checked = !!ai.spontaneous;
        $('ai-status').textContent = ai.has_key
            ? 'AI is enabled: right-click a pony and choose Talk. Original pony speech still works too.'
            : 'No API key: only the original pony.ini speech is used. Add a key to let ponies talk with you.';
    }
    $('ai-save').onclick = function () {
        send({ cmd: 'ai_save', data: { api_key: $('ai-key').value.trim(), base_url: $('ai-url').value.trim(), model: $('ai-model').value.trim(),
            language: $('ai-lang').value.trim() || 'Russian', spontaneous: $('ai-spont').checked } });
        $('ai-key').value = ''; status('AI settings saved');
    };
    $('ai-clear').onclick = function () { send({ cmd: 'ai_clear' }); status('API key removed'); };

    $('btn-editor').onclick = function () { send({ cmd: 'open_editor' }); status('Opening Pony Editor...'); };
    $('btn-reload').onclick = function () { send({ cmd: 'reload' }); status('Reloading ponies...'); };

    // ------------------------------------------------------------ receive
    window.dpReceive = function (msg) {
        if (msg.type === 'state') {
            state = Object.assign(state, msg.data);
            renderChips(); renderGrid(); renderHouses(); renderActive(); renderOptions(); renderProfiles(); renderAi();
            $('about').textContent = state.version || '';
        } else if (msg.type === 'active') {
            state.active = msg.list; state.houses_active = msg.houses || []; renderActive();
        } else if (msg.type === 'status') {
            status(msg.text);
        } else if (msg.type === 'tab') {
            showTab(msg.name);
        } else if (msg.type === 'counts') {
            state.counts = msg.counts; renderGrid();
        }
    };
    send({ cmd: 'ready' });
})();
