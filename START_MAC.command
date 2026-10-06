#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 schema.py
python3 seed_demo.py
python3 canonicalize.py
( sleep 1; open "http://127.0.0.1:8787" ) &
python3 server.py
