#!/bin/sh
set -eu
command -v python3 >/dev/null 2>&1 || { echo 'Python 3.10 or newer is required. Install it using your distribution documentation.' >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { echo 'Python 3.10 or newer is required.' >&2; exit 1; }
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$TASK_ROOT/scripts/install.py" "$@"
