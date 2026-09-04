import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Rectangle {
    id: root

    property var bridge: null
    color: "#0F1117"

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

        // 1. Header toolbar
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "📋 Task Queue"
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

            // Prominent "Retry Failed" Action Button with Real-time Count Badge
            RowLayout {
                spacing: 6

                StyledButton {
                    id: retryFailedBtn
                    text: "Retry Failed"
                    iconText: "🔁"
                    variant: (root.bridge && root.bridge.queueModel && root.bridge.queueModel.failedCount > 0) ? "danger" : "ghost"
                    implicitHeight: 28
                    tooltip: "Open selective retry dialog to inspect and re-download failed files"
                    opacity: (root.bridge && root.bridge.queueModel && root.bridge.queueModel.failedCount > 0) ? 1.0 : 0.45
                    Behavior on opacity { NumberAnimation { duration: 180 } }
                    onClicked: {
                        retryModal.isOpen = true
                    }
                }
            }

            StyledButton {
                text: "Download Links"
                iconText: "☁️"
                variant: (root.bridge && root.bridge.hasHarvestedLinks) ? "primary" : "outline"
                implicitHeight: 28
                tooltip: "Open dialog to download harvested links via Mega.nz, Google Drive, Dropbox, or GoFile"
                opacity: (root.bridge && root.bridge.hasHarvestedLinks) ? 1.0 : 0.6
                onClicked: cloudModal.isOpen = true
            }

            StyledButton {
                text: "Export Links"
                iconText: "🔗"
                variant: "outline"
                implicitHeight: 28
                tooltip: "Export harvested external cloud links to text file"
                onClicked: if (root.bridge) root.bridge.exportAllLinks()
            }

            StyledButton {
                text: "Clear Queue"
                iconText: "🗑"
                variant: "ghost"
                implicitHeight: 28
                tooltip: "Remove all tasks from queue"
                onClicked: if (root.bridge && root.bridge.queueModel) root.bridge.queueModel.clear()
            }
        }

        // 2. Status Filter Tabs (All / Active / Completed / Failed)
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            // Filter Tab Component
            Repeater {
                model: [
                    { key: "all", label: "All", icon: "📁", count: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.totalCount : 0, color: "#38BDF8", tip: "Show all download tasks in queue" },
                    { key: "downloading", label: "Active", icon: "⚡", count: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.downloadingCount : 0, color: "#0EA5E9", tip: "Show active/in-progress downloads" },
                    { key: "completed", label: "Completed", icon: "✔", count: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.completedCount : 0, color: "#10B981", tip: "Show successfully completed downloads" },
                    { key: "failed", label: "Errors / Failed", icon: "✖", count: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.failedCount : 0, color: "#EF4444", tip: "Show failed download tasks" }
                ]

                delegate: Rectangle {
                    id: tabRect
                    height: 26
                    width: Math.max(75, tabRow.implicitWidth + 16)
                    radius: 5

                    property bool isSelected: root.bridge && root.bridge.queueModel ? root.bridge.queueModel.filterStatus === modelData.key : false

                    color: isSelected ? (modelData.key === "failed" ? "#3B181E" : "#1A2638") : (tabMouse.containsMouse ? "#1E2430" : "#141720")
                    border.color: isSelected ? (modelData.key === "failed" ? "#EF4444" : modelData.color) : (modelData.key === "failed" && modelData.count > 0 ? "#7F1D1D" : "#242A38")
                    border.width: isSelected ? 1.5 : 1

                    scale: tabMouse.pressed ? 0.93 : (tabMouse.containsMouse ? 1.04 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
                    }
                    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                    Behavior on border.color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }

                    Row {
                        id: tabRow
                        anchors.centerIn: parent
                        spacing: 5

                        Text {
                            text: modelData.icon
                            font.pixelSize: 10
                            color: isSelected ? modelData.color : "#94A3B8"
                        }

                        Text {
                            text: modelData.label
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: isSelected ? Font.DemiBold : Font.Normal
                            color: isSelected ? "#F8FAFC" : "#94A3B8"
                        }

                        // Count pill
                        Rectangle {
                            height: 16
                            width: Math.max(16, cntText.implicitWidth + 6)
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
                        ToolTip.delay: 400
                        ToolTip.text: modelData.tip
                        onClicked: {
                            if (root.bridge && root.bridge.queueModel) {
                                root.bridge.queueModel.filterStatus = modelData.key
                            }
                        }
                    }
                }
            }

            Item { Layout.fillWidth: true }
        }

        // 3. Tasks ListView
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#141720"
            border.color: "#242A38"
            border.width: 1
            radius: 8
            clip: true

            ListView {
                id: queueList
                anchors.fill: parent
                anchors.margins: 6
                spacing: 6
                model: root.bridge ? root.bridge.queueModel : null

                ScrollBar.vertical: ScrollBar { active: true; policy: ScrollBar.AsNeeded }

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
                                font.weight: Font.DemiBold
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
                                    text: (model.retryCount > 0 ? ("[" + (model.retryCount === 1 ? "1 retry" : model.retryCount + " retries") + " failed] ") : "") + model.errorMsg
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    color: "#FCA5A5"
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                }

                                StyledButton {
                                    text: "Retry"
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
                        if (status === "failed") return "🎉 No failed downloads!\nAll tasks completed without errors."
                        if (status === "downloading") return "⚡ No active downloads running.\nStart a download to see active files."
                        if (status === "completed") return "📁 No completed downloads yet."
                        return "No download tasks in queue.\nEnter a URL and click 'Start Download' or 'Add to Queue'."
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
}
