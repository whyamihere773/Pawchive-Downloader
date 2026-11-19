import QtQuick
import QtQuick.Controls
import ".."

// Compact icon button used across the MediaLightboxModal top toolbar.
Rectangle {
    id: lbb
    property string glyph: ""
    property string tip: ""
    property bool active: false
    property bool danger: false
    property color activeColor: "#38BDF8"
    signal clicked()
    width: 28
    height: 28
    radius: 5
    color: lbbMouse.containsMouse ? (danger ? "#3A1620" : "#222D42") : "#141A28"
    border.color: active ? activeColor : (lbbMouse.containsMouse ? (danger ? "#EF4444" : "#38BDF8") : "#2A364E")
    border.width: 1
    Text {
        anchors.centerIn: parent
        text: lbb.glyph
        font.pixelSize: 13
        color: lbb.active ? lbb.activeColor : (lbb.danger ? "#F87171" : "#E2E8F0")
    }
    Springy { hover: lbbMouse.containsMouse; pressed: lbbMouse.pressed }
    MouseArea {
        id: lbbMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: lbb.clicked()
        ToolTip.visible: containsMouse && lbb.tip.length > 0
        ToolTip.delay: 250
        ToolTip.text: lbb.tip
    }
}
