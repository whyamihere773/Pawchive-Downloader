#!/usr/bin/env bash
# Pawchive Downloader — One-click compilation wrapper for Linux / CachyOS
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================================="
echo "  🚀 Pawchive Downloader — Linux / CachyOS Build Launcher"
echo "=================================================================="

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found. Please install Python 3.9+ first."
    exit 1
fi

# Detect CachyOS / Arch and prompt package installation if packages are missing
if [ -f /etc/os-release ] && grep -qiE "cachyos|arch" /etc/os-release; then
    echo "⚡ Detected CachyOS / Arch Linux system."
elif [ -f /etc/os-release ] && grep -qiE "ubuntu|debian" /etc/os-release; then
    echo "⚡ Detected Ubuntu / Debian / WSL system."
fi

# Execute python build script
python3 build_linux.py "$@"

