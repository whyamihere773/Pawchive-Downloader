"""
Plug-and-play Cloud Storage Provider package.
Implement `CloudProvider` and register it with `cloud_provider_registry` to add new cloud hosts.
"""

from services.cloud_providers.base import (
    CloudProvider,
    CloudProviderRegistry,
    _WIN_RESERVED_NAMES,
    _active_cloud_lock,
    _active_cloud_resps,
    _inside,
    _safe_name,
    cancel_all_cloud_downloads,
    cloud_provider_registry,
    should_skip_cloud_file,
)
from services.cloud_providers.dropbox_gofile_provider import (
    DropboxCloudProvider,
    GoFileCloudProvider,
    download_dropbox_link,
    download_gofile_link,
)
from services.cloud_providers.gdrive_provider import (
    GDRIVE_AVAILABLE,
    GDriveCloudProvider,
    _DevNull,
    _gdrive_resolve_filename,
    _is_quota_error_file,
    _suppress_gdown_output,
    download_gdrive_link,
    gdown,
)
from services.cloud_providers.mega_provider import (
    AES,
    MEGA_API_URL,
    PYCRYPTODOME_AVAILABLE,
    MegaCloudProvider,
    _b64_to_bytes,
    _decrypt_mega_attribute,
    _decrypt_mega_key,
    _parse_mega_key,
    _process_file_key,
    _process_mega_folder,
    _urlb64_to_b64,
    download_and_decrypt_mega_file,
    download_mega_link,
)

for _provider in (
    MegaCloudProvider(),
    GDriveCloudProvider(),
    DropboxCloudProvider(),
    GoFileCloudProvider(),
):
    cloud_provider_registry.register(_provider)

__all__ = [
    "CloudProvider",
    "CloudProviderRegistry",
    "cloud_provider_registry",
    "MegaCloudProvider",
    "GDriveCloudProvider",
    "DropboxCloudProvider",
    "GoFileCloudProvider",
    "cancel_all_cloud_downloads",
    "should_skip_cloud_file",
    "download_mega_link",
    "download_gdrive_link",
    "download_dropbox_link",
    "download_gofile_link",
]
