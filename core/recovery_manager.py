"""
Recovery & Crash Journal Manager
Provides 100% crash-proof recovery for interrupted downloads.
Uses atomic write-flush-fsync-replace, automatic .bak fallback,
and multi-artist / multi-platform session tracking.
"""

import os
import json
import shutil
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Tuple, Callable
from core.logger import logger
from core.queue_journal import QueueJournal, safe_journal_call


from core.path_utils import get_config_dir


class RecoveryManager:
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = get_config_dir(config_dir)

        os.makedirs(self.config_dir, exist_ok=True)
        # The queue's crash journal is an SQLite database: saves only write what changed (the JSON
        # journal below rewrote the whole queue every 30 s; it's imported once if found)
        self.journal_file = os.path.join(self.config_dir, "recovery_journal.db")
        self.journal = QueueJournal(self.journal_file)
        self.legacy_journal_file = os.path.join(self.config_dir, "recovery_journal.json")
        self.tmp_file = os.path.join(self.config_dir, "recovery_journal.json.tmp")
        self.bak_file = os.path.join(self.config_dir, "recovery_journal.json.bak")
        self._legacy_checked = False
        self._carried_changes: List[Any] = []
        self.retry_spillover_file = os.path.join(self.config_dir, "retry_spillover.json")
        self._write_lock = threading.Lock()
        self._async_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="recovery_writer")
        self._async_checkpoint_busy = threading.Event()   # a background checkpoint write is queued / running
        self._generation = 0   # bumped by discard_recovery(); stale background writes are skipped
        # The failed files saved for Retry Failed, kept in memory: the button counts them all the time,
        # and reading the whole file on the window thread each time stalled it (#28 / scaling plan)
        self._cache_lock = threading.Lock()
        self._retry_cache_key: Any = "unread"       # (mtime, size) of the file the cache matches
        self._retry_cache: List[Dict[str, Any]] = []
        self._retry_counts: Tuple[int, int] = (0, 0)  # (all, without 404s)
        self._retry_loading = threading.Event()
        self.on_retries_loaded: Optional[Callable[[], None]] = None

    @staticmethod
    def _detect_platform(service: str, domain: str = "", url: str = "") -> str:
        """Derives a friendly platform name (e.g. Kemono, Coomer, Patreon, Fanbox, OnlyFans, Bunkr, Erome, nHentai)."""
        svc = (service or "").lower()
        dom = (domain or "").lower()
        u = (url or "").lower()

        # Dedicated external providers
        if svc in ("bunkr",) or "bunkr" in dom or "bunkr" in u or "balbums.st" in dom or "balbums.st" in u:
            return "Bunkr"
        if svc in ("erome",) or "erome" in dom or "erome" in u:
            return "Erome"
        if svc in ("nhentai",) or "nhentai" in dom or "nhentai" in u:
            return "nHentai"

        # Check domain first
        if "coomer" in dom or "coomer" in u:
            platform_base = "Coomer"
        elif "kemono" in dom or "kemono" in u:
            platform_base = "Kemono"
        elif "pawchive" in dom or "pawchive" in u:
            platform_base = "Pawchive"
        elif "cum.st" in dom or "cum.st" in u:
            platform_base = "cum.st"
        else:
            if svc in ("onlyfans", "fansly", "candfans"):
                platform_base = "Coomer"
            else:
                platform_base = "Kemono"

        service_labels = {
            "patreon": "Patreon",
            "fanbox": "Pixiv Fanbox",
            "fantia": "Fantia",
            "onlyfans": "OnlyFans",
            "fansly": "Fansly",
            "candfans": "CandFans",
            "subscribestar": "SubscribeStar",
            "boosty": "Boosty",
            "dlsite": "DLsite",
            "discord": "Discord",
            "afdian": "Afdian",
            "gumroad": "Gumroad"
        }
        svc_label = service_labels.get(svc, svc.capitalize() if svc else "Unknown")
        return f"{svc_label} ({platform_base})"

    @staticmethod
    def _format_size(num_bytes: int) -> str:
        """Formats byte count into human-readable string."""
        if num_bytes <= 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(num_bytes) < 1024.0:
                return f"{num_bytes:.2f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.2f} PB"

    @staticmethod
    def artist_name(t: Any) -> str:
        """The creator a task is shown under in the recovery summary (album sites like Bunkr are named
        after the album / folder instead of the site)."""
        def g(name):
            return getattr(t, name, "") if not isinstance(t, dict) else t.get(name, "")
        c_name = g("creator_name") or "Unknown Artist"
        p_title = g("post_title") or ""
        target_p = g("target_path") or ""
        if c_name.lower() in ("bunkr", "erome", "nhentai", "unknown artist", "bunkr album", "erome album"):
            if p_title and p_title.lower() not in ("bunkr", "erome", "nhentai", "untitled", "bunkr album", "erome album"):
                return p_title
            if target_p:
                parent_folder = os.path.basename(os.path.dirname(target_p))
                for prefix in ("Bunkr - ", "Erome - ", "nHentai - "):
                    if parent_folder.startswith(prefix):
                        extracted = parent_folder[len(prefix):].strip()
                        if extracted:
                            return extracted
                        break
        return c_name

    def _platform_of(self, t: Any) -> str:
        g = (lambda n: t.get(n, "")) if isinstance(t, dict) else (lambda n: getattr(t, n, ""))
        return self._detect_platform(g("service") or "", url=g("url") or "")

    def build_summary(self, tasks: List[Any], batches: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Calculates artist-level and overall progress summary from a list of tasks.
        """
        if not tasks:
            return {
                "artists": [],
                "total_files": 0,
                "completed_files": 0,
                "pending_files": 0,
                "failed_files": 0,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "percent": 0.0,
                "formatted_downloaded": "0 B",
                "formatted_total": "0 B",
                "saved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        artist_map: Dict[str, Dict[str, Any]] = {}
        total_files = len(tasks)
        completed_files = 0
        failed_files = 0
        pending_files = 0
        downloaded_bytes = 0
        total_bytes = 0

        for t in tasks:
            c_name = getattr(t, "creator_name", "") or (t.get("creator_name") if isinstance(t, dict) else "") or "Unknown Artist"
            svc = getattr(t, "service", "") or (t.get("service") if isinstance(t, dict) else "") or ""
            url = getattr(t, "url", "") or (t.get("url") if isinstance(t, dict) else "") or ""
            st = getattr(t, "status", "") or (t.get("status") if isinstance(t, dict) else "") or "pending"
            p_title = getattr(t, "post_title", "") or (t.get("post_title") if isinstance(t, dict) else "") or ""
            target_p = getattr(t, "target_path", "") or (t.get("target_path") if isinstance(t, dict) else "") or ""

            # If creator_name is generic provider (e.g. "Bunkr", "Erome", "nHentai", "Unknown Artist")
            # extract real creator from post_title or folder name
            if c_name.lower() in ("bunkr", "erome", "nhentai", "unknown artist", "bunkr album", "erome album"):
                if p_title and p_title.lower() not in ("bunkr", "erome", "nhentai", "untitled", "bunkr album", "erome album"):
                    c_name = p_title
                elif target_p:
                    parent_folder = os.path.basename(os.path.dirname(target_p))
                    for prefix in ("Bunkr - ", "Erome - ", "nHentai - "):
                        if parent_folder.startswith(prefix):
                            extracted = parent_folder[len(prefix):].strip()
                            if extracted:
                                c_name = extracted
                            break

            f_size = getattr(t, "file_size", 0) or (t.get("file_size", 0) if isinstance(t, dict) else 0) or 0
            d_bytes = getattr(t, "downloaded_bytes", 0) or (t.get("downloaded_bytes", 0) if isinstance(t, dict) else 0) or 0

            task_total = max(f_size, d_bytes)
            total_bytes += task_total
            downloaded_bytes += d_bytes

            if st == "completed":
                completed_files += 1
            elif st == "failed":
                failed_files += 1
            else:
                pending_files += 1

            key = f"{c_name}_{svc}".lower()
            if key not in artist_map:
                artist_map[key] = {
                    "name": c_name,
                    "service": svc,
                    "platform": self._detect_platform(svc, url=url),
                    "completed": 0,
                    "total": 0,
                    "downloaded_bytes": 0,
                    "total_bytes": 0
                }
            artist_map[key]["total"] += 1
            artist_map[key]["total_bytes"] += task_total
            artist_map[key]["downloaded_bytes"] += d_bytes
            if st == "completed":
                artist_map[key]["completed"] += 1

        artists_list = []
        for a in artist_map.values():
            pct = (a["completed"] / a["total"] * 100.0) if a["total"] > 0 else 0.0
            artists_list.append({
                "name": a["name"],
                "service": a["service"],
                "platform": a["platform"],
                "completed": a["completed"],
                "total": a["total"],
                "percent": round(pct, 1),
                "formatted_downloaded": self._format_size(a["downloaded_bytes"]),
                "formatted_total": self._format_size(a["total_bytes"])
            })

        overall_pct = (completed_files / total_files * 100.0) if total_files > 0 else 0.0

        return {
            "artists": artists_list,
            "total_files": total_files,
            "completed_files": completed_files,
            "pending_files": pending_files,
            "failed_files": failed_files,
            "downloaded_bytes": downloaded_bytes,
            "total_bytes": total_bytes,
            "percent": round(overall_pct, 1),
            "formatted_downloaded": self._format_size(downloaded_bytes),
            "formatted_total": self._format_size(total_bytes),
            "saved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def save_checkpoint(
        self,
        tasks: List[Any],
        batches: Optional[List[Dict[str, Any]]] = None,
        settings: Optional[Dict[str, Any]] = None,
        status: str = "interrupted",
        async_write: bool = False,
        changed: Optional[List[Any]] = None
    ) -> bool:
        """
        Saves the queue to the crash journal: only tasks that changed since the last save are written.
        `changed` (tasks whose status changed) lets a save skip comparing every task. Can run in the
        background so it never pauses downloads or the window.
        """
        if not tasks:
            return False

        if async_write:
            # On slow drives a write can take longer than the 30 s between checkpoints: don't pile them up.
            # The changes of a skipped save go with the next one (they've been taken from the counter).
            if self._async_checkpoint_busy.is_set():
                if changed:
                    self._carried_changes.extend(changed)
                return True
            self._async_checkpoint_busy.set()
            if changed is not None and self._carried_changes:
                changed = list(changed) + self._carried_changes
                self._carried_changes = []

            generation = self._generation

            def _job(t, b, s, st, ch):
                try:
                    self._save_checkpoint_sync(t, b, s, st, generation=generation, changed=ch)
                finally:
                    self._async_checkpoint_busy.clear()

            self._async_executor.submit(
                _job,
                list(tasks),
                list(batches) if batches else None,
                dict(settings) if settings else None,
                status,
                list(changed) if changed is not None else None,
            )
            return True
        return self._save_checkpoint_sync(tasks, batches, settings, status, changed=changed)

    def _save_checkpoint_sync(
        self,
        tasks: List[Any],
        batches: Optional[List[Dict[str, Any]]] = None,
        settings: Optional[Dict[str, Any]] = None,
        status: str = "interrupted",
        generation: Optional[int] = None,
        changed: Optional[List[Any]] = None
    ) -> bool:
        with self._write_lock:
            # A background write queued before the journal was discarded (download finished or
            # cancelled) must not bring it back: that showed "Unfinished download detected" next start
            if generation is not None and generation != self._generation:
                return False
            try:
                self._import_legacy_journal()
                written = self.journal.sync(tasks, batches, settings, status, changed=changed,
                                            artist_of=self.artist_name, platform_of=self._platform_of)
                logger.debug(f"Download recovery checkpoint saved ({written} changed file(s)).", category="session")
                return True
            except Exception as e:
                logger.error(f"Failed to save recovery checkpoint: {e}", category="session")
                return False

    def dump_retries(self, failed_tasks: List[Any], async_write: bool = True) -> bool:
        """Dumps failed retry tasks to disk in compact JSON to keep memory low during long sessions."""
        if not failed_tasks:
            return False

        def _do_dump(tasks_list):
            with self._write_lock:
                try:
                    raw_tasks = [t.to_dict() if hasattr(t, "to_dict") else t for t in tasks_list]
                    tmp = f"{self.retry_spillover_file}.tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump(raw_tasks, f, separators=(',', ':'), ensure_ascii=False)
                        f.flush()
                    os.replace(tmp, self.retry_spillover_file)
                    self._set_retry_cache(raw_tasks)
                    logger.debug(f"Spilled {len(raw_tasks)} failed retry tasks to disk.", category="session")
                    return True
                except Exception as ex:
                    logger.debug(f"Failed to spill retry tasks to disk: {ex}", category="session")
                    return False

        if async_write:
            self._async_executor.submit(_do_dump, list(failed_tasks))
            return True
        return _do_dump(failed_tasks)

    def _retry_file_key(self):
        try:
            st = os.stat(self.retry_spillover_file)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def _set_retry_cache(self, data: List[Dict[str, Any]]) -> None:
        def is_404(item) -> bool:
            msg = item.get("error_msg") if isinstance(item, dict) else getattr(item, "error_msg", "")
            return "404" in str(msg or "").lower()
        counts = (len(data), sum(1 for item in data if not is_404(item)))
        with self._cache_lock:
            self._retry_cache_key = self._retry_file_key()
            self._retry_cache = list(data)
            self._retry_counts = counts

    def load_retries(self) -> List[Dict[str, Any]]:
        """Loads spilled retry tasks from disk (from memory when the file hasn't changed)."""
        key = self._retry_file_key()
        with self._cache_lock:
            if key == self._retry_cache_key:
                return list(self._retry_cache)
        with self._write_lock:
            if not os.path.exists(self.retry_spillover_file):
                self._set_retry_cache([])
                return []
            try:
                with open(self.retry_spillover_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data = data if isinstance(data, list) else []
                self._set_retry_cache(data)
                return list(data)
            except Exception as ex:
                logger.debug(f"Could not load retry spillover file: {ex}", category="session")
                return []

    def retry_counts(self, wait: bool = True) -> Optional[Tuple[int, int]]:
        """(failed files saved for Retry Failed, of which not 404). With wait=False (the window thread)
        it never reads the file: when the saved list changed it returns None, reads it in the
        background and calls on_retries_loaded when done."""
        key = self._retry_file_key()
        with self._cache_lock:
            if key == self._retry_cache_key:
                return self._retry_counts
        if key is None:                      # no saved failed files: nothing to read
            self._set_retry_cache([])
            with self._cache_lock:
                return self._retry_counts
        if wait:
            self.load_retries()
            with self._cache_lock:
                return self._retry_counts
        if not self._retry_loading.is_set():
            self._retry_loading.set()

            def _job():
                try:
                    self.load_retries()
                finally:
                    self._retry_loading.clear()
                    if self.on_retries_loaded:
                        try:
                            self.on_retries_loaded()
                        except Exception:
                            pass
            threading.Thread(target=_job, name="RetryListLoad", daemon=True).start()
        return None

    def retry_counts_cached(self) -> Tuple[int, int]:
        """The last known counts, whatever the file holds now."""
        with self._cache_lock:
            return self._retry_counts

    def clear_retries(self) -> bool:
        """Removes the retry spillover file when user manually clears retries or upon app exit."""
        with self._write_lock:
            if os.path.exists(self.retry_spillover_file):
                try:
                    os.remove(self.retry_spillover_file)
                    self._set_retry_cache([])
                    logger.debug("Retry spillover file removed.", category="session")
                    return True
                except Exception as ex:
                    logger.debug(f"Could not remove retry spillover file: {ex}", category="session")
            self._set_retry_cache([])
            return False

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Loads the saved queue: {status, saved_at, settings, batches, tasks, summary} or None.
        A journal that can't be read is reported and treated as empty.
        """
        self._import_legacy_journal()
        data = safe_journal_call(self.journal.load)
        if not data:
            return None
        data["summary"] = safe_journal_call(lambda: self.journal.summary(self._format_size)) or self.build_summary(data["tasks"])
        return data

    def _read_legacy_json(self) -> Optional[Dict[str, Any]]:
        """The JSON journal of older versions (its .bak if the main file is damaged)."""
        for path in (self.legacy_journal_file, self.bak_file):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data and isinstance(data, dict) and data.get("tasks"):
                        return data
                except Exception as e:
                    logger.warning(f"Old recovery journal {os.path.basename(path)} couldn't be read ({e}).", category="session")
        return None

    def _import_legacy_journal(self) -> None:
        """Moves an older version's JSON journal into the database, once."""
        if self._legacy_checked:
            return
        self._legacy_checked = True
        if not (os.path.exists(self.legacy_journal_file) or os.path.exists(self.bak_file)):
            return
        data = self._read_legacy_json()
        try:
            if data and not safe_journal_call(self.journal.has_rows, False):
                self.journal.sync(data.get("tasks") or [], data.get("batches"), data.get("settings"),
                                  data.get("status") or "interrupted",
                                  artist_of=self.artist_name, platform_of=self._platform_of)
                logger.info(f"Recovery journal moved to the new format ({len(data.get('tasks') or [])} file(s)).",
                            category="session")
        finally:
            # The old files are kept, renamed ("….migrated"), never deleted: nothing can be lost if the
            # move needs fixing later. Renamed, they aren't imported again.
            for fpath in (self.legacy_journal_file, self.bak_file):
                if os.path.exists(fpath):
                    try:
                        os.replace(fpath, fpath + ".migrated")
                    except OSError:
                        pass

    def has_unfinished_session(self) -> bool:
        """Checks whether a valid unfinished recovery session exists. Only files that never got their
        turn count: failed files are kept for Retry Failed (counting them brought the prompt back on
        every start, and Resume couldn't do anything about them, #28). Asked of the database without
        loading the queue."""
        self._import_legacy_journal()
        return bool(safe_journal_call(self.journal.has_unfinished, False))

    def get_recovery_summary(self) -> Optional[Dict[str, Any]]:
        """Returns the high-level summary dict for displaying in the recovery modal (counted by the
        database, without loading the queue)."""
        self._import_legacy_journal()
        return safe_journal_call(lambda: self.journal.summary(self._format_size))

    def discard_recovery(self) -> bool:
        """Empties the crash journal (and removes an old version's JSON journal files)."""
        purged = False
        with self._write_lock:
            self._generation += 1      # background writes queued before this are dropped
            try:
                purged = bool(safe_journal_call(self.journal.has_rows, False))
                safe_journal_call(self.journal.clear)
            except Exception as e:
                logger.warning(f"Could not empty the recovery journal: {e}", category="session")
            # (an older version's JSON journal is imported on first use and kept as "….migrated")
            if os.path.exists(self.tmp_file):
                try:
                    os.remove(self.tmp_file)
                except OSError:
                    pass
        if purged:
            logger.info("Recovery journal files discarded.", category="session")
        return purged

