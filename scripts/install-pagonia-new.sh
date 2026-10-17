#!/usr/bin/env bash
# New modular Pagonia installer; the legacy monolith remains untouched.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd -P)
exec /usr/bin/python3 "$SCRIPT_DIR/pagonia-installer.py" "$@"
