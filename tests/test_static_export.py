import json
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
        self.assertEqual(snapshot['artworks'][0]['image_url'], 'https://example.com/open.jpg')
        detail = next(iter(snapshot['details'].values()))
        self.assertEqual(len(detail['sources']), 2)
        restricted = next(source for source in detail['sources'] if source['source_id'] == 'moma')
        self.assertIsNone(restricted['image_url'])
        self.assertEqual(restricted['image_license'], 'restricted')
        self.assertIn("snapshotUrl: './snapshot.json'", (self.output / 'config.js').read_text())
        self.assertIn('href="./styles.css"', (self.output / 'index.html').read_text())
        self.assertEqual(json.loads((self.output / 'snapshot.json').read_text())['version'], 1)

    def test_empty_database_is_not_published(self):
        with self.assertRaisesRegex(ValueError, 'No canonical artworks'):
            export_site(self.db_path, self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
