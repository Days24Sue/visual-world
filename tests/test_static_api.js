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
    assert.deepEqual(request(snapshot, '/api/search?limit=1&offset=1').items.map(item => item.id), [2]);
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
