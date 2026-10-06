import tempfile
import io
import json
import tarfile
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
        self.assertEqual(rows[1]['image_url'], 'https://example.com/iiif/two/full/843,/0/default.jpg')

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

    def test_cleveland_continues_when_server_caps_page_size(self):
        from connectors import cleveland
        responses = [
            {'info': {'total': 3}, 'data': [{'id': 1}, {'id': 2}]},
            {'info': {'total': 3}, 'data': [{'id': 3}]},
        ]
        with patch.object(cleveland, 'http_json', side_effect=responses) as fetch:
            self.assertEqual(cleveland.sync(self.conn, limit=3), 3)
        self.assertIn('skip=2', fetch.call_args_list[1].args[0])

    def test_cleveland_full_sync_uses_bulk_jpeg_instead_of_tiff(self):
        from connectors import cleveland
        record = {'id': 1, 'share_license_status': 'CC0', 'images': {
            'full': {'url': 'https://example.com/master.tif'},
            'print': {'url': 'https://example.com/large.jpg'},
            'web': {'url': 'https://example.com/small.jpg'},
        }}
        with patch.object(cleveland, 'stream_json_array', return_value=iter([record])), patch.object(cleveland, 'http_json') as api:
            self.assertEqual(cleveland.sync(self.conn), 1)
            api.assert_not_called()
        row = self.conn.execute('SELECT image_url,thumbnail_url FROM artworks').fetchone()
        self.assertEqual(tuple(row), ('https://example.com/large.jpg', 'https://example.com/small.jpg'))

    def test_bulk_json_stream_handles_split_unicode_and_rejects_truncation(self):
        from connectors import common
        data = json.dumps([{'title': '名画'}, {'id': 2}], ensure_ascii=False).encode()
        with patch.object(common, 'http_response', return_value=io.BytesIO(data)):
            self.assertEqual(list(common.stream_json_array('https://example.com/data', chunk_size=3)), [{'title': '名画'}, {'id': 2}])
        with patch.object(common, 'http_response', return_value=io.BytesIO(b'[{"id":1}')):
            with self.assertRaisesRegex(ValueError, 'Truncated'):
                list(common.stream_json_array('https://example.com/data', chunk_size=3))

    def test_artic_full_sync_streams_official_dump_and_skips_other_entities(self):
        from connectors import artic
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:bz2') as archive:
            for name, record in [('json/agents/1.json', {'id': 1}),
                                 ('json/artworks/9.json', {'id': 9, 'title': 'Open work', 'is_public_domain': True, 'image_id': 'image'}),
                                 ('json/artworks/10.json', {'id': 10, 'title': 'Restricted work', 'is_public_domain': False, 'image_id': 'restricted'})]:
                data = json.dumps(record).encode()
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        buffer.seek(0)
        with patch.object(artic, 'http_response', return_value=buffer), patch.object(artic, 'http_json') as api:
            self.assertEqual(artic.sync(self.conn), 2)
            api.assert_not_called()
        rows = self.conn.execute("SELECT source_object_id,image_url FROM artworks ORDER BY id").fetchall()
        self.assertEqual(rows[0]['source_object_id'], '9')
        self.assertIn('/full/843,/', rows[0]['image_url'])
        self.assertIsNone(rows[1]['image_url'])

    def test_walters_media_failure_is_reported(self):
        from connectors import walters
        with patch.object(walters, '_media_index', side_effect=RuntimeError('media unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'media unavailable'):
                walters.sync(self.conn, limit=1)

    def test_artic_keeps_structured_creator_and_source_taxonomy(self):
        from connectors import artic
        record = {'id': 1, 'artist_id': 7, 'artist_titles': ['Claude Monet'],
                  'style_titles': ['Impressionism'], 'subject_titles': ['landscape'],
                  'term_titles': ['oil painting'], 'description': '<p>A <em>landscape</em>.</p>'}
        with patch.object(artic, '_records', return_value=iter([(record, 'https://example.com/iiif')])):
            artic.sync(self.conn)
        row = self.conn.execute('SELECT * FROM artworks').fetchone()
        self.assertEqual(json.loads(row['artist_names']), ['Claude Monet'])
        self.assertEqual(row['artist_id'], '7')
        self.assertEqual((row['style'], row['subjects'], row['tags']), ('Impressionism', 'landscape', 'oil painting'))
        self.assertNotIn('<', row['description'])


if __name__ == '__main__':
    unittest.main()
