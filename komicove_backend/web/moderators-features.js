let contributorRows=[], updateRows=[], importedReleases=[];
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
    await api('/api/moderators/updates',{method:'POST',body:JSON.stringify(payload)});
    msg('updateMsg',t('Mensagem publicada nos apps.'));await loadUpdates();
  }catch(error){msg('updateMsg',error.message,true);}finally{button.disabled=false;}
};
async function loadUpdates(more=false) {
  try {
    const rows=await api(`/api/moderators/updates?offset=${more?updateRows.length:0}&limit=50`);updateRows=more?updateRows.concat(rows):rows;
    $('updateRows').innerHTML=updateRows.map(item=>`<article class="update-log"><h3>${esc(item.title)}</h3><span class="badge">${esc(item.version)}</span><small>${t('por')} @${esc(item.created_by_username)} · ${date(item.created_at)}</small><small>${t(item.source==='github'?'Importada do GitHub':'Manual')}${item.source_repository?` · ${esc(item.source_repository)} · #${esc(item.source_release_id)}`:''}</small><small>${t('Destino')}: ${t(item.download_destination==='site'?'Site do Komicove':item.download_destination==='github'?'GitHub':'Sem botão Baixar')}</small>${item.source_release_url?`<a href="${esc(item.source_release_url)}" target="_blank" rel="noopener noreferrer">${t('Release')}</a>`:''}<div class="markdown">${item.notes_html}</div>${item.download_url?`<a class="btn secondary" href="${esc(item.download_url)}" target="_blank" rel="noopener noreferrer">${t('Baixar')}</a>`:''}</article>`).join('')||`<p>${t('Nenhuma atualização publicada.')}</p>`;
    $('updatesMore').classList.toggle('hidden',rows.length<50);
  }catch(error){msg('updateMsg',error.message,true);}
}
$('updatesRefresh').onclick=()=>loadUpdates();$('updatesMore').onclick=()=>loadUpdates(true);
