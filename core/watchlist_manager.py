"""
Watchlist Manager
Tracks followed artists, persists last-download metadata, and detects new posts
for the Watchlist tab. All network operations are intended to be called from a
background thread to keep the GUI responsive.
"""

import datetime
import os
import threading
from typing import Any, Dict, List, Optional

from core.logger import logger
from core.watchlist_models import (
    WatchlistEntry,
    _TrackedList,
    _day,
    _keep_aside,
    post_id_is_newer,
    trim_post,
)
from core.watchlist_posts import WatchlistPostsMixin
from core.watchlist_storage import WatchlistStorageMixin
from core.watchlist_store import WatchlistStore


class WatchlistManager(WatchlistStorageMixin, WatchlistPostsMixin):
    """
    Manages persistent watchlist of followed artists.
    Thread-safe for reads; writes should be serialized on the main thread
    (or protected externally if called from workers).
    """

    VERSION = 1

    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        # The watchlist lives in watchlist.db (one row per creator; a save writes only the creators
        # that changed). Older versions' watchlist.json is imported once and kept as .migrated.
        self.watchlist_file = os.path.join(config_dir, "watchlist.json")
        self.db_file = os.path.join(config_dir, "watchlist.db")
        self.store = WatchlistStore(self.db_file)
        self._index_stale = True
        self._entries: _TrackedList = _TrackedList((), self._list_changed)
        # Checks run in background threads while the window edits entries
        self._lock = threading.RLock()
        # With background_saves on (the app), save() only marks the watchlist changed and a writer
        # thread writes it, so the window never waits for the disk. A burst of changes is written
        # once; flush() writes what's pending (on close).
        self.background_saves = False
        self._save_gen = 0
        self._saved_gen = 0
        self._save_wanted = threading.Event()
        self._write_lock = threading.Lock()
        self._writer: Optional[threading.Thread] = None
        self._write_failures = 0
        # Change tracking: creators get a row id; the ones changed since the last save are written
        self._next_rid = 1
        self._seq_min = 0
        self._seq_max = 0
        self._dirty: Dict[int, WatchlistEntry] = {}
        self._deleted: set = set()
        self._members: Dict[int, WatchlistEntry] = {}       # rid -> creator, as of the last look at the list
        self._write_all = False
        # (user id, service) -> creator: finding a creator was a walk through the whole list
        self._index: Dict[tuple, WatchlistEntry] = {}
        self._index_src: Optional[list] = None
        self._index_len = -1
        self._index_stale = True

    @property
    def entries(self) -> List[WatchlistEntry]:
        return self._entries

    @entries.setter
    def entries(self, value) -> None:
        self._entries = _TrackedList(value or (), self._list_changed)
        self._index_stale = True

    def _list_changed(self) -> None:
        self._index_stale = True

    # ── Change tracking ────────────────────────────────────────────────────────


    # ── CRUD ───────────────────────────────────────────────────────────────────

    def _find(self, user_id: str, service: str) -> Optional[WatchlistEntry]:
        """Return existing entry or None."""
        with self._lock:
            self._sync_members_locked()
            return self._index.get(((user_id or "").strip().lower(), (service or "").strip().lower()))

    def get_all(self) -> List[WatchlistEntry]:
        with self._lock:
            return list(self.entries)

    def add_entry(
        self,
        url: str,
        creator_name: str,
        user_id: str,
        service: str,
        domain: str,
        last_post_id: str = "",
        last_post_date: str = "",
        auto_check: bool = True,
        download_dir: str = "",
        options: Optional[Dict[str, Any]] = None,
        is_favorite: bool = False,
        custom_folder: Optional[bool] = None,
    ) -> bool:
        """
        Add or update a watchlist entry.
        Returns True if a new entry was created, False if updated.
        """
        with self._lock:
            return self._add_entry_locked(url, creator_name, user_id, service, domain, last_post_id,
                                          last_post_date, auto_check, download_dir, options, is_favorite, custom_folder)

    def _add_entry_locked(self, url, creator_name, user_id, service, domain, last_post_id,
                          last_post_date, auto_check, download_dir, options, is_favorite: bool = False,
                          custom_folder: Optional[bool] = None) -> bool:
        existing = self._find(user_id, service)
        if existing:
            # Update last download info but don't touch auto_check preference
            if last_post_date or last_post_id:
                self._advance_cutoff(existing, last_post_id, last_post_date)
            # Update name in case it resolved better
            if creator_name and creator_name != user_id:
                old_was_numeric = (existing.creator_name == user_id or not existing.creator_name)
                existing.creator_name = creator_name
                # If existing download_dir was tied to numeric user_id, auto-repair folder name
                if existing.download_dir and old_was_numeric:
                    clean_target = os.path.normpath(existing.download_dir)
                    base = os.path.basename(clean_target)
                    from core.folder_naming import is_creator_folder, creator_folder
                    if is_creator_folder(base, user_id, service):
                        parent_dir = os.path.dirname(clean_target)
                        from core.filter_engine import FilterEngine
                        clean_c = FilterEngine.clean_filesystem_text(creator_name, max_len=80, fallback="creator")
                        new_dir = os.path.join(parent_dir, creator_folder(clean_c, service))
                        old_dir = existing.download_dir
                        if os.path.exists(old_dir) and not os.path.exists(new_dir):
                            try:
                                os.rename(old_dir, new_dir)
                                logger.info(f"Auto-migrated folder '{base}' -> '{os.path.basename(new_dir)}'", category="watchlist")
                            except Exception as e:
                                logger.debug(f"Could not rename folder on disk: {e}", category="watchlist")
                        existing.download_dir = new_dir
                        if hasattr(existing, "download_dirs") and isinstance(existing.download_dirs, list):
                            old_key = os.path.normcase(os.path.normpath(old_dir))
                            norm_new = os.path.normpath(new_dir)
                            new_key = os.path.normcase(norm_new)
                            updated_dirs = []
                            seen_keys = set()
                            for d in existing.download_dirs:
                                if not d:
                                    continue
                                d_key = os.path.normcase(os.path.normpath(d))
                                rep = norm_new if d_key == old_key else d
                                rep_key = new_key if d_key == old_key else d_key
                                if rep_key not in seen_keys:
                                    seen_keys.add(rep_key)
                                    updated_dirs.append(rep)
                            if new_key not in seen_keys:
                                updated_dirs.insert(0, norm_new)
                            existing.download_dirs = updated_dirs
                elif download_dir and not existing.download_dir:
                    existing.download_dir = download_dir
            elif download_dir and not existing.download_dir:
                existing.download_dir = download_dir
            if custom_folder is True:
                existing.custom_folder = True
                if download_dir:
                    norm_dir = os.path.normpath(download_dir)
                    existing.download_dir = norm_dir
                    if not hasattr(existing, "download_dirs") or not isinstance(existing.download_dirs, list):
                        existing.download_dirs = []
                    if norm_dir not in existing.download_dirs:
                        existing.download_dirs.insert(0, norm_dir)
            elif custom_folder is False:
                existing.custom_folder = False
            if url:
                existing.url = url
            if options:
                existing_is_custom = isinstance(getattr(existing, "options", None), dict) and bool(existing.options.get("use_custom_settings"))
                incoming_is_custom = isinstance(options, dict) and bool(options.get("use_custom_settings"))
                if not existing_is_custom or incoming_is_custom:
                    existing.options = options
            if is_favorite:
                existing.is_favorite = True
            self.save(existing)
            return False
        else:
            entry = WatchlistEntry(
                url=url,
                service=service,
                domain=domain,
                user_id=user_id,
                creator_name=creator_name,
                last_post_id=last_post_id,
                last_post_date=last_post_date,
                added_at=datetime.datetime.now().isoformat(timespec="seconds"),
                auto_check=auto_check,
                download_dir=download_dir,
                custom_folder=bool(custom_folder),
                options=options or {},
                ignored_post_ids=[],
                cached_new_posts=[],
                cutoff_day_ids=[str(last_post_id)] if last_post_id else [],
                is_favorite=bool(is_favorite),
            )
            self.entries.insert(0, entry)
            self._adopt(entry, at_head=True)
            self.save(entry)
            logger.info(
                f"Added to watchlist: {creator_name!r} [{service}] (last post: {last_post_date or 'unknown'})",
                category="watchlist"
            )
            return True

    def set_favorite(self, user_id: str, service: str, is_favorite: bool) -> bool:
        """Sets favorite status for a creator in the watchlist. Returns True if found and updated."""
        with self._lock:
            existing = self._find(user_id, service)
            if existing:
                if existing.is_favorite != is_favorite:
                    existing.is_favorite = is_favorite
                    self.save(existing)
                return True
            return False

    def add_or_update_favorite_creator(
        self,
        user_id: str,
        service: str,
        creator_name: str,
        domain: str = "pawchive.pw",
        url: str = "",
        is_favorite: bool = True,
    ) -> WatchlistEntry:
        """Ensures a favorited creator exists in Watchlist and is marked as favorite."""
        with self._lock:
            existing = self._find(user_id, service)
            if existing:
                existing.is_favorite = is_favorite
                if domain and ("cum.st" in domain or "cumst" in domain):
                    existing.domain = "cum.st"
                if creator_name and (existing.creator_name == user_id or not existing.creator_name):
                    existing.creator_name = creator_name
                if url:
                    existing.url = url
                elif not existing.url:
                    if "cum.st" in existing.domain or "cumst" in existing.domain:
                        existing.url = f"https://cum.st/creators/{service}/{user_id}"
                    else:
                        existing.url = f"https://{existing.domain}/{service}/user/{user_id}"
                self.save(existing)
                return existing
            else:
                if not url:
                    if "cum.st" in domain or "cumst" in domain:
                        url = f"https://cum.st/creators/{service}/{user_id}"
                    else:
                        url = f"https://{domain}/{service}/user/{user_id}"
                entry = WatchlistEntry(
                    url=url,
                    service=service,
                    domain=domain,
                    user_id=user_id,
                    creator_name=creator_name or user_id,
                    added_at=datetime.datetime.now().isoformat(timespec="seconds"),
                    auto_check=True,
                    is_favorite=is_favorite,
                )
                self.entries.insert(0, entry)
                self._adopt(entry, at_head=True)
                self.save(entry)
                logger.info(f"Added favorite creator to watchlist: {creator_name!r} [{service}]", category="watchlist")
                return entry

    def remove_entry(self, user_id: str, service: str) -> bool:
        """Remove entry by (user_id, service). Returns True if removed."""
        with self._lock:
            existing = self._find(user_id, service)
            if not existing:
                return False
            self.entries.remove(existing)
            self.save()
        logger.info(f"Removed from watchlist: {existing.creator_name!r} [{service}]", category="watchlist")
        return True

    def update_last_download(self, user_id: str, service: str, post_id: str, post_date: str,
                             day_ids: Optional[List[str]] = None):
        """Update last-downloaded post metadata after a successful download."""
        with self._lock:
            existing = self._find(user_id, service)
            if existing:
                self._advance_cutoff(existing, post_id, post_date, day_ids)
                cutoff_day = _day(existing.last_post_date)
                done = {str(i) for i in existing.cutoff_day_ids}
                # Posts still waiting in the review drawer stay there unless they're now covered
                existing.cached_new_posts = [
                    p for p in existing.cached_new_posts
                    if _day(p.get("published") or p.get("added") or "") > cutoff_day
                    or (_day(p.get("published") or p.get("added") or "") == cutoff_day and str(p.get("id", "")) not in done
                        and not (str(p.get("id", "")).isdigit() and existing.last_post_id.isdigit()
                                 and int(p.get("id")) <= int(existing.last_post_id)))
                ]
                existing.new_post_count = len(existing.cached_new_posts)
                self.save(existing)

    def resolve_posts(
        self,
        user_id: str,
        service: str,
        post_ids: Optional[List[str]] = None,
        latest_post_id: str = "",
        latest_post_date: str = "",
        day_ids: Optional[List[str]] = None
    ) -> bool:
        """
        Mark new posts as resolved (e.g. after download, or when files were already archived / on disk).
        If post_ids is None: marks all pending updates as resolved, resetting new_post_count to 0.
        If post_ids is given: removes those specific posts from cached_new_posts and updates new_post_count.
        Advances last_post_date and last_post_id safely without regression.
        """
        with self._lock:
            existing = self._find(user_id, service)
            if not existing:
                return False

            if post_ids:
                p_set = set(str(pid) for pid in post_ids)
                existing.cached_new_posts = [
                    p for p in getattr(existing, "cached_new_posts", [])
                    if str(p.get("id", "")) not in p_set
                ]
                existing.new_post_count = len(existing.cached_new_posts)
                if existing.new_post_count == 0 and (latest_post_date or latest_post_id):
                    self._advance_cutoff(existing, latest_post_id, latest_post_date, day_ids)
            else:
                if latest_post_date or latest_post_id:
                    self._advance_cutoff(existing, latest_post_id, latest_post_date, day_ids)
                existing.new_post_count = 0
                existing.cached_new_posts = []

            if existing.new_post_count <= 0:
                existing.new_post_count = 0
                existing.cached_new_posts = []

            self.save(existing)
            return True

    def set_auto_check(self, user_id: str, service: str, enabled: bool):
        """Toggle the per-entry auto_check flag."""
        with self._lock:
            existing = self._find(user_id, service)
            if existing:
                existing.auto_check = enabled
        if existing:
            self.save(existing)

    def set_all_auto_check(self, enabled: bool) -> int:
        """Set the auto_check flag for all entries."""
        with self._lock:
            changed = []
            for entry in self.entries:
                if getattr(entry, "auto_check", True) != enabled:
                    entry.auto_check = enabled
                    changed.append(entry)
            if changed:
                self.save(*changed)
            return len(changed)

    def set_download_dir(self, user_id: str, service: str, download_dir: str,
                         custom_folder: Optional[bool] = None) -> bool:
        """Set or update the download directory for a watchlist artist."""
        with self._lock:
            existing = self._find(user_id, service)
            if not existing:
                return False
            norm = os.path.normpath(download_dir) if download_dir else ""
            existing.download_dir = norm
            if norm:
                if not hasattr(existing, "download_dirs") or not isinstance(existing.download_dirs, list):
                    existing.download_dirs = []
                if norm not in existing.download_dirs:
                    existing.download_dirs.insert(0, norm)
            if custom_folder is not None:
                existing.custom_folder = bool(custom_folder)
            self.save(existing)
            return True

    def update_entry_settings(
        self,
        user_id: str,
        service: str,
        *,
        auto_check: Optional[bool] = None,
        options: Optional[Dict[str, Any]] = None,
        last_post_date: Optional[str] = None,
    ) -> bool:
        """Update auto-check, per-creator options, or cutoff date for a watchlist entry."""
        with self._lock:
            existing = self._find(user_id, service)
            if not existing:
                return False
            if auto_check is not None:
                existing.auto_check = bool(auto_check)
            if options is not None:
                existing.options = dict(options)
            if last_post_date is not None:
                norm_date = self.normalize_date(last_post_date)
                if norm_date is not None and norm_date != existing.last_post_date:
                    existing.last_post_date = norm_date
                    existing.last_post_id = ""
                    existing.cutoff_day_ids = []
                    if not norm_date:
                        existing.cached_new_posts = []
                        existing.new_post_count = 0
            self.save(existing)
            return True

    def reset_for_redownload(self, user_id: str, service: str, keep_dir: str = "") -> bool:
        """Clear download cutoff/cache before a full destructive re-download, keeping settings and folder."""
        with self._lock:
            existing = self._find(user_id, service)
            if not existing:
                return False
            existing.last_post_id = ""
            existing.last_post_date = ""
            existing.cutoff_day_ids = []
            existing.cached_new_posts = []
            existing.new_post_count = 0
            if keep_dir:
                norm_keep = os.path.normpath(keep_dir)
                existing.download_dir = norm_keep
                existing.download_dirs = [norm_keep]
            self.save(existing)
            return True

    def add_download_dir(self, user_id: str, service: str, new_dir: str) -> bool:
        """Add a path to an artist's download_dirs list if not present."""
        if not new_dir:
            return False
        with self._lock:
            existing = self._find(user_id, service)
            if not existing:
                return False
            norm = os.path.normpath(new_dir)
            if not hasattr(existing, "download_dirs") or not isinstance(existing.download_dirs, list):
                existing.download_dirs = [existing.download_dir] if existing.download_dir else []
            if norm not in existing.download_dirs:
                existing.download_dirs.append(norm)
            if not existing.download_dir:
                existing.download_dir = norm
        self.save(existing)
        return True

    def remove_download_dir(self, user_id: str, service: str, target_dir: str) -> bool:
        """Remove a path from an artist's download_dirs list (e.g. when consolidated by user)."""
        if not target_dir:
            return False
        with self._lock:
            existing = self._find(user_id, service)
            if not existing:
                return False
            norm = os.path.normpath(target_dir).lower()
            if hasattr(existing, "download_dirs") and isinstance(existing.download_dirs, list):
                existing.download_dirs = [d for d in existing.download_dirs if os.path.normpath(d).lower() != norm]
            if existing.download_dir and os.path.normpath(existing.download_dir).lower() == norm:
                existing.download_dir = existing.download_dirs[0] if existing.download_dirs else ""
        self.save(existing)
        return True

    def get_download_dirs(self, user_id: str, service: str) -> List[str]:
        """Returns all registered paths for an artist."""
        with self._lock:
            existing = self._find(user_id, service)
            if existing:
                dirs = list(getattr(existing, "download_dirs", []) or [])
                if existing.download_dir and existing.download_dir not in dirs:
                    dirs.insert(0, existing.download_dir)
                return dirs
            return []

    @staticmethod
    def normalize_date(s: str) -> Optional[str]:
        """
        Convert any user-provided or API date string into canonical 'YYYY-MM-DD'.
        Supports:
          - ISO dates: 'YYYY-MM-DD', 'YYYY-MM-DDTHH:MM:SS', 'YYYY/MM/DD', 'YYYY.MM.DD'
          - Slash/dash/dot variants: 'DD/MM/YYYY', 'MM/DD/YYYY', 'DD-MM-YYYY', etc.
          - Compact digits: 'YYYYMMDD'
          - Written months: '19 Aug 2026', 'August 19, 2026', '2026 Aug 19'
          - Relative terms: 'today', 'yesterday'
          - Clear terms: '', 'never', 'none', 'clear', 'null', 'reset', '-' -> returns ''
          - Unix timestamp in seconds or milliseconds
        Returns:
          Canonical 'YYYY-MM-DD' string, or '' if cleared, or None if invalid.
        """
        s = (s or "").strip()
        if not s or s.lower() in ("never", "none", "clear", "null", "reset", "-", "never downloaded"):
            return ""
        if s.lower() == "today":
            return datetime.date.today().strftime("%Y-%m-%d")
        if s.lower() == "yesterday":
            return (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        # Check for numeric unix timestamp (10 digits for seconds, 13 for ms)
        if s.isdigit() and len(s) in (10, 13):
            try:
                ts = int(s) / 1000.0 if len(s) == 13 else int(s)
                return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            except Exception:
                pass

        # Check for compact 8-digit date: YYYYMMDD
        if s.isdigit() and len(s) == 8:
            try:
                y = int(s[:4])
                m = int(s[4:6])
                d = int(s[6:8])
                dt = datetime.date(y, m, d)
                if 1990 <= dt.year <= 2100:
                    return dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        # Try dateutil.parser if available (strict mode without fuzzy false positives)
        try:
            import dateutil.parser
            dt = dateutil.parser.parse(s, fuzzy=False)
            if 1990 <= dt.year <= 2100:
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

        # Fallback standard datetime formats
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y.%m.%d", "%d.%m.%Y", "%B %d, %Y", "%d %B %Y", "%b %d, %Y", "%d %b %Y"):
            try:
                dt = datetime.datetime.strptime(s, fmt)
                if 1990 <= dt.year <= 2100:
                    return dt.strftime("%Y-%m-%d")
            except Exception:
                continue

        return None

    def set_last_post_date(self, user_id: str, service: str, raw_date_str: str) -> tuple:
        """
        Manually update or reset the last_post_date for an entry.
        Normalizes any input format into canonical 'YYYY-MM-DD' (or '' if cleared).
        Returns (success: bool, normalized_date_or_error: str).
        """
        normalized = self.normalize_date(raw_date_str)
        with self._lock:
            existing = self._find(user_id, service)
            if not existing:
                return False, "Artist not found in watchlist"
            if normalized is None:
                return False, f"Invalid date format: '{raw_date_str}'. Please use YYYY-MM-DD (e.g. 2024-05-18), DD/MM/YYYY, or Month DD, YYYY."
            existing.last_post_date = normalized
            existing.last_post_id = ""  # Reset cutoff post id
            existing.cutoff_day_ids = []
            existing.new_post_count = 0
            existing.cached_new_posts = []
            cname = existing.creator_name
        self.save(existing)
        logger.info(
            f"Watchlist: updated last download date for {cname!r} [{service}] to {normalized or 'Never'}.",
            category="watchlist"
        )
        return True, normalized

    def ignore_post(self, user_id: str, service: str, post_id: str) -> bool:
        """Add post_id to ignored list for an entry."""
        pid = str(post_id).strip()
        if not pid:
            return False
        with self._lock:
            existing = self._find(user_id, service)
            if not existing:
                return False
            if pid not in existing.ignored_post_ids:
                existing.ignored_post_ids.append(pid)
            existing.cached_new_posts = [p for p in existing.cached_new_posts if str(p.get("id")) != pid]
            existing.new_post_count = len(existing.cached_new_posts)
        self.save(existing)
        return True

    def unignore_post(self, user_id: str, service: str, post_id: str) -> bool:
        """Remove post_id from ignored list for an entry."""
        pid = str(post_id).strip()
        with self._lock:
            existing = self._find(user_id, service)
            if not (existing and pid in existing.ignored_post_ids):
                return False
            existing.ignored_post_ids.remove(pid)
        self.save(existing)
        return True

    def unignore_all(self, user_id: str, service: str) -> bool:
        """Clear all ignored posts for an entry."""
        with self._lock:
            existing = self._find(user_id, service)
            if not (existing and existing.ignored_post_ids):
                return False
            existing.ignored_post_ids = []
        self.save(existing)
        return True
