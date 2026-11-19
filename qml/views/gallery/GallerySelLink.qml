import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Text {
    id: link
    property string label: ""
    property string tip: ""
    signal triggered()
    text: label
    font.family: "Segoe UI, sans-serif"
    font.pixelSize: 10
    font.weight: 600
    font.underline: linkMouse.containsMouse
    color: linkMouse.containsMouse ? "#BAE6FD" : "#7DD3FC"
    Springy { hover: linkMouse.containsMouse; pressed: linkMouse.pressed }
    MouseArea {
        id: linkMouse
        anchors.fill: parent
        anchors.margins: -3
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: link.triggered()
        ToolTip.visible: containsMouse && link.tip.length > 0
        ToolTip.delay: 300
        ToolTip.text: link.tip
    }
}
