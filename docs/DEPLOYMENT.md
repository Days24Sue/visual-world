# Deployment

## Free GitHub Pages beta

The public repository uses `.github/workflows/pages.yml` to build a fresh, isolated SQLite database, synchronize up to 200 real records per source, export a rights-aware static snapshot, and deploy it to GitHub Pages. The workflow also runs weekly and can be started manually. The database and third-party image files are not committed or uploaded; only the static site and normalized metadata snapshot are published.

1. In repository Settings → Pages, select **GitHub Actions** as the build and deployment source.
2. Run **Publish free beta** from Actions, or push a change to `main`. The workflow keeps the old site live if a connector or export fails.
3. Open [the Pages site](https://days24sue.github.io/visual-world/) and verify search, source/year/public-domain/image filters, artwork details, original record links and rights text.

For a local preview using an existing synchronized database:

```bash
python export_static.py --output dist
python -m http.server 8788 --directory dist
```

`dist/` is ignored by Git. Remove it before rebuilding locally. Pages has no live Python API or persistent SQLite database: search runs in the browser against the bounded snapshot, and freshness depends on a successful weekly workflow run. Do not describe it as a full real-time corpus.

## Optional paid Render service

`render.yaml` defines a Docker web service with a persistent `/data` disk, a health check, and `VISUAL_WORLD_DB_PATH=/data/visual_world.db`. Review the paid compute plan and disk size before connecting the Blueprint to a Render account. The service starts with an empty database until the first sync completes.

1. Create a public GitHub repository and push the project code. Do not commit `data/*.db`, generated exports, or third-party image archives.
2. In Render, create a Blueprint from that repository using `render.yaml`. Confirm the disk is mounted at `/data`, then wait for `/api/health` to pass.
3. Open the running paid web service's Dashboard Shell. From `/app`, run the initial import on that same service instance:

   ```bash
   python sync.py --source artworks
   python sync.py --source resources
   ```

   `sync.py` rebuilds the canonical index after each run. If a source fails, the command exits nonzero and its `sync_runs` row records the error; retry that source after checking its health.
4. Check `/api/stats`, search with a source/year filter, open an artwork detail, and confirm its original link and rights fields before sharing the public URL.

The Render disk belongs to one running service instance. Render cron jobs, pre-deploy commands, and separate workers cannot access that disk. Schedule refreshes inside the same instance or move the database to a shared service before adding an external scheduler. The weekly GitHub Action checks source availability only; it does not update the production database. Arrange database backups before a large import.

## Other Docker hosts

Run the Dockerfile on a host that provides a persistent volume mounted at `/data` and set:

```text
VISUAL_WORLD_DB_PATH=/data/visual_world.db
HOST=0.0.0.0
PORT=<platform port>
```

The container command starts `server.py`; perform the first sync on the same persistent volume. `/api/health` checks service/database connectivity, not whether a public corpus has been loaded.

## V1 scale gate

When the public corpus outgrows a single SQLite volume, move normalized/canonical tables to Postgres, use a dedicated faceted search service, and run syncs from a separate worker. Keep image URLs on source-approved IIIF/CDN endpoints rather than mirroring protected media.
