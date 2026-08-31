import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property int progressPercent: 0
    property string statusText: "Idle"
    property string filesText: ""
    property string speedText: "0 KB/s"
    property string etaText: "--"
    property string elapsedText: "0s"
    property string savedText: "0 MB"
    property bool active: false

    implicitHeight: 40
    implicitWidth: 300

    ColumnLayout {
        anchors.fill: parent
        spacing: 5

        // Top info line with inline badges
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: root.active ? "Downloading:" : root.statusText
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 11
                font.weight: Font.DemiBold
                color: root.active ? "#38BDF8" : "#94A3B8"
            }

            // Inline Telemetry Badges (Embedded directly in progress header with Spring Entrance)
            RowLayout {
                spacing: 6
                visible: opacity > 0
                opacity: root.active ? 1.0 : 0.0
                scale: root.active ? 1.0 : 0.85
                transformOrigin: Item.Left

                Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.4 } }

                // Files count badge
                Rectangle {
                    implicitHeight: 22
                    implicitWidth: fileRow.implicitWidth + 16
                    radius: 5
                    color: "#161E2E"
                    border.color: "#1E293B"
                    border.width: 1
                    visible: opacity > 0
                    opacity: root.filesText.length > 0 ? 1.0 : 0.0
                    scale: opacity > 0 ? 1.0 : 0.6
                    transformOrigin: Item.Center

                    Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: fileRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "📁"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: root.filesText
                            font.family: "Cascadia Code, Consolas, monospace"
                            font.pixelSize: 10
                            font.weight: Font.Medium
                            color: "#A78BFA"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                // Live Speed badge
                Rectangle {
                    implicitHeight: 22
                    implicitWidth: speedRow.implicitWidth + 16
                    radius: 5
                    color: "#161E2E"
                    border.color: "#1E293B"
                    border.width: 1
                    visible: opacity > 0
                    opacity: (root.speedText !== "0 KB/s" && root.speedText.length > 0) ? 1.0 : 0.0
                    scale: opacity > 0 ? 1.0 : 0.6
                    transformOrigin: Item.Center

                    Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: speedRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "⚡"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: root.speedText
                            font.family: "Cascadia Code, Consolas, monospace"
                            font.pixelSize: 10
                            font.weight: Font.Medium
                            color: "#34D399"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                // In-depth Live ETA badge
                Rectangle {
                    implicitHeight: 22
                    implicitWidth: etaRow.implicitWidth + 16
                    radius: 5
                    color: "#161E2E"
                    border.color: "#1E293B"
                    border.width: 1
                    visible: opacity > 0
                    opacity: (root.etaText !== "--" && root.etaText.length > 0) ? 1.0 : 0.0
                    scale: opacity > 0 ? 1.0 : 0.6
                    transformOrigin: Item.Center

                    Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: etaRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "⏳"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "ETA " + root.etaText
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#38BDF8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                // Elapsed time badge
                Rectangle {
                    implicitHeight: 22
                    implicitWidth: elapsedRow.implicitWidth + 16
                    radius: 5
                    color: "#161E2E"
                    border.color: "#1E293B"
                    border.width: 1
                    visible: opacity > 0
                    opacity: (root.elapsedText.length > 0 && root.elapsedText !== "0s") ? 1.0 : 0.0
                    scale: opacity > 0 ? 1.0 : 0.6
                    transformOrigin: Item.Center

                    Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: elapsedRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "⏱"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: root.elapsedText
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#A78BFA"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                // Saved data counter badge
                Rectangle {
                    implicitHeight: 22
                    implicitWidth: savedRow.implicitWidth + 16
                    radius: 5
                    color: "#161E2E"
                    border.color: "#1E293B"
                    border.width: 1
                    visible: opacity > 0
                    opacity: (root.savedText.length > 0 && root.savedText !== "0 MB") ? 1.0 : 0.0
                    scale: opacity > 0 ? 1.0 : 0.6
                    transformOrigin: Item.Center

                    Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: savedRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "💾"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: root.savedText
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#34D399"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.progressPercent + "%"
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 11
                font.weight: Font.Bold
                color: "#F1F5F9"
            }
        }

        // Progress track & fill bar
        Rectangle {
            Layout.fillWidth: true
            height: 7
            radius: 4
            color: "#14171F"
            border.color: root.active ? "#1E3A5F" : "#282E3D"
            border.width: 1
            clip: true

            Behavior on border.color {
                ColorAnimation { duration: 200 }
            }

            Rectangle {
                id: fillBar
                height: parent.height
                radius: 4
                width: Math.max(0, Math.min(parent.width, parent.width * (root.progressPercent / 100)))

                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "#0284C7" }
                    GradientStop { position: 0.5; color: "#38BDF8" }
                    GradientStop { position: 1.0; color: "#34D399" }
                }

                // Fluid physical easing
                Behavior on width {
                    NumberAnimation { duration: 280; easing.type: Easing.OutCubic }
                }
            }
        }
    }
}
