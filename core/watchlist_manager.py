"""
Watchlist Manager
Tracks followed artists, persists last-download metadata, and detects new posts
for the Watchlist tab. All network operations are intended to be called from a
background thread to keep the GUI responsive.
"""

import json
import os
import datetime
import shutil
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

from core.logger import logger
from core.watchlist_store import WatchlistStore


@dataclass
class WatchlistEntry:
    url: str
    service: str
    domain: str
    user_id: str
    creator_name: str
    last_post_id: str = ""
    last_post_date: str = ""   # ISO date string: "YYYY-MM-DD"
    added_at: str = ""
    auto_check: bool = True
    new_post_count: int = 0    # transient — not persisted, set after checks
    download_dir: str = ""
    download_dirs: List[str] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    ignored_post_ids: List[str] = field(default_factory=list)
    cached_new_posts: List[Dict[str, Any]] = field(default_factory=list)  # transient — discovered new posts
    # Posts from the last-download date that are already downloaded. Sites with non-numeric post IDs
    # (Boosty, cum.st) can't tell which same-day post came first, so they're remembered by ID.
    cutoff_day_ids: List[str] = field(default_factory=list)
    last_checked_at: float = 0.0   # when a check last finished for this creator (time.time())
    custom_folder: bool = False    # download_dir was chosen by the user: used as it is, never moved

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        # The manager is told which creators changed, so a save writes only those
        hook = self.__dict__.get("_changed")
        if hook is not None and name[0] != "_":
            hook(self, name)

    def store_fields(self) -> Dict[str, Any]:
        """What's saved for this creator, apart from its settings and the updates found."""
        dirs = list(self.download_dirs or [])
        if self.download_dir and self.download_dir not in dirs:
            dirs.insert(0, self.download_dir)
        d = {
            "url": self.url, "service": self.service, "domain": self.domain, "user_id": self.user_id,
            "creator_name": self.creator_name, "last_post_id": self.last_post_id,
            "last_post_date": self.last_post_date, "added_at": self.added_at, "auto_check": self.auto_check,
            "download_dir": self.download_dir or (dirs[0] if dirs else ""), "download_dirs": dirs,
            "ignored_post_ids": list(self.ignored_post_ids or []),
            "cutoff_day_ids": list(self.cutoff_day_ids or []),
        }
        if self.last_checked_at:
            d["last_checked_at"] = self.last_checked_at
        if self.custom_folder:
            d["custom_folder"] = True
        return d

    def to_dict(self) -> Dict[str, Any]:
        # Sync primary download_dir with the first valid entry in download_dirs
        if self.download_dirs and not self.download_dir:
            self.download_dir = self.download_dirs[0]
        elif self.download_dir and self.download_dir not in self.download_dirs:
            self.download_dirs.insert(0, self.download_dir)

        d = asdict(self)
        d.pop("new_post_count", None)   # don't persist transient field
        d.pop("cached_new_posts", None) # don't persist transient field
        if not d.get("last_checked_at"):
            d.pop("last_checked_at", None)
        if not d.get("custom_folder"):
            d.pop("custom_folder", None)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WatchlistEntry":
        from core.path_translation import localize_path      # (saved on the other system: D:\ ↔ /mnt/d)
        single_dir = localize_path(str(d.get("download_dir", "") or "").strip())
        if single_dir:
            single_dir = os.path.normpath(single_dir)     # ("D:/x" and "D:\x" showed as two locations)
        raw_dirs = d.get("download_dirs", [])
        if not isinstance(raw_dirs, list):
            raw_dirs = [raw_dirs] if raw_dirs else []
        raw_dirs = [localize_path(str(p)) for p in raw_dirs]
        norm_dirs = [os.path.normpath(str(p)) for p in raw_dirs if str(p).strip()]
        if single_dir:
            norm_single = os.path.normpath(single_dir)
            if norm_single not in norm_dirs:
                norm_dirs.insert(0, norm_single)

        return cls(
            url=d.get("url", ""),
            service=d.get("service", ""),
            domain=d.get("domain", ""),
            user_id=d.get("user_id", ""),
            creator_name=d.get("creator_name", ""),
            last_post_id=d.get("last_post_id", ""),
            last_post_date=d.get("last_post_date", ""),
            added_at=d.get("added_at", ""),
            auto_check=bool(d.get("auto_check", True)),
            new_post_count=0,
            download_dir=single_dir or (norm_dirs[0] if norm_dirs else ""),
            download_dirs=norm_dirs,
            options=d.get("options", {}) if isinstance(d.get("options"), dict) else {},
            ignored_post_ids=list(d.get("ignored_post_ids", [])) if isinstance(d.get("ignored_post_ids"), list) else [],
            cached_new_posts=[],
            cutoff_day_ids=[str(x) for x in d.get("cutoff_day_ids", [])] if isinstance(d.get("cutoff_day_ids"), list) else [],
            last_checked_at=float(d.get("last_checked_at") or 0.0),
            custom_folder=bool(d.get("custom_folder", False)),
        )



def post_id_is_newer(post_id: str, than_id: str) -> bool:
    """Post IDs grow over time on these sites. For IDs that aren't plain numbers the order is unknown,
    so this is False (it used to be True for any other ID, which made every post from the last
    download's date "new" again on every check for Boosty / cum.st creators)."""
    a, b = str(post_id or "").strip(), str(than_id or "").strip()
    if a.isdigit() and b.isdigit():
        return int(a) > int(b)
    return False


def _day(date_str: str) -> str:
    s = str(date_str or "")
    return s.split("T")[0] if "T" in s else s[:10]


def trim_post(p: Dict[str, Any]) -> Dict[str, Any]:
    """The part of a found post that's kept across restarts: what the updates list shows (title,
    date, file count) and what marking it done / ignored needs (id, dates). Downloads fetch the post
    again."""
    out = {k: p[k] for k in ("id", "title", "published", "added") if p.get(k) not in (None, "")}

    def _f(f):
        return {k: f[k] for k in ("name", "path", "storageKey") if f.get(k)}
    f = p.get("file")
    if isinstance(f, dict) and (f.get("path") or f.get("storageKey")):
        out["file"] = _f(f)
    atts = [_f(a) for a in (p.get("attachments") or []) if isinstance(a, dict) and (a.get("path") or a.get("storageKey"))]
    if atts:
        out["attachments"] = atts
    return out


def _keep_aside(path: str) -> Optional[str]:
    """Renames an imported file to "<name>.migrated" (never deleted: it can still be opened or put
    back by hand). An earlier .migrated file isn't overwritten."""
    target = path + ".migrated"
    n = 2
    while os.path.exists(target):
        target = f"{path}.migrated-{n}"
        n += 1
    try:
        os.replace(path, target)
        return target
    except OSError as e:
        logger.warning(f"Couldn't rename {os.path.basename(path)} after importing it: {e}", category="watchlist")
        return None


class _TrackedList(list):
    """The creator list. The manager hears of every change to it (its lookup index and its saves
    follow the list, also when code edits the list directly)."""
    __slots__ = ("_on_change",)

    def __init__(self, items=(), on_change=None):
        super().__init__(items)
        self._on_change = on_change

    def _changed(self):
        if self._on_change is not None:
            self._on_change()

    def append(self, x):
        super().append(x)
        self._changed()

    def extend(self, xs):
        super().extend(xs)
        self._changed()

    def insert(self, i, x):
        super().insert(i, x)
        self._changed()

    def remove(self, x):
        super().remove(x)
        self._changed()

    def pop(self, *a):
        r = super().pop(*a)
        self._changed()
        return r

    def clear(self):
        super().clear()
        self._changed()

    def sort(self, *a, **kw):
        super().sort(*a, **kw)
        self._changed()

    def reverse(self):
        super().reverse()
        self._changed()

    def __setitem__(self, i, x):
        super().__setitem__(i, x)
        self._changed()

    def __delitem__(self, i):
        super().__delitem__(i)
        self._changed()

    def __iadd__(self, xs):
        r = super().__iadd__(xs)
        self._changed()
        return r


class WatchlistManager:
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
        if not self.background_saves:
            self._write_pending()
            return
        if self._writer is None or not self._writer.is_alive():
            self._writer = threading.Thread(target=self._writer_loop, name="WatchlistWriter", daemon=True)
            self._writer.start()
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
    ) -> bool:
        """
        Add or update a watchlist entry.
        Returns True if a new entry was created, False if updated.
        """
        with self._lock:
            return self._add_entry_locked(url, creator_name, user_id, service, domain, last_post_id,
                                          last_post_date, auto_check, download_dir, options)

    def _add_entry_locked(self, url, creator_name, user_id, service, domain, last_post_id,
                          last_post_date, auto_check, download_dir, options) -> bool:
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
                        if os.path.exists(existing.download_dir) and not os.path.exists(new_dir):
                            try:
                                os.rename(existing.download_dir, new_dir)
                                logger.info(f"Auto-migrated folder '{base}' -> '{os.path.basename(new_dir)}'", category="watchlist")
                            except Exception as e:
                                logger.debug(f"Could not rename folder on disk: {e}", category="watchlist")
                        existing.download_dir = new_dir
                elif download_dir and not existing.download_dir:
                    existing.download_dir = download_dir
            elif download_dir and not existing.download_dir:
                existing.download_dir = download_dir
            if url:
                existing.url = url
            if options:
                existing.options = options
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
                options=options or {},
                ignored_post_ids=[],
                cached_new_posts=[],
                cutoff_day_ids=[str(last_post_id)] if last_post_id else [],
            )
            self.entries.insert(0, entry)
            self._adopt(entry, at_head=True)
            self.save(entry)
            logger.info(
                f"Added to watchlist: {creator_name!r} [{service}] (last post: {last_post_date or 'unknown'})",
                category="watchlist"
            )
            return True

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
        existing = self._find(user_id, service)
        if existing:
            existing.auto_check = enabled
            self.save(existing)

    def set_download_dir(self, user_id: str, service: str, download_dir: str) -> bool:
        """Set or update the custom download directory for an entry."""
        existing = self._find(user_id, service)
        if existing:
            norm = os.path.normpath(download_dir) if download_dir else ""
            existing.download_dir = norm
            if norm:
                if not hasattr(existing, "download_dirs") or not isinstance(existing.download_dirs, list):
                    existing.download_dirs = []
                if norm not in existing.download_dirs:
                    existing.download_dirs.insert(0, norm)
            self.save(existing)
            return True
        return False

    def add_download_dir(self, user_id: str, service: str, new_dir: str) -> bool:
        """Add a path to an artist's download_dirs list if not present."""
        existing = self._find(user_id, service)
        if existing and new_dir:
            norm = os.path.normpath(new_dir)
            if not hasattr(existing, "download_dirs") or not isinstance(existing.download_dirs, list):
                existing.download_dirs = [existing.download_dir] if existing.download_dir else []
            if norm not in existing.download_dirs:
                existing.download_dirs.append(norm)
            if not existing.download_dir:
                existing.download_dir = norm
            self.save(existing)
            return True
        return False

    def remove_download_dir(self, user_id: str, service: str, target_dir: str) -> bool:
        """Remove a path from an artist's download_dirs list (e.g. when consolidated by user)."""
        existing = self._find(user_id, service)
        if existing and target_dir:
            norm = os.path.normpath(target_dir).lower()
            if hasattr(existing, "download_dirs") and isinstance(existing.download_dirs, list):
                existing.download_dirs = [d for d in existing.download_dirs if os.path.normpath(d).lower() != norm]
            if existing.download_dir and os.path.normpath(existing.download_dir).lower() == norm:
                existing.download_dir = existing.download_dirs[0] if existing.download_dirs else ""
            self.save(existing)
            return True
        return False

    def get_download_dirs(self, user_id: str, service: str) -> List[str]:
        """Returns all registered paths for an artist."""
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
        existing = self._find(user_id, service)
        if not existing:
            return False, "Artist not found in watchlist"

        normalized = self.normalize_date(raw_date_str)
        if normalized is None:
            return False, f"Invalid date format: '{raw_date_str}'. Please use YYYY-MM-DD (e.g. 2024-05-18), DD/MM/YYYY, or Month DD, YYYY."

        existing.last_post_date = normalized
        existing.last_post_id = ""  # Reset cutoff post id
        existing.cutoff_day_ids = []
        existing.new_post_count = 0
        existing.cached_new_posts = []
        self.save()
        logger.info(
            f"Watchlist: updated last download date for {existing.creator_name!r} [{service}] to {normalized or 'Never'}.",
            category="watchlist"
        )
        return True, normalized


    def ignore_post(self, user_id: str, service: str, post_id: str) -> bool:
        """Add post_id to ignored list for an entry."""
        pid = str(post_id).strip()
        if not pid:
            return False
        existing = self._find(user_id, service)
        if existing:
            if pid not in existing.ignored_post_ids:
                existing.ignored_post_ids.append(pid)
            existing.cached_new_posts = [p for p in existing.cached_new_posts if str(p.get("id")) != pid]
            existing.new_post_count = len(existing.cached_new_posts)
            self.save(existing)
            return True
        return False

    def unignore_post(self, user_id: str, service: str, post_id: str) -> bool:
        """Remove post_id from ignored list for an entry."""
        pid = str(post_id).strip()
        existing = self._find(user_id, service)
        if existing and pid in existing.ignored_post_ids:
            existing.ignored_post_ids.remove(pid)
            self.save(existing)
            return True
        return False

    def unignore_all(self, user_id: str, service: str) -> bool:
        """Clear all ignored posts for an entry."""
        existing = self._find(user_id, service)
        if existing and existing.ignored_post_ids:
            existing.ignored_post_ids = []
            self.save(existing)
            return True
        return False


    # ── New-Post Detection ─────────────────────────────────────────────────────

    def get_posts_since(self, entry: WatchlistEntry, api_client, raise_on_error: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch posts for an entry and return only those published strictly after entry.last_post_date.
        Paginates page-by-page until the cutoff date/id is reached or all posts are fetched,
        ensuring the exact number of new posts is discovered without artificial caps.
        Results are sorted oldest-first so callers can download in order.
        Runs synchronously — call from a background thread.
        raise_on_error: a page that couldn't be fetched raises instead of ending the list early (the
        creator's updates found earlier are then kept).
        """
        from core.parser import KemonoURLParser

        parsed = KemonoURLParser.parse(entry.url)
        if not parsed.is_valid:
            logger.warning(
                f"Watchlist: could not parse URL for {entry.creator_name!r}: {entry.url}",
                category="watchlist"
            )
            return []

        cutoff = entry.last_post_date  # "YYYY-MM-DD" or ISO string
        if cutoff and "T" in cutoff:
            cutoff = cutoff.split("T")[0]
        elif cutoff:
            cutoff = cutoff[:10]
        cutoff_id = str(entry.last_post_id or "")
        known_day_ids = {str(i) for i in getattr(entry, "cutoff_day_ids", []) or []}
        if cutoff_id:
            known_day_ids.add(cutoff_id)

        # Auto-heal numeric name if needed
        if (entry.creator_name == entry.user_id or not entry.creator_name) and hasattr(api_client, "resolve_creator_name"):
            try:
                resolved = api_client.resolve_creator_name(parsed)
                if resolved and resolved != entry.user_id:
                    self.add_entry(
                        url=entry.url,
                        creator_name=resolved,
                        user_id=entry.user_id,
                        service=entry.service,
                        domain=entry.domain
                    )
            except Exception:
                pass

        new_posts: List[Dict[str, Any]] = []
        current_page = 1
        page_size = 50
        largest_page = 0
        max_pages = 100  # Up to 5,000 posts to support deep updates while preventing infinite loops

        while current_page <= max_pages:
            try:
                page_posts = api_client.fetch_user_posts(
                    parsed, page_start=current_page, page_end=current_page, page_size=page_size
                )
            except Exception as e:
                if raise_on_error:
                    raise
                logger.warning(
                    f"Watchlist check failed on page {current_page} for {entry.creator_name!r}: {e}",
                    category="watchlist"
                )
                break
            failed = getattr(api_client, "last_fetch_failed", None)
            if raise_on_error and callable(failed) and failed() is True:
                raise RuntimeError(f"page {current_page} of the post list couldn't be fetched")

            if not page_posts:
                break

            page_oldest_pub = None
            found_cutoff_id_on_page = False

            for p in page_posts:
                pub = p.get("published") or p.get("added") or ""
                if isinstance(pub, (int, float)):
                    try:
                        pub = datetime.datetime.fromtimestamp(pub).strftime("%Y-%m-%d")
                    except Exception:
                        pub = ""
                elif isinstance(pub, str) and "T" in pub:
                    pub = pub.split("T")[0]
                elif isinstance(pub, str):
                    pub = pub[:10]

                post_id = str(p.get("id", ""))

                # Track oldest date seen on this page to decide if we should paginate further
                if pub and (page_oldest_pub is None or pub < page_oldest_pub):
                    page_oldest_pub = pub

                if cutoff:
                    if pub and pub > cutoff:
                        # Strictly newer: always include
                        new_posts.append(p)
                    elif pub == cutoff:
                        if post_id and post_id == cutoff_id:
                            # This is exactly the last-seen post — skip it, mark cutoff reached
                            found_cutoff_id_on_page = True
                        elif post_id in known_day_ids:
                            pass   # already downloaded on that day
                        elif post_id and cutoff_id and post_id.isdigit() and cutoff_id.isdigit():
                            if int(post_id) > int(cutoff_id):
                                new_posts.append(p)
                            # else: already downloaded (older post on same day)
                        elif post_id and getattr(entry, "cutoff_day_ids", None):
                            # Non-numeric IDs: anything not in the downloaded list for that day is new
                            new_posts.append(p)
                        elif not cutoff_id and not known_day_ids:
                            # When cutoff date is set but cutoff_id is empty, posts on cutoff date are already covered
                            pass
                        elif not cutoff_id or post_id_is_newer(post_id, cutoff_id):
                            # Same date, posted after the last download — new
                            new_posts.append(p)
                        # Same date but older than the last download: already downloaded.
                    # pub < cutoff: skip this post (too old)
                else:
                    # No cutoff at all — include everything
                    new_posts.append(p)

            # Stop paginating if:
            # 1. This was the last page (fewer posts than page_size)
            # 2. The oldest post on this page is already before the cutoff (no need to go deeper)
            # 3. We found the exact cutoff post id on this page
            largest_page = max(largest_page, len(page_posts))
            if len(page_posts) < largest_page:
                break
            if cutoff and page_oldest_pub and page_oldest_pub < cutoff:
                break
            if found_cutoff_id_on_page:
                break

            current_page += 1

        # Sort oldest first for ordered downloading
        new_posts.sort(key=lambda p: (
            p.get("published") or p.get("added") or "0",
            str(p.get("id", "0"))
        ))

        # Filter out ignored posts and update cached_new_posts
        ignored_set = set(str(pid) for pid in getattr(entry, "ignored_post_ids", []))
        unignored_posts = [p for p in new_posts if str(p.get("id", "")) not in ignored_set]
        entry.cached_new_posts = unignored_posts
        entry.new_post_count = len(unignored_posts)

        return unignored_posts

    def to_json_list(self) -> str:
        """Return JSON string of all entries (for QML consumption)."""
        data = []
        for e in self.entries:
            data.append({
                "url": e.url,
                "creatorName": e.creator_name,
                "service": e.service,
                "domain": e.domain,
                "userId": e.user_id,
                "lastPostDate": e.last_post_date,
                "lastPostId": e.last_post_id,
                "addedAt": e.added_at,
                "autoCheck": e.auto_check,
                "newPostCount": e.new_post_count,
                "downloadDir": e.download_dir,
                "ignoredCount": len(getattr(e, "ignored_post_ids", [])),
                "cachedNewPosts": [
                    {
                        "id": str(p.get("id", "")),
                        "title": (p.get("title") or "Untitled").strip(),
                        "published": str(p.get("published") or p.get("added") or "")[:10],
                        "fileCount": (1 if (p.get("file") and isinstance(p.get("file"), dict) and (p.get("file").get("path") or p.get("file").get("storageKey"))) else 0) + len([a for a in (p.get("attachments") or []) if isinstance(a, dict) and (a.get("path") or a.get("storageKey"))]),
                    }
                    for p in getattr(e, "cached_new_posts", [])
                ],
            })
        return json.dumps(data, ensure_ascii=False)

