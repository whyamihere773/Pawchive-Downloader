import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: rr
    property int current: 0
    property int hovered: 0
    signal rated(int n)
    width: parent ? parent.width : 200
    height: 26
    radius: 4
    color: "transparent"
    Row {
        anchors.left: parent.left
        anchors.leftMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8
        Text { text: "★"; width: 16; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 11; color: "#CBD5E1" }
        Text { text: "Rate"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; color: "#E2E8F0"; width: 34 }
        Repeater {
            model: 5
            delegate: Text {
                readonly property int n: index + 1
                text: (rr.hovered ? n <= rr.hovered : n <= rr.current) ? "★" : "☆"
                font.pixelSize: 14
                color: (rr.hovered ? n <= rr.hovered : n <= rr.current) ? "#FBBF24" : "#64748B"
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -2
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onEntered: rr.hovered = parent.n
                    onExited: rr.hovered = 0
                    onClicked: rr.rated(parent.n === rr.current ? 0 : parent.n)
                }
            }
        }
    }
}
