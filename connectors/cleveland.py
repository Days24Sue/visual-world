from .common import http_json, clean_int, joinish, upsert
BASE='https://openaccess-api.clevelandart.org/api/artworks/'

def sync(conn, limit=None):
    skip=0; n=0; batch=1000
    while True:
        data=http_json(f'{BASE}?limit={batch}&skip={skip}')
        rows=data.get('data',[]) if isinstance(data,dict) else []
        if not rows: break
        for r in rows:
            oid=str(r.get('id'))
            images=r.get('images') or {}
            web=images.get('web') or {}
            full=images.get('full') or {}
            thumb=images.get('print') or web
            creators=r.get('creators') or []
            artist='; '.join(c.get('description','') for c in creators if isinstance(c,dict))
            open_image=str(r.get('share_license_status') or '').upper()=='CC0'
            row={
              'canonical_key':f'cleveland:{oid}','source_id':'cleveland','source_object_id':oid,'title':r.get('title'),'artist':artist,
              'date_display':r.get('creation_date'),'year_start':clean_int(r.get('creation_date_earliest')),'year_end':clean_int(r.get('creation_date_latest')),
              'culture':joinish(r.get('culture')),'department':r.get('department'),'classification':r.get('type'),'medium':r.get('technique'),'dimensions':joinish(r.get('measurements')),
              'subjects':joinish(r.get('fun_fact')),'description':r.get('description'),'image_url':(full.get('url') or web.get('url')) if open_image else None,'thumbnail_url':thumb.get('url') if open_image and isinstance(thumb,dict) else None,
              'object_url':r.get('url'),'accession_number':r.get('accession_number'),'wikidata_qid':r.get('wikidata_id'),'metadata_license':'CC0','image_license':'CC0' if open_image else 'Image use restricted or unverified',
              'public_domain':1 if open_image else 0,'rights_note':r.get('copyright')
            }
            upsert(conn,row); n+=1
            if limit and n>=limit: conn.commit(); return n
        conn.commit(); skip += len(rows)
        if len(rows)<batch: break
    return n
