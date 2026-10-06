from .common import stream_csv, clean_int, first_year, pick, upsert
URLS=[
 ('M+ Collection','https://raw.githubusercontent.com/mplusmuseum/collection-data/master/objects.csv'),
 ('M+ Sigg Collection','https://raw.githubusercontent.com/mplusmuseum/collection-data/master/objects_sigg_collection.csv'),
]

def sync(conn, limit=None):
    n=0
    for collection,url in URLS:
        for i,r in enumerate(stream_csv(url),1):
            accession=pick(r,'Accession Number','accession_number','Object Number','object_number','Object No.','object_no')
            oid=str(pick(r,'Object ID','ObjectID','object_id','ID','id',default='') or accession or f'{collection}:{i}')
            title=pick(r,'Title','title','Object Name','object_name')
            artist=pick(r,'Artist','artist','Creator','creator','Constituent','constituent')
            date=pick(r,'Date','date','Date Text','date_text')
            y0=clean_int(pick(r,'Begin Year','begin_year','Date Begin','date_begin')) or first_year(date)
            y1=clean_int(pick(r,'End Year','end_year','Date End','date_end')) or y0
            row={
              'canonical_key':f'mplus:{oid}','source_id':'mplus','source_object_id':oid,
              'title':title,'artist':artist,'date_display':date,'year_start':y0,'year_end':y1,
              'department':collection,'classification':pick(r,'Classification','classification','Type','type'),
              'medium':pick(r,'Medium','medium'),'dimensions':pick(r,'Dimensions','dimensions'),
              'country':pick(r,'Country','country','Place','place'),'culture':pick(r,'Culture','culture'),
              'object_url':pick(r,'URL','url','Link','link'),'accession_number':accession,
              'metadata_license':'CC0 1.0','image_license':'Images excluded from open dataset','public_domain':None,
              'rights_note':'M+ releases textual collection metadata under CC0; images are not included.'
            }
            upsert(conn,row); n+=1
            if n%1000==0: conn.commit()
            if limit and n>=limit: conn.commit(); return n
    conn.commit(); return n
