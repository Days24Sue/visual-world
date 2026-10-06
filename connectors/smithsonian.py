import json, os, urllib.error
from .common import stream_lines, clean_int, joinish, upsert

BASE='https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan'
ART_UNITS=['CHNDM','FSG','HMSG','NMAfA','NPG','SAAM']
ALL_UNITS=['AAA','ACM','CFCHFOLKLIFE','CHNDM','EEPA','FBR','FSG','HAC','HMSG','HSFA','NAA','NASM','NMAAHC','NMAH','NMAI','NMAfA','NMNHANTHRO','NMNHBIRDS','NMNHBOTANY','NMNHEDUCATION','NMNHENTO','NMNHFISHES','NMNHHERPS','NMNHINV','NMNHMAMMALS','NMNHMINSCI','NMNHPALEO','NPG','NPM','NZP','SAAM','SIA','SIL']

def _vals(items,label_contains=None):
    out=[]
    for x in items or []:
        if not isinstance(x,dict): continue
        if label_contains and label_contains.lower() not in str(x.get('label','')).lower(): continue
        v=x.get('content') or x.get('indexedContent')
        if v: out.append(str(v))
    return ' | '.join(out)

def _first_media(dnr):
    media=((dnr.get('online_media') or {}).get('media') or [])
    open_media=[]
    for m in media:
        if not isinstance(m,dict) or str(m.get('type','')).lower()!='images': continue
        usage=((m.get('usage') or {}).get('access') or '').upper()
        if usage=='CC0': open_media.append(m)
    m=(open_media or [m for m in media if isinstance(m,dict) and str(m.get('type','')).lower()=='images'])
    m=m[0] if m else None
    if not m: return None,None,None,None
    ids=m.get('idsId')
    content=m.get('content') or m.get('thumbnail')
    thumb=m.get('thumbnail') or content
    full=(f'https://ids.si.edu/ids/deliveryService?id={ids}&max=1600' if ids and not str(ids).startswith('http') else content)
    usage=((m.get('usage') or {}).get('access') or '')
    return full,thumb,usage,ids

def _record(r):
    if r.get('type')!='edanmdm': return None
    content=r.get('content') or {}; dnr=content.get('descriptiveNonRepeating') or {}; idx=content.get('indexedStructured') or {}; free=content.get('freetext') or {}
    usage=((dnr.get('metadata_usage') or {}).get('access') or '').upper()
    if usage and usage!='CC0': return None
    oid=dnr.get('record_ID') or r.get('id')
    if not oid: return None
    title=dnr.get('title'); title=title.get('content') if isinstance(title,dict) else title
    full,thumb,img_usage,_=_first_media(dnr)
    dates=idx.get('date') or []
    date=joinish(dates) or _vals(free.get('date'))
    years=[clean_int(x) for x in dates if clean_int(x)]
    object_types=idx.get('object_type') or []
    names=idx.get('name') or []
    topics=idx.get('topic') or []
    places=idx.get('place') or []
    identifiers=free.get('identifier') or []
    accession=_vals(identifiers,'accession') or _vals(identifiers,'catalog') or _vals(identifiers)
    medium=_vals(free.get('physicalDescription'),'medium') or _vals(free.get('physicalDescription'),'material')
    dimensions=_vals(free.get('physicalDescription'),'measurement')
    artist=joinish(names)
    return {
      'canonical_key':f"smithsonian:{oid}",'source_id':'smithsonian','source_object_id':str(oid),'title':title,'artist':artist,
      'date_display':date,'year_start':min(years) if years else None,'year_end':max(years) if years else None,
      'country':joinish(places),'culture':joinish(idx.get('culture')),'department':r.get('unitCode'),
      'classification':joinish(object_types),'medium':medium,'dimensions':dimensions,'subjects':joinish(topics),'tags':joinish(topics),
      'description':_vals(free.get('notes')),'image_url':full if str(img_usage).upper()=='CC0' else None,
      'thumbnail_url':thumb if str(img_usage).upper()=='CC0' else None,'object_url':dnr.get('record_link'),'accession_number':accession,
      'metadata_license':'CC0' if usage=='CC0' else 'Smithsonian Open Access metadata','image_license':img_usage or 'record-specific',
      'public_domain':1 if str(img_usage).upper()=='CC0' else 0,'rights_note':dnr.get('data_source')
    }

def _units():
    raw=os.getenv('VISUAL_WORLD_SMITHSONIAN_UNITS','').strip()
    if not raw: return ART_UNITS
    if raw.lower()=='all': return ALL_UNITS
    return [x.strip().upper() for x in raw.split(',') if x.strip()]

def sync(conn, limit=None):
    n=0
    for unit in _units():
        for i in range(256):
            url=f'{BASE}/{unit.lower()}/{i:02x}.txt'
            try:
                lines=stream_lines(url)
                for line in lines:
                    line=line.strip()
                    if not line: continue
                    try: r=json.loads(line)
                    except json.JSONDecodeError: continue
                    row=_record(r)
                    if not row: continue
                    upsert(conn,row); n+=1
                    if n%1000==0: conn.commit()
                    if limit and n>=limit: conn.commit(); return n
            except urllib.error.HTTPError as e:
                if e.code==404: continue
                raise
    conn.commit(); return n
