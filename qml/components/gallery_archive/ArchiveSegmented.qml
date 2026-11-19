import QtQuick
import QtQuick.Controls
import ".."

Rectangle {
    id: seg
    property var options: []     // [{ value, label, tip }]
    property string value: ""
    signal picked(string choice)
    implicitHeight: 26
    implicitWidth: segRow.implicitWidth + 4
    radius: 6
    color: "#0D1018"
    border.color: "#252D3E"
    border.width: 1
    Row {
        id: segRow
        anchors.centerIn: parent
        spacing: 2
        Repeater {
            model: seg.options
            delegate: Rectangle {
                readonly property bool active: seg.value === modelData.value
                implicitHeight: 22
                implicitWidth: segText.implicitWidth + 18
                radius: 4
                color: active ? "#1E3A5F" : (segMouse.containsMouse ? "#182030" : "transparent")
                border.color: active ? "#38BDF8" : "transparent"
                border.width: 1
                Text {
                    id: segText
                    anchors.centerIn: parent
                    text: modelData.label
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: active ? 700 : 600
                    color: active ? "#38BDF8" : "#94A3B8"
                }
                Springy { hover: segMouse.containsMouse; pressed: segMouse.pressed }
                MouseArea {
                    id: segMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: seg.picked(modelData.value)
                    ToolTip.visible: containsMouse && !!modelData.tip
                    ToolTip.delay: 300
                    ToolTip.text: modelData.tip || ""
                }
            }
        }
    }
}

