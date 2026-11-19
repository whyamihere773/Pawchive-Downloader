import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "queue"

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
        running: root.visible && (root.bridge ? root.bridge.isDownloading : false)
        onTriggered: {
            if (!root.bridge || !root.bridge.queueModel) return
            var model = root.bridge.queueModel
            if (model.refreshActiveRows) {
                model.refreshActiveRows()
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
                    onClicked: if (typeof appWindow !== "undefined" && typeof appWindow.openRetryModal === "function") appWindow.openRetryModal()
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
                    onClicked: if (typeof appWindow !== "undefined" && typeof appWindow.openCloudModal === "function") appWindow.openCloudModal()
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
                    onClicked: if (typeof appWindow !== "undefined" && typeof appWindow.openImportModal === "function") appWindow.openImportModal()
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
                    onClicked: if (typeof appWindow !== "undefined" && typeof appWindow.openRetryModal === "function") appWindow.openRetryModal()
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
                        { key: "skipped", labelKey: "qtab_skipped", defaultLabel: "Skipped", icon: "⏭️", count: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.skippedCount : 0, color: "#F59E0B", tipKey: "qtab_skipped_tip", defaultTip: "Show downloads skipped by filters or rules" },
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

                        color: isSelected ? (modelData.key === "failed" ? "#3B181E" : (modelData.key === "skipped" ? "#38230D" : "#1A2638")) : (tabMouse.containsMouse ? "#1E2430" : "#141720")
                        border.color: isSelected ? (modelData.key === "failed" ? "#EF4444" : (modelData.key === "skipped" ? "#F59E0B" : modelData.color)) : (modelData.key === "failed" && modelData.count > 0 ? "#7F1D1D" : (modelData.key === "skipped" && modelData.count > 0 ? "#B45309" : "#242A38"))
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
                                color: modelData.key === "failed" && modelData.count > 0 ? "#EF4444" : (modelData.key === "skipped" && modelData.count > 0 ? "#D97706" : (isSelected ? "#2E3B50" : "#1E2330"))

                                Behavior on color { ColorAnimation { duration: 150 } }

                                Text {
                                    id: cntText
                                    anchors.centerIn: parent
                                    text: modelData.count.toString()
                                    font.pixelSize: 9
                                    font.bold: true
                                    color: (modelData.key === "failed" || modelData.key === "skipped") && modelData.count > 0 ? "#FFFFFF" : (isSelected ? modelData.color : "#64748B")
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
                QueueGroupsList {
                    view: root
                }

                // Individual Files ListView
                QueueTaskList {
                    view: root
                }
        }
    }
}
}

