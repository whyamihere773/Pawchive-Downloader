import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Footer Row ───────────────────────────────────────────────
RowLayout {
    id: footerRoot
    required property var modal
    required property var filesModel
    Layout.fillWidth: true
    spacing: 10

    // Comprehensive Selection Counter Pill (Files + Posts)
    Rectangle {
        height: 30
        implicitWidth: selCounterRow.implicitWidth + 20
        radius: 6
        color: "#161D2B"
        border.color: "#2D3748"

        Row {
            id: selCounterRow
            anchors.centerIn: parent
            spacing: 6

            Text {
                text: footerRoot.modal.tr("label_selected_counter", "Selected:")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#94A3B8"
                anchors.verticalCenter: parent.verticalCenter
            }

            // Files Count
            Text {
                text: footerRoot.modal.totalSelectedFiles + " / " + footerRoot.modal.totalFilesCount + " files"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: Font.Bold
                color: footerRoot.modal.totalSelectedFiles > 0 ? "#38BDF8" : "#EF4444"
                anchors.verticalCenter: parent.verticalCenter
            }

            // Divider
            Text {
                text: "•"
                font.pixelSize: 10
                color: "#475569"
                anchors.verticalCenter: parent.verticalCenter
            }

            // Posts Count
            Text {
                text: footerRoot.modal.selectedCount + " / " + footerRoot.modal.allPosts.length + " posts"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#CBD5E1"
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    Text {
        visible: !footerRoot.modal.isInspecting || footerRoot.filesModel.count > 1
        text: footerRoot.modal.isInspecting
            ? "Tip: Shift+click for range • Ctrl+click to preview/play"
            : (footerRoot.modal.quickSelectClickMode
                ? "Tip: Click to select • Ctrl+click to preview/play • Shift+click for range"
                : "Tip: Click to preview/play • Ctrl+click to select • Shift+click for range")
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 10
        color: "#64748B"
    }

    Item { Layout.fillWidth: true }

    // Cancel / Close Button
    Rectangle {
        height: 34
        implicitWidth: cancelText.implicitWidth + 20
        radius: 7
        color: cancelMouse.containsMouse ? "#1E293B" : "transparent"
        border.color: cancelMouse.containsMouse ? "#334155" : "transparent"
        scale: cancelMouse.pressed ? 0.94 : 1.0
        Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

        Text {
            id: cancelText
            anchors.centerIn: parent
            text: footerRoot.modal.tr("btn_cancel", "Cancel")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 12
            color: "#94A3B8"
        }

        MouseArea {
            id: cancelMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: footerRoot.modal.closeModal()
        }
    }

    // Add to Queue Selected Button
    Rectangle {
        height: 34
        implicitWidth: queueSelRow.implicitWidth + 24
        radius: 7
        color: queueSelMouse.containsMouse ? "#1E293B" : "#141A26"
        border.color: "#2D3748"
        border.width: 1
        scale: queueSelMouse.pressed ? 0.94 : (queueSelMouse.containsMouse ? 1.02 : 1.0)
        Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

        Row {
            id: queueSelRow
            anchors.centerIn: parent
            spacing: 6
            Text { text: "➕"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
            Text {
                text: footerRoot.modal.tr("btn_queue_selected", "Queue Selected") + " (" + footerRoot.modal.totalSelectedFiles + " files)"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: "#E2E8F0"
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        MouseArea {
            id: queueSelMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: footerRoot.modal.totalSelectedFiles > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
            enabled: footerRoot.modal.totalSelectedFiles > 0
            opacity: footerRoot.modal.totalSelectedFiles > 0 ? 1.0 : 0.5
            onClicked: {
                var ids = footerRoot.modal.getSelectedPostIds()
                var filesMap = footerRoot.modal.getSelectedFilesMap()
                if (footerRoot.modal.bridge) {
                    footerRoot.modal.bridge.startDownloadSelectedPosts(ids, false, filesMap)
                }
                footerRoot.modal.closeModal()
            }
        }
    }

    // Download Selected Button
    Rectangle {
        height: 34
        implicitWidth: dlSelRow.implicitWidth + 28
        radius: 7
        color: dlSelMouse.containsMouse ? "#0284C7" : "#0369A1"
        border.color: "#38BDF8"
        border.width: 1
        scale: dlSelMouse.pressed ? 0.94 : (dlSelMouse.containsMouse ? 1.03 : 1.0)
        Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.35; mass: 1.0 } }

        Row {
            id: dlSelRow
            anchors.centerIn: parent
            spacing: 6
            Text { text: "⚡"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
            Text {
                text: footerRoot.modal.tr("btn_download_selected", "Download Selected") + " (" + footerRoot.modal.totalSelectedFiles + " files)"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: Font.Bold
                color: "#FFFFFF"
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        MouseArea {
            id: dlSelMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: footerRoot.modal.totalSelectedFiles > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
            enabled: footerRoot.modal.totalSelectedFiles > 0
            opacity: footerRoot.modal.totalSelectedFiles > 0 ? 1.0 : 0.5
            onClicked: {
                var ids = footerRoot.modal.getSelectedPostIds()
                var filesMap = footerRoot.modal.getSelectedFilesMap()
                if (footerRoot.modal.bridge) {
                    footerRoot.modal.bridge.startDownloadSelectedPosts(ids, true, filesMap)
                }
                footerRoot.modal.closeModal()
            }
        }
    }
}
