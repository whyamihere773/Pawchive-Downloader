"""Modular domain mixins composed by bridge.app_bridge.AppBridge."""

from bridge.app_bridge_mixins.signals_mixin import AppBridgeSignalsMixin
from bridge.app_bridge_mixins.settings_props_core import SettingsPropsCoreMixin
from bridge.app_bridge_mixins.settings_props_extended import SettingsPropsExtendedMixin
from bridge.app_bridge_mixins.settings_props_misc import SettingsPropsMiscMixin
from bridge.app_bridge_mixins.archive_mixin import ArchiveMixin
from bridge.app_bridge_mixins.ai_known_mixin import AiKnownMixin
from bridge.app_bridge_mixins.download_control_mixin import DownloadControlMixin
from bridge.app_bridge_mixins.favorites_mixin import FavoritesMixin
from bridge.app_bridge_mixins.post_selection_mixin import PostSelectionMixin
from bridge.app_bridge_mixins.post_selection_queue_mixin import PostSelectionQueueMixin
from bridge.app_bridge_mixins.download_fetch_mixin import DownloadFetchMixin
from bridge.app_bridge_mixins.recovery_retry_mixin import RecoveryRetryMixin
from bridge.app_bridge_mixins.mid_download_mixin import MidDownloadMixin
from bridge.app_bridge_mixins.downloader_events_mixin import DownloaderEventsMixin
from bridge.app_bridge_mixins.queue_cloud_mixin import QueueCloudMixin
from bridge.app_bridge_mixins.watchlist_sync_mixin import WatchlistSyncMixin
from bridge.app_bridge_mixins.watchlist_entries_mixin import WatchlistEntriesMixin
from bridge.app_bridge_mixins.watchlist_folders_mixin import WatchlistFoldersMixin
from bridge.app_bridge_mixins.vault_pool_scheduler_mixin import VaultPoolSchedulerMixin
from bridge.app_bridge_mixins.gallery_explorer_mixin import GalleryExplorerMixin
from bridge.app_bridge_mixins.gallery_rename_mixin import GalleryRenameMixin
from bridge.app_bridge_mixins.gallery_maintenance_mixin import GalleryMaintenanceMixin
from bridge.app_bridge_mixins.gallery_safety_sort_mixin import GallerySafetySortMixin

__all__ = [
    "AppBridgeSignalsMixin",
    "SettingsPropsCoreMixin",
    "SettingsPropsExtendedMixin",
    "SettingsPropsMiscMixin",
    "ArchiveMixin",
    "AiKnownMixin",
    "DownloadControlMixin",
    "FavoritesMixin",
    "PostSelectionMixin",
    "PostSelectionQueueMixin",
    "DownloadFetchMixin",
    "RecoveryRetryMixin",
    "MidDownloadMixin",
    "DownloaderEventsMixin",
    "QueueCloudMixin",
    "WatchlistSyncMixin",
    "WatchlistEntriesMixin",
    "WatchlistFoldersMixin",
    "VaultPoolSchedulerMixin",
    "GalleryExplorerMixin",
    "GalleryRenameMixin",
    "GalleryMaintenanceMixin",
    "GallerySafetySortMixin",
]
