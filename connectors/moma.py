from .common import stream_csv, clean_int, upsert
URL='https://media.githubusercontent.com/media/MuseumofModernArt/collection/main/Artworks.csv'

def sync(conn, limit=None):
    n=0
    for r in stream_csv(URL):
        oid=r.get('ObjectID')
        if not oid: continue
        row={
          'canonical_key': f'moma:{oid}','source_id':'moma','source_object_id':oid,
          'title':r.get('Title'),'artist':r.get('Artist'),'artist_id':r.get('ConstituentID'),
          'date_display':r.get('Date'),'year_start':clean_int(r.get('DateBegin')),'year_end':clean_int(r.get('DateEnd')),
          'department':r.get('Department'),'classification':r.get('Classification'),'medium':r.get('Medium'),'dimensions':r.get('Dimensions'),
          'object_url':r.get('URL'),'accession_number':r.get('AccessionNumber'),'metadata_license':'CC0 dataset','image_license':'Not included in open dataset',
          'public_domain':None,'rights_note':'MoMA open dataset excludes images.'
        }
        upsert(conn,row); n+=1
        if n%1000==0: conn.commit()
        if limit and n>=limit: break
    conn.commit(); return n
