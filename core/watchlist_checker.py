"""
Checking the whole Watchlist for new posts, built for big watchlists.

- Sites are checked in parallel, each site one creator at a time (the same pace per site as before).
- Creators who post most recently are checked first.
- A check that was stopped or cut off continues where it left off next time (creators already checked
  in that round are skipped), as long as it was started less than a day ago.
- Pawchive lists every creator with the time of their last update: creators that haven't changed since
  they were last checked are skipped (one request instead of one per creator). Everyone still gets a
  full check at least once a week, and skipped creators keep the updates found earlier.
- Each creator's result is reported as soon as it's known.
"""

import threading
import time
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.logger import logger

ROUND_MAX_AGE = 24 * 3600            # an unfinished round older than this starts over
UNCHANGED_MARGIN = 24 * 3600         # "updated" must be this much older than the last check to skip
FULL_CHECK_EVERY = 7 * 24 * 3600     # checked in full at least this often, whatever the listing says
LISTING_MIN_CREATORS = 30            # fewer creators on a site: checking them is cheaper than the listing


def site_of(entry) -> str:
    domain = (getattr(entry, "domain", "") or "").lower().strip()
    if domain:
        return domain
    url = getattr(entry, "url", "") or ""
    return url.split("://")[-1].split("/")[0].lower()


def activity_day(entry) -> str:
    """Sorted in reverse: most recently active first, creators never downloaded from last ("")."""
    return str(getattr(entry, "last_post_date", "") or "")[:10]


class WatchlistChecker:
    def __init__(self, manager, check_one: Callable[[Any], int],
                 on_result: Optional[Callable[[Any, int], None]] = None,
                 on_progress: Optional[Callable[[int, int], None]] = None,
                 listing: Optional[Callable[[str], Optional[Dict[Tuple[str, str], float]]]] = None,
                 max_parallel_sites: int = 4):
        self.manager = manager
        self.check_one = check_one              # entry -> number of new posts (raises on failure)
        self.on_result = on_result
        self.on_progress = on_progress
        self.listing = listing                  # site -> {(service, user id): last update} or None
        self.max_parallel_sites = max_parallel_sites
        self.cancel_event = threading.Event()
        self._lock = threading.Lock()
        self.done = 0
        self.total = 0
        self.total_new = 0
        self.skipped_unchanged = 0
        self.failed = 0

    def cancel(self) -> None:
        self.cancel_event.set()

    # ── Round (resume) ─────────────────────────────────────────────────────────
    def _round_start(self, resume: bool) -> float:
        store = getattr(self.manager, "store", None)
        now = time.time()
        if store is not None:
            try:
                started = float(store.get_meta("check_round_started", "0") or 0)
                finished = store.get_meta("check_round_finished", "") == str(started)
                if resume and started and not finished and now - started < ROUND_MAX_AGE:
                    return started
                store.set_meta("check_round_started", str(now))
            except Exception as e:
                logger.debug(f"Watchlist check round not saved: {e}", category="watchlist")
        return now

    def _round_finished(self, started: float) -> None:
        store = getattr(self.manager, "store", None)
        if store is not None:
            try:
                store.set_meta("check_round_finished", str(started))
            except Exception:
                pass

    # ── Skipping creators that haven't changed ─────────────────────────────────
    def _unchanged(self, site: str, entries: List[Any], now: float) -> set:
        if not self.listing or len(entries) < LISTING_MIN_CREATORS:
            return set()
        candidates = [e for e in entries
                      if getattr(e, "last_checked_at", 0) and now - e.last_checked_at < FULL_CHECK_EVERY]
        if len(candidates) < LISTING_MIN_CREATORS:
            return set()
        try:
            updated = self.listing(site)
        except Exception as e:
            logger.debug(f"Creator list of {site} unavailable: {e}", category="watchlist")
            updated = None
        if not updated:
            return set()
        skip = set()
        for e in candidates:
            u = updated.get(((e.service or "").lower(), str(e.user_id)))
            if u is not None and u < e.last_checked_at - UNCHANGED_MARGIN:
                skip.add(id(e))
        if skip:
            logger.info(f"Watchlist: {len(skip)} of {len(entries)} {site} artist(s) haven't posted since "
                        f"their last check; skipped.", category="watchlist")
        return skip

    # ── Running ────────────────────────────────────────────────────────────────
    def run(self, entries: Iterable[Any], resume: bool = True) -> int:
        """Checks the entries; returns the number of new posts found (also self.total_new)."""
        entries = list(entries)
        started = self._round_start(resume)
        todo = [e for e in entries if not (getattr(e, "last_checked_at", 0) >= started)]
        already = len(entries) - len(todo)
        if already:
            logger.info(f"Watchlist: continuing the last check ({already} of {len(entries)} artist(s) "
                        f"already done).", category="watchlist")
            # creators done in that round count with what they found then
            self.total_new += sum(getattr(e, "new_post_count", 0) or 0 for e in entries
                                  if getattr(e, "last_checked_at", 0) >= started)
        by_site: Dict[str, List[Any]] = defaultdict(list)
        for e in todo:
            by_site[site_of(e)].append(e)
        now = time.time()
        self.total = len(entries)
        self.done = already
        self._progress()
        queues = {}
        for site, items in by_site.items():
            items.sort(key=activity_day, reverse=True)
            skip = self._unchanged(site, items, now)
            if skip:
                self.skipped_unchanged += len(skip)
                self.total_new += sum(getattr(e, "new_post_count", 0) or 0 for e in items if id(e) in skip)
                with self._lock:
                    self.done += len(skip)
                self._progress()
            queues[site] = [e for e in items if id(e) not in skip]

        sites = sorted(queues, key=lambda s: -len(queues[s]))
        pending = list(sites)
        pending_lock = threading.Lock()

        def worker():
            while not self.cancel_event.is_set():
                with pending_lock:
                    if not pending:
                        return
                    site = pending.pop(0)
                for e in queues[site]:
                    if self.cancel_event.is_set():
                        return
                    self._check(e)

        threads = [threading.Thread(target=worker, name=f"WatchlistCheck-{i}", daemon=True)
                   for i in range(max(1, min(self.max_parallel_sites, len(sites))))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if not self.cancel_event.is_set():
            self._round_finished(started)
        return self.total_new

    def _check(self, e) -> None:
        try:
            n = int(self.check_one(e) or 0)
        except Exception as ex:
            n = None
            with self._lock:
                self.failed += 1
            logger.warning(f"Watchlist check error for {getattr(e, 'creator_name', '?')!r}: {ex}", category="watchlist")
        if n is not None:
            if getattr(e, "new_post_count", n) != n:
                e.new_post_count = n
            e.last_checked_at = time.time()
            try:
                self.manager.save(e)
            except Exception:
                pass
            with self._lock:
                self.total_new += n
        with self._lock:
            self.done += 1
        if n is not None and self.on_result:
            try:
                self.on_result(e, n)
            except Exception:
                pass
        self._progress()

    def _progress(self) -> None:
        if self.on_progress:
            try:
                self.on_progress(self.done, self.total)
            except Exception:
                pass
