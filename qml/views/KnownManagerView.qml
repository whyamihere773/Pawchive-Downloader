import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Rectangle {
    id: root

    property var bridge: null
    color: "#0F1117"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // Header & Quick Add
        CardSection {
            Layout.fillWidth: true
            title: "Known Series & Characters (for folder categorization & filters)"
            iconText: "🏷️"

            ColumnLayout {
                width: parent.width
                spacing: 10

                // Search and Add inputs
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    StyledTextField {
                        id: searchBox
                        Layout.fillWidth: true
                        placeholderText: "Search characters or series..."
                        leadingIcon: "🔍"
                        onTextChanged: {
                            if (root.bridge && root.bridge.knownModel) {
                                root.bridge.knownModel.setSearchQuery(text)
                            }
                        }
                    }

                    StyledButton {
                        text: "Open Known.txt"
                        iconText: "📄"
                        variant: "outline"
                        onClicked: if (root.bridge) root.bridge.openKnownTxt()
                    }
                }

                // Add new entry bar
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    StyledTextField {
                        id: newNameInput
                        Layout.fillWidth: true
                        placeholderText: "Add a name, or aliases: Katarin | Katarin Bokha"
                        leadingIcon: "➕"
                        onAccepted: addBtn.clicked()
                    }

                    StyledButton {
                        id: addBtn
                        text: "Add"
                        iconText: "➕"
                        variant: "primary"
                        onClicked: {
                            if (newNameInput.text.trim().length > 0 && root.bridge) {
                                root.bridge.addKnownCharacter(newNameInput.text.trim())
                                newNameInput.text = ""
                            }
                        }
                    }
                }
            }
        }

        // Characters Grid / ListView
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#141720"
            border.color: "#242A38"
            border.width: 1
            radius: 8
            clip: true

            ListView {
                id: knownList
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6
                model: root.bridge ? root.bridge.knownModel : null

                ScrollBar.vertical: ScrollBar { active: true; policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    width: knownList.width - 12
                    height: 38
                    radius: 6
                    color: itemMouse.pressed ? "#161B26" : (itemMouse.containsMouse ? "#202534" : "#191D28")
                    border.color: itemMouse.containsMouse ? "#38BDF8" : "#282E3D"
                    border.width: 1

                    scale: itemMouse.pressed ? 0.98 : (itemMouse.containsMouse ? 1.012 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.4 }
                    }
                    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                    Behavior on border.color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }

                    MouseArea {
                        id: itemMouse
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 8
                        spacing: 8

                        Text {
                            text: "🏷️"
                            font.pixelSize: 12
                        }

                        Text {
                            text: model.name
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: "#F1F5F9"
                            Layout.fillWidth: true
                        }

                        StyledButton {
                            text: "+ Add to Filter"
                            variant: "outline"
                            implicitHeight: 26
                            implicitWidth: 100
                            onClicked: {
                                if (root.bridge) root.bridge.applyCharacterToFilter(model.name)
                            }
                        }

                        StyledButton {
                            text: "Delete"
                            variant: "ghost"
                            implicitHeight: 26
                            implicitWidth: 60
                            onClicked: {
                                if (root.bridge) root.bridge.removeKnownCharacter(index)
                            }
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    text: "No characters or series found."
                    color: "#64748B"
                    font.family: "Segoe UI, sans-serif"
                    visible: knownList.count === 0
                }
            }
        }
    }
}
