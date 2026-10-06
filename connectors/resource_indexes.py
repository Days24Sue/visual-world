import hashlib, re
from urllib.parse import urlparse
from .common import http_bytes, upsert_resource

INDEXES={
 'awesome_illustrations':('https://raw.githubusercontent.com/MrPeker/awesome-illustrations/master/readme.md','Illustration resource'),
 'design_resources':('https://raw.githubusercontent.com/reinaldosimoes/design-resources/main/README.md','Design resource'),
 'art_datasets':('https://raw.githubusercontent.com/georgeblck/art-datasets/master/README.md','Art dataset'),
}
LINK=re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')
HEADING=re.compile(r'^(#{1,6})\s+(.+?)\s*$')

def sync_one(conn,source_id,limit=None):
    url,default_cat=INDEXES[source_id]
    text=http_bytes(url,120).decode('utf-8',errors='replace')
    category=default_cat; n=0; seen=set()
    lines=text.splitlines()
    for idx,line in enumerate(lines):
        h=HEADING.match(line.strip())
        if h: category=re.sub(r'[*_`]+','',h.group(2)).strip()[:120] or default_cat
        for name,target in LINK.findall(line):
            if target.startswith(('https://img.shields.io','https://github.com/sponsors/')): continue
            if target in seen: continue
            seen.add(target)
            domain=urlparse(target).netloc.lower()
            if not domain: continue
            desc=re.sub(r'\s+',' ', re.sub(r'[`*_>#|]',' ',line)).strip()
            rid=hashlib.sha1(target.encode()).hexdigest()
            upsert_resource(conn,{
              'source_id':source_id,'source_resource_id':rid,'name':re.sub(r'[`*_]','',name).strip() or domain,
              'url':target,'category':category,'description':desc[:500],'tags':f'{default_cat} {category} {domain}',
              'license_note':'Index entry only. Check destination license/terms before reuse.'
            })
            n+=1
            if n%200==0: conn.commit()
            if limit and n>=limit: conn.commit(); return n
    conn.commit(); return n

def make(source_id):
    class C:
        @staticmethod
        def sync(conn,limit=None): return sync_one(conn,source_id,limit)
    return C

awesome_illustrations=make('awesome_illustrations')
design_resources=make('design_resources')
art_datasets=make('art_datasets')
