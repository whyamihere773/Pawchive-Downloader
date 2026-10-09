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
- Spot checks: a few of the creators the site's list would skip are checked anyway, first. If one of them
  has posted since its last check, the list can't be trusted that day and every creator is checked.
"""

import random
import threading
import time
from collections import defaultdict, deque
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.logger import logger

ROUND_MAX_AGE = 24 * 3600            # an unfinished round older than this starts over
UNCHANGED_MARGIN = 24 * 3600         # "updated" must be this much older than the last check to skip
FULL_CHECK_EVERY = 7 * 24 * 3600     # checked in full at least this often, whatever the listing says
LISTING_MIN_CREATORS = 30            # fewer creators on a site: checking them is cheaper than the listing
SPOT_CHECKS_MIN, SPOT_CHECKS_MAX = 3, 100   # skipped creators checked anyway, to test the list


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
                 max_parallel_sites: int = 4,
                 listing_cost: Optional[Callable[[str], int]] = None):
        self.manager = manager
        self.check_one = check_one              # entry -> number of new posts (raises on failure)
        self.on_result = on_result
        self.on_progress = on_progress
        self.listing = listing                  # site -> {(service, user id): last update} or None
        self.listing_cost = listing_cost        # site -> requests needed to read its list
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
        # Worth it when reading the site's list takes fewer requests than checking the artists it can
        # skip (one request for Pawchive; about a thousand for cum.st)
        cost = self.listing_cost(site) if self.listing_cost else 1
        if len(candidates) < max(LISTING_MIN_CREATORS, int(cost * 1.5)):
            return set()
        try:
            try:
                updated = self.listing(site, should_stop=self.cancel_event.is_set)
            except TypeError:
                updated = self.listing(site)
        except Exception as e:
            logger.debug(f"Creator list of {site} unavailable: {e}", category="watchlist")
            updated = None
        if not updated:
            return set()
        skip = set()
        for e in candidates:
            svc = (e.service or "").lower()
            u = updated.get((svc, str(e.user_id)))
            if u is None:
                u = updated.get((svc, str(e.user_id).lower()))
            if u and u < e.last_checked_at - UNCHANGED_MARGIN:      # (0: the site doesn't know; checked)
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
        queues: Dict[str, deque] = {}
        held: Dict[str, List[Any]] = {}        # skipped by the site's list, pending its spot checks
        spots: Dict[str, Dict[int, int]] = {}   # site -> {id(creator): new posts known before}
        for site, items in by_site.items():
            items.sort(key=activity_day, reverse=True)
            skip = self._unchanged(site, items, now)
            sample: List[Any] = []
            if skip:
                skipped = [e for e in items if id(e) in skip]
                # 2% (3 to 100): a list that misses even 5% of updates is caught 99% of the time at 100
                k = min(len(skipped), SPOT_CHECKS_MAX, max(SPOT_CHECKS_MIN, len(skipped) // 50))
                sample = random.sample(skipped, k)
                for e in sample:
                    skip.discard(id(e))
                held[site] = [e for e in skipped if id(e) in skip]
                spots[site] = {id(e): getattr(e, "new_post_count", 0) or 0 for e in sample}
            ids = {id(e) for e in sample}
            queues[site] = deque(sample + [e for e in items if id(e) not in skip and id(e) not in ids])

        sites = sorted(queues, key=lambda s: -len(queues[s]))
        pending = list(sites)
        pending_lock = threading.Lock()

        def worker():
            while not self.cancel_event.is_set():
                with pending_lock:
                    if not pending:
                        return
                    site = pending.pop(0)
                q = queues[site]
                waiting = dict(spots.get(site, {}))      # spot checks not done yet
                doubt = False
                while q:
                    if self.cancel_event.is_set():
                        return
                    e = q.popleft()
                    n = self._check(e)
                    if id(e) in waiting:
                        before = waiting.pop(id(e))
                        if n is not None and n > before:
                            doubt = True                  # posted since its last check: the list missed it
                        if not waiting and site in held:
                            self._settle_held(site, held.pop(site), doubt, q)

        threads = [threading.Thread(target=worker, name=f"WatchlistCheck-{i}", daemon=True)
                   for i in range(max(1, min(self.max_parallel_sites, len(sites))))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if not self.cancel_event.is_set():
            self._round_finished(started)
        return self.total_new

    def _settle_held(self, site: str, skipped: List[Any], doubt: bool, queue: deque) -> None:
        """After a site's spot checks: the creators its list skipped are skipped (counted with what they
        found before), or, if a spot check found the list wrong, checked like the others."""
        if doubt:
            logger.warning(f"Watchlist: {site}'s creator list missed new posts in a spot check; checking all "
                           f"{len(skipped)} artist(s) it would have skipped.", category="watchlist")
            queue.extend(skipped)
            return
        with self._lock:
            self.skipped_unchanged += len(skipped)
            self.total_new += sum(getattr(e, "new_post_count", 0) or 0 for e in skipped)
            self.done += len(skipped)
        self._progress()

    def _check(self, e) -> Optional[int]:
        """Checks one creator; its number of new posts, None when it couldn't be checked."""
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
        return n

    def _progress(self) -> None:
        if self.on_progress:
            try:
                self.on_progress(self.done, self.total)
            except Exception:
                pass
