(function(){
  const $=s=>document.querySelector(s);
  const $$=s=>Array.from(document.querySelectorAll(s));
  const toast = (t)=>{ const n=$('#toast'); if(!n) return; n.textContent=t; n.style.opacity='1'; setTimeout(()=>n.style.opacity='0',2000); };

  let currentProvider='gemini';
  let statusFilter='all';
  let page=1, pageSize=20;
  let cache={ grouped:null, stats:null };
  let sortKey='last', sortDir='desc';
  let autoRefreshInterval = null;
  let autoRefreshEnabled = true;
  let refreshIntervalSeconds = 5; // 5秒快速刷新，确保实时更新

  async function fetchJSON(url){ 
    try {
      // 添加时间戳防止缓存
      const cacheBuster = new Date().getTime();
      const separator = url.includes('?') ? '&' : '?';
      const finalUrl = `${url}${separator}_t=${cacheBuster}`;
      
      const r=await fetch(finalUrl, {
        cache: 'no-cache',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      }); 
      if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`);
      const data = await r.json();
      console.log(`🌐 Fresh data from ${url}:`, data);
      return data;
    } catch(e) {
      console.error('Fetch error:', e);
      throw e;
    }
  }

  async function loadStats(){
    try {
      console.log('🔄 Loading stats at', new Date().toLocaleTimeString());
      const newStats = await fetchJSON('/api/stats');
      console.log('📊 Raw API response:', JSON.stringify(newStats, null, 2));

      // 验证API数据
      const apiTotal = (newStats.by_type?.openrouter || 0) + (newStats.by_type?.openai || 0) + (newStats.by_type?.anthropic || 0) + (newStats.by_type?.gemini || 0);
      console.log('📊 API data verification:', {
        by_type: newStats.by_type,
        calculated_total: apiTotal,
        total_valid: newStats.total_valid,
        total_429: newStats.total_429
      });

      // 强制清除旧缓存
      cache.stats = null;

      // 立即更新缓存
      cache.stats = newStats;

      // 强制更新所有数字
      forceUpdateAllNumbers(newStats);

      renderTrend();
      renderBadges();
      $('#dot')?.classList.add('on');

    } catch(e) {
      console.error('❌ Failed to load stats:', e);
      $('#dot')?.classList.remove('on');
    }
  }

  // 新增：强制更新所有数字的函数
  function forceUpdateAllNumbers(stats) {
    console.log('🔥 Force updating all numbers with:', stats);

    // 计算总数
    const by_type = stats.by_type || {};
    const total = (by_type.openrouter || 0) + (by_type.openai || 0) + (by_type.anthropic || 0) + (by_type.gemini || 0);
    const valid = stats.total_valid || 0;
    const rate429 = stats.total_429 || 0;
    const forbidden = stats.total_forbidden || 0;

    console.log('🔥 Calculated values:', { total, valid, rate429, forbidden });

    // 强制更新顶部数字
    updateElementValue('tTotal', total);
    updateElementValue('tValid', valid);
    updateElementValue('t429', rate429);
    // tForbidden元素不存在，跳过
    // updateElementValue('tForbidden', forbidden);

    // 强制更新provider badges (使用正确的ID)
    updateElementValue('b_or', by_type.openrouter || 0);
    updateElementValue('b_oa', by_type.openai || 0);
    updateElementValue('b_cl', by_type.anthropic || 0);
    updateElementValue('b_ge', by_type.gemini || 0);
  }

  // 新增：强制更新单个元素的函数
  function updateElementValue(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
      console.log(`🔥 Updating ${elementId}: ${element.textContent} → ${value}`);

      // 多种方式强制更新
      element.textContent = value;
      element.innerHTML = value;
      element.innerText = value;

      // 强制重绘
      element.style.opacity = '0.99';
      element.offsetHeight; // 触发重排
      element.style.opacity = '1';

      console.log(`🔥 ${elementId} updated result:`, element.textContent);
    } else {
      console.error(`❌ Element ${elementId} not found!`);
    }
  }
  
  async function loadScannerStatus(){
    try {
      const status = await fetchJSON('/api/scanner/status');
      updateScannerDisplay(status);
    } catch(e) {
      console.error('Failed to load scanner status:', e);
    }
  }
  
  function updateScannerDisplay(status){
    // Update header status
    const statusEl = $('#status');
    const dotEl = $('#dot');
    const infoEl = $('#scannerInfo');
    
    if(!status.github_tokens_configured){
      statusEl.textContent = '未配置';
      dotEl.classList.remove('on', 'scanning');
      dotEl.style.background = '#ff5c7a';
      infoEl.textContent = '请配置 GitHub Token';
    } else if(status.is_running){
      statusEl.textContent = '扫描中';
      dotEl.classList.add('scanning');
      dotEl.style.background = '#ffb74d';
      if(status.current_query){
        infoEl.textContent = `正在扫描: ${status.current_query.substring(0,30)}...`;
      }
    } else {
      statusEl.textContent = '运行中';
      dotEl.classList.remove('scanning');
      dotEl.classList.add('on');
      dotEl.style.background = '';
      
      if(status.last_scan_end){
        const lastTime = new Date(status.last_scan_end);
        const now = new Date();
        const diffMs = now - lastTime;
        const diffMins = Math.floor(diffMs / 60000);
        
        if(diffMins < 1){
          infoEl.textContent = '刚刚扫描完成';
        } else if(diffMins < 60){
          infoEl.textContent = `${diffMins}分钟前扫描`;
        } else {
          const diffHours = Math.floor(diffMins / 60);
          infoEl.textContent = `${diffHours}小时前扫描`;
        }
        
        // Next scan time
        const nextScan = new Date(lastTime.getTime() + status.scan_interval * 1000);
        if(nextScan > now){
          const nextDiffMs = nextScan - now;
          const nextMins = Math.floor(nextDiffMs / 60000);
          if(nextMins > 0){
            infoEl.textContent += ` · 下次扫描: ${nextMins}分钟后`;
          }
        }
      } else {
        infoEl.textContent = '等待首次扫描';
      }
    }
    
    // Update config modal status if open
    if($('#configModal').style.display === 'block'){
      $('#cfgScanStatus').textContent = status.is_running ? '扫描中...' : '空闲';
      $('#cfgLastScan').textContent = status.last_scan_end || '尚未扫描';
      $('#cfgKeysFound').textContent = status.keys_found_session || 0;
      
      // Show errors if any
      if(status.errors && status.errors.length > 0){
        const lastError = status.errors[status.errors.length - 1];
        $('#cfgScanStatus').textContent += ` (最近错误: ${lastError})`;
      }
    }
  }

  async function loadKeys(){
    try{
      console.log('🔄 Loading keys...'); // 调试日志
      const newGrouped = await fetchJSON('/api/keys_grouped');
      console.log('🔑 Keys loaded:', newGrouped); // 调试日志

      // 强制更新缓存
      cache.grouped = newGrouped;
    } catch {
      console.log('⚠️ Fallback to /api/keys'); // 调试日志
      try {
        const list=await fetchJSON('/api/keys');
        const g={openrouter:[],openai:[],anthropic:[],gemini:[]};
        (list||[]).forEach(k=>{
          const t=(k.type||'').toLowerCase();
          (g[t]||(g[t]=[])).push(k)
        });
        cache.grouped=g;
        console.log('🔑 Keys grouped from list:', g); // 调试日志
      } catch(e) {
        console.error('❌ Failed to load keys:', e);
        cache.grouped = {openrouter:[],openai:[],anthropic:[],gemini:[]};
      }
    }
    renderGrid();
  }

  // 保留renderTiles作为备用，但使用新的强制更新逻辑
  function renderTiles(){
    const s = cache.stats || {};
    console.log('🔄 renderTiles called, delegating to forceUpdateAllNumbers');
    forceUpdateAllNumbers(s);
  }

  function renderBadges(){
    const s = cache.stats || {};
    console.log('🔄 renderBadges called, delegating to forceUpdateAllNumbers');
    // forceUpdateAllNumbers已经处理了badges更新，这里不需要重复
  }

  function renderTrend(){ 
    const s=cache.stats||{}; 
    const labels=Object.keys(s.trend_total||{}).sort().slice(-60); // Last 60 minutes
    const pick=(o)=>labels.map(k=>o?.[k]||0);
    
    const data={ 
      series:[
        {name:'Total/min', data: pick(s.trend_total)}, 
        {name:'Valid (200)', data: pick(s.trend_valid)}, 
        {name:'429', data: pick(s.trend_429)}
      ], 
      xaxis:{ categories:labels } 
    };
    
    const el=document.querySelector('#trend'); 
    if(!el) return;
    
    if(window.__trend){ 
      window.__trend.updateOptions({series:data.series, xaxis:data.xaxis}); 
      return; 
    }
    
    window.__trend=new ApexCharts(el,{ 
      chart:{type:'area', height:280, toolbar:{show:false}}, 
      stroke:{curve:'smooth', width:2}, 
      dataLabels:{enabled:false}, 
      colors:['#4c7dff','#21c07a','#ffb74d'], 
      series:data.series, 
      xaxis:{
        ...data.xaxis,
        labels: { show: false }
      },
      yaxis: {
        labels: {
          style: { colors: '#9fb3c8' }
        }
      },
      grid: {
        borderColor: '#1e2630',
        strokeDashArray: 3
      },
      fill:{
        type:'gradient', 
        gradient:{shadeIntensity:.5,opacityFrom:.3,opacityTo:.05}
      } 
    });
    window.__trend.render();
  }

  const fmtCurrency=(n)=>{
    let x=Number(n);
    if(!isFinite(x)) x=0;

    // 负数表示无限额度，显示已使用金额
    if(x < 0) {
      const used = Math.abs(x);
      return `<span style="color:#10b981">$${used.toFixed(2)} <small>(unlimited)</small></span>`;
    }

    // 正数表示剩余额度
    return '$'+x.toFixed(2);
  };

  function fmtStatus(k){ 
    const st=(k.status||'').toString(); 
    if(/200|valid/i.test(st)) return {t:'200', c:'green'}; 
    if(/429/.test(st)) return {t:'429', c:'amber'}; 
    if(/403|forbidden/i.test(st)) return {t:'Forbidden', c:'red'}; 
    return {t: st||'-', c:''}; 
  }

  function maskKey(k, showFull = false){ 
    const v=k.key||''; 
    if(showFull) return v;
    return v.length>24? v.slice(0,12)+'...'+v.slice(-6): v; 
  }

  function nextTime(k){ 
    const ts=new Date(k.last_checked||k.found_at||Date.now()); 
    return new Date(ts.getTime()+60*60000).toLocaleString(); 
  }

  function getSortValue(k){
    if(sortKey==='key') return (k.key||'');
    if(sortKey==='status') return (k.status||'');
    if(sortKey==='last') return new Date(k.last_checked||0).getTime();
    if(sortKey==='next') return new Date(nextTime(k)).getTime();
    if(sortKey==='balance') return k.balance||0;
    return 0;
  }

  function renderGrid(){
    const g=cache.grouped||{};
    const arr=(g[currentProvider]||[]).slice();
    console.log(`🔄 Updating grid for ${currentProvider}, total keys:`, arr.length); // 调试日志

    const filtered=arr.filter(k=>{
      const st=(k.status||'').toString().toLowerCase();
      if(statusFilter==='valid') return st.includes('200')||st.includes('valid');
      if(statusFilter==='429') return st.includes('429');
      if(statusFilter==='forbidden') return st.includes('403')||st.includes('forbidden');
      if(statusFilter==='other') return !(st.includes('200')||st.includes('valid')||st.includes('429')||st.includes('403')||st.includes('forbidden'));
      return true;
    });

    // Apply sorting
    filtered.sort((a,b)=>{
      const va=getSortValue(a), vb=getSortValue(b);
      if(va==vb) return 0;
      return (va>vb?1:-1)*(sortDir==='asc'?1:-1);
    });

    const total=filtered.length;
    const pages=Math.max(1, Math.ceil(total/pageSize));
    if(page>pages) page=pages;
    const start=(page-1)*pageSize;
    const items=filtered.slice(start,start+pageSize);

    console.log(`📋 Grid updated: ${total} total, page ${page}/${pages}, showing ${items.length} items`); // 调试日志

    // 强制更新分页信息
    const pgInfoEl = $('#pgInfo');
    if(pgInfoEl) {
      pgInfoEl.textContent = `共 ${total} 条 • 第 ${page}/${pages} 页`;
    }

    const rows=items.map((k, idx)=>{
      const st=fmtStatus(k);
      const isOR = ((k.type||'').toLowerCase()==='openrouter') || (currentProvider==='openrouter');
      const bal = isOR? `<span class="balance">${fmtCurrency(k.balance||0)}</span>` : '';
      return `<tr data-key-index="${idx}">
        <td><span class="key clickable" title="点击复制完整密钥">${maskKey(k)}</span>${bal}</td>
        <td><span class="status ${st.c}">${st.t}</span></td>
        <td>${k.last_checked||'-'}</td>
        <td>${nextTime(k)}</td>
        <td>${isOR?fmtCurrency(k.balance||0):'-'}</td>
      </tr>`;
    }).join('');

    // 强制更新表格内容
    const gridBodyEl = $('#gridBody');
    if(gridBodyEl) {
      gridBodyEl.innerHTML = rows||`<tr><td colspan="5" style="color:#9fb3c8">暂无数据</td></tr>`;
    }
    window.__pageItems=items;
  }

  function bind(){
    // Providers
    $$('.providers .btn').forEach(btn=>btn.addEventListener('click',()=>{ 
      $$('.providers .btn').forEach(b=>b.classList.remove('active')); 
      btn.classList.add('active'); 
      currentProvider=btn.getAttribute('data-p'); 
      page=1; 
      renderGrid(); 
    }));
    
    // Status filter
    $('#statusSel')?.addEventListener('change', e=>{ 
      statusFilter=e.target.value; 
      page=1; 
      renderGrid(); 
    });
    
    $('#clearBtn')?.addEventListener('click', ()=>{
      statusFilter='all';
      $('#statusSel').value='all';
      page=1;
      renderGrid();
    });

    // Manual refresh button - 强制刷新
    $('#manualRefreshBtn')?.addEventListener('click', async ()=>{
      console.log('🔄 ===== MANUAL REFRESH START =====');
      try {
        // 完全清除缓存
        cache.stats = null;
        cache.grouped = null;

        // 直接获取最新数据并更新
        console.log('🔄 Getting fresh data...');
        const freshStats = await fetchJSON('/api/stats');
        console.log('📊 Manual refresh - fresh stats:', freshStats);

        // 立即强制更新所有数字
        forceUpdateAllNumbers(freshStats);

        await loadKeys();
        await loadScannerStatus();

        toast('数据已强制刷新');
        console.log('✅ ===== MANUAL REFRESH COMPLETE =====');
      } catch(e) {
        console.error('❌ Manual refresh failed:', e);
        toast('刷新失败');
      }
    });

    // Test update button - 使用新的强制更新逻辑
    $('#testUpdateBtn')?.addEventListener('click', ()=>{
      console.log('🧪 Testing new force update system...');

      // 设置测试数据
      const testStats = {
        by_type: { openrouter: 100, openai: 200, anthropic: 50, gemini: 300 },
        total_valid: 123,
        total_429: 45,
        total_forbidden: 67
      };

      console.log('🧪 Test data:', testStats);

      // 使用新的强制更新函数
      forceUpdateAllNumbers(testStats);

      // 0.5秒后测试直接DOM操作
      setTimeout(() => {
        console.log('🧪 Testing direct DOM manipulation...');
        updateElementValue('tTotal', 999);
        updateElementValue('tValid', 888);
        updateElementValue('t429', 777);
        updateElementValue('b_or', 111);
        updateElementValue('b_oa', 222);
        updateElementValue('b_cl', 333);
        updateElementValue('b_ge', 444);
      }, 500);

      toast('测试数据已设置');
    });

    // Pager
    $('#prevPg')?.addEventListener('click', ()=>{
      if(page>1){
        page--;
        renderGrid(); 
      }
    });
    
    $('#nextPg')?.addEventListener('click', ()=>{ 
      const g=cache.grouped||{}; 
      const arr=(g[currentProvider]||[]);
      const total=arr.length;
      const pages=Math.max(1, Math.ceil(total/pageSize));
      if(page<pages){
        page++; 
        renderGrid();
      }
    });
    
    // Copy all keys on page
    $('#copyPage')?.addEventListener('click', ()=>{ 
      const items=(window.__pageItems||[]).map(k=>k.key).filter(Boolean); 
      if(!items.length) return toast('当前页没有可复制的 Key'); 
      navigator.clipboard.writeText(items.join('\n'))
        .then(()=>toast('已复制当前页'))
        .catch(()=>toast('复制失败')); 
    });
    
    // Table header sorting
    const head=$('#grid thead');
    if(head){
      head.addEventListener('click', (e)=>{
        const th=e.target.closest('th[data-sort]'); 
        if(!th) return;
        const key=th.getAttribute('data-sort');
        
        if(sortKey===key){ 
          sortDir= (sortDir==='asc'?'desc':'asc'); 
        } else { 
          sortKey=key; 
          sortDir='desc'; 
        }
        
        // Update header visual
        $$('#grid thead th').forEach(t=>t.classList.remove('sorted-asc','sorted-desc'));
        th.classList.add(sortDir==='asc'?'sorted-asc':'sorted-desc');
        
        renderGrid();
      });
    }
    
    // Click on key to copy full key
    $('#gridBody')?.addEventListener('click', (e)=>{
      const keySpan = e.target.closest('.key.clickable');
      if(keySpan){
        const tr = keySpan.closest('tr');
        const idx = parseInt(tr.getAttribute('data-key-index'));
        const item = window.__pageItems[idx];
        if(item && item.key){
          navigator.clipboard.writeText(item.key)
            .then(()=>{
              toast('已复制完整密钥');
              // Flash effect
              keySpan.style.color = '#4c7dff';
              setTimeout(()=>keySpan.style.color = '', 300);
            })
            .catch(()=>toast('复制失败'));
        }
      }
    });
    
    // Hidden admin entry
    let adminClicks=0, adminTm=null; 
    $('#header .title h1')?.addEventListener('click',()=>{ 
      adminClicks++; 
      clearTimeout(adminTm); 
      adminTm=setTimeout(()=>{adminClicks=0},1000); 
      if(adminClicks>=10){ 
        adminClicks=0; 
        $('#adminModal').style.display='block'; 
      } 
    });
    
    // Admin login
    $('#loginBtn')?.addEventListener('click', async ()=>{ 
      const pwd=($('#adminPwd')?.value||'').trim(); 
      if(!pwd) return toast('请输入密码'); 
      
      try {
        const r=await fetch('/api/admin/login',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({password:pwd})
        }); 
        
        if(r.ok){ 
          toast('登录成功'); 
          $('#adminModal').style.display='none';
          $('#adminPwd').value='';
          window.dispatchEvent(new CustomEvent('adminLogged')); 
          openConfig();
        } else {
          toast('密码错误'); 
        }
      } catch(e) {
        toast('登录失败');
      }
    });
    
    // Config panel
    bindConfig();
    
    // Notice details
    $('#nDetail')?.addEventListener('click', ()=>{
      toast('为保护资源，部分功能受限');
    });
    
    // Export and copy all buttons
    $('#copyAllBtn')?.addEventListener('click', async ()=>{
      await showKeysModal(currentProvider);
    });
    
    $('#exportBtn')?.addEventListener('click', ()=>{
      exportKeys(currentProvider);
    });
  }
  
  // Export keys to text file
  function exportKeys(provider){
    let url = `/api/keys/export/${provider}`;
    let filename = `keys_${provider}`;
    
    // Add status filter if not 'all'
    if(statusFilter && statusFilter !== 'all'){
      // Map status filter to actual status codes
      const statusMap = {
        'valid': '200',
        '429': '429', 
        'forbidden': '403',
        'other': 'other'
      };
      const actualStatus = statusMap[statusFilter] || statusFilter;
      url += `/${actualStatus}`;
      filename += `_${statusFilter}`;
    }
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}_${Date.now()}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    const filterText = statusFilter === 'all' ? '所有' : statusFilter;
    toast(`开始下载 ${filterText} 状态的密钥...`);
  }
  
  // Show keys modal with full keys
  async function showKeysModal(provider){
    try {
      const response = await fetch(`/api/keys/copy/${provider}`);
      const data = await response.json();
      
      let content = '';
      for(const [type, keys] of Object.entries(data.keys)){
        if(keys.length > 0){
          content += `# ${type.toUpperCase()} KEYS\n`;
          content += '='.repeat(50) + '\n';
          for(const k of keys){
            const statusStr = k.status ? ` [${k.status}]` : '';
            content += `${k.key}${statusStr}\n`;
          }
          content += '\n';
        }
      }
      
      if(!content){
        content = '暂无密钥';
      }
      
      $('#keysContent').textContent = content;
      $('#keysModal').style.display = 'block';
      
      // Setup modal buttons
      $('#copyKeysBtn').onclick = ()=>{
        const keysOnly = [];
        for(const keys of Object.values(data.keys)){
          keysOnly.push(...keys.map(k => k.key));
        }
        navigator.clipboard.writeText(keysOnly.join('\n'))
          .then(()=>toast(`已复制 ${keysOnly.length} 个密钥`))
          .catch(()=>toast('复制失败'));
      };
      
      $('#downloadKeysBtn').onclick = ()=>{
        exportKeys(provider);
      };
      
    } catch(e){
      toast('加载密钥失败');
    }
  }
  
  // Filter keys in modal
  window.filterKeys = async function(filter){
    await showKeysModal(filter);
  }

  async function openConfig(){
    try{
      const cfg = await fetch('/api/config').then(r=>r.json());
      $('#cfgTokens').value = (cfg.github_tokens||[]).join('\n');
      $('#cfgQueries').value = (cfg.scan_queries||[]).join('\n');
      $('#cfgInterval').value = cfg.scan_interval||60;
      $('#cfgMax').value = cfg.max_results_per_query||100;
      $('#cfgRecent').checked = cfg.prefer_recent !== false;
      $('#cfgDays').value = cfg.recent_days||30;
      $('#configModal').style.display='block';
      
      // Load scanner status
      loadScannerStatus();
    }catch(e){ 
      toast('读取配置失败'); 
    }
  }

  async function saveConfig(){
    const body = {
      github_tokens: ($('#cfgTokens').value||'').split(/\n+/).map(s=>s.trim()).filter(Boolean),
      scan_queries: ($('#cfgQueries').value||'').split(/\n+/).map(s=>s.trim()).filter(Boolean),
      scan_interval: parseInt($('#cfgInterval').value||'60',10),
      max_results_per_query: parseInt($('#cfgMax').value||'100',10),
      prefer_recent: !!$('#cfgRecent').checked,
      recent_days: parseInt($('#cfgDays').value||'30',10),
    };
    
    try {
      const r = await fetch('/api/config',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(body)
      });
      
      if(r.ok){ 
        toast('已保存配置'); 
        $('#configModal').style.display='none'; 
      } else { 
        toast('保存失败（需管理员登录）'); 
      }
    } catch(e) {
      toast('保存失败');
    }
  }

  function bindConfig(){
    $('#cfgSave')?.addEventListener('click', saveConfig);
    $('#cfgCancel')?.addEventListener('click', ()=> $('#configModal').style.display='none');
    
    // Trigger scan button
    $('#triggerScan')?.addEventListener('click', async ()=>{
      try {
        const btn = $('#triggerScan');
        btn.disabled = true;
        btn.textContent = '触发中...';
        
        const r = await fetch('/api/scanner/trigger', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'}
        });
        
        if(r.ok){
          toast('扫描已触发，请稍候...');
          setTimeout(loadScannerStatus, 2000);
        } else {
          toast('触发失败（需要管理员权限）');
        }
      } catch(e) {
        toast('触发失败');
      } finally {
        const btn = $('#triggerScan');
        btn.disabled = false;
        btn.textContent = '立即扫描';
      }
    });
  }

  function startAutoRefresh(){
    if(autoRefreshInterval) clearInterval(autoRefreshInterval);
    
    if(autoRefreshEnabled){
      autoRefreshInterval = setInterval(async ()=>{
        const timestamp = new Date().toLocaleTimeString();
        console.log('🔄 ===== AUTO REFRESH START =====', timestamp);
        try {
          // 完全清除所有缓存
          cache.stats = null;
          cache.grouped = null;

          // 强制获取最新数据
          console.log('🔄 Step 1: Getting fresh stats...');
          const freshStats = await fetchJSON('/api/stats');
          console.log('📊 Fresh stats received:', freshStats);

          // 立即更新数字
          console.log('🔄 Step 2: Force updating numbers...');
          forceUpdateAllNumbers(freshStats);

          console.log('🔄 Step 3: Loading keys...');
          await loadKeys();

          console.log('🔄 Step 4: Loading scanner status...');
          await loadScannerStatus();

          updateAutoRefreshStatus();

          console.log('✅ ===== AUTO REFRESH COMPLETE =====', new Date().toLocaleTimeString());
        } catch(e) {
          console.error('❌ Auto refresh failed:', e);
        }
      }, refreshIntervalSeconds * 1000);

      updateAutoRefreshStatus();
      console.log(`✅ Auto refresh started (${refreshIntervalSeconds}s interval)`);
    }
  }
  
  function toggleAutoRefresh(){
    autoRefreshEnabled = !autoRefreshEnabled;
    if(autoRefreshEnabled){
      startAutoRefresh();
      toast(`自动刷新已开启 (${refreshIntervalSeconds}秒)`);
    } else {
      if(autoRefreshInterval) clearInterval(autoRefreshInterval);
      autoRefreshInterval = null;
      toast('自动刷新已关闭');
    }
    updateAutoRefreshStatus();
  }
  
  function updateAutoRefreshStatus(){
    const btn = document.getElementById('autoRefreshBtn');
    if(btn){
      btn.textContent = autoRefreshEnabled ? `🔄 自动刷新 (${refreshIntervalSeconds}s)` : '🔄 自动刷新 (关闭)';
      btn.style.backgroundColor = autoRefreshEnabled ? '#10b981' : '#6b7280';
    }
  }
  
  function bindAutoRefresh(){
    // 延迟一点执行，确保DOM完全加载
    setTimeout(() => {
      // 先尝试添加到header-buttons
      let container = document.querySelector('.header-buttons');
      
      // 如果找不到header-buttons，创建一个固定位置的容器
      if(!container) {
        container = document.createElement('div');
        container.style.cssText = 'position:fixed;top:10px;right:10px;z-index:1000;display:flex;gap:8px;';
        document.body.appendChild(container);
      }
      
      if(container && !document.getElementById('autoRefreshBtn')){
        // 创建自动刷新按钮
        const autoBtn = document.createElement('button');
        autoBtn.id = 'autoRefreshBtn';
        autoBtn.style.cssText = 'background:#10b981;color:white;padding:8px 12px;border-radius:6px;border:none;cursor:pointer;font-size:12px;box-shadow:0 2px 4px rgba(0,0,0,0.2);';
        autoBtn.onclick = toggleAutoRefresh;
        container.appendChild(autoBtn);
        
        // 创建间隔选择器
        const select = document.createElement('select');
        select.id = 'refreshIntervalSelect';
        select.style.cssText = 'padding:6px;border-radius:4px;border:1px solid #374151;background:#1f2937;color:white;font-size:12px;box-shadow:0 2px 4px rgba(0,0,0,0.2);';
        select.innerHTML = `
          <option value="3">3秒</option>
          <option value="5" selected>5秒</option>
          <option value="10">10秒</option>
          <option value="30">30秒</option>
          <option value="60">60秒</option>
        `;
        select.onchange = (e)=>{
          refreshIntervalSeconds = parseInt(e.target.value);
          if(autoRefreshEnabled){
            startAutoRefresh();
            toast('刷新间隔已更改为 ' + refreshIntervalSeconds + '秒');
          }
          updateAutoRefreshStatus();
        };
        container.appendChild(select);
        
        // 立即更新按钮状态
        updateAutoRefreshStatus();
      }
    }, 500); // 增加延迟时间
  }

  async function init(){ 
    bind(); 
    bindAutoRefresh();
    await loadStats(); 
    await loadKeys(); 
    await loadScannerStatus();
    
    // Start auto refresh
    startAutoRefresh();
  }
  
  document.addEventListener('DOMContentLoaded', init);
})();