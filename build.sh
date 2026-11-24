#!/bin/sh
# Build dist/speeddisk (Linux or macOS). Requires Python 3 with venv.
set -e
V="${VENV:-$HOME/.venv-speeddisk}"
[ -x "$V/bin/python" ] || python3 -m venv "$V"
"$V/bin/pip" install -q pyinstaller
"$V/bin/pyinstaller" -F -n speeddisk --distpath dist --workpath /tmp/sd-build --specpath /tmp/sd-build speeddisk.py
