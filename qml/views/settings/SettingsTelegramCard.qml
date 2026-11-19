import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

CardSection {
    id: telegramCard
    required property var view
    function tr(key, fallback) { return view ? view.tr(key, fallback) : (fallback !== undefined ? fallback : key) }
    Layout.fillWidth: true
    interactive: !telegramCard.view.isScrolling
    title: tr("section_telegram", "Telegram Integration & Account Settings")
    iconText: "✈️"
    entranceOffsetY: telegramCard.view.tabEntranceOffsetY
    entranceOpacity: telegramCard.view.tabEntranceOpacity

    ColumnLayout {
        width: parent.width
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        spacing: 12

        // Status & Quick Connect Row
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 12

            Item {
                width: 14
                height: 14
                Layout.alignment: Qt.AlignVCenter

                // Liquid droplet core
                Rectangle {
                    id: tgStatusDot
                    anchors.centerIn: parent
                    width: 10
                    height: 10
                    radius: 5
                    color: (telegramBridge && telegramBridge.isLoggedIn) ? "#10B981" : "#64748B"

                    Behavior on color { ColorAnimation { duration: 250 } }
                }

                // Surface tension breathing aura
                Rectangle {
                    anchors.centerIn: parent
                    width: 16
                    height: 16
                    radius: 8
                    color: "transparent"
                    border.color: (telegramBridge && telegramBridge.isLoggedIn) ? "#10B981" : "#64748B"
                    border.width: 1
                    visible: telegramBridge && telegramBridge.isLoggedIn
                    opacity: 0.3

                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: telegramBridge && telegramBridge.isLoggedIn
                        NumberAnimation { to: 0.85; duration: 1600; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.15; duration: 1600; easing.type: Easing.InOutSine }
                    }
                    SequentialAnimation on scale {
                        loops: Animation.Infinite
                        running: telegramBridge && telegramBridge.isLoggedIn
                        NumberAnimation { to: 1.25; duration: 1600; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.95; duration: 1600; easing.type: Easing.InOutSine }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.minimumWidth: 0
                spacing: 2

                Text {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    text: (telegramBridge && telegramBridge.isLoggedIn)
                          ? (tr("tg_connected_as", "Connected as @") + telegramBridge.currentUsername + (telegramBridge.currentPhone ? " (" + telegramBridge.currentPhone + ")" : ""))
                          : tr("tg_not_connected", "Telegram Account Not Connected")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: (telegramBridge && telegramBridge.isLoggedIn) ? "#34D399" : "#94A3B8"
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    text: (telegramBridge && telegramBridge.isLoggedIn)
                          ? tr("tg_ready_desc", "Ready to download media from public and private Telegram channels.")
                          : tr("tg_connect_desc", "Connect via QR code, phone number, or bot token to enable downloads.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    wrapMode: Text.WordWrap
                }
            }

            StyledButton {
                text: (telegramBridge && telegramBridge.isLoggedIn) ? tr("tg_btn_manage", "Manage / Switch") : tr("tg_btn_connect", "Connect Telegram")
                implicitWidth: Math.max(140, contentItem.implicitWidth + 20)
                implicitHeight: 32
                variant: (telegramBridge && telegramBridge.isLoggedIn) ? "outline" : "primary"
                onClicked: {
                    appWindow.openTelegramAuthModal(false)
                }
            }
        }

        // Reset Login Row (shown when logged in — fixes corrupted session / re-login)
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            visible: telegramBridge && telegramBridge.isLoggedIn
            spacing: 8

            Text {
                text: "🔄"
                font.pixelSize: 12
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.minimumWidth: 0
                spacing: 2

                Text {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    text: tr("tg_reset_title", "Reset Telegram Session")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    color: "#F87171"
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    text: tr("tg_reset_desc", "Wipes the saved session and forces a clean re-login. Use this if you see auth errors or the account is acting unexpectedly.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    wrapMode: Text.WordWrap
                }
            }

            StyledButton {
                text: tr("tg_btn_reset_login", "Reset Login")
                implicitWidth: Math.max(110, contentItem.implicitWidth + 20)
                implicitHeight: 30
                variant: "danger"
                onClicked: {
                    if (telegramBridge) telegramBridge.resetSession()
                }
            }
        }

        // Mini Red Disclaimer Notice
        Rectangle {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            implicitHeight: tgMiniNotice.implicitHeight + 16
            radius: 6
            color: "#251214"
            border.color: "#EF4444"
            border.width: 1

            RowLayout {
                id: tgMiniNotice
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 8
                spacing: 8

                Text {
                    text: "⚠️"
                    font.pixelSize: 13
                    Layout.alignment: Qt.AlignTop
                }

                Text {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.minimumWidth: 0
                    text: tr("tg_settings_notice", "Developer Notice: Use a dedicated secondary Telegram account for mass downloading to protect your primary personal account from automated bans or restrictions.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    color: "#FCA5A5"
                    wrapMode: Text.WordWrap
                }
            }
        }

        // Reset Warning Modals button if acknowledged
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            visible: telegramCard.view.bridge ? (telegramCard.view.bridge.telegramSafetyAcknowledged || telegramCard.view.bridge.telegramLiabilityAcknowledged) : false
            spacing: 8

            Text {
                text: tr("tg_warnings_dismissed", "⚠️ Telegram safety advisory / liability disclaimer has been dismissed.")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#94A3B8"
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.minimumWidth: 0
                wrapMode: Text.WordWrap
            }

            StyledButton {
                text: tr("tg_btn_reset_warnings", "Reset Warning Prompts")
                variant: "outline"
                Layout.preferredHeight: 28
                Layout.preferredWidth: Math.max(160, contentItem.implicitWidth + 20)
                onClicked: {
                    if (telegramCard.view.bridge) telegramCard.view.bridge.resetTelegramWarnings()
                }
            }
        }

        // Advanced Custom Credentials Collapsible
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            MouseArea {
                Layout.fillWidth: true
                Layout.preferredHeight: 22
                cursorShape: Qt.PointingHandCursor
                onClicked: tgAdvancedCol.visible = !tgAdvancedCol.visible

                RowLayout {
                    anchors.fill: parent
                    spacing: 6

                    Text {
                        text: "⚙️"
                        font.pixelSize: 12
                    }

                    Text {
                        text: tr("tg_custom_api_title", "Advanced: Custom Telegram API Credentials (Optional)")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        color: "#94A3B8"
                        Layout.fillWidth: true
                        Layout.preferredWidth: 0
                        elide: Text.ElideRight
                    }

                    Text {
                        text: tgAdvancedCol.visible ? "▲" : "▼"
                        font.pixelSize: 9
                        color: "#64748B"
                    }
                }
            }

            ColumnLayout {
                id: tgAdvancedCol
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 8
                visible: false

                Text {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    Layout.minimumWidth: 0
                    text: tr("tg_custom_api_desc", "By default, Pawchive uses standard built-in credentials. If you experience connection limits, obtain your free api_id & api_hash from my.telegram.org and save them below:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 10

                    StyledTextField {
                        id: customApiIdInput
                        Layout.preferredWidth: 130
                        Layout.minimumWidth: 70
                        placeholderText: "API ID (e.g. 123456)"
                    }

                    StyledTextField {
                        id: customApiHashInput
                        Layout.fillWidth: true
                        Layout.minimumWidth: 70
                        Layout.preferredWidth: 0
                        placeholderText: "API Hash (32 characters)"
                    }

                    StyledButton {
                        text: tr("btn_save", "Save Keys")
                        implicitWidth: Math.max(85, contentItem.implicitWidth + 20)
                        implicitHeight: 30
                        variant: "outline"
                        onClicked: {
                            var idVal = parseInt(customApiIdInput.text.trim()) || 0
                            var hashVal = customApiHashInput.text.trim()
                            if (telegramBridge && idVal > 0 && hashVal.length > 0) {
                                telegramBridge.setCustomCredentials(idVal, hashVal)
                            }
                        }
                    }
                }
            }
        }
    }
}
