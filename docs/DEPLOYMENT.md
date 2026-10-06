# Deployment

## V0.5 public beta

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
