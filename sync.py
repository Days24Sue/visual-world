#!/usr/bin/env python3
import argparse, traceback, sys
from datetime import datetime, timezone
from schema import init_db
from connectors import CONNECTORS
from connectors.common import now_iso

RESOURCE_IDS={'awesome_illustrations','design_resources','art_datasets'}

def main():
    p=argparse.ArgumentParser(description='Visual World full collection synchronizer')
    p.add_argument('--source', choices=list(CONNECTORS)+['all','artworks','resources'], default='all')
    p.add_argument('--limit', type=int, default=None, help='Per-source record cap. Omit for full sync.')
    args=p.parse_args()
    conn=init_db()
    if args.source=='all': selected=list(CONNECTORS)
    elif args.source=='artworks': selected=[x for x in CONNECTORS if x not in RESOURCE_IDS]
    elif args.source=='resources': selected=[x for x in CONNECTORS if x in RESOURCE_IDS]
    else: selected=[args.source]
    had_error=False
    for name in selected:
        print(f'\n=== {name} ===')
        started=now_iso(); cur=conn.execute('INSERT INTO sync_runs(source_id,started_at,status) VALUES(?,?,?)',(name,started,'running')); run_id=cur.lastrowid; conn.commit()
        try:
            count=CONNECTORS[name].sync(conn,args.limit)
            if name in RESOURCE_IDS:
                conn.execute('UPDATE sources SET last_sync=?, resource_count=(SELECT count(*) FROM resources WHERE source_id=?) WHERE id=?',(now_iso(),name,name))
            else:
                conn.execute('''UPDATE sources SET last_sync=?,
                  record_count=(SELECT count(*) FROM artworks WHERE source_id=?),
                  image_count=(SELECT count(*) FROM artworks WHERE source_id=? AND public_domain=1 AND coalesce(thumbnail_url,image_url) is not null)
                  WHERE id=?''',(now_iso(),name,name,name))
            conn.execute('UPDATE sync_runs SET finished_at=?,status=?,processed=? WHERE id=?',(now_iso(),'ok',count or 0,run_id)); conn.commit(); print(f'{name}: {count} records processed')
        except Exception as e:
            had_error=True
            conn.execute('UPDATE sync_runs SET finished_at=?,status=?,error=? WHERE id=?',(now_iso(),'error',str(e)[:2000],run_id)); conn.commit(); print(f'{name}: ERROR: {e}'); traceback.print_exc()
    from canonicalize import rebuild
    groups, raw = rebuild(conn)
    print(f'Canonical index: {groups:,} works from {raw:,} source records.')
    total=conn.execute('select count(*) from artworks').fetchone()[0]
    resources=conn.execute('select count(*) from resources').fetchone()[0]
    print(f'\nDatabase now contains {total:,} artwork records and {resources:,} indexed resources.')
    if had_error:
        sys.exit(1)

if __name__=='__main__': main()
