import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// Individual file tasks SmoothListView for QueueView.
SmoothListView {
    id: queueList

    required property var view
    Layout.fillWidth: true
    Layout.fillHeight: true
    spacing: 6
    clip: true
    visible: view.bridge && view.bridge.queueModel && (view.bridge.queueModel.viewMode === "flat" || view.bridge.queueModel.selectedBatchId !== "")
    model: view.bridge ? view.bridge.queueModel : null

delegate: Rectangle {
    id: delegateRoot
    readonly property bool rowIsUnimported: !!model.isUnimported
    width: queueList.width - 12
    height: taskCol.implicitHeight + 16
    implicitHeight: height
    radius: 6
    color: rowIsUnimported ? "#1F1910" : (model.status === "failed" ? "#1F161A" : (model.status === "downloading" ? "#131E2E" : (model.status === "skipped" ? "#1C150E" : (delegateHover.containsMouse ? "#1D222F" : "#1A1E29"))))
    border.color: rowIsUnimported ? "#D97706" : (model.status === "downloading" ? "#38BDF8" : (model.status === "failed" ? "#EF4444" : (model.status === "skipped" ? (delegateHover.containsMouse ? "#F59E0B" : "#B45309") : (delegateHover.containsMouse ? "#3E485D" : "#282E3D"))))
    border.width: (model.status === "failed" || model.status === "skipped") ? 1.5 : 1

    Behavior on color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }
    Behavior on border.color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }

    MouseArea {
        id: delegateHover
        anchors.fill: parent
        hoverEnabled: true
        preventStealing: false
        z: -1
    }

    ColumnLayout {
        id: taskCol
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
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
                    if (delegateRoot.rowIsUnimported) return "#B45309"
                    if (model.status === "completed") return "#10B981"
                    if (model.status === "downloading") return "#0284C7"
                    if (model.status === "skipped") return "#D97706"
                    if (model.status === "failed") return "#EF4444"
                    return "#333A48"
                }

                Behavior on color { ColorAnimation { duration: 200 } }

                Text {
                    id: statusText
                    anchors.centerIn: parent
                    text: delegateRoot.rowIsUnimported ? "NOT IMPORTED" : model.status.toUpperCase()
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
                color: delegateRoot.rowIsUnimported ? "#FDE68A" : (model.status === "failed" ? "#FCA5A5" : (model.status === "skipped" ? "#FDE68A" : "#F1F5F9"))
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
                        if (delegateRoot.rowIsUnimported) return "#3B2608"
                        if (model.status === "completed") return "#064E3B"
                        if (model.status === "downloading") return "#0C4A6E"
                        if (model.status === "skipped") return "#451A03"
                        if (model.status === "failed") return "#450A0A"
                        return "#1E293B"
                    }
                    border.color: {
                        if (delegateRoot.rowIsUnimported) return "#F59E0B"
                        if (model.status === "completed") return "#10B981"
                        if (model.status === "downloading") return "#38BDF8"
                        if (model.status === "skipped") return "#F59E0B"
                        if (model.status === "failed") return "#EF4444"
                        return "#334155"
                    }
                    border.width: 1
                    anchors.verticalCenter: parent.verticalCenter

                    Text {
                        id: pctText
                        anchors.centerIn: parent
                        text: {
                            if (delegateRoot.rowIsUnimported) return "No Retry"
                            if (model.status === "completed") return "100%"
                            if (model.status === "skipped") return "Skipped"
                            if (model.status === "failed") return (model.retryCount > 0 ? ("Failed (" + model.retryCount + "x)") : "Failed")
                            if (model.status === "downloading") return model.percentage + "%"
                            return "0%"
                        }
                        font.family: "Cascadia Code, Consolas, monospace"
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        color: {
                            if (delegateRoot.rowIsUnimported) return "#FCD34D"
                            if (model.status === "completed") return "#34D399"
                            if (model.status === "downloading") return "#38BDF8"
                            if (model.status === "skipped") return "#FBBF24"
                            if (model.status === "failed") return "#FCA5A5"
                            return "#94A3B8"
                        }
                    }
                }

                // Single Item Retry Button (Visible only for retryable failed items)
                Rectangle {
                    width: 22
                    height: 20
                    radius: 4
                    color: itemRetryMouse.containsMouse ? "#EF4444" : "#2E1A20"
                    border.color: "#EF4444"
                    border.width: 1
                    visible: model.status === "failed" && !delegateRoot.rowIsUnimported
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
                            if (view.bridge && view.bridge.queueModel) {
                                view.bridge.queueModel.retryTaskAt(index)
                            }
                        }
                    }
                }

                // Show the downloaded file in the Gallery (finished items)
                Rectangle {
                    width: 22
                    height: 20
                    radius: 4
                    color: itemGalleryMouse.containsMouse ? "#1E293B" : "#141A28"
                    border.color: itemGalleryMouse.containsMouse ? "#38BDF8" : "#2E3A56"
                    border.width: 1
                    visible: model.status === "completed" && !!model.targetPath
                    anchors.verticalCenter: parent.verticalCenter
                    Text { anchors.centerIn: parent; text: "🖼"; font.pixelSize: 10 }
                    MouseArea {
                        id: itemGalleryMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: view.tr("queue_show_gallery_tip", "Show this file in the Gallery")
                        onClicked: if (view.bridge) view.bridge.showInGallery(model.targetPath)
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
                width: Math.max(0, Math.min(parent.width, parent.width * (model.status === "skipped" ? 1.0 : model.progress)))
                color: model.status === "completed" ? "#10B981" : (model.status === "skipped" ? "#F59E0B" : "#38BDF8")

                Behavior on width {
                    NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
                }
                Behavior on color {
                    ColorAnimation { duration: 200 }
                }
            }
        }

        // Detailed Filter / Skip Reason Box (Visible when skipped)
        Rectangle {
            Layout.fillWidth: true
            height: skippedRow.implicitHeight + 8
            radius: 4
            color: "#28180E"
            border.color: "#92400E"
            border.width: 1
            visible: model.status === "skipped" && model.errorMsg.length > 0

            RowLayout {
                id: skippedRow
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                Text {
                    text: "⏭️"
                    font.pixelSize: 11
                }

                Text {
                    text: model.errorMsg
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#FDE68A"
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }
            }
        }

        // Detailed Error Box with Retry Action (Visible when failed)
        Rectangle {
            Layout.fillWidth: true
            height: errorRow.implicitHeight + 8
            radius: 4
            color: delegateRoot.rowIsUnimported ? "#2A1F0E" : "#2C1217"
            border.color: delegateRoot.rowIsUnimported ? "#92400E" : "#5C1D24"
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
                    text: (!delegateRoot.rowIsUnimported && model.retryCount > 0 ? ("[" + model.retryCount + " " + (model.retryCount === 1 ? view.tr("label_failed_retry", "retry failed") : view.tr("label_failed_retries", "retries failed")) + "] ") : "") + model.errorMsg
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: delegateRoot.rowIsUnimported ? "#FDE68A" : "#FCA5A5"
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }

                StyledButton {
                    visible: !delegateRoot.rowIsUnimported
                    text: view.tr("btn_retry", "Retry")
                    iconText: "↻"
                    variant: "danger"
                    implicitHeight: 20
                    onClicked: {
                        if (view.bridge && view.bridge.queueModel) {
                            view.bridge.queueModel.retryTaskAt(index)
                        }
                    }
                }

                Rectangle {
                    visible: delegateRoot.rowIsUnimported
                    implicitHeight: 20
                    implicitWidth: noRetryPillTxt.implicitWidth + 12
                    Layout.preferredHeight: implicitHeight
                    Layout.preferredWidth: implicitWidth
                    radius: 4
                    color: "#3B2608"
                    border.color: "#B45309"
                    border.width: 1

                    Text {
                        id: noRetryPillTxt
                        anchors.centerIn: parent
                        text: view.tr("btn_retry_disabled_short", "Retry Disabled")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.bold: true
                        color: "#FCD34D"
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: view.tr("tip_unimported_no_retry", "This file isn't physically hosted on Pawchive's servers yet, so retrying won't download it.")
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
        var status = view.bridge && view.bridge.queueModel ? view.bridge.queueModel.filterStatus : "all"
        if (status === "failed") return view.tr("empty_no_failed", "🎉 No failed downloads!\nAll tasks completed without errors.")
        if (status === "downloading") return view.tr("empty_no_active", "⚡ No active downloads running.\nStart a download to see active files.")
        if (status === "completed") return view.tr("empty_no_completed", "📁 No completed downloads yet.")
        if (status === "skipped") return view.tr("empty_no_skipped", "⏭️ No skipped files in queue.")
        return view.tr("empty_no_tasks", "No download tasks in queue.\nEnter a URL and click 'Start Download' or 'Add to Queue'.")
    }
    color: "#475569"
    font.family: "Segoe UI, sans-serif"
    font.pixelSize: 13
    horizontalAlignment: Text.AlignHCenter
    visible: queueList.count === 0

}
            }
