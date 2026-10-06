const cfg = window.VISUAL_WORLD_CONFIG || {};
const $ = selector => document.querySelector(selector);
const fmt = number => new Intl.NumberFormat('zh-CN').format(number || 0);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const fold = value => String(value || '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
function safeUrl(value) { try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : ''; } catch { return ''; } }
const staticClient = cfg.snapshotUrl ? window.VisualWorldStaticApi.createClient(cfg.snapshotUrl) : null;
async function getJson(path, options = {}) {
    if (staticClient) return staticClient(path, options);
    const response = await fetch(path, options);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}
const FILTERS = ['q', 'artist', 'style', 'subject', 'kind', 'year_from', 'year_to', 'sort'];
const LIMIT = 48;
let stats, catalog, artistMap, termMap, state = {}, controller, version = 0, offset = 0, directoryOffset = 0, previousFocus, detailVersion = 0;
function name(artist) { return artist?.name_zh || artist?.name || '未署名创作者'; }
function life(artist) { return artist.birth_year != null ? artist.death_year != null ? `${artist.birth_year}–${artist.death_year}` : `生于 ${artist.birth_year}` : ''; }
function label(term) { return term?.label_zh || term?.label || ''; }
function route(view, values = {}) {
    const params = new URLSearchParams();
    for (const key of FILTERS) if (values[key] !== undefined && values[key] !== '') params.set(key, values[key]);
    return '#' + view + (params.size ? '?' + params : '');
}
function readRoute() {
    const [view, query = ''] = location.hash.slice(1).split('?');
    const params = new URLSearchParams(query);
    const result = { view: ['home', 'artists', 'periods', 'styles', 'subjects', 'works'].includes(view) ? view : 'home' };
    for (const key of FILTERS) result[key] = params.get(key) || '';
    return result;
}
function navigate(view, values = {}) {
    const target = route(view, values);
    if (location.hash === target) renderRoute(); else location.hash = target;
}
function artistMatches(artist, query) { return fold(artist.aliases.join(' ')).includes(fold(query.trim())); }
function artistLink(id, text) { const artist = artistMap.get(id); return artist ? `<a href="${esc(route('works', { artist: id }))}">${esc(text || name(artist))}</a>` : ''; }
function option(value, text) { return `<option value="${esc(value)}">${esc(text)}</option>`; }
function renderHome() {
    const featured = catalog.featured_artists.map(id => artistMap.get(id)).filter(Boolean);
    const cover = featured.find(artist => safeUrl(artist.image_url));
    const entries = [['artists', '找画家', '从熟悉的名字，走进一位创作者的世界。'], ['periods', '看时期', '沿创作年代，寻找同时期的作品与画家。'], ['styles', '逛流派', '从印象派到立体主义，认识不同的艺术语言。'], ['subjects', '选主题', '风景、肖像、花卉，从你感兴趣的内容开始。']];
    const homeLinks = (items, dimension) => items.map(term => `<a href="${esc(route('works', { [dimension]: term.id }))}">${esc(label(term))}<small>${fmt(term.count)} 件</small></a>`).join('');
    const styles = catalog.styles.filter(term => term.label_zh).slice(0, 10);
    const subjects = catalog.subjects.filter(term => term.label_zh).slice(0, 10);
    $('#home').innerHTML = `<div class="hero"><div><p class="eyebrow">A PLACE TO DISCOVER ART · 世界艺术探索馆</p><h1>从你感兴趣的地方，<br>走进艺术。</h1><p class="sub">寻找一位画家，探索一段时期，或沿着风景、肖像与色彩发现作品。这里把开放馆藏整理成可以循着线索浏览的艺术世界。</p><a class="text-link" href="#works">浏览完整作品库 →</a><div class="hero-stats"><div><strong>${fmt(stats.canonical)}</strong><span>件可查看作品</span></div><div><strong>${fmt(catalog.artists.length)}</strong><span>位创作者 / 署名</span></div></div></div>${cover ? `<figure><img class="discovery-image" referrerpolicy="no-referrer" src="${esc(safeUrl(cover.hero_image_url || cover.image_url))}" alt="${esc(cover.sample_title)}"><figcaption>${esc(name(cover))} · ${esc(cover.sample_title)}<a href="${esc(route('works', { artist: cover.id }))}">查看作品</a></figcaption></figure>` : ''}</div><div class="entry-links">${entries.map(([view, title, intro]) => `<a href="#${view}"><h3>${title} →</h3><p>${intro}</p></a>`).join('')}</div><section class="home-section"><div class="section-head"><h2>从一位画家开始</h2><a href="#artists" class="text-link">全部画家与创作者 →</a></div><div class="artist-featured">${featured.slice(0, 8).map(artist => `<a href="${esc(route('works', { artist: artist.id }))}">${safeUrl(artist.image_url) ? `<img class="discovery-image" loading="lazy" referrerpolicy="no-referrer" src="${esc(safeUrl(artist.image_url))}" alt="${esc(artist.sample_title)}">` : ''}<h3>${esc(name(artist))}</h3><p>${esc(artist.name)}${life(artist) ? ' · ' + esc(life(artist)) : ''}</p><small>本库 ${fmt(artist.count)} 件作品</small></a>`).join('')}</div></section><section class="home-section"><div class="section-head"><h2>沿着时间探索</h2><a href="#periods" class="text-link">查看时期 →</a></div><div class="browse-links">${catalog.periods.map(period => `<a href="${esc(route('works', { year_from: period.year_from, year_to: period.year_to }))}">${esc(period.label)}<small>${fmt(period.count)} 件</small></a>`).join('')}</div></section>${styles.length ? `<section class="home-section"><div class="section-head"><h2>认识不同的艺术语言</h2><a href="#styles" class="text-link">全部风格与流派 →</a></div><div class="browse-links">${homeLinks(styles, 'style')}</div></section>` : ''}${subjects.length ? `<section class="home-section"><div class="section-head"><h2>从一个主题出发</h2><a href="#subjects" class="text-link">全部主题 →</a></div><div class="browse-links">${homeLinks(subjects, 'subject')}</div></section>` : ''}`;
}
function renderDirectory(reset = true) {
    if (reset) { directoryOffset = 0; $('#directoryGrid').innerHTML = ''; }
    const isArtist = state.view === 'artists';
    const text = $('#directorySearch').value.trim();
    let items = catalog[state.view] || [];
    items = items.filter(item => isArtist ? artistMatches(item, text) : fold([label(item), item.label].join(' ')).includes(fold(text)));
    const sorting = $('#directorySort').value;
    items = [...items].sort((a, b) => {
        if (sorting === 'name') return (isArtist ? name(a) : label(a)).localeCompare(isArtist ? name(b) : label(b), 'zh-CN');
        if (sorting === 'time' && isArtist) return (a.birth_year ?? Infinity) - (b.birth_year ?? Infinity) || b.count - a.count;
        return Number(Boolean(isArtist ? b.name_zh : b.label_zh)) - Number(Boolean(isArtist ? a.name_zh : a.label_zh)) || b.count - a.count;
    });
    if (state.view === 'periods') items.sort((a, b) => a.year_from - b.year_from);
    const page = items.slice(directoryOffset, directoryOffset + 90);
    $('#directoryGrid').className = isArtist ? 'artist-directory' : 'facet-directory';
    $('#directoryGrid').insertAdjacentHTML('beforeend', page.map(item => {
        if (isArtist) return `<a class="artist-entry" href="${esc(route('works', { artist: item.id }))}"><h3>${esc(name(item))}</h3><p>${esc(item.name)}${life(item) ? ' · ' + esc(life(item)) : ''}</p><small>本库可查看 ${fmt(item.count)} 件作品 →</small></a>`;
        const values = state.view === 'periods' ? { year_from: item.year_from, year_to: item.year_to } : { [state.view === 'styles' ? 'style' : 'subject']: item.id };
        return `<a class="facet-entry" href="${esc(route('works', values))}"><div><h3>${esc(label(item))}</h3>${item.label_zh ? `<p>${esc(item.label)}</p>` : ''}</div><small>${fmt(item.count)} 件 →</small></a>`;
    }).join(''));
    directoryOffset += page.length;
    $('#directoryStatus').textContent = items.length ? `共 ${fmt(items.length)} ${isArtist ? '位创作者 / 署名' : '项'}，已显示 ${fmt(directoryOffset)} ${isArtist ? '位' : '项'}` : '没有找到匹配内容，请换一个名字或关键词。';
    $('#directoryMore').classList.toggle('hidden', directoryOffset >= items.length);
}
function populateArtists(query = '') {
    const selected = state.artist;
    const items = catalog.artists.filter(artist => artistMatches(artist, query)).slice(0, 120);
    if (selected && artistMap.has(selected) && !items.some(artist => artist.id === selected)) items.unshift(artistMap.get(selected));
    $('#artistFilter').innerHTML = option('', '全部创作者') + items.map(artist => option(artist.id, `${name(artist)} · ${fmt(artist.count)} 件`)).join('');
    $('#artistFilter').value = selected;
}
function syncFilters() {
    $('#artistLookup').value = state.artist ? name(artistMap.get(state.artist)) : '';
    populateArtists($('#artistLookup').value);
    for (const dimension of ['style', 'subject', 'kind', 'sort']) $(`#${dimension}Filter`).value = state[dimension] || (dimension === 'sort' ? 'relevance' : '');
    $('#yearFrom').value = state.year_from;
    $('#yearTo').value = state.year_to;
    $('#periodFilter').value = catalog.periods.find(period => String(period.year_from) === state.year_from && String(period.year_to) === state.year_to)?.id || '';
    const active = [];
    for (const dimension of ['artist', 'style', 'subject', 'kind']) {
        if (!state[dimension]) continue;
        const value = dimension === 'artist' ? name(artistMap.get(state.artist)) : label(termMap.get(state[dimension]));
        const next = { ...state, [dimension]: '' };
        active.push(`<a href="${esc(route('works', next))}" aria-label="取消${esc(value)}筛选">${esc(value || '所选条件')} ×</a>`);
    }
    if (state.year_from || state.year_to) active.push(`<a href="${esc(route('works', { ...state, year_from: '', year_to: '' }))}">年代 ${esc(state.year_from || '不限')}–${esc(state.year_to || '不限')} ×</a>`);
    if (state.q) active.push(`<a href="${esc(route('works', { ...state, q: '' }))}">搜索：${esc(state.q)} ×</a>`);
    $('#activeFilters').innerHTML = active.join('');
    $('#clearFilters').classList.toggle('hidden', !FILTERS.some(key => state[key] && !(key === 'sort' && state[key] === 'relevance')));
}
function renderProfile() {
    const artist = artistMap.get(state.artist);
    $('#profile').classList.toggle('hidden', !artist);
    if (!artist) return;
    const nationality = catalog.translations?.[artist.nationality] || artist.nationality;
    $('#profile').innerHTML = `<a href="#artists" class="text-link">← 全部画家与创作者</a><h1>${esc(name(artist))}</h1>${artist.name_zh ? `<p class="original-name">${esc(artist.name)}</p>` : ''}<div class="profile-facts">${life(artist) ? `<p><span>生卒年</span>${esc(life(artist))}</p>` : ''}${nationality ? `<p><span>资料记录的国籍</span>${esc(nationality)}</p>` : ''}<p><span>本库可查看作品</span>${fmt(artist.count)} 件</p>${artist.first_work_year != null ? `<p><span>库内作品创作年代</span>${esc(artist.first_work_year)}–${esc(artist.last_work_year ?? artist.first_work_year)}</p>` : ''}</div>${artist.movements.length ? `<p>馆内作品关联风格：${esc(artist.movements.join('、'))}</p>` : ''}<p class="profile-note">这里展示本库有公开图片的作品，并非画家的全部创作。${safeUrl(artist.info_source) ? `生卒年、国籍资料来自 <a href="${esc(safeUrl(artist.info_source))}" target="_blank" rel="noopener noreferrer">PainterPalette</a>（<a href="./licenses/PainterPalette.txt" target="_blank" rel="noopener">MIT 许可</a>）；中文姓名由本站整理。` : '作者署名与年代信息来自馆藏记录；中文姓名由本站整理。'}</p>`;
}
function artworkCard(artwork) {
    const image = safeUrl(artwork.thumbnail_url || artwork.image_url);
    const artistLinks = (artwork.artist_ids || []).map(id => artistLink(id)).filter(Boolean).join('、');
    const fallback = [artwork.image_url, ...(artwork.image_alternatives || [])];
    return `<article class="card" data-artwork-id="${artwork.id}" tabindex="0" role="button" aria-label="查看作品：${esc(artwork.title || '未命名作品')}"><div class="art"><img referrerpolicy="no-referrer" loading="lazy" src="${esc(image)}" alt="${esc(artwork.title || '未命名作品')}" data-fallbacks="${esc(JSON.stringify(fallback))}"></div><div class="meta"><h3>${esc(artwork.title || '未命名作品')}</h3><p>${artistLinks || esc(artwork.artist || '未署名创作者')}</p><p>${esc(artwork.date_display || '年代未注明')}</p><p class="medium">${esc(artwork.medium || artwork.classification || '')}</p></div></article>`;
}
async function search(reset = false) {
    if (reset) {
        controller?.abort(); controller = new AbortController(); version++; offset = 0;
        $('#grid').innerHTML = ''; $('#resultCount').textContent = ''; $('#relatedArtists').innerHTML = '';
    }
    const current = version;
    const params = new URLSearchParams({ limit: LIMIT, offset, with_images: '1' });
    for (const key of FILTERS) if (state[key]) params.set(key, state[key]);
    $('#resultStatus').textContent = '正在检索完整作品库，首次加载索引可能需要一点时间…';
    $('#more').disabled = true;
    const artist = artistMap.get(state.artist);
    const period = catalog.periods.find(item => String(item.year_from) === state.year_from && String(item.year_to) === state.year_to);
    $('#resultTitle').textContent = artist ? `${name(artist)}的作品` : state.q ? `“${state.q}”的搜索结果` : state.style ? label(termMap.get(state.style)) : state.subject ? label(termMap.get(state.subject)) : period ? `${period.label}的作品` : '全部作品';
    try {
        const data = await getJson('/api/search?' + params, { signal: controller.signal });
        if (current !== version || state.view !== 'works') return;
        const items = data.items || [];
        $('#grid').insertAdjacentHTML('beforeend', items.map(artworkCard).join(''));
        offset += items.length;
        $('#resultCount').textContent = `共 ${fmt(data.total)} 件作品 · 已加载 ${fmt(offset)} 件`;
        $('#resultStatus').textContent = data.total === 0 ? '没有符合条件的作品。可以取消部分筛选，或尝试作者原名。' : '';
        $('#more').classList.toggle('hidden', offset >= data.total);
        $('#relatedArtists').innerHTML = !state.artist && data.artist_counts?.length ? `<h3>${state.year_from || state.year_to ? '这段时期的创作者' : '结果中的创作者'}</h3>${data.artist_counts.filter(item => artistMap.has(item.id)).map(item => `<a href="${esc(route('works', { ...state, artist: item.id }))}">${esc(name(artistMap.get(item.id)))}<span>${fmt(item.count)} 件</span></a>`).join('')}` : '';
    } catch (error) {
        if (error.name !== 'AbortError' && current === version) { $('#resultStatus').textContent = '检索暂时没有完成，请重试。'; $('#more').classList.add('hidden'); }
    } finally { if (current === version) $('#more').disabled = false; }
}
function renderRoute() {
    controller?.abort(); version++; detailVersion++; closeModal(false);
    state = readRoute();
    $('#q').value = state.q;
    $('#suggestions').classList.add('hidden');
    document.querySelectorAll('nav a').forEach(link => link.classList.toggle('active', link.dataset.view === state.view));
    $('#home').classList.toggle('hidden', state.view !== 'home');
    $('#directory').classList.toggle('hidden', !['artists', 'periods', 'styles', 'subjects'].includes(state.view));
    $('#library').classList.toggle('hidden', state.view !== 'works');
    if (state.view === 'home') renderHome();
    else if (state.view === 'works') { syncFilters(); renderProfile(); search(true); }
    else {
        const copy = {
            artists: ['ARTISTS · 画家与创作者', '寻找一位画家', '用中文名或原名检索。目录包含馆藏中的画家及其他创作者；每个名字都能进入对应的作品页。'],
            periods: ['PERIODS · 创作年代', '沿着时间探索', '按作品的创作年代浏览，进入时期后可继续查看其中的画家。跨年代作品可能出现在多个时期；这不是按流派划定的艺术史分期。'],
            styles: ['STYLES · 风格与流派', '认识不同的艺术语言', '使用馆方提供的风格与流派标签。没有标签的作品仍可在完整作品库中找到。'],
            subjects: ['SUBJECTS · 内容主题', '从一个主题出发', '按馆藏标注的画面内容探索。已整理常见中文主题，其他标签保留原文。'],
        }[state.view];
        $('#directoryEyebrow').textContent = copy[0]; $('#directoryTitle').textContent = copy[1]; $('#directoryIntro').textContent = copy[2];
        $('#directorySearch').value = ''; $('#directorySearch').placeholder = state.view === 'artists' ? '输入画家中文名或原名，例如：毕加索' : '输入名称，例如：印象派、风景';
        $('#directorySort').value = 'count'; $('#directorySort').querySelector('[value="time"]').hidden = state.view !== 'artists';
        $('#directorySortLabel').classList.toggle('hidden', state.view === 'periods'); renderDirectory();
    }
}
function sourceRow(source) {
    const url = safeUrl(source.object_url) || safeUrl(source.source_homepage);
    return `<div class="source-row"><b>${esc(source.source_name || source.source_id)}</b><span>${esc(source.accession_number || source.source_object_id || '')}</span><span>图像许可：${esc(source.image_license || '未注明')} · 元数据：${esc(source.metadata_license || '未注明')}</span>${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">馆方出处 ↗</a>` : ''}</div>`;
}
async function openArtwork(id) {
    const requestVersion = ++detailVersion;
    previousFocus = document.activeElement;
    try {
        const data = await getJson('/api/artwork?id=' + encodeURIComponent(id));
        if (requestVersion !== detailVersion || !data.artwork) return;
        const artwork = data.artwork, image = safeUrl(artwork.image_url || artwork.thumbnail_url);
        if (!image) return;
        const tags = ['style', 'subject'].flatMap(dimension => (artwork[dimension + '_ids'] || []).map(key => `<a href="${esc(route('works', { [dimension]: key }))}">${esc(label(termMap.get(key)))}</a>`)).slice(0, 20);
        const artists = (artwork.artist_ids || []).map(key => artistLink(key)).filter(Boolean).join('、');
        const fallback = [artwork.thumbnail_url, ...data.sources.filter(source => source.public_domain === 1).flatMap(source => [source.image_url, source.thumbnail_url])];
        $('#modalBody').innerHTML = `<div class="detail-image"><img referrerpolicy="no-referrer" src="${esc(image)}" data-fallbacks="${esc(JSON.stringify(fallback))}" data-artwork-id="${artwork.id}" alt="${esc(artwork.title || '未命名作品')}"></div><div class="detail-copy"><p class="eyebrow">ARTWORK · 作品详情</p><h2>${esc(artwork.title || '未命名作品')}</h2><h3>${artists || esc(artwork.artist || '未署名创作者')}</h3><p class="detail-meta">${esc(artwork.date_display || '年代未注明')} · ${esc(artwork.classification || '')}<br>${esc(artwork.medium || '')}</p><div class="detail-tags">${tags.join('')}</div>${artwork.description ? `<p class="detail-desc">${esc(artwork.description)}</p>` : ''}<p class="detail-rights">图片来自馆方标注的公开来源。作品和图片的许可信息见下方。</p><details><summary>馆藏出处与许可</summary>${data.sources.map(sourceRow).join('')}</details></div>`;
        $('#modal').classList.remove('hidden'); document.body.classList.add('modal-open'); $('#closeModal').focus();
    } catch { if (requestVersion === detailVersion) $('#resultStatus').textContent = '作品详情暂时无法加载，请重试。'; }
}
function closeModal(restore = true) {
    detailVersion++; $('#modal').classList.add('hidden'); document.body.classList.remove('modal-open');
    if (restore && previousFocus?.isConnected) previousFocus.focus();
}
$('#searchForm').addEventListener('submit', event => { event.preventDefault(); navigate('works', { q: $('#q').value.trim() }); });
$('#q').addEventListener('input', () => {
    if (!catalog) return;
    const query = $('#q').value.trim();
    const matches = query ? catalog.artists.filter(artist => artistMatches(artist, query)).slice(0, 6) : [];
    $('#suggestions').innerHTML = matches.map(artist => `<a href="${esc(route('works', { artist: artist.id }))}"><span>${esc(name(artist))}${artist.name_zh ? ` <small>${esc(artist.name)}</small>` : ''}</span><small>${fmt(artist.count)} 件</small></a>`).join('');
    $('#suggestions').classList.toggle('hidden', matches.length === 0);
});
$('#directorySearch').addEventListener('input', () => renderDirectory());
$('#directorySort').addEventListener('change', () => renderDirectory());
$('#directoryMore').addEventListener('click', () => renderDirectory(false));
$('#artistLookup').addEventListener('input', () => populateArtists($('#artistLookup').value));
$('#periodFilter').addEventListener('change', () => {
    const period = catalog.periods.find(item => item.id === $('#periodFilter').value);
    $('#yearFrom').value = period?.year_from ?? ''; $('#yearTo').value = period?.year_to ?? '';
});
for (const input of ['#yearFrom', '#yearTo']) $(input).addEventListener('input', () => { $('#periodFilter').value = ''; });
$('#filterForm').addEventListener('submit', event => {
    event.preventDefault();
    const from = $('#yearFrom').value.trim(), to = $('#yearTo').value.trim();
    if (from && to && Number(from) > Number(to)) { $('#resultStatus').textContent = '起始年份不能晚于结束年份。'; $('#yearFrom').focus(); return; }
    const values = { q: state.q, artist: $('#artistFilter').value, year_from: from, year_to: to };
    for (const dimension of ['style', 'subject', 'kind', 'sort']) values[dimension] = $(`#${dimension}Filter`).value;
    navigate('works', values);
});
$('#more').addEventListener('click', () => search());
$('#closeModal').addEventListener('click', () => closeModal());
$('#modal').addEventListener('click', event => { if (event.target === $('#modal')) closeModal(); });
document.addEventListener('click', event => {
    if (!event.target.closest('.search-bar')) $('#suggestions').classList.add('hidden');
    if (event.target.closest('#modal a')?.hash) closeModal(false);
    const card = event.target.closest('.card[data-artwork-id]');
    if (card && !event.target.closest('a')) openArtwork(card.dataset.artworkId);
});
document.addEventListener('keydown', event => {
    if (event.key === 'Escape') { closeModal(); $('#suggestions').classList.add('hidden'); }
    if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('.card')) { event.preventDefault(); openArtwork(event.target.dataset.artworkId); }
    if (event.key === 'Tab' && !$('#modal').classList.contains('hidden')) {
        const controls = [...$('#modal').querySelectorAll('button,a[href],summary')].filter(element => element.getClientRects().length);
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
});
document.addEventListener('error', event => {
    const image = event.target;
    if (image.matches?.('.discovery-image')) { image.remove(); return; }
    if (!image.matches?.('.card img,.detail-image img')) return;
    let alternatives = [];
    try { alternatives = JSON.parse(image.dataset.fallbacks || '[]'); } catch {}
    alternatives = [...new Set(alternatives.map(safeUrl).filter(url => url && url !== image.src))];
    const fallback = alternatives.shift(); image.dataset.fallbacks = JSON.stringify(alternatives);
    if (fallback) { image.src = fallback; return; }
    const card = image.closest('.card');
    if (card) { card.remove(); return; }
    document.querySelector(`.card[data-artwork-id="${image.dataset.artworkId}"]`)?.remove(); closeModal();
    $('#resultStatus').textContent = '这件作品的公开图片暂时不可用，已隐藏，请浏览其他作品。';
}, true);
window.addEventListener('hashchange', () => { if (catalog) { renderRoute(); window.scrollTo({ top: 0, behavior: 'instant' }); } });
Promise.all([getJson('/api/stats'), getJson('/api/explore')]).then(([statistics, exploration]) => {
    stats = statistics; catalog = exploration;
    artistMap = new Map(catalog.artists.map(artist => [artist.id, artist]));
    termMap = new Map([...catalog.styles, ...catalog.subjects, ...catalog.kinds].map(term => [term.id, term]));
    for (const dimension of ['style', 'subject', 'kind']) {
        const items = catalog[{ style: 'styles', subject: 'subjects', kind: 'kinds' }[dimension]];
        $(`#${dimension}Filter`).insertAdjacentHTML('beforeend', [...items].sort((a, b) => Number(Boolean(b.label_zh)) - Number(Boolean(a.label_zh)) || b.count - a.count).map(term => option(term.id, `${label(term)} · ${fmt(term.count)} 件`)).join(''));
    }
    $('#periodFilter').insertAdjacentHTML('beforeend', catalog.periods.map(period => option(period.id, period.label)).join(''));
    $('#snapshotNote').textContent = '馆藏图像与文字的权利信息见作品详情。' + (stats.snapshot_at ? ` 数据更新：${new Date(stats.snapshot_at).toLocaleDateString('zh-CN')}` : '');
    $('#appStatus').textContent = ''; renderRoute();
}).catch(() => { $('#appStatus').textContent = '探索目录暂时无法加载，请刷新重试。'; });
