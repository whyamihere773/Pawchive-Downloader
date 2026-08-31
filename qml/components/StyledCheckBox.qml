import QtQuick
import QtQuick.Controls

CheckBox {
    id: control

    property color accentColor: "#38BDF8"
    property string tooltip: ""

    ToolTip {
        text: control.tooltip
        visible: control.tooltip.length > 0 && control.hovered
        delay: 400
        timeout: 5000
        contentItem: Text {
            text: control.tooltip
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

    font.family: "Segoe UI, Inter, sans-serif"
    font.pixelSize: 12
    spacing: 8

    indicator: Rectangle {
        implicitWidth: 18
        implicitHeight: 18
        x: control.leftPadding
        anchors.verticalCenter: parent.verticalCenter
        radius: 4
        color: control.checked ? control.accentColor : "#14171F"
        border.color: control.checked ? control.accentColor : (control.hovered ? "#64748B" : "#333A48")
        border.width: control.checked ? 1.5 : 1

        scale: control.down ? 0.90 : (control.hovered ? 1.08 : 1.0)
        transformOrigin: Item.Center

        Behavior on scale {
            NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
        }
        Behavior on color {
            ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
        }
        Behavior on border.color {
            ColorAnimation { duration: 140; easing.type: Easing.OutCubic }
        }

        // Checkmark symbol with spring pop-in
        Text {
            anchors.centerIn: parent
            text: "✓"
            color: "#0F172A"
            font.bold: true
            font.pixelSize: 12
            scale: control.checked ? 1.0 : 0.2
            opacity: control.checked ? 1.0 : 0.0

            Behavior on scale {
                NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.8 }
            }
            Behavior on opacity {
                NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
            }
        }
    }

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.checked ? "#F1F5F9" : (control.hovered ? "#CBD5E1" : "#94A3B8")
        verticalAlignment: Text.AlignVCenter
        leftPadding: control.indicator.width + control.spacing

        Behavior on color {
            ColorAnimation { duration: 140 }
        }
    }
}
