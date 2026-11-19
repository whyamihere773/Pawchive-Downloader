import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Busy overlay while quiescing workers / re-scanning API / migrating .part files
Rectangle {
    id: midDownloadBusyOverlay
    required property var window
    anchors.fill: parent
    z: 9999
    visible: Boolean(appBridge && appBridge.isApplyingMidDownloadSettings)
    color: "#B8060910"

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
    }

    Rectangle {
        width: Math.min(460, parent.width - 40)
        implicitHeight: busyOverlayCol.implicitHeight + 36
        anchors.centerIn: parent
        radius: 12
        color: "#131722"
        border.color: "#38BDF8"
        border.width: 1.5

        ColumnLayout {
            id: busyOverlayCol
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                margins: 18
            }
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: "⏳"
                    font.pixelSize: 20
                }

                Text {
                    Layout.fillWidth: true
                    text: midDownloadBusyOverlay.window.tr("title_applying_mid_settings", "Updating active download...")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 15
                    font.bold: true
                    color: "#F8FAFC"
                }
            }

            Text {
                Layout.fillWidth: true
                text: (appBridge && appBridge.midDownloadApplyStatusText) ? appBridge.midDownloadApplyStatusText : "Please wait..."
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: "#CBD5E1"
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true

                Item { Layout.fillWidth: true }

                StyledButton {
                    text: midDownloadBusyOverlay.window.tr("btn_cancel", "Cancel")
                    variant: "outline"
                    implicitHeight: 32
                    onClicked: if (appBridge) appBridge.cancelMidDownloadApply()
                }
            }
        }
    }
}
