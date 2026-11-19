import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

CardSection {
    id: privacyCard
    required property var view
    function tr(key, fallback) { return view ? view.tr(key, fallback) : (fallback !== undefined ? fallback : key) }
    Layout.fillWidth: true
    interactive: !privacyCard.view.isScrolling
    title: privacyCard.view.tr("section_privacy_security", "Privacy Mode & PIN Protection")
    iconText: "👁️"
    entranceOffsetY: privacyCard.view.tabEntranceOffsetY
    entranceOpacity: privacyCard.view.tabEntranceOpacity

    ColumnLayout {
        width: parent.width
        spacing: 12

        Text {
            text: privacyCard.view.tr("privacy_settings_desc", "Instantly blur application content and hide URLs, thumbnails, and creator details (Ctrl+P or the top-bar eye button). Active downloads continue normally. The blur resets automatically on application restart.")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        // Status & Configuration Card
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: pinStatusRow.implicitHeight + 20
            radius: 8
            color: "#131722"
            border.color: "#1E2536"
            border.width: 1

            RowLayout {
                id: pinStatusRow
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 10
                spacing: 12

                Rectangle {
                    width: 32
                    height: 32
                    radius: 16
                    color: "#141824"
                    border.color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyPinConfigured) ? "#10B981" : "#2E384D"
                    border.width: 1
                    Layout.alignment: Qt.AlignTop

                    Image {
                        anchors.centerIn: parent
                        width: 16
                        height: 16
                        sourceSize: Qt.size(16, 16)
                        source: (privacyCard.view.bridge && privacyCard.view.bridge.privacyPinConfigured)
                                ? "../../../assets/icons/eye_closed.svg"
                                : "../../../assets/icons/eye_open.svg"
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.minimumWidth: 80
                    spacing: 4

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            text: (privacyCard.view.bridge && privacyCard.view.bridge.privacyPinConfigured)
                                  ? privacyCard.view.tr("privacy_pin_status_active", "4-Digit PIN Protection Active")
                                  : privacyCard.view.tr("privacy_pin_status_none", "No PIN Configured (Unlocked with 1 Click)")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyPinConfigured) ? "#10B981" : "#F8FAFC"
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                            Layout.preferredWidth: 0
                        }

                        Rectangle {
                            height: 18
                            implicitWidth: pinBadgeText.implicitWidth + 12
                            radius: 9
                            color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyPinConfigured) ? "#064E3B" : "#1E293B"
                            border.color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyPinConfigured) ? "#059669" : "#334155"
                            border.width: 1

                            Text {
                                id: pinBadgeText
                                anchors.centerIn: parent
                                text: (privacyCard.view.bridge && privacyCard.view.bridge.privacyPinConfigured) ? privacyCard.view.tr("badge_pin_enabled", "PIN Enabled") : privacyCard.view.tr("badge_optional", "Optional")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                                color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyPinConfigured) ? "#6EE7B7" : "#94A3B8"
                            }
                        }
                    }

                    Text {
                        text: (privacyCard.view.bridge && privacyCard.view.bridge.privacyPinConfigured)
                              ? privacyCard.view.tr("privacy_pin_active_hint", "Entering your 4-digit PIN is required to unblur the app. You can reset or change it at any time.")
                              : privacyCard.view.tr("privacy_pin_none_hint", "Clicking the shield or pressing Ctrl+P blurs the app immediately. Anyone can unblur with 1 click unless a PIN is set.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        Layout.preferredWidth: 0
                        Layout.minimumWidth: 80
                    }
                }

                // Action Buttons: Set / Change / Reset PIN
                RowLayout {
                    spacing: 8
                    Layout.alignment: Qt.AlignVCenter
                    Layout.fillWidth: false

                    // Set PIN / Change PIN Button
                    Rectangle {
                        id: pinActionBtn
                        height: 26
                        Layout.preferredHeight: 26
                        Layout.preferredWidth: pinActionRow.implicitWidth + 16
                        radius: 5
                        color: pinActionMouse.containsMouse ? "#0284C7" : "#0369A1"
                        border.color: "#38BDF8"
                        border.width: 1

                        Row {
                            id: pinActionRow
                            anchors.centerIn: parent
                            spacing: 5
                            Text {
                                text: "🔑"
                                font.pixelSize: 10
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                id: pinActionText
                                text: (privacyCard.view.bridge && privacyCard.view.bridge.privacyPinConfigured)
                                      ? privacyCard.view.tr("btn_change_pin", "Change PIN")
                                      : privacyCard.view.tr("btn_set_pin", "Set 4-Digit PIN")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: "#FFFFFF"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            id: pinActionMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                inlinePinBox.editingPin = !inlinePinBox.editingPin
                                if (inlinePinBox.editingPin) {
                                    newPinField.forceActiveFocus()
                                }
                            }
                        }
                    }

                    // Reset PIN Button (visible if PIN configured)
                    Rectangle {
                        id: resetPinBtn
                        visible: privacyCard.view.bridge ? privacyCard.view.bridge.privacyPinConfigured : false
                        height: 26
                        Layout.preferredHeight: 26
                        Layout.preferredWidth: resetPinRow.implicitWidth + 16
                        radius: 5
                        color: resetPinMouse.containsMouse ? "#7F1D1D" : "#450A0A"
                        border.color: "#EF4444"
                        border.width: 1

                        Row {
                            id: resetPinRow
                            anchors.centerIn: parent
                            spacing: 5
                            Text {
                                text: "🗑️"
                                font.pixelSize: 10
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                id: resetPinText
                                text: privacyCard.view.tr("btn_reset_pin", "Reset PIN")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: "#FCA5A5"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            id: resetPinMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: privacyCard.view.tr("tip_reset_pin", "Clears your PIN. The app can be unblurred without a password at any time.")
                            onClicked: {
                                if (privacyCard.view.bridge) privacyCard.view.bridge.resetPrivacyPin()
                                inlinePinBox.editingPin = false
                            }
                        }
                    }
                }
            }
        }

        // Inline PIN Setup Box (unfolds when editing PIN)
        Rectangle {
            id: inlinePinBox
            Layout.fillWidth: true
            visible: editingPin
            implicitHeight: pinEditCol.implicitHeight + 24
            radius: 8
            color: "#0F131D"
            border.color: "#38BDF8"
            border.width: 1

            property bool editingPin: false
            property string editError: ""

            ColumnLayout {
                id: pinEditCol
                anchors.fill: parent
                anchors.margins: 12
                spacing: 10

                Text {
                    text: privacyCard.view.tr("privacy_set_pin_prompt", "Enter a 4-digit PIN to require a password on unblurring:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: 600
                    color: "#F8FAFC"
                }

                RowLayout {
                    spacing: 16

                    ColumnLayout {
                        spacing: 4
                        Text {
                            text: privacyCard.view.tr("label_new_pin", "New 4-Digit PIN:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                        StyledTextField {
                            id: newPinField
                            implicitWidth: 140
                            implicitHeight: 32
                            placeholderText: "••••"
                            echoMode: TextInput.Password
                            maximumLength: 4
                            inputMethodHints: Qt.ImhDigitsOnly
                            validator: RegularExpressionValidator { regularExpression: /[0-9]{4}/ }
                        }
                    }

                    ColumnLayout {
                        spacing: 4
                        Text {
                            text: privacyCard.view.tr("label_confirm_pin", "Confirm PIN:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                        StyledTextField {
                            id: confirmPinField
                            implicitWidth: 140
                            implicitHeight: 32
                            placeholderText: "••••"
                            echoMode: TextInput.Password
                            maximumLength: 4
                            inputMethodHints: Qt.ImhDigitsOnly
                            validator: RegularExpressionValidator { regularExpression: /[0-9]{4}/ }
                        }
                    }

                    Row {
                        spacing: 8
                        Layout.alignment: Qt.AlignBottom

                        Rectangle {
                            height: 26
                            implicitWidth: savePinBtnText.implicitWidth + 18
                            width: implicitWidth
                            radius: 5
                            color: savePinMouse.containsMouse ? "#0284C7" : "#0369A1"
                            border.color: "#38BDF8"
                            border.width: 1

                            Text {
                                id: savePinBtnText
                                anchors.centerIn: parent
                                text: privacyCard.view.tr("btn_save_pin", "Save PIN")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: "#FFFFFF"
                            }

                            MouseArea {
                                id: savePinMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var p1 = newPinField.text.trim()
                                    var p2 = confirmPinField.text.trim()
                                    if (p1.length !== 4) {
                                        inlinePinBox.editError = privacyCard.view.tr("err_pin_4_digits", "PIN must be exactly 4 digits.")
                                        return
                                    }
                                    if (p1 !== p2) {
                                        inlinePinBox.editError = privacyCard.view.tr("err_pin_mismatch", "PINs do not match.")
                                        return
                                    }
                                    if (privacyCard.view.bridge) privacyCard.view.bridge.setPrivacyPin(p1)
                                    inlinePinBox.editingPin = false
                                    newPinField.text = ""
                                    confirmPinField.text = ""
                                    inlinePinBox.editError = ""
                                }
                            }
                        }

                        Rectangle {
                            height: 26
                            implicitWidth: cancelPinBtnText.implicitWidth + 16
                            width: implicitWidth
                            radius: 5
                            color: cancelPinMouse.containsMouse ? "#1E293B" : "#141A28"
                            border.color: "#334155"
                            border.width: 1

                            Text {
                                id: cancelPinBtnText
                                anchors.centerIn: parent
                                text: privacyCard.view.tr("btn_cancel", "Cancel")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: cancelPinMouse.containsMouse ? "#FFFFFF" : "#94A3B8"
                            }

                            MouseArea {
                                id: cancelPinMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    inlinePinBox.editingPin = false
                                    newPinField.text = ""
                                    confirmPinField.text = ""
                                    inlinePinBox.editError = ""
                                }
                            }
                        }
                    }
                }

                Text {
                    visible: inlinePinBox.editError.length > 0
                    text: inlinePinBox.editError
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#EF4444"
                }
            }
        }

        // ── Inactivity / Auto-Lock Idle Timer Card (Always Available) ──
        Rectangle {
            id: idleTimerCard
            Layout.fillWidth: true
            implicitHeight: idleTimerLayout.implicitHeight + 24
            radius: 8
            color: "#131722"
            border.color: "#1E2536"
            border.width: 1

            readonly property bool isCompact: width < 540

            GridLayout {
                id: idleTimerLayout
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 12
                columns: idleTimerCard.isCompact ? 1 : 2
                rowSpacing: 10
                columnSpacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.minimumWidth: 80
                    spacing: 12
                    Layout.alignment: Qt.AlignVCenter

                    Rectangle {
                        width: 32
                        height: 32
                        radius: 16
                        color: "#141824"
                        border.color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyIdleMinutes > 0) ? "#38BDF8" : "#2E384D"
                        border.width: 1
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            anchors.centerIn: parent
                            text: "⏱️"
                            font.pixelSize: 15
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 0
                        Layout.minimumWidth: 60
                        spacing: 3

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Text {
                                text: privacyCard.view.tr("privacy_idle_title", "Auto-Lock when Idle")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: 600
                                color: "#F8FAFC"
                            }

                            Rectangle {
                                height: 18
                                implicitWidth: idleBadgeText.implicitWidth + 12
                                radius: 9
                                color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyIdleMinutes > 0) ? "#064E3B" : "#1E293B"
                                border.color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyIdleMinutes > 0) ? "#059669" : "#334155"
                                border.width: 1

                                Text {
                                    id: idleBadgeText
                                    anchors.centerIn: parent
                                    text: (privacyCard.view.bridge && privacyCard.view.bridge.privacyIdleMinutes > 0)
                                          ? (privacyCard.view.bridge.privacyIdleMinutes + " min")
                                          : privacyCard.view.tr("opt_disabled", "Disabled")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                    color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyIdleMinutes > 0) ? "#6EE7B7" : "#94A3B8"
                                }
                            }
                        }

                        Text {
                            text: privacyCard.view.tr("privacy_idle_hint", "Automatically engage Privacy Mode when no mouse or keyboard activity is detected.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            Layout.preferredWidth: 0
                        }
                    }
                }

                RowLayout {
                    spacing: 8
                    Layout.alignment: idleTimerCard.isCompact ? Qt.AlignLeft : Qt.AlignRight
                    Layout.leftMargin: idleTimerCard.isCompact ? 44 : 0

                    StyledComboBox {
                        id: idleTimeoutCombo
                        Layout.preferredWidth: 165
                        model: [
                            { text: privacyCard.view.tr("opt_disabled", "Disabled (Never Auto-Lock)"), value: 0 },
                            { text: privacyCard.view.tr("opt_idle_1m", "1 minute"), value: 1 },
                            { text: privacyCard.view.tr("opt_idle_2m", "2 minutes"), value: 2 },
                            { text: privacyCard.view.tr("opt_idle_3m", "3 minutes"), value: 3 },
                            { text: privacyCard.view.tr("opt_idle_5m", "5 minutes (Default)"), value: 5 },
                            { text: privacyCard.view.tr("opt_idle_10m", "10 minutes"), value: 10 },
                            { text: privacyCard.view.tr("opt_idle_15m", "15 minutes"), value: 15 },
                            { text: privacyCard.view.tr("opt_idle_20m", "20 minutes"), value: 20 },
                            { text: privacyCard.view.tr("opt_idle_30m", "30 minutes"), value: 30 },
                            { text: privacyCard.view.tr("opt_idle_45m", "45 minutes"), value: 45 },
                            { text: privacyCard.view.tr("opt_idle_60m", "60 minutes"), value: 60 }
                        ]
                        value: privacyCard.view.bridge ? privacyCard.view.bridge.privacyIdleMinutes : 5
                        onValuePicked: function(val) {
                            if (privacyCard.view.bridge) privacyCard.view.bridge.setPrivacyIdleMinutes(parseInt(val))
                        }
                    }

                    // Quick Toggle / Disable Button
                    Rectangle {
                        id: disableIdleBtn
                        height: 28
                        Layout.preferredHeight: 28
                        Layout.preferredWidth: disableIdleBtnText.implicitWidth + 20
                        radius: 5
                        color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyIdleMinutes > 0)
                               ? (disableIdleMouse.containsMouse ? "#7F1D1D" : "#450A0A")
                               : (disableIdleMouse.containsMouse ? "#065F46" : "#064E3B")
                        border.color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyIdleMinutes > 0) ? "#EF4444" : "#10B981"
                        border.width: 1

                        Text {
                            id: disableIdleBtnText
                            anchors.centerIn: parent
                            text: (privacyCard.view.bridge && privacyCard.view.bridge.privacyIdleMinutes > 0)
                                  ? privacyCard.view.tr("btn_disable_idle", "Disable")
                                  : privacyCard.view.tr("btn_enable_idle", "Enable")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: (privacyCard.view.bridge && privacyCard.view.bridge.privacyIdleMinutes > 0) ? "#FCA5A5" : "#6EE7B7"
                        }

                        MouseArea {
                            id: disableIdleMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: (privacyCard.view.bridge && privacyCard.view.bridge.privacyIdleMinutes > 0)
                                          ? privacyCard.view.tr("tip_disable_idle", "Completely turn off idle auto-locking")
                                          : privacyCard.view.tr("tip_enable_idle", "Turn on idle auto-locking (5 minutes default)")
                            onClicked: {
                                if (!privacyCard.view.bridge) return
                                if (privacyCard.view.bridge.privacyIdleMinutes > 0) {
                                    privacyCard.view.bridge.setPrivacyIdleMinutes(0)
                                } else {
                                    privacyCard.view.bridge.setPrivacyIdleMinutes(5)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
