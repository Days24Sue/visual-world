import json
import tarfile
from pathlib import PurePosixPath
from .common import http_json, http_response, clean_int, upsert
BASE='https://api.artic.edu/api/v1/artworks'
BULK_URL='https://artic-api-data.s3.amazonaws.com/artic-api-data.tar.bz2'
FIELDS='id,title,artist_display,date_display,date_start,date_end,place_of_origin,department_title,artwork_type_title,medium_display,dimensions,image_id,is_public_domain,copyright_notice,main_reference_number,api_link'

def _records(limit):
    if limit is None:
        with http_response(BULK_URL, timeout=240) as response:
            with tarfile.open(fileobj=response, mode='r|bz2') as archive:
                for member in archive:
                    path=PurePosixPath(member.name)
                    if not member.isfile() or path.parent.name!='artworks' or path.suffix!='.json': continue
                    with archive.extractfile(member) as handle:
                        payload=json.load(handle)
                    yield payload.get('data',payload), 'https://www.artic.edu/iiif/2'
        return
    page=1; n=0
    while True:
        per=100
        data=http_json(f'{BASE}?page={page}&limit={per}&fields={FIELDS}')
        iiif=(data.get('config') or {}).get('iiif_url','https://www.artic.edu/iiif/2')
        rows=data.get('data',[])
        if not rows: break
        for r in rows:
            yield r,iiif
            n+=1
            if limit and n>=limit: return
        page+=1
        if page > (data.get('pagination') or {}).get('total_pages',page): break

def sync(conn, limit=None):
    n=0
    for r,iiif in _records(limit):
        image_id=r.get('image_id')
        open_image=bool(r.get('is_public_domain'))
        img=f'{iiif}/{image_id}/full/843,/0/default.jpg' if image_id and open_image else None
        thumb=f'{iiif}/{image_id}/full/400,/0/default.jpg' if image_id and open_image else None
        oid=str(r['id'])
        row={
          'canonical_key':f'artic:{oid}','source_id':'artic','source_object_id':oid,'title':r.get('title'),'artist':r.get('artist_display'),
          'date_display':r.get('date_display'),'year_start':clean_int(r.get('date_start')),'year_end':clean_int(r.get('date_end')),'country':r.get('place_of_origin'),
          'department':r.get('department_title'),'classification':r.get('artwork_type_title'),'medium':r.get('medium_display'),'dimensions':r.get('dimensions'),
          'image_url':img,'thumbnail_url':thumb,'object_url':f'https://www.artic.edu/artworks/{oid}','accession_number':r.get('main_reference_number'),
          'metadata_license':'CC0 except noted description fields','image_license':'Public-domain image' if open_image else 'Image use restricted or unverified','public_domain':1 if open_image else 0,
          'rights_note':r.get('copyright_notice')
        }
        upsert(conn,row); n+=1
        if n%1000==0:
            conn.commit()
            print(f'artic: {n:,} records imported', flush=True)
    if not n:
        raise ValueError("Art Institute collection download contained no artworks")
    conn.commit()
    return n
