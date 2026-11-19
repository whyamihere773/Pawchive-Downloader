import QtQuick

Item {
    id: chk
    property string label: ""
    property bool checked: false
    signal toggled()
    implicitHeight: 20
    implicitWidth: chkRow.implicitWidth
    Row {
        id: chkRow
        spacing: 8
        anchors.verticalCenter: parent.verticalCenter
        Rectangle {
            width: 15; height: 15; radius: 3
            anchors.verticalCenter: parent.verticalCenter
            color: chk.checked ? "#38BDF8" : "transparent"
            border.color: chk.checked ? "#38BDF8" : (chkMouse.containsMouse ? "#38BDF8" : "#64748B")
            border.width: 1
            Text { anchors.centerIn: parent; visible: chk.checked; text: "✓"; font.pixelSize: 10; font.weight: 800; color: "#0F172A" }
        }
        Text {
            text: chk.label
            anchors.verticalCenter: parent.verticalCenter
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#CBD5E1"
        }
    }
    MouseArea {
        id: chkMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: chk.toggled()
    }
}

