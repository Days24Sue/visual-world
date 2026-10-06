#!/usr/bin/env python3
import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from schema import DB_PATH


WEB = Path(__file__).parent / 'web'


def rows(conn, query):
    return [dict(row) for row in conn.execute(query).fetchall()]


def build_snapshot(conn):
    artworks = rows(conn, '''SELECT * FROM canonical_artworks
        ORDER BY CASE WHEN coalesce(thumbnail_url,image_url) IS NOT NULL THEN 0 ELSE 1 END,
        source_count DESC, id DESC''')
    if not artworks:
        raise ValueError('No canonical artworks to publish; run sync.py first')

    sources = rows(conn, '''SELECT s.*,
        (SELECT r.status FROM sync_runs r WHERE r.source_id=s.id ORDER BY r.id DESC LIMIT 1) last_status,
        (SELECT r.error FROM sync_runs r WHERE r.source_id=s.id ORDER BY r.id DESC LIMIT 1) last_error
        FROM sources s ORDER BY CASE WHEN s.kind='resource_index' THEN 1 ELSE 0 END,
        s.record_count DESC, s.resource_count DESC, s.name''')
    stats = {
        'total': conn.execute('SELECT count(*) FROM artworks').fetchone()[0],
        'canonical': len(artworks),
        'images': conn.execute('''SELECT count(*) FROM artworks WHERE public_domain=1
            AND coalesce(thumbnail_url,image_url) IS NOT NULL''').fetchone()[0],
        'artists': conn.execute("SELECT count(DISTINCT artist) FROM artworks WHERE artist IS NOT NULL AND artist<>''").fetchone()[0],
        'resources': conn.execute('SELECT count(*) FROM resources').fetchone()[0],
        'sources': sources,
    }
    stats['duplicates'] = max(0, stats['total'] - stats['canonical'])
    resources = rows(conn, '''SELECT id,source_id,source_resource_id,name,url,category,
        description,tags,license_note,source_updated_at,ingested_at
        FROM resources ORDER BY category,name''')
    details = {str(artwork['id']): {'artwork': artwork, 'sources': []} for artwork in artworks}
    members = rows(conn, '''SELECT m.canonical_id,a.*,s.name source_name,s.homepage source_homepage
        FROM canonical_members m JOIN artworks a ON a.id=m.artwork_id
        JOIN sources s ON s.id=a.source_id
        ORDER BY m.canonical_id,
        CASE WHEN coalesce(a.thumbnail_url,a.image_url) IS NOT NULL THEN 0 ELSE 1 END,
        a.source_id''')
    for member in members:
        detail = details[str(member.pop('canonical_id'))]
        if member['public_domain'] != 1:
            member['image_url'] = None
            member['thumbnail_url'] = None
        detail['sources'].append(member)

    for detail in details.values():
        artwork = detail['artwork']
        displayable = {url for member in detail['sources'] if member['public_domain'] == 1
                       for url in (member['image_url'], member['thumbnail_url']) if url}
        for field in ('image_url', 'thumbnail_url'):
            if artwork[field] and artwork[field] not in displayable:
                raise ValueError(f'Artwork {artwork["id"]} has an image without an open source')

    generated_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    stats['snapshot_at'] = generated_at
    return {'version': 1, 'generated_at': generated_at, 'stats': stats,
            'artworks': artworks, 'resources': resources, 'details': details}


def export_site(db_path, output):
    db_path = Path(db_path)
    output = Path(output)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    if output.resolve().is_relative_to(WEB.resolve()):
        raise ValueError('Output cannot be inside web/')

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        snapshot = build_snapshot(conn)
    finally:
        conn.close()

    config = (WEB / 'config.js').read_text()
    marker = "snapshotUrl: ''"
    if config.count(marker) != 1:
        raise ValueError('web/config.js must contain one empty snapshotUrl')
    shutil.copytree(WEB, output)
    (output / 'config.js').write_text(config.replace(marker, "snapshotUrl: './snapshot.json'"))
    (output / 'snapshot.json').write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')))
    (output / '.nojekyll').touch()
    return snapshot


def main():
    parser = argparse.ArgumentParser(description='Export a rights-aware GitHub Pages snapshot')
    parser.add_argument('--db', type=Path, default=DB_PATH)
    parser.add_argument('--output', type=Path, default=Path('dist'))
    args = parser.parse_args()
    snapshot = export_site(args.db, args.output)
    print(f'Exported {len(snapshot["artworks"])} canonical artworks and '
          f'{len(snapshot["resources"])} resources to {args.output}')


if __name__ == '__main__':
    main()
