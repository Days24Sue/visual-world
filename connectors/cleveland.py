import json
from .common import http_json, stream_json_array, clean_int, joinish, upsert
BASE='https://openaccess-api.clevelandart.org/api/artworks/'
BULK_URL='https://media.githubusercontent.com/media/ClevelandMuseumArt/openaccess/master/data.json'

def _records(limit):
    if limit is None:
        yield from stream_json_array(BULK_URL)
        return
    skip=0; n=0; batch=1000
    while True:
        data=http_json(f'{BASE}?limit={batch}&skip={skip}')
        rows=data.get('data',[]) if isinstance(data,dict) else []
        if not rows: break
        for r in rows:
            yield r
            n+=1
            if limit and n>=limit: return
        skip += len(rows)
        total=(data.get('info') or {}).get('total')
        if total is not None and skip>=int(total): break

def sync(conn, limit=None):
    n=0
    for r in _records(limit):
        oid=str(r.get('id'))
        images=r.get('images') or {}
        web=images.get('web') or {}
        full=images.get('full') or {}
        printable=images.get('print') or {}
        thumb=web or printable
        # The full master is commonly TIFF, which browsers cannot display.
        full_url=full.get('url') or ''
        browser_full=full_url if full_url and not full_url.lower().split('?')[0].endswith(('.tif','.tiff')) else None
        image=printable.get('url') or web.get('url') or browser_full
        creators=r.get('creators') or []
        artist='; '.join(c.get('description','') for c in creators if isinstance(c,dict))
        open_image=str(r.get('share_license_status') or '').upper()=='CC0'
        row={
          'canonical_key':f'cleveland:{oid}','source_id':'cleveland','source_object_id':oid,'title':r.get('title'),'artist':artist,
          'artist_names':json.dumps([c.get('description','').split(' (')[0] for c in creators if isinstance(c,dict)],ensure_ascii=False),
          'date_display':r.get('creation_date'),'year_start':clean_int(r.get('creation_date_earliest')),'year_end':clean_int(r.get('creation_date_latest')),
          'culture':joinish(r.get('culture')),'department':r.get('department'),'classification':r.get('type'),'medium':r.get('technique'),'dimensions':joinish(r.get('measurements')),
          'description':r.get('description'),'image_url':image if open_image else None,'thumbnail_url':thumb.get('url') if open_image and isinstance(thumb,dict) else None,
          'object_url':r.get('url'),'accession_number':r.get('accession_number'),'wikidata_qid':r.get('wikidata_id'),'metadata_license':'CC0','image_license':'CC0' if open_image else 'Image use restricted or unverified',
          'public_domain':1 if open_image else 0,'rights_note':r.get('copyright')
        }
        upsert(conn,row); n+=1
        if n%1000==0:
            conn.commit()
            print(f'cleveland: {n:,} records imported', flush=True)
    if not n: raise ValueError('Cleveland collection download contained no artworks')
    conn.commit()
    return n
