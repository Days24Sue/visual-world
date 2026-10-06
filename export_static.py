#!/usr/bin/env python3
"""Export the complete image-bearing collection in bounded, lazy-loaded shards."""
import argparse
import gzip
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from schema import DB_PATH
from exploration import artwork_dimensions, catalog, rebuild as rebuild_exploration, search_text

WEB = Path(__file__).parent / 'web'
DISPLAYABLE = "coalesce(nullif(c.thumbnail_url,''),nullif(c.image_url,'')) IS NOT NULL"
SEARCH_FIELDS = ('title', 'artist', 'date_display', 'country', 'culture',
                 'classification', 'medium', 'style', 'subjects', 'tags', 'description')
CARD_FIELDS = ('id', 'title', 'artist', 'date_display', 'medium', 'classification',
               'year_start', 'year_end', 'public_domain', 'source_ids', 'source_count',
               'image_url', 'thumbnail_url', 'style', 'subjects')


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def public_stats(conn):
    sources = [dict(row) for row in conn.execute(f'''SELECT s.*,
        (SELECT count(DISTINCT c.id) FROM canonical_artworks c
         JOIN canonical_members m ON m.canonical_id=c.id
         WHERE m.source_id=s.id AND {DISPLAYABLE}) visible_count,
        (SELECT r.status FROM sync_runs r WHERE r.source_id=s.id ORDER BY r.id DESC LIMIT 1) last_status,
        (SELECT r.error FROM sync_runs r WHERE r.source_id=s.id ORDER BY r.id DESC LIMIT 1) last_error
        FROM sources s ORDER BY s.kind,s.name''')]
    raw = conn.execute('SELECT count(*) FROM artworks').fetchone()[0]
    canonical_total = conn.execute('SELECT count(*) FROM canonical_artworks').fetchone()[0]
    visible = conn.execute(f'SELECT count(*) FROM canonical_artworks c WHERE {DISPLAYABLE}').fetchone()[0]
    profile_count = conn.execute('SELECT count(*) FROM artist_profiles').fetchone()[0]
    return {
        'total': raw, 'canonical': visible, 'images': visible,
        'duplicates': max(0, raw - canonical_total),
        'artists': profile_count or conn.execute(f"SELECT count(DISTINCT artist) FROM canonical_artworks c WHERE {DISPLAYABLE} AND coalesce(artist,'')<>''").fetchone()[0],
        'resources': conn.execute('SELECT count(*) FROM resources').fetchone()[0],
        'sources': [source for source in sources if source['visible_count'] or source['resource_count']],
        'snapshot_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }


def detail_for(conn, artwork):
    members = [dict(row) for row in conn.execute('''SELECT a.*,s.name source_name,
        s.homepage source_homepage FROM canonical_members m
        JOIN artworks a ON a.id=m.artwork_id JOIN sources s ON s.id=a.source_id
        WHERE m.canonical_id=? ORDER BY a.source_id''', (artwork['id'],))]
    for member in members:
        if member['public_domain'] != 1:
            member['image_url'] = member['thumbnail_url'] = None
    displayable = {url for member in members if member['public_domain'] == 1
                   for url in (member['image_url'], member['thumbnail_url']) if url}
    for field in ('image_url', 'thumbnail_url'):
        if artwork[field] and artwork[field] not in displayable:
            raise ValueError(f'Artwork {artwork["id"]} has an image without an open source')
    return {'artwork': artwork, 'sources': members}


def export_site(db_path, output, chunk_size=500):
    db_path, output = Path(db_path), Path(output)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    if output.resolve().is_relative_to(WEB.resolve()):
        raise ValueError('Output cannot be inside web/')
    if chunk_size < 1:
        raise ValueError('Chunk size must be positive')
    config = (WEB / 'config.js').read_text()
    marker = "snapshotUrl: ''"
    if config.count(marker) != 1:
        raise ValueError('web/config.js must contain one empty snapshotUrl')
    from schema import init_db
    conn = init_db(db_path)
    try:
        if not conn.execute('SELECT 1 FROM artist_profiles LIMIT 1').fetchone():
            rebuild_exploration(conn)
        stats = public_stats(conn)
        exploration = catalog(conn)
        dimensions = artwork_dimensions(conn)
        artists = {artist['id']: artist for artist in exploration['artists']}
        taxonomy = {term['id']: term for dimension in ('styles', 'subjects', 'kinds') for term in exploration[dimension]}
        if not stats['canonical']:
            raise ValueError('No canonical artworks with displayable images to publish; run sync.py first')
        shutil.copytree(WEB, output)
        (output / 'data').mkdir()
        (output / 'config.js').write_text(config.replace(marker, "snapshotUrl: './snapshot.json'"))
        resources = [dict(row) for row in conn.execute('SELECT * FROM resources ORDER BY category,name')]
        manifest = {'version': 2, 'generated_at': stats['snapshot_at'], 'stats': stats,
                    'resources': resources, 'chunks': [], 'search_index_url': 'data/search.json.gz',
                    'search_index_version': 2, 'explore_url': 'data/explore.json'}
        write_json(output / manifest['explore_url'], exploration)
        cursor = conn.execute(f'''SELECT c.* FROM canonical_artworks c WHERE {DISPLAYABLE}
            ORDER BY c.source_count DESC,c.id DESC''')
        search_index = gzip.open(output / manifest['search_index_url'], 'wt', encoding='utf-8')
        search_index.write('[')
        first_search_row = True
        while batch := cursor.fetchmany(chunk_size):
            number = len(manifest['chunks'])
            index_path, detail_path = f'data/index-{number}.json', f'data/details-{number}.json'
            cards, details, source_ids = [], {}, set()
            for row in batch:
                artwork = dict(row)
                card = {field: artwork[field] for field in CARD_FIELDS}
                card.update(dimensions[artwork['id']])
                card['search_text'] = search_text(artwork, dimensions[artwork['id']], artists, taxonomy)
                if not first_search_row:
                    search_index.write(',')
                json.dump([number, card['search_text'], card['id'], card['artist_ids'],
                           artwork['year_start'], artwork['year_end'], card['style_ids'],
                           card['subject_ids'], card['kind_ids'], artwork['source_ids'], artwork['title']],
                          search_index, ensure_ascii=False, separators=(',', ':'))
                first_search_row = False
                card['detail_path'] = detail_path
                cards.append(card)
                source_ids.update((artwork['source_ids'] or '').split('|'))
                detail = detail_for(conn, artwork)
                detail['artwork'].update(dimensions[artwork['id']])
                card['image_alternatives'] = list(dict.fromkeys(
                    url for member in detail['sources'] if member['public_domain'] == 1
                    for url in (member['thumbnail_url'], member['image_url']) if url))
                details[str(artwork['id'])] = detail
            write_json(output / index_path, cards)
            write_json(output / detail_path, details)
            manifest['chunks'].append({'url': index_path, 'details_url': detail_path,
                                       'count': len(cards), 'sources': sorted(source_ids),
                                       'min_id': min(card['id'] for card in cards),
                                       'max_id': max(card['id'] for card in cards)})
        search_index.write(']')
        search_index.close()
        write_json(output / 'snapshot.json', manifest)
        (output / '.nojekyll').touch()
        return manifest
    except Exception:
        if 'search_index' in locals():
            search_index.close()
        if output.exists():
            shutil.rmtree(output)
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Export the full image collection as a sharded Pages site')
    parser.add_argument('--db', type=Path, default=DB_PATH)
    parser.add_argument('--output', type=Path, default=Path('dist'))
    args = parser.parse_args()
    snapshot = export_site(args.db, args.output)
    print(f'Exported {snapshot["stats"]["canonical"]:,} displayable artworks in '
          f'{len(snapshot["chunks"])} chunks to {args.output}')


if __name__ == '__main__':
    main()
