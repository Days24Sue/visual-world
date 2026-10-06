#!/usr/bin/env python3
import json, mimetypes, os, re, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from schema import connect, init_db
from canonicalize import rebuild as rebuild_canonical

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

def search_artworks(conn,query,source,kind,with_images,public_only,year_from,year_to,limit,offset):
    if year_from>year_to: return []
    where=[]; args=[]
    if source: where.append('EXISTS (SELECT 1 FROM canonical_members m WHERE m.canonical_id=c.id AND m.source_id=?)'); args.append(source)
    if kind: where.append('c.classification like ?'); args.append('%'+kind+'%')
    if with_images: where.append('coalesce(c.thumbnail_url,c.image_url) is not null')
    if public_only: where.append('c.public_domain=1')
    if year_from>-100000: where.append('coalesce(c.year_end,c.year_start)>=?'); args.append(year_from)
    if year_to<100000: where.append('coalesce(c.year_start,c.year_end)<=?'); args.append(year_to)
    if query:
        match=safe_fts(query)
        if not match: return []
        sql='SELECT c.* FROM canonical_fts f JOIN canonical_artworks c ON c.id=f.rowid WHERE canonical_fts MATCH ?'; params=[match]
        if where: sql+=' AND '+' AND '.join(where); params+=args
        sql+=' ORDER BY bm25(canonical_fts), c.source_count DESC LIMIT ? OFFSET ?'; params += [limit,offset]
    else:
        sql='SELECT c.* FROM canonical_artworks c'; params=[]
        if where: sql+=' WHERE '+' AND '.join(where); params=args
        sql+=' ORDER BY CASE WHEN coalesce(c.thumbnail_url,c.image_url) IS NOT NULL THEN 0 ELSE 1 END, c.source_count DESC, c.id DESC LIMIT ? OFFSET ?'; params += [limit,offset]
    return rows(conn,sql,params)

class H(BaseHTTPRequestHandler):
    def send_json(self,obj,status=200):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u=urllib.parse.urlparse(self.path); path=u.path; q=urllib.parse.parse_qs(u.query)
        if path.startswith('/api/'):
            conn=connect(); self._conn=conn
            if path=='/api/health':
                return self.send_json({'ok':True,'service':'visual-world','version':'0.5','artworks':conn.execute('select count(*) from artworks').fetchone()[0]})
            if path=='/api/stats':
                total=conn.execute('select count(*) from artworks').fetchone()[0]
                canonical=conn.execute('select count(*) from canonical_artworks').fetchone()[0]
                imgs=conn.execute("select count(*) from artworks where public_domain=1 and coalesce(thumbnail_url,image_url) is not null").fetchone()[0]
                artists=conn.execute("select count(distinct artist) from artworks where artist is not null and artist<>''").fetchone()[0]
                resource_total=conn.execute('select count(*) from resources').fetchone()[0]
                src=rows(conn,"""select s.*, (select r.status from sync_runs r where r.source_id=s.id order by r.id desc limit 1) last_status, (select r.error from sync_runs r where r.source_id=s.id order by r.id desc limit 1) last_error from sources s order by case when s.kind='resource_index' then 1 else 0 end, s.record_count desc, s.resource_count desc, s.name""")
                return self.send_json({'total':total,'canonical':canonical,'duplicates':max(0,total-canonical),'images':imgs,'artists':artists,'resources':resource_total,'sources':src})
            if path=='/api/search':
                query=(q.get('q') or [''])[0].strip(); source=(q.get('source') or [''])[0]; kind=(q.get('kind') or [''])[0]
                with_images=(q.get('with_images') or ['0'])[0]=='1'; public_only=(q.get('public_domain') or ['0'])[0]=='1'
                year_from=as_int(q,'year_from',-100000); year_to=as_int(q,'year_to',100000)
                limit=as_int(q,'limit',60,1,200); offset=as_int(q,'offset',0,0)
                items=search_artworks(conn,query,source,kind,with_images,public_only,year_from,year_to,limit,offset)
                return self.send_json({'items':items,'limit':limit,'offset':offset})
            if path=='/api/artwork':
                cid=as_int(q,'id',0,0)
                c=conn.execute('SELECT * FROM canonical_artworks WHERE id=?',(cid,)).fetchone()
                if not c: return self.send_json({'error':'not found'},404)
                members=rows(conn,'''SELECT a.*, s.name source_name, s.homepage source_homepage FROM canonical_members m JOIN artworks a ON a.id=m.artwork_id JOIN sources s ON s.id=a.source_id WHERE m.canonical_id=? ORDER BY CASE WHEN coalesce(a.thumbnail_url,a.image_url) IS NOT NULL THEN 0 ELSE 1 END,a.source_id''',(cid,))
                return self.send_json({'artwork':dict(c),'sources':members})
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
    conn.close()
    host=os.environ.get('HOST','0.0.0.0'); port=int(os.environ.get('PORT','8787'))
    print(f'Visual World → http://{host}:{port}'); ThreadingHTTPServer((host,port),H).serve_forever()
