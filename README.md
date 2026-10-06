# Visual World / 世界艺术探索馆 · V0.6

V0.6 把前台整理为作品探索网站：画家、时期、风格与流派、内容主题四种入口，共用完整作品检索。资源目录与数据源保留为内部数据，不再作为公共导航模块。

- 画家页合并馆方标准姓名和展示姓名，提供常见中文名字与别名、生卒年及本库作品。工作室、归属等署名保持区别。
- 时期按作品创作年代筛选，支持查看结果中的创作者；不把世纪自动解释成艺术史流派。
- 芝加哥馆藏的标准作者、风格、主题和文字说明完整入库。没有标签的作品仍在完整作品库中。
- PainterPalette 用于精确姓名匹配后的生卒年和国籍补充；其流派标签不自动套到馆藏作品上。匹配有歧义时不选取传记。
- 全量索引支持中文、多个维度组合、准确结果数量、跨分片排序与分页；作品图片按当前页面加载。
- 筛选条件保存在网址中，可以分享画家或分类页面，并通过浏览器前进、后退恢复。

升级已有本地数据库：`python3 -u sync.py --source public`。只重建探索目录：`python3 exploration.py --sync-painters`。后者不重新下载馆藏作品。

中文名称和常见标签映射在 `curation.json`。PainterPalette 原始补充文件缓存在 `data/cache/`，不进入代码仓库。参见 [资料出处](docs/EXPLORATION.md)。

**Visual World** is an open visual-culture index designed to aggregate as much publicly indexable art, illustration and design material as possible across museums, open collections and resource directories.

The V0.6 code is published at [GitHub](https://github.com/Days24Sue/visual-world), and the [free public beta](https://days24sue.github.io/visual-world/) is live as a periodically refreshed, sharded GitHub Pages collection. The original Python API and Docker deployment remain available for a future dynamic host.

It is **not** a hand-picked image gallery. The public artwork library contains only works with open image URLs. The three production sources (NGA, Cleveland and Chicago) are imported without a record cap. GitHub Pages loads small search and detail shards on demand; the existing Python API can serve the same collection dynamically. Metadata-only records remain internal and never appear as artwork cards.

## Foundation retained from V0.5

- **Canonical artwork layer** — conservative cross-source deduplication while preserving every source record.
- **Provenance-first detail view** — one artwork can expose multiple museum/source records and their rights status.
- **Search filters** — source, year range, images only and public-domain only.
- **Sync history** — each ingestion run records success/error and processed count.
- **Free public beta** — GitHub Actions synchronizes complete image-capable collections and publishes a rights-aware static site to GitHub Pages.
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
python3 sync.py --source public
python3 sync.py --source resources
python3 server.py
```

Open `http://127.0.0.1:8787`.

## Full synchronization

```bash
python3 sync.py --source public
python3 sync.py --source resources
```

The three production artwork sources only:

```bash
python3 sync.py --source public
```

Resource indexes only:

```bash
python3 sync.py --source resources
```

The legacy `--source artworks` and `--source all` groups remain available for research; they also ingest metadata-only museums.

For development only, cap each source:

```bash
python3 sync.py --source public --limit 1000
```

Omit `--limit` for a true full source sync.

## Canonicalization

After synchronization `sync.py` rebuilds the canonical index automatically. It can also be run separately:

```bash
python3 canonicalize.py
```

V0.5 merges automatically only with strong evidence: a shared Wikidata QID or normalized **title + artist + year**. Ambiguous records remain separate rather than risking incorrect merges.

## Deploy

The zero-cost public site uses GitHub Pages. The `Publish free beta` workflow builds an isolated SQLite database, fully synchronizes NGA, Cleveland and Chicago, and refreshes it weekly. Cleveland and Chicago use their official bulk dumps. Only artworks with open image URLs are exported. Search indexes and details are split into 500-work shards; opening the site does not download the entire collection. The Python API is not running on Pages; the first text search loads a compressed text index, then fetches only candidate shards. Browsers without gzip decompression support fall back to scanning shards. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

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
