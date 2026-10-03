import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Import Confirmation Modal
// Prompts the user to choose between Merging into the current queue or Replacing it.
Item {
    id: root

    property var bridge: null
    property bool isOpen: false

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage      // re-translate when the language changes
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    anchors.fill: parent
    z: 9998
    visible: isOpen

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#B0060910"
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        MouseArea {
            anchors.fill: parent
        }
    }

    // Modal Card
    Rectangle {
        id: card
        width: Math.min(500, parent.width - 40)
        height: cardCol.implicitHeight + 48
        anchors.centerIn: parent
        radius: 16
        color: "#131722"
        border.color: "#2D3748"
        border.width: 1.5

        y: root.isOpen ? 0 : -28
        scale: root.isOpen ? 1.0 : 0.88
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on y {
            NumberAnimation { duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.25 }
        }
        Behavior on scale {
            NumberAnimation { duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.25 }
        }
        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        ColumnLayout {
            id: cardCol
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                topMargin: 24
                leftMargin: 24
                rightMargin: 24
            }
            spacing: 16

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    width: 42
                    height: 42
                    radius: 21
                    color: "#1E293B"
                    border.color: "#38BDF8"
                    border.width: 1.5

                    Text {
                        anchors.centerIn: parent
                        text: "📂"
                        font.pixelSize: 20
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3

                    Text {
                        text: root.tr("import_modal_title", "Import Queue State")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                    }

                    Text {
                        text: root.tr("import_modal_subtitle", "Select how you want to load the backup file into your queue.")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 12
                        color: "#94A3B8"
                    }
                }
            }

            // Explanatory Note
            Rectangle {
                Layout.fillWidth: true
                height: descText.implicitHeight + 16
                radius: 8
                color: "#1A202C"
                border.color: "#2D3748"
                border.width: 1

                Text {
                    id: descText
                    anchors {
                        left: parent.left
                        right: parent.right
                        top: parent.top
                        margins: 8
                    }
                    text: root.tr("import_disk_note", "✨ Smart Disk Check: Files already present in your download folder will be automatically verified and marked as completed.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                }
            }

            // Options Buttons
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                // Option 1: Merge
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 44
                    radius: 8
                    color: mergeMouse.containsMouse ? "#0284C7" : "#0EA5E9"

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 1
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: root.tr("btn_import_merge", "➕ Merge (Append)")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: root.tr("btn_import_merge_desc", "Keep current queue and add backup")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#E0F2FE"
                        }
                    }

                    MouseArea {
                        id: mergeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.isOpen = false
                            if (root.bridge) root.bridge.importQueueState("merge")
                        }
                    }
                }

                // Option 2: Replace
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 44
                    radius: 8
                    color: replaceMouse.containsMouse ? "#334155" : "#1E293B"
                    border.color: "#475569"
                    border.width: 1

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 1
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: root.tr("btn_import_replace", "🔄 Replace Current Queue")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: "#F1F5F9"
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: root.tr("btn_import_replace_desc", "Clear current queue and load backup")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#94A3B8"
                        }
                    }

                    MouseArea {
                        id: replaceMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.isOpen = false
                            if (root.bridge) root.bridge.importQueueState("replace")
                        }
                    }
                }
            }

            // Cancel Button
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                radius: 6
                color: "transparent"

                Text {
                    anchors.centerIn: parent
                    text: root.tr("btn_cancel", "Cancel")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: cancelMouse.containsMouse ? "#F8FAFC" : "#64748B"
                }

                MouseArea {
                    id: cancelMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.isOpen = false
                }
            }
        }
    }
}
