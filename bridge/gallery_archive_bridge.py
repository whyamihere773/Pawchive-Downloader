"""
QML bridge for the Gallery's Compress / Extract actions.

Runs one archive job at a time on a background thread and reports progress
through signals. Extraction tries, in order: the password typed by the user,
the password remembered for that exact archive, no password, then every
candidate from the Decompressor Password Bank. Archives that still need a
password are reported back so the Gallery can ask for one.
"""

import os
import shutil
import threading

from PySide6.QtCore import QObject, Property, Signal, Slot

from core.archive_password_manager import archive_password_manager
from core.logger import logger
from services.archive_tools import (
    ARCHIVE_FORMATS,
    ArchiveTools,
    ProgressMeter,
    is_archive_name,
    path_size,
    unique_archive_path,
    validate_archive_name,
)


class GalleryArchiveBridge(QObject):
    busyChanged = Signal()
    # {percent, name, status, speed (bytes/s), eta (s, -1 = unknown), doneBytes, totalBytes,
    #  elapsed (s), index, count}
    jobProgress = Signal('QVariantMap')
    jobFinished = Signal('QVariantMap')        # summary of the finished job

    def __init__(self, app_bridge=None, tools_bridge=None, parent=None):
        super().__init__(parent)
        self._app = app_bridge
        self._tools_bridge = tools_bridge   # GalleryToolsBridge, for undo of finished copies
        # Preview files unpacked by "Look inside" are only needed for one session
        threading.Thread(target=self.clear_preview_cache, daemon=True, name="ArchivePreviewCleanup").start()
        self._tools = ArchiveTools()
        self._busy = False
        self._cancel = threading.Event()

    # ── State ────────────────────────────────────────────────────────────────
    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(bool, constant=True)
    def available(self) -> bool:
        return self._tools.available

    def _set_busy(self, val: bool):
        if self._busy != val:
            self._busy = val
            self.busyChanged.emit()

    def _is_blocked(self, path: str) -> bool:
        if not self._app or not hasattr(self._app, "getPathSafetyInfo"):
            return False
        info = self._app.getPathSafetyInfo(path)
        return bool(info.get("is_blocked"))

    # ── Queries used by the dialog ───────────────────────────────────────────
    @Slot(str, result=bool)
    def isArchive(self, filename: str) -> bool:
        return is_archive_name(filename or "")

    @Slot('QVariantList', result='QVariantList')
    def describeArchives(self, paths: list) -> list:
        """Which of the given paths are archives, and whether each can be extracted."""
        out = []
        for p in paths or []:
            name = os.path.basename(p or "")
            if not p or not is_archive_name(name):
                continue
            ok, reason = self._tools.can_extract(name)
            try:
                size = os.path.getsize(p)
            except OSError:
                size = 0
            out.append({"path": os.path.normpath(p), "name": name, "size": size, "supported": ok, "reason": reason})
        return out

    @Slot(str, result='qint64')
    def freeSpace(self, path: str) -> int:
        try:
            probe = path
            while probe and not os.path.exists(probe):
                parent = os.path.dirname(probe)
                if parent == probe:
                    break
                probe = parent
            return shutil.disk_usage(probe or path).free
        except Exception:
            return -1

    @Slot(str, result=str)
    def validateName(self, name: str) -> str:
        return validate_archive_name(name or "")

    # ── Jobs ─────────────────────────────────────────────────────────────────
    @Slot()
    def cancel(self):
        if self._busy:
            self._cancel.set()
            self._tools.cancel()

    @Slot('QVariantList', 'QVariantMap', result=str)
    def startCompress(self, paths: list, options: dict) -> str:
        """Returns '' when the job started, otherwise an error message."""
        if self._busy:
            return "Another archive job is still running."
        sources = [os.path.normpath(p) for p in (paths or []) if p and os.path.exists(p)]
        if not sources:
            return "Nothing to archive: the selected items no longer exist."

        fmt = str(options.get("format") or "zip").lower()
        if fmt not in ARCHIVE_FORMATS:
            return f"Unsupported archive format: {fmt}"
        mode = str(options.get("mode") or "single")
        level = str(options.get("level") or "normal")
        password = str(options.get("password") or "")
        dest_dir = os.path.normpath(str(options.get("destDir") or os.path.dirname(sources[0])))
        name = str(options.get("name") or "").strip()
        delete_originals = bool(options.get("deleteOriginals"))

        if not os.path.isdir(dest_dir):
            return f"The destination folder doesn't exist: {dest_dir}"
        if self._is_blocked(dest_dir):
            return "Saving archives into a protected system folder is blocked."
        dest_case = os.path.normcase(dest_dir)
        for s in sources:
            if self._is_blocked(s):
                return f"Archiving a protected system folder is blocked: {os.path.basename(s)}"
            s_case = os.path.normcase(s)
            if os.path.isdir(s) and (dest_case == s_case or dest_case.startswith(s_case + os.sep)):
                return f"The archive can't be saved inside '{os.path.basename(s)}', which is being archived."
        if mode == "single":
            err = validate_archive_name(name)
            if err:
                return err

        self._cancel.clear()
        self._set_busy(True)
        threading.Thread(
            target=self._run_compress,
            args=(sources, dest_dir, mode, name, fmt, level, password, delete_originals),
            daemon=True,
            name="GalleryCompress",
        ).start()
        return ""

    @Slot('QVariantList', 'QVariantMap', result=str)
    def startExtract(self, paths: list, options: dict) -> str:
        """Returns '' when the job started, otherwise an error message."""
        if self._busy:
            return "Another archive job is still running."
        archives = [a for a in self.describeArchives(paths) if a["supported"] and os.path.exists(a["path"])]
        if not archives:
            return "None of the selected files can be extracted."

        dest_dir = str(options.get("destDir") or "")
        if dest_dir:
            dest_dir = os.path.normpath(dest_dir)
            if not os.path.isdir(dest_dir):
                return f"The destination folder doesn't exist: {dest_dir}"
            if self._is_blocked(dest_dir):
                return "Extracting into a protected system folder is blocked."
        password = str(options.get("password") or "")
        per_archive = dict(options.get("passwords") or {})
        remember = bool(options.get("rememberPassword", True))
        delete_archives = bool(options.get("deleteArchives"))

        self._cancel.clear()
        self._set_busy(True)
        threading.Thread(
            target=self._run_extract,
            args=(archives, dest_dir, password, per_archive, remember, delete_archives),
            daemon=True,
            name="GalleryExtract",
        ).start()
        return ""

    # ── Look inside an archive ──────────────────────────────────────────────
    @Slot(str, str, result=int)
    def listArchiveAsync(self, path: str, password: str = "") -> int:
        """listArchive in the background (answer via listingReady). Reading a big archive with
        7-Zip used to freeze the window until it finished."""
        self._listing_token = getattr(self, "_listing_token", 0) + 1
        token = self._listing_token

        def _job():
            try:
                res = self.listArchive(path, password)
            except Exception as e:
                res = {"ok": False, "error": f"Couldn't read the archive: {e}", "needsPassword": False, "entries": []}
            try:
                self.listingReady.emit(token, res)
            except RuntimeError:
                pass      # the app is closing
        threading.Thread(target=_job, daemon=True, name="ArchiveListing").start()
        return token

    @Slot(str, str, result='QVariantMap')
    def listArchive(self, path: str, password: str = "") -> dict:
        """List an archive's contents without extracting it.

        Returns {ok, error, needsPassword, encrypted, entries[], fileCount, totalSize, packedSize}.
        Each entry: {path ("a/b.png"), name, dir ("a"), is_dir, size, packed, mtime}.
        Folders that only exist implicitly (common in ZIPs) are added so every file has a parent.
        """
        import subprocess
        from services.archive_tools import _hidden_window_kwargs

        result = {"ok": False, "error": "", "needsPassword": False, "encrypted": False,
                  "entries": [], "fileCount": 0, "totalSize": 0, "packedSize": 0}
        name = os.path.basename(path or "")
        ok, reason = self._tools.can_extract(name)
        if not path or not os.path.isfile(path) or not ok:
            result["error"] = reason or "The archive no longer exists."
            return result
        engine = self._tools.engine_for(name)
        cmd = [engine._7za_path, "l", "-slt", "-sccUTF-8", f"-p{password}" if password else "-p-", "--", path]
        try:
            r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=120, **_hidden_window_kwargs())
        except Exception as e:
            result["error"] = f"Couldn't read the archive: {e}"
            return result
        out = r.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")
        if r.returncode != 0:
            if engine.is_password_error(out):
                result["needsPassword"] = True
                result["error"] = "This archive is password-protected." if not password else "That password didn't work."
            else:
                tail = [l for l in out.strip().splitlines() if l.strip()][-3:]
                result["error"] = "Couldn't read the archive: " + " ".join(tail)
            return result

        body = out.split("\n----------\n", 1)
        blocks = body[1].split("\n\n") if len(body) == 2 else []
        entries, seen_dirs = [], set()
        for block in blocks:
            fields = {}
            for line in block.splitlines():
                if " = " in line:
                    k, v = line.split(" = ", 1)
                    fields[k.strip()] = v.strip()
            p = fields.get("Path", "").replace("\\", "/").strip("/")
            if not p:
                continue
            is_dir = fields.get("Folder") == "+" or "D" in fields.get("Attributes", "").split(" ")[0]
            if fields.get("Encrypted") == "+":
                result["encrypted"] = True
            size = int(fields.get("Size") or 0) if (fields.get("Size") or "0").isdigit() else 0
            packed = int(fields.get("Packed Size") or 0) if (fields.get("Packed Size") or "0").isdigit() else 0
            parent = p.rsplit("/", 1)[0] if "/" in p else ""
            entries.append({"path": p, "name": p.rsplit("/", 1)[-1], "dir": parent, "is_dir": is_dir,
                            "size": size, "packed": packed, "mtime": fields.get("Modified", "")})
            if is_dir:
                seen_dirs.add(p)
            else:
                result["fileCount"] += 1
                result["totalSize"] += size
                result["packedSize"] += packed
        # Synthesize folders that only appear inside file paths
        for e in list(entries):
            parent = e["dir"]
            while parent and parent not in seen_dirs:
                seen_dirs.add(parent)
                up = parent.rsplit("/", 1)[0] if "/" in parent else ""
                entries.append({"path": parent, "name": parent.rsplit("/", 1)[-1], "dir": up, "is_dir": True,
                                "size": 0, "packed": 0, "mtime": ""})
                parent = up
        result["entries"] = entries
        result["ok"] = True
        return result

    previewReady = Signal(int, 'QVariantMap')   # token, {ok, error, needsPassword, files: {entryPath: localPath}}
    listingReady = Signal(int, 'QVariantMap')   # token, the result of listArchive

    @staticmethod
    def _preview_root() -> str:
        from PySide6.QtCore import QStandardPaths
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation) or os.path.expanduser("~")
        return os.path.join(base, "archive_preview")

    @Slot(str, 'QVariantList', str, result=int)
    def extractForPreview(self, archivePath: str, entryPaths: list, password: str = "") -> int:
        """Unpack just the given entries into a temporary cache (for the lightbox). Answer via previewReady."""
        self._preview_token = getattr(self, "_preview_token", 0) + 1
        token = self._preview_token
        threading.Thread(target=self._run_preview, args=(token, archivePath, list(entryPaths or []), password),
                         daemon=True, name="ArchivePreview").start()
        return token

    def _run_preview(self, token, archive_path, entries, password):
        import hashlib
        import subprocess
        from services.archive_tools import _hidden_window_kwargs

        res = {"ok": False, "error": "", "needsPassword": False, "files": {}}
        try:
            st = os.stat(archive_path)
        except OSError:
            res["error"] = "The archive no longer exists."
            self.previewReady.emit(token, res)
            return
        key = hashlib.sha1(f"{os.path.normcase(archive_path)}|{st.st_mtime_ns}|{st.st_size}".encode("utf-8")).hexdigest()[:16]
        out_dir = os.path.join(self._preview_root(), key)
        os.makedirs(out_dir, exist_ok=True)

        def local(e):
            return os.path.join(out_dir, *e.split("/"))

        missing = [e for e in entries if not os.path.isfile(local(e))]
        if missing:
            engine = self._tools.engine_for(os.path.basename(archive_path))
            list_file = os.path.join(out_dir, f".list_{token}.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                f.write("\n".join(missing))
            # -spd: names are literal (no wildcards); -aos: keep files already unpacked
            cmd = [engine._7za_path, "x", "-y", "-aos", "-spd", "-scsUTF-8", "-sccUTF-8",
                   f"-o{out_dir}", f"-p{password}" if password else "-p-", archive_path, f"@{list_file}"]
            try:
                r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   timeout=600, **_hidden_window_kwargs())
                out = r.stdout.decode("utf-8", errors="replace")
                if r.returncode != 0:
                    if engine.is_password_error(out):
                        res["needsPassword"] = True
                        res["error"] = "These files are password-protected." if not password else "That password didn't work."
                    else:
                        tail = [l for l in out.strip().splitlines() if l.strip()][-2:]
                        res["error"] = "Couldn't unpack for preview: " + " ".join(tail)
            except Exception as e:
                res["error"] = f"Couldn't unpack for preview: {e}"
            finally:
                try:
                    os.remove(list_file)
                except OSError:
                    pass

        res["files"] = {e: local(e) for e in entries if os.path.isfile(local(e))}
        res["ok"] = bool(res["files"]) and not res["needsPassword"]
        self.previewReady.emit(token, res)

    def clear_preview_cache(self):
        """Remove unpacked preview files from earlier sessions (our own temp data only)."""
        shutil.rmtree(self._preview_root(), ignore_errors=True)

    @Slot('QVariantList', str, result=str)
    def startCopy(self, paths: list, destDir: str) -> str:
        """Copy files/folders into destDir in the background. Returns '' or an error message."""
        if self._busy:
            return "Another file job is still running."
        sources = [os.path.normpath(p) for p in (paths or []) if p and os.path.exists(p)]
        if not sources:
            return "Nothing to copy: the items no longer exist."
        dest = os.path.normpath(destDir or "")
        if not dest or not os.path.isdir(dest):
            return f"The destination folder doesn't exist: {destDir}"
        if self._is_blocked(dest):
            return "Copying into a protected system folder is blocked."
        dest_case = os.path.normcase(dest)
        for s in sources:
            s_case = os.path.normcase(s)
            if os.path.isdir(s) and (dest_case == s_case or dest_case.startswith(s_case + os.sep)):
                return f"Can't copy '{os.path.basename(s)}' into itself."

        self._cancel.clear()
        self._set_busy(True)
        threading.Thread(target=self._run_copy, args=(sources, dest), daemon=True, name="GalleryCopy").start()
        return ""

    # ── Workers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _unique_copy_target(dest_dir: str, name: str, is_dir: bool) -> str:
        """'photo.png' -> 'photo (2).png' when the name is taken; folders get ' (2)' too."""
        target = os.path.join(dest_dir, name)
        if not os.path.exists(target):
            return target
        stem, ext = (name, "") if is_dir else os.path.splitext(name)
        n = 2
        while os.path.exists(os.path.join(dest_dir, f"{stem} ({n}){ext}")):
            n += 1
        return os.path.join(dest_dir, f"{stem} ({n}){ext}")

    def _copy_file(self, src: str, dst: str, on_bytes) -> None:
        """Chunked copy so progress (and Cancel) work on big files."""
        with open(src, "rb") as fin, open(dst, "wb") as fout:
            while True:
                if self._cancel.is_set():
                    raise InterruptedError()
                chunk = fin.read(4 * 1024 * 1024)
                if not chunk:
                    break
                fout.write(chunk)
                on_bytes(len(chunk))
        try:
            shutil.copystat(src, dst)
        except OSError:
            pass

    def _run_copy(self, sources, dest_dir):
        from services.archive_tools import path_size
        self.jobProgress.emit({"percent": 0.0, "name": "", "status": "Measuring files…", "speed": 0.0, "eta": -1.0,
                               "doneBytes": 0, "totalBytes": 0, "elapsed": 0.0, "index": 0, "count": len(sources)})
        sizes = [path_size(s) for s in sources]
        meter = ProgressMeter(sum(sizes))
        copied_total = [0]
        last_copy_emit = [0.0]
        outputs, errors = [], []

        for i, src in enumerate(sources):
            if self._cancel.is_set():
                break
            name = os.path.basename(src)
            is_dir = os.path.isdir(src)
            target = self._unique_copy_target(dest_dir, name, is_dir)
            status = f"Copying {name}…"

            def on_bytes(n, i=i, name=name, status=status):
                copied_total[0] += n
                now = time.time()
                if now - last_copy_emit[0] < 0.1:
                    return
                last_copy_emit[0] = now
                info = meter.sample(copied_total[0])
                info.update({"name": name, "status": status, "index": i, "count": len(sources)})
                self.jobProgress.emit(info)

            try:
                if is_dir:
                    for dirpath, dirnames, files in os.walk(src):
                        rel = os.path.relpath(dirpath, src)
                        out_dir = target if rel == "." else os.path.join(target, rel)
                        os.makedirs(out_dir, exist_ok=True)
                        for f in files:
                            self._copy_file(os.path.join(dirpath, f), os.path.join(out_dir, f), on_bytes)
                else:
                    self._copy_file(src, target, on_bytes)
                outputs.append(target)
            except InterruptedError:
                self._remove_partial_copy(target)
                break
            except Exception as e:
                self._remove_partial_copy(target)
                errors.append(f"{name}: {e}")

        if outputs:
            logger.info(f"Copied {len(outputs)} item(s) to '{dest_dir}'.", category="gallery")
            if self._tools_bridge is not None:
                self._tools_bridge.record_copy(outputs)  # also when cancelled: finished items stay undoable
        for e in errors[:5]:
            logger.warning(e, category="gallery")

        self._set_busy(False)
        self.jobFinished.emit({
            "kind": "copy",
            "succeeded": len(outputs),
            "failed": len(errors),
            "total": len(sources),
            "cancelled": self._cancel.is_set(),
            "outputs": outputs,
            "errors": errors,
            "warnings": [],
            "needsPassword": [],
            "originalsTrashed": False,
        })

    @staticmethod
    def _remove_partial_copy(target: str):
        """Remove an item this job was in the middle of creating (never pre-existing data)."""
        try:
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
            elif os.path.isfile(target):
                os.remove(target)
        except OSError:
            pass

    def _progress(self, meter: ProgressMeter, done_before: int, item_size: int, pct: float,
                  index: int, count: int, name: str, status: str):
        """Report progress weighted by bytes, so the ETA isn't thrown off by one huge item."""
        pct = max(0.0, min(100.0, pct))
        now = time.time()
        last_t = getattr(self, "_last_job_progress_time", 0.0)
        if pct < 100.0 and (now - last_t < 0.1):
            return
        self._last_job_progress_time = now
        info = meter.sample(done_before + item_size * pct / 100.0)
        if not meter.total:
            info["percent"] = ((index + pct / 100.0) / max(1, count)) * 100.0
        info.update({"name": name, "status": status, "index": index, "count": count})
        self.jobProgress.emit(info)

    def _status(self, meter: ProgressMeter, done_before: int, index: int, count: int, name: str, status: str):
        """Status-only update (opening, password checks) that keeps the current numbers."""
        self._progress(meter, done_before, 0, 0.0, index, count, name, status)

    def _trash(self, paths):
        from PySide6.QtCore import QFile
        failed = []
        for p in paths:
            try:
                if not QFile.moveToTrash(p):
                    failed.append(os.path.basename(p))
            except Exception:
                failed.append(os.path.basename(p))
        return failed

    def _run_compress(self, sources, dest_dir, mode, name, fmt, level, password, delete_originals):
        ext = ARCHIVE_FORMATS[fmt]
        if mode == "each":
            jobs = []
            for s in sources:
                base = os.path.basename(s) if os.path.isdir(s) else os.path.splitext(os.path.basename(s))[0]
                jobs.append(([s], base or os.path.basename(s)))
        else:
            jobs = [(sources, name)]

        outputs, errors, warnings = [], [], []
        archived_sources = []

        # Measure first so speed and ETA are based on real bytes
        self.jobProgress.emit({"percent": 0.0, "name": "", "status": "Measuring files…", "speed": 0.0, "eta": -1.0,
                               "doneBytes": 0, "totalBytes": 0, "elapsed": 0.0, "index": 0, "count": len(jobs)})
        sizes = []
        for srcs, _ in jobs:
            if self._cancel.is_set():
                break
            sizes.append(sum(path_size(s) for s in srcs))
        meter = ProgressMeter(sum(sizes))
        done_before = 0

        for i, (srcs, base) in enumerate(jobs):
            if self._cancel.is_set():
                break
            dest_path = unique_archive_path(dest_dir, base, ext)
            label = os.path.basename(dest_path)
            size = sizes[i] if i < len(sizes) else 0
            status = f"Creating {label}…"
            self._progress(meter, done_before, size, 0.0, i, len(jobs), label, status)
            ok, msg = self._tools.create_archive(
                srcs, dest_path, fmt, level, password,
                lambda pct, i=i, label=label, size=size, db=done_before, status=status:
                    self._progress(meter, db, size, pct, i, len(jobs), label, status),
                self._cancel,
            )
            done_before += size
            if ok:
                outputs.append(dest_path)
                if msg:
                    # 7-Zip skipped something (e.g. a locked file): that file isn't in the archive,
                    # so the originals of this archive are kept even with "delete originals"
                    warnings.append(f"{label}: {msg} — originals kept")
                else:
                    archived_sources.extend(srcs)
            elif not self._cancel.is_set():
                errors.append(f"{label}: {msg}")

        trash_failed = []
        if delete_originals and archived_sources and not self._cancel.is_set():
            trash_failed = self._trash(archived_sources)
            if trash_failed:
                errors.append("Couldn't move to the Recycle Bin: " + ", ".join(trash_failed[:5]))

        if outputs:
            logger.info(f"Created {len(outputs)} archive(s) in '{dest_dir}'.", category="gallery")
        for e in errors[:5]:
            logger.warning(e, category="gallery")

        self._set_busy(False)
        self.jobFinished.emit({
            "kind": "compress",
            "succeeded": len(outputs),
            "failed": len(errors) if not trash_failed else len(errors) - 1,
            "total": len(jobs),
            "cancelled": self._cancel.is_set(),
            "outputs": outputs,
            "errors": errors,
            "warnings": warnings,
            "needsPassword": [],
            "originalsTrashed": delete_originals and not self._cancel.is_set() and len(archived_sources) > len(trash_failed),
        })

    def _run_extract(self, archives, dest_dir, password, per_archive, remember, delete_archives):
        outputs, errors, needs_password, extracted_archives = [], [], [], []
        count = len(archives)
        meter = ProgressMeter(sum(a["size"] for a in archives))
        done_before = 0
        for i, arc in enumerate(archives):
            if self._cancel.is_set():
                break
            path, name, size = arc["path"], arc["name"], arc["size"]
            target_parent = dest_dir or os.path.dirname(path)
            status = f"Extracting {name}…"
            self._status(meter, done_before, i, count, name, f"Opening {name}…")

            def cb(pct, i=i, name=name, size=size, db=done_before, status=status):
                self._progress(meter, db, size, pct, i, count, name, status)

            supplied = per_archive.get(path) or password or ""
            attempts = []
            if supplied:
                attempts.append(supplied)
            remembered = archive_password_manager.get_archive_password(path)
            if remembered and remembered not in attempts:
                attempts.append(remembered)
            attempts.append(None)  # no password (a quick header check runs first)

            ok, err, out_dir, used_pw = False, "", "", None
            for pw in attempts:
                if self._cancel.is_set():
                    break
                ok, err, out_dir = self._tools.extract(path, target_parent, pw, cb, self._cancel, f"gal_{i}")
                if ok:
                    used_pw = pw
                    break
                if not self._tools.engine.is_password_error(err):
                    break

            # Still locked: try every saved candidate. A wrong password fails within
            # moments, and the right one extracts straight away (no separate test pass).
            if not ok and not self._cancel.is_set() and self._tools.engine.is_password_error(err):
                candidates = [c for c in archive_password_manager.find_candidate_passwords(path, "") if c not in attempts]
                for n, cand in enumerate(candidates, 1):
                    if self._cancel.is_set():
                        break
                    self._status(meter, done_before, i, count, name,
                                 f"Trying saved passwords for {name} ({n} of {len(candidates)})…")
                    ok, err, out_dir = self._tools.extract(path, target_parent, cand, cb, self._cancel, f"gal_{i}")
                    if ok:
                        used_pw = cand
                        break
                    if not self._tools.engine.is_password_error(err):
                        break

            done_before += size
            if ok:
                outputs.append(out_dir)
                extracted_archives.append(path)
                # record_archive_password also adds the password to the bank, so a
                # password the user typed is only stored when they asked to remember it.
                if used_pw and (used_pw != supplied or remember):
                    archive_password_manager.record_archive_password(path, used_pw)
            elif self._cancel.is_set():
                break
            elif self._tools.engine.is_password_error(err):
                needs_password.append({"path": path, "name": name, "wrongPassword": bool(supplied)})
            else:
                errors.append(f"{name}: {err}")

        trash_failed = []
        if delete_archives and extracted_archives and not self._cancel.is_set():
            trash_failed = self._trash(extracted_archives)
            if trash_failed:
                errors.append("Couldn't move to the Recycle Bin: " + ", ".join(trash_failed[:5]))

        if outputs:
            logger.info(f"Extracted {len(outputs)} archive(s).", category="gallery")
        for e in errors[:5]:
            logger.warning(e, category="gallery")

        self._set_busy(False)
        self.jobFinished.emit({
            "kind": "extract",
            "succeeded": len(outputs),
            "failed": len([e for e in errors if not e.startswith("Couldn't move")]),
            "total": count,
            "cancelled": self._cancel.is_set(),
            "outputs": outputs,
            "errors": errors,
            "warnings": [],
            "needsPassword": needs_password,
            "originalsTrashed": delete_archives and not self._cancel.is_set() and len(extracted_archives) > len(trash_failed),
        })
