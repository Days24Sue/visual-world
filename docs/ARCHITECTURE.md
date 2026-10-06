# Architecture

Visual World separates source ingestion, source records, canonical visual entities, search, and presentation.

```text
Museum APIs / CSV / OAI-PMH / NDJSON / curated resource indexes
                               ↓
                         source connectors
                               ↓
                     normalized source records
                               ↓
                 conservative canonicalization
                               ↓
                         search / facets
                               ↓
                         public website
```

## Why canonicalization exists

A single artwork may appear in its owning museum, Wikidata, Wikimedia Commons, and aggregators. Visual World keeps every source record but exposes one canonical artwork when there is strong evidence that records represent the same object.

V0.5 only merges automatically when records share a Wikidata QID or the normalized title + artist + year triple. Ambiguous records remain separate. Future versions can add authority IDs, accession mappings and perceptual image hashes.

## Storage

The development build uses SQLite + FTS5. The database path is configurable with `VISUAL_WORLD_DB_PATH`, which allows a deployed container to attach persistent storage. At larger public scale, the same logical schema should move to Postgres plus a dedicated faceted/vector search engine.
