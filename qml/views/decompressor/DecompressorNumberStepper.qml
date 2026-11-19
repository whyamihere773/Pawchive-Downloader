import QtQuick
import QtQuick.Layouts

// Custom themed stepper component matching the Pawchive dark cyber aesthetic
Rectangle {
    id: stepper
    property int from: 1
    property int to: 10
    property int value: 1
    signal valueModified(int val)

    implicitWidth: 88
    implicitHeight: 26
    radius: 6
    color: "#111827"
    border.color: "#283042"
    border.width: 1

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Minus button
        Rectangle {
            Layout.preferredWidth: 26
            Layout.fillHeight: true
            radius: 5
            color: minusMouse.pressed ? "#1E293B" : (minusMouse.containsMouse ? "#1F293D" : "transparent")
            opacity: stepper.value > stepper.from ? 1.0 : 0.35

            Text {
                anchors.centerIn: parent
                text: "−"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 14
                font.weight: Font.Bold
                color: minusMouse.containsMouse ? "#38BDF8" : "#94A3B8"
            }

            MouseArea {
                id: minusMouse
                anchors.fill: parent
                hoverEnabled: stepper.value > stepper.from
                cursorShape: stepper.value > stepper.from ? Qt.PointingHandCursor : Qt.ArrowCursor
                enabled: stepper.value > stepper.from
                onClicked: {
                    var v = Math.max(stepper.from, stepper.value - 1);
                    stepper.value = v;
                    stepper.valueModified(v);
                }
            }
        }

        // Value text
        Text {
            Layout.fillWidth: true
            Layout.fillHeight: true
            text: stepper.value
            font.family: "Segoe UI, Inter, sans-serif"
            font.pixelSize: 12
            font.weight: 600
            color: "#F1F5F9"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        // Plus button
        Rectangle {
            Layout.preferredWidth: 26
            Layout.fillHeight: true
            radius: 5
            color: plusMouse.pressed ? "#1E293B" : (plusMouse.containsMouse ? "#1F293D" : "transparent")
            opacity: stepper.value < stepper.to ? 1.0 : 0.35

            Text {
                anchors.centerIn: parent
                text: "+"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 13
                font.weight: Font.Bold
                color: plusMouse.containsMouse ? "#38BDF8" : "#94A3B8"
            }

            MouseArea {
                id: plusMouse
                anchors.fill: parent
                hoverEnabled: stepper.value < stepper.to
                cursorShape: stepper.value < stepper.to ? Qt.PointingHandCursor : Qt.ArrowCursor
                enabled: stepper.value < stepper.to
                onClicked: {
                    var v = Math.min(stepper.to, stepper.value + 1);
                    stepper.value = v;
                    stepper.valueModified(v);
                }
            }
        }
    }
}
