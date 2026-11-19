"""
Cloud Storage Provider Contract, Registry & Shared Transfer Utilities
Plug-and-play provider interface adhering to AGENTS.md Rule 1.
"""

from abc import ABC, abstractmethod
import os
import re
from threading import Lock
from typing import Any, Callable, List, Optional, Tuple, Union

_active_cloud_resps: set = set()
_active_cloud_lock = Lock()

_WIN_RESERVED_NAMES = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def _safe_name(name, fallback: str = "file") -> str:
    """A file or folder name from a cloud site, made safe to use as ONE path component.

    Names are chosen by whoever uploaded the files: characters Windows refuses (e.g. "Part 1: Intro")
    made those files fail, and a name like ".." could place files outside the download folder.
    """
    n = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name or "")).strip().rstrip(". ")
    if not n or set(n) <= {"."}:
        n = fallback
    if n.split(".")[0].upper() in _WIN_RESERVED_NAMES:
        n = "_" + n
    return n[:200]


def _inside(base: str, path: str) -> bool:
    """True when path is inside the folder base."""
    try:
        b = os.path.normcase(os.path.abspath(base))
        p = os.path.normcase(os.path.abspath(path))
        return os.path.commonpath([b, p]) == b and p != b
    except ValueError:
        return False


def cancel_all_cloud_downloads():
    """Instantly terminates all active cloud download HTTP streams and sockets (Mega, Dropbox, Gofile)."""
    with _active_cloud_lock:
        for r in list(_active_cloud_resps):
            try:
                r.close()
                if hasattr(r, "raw") and r.raw:
                    r.raw.close()
            except Exception:
                pass
        _active_cloud_resps.clear()


def should_skip_cloud_file(
    file_name_or_path: str,
    skip_words: Optional[Union[str, List[str]]] = None,
    file_size: Optional[int] = None,
    options: Optional[Any] = None
) -> Tuple[bool, str]:
    """
    Checks if a cloud file or folder path contains any skipped keywords or fails FilterOptions.
    Returns (True, reason) if it should be skipped, or (False, "") if kept.
    """
    if not file_name_or_path:
        return False, ""

    # 1. Check with FilterOptions if available
    if options is not None:
        try:
            from core.filter_engine import FilterEngine
            base_name = os.path.basename(file_name_or_path)
            keep, reason = FilterEngine.should_keep_file(base_name, options, file_size=file_size)
            if not keep:
                return True, reason
        except Exception:
            pass

    # 2. Check skip_words (can be str or list)
    if skip_words:
        try:
            from core.filter_engine import FilterEngine
            if isinstance(skip_words, str):
                words = FilterEngine._parse_comma_list(skip_words)
            elif isinstance(skip_words, (list, tuple, set)):
                words = [str(w).strip() for w in skip_words if str(w).strip()]
            else:
                words = []

            base_name = os.path.basename(file_name_or_path)
            stem_base = os.path.splitext(base_name)[0]
            path_parts = [p for p in re.split(r'[\\/]', file_name_or_path) if p]

            for word in words:
                if word.startswith("[") and word.endswith("]"):
                    continue
                pattern = r"(?:^|[_\-\s\./\\])" + re.escape(word) + r"(?:[_\-\s\./\\]|$)"
                if re.search(pattern, stem_base, re.IGNORECASE) or re.search(r"\b" + re.escape(word) + r"\b", base_name, re.IGNORECASE):
                    return True, f"File name matches skip keyword: '{word}'"
                for part in path_parts[:-1]:
                    part_stem = os.path.splitext(part)[0]
                    if re.search(pattern, part_stem, re.IGNORECASE) or re.search(r"\b" + re.escape(word) + r"\b", part, re.IGNORECASE):
                        return True, f"Parent folder matches skip keyword: '{word}'"
        except Exception:
            pass

    return False, ""


class CloudProvider(ABC):
    """Plug-and-play contract for an external cloud host downloader."""

    name: str = ""

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Return True if this provider handles the given URL."""

    @abstractmethod
    def download(
        self,
        url: str,
        target_folder: str,
        log_func: Callable[[str], None] = print,
        progress_callback: Optional[Callable[..., None]] = None,
        cancel_event: Optional[Any] = None,
        pause_event: Optional[Any] = None,
        **kwargs: Any,
    ) -> bool:
        """Download the target cloud resource into `target_folder`."""


class CloudProviderRegistry:
    """Registry allowing new cloud hosts to be plugged in without modifying core logic."""

    def __init__(self) -> None:
        self._providers: List[CloudProvider] = []

    def register(self, provider: CloudProvider) -> None:
        if any(p.name == provider.name for p in self._providers):
            self._providers = [p if p.name != provider.name else provider for p in self._providers]
        else:
            self._providers.append(provider)

    def resolve(self, url: str) -> Optional[CloudProvider]:
        for provider in self._providers:
            if provider.can_handle(url):
                return provider
        return None

    def all_providers(self) -> List[CloudProvider]:
        return list(self._providers)

    def download_url(self, url: str, target_folder: str, **kwargs: Any) -> bool:
        provider = self.resolve(url)
        if provider is None:
            log_func = kwargs.get("log_func", print)
            log_func(f"⚠️ No registered cloud provider for URL: {url}")
            return False
        return provider.download(url, target_folder, **kwargs)


cloud_provider_registry = CloudProviderRegistry()
