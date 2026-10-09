import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Watchlist → "Change download folder": the artist already has files in the current folder.
// Move them to the new folder (the archive follows), or use the new folder only for new downloads.
Item {
    id: root

    property var bridge: null
    property bool isOpen: false
    property string userId: ""
    property string service: ""
    property string creatorName: ""
    property string oldDirs: ""
    property string newDir: ""
    property int fileCount: 0
    property string sizeText: ""

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage      // re-translate when the language changes
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    function open(uid, svc, name, olds, target, count, size) {
        userId = uid
        service = svc
        creatorName = name
        oldDirs = olds
        newDir = target
        fileCount = count
        sizeText = size
        isOpen = true
    }

    function choose(move) {
        isOpen = false
        if (bridge) bridge.applyWatchlistFolderChange(userId, service, newDir, move)
    }

    anchors.fill: parent
    z: 9998
    visible: isOpen

    Rectangle {
        anchors.fill: parent
        color: "#B0060910"
        opacity: root.isOpen ? 1.0 : 0.0
        Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
        MouseArea { anchors.fill: parent }          // nothing behind it can be clicked
    }

    Rectangle {
        id: card
        width: Math.min(560, parent.width - 40)
        height: cardCol.implicitHeight + 48
        anchors.centerIn: parent
        radius: 12
        color: "#131722"
        border.color: "#2D3748"
        border.width: 1
        scale: root.isOpen ? 1.0 : 0.94
        opacity: root.isOpen ? 1.0 : 0.0
        Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        ColumnLayout {
            id: cardCol
            anchors { top: parent.top; left: parent.left; right: parent.right; margins: 24 }
            spacing: 14

            Text {
                Layout.fillWidth: true
                text: root.tr("folder_change_title", "Change download folder") + "  ·  " + root.creatorName
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 16
                font.weight: Font.Bold
                color: "#F8FAFC"
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                text: root.tr("folder_change_body", "%1 file(s) (%2) are already downloaded in the current folder. Move them to the new folder too?")
                          .replace("%1", root.fileCount).replace("%2", root.sizeText)
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: "#CBD5E1"
                wrapMode: Text.WordWrap
            }

            Repeater {
                model: [
                    { label: root.tr("folder_change_from", "Current folder"), path: root.oldDirs, color: "#94A3B8" },
                    { label: root.tr("folder_change_to", "New folder"), path: root.newDir, color: "#38BDF8" }
                ]
                delegate: Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: pathCol.implicitHeight + 16
                    radius: 8
                    color: "#1A202C"
                    border.color: "#2D3748"
                    border.width: 1

                    ColumnLayout {
                        id: pathCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 8 }
                        spacing: 3
                        Text {
                            text: modelData.label
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#64748B"
                        }
                        Text {
                            Layout.fillWidth: true
                            text: modelData.path
                            font.family: "Consolas, 'Cascadia Code', monospace"
                            font.pixelSize: 11
                            color: modelData.color
                            wrapMode: Text.WrapAnywhere
                        }
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                text: root.tr("folder_change_note", "Moving keeps sub-folders and never overwrites a file: same files are merged, different ones with the same name are kept as \"name (2)\". With the download archive on, its records follow the files.")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#64748B"
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 4
                spacing: 10

                StyledButton {
                    text: root.tr("btn_cancel", "Cancel")
                    variant: "ghost"
                    implicitHeight: 34
                    onClicked: root.isOpen = false
                }
                Item { Layout.fillWidth: true }
                StyledButton {
                    text: root.tr("folder_change_new_only", "Only new downloads")
                    tooltip: root.tr("folder_change_new_only_tip", "Files stay where they are and are still recognised; new downloads go to the new folder")
                    variant: "outline"
                    implicitHeight: 34
                    onClicked: root.choose(false)
                }
                StyledButton {
                    text: root.tr("folder_change_move", "Move files")
                    iconText: "📦"
                    variant: "primary"
                    implicitHeight: 34
                    onClicked: root.choose(true)
                }
            }
        }
    }
}
