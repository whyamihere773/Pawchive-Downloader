"""
Build Script for Pawchive Downloader
Compiles the application into a clean Windows directory distribution with '_internal' layout.
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


def post_build_setup(output_dir: str):
    """Sets up runtime folders and config templates next to the executable."""
    print("\n📁 Configuring clean runtime environment...")

    # Create config and dependencies directories next to executable
    config_dir = os.path.join(output_dir, "config")
    deps_dir = os.path.join(output_dir, "dependencies")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(deps_dir, exist_ok=True)

    # Copy example settings into config/
    src_example = os.path.join("config", "settings.example.json")
    dst_example = os.path.join(config_dir, "settings.example.json")
    if os.path.exists(src_example):
        shutil.copy2(src_example, dst_example)
        print(f"   Copied {src_example} -> {dst_example}")

    print("✅ Runtime environment configured successfully.\n")


def main():
    parser = argparse.ArgumentParser(description="Build Pawchive Downloader with clean '_internal' layout.")
    parser.add_argument("--clean", action="store_true", default=True, help="Clean build directories before compiling (default: True).")
    parser.add_argument("--noupdate-check", action="store_true", help="Skip dependency check.")

    args = parser.parse_args()

    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

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
    post_build_setup(out_folder)

    exe_path = os.path.join(out_folder, "Pawchive Downloader.exe")

    print("=" * 65)
    print("  🎉 Build Completed Successfully!")
    print(f"  📁 Output Folder: {out_folder}")
    print(f"  🚀 Executable:    {exe_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()
