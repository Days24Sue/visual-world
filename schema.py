import os, sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get('VISUAL_WORLD_DB_PATH', str(Path(__file__).parent / 'data' / 'visual_world.db')))

SCHEMA = r'''
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  homepage TEXT,
  kind TEXT NOT NULL,
  rights_note TEXT,
  sync_mode TEXT,
  last_sync TEXT,
  record_count INTEGER NOT NULL DEFAULT 0,
  image_count INTEGER NOT NULL DEFAULT 0,
  resource_count INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS artworks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_key TEXT,
  source_id TEXT NOT NULL REFERENCES sources(id),
  source_object_id TEXT NOT NULL,
  title TEXT,
  title_original TEXT,
  artist TEXT,
  artist_id TEXT,
  artist_names TEXT,
  date_display TEXT,
  year_start INTEGER,
  year_end INTEGER,
  country TEXT,
  culture TEXT,
  department TEXT,
  classification TEXT,
  medium TEXT,
  dimensions TEXT,
  style TEXT,
  subjects TEXT,
  tags TEXT,
  description TEXT,
  image_url TEXT,
  thumbnail_url TEXT,
  image_width INTEGER,
  image_height INTEGER,
  object_url TEXT,
  accession_number TEXT,
  wikidata_qid TEXT,
  metadata_license TEXT,
  image_license TEXT,
  public_domain INTEGER,
  rights_note TEXT,
  source_updated_at TEXT,
  ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_id, source_object_id)
);

CREATE TABLE IF NOT EXISTS canonical_artworks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_key TEXT NOT NULL UNIQUE,
  title TEXT,
  title_original TEXT,
  artist TEXT,
  date_display TEXT,
  year_start INTEGER,
  year_end INTEGER,
  country TEXT,
  culture TEXT,
  classification TEXT,
  medium TEXT,
  style TEXT,
  subjects TEXT,
  tags TEXT,
  description TEXT,
  image_url TEXT,
  thumbnail_url TEXT,
  public_domain INTEGER,
  wikidata_qid TEXT,
  source_count INTEGER NOT NULL DEFAULT 1,
  image_count INTEGER NOT NULL DEFAULT 0,
  source_ids TEXT,
  representative_artwork_id INTEGER REFERENCES artworks(id),
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS canonical_members (
  canonical_id INTEGER NOT NULL REFERENCES canonical_artworks(id) ON DELETE CASCADE,
  artwork_id INTEGER NOT NULL UNIQUE REFERENCES artworks(id) ON DELETE CASCADE,
  source_id TEXT NOT NULL,
  PRIMARY KEY(canonical_id, artwork_id)
);

CREATE TABLE IF NOT EXISTS sync_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  processed INTEGER NOT NULL DEFAULT 0,
  error TEXT
);

CREATE TABLE IF NOT EXISTS resources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(id),
  source_resource_id TEXT NOT NULL,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  category TEXT,
  description TEXT,
  tags TEXT,
  image_url TEXT,
  license_note TEXT,
  source_updated_at TEXT,
  ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_id, source_resource_id)
);

CREATE INDEX IF NOT EXISTS idx_artworks_source ON artworks(source_id);
CREATE INDEX IF NOT EXISTS idx_artworks_year ON artworks(year_start, year_end);
CREATE INDEX IF NOT EXISTS idx_artworks_artist ON artworks(artist);
CREATE INDEX IF NOT EXISTS idx_artworks_classification ON artworks(classification);
CREATE INDEX IF NOT EXISTS idx_artworks_public_domain ON artworks(public_domain);
CREATE INDEX IF NOT EXISTS idx_resources_source ON resources(source_id);
CREATE INDEX IF NOT EXISTS idx_resources_category ON resources(category);

CREATE VIRTUAL TABLE IF NOT EXISTS artworks_fts USING fts5(
  title, artist, date_display, country, culture, department, classification, medium, style, subjects, tags, description,
  content='artworks', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE INDEX IF NOT EXISTS idx_canonical_year ON canonical_artworks(year_start, year_end);
CREATE INDEX IF NOT EXISTS idx_canonical_artist ON canonical_artworks(artist);
CREATE INDEX IF NOT EXISTS idx_canonical_classification ON canonical_artworks(classification);
CREATE INDEX IF NOT EXISTS idx_canonical_public_domain ON canonical_artworks(public_domain);
CREATE INDEX IF NOT EXISTS idx_canonical_members_source ON canonical_members(source_id);

CREATE TABLE IF NOT EXISTS artist_profiles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  name_zh TEXT,
  aliases TEXT NOT NULL DEFAULT '[]',
  birth_year INTEGER,
  death_year INTEGER,
  nationality TEXT,
  movements TEXT NOT NULL DEFAULT '[]',
  info_source TEXT
);
CREATE TABLE IF NOT EXISTS canonical_artists (
  canonical_id INTEGER NOT NULL REFERENCES canonical_artworks(id) ON DELETE CASCADE,
  artist_id TEXT NOT NULL REFERENCES artist_profiles(id),
  PRIMARY KEY(canonical_id,artist_id)
);
CREATE INDEX IF NOT EXISTS idx_canonical_artists_artist ON canonical_artists(artist_id,canonical_id);
CREATE TABLE IF NOT EXISTS taxonomy_terms (
  id TEXT PRIMARY KEY,
  dimension TEXT NOT NULL,
  label TEXT NOT NULL,
  label_zh TEXT
);
CREATE TABLE IF NOT EXISTS canonical_terms (
  canonical_id INTEGER NOT NULL REFERENCES canonical_artworks(id) ON DELETE CASCADE,
  term_id TEXT NOT NULL REFERENCES taxonomy_terms(id),
  PRIMARY KEY(canonical_id,term_id)
);
CREATE INDEX IF NOT EXISTS idx_canonical_terms_term ON canonical_terms(term_id,canonical_id);
CREATE VIRTUAL TABLE IF NOT EXISTS exploration_fts USING fts5(
  search_text, tokenize='unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS canonical_fts USING fts5(
  title, artist, date_display, country, culture, classification, medium, style, subjects, tags, description,
  content='canonical_artworks', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS canonical_ai AFTER INSERT ON canonical_artworks BEGIN
  INSERT INTO canonical_fts(rowid,title,artist,date_display,country,culture,classification,medium,style,subjects,tags,description)
  VALUES(new.id,new.title,new.artist,new.date_display,new.country,new.culture,new.classification,new.medium,new.style,new.subjects,new.tags,new.description);
END;
CREATE TRIGGER IF NOT EXISTS canonical_ad AFTER DELETE ON canonical_artworks BEGIN
  INSERT INTO canonical_fts(canonical_fts,rowid,title,artist,date_display,country,culture,classification,medium,style,subjects,tags,description)
  VALUES('delete',old.id,old.title,old.artist,old.date_display,old.country,old.culture,old.classification,old.medium,old.style,old.subjects,old.tags,old.description);
END;
CREATE TRIGGER IF NOT EXISTS canonical_au AFTER UPDATE ON canonical_artworks BEGIN
  INSERT INTO canonical_fts(canonical_fts,rowid,title,artist,date_display,country,culture,classification,medium,style,subjects,tags,description)
  VALUES('delete',old.id,old.title,old.artist,old.date_display,old.country,old.culture,old.classification,old.medium,old.style,old.subjects,old.tags,old.description);
  INSERT INTO canonical_fts(rowid,title,artist,date_display,country,culture,classification,medium,style,subjects,tags,description)
  VALUES(new.id,new.title,new.artist,new.date_display,new.country,new.culture,new.classification,new.medium,new.style,new.subjects,new.tags,new.description);
END;

CREATE VIRTUAL TABLE IF NOT EXISTS resources_fts USING fts5(
  name, category, description, tags,
  content='resources', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS artworks_ai AFTER INSERT ON artworks BEGIN
  INSERT INTO artworks_fts(rowid,title,artist,date_display,country,culture,department,classification,medium,style,subjects,tags,description)
  VALUES(new.id,new.title,new.artist,new.date_display,new.country,new.culture,new.department,new.classification,new.medium,new.style,new.subjects,new.tags,new.description);
END;
CREATE TRIGGER IF NOT EXISTS artworks_ad AFTER DELETE ON artworks BEGIN
  INSERT INTO artworks_fts(artworks_fts,rowid,title,artist,date_display,country,culture,department,classification,medium,style,subjects,tags,description)
  VALUES('delete',old.id,old.title,old.artist,old.date_display,old.country,old.culture,old.department,old.classification,old.medium,old.style,old.subjects,old.tags,old.description);
END;
CREATE TRIGGER IF NOT EXISTS artworks_au AFTER UPDATE ON artworks BEGIN
  INSERT INTO artworks_fts(artworks_fts,rowid,title,artist,date_display,country,culture,department,classification,medium,style,subjects,tags,description)
  VALUES('delete',old.id,old.title,old.artist,old.date_display,old.country,old.culture,old.department,old.classification,old.medium,old.style,old.subjects,old.tags,old.description);
  INSERT INTO artworks_fts(rowid,title,artist,date_display,country,culture,department,classification,medium,style,subjects,tags,description)
  VALUES(new.id,new.title,new.artist,new.date_display,new.country,new.culture,new.department,new.classification,new.medium,new.style,new.subjects,new.tags,new.description);
END;
CREATE TRIGGER IF NOT EXISTS resources_ai AFTER INSERT ON resources BEGIN
  INSERT INTO resources_fts(rowid,name,category,description,tags)
  VALUES(new.id,new.name,new.category,new.description,new.tags);
END;
CREATE TRIGGER IF NOT EXISTS resources_ad AFTER DELETE ON resources BEGIN
  INSERT INTO resources_fts(resources_fts,rowid,name,category,description,tags)
  VALUES('delete',old.id,old.name,old.category,old.description,old.tags);
END;
CREATE TRIGGER IF NOT EXISTS resources_au AFTER UPDATE ON resources BEGIN
  INSERT INTO resources_fts(resources_fts,rowid,name,category,description,tags)
  VALUES('delete',old.id,old.name,old.category,old.description,old.tags);
  INSERT INTO resources_fts(rowid,name,category,description,tags)
  VALUES(new.id,new.name,new.category,new.description,new.tags);
END;
'''

SOURCES = [
    ('met','The Metropolitan Museum of Art','https://www.metmuseum.org/art/collection','museum','CC0 select metadata/images; verify per-object image status','bulk_csv'),
    ('moma','Museum of Modern Art','https://www.moma.org/collection/','museum','Metadata dataset CC0; images excluded from open dataset','bulk_csv'),
    ('nga','National Gallery of Art','https://www.nga.gov/artworks.html','museum','Metadata CC0; image rights vary by linked asset','bulk_csv'),
    ('artic','Art Institute of Chicago','https://www.artic.edu/collection','museum','API metadata largely CC0; image use depends on artwork/public-domain status','api'),
    ('cleveland','Cleveland Museum of Art','https://www.clevelandart.org/art/collection/search','museum','Open Access metadata and qualifying images CC0','api'),
    ('rijks','Rijksmuseum','https://www.rijksmuseum.nl/en/collection','museum','OAI-PMH metadata + IIIF; rights are record-specific','oai_pmh'),
    ('tate','Tate Collection snapshot','https://www.tate.org.uk/art','museum_snapshot','CC0 metadata snapshot; last updated Oct 2014; images excluded','bulk_csv'),
    ('whitney','Whitney Museum of American Art','https://whitney.org/collection','museum','CC0 metadata; images excluded from dataset','bulk_csv'),
    ('mplus','M+ Museum Hong Kong','https://www.mplus.org.hk/en/collection/','museum','CC0 metadata; images excluded from dataset','bulk_csv'),
    ('walters','Walters Art Museum','https://art.thewalters.org/','museum','Static collection data and images released CC0','bulk_csv'),
    ('smithsonian','Smithsonian Open Access · Art Units','https://www.si.edu/openaccess','museum_network','Bulk EDAN NDJSON; metadata/media rights are record-specific','bulk_ndjson'),
    ('awesome_illustrations','Awesome Illustrations','https://github.com/MrPeker/awesome-illustrations','resource_index','Link index; destination rights remain with each resource','markdown_index'),
    ('design_resources','Design Resources','https://github.com/reinaldosimoes/design-resources','resource_index','Link index; destination rights remain with each resource','markdown_index'),
    ('art_datasets','Art Datasets','https://github.com/georgeblck/art-datasets','resource_index','Dataset directory; destination rights remain with each source','markdown_index'),
]

def connect(path=DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def _migrate(conn):
    cols={r['name'] for r in conn.execute('PRAGMA table_info(sources)').fetchall()}
    if 'resource_count' not in cols:
        conn.execute('ALTER TABLE sources ADD COLUMN resource_count INTEGER NOT NULL DEFAULT 0')
    artwork_cols={r['name'] for r in conn.execute('PRAGMA table_info(artworks)')}
    if 'artist_names' not in artwork_cols:
        conn.execute('ALTER TABLE artworks ADD COLUMN artist_names TEXT')


def init_db(path=DB_PATH):
    conn = connect(path)
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.executemany('''INSERT INTO sources(id,name,homepage,kind,rights_note,sync_mode)
      VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
      name=excluded.name, homepage=excluded.homepage, kind=excluded.kind,
      rights_note=excluded.rights_note, sync_mode=excluded.sync_mode''', SOURCES)
    conn.commit()
    return conn

if __name__ == '__main__':
    c = init_db()
    print(DB_PATH)
    print(c.execute('select count(*) from sources').fetchone()[0], 'sources ready')
