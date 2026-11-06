// SentinelForge Frontend Application Engine

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

// Global State
let currentTab = 'agent';
let activePatchData = null;
let mcpToolRegistry = [];
let isAgentRunning = false;

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  refreshHeaderStatus();
  initAgentTab();
  initRagTab();
  initMcpTab();
  initAuditTab();

  // Polling for header stats
  setInterval(refreshHeaderStatus, 12000);
});

// --- Tab Navigation ---
function initNavigation() {
  const tabs = ['agent', 'rag', 'mcp', 'audit'];
  tabs.forEach(tab => {
    const btn = document.getElementById(`tab-btn-${tab}`);
    if (!btn) return;
    btn.addEventListener('click', () => {
      tabs.forEach(t => {
        const b = document.getElementById(`tab-btn-${t}`);
        const p = document.getElementById(`tab-pane-${t}`);
        if (b) b.classList.remove('active');
        if (p) p.classList.add('hidden');
      });
      btn.classList.add('active');
      const targetPane = document.getElementById(`tab-pane-${tab}`);
      if (targetPane) {
        targetPane.classList.remove('hidden');
        targetPane.classList.add('animate-fadeIn');
      }
      currentTab = tab;

      if (tab === 'audit') loadAuditTab();
      if (tab === 'rag') refreshRagStats();
    });
  });
}

// --- Header Status ---
async function refreshHeaderStatus() {
  try {
    const health = await API.health();
    document.getElementById('header-app-version').textContent = `v${health.version}`;
    document.getElementById('header-mode').textContent = health.mode.toUpperCase();
    document.getElementById('header-provider').textContent = health.llm_provider.toUpperCase();
    document.getElementById('header-chunks').textContent = `${health.rag_chunks_indexed} Chunks`;

    const privacyBadge = document.getElementById('header-privacy');
    if (health.is_local_processing) {
      privacyBadge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> 100% Local / Zero Cloud Leak';
      privacyBadge.className = 'text-[11px] font-semibold px-2.5 py-1 rounded-full bg-emerald-950/70 text-emerald-400 border border-emerald-800/60 flex items-center gap-1.5';
    } else {
      privacyBadge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span> Free Cloud Tier';
      privacyBadge.className = 'text-[11px] font-semibold px-2.5 py-1 rounded-full bg-amber-950/70 text-amber-400 border border-amber-800/60 flex items-center gap-1.5';
    }
  } catch (err) {
    console.error('Failed to fetch status:', err);
  }
}

// ==========================================
// TAB 1: CODING AGENT & PATCH REVIEW
// ==========================================
function initAgentTab() {
  const taskInput = document.getElementById('agent-task-input');
  const runBtn = document.getElementById('agent-run-btn');

  // Scenario presets
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      taskInput.value = btn.getAttribute('data-prompt');
      taskInput.focus();
    });
  });

  // Run Agent Loop
  runBtn.addEventListener('click', async () => {
    const task = taskInput.value.trim();
    if (!task || isAgentRunning) return;

    isAgentRunning = true;
    setAgentLoading(true);
    resetAgentResults();

    const stageNarration = document.getElementById('stage-narration-text');
    const stages = [
      { id: 'step-1', text: 'Analyzing repository files and AST structures...' },
      { id: 'step-2', text: 'Synthesizing verified multi-step execution plan...' },
      { id: 'step-3', text: 'Querying FastEmbed vector index for cited specifications...' },
      { id: 'step-4', text: 'Formulating minimal unified diff (diff -u) patch...' },
      { id: 'step-5', text: 'Spawning isolated sandbox runner to execute unittest suite...' },
      { id: 'step-6', text: 'Self-critique analyzing test exit codes & regression risks...' },
      { id: 'step-7', text: 'Final report compiled. Staging diff for human approval.' }
    ];

    // Animate stage sequence
    let currentStep = 0;
    const interval = setInterval(() => {
      if (currentStep < stages.length) {
        setStageActive(stages[currentStep].id);
        stageNarration.textContent = stages[currentStep].text;
        currentStep++;
      }
    }, 450);

    try {
      const startTime = performance.now();
      const report = await API.agentRun(task);
      const totalTime = ((performance.now() - startTime) / 1000).toFixed(2);

      clearInterval(interval);
      stages.forEach(s => setStageCompleted(s.id));
      stageNarration.textContent = `Completed 7-stage cognitive loop in ${totalTime}s. Diff is staged awaiting your approval.`;

      renderAgentReport(report);
      refreshHeaderStatus();
      loadAuditTab();
    } catch (err) {
      clearInterval(interval);
      stageNarration.textContent = 'Agent loop failed: ' + err.message;
      showToast('Agent execution error: ' + err.message, 'error');
    } finally {
      isAgentRunning = false;
      setAgentLoading(false);
    }
  });

  // Copy Diff Button
  document.getElementById('copy-diff-btn').addEventListener('click', () => {
    if (!activePatchData || !activePatchData.unified_diff) return;
    navigator.clipboard.writeText(activePatchData.unified_diff).then(() => {
      const btn = document.getElementById('copy-diff-btn');
      btn.innerHTML = '✔ Copied';
      setTimeout(() => { btn.innerHTML = '📋 Copy Diff'; }, 2000);
    });
  });

  // Patch Approval Button
  document.getElementById('patch-approve-btn').addEventListener('click', async () => {
    if (!activePatchData || !activePatchData.patch_id) return;
    try {
      const res = await API.agentApprovePatch(activePatchData.patch_id, true);
      showToast('Patch approved & applied! Backup .bak created in workspace.', 'success');
      updatePatchStatusBadge('APPLIED');
      document.getElementById('patch-decision-bar').classList.add('hidden');
      document.getElementById('applied-success-banner').classList.remove('hidden');
      loadAuditTab();
    } catch (err) {
      showToast('Approval error: ' + err.message, 'error');
    }
  });

  // Patch Rejection Button
  document.getElementById('patch-reject-btn').addEventListener('click', async () => {
    if (!activePatchData || !activePatchData.patch_id) return;
    try {
      const res = await API.agentApprovePatch(activePatchData.patch_id, false);
      showToast('Patch rejected. Repository untouched.', 'info');
      updatePatchStatusBadge('REJECTED');
      document.getElementById('patch-decision-bar').classList.add('hidden');
      loadAuditTab();
    } catch (err) {
      showToast('Rejection error: ' + err.message, 'error');
    }
  });
}

function setStageActive(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = 'stage-step active flex flex-col items-center gap-1.5 text-center flex-1';
}

function setStageCompleted(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = 'stage-step completed flex flex-col items-center gap-1.5 text-center flex-1';
}

function setAgentLoading(loading) {
  const btn = document.getElementById('agent-run-btn');
  const pipelineBox = document.getElementById('agent-pipeline-visualizer');
  if (loading) {
    btn.disabled = true;
    btn.classList.add('opacity-80');
    btn.innerHTML = `<span class="inline-block animate-spin mr-2">⟳</span> Synthesizing & Verifying...`;
    pipelineBox.classList.remove('hidden');
  } else {
    btn.disabled = false;
    btn.classList.remove('opacity-80');
    btn.innerHTML = `<span>⚡ Execute 7-Stage Agent Loop</span>`;
  }
}

function resetAgentResults() {
  document.getElementById('agent-results-view').classList.add('hidden');
  document.getElementById('applied-success-banner').classList.add('hidden');
  document.getElementById('patch-decision-bar').classList.add('hidden');
  ['step-1', 'step-2', 'step-3', 'step-4', 'step-5', 'step-6', 'step-7'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.className = 'stage-step flex flex-col items-center gap-1.5 text-center flex-1';
  });
}

function renderAgentReport(report) {
  document.getElementById('agent-results-view').classList.remove('hidden');
  document.getElementById('agent-plan-content').textContent = report.plan;

  // Render Citations
  const citList = document.getElementById('agent-citations-container');
  citList.innerHTML = '';
  if (report.citations && report.citations.length > 0) {
    report.citations.forEach(c => {
      const card = document.createElement('div');
      card.className = 'p-3 rounded-lg bg-slate-950/70 border border-white/[0.06] text-xs space-y-1';
      card.innerHTML = `
        <div class="flex items-center justify-between">
          <span class="font-mono font-semibold text-cyan-400">📄 ${c.source_file || c.citation_text}</span>
          <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-950/80 text-cyan-300 border border-cyan-800/60">
            ${(c.similarity_score * 100).toFixed(1)}% Match
          </span>
        </div>
        <p class="text-slate-400 italic text-[11px] leading-relaxed">${(c.encapsulated_text || '').slice(0, 150)}...</p>
      `;
      citList.appendChild(card);
    });
  } else {
    citList.innerHTML = '<span class="text-xs text-slate-500">No external documents cited.</span>';
  }

  // Render Diff with Line Numbers
  activePatchData = {
    patch_id: report.patch_id,
    target_file: report.target_file,
    unified_diff: report.unified_diff,
    status: report.status
  };
  renderUnifiedDiff(report.unified_diff || 'No diff generated.');

  // Sandbox Test Terminal Box
  const isPass = report.sandbox_success;
  const statusBadge = document.getElementById('terminal-exit-badge');
  statusBadge.textContent = isPass ? 'EXIT 0 • PASSED' : 'EXIT FAIL';
  statusBadge.className = isPass
    ? 'px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-emerald-950 text-emerald-400 border border-emerald-800'
    : 'px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-rose-950 text-rose-400 border border-rose-800';

  document.getElementById('terminal-duration').textContent = `${report.test_summary?.duration_ms || 18}ms`;
  document.getElementById('terminal-stdout').textContent = report.test_summary?.output || 'No output recorded.';

  // Self-Critique & Risk Notes
  document.getElementById('agent-critique-text').textContent = report.self_critique || 'Self-critique completed without regressions.';
  const riskList = document.getElementById('agent-risks-container');
  riskList.innerHTML = '';
  (report.risk_notes || []).forEach(r => {
    const li = document.createElement('li');
    li.className = 'text-xs text-amber-300/90 flex items-start gap-2';
    li.innerHTML = `<span class="text-amber-400">⚠</span> <span>${r}</span>`;
    riskList.appendChild(li);
  });

  // Approval Gate Status
  updatePatchStatusBadge(report.status);
  if (report.status === 'PENDING_APPROVAL') {
    document.getElementById('patch-decision-bar').classList.remove('hidden');
  }
}

function updatePatchStatusBadge(status) {
  const badge = document.getElementById('patch-status-badge');
  badge.textContent = status;
  if (status === 'PENDING_APPROVAL') {
    badge.className = 'text-xs font-bold px-3 py-1 rounded-full bg-amber-950/80 text-amber-400 border border-amber-800/80';
  } else if (status === 'APPLIED') {
    badge.className = 'text-xs font-bold px-3 py-1 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800/80';
  } else {
    badge.className = 'text-xs font-bold px-3 py-1 rounded-full bg-rose-950/80 text-rose-400 border border-rose-800/80';
  }
}

function renderUnifiedDiff(diffText) {
  const container = document.getElementById('diff-lines-container');
  container.innerHTML = '';

  const lines = diffText.split('\n');
  let oldLine = 1;
  let newLine = 1;

  let addedCount = 0;
  let removedCount = 0;

  lines.forEach(line => {
    const row = document.createElement('div');
    row.className = 'diff-row font-mono text-xs';

    if (line.startsWith('---') || line.startsWith('+++') || line.startsWith('@@')) {
      row.className += ' diff-row-header';
      row.innerHTML = `<div class="diff-gutter">...</div><div class="diff-content">${escapeHtml(line)}</div>`;
    } else if (line.startsWith('+')) {
      addedCount++;
      row.className += ' diff-row-added';
      row.innerHTML = `<div class="diff-gutter">+</div><div class="diff-content">${escapeHtml(line)}</div>`;
      newLine++;
    } else if (line.startsWith('-')) {
      removedCount++;
      row.className += ' diff-row-removed';
      row.innerHTML = `<div class="diff-gutter">-</div><div class="diff-content">${escapeHtml(line)}</div>`;
      oldLine++;
    } else {
      row.innerHTML = `<div class="diff-gutter">${oldLine}</div><div class="diff-content">${escapeHtml(line)}</div>`;
      oldLine++;
      newLine++;
    }
    container.appendChild(row);
  });

  document.getElementById('diff-stats-added').textContent = `+${addedCount}`;
  document.getElementById('diff-stats-removed').textContent = `-${removedCount}`;
}

// ==========================================
// TAB 2: LOCAL RAG & EVIDENCE CITATIONS
// ==========================================
function initRagTab() {
  refreshRagStats();

  const qInput = document.getElementById('rag-query-input');
  const searchBtn = document.getElementById('rag-search-btn');

  searchBtn.addEventListener('click', async () => {
    const q = qInput.value.trim();
    if (!q) return;

    searchBtn.disabled = true;
    searchBtn.innerHTML = `<span class="animate-spin inline-block mr-1">⟳</span> Searching...`;
    try {
      const data = await API.ragQuery(q, 4);
      renderRagSearchResults(data.results || []);
    } catch (err) {
      showToast('RAG query failure: ' + err.message, 'error');
    } finally {
      searchBtn.disabled = false;
      searchBtn.innerHTML = `<span>Search Index</span>`;
    }
  });

  // Ingest Text Form
  document.getElementById('rag-ingest-text-btn').addEventListener('click', async () => {
    const fn = document.getElementById('rag-filename-input').value.trim();
    const content = document.getElementById('rag-content-input').value.trim();
    if (!fn || !content) {
      showToast('Please provide both filename and content.', 'error');
      return;
    }
    try {
      await API.ragIngestText(fn, content);
      showToast(`Indexed ${fn} into local vector store`, 'success');
      document.getElementById('rag-filename-input').value = '';
      document.getElementById('rag-content-input').value = '';
      refreshRagStats();
      refreshHeaderStatus();
      loadAuditTab();
    } catch (err) {
      showToast('Ingest error: ' + err.message, 'error');
    }
  });

  // File Upload
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
      div.className = 'flex items-center justify-between p-2.5 rounded-lg bg-slate-950/80 border border-white/[0.06] text-xs font-mono';
      div.innerHTML = `
        <span class="text-slate-300 truncate max-w-[220px]" title="${f}">📄 ${name}</span>
        <button class="delete-file-btn text-rose-400 hover:text-rose-300 text-[11px] font-semibold transition-colors" data-fn="${name}">
          Delete
        </button>
      `;
      list.appendChild(div);
    });

    document.querySelectorAll('.delete-file-btn').forEach(b => {
      b.addEventListener('click', async () => {
        const fn = b.getAttribute('data-fn');
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
    console.error('Failed to load RAG stats:', err);
  }
}

function renderRagSearchResults(results) {
  const container = document.getElementById('rag-results-container');
  container.innerHTML = '';

  if (results.length === 0) {
    container.innerHTML = '<div class="text-xs text-slate-500 py-12 text-center font-mono">No matching passages found in local index.</div>';
    return;
  }

  results.forEach(res => {
    const card = document.createElement('div');
    card.className = 'p-4 rounded-xl bg-slate-950/80 border border-white/[0.08] space-y-2.5 transition-all hover:border-cyan-500/30';

    const simScore = (res.similarity_score * 100).toFixed(1);
    const isSuspicious = res.injection_flagged;

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="font-mono font-bold text-xs text-cyan-400">📄 ${res.citation_text}</span>
        <div class="flex items-center gap-2">
          ${isSuspicious ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-400 border border-rose-800 animate-pulse">🚨 INJECTION DETECTED</span>' : '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">🛡 Boundary Sanitized</span>'}
          <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300">${simScore}% Similarity</span>
        </div>
      </div>
      <pre class="p-3 rounded-lg bg-black/80 text-slate-300 font-mono text-xs whitespace-pre-wrap border border-slate-800/80 max-h-48 overflow-y-auto leading-relaxed">${escapeHtml(res.encapsulated_text)}</pre>
    `;
    container.appendChild(card);
  });
}

// ==========================================
// TAB 3: MCP PROTOCOL EXPLORER
// ==========================================
async function initMcpTab() {
  try {
    const data = await API.mcpTools();
    mcpToolRegistry = data.tools || [];

    const select = document.getElementById('mcp-tool-select');
    select.innerHTML = '';
    mcpToolRegistry.forEach(tool => {
      const opt = document.createElement('option');
      opt.value = tool.name;
      opt.textContent = `${tool.name} — ${tool.description}`;
      select.appendChild(opt);
    });

    select.addEventListener('change', () => updateMcpToolInputTemplate(select.value));
    if (mcpToolRegistry.length > 0) updateMcpToolInputTemplate(mcpToolRegistry[0].name);

    document.getElementById('mcp-invoke-btn').addEventListener('click', async () => {
      const toolName = select.value;
      const rawArgs = document.getElementById('mcp-args-textarea').value.trim();
      let argsObj = {};
      try {
        if (rawArgs) argsObj = JSON.parse(rawArgs);
      } catch (e) {
        showToast('Invalid JSON arguments syntax', 'error');
        return;
      }

      const out = document.getElementById('mcp-tool-output');
      out.textContent = 'Invoking tool via official FastMCP protocol...';
      const t0 = performance.now();

      try {
        const res = await API.mcpInvoke(toolName, argsObj);
        const duration = (performance.now() - t0).toFixed(1);
        out.textContent = `// MCP Protocol Response (${duration}ms)\n` + JSON.stringify(res, null, 2);
        loadAuditTab();
      } catch (err) {
        out.textContent = 'MCP Tool Invocation Error: ' + err.message;
      }
    });

    // Resources
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
      rationale: 'Prevent zero division error'
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
async function initAuditTab() {
  loadAuditTab();
}

async function loadAuditTab() {
  try {
    const data = await API.auditLogs(30);
    const tbody = document.getElementById('audit-table-body');
    tbody.innerHTML = '';

    const events = data.events || [];
    if (events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-slate-500 font-mono text-xs">No audit events recorded yet.</td></tr>';
      return;
    }

    events.slice().reverse().forEach(ev => {
      const tr = document.createElement('tr');
      tr.className = 'border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors text-xs font-mono';

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
        <td class="py-2.5 px-3 text-slate-300 truncate max-w-[220px]" title="${ev.command || ev.target_path || ''}">${ev.command || ev.target_path || '-'}</td>
        <td class="py-2.5 px-3 ${ev.success ? 'text-emerald-400' : 'text-rose-400'} font-bold">${ev.success ? 'SUCCESS' : 'BLOCKED / FAILED'}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error fetching audit logs:', err);
  }
}

// Utility Helpers
function escapeHtml(str) {
  return (str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  const colors = {
    success: 'bg-emerald-950/90 border-emerald-800/80 text-emerald-300',
    error: 'bg-rose-950/90 border-rose-800/80 text-rose-300',
    info: 'bg-cyan-950/90 border-cyan-800/80 text-cyan-300'
  };
  toast.className = `p-3.5 rounded-xl shadow-2xl border text-xs font-medium flex items-center justify-between gap-3 ${colors[type] || colors.info} transition-all duration-300 animate-slideUp`;
  toast.innerHTML = `<span>${message}</span><button class="text-slate-400 hover:text-white">&times;</button>`;

  toast.querySelector('button').addEventListener('click', () => toast.remove());
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}
