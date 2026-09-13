import QtQuick
import QtQuick.Controls

// StyledSwitch — dark-theme pill toggle matching Pawchive's slate palette.
// Usage:
//   StyledSwitch {
//       label: "Enable Feature"
//       accentColor: "#38BDF8"
//       checked: bridge.someFlag
//       onToggled: bridge.someFlag = checked
//   }
Item {
    id: root

    property bool checked: false
    property string label: ""
    property string tooltip: ""
    property color accentColor: "#38BDF8"
    property bool enabled: true

    signal toggled(bool isChecked)

    implicitWidth: row.implicitWidth
    implicitHeight: 24

    opacity: root.enabled ? 1.0 : 0.45
    Behavior on opacity { NumberAnimation { duration: 150 } }

    Row {
        id: row
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8

        // Track
        Rectangle {
            id: track
            width: 38
            height: 22
            radius: 11
            anchors.verticalCenter: parent.verticalCenter
            color: root.checked ? root.accentColor : "#252D3D"
            border.color: root.checked ? Qt.darker(root.accentColor, 1.15) : "#334155"
            border.width: 1

            Behavior on color  { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }
            Behavior on border.color { ColorAnimation { duration: 160 } }

            // Inner glow ring when on
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                color: "transparent"
                border.color: root.checked ? Qt.lighter(root.accentColor, 1.3) : "transparent"
                border.width: 1
                opacity: 0.35
                Behavior on border.color { ColorAnimation { duration: 160 } }
            }

            // Thumb
            Rectangle {
                id: thumb
                width: 16
                height: 16
                radius: 8
                anchors.verticalCenter: parent.verticalCenter
                x: root.checked ? parent.width - width - 3 : 3
                color: root.checked ? "white" : "#94A3B8"

                Behavior on x {
                    SpringAnimation {
                        spring: 4.2
                        damping: 0.38
                        mass: 0.8
                        epsilon: 0.25
                    }
                }
                Behavior on color { ColorAnimation { duration: 160 } }

                scale: switchArea.pressed ? 0.86 : (switchArea.containsMouse ? 1.08 : 1.0)
                transformOrigin: Item.Center
                Behavior on scale {
                    SpringAnimation {
                        spring: 4.5
                        damping: 0.35
                        mass: 0.8
                        epsilon: 0.01
                    }
                }
            }

            MouseArea {
                id: switchArea
                anchors.fill: parent
                hoverEnabled: true
                enabled: root.enabled
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.checked = !root.checked
                    root.toggled(root.checked)
                }
            }
        }

        // Label
        Text {
            visible: root.label.length > 0
            text: root.label
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 12
            anchors.verticalCenter: parent.verticalCenter
            color: root.checked ? "#E2E8F0" : "#64748B"
            Behavior on color { ColorAnimation { duration: 160 } }
        }
    }

    // Tooltip
    ToolTip {
        visible: root.tooltip.length > 0 && switchArea.containsMouse
        text: root.tooltip
        delay: 400
        timeout: 5000
        contentItem: Text {
            text: root.tooltip
            font.family: "Segoe UI, Inter, sans-serif"
            font.pixelSize: 11
            color: "#F1F5F9"
            wrapMode: Text.Wrap
        }
        background: Rectangle {
            color: "#181B24"
            border.color: root.accentColor
            border.width: 1
            radius: 6
        }
    }
}
