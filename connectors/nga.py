from .common import stream_csv, clean_int, upsert
BASE='https://raw.githubusercontent.com/NationalGalleryOfArt/opendata/main/data/'
OBJECTS=BASE+'objects.csv'
IMAGES=BASE+'published_images.csv'

def _image_index():
    out={}
    for r in stream_csv(IMAGES):
        if str(r.get('openaccess','')).strip() not in ('1','true','True'): continue
        oid=str(r.get('depictstmsobjectid') or '').strip()
        if not oid: continue
        if oid in out and str(r.get('viewtype','')).lower()!='primary': continue
        base=r.get('iiifurl') or r.get('iiifURL')
        uuid=r.get('uuid')
        full=None
        if base:
            base=base.rstrip('/')
            full=base+'/full/!1600,1600/0/default.jpg' if '/full/' not in base else base
        elif uuid:
            full=f'https://api.nga.gov/iiif/{uuid}/full/!1600,1600/0/default.jpg'
        thumb=r.get('iiifthumburl') or r.get('iiifThumbURL') or (f'https://api.nga.gov/iiif/{uuid}/full/!600,600/0/default.jpg' if uuid else full)
        out[oid]=(full,thumb,clean_int(r.get('width')),clean_int(r.get('height')),uuid)
    return out

def sync(conn, limit=None):
    images=_image_index(); n=0
    for r in stream_csv(OBJECTS):
        oid=str(r.get('objectid') or r.get('objectID') or r.get('ObjectID') or '').strip()
        if not oid: continue
        img=images.get(oid,(None,None,None,None,None))
        row={
          'canonical_key': f'nga:{oid}','source_id':'nga','source_object_id':oid,
          'title':r.get('title'),'artist':r.get('attribution'),'date_display':r.get('displaydate'),
          'year_start':clean_int(r.get('beginyear')),'year_end':clean_int(r.get('endyear')),
          'department':r.get('departmentabbr'),'classification':r.get('visualbrowserclassification') or r.get('classification'),
          'medium':r.get('medium'),'dimensions':r.get('dimensions'),'description':r.get('provenancetext'),
          'image_url':img[0],'thumbnail_url':img[1],'image_width':img[2],'image_height':img[3],
          'object_url':f'https://www.nga.gov/artworks/{oid}' if not r.get('url') else r.get('url'),
          'accession_number':r.get('accessionnum'),'wikidata_qid':r.get('wikidataid'),
          'metadata_license':'CC0 dataset','image_license':'NGA Open Access' if img[0] else 'No open-access image joined',
          'public_domain':1 if img[0] else 0,'rights_note':'Only published_images rows flagged openaccess=1 are exposed as image URLs.',
          'source_updated_at':r.get('lastdetectedmodification')
        }
        upsert(conn,row); n+=1
        if n%1000==0: conn.commit()
        if limit and n>=limit: break
    conn.commit(); return n
