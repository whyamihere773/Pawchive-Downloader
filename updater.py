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

# GUI: Tkinter (standard library, zero external DLL dependency on Windows)
try:
    import tkinter as tk
    from tkinter import ttk
    HAS_TKINTER = True
except (ImportError, Exception):
    HAS_TKINTER = False

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except Exception:
    HAS_PIL = False


def set_dark_title_bar(window):
    """Enables Windows 10/11 native immersive dark mode on the window frame."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()
        value = ctypes.c_int(1)
        for attr in (20, 19):  # 20 on Win11/modern Win10, 19 on earlier builds
            res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
            )
            if res == 0:
                break
    except Exception:
        pass


class ModernProgressBar(tk.Canvas):
    """Smooth, antialiased pill-shaped progress bar built with native Tkinter Canvas."""
    def __init__(self, parent, bg="#131722", trough="#1A2130", fill="#38BDF8", height=8, radius=4, **kwargs):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0, **kwargs)
        self.trough_color = trough
        self.fill_color = fill
        self.radius = radius
        self.progress = 0.0
        self.bind("<Configure>", self._draw)

    def set(self, value):
        self.progress = max(0.0, min(100.0, float(value)))
        self._draw()

    def set_color(self, fill):
        self.fill_color = fill
        self._draw()

    def _draw(self, event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 4 or h <= 2:
            return
        r = min(self.radius, h // 2)
        # Background pill track
        self._create_rounded_rect(0, 0, w, h, r, fill=self.trough_color)
        # Active filled progress pill
        if self.progress > 0:
            fill_w = max(r * 2, int(w * (self.progress / 100.0)))
            fill_w = min(w, fill_w)
            self._create_rounded_rect(0, 0, fill_w, h, r, fill=self.fill_color)

    def _create_rounded_rect(self, x1, y1, x2, y2, r, fill):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1
        ]
        return self.create_polygon(points, fill=fill, smooth=True)

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
        self._icon_img = None

        self._setup_window()
        self._setup_styles()
        self._create_widgets()

        # Start background update worker
        threading.Thread(target=self._run_update_pipeline, daemon=True).start()

    def _setup_window(self):
        self.root.title("Pawchive Downloader Updater")
        self.root.geometry("520x330")
        self.root.resizable(False, False)
        self.root.configure(bg="#0B0D12")
        set_dark_title_bar(self.root)

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

    def _create_widgets(self):
        # Outer Card with crisp border
        card = tk.Frame(self.root, bg="#131722", bd=0, highlightbackground="#2A303F", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Top vibrant accent gradient line
        top_accent = tk.Canvas(card, height=3, bg="#131722", highlightthickness=0, bd=0)
        top_accent.pack(fill="x", side="top")
        top_accent.create_rectangle(0, 0, 600, 3, fill="#38BDF8", outline="")

        # Header Frame
        header_frame = tk.Frame(card, bg="#131722")
        header_frame.pack(fill="x", padx=22, pady=(16, 12))

        # Brand Icon + Title block
        brand_frame = tk.Frame(header_frame, bg="#131722")
        brand_frame.pack(side="left", fill="y")

        icon_path = os.path.join(self.target_dir, "assets", "icon.png")
        if HAS_PIL and os.path.exists(icon_path):
            try:
                pil_img = Image.open(icon_path).resize((36, 36), Image.Resampling.LANCZOS)
                self._icon_img = ImageTk.PhotoImage(pil_img)
                icon_lbl = tk.Label(brand_frame, image=self._icon_img, bg="#131722")
                icon_lbl.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        title_col = tk.Frame(brand_frame, bg="#131722")
        title_col.pack(side="left", fill="y")

        title_label = tk.Label(
            title_col,
            text="Pawchive Downloader",
            font=("Segoe UI", 13, "bold"),
            fg="#F8FAFC",
            bg="#131722"
        )
        title_label.pack(anchor="w")

        sub_label = tk.Label(
            title_col,
            text="Companion Auto-Updater",
            font=("Segoe UI", 9),
            fg="#64748B",
            bg="#131722"
        )
        sub_label.pack(anchor="w", pady=(1, 0))

        # Version Pill Badge
        badge_frame = tk.Frame(header_frame, bg="#1E293B", highlightbackground="#2A303F", highlightthickness=1)
        badge_frame.pack(side="right", pady=4)

        v_text = self.version if str(self.version).startswith("v") else f"v{self.version}"
        self.ver_badge = tk.Label(
            badge_frame,
            text=v_text,
            font=("Cascadia Code", 9, "bold"),
            fg="#38BDF8",
            bg="#1E293B",
            padx=10,
            pady=3
        )
        self.ver_badge.pack()

        # Divider
        sep = tk.Frame(card, height=1, bg="#1E2433")
        sep.pack(fill="x", padx=22, pady=(2, 14))

        # Status & Percentage Header Row
        status_row = tk.Frame(card, bg="#131722")
        status_row.pack(fill="x", padx=22, pady=(0, 8))

        self.status_label = tk.Label(
            status_row,
            text="Preparing update pipeline...",
            font=("Segoe UI", 10, "bold"),
            fg="#F8FAFC",
            bg="#131722"
        )
        self.status_label.pack(side="left")

        self.pct_label = tk.Label(
            status_row,
            text="0%",
            font=("Cascadia Code", 10, "bold"),
            fg="#38BDF8",
            bg="#131722"
        )
        self.pct_label.pack(side="right")

        # Smooth Canvas Progress Bar
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ModernProgressBar(
            card,
            bg="#131722",
            trough="#1A2130",
            fill="#38BDF8",
            height=8,
            radius=4
        )
        self.progress_bar.pack(fill="x", padx=22, pady=(0, 10))

        # Details / Transfer Statistics Card
        detail_card = tk.Frame(card, bg="#0E1118", highlightbackground="#1E2433", highlightthickness=1)
        detail_card.pack(fill="x", padx=22, pady=(0, 16))

        self.detail_label = tk.Label(
            detail_card,
            text="● Initializing release synchronization...",
            font=("Cascadia Code", 8),
            fg="#94A3B8",
            bg="#0E1118",
            padx=10,
            pady=7,
            anchor="w"
        )
        self.detail_label.pack(fill="x")

        # Footer Action Area
        footer_frame = tk.Frame(card, bg="#131722")
        footer_frame.pack(fill="x", padx=22, pady=(0, 14), side="bottom")

        safe_lbl = tk.Label(
            footer_frame,
            text="🔒 Safe zero-lock atomic deployment",
            font=("Segoe UI", 8),
            fg="#475569",
            bg="#131722"
        )
        safe_lbl.pack(side="left", pady=4)

        self.cancel_btn = tk.Button(
            footer_frame,
            text="Cancel",
            font=("Segoe UI", 9, "bold"),
            fg="#94A3B8",
            bg="#1E2430",
            activebackground="#283244",
            activeforeground="#F8FAFC",
            bd=0,
            padx=16,
            pady=5,
            cursor="hand2",
            highlightbackground="#2A303F",
            highlightthickness=1,
            relief="flat",
            command=self._on_cancel
        )
        self.cancel_btn.pack(side="right")

        def _on_btn_enter(e):
            if str(self.cancel_btn["state"]) != "disabled":
                self.cancel_btn.config(bg="#283244", fg="#F8FAFC", highlightbackground="#38BDF8")

        def _on_btn_leave(e):
            if str(self.cancel_btn["state"]) != "disabled":
                self.cancel_btn.config(bg="#1E2430", fg="#94A3B8", highlightbackground="#2A303F")

        self.cancel_btn.bind("<Enter>", _on_btn_enter)
        self.cancel_btn.bind("<Leave>", _on_btn_leave)

    def _set_status(self, status: str, detail: str = "", progress: Optional[float] = None):
        def _update():
            self.status_label.config(text=status)
            if detail is not None:
                d_text = detail
                if d_text and not d_text.startswith("●"):
                    d_text = f"● {d_text}"
                self.detail_label.config(text=d_text)
            if progress is not None:
                p_val = max(0.0, min(100.0, float(progress)))
                self.progress_var.set(p_val)
                self.progress_bar.set(p_val)
                self.pct_label.config(text=f"{int(p_val)}%")
                if p_val >= 99.5:
                    self.progress_bar.set_color("#10B981")
                    self.pct_label.config(fg="#10B981", text="100%")
                    self.status_label.config(fg="#10B981")
        self.root.after(0, _update)

    def _on_cancel(self):
        self._cancel_requested = True
        self._set_status("Cancelling update...", "Cleaning up temporary files...", progress=0.0)
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
            dlg.title("Pawchive Updater — Action Required")
            dlg.geometry("500x340")
            dlg.resizable(False, False)
            dlg.configure(bg="#0B0D12")
            set_dark_title_bar(dlg)
            dlg.grab_set()  # Modal
            dlg.transient(self.root)

            # Center on parent
            dlg.update_idletasks()
            px = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
            py = self.root.winfo_y() + (self.root.winfo_height() - 340) // 2
            dlg.geometry(f"+{px}+{py}")

            card = tk.Frame(dlg, bg="#131722", highlightbackground="#2A303F", highlightthickness=1)
            card.pack(fill="both", expand=True, padx=16, pady=16)

            # Top warning amber line
            top_bar = tk.Canvas(card, height=3, bg="#131722", highlightthickness=0, bd=0)
            top_bar.pack(fill="x", side="top")
            top_bar.create_rectangle(0, 0, 500, 3, fill="#F59E0B", outline="")

            hdr = tk.Frame(card, bg="#131722")
            hdr.pack(fill="x", padx=20, pady=(16, 6))

            tk.Label(
                hdr,
                text="⚠️ Application Files Still in Use",
                font=("Segoe UI", 12, "bold"),
                fg="#F8FAFC", bg="#131722"
            ).pack(side="left")

            badge = tk.Frame(hdr, bg="#2E1F0A", highlightbackground="#F59E0B", highlightthickness=1)
            badge.pack(side="right")
            tk.Label(
                badge, text=f"{len(failed_files)} locked file(s)",
                font=("Cascadia Code", 8, "bold"),
                fg="#F59E0B", bg="#2E1F0A", padx=6, pady=2
            ).pack()

            explanation = (
                "Windows is holding a lock on old app files — this usually occurs when your "
                "antivirus is scanning the folder or Windows takes longer to release handles.\n\n"
                "The update package is already downloaded and verified. Choose how to apply it:"
            )
            tk.Label(
                card,
                text=explanation,
                font=("Segoe UI", 9),
                fg="#94A3B8", bg="#131722",
                justify="left", wraplength=440, anchor="w"
            ).pack(padx=20, pady=(0, 14), fill="x")

            btn_row = tk.Frame(card, bg="#131722")
            btn_row.pack(padx=20, fill="x")

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
                text="⚡ Retry as Administrator  (Recommended)",
                font=("Segoe UI", 9, "bold"),
                fg="#FFFFFF", bg="#0284C7",
                activebackground="#0369A1", activeforeground="#FFFFFF",
                bd=0, padx=16, pady=8, cursor="hand2",
                command=on_admin, anchor="w",
                highlightbackground="#38BDF8", highlightthickness=1
            )
            admin_btn.pack(fill="x", pady=(0, 4))

            # Hint under primary button
            tk.Label(
                btn_row,
                text="Windows will display a standard UAC prompt — click 'Yes' to overwrite locked files.",
                font=("Segoe UI", 8),
                fg="#64748B", bg="#131722",
                anchor="w"
            ).pack(fill="x", pady=(0, 10))

            # Secondary action
            later_btn = tk.Button(
                btn_row,
                text="I'll do it later",
                font=("Segoe UI", 9),
                fg="#94A3B8", bg="#1E2430",
                activebackground="#283244", activeforeground="#F8FAFC",
                bd=0, padx=16, pady=6, cursor="hand2",
                command=on_later, anchor="w",
                highlightbackground="#2A303F", highlightthickness=1
            )
            later_btn.pack(fill="x")

            # Hint under secondary button
            tk.Label(
                btn_row,
                text="Run 'updater.exe' from the app folder whenever you're ready.",
                font=("Segoe UI", 8),
                fg="#64748B", bg="#131722",
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

            # 2. Prepare directories in temporary directory
            temp_base = tempfile.gettempdir()
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

            exe_path = ""
            if sys.platform == "win32":
                cand = os.path.join(self.target_dir, "Pawchive Downloader.exe")
                if os.path.exists(cand):
                    exe_path = cand
                else:
                    for f in os.listdir(self.target_dir):
                        if f.lower().endswith(".exe") and "updater" not in f.lower():
                            exe_path = os.path.join(self.target_dir, f)
                            break
            else:
                cand = os.path.join(self.target_dir, "Pawchive Downloader")
                if os.path.exists(cand) and os.access(cand, os.X_OK):
                    exe_path = cand
                else:
                    for f in os.listdir(self.target_dir):
                        p = os.path.join(self.target_dir, f)
                        if os.path.isfile(p) and os.access(p, os.X_OK) and "updater" not in f.lower() and not f.endswith(".sh"):
                            exe_path = p
                            break

            if exe_path and os.path.exists(exe_path):
                subprocess.Popen([exe_path], cwd=self.target_dir)
            elif not getattr(sys, "frozen", False):
                main_py = os.path.join(self.target_dir, "main.py")
                if os.path.exists(main_py):
                    subprocess.Popen([sys.executable, main_py], cwd=self.target_dir)

            self.root.after(500, self.root.destroy)

        except Exception as err:
            self._set_status("Update Failed", f"Error: {err}", progress=0.0)
            self.root.after(0, lambda: self.cancel_btn.config(text="Close", state="normal", command=self.root.destroy))


def run_headless_update(target_dir: str, pid: int, download_url: str, version: str):
    """Fallback CLI update pipeline when Tkinter is not available (common on minimal Linux/Docker)."""
    print(f"[*] Starting Pawchive Downloader CLI updater (Target: {version or 'latest'})...")
    if pid > 0:
        print("[*] Waiting for previous application process to exit...")
        start_wait = time.time()
        while is_pid_running(pid):
            if time.time() - start_wait > 15:
                break
            time.sleep(0.3)
    time.sleep(_EXE_RELEASE_WAIT)

    temp_base = tempfile.gettempdir()
    updater_work_dir = os.path.join(temp_base, f"pawchive_update_{int(time.time())}")
    zip_dest = os.path.join(updater_work_dir, "update.zip")
    staging_dir = os.path.join(updater_work_dir, "staging")
    os.makedirs(staging_dir, exist_ok=True)

    try:
        print(f"[*] Downloading update from {download_url}...")
        req = urllib.request.Request(download_url, headers={"User-Agent": "Pawchive-Updater/1.0"})
        with urllib.request.urlopen(req, timeout=45) as resp, open(zip_dest, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)

        print("[*] Extracting update package...")
        with zipfile.ZipFile(zip_dest, "r") as zf:
            zf.extractall(staging_dir)

        stage_root = staging_dir
        entries = [os.path.join(staging_dir, e) for e in os.listdir(staging_dir)]
        if len(entries) == 1 and os.path.isdir(entries[0]):
            stage_root = entries[0]

        print("[*] Installing updated files...")
        copied = 0
        for root_d, dirs, files in os.walk(stage_root):
            rel = os.path.relpath(root_d, stage_root)
            first = rel.split(os.sep)[0] if rel != "." else ""
            if first.lower() in PROTECTED_DIRS:
                dirs[:] = []
                continue
            dest_folder = target_dir if rel == "." else os.path.join(target_dir, rel)
            os.makedirs(dest_folder, exist_ok=True)
            for file_name in files:
                if file_name.lower() in PROTECTED_FILES:
                    continue
                s_file = os.path.join(root_d, file_name)
                d_file = os.path.join(dest_folder, file_name)
                try:
                    shutil.copy2(s_file, d_file)
                    copied += 1
                except Exception as ex:
                    print(f"[!] Warning: could not copy {file_name}: {ex}")

        print(f"[+] Update complete! Installed {copied} files.")
        shutil.rmtree(updater_work_dir, ignore_errors=True)

        # Relaunch
        exe_path = ""
        if sys.platform == "win32":
            cand = os.path.join(target_dir, "Pawchive Downloader.exe")
            if os.path.exists(cand):
                exe_path = cand
        else:
            cand = os.path.join(target_dir, "Pawchive Downloader")
            if os.path.exists(cand) and os.access(cand, os.X_OK):
                exe_path = cand

        if exe_path and os.path.exists(exe_path):
            print(f"[*] Relaunching {exe_path}...")
            subprocess.Popen([exe_path], cwd=target_dir)
        elif not getattr(sys, "frozen", False):
            main_py = os.path.join(target_dir, "main.py")
            if os.path.exists(main_py):
                print(f"[*] Relaunching source: {main_py}...")
                subprocess.Popen([sys.executable, main_py], cwd=target_dir)
    except Exception as e:
        print(f"[!] Update error: {e}")
        shutil.rmtree(updater_work_dir, ignore_errors=True)


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
    # If running from inside target_dir as a compiled exe, copy self to tempdir
    # so target_dir/updater itself is not locked and can be cleanly updated!
    if getattr(sys, "frozen", False) and not args.temp_runner:
        my_exe = os.path.abspath(sys.executable)
        temp_dir = tempfile.gettempdir()
        ext = ".exe" if sys.platform == "win32" else ""
        temp_updater = os.path.join(temp_dir, f"pawchive_updater_run_{int(time.time())}{ext}")
        try:
            shutil.copy2(my_exe, temp_updater)
            if sys.platform != "win32":
                try:
                    os.chmod(temp_updater, 0o755)
                except Exception:
                    pass
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

    if not HAS_TKINTER:
        run_headless_update(target_dir, args.pid, download_url, version)
        sys.exit(0)

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
