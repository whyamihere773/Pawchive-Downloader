import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

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
        radius: 16
        color: "#131722"
        border.color: "#2D3748"
        border.width: 1.5

        y: root.isOpen ? 0 : -28
        scale: root.isOpen ? 1.0 : 0.90
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on y {
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
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 14
                visible: !root.isRunning && !root.isFinished

                // Interrupted Rebuild Recovery Banner (Crash / Power-Loss / Close Resume)
                Rectangle {
                    visible: root.hasSavedRebuild
                    Layout.fillWidth: true
                    implicitHeight: recoveryCol.implicitHeight + 20
                    radius: 10
                    color: "#1B160B"
                    border.color: "#B45309"
                    border.width: 1.2

                    ColumnLayout {
                        id: recoveryCol
                        anchors {
                            left: parent.left
                            right: parent.right
                            verticalCenter: parent.verticalCenter
                            leftMargin: 12
                            rightMargin: 12
                        }
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                text: "🔄"
                                font.pixelSize: 15
                                Layout.alignment: Qt.AlignVCenter
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 2

                                Text {
                                    text: root.tr("rebuild_recovery_title", "Interrupted Archive Rebuild Detected")
                                    font.family: "Segoe UI, Inter, sans-serif"
                                    font.pixelSize: 12
                                    font.weight: 700
                                    color: "#FCD34D"
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }

                                Text {
                                    text: {
                                        var s = root.savedRebuildSummary || ({})
                                        var tot = s.total_files || 0
                                        var proc = s.processed_files || 0
                                        var pct = s.percent || 0
                                        var added = s.added_count || 0
                                        var savedAt = s.saved_at ? (" • " + s.saved_at) : ""
                                        if (tot > 0) {
                                            return proc + " / " + tot + " files (" + pct + "%) • +" + added + " added" + savedAt
                                        }
                                        return root.tr("rebuild_recovery_discover_desc", "Saved during folder scan — resume to pick up without re-configuring.") + savedAt
                                    }
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    color: "#FDE68A"
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            StyledButton {
                                text: root.tr("rebuild_recovery_btn_resume", "Resume Where It Left Off")
                                iconText: "▶️"
                                variant: "success"
                                implicitHeight: 28
                                onClicked: root.resumeSavedRebuild(false)
                            }

                            StyledButton {
                                text: root.tr("rebuild_recovery_btn_resume_bg", "Resume in Background")
                                iconText: "⬇"
                                variant: "outline"
                                implicitHeight: 28
                                onClicked: root.resumeSavedRebuild(true)
                            }

                            Item { Layout.fillWidth: true }

                            StyledButton {
                                text: root.tr("rebuild_recovery_btn_discard", "Discard")
                                variant: "ghost"
                                implicitHeight: 28
                                onClicked: root.discardSavedRebuild()
                            }
                        }
                    }
                }

                // Section: Directories to Scan
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: root.tr("rebuild_scan_folders_header", "Scan Directories & Drives")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: "#CBD5E1"
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }

                        StyledButton {
                            text: card.width < 480 ? "" : root.tr("rebuild_reset_defaults", "Reset Defaults")
                            iconText: "↺"
                            variant: "ghost"
                            implicitHeight: 26
                            tooltip: root.tr("rebuild_reset_defaults", "Reset Defaults")
                            onClicked: root.initDirectories()
                        }

                        StyledButton {
                            text: card.width < 420 ? "" : root.tr("rebuild_add_folder", "Add Folder...")
                            iconText: "📁"
                            variant: "outline"
                            implicitHeight: 26
                            tooltip: root.tr("rebuild_add_folder", "Add Folder...")
                            onClicked: {
                                var chosen = root.bridge.browseFolderDialog("Select Download Folder or Drive to Scan", "")
                                if (chosen) {
                                    root.addDirectory(chosen)
                                }
                            }
                        }
                    }

                    // Directory List Container
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: Math.min(130, Math.max(56, dirCol.implicitHeight + 12))
                        radius: 8
                        color: "#0B0E14"
                        border.color: "#1E293B"
                        border.width: 1
                        clip: true

                        SmoothFlickable {
                            anchors.fill: parent
                            anchors.margins: 6
                            contentWidth: width
                            contentHeight: dirCol.implicitHeight

                            ColumnLayout {
                                id: dirCol
                                width: parent.width
                                spacing: 4

                                Repeater {
                                    model: root.scanDirectories

                                    delegate: Rectangle {
                                        Layout.fillWidth: true
                                        implicitHeight: 28
                                        radius: 6
                                        color: rowHover.containsMouse ? "#161E2E" : "#0F141F"
                                        border.color: rowHover.containsMouse ? "#2A374A" : "transparent"
                                        border.width: 1

                                        MouseArea {
                                            id: rowHover
                                            anchors.fill: parent
                                            hoverEnabled: true
                                        }

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 6
                                            spacing: 8

                                            Text {
                                                text: "📁"
                                                font.pixelSize: 12
                                            }

                                            Text {
                                                text: modelData
                                                font.family: "Consolas, 'Cascadia Code', monospace"
                                                font.pixelSize: 11
                                                color: "#E2E8F0"
                                                Layout.fillWidth: true
                                                elide: Text.ElideMiddle
                                            }

                                            Rectangle {
                                                width: 18
                                                height: 18
                                                radius: 9
                                                color: delHover.containsMouse ? "#334155" : "transparent"

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: "✕"
                                                    font.pixelSize: 10
                                                    color: delHover.containsMouse ? "#F87171" : "#64748B"
                                                }

                                                MouseArea {
                                                    id: delHover
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: root.removeDirectory(index)
                                                }
                                            }
                                        }
                                    }
                                }

                                Text {
                                    text: root.tr("rebuild_no_folders_hint", "No directories selected. Click 'Add Folder...' to select a download directory or drive.")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    color: "#64748B"
                                    visible: root.scanDirectories.length === 0
                                    Layout.fillWidth: true
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.topMargin: 12
                                    Layout.bottomMargin: 12
                                }
                            }
                        }
                    }
                }

                // Section: Options
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    StyledCheckBox {
                        id: hashCheck
                        text: root.tr("rebuild_opt_hash", "Full SHA-256 Hashing")
                        tooltip: root.tr("rebuild_opt_hash_tip", "Computes cryptographic hashes for 100% duplicate protection. Uncheck for fast timestamp signature mode.")
                        checked: root.fullHashMode
                        onCheckedChanged: root.fullHashMode = checked
                    }

                    StyledCheckBox {
                        id: infoCheck
                        text: root.tr("rebuild_opt_post_info", "Parse post_info.txt Metadata")
                        tooltip: root.tr("rebuild_opt_post_info_tip", "Reads post_info.txt files to recover exact original post IDs, URLs, and creator IDs.")
                        checked: root.detectPostInfo
                        onCheckedChanged: root.detectPostInfo = checked
                    }

                    StyledCheckBox {
                        id: skipCheck
                        text: root.tr("rebuild_opt_skip_existing", "Skip Already Indexed Files")
                        tooltip: root.tr("rebuild_opt_skip_existing_tip", "Bypasses files already recorded in the archive database to save time.")
                        checked: root.skipExisting
                        onCheckedChanged: root.skipExisting = checked
                    }
                }
            }

            // ── PHASE 2: Live Progress & Telemetry (Visible when running) ─
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 14
                visible: root.isRunning || root.isFinished

                // Status Banner Line
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: root.isFinished
                              ? (root.finishStatus === "cancelled" ? root.tr("rebuild_status_cancelled", "Rebuild Stopped") : root.tr("rebuild_status_complete", "Archive Rebuild Complete"))
                              : (root.isPaused
                                 ? root.tr("rebuild_status_paused", "Rebuild Paused")
                                 : (root.progressData.phase === "discovering"
                                    ? ((root.progressData.total_files || 0) > 0
                                       ? root.tr("rebuild_status_discovering_count", "Discovering files across directories… (%1 found)").replace("%1", root.progressData.total_files)
                                       : root.tr("rebuild_status_discovering", "Discovering files across directories..."))
                                    : root.tr("rebuild_status_indexing", "Scanning and cataloging files...")))
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 13
                        font.weight: 600
                        color: root.isFinished
                               ? (root.finishStatus === "cancelled" ? "#FBBF24" : "#34D399")
                               : (root.isPaused ? "#FBBF24" : "#38BDF8")
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    // Speed Badge
                    Rectangle {
                        implicitHeight: 22
                        implicitWidth: speedRow.implicitWidth + 12
                        radius: 6
                        color: "#0B0E14"
                        border.color: "#1E293B"
                        border.width: 1
                        visible: root.isRunning && root.progressData.files_per_sec > 0

                        RowLayout {
                            id: speedRow
                            anchors.centerIn: parent
                            spacing: 5

                            Text {
                                text: "⚡ " + (root.progressData.files_per_sec || 0) + " files/s (" + (root.progressData.mb_per_sec || 0) + " MB/s)"
                                font.family: "Consolas, monospace"
                                font.pixelSize: 11
                                font.weight: 600
                                color: "#38BDF8"
                            }
                        }
                    }

                    // Elapsed Time Badge
                    Rectangle {
                        implicitHeight: 22
                        implicitWidth: elapsedRow.implicitWidth + 12
                        radius: 6
                        color: "#0B0E14"
                        border.color: "#1E293B"
                        border.width: 1

                        RowLayout {
                            id: elapsedRow
                            anchors.centerIn: parent
                            spacing: 4

                            Text {
                                text: "⏱️ " + (root.progressData.elapsed_seconds || 0) + "s"
                                font.family: "Consolas, monospace"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                        }
                    }
                }

                // Sleek Animated Progress Bar
                Rectangle {
                    id: modalProgressTrack
                    Layout.fillWidth: true
                    height: 14
                    radius: 7
                    color: "#0B0E14"
                    border.color: "#1E293B"
                    border.width: 1
                    clip: true

                    readonly property bool isDiscovering: root.isRunning && !root.isPaused && root.progressData.phase === "discovering"

                    Rectangle {
                        visible: !modalProgressTrack.isDiscovering
                        height: parent.height
                        width: Math.max(8, parent.width * (Math.min(100, Math.max(0, root.progressData.percentage || 0)) / 100.0))
                        radius: 7

                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: root.isFinished ? (root.finishStatus === "cancelled" ? "#D97706" : "#10B981") : "#0284C7" }
                            GradientStop { position: 1.0; color: root.isFinished ? (root.finishStatus === "cancelled" ? "#FBBF24" : "#34D399") : "#38BDF8" }
                        }

                        Behavior on width {
                            NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
                        }
                    }

                    Rectangle {
                        id: modalShimmer
                        visible: modalProgressTrack.isDiscovering
                        width: Math.max(64, parent.width * 0.28)
                        height: parent.height
                        radius: 7
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: "transparent" }
                            GradientStop { position: 0.5; color: "#38BDF8" }
                            GradientStop { position: 1.0; color: "transparent" }
                        }
                        SequentialAnimation on x {
                            running: root.isOpen && modalProgressTrack.isDiscovering
                            loops: Animation.Infinite
                            NumberAnimation { from: -modalShimmer.width; to: modalProgressTrack.width; duration: 1200; easing.type: Easing.InOutSine }
                        }
                    }
                }

                // Current File Marquee
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    visible: root.isRunning && Boolean(root.progressData.current_file)

                    Text {
                        text: "📄"
                        font.pixelSize: 11
                    }

                    Text {
                        text: root.progressData.current_path || root.progressData.current_file || ""
                        font.family: "Consolas, monospace"
                        font.pixelSize: 11
                        color: "#64748B"
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                    }
                }

                // Telemetry Micro-Cards Grid
                GridLayout {
                    Layout.fillWidth: true
                    columns: card.width < 500 ? 2 : 4
                    rowSpacing: 8
                    columnSpacing: 8

                    // Stat 1: Files Processed / Total
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 52
                        radius: 8
                        color: "#0D111A"
                        border.color: "#1E293B"
                        border.width: 1

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 2

                            Text {
                                text: (root.progressData.processed_files || 0) + " / " + (root.progressData.total_files || 0)
                                font.family: "Consolas, monospace"
                                font.pixelSize: 13
                                font.weight: 700
                                color: "#F8FAFC"
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: root.tr("rebuild_stat_files", "Files Scanned")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#64748B"
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }

                    // Stat 2: Added to Archive
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 52
                        radius: 8
                        color: "#0D111A"
                        border.color: "#1E293B"
                        border.width: 1

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 2

                            Text {
                                text: "+" + (root.progressData.added_count || 0)
                                font.family: "Consolas, monospace"
                                font.pixelSize: 13
                                font.weight: 700
                                color: "#34D399"
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: root.tr("rebuild_stat_added", "Added")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#64748B"
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }

                    // Stat 3: Skipped (Existing)
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 52
                        radius: 8
                        color: "#0D111A"
                        border.color: "#1E293B"
                        border.width: 1

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 2

                            Text {
                                text: (root.progressData.skipped_count || 0).toString()
                                font.family: "Consolas, monospace"
                                font.pixelSize: 13
                                font.weight: 700
                                color: "#FBBF24"
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: root.tr("rebuild_stat_skipped", "Skipped")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#64748B"
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }

                    // Stat 4: Errors
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 52
                        radius: 8
                        color: "#0D111A"
                        border.color: "#1E293B"
                        border.width: 1

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 2

                            Text {
                                text: (root.progressData.error_count || 0).toString()
                                font.family: "Consolas, monospace"
                                font.pixelSize: 13
                                font.weight: 700
                                color: (root.progressData.error_count > 0) ? "#F87171" : "#64748B"
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Text {
                                text: root.tr("rebuild_stat_errors", "Errors")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#64748B"
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                }

                // Discovered Entities Line
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 28
                        radius: 6
                        color: "#0B0E14"
                        border.color: "#1E293B"
                        border.width: 1

                        RowLayout {
                            anchors.centerIn: parent
                            spacing: 6

                            Text {
                                text: "🎨 " + root.tr("rebuild_stat_creators", "Creators Found") + ":"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                            Text {
                                text: (root.progressData.total_creators || 0).toString()
                                font.family: "Consolas, monospace"
                                font.pixelSize: 11
                                font.weight: 700
                                color: "#38BDF8"
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 28
                        radius: 6
                        color: "#0B0E14"
                        border.color: "#1E293B"
                        border.width: 1

                        RowLayout {
                            anchors.centerIn: parent
                            spacing: 6

                            Text {
                                text: "📦 " + root.tr("rebuild_stat_posts", "Posts Found") + ":"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                            Text {
                                text: (root.progressData.total_posts || 0).toString()
                                font.family: "Consolas, monospace"
                                font.pixelSize: 11
                                font.weight: 700
                                color: "#A78BFA"
                            }
                        }
                    }
                }
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
