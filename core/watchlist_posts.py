"""
Watchlist New-Post Discovery & QML Serialization Mixin
Decomposed from core/watchlist_manager.py to keep modules cohesive and under 1,000 lines.
"""

import datetime
import json
import threading
from typing import Any, Dict, List, Optional

from core.logger import logger
from core.watchlist_models import WatchlistEntry, post_id_is_newer


class WatchlistPostsMixin:
    """Paginates creator APIs to discover new posts and serializes entries for QML."""

    def get_posts_since(
        self,
        entry: WatchlistEntry,
        api_client,
        raise_on_error: bool = False,
        page_start: int = 1,
        page_end: int = 999999,
        cancel_event: Optional[threading.Event] = None
    ) -> List[Dict[str, Any]]:
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

        # Auto-heal creator name if missing, numeric, or if duplicate names exist across distinct accounts
        snapshot_entries = self.get_all() if hasattr(self, "get_all") else list(self.entries)
        has_duplicate_name = any(
            e is not entry and e.service.lower() == entry.service.lower() and e.creator_name and e.creator_name.lower() == entry.creator_name.lower()
            for e in snapshot_entries
        )
        if (entry.creator_name == entry.user_id or not entry.creator_name or has_duplicate_name) and hasattr(api_client, "resolve_creator_name"):
            try:
                resolved = api_client.resolve_creator_name(parsed)
                if resolved and resolved != entry.user_id and resolved != entry.creator_name:
                    old_name = entry.creator_name
                    self.add_entry(
                        url=entry.url,
                        creator_name=resolved,
                        user_id=entry.user_id,
                        service=entry.service,
                        domain=entry.domain
                    )
                    logger.info(
                        f"Auto-healed creator name for [{entry.service}] {entry.user_id}: {old_name!r} -> {resolved!r}",
                        category="watchlist"
                    )
            except Exception:
                pass

        new_posts: List[Dict[str, Any]] = []
        if page_start < 1:
            page_start = 1
        if page_end < page_start:
            page_end = page_start
        current_page = page_start
        page_size = 50
        largest_page = 0
        max_pages = min(100, page_end)  # Up to page_end (capped at 100 pages / 5,000 posts)

        while current_page <= max_pages:
            if cancel_event and cancel_event.is_set():
                break
            try:
                page_posts = api_client.fetch_user_posts(
                    parsed, page_start=current_page, page_end=current_page, page_size=page_size,
                    cancel_event=cancel_event
                )
            except TypeError:
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
            page_new_count_before = len(new_posts)

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
            largest_page = max(largest_page, len(page_posts))
            if len(page_posts) < largest_page:
                break

            # 2. We found the exact cutoff post id on this page
            if found_cutoff_id_on_page:
                break

            # 3. The oldest post on this page is already before the cutoff (no need to go deeper)
            if cutoff and page_oldest_pub and page_oldest_pub < cutoff:
                break

            # 4. Oldest post on this page is on cutoff date and cutoff_id is empty (cutoff date is already covered)
            if cutoff and not cutoff_id and page_oldest_pub and page_oldest_pub <= cutoff:
                break

            # 5. On page 1 (or any page): if no new posts were found on this entire page, the artist
            #    has not posted anything newer than the cutoff date. Since posts are reverse chronological,
            #    older pages cannot contain newer posts either. Stop immediately (no further page requests).
            if cutoff and len(new_posts) == page_new_count_before:
                logger.debug(
                    f"Watchlist: {entry.creator_name!r} up to date (no posts newer than {cutoff} on page {current_page}) — stopping check.",
                    category="watchlist"
                )
                break

            current_page += 1

        # Sort oldest first for ordered downloading (normalize mixed int/float timestamps and ISO strings)
        def _post_sort_key(p: Dict[str, Any]):
            raw_d = p.get("published") or p.get("added") or ""
            if isinstance(raw_d, (int, float)):
                try:
                    d_norm = datetime.datetime.fromtimestamp(raw_d).strftime("%Y-%m-%dT%H:%M:%S")
                except Exception:
                    d_norm = "0"
            else:
                d_norm = str(raw_d).strip() or "0"
            raw_id = str(p.get("id", "0") or "0")
            id_key = (0, int(raw_id), raw_id) if raw_id.isdigit() else (1, 0, raw_id)
            return (d_norm, id_key)

        new_posts.sort(key=_post_sort_key)

        # Filter out ignored posts and update cached_new_posts
        ignored_set = set(str(pid) for pid in getattr(entry, "ignored_post_ids", []))
        unignored_posts = [p for p in new_posts if str(p.get("id", "")) not in ignored_set]
        entry.cached_new_posts = unignored_posts
        entry.new_post_count = len(unignored_posts)

        return unignored_posts

    def to_json_list(self) -> str:
        """Return JSON string of all entries (for QML consumption)."""
        def _post_file_count(p: dict) -> int:
            f = p.get("file")
            atts = [a for a in (p.get("attachments") or []) if isinstance(a, dict) and (a.get("path") or a.get("storageKey"))]
            f_path = (f.get("path") or f.get("storageKey") or "").strip().lower() if isinstance(f, dict) else ""
            att_paths = {(a.get("path") or a.get("storageKey") or "").strip().lower() for a in atts}
            unique = len(att_paths)
            if f_path and f_path not in att_paths:
                unique += 1
            return unique or (1 if f else len(atts))

        data = []
        snapshot_entries = self.get_all() if hasattr(self, "get_all") else list(self.entries)
        for e in snapshot_entries:
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
                        "title": (p.get("title") or p.get("captionText") or p.get("caption") or "Untitled").strip(),
                        "published": str(p.get("published") or p.get("added") or "")[:10],
                        "fileCount": _post_file_count(p),
                    }
                    for p in getattr(e, "cached_new_posts", [])
                ],
            })
        return json.dumps(data, ensure_ascii=False)
