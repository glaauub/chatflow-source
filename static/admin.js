/* 外贸一键建站 - 后台交互逻辑 */
const $ = (id) => document.getElementById(id);

async function api(url, opts) {
  const saveForm = window.__cfSubmittingForm;
  const saveState = saveForm && window.cfFormState ? window.cfFormState(saveForm) : null;
  window.__cfSubmittingForm = null;
  let r;
  try { r = await fetch(url, opts); }
  catch (_) { throw new Error('软件连接断开，这次操作是否保存成功还无法确认。请先复制未保存的内容，再重新打开 ChatFLOW，并使用它新打开的窗口；旧浏览器标签页可能已经失效。'); }
  if (r.redirected || !(r.headers.get('content-type') || '').includes('application/json')) throw new Error('登录或授权状态已变化，请重新进入软件；未保存内容请先复制留存。');
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || '请求失败');
  if (saveForm && opts && ['POST','PUT'].includes(opts.method)) window.dispatchEvent(new CustomEvent('cf-saved', {detail:{form:saveForm,state:saveState}}));
  return data;
}

function esc(s) {
  const div = document.createElement('div');
  div.textContent = s == null ? '' : String(s);
  return div.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* ===== 模板管理（下拉选择） ===== */
let currentTemplate = 'business';
const templatesMap = {};

function loadTemplates() {
  api('/api/templates').then(list => {
    const sel = $('templateSelect');
    if (!sel) return;
    list.forEach(t => { templatesMap[t.id] = t; });
    sel.innerHTML = list.map(t =>
      `<option value="${esc(t.id)}">${esc(t.name)}${t.desc ? ' — ' + esc(t.desc) : ''}</option>`).join('');
    sel.value = currentTemplate;
    sel.onchange = () => selectTemplate(sel.value);
    renderTemplateInfo();
  }).catch(e => alert(e.message));
}

function renderTemplateInfo() {
  const info = $('templateInfo');
  if (!info) return;
  const t = templatesMap[currentTemplate];
  if (!t) { info.innerHTML = ''; return; }
  info.innerHTML =
    `<div class="template-mini">
       <div class="swatch" style="background:${esc(t.thumb || '#e8edf5')}"></div>
       <div>
         <div class="fw-semibold">${esc(t.name)}</div>
         <div class="small text-muted">${esc(t.desc || '')}</div>
       </div>
     </div>`;
}

function selectTemplate(id) {
  currentTemplate = id;
  const sel = $('templateSelect');
  if (sel && sel.value !== id) sel.value = id;
  renderTemplateInfo();
  // 自动保存模板选择
  saveConfig({ site_template: id });
  // 若预览弹窗已打开，即时刷新预览
  const pm = bootstrap.Modal.getInstance($('previewModal'));
  if (pm && pm._isShown) $('previewFrame').src = previewUrl();
}

async function saveConfig(extra) {
  const cfg = Object.assign({
    site_template: currentTemplate,
    language: $('langSelect') ? $('langSelect').value : '',
    pay_methods: collectPayMethods(),
  }, extra || {});
  try {
    await api('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg)
    });
    if (cfg.language) currentLanguage = cfg.language;
    return true;
  } catch (e) { alert(e.message); return false; }
}

/* ===== 多语言设置 ===== */
let currentLanguage = 'en';
function loadLanguages() {
  api('/api/languages').then(list => {
    const sel = $('langSelect');
    sel.innerHTML = list.map(l => `<option value="${esc(l.id)}">${esc(l.name)}（${esc(l.id)}）</option>`).join('');
    if (list.some(l => l.id === currentLanguage)) sel.value = currentLanguage;
  }).catch(e => alert(e.message));
}

$('langForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const ok = await saveConfig();
  if (ok) {
    $('langSaveTip').textContent = '✅ 已保存，预览与生成将按新语言输出';
    setTimeout(() => { $('langSaveTip').textContent = ''; }, 2500);
  }
});

/* ===== 站点统计 ===== */
function loadStats() {
  api('/api/stats').then(s => {
    $('statProducts').textContent = s.products;
    $('statVersions').textContent = s.versions;
    $('statDeployCount').textContent = s.deploy_count;
    $('statLastDeploy').textContent = s.last_deploy || '暂无部署记录';
  }).catch(e => alert(e.message));
}

/* ===== 新手教程 ===== */
function loadTutorial() {
  api('/api/tutorial').then(t => {
    const box = $('tutorialBox');
    box.innerHTML =
      `<div class="mb-3"><h5 class="fw-bold mb-1">${esc(t.title)}</h5>
       <p class="text-muted small mb-0">${esc(t.subtitle || '')}</p></div>
       <div class="row g-3">
        ${(t.steps || []).map(st => `
          <div class="col-md-6">
            <div class="border rounded p-3 h-100">
              <div class="d-flex align-items-center mb-2">
                <span class="badge rounded-pill bg-primary me-2">Step ${esc(st.no)}</span>
                <span class="fw-bold">${esc(st.title)}</span>
              </div>
              <ol class="small mb-2 ps-3">${(st.items || []).map(it => `<li class="mb-1">${esc(it)}</li>`).join('')}</ol>
              ${st.tips ? `<div class="alert alert-warning py-2 small mb-0">💡 ${esc(st.tips)}</div>` : ''}
            </div>
          </div>`).join('')}
       </div>`;
  }).catch(e => { $('tutorialBox').innerHTML = `<div class="text-danger small">加载失败：${esc(e.message)}</div>`; });
}

/* ===== 支付方式渠道（全球移动/网络支付自选多填） ===== */
const PAY_GROUPS = [
  ['主流国际', [
    ['paypal', 'PayPal（收款邮箱）'], ['stripe', 'Stripe（支付链接）'], ['visa', 'Visa'],
    ['mastercard', 'Mastercard'], ['amex', 'American Express'], ['jcb', 'JCB'],
    ['discover', 'Discover'], ['card', '信用卡 / 借记卡'],
    ['applepay', 'Apple Pay'], ['googlepay', 'Google Pay']
  ]],
  ['中国 / 亚洲移动支付', [
    ['unionpay', '银联 UnionPay'], ['alipay', '支付宝 Alipay'], ['wechat', '微信支付 WeChat Pay'],
    ['paytm', 'Paytm（印度）'], ['gcash', 'GCash（菲律宾）'], ['grabpay', 'GrabPay（东南亚）'],
    ['touchngo', "Touch 'n Go（马来西亚）"], ['dana', 'DANA（印尼）'], ['ovo', 'OVO（印尼）'],
    ['maya', 'Maya（菲律宾）'], ['kakao', 'KakaoPay（韩国）'], ['naver', 'Naver Pay（韩国）'],
    ['linepay', 'LINE Pay'], ['phonepe', 'PhonePe（印度）'], ['razorpay', 'Razorpay（印度）'],
    ['razerpay', 'RazerPay（东南亚）'], ['paynow', 'PayNow（新加坡）'],
    ['promptpay', 'PromptPay（泰国）'], ['kpay', 'KBZ Pay（缅甸）'], ['bkash', 'bKash（孟加拉）'],
    ['mpesa', 'M-Pesa（非洲）']
  ]],
  ['国际钱包 / 在线支付', [
    ['usdt', 'USDT（加密货币）'], ['bitcoin', 'Bitcoin（加密货币）'], ['cashapp', 'Cash App'],
    ['venmo', 'Venmo'], ['zelle', 'Zelle'], ['klarna', 'Klarna'], ['afterpay', 'Afterpay'],
    ['shoppay', 'Shop Pay'], ['payoneer', 'Payoneer'], ['skrill', 'Skrill'],
    ['neteller', 'Neteller'], ['wise', 'Wise'], ['webmoney', 'WebMoney'],
    ['yandexpay', 'Yandex Pay（俄罗斯）']
  ]],
  ['拉美 / 其它地区', [
    ['pix', 'Pix（巴西）'], ['oxxo', 'OXXO（墨西哥）']
  ]],
  ['银行 / 汇款', [
    ['banktt', '银行电汇 Bank Transfer (T/T)'], ['westernunion', 'Western Union'], ['moneygram', 'MoneyGram']
  ]],
  ['其它', [
    ['custom', '自定义链接 Custom Link'], ['other', '其它渠道（自定义名称）']
  ]]
];
const PAY_FLAT = PAY_GROUPS.flatMap(g => g[1]);

function payTypeOptions(selected) {
  let html = '';
  for (const g of PAY_GROUPS) {
    html += `<optgroup label="${escHtml(g[0])}">`;
    for (const [id, lab] of g[1]) {
      html += `<option value="${escHtml(id)}" ${id === selected ? 'selected' : ''}>${escHtml(lab)}</option>`;
    }
    html += '</optgroup>';
  }
  return html;
}

let PAY_BRAND_COLORS = {};
let PAY_ICON_SVGS = {};

function loadPayBrands() {
  api('/api/pay_brands').then(c => { PAY_BRAND_COLORS = c || {}; }).catch(() => {});
}

function loadPayIcons() {
  api('/api/pay_icons').then(c => { PAY_ICON_SVGS = c || {}; }).catch(() => {});
}

function payShortLabel(optText) {
  return String(optText || '').split('（')[0].split('(')[0].trim();
}

/* 行内品牌/图标预览：自定义上传 icon -> 系统内置品牌徽章 SVG -> 品牌色字标 三级回退 */
function updatePayChip(row) {
  if (!row) return;
  const chip = row.querySelector('.pm-prev');
  const svgEl = row.querySelector('.pm-prev-svg');
  const imgEl = row.querySelector('.pm-prev-img');
  const sel = row.querySelector('.pay-type');
  const icon = row.querySelector('.pay-icon');
  if (!chip || !imgEl) return;
  const ic = icon ? icon.value.trim() : '';
  if (ic) {
    imgEl.src = ic;
    imgEl.classList.remove('d-none');
    chip.classList.add('d-none');
    if (svgEl) svgEl.classList.add('d-none');
    return;
  }
  imgEl.classList.add('d-none');
  const type = sel ? sel.value : '';
  const sysLogo = PAY_ICON_SVGS[type] || '';
  if (svgEl && sysLogo) {
    svgEl.innerHTML = '<img src="/static/' + sysLogo + '" alt="' + escHtml(type) + '" ' +
      'style="height:24px;width:auto;max-width:88px;object-fit:contain;display:inline-block;">';
    svgEl.classList.remove('d-none');
    chip.classList.add('d-none');
    return;
  }
  if (svgEl) svgEl.classList.add('d-none');
  chip.classList.remove('d-none');
  const opt = sel && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex] : null;
  const txt = payShortLabel(opt ? opt.text : '');
  const col = PAY_BRAND_COLORS[type] || '#5a6577';
  chip.style.setProperty('--pmc', col);
  chip.textContent = txt || type;
}

function addPayRow(type, value, name, icon) {
  const box = $('payMethodRows');
  if (!box) return;
  const row = document.createElement('div');
  row.className = 'pay-method-row d-flex gap-2 align-items-center flex-wrap';
  row.innerHTML =
    '<div class="btn-group-vertical flex-shrink-0" style="min-width:22px;">' +
    '<button type="button" class="btn btn-sm btn-outline-secondary pay-up px-1 py-0" title="上移"><i class="bi bi-chevron-up"></i></button>' +
    '<button type="button" class="btn btn-sm btn-outline-secondary pay-down px-1 py-0" title="下移"><i class="bi bi-chevron-down"></i></button>' +
    '</div>' +
    '<span class="pm pm-prev flex-shrink-0 d-none" style="--pmc:#5a6577;height:26px;font-size:12px;font-weight:700;background:#fff;border:1px solid #e2e7ee;border-radius:6px;display:inline-flex;align-items:center;padding:0 9px;white-space:nowrap;"></span>' +
    '<span class="pm-prev-svg d-none flex-shrink-0" title="官方品牌 logo（系统内置，无需上传；可选自定义图标覆盖）" style="height:26px;display:inline-flex;align-items:center;background:transparent;border:none;"></span>' +
    '<img class="pm-prev-img d-none flex-shrink-0" alt="渠道图标" style="height:26px;max-width:90px;object-fit:contain;">' +
    '<select class="form-select pay-type" style="min-width:220px;max-width:300px;">' + payTypeOptions(type || '') + '</select>' +
    '<input class="form-control pay-name d-none" type="text" placeholder="自定义渠道名称（如 MTN MoMo）" style="min-width:150px;max-width:220px;" value="' + escHtml(name || '') + '">' +
    '<div class="d-inline-flex align-items-center gap-1 flex-shrink-0">' +
    '<input type="hidden" class="pay-icon" value="' + escHtml(icon || '') + '">' +
    '<button type="button" class="btn btn-sm btn-outline-primary pay-ico-up" title="选择渠道后已自动匹配系统内置品牌徽章；如需完全自定义可上传 PNG/SVG 覆盖"><i class="bi bi-upload me-1"></i>自定义图标</button>' +
    '<span class="small text-muted" style="font-size:11px;line-height:1.1;max-width:150px;">不传图标即展示系统内置品牌徽章；可上传横版透明 PNG/SVG 覆盖</span>' +
    '</div>' +
    '<input class="form-control pay-value" type="text" placeholder="收款账号 / 邮箱 / 链接（可选，纯展示徽章）" value="' + escHtml(value || '') + '" style="min-width:220px;">' +
    '<button type="button" class="btn btn-outline-danger pay-del" title="移除该渠道"><i class="bi bi-x-lg"></i></button>';
  box.appendChild(row);
  const sel = row.querySelector('.pay-type');
  const nameInp = row.querySelector('.pay-name');
  const syncName = () => { nameInp.classList.toggle('d-none', sel.value !== 'other'); };
  sel.addEventListener('change', () => { syncName(); updatePayChip(row); });
  syncName();
  updatePayChip(row);
}

function movePayRow(row, dir) {
  if (!row) return;
  const box = row.parentElement;
  if (!box) return;
  const rows = Array.from(box.querySelectorAll('.pay-method-row'));
  const i = rows.indexOf(row);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= rows.length) return;
  if (dir < 0) box.insertBefore(row, rows[j]);
  else box.insertBefore(rows[j], row);
}

function renderPayRows(list) {
  const box = $('payMethodRows');
  if (!box) return;
  box.innerHTML = '';
  const arr = list && list.length ? list : [];
  arr.forEach(m => addPayRow(m.type || '', m.value || '', m.name || '', m.icon || ''));
  if (!arr.length) addPayRow('paypal', '');
}

function collectPayMethods() {
  const box = $('payMethodRows');
  if (!box) return [];
  const arr = [];
  box.querySelectorAll('.pay-method-row').forEach(r => {
    const sel = r.querySelector('.pay-type');
    const inp = r.querySelector('.pay-value');
    const nameInp = r.querySelector('.pay-name');
    const iconInp = r.querySelector('.pay-icon');
    if (!sel || !inp) return;
    const typ = sel.value.trim();
    const val = inp.value.trim();
    const nm = typ === 'other' ? (nameInp ? nameInp.value.trim() : '') : '';
    const ic = iconInp ? iconInp.value.trim() : '';
    if (typ) arr.push({ type: typ, value: val, name: nm, icon: ic });
  });
  const seen = new Set();
  return arr.filter(x => {
    const key = x.type === 'other' ? ('other:' + (x.name || '').toLowerCase()) : x.type;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

$('payForm').addEventListener('click', (e) => {
  const rows = $('payMethodRows');
  const r = e.target.closest('.pay-method-row');
  if (!rows || !r) return;
  if (e.target.closest('.pay-del')) {
    rows.removeChild(r);
    if (!rows.querySelector('.pay-method-row')) addPayRow('paypal', '');
    return;
  }
  if (e.target.closest('.pay-up')) { movePayRow(r, -1); return; }
  if (e.target.closest('.pay-down')) { movePayRow(r, 1); return; }
  if (e.target.closest('.pay-ico-up')) {
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = 'image/png,image/jpeg,image/webp,image/svg+xml';
    inp.onchange = async () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      if (f.size > 2 * 1024 * 1024) { alert('图标文件请控制在 2MB 以内'); return; }
      const fd = new FormData();
      fd.append('file', f);
      try {
        const res = await api('/api/upload', { method: 'POST', body: fd });
        const url = res.path || res.url || '';
        if (!url) { alert('上传失败：未返回文件地址'); return; }
        const hidden = r.querySelector('.pay-icon');
        if (hidden) hidden.value = url;
        updatePayChip(r);
      } catch (err) { alert(err.message || '上传失败'); }
    };
    inp.click();
    return;
  }
});
$('payAddBtn').addEventListener('click', () => addPayRow('', ''));

/* ===== 支付配置管理 ===== */
function loadConfig() {
  api('/api/config').then(cfg => {
    currentTemplate = cfg.site_template || 'business';
    currentLanguage = cfg.language || 'en';
    currentSiteLayout = cfg.site_layout || 'classic';
    if ($('langSelect')) $('langSelect').value = currentLanguage;
    if ($('siteLayoutSelect')) $('siteLayoutSelect').value = currentSiteLayout;
    renderPayRows(cfg.pay_methods || []);
    // 公司信息
    const c = cfg.company || {};
    $('companyName').value = c.name || '';
    $('companyLogo').value = c.logo || '';
    const prev = $('companyLogoPreview');
    if (prev && c.logo) { prev.src = c.logo; prev.classList.remove('d-none'); }
    // 网站 Logo（sec-brand 上传框）：加载即显示「已上传」预览
    if (cfg.site_logo) renderLogoPreview(cfg.site_logo);
    $('companyBrief').value = c.brief || '';
    $('companyAddress').value = c.address || '';
    $('companyPhone').value = c.phone || '';
    $('companyEmail').value = c.email || '';
    $('companyFounded').value = c.founded || '';
    $('companySize').value = c.size || '';
    if ($('companyIndustry')) $('companyIndustry').value = c.industry || '';
    if ($('companyProducts')) $('companyProducts').value = c.products || '';
    if ($('footerCopyright')) $('footerCopyright').value = c.footer_copyright || '';
    if ($('footerIcp')) $('footerIcp').value = c.footer_icp || '';
    // SEO
    const s = cfg.seo || {};
    $('seoSiteTitle').value = s.site_title || '';
    $('seoSiteDescription').value = s.site_description || '';
    $('seoSiteKeywords').value = s.site_keywords || '';
    $('seoAuthor').value = s.author || '';
    $('seoRobots').value = s.robots || '';
    $('seoHiddenKeywords').value = s.hidden_keywords || '';
    $('seoSiteUrl').value = s.site_url || '';
    $('seoAnalyticsCode').value = s.analytics_code || '';
    $('seoCookieEnabled').checked = String(s.cookie_enabled === undefined ? '1' : s.cookie_enabled) !== '0';
    // AI GEO
    $('geoBrandSummary').value = s.brand_summary || '';
    $('geoSellingPoints').value = s.selling_points || '';
    const aiOn = String(s.ai_enabled === undefined ? '1' : s.ai_enabled);
    $('geoAiEnabled').checked = ['1', 'true', 'on', 'yes'].includes(aiOn.toLowerCase());
    // AI GEO（P2 扩展字段）
    if ($('geoTargetMarkets')) $('geoTargetMarkets').value = Array.isArray(s.target_markets) ? s.target_markets.join('\n') : (s.target_markets || '');
    if ($('geoCerts')) $('geoCerts').value = Array.isArray(s.certifications) ? s.certifications.join('\n') : (s.certifications || '');
    if ($('geoSvcCaps')) $('geoSvcCaps').value = Array.isArray(s.service_capabilities) ? s.service_capabilities.join('\n') : (s.service_capabilities || '');
    geoFaqLoad(s.faq || []);
  }).catch(e => alert(e.message));
}

/* ===== 公司信息管理 ===== */
$('companyLogoUploadBtn').addEventListener('click', async () => {
  const fileInput = $('companyLogoFile');
  if (!fileInput.files.length) return alert('请先选择 Logo 图片文件');
  const fd = new FormData();
  fd.append('logo', fileInput.files[0]);
  try {
    const res = await api('/api/company/logo', { method: 'POST', body: fd });
    $('companyLogo').value = res.path || '';
    const prev = $('companyLogoPreview');
    if (res.path) {
      prev.src = res.path;
      prev.classList.remove('d-none');
    }
    alert('✅ Logo 已上传');
  } catch (e) { alert(e.message); }
});

$('companyForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await api('/api/company', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_name: $('companyName').value.trim(),
        company_logo: $('companyLogo').value.trim(),
        company_brief: $('companyBrief').value.trim(),
        company_address: $('companyAddress').value.trim(),
        company_phone: $('companyPhone').value.trim(),
        company_email: $('companyEmail').value.trim(),
        company_founded: $('companyFounded').value.trim(),
        company_size: $('companySize').value.trim(),
        company_industry: ($('companyIndustry') ? $('companyIndustry').value : '').trim(),
        company_products: ($('companyProducts') ? $('companyProducts').value : '').trim(),
        footer_copyright: ($('footerCopyright') ? $('footerCopyright').value : '').trim(),
        footer_icp: ($('footerIcp') ? $('footerIcp').value : '').trim()
      })
    });
    alert('✅ 公司信息已保存');
  } catch (e) { alert(e.message); }
});

/* ===== 公司简介一键生成（本地模板，不联网不填 Key） ===== */
async function genCompanyBrief() {
  const btn = $('briefGenBtn');
  if (btn) { btn.disabled = true; const old = btn.innerHTML; btn.innerHTML = '生成中...'; }
  try {
    const res = await api('/api/company/generate_brief', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template: $('briefTemplate').value })
    });
    $('companyBrief').value = res.brief || '';
    $('companyBrief').focus();
  } catch (e) { alert(e.message); }
  finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-stars me-1"></i>一键生成'; }
  }
}

/* ===== SEO / GEO 管理 ===== */
$('seoForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await api('/api/seo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        seo_site_title: $('seoSiteTitle').value.trim(),
        seo_site_description: $('seoSiteDescription').value.trim(),
        seo_site_keywords: $('seoSiteKeywords').value.trim(),
        seo_author: $('seoAuthor').value.trim(),
        seo_robots: $('seoRobots').value.trim(),
        seo_hidden_keywords: $('seoHiddenKeywords').value.trim(),
        site_url: $('seoSiteUrl').value.trim(),
        geo_brand_summary: $('geoBrandSummary').value.trim(),
        geo_selling_points: $('geoSellingPoints').value,
        geo_ai_enabled: $('geoAiEnabled').checked ? 1 : 0,
        // P2：AI GEO 精致化扩展字段
        geo_target_markets: $('geoTargetMarkets').value,
        geo_certifications: $('geoCerts').value,
        geo_service_capabilities: $('geoSvcCaps').value,
        geo_faq: JSON.stringify(geoFaqCollect()),
        analytics_code: $('seoAnalyticsCode').value.trim(),
        cookie_enabled: $('seoCookieEnabled').checked ? 1 : 0
      })
    });
    $('seoSaveTip').textContent = '✅ 已保存';
    setTimeout(() => { $('seoSaveTip').textContent = ''; }, 2000);
  } catch (e) { alert(e.message); }
});

/* ===== SEO 看得懂改造（P3）：折叠帮助 + 行业一键示例 ===== */
const SEO_SAMPLE_FIELD_MAP = {
  seoSiteTitle: 'site_title',
  seoSiteDescription: 'site_description',
  seoSiteKeywords: 'site_keywords',
  geoBrandSummary: 'brand_summary',
  geoSellingPoints: 'selling_points',
  geoSvcCaps: 'service_capabilities'
};
const SEO_SAMPLE_TIP_LABEL = {
  factory: '工厂 / 制造商', trading: '外贸公司 / 贸易商', startup: '初创 / 新站'
};

function seoHelpHtml(h) {
  const line = (label, v) => {
    const s = String(v == null ? '' : v);
    return '<div class="mt-1"><b>' + label + '</b>' + escHtml(s).replace(/\n/g, '<br>') + '</div>';
  };
  return line('这是什么：', h.what) + line('为什么重要：', h.why) + line('怎么写（示例）：', h.how);
}
function initSeoHelp() {
  if (!window.SEO_FIELD_HELP) {
    console.warn('[seo_help] SEO_FIELD_HELP 未加载，跳过折叠帮助注入');
    return;
  }
  document.querySelectorAll('label[data-help-key]').forEach(label => {
    const key = label.getAttribute('data-help-key');
    const h = window.SEO_FIELD_HELP[key];
    if (!h) return;
    if (label.querySelector('.seo-help-btn')) return;   // 防重复注入
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-link btn-sm p-0 ms-1 text-decoration-none align-baseline seo-help-btn';
    btn.title = '点击展开 / 收起帮助';
    btn.innerHTML = '<span class="text-primary">ⓘ</span> 这是什么';
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const box = document.querySelector('.seo-help-box[data-help-for="' + key + '"]');
      if (box) box.classList.toggle('d-none');
    });
    const box = document.createElement('div');
    box.className = 'seo-help-box small mt-1 mb-2 p-2 border-start border-2 border-info bg-white rounded d-none';
    box.setAttribute('data-help-for', key);
    box.innerHTML = seoHelpHtml(h);
    label.insertAdjacentElement('afterend', btn);
    btn.insertAdjacentElement('afterend', box);
  });
}
function bindSeoSampleUndo() {
  const btn = $('seoSampleUndoBtn');
  if (btn) btn.addEventListener('click', undoSeoSample);
}
function renderSeoSampleTip(industry, keptCount, appliedCount) {
  const tip = $('seoSampleTip');
  if (!tip) return;
  const industryLabel = SEO_SAMPLE_TIP_LABEL[industry] || industry;
  if (appliedCount === 0) {
    tip.innerHTML = '<div class="alert alert-secondary py-1 px-2 mb-0 small"><i class="bi bi-check2 me-1"></i><b>' + escHtml(industryLabel) + '</b>示例：本次涉及的字段您都已填写，为避免覆盖您的真实内容，没有改动任何字段。</div>';
  } else {
    tip.innerHTML = '<div class="alert alert-warning py-1 px-2 mb-0 small d-flex flex-wrap align-items-center gap-2">'
      + '<span><i class="bi bi-magic me-1"></i>已填写的 <b>' + keptCount + '</b> 项保持不变，示例只补空了 <b>' + appliedCount + '</b> 项。<b class="text-danger">示例仅供参考，请把 [占位符] 改成你的真实信息</b>（尤其是认证、年份与规模）。</span>'
      + '<button type="button" class="btn btn-sm btn-outline-danger py-0 ms-auto" id="seoSampleUndoBtn"><i class="bi bi-arrow-counterclockwise me-1"></i>撤销本次示例填充</button>'
      + '</div>';
  }
  tip.classList.remove('d-none');
  bindSeoSampleUndo();
}
function undoSeoSample() {
  const u = window.__seoSampleUndo;
  if (!u) return;
  (u.applied || []).forEach(it => {
    const el = $(it.id);
    if (el) el.value = it.oldValue;
  });
  window.__seoSampleUndo = null;
  const tip = $('seoSampleTip');
  if (tip) {
    tip.innerHTML = '<div class="alert alert-secondary py-1 px-2 mb-0 small"><i class="bi bi-arrow-counterclockwise me-1"></i>已撤销本次 <b>' + escHtml(u.label || '') + '</b> 示例填充，字段已还原为填充前的状态。</div>';
  }
}
function applyIndustrySample(industry) {
  if (window.__seoSampleUndo) undoSeoSample();   // 新示例前先还原旧示例，避免旧值记录被覆盖
  api('/api/seo/sample', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ industry: industry })
  }).then(data => {
    const smp = (data && data.sample) || {};
    const kept = [];
    const undoState = { applied: [], label: SEO_SAMPLE_TIP_LABEL[industry] || industry };
    Object.keys(SEO_SAMPLE_FIELD_MAP).forEach(id => {
      const el = $(id);
      const key = SEO_SAMPLE_FIELD_MAP[id];
      if (!el || !(key in smp)) return;
      const oldVal = el.value;
      if (oldVal.trim()) { kept.push(id); return; }            // 非空保留（B7：只补空，不覆盖）
      const raw = smp[key];
      const newVal = Array.isArray(raw) ? raw.join('\n') : String(raw == null ? '' : raw);
      if (!newVal.trim()) return;
      undoState.applied.push({ id: id, oldValue: oldVal });    // 记录旧值，撤销可一键还原
      el.value = newVal;
    });
    window.__seoSampleUndo = undoState.applied.length ? undoState : null;
    renderSeoSampleTip(industry, kept.length, undoState.applied.length);
  }).catch(e => alert(e.message));
}
if ($('seoSampleFactory')) {
  $('seoSampleFactory').addEventListener('click', () => applyIndustrySample('factory'));
  $('seoSampleTrading').addEventListener('click', () => applyIndustrySample('trading'));
  $('seoSampleStartup').addEventListener('click', () => applyIndustrySample('startup'));
}
initSeoHelp();

/* ===== AI GEO 精致化（P2）：FAQ 行编辑器 ===== */
function geoFaqRowHtml(q, a) {
  return `<div class="geo-faq-row border rounded p-2 mb-2">
    <div class="row g-1">
      <div class="col-8"><input class="form-control form-control-sm geo-faq-q" maxlength="300" placeholder="问题（AI 常被问到，如：你们的最小起订量是多少？）" value="${escHtml(q || '')}"></div>
      <div class="col-4 d-flex justify-content-end gap-1 align-items-start">
        <button class="btn btn-outline-secondary btn-sm geo-faq-up" type="button" title="上移"><i class="bi bi-arrow-up"></i></button>
        <button class="btn btn-outline-secondary btn-sm geo-faq-down" type="button" title="下移"><i class="bi bi-arrow-down"></i></button>
        <button class="btn btn-outline-danger btn-sm geo-faq-del" type="button" title="删除"><i class="bi bi-trash"></i></button>
      </div>
    </div>
    <textarea class="form-control form-control-sm mt-1 geo-faq-a" rows="2" maxlength="3000" placeholder="回答（AI 引用你的答案，如：MOQ 100 pcs，混装可议）">${escHtml(a || '')}</textarea>
  </div>`;
}
function geoFaqAddRow(data) {
  data = data || {};
  const box = $('geoFaqRows');
  if (!box) return;
  box.insertAdjacentHTML('beforeend', geoFaqRowHtml(data.q || '', data.a || ''));
  geoFaqBindRows(box);
}
function geoFaqCollect() {
  return [...document.querySelectorAll('#geoFaqRows .geo-faq-row')].map(r => ({
    q: (r.querySelector('.geo-faq-q').value || '').trim(),
    a: (r.querySelector('.geo-faq-a').value || '').trim()
  })).filter(x => x.q);
}
function geoFaqLoad(rows) {
  const box = $('geoFaqRows');
  if (!box) return;
  box.innerHTML = '';
  const arr = Array.isArray(rows) ? rows : [];
  arr.forEach(r => {
    if (Array.isArray(r)) geoFaqAddRow({ q: r[0], a: r[1] });   // 后端兼容 [q,a] 数组
    else geoFaqAddRow(r);
  });
  if (!arr.length) geoFaqAddRow();
}
function geoFaqMoveRow(row, dir) {
  if (dir < 0 && row.previousElementSibling) row.parentNode.insertBefore(row, row.previousElementSibling);
  if (dir > 0 && row.nextElementSibling) row.parentNode.insertBefore(row.nextElementSibling, row);
}
function geoFaqBindRows(scope) {
  scope.querySelectorAll('.geo-faq-up').forEach(btn => btn.onclick = () => geoFaqMoveRow(btn.closest('.geo-faq-row'), -1));
  scope.querySelectorAll('.geo-faq-down').forEach(btn => btn.onclick = () => geoFaqMoveRow(btn.closest('.geo-faq-row'), 1));
  scope.querySelectorAll('.geo-faq-del').forEach(btn => btn.onclick = () => btn.closest('.geo-faq-row').remove());
}
if ($('geoFaqAdd')) $('geoFaqAdd').addEventListener('click', () => geoFaqAddRow());
if (!$('geoFaqRows').children.length) geoFaqAddRow();

/* ===== AI GEO 精致化（P2）：服务能力工厂常用项填充 ===== */
const GEO_SVC_PRESETS = {
  en: ['OEM/ODM supported', 'Delivery time: 15-25 days', 'MOQ: 100 pcs', 'Free samples within 3 days'],
  zh: ['支持 OEM/ODM 定制', '交期 15-25 天', 'MOQ 100 pcs', '免费样品 3 天内发出']
};
$('geoSvcPreset').addEventListener('change', () => {
  $('geoSvcPresetBtn').disabled = !$('geoSvcPreset').value;
});
$('geoSvcPresetBtn').addEventListener('click', () => {
  const lang = $('geoSvcPreset').value;
  if (!lang) return;
  const lines = GEO_SVC_PRESETS[lang] || [];
  const ta = $('geoSvcCaps');
  ta.value = lines.join('\n');
  ta.focus();
  $('geoSvcPresetBtn').disabled = true;
  $('geoSvcPreset').value = '';
});

/* ===== AI GEO 精致化（P2）：健康度评分 ===== */
const GEO_HEALTH_JUMP = {
  brand_summary: 'geoBrandSummary', selling_points: 'geoSellingPoints',
  target_markets: 'geoTargetMarkets', certifications: 'geoCerts',
  service_capabilities: 'geoSvcCaps', faq: 'geoFaqRows',
  ai_enabled: 'geoAiEnabled', consistency: 'companyBrief'
};
function geoJumpTo(key) {
  const id = GEO_HEALTH_JUMP[key];
  const el = $(id);
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  const t = el.tagName === 'TEXTAREA' || el.tagName === 'INPUT' ? el : el.querySelector('input,textarea');
  if (t) t.focus({ preventScroll: true });
  el.style.transition = 'box-shadow .3s';
  el.style.boxShadow = '0 0 0 3px rgba(255,193,7,.7)';
  setTimeout(() => { el.style.boxShadow = ''; }, 1600);
}
$('geoHealthBtn').addEventListener('click', async () => {
  const box = $('geoHealthBox');
  box.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>评分中…';
  try {
    const res = await api('/api/geo/health', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const items = res.items || [];
    const cls = res.score >= 90 ? 'success' : (res.score >= 70 ? 'warning' : 'danger');
    box.innerHTML = `
      <div class="d-flex align-items-center gap-2 mb-1">
        <span class="fw-semibold text-dark">AI GEO 健康度：<span class="text-${cls}">${res.score} 分</span></span>
        <span class="badge text-bg-${cls}">${escHtml(res.grade || '')}</span>
      </div>
      <div class="progress mb-2" style="height:8px;"><div class="progress-bar bg-${cls}" style="width:${Math.max(res.score, 2)}%"></div></div>
      <div class="list-group list-group-flush">${items.map(it => `
        <div class="list-group-item px-1 py-1 d-flex align-items-start gap-2 ${it.passed ? '' : 'bg-warning-subtle'}">
          <span>${it.passed ? '✅' : '⚠️'}</span>
          <div class="flex-grow-1">
            <span class="fw-semibold small">${escHtml(it.label)} ${it.score}/${it.max}</span>
            <div class="text-muted small">${escHtml(it.hint || '')}</div>
          </div>
          ${it.passed ? '' : `<button class="btn btn-sm btn-outline-primary geo-health-jump" data-key="${escHtml(it.key)}">去填写</button>`}
        </div>`).join('')}
      </div>
      <div class="small text-muted mt-1">评分基于<b>最近一次保存</b>的 SEO 设置；如果刚改过内容请先点「保存 SEO 设置」再评分。分数只表示资料填写情况，不代表排名、曝光或 AI 推荐概率。</div>`;
    box.querySelectorAll('.geo-health-jump').forEach(btn => btn.onclick = () => geoJumpTo(btn.dataset.key));
  } catch (e) { box.textContent = '评分失败：' + e.message; }
});

/* ===== AI GEO 精致化（P2）：模拟 AI 引用预览 ===== */
$('geoPreviewBtn').addEventListener('click', async () => {
  const box = $('geoPreviewBox');
  box.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>生成预览中…';
  try {
    const res = await api('/api/geo/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    box.innerHTML = `
      <div class="alert alert-light border mb-2 py-2"><i class="bi bi-chat-quote me-1"></i><b>本地资料示例（未调用 AI，不代表真实引用）</b><div class="mt-1 text-dark">${escHtml(res.conversation || '')}</div></div>
      <div class="alert alert-light border mb-2 py-2"><i class="bi bi-file-text me-1"></i><b>结构化数据版（将写入 llms.txt / JSON-LD 的节选）</b><pre class="mb-0 mt-1" style="white-space:pre-wrap;">${escHtml(res.structured || '')}</pre><div class="mt-1 text-muted">FAQ 共 ${res.faq_count || 0} 条（结构化数据只预览前 3 问）。</div></div>
      <div class="small text-muted">预览基于<b>最近一次保存</b>的 SEO 设置；若刚改过内容请先保存再预览。<b>已保存</b> = 已点「保存 SEO 设置」。</div>`;
  } catch (e) { box.textContent = '预览失败：' + e.message; }
});

/* ===== AI GEO 精致化（P2）：从公司资料一键生成 GEO 草稿（确认弹窗 + 双按钮） ===== */
let geoDraftData = null;
function geoDraftTargets() {
  return [
    { key: 'brand_summary', input: $('geoBrandSummary'), label: 'Brand Summary' },
    { key: 'selling_points', input: $('geoSellingPoints'), label: '核心卖点' },
    { key: 'service_capabilities', input: $('geoSvcCaps'), label: '服务能力' },
    { key: 'target_markets', input: $('geoTargetMarkets'), label: '目标市场' }
  ];
}
function geoDraftFill(mode) {
  const d = geoDraftData;
  if (!d) return;
  let filled = 0, kept = 0;
  geoDraftTargets().forEach(t => {
    const draft = t.key === 'selling_points' ? (d.selling_points || []).join('\n')
      : t.key === 'service_capabilities' ? (d.service_capabilities || []).join('\n')
      : t.key === 'target_markets' ? (d.target_markets || []).join('\n')
      : (d.brand_summary || '');
    if (draft === '') return;
    const cur = (t.input.value || '').trim();
    if (mode === 'overwrite' || cur === '') {
      t.input.value = draft;
      filled++;
    } else kept++;
  });
  const m = document.getElementById('geoDraftModal');
  if (m && window.bootstrap && bootstrap.Modal) bootstrap.Modal.getInstance(m)?.hide();
  const box = $('geoDraftBox');
  box.innerHTML = `<span class="text-success"><i class="bi bi-check-circle me-1"></i>${mode === 'overwrite' ? '已整体覆盖' : '已填充空字段'} ${filled} 项${kept ? '（原已有内容的 ' + kept + ' 项保持不变）' : ''}——请检查后点「保存 SEO 设置」落库。FAQ 不会自动生成，请手动添加客户常问的交期 / MOQ 问题。</span>`;
}
$('geoDraftBtn').addEventListener('click', async () => {
  const btn = $('geoDraftBtn');
  btn.disabled = true;
  const old = btn.innerHTML;
  btn.innerHTML = '生成中…';
  try {
    const template = ($('briefTemplate') && $('briefTemplate').value) || 'factory';
    const res = await api('/api/geo/generate_draft', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template })
    });
    geoDraftData = res;
    const zh = String(res.lang || '').startsWith('zh');
    const sec = (title, text) => `<div class="mb-2"><div class="fw-semibold text-dark small">${title}</div><pre class="border rounded bg-light p-2 mb-1" style="white-space:pre-wrap;">${escHtml(text || '')}</pre></div>`;
    const rows = (title, arr) => sec(title, (arr || []).join('\n'));
    document.getElementById('geoDraftBody').innerHTML =
      sec('1. Brand Summary 草稿', res.brand_summary || '') +
      rows('2. 核心卖点草稿（可删改）', res.selling_points || []) +
      rows('3. 服务能力草稿（占位数字请替换为真实值）', res.service_capabilities || []) +
      rows('4. 目标市场（[待补充] 请替换为真实地区，不猜测）', res.target_markets || []);
    document.getElementById('geoDraftTips').innerHTML = (res.tips || []).map(t => '<div><i class="bi bi-exclamation-circle me-1"></i>' + escHtml(t) + '</div>').join('');
    document.getElementById('geoDraftModalBody').querySelector('.alert-warning').innerHTML =
      zh ? '<i class="bi bi-exclamation-triangle me-1"></i>草稿按当前站点语言生成，直接覆盖会替换你已填的内容——已填内容若未备份无法自动还原。缺数据处用 <b>[待补充]</b> 占位，不替你编造行业 / 市场 / 认证；FAQ 不会自动生成（需真实业务答案）。'
         : '<i class="bi bi-exclamation-triangle me-1"></i>Draft is generated in current site language. Overwrite replaces your existing content (no auto-undo). Missing data uses <b>[to be completed]</b> placeholders; FAQ is not auto-generated (needs real business answers).';
    if (window.bootstrap && bootstrap.Modal) new bootstrap.Modal(document.getElementById('geoDraftModal')).show();
  } catch (e) { alert('生成失败：' + e.message); }
  finally { btn.disabled = false; btn.innerHTML = old; }
});
$('geoDraftFillEmptyBtn').addEventListener('click', () => geoDraftFill('empty'));
$('geoDraftOverwriteBtn').addEventListener('click', () => geoDraftFill('overwrite'));

/* ===== SEO 关键词建议器 ===== */
let kwData = null;
$('suggestKwBtn').addEventListener('click', async () => {
  try {
    const res = await api('/api/seo/suggest_keywords');
    kwData = res.items || [];
    if (!kwData.length) { $('suggestKwBox').innerHTML = '<span class="text-danger">暂无可建议内容，请先添加产品。</span>'; return; }
    $('suggestKwBox').innerHTML = kwData.map(g => `
      <div class="mb-2">
        <div class="fw-semibold text-dark small">${g.label}</div>
        <div class="d-flex flex-wrap gap-1 mt-1">${(g.words || []).map(w => `<span class="badge text-bg-light border">${escHtml(w)}</span>`).join('')}</div>
      </div>`).join('');
    $('fillKwBtn').disabled = false;
    $('fillHiddenBtn').disabled = false;
  } catch (e) { alert(e.message); }
});
$('fillKwBtn').addEventListener('click', () => {
  if (!kwData) return;
  const core = (kwData[0] && kwData[0].words) || [];
  const tail = (kwData[1] && kwData[1].words) || [];
  const merged = [...new Set([...core, ...tail])];
  $('seoSiteKeywords').value = merged.slice(0, 20).join(', ');
  $('suggestKwBox').insertAdjacentHTML('beforeend', '<div class="text-success small mt-1"><i class="bi bi-check-circle me-1"></i>已填入“站点 Keywords”。</div>');
});
$('fillHiddenBtn').addEventListener('click', () => {
  if (!kwData) return;
  const core = (kwData[0] && kwData[0].words) || [];
  const tail = (kwData[1] && kwData[1].words) || [];
  $('seoHiddenKeywords').value = [...new Set([...tail, ...core])].slice(0, 20).join(', ');
  $('suggestKwBox').insertAdjacentHTML('beforeend', '<div class="text-success small mt-1"><i class="bi bi-check-circle me-1"></i>已填入“补充关键词”（长尾词）。</div>');
});

/* ===== SEO 自检清单 ===== */
function seoAuditCollectSeo() {
  return {
    seo_site_title: ($('seoSiteTitle') ? $('seoSiteTitle').value.trim() : ''),
    seo_site_description: ($('seoSiteDescription') ? $('seoSiteDescription').value.trim() : ''),
    seo_site_keywords: ($('seoSiteKeywords') ? $('seoSiteKeywords').value.trim() : ''),
    seo_author: ($('seoAuthor') ? $('seoAuthor').value.trim() : ''),
    seo_robots: ($('seoRobots') ? $('seoRobots').value.trim() : ''),
    seo_hidden_keywords: ($('seoHiddenKeywords') ? $('seoHiddenKeywords').value.trim() : ''),
    site_url: ($('seoSiteUrl') ? $('seoSiteUrl').value.trim() : ''),
    geo_brand_summary: ($('geoBrandSummary') ? $('geoBrandSummary').value.trim() : ''),
    geo_selling_points: ($('geoSellingPoints') ? $('geoSellingPoints').value : ''),
    geo_ai_enabled: ($('geoAiEnabled') && $('geoAiEnabled').checked) ? 1 : 0,
    geo_target_markets: ($('geoTargetMarkets') ? $('geoTargetMarkets').value : ''),
    geo_certifications: ($('geoCerts') ? $('geoCerts').value : ''),
    geo_service_capabilities: ($('geoSvcCaps') ? $('geoSvcCaps').value : ''),
    geo_faq: (typeof geoFaqCollect === 'function') ? JSON.stringify(geoFaqCollect()) : '[]',
    analytics_code: ($('seoAnalyticsCode') ? $('seoAnalyticsCode').value.trim() : ''),
    cookie_enabled: ($('seoCookieEnabled') && $('seoCookieEnabled').checked) ? 1 : 0
  };
}
async function seoAuditSave(patch) {
  const body = Object.assign(seoAuditCollectSeo(), patch || {});
  return await api('/api/seo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}
function seoAuditEscapeAttrJson(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function showAuditConfirm(textHtml, onOk) {
  let root = document.getElementById('auditConfirmModal');
  if (!root) {
    root = document.createElement('div');
    root.id = 'auditConfirmModal';
    root.className = 'modal fade';
    root.tabIndex = -1;
    root.innerHTML = '<div class="modal-dialog modal-dialog-centered"><div class="modal-content">'
      + '<div class="modal-header"><h5 class="modal-title"><i class="bi bi-shield-check me-1 text-primary"></i>确认执行修复</h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>'
      + '<div class="modal-body" id="auditConfirmBody"></div>'
      + '<div class="modal-footer"><button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">取消</button>'
      + '<button type="button" class="btn btn-primary" id="auditConfirmOk"><i class="bi bi-check-lg me-1"></i>确认执行</button></div></div>';
    document.body.appendChild(root);
  }
  document.getElementById('auditConfirmBody').innerHTML = textHtml;
  const okBtn = document.getElementById('auditConfirmOk');
  okBtn.onclick = async () => {
    const inst = (window.bootstrap && bootstrap.Modal) ? bootstrap.Modal.getInstance(root) : null;
    if (inst) inst.hide();
    try { await onOk(); } catch (e) { alert('修复失败：' + e.message); }
  };
  if (window.bootstrap && bootstrap.Modal) {
    new bootstrap.Modal(root, { backdrop: 'static' }).show();
  } else if (window.confirm(String(textHtml).replace(/<[^>]+>/g, '').trim())) {
    onOk().catch(e => alert('修复失败：' + e.message));
  }
}
function auditShowTip(html) {
  const box = $('seoAuditBox');
  box.insertAdjacentHTML('beforeend', '<div class="alert alert-success py-1 px-2 small mt-2 mb-0"><i class="bi bi-check-circle me-1"></i>' + html + '</div>');
}
function seoAuditGotoField(id) {
  if (id === 'category_manager') { showPanel('sec-categories'); return; }
  showPanel('sec-seo');
  const el = document.getElementById(id);
  if (el) setTimeout(() => { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); try { el.focus({ preventScroll: true }); } catch (e) { el.focus(); } }, 250);
}
function auditGoProduct(id, mode) {
  const root = document.getElementById('auditProductsModal');
  if (root && window.bootstrap && bootstrap.Modal) bootstrap.Modal.getInstance(root)?.hide();
  if (mode === 'seo') openProductSeo(id);
  else editProduct(id);
}
function openAuditProductModal(target, items) {
  const meta = {
    noimg_modal: { title: '无主图产品（去补图）', mode: 'edit', empty: '没有产品缺少主图。' },
    noseo_modal: { title: '未填产品级 SEO 的产品（建议逐个补全）', mode: 'seo', empty: '所有产品都已填写独立 SEO 标题/描述。' },
    nodesc_modal: { title: '无详情描述的产品（影响 JSON-LD 可读性）', mode: 'edit', empty: '没有产品缺少详情描述。' }
  }[target] || { title: '产品清单', mode: 'edit', empty: '暂无' };
  const list = (items || []).slice(0, 200);
  let root = document.getElementById('auditProductsModal');
  if (!root) {
    root = document.createElement('div');
    root.id = 'auditProductsModal';
    root.className = 'modal fade';
    root.tabIndex = -1;
    root.innerHTML = '<div class="modal-dialog modal-dialog-centered modal-dialog-scrollable"><div class="modal-content">'
      + '<div class="modal-header"><h5 class="modal-title" id="auditProductsTitle"></h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>'
      + '<div class="modal-body" id="auditProductsBody"></div>'
      + '<div class="modal-footer"><button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">关闭</button></div></div></div>';
    document.body.appendChild(root);
  }
  document.getElementById('auditProductsTitle').textContent = meta.title + (list.length ? '（' + list.length + ' 个，点击可直接跳转）' : '');
  const inner = list.length
    ? '<div class="list-group list-group-flush">' + list.map(p => '<div class="list-group-item px-0 py-2 d-flex align-items-center justify-content-between gap-2">'
      + '<div class="small text-truncate">' + escHtml(p.name || ('产品 #' + p.id)) + '</div>'
      + '<button class="btn btn-sm btn-outline-primary flex-shrink-0" onclick="auditGoProduct(' + Number(p.id) + ',\'' + meta.mode + '\')">'
      + (meta.mode === 'seo' ? '<i class="bi bi-search me-1"></i>去填 SEO' : '<i class="bi bi-pencil me-1"></i>去编辑') + '</button></div>').join('') + '</div>'
    : '<div class="text-muted small py-2">' + meta.empty + '</div>';
  document.getElementById('auditProductsBody').innerHTML = inner;
  if (window.bootstrap && bootstrap.Modal) new bootstrap.Modal(root).show();
}
function seoAuditGotoGenerate(previewText) {
  const run = () => {
    showPanel('sec-deploy');
    const el = $('repoName');
    if (el) setTimeout(() => { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); try { el.focus({ preventScroll: true }); } catch (e) { el.focus(); } }, 250);
    auditShowTip('已带您到「部署设置」：填写 GitHub 仓库名后点击「一键生成外贸网站并上传到 GitHub」，系统会重新生成整站（含 llms.txt / sitemap.xml）。');
  };
  if (previewText) showAuditConfirm('<div class="small">' + escHtml(previewText) + '</div>', run);
  else run();
}
async function doAuditFix(item) {
  const a = item.action || {};
  const p = a.payload || {};
  const fn = p.fn || '';
  let tip = '';
  if (fn === 'setFieldValue' && p.field) {
    const cur = String(seoAuditCollectSeo()[p.field] || '').trim();
    if (cur) {
      tip = '该字段已有内容，未做覆盖（保持你已填写的值）。';
    } else {
      await seoAuditSave({ [p.field]: String(p.value || '') });
      tip = '已写入并保存：' + escHtml(p.value || '');
    }
  } else if (fn === 'suggestKeywords') {
    const res = await api('/api/seo/suggest_keywords');
    const items = res.items || [];
    const core = (items[0] && items[0].words) || [];
    const tail = (items[1] && items[1].words) || [];
    const merged = [...new Set([...core, ...tail])];
    if (!merged.length) {
      tip = '暂无可生成的关键词，请先添加产品/完善公司资料后重试。';
    } else {
      await seoAuditSave({ seo_site_keywords: merged.slice(0, 20).join(', ') });
      tip = '已用本地建议生成 ' + merged.slice(0, 20).length + ' 个关键词并保存。';
    }
  } else if (fn === 'geoDraft') {
    const res = await api('/api/geo/generate_draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template: ($('briefTemplate') && $('briefTemplate').value) || 'factory' })
    });
    const draft = (res.selling_points || []).join('\n');
    if (!draft) {
      tip = '公司资料不足以生成卖点草稿，请先到「公司设置」补全公司简介/主营产品。';
    } else {
      const t = $('geoSellingPoints');
      const cur = (t && t.value ? t.value : '').trim();
      t.value = cur ? cur + '\n' + draft : draft;
      seoAuditGotoField('geoSellingPoints');
      tip = '卖点草稿已填入' + (cur ? '（追加到已有内容后）' : '') + '——请检查后点「保存 SEO 设置」落库，不会自动覆盖其它设置。';
    }
  } else if (fn === 'enableAI') {
    await seoAuditSave({ geo_ai_enabled: 1 });
    if ($('geoAiEnabled')) $('geoAiEnabled').checked = true;
    tip = '已开启「允许 AI 引用」并保存。';
  } else {
    tip = '未知修复动作';
  }
  auditShowTip(tip);
  if (typeof window.__seoAuditReRun === 'function') setTimeout(window.__seoAuditReRun, 600);
}
function auditAction(action) {
  if (!action) return;
  if (action.type === 'jump') { seoAuditGotoField(action.target); return; }
  if (action.type === 'open') {
    if (action.target === 'generate') { seoAuditGotoGenerate((action.payload || {}).preview); return; }
    if (action.target && String(action.target).indexOf('_modal') > 0) {
      openAuditProductModal(action.target, (action.payload || {}).items);
      return;
    }
    return;
  }
  if (action.type === 'fix') {
    const p = action.payload || {};
    const text = '<div class="small text-muted mb-2"><i class="bi bi-shield-check me-1"></i>这是一个写库/改动操作，确认后才会执行；不会改动你已填写的其它内容。</div>'
      + (p.preview ? '<div class="alert alert-light border small mb-0">' + escHtml(p.preview) + '</div>' : '<div class="text-muted small mb-0">确认执行该修复动作？</div>');
    showAuditConfirm(text, () => doAuditFix({ action: action }));
  }
}
function auditActionFrom(el) {
  try { auditAction(JSON.parse(el.getAttribute('data-action'))); } catch (e) { alert('修复动作解析失败：' + e.message); }
}
function renderSeoAudit(res) {
  const box = $('seoAuditBox');
  const checks = res.checks || [];
  box.innerHTML = `
    <div class="mb-2">${res.passed} / ${res.total} 项通过 ${res.passed === res.total ? '🎉 太棒了！' : '（红色项可点右侧「修复」一键处理）'}</div>
    <ul class="list-group list-group-flush">${checks.map(c => {
      const btnHtml = (!c.passed && c.action)
        ? `<button class="btn btn-sm btn-outline-warning flex-shrink-0 ms-1" type="button" data-action="${seoAuditEscapeAttrJson(JSON.stringify(c.action))}" onclick="auditActionFrom(this)"><i class="bi bi-magic me-1"></i>${escHtml(c.action.label || '修复')}</button>`
        : '';
      return `<li class="list-group-item px-1 py-2 ${c.passed ? '' : 'bg-danger-subtle'}">
        <div class="d-flex align-items-start gap-2">
          <span class="me-1">${c.passed ? '✅' : '❌'}</span>
          <div class="flex-grow-1">
            <div class="fw-semibold small ${c.passed ? 'text-success' : 'text-danger'}">${escHtml(c.label)}${c.detail ? ` <span class="text-muted fw-normal">— ${escHtml(c.detail)}</span>` : ''}</div>
            <div class="text-muted small"><i class="bi bi-question-circle me-1"></i>为什么重要：${escHtml(c.why || '')}</div>
          </div>
          ${btnHtml}
        </div>
      </li>`;
    }).join('')}
    </ul>`;
}
$('seoAuditBtn').addEventListener('click', async () => {
  const box = $('seoAuditBox');
  box.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>检查中…';
  try {
    const res = await api('/api/seo/audit');
    renderSeoAudit(res);
    window.__seoAuditReRun = () => { api('/api/seo/audit').then(renderSeoAudit).catch(() => {}); };
  } catch (e) {
    box.innerHTML = `<span class="text-danger">自检失败：${escHtml(e.message)}</span>`;
  }
});

function escHtml(s) {
  return String(s === undefined || s === null ? '' : s).replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[ch]);
}

$('payForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const ok = await saveConfig();
  if (ok) {
    $('paySaveTip').textContent = '✅ 已保存';
    setTimeout(() => { $('paySaveTip').textContent = ''; }, 2000);
  }
});

/* ===== Logo 管理 ===== */
function renderLogoPreview(path) {
  const box = $('logoPreview');
  if (path) {
    box.innerHTML = `<img src="${esc(path)}" alt="logo" style="max-height:52px;border:1px solid #eee;border-radius:6px;padding:4px;">`;
    box.classList.remove('d-none');
  } else {
    box.innerHTML = '';
    box.classList.add('d-none');
  }
}

$('logoForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = $('logoFile').files[0];
  if (!f) return alert('请先选择 Logo 图片');
  const fd = new FormData();
  fd.append('file', f);
  try {
    const res = await api('/api/logo', { method: 'POST', body: fd });
    renderLogoPreview(res.path);
    $('logoFile').value = '';
  } catch (e) { alert(e.message); }
});

$('logoRemoveBtn').addEventListener('click', async () => {
  try {
    await api('/api/logo', { method: 'DELETE' });
    renderLogoPreview('');
  } catch (e) { alert(e.message); }
});

/* ===== Banner 管理 ===== */
function loadBanners() {
  api('/api/banner').then(list => {
    const box = $('bannerList');
    box.innerHTML = list.length ? list.map(b =>
      `<div class="banner-item">
         <img src="${esc(b.image_path)}" alt="banner">
         <button class="btn btn-sm btn-danger" onclick="delBanner(${b.id})">删除</button>
       </div>`).join('') : '<div class="friendly-empty"><i class="bi bi-images"></i><div><b>还没有横幅</b><p>在上方选择图片上传，保存后首页顶部会自动轮播展示。</p></div></div>';
  }).catch(e => alert(e.message));
}

$('bannerForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const files = $('bannerFile').files;
  if (!files.length) return alert('请先选择图片');
  const fd = new FormData();
  for (const f of files) fd.append('file', f);
  try {
    await api('/api/banner/upload', { method: 'POST', body: fd });
    $('bannerFile').value = '';
    loadBanners();
  } catch (e) { alert(e.message); }
});

function delBanner(id) {
  if (!confirm('确定删除该横幅？')) return;
  api('/api/banner/' + id, { method: 'DELETE' }).then(loadBanners).catch(e => alert(e.message));
}

/* ===== 联系方式管理 ===== */
function loadContacts() {
  api('/api/contacts').then(list => {
    const tb = $('contactTable');
    tb.innerHTML = list.length ? list.map(c =>
      `<tr>
        <td>${esc(c.contact_type)}</td>
        <td>${esc(c.contact_value)}</td>
        <td class="text-end"><button class="btn btn-sm btn-outline-danger" onclick="delContact(${c.id})">删除</button></td>
      </tr>`).join('')
      : '<tr><td colspan="3"><div class="friendly-empty sm"><i class="bi bi-telephone"></i><div><b>还没有联系方式</b><p>在上方表单添加电话 / WhatsApp / 邮箱等，网站联系区会自动展示。</p></div></div></td></tr>';
  }).catch(e => alert(e.message));
}

$('contactForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const value = $('contactValue').value.trim();
  if (!value) return alert('请填写号码或 ID');
  try {
    await api('/api/contacts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contact_type: $('contactType').value, contact_value: value })
    });
    $('contactValue').value = '';
    loadContacts();
  } catch (e) { alert(e.message); }
});

function delContact(id) {
  if (!confirm('确定删除该联系方式？')) return;
  api('/api/contacts/' + id, { method: 'DELETE' }).then(loadContacts).catch(e => alert(e.message));
}

/* ===== 产品管理 ===== */
function loadSiteLayouts() {
  api('/api/detail_layouts').then(list => {
    const sel = $('siteLayoutSelect');
    if (!sel) return;
    sel.innerHTML = list.map(d =>
      `<option value="${esc(d.id)}">${esc(d.name)}${d.desc ? ' - ' + esc(d.desc) : ''}</option>`).join('');
    if (currentSiteLayout && list.some(d => d.id === currentSiteLayout)) sel.value = currentSiteLayout;
  }).catch(e => alert(e.message));
}

let currentSiteLayout = 'classic';

/* ===== 产品编辑：Word 式富文本描述 + 图片管理 ===== */
let editingProductId = null;
let imgUrls = [];        // 当前图片 URL 列表（第一张为主图，含新增）
let removedUrls = [];    // 待删除（物理清理）的图片 URL
let productRteInited = false;

function renderImgManager() {
  const box = $('existingImgs');
  box.innerHTML = '';
  imgUrls.forEach((u, i) => {
    const wrap = document.createElement('div');
    wrap.className = 'border rounded p-1 text-center';
    wrap.style.width = '104px';
    wrap.innerHTML = `<img src="${esc(u)}" class="w-100 rounded" style="height:72px;object-fit:cover;" alt="">
      <div class="d-flex justify-content-center gap-1 mt-1">
        ${i === 0
          ? '<span class="badge bg-primary">主图</span>'
          : `<button type="button" class="btn btn-sm btn-outline-primary py-0 px-1" title="设为主图" onclick="setMainImg('${esc(u)}')">设主图</button>`}
        <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" title="删除图片" onclick="removeImg('${esc(u)}')">删除</button>
      </div>`;
    box.appendChild(wrap);
  });
  if (!imgUrls.length) box.innerHTML = '<div class="friendly-empty sm"><i class="bi bi-images"></i><div><b>还没有图片</b><p>点「选择图片」上传，第一张会自动设为主图。</p></div></div>';
}

function setMainImg(url) {
  const idx = imgUrls.indexOf(url);
  if (idx <= 0) return;
  imgUrls.splice(idx, 1);
  imgUrls.unshift(url);
  renderImgManager();
}

function removeImg(url) {
  imgUrls = imgUrls.filter(u => u !== url);
  if (!removedUrls.includes(url)) removedUrls.push(url);
  renderImgManager();
}

async function uploadProductImgs(files) {
  for (const f of files) {
    const fd = new FormData();
    fd.append('file', f);
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || '上传失败');
    imgUrls.push(data.path);
  }
  renderImgManager();
}

$('pImg').addEventListener('change', async (e) => {
  const files = Array.from(e.target.files || []);
  if (!files.length) return;
  const btn = $('pImgUploadBtn');
  if (btn) { btn.disabled = true; btn.textContent = '上传中...'; }
  try {
    await uploadProductImgs(files);
  } catch (err) {
    alert(err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-upload me-1"></i>选择图片'; }
    e.target.value = '';
  }
});

let currentProductIds = [];

function updateMetaCounts() {
  const t = $('pMetaTitleCount');
  const d = $('pMetaDescCount');
  if (t) t.textContent = String(($('pMetaTitle') ? $('pMetaTitle').value : '') || '').length;
  if (d) d.textContent = String(($('pMetaDesc') ? $('pMetaDesc').value : '') || '').length;
}
['pMetaTitle', 'pMetaDesc'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', updateMetaCounts);
});

function loadProducts() {
  api('/api/products').then(list => {
    currentProductIds = list.map(p => p.id);
    const tb = $('productTable');
    if (!list.length) {
      tb.innerHTML = '<tr><td colspan="6"><div class="friendly-empty"><i class="bi bi-box2"></i><div><b>还没有产品</b><p>点下方按钮添加第一个产品：填名称、价格并上传图片，保存后可预览，发布后客户才能看到更新。</p></div><button class="btn btn-sm btn-primary" onclick="openProductForm()"><i class="bi bi-plus-lg me-1"></i>新增产品</button></div></td></tr>';
    } else {
      tb.innerHTML = list.map(p => {
        const hasSeo = !!(((p.meta_title || '').trim()) || ((p.meta_description || '').trim()));
        return `<tr>
        <td>${p.img ? `<img class="product-thumb" src="${esc(p.img)}" alt="">` : '<span class="text-muted small">无图</span>'}</td>
        <td>${esc(p.name)}${p.category ? `<div class="small text-secondary">${esc(p.category)}</div>` : ''}</td>
        <td class="text-warning fw-bold">${esc(p.price)}</td>
        <td>${p.stock === null ? '<span class="text-secondary small">未知</span>' : (p.stock > 0 ? `<span class="text-success">${esc(p.stock)}</span>` : '<span class="text-danger small">缺货</span>')}</td>
        <td class="text-nowrap text-center">
          <button class="btn btn-sm btn-outline-secondary py-0 px-1" title="上移（前台展示顺序）" onclick="moveProduct(${p.id}, -1)"><i class="bi bi-arrow-up"></i></button>
          <button class="btn btn-sm btn-outline-secondary py-0 px-1" title="下移（前台展示顺序）" onclick="moveProduct(${p.id}, 1)"><i class="bi bi-arrow-down"></i></button>
        </td>
        <td class="text-end text-nowrap">
          <button class="btn btn-sm ${hasSeo ? 'btn-outline-success' : 'btn-outline-secondary'}" title="${hasSeo ? '已填写独立 SEO 标题/描述（点击可快速查看/修改）' : '未填写产品级 SEO（选填，不填自动用默认规则）'}" onclick="openProductSeo(${p.id})"><i class="bi ${hasSeo ? 'bi-check-circle-fill' : 'bi-circle'} me-1"></i>SEO</button>
          <button class="btn btn-sm btn-outline-secondary" title="复制为一条完整新产品（图片/富文本/规格/价格等全部字段）" onclick="copyProduct(${p.id})"><i class="bi bi-copy me-1"></i>复制</button>
          <button class="btn btn-sm btn-outline-primary" onclick="editProduct(${p.id})">编辑</button>
          <button class="btn btn-sm btn-outline-danger" onclick="delProduct(${p.id})">删除</button>
        </td>
      </tr>`;
      }).join('');
    }
  }).catch(e => alert(e.message));
}

function openProductSeo(id) {
  if (!id) return;
  editProduct(id);
  setTimeout(() => {
    const c = document.getElementById('pMetaSeoCollapse');
    if (c) {
      const inst = (window.bootstrap && bootstrap.Collapse) ? bootstrap.Collapse.getOrCreateInstance(c) : null;
      if (inst) inst.show();
      c.scrollIntoView({ behavior: 'smooth', block: 'center' });
      const t = document.getElementById('pMetaTitle');
      if (t) t.focus();
    }
  }, 250);
}

/* ===== 产品批量导入（下载模板 / 导入面板 / 导入报告） P1 ===== */
let lastImportResult = null;
let lastImportFileName = '';

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function toggleImportPanel() {
  const w = $('productImportWrap');
  if (!w) return;
  const show = w.classList.contains('d-none');
  w.classList.toggle('d-none', !show);
  const btn = $('productImportToggleBtn');
  if (btn) btn.classList.toggle('btn-outline-primary', show);
  if (show) {
    // 打开导入面板时收起单条编辑表单，避免两区同时展开
    const fw = $('productFormWrap');
    if (fw) fw.classList.add('d-none');
    showPanel('sec-product');
  }
}

function downloadTemplateXlsx() {
  // xlsx 模板由后端生成（含表头/说明/示例三行）
  window.location.href = '/api/products/template';
}

function downloadTemplateCsv() {
  // csv 模板在前端直接生成（utf-8 BOM 保证 Excel 打开中文不乱码），列结构与 xlsx 模板一致
  const rows = [
    ['产品名称', '价格', '分类', '库存数量', 'SKU', '型号', '规格', '产品视频链接', '详细描述', '图片'],
    ['产品名称（必填，不能与已有产品同名，如：LED Lamp）', '价格（选填，原样保存，如 $9.90 或 9.90）', '分类（选填，不存在会自动创建）', '库存数量（选填，整数 ≥0；未知留空；非法值跳过该行）', 'SKU（选填，库存编码）', '型号（选填）', '规格（选填，如 10x10x5cm）', '产品视频链接（选填，YouTube/Vimeo 分享链接）', '详细描述（选填，产品介绍文本）', '图片文件名（选填，如 led-lamp.jpg；多张用 | 分隔，如 a.jpg|b.jpg；文件需和本表格一起上传，或打包 zip）'],
    ['示例-请删除本行', '$9.90', 'LED 灯具', '100', 'LED-100W-A', 'XT-880', '10x10x5cm', 'https://www.youtube.com/watch?v=xxxx', '这是一段示例产品介绍，导入时会自动跳过。', 'led-lamp.jpg|led-lamp-2.jpg']
  ];
  const csv = '\ufeff' + rows.map(r => r.map(c => '"' + String(c == null ? '' : c).replace(/"/g, '""') + '"').join(',')).join('\r\n');
  saveBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), 'ChatFLOW产品批量导入模板.csv');
}

const IMPORT_IMG_EXTS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'];

function importFileKind(name) {
  const ext = (name.split('.').pop() || '').toLowerCase();
  if (ext === 'xlsx' || ext === 'csv') return 'table';
  if (ext === 'zip') return 'zip';
  if (IMPORT_IMG_EXTS.indexOf(ext) >= 0) return 'img';
  return 'other';
}

function onImportFileChange() {
  const input = $('productImportFile');
  if (!input || !input.files || !input.files.length) return;
  const files = Array.from(input.files);
  let table = null, zip = null;
  for (const file of files) {
    const kind = importFileKind(file.name);
    if (kind === 'other') {
      alert('不支持的文件：' + file.name + '（请只选 .xlsx/.csv 表格、图片文件或 .zip 压缩包）');
      input.value = '';
      return;
    }
    if (kind === 'table') {
      if (table) {
        alert('请只选择一个表格文件：' + file.name);
        input.value = '';
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        alert('表格文件超过 10MB 上限，请拆分后导入');
        input.value = '';
        return;
      }
      table = file;
    }
    if (kind === 'zip') {
      if (files.length > 1) {
        alert('选择 .zip 压缩包时请只选择该压缩包一个文件');
        input.value = '';
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        alert('压缩包超过 50MB 上限，请拆分后导入');
        input.value = '';
        return;
      }
      zip = file;
    }
  }
  if (!table && !zip) {
    alert('请选择表格文件（.xlsx/.csv）或 .zip 压缩包');
    input.value = '';
    return;
  }
}

function startProductImport() {
  const input = $('productImportFile');
  const files = input && input.files ? Array.from(input.files) : [];
  if (!files.length) {
    alert('请先选择要导入的文件（.xlsx/.csv 表格 + 图片，或 .zip 压缩包）');
    return;
  }
  // 分类文件：zip 单独提交；否则 1 个表格 + 若干图片
  let tableFile = null, zipFile = null;
  const imgFiles = [];
  for (const file of files) {
    const kind = importFileKind(file.name);
    if (kind === 'zip') zipFile = file;
    else if (kind === 'table') tableFile = file;
    else if (kind === 'img') imgFiles.push(file);
    else {
      alert('不支持的文件：' + file.name + '（请只选 .xlsx/.csv 表格、图片文件或 .zip 压缩包）');
      return;
    }
  }
  if (zipFile) {
    if (files.length > 1 || tableFile || imgFiles.length) {
      alert('选择 .zip 压缩包时请只选择该压缩包一个文件');
      return;
    }
    if (zipFile.size > 50 * 1024 * 1024) {
      alert('压缩包超过 50MB 上限，请拆分后导入');
      return;
    }
  } else {
    if (!tableFile) {
      alert('请选择一个表格文件（.xlsx/.csv）');
      return;
    }
    if (tableFile.size > 10 * 1024 * 1024) {
      alert('表格文件超过 10MB 上限，请拆分后导入');
      return;
    }
  }
  const displayName = zipFile ? zipFile.name : (tableFile.name + (imgFiles.length ? ' + ' + imgFiles.length + ' 张图片' : ''));
  const bodyTip = zipFile ? '压缩包内自动匹配同名的表格与图片文件。'
    : '表格「图片」列填写的文件名会与所选图片文件按文件名自动匹配，匹配不到的行仅提示缺失、不影响导入。';
  if (!confirm('确认导入“' + displayName + '”？\n\n' + bodyTip + '\n导入只新增产品：与已有产品重名的行自动跳过、失败行自动跳过并写进报告，不会修改或删除已有产品。')) return;
  const fd = new FormData();
  if (zipFile) {
    fd.append('file', zipFile);
  } else {
    fd.append('file', tableFile);
    imgFiles.forEach(f => fd.append('images', f, f.name));
  }
  const btn = $('productImportBtn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>导入中…';
  }
  api('/api/products/import', { method: 'POST', body: fd })
    .then(res => {
      renderImportReport(res, zipFile ? zipFile.name : tableFile.name);
      loadProducts();
      loadStats();
      showPanel('sec-product');
    })
    .catch(e => alert(e.message))
    .finally(() => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-play-circle me-1"></i>开始导入';
      }
    });
}

function renderImportReport(r, fname) {
  lastImportResult = r;
  lastImportFileName = fname || '';
  const box = $('productImportReport');
  if (!box) return;
  box.classList.remove('d-none');
  const fBtn = $('failReportBtn');
  if (fBtn) fBtn.style.display = (r.failed && r.failed.length) ? '' : 'none';
  const failed = r.failed || [];
  const dups = r.skipped_duplicate_names || [];
  const cats = r.new_categories || [];
  const warns = r.warnings || [];
  const unknown = r.unknown_cols || [];
  let html = '';
  if (r.success === 0 && failed.length === 0 && (r.note_rows || 0) > 0) {
    html += '<div class="alert alert-warning py-2 mb-2"><i class="bi bi-info-circle me-1"></i>文件里没有可导入的数据行（仅包含说明行 / 示例行 / 空行），请填写产品数据后重新导入。</div>';
  } else {
    html += '<div class="alert alert-success py-2 mb-2"><i class="bi bi-check-circle me-1"></i><b>导入完成：成功 ' + r.success + '，失败 ' + failed.length + '，重复跳过 ' + (r.skipped_duplicates || 0) + '</b>'
      + (r.note_rows ? '　（已自动跳过说明/示例行 ' + r.note_rows + ' 行）' : '')
      + '</div>';
  }
  if (cats.length) {
    html += '<div class="alert alert-info py-2 mb-2"><i class="bi bi-tags me-1"></i>系统已自动创建分类：<b>' + esc(cats.join('、')) + '</b> 等 ' + cats.length + ' 个</div>';
  }
  if (failed.length) {
    html += '<div class="mb-2"><span class="fw-semibold text-danger small">失败明细（' + failed.length + ' 行，已跳过未入库）：</span></div>'
      + '<div class="table-responsive"><table class="table table-sm table-bordered align-middle mb-0"><thead class="table-light"><tr><th style="width:90px">文件行号</th><th>产品名称</th><th>失败原因</th></tr></thead><tbody>'
      + failed.map(f => '<tr><td class="text-secondary text-nowrap">第 ' + f.row + ' 行</td><td>' + esc(f.name || '（无名称）') + '</td><td class="text-danger">' + esc(f.reason) + '</td></tr>').join('')
      + '</tbody></table></div>';
  }
  if (dups.length) {
    const shown = dups.slice(0, 10).map(d => esc(d.name)).join('、');
    html += '<div class="small text-secondary mt-2"><i class="bi bi-arrow-repeat me-1"></i>与已有产品/本次导入产品重名，已跳过：' + shown
      + (dups.length > 10 ? ' 等 ' + dups.length + ' 个' : '') + '</div>';
  }
  (warns || []).forEach(w => {
    html += '<div class="small text-warning mt-1"><i class="bi bi-exclamation-triangle me-1"></i>' + esc(w) + '</div>';
  });
  if (unknown.length) {
    html += '<div class="small text-muted mt-1"><i class="bi bi-info-circle me-1"></i>存在未识别列（已忽略，不影响导入）：' + esc(unknown.slice(0, 8).join('、')) + (unknown.length > 8 ? ' 等' : '') + '</div>';
  }
  box.innerHTML = html;
}

function downloadFailReport() {
  const r = lastImportResult;
  if (!r || !r.failed || !r.failed.length) {
    alert('当前没有失败记录可下载');
    return;
  }
  const lines = [
    '产品批量导入失败报告',
    '文件：' + (lastImportFileName || ''),
    '成功 ' + r.success + ' 条 / 失败 ' + r.failed.length + ' 条 / 重复跳过 ' + (r.skipped_duplicates || 0) + ' 条',
    '', '失败明细：'
  ];
  r.failed.forEach(f => lines.push('第 ' + f.row + ' 行「' + (f.name || '') + '」导入失败：' + f.reason));
  if (r.warnings && r.warnings.length) {
    lines.push('', '提示：');
    r.warnings.forEach(w => lines.push('- ' + w));
  }
  saveBlob(new Blob(['\ufeff' + lines.join('\r\n'), ], { type: 'text/plain;charset=utf-8' }), '产品导入失败报告.txt');
}

function moveProduct(id, dir) {
  const i = currentProductIds.indexOf(id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= currentProductIds.length) return;
  const arr = currentProductIds.slice();
  arr.splice(i, 1);
  arr.splice(j, 0, id);
  api('/api/products/reorder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids: arr })
  }).then(() => loadProducts()).catch(e => alert(e.message));
}

function openProductForm() {
  resetProductForm();
  $('productFormWrap').classList.remove('d-none');
  if (!productRteInited) {
    initRte('pRte', 'pDesc', 'pRteBar');
    productRteInited = true;
  }
  showPanel('sec-product');
  setTimeout(() => { const nm = $('pName'); if (nm) nm.focus(); }, 80);
}

function cancelProductForm() {
  resetProductForm();
  const w = $('productFormWrap');
  if (w) w.classList.add('d-none');
}

function editProduct(id) {
  api('/api/products/' + id).then(p => {
    if (!p || !p.id) return alert('产品不存在');
    editingProductId = id;
    removedUrls = [];
    imgUrls = (p.images && p.images.length ? p.images : (p.img ? [p.img] : []));
    $('pName').value = p.name || '';
    $('pPrice').value = p.price || '';
    loadCategoryOptions(p.category || '').then(() => { $('pCategory').value = p.category || ''; });
    $('pStock').value = p.stock === null ? '' : (p.stock || 0);
    $('pSku').value = p.sku || '';
    $('pModel').value = p.model || '';
    $('pSpec').value = p.spec || '';
    $('pVideo').value = p.product_video || '';
    $('pMetaTitle').value = p.meta_title || '';
    $('pMetaDesc').value = p.meta_description || '';
    updateMetaCounts();
    if (!productRteInited) {
      initRte('pRte', 'pDesc', 'pRteBar');
      productRteInited = true;
    }
    setRteHtml('pRte', mdToHtml(p.description));
    renderImgManager();
    const titleEl = $('productFormTitle');
    if (titleEl) titleEl.textContent = '编辑产品：' + (p.name || '');
    const submitBtn = $('productSubmitBtn');
    if (submitBtn) submitBtn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>保存修改';
    const cancelBtn = $('cancelEditBtn');
    if (cancelBtn) cancelBtn.style.display = '';
    const tip = $('productFormTip');
    if (tip) tip.textContent = '保存后将自动收起编辑面板';
    const cpy = $('productCopyBtn');
    if (cpy) cpy.classList.remove('d-none');
    $('productFormWrap').classList.remove('d-none');
    showPanel('sec-product');
  }).catch(e => alert(e.message));
}

/* ===== 产品复制 ===== */
function copyProduct(id) {
  if (!id) return alert('缺少产品 ID');
  if (!confirm('将复制为一条完整的新产品记录（图片/富文本/分类/规格/价格/型号/SKU/库存等全部字段），复制后可继续改名编辑。')) return;
  api('/api/products/' + id + '/copy', { method: 'POST' })
    .then(() => { alert('✅ 已创建副本，列表已刷新'); loadProducts(); loadStats(); })
    .catch(e => alert(e.message));
}

function copyEditingProduct() {
  if (editingProductId) copyProduct(editingProductId);
  else alert('请先保存当前产品，再进行复制');
}

function resetProductForm() {
  editingProductId = null;
  imgUrls = [];
  removedUrls = [];
  const box = $('existingImgs');
  if (box) box.innerHTML = '';
  const form = $('productForm');
  if (form) form.reset();
  const stock = $('pStock');
  if (stock) stock.value = 0;
  const submitBtn = $('productSubmitBtn');
  if (submitBtn) submitBtn.innerHTML = '<i class="bi bi-plus-circle me-1"></i>添加产品';
  const cancelBtn = $('cancelEditBtn');
  if (cancelBtn) cancelBtn.style.display = 'none';
  const titleEl = $('productFormTitle');
  if (titleEl) titleEl.textContent = '添加产品';
  const tip = $('productFormTip');
  if (tip) tip.textContent = '';
  const cpy = $('productCopyBtn');
  if (cpy) cpy.classList.add('d-none');
  if (productRteInited) setRteHtml('pRte', '');
  if ($('pMetaTitle')) $('pMetaTitle').value = '';
  if ($('pMetaDesc')) $('pMetaDesc').value = '';
  updateMetaCounts();
}

$('productForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const nameVal = $('pName').value.trim();
  if (!nameVal) {
    alert('请填写产品名称');
    $('pName').focus();
    return;
  }
  if (productRteInited && $('pRte')) {
    $('pDesc').value = $('pRte').innerHTML;
  }
  const fd = new FormData();
  fd.append('name', nameVal);
  fd.append('price', $('pPrice').value.trim());
  fd.append('spec', $('pSpec').value.trim());
  fd.append('sku', $('pSku').value.trim());
  fd.append('model', $('pModel').value.trim());
  fd.append('category', $('pCategory').value.trim());
  fd.append('stock', $('pStock').value);
  fd.append('description', $('pDesc').value || '');
  fd.append('product_video', $('pVideo').value.trim());
  fd.append('meta_title', ($('pMetaTitle') ? $('pMetaTitle').value.trim() : ''));
  fd.append('meta_description', ($('pMetaDesc') ? $('pMetaDesc').value.trim() : ''));
  const files = $('pImg').files;
  for (const f of files) fd.append('imgs', f);
  if (imgUrls.length) fd.append('images_order', JSON.stringify(imgUrls));
  if (removedUrls.length) fd.append('removed', JSON.stringify(removedUrls));
  const submitBtn = $('productSubmitBtn');
  if (submitBtn) { submitBtn.disabled = true; submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>保存中...'; }
  try {
    if (editingProductId) {
      await api('/api/products/' + editingProductId, { method: 'PUT', body: fd });
    } else {
      await api('/api/products', { method: 'POST', body: fd });
    }
    cancelProductForm();
    loadProducts();
    loadStats();
    if (typeof showPanel === 'function') showPanel('sec-product');
  } catch (err) {
    alert(err.message);
  } finally {
    if (submitBtn) { submitBtn.disabled = false; submitBtn.innerHTML = '<i class="bi bi-plus-circle me-1"></i>添加产品'; }
  }
});

function delProduct(id) {
  if (!confirm('确定删除该产品？')) return;
  api('/api/products/' + id, { method: 'DELETE' }).then(() => { loadProducts(); loadStats(); }).catch(e => alert(e.message));
}

/* ===== 产品分类管理（下拉选项 + 后台分类面板共用） ===== */
function loadCategoryOptions(keepVal) {
  const sel = $('pCategory');
  if (!sel) return Promise.resolve();
  const cur = (keepVal !== undefined && keepVal !== null) ? String(keepVal) : (sel.value || '');
  return api('/api/categories').then(list => {
    const names = (list || []).map(c => c.name);
    sel.innerHTML = '<option value="">未分类</option>' +
      list.map(c => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join('');
    if (cur) {
      if (names.indexOf(cur) >= 0) { sel.value = cur; }
      else {
        const o = document.createElement('option');
        o.value = cur; o.textContent = cur;
        sel.appendChild(o);
        sel.value = cur;
      }
    }
  }).catch(() => {});
}

function quickAddCategory() {
  const name = prompt('新分类名称（添加后可在下方下拉中选择）：');
  if (!name) return;
  api('/api/categories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name.trim() })
  }).then(() => {
    loadCategoryOptions('');
    loadCategories();
  }).catch(e => alert(e.message));
}

let currentCatIds = [];

function loadCategories() {
  api('/api/categories').then(list => {
    currentCatIds = list.map(c => c.id);
    const tb = $('catTable');
    if (!tb) return;
    tb.innerHTML = list.length ? list.map((c, i) =>
      `<tr>
        <td class="text-center text-secondary">${i + 1}</td>
        <td>${esc(c.name)}</td>
        <td>${c.product_count || 0}</td>
        <td class="text-end text-nowrap">
          <button class="btn btn-sm btn-outline-secondary py-0 px-1" title="上移" onclick="catMove(${c.id}, -1)"><i class="bi bi-arrow-up"></i></button>
          <button class="btn btn-sm btn-outline-secondary py-0 px-1" title="下移" onclick="catMove(${c.id}, 1)"><i class="bi bi-arrow-down"></i></button>
          <button class="btn btn-sm btn-outline-primary" onclick="catRename(${c.id}, ${JSON.stringify(c.name)})">改名</button>
          <button class="btn btn-sm btn-outline-danger" onclick="catDelete(${c.id})">删除</button>
        </td>
      </tr>`).join('')
      : '<tr><td colspan="4"><div class="friendly-empty sm"><i class="bi bi-tags"></i><div><b>还没有分类</b><p>在上方输入名称添加分类；旧产品用过的分类会自动补入这里。</p></div></div></td></tr>';
    const tip = $('catCountTip');
    if (tip) tip.textContent = '当前共 ' + list.length + ' 个分类';
  }).catch(e => alert(e.message));
}

function catMove(id, dir) {
  const i = currentCatIds.indexOf(id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= currentCatIds.length) return;
  const arr = currentCatIds.slice();
  arr.splice(i, 1); arr.splice(j, 0, id);
  api('/api/categories/reorder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids: arr })
  }).then(() => { loadCategories(); loadCategoryOptions(''); }).catch(e => alert(e.message));
}

function catRename(id, oldName) {
  const name = prompt('新的分类名称：', oldName || '');
  if (!name || name.trim() === oldName) return;
  api('/api/categories/' + id, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name.trim() })
  }).then(() => { loadCategories(); loadCategoryOptions(''); }).catch(e => alert(e.message));
}

function catDelete(id) {
  if (!confirm('删除该分类将只取消产品上的分类标记，不会删除任何产品。确定删除？')) return;
  api('/api/categories/' + id, { method: 'DELETE' })
    .then(() => { loadCategories(); loadCategoryOptions(''); loadProducts(); })
    .catch(e => alert(e.message));
}

const catFormEl = $('catAddForm');
if (catFormEl) catFormEl.addEventListener('submit', (e) => {
  e.preventDefault();
  const input = $('catNameInput');
  const name = input.value.trim();
  if (!name) return alert('请输入分类名称');
  api('/api/categories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name })
  }).then(() => { input.value = ''; loadCategories(); loadCategoryOptions(''); })
    .catch(err => alert(err.message));
});

/* ===== 数据备份 / 恢复 ===== */
function fmtSize(b) {
  if (!b && b !== 0) return '';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1048576).toFixed(2) + ' MB';
}

function createBackup() {
  const btn = $('backupCreateBtn');
  const tip = $('backupTip');
  if (btn) { btn.disabled = true; }
  if (tip) tip.textContent = '正在打包，请稍候...';
  api('/api/backup/create', { method: 'POST' }).then(d => {
    if (tip) tip.textContent = '✅ 已生成 ' + d.file;
    loadBackups();
    const a = document.createElement('a');
    a.href = '/api/backup/download/' + encodeURIComponent(d.file);
    document.body.appendChild(a);
    a.click();
    a.remove();
  }).catch(e => {
    if (tip) tip.textContent = '';
    alert(e.message);
  }).finally(() => { if (btn) btn.disabled = false; });
}

function downloadBackup(name) {
  const a = document.createElement('a');
  a.href = '/api/backup/download/' + encodeURIComponent(name);
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function restoreBackup() {
  const input = $('backupFileInput');
  if (!input || !input.files.length) return alert('请先选择要还原的 .zip 备份文件');
  if (!confirm('导入将覆盖当前数据与图片。系统会先自动备份，成功后才还原；选错可从备份记录找回。继续？')) return;
  const fd = new FormData();
  fd.append('file', input.files[0]);
  const btn = document.querySelector('[onclick="restoreBackup()"]');
  if (btn) { btn.disabled = true; btn.innerHTML = '还原中...'; }
  api('/api/backup/restore', { method: 'POST', body: fd }).then(d => {
    input.value = '';
    alert('✅ ' + (d.msg || '还原成功，当前数据已替换为备份内容'));
    location.reload();
  }).catch(e => alert(e.message)).finally(() => {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>开始还原'; }
  });
}

function loadBackups() {
  api('/api/backup/list').then(list => {
    const tb = $('backupTable');
    if (!tb) return;
    tb.innerHTML = list.length ? list.map(b =>
      `<tr>
        <td>${esc(b.file)}</td>
        <td>${fmtSize(b.size)}</td>
        <td>${esc(b.mtime)}</td>
        <td class="text-end"><button class="btn btn-sm btn-outline-primary" onclick="downloadBackup('${esc(b.file)}')">下载</button></td>
      </tr>`).join('')
      : '<tr><td colspan="4"><div class="friendly-empty sm"><i class="bi bi-database-down"></i><div><b>还没有备份记录</b><p>点击「立即备份并下载」生成第一份备份，多备份以防数据丢失。</p></div></div></td></tr>';
  }).catch(e => alert(e.message));
}


$('layoutForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const ok = await saveConfig({ site_layout: $('siteLayoutSelect').value });
  if (ok) {
    currentSiteLayout = $('siteLayoutSelect').value;
    $('layoutSaveTip').textContent = '✅ 已保存，所有产品详情页将统一使用该风格';
    setTimeout(() => { $('layoutSaveTip').textContent = ''; }, 2500);
  }
});

/* ===== 实时预览 ===== */
const previewModal = new bootstrap.Modal($('previewModal'));

function currentSiteName() {
  return sessionStorage.getItem('site_name') || 'My Export Site';
}

function previewUrl() {
  return '/api/preview?_t=' + Date.now() + '&site_name=' + encodeURIComponent(currentSiteName())
    + '&template=' + encodeURIComponent(currentTemplate);
}

function openPreview() {
  $('previewFrame').src = previewUrl();
  setPreview('desktop');
  previewModal.show();
}

function setPreview(mode) {
  const f = $('previewFrame');
  if (mode === 'mobile') {
    f.style.width = '375px';
    f.style.height = '700px';
  } else {
    f.style.width = '1280px';
    f.style.height = '720px';
  }
}

/* ===== 一键生成与部署 ===== */
async function deployAll() {
  const repo = $('repoName').value.trim();
  if (!repo) return alert('请先填写 GitHub 仓库名（仓库不存在时会自动创建）');
  if (!/^[A-Za-z0-9_.-]+$/.test(repo)) {
    $('repoName').focus();
    $('repoName').select();
    return alert('仓库名格式不正确：只能包含字母、数字、-、_、.。\n请只填写仓库名本身（如 my-export-site），不要粘贴其他文字。');
  }
  const name = $('siteName').value.trim() || 'My Export Site';
  sessionStorage.setItem('site_name', name);

  const btn = $('deployBtn');
  btn.disabled = true;
  $('deployResult').innerHTML = '<div class="alert alert-info py-2 mb-0">⏳ 正在生成网站...</div>';
  try {
    await api('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ site_name: name, template: currentTemplate, repo })
    });
    $('deployResult').innerHTML = '<div class="alert alert-info py-2 mb-0">⏳ 网站已生成，正在推送到 GitHub...</div>';
    const res = await api('/api/deploy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo })
    });
    const pagesHtml = res.pages
      ? `<div class="small ${res.pages.ok ? 'text-success' : 'text-warning'} mt-1">${esc(res.pages.msg)}</div>`
      : '<div class="small text-muted mt-1">首次访问 GitHub Pages 可能需要等待 1-2 分钟生效</div>';
    const siteUrl = res.url;
    let extra = '';
    if (res.domain) {
      extra += `<div class="small text-info mt-1">🌐 已绑定自定义域名 <b>${esc(res.domain)}</b>：请把该域名的 DNS（CNAME 或 A 记录）指向 GitHub Pages，生效后即可用此域名访问。</div>`;
    }
    if (res.notice) {
      extra += `<div class="small text-secondary mt-1">🔄 ${esc(res.notice)}</div>`;
    }
    $('deployResult').innerHTML =
      `<div class="alert alert-success mb-0">📦 文件上传完成，正在等待上线。<br>网站地址：<a href="${esc(siteUrl)}" target="_blank">${esc(siteUrl)}</a>${pagesHtml}${extra}
       <div class="small text-muted mt-2" id="siteCheckTip">⏳ 正在自动检测站点上线状态（GitHub Pages 首次发布约需 1-2 分钟）...</div></div>`;
    // 自动轮询检测站点是否可访问，免去手动去 GitHub 仓库确认
    let tries = 0;
    const maxTries = 24; // 最多检测约 4 分钟
    (function pollSite() {
      api('/api/check_site', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: siteUrl, build_id: res.build_id })
      }).then(r => {
        tries++;
        if (r.ok) {
          $('siteCheckTip').innerHTML = `<div class="small text-success mt-1">✅ 本次更新已上线，点击上方链接即可访问</div>`;
        } else if (tries < maxTries) {
          setTimeout(pollSite, 10000);
        } else {
          $('siteCheckTip').innerHTML = `<div class="small text-muted mt-1">检测超时。GitHub Pages 首次发布有时需要更久，稍后直接访问上方链接即可，通常无需手动操作。</div>`;
        }
      }).catch(() => {
        tries++;
        if (tries < maxTries) setTimeout(pollSite, 10000);
        else $('siteCheckTip').innerHTML = `<div class="small text-muted mt-1">检测中断。稍后直接访问上方链接即可。</div>`;
      });
    })();
  } catch (e) {
    const msg = esc(e.message || '部署失败').replace(/\n/g, '<br>');
    $('deployResult').innerHTML = `<div class="alert alert-danger py-2 mb-0">❌ ${msg}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 一键生成外贸网站并上传到GitHub';
  }
}

/* ===== 板块化建站管理 ===== */
let sectionTypes = [];
let sectionModal = null;
let editingSectionId = null;

const SECTION_FIELDS = {
  hero: [],
  products: [
    { key: 'limit', label: '展示数量（0 为全部）', type: 'number', placeholder: '0' },
    { key: 'subtitle', label: '副标题', type: 'text', placeholder: 'High-quality products...' }
  ],
  about: [
    { key: 'text', label: '公司介绍文字', type: 'textarea', placeholder: 'Write about your company...' },
    { key: 'image', label: '图片路径', type: 'text', placeholder: '/uploads/xxx.jpg' }
  ],
  why_us: { list: true, itemFields: [{ key: 'icon', label: '图标' }, { key: 'title', label: '标题' }, { key: 'text', label: '说明' }], defaultCount: 4 },
  team: { list: true, itemFields: [{ key: 'photo', label: '头像路径' }, { key: 'name', label: '姓名' }, { key: 'role', label: '职位' }, { key: 'text', label: '简介' }], defaultCount: 3 },
  cases: { list: true, itemFields: [{ key: 'image', label: '图片路径' }, { key: 'title', label: '标题' }, { key: 'text', label: '描述' }], defaultCount: 3 },
  news: { list: true, itemFields: [{ key: 'title', label: '标题' }, { key: 'date', label: '日期' }, { key: 'text', label: '内容' }], defaultCount: 3 },
  faq: { list: true, itemFields: [{ key: 'q', label: '问题' }, { key: 'a', label: '回答' }], defaultCount: 4 },
  testimonials: { list: true, itemFields: [{ key: 'name', label: '客户名' }, { key: 'role', label: '国家/职位' }, { key: 'text', label: '评价内容' }], defaultCount: 3 },
  stats: { list: true, itemFields: [{ key: 'value', label: '数字（如 5000+）' }, { key: 'label', label: '说明' }], defaultCount: 4 },
  partners: { list: true, itemFields: [{ key: 'logo', label: 'Logo 路径' }, { key: 'name', label: '名称' }, { key: 'link', label: '外链 URL（可选）' }], defaultCount: 4 },
  payments: [{ key: 'text', label: '说明文字', type: 'textarea', placeholder: 'We support multiple secure payment methods...' }],
  contacts: [],
  trust: { list: true, itemFields: [{ key: 'icon', label: '图标' }, { key: 'title', label: '标题' }, { key: 'text', label: '说明' }], defaultCount: 4 },
  video: [{ key: 'url', label: '视频 URL（YouTube/外链，自动转嵌入）', type: 'text', placeholder: 'https://www.youtube.com/watch?v=xxx' }, { key: 'mp4', label: '或填本地/直链 MP4（优先）', type: 'text', placeholder: 'uploads/videos/demo.mp4' }, { key: 'poster', label: '视频封面图路径（可选）', type: 'text', placeholder: 'uploads/videos/demo-cover.jpg' }, { key: 'video_title', label: '视频标题', type: 'text', placeholder: 'Company Video' }],
  map: [{ key: 'address', label: '地址（自动生成 Google 地图）', type: 'text', placeholder: "No.88, Bao'an District, Shenzhen" }, { key: 'embed', label: '或直接填地图嵌入 URL', type: 'text', placeholder: 'https://maps.google.com/maps?q=...&output=embed' }],
  friend_links: [],
  spider_pool: { list: true, itemFields: [{ key: 'name', label: '锚文本' }, { key: 'url', label: '外链 URL' }], defaultCount: 5 },
  certificates: { list: true, itemFields: [{ key: 'image', label: '证书图片路径' }, { key: 'title', label: '证书/专利名称' }, { key: 'text', label: '说明' }], defaultCount: 3 },
  cta: [{ key: 'subtitle', label: '副标题', type: 'text', placeholder: 'Get a free quote within 24 hours...' }, { key: 'btn_text', label: '按钮文字', type: 'text', placeholder: 'Get a Free Quote' }, { key: 'btn_url', label: '按钮链接（留空跳转联系区）', type: 'text', placeholder: '#contact 或 https://...' }]
};

function sectionTypeInfo(id) {
  return sectionTypes.find(t => t.id === id) || { name: id, desc: '' };
}

function loadSectionTypes() {
  api('/api/sections/types').then(list => {
    sectionTypes = list;
    const sel = $('sectionTypeSelect');
    sel.innerHTML = list.map(t => `<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('');
    sel.onchange = () => {
      const info = sectionTypeInfo(sel.value);
      $('sectionTypeDesc').textContent = info.desc || '';
    };
    sel.onchange();
  }).catch(e => alert(e.message));
}

function loadSections() {
  api('/api/sections').then(list => {
    const tb = $('sectionTable');
    tb.innerHTML = list.length ? list.map((s, i) =>
      `<tr>
        <td><span class="text-muted small">#${i + 1}</span></td>
        <td>${esc(sectionTypeInfo(s.section_type).name || s.section_type)}</td>
        <td>${esc(s.title || '')}</td>
        <td>${s.enabled ? '<span class="text-success">启用</span>' : '<span class="text-muted">停用</span>'}</td>
        <td class="text-end text-nowrap">
          <button class="btn btn-sm btn-outline-secondary" onclick="moveSection(${s.id},'up')" title="上移">↑</button>
          <button class="btn btn-sm btn-outline-secondary" onclick="moveSection(${s.id},'down')" title="下移">↓</button>
          <button class="btn btn-sm btn-outline-primary" onclick="editSection(${s.id})">配置</button>
          <button class="btn btn-sm btn-outline-secondary" onclick="toggleSection(${s.id},${s.enabled ? 0 : 1})">${s.enabled ? '停用' : '启用'}</button>
          <button class="btn btn-sm btn-outline-danger" onclick="delSection(${s.id})">删除</button>
        </td>
      </tr>`).join('')
      : '<tr><td colspan="5"><div class="friendly-empty"><i class="bi bi-grid-3x3-gap"></i><div><b>首页还是空的</b><p>在上方选择板块类型并点「添加板块」，一步步搭出首页内容。</p></div><button class="btn btn-sm btn-primary" onclick="addSection()"><i class="bi bi-plus-lg me-1"></i>添加板块</button></div></td></tr>';
  }).catch(e => alert(e.message));
}

function addSection() {
  const stype = $('sectionTypeSelect').value;
  const title = $('sectionTitle').value.trim();
  api('/api/sections', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ section_type: stype, title, enabled: true })
  }).then(() => {
    $('sectionTitle').value = '';
    loadSections();
  }).catch(e => alert(e.message));
}

function moveSection(id, direction) {
  api('/api/sections/' + id + '/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction })
  }).then(loadSections).catch(e => alert(e.message));
}

function toggleSection(id, enabled) {
  api('/api/sections/' + id, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled })
  }).then(loadSections).catch(e => alert(e.message));
}

function delSection(id) {
  if (!confirm('确定删除该板块？')) return;
  api('/api/sections/' + id, { method: 'DELETE' }).then(loadSections).catch(e => alert(e.message));
}

function sectionFieldsHtml(fields, content) {
  if (fields.list) {
    const items = content.items || [];
    const rows = items.map((it, idx) => listItemHtml(fields.itemFields, it, idx)).join('')
      || new Array(fields.defaultCount).fill(0).map((_, i) => listItemHtml(fields.itemFields, {}, i)).join('');
    return `<div class="list-editor">${rows}
      <button type="button" class="btn btn-sm btn-outline-success" onclick="addListItem(this, '${esc(JSON.stringify(fields.itemFields))}')">＋ 添加一项</button></div>`;
  }
  return fields.map(f => {
    const v = content[f.key] != null ? content[f.key] : '';
    if (f.type === 'textarea') {
      return `<div class="mb-2"><label class="form-label small mb-1">${esc(f.label)}</label><textarea class="form-control field-${esc(f.key)}" rows="2" placeholder="${esc(f.placeholder || '')}">${esc(v)}</textarea></div>`;
    }
    return `<div class="mb-2"><label class="form-label small mb-1">${esc(f.label)}</label><input class="form-control field-${esc(f.key)}" type="${f.type === 'number' ? 'number' : 'text'}" value="${esc(v)}" placeholder="${esc(f.placeholder || '')}"></div>`;
  }).join('');
}

function listItemHtml(itemFields, item, idx) {
  return `<div class="list-item card card-body mb-2 p-2">
    <div class="row g-2 align-items-center">
      ${itemFields.map(f => `<div class="col"><input class="form-control form-control-sm it-${esc(f.key)}" value="${esc(item[f.key] || '')}" placeholder="${esc(f.label)}"></div>`).join('')}
      <div class="col-auto"><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('.list-item').remove()">删除</button></div>
    </div></div>`;
}

function addListItem(btn, fieldsJson) {
  const fields = JSON.parse(fieldsJson);
  const div = document.createElement('div');
  div.innerHTML = listItemHtml(fields, {}, 0);
  btn.closest('.list-editor').insertBefore(div.firstChild, btn);
}

function editSection(id) {
  editingSectionId = id;
  api('/api/sections').then(list => {
    const s = list.find(x => x.id === id);
    if (!s) return alert('板块不存在');
    const info = sectionTypeInfo(s.section_type);
    const fields = SECTION_FIELDS[s.section_type] || [];
    $('sectionModalTitle').textContent = '配置板块：' + (info.name || s.section_type);
    const content = s.content || {};
    $('sectionModalBody').innerHTML =
      `<div class="alert alert-light small mb-3"><b>这个部分是做什么的：</b>${esc(info.desc || '')}</div>
       <div class="mb-2"><label class="form-label small mb-1">板块标题</label><input id="secTitleInput" class="form-control" value="${esc(s.title || '')}"></div>
       <input type="hidden" id="secTypeInput" value="${esc(s.section_type)}">
       ${sectionFieldsHtml(fields, content)}`;
    if (!sectionModal) sectionModal = new bootstrap.Modal($('sectionModal'));
    sectionModal.show();
  }).catch(e => alert(e.message));
}

function collectSectionContent() {
  const stype = $('secTypeInput').value;
  const fields = SECTION_FIELDS[stype] || [];
  const content = {};
  if (fields.list) {
    content.items = Array.from(document.querySelectorAll('#sectionModalBody .list-item')).map(row => {
      const item = {};
      fields.itemFields.forEach(f => { item[f.key] = row.querySelector('.it-' + f.key) ? row.querySelector('.it-' + f.key).value.trim() : ''; });
      return item;
    }).filter(it => Object.values(it).some(v => v));
  } else {
    fields.forEach(f => {
      const el = document.querySelector('#sectionModalBody .field-' + f.key);
      if (el) content[f.key] = el.value.trim();
    });
  }
  return content;
}

function saveSection() {
  if (editingSectionId == null) return;
  api('/api/sections/' + editingSectionId, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: $('secTitleInput').value.trim(),
      content: collectSectionContent()
    })
  }).then(() => {
    if (sectionModal) sectionModal.hide();
    loadSections();
  }).catch(e => alert(e.message));
}

/* ===== 页面管理（Word 式富文本编辑，无需代码） ===== */
let editingPageId = null;
let pageModal = null;

function loadPages() {
  api('/api/pages').then(list => {
    const tb = $('pageTable');
    tb.innerHTML = list.length ? list.map(p =>
      `<tr>
        <td>${esc(p.title)}</td>
        <td><code>${esc(p.slug)}</code></td>
        <td>${p.enabled ? '<span class="text-success">显示</span>' : '<span class="text-muted">隐藏</span>'}</td>
        <td class="text-end text-nowrap">
          <button class="btn btn-sm btn-outline-primary" onclick="editPage(${p.id})">编辑</button>
          <button class="btn btn-sm btn-outline-secondary" onclick="togglePage(${p.id},${p.enabled ? 0 : 1})">${p.enabled ? '隐藏' : '显示'}</button>
          <button class="btn btn-sm btn-outline-danger" onclick="delPage(${p.id})">删除</button>
        </td>
      </tr>`).join('')
      : '<tr><td colspan="4"><div class="friendly-empty"><i class="bi bi-file-earmark-text"></i><div><b>还没有自定义页面</b><p>可添加「关于我们」「服务介绍」等独立页面，启用后会自动出现在网站导航。</p></div><button class="btn btn-sm btn-primary" onclick="addPage()"><i class="bi bi-plus-lg me-1"></i>新增页面</button></div></td></tr>';
  }).catch(e => alert(e.message));
}

function addPage() {
  const title = $('pageTitle').value.trim();
  const slug = $('pageSlug').value.trim();
  if (!title) return alert('请填写页面标题');
  const templateSel = $('pageTemplate');
  const template = templateSel ? templateSel.value : '';
  api('/api/pages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, slug, template })
  }).then(() => {
    $('pageTitle').value = '';
    $('pageSlug').value = '';
    if (templateSel) templateSel.value = '';
    loadPages();
  }).catch(e => alert(e.message));
}

function editPage(id) {
  editingPageId = id;
  api('/api/pages').then(list => {
    const p = list.find(x => x.id === id);
    if (!p) return alert('页面不存在');
    $('pageModalBody').innerHTML =
      `<div class="row g-2 mb-2">
        <div class="col-md-6"><label class="form-label small mb-1">页面标题</label><input id="pgTitle" class="form-control" value="${esc(p.title)}"></div>
        <div class="col-md-6"><label class="form-label small mb-1">网址标识（小写字母数字连字符，留空自动生成）</label><input id="pgSlug" class="form-control" value="${esc(p.slug)}"></div>
      </div>
      <div class="mb-2">
        <label class="form-label small mb-1">页面内容（像 Word 一样直接编辑，无需接触代码）</label>
        <div class="rte-wrap">
          <div class="rte-toolbar" id="pgRteBar"></div>
          <div id="pgRte" class="rte-box" contenteditable="true" data-placeholder="在这里编写页面内容：文字、大小、加粗、对齐、标题、列表、链接、图片都支持；点击图片可选中删除"></div>
        </div>
        <input type="hidden" id="pgContent">
      </div>
      <hr>
      <div class="row g-2">
        <div class="col-md-4"><label class="form-label small mb-1">SEO Title</label><input id="pgSeoTitle" class="form-control" value="${esc(p.seo_title || '')}"></div>
        <div class="col-md-4"><label class="form-label small mb-1">SEO Description</label><input id="pgSeoDesc" class="form-control" value="${esc(p.seo_description || '')}"></div>
        <div class="col-md-4"><label class="form-label small mb-1">SEO Keywords</label><input id="pgSeoKeywords" class="form-control" value="${esc(p.seo_keywords || '')}"></div>
      </div>`;
    initRte('pgRte', 'pgContent', 'pgRteBar');
    setRteHtml('pgRte', mdToHtml(p.content || ''));
    if (!pageModal) pageModal = new bootstrap.Modal($('pageModal'));
    pageModal.show();
  }).catch(e => alert(e.message));
}

function savePage() {
  if (editingPageId == null) return;
  const box = $('pgRte');
  if (box) $('pgContent').value = box.innerHTML;
  api('/api/pages/' + editingPageId, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: $('pgTitle').value.trim(),
      slug: $('pgSlug').value.trim(),
      content: $('pgContent').value,
      seo_title: $('pgSeoTitle').value.trim(),
      seo_description: $('pgSeoDesc').value.trim(),
      seo_keywords: $('pgSeoKeywords').value.trim()
    })
  }).then(() => {
    if (pageModal) pageModal.hide();
    loadPages();
  }).catch(e => alert(e.message));
}

function togglePage(id, enabled) {
  api('/api/pages/' + id, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled })
  }).then(loadPages).catch(e => alert(e.message));
}

function delPage(id) {
  if (!confirm('确定删除该页面？')) return;
  api('/api/pages/' + id, { method: 'DELETE' }).then(loadPages).catch(e => alert(e.message));
}


function loadFriendLinks() {
  api('/api/friend_links').then(list => {
    const tb = $('friendLinkTable');
    tb.innerHTML = list.length ? list.map(l =>
      `<tr>
        <td>${esc(l.name)}</td>
        <td><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.url)}</a></td>
        <td>${l.nofollow ? '<span class="text-success">nofollow</span>' : '<span class="text-muted">follow</span>'}</td>
        <td class="text-end text-nowrap">
          <button class="btn btn-sm btn-outline-secondary" onclick="toggleFl(${l.id},${l.nofollow ? 0 : 1})">${l.nofollow ? '改 follow' : '改 nofollow'}</button>
          <button class="btn btn-sm btn-outline-danger" onclick="delFl(${l.id})">删除</button>
        </td>
      </tr>`).join('')
      : '<tr><td colspan="4"><div class="friendly-empty"><i class="bi bi-link-45deg"></i><div><b>还没有友情链接</b><p>在上方填网站名称和网址，点「添加友链」，页脚即会展示合作伙伴。</p></div></div></td></tr>';
  }).catch(e => alert(e.message));
}

$('friendLinkForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = $('flName').value.trim();
  const url = $('flUrl').value.trim();
  if (!name || !url) return alert('请填写名称与 URL');
  try {
    await api('/api/friend_links', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, url, nofollow: true })
    });
    $('flName').value = '';
    $('flUrl').value = '';
    loadFriendLinks();
  } catch (e) { alert(e.message); }
});

function toggleFl(id, nofollow) {
  api('/api/friend_links/' + id, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nofollow })
  }).then(loadFriendLinks).catch(e => alert(e.message));
}

function delFl(id) {
  if (!confirm('确定删除该友链？')) return;
  api('/api/friend_links/' + id, { method: 'DELETE' }).then(loadFriendLinks).catch(e => alert(e.message));
}

loadConfig();
loadPayBrands();
loadPayIcons();
loadTemplates();
loadLanguages();
loadStats();
loadSiteLayouts();
loadBanners();
loadContacts();
loadProducts();
loadCategoryOptions('');
loadCategories();
loadBackups();
loadSectionTypes();
loadSections();
loadPages();
loadFriendLinks();
loadTutorial();

/* ===== 后台导航：面板化切换 + 顶部复位 ===== */
const SEC_ORDER = ['sec-stats', 'sec-template', 'sec-company', 'sec-brand', 'sec-product', 'sec-collection', 'sec-categories', 'sec-sections', 'sec-seo', 'sec-growth', 'sec-friendlinks', 'sec-pay', 'sec-backup', 'sec-deploy', 'sec-tutorial'];

/* 面板 → 分组/页面名映射（用于顶部标题与面包屑） */
const SEC_META = {
  'sec-stats': { group: '开始', page: '站点概览', icon: 'bi-speedometer2' },
  'sec-template': { group: '建站', page: '模板与语言', icon: 'bi-palette' },
  'sec-sections': { group: '建站', page: '板块与页面', icon: 'bi-grid-1x2' },
  'sec-product': { group: '内容', page: '产品管理', icon: 'bi-box-seam' },
  'sec-collection': { group: '内容', page: '商品采集与翻译', icon: 'bi-box-arrow-in-down' },
  'sec-categories': { group: '内容', page: '分类管理', icon: 'bi-tags' },
  'sec-company': { group: '内容', page: '公司设置', icon: 'bi-buildings' },
  'sec-brand': { group: '内容', page: '品牌与素材', icon: 'bi-image' },
  'sec-seo': { group: '推广', page: 'SEO 优化', icon: 'bi-search' },
  'sec-growth': { group: '推广', page: '推广工具箱', icon: 'bi-tools' },
  'sec-friendlinks': { group: '推广', page: '友情链接', icon: 'bi-link-45deg' },
  'sec-pay': { group: '推广', page: '支付配置', icon: 'bi-credit-card', desc: '自选全球移动/网络支付渠道（PayPal/Alipay/微信/银行T/T 等数十种），像联系方式一样可添加多条' },
  'sec-backup': { group: '系统', page: '数据备份', icon: 'bi-database-down' },
  'sec-deploy': { group: '系统', page: '网站部署', icon: 'bi-rocket-takeoff' },
  'sec-tutorial': { group: '系统', page: '使用教程', icon: 'bi-journal-bookmark' }
};

/* 新手引导文案：这页做什么 + 最简单三步 */
const GUIDE_COPY = {
  'sec-stats': { title: '查看网站整体情况', steps: ['看左边三张卡片了解网站数据', '需要改内容就点左侧菜单去对应页面', '想马上上线？去「网站部署」点一键生成'] },
  'sec-template': { title: '选择网站长相和语言', steps: ['选一套喜欢的模板，右上角可预览', '选择网站主要语言（英文/中文/日语等）', '点「保存」，网站文字会跟着变'] },
  'sec-sections': { title: '把首页内容一块块搭起来', steps: ['上面加板块：选类型 → 填标题 → 点「添加板块」', '点「配置」填写内容，拖动或↑↓调顺序', '「停用」可临时隐藏某块，「删除」前会再次确认'] },
  'sec-company': { title: '填写公司介绍，客户更信任你', steps: ['填公司名称、简介、Logo', '填成立年份、规模等信息', '点「保存」，网站页脚与联系区会同步更新'] },
  'sec-brand': { title: '准备网站的图片素材', steps: ['上传横幅大图和产品主图', '上传后可在页面下方预览效果', '图片会按尺寸提示自动展示，无需手动改代码'] },
  'sec-product': { title: '把要卖的产品加进网站', steps: ['点右上角「＋ 新增产品」', '填名称、价格，上传图片，选分类', '点保存。首页和产品详情页会自动出现'] },
  'sec-collection': { title: '把来源商品整理成自己的产品草稿', steps: ['粘贴商品链接，或用关键词、店铺链接查找商品', '检查采集的名称、图片和 SKU；需要译文时准备本地 AI', '选择语言并检查译文，再加入产品管理'] },
  'sec-categories': { title: '把产品分门别类，方便客户浏览', steps: ['上面输入分类名称，点「添加分类」', '可重命名、上下移动、删除', '添加/编辑产品时即可直接选用'] },
  'sec-seo': { title: '让 Google 等搜索引擎更容易找到你', steps: ['填公司一句话介绍和核心卖点（AI GEO 用）', '点「获取关键词建议」挑选行业词', '点「开始自检」，按绿色清单逐项完成即可'] },
  'sec-growth': { title: '配置网站推广工具和主题页面', steps: ['填写内链或隐藏内容，分别控制启用开关', '保存设置；主题落地页先生成草稿再检查', '重新生成并发布后生效，效果需要实际观察'] },
  'sec-friendlinks': { title: '在网站底部展示合作伙伴链接', steps: ['上方填对方网站名称和网址', '点「添加友链」', '想不被搜索引擎跟踪就保持 nofollow'] },
  'sec-pay': { title: '展示你支持的收款方式，客户更放心', steps: ['从清单添加 PayPal / Stripe / 银行转账等渠道（收款账号可不填）', '可选：上传渠道自定义图标，或留空用内置品牌徽章', '保存后产品卡片和详情页自动显示「We accept」徽章墙，客户无法在站内直接付款'] },
  'sec-backup': { title: '给网站数据上「保险」', steps: ['点「立即备份」下载 zip 备份文件', '建议每次大改前备份一次', '需要还原时选择备份文件一键导入'] },
  'sec-deploy': { title: '一键把网站生成/发布出去', steps: ['先点「生成网站」在本地预览效果', '没问题再点「部署上线」', '部署成功后网站链接立即生效'] },
  'sec-tutorial': { title: '从零开始的保姆级教程', steps: ['跟着左侧目录一步步操作', '每步都有截图和解释', '看不懂随时回到对应管理页面重试'] }
};

function updateCrumb(id) {
  const meta = SEC_META[id] || { group: '开始', page: '管理后台', icon: 'bi-gear' };
  const h = $('pageHeaderTitle');
  if (h) h.innerHTML = `<i class="bi ${meta.icon} me-2 text-primary"></i>${esc(meta.page)}`;
  const g = $('crumbGroup');
  if (g) g.textContent = meta.group;
  const p = $('crumbPage');
  if (p) p.textContent = meta.page;
}

/* 新手引导条：注入每个面板 + 可关闭记忆 */
function mountGuides() {
  Object.keys(GUIDE_COPY).forEach(id => {
    const panel = $(id);
    if (!panel) return;
    const card = panel.querySelector('.card');
    if (!card) return;
    const body = card.querySelector('.card-body');
    if (!body || card.querySelector('.guide-bar')) return;
    const c = GUIDE_COPY[id];
    const bar = document.createElement('div');
    bar.className = 'guide-bar';
    bar.id = 'guide-' + id;
    bar.innerHTML =
      '<i class="guide-ico bi bi-lightbulb"></i>' +
      '<div class="guide-main"><div class="guide-title">这一页做什么？<b>' + esc(c.title) + '</b></div>' +
      '<div class="guide-steps">' + c.steps.map((s, i) => '<span class="guide-step"><b>' + (i + 1) + '</b>' + esc(s) + '</span>').join('') + '</div></div>' +
      '<button type="button" class="btn-close guide-close" aria-label="关闭引导" title="关闭引导，本页不再显示"></button>';
    if (localStorage.getItem('guideHide_' + id) === '1') bar.classList.add('guide-hidden');
    card.insertBefore(bar, body);
    bar.querySelector('.guide-close').addEventListener('click', function () {
      localStorage.setItem('guideHide_' + id, '1');
      bar.classList.add('guide-hidden');
    });
  });
}

function showPanel(id) {
  if (!id) return;
  SEC_ORDER.forEach(k => {
    const el = $(k);
    if (el) el.classList.toggle('d-none', k !== id);
  });
  document.querySelectorAll('.sidebar-menu a[href^="#sec-"]').forEach(a => {
    a.classList.toggle('active', a.getAttribute('href') === '#' + id);
  });
  updateCrumb(id);
  try { history.replaceState(null, '', '#' + id); } catch (e) { /* noop */ }
  window.scrollTo({ top: 0, behavior: 'smooth' });
  const target = $(id);
  if (target) target.scrollIntoView({ block: 'start', behavior: 'smooth' });
}

document.querySelectorAll('.sidebar-menu a[href^="#sec-"]').forEach(a => {
  a.addEventListener('click', (e) => {
    e.preventDefault();
    const id = a.getAttribute('href').replace('#', '');
    showPanel(id);
  });
});

/* ============================================================
   Word 式富文本编辑器（零依赖，contenteditable + execCommand，
   离线可用，无需外网 CDN。数据存 HTML，由后端白名单过滤）
   ============================================================ */
let _rteSeq = 0;

function mdToHtml(src) {
  if (!src) return '';
  const s = String(src);
  // 已是 HTML（含标签）→ 简单清理后直接复用，兼容旧数据
  if (/<(p|div|h[1-6]|ul|ol|li|img|table|blockquote|b|strong|em|i|u|s|a|br|span|font)[\s>/]/i.test(s)) {
    return sanitizeRte(s);
  }
  const lines = s.split(/\r?\n/);
  const out = [];
  let inList = false;
  lines.forEach(raw => {
    const line = raw.trim();
    if (!line) {
      if (inList) { out.push('</ul>'); inList = false; }
      return;
    }
    let m = line.match(/^(#{1,4})\s+(.*)$/);
    if (m) {
      if (inList) { out.push('</ul>'); inList = false; }
      const lv = Math.min(m[1].length + 1, 4);
      out.push('<h' + lv + '>' + inlineMd(m[2]) + '</h' + lv + '>');
      return;
    }
    m = line.match(/^[-*]\s+(.*)$/) || line.match(/^\d+[.、)]\s+(.*)$/);
    if (m) {
      if (!inList) { out.push('<ul>'); inList = true; }
      out.push('<li>' + inlineMd(m[1]) + '</li>');
      return;
    }
    if (inList) { out.push('</ul>'); inList = false; }
    out.push('<p>' + inlineMd(line) + '</p>');
  });
  if (inList) out.push('</ul>');
  return out.join('');
}

function inlineMd(t) {
  return sanitizeRte(esc(t))
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;height:auto;">')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
}

function sanitizeRte(html) {
  // 后端还有白名单过滤；此处仅去掉 script/style 等明显隐患，方便旧数据回显
  return String(html == null ? '' : html)
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/javascript:/gi, '')
    .replace(/onerror|onclick|onload|onmouseover|onchange/gi, '');
}

function setRteHtml(boxId, html) {
  const box = $(boxId);
  if (!box) return;
  box.innerHTML = html || '';
}


function initRte(boxId, hiddenId, barId) {
  const box = $(boxId);
  const bar = $(barId);
  if (!box || !bar) return;
  const seq = ++_rteSeq;
  const fileId = 'rteFile' + seq;
  const popIds = {
    fmt: 'rteFmtPop' + seq,
    font: 'rteFontPop' + seq,
    size: 'rteSizePop' + seq,
    color: 'rteColorPop' + seq,
    bg: 'rteBgPop' + seq
  };
  const FMT_NAMES = { H1: '标题 1', H2: '标题 2', H3: '标题 3', H4: '标题 4', BLOCKQUOTE: '引用' };
  const FMT_KEYS = { '标题 1': 'h1', '标题 2': 'h2', '标题 3': 'h3', '标题 4': 'h4', '引用': 'blockquote', '正文': 'p' };
  const FONT_OPTS = [
    ['Arial, sans-serif', 'Arial'], ['Verdana, sans-serif', 'Verdana'],
    ['Georgia, serif', 'Georgia'], ['Times New Roman, serif', 'Times New Roman'],
    ['Courier New, monospace', 'Courier New'],
    ['微软雅黑, Microsoft YaHei, sans-serif', '微软雅黑'], ['宋体, SimSun, serif', '宋体']
  ];
  const SIZE_OPTS = [[12, '小（12px）'], [14, '普通（14px）'], [16, '大（16px）'],
                     [18, '更大（18px）'], [22, '特大（22px）'], [28, '超大（28px）']];
  const FG_SWATCHES = ['#1f2d3d', '#8a919f', '#d64545', '#e67e22', '#b58900', '#27ae60', '#2d8cf0', '#8e44ad', '#ffffff'];
  const BG_SWATCHES = ['#fff3b0', '#ffe08a', '#d9f2d0', '#bfe3ff', '#ffd6d6', '#f0dcff', '#fff0f0', '#ffffff'];

  const popBtn = (pid, label, title, extra) =>
    '<button type="button" class="rte-btn rte-pop-btn ' + (extra || '') + '" data-pop="' + pid + '" title="' + title + '">' +
      '<span class="rte-pop-label">' + label + '</span><i class="bi bi-caret-down-fill rte-caret"></i>' +
    '</button>';
  const btn = (icon, cmd, val, title, extraCls) =>
    '<button type="button" class="rte-btn ' + (extraCls || '') + '" title="' + title + '" data-cmd="' + cmd + '" data-val="' + (val || '') + '"><i class="bi ' + icon + '"></i></button>';
  const swatches = (arr, act) => arr.map(c =>
    '<button type="button" class="rte-swatch" data-act="' + act + ',' + c + '" style="background:' + c + ';' +
    (c === '#ffffff' ? 'border:1px solid #d6dbe3;' : '') + '" title="' + c + '"></button>').join('');

  bar.innerHTML =
    '<div class="rte-group rte-group-drop">' +
      '<div class="rte-pop-wrap">' + popBtn(popIds.fmt, '正文', '段落样式') +
        '<div class="rte-pop" id="' + popIds.fmt + '">' +
          '<button type="button" class="rte-pop-opt" data-act="block,p">正文</button>' +
          '<button type="button" class="rte-pop-opt" data-act="block,h1">标题 1</button>' +
          '<button type="button" class="rte-pop-opt" data-act="block,h2">标题 2</button>' +
          '<button type="button" class="rte-pop-opt" data-act="block,h3">标题 3</button>' +
          '<button type="button" class="rte-pop-opt" data-act="block,h4">标题 4</button>' +
          '<button type="button" class="rte-pop-opt" data-act="block,blockquote">引用</button>' +
        '</div></div>' +
      '<div class="rte-pop-wrap">' + popBtn(popIds.font, '字体', '字体') +
        '<div class="rte-pop" id="' + popIds.font + '">' +
          FONT_OPTS.map(o => '<button type="button" class="rte-pop-opt" data-act="fontf,' + o[0] + '">' + o[1] + '</button>').join('') +
        '</div></div>' +
      '<div class="rte-pop-wrap">' + popBtn(popIds.size, '字号', '字号') +
        '<div class="rte-pop" id="' + popIds.size + '">' +
          SIZE_OPTS.map(o => '<button type="button" class="rte-pop-opt" data-act="font,' + o[0] + '">' + o[1] + '</button>').join('') +
        '</div></div>' +
    '</div>' +
    '<div class="rte-group">' +
      btn('bi-type-bold', 'bold', '', '加粗') +
      btn('bi-type-italic', 'italic', '', '斜体') +
      btn('bi-type-underline', 'underline', '', '下划线') +
      btn('bi-type-strikethrough', 'strikeThrough', '', '删除线') +
      '<div class="rte-pop-wrap">' +
        '<button type="button" class="rte-btn rte-color-btn" data-pop="' + popIds.color + '" title="文字颜色">' +
          '<i class="bi bi-palette"></i><span class="rte-color-swatch" style="background:#1f2d3d"></span></button>' +
        '<div class="rte-pop rte-color-pop" id="' + popIds.color + '">' +
          '<div class="rte-pop-title">文字颜色</div>' +
          '<div class="rte-swatches">' + swatches(FG_SWATCHES, 'color') + '</div>' +
          '<label class="rte-custom-color">自定义：<input type="color" data-role="fgpick" value="#1f2d3d"></label>' +
        '</div></div>' +
      '<div class="rte-pop-wrap">' +
        '<button type="button" class="rte-btn rte-color-btn" data-pop="' + popIds.bg + '" title="背景高亮颜色">' +
          '<i class="bi bi-highlighter"></i><span class="rte-color-swatch" style="background:#fff3b0"></span></button>' +
        '<div class="rte-pop rte-color-pop" id="' + popIds.bg + '">' +
          '<div class="rte-pop-title">背景高亮</div>' +
          '<div class="rte-swatches">' + swatches(BG_SWATCHES, 'bg') + '</div>' +
          '<label class="rte-custom-color">自定义：<input type="color" data-role="bgpick" value="#fff3b0"></label>' +
        '</div></div>' +
      btn('bi-eraser', 'clear', '', '清除格式') +
    '</div>' +
    '<div class="rte-group">' +
      btn('bi-text-left', 'justifyLeft', '', '左对齐') +
      btn('bi-text-center', 'justifyCenter', '', '居中') +
      btn('bi-text-right', 'justifyRight', '', '右对齐') +
      btn('bi-text-justify', 'justifyFull', '', '两端对齐') +
    '</div>' +
    '<div class="rte-group">' +
      btn('bi-list-ul', 'insertUnorderedList', '', '项目符号') +
      btn('bi-list-ol', 'insertOrderedList', '', '编号列表') +
      btn('bi-link-45deg', 'link', '', '添加链接') +
      '<button type="button" class="rte-btn rte-btn-primary rte-img-btn" data-cmd="img" title="插入图片：点击选择本地图片并上传到正文"><i class="bi bi-image me-1"></i>插入图片</button>' +
      btn('bi-arrow-counterclockwise', 'undo', '', '撤销') +
      btn('bi-arrow-clockwise', 'redo', '', '重做') +
    '</div>' +
    '<input type="file" id="' + fileId + '" accept="image/*" class="d-none">';

  // ------- 弹出面板开关（同一时刻最多展开一个；点外部自动收起） -------
  const closePops = (exceptId) => {
    bar.querySelectorAll('.rte-pop').forEach(p => { if (p.id !== exceptId) p.classList.remove('show'); });
  };
  const openPop = (pid, btnEl) => {
    const pop = $(pid);
    if (!pop) return;
    const isOpen = pop.classList.contains('show');
    closePops(pid);
    if (isOpen) return;
    pop.classList.add('show');
    pop.style.left = Math.max(4, btnEl.offsetLeft) + 'px';
    pop.style.top = '';
    const popH = pop.offsetHeight;
    const r = btnEl.getBoundingClientRect();
    const spaceBelow = window.innerHeight - r.bottom - 10;
    pop.style.top = (spaceBelow > popH + 6 ? 30 : -(popH + 8)) + 'px';
    setTimeout(() => {
      const l = pop.getBoundingClientRect().left + pop.offsetWidth - window.innerWidth;
      if (l > 4) pop.style.left = Math.max(4, pop.offsetLeft - l) + 'px';
    }, 0);
  };
  document.addEventListener('mousedown', (e) => {
    if (!bar.contains(e.target)) closePops('');
  });

  // ------- 选区保存/恢复（核心：任何工具应用前恢复选中内容） -------
  let savedRange = null;
  const snapshotSel = () => {
    const sel = window.getSelection();
    if (sel && sel.rangeCount && sel.getRangeAt(0) && !sel.getRangeAt(0).collapsed) {
      try { savedRange = sel.getRangeAt(0).cloneRange(); } catch (err) { savedRange = null; }
    }
  };
  const restoreSel = () => {
    if (savedRange) {
      try {
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(savedRange);
      } catch (err) { /* ignore */ }
    }
    box.focus();
  };
  bar.addEventListener('mousedown', (e) => {
    if (e.target.closest('.rte-btn, .rte-pop-opt, .rte-swatch, input[type=color]')) e.preventDefault();
    if (!e.target.closest('input[type=color]')) snapshotSel();
  });
  bar.addEventListener('focusout', () => { savedRange = null; }, true);
  box.addEventListener('keyup', snapshotSel);
  box.addEventListener('mouseup', snapshotSel);

  // ------- 点击分发：面板 / 选项 / 普通命令 -------
  bar.addEventListener('click', (e) => {
    const popBtnEl = e.target.closest('[data-pop]');
    if (popBtnEl) { openPop(popBtnEl.getAttribute('data-pop'), popBtnEl); return; }
    const actEl = e.target.closest('[data-act]');
    if (actEl) {
      const parts = actEl.getAttribute('data-act').split(',');
      const kind = parts[0];
      const v = parts.slice(1).join(',').trim();
      closePops('');
      if (kind === 'block') { restoreSel(); rteRun(box, 'formatBlock', FMT_KEYS[v] || 'p'); }
      else if (kind === 'font') { restoreSel(); wrapSpan(box, 'fontSize', v + 'px'); }
      else if (kind === 'fontf') { restoreSel(); wrapSpan(box, 'fontFamily', v); }
      else if (kind === 'color') { restoreSel(); wrapSpan(box, 'color', v); }
      else if (kind === 'bg') { restoreSel(); wrapSpan(box, 'backgroundColor', v); }
      box.focus();
      return;
    }
    const b = e.target.closest('[data-cmd]');
    if (!b) return;
    const cmd = b.getAttribute('data-cmd');
    if (cmd === 'img') { const fi = $(fileId); if (fi) fi.click(); return; }
    const val = b.getAttribute('data-val') || '';
    restoreSel();
    rteRun(box, cmd, val);
  });

  // 自定义颜色取色器
  bar.querySelectorAll('input[type=color]').forEach(ci => {
    ci.addEventListener('change', () => {
      restoreSel();
      if (ci.getAttribute('data-role') === 'bgpick') wrapSpan(box, 'backgroundColor', ci.value);
      else wrapSpan(box, 'color', ci.value);
    });
  });

  // ------- 图片上传：上传成功后插入光标处（或文末），并约束图片显示尺寸 -------
  const file = $(fileId);
  if (file) {
    file.addEventListener('change', async (e) => {
      const f = e.target.files && e.target.files[0];
      e.target.value = '';
      if (!f) return;
      const fd = new FormData();
      fd.append('file', f);
      try {
        const res = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.error || '上传失败');
        box.focus();
        const sel = window.getSelection();
        if (sel && sel.rangeCount && !sel.getRangeAt(0).collapsed) sel.removeAllRanges();
        document.execCommand('insertImage', false, data.path);
        const imgs = box.querySelectorAll('img');
        const last = imgs[imgs.length - 1];
        if (last) {
          last.style.maxWidth = '100%';
          last.style.height = 'auto';
          last.setAttribute('alt', '图片');
        }
      } catch (err) {
        alert(err.message);
      }
    });
  }

  // ------- 光标位置变化时同步下拉按钮文案（反映当前段落/字体/字号） -------
  const syncRteState = () => {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;
    const node = sel.getRangeAt(0).startContainer;
    let el = node.nodeType === 1 ? node : node.parentElement;
    if (!el || !box.contains(el)) return;
    let fmtName = '正文', sizeTxt = null, fontTxt = null;
    while (el && el !== box) {
      if (FMT_NAMES[el.tagName]) fmtName = FMT_NAMES[el.tagName];
      if (el.style) {
        if (!sizeTxt && /^\d+px$/.test(el.style.fontSize || '')) sizeTxt = parseInt(el.style.fontSize, 10);
        if (!fontTxt && el.style.fontFamily) fontTxt = el.style.fontFamily.split(',')[0].replace(/["']/g, '').trim();
      }
      el = el.parentElement;
    }
    const setLabel = (pid, txt) => {
      const l = bar.querySelector('[data-pop="' + pid + '"] .rte-pop-label');
      if (l) l.textContent = txt;
    };
    setLabel(popIds.fmt, fmtName);
    setLabel(popIds.size, sizeTxt ? sizeTxt + 'px' : '字号');
    setLabel(popIds.font, fontTxt ? fontTxt : '字体');
  };
  ['keyup', 'mouseup', 'click', 'input'].forEach(ev => box.addEventListener(ev, syncRteState));

  // ------- 点击图片可选中并删除 -------
  box.addEventListener('click', (e) => {
    if (e.target && e.target.tagName === 'IMG') {
      e.preventDefault();
      box.focus();
      const r = document.createRange();
      r.selectNode(e.target);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(r);
      if (confirm('删除这张图片？')) e.target.remove();
    }
  });

  // ------- 空态占位提示 -------
  if (!box.getAttribute('data-ph-inited')) {
    box.setAttribute('data-ph-inited', '1');
    const ph = box.getAttribute('data-placeholder') || '';
    if (ph) box.dataset.placeholder = ph;
    box.addEventListener('focus', () => box.classList.add('rte-focus'));
    box.addEventListener('blur', () => {
      box.classList.remove('rte-focus');
      box.classList.toggle('rte-empty', !box.textContent.trim() && !box.querySelector('img'));
    });
    box.classList.add('rte-empty');
  }
}

function rteRun(box, cmd, val) {
  if (!box) return;
  box.focus();
  if (cmd === 'formatBlock') {
    document.execCommand('formatBlock', false, val ? '<' + val + '>' : 'p');
  } else if (cmd === 'fontSize') {
    if (!val) return;
    wrapSpan(box, 'fontSize', val + 'px');
  } else if (cmd === 'fontFamily') {
    if (!val) return;
    wrapSpan(box, 'fontFamily', val);
  } else if (cmd === 'bold' || cmd === 'italic' || cmd === 'underline' || cmd === 'strikeThrough') {
    document.execCommand(cmd, false, null);
  } else if (cmd === 'clear') {
    document.execCommand('removeFormat', false, null);
  } else if (cmd.indexOf('justify') === 0) {
    document.execCommand(cmd, false, null);
  } else if (cmd === 'insertUnorderedList' || cmd === 'insertOrderedList') {
    document.execCommand(cmd, false, null);
  } else if (cmd === 'link') {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount || sel.getRangeAt(0).collapsed || !sel.toString().trim()) {
      alert('请先选中要添加链接的文字');
      return;
    }
    const url = prompt('请输入链接地址（建议以 http:// 或 https:// 开头）：');
    if (!url) return;
    document.execCommand('createLink', false, url);
  } else if (cmd === 'undo') {
    document.execCommand('undo', false, null);
  } else if (cmd === 'redo') {
    document.execCommand('redo', false, null);
  }
}

function wrapSpan(box, prop, cssVal) {
  if (!cssVal) return;
  box.focus();
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return;
  const range = sel.getRangeAt(0);
  if (range.collapsed || !sel.toString().trim()) { box.focus(); return; }
  const span = document.createElement('span');
  span.style[prop] = cssVal;
  try {
    range.surroundContents(span);
    const r2 = document.createRange();
    r2.selectNodeContents(span);
    sel.removeAllRanges();
    sel.addRange(r2);
  } catch (err) {
    // 跨段落选区：用 insertHTML 包裹选区 HTML
    const tmp = document.createElement('div');
    tmp.appendChild(range.cloneContents());
    const innerHtml = sanitizeRte(tmp.innerHTML);
    document.execCommand('insertHTML', false, '<span style="' + prop + ':' + cssVal.replace(/"/g, '') + '">' + innerHtml + '</span>');
  }
}


/* 初始化：面板默认展示 + 恢复当前 hash */
(function () {
  const h = (location.hash || '').replace('#', '');
  const initial = SEC_ORDER.indexOf(h) >= 0 ? h : 'sec-stats';
  SEC_ORDER.forEach(k => {
    const el = $(k);
    if (el) el.classList.toggle('d-none', k !== initial);
  });
  const nav = document.querySelector('.sidebar-menu a[href="#' + initial + '"]');
  if (nav) nav.classList.add('active');
  updateCrumb(initial);
  mountGuides();
  window.scrollTo(0, 0);
})();

/* ===== 3 步快速开始引导（首次打开自动弹出） ===== */
(function () {
  let obTemplate = '';
  let obModal = null;

  function obStep(n) {
    [1, 2, 3].forEach(i => $('obStep' + i).classList.toggle('d-none', i !== n));
    [1, 2, 3].forEach(i => {
      const el = $('obStepLabel' + i);
      el.classList.toggle('text-primary', i === n);
      el.classList.toggle('fw-bold', i === n);
    });
  }

  function markStep2() {
    const name = $('obSiteName').value.trim();
    if (!name) { $('obSiteName').focus(); return alert('先给网站起个名字（用英文）'); }
    obStep(2);
    api('/api/templates').then(list => {
      const grid = $('obTemplateGrid');
      grid.innerHTML = list.map(t =>
        '<div class="col-6 col-md-4">' +
        '<div class="card ob-tpl h-100" data-id="' + esc(t.id) + '" style="cursor:pointer;border-width:2px;">' +
        '<div class="p-2">' +
        '<div style="height:52px;border-radius:8px;background:' + esc(t.thumb) + ';"></div>' +
        '<div class="fw-semibold mt-2 small">' + esc(t.name) + '</div>' +
        '<div class="text-muted" style="font-size:.72rem;line-height:1.3;">' + esc(t.desc) + '</div>' +
        '</div></div></div>').join('');
      grid.querySelectorAll('.ob-tpl').forEach(card => {
        card.addEventListener('click', () => {
          grid.querySelectorAll('.ob-tpl').forEach(c => {
            c.classList.remove('border-primary');
            c.classList.add('border-light');
          });
          card.classList.add('border-primary');
          card.classList.remove('border-light');
          obTemplate = card.dataset.id;
          $('obNext2').disabled = false;
        });
      });
    });
  }

  function markStep3() {
    obStep(3);
    const name = $('obSiteName').value.trim() || 'My Export Site';
    $('obGenStatus').innerHTML = '<div class="alert alert-info py-2 mb-0">⏳ 正在生成演示网站...</div>';
    $('obGenResult').innerHTML = '';
    api('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ site_name: name, template: obTemplate || 'business' })
    }).then(res => {
      $('obGenStatus').innerHTML = '<div class="alert alert-success py-2 mb-2">✅ 演示网站已生成（模板：' + esc(res.template_name || '') + '）</div>';
      $('obGenResult').innerHTML = '<div class="small text-muted mb-2">预览是本地效果，没有推到网上。满意就点「完成」开始录自己的产品和联系方式；不满意就「清空演示数据」换个模板再来。</div>';
      $('obPreview').classList.remove('d-none');
      $('obReset').classList.remove('d-none');
      $('obFinish').classList.remove('d-none');
      $('obPreview').onclick = () => window.open('/api/preview?site_name=' + encodeURIComponent(name) + '&template=' + encodeURIComponent(obTemplate || 'business'), '_blank');
    }).catch(e => {
      $('obGenStatus').innerHTML = '<div class="alert alert-danger py-2 mb-0">生成失败：' + esc(e.message) + '</div>';
    });
  }

  function obFinish() {
    api('/api/onboarding/done', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    }).then(() => { obModal.hide(); }).catch(() => { obModal.hide(); });
  }

  (function () {
    if (!$('onboardModal') || !window.bootstrap) return;
    api('/api/onboarding/status').then(st => {
      if (!st.show) return;
      obModal = new bootstrap.Modal($('onboardModal'));
      $('obNext1').addEventListener('click', markStep2);
      $('obBack2').addEventListener('click', () => obStep(1));
      $('obNext2').addEventListener('click', markStep3);
      $('obBack3').addEventListener('click', () => obStep(2));
      $('obFinish').addEventListener('click', obFinish);
      $('obSkip').addEventListener('click', obFinish);
      $('onboardSkipTop').addEventListener('click', obFinish);
      $('obReset').addEventListener('click', () => {
        if (!confirm('确定清空演示数据吗？产品、横幅、联系方式等会全部清空，回到全新状态。')) return;
        api('/api/onboarding/reset', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: '{}'
        }).then(() => {
          obModal.hide();
          location.reload();
        });
      });
      obModal.show();
    }).catch(() => {});

  })();
})();

/* ===== 内置「原始模板」：加载示例 / 一键清空（全局函数，供 inline onclick 调用）===== */
function loadStarterTemplate() {
  if (!confirm('加载示例模板会覆盖当前的产品/横幅/联系方式/板块内容等数据。确定继续？建议先备份。')) return;
  var btn = $('starterLoadBtn'); if (btn) btn.disabled = true;
  api('/api/starter/load', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
    .then(function () {
      // 加载后整页刷新：所有表单字段与图片「已上传」预览（logo / 横幅 / 产品 / 灰帽工具箱）都会从数据库重新填充
      location.reload();
    })
    .catch(function (e) { if ($('starterTip')) $('starterTip').textContent = '加载失败：' + (e && e.message ? e.message : e); if (btn) btn.disabled = false; });
}

function clearStarterContent() {
  if (!confirm('一键清空会删除全部填写的内容（产品/横幅/联系方式/板块内容/SEO/推广工具箱等），但保留板块框架与模板设置。确定？')) return;
  var btn = $('starterClearBtn'); if (btn) btn.disabled = true;
  api('/api/starter/clear', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
    .then(function () {
      // 清空后整页刷新：表单回到空白框架（产品/横幅/联系方式/板块内容/SEO/灰帽 全部清空），仅保留板块骨架与模板设置
      location.reload();
    })
    .catch(function (e) { if ($('starterTip')) $('starterTip').textContent = '清空失败：' + (e && e.message ? e.message : e); if (btn) btn.disabled = false; });
}
