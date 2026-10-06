from schema import init_db
from connectors.common import upsert, upsert_resource

DEMO=[
{'source_id':'artic','source_object_id':'27992','canonical_key':'artic:27992','title':'A Sunday on La Grande Jatte — 1884','artist':'Georges Seurat','date_display':'1884–86','year_start':1884,'year_end':1886,'classification':'Painting','medium':'Oil on canvas','image_url':'https://www.artic.edu/iiif/2/2d484387-2509-5e8e-2c43-22f9981972eb/full/1000,/0/default.jpg','thumbnail_url':'https://www.artic.edu/iiif/2/2d484387-2509-5e8e-2c43-22f9981972eb/full/500,/0/default.jpg','object_url':'https://www.artic.edu/artworks/27992','public_domain':1,'metadata_license':'CC0','image_license':'Public domain'},
{'source_id':'met','source_object_id':'436535','canonical_key':'met:436535','title':'Wheat Field with Cypresses','artist':'Vincent van Gogh','date_display':'1889','year_start':1889,'year_end':1889,'classification':'Painting','medium':'Oil on canvas','object_url':'https://www.metmuseum.org/art/collection/search/436535','public_domain':1,'metadata_license':'CC0 select dataset','image_license':'CC0 when Public Domain'},
{'source_id':'met','source_object_id':'437133','canonical_key':'met:437133','title':'The Dance Class','artist':'Edgar Degas','date_display':'1874','year_start':1874,'year_end':1874,'classification':'Painting','medium':'Oil on canvas','object_url':'https://www.metmuseum.org/art/collection/search/437133','public_domain':1,'metadata_license':'CC0 select dataset','image_license':'CC0 when Public Domain'},
{'source_id':'moma','source_object_id':'78411','canonical_key':'moma:78411','title':'The Starry Night','artist':'Vincent van Gogh','date_display':'1889','year_start':1889,'year_end':1889,'classification':'Painting','medium':'Oil on canvas','object_url':'https://www.moma.org/collection/works/79802','public_domain':None,'metadata_license':'CC0 dataset','image_license':'Not included in open dataset'},
{'source_id':'mplus','source_object_id':'demo-1','canonical_key':'mplus:demo-1','title':'M+ modern visual culture index','artist':'Demo record','date_display':'20th–21st century','classification':'Visual culture','medium':'Metadata demo','object_url':'https://www.mplus.org.hk/en/collection/','public_domain':None,'metadata_license':'CC0 1.0','image_license':'Images excluded from dataset'},
]
RESOURCES=[
{'source_id':'awesome_illustrations','source_resource_id':'demo-open-doodles','name':'Open Doodles','url':'https://www.opendoodles.com/','category':'Illustration','description':'Open-source illustration library indexed from a GitHub resource list.','tags':'illustration hand drawn open source','license_note':'Check destination license.'},
{'source_id':'design_resources','source_resource_id':'demo-blush','name':'Blush','url':'https://blush.design/','category':'Illustration','description':'Illustration creation and discovery resource.','tags':'illustration design characters','license_note':'Check destination license.'},
{'source_id':'art_datasets','source_resource_id':'demo-wikiart','name':'WikiArt datasets','url':'https://www.wikiart.org/','category':'Art datasets','description':'Art-history image and metadata resources; dataset availability varies by project.','tags':'art history styles dataset','license_note':'Check dataset and image rights separately.'},
]
c=init_db()
for x in DEMO: upsert(c,x)
for x in RESOURCES: upsert_resource(c,x)
c.commit()
for sid in {x['source_id'] for x in DEMO}:
    c.execute('UPDATE sources SET record_count=(SELECT count(*) FROM artworks WHERE source_id=?), image_count=(SELECT count(*) FROM artworks WHERE source_id=? AND public_domain=1 AND coalesce(thumbnail_url,image_url) is not null) WHERE id=?',(sid,sid,sid))
for sid in {x['source_id'] for x in RESOURCES}:
    c.execute('UPDATE sources SET resource_count=(SELECT count(*) FROM resources WHERE source_id=?) WHERE id=?',(sid,sid))
c.commit()
print('seeded', len(DEMO), 'artworks and',len(RESOURCES),'resources')
