#!/bin/bash
set -euo pipefail
cd "/Users/raymundozialcita/techmeme-signals"

# launchd fires these jobs right after a pmset-scheduled wake. With FileVault on,
# the encrypted volume can still be settling when that happens, and reading the
# venv's site files then raises "OSError: [Errno 11] Resource deadlock avoided"
# before the pipeline even starts. Poll until the venv is actually usable instead
# of trusting a fixed wake-to-run buffer.
for i in $(seq 1 20); do
    if .venv/bin/python3 -c "pass" 2>/dev/null; then
        break
    fi
    sleep 15
done

exec .venv/bin/python3 -c "$1"
