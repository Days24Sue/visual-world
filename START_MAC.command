#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 schema.py
if ! python3 - <<'PY'
from schema import connect
conn = connect()
has_images = conn.execute("SELECT 1 FROM canonical_artworks WHERE coalesce(nullif(thumbnail_url,''),nullif(image_url,'')) IS NOT NULL LIMIT 1").fetchone()
conn.close()
raise SystemExit(0 if has_images else 1)
PY
then
    python3 -u sync.py --source public
    python3 -u sync.py --source resources
fi
( sleep 1; open "http://127.0.0.1:8787" ) &
python3 server.py
