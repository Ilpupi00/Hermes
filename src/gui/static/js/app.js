/* ===========================================
   HERMES — app.js
   Nessuna modifica alla logica dei Thread Pool.
   Solo UI: navigazione, rendering, modal, toast.
   =========================================== */

// ── WebSocket logs ──────────────────────────────────────────────────
const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocket(`${wsProto}://${window.location.host}/ws/logs`);
const terminal = document.getElementById('terminal-output');
const MAX_TERMINAL_LINES = 2000;

ws.onmessage = function(event) {
    const timestamp = new Date().toLocaleTimeString('it-IT');
    terminal.textContent += `[${timestamp}] ${event.data}\n`;
    const lines = terminal.textContent.split('\n');
    if (lines.length > MAX_TERMINAL_LINES) {
        terminal.textContent = lines.slice(-MAX_TERMINAL_LINES).join('\n');
    }
    const tc = document.getElementById('terminal-container');
    tc.scrollTop = tc.scrollHeight;
};

// ── Routing: sincronizzato col backend ──────────────────────────────
// NON usiamo più un oggetto locale: le route vengono sempre lette dal server.

// ── Navigazione multi-pagina ─────────────────────────────────────────
const PAGE_TITLES = {
    dashboard: 'Dashboard',
    pools:     'Thread Pools',
    routing:   'Routing Modelli',
    logs:      'Log di Sistema',
};

function navigate(pageId, el) {
    // Nasconde tutte le pagine
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    // Mostra la pagina target
    document.getElementById(`page-${pageId}`).classList.add('active');
    if (el) el.classList.add('active');

    // Aggiorna titolo topbar
    document.getElementById('topbar-title').textContent = PAGE_TITLES[pageId] || pageId;

    // Aggiorna la select dei pool nella pagina routing
    if (pageId === 'routing') {
        refreshRoutePoolSelect();
        loadRoutes();
    }

    return false;
}

// ── Clock ─────────────────────────────────────────────────────────────
function updateClock() {
    const el = document.getElementById('topbar-time');
    if (el) el.textContent = new Date().toLocaleTimeString('it-IT');
}
setInterval(updateClock, 1000);
updateClock();

// ── Status polling ────────────────────────────────────────────────────
async function updateStatus() {
    try {
        const res  = await fetch('/api/status');
        const data = await res.json();

        const isRunning = data.is_running;

        // Status indicators
        const dot   = document.getElementById('status-dot');
        const label = document.getElementById('status-label');
        const pill  = document.getElementById('status-pill');
        const pillDot  = pill.querySelector('.pill-dot');
        const pillText = document.getElementById('pill-text');

        if (isRunning) {
            dot.classList.add('online');
            label.textContent = 'ONLINE';
            pill.classList.add('online');
            pillDot.classList.add('online');
            pillText.textContent = 'ONLINE';
        } else {
            dot.classList.remove('online');
            label.textContent = 'OFFLINE';
            pill.classList.remove('online');
            pillDot.classList.remove('online');
            pillText.textContent = 'OFFLINE';
        }

        // Bottoni avvio/arresto
        const btnStart   = document.getElementById('btn-start');
        const btnStop    = document.getElementById('btn-stop');
        const btnAddPool = document.getElementById('btn-add-pool');

        btnStart.disabled   = isRunning;
        btnStop.disabled    = !isRunning;
        btnAddPool.disabled = !isRunning;

        // Rendering pool nelle due pagine (Dashboard e Pool Manager)
        renderPools(data.pools, isRunning);

    } catch (e) { console.error('Status error:', e); }
}

// ── Rendering Pool ────────────────────────────────────────────────────
function renderPools(pools, isRunning) {
    const overview = document.getElementById('pools-overview');
    const manage   = document.getElementById('pools-manage-container');

    const emptyHTML = (icon, msg) => `
        <div class="empty-state">
            <div class="empty-icon">${icon}</div>
            <p>${msg}</p>
        </div>`;

    if (!isRunning || !pools || Object.keys(pools).length === 0) {
        const msg = isRunning
            ? emptyHTML('◈', 'Nessun pool attivo — aggiungine uno!')
            : emptyHTML('⚡', 'Avvia Hermes per visualizzare i pool');
        overview.innerHTML = msg;
        manage.innerHTML   = msg;

        // KPI a zero
        document.getElementById('kpi-pools').textContent   = '0';
        document.getElementById('kpi-workers').textContent = '0';
        document.getElementById('kpi-queue').textContent   = '0';
        document.getElementById('kpi-active').textContent  = '0';
        return;
    }

    const entries = Object.entries(pools);
    let totalWorkers = 0, totalQueue = 0, totalActive = 0;

    let html = '';
    for (const [name, stats] of entries) {
        totalWorkers += (stats.max_workers || 0);
        totalQueue   += (stats.in_coda    || 0);
        totalActive  += (stats.attivi     || 0);

        const working   = (stats.in_coda || 0) > 0;
        const safeName  = String(name).replace(/[&<>"'`]/g, '');
        const dotClass  = working ? 'active' : '';
        const cardClass = working ? 'working' : '';

        html += `
        <div class="pool-card ${cardClass}">
            <div class="pool-card-header">
                <div class="pool-card-name">
                    <span class="pool-dot ${dotClass}"></span>
                    ${safeName.toUpperCase()}
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
                    <span class="pool-badge">${stats.max_workers} workers</span>
                    <div class="pool-actions">
                        <button class="pool-action-btn" onclick='editPool(${JSON.stringify(name)}, ${stats.max_workers})' title="Modifica">✏️</button>
                        <button class="pool-action-btn" onclick='deletePool(${JSON.stringify(name)})' title="Elimina">🗑️</button>
                    </div>
                </div>
            </div>
            <div class="pool-card-stats">
                <div class="pool-stat">
                    <div class="pool-stat-label">In Coda</div>
                    <div class="pool-stat-value">${stats.in_coda ?? 0}</div>
                </div>
                <div class="pool-stat">
                    <div class="pool-stat-label">Attivi</div>
                    <div class="pool-stat-value">${stats.attivi ?? 0}</div>
                </div>
            </div>
        </div>`;
    }

    overview.innerHTML = html;
    manage.innerHTML   = html;

    // KPI
    document.getElementById('kpi-pools').textContent   = entries.length;
    document.getElementById('kpi-workers').textContent = totalWorkers;
    document.getElementById('kpi-queue').textContent   = totalQueue;
    document.getElementById('kpi-active').textContent  = totalActive;
}

// ── Start / Stop ───────────────────────────────────────────────────────
async function startHermes() {
    const workers  = parseInt(document.getElementById('workers').value)  || 4;
    const interval = parseInt(document.getElementById('interval').value) || 15;
    const res = await fetch('/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workers, interval })
    });
    const data = await res.json();
    showToast(data.status === 'started' ? 'Hermes avviato ✓' : 'Già in esecuzione', 'success');
    updateStatus();
}

async function stopHermes() {
    await fetch('/api/stop', { method: 'POST' });
    showToast('Hermes arrestato', 'info');
    updateStatus();
}

// ── Add Pool (tramite modal) ───────────────────────────────────────────
let modalMode = 'add';
let modalOldName = null;

function openAddPoolModal() {
    modalMode    = 'add';
    modalOldName = null;
    document.getElementById('modal-title').textContent         = 'Nuovo Pool';
    document.getElementById('modal-confirm-btn').textContent   = 'Crea Pool';
    document.getElementById('modal-pool-name').value          = '';
    document.getElementById('modal-pool-workers').value       = '';
    document.getElementById('modal-pool-name').disabled       = false;
    openModal();
}

function openModal()  { document.getElementById('modal-overlay').classList.add('open'); }
function closeModal() { document.getElementById('modal-overlay').classList.remove('open'); }

async function confirmModal() {
    const name    = document.getElementById('modal-pool-name').value.trim();
    const workers = parseInt(document.getElementById('modal-pool-workers').value);

    if (!name)          return showToast('Inserisci un nome per il pool', 'error');
    if (!workers || workers < 1) return showToast('Inserisci un numero valido di workers', 'error');

    if (modalMode === 'add') {
        const res = await fetch('/api/pools', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, workers })
        });
        const data = await res.json();
        showToast(data.success ? `Pool "${name}" creato ✓` : `Errore: ${data.error}`, data.success ? 'success' : 'error');
    } else {
        const res = await fetch(`/api/pools/${encodeURIComponent(modalOldName)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_name: name, workers })
        });
        const data = await res.json();
        showToast(data.success ? `Pool aggiornato ✓` : `Errore: ${data.message}`, data.success ? 'success' : 'error');
    }

    closeModal();
    updateStatus();
}

// ── Edit / Delete Pool ─────────────────────────────────────────────────
function editPool(oldName, currentWorkers) {
    modalMode    = 'edit';
    modalOldName = oldName;
    document.getElementById('modal-title').textContent         = `Modifica "${oldName}"`;
    document.getElementById('modal-confirm-btn').textContent   = 'Salva Modifiche';
    document.getElementById('modal-pool-name').value          = oldName;
    document.getElementById('modal-pool-workers').value       = currentWorkers;
    document.getElementById('modal-pool-name').disabled       = false;
    openModal();
}

async function deletePool(name) {
    if (!confirm(`Eliminare il pool "${name}"?\nI task in coda verranno annullati.`)) return;
    const res    = await fetch(`/api/pools/${encodeURIComponent(name)}`, { method: 'DELETE' });
    const result = await res.json();
    showToast(result.success ? `Pool "${name}" eliminato` : `Errore: ${result.message}`, result.success ? 'info' : 'error');
    updateStatus();
}

// ── Routing ────────────────────────────────────────────────────────────
function refreshRoutePoolSelect() {
    const sel = document.getElementById('route-pool');
    // Leggiamo i pool dal DOM già renderizzato (senza refetch)
    const cards = document.querySelectorAll('#pools-manage-container .pool-card .pool-card-name');
    sel.innerHTML = '<option value="" disabled selected>Seleziona un pool...</option>';
    cards.forEach(card => {
        const name = card.textContent.trim().toLowerCase();
        const opt  = document.createElement('option');
        opt.value  = name;
        opt.textContent = name;
        sel.appendChild(opt);
    });
}

async function saveRoute() {
    const modelName = document.getElementById('route-model').value.trim();
    const poolName  = document.getElementById('route-pool').value;
    if (!modelName) return showToast('Inserisci il nome del modello', 'error');
    if (!poolName)  return showToast('Seleziona un pool di destinazione', 'error');

    const res  = await fetch('/api/routes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: modelName, pool_name: poolName })
    });
    const data = await res.json();

    if (data.success) {
        document.getElementById('route-model').value = '';
        document.getElementById('route-pool').value  = '';
        await loadRoutes();
        showToast(`Routing: ${modelName} → ${poolName} ✓`, 'success');
    } else {
        showToast(`Errore: ${data.error}`, 'error');
    }
}

async function deleteRoute(modelName) {
    const res    = await fetch(`/api/routes/${encodeURIComponent(modelName)}`, { method: 'DELETE' });
    const result = await res.json();
    if (result.success) {
        showToast(`Regola "${modelName}" rimossa`, 'info');
        await loadRoutes();
    } else {
        showToast(`Errore: ${result.error}`, 'error');
    }
}

async function loadRoutes() {
    try {
        const res  = await fetch('/api/routes');
        const data = await res.json();
        renderRoutes(data.routes || {});
    } catch (e) {
        renderRoutes({});
    }
}

function renderRoutes(routes) {
    const list    = document.getElementById('routes-list');
    const entries = Object.entries(routes);
    if (entries.length === 0) {
        list.innerHTML = '<div class="empty-state-sm">Nessuna regola configurata.</div>';
        return;
    }
    list.innerHTML = entries.map(([model, pool]) => `
        <div class="route-item">
            <span class="route-model">${model}</span>
            <span class="route-arrow">→</span>
            <span class="route-pool">${pool}</span>
            <button class="route-delete-btn" onclick="deleteRoute(${JSON.stringify(model)})" title="Rimuovi regola">✕</button>
        </div>
    `).join('');
}

// ── Log export ─────────────────────────────────────────────────────────
function downloadLogs() {
    const startEl = document.getElementById('log-start').value;
    const endEl   = document.getElementById('log-end').value;
    const toISO   = v => v ? v + ':00' : null;

    let url = '/api/logs/download';
    const params = new URLSearchParams();
    if (toISO(startEl)) params.set('start', toISO(startEl));
    if (toISO(endEl))   params.set('end',   toISO(endEl));
    if ([...params].length) url += '?' + params.toString();

    const a = document.createElement('a');
    a.href = url; a.download = ''; document.body.appendChild(a);
    a.click(); document.body.removeChild(a);
    showToast('Download avviato', 'info');
}

function clearTerminal() {
    document.getElementById('terminal-output').textContent = '';
    showToast('Terminale pulito', 'info');
}

// ── Toast ──────────────────────────────────────────────────────────────
let toastTimer = null;
function showToast(msg, type = 'info') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className   = `toast ${type} show`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 3000);
}

// ── Boot ───────────────────────────────────────────────────────────────
setInterval(updateStatus, 1500);
updateStatus();