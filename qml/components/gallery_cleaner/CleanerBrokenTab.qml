import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Tab 1: Broken & Zero-Byte Files scanner and cleanup list.
Item {
    id: brokenTab

    required property var modal
    visible: modal.activeTab === "broken"
    Layout.fillWidth: true
    Layout.fillHeight: true

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 6
            color: "#0A0D15"
            border.color: "#1E273A"
            border.width: 1
            clip: true

            // Empty State
            Text {
                anchors.centerIn: parent
                visible: modal.isScanning && modal.activeTab === "broken"
                text: "Scanning…"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: "#94A3B8"
            }
            Item {
                anchors.centerIn: parent
                visible: modal.brokenItems.length === 0 && !modal.isScanning
                ColumnLayout {
                    spacing: 6
                    anchors.centerIn: parent
                    Text { text: "✨"; font.pixelSize: 28; Layout.alignment: Qt.AlignHCenter }
                    Text {
                        text: "No broken or 0-byte files found in this folder!"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#10B981"
                        Layout.alignment: Qt.AlignHCenter
                    }
                }
            }

            ListView {
                id: brokenListView
                visible: modal.brokenItems.length > 0
                anchors.fill: parent
                anchors.margins: 4
                spacing: 2
                model: modal.brokenItems
                clip: true

                delegate: Rectangle {
                    width: brokenListView.width
                    height: 32
                    radius: 4
                    color: modal.selectedBrokenPaths[modelData.path] ? "#1F1A26" : (index % 2 === 0 ? "#111623" : "#0D111C")
                    border.color: modal.selectedBrokenPaths[modelData.path] ? "#EF4444" : "transparent"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 8

                        // Checkbox
                        Rectangle {
                            width: 16; height: 16; radius: 3
                            color: modal.selectedBrokenPaths[modelData.path] ? "#EF4444" : "#161D2B"
                            border.color: "#374151"; border.width: 1
                            Text { visible: Boolean(modal.selectedBrokenPaths && modal.selectedBrokenPaths[modelData.path]); anchors.centerIn: parent; text: "✓"; font.pixelSize: 10; font.weight: Font.Bold; color: "#FFFFFF" }
                        }

                        Text {
                            text: modelData.name
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#F8FAFC"
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            implicitHeight: 20
                            implicitWidth: bTypeTxt.implicitWidth + 10
                            radius: 4
                            color: "#3B1219"
                            border.color: "#EF4444"
                            border.width: 1
                            Text {
                                id: bTypeTxt
                                anchors.centerIn: parent
                                text: modelData.type_label || modelData.type
                                font.pixelSize: 9
                                font.weight: 600
                                color: "#FCA5A5"
                            }
                        }

                        Text {
                            text: modelData.size > 0 ? modal.formatBytes(modelData.size) : "0 B"
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 10
                            color: "#94A3B8"
                            Layout.preferredWidth: 60
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    Springy { hover: bItemMouse.containsMouse; pressed: bItemMouse.pressed }
                    MouseArea {
                        id: bItemMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modal.toggleBrokenSelection(modelData.path)
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 350
                        ToolTip.text: (modal.selectedBrokenPaths[modelData.path] ? "☑ Marked for deletion: " : "☐ Click to select: ") + modelData.path + "\nSize: " + (modelData.size > 0 ? modal.formatBytes(modelData.size) : "0 B")
                    }
                }
            }
        }

        // Broken items actions bar
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Rectangle {
                implicitHeight: 26; implicitWidth: 72; radius: 4
                color: "#182030"; border.color: "#28354E"; border.width: 1
                Text { anchors.centerIn: parent; text: "Select All"; font.pixelSize: 10; color: "#94A3B8" }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: modal.selectAllBroken(true)
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Select all detected broken and 0-byte files for cleanup"
                }
            }
            Rectangle {
                implicitHeight: 26; implicitWidth: 80; radius: 4
                color: "#182030"; border.color: "#28354E"; border.width: 1
                Text { anchors.centerIn: parent; text: "Deselect All"; font.pixelSize: 10; color: "#94A3B8" }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: modal.selectAllBroken(false)
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Uncheck all files in the broken files list"
                }
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                implicitHeight: 32
                implicitWidth: cleanBtnText.implicitWidth + 20
                radius: 6
                color: modal.selectedBrokenCount > 0 ? "#DC2626" : "#222634"
                border.color: modal.selectedBrokenCount > 0 ? "#EF4444" : "#323747"
                border.width: 1
                opacity: modal.selectedBrokenCount > 0 ? 1.0 : 0.5

                Text {
                    id: cleanBtnText
                    anchors.centerIn: parent
                    text: "Clean Selected (" + modal.selectedBrokenCount + ")"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 700
                    color: "#FFFFFF"
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: modal.selectedBrokenCount > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: modal.deleteBrokenItems()
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: modal.selectedBrokenCount > 0 ? ("Move " + modal.selectedBrokenCount + " selected broken file(s) to the Recycle Bin.") : "No broken files selected for deletion. Check files above to enable cleanup."
                }
            }
        }
    }
}

