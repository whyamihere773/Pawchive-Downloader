import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: bannerRoot

    property var bridge: null
    property bool settingNewPin: false
    property string newPinInput: ""
    property string pinErrorText: ""

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    readonly property bool isActive: bridge ? bridge.safeModeActive : false

    Layout.fillWidth: true
    implicitHeight: isActive ? contentCol.implicitHeight + 24 : 0
    visible: implicitHeight > 1
    clip: true

    Behavior on implicitHeight {
        NumberAnimation {
            duration: bannerRoot.isActive ? 320 : 220
            easing.type: bannerRoot.isActive ? Easing.OutBack : Easing.InQuad
            easing.overshoot: 1.2
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "#181410"
        border.color: "#B45309"
        border.width: 1

        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 4
            color: "#F59E0B"
        }

        ColumnLayout {
            id: contentCol
            anchors.fill: parent
            anchors.leftMargin: 18
            anchors.rightMargin: 16
            anchors.topMargin: 12
            anchors.bottomMargin: 12
            spacing: 10

            // Header Row: Icon + Title
            RowLayout {
                spacing: 10
                Layout.fillWidth: true

                Text {
                    text: "🔒"
                    font.pixelSize: 18
                }

                Text {
                    text: bannerRoot.tr("safemode_title", "Safe Mode Active — Action Required")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    color: "#FCD34D"
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    height: 20
                    implicitWidth: badgeText.implicitWidth + 12
                    radius: 10
                    color: "#451A03"
                    border.color: "#78350F"
                    border.width: 1

                    Text {
                        id: badgeText
                        anchors.centerIn: parent
                        text: bannerRoot.tr("badge_quarantine", "Tabs Quarantined")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#FBBF24"
                    }
                }
            }

            // Explanatory Text
            Text {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: bannerRoot.tr("safemode_desc", "A PIN reset was requested or 5 incorrect attempts were entered during the previous session. Tabs and previews have been temporarily quarantined to protect your privacy. Active downloads are completely safe.")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                lineHeight: 1.35
                color: "#E2E8F0"
            }

            // Interactive Action Area
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                visible: !settingNewPin

                Text {
                    text: bannerRoot.tr("safemode_instructions", "Choose an option to restore full access to all tabs:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#94A3B8"
                }

                Item { Layout.fillWidth: true }

                // Option 1: Set New PIN
                Rectangle {
                    height: 30
                    implicitWidth: setPinText.implicitWidth + 24
                    radius: 6
                    color: setPinMouse.containsMouse ? "#2563EB" : "#1D4ED8"
                    border.color: setPinMouse.containsMouse ? "#60A5FA" : "#3B82F6"
                    border.width: 1

                    scale: setPinMouse.pressed ? 0.95 : (setPinMouse.containsMouse ? 1.03 : 1.0)
                    Behavior on scale { NumberAnimation { duration: 120 } }

                    Text {
                        id: setPinText
                        anchors.centerIn: parent
                        text: bannerRoot.tr("safemode_btn_set_pin", "🔑 Set New PIN")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#FFFFFF"
                    }

                    MouseArea {
                        id: setPinMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            newPinInput = ""
                            pinErrorText = ""
                            settingNewPin = true
                        }
                    }
                }

                // Option 2: Remove PIN (Blur Only)
                Rectangle {
                    height: 30
                    implicitWidth: remPinText.implicitWidth + 24
                    radius: 6
                    color: remPinMouse.containsMouse ? "#334155" : "#1E293B"
                    border.color: remPinMouse.containsMouse ? "#64748B" : "#475569"
                    border.width: 1

                    scale: remPinMouse.pressed ? 0.95 : (remPinMouse.containsMouse ? 1.03 : 1.0)
                    Behavior on scale { NumberAnimation { duration: 120 } }

                    Text {
                        id: remPinText
                        anchors.centerIn: parent
                        text: bannerRoot.tr("safemode_btn_remove_pin", "🔓 Remove PIN (Blur Only)")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#CBD5E1"
                    }

                    MouseArea {
                        id: remPinMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (bridge) bridge.completePinReset("")
                        }
                    }
                }
            }

            // Inline PIN Configuration (When "Set New PIN" is selected)
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                visible: settingNewPin

                Text {
                    text: bannerRoot.tr("safemode_pin_prompt", "Enter new 4-digit PIN:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: 600
                    color: "#FCD34D"
                }

                TextField {
                    id: pinField
                    implicitWidth: 100
                    implicitHeight: 30
                    maximumLength: 4
                    echoMode: TextInput.Password
                    inputMethodHints: Qt.ImhDigitsOnly
                    color: "#FFFFFF"
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    horizontalAlignment: TextInput.AlignHCenter
                    background: Rectangle {
                        color: "#0F1117"
                        border.color: pinField.activeFocus ? "#38BDF8" : "#334155"
                        border.width: 1
                        radius: 5
                    }
                    text: newPinInput
                    onTextChanged: {
                        newPinInput = text.replace(/[^0-9]/g, "")
                        pinErrorText = ""
                        if (newPinInput.length === 4) {
                            // Ready to save
                        }
                    }
                    Keys.onReturnPressed: confirmNewPin()
                    Keys.onEnterPressed: confirmNewPin()
                    Keys.onEscapePressed: {
                        settingNewPin = false
                        newPinInput = ""
                        pinErrorText = ""
                    }
                }

                // Confirm Button
                Rectangle {
                    height: 30
                    implicitWidth: confText.implicitWidth + 20
                    radius: 6
                    color: confMouse.containsMouse ? "#059669" : "#10B981"
                    border.color: confMouse.containsMouse ? "#34D399" : "#059669"
                    border.width: 1
                    enabled: newPinInput.length === 4
                    opacity: enabled ? 1.0 : 0.5

                    Text {
                        id: confText
                        anchors.centerIn: parent
                        text: bannerRoot.tr("safemode_btn_confirm_pin", "Save & Restore Tabs")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#FFFFFF"
                    }

                    MouseArea {
                        id: confMouse
                        anchors.fill: parent
                        hoverEnabled: parent.enabled
                        cursorShape: parent.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: confirmNewPin()
                    }
                }

                // Cancel Button
                Rectangle {
                    height: 30
                    implicitWidth: cancelText.implicitWidth + 16
                    radius: 6
                    color: "transparent"
                    border.color: cancelMouse.containsMouse ? "#94A3B8" : "#475569"
                    border.width: 1

                    Text {
                        id: cancelText
                        anchors.centerIn: parent
                        text: bannerRoot.tr("btn_cancel", "Cancel")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: cancelMouse.containsMouse ? "#F8FAFC" : "#94A3B8"
                    }

                    MouseArea {
                        id: cancelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            settingNewPin = false
                            newPinInput = ""
                            pinErrorText = ""
                        }
                    }
                }

                Text {
                    visible: pinErrorText.length > 0
                    text: pinErrorText
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#F87171"
                }

                Item { Layout.fillWidth: true }
            }
        }
    }

    function confirmNewPin() {
        if (newPinInput.length !== 4) {
            pinErrorText = bannerRoot.tr("safemode_pin_error", "Please enter exactly 4 digits")
            return
        }
        if (bridge) {
            bridge.completePinReset(newPinInput)
            settingNewPin = false
            newPinInput = ""
            pinErrorText = ""
        }
    }
}
