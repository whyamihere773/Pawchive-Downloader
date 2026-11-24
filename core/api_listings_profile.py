"""
API Client — Creator Listings, Profile Lookup & Pawchive Deferred Attachment Resolver Mixin
Decomposed from core/api_client.py to keep modules cohesive and under 1,000 lines.
"""

import json
import random
import re
import threading
import time
from typing import Any, Callable, Dict, Optional
from urllib.parse import unquote

from core.filter_options import safe_int
from core.logger import logger
from core.parser import URLParseResult
from core.providers import is_disabled
from core.text_utils import clean_text

_COOMER_FAMILY_SERVICES = {"onlyfans", "fansly", "candfans"}


class ApiListingsProfileMixin:
    """Creator directory listings, profile resolution, and Pawchive temporary-attachment scraping."""

    def _extract_creator_from_html(self, html_text: str, user_id: str) -> Optional[str]:
        """Extract creator display name from Kemono/Pawchive/Coomer HTML page metadata."""
        if not html_text:
            return None
        import re
        uid_str = str(user_id).strip()

        # 1. itemprop="name"
        m = re.search(r'itemprop=["\']name["\'][^>]*>(.*?)<', html_text, re.I)
        if m:
            name = clean_text(m.group(1))
            if name and name != uid_str:
                return name

        # 2. user-header__name
        m = re.search(r'class=["\'][^"\']*user-header__name[^"\']*["\'][^>]*>(.*?)<', html_text, re.I)
        if m:
            name = clean_text(m.group(1))
            if name and name != uid_str:
                return name

        # 3. title regex: Posts of (.*?) from ...
        m = re.search(r'<title>\s*Posts of (.*?) from', html_text, re.I)
        if m:
            name = clean_text(m.group(1))
            if name and name != uid_str:
                return name

        # 4. title regex: (.*?)'s posts | ...
        m = re.search(r'<title>\s*(.*?)\'s posts', html_text, re.I)
        if m:
            name = clean_text(m.group(1))
            if name and name != uid_str:
                return name

        # 5. og:title
        m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html_text, re.I)
        if m:
            name = clean_text(m.group(1))
            if name and name != uid_str and not name.lower().startswith("posts of"):
                return name

        return None

    @property
    def _fetch_state(self) -> threading.local:
        st = self.__dict__.get("_fetch_tls")
        if st is None:
            st = self.__dict__.setdefault("_fetch_tls", threading.local())
        return st

    def last_fetch_failed(self) -> bool:
        """True when this thread's last fetch_user_posts stopped early because of an error (no
        answer, still rate limited, HTTP 403 / 5xx, unreadable page) rather than at the end of the
        list. Its result then can't be trusted to be complete."""
        return bool(getattr(self._fetch_state, "failed", False))

    # Sites that list every creator with the time of their last update in one request
    # Sites that list every creator with the time of their last update: Pawchive in one request,
    # cum.st 50 at a time (in name order, which doesn't move while it's read)
    _CREATOR_LISTINGS = ("pawchive.pw", "cum.st")
    CUMST_PAGE, CUMST_STEP = 50, 45        # pages overlap: a creator added meanwhile can't slip between
    _listing_cache: Dict[str, tuple] = {}
    _listing_lock = threading.Lock()
    _listing_sizes: Dict[str, int] = {"cum.st": 51000}     # last known number of creators

    def creator_listing_cost(self, domain: str) -> int:
        """Requests needed to read a site's creator list (0: the site has none)."""
        domain = (domain or "").lower()
        if domain not in self._CREATOR_LISTINGS or is_disabled(domain):
            return 0
        if domain == "cum.st":
            with self._listing_lock:
                size = self._listing_sizes.get(domain, 51000)
            return size // self.CUMST_STEP + 1
        return 1

    def fetch_creator_updates(self, domain: str, max_age: float = 600.0,
                              should_stop: Optional[Callable[[], bool]] = None) -> Optional[Dict[tuple, float]]:
        """{(service, user id): time of the creator's last update} for every creator on the site, or
        None when the site has no such list (or it couldn't be fetched, or should_stop said so). Used by
        the Watchlist check to skip creators that haven't posted since their last check. Cached for a
        few minutes."""
        domain = (domain or "").lower()
        if domain not in self._CREATOR_LISTINGS or is_disabled(domain):
            return None
        with self._listing_lock:
            hit = self._listing_cache.get(domain)
            if hit and time.time() - hit[0] < max_age:
                return hit[1]
            if domain == "cum.st":
                updates = self._fetch_cumst_creators(should_stop)
                if updates:
                    self._listing_cache[domain] = (time.time(), updates)
                return updates
            resp = self._get_with_log(f"https://{domain}/api/v1/creators", timeout=60)
            if resp is None or resp.status_code != 200:
                return None
            try:
                text = resp.text
            except Exception:
                return None
            updates: Dict[tuple, float] = {}
            # Read one creator at a time: parsing the whole list (15 MB) in one call would hold up the
            # window for a moment
            dec = json.JSONDecoder()
            sep = re.compile(r"[\s,]*")
            i = sep.match(text, text.find("[") + 1).end() if "[" in text else len(text)
            n = len(text)
            try:
                while i < n and text[i] != "]":
                    c, i = dec.raw_decode(text, i)
                    i = sep.match(text, i).end()
                    if isinstance(c, dict) and c.get("id") is not None:
                        try:
                            updates[(str(c.get("service") or "").lower(), str(c["id"]))] = float(c.get("updated") or 0)
                        except (TypeError, ValueError):
                            pass
            except ValueError as e:
                logger.debug(f"Creator list of {domain} couldn't be read: {e}", category="api")
                return None
            if not updates:
                return None
            self._listing_cache[domain] = (time.time(), updates)
            logger.debug(f"Creator list of {domain}: {len(updates)} creators.", category="api")
            return updates

    def _fetch_cumst_creators(self, should_stop: Optional[Callable[[], bool]] = None) -> Optional[Dict[tuple, float]]:
        """cum.st's creator list, a page of 50 at a time in name order (about a thousand requests, at the
        same pace as reading posts). A creator is found by its id and by its name (Watchlist links use
        either); its time is the later of "updated" and "contentUpdated"."""
        updates: Dict[tuple, float] = {}
        offset, total, failures = 0, None, 0
        while total is None or offset < total + self.CUMST_PAGE:
            if should_stop is not None and should_stop():
                return None
            resp = self._get_with_log(f"https://cum.st/api/v1/creators?sort=name&o={offset}", timeout=30)
            if resp is None or resp.status_code != 200:
                failures += 1
                if failures >= 3:
                    logger.debug("cum.st creator list couldn't be read to the end.", category="api")
                    return None
                time.sleep(2.0)
                continue
            failures = 0
            try:
                data = resp.json()
            except ValueError:
                return None
            creators = data.get("creators") if isinstance(data, dict) else data
            if isinstance(data, dict) and data.get("total") is not None:
                tot_val = safe_int(data.get("total"), -1)
                if tot_val >= 0:
                    total = tot_val
                    self._listing_sizes["cum.st"] = total
            if not creators:
                break
            for c in creators:
                if not isinstance(c, dict):
                    continue
                svc = str(c.get("service") or "").lower()
                try:
                    when = max(float(c.get("updated") or 0), float(c.get("contentUpdated") or 0))
                except (TypeError, ValueError):
                    continue
                if when <= 0:
                    continue                    # never updated as far as the site knows: checked normally
                for ident in {str(c.get(k)) for k in ("id", "name", "public_id") if c.get(k)}:
                    updates[(svc, ident)] = max(when, updates.get((svc, ident), 0.0))
                    updates[(svc, ident.lower())] = max(when, updates.get((svc, ident.lower()), 0.0))
            if len(creators) < self.CUMST_PAGE:
                break
            offset += self.CUMST_STEP
            time.sleep(random.uniform(0.35, 0.55))
        logger.debug(f"Creator list of cum.st: {len(updates)} names / ids.", category="api")
        return updates or None

    def resolve_creator_name(self, parsed: URLParseResult) -> Optional[str]:
        """Convenience helper to resolve and return just the clean creator display name."""
        if not parsed or not parsed.is_valid:
            return None
        profile = self.fetch_creator_profile(parsed)
        if profile and isinstance(profile, dict):
            name = profile.get("displayName") or profile.get("name") or profile.get("username")
            if name and str(name).strip() != str(parsed.user_id).strip():
                return clean_text(str(name))
        return None

    def fetch_creator_profile(self, parsed: URLParseResult) -> Dict[str, Any]:
        """Fetch creator profile, trying profile endpoints, cross-domain mirrors, HTML page scraping, and post fallback."""
        if getattr(parsed, "domain", "") == "coomerfans.com" or getattr(parsed, "provider", "") == "coomerfans":
            from services.coomerfans_client import fetch_creator_profile as fetch_cf_profile
            return fetch_cf_profile(parsed)

        logger.info(f"Fetching creator profile: {parsed.service}/{parsed.user_id}", category="api")
        uid_str = str(parsed.user_id).strip()

        # Phase 1: Try dedicated JSON profile endpoints on the link's site + the mirror that carries
        # the same creators (Pawchive/Kemono, or cum.st/Coomer). Switched-off sites are skipped.
        family = ("coomer.st", "cum.st") if str(parsed.service).lower() in _COOMER_FAMILY_SERVICES else ("pawchive.pw", "kemono.cr")
        profile_domains = [d for d in [parsed.domain, *family] if d and not is_disabled(d)]
        profile_domains = list(dict.fromkeys(profile_domains))

        for domain in profile_domains:
            url = f"https://{domain}/api/v1/{parsed.service}/user/{parsed.user_id}/profile"
            resp = self._get_with_log(url, timeout=10, quick=True)
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, dict):
                        raw_name = data.get("displayName") or data.get("name") or data.get("username")
                        name = clean_text(raw_name) if raw_name else None
                        if name and name != uid_str:
                            data["name"] = name
                            logger.success(f"Creator: {name!r}  service={parsed.service}  id={parsed.user_id}", category="api")
                            return data
                except Exception as e:
                    logger.debug(f"Failed to parse profile JSON from {url}: {e}", category="api")

        # Phase 2: HTML Page metadata scraping (extremely resilient against API rate limits & 429/403)
        from core.parser import canonical_site_url
        for domain in profile_domains:
            html_url = canonical_site_url(domain, parsed.service, parsed.user_id) or f"https://{domain}/{parsed.service}/user/{parsed.user_id}"
            resp = self._get_with_log(html_url, timeout=10, quick=True)
            if resp and resp.status_code == 200:
                name = self._extract_creator_from_html(resp.text, uid_str)
                if name:
                    logger.success(f"Creator: {name!r} (from HTML page {domain})  service={parsed.service}  id={parsed.user_id}", category="api")
                    return {"id": parsed.user_id, "name": name, "service": parsed.service}

        # Phase 3: Try posts endpoints ONLY if they contain a distinct creator name (NEVER accept raw_name == user_id)
        for domain in profile_domains:
            posts_url = self.posts_list_url(domain, parsed.service, parsed.user_id, 0)
            resp = self._get_with_log(posts_url, timeout=10, quick=True)
            if resp and resp.status_code == 200:
                try:
                    posts_data = resp.json()
                    items = posts_data.get("posts", []) if isinstance(posts_data, dict) else (posts_data if isinstance(posts_data, list) else [])
                    if items and isinstance(items[0], dict):
                        # ONLY check username or name — NEVER accept user field which is always the user_id
                        raw_name = items[0].get("username") or items[0].get("name")
                        name = clean_text(raw_name) if raw_name else None
                        if name and name != uid_str:
                            logger.success(f"Creator: {name!r} (from post metadata)  service={parsed.service}", category="api")
                            return {"id": parsed.user_id, "name": name, "service": parsed.service}
                except Exception:
                    pass

        logger.warning(f"Could not retrieve profile for {parsed.user_id}; using ID as name.", category="api")
        return {"id": parsed.user_id, "name": parsed.user_id, "service": parsed.service}

    @staticmethod
    def extract_pawchive_temporary_attachments(html_text: str) -> Dict[str, str]:
        """
        Parses Pawchive post HTML and returns a mapping of:
        clean_filename -> signed temporary download URL (https://t1-t4.pawchive.pw/(f|d)/...).
        """
        if not html_text:
            return {}
        matches = re.findall(r'(?:href|src)=["\'](https://t\d+\.pawchive\.pw/(?:f|d)/[^"\']+)["\']', html_text)
        mapping: Dict[str, str] = {}
        for raw_u in matches:
            u = raw_u.replace("&amp;", "&")
            path_part = u.split("?")[0].split("/")[-1]
            name = unquote(path_part)
            if name and name not in mapping:
                mapping[name] = u
        return mapping

    @staticmethod
    def is_pawchive_temp_expired(fobj: Dict[str, Any]) -> bool:
        """Returns True if the temporary Pawchive URL or temp_expires has expired."""
        if not isinstance(fobj, dict):
            return False
        raw_path = fobj.get("path") if isinstance(fobj.get("path"), str) else ""
        temp_u = (
            fobj.get("temp_download_url")
            or fobj.get("temp_url")
            or (raw_path if re.search(r"\bt\d+\.pawchive\.pw\b", raw_path) else "")
        )
        if temp_u and "?e=" in temp_u:
            try:
                m = re.search(r'[?&]e=(\d+)', temp_u)
                if m:
                    exp_ts = float(m.group(1))
                    if time.time() > exp_ts:
                        return True
            except Exception:
                pass
        temp_expires = fobj.get("temp_expires")
        if temp_expires:
            try:
                from datetime import datetime, timezone
                exp_dt = datetime.fromisoformat(str(temp_expires).replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp_dt:
                    return True
            except Exception:
                pass
        return False

    def resolve_pawchive_deferred_attachments(self, post: Dict[str, Any], domain: str = "pawchive.pw") -> int:
        """
        Resolves signed t1-t4.pawchive.pw temporary download URLs for Pawchive attachments
        (either via direct 'temp_download_url'/'temp_url' in API JSON or scraping post HTML for 'deferred: True' items).
        Returns the number of resolved attachments.
        """
        if not isinstance(post, dict):
            return 0

        attachments = post.get("attachments", [])
        if not isinstance(attachments, list):
            attachments = []

        resolved_count = 0
        targets = []
        main_f = post.get("file")
        if isinstance(main_f, dict):
            targets.append(main_f)
        for a in attachments:
            if isinstance(a, dict):
                targets.append(a)

        # 1. Resolve direct temp_download_url / temp_url fields provided in the API JSON for file and attachments
        for target in targets:
            temp_u = target.get("temp_download_url") or target.get("temp_url")
            if temp_u and not str(temp_u).split("?")[0].lower().endswith(".m3u8") and not self.is_pawchive_temp_expired(target):
                target["path"] = temp_u
                target["is_temporary"] = True
                target["preview_only"] = False
                resolved_count += 1

        if post.get("has_full") is False:
            return resolved_count

        deferred_items = [
            a for a in attachments
            if isinstance(a, dict) and a.get("deferred") and not a.get("is_temporary") and (not a.get("path") or not str(a.get("path", "")).startswith("http"))
        ]
        if not deferred_items:
            return resolved_count

        post_id = str(post.get("id") or "")
        service = post.get("service") or ""
        user_id = str(post.get("user") or "")

        if not post_id or not service or not user_id:
            return resolved_count

        eff_domain = domain if "pawchive" in (domain or "") else "pawchive.pw"
        page_url = f"https://{eff_domain}/{service}/user/{user_id}/post/{post_id}"
        logger.debug(f"Fetching post HTML to resolve {len(deferred_items)} temporary file(s): {page_url}", category="api")

        resp = self._get_with_log(page_url, timeout=20)
        if not resp or resp.status_code != 200 or not resp.text:
            logger.warning(f"Could not fetch HTML for post {post_id} to resolve temporary files", category="api")
            return resolved_count

        temp_map = self.extract_pawchive_temporary_attachments(resp.text)
        if not temp_map:
            logger.info(f"Post {post_id} has {len(deferred_items)} deferred attachment(s), but temporary links are expired or unavailable", category="api")
            return resolved_count

        html_resolved = 0
        lower_map = {k.lower(): v for k, v in temp_map.items()}
        for att in deferred_items:
            att_name = att.get("name") or ""
            matched_url = temp_map.get(att_name) or lower_map.get(att_name.lower())
            if matched_url:
                att["path"] = matched_url
                att["is_temporary"] = True
                att["preview_only"] = False
                html_resolved += 1

        if isinstance(main_f, dict) and (main_f.get("deferred") or main_f.get("preview_only")) and not main_f.get("is_temporary"):
            mf_name = main_f.get("name") or ""
            matched_mf_url = temp_map.get(mf_name) or lower_map.get(mf_name.lower())
            if matched_mf_url:
                main_f["path"] = matched_mf_url
                main_f["is_temporary"] = True
                main_f["preview_only"] = False
                html_resolved += 1

        resolved_count += html_resolved
        if html_resolved > 0:
            logger.info(f"✨ Resolved {html_resolved}/{len(deferred_items)} temporary oversized file(s) from t1.pawchive.pw for post {post_id}", category="api")

        return resolved_count
