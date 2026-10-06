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
        const text = fields.map(field => fold(item[field])).join(' ');
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
                if (params.get('with_images') === '1' && !(artwork.thumbnail_url || artwork.image_url)) return false;
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
        return async path => {
            if (!pending) {
                pending = fetcher(snapshotUrl).then(response => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    return response.json();
                }).catch(error => {
                    pending = null;
                    throw error;
                });
            }
            return request(await pending, path);
        };
    }

    return { request, createClient };
})();

if (typeof window !== 'undefined') window.VisualWorldStaticApi = VisualWorldStaticApi;
if (typeof module !== 'undefined') module.exports = VisualWorldStaticApi;
