import csv, io, json, urllib.error, urllib.request
from datetime import datetime, timezone

UA = 'VisualWorld/0.2 (+personal research visual index)'

def http_response(url, timeout=90):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=timeout)

def http_bytes(url, timeout=90):
    with http_response(url, timeout) as r:
        return r.read()

def http_json(url, timeout=90):
    return json.loads(http_bytes(url, timeout).decode('utf-8'))

def stream_csv(url, encoding='utf-8-sig'):
    resp = http_response(url, timeout=240)
    text = io.TextIOWrapper(resp, encoding=encoding, newline='')
    try:
        yield from csv.DictReader(text)
    finally:
        resp.close()

def stream_lines(url, encoding='utf-8'):
    resp=http_response(url, timeout=240)
    text=io.TextIOWrapper(resp,encoding=encoding)
    try:
        for line in text:
            yield line
    finally:
        resp.close()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def clean_int(v):
    try:
        if v is None or str(v).strip()=='' : return None
        return int(float(str(v).strip()))
    except Exception:
        return None

def first_year(v):
    import re
    if v is None: return None
    m=re.search(r'(?<!\d)(1[0-9]{3}|20[0-9]{2}|[5-9][0-9]{2})(?!\d)',str(v))
    return int(m.group(1)) if m else None

def pick(d, *keys, default=''):
    for k in keys:
        v=d.get(k)
        if v not in (None,'',[]): return v
    return default

def joinish(v):
    if v is None: return ''
    if isinstance(v, list):
        out=[]
        for x in v:
            if isinstance(x,dict):
                x=x.get('content') or x.get('label') or x.get('name') or ''
            if x not in (None,''): out.append(str(x))
        return ' | '.join(out)
    return str(v)

def upsert(conn, row):
    cols = [
      'canonical_key','source_id','source_object_id','title','title_original','artist','artist_id',
      'date_display','year_start','year_end','country','culture','department','classification','medium',
      'dimensions','style','subjects','tags','description','image_url','thumbnail_url','image_width','image_height',
      'object_url','accession_number','wikidata_qid','metadata_license','image_license','public_domain',
      'rights_note','source_updated_at'
    ]
    values=[row.get(c) for c in cols]
    update=', '.join(f'{c}=excluded.{c}' for c in cols if c not in ('source_id','source_object_id'))
    sql=f"INSERT INTO artworks({','.join(cols)}) VALUES({','.join('?' for _ in cols)}) ON CONFLICT(source_id,source_object_id) DO UPDATE SET {update}"
    conn.execute(sql, values)

def upsert_resource(conn,row):
    cols=['source_id','source_resource_id','name','url','category','description','tags','image_url','license_note','source_updated_at']
    vals=[row.get(c) for c in cols]
    update=', '.join(f'{c}=excluded.{c}' for c in cols if c not in ('source_id','source_resource_id'))
    conn.execute(f"INSERT INTO resources({','.join(cols)}) VALUES({','.join('?' for _ in cols)}) ON CONFLICT(source_id,source_resource_id) DO UPDATE SET {update}",vals)
