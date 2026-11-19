import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Unimported Pawchive content notice ──────────────────────────────────────
// Shown when Pawchive only hosts preview thumbnails for post(s) and has not
// imported the full-size files yet. Non-blocking for background downloads;
// users can permanently hide the modal while keeping the warning in the log.
Item {
    id: root

    property var bridge: null
    property bool isOpen: false
    property string title: "Not Imported on Pawchive Yet"
    property string message: ""

    signal openSettingsRequested()

    anchors.fill: parent
    z: 99991
    opacity: isOpen ? 1 : 0
    visible: opacity > 0.005
    enabled: isOpen
    Behavior on opacity { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }

    function show(heading, body) {
        if (root.bridge && root.bridge.hideUnimportedNotice)
            return
        if (root.isOpen)
            return
        title = (heading && heading.length > 0) ? heading : "Not Imported on Pawchive Yet"
        message = body || ""
        dontShowAgainCheck.checked = false
        isOpen = true
    }

    function close() {
        if (dontShowAgainCheck.checked && root.bridge) {
            root.bridge.hideUnimportedNotice = true
        }
        isOpen = false
    }

    Rectangle {
        anchors.fill: parent
        color: "#060910"
        opacity: root.isOpen ? 0.85 : 0.0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onClicked: root.close()
            onWheel: (wheel) => wheel.accepted = true
        }
    }

    Rectangle {
        width: Math.min(540, parent.width - 32)
        height: content.implicitHeight + 40
        anchors.centerIn: parent
        radius: 10
        color: "#181B22"
        border.color: "#F59E0B"
        border.width: 1
        scale: root.isOpen ? 1.0 : 0.96
        Behavior on scale { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        MouseArea { anchors.fill: parent }

        ColumnLayout {
            id: content
            anchors.centerIn: parent
            width: parent.width - 40
            spacing: 14

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                UnimportedTriangleBadge {
                    width: 28
                    height: 28
                    tooltipText: "Full-size files aren't hosted on Pawchive yet"
                }

                Text {
                    Layout.fillWidth: true
                    text: root.title
                    wrapMode: Text.Wrap
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 15
                    font.weight: 700
                    color: "#FDE68A"
                }
            }

            Text {
                Layout.fillWidth: true
                text: root.message
                wrapMode: Text.Wrap
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                lineHeight: 1.35
                color: "#CBD5E1"
            }

            StyledCheckBox {
                id: dontShowAgainCheck
                objectName: "unimportedDontShowAgainCheck"
                Layout.fillWidth: true
                Layout.topMargin: 2
                text: "Do not show this notice again (still logged in Progress Log)"
                tooltip: "Hides this pop-up in the future while keeping the warning message in your Progress Log"
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 2
                spacing: 8

                StyledButton {
                    objectName: "unimportedOpenSettingsBtn"
                    text: "Open Settings"
                    variant: "outline"
                    tooltip: "Jump to Downloader → Quick → Fallback to thumbnails if full-size missing"
                    onClicked: {
                        root.close()
                        root.openSettingsRequested()
                    }
                }

                Item { Layout.fillWidth: true }

                StyledButton {
                    objectName: "unimportedGotItBtn"
                    text: "Got it"
                    variant: "primary"
                    onClicked: root.close()
                }
            }
        }
    }
}
