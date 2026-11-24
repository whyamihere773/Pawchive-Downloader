import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

CardSection {
    id: guardCard
    objectName: "pawchiveRateGuardCard"
    required property var view

    readonly property var bridge: guardCard.view ? guardCard.view.bridge : null
    readonly property var info: (bridge && bridge.pawchiveRateGuardInfo) ? bridge.pawchiveRateGuardInfo : ({})
    readonly property string curMode: bridge ? String(bridge.pawchiveRateGuardMode || "smart") : "smart"
    readonly property string curFooterStyle: bridge ? String(bridge.pawchiveRateGuardFooterStyle || "micro") : "micro"
    readonly property string guardState: String(info.state || "cruise")
    readonly property real dangerRpm: Number(info.danger_rpm || 0)
    property bool justRecalibrated: false

    Layout.fillWidth: true
    title: guardCard.view.tr("card_pawchive_rate_guard", "Pawchive Rate Guard & Anti-Ban Calibration")
    iconText: "🛡️"
    entranceOffsetY: guardCard.view.tabEntranceOffsetY * 1.35
    entranceOpacity: guardCard.view.tabEntranceOpacity

    Timer {
        id: recalResetTimer
        interval: 1700
        onTriggered: guardCard.justRecalibrated = false
    }

    ColumnLayout {
        width: parent.width
        spacing: 11

        // 1. Live Speedometer + Learned Ceiling + Recalibrate Action Row
        Flow {
            width: parent.width
            Layout.fillWidth: true
            spacing: 8

            // Live State & RPM Readout Pill
            Rectangle {
                height: 28
                implicitWidth: Math.min(guardCard.width - 16, statusRow.implicitWidth + 18)
                radius: 7
                color: guardCard.guardState === "cooldown" || guardCard.guardState === "paused_shield"
                       ? "#2E1418"
                       : (guardCard.guardState === "probing" || guardCard.guardState === "recovering" ? "#2E2414" : "#0F241D")
                border.color: guardCard.guardState === "cooldown" || guardCard.guardState === "paused_shield"
                              ? "#EF4444"
                              : (guardCard.guardState === "probing" || guardCard.guardState === "recovering" ? "#F59E0B" : "#10B981")
                border.width: 1

                Behavior on color { ColorAnimation { duration: 160 } }
                Behavior on border.color { ColorAnimation { duration: 160 } }

                RowLayout {
                    id: statusRow
                    anchors.centerIn: parent
                    spacing: 6

                    Text {
                        text: guardCard.guardState === "cooldown" || guardCard.guardState === "paused_shield"
                              ? "⏳"
                              : (guardCard.guardState === "probing" || guardCard.guardState === "recovering" ? "🟡" : "🟢")
                        font.pixelSize: 10
                    }

                    Text {
                        text: String(guardCard.info.status_text || "Cruise (Pace 26/min)")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: guardCard.guardState === "cooldown" || guardCard.guardState === "paused_shield"
                               ? "#FCA5A5"
                               : (guardCard.guardState === "probing" || guardCard.guardState === "recovering" ? "#FDE68A" : "#6EE7B7")
                        elide: Text.ElideRight
                    }
                }
            }

            // Learned 429 Ceiling Badge (shown when a ceiling was learned in this or a past session)
            Rectangle {
                readonly property int dangerStreams: Number(guardCard.info.danger_streams || 0)
                visible: guardCard.dangerRpm > 0 || dangerStreams > 0
                height: 28
                implicitWidth: ceilTxt.implicitWidth + 16
                radius: 7
                color: "#1B1628"
                border.color: "#8B5CF6"
                border.width: 1

                Text {
                    id: ceilTxt
                    anchors.centerIn: parent
                    text: {
                        var parts = []
                        if (guardCard.dangerRpm > 0) parts.push(guardCard.dangerRpm.toFixed(1) + "/min")
                        if (parent.dangerStreams > 0) parts.push(parent.dangerStreams + " conn")
                        return "⚡ Learned 429 Threshold: " + parts.join(" • ")
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    color: "#DDD6FE"
                }
            }

            // 1-Click Recalibrate Button
            Rectangle {
                id: recalBtn
                objectName: "recalibrateRateGuardBtn"
                height: 28
                implicitWidth: recalRow.implicitWidth + 18
                radius: 7
                color: guardCard.justRecalibrated
                       ? "#064E3B"
                       : (recalMouse.containsMouse ? "#1E293B" : "#141B29")
                border.color: guardCard.justRecalibrated ? "#10B981" : (recalMouse.containsMouse ? "#38BDF8" : "#334155")
                border.width: 1

                Springy { hover: recalMouse.containsMouse; pressed: recalMouse.pressed }

                Row {
                    id: recalRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text {
                        text: guardCard.justRecalibrated ? "✓" : "🔄"
                        font.pixelSize: 11
                        color: guardCard.justRecalibrated ? "#6EE7B7" : "#7DD3FC"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: guardCard.justRecalibrated ? "Recalibrated!" : "Recalibrate"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: guardCard.justRecalibrated ? "#A7F3D0" : "#E2E8F0"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: recalMouse
                    objectName: "recalibrateRateGuardMouse"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Clear saved 429 thresholds and smoothly re-measure your safe Pawchive speed from scratch"
                    onClicked: {
                        if (guardCard.bridge && guardCard.bridge.recalibratePawchiveRateGuard) {
                            guardCard.bridge.recalibratePawchiveRateGuard()
                            guardCard.justRecalibrated = true
                            recalResetTimer.restart()
                        }
                    }
                }
            }
        }

        // 2. Mode Selector Pills (Smart Auto | Cautious Ban-Safe | Custom Manual)
        Flow {
            width: parent.width
            Layout.fillWidth: true
            spacing: 8

            Repeater {
                model: [
                    {
                        key: "smart",
                        icon: "⚡",
                        label: "Smart Auto (Recommended)",
                        tip: "Two-layer per-node + rolling hourly pacing. Dynamically scales up to 5 connections when clean, glides into steady Quota Cruise if hourly limits tighten, and self-heals upward automatically."
                    },
                    {
                        key: "cautious",
                        icon: "🛡️",
                        label: "Cautious (Ban-Safe)",
                        tip: "Extra conservative (~75% of learned limit, max 2 streams, longer quiet cooldowns) for maximum IP safety during multi-hour sessions."
                    },
                    {
                        key: "manual",
                        icon: "🎛️",
                        label: "Custom Manual",
                        tip: "Set your own exact files-per-minute target, stream limit, and 429 quiet cooldown while keeping the Ban-Shield auto-pause active."
                    }
                ]

                delegate: Rectangle {
                    readonly property bool active: guardCard.curMode === modelData.key
                    objectName: "rateGuardMode_" + modelData.key
                    height: 30
                    width: mRow.implicitWidth + 18
                    radius: 7
                    color: active
                           ? (modelData.key === "cautious" ? "#064E3B" : (modelData.key === "manual" ? "#3B1D5E" : "#162A45"))
                           : (mMouse.containsMouse ? "#1A2336" : "#0F1522")
                    border.color: active
                                  ? (modelData.key === "cautious" ? "#34D399" : (modelData.key === "manual" ? "#A78BFA" : "#38BDF8"))
                                  : (mMouse.containsMouse ? "#334155" : "#1E293B")
                    border.width: active ? 1.5 : 1

                    Springy { hover: mMouse.containsMouse; pressed: mMouse.pressed }

                    Row {
                        id: mRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: modelData.icon; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: modelData.label
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: active ? Font.Bold : Font.Medium
                            color: active ? "#F8FAFC" : "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: mMouse
                        objectName: "rateGuardModeMouse_" + modelData.key
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: modelData.tip
                        onClicked: {
                            if (guardCard.bridge) {
                                guardCard.bridge.pawchiveRateGuardMode = modelData.key
                            }
                        }
                    }
                }
            }
        }

        // 3. Expandable Custom Manual Sliders (Spring-animated reveal)
        Rectangle {
            id: manualPanel
            readonly property bool open: guardCard.curMode === "manual"
            Layout.fillWidth: true
            Layout.preferredHeight: open ? (manualCol.implicitHeight + 20) : 0
            visible: opacity > 0.01
            opacity: open ? 1.0 : 0.0
            clip: true
            radius: 8
            color: "#0B101B"
            border.color: "#2E3B55"
            border.width: 1

            Behavior on Layout.preferredHeight {
                SpringAnimation { spring: 4.2; damping: 0.36; mass: 0.85 }
            }
            Behavior on opacity { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }

            ColumnLayout {
                id: manualCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 10
                spacing: 8

                // Slider 1: Target Requests / Minute
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Text {
                        text: "Target Pace (files/min):"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#CBD5E1"
                        Layout.preferredWidth: 155
                    }
                    Slider {
                        id: rpmSlider
                        objectName: "pawchiveManualRpmSlider"
                        Layout.fillWidth: true
                        from: 8
                        to: 60
                        stepSize: 1
                        value: guardCard.bridge ? guardCard.bridge.pawchiveManualRpm : 24
                        onMoved: if (guardCard.bridge) guardCard.bridge.pawchiveManualRpm = Math.round(value)
                    }
                    Rectangle {
                        implicitWidth: 68
                        height: 22
                        radius: 11
                        color: "#152238"
                        border.color: "#38BDF8"
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: Math.round(rpmSlider.value) + "/min"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.bold: true
                            color: "#7DD3FC"
                        }
                    }
                }

                // Slider 2: Max Simultaneous Pawchive Streams
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Text {
                        text: "Max Pawchive Streams:"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#CBD5E1"
                        Layout.preferredWidth: 155
                    }
                    Slider {
                        id: streamsSlider
                        objectName: "pawchiveManualStreamsSlider"
                        Layout.fillWidth: true
                        from: 1
                        to: 6
                        stepSize: 1
                        value: guardCard.bridge ? guardCard.bridge.pawchiveManualStreams : 3
                        onMoved: if (guardCard.bridge) guardCard.bridge.pawchiveManualStreams = Math.round(value)
                    }
                    Rectangle {
                        implicitWidth: 68
                        height: 22
                        radius: 11
                        color: "#152238"
                        border.color: "#38BDF8"
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: Math.round(streamsSlider.value) + "T"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.bold: true
                            color: "#7DD3FC"
                        }
                    }
                }

                // Slider 3: 429 Quiet Cooldown Seconds
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Text {
                        text: "429 Quiet Cooldown:"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#CBD5E1"
                        Layout.preferredWidth: 155
                    }
                    Slider {
                        id: cdSlider
                        objectName: "pawchiveManualCooldownSlider"
                        Layout.fillWidth: true
                        from: 15
                        to: 180
                        stepSize: 5
                        value: guardCard.bridge ? guardCard.bridge.pawchiveManualCooldown : 40
                        onMoved: if (guardCard.bridge) guardCard.bridge.pawchiveManualCooldown = Math.round(value)
                    }
                    Rectangle {
                        implicitWidth: 68
                        height: 22
                        radius: 11
                        color: "#152238"
                        border.color: "#38BDF8"
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: Math.round(cdSlider.value) + "s"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.bold: true
                            color: "#7DD3FC"
                        }
                    }
                }
            }
        }

        // 4. Bottom Status Bar Display Style Selector
        Flow {
            width: parent.width
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "Bottom Bar Badge:"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#94A3B8"
                height: 26
                verticalAlignment: Text.AlignVCenter
            }

            Repeater {
                model: [
                    { key: "full", label: "Full Length", tip: "Show full unshortened state, pace, connections, and 60-minute request count in the bottom bar." },
                    { key: "micro", label: "Compact (Default)", tip: "Single compact badge combining live pace, connections, and 60-minute count." },
                    { key: "minimal", label: "Minimal", tip: "Compact icon + pace and connections only (full details on hover or click)." },
                    { key: "tiny", label: "Tiny Dot", tip: "Ultra-small colored status dot + live pace." },
                    { key: "hidden", label: "Hidden", tip: "Hide the Rate Guard badge from the bottom bar." }
                ]

                delegate: Rectangle {
                    readonly property bool active: guardCard.curFooterStyle === modelData.key
                    objectName: "rateGuardFooterStyle_" + modelData.key
                    height: 26
                    width: fsTxt.implicitWidth + 16
                    radius: 6
                    color: active ? "#1E1B38" : (fsMouse.containsMouse ? "#1A2336" : "#0F1522")
                    border.color: active ? "#A78BFA" : (fsMouse.containsMouse ? "#334155" : "#1E293B")
                    border.width: active ? 1.5 : 1

                    Springy { hover: fsMouse.containsMouse; pressed: fsMouse.pressed }

                    Text {
                        id: fsTxt
                        anchors.centerIn: parent
                        text: modelData.label
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: active ? Font.Bold : Font.Medium
                        color: active ? "#DDD6FE" : "#94A3B8"
                    }

                    MouseArea {
                        id: fsMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: modelData.tip
                        onClicked: if (guardCard.bridge) guardCard.bridge.pawchiveRateGuardFooterStyle = modelData.key
                    }
                }
            }
        }
    }
}
