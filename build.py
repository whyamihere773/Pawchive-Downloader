"""
Build Script for Pawchive Downloader
Compiles the application into a standalone Windows directory distribution with console hidden.
"""

import sys
import os
import shutil
import subprocess
import argparse


def check_and_install_dependencies():
    """Ensures all runtime dependencies and PyInstaller are installed."""
    required = ["PySide6", "requests", "urllib3", "PIL", "Crypto", "gdown", "PyInstaller"]
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


def post_build_setup(dist_dir: str):
    """Sets up runtime folders and config templates next to the executable."""
    print("\n📁 Preparing runtime environment...")
    
    target_root = os.path.join(dist_dir, "PawchiveDownloader")
    os.makedirs(target_root, exist_ok=True)

    # Create config and dependencies directories next to executable
    config_dir = os.path.join(target_root, "config")
    deps_dir = os.path.join(target_root, "dependencies")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(deps_dir, exist_ok=True)

    # Copy example settings
    src_example = os.path.join("config", "settings.example.json")
    dst_example = os.path.join(config_dir, "settings.example.json")
    if os.path.exists(src_example):
        shutil.copy2(src_example, dst_example)
        print(f"   Copied {src_example} -> {dst_example}")

    print("✅ Runtime environment configured.\n")


def main():
    parser = argparse.ArgumentParser(description="Build Pawchive Downloader as a Windows directory distribution.")
    parser.add_argument("--clean", action="store_true", default=True, help="Clean build directories before compiling (default: True).")
    parser.add_argument("--noupdate-check", action="store_true", help="Skip dependency check.")

    args = parser.parse_args()

    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    print("=" * 65)
    print("  🚀 Pawchive Downloader — Windows Build System (One Directory)")
    print("=" * 65)

    if not args.noupdate_check:
        check_and_install_dependencies()

    if args.clean:
        clean_build_artifacts()

    spec_file = os.path.join(project_root, "PawchiveDownloader.spec")
    
    # Standard one-directory windowed build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        spec_file
    ]

    print(f"\n🔨 Executing PyInstaller (One Directory, Console Hidden):\n   {' '.join(cmd)}\n")
    build_result = subprocess.run(cmd)

    if build_result.returncode != 0:
        print("\n❌ Build failed! Please check the output logs above.")
        sys.exit(build_result.returncode)

    dist_dir = os.path.join(project_root, "dist")
    post_build_setup(dist_dir)

    out_folder = os.path.join(dist_dir, "PawchiveDownloader")
    exe_path = os.path.join(out_folder, "PawchiveDownloader.exe")

    print("=" * 65)
    print("  🎉 Build Completed Successfully!")
    print(f"  📁 Output Directory: {out_folder}")
    print(f"  🚀 Executable:       {exe_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()
