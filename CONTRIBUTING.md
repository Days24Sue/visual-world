# Contributing

The most valuable contribution is usually a new or improved data-source connector.

1. Open an issue describing the source, official documentation, data volume and rights model.
2. Add the source to `schema.py` / `source_registry.csv`.
3. Implement `sync(conn, limit=None)` in `connectors/` using the connector contract in `docs/CONNECTORS.md`.
4. Preserve metadata and image rights separately.
5. Verify `python sync.py --source <id> --limit 3` and `python -m unittest discover -s tests -v`.
6. Submit a pull request with the source documentation link and known limitations.

Do not add scraped sources whose terms prohibit indexing or redistribution.
