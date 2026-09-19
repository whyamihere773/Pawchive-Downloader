import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Rectangle {
    id: authModalRoot

    property bool isOpen: false
    property bool isPrivateChannel: false
    property var bridge: null
    signal continued()

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    visible: opacity > 0
    anchors.fill: parent
    color: "#D90B0D12"
    z: 1100

    opacity: isOpen ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    // Block pointer events
    MouseArea {
        anchors.fill: parent
        onClicked: {}
    }

    // Local design tokens
    QtObject {
        id: theme
        readonly property color bgCard: "#202530"
        readonly property color bgSurface: "#181B22"
        readonly property color borderSubtle: "#2A303F"
        readonly property color primary: "#38BDF8"
        readonly property color primaryHover: "#0EA5E9"
        readonly property color primaryGlow: "#1E3A5F"
        readonly property color danger: "#EF4444"
        readonly property color success: "#10B981"
        readonly property color textPrimary: "#F8FAFC"
        readonly property color textSecondary: "#94A3B8"
        readonly property color textMuted: "#64748B"
        readonly property int radiusSm: 4
        readonly property int radiusMd: 8
        readonly property int radiusLg: 12
        readonly property int fontSizeSm: 11
        readonly property int fontSizeMd: 13
        readonly property int fontSizeLg: 15
        readonly property string fontFamily: "Segoe UI, Inter, sans-serif"
    }

    // Modal Card
    Rectangle {
        id: modalContent
        width: Math.min(680, parent.width - 32)
        height: Math.min(760, parent.height - 40)
        anchors.centerIn: parent
        color: theme.bgCard
        radius: theme.radiusLg
        border.color: theme.borderSubtle
        border.width: 1
        clip: true

        transform: [
            Translate {
                id: fluidTranslate
                y: 0
            },
            Scale {
                id: fluidScale
                origin.x: modalContent.width / 2
                origin.y: modalContent.height / 2
                xScale: 1.0
                yScale: 1.0
            }
        ]

        ParallelAnimation {
            id: fluidDropAnim
            NumberAnimation {
                target: fluidTranslate
                property: "y"
                from: -42
                to: 0
                duration: 440
                easing.type: Easing.OutBack
                easing.overshoot: 1.35
            }
            SequentialAnimation {
                ParallelAnimation {
                    NumberAnimation { target: fluidScale; property: "yScale"; to: 1.045; duration: 130; easing.type: Easing.OutQuad }
                    NumberAnimation { target: fluidScale; property: "xScale"; to: 0.972; duration: 130; easing.type: Easing.OutQuad }
                }
                ParallelAnimation {
                    NumberAnimation { target: fluidScale; property: "yScale"; to: 0.955; duration: 125; easing.type: Easing.OutQuad }
                    NumberAnimation { target: fluidScale; property: "xScale"; to: 1.038; duration: 125; easing.type: Easing.OutQuad }
                }
                ParallelAnimation {
                    NumberAnimation { target: fluidScale; property: "yScale"; to: 1.018; duration: 110; easing.type: Easing.OutQuad }
                    NumberAnimation { target: fluidScale; property: "xScale"; to: 0.988; duration: 110; easing.type: Easing.OutQuad }
                }
                ParallelAnimation {
                    NumberAnimation { target: fluidScale; property: "yScale"; to: 1.0; duration: 95; easing.type: Easing.OutQuad }
                    NumberAnimation { target: fluidScale; property: "xScale"; to: 1.0; duration: 95; easing.type: Easing.OutQuad }
                }
            }
        }

        ParallelAnimation {
            id: fluidSinkAnim
            NumberAnimation {
                target: fluidTranslate
                property: "y"
                to: 24
                duration: 180
                easing.type: Easing.InQuad
            }
            ParallelAnimation {
                NumberAnimation { target: fluidScale; property: "yScale"; to: 0.92; duration: 180; easing.type: Easing.InQuad }
                NumberAnimation { target: fluidScale; property: "xScale"; to: 0.95; duration: 180; easing.type: Easing.InQuad }
            }
        }

        Connections {
            target: authModalRoot
            function onIsOpenChanged() {
                if (authModalRoot.isOpen) {
                    fluidDropAnim.restart()
                } else {
                    fluidSinkAnim.restart()
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            // ── Header ────────────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    width: 38
                    height: 38
                    radius: 8
                    color: "#1E3A5F"
                    border.color: "#38BDF8"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "✈️"
                        font.pixelSize: 18
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: authModalRoot.isPrivateChannel
                              ? tr("tg_auth_title_private", "Private Telegram Channel — Account Required")
                              : tr("tg_auth_title", "Connect Telegram Account")
                        font.pixelSize: theme.fontSizeLg
                        font.bold: true
                        font.family: theme.fontFamily
                        color: theme.textPrimary
                    }

                    Text {
                        text: (telegramBridge && telegramBridge.isLoggedIn)
                            ? tr("tg_auth_connected_sub", "Account connected! Click Continue to proceed.")
                            : tr("tg_auth_subtitle", "Connect your account to unlock Telegram downloads.")
                        font.pixelSize: theme.fontSizeSm
                        font.family: theme.fontFamily
                        color: (telegramBridge && telegramBridge.isLoggedIn) ? theme.success : theme.textSecondary
                    }
                }

                StyledButton {
                    text: "✕"
                    implicitWidth: 32
                    implicitHeight: 32
                    variant: "ghost"
                    onClicked: {
                        if (telegramBridge) telegramBridge.cancelQrLogin()
                        authModalRoot.isOpen = false
                    }
                }
            }

            // ── Private Channel Banner (if triggered by private link) ─────────
            Rectangle {
                visible: authModalRoot.isPrivateChannel
                Layout.fillWidth: true
                implicitHeight: privLayout.implicitHeight + 16
                radius: theme.radiusMd
                color: "#2D2012"
                border.color: "#F59E0B"
                border.width: 1

                RowLayout {
                    id: privLayout
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10

                    Text {
                        text: "🔒"
                        font.pixelSize: 18
                    }

                    Text {
                        Layout.fillWidth: true
                        text: tr("tg_private_warn", "Private Channel Detected: You must be a member of this channel with the connected account to access and download its media files.")
                        font.pixelSize: theme.fontSizeSm
                        font.family: theme.fontFamily
                        color: "#FDE68A"
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // ── Scrollable Body ───────────────────────────────────────────────
            SmoothFlickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: mainCol.implicitHeight + 10

                ColumnLayout {
                    id: mainCol
                    width: parent.width - 8
                    spacing: 14

                    // ── ⚠️ Prominent Red Disclaimer of Liability ───────────────
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: disclaimerCol.implicitHeight + 20
                        radius: theme.radiusMd
                        color: "#2B1114"
                        border.color: theme.danger
                        border.width: 1.5

                        ColumnLayout {
                            id: disclaimerCol
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 6

                            RowLayout {
                                spacing: 6
                                Text {
                                    text: "⚠️"
                                    font.pixelSize: 16
                                }
                                Text {
                                    text: tr("tg_disclaimer_title", "DISCLAIMER OF LIABILITY")
                                    font.pixelSize: theme.fontSizeSm
                                    font.bold: true
                                    font.family: theme.fontFamily
                                    color: theme.danger
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: tr("tg_disclaimer_text", "I, as the developer of this application, provide this tool solely for personal archival, backup, and educational purposes. I assume no liability or responsibility for any account suspensions, bans, rate-limit restrictions, data loss, or damages resulting from the use or misuse of Telegram integration. Telegram strictly monitors automated activity and mass downloads. By proceeding and connecting an account, you acknowledge that you do so entirely at your own discretion and risk.")
                                font.pixelSize: theme.fontSizeSm
                                font.bold: true
                                font.family: theme.fontFamily
                                color: theme.danger
                                wrapMode: Text.WordWrap
                                lineHeight: 1.3
                            }
                        }
                    }

                    // ── Collapsible Ban Prevention & Safety Guide ─────────────
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: guideCol.implicitHeight + 16
                        radius: theme.radiusMd
                        color: theme.bgSurface
                        border.color: theme.borderSubtle
                        border.width: 1

                        ColumnLayout {
                            id: guideCol
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 8

                            MouseArea {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 24
                                cursorShape: Qt.PointingHandCursor
                                onClicked: guideDetails.visible = !guideDetails.visible

                                RowLayout {
                                    anchors.fill: parent
                                    spacing: 8

                                    Text {
                                        text: "🛡️"
                                        font.pixelSize: 14
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: tr("tg_guide_title", "Account Safety & Ban Prevention Guide")
                                        font.pixelSize: theme.fontSizeMd
                                        font.bold: true
                                        font.family: theme.fontFamily
                                        color: theme.textPrimary
                                    }

                                    Text {
                                        text: guideDetails.visible ? "▲" : "▼"
                                        font.pixelSize: 10
                                        color: theme.textSecondary
                                    }
                                }
                            }

                            ColumnLayout {
                                id: guideDetails
                                Layout.fillWidth: true
                                spacing: 8
                                visible: false

                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 1
                                    color: theme.borderSubtle
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: tr("tg_guide_text", "• Use a Secondary / Burner Account: Never use your primary personal Telegram account (with family & friends) for mass downloading. Keep them separate.\n• Warm Up Fresh Accounts: Accounts registered within the last few weeks with virtual/VoIP numbers have zero trust score. Let new accounts age and participate in normal chat activity first.\n• Never Scrape Members: Telegram issues instant bans to automated scrapers that harvest user lists or send mass DMs. Pawchive only reads media attachments.\n• Respect Cooldowns: When Telegram asks to wait ('FloodWait'), Pawchive automatically sleeps and resumes. Never try to bypass rate-limit timers.")
                                    font.pixelSize: theme.fontSizeSm
                                    font.family: theme.fontFamily
                                    color: theme.textSecondary
                                    wrapMode: Text.WordWrap
                                    lineHeight: 1.35
                                }
                            }
                        }
                    }

                    // ── Active Connected Account View ─────────────────────────
                    Rectangle {
                        visible: telegramBridge && telegramBridge.isLoggedIn
                        Layout.fillWidth: true
                        implicitHeight: connLayout.implicitHeight + 20
                        radius: theme.radiusMd
                        color: "#0F2E22"
                        border.color: theme.success
                        border.width: 1

                        RowLayout {
                            id: connLayout
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 12

                            Rectangle {
                                width: 36
                                height: 36
                                radius: 18
                                color: theme.success

                                // Fluid surface tension aura ring
                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: -3
                                    radius: 21
                                    color: "transparent"
                                    border.color: theme.success
                                    border.width: 1
                                    opacity: 0.35

                                    SequentialAnimation on opacity {
                                        loops: Animation.Infinite
                                        running: telegramBridge && telegramBridge.isLoggedIn
                                        NumberAnimation { to: 0.85; duration: 1600; easing.type: Easing.InOutSine }
                                        NumberAnimation { to: 0.20; duration: 1600; easing.type: Easing.InOutSine }
                                    }
                                }

                                Text {
                                    anchors.centerIn: parent
                                    text: "✓"
                                    font.pixelSize: 18
                                    font.bold: true
                                    color: "#FFFFFF"
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2

                                Text {
                                    text: tr("tg_status_connected", "Connected to Telegram")
                                    font.pixelSize: theme.fontSizeMd
                                    font.bold: true
                                    color: theme.textPrimary
                                }

                                Text {
                                    text: (telegramBridge ? "@" + telegramBridge.currentUsername : "") +
                                          (telegramBridge && telegramBridge.currentPhone ? " (" + telegramBridge.currentPhone + ")" : "")
                                    font.pixelSize: theme.fontSizeSm
                                    color: theme.textSecondary
                                }
                            }

                            StyledButton {
                                text: tr("tg_btn_logout", "Disconnect")
                                implicitWidth: 100
                                implicitHeight: 32
                                variant: "danger"
                                onClicked: {
                                    if (telegramBridge) telegramBridge.disconnectAccount()
                                }
                            }
                        }
                    }

                    // ── Authentication Flow (Shown when NOT logged in) ─────────
                    ColumnLayout {
                        visible: !telegramBridge || !telegramBridge.isLoggedIn
                        Layout.fillWidth: true
                        spacing: 12

                        // Tab Bar for Auth Methods
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Repeater {
                                model: [
                                    { name: tr("tg_tab_qr", "📱 QR Code (Recommended)"), tabId: 0 },
                                    { name: tr("tg_tab_phone", "📞 Phone & SMS"), tabId: 1 },
                                    { name: tr("tg_tab_bot", "🤖 Bot Token"), tabId: 2 }
                                ]

                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 34
                                    radius: theme.radiusSm
                                    color: authTabs.currentTab === modelData.tabId ? theme.primaryGlow : theme.bgSurface
                                    border.color: authTabs.currentTab === modelData.tabId ? theme.primary : theme.borderSubtle
                                    border.width: 1

                                    scale: tabMouse.pressed ? 0.94 : (tabMouse.containsMouse ? 1.025 : 1.0)
                                    Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.32; mass: 1.8 } }
                                    Behavior on color { ColorAnimation { duration: 160 } }
                                    Behavior on border.color { ColorAnimation { duration: 160 } }

                                    MouseArea {
                                        id: tabMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            authTabs.currentTab = modelData.tabId
                                            if (modelData.tabId === 0 && telegramBridge && !telegramBridge.isLoggedIn) {
                                                telegramBridge.startQrLogin()
                                            } else if (modelData.tabId !== 0 && telegramBridge) {
                                                telegramBridge.cancelQrLogin()
                                            }
                                        }
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.name
                                        font.pixelSize: theme.fontSizeSm
                                        font.bold: authTabs.currentTab === modelData.tabId
                                        color: authTabs.currentTab === modelData.tabId ? theme.primary : theme.textSecondary
                                    }
                                }
                            }
                        }

                        Item { id: authTabs; property int currentTab: 0 }

                        // ── Tab 0: QR Code Login ──────────────────────────────
                        ColumnLayout {
                            visible: authTabs.currentTab === 0 && (!telegramBridge || telegramBridge.loginState !== "need_2fa")
                            Layout.fillWidth: true
                            spacing: 12

                            Rectangle {
                                id: qrContainer
                                Layout.alignment: Qt.AlignHCenter
                                width: 220
                                height: 220
                                radius: theme.radiusMd
                                color: "#0B0D12"
                                border.color: theme.primary
                                border.width: 1.5

                                // Fluid surface tension breathing aura
                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: -4
                                    radius: theme.radiusMd + 4
                                    color: "transparent"
                                    border.color: theme.primary
                                    border.width: 1.5
                                    opacity: 0.35
                                    z: -1

                                    SequentialAnimation on opacity {
                                        loops: Animation.Infinite
                                        running: authModalRoot.isOpen && (!telegramBridge || !telegramBridge.isLoggedIn)
                                        NumberAnimation { to: 0.75; duration: 1500; easing.type: Easing.InOutSine }
                                        NumberAnimation { to: 0.18; duration: 1500; easing.type: Easing.InOutSine }
                                    }
                                    SequentialAnimation on anchors.margins {
                                        loops: Animation.Infinite
                                        running: authModalRoot.isOpen && (!telegramBridge || !telegramBridge.isLoggedIn)
                                        NumberAnimation { to: -6; duration: 1500; easing.type: Easing.InOutSine }
                                        NumberAnimation { to: -3; duration: 1500; easing.type: Easing.InOutSine }
                                    }
                                }

                                // Fluid hydrodynamic buoyant hover
                                scale: qrMouse.containsMouse ? 1.025 : 1.0
                                transform: Translate {
                                    y: qrMouse.containsMouse ? -3 : 0
                                    Behavior on y { SpringAnimation { spring: 3.5; damping: 0.32; mass: 2.0 } }
                                }
                                Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.32; mass: 2.0 } }

                                MouseArea {
                                    id: qrMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                }

                                Image {
                                    anchors.centerIn: parent
                                    width: 200
                                    height: 200
                                    source: telegramBridge ? telegramBridge.qrCodeDataUrl : ""
                                    fillMode: Image.PreserveAspectFit
                                    visible: telegramBridge && telegramBridge.qrCodeDataUrl.length > 0
                                }

                                ColumnLayout {
                                    anchors.centerIn: parent
                                    visible: !telegramBridge || telegramBridge.qrCodeDataUrl.length === 0
                                    spacing: 8

                                    BusyIndicator {
                                        Layout.alignment: Qt.AlignHCenter
                                        running: true
                                    }

                                    Text {
                                        text: tr("tg_loading_qr", "Generating QR Code...")
                                        font.pixelSize: theme.fontSizeSm
                                        color: theme.textSecondary
                                    }
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                horizontalAlignment: Text.AlignHCenter
                                text: tr("tg_qr_instructions", "1. Open Telegram on your phone\n2. Go to Settings → Devices → Link Desktop Device\n3. Point your phone camera at this screen to log in")
                                font.pixelSize: theme.fontSizeSm
                                font.family: theme.fontFamily
                                color: theme.textSecondary
                                lineHeight: 1.3
                            }
                        }

                        // ── Tab 1: Phone Number Login ─────────────────────────
                        ColumnLayout {
                            visible: authTabs.currentTab === 1 && (!telegramBridge || telegramBridge.loginState !== "need_2fa")
                            Layout.fillWidth: true
                            spacing: 10

                            Text {
                                text: tr("tg_phone_label", "Enter your phone number with country code (e.g. +1234567890):")
                                font.pixelSize: theme.fontSizeSm
                                color: theme.textSecondary
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                StyledTextField {
                                    id: phoneInput
                                    Layout.fillWidth: true
                                    placeholderText: "+1 555 123 4567"
                                }

                                StyledButton {
                                    text: tr("tg_btn_send_code", "Send Code")
                                    implicitWidth: 110
                                    implicitHeight: 34
                                    variant: "primary"
                                    onClicked: {
                                        if (phoneInput.text.trim().length > 0 && telegramBridge) {
                                            telegramBridge.sendPhoneCode(phoneInput.text.trim())
                                        }
                                    }
                                }
                            }

                            // Code verification section
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                visible: telegramBridge && telegramBridge.loginState === "code_sent"

                                Text {
                                    text: tr("tg_code_label", "Enter the 5-digit verification code received:")
                                    font.pixelSize: theme.fontSizeSm
                                    color: theme.textSecondary
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    StyledTextField {
                                        id: codeInput
                                        Layout.fillWidth: true
                                        placeholderText: "12345"
                                    }

                                    StyledButton {
                                        text: tr("tg_btn_verify", "Verify & Log In")
                                        implicitWidth: 120
                                        implicitHeight: 34
                                        variant: "success"
                                        onClicked: {
                                            if (codeInput.text.trim().length > 0 && telegramBridge) {
                                                telegramBridge.verifyPhoneCode(codeInput.text.trim())
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ── Tab 2: Bot Token Login ────────────────────────────
                        ColumnLayout {
                            visible: authTabs.currentTab === 2 && (!telegramBridge || telegramBridge.loginState !== "need_2fa")
                            Layout.fillWidth: true
                            spacing: 10

                            Text {
                                text: tr("tg_bot_label", "Enter your Telegram Bot Token (from @BotFather):")
                                font.pixelSize: theme.fontSizeSm
                                color: theme.textSecondary
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                StyledTextField {
                                    id: botTokenInput
                                    Layout.fillWidth: true
                                    placeholderText: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                                }

                                StyledButton {
                                    text: tr("tg_btn_connect_bot", "Connect Bot")
                                    implicitWidth: 120
                                    implicitHeight: 34
                                    variant: "primary"
                                    onClicked: {
                                        if (botTokenInput.text.trim().length > 0 && telegramBridge) {
                                            telegramBridge.loginWithBotToken(botTokenInput.text.trim())
                                        }
                                    }
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: tr("tg_bot_note", "Note: Telegram Bot API limits file downloads to 20–50 MB and can only access public channels or chats where the bot is added.")
                                font.pixelSize: 11
                                color: theme.textMuted
                                wrapMode: Text.WordWrap
                            }
                        }

                        // ── 2FA Cloud Password Prompt ─────────────────────────
                        ColumnLayout {
                            visible: telegramBridge && telegramBridge.loginState === "need_2fa"
                            Layout.fillWidth: true
                            spacing: 10

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: twoFaCol.implicitHeight + 16
                                radius: theme.radiusMd
                                color: "#1F1B2E"
                                border.color: "#A855F7"
                                border.width: 1

                                ColumnLayout {
                                    id: twoFaCol
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 8

                                    Text {
                                        text: tr("tg_2fa_title", "🔑 Two-Step Verification (2FA) Cloud Password")
                                        font.pixelSize: theme.fontSizeMd
                                        font.bold: true
                                        color: "#E9D5FF"
                                    }

                                    Text {
                                        text: tr("tg_2fa_desc", "This Telegram account is protected with a cloud password. Enter it below to complete login:")
                                        font.pixelSize: theme.fontSizeSm
                                        color: theme.textSecondary
                                        wrapMode: Text.WordWrap
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8

                                        StyledTextField {
                                            id: twoFaInput
                                            Layout.fillWidth: true
                                            placeholderText: "Your 2FA Password"
                                            echoMode: TextInput.Password
                                        }

                                        StyledButton {
                                            text: tr("tg_btn_submit_2fa", "Unlock")
                                            implicitWidth: 90
                                            implicitHeight: 34
                                            variant: "primary"
                                            onClicked: {
                                                if (twoFaInput.text.length > 0 && telegramBridge) {
                                                    telegramBridge.submit2faPassword(twoFaInput.text)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Status message feedback
                        Text {
                            visible: telegramBridge && telegramBridge.statusMessage.length > 0
                            Layout.fillWidth: true
                            text: telegramBridge ? telegramBridge.statusMessage : ""
                            font.pixelSize: theme.fontSizeSm
                            color: (telegramBridge && telegramBridge.loginState === "error") ? theme.danger : theme.primary
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }
                }
            }

            // ── Footer ────────────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Item { Layout.fillWidth: true }

                StyledButton {
                    visible: telegramBridge && telegramBridge.isLoggedIn
                    text: tr("btn_close", "Close")
                    implicitWidth: 90
                    implicitHeight: 34
                    variant: "ghost"
                    onClicked: {
                        authModalRoot.isOpen = false
                    }
                }

                StyledButton {
                    id: footerActionBtn
                    text: (telegramBridge && telegramBridge.isLoggedIn)
                        ? tr("btn_continue", "Continue →")
                        : tr("btn_close", "Close")
                    implicitWidth: (telegramBridge && telegramBridge.isLoggedIn) ? 135 : 100
                    implicitHeight: 34
                    variant: (telegramBridge && telegramBridge.isLoggedIn) ? "primary" : "outline"

                    Behavior on implicitWidth {
                        NumberAnimation { duration: 250; easing.type: Easing.OutBack; easing.overshoot: 1.3 }
                    }

                    onClicked: {
                        var wasLoggedIn = telegramBridge && telegramBridge.isLoggedIn
                        if (!wasLoggedIn && telegramBridge) {
                            telegramBridge.cancelQrLogin()
                        }
                        authModalRoot.isOpen = false
                        if (wasLoggedIn) {
                            authModalRoot.continued()
                        }
                    }
                }
            }
        }
    }

    onIsOpenChanged: {
        if (isOpen && telegramBridge && !telegramBridge.isLoggedIn) {
            telegramBridge.startQrLogin()
        }
    }
}
