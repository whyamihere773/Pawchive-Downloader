import QtQuick
import QtQuick.Controls

TextField {
    id: control

    property string leadingIcon: ""
    property bool showClearButton: true
    property int customRadius: 8

    font.family: "Segoe UI, Inter, sans-serif"
    font.pixelSize: 13
    color: "#F1F5F9"
    placeholderTextColor: "#64748B"
    selectByMouse: true
    selectedTextColor: "#FFFFFF"
    selectionColor: "#0284C7"
    implicitHeight: 34

    leftPadding: leadingIcon.length > 0 ? 32 : 12
    rightPadding: (showClearButton && control.text.length > 0) ? 30 : 12

    // Leading icon
    Text {
        anchors.left: parent.left
        anchors.leftMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        text: control.leadingIcon
        color: control.activeFocus ? "#38BDF8" : "#64748B"
        font.pixelSize: 13
        visible: control.leadingIcon.length > 0
    }

    // Clear text button
    Rectangle {
        id: clearBtn
        width: 18
        height: 18
        radius: 9
        color: clearMouse.containsMouse ? "#374151" : "#1F2937"
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        visible: control.showClearButton && control.text.length > 0

        scale: clearMouse.pressed ? 0.85 : (clearMouse.containsMouse ? 1.15 : 1.0)
        transformOrigin: Item.Center

        Behavior on scale {
            NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.6 }
        }
        Behavior on color {
            ColorAnimation { duration: 120 }
        }

        Text {
            anchors.centerIn: parent
            text: "×"
            color: clearMouse.containsMouse ? "#F8FAFC" : "#94A3B8"
            font.pixelSize: 13
            font.bold: true
        }

        MouseArea {
            id: clearMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                control.text = ""
                control.editingFinished()
            }
        }
    }

    background: Rectangle {
        implicitWidth: 200
        implicitHeight: control.implicitHeight
        radius: control.customRadius
        color: control.activeFocus ? "#0E1118" : (control.hovered ? "#161922" : "#14171F")
        border.color: control.activeFocus ? "#38BDF8" : (control.hovered ? "#475569" : "#2E3544")
        border.width: control.activeFocus ? 1.5 : 1

        // Dynamic focus glow
        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: control.customRadius + 2
            color: "transparent"
            border.color: "#38BDF8"
            border.width: 1.5
            opacity: control.activeFocus ? 0.4 : 0.0
            z: -1

            Behavior on opacity {
                NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
            }
        }

        Behavior on color {
            ColorAnimation { duration: 160; easing.type: Easing.OutCubic }
        }
        Behavior on border.color {
            ColorAnimation { duration: 160; easing.type: Easing.OutCubic }
        }
    }
}
