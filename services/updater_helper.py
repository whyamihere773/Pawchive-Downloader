"""
Standalone Updater Helper Script.
Runs as a detached process when updating Pawchive Downloader.
Waits for main app PID to exit, safely copies new files while protecting
user configuration and downloads, updates version.json, and restarts the app.
"""

import os
import sys
import time
import json
import shutil
import argparse
import subprocess

# Directories that must NEVER be overwritten or deleted during update
PROTECTED_DIRS = {
    "config",
    "downloads",
    ".git",
    "temp",
    "logs",
    "venv",
    ".venv",
    "__pycache__"
}

PROTECTED_FILES = {
    "watchlist.json",
    "settings.json",
    "Known.txt",
    "cookies.txt",
    "link_vault.json",
    "link_vault.json.bak",
    "storage_pools.json",
    "schedules.json"
}


def wait_for_pid_exit(pid: int, max_wait: int = 12) -> bool:
    """Wait for parent application PID to exit completely."""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            # Check if process exists on Windows
            if sys.platform == "win32":
                import ctypes
                SYNCHRONIZE = 0x00100000
                process = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
                if not process:
                    return True
                # Check if still running
                STILL_ACTIVE = 259
                exit_code = ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code))
                ctypes.windll.kernel32.CloseHandle(process)
                if exit_code.value != STILL_ACTIVE:
                    return True
            else:
                os.kill(pid, 0)
        except OSError:
            return True
        except Exception:
            return True
        time.sleep(0.5)
    return False


def copy_staging_files(staging_dir: str, target_dir: str):
    """Recursively copy files from staging to target, strictly preserving protected dirs and user files."""
    for root, dirs, files in os.walk(staging_dir):
        rel_root = os.path.relpath(root, staging_dir)
        first_part = rel_root.split(os.sep)[0] if rel_root != "." else ""

        if first_part.lower() in PROTECTED_DIRS:
            dirs[:] = []
            continue

        target_root = target_dir if rel_root == "." else os.path.join(target_dir, rel_root)
        os.makedirs(target_root, exist_ok=True)

        for f in files:
            if f.lower() in PROTECTED_FILES:
                continue
            src_file = os.path.join(root, f)
            dst_file = os.path.join(target_root, f)
            try:
                shutil.copy2(src_file, dst_file)
            except Exception as e:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--staging-dir", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--commit-sha", default="")
    parser.add_argument("--version-str", default="")
    parser.add_argument("--is-compiled", default="0")
    args = parser.parse_args()

    # Step 1: Wait for main app to exit
    wait_for_pid_exit(args.pid, max_wait=10)
    time.sleep(1.0)  # Grace period for Windows file unlock

    # Step 2: Copy updated files from staging to target
    if os.path.exists(args.staging_dir) and os.path.exists(args.target_dir):
        copy_staging_files(args.staging_dir, args.target_dir)

    # Step 3: Write new version metadata
    if args.commit_sha or args.version_str:
        version_data = {
            "commit": args.commit_sha,
            "short_commit": args.commit_sha[:7] if args.commit_sha else "",
            "version": args.version_str,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            with open(os.path.join(args.target_dir, "version.json"), "w", encoding="utf-8") as f:
                json.dump(version_data, f, indent=2)
        except Exception:
            pass

    # Step 4: Clean up staging folder
    try:
        temp_root = os.path.join(args.target_dir, "temp", "update")
        if os.path.exists(temp_root):
            shutil.rmtree(temp_root, ignore_errors=True)
    except Exception:
        pass

    # Step 5: Relaunch application
    try:
        is_compiled = (args.is_compiled == "1")
        if is_compiled:
            # Compiled exe name in target dir
            exe_cand = os.path.join(args.target_dir, "Pawchive.exe")
            if not os.path.exists(exe_cand):
                for f in os.listdir(args.target_dir):
                    if f.lower().endswith(".exe") and "updater" not in f.lower():
                        exe_cand = os.path.join(args.target_dir, f)
                        break
            subprocess.Popen([exe_cand], cwd=args.target_dir)
        else:
            python_exe = sys.executable
            main_script = os.path.join(args.target_dir, "main.py")
            subprocess.Popen([python_exe, main_script], cwd=args.target_dir)
    except Exception as e:
        pass


if __name__ == "__main__":
    main()
