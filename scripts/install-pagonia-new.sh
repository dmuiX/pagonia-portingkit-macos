#!/usr/bin/env bash
# Modular Pagonia installer; never invokes the legacy monolith.
set -euo pipefail
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd -P)
PYTHON=$(command -v python3) || {
  echo "ERROR: Python 3.10 or newer is required." >&2
  exit 1
}
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "ERROR: Python 3.10 or newer is required." >&2
  exit 1
}
exec "$PYTHON" "$SCRIPT_DIR/pagonia-installer.py" "$@"
