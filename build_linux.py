#!/usr/bin/env python3
"""
Pawchive Downloader — Linux / CachyOS Compilation Script
Compiles Pawchive Downloader into a native standalone ELF distribution with '_internal' layout.
Supports CachyOS, Arch Linux, Fedora, Ubuntu/Debian, and any standard Linux distribution.
"""

import os
import sys
import shutil
import subprocess
import argparse
import stat


def is_cachyos_or_arch() -> bool:
    """Detect if running on CachyOS or an Arch Linux-based system."""
    if os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                content = f.read().lower()
                return "cachyos" in content or "arch" in content or "endeavouros" in content or "manjaro" in content
        except Exception:
            pass
    return False


def get_version() -> str:
    """Read version from version.json or fallback."""
    v_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.json")
    if os.path.exists(v_file):
        try:
            import json
            with open(v_file, "r", encoding="utf-8") as f:
                return json.load(f).get("version", "1.1.7")
        except Exception:
            pass
    return "1.1.7"


def check_and_install_dependencies():
    """Verify build packages are installed, using uv or pip if missing."""
    required = {
        "PySide6": "PySide6",
        "requests": "requests",
        "urllib3": "urllib3",
        "PIL": "Pillow",
        "Crypto": "pycryptodome",
        "mutagen": "mutagen",
        "telethon": "telethon",
        "qrcode": "qrcode",
        "PyInstaller": "pyinstaller",
    }

    missing = []
    for mod, pkg in required.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"⚠️  Missing required packages: {', '.join(missing)}")
        if is_cachyos_or_arch():
            print("\n💡 [CachyOS / Arch Tip] You can install system-optimized packages directly via pacman:")
            print("   sudo pacman -S --needed python-pyside6 python-pillow python-requests python-urllib3 python-pycryptodome python-mutagen python-qrcode yt-dlp p7zip\n")

        uv_path = shutil.which("uv")
        if uv_path:
            print("⚡ Fast installing dependencies via uv...")
            cmd = [uv_path, "pip", "install", "--system", "-r", "requirements.txt"]
        else:
            print("📦 Installing dependencies via pip...")
            cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
            if sys.version_info >= (3, 11):
                cmd.append("--break-system-packages")

        res = subprocess.run(cmd)
        if res.returncode != 0 and uv_path:
            print("⚠️ uv install failed, falling back to pip...")
            fallback = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
            if sys.version_info >= (3, 11):
                fallback.append("--break-system-packages")
            res = subprocess.run(fallback)

        if res.returncode != 0:
            print("❌ Failed to install required packages. Please install them manually.")
            sys.exit(1)
        print("✅ Dependencies installed successfully.\n")


def clean_artifacts():
    """Clean previous build artifacts."""
    print("🧹 Cleaning previous Linux build artifacts...")
    for folder in ["build", "dist", "__pycache__"]:
        if os.path.isdir(folder):
            try:
                shutil.rmtree(folder)
                print(f"   Removed {folder}/")
            except Exception as e:
                print(f"   Warning: Could not remove {folder}: {e}")


def post_build_setup(output_dir: str):
    """Set up runtime folders, desktop entry, and executable permissions."""
    print("\n📁 Configuring clean runtime environment...")

    config_dir = os.path.join(output_dir, "config")
    data_dir = os.path.join(output_dir, "data")
    deps_dir = os.path.join(output_dir, "dependencies")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(deps_dir, exist_ok=True)

    src_example = os.path.join("config", "settings.example.json")
    dst_example = os.path.join(config_dir, "settings.example.json")
    if os.path.exists(src_example) and not os.path.exists(dst_example):
        shutil.copy2(src_example, dst_example)
        print("   Copied config/settings.example.json")

    # Copy desktop file and icon
    for f in ["pawchive.desktop", "assets/icon.png"]:
        if os.path.exists(f):
            dest = os.path.join(output_dir, os.path.basename(f))
            shutil.copy2(f, dest)
            print(f"   Copied {f} -> {dest}")

    # Ensure executable permissions on pawchive binary
    main_bin = os.path.join(output_dir, "pawchive")
    if os.path.exists(main_bin):
        st = os.stat(main_bin)
        os.chmod(main_bin, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print("   Set executable bit (chmod +x) on 'pawchive'")


def main():
    parser = argparse.ArgumentParser(description="Build Pawchive Downloader for Linux / CachyOS.")
    parser.add_argument("--clean", action="store_true", default=True, help="Clean build directories before compiling.")
    parser.add_argument("--noupdate-check", action="store_true", help="Skip dependency check.")

    args = parser.parse_args()

    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    distro_label = "CachyOS / Arch Linux" if is_cachyos_or_arch() else "Linux"
    version = get_version()

    print("=" * 65)
    print(f"  🚀 Pawchive Downloader v{version} — {distro_label} Build System")
    print("=" * 65)

    if not args.noupdate_check:
        check_and_install_dependencies()

    if args.clean:
        clean_artifacts()

    spec_file = os.path.join(project_root, "PawchiveDownloader_linux.spec")
    if not os.path.exists(spec_file):
        print(f"❌ Spec file not found: {spec_file}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        spec_file
    ]

    print(f"\n🔨 Compiling with PyInstaller:\n   {' '.join(cmd)}\n")
    build_result = subprocess.run(cmd)

    if build_result.returncode != 0:
        print("\n❌ Build failed! Please inspect the logs above.")
        sys.exit(build_result.returncode)

    out_folder = os.path.join(project_root, "dist", "Pawchive Downloader")
    post_build_setup(out_folder)

    print("\n" + "=" * 65)
    print("  🎉 Build Completed Successfully!")
    print("=" * 65)
    print(f"\nExecutable distribution directory:\n   {out_folder}")
    print("\nTo test and run:")
    print(f"   cd \"{out_folder}\" && ./pawchive\n")


if __name__ == "__main__":
    main()
