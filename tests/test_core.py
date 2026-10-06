import os, tempfile, unittest
from pathlib import Path

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ['VISUAL_WORLD_DB_PATH']=str(Path(self.tmp.name)/'test.db')
        import importlib, schema
        importlib.reload(schema)
        self.schema=schema
        self.conn=schema.init_db()
    def tearDown(self):
        self.conn.close(); self.tmp.cleanup(); os.environ.pop('VISUAL_WORLD_DB_PATH',None)
    def test_schema_sources(self):
        self.assertGreaterEqual(self.conn.execute('select count(*) from sources').fetchone()[0],14)
        tables={r[0] for r in self.conn.execute("select name from sqlite_master where type='table'")}
        self.assertIn('canonical_artworks',tables); self.assertIn('canonical_members',tables); self.assertIn('sync_runs',tables)
    def test_canonical_merge(self):
        from connectors.common import upsert
        base={'title':'Same Work','artist':'Example Artist','date_display':'1888','year_start':1888,'classification':'Painting'}
        upsert(self.conn,{**base,'source_id':'met','source_object_id':'1','canonical_key':'met:1','object_url':'https://example.com/a'})
        upsert(self.conn,{**base,'source_id':'moma','source_object_id':'2','canonical_key':'moma:2','object_url':'https://example.com/b'})
        self.conn.commit()
        import canonicalize
        groups,raw=canonicalize.rebuild(self.conn)
        self.assertEqual((groups,raw),(1,2))
        row=self.conn.execute('select source_count from canonical_artworks').fetchone(); self.assertEqual(row[0],2)
    def test_qid_url_merges_with_unlinked_matching_record(self):
        from connectors.common import upsert
        base={'title':'Named Work','artist':'Example Artist','year_start':1888,'year_end':1888}
        upsert(self.conn,{**base,'source_id':'met','source_object_id':'1','wikidata_qid':'https://www.wikidata.org/wiki/Q123'})
        upsert(self.conn,{**base,'source_id':'moma','source_object_id':'2','description':'Longer museum description','medium':'Oil on canvas'})
        self.conn.commit()
        from canonicalize import rebuild
        self.assertEqual(rebuild(self.conn),(1,2))
        self.assertEqual(self.conn.execute('select canonical_key from canonical_artworks').fetchone()[0],'wikidata:Q123')
        self.assertEqual(self.conn.execute('select wikidata_qid from canonical_artworks').fetchone()[0],'Q123')
    def test_ambiguous_titles_and_conflicting_identifiers_stay_separate(self):
        from connectors.common import upsert
        for source,object_id,qid in [('met','1','Q1'),('met','2',None),('moma','3','Q2')]:
            upsert(self.conn,{'source_id':source,'source_object_id':object_id,'title':'Named Work','artist':'Artist','year_start':1900,'wikidata_qid':qid})
        upsert(self.conn,{'source_id':'artic','source_object_id':'4','title':'Untitled','artist':'Artist','year_start':1900})
        upsert(self.conn,{'source_id':'cleveland','source_object_id':'5','title':'Untitled','artist':'Artist','year_start':1900})
        self.conn.commit()
        from canonicalize import rebuild
        self.assertEqual(rebuild(self.conn),(5,5))
    def test_rebuild_preserves_ids_and_uses_only_open_images(self):
        from connectors.common import upsert
        base={'title':'Named Work','artist':'Artist','year_start':1888}
        upsert(self.conn,{**base,'source_id':'met','source_object_id':'1','public_domain':1})
        upsert(self.conn,{**base,'source_id':'moma','source_object_id':'2','public_domain':0,'image_url':'https://example.com/restricted.jpg'})
        self.conn.commit()
        from canonicalize import rebuild
        rebuild(self.conn)
        first=self.conn.execute('select id,image_url,public_domain,image_count from canonical_artworks').fetchone()
        self.assertIsNone(first['image_url'])
        self.assertEqual((first['public_domain'],first['image_count']),(1,0))
        upsert(self.conn,{**base,'source_id':'met','source_object_id':'1','public_domain':1,'image_url':'https://example.com/open.jpg'})
        self.conn.commit()
        rebuild(self.conn)
        second=self.conn.execute('select id,image_url,image_count from canonical_artworks').fetchone()
        self.assertEqual(second['id'],first['id'])
        self.assertEqual(second['image_url'],'https://example.com/open.jpg')
        self.assertEqual(second['image_count'],1)
        self.assertEqual(self.conn.execute("select count(*) from canonical_fts where canonical_fts match 'Named'").fetchone()[0],1)
    def test_search_filters_source_year_and_displayable_image(self):
        from connectors.common import upsert
        upsert(self.conn,{'source_id':'met','source_object_id':'1','title':'Open Painting','artist':'Artist','year_start':1888,'year_end':1888,'public_domain':1,'image_url':'https://example.com/open.jpg'})
        upsert(self.conn,{'source_id':'moma','source_object_id':'2','title':'Restricted Painting','artist':'Artist','public_domain':0,'image_url':'https://example.com/restricted.jpg'})
        self.conn.commit()
        from canonicalize import rebuild
        from server import search_artworks
        rebuild(self.conn)
        def search(**filters):
            options={'query':'','source':'','kind':'','with_images':False,'public_only':False,'year_from':-100000,'year_to':100000,'limit':60,'offset':0}
            options.update(filters)
            return search_artworks(self.conn,**options)
        self.assertEqual([item['title'] for item in search(source='met',year_from=1800,year_to=1900,with_images=True,public_only=True)],['Open Painting'])
        self.assertEqual(search(source='met%'),[])
        self.assertEqual(search(year_from=1800,year_to=1900)[0]['title'],'Open Painting')
        self.assertEqual(search(year_from=1900,year_to=1800),[])
        self.assertEqual(search(query='!!!'),[])
        self.assertEqual([item['title'] for item in search()], ['Open Painting'])
        self.assertEqual(search(source='moma'), [])
    def test_rights_do_not_infer_from_metadata(self):
        from connectors.common import upsert
        upsert(self.conn,{'source_id':'moma','source_object_id':'x','title':'Rights Test','metadata_license':'CC0','image_license':'Not included','public_domain':None})
        self.conn.commit(); row=self.conn.execute('select metadata_license,image_license,public_domain from artworks where source_object_id=?',('x',)).fetchone()
        self.assertEqual(row[0],'CC0'); self.assertEqual(row[1],'Not included'); self.assertIsNone(row[2])

if __name__=='__main__': unittest.main()
