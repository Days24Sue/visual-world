"""Artist identities and source-labelled facets for the complete public collection."""
import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from connectors.common import http_bytes, plain_text

ROOT = Path(__file__).parent
CURATION = json.loads((ROOT / 'curation.json').read_text())
PAINTER_URL = 'https://raw.githubusercontent.com/me9hanics/PainterPalette/main/PainterPalette.csv'
PAINTER_SOURCE = 'https://github.com/me9hanics/PainterPalette'
VISIBLE = "coalesce(nullif(c.thumbnail_url,''),nullif(c.image_url,'')) IS NOT NULL"
PERIODS = [
    ('before-1400', '1400 年以前', -100000, 1399),
    ('1400', '15 世纪', 1400, 1499), ('1500', '16 世纪', 1500, 1599),
    ('1600', '17 世纪', 1600, 1699), ('1700', '18 世纪', 1700, 1799),
    ('1800', '19 世纪', 1800, 1899), ('1900', '20 世纪', 1900, 1999),
    ('2000', '21 世纪', 2000, 2099),
]


def fold(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(value or ''))
                           if not unicodedata.combining(c)).casefold().split())


def stable_id(dimension, value):
    return dimension + '-' + hashlib.sha1(fold(value).encode()).hexdigest()[:16]


def terms(value):
    return list(dict.fromkeys(v.strip() for v in str(value or '').split('|') if v.strip()))


def integer_year(value):
    try:
        number = float(value)
        return int(number) if number.is_integer() and -10000 <= number <= 2100 else None
    except (TypeError, ValueError):
        return None


def creator_name(value):
    name = plain_text(value).split('\n')[0].strip()
    # Museum display strings append nationality and dates after the name.
    # Attribution qualifiers stay intact: a workshop is not the named artist.
    name = re.sub(r'\s*\([^)]*(?:\d{3,4}|American|French|Dutch|British|German|Italian|Spanish|Japanese|Swiss|Norwegian|Austrian|Belgian)[^)]*\)\s*$', '', name)
    return name.strip(' ;')


def painter_data(cache_path, download=False):
    payload = None
    if download:
        payload = http_bytes(PAINTER_URL, timeout=240)
    if payload is None and not cache_path.exists():
        return {}
    text = payload.decode('utf-8-sig') if payload is not None else cache_path.read_text(encoding='utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    if not {'artist', 'artist name'}.intersection(reader.fieldnames or []):
        raise ValueError('PainterPalette download has no artist name column')
    result = {}
    for row in reader:
        name = row.get('artist') or row.get('artist name')
        if name:
            result.setdefault(fold(name), []).append(row)
    if not result:
        raise ValueError('PainterPalette download contains no artists')
    if payload is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix('.tmp')
        temporary.write_bytes(payload)
        temporary.replace(cache_path)
    # Ambiguous names must not silently select one biography.
    return {name: rows[0] for name, rows in result.items() if len(rows) == 1}


def rebuild(conn, download=False, cache_path=None):
    cache_path = Path(cache_path or ROOT / 'data/cache/painterpalette.csv')
    painters = painter_data(cache_path, download)
    curated = {fold(name): name for name in CURATION['artists']}
    for name, aliases in CURATION['artist_aliases'].items():
        for alias in aliases:
            curated[fold(alias)] = name
    translations = {fold(label): zh for label, zh in CURATION['terms'].items()}
    members = defaultdict(list)
    for row in conn.execute(f'''SELECT m.canonical_id,a.artist,a.artist_names
        FROM canonical_members m JOIN artworks a ON a.id=m.artwork_id
        JOIN canonical_artworks c ON c.id=m.canonical_id WHERE {VISIBLE}'''):
        members[row['canonical_id']].append(row)
    profiles, taxonomy, links, term_links = {}, {}, [], []
    for artwork in conn.execute(f'SELECT c.* FROM canonical_artworks c WHERE {VISIBLE}'):
        ids = set()
        for member in members[artwork['id']]:
            try:
                names = json.loads(member['artist_names'] or '[]')
            except (TypeError, json.JSONDecodeError):
                names = []
            if not isinstance(names, list):
                names = []
            if not names:
                names = str(member['artist'] or '').split(';')
            for raw in names:
                if not isinstance(raw, str):
                    continue
                name = creator_name(raw)
                if not name or fold(name) in {'unknown', 'unknown artist', 'anonymous', 'unidentified artist', 'unidentified'}:
                    continue
                name = curated.get(fold(name), name)
                key = stable_id('artist', name)
                ids.add(key)
                if key not in profiles:
                    supplement = painters.get(fold(name), {})
                    date_match = re.search(r'(\d{3,4})\s*[–—-]\s*(\d{3,4})', member['artist'] or '')
                    birth = integer_year(supplement.get('birth_year'))
                    death = integer_year(supplement.get('death_year'))
                    if not supplement and date_match and len(names) == 1:
                        birth, death = map(int, date_match.groups())
                    zh = CURATION['artists'].get(name)
                    aliases = [name] + ([zh] if zh else []) + CURATION['artist_aliases'].get(name, [])
                    profiles[key] = {
                        'id': key, 'name': name, 'name_zh': zh,
                        'aliases': json.dumps(list(dict.fromkeys(aliases)), ensure_ascii=False),
                        'birth_year': birth, 'death_year': death,
                        'nationality': supplement.get('Nationality') or supplement.get('citizenship') or None,
                        # Supplement movement labels can be inconsistent. Use museum
                        # work styles for navigation, never assign every work an artist's style.
                        'movements': '[]', 'info_source': PAINTER_SOURCE if supplement else '馆藏作者信息',
                    }
        links.extend((artwork['id'], key) for key in sorted(ids))
        for dimension, field in [('style', 'style'), ('subject', 'subjects'), ('kind', 'classification')]:
            for label in terms(artwork[field]):
                if dimension == 'style' and re.search(r'\bcentur(?:y|ies)\b', label, re.I):
                    continue
                zh = translations.get(fold(label))
                key = stable_id(dimension, zh or label)
                taxonomy.setdefault(key, {'id': key, 'dimension': dimension, 'label': label, 'label_zh': zh})
                term_links.append((artwork['id'], key))
    conn.execute('SAVEPOINT exploration_rebuild')
    try:
        conn.execute('DELETE FROM canonical_artists')
        conn.execute('DELETE FROM canonical_terms')
        conn.execute('DELETE FROM artist_profiles')
        conn.execute('DELETE FROM taxonomy_terms')
        columns = ('id', 'name', 'name_zh', 'aliases', 'birth_year', 'death_year', 'nationality', 'movements', 'info_source')
        conn.executemany(f"INSERT INTO artist_profiles({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
                         [tuple(profile[col] for col in columns) for profile in profiles.values()])
        conn.executemany('INSERT INTO canonical_artists VALUES(?,?)', links)
        conn.executemany('INSERT INTO taxonomy_terms VALUES(:id,:dimension,:label,:label_zh)', taxonomy.values())
        conn.executemany('INSERT OR IGNORE INTO canonical_terms VALUES(?,?)', term_links)
        conn.execute('DELETE FROM exploration_fts')
        dimensions = artwork_dimensions(conn)
        for artwork in conn.execute(f'SELECT c.* FROM canonical_artworks c WHERE {VISIBLE}'):
            text = search_text(artwork, dimensions[artwork['id']], profiles, taxonomy)
            conn.execute('INSERT INTO exploration_fts(rowid,search_text) VALUES(?,?)', (artwork['id'], text))
        conn.execute('RELEASE exploration_rebuild')
        conn.commit()
    except Exception:
        conn.execute('ROLLBACK TO exploration_rebuild')
        conn.execute('RELEASE exploration_rebuild')
        raise
    return {'artists': len(profiles), 'matched_profiles': sum(p['info_source'] == PAINTER_SOURCE for p in profiles.values()),
            'styles': sum(t['dimension'] == 'style' for t in taxonomy.values()),
            'subjects': sum(t['dimension'] == 'subject' for t in taxonomy.values())}


def search_text(artwork, dimensions, artists, taxonomy):
    fields = ('title', 'artist', 'date_display', 'country', 'culture', 'classification',
              'medium', 'style', 'subjects', 'tags', 'description')
    parts = [str(artwork[field] or '') for field in fields]
    for key in dimensions['artist_ids']:
        aliases = artists[key]['aliases']
        parts.extend(json.loads(aliases) if isinstance(aliases, str) else aliases)
    for dimension in ('style', 'subject', 'kind'):
        for key in dimensions[dimension + '_ids']:
            term = taxonomy[key]
            parts.extend([term['label'], term['label_zh'] or ''])
    return ' '.join(parts)


def artwork_dimensions(conn):
    result = defaultdict(lambda: {'artist_ids': [], 'style_ids': [], 'subject_ids': [], 'kind_ids': []})
    for row in conn.execute('SELECT canonical_id,artist_id FROM canonical_artists'):
        result[row[0]]['artist_ids'].append(row[1])
    for row in conn.execute('''SELECT l.canonical_id,t.id,t.dimension FROM canonical_terms l
        JOIN taxonomy_terms t ON t.id=l.term_id'''):
        result[row[0]][row[2] + '_ids'].append(row[1])
    return result


def catalog(conn):
    artists = []
    for row in conn.execute(f'''SELECT p.*,count(*) count,min(c.year_start) first_work_year,
        max(c.year_end) last_work_year,
        coalesce(min(CASE WHEN lower(c.classification) LIKE '%painting%' THEN c.id END),min(c.id)) sample_id FROM artist_profiles p
        JOIN canonical_artists l ON l.artist_id=p.id JOIN canonical_artworks c ON c.id=l.canonical_id
        WHERE {VISIBLE} GROUP BY p.id ORDER BY count DESC,p.name'''):
        profile = dict(row)
        profile['aliases'] = json.loads(profile['aliases'])
        profile['movements'] = []
        artists.append(profile)
    artist_map = {artist['id']: artist for artist in artists}
    for row in conn.execute('''SELECT DISTINCT a.artist_id,t.label_zh,t.label FROM canonical_artists a
        JOIN canonical_terms l ON l.canonical_id=a.canonical_id
        JOIN taxonomy_terms t ON t.id=l.term_id WHERE t.dimension='style' AND t.label_zh IS NOT NULL'''):
        if row['artist_id'] in artist_map:
            artist_map[row['artist_id']]['movements'].append(row['label_zh'] or row['label'])
    facets = {'styles': [], 'subjects': [], 'kinds': []}
    for row in conn.execute(f'''SELECT t.*,count(*) count FROM taxonomy_terms t
        JOIN canonical_terms l ON l.term_id=t.id JOIN canonical_artworks c ON c.id=l.canonical_id
        WHERE {VISIBLE} GROUP BY t.id ORDER BY count DESC,t.label'''):
        facets[{'style': 'styles', 'subject': 'subjects', 'kind': 'kinds'}[row['dimension']]].append(dict(row))
    periods = []
    for key, label, start, end in PERIODS:
        count = conn.execute(f'''SELECT count(*) FROM canonical_artworks c WHERE {VISIBLE}
            AND coalesce(c.year_end,c.year_start)>=? AND coalesce(c.year_start,c.year_end)<=?''', (start, end)).fetchone()[0]
        if count:
            periods.append({'id': key, 'label': label, 'year_from': start, 'year_to': end, 'count': count})
    featured = [a['id'] for a in artists if a['name_zh']]
    priority = ['Claude Monet', 'Vincent van Gogh', 'Pablo Picasso', 'Georges Seurat', 'Rembrandt van Rijn',
                'Katsushika Hokusai', 'Henri Matisse', 'Mary Cassatt']
    featured.sort(key=lambda key: priority.index(artist_map[key]['name']) if artist_map[key]['name'] in priority else len(priority))
    for key in featured[:12]:
        row = conn.execute('SELECT thumbnail_url,image_url,title FROM canonical_artworks WHERE id=?', (artist_map[key]['sample_id'],)).fetchone()
        artist_map[key]['image_url'] = row['thumbnail_url'] or row['image_url']
        artist_map[key]['hero_image_url'] = row['image_url'] or row['thumbnail_url']
        artist_map[key]['sample_title'] = row['title']
    return {'artists': artists, **facets, 'periods': periods, 'featured_artists': featured[:12],
            'translations': CURATION['terms']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Rebuild artists and browsing facets without limiting the collection')
    parser.add_argument('--sync-painters', action='store_true', help='Refresh the PainterPalette biography supplement')
    args = parser.parse_args()
    from schema import init_db
    conn = init_db()
    try:
        print(json.dumps(rebuild(conn, download=args.sync_painters), ensure_ascii=False))
    finally:
        conn.close()
