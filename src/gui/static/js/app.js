const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocket(`${wsProto}://${window.location.host}/ws/logs`);
const terminal = document.getElementById('terminal-output');
const terminalContainer = document.getElementById('terminal-container');
const MAX_TERMINAL_LINES = 2000;

ws.onmessage = function(event) {
    terminal.textContent += event.data + "\n";
    const lines = terminal.textContent.split("\n");
    if (lines.length > MAX_TERMINAL_LINES) {
        terminal.textContent = lines.slice(-MAX_TERMINAL_LINES).join("\n");
    }
    terminalContainer.scrollTop = terminalContainer.scrollHeight;
};

async function updateStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        const badge = document.getElementById('status-badge');
        const btnStart = document.getElementById('btn-start');
        const btnStop = document.getElementById('btn-stop');
        const btnAddPool = document.getElementById('btn-add-pool');

        if (data.is_running) {
            badge.textContent = "ONLINE 🟢";
            badge.className = "px-3 py-1 rounded text-sm font-bold bg-green-500/20 text-green-400 border border-green-500/30 shadow-[0_0_10px_rgba(34,197,94,0.2)]";
            btnStart.disabled = true; btnStart.className = "w-full bg-gray-700 text-gray-500 font-bold py-3 rounded cursor-not-allowed";
            btnStop.disabled = false; btnStop.className = "w-full bg-red-600 hover:bg-red-500 text-white font-bold py-3 rounded shadow-lg shadow-red-500/30 transition";
            btnAddPool.disabled = false; btnAddPool.className = "w-full bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold py-2 rounded transition shadow-lg shadow-emerald-500/20";
        } else {
            badge.textContent = "OFFLINE 🔴";
            badge.className = "px-3 py-1 rounded text-sm font-bold bg-red-500/20 text-red-400 border border-red-500/30 shadow-[0_0_10px_rgba(239,68,68,0.2)]";
            btnStart.disabled = false; btnStart.className = "w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded shadow-lg shadow-blue-500/30 transition";
            btnStop.disabled = true; btnStop.className = "w-full bg-gray-700 text-gray-500 font-bold py-3 rounded cursor-not-allowed";
            btnAddPool.disabled = true; btnAddPool.className = "w-full bg-gray-700 text-gray-500 text-sm font-bold py-2 rounded opacity-50 cursor-not-allowed";
        }

        const poolsContainer = document.getElementById('pools-container');
        if (data.is_running && Object.keys(data.pools).length > 0) {
            poolsContainer.innerHTML = '';
            for (const [name, stats] of Object.entries(data.pools)) {
                const isWorking = stats.in_coda > 0;
                const borderColor = isWorking ? 'border-blue-500' : 'border-gray-600';
                const dotColor = isWorking ? 'bg-blue-500 animate-pulse' : 'bg-gray-500';
                
                // NOTA: Aggiunta la classe 'group' e i bottoni di Edit/Delete
                const safeLabel = String(name).replace(/[&<>"'`]/g, '');
                poolsContainer.innerHTML += `
                    <div class="pool-card bg-gray-800 p-5 rounded-lg border ${borderColor} shadow-md transition-all relative">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                            <h4 style="font-weight:bold; color:#f3f4f6; display:flex; align-items:center; gap:8px;">
                                <span style="width:12px; height:12px; border-radius:50%; display:inline-block;" class="${dotColor}"></span>
                                ${safeLabel.toUpperCase()}
                            </h4>
                            <div style="display:flex; align-items:center; gap:12px;">
                                <span style="background:#111827; font-size:12px; padding:4px 8px; border-radius:4px; color:#9ca3af; border:1px solid #374151;">
                                    Max Workers: ${stats.max_workers}
                                </span>
                                <div class="pool-actions" style="display:flex; gap:8px;">
                                    <button onclick='editPool(${JSON.stringify(name)}, ${stats.max_workers})'
                                        style="color:#60a5fa; background:none; border:none; cursor:pointer; font-size:16px; padding:2px 6px; border-radius:4px;"
                                        title="Modifica Pool">✏️</button>
                                    <button onclick='deletePool(${JSON.stringify(name)})'
                                        style="color:#f87171; background:none; border:none; cursor:pointer; font-size:16px; padding:2px 6px; border-radius:4px;"
                                        title="Elimina Pool">🗑️</button>
                                </div>
                            </div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:flex-end;">
                            <div>
                                <p style="font-size:11px; color:#6b7280; text-transform:uppercase; letter-spacing:0.05em;">Task in Coda</p>
                                <p style="font-size:28px; font-weight:300; color:white;">${stats.in_coda}</p>
                            </div>
                            <div style="text-align:right; font-size:14px; color:${isWorking ? '#60a5fa' : '#6b7280'};">
                                ${stats.attivi}
                            </div>
                        </div>
                    </div>
                `;
            }
        } else if (!data.is_running) {
            poolsContainer.innerHTML = '<div class="bg-gray-800 p-4 rounded-lg border border-gray-700 flex items-center justify-center text-gray-500">Avvia Hermes per visualizzare i Pool...</div>';
        }
    } catch (e) { console.error(e); }
}

async function startHermes() {
    const workers = document.getElementById('workers').value;
    const interval = document.getElementById('interval').value;
    await fetch('/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workers: parseInt(workers), interval: parseInt(interval) })
    });
    updateStatus();
}

async function stopHermes() {
    await fetch('/api/stop', { method: 'POST' });
    updateStatus();
}

async function addPool() {
    const name = document.getElementById('new-pool-name').value;
    const workers = document.getElementById('new-pool-workers').value;
    if(!name || !workers) return;

    await fetch('/api/pools', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, workers: parseInt(workers) })
    });
    document.getElementById('new-pool-name').value = '';
    document.getElementById('new-pool-workers').value = '';
    updateStatus();
}

// --- NUOVE FUNZIONI DI MODIFICA / ELIMINAZIONE ---

async function editPool(oldName, currentWorkers) {
    const newName = prompt(`Rinomina il pool '${oldName}':`, oldName);
    if (!newName) return;
    
    const newWorkers = prompt(`Imposta i nuovi workers per '${newName}':`, currentWorkers);
    if (!newWorkers || isNaN(newWorkers)) return;

    const res = await fetch('/api/pools/' + oldName, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_name: newName, workers: parseInt(newWorkers) })
    });
    const result = await res.json();
    if(!result.success) alert("Errore: " + result.message);
    
    updateStatus();
}

async function deletePool(name) {
    if(!confirm(`Sei sicuro di voler eliminare il pool '${name}'? \nTutti i task attualmente in coda verranno annullati!`)) return;
    
    const res = await fetch('/api/pools/' + name, { method: 'DELETE' });
    const result = await res.json();
    if(!result.success) alert("Errore: " + result.message);
    
    updateStatus();
}

function downloadLogs() {
    const startEl = document.getElementById('log-start').value;
    const endEl   = document.getElementById('log-end').value;

    // Converti datetime-local (YYYY-MM-DDTHH:MM) in ISO seconds
    const toISO = v => v ? v + ':00' : null;

    let url = '/api/logs/download';
    const params = new URLSearchParams();
    if (toISO(startEl)) params.set('start', toISO(startEl));
    if (toISO(endEl))   params.set('end',   toISO(endEl));
    if ([...params].length) url += '?' + params.toString();

    // Apre il file come download senza lasciare la pagina
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function clearTerminal() {
    document.getElementById('terminal-output').textContent = '';
}

// Polling ogni secondo
setInterval(updateStatus, 1000);
updateStatus();