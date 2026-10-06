import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from schema import init_db
from connectors.common import upsert
from canonicalize import rebuild as canonicalize
from exploration import rebuild, catalog, stable_id, painter_data
from server import search_artworks


class ExplorationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = init_db(Path(self.tmp.name) / 'test.db')
        self.cache = Path(self.tmp.name) / 'painters.csv'
        with self.cache.open('w') as handle:
            writer = csv.DictWriter(handle, fieldnames=['artist', 'birth_year', 'death_year', 'Nationality', 'movement'])
            writer.writeheader()
            writer.writerow({'artist': 'Claude Monet', 'birth_year': '1840.0', 'death_year': '1926.0',
                             'Nationality': 'French', 'movement': 'Incorrect external style'})
        for source, oid, artist, year, style, subject in [
                ('artic', '1', 'Claude Monet (French, 1840–1926)', 1888, 'Impressionism', 'landscape | landscapes'),
                ('nga', '2', 'Claude Monet', 1901, None, None),
                ('cleveland', '3', 'Claude Monet (French, 1840–1926)', None, None, None),
                ('nga', '4', 'Workshop of Claude Monet', 1890, None, None)]:
            upsert(self.conn, {'source_id': source, 'source_object_id': oid, 'title': f'Work {oid}',
                              'artist': artist, 'year_start': year, 'year_end': year, 'style': style,
                              'subjects': subject, 'classification': 'Painting', 'public_domain': 1,
                              'image_url': f'https://example.com/{oid}.jpg'})
        upsert(self.conn, {'source_id': 'artic', 'source_object_id': 'hidden', 'artist': 'Hidden Artist', 'title': 'No picture'})
        self.conn.commit()
        canonicalize(self.conn)
        rebuild(self.conn, cache_path=self.cache)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def search(self, **changes):
        options = dict(query='', source='', kind='', with_images=True, public_only=False,
                       year_from=-100000, year_to=100000, limit=60, offset=0, summary=True)
        options.update(changes)
        return search_artworks(self.conn, **options)

    def test_artist_identity_merges_display_variants_but_not_workshops(self):
        data = catalog(self.conn)
        self.assertEqual(len(data['artists']), 2)
        monet = next(artist for artist in data['artists'] if artist['name'] == 'Claude Monet')
        self.assertEqual(monet['count'], 3)
        self.assertEqual(monet['name_zh'], '克洛德·莫奈')
        self.assertEqual((monet['birth_year'], monet['death_year']), (1840, 1926))
        self.assertEqual(monet['movements'], ['印象派'])
        self.assertEqual(self.search(artist=monet['id'])['total'], 3)
        self.assertFalse(any(artist['name'] == 'Hidden Artist' for artist in data['artists']))

    def test_chinese_queries_and_combined_facets_use_full_index(self):
        self.assertEqual(self.search(query='莫奈')['total'], 3)
        result = self.search(query='莫奈 风景', style=stable_id('style', '印象派'),
                             subject=stable_id('subject', '风景'), year_from=1800, year_to=1899)
        self.assertEqual([item['title'] for item in result['items']], ['Work 1'])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['artist_counts'][0]['count'], 1)
        self.assertEqual(self.search(artist='artist-missing')['total'], 0)

    def test_periods_sorting_and_pagination_preserve_unknown_dates(self):
        key = stable_id('artist', 'Claude Monet')
        result = self.search(artist=key, sort='oldest', limit=1, offset=1)
        self.assertEqual(result['total'], 3)
        self.assertEqual(result['items'][0]['year_start'], 1901)
        self.assertEqual(self.search(artist=key, sort='newest')['items'][-1]['year_start'], None)
        self.assertEqual(self.search(artist=key, year_from=1800, year_to=1899)['total'], 1)
        self.assertEqual(self.search(year_from=1900, year_to=1800)['total'], 0)

    def test_rebuild_does_not_leave_stale_links_or_duplicate_synonyms(self):
        first = catalog(self.conn)
        self.assertEqual(first['subjects'][0]['count'], 1)
        self.assertEqual(rebuild(self.conn, cache_path=self.cache)['artists'], 2)
        self.assertEqual(catalog(self.conn)['artists'][0]['id'], first['artists'][0]['id'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM canonical_artists').fetchone()[0], 4)

    def test_bad_biography_download_preserves_existing_cache(self):
        previous = self.cache.read_bytes()
        with patch('exploration.http_bytes', return_value=b'<html>temporarily unavailable</html>'):
            with self.assertRaisesRegex(ValueError, 'artist name column'):
                painter_data(self.cache, download=True)
        self.assertEqual(self.cache.read_bytes(), previous)

    def test_ambiguous_biographies_are_not_selected(self):
        with self.cache.open('a') as handle:
            handle.write('Claude Monet,1900,1950,French,Other\n')
        self.assertNotIn('claude monet', painter_data(self.cache))


if __name__ == '__main__':
    unittest.main()
