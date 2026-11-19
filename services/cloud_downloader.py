"""
Cloud Storage Downloader Subsystem (Facade)
Re-exports all cloud provider functions and the plug-and-play `cloud_provider_registry`
backed by `services.cloud_providers`.
"""

import requests  # noqa: F401 — re-exported for callers & test patches

from services.cloud_providers import (  # noqa: F401
    AES,
    GDRIVE_AVAILABLE,
    MEGA_API_URL,
    PYCRYPTODOME_AVAILABLE,
    CloudProvider,
    CloudProviderRegistry,
    DropboxCloudProvider,
    GDriveCloudProvider,
    GoFileCloudProvider,
    MegaCloudProvider,
    _DevNull,
    _WIN_RESERVED_NAMES,
    _active_cloud_lock,
    _active_cloud_resps,
    _b64_to_bytes,
    _decrypt_mega_attribute,
    _decrypt_mega_key,
    _gdrive_resolve_filename,
    _inside,
    _is_quota_error_file,
    _parse_mega_key,
    _process_file_key,
    _process_mega_folder,
    _safe_name,
    _suppress_gdown_output,
    _urlb64_to_b64,
    cancel_all_cloud_downloads,
    cloud_provider_registry,
    download_and_decrypt_mega_file,
    download_dropbox_link,
    download_gdrive_link,
    download_gofile_link,
    download_mega_link,
    gdown,
    should_skip_cloud_file,
)


def download_cloud_link(url: str, target_folder: str, **kwargs) -> bool:
    """Dispatch any supported cloud URL via the plug-and-play provider registry."""
    return cloud_provider_registry.download_url(url, target_folder, **kwargs)
