#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 sync.py --source artworks
printf '\nArtwork sync complete. Canonical index rebuilt.\n'
read -n 1 -s -r -p "Press any key to close..."
