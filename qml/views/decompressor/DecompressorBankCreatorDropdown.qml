import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Floating Artist Selector Dropdown Menu
Rectangle {
    id: creatorDropdownMenu
    required property var view
    property real anchorBottomY: 0
    signal creatorPicked()

    function focusAndSelect(name) {
        creatorDropdownMenu.forceActiveFocus();
        var names = creatorDropdownMenu.view.decompressor ? creatorDropdownMenu.view.decompressor.bankCreatorNames : ["Global"];
        var idx = names.indexOf(name);
        if (idx >= 0) {
            creatorListView.currentIndex = idx;
            creatorListView.positionViewAtIndex(idx, ListView.Center);
        }
    }
    objectName: "creatorDropdownMenu"
    z: 99
    visible: opacity > 0
    opacity: creatorDropdownMenu.view.isCreatorMenuOpen ? 1.0 : 0.0
    scale: creatorDropdownMenu.view.isCreatorMenuOpen ? 1.0 : 0.93
    transformOrigin: Item.BottomLeft
    focus: creatorDropdownMenu.view.isCreatorMenuOpen

    Behavior on opacity { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }
    Behavior on scale { SpringAnimation { spring: 5.5; damping: 0.45; mass: 0.85; epsilon: 0.005 } }

    x: 18
    y: creatorDropdownMenu.anchorBottomY - height - 6
    width: 240
    height: Math.min(creatorListView.contentHeight + 14, 230)
    radius: 8
    color: "#0E1422"
    border.color: "#1E293B"
    border.width: 1
    clip: true

    // Keyboard navigation and instant letter-jump (e.g. Press 'E' -> jumps to creators starting with 'E')
    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape) {
            creatorDropdownMenu.view.isCreatorMenuOpen = false;
            event.accepted = true;
            return;
        }
        if (event.key === Qt.Key_Down) {
            if (creatorListView.currentIndex < creatorListView.count - 1) {
                creatorListView.currentIndex++;
                creatorListView.positionViewAtIndex(creatorListView.currentIndex, ListView.Contain);
            }
            event.accepted = true;
            return;
        }
        if (event.key === Qt.Key_Up) {
            if (creatorListView.currentIndex > 0) {
                creatorListView.currentIndex--;
                creatorListView.positionViewAtIndex(creatorListView.currentIndex, ListView.Contain);
            }
            event.accepted = true;
            return;
        }
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            var names = creatorDropdownMenu.view.decompressor ? creatorDropdownMenu.view.decompressor.bankCreatorNames : ["Global"];
            if (creatorListView.currentIndex >= 0 && creatorListView.currentIndex < names.length) {
                creatorDropdownMenu.view.selectedBankCreator = names[creatorListView.currentIndex];
                creatorDropdownMenu.view.isCreatorMenuOpen = false;
                creatorDropdownMenu.creatorPicked();
            }
            event.accepted = true;
            return;
        }

        var text = event.text;
        if (text && text.length === 1) {
            var ch = text.toLowerCase();
            var names = creatorDropdownMenu.view.decompressor ? creatorDropdownMenu.view.decompressor.bankCreatorNames : ["Global"];
            for (var i = 0; i < names.length; i++) {
                var cName = names[i];
                if (cName.length > 0 && cName[0].toLowerCase() === ch) {
                    creatorListView.currentIndex = i;
                    creatorListView.positionViewAtIndex(i, ListView.Beginning);
                    event.accepted = true;
                    return;
                }
            }
        }
    }

    ListView {
        id: creatorListView
        objectName: "creatorListView"
        anchors.fill: parent
        anchors.margins: 6
        clip: true
        model: creatorDropdownMenu.view.decompressor ? creatorDropdownMenu.view.decompressor.bankCreatorNames : ["Global"]
        currentIndex: {
            var names = creatorDropdownMenu.view.decompressor ? creatorDropdownMenu.view.decompressor.bankCreatorNames : ["Global"];
            var idx = names.indexOf(creatorDropdownMenu.view.selectedBankCreator);
            return idx >= 0 ? idx : 0;
        }
        spacing: 2

        ScrollBar.vertical: ScrollBar {
            id: menuScroll
            active: true
            policy: ScrollBar.AsNeeded
            width: 6
        }

        delegate: Rectangle {
            id: creatorItemDelegate
            width: creatorListView.width - (menuScroll.visible ? 8 : 0)
            height: 30
            radius: 5
            property bool isSelected: creatorDropdownMenu.view.selectedBankCreator === modelData
            property int pwCount: {
                var name = modelData;
                if (creatorDropdownMenu.view.pwBankTree) {
                    for (var i = 0; i < creatorDropdownMenu.view.pwBankTree.length; i++) {
                        if (creatorDropdownMenu.view.pwBankTree[i].creator === name) {
                            return creatorDropdownMenu.view.pwBankTree[i].count || (creatorDropdownMenu.view.pwBankTree[i].passwords ? creatorDropdownMenu.view.pwBankTree[i].passwords.length : 0);
                        }
                    }
                }
                return 0;
            }

            color: isSelected ? "#162234" : (itemMouse.containsMouse ? "#151D2C" : "transparent")
            border.color: isSelected ? "#1E3A5F" : "transparent"
            border.width: 1
            clip: true

            // Active item left blue accent bar
            Rectangle {
                width: 3
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.topMargin: 4
                anchors.bottomMargin: 4
                radius: 1.5
                color: "#38BDF8"
                visible: creatorItemDelegate.isSelected
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: creatorItemDelegate.isSelected ? 10 : 8
                anchors.rightMargin: 8
                spacing: 6

                Text {
                    text: modelData === "Global" ? "🌐" : "👤"
                    font.pixelSize: 11
                }

                Text {
                    text: modelData
                    font.pixelSize: 11
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.weight: creatorItemDelegate.isSelected ? Font.DemiBold : Font.Normal
                    color: creatorItemDelegate.isSelected ? "#38BDF8" : (itemMouse.containsMouse ? "#F1F5F9" : "#CBD5E1")
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                // Saved password count badge for each artist
                Rectangle {
                    visible: creatorItemDelegate.pwCount > 0
                    implicitHeight: 16
                    implicitWidth: Math.max(16, countTxt.implicitWidth + 8)
                    radius: 8
                    color: creatorItemDelegate.isSelected ? "#0284C7" : "#1E293B"
                    border.color: creatorItemDelegate.isSelected ? "#38BDF8" : "#334155"
                    border.width: 1

                    Text {
                        id: countTxt
                        anchors.centerIn: parent
                        text: creatorItemDelegate.pwCount.toString()
                        font.pixelSize: 9
                        font.weight: Font.Bold
                        color: creatorItemDelegate.isSelected ? "#FFFFFF" : "#94A3B8"
                    }
                }

                Text {
                    text: "✓"
                    font.pixelSize: 10
                    font.weight: Font.Bold
                    color: "#38BDF8"
                    visible: creatorItemDelegate.isSelected
                }
            }

            MouseArea {
                id: itemMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    creatorDropdownMenu.view.selectedBankCreator = modelData;
                    creatorListView.currentIndex = index;
                    creatorDropdownMenu.view.isCreatorMenuOpen = false;
                    creatorDropdownMenu.creatorPicked();
                }
            }
        }
    }
}
