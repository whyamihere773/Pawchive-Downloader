import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// Grouped creator/post batches SmoothListView for QueueView.
SmoothListView {
    id: groupsList

    required property var view
    Layout.fillWidth: true
    Layout.fillHeight: true
    spacing: 8
    clip: true
    visible: view.bridge && view.bridge.queueModel && view.bridge.queueModel.viewMode === "grouped" && view.bridge.queueModel.selectedBatchId === ""
    model: view.bridge && view.bridge.queueModel ? view.bridge.queueModel.groupsModel : null

    delegate: Rectangle {
        id: groupCard
        readonly property var modelData: model
        readonly property int cardDownloading: (typeof downloadingFiles !== "undefined" ? downloadingFiles : (model && model.downloadingFiles !== undefined ? model.downloadingFiles : 0))
        readonly property int cardPending: (typeof pendingFiles !== "undefined" ? pendingFiles : (model && model.pendingFiles !== undefined ? model.pendingFiles : 0))
        readonly property int cardFailed: (typeof failedFiles !== "undefined" ? failedFiles : (model && model.failedFiles !== undefined ? model.failedFiles : 0))
        readonly property int cardUnimported: (typeof unimportedFiles !== "undefined" ? unimportedFiles : (model && model.unimportedFiles !== undefined ? model.unimportedFiles : 0))
        readonly property int cardRetryableFailed: (typeof retryableFailedFiles !== "undefined" ? retryableFailedFiles : (model && model.retryableFailedFiles !== undefined ? model.retryableFailedFiles : Math.max(0, cardFailed - cardUnimported)))
        readonly property bool cardOnlyUnimportedFailed: cardFailed > 0 && cardRetryableFailed === 0 && cardUnimported > 0
        readonly property string cardStatus: (typeof status !== "undefined" ? status : (model && model.status !== undefined ? model.status : "pending"))
        readonly property string cardBatchId: (typeof batchId !== "undefined" ? batchId : (model && model.batchId !== undefined ? model.batchId : ""))
        readonly property bool cardIsActiveDownloading: groupCard.cardDownloading > 0 || groupCard.cardStatus === "downloading"
        readonly property bool cardIsBatchPaused: groupCard.cardStatus === "paused" || (typeof isPaused !== "undefined" ? isPaused : (model && model.isPaused !== undefined ? model.isPaused : false)) || (view.bridge && view.bridge.queueModel && view.bridge.queueModel.isBatchPaused(groupCard.cardBatchId))
        readonly property bool cardIsEffectivelyPaused: cardIsBatchPaused || (view.bridge && view.bridge.isPaused && (cardIsActiveDownloading || (cardPending > 0 && view.bridge.isDownloading)))
        width: groupsList.width - 12
        height: cardInnerCol.implicitHeight + 20
        implicitHeight: height
        radius: 8
        color: groupCard.cardStatus === "failed" ? "#22161A" : (groupCard.cardStatus === "downloading" ? "#131E30" : (groupCard.cardStatus === "skipped" ? "#1C150E" : (cardMouse.containsMouse ? "#1D2332" : "#171B26")))
        border.color: groupCard.cardIsEffectivelyPaused ? "#F59E0B" : (groupCard.cardStatus === "downloading" ? "#0EA5E9" : (groupCard.cardStatus === "failed" ? "#EF4444" : (groupCard.cardStatus === "skipped" ? "#B45309" : (cardMouse.containsMouse ? "#3B465E" : "#283042"))))
        border.width: 1.5

        Behavior on color { ColorAnimation { duration: 150 } }
        Behavior on border.color { ColorAnimation { duration: 150 } }

        MouseArea {
            id: cardMouse
            anchors.fill: parent
            hoverEnabled: true
            preventStealing: false
            z: -1
        }

        ColumnLayout {
            id: cardInnerCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 10
            spacing: 8

            // Top line: Service badge, Creator, Post title, Status pill
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Rectangle {
                    implicitHeight: 20
                    implicitWidth: svcText.implicitWidth + 10
                    Layout.preferredHeight: 20
                    Layout.preferredWidth: svcText.implicitWidth + 10
                    Layout.alignment: Qt.AlignVCenter
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
                    Layout.alignment: Qt.AlignVCenter
                }

                Text {
                    text: "•"
                    color: "#64748B"
                    font.pixelSize: 11
                    Layout.alignment: Qt.AlignVCenter
                }

                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 40
                    Layout.alignment: Qt.AlignVCenter
                    text: modelData.postTitle
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#94A3B8"
                    elide: Text.ElideRight
                }

                // Status Badge
                Rectangle {
                    implicitHeight: 20
                    implicitWidth: stText.implicitWidth + 14
                    Layout.preferredHeight: 20
                    Layout.preferredWidth: implicitWidth
                    Layout.minimumWidth: implicitWidth
                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                    radius: 4
                    color: groupCard.cardIsEffectivelyPaused ? "#451A03" : (groupCard.cardOnlyUnimportedFailed && modelData.status === "failed" ? "#451A03" : (modelData.status === "completed" ? "#064E3B" : (modelData.status === "downloading" ? "#0C4A6E" : (modelData.status === "skipped" ? "#451A03" : (modelData.status === "failed" ? "#7F1D1D" : "#1E293B")))))
                    border.color: groupCard.cardIsEffectivelyPaused ? "#F59E0B" : (groupCard.cardOnlyUnimportedFailed && modelData.status === "failed" ? "#F59E0B" : (modelData.status === "completed" ? "#10B981" : (modelData.status === "downloading" ? "#0EA5E9" : (modelData.status === "skipped" ? "#F59E0B" : (modelData.status === "failed" ? "#EF4444" : "#475569")))))
                    border.width: 1

                    Text {
                        id: stText
                        anchors.centerIn: parent
                        text: groupCard.cardIsEffectivelyPaused ? "PAUSED" : (groupCard.cardOnlyUnimportedFailed && modelData.status === "failed" ? "NOT IMPORTED" : (modelData.status ? modelData.status.toUpperCase() : ""))
                        font.pixelSize: 9
                        font.bold: true
                        color: groupCard.cardIsEffectivelyPaused ? "#FDE68A" : (groupCard.cardOnlyUnimportedFailed && modelData.status === "failed" ? "#FDE68A" : (modelData.status === "completed" ? "#6EE7B7" : (modelData.status === "downloading" ? "#7DD3FC" : (modelData.status === "skipped" ? "#FDE68A" : (modelData.status === "failed" ? "#FCA5A5" : "#94A3B8")))))
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
                        Layout.minimumWidth: 36
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
                            color: modelData.status === "completed" ? "#10B981" : (modelData.status === "skipped" ? "#F59E0B" : (modelData.status === "failed" ? "#EF4444" : "#10B981"))
                            Behavior on width { NumberAnimation { duration: 200 } }
                        }
                    }

                    Text {
                        text: (modelData.skippedFiles > 0 ? (modelData.completedFiles + " (+" + modelData.skippedFiles + " skipped)/" + modelData.totalFiles) : (modelData.completedFiles + "/" + modelData.totalFiles))
                        font.family: "Cascadia Code, Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        Layout.preferredWidth: implicitWidth
                        Layout.minimumWidth: implicitWidth
                        Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
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
                        Layout.minimumWidth: 36
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
                        Layout.preferredWidth: Math.max(42, implicitWidth)
                        Layout.minimumWidth: Math.max(42, implicitWidth)
                        Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
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
                visible: view.isNarrow

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: modelData.completedFiles + " / " + modelData.totalFiles + " files"
                              + (groupCard.cardRetryableFailed > 0 ? (" (" + groupCard.cardRetryableFailed + " failed)") : "")
                              + (groupCard.cardUnimported > 0 ? (" (" + groupCard.cardUnimported + " not imported)") : "")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: groupCard.cardRetryableFailed > 0 ? "#F87171" : (groupCard.cardUnimported > 0 ? "#FBBF24" : "#94A3B8")
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
                        text: view.isVeryNarrow ? "" : view.tr("btn_view_files", "View Files")
                        iconText: "🔍"
                        variant: "outline"
                        implicitHeight: 24
                        tooltip: view.tr("btn_view_files", "View Files")
                        onClicked: {
                            if (view.bridge && view.bridge.queueModel) {
                                view.bridge.queueModel.selectedBatchId = groupCard.cardBatchId
                            }
                        }
                    }

                    StyledButton {
                        visible: groupCard.cardRetryableFailed > 0
                        text: view.isVeryNarrow ? "" : view.tr("btn_retry_batch", "Retry Failed")
                        iconText: "🔁"
                        variant: "danger"
                        implicitHeight: 24
                        tooltip: view.tr("btn_retry_batch", "Retry Failed")
                        onClicked: {
                            if (view.bridge && view.bridge.queueModel) {
                                view.bridge.queueModel.retryBatch(groupCard.cardBatchId)
                            }
                        }
                    }

                    StyledButton {
                        visible: groupCard.cardOnlyUnimportedFailed
                        text: view.isVeryNarrow ? "" : view.tr("badge_not_imported", "Not Imported")
                        iconText: "⚠️"
                        variant: "outline"
                        implicitHeight: 24
                        tooltip: view.tr("tip_unimported_inspect", "Files aren't imported on Pawchive yet (retry disabled) — click to inspect details")
                        onClicked: {
                            if (typeof appWindow !== "undefined" && typeof appWindow.openRetryModal === "function") {
                                appWindow.openRetryModal()
                            }
                        }
                    }

                    StyledButton {
                        visible: groupCard.cardIsActiveDownloading || groupCard.cardPending > 0 || groupCard.cardIsBatchPaused
                        text: view.isVeryNarrow ? "" : (groupCard.cardIsBatchPaused ? view.tr("action_resume", "Resume") : view.tr("action_pause", "Pause"))
                        iconText: groupCard.cardIsBatchPaused ? "▶" : "⏸"
                        variant: "ghost"
                        implicitHeight: 24
                        tooltip: groupCard.cardIsBatchPaused ? view.tr("tip_resume_download", "Resume paused download") : view.tr("tip_pause_download", "Pause download")
                        onClicked: {
                            if (view.bridge && view.bridge.queueModel) {
                                view.bridge.queueModel.toggleBatchPause(groupCard.cardBatchId)
                            }
                        }
                    }

                    StyledButton {
                        visible: groupCard.cardDownloading > 0 || groupCard.cardPending > 0 || groupCard.cardIsBatchPaused
                        text: view.isVeryNarrow ? "" : view.tr("btn_cancel_batch", "Cancel")
                        iconText: "✕"
                        variant: "ghost"
                        implicitHeight: 24
                        tooltip: view.tr("btn_cancel_batch", "Cancel")
                        onClicked: {
                            if (view.bridge && view.bridge.queueModel) {
                                view.bridge.queueModel.cancelBatch(groupCard.cardBatchId)
                            }
                        }
                    }

                    StyledButton {
                        text: view.isVeryNarrow ? "" : view.tr("btn_remove_batch", "Remove")
                        iconText: "🗑"
                        variant: "ghost"
                        implicitHeight: 24
                        tooltip: view.tr("btn_remove_batch", "Remove")
                        onClicked: {
                            if (view.bridge && view.bridge.queueModel) {
                                view.bridge.queueModel.removeBatch(groupCard.cardBatchId)
                            }
                        }
                    }
                }
            }

            // Wide mode single-row layout
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: !view.isNarrow

                Text {
                    text: modelData.completedFiles + " / " + modelData.totalFiles + " files"
                          + (groupCard.cardRetryableFailed > 0 ? (" (" + groupCard.cardRetryableFailed + " failed)") : "")
                          + (groupCard.cardUnimported > 0 ? (" (" + groupCard.cardUnimported + " not imported)") : "")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: groupCard.cardRetryableFailed > 0 ? "#F87171" : (groupCard.cardUnimported > 0 ? "#FBBF24" : "#94A3B8")
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
                    text: view.tr("btn_view_files", "View Files")
                    iconText: "🔍"
                    variant: "outline"
                    implicitHeight: 24
                    tooltip: view.tr("btn_view_files", "View Files")
                    onClicked: {
                        if (view.bridge && view.bridge.queueModel) {
                            view.bridge.queueModel.selectedBatchId = groupCard.cardBatchId
                        }
                    }
                }

                StyledButton {
                    visible: groupCard.cardRetryableFailed > 0
                    text: view.tr("btn_retry_batch", "Retry Failed")
                    iconText: "🔁"
                    variant: "danger"
                    implicitHeight: 24
                    tooltip: view.tr("btn_retry_batch", "Retry Failed")
                    onClicked: {
                        if (view.bridge && view.bridge.queueModel) {
                            view.bridge.queueModel.retryBatch(groupCard.cardBatchId)
                        }
                    }
                }

                StyledButton {
                    visible: groupCard.cardOnlyUnimportedFailed
                    text: view.tr("badge_not_imported", "Not Imported")
                    iconText: "⚠️"
                    variant: "outline"
                    implicitHeight: 24
                    tooltip: view.tr("tip_unimported_inspect", "Files aren't imported on Pawchive yet (retry disabled) — click to inspect details")
                    onClicked: {
                        if (typeof appWindow !== "undefined" && typeof appWindow.openRetryModal === "function") {
                            appWindow.openRetryModal()
                        }
                    }
                }

                StyledButton {
                    visible: groupCard.cardIsActiveDownloading || groupCard.cardPending > 0 || groupCard.cardIsBatchPaused
                    text: groupCard.cardIsBatchPaused ? view.tr("action_resume", "Resume") : view.tr("action_pause", "Pause")
                    iconText: groupCard.cardIsBatchPaused ? "▶" : "⏸"
                    variant: "ghost"
                    implicitHeight: 24
                    tooltip: groupCard.cardIsBatchPaused ? view.tr("tip_resume_download", "Resume paused download") : view.tr("tip_pause_download", "Pause download")
                    onClicked: {
                        if (view.bridge && view.bridge.queueModel) {
                            view.bridge.queueModel.toggleBatchPause(groupCard.cardBatchId)
                        }
                    }
                }

                StyledButton {
                    visible: groupCard.cardDownloading > 0 || groupCard.cardPending > 0 || groupCard.cardIsBatchPaused
                    text: view.tr("btn_cancel_batch", "Cancel")
                    iconText: "✕"
                    variant: "ghost"
                    implicitHeight: 24
                    tooltip: view.tr("btn_cancel_batch", "Cancel")
                    onClicked: {
                        if (view.bridge && view.bridge.queueModel) {
                            view.bridge.queueModel.cancelBatch(groupCard.cardBatchId)
                        }
                    }
                }

                StyledButton {
                    text: view.tr("btn_remove_batch", "Remove")
                    iconText: "🗑"
                    variant: "ghost"
                    implicitHeight: 24
                    tooltip: view.tr("btn_remove_batch", "Remove")
                    onClicked: {
                        if (view.bridge && view.bridge.queueModel) {
                            view.bridge.queueModel.removeBatch(groupCard.cardBatchId)
                        }
                    }
                }
            }
        }
    }

    // Empty state for groups
    Text {
        anchors.centerIn: parent
        text: view.tr("empty_no_batches", "No creator or post batches in queue.\nEnter a creator or post link and click 'Add to Queue'.")
        color: "#475569"
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 13
        horizontalAlignment: Text.AlignHCenter
        visible: groupsList.count === 0
    }
}

