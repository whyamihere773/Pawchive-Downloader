"""Gallery: "Check for new posts" for the creator folder being viewed.

Works out which creator a folder belongs to, compares the creator's posts online with the
posts already saved in the folder, and queues the missing ones into that same folder.

Which creator?  (first match wins)
  1. a creator link the user pasted for this folder earlier (remembered)
  2. a Watchlist entry whose download folder contains this folder
  3. the "Creator URL" line of a post_info.txt nearby
  4. the download archive database, when it is turned on

Which posts are already here?  The post ID the downloader puts at the start of file and folder
names ("169913374_…"), the "Post ID" of post_info.txt files, and the archive database.
"""

import datetime
import json
import os
import re
import threading
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QObject, Signal, Slot

from core.logger import logger
from core.path_utils import is_post_info_name, post_info_files

_POST_ID_PREFIX = re.compile(r"^(\d{5,})_")
_CREATOR_URL = re.compile(r"https?://([^/\s]+)/([^/\s]+)/user/([^/?#\s]+)")
_POST_ID_LINE = re.compile(r"^\s*post id\s*:\s*(\S+)", re.IGNORECASE)
_SERVICE_TAG = re.compile(r"\[([A-Za-z0-9_-]{2,20})\]\s*$")
_COOMER_SERVICES = {"onlyfans", "fansly", "candfans"}
_MAX_WALK_FILES = 300_000


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(p)) if p else ""


def _inside(folder: str, root: str) -> bool:
    f, r = _norm(folder), _norm(root)
    return bool(r) and (f == r or f.startswith(r.rstrip("\\/") + os.sep))


def _creator_url_from_info(info_path: str) -> str:
    try:
        with open(info_path, "r", encoding="utf-8", errors="replace") as fh:
            for _ in range(60):
                line = fh.readline()
                if not line:
                    break
                if line.lower().startswith("creator url"):
                    m = _CREATOR_URL.search(line)
                    if m:
                        return m.group(0)
    except OSError:
        pass
    return ""


def _post_id_from_info(info_path: str) -> str:
    try:
        with open(info_path, "r", encoding="utf-8", errors="replace") as fh:
            for _ in range(30):
                line = fh.readline()
                if not line:
                    break
                m = _POST_ID_LINE.match(line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return ""


def _published(post: dict) -> str:
    """Sortable date text of a post ("2025-03-01T12:00:00")."""
    pub = post.get("published") or post.get("added") or ""
    if isinstance(pub, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(pub, datetime.timezone.utc).replace(tzinfo=None).isoformat()
        except Exception:
            return ""
    return str(pub)


def _has_files(post: dict) -> bool:
    """Text-only posts have nothing to download, so they never count as missing."""
    f = post.get("file") or {}
    if isinstance(f, dict) and (f.get("path") or f.get("name")):
        return True
    for a in post.get("attachments") or []:
        if isinstance(a, dict) and (a.get("path") or a.get("name")):
            return True
    return False


class GalleryUpdates(QObject):
    checkProgress = Signal(int, "QVariantMap")   # token, {page, scanned}
    creatorFolderReady = Signal(str, "QVariantMap")  # folder, creatorForFolder() answer
    checkFinished = Signal(int, "QVariantMap")   # token, result (see _finish)
    downloadQueued = Signal(int, "QVariantMap")  # token, {ok, files, posts, folder, message}

    def __init__(self, app_bridge=None, watchlist_manager=None, parent=None, links_file: str = ""):
        super().__init__(parent)
        self._app = app_bridge
        self._watchlist = watchlist_manager
        self._token = 0
        self._cancel = threading.Event()
        self._results: Dict[int, dict] = {}
        if not links_file:
            try:
                from core.path_utils import get_config_dir
                links_file = os.path.join(get_config_dir(), "gallery_creator_links.json")
            except Exception:
                links_file = os.path.join(os.path.expanduser("~"), ".pawchive_gallery_creator_links.json")
        self._links_file = links_file
        self._links: Dict[str, str] = self._load_links()

    # ── Remembered links (folder → creator URL) ─────────────────────────────
    def _load_links(self) -> Dict[str, str]:
        try:
            with open(self._links_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return {str(k): str(v) for k, v in (data.get("links") or {}).items()} if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception as e:
            logger.warning(f"Couldn't read remembered creator links ({e}).", category="gallery")
            return {}

    def _save_links(self):
        try:
            os.makedirs(os.path.dirname(self._links_file), exist_ok=True)
            tmp = self._links_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "links": self._links}, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self._links_file)
        except Exception as e:
            logger.warning(f"Couldn't save the creator link: {e}", category="gallery")

    # ── Which creator is this folder? ───────────────────────────────────────
    @staticmethod
    def _parse(url: str):
        from core.parser import KemonoURLParser
        parsed = KemonoURLParser.parse((url or "").strip())
        if not parsed.is_valid or parsed.provider != "kemono" or not parsed.user_id or parsed.post_id:
            return None
        return parsed

    @staticmethod
    def _artist_dir_for(folder: str, service: str) -> str:
        """The creator's own folder: the nearest folder named "… [service]", else the folder itself."""
        probe = os.path.normpath(folder)
        tag = f"[{(service or '').lower()}]"
        for _ in range(5):
            if service and os.path.basename(probe).lower().endswith(tag):
                return probe
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent
        return os.path.normpath(folder)

    def _from_url(self, url: str, folder: str, source: str, name: str = "", artist_dir: str = "") -> Optional[dict]:
        parsed = self._parse(url)
        if not parsed:
            return None
        return {
            "found": True,
            "url": f"https://{parsed.domain}/{parsed.service}/user/{parsed.user_id}",
            "domain": parsed.domain,
            "service": parsed.service,
            "userId": str(parsed.user_id),
            "name": name,
            "artistDir": artist_dir or self._artist_dir_for(folder, parsed.service),
            "source": source,
        }

    def _identify(self, folder: str) -> Optional[dict]:
        folder = os.path.normpath(folder)

        # 1. A link the user gave for this folder (or a parent of it)
        best = ""
        for key in self._links:
            if _inside(folder, key) and len(key) > len(best):
                best = key
        if best:
            info = self._from_url(self._links[best], folder, "remembered", artist_dir=best)
            if info:
                return info

        # 2. Watchlist download folders
        if self._watchlist is not None:
            for entry in list(getattr(self._watchlist, "entries", [])):
                dirs = list(getattr(entry, "download_dirs", []) or [])
                if getattr(entry, "download_dir", ""):
                    dirs.append(entry.download_dir)
                for d in dirs:
                    if d and _inside(folder, d):
                        url = getattr(entry, "url", "") or f"https://{entry.domain}/{entry.service}/user/{entry.user_id}"
                        info = self._from_url(url, folder, "watchlist", getattr(entry, "creator_name", ""), os.path.normpath(d))
                        if info:
                            return info

        # 3. post_info.txt here, above, or in the first post folders below (posts sharing a
        #    folder each have a "post_info [<id>].txt"; grouped by type they sit in "Other")
        probe = folder
        for _ in range(4):
            for info in post_info_files(probe, limit=3):
                url = _creator_url_from_info(info)
                if url:
                    return self._from_url(url, folder, "post info")
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent
        try:
            with os.scandir(folder) as it:
                checked = 0
                for entry in it:
                    if checked >= 40:
                        break
                    if entry.is_dir(follow_symlinks=False):
                        checked += 1
                        below = [entry.path]
                        if entry.name.lower() == "other":
                            try:
                                below += sorted(e.path for e in os.scandir(entry.path) if e.is_dir(follow_symlinks=False))[:20]
                            except OSError:
                                pass
                        for d in below:
                            for info in post_info_files(d, limit=3):
                                url = _creator_url_from_info(info)
                                if url:
                                    return self._from_url(url, folder, "post info")
        except OSError:
            pass

        # 4. Download archive database (only when the user turned it on)
        am = getattr(self._app, "archive_manager", None)
        if am is not None and getattr(am, "is_enabled", False) and getattr(am, "_conn", None) is not None:
            try:
                like = os.path.normpath(folder).rstrip("\\/") + os.sep + "%"
                with am._lock:
                    row = am._conn.execute(
                        "SELECT service, creator_id, creator_name FROM downloaded_files "
                        "WHERE file_path LIKE ? AND creator_id IS NOT NULL AND creator_id != '' LIMIT 1",
                        (like,),
                    ).fetchone()
                if row:
                    service, creator_id, creator_name = row[0], row[1], row[2] or ""
                    domain = "coomer.st" if (service or "").lower() in _COOMER_SERVICES else "kemono.cr"
                    return self._from_url(f"https://{domain}/{service}/user/{creator_id}", folder, "archive", creator_name)
            except Exception as e:
                logger.debug(f"Archive lookup for {folder} failed: {e}", category="gallery")
        return None

    @staticmethod
    def _looks_like_creator_folder(folder: str) -> bool:
        if _SERVICE_TAG.search(os.path.basename(os.path.normpath(folder))):
            return True
        try:
            with os.scandir(folder) as it:
                for n, entry in enumerate(it):
                    if n > 400:
                        break
                    if _POST_ID_PREFIX.match(entry.name):
                        return True
        except OSError:
            pass
        return False

    @Slot(str)
    def creatorForFolderAsync(self, folder: str) -> None:
        """creatorForFolder in the background, answered with creatorFolderReady(folder, info). It runs on
        every folder the Gallery opens and reads files, the watchlist and the archive: on the window
        thread it stalled each folder change, for seconds with big watchlists / archives."""
        def _job():
            info = self.creatorForFolder(folder)
            try:
                self.creatorFolderReady.emit(folder, info)
            except RuntimeError:
                pass        # the app is closing
        threading.Thread(target=_job, name="GalleryCreator", daemon=True).start()

    @Slot(str, result="QVariantMap")
    def creatorForFolder(self, folder: str) -> dict:
        """{found, url, service, userId, name, artistDir, source} or {found: False, maybe}.

        maybe = the folder looks like downloads from one creator (so the button is worth showing
        and the user can paste the creator's link)."""
        if not folder or folder.startswith("::") or not os.path.isdir(folder):
            return {"found": False, "maybe": False}
        try:
            info = self._identify(folder)
        except Exception as e:
            logger.debug(f"creatorForFolder({folder}) failed: {e}", category="gallery")
            info = None
        if info:
            return info
        return {"found": False, "maybe": self._looks_like_creator_folder(folder)}

    @Slot(str, str, result="QVariantMap")
    def rememberCreatorLink(self, folder: str, url: str) -> dict:
        """The user pasted a creator link for this folder: check it and remember it."""
        info = self._from_url(url, folder, "remembered", artist_dir=os.path.normpath(folder))
        if not info:
            return {"found": False, "error": "That doesn't look like a creator link (for example https://kemono.cr/patreon/user/12345)."}
        self._links[os.path.normpath(folder)] = info["url"]
        self._save_links()
        return info

    # ── Posts already in the folder ─────────────────────────────────────────
    def _known_post_ids(self, artist_dir: str, service: str, user_id: str) -> Set[str]:
        known: Set[str] = set()
        seen = 0
        for root, dirs, files in os.walk(artist_dir):
            for d in dirs:
                m = _POST_ID_PREFIX.match(d)
                if m:
                    known.add(m.group(1))
            for f in files:
                seen += 1
                m = _POST_ID_PREFIX.match(f)
                if m:
                    known.add(m.group(1))
                elif is_post_info_name(f):
                    pid = _post_id_from_info(os.path.join(root, f))
                    if pid:
                        known.add(pid)
            if seen > _MAX_WALK_FILES or self._cancel.is_set():
                break
        am = getattr(self._app, "archive_manager", None)
        if am is not None and getattr(am, "is_enabled", False) and getattr(am, "_conn", None) is not None:
            try:
                with am._lock:
                    rows = am._conn.execute(
                        "SELECT DISTINCT post_id FROM downloaded_files WHERE service = ? AND creator_id = ?",
                        (service, user_id),
                    ).fetchall()
                known.update(str(r[0]) for r in rows if r and r[0])
            except Exception:
                pass
        return known

    # ── Check ───────────────────────────────────────────────────────────────
    @Slot(str, result=int)
    def checkFolder(self, folder: str) -> int:
        """Compare the creator's posts with this folder. Progress: checkProgress; answer: checkFinished."""
        self._cancel.set()
        self._cancel = threading.Event()
        cancel = self._cancel
        self._token += 1
        token = self._token
        threading.Thread(target=self._run_check, args=(token, folder, cancel), daemon=True, name="GalleryUpdates").start()
        return token

    @Slot()
    def cancel(self):
        self._cancel.set()

    def _run_check(self, token: int, folder: str, cancel: threading.Event):
        def fail(message: str):
            if not cancel.is_set():
                self.checkFinished.emit(token, {"ok": False, "error": message})

        try:
            info = self._identify(folder)
            if not info:
                fail("The gallery couldn't tell which creator this folder belongs to.")
                return
            api = getattr(self._app, "api_client", None)
            parsed = self._parse(info["url"])
            if api is None or parsed is None:
                fail("Checking for posts isn't available right now.")
                return
            name = info.get("name") or ""
            if not name:
                try:
                    name = api.resolve_creator_name(parsed) or ""
                except Exception:
                    name = ""
            name = name or os.path.basename(info["artistDir"]) or parsed.user_id

            self.checkProgress.emit(token, {"page": 0, "scanned": 0, "stage": "local", "name": name})
            known = self._known_post_ids(info["artistDir"], parsed.service, str(parsed.user_id))
            if cancel.is_set():
                return

            def on_page(page, count):
                if not cancel.is_set():
                    self.checkProgress.emit(token, {"page": int(page), "scanned": int(count), "stage": "online", "name": name})

            posts = api.fetch_user_posts(parsed, progress_callback=on_page, cancel_event=cancel)
            if cancel.is_set():
                return
            if not posts:
                fail(f"Couldn't load {name}'s posts. Check your connection, or try again in a moment.")
                return

            # One entry per post, only posts that actually have files
            by_id: Dict[str, dict] = {}
            for p in posts:
                pid = str(p.get("id", ""))
                if pid and pid not in by_id and _has_files(p):
                    by_id[pid] = p
            have = [p for pid, p in by_id.items() if pid in known]
            missing = [p for pid, p in by_id.items() if pid not in known]
            latest_have = max((_published(p) for p in have), default="")
            if latest_have:
                new = [p for p in missing if _published(p) > latest_have]
                older = [p for p in missing if _published(p) <= latest_have]
            else:
                new, older = [], missing
            new.sort(key=_published, reverse=True)
            older.sort(key=_published, reverse=True)

            self._results = {token: {
                "info": info, "name": name, "parsed": parsed, "new": new, "older": older,
            }}

            def brief(p):
                return {"title": str(p.get("title") or "Untitled post"), "date": _published(p)[:10], "id": str(p.get("id", ""))}

            self.checkFinished.emit(token, {
                "ok": True,
                "name": name,
                "service": parsed.service,
                "url": info["url"],
                "artistDir": info["artistDir"],
                "total": len(by_id),
                "have": len(have),
                "newCount": len(new),
                "olderCount": len(older),
                "matched": len(have) > 0,
                "latestHave": latest_have[:10],
                "newest": [brief(p) for p in (new or older)[:6]],
            })
        except Exception as e:
            logger.warning(f"Checking for new posts failed: {e}", category="gallery")
            fail("Something went wrong while checking. Try again in a moment.")

    # ── Download ────────────────────────────────────────────────────────────
    @Slot(int, bool, result=bool)
    def downloadMissing(self, token: int, includeOlder: bool) -> bool:
        """Queue the new posts (and, if asked, the older ones too) into the creator's folder."""
        r = self._results.get(token)
        if not r:
            return False
        posts = list(r["new"]) + (list(r["older"]) if includeOlder else [])
        if not posts:
            return False
        threading.Thread(target=self._run_download, args=(token, r, posts), daemon=True, name="GalleryUpdatesDl").start()
        return True

    def _run_download(self, token: int, r: dict, posts: List[dict]):
        app = self._app
        info, parsed, name = r["info"], r["parsed"], r["name"]
        artist_dir = info["artistDir"]
        try:
            options = app._get_filter_options()
            tasks = app.downloader.build_tasks_from_posts(
                posts=posts,
                creator_name=name,
                service=parsed.service,
                domain=parsed.domain,
                base_dir=app._download_dir,
                options=options,
                batch_id=f"gallery_{parsed.service}_{parsed.user_id}",
                artist_dir=artist_dir,
                user_id=str(parsed.user_id),
            )
            if not tasks:
                self.downloadQueued.emit(token, {
                    "ok": False, "files": 0, "posts": len(posts), "folder": artist_dir,
                    "message": "Nothing to download: those files are already here or your download filters skip them.",
                })
                return
            app._appendTasksSignal.emit(tasks)
            app.downloader.append_tasks(tasks, options=options, cookie_str=getattr(app, "_cookie_string", ""))
            if not app._is_downloading and getattr(app.downloader, "_is_running", False):
                app._is_downloading = True
                app.isDownloadingChanged.emit()
            logger.success(f"Gallery: queued {len(tasks)} file(s) from {len(posts)} post(s) of {name!r} into {artist_dir}.", category="gallery")
            self.downloadQueued.emit(token, {
                "ok": True, "files": len(tasks), "posts": len(posts), "folder": artist_dir,
                "message": f"Downloading {len(tasks)} file{'s' if len(tasks) != 1 else ''} from {len(posts)} post{'s' if len(posts) != 1 else ''}. They'll appear here as they finish.",
            })
        except Exception as e:
            logger.warning(f"Couldn't queue the new posts of {name!r}: {e}", category="gallery")
            self.downloadQueued.emit(token, {"ok": False, "files": 0, "posts": len(posts), "folder": artist_dir,
                                             "message": "Couldn't start the download. See the log for details."})
