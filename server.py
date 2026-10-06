#!/usr/bin/env python3
import json, mimetypes, os, re, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from schema import connect, init_db
from canonicalize import rebuild as rebuild_canonical
from export_static import public_stats

ROOT=Path(__file__).parent
WEB=ROOT/'web'

def rows(conn,sql,args=()): return [dict(r) for r in conn.execute(sql,args).fetchall()]
def safe_fts(q):
    tokens=re.findall(r'[\w\u4e00-\u9fff]+(?:-[\w\u4e00-\u9fff]+)*', q, flags=re.UNICODE)
    return ' AND '.join('"'+t.replace('"',' ')+'"' for t in tokens) if tokens else None
def as_int(q,key,default,minimum=None,maximum=None):
    try: v=int((q.get(key) or [str(default)])[0])
    except (TypeError, ValueError): v=default
    if minimum is not None: v=max(minimum,v)
    if maximum is not None: v=min(maximum,v)
    return v

def search_artworks(conn,query,source,kind,with_images,public_only,year_from,year_to,limit,offset,
                    artist='',style='',subject='',sort='relevance',summary=False):
    if year_from>year_to:
        return {'items':[], 'total':0, 'artist_counts':[]} if summary else []
    where=["coalesce(nullif(c.thumbnail_url,''),nullif(c.image_url,'')) IS NOT NULL"]; args=[]
    if source:
        where.append('EXISTS (SELECT 1 FROM canonical_members m WHERE m.canonical_id=c.id AND m.source_id=?)'); args.append(source)
    if kind:
        if kind.startswith('kind-'):
            where.append('EXISTS (SELECT 1 FROM canonical_terms t WHERE t.canonical_id=c.id AND t.term_id=?)'); args.append(kind)
        else:
            where.append('c.classification like ?'); args.append('%'+kind+'%')
    if public_only: where.append('c.public_domain=1')
    if year_from>-100000: where.append('coalesce(c.year_end,c.year_start)>=?'); args.append(year_from)
    if year_to<100000: where.append('coalesce(c.year_start,c.year_end)<=?'); args.append(year_to)
    if artist:
        where.append('EXISTS (SELECT 1 FROM canonical_artists a WHERE a.canonical_id=c.id AND a.artist_id=?)'); args.append(artist)
    for term in (style,subject):
        if term:
            where.append('EXISTS (SELECT 1 FROM canonical_terms t WHERE t.canonical_id=c.id AND t.term_id=?)'); args.append(term)
    base=' FROM canonical_artworks c'
    params=[]; fts=''
    if query:
        match=safe_fts(query)
        if not match:
            return {'items':[], 'total':0, 'artist_counts':[]} if summary else []
        fts='exploration_fts' if conn.execute('SELECT 1 FROM exploration_fts LIMIT 1').fetchone() else 'canonical_fts'
        base+=f' JOIN {fts} f ON c.id=f.rowid'
        where.insert(0,f'{fts} MATCH ?'); params.append(match)
    base+=' WHERE '+' AND '.join(where); params+=args
    order={'oldest':'c.year_start IS NULL,c.year_start,c.id',
           'newest':'c.year_start IS NULL,c.year_start DESC,c.id DESC',
           'title':'c.title COLLATE NOCASE,c.id'}.get(sort, (f'bm25({fts}), ' if fts else '')+'c.source_count DESC,c.id DESC')
    items=rows(conn,'SELECT c.*'+base+' ORDER BY '+order+' LIMIT ? OFFSET ?',params+[limit,offset])
    for item in items:
        item['artist_ids']=[r[0] for r in conn.execute('SELECT artist_id FROM canonical_artists WHERE canonical_id=?',(item['id'],))]
        for dimension in ('style','subject','kind'):
            item[dimension+'_ids']=[r[0] for r in conn.execute('SELECT t.id FROM canonical_terms l JOIN taxonomy_terms t ON t.id=l.term_id WHERE l.canonical_id=? AND t.dimension=?',(item['id'],dimension))]
        images=conn.execute('SELECT a.thumbnail_url,a.image_url FROM canonical_members m JOIN artworks a ON a.id=m.artwork_id WHERE m.canonical_id=? AND a.public_domain=1',(item['id'],))
        item['image_alternatives']=list(dict.fromkeys(url for row in images for url in row if url))
    if not summary: return items
    total=conn.execute('SELECT count(*)'+base,params).fetchone()[0]
    counts=rows(conn,'SELECT a.artist_id id,count(*) count FROM canonical_artists a WHERE a.canonical_id IN (SELECT c.id'+base+') GROUP BY a.artist_id ORDER BY count DESC,a.artist_id LIMIT 12',params)
    return {'items':items,'total':total,'artist_counts':counts}

class H(BaseHTTPRequestHandler):
    def send_json(self,obj,status=200):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u=urllib.parse.urlparse(self.path); path=u.path; q=urllib.parse.parse_qs(u.query)
        if path.startswith('/api/'):
            conn=connect(); self._conn=conn
            if path=='/api/health':
                return self.send_json({'ok':True,'service':'visual-world','version':'0.6','artworks':conn.execute('select count(*) from artworks').fetchone()[0]})
            if path=='/api/stats':
                stats=public_stats(conn)
                stats.pop('snapshot_at')
                return self.send_json(stats)
            if path=='/api/explore':
                from exploration import catalog
                return self.send_json(catalog(conn))
            if path=='/api/search':
                query=(q.get('q') or [''])[0].strip(); source=(q.get('source') or [''])[0]; kind=(q.get('kind') or [''])[0]
                with_images=(q.get('with_images') or ['0'])[0]=='1'; public_only=(q.get('public_domain') or ['0'])[0]=='1'
                year_from=as_int(q,'year_from',-100000); year_to=as_int(q,'year_to',100000)
                limit=as_int(q,'limit',60,1,200); offset=as_int(q,'offset',0,0)
                result=search_artworks(conn,query,source,kind,with_images,public_only,year_from,year_to,limit,offset,
                    artist=(q.get('artist') or [''])[0],style=(q.get('style') or [''])[0],subject=(q.get('subject') or [''])[0],sort=(q.get('sort') or ['relevance'])[0],summary=True)
                return self.send_json({**result,'limit':limit,'offset':offset})
            if path=='/api/artwork':
                cid=as_int(q,'id',0,0)
                c=conn.execute("SELECT * FROM canonical_artworks WHERE id=? AND coalesce(nullif(thumbnail_url,''),nullif(image_url,'')) IS NOT NULL",(cid,)).fetchone()
                if not c: return self.send_json({'error':'not found'},404)
                members=rows(conn,'''SELECT a.*, s.name source_name, s.homepage source_homepage FROM canonical_members m JOIN artworks a ON a.id=m.artwork_id JOIN sources s ON s.id=a.source_id WHERE m.canonical_id=? ORDER BY CASE WHEN coalesce(a.thumbnail_url,a.image_url) IS NOT NULL THEN 0 ELSE 1 END,a.source_id''',(cid,))
                from export_static import detail_for
                detail=detail_for(conn,dict(c))
                detail['artwork']['artist_ids']=[r[0] for r in conn.execute('SELECT artist_id FROM canonical_artists WHERE canonical_id=?',(cid,))]
                for dimension in ('style','subject','kind'):
                    detail['artwork'][dimension+'_ids']=[r[0] for r in conn.execute('SELECT t.id FROM canonical_terms l JOIN taxonomy_terms t ON t.id=l.term_id WHERE l.canonical_id=? AND t.dimension=?',(cid,dimension))]
                return self.send_json(detail)
            if path=='/api/resources':
                query=(q.get('q') or [''])[0].strip(); source=(q.get('source') or [''])[0]
                limit=as_int(q,'limit',80,1,200); offset=as_int(q,'offset',0,0)
                where=[]; args=[]
                if source: where.append('r.source_id=?'); args.append(source)
                if query:
                    match=safe_fts(query)
                    if not match: return self.send_json({'items':[],'limit':limit,'offset':offset})
                    sql='SELECT r.* FROM resources_fts f JOIN resources r ON r.id=f.rowid WHERE resources_fts MATCH ?'; params=[match]
                    if where: sql+=' AND '+' AND '.join(where); params+=args
                    sql+=' ORDER BY bm25(resources_fts) LIMIT ? OFFSET ?'; params += [limit,offset]
                else:
                    sql='SELECT r.* FROM resources r'; params=[]
                    if where: sql+=' WHERE '+' AND '.join(where); params=args
                    sql+=' ORDER BY r.category,r.name LIMIT ? OFFSET ?'; params += [limit,offset]
                return self.send_json({'items':rows(conn,sql,params),'limit':limit,'offset':offset})
            if path=='/api/source-counts': return self.send_json(rows(conn,'select id,name,kind,record_count,image_count,resource_count,last_sync from sources order by name'))
            return self.send_json({'error':'not found'},404)
        rel='index.html' if path=='/' else path.lstrip('/')
        f=(WEB/rel).resolve()
        if not f.is_relative_to(WEB.resolve()) or not f.exists() or f.is_dir(): f=WEB/'index.html'
        b=f.read_bytes(); self.send_response(200); self.send_header('Content-Type',mimetypes.guess_type(str(f))[0] or 'application/octet-stream'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def finish(self):
        try: super().finish()
        finally:
            conn=getattr(self,'_conn',None)
            if conn is not None: conn.close()
    def log_message(self,fmt,*args): pass

if __name__=='__main__':
    conn=init_db()
    if conn.execute('select count(*) from artworks').fetchone()[0] and not conn.execute('select count(*) from canonical_artworks').fetchone()[0]:
        rebuild_canonical(conn)
    if not conn.execute('SELECT 1 FROM exploration_fts LIMIT 1').fetchone():
        from exploration import rebuild
        rebuild(conn)
    conn.close()
    host=os.environ.get('HOST','0.0.0.0'); port=int(os.environ.get('PORT','8787'))
    print(f'Visual World → http://{host}:{port}'); ThreadingHTTPServer((host,port),H).serve_forever()
