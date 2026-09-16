(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  if (!byId('growthTools') || !byId('collectionCenter')) return;
  const text = (id, value) => { byId(id).textContent = String(value ?? ''); };
  const lines = value => value.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const busy = new Set();
  const make = (tag, value, cls) => {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = String(value);
    if (cls) node.className = cls;
    return node;
  };
  async function request(path, body, options = {}) {
    const init = { credentials: 'same-origin', ...options };
    if (body !== undefined) {
      init.method = 'POST';
      if (body instanceof FormData) init.body = body;
      else { init.headers = { 'Content-Type': 'application/json' }; init.body = JSON.stringify(body); }
    }
    let response;
    try { response = await fetch(path, init); }
    catch (_) { throw new Error('软件连接断开。请重新打开 ChatFLOW，使用新打开的窗口，再刷新草稿或产品列表确认结果。不要反复点击导入，以免重复操作。'); }
    if (response.status === 401 || response.redirected) throw new Error('登录已过期，请重新登录后再操作。');
    if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('服务器没有返回有效结果，请检查软件是否仍在运行。');
    const data = await response.json();
    if (!response.ok || data.error || data.success === false) throw new Error(data.error || data.message || `操作失败（${response.status}）`);
    return data;
  }
  function handle(id, callback, errorId) {
    byId(id).addEventListener('click', async () => {
      if (busy.has(id)) return;
      busy.add(id); byId(id).disabled = true;
      try { await callback(); }
      catch (error) { if (errorId) text(errorId, error.message); else log(error.message, true); }
      finally { busy.delete(id); byId(id).disabled = false; updateDraftButtons(); }
    });
  }
  function refreshAdminPanels(names) {
    names.forEach(name => {
      if (typeof window[name] !== 'function') return;
      try {
        Promise.resolve(window[name]()).catch(() => log('资料已保存，但列表刷新没有完成。请稍后重新打开对应管理页。', true));
      } catch (_) { log('资料已保存，但列表刷新没有完成。请稍后重新打开对应管理页。', true); }
    });
  }
  function parseRows(id, columns) {
    return lines(byId(id).value).map((line, index) => {
      const parts = line.split('|').map(s => s.trim());
      if (parts.length < columns || parts.length > columns || parts.slice(0, 2).some(s => !s)) {
        throw new Error(`第 ${index + 1} 行格式不对，请按照框上方的格式填写。`);
      }
      return parts;
    });
  }
  let growthLoaded = false;
  byId('growthSave').disabled = true;
  request('/api/growth/settings').then(data => {
    const s = data.settings || data;
    byId('growthKeywordsEnabled').checked = !!s.hidden_keywords_enabled;
    byId('growthKeywordLines').value = (s.hidden_keywords || []).join('\n');
    byId('growthLinksEnabled').checked = !!s.hidden_links_enabled;
    byId('growthLinkLines').value = (s.hidden_links || []).map(x => [x.name, x.url, x.rel || 'nofollow'].join(' | ')).join('\n');
    byId('growthInternalEnabled').checked = !!s.internal_links_enabled;
    byId('growthInternalLines').value = (s.internal_links || []).map(x => [x.keyword, x.url].join(' | ')).join('\n');
    growthLoaded = true; byId('growthSave').disabled = false;
  }).catch(e => text('growthMessage', `未能读取已有设置：${e.message} 请刷新后重试。`));
  handle('growthSave', async () => {
    if (!growthLoaded) throw new Error('已有设置尚未读取成功，请刷新后重试。');
    const hiddenLinks = parseRows('growthLinkLines', 3).map(([name, url, rel]) => {
      rel = rel.toLowerCase();
      if (!['follow', 'nofollow', 'sponsored'].includes(rel)) throw new Error('链接第三项只能填 follow、nofollow 或 sponsored。');
      return { name, url, rel };
    });
    const settings = {
      hidden_keywords_enabled: byId('growthKeywordsEnabled').checked,
      hidden_keywords: lines(byId('growthKeywordLines').value),
      hidden_links_enabled: byId('growthLinksEnabled').checked,
      hidden_links: hiddenLinks,
      internal_links_enabled: byId('growthInternalEnabled').checked,
      internal_links: parseRows('growthInternalLines', 2).map(([keyword, url]) => ({ keyword, url })),
      max_links_per_page: 3
    };
    await request('/api/growth/settings', settings);
    text('growthMessage', '已保存。重新生成并发布网站后生效。');
  }, 'growthMessage');
  function landingPayload() {
    const topics = [...new Set(lines(byId('growthTopics').value))];
    if (!topics.length) throw new Error('请先填写至少一个页面主题。');
    const raw = byId('growthProductIds').value.trim();
    const productIds = raw ? raw.split(/[,，]/).map(s => s.trim()) : [];
    if (productIds.some(s => !/^[1-9]\d*$/.test(s))) throw new Error('产品编号请填正整数，用逗号隔开。');
    return { topics, product_ids: [...new Set(productIds.map(Number))] };
  }
  handle('growthLandingPreview', async () => {
    const payload = landingPayload();
    text('growthLandingResult', '正在准备页面草稿…');
    const data = await request('/api/growth/landing-preview', payload);
    const target = byId('growthLandingResult'); target.replaceChildren();
    if (data.notice) target.append(make('p', data.notice, 'text-muted'));
    (data.items || []).forEach(item => {
      const card = make('details', undefined, 'border rounded p-2 mb-2');
      card.append(make('summary', item.title || '未命名页面', 'fw-semibold'));
      card.append(make('div', `页面地址：${item.slug || '尚未生成'}`, 'text-muted small mt-2'));
      const parsed = new DOMParser().parseFromString(item.content || '', 'text/html');
      parsed.querySelectorAll('script,style').forEach(node => node.remove());
      const content = make('div', (parsed.body.textContent || '').trim() || '没有可预览的内容', 'mt-2');
      content.style.whiteSpace = 'pre-wrap'; content.style.maxHeight = '300px'; content.style.overflow = 'auto';
      card.append(content); target.append(card);
    });
    if (!(data.items || []).length) target.append(make('p', '没有生成页面，请检查主题和产品资料。'));
  }, 'growthLandingResult');
  handle('growthLandingCreate', async () => {
    const payload = landingPayload();
    text('growthLandingResult', '正在创建页面草稿…');
    const data = await request('/api/growth/landing-create', payload);
    refreshAdminPanels(['loadPages']);
    text('growthLandingResult', `已创建 ${data.count ?? (data.created || []).length} 个页面草稿。默认不显示，请到「板块与页面」检查后开启。`);
  }, 'growthLandingResult');

  let drafts = [];
  let selectedId = null;
  let aiReady = false;
  let collecting = false;
  let stopCollection = false;
  let pollTimer = null;
  let pollUntil = 0;
  let logStarted = false;
  function log(message, isError = false) {
    const target = byId('collectionLog');
    if (!logStarted) { target.replaceChildren(); logStarted = true; }
    const line = make('div', `${new Date().toLocaleTimeString()} · ${message}`, 'py-1' + (isError ? ' text-danger' : ''));
    target.append(line);
    while (target.childElementCount > 150) target.firstElementChild.remove();
    target.scrollTop = target.scrollHeight;
  }
  const activeDraft = () => drafts.find(d => String(d.id) === String(selectedId));
  function updateDraftButtons() {
    const d = activeDraft(); const language = byId('collectionLanguage').value;
    const hasTranslation = !!(d && d.translations && d.translations[language]);
    const active = busy.has('collectionTranslate') || busy.has('collectionImport');
    const collectionActive = collecting || busy.has('collectionHtmlImport');
    byId('collectionTranslate').disabled = !d || !language || !aiReady || active || collectionActive;
    byId('collectionImport').disabled = !d || (!!language && !hasTranslation) || active || collectionActive;
    byId('collectionLanguage').disabled = active || collectionActive || byId('collectionLanguage').options.length < 2;
    byId('collectionSourceLanguage').disabled = active || collectionActive || byId('collectionSourceLanguage').options.length < 2;
    byId('collectionAutoTranslate').disabled = collectionActive;
    byId('collectionAiStart').disabled = busy.has('collectionAiStart') || !!pollTimer;
  }
  function safeWebUrl(value) {
    try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) ? u.href : null; }
    catch (_) { return null; }
  }
  function appendField(parent, label, value) {
    const row = make('div', undefined, 'mb-2'); row.append(make('strong', `${label}：`));
    const content = make('span', value === undefined || value === null || value === '' ? '未采集到' : value);
    content.style.whiteSpace = 'pre-wrap'; row.append(content); parent.append(row);
  }
  function renderDetails() {
    const target = byId('collectionDraftDetail'); target.replaceChildren();
    const d = activeDraft();
    if (!d) { target.append(make('p', '先从左边选择一个草稿。')); updateDraftButtons(); return; }
    const original = d.product || {};
    const language = byId('collectionLanguage').value;
    const translation = d.translations && d.translations[language];
    const product = translation ? { ...original, ...translation } : original;
    target.append(make('div', language ? (translation ? '正在显示已保存的译文' : '所选语言还没有译文，下面显示原文。') : '正在显示采集原文', 'text-muted mb-2'));
    appendField(target, '商品名称', product.name);
    appendField(target, '原 SKU 编号', original.sku || '页面未提供');
    if (original.model) appendField(target, '型号', original.model);
    appendField(target, '原价格', original.price === null || original.price === undefined || original.price === '' ? '页面未提供' : `${original.price} ${original.currency || '（货币未知）'}`);
    appendField(target, '描述', product.description);
    appendField(target, '规格', product.spec);
    appendField(target, '分类', product.category);
    const source = safeWebUrl(original.source_url);
    if (source && !source.includes('imported-page.invalid')) { const link = make('a', '查看原商品页面'); link.href = source; link.target = '_blank'; link.rel = 'noopener noreferrer'; target.append(link); }
    const variants = original.variants || [];
    if (variants.length) {
      const detail = make('details', undefined, 'mt-2'); detail.append(make('summary', `查看 ${variants.length} 个 SKU / 规格组合`));
      variants.forEach((variant, index) => {
        const row = make('div', undefined, 'border-bottom py-2');
        const attrs = translation && translation.variants && translation.variants[index] ? translation.variants[index].attributes : variant.attributes;
        row.append(make('strong', variant.sku || variant.source_sku || '编号缺失'));
        row.append(make('div', (attrs || []).map(a => `${a.name}：${a.value}`).join(' / ') || '没有规格文字'));
        row.append(make('div', `价格：${variant.price ?? '未知'} ${original.currency || ''}；库存：${variant.stock ?? '未知'}`, 'text-muted'));
        detail.append(row);
      }); target.append(detail);
    }
    const images = original.images || [];
    appendField(target, '图片数量', images.length);
    if (images.length) {
      const thumbnails = make('div', undefined, 'd-flex gap-2 flex-wrap my-2');
      images.slice(0, 12).forEach((url, index) => {
        const safe = safeWebUrl(url); if (!safe) return;
        const img = make('img'); img.src = safe; img.alt = `商品图片 ${index + 1}`;
        img.width = 80; img.height = 80; img.loading = 'lazy'; img.style.objectFit = 'contain';
        img.referrerPolicy = 'no-referrer';
        img.addEventListener('error', () => img.replaceWith(make('span', `图片 ${index + 1} 暂时打不开`, 'text-muted')));
        thumbnails.append(img);
      });
      target.append(thumbnails);
      const detail = make('details'); detail.append(make('summary', '查看图片地址'));
      images.forEach((url, i) => {
        const safe = safeWebUrl(url); if (!safe) return;
        const row = make('div'); const link = make('a', `图片 ${i + 1}`); link.href = safe; link.target = '_blank'; link.rel = 'noopener noreferrer'; row.append(link); detail.append(row);
      }); target.append(detail);
    }
    if (original.warnings && original.warnings.length) target.append(make('p', `需要补充：${original.warnings.join('；')}`, 'text-warning mt-2'));
    updateDraftButtons();
  }
  function renderDrafts() {
    const target = byId('collectionDraftList'); target.replaceChildren();
    if (!drafts.length) { target.append(make('div', '还没有采集草稿。先粘贴商品链接或导入 HTML 文件。', 'border rounded p-3 small text-muted')); selectedId = null; }
    if (selectedId && !activeDraft()) selectedId = null;
    drafts.forEach(d => {
      const product = d.product || {};
      const chosen = String(d.id) === String(selectedId);
      const button = make('button', undefined, 'list-group-item list-group-item-action' + (chosen ? ' active' : ''));
      button.type = 'button'; button.setAttribute('aria-pressed', String(chosen));
      button.append(make('div', product.name || '未命名商品', 'fw-semibold'));
      button.append(make('div', `来源：${product.source_platform || product.source_url || 'HTML 文件'} · SKU：${(product.variants || []).length}`, 'small text-break'));
      const warnings = [...(product.warnings || [])];
      if (!product.description && !warnings.some(w => String(w).includes('描述'))) warnings.push('没有描述');
      if (!(product.variants || []).length) warnings.push('没有多规格 SKU 资料');
      if (warnings.length) button.append(make('div', `待检查：${warnings.join('；')}`, 'small mt-1'));
      const translated = Object.keys(d.translations || {});
      if (translated.length) button.append(make('div', `已有译文：${translated.join('、')}`, 'small mt-1'));
      button.addEventListener('click', () => { selectedId = d.id; text('collectionDraftMessage', ''); renderDrafts(); });
      target.append(button);
    });
    renderDetails();
  }
  function upsertDraft(draft, select = true) {
    if (!draft || draft.id === undefined) throw new Error('服务器没有返回有效商品草稿。');
    const index = drafts.findIndex(d => String(d.id) === String(draft.id));
    if (index >= 0) drafts[index] = draft; else drafts.unshift(draft);
    if (select) selectedId = draft.id;
    renderDrafts();
  }
  async function refreshDrafts() {
    const data = await request('/api/collection/drafts');
    drafts = data.items || [];
    if (!selectedId && drafts.length) selectedId = drafts[0].id;
    renderDrafts();
  }
  function setAiStatus(ai) {
    ai = ai || {}; aiReady = ai.ready === true;
    text('collectionAiState', ai.message || (aiReady ? '本地 AI 已就绪' : '本地 AI 尚未准备好'));
    const active = ['downloading', 'loading', 'installing', 'starting'].includes(ai.state);
    byId('collectionAiProgressWrap').hidden = !active;
    const progress = Number(ai.progress);
    const number = Number.isFinite(progress) ? Math.max(0, Math.min(100, progress)) : 0;
    byId('collectionAiProgress').style.width = `${number}%`;
    byId('collectionAiProgress').setAttribute('aria-valuenow', String(number));
    byId('collectionAiProgress').classList.toggle('progress-bar-striped', active);
    byId('collectionAiProgress').classList.toggle('progress-bar-animated', active);
    updateDraftButtons();
    return active;
  }
  async function refreshStatus(options = {}) {
    const data = await request('/api/collection/status');
    if (options.fillOptions) {
      const language = byId('collectionLanguage');
      language.replaceChildren(new Option('原文（不翻译）', ''));
      (data.languages || []).forEach(x => language.add(new Option(x.name, x.id)));
      const sourceLanguage = byId('collectionSourceLanguage');
      sourceLanguage.replaceChildren(new Option('自动识别', ''));
      (data.languages || []).forEach(x => sourceLanguage.add(new Option(x.name, x.id)));
      const platform = byId('collectionPlatform'); platform.replaceChildren();
      const searchPlatforms = (data.platforms || []).filter(x => x.search === true);
      searchPlatforms.forEach(x => platform.add(new Option(x.name, x.id)));
      platform.disabled = !platform.options.length;
      if (!platform.options.length) platform.add(new Option('暂时没有可查询的平台', ''));
      text('collectionPlatformNote', `当前有 ${searchPlatforms.length} 个支持关键词查找的平台来源。能否采集取决于商品页面实际公开的数据；其他来源可尝试直接粘贴商品链接。`);
    }
    const active = setAiStatus(data.ai);
    return { ...data.ai, active };
  }
  function stopPolling(message) {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = null; pollUntil = 0;
    byId('collectionAiPollStop').hidden = true;
    if (message) text('collectionAiState', message);
    updateDraftButtons();
  }
  function startPolling() {
    if (pollTimer) clearTimeout(pollTimer);
    pollUntil = Date.now() + 10 * 60 * 1000;
    byId('collectionAiPollStop').hidden = false;
    const poll = async () => {
      try {
        const ai = await refreshStatus();
        if (!pollUntil) return;
        if (ai.ready || !ai.active) { stopPolling(); return; }
        if (Date.now() >= pollUntil) { stopPolling('已停止自动查看进度。模型可能仍在准备，请稍后点击“准备 / 启动本地 AI”查看。'); return; }
        pollTimer = setTimeout(poll, 5000);
      } catch (e) { stopPolling(e.message); }
    };
    pollTimer = setTimeout(poll, 5000); updateDraftButtons();
  }
  handle('collectionAiStart', async () => {
    text('collectionAiState', '正在准备本地 AI…');
    const ai = await request('/api/collection/ai/start', {});
    const active = setAiStatus(ai.ai || ai);
    if (!(ai.ai || ai).ready && active) startPolling();
  }, 'collectionAiState');
  byId('collectionAiPollStop').addEventListener('click', () => stopPolling('已停止查看进度；这不会中断后台下载。稍后可以再次查看。'));
  byId('collectionLanguage').addEventListener('change', () => { text('collectionDraftMessage', ''); renderDetails(); });
  handle('collectionTranslate', async () => {
    const draft = activeDraft(); const language = byId('collectionLanguage').value;
    if (!draft || !language) throw new Error('请先选择草稿和目标语言。');
    if (!aiReady) throw new Error('本地 AI 尚未准备好，请先准备 / 启动。');
    text('collectionDraftMessage', '正在本机翻译，内容多时需要一些时间…');
    const sourceLanguage = byId('collectionSourceLanguage').value;
    updateDraftButtons();
    const data = await request(`/api/collection/drafts/${encodeURIComponent(draft.id)}/translate`, { language, source_language: sourceLanguage });
    const stillSelected = String(selectedId) === String(draft.id);
    upsertDraft(data.draft, false);
    refreshAdminPanels(['loadProducts', 'loadCategories', 'loadStats']);
    if (stillSelected) text('collectionDraftMessage', '译文已保存。请检查专业词和规格，再加入产品。');
    else log(`“${draft.product.name}”的译文已保存。`);
  }, 'collectionDraftMessage');
  handle('collectionImport', async () => {
    const draft = activeDraft(); const language = byId('collectionLanguage').value;
    if (!draft) throw new Error('请先选择草稿。');
    if (language && !(draft.translations || {})[language]) throw new Error('这个语言还没有译文，请先翻译。');
    text('collectionDraftMessage', `正在保存描述并下载 ${draft.product.images.length} 张图片，图片多时需要几分钟。请保持软件打开。`);
    const data = await request(`/api/collection/drafts/${encodeURIComponent(draft.id)}/import`, { language });
    refreshAdminPanels(['loadProducts', 'loadCategories', 'loadStats']);
    const message = `已加入产品，产品编号：${data.product_id}。请到「产品管理」检查资料和图片后再发布。${data.notice || ''}`;
    if (String(selectedId) === String(draft.id)) text('collectionDraftMessage', message);
    log(message);
  }, 'collectionDraftMessage');
  handle('collectionRefresh', refreshDrafts);
  function translationOptions() {
    const enabled = byId('collectionAutoTranslate').checked;
    const language = byId('collectionLanguage').value;
    if (enabled && !language) throw new Error('已选择自动翻译，请先在下方选择目标语言。');
    if (enabled && !aiReady) throw new Error('已选择自动翻译，请先准备 / 启动本地 AI，等显示“已就绪”再开始。');
    return { enabled, language, source_language: byId('collectionSourceLanguage').value };
  }
  async function translateCollected(draft, options) {
    if (!options.enabled) return true;
    try {
      log(`正在自动翻译：${draft.product.name}`);
      const data = await request(`/api/collection/drafts/${encodeURIComponent(draft.id)}/translate`, { language: options.language, source_language: options.source_language });
      upsertDraft(data.draft, false);
      refreshAdminPanels(['loadProducts', 'loadCategories', 'loadStats']);
      log(`已保存 ${options.language} 译文：${draft.product.name}`);
      return true;
    } catch (error) {
      log(`自动翻译失败，原文草稿已保留：${draft.product.name} — ${error.message}`, true);
      return false;
    }
  }
  handle('collectionCollect', async () => {
    const urls = [...new Set(lines(byId('collectionUrls').value))];
    if (!urls.length) throw new Error('请先粘贴至少一个商品链接。');
    if (urls.length > 20) throw new Error('一次最多采集 20 个链接，请分批进行。');
    if (urls.some(url => !safeWebUrl(url))) throw new Error('请填写完整的 http 或 https 商品链接，每行一个。');
    const translate = translationOptions();
    collecting = true; stopCollection = false; updateDraftButtons();
    byId('collectionStop').disabled = false; byId('collectionUrls').disabled = true;
    let succeeded = 0; let failed = 0; let attempted = 0; let translationFailed = 0;
    try {
      for (const url of urls) {
        if (stopCollection) break;
        attempted += 1;
        text('collectionProgress', `正在采集 ${attempted} / ${urls.length}`);
        try {
          const data = await request('/api/collection/collect', { url });
          upsertDraft(data.draft); succeeded += 1;
          log(`已保存草稿：${data.draft.product.name}；来源：${url}`);
          if (!(await translateCollected(data.draft, translate))) translationFailed += 1;
        } catch (e) { failed += 1; log(`采集失败：${url} — ${e.message}`, true); }
      }
      const message = `${stopCollection ? '已停止；' : '已处理；'}采集成功 ${succeeded} 个，采集失败 ${failed} 个，未处理 ${urls.length - attempted} 个。${translate.enabled ? `自动翻译成功 ${succeeded - translationFailed} 个，失败 ${translationFailed} 个。` : ''}`;
      text('collectionProgress', message); log(message);
    } finally { collecting = false; byId('collectionStop').disabled = true; byId('collectionUrls').disabled = false; }
  });
  byId('collectionStop').addEventListener('click', () => {
    if (collecting) { stopCollection = true; byId('collectionStop').disabled = true; text('collectionProgress', '停止后续采集，正在等待当前商品和翻译返回。'); }
  });
  function showFound(data) {
    byId('collectionFoundArea').hidden = false;
    const target = byId('collectionFoundList'); target.replaceChildren();
    const urls = [...new Set((data.urls || []).map(x => typeof x === 'string' ? x : x.url).filter(x => safeWebUrl(x)))];
    text('collectionFoundMessage', `${data.message || ''} 找到 ${urls.length} 个链接；请检查并选择要采集的商品。`);
    urls.forEach((url, index) => {
      const label = make('label', undefined, 'd-flex gap-2 border-bottom py-2 small');
      const check = make('input'); check.type = 'checkbox'; check.className = 'form-check-input flex-shrink-0'; check.value = url; check.checked = index < 20;
      label.append(check); label.append(make('span', url, 'text-break')); target.append(label);
    });
    if (!urls.length) target.append(make('p', '没有找到可用的商品链接。可以改用商品直达链接，或者导入保存到电脑的 HTML 文件。', 'small text-muted'));
  }
  handle('collectionSearch', async () => {
    const query = byId('collectionQuery').value.trim(); const platform = byId('collectionPlatform').value;
    if (!query || !platform) throw new Error('请先选择平台并输入商品关键词。');
    log('正在查找商品链接…');
    showFound(await request('/api/collection/search', { platform, query }));
  });
  handle('collectionShop', async () => {
    const url = byId('collectionShopUrl').value.trim();
    if (!safeWebUrl(url)) throw new Error('请先填写完整的店铺或商品列表页地址。');
    log('正在读取店铺页面中的商品链接…');
    showFound(await request('/api/collection/shop', { url, max_pages: Math.min(3, Math.max(1, Number(byId('collectionShopPages').value) || 1)) }));
  });
  byId('collectionFoundAll').addEventListener('click', () => {
    byId('collectionFoundList').querySelectorAll('input[type="checkbox"]').forEach((check, index) => { check.checked = index < 20; });
  });
  byId('collectionFoundUse').addEventListener('click', () => {
    if (collecting) { log('请等待当前采集结束后，再更换链接。', true); return; }
    const urls = Array.from(byId('collectionFoundList').querySelectorAll('input:checked')).map(check => check.value);
    if (!urls.length || urls.length > 20) { log('请选择 1 到 20 个商品链接。', true); return; }
    const combined = [...new Set([...lines(byId('collectionUrls').value), ...urls])];
    if (combined.length > 20) { log('与采集框已有链接合计超过 20 个，请先清理采集框或减少选择。', true); return; }
    byId('collectionUrls').value = combined.join('\n'); byId('collectionUrls').focus();
    log(`已把选中链接加入采集框，现在共 ${combined.length} 个。点击“开始采集”才会读取商品。`);
  });
  handle('collectionHtmlImport', async () => {
    const file = byId('collectionHtmlFile').files[0];
    if (!file) throw new Error('请先选择一个 HTML 文件。');
    if (!/\.html?$/i.test(file.name)) throw new Error('请导入 .html 或 .htm 网页文件。');
    if (file.size > 5 * 1024 * 1024) throw new Error('HTML 文件不能超过 5 MB，请去掉无关内容后再导入。');
    const source = byId('collectionHtmlSource').value.trim();
    if (source && !safeWebUrl(source)) throw new Error('原商品链接请填写完整的 http 或 https 地址，也可以留空。');
    const translate = translationOptions(); updateDraftButtons();
    const body = new FormData(); body.append('file', file); if (source) body.append('url', source);
    const data = await request('/api/collection/html', body);
    upsertDraft(data.draft); log(`文件已读取并保存草稿：${data.draft.product.name}`);
    await translateCollected(data.draft, translate);
  });
  byId('collectionSpreadsheet').addEventListener('click', () => {
    if (typeof window.showPanel === 'function') window.showPanel('sec-product');
    const wrap = byId('productImportWrap');
    if (wrap && wrap.classList.contains('d-none') && typeof window.toggleImportPanel === 'function') window.toggleImportPanel();
  });
  byId('collectionClearLog').addEventListener('click', () => { byId('collectionLog').replaceChildren(); logStarted = false; text('collectionLog', '进度显示已清空，采集草稿仍然保留。'); });
  refreshStatus({ fillOptions: true }).then(ai => { if (ai.active && !ai.ready) startPolling(); }).catch(e => { text('collectionAiState', e.message); log(`无法读取采集服务状态：${e.message}`, true); });
  refreshDrafts().catch(e => text('collectionDraftList', e.message));
})();
