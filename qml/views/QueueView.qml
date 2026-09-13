import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Rectangle {
    id: root

    property var bridge: null
    color: "#0F1117"

    readonly property bool isNarrow: root.width < 780
    readonly property bool isVeryNarrow: root.width < 520

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    // 1-second live refresh timer — forces active downloading rows to repaint live speed/ETA
    Timer {
        id: liveRefreshTimer
        interval: 1000
        repeat: true
        running: root.bridge ? root.bridge.isDownloading : false
        onTriggered: {
            if (!root.bridge || !root.bridge.queueModel) return
            var model = root.bridge.queueModel
            var count = model.rowCount()
            if (count > 0) {
                model.dataChanged(model.index(0, 0), model.index(count - 1, 0))
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // 1. Header Toolbar
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            // Row 1: Title, Count Badge, and Primary Queue Actions
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: "📋 " + root.tr("title_task_queue", "Task Queue")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    color: "#F8FAFC"
                }

                // Total count badge
                Rectangle {
                    width: Math.max(24, totalCountText.implicitWidth + 12)
                    height: 20; radius: 10; color: "#242A38"
                    Text {
                        id: totalCountText
                        anchors.centerIn: parent
                        text: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.totalCount.toString() : "0"
                        font.pixelSize: 10; font.bold: true; color: "#38BDF8"
                    }
                }

                Item { Layout.fillWidth: true }

                // Quick Action: Retry Failed (prominent when errors exist)
                StyledButton {
                    id: retryFailedBtn
                    visible: (root.bridge && root.bridge.queueModel && root.bridge.queueModel.failedCount > 0)
                    text: root.tr("btn_retry_failed", "Retry Failed")
                    iconText: "🔁"
                    variant: "danger"
                    implicitHeight: 28
                    tooltip: root.tr("tip_retry_failed", "Open selective retry dialog to inspect and re-download failed files")
                    onClicked: retryModal.isOpen = true
                }

                // Quick Action: Clear Queue
                StyledButton {
                    text: root.tr("btn_clear_queue", "Clear")
                    iconText: "🗑"
                    variant: "ghost"
                    implicitHeight: 28
                    tooltip: root.tr("tip_clear_queue", "Remove all tasks from queue")
                    onClicked: if (root.bridge && root.bridge.queueModel) root.bridge.queueModel.clear()
                }
            }

            // Row 2: Secondary Queue Utility Actions in an auto-wrapping Flow
            Flow {
                Layout.fillWidth: true
                spacing: 6

                StyledButton {
                    text: root.tr("btn_download_links", "Download Links")
                    iconText: "☁️"
                    variant: (root.bridge && root.bridge.hasHarvestedLinks) ? "primary" : "outline"
                    implicitHeight: 26
                    tooltip: root.tr("tip_download_links", "Open dialog to download harvested links via Mega.nz, Google Drive, Dropbox, or GoFile")
                    opacity: (root.bridge && root.bridge.hasHarvestedLinks) ? 1.0 : 0.6
                    onClicked: cloudModal.isOpen = true
                }

                StyledButton {
                    text: root.tr("btn_export_links", "Export Links")
                    iconText: "🔗"
                    variant: "outline"
                    implicitHeight: 26
                    tooltip: root.tr("tip_export_links", "Export harvested external cloud links to text file")
                    onClicked: if (root.bridge) root.bridge.exportAllLinks()
                }

                StyledButton {
                    text: root.tr("btn_export_queue", "Export State")
                    iconText: "💾"
                    variant: "outline"
                    implicitHeight: 26
                    tooltip: root.tr("tip_export_queue", "Export queue snapshot with progress and settings to a backup JSON file")
                    onClicked: if (root.bridge) root.bridge.exportQueueState()
                }

                StyledButton {
                    text: root.tr("btn_import_queue", "Import State")
                    iconText: "📂"
                    variant: "outline"
                    implicitHeight: 26
                    tooltip: root.tr("tip_import_queue", "Load a saved queue backup file (Merge or Replace)")
                    onClicked: importModal.isOpen = true
                }

                // If failedCount is 0, show Retry Failed as ghost button here so it's always accessible
                StyledButton {
                    visible: !(root.bridge && root.bridge.queueModel && root.bridge.queueModel.failedCount > 0)
                    text: root.tr("btn_retry_failed", "Retry Failed")
                    iconText: "🔁"
                    variant: "ghost"
                    implicitHeight: 26
                    tooltip: root.tr("tip_retry_failed", "Open selective retry dialog to inspect and re-download failed files")
                    opacity: 0.45
                    onClicked: retryModal.isOpen = true
                }
            }
        }

        // 2. Status Filter Tabs & View Mode Switcher
        Flow {
            Layout.fillWidth: true
            spacing: 8

            // Filter Tabs in a non-overlapping Row
            Row {
                id: filterTabsRow
                spacing: 6

                Repeater {
                    model: [
                        { key: "all", labelKey: "qtab_all", defaultLabel: "All", icon: "📁", count: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.totalCount : 0, color: "#38BDF8", tipKey: "qtab_all_tip", defaultTip: "Show all download tasks in queue" },
                        { key: "downloading", labelKey: "qtab_active", defaultLabel: "Active", icon: "⚡", count: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.downloadingCount : 0, color: "#0EA5E9", tipKey: "qtab_active_tip", defaultTip: "Show active/in-progress downloads" },
                        { key: "completed", labelKey: "qtab_completed", defaultLabel: "Completed", icon: "✔", count: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.completedCount : 0, color: "#10B981", tipKey: "qtab_completed_tip", defaultTip: "Show successfully completed downloads" },
                        { key: "failed", labelKey: "qtab_failed", defaultLabel: "Errors / Failed", icon: "✖", count: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.failedCount : 0, color: "#EF4444", tipKey: "qtab_failed_tip", defaultTip: "Show failed download tasks" }
                    ]

                    delegate: Rectangle {
                        id: tabRect
                        height: 26
                        property bool isSelected: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.filterStatus === modelData.key : false
                        property bool showLabel: root.width >= 560

                        // Direct intrinsic calculation with NO cyclic bindings
                        width: tabIconText.implicitWidth + (showLabel ? (tabLabelText.implicitWidth + 6) : 0) + countPill.width + 18
                        radius: 5

                        color: isSelected ? (modelData.key === "failed" ? "#3B181E" : "#1A2638") : (tabMouse.containsMouse ? "#1E2430" : "#141720")
                        border.color: isSelected ? (modelData.key === "failed" ? "#EF4444" : modelData.color) : (modelData.key === "failed" && modelData.count > 0 ? "#7F1D1D" : "#242A38")
                        border.width: isSelected ? 1.5 : 1

                        scale: tabMouse.pressed ? 0.93 : (tabMouse.containsMouse ? 1.04 : 1.0)
                        transformOrigin: Item.Center

                        Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }
                        Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                        Behavior on border.color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }

                        Row {
                            anchors.centerIn: parent
                            spacing: 5

                            Text {
                                id: tabIconText
                                text: modelData.icon
                                font.pixelSize: 10
                                color: isSelected ? modelData.color : "#94A3B8"
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                id: tabLabelText
                                visible: tabRect.showLabel
                                text: root.tr(modelData.labelKey, modelData.defaultLabel)
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: isSelected ? 600 : Font.Normal
                                color: isSelected ? "#F8FAFC" : "#94A3B8"
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            // Count pill
                            Rectangle {
                                id: countPill
                                height: 16
                                width: Math.max(16, cntText.implicitWidth + 8)
                                radius: 8
                                anchors.verticalCenter: parent.verticalCenter
                                color: modelData.key === "failed" && modelData.count > 0 ? "#EF4444" : (isSelected ? "#2E3B50" : "#1E2330")

                                Behavior on color { ColorAnimation { duration: 150 } }

                                Text {
                                    id: cntText
                                    anchors.centerIn: parent
                                    text: modelData.count.toString()
                                    font.pixelSize: 9
                                    font.bold: true
                                    color: modelData.key === "failed" && modelData.count > 0 ? "#FFFFFF" : (isSelected ? modelData.color : "#64748B")
                                }
                            }
                        }

                        MouseArea {
                            id: tabMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: root.tr(modelData.tipKey, modelData.defaultTip)
                            onClicked: {
                                if (root.bridge && root.bridge.queueModel) {
                                    root.bridge.queueModel.filterStatus = modelData.key
                                }
                            }
                        }
                    }
                }
            }

            // View Mode Switcher (Grouped vs Flat)
            Rectangle {
                height: 26
                width: modeRow.implicitWidth + 8
                radius: 5
                color: "#161A24"
                border.color: "#282E3D"
                border.width: 1

                Row {
                    id: modeRow
                    anchors.centerIn: parent
                    spacing: 3

                    // Grouped Mode Button
                    Rectangle {
                        height: 20
                        width: grpText.implicitWidth + 12
                        radius: 3
                        color: (root.bridge && root.bridge.queueModel && root.bridge.queueModel.viewMode === "grouped") ? "#2563EB" : (grpHover.containsMouse ? "#222736" : "transparent")
                        Text {
                            id: grpText
                            anchors.centerIn: parent
                            text: "👥 " + root.tr("view_grouped", "Grouped")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: (root.bridge && root.bridge.queueModel && root.bridge.queueModel.viewMode === "grouped") ? Font.Bold : Font.Normal
                            color: "#FFFFFF"
                        }
                        MouseArea {
                            id: grpHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.text: root.tr("view_grouped", "Grouped")
                            onClicked: {
                                if (root.bridge && root.bridge.queueModel) {
                                    root.bridge.queueModel.viewMode = "grouped"
                                }
                            }
                        }
                    }

                    // Flat Mode Button
                    Rectangle {
                        height: 20
                        width: flatText.implicitWidth + 12
                        radius: 3
                        color: (root.bridge && root.bridge.queueModel && root.bridge.queueModel.viewMode === "flat") ? "#2563EB" : (flatHover.containsMouse ? "#222736" : "transparent")
                        Text {
                            id: flatText
                            anchors.centerIn: parent
                            text: "📄 " + root.tr("view_flat", "Flat List")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: (root.bridge && root.bridge.queueModel && root.bridge.queueModel.viewMode === "flat") ? Font.Bold : Font.Normal
                            color: "#FFFFFF"
                        }
                        MouseArea {
                            id: flatHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.text: root.tr("view_flat", "Flat List")
                            onClicked: {
                                if (root.bridge && root.bridge.queueModel) {
                                    root.bridge.queueModel.viewMode = "flat"
                                    root.bridge.queueModel.selectedBatchId = ""
                                }
                            }
                        }
                    }
                }
            }
        }

        // 3. Tasks Container
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#141720"
            border.color: "#242A38"
            border.width: 1
            radius: 8
            clip: true

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 6
                spacing: 6

                // Drilldown Breadcrumb Header when inspecting a specific batch
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32
                    radius: 6
                    color: "#1A2333"
                    border.color: "#38BDF8"
                    border.width: 1
                    visible: root.bridge && root.bridge.queueModel && root.bridge.queueModel.selectedBatchId !== ""

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 8

                        Rectangle {
                            height: 22
                            width: backBtnText.implicitWidth + 14
                            radius: 4
                            color: backMouse.containsMouse ? "#0284C7" : "#0EA5E9"
                            Text {
                                id: backBtnText
                                anchors.centerIn: parent
                                text: "⬅ " + root.tr("btn_back_to_groups", "Back to Batches")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.bold: true
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                id: backMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (root.bridge && root.bridge.queueModel) {
                                        root.bridge.queueModel.selectedBatchId = ""
                                    }
                                }
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: "📁 " + (root.bridge && root.bridge.queueModel ? root.bridge.queueModel.selectedBatchId : "")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.bold: true
                            color: "#F8FAFC"
                            elide: Text.ElideMiddle
                        }
                    }
                }

                // Grouped Batches ListView
                SmoothListView {
                    id: groupsList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 8
                    clip: true
                    visible: root.bridge && root.bridge.queueModel && root.bridge.queueModel.viewMode === "grouped" && root.bridge.queueModel.selectedBatchId === ""
                    model: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.groups : []

                    delegate: Rectangle {
                        id: groupCard
                        width: groupsList.width - 12
                        implicitHeight: cardInnerCol.implicitHeight + 20
                        radius: 8
                        color: modelData.status === "failed" ? "#22161A" : (modelData.status === "downloading" ? "#131E30" : (cardMouse.containsMouse ? "#1D2332" : "#171B26"))
                        border.color: modelData.status === "downloading" ? "#0EA5E9" : (modelData.status === "failed" ? "#EF4444" : (cardMouse.containsMouse ? "#3B465E" : "#283042"))
                        border.width: 1.5

                        Behavior on color { ColorAnimation { duration: 150 } }
                        Behavior on border.color { ColorAnimation { duration: 150 } }

                        MouseArea {
                            id: cardMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            z: -1
                        }

                        ColumnLayout {
                            id: cardInnerCol
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 8

                            // Top line: Service badge, Creator, Post title, Status pill
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Rectangle {
                                    height: 20
                                    width: svcText.implicitWidth + 10
                                    radius: 4
                                    color: "#222C3D"
                                    Text {
                                        id: svcText
                                        anchors.centerIn: parent
                                        text: (modelData.service || "kemono").toUpperCase()
                                        font.pixelSize: 9
                                        font.bold: true
                                        color: "#38BDF8"
                                    }
                                }

                                Text {
                                    text: modelData.creatorName
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 13
                                    font.weight: Font.Bold
                                    color: "#F8FAFC"
                                }

                                Text {
                                    text: "•"
                                    color: "#64748B"
                                    font.pixelSize: 11
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.postTitle
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    color: "#94A3B8"
                                    elide: Text.ElideRight
                                }

                                // Status Badge
                                Rectangle {
                                    height: 20
                                    width: stText.implicitWidth + 10
                                    radius: 4
                                    color: modelData.status === "completed" ? "#064E3B" : (modelData.status === "downloading" ? "#0C4A6E" : (modelData.status === "failed" ? "#7F1D1D" : "#1E293B"))
                                    border.color: modelData.status === "completed" ? "#10B981" : (modelData.status === "downloading" ? "#0EA5E9" : (modelData.status === "failed" ? "#EF4444" : "#475569"))
                                    border.width: 1

                                    Text {
                                        id: stText
                                        anchors.centerIn: parent
                                        text: modelData.status.toUpperCase()
                                        font.pixelSize: 9
                                        font.bold: true
                                        color: modelData.status === "completed" ? "#6EE7B7" : (modelData.status === "downloading" ? "#7DD3FC" : (modelData.status === "failed" ? "#FCA5A5" : "#94A3B8"))
                                    }
                                }
                            }

                            // Dual Progress Bars
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4

                                // Total progress (file counter)
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text {
                                        text: "Total"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: "#64748B"
                                        Layout.preferredWidth: 36
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 5
                                        radius: 2
                                        color: "#1F2636"

                                        Rectangle {
                                            height: parent.height
                                            width: parent.width * Math.min(1.0, Math.max(0.0,
                                                (modelData.totalProgress !== undefined ? modelData.totalProgress : modelData.progress)))
                                            radius: 2
                                            color: modelData.status === "completed" ? "#10B981" : (modelData.status === "failed" ? "#EF4444" : "#10B981")
                                            Behavior on width { NumberAnimation { duration: 200 } }
                                        }
                                    }

                                    Text {
                                        text: modelData.completedFiles + "/" + modelData.totalFiles
                                        font.family: "Cascadia Code, Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: "#94A3B8"
                                        Layout.preferredWidth: 42
                                        horizontalAlignment: Text.AlignRight
                                    }
                                }

                                // Active file progress
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    visible: modelData.status === "downloading" && modelData.activeFileName !== undefined && modelData.activeFileName !== ""

                                    Text {
                                        text: "File"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: "#64748B"
                                        Layout.preferredWidth: 36
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 5
                                        radius: 2
                                        color: "#1F2636"

                                        Rectangle {
                                            height: parent.height
                                            width: parent.width * Math.min(1.0, Math.max(0.0,
                                                (modelData.activeFileProgressPct !== undefined ? modelData.activeFileProgressPct / 100.0 : 0)))
                                            radius: 2
                                            color: "#38BDF8"
                                            Behavior on width { NumberAnimation { duration: 150 } }
                                        }
                                    }

                                    Text {
                                        text: (modelData.activeFileProgressPct !== undefined ? modelData.activeFileProgressPct : 0) + "%"
                                        font.family: "Cascadia Code, Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: "#38BDF8"
                                        Layout.preferredWidth: 42
                                        horizontalAlignment: Text.AlignRight
                                    }
                                }

                                // Active file name + speed row
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    visible: modelData.status === "downloading" && modelData.activeFileName !== undefined && modelData.activeFileName !== ""

                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.activeFileName !== undefined ? modelData.activeFileName : ""
                                        font.family: "Cascadia Code, Segoe UI Mono, monospace"
                                        font.pixelSize: 10
                                        color: "#64748B"
                                        elide: Text.ElideMiddle
                                    }

                                    Text {
                                        text: modelData.activeFileSpeed !== undefined ? modelData.activeFileSpeed : ""
                                        font.family: "Cascadia Code, Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: "#38BDF8"
                                    }
                                }
                            }

                            // Bottom Row: Responsive File Counts, Data Size, and Control Buttons
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                visible: root.isNarrow

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text {
                                        text: modelData.completedFiles + " / " + modelData.totalFiles + " files" + (modelData.failedFiles > 0 ? (" (" + modelData.failedFiles + " failed)") : "")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: modelData.failedFiles > 0 ? "#F87171" : "#94A3B8"
                                    }

                                    Text { text: "•"; color: "#475569"; font.pixelSize: 10 }

                                    Text {
                                        text: modelData.downloadedBytesStr
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: "#94A3B8"
                                    }
                                }

                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    StyledButton {
                                        text: root.isVeryNarrow ? "" : root.tr("btn_view_files", "View Files")
                                        iconText: "🔍"
                                        variant: "outline"
                                        implicitHeight: 24
                                        tooltip: root.tr("btn_view_files", "View Files")
                                        onClicked: {
                                            if (root.bridge && root.bridge.queueModel) {
                                                root.bridge.queueModel.selectedBatchId = modelData.batchId
                                            }
                                        }
                                    }

                                    StyledButton {
                                        visible: modelData.failedFiles > 0
                                        text: root.isVeryNarrow ? "" : root.tr("btn_retry_batch", "Retry Failed")
                                        iconText: "🔁"
                                        variant: "danger"
                                        implicitHeight: 24
                                        tooltip: root.tr("btn_retry_batch", "Retry Failed")
                                        onClicked: {
                                            if (root.bridge && root.bridge.queueModel) {
                                                root.bridge.queueModel.retryBatch(modelData.batchId)
                                            }
                                        }
                                    }

                                    StyledButton {
                                        visible: modelData.downloadingFiles > 0 || modelData.pendingFiles > 0
                                        text: root.isVeryNarrow ? "" : root.tr("btn_cancel_batch", "Cancel")
                                        iconText: "⏸"
                                        variant: "ghost"
                                        implicitHeight: 24
                                        tooltip: root.tr("btn_cancel_batch", "Cancel")
                                        onClicked: {
                                            if (root.bridge && root.bridge.queueModel) {
                                                root.bridge.queueModel.cancelBatch(modelData.batchId)
                                            }
                                        }
                                    }

                                    StyledButton {
                                        text: root.isVeryNarrow ? "" : root.tr("btn_remove_batch", "Remove")
                                        iconText: "🗑"
                                        variant: "ghost"
                                        implicitHeight: 24
                                        tooltip: root.tr("btn_remove_batch", "Remove")
                                        onClicked: {
                                            if (root.bridge && root.bridge.queueModel) {
                                                root.bridge.queueModel.removeBatch(modelData.batchId)
                                            }
                                        }
                                    }
                                }
                            }

                            // Wide mode single-row layout
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                visible: !root.isNarrow

                                Text {
                                    text: modelData.completedFiles + " / " + modelData.totalFiles + " files" + (modelData.failedFiles > 0 ? (" (" + modelData.failedFiles + " failed)") : "")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    color: modelData.failedFiles > 0 ? "#F87171" : "#94A3B8"
                                }

                                Text { text: "•"; color: "#475569"; font.pixelSize: 10 }

                                Text {
                                    text: modelData.downloadedBytesStr
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    color: "#94A3B8"
                                }

                                Item { Layout.fillWidth: true }

                                // Action buttons
                                StyledButton {
                                    text: root.tr("btn_view_files", "View Files")
                                    iconText: "🔍"
                                    variant: "outline"
                                    implicitHeight: 24
                                    tooltip: root.tr("btn_view_files", "View Files")
                                    onClicked: {
                                        if (root.bridge && root.bridge.queueModel) {
                                            root.bridge.queueModel.selectedBatchId = modelData.batchId
                                        }
                                    }
                                }

                                StyledButton {
                                    visible: modelData.failedFiles > 0
                                    text: root.tr("btn_retry_batch", "Retry Failed")
                                    iconText: "🔁"
                                    variant: "danger"
                                    implicitHeight: 24
                                    tooltip: root.tr("btn_retry_batch", "Retry Failed")
                                    onClicked: {
                                        if (root.bridge && root.bridge.queueModel) {
                                            root.bridge.queueModel.retryBatch(modelData.batchId)
                                        }
                                    }
                                }

                                StyledButton {
                                    visible: modelData.downloadingFiles > 0 || modelData.pendingFiles > 0
                                    text: root.tr("btn_cancel_batch", "Cancel")
                                    iconText: "⏸"
                                    variant: "ghost"
                                    implicitHeight: 24
                                    tooltip: root.tr("btn_cancel_batch", "Cancel")
                                    onClicked: {
                                        if (root.bridge && root.bridge.queueModel) {
                                            root.bridge.queueModel.cancelBatch(modelData.batchId)
                                        }
                                    }
                                }

                                StyledButton {
                                    text: root.tr("btn_remove_batch", "Remove")
                                    iconText: "🗑"
                                    variant: "ghost"
                                    implicitHeight: 24
                                    tooltip: root.tr("btn_remove_batch", "Remove")
                                    onClicked: {
                                        if (root.bridge && root.bridge.queueModel) {
                                            root.bridge.queueModel.removeBatch(modelData.batchId)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Empty state for groups
                    Text {
                        anchors.centerIn: parent
                        text: root.tr("empty_no_batches", "No creator or post batches in queue.\nEnter a creator or post link and click 'Add to Queue'.")
                        color: "#475569"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        visible: groupsList.count === 0
                    }
                }

                // 3. Individual Files ListView
                SmoothListView {
                    id: queueList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 6
                    clip: true
                    visible: root.bridge && root.bridge.queueModel && (root.bridge.queueModel.viewMode === "flat" || root.bridge.queueModel.selectedBatchId !== "")
                    model: root.bridge ? root.bridge.queueModel : null

                delegate: Rectangle {
                    id: delegateRoot
                    width: queueList.width - 12
                    implicitHeight: taskCol.implicitHeight + 16
                    radius: 6
                    color: model.status === "failed" ? "#1F161A" : (model.status === "downloading" ? "#131E2E" : (delegateHover.containsMouse ? "#1D222F" : "#1A1E29"))
                    border.color: model.status === "downloading" ? "#38BDF8" : (model.status === "failed" ? "#EF4444" : (delegateHover.containsMouse ? "#3E485D" : "#282E3D"))
                    border.width: model.status === "failed" ? 1.5 : 1

                    Behavior on color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }
                    Behavior on border.color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }

                    MouseArea {
                        id: delegateHover
                        anchors.fill: parent
                        hoverEnabled: true
                        z: -1
                    }

                    ColumnLayout {
                        id: taskCol
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 6

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            // Service / Status badge
                            Rectangle {
                                implicitWidth: statusText.implicitWidth + 16
                                implicitHeight: 20
                                Layout.preferredWidth: statusText.implicitWidth + 16
                                Layout.preferredHeight: 20
                                Layout.alignment: Qt.AlignVCenter
                                radius: 4
                                color: {
                                    if (model.status === "completed") return "#10B981"
                                    if (model.status === "downloading") return "#0284C7"
                                    if (model.status === "failed") return "#EF4444"
                                    return "#333A48"
                                }

                                Behavior on color { ColorAnimation { duration: 200 } }

                                Text {
                                    id: statusText
                                    anchors.centerIn: parent
                                    text: model.status.toUpperCase()
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 9
                                    font.bold: true
                                    color: "#FFFFFF"
                                }
                            }

                            // Filename
                            Text {
                                text: model.filename
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: 600
                                color: model.status === "failed" ? "#FCA5A5" : "#F1F5F9"
                                Layout.fillWidth: true
                                elide: Text.ElideMiddle
                            }

                            // Progress Percentage badge & Retry Action
                            Row {
                                spacing: 6
                                Layout.alignment: Qt.AlignRight

                                // Percentage Badge
                                Rectangle {
                                    height: 20
                                    width: pctText.implicitWidth + 14
                                    radius: 4
                                    color: {
                                        if (model.status === "completed") return "#064E3B"
                                        if (model.status === "downloading") return "#0C4A6E"
                                        if (model.status === "failed") return "#450A0A"
                                        return "#1E293B"
                                    }
                                    border.color: {
                                        if (model.status === "completed") return "#10B981"
                                        if (model.status === "downloading") return "#38BDF8"
                                        if (model.status === "failed") return "#EF4444"
                                        return "#334155"
                                    }
                                    border.width: 1
                                    anchors.verticalCenter: parent.verticalCenter

                                    Text {
                                        id: pctText
                                        anchors.centerIn: parent
                                        text: {
                                            if (model.status === "completed") return "100%"
                                            if (model.status === "failed") return (model.retryCount > 0 ? ("Failed (" + model.retryCount + "x)") : "Failed")
                                            if (model.status === "downloading") return model.percentage + "%"
                                            return "0%"
                                        }
                                        font.family: "Cascadia Code, Consolas, monospace"
                                        font.pixelSize: 10
                                        font.weight: Font.Bold
                                        color: {
                                            if (model.status === "completed") return "#34D399"
                                            if (model.status === "downloading") return "#38BDF8"
                                            if (model.status === "failed") return "#FCA5A5"
                                            return "#94A3B8"
                                        }
                                    }
                                }

                                // Single Item Retry Button (Visible for failed items)
                                Rectangle {
                                    width: 22
                                    height: 20
                                    radius: 4
                                    color: itemRetryMouse.containsMouse ? "#EF4444" : "#2E1A20"
                                    border.color: "#EF4444"
                                    border.width: 1
                                    visible: model.status === "failed"
                                    anchors.verticalCenter: parent.verticalCenter

                                    scale: itemRetryMouse.pressed ? 0.85 : (itemRetryMouse.containsMouse ? 1.18 : 1.0)
                                    transformOrigin: Item.Center

                                    Behavior on scale {
                                        NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.6 }
                                    }
                                    Behavior on color { ColorAnimation { duration: 120 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "↻"
                                        font.pixelSize: 12
                                        font.bold: true
                                        color: itemRetryMouse.containsMouse ? "#FFFFFF" : "#F87171"
                                    }

                                    MouseArea {
                                        id: itemRetryMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (root.bridge && root.bridge.queueModel) {
                                                root.bridge.queueModel.retryTaskAt(index)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Subline info (Post title & Creator)
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            Text {
                                text: model.creatorName + " [" + model.service + "]: " + model.postTitle
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#64748B"
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }

                        // Progress Bar (when downloading or completed)
                        Rectangle {
                            Layout.fillWidth: true
                            height: 4
                            radius: 2
                            color: "#10131A"
                            visible: model.status !== "failed"

                            Rectangle {
                                height: parent.height
                                radius: 2
                                width: Math.max(0, Math.min(parent.width, parent.width * model.progress))
                                color: model.status === "completed" ? "#10B981" : "#38BDF8"

                                Behavior on width {
                                    NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
                                }
                                Behavior on color {
                                    ColorAnimation { duration: 200 }
                                }
                            }
                        }

                        // Detailed Error Box with Retry Action (Visible when failed)
                        Rectangle {
                            Layout.fillWidth: true
                            height: errorRow.implicitHeight + 8
                            radius: 4
                            color: "#2C1217"
                            border.color: "#5C1D24"
                            border.width: 1
                            visible: model.status === "failed" && model.errorMsg.length > 0

                            RowLayout {
                                id: errorRow
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 6

                                Text {
                                    text: "⚠️"
                                    font.pixelSize: 11
                                }

                                Text {
                                    text: (model.retryCount > 0 ? ("[" + model.retryCount + " " + (model.retryCount === 1 ? root.tr("label_failed_retry", "retry failed") : root.tr("label_failed_retries", "retries failed")) + "] ") : "") + model.errorMsg
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    color: "#FCA5A5"
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                }

                                StyledButton {
                                    text: root.tr("btn_retry", "Retry")
                                    iconText: "↻"
                                    variant: "danger"
                                    implicitHeight: 20
                                    onClicked: {
                                        if (root.bridge && root.bridge.queueModel) {
                                            root.bridge.queueModel.retryTaskAt(index)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Empty state placeholder
                Text {
                    anchors.centerIn: parent
                    text: {
                        var status = root.bridge && root.bridge.queueModel ? root.bridge.queueModel.filterStatus : "all"
                        if (status === "failed") return root.tr("empty_no_failed", "🎉 No failed downloads!\nAll tasks completed without errors.")
                        if (status === "downloading") return root.tr("empty_no_active", "⚡ No active downloads running.\nStart a download to see active files.")
                        if (status === "completed") return root.tr("empty_no_completed", "📁 No completed downloads yet.")
                        return root.tr("empty_no_tasks", "No download tasks in queue.\nEnter a URL and click 'Start Download' or 'Add to Queue'.")
                    }
                    color: "#475569"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 13
                    horizontalAlignment: Text.AlignHCenter
                    visible: queueList.count === 0

                }
            }
        }
    }
}

    // Modal popup dialog for selectively retrying failed downloads
    RetryModal {
        id: retryModal
        bridge: root.bridge
    }

    // Modal popup dialog for downloading harvested external cloud links
    CloudDownloadModal {
        id: cloudModal
        bridge: root.bridge
    }

    // Modal popup dialog for importing queue state snapshot
    ImportConfirmModal {
        id: importModal
        bridge: root.bridge
    }
}
