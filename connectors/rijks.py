import urllib.parse, xml.etree.ElementTree as ET
from .common import http_bytes, upsert
BASE='https://data.rijksmuseum.nl/oai'
NS={
'oai':'http://www.openarchives.org/OAI/2.0/','dc':'http://purl.org/dc/elements/1.1/','dct':'http://purl.org/dc/terms/',
'edm':'http://www.europeana.eu/schemas/edm/','ore':'http://www.openarchives.org/ore/terms/','rdf':'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
}

def _text(node, path):
    x=node.find(path,NS)
    return (x.text or '').strip() if x is not None and x.text else None

def _texts(node,path):
    return ' | '.join((x.text or '').strip() for x in node.findall(path,NS) if x.text)

def _resource(node,path):
    x=node.find(path,NS)
    return x.attrib.get('{%s}resource'%NS['rdf']) if x is not None else None

def sync(conn, limit=None):
    token=None; n=0
    while True:
        if token:
            url=BASE+'?'+urllib.parse.urlencode({'verb':'ListRecords','resumptionToken':token})
        else:
            url=BASE+'?'+urllib.parse.urlencode({'verb':'ListRecords','metadataPrefix':'edm'})
        root=ET.fromstring(http_bytes(url,timeout=180))
        recs=root.findall('.//oai:record',NS)
        if not recs: break
        for rec in recs:
            header=rec.find('oai:header',NS)
            if header is not None and header.attrib.get('status')=='deleted': continue
            ident=_text(rec,'oai:header/oai:identifier')
            cho=rec.find('.//edm:ProvidedCHO',NS)
            agg=rec.find('.//ore:Aggregation',NS)
            if cho is None or not ident: continue
            oid=ident.rstrip('/').split('/')[-1]
            title=_text(cho,'dc:title')
            created=_text(cho,'dct:created')
            shown=None; image=None; rights=None
            if agg is not None:
                rights=_resource(agg,'edm:rights')
                x=agg.find('edm:isShownAt/edm:WebResource',NS)
                if x is not None: shown=x.attrib.get('{%s}about'%NS['rdf'])
                y=agg.find('edm:isShownBy/edm:WebResource',NS)
                if y is not None: image=y.attrib.get('{%s}about'%NS['rdf'])
            open_image=bool(rights and ('publicdomain' in rights.lower() or 'zero/1.0' in rights.lower()))
            row={
              'canonical_key':ident,'source_id':'rijks','source_object_id':oid,'title':title,'date_display':created,'medium':_texts(cho,'dc:format'),
              'classification':_texts(cho,'dc:type'),'subjects':_texts(cho,'dc:subject'),'description':_text(cho,'dc:description'),'dimensions':_texts(cho,'dct:extent'),
              'image_url':image if open_image else None,'thumbnail_url':image if open_image else None,'object_url':shown or ident,'accession_number':_text(cho,'dc:identifier'),'metadata_license':_resource(cho,'dc:rights') or 'record-specific',
              'image_license':rights or 'record-specific','public_domain':1 if open_image else 0,'rights_note':None,
              'source_updated_at':_text(rec,'oai:header/oai:datestamp')
            }
            upsert(conn,row); n+=1
            if limit and n>=limit: conn.commit(); return n
        conn.commit()
        tok=root.find('.//oai:resumptionToken',NS)
        token=(tok.text or '').strip() if tok is not None and tok.text else None
        if not token: break
    return n
