"""
Link Vault Manager
Permanent cloud link harvester, credential database, and health probing engine.
Maintains an atomic, persistent repository in config/link_vault.json with automatic
.bak fallback, uncapped post text storage, and Creator > Posts > Links tree modeling.
"""

import os
import sys
import json
import time
import uuid
import re
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Set, Callable
from urllib.parse import urlparse

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.logger import logger
from core.text_utils import strip_html_tags


class LinkVaultManager:
    """
    Manages persistent storage, tree modeling, deletion, and health checks
    for external cloud storage links and passwords.
    """

    def __init__(self, config_dir: Optional[str] = None):
        if not config_dir:
            config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        self.config_dir = config_dir
        os.makedirs(self.config_dir, exist_ok=True)

        self.vault_file = os.path.join(self.config_dir, "link_vault.json")
        self.bak_file = os.path.join(self.config_dir, "link_vault.json.bak")
        self._lock = threading.Lock()
        self._probing_active = False

        self.data: Dict[str, Any] = {
            "version": 1,
            "creators": {},
            "posts": {},
            "links": []
        }
        self._load()

    def _load(self):
        """Loads vault data with automatic .bak fallback."""
        with self._lock:
            # 1. Primary file
            if os.path.exists(self.vault_file):
                try:
                    with open(self.vault_file, "r", encoding="utf-8") as f:
                        content = json.load(f)
                        if isinstance(content, dict) and "links" in content:
                            self.data = self._validate_schema(content)
                            logger.info(
                                f"Link Vault loaded: {len(self.data.get('creators', {}))} creators, "
                                f"{len(self.data.get('links', []))} links.",
                                category="vault"
                            )
                            return
                except Exception as e:
                    logger.warning(f"Failed to load primary link_vault.json: {e}; checking backup...", category="vault")

            # 2. Fallback to .bak file
            if os.path.exists(self.bak_file):
                try:
                    with open(self.bak_file, "r", encoding="utf-8") as f:
                        content = json.load(f)
                        if isinstance(content, dict) and "links" in content:
                            self.data = self._validate_schema(content)
                            logger.success("Recovered Link Vault from .bak backup.", category="vault")
                            self._save_unlocked()
                            return
                except Exception as e:
                    logger.error(f"Backup link_vault.json.bak also failed to load: {e}", category="vault")

            # 3. Default empty schema
            self.data = {
                "version": 1,
                "creators": {},
                "posts": {},
                "links": []
            }

    @staticmethod
    def _validate_schema(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Ensures all expected schema fields exist."""
        return {
            "version": raw.get("version", 1),
            "creators": raw.get("creators", {}) if isinstance(raw.get("creators"), dict) else {},
            "posts": raw.get("posts", {}) if isinstance(raw.get("posts"), dict) else {},
            "links": raw.get("links", []) if isinstance(raw.get("links"), list) else []
        }

    def save(self):
        """Thread-safe atomic save with .bak rotation and fsync."""
        with self._lock:
            self._save_unlocked()

    def _save_unlocked(self):
        """Internal atomic write."""
        tmp_path = f"{self.vault_file}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass

            if os.path.exists(self.vault_file):
                try:
                    import shutil
                    shutil.copy2(self.vault_file, self.bak_file)
                except Exception as e:
                    logger.debug(f"Could not rotate link vault .bak: {e}", category="vault")

            os.replace(tmp_path, self.vault_file)

            # Ensure .bak exists even on initial creation
            if not os.path.exists(self.bak_file):
                try:
                    import shutil
                    shutil.copy2(self.vault_file, self.bak_file)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to persist link vault: {e}", category="vault")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalizes URL for deduplication."""
        if not url:
            return ""
        u = url.strip()
        # Remove trailing slashes for non-path URLs
        if u.endswith("/") and not u.endswith("://"):
            u = u[:-1]
        return u

    def add_harvested_data(
        self,
        creator_name: str,
        service: str,
        user_id: str,
        harvested_posts: List[Dict[str, Any]]
    ) -> int:
        """
        Ingests harvested posts and external links into the persistent vault.
        Returns the number of new links added.
        """
        if not harvested_posts:
            return 0

        creator_name = creator_name.strip() or "Unknown Artist"
        service = service.strip() or "general"
        user_id = str(user_id).strip() or "unknown"
        creator_key = f"{service}:{user_id}".lower()
        now_iso = datetime.datetime.now().isoformat()

        new_links_count = 0

        with self._lock:
            # 1. Update/Add Creator
            if creator_key not in self.data["creators"]:
                self.data["creators"][creator_key] = {
                    "creator_key": creator_key,
                    "creator_name": creator_name,
                    "service": service,
                    "user_id": user_id,
                    "post_count": 0,
                    "link_count": 0,
                    "created_at": now_iso,
                    "updated_at": now_iso
                }
            else:
                self.data["creators"][creator_key]["creator_name"] = creator_name
                self.data["creators"][creator_key]["updated_at"] = now_iso

            # Index existing links for fast O(1) deduplication: (creator_key, normalized_url)
            existing_link_signatures: Set[str] = {
                f"{item.get('creator_key', '')}|{self.normalize_url(item.get('url', ''))}"
                for item in self.data["links"]
            }

            for p in harvested_posts:
                post_id = str(p.get("post_id") or p.get("id") or str(uuid.uuid4())[:8])
                title = str(p.get("title") or "Untitled Post").strip()
                published = str(p.get("published") or p.get("date") or "")
                raw_body = str(p.get("full_text") or p.get("content") or p.get("description") or "")
                full_text = strip_html_tags(raw_body)
                post_url = str(p.get("post_url") or p.get("url") or "")
                post_passwords = p.get("passwords") or []

                # Store post text without arbitrary length capping
                self.data["posts"][post_id] = {
                    "post_id": post_id,
                    "creator_key": creator_key,
                    "creator_name": creator_name,
                    "title": title,
                    "published": published,
                    "full_text": full_text,
                    "post_url": post_url,
                    "passwords": list(set(post_passwords))
                }

                # Add links
                links_list = p.get("links") or []
                for item in links_list:
                    if isinstance(item, str):
                        raw_url = item
                        platform = "other"
                        link_passwords = post_passwords
                    elif isinstance(item, dict):
                        raw_url = item.get("url", "")
                        platform = item.get("platform", "other")
                        link_passwords = item.get("passwords") or post_passwords
                    else:
                        continue

                    norm_url = self.normalize_url(raw_url)
                    if not norm_url:
                        continue

                    sig = f"{creator_key}|{norm_url}"
                    if sig in existing_link_signatures:
                        # Update passwords if newly discovered
                        for existing in self.data["links"]:
                            if existing.get("creator_key") == creator_key and self.normalize_url(existing.get("url", "")) == norm_url:
                                current_pws = set(existing.get("passwords", []))
                                current_pws.update(link_passwords)
                                existing["passwords"] = sorted(list(current_pws))
                                break
                        continue

                    link_entry = {
                        "id": str(uuid.uuid4()),
                        "url": norm_url,
                        "platform": platform,
                        "post_id": post_id,
                        "creator_key": creator_key,
                        "creator_name": creator_name,
                        "post_title": title,
                        "passwords": sorted(list(set(link_passwords))),
                        "password_source": item.get("password_source", "post") if isinstance(item, dict) else "post",
                        "health": "unknown",  # "alive", "dead", "unknown"
                        "last_checked": None,
                        "added_at": now_iso
                    }
                    self.data["links"].append(link_entry)
                    existing_link_signatures.add(sig)
                    new_links_count += 1

            # Recalculate counts
            self._recalculate_counts_unlocked()
            self._save_unlocked()

        if new_links_count > 0:
            logger.success(
                f"Link Vault: Added {new_links_count} new link(s) for '{creator_name}'.",
                category="vault"
            )
        return new_links_count

    def _recalculate_counts_unlocked(self):
        """Recalculates post and link counts per creator."""
        for ckey, cinfo in self.data["creators"].items():
            c_posts = [p for p in self.data["posts"].values() if p.get("creator_key") == ckey]
            c_links = [lnk for lnk in self.data["links"] if lnk.get("creator_key") == ckey]
            cinfo["post_count"] = len(c_posts)
            cinfo["link_count"] = len(c_links)

    def get_tree_model(self, search_query: str = "", platform_filter: str = "") -> List[Dict[str, Any]]:
        """
        Builds a hierarchical list model for QML:
        Creator -> Posts -> Links.
        Applies live case-insensitive search and platform filtering.
        """
        search_lower = search_query.strip().lower()
        platform_filter = platform_filter.strip().lower()

        with self._lock:
            tree = []
            # Sort creators by most recently updated
            sorted_creators = sorted(
                self.data["creators"].values(),
                key=lambda x: x.get("updated_at", ""),
                reverse=True
            )

            for c in sorted_creators:
                ckey = c.get("creator_key", "")
                c_name = c.get("creator_name", "Unknown")
                c_service = c.get("service", "")

                # Gather posts for this creator
                c_posts = [p for p in self.data["posts"].values() if p.get("creator_key") == ckey]
                # Sort posts by publication date descending
                c_posts.sort(key=lambda x: x.get("published", ""), reverse=True)

                creator_posts_list = []
                creator_total_links = 0

                for post in c_posts:
                    pid = post.get("post_id", "")
                    p_title = post.get("title", "")
                    p_full_text = post.get("full_text", "")
                    p_passwords = post.get("passwords", [])

                    # Find child links for this post
                    child_links = [
                        lnk for lnk in self.data["links"]
                        if lnk.get("post_id") == pid and lnk.get("creator_key") == ckey
                    ]

                    # Filter by platform
                    if platform_filter and platform_filter != "all":
                        child_links = [lnk for lnk in child_links if lnk.get("platform", "").lower() == platform_filter]

                    # Filter by search query
                    if search_lower:
                        match_creator = search_lower in c_name.lower() or search_lower in c_service.lower()
                        match_post = search_lower in p_title.lower() or search_lower in p_full_text.lower()
                        matched_links = []
                        for lnk in child_links:
                            url_match = search_lower in lnk.get("url", "").lower()
                            pw_match = any(search_lower in str(pw).lower() for pw in lnk.get("passwords", []))
                            if match_creator or match_post or url_match or pw_match:
                                matched_links.append(lnk)
                        child_links = matched_links

                    if not child_links and search_lower and not (search_lower in c_name.lower() or search_lower in p_title.lower()):
                        continue

                    creator_total_links += len(child_links)
                    creator_posts_list.append({
                        "post_id": pid,
                        "title": p_title,
                        "published": post.get("published", ""),
                        "full_text": strip_html_tags(p_full_text),
                        "post_url": post.get("post_url", ""),
                        "passwords": p_passwords,
                        "links_count": len(child_links),
                        "links": child_links
                    })

                if creator_posts_list or (not search_lower and not platform_filter):
                    tree.append({
                        "creator_key": ckey,
                        "creator_name": c_name,
                        "service": c_service,
                        "user_id": c.get("user_id", ""),
                        "post_count": len(creator_posts_list),
                        "link_count": creator_total_links,
                        "updated_at": c.get("updated_at", ""),
                        "posts": creator_posts_list
                    })

            return tree

    def delete_link(self, link_id: str) -> bool:
        """Deletes a single link by ID."""
        with self._lock:
            before_len = len(self.data["links"])
            self.data["links"] = [lnk for lnk in self.data["links"] if lnk.get("id") != link_id]
            if len(self.data["links"]) < before_len:
                self._recalculate_counts_unlocked()
                self._save_unlocked()
                logger.info(f"Link {link_id} deleted from Link Vault.", category="vault")
                return True
        return False

    def delete_post(self, post_id: str) -> bool:
        """Deletes a post and all its associated links."""
        with self._lock:
            removed = False
            if post_id in self.data["posts"]:
                del self.data["posts"][post_id]
                removed = True
            before_len = len(self.data["links"])
            self.data["links"] = [lnk for lnk in self.data["links"] if lnk.get("post_id") != post_id]
            if removed or len(self.data["links"]) < before_len:
                self._recalculate_counts_unlocked()
                self._save_unlocked()
                logger.info(f"Post {post_id} and child links deleted from Link Vault.", category="vault")
                return True
        return False

    def delete_creator(self, creator_key: str) -> bool:
        """Deletes an entire creator, all their posts, and all their links."""
        with self._lock:
            creator_key = creator_key.lower()
            if creator_key in self.data["creators"]:
                del self.data["creators"][creator_key]
                # Remove posts
                self.data["posts"] = {
                    pid: p for pid, p in self.data["posts"].items()
                    if p.get("creator_key") != creator_key
                }
                # Remove links
                self.data["links"] = [
                    lnk for lnk in self.data["links"]
                    if lnk.get("creator_key") != creator_key
                ]
                self._save_unlocked()
                logger.info(f"Creator {creator_key} purged from Link Vault.", category="vault")
                return True
        return False

    def clean_dead_links(self) -> int:
        """Purges all links verified as dead (HTTP 404 or host dead)."""
        with self._lock:
            initial_count = len(self.data["links"])
            self.data["links"] = [lnk for lnk in self.data["links"] if lnk.get("health") != "dead"]
            purged = initial_count - len(self.data["links"])
            if purged > 0:
                self._recalculate_counts_unlocked()
                self._save_unlocked()
                logger.success(f"Cleaned {purged} dead links from Link Vault.", category="vault")
            return purged

    def update_link_health(self, link_id: str, health: str):
        """Updates health status for a single link ('alive', 'dead', 'unknown')."""
        with self._lock:
            for lnk in self.data["links"]:
                if lnk.get("id") == link_id:
                    lnk["health"] = health
                    lnk["last_checked"] = datetime.datetime.now().isoformat()
                    break
        self.save()

    def get_all_passwords(self) -> List[str]:
        """Returns a flat, deduplicated list of all passwords currently stored."""
        with self._lock:
            pw_set = set()
            for post in self.data["posts"].values():
                for pw in post.get("passwords", []):
                    if pw and isinstance(pw, str):
                        pw_set.add(pw.strip())
            for lnk in self.data["links"]:
                for pw in lnk.get("passwords", []):
                    if pw and isinstance(pw, str):
                        pw_set.add(pw.strip())
            return sorted(list(pw_set))

    def probe_link_health_single(self, link_item: Dict[str, Any]) -> str:
        """
        Probes a single link using non-blocking HEAD/API checks.
        Returns: 'alive', 'dead', or 'unknown'.
        """
        import requests
        url = link_item.get("url", "")
        platform = link_item.get("platform", "other").lower()

        if not url:
            return "dead"

        try:
            # 1. Pixeldrain API check
            if "pixeldrain.com" in url:
                m = re.search(r'pixeldrain\.com/(?:u/|l/|api/file/)([a-zA-Z0-9_\-]+)', url)
                if m:
                    file_id = m.group(1)
                    api_url = f"https://pixeldrain.com/api/file/{file_id}/info"
                    r = requests.get(api_url, timeout=6)
                    if r.status_code == 200 and r.json().get("success") is True:
                        return "alive"
                    elif r.status_code == 404:
                        return "dead"

            # 2. GoFile API check
            if "gofile.io" in url:
                m = re.search(r'gofile\.io/(?:d/|#)([a-zA-Z0-9_\-]+)', url)
                if m:
                    content_id = m.group(1)
                    api_url = f"https://api.gofile.io/contents/{content_id}"
                    r = requests.get(api_url, timeout=6)
                    if r.status_code == 200 and r.json().get("status") == "ok":
                        return "alive"
                    elif r.status_code in (404, 400):
                        return "dead"

            # 3. Mega syntax check
            if "mega.nz" in url or "mega.co.nz" in url:
                # Validate valid Mega file/folder syntax (#... or /file/... or /folder/...)
                if "#" in url or "/file/" in url or "/folder/" in url:
                    return "alive"

            # 4. Catbox / general HTTP HEAD request
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            r = requests.head(url, headers=headers, timeout=6, allow_redirects=True)
            if r.status_code in (200, 206, 301, 302, 307, 308):
                return "alive"
            elif r.status_code in (404, 410):
                return "dead"
            elif r.status_code == 405:
                # Method Not Allowed -> fallback to 1-byte GET
                r = requests.get(url, headers={**headers, "Range": "bytes=0-0"}, timeout=6, stream=True)
                if r.status_code in (200, 206):
                    return "alive"
                elif r.status_code in (404, 410):
                    return "dead"
        except Exception:
            return "unknown"

        return "unknown"

    def probe_all_links_async(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
        creator_key: Optional[str] = None,
        completion_callback: Optional[Callable[[], None]] = None
    ):
        """
        Runs health check across all stored links (or links belonging to creator_key) in a background worker pool.
        Non-blocking, updates status in real-time.
        """
        if self._probing_active:
            logger.warning("Health probing is already in progress.", category="vault")
            return

        def _worker():
            self._probing_active = True
            try:
                with self._lock:
                    if creator_key:
                        ck_lower = creator_key.lower()
                        links_copy = [lnk for lnk in self.data["links"] if lnk.get("creator_key", "").lower() == ck_lower]
                    else:
                        links_copy = list(self.data["links"])
                total = len(links_copy)
                logger.info(f"Link Vault: Starting health probe across {total} links (creator={creator_key or 'all'})...", category="vault")

                done_count = 0
                if total > 0:
                    with ThreadPoolExecutor(max_workers=8) as executor:
                        future_to_link = {
                            executor.submit(self.probe_link_health_single, lnk): lnk
                            for lnk in links_copy
                        }

                        for future in as_completed(future_to_link):
                            if cancel_event and cancel_event.is_set():
                                logger.warning("Health probing cancelled by user.", category="vault")
                                break

                            lnk = future_to_link[future]
                            try:
                                status = future.result()
                            except Exception:
                                status = "unknown"

                            self.update_link_health(lnk["id"], status)
                            done_count += 1

                            if progress_callback:
                                progress_callback(done_count, total, lnk.get("url", ""))

                self.save()
                logger.success(f"Link Vault: Health probing complete ({done_count}/{total} checked).", category="vault")
            finally:
                self._probing_active = False
                if completion_callback:
                    try:
                        completion_callback()
                    except Exception as e:
                        logger.error(f"Error in probe completion callback: {e}", category="vault")

        t = threading.Thread(target=_worker, daemon=True, name="LinkVaultProber")
        t.start()


# Global Singleton
link_vault_manager = LinkVaultManager()
