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

    function request(snapshot, path) {
        if (snapshot.version !== 1) throw new Error('Unsupported static snapshot');
        const url = new URL(path, 'https://visual-world.invalid');
        const params = url.searchParams;
        if (url.pathname === '/api/stats') return snapshot.stats;
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
                if (kind && !fold(artwork.classification).includes(kind)) return false;
                if (!(artwork.thumbnail_url || artwork.image_url)) return false;
                if (params.get('public_domain') === '1' && artwork.public_domain !== 1) return false;
                if (yearFrom > -100000 && (artwork.year_end ?? artwork.year_start ?? -Infinity) < yearFrom) return false;
                if (yearTo < 100000 && (artwork.year_start ?? artwork.year_end ?? Infinity) > yearTo) return false;
                return matchesText(artwork, params.get('q') || '', artworkFields);
            });
            return paged(items, params, 60);
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
