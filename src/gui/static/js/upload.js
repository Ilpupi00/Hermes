/* =============================================================
   HERMES — upload.js
   Logica pagina "Esegui Job":
   - Drag & drop / file picker CSV
   - Preview prime righe (client-side)
   - Submit multipart al backend POST /api/upload
   - Polling GET /api/jobs + GET /api/jobs/{id}/results
   - Render tabella risultati live + download
   ============================================================= */

// ── Stato della pagina ──────────────────────────────────────────────────────
let uploadState = {
    file:        null,
    headers:     [],
    previewRows: [],
    jobsPolling: null,
};

// ── Inizializzazione (chiamata da navigate()) ────────────────────────────────
function initUploadPage() {
    setupDropZone();
    populateModelSelect();
    loadJobs();
}

// ── Popola select modelli dalla API ─────────────────────────────────────────
async function populateModelSelect() {
    const sel = document.getElementById('upload-model-select');
    if (!sel) return;
    try {
        const res  = await fetch('/api/models');
        const data = await res.json();
        const models = data.models || [];

        if (models.length === 0) {
            sel.innerHTML = '<option value="" disabled selected>— Nessun modello registrato —</option>';
            return;
        }
        sel.innerHTML = '<option value="" disabled selected>Seleziona modello AI…</option>' +
            models.map(m => {
                const provider = (typeof detectProvider === 'function')
                    ? detectProvider(m.nome_modello, m.tipo)
                    : { label: m.tipo };
                return `<option value="${m.id_modello}" data-tipo="${m.tipo}">
                    ${provider.label} — ${m.nome_modello}
                </option>`;
            }).join('');

        // Mostra/nasconde il campo token in base al tipo selezionato
        sel.addEventListener('change', onUploadModelChange);
    } catch (e) {
        console.error('Errore caricamento modelli:', e);
    }
}

function onUploadModelChange() {
    const sel      = document.getElementById('upload-model-select');
    const opt      = sel.options[sel.selectedIndex];
    const tipo     = opt?.dataset?.tipo || '';
    const tokenRow = document.getElementById('upload-token-row');
    if (tokenRow) tokenRow.style.display = (tipo === 'hf_api') ? 'flex' : 'none';
}

// ── Drag & Drop Zone ─────────────────────────────────────────────────────────
function setupDropZone() {
    const zone  = document.getElementById('csv-drop-zone');
    const input = document.getElementById('csv-file-input');
    if (!zone || !input) return;

    zone.addEventListener('click',      () => input.click());
    zone.addEventListener('dragover',   e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave',  () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop',       e => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        const f = e.dataTransfer.files[0];
        if (f) handleCsvFile(f);
    });
    input.addEventListener('change', () => {
        if (input.files[0]) handleCsvFile(input.files[0]);
    });
}

// ── Lettura e anteprima CSV (client-side) ────────────────────────────────────
function handleCsvFile(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
        showToast('Il file deve essere un CSV', 'error');
        return;
    }
    uploadState.file = file;

    const reader = new FileReader();
    reader.onload = e => {
        const text  = e.target.result;
        const lines = text.split(/\r?\n/).filter(l => l.trim());
        if (lines.length < 2) {
            showToast('CSV vuoto o senza dati', 'error');
            return;
        }

        // Parsing semplice (gestisce le virgolette di base)
        const parseRow = line => {
            const result = [];
            let current  = '';
            let inQ      = false;
            for (const ch of line) {
                if (ch === '"') { inQ = !inQ; }
                else if (ch === ',' && !inQ) { result.push(current); current = ''; }
                else { current += ch; }
            }
            result.push(current);
            return result.map(c => c.trim());
        };

        uploadState.headers     = parseRow(lines[0]);
        uploadState.previewRows = lines.slice(1, 6).map(parseRow);

        renderCsvPreview(file.name, lines.length - 1);
        updateDropZoneLabel(file.name, lines.length - 1);
    };
    reader.readAsText(file, 'utf-8');
}

function updateDropZoneLabel(name, nRighe) {
    const zone = document.getElementById('csv-drop-zone');
    if (!zone) return;
    zone.innerHTML = `
        <div class="dz-icon">✓</div>
        <div class="dz-filename">${name}</div>
        <div class="dz-meta">${nRighe} righe di dati · clicca per cambiare</div>
    `;
    zone.classList.add('has-file');
}

function renderCsvPreview(name, nRighe) {
    const section = document.getElementById('csv-preview-section');
    const table   = document.getElementById('csv-preview-table');
    if (!section || !table) return;

    section.style.display = 'block';
    document.getElementById('csv-preview-info').textContent =
        `${name} — ${nRighe} righe totali · anteprima prime 5`;

    const { headers, previewRows } = uploadState;
    table.innerHTML = `
        <thead>
            <tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr>
        </thead>
        <tbody>
            ${previewRows.map(r =>
                `<tr>${headers.map((_, i) =>
                    `<td>${r[i] ?? ''}</td>`
                ).join('')}</tr>`
            ).join('')}
        </tbody>
    `;
}

// ── Submit del job ────────────────────────────────────────────────────────────
async function submitUploadJob() {
    const modelSel   = document.getElementById('upload-model-select');
    const promptEl   = document.getElementById('upload-prompt');
    const tempEl     = document.getElementById('upload-temperatura');
    const tokensEl   = document.getElementById('upload-max-tokens');
    const chunkEl    = document.getElementById('upload-chunk-size');
    const tokenEl    = document.getElementById('upload-hub-token');
    const btn        = document.getElementById('btn-upload-submit');

    if (!uploadState.file) return showToast('Carica un CSV prima', 'error');
    if (!modelSel.value)   return showToast('Seleziona un modello AI', 'error');
    if (!promptEl.value.trim()) return showToast('Inserisci il prompt', 'error');

    btn.disabled    = true;
    btn.textContent = '⏳ Caricamento…';

    const fd = new FormData();
    fd.append('file',        uploadState.file);
    fd.append('id_modello',  modelSel.value);
    fd.append('prompt',      promptEl.value.trim());
    fd.append('temperatura', tempEl.value  || '0.1');
    fd.append('max_tokens',  tokensEl.value || '500');
    fd.append('chunk_size',  chunkEl.value  || '1000');
    if (tokenEl && tokenEl.value.trim())
        fd.append('hub_token', tokenEl.value.trim());

    try {
        const res  = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await res.json();

        if (!res.ok) {
            showToast(`Errore: ${data.detail || 'Upload fallito'}`, 'error');
            return;
        }

        showToast(`✓ Job ${data.id_esecuzione} avviato — ${data.n_righe} righe`, 'success');
        renderUploadResult(data);
        loadJobs();

        // Resetta il form
        uploadState.file = null;
        const zone = document.getElementById('csv-drop-zone');
        if (zone) {
            zone.classList.remove('has-file');
            zone.innerHTML = `
                <div class="dz-icon">📄</div>
                <div class="dz-label">Trascina un CSV qui o <strong>clicca per selezionare</strong></div>
                <div class="dz-meta">Formati supportati: CSV UTF-8 · max 50 MB</div>
            `;
        }
        document.getElementById('csv-preview-section').style.display = 'none';
        document.getElementById('csv-file-input').value = '';

    } catch (e) {
        showToast(`Errore rete: ${e.message}`, 'error');
    } finally {
        btn.disabled    = false;
        btn.textContent = '▶ Avvia Elaborazione';
    }
}

function renderUploadResult(data) {
    const el = document.getElementById('upload-result-banner');
    if (!el) return;
    el.style.display = 'flex';
    el.className     = `upload-result-banner ${data.hermes_running ? 'ok' : 'warn'}`;
    el.innerHTML     = `
        <span class="urb-icon">${data.hermes_running ? '✓' : '⚠'}</span>
        <div>
            <strong>Job #${data.id_esecuzione}</strong> — ${data.modello} (${data.tipo})
            <br><small>${data.message}</small>
        </div>
        <button class="btn btn-sm btn-ghost" onclick="openJobResults(${data.id_esecuzione})">
            Vedi risultati →
        </button>
    `;
}

// ── Lista Job (GET /api/jobs) ─────────────────────────────────────────────────
async function loadJobs() {
    try {
        const res  = await fetch('/api/jobs');
        const data = await res.json();
        renderJobsList(data.jobs || []);
    } catch (e) {
        console.error('Errore caricamento job:', e);
    }
}

function renderJobsList(jobs) {
    const container = document.getElementById('jobs-list-container');
    if (!container) return;

    if (jobs.length === 0) {
        container.innerHTML = '<div class="empty-state-sm">Nessun job eseguito ancora.</div>';
        return;
    }

    container.innerHTML = jobs.map(j => {
        const pct      = j.totale > 0 ? Math.round((j.completate / j.totale) * 100) : 0;
        const isDone   = j.totale > 0 && j.completate + j.errori >= j.totale;
        const hasErr   = j.errori > 0;
        
        let statusCls = 'pending';
        let statusLbl = '⟳ In corso…';
        
        if (j.stato === 'Fallito') {
            statusCls = 'error';
            statusLbl = '❌ Fallito';
        } else if (j.stato === 'Rimandato') {
            statusCls = 'partial';
            statusLbl = '⏸ Rimandato';
        } else if (isDone) {
            statusCls = hasErr ? 'partial' : 'done';
            statusLbl = hasErr ? `⚠ ${j.errori} err` : '✓ Completato';
        } else if (j.stato === 'In attesa') {
            statusCls = 'pending';
            statusLbl = '⏳ In attesa';
        }

        const provider = (typeof detectProvider === 'function')
            ? detectProvider(j.modello, j.tipo)
            : { label: j.tipo, color: '#6366f1', bg: 'rgba(99,102,241,0.1)', svg: '' };
        const logoHtml = (typeof getProviderLogoHtml === 'function')
            ? getProviderLogoHtml(provider, 28) : '';

        return `
        <div class="job-item">
            <div class="job-item-left">
                ${logoHtml}
                <div class="job-item-info">
                    <div class="job-item-name">Job #${j.id_esecuzione} <span class="job-model-name">${j.modello}</span></div>
                    <div class="job-item-meta">
                        <span class="job-status-badge ${statusCls}">${statusLbl}</span>
                        <span>${j.completate}/${j.totale} righe</span>
                        ${j.errori > 0 ? `<span style="color:#fb7185">${j.errori} errori</span>` : ''}
                    </div>
                </div>
            </div>
            <div class="job-item-actions">
                <div class="job-progress-bar" title="${pct}% completato">
                    <div class="job-progress-fill ${hasErr ? 'has-err' : ''}" style="width:${pct}%"></div>
                </div>
                <button class="model-action-btn" onclick="openJobResults(${j.id_esecuzione})">
                    Risultati
                </button>
                ${isDone ? `<a class="model-action-btn" href="/api/jobs/${j.id_esecuzione}/download">⬇ CSV</a>` : ''}
                <button class="model-action-btn" style="color: #fb7185; border-color: #fb7185; margin-left: auto;" onclick="deleteJob(${j.id_esecuzione})">
                    Elimina
                </button>
            </div>
        </div>`;
    }).join('');
}

window.deleteJob = async function(id) {
    if (!confirm(`Vuoi davvero eliminare definitivamente il Job #${id}?`)) return;
    try {
        const res = await fetch(`/api/jobs/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            if (typeof showToast === 'function') showToast('Job eliminato con successo', 'success');
            if (currentJobId === id) closeJobResults();
            loadJobs();
        } else {
            if (typeof showToast === 'function') showToast(`Errore: ${data.detail || data.message}`, 'error');
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast(`Errore rete: ${e.message}`, 'error');
    }
}

// ── Pannello risultati di un job ──────────────────────────────────────────────
let currentJobId = null;

async function openJobResults(id) {
    currentJobId = id;
    const panel = document.getElementById('job-results-panel');
    if (!panel) return;
    panel.style.display = 'block';
    document.getElementById('job-results-title').textContent = `Risultati — Job #${id}`;
    document.getElementById('job-results-download-btn').href = `/api/jobs/${id}/download`;
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    await fetchAndRenderResults(id);
}

async function fetchAndRenderResults(id) {
    const tbody = document.getElementById('job-results-tbody');
    const info  = document.getElementById('job-results-info');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-muted)">⟳ Caricamento…</td></tr>';

    try {
        const res  = await fetch(`/api/jobs/${id}/results?limit=200`);
        const data = await res.json();

        if (!res.ok || !data.results) {
            tbody.innerHTML = `<tr><td colspan="5" style="color:#fb7185">Errore: ${data.detail || 'Sconosciuto'}</td></tr>`;
            return;
        }

        if (info) info.textContent = `${data.results.length} / ${data.totale} risultati`;

        if (data.results.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-muted)">Nessun risultato ancora — il job potrebbe essere ancora in elaborazione</td></tr>';
            return;
        }

        tbody.innerHTML = data.results.map(r => {
            const isOk = r.stato === 'Completato';
            const out  = (r.output || '').substring(0, 120) + (r.output?.length > 120 ? '…' : '');
            return `
            <tr class="${isOk ? '' : 'row-error'}">
                <td class="mono">${r.id_riga_input}</td>
                <td class="mono">${r.id_file}</td>
                <td><span class="job-status-badge ${isOk ? 'done' : 'err'}">${r.stato}</span></td>
                <td class="mono">${r.tempo_esecuzione != null ? r.tempo_esecuzione + 's' : '—'}</td>
                <td class="result-output" title="${(r.output || '').replace(/"/g, '&quot;')}">${out}</td>
            </tr>`;
        }).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="5" style="color:#fb7185">Errore rete: ${e.message}</td></tr>`;
    }
}

function closeJobResults() {
    const panel = document.getElementById('job-results-panel');
    if (panel) panel.style.display = 'none';
    currentJobId = null;
}

// ── Auto-refresh job list ogni 5s quando pagina upload è attiva ───────────────
function startJobsPolling() {
    if (uploadState.jobsPolling) return;
    uploadState.jobsPolling = setInterval(loadJobs, 5000);
}
function stopJobsPolling() {
    if (uploadState.jobsPolling) {
        clearInterval(uploadState.jobsPolling);
        uploadState.jobsPolling = null;
    }
}
