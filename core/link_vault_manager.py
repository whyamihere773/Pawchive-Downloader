"""
Link Vault Manager
Permanent cloud link harvester, credential database, and health probing engine.
Stored in config/link_vault.db (SQLite: a save writes only the creators, posts and links that changed;
the whole vault used to be rewritten as JSON, with an fsync and a .bak copy, after every change). Older
versions' link_vault.json is imported once and kept as link_vault.json.migrated. Uncapped post text
storage, and Creator > Posts > Links tree modeling.
"""

import os
import sys
import json
import uuid
import re
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Set, Callable

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

import contextlib
import sqlite3

from core.logger import logger
from core.text_utils import strip_html_tags


class LinkVaultStore:
    """link_vault.db: one row per creator, post and link (each as JSON), written as they change."""

    def __init__(self, path: str):
        self.path = path
        self._ready = False

    def exists(self) -> bool:
        return os.path.exists(self.path)

    @contextlib.contextmanager
    def _db(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            if not self._ready:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS creators (key TEXT PRIMARY KEY, data TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS posts (post_id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS links (id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL);
                """)
                conn.commit()
                self._ready = True
            yield conn
        finally:
            conn.close()

    def load(self) -> Optional[Dict[str, Any]]:
        """The vault, or None when the database is empty."""
        with self._db() as conn:
            creators = {k: json.loads(d) for k, d in conn.execute("SELECT key, data FROM creators;")}
            posts = {pid: json.loads(d) for pid, d in conn.execute("SELECT post_id, data FROM posts ORDER BY seq;")}
            links = [json.loads(d) for (d,) in conn.execute("SELECT data FROM links ORDER BY seq;")]
        if not (creators or posts or links):
            return None
        return {"version": 1, "creators": creators, "posts": posts, "links": links}

    def write(self, creators: Dict[str, Any], posts: Dict[str, Any], links: Dict[str, Any],
              gone_creators=(), gone_posts=(), gone_links=(), seq_of=None, replace_all: bool = False) -> None:
        dumps = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
        seq_of = seq_of or {}
        with self._db() as conn:
            with conn:
                if replace_all:
                    conn.execute("DELETE FROM creators;")
                    conn.execute("DELETE FROM posts;")
                    conn.execute("DELETE FROM links;")
                conn.executemany("INSERT INTO creators (key, data) VALUES (?, ?) "
                                 "ON CONFLICT(key) DO UPDATE SET data = excluded.data;",
                                 [(k, dumps(v)) for k, v in creators.items()])
                conn.executemany("INSERT INTO posts (post_id, seq, data) VALUES (?, ?, ?) "
                                 "ON CONFLICT(post_id) DO UPDATE SET data = excluded.data;",
                                 [(k, seq_of.get(("p", k), 0), dumps(v)) for k, v in posts.items()])
                conn.executemany("INSERT INTO links (id, seq, data) VALUES (?, ?, ?) "
                                 "ON CONFLICT(id) DO UPDATE SET data = excluded.data;",
                                 [(k, seq_of.get(("l", k), 0), dumps(v)) for k, v in links.items()])
                conn.executemany("DELETE FROM creators WHERE key = ?;", [(k,) for k in gone_creators])
                conn.executemany("DELETE FROM posts WHERE post_id = ?;", [(k,) for k in gone_posts])
                conn.executemany("DELETE FROM links WHERE id = ?;", [(k,) for k in gone_links])


class LinkVaultManager:
    """
    Manages persistent storage, tree modeling, deletion, and health checks
    for external cloud storage links and passwords.
    """

    def __init__(self, config_dir: Optional[str] = None):
        if not config_dir:
            from core.path_utils import get_config_dir, migrate_legacy_files
            config_dir = get_config_dir()
            migrate_legacy_files(config_dir, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config"),
                                 ("link_vault.json", "link_vault.json.bak"))
        self.config_dir = config_dir
        os.makedirs(self.config_dir, exist_ok=True)

        self.vault_file = os.path.join(self.config_dir, "link_vault.json")      # older versions (imported once)
        self.bak_file = os.path.join(self.config_dir, "link_vault.json.bak")
        self.store = LinkVaultStore(os.path.join(self.config_dir, "link_vault.db"))
        self._lock = threading.Lock()
        self._probing_active = False
        # What changed since the last save (only that is written), and lookups by link id / by link
        self._dirty = {"creators": set(), "posts": set(), "links": set()}
        self._gone = {"creators": set(), "posts": set(), "links": set()}
        self._write_all = False
        self._seq = 0
        self._seq_of: Dict[tuple, int] = {}
        self._link_by_id: Dict[str, Dict[str, Any]] = {}
        self._link_by_sig: Dict[str, Dict[str, Any]] = {}

        self._data: Dict[str, Any] = {
            "version": 1,
            "creators": {},
            "posts": {},
            "links": []
        }
        self._load()

    @property
    def data(self) -> Dict[str, Any]:
        return self._data

    @data.setter
    def data(self, value: Dict[str, Any]) -> None:
        """Replacing the whole vault: everything is written by the next save."""
        self._data = self._validate_schema(value or {})
        self._rebuild_indexes_unlocked()
        self._write_all = True

    def _load(self):
        """Loads the vault from link_vault.db; an older version's link_vault.json (or its .bak) is
        imported the first time and kept, renamed to .migrated."""
        with self._lock:
            data = None
            try:
                if self.store.exists():
                    data = self.store.load()
            except Exception as e:
                logger.error(f"Failed to load link_vault.db: {e}", category="vault")
            imported = False
            if data is None:
                data = self._read_legacy_json()
                imported = data is not None
            self._data = self._validate_schema(data or {})
            self._rebuild_indexes_unlocked()
            if imported:
                self._write_all = True
                if self._save_unlocked():
                    for path in (self.vault_file, self.bak_file):
                        self._keep_aside(path)
                    logger.info("Link Vault moved to the new format; the old file is kept as link_vault.json.migrated.",
                                category="vault")
            if self.data["creators"] or self.data["links"]:
                logger.info(
                    f"Link Vault loaded: {len(self.data.get('creators', {}))} creators, "
                    f"{len(self.data.get('links', []))} links.",
                    category="vault"
                )

    def _read_legacy_json(self) -> Optional[Dict[str, Any]]:
        for path in (self.vault_file, self.bak_file):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = json.load(f)
                    if isinstance(content, dict) and "links" in content:
                        if path == self.bak_file:
                            logger.success("Recovered Link Vault from .bak backup.", category="vault")
                        return content
                except Exception as e:
                    logger.warning(f"Failed to load {os.path.basename(path)}: {e}", category="vault")
        return None

    @staticmethod
    def _keep_aside(path: str) -> None:
        """Renames an imported file to "<name>.migrated" (never deleted)."""
        if not os.path.exists(path):
            return
        target = path + ".migrated"
        n = 2
        while os.path.exists(target):
            target = f"{path}.migrated-{n}"
            n += 1
        try:
            os.replace(path, target)
        except OSError as e:
            logger.warning(f"Couldn't rename {os.path.basename(path)} after importing it: {e}", category="vault")

    def _rebuild_indexes_unlocked(self) -> None:
        self._link_by_id = {}
        self._link_by_sig = {}
        self._seq_of = {}
        self._seq = 0
        for pid in self.data["posts"]:
            self._seq += 1
            self._seq_of[("p", pid)] = self._seq
        for lnk in self.data["links"]:
            self._seq += 1
            self._index_link_unlocked(lnk)

    def _index_link_unlocked(self, lnk: Dict[str, Any]) -> None:
        lid = lnk.get("id")
        if lid:
            self._link_by_id[lid] = lnk
            if ("l", lid) not in self._seq_of:
                self._seq += 1
                self._seq_of[("l", lid)] = self._seq
        self._link_by_sig.setdefault(f"{lnk.get('creator_key', '')}|{self.normalize_url(lnk.get('url', ''))}", lnk)

    def _touch(self, kind: str, key: str) -> None:
        if kind == "posts" and ("p", key) not in self._seq_of:
            self._seq += 1
            self._seq_of[("p", key)] = self._seq
        self._dirty[kind].add(key)
        self._gone[kind].discard(key)

    def _forget(self, kind: str, key: str) -> None:
        self._dirty[kind].discard(key)
        self._gone[kind].add(key)
        if kind == "links":
            lnk = self._link_by_id.pop(key, None)
            if lnk is not None:
                sig = f"{lnk.get('creator_key', '')}|{self.normalize_url(lnk.get('url', ''))}"
                if self._link_by_sig.get(sig) is lnk:
                    del self._link_by_sig[sig]

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
        """Writes what changed since the last save (one transaction)."""
        with self._lock:
            self._save_unlocked()

    def _save_unlocked(self) -> bool:
        """Internal write of the changed rows. True when everything is saved."""
        self.revision = getattr(self, "revision", 0) + 1      # every change is saved: readers cache by it
        d = self.data
        if self._write_all:
            creators, posts = dict(d["creators"]), dict(d["posts"])
            links = {lnk.get("id"): lnk for lnk in d["links"] if lnk.get("id")}
            gone = {"creators": set(), "posts": set(), "links": set()}
        else:
            creators = {k: d["creators"][k] for k in self._dirty["creators"] if k in d["creators"]}
            posts = {k: d["posts"][k] for k in self._dirty["posts"] if k in d["posts"]}
            links = {k: self._link_by_id[k] for k in self._dirty["links"] if k in self._link_by_id}
            gone = {k: set(v) for k, v in self._gone.items()}
        if not (creators or posts or links or any(gone.values()) or self._write_all):
            return True
        try:
            self.store.write(creators, posts, links, gone["creators"], gone["posts"], gone["links"],
                             seq_of=self._seq_of, replace_all=self._write_all)
        except Exception as e:
            logger.error(f"Failed to persist link vault: {e}", category="vault")
            return False                    # (kept as changed: written with the next save)
        self._write_all = False
        for v in self._dirty.values():
            v.clear()
        for v in self._gone.values():
            v.clear()
        return True

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
            self._touch("creators", creator_key)

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
                self._touch("posts", post_id)

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
                    existing = self._link_by_sig.get(sig)
                    if existing is not None:
                        # Update passwords if newly discovered
                        current_pws = set(existing.get("passwords", []))
                        if not current_pws.issuperset(link_passwords):
                            current_pws.update(link_passwords)
                            existing["passwords"] = sorted(list(current_pws))
                            self._touch("links", existing.get("id"))
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
                    self._index_link_unlocked(link_entry)
                    self._touch("links", link_entry["id"])
                    new_links_count += 1

            # Recalculate counts (this creator's: every creator's was recounted over every post and
            # link on each harvest)
            self._recalculate_counts_unlocked({creator_key})
            self._save_unlocked()

        if new_links_count > 0:
            logger.success(
                f"Link Vault: Added {new_links_count} new link(s) for '{creator_name}'.",
                category="vault"
            )
        return new_links_count

    def _recalculate_counts_unlocked(self, only: Optional[Set[str]] = None):
        """Recalculates post and link counts per creator (of the creators in `only`, or all), in one
        pass over the posts and links."""
        keys = set(self.data["creators"]) if only is None else {k for k in only if k in self.data["creators"]}
        if not keys:
            return
        posts = dict.fromkeys(keys, 0)
        links = dict.fromkeys(keys, 0)
        for p in self.data["posts"].values():
            k = p.get("creator_key")
            if k in posts:
                posts[k] += 1
        for lnk in self.data["links"]:
            k = lnk.get("creator_key")
            if k in links:
                links[k] += 1
        for k in keys:
            cinfo = self.data["creators"][k]
            if cinfo.get("post_count") != posts[k] or cinfo.get("link_count") != links[k]:
                cinfo["post_count"] = posts[k]
                cinfo["link_count"] = links[k]
                self._touch("creators", k)

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
            # Posts by creator and links by post, found once: scanning every post for each creator and
            # every link for each post took seconds (minutes on big vaults) on the window thread
            posts_by_creator: Dict[str, List[Dict[str, Any]]] = {}
            for p in self.data["posts"].values():
                posts_by_creator.setdefault(p.get("creator_key", ""), []).append(p)
            links_by_post: Dict[tuple, List[Dict[str, Any]]] = {}
            for lnk in self.data["links"]:
                links_by_post.setdefault((lnk.get("creator_key", ""), lnk.get("post_id", "")), []).append(lnk)

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
                c_posts = list(posts_by_creator.get(ckey, []))
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
                    child_links = list(links_by_post.get((ckey, pid), []))

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
            lnk = self._link_by_id.get(link_id)
            if lnk is not None:
                self.data["links"] = [x for x in self.data["links"] if x.get("id") != link_id]
                self._forget("links", link_id)
                self._recalculate_counts_unlocked({lnk.get("creator_key", "")})
                self._save_unlocked()
                logger.info(f"Link {link_id} deleted from Link Vault.", category="vault")
                return True
        return False

    def update_link_passwords(self, link_id: str, passwords: List[str]) -> bool:
        """
        Updates the password list for a specific link.
        Deduplicates, strips whitespace, and saves atomically.
        """
        clean_pws = []
        seen = set()
        for p in passwords:
            val = str(p).strip()
            if val and val not in seen:
                seen.add(val)
                clean_pws.append(val)

        with self._lock:
            lnk = self._link_by_id.get(link_id)
            found = lnk is not None
            if found:
                lnk["passwords"] = clean_pws
                self._touch("links", link_id)
                self._save_unlocked()
                logger.info(f"Updated passwords for link {link_id} ({len(clean_pws)} saved).", category="vault")
                return True
        return False

    def delete_post(self, post_id: str) -> bool:
        """Deletes a post and all its associated links."""
        with self._lock:
            removed = False
            affected = set()
            if post_id in self.data["posts"]:
                affected.add(self.data["posts"][post_id].get("creator_key", ""))
                del self.data["posts"][post_id]
                self._forget("posts", post_id)
                removed = True
            gone = [lnk for lnk in self.data["links"] if lnk.get("post_id") == post_id]
            if gone:
                self.data["links"] = [lnk for lnk in self.data["links"] if lnk.get("post_id") != post_id]
                for lnk in gone:
                    affected.add(lnk.get("creator_key", ""))
                    self._forget("links", lnk.get("id"))
            if removed or gone:
                self._recalculate_counts_unlocked(affected)
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
                self._forget("creators", creator_key)
                # Remove posts
                for pid, p in list(self.data["posts"].items()):
                    if p.get("creator_key") == creator_key:
                        del self.data["posts"][pid]
                        self._forget("posts", pid)
                # Remove links
                keep = []
                for lnk in self.data["links"]:
                    if lnk.get("creator_key") == creator_key:
                        self._forget("links", lnk.get("id"))
                    else:
                        keep.append(lnk)
                self.data["links"] = keep
                self._save_unlocked()
                logger.info(f"Creator {creator_key} purged from Link Vault.", category="vault")
                return True
        return False

    def clean_dead_links(self) -> int:
        """Purges all links verified as dead (HTTP 404 or host dead)."""
        with self._lock:
            dead = [lnk for lnk in self.data["links"] if lnk.get("health") == "dead"]
            purged = len(dead)
            if purged > 0:
                self.data["links"] = [lnk for lnk in self.data["links"] if lnk.get("health") != "dead"]
                for lnk in dead:
                    self._forget("links", lnk.get("id"))
                self._recalculate_counts_unlocked({lnk.get("creator_key", "") for lnk in dead})
                self._save_unlocked()
                logger.success(f"Cleaned {purged} dead links from Link Vault.", category="vault")
            return purged

    def update_link_health(self, link_id: str, health: str, save: bool = True):
        """Updates health status for a single link ('alive', 'dead', 'unknown')."""
        with self._lock:
            lnk = self._link_by_id.get(link_id)       # (a walk through every link for each result)
            if lnk is not None:
                lnk["health"] = health
                lnk["last_checked"] = datetime.datetime.now().isoformat()
                self._touch("links", link_id)
        if save:
            self.save()

    @staticmethod
    def _probe_mega(url: str) -> str:
        """Asks MEGA's public API whether a file / folder link still exists (a link that merely
        looked valid used to count as alive, so dead MEGA links were never cleaned up)."""
        import requests
        m = re.search(r"mega(?:\.co)?\.nz/(?:file/|#!)([A-Za-z0-9_-]{8})", url)
        folder = False
        if not m:
            m = re.search(r"mega(?:\.co)?\.nz/(?:folder/|#F!)([A-Za-z0-9_-]{8})", url)
            folder = bool(m)
        if not m:
            return "unknown"
        handle = m.group(1)
        if folder:
            r = requests.post(f"https://g.api.mega.co.nz/cs?id=1&n={handle}",
                              json=[{"a": "f", "c": 1, "ca": 1, "r": 1}], timeout=8)
        else:
            r = requests.post("https://g.api.mega.co.nz/cs?id=1", json=[{"a": "g", "p": handle}], timeout=8)
        if r.status_code != 200:
            return "unknown"
        data = r.json()
        first = data[0] if isinstance(data, list) and data else data
        if isinstance(first, dict):
            return "alive"
        if isinstance(first, int) and first in (-9, -16):    # not found / taken down
            return "dead"
        return "unknown"

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

            # 3. MEGA API check (a HEAD request on a MEGA page always answers 200)
            if "mega.nz" in url or "mega.co.nz" in url:
                return self._probe_mega(url)

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
        with self._lock:
            if self._probing_active:
                logger.warning("Health probing is already in progress.", category="vault")
                return
            self._probing_active = True     # set before the thread starts: two quick clicks ran two probes

        def _worker():
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
                    executor = ThreadPoolExecutor(max_workers=8)
                    try:
                        future_to_link = {
                            executor.submit(self.probe_link_health_single, lnk): lnk
                            for lnk in links_copy
                        }

                        for future in as_completed(future_to_link):
                            if cancel_event and cancel_event.is_set():
                                logger.warning("Health probing cancelled by user.", category="vault")
                                # Drop the checks that haven't started (cancel used to wait for all of them)
                                executor.shutdown(wait=False, cancel_futures=True)
                                break

                            lnk = future_to_link[future]
                            try:
                                status = future.result()
                            except Exception:
                                status = "unknown"

                            # Saved in batches: every checked link used to rewrite the whole vault file
                            self.update_link_health(lnk["id"], status, save=False)
                            done_count += 1
                            if done_count % 50 == 0:
                                self.save()

                            if progress_callback:
                                progress_callback(done_count, total, lnk.get("url", ""))
                    finally:
                        executor.shutdown(wait=False, cancel_futures=True)

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
