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
