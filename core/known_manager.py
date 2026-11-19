"""
Known Series and Character Manager
Handles persistent storage, categorization matching, smart character extraction, and auto-learning.
"""

import os
import threading
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.franchise_resolver import FranchiseResolver
from core.known_candidates import KnownCandidatesMixin
from core.known_constants import (
    GENERIC_TITLE_WORDS,
    IGNORED_TAGS,
    _AND_PAIR,
    _BLOCKED_FRANCHISES,
    _CHAPTER_HEAD,
    _CREATURE_PATTERN,
    _FRANCHISE_BLOCKLIST,
    _GENERIC_SEGMENT_TAGS,
    _INLINE_NAME_WORKFLOW,
    _LEAD_JUNK,
    _NOISE_TAGS,
    _ONLY_JUNK,
    _RANGE_PATTERN,
    _STOP_CHAR_WORDS,
    _TRAIL_JUNK,
    _WORKFLOW_TOKEN,
    _is_invalid_franchise,
)
from core.known_hierarchy import KnownHierarchyMixin
from core.known_matcher import KnownMatcherMixin
from core.known_storage import KnownStorageMixin


class KnownManager(
    KnownStorageMixin,
    KnownMatcherMixin,
    KnownHierarchyMixin,
    KnownCandidatesMixin,
):
    background_reload = False
    _edit_lock = threading.Lock()

    def __init__(self, file_path: Optional[str] = None):
        if file_path:
            self.file_path = file_path
        else:
            from core.path_utils import get_config_dir
            self.file_path = os.path.join(get_config_dir(), "Known.txt")

        # Recognition mode: "hybrid", "database_only", "learning_only"
        self.mode: str = "hybrid"

        self.entries: List[str] = []
        self.entry_franchise_map: Dict[str, str] = {}
        self.franchise_sections: Dict[str, List[str]] = {}
        self.standalone_entries: List[str] = []

        # Master comprehensive database (Danbooru Cat 3 & 4 game & anime characters)
        self.master_characters: Dict[str, Dict[str, str]] = {}
        self.master_franchises: List[str] = []
        self._master_char_map: Dict[Tuple[str, ...], Tuple[str, str]] = {}
        self._master_franchise_map: Dict[Tuple[str, ...], str] = {}

        # Automated Franchise & Series Resolver (Seed Catalog, Local Cache, Fuzzy, AniList Auto-discovery)
        self.franchise_resolver = FranchiseResolver()

        # Custom Known.txt fast lookup indexes
        self.franchise_aliases: Dict[str, List[str]] = {}
        self._custom_franchise_map: Dict[Tuple[str, ...], str] = {}
        self._custom_cjk_names: Set[str] = set()
        self._custom_cjk_franchises: Set[str] = set()
        self._custom_exact_map: Dict[Tuple[str, ...], Tuple[str, str]] = {}
        self._custom_first_token_map: Dict[str, List[Tuple[str, Tuple[str, ...]]]] = {}
        self._custom_last_token_map: Dict[str, List[Tuple[str, Tuple[str, ...]]]] = {}
        self._custom_single_names: List[str] = []
        self._custom_indexed: List[Tuple[str, Tuple[str, ...]]] = []

        # In-memory query cache for instant hits
        self._lru_cache: Dict[Tuple[str, Tuple[str, ...], Tuple[str, ...], str, str], Optional[Tuple[str, str]]] = {}

        # AI-assisted recognition subsystem (Tier 1 Embeddings & Tier 2 Reasoner)
        self.model_manager: Optional[Any] = None
        self.semantic_matcher: Optional[Any] = None
        self.contextual_reasoner: Optional[Any] = None
        self._ai_enabled: bool = False
        self._ai_engine_mode: str = "hybrid"

        self._load_master_db()

        self.on_entries_changed: Optional[Callable[[], None]] = None
        self._lock = threading.RLock()
        self.load()
