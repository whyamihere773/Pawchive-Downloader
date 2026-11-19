import QtQuick
import ".."

Rectangle {
    id: btn
    property string label: ""
    property bool primary: false
    property bool danger: false
    property bool enabledState: true
    signal clicked()
    implicitHeight: 30
    implicitWidth: btnText.implicitWidth + 26
    radius: 6
    opacity: enabledState ? 1.0 : 0.45
    color: primary ? (btnMouse.containsMouse && enabledState ? "#0EA5E9" : "#0284C7")
                   : (btnMouse.containsMouse && enabledState ? (danger ? "#3A1620" : "#1E293B") : "#141720")
    border.color: primary ? "#38BDF8" : (danger ? "#EF4444" : "#2E384D")
    border.width: 1
    Text {
        id: btnText
        anchors.centerIn: parent
        text: btn.label
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 11
        font.weight: 700
        color: primary ? "#FFFFFF" : (danger ? "#F87171" : "#E2E8F0")
    }
    Springy { hover: btnMouse.containsMouse; pressed: btnMouse.pressed }
    MouseArea {
        id: btnMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: btn.enabledState ? Qt.PointingHandCursor : Qt.ForbiddenCursor
        onClicked: if (btn.enabledState) btn.clicked()
    }
}

