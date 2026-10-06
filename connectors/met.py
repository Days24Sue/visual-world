from .common import stream_csv, clean_int, upsert

URL='https://media.githubusercontent.com/media/metmuseum/openaccess/master/MetObjects.csv'

def sync(conn, limit=None):
    n=0
    for r in stream_csv(URL):
        oid=r.get('Object ID')
        if not oid: continue
        pd = str(r.get('Is Public Domain','')).strip().lower() == 'true'
        row={
          'canonical_key': r.get('Link Resource') or f'met:{oid}', 'source_id':'met','source_object_id':oid,
          'title':r.get('Title'),'artist':r.get('Artist Display Name'),'artist_id':r.get('Artist Wikidata URL'),
          'date_display':r.get('Object Date'),'year_start':clean_int(r.get('Object Begin Date')),'year_end':clean_int(r.get('Object End Date')),
          'country':r.get('Country'),'culture':r.get('Culture'),'department':r.get('Department'),'classification':r.get('Classification'),
          'medium':r.get('Medium'),'dimensions':r.get('Dimensions'),'subjects':r.get('Tags'),'tags':r.get('Tags'),
          'image_url':None,'thumbnail_url':None,'object_url':r.get('Link Resource'),
          'accession_number':r.get('AccessionNumber'),'wikidata_qid':r.get('Object Wikidata URL'),
          'metadata_license':'CC0 select dataset','image_license':'CC0 when object is marked Public Domain','public_domain':1 if pd else 0,
          'rights_note':None,'source_updated_at':None
        }
        upsert(conn,row); n+=1
        if n%1000==0: conn.commit()
        if limit and n>=limit: break
    conn.commit(); return n
