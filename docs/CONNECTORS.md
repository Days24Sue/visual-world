# Connector contract

Every artwork connector must implement `sync(conn, limit=None)` and write normalized records through `connectors.common.upsert`.

Required identity fields:

- `source_id`
- `source_object_id`

Strongly recommended fields:

- title / artist / date / year
- classification / medium / culture / country
- object URL
- image and thumbnail URL when permitted
- accession number / Wikidata QID / authority IDs when available
- metadata license and image license separately
- public-domain status only when explicitly supported

A connector may be full-sync, incremental, OAI-PMH, bulk-file or API based. It must not silently invent rights information.

## Public production sources

The Pages workflow fully imports NGA, Cleveland and Chicago. NGA joins its objects CSV to the published open image CSV. Cleveland streams its official full JSON dump for full syncs. Bounded API checks advance by the actual returned row count, so a short page does not cause premature completion. TIFF masters are replaced by print/web JPEGs in the public UI. Chicago streams the official `artic-api-data.tar.bz2` dump for full syncs; bounded smoke checks still use the API. Metadata-only and restricted-image artworks stay in storage but are excluded from the public library.
