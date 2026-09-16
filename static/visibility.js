(() => {
  const el = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const json = body => ({method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  let report;
  el('visibilityAudit').onclick = async () => {
    const button=el('visibilityAudit'); button.disabled=true;
    el('visibilityReport').textContent='正在生成并逐页检查，使用最近保存的内容…';
    try {
      report=await api('/api/visibility/audit', json({}));
      el('visibilityReport').innerHTML=`<p><b>检查了 ${report.pages} 页：${report.errors} 个需要修正的问题，${report.warnings} 个建议。</b></p><p class="small text-muted">${escape(report.notice)}</p>`+
        report.issues.map(i=>`<div class="border rounded p-2 mb-2"><b class="${i.level==='error'?'text-danger':'text-warning'}">${escape(i.problem)}</b><div class="small">${escape(i.page)}</div><div>${escape(i.fix)}</div></div>`).join('');
      el('visibilityDownload').disabled=false;
    } catch(e){el('visibilityReport').textContent=e.message;} finally {button.disabled=false;}
  };
  el('visibilityDownload').onclick=()=>{
    const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='ChatFLOW-网站检查.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  api('/api/visibility/settings').then(s=>{el('visibilitySearch').checked=s.search;el('visibilityTraining').checked=s.training;}).catch(e=>el('visibilitySettingTip').textContent=e.message);
  el('visibilitySave').onclick=async()=>{
    try {await api('/api/visibility/settings',json({geo_ai_enabled:el('visibilitySearch').checked,geo_training_enabled:el('visibilityTraining').checked}));el('geoAiEnabled').checked=el('visibilitySearch').checked;el('visibilitySettingTip').textContent='已保存，发布后生效。';}
    catch(e){el('visibilitySettingTip').textContent=e.message;}
  };
  el('geoAiEnabled').addEventListener('change',()=>el('visibilitySearch').checked=el('geoAiEnabled').checked);
  el('productDraftPreview').onclick=async()=>{
    try{const d=await api('/api/visibility/product_drafts');el('productDraftResult').innerHTML='<p>'+escape(d.notice)+'</p>'+d.items.map(x=>'<div class="border-bottom p-2"><b>'+escape(x.name)+'</b><br>'+escape(x.fields.meta_title||'标题已有内容，保留')+'<br>'+escape(x.fields.meta_description||'摘要已有内容，保留')+'</div>').join('');el('productDraftApply').disabled=d.count===0;}
    catch(e){el('productDraftResult').textContent=e.message;}
  };
  el('productDraftApply').onclick=async()=>{
    el('productDraftApply').disabled=true;
    try{const d=await api('/api/visibility/product_drafts',json({}));el('productDraftResult').textContent='已为 '+d.count+' 个产品补齐空白项。请检查，再发布网站。';}
    catch(e){el('productDraftResult').textContent=e.message;el('productDraftApply').disabled=false;}
  };
  api('/api/visibility/experiments').then(x=>el('experimentEnabled').checked=x.enabled).catch(e=>el('experimentTip').textContent=e.message);
  el('experimentSave').onclick=async()=>{
    try{await api('/api/visibility/experiments',json({enabled:el('experimentEnabled').checked}));el('experimentTip').textContent='已保存，重新生成并发布后生效。';}
    catch(e){el('experimentTip').textContent=e.message;}
  };
  const records=async()=>{
    const rows=await api('/api/visibility/results');
    el('vrRecords').innerHTML=rows.length?'<div class="table-responsive"><table class="table"><thead><tr><th>日期</th><th>曝光</th><th>点击</th><th>询盘</th><th>来源 / AI 证据</th></tr></thead><tbody>'+rows.slice().reverse().map(x=>`<tr><td>${escape(x.date)}</td><td>${x.impressions}</td><td>${x.clicks}</td><td>${x.inquiries}</td><td>${escape(x.source)}<br>${escape(x.ai_evidence)}</td></tr>`).join('')+'</tbody></table></div>':'还没有记录，有真实数据后再填写。';
  };
  el('vrDate').value=new Date().toLocaleDateString('en-CA');
  el('vrSave').onclick=async()=>{
    try {await api('/api/visibility/results',json({date:el('vrDate').value,impressions:el('vrImpressions').value,clicks:el('vrClicks').value,inquiries:el('vrInquiries').value,source:el('vrSource').value,ai_evidence:el('vrEvidence').value}));await records();}
    catch(e){el('vrRecords').textContent=e.message;}
  };
  records().catch(e=>el('vrRecords').textContent=e.message);
  // Warn on navigation when a form's current state differs from its successfully saved state.
  const dirty=new Set();
  window.cfFormState=form=>JSON.stringify(Array.from(form.elements).map(e=>[e.name||e.id,e.value,e.checked]));
  document.addEventListener('input',e=>{const form=e.target.closest('form');if(form) dirty.add(form);});
  document.addEventListener('submit',e=>{
    const form=e.target;
    // A submitted form is not yet saved. api() emits only after a successful response.
    window.__cfSubmittingForm=form;
  },true);
  window.addEventListener('cf-saved',e=>{const {form,state}=e.detail;if(window.cfFormState(form)===state)dirty.delete(form);});
  window.addEventListener('beforeunload',e=>{if(dirty.size){e.preventDefault();e.returnValue='';}});
})();
