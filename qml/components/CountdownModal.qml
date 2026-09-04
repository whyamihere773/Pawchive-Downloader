import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Countdown modal — shown before any post-download system action (shutdown/restart/hibernate/sleep/close).
// Gives the user 15 seconds to cancel. Cancelling resets the action to "Do Nothing".
Item {
    id: root

    property var bridge: null
    property bool isOpen: false

    // Action label displayed to the user ("Shutdown", "Restart", etc.)
    property string actionLabel: ""

    readonly property int totalSeconds: 15

    // Internal countdown state
    property int secondsLeft: totalSeconds

    // Fill the full window so the overlay covers everything
    anchors.fill: parent
    z: 9999
    visible: isOpen

    // Reset timer whenever modal opens
    onIsOpenChanged: {
        if (isOpen) {
            secondsLeft = totalSeconds
            countdownTimer.restart()
        } else {
            countdownTimer.stop()
        }
    }

    // ── 15-second countdown ticker ────────────────────────────────────────────
    Timer {
        id: countdownTimer
        interval: 1000
        repeat: true
        running: false
        onTriggered: {
            root.secondsLeft -= 1
            if (root.secondsLeft <= 0) {
                countdownTimer.stop()
                root.isOpen = false
                // Confirm: actually run the action
                if (root.bridge) root.bridge.confirmPostAction()
            }
        }
    }

    // ── Backdrop ──────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.72

        Behavior on opacity { NumberAnimation { duration: 220 } }

        MouseArea {
            anchors.fill: parent
            // Block clicks on anything behind the modal
        }
    }

    // ── Card ──────────────────────────────────────────────────────────────────
    Rectangle {
        id: card
        width: 380
        height: cardCol.implicitHeight + 48
        anchors.centerIn: parent
        radius: 16
        color: "#131720"
        border.color: "#2D3748"
        border.width: 1.5

        // Subtle glow matching the danger tone
        layer.enabled: true
        layer.effect: null

        // Drop shadow via border glow effect rectangle
        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: parent.radius + 2
            color: "transparent"
            border.color: "#EF444430"
            border.width: 2
            z: -1
        }

        // Entrance animation
        scale: root.isOpen ? 1.0 : 0.88
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on scale   { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.3 } }
        Behavior on opacity { NumberAnimation { duration: 220 } }

        ColumnLayout {
            id: cardCol
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                topMargin: 28
                leftMargin: 28
                rightMargin: 28
            }
            spacing: 20

            // ── Header ────────────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Warning icon
                Rectangle {
                    width: 36; height: 36; radius: 18
                    color: "#3B1818"
                    border.color: "#EF4444"
                    border.width: 1.5

                    Text {
                        anchors.centerIn: parent
                        text: actionLabel === "Close App" ? "\uD83D\uDEAA" : "\u26A0\uFE0F"
                        font.pixelSize: 16
                    }
                }

                Column {
                    spacing: 2
                    Layout.fillWidth: true

                    Text {
                        text: root.actionLabel + " in..."
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                    }

                    Text {
                        text: "Download finished. Click Cancel to stop."
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                }
            }

            // ── Countdown ring ────────────────────────────────────────────────
            Item {
                Layout.alignment: Qt.AlignHCenter
                width: 120; height: 120

                // Background ring
                Canvas {
                    id: bgRing
                    anchors.fill: parent
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.beginPath()
                        ctx.arc(width / 2, height / 2, 48, 0, Math.PI * 2)
                        ctx.strokeStyle = "#1E293B"
                        ctx.lineWidth = 8
                        ctx.stroke()
                    }
                }

                // Danger progress arc
                Canvas {
                    id: progressRing
                    anchors.fill: parent

                    property real fraction: root.secondsLeft / root.totalSeconds

                    onFractionChanged: requestPaint()

                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)

                        var startAngle = -Math.PI / 2
                        var endAngle = startAngle + fraction * Math.PI * 2

                        ctx.beginPath()
                        ctx.arc(width / 2, height / 2, 48, startAngle, endAngle)
                        ctx.strokeStyle = fraction > 0.4 ? "#EF4444" : (fraction > 0.2 ? "#F97316" : "#FBBF24")
                        ctx.lineWidth = 8
                        ctx.lineCap = "round"
                        ctx.stroke()
                    }

                    Behavior on fraction {
                        NumberAnimation { duration: 800; easing.type: Easing.InOutSine }
                    }
                }

                // Center countdown number
                Column {
                    anchors.centerIn: parent
                    spacing: -2

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: root.secondsLeft.toString()
                        font.family: "Cascadia Code, Consolas, monospace"
                        font.pixelSize: 34
                        font.weight: Font.Bold
                        color: progressRing.fraction > 0.4 ? "#EF4444" : (progressRing.fraction > 0.2 ? "#F97316" : "#FBBF24")

                        Behavior on color { ColorAnimation { duration: 400 } }
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "sec"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                    }
                }
            }

            // ── Action description ────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: actionDesc.implicitHeight + 16
                radius: 8
                color: "#1A0F0F"
                border.color: "#7F1D1D"
                border.width: 1

                Text {
                    id: actionDesc
                    anchors {
                        left: parent.left; right: parent.right
                        verticalCenter: parent.verticalCenter
                        leftMargin: 14; rightMargin: 14
                    }
                    text: {
                        if (root.actionLabel === "Shutdown")   return "Your PC will shut down when the timer reaches 0."
                        if (root.actionLabel === "Restart")    return "Your PC will restart when the timer reaches 0."
                        if (root.actionLabel === "Hibernate")  return "Your PC will hibernate when the timer reaches 0."
                        if (root.actionLabel === "Sleep")      return "Your PC will go to sleep when the timer reaches 0."
                        if (root.actionLabel === "Close App")  return "Pawchive Downloader will close when the timer reaches 0."
                        return "The action will run when the timer reaches 0."
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#FCA5A5"
                    wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignHCenter
                }
            }

            // ── Cancel Button ─────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: 42
                radius: 10
                color: cancelMouse.containsMouse ? "#374151" : "#1F2937"
                border.color: cancelMouse.containsMouse ? "#6B7280" : "#374151"
                border.width: 1.5

                Behavior on color { ColorAnimation { duration: 120 } }
                Behavior on border.color { ColorAnimation { duration: 120 } }

                scale: cancelMouse.pressed ? 0.96 : 1.0
                Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutBack } }

                Row {
                    anchors.centerIn: parent
                    spacing: 8

                    Text {
                        text: "\u274C"
                        font.pixelSize: 14
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Text {
                        text: "Cancel — Don't " + root.actionLabel
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        color: "#F1F5F9"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: cancelMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        countdownTimer.stop()
                        root.isOpen = false
                        // Cancel: reset post-download action to none
                        if (root.bridge) root.bridge.cancelPostAction()
                    }
                }
            }

            // Bottom spacer
            Item { height: 4 }
        }
    }
}
