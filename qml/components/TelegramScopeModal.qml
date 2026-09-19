import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Rectangle {
    id: scopeModalRoot

    property bool isOpen: false
    property string targetChannelId: ""
    property string targetRawUrl: ""
    property bool isPrivateChannel: false
    property string channelTitle: "Telegram Channel"
    property bool isLoading: false
    property string defaultAction: "download" // "download" or "select"

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
        readonly property color success: "#10B981"
        readonly property color textPrimary: "#F8FAFC"
        readonly property color textSecondary: "#94A3B8"
        readonly property int radiusMd: 8
        readonly property int radiusLg: 12
        readonly property int fontSizeSm: 11
        readonly property int fontSizeMd: 13
        readonly property int fontSizeLg: 15
        readonly property string fontFamily: "Segoe UI, Inter, sans-serif"
    }

    Rectangle {
        id: modalContent
        width: Math.min(560, parent.width - 32)
        height: Math.min(620, parent.height - 40)
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
            target: scopeModalRoot
            function onIsOpenChanged() {
                if (scopeModalRoot.isOpen) {
                    fluidDropAnim.restart()
                } else {
                    fluidSinkAnim.restart()
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 14

            // ── Header ────────────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    width: 44
                    height: 44
                    radius: 22
                    color: "#1E3A5F"
                    border.color: theme.primary
                    border.width: 1

                    // Fluid surface tension aura ring
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -3
                        radius: 25
                        color: "transparent"
                        border.color: theme.primary
                        border.width: 1
                        opacity: 0.4

                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            running: scopeModalRoot.isOpen
                            NumberAnimation { to: 0.85; duration: 1600; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 0.20; duration: 1600; easing.type: Easing.InOutSine }
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: "✈️"
                        font.pixelSize: 22
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: scopeModalRoot.channelTitle
                        font.pixelSize: theme.fontSizeLg
                        font.bold: true
                        color: theme.textPrimary
                        elide: Text.ElideRight
                    }

                    RowLayout {
                        spacing: 6
                        Rectangle {
                            height: 18
                            width: tagText.implicitWidth + 10
                            radius: 9
                            color: scopeModalRoot.isPrivateChannel ? "#78350F" : "#0C4A6E"

                            Text {
                                id: tagText
                                anchors.centerIn: parent
                                text: scopeModalRoot.isPrivateChannel ? "Private Channel" : "Public Channel"
                                font.pixelSize: 10
                                font.bold: true
                                color: scopeModalRoot.isPrivateChannel ? "#FDE68A" : "#BAE6FD"
                            }
                        }

                        Text {
                            text: scopeModalRoot.targetChannelId ? "@" + scopeModalRoot.targetChannelId : ""
                            font.pixelSize: theme.fontSizeSm
                            color: theme.textSecondary
                            visible: text.length > 0
                        }
                    }
                }

                StyledButton {
                    text: "✕"
                    implicitWidth: 32
                    implicitHeight: 32
                    variant: "ghost"
                    onClicked: scopeModalRoot.isOpen = false
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: theme.borderSubtle
            }

            // ── Options Body ──────────────────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 14

                // Media Type Filters
                Text {
                    text: tr("tg_filter_types", "Media Types to Download:")
                    font.pixelSize: theme.fontSizeMd
                    font.bold: true
                    color: theme.textPrimary
                }

                GridLayout {
                    columns: 2
                    columnSpacing: 16
                    rowSpacing: 8
                    Layout.fillWidth: true

                    StyledCheckBox {
                        id: chkVideos
                        text: "🎬 Videos & Clips"
                        checked: true
                    }

                    StyledCheckBox {
                        id: chkPhotos
                        text: "🖼️ Photos & Images"
                        checked: true
                    }

                    StyledCheckBox {
                        id: chkDocuments
                        text: "📦 Documents & Archives"
                        checked: true
                    }

                    StyledCheckBox {
                        id: chkAudio
                        text: "🎵 Audio & Voice"
                        checked: false
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: theme.borderSubtle
                }

                // Post Count Limit
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: tr("tg_post_limit_label", "Number of Recent Posts to Scan:")
                        font.pixelSize: theme.fontSizeMd
                        font.bold: true
                        color: theme.textPrimary
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Repeater {
                            model: [50, 100, 200, 500]
                            StyledButton {
                                text: modelData.toString()
                                Layout.fillWidth: true
                                implicitHeight: 30
                                variant: postSpinBox.value === modelData ? "primary" : "outline"
                                onClicked: postSpinBox.value = modelData
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Text {
                            text: tr("tg_custom_limit", "Custom limit:")
                            font.pixelSize: theme.fontSizeSm
                            color: theme.textSecondary
                        }

                        StyledSpinBox {
                            id: postSpinBox
                            from: 10
                            to: 5000
                            value: 100
                            stepSize: 25
                            Layout.preferredWidth: 140
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: theme.borderSubtle
                }

                // Max File Size Limit
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: tr("tg_size_cap_label", "Maximum File Size Filter:")
                        font.pixelSize: theme.fontSizeMd
                        font.bold: true
                        color: theme.textPrimary
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Text {
                            text: tr("tg_skip_above", "Skip files larger than:")
                            font.pixelSize: theme.fontSizeSm
                            color: theme.textSecondary
                        }

                        StyledSpinBox {
                            id: maxSizeSpinBox
                            from: 0
                            to: 4000
                            value: 0
                            stepSize: 50
                            Layout.preferredWidth: 140
                        }

                        Text {
                            text: maxSizeSpinBox.value === 0 ? tr("tg_no_limit", "(0 = No size limit)") : "MB"
                            font.pixelSize: theme.fontSizeSm
                            color: maxSizeSpinBox.value === 0 ? theme.success : theme.textSecondary
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }

            // ── Loading Status ────────────────────────────────────────────────
            RowLayout {
                visible: scopeModalRoot.isLoading
                Layout.fillWidth: true
                spacing: 10

                BusyIndicator {
                    Layout.preferredWidth: 24
                    Layout.preferredHeight: 24
                    running: true
                }

                Text {
                    text: tr("tg_scanning_channel", "Resolving and scanning channel media history...")
                    font.pixelSize: theme.fontSizeSm
                    color: theme.primary
                }
            }

            // ── Footer ────────────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                StyledButton {
                    text: tr("btn_cancel", "Cancel")
                    implicitWidth: 90
                    implicitHeight: 36
                    variant: "outline"
                    onClicked: scopeModalRoot.isOpen = false
                }

                Item { Layout.fillWidth: true }

                StyledButton {
                    text: "🖼️ " + tr("tg_btn_select_posts", "Select Posts…")
                    implicitWidth: 145
                    implicitHeight: 36
                    variant: scopeModalRoot.defaultAction === "select" ? "primary" : "outline"
                    enabled: !scopeModalRoot.isLoading && (chkVideos.checked || chkPhotos.checked || chkDocuments.checked || chkAudio.checked)
                    onClicked: {
                        console.log(">>> SCOPE MODAL: Select Posts clicked. telegramBridge =", telegramBridge, "targetChannelId =", scopeModalRoot.targetChannelId)
                        scopeModalRoot.isLoading = true

                        var mediaTypes = []
                        if (chkVideos.checked) mediaTypes.push("video")
                        if (chkPhotos.checked) mediaTypes.push("photo")
                        if (chkDocuments.checked) mediaTypes.push("document")
                        if (chkAudio.checked) mediaTypes.push("audio")

                        if (telegramBridge) {
                            telegramBridge.fetchMessages(
                                scopeModalRoot.targetChannelId,
                                postSpinBox.value,
                                mediaTypes,
                                maxSizeSpinBox.value,
                                true
                            )
                        }
                    }
                }

                StyledButton {
                    text: "⬇️ " + tr("tg_btn_start_queue", "Start Download")
                    implicitWidth: 155
                    implicitHeight: 36
                    variant: scopeModalRoot.defaultAction === "download" ? "primary" : "default"
                    enabled: !scopeModalRoot.isLoading && (chkVideos.checked || chkPhotos.checked || chkDocuments.checked || chkAudio.checked)
                    onClicked: {
                        console.log(">>> SCOPE MODAL: Start Download clicked. telegramBridge =", telegramBridge, "targetChannelId =", scopeModalRoot.targetChannelId)
                        scopeModalRoot.isLoading = true

                        var mediaTypes = []
                        if (chkVideos.checked) mediaTypes.push("video")
                        if (chkPhotos.checked) mediaTypes.push("photo")
                        if (chkDocuments.checked) mediaTypes.push("document")
                        if (chkAudio.checked) mediaTypes.push("audio")

                        if (telegramBridge) {
                            telegramBridge.fetchMessages(
                                scopeModalRoot.targetChannelId,
                                postSpinBox.value,
                                mediaTypes,
                                maxSizeSpinBox.value,
                                false
                            )
                        }
                    }
                }
            }
        }
    }

    Connections {
        target: telegramBridge ? telegramBridge : null
        function onChannelMessagesReady(messages) {
            scopeModalRoot.isLoading = false
            scopeModalRoot.isOpen = false
            if (appBridge && messages.length > 0) {
                appBridge.queueTelegramFiles(scopeModalRoot.channelTitle, messages)
            }
        }
        function onChannelMessagesForSelectionReady(messages) {
            scopeModalRoot.isLoading = false
            scopeModalRoot.isOpen = false
            if (appBridge && messages.length > 0) {
                appBridge.openTelegramPostSelection(scopeModalRoot.channelTitle, messages, scopeModalRoot.targetRawUrl)
            }
        }
        function onChannelResolutionFailed(err) {
            scopeModalRoot.isLoading = false
        }
    }
}
