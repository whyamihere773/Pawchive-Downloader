import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: textContextMenu
    parent: Overlay.overlay
    width: 175
    padding: 6
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    transformOrigin: Popup.TopLeft

    property var target: null

    function showAt(item, mouseX, mouseY) {
        target = item
        if (target && typeof target.forceActiveFocus === "function") {
            target.forceActiveFocus()
        }

        // Map position from target to parent of popup if needed
        var mapped = target ? target.mapToItem(textContextMenu.parent, mouseX, mouseY) : { x: mouseX, y: mouseY }
        var parentWidth = textContextMenu.parent ? textContextMenu.parent.width : 800
        var parentHeight = textContextMenu.parent ? textContextMenu.parent.height : 600

        textContextMenu.x = Math.max(8, Math.min(mapped.x, parentWidth - textContextMenu.width - 8))
        textContextMenu.y = Math.max(8, Math.min(mapped.y, parentHeight - textContextMenu.implicitHeight - 8))
        textContextMenu.open()
    }

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 110; easing.type: Easing.OutCubic }
        NumberAnimation { property: "scale"; from: 0.94; to: 1.0; duration: 110; easing.type: Easing.OutCubic }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 80; easing.type: Easing.InCubic }
        NumberAnimation { property: "scale"; from: 1.0; to: 0.96; duration: 80; easing.type: Easing.InCubic }
    }

    background: Rectangle {
        color: "#0D111A"
        border.color: "#28344A"
        border.width: 1.2
        radius: 8

        // Top accent bar
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 2
            radius: 1
            color: "#38BDF8"
            opacity: 0.8
        }
    }

    contentItem: ColumnLayout {
        spacing: 2

        component MenuItem: Rectangle {
            id: mItem
            Layout.fillWidth: true
            height: 28
            radius: 5

            property string icon: ""
            property string label: ""
            property string shortcut: ""
            property bool danger: false
            property bool active: true
            signal triggered()

            opacity: active ? 1.0 : 0.4
            color: !active ? "transparent" : (mMouse.containsMouse ? (danger ? "#2E151E" : "#172338") : "transparent")
            border.color: !active ? "transparent" : (mMouse.containsMouse ? (danger ? "#7F1D1D" : "#2A436D") : "transparent")
            border.width: 1

            Behavior on color { ColorAnimation { duration: 80 } }
            Behavior on border.color { ColorAnimation { duration: 80 } }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                Text {
                    text: mItem.icon
                    font.pixelSize: 11
                    Layout.alignment: Qt.AlignVCenter
                }

                Text {
                    text: mItem.label
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    color: mItem.danger ? "#FCA5A5" : (mItem.active ? "#F1F5F9" : "#64748B")
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                }

                Text {
                    text: mItem.shortcut
                    font.family: "Segoe UI, monospace, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    Layout.alignment: Qt.AlignVCenter
                    visible: mItem.shortcut.length > 0
                }
            }

            MouseArea {
                id: mMouse
                anchors.fill: parent
                hoverEnabled: mItem.active
                cursorShape: mItem.active ? Qt.PointingHandCursor : Qt.ArrowCursor
                enabled: mItem.active
                onClicked: {
                    mItem.triggered()
                }
            }
        }

        // Paste action
        MenuItem {
            icon: "📋"
            label: "Paste"
            shortcut: "Ctrl+V"
            active: textContextMenu.target && !textContextMenu.target.readOnly
            onTriggered: {
                if (textContextMenu.target) {
                    textContextMenu.target.paste()
                }
                textContextMenu.close()
            }
        }

        // Copy action
        MenuItem {
            icon: "📄"
            label: "Copy"
            shortcut: "Ctrl+C"
            active: textContextMenu.target && textContextMenu.target.selectedText && textContextMenu.target.selectedText.length > 0
            onTriggered: {
                if (textContextMenu.target) {
                    textContextMenu.target.copy()
                }
                textContextMenu.close()
            }
        }

        // Cut action
        MenuItem {
            icon: "✂️"
            label: "Cut"
            shortcut: "Ctrl+X"
            active: textContextMenu.target && !textContextMenu.target.readOnly && textContextMenu.target.selectedText && textContextMenu.target.selectedText.length > 0
            onTriggered: {
                if (textContextMenu.target) {
                    textContextMenu.target.cut()
                }
                textContextMenu.close()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#1E2738"
            Layout.topMargin: 2
            Layout.bottomMargin: 2
        }

        // Select All action
        MenuItem {
            icon: "🔲"
            label: "Select All"
            shortcut: "Ctrl+A"
            active: textContextMenu.target && textContextMenu.target.text && textContextMenu.target.text.length > 0
            onTriggered: {
                if (textContextMenu.target) {
                    textContextMenu.target.selectAll()
                }
                textContextMenu.close()
            }
        }

        // Clear action
        MenuItem {
            icon: "🗑️"
            label: "Clear"
            danger: true
            active: textContextMenu.target && !textContextMenu.target.readOnly && textContextMenu.target.text && textContextMenu.target.text.length > 0
            onTriggered: {
                if (textContextMenu.target) {
                    textContextMenu.target.text = ""
                    if (typeof textContextMenu.target.editingFinished === "function") {
                        textContextMenu.target.editingFinished()
                    }
                }
                textContextMenu.close()
            }
        }
    }
}
