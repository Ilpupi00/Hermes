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
    models:    'Modelli AI',
    logs:      'Log di Sistema',
    upload:    'Esegui Job',
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

    // Carica i modelli quando si apre la sezione Modelli AI
    if (pageId === 'models') {
        loadModels();
    }

    // Inizializza pagina upload e avvia polling job
    if (pageId === 'upload') {
        if (typeof initUploadPage === 'function') initUploadPage();
        if (typeof startJobsPolling === 'function') startJobsPolling();
    } else {
        if (typeof stopJobsPolling === 'function') stopJobsPolling();
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
        totalActive  += (stats.in_esecuzione || 0);

        const working   = (stats.in_esecuzione || 0) > 0 || (stats.in_coda || 0) > 0;
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
                    <div class="pool-stat-value">${stats.in_esecuzione ?? 0}</div>
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

// ═══════════════════════════════════════════════════════════════════════
//  MODELLI AI — CRUD + Ricerca HuggingFace
// ═══════════════════════════════════════════════════════════════════════

let testModelId = null;

// ── Mostra/Nasconde il campo endpoint_url in base al tipo ─────────────
function onModelTipoChange() {
    const tipo = document.getElementById('model-tipo').value;
    const group = document.getElementById('model-endpoint-group');
    group.style.display = (tipo === 'local_url') ? 'block' : 'none';
}

// ── Load lista modelli dal backend ────────────────────────────────────
async function loadModels() {
    try {
        // Carica modelli e routes in parallelo
        const [modRes, routeRes] = await Promise.all([
            fetch('/api/models'),
            fetch('/api/routes')
        ]);
        const modData   = await modRes.json();
        const routeData = routeRes.ok ? await routeRes.json() : {routes: {}};

        // Ottieni i pool disponibili dallo stato corrente
        const statusRes = await fetch('/api/status');
        const statusData = statusRes.ok ? await statusRes.json() : {pools: {}};
        const availablePools = Object.keys(statusData.pools || {});
        const isRunning = statusData.is_running || false;

        renderModels(modData.models || [], routeData.routes || {}, availablePools, isRunning);
    } catch (e) {
        document.getElementById('models-list').innerHTML =
            '<div class="empty-state-sm">Errore caricamento modelli.</div>';
    }
}

// ── Render lista modelli ──────────────────────────────────────────────
function renderModels(models, routes = {}, availablePools = [], isRunning = false) {
    const container = document.getElementById('models-list');
    if (models.length === 0) {
        container.innerHTML = '<div class="empty-state-sm">Nessun modello registrato.</div>';
        return;
    }

    const poolOptions = isRunning && availablePools.length > 0
        ? `<option value="">— Nessuno (usa default) —</option>` +
          availablePools.map(p => `<option value="${p}">${p}</option>`).join('')
        : `<option value="" disabled>Avvia Hermes per assegnare</option>`;

    container.innerHTML = models.map(m => {
        // Provider detection & logo
        const provider    = (typeof detectProvider === 'function') ? detectProvider(m.nome_modello, m.tipo) : null;
        const logoHtml    = provider ? getProviderLogoHtml(provider, 34) : '';
        const provBadge   = provider ? getProviderBadgeHtml(m.nome_modello, m.tipo) : '';

        let badgeLabel = m.tipo;
        if (m.tipo === 'hf_api')    badgeLabel = 'HF API';
        else if (m.tipo === 'hf_local') badgeLabel = 'HF Local';
        else badgeLabel = 'Local Server';

        const endpoint = m.endpoint_url
            ? `<span title="${m.endpoint_url}">• ${m.endpoint_url.substring(0,28)}${m.endpoint_url.length>28?'…':''}</span>`
            : '';

        // Pool assignment
        const assignedPool = routes[m.nome_modello] || null;
        let poolBadge = '';
        if (!isRunning) {
            poolBadge = `<span class="model-pool-badge offline">⚡ Motore offline</span>`;
        } else if (assignedPool) {
            poolBadge = `<span class="model-pool-badge assigned">◈ ${assignedPool}</span>`;
        } else {
            poolBadge = `<span class="model-pool-badge unassigned">◎ default</span>`;
        }

        const selectDisabled = !isRunning ? 'disabled' : '';
        const selectedPool = assignedPool || '';
        const poolSelectHtml = availablePools.length > 0 || !isRunning
            ? availablePools.map(p => `<option value="${p}" ${p === selectedPool ? 'selected' : ''}>${p}</option>`).join('')
            : '';

        const poolSelectOptions = isRunning
            ? `<option value="" ${!assignedPool ? 'selected' : ''}>— Nessuno (usa default) —</option>${poolSelectHtml}`
            : `<option value="" disabled selected>Avvia Hermes per assegnare</option>`;

        return `
        <div class="model-item">
            <div class="model-item-top">
                <div class="model-item-logo-wrap">
                    ${logoHtml}
                </div>
                <div class="model-item-info">
                    <div class="model-item-name" title="${m.nome_modello}">${m.nome_modello}</div>
                    <div class="model-item-meta">
                        ${provBadge}
                        <span class="model-tipo-badge ${m.tipo}">${badgeLabel}</span>
                        ${endpoint}
                        ${m.descrizione ? `<span title="${m.descrizione}">${m.descrizione.substring(0,35)}${m.descrizione.length>35?'…':''}</span>` : ''}
                    </div>
                </div>
                <div class="model-item-actions">
                    ${m.tipo === 'hf_local' ? `<button class="model-action-btn" onclick='preloadModel(${m.id_modello}, ${JSON.stringify(m.nome_modello)})' title="Precarica modello in memoria RAM/VRAM">⚡ Precarica</button>` : ''}
                    <button class="model-action-btn" onclick='openModelTest(${m.id_modello}, ${JSON.stringify(m.nome_modello)}, ${JSON.stringify(m.tipo)})' title="Testa connessione">Test</button>
                    <button class="model-action-btn" onclick='editModel(${JSON.stringify(m)})' title="Modifica">Modifica</button>
                    <button class="model-action-btn danger" onclick='deleteModel(${m.id_modello}, ${JSON.stringify(m.nome_modello)})' title="Elimina">Elimina</button>
                </div>
            </div>
            <div class="model-pool-row">
                <span class="model-pool-label">Pool →</span>
                ${poolBadge}
                <select class="model-pool-select" id="pool-select-${m.id_modello}" ${selectDisabled} onchange='assignModelToPool(${m.id_modello}, ${JSON.stringify(m.nome_modello)}, this.value)'>
                    ${poolSelectOptions}
                </select>
            </div>
        </div>`;
    }).join('');
}

// ── Salva modello (create o update) ──────────────────────────────────
async function saveModel() {
    const id           = document.getElementById('model-edit-id').value;
    const nome_modello = document.getElementById('model-name').value.trim();
    const tipo         = document.getElementById('model-tipo').value;
    const endpoint_url = document.getElementById('model-endpoint').value.trim() || null;
    const descrizione  = document.getElementById('model-desc').value.trim() || null;

    if (!nome_modello) return showToast('Inserisci il nome del modello', 'error');
    if (tipo === 'local_url' && !endpoint_url) return showToast('Inserisci l\'URL endpoint locale', 'error');

    let res;
    if (id) {
        res = await fetch(`/api/models/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nome_modello, tipo, endpoint_url, descrizione })
        });
    } else {
        res = await fetch('/api/models', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nome_modello, tipo, endpoint_url, descrizione })
        });
    }

    if (res.ok) {
        showToast(id ? 'Modello aggiornato ✓' : 'Modello registrato ✓', 'success');
        resetModelForm();
        loadModels();
    } else {
        const err = await res.json();
        showToast(`Errore: ${err.detail || 'Sconosciuto'}`, 'error');
    }
}

// ── Popola form per modifica ──────────────────────────────────────────
function editModel(m) {
    document.getElementById('model-edit-id').value    = m.id_modello;
    document.getElementById('model-name').value       = m.nome_modello;
    document.getElementById('model-tipo').value       = m.tipo;
    document.getElementById('model-endpoint').value   = m.endpoint_url || '';
    document.getElementById('model-desc').value       = m.descrizione  || '';
    document.getElementById('model-form-title').textContent = `Modifica: ${m.nome_modello}`;
    onModelTipoChange();
    document.getElementById('model-name').focus();
}

// ── Reset form ─────────────────────────────────────────────────────────
function resetModelForm() {
    document.getElementById('model-edit-id').value    = '';
    document.getElementById('model-name').value       = '';
    document.getElementById('model-tipo').value       = 'hf_api';
    document.getElementById('model-endpoint').value   = '';
    document.getElementById('model-desc').value       = '';
    document.getElementById('model-form-title').textContent = 'Registra Modello';
    onModelTipoChange();
}

// ── Assegna modello a pool ─────────────────────────────────────────────
async function assignModelToPool(id, nome, poolName) {
    const select = document.getElementById(`pool-select-${id}`);
    if (select) select.disabled = true;

    try {
        const res = await fetch(`/api/models/${id}/assign-pool`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pool_name: poolName || null })
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message, 'success');
            // Ricarica per aggiornare badge e routing page
            await loadModels();
        } else {
            showToast(`Errore: ${data.message}`, 'error');
            await loadModels(); // ripristina stato corretto
        }
    } catch (e) {
        showToast(`Errore rete: ${e.message}`, 'error');
        if (select) select.disabled = false;
    }
}

// ── Elimina modello ───────────────────────────────────────────────────
async function deleteModel(id, nome) {
    if (!confirm(`Eliminare il modello "${nome}"?`)) return;
    const res = await fetch(`/api/models/${id}`, { method: 'DELETE' });
    if (res.ok) {
        showToast(`Modello "${nome}" eliminato`, 'info');
        loadModels();
    } else {
        showToast('Errore durante eliminazione', 'error');
    }
}

// ── Precaricamento modello locale ────────────────────────────────────
async function preloadModel(id, nome) {
    if (!confirm(`Vuoi forzare il precaricamento in memoria del modello ${nome}?\nL'operazione può richiedere diversi minuti e usare molta RAM.`)) return;

    showToast(`Pre-caricamento di ${nome} avviato, attendere...`, 'info');
    try {
        const resp = await fetch(`/api/models/${id}/preload`, { method: 'POST' });
        const data = await resp.json();
        if (resp.ok) {
            showToast(data.message || `Modello ${nome} precaricato con successo!`, 'success');
        } else {
            showToast(data.detail || `Errore precaricamento ${nome}`, 'error');
        }
    } catch (err) {
        console.error(err);
        showToast("Errore di rete durante il precaricamento", 'error');
    }
}

// ── Apre pannello test ────────────────────────────────────────────────
function openModelTest(id, nome, tipo) {
    testModelId = id;
    document.getElementById('test-model-name').textContent = nome;
    const panel = document.getElementById('model-test-panel');
    panel.style.display = 'block';
    // Mostra/nasconde il campo token in base al tipo
    const tokenGroup = document.getElementById('test-hub-token').closest('.form-group');
    tokenGroup.style.display = (tipo === 'hf_api') ? '' : 'none';
    document.getElementById('test-result').style.display = 'none';
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ── Esegue test connessione ───────────────────────────────────────────
async function testModelConnection() {
    if (!testModelId) return;
    const btn    = document.getElementById('btn-test');
    const result = document.getElementById('test-result');
    btn.disabled = true;
    btn.textContent = '⏳ In corso...';
    result.style.display = 'none';

    const payload = {
        hub_token:  document.getElementById('test-hub-token').value || null,
        prompt:     document.getElementById('test-prompt').value,
        max_tokens: 50,
    };

    try {
        const res  = await fetch(`/api/models/${testModelId}/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        result.style.display = 'block';
        if (data.status === 'ok') {
            result.className = 'test-result ok';
            result.textContent = `✓ OK — Risposta:\n${data.risposta}`;
            showToast('Test superato ✓', 'success');
        } else {
            result.className = 'test-result error';
            result.textContent = `✗ ERRORE:\n${data.detail}`;
            showToast('Test fallito', 'error');
        }
    } catch (e) {
        result.style.display = 'block';
        result.className = 'test-result error';
        result.textContent = `✗ Errore di rete: ${e.message}`;
    } finally {
        btn.disabled = false;
        btn.textContent = '▶ Esegui Test';
    }
}

// ── Ricerca HuggingFace Hub ───────────────────────────────────────────
async function searchHuggingFace() {
    const query   = document.getElementById('hf-search-query').value.trim();
    const task    = document.getElementById('hf-search-task').value;
    const btn     = document.getElementById('btn-hf-search');
    const grid    = document.getElementById('hf-results');

    btn.disabled = true;
    grid.innerHTML = '<div class="hf-searching">🔍 Ricerca in corso su HuggingFace Hub...</div>';

    try {
        const params = new URLSearchParams({ q: query, limit: 12, task });
        const res    = await fetch(`/api/models/search?${params}`);
        const data   = await res.json();

        if (!data.results || data.results.length === 0) {
            grid.innerHTML = '<div class="hf-searching">Nessun risultato trovato.</div>';
            return;
        }

        grid.innerHTML = data.results.map(m => {
            const tagsList = m.tags || [];
            const tagsHtml = tagsList.slice(0, 4).map(t => `<span class="hf-tag">${t}</span>`).join('');
            const likes    = m.likes    >= 1000 ? (m.likes/1000).toFixed(1)+'k'    : m.likes;
            const dl       = m.downloads >= 1000 ? (m.downloads/1000).toFixed(1)+'k' : m.downloads;

            // Provider logo for search results
            const provider    = (typeof detectProvider === 'function') ? detectProvider(m.id, 'hf_api') : null;
            const logoSmall   = provider ? getProviderLogoHtml(provider, 24) : '';
            const provLbl     = provider ? `<span style="color:${provider.color};font-size:10px;font-weight:600;">${provider.label}</span>` : '';

            return `
            <div class="hf-result-card">
                <div class="hf-result-header">
                    ${logoSmall}
                    <div class="hf-result-id" title="${m.id}">${m.id}</div>
                </div>
                <div class="hf-result-meta">
                    ${provLbl}
                    <span>❤️ ${likes}</span>
                    <span>⬇️ ${dl}</span>
                    ${m.pipeline ? `<span>· ${m.pipeline}</span>` : ''}
                </div>
                <div class="hf-result-tags">${tagsHtml}</div>
                <div class="hf-result-actions">
                    <button class="btn-hf-add" onclick='prefillModelForm(${JSON.stringify(m.id)})'>+ Aggiungi</button>
                    <button class="btn-hf-add" style="flex:0;padding:6px 10px;" onclick='window.open("https://huggingface.co/${m.id}","_blank")' title="Apri su HuggingFace">↗</button>
                </div>
            </div>`;
        }).join('');

    } catch (e) {
        grid.innerHTML = `<div class="hf-searching">Errore: ${e.message}</div>`;
    } finally {
        btn.disabled = false;
    }
}

// ── Pre-compila form con modello scelto dalla ricerca ─────────────────
function prefillModelForm(modelId) {
    resetModelForm();
    document.getElementById('model-name').value = modelId;
    document.getElementById('model-tipo').value = 'hf_api';
    onModelTipoChange();
    document.getElementById('model-name').focus();
    // Scroll verso il form
    document.querySelector('.models-layout').scrollIntoView({ behavior: 'smooth', block: 'start' });
    showToast(`"${modelId}" pre-compilato nel form ✓`, 'info');
}