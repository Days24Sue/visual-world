#!/usr/bin/env python3
import argparse
import hashlib
import re
import unicodedata
from collections import defaultdict

from schema import init_db


GENERIC_TITLES = {'untitled', 'no title', 'sans titre', 'ohne titel', 'portrait', 'self portrait', 'landscape', 'still life', 'study'}
QID_PATTERN = re.compile(r'(?:https?://(?:www\.)?wikidata\.org/(?:entity|wiki)/)?(Q[1-9]\d*)/?', re.IGNORECASE)


def norm(value):
    if value is None:
        return ''
    normalized = unicodedata.normalize('NFKC', str(value)).lower().strip()
    normalized = re.sub(r'[^\w\u4e00-\u9fff]+', ' ', normalized, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', normalized).strip()


def wikidata_qid(value):
    match = QID_PATTERN.fullmatch(str(value or '').strip())
    return match.group(1).upper() if match else None


def title_artist_year_key(row):
    title = norm(row['title'] or row['title_original'])
    artist = norm(row['artist'])
    start, end = row['year_start'], row['year_end']
    if not title or title in GENERIC_TITLES or not artist or (start is not None and end is not None and start != end):
        return None
    year = start if start is not None else end
    if year is None:
        return None
    raw = f'{title}|{artist}|{year}'.encode('utf-8')
    return 'tay:' + hashlib.sha1(raw).hexdigest()[:24]


def canonical_key(row):
    qid = wikidata_qid(row['wikidata_qid'])
    return ('wikidata:' + qid if qid else title_artist_year_key(row)) or f"source:{row['source_id']}:{row['source_object_id']}"


def score(row):
    fields = ['title', 'artist', 'date_display', 'country', 'culture', 'department', 'classification', 'medium', 'dimensions', 'style', 'subjects', 'description', 'image_url', 'thumbnail_url', 'object_url', 'wikidata_qid']
    return sum(1 for field in fields if row[field] not in (None, ''))


def rebuild(conn):
    rows = conn.execute('SELECT * FROM artworks ORDER BY id').fetchall()
    candidates = defaultdict(list)
    for row in rows:
        key = title_artist_year_key(row)
        if key:
            candidates[key].append(row)

    safe_candidates = {}
    for key, members in candidates.items():
        qids = {qid for member in members if (qid := wikidata_qid(member['wikidata_qid']))}
        if len({member['source_id'] for member in members}) == len(members) and len(qids) <= 1:
            safe_candidates[key] = next(iter(qids), None)

    groups = defaultdict(list)
    for row in rows:
        qid = wikidata_qid(row['wikidata_qid'])
        candidate = title_artist_year_key(row)
        if candidate in safe_candidates:
            qid = safe_candidates[candidate] or qid
            key = 'wikidata:' + qid if qid else candidate
        else:
            key = 'wikidata:' + qid if qid else f"source:{row['source_id']}:{row['source_object_id']}"
        groups[key].append(row)

    conn.execute('SAVEPOINT canonical_rebuild')
    try:
        conn.execute('DELETE FROM canonical_members')
        for key, members in groups.items():
            representative = max(members, key=score)
            displayable = [member for member in members if member['public_domain'] == 1 and (member['thumbnail_url'] or member['image_url'])]
            image = max(displayable, key=score) if displayable else None
            sources = sorted({member['source_id'] for member in members})
            public_domain = 1 if any(member['public_domain'] == 1 for member in members) else (0 if any(member['public_domain'] == 0 for member in members) else None)
            values = {
                'canonical_key': key, 'title': representative['title'], 'title_original': representative['title_original'],
                'artist': representative['artist'], 'date_display': representative['date_display'],
                'year_start': representative['year_start'], 'year_end': representative['year_end'],
                'country': representative['country'], 'culture': representative['culture'],
                'classification': representative['classification'], 'medium': representative['medium'],
                'style': ' | '.join(dict.fromkeys(term.strip() for member in members for term in (member['style'] or '').split('|') if term.strip())) or None,
                'subjects': ' | '.join(dict.fromkeys(term.strip() for member in members for term in (member['subjects'] or '').split('|') if term.strip())) or None,
                'tags': ' | '.join(dict.fromkeys(term.strip() for member in members for term in (member['tags'] or '').split('|') if term.strip())) or None,
                'description': representative['description'], 'image_url': image['image_url'] if image else None,
                'thumbnail_url': image['thumbnail_url'] if image else None, 'public_domain': public_domain,
                'wikidata_qid': key.split(':', 1)[1] if key.startswith('wikidata:') else wikidata_qid(representative['wikidata_qid']),
                'source_count': len(sources),
                'image_count': len(displayable), 'source_ids': '|'.join(sources),
                'representative_artwork_id': representative['id'],
            }
            columns = list(values)
            assignments = ','.join(f'{column}=excluded.{column}' for column in columns if column != 'canonical_key')
            conn.execute(
                f"INSERT INTO canonical_artworks({','.join(columns)}) VALUES({','.join('?' for _ in columns)}) "
                f'ON CONFLICT(canonical_key) DO UPDATE SET {assignments}',
                [values[column] for column in columns],
            )
            canonical_id = conn.execute('SELECT id FROM canonical_artworks WHERE canonical_key=?', (key,)).fetchone()[0]
            conn.executemany(
                'INSERT INTO canonical_members(canonical_id,artwork_id,source_id) VALUES(?,?,?)',
                [(canonical_id, member['id'], member['source_id']) for member in members],
            )
        conn.execute('DELETE FROM canonical_artworks WHERE NOT EXISTS (SELECT 1 FROM canonical_members WHERE canonical_id=canonical_artworks.id)')
    except Exception:
        conn.execute('ROLLBACK TO canonical_rebuild')
        conn.execute('RELEASE canonical_rebuild')
        raise
    conn.execute('RELEASE canonical_rebuild')
    conn.commit()
    return len(groups), len(rows)


def main():
    parser = argparse.ArgumentParser(description='Rebuild conservative cross-source canonical artwork groups')
    parser.parse_args()
    conn = init_db()
    groups, raw = rebuild(conn)
    print(f'Canonical index rebuilt: {groups:,} canonical works from {raw:,} source records; merged {raw-groups:,} duplicate records.')


if __name__ == '__main__':
    main()
