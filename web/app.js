const cfg=window.VISUAL_WORLD_CONFIG||{}; if(safeUrl(cfg.githubUrl)){const g=document.querySelector('#githubLink');g.href=safeUrl(cfg.githubUrl);g.classList.remove('hidden')}
let offset=0,currentSource='',currentQ='',mode='works',statsData=null,searchVersion=0,previousFocus=null,searchController=null; const LIMIT=60;
const $=s=>document.querySelector(s),fmt=n=>new Intl.NumberFormat().format(n||0);
function esc(s=''){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function safeUrl(value){try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)?url.href:''}catch{return ''}}
const staticClient=cfg.snapshotUrl?window.VisualWorldStaticApi.createClient(cfg.snapshotUrl):null;
async function getJson(url,options={}){if(staticClient)return staticClient(url,options);const response=await fetch(url,options);if(!response.ok)throw new Error(`HTTP ${response.status}`);return response.json()}
function artworkCard(a){const img=safeUrl(a.thumbnail_url||a.image_url);const art=img?`<img referrerpolicy="no-referrer" loading="lazy" src="${esc(img)}" alt="${esc(a.title||'Untitled')}" data-fallbacks="${esc(JSON.stringify([a.image_url,...(a.image_alternatives||[])]))}">`:'<div class="noimg">∿</div>';const multi=a.source_count>1?`<span class="multi">${a.source_count} sources</span>`:'';return `<article class="card" data-artwork-id="${a.id}" role="button" tabindex="0" aria-label="查看作品：${esc(a.title||'Untitled')}"><div class="art">${art}${multi}</div><div class="meta"><h3>${esc(a.title||'Untitled')}</h3><p>${esc(a.artist||'Unknown artist')}</p><p>${esc(a.date_display||'')} ${a.medium?'· '+esc(a.medium):''}</p></div></article>`}
function resourceCard(r){const url=safeUrl(r.url);const domain=url?new URL(url).hostname.replace(/^www\./,''):'';const start=url?`<a class="resource-card" href="${esc(url)}" target="_blank" rel="noopener noreferrer">`:'<article class="resource-card">';return `${start}<div class="resource-top"><span class="resource-source">${esc(r.source_id.replaceAll('_',' '))}</span><span>${url?'↗':''}</span></div><h3>${esc(r.name)}</h3><p>${esc(r.description||'')}</p>${r.license_note?`<p class="resource-license">${esc(r.license_note)}</p>`:''}<div class="resource-foot"><span>${esc(r.category||'Resource')}</span><span>${esc(domain)}</span></div>${url?'</a>':'</article>'}`}
function sourceCard(s){const health=s.last_status==='ok'?'✓ healthy':s.last_status==='error'?'⚠ last sync failed':'○ not checked';const homepage=safeUrl(s.homepage);return `<article class="source-card"><div><span class="source-kind">${esc(s.kind.replaceAll('_',' '))}</span><h3>${esc(s.name)}</h3></div><p>${esc(s.rights_note||'')}</p><div class="source-numbers"><span><b>${fmt(s.visible_count??s.record_count)}</b> 可看作品</span><span><b>${fmt(s.image_count)}</b> images</span><span><b>${fmt(s.resource_count)}</b> links</span></div><div class="source-sync ${esc(s.last_status||'')}">${health}${s.last_sync?` · ${esc(new Date(s.last_sync).toLocaleString())}`:''}</div>${s.last_error?`<details class="source-error"><summary>Last error</summary><p>${esc(s.last_error)}</p></details>`:''}${homepage?`<a href="${esc(homepage)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>`:''}</article>`}
async function loadStats(){statsData=await getJson('/api/stats'); $('#canonical').textContent=fmt(statsData.canonical); $('#total').textContent=fmt(statsData.total); $('#images').textContent=fmt(statsData.images); $('#artists').textContent=fmt(statsData.artists); $('#resourceN').textContent=fmt(statsData.resources); $('#sourceN').textContent=statsData.sources.length; if(statsData.snapshot_at)$('#snapshotNote').textContent=` · 全量公开图库，更新于 ${new Date(statsData.snapshot_at).toLocaleString()}`; renderSources()}
function renderSources(){const box=$('#sources'); if(mode==='sources'){box.innerHTML='';return} const resourceMode=mode==='resources'; const list=statsData.sources.filter(s=>resourceMode?s.kind==='resource_index':s.kind!=='resource_index'&&(s.visible_count??s.record_count)>0); const total=resourceMode?statsData.resources:statsData.canonical; box.innerHTML=`<button class="source-btn active" data-source=""><span>All sources</span><small>${fmt(total)}</small></button>`+list.map(s=>`<button class="source-btn" data-source="${s.id}"><span>${esc(s.name)}</span><small>${fmt(resourceMode?s.resource_count:(s.visible_count??s.record_count))}</small></button>`).join(''); box.onclick=e=>{let b=e.target.closest('.source-btn'); if(!b)return; currentSource=b.dataset.source; offset=0; document.querySelectorAll('.source-btn').forEach(x=>x.classList.remove('active')); b.classList.add('active'); search(true)}}
function filterParams(p){if(mode!=='works')return; p.set('with_images','1'); if($('#publicDomain').checked)p.set('public_domain','1'); const f=$('#yearFrom').value.trim(),t=$('#yearTo').value.trim(); if(/^\-?\d+$/.test(f))p.set('year_from',f); if(/^\-?\d+$/.test(t))p.set('year_to',t)}
async function search(reset=false){
    if(reset){searchController?.abort();searchController=new AbortController();searchVersion++;offset=0;$('#grid').innerHTML='';$('#resourceGrid').innerHTML=''}
    if(mode==='sources'){renderSourcePage();return}
    const version=searchVersion,searchMode=mode;
    const endpoint=searchMode==='resources'?'/api/resources':'/api/search';
    const params=new URLSearchParams({limit:LIMIT,offset,q:currentQ,source:currentSource});
    filterParams(params);
    $('#resultStatus').textContent='加载中…';
    $('#more').disabled=true;
    try{
        const data=await getJson(endpoint+'?'+params,{signal:searchController?.signal});
        if(version!==searchVersion)return;
        const items=data.items||[];
        const target=searchMode==='works'?$('#grid'):$('#resourceGrid');
        target.insertAdjacentHTML('beforeend',items.map(searchMode==='works'?artworkCard:resourceCard).join(''));
        offset+=items.length;
        const defaultTitle=searchMode==='works'?'All works':'All resources';
        $('#resultTitle').textContent=currentQ?`Results for “${currentQ}”`:(currentSource?(document.querySelector(`.source-btn[data-source="${currentSource}"] span`)?.textContent||defaultTitle):defaultTitle);
        $('#resultStatus').textContent=offset===0?'没有找到匹配内容，请更换关键词或筛选条件。':'';
        $('#more').style.display=items.length<LIMIT?'none':'block';
    }catch(error){
        if(error.name!=='AbortError'&&version===searchVersion){$('#resultStatus').textContent='搜索暂时不可用，请稍后重试。';$('#more').style.display='none'}
    }finally{
        if(version===searchVersion)$('#more').disabled=false;
    }
}
function renderSourcePage(){const g=$('#sourceGrid');g.innerHTML=statsData.sources.map(sourceCard).join('');$('#resultTitle').textContent='Connected & planned sources';$('#resultStatus').textContent='';$('#more').style.display='none'}
function setMode(next){if(!statsData)return;mode=next;currentSource='';offset=0;document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));$('#grid').classList.toggle('hidden',mode!=='works');$('#resourceGrid').classList.toggle('hidden',mode!=='resources');$('#sourceGrid').classList.toggle('hidden',mode!=='sources');$('#workFilters').classList.toggle('hidden',mode!=='works');$('#sources').classList.toggle('hidden',mode==='sources');$('#sourceLabel').textContent=mode==='resources'?'RESOURCE INDEXES':mode==='works'?'ARTWORK SOURCES':'SOURCE REGISTRY';$('#modeEyebrow').textContent=mode==='resources'?'DISCOVER · RESOURCES':mode==='sources'?'SYSTEM · SOURCES':'DISCOVER · ARTWORKS';$('#hint').textContent=mode==='resources'?'这里存的是“去哪里继续找”的资源入口，不复制对方全部素材。':mode==='sources'?'每个数据源独立记录同步方式、规模、最后同步时间和版权边界。':'只展示有公开图片的作品，点击即可查看。三个博物馆全量导入，多个来源的同一作品合并展示。';renderSources();search(true)}
function sourceRow(source){
    const url=safeUrl(source.object_url)||safeUrl(source.source_homepage);
    const rights=source.public_domain===1?'来源标记为 Public Domain / CC0':source.public_domain===0?'来源未标记为公有领域':'图像权利状态未确认';
    return `<div class="source-row"><div><b>${esc(source.source_name||source.source_id)}</b><small>${esc(source.accession_number||source.source_object_id||'')}</small><span>${esc(rights)}</span><span>元数据：${esc(source.metadata_license||'未注明')}</span><span>图像：${esc(source.image_license||'未注明')}</span>${source.rights_note?`<span>${esc(source.rights_note)}</span>`:''}</div>${url?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">查看原始记录 ↗</a>`:''}</div>`;
}
async function openArtwork(id){
    try{
        const data=await getJson('/api/artwork?id='+encodeURIComponent(id));
        if(!data.artwork)return;
        const artwork=data.artwork,image=safeUrl(artwork.image_url||artwork.thumbnail_url);
        const imageSource=data.sources.find(source=>source.public_domain===1&&((artwork.image_url&&source.image_url===artwork.image_url)||(artwork.thumbnail_url&&source.thumbnail_url===artwork.thumbnail_url)));
        if(!image){document.querySelector(`.card[data-artwork-id="${id}"]`)?.remove();return}
        const rights=artwork.public_domain===1?'至少一个来源标记为公有领域':'请逐条核对来源权利';
        const imageNote=image&&imageSource?`展示图像：${esc(imageSource.source_name||imageSource.source_id)} · ${esc(imageSource.image_license||'请核对原始记录')}`:'公开图片，出处与许可见下方。';
        $('#modalBody').innerHTML=`<div class="detail-image">${image?`<img referrerpolicy="no-referrer" src="${esc(image)}" data-fallbacks="${esc(JSON.stringify([artwork.thumbnail_url,...data.sources.filter(source=>source.public_domain===1).flatMap(source=>[source.image_url,source.thumbnail_url])]))}" data-artwork-id="${artwork.id}" alt="${esc(artwork.title||'Untitled')}">`:'<div class="noimg">∿</div>'}</div><div class="detail-copy"><p class="eyebrow">${artwork.source_count} SOURCE${artwork.source_count===1?'':'S'} · ${esc(rights)}</p><h2>${esc(artwork.title||'Untitled')}</h2><h3>${esc(artwork.artist||'Unknown artist')}</h3><p class="detail-meta">${esc(artwork.date_display||'')}${artwork.classification?' · '+esc(artwork.classification):''}${artwork.medium?' · '+esc(artwork.medium):''}</p>${artwork.description?`<p class="detail-desc">${esc(artwork.description)}</p>`:''}<p class="detail-rights">${imageNote}</p><h4>来源与版权</h4><div class="source-list">${data.sources.map(sourceRow).join('')}</div></div>`;
        previousFocus=document.activeElement;
        $('#modal').classList.remove('hidden');document.body.classList.add('modal-open');$('#closeModal').focus();
    }catch(error){$('#resultStatus').textContent='作品详情暂时不可用，请稍后重试。'}
}
function closeModal(){$('#modal').classList.add('hidden');document.body.classList.remove('modal-open');previousFocus?.focus()}
$('#go').onclick=()=>{currentQ=$('#q').value.trim();search(true)};$('#q').addEventListener('keydown',e=>{if(e.key==='Enter')$('#go').click()});$('#chips').onclick=e=>{if(e.target.tagName!=='BUTTON')return;currentQ=e.target.dataset.q;$('#q').value=currentQ;search(true)};$('#more').onclick=()=>search(false);$('#publicDomain').onchange=()=>search(true);$('#applyFilters').onclick=()=>search(true);document.querySelector('nav').onclick=e=>{const b=e.target.closest('.nav');if(b)setMode(b.dataset.mode)};document.addEventListener('click',e=>{const art=e.target.closest('.card[data-artwork-id]');if(art)openArtwork(art.dataset.artworkId)});$('#closeModal').onclick=closeModal;$('#modal').onclick=e=>{if(e.target.id==='modal')closeModal()};document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();if((e.key==='Enter'||e.key===' ')&&e.target.matches('[data-artwork-id]')){e.preventDefault();openArtwork(e.target.dataset.artworkId)}});
document.addEventListener('error',event=>{
    const img=event.target;
    if(!img.matches?.('.card img,.detail-image img'))return;
    let alternatives=[];
    try{alternatives=JSON.parse(img.dataset.fallbacks||'[]')}catch{}
    alternatives=[...new Set(alternatives.map(safeUrl).filter(url=>url&&url!==img.src))];
    const fallback=alternatives.shift();
    img.dataset.fallbacks=JSON.stringify(alternatives);
    if(fallback){
        img.src=fallback;
        if(img.closest('.detail-image'))$('.detail-rights').textContent='展示图片使用可用的公开来源，出处与许可见下方。';
        return;
    }
    const card=img.closest('.card');
    if(card){card.remove();return}
    document.querySelector(`.card[data-artwork-id="${img.dataset.artworkId}"]`)?.remove();
    closeModal();
    $('#resultStatus').textContent='这件作品的图片暂时无法加载，已隐藏，请浏览其他作品。';
},true);
loadStats().then(()=>search(true)).catch(()=>{$('#resultStatus').textContent='数据暂时不可用，请刷新页面重试。';$('#more').style.display='none'});
