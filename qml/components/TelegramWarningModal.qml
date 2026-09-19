import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Rectangle {
    id: warningModalRoot

    property bool isOpen: false
    property int currentStep: 1  // 1 = Safety Warning, 2 = Liability Disclaimer
    property var bridge: null

    signal accepted()
    signal cancelled()

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    function open() {
        chkDontShowSafety.checked = false
        chkDontShowLiability.checked = false
        if (bridge && bridge.telegramSafetyAcknowledged) {
            currentStep = 2
        } else {
            currentStep = 1
        }
        isOpen = true
    }

    function close() {
        isOpen = false
        cancelled()
    }

    visible: opacity > 0
    anchors.fill: parent
    color: "#D90B0D12"
    z: 1150

    opacity: isOpen ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: {}
    }

    // Local design tokens
    QtObject {
        id: theme
        readonly property color bgCard: "#1C202B"
        readonly property color bgSurface: "#141720"
        readonly property color borderSubtle: "#283042"
        readonly property color primary: "#38BDF8"
        readonly property color primaryHover: "#0EA5E9"
        readonly property color primaryGlow: "#1E3A5F"
        readonly property color warning: "#F59E0B"
        readonly property color warningBg: "#241D12"
        readonly property color warningBorder: "#D97706"
        readonly property color danger: "#EF4444"
        readonly property color dangerBg: "#251216"
        readonly property color dangerBorder: "#DC2626"
        readonly property color textPrimary: "#F8FAFC"
        readonly property color textSecondary: "#94A3B8"
        readonly property color textMuted: "#64748B"
        readonly property int radiusSm: 6
        readonly property int radiusMd: 8
        readonly property int radiusLg: 12
        readonly property string fontFamily: "Segoe UI, Inter, sans-serif"
    }

    // Modal Card
    Rectangle {
        id: modalContent
        width: Math.min(580, parent.width - 32)
        height: Math.min(600, parent.height - 40)
        anchors.centerIn: parent
        color: theme.bgCard
        radius: theme.radiusLg
        border.color: currentStep === 2 ? theme.dangerBorder : theme.borderSubtle
        border.width: currentStep === 2 ? 1.5 : 1
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
            target: warningModalRoot
            function onIsOpenChanged() {
                if (warningModalRoot.isOpen) {
                    fluidDropAnim.restart()
                } else {
                    fluidSinkAnim.restart()
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14

            // ── Header ────────────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    width: 42
                    height: 42
                    radius: theme.radiusMd
                    color: currentStep === 2 ? "#3B1219" : "#32200E"
                    border.color: currentStep === 2 ? theme.danger : theme.warning
                    border.width: 1

                    // Fluid surface tension breathing aura
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -3
                        radius: theme.radiusMd + 3
                        color: "transparent"
                        border.color: currentStep === 2 ? theme.danger : theme.warning
                        border.width: 1.5
                        opacity: 0.35

                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            running: warningModalRoot.isOpen
                            NumberAnimation { to: 0.85; duration: 1500; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 0.15; duration: 1500; easing.type: Easing.InOutSine }
                        }
                        SequentialAnimation on scale {
                            loops: Animation.Infinite
                            running: warningModalRoot.isOpen
                            NumberAnimation { to: 1.06; duration: 1500; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 1.00; duration: 1500; easing.type: Easing.InOutSine }
                        }
                    }

                    Behavior on color { ColorAnimation { duration: 200 } }
                    Behavior on border.color { ColorAnimation { duration: 200 } }

                    Text {
                        anchors.centerIn: parent
                        text: currentStep === 2 ? "🚨" : "🛡️"
                        font.pixelSize: 20
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: currentStep === 2
                            ? tr("tg_warn_modal_title2", "Developer Disclaimer & Liability Notice")
                            : tr("tg_warn_modal_title1", "Telegram Account Safety Advisory")
                        font.family: theme.fontFamily
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        color: currentStep === 2 ? "#FCA5A5" : theme.textPrimary
                    }

                    Text {
                        text: currentStep === 2
                            ? tr("tg_warn_modal_sub2", "Step 2 of 2: Terms of Use & Developer Disclaimer")
                            : tr("tg_warn_modal_sub1", "Step 1 of 2: Important MTProto anti-ban recommendations")
                        font.family: theme.fontFamily
                        font.pixelSize: 11
                        color: theme.textSecondary
                    }
                }

                // Close Button
                Rectangle {
                    width: 28
                    height: 28
                    radius: 14
                    color: closeBtnMouse.containsMouse ? "#2A3245" : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        color: theme.textSecondary
                        font.pixelSize: 12
                    }

                    MouseArea {
                        id: closeBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: warningModalRoot.close()
                    }
                }
            }

            // ── Step Progress Indicator ───────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                // Step 1 Pill
                Rectangle {
                    Layout.fillWidth: true
                    height: 26
                    radius: theme.radiusSm
                    color: currentStep === 1 ? "#2E2412" : "#141720"
                    border.color: currentStep === 1 ? theme.warning : "#242C3D"
                    border.width: 1

                    RowLayout {
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: (bridge && bridge.telegramSafetyAcknowledged) ? "✓" : "1"
                            font.family: theme.fontFamily
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: currentStep === 1 ? theme.warning : (bridge && bridge.telegramSafetyAcknowledged ? "#10B981" : theme.textMuted)
                        }
                        Text {
                            text: tr("tg_step_safety", "Account Safety")
                            font.family: theme.fontFamily
                            font.pixelSize: 11
                            font.weight: currentStep === 1 ? Font.Bold : Font.Normal
                            color: currentStep === 1 ? theme.textPrimary : theme.textMuted
                        }
                    }
                }

                // Step 2 Pill
                Rectangle {
                    Layout.fillWidth: true
                    height: 26
                    radius: theme.radiusSm
                    color: currentStep === 2 ? "#331216" : "#141720"
                    border.color: currentStep === 2 ? theme.danger : "#242C3D"
                    border.width: 1

                    RowLayout {
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: (bridge && bridge.telegramLiabilityAcknowledged) ? "✓" : "2"
                            font.family: theme.fontFamily
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: currentStep === 2 ? "#FCA5A5" : (bridge && bridge.telegramLiabilityAcknowledged ? "#10B981" : theme.textMuted)
                        }
                        Text {
                            text: tr("tg_step_liability", "Liability Disclaimer")
                            font.family: theme.fontFamily
                            font.pixelSize: 11
                            font.weight: currentStep === 2 ? Font.Bold : Font.Normal
                            color: currentStep === 2 ? theme.textPrimary : theme.textMuted
                        }
                    }
                }
            }

            // ── Body: Stack depending on step ─────────────────────────────────
            StackLayout {
                id: stepStack
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: currentStep - 1

                // ════════════ STEP 1: SAFETY ADVISORY ════════════
                ColumnLayout {
                    spacing: 12

                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentHeight: step1Content.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds

                        ColumnLayout {
                            id: step1Content
                            width: parent.width
                            spacing: 10

                            // Top Advisory Box
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: advCol.implicitHeight + 16
                                radius: theme.radiusMd
                                color: theme.warningBg
                                border.color: theme.warningBorder
                                border.width: 1

                                ColumnLayout {
                                    id: advCol
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 4

                                    RowLayout {
                                        spacing: 6
                                        Text {
                                            text: "⚠️"
                                            font.pixelSize: 13
                                        }
                                        Text {
                                            text: tr("tg_adv_banner_title", "Important Notice: MTProto Anti-Ban Protections")
                                            font.family: theme.fontFamily
                                            font.pixelSize: 12
                                            font.weight: Font.Bold
                                            color: "#FCD34D"
                                        }
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: tr("tg_adv_banner_desc", "Telegram's servers actively detect high-volume file scraping. Please read these recommendations carefully before continuing:")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 11
                                        color: "#FDE68A"
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }

                            // 4 Key Advisory Cards
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: card1Col.implicitHeight + 14
                                radius: theme.radiusSm
                                color: theme.bgSurface
                                border.color: theme.borderSubtle
                                border.width: 1

                                ColumnLayout {
                                    id: card1Col
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 3

                                    Text {
                                        text: "🚫 " + tr("tg_adv_ban_title", "Account Ban & Suspension Risk")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 12
                                        font.weight: Font.Bold
                                        color: "#F87171"
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: tr("tg_adv_ban_desc", "Aggressive mass querying can trigger Telegram's automated spam filters, resulting in temporary FloodWait locks or permanent phone number bans.")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 11
                                        color: theme.textSecondary
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: card2Col.implicitHeight + 14
                                radius: theme.radiusSm
                                color: theme.bgSurface
                                border.color: theme.borderSubtle
                                border.width: 1

                                ColumnLayout {
                                    id: card2Col
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 3

                                    Text {
                                        text: "👤 " + tr("tg_adv_burner_title", "Use Burner / Secondary Accounts")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 12
                                        font.weight: Font.Bold
                                        color: "#38BDF8"
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: tr("tg_adv_burner_desc", "NEVER use your primary personal Telegram phone number. Always use a dedicated secondary or throwaway account to protect personal chats and contacts.")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 11
                                        color: theme.textSecondary
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: card3Col.implicitHeight + 14
                                radius: theme.radiusSm
                                color: theme.bgSurface
                                border.color: theme.borderSubtle
                                border.width: 1

                                ColumnLayout {
                                    id: card3Col
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 3

                                    Text {
                                        text: "⏱️ " + tr("tg_adv_flood_title", "Automatic FloodWait Backoff")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 12
                                        font.weight: Font.Bold
                                        color: "#FBBF24"
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: tr("tg_adv_flood_desc", "Pawchive includes rate limiting and cooldown algorithms. If Telegram returns a FloodWait error, the app will pause and wait out the cooldown automatically.")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 11
                                        color: theme.textSecondary
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                    }

                    // Checkbox: Do not show again for safety
                    StyledCheckBox {
                        id: chkDontShowSafety
                        Layout.fillWidth: true
                        text: tr("tg_chk_dont_show_safety", "Do not show this safety advice again")
                        accentColor: theme.warning
                    }

                    // Action Buttons for Step 1
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        StyledButton {
                            text: tr("btn_cancel", "Cancel")
                            variant: "outline"
                            Layout.preferredHeight: 34
                            Layout.preferredWidth: 90
                            onClicked: warningModalRoot.close()
                        }

                        Item { Layout.fillWidth: true }

                        StyledButton {
                            text: tr("tg_btn_next_liability", "Next: Liability Terms →")
                            variant: "primary"
                            Layout.preferredHeight: 34
                            Layout.preferredWidth: 175
                            onClicked: {
                                if (chkDontShowSafety.checked && bridge) {
                                    bridge.telegramSafetyAcknowledged = true
                                }
                                warningModalRoot.currentStep = 2
                            }
                        }
                    }
                }

                // ════════════ STEP 2: DEVELOPER LIABILITY DISCLAIMER ════════════
                ColumnLayout {
                    spacing: 12

                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentHeight: step2Content.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds

                        ColumnLayout {
                            id: step2Content
                            width: parent.width
                            spacing: 10

                            // Prominent Red Liability Box
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: redBoxCol.implicitHeight + 20
                                radius: theme.radiusMd
                                color: theme.dangerBg
                                border.color: theme.dangerBorder
                                border.width: 1.5

                                ColumnLayout {
                                    id: redBoxCol
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 8

                                    RowLayout {
                                        spacing: 8
                                        Text {
                                            text: "🚨"
                                            font.pixelSize: 16
                                        }
                                        Text {
                                            text: tr("tg_legal_header", "DEVELOPER DISCLAIMER & LIMITATION OF LIABILITY")
                                            font.family: theme.fontFamily
                                            font.pixelSize: 12
                                            font.weight: Font.Bold
                                            color: "#F87171"
                                        }
                                    }

                                    // Main first-person developer liability message
                                    Text {
                                        Layout.fillWidth: true
                                        text: tr("tg_liability_statement", "I, as the developer of Pawchive Downloader, assume no responsibility or liability whatsoever for any account bans, suspensions, phone restrictions, channel removals, data loss, or damages resulting from the use of this software with Telegram.\n\nTelegram strictly regulates automated and third-party MTProto client usage under its Terms of Service. You proceed entirely at your own risk and discretion.")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 12
                                        font.weight: Font.DemiBold
                                        color: "#FEE2E2"
                                        wrapMode: Text.WordWrap
                                        lineHeight: 1.25
                                    }
                                }
                            }

                            // Terms recap points
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: recapCol.implicitHeight + 14
                                radius: theme.radiusSm
                                color: theme.bgSurface
                                border.color: theme.borderSubtle
                                border.width: 1

                                ColumnLayout {
                                    id: recapCol
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 6

                                    Text {
                                        text: tr("tg_recap_title", "Key Terms Summary:")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 11
                                        font.weight: Font.Bold
                                        color: theme.textSecondary
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: "• " + tr("tg_recap_1", "Compliance with Telegram's Terms of Service is solely your personal responsibility.")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 11
                                        color: theme.textSecondary
                                        wrapMode: Text.WordWrap
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: "• " + tr("tg_recap_2", "The developer does not and cannot guarantee immunity against account restrictions or rate bans.")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 11
                                        color: theme.textSecondary
                                        wrapMode: Text.WordWrap
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: "• " + tr("tg_recap_3", "All connection sessions and download requests are executed locally on your machine.")
                                        font.family: theme.fontFamily
                                        font.pixelSize: 11
                                        color: theme.textSecondary
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                    }

                    // Checkbox: Do not show again for liability
                    StyledCheckBox {
                        id: chkDontShowLiability
                        Layout.fillWidth: true
                        text: tr("tg_chk_dont_show_liability", "Do not show this liability disclaimer again")
                        accentColor: theme.danger
                    }

                    // Action Buttons for Step 2
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        StyledButton {
                            text: tr("btn_back", "← Back")
                            variant: "outline"
                            Layout.preferredHeight: 34
                            Layout.preferredWidth: 80
                            visible: !(bridge && bridge.telegramSafetyAcknowledged)
                            onClicked: warningModalRoot.currentStep = 1
                        }

                        StyledButton {
                            text: tr("btn_decline", "Decline / Cancel")
                            variant: "ghost"
                            Layout.preferredHeight: 34
                            Layout.preferredWidth: 120
                            onClicked: warningModalRoot.close()
                        }

                        Item { Layout.fillWidth: true }

                        StyledButton {
                            text: tr("tg_btn_accept", "Accept & Proceed →")
                            variant: "danger"
                            Layout.preferredHeight: 34
                            Layout.preferredWidth: 155
                            onClicked: {
                                if (chkDontShowLiability.checked && bridge) {
                                    bridge.telegramLiabilityAcknowledged = true
                                }
                                warningModalRoot.isOpen = false
                                warningModalRoot.accepted()
                            }
                        }
                    }
                }
            }
        }
    }
}
