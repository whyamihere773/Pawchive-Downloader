"""
QML bridge for Gallery tools that don't belong in the main app bridge:

- Recursive search across subfolders (background thread, streamed in batches)
- Finding the source post a downloaded file came from
- An undo stack for move, rename, new folder and copy
- Favourites and star ratings (kept in gallery_marks.json, followed through moves/renames)
- Copying an image / file to the clipboard
- Watching the open folder so new files show up live
- Tagging files with characters / series from the Known list (for the character filter)
"""

import json
import os
import re
import shutil
import threading
import time
from typing import Dict, List, Optional

from PySide6.QtCore import QFileSystemWatcher, QMimeData, QObject, Property, QUrl, Signal, Slot

from core.logger import logger

_POST_ID_PREFIX = re.compile(r"^(\d{5,})_")
_INVALID_NAME_CHARS = set('<>:"/\\|?*')
_UNDO_LIMIT = 25


def _file_item(entry: os.DirEntry, root: str) -> Optional[dict]:
    """Same shape as AppBridge.listDirectory items, plus the folder relative to the search root."""
    try:
        is_dir = entry.is_dir(follow_symlinks=False)
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return None
    rel_dir = os.path.relpath(os.path.dirname(entry.path), root)
    return {
        "name": entry.name,
        "path": os.path.normpath(entry.path),
        "is_dir": is_dir,
        "size": -1 if is_dir else st.st_size,
        "file_count": -1 if is_dir else 0,
        "folder_count": 0,
        "child_count": -1 if is_dir else 0,
        "mtime": st.st_mtime,
        "ext": "" if is_dir else os.path.splitext(entry.name)[1].lower(),
        "rel_dir": "" if rel_dir == "." else rel_dir,
    }


def parse_search_query(query: str):
    """Split a search into name words and file-type filters.

    ".png", "*.png" and "ext:png" are type filters (several = any of them, compound
    types like ".tar.gz" work); everything else must appear in the name.
    """
    words, exts = [], []
    for tok in (query or "").lower().split():
        if tok.startswith("ext:"):
            tok = "." + tok[4:].lstrip(".")
        elif tok.startswith("*."):
            tok = tok[1:]
        if tok.startswith(".") and len(tok) > 1:
            exts.append(tok)
        elif tok:
            words.append(tok)
    return words, exts


def name_matches(name: str, is_dir: bool, words: List[str], exts: List[str]) -> bool:
    lower = name.lower()
    if exts and (is_dir or not any(lower.endswith(e) for e in exts)):
        return False
    return all(w in lower for w in words)


def _parse_post_info(path: str) -> Dict[str, str]:
    """Read the header lines the downloader writes into post_info.txt."""
    meta: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i > 40 or line.startswith("---"):
                    break
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
    except OSError:
        pass
    return meta


def _mark_key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


class GalleryToolsBridge(QObject):
    # token, batch of items, finished?, folders scanned
    searchBatch = Signal(int, 'QVariantList', bool, int)
    undoChanged = Signal()
    marksChanged = Signal()
    watchedFolderChanged = Signal(str)          # the open folder's contents changed on disk
    tagsReady = Signal(int, 'QVariantMap')      # token, {path: [character / series names]}
    animationReady = Signal(str, 'QVariantMap') # path, {frames, durations} (frames 0 = not animated)
    storageProgress = Signal(int, 'QVariantMap')  # token, {files, bytes, folder}
    storageReady = Signal(int, 'QVariantMap')     # token, breakdown (see _run_storage)

    def __init__(self, app_bridge=None, watchlist_manager=None, parent=None, marks_file: str = ""):
        super().__init__(parent)
        self._app = app_bridge
        self._watchlist = watchlist_manager
        self._search_token = 0
        self._undo: List[dict] = []
        self._lock = threading.Lock()

        # Favourites / ratings: {normcase path: {"path", "fav", "rating", "updated"}}
        if not marks_file:
            try:
                from core.path_utils import get_config_dir
                marks_file = os.path.join(get_config_dir(), "gallery_marks.json")
            except Exception:
                marks_file = os.path.join(os.path.expanduser("~"), ".pawchive_gallery_marks.json")
        self._marks_file = marks_file
        self._marks: Dict[str, dict] = {}
        self._load_marks()

        # Live refresh of the open folder
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self.watchedFolderChanged.emit)
        self._tag_token = 0
        self._storage_token = 0
        self._storage_cancel = threading.Event()

    # ── Recursive search ────────────────────────────────────────────────────
    @Slot(str, str, int, result=int)
    def startSearch(self, root: str, query: str, maxResults: int = 5000) -> int:
        """Search names under root. Results arrive through searchBatch; returns the search token."""
        with self._lock:
            self._search_token += 1
            token = self._search_token
        words, exts = parse_search_query(query)
        if not root or not os.path.isdir(root) or not (words or exts):
            self.searchBatch.emit(token, [], True, 0)
            return token
        threading.Thread(
            target=self._run_search, args=(token, os.path.normpath(root), words, exts, max(1, maxResults)),
            daemon=True, name="GallerySearch",
        ).start()
        return token

    @Slot()
    def cancelSearch(self):
        with self._lock:
            self._search_token += 1

    def _run_search(self, token: int, root: str, words: List[str], exts: List[str], max_results: int):
        batch: List[dict] = []
        found = 0
        scanned = 0
        last_emit = time.monotonic()
        stack = [root]
        while stack:
            if token != self._search_token:
                return
            folder = stack.pop()
            scanned += 1
            try:
                with os.scandir(folder) as it:
                    entries = list(it)
            except OSError:
                continue
            for entry in entries:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    is_dir = False
                if is_dir:
                    stack.append(entry.path)
                if name_matches(entry.name, is_dir, words, exts):
                    item = _file_item(entry, root)
                    if item:
                        batch.append(item)
                        found += 1
                        if found >= max_results:
                            stack = []
                            break
            now = time.monotonic()
            if batch and (len(batch) >= 300 or now - last_emit > 0.3):
                if token != self._search_token:
                    return
                self.searchBatch.emit(token, batch, False, scanned)
                batch = []
                last_emit = now
        if token == self._search_token:
            self.searchBatch.emit(token, batch, True, scanned)

    # ── Source post ─────────────────────────────────────────────────────────
    @Slot(str, result='QVariantMap')
    def sourcePost(self, path: str) -> dict:
        """Work out the web page of the post a downloaded file came from.

        Post ID: the number the downloader puts at the start of file names, or post_info.txt.
        Site / service / creator: the 'Creator URL' line of a nearby post_info.txt, or the
        watchlist entry whose download folder contains the file.
        """
        empty = {"url": "", "postId": "", "title": ""}
        if not path:
            return empty
        path = os.path.normpath(path)
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        name = os.path.basename(path)

        post_id = ""
        m = _POST_ID_PREFIX.match(name)
        if m:
            post_id = m.group(1)

        # Walk up a few levels looking for post_info.txt files
        domain = service = user = title = ""
        info_post_url = ""
        # (beside the file: its post's own info file, also the "Other" folder when grouped by type;
        # in a folder shared by many posts, any of their info files still gives the creator)
        from core.path_utils import POST_INFO_NAME, info_dirs_for, post_info_files, post_info_for_file
        probe = folder
        for level in range(4):
            info = os.path.join(probe, POST_INFO_NAME)
            if level == 0:
                info = next((f for f in (post_info_for_file(d, name, post_id) for d in info_dirs_for(folder)) if f), "")
                if not info:
                    shared = post_info_files(folder, limit=1)
                    cm = re.match(r"https?://([^/]+)/([^/]+)/user/([^/?#]+)",
                                  _parse_post_info(shared[0]).get("creator url", "")) if shared else None
                    if cm:
                        domain, service, user = cm.group(1), cm.group(2), cm.group(3)
            if info and os.path.isfile(info):
                meta = _parse_post_info(info)
                cu = meta.get("creator url", "")
                cm = re.match(r"https?://([^/]+)/([^/]+)/user/([^/?#]+)", cu)
                if cm and not domain:
                    domain, service, user = cm.group(1), cm.group(2), cm.group(3)
                info_id = meta.get("post id", "")
                if not post_id and info_id and probe == folder:
                    post_id = info_id
                if info_id and info_id == post_id:
                    title = meta.get("title", "")
                    info_post_url = meta.get("post url", "")
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent

        if not post_id:
            return empty
        if info_post_url:
            return {"url": info_post_url, "postId": post_id, "title": title}

        if not domain and self._watchlist is not None:
            folder_case = os.path.normcase(folder)
            for entry in list(getattr(self._watchlist, "entries", [])):
                dirs = list(getattr(entry, "download_dirs", []) or [])
                if getattr(entry, "download_dir", ""):
                    dirs.append(entry.download_dir)
                for d in dirs:
                    d_case = os.path.normcase(os.path.normpath(d))
                    if d and (folder_case == d_case or folder_case.startswith(d_case + os.sep)):
                        domain, service, user = entry.domain, entry.service, str(entry.user_id)
                        break
                if domain:
                    break

        if not (domain and service and user):
            return {"url": "", "postId": post_id, "title": title}
        return {"url": f"https://{domain}/{service}/user/{user}/post/{post_id}", "postId": post_id, "title": title}

    # ── Favourites & ratings ────────────────────────────────────────────────
    def _load_marks(self):
        try:
            with open(self._marks_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("items", {}) if isinstance(data, dict) else {}
            self._marks = {k: v for k, v in items.items() if isinstance(v, dict) and v.get("path")}
        except FileNotFoundError:
            self._marks = {}
        except Exception as e:
            logger.warning(f"Couldn't read gallery favourites ({e}); starting with an empty list.", category="gallery")
            self._marks = {}

    def _save_marks(self):
        try:
            os.makedirs(os.path.dirname(self._marks_file), exist_ok=True)
            tmp = self._marks_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "items": self._marks}, f, ensure_ascii=False)
            os.replace(tmp, self._marks_file)
        except Exception as e:
            logger.warning(f"Couldn't save gallery favourites: {e}", category="gallery")
        self.marksChanged.emit()

    def _set_mark(self, path: str, **fields):
        key = _mark_key(path)
        entry = dict(self._marks.get(key) or {"path": os.path.normpath(path), "fav": False, "rating": 0})
        entry.update(fields)
        entry["updated"] = time.time()
        if not entry.get("fav") and not entry.get("rating"):
            self._marks.pop(key, None)
        else:
            self._marks[key] = entry

    @Slot(result='QVariantMap')
    def allMarks(self) -> dict:
        """{normcase path: {"fav": bool, "rating": 0-5}} for every marked item."""
        return {k: {"fav": bool(v.get("fav")), "rating": int(v.get("rating") or 0)} for k, v in self._marks.items()}

    @Slot('QVariantList', bool)
    def setFavorite(self, paths: list, on: bool):
        for p in paths or []:
            if p:
                self._set_mark(p, fav=bool(on))
        self._save_marks()

    @Slot('QVariantList', int)
    def setRating(self, paths: list, rating: int):
        rating = max(0, min(5, int(rating)))
        for p in paths or []:
            if p:
                self._set_mark(p, rating=rating)
        self._save_marks()

    @Slot(result='QVariantMap')
    def favoriteItems(self) -> dict:
        """Favourites that still exist, as gallery items (rel_dir = their folder), plus a missing count."""
        items, missing = [], 0
        for key, m in self._marks.items():
            if not m.get("fav"):
                continue
            path = m["path"]
            try:
                st = os.stat(path)
            except OSError:
                missing += 1
                continue
            is_dir = os.path.isdir(path)
            items.append({
                "name": os.path.basename(path), "path": path, "is_dir": is_dir,
                "size": -1 if is_dir else st.st_size, "file_count": -1 if is_dir else 0, "folder_count": 0,
                "child_count": -1 if is_dir else 0, "mtime": st.st_mtime,
                "ext": "" if is_dir else os.path.splitext(path)[1].lower(),
                "rel_dir": os.path.dirname(path),
            })
        return {"items": items, "missing": missing}

    @Slot(result=int)
    def forgetMissingFavorites(self) -> int:
        gone = [k for k, m in self._marks.items() if not os.path.exists(m["path"])]
        for k in gone:
            self._marks.pop(k, None)
        if gone:
            self._save_marks()
        return len(gone)

    def _remap_marks(self, src: str, dst: str):
        """Keep favourites/ratings attached to items (and everything inside folders) that moved."""
        src_key, changed = _mark_key(src), False
        for key in list(self._marks.keys()):
            if key == src_key or key.startswith(src_key + os.sep):
                entry = self._marks.pop(key)
                rest = entry["path"][len(os.path.normpath(src)):]
                entry["path"] = os.path.normpath(dst) + rest
                self._marks[_mark_key(entry["path"])] = entry
                changed = True
        return changed

    def _remap_pairs(self, pairs):
        if any(self._remap_marks(a, b) for a, b in pairs):
            self._save_marks()

    # ── Clipboard ───────────────────────────────────────────────────────────
    @Slot(str, result=bool)
    def copyFileToClipboard(self, path: str) -> bool:
        """Put the file on the clipboard: pastes as a file in Explorer, and as the picture
        itself in chat apps and editors when it's an image."""
        from PySide6.QtGui import QGuiApplication, QImage
        if not path or not os.path.isfile(path):
            return False
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        img = QImage(path)
        if not img.isNull():
            mime.setImageData(img)
        QGuiApplication.clipboard().setMimeData(mime)
        return True

    # ── Animated images (APNG, animated AVIF, …) ───────────────────────────
    @Slot(str)
    def prepareAnimation(self, path: str):
        """Decode an animation's frames in the background; answers with animationReady."""
        from bridge.thumbnail_provider import load_animation

        def work():
            info = load_animation(path) if path and os.path.isfile(path) else {"frames": 0, "durations": []}
            self.animationReady.emit(path, info)

        threading.Thread(target=work, daemon=True, name="AnimDecode").start()

    # ── Live refresh ────────────────────────────────────────────────────────
    @Slot(str)
    def watchFolder(self, path: str):
        """Watch only the open folder (not its subfolders) for added / removed / renamed files."""
        old = self._watcher.directories()
        if old:
            self._watcher.removePaths(old)
        if path and os.path.isdir(path):
            self._watcher.addPath(path)

    # ── Storage breakdown ───────────────────────────────────────────────────
    _STORAGE_KINDS = (
        ("Videos", {".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".flv", ".f4v", ".wmv", ".asf", ".mpg", ".mpeg", ".m2v", ".ts", ".mts", ".m2ts", ".3gp", ".3g2", ".ogv", ".vob", ".divx"}),
        ("Pictures", {".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".apng", ".gif", ".webp", ".avif", ".heic", ".heif", ".jxl", ".bmp", ".tif", ".tiff", ".psd", ".svg", ".ico", ".tga", ".dds", ".qoi"}),
        ("Archives", {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".cbz", ".cbr", ".001"}),
        ("Audio", {".mp3", ".flac", ".wav", ".ogg", ".oga", ".m4a", ".aac", ".opus", ".wma", ".aiff", ".aif", ".mka"}),
    )

    @Slot(str, result=int)
    def scanStorage(self, path: str) -> int:
        """What takes up space under path. Progress: storageProgress; answer: storageReady."""
        self._storage_cancel.set()
        self._storage_cancel = threading.Event()
        self._storage_token += 1
        token = self._storage_token
        threading.Thread(target=self._run_storage, args=(token, path, self._storage_cancel), daemon=True, name="GalleryStorage").start()
        return token

    @Slot()
    def cancelStorageScan(self):
        self._storage_cancel.set()

    def _run_storage(self, token: int, path: str, cancel: threading.Event):
        import heapq
        path = os.path.normpath(path or "")
        if not os.path.isdir(path):
            self.storageReady.emit(token, {"ok": False, "path": path, "error": "This folder isn't available."})
            return
        kinds = {k: [0, 0] for k, _ in self._STORAGE_KINDS}
        kinds["Other"] = [0, 0]
        ext_kind = {e: k for k, exts in self._STORAGE_KINDS for e in exts}
        children: Dict[str, list] = {}      # immediate subfolder -> [bytes, files]
        loose = [0, 0]                      # files directly in path
        largest: list = []                  # min-heap of (size, path, mtime)
        total_bytes = total_files = 0
        last = time.time()
        sep_len = len(path.rstrip("\\/")) + 1
        try:
            for root, dirs, files in os.walk(path):
                if cancel.is_set():
                    return
                rel = root[sep_len:] if len(root) > len(path) else ""
                top = rel.split(os.sep, 1)[0] if rel else ""
                bucket = children.setdefault(top, [0, 0]) if top else loose
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        st = os.stat(fp, follow_symlinks=False)
                    except OSError:
                        continue
                    size = st.st_size
                    total_bytes += size
                    total_files += 1
                    bucket[0] += size
                    bucket[1] += 1
                    k = kinds[ext_kind.get(os.path.splitext(f)[1].lower(), "Other")]
                    k[0] += size
                    k[1] += 1
                    if len(largest) < 100:
                        heapq.heappush(largest, (size, fp, st.st_mtime))
                    elif size > largest[0][0]:
                        heapq.heapreplace(largest, (size, fp, st.st_mtime))
                now = time.time()
                if now - last > 0.25:
                    last = now
                    self.storageProgress.emit(token, {"files": total_files, "bytes": total_bytes, "folder": rel})
        except Exception as e:
            logger.warning(f"Storage scan of {path} failed: {e}", category="gallery")
            self.storageReady.emit(token, {"ok": False, "path": path, "error": "Couldn't finish reading this folder."})
            return
        if cancel.is_set():
            return

        def share(b):
            return (b / total_bytes) if total_bytes else 0.0

        folders = [{"name": n, "path": os.path.join(path, n), "bytes": v[0], "files": v[1], "share": share(v[0]), "isLoose": False}
                   for n, v in children.items()]
        if loose[1]:
            folders.append({"name": "Files in this folder", "path": path, "bytes": loose[0], "files": loose[1], "share": share(loose[0]), "isLoose": True})
        folders.sort(key=lambda x: x["bytes"], reverse=True)
        big = sorted(largest, reverse=True)
        self.storageReady.emit(token, {
            "ok": True,
            "path": path,
            "totalBytes": total_bytes,
            "totalFiles": total_files,
            "folders": folders[:200],
            "kinds": [{"name": k, "bytes": v[0], "files": v[1], "share": share(v[0])} for k, v in sorted(kinds.items(), key=lambda kv: kv[1][0], reverse=True) if v[1]],
            "largest": [{"name": os.path.basename(fp), "path": fp, "size": size, "mtime": mtime,
                         "folder": os.path.dirname(fp)[sep_len:] if len(os.path.dirname(fp)) > len(path) else "",
                         "ext": os.path.splitext(fp)[1].lower()} for size, fp, mtime in big],
        })

    # ── Character / series tags ─────────────────────────────────────────────
    @Slot('QVariantList', result=int)
    def tagItems(self, items: list) -> int:
        """Tag [{path, title}] with Known-list characters / series in the background (answer: tagsReady)."""
        self._tag_token += 1
        token = self._tag_token
        km = getattr(self._app, "known_manager", None)
        work = [(str(i.get("path", "")), str(i.get("title", ""))) for i in (items or []) if isinstance(i, dict)]
        threading.Thread(target=self._run_tags, args=(token, km, work), daemon=True, name="GalleryTags").start()
        return token

    @staticmethod
    def tags_for_title(km, title: str) -> List[str]:
        """The matcher stops at the first name it recognises ("Marvel Rivals Emma Frost" -> "Marvel Rivals"),
        so remove each match and look again to also find the character."""
        tags: List[str] = []
        text = title or ""
        custom = {e.lower() for e in getattr(km, "entries", [])}
        for attempt in range(3):
            try:
                hit = km.find_matching_hierarchy(text)
            except Exception:
                hit = None
            if not hit:
                break
            franchise, character = hit
            found = False
            for name in (character, franchise):
                if not name or name.lower() == "general" or name.lower() in (t.lower() for t in tags):
                    continue
                # Later passes run on leftover words ("Chocolate Cake"), so only trust full names
                # (2+ words) or names from the user's own Known list there.
                if attempt > 0 and len(name.split()) < 2 and name.lower() not in custom:
                    continue
                tags.append(name)
                found = True
            stripped = text
            for name in (character, franchise):
                if name:
                    stripped = re.sub(re.escape(name), " ", stripped, flags=re.IGNORECASE)
            if not found or stripped.strip() == text.strip():
                break
            text = stripped
        return tags

    def _run_tags(self, token, km, work):
        result = {}
        if km is not None:
            for i, (path, title) in enumerate(work):
                if token != self._tag_token:
                    return
                tags = self.tags_for_title(km, title)
                if tags:
                    result[path] = tags
        if token == self._tag_token:
            self.tagsReady.emit(token, result)

    # ── File operations with undo ───────────────────────────────────────────
    def _push_undo(self, op: dict):
        self._undo.append(op)
        del self._undo[:-_UNDO_LIMIT]
        self.undoChanged.emit()

    @Property(bool, notify=undoChanged)
    def canUndo(self) -> bool:
        return bool(self._undo)

    @Property(str, notify=undoChanged)
    def undoLabel(self) -> str:
        return self._undo[-1]["label"] if self._undo else ""

    @Slot('QVariantList', str, result='QVariantMap')
    def moveItems(self, paths: list, destDir: str) -> dict:
        res = self._app.moveItems(paths, destDir)
        pairs = res.get("pairs") or []
        self._remap_pairs(pairs)
        if pairs:
            n = len(pairs)
            self._push_undo({"type": "move", "pairs": pairs,
                             "label": f"Undo move of {n} item{'s' if n != 1 else ''}"})
        return res

    @Slot(str, str, result='QVariantMap')
    def renameItem(self, path: str, newName: str) -> dict:
        res = self._app.renameItem(path, newName)
        if res.get("success") and res.get("new_path") and os.path.normpath(res["new_path"]) != os.path.normpath(path):
            self._remap_pairs([[os.path.normpath(path), res["new_path"]]])
            self._push_undo({"type": "move", "pairs": [[os.path.normpath(path), res["new_path"]]],
                             "label": f"Undo rename of '{os.path.basename(path)}'"})
        return res

    @Slot(str, str, result='QVariantMap')
    def createFolder(self, parent: str, name: str) -> dict:
        name = (name or "").strip()
        if not parent or not os.path.isdir(parent):
            return {"success": False, "error": "The current folder no longer exists.", "path": ""}
        if not name or name in (".", "..") or any(c in _INVALID_NAME_CHARS for c in name) or name.endswith((".", " ")):
            return {"success": False, "error": "That name contains characters that aren't allowed.", "path": ""}
        if self._app and self._app.getPathSafetyInfo(parent).get("is_blocked"):
            return {"success": False, "error": "Creating folders inside a protected system folder is blocked.", "path": ""}
        target = os.path.join(parent, name)
        if os.path.exists(target):
            return {"success": False, "error": f"An item named '{name}' already exists here.", "path": ""}
        try:
            os.makedirs(target)
        except OSError as e:
            return {"success": False, "error": str(e), "path": ""}
        self._push_undo({"type": "mkdir", "path": target, "label": f"Undo new folder '{name}'"})
        return {"success": True, "error": "", "path": target}

    def record_copy(self, created_paths: List[str]):
        """Called by the copy job so a finished copy can be undone (copies go to the Recycle Bin)."""
        if created_paths:
            n = len(created_paths)
            self._push_undo({"type": "copy", "paths": list(created_paths),
                             "label": f"Undo copy of {n} item{'s' if n != 1 else ''}"})

    @Slot(result='QVariantMap')
    def undoLast(self) -> dict:
        if not self._undo:
            return {"success": False, "message": "Nothing to undo."}
        op = self._undo.pop()
        self.undoChanged.emit()
        errors: List[str] = []
        done = 0

        if op["type"] == "move":
            # Move each item back where it came from, newest first
            for src, dst in reversed(op["pairs"]):
                if not os.path.exists(dst):
                    errors.append(f"'{os.path.basename(dst)}' is no longer there")
                    continue
                same_item = os.path.normcase(src) == os.path.normcase(dst)
                if os.path.exists(src) and not same_item:
                    errors.append(f"'{os.path.basename(src)}' already exists in its original place")
                    continue
                try:
                    os.makedirs(os.path.dirname(src), exist_ok=True)
                    shutil.move(dst, src)
                    self._remap_pairs([[dst, src]])
                    done += 1
                except Exception as e:
                    errors.append(f"{os.path.basename(dst)}: {e}")
        elif op["type"] == "mkdir":
            try:
                os.rmdir(op["path"])
                done = 1
            except OSError:
                errors.append(f"'{os.path.basename(op['path'])}' isn't empty any more, so it was left in place")
        elif op["type"] == "copy":
            from PySide6.QtCore import QFile
            for p in op["paths"]:
                if os.path.exists(p):
                    if QFile.moveToTrash(p):
                        done += 1
                    else:
                        errors.append(f"Couldn't move '{os.path.basename(p)}' to the Recycle Bin")

        if errors:
            for e in errors[:5]:
                logger.warning(f"Undo: {e}", category="gallery")
            msg = f"Partly undone ({done} done): {errors[0]}" if done else f"Couldn't undo: {errors[0]}"
            return {"success": done > 0, "message": msg}
        logger.info(f"{op['label'].replace('Undo', 'Undid', 1)}.", category="gallery")
        return {"success": True, "message": op["label"].replace("Undo", "Undid", 1)}
