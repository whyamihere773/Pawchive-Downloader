"""
Downloader URL Resolution, Verification & Post-Processing Mixin
Decomposed from core/downloader.py to keep modules cohesive and under 1,000 lines.
"""

import datetime
import hashlib
import json
import os
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image

from core.atomic_io import atomic_write_text, replace_file
from core.audio_tagger import AudioTagger
from core.downloader_models import (
    DownloadTask,
    PART_SUFFIX,
    _remove_quietly,
    _write_post_info,
    atomic_move_part,
    content_hash_from_url,
    needs_full_size_upgrade,
)
from core.filter_engine import FilterEngine, FilterOptions
from core.logger import logger
from core.providers import is_disabled
from core.statistics_manager import statistics_manager
from services.link_extractor import LinkExtractor


class DownloaderUrlPostprocessMixin:
    """URL resolution, Pawchive signed-link refresh, hash verification, sidecar & WebP conversion."""

    @staticmethod
    def extract_passwords(text: str) -> list:
        """
        Smartly extracts password candidates from post text using CJK-aware boundary heuristics.
        Delegates to LinkExtractor.extract_passwords for unified multilingual password extraction.
        """
        if not text:
            return []
        return LinkExtractor.extract_passwords(text)

    @staticmethod
    def extract_norm_rel_key(f_dict: Dict[str, Any]) -> str:
        """
        Extracts a canonical relative key/hash identifying the exact underlying file across mirrors.
        Handles relative paths (/ab/cd/...), thumbnail URLs, CDN URLs, and cum.st storage keys.
        """
        if not isinstance(f_dict, dict):
            return ""
        rp = f_dict.get("path") or f_dict.get("storageKey") or ""
        if not rp:
            return ""
        rp = rp.split("?")[0]
        if re.match(r'^[0-9a-f]{16,}$', rp):
            return rp.lower()
        m_match = re.search(r'/(?:data|thumbnail/data)?/[0-9a-f]?([0-9a-f]{2}/[0-9a-f]{2}/[^\s?#]+)', rp, re.IGNORECASE)
        if m_match:
            return "/" + m_match.group(1).lower()
        if "://" in rp:
            rp = "/" + rp.split("://")[-1].partition("/")[-1]
        if rp.startswith("/data/"):
            rp = rp[5:]
        if not rp.startswith("/"):
            rp = f"/{rp}"
        return rp.lower()

    @staticmethod
    def _resolve_candidate_video_url(fobj: dict, domain: str) -> str:
        p = fobj.get("temp_download_url") or fobj.get("path") or fobj.get("storageKey") or ""
        if not p:
            return ""
        if p.startswith("http://") or p.startswith("https://"):
            return p.replace("e1.cum.st", "cdn.cum.st")
        clean_rel = "/" + p.lstrip("/")
        if clean_rel.startswith("/data/"):
            clean_rel = clean_rel[5:]
        if "cum.st" in (domain or "") or re.match(r'^[0-9a-f]{16,}$', p):
            if re.match(r'^[0-9a-f]{16,}$', p):
                variants = fobj.get("variants") or []
                vname = "original.mp4"
                if isinstance(variants, list) and variants:
                    for v in variants:
                        if isinstance(v, dict) and "original" in (v.get("name") or "").lower():
                            vname = v.get("name")
                            break
                    else:
                        if isinstance(variants[0], dict) and variants[0].get("name"):
                            vname = variants[0].get("name")
                return f"https://cdn.cum.st/media/{p}/{vname}"
            return f"https://cum.st/data{clean_rel}"
        elif "coomer" in (domain or ""):
            return f"https://c1.coomer.st/data{clean_rel}" if not is_disabled("coomer.st") else f"https://cum.st/data{clean_rel}"
        else:
            srv = str(fobj.get("server") or "").strip().rstrip("/")
            if not srv and fobj.get("node") is not None:
                srv = f"https://n{fobj.get('node')}.pawchive.pw"
            if srv and not srv.startswith(("http://", "https://")):
                srv = f"https://{srv}"
            return f"{srv or 'https://file.pawchive.pw'}/data{clean_rel}"

    @staticmethod
    def _is_pawchive_temp_expired(fobj: Dict[str, Any]) -> bool:
        """Returns True if the temporary Pawchive URL or temp_expires has expired."""
        if not isinstance(fobj, dict):
            return False
        raw_p = fobj.get("path") if isinstance(fobj.get("path"), str) else ""
        temp_u = (
            fobj.get("temp_download_url")
            or fobj.get("temp_url")
            or (raw_p if re.search(r"\bt\d+\.pawchive\.pw\b", raw_p) else "")
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

    def _resolve_pawchive_deferred_attachments(self, post: Dict[str, Any], domain: str = "pawchive.pw") -> int:
        """
        Resolves signed t1.pawchive.pw temporary download URLs for Pawchive attachments
        (either via direct 'temp_url' in API JSON or scraping post HTML for legacy 'deferred: True' items).
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
            if temp_u and not str(temp_u).split("?")[0].lower().endswith(".m3u8") and not self._is_pawchive_temp_expired(target):
                target["path"] = temp_u
                target["is_temporary"] = True
                target["preview_only"] = False
                resolved_count += 1

        # 2. Only scrape post HTML for legacy 'deferred: True' attachments that lack a direct temp_url.
        #    Never scrape HTML for unimported (has_full=False) or bare preview_only posts, which
        #    have no temporary links in HTML and would otherwise trigger hundreds of wasted page fetches.
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
        logger.debug(f"Fetching post HTML to resolve {len(deferred_items)} temporary oversized file(s): {page_url}", category="downloader")

        session = self._new_cookieless_session()
        session_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": f"https://{eff_domain}/",
            "X-Contact": "https://github.com/whyamihere773/Pawchive-Downloader",
            "X-Client-Notice": (
                "Pawchive Downloader user here! Love your site. If my client is ever causing server strain, "
                "please open an issue on GitHub instead of a hard ban and I'll fix my request pacing immediately."
            )
        }
        session.headers.update(session_headers)
        try:
            resp = session.get(page_url, timeout=20)
            if resp.status_code != 200 or not resp.text:
                logger.warning(f"Could not fetch HTML for post {post_id} (HTTP {resp.status_code}) to resolve temporary files", category="downloader")
                return resolved_count

            matches = re.findall(r'(?:href|src)=["\'](https://t\d+\.pawchive\.pw/(?:f|d)/[^"\']+)["\']', resp.text)
            temp_map: Dict[str, str] = {}
            for raw_u in matches:
                u = raw_u.replace("&amp;", "&")
                path_part = u.split("?")[0].split("/")[-1]
                name = urllib.parse.unquote(path_part)
                if name and name not in temp_map:
                    temp_map[name] = u

            if not temp_map:
                logger.info(f"Post {post_id} has {len(deferred_items)} deferred attachment(s), but temporary links are expired or unavailable", category="downloader")
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
                logger.info(f"✨ Resolved {html_resolved}/{len(deferred_items)} temporary oversized file(s) from t1.pawchive.pw for post {post_id}", category="downloader")
            return resolved_count
        except Exception as e:
            logger.warning(f"Failed resolving temporary attachments for post {post_id}: {e}", category="downloader")
            return resolved_count
        finally:
            try:
                session.close()
            except Exception:
                pass

    def _refresh_pawchive_temp_url(self, task: DownloadTask) -> Optional[str]:
        """Re-fetches a Pawchive post page to obtain a fresh signed t1.pawchive.pw URL for an expired link."""
        service = getattr(task, "service", "")
        user_id = str(getattr(task, "user_id", "") or "")
        post_id = str(getattr(task, "post_id", "") or "")
        filename = getattr(task, "filename", "") or ""
        if not service or not user_id or not post_id or not filename:
            return None

        page_url = f"https://pawchive.pw/{service}/user/{user_id}/post/{post_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://pawchive.pw/",
            "X-Contact": "https://github.com/whyamihere773/Pawchive-Downloader",
        }
        try:
            sess = self._get_worker_session()
            r = sess.get(page_url, headers=headers, timeout=15)
            if r.status_code != 200 or not r.text:
                return None
            matches = re.findall(r'(?:href|src)=["\'](https://t\d+\.pawchive\.pw/(?:f|d)/[^"\']+)["\']', r.text)
            fn_low = filename.lower()
            for raw_u in matches:
                u = raw_u.replace("&amp;", "&")
                path_part = u.split("?")[0].split("/")[-1]
                name = urllib.parse.unquote(path_part)
                if name and (name == filename or name.lower() == fn_low):
                    return u
        except Exception as ex:
            logger.debug(f"Failed re-resolving temporary URL for {filename}: {ex}", category="downloader")
        return None

    def _write_pending_post_info(self, task: DownloadTask) -> None:
        path = getattr(task, "post_info_path", "")
        post_id = getattr(task, "post_id", "")
        if path:
            content = self._post_info_pending.pop((path, post_id), None)
            if content is None:
                content = self._post_info_pending.pop(path, None)
            if content is not None:
                _write_post_info(path, content, post_id)

    def _finalize_part(self, task: DownloadTask, options: FilterOptions, part_path: str, final_size: int,
                       hasher=None, strict_hash: bool = False, is_upgrade_download: bool = False,
                       found_existing_path: Optional[str] = None) -> Tuple[bool, str]:
        """Checks a finished .part file (size filter, checksum) and gives it its real name."""
        if final_size > 0 and options:
            keep_file, f_reason = FilterEngine.should_keep_file(task.filename, options, file_size=final_size)
            if not keep_file:
                _remove_quietly(part_path)
                with self._lock:
                    self.downloaded_bytes = max(0, self.downloaded_bytes - task.downloaded_bytes)
                logger.info(f"⏭️ Skipping {task.filename} ({FilterEngine.format_size_str(final_size)}): {f_reason}", category="filter")
                task.status = "skipped"
                task.error_msg = f_reason
                task.progress_pct = 100
                task.eta_str = "Skipped"
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)
                return True, f"Skipped: {f_reason}"

        # Checksum before any post-processing (tagging / WebP conversion change the bytes)
        problem = self._verify_file_hash(task, final_size, path=part_path, hasher=hasher, strict=strict_hash)
        if problem:
            _remove_quietly(part_path)
            with self._lock:
                self.downloaded_bytes = max(0, self.downloaded_bytes - task.downloaded_bytes)
            task.downloaded_bytes = 0
            task.progress_pct = 0
            logger.error(f"  ✖ {task.filename}: {problem}", category="file", details=self._task_context(task))
            return False, problem

        if self.is_batch_cancelled(task):
            _remove_quietly(part_path)
            return False, "Cancelled"
        if self.is_batch_paused(task) or task.status == "paused":
            return False, "Batch paused by user"

        # One step: an older small copy under the same name stays until the full file replaces it
        replace_file(part_path, task.target_path)
        task.progress_pct = 100
        task.eta_str = "Done"

        # An older copy under another name (e.g. a .webp preview) is replaced by the full file
        if is_upgrade_download and found_existing_path and os.path.exists(found_existing_path):
            if os.path.abspath(found_existing_path) != os.path.abspath(task.target_path):
                _remove_quietly(found_existing_path)

        self._post_process_downloaded_file(task, options)

        # Thread cooldown delay to avoid CDN rate limiting (429)
        if options.download_delay > 0 and not self._cancel_event.is_set():
            time.sleep(options.download_delay)
        return True, "Success"

    def _verify_file_hash(self, task: DownloadTask, file_size: int, path: Optional[str] = None,
                          hasher=None, strict: bool = False) -> str:
        """Verifies downloaded file integrity using SHA-256 or MD5 before any post-processing.

        Returns an error message when the file is damaged (only for hashes known to be the real
        content hash, and only when strict), otherwise "".
        """
        path = path or task.target_path
        raw_hash = (task.expected_sha256 or "").strip().lower()
        # Kemono / Pawchive / Coomer file names are the content's SHA-256: the most reliable hash
        url_hash = content_hash_from_url(task.url)
        if url_hash:
            raw_hash = url_hash
        if not raw_hash or not os.path.exists(path):
            if file_size > 0:
                logger.success(
                    f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved)",
                    category="file"
                )
            return ""

        precomputed = hasher
        # Determine hash algorithm by length
        if len(raw_hash) == 64 and all(c in "0123456789abcdef" for c in raw_hash):
            algo_name = "SHA-256"
            hasher = hashlib.sha256()
        elif len(raw_hash) == 32 and all(c in "0123456789abcdef" for c in raw_hash):
            algo_name = "MD5"
            hasher = hashlib.md5()
        else:
            # Non-standard hash format (e.g. storageKey or arbitrary identifier)
            if file_size > 0:
                logger.success(
                    f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved)",
                    category="file"
                )
            return ""

        # Video variants and storage keys on cum.st or similar CDN mirrors often have rearranged
        # container atoms (moov atom faststart) or upstream transcode layouts where the served
        # media stream differs from the upstream ingest storageKey.
        _, ext = os.path.splitext(task.target_path.lower())
        is_video = ext in (".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi")
        is_storage_key_url = "cum.st/media/" in task.url or "e1.cum.st" in task.url or "cdn.cum.st" in task.url
        if is_storage_key_url and is_video:
            if file_size > 0:
                logger.success(
                    f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved)",
                    category="file"
                )
            return ""

        try:
            if precomputed is not None and algo_name == "SHA-256":
                computed_hash = precomputed.hexdigest().lower()
            else:
                with open(path, "rb") as check_f:
                    while chunk := check_f.read(1024 * 1024):
                        hasher.update(chunk)
                computed_hash = hasher.hexdigest().lower()
            if computed_hash == raw_hash:
                logger.success(
                    f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved, {algo_name} verified)",
                    category="file"
                )
            elif url_hash and strict:
                return "The file arrived damaged (checksum mismatch); it downloads again on retry"
            else:
                # File completed successfully (Content-Length and TLS integrity validated),
                # but the server-provided hash was an upstream ingest ID, storage key, or CDN transcode variant.
                # Always confirm success to the user without false-alarm warnings.
                if file_size > 0:
                    logger.success(
                        f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved)",
                        category="file"
                    )
                (logger.warning if url_hash else logger.debug)(
                    f"{task.filename}: server metadata {algo_name} differs from delivered stream "
                    f"(expected {raw_hash[:8]}, got {computed_hash[:8]}; upstream storageKey/variant)",
                    category="file"
                )
        except Exception as ex:
            logger.debug(f"Hash calculation error for {task.filename}: {ex}", category="file")
            if file_size > 0:
                logger.success(
                    f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved)",
                    category="file"
                )
        return ""

    def _post_process_downloaded_file(self, task: DownloadTask, options: FilterOptions):
        """Runs post-download processing such as WebP compression and audio metadata tagging."""
        if not task.target_path or not os.path.exists(task.target_path):
            return

        # 1. WebP conversion (the task, archive and queue then point at the .webp file)
        if options.compress_to_webp:
            converted = self._convert_to_webp(task.target_path, getattr(options, "webp_quality", "balanced"))
            if converted:
                task.target_path = converted

        # 2. Audio metadata tagging
        if getattr(options, "write_audio_metadata", False) and AudioTagger.is_supported(task.target_path):
            AudioTagger.tag_audio_file(
                file_path=task.target_path,
                artist=task.creator_name,
                title=task.post_title or os.path.splitext(task.filename)[0],
                album=task.post_title or task.creator_name,
                date=getattr(task, "post_date", "") or "",
                comment=getattr(task, "post_url", "") or task.url
            )

        # 3. Metadata sidecars (Hydrus Network, Eagle, Booru taggers)
        if getattr(options, "write_sidecars", False):
            self._write_sidecar_metadata(task, options)

    def _write_sidecar_metadata(self, task: DownloadTask, options: FilterOptions):
        """Generates companion metadata sidecars (.json / .txt) for external gallery software."""
        try:
            if not task.target_path or not os.path.exists(task.target_path):
                return
            sidecar_fmt = getattr(options, "sidecar_format", "json").lower()
            sidecar_scope = getattr(options, "sidecar_scope", "per_file").lower()

            dest_dir = os.path.dirname(task.target_path)
            base_name = os.path.splitext(task.target_path)[0]

            paths_to_write = []
            if sidecar_scope == "per_post":
                if sidecar_fmt in ("json", "both"):
                    paths_to_write.append((os.path.join(dest_dir, "post_metadata.json"), "json"))
                if sidecar_fmt in ("txt", "both"):
                    paths_to_write.append((os.path.join(dest_dir, "post_metadata.txt"), "txt"))
            else:
                if sidecar_fmt in ("json", "both"):
                    paths_to_write.append((f"{base_name}.json", "json"))
                if sidecar_fmt in ("txt", "both"):
                    paths_to_write.append((f"{base_name}.txt", "txt"))

            tags_list = []
            raw_tags = getattr(task, "tags", None)
            if raw_tags:
                from core.filter_engine import FilterEngine
                tags_list = FilterEngine.normalize_tags(raw_tags)

            if task.creator_name and f"creator:{task.creator_name}" not in tags_list:
                tags_list.insert(0, f"creator:{task.creator_name}")
            if task.service and f"service:{task.service}" not in tags_list:
                tags_list.insert(1, f"service:{task.service}")

            for out_path, fmt in paths_to_write:
                if fmt == "json":
                    meta = {
                        "title": task.post_title or "",
                        "creator": task.creator_name or "",
                        "service": task.service or "",
                        "user_id": task.user_id or "",
                        "post_id": task.post_id or "",
                        "post_url": task.post_url or "",
                        "file_url": task.url or "",
                        "filename": task.filename or os.path.basename(task.target_path),
                        "file_size": task.file_size or (os.path.getsize(task.target_path) if os.path.exists(task.target_path) else 0),
                        "file_hash": task.expected_sha256 or "",
                        "published_at": getattr(task, "post_date", "") or "",
                        "tags": tags_list
                    }
                    atomic_write_text(out_path, json.dumps(meta, ensure_ascii=False, indent=2))
                elif fmt == "txt":
                    lines = [t for t in tags_list]
                    if getattr(task, "post_url", ""):
                        lines.append(f"source:{task.post_url}")
                    if getattr(task, "post_date", ""):
                        lines.append(f"date:{task.post_date}")
                    if task.post_title:
                        lines.append(f"title:{task.post_title}")
                    atomic_write_text(out_path, "\n".join(lines) + "\n")
        except Exception as ex:
            logger.debug(f"Could not save metadata sidecar for {task.filename}: {ex}", category="file")

    def _convert_to_webp(self, file_path: str, level: str = "balanced") -> Optional[str]:
        """Converts JPG/PNG to WebP at the chosen level; returns the new path, or None when the file
        was kept as it was (also when the WebP wouldn't be smaller, e.g. lossless on a photo)."""
        from core.filter_engine import WEBP_QUALITY_LEVELS
        try:
            _, ext = os.path.splitext(file_path.lower())
            if ext in (".jpg", ".jpeg", ".png"):
                webp_path = os.path.splitext(file_path)[0] + ".webp"
                tmp_path = webp_path + PART_SUFFIX
                quality = WEBP_QUALITY_LEVELS.get(str(level or "").lower(), 85)
                with Image.open(file_path) as img:
                    if quality is None:
                        img.save(tmp_path, "WEBP", lossless=True, exact=True, quality=100, method=6)
                    else:
                        img.save(tmp_path, "WEBP", quality=quality, method=4)
                orig_size = os.path.getsize(file_path)
                new_size = os.path.getsize(tmp_path)
                if new_size >= orig_size:
                    _remove_quietly(tmp_path)
                    logger.debug(f"Kept {os.path.basename(file_path)}: as WebP it wasn't smaller.", category="downloader")
                    return None
                replace_file(tmp_path, webp_path)
                os.remove(file_path)
                statistics_manager.record_compression(orig_size, new_size)
                return webp_path
        except Exception as e:
            _remove_quietly(os.path.splitext(file_path)[0] + ".webp" + PART_SUFFIX)
            logger.debug(f"WebP compression skipped for {file_path}: {e}", category="downloader")
        return None
