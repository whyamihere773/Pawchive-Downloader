import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// 4. Bottom Status & Progress Footer (the Gallery shows a small download chip instead)
Item {
    id: footerProgressArea
    required property var window
    Layout.fillWidth: true
    Layout.preferredHeight: 44 * footerProgressArea.window.chromeProgress
    visible: footerProgressArea.window.chromeProgress > 0
    opacity: footerProgressArea.window.chromeOpacity
    clip: footerProgressArea.window.chromeMoving

    Rectangle {
        width: parent.width
        height: 44
        anchors.top: parent.top
        transform: Translate { y: 16 * footerProgressArea.window.chromeSlide }
        color: "#0B0D12"
        border.color: "#1E2330"
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 12

            // Error Indicator if any
            Rectangle {
                width: 20; height: 20; radius: 10
                color: "#EF4444"
                visible: appBridge ? appBridge.hasError : false
                Text { anchors.centerIn: parent; text: "!"; color: "#FFFFFF"; font.bold: true }
            }

            // Overall Progress Bar (Full-Width with Inline Telemetry Badges)
            ProgressBarFancy {
                Layout.fillWidth: true
                progressPercent: appBridge ? appBridge.overallProgress : 0
                statusText: appBridge ? appBridge.statusText : "Progress: Idle"
                filesText: appBridge ? appBridge.filesCountText : ""
                speedText: appBridge ? appBridge.currentSpeed : "0 KB/s"
                etaText: appBridge ? appBridge.etaText : "--"
                elapsedText: appBridge ? appBridge.elapsedTimeText : "0s"
                savedText: appBridge ? appBridge.savedBytesText : "0 MB"
                active: appBridge ? appBridge.isDownloading : false
            }

            // Live Adaptive Health & Scaling Pill (Feature 5) with Spring Entrance
            Rectangle {
                id: adaptivePill
                implicitHeight: 24
                implicitWidth: adaptiveRow.implicitWidth + 24
                radius: 6
                visible: opacity > 0
                opacity: (appBridge && appBridge.isDownloading && appBridge.adaptiveThreading && appBridge.adaptiveStatusText.length > 0) ? 1.0 : 0.0
                scale: opacity > 0 ? 1.0 : 0.6
                transformOrigin: Item.Center

                Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                Behavior on scale { NumberAnimation { duration: 240; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                color: {
                    if (!appBridge) return "#161E2E"
                    if (appBridge.adaptiveState === "cooldown") return "#2E1418"
                    if (appBridge.adaptiveState === "scaling") return "#2E2414"
                    return "#122820"
                }
                border.color: {
                    if (!appBridge) return "#1E293B"
                    if (appBridge.adaptiveState === "cooldown") return "#EF4444"
                    if (appBridge.adaptiveState === "scaling") return "#FBBF24"
                    return "#10B981"
                }
                border.width: 1

                Behavior on color { ColorAnimation { duration: 150 } }
                Behavior on border.color { ColorAnimation { duration: 150 } }

                Row {
                    id: adaptiveRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        text: {
                            if (!appBridge) return "⚡"
                            if (appBridge.adaptiveState === "cooldown") return "⏳"
                            if (appBridge.adaptiveState === "scaling") return "⚡"
                            return "✔"
                        }
                        font.pixelSize: 10
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        id: adaptivePillText
                        text: appBridge ? appBridge.adaptiveStatusText : ""
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        anchors.verticalCenter: parent.verticalCenter
                        color: {
                            if (!appBridge) return "#38BDF8"
                            if (appBridge.adaptiveState === "cooldown") return "#FCA5A5"
                            if (appBridge.adaptiveState === "scaling") return "#FCD34D"
                            return "#6EE7B7"
                        }
                    }
                }
            }

            // Quick session state badge
            Rectangle {
                height: 22
                width: Math.max(90, sessStateText.implicitWidth + 12)
                radius: 4
                color: "#181B22"
                border.color: "#282E3D"
                border.width: 1
                visible: appBridge ? appBridge.hasSavedSession : false

                Row {
                    anchors.centerIn: parent
                    spacing: 4
                    Text { text: "📁"; font.pixelSize: 10 }
                    Text {
                        id: sessStateText
                        text: footerProgressArea.window.tr("badge_session_active", "Session Active")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#FBBF24"
                    }
                }
            }
        }
    }
}
