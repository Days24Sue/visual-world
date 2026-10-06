import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from schema import init_db


class ConnectorRightsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = init_db(Path(self.tmp.name) / 'connectors.db')

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_artic_excludes_restricted_image(self):
        from connectors import artic
        response = {
            'config': {'iiif_url': 'https://example.com/iiif'},
            'data': [
                {'id': 1, 'title': 'Restricted', 'image_id': 'one', 'is_public_domain': False},
                {'id': 2, 'title': 'Open', 'image_id': 'two', 'is_public_domain': True},
            ],
        }
        with patch.object(artic, 'http_json', return_value=response):
            self.assertEqual(artic.sync(self.conn, limit=2), 2)
        rows = self.conn.execute('SELECT image_url,public_domain FROM artworks ORDER BY source_object_id').fetchall()
        self.assertIsNone(rows[0]['image_url'])
        self.assertEqual(rows[1]['image_url'], 'https://example.com/iiif/two/full/1200,/0/default.jpg')

    def test_cleveland_excludes_restricted_image(self):
        from connectors import cleveland
        response = {'data': [
            {'id': 1, 'images': {'full': {'url': 'https://example.com/restricted.jpg'}}, 'share_license_status': 'Copyright'},
            {'id': 2, 'images': {'full': {'url': 'https://example.com/open.jpg'}}, 'share_license_status': 'CC0'},
        ]}
        with patch.object(cleveland, 'http_json', return_value=response):
            self.assertEqual(cleveland.sync(self.conn, limit=2), 2)
        rows = self.conn.execute('SELECT image_url,public_domain FROM artworks ORDER BY source_object_id').fetchall()
        self.assertIsNone(rows[0]['image_url'])
        self.assertEqual(rows[1]['image_url'], 'https://example.com/open.jpg')

    def test_tate_metadata_does_not_expose_thumbnail(self):
        from connectors import tate
        with patch.object(tate, 'stream_csv', return_value=iter([{'id': '1', 'title': 'Work', 'thumbnailUrl': 'https://example.com/image.jpg'}])):
            self.assertEqual(tate.sync(self.conn, limit=1), 1)
        self.assertIsNone(self.conn.execute("SELECT thumbnail_url FROM artworks WHERE source_id='tate'").fetchone()[0])

    def test_walters_media_failure_is_reported(self):
        from connectors import walters
        with patch.object(walters, '_media_index', side_effect=RuntimeError('media unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'media unavailable'):
                walters.sync(self.conn, limit=1)


if __name__ == '__main__':
    unittest.main()
