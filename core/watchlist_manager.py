"""
Watchlist Manager
Tracks followed artists, persists last-download metadata, and detects new posts
for the Watchlist tab. All network operations are intended to be called from a
background thread to keep the GUI responsive.
"""

import json
import os
import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

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
    auto_check: bool = True
    new_post_count: int = 0    # transient — not persisted, set after checks
    download_dir: str = ""
    download_dirs: List[str] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    ignored_post_ids: List[str] = field(default_factory=list)
    cached_new_posts: List[Dict[str, Any]] = field(default_factory=list)  # transient — discovered new posts

    def to_dict(self) -> Dict[str, Any]:
        # Sync primary download_dir with the first valid entry in download_dirs
        if self.download_dirs and not self.download_dir:
            self.download_dir = self.download_dirs[0]
        elif self.download_dir and self.download_dir not in self.download_dirs:
            self.download_dirs.insert(0, self.download_dir)

        d = asdict(self)
        d.pop("new_post_count", None)   # don't persist transient field
        d.pop("cached_new_posts", None) # don't persist transient field
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WatchlistEntry":
        single_dir = str(d.get("download_dir", "") or "").strip()
        raw_dirs = d.get("download_dirs", [])
        if not isinstance(raw_dirs, list):
            raw_dirs = [raw_dirs] if raw_dirs else []
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
        )



class WatchlistManager:
    """
    Manages persistent watchlist of followed artists.
    Thread-safe for reads; writes should be serialized on the main thread
    (or protected externally if called from workers).
    """

    VERSION = 1

    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.watchlist_file = os.path.join(config_dir, "watchlist.json")
        self.entries: List[WatchlistEntry] = []

    # ── Persistence ────────────────────────────────────────────────────────────

    def load(self):
        """Load entries from disk. Safe to call multiple times."""
        if not os.path.exists(self.watchlist_file):
            self.entries = []
            return

        try:
            with open(self.watchlist_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_entries = data.get("entries", []) if isinstance(data, dict) else []
            self.entries = [WatchlistEntry.from_dict(e) for e in raw_entries if isinstance(e, dict)]
            logger.info(
                f"Watchlist loaded: {len(self.entries)} artist(s) tracked.",
                category="watchlist"
            )
        except Exception as e:
            logger.warning(f"Could not load watchlist.json: {e}", category="watchlist")
            self.entries = []

    def save(self):
        """Persist current entries to disk."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            data = {
                "version": self.VERSION,
                "entries": [e.to_dict() for e in self.entries]
            }
            with open(self.watchlist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save watchlist: {e}", category="watchlist")

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def _find(self, user_id: str, service: str) -> Optional[WatchlistEntry]:
        """Return existing entry or None."""
        uid = user_id.strip().lower()
        svc = service.strip().lower()
        for e in self.entries:
            if e.user_id.lower() == uid and e.service.lower() == svc:
                return e
        return None

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
        existing = self._find(user_id, service)
        if existing:
            # Update last download info but don't touch auto_check preference
            if last_post_date and (not existing.last_post_date or last_post_date >= existing.last_post_date):
                existing.last_post_id = last_post_id or existing.last_post_id
                existing.last_post_date = last_post_date
            elif last_post_id and not existing.last_post_id:
                existing.last_post_id = last_post_id
            # Update name in case it resolved better
            if creator_name and creator_name != user_id:
                old_was_numeric = (existing.creator_name == user_id or not existing.creator_name)
                existing.creator_name = creator_name
                # If existing download_dir was tied to numeric user_id, auto-repair folder name
                if existing.download_dir and old_was_numeric:
                    clean_target = os.path.normpath(existing.download_dir)
                    base = os.path.basename(clean_target)
                    expected_numeric = f"{user_id} [{service}]"
                    if base.lower() == expected_numeric.lower() or base == user_id:
                        parent_dir = os.path.dirname(clean_target)
                        from core.filter_engine import FilterEngine
                        clean_c = FilterEngine.clean_filesystem_text(creator_name, max_len=80, fallback="creator")
                        new_dir = os.path.join(parent_dir, f"{clean_c} [{service}]")
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
            self.save()
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
            )
            self.entries.insert(0, entry)
            self.save()
            logger.info(
                f"Added to watchlist: {creator_name!r} [{service}] (last post: {last_post_date or 'unknown'})",
                category="watchlist"
            )
            return True

    def remove_entry(self, user_id: str, service: str) -> bool:
        """Remove entry by (user_id, service). Returns True if removed."""
        existing = self._find(user_id, service)
        if existing:
            self.entries.remove(existing)
            self.save()
            logger.info(f"Removed from watchlist: {existing.creator_name!r} [{service}]", category="watchlist")
            return True
        return False

    def update_last_download(self, user_id: str, service: str, post_id: str, post_date: str):
        """Update last-downloaded post metadata after a successful download."""
        existing = self._find(user_id, service)
        if existing:
            existing.last_post_id = post_id
            existing.last_post_date = post_date
            existing.new_post_count = 0
            existing.cached_new_posts = []
            self.save()

    def set_auto_check(self, user_id: str, service: str, enabled: bool):
        """Toggle the per-entry auto_check flag."""
        existing = self._find(user_id, service)
        if existing:
            existing.auto_check = enabled
            self.save()

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
            self.save()
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
            self.save()
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
            self.save()
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
            self.save()
            return True
        return False

    def unignore_post(self, user_id: str, service: str, post_id: str) -> bool:
        """Remove post_id from ignored list for an entry."""
        pid = str(post_id).strip()
        existing = self._find(user_id, service)
        if existing and pid in existing.ignored_post_ids:
            existing.ignored_post_ids.remove(pid)
            self.save()
            return True
        return False

    def unignore_all(self, user_id: str, service: str) -> bool:
        """Clear all ignored posts for an entry."""
        existing = self._find(user_id, service)
        if existing and existing.ignored_post_ids:
            existing.ignored_post_ids = []
            self.save()
            return True
        return False


    # ── New-Post Detection ─────────────────────────────────────────────────────

    def get_posts_since(self, entry: WatchlistEntry, api_client) -> List[Dict[str, Any]]:
        """
        Fetch posts for an entry and return only those published strictly after entry.last_post_date.
        Paginates page-by-page until the cutoff date/id is reached or all posts are fetched,
        ensuring the exact number of new posts is discovered without artificial caps.
        Results are sorted oldest-first so callers can download in order.
        Runs synchronously — call from a background thread.
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
        max_pages = 100  # Up to 5,000 posts to support deep updates while preventing infinite loops

        while current_page <= max_pages:
            try:
                page_posts = api_client.fetch_user_posts(
                    parsed, page_start=current_page, page_end=current_page, page_size=page_size
                )
            except Exception as e:
                logger.warning(
                    f"Watchlist check failed on page {current_page} for {entry.creator_name!r}: {e}",
                    category="watchlist"
                )
                break

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
                        else:
                            # Same date but a different post — include (new post on same day)
                            new_posts.append(p)
                    # pub < cutoff: skip this post (too old)
                else:
                    # No cutoff at all — include everything
                    new_posts.append(p)

            # Stop paginating if:
            # 1. This was the last page (fewer posts than page_size)
            # 2. The oldest post on this page is already before the cutoff (no need to go deeper)
            # 3. We found the exact cutoff post id on this page
            if len(page_posts) < page_size:
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

