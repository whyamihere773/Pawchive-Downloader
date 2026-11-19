"""
BrowserBridge Canonical URL Resolution, Clipboard Copy, Redownload & Drive Relocation Mixin
Decomposed from bridge/browser_bridge.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import inspect
import os
import threading
from typing import Any, Dict, Tuple

from PySide6.QtCore import QUrl, Slot

from bridge.browser_bridge_mixins.signals_mixin import BrowserSignalsMixin
from core.browser_providers import browser_registry
from core.local_library import LocalLibraryService
from core.logger import logger
from core.parser import normalize_archive_url


class BrowserLinksRelocateMixin(BrowserSignalsMixin):
    """Resolves canonical creator/post/attachment URLs, handles clipboard actions, redownloads, and moves."""

    def _resolve_creator_url(self, creator_map: Optional[Dict[str, Any]] = None) -> str:
        creator = dict(creator_map) if (creator_map and isinstance(creator_map, dict)) else dict(self._selected_creator or {})
        if not creator:
            return ""
        raw_url = str(creator.get("url") or "").strip()
        if raw_url.startswith(("http://", "https://")):
            return normalize_archive_url(raw_url)
        prov, svc, cid = self._resolve_online_provider(creator, self._get_creator_links())
        if prov and svc and svc != "local" and cid:
            built = str(prov.build_creator_url(svc, cid) or "").strip()
            if built:
                return normalize_archive_url(built)
        if raw_url:
            return raw_url
        for d in (creator.get("local_dirs") or []):
            d_str = str(d or "").strip()
            if d_str:
                return QUrl.fromLocalFile(d_str).toString()
        return ""

    def _resolve_post_online_context(
        self, post_map: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], str, str, str, str, str]:
        post = dict(post_map) if (post_map and isinstance(post_map, dict)) else dict(self._selected_post or {})
        if not post:
            return {}, "", "", "", "", ""
        svc = str(post.get("service") or "").strip().lower()
        cid = str(post.get("creator_id") or "").strip()
        pid = str(post.get("post_id") or "").strip()
        prov_id = str(post.get("provider_id") or "").strip().lower()
        is_dm = bool(post.get("is_dm"))
        url = str(post.get("url") or "").strip()

        if svc in ("", "local") or not cid or not prov_id:
            source_creator = dict(self._selected_creator or {})
            if not source_creator:
                source_creator = {
                    "provider_id": prov_id,
                    "service": svc,
                    "creator_id": cid,
                    "name": post.get("creator_name") or "",
                    "key": f"{prov_id}:{svc}:{cid}" if (prov_id and svc and cid) else "",
                }
            r_prov, r_svc, r_cid = self._resolve_online_provider(source_creator, self._get_creator_links())
            if r_prov and r_svc and r_cid:
                prov_id = r_prov.provider_id
                svc = r_svc
                cid = r_cid

        if not url:
            url = LocalLibraryService._build_post_online_url(prov_id, svc, cid, pid, is_dm=is_dm)
        if not url and prov_id and svc and svc != "local" and cid and pid and pid != "root_files":
            prov = browser_registry.get_provider(prov_id)
            if prov:
                url = prov.build_dm_url(svc, cid, pid) if is_dm else prov.build_post_url(svc, cid, pid)
        return post, prov_id, svc, cid, pid, normalize_archive_url(str(url or "").strip())

    def _resolve_post_url(self, post_map: Optional[Dict[str, Any]] = None) -> str:
        post, _prov_id, _svc, _cid, _pid, url = self._resolve_post_online_context(post_map)
        if url:
            return url
        if not post:
            return ""
        folder = str(post.get("local_folder") or "").strip()
        if folder:
            return QUrl.fromLocalFile(folder).toString()
        for att in post.get("attachments") or []:
            if isinstance(att, dict):
                lp = str(att.get("local_path") or "").strip()
                if lp:
                    return QUrl.fromLocalFile(os.path.dirname(lp)).toString()
        return ""

    def _resolve_attachment_url(
        self,
        att_map: Optional[Dict[str, Any]] = None,
        _post_map: Optional[Dict[str, Any]] = None,
    ) -> str:
        att = dict(att_map) if (att_map and isinstance(att_map, dict)) else {}
        if not att:
            return ""
        for key in ("url", "source_url", "sourceUrl"):
            val = str(att.get(key) or "").strip()
            if val:
                return val
        local_path = str(att.get("local_path") or att.get("localPath") or "").strip()
        if local_path:
            return QUrl.fromLocalFile(local_path).toString()
        thumb = str(att.get("thumbnail_url") or att.get("thumbnailUrl") or "").strip()
        return thumb

    def _copy_text(self, text: str, label: str = "Link") -> bool:
        clean = str(text or "").strip()
        if not clean:
            self.toastRequested.emit(f"No {label.lower()} available to copy.", "warning")
            return False
        try:
            if self._app_bridge and hasattr(self._app_bridge, "copyToClipboard"):
                self._app_bridge.copyToClipboard(clean)
            else:
                from PySide6.QtGui import QGuiApplication
                cb = QGuiApplication.clipboard()
                if cb:
                    cb.setText(clean)
            self.toastRequested.emit(f"{label} copied to clipboard.", "success")
            return True
        except Exception as e:
            logger.debug(f"[BrowserBridge] Failed to copy {label.lower()}: {e}", category="system")
            self.toastRequested.emit(f"Could not copy {label.lower()}.", "error")
            return False

    @Slot("QVariantMap", result=str)
    def resolveCreatorUrl(self, creator_map: Dict[str, Any]) -> str:
        return self._resolve_creator_url(creator_map)

    @Slot("QVariantMap", result=str)
    def resolvePostUrl(self, post_map: Dict[str, Any]) -> str:
        return self._resolve_post_url(post_map)

    @Slot("QVariantMap", "QVariantMap", result=str)
    def resolveAttachmentUrl(self, att_map: Dict[str, Any], post_map: Dict[str, Any]) -> str:
        return self._resolve_attachment_url(att_map, post_map)

    @Slot(str, result=bool)
    def copyLink(self, url: str) -> bool:
        return self._copy_text(url, "Link")

    @Slot(str, str, result=bool)
    def copyLabeledLink(self, url: str, label: str) -> bool:
        return self._copy_text(url, label or "Link")

    @Slot("QVariantMap", result=bool)
    def copyCreatorLink(self, creator_map: Dict[str, Any]) -> bool:
        return self._copy_text(self._resolve_creator_url(creator_map), "Creator link")

    @Slot("QVariantMap", result=bool)
    def copyPostLink(self, post_map: Dict[str, Any]) -> bool:
        return self._copy_text(self._resolve_post_url(post_map), "Post link")

    @Slot("QVariantMap", "QVariantMap", result=bool)
    def copyAttachmentLink(self, att_map: Dict[str, Any], post_map: Dict[str, Any]) -> bool:
        return self._copy_text(self._resolve_attachment_url(att_map, post_map), "File link")

    @Slot("QVariantMap", result=bool)
    def redownloadPost(self, post_map: Dict[str, Any]) -> bool:
        post, _prov_id, svc, _cid, pid, url = self._resolve_post_online_context(post_map)
        if not post:
            self.toastRequested.emit("Select a post first to redownload it.", "warning")
            return False

        if not url:
            self.toastRequested.emit("This local post folder doesn't have an online source URL to redownload.", "warning")
            return False
        if not self._app_bridge:
            self.toastRequested.emit("Downloader bridge is not connected.", "warning")
            return False

        arch_mgr = getattr(self._app_bridge, "archive_manager", None)
        if arch_mgr and svc and pid:
            try:
                arch_mgr.delete_by_post(svc, pid)
            except Exception as e:
                logger.debug(f"[BrowserBridge] Could not clear archive entry for post {svc}:{pid}: {e}", category="archive")

        if hasattr(self._app_bridge, "enqueueBatchUrls"):
            self._app_bridge.enqueueBatchUrls([url], True, True)
        else:
            self._app_bridge.currentUrl = url
            self._app_bridge.startDownload()

        title = str(post.get("title") or pid or "post").strip()
        self.toastRequested.emit(f"Queued '{title}' for fresh redownload (overwriting existing files).", "success")
        return True

    @Slot("QVariantMap")
    def redownloadPostAsync(self, post_map: Dict[str, Any]) -> None:
        """Non-blocking companion to redownloadPost: clears archive records on a worker thread before queueing."""
        post, _prov_id, svc, _cid, pid, url = self._resolve_post_online_context(post_map)
        if not post:
            self.toastRequested.emit("Select a post first to redownload it.", "warning")
            return
        if not url:
            self.toastRequested.emit("This local post folder doesn't have an online source URL to redownload.", "warning")
            return
        if not self._app_bridge:
            self.toastRequested.emit("Downloader bridge is not connected.", "warning")
            return

        title = str(post.get("title") or pid or "post").strip()
        arch_mgr = getattr(self._app_bridge, "archive_manager", None)

        def _worker():
            if arch_mgr and svc and pid:
                try:
                    arch_mgr.delete_by_post(svc, pid)
                except Exception as e:
                    logger.debug(f"[BrowserBridge] Could not clear archive entry for post {svc}:{pid}: {e}", category="archive")

            def _dispatch():
                if hasattr(self._app_bridge, "enqueueBatchUrls"):
                    self._app_bridge.enqueueBatchUrls([url], True, True)
                else:
                    self._app_bridge.currentUrl = url
                    self._app_bridge.startDownload()
                self.toastRequested.emit(f"Queued '{title}' for fresh redownload (overwriting existing files).", "success")

            self._callOnGui.emit(_dispatch)

        threading.Thread(target=_worker, daemon=True, name="BrowserRedownloadWorker").start()

    @Slot(str, str)
    def moveCreatorToDrive(self, creator_key: str, target_root_dir: str) -> None:
        """
        Relocates an artist's on-disk folder(s) to another drive/folder in a background thread,
        emitting live progress for the Newtonian progress bar and syncing ArchiveManager + Watchlist.
        """
        clean_target = (target_root_dir or "").replace("file:///", "").replace("file://", "").strip()
        if not creator_key or not clean_target:
            return
        self._relocate_cancel.clear()

        def _on_prog(done: int, total: int, fname: str):
            self._callOnGui.emit(lambda: self.relocationProgress.emit(creator_key, done, total, fname))

        def _worker():
            res = self._local_library.relocate_creator_to_drive(
                creator_key=creator_key,
                target_root_dir=clean_target,
                cancel_event=self._relocate_cancel,
                progress_cb=_on_prog,
            )

            def _done():
                ok = bool(res.get("ok"))
                if ok:
                    msg = f"Moved {res.get('moved', 0)} file(s) to {res.get('dest_dir', clean_target)} ({res.get('relocated_records', 0)} archive records updated)."
                    self.toastRequested.emit(msg, "success")
                else:
                    msg = str(res.get("error") or (res.get("errors") or ["Move failed"])[0])
                    self.toastRequested.emit(msg, "error")
                self.relocationFinished.emit(creator_key, ok, msg)
                self.localDrivesChanged.emit()
                self.refresh(False)

            self._callOnGui.emit(_done)

        threading.Thread(target=_worker, daemon=True, name="BrowserDriveMoveWorker").start()

    @Slot()
    def cancelMoveCreator(self) -> None:
        self._relocate_cancel.set()
