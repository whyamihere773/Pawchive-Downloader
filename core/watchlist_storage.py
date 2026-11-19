"""
Watchlist Change Tracking, SQLite Persistence, Legacy Migration & Backup Mixin
Decomposed from core/watchlist_manager.py to keep modules cohesive and under 1,000 lines.
"""

import json
import os
import shutil
import threading
import time
from typing import Dict, List, Optional

from core.logger import logger
from core.watchlist_models import (
    WatchlistEntry,
    _day,
    _keep_aside,
    post_id_is_newer,
    trim_post,
)


class WatchlistStorageMixin:
    """Handles dirty tracking, incremental SQLite saves, legacy JSON import/merge, and recovery."""

    def _entry_changed(self, e: WatchlistEntry, name: str) -> None:
        with self._lock:
            rid = e.__dict__.get("_rid")
            if rid is not None:
                self._dirty[rid] = e
            if name in ("user_id", "service"):
                self._index_stale = True

    def _adopt(self, e: WatchlistEntry, at_head: bool = False, rid: Optional[int] = None,
               seq: Optional[int] = None) -> None:
        """Gives a creator its row id and position and starts tracking its changes."""
        if e.__dict__.get("_rid") is None:
            if rid is None:
                rid = self._next_rid
            self._next_rid = max(self._next_rid, rid + 1)
            if seq is None:
                if at_head:
                    self._seq_min -= 1
                    seq = self._seq_min
                else:
                    self._seq_max += 1
                    seq = self._seq_max
            self._seq_min = min(self._seq_min, seq)
            self._seq_max = max(self._seq_max, seq)
            object.__setattr__(e, "_rid", rid)
            object.__setattr__(e, "_seq", seq)
            self._dirty[rid] = e
        object.__setattr__(e, "_changed", self._entry_changed)

    def _sync_members_locked(self, force: bool = False) -> None:
        """The list is what counts: creators put into or taken out of it directly (older code, tests)
        are noticed here, given row ids, and saved or removed."""
        ents = self._entries
        if not force and not self._index_stale and ents is self._index_src:
            return
        index: Dict[tuple, WatchlistEntry] = {}
        current: Dict[int, WatchlistEntry] = {}
        for i, e in enumerate(ents):
            if e.__dict__.get("_rid") is None or e.__dict__.get("_changed") is None:
                self._adopt(e, at_head=(i == 0 and len(ents) > 1))
            rid = e.__dict__["_rid"]
            if rid in current and current[rid] is not e:
                object.__setattr__(e, "_rid", None)          # a copy of another creator's object
                self._adopt(e)
                rid = e.__dict__["_rid"]
            current[rid] = e
            index.setdefault(((e.user_id or "").strip().lower(), (e.service or "").strip().lower()), e)
        for rid in self._members.keys() - current.keys():
            self._deleted.add(rid)
            self._dirty.pop(rid, None)
        self._members = current
        self._index = index
        self._index_src = ents
        self._index_len = len(ents)
        self._index_stale = False

    # ── Persistence ────────────────────────────────────────────────────────────

    def load(self):
        """Load entries from disk. Safe to call multiple times."""
        with self._lock:
            self._reset_tracking()
            entries, source = self._read_storage()
            self.entries = entries
            self._sync_members_locked(force=True)
            self._dirty.clear()
            self._deleted.clear()
            if source in ("json", "restored"):
                self._write_all = True
                self._save_gen += 1
        if source == "json":
            self._import_finished()
        elif source == "restored":
            self._write_pending(force=True)
        elif source == "db+json":
            self._merge_legacy_json()
        if entries:
            logger.info(f"Watchlist loaded: {len(entries)} artist(s) tracked.", category="watchlist")
            self._backup_in_background()

    def _reset_tracking(self) -> None:
        self._dirty = {}
        self._deleted = set()
        self._members = {}
        self._index_src = None
        self._index_stale = True
        self._write_all = False
        self._next_rid, self._seq_min, self._seq_max = 1, 0, 0

    def _entries_from_rows(self, rows) -> List[WatchlistEntry]:
        entries = []
        for rid, pos, d, new_posts in rows:
            e = WatchlistEntry.from_dict(d)
            e.cached_new_posts = list(new_posts or [])
            e.new_post_count = len(e.cached_new_posts)
            self._adopt(e, rid=rid, seq=pos)
            entries.append(e)
        return entries

    def _read_storage(self):
        """(entries, where they came from): the database; its backup if it's damaged; else an older
        version's watchlist.json."""
        damaged = False
        if self.store.exists():
            for attempt in ("db", "backup"):
                try:
                    entries = self._entries_from_rows(self.store.load())
                    if attempt == "backup":
                        logger.warning(f"Watchlist restored from its backup ({len(entries)} artist(s)).",
                                       category="watchlist")
                    has_json = os.path.exists(self.watchlist_file)
                    if entries or not has_json:
                        return entries, ("db+json" if has_json else "db")
                    break                         # empty database next to a watchlist.json: import it
                except Exception as e:
                    damaged = True
                    self._next_rid, self._seq_min, self._seq_max = 1, 0, 0
                    kept = self.store.set_aside()
                    logger.error(f"The watchlist database couldn't be read ({e}); it was kept as "
                                 f"{os.path.basename(kept) if kept else os.path.basename(self.db_file)}.",
                                 category="watchlist")
                    bak = self.db_file + ".bak"
                    if attempt == "db" and kept and os.path.exists(bak):
                        try:
                            shutil.copy2(bak, self.db_file)
                            continue
                        except OSError:
                            pass
                    break
        legacy = self._read_legacy_json(self.watchlist_file)
        if legacy is not None:
            for i, e in enumerate(legacy):
                self._adopt(e, seq=i)
            return legacy, "json"
        if damaged:
            # Database damaged and no backup: the last imported watchlist.json is better than nothing
            newest = None
            for name in os.listdir(self.config_dir):
                if name.startswith("watchlist.json.migrated"):
                    path = os.path.join(self.config_dir, name)
                    if newest is None or os.path.getmtime(path) > os.path.getmtime(newest):
                        newest = path
            legacy = self._read_legacy_json(newest) if newest else None
            if legacy:
                logger.warning(f"Watchlist restored from {os.path.basename(newest)} "
                               f"(changes made after it was imported are missing).", category="watchlist")
                for i, e in enumerate(legacy):
                    self._adopt(e, seq=i)
                return legacy, "restored"
        return [], "empty"

    @staticmethod
    def _read_legacy_json(path: str) -> Optional[List[WatchlistEntry]]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_entries = data.get("entries", []) if isinstance(data, dict) else []
            return [WatchlistEntry.from_dict(e) for e in raw_entries if isinstance(e, dict)]
        except Exception as e:
            logger.warning(f"Could not load {os.path.basename(path)}: {e}", category="watchlist")
            return None

    def _import_finished(self) -> None:
        """Writes the imported watchlist.json to the database; only then is the file renamed."""
        if self._write_pending(force=True):
            kept = _keep_aside(self.watchlist_file)
            logger.info(f"Watchlist moved to the new format ({len(self.entries)} artist(s)); the old file is "
                        f"kept as {os.path.basename(kept) if kept else 'watchlist.json'}.", category="watchlist")

    def _merge_legacy_json(self) -> None:
        """A watchlist.json next to the database (an older version was used in between): artists
        missing from the database are added and download progress is carried over; nothing is lost."""
        legacy = self._read_legacy_json(self.watchlist_file)
        if legacy is None:
            return
        added = 0
        with self._lock:
            for je in legacy:
                existing = self._find(je.user_id, je.service)
                if existing is None:
                    self.entries.append(je)
                    added += 1
                elif je.last_post_date or je.last_post_id:
                    self._advance_cutoff(existing, je.last_post_id, je.last_post_date, je.cutoff_day_ids)
            self._save_gen += 1
        if self._write_pending(force=True):
            kept = _keep_aside(self.watchlist_file)
            logger.info(f"Merged a newer watchlist.json ({added} new artist(s)); the file is kept as "
                        f"{os.path.basename(kept) if kept else 'watchlist.json'}.", category="watchlist")

    def _backup_in_background(self) -> None:
        """A daily copy of watchlist.db (watchlist.db.bak), used if the database is ever damaged."""
        bak = self.db_file + ".bak"
        try:
            if os.path.exists(bak) and time.time() - os.path.getmtime(bak) < 24 * 3600:
                return
        except OSError:
            pass
        if not self.store.exists():
            return
        threading.Thread(target=self.store.backup, name="WatchlistBackup", daemon=True).start()

    def save(self, *changed: WatchlistEntry, full: bool = False):
        """Persist changes (crash-safe: SQLite commits are all-or-nothing). Creators changed in place
        (a list edited rather than replaced) can be passed in; full=True writes every creator."""
        with self._lock:
            for e in changed:
                rid = getattr(e, "__dict__", {}).get("_rid")
                if rid is not None:
                    self._dirty[rid] = e
            if full:
                self._write_all = True
            self._save_gen += 1
            bg = bool(self.background_saves)
            if bg and (self._writer is None or not self._writer.is_alive()):
                self._writer = threading.Thread(target=self._writer_loop, name="WatchlistWriter", daemon=True)
                self._writer.start()
        if not bg:
            self._write_pending()
            return
        self._save_wanted.set()

    def flush(self) -> None:
        """Writes changes that are still waiting for the background writer."""
        if self._saved_gen < self._save_gen:
            self._write_pending(force=True)

    def _writer_loop(self) -> None:
        while True:
            self._save_wanted.wait()
            time.sleep(0.4)                 # changes made together are written together
            self._save_wanted.clear()
            if not self._write_pending() and self._saved_gen < self._save_gen:
                time.sleep(min(30.0, 2.0 * self._write_failures))   # disk full / locked: try again later
                self._save_wanted.set()

    def _row_for(self, rid: int, e: WatchlistEntry) -> tuple:
        return (rid, e.__dict__.get("_seq", 0), e.store_fields(), dict(e.options or {}),
                [trim_post(p) for p in (e.cached_new_posts or [])])

    def _write_pending(self, force: bool = False) -> bool:
        """Writes the creators changed since the last save. True when everything is saved."""
        with self._write_lock:
            gen = self._save_gen
            if gen <= self._saved_gen and not force:
                return True
            with self._lock:
                write_all = self._write_all
                self._sync_members_locked(force=write_all)
                self._write_all = False
                if write_all:
                    dirty = dict(self._members)
                else:
                    dirty = {rid: e for rid, e in self._dirty.items() if rid in self._members}
                self._dirty.clear()
                deleted = set(self._deleted)
                self._deleted.clear()
            if not dirty and not deleted and not write_all:
                self._saved_gen = max(self._saved_gen, gen)
                return True
            try:
                rows = []
                for rid, e in dirty.items():
                    for _ in range(3):
                        try:
                            rows.append(self._row_for(rid, e))
                            break
                        except RuntimeError:
                            continue                    # changed meanwhile; read it again
                    else:
                        with self._lock:
                            rows.append(self._row_for(rid, e))
                self.store.write(rows, deleted - dirty.keys(), replace_all=write_all)
                self._saved_gen = max(self._saved_gen, gen)
                if self._write_failures:
                    logger.info("Watchlist saved again.", category="watchlist")
                self._write_failures = 0
                return True
            except Exception as e:
                with self._lock:                        # kept for the next try
                    for rid, ent in dirty.items():
                        self._dirty.setdefault(rid, ent)
                    self._deleted |= deleted
                    self._write_all = self._write_all or write_all
                self._write_failures += 1
                if self._write_failures in (1, 10, 100):
                    logger.error(f"Failed to save watchlist: {e}", category="watchlist")
                return False

    @staticmethod
    def _advance_cutoff(e: WatchlistEntry, post_id: str, post_date: str, day_ids: Optional[List[str]] = None):
        """Moves the "downloaded up to" point forward (never back) and remembers which posts of
        that day are already downloaded."""
        post_id = str(post_id or "")
        day = _day(post_date)
        ids = {str(i) for i in (day_ids or []) if str(i)}
        if post_id:
            ids.add(post_id)
        cur_day = _day(e.last_post_date)
        existing_ids = set(getattr(e, "cutoff_day_ids", []) or [])
        if day and (not cur_day or day > cur_day):
            e.last_post_date = day
            e.last_post_id = post_id
            e.cutoff_day_ids = sorted(ids)
        elif day and day == cur_day:
            if post_id and (not e.last_post_id or post_id_is_newer(post_id, e.last_post_id)):
                e.last_post_id = post_id
            e.cutoff_day_ids = sorted(existing_ids | ids)
        elif not day and post_id and not e.last_post_id:
            e.last_post_id = post_id
