import json
import gzip
import tempfile
import unittest
from pathlib import Path

from canonicalize import rebuild
from connectors.common import upsert
from export_static import export_site
from schema import init_db


class StaticExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'test.db'
        self.output = Path(self.tmp.name) / 'site'
        self.conn = init_db(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_export_preserves_provenance_without_restricted_images(self):
        base = {'title': 'Shared Work', 'artist': 'Artist', 'year_start': 1888}
        upsert(self.conn, {**base, 'source_id': 'met', 'source_object_id': '1',
                           'public_domain': 1, 'image_url': 'https://example.com/open.jpg',
                           'metadata_license': 'CC0', 'image_license': 'CC0'})
        upsert(self.conn, {**base, 'source_id': 'moma', 'source_object_id': '2',
                           'public_domain': 0, 'image_url': 'https://example.com/restricted.jpg',
                           'metadata_license': 'CC0', 'image_license': 'restricted'})
        self.conn.execute('''INSERT INTO resources(source_id,source_resource_id,name,url,category)
            VALUES(?,?,?,?,?)''', ('art_datasets', 'example', 'Example', 'https://example.com', 'Dataset'))
        self.conn.commit()
        rebuild(self.conn)

        snapshot = export_site(self.db_path, self.output)
        self.assertEqual(snapshot['stats']['total'], 2)
        self.assertEqual(snapshot['stats']['canonical'], 1)
        self.assertEqual(snapshot['stats']['duplicates'], 1)
        self.assertEqual(len(snapshot['resources']), 1)
        cards = json.loads((self.output / snapshot['chunks'][0]['url']).read_text())
        self.assertEqual(cards[0]['image_url'], 'https://example.com/open.jpg')
        detail = next(iter(json.loads((self.output / snapshot['chunks'][0]['details_url']).read_text()).values()))
        self.assertEqual(len(detail['sources']), 2)
        restricted = next(source for source in detail['sources'] if source['source_id'] == 'moma')
        self.assertIsNone(restricted['image_url'])
        self.assertEqual(restricted['image_license'], 'restricted')
        self.assertIn("snapshotUrl: './snapshot.json'", (self.output / 'config.js').read_text())
        self.assertIn('href="./styles.css"', (self.output / 'index.html').read_text())
        self.assertEqual(json.loads((self.output / 'snapshot.json').read_text())['version'], 2)

    def test_export_excludes_metadata_only_and_chunks_entire_collection(self):
        for number in range(7):
            upsert(self.conn, {'source_id': 'nga', 'source_object_id': str(number),
                              'title': f'Image {number}', 'public_domain': 1,
                              'image_url': f'https://example.com/{number}.jpg'})
        upsert(self.conn, {'source_id': 'met', 'source_object_id': 'missing', 'title': 'No image'})
        upsert(self.conn, {'source_id': 'moma', 'source_object_id': 'restricted',
                          'public_domain': 0, 'image_url': 'https://example.com/restricted.jpg'})
        self.conn.commit()
        rebuild(self.conn)
        manifest = export_site(self.db_path, self.output, chunk_size=3)
        self.assertEqual(manifest['stats']['total'], 9)
        self.assertEqual(manifest['stats']['canonical'], 7)
        self.assertEqual([chunk['count'] for chunk in manifest['chunks']], [3, 3, 1])
        self.assertEqual([source['id'] for source in manifest['stats']['sources']], ['nga'])
        ids = set()
        for chunk in manifest['chunks']:
            cards = json.loads((self.output / chunk['url']).read_text())
            details = json.loads((self.output / chunk['details_url']).read_text())
            for card in cards:
                ids.add(card['id'])
                self.assertTrue(card['image_url'])
                self.assertEqual(details[str(card['id'])]['artwork']['id'], card['id'])
        self.assertEqual(len(ids), 7)
        with gzip.open(self.output / manifest['search_index_url'], 'rt', encoding='utf-8') as handle:
            index = json.load(handle)
        self.assertEqual(len(index), 7)
        self.assertEqual({row[0] for row in index}, {0, 1, 2})
        self.assertTrue(all('Image' in row[1] for row in index))

    def test_empty_database_is_not_published(self):
        with self.assertRaisesRegex(ValueError, 'No canonical artworks'):
            export_site(self.db_path, self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
