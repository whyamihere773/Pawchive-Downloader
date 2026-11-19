import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Tab 2: SHA-256 Duplicate File Finder and deletion strategies.
Item {
    id: duplicatesTab

    required property var modal
    visible: modal.activeTab === "duplicates"
    Layout.fillWidth: true
    Layout.fillHeight: true

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        // Wasted Storage Alert Banner
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 34
            radius: 6
            color: modal.totalWastedBytes > 0 ? "#2B1D0E" : "#131A28"
            border.color: modal.totalWastedBytes > 0 ? "#F59E0B" : "#243248"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Text { text: modal.isDupScanning ? "⏳" : (modal.totalWastedBytes > 0 ? "⚠️" : "✨"); font.pixelSize: 14 }
                Text {
                    text: modal.isDupScanning ? "Scanning for duplicates…" : (modal.totalWastedBytes > 0 ?
                          ("Found " + modal.duplicateGroups.length + " duplicate groups — Reclaim " + modal.formatBytes(modal.totalWastedBytes) + " of disk space") :
                          "No duplicate files detected in this folder!")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: modal.totalWastedBytes > 0 ? "#FCD34D" : "#38BDF8"
                    Layout.fillWidth: true
                }

                // Strategy buttons
                Rectangle {
                    visible: modal.duplicateGroups.length > 0
                    implicitHeight: 22; implicitWidth: 84; radius: 4
                    color: "#1E273A"; border.color: "#38BDF8"; border.width: 1
                    Text { anchors.centerIn: parent; text: "Keep Oldest"; font.pixelSize: 9; font.weight: 600; color: "#38BDF8" }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modal.selectDuplicatesStrategy("keep_oldest")
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Keep Oldest Copies\nAutomatically marks newer duplicates for deletion, keeping the earliest downloaded file in each set."
                    }
                }

                Rectangle {
                    visible: modal.duplicateGroups.length > 0
                    implicitHeight: 22; implicitWidth: 84; radius: 4
                    color: "#1E273A"; border.color: "#38BDF8"; border.width: 1
                    Text { anchors.centerIn: parent; text: "Keep Newest"; font.pixelSize: 9; font.weight: 600; color: "#38BDF8" }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modal.selectDuplicatesStrategy("keep_newest")
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Keep Newest Copies\nAutomatically marks older duplicates for deletion, keeping the most recently downloaded file in each set."
                    }
                }
            }
        }

        // Duplicates List
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 6
            color: "#0A0D15"
            border.color: "#1E273A"
            border.width: 1
            clip: true

            ListView {
                id: dupListView
                anchors.fill: parent
                anchors.margins: 4
                spacing: 6
                model: modal.duplicateGroups
                clip: true

                delegate: Rectangle {
                    width: dupListView.width
                    implicitHeight: dupCol.implicitHeight + 12
                    radius: 6
                    color: "#121724"
                    border.color: "#222D42"
                    border.width: 1

                    ColumnLayout {
                        id: dupCol
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 4

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: "Duplicate Set #" + (index + 1) + " (SHA: " + modelData.hash + ")"
                                font.family: "Segoe UI, monospace"
                                font.pixelSize: 10
                                font.weight: 700
                                color: "#F59E0B"
                            }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: modal.formatBytes(modelData.size) + " each • " + modelData.count + " copies"
                                font.family: "Segoe UI, monospace"
                                font.pixelSize: 10
                                color: "#94A3B8"
                            }
                        }

                        Repeater {
                            model: modelData.files
                            delegate: Rectangle {
                                Layout.fillWidth: true
                                height: 24
                                radius: 3
                                color: modal.selectedDupPaths[modelData.path] ? "#2A181C" : "#0A0E17"
                                border.color: modal.selectedDupPaths[modelData.path] ? "#EF4444" : "#1A2234"
                                border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 6
                                    anchors.rightMargin: 6
                                    spacing: 6

                                    Rectangle {
                                        width: 14; height: 14; radius: 3
                                        color: modal.selectedDupPaths[modelData.path] ? "#EF4444" : "#161D2B"
                                        border.color: "#374151"; border.width: 1
                                        Text { visible: Boolean(modal.selectedDupPaths && modal.selectedDupPaths[modelData.path]); anchors.centerIn: parent; text: "✓"; font.pixelSize: 9; font.weight: Font.Bold; color: "#FFFFFF" }
                                    }

                                    Text {
                                        text: modelData.rel_path || modelData.name
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: modal.selectedDupPaths[modelData.path] ? "#FCA5A5" : "#E2E8F0"
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                }

                                Springy { hover: dupFileMouse.containsMouse; pressed: dupFileMouse.pressed }
                                MouseArea {
                                    id: dupFileMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: modal.toggleDupSelection(modelData.path)
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 350
                                    ToolTip.text: (modal.selectedDupPaths[modelData.path] ? "🗑️ Marked for deletion:\n" : "💾 Keeping file:\n") + modelData.path + "\nClick to toggle keep/delete"
                                }
                            }
                        }
                    }
                }
            }
        }

        // Duplicates Action Bar
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: modal.selectedDupCount + " duplicate files selected for deletion"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#94A3B8"
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                implicitHeight: 32
                implicitWidth: delDupBtnText.implicitWidth + 20
                radius: 6
                color: modal.selectedDupCount > 0 ? "#DC2626" : "#222634"
                border.color: modal.selectedDupCount > 0 ? "#EF4444" : "#323747"
                border.width: 1
                opacity: modal.selectedDupCount > 0 ? 1.0 : 0.5

                Text {
                    id: delDupBtnText
                    anchors.centerIn: parent
                    text: "Delete Selected Duplicates (" + modal.selectedDupCount + ")"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 700
                    color: "#FFFFFF"
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: modal.selectedDupCount > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: modal.deleteDuplicateItems()
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: modal.selectedDupCount > 0 ? ("Move " + modal.selectedDupCount + " selected duplicate file(s) to the Recycle Bin. Empty the Recycle Bin to reclaim the disk space.") : "No duplicates selected for deletion. Choose a strategy or click items above."
                }
            }
        }
    }
}

