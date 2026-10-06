#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 sync.py --source resources
printf '\nResource sync complete.\n'
read -n 1 -s -r -p "Press any key to close..."
