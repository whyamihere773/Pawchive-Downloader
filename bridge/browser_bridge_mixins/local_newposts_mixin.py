"""
BrowserBridge Local Drives Management & Cross-Site New-Posts Checker Mixin
Decomposed from bridge/browser_bridge.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import Slot

from bridge.browser_bridge_mixins.signals_mixin import BrowserSignalsMixin
from core.browser_providers import browser_registry
from core.local_library import LocalLibraryService
from core.logger import logger


class BrowserLocalNewPostsMixin(BrowserSignalsMixin):
    """Manages local library roots/drives and checks online providers for undownloaded new posts."""

    @Slot(str)
    def addLocalLibraryRoot(self, folder_path: str) -> None:
        clean = (folder_path or "").replace("file:///", "").replace("file://", "").strip()
        if not clean:
            return
        norm = os.path.normpath(clean)
        if not os.path.isdir(norm):
            self.toastRequested.emit(f"Folder does not exist: {norm}", "error")
            return
        settings = self._read_settings()
        roots = list(settings.get("local_library_roots") or [])
        if not any(os.path.normcase(r) == os.path.normcase(norm) for r in roots):
            roots.append(norm)
        settings["local_library_roots"] = roots

        # Re-adding a folder explicitly un-excludes its drive / root path
        drv_key = LocalLibraryService.normalize_drive_key(norm)
        if drv_key:
            settings["excluded_local_drives"] = [
                d for d in (settings.get("excluded_local_drives") or [])
                if LocalLibraryService.normalize_drive_key(d) != drv_key
            ]
        settings["excluded_local_roots"] = [
            r for r in (settings.get("excluded_local_roots") or [])
            if os.path.normcase(os.path.normpath(r)) != os.path.normcase(norm)
        ]
        self._write_settings(settings)
        self.localDrivesChanged.emit()
        if self._browser_mode == "local":
            self.refresh(True)
        self.toastRequested.emit(f"Added local library folder: {norm}", "success")

    @Slot(str)
    def removeLocalLibraryRoot(self, folder_path: str) -> None:
        norm = os.path.normpath((folder_path or "").strip())
        if not norm:
            return
        settings = self._read_settings()
        roots = [
            r for r in (settings.get("local_library_roots") or [])
            if os.path.normcase(os.path.normpath(r)) != os.path.normcase(norm)
        ]
        settings["local_library_roots"] = roots
        # If it still exists as a default/primary/overflow root, track it in excluded_local_roots
        excl_roots = list(settings.get("excluded_local_roots") or [])
        if not any(os.path.normcase(os.path.normpath(r)) == os.path.normcase(norm) for r in excl_roots):
            excl_roots.append(norm)
        settings["excluded_local_roots"] = excl_roots
        self._write_settings(settings)
        self.localDrivesChanged.emit()
        if self._browser_mode == "local":
            self.refresh(True)

    @Slot(str, str)
    @Slot(str)
    def removeLocalDrive(self, drive_label: str, root_path: str = "") -> None:
        drv_key = LocalLibraryService.normalize_drive_key(drive_label or root_path)
        norm_root = os.path.normpath((root_path or "").strip()) if (root_path or "").strip() else ""
        if not drv_key and not norm_root:
            return
        settings = self._read_settings()
        if os.name == "nt" and drv_key and len(drv_key) == 2 and drv_key[1] == ":":
            excl_drvs = list(settings.get("excluded_local_drives") or [])
            if not any(LocalLibraryService.normalize_drive_key(d) == drv_key for d in excl_drvs):
                excl_drvs.append(drv_key)
            settings["excluded_local_drives"] = excl_drvs
        else:
            target = norm_root or drv_key
            excl_roots = list(settings.get("excluded_local_roots") or [])
            if not any(os.path.normcase(os.path.normpath(r)) == os.path.normcase(target) for r in excl_roots):
                excl_roots.append(target)
            settings["excluded_local_roots"] = excl_roots
            settings["local_library_roots"] = [
                r for r in (settings.get("local_library_roots") or [])
                if os.path.normcase(os.path.normpath(r)) != os.path.normcase(target)
            ]
        self._write_settings(settings)

        if drv_key and (self._active_drive or "").strip().upper() == drv_key.upper():
            self._active_drive = "all"
            self.filterStateChanged.emit()

        self.localDrivesChanged.emit()
        if self._browser_mode == "local":
            self.refresh(True)
        else:
            self._local_library.refresh_catalog(heal_moved_paths=False)
        shown = drv_key or norm_root
        self.toastRequested.emit(f"Removed drive {shown} from Local Browser. You can restore it anytime.", "info")

    @Slot()
    def restoreDefaultLocalDrives(self) -> None:
        settings = self._read_settings()
        settings["excluded_local_drives"] = []
        settings["excluded_local_roots"] = []
        self._write_settings(settings)
        self.localDrivesChanged.emit()
        if self._browser_mode == "local":
            self.refresh(True)
        else:
            self._local_library.refresh_catalog(heal_moved_paths=False)
        self.toastRequested.emit("Restored all default & system drives in Local Browser.", "success")

    def _reset_new_posts_state(self, emit: bool = True) -> None:
        self._new_posts_gen += 1
        changed = (
            self._is_checking_new_posts
            or bool(self._new_posts_list)
            or bool(self._creator_search_matches)
            or bool(self._new_posts_creator_key)
            or bool(self._new_posts_status_text)
        )
        self._is_checking_new_posts = False
        self._new_posts_list = []
        self._creator_search_matches = []
        self._new_posts_creator_key = ""
        self._new_posts_status_text = ""
        if emit and changed:
            self.newPostsStateChanged.emit()

    @Slot()
    def clearNewPosts(self) -> None:
        self._reset_new_posts_state(emit=True)

    @staticmethod
    def _normalize_match_token(text: str) -> str:
        s = (text or "").strip().lower()
        s = re.sub(r"\s*\(@[^)]+\)$", "", s)
        s = re.sub(r"\s*[\(\[][a-z0-9_.-]+[\)\]]$", "", s)
        return re.sub(r"[^a-z0-9]", "", s)

    def _save_local_creator_link(self, creator: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
        settings = self._read_settings()
        links = dict(settings.get("local_creator_links") or {})
        prov_id = str(candidate.get("provider_id") or "").strip().lower()
        svc = str(candidate.get("service") or "").strip().lower()
        cid = str(candidate.get("creator_id") or "").strip()
        url = str(candidate.get("url") or "").strip()
        cname = str(candidate.get("name") or creator.get("name") or cid).strip()
        if not prov_id or not svc or svc == "local" or not cid:
            return dict(creator)

        link_payload = {
            "provider_id": prov_id,
            "service": svc,
            "creator_id": cid,
            "name": cname,
            "url": url,
            "post_count": int(candidate.get("post_count") or 0),
            "dm_count": int(candidate.get("dm_count") or 0),
        }
        orig_name = str(creator.get("name") or "").strip().lower()
        orig_key = str(creator.get("key") or "").strip()
        for k in {
            orig_key,
            orig_name,
            f"local:{orig_name}" if orig_name else "",
            cname.lower(),
        }:
            if k:
                links[k] = link_payload
        for d in (creator.get("local_dirs") or []):
            bname = os.path.basename(str(d)).strip().lower()
            if bname:
                links[bname] = link_payload

        settings["local_creator_links"] = links
        self._write_settings(settings)

        updated = dict(creator)
        updated["provider_id"] = prov_id
        updated["service"] = svc
        updated["service_label"] = candidate.get("service_label") or svc.capitalize()
        updated["creator_id"] = cid
        if url:
            updated["url"] = url
        if int(candidate.get("dm_count") or 0) > 0:
            updated["dm_count"] = int(candidate.get("dm_count") or 0)
        return updated

    @staticmethod
    def _resolve_online_provider(
        creator_map: Dict[str, Any],
        creator_links: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, str, str]:
        prov_id = str(creator_map.get("provider_id") or "").strip().lower()
        svc = str(creator_map.get("service") or "").strip().lower()
        cid = str(creator_map.get("creator_id") or "").strip()
        raw_url = str(creator_map.get("url") or "").strip()

        if (not svc or svc == "local" or not cid or not raw_url) and isinstance(creator_links, dict) and creator_links:
            cname_low = str(creator_map.get("name") or "").strip().lower()
            ckey = str(creator_map.get("key") or "").strip()
            saved = (
                creator_links.get(ckey)
                or creator_links.get(f"local:{cname_low}")
                or creator_links.get(cname_low)
            )
            if not saved:
                for d in (creator_map.get("local_dirs") or []):
                    bname = os.path.basename(str(d)).strip().lower()
                    if bname and isinstance(creator_links.get(bname), dict):
                        saved = creator_links[bname]
                        break
            if isinstance(saved, dict):
                prov_id = str(saved.get("provider_id") or prov_id or "").strip().lower()
                svc = str(saved.get("service") or svc or "").strip().lower()
                cid = str(saved.get("creator_id") or cid or "").strip()
                raw_url = str(saved.get("url") or raw_url or "").strip()

        if raw_url:
            try:
                from core.parser import KemonoURLParser
                parsed = KemonoURLParser.parse_url(raw_url)
                if parsed and getattr(parsed, "is_valid", False) and not getattr(parsed, "is_external_provider", False):
                    if not svc or svc == "local":
                        svc = str(parsed.service or "").strip().lower()
                    if not cid:
                        cid = str(parsed.user_id or "").strip()
                    dom = str(parsed.domain or "").lower()
                    if not prov_id:
                        if "coomerfans" in dom:
                            prov_id = "coomerfans"
                        elif "cum.st" in dom:
                            prov_id = "cumst"
                        else:
                            prov_id = "pawchive"
            except Exception:
                pass

        prov = browser_registry.get_provider(prov_id) if prov_id else None
        if prov is None or (svc and svc != "local" and getattr(prov.capabilities, "supported_services", None) and svc not in prov.capabilities.supported_services and prov_id == "pawchive" and svc in ("onlyfans", "fansly", "candfans", "coomerfans")):
            if svc == "coomerfans":
                prov = browser_registry.get_provider("coomerfans")
            elif svc in ("onlyfans", "fansly", "candfans"):
                prov = browser_registry.get_provider("cumst")
            else:
                prov = browser_registry.get_provider(prov_id or "pawchive") or browser_registry.get_provider("pawchive")
        return prov, svc, cid

    def _collect_known_post_signatures(
        self, creator: Dict[str, Any], svc: str, cid: str, cname: str
    ) -> Tuple[Set[str], Set[Tuple[str, str]], Set[str]]:
        known_ids: Set[str] = set()
        known_title_dates: Set[Tuple[str, str]] = set()
        known_filenames: Set[str] = set()

        def _record_filename(fn: str) -> None:
            clean = os.path.basename(str(fn or "").strip()).lower()
            if not clean:
                return
            known_filenames.add(clean)
            stripped = re.sub(r"^\d+_", "", clean)
            if stripped:
                known_filenames.add(stripped)

        def _record_post(p: Dict[str, Any]):
            pid = str(p.get("post_id") or "").strip()
            if pid and pid != "root_files" and not pid.startswith("local_"):
                known_ids.add(pid.lower())
            title = str(p.get("title") or "").strip().lower()
            pub = str(p.get("published_at") or p.get("downloaded_at") or "").strip()[:10]
            if title and pub:
                known_title_dates.add((title, pub))
            for att in (p.get("attachments") or []):
                if isinstance(att, dict):
                    _record_filename(att.get("name") or att.get("local_path") or "")

        creator_key = str(creator.get("key") or "").strip()
        if creator_key:
            lposts, _ = self._local_library.list_local_creator_posts(creator_key, drive_filter="all", limit=0)
            for p in lposts:
                _record_post(p)

        if not known_ids or not known_filenames:
            local_match = self._find_local_creator(svc, cid, cname)
            if local_match and str(local_match.get("key") or "") != creator_key:
                lposts2, _ = self._local_library.list_local_creator_posts(str(local_match.get("key") or ""), drive_filter="all", limit=0)
                for p in lposts2:
                    _record_post(p)

        arch_mgr = getattr(self._app_bridge, "archive_manager", None) if self._app_bridge else None
        if arch_mgr:
            try:
                arch_key = str(creator.get("archive_key") or "").strip()
                if not arch_key:
                    for sm in (arch_mgr.get_creator_summaries() or []):
                        s_svc = str(sm.get("service") or "").strip().lower()
                        s_cid = str(sm.get("creator_id") or "").strip()
                        s_name = str(sm.get("creator_name") or "").strip().lower()
                        if (not svc or s_svc == svc) and ((cid and s_cid.lower() == cid.lower()) or (cname and s_name == cname.lower())):
                            arch_key = str(sm.get("key") or "").strip()
                            break
                if arch_key:
                    for ap in (arch_mgr.get_creator_posts(arch_key) or []):
                        ap_pid = str(ap.get("post_id") or "").strip()
                        if ap_pid:
                            known_ids.add(ap_pid.lower())
                        ap_t = str(ap.get("post_title") or "").strip().lower()
                        ap_d = str(ap.get("downloaded_at") or "").strip()[:10]
                        if ap_t and ap_d:
                            known_title_dates.add((ap_t, ap_d))
            except Exception:
                pass

        return known_ids, known_title_dates, known_filenames

    def _search_creator_across_sites(self, query_name: str, preferred_service: str = "") -> List[Dict[str, Any]]:
        clean_raw = (query_name or "").strip()
        if not clean_raw:
            return []
        stripped = re.sub(r"\s*\(@[^)]+\)$", "", clean_raw).strip()
        stripped = re.sub(r"\s*[\(\[][a-zA-Z0-9_.-]+[\)\]]$", "", stripped).strip()
        queries: List[str] = [stripped or clean_raw]
        alt_space = re.sub(r"[_\-]+", " ", queries[0]).strip()
        if alt_space and alt_space.lower() != queries[0].lower():
            queries.append(alt_space)

        q_norm = self._normalize_match_token(queries[0])
        pref_svc = (preferred_service or "").strip().lower()
        if pref_svc == "local":
            pref_svc = ""

        providers = [p for p in browser_registry.get_active_providers() if p.capabilities().supports_creator_search]
        if not providers:
            return []

        def _probe_provider(prov):
            caps = prov.capabilities()
            manifest = prov.get_manifest_entry()
            found_items: List[Dict[str, Any]] = []
            for q in queries:
                try:
                    svc_arg = pref_svc if (pref_svc and any(k == pref_svc for k, _ in caps.services)) else "all"
                    res = prov.list_creators(query=q, service=svc_arg, offset=0, limit=25)
                    if (not res.items or res.error) and svc_arg != "all":
                        res = prov.list_creators(query=q, service="all", offset=0, limit=25)
                    if not res.error and res.items:
                        for it in res.items:
                            item = dict(it)
                            item["provider_name"] = manifest.get("name") or prov.display_name
                            item["provider_icon"] = manifest.get("icon") or caps.badge_icon
                            item["provider_accent"] = manifest.get("accentColor") or caps.accent_color
                            found_items.append(item)
                        break
                except Exception:
                    continue
            return found_items

        raw_candidates: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(4, len(providers))) as pool:
            futs = [pool.submit(_probe_provider, p) for p in providers]
            for fut in as_completed(futs):
                try:
                    raw_candidates.extend(fut.result() or [])
                except Exception:
                    pass

        scored: List[Dict[str, Any]] = []
        seen_keys: Set[Tuple[str, str, str]] = set()
        for item in raw_candidates:
            pid = str(item.get("provider_id") or "").lower()
            svc = str(item.get("service") or "").lower()
            cid = str(item.get("creator_id") or "")
            uniq = (pid, svc, cid.lower())
            if uniq in seen_keys or not cid:
                continue

            name_raw = str(item.get("name") or "")
            handle_m = re.search(r"\(@([^)]+)\)", name_raw)
            bare_name = re.sub(r"\s*\(@[^)]+\)$", "", name_raw).strip()
            candidates_str = [
                bare_name.lower(),
                (handle_m.group(1).lower() if handle_m else ""),
                cid.lower(),
            ]
            cand_norms = [self._normalize_match_token(s) for s in candidates_str if s]

            score = 0
            if any(c == queries[0].lower() for c in candidates_str if c) or (q_norm and q_norm in cand_norms):
                score = 100
            elif any(c.startswith(queries[0].lower()) for c in candidates_str if c) or (q_norm and any(cn.startswith(q_norm) for cn in cand_norms)):
                score = 85
            elif len(q_norm) >= 3 and (
                any(q_norm in cn for cn in cand_norms) or any(cn in q_norm and len(cn) >= 3 for cn in cand_norms)
            ):
                score = 65

            if score == 0:
                continue

            if pref_svc and svc == pref_svc:
                score += 12
            seen_keys.add(uniq)
            item["match_score"] = score
            item["is_exact_match"] = score >= 100
            item["post_activity"] = int(item.get("post_count") or 0) + int(item.get("favorited_count") or 0) // 100
            scored.append(item)

        scored.sort(key=lambda c: (c.get("match_score", 0), c.get("post_activity", 0), c.get("post_count", 0)), reverse=True)
        return scored[:12]

    def _run_new_posts_check_for_target(
        self,
        creator: Dict[str, Any],
        prov: Any,
        svc: str,
        cid: str,
        cname: str,
        status_prefix: str = "",
    ) -> None:
        known_ids, known_title_dates, known_filenames = self._collect_known_post_signatures(creator, svc, cid, cname)
        self._new_posts_gen += 1
        gen = self._new_posts_gen
        creator_key = str(creator.get("key") or "").strip()

        self._is_checking_new_posts = True
        self._new_posts_list = []
        self._new_posts_creator_key = creator_key
        self._new_posts_status_text = status_prefix or f"Checking '{cname}' online on {prov.display_name} for newer posts…"
        self.newPostsStateChanged.emit()

        def _worker():
            fetched: List[Dict[str, Any]] = []
            err_msg = ""
            try:
                res = prov.list_creator_posts(service=svc, creator_id=cid, creator_name=cname, offset=0, limit=50)
                if res.error:
                    err_msg = res.error
                else:
                    fetched.extend(res.items or [])
                    if res.has_more and known_ids and not any(str(it.get("post_id") or "").strip().lower() in known_ids for it in fetched):
                        res2 = prov.list_creator_posts(service=svc, creator_id=cid, creator_name=cname, offset=50, limit=50)
                        if not res2.error and res2.items:
                            fetched.extend(res2.items)
                if not err_msg and getattr(prov.capabilities(), "supports_dms", False) and (int(creator.get("dm_count") or 0) > 0 or self._creator_section == "dms"):
                    dm_res = prov.list_creator_dms(service=svc, creator_id=cid, creator_name=cname, offset=0, limit=50)
                    if not dm_res.error and dm_res.items:
                        fetched.extend(dm_res.items)
            except Exception as e:
                err_msg = str(e)

            missing: List[Dict[str, Any]] = []
            seen_pids: Set[Tuple[bool, str]] = set()
            for item in fetched:
                p = dict(item)
                pid = str(p.get("post_id") or "").strip()
                pid_low = pid.lower()
                is_dm = bool(p.get("is_dm"))
                if pid_low:
                    dedup_k = (is_dm, pid_low)
                    if dedup_k in seen_pids:
                        continue
                    seen_pids.add(dedup_k)
                    if pid_low in known_ids:
                        continue
                title_low = str(p.get("title") or "").strip().lower()
                pub = str(p.get("published_at") or "").strip()[:10]
                if title_low and pub and (title_low, pub) in known_title_dates:
                    continue
                if known_filenames:
                    att_names = [
                        os.path.basename(str(a.get("name") or "")).strip().lower()
                        for a in (p.get("attachments") or [])
                        if isinstance(a, dict) and a.get("name")
                    ]
                    if att_names and all(an in known_filenames for an in att_names):
                        continue
                p["is_on_disk"] = False
                missing.append(p)

            def _apply():
                if gen != self._new_posts_gen:
                    return
                self._is_checking_new_posts = False
                if err_msg:
                    self._new_posts_list = []
                    self._new_posts_status_text = f"Update check failed: {err_msg}"
                    self.newPostsStateChanged.emit()
                    self.toastRequested.emit(f"Could not check newer posts for '{cname}': {err_msg}", "warning")
                    return
                self._new_posts_list = missing
                if missing:
                    self._new_posts_status_text = f"Found {len(missing)} newer/missing item(s) for '{cname}' ({prov.display_name})."
                    self.newPostsStateChanged.emit()
                    self.toastRequested.emit(self._new_posts_status_text, "success")
                else:
                    self._new_posts_status_text = f"'{cname}' is up to date on {prov.display_name} — no missing recent posts."
                    self.newPostsStateChanged.emit()
                    self.toastRequested.emit(self._new_posts_status_text, "info")

            self._callOnGui.emit(_apply)

        threading.Thread(target=_worker, daemon=True, name="BrowserCheckNewPosts").start()

    @Slot("QVariantMap")
    def searchCreatorAcrossSites(self, creator_map: Dict[str, Any]) -> None:
        creator = dict(creator_map) if (creator_map and isinstance(creator_map, dict)) else dict(self._selected_creator)
        if not creator:
            self.toastRequested.emit("Select a creator first to search across sites.", "warning")
            return
        cname = str(creator.get("name") or creator.get("creator_id") or "creator").strip()
        pref_svc = str(creator.get("service") or "").strip().lower()
        self._new_posts_gen += 1
        gen = self._new_posts_gen
        self._is_checking_new_posts = True
        self._new_posts_list = []
        self._creator_search_matches = []
        self._new_posts_creator_key = str(creator.get("key") or "").strip()
        self._new_posts_status_text = f"Searching cum.st, Pawchive, and CoomerFans for '{cname}'…"
        self.newPostsStateChanged.emit()

        def _worker():
            matches = self._search_creator_across_sites(cname, pref_svc)

            def _apply():
                if gen != self._new_posts_gen:
                    return
                self._creator_search_matches = matches
                if not matches:
                    self._is_checking_new_posts = False
                    self._new_posts_status_text = f"Could not find '{cname}' on cum.st, Pawchive, or CoomerFans."
                    self.newPostsStateChanged.emit()
                    self.toastRequested.emit(self._new_posts_status_text, "warning")
                elif len(matches) == 1:
                    best = matches[0]
                    updated = self._save_local_creator_link(creator, best)
                    if self._selected_creator.get("key") == creator.get("key"):
                        self._selected_creator = updated
                        self.selectedCreatorChanged.emit()
                    prov = browser_registry.get_provider(str(best.get("provider_id") or ""))
                    b_svc = str(best.get("service") or "")
                    b_cid = str(best.get("creator_id") or "")
                    b_name = str(best.get("name") or cname)
                    if prov and b_svc and b_cid:
                        self._run_new_posts_check_for_target(
                            updated,
                            prov,
                            b_svc,
                            b_cid,
                            b_name,
                            status_prefix=f"Matched '{cname}' → {b_name} ({best.get('service_label', b_svc)} · {best.get('provider_name', prov.display_name)}) — checking posts…",
                        )
                    else:
                        self._is_checking_new_posts = False
                        self._new_posts_status_text = f"Found 1 match for '{cname}'."
                        self.newPostsStateChanged.emit()
                else:
                    self._is_checking_new_posts = False
                    self._new_posts_status_text = f"Found {len(matches)} match(es) across sites for '{cname}' — pick a profile to check for newer posts:"
                    self.newPostsStateChanged.emit()

            self._callOnGui.emit(_apply)

        threading.Thread(target=_worker, daemon=True, name="BrowserCrossSiteCreatorSearch").start()

    @Slot("QVariantMap")
    def selectCreatorMatchAndCheck(self, candidate_map: Dict[str, Any]) -> None:
        if not candidate_map or not isinstance(candidate_map, dict):
            return
        creator = dict(self._selected_creator or {})
        updated = self._save_local_creator_link(creator, candidate_map)
        if creator and self._selected_creator.get("key") == creator.get("key"):
            self._selected_creator = updated
            self.selectedCreatorChanged.emit()
        prov = browser_registry.get_provider(str(candidate_map.get("provider_id") or ""))
        svc = str(candidate_map.get("service") or "").strip().lower()
        cid = str(candidate_map.get("creator_id") or "").strip()
        cname = str(candidate_map.get("name") or updated.get("name") or cid).strip()
        if not prov or not svc or not cid:
            self.toastRequested.emit("Selected match is missing provider details.", "warning")
            return
        if self._browser_mode == "local":
            threading.Thread(
                target=lambda: self._local_library.refresh_catalog(heal_moved_paths=False),
                daemon=True,
            ).start()
        self._run_new_posts_check_for_target(
            updated,
            prov,
            svc,
            cid,
            cname,
            status_prefix=f"Checking {cname} ({candidate_map.get('service_label', svc)} · {prov.display_name}) for newer posts…",
        )

    @Slot("QVariantMap")
    def checkCreatorNewPosts(self, creator_map: Dict[str, Any]) -> None:
        creator = dict(creator_map) if (creator_map and isinstance(creator_map, dict)) else dict(self._selected_creator)
        if not creator:
            self.toastRequested.emit("Select a creator first to check for newer posts.", "warning")
            return

        prov, svc, cid = self._resolve_online_provider(creator, self._get_creator_links())
        cname = str(creator.get("name") or cid or "creator").strip()
        if not prov or not svc or svc == "local" or not cid:
            self.searchCreatorAcrossSites(creator)
            return

        self._creator_search_matches = []
        self._run_new_posts_check_for_target(creator, prov, svc, cid, cname)

    @Slot("QVariantList", bool)
    @Slot("QVariantList")
    def downloadNewPosts(self, urls: Optional[List[str]] = None, auto_start: bool = True) -> int:
        clean_urls = [str(u or "").strip() for u in (urls or []) if str(u or "").strip()]
        if not clean_urls:
            clean_urls = [str(p.get("url") or "").strip() for p in self._new_posts_list if str(p.get("url") or "").strip()]
        if not clean_urls:
            self.toastRequested.emit("No newer post URLs available to download.", "warning")
            return 0
        if not self._app_bridge:
            self.toastRequested.emit("Downloader bridge is not connected.", "warning")
            return 0
        if hasattr(self._app_bridge, "enqueueBatchUrls"):
            self._app_bridge.enqueueBatchUrls(clean_urls, auto_start)
        else:
            self._app_bridge.currentUrl = "\n".join(clean_urls)
            self._app_bridge.startDownload() if auto_start else self._app_bridge.addToQueue()

        url_set = set(clean_urls)
        self._new_posts_list = [p for p in self._new_posts_list if str(p.get("url") or "").strip() not in url_set]
        self._new_posts_status_text = f"Queued {len(clean_urls)} newer post(s) in Downloader."
        self.newPostsStateChanged.emit()
        self.toastRequested.emit(self._new_posts_status_text, "success")
        return len(clean_urls)
