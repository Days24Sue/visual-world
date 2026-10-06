# V0.5 Public Beta release checklist

## Engineering — complete in this package
- [x] normalized multi-source artwork/resource schema
- [x] canonical artwork entity layer
- [x] provenance detail endpoint/UI
- [x] rights-aware fields and public-domain filter
- [x] year/source/image filters
- [x] source sync-run logging
- [x] automated tests
- [x] GitHub Actions CI and connector smoke checks
- [x] Docker deployment support
- [x] Render Blueprint with persistent disk and health check
- [x] open-source docs / license / contributing guide

## Account-level publication
- [x] create a public GitHub repository named `visual-world`
- [x] push this project to `main`
- [x] set `web/config.js` GitHub URL to the real repository URL
- [ ] connect a public container host with persistent storage
- [ ] set `VISUAL_WORLD_DB_PATH` to the mounted persistent volume
- [ ] run initial production sync
- [ ] choose a same-instance refresh schedule or move to shared storage before scheduling production sync
- [ ] arrange backups for the production database
- [ ] add final public domain name if desired

## V1 scale gate
Move from SQLite to Postgres + dedicated search before the public corpus or concurrent usage makes single-node SQLite a bottleneck. The logical schema and connector contract are intentionally kept portable for that migration.
