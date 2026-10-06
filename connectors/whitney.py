from .common import stream_csv, clean_int, first_year, pick, upsert
URL='https://raw.githubusercontent.com/whitneymuseum/open-access/main/artworks.csv'

def sync(conn, limit=None):
    n=0
    for i,r in enumerate(stream_csv(URL),1):
        oid=str(pick(r,'id','ID','object_id','Object ID','ObjectID','work_id','Work ID',default='')).strip()
        accession=pick(r,'accession_number','Accession Number','accessionNumber','Accession')
        if not oid: oid=str(accession or i)
        date=pick(r,'date','Date','date_text','Date Text','display_date')
        year=clean_int(pick(r,'year','Year')) or first_year(date)
        title=pick(r,'title','Title','object_name','Object Name')
        artist=pick(r,'artist','Artist','artists','Artist Name','artist_name')
        url=pick(r,'url','URL','link','Link') or (f'https://whitney.org/collection/works/{oid}' if oid.isdigit() else None)
        row={
          'canonical_key':f'whitney:{oid}','source_id':'whitney','source_object_id':oid,
          'title':title,'artist':artist,'artist_id':pick(r,'artist_id','Artist ID','artistId'),
          'date_display':date,'year_start':year,'year_end':year,'classification':pick(r,'classification','Classification','type','Type'),
          'medium':pick(r,'medium','Medium'),'dimensions':pick(r,'dimensions','Dimensions'),
          'object_url':url,'accession_number':accession,'metadata_license':'CC0','image_license':'Images excluded from open dataset',
          'public_domain':None,'rights_note':'Whitney open-access CSV metadata is CC0; image rights are separate.'
        }
        upsert(conn,row); n+=1
        if n%1000==0: conn.commit()
        if limit and n>=limit: break
    conn.commit(); return n
