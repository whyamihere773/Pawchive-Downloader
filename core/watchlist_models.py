"""
Watchlist Entry Data Model, Post Comparison Helpers & Tracked List
Decomposed from core/watchlist_manager.py to keep modules cohesive and under 1,000 lines.
"""

from dataclasses import asdict, dataclass, field
import os
from typing import Any, Dict, List, Optional

from core.filter_options import normalize_post_date_ymd, normalize_post_timestamp_str
from core.logger import logger


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
    auto_check: bool = False
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
    is_favorite: bool = False      # creator is favorited by user (syncs with Pawchive favorites)

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
            "is_favorite": bool(self.is_favorite),
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
            auto_check=bool(d.get("auto_check", False)),
            new_post_count=0,
            download_dir=single_dir or (norm_dirs[0] if norm_dirs else ""),
            download_dirs=norm_dirs,
            options=d.get("options", {}) if isinstance(d.get("options"), dict) else {},
            ignored_post_ids=list(d.get("ignored_post_ids", [])) if isinstance(d.get("ignored_post_ids"), list) else [],
            cached_new_posts=[],
            cutoff_day_ids=[str(x) for x in d.get("cutoff_day_ids", [])] if isinstance(d.get("cutoff_day_ids"), list) else [],
            last_checked_at=float(d.get("last_checked_at") or 0.0),
            custom_folder=bool(d.get("custom_folder", False)),
            is_favorite=bool(d.get("is_favorite", False)),
        )



def post_id_is_newer(post_id: str, than_id: str) -> bool:
    """Post IDs grow over time on these sites. For IDs that aren't plain numbers the order is unknown,
    so this is False (it used to be True for any other ID, which made every post from the last
    download's date "new" again on every check for Boosty / cum.st creators)."""
    a, b = str(post_id or "").strip(), str(than_id or "").strip()
    if a.isascii() and a.isdigit() and b.isascii() and b.isdigit():
        return int(a) > int(b)
    return False


def _day(date_str: Any) -> str:
    return normalize_post_date_ymd(date_str, fallback="")


def trim_post(p: Dict[str, Any]) -> Dict[str, Any]:
    """The part of a found post that's kept across restarts: what the updates list shows (title,
    date, file count) and what marking it done / ignored needs (id, dates). Downloads fetch the post
    again."""
    out: Dict[str, Any] = {}
    if p.get("id") not in (None, ""):
        out["id"] = p["id"]
    if p.get("title") not in (None, ""):
        out["title"] = p["title"]
    raw_pub = p.get("published") if p.get("published") not in (None, "") else p.get("createdAt")
    if raw_pub not in (None, ""):
        out["published"] = normalize_post_timestamp_str(raw_pub, fallback=str(raw_pub))
    if p.get("added") not in (None, ""):
        out["added"] = normalize_post_timestamp_str(p["added"], fallback=str(p["added"]))

    def _f(f):
        return {k: f[k] for k in ("name", "path", "storageKey") if f.get(k)}
    f = p.get("file")
    if isinstance(f, dict) and (f.get("path") or f.get("storageKey")):
        out["file"] = _f(f)
    atts = [_f(a) for a in (p.get("attachments") or p.get("media") or []) if isinstance(a, dict) and (a.get("path") or a.get("storageKey"))]
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


