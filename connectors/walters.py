from .common import stream_csv, clean_int, first_year, pick, upsert
ART='https://raw.githubusercontent.com/WaltersArtMuseum/api-thewalters-org/master/art.csv'
MEDIA='https://raw.githubusercontent.com/WaltersArtMuseum/api-thewalters-org/master/media.csv'

def _k(r,*names): return pick(r,*names,default='')

def _media_index():
    by={}
    for r in stream_csv(MEDIA):
        oid=str(_k(r,'ObjectID','objectID','object_id','ObjectId','objectid','ArtID','art_id')).strip()
        if not oid: continue
        url=_k(r,'MediaURL','media_url','URL','url','ImageURL','image_url','LargeImageURL','large_image_url','PublicURL','public_url')
        thumb=_k(r,'ThumbnailURL','thumbnail_url','ThumbURL','thumb_url','SmallImageURL','small_image_url') or url
        if url or thumb:
            by.setdefault(oid,(url or thumb,thumb or url))
    return by

def sync(conn, limit=None):
    media=_media_index()
    n=0
    for i,r in enumerate(stream_csv(ART),1):
        oid=str(_k(r,'ObjectID','objectID','object_id','ObjectId','objectid','ID','id') or i).strip()
        accession=_k(r,'AccessionNumber','accession_number','Accession Number','ObjectNumber','object_number')
        date=_k(r,'DateText','date_text','Date','date','DisplayDate','display_date')
        y0=clean_int(_k(r,'BeginYear','begin_year','DateBegin','date_begin')) or first_year(date)
        y1=clean_int(_k(r,'EndYear','end_year','DateEnd','date_end')) or y0
        img,thumb=media.get(oid,(None,None))
        row={
          'canonical_key':f'walters:{oid}','source_id':'walters','source_object_id':oid,
          'title':_k(r,'Title','title','ObjectName','object_name'),'artist':_k(r,'Creator','creator','Artist','artist','CreatorName','creator_name'),
          'date_display':date,'year_start':y0,'year_end':y1,'classification':_k(r,'Classification','classification','ObjectType','object_type'),
          'medium':_k(r,'Medium','medium'),'dimensions':_k(r,'Dimensions','dimensions'),'culture':_k(r,'Culture','culture'),
          'description':_k(r,'Description','description'),'image_url':img,'thumbnail_url':thumb,
          'object_url':_k(r,'PublicURL','public_url','URL','url') or (f'https://art.thewalters.org/detail/{oid}/' if oid else None),
          'accession_number':accession,'metadata_license':'CC0','image_license':'CC0 dataset release','public_domain':1,
          'rights_note':'Walters static collection data and released images are published under CC0.'
        }
        upsert(conn,row); n+=1
        if n%1000==0: conn.commit()
        if limit and n>=limit: break
    conn.commit(); return n
