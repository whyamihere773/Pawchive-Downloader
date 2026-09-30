"""
Assembles a complete standalone portable Linux release bundle and tarball.
"""

import os
import shutil
import tarfile
import zipfile

root = os.path.dirname(os.path.abspath(__file__))
dist = os.path.join(root, "dist")
out_dir = os.path.join(dist, "Pawchive-Downloader-Linux")
os.makedirs(out_dir, exist_ok=True)

# Copy source trees
for d in ["bridge", "core", "services", "qml", "assets", "locales"]:
    dst_d = os.path.join(out_dir, d)
    if os.path.exists(dst_d):
        shutil.rmtree(dst_d)
    shutil.copytree(
        os.path.join(root, d),
        dst_d,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyd")
    )

# Ensure runtime directories
for sub in ["config", "data", "dependencies"]:
    os.makedirs(os.path.join(out_dir, sub), exist_ok=True)

# Copy files
files_to_copy = [
    "main.py",
    "updater.py",
    "version.json",
    "requirements.txt",
    "pyproject.toml",
    "PKGBUILD",
    "pawchive.desktop",
    "install_cachyos.sh",
    "build_linux.py",
    "build_linux.sh",
    "PawchiveDownloader_linux.spec"
]
for f in files_to_copy:
    src_f = os.path.join(root, f)
    if os.path.exists(src_f):
        shutil.copy2(src_f, os.path.join(out_dir, f))

cfg_example = os.path.join(root, "config", "settings.example.json")
if os.path.exists(cfg_example):
    shutil.copy2(cfg_example, os.path.join(out_dir, "config", "settings.example.json"))

icon_img = os.path.join(root, "assets", "icon.png")
if os.path.exists(icon_img):
    shutil.copy2(icon_img, os.path.join(out_dir, "icon.png"))

# Create executable POSIX bash launcher 'pawchive'
launcher = (
    "#!/usr/bin/env bash\n"
    "# Pawchive Downloader — Standalone Linux Launcher\n"
    "set -e\n"
    'HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
    'export PYTHONPATH="$HERE:$PYTHONPATH"\n'
    'export QT_QUICK_CONTROLS_STYLE="Basic"\n'
    "\n"
    "if command -v python3 &>/dev/null; then\n"
    '    PY_BIN="python3"\n'
    "elif command -v python &>/dev/null; then\n"
    '    PY_BIN="python"\n'
    "else\n"
    '    echo "❌ Python 3.9+ is required to launch Pawchive Downloader."\n'
    "    exit 1\n"
    "fi\n"
    "\n"
    'exec "$PY_BIN" "$HERE/main.py" "$@"\n'
)

launcher_path = os.path.join(out_dir, "pawchive")
with open(launcher_path, "w", newline="\n", encoding="utf-8") as f:
    f.write(launcher)

# Create tar.gz archive
tar_path = os.path.join(dist, "Pawchive-Downloader-v1.2.1-Linux.tar.gz")
with tarfile.open(tar_path, "w:gz") as tar:
    tar.add(out_dir, arcname="Pawchive-Downloader-Linux")
print(f"Created {tar_path}")

# Create zip archive
zip_path = os.path.join(dist, "Pawchive-Downloader-v1.2.1-Linux.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for root_dir, _, files in os.walk(out_dir):
        for file in files:
            full_p = os.path.join(root_dir, file)
            rel_p = os.path.relpath(full_p, dist)
            zipf.write(full_p, rel_p)
print(f"Created {zip_path}")
print("Packaging complete.")
