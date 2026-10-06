#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 sync.py --source all
printf '\nSync complete. Canonical index rebuilt.\n'
read -n 1 -s -r -p "Press any key to close..."
