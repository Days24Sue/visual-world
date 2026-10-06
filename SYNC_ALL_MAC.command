#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 -u sync.py --source public
python3 -u sync.py --source resources
printf '\nSync complete. Canonical index rebuilt.\n'
read -n 1 -s -r -p "Press any key to close..."
