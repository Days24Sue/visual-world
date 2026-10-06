#!/usr/bin/env sh
set -eu
python sync.py --source "${1:-all}"
python canonicalize.py
