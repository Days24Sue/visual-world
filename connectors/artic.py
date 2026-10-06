from .common import http_json, clean_int, upsert
BASE='https://api.artic.edu/api/v1/artworks'
FIELDS='id,title,artist_display,date_display,date_start,date_end,place_of_origin,department_title,artwork_type_title,medium_display,dimensions,image_id,is_public_domain,copyright_notice,main_reference_number,api_link'

def sync(conn, limit=None):
    page=1; n=0
    while True:
        per=100
        data=http_json(f'{BASE}?page={page}&limit={per}&fields={FIELDS}')
        iiif=(data.get('config') or {}).get('iiif_url','https://www.artic.edu/iiif/2')
        rows=data.get('data',[])
        if not rows: break
        for r in rows:
            image_id=r.get('image_id')
            open_image=bool(r.get('is_public_domain'))
            img=f'{iiif}/{image_id}/full/1200,/0/default.jpg' if image_id and open_image else None
            thumb=f'{iiif}/{image_id}/full/500,/0/default.jpg' if image_id and open_image else None
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
            if limit and n>=limit: conn.commit(); return n
        conn.commit(); page+=1
        if page > (data.get('pagination') or {}).get('total_pages',page): break
    return n
