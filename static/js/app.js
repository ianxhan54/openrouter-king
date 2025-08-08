// OpenRouter Scanner Frontend Logic
// Handles config, scanning controls, keys rendering, logs, charts, and copy/export

let state = {
  keys: [],
  filteredKeys: [],
  running: false,
  charts: {
    balanceChart: null,
  },
};

// DOM refs
const el = {
  statusDot: () => document.querySelector('#statusIndicator .status-dot'),
  statusText: () => document.getElementById('statusText'),
  totalKeys: () => document.getElementById('totalKeys'),
  validKeys: () => document.getElementById('validKeys'),
  totalBalance: () => document.getElementById('totalBalance'),
  startBtn: () => document.getElementById('startBtn'),
  stopBtn: () => document.getElementById('stopBtn'),
  githubTokens: () => document.getElementById('githubTokens'),
  searchQueries: () => document.getElementById('searchQueries'),
  scanInterval: () => document.getElementById('scanInterval'),
  maxResults: () => document.getElementById('maxResults'),
  logsContainer: () => document.getElementById('logsContainer'),
  keysList: () => document.getElementById('keysList'),
  keySearch: () => document.getElementById('keySearch'),
  keyFilter: () => document.getElementById('keyFilter'),
  notification: () => document.getElementById('notification'),
  keyModal: () => document.getElementById('keyModal'),
  keyDetails: () => document.getElementById('keyDetails'),
  balanceChart: () => document.getElementById('balanceChart'),
};

// Helpers
function showNotification(text, type = 'info') {
  const n = el.notification();
  if (!n) return;
  n.textContent = text;
  n.className = `notification ${type}`;
  n.style.opacity = '1';
  setTimeout(() => (n.style.opacity = '0'), 2200);
}

function formatCurrency(n) {
  if (typeof n !== 'number') return '0.00';
  return n.toFixed(2);
}

function copyToClipboard(text) {
  if (!text) return;
  navigator.clipboard
    .writeText(text)
    .then(() => showNotification('已复制到剪贴板 ✅', 'success'))
    .catch(() => showNotification('复制失败 ❌', 'error'));
}

function updateStatusUI(running) {
  state.running = running;
  const dot = el.statusDot();
  const txt = el.statusText();
  const start = el.startBtn();
  const stop = el.stopBtn();
  if (running) {
    dot?.classList.add('running');
    txt.textContent = '运行中';
    start.disabled = true;
    stop.disabled = false;
  } else {
    dot?.classList.remove('running');
    txt.textContent = '未运行';
    start.disabled = false;
    stop.disabled = true;
  }
}

// Load & save config
async function loadConfig() {
  const res = await fetch('/api/config');
  const cfg = await res.json();
  el.githubTokens().value = (cfg.github_tokens || []).join('\n');
  el.searchQueries().value = (cfg.scan_queries || []).join('\n');
  el.scanInterval().value = cfg.scan_interval ?? 60;
  el.maxResults().value = cfg.max_results_per_query ?? 100;
}

async function saveConfig() {
  try {
    const payload = {
      github_tokens: el.githubTokens().value
        .split(/\n|,/) // allow newline or comma
        .map((s) => s.trim())
        .filter(Boolean),
      scan_queries: el.searchQueries().value
        .split(/\n/)
        .map((s) => s.trim())
        .filter(Boolean),
      scan_interval: Number(el.scanInterval().value || 60),
      max_results_per_query: Number(el.maxResults().value || 100),
    };

    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.status === 'success') {
      showNotification('配置已保存 ✅', 'success');
    } else {
      showNotification('保存失败 ❌', 'error');
    }
  } catch (e) {
    showNotification('保存出错 ❌', 'error');
  }
}

// Scan control
async function startScan() {
  const res = await fetch('/api/start', { method: 'POST' });
  const data = await res.json();
  if (data.status === 'started' || data.status === 'already_running') {
    updateStatusUI(true);
    showNotification('扫描已启动 🚀', 'success');
  } else {
    showNotification('启动失败 ❌', 'error');
  }
}

async function stopScan() {
  const res = await fetch('/api/stop', { method: 'POST' });
  const data = await res.json();
  if (data.status === 'stopped') {
    updateStatusUI(false);
    showNotification('扫描已停止 ⏹️', 'warning');
  }
}

// Keys
function computeStats(keys) {
  const total = keys.length;
  const valid = total; // DB仅保存有效Key
  let totalBalance = 0;
  keys.forEach((k) => {
    const b = Number(k.balance || 0);
    if (!Number.isNaN(b)) totalBalance += b;
  });
  return { total, valid, totalBalance };
}

function renderKeys(keys) {
  state.keys = keys;
  state.filteredKeys = [...keys];

  const list = el.keysList();
  if (!keys.length) {
    list.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">🔍</span>
        <p>暂无发现的Keys</p>
        <small>开始扫描以发现OpenRouter API Keys</small>
      </div>`;
  } else {
    list.innerHTML = '';
    keys.forEach((k, idx) => {
      const hasLimit = typeof k.limit === 'number' && k.limit > 0;
      const remaining = hasLimit ? Math.max(0, k.limit - (k.balance || 0)) : null;
      const item = document.createElement('div');
      item.className = 'key-item';
      item.dataset.key = k.key;
      item.dataset.balance = k.balance ?? 0;
      item.dataset.limit = k.limit ?? '';
      item.dataset.free = k.is_free_tier ? '1' : '0';

      item.innerHTML = `
        <div class="key-main">
          <div class="key-row">
            <span class="key-text" title="点击查看详情">${k.key_display}</span>
            <div class="key-actions">
              <button class="btn btn-xs" data-action="copy" title="复制该Key">复制</button>
              <a class="btn btn-xs btn-outline" href="${k.source_url}" target="_blank" title="来源">来源</a>
            </div>
          </div>
          <div class="key-meta">
            <span>使用量: $${formatCurrency(Number(k.balance || 0))}</span>
            <span>限额: ${hasLimit ? '$' + formatCurrency(Number(k.limit)) : '无限制'}</span>
            ${remaining !== null ? `<span>剩余: $${formatCurrency(remaining)}</span>` : ''}
            <span>${k.is_free_tier ? '免费层' : '付费'}</span>
            <span>${k.source_repo || ''}</span>
          </div>
        </div>
      `;

      item.querySelector('.key-text').addEventListener('click', () => openKeyModal(k));
      item.querySelector('[data-action="copy"]').addEventListener('click', (e) => {
        e.stopPropagation();
        copyToClipboard(k.key);
      });

      list.appendChild(item);
    });
  }

  const stats = computeStats(keys);
  el.totalKeys().textContent = String(stats.total);
  el.validKeys().textContent = String(stats.valid);
  el.totalBalance().textContent = formatCurrency(stats.totalBalance);
  updateBalanceChart(keys);
}

async function refreshKeys() {
  const res = await fetch('/api/keys');
  const keys = await res.json();
  renderKeys(keys);
}

function filterKeys() {
  const q = (el.keySearch().value || '').trim().toLowerCase();
  const f = el.keyFilter().value;

  const match = (k) => {
    if (q && !(k.key_display.toLowerCase().includes(q) || (k.source_repo || '').toLowerCase().includes(q))) {
      return false;
    }
    if (f === 'valid') return true; // all stored keys are valid
    if (f === 'balance') {
      const hasLimit = typeof k.limit === 'number' && k.limit > 0;
      const remaining = hasLimit ? k.limit - (k.balance || 0) : Infinity;
      return remaining > 0;
    }
    if (f === 'free') return !!k.is_free_tier;
    return true; // all
  };

  const filtered = state.keys.filter(match);
  renderKeys(filtered);
}

function exportKeys() {
  if (!state.keys.length) return showNotification('没有可导出的Key', 'warning');
  const rows = [
    ['key', 'usage', 'limit', 'is_free_tier', 'source_repo', 'source_url', 'found_at', 'last_checked'],
    ...state.keys.map((k) => [
      k.key,
      k.balance ?? '',
      k.limit ?? '',
      k.is_free_tier ? 'true' : 'false',
      k.source_repo ?? '',
      k.source_url ?? '',
      k.found_at ?? '',
      k.last_checked ?? '',
    ]),
  ];
  const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `openrouter_keys_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function copyValidKeys() {
  if (!state.keys.length) return showNotification('没有可复制的Key', 'warning');
  // 复制当前筛选条件下的“有效”Key，这里数据库中均为有效
  const f = el.keyFilter().value;
  const keys = (f === 'all' || f === 'valid') ? state.keys : state.keys.filter((k) => {
    if (f === 'balance') {
      const hasLimit = typeof k.limit === 'number' && k.limit > 0;
      const remaining = hasLimit ? k.limit - (k.balance || 0) : Infinity;
      return remaining > 0;
    }
    if (f === 'free') return !!k.is_free_tier;
    return true;
  });
  const text = keys.map((k) => k.key).join('\n');
  copyToClipboard(text);
}

// Modal
function openKeyModal(k) {
  const m = el.keyModal();
  const d = el.keyDetails();
  if (!m || !d) return;
  d.innerHTML = `
    <div class="kv"><span class="k">Key</span><span class="v">${k.key}</span></div>
    <div class="kv"><span class="k">显示</span><span class="v">${k.key_display}</span></div>
    <div class="kv"><span class="k">使用量</span><span class="v">$${formatCurrency(Number(k.balance || 0))}</span></div>
    <div class="kv"><span class="k">限额</span><span class="v">${typeof k.limit === 'number' && k.limit > 0 ? '$' + formatCurrency(Number(k.limit)) : '无限制'}</span></div>
    <div class="kv"><span class="k">免费层</span><span class="v">${k.is_free_tier ? '是' : '否'}</span></div>
    <div class="kv"><span class="k">来源</span><span class="v"><a href="${k.source_url}" target="_blank">${k.source_repo}</a></span></div>
    <div class="actions">
      <button class="btn btn-primary" id="copySingleKey">复制Key</button>
    </div>
  `;
  m.style.display = 'block';
  document.getElementById('copySingleKey')?.addEventListener('click', () => copyToClipboard(k.key));
}

function closeModal() {
  const m = el.keyModal();
  if (m) m.style.display = 'none';
}
window.closeModal = closeModal; // expose for HTML onclick

// Logs
function addLogItem(log) {
  const c = el.logsContainer();
  if (!c) return;
  const item = document.createElement('div');
  item.className = `log-item ${log.level || 'info'}`;
  const ts = log.time || log.timestamp || new Date().toISOString();
  item.innerHTML = `<span class="ts">${new Date(ts).toLocaleString()}</span><span class="lv">[${log.level}]</span><span class="msg">${log.message}</span>`;
  c.prepend(item);
  // limit to 200 logs
  while (c.childNodes.length > 200) c.removeChild(c.lastChild);
}

async function loadLogs() {
  try {
    const res = await fetch('/api/logs');
    const logs = await res.json();
    el.logsContainer().innerHTML = '';
    logs.reverse().forEach(addLogItem); // oldest first
  } catch (e) {
    // ignore
  }
}

// Charts
function updateBalanceChart(keys) {
  const ctx = el.balanceChart();
  if (!ctx) return;
  const free = keys.filter((k) => k.is_free_tier).length;
  const paid = keys.length - free;
  const totalUsage = keys.reduce((s, k) => s + Number(k.balance || 0), 0);

  const data = {
    labels: ['免费层', '付费'],
    datasets: [
      {
        label: '数量',
        data: [free, paid],
        backgroundColor: ['#36a2eb66', '#4bc0c066'],
        borderColor: ['#36a2eb', '#4bc0c0'],
        borderWidth: 1,
        yAxisID: 'y',
      },
      {
        label: '总使用量($)',
        data: [0, totalUsage],
        type: 'line',
        borderColor: '#ff6384',
        backgroundColor: '#ff638466',
        yAxisID: 'y1',
      },
    ],
  };

  if (state.charts.balanceChart) {
    state.charts.balanceChart.data = data;
    state.charts.balanceChart.update();
  } else {
    state.charts.balanceChart = new Chart(ctx, {
      type: 'bar',
      data,
      options: {
        responsive: true,
        scales: {
          y: { beginAtZero: true, position: 'left' },
          y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false } },
        },
      },
    });
  }
}

// Socket.IO
function initSocket() {
  const socket = io();
  socket.on('connect', () => {
    // connected
  });
  socket.on('log', (payload) => {
    addLogItem(payload);
  });
  socket.on('new_key', (payload) => {
    // Re-fetch keys to keep data consistent
    refreshKeys();
    showNotification(`发现有效Key: ${payload.key} ✅`, 'success');
  });
}

// Init
async function init() {
  try {
    const statusRes = await fetch('/api/status');
    const status = await statusRes.json();
    updateStatusUI(!!status.running);
  } catch (e) {
    // ignore
  }

  await loadConfig();
  await refreshKeys();
  await loadLogs();
  initSocket();

  // Bind filters
  el.keySearch().addEventListener('keyup', () => filterKeys());
  el.keyFilter().addEventListener('change', () => filterKeys());

  // Close modal on backdrop click
  el.keyModal().addEventListener('click', (e) => {
    if (e.target === el.keyModal()) closeModal();
  });
}

window.saveConfig = saveConfig;
window.startScan = startScan;
window.stopScan = stopScan;
window.refreshKeys = refreshKeys;
window.exportKeys = exportKeys;
window.copyValidKeys = copyValidKeys;

window.addEventListener('DOMContentLoaded', init);

