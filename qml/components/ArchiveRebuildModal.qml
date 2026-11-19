import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "archive_rebuild"

// Archive Rebuild Modal
// High-performance asynchronous multi-directory scanner and archive sync dashboard.
// Scans multiple directories/drives, computes hashes, deduces metadata, and bulk-inserts to SQLite.
Item {
    id: root

    property var bridge: null
    property bool isOpen: false

    // Configuration state
    property var scanDirectories: []
    property bool fullHashMode: true
    property bool detectPostInfo: true
    property bool skipExisting: true

    // Rebuild execution telemetry state
    property bool isRunning: bridge ? bridge.isArchiveRebuilding : false
    property bool isPaused: bridge ? bridge.isArchiveRebuildPaused : false
    property bool isFinished: false
    property string finishStatus: "complete" // "complete" or "cancelled"
    property bool backgroundActive: false
    readonly property bool hasSavedRebuild: Boolean(bridge && bridge.hasSavedArchiveRebuild)
    readonly property var savedRebuildSummary: (bridge && bridge.archiveRebuildRecoverySummary) ? bridge.archiveRebuildRecoverySummary : ({})
    readonly property bool showBackgroundBar: !isOpen && (isRunning || (isFinished && backgroundActive) || hasSavedRebuild)

    property var progressData: ({
        phase: "idle",
        percentage: 0.0,
        total_files: 0,
        processed_files: 0,
        added_count: 0,
        skipped_count: 0,
        error_count: 0,
        total_creators: 0,
        total_posts: 0,
        files_per_sec: 0.0,
        mb_per_sec: 0.0,
        elapsed_seconds: 0.0,
        current_file: "",
        current_path: ""
    })

    signal rebuildCompleted()

    function tr(key, fallback) {
        if (typeof Lang !== "undefined" && Lang) {
            var _ = Lang.activeLanguage
            var res = Lang.t(key)
            return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
        }
        return fallback !== undefined ? fallback : key
    }

    function initDirectories() {
        if (!bridge) return
        var suggested = bridge.getSuggestedRebuildDirectories()
        if (suggested && suggested.length > 0) {
            root.scanDirectories = suggested.slice(0)
        } else {
            root.scanDirectories = []
        }
    }

    function addDirectory(path) {
        if (!path) return
        var cleaned = path.replace("file:///", "").replace("file://", "")
        for (var i = 0; i < scanDirectories.length; i++) {
            if (scanDirectories[i].toLowerCase() === cleaned.toLowerCase()) {
                return
            }
        }
        var next = scanDirectories.slice(0)
        next.push(cleaned)
        scanDirectories = next
    }

    function removeDirectory(index) {
        if (index < 0 || index >= scanDirectories.length) return
        var next = scanDirectories.slice(0)
        next.splice(index, 1)
        scanDirectories = next
    }

    function startRebuild() {
        if (!bridge || scanDirectories.length === 0) return
        root.isFinished = false
        root.finishStatus = ""
        root.backgroundActive = false
        root.progressData = {
            phase: "discovering",
            percentage: 0.0,
            total_files: 0,
            processed_files: 0,
            added_count: 0,
            skipped_count: 0,
            error_count: 0,
            total_creators: 0,
            total_posts: 0,
            files_per_sec: 0.0,
            mb_per_sec: 0.0,
            elapsed_seconds: 0.0,
            current_file: "",
            current_path: ""
        }

        var hashMode = root.fullHashMode ? "full" : "fast"
        bridge.startArchiveRebuild(root.scanDirectories, hashMode, root.detectPostInfo, root.skipExisting)
    }

    function togglePause() {
        if (!bridge) return
        if (root.isPaused) {
            bridge.resumeArchiveRebuild()
        } else {
            bridge.pauseArchiveRebuild()
        }
    }

    function cancelRebuild() {
        if (!bridge) return
        bridge.cancelArchiveRebuild()
    }

    function resumeSavedRebuild(inBackground) {
        if (!bridge || typeof bridge.resumeSavedArchiveRebuild !== "function") return
        var s = root.savedRebuildSummary || ({})
        root.isFinished = false
        root.finishStatus = ""
        root.backgroundActive = Boolean(inBackground)
        root.progressData = {
            phase: (s.status === "discovering") ? "discovering" : "indexing",
            percentage: s.percent || 0.0,
            total_files: s.total_files || 0,
            processed_files: s.processed_files || 0,
            added_count: s.added_count || 0,
            skipped_count: s.skipped_count || 0,
            error_count: s.error_count || 0,
            total_creators: s.total_creators || 0,
            total_posts: s.total_posts || 0,
            files_per_sec: 0.0,
            mb_per_sec: 0.0,
            elapsed_seconds: s.elapsed_prior || 0.0,
            current_file: "",
            current_path: ""
        }
        var ok = bridge.resumeSavedArchiveRebuild()
        if (ok && inBackground) {
            root.isOpen = false
        }
    }

    function discardSavedRebuild() {
        if (!bridge || typeof bridge.discardSavedArchiveRebuild !== "function") return
        bridge.discardSavedArchiveRebuild()
    }

    function minimizeToBackground() {
        root.backgroundActive = true
        root.isOpen = false
    }

    function dismissBackgroundBanner() {
        if (root.isRunning) return
        root.backgroundActive = false
        root.isFinished = false
    }

    function close() {
        if (root.isRunning) {
            minimizeToBackground()
            return
        }
        root.isOpen = false
        root.isFinished = false
        root.backgroundActive = false
    }

    onIsOpenChanged: {
        if (isOpen) {
            if (scanDirectories.length === 0) {
                initDirectories()
            }
            if (!isRunning && !backgroundActive) {
                root.isFinished = false
            }
        }
    }

    Connections {
        target: root.bridge
        function onArchiveRebuildProgress(data) {
            root.progressData = data
            if (data.phase === "complete" || data.phase === "cancelled") {
                root.finishStatus = data.phase
                root.isFinished = true
            }
        }
        function onArchiveRebuildFinished(stats) {
            root.isFinished = true
            root.finishStatus = (root.finishStatus === "cancelled") ? "cancelled" : "complete"
            if (!root.isOpen) {
                root.backgroundActive = true
            }
            root.rebuildCompleted()
        }
    }

    anchors.fill: parent
    z: 9999
    visible: isOpen

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#B8060910"
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: {
                if (root.isRunning) {
                    root.minimizeToBackground()
                } else {
                    root.close()
                }
            }
        }
    }

    // Modal Card
    Rectangle {
        id: card
        width: Math.min(620, Math.max(320, parent.width - 32))
        implicitHeight: cardCol.implicitHeight + 44
        anchors.centerIn: parent
        anchors.verticalCenterOffset: root.isOpen ? 0 : -28
        radius: 16
        color: "#131722"
        border.color: "#2D3748"
        border.width: 1.5

        scale: root.isOpen ? 1.0 : 0.90
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on anchors.verticalCenterOffset {
            NumberAnimation { duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.25 }
        }
        Behavior on scale {
            NumberAnimation { duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.25 }
        }
        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        ColumnLayout {
            id: cardCol
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                topMargin: 20
                leftMargin: card.width < 440 ? 14 : 22
                rightMargin: card.width < 440 ? 14 : 22
            }
            spacing: 14

            // ── Top Header Row ──────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                Rectangle {
                    width: 44
                    height: 44
                    radius: 22
                    color: "#1E293B"
                    border.color: root.isRunning ? "#38BDF8" : (root.isFinished ? "#34D399" : "#475569")
                    border.width: 1.5

                    Text {
                        anchors.centerIn: parent
                        text: root.isFinished ? "🎉" : (root.isRunning ? "⚡" : "🔨")
                        font.pixelSize: 22

                        scale: root.isRunning ? 1.15 : 1.0
                        Behavior on scale {
                            NumberAnimation { duration: 250; easing.type: Easing.InOutQuad }
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3

                    Text {
                        text: root.isFinished
                              ? root.tr("rebuild_status_complete", "Archive Rebuild Complete")
                              : root.tr("dialog_rebuild_archive_title", "Rebuild Download Archive")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 17
                        font.weight: 700
                        color: "#F8FAFC"
                    }

                    Text {
                        text: root.isFinished
                              ? root.tr("rebuild_complete_desc", "Local folders have been scanned and records have been committed to the archive database.")
                              : root.tr("dialog_rebuild_archive_desc", "Deep scan one or more directories to catalog existing files, deduce creator metadata, and populate the archive database.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }

                // Minimize to Background Button (visible while running)
                Rectangle {
                    visible: root.isRunning
                    width: 28
                    height: 28
                    radius: 14
                    color: minHover.containsMouse ? "#1E2F47" : "transparent"
                    border.color: minHover.containsMouse ? "#38BDF8" : "transparent"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "—"
                        font.pixelSize: 12
                        font.weight: 700
                        color: minHover.containsMouse ? "#7DD3FC" : "#94A3B8"
                    }

                    MouseArea {
                        id: minHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: root.tr("rebuild_btn_background_tip", "Minimize to bottom progress bar and keep rebuilding in the background")
                        onClicked: root.minimizeToBackground()
                    }
                }

                // Close / Minimize Button
                Rectangle {
                    width: 28
                    height: 28
                    radius: 14
                    color: closeHover.containsMouse ? "#2A374A" : "transparent"
                    border.color: closeHover.containsMouse ? "#475569" : "transparent"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 12
                        font.weight: 700
                        color: closeHover.containsMouse ? "#F8FAFC" : "#64748B"
                    }

                    MouseArea {
                        id: closeHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse && root.isRunning
                        ToolTip.delay: 300
                        ToolTip.text: root.tr("rebuild_btn_background_tip", "Minimize to bottom progress bar and keep rebuilding in the background")
                        onClicked: root.close()
                    }
                }
            }

            // Divider
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1E293B"
            }

            // ── PHASE 1: Configuration Form (Visible when idle) ──────────
            ArchiveRebuildConfigPane {
                modal: root
                cardWidth: card.width
            }

            // ── PHASE 2: Live Progress & Telemetry (Visible when running) ─
            ArchiveRebuildProgressPane {
                modal: root
                cardWidth: card.width
            }

            // Divider
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1E293B"
            }

            // ── Action Footer Buttons ──────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Send active rebuild to bottom progress bar
                StyledButton {
                    text: root.tr("rebuild_btn_background", "Run in Background")
                    iconText: "⬇"
                    variant: "outline"
                    visible: root.isRunning
                    tooltip: root.tr("rebuild_btn_background_tip", "Minimize to bottom progress bar and keep rebuilding in the background")
                    onClicked: root.minimizeToBackground()
                }

                Item { Layout.fillWidth: true }

                // Actions when IDLE
                StyledButton {
                    text: root.tr("rebuild_btn_cancel", "Cancel")
                    variant: "ghost"
                    visible: !root.isRunning && !root.isFinished
                    onClicked: root.close()
                }

                StyledButton {
                    text: root.tr("rebuild_btn_start", "Start Rebuild")
                    iconText: "🚀"
                    variant: "primary"
                    visible: !root.isRunning && !root.isFinished
                    enabled: root.scanDirectories.length > 0
                    onClicked: root.startRebuild()
                }

                // Actions when RUNNING
                StyledButton {
                    text: root.isPaused ? root.tr("rebuild_btn_resume", "Resume") : root.tr("rebuild_btn_pause", "Pause")
                    iconText: root.isPaused ? "▶️" : "⏸️"
                    variant: "outline"
                    visible: root.isRunning
                    onClicked: root.togglePause()
                }

                StyledButton {
                    text: root.tr("rebuild_btn_cancel", "Cancel")
                    iconText: "⏹️"
                    variant: "danger"
                    visible: root.isRunning
                    onClicked: root.cancelRebuild()
                }

                // Action when FINISHED
                StyledButton {
                    text: root.tr("rebuild_btn_done", "Done & View Catalog")
                    iconText: "✓"
                    variant: "success"
                    visible: root.isFinished
                    onClicked: root.close()
                }
            }
        }
    }
}
