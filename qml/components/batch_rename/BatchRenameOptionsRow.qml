import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Advanced Options & Move-to-Folder Bar for Smart Batch Renamer.
RowLayout {
    id: optionsRow

    required property var modal
    Layout.fillWidth: true
    Layout.fillHeight: false
    spacing: 14

    // Option 1: Files only
    RowLayout {
        spacing: 5
        Layout.alignment: Qt.AlignVCenter
        Rectangle {
            width: 14; height: 14; radius: 3
            color: modal.filesOnly ? "#38BDF8" : "#161D2B"
            border.color: "#374151"; border.width: 1
            Text { visible: modal.filesOnly; anchors.centerIn: parent; text: "✓"; font.pixelSize: 9; font.weight: Font.Bold; color: "#0B0E14" }
            Springy { hover: filesOnlyMouse.containsMouse; pressed: filesOnlyMouse.pressed }
            MouseArea {
                id: filesOnlyMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    modal.filesOnly = !modal.filesOnly
                    modal.updatePreview()
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "When checked, only renames individual files and skips modifying subfolder names."
            }
        }
        Text {
            text: "Files only (skip folders)"
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 10
            color: "#94A3B8"
            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    modal.filesOnly = !modal.filesOnly
                    modal.updatePreview()
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "When checked, only renames individual files and skips modifying subfolder names."
            }
        }
    }

    // Option 2: Include subfolders (continuous numbering)
    RowLayout {
        spacing: 5
        Layout.alignment: Qt.AlignVCenter
        Rectangle {
            width: 14; height: 14; radius: 3
            color: modal.includeSubfolders ? "#818CF8" : "#161D2B"
            border.color: "#374151"; border.width: 1
            Text { visible: modal.includeSubfolders; anchors.centerIn: parent; text: "✓"; font.pixelSize: 9; font.weight: Font.Bold; color: "#0B0E14" }
            Springy { hover: subfoldersMouse.containsMouse; pressed: subfoldersMouse.pressed }
            MouseArea {
                id: subfoldersMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    modal.includeSubfolders = !modal.includeSubfolders
                    modal.updatePreview()
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "Recursively scans files in all subfolders and numbers them continuously across folders\n(e.g. Folder 1 gets 1-100, Folder 2 starts at 101)."
            }
        }
        Text {
            text: "Include subfolders (continuous sequence)"
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 10
            color: modal.includeSubfolders ? "#C7D2FE" : "#94A3B8"
            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    modal.includeSubfolders = !modal.includeSubfolders
                    modal.updatePreview()
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "Recursively scans files in all subfolders and numbers them continuously across folders\n(e.g. Folder 1 gets 1-100, Folder 2 starts at 101)."
            }
        }
    }

    // Option 3: Move all into folder
    RowLayout {
        spacing: 5
        Layout.alignment: Qt.AlignVCenter
        Rectangle {
            width: 14; height: 14; radius: 3
            color: modal.moveToFolder ? "#10B981" : "#161D2B"
            border.color: "#374151"; border.width: 1
            Text { visible: modal.moveToFolder; anchors.centerIn: parent; text: "✓"; font.pixelSize: 9; font.weight: Font.Bold; color: "#0B0E14" }
            Springy { hover: moveFolderMouse.containsMouse; pressed: moveFolderMouse.pressed }
            MouseArea {
                id: moveFolderMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    modal.moveToFolder = !modal.moveToFolder
                    modal.updatePreview()
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "Flattens and moves all renamed files into a single destination folder."
            }
        }
        Text {
            text: "Move all into folder"
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 10
            color: modal.moveToFolder ? "#6EE7B7" : "#94A3B8"
            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    modal.moveToFolder = !modal.moveToFolder
                    modal.updatePreview()
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "Flattens and moves all renamed files into a single destination folder."
            }
        }
    }

    // Destination Folder Indicator & Picker
    RowLayout {
        visible: modal.moveToFolder
        spacing: 5
        Layout.alignment: Qt.AlignVCenter

        Rectangle {
            implicitHeight: 22
            implicitWidth: Math.min(220, destLabel.implicitWidth + 14)
            radius: 4
            color: "#0B1D15"
            border.color: "#059669"
            border.width: 1
            clip: true
            Text {
                id: destLabel
                anchors.centerIn: parent
                width: Math.min(implicitWidth, Math.max(0, parent.width - 14))
                horizontalAlignment: Text.AlignHCenter
                text: "📁 " + (modal.destinationFolder ? modal.destinationFolder : "Current Folder")
                elide: Text.ElideMiddle
                maximumLineCount: 1
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                color: "#A7F3D0"
            }
            MouseArea {
                id: destPillMouse
                anchors.fill: parent
                hoverEnabled: true
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "Target destination folder where renamed files will be moved:\n" + (modal.destinationFolder || modal.folderPath)
            }
        }

        Rectangle {
            implicitHeight: 22
            implicitWidth: changeDestTxt.implicitWidth + 12
            radius: 4
            color: changeDestMouse.containsMouse ? "#10B981" : "#065F46"
            border.color: "#059669"
            border.width: 1
            Text {
                id: changeDestTxt
                anchors.centerIn: parent
                text: "Change..."
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                font.weight: 600
                color: "#FFFFFF"
            }
            Springy { hover: changeDestMouse.containsMouse; pressed: changeDestMouse.pressed }
            MouseArea {
                id: changeDestMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (modal.bridge && modal.bridge.browseFolderDialog) {
                        var chosen = modal.bridge.browseFolderDialog("Select Target Destination Folder", modal.destinationFolder || modal.folderPath)
                        if (chosen && chosen.length > 0) {
                            modal.destinationFolder = chosen
                            modal.updatePreview()
                        }
                    }
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "Browse and select a different target folder or drive to move renamed files into."
            }
        }
    }

    Item { Layout.fillWidth: true }
}

