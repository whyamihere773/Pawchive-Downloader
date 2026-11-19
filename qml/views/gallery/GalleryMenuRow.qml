import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: menuRow
    property string icon: ""
    property string label: ""
    property string hint: ""
    property bool danger: false
    property bool checked: false
    signal triggered()
    width: parent ? parent.width : 200
    height: 26
    radius: 4
    color: rowMouse.containsMouse ? (danger ? "#3A1620" : "#1E293D") : "transparent"

    Row {
        anchors.left: parent.left
        anchors.leftMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8
        transform: Translate {
            x: rowMouse.containsMouse ? 3 : 0
            Behavior on x { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.001 } }
        }
        // Color only affects plain symbols (☑ ✕ ▲); color emoji keep their own colors
        Text {
            text: menuRow.icon
            font.pixelSize: 11
            width: 16
            horizontalAlignment: Text.AlignHCenter
            color: menuRow.danger ? "#F87171" : (menuRow.checked ? "#38BDF8" : "#CBD5E1")
        }
        Text {
            text: menuRow.label
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            font.weight: menuRow.checked ? 700 : Font.Normal
            color: menuRow.danger ? "#F87171" : (menuRow.checked ? "#38BDF8" : "#E2E8F0")
        }
    }
    Text {
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        text: menuRow.hint
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 9
        color: "#64748B"
    }
    MouseArea {
        id: rowMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: menuRow.triggered()
    }
}
