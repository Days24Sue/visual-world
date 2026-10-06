const test = require('node:test');
const assert = require('node:assert/strict');
const { request, createClient } = require('../web/static_api.js');

const snapshot = {
    version: 1,
    stats: { canonical: 2, resources: 1, snapshot_at: '2026-10-06T00:00:00+00:00' },
    artworks: [
        { id: 1, title: 'Open Painting', artist: 'Émile', source_ids: 'met|moma', year_start: 1888, year_end: 1888, public_domain: 1, image_url: 'https://example.com/open.jpg' },
        { id: 2, title: 'Other Work', artist: 'Someone', source_ids: 'tate', year_start: null, year_end: null, public_domain: 0, image_url: null },
    ],
    resources: [{ id: 1, source_id: 'art_datasets', name: 'Open Dataset', category: 'Dataset' }],
    details: { 1: { artwork: { id: 1 }, sources: [{ source_id: 'met' }, { source_id: 'moma' }] } },
};

test('static search applies source, year, image, rights and text filters', () => {
    const result = request(snapshot, '/api/search?source=moma&year_from=1800&year_to=1900&with_images=1&public_domain=1&q=Emile');
    assert.deepEqual(result.items.map(item => item.id), [1]);
    assert.equal(request(snapshot, '/api/search?source=met%25').items.length, 0);
    assert.equal(request(snapshot, '/api/search?year_from=1900&year_to=1800').items.length, 0);
    assert.equal(request(snapshot, '/api/search?q=!!!').items.length, 0);
});

test('static search paginates and preserves artwork details', () => {
    assert.deepEqual(request(snapshot, '/api/search?limit=1&offset=1').items.map(item => item.id), []);
    assert.equal(request(snapshot, '/api/search?source=tate').items.length, 0);
    assert.equal(request(snapshot, '/api/artwork?id=1').sources.length, 2);
    assert.equal(request(snapshot, '/api/artwork?id=999').error, 'not found');
    assert.equal(request(snapshot, '/api/resources?source=art_datasets&q=dataset').items.length, 1);
});

test('static client loads the snapshot only once', async () => {
    let calls = 0;
    const client = createClient('./snapshot.json', async () => {
        calls += 1;
        return { ok: true, json: async () => snapshot };
    });
    await Promise.all([client('/api/stats'), client('/api/search')]);
    assert.equal(calls, 1);
});

test('sharded client browses lazily, paginates across shards and loads matching details', async () => {
    const cards = Array.from({ length: 5 }, (_, i) => ({
        id: i + 1, title: `Painting ${i + 1}`, artist: 'Artist', source_ids: i < 3 ? 'nga' : 'artic',
        public_domain: 1, image_url: `https://example.com/${i + 1}.jpg`,
        search_text: i === 4 ? 'Rare landscape Émile' : `Painting ${i + 1}`,
        detail_path: `data/details-${Math.floor(i / 3)}.json`,
    }));
    const manifest = { version: 2, stats: { canonical: 5 }, resources: [], chunks: [
        { url: 'data/index-0.json', details_url: 'data/details-0.json', count: 3, sources: ['nga'], min_id: 1, max_id: 3 },
        { url: 'data/index-1.json', details_url: 'data/details-1.json', count: 2, sources: ['artic'], min_id: 4, max_id: 5 },
    ] };
    const files = {
        './snapshot.json': manifest,
        'https://visual-world.invalid/data/index-0.json': cards.slice(0, 3),
        'https://visual-world.invalid/data/index-1.json': cards.slice(3),
        'https://visual-world.invalid/data/details-1.json': { 5: { artwork: cards[4], sources: [{ source_id: 'artic' }] } },
    };
    const calls = [];
    const client = createClient('./snapshot.json', async url => {
        calls.push(url);
        assert.ok(url in files, `Unexpected fetch: ${url}`);
        return { ok: true, json: async () => files[url] };
    });
    assert.equal((await client('/api/stats')).canonical, 5);
    assert.equal(calls.length, 1);
    assert.deepEqual((await client('/api/search?limit=2')).items.map(a => a.id), [1, 2]);
    assert.equal(calls.length, 2);
    assert.deepEqual((await client('/api/search?limit=2&offset=2')).items.map(a => a.id), [3, 4]);
    assert.deepEqual((await client('/api/search?q=Emile')).items.map(a => a.id), [5]);
    assert.equal((await client('/api/artwork?id=5')).sources[0].source_id, 'artic');
    assert.equal(calls.filter(url => url.endsWith('index-0.json')).length, 1);
    assert.equal(calls.filter(url => url.endsWith('index-1.json')).length, 1);
});

test('sharded search does not truncate a shard at the per-request page limit', async () => {
    const cards = Array.from({ length: 501 }, (_, i) => ({ id: i, title: `Work ${i}`, image_url: 'https://example.com/image.jpg', source_ids: 'nga' }));
    const manifest = { version: 2, chunks: [{ url: 'data/index.json', sources: ['nga'], min_id: 0, max_id: 500 }] };
    const client = createClient('./snapshot.json', async url => ({ ok: true, json: async () => url === './snapshot.json' ? manifest : cards }));
    assert.deepEqual((await client('/api/search?limit=2&offset=499')).items.map(a => a.id), [499, 500]);
});

test('failed shards can be retried without skipping matching works', async () => {
    const manifest = { version: 2, chunks: [{ url: 'data/index.json', sources: ['nga'], min_id: 1, max_id: 1 }] };
    let attempts = 0;
    const client = createClient('./snapshot.json', async url => {
        if (url === './snapshot.json') return { ok: true, json: async () => manifest };
        attempts++;
        if (attempts === 1) return { ok: false, status: 503 };
        return { ok: true, json: async () => [{ id: 1, image_url: 'https://example.com/open.jpg' }] };
    });
    await assert.rejects(client('/api/search'), /HTTP 503/);
    assert.equal((await client('/api/search')).items[0].id, 1);
});

test('compressed text index skips unrelated chunks and is reused across searches', async () => {
    const { gzipSync } = require('node:zlib');
    const manifest = { version: 2, search_index_url: 'data/search.json.gz', chunks: [
        { url: 'data/first.json', sources: ['nga'], min_id: 1, max_id: 1 },
        { url: 'data/second.json', sources: ['nga'], min_id: 2, max_id: 2 },
    ] };
    const compressed = gzipSync(JSON.stringify([[0, 'unrelated work'], [1, 'Landscape Monet 日本']]));
    const calls = [];
    const client = createClient('./snapshot.json', async url => {
        calls.push(url);
        if (url === './snapshot.json') return { ok: true, json: async () => manifest };
        if (url.endsWith('search.json.gz')) return { ok: true, arrayBuffer: async () => compressed };
        assert.ok(url.endsWith('second.json'), 'Unrelated shard should not load');
        return { ok: true, json: async () => [{ id: 2, image_url: 'https://example.com/open.jpg', search_text: 'Landscape Monet 日本' }] };
    });
    assert.deepEqual((await client('/api/search?q=Monet')).items.map(a => a.id), [2]);
    assert.deepEqual((await client('/api/search?q=日本')).items.map(a => a.id), [2]);
    assert.equal(calls.filter(url => url.endsWith('search.json.gz')).length, 1);
});
