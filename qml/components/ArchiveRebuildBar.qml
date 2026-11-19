import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Persistent bottom progress bar displayed while Archive Rebuild runs (or finishes) in the background.
// Mounted above the main footer in main.qml so it stays visible across every tab.
Item {
    id: barRoot

    property var modal: null

    readonly property bool isShown: Boolean(modal && modal.showBackgroundBar)
    readonly property bool isRunning: Boolean(modal && modal.isRunning)
    readonly property bool isPaused: Boolean(modal && modal.isPaused)
    readonly property bool isFinished: Boolean(modal && modal.isFinished)
    readonly property bool isRecoveryPrompt: Boolean(modal && modal.hasSavedRebuild && !isRunning && !isFinished)
    readonly property var recoverySummary: (modal && modal.savedRebuildSummary) ? modal.savedRebuildSummary : ({})
    readonly property string finishStatus: modal ? modal.finishStatus : ""
    readonly property var progressData: (modal && modal.progressData) ? modal.progressData : ({})

    readonly property bool isDiscovering: isRunning && !isPaused && (progressData.phase === "discovering")
    readonly property real pct: Math.min(100, Math.max(0,
        isRecoveryPrompt
            ? (recoverySummary.percent || 0)
            : (isFinished ? 100 : (progressData.percentage || 0))
    ))

    // Safe animated height for ColumnLayout (avoids Behavior on height layout fighting)
    property real animHeight: isShown ? 38 : 0
    Behavior on animHeight {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    Layout.preferredHeight: animHeight
    Layout.maximumHeight: animHeight
    implicitHeight: animHeight
    visible: animHeight > 0.5
    clip: true

    function tr(key, fallback) {
        if (typeof Lang !== "undefined" && Lang) {
            var _ = Lang.activeLanguage
            var res = Lang.t(key)
            return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
        }
        return fallback !== undefined ? fallback : key
    }

    readonly property color accentColor: {
        if (isRecoveryPrompt) return "#F59E0B"
        if (isFinished) return (finishStatus === "cancelled") ? "#FBBF24" : "#10B981"
        if (isPaused) return "#FBBF24"
        return "#38BDF8"
    }

    readonly property string statusLabel: {
        if (isRecoveryPrompt) {
            return tr("rebuild_bar_interrupted", "Unfinished Archive Rebuild Saved")
        }
        if (isFinished) {
            return (finishStatus === "cancelled")
                ? tr("rebuild_status_cancelled", "Rebuild Stopped")
                : tr("rebuild_status_complete", "Archive Rebuild Complete")
        }
        if (isPaused) {
            return tr("rebuild_status_paused", "Rebuild Paused")
        }
        if (isDiscovering) {
            var found = progressData.total_files || 0
            return found > 0
                ? tr("rebuild_bar_discovering_count", "Rebuilding Archive — Discovering… (%1 found)").replace("%1", found)
                : tr("rebuild_bar_discovering", "Rebuilding Archive — Discovering files…")
        }
        return tr("rebuild_bar_running", "Rebuilding Archive")
    }

    readonly property string telemetrySummary: {
        if (isRecoveryPrompt) {
            var rProc = recoverySummary.processed_files || 0
            var rTot = recoverySummary.total_files || 0
            var rAdded = recoverySummary.added_count || 0
            if (rTot > 0) {
                return rProc + " / " + rTot + " • +" + rAdded + " " + tr("rebuild_stat_added", "Added").toLowerCase()
            }
            return tr("rebuild_bar_interrupted_discover", "Interrupted during folder scan — click Resume to continue")
        }
        var added = progressData.added_count || 0
        var skipped = progressData.skipped_count || 0
        var proc = progressData.processed_files || 0
        var tot = progressData.total_files || 0
        var fps = progressData.files_per_sec || 0
        var creators = progressData.total_creators || 0
        if (isFinished) {
            return "+" + added + " " + tr("rebuild_stat_added", "Added").toLowerCase()
                + " • " + skipped + " " + tr("rebuild_stat_skipped", "Skipped").toLowerCase()
                + (creators > 0 ? (" • " + creators + " " + tr("rebuild_bar_creators", "creators")) : "")
        }
        if (isDiscovering) {
            return progressData.current_path ? progressData.current_path : ""
        }
        var parts = [proc + " / " + tot]
        parts.push("+" + added)
        if (fps > 0 && !isPaused) {
            parts.push(fps + "/s")
        }
        return parts.join(" • ")
    }

    Rectangle {
        id: barCard
        width: parent.width
        height: 38
        anchors.bottom: parent.bottom
        color: barClickArea.containsMouse ? "#101829" : "#0C1220"
        border.color: "#1B263B"
        border.width: 1

        Behavior on color { ColorAnimation { duration: 130 } }

        // Subtle full-bar progress wash
        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: barRoot.isDiscovering ? 0 : (parent.width * (barRoot.pct / 100.0))
            color: barRoot.accentColor
            opacity: 0.08
            Behavior on width { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
        }

        // Top 2px glowing status accent edge
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 2
            color: barRoot.accentColor
            opacity: 0.75
            Behavior on color { ColorAnimation { duration: 180 } }
        }

        // Clicking anywhere on the bar opens the full Archive Rebuild modal
        MouseArea {
            id: barClickArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (barRoot.modal) {
                    barRoot.modal.isOpen = true
                }
            }
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10

            // Status Icon
            Text {
                text: barRoot.isRecoveryPrompt
                    ? "🔄"
                    : (barRoot.isFinished
                        ? (barRoot.finishStatus === "cancelled" ? "⏹️" : "✅")
                        : (barRoot.isPaused ? "⏸️" : "⚡"))
                font.pixelSize: 13
                Layout.alignment: Qt.AlignVCenter
            }

            // Status Label
            Text {
                text: barRoot.statusLabel
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: barRoot.isRecoveryPrompt
                    ? "#FCD34D"
                    : (barRoot.isFinished
                        ? (barRoot.finishStatus === "cancelled" ? "#FCD34D" : "#6EE7B7")
                        : (barRoot.isPaused ? "#FCD34D" : "#E2E8F0"))
                elide: Text.ElideRight
                Layout.minimumWidth: 0
                Layout.maximumWidth: barRoot.width < 680 ? 180 : 300
                Layout.alignment: Qt.AlignVCenter
            }

            // Dedicated Horizontal Progress Track
            Rectangle {
                id: progressTrack
                Layout.fillWidth: true
                Layout.minimumWidth: 64
                Layout.maximumWidth: 260
                height: 8
                radius: 4
                color: "#070B12"
                border.color: "#1E293B"
                border.width: 1
                clip: true
                Layout.alignment: Qt.AlignVCenter

                // Determinate fill
                Rectangle {
                    visible: !barRoot.isDiscovering
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: Math.max(barRoot.pct > 0 ? 6 : 0, parent.width * (barRoot.pct / 100.0))
                    radius: 4
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop {
                            position: 0.0
                            color: barRoot.isRecoveryPrompt
                                ? "#D97706"
                                : (barRoot.isFinished
                                    ? (barRoot.finishStatus === "cancelled" ? "#D97706" : "#059669")
                                    : (barRoot.isPaused ? "#D97706" : "#0284C7"))
                        }
                        GradientStop {
                            position: 1.0
                            color: barRoot.accentColor
                        }
                    }
                    Behavior on width { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
                }

                // Indeterminate shimmer during directory discovery
                Rectangle {
                    id: shimmerPill
                    visible: barRoot.isDiscovering
                    width: Math.max(36, parent.width * 0.32)
                    height: parent.height
                    radius: 4
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.5; color: "#38BDF8" }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                    SequentialAnimation on x {
                        running: barRoot.visible && barRoot.isDiscovering
                        loops: Animation.Infinite
                        NumberAnimation { from: -shimmerPill.width; to: progressTrack.width; duration: 1200; easing.type: Easing.InOutSine }
                    }
                }
            }

            // Percentage Badge
            Text {
                visible: !barRoot.isDiscovering && (!barRoot.isRecoveryPrompt || (barRoot.recoverySummary.total_files || 0) > 0)
                text: Math.round(barRoot.pct) + "%"
                font.family: "Consolas, monospace"
                font.pixelSize: 11
                font.weight: 700
                color: barRoot.accentColor
                Layout.alignment: Qt.AlignVCenter
            }

            // Live Telemetry Summary (hides cleanly on very narrow windows)
            Text {
                visible: barRoot.width >= 560 && barRoot.telemetrySummary.length > 0
                text: barRoot.telemetrySummary
                font.family: "Consolas, Segoe UI, monospace"
                font.pixelSize: 11
                color: "#94A3B8"
                elide: barRoot.isDiscovering ? Text.ElideMiddle : Text.ElideRight
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.alignment: Qt.AlignVCenter
            }

            // Spacer when telemetry is hidden
            Item {
                visible: !(barRoot.width >= 560 && barRoot.telemetrySummary.length > 0)
                Layout.fillWidth: true
            }

            // ── Compact Controls ───────────────────────────────────────
            // Resume Saved Checkpoint (when interrupted from crash / power loss / close)
            Rectangle {
                visible: barRoot.isRecoveryPrompt
                implicitHeight: 24
                implicitWidth: resumeSavedRow.implicitWidth + 14
                radius: 5
                color: resumeSavedMouse.containsMouse ? "#065F46" : "#064E3B"
                border.color: resumeSavedMouse.containsMouse ? "#34D399" : "#10B981"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Row {
                    id: resumeSavedRow
                    anchors.centerIn: parent
                    spacing: 4
                    Text { text: "▶"; font.pixelSize: 10; color: "#6EE7B7"; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: barRoot.tr("rebuild_btn_resume", "Resume")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#ECFDF5"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: resumeSavedMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: barRoot.tr("rebuild_bar_resume_saved_tip", "Resume Archive Rebuild right where it left off in the background")
                    onClicked: {
                        if (barRoot.modal) barRoot.modal.resumeSavedRebuild(true)
                    }
                }
            }

            // Pause / Resume (when running)
            Rectangle {
                visible: barRoot.isRunning
                implicitHeight: 24
                implicitWidth: pauseRow.implicitWidth + 14
                radius: 5
                color: pauseBtnMouse.containsMouse ? "#1E293B" : "#111827"
                border.color: pauseBtnMouse.containsMouse ? "#475569" : "#243045"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Row {
                    id: pauseRow
                    anchors.centerIn: parent
                    spacing: 4
                    Text {
                        text: barRoot.isPaused ? "▶️" : "⏸️"
                        font.pixelSize: 10
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        visible: barRoot.width >= 760
                        text: barRoot.isPaused
                            ? barRoot.tr("rebuild_btn_resume", "Resume")
                            : barRoot.tr("rebuild_btn_pause", "Pause")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#E2E8F0"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: pauseBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 350
                    ToolTip.text: barRoot.isPaused
                        ? barRoot.tr("rebuild_btn_resume", "Resume")
                        : barRoot.tr("rebuild_btn_pause", "Pause")
                    onClicked: {
                        if (barRoot.modal) barRoot.modal.togglePause()
                    }
                }
            }

            // Expand / View Summary Button
            Rectangle {
                implicitHeight: 24
                implicitWidth: detailsRow.implicitWidth + 14
                radius: 5
                color: detailsBtnMouse.containsMouse ? "#152B42" : "#0F2033"
                border.color: detailsBtnMouse.containsMouse ? "#38BDF8" : "#1E4268"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Row {
                    id: detailsRow
                    anchors.centerIn: parent
                    spacing: 4
                    Text {
                        text: barRoot.isFinished ? "📊" : "↗"
                        font.pixelSize: 10
                        color: "#38BDF8"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: barRoot.isFinished
                            ? barRoot.tr("rebuild_bar_summary", "View Summary")
                            : barRoot.tr("rebuild_bar_details", "Details")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#7DD3FC"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: detailsBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 350
                    ToolTip.text: barRoot.tr("rebuild_bar_expand_tip", "Open the full Archive Rebuild dashboard")
                    onClicked: {
                        if (barRoot.modal) barRoot.modal.isOpen = true
                    }
                }
            }

            // Cancel Rebuild (when running)
            Rectangle {
                visible: barRoot.isRunning
                implicitHeight: 24
                implicitWidth: 26
                radius: 5
                color: stopBtnMouse.containsMouse ? "#3B151B" : "#1D1216"
                border.color: stopBtnMouse.containsMouse ? "#EF4444" : "#4C1D24"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Text {
                    anchors.centerIn: parent
                    text: "⏹"
                    font.pixelSize: 11
                    color: stopBtnMouse.containsMouse ? "#FCA5A5" : "#F87171"
                }

                MouseArea {
                    id: stopBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: barRoot.tr("rebuild_bar_stop_tip", "Stop Archive Rebuild")
                    onClicked: {
                        if (barRoot.modal) barRoot.modal.cancelRebuild()
                    }
                }
            }

            // Discard Saved Checkpoint (when recovery prompt)
            Rectangle {
                visible: barRoot.isRecoveryPrompt
                implicitHeight: 24
                implicitWidth: 26
                radius: 5
                color: discardSavedMouse.containsMouse ? "#3B151B" : "transparent"
                border.color: discardSavedMouse.containsMouse ? "#EF4444" : "transparent"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    font.pixelSize: 11
                    font.weight: 700
                    color: discardSavedMouse.containsMouse ? "#FCA5A5" : "#94A3B8"
                }

                MouseArea {
                    id: discardSavedMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: barRoot.tr("rebuild_bar_discard_saved_tip", "Discard saved Archive Rebuild checkpoint")
                    onClicked: {
                        if (barRoot.modal) barRoot.modal.discardSavedRebuild()
                    }
                }
            }

            // Dismiss Completed/Stopped Banner (when finished)
            Rectangle {
                visible: barRoot.isFinished && !barRoot.isRunning
                implicitHeight: 24
                implicitWidth: 26
                radius: 5
                color: dismissBtnMouse.containsMouse ? "#263248" : "transparent"
                border.color: dismissBtnMouse.containsMouse ? "#475569" : "transparent"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    font.pixelSize: 11
                    font.weight: 700
                    color: dismissBtnMouse.containsMouse ? "#F8FAFC" : "#94A3B8"
                }

                MouseArea {
                    id: dismissBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: barRoot.tr("rebuild_bar_dismiss", "Dismiss")
                    onClicked: {
                        if (barRoot.modal) barRoot.modal.dismissBackgroundBanner()
                    }
                }
            }
        }
    }
}
