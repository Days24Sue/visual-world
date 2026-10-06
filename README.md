# Visual World / 世界视觉库 · V0.5 Public Beta Foundation

**Visual World** is an open visual-culture index designed to aggregate as much publicly indexable art, illustration and design material as possible across museums, open collections and resource directories.

The V0.5 code is published at [GitHub](https://github.com/Days24Sue/visual-world). The free public beta is built as a periodically refreshed GitHub Pages snapshot; the original Python API and Docker deployment remain available for a future dynamic host.

It is **not** a hand-picked image gallery. The canonical database can grow beyond the bounded free-site snapshot. GitHub Pages searches its exported snapshot in the browser, while a future dynamic host can serve a larger corpus through the existing API.

## What V0.5 adds

- **Canonical artwork layer** — conservative cross-source deduplication while preserving every source record.
- **Provenance-first detail view** — one artwork can expose multiple museum/source records and their rights status.
- **Search filters** — source, year range, images only and public-domain only.
- **Sync history** — each ingestion run records success/error and processed count.
- **Free public beta** — GitHub Actions synchronizes a bounded real-data snapshot and publishes a rights-aware static site to GitHub Pages.
- **Optional dynamic deployment** — configurable persistent database path, Dockerfile, health endpoint and a paid Render disk template.
- **Open-source readiness** — MIT license for code, contribution guide, connector contract, data-rights policy and GitHub Actions CI/source smoke checks.

## Connected artwork sources

Current implemented connectors include:

- The Metropolitan Museum of Art
- Museum of Modern Art
- National Gallery of Art
- Art Institute of Chicago
- Cleveland Museum of Art
- Rijksmuseum
- Tate Collection snapshot
- Whitney Museum of American Art
- M+ Museum Hong Kong
- Walters Art Museum
- Smithsonian Open Access art/design units

Resource indexes currently include Awesome Illustrations, Design Resources and Art Datasets. See `source_registry.csv` for the implementation backlog and source-specific rights strategy.

## Data model

```text
source APIs / bulk files / OAI-PMH / NDJSON / resource indexes
                              ↓
                         connectors
                              ↓
                     normalized records
                  artworks / resources / rights
                              ↓
                    canonical artworks
                              ↓
                      SQLite + FTS5
                              ↓
                        public UI
```

The repository stores **code and metadata logic**, not mirrored multi-gigabyte third-party image archives. Image and metadata rights are tracked separately. See [`docs/DATA_RIGHTS.md`](docs/DATA_RIGHTS.md).

## Run locally

Mac users can double-click `START_MAC.command`, or run:

```bash
python3 seed_demo.py
python3 canonicalize.py
python3 server.py
```

Open `http://127.0.0.1:8787`.

## Full synchronization

```bash
python3 sync.py --source all
```

Artwork sources only:

```bash
python3 sync.py --source artworks
```

Resource indexes only:

```bash
python3 sync.py --source resources
```

For development only, cap each source:

```bash
python3 sync.py --source all --limit 1000
```

Omit `--limit` for a true full source sync.

## Canonicalization

After synchronization `sync.py` rebuilds the canonical index automatically. It can also be run separately:

```bash
python3 canonicalize.py
```

V0.5 merges automatically only with strong evidence: a shared Wikidata QID or normalized **title + artist + year**. Ambiguous records remain separate rather than risking incorrect merges.

## Deploy

The zero-cost beta uses GitHub Pages. The `Publish free beta` workflow builds an isolated SQLite database, synchronizes up to 200 records per source, exports a static snapshot and refreshes it weekly. The Python API is not running on Pages; search and filters use the bounded snapshot in the browser. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

For an optional containerized dynamic service with a persistent database, set:

```text
VISUAL_WORLD_DB_PATH=/data/visual_world.db
HOST=0.0.0.0
PORT=<platform-provided-port>
```

The V1 production target moves the same logical model to Postgres plus a dedicated faceted search service once the public corpus outgrows a single SQLite volume.

The scheduled GitHub source check probes connectors against disposable databases; the separate Pages workflow builds and publishes the public snapshot. Neither updates an optional hosted SQLite database.

## Open-source project structure

```text
connectors/          Source-specific ingestion
web/                 Public interface
schema.py            Database schema + source registry
canonicalize.py      Cross-source canonical entity builder
sync.py              Full/incremental ingestion runner
server.py            Search/detail/public API
export_static.py     Rights-aware Pages snapshot exporter
source_registry.csv  Source roadmap and rights strategy
docs/                Architecture, rights and deployment docs
.github/workflows/   CI, source health, Pages publication and container checks
tests/               Core invariants
```

## Roadmap

See [`ROADMAP.md`](ROADMAP.md). The next release target is **V1.0 public website**: 20+ maintained sources, production Postgres, dedicated faceted search, artist/style pages, automated refresh and public source-health reporting.

## License

Visual World's **software** is MIT licensed. Third-party metadata and images remain governed by their individual sources and object-level terms.
