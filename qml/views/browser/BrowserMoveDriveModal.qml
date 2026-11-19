import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Popup {
    id: moveCreatorDriveModal
    required property var view
    anchors.centerIn: Overlay.overlay
    width: 520
    height: 410
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Rectangle {
        radius: 12
        color: "#0F1420"
        border.color: "#10B981"
        border.width: 1.5
    }

    contentItem: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: "💽 Move Creator to Another Drive"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 15
                font.weight: Font.Bold
                color: "#F8FAFC"
            }
            Rectangle {
                width: 28; height: 28; radius: 6; color: "#1E293B"
                Text { anchors.centerIn: parent; text: "✕"; color: "#94A3B8" }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: moveCreatorDriveModal.close() }
            }
        }

        Text {
            Layout.fillWidth: true
            text: moveCreatorDriveModal.view.creatorToRelocate
                  ? ("Relocate '" + (moveCreatorDriveModal.view.creatorToRelocate.name || "") + "' (" + Number(moveCreatorDriveModal.view.creatorToRelocate.local_file_count || 0) + " files • " + moveCreatorDriveModal.view.formatBytes(moveCreatorDriveModal.view.creatorToRelocate.local_size_bytes) + ") to another drive. Archive records and Watchlist paths will update automatically.")
                  : ""
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
            wrapMode: Text.Wrap
        }

        SmoothListView {
            id: drivePickList
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8
            model: moveCreatorDriveModal.view.bBridge ? moveCreatorDriveModal.view.bBridge.relocateTargetDrives : []

            delegate: Rectangle {
                readonly property var dItem: modelData || ({})
                width: drivePickList.width - 10
                height: 64
                radius: 8
                color: dPickHover.hovered ? "#162235" : "#111827"
                border.color: dPickHover.hovered ? "#10B981" : "#1E293B"
                border.width: 1

                HoverHandler { id: dPickHover }
                Springy { hover: dPickHover.hovered; pressed: dPickMouse.pressed }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "💽 Drive " + (dItem.drive || "") + "  —  " + (dItem.root_path || "")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                            Layout.fillWidth: true
                            elide: Text.ElideMiddle
                        }
                        Text {
                            text: Number(dItem.free_gb || 0).toFixed(1) + " GB free / " + Number(dItem.total_gb || 0).toFixed(0) + " GB"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#34D399"
                        }
                    }

                    // Capacity bar
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 6
                        radius: 3
                        color: "#1E293B"
                        Rectangle {
                            height: parent.height
                            radius: 3
                            width: parent.width * Math.min(1.0, Number(dItem.percent_used || 0) / 100.0)
                            color: Number(dItem.percent_used || 0) > 90 ? "#EF4444" : "#38BDF8"
                        }
                    }
                }

                MouseArea {
                    id: dPickMouse
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (moveCreatorDriveModal.view.bBridge && moveCreatorDriveModal.view.creatorToRelocate && dItem.root_path) {
                            moveCreatorDriveModal.view.bBridge.moveCreatorToDrive(moveCreatorDriveModal.view.creatorToRelocate.key, dItem.root_path)
                            moveCreatorDriveModal.close()
                        }
                    }
                }
            }
        }

        // Custom Folder Picker on Any Drive
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            radius: 8
            color: customDestMouse.containsMouse ? "#1E293B" : "#151C2B"
            border.color: "#38BDF8"
            border.width: 1
            Springy { hover: customDestMouse.containsMouse; pressed: customDestMouse.pressed }

            Text {
                anchors.centerIn: parent
                text: "📂 Choose Custom Destination Folder on Any Disk…"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: Font.Bold
                color: "#38BDF8"
            }
            MouseArea {
                id: customDestMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: moveCreatorDriveModal.view.openCustomRelocateFolderDialog()
            }
        }
    }
}
