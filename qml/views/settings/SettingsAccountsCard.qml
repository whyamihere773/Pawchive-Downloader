import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

CardSection {
    id: accountsSection
    required property var view
    function tr(key, fallback) { return view ? view.tr(key, fallback) : (fallback !== undefined ? fallback : key) }
    Layout.fillWidth: true
    interactive: !accountsSection.view.isScrolling
    title: tr("section_accounts", "Accounts & Connected Providers")
    iconText: "🔐"
    customBorderColor: accountsSection.view.highlightAccountsSection ? "#F59E0B" : "transparent"
    customBorderWidth: accountsSection.view.highlightAccountsSection ? 2 : 0
    entranceOffsetY: accountsSection.view.tabEntranceOffsetY
    entranceOpacity: accountsSection.view.tabEntranceOpacity

    ColumnLayout {
        width: parent.width
        Layout.fillWidth: true
        spacing: 12

        // ── Hardware Encryption Security Banner ──
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: vaultBannerRow.implicitHeight + 18
            radius: 8
            color: "#0B1D16"
            border.color: "#059669"
            border.width: 1

            RowLayout {
                id: vaultBannerRow
                anchors.fill: parent
                anchors.margins: 10
                spacing: 10

                Text {
                    text: "🛡️"
                    font.pixelSize: 22
                    Layout.alignment: Qt.AlignVCenter
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            text: tr("vault_banner_title", "Hardware-Bound DPAPI Credential Vault")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: "#34D399"
                            Layout.fillWidth: true
                            Layout.preferredWidth: 0
                            elide: Text.ElideRight
                        }
                        Rectangle {
                            implicitWidth: encBadgeText.implicitWidth + 10
                            implicitHeight: 18
                            radius: 4
                            color: "#064E3B"
                            border.color: "#10B981"
                            border.width: 1
                            Layout.alignment: Qt.AlignVCenter
                            Text {
                                id: encBadgeText
                                anchors.centerIn: parent
                                text: "🔒 DPAPI / AES-256-GCM"
                                font.pixelSize: 9
                                font.bold: true
                                color: "#A7F3D0"
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 0
                        text: tr("vault_banner_desc", "Session cookies, tokens, and credentials are encrypted directly with Windows CryptProtectData and hardware-derived keys. Credentials are never written to disk in plaintext.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        // ── Providers List ──
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            Repeater {
                model: accountsSection.view.providersList

                delegate: Rectangle {
                    id: providerCard
                    readonly property bool isTargetProvider: accountsSection.view.highlightedProviderId === modelData.id
                    readonly property bool isHighlighted: isTargetProvider || (accountsSection.view.highlightedProviderId === "" && accountsSection.view.highlightAccountsSection)

                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    width: parent ? parent.width : 0
                    implicitHeight: cardInnerCol.implicitHeight + 20
                    radius: 8
                    color: providerCard.isHighlighted ? "#1C170E" : "#121722"
                    border.color: providerCard.isHighlighted ? "#F59E0B" : (cardHover.hovered ? "#38BDF8" : (modelData.is_logged_in ? "#1B3A30" : "#202838"))
                    border.width: providerCard.isHighlighted ? 2 : 1

                    Behavior on color { ColorAnimation { duration: 180 } }
                    Behavior on border.color { ColorAnimation { duration: 180 } }

                    SequentialAnimation on border.color {
                        running: providerCard.isHighlighted
                        loops: 6
                        ColorAnimation { to: "#FDE68A"; duration: 400; easing.type: Easing.InOutQuad }
                        ColorAnimation { to: "#F59E0B"; duration: 400; easing.type: Easing.InOutQuad }
                    }

                    Connections {
                        target: accountsSection.view
                        function onHighlightedProviderIdChanged() {
                            if (providerCard.isTargetProvider && !modelData.is_logged_in) {
                                if (modelData.supports_credentials_login) {
                                    loginDrawer.visible = true
                                    cardEditor.visible = false
                                } else {
                                    cardEditor.visible = true
                                    loginDrawer.visible = false
                                }
                            }
                        }
                    }

                    Component.onCompleted: {
                        if (providerCard.isTargetProvider && !modelData.is_logged_in) {
                            if (modelData.supports_credentials_login) {
                                loginDrawer.visible = true
                            } else {
                                cardEditor.visible = true
                            }
                        }
                    }

                    HoverHandler { id: cardHover }

                    ColumnLayout {
                        id: cardInnerCol
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0

                        // Row 1: Header
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 8

                            Text {
                                text: modelData.icon || "🔑"
                                font.pixelSize: 16
                                Layout.alignment: Qt.AlignVCenter
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 1
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: 6
                                    Text {
                                        text: modelData.name || modelData.id
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 12
                                        font.weight: Font.DemiBold
                                        color: "#F8FAFC"
                                    }
                                    Rectangle {
                                        implicitWidth: catText.implicitWidth + 8
                                        implicitHeight: 16
                                        radius: 3
                                        color: "#1A2234"
                                        border.color: "#2C394F"
                                        border.width: 1
                                        Text {
                                            id: catText
                                            anchors.centerIn: parent
                                            text: modelData.category || "Platform"
                                            font.pixelSize: 9
                                            color: "#94A3B8"
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                }
                                Text {
                                    text: modelData.domain || ""
                                    font.pixelSize: 9
                                    color: "#64748B"
                                    visible: text.length > 0
                                }
                            }

                            // Status Badge Pill
                            Rectangle {
                                implicitWidth: statusPillRow.implicitWidth + 14
                                implicitHeight: 22
                                radius: 11
                                color: modelData.is_disabled ? "#2A2112" : (modelData.is_logged_in ? "#0B2B20" : "#1A202C")
                                border.color: modelData.is_disabled ? "#F59E0B" : (modelData.is_logged_in ? "#10B981" : "#475569")
                                border.width: 1

                                Row {
                                    id: statusPillRow
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Rectangle {
                                        width: 6; height: 6; radius: 3
                                        color: modelData.is_disabled ? "#F59E0B" : (modelData.is_logged_in ? "#10B981" : "#64748B")
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Text {
                                        text: modelData.status_text || (modelData.is_logged_in ? tr("status_connected", "Connected") : tr("status_not_connected", "Not Connected"))
                                        font.pixelSize: 10
                                        font.weight: Font.Medium
                                        color: modelData.is_disabled ? "#FCD34D" : (modelData.is_logged_in ? "#34D399" : "#94A3B8")
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                            }
                        }

                        // Row 2: Feature tags (wrapping Flow bounded by card width)
                        Flow {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            width: cardInnerCol.width
                            spacing: 4
                            visible: modelData.features && modelData.features.length > 0

                            Repeater {
                                model: modelData.features
                                delegate: Rectangle {
                                    implicitWidth: featText.implicitWidth + 8
                                    implicitHeight: 18
                                    radius: 3
                                    color: "#161E2E"
                                    border.color: "#243044"
                                    border.width: 1
                                    Text {
                                        id: featText
                                        anchors.centerIn: parent
                                        text: "✓ " + modelData
                                        font.pixelSize: 9
                                        color: "#94A3B8"
                                    }
                                }
                            }
                        }

                        // Row 3: Account preview / info
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 6
                            visible: modelData.is_logged_in

                            Text {
                                text: tr("lbl_active_key", "Active Key:")
                                font.pixelSize: 10
                                color: "#64748B"
                            }
                            Rectangle {
                                implicitWidth: maskedText.implicitWidth + 10
                                implicitHeight: 20
                                radius: 4
                                color: "#090D15"
                                border.color: "#1E293B"
                                border.width: 1
                                Text {
                                    id: maskedText
                                    anchors.centerIn: parent
                                    text: modelData.masked_value || "••••••••"
                                    font.family: "Consolas, Segoe UI, monospace"
                                    font.pixelSize: 10
                                    color: "#38BDF8"
                                }
                            }
                            Item { Layout.fillWidth: true }
                        }

                        Text {
                            text: modelData.help_tip || ""
                            font.pixelSize: 10
                            color: modelData.is_disabled ? "#FCD34D" : "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            visible: !modelData.is_logged_in || Boolean(modelData.is_disabled)
                        }

                        // Row 4: Action Buttons (Flow-wrapped to seamlessly adapt to any card width)
                        Flow {
                            id: cardButtonsFlow
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            width: cardInnerCol.width
                            spacing: 6

                            // Direct Username/Password Login
                            StyledButton {
                                text: modelData.is_logged_in ? tr("btn_relogin", "Re-login") : tr("btn_login_account", "Log In")
                                iconText: "🔑"
                                variant: modelData.is_logged_in ? "outline" : "primary"
                                Layout.preferredHeight: 26
                                visible: Boolean(modelData.supports_credentials_login) && !modelData.is_disabled
                                onClicked: {
                                    cardEditor.visible = false
                                    loginDrawer.visible = !loginDrawer.visible
                                }
                            }

                            // 1-Click Browser Import
                            StyledButton {
                                text: modelData.is_logged_in ? tr("btn_reimport", "Re-import") : tr("btn_import_browser", "1-Click Import")
                                iconText: "⚡"
                                variant: "outline"
                                Layout.preferredHeight: 26
                                visible: Boolean(modelData.supports_browser_import) && !modelData.is_disabled
                                onClicked: {
                                    if (accountsSection.view.bridge) accountsSection.view.bridge.importBrowserCookiesToProvider(modelData.id, "")
                                }
                            }

                            // Paste Cookie
                            StyledButton {
                                text: tr("btn_paste_cookie", "Paste Cookie")
                                iconText: "🍪"
                                variant: (!modelData.supports_credentials_login && !modelData.is_logged_in) ? "primary" : "outline"
                                Layout.preferredHeight: 26
                                visible: !modelData.is_disabled
                                onClicked: {
                                    loginDrawer.visible = false
                                    cardEditor.visible = !cardEditor.visible
                                }
                            }

                            // Test Connection
                            StyledButton {
                                text: tr("btn_test_conn", "Test Live")
                                iconText: "🔄"
                                variant: "outline"
                                Layout.preferredHeight: 26
                                visible: modelData.is_logged_in && modelData.supports_test_connection && !modelData.is_disabled
                                onClicked: {
                                    if (accountsSection.view.bridge) accountsSection.view.bridge.validateProviderSession(modelData.id)
                                }
                            }

                            // Log Out
                            StyledButton {
                                text: tr("btn_logout", "Log Out")
                                iconText: "🚪"
                                variant: "danger"
                                Layout.preferredHeight: 26
                                visible: modelData.is_logged_in
                                onClicked: {
                                    if (accountsSection.view.bridge) accountsSection.view.bridge.clearProviderCredential(modelData.id)
                                }
                            }
                        }

                        // Live Validation / Login Result Banner
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            width: cardInnerCol.width
                            implicitHeight: valText.implicitHeight + 12
                            radius: 4
                            color: (accountsSection.view.validationResults[modelData.id] && accountsSection.view.validationResults[modelData.id].success) ? "#0A241B" : "#281216"
                            border.color: (accountsSection.view.validationResults[modelData.id] && accountsSection.view.validationResults[modelData.id].success) ? "#10B981" : "#EF4444"
                            border.width: 1
                            visible: Boolean(accountsSection.view.validationResults[modelData.id])

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 6
                                spacing: 6
                                Text {
                                    text: (accountsSection.view.validationResults[modelData.id] && accountsSection.view.validationResults[modelData.id].success) ? "✔" : "✘"
                                    color: (accountsSection.view.validationResults[modelData.id] && accountsSection.view.validationResults[modelData.id].success) ? "#34D399" : "#F87171"
                                    font.bold: true
                                    font.pixelSize: 11
                                }
                                Text {
                                    id: valText
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: accountsSection.view.validationResults[modelData.id] ? accountsSection.view.validationResults[modelData.id].message : ""
                                    color: (accountsSection.view.validationResults[modelData.id] && accountsSection.view.validationResults[modelData.id].success) ? "#A7F3D0" : "#FCA5A5"
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }

                        // Inline Account Login Drawer
                        ColumnLayout {
                            id: loginDrawer
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            width: cardInnerCol.width
                            spacing: 8
                            visible: false

                            Rectangle {
                                Layout.fillWidth: true
                                height: 1
                                color: "#242E42"
                            }

                            Text {
                                text: "🔑 " + tr("lbl_account_login", "Account Login") + " — " + modelData.name
                                font.bold: true
                                font.pixelSize: 11
                                color: "#38BDF8"
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 8

                                StyledTextField {
                                    id: loginUserField
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 80
                                    placeholderText: tr("ph_username", "Username or email...")
                                    text: modelData.username || ""
                                }

                                StyledTextField {
                                    id: loginPassField
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 80
                                    echoMode: TextInput.Password
                                    placeholderText: tr("ph_password", "Password...")
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 8

                                Item { Layout.fillWidth: true }

                                StyledButton {
                                    text: tr("btn_cancel", "Cancel")
                                    Layout.preferredHeight: 28
                                    Layout.preferredWidth: Math.max(70, contentItem.implicitWidth + 20)
                                    variant: "outline"
                                    onClicked: loginDrawer.visible = false
                                }

                                StyledButton {
                                    text: tr("btn_do_login", "Log In")
                                    iconText: "🔓"
                                    Layout.preferredHeight: 28
                                    Layout.preferredWidth: Math.max(95, contentItem.implicitWidth + 20)
                                    variant: "primary"
                                    onClicked: {
                                        if (accountsSection.view.bridge) {
                                            accountsSection.view.bridge.loginProviderWithCredentials(modelData.id, loginUserField.text, loginPassField.text)
                                            loginDrawer.visible = false
                                        }
                                    }
                                }
                            }

                            Text {
                                text: "💡 " + tr("tip_login_hint", "Direct password login securely stores your authenticated session in the DPAPI vault. If Cloudflare blocks direct login, use 1-Click Import.")
                                font.pixelSize: 10
                                color: "#64748B"
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                            }
                        }

                        // Inline Manual Cookie Editor
                        ColumnLayout {
                            id: cardEditor
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            width: cardInnerCol.width
                            spacing: 8
                            visible: false

                            Rectangle {
                                Layout.fillWidth: true
                                height: 1
                                color: "#242E42"
                            }

                            Text {
                                text: "🍪 " + tr("lbl_cookie_login", "Session Cookie / JWT") + " — " + modelData.name
                                font.bold: true
                                font.pixelSize: 11
                                color: "#F59E0B"
                            }

                            StyledTextField {
                                id: editField
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                placeholderText: tr("ph_enter_cookie", "Paste session cookie (session=...)...")
                                text: modelData.raw_cookie || ""
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 8

                                StyledButton {
                                    text: tr("btn_paste", "Paste")
                                    iconText: "📋"
                                    Layout.preferredHeight: 28
                                    Layout.preferredWidth: Math.max(80, contentItem.implicitWidth + 20)
                                    variant: "outline"
                                    onClicked: editField.paste()
                                }

                                Item { Layout.fillWidth: true }

                                StyledButton {
                                    text: tr("btn_cancel", "Cancel")
                                    Layout.preferredHeight: 28
                                    Layout.preferredWidth: Math.max(70, contentItem.implicitWidth + 20)
                                    variant: "outline"
                                    onClicked: cardEditor.visible = false
                                }

                                StyledButton {
                                    text: tr("btn_save_encrypt", "Save & Encrypt")
                                    iconText: "🔒"
                                    Layout.preferredHeight: 28
                                    Layout.preferredWidth: Math.max(125, contentItem.implicitWidth + 20)
                                    variant: "primary"
                                    onClicked: {
                                        if (accountsSection.view.bridge) {
                                            accountsSection.view.bridge.saveProviderCredential(modelData.id, editField.text.trim())
                                            cardEditor.visible = false
                                        }
                                    }
                                }
                            }

                            Text {
                                text: "💡 " + (modelData.help_tip || "")
                                font.pixelSize: 10
                                color: "#64748B"
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                visible: modelData.help_tip && modelData.help_tip.length > 0
                            }
                        }
                    }
                }
            }
        }
    }
}
