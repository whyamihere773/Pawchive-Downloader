import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Always-visible Pawchive Rate Guard status pill + unshortened hover tooltip + click quick-popover
Item {
    id: root
    objectName: "pawchiveRateGuardFooterPill"
    property var bridge: null

    readonly property string footerStyle: root.bridge ? String(root.bridge.pawchiveRateGuardFooterStyle || "micro") : "micro"
    readonly property bool shown: root.footerStyle !== "hidden"
    readonly property var info: (root.bridge && root.bridge.pawchiveRateGuardInfo) ? root.bridge.pawchiveRateGuardInfo : ({})
    readonly property string curMode: root.bridge ? String(root.bridge.pawchiveRateGuardMode || "smart") : "smart"
    readonly property string guardState: String(root.info.state || "cruise")
    readonly property bool quotaCruise: Boolean(root.info.quota_cruise)
    readonly property bool isDownloading: root.bridge ? Boolean(root.bridge.isDownloading) : false

    readonly property real liveRpm: Number(root.info.live_rpm || 0)
    readonly property real effRpm: Number(root.info.effective_rpm || 26)
    readonly property real targetRpm: Number(root.info.target_rpm || 26)
    readonly property real dangerRpm: Number(root.info.danger_rpm || 0)
    readonly property int maxStreams: Number(root.info.max_streams !== undefined ? root.info.max_streams : 3)
    readonly property int nodeStreams: Number(root.info.node_streams !== undefined ? root.info.node_streams : 2)
    readonly property int targetStreams: Number(root.info.target_streams !== undefined ? root.info.target_streams : 3)
    readonly property int dangerStreams: Number(root.info.danger_streams || 0)
    readonly property real cdRem: Number(root.info.cooldown_remaining || 0)
    readonly property int waveNum: Number(root.info.wave || 0)
    readonly property int recClean: Number(root.info.recovery_clean_files || 0)
    readonly property real sent5m: Number(root.info.sent_5m || 0)
    readonly property real sent60m: Number(root.info.sent_60m || 0)
    readonly property int waves5m: Number(root.info.waves_5m || 0)
    readonly property int waves60m: Number(root.info.waves_60m || 0)

    readonly property bool isCooling: root.guardState === "cooldown" || root.guardState === "paused_shield" || root.cdRem > 0.05
    readonly property bool isCaution: !root.isCooling && (root.guardState === "probing" || root.guardState === "recovering")

    visible: opacity > 0.01
    opacity: root.shown ? 1.0 : 0.0
    implicitHeight: 24
    implicitWidth: root.shown ? badgeCluster.implicitWidth : 0

    Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
    Behavior on implicitWidth { SpringAnimation { spring: 4.4; damping: 0.38; mass: 0.85 } }

    // Format integer with full thousand separators (never shortened for tooltips/full view)
    function fmtFullInt(n) {
        var v = Math.round(Number(n || 0))
        return v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")
    }

    // Compact k-notation used ONLY inside the compact 'micro' badge
    function fmtCompact60m(n) {
        var v = Math.round(Number(n || 0))
        if (v >= 1000) return (v / 1000.0).toFixed(1) + "k/h"
        return v + "/h"
    }

    function fmtPaceShort(val) {
        var v = Number(val || 0)
        return (v < 10.0 && Math.abs(v - Math.round(v)) >= 0.05) ? v.toFixed(1) : Math.round(v).toString()
    }

    readonly property string modeFullLabel: {
        if (root.curMode === "cautious") return "Cautious (Ban-Safe)"
        if (root.curMode === "manual") return "Custom Manual"
        return "Smart Auto (Recommended)"
    }

    readonly property string stateFullLabel: {
        if (root.guardState === "paused_shield") return "Ban-Shield Auto-Paused (3 failed post-cooldown probes)"
        if (root.isCooling) return "Quiet Cooldown (" + root.cdRem.toFixed(1) + " seconds remaining, Wave " + Math.max(1, root.waveNum) + ")"
        if (root.guardState === "probing") return "Post-Cooldown Probe (1 test connection)"
        if (root.guardState === "recovering") return "Smooth Recovery (" + root.recClean + " of 15 clean files verified)"
        if (root.quotaCruise) return "Quota Cruise (Steady pace underneath hourly server refill)"
        if (!root.isDownloading && root.liveRpm <= 0.05) return "Idle & Ready"
        return "Cruise (Healthy)"
    }

    readonly property string pillIcon: {
        if (root.isCooling) return "⏳"
        if (root.isCaution) return "🟡"
        if (root.quotaCruise) return "🌊"
        return "🛡️"
    }

    readonly property color dotColor: {
        if (root.isCooling) return "#EF4444"
        if (root.isCaution) return "#FBBF24"
        if (root.quotaCruise) return "#38BDF8"
        if (!root.isDownloading && root.liveRpm <= 0.05) return "#60A5FA"
        return "#34D399"
    }

    readonly property color pillBgColor: {
        if (root.isCooling) return "#2E1418"
        if (root.isCaution) return "#2E2414"
        if (root.quotaCruise) return "#0E2233"
        if (!root.isDownloading && root.liveRpm <= 0.05) return "#121926"
        return "#0F241D"
    }

    readonly property color pillBorderColor: {
        if (root.isCooling) return "#EF4444"
        if (root.isCaution) return "#F59E0B"
        if (root.quotaCruise) return "#38BDF8"
        if (!root.isDownloading && root.liveRpm <= 0.05) return "#283952"
        return "#10B981"
    }

    readonly property color pillTextColor: {
        if (root.isCooling) return "#FCA5A5"
        if (root.isCaution) return "#FDE68A"
        if (root.quotaCruise) return "#7DD3FC"
        if (!root.isDownloading && root.liveRpm <= 0.05) return "#93C5FD"
        return "#6EE7B7"
    }

    // Complete, unshortened multi-line tooltip text
    readonly property string fullTooltipText: {
        var lines = []
        lines.push("🛡️ Pawchive Rate Guard — " + root.modeFullLabel)
        lines.push("Status: " + root.stateFullLabel)
        lines.push("Live Pace: " + root.liveRpm.toFixed(1) + " files/minute  •  Target Cap: " + root.effRpm.toFixed(1) + " files/minute")
        lines.push("Connections: " + root.maxStreams + " max total  •  " + root.nodeStreams + " max per storage server (Target: " + root.targetStreams + " connections)")
        lines.push("Pawchive Requests Sent: " + root.fmtFullInt(root.sent5m) + " in last 5 minutes  •  " + root.fmtFullInt(root.sent60m) + " in last 60 minutes")
        lines.push("Rate-Limit (429) Hits: " + root.waves5m + " in last 5 minutes  •  " + root.waves60m + " in last 60 minutes")
        if (root.dangerRpm > 0 || root.dangerStreams > 0) {
            var dParts = []
            if (root.dangerRpm > 0) dParts.push(root.dangerRpm.toFixed(1) + " files/minute")
            if (root.dangerStreams > 0) dParts.push(root.dangerStreams + " connections")
            lines.push("Learned 429 Threshold: " + dParts.join("  •  "))
        } else {
            lines.push("Learned 429 Threshold: None triggered (auto-calibrating smoothly)")
        }
        lines.push("Click to switch mode, change badge layout, or recalibrate")
        return lines.join("\n")
    }

    // Keep cooldown countdown and rolling 1m/60m decay live even while paused or idle
    Timer {
        interval: 1000
        repeat: true
        running: root.shown && (root.isCooling || root.liveRpm > 0 || guardPopup.opened)
        onTriggered: {
            if (root.bridge && root.bridge.refreshPawchiveRateGuard) {
                root.bridge.refreshPawchiveRateGuard()
            }
        }
    }

    Timer {
        id: recalFlashTimer
        interval: 1200
        onTriggered: root.justRecalibrated = false
    }
    property bool justRecalibrated: false

    RowLayout {
        id: badgeCluster
        anchors.verticalCenter: parent.verticalCenter
        spacing: 6

        // Main Rate Guard Badge (adapts cleanly to full / micro / minimal / tiny)
        Rectangle {
            id: mainBadge
            objectName: "pawchiveFooterMainBadge"
            implicitHeight: 22
            implicitWidth: mainBadgeRow.implicitWidth + 16
            radius: 5
            color: root.pillBgColor
            border.color: pillMouse.containsMouse ? Qt.lighter(root.pillBorderColor, 1.2) : root.pillBorderColor
            border.width: 1

            scale: pillMouse.pressed ? 0.94 : (pillMouse.containsMouse ? 1.03 : 1.0)
            transformOrigin: Item.Center

            Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.34; mass: 0.9 } }
            Behavior on implicitWidth { SpringAnimation { spring: 4.4; damping: 0.40; mass: 0.85 } }
            Behavior on color { ColorAnimation { duration: 160 } }
            Behavior on border.color { ColorAnimation { duration: 160 } }

            Row {
                id: mainBadgeRow
                anchors.centerIn: parent
                spacing: 5

                // Ultra-Tiny uses a crisp status dot; other modes show state emoji
                Rectangle {
                    visible: root.footerStyle === "tiny"
                    width: 7
                    height: 7
                    radius: 3.5
                    color: root.dotColor
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    visible: root.footerStyle !== "tiny"
                    text: root.pillIcon
                    font.pixelSize: 10
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    objectName: "pawchiveFooterPrimaryText"
                    font.family: root.footerStyle === "full" ? "Segoe UI, sans-serif" : "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    color: root.pillTextColor
                    anchors.verticalCenter: parent.verticalCenter
                    text: {
                        var liveS = root.fmtPaceShort(root.liveRpm)
                        var capS = root.fmtPaceShort(root.effRpm)
                        var cdS = Math.max(1, Math.round(root.cdRem)) + "s"
                        var modeShort = root.curMode === "cautious" ? "Cautious" : (root.curMode === "manual" ? "Manual" : "Smart")

                        if (root.footerStyle === "full") {
                            if (root.guardState === "paused_shield") return "Ban-Shield Paused • 0 conn"
                            if (root.isCooling) return "Quiet Cooldown: " + cdS + " • 0 conn (wave " + Math.max(1, root.waveNum) + ")"
                            if (root.guardState === "probing") return "Probing: " + root.effRpm.toFixed(1) + " req/min • 1 conn"
                            if (root.guardState === "recovering") return "Recovering (" + root.recClean + "/15): " + root.liveRpm.toFixed(1) + "/" + root.effRpm.toFixed(1) + " req/min • " + root.maxStreams + " conn"
                            if (root.quotaCruise) return "Quota Cruise: " + root.liveRpm.toFixed(1) + "/" + root.effRpm.toFixed(1) + " req/min • " + root.maxStreams + " conn"
                            if (!root.isDownloading && root.liveRpm <= 0.05) return "Pawchive: " + modeShort + " • Cap " + root.effRpm.toFixed(1) + "/min • " + root.maxStreams + " conn"
                            return "Cruise: " + root.liveRpm.toFixed(1) + "/" + root.effRpm.toFixed(1) + " req/min • " + root.maxStreams + " conn"
                        }

                        if (root.footerStyle === "minimal") {
                            if (root.guardState === "paused_shield") return "Shield Paused"
                            if (root.isCooling) return "CD " + cdS + " · 0T"
                            if (root.guardState === "recovering") return capS + "/m · " + root.maxStreams + "T (" + root.recClean + "/15)"
                            if (root.quotaCruise) return capS + "/m · " + root.maxStreams + "T"
                            if (!root.isDownloading && root.liveRpm <= 0.05) return capS + "/m · " + root.maxStreams + "T"
                            return liveS + "/" + capS + "/m · " + root.maxStreams + "T"
                        }

                        if (root.footerStyle === "tiny") {
                            if (root.isCooling) return cdS
                            if (!root.isDownloading && root.liveRpm <= 0.05) return capS + "/m"
                            return (root.quotaCruise ? capS : liveS) + "/m · " + root.maxStreams + "T"
                        }

                        // Default "micro": unified single compact badge
                        if (root.guardState === "paused_shield") return "Paused · 0T"
                        if (root.isCooling) return cdS + " · 0T"
                        if (!root.isDownloading && root.liveRpm <= 0.05) return capS + "/m · " + root.maxStreams + "T"
                        return (root.quotaCruise ? capS : liveS) + "/m · " + root.maxStreams + "T"
                    }
                }

                // Inline divider + secondary segment inside Unified Micro mode
                Text {
                    visible: root.footerStyle === "micro"
                    text: "|"
                    font.family: "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 10
                    color: "#475569"
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    visible: root.footerStyle === "micro"
                    font.family: "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 10
                    font.weight: Font.Medium
                    color: root.guardState === "recovering" ? "#FDE68A" : "#C4B5FD"
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.guardState === "recovering"
                          ? (root.recClean + "/15")
                          : root.fmtCompact60m(root.sent60m)
                }
            }
        }

        // Separate Full-Length 60-Minute Counter Pill (shown only when footerStyle === "full")
        Rectangle {
            visible: root.footerStyle === "full"
            implicitHeight: 22
            implicitWidth: fullHourlyRow.implicitWidth + 16
            radius: 5
            color: "#161E2E"
            border.color: pillMouse.containsMouse ? "#38BDF8" : "#26334D"
            border.width: 1

            Behavior on border.color { ColorAnimation { duration: 150 } }

            Row {
                id: fullHourlyRow
                anchors.centerIn: parent
                spacing: 4
                Text { text: "📊"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: root.fmtFullInt(root.sent60m) + " req / 60m"
                    font.family: "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 10
                    font.weight: Font.Medium
                    color: "#C4B5FD"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
    }

    MouseArea {
        id: pillMouse
        objectName: "pawchiveFooterPillMouse"
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            if (guardPopup.opened) guardPopup.close()
            else guardPopup.open()
        }
    }

    // Custom dark multi-line hover tooltip showing 100% unshortened data
    ToolTip {
        id: fullHoverTip
        objectName: "pawchiveFooterFullToolTip"
        parent: mainBadge
        visible: pillMouse.containsMouse && !guardPopup.opened
        delay: 180
        timeout: -1
        padding: 10
        y: -implicitHeight - 8

        contentItem: Text {
            text: root.fullTooltipText
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            lineHeight: 1.28
            color: "#F1F5F9"
        }

        background: Rectangle {
            radius: 7
            color: "#0B101B"
            border.color: "#38BDF8"
            border.width: 1
        }
    }

    // Spring-Animated Quick Control & Full Telemetry Popover
    Popup {
        id: guardPopup
        objectName: "pawchiveFooterQuickPopup"
        parent: mainBadge
        x: Math.min(0, mainBadge.width - width)
        y: -height - 8
        width: 318
        padding: 11
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 140; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.88; to: 1.0; spring: 4.5; damping: 0.36; mass: 0.85 }
            }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 110; easing.type: Easing.InCubic }
        }

        background: Rectangle {
            radius: 9
            color: "#0D121D"
            border.color: "#2B3B55"
            border.width: 1
        }

        contentItem: ColumnLayout {
            spacing: 8

            // Header: State + Recalibrate
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Text {
                    text: root.pillIcon + "  Pawchive Rate Guard"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    color: "#F8FAFC"
                    Layout.fillWidth: true
                }

                Rectangle {
                    height: 22
                    implicitWidth: popRecalTxt.implicitWidth + 14
                    radius: 5
                    color: root.justRecalibrated ? "#064E3B" : (popRecalMouse.containsMouse ? "#1E293B" : "#141B29")
                    border.color: root.justRecalibrated ? "#10B981" : (popRecalMouse.containsMouse ? "#38BDF8" : "#334155")
                    border.width: 1
                    scale: popRecalMouse.pressed ? 0.93 : 1.0
                    Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35 } }

                    Text {
                        id: popRecalTxt
                        anchors.centerIn: parent
                        text: root.justRecalibrated ? "✓ Reset!" : "🔄 Reset"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        color: root.justRecalibrated ? "#A7F3D0" : "#E2E8F0"
                    }

                    MouseArea {
                        id: popRecalMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.bridge && root.bridge.recalibratePawchiveRateGuard) {
                                root.bridge.recalibratePawchiveRateGuard()
                                root.justRecalibrated = true
                                recalFlashTimer.restart()
                            }
                        }
                    }
                }
            }

            // Full Unshortened Telemetry Readout Box
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: teleCol.implicitHeight + 14
                radius: 6
                color: "#121928"
                border.color: "#1E293B"
                border.width: 1

                ColumnLayout {
                    id: teleCol
                    anchors.fill: parent
                    anchors.margins: 7
                    spacing: 3

                    Text {
                        text: root.stateFullLabel
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: root.pillTextColor
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                    Text {
                        text: "Pace: " + root.liveRpm.toFixed(1) + " / " + root.effRpm.toFixed(1) + " files/min  •  Conn: " + root.maxStreams + " (" + root.nodeStreams + "/server)"
                        font.family: "Cascadia Code, Consolas, monospace"
                        font.pixelSize: 10
                        color: "#CBD5E1"
                    }
                    Text {
                        text: "Requests: " + root.fmtFullInt(root.sent5m) + " (5m)  •  " + root.fmtFullInt(root.sent60m) + " (60m)"
                        font.family: "Cascadia Code, Consolas, monospace"
                        font.pixelSize: 10
                        color: "#C4B5FD"
                    }
                    Text {
                        text: "429 Hits: " + root.waves5m + " (5m)  •  " + root.waves60m + " (60m)"
                              + (root.dangerRpm > 0 ? ("  •  Ceil: " + root.dangerRpm.toFixed(1) + "/m") : "")
                        font.family: "Cascadia Code, Consolas, monospace"
                        font.pixelSize: 10
                        color: "#94A3B8"
                    }
                }
            }

            // Mode Switcher
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text {
                    text: "Protection Mode:"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#94A3B8"
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 5
                    Repeater {
                        model: [
                            { key: "smart", label: "⚡ Smart Auto" },
                            { key: "cautious", label: "🛡️ Cautious" },
                            { key: "manual", label: "🎛️ Manual" }
                        ]
                        delegate: Rectangle {
                            readonly property bool active: root.curMode === modelData.key
                            Layout.fillWidth: true
                            height: 24
                            radius: 5
                            color: active ? "#162A45" : (pmMouse.containsMouse ? "#1A2336" : "#0F1522")
                            border.color: active ? "#38BDF8" : "#1E293B"
                            border.width: active ? 1.5 : 1
                            scale: pmMouse.pressed ? 0.94 : 1.0
                            Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35 } }

                            Text {
                                anchors.centerIn: parent
                                text: modelData.label
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: active ? Font.Bold : Font.Medium
                                color: active ? "#F8FAFC" : "#94A3B8"
                            }
                            MouseArea {
                                id: pmMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (root.bridge) root.bridge.pawchiveRateGuardMode = modelData.key
                            }
                        }
                    }
                }
            }

            // Footer Badge Layout Switcher
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text {
                    text: "Footer Badge Style:"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#94A3B8"
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Repeater {
                        model: [
                            { key: "full", label: "Full" },
                            { key: "micro", label: "Compact" },
                            { key: "minimal", label: "Minimal" },
                            { key: "tiny", label: "Tiny" },
                            { key: "hidden", label: "Hide" }
                        ]
                        delegate: Rectangle {
                            readonly property bool active: root.footerStyle === modelData.key
                            Layout.fillWidth: true
                            height: 22
                            radius: 5
                            color: active ? "#1E1B38" : (stMouse.containsMouse ? "#1A2336" : "#0F1522")
                            border.color: active ? "#A78BFA" : "#1E293B"
                            border.width: active ? 1.5 : 1
                            scale: stMouse.pressed ? 0.94 : 1.0
                            Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35 } }

                            Text {
                                anchors.centerIn: parent
                                text: modelData.label
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: active ? Font.Bold : Font.Medium
                                color: active ? "#DDD6FE" : "#94A3B8"
                            }
                            MouseArea {
                                id: stMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (root.bridge) root.bridge.pawchiveRateGuardFooterStyle = modelData.key
                            }
                        }
                    }
                }
            }
        }
    }
}
