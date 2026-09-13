"""
Pawchive Downloader - Standalone Companion Updater.
Packaged as a lightweight onefile GUI application (console hidden).
Handles downloading, staging, zero-lock file synchronization, and application relaunch.
"""

import os
import sys
import time
import json
import shutil
import zipfile
import argparse
import subprocess
import threading
import urllib.request
from typing import Optional

# GUI: Tkinter (standard library, zero external DLL dependency)
import tkinter as tk
from tkinter import ttk

# Files and folders that must NEVER be touched during an update
PROTECTED_DIRS = {"config", "downloads", "temp", "logs", "venv", ".venv", "__pycache__", ".git"}
PROTECTED_FILES = {
    "settings.json", "watchlist.json", "known.txt", "cookies.txt",
    "link_vault.json", "link_vault.json.bak", "storage_pools.json", "schedules.json"
}

# Extra wait time after PID exits before touching exe files (Windows handle-release delay)
_EXE_RELEASE_WAIT = 1.5


def is_pid_running(pid: int) -> bool:
    """Check if process with given PID is still active on Windows."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if not handle:
                return False
            STILL_ACTIVE = 259
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return code.value == STILL_ACTIVE
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class UpdaterApp:
    def __init__(self, root: tk.Tk, target_dir: str, pid: int, download_url: str, version: str):
        self.root = root
        self.target_dir = os.path.abspath(target_dir)
        self.pid = pid
        self.download_url = download_url
        self.version = version or "Latest"
        self._cancel_requested = False

        self._setup_window()
        self._setup_styles()
        self._create_widgets()

        # Start background update worker
        threading.Thread(target=self._run_update_pipeline, daemon=True).start()

    def _setup_window(self):
        self.root.title("Pawchive Downloader Updater")
        self.root.geometry("480x280")
        self.root.resizable(False, False)
        self.root.configure(bg="#121214")

        # Center on screen
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

        # Set application icon if exists
        icon_path = os.path.join(self.target_dir, "assets", "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

    def _setup_styles(self):
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        # Custom purple progressbar
        self.style.configure(
            "Purple.Horizontal.TProgressbar",
            troughcolor="#1e1e24",
            background="#a855f7",
            darkcolor="#9333ea",
            lightcolor="#c084fc",
            bordercolor="#1e1e24",
            thickness=10
        )

    def _create_widgets(self):
        # Outer Card
        card = tk.Frame(self.root, bg="#18181b", bd=1, relief="flat", highlightbackground="#27272a", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Header with Logo & Title
        header_frame = tk.Frame(card, bg="#18181b")
        header_frame.pack(fill="x", padx=20, pady=(18, 10))

        title_label = tk.Label(
            header_frame,
            text="Pawchive Downloader",
            font=("Segoe UI", 14, "bold"),
            fg="#f4f4f5",
            bg="#18181b"
        )
        title_label.pack(side="left")

        self.ver_badge = tk.Label(
            header_frame,
            text=f"Updating to {self.version}",
            font=("Segoe UI", 9, "bold"),
            fg="#a855f7",
            bg="#27272a",
            padx=8,
            pady=2
        )
        self.ver_badge.pack(side="right")

        # Status text
        self.status_label = tk.Label(
            card,
            text="Preparing update...",
            font=("Segoe UI", 10),
            fg="#e4e4e7",
            bg="#18181b",
            anchor="w"
        )
        self.status_label.pack(fill="x", padx=20, pady=(14, 6))

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            card,
            variable=self.progress_var,
            maximum=100.0,
            style="Purple.Horizontal.TProgressbar"
        )
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 6))

        # Sub-status / Speed details
        self.detail_label = tk.Label(
            card,
            text="Please wait while the update is applied...",
            font=("Segoe UI", 8),
            fg="#71717a",
            bg="#18181b",
            anchor="w"
        )
        self.detail_label.pack(fill="x", padx=20, pady=(0, 16))

        # Footer button area
        btn_frame = tk.Frame(card, bg="#18181b")
        btn_frame.pack(fill="x", padx=20, pady=(0, 12))

        self.cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            font=("Segoe UI", 9),
            fg="#a1a1aa",
            bg="#27272a",
            activebackground="#3f3f46",
            activeforeground="#f4f4f5",
            bd=0,
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._on_cancel
        )
        self.cancel_btn.pack(side="right")

    def _set_status(self, status: str, detail: str = "", progress: Optional[float] = None):
        def _update():
            self.status_label.config(text=status)
            if detail is not None:
                self.detail_label.config(text=detail)
            if progress is not None:
                self.progress_var.set(progress)
        self.root.after(0, _update)

    def _on_cancel(self):
        self._cancel_requested = True
        self._set_status("Cancelling update...", "Cleaning up temporary files...")
        self.root.after(1000, self.root.destroy)

    def _clean_stale_old_files(self):
        """Remove any leftover *.old files from a previous update attempt."""
        for root_d, _dirs, files in os.walk(self.target_dir):
            for f in files:
                if f.endswith(".old"):
                    try:
                        os.remove(os.path.join(root_d, f))
                    except Exception:
                        pass

    def _safe_delete(self, path: str):
        """
        Delete a file as safely as possible without admin.
        Strategy: rename to .old first (works even on locked/AV-scanned files
        because rename only touches the directory entry), then delete the .old.
        If .old deletion fails it stays harmlessly until the next update.
        """
        if not os.path.exists(path):
            return
        old_path = path + ".old"
        # Remove any stale .old before renaming
        try:
            if os.path.exists(old_path):
                os.remove(old_path)
        except Exception:
            pass
        try:
            os.rename(path, old_path)   # Works even on memory-mapped/locked files!
        except Exception:
            return  # Cannot even rename — leave the file, copy will try to overwrite
        try:
            os.remove(old_path)
        except Exception:
            pass  # Locked by AV or still mapped — harmless, cleaned next update

    def _safe_copy(self, src: str, dst: str) -> bool:
        """
        Copy src to dst, handling the case where dst is still locked.
        Renames dst -> dst.old first (rename is allowed on locked files),
        then copies src to the real dst name.
        Returns True on success, False if the file could not be written.
        """
        if os.path.exists(dst):
            old_path = dst + ".old"
            try:
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception:
                pass
            try:
                os.rename(dst, old_path)  # Side-step the lock
            except Exception:
                pass  # If rename also fails, try a direct overwrite below
        try:
            shutil.copy2(src, dst)
        except Exception:
            return False  # Could not write — file is truly stuck
        # Best-effort cleanup of the renamed old file
        old_path = dst + ".old"
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass  # Stays as .old, cleaned on next update — no harm
        return True

    def _relaunch_as_admin(self):
        """
        Re-launch the updater with administrator privileges using Windows UAC.
        Uses ShellExecuteW with the 'runas' verb so Windows shows the native
        UAC prompt — we never store or request credentials ourselves.
        """
        import ctypes
        # Build the exe path: we are already a temp copy in %TEMP%
        if getattr(sys, "frozen", False):
            exe = os.path.abspath(sys.executable)
        else:
            exe = sys.executable

        params = (
            f'--target-dir "{self.target_dir}" '
            f'--pid 0 '
            f'--download-url "{self.download_url}" '
            f'--version "{self.version}" '
            f'--temp-runner'
        )
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None,       # hwnd
                "runas",    # verb  — triggers UAC elevation
                exe,
                params,
                None,       # working dir
                1           # SW_SHOWNORMAL
            )
        except Exception as e:
            self._set_status("Could not elevate", f"Error: {e}", progress=0.0)
            return
        # Close this instance — the elevated copy takes over
        self.root.after(300, self.root.destroy)

    def _show_lock_error_dialog(self, failed_files: list):
        """
        Show a recovery dialog when some files could not be installed due to
        file locks. Offers two options:
          1. Run as Administrator — relaunches via UAC (Windows handles the prompt)
          2. Try Later           — closes the updater; user can run updater.exe
                                   from the install folder manually
        """
        def _build():
            dlg = tk.Toplevel(self.root)
            dlg.title("Update could not finish")
            dlg.geometry("460x290")
            dlg.resizable(False, False)
            dlg.configure(bg="#121214")
            dlg.grab_set()  # Modal
            dlg.transient(self.root)

            # Center on parent
            dlg.update_idletasks()
            px = self.root.winfo_x() + (self.root.winfo_width()  - 460) // 2
            py = self.root.winfo_y() + (self.root.winfo_height() - 290) // 2
            dlg.geometry(f"+{px}+{py}")

            card = tk.Frame(dlg, bg="#18181b", highlightbackground="#27272a", highlightthickness=1)
            card.pack(fill="both", expand=True, padx=14, pady=14)

            tk.Label(
                card,
                text="The app didn't fully close in time",
                font=("Segoe UI", 11, "bold"),
                fg="#f4f4f5", bg="#18181b"
            ).pack(pady=(16, 8))

            explanation = (
                "Windows is still holding on to some of the old app files — "
                "this usually happens when your antivirus is scanning them or "
                "Windows is slow releasing them after the app closed.\n\n"
                "The update has been downloaded and is ready to install. "
                "You just need to choose how to finish it:"
            )
            tk.Label(
                card,
                text=explanation,
                font=("Segoe UI", 9),
                fg="#a1a1aa", bg="#18181b",
                justify="left", wraplength=410, anchor="w"
            ).pack(padx=16, pady=(0, 14), fill="x")

            btn_row = tk.Frame(card, bg="#18181b")
            btn_row.pack(padx=16, fill="x")

            def on_admin():
                dlg.destroy()
                threading.Thread(target=self._relaunch_as_admin, daemon=True).start()

            def on_later():
                dlg.destroy()
                self._set_status(
                    "Update ready — finish it when you're ready",
                    "Open the install folder and run 'updater.exe' to apply the update.",
                    progress=0.0
                )
                self.root.after(0, lambda: self.cancel_btn.config(
                    text="Close", state="normal", command=self.root.destroy
                ))

            # Primary action
            admin_btn = tk.Button(
                btn_row,
                text="Retry as Administrator  (Recommended)",
                font=("Segoe UI", 9, "bold"),
                fg="#ffffff", bg="#a855f7",
                activebackground="#9333ea", activeforeground="#ffffff",
                bd=0, padx=16, pady=7, cursor="hand2",
                command=on_admin, anchor="w"
            )
            admin_btn.pack(fill="x", pady=(0, 6))

            # Hint under primary button
            tk.Label(
                btn_row,
                text="Windows will ask if you want to allow the update — click Yes to continue.",
                font=("Segoe UI", 8),
                fg="#52525b", bg="#18181b",
                anchor="w"
            ).pack(fill="x", pady=(0, 10))

            # Secondary action
            later_btn = tk.Button(
                btn_row,
                text="I'll do it later",
                font=("Segoe UI", 9),
                fg="#a1a1aa", bg="#27272a",
                activebackground="#3f3f46", activeforeground="#f4f4f5",
                bd=0, padx=16, pady=6, cursor="hand2",
                command=on_later, anchor="w"
            )
            later_btn.pack(fill="x")

            # Hint under secondary button
            tk.Label(
                btn_row,
                text="Run 'updater.exe' from the app folder whenever you're ready.",
                font=("Segoe UI", 8),
                fg="#52525b", bg="#18181b",
                anchor="w"
            ).pack(fill="x", pady=(2, 0))

        self.root.after(0, _build)

    def _delete_non_protected(self):
        """Remove all non-protected items from target_dir using safe rename strategy."""
        for entry in os.listdir(self.target_dir):
            entry_lower = entry.lower()
            full_path = os.path.join(self.target_dir, entry)

            if entry_lower in PROTECTED_DIRS:
                continue
            if entry_lower in PROTECTED_FILES:
                continue
            if entry_lower == "updater.exe":
                # Running from %TEMP% already — will be overwritten by copy step
                continue
            # Skip .old debris (already renamed from a previous pass)
            if entry.endswith(".old"):
                continue

            if os.path.isdir(full_path):
                shutil.rmtree(full_path, ignore_errors=True)
            else:
                self._safe_delete(full_path)

    def _run_update_pipeline(self):
        try:
            # 1. Wait for Pawchive Downloader to completely terminate
            if self.pid > 0:
                self._set_status("Closing Pawchive Downloader...", "Waiting for process to unlock files...")
                start_wait = time.time()
                while is_pid_running(self.pid):
                    if self._cancel_requested:
                        return
                    if time.time() - start_wait > 15:
                        break
                    time.sleep(0.3)

            # Extra buffer for Windows to fully release file handles (no admin needed)
            time.sleep(_EXE_RELEASE_WAIT)

            # 2. Prepare directories in %TEMP%
            temp_base = os.environ.get("TEMP", os.path.expanduser("~"))
            updater_work_dir = os.path.join(temp_base, f"pawchive_update_{int(time.time())}")
            zip_dest = os.path.join(updater_work_dir, "update.zip")
            staging_dir = os.path.join(updater_work_dir, "staging")
            os.makedirs(staging_dir, exist_ok=True)

            # 3. Download Release ZIP
            self._set_status("Connecting to GitHub...", "Resolving release package...", progress=5.0)
            req = urllib.request.Request(self.download_url, headers={"User-Agent": "Pawchive-Updater/1.0"})

            with urllib.request.urlopen(req, timeout=30) as resp:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                start_t = time.time()
                last_ui_t = start_t

                with open(zip_dest, "wb") as out_f:
                    while True:
                        if self._cancel_requested:
                            shutil.rmtree(updater_work_dir, ignore_errors=True)
                            return
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)

                        now = time.time()
                        if now - last_ui_t >= 0.25 or downloaded == total_size:
                            last_ui_t = now
                            pct = (downloaded / total_size * 100) if total_size > 0 else 50.0
                            elapsed = max(0.001, now - start_t)
                            speed_mb = (downloaded / elapsed) / (1024 * 1024)
                            mb_done = downloaded / (1024 * 1024)
                            mb_total = total_size / (1024 * 1024)

                            rem_sec = int((total_size - downloaded) / max(1, downloaded / elapsed)) if total_size > 0 else 0
                            eta_str = f"ETA: {rem_sec}s" if rem_sec < 120 else f"ETA: {rem_sec // 60}m {rem_sec % 60}s"

                            status = f"Downloading update ({int(pct)}%)..."
                            detail = f"{mb_done:.1f} MB / {mb_total:.1f} MB • {speed_mb:.1f} MB/s • {eta_str}"
                            self._set_status(status, detail, progress=5.0 + (pct * 0.75))

            # 4. Extract Package
            self.root.after(0, lambda: self.cancel_btn.config(state="disabled"))
            self._set_status("Extracting update package...", "Verifying files...", progress=82.0)

            with zipfile.ZipFile(zip_dest, "r") as zf:
                zf.extractall(staging_dir)

            # Locate root directory inside zip if nested (zip has a single root folder)
            stage_root = staging_dir
            entries = [os.path.join(staging_dir, e) for e in os.listdir(staging_dir)]
            if len(entries) == 1 and os.path.isdir(entries[0]):
                stage_root = entries[0]

            # 5. Clean up .old debris from any previous failed update
            self._set_status("Preparing installation...", "Cleaning up previous update debris...", progress=84.0)
            self._clean_stale_old_files()

            # 6. Delete all non-protected items from target dir (clean slate)
            self._set_status("Clearing old version...", "Removing outdated application files...", progress=87.0)
            self._delete_non_protected()

            # 7. Copy fresh files into target directory
            self._set_status("Installing update...", "Copying new application files...", progress=91.0)

            copied_count = 0
            failed_files: list = []
            for root_d, dirs, files in os.walk(stage_root):
                rel = os.path.relpath(root_d, stage_root)
                first = rel.split(os.sep)[0] if rel != "." else ""

                # Skip protected dirs from the new zip too (shouldn't exist, but be safe)
                if first.lower() in PROTECTED_DIRS:
                    dirs[:] = []
                    continue

                dest_folder = self.target_dir if rel == "." else os.path.join(self.target_dir, rel)
                os.makedirs(dest_folder, exist_ok=True)

                for file_name in files:
                    if file_name.lower() in PROTECTED_FILES:
                        continue
                    s_file = os.path.join(root_d, file_name)
                    d_file = os.path.join(dest_folder, file_name)
                    if self._safe_copy(s_file, d_file):
                        copied_count += 1
                    else:
                        failed_files.append(d_file)

            # If any files failed to copy, offer admin elevation or try-later
            if failed_files:
                self._set_status(
                    "Some files could not be replaced",
                    f"{len(failed_files)} file(s) are still locked. Choose how to proceed.",
                    progress=92.0
                )
                self._show_lock_error_dialog(failed_files)
                shutil.rmtree(updater_work_dir, ignore_errors=True)
                return  # Do not relaunch until user decides

            self._set_status("Finalizing update...", f"Installed {copied_count} files successfully.", progress=98.0)
            time.sleep(0.5)

            # 7. Clean up temporary work directory
            shutil.rmtree(updater_work_dir, ignore_errors=True)

            # 7. Relaunch Application
            self._set_status("Update complete!", "Relaunching Pawchive Downloader...", progress=100.0)
            time.sleep(0.8)

            exe_path = os.path.join(self.target_dir, "Pawchive Downloader.exe")
            if not os.path.exists(exe_path):
                # Fallback search
                for f in os.listdir(self.target_dir):
                    if f.lower().endswith(".exe") and "updater" not in f.lower():
                        exe_path = os.path.join(self.target_dir, f)
                        break

            if os.path.exists(exe_path):
                subprocess.Popen([exe_path], cwd=self.target_dir)

            self.root.after(500, self.root.destroy)

        except Exception as err:
            self._set_status("Update Failed", f"Error: {err}", progress=0.0)
            self.root.after(0, lambda: self.cancel_btn.config(text="Close", state="normal", command=self.root.destroy))


def main():
    parser = argparse.ArgumentParser(description="Pawchive Downloader Standalone Companion Updater")
    parser.add_argument("--target-dir", default="", help="Installation root of Pawchive Downloader")
    parser.add_argument("--pid", type=int, default=0, help="PID of the running main app to wait for")
    parser.add_argument("--download-url", default="", help="Direct download URL for the update zip")
    parser.add_argument("--version", default="", help="Target version string to display")
    parser.add_argument("--temp-runner", action="store_true", help="Internal flag: running from temp location")

    args = parser.parse_args()

    target_dir = args.target_dir
    if not target_dir:
        if getattr(sys, "frozen", False):
            target_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            target_dir = os.path.dirname(os.path.abspath(__file__))

    download_url = args.download_url
    version = args.version
    if not download_url:
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/whyamihere773/Pawchive-Downloader/releases/latest",
                headers={"User-Agent": "Pawchive-Updater/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not version:
                    version = data.get("tag_name", "")
                for asset in data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if name.endswith(".zip"):
                        download_url = asset.get("browser_download_url", "")
                        break
        except Exception:
            pass

    if not download_url:
        print("❌ Error: No download package URL provided and could not query GitHub releases.")
        sys.exit(1)

    # Self-relocation:
    # If running from inside target_dir as a compiled exe, copy self to %TEMP%
    # so target_dir/updater.exe itself is not locked and can be cleanly updated!
    if getattr(sys, "frozen", False) and not args.temp_runner:
        my_exe = os.path.abspath(sys.executable)
        temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
        temp_updater = os.path.join(temp_dir, f"pawchive_updater_run_{int(time.time())}.exe")
        try:
            shutil.copy2(my_exe, temp_updater)
            cmd = [
                temp_updater,
                "--target-dir", target_dir,
                "--pid", str(args.pid),
                "--download-url", download_url,
                "--version", version,
                "--temp-runner"
            ]
            subprocess.Popen(cmd)
            sys.exit(0)
        except Exception:
            pass  # Fall back to running in-place

    root = tk.Tk()
    app = UpdaterApp(
        root=root,
        target_dir=target_dir,
        pid=args.pid,
        download_url=download_url,
        version=version
    )
    root.mainloop()


if __name__ == "__main__":
    main()
