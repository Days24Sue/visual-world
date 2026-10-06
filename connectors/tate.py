from .common import stream_csv, clean_int, first_year, upsert
URL='https://raw.githubusercontent.com/tategallery/collection/master/artwork_data.csv'

def sync(conn, limit=None):
    n=0
    for r in stream_csv(URL):
        oid=str(r.get('id') or r.get('accession_number') or '').strip()
        if not oid: continue
        year=clean_int(r.get('year')) or first_year(r.get('dateText'))
        row={
          'canonical_key':f'tate:{oid}','source_id':'tate','source_object_id':oid,
          'title':r.get('title'),'artist':r.get('artist'),'artist_id':r.get('artistId'),
          'date_display':r.get('dateText'),'year_start':year,'year_end':year,
          'classification':r.get('artistRole') or None,'medium':r.get('medium'),'dimensions':r.get('dimensions'),
          'thumbnail_url':None,'object_url':r.get('url') or None,
          'accession_number':r.get('accession_number'),'metadata_license':'CC0 snapshot','image_license':'Images are not part of the CC0 dataset',
          'public_domain':None,'rights_note':('Tate GitHub collection snapshot last updated October 2014. '
                                             + (r.get('thumbnailCopyright') or '')).strip()
        }
        upsert(conn,row); n+=1
        if n%1000==0: conn.commit()
        if limit and n>=limit: break
    conn.commit(); return n
