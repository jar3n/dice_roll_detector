#!/usr/bin/env bash
#
# pip_install_ssd_tmp.sh
#
# Installs Python requirements using a temp directory on the SSD-backed
# root filesystem instead of the small RAM-backed /tmp tmpfs. This avoids
# "no space left on device" errors during pip install on the Pi.
#
# Usage:
#   ./pip_install_ssd_tmp.sh [path-to-requirements.txt]
#
# If no path is given, defaults to requirements.txt in the current directory.

set -euo pipefail

REQUIREMENTS_FILE="${1:-requirements.txt}"

if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
    echo "Error: requirements file not found: $REQUIREMENTS_FILE" >&2
    exit 1
fi

# Create a temp dir on the SSD-backed root filesystem (not /tmp, which is tmpfs)
SSD_TMPDIR="$HOME/pip-tmp"
mkdir -p "$SSD_TMPDIR"

echo "Using TMPDIR=$SSD_TMPDIR for this install (avoids RAM-backed /tmp)"
echo "Installing from: $REQUIREMENTS_FILE"

# Run pip with TMPDIR redirected just for this command (doesn't persist
# to your shell/session after the script exits)
TMPDIR="$SSD_TMPDIR" pip install --no-cache-dir -r "$REQUIREMENTS_FILE"

echo "Done. Cleaning up temp build directory..."
rm -rf "${SSD_TMPDIR:?}"/*

echo "Install complete."