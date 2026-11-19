#!/usr/bin/env sh
# Pawchive Downloader — Remove Linux Desktop Integration
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
APPS_DIR="${XDG_DATA_HOME}/applications"
DESKTOP_FILE="${APPS_DIR}/pawchive.desktop"
ICON_FILE_512="${XDG_DATA_HOME}/icons/hicolor/512x512/apps/pawchive.png"
ICON_FILE_256="${XDG_DATA_HOME}/icons/hicolor/256x256/apps/pawchive.png"
LINK_PATH="${HOME}/.local/bin/pawchive"

rm -f "${DESKTOP_FILE}" "${ICON_FILE_512}" "${ICON_FILE_256}"

if [ -L "${LINK_PATH}" ]; then
    TARGET="$(readlink "${LINK_PATH}" 2>/dev/null || true)"
    case "${TARGET}" in
        "${SCRIPT_DIR}/"*) rm -f "${LINK_PATH}" ;;
    esac
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APPS_DIR}" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${XDG_DATA_HOME}/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Pawchive Downloader desktop integration removed."
echo "Your extracted folder and saved settings/archives were not deleted."
