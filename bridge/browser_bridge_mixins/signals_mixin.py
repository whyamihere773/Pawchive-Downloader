"""
Central Qt Signal Declarations for BrowserBridge.
Inherited via diamond mixin pattern so all domain mixins share unified Qt signal identities.
"""

from PySide6.QtCore import Signal


class BrowserSignalsMixin:
    """Shared Qt Signal definitions for BrowserBridge."""

    providersManifestChanged = Signal()
    browserModeChanged = Signal()
    activeProviderChanged = Signal()
    filterStateChanged = Signal()
    loadingStateChanged = Signal()
    paginationChanged = Signal()
    selectedCreatorChanged = Signal()
    selectedPostChanged = Signal()
    marksChanged = Signal()
    localDrivesChanged = Signal()
    newPostsStateChanged = Signal()
    tagsListReady = Signal("QVariantList")
    relocationProgress = Signal(str, int, int, str)   # creatorKey, done, total, currentFile
    relocationFinished = Signal(str, bool, str)       # creatorKey, ok, message
    toastRequested = Signal(str, str)                 # message, kind ("info"|"success"|"warning"|"error")
    navigateToTabRequested = Signal(int)              # tab index in main.qml
    remoteMediaReady = Signal(str, str, str)          # sourceUrl, localPath, error
    activeProviderAuthChanged = Signal()
    loginPromptRequested = Signal(str, str)           # providerId, reason
    providerLoginFinished = Signal(str, bool, str)    # providerId, ok, message
    lastDownloadDirChanged = Signal()
    _callOnGui = Signal(object)
