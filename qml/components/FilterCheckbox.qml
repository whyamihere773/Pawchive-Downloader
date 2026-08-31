import QtQuick
import QtQuick.Controls

Item {
    id: root

    property string label: ""
    property string iconText: ""
    property bool checked: false
    property color activeColor: "#38BDF8"
    property string tooltip: ""

    ToolTip {
        text: root.tooltip
        visible: root.tooltip.length > 0 && mouseArea.containsMouse
        delay: 400
        timeout: 5000
        contentItem: Text {
            text: root.tooltip
            font.family: "Segoe UI, Inter, sans-serif"
            font.pixelSize: 11
            color: "#F1F5F9"
        }
        background: Rectangle {
            color: "#181B24"
            border.color: "#38BDF8"
            border.width: 1
            radius: 6
        }
    }

    signal toggled(bool isChecked)
    signal clicked()

    implicitHeight: 28
    implicitWidth: rowLayout.implicitWidth + 16

    // Physical Newtonian Spring on Press / Hover
    scale: mouseArea.pressed ? 0.93 : (mouseArea.containsMouse ? 1.04 : 1.0)
    transformOrigin: Item.Center

    Behavior on scale {
        NumberAnimation {
            duration: mouseArea.pressed ? 100 : 200
            easing.type: mouseArea.pressed ? Easing.OutCubic : Easing.OutBack
            easing.overshoot: 1.5
        }
    }

    Rectangle {
        id: bg
        anchors.fill: parent
        radius: 6
        color: root.checked ? Qt.rgba(root.activeColor.r, root.activeColor.g, root.activeColor.b, 0.18) : (mouseArea.containsMouse ? "#222733" : "#181B24")
        border.color: root.checked ? root.activeColor : (mouseArea.containsMouse ? "#475569" : "#2E3544")
        border.width: root.checked ? 1.5 : 1

        Behavior on color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }
        Behavior on border.color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }

        Row {
            id: rowLayout
            spacing: 6
            anchors.centerIn: parent

            Text {
                text: root.iconText
                visible: root.iconText.length > 0
                font.pixelSize: 12
                anchors.verticalCenter: parent.verticalCenter
                color: root.checked ? root.activeColor : "#94A3B8"

                scale: root.checked ? 1.15 : (mouseArea.containsMouse ? 1.08 : 1.0)
                Behavior on scale {
                    NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.6 }
                }
            }

            Text {
                text: root.label
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 11
                font.weight: root.checked ? Font.DemiBold : Font.Medium
                color: root.checked ? "#F8FAFC" : "#94A3B8"
                anchors.verticalCenter: parent.verticalCenter

                Behavior on color { ColorAnimation { duration: 150 } }
            }
        }

        MouseArea {
            id: mouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                root.toggled(!root.checked)
                root.clicked()
            }
        }
    }
}
