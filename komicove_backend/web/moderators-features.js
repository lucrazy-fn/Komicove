let contributorRows=[], updateRows=[], importedReleases=[], updateIndex=0;
let releasePage=0;
const tokenStatuses={available:'Disponível',used:'Utilizado',revoked:'Revogado',expired:'Expirado'};
async function loadContributors(more=false) {
  try {
    const rows=await api(`/api/contributor-tokens?offset=${more?contributorRows.length:0}&limit=50`);
    contributorRows=more?contributorRows.concat(rows):rows;
    $('contributorRows').innerHTML=contributorRows.map(item=>`<div class="invite"><div><b>${esc(t(tokenStatuses[item.status]))} · ${esc(item.id.slice(0,8))}</b><small>${t('Criado por')} @${esc(item.created_by_username)} · ${date(item.created_at)}</small><small>${t('Expira')} ${date(item.expires_at)}</small>${item.used_at?`<small>${t('Utilizado por')} @${esc(item.used_by_username)} · ${date(item.used_at)}</small>`:''}${item.revoked_at?`<small>${t('Revogado')} ${date(item.revoked_at)}</small>`:''}</div>${item.status==='available'?`<button class="btn danger" data-contributor-revoke="${esc(item.id)}">${t('Revogar')}</button>`:''}</div>`).join('')||`<p>${t('Nenhum token de Contribuidor.')}</p>`;
    $('contributorsMore').classList.toggle('hidden',rows.length<50);
    document.querySelectorAll('[data-contributor-revoke]').forEach(button=>button.onclick=async()=>{
      button.disabled=true;
      try { await api(`/api/contributor-tokens/${button.dataset.contributorRevoke}`,{method:'DELETE'});await loadContributors(); }
      catch(error) {msg('contributorMsg',error.message,true);} finally {button.disabled=false;}
    });
  } catch(error) {msg('contributorMsg',error.message,true);}
}
$('contributorsRefresh').onclick=()=>loadContributors();$('contributorsMore').onclick=()=>loadContributors(true);
$('contributorGenerate').onclick=async()=>{
  const button=$('contributorGenerate');button.disabled=true;
  $('contributorResult').classList.add('hidden');$('contributorSecret').textContent='';
  try {
    const data=await api('/api/contributor-tokens',{method:'POST',body:JSON.stringify({valid_hours:Number($('contributorHours').value)})});
    $('contributorSecret').textContent=data.secret;$('contributorResult').classList.remove('hidden');
    msg('contributorMsg',`${t('Válido até')} ${date(data.expires_at)}`);await loadContributors();
  }catch(error){msg('contributorMsg',error.message,true);}finally{button.disabled=false;}
};
$('contributorCopy').onclick=async()=>{
  try {await navigator.clipboard.writeText($('contributorSecret').textContent);msg('contributorMsg',t('Copiado!'));}
  catch {msg('contributorMsg',t('Não foi possível copiar. Selecione e copie o token acima.'),true);}
};
function updateSourceChanged() {
  const imported=$('updateSource').value==='github';$('releaseFields').classList.toggle('hidden',!imported);
  for(const id of ['updateTitle','updateVersion','updateNotes'])$(id).readOnly=imported;
  $('updatePreviewBody').replaceChildren();
  renderDownloadDestination();
}
$('updateSource').onchange=updateSourceChanged;
$('releaseRepository').onchange=()=>{importedReleases=[];releasePage=0;$('releasesMore').classList.add('hidden');$('releaseChoice').replaceChildren(new Option(t('Selecione uma Release'),''));for(const id of ['updateTitle','updateVersion','updateNotes'])$(id).value='';$('updatePreviewBody').replaceChildren();renderDownloadDestination();};
async function loadReleases(more=false){
  const button=$('loadReleases'),repository=$('releaseRepository').value,page=more?releasePage+1:1,selected=$('releaseChoice').value;button.disabled=true;$('releasesMore').disabled=true;
  try {
    const rows=await api(`/api/moderators/releases?repository=${encodeURIComponent(repository)}&page=${page}`);
    if(repository!==$('releaseRepository').value)return;
    releasePage=page;importedReleases=more?importedReleases.concat(rows):rows;
    $('releaseChoice').replaceChildren(new Option(t('Selecione uma Release'),''),...importedReleases.map(item=>new Option(`${item.title} (${item.version})`,String(item.id))));msg('updateMsg','');
    if(more)$('releaseChoice').value=selected;
    $('releasesMore').classList.toggle('hidden',rows.length<30);
  }catch(error){msg('updateMsg',error.message,true);}finally{button.disabled=false;$('releasesMore').disabled=false;}
}
$('loadReleases').onclick=()=>loadReleases();$('releasesMore').onclick=()=>loadReleases(true);
$('releaseChoice').onchange=()=>{
  const release=importedReleases.find(item=>String(item.id)===$('releaseChoice').value);if(!release)return;
  $('updateTitle').value=release.title;$('updateVersion').value=release.version;$('updateNotes').value=release.notes;
  renderDownloadDestination();previewUpdate();
};
async function previewUpdate() {
  const button=$('updatePreview'),notes=$('updateNotes').value;button.disabled=true;
  try {const data=await api('/api/moderators/updates/preview',{method:'POST',body:JSON.stringify({notes})});if(notes===$('updateNotes').value)$('updatePreviewBody').innerHTML=data.html;}
  catch(error){msg('updateMsg',error.message,true);}finally{button.disabled=false;}
}
$('updatePreview').onclick=previewUpdate;
function renderDownloadDestination(){
  const version=$('updateVersion').value.trim().replace(/^[vV]/,'');
  $('updateDownload').textContent=$('updateDestination').value==='site'?'https://lucrazy-fn.github.io/Komicove/#downloads':version?`https://github.com/lucrazy-fn/PANEL-ComicBookReader/releases/tag/v${encodeURIComponent(version)}`:t('Informe a versão para ver o destino.');
}
$('updateVersion').oninput=renderDownloadDestination;$('updateDestination').onchange=renderDownloadDestination;
renderDownloadDestination();
$('updatePublish').onclick=async()=>{
  const button=$('updatePublish');button.disabled=true;
  try {
    const payload={source:$('updateSource').value,download_destination:$('updateDestination').value};
    if(payload.source==='github') {
      if(!$('releaseChoice').value)throw Error(t('Selecione uma Release antes de publicar.'));
      payload.repository=$('releaseRepository').value;payload.release_id=$('releaseChoice').value;
    } else {payload.title=$('updateTitle').value;payload.version=$('updateVersion').value;payload.notes=$('updateNotes').value;}
    const created=await api('/api/moderators/updates',{method:'POST',body:JSON.stringify(payload)});
    msg('updateMsg',t('Mensagem publicada nos apps.'));await loadUpdates(created.id);
  }catch(error){msg('updateMsg',error.message,true);}finally{button.disabled=false;}
};
function renderUpdateHistory() {
  const controls=$('updateHistoryControls');
  controls.classList.toggle('hidden',updateRows.length===0);
  if(!updateRows.length){$('updateRows').innerHTML=`<p>${t('Nenhuma atualização publicada.')}</p>`;return;}
  updateIndex=Math.max(0,Math.min(updateIndex,updateRows.length-1));
  const choice=$('updateHistoryChoice');
  choice.replaceChildren(...updateRows.map((item,index)=>new Option(`${item.title} (${item.version})${index===0?` · ${t('Mais recente')}`:''}${item.automatic?` · ${t('Detectada automaticamente')}`:''}${item.selected?` · ${t('Exibida nos aplicativos')}`:''}`,item.id)));
  choice.value=updateRows[updateIndex].id;
  $('updatePrevious').disabled=updateIndex>=updateRows.length-1;
  $('updateNext').disabled=updateIndex<=0;
  const item=updateRows[updateIndex];
  $('updateRows').innerHTML=`<article class="update-log${item.selected?' selected':''}"><div class="update-log-head"><div><h3>${esc(item.title)}</h3><span class="badge">${esc(item.version)}</span>${updateIndex===0?`<span class="badge">${t('Mais recente')}</span>`:''}${item.automatic?`<span class="badge">${t('Detectada automaticamente')}</span>`:''}${item.selected?`<span class="badge update-selected-badge">${t('Exibida nos aplicativos')}</span>`:''}</div>${item.selected?`<button class="btn secondary" disabled>${t('Exibida nos aplicativos')}</button>`:`<button class="btn" data-select-update="${esc(item.id)}">${t('Exibir nos aplicativos')}</button>`}</div>${item.automatic?`<small>${t('Detectada automaticamente')} · GitHub · ${date(item.created_at)}</small>`:`<small>${t('por')} @${esc(item.created_by_username)} · ${date(item.created_at)}</small>`}<small>${t(item.source==='github'?'Importada do GitHub':'Manual')}${item.source_repository?` · ${esc(item.source_repository)} · #${esc(item.source_release_id)}`:''}</small><small>${t('Destino')}: ${t(item.download_destination==='site'?'Site do Komicove':item.download_destination==='github'?'GitHub':'Sem botão Baixar')}</small>${item.source_release_url?`<a href="${esc(item.source_release_url)}" target="_blank" rel="noopener noreferrer">${t('Release')}</a>`:''}<div class="markdown">${item.notes_html}</div>${item.download_url?`<a class="btn secondary" href="${esc(item.download_url)}" target="_blank" rel="noopener noreferrer">${t('Baixar')}</a>`:''}</article>`;
  const selectButton=document.querySelector('[data-select-update]');
  if(selectButton)selectButton.onclick=async()=>{
    selectButton.disabled=true;
    try{await api(`/api/moderators/updates/${encodeURIComponent(item.id)}/selection`,{method:'PUT'});msg('updateMsg',t('Atualização selecionada para os aplicativos.'));await loadUpdates(item.id);}
    catch(error){msg('updateMsg',error.message,true);selectButton.disabled=false;}
  };
}
function updateVersionId(value) {
  const match=String(value||'').trim().match(/^[vV]?(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/);
  if(!match)return String(value||'').toLowerCase();
  return `${Number(match[1])}.${Number(match[2])}.${Number(match[3]||0)}${Number(match[4]||0)?`.${Number(match[4])}`:''}${match[5]?`-${match[5].toLowerCase()}`:''}`;
}
async function loadAutomaticUpdates() {
  const repositories=['lucrazy-fn/PANEL-ComicBookReader','lucrazy-fn/Komicove'];
  const groups=await Promise.all(repositories.map(async(repository,repositoryIndex)=>{
    let page=1,rows=[],batch=[];
    try {
      do {
        batch=await api(`/api/moderators/releases?repository=${encodeURIComponent(repository)}&page=${page++}`);
        rows=rows.concat(batch);
      } while(batch.length===30);
    } catch(_error) { return []; }
    return rows.map(item=>({id:`auto-${repositoryIndex}-${item.id}`,title:item.title,version:item.version,notes:item.notes,
      notes_html:item.notes_html,source:'github',source_repository:repository,source_release_id:item.id,
      source_release_url:item.url,download_destination:'github',download_url:item.url,
      created_by_username:'GitHub',created_at:item.created_at,selected:false,selection_token:null,automatic:true}));
  }));
  return groups.flat();
}
async function loadUpdates(preferredId=null) {
  try {
    const currentId=preferredId||(updateRows[updateIndex]&&updateRows[updateIndex].id);let rows=[],page=[];
    do{page=await api(`/api/moderators/updates?offset=${rows.length}&limit=100`);rows=rows.concat(page);}while(page.length===100);
    const seen=new Set(rows.map(item=>updateVersionId(item.version)));
    for(const item of await loadAutomaticUpdates())if(!seen.has(updateVersionId(item.version))){rows.push(item);seen.add(updateVersionId(item.version));}
    updateRows=rows.sort((first,second)=>String(second.created_at||'').localeCompare(String(first.created_at||'')));
    const requested=updateRows.findIndex(item=>item.id===currentId),selected=updateRows.findIndex(item=>item.selected);
    updateIndex=requested>=0?requested:selected>=0?selected:0;
    renderUpdateHistory();
  }catch(error){msg('updateMsg',error.message,true);}
}
$('updateHistoryChoice').onchange=()=>{const index=updateRows.findIndex(item=>item.id===$('updateHistoryChoice').value);if(index>=0){updateIndex=index;renderUpdateHistory();}};
$('updatePrevious').onclick=()=>{if(updateIndex<updateRows.length-1){updateIndex++;renderUpdateHistory();}};
$('updateNext').onclick=()=>{if(updateIndex>0){updateIndex--;renderUpdateHistory();}};
$('updatesRefresh').onclick=()=>loadUpdates();
