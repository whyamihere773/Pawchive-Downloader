"""
Central Qt Signal Declarations for DecompressorBridge.
Inherited via diamond mixin pattern so all domain mixins share unified Qt signal identities.
"""

from PySide6.QtCore import Signal


class DecompressorSignalsMixin:
    """Shared Qt Signal definitions for DecompressorBridge."""

    scanStarted = Signal()
    scanFinished = Signal(int, "qint64")  # count, total_bytes (64-bit to prevent 32-bit overflow)
    scanError = Signal(str)
    itemsChanged = Signal()
    isBusyChanged = Signal()
    isScanningChanged = Signal()
    isExtractingChanged = Signal()
    selectedStatsChanged = Signal()
    settingsChanged = Signal()
    locationsChanged = Signal()
    diskCheckCompleted = Signal(str)  # JSON string of List[DiskCheckResult]
    extractionStarted = Signal()
    extractionProgress = Signal(float, str, float, str, str)  # overall%, cur_name, cur_pct, eta_str, speed_str
    itemUpdated = Signal(str, str, float, str)  # id, status, progress, error_message
    extractionFinished = Signal(int, int)  # success_count, error_count
    redecompressConfirmRequested = Signal(int, int)  # already_done_count, total_selected_count
    passwordPromptRequested = Signal(str, str, str, str, str, "qint64")  # itemId, filename, creator, directory, errorMsg, size
    passwordPromptDismissed = Signal(str)  # itemId
    passwordWrong = Signal(str)           # itemId — wrong password entered
    passwordBankChanged = Signal()
    ffmpegChanged = Signal()
    compressionReviewRequested = Signal(int, "qint64", "qint64", int)   # files, bytes before, after, failed
    originalsHandled = Signal(str)                                      # what was done with the originals
    mediaCountReady = Signal(int, int, int, "qint64")       # pictures, videos, animated, their bytes
    compressPathsProgress = Signal(float, str)              # percent, file being compressed
    compressPathsFinished = Signal(int, "qint64", "qint64", int, int, bool)   # files, before, after, failed, left, stopped
    galleryOriginalsHandled = Signal(str)
    compressingPathsChanged = Signal()
    groupCountChanged = Signal()
    presetTestFinished = Signal("QVariantMap")
    _guiCall = Signal(object)
