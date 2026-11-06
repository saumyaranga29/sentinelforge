// SentinelForge Frontend Application Logic

const API = {
  health: () => fetch('/health').then(r => r.json()),
  ragStats: () => fetch('/api/rag/stats').then(r => r.json()),
  ragQuery: (query, top_k = 3) => fetch('/api/rag/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k })
  }).then(r => r.json()),
  ragIngestText: (filename, content) => fetch('/api/rag/ingest/text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, content })
  }).then(r => r.json()),
  ragDelete: (filename) => fetch(`/api/rag/content/${encodeURIComponent(filename)}`, {
    method: 'DELETE'
  }).then(r => r.json()),
  agentRun: (task, target_file = null) => fetch('/api/agent/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task, target_file })
  }).then(r => r.json()),
  agentActivePatch: () => fetch('/api/agent/patch/active').then(r => r.json()),
  agentApprovePatch: (patch_id, approved) => fetch('/api/agent/patch/approve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patch_id, approved })
  }).then(r => r.json()),
  mcpTools: () => fetch('/api/mcp/tools').then(r => r.json()),
  mcpInvoke: (tool_name, args) => fetch('/api/mcp/tools/invoke', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool_name, arguments: args })
  }).then(r => r.json()),
  mcpResource: (uri) => fetch(`/api/mcp/resources?uri=${encodeURIComponent(uri)}`).then(r => r.json()),
  auditLogs: (limit = 30) => fetch(`/api/audit/logs?limit=${limit}`).then(r => r.json())
};

// State
let currentTab = 'agent';
let activePatchData = null;
let mcpToolRegistry = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  refreshHeaderStatus();
  loadAgentTab();
  loadRagTab();
  loadMcpTab();
  loadAuditTab();

  // Periodic status poll
  setInterval(refreshHeaderStatus, 10000);
});

// --- Tab Switching ---
function initTabs() {
  const tabs = ['agent', 'rag', 'mcp', 'audit'];
  tabs.forEach(tab => {
    const btn = document.getElementById(`tab-btn-${tab}`);
    if (btn) {
      btn.addEventListener('click', () => {
        tabs.forEach(t => {
          document.getElementById(`tab-btn-${t}`).classList.remove('bg-slate-800', 'text-cyan-400', 'border-cyan-500');
          document.getElementById(`tab-btn-${t}`).classList.add('text-slate-400');
          document.getElementById(`tab-pane-${t}`).classList.add('hidden');
        });
        btn.classList.add('bg-slate-800', 'text-cyan-400', 'border-cyan-500');
        btn.classList.remove('text-slate-400');
        document.getElementById(`tab-pane-${tab}`).classList.remove('hidden');
        currentTab = tab;
      });
    }
  });
}

// --- Header Status ---
async function refreshHeaderStatus() {
  try {
    const health = await API.health();
    document.getElementById('header-app-version').textContent = `v${health.version}`;
    document.getElementById('header-mode').textContent = health.mode.toUpperCase();
    document.getElementById('header-provider').textContent = health.llm_provider.toUpperCase();
    document.getElementById('header-chunks').textContent = `${health.rag_chunks_indexed} Chunks Indexed`;

    const privacyBadge = document.getElementById('header-privacy');
    if (health.is_local_processing) {
      privacyBadge.textContent = '100% Local / Zero Cloud Leak';
      privacyBadge.className = 'text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 flex items-center gap-1.5';
    } else {
      privacyBadge.textContent = 'Cloud Free-Tier Mode';
      privacyBadge.className = 'text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-950/80 text-amber-400 border border-amber-800/60 flex items-center gap-1.5';
    }
  } catch (err) {
    console.error('Failed to fetch health status:', err);
  }
}

// ==========================================
// TAB 1: CODING AGENT & PATCH REVIEW
// ==========================================
function loadAgentTab() {
  const taskInput = document.getElementById('agent-task-input');
  const runBtn = document.getElementById('agent-run-btn');

  // Quick prompt buttons
  document.querySelectorAll('.quick-prompt-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      taskInput.value = btn.getAttribute('data-prompt');
    });
  });

  runBtn.addEventListener('click', async () => {
    const task = taskInput.value.trim();
    if (!task) return;

    setAgentLoading(true);
    resetAgentResults();

    try {
      // Simulate stages progression for visual polish
      animateAgentStages();
      const report = await API.agentRun(task);
      renderAgentReport(report);
      refreshHeaderStatus();
      loadAuditTab();
    } catch (err) {
      showToast('Agent execution error: ' + err.message, 'error');
    } finally {
      setAgentLoading(false);
    }
  });

  // Approve button
  document.getElementById('patch-approve-btn').addEventListener('click', async () => {
    if (!activePatchData || !activePatchData.patch_id) return;
    try {
      const res = await API.agentApprovePatch(activePatchData.patch_id, true);
      showToast('Patch approved and safely applied! Backup .bak created.', 'success');
      updatePatchStatusBadge('APPLIED');
      document.getElementById('patch-actions-container').classList.add('hidden');
      loadAuditTab();
    } catch (err) {
      showToast('Approval error: ' + err.message, 'error');
    }
  });

  // Reject button
  document.getElementById('patch-reject-btn').addEventListener('click', async () => {
    if (!activePatchData || !activePatchData.patch_id) return;
    try {
      const res = await API.agentApprovePatch(activePatchData.patch_id, false);
      showToast('Patch rejected. Repository untouched.', 'info');
      updatePatchStatusBadge('REJECTED');
      document.getElementById('patch-actions-container').classList.add('hidden');
      loadAuditTab();
    } catch (err) {
      showToast('Rejection error: ' + err.message, 'error');
    }
  });
}

function setAgentLoading(isLoading) {
  const btn = document.getElementById('agent-run-btn');
  const stagesCard = document.getElementById('agent-stages-progress');
  if (isLoading) {
    btn.disabled = true;
    btn.innerHTML = `<span class="inline-block animate-spin mr-2">⟳</span> Running 7-Stage Loop...`;
    stagesCard.classList.remove('hidden');
  } else {
    btn.disabled = false;
    btn.innerHTML = `<span>▶ Run 7-Stage Agent Loop</span>`;
  }
}

function animateAgentStages() {
  const stageElements = [
    'stage-1', 'stage-2', 'stage-3', 'stage-4', 'stage-5', 'stage-6', 'stage-7'
  ];
  stageElements.forEach((id, idx) => {
    setTimeout(() => {
      const el = document.getElementById(id);
      if (el) {
        el.className = 'flex items-center gap-2 text-xs font-medium text-emerald-400 transition-all';
        el.querySelector('.stage-dot').className = 'w-2 h-2 rounded-full bg-emerald-400 stage-dot';
      }
    }, idx * 400);
  });
}

function resetAgentResults() {
  document.getElementById('agent-results-container').classList.add('hidden');
  document.getElementById('patch-actions-container').classList.add('hidden');
}

function renderAgentReport(report) {
  document.getElementById('agent-results-container').classList.remove('hidden');
  document.getElementById('agent-plan-output').textContent = report.plan;

  // Render Citations
  const citationsList = document.getElementById('agent-citations-list');
  citationsList.innerHTML = '';
  if (report.citations && report.citations.length > 0) {
    report.citations.forEach(cit => {
      const card = document.createElement('div');
      card.className = 'p-3 rounded-lg bg-slate-900 border border-slate-700/60 text-xs text-slate-300';
      card.innerHTML = `
        <div class="flex items-center justify-between mb-1.5">
          <span class="font-mono font-semibold text-cyan-400">📄 ${cit.source_file || cit.citation_text}</span>
          <span class="px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 text-[10px]">
            Score: ${(cit.similarity_score * 100).toFixed(1)}%
          </span>
        </div>
        <p class="text-slate-400 italic">${(cit.encapsulated_text || '').slice(0, 140)}...</p>
      `;
      citationsList.appendChild(card);
    });
  } else {
    citationsList.innerHTML = '<span class="text-xs text-slate-500">No external documents cited for this task.</span>';
  }

  // Render Unified Diff
  renderDiff(report.unified_diff || 'No diff produced.');
  activePatchData = {
    patch_id: report.patch_id,
    target_file: report.target_file,
    status: report.status
  };

  // Render Sandbox Test Results
  const testCard = document.getElementById('agent-test-summary');
  const testLogs = document.getElementById('agent-test-logs');
  if (report.sandbox_executed) {
    const isPass = report.sandbox_success;
    testCard.innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-semibold ${isPass ? 'text-emerald-400' : 'text-rose-400'}">
          ${isPass ? '✔ Sandbox Execution Passed' : '✖ Sandbox Tests Failed'}
        </span>
        <span class="text-[11px] font-mono text-slate-400">Exit Code: ${report.test_summary?.exit_code ?? 0}</span>
      </div>
    `;
    testLogs.textContent = report.test_summary?.output || 'No output recorded.';
  }

  // Self-Critique & Risks
  document.getElementById('agent-critique-output').textContent = report.self_critique || 'Self-critique completed without alerts.';
  const riskList = document.getElementById('agent-risk-list');
  riskList.innerHTML = '';
  (report.risk_notes || []).forEach(risk => {
    const li = document.createElement('li');
    li.className = 'text-xs text-amber-300/90 flex items-start gap-1.5';
    li.innerHTML = `<span>⚠</span> <span>${risk}</span>`;
    riskList.appendChild(li);
  });

  // Show Approval Gate
  updatePatchStatusBadge(report.status);
  if (report.status === 'PENDING_APPROVAL') {
    document.getElementById('patch-actions-container').classList.remove('hidden');
  }
}

function updatePatchStatusBadge(status) {
  const badge = document.getElementById('patch-status-badge');
  badge.textContent = status;
  if (status === 'PENDING_APPROVAL') {
    badge.className = 'text-xs font-bold px-2.5 py-1 rounded bg-amber-950 text-amber-400 border border-amber-800';
  } else if (status === 'APPLIED') {
    badge.className = 'text-xs font-bold px-2.5 py-1 rounded bg-emerald-950 text-emerald-400 border border-emerald-800';
  } else {
    badge.className = 'text-xs font-bold px-2.5 py-1 rounded bg-rose-950 text-rose-400 border border-rose-800';
  }
}

function renderDiff(diffText) {
  const container = document.getElementById('agent-diff-viewer');
  container.innerHTML = '';

  const lines = diffText.split('\n');
  lines.forEach(line => {
    const row = document.createElement('div');
    row.className = 'px-3 py-0.5 text-xs font-mono leading-relaxed ';
    if (line.startsWith('---') || line.startsWith('+++') || line.startsWith('@@')) {
      row.className += 'diff-header text-blue-300';
    } else if (line.startsWith('+')) {
      row.className += 'diff-added';
    } else if (line.startsWith('-')) {
      row.className += 'diff-removed';
    } else {
      row.className += 'text-slate-400';
    }
    row.textContent = line || ' ';
    container.appendChild(row);
  });
}

// ==========================================
// TAB 2: LOCAL RAG & EVIDENCE Q&A
// ==========================================
function loadRagTab() {
  refreshRagStats();

  // Search input
  const queryInput = document.getElementById('rag-query-input');
  const searchBtn = document.getElementById('rag-search-btn');

  searchBtn.addEventListener('click', async () => {
    const q = queryInput.value.trim();
    if (!q) return;

    searchBtn.disabled = true;
    try {
      const data = await API.ragQuery(q, 4);
      renderRagSearchResults(data.results || []);
    } catch (err) {
      showToast('Search failure: ' + err.message, 'error');
    } finally {
      searchBtn.disabled = false;
    }
  });

  // Text ingestion form
  document.getElementById('rag-ingest-text-btn').addEventListener('click', async () => {
    const fn = document.getElementById('rag-filename-input').value.trim();
    const content = document.getElementById('rag-content-input').value.trim();
    if (!fn || !content) {
      showToast('Please provide both filename and content.', 'error');
      return;
    }
    try {
      await API.ragIngestText(fn, content);
      showToast(`Successfully indexed ${fn}`, 'success');
      document.getElementById('rag-filename-input').value = '';
      document.getElementById('rag-content-input').value = '';
      refreshRagStats();
      refreshHeaderStatus();
      loadAuditTab();
    } catch (err) {
      showToast('Ingest error: ' + err.message, 'error');
    }
  });

  // File upload form
  document.getElementById('rag-upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('rag-file-input');
    if (!fileInput.files || fileInput.files.length === 0) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
      const res = await fetch('/api/rag/ingest/upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      showToast(`Uploaded & indexed ${data.file || 'document'}`, 'success');
      fileInput.value = '';
      refreshRagStats();
      refreshHeaderStatus();
      loadAuditTab();
    } catch (err) {
      showToast('Upload error: ' + err.message, 'error');
    }
  });
}

async function refreshRagStats() {
  try {
    const stats = await API.ragStats();
    document.getElementById('rag-total-chunks').textContent = stats.total_chunks;
    document.getElementById('rag-total-files').textContent = (stats.indexed_files || []).length;
    document.getElementById('rag-engine-badge').textContent = stats.engine;

    const list = document.getElementById('rag-files-list');
    list.innerHTML = '';
    (stats.indexed_files || []).forEach(f => {
      const name = f.split(/[\\/]/).pop();
      const div = document.createElement('div');
      div.className = 'flex items-center justify-between p-2.5 rounded bg-slate-900 border border-slate-700/60 text-xs';
      div.innerHTML = `
        <span class="font-mono text-slate-300 truncate max-w-[200px]" title="${f}">📄 ${name}</span>
        <button class="delete-rag-file-btn text-rose-400 hover:text-rose-300 text-[11px] font-semibold" data-filename="${name}">
          Delete
        </button>
      `;
      list.appendChild(div);
    });

    document.querySelectorAll('.delete-rag-file-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const fn = btn.getAttribute('data-filename');
        if (confirm(`Delete indexed chunks for ${fn}?`)) {
          await API.ragDelete(fn);
          showToast(`Deleted ${fn}`, 'info');
          refreshRagStats();
          refreshHeaderStatus();
          loadAuditTab();
        }
      });
    });
  } catch (err) {
    console.error('Error loading RAG stats:', err);
  }
}

function renderRagSearchResults(results) {
  const container = document.getElementById('rag-results-container');
  container.innerHTML = '';

  if (results.length === 0) {
    container.innerHTML = '<div class="text-xs text-slate-500 py-6 text-center">No matching documents found.</div>';
    return;
  }

  results.forEach(res => {
    const card = document.createElement('div');
    card.className = 'p-4 rounded-xl bg-slate-900 border border-slate-700/70 space-y-2';

    const simScore = (res.similarity_score * 100).toFixed(1);
    const isSuspicious = res.injection_flagged;

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="font-mono font-bold text-xs text-cyan-400">📄 ${res.citation_text}</span>
        <div class="flex items-center gap-2">
          ${isSuspicious ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-400 border border-rose-800">⚠ INJECTION FLAGGED</span>' : '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">🛡 Boundary Sanitized</span>'}
          <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300">${simScore}% Match</span>
        </div>
      </div>
      <pre class="p-3 rounded-lg bg-slate-950 text-slate-300 font-mono text-xs whitespace-pre-wrap border border-slate-800 max-h-48 overflow-y-auto">${res.encapsulated_text}</pre>
    `;
    container.appendChild(card);
  });
}

// ==========================================
// TAB 3: MCP PROTOCOL EXPLORER
// ==========================================
async function loadMcpTab() {
  try {
    const data = await API.mcpTools();
    mcpToolRegistry = data.tools || [];

    const select = document.getElementById('mcp-tool-select');
    select.innerHTML = '';
    mcpToolRegistry.forEach(tool => {
      const opt = document.createElement('option');
      opt.value = tool.name;
      opt.textContent = `${tool.name} - ${tool.description}`;
      select.appendChild(opt);
    });

    select.addEventListener('change', () => {
      updateMcpToolInputTemplate(select.value);
    });

    if (mcpToolRegistry.length > 0) {
      updateMcpToolInputTemplate(mcpToolRegistry[0].name);
    }

    // Tool execution button
    document.getElementById('mcp-invoke-btn').addEventListener('click', async () => {
      const toolName = select.value;
      const rawArgs = document.getElementById('mcp-args-textarea').value.trim();
      let argsObj = {};
      try {
        if (rawArgs) argsObj = JSON.parse(rawArgs);
      } catch (e) {
        showToast('Invalid JSON arguments format', 'error');
        return;
      }

      const outputPre = document.getElementById('mcp-tool-output');
      outputPre.textContent = 'Invoking MCP tool via protocol...';

      try {
        const res = await API.mcpInvoke(toolName, argsObj);
        outputPre.textContent = JSON.stringify(res, null, 2);
        loadAuditTab();
      } catch (err) {
        outputPre.textContent = 'Error: ' + err.message;
      }
    });

    // Resource reader buttons
    document.getElementById('mcp-read-patch-res').addEventListener('click', async () => {
      const res = await API.mcpResource('repo://workspace/active_patch');
      document.getElementById('mcp-resource-output').textContent = JSON.stringify(res, null, 2);
    });

    document.getElementById('mcp-read-stats-res').addEventListener('click', async () => {
      const res = await API.mcpResource('rag://index/stats');
      document.getElementById('mcp-resource-output').textContent = JSON.stringify(res, null, 2);
    });
  } catch (err) {
    console.error('Failed to load MCP tools:', err);
  }
}

function updateMcpToolInputTemplate(toolName) {
  const textarea = document.getElementById('mcp-args-textarea');
  const defaults = {
    'retrieve_context': { query: 'division by zero calculator', top_k: 3 },
    'inspect_repository': { relative_path: '', max_depth: 3 },
    'execute_in_sandbox': { command: 'python', args: ['-m', 'unittest', 'discover', '-s', '.'], timeout_seconds: 10 },
    'propose_patch': {
      target_file: 'calculator.py',
      original_content: 'def divide(a, b):\n    return a / b\n',
      modified_content: 'def divide(a, b):\n    if b == 0:\n        raise ValueError("Cannot divide by zero")\n    return a / b\n',
      rationale: 'Prevent zero division'
    },
    'system_status': {},
    'ingest_content': { file_path: 'calculator.py' },
    'delete_indexed_content': { file_path: 'calculator.py' }
  };
  textarea.value = JSON.stringify(defaults[toolName] || {}, null, 2);
}

// ==========================================
// TAB 4: AUDIT TELEMETRY & SECURITY LOGS
// ==========================================
async function loadAuditTab() {
  try {
    const data = await API.auditLogs(30);
    const tbody = document.getElementById('audit-table-body');
    tbody.innerHTML = '';

    const events = data.events || [];
    if (events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="py-4 text-center text-slate-500 text-xs">No audit events logged yet.</td></tr>';
      return;
    }

    events.slice().reverse().forEach(ev => {
      const tr = document.createElement('tr');
      tr.className = 'border-b border-slate-800/80 hover:bg-slate-900/60 transition-colors text-xs font-mono';

      const timeStr = (ev.timestamp || '').split('T')[1]?.split('.')[0] || ev.timestamp;
      const isSecAlert = ev.severity === 'SECURITY_ALERT';
      const isWarning = ev.severity === 'WARNING';

      const sevBadge = isSecAlert
        ? '<span class="px-2 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-800 font-bold">ALERT</span>'
        : (isWarning ? '<span class="px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800">WARN</span>' : '<span class="px-2 py-0.5 rounded bg-slate-800 text-slate-400">INFO</span>');

      tr.innerHTML = `
        <td class="py-2.5 px-3 text-slate-400">${timeStr}</td>
        <td class="py-2.5 px-3 font-semibold ${isSecAlert ? 'text-rose-400' : 'text-cyan-400'}">${ev.event_type}</td>
        <td class="py-2.5 px-3">${sevBadge}</td>
        <td class="py-2.5 px-3 text-slate-300 truncate max-w-[200px]" title="${ev.command || ev.target_path || ''}">${ev.command || ev.target_path || '-'}</td>
        <td class="py-2.5 px-3 ${ev.success ? 'text-emerald-400' : 'text-rose-400'} font-bold">${ev.success ? 'SUCCESS' : 'FAILED'}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load audit logs:', err);
  }
}

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  const colors = {
    success: 'bg-emerald-950 border-emerald-800 text-emerald-300',
    error: 'bg-rose-950 border-rose-800 text-rose-300',
    info: 'bg-cyan-950 border-cyan-800 text-cyan-300'
  };
  toast.className = `p-3 rounded-lg shadow-lg border text-xs font-medium flex items-center justify-between gap-3 ${colors[type] || colors.info} transition-all duration-300`;
  toast.innerHTML = `<span>${message}</span><button class="text-slate-400 hover:text-white">&times;</button>`;

  toast.querySelector('button').addEventListener('click', () => toast.remove());
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}
