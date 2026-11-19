"""
Application Bridge Subsystem
Binds the PySide6/Qt Core engine with the QML User Interface, providing
reactive properties, slots, session persistence, telemetry signals, and async orchestration.

Composes domain-specific mixins from `bridge.app_bridge_mixins` while preserving
100% of QML signals, properties, slots, and module-level exports.
"""

import os
import sys
from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QFileDialog  # noqa: F401 (re-exported for QML & tests)

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core import folder_naming
from core.watchlist_manager import post_id_is_newer  # noqa: F401  (kept for older imports)
from services.bunkr_client import fetch_bunkr_album  # noqa: F401
from services.erome_client import fetch_erome_album  # noqa: F401
from services.nhentai_client import fetch_nhentai_gallery  # noqa: F401
from services.cloud_downloader import (  # noqa: F401
    download_dropbox_link,
    download_gdrive_link,
    download_gofile_link,
    download_mega_link,
)

from bridge.app_bridge_mixins import (
    SettingsPropsCoreMixin,
    SettingsPropsExtendedMixin,
    SettingsPropsMiscMixin,
    ArchiveMixin,
    AiKnownMixin,
    DownloadControlMixin,
    FavoritesMixin,
    PostSelectionMixin,
    PostSelectionQueueMixin,
    DownloadFetchMixin,
    RecoveryRetryMixin,
    MidDownloadMixin,
    DownloaderEventsMixin,
    QueueCloudMixin,
    WatchlistSyncMixin,
    WatchlistEntriesMixin,
    WatchlistFoldersMixin,
    VaultPoolSchedulerMixin,
    GalleryExplorerMixin,
    GalleryRenameMixin,
    GalleryMaintenanceMixin,
    GallerySafetySortMixin,
)
from bridge.app_bridge_mixins.init_state import (
    init_bridge_core_state,
    init_bridge_runtime_and_signals,
)


def _post_order_key(date: str, post_id: str):
    pid = str(post_id or "")
    return (str(date or "")[:10], int(pid) if pid.isdigit() else -1)


_PATH_SAFETY_CACHE: dict = {}      # path -> (time, getPathSafetyInfo answer)

_FOLDER_PREVIEW_IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp",
    ".avif", ".apng", ".tif", ".tiff", ".jfif",
}


def watchlist_cutoff(done_posts, unfinished_posts):
    """Where the Watchlist's "downloaded up to" point may move, from what actually finished.

    done_posts / unfinished_posts: iterables of (date, post_id). The point only advances through
    posts that are older than every post that didn't finish (failed, cancelled, never started), so
    nothing is skipped by a later check. Returns (post_id, date, ids_of_done_posts_on_that_date),
    or ("", "", []) when nothing can be recorded.
    """
    done = [(str(d or "")[:10], str(p or "")) for d, p in done_posts if d]
    unfinished = [(str(d or "")[:10], str(p or "")) for d, p in unfinished_posts if d]
    if unfinished:
        first_open = min(_post_order_key(d, p) for d, p in unfinished)
        done = [(d, p) for d, p in done if _post_order_key(d, p) < first_open]
    if not done:
        return "", "", []
    newest_date, newest_pid = max(done, key=lambda dp: _post_order_key(*dp))
    day_ids = sorted({p for d, p in done if d == newest_date and p})
    return newest_pid, newest_date, day_ids


class AppBridge(
    SettingsPropsCoreMixin,
    SettingsPropsExtendedMixin,
    SettingsPropsMiscMixin,
    ArchiveMixin,
    AiKnownMixin,
    DownloadControlMixin,
    FavoritesMixin,
    PostSelectionMixin,
    PostSelectionQueueMixin,
    DownloadFetchMixin,
    RecoveryRetryMixin,
    MidDownloadMixin,
    DownloaderEventsMixin,
    QueueCloudMixin,
    WatchlistSyncMixin,
    WatchlistEntriesMixin,
    WatchlistFoldersMixin,
    VaultPoolSchedulerMixin,
    GalleryExplorerMixin,
    GalleryRenameMixin,
    GalleryMaintenanceMixin,
    GallerySafetySortMixin,
    QObject,
):
    def __init__(self, parent=None):
        super().__init__(parent)
        init_bridge_core_state(self)
        self.downloader.ytdlp_manager.set_cookies_browser(self._embed_cookies_browser)
        init_bridge_runtime_and_signals(self)

    @Slot()
    @Slot(bool)
    def saveSettings(self, explicit_save: bool = False):
        settings_dict = {
            "download_dir": self._download_dir,
            "threads": self._threads_count,
            "user_agent": self._user_agent,
            "page_start": 1,
            "page_end": 999999,
            "character_scope": self._character_scope,
            "skip_words": self._skip_words,
            "skip_scope": self._skip_scope,
            "remove_words": self._remove_words,
            "filter_profile": self._filter_profile,
            "remove_words_profile": self._remove_words_profile,
            "subfolder_per_post": self._subfolder_per_post,
            "date_prefix": self._date_prefix,
            "site_in_folder_name": folder_naming.include_service,
            "file_index_prefix": self._file_index_prefix,
            "separate_by_known": self._separate_folders_by_known,
            "download_revisions": self._download_revisions,
            "adaptive_threading": self._adaptive_threading,
            "threads_locked": self._threads_locked,
            "auto_retry_at_end": self._auto_retry_at_end,
            "manga_mode": self._manga_mode,
            "filename_style": self._filename_style,
            "filename_template": self._filename_template,
            "proxy_url": self._proxy_url,
            "compress_webp": self._compress_webp,
            "webp_quality": self._webp_quality,
            "keep_duplicates": self._keep_duplicates,
            "scan_content_images": self._scan_content_images,
            "download_dms": self._download_dms,
            "download_delay": self._download_delay,
            "save_post_metadata": self._save_post_metadata,
            "write_sidecars": self._write_sidecars,
            "sidecar_format": self._sidecar_format,
            "sidecar_scope": self._sidecar_scope,
            "download_embeds": self._download_embeds,
            "embed_cookies_browser": self._embed_cookies_browser,
            "decompressor": (self._decompressor_bridge.settings_dict() if getattr(self, "_decompressor_bridge", None)
                             else getattr(self, "_loaded_decompressor_settings", {})),
            "open_folder_on_complete": self._open_folder_on_complete,
            "play_completion_sound": self._play_completion_sound,
            "generate_desktop_report": self._generate_desktop_report,
            "post_download_action": "none",
            "known_recognition_mode": self._known_recognition_mode,
            "ai_recognition_enabled": self._ai_recognition_enabled,
            "ai_engine_mode": self._ai_engine_mode,
            "ai_deep_reasoner_variant": self._ai_deep_reasoner_variant,
            "language": self._language,
            "ui_scale": self._ui_scale,
            "console_width": self._console_width,
            "tag_folder_mode": self._tag_folder_mode,
            "skip_post_covers": self._skip_post_covers,
            "download_thumbnails_only": self._download_thumbnails_only,
            "fallback_to_thumbnails": self._fallback_to_thumbnails,
            "hide_unimported_notice": self._hide_unimported_notice,
            "redownload_small_files": self._redownload_small_files,
            "date_auto_scan_pages": self._date_auto_scan_pages,
            "enable_download_archive": self._enable_download_archive,
            "download_pawchive_temporary_files": self._download_pawchive_temporary_files,
            "min_file_size": self._min_file_size,
            "max_file_size": self._max_file_size,
            "video_duration_filter_enabled": self._video_duration_filter_enabled,
            "min_video_duration": self._min_video_duration,
            "max_video_duration": self._max_video_duration,
            "exact_extensions": self._exact_extensions,
            "saved_custom_extensions": self._saved_custom_extensions,
            "gallery_bookmarks": self._gallery_bookmarks,
            "write_audio_metadata": self._write_audio_metadata,
            "telegram_safety_acknowledged": self._telegram_safety_acknowledged,
            "telegram_liability_acknowledged": self._telegram_liability_acknowledged,
            "skip_retry_404": self._skip_retry_404,
            "group_file_type": self._group_file_type,
            "file_order": self._file_order,
            "watchlist_apply_global_settings": self._watchlist_apply_global_settings,
            "watchlist_check_on_startup": self._watchlist_check_on_startup,
            "bandwidth_limit_enabled": self._bandwidth_limit_enabled,
            "bandwidth_limit_value": self._bandwidth_limit_value,
            "bandwidth_limit_unit": self._bandwidth_limit_unit,
            "privacy_pin": self._privacy_pin,
            "pending_pin_reset": self._pending_pin_reset,
            "privacy_idle_minutes": self._privacy_idle_minutes,
            "disabled_tabs": list(self._disabled_tabs),
            "local_library_roots": list(getattr(self, "_local_library_roots", [])),
            "browser_last_download_dir": str(getattr(self, "_browser_last_download_dir", "") or ""),
        }
        self.session_manager.save_settings(settings_dict, silent=True)
        self._evaluate_pending_download_settings()
        if explicit_save and self._has_pending_download_settings_changes and not self._is_applying_mid_download:
            self.requestMidDownloadSettingsPrompt("global")
