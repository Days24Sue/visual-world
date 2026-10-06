const VisualWorldStaticApi = (() => {
    const artworkFields = ['title', 'artist', 'date_display', 'country', 'culture', 'classification', 'medium', 'style', 'subjects', 'tags', 'description'];
    const resourceFields = ['name', 'category', 'description', 'tags'];

    function fold(value) {
        return String(value ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase();
    }

    function matchesText(item, query, fields) {
        if (!query.trim()) return true;
        const tokens = fold(query).match(/[\p{L}\p{N}_-]+/gu) || [];
        if (!tokens.length) return false;
        const text = fold(item.search_text ?? fields.map(field => item[field] ?? '').join(' '));
        return tokens.every(token => text.includes(token));
    }

    function integer(value, fallback) {
        if (value === null || !/^-?\d+$/.test(value)) return fallback;
        const parsed = Number(value);
        return Number.isSafeInteger(parsed) ? parsed : fallback;
    }

    function paged(items, params, defaultLimit) {
        const limit = Math.max(1, Math.min(200, integer(params.get('limit'), defaultLimit)));
        const offset = Math.max(0, integer(params.get('offset'), 0));
        return { items: items.slice(offset, offset + limit), limit, offset };
    }

    function matchesFacets(artwork, params) {
        return ['artist', 'style', 'subject'].every(dimension =>
            !params.get(dimension) || (artwork[dimension + '_ids'] || []).includes(params.get(dimension))) &&
            (!params.get('kind')?.startsWith('kind-') || (artwork.kind_ids || []).includes(params.get('kind')));
    }

    function request(snapshot, path) {
        if (snapshot.version !== 1) throw new Error('Unsupported static snapshot');
        const url = new URL(path, 'https://visual-world.invalid');
        const params = url.searchParams;
        if (url.pathname === '/api/stats') return snapshot.stats;
        if (url.pathname === '/api/explore') return snapshot.explore;
        if (url.pathname === '/api/artwork') {
            return snapshot.details[params.get('id')] || { error: 'not found' };
        }
        if (url.pathname === '/api/search') {
            const source = params.get('source') || '';
            const kind = fold(params.get('kind') || '');
            const yearFrom = integer(params.get('year_from'), -100000);
            const yearTo = integer(params.get('year_to'), 100000);
            const items = yearFrom > yearTo ? [] : snapshot.artworks.filter(artwork => {
                if (source && !(artwork.source_ids || '').split('|').includes(source)) return false;
                if (!matchesFacets(artwork, params)) return false;
                if (kind && !kind.startsWith('kind-') && !fold(artwork.classification).includes(kind)) return false;
                if (!(artwork.thumbnail_url || artwork.image_url)) return false;
                if (params.get('public_domain') === '1' && artwork.public_domain !== 1) return false;
                if (yearFrom > -100000 && (artwork.year_end ?? artwork.year_start ?? -Infinity) < yearFrom) return false;
                if (yearTo < 100000 && (artwork.year_start ?? artwork.year_end ?? Infinity) > yearTo) return false;
                return matchesText(artwork, params.get('q') || '', artworkFields);
            });
            return { ...paged(items, params, 60), total: items.length };
        }
        if (url.pathname === '/api/resources') {
            const source = params.get('source') || '';
            const items = snapshot.resources.filter(resource =>
                (!source || resource.source_id === source) &&
                matchesText(resource, params.get('q') || '', resourceFields));
            return paged(items, params, 80);
        }
        throw new Error(`Unknown static API route: ${url.pathname}`);
    }

    function createClient(snapshotUrl, fetcher = globalThis.fetch) {
        let pending;
        let searchIndexPending;
        let searchSession;
        let explorePending;
        const cache = new Map();
        const detailPaths = new Map();
        const base = new URL(snapshotUrl, globalThis.location?.href || 'https://visual-world.invalid/');
        async function loadShard(path) {
            const url = new URL(path, base).href;
            if (!cache.has(url)) {
                const loading = fetcher(url).then(response => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    return response.json();
                }).catch(error => { cache.delete(url); throw error; });
                cache.set(url, loading);
                if (cache.size > 4) cache.delete(cache.keys().next().value);
            }
            return cache.get(url);
        }
        async function loadIndex(snapshot) {
            if (!searchIndexPending) {
                searchIndexPending = fetcher(new URL(snapshot.search_index_url, base).href).then(async response => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    const compressed = await response.arrayBuffer();
                    if (typeof DecompressionStream === 'undefined') throw new Error('This browser needs gzip decompression support');
                    const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'));
                    const index = await new Response(stream).json();
                    if (snapshot.search_index_version === 2) {
                        for (const row of index) row[1] = fold(row[1]);
                    }
                    return index;
                }).catch(error => { searchIndexPending = null; throw error; });
            }
            return searchIndexPending;
        }
        async function indexedSearch(snapshot, params, options) {
            const index = await loadIndex(snapshot);
            const filters = new URLSearchParams(params);
            filters.delete('offset'); filters.delete('limit'); filters.sort();
            const key = filters.toString();
            const limit = Math.max(1, Math.min(200, integer(params.get('limit'), 60)));
            const offset = Math.max(0, integer(params.get('offset'), 0));
            if (!searchSession || searchSession.key !== key) {
                const query = params.get('q')?.trim() || '';
                const tokens = fold(query).match(/[\p{L}\p{N}_-]+/gu) || [];
                const from = integer(params.get('year_from'), -100000);
                const to = integer(params.get('year_to'), 100000);
                const selected = [];
                for (let i = 0; i < index.length; i++) {
                    if (i % 20000 === 0) {
                        await new Promise(resolve => setTimeout(resolve, 0));
                        if (options.signal?.aborted) throw new DOMException('Search cancelled', 'AbortError');
                    }
                    const row = index[i];
                    if (from > to || (query && (!tokens.length || !tokens.every(token => row[1].includes(token))))) continue;
                    if (params.get('artist') && !row[3].includes(params.get('artist'))) continue;
                    if (params.get('style') && !row[6].includes(params.get('style'))) continue;
                    if (params.get('subject') && !row[7].includes(params.get('subject'))) continue;
                    if (params.get('kind') && (params.get('kind').startsWith('kind-') ? !row[8].includes(params.get('kind')) : !row[1].includes(fold(params.get('kind'))))) continue;
                    if (params.get('source') && !String(row[9] || '').split('|').includes(params.get('source'))) continue;
                    if (from > -100000 && (row[5] ?? row[4] ?? -Infinity) < from) continue;
                    if (to < 100000 && (row[4] ?? row[5] ?? Infinity) > to) continue;
                    selected.push(row);
                }
                const sort = params.get('sort');
                if (sort === 'oldest' || sort === 'newest') selected.sort((a, b) => {
                    const first = a[4] ?? a[5], second = b[4] ?? b[5];
                    if (first === null && second === null) return a[2] - b[2];
                    if (first === null) return 1;
                    if (second === null) return -1;
                    return (first - second) * (sort === 'newest' ? -1 : 1) || a[2] - b[2];
                });
                if (sort === 'title') selected.sort((a, b) => String(a[10] || '').localeCompare(String(b[10] || '')) || a[2] - b[2]);
                const counts = new Map();
                for (const row of selected) for (const artist of row[3]) counts.set(artist, (counts.get(artist) || 0) + 1);
                const artistCounts = [...counts].map(([id, count]) => ({ id, count })).sort((a, b) => b.count - a.count || a.id.localeCompare(b.id)).slice(0, 12);
                searchSession = { key, rows: selected, artistCounts };
            }
            const session = searchSession;
            const page = session.rows.slice(offset, offset + limit);
            const positions = [...new Set(page.map(row => row[0]))];
            const cards = new Map();
            // Bound parallel downloads to the shards containing this page.
            for (const position of positions) {
                if (options.signal?.aborted) throw new DOMException('Search cancelled', 'AbortError');
                for (const card of await loadShard(snapshot.chunks[position].url)) cards.set(card.id, card);
            }
            if (options.signal?.aborted) throw new DOMException('Search cancelled', 'AbortError');
            const items = page.map(row => cards.get(row[2])).filter(Boolean);
            if (items.length !== page.length) throw new Error('Search index and artwork shards do not match');
            for (const item of items) detailPaths.set(item.id, item.detail_path);
            return { items, total: session.rows.length, artist_counts: session.artistCounts, limit, offset };
        }
        return async (path, options = {}) => {
            if (!pending) {
                pending = fetcher(snapshotUrl, { cache: 'no-cache' }).then(response => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    return response.json();
                }).catch(error => {
                    pending = null;
                    throw error;
                });
            }
            const snapshot = await pending;
            if (snapshot.version === 1) return request(snapshot, path);
            if (snapshot.version !== 2) throw new Error('Unsupported static snapshot');
            const url = new URL(path, base);
            const params = url.searchParams;
            if (url.pathname === '/api/stats') return snapshot.stats;
            if (url.pathname === '/api/explore') {
                if (!explorePending) explorePending = loadShard(snapshot.explore_url).catch(error => { explorePending = null; throw error; });
                return explorePending;
            }
            if (url.pathname === '/api/resources') {
                return request({ ...snapshot, version: 1 }, path);
            }
            if (url.pathname === '/api/artwork') {
                const id = integer(params.get('id'), 0);
                const knownPath = detailPaths.get(id);
                if (knownPath) return (await loadShard(knownPath))[id] || { error: 'not found' };
                for (const chunk of snapshot.chunks) {
                    if (id < chunk.min_id || id > chunk.max_id) continue;
                    const detail = (await loadShard(chunk.details_url))[id];
                    if (detail) return detail;
                }
                return { error: 'not found' };
            }
            if (url.pathname !== '/api/search') throw new Error(`Unknown static API route: ${url.pathname}`);
            if (snapshot.search_index_version === 2) return indexedSearch(snapshot, params, options);
            const limit = Math.max(1, Math.min(200, integer(params.get('limit'), 60)));
            const offset = Math.max(0, integer(params.get('offset'), 0));
            const filters = new URLSearchParams(params);
            filters.delete('offset'); filters.delete('limit'); filters.sort();
            const key = filters.toString();
            if (!searchSession || searchSession.key !== key) {
                searchSession = { key, nextChunk: 0, items: [], complete: false };
            }
            const session = searchSession;
            const source = params.get('source');
            if (!session.candidateChunks && params.get('q')?.trim() && snapshot.search_index_url && typeof DecompressionStream !== 'undefined') {
                if (!searchIndexPending) {
                    searchIndexPending = fetcher(new URL(snapshot.search_index_url, base).href).then(async response => {
                        if (!response.ok) throw new Error(`HTTP ${response.status}`);
                        const decompressed = new Blob([await response.arrayBuffer()]).stream().pipeThrough(new DecompressionStream('gzip'));
                        return new Response(decompressed).json();
                    }).catch(error => { searchIndexPending = null; throw error; });
                }
                const index = await searchIndexPending;
                if (options.signal?.aborted) throw new DOMException('Search cancelled', 'AbortError');
                session.candidateChunks = new Set(index.filter(row => matchesText({ search_text: row[1] }, params.get('q'), artworkFields)).map(row => row[0]));
            }
            // Keep only matching cards for this query. Sequential pagination continues
            // from the last shard rather than downloading the whole corpus again.
            while (!session.complete && session.items.length < offset + limit) {
                if (options.signal?.aborted) throw new DOMException('Search cancelled', 'AbortError');
                if (session.nextChunk >= snapshot.chunks.length) { session.complete = true; break; }
                const position = session.nextChunk;
                const chunk = snapshot.chunks[position];
                if (session.candidateChunks && !session.candidateChunks.has(position)) { session.nextChunk++; continue; }
                if (source && !chunk.sources.includes(source)) { session.nextChunk++; continue; }
                const artworks = await loadShard(chunk.url);
                if (options.signal?.aborted) throw new DOMException('Search cancelled', 'AbortError');
                if (session.nextChunk !== position) continue;
                const localParams = new URLSearchParams(params);
                localParams.set('offset', '0'); localParams.set('limit', '200');
                // request() caps a page at 200, so filter every slice of the shard.
                for (let start = 0; start < artworks.length; start += 200) {
                    const result = request({ version: 1, artworks: artworks.slice(start, start + 200) }, '/api/search?' + localParams);
                    for (const artwork of result.items) {
                        detailPaths.set(artwork.id, artwork.detail_path);
                        session.items.push(artwork);
                    }
                }
                session.nextChunk++;
            }
            return { items: session.items.slice(offset, offset + limit), limit, offset };
        };
    }

    return { request, createClient };
})();

if (typeof window !== 'undefined') window.VisualWorldStaticApi = VisualWorldStaticApi;
if (typeof module !== 'undefined') module.exports = VisualWorldStaticApi;
