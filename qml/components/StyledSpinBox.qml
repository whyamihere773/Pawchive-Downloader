import QtQuick
import QtQuick.Controls

// StyledSpinBox — dark-theme +/- counter matching Pawchive's slate palette.
// Usage:
//   StyledSpinBox {
//       from: 1; to: 72; value: 6; stepSize: 1
//       suffix: " hrs"
//       onValueModified: doSomething(value)
//   }
Item {
    id: root

    property int from: 0
    property int to: 99
    property int value: 0
    property int stepSize: 1
    property string suffix: ""
    property string prefix: ""
    property color accentColor: "#38BDF8"
    property bool enabled: true

    signal valueModified(int newValue)

    implicitWidth: 120
    implicitHeight: 32

    opacity: root.enabled ? 1.0 : 0.45
    Behavior on opacity { NumberAnimation { duration: 150 } }

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: "#141923"
        border.color: root.enabled && (minusArea.containsMouse || plusArea.containsMouse) ? root.accentColor : "#283042"
        border.width: 1
        clip: true

        Behavior on border.color { ColorAnimation { duration: 150 } }

        Row {
            anchors.fill: parent

            // — Decrement button
            Rectangle {
                id: minusBtn
                width: 28
                height: parent.height
                color: minusArea.pressed ? "#1E293B" : (minusArea.containsMouse ? "#1A2234" : "transparent")
                Behavior on color { ColorAnimation { duration: 100 } }

                Text {
                    anchors.centerIn: parent
                    text: "−"
                    font.pixelSize: 16
                    font.weight: Font.Light
                    color: minusArea.pressed ? root.accentColor
                         : (minusArea.containsMouse ? "#CBD5E1" : "#64748B")
                    scale: minusArea.pressed ? 0.82 : (minusArea.containsMouse ? 1.18 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale {
                        SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.01 }
                    }
                    Behavior on color { ColorAnimation { duration: 100 } }
                }

                MouseArea {
                    id: minusArea
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: root.enabled
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        var next = Math.max(root.from, root.value - root.stepSize)
                        if (next !== root.value) {
                            root.value = next
                            root.valueModified(next)
                        }
                    }
                    // Hold-to-repeat
                    onPressAndHold: repeatTimer.start()
                    onReleased: repeatTimer.stop()

                    Timer {
                        id: repeatTimer
                        interval: 120
                        repeat: true
                        onTriggered: {
                            var next = Math.max(root.from, root.value - root.stepSize)
                            if (next !== root.value) {
                                root.value = next
                                root.valueModified(next)
                            } else {
                                repeatTimer.stop()
                            }
                        }
                    }
                }

                // Right divider
                Rectangle {
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.topMargin: 6
                    anchors.bottomMargin: 6
                    width: 1
                    color: "#283042"
                }
            }

            // Value display with Newtonian pulse
            Item {
                width: parent.width - 56
                height: parent.height

                Text {
                    id: valText
                    anchors.centerIn: parent
                    text: root.prefix + root.value + root.suffix
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    color: root.accentColor
                    horizontalAlignment: Text.AlignHCenter

                    scale: 1.0
                    transformOrigin: Item.Center

                    Behavior on scale {
                        SpringAnimation { spring: 4.0; damping: 0.35; mass: 0.8; epsilon: 0.01 }
                    }
                    Behavior on color { ColorAnimation { duration: 150 } }

                    Connections {
                        target: root
                        function onValueChanged() {
                            valText.scale = 1.15
                            popTimer.restart()
                        }
                    }

                    Timer {
                        id: popTimer
                        interval: 100
                        onTriggered: valText.scale = 1.0
                    }
                }
            }

            // + Increment button
            Rectangle {
                id: plusBtn
                width: 28
                height: parent.height
                color: plusArea.pressed ? "#1E293B" : (plusArea.containsMouse ? "#1A2234" : "transparent")
                Behavior on color { ColorAnimation { duration: 100 } }

                // Left divider
                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.topMargin: 6
                    anchors.bottomMargin: 6
                    width: 1
                    color: "#283042"
                }

                Text {
                    anchors.centerIn: parent
                    text: "+"
                    font.pixelSize: 15
                    font.weight: Font.Light
                    color: plusArea.pressed ? root.accentColor
                         : (plusArea.containsMouse ? "#CBD5E1" : "#64748B")
                    scale: plusArea.pressed ? 0.82 : (plusArea.containsMouse ? 1.18 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale {
                        SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.01 }
                    }
                    Behavior on color { ColorAnimation { duration: 100 } }
                }

                MouseArea {
                    id: plusArea
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: root.enabled
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        var next = Math.min(root.to, root.value + root.stepSize)
                        if (next !== root.value) {
                            root.value = next
                            root.valueModified(next)
                        }
                    }
                    // Hold-to-repeat
                    onPressAndHold: repeatTimer2.start()
                    onReleased: repeatTimer2.stop()

                    Timer {
                        id: repeatTimer2
                        interval: 120
                        repeat: true
                        onTriggered: {
                            var next = Math.min(root.to, root.value + root.stepSize)
                            if (next !== root.value) {
                                root.value = next
                                root.valueModified(next)
                            } else {
                                repeatTimer2.stop()
                            }
                        }
                    }
                }
            }
        }
    }
}
