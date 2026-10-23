import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: overlayRoot

    property var bridge: null
    property string enteredPin: ""
    property bool confirmingReset: false
    property string errorText: ""

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    // Newtonian weight-based entry & exit: stays visible while fading/settling
    visible: opacity > 0.001
    opacity: (bridge && bridge.privacyModeActive) ? 1.0 : 0.0
    scale: (bridge && bridge.privacyModeActive) ? 1.0 : 0.96

    Behavior on opacity {
        NumberAnimation {
            duration: (bridge && bridge.privacyModeActive) ? 260 : 180
            easing.type: (bridge && bridge.privacyModeActive) ? Easing.OutCubic : Easing.InCubic
        }
    }
    Behavior on scale {
        NumberAnimation {
            duration: (bridge && bridge.privacyModeActive) ? 320 : 200
            easing.type: (bridge && bridge.privacyModeActive) ? Easing.OutBack : Easing.InQuad
            easing.overshoot: 1.2
        }
    }

    onVisibleChanged: {
        if (visible) {
            enteredPin = ""
            confirmingReset = false
            errorText = ""
            overlayRoot.forceActiveFocus()
        }
    }

    // Capture keyboard input for PIN digits and quick unlock
    focus: true
    Keys.onPressed: function(event) {
        if (!visible || !bridge || !bridge.privacyModeActive) return

        var isLocked = bridge.privacyLockoutActive
        if (isLocked) {
            if (event.key === Qt.Key_Escape) {
                // If user pressed Esc while in lockout, ignore or keep locked
                event.accepted = true
            }
            return
        }

        var hasPin = bridge.privacyPinConfigured

        if (hasPin) {
            if (confirmingReset) {
                if (event.key === Qt.Key_Escape) {
                    confirmingReset = false
                    event.accepted = true
                }
                return
            }

            if (event.key >= Qt.Key_0 && event.key <= Qt.Key_9) {
                var digit = String.fromCharCode(event.key)
                handleDigit(digit)
                event.accepted = true
            } else if (event.key === Qt.Key_Backspace) {
                handleBackspace()
                event.accepted = true
            } else if (event.key === Qt.Key_Escape) {
                enteredPin = ""
                errorText = ""
                confirmingReset = false
                event.accepted = true
            }
        } else {
            // No PIN — Space, Enter, or Escape unlocks immediately
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space || event.key === Qt.Key_Escape) {
                unlockNow()
                event.accepted = true
            }
        }
    }

    function unlockNow() {
        if (bridge) bridge.privacyModeActive = false
    }

    function handleDigit(d) {
        if (enteredPin.length < 4) {
            errorText = ""
            enteredPin += d
            if (enteredPin.length === 4) {
                checkPinTimer.restart()
            }
        }
    }

    function handleBackspace() {
        if (enteredPin.length > 0) {
            errorText = ""
            enteredPin = enteredPin.substring(0, enteredPin.length - 1)
        }
    }

    Timer {
        id: checkPinTimer
        interval: 100
        repeat: false
        onTriggered: {
            if (!bridge) return
            var ok = bridge.unlockPrivacyMode(enteredPin)
            if (!ok) {
                var remaining = 5 - (bridge.privacyFailedAttempts || 0)
                if (bridge.privacyLockoutActive) {
                    errorText = ""
                } else if (remaining > 0) {
                    errorText = overlayRoot.tr("privacy_failed_attempts", "Incorrect PIN (%1 of 5 attempts remaining)").arg(remaining)
                } else {
                    errorText = overlayRoot.tr("msg_incorrect_pin", "Incorrect PIN")
                }
                shakeAnim.restart()
                enteredPin = ""
            } else {
                enteredPin = ""
                errorText = ""
            }
        }
    }

    // Click anywhere behavior:
    // If no PIN: clicking anywhere immediately unblurs
    // If PIN: clicking anywhere returns focus so user can type digits
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: (bridge && !bridge.privacyPinConfigured && !bridge.privacyLockoutActive) ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: {
            overlayRoot.forceActiveFocus()
            if (bridge && !bridge.privacyPinConfigured && !bridge.privacyLockoutActive) {
                unlockNow()
            }
        }
    }

    // Translucent dark frosted glass veil (strong, deeply obscuring content while looking elegant)
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(8/255, 10/255, 16/255, 0.88)
    }

    // Minimal Floating Center Container with Newtonian spring physics
    Item {
        id: centerBox
        anchors.centerIn: parent
        width: Math.min(parent.width - 40, bridge && bridge.privacyLockoutActive ? 440 : 340)
        height: Math.min(parent.height - 40, bridge && bridge.privacyLockoutActive ? 320 : 250)

        // Newtonian spring entrance for the card
        scale: (bridge && bridge.privacyModeActive) ? 1.0 : 0.90
        Behavior on scale {
            NumberAnimation {
                duration: 350
                easing.type: Easing.OutBack
                easing.overshoot: 1.3
            }
        }

        // Damped harmonic shake on incorrect PIN entry
        SequentialAnimation {
            id: shakeAnim
            running: false
            NumberAnimation { target: centerBox; property: "x"; to: centerBox.x - 12; duration: 45; easing.type: Easing.OutQuad }
            NumberAnimation { target: centerBox; property: "x"; to: centerBox.x + 10; duration: 45; easing.type: Easing.OutQuad }
            NumberAnimation { target: centerBox; property: "x"; to: centerBox.x - 8; duration: 40; easing.type: Easing.OutQuad }
            NumberAnimation { target: centerBox; property: "x"; to: centerBox.x + 6; duration: 40; easing.type: Easing.OutQuad }
            NumberAnimation { target: centerBox; property: "x"; to: centerBox.x - 3; duration: 35; easing.type: Easing.OutQuad }
            NumberAnimation { target: centerBox; property: "x"; to: centerBox.x; duration: 35; easing.type: Easing.OutQuad }
        }

        // ══════════════════════════════════════════════════════════════════════
        // STATE 1: SESSION LOCKED (5 Failed Attempts OR PIN Reset Requested)
        // ══════════════════════════════════════════════════════════════════════
        ColumnLayout {
            anchors.centerIn: parent
            width: parent.width
            spacing: 16
            visible: bridge && bridge.privacyLockoutActive

            // Warning shield/lock badge
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 56
                height: 56
                radius: 28
                color: Qt.rgba(239/255, 68/255, 68/255, 0.15)
                border.color: "#EF4444"
                border.width: 1.5

                Text {
                    anchors.centerIn: parent
                    text: "🔒"
                    font.pixelSize: 26
                }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: overlayRoot.tr("privacy_locked_out_title", "Session Locked")
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 18
                font.weight: 700
                color: "#F87171"
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                text: overlayRoot.tr("privacy_locked_out_desc", "Too many failed attempts or PIN reset requested. To protect your privacy, please restart Pawchive to reset your PIN.")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                lineHeight: 1.35
                color: "#CBD5E1"
            }

            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                Layout.fillWidth: true
                height: downloadSafeRow.implicitHeight + 16
                radius: 8
                color: Qt.rgba(16/255, 185/255, 129/255, 0.10)
                border.color: Qt.rgba(16/255, 185/255, 129/255, 0.30)
                border.width: 1

                RowLayout {
                    id: downloadSafeRow
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    Text {
                        text: "✓"
                        font.pixelSize: 13
                        font.weight: Font.Bold
                        color: "#10B981"
                    }

                    Text {
                        Layout.fillWidth: true
                        text: overlayRoot.tr("privacy_downloads_safe_notice", "Active downloads will safely pause and automatically resume once reopened.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#A7F3D0"
                        wrapMode: Text.Wrap
                    }
                }
            }

            // Close / Exit App Button
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                height: 34
                implicitWidth: exitRow.implicitWidth + 28
                radius: 8
                color: exitMouse.containsMouse ? "#DC2626" : "#EF4444"
                border.color: exitMouse.containsMouse ? "#EF4444" : "#B91C1C"
                border.width: 1

                scale: exitMouse.pressed ? 0.95 : (exitMouse.containsMouse ? 1.03 : 1.0)
                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack } }

                Row {
                    id: exitRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        text: overlayRoot.tr("privacy_btn_exit_app", "Exit App & Restart Later")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#FFFFFF"
                    }
                }

                MouseArea {
                    id: exitMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: Qt.quit()
                }
            }
        }

        // ══════════════════════════════════════════════════════════════════════
        // STATE 2: ACTIVE PRIVACY MODE (NOT LOCKED OUT)
        // ══════════════════════════════════════════════════════════════════════
        ColumnLayout {
            anchors.centerIn: parent
            spacing: 14
            visible: !(bridge && bridge.privacyLockoutActive)

            // Subtle Minimal Icon
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 48
                height: 48
                radius: 24
                color: Qt.rgba(20/255, 25/255, 36/255, 0.85)
                border.color: (bridge && bridge.privacyPinConfigured) ? "#2D3748" : "#38BDF8"
                border.width: 1

                scale: iconMouse.containsMouse ? 1.08 : 1.0
                Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutBack } }

                Image {
                    anchors.centerIn: parent
                    width: 24
                    height: 24
                    sourceSize: Qt.size(24, 24)
                    source: "../../assets/icons/eye_closed.svg"
                }

                MouseArea {
                    id: iconMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (bridge && !bridge.privacyPinConfigured) {
                            unlockNow()
                        } else {
                            overlayRoot.forceActiveFocus()
                        }
                    }
                }
            }

            // Minimal Title
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: (bridge && bridge.privacyPinConfigured)
                      ? overlayRoot.tr("privacy_enter_pin_title", "Enter PIN")
                      : overlayRoot.tr("privacy_shield_title", "Privacy Mode")
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 15
                font.weight: 600
                color: "#F1F5F9"
            }

            // ── NO PIN CONFIGURED: 1-Click / Space Resume Pill ──
            ColumnLayout {
                visible: bridge && !bridge.privacyPinConfigured
                Layout.alignment: Qt.AlignHCenter
                spacing: 8

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    height: 32
                    implicitWidth: resumeRow.implicitWidth + 24
                    radius: 16
                    color: resumeMouse.containsMouse ? Qt.rgba(56/255, 189/255, 248/255, 0.15) : Qt.rgba(20/255, 25/255, 36/255, 0.75)
                    border.color: resumeMouse.containsMouse ? "#38BDF8" : "#2E384D"
                    border.width: 1

                    scale: resumeMouse.pressed ? 0.95 : (resumeMouse.containsMouse ? 1.04 : 1.0)
                    Behavior on scale { NumberAnimation { duration: 120 } }
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    Row {
                        id: resumeRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: overlayRoot.tr("btn_resume_app", "Click to Resume")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: resumeMouse.containsMouse ? "#38BDF8" : "#CBD5E1"
                        }
                    }

                    MouseArea {
                        id: resumeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: unlockNow()
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: overlayRoot.tr("hint_press_space_to_resume", "or press Space / Esc")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                }
            }

            // ── PIN CONFIGURED: Minimal Dots & Direct Typing ──
            ColumnLayout {
                visible: bridge && bridge.privacyPinConfigured
                Layout.alignment: Qt.AlignHCenter
                spacing: 12

                // 4 Minimal Dots with spring animation
                Row {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 14

                    Repeater {
                        model: 4
                        Rectangle {
                            width: 12
                            height: 12
                            radius: 6
                            color: index < enteredPin.length ? "#38BDF8" : "transparent"
                            border.color: index < enteredPin.length ? "#38BDF8" : "#475569"
                            border.width: 1.5

                            scale: index < enteredPin.length ? 1.25 : 1.0
                            Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }
                            Behavior on color { ColorAnimation { duration: 100 } }
                            Behavior on border.color { ColorAnimation { duration: 100 } }

                            Rectangle {
                                anchors.centerIn: parent
                                width: 18
                                height: 18
                                radius: 9
                                color: Qt.rgba(56/255, 189/255, 248/255, 0.3)
                                visible: index < enteredPin.length
                            }
                        }
                    }
                }

                // Error text or hint
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: errorText.length > 0 ? errorText : overlayRoot.tr("hint_type_pin", "Type 4-digit PIN on keyboard")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: errorText.length > 0 ? "#F87171" : "#64748B"
                }

                // Reset PIN actions
                Item {
                    Layout.alignment: Qt.AlignHCenter
                    height: 28
                    implicitWidth: confirmingReset ? resetConfirmCol.implicitWidth : resetLink.implicitWidth

                    // State A: Discreet Reset PIN Link
                    Text {
                        id: resetLink
                        visible: !confirmingReset
                        anchors.centerIn: parent
                        text: overlayRoot.tr("btn_forgot_pin", "Forgot PIN / Reset")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.underline: resetLinkMouse.containsMouse
                        color: resetLinkMouse.containsMouse ? "#EF4444" : "#64748B"

                        MouseArea {
                            id: resetLinkMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: confirmingReset = true
                        }
                    }

                    // State B: Confirming Reset requires app restart to protect privacy
                    Row {
                        id: resetConfirmCol
                        visible: confirmingReset
                        anchors.centerIn: parent
                        spacing: 8

                        Text {
                            text: overlayRoot.tr("msg_reset_restart_req", "Restart required to reset PIN:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            text: overlayRoot.tr("btn_lock_and_restart", "Lock & Reset")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            font.underline: yesMouse.containsMouse
                            color: yesMouse.containsMouse ? "#F87171" : "#EF4444"
                            anchors.verticalCenter: parent.verticalCenter

                            MouseArea {
                                id: yesMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (bridge) bridge.requestPinReset()
                                    confirmingReset = false
                                }
                            }
                        }

                        Text {
                            text: "•"
                            font.pixelSize: 10
                            color: "#475569"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            text: overlayRoot.tr("btn_cancel", "Cancel")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.underline: noMouse.containsMouse
                            color: noMouse.containsMouse ? "#CBD5E1" : "#64748B"
                            anchors.verticalCenter: parent.verticalCenter

                            MouseArea {
                                id: noMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: confirmingReset = false
                            }
                        }
                    }
                }
            }
        }
    }
}
