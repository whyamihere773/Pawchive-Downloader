"""
Build Script for Pawchive Downloader
Compiles the application into a clean Windows directory distribution with '_internal' layout.
"""

import sys
import os
import json
import shutil
import subprocess
import argparse


def get_version() -> str:
    """Read the current version from version.json (single source of truth)."""
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.json")
    if not os.path.exists(version_file):
        print("⚠️  version.json not found — using fallback version 1.0.0")
        return "1.0.0"
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        version = data.get("version", "1.0.0")
        print(f"📋 Building version: {version}")
        return version
    except Exception as e:
        print(f"⚠️  Could not read version.json: {e} — using fallback 1.0.0")
        return "1.0.0"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def check_and_install_dependencies():
    """Ensures all runtime dependencies and PyInstaller are installed."""
    required = ["PySide6", "requests", "urllib3", "PIL", "Crypto", "gdown", "PyInstaller", "telethon", "qrcode", "mutagen"]
    missing = []

    for pkg in required:
        try:
            if pkg == "Crypto":
                import Crypto
            elif pkg == "PIL":
                import PIL
            elif pkg == "PyInstaller":
                import PyInstaller
            else:
                __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"⚠️  Missing required build packages: {', '.join(missing)}")
        print("📦 Installing required packages via pip...")
        pip_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        result = subprocess.run(pip_cmd)
        if result.returncode != 0:
            print("❌ Failed to install dependencies. Please run 'pip install -r requirements.txt' manually.")
            sys.exit(1)
        print("✅ Dependencies installed successfully.\n")


def clean_build_artifacts():
    """Removes previous build/, dist/, and cache directories."""
    print("🧹 Cleaning previous build artifacts...")
    for folder in ["build", "dist", "__pycache__"]:
        if os.path.isdir(folder):
            try:
                shutil.rmtree(folder)
                print(f"   Removed {folder}/")
            except Exception as e:
                print(f"   Warning: Could not remove {folder}: {e}")


def post_build_setup(output_dir: str, version: str):
    """Sets up runtime folders, data files, and config templates next to the executable."""
    print("\n📁 Configuring clean runtime environment...")

    # Create config, data, and dependencies directories next to executable
    config_dir = os.path.join(output_dir, "config")
    data_dir = os.path.join(output_dir, "data")
    deps_dir = os.path.join(output_dir, "dependencies")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(deps_dir, exist_ok=True)

    # Copy example settings into config/
    src_example = os.path.join("config", "settings.example.json")
    dst_example = os.path.join(config_dir, "settings.example.json")
    if os.path.exists(src_example):
        shutil.copy2(src_example, dst_example)
        print(f"   Copied {src_example} -> {dst_example}")

    # Copy master_characters.json and master_characters.bin into data/
    src_master_json = os.path.join("data", "master_characters.json")
    dst_master_json = os.path.join(data_dir, "master_characters.json")
    if os.path.exists(src_master_json):
        shutil.copy2(src_master_json, dst_master_json)
        print(f"   Copied {src_master_json} -> {dst_master_json}")

    src_master_bin = os.path.join("data", "master_characters.bin")
    dst_master_bin = os.path.join(data_dir, "master_characters.bin")
    if os.path.exists(src_master_bin):
        shutil.copy2(src_master_bin, dst_master_bin)
        print(f"   Copied {src_master_bin} -> {dst_master_bin}")

    # Stamp version.json into dist so the compiled exe can report its exact version
    src_version = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.json")
    dst_version = os.path.join(output_dir, "version.json")
    if os.path.exists(src_version):
        shutil.copy2(src_version, dst_version)
        print(f"   Stamped version.json ({version}) -> {dst_version}")
    else:
        # Write a minimal one if it doesn't exist yet
        from datetime import datetime, timezone
        minimal = {"version": version, "commit": "", "short_commit": "", "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
        with open(dst_version, "w", encoding="utf-8") as f:
            json.dump(minimal, f, indent=4)
        print(f"   Created minimal version.json ({version}) -> {dst_version}")

    print("✅ Runtime environment configured successfully.\n")


def patch_version_info(version: str):
    """Update version numbers in version_info.txt and version_info_updater.txt to match version.json."""
    import re
    parts = version.split(".")
    while len(parts) < 4:
        parts.append("0")
    try:
        ver_tuple = tuple(int(p) for p in parts[:4])
    except ValueError:
        ver_tuple = (1, 0, 0, 0)
    ver_str4 = ".".join(str(p) for p in ver_tuple)

    for info_file in ["version_info.txt", "version_info_updater.txt"]:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), info_file)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(r'filevers=\(\d+, \d+, \d+, \d+\)', f'filevers={ver_tuple}', content)
        content = re.sub(r'prodvers=\(\d+, \d+, \d+, \d+\)', f'prodvers={ver_tuple}', content)
        content = re.sub(r"'FileVersion',\s*'[^']*'",   f"'FileVersion', '{ver_str4}'", content)
        content = re.sub(r"'ProductVersion',\s*'[^']*'", f"'ProductVersion', '{version}'", content)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"   Patched {info_file} -> v{version}")


def main():
    parser = argparse.ArgumentParser(description="Build Pawchive Downloader with clean '_internal' layout.")
    parser.add_argument("--clean", action="store_true", default=True, help="Clean build directories before compiling (default: True).")
    parser.add_argument("--noupdate-check", action="store_true", help="Skip dependency check.")

    args = parser.parse_args()

    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    app_version = get_version()
    patch_version_info(app_version)

    print("=" * 65)
    print("  🚀 Pawchive Downloader — Windows Build System (_internal layout)")
    print("=" * 65)


    if not args.noupdate_check:
        check_and_install_dependencies()

    if args.clean:
        clean_build_artifacts()

    spec_file = os.path.join(project_root, "PawchiveDownloader.spec")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        spec_file
    ]

    print(f"\n🔨 Compiling with PyInstaller:\n   {' '.join(cmd)}\n")
    build_result = subprocess.run(cmd)

    if build_result.returncode != 0:
        print("\n❌ Build failed! Please check the output logs above.")
        sys.exit(build_result.returncode)

    out_folder = os.path.join(project_root, "dist", "Pawchive Downloader")

    # 2. Compile standalone onefile companion updater (console hidden)
    print("\n🔨 Compiling updater.exe (standalone onefile, console hidden)...")
    icon_file = os.path.join(project_root, "assets", "icon.ico")
    updater_work = os.path.join(project_root, "build", "updater_build")
    updater_dist = os.path.join(project_root, "build", "updater_dist")
    os.makedirs(updater_work, exist_ok=True)
    os.makedirs(updater_dist, exist_ok=True)

    version_info_updater = os.path.join(project_root, "version_info_updater.txt")
    updater_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--noupx",                          # Disable UPX: major AV/ML false-positive trigger
        "--name", "updater",
        "--workpath", updater_work,
        "--distpath", updater_dist,
    ]
    if os.path.exists(icon_file):
        updater_cmd.extend(["--icon", icon_file])
    if os.path.exists(version_info_updater):
        updater_cmd.extend(["--version-file", version_info_updater])
    updater_cmd.append(os.path.join(project_root, "updater.py"))

    updater_result = subprocess.run(updater_cmd)
    if updater_result.returncode != 0:
        print("\n❌ Build failed for updater.exe!")
        sys.exit(updater_result.returncode)

    built_updater = os.path.join(updater_dist, "updater.exe")
    dst_updater = os.path.join(out_folder, "updater.exe")
    if os.path.exists(built_updater):
        shutil.copy2(built_updater, dst_updater)
        print(f"   Embedded updater.exe -> {dst_updater}")

    # Remove temporary updater.spec
    spec_auto = os.path.join(project_root, "updater.spec")
    if os.path.exists(spec_auto):
        try:
            os.remove(spec_auto)
        except Exception:
            pass

    post_build_setup(out_folder, app_version)

    # Clean intermediate compiler files from build/ so only dist/ remains
    build_temp = os.path.join(project_root, "build")
    if os.path.isdir(build_temp):
        try:
            shutil.rmtree(build_temp)
        except Exception:
            pass

    exe_path = os.path.join(out_folder, "Pawchive Downloader.exe")

    # Create release zip archive — name includes version from version.json
    zip_name = f"Pawchive-Downloader-v{app_version}-Windows"
    zip_base = os.path.join(project_root, "dist", zip_name)
    print("\n📦 Compressing release into ZIP archive...")
    zip_path = shutil.make_archive(zip_base, "zip", root_dir=os.path.join(project_root, "dist"), base_dir="Pawchive Downloader")
    print(f"   Created {zip_path}")

    print("=" * 65)
    print("  🎉 Build Completed Successfully!")
    print(f"  📋 Version:       v{app_version}")
    print(f"  📁 Output Folder: {out_folder}")
    print(f"  🚀 Executable:    {exe_path}")
    print(f"  📦 Release ZIP:   {zip_path}")
    print("=" * 65)

    # Open output folder in Windows Explorer
    try:
        os.startfile(out_folder)
    except Exception:
        pass


if __name__ == "__main__":
    main()

