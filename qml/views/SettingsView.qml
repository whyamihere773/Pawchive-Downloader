import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

SmoothFlickable {
    id: root

    property var bridge: null

    // Cookie importer state
    property bool importingCookies: false
    property string cookieStatusText: ""
    property string cookieStatusColor: "#94A3B8"

    // AI Model download states
    property string aiT1Status: (root.bridge && root.bridge.aiFastSemanticReady) ? "ready" : "not_downloaded"
    property real aiT1Percent: (root.bridge && root.bridge.aiFastSemanticReady) ? 100 : 0
    property string aiT1Speed: ""
    property string aiT1Error: ""

    property string aiT2LightStatus: (root.bridge && root.bridge.aiDeepReasonerLightReady) ? "ready" : "not_downloaded"
    property real aiT2LightPercent: (root.bridge && root.bridge.aiDeepReasonerLightReady) ? 100 : 0
    property string aiT2LightSpeed: ""
    property string aiT2LightError: ""

    property string aiT2HeavyStatus: (root.bridge && root.bridge.aiDeepReasonerHeavyReady) ? "ready" : "not_downloaded"
    property real aiT2HeavyPercent: (root.bridge && root.bridge.aiDeepReasonerHeavyReady) ? 100 : 0
    property string aiT2HeavySpeed: ""
    property string aiT2HeavyError: ""

    function syncAiModelStatuses() {
        if (!root.bridge) return
        var s1 = root.bridge.getAiModelStatus("fast_semantic")
        if (s1) {
            aiT1Status = s1.status || (root.bridge.aiFastSemanticReady ? "ready" : "not_downloaded")
            aiT1Percent = (s1.percent !== undefined) ? s1.percent : (aiT1Status === "ready" ? 100 : 0)
            aiT1Speed = s1.speed_mbps ? (s1.speed_mbps.toFixed(1) + " MB/s") : ""
            aiT1Error = s1.error || ""
        }
        var s2l = root.bridge.getAiModelStatus("deep_reasoner_light")
        if (s2l) {
            aiT2LightStatus = s2l.status || (root.bridge.aiDeepReasonerLightReady ? "ready" : "not_downloaded")
            aiT2LightPercent = (s2l.percent !== undefined) ? s2l.percent : (aiT2LightStatus === "ready" ? 100 : 0)
            aiT2LightSpeed = s2l.speed_mbps ? (s2l.speed_mbps.toFixed(1) + " MB/s") : ""
            aiT2LightError = s2l.error || ""
        }
        var s2h = root.bridge.getAiModelStatus("deep_reasoner_heavy")
        if (s2h) {
            aiT2HeavyStatus = s2h.status || (root.bridge.aiDeepReasonerHeavyReady ? "ready" : "not_downloaded")
            aiT2HeavyPercent = (s2h.percent !== undefined) ? s2h.percent : (aiT2HeavyStatus === "ready" ? 100 : 0)
            aiT2HeavySpeed = s2h.speed_mbps ? (s2h.speed_mbps.toFixed(1) + " MB/s") : ""
            aiT2HeavyError = s2h.error || ""
        }
    }

    Connections {
        target: root.bridge
        function onAiModelProgressChanged(modelKey, status, percent, speedStr, error) {
            if (modelKey === "fast_semantic") {
                root.aiT1Status = status
                root.aiT1Percent = percent
                root.aiT1Speed = speedStr
                root.aiT1Error = error
            } else if (modelKey === "deep_reasoner_light") {
                root.aiT2LightStatus = status
                root.aiT2LightPercent = percent
                root.aiT2LightSpeed = speedStr
                root.aiT2LightError = error
            } else if (modelKey === "deep_reasoner_heavy") {
                root.aiT2HeavyStatus = status
                root.aiT2HeavyPercent = percent
                root.aiT2HeavySpeed = speedStr
                root.aiT2HeavyError = error
            }
        }
    }

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    contentWidth: width
    contentHeight: settingsCol.implicitHeight + 36

    // Cascading Newtonian entrance animation stage
    property int entranceStage: 0

    function triggerEntrance() {
        entranceStage = 0
        staggerTimer.restart()
    }

    Timer {
        id: staggerTimer
        interval: 35
        repeat: true
        running: false
        onTriggered: {
            entranceStage++
            if (entranceStage >= 7) stop()
        }
    }

    Component.onCompleted: {
        triggerEntrance()
        syncAiModelStatuses()
    }
    onVisibleChanged: {
        if (visible) {
            triggerEntrance()
            syncAiModelStatuses()
        }
    }

    ColumnLayout {
        id: settingsCol
        width: root.width - (root.verticalScrollBar && root.verticalScrollBar.visible ? 10 : 0)
        spacing: 12

        // Section 0: Language & Internationalization
        CardSection {
            Layout.fillWidth: true
            interactive: !root.isScrolling
            title: tr("section_language", "Language & Display")
            iconText: "🌐"
            entranceOffsetY: root.entranceStage >= 1 ? 0 : 24
            entranceOpacity: root.entranceStage >= 1 ? 1.0 : 0.0

            ColumnLayout {
                width: parent.width
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Text {
                        text: tr("label_language", "Interface Language:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#94A3B8"
                    }

                    ComboBox {
                        id: langCombo
                        Layout.fillWidth: true
                        Layout.maximumWidth: 240
                        Layout.minimumWidth: 130
                        Layout.preferredHeight: 32
                        model: Lang ? Lang.availableLanguages : []
                        textRole: "native"
                        valueRole: "code"

                        currentIndex: {
                            if (!Lang) return 0
                            var list = Lang.availableLanguages
                            for (var i = 0; i < list.length; i++) {
                                if (list[i].code === Lang.currentLanguage) return i
                            }
                            return 0
                        }

                        onActivated: function(index) {
                            if (Lang && model[index]) {
                                var selectedCode = model[index].code
                                Lang.setLanguage(selectedCode)
                                if (root.bridge) root.bridge.language = selectedCode
                            }
                        }

                        background: Rectangle {
                            color: "#141923"
                            border.color: langCombo.activeFocus ? "#38BDF8" : "#283042"
                            border.width: 1
                            radius: 6
                        }

                        contentItem: Text {
                            leftPadding: 10
                            rightPadding: (langCombo.indicator ? langCombo.indicator.width : 0) + 10
                            text: langCombo.displayText
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#F1F5F9"
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        popup: Popup {
                            y: langCombo.height + 2
                            width: langCombo.width
                            implicitHeight: contentItem.implicitHeight + 10
                            padding: 4
                            background: Rectangle {
                                color: "#141923"
                                border.color: "#283042"
                                border.width: 1
                                radius: 6
                            }
                            contentItem: ListView {
                                clip: true
                                implicitHeight: Math.min(contentHeight, 300)
                                model: langCombo.popup.visible ? langCombo.delegateModel : null
                                currentIndex: langCombo.highlightedIndex
                                ScrollBar.vertical: ScrollBar { active: true; policy: ScrollBar.AsNeeded }
                            }
                        }

                        delegate: ItemDelegate {
                            width: langCombo.width - 8
                            height: 30
                            highlighted: langCombo.highlightedIndex === index
                            contentItem: Text {
                                text: modelData.native
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: highlighted ? "#38BDF8" : "#CBD5E1"
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                color: highlighted ? "#1E293B" : "transparent"
                                radius: 4
                            }
                        }
                    }
                }

                // AI Translation Disclaimer Banner
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: disclaimerRow.implicitHeight + 16
                    radius: 6
                    color: "#141A26"
                    border.color: "#233147"
                    border.width: 1

                    RowLayout {
                        id: disclaimerRow
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        anchors.topMargin: 8
                        anchors.bottomMargin: 8
                        spacing: 8

                        Text {
                            text: "🤖"
                            font.pixelSize: 13
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Text {
                            text: tr("disclaimer_translation", "Translations are generated by AI and Google Translate. Some phrasing may not be completely accurate.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }

        // Network & Authentication
        CardSection {
            Layout.fillWidth: true
            interactive: !root.isScrolling
            title: tr("section_network", "Network & Authentication (Cloudflare / Cookies)")
            iconText: "🌐"
            entranceOffsetY: root.entranceStage >= 2 ? 0 : 24
            entranceOpacity: root.entranceStage >= 2 ? 1.0 : 0.0

            ColumnLayout {
                width: parent.width
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 10

                Text {
                    text: tr("label_cookie", "Session Cookie (Useful for Patreon / Fanbox / Cloudflare bypass):")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    wrapMode: Text.WordWrap
                }

                StyledTextField {
                    Layout.fillWidth: true
                    placeholderText: tr("placeholder_cookie", "e.g., session=eyJhbGci... or cf_clearance=...")
                    text: root.bridge ? root.bridge.cookieString : ""
                    onTextChanged: if (root.bridge && root.bridge.cookieString !== text) root.bridge.cookieString = text
                }

                // 1-Click Browser Cookie Importer & Expiration Watchdog
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: cookieHelperCol.implicitHeight + 20
                    radius: 8
                    color: "#141A26"
                    border.color: cookieBoxHover.hovered ? "#38BDF8" : "#233147"
                    border.width: 1

                    HoverHandler { id: cookieBoxHover }

                    transform: Translate {
                        y: cookieBoxHover.hovered ? -1.5 : 0
                        Behavior on y {
                            SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.9; epsilon: 0.25 }
                        }
                    }

                    Behavior on border.color { ColorAnimation { duration: 160 } }

                    ColumnLayout {
                        id: cookieHelperCol
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text { text: "🍪"; font.pixelSize: 13 }
                            Text {
                                text: tr("cookie_importer_title", "1-Click Browser Session Importer")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#F1F5F9"
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }

                            // Real-time Expiration Watchdog Badge
                            Rectangle {
                                height: 20
                                Layout.preferredWidth: Math.min(watchdogLabel.implicitWidth + 16, 180)
                                Layout.minimumWidth: 0
                                Layout.maximumWidth: 180
                                radius: 10
                                color: "#0F172A"
                                border.color: root.bridge ? root.bridge.cookieWatchdogColor : "#64748B"
                                border.width: 1
                                clip: true

                                Row {
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Rectangle {
                                        width: 6; height: 6; radius: 3
                                        color: root.bridge ? root.bridge.cookieWatchdogColor : "#94A3B8"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Text {
                                        id: watchdogLabel
                                        text: root.bridge ? root.bridge.cookieWatchdogText : tr("cookie_status_none", "No session cookie")
                                        font.pixelSize: 10
                                        font.weight: 600
                                        color: root.bridge ? root.bridge.cookieWatchdogColor : "#94A3B8"
                                        anchors.verticalCenter: parent.verticalCenter
                                        elide: Text.ElideRight
                                        maximumLineCount: 1
                                    }
                                }
                            }
                        }

                        Text {
                            text: tr("cookie_importer_desc", "Extracts authenticated Kemono/Patreon session cookies directly from your installed browser without locking open sessions or requiring manual DevTools copying.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        // Browser selector row
                        Flow {
                            width: parent.width
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 8

                            ComboBox {
                                id: browserSelector
                                width: Math.min(parent.width, 190)
                                height: 30
                                model: [
                                    { id: "",         name: tr("browser_auto",    "Auto-Detect") },
                                    { id: "firefox",  name: tr("browser_firefox", "Mozilla Firefox (Recommended)") },
                                    { id: "edge",     name: tr("browser_edge",    "Microsoft Edge") },
                                    { id: "brave",    name: tr("browser_brave",   "Brave Browser") },
                                    { id: "operagx",  name: tr("browser_operagx", "Opera GX") },
                                    { id: "opera",    name: tr("browser_opera",   "Opera") },
                                    { id: "chrome",   name: tr("browser_chrome",  "Google Chrome") }
                                ]
                                textRole: "name"
                                valueRole: "id"
                                currentIndex: 0

                                background: Rectangle {
                                    color: "#141923"
                                    border.color: browserSelector.activeFocus ? "#38BDF8" : "#283042"
                                    border.width: 1
                                    radius: 6
                                }

                                contentItem: Text {
                                    leftPadding: 10
                                    rightPadding: browserSelector.indicator.width + 10
                                    text: browserSelector.displayText
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    color: "#F1F5F9"
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                }

                                indicator: Canvas {
                                    id: browserSelectorArrow
                                    x: browserSelector.width - width - 8
                                    y: (browserSelector.height - height) / 2
                                    width: 10; height: 6
                                    contextType: "2d"
                                    onPaint: {
                                        var ctx = getContext("2d")
                                        ctx.clearRect(0, 0, width, height)
                                        ctx.fillStyle = "#94A3B8"
                                        ctx.beginPath()
                                        ctx.moveTo(0, 0)
                                        ctx.lineTo(width, 0)
                                        ctx.lineTo(width / 2, height)
                                        ctx.closePath()
                                        ctx.fill()
                                    }
                                }

                                popup: Popup {
                                    y: browserSelector.height + 2
                                    width: browserSelector.width
                                    implicitHeight: contentItem.implicitHeight + 10
                                    padding: 4
                                    background: Rectangle {
                                        color: "#141923"
                                        border.color: "#283042"
                                        border.width: 1
                                        radius: 6
                                    }
                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: Math.min(contentHeight, 260)
                                        model: browserSelector.popup.visible ? browserSelector.delegateModel : null
                                        currentIndex: browserSelector.highlightedIndex
                                        ScrollBar.vertical: ScrollBar { active: true; policy: ScrollBar.AsNeeded }
                                    }
                                }

                                delegate: ItemDelegate {
                                    width: browserSelector.width - 8
                                    height: 30
                                    highlighted: browserSelector.highlightedIndex === index
                                    contentItem: Text {
                                        text: modelData.name
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: highlighted ? "#38BDF8" : "#CBD5E1"
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    background: Rectangle {
                                        color: highlighted ? "#1E293B" : "transparent"
                                        radius: 4
                                    }
                                }
                            }

                            StyledButton {
                                id: importCookieBtn
                                text: tr("btn_import_cookies", "Import from Browser")
                                iconText: importingCookies ? "⏳" : "⚡"
                                variant: "primary"
                                enabled: !importingCookies
                                opacity: importingCookies ? 0.7 : 1.0
                                onClicked: {
                                    var bid = browserSelector.model[browserSelector.currentIndex].id
                                    importingCookies = true
                                    cookieStatusText = tr("cookie_importing", "Importing…")
                                    cookieStatusColor = "#94A3B8"
                                    if (root.bridge) root.bridge.importBrowserCookies(bid)
                                }
                            }
                        }

                        // Import status feedback
                        Text {
                            id: cookieImportStatus
                            Layout.fillWidth: true
                            text: cookieStatusText
                            color: cookieStatusColor
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                            visible: cookieStatusText !== ""
                            Behavior on opacity { NumberAnimation { duration: 150 } }
                        }

                        // Connections for import result
                        Connections {
                            target: root.bridge
                            function onCookieImportCompleted(success, message) {
                                importingCookies = false
                                if (success) {
                                    cookieStatusText = "✔ Imported from " + message
                                    cookieStatusColor = "#10B981"
                                } else {
                                    cookieStatusText = "✘ " + message
                                    cookieStatusColor = "#F87171"
                                }
                            }
                        }
                    }
                }

                Text {
                    text: tr("label_user_agent", "Custom User-Agent:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                StyledTextField {
                    Layout.fillWidth: true
                    placeholderText: tr("placeholder_user_agent", "Leave blank for default Chromium browser header")
                    text: root.bridge ? root.bridge.userAgent : ""
                    onTextChanged: if (root.bridge && root.bridge.userAgent !== text) root.bridge.userAgent = text
                }

                Text {
                    text: tr("label_proxy", "HTTP / HTTPS / SOCKS5 Proxy:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                StyledTextField {
                    Layout.fillWidth: true
                    placeholderText: tr("placeholder_proxy", "e.g., http://127.0.0.1:8080 or socks5://127.0.0.1:1080")
                    text: root.bridge ? root.bridge.proxyUrl : ""
                    onTextChanged: if (root.bridge && root.bridge.proxyUrl !== text) root.bridge.proxyUrl = text
                }
            }
        }

        // Storage & Naming Options
        CardSection {
            Layout.fillWidth: true
            interactive: !root.isScrolling
            title: tr("section_storage", "Storage & File Processing")
            iconText: "💾"
            entranceOffsetY: root.entranceStage >= 3 ? 0 : 24
            entranceOpacity: root.entranceStage >= 3 ? 1.0 : 0.0

            ColumnLayout {
                width: parent.width
                spacing: 10

                StyledCheckBox {
                    text: tr("opt_auto_sync_known", "Auto-sync Known.txt on startup")
                    checked: true
                }

                StyledCheckBox {
                    text: tr("opt_show_console_links", "Show external links & media URLs in live console")
                    checked: true
                }

                StyledCheckBox {
                    text: tr("opt_extract_inline", "Extract and download inline post images from HTML content")
                    checked: root.bridge ? root.bridge.scanContentImages : true
                    onCheckedChanged: if (root.bridge) root.bridge.scanContentImages = checked
                }

                StyledCheckBox {
                    text: tr("opt_download_embeds", "Download embedded media players (Vimeo, YouTube, Streamable) via yt-dlp")
                    checked: root.bridge ? root.bridge.downloadEmbeds : true
                    onCheckedChanged: if (root.bridge) root.bridge.downloadEmbeds = checked
                }

                StyledCheckBox {
                    text: tr("opt_compress_webp", "Convert downloaded PNG/JPG to WebP format")
                    checked: root.bridge ? root.bridge.compressWebp : false
                    onCheckedChanged: if (root.bridge) root.bridge.compressWebp = checked
                }

                StyledCheckBox {
                    text: tr("opt_tag_audio_files_settings", "Write creator and post tags to downloaded audio files (MP3/FLAC/M4A)")
                    tooltip: tr("opt_tag_audio_files_tip", "Automatically sets Artist to creator name and Title to post title for seamless import into music managers")
                    checked: root.bridge ? root.bridge.writeAudioMetadata : false
                    onCheckedChanged: if (root.bridge) root.bridge.writeAudioMetadata = checked
                }

                StyledCheckBox {
                    text: tr("opt_download_pawchive_temp", "Download Pawchive temporary oversized files (t1.pawchive.pw)")
                    tooltip: tr("opt_download_pawchive_temp_tip", "Download oversized files that Pawchive keeps in temporary 30-day storage")
                    checked: root.bridge ? root.bridge.downloadPawchiveTemporaryFiles : true
                    onCheckedChanged: if (root.bridge) root.bridge.downloadPawchiveTemporaryFiles = checked
                }

                StyledCheckBox {
                    text: tr("opt_desktop_report", "Generate completion report on Desktop (HTML & TXT)")
                    tooltip: tr("opt_desktop_report_tip", "Automatically save a visual summary report and failure log to your Desktop upon completion")
                    checked: root.bridge ? root.bridge.generateDesktopReport : false
                    onCheckedChanged: if (root.bridge) root.bridge.generateDesktopReport = checked
                }

                // Download Archive Database Sub-Card (gallery-dl style)
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: archiveCol.implicitHeight + 22
                    radius: 8
                    color: "#141A26"
                    border.color: archiveBoxHover.hovered ? "#38BDF8" : "#233147"
                    border.width: 1

                    HoverHandler { id: archiveBoxHover }

                    transform: Translate {
                        y: archiveBoxHover.hovered ? -1.5 : 0
                        Behavior on y {
                            SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.9; epsilon: 0.25 }
                        }
                    }

                    Behavior on border.color { ColorAnimation { duration: 160 } }

                    ColumnLayout {
                        id: archiveCol
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                text: "🗃️"
                                font.pixelSize: 14
                                Layout.alignment: Qt.AlignVCenter
                            }

                            Text {
                                text: tr("opt_download_archive", "Download Archive Database")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: 600
                                color: "#F1F5F9"
                                Layout.fillWidth: true
                            }

                            Rectangle {
                                implicitHeight: 18
                                implicitWidth: galleryDlBadgeText.implicitWidth + 10
                                radius: 9
                                color: "#0F2942"
                                border.color: "#0284C7"
                                border.width: 1

                                Text {
                                    id: galleryDlBadgeText
                                    anchors.centerIn: parent
                                    text: "gallery-dl style"
                                    font.pixelSize: 9
                                    font.weight: 600
                                    color: "#38BDF8"
                                }
                            }

                            StyledSwitch {
                                checked: root.bridge ? root.bridge.enableDownloadArchive : false
                                accentColor: "#38BDF8"
                                onToggled: function(isChecked) {
                                    if (root.bridge) root.bridge.enableDownloadArchive = isChecked
                                }
                            }
                        }

                        Text {
                            text: tr("desc_download_archive", "Records downloaded files in an isolated local database. Subsequent downloads will skip files even if they have been unzipped, moved to another drive, or deleted locally.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        // Dynamic drawer revealed when enabled
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            visible: root.bridge ? root.bridge.enableDownloadArchive : false

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: warningRow.implicitHeight + 12
                                radius: 6
                                color: "#2A1F0D"
                                border.color: "#B45309"
                                border.width: 1

                                RowLayout {
                                    id: warningRow
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    spacing: 6

                                    Text {
                                        text: "⚠️"
                                        font.pixelSize: 11
                                    }

                                    Text {
                                        text: tr("tip_download_archive_warning", "Note: Files deleted from disk will not re-download while this is active unless you click Clear Archive.")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: "#FDE68A"
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                    }
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10

                                Rectangle {
                                    implicitHeight: 28
                                    implicitWidth: recordCountText.implicitWidth + 16
                                    radius: 14
                                    color: "#1E293B"
                                    border.color: "#334155"
                                    border.width: 1

                                    Text {
                                        id: recordCountText
                                        anchors.centerIn: parent
                                        text: tr("badge_archive_records", "Archived files: ") + (root.bridge ? root.bridge.archiveRecordCount : 0)
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: 600
                                        color: "#CBD5E1"
                                    }
                                }

                                Item { Layout.fillWidth: true }

                                StyledButton {
                                    text: tr("btn_open_archive_tab", "Open Archive Tab ➔")
                                    iconText: "🗃️"
                                    variant: "outline"
                                    implicitHeight: 28
                                    onClicked: {
                                        if (typeof appWindow !== "undefined" && appWindow) {
                                            appWindow.currentTab = 7
                                        }
                                    }
                                }

                                StyledButton {
                                    text: tr("btn_clear_archive", "Clear Archive")
                                    iconText: "🗑️"
                                    variant: "danger"
                                    implicitHeight: 28
                                    onClicked: {
                                        if (root.bridge) {
                                            root.bridge.clearDownloadArchive()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Filename Formatting & Custom Templates Sub-Card
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: filenameCol.implicitHeight + 22
                    radius: 8
                    color: "#141A26"
                    border.color: filenameBoxHover.hovered ? "#38BDF8" : "#233147"
                    border.width: 1

                    HoverHandler { id: filenameBoxHover }

                    transform: Translate {
                        y: filenameBoxHover.hovered ? -1.5 : 0
                        Behavior on y {
                            SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.9; epsilon: 0.25 }
                        }
                    }

                    Behavior on border.color { ColorAnimation { duration: 160 } }

                    ColumnLayout {
                        id: filenameCol
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                text: "🏷️"
                                font.pixelSize: 14
                                Layout.alignment: Qt.AlignVCenter
                            }

                            Text {
                                text: root.tr("label_filename_style", "Filename Formatting Pattern")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: 600
                                color: "#F1F5F9"
                                Layout.fillWidth: true
                            }

                            ComboBox {
                                id: filenameStyleCombo
                                Layout.preferredWidth: 320
                                Layout.preferredHeight: 36

                                ToolTip.visible: filenameStyleCombo.hovered && !filenameStyleCombo.popup.visible
                                ToolTip.text: root.tr("tip_filename_pattern", "Choose how downloaded files are named and organized on your disk")
                                ToolTip.delay: 450

                                model: [
                                    {
                                        text: root.tr("style_post_title", "Post Title - Original (Default)"),
                                        value: "post_title",
                                        icon: "📄",
                                        example: "Post Title - original_filename.jpg",
                                        tag: root.tr("badge_default", "Default")
                                    },
                                    {
                                        text: root.tr("style_original", "Original Filename Only"),
                                        value: "original",
                                        icon: "🏷️",
                                        example: "original_filename.jpg (source name)",
                                        tag: ""
                                    },
                                    {
                                        text: root.tr("style_date_post_title", "Date - Post Title - Original"),
                                        value: "date_post_title",
                                        icon: "📅",
                                        example: "[2026-09-17] Post Title - image.png",
                                        tag: ""
                                    },
                                    {
                                        text: root.tr("style_date_based", "Date Numbering"),
                                        value: "date_based",
                                        icon: "🔢",
                                        example: "2026-09-17_001_01.png (chronological)",
                                        tag: ""
                                    },
                                    {
                                        text: root.tr("style_global_numbering", "Global Index + Post Title"),
                                        value: "post_title_global_numbering",
                                        icon: "🌐",
                                        example: "001 - Post Title - image.png",
                                        tag: ""
                                    },
                                    {
                                        text: root.tr("style_custom_template", "Custom Template…"),
                                        value: "custom",
                                        icon: "✨",
                                        example: "Define tags: {artist}, {date}, {title}…",
                                        tag: root.tr("badge_advanced", "Advanced")
                                    }
                                ]
                                textRole: "text"
                                valueRole: "value"

                                currentIndex: {
                                    if (!root.bridge) return 0
                                    var cur = root.bridge.filenameStyle || "post_title"
                                    for (var i = 0; i < model.length; i++) {
                                        if (model[i].value === cur) return i
                                    }
                                    return 0
                                }

                                onActivated: function(index) {
                                    var item = model[index]
                                    if (root.bridge && item) {
                                        root.bridge.filenameStyle = item.value
                                    }
                                }

                                background: Rectangle {
                                    radius: 7
                                    color: filenameStyleCombo.pressed ? "#0A0E17" : (filenameStyleCombo.hovered ? "#131B2A" : "#0E1420")
                                    border.color: (filenameStyleCombo.activeFocus || filenameStyleCombo.popup.visible)
                                                  ? "#38BDF8"
                                                  : (filenameStyleCombo.hovered ? "#3B5275" : "#233147")
                                    border.width: (filenameStyleCombo.activeFocus || filenameStyleCombo.popup.visible) ? 1.5 : 1

                                    Behavior on color { ColorAnimation { duration: 120 } }
                                    Behavior on border.color { ColorAnimation { duration: 120 } }
                                }

                                contentItem: RowLayout {
                                    spacing: 8
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 34

                                    Text {
                                        text: (filenameStyleCombo.model[filenameStyleCombo.currentIndex] && filenameStyleCombo.model[filenameStyleCombo.currentIndex].icon)
                                              ? filenameStyleCombo.model[filenameStyleCombo.currentIndex].icon
                                              : "🏷️"
                                        font.pixelSize: 14
                                        Layout.alignment: Qt.AlignVCenter
                                    }

                                    Text {
                                        text: filenameStyleCombo.displayText
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: Font.Medium
                                        color: "#F1F5F9"
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                        Layout.alignment: Qt.AlignVCenter
                                    }
                                }

                                indicator: Item {
                                    x: filenameStyleCombo.width - width - 10
                                    y: (filenameStyleCombo.height - height) / 2
                                    width: 18
                                    height: 18

                                    Text {
                                        anchors.centerIn: parent
                                        text: "▾"
                                        font.pixelSize: 14
                                        color: filenameStyleCombo.popup.visible ? "#38BDF8" : (filenameStyleCombo.hovered ? "#94A3B8" : "#64748B")
                                        rotation: filenameStyleCombo.popup.visible ? 180 : 0
                                        transformOrigin: Item.Center

                                        Behavior on rotation {
                                            NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                                        }
                                        Behavior on color {
                                            ColorAnimation { duration: 120 }
                                        }
                                    }
                                }

                                popup: Popup {
                                    y: filenameStyleCombo.height + 4
                                    width: 370
                                    implicitHeight: Math.min(contentItem.implicitHeight + 12, 330)
                                    padding: 5
                                    transformOrigin: Popup.Top

                                    enter: Transition {
                                        NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 140; easing.type: Easing.OutCubic }
                                        NumberAnimation { property: "scale"; from: 0.96; to: 1.0; duration: 140; easing.type: Easing.OutCubic }
                                    }
                                    exit: Transition {
                                        NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 100; easing.type: Easing.InCubic }
                                    }

                                    background: Rectangle {
                                        color: "#0E1420"
                                        border.color: "#25354C"
                                        border.width: 1.5
                                        radius: 8
                                    }

                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: contentHeight
                                        model: filenameStyleCombo.popup.visible ? filenameStyleCombo.delegateModel : null
                                        currentIndex: filenameStyleCombo.highlightedIndex
                                        boundsBehavior: Flickable.StopAtBounds
                                        spacing: 2
                                        ScrollBar.vertical: ScrollBar {
                                            active: true
                                            policy: ScrollBar.AsNeeded
                                        }
                                    }
                                }

                                delegate: ItemDelegate {
                                    id: itemDel
                                    width: filenameStyleCombo.popup.width - 10
                                    height: 48
                                    highlighted: filenameStyleCombo.highlightedIndex === index
                                    hoverEnabled: true

                                    readonly property bool isCurrent: filenameStyleCombo.currentIndex === index

                                    background: Rectangle {
                                        radius: 6
                                        color: itemDel.isCurrent
                                               ? "#14253D"
                                               : (itemDel.hovered ? "#162030" : "transparent")
                                        border.color: itemDel.isCurrent ? "#224A75" : (itemDel.hovered ? "#223147" : "transparent")
                                        border.width: 1

                                        // Left active indicator pill
                                        Rectangle {
                                            width: 3
                                            height: 24
                                            radius: 1.5
                                            color: "#38BDF8"
                                            anchors.left: parent.left
                                            anchors.leftMargin: 2
                                            anchors.verticalCenter: parent.verticalCenter
                                            visible: itemDel.isCurrent
                                        }

                                        Behavior on color { ColorAnimation { duration: 100 } }
                                    }

                                    contentItem: RowLayout {
                                        spacing: 9
                                        anchors.fill: parent
                                        anchors.leftMargin: itemDel.isCurrent ? 12 : 8
                                        anchors.rightMargin: 10

                                        // Icon container
                                        Rectangle {
                                            width: 28
                                            height: 28
                                            radius: 6
                                            color: itemDel.isCurrent ? "#1E3352" : (itemDel.hovered ? "#1C273A" : "#121824")
                                            border.color: itemDel.isCurrent ? "#38BDF8" : "#222D3E"
                                            border.width: 1
                                            Layout.alignment: Qt.AlignVCenter

                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData.icon || "🏷️"
                                                font.pixelSize: 13
                                            }
                                        }

                                        // Title + example subtitle
                                        ColumnLayout {
                                            spacing: 1
                                            Layout.fillWidth: true
                                            Layout.alignment: Qt.AlignVCenter

                                            RowLayout {
                                                spacing: 6
                                                Layout.fillWidth: true

                                                Text {
                                                    text: modelData.text
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 11
                                                    font.weight: itemDel.isCurrent ? Font.DemiBold : Font.Normal
                                                    color: itemDel.isCurrent ? "#38BDF8" : (itemDel.hovered ? "#FFFFFF" : "#E2E8F0")
                                                    elide: Text.ElideRight
                                                    Layout.fillWidth: true
                                                }

                                                // Tag pill (e.g. Default / Advanced)
                                                Rectangle {
                                                    visible: modelData.tag && modelData.tag.length > 0
                                                    height: 16
                                                    implicitWidth: tagText.implicitWidth + 8
                                                    radius: 4
                                                    color: modelData.tag === "Default" ? "#0369A1" : "#334155"
                                                    Layout.alignment: Qt.AlignVCenter

                                                    Text {
                                                        id: tagText
                                                        anchors.centerIn: parent
                                                        text: modelData.tag || ""
                                                        font.family: "Segoe UI, sans-serif"
                                                        font.pixelSize: 9
                                                        font.weight: Font.DemiBold
                                                        color: "#FFFFFF"
                                                    }
                                                }
                                            }

                                            Text {
                                                text: modelData.example || ""
                                                font.family: "Consolas, Segoe UI, sans-serif"
                                                font.pixelSize: 10
                                                color: itemDel.isCurrent ? "#7DD3FC" : "#64748B"
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }
                                        }

                                        // Checkmark for current selection
                                        Text {
                                            text: "✓"
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 13
                                            font.weight: Font.Bold
                                            color: "#38BDF8"
                                            visible: itemDel.isCurrent
                                            Layout.alignment: Qt.AlignVCenter
                                        }
                                    }
                                }
                            }
                        }

                        // Newtonian Expanding Custom Template Editor
                        Item {
                            id: customTemplateExpand
                            Layout.fillWidth: true
                            readonly property bool isCustom: root.bridge ? root.bridge.filenameStyle === "custom" : false
                            implicitHeight: isCustom ? (templateInnerCol.implicitHeight + 8) : 0
                            clip: true
                            visible: height > 0.5
                            height: implicitHeight

                            Behavior on height {
                                SpringAnimation {
                                    spring: 3.5
                                    damping: 0.35
                                    mass: 1.0
                                    epsilon: 0.5
                                }
                            }

                            ColumnLayout {
                                id: templateInnerCol
                                width: parent.width
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    StyledTextField {
                                        id: templateInput
                                        Layout.fillWidth: true
                                        placeholderText: "{artist} - [{date}] - {title} - {orig_name}"
                                        tooltip: root.tr("tip_template_input", "Enter custom pattern using tags below. Preview updates in real-time.")
                                        text: root.bridge ? root.bridge.filenameTemplate : ""
                                        onTextChanged: {
                                            if (root.bridge && root.bridge.filenameTemplate !== text) {
                                                root.bridge.filenameTemplate = text
                                            }
                                        }
                                    }

                                    StyledButton {
                                        text: root.tr("btn_reset_template", "Reset")
                                        tooltip: root.tr("tip_reset_template", "Reset filename template to: {title} - {orig_name}")
                                        variant: "ghost"
                                        implicitWidth: 70
                                        implicitHeight: 32
                                        onClicked: {
                                            if (root.bridge) {
                                                root.bridge.filenameTemplate = "{title} - {orig_name}"
                                                templateInput.text = "{title} - {orig_name}"
                                            }
                                        }
                                    }
                                }

                                // Clickable Tag Chips with Newtonian Press Bounce
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Repeater {
                                        model: [
                                            { tag: "{title}", label: "Title" },
                                            { tag: "{post_id}", label: "Post ID" },
                                            { tag: "{artist}", label: "Artist" },
                                            { tag: "{date}", label: "Date (YYYY-MM-DD)" },
                                            { tag: "{orig_name}", label: "Original Filename" },
                                            { tag: "{name}", label: "Filename Stem" },
                                            { tag: "{ext}", label: "Extension (.ext)" },
                                            { tag: "{file_index}", label: "File Index (01)" },
                                            { tag: "{post_index}", label: "Post Index (001)" }
                                        ]

                                        delegate: Rectangle {
                                            height: 24
                                            implicitWidth: chipRow.implicitWidth + 14
                                            radius: 4
                                            color: chipMouse.containsMouse ? "#1E293B" : "#0E141E"
                                            border.color: chipMouse.containsMouse ? "#38BDF8" : "#233147"
                                            border.width: 1

                                            ToolTip.visible: chipMouse.containsMouse
                                            ToolTip.text: modelData.label + " (" + modelData.tag + ")"
                                            ToolTip.delay: 350

                                            scale: chipMouse.pressed ? 0.94 : (chipMouse.containsMouse ? 1.05 : 1.0)
                                            Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35; mass: 1.0 } }

                                            Row {
                                                id: chipRow
                                                anchors.centerIn: parent
                                                spacing: 4
                                                Text { text: "+"; font.pixelSize: 10; color: "#38BDF8"; font.weight: Font.Bold }
                                                Text {
                                                    text: modelData.tag
                                                    font.family: "Segoe UI, monospace"
                                                    font.pixelSize: 11
                                                    color: "#E2E8F0"
                                                }
                                            }

                                            MouseArea {
                                                id: chipMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    var cur = templateInput.text || ""
                                                    if (cur.length > 0 && !cur.endsWith(" ") && !cur.endsWith("-") && !cur.endsWith("_")) {
                                                        cur += "_"
                                                    }
                                                    templateInput.text = cur + modelData.tag
                                                }
                                            }
                                        }
                                    }
                                }

                                // Live Preview Row
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Text {
                                        text: "👁️ " + root.tr("label_preview", "Live Preview:")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: 600
                                        color: "#64748B"
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: root.bridge ? root.bridge.previewCustomFilename(templateInput.text) : ""
                                        font.family: "Segoe UI, monospace"
                                        font.pixelSize: 11
                                        color: "#38BDF8"
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // Multi-Drive Overflow & Auto-Spanning (Storage Pools)
        CardSection {
            Layout.fillWidth: true
            interactive: !root.isScrolling
            title: tr("section_storage_pools", "Multi-Drive Overflow & Auto-Spanning (Storage Pools)")
            iconText: "💽"
            entranceOffsetY: root.entranceStage >= 4 ? 0 : 24
            entranceOpacity: root.entranceStage >= 4 ? 1.0 : 0.0

            ColumnLayout {
                id: storagePoolCol
                width: parent.width
                spacing: 12

                property var poolData: {
                    try {
                        return root.bridge ? JSON.parse(root.bridge.storagePoolStatusJson) : {}
                    } catch(e) {
                        return {}
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: tr("opt_enable_pools", "Enable Multi-Drive Storage Overflow")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#F1F5F9"
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }

                    StyledSwitch {
                        checked: storagePoolCol.poolData.enabled !== undefined ? storagePoolCol.poolData.enabled : false
                        accentColor: "#38BDF8"
                        onToggled: function(isChecked) {
                            if (root.bridge) root.bridge.setStoragePoolEnabled(isChecked)
                        }
                    }
                }

                Text {
                    text: tr("desc_storage_pools", "Prevents disk-full crashes ('No space left on device') by automatically spilling file downloads to secondary drives when your primary drive reaches its safety margin. Preserves creator and post directory hierarchy seamlessly.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                // Safety Margin Row
                Flow {
                    width: parent.width
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 8

                    RowLayout {
                        spacing: 8
                        Text {
                            text: tr("label_safety_margin", "Safety Free Space Margin:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#CBD5E1"
                        }

                        StyledSpinBox {
                            id: marginSpin
                            from: 2
                            to: 100
                            value: storagePoolCol.poolData.safety_margin_gb || 10
                            stepSize: 1
                            suffix: " GB"
                            accentColor: "#38BDF8"
                            implicitWidth: 110
                            onValueModified: function(v) {
                                if (root.bridge) root.bridge.setStoragePoolMargin(v)
                            }
                        }
                    }

                    Text {
                        text: "(" + tr("desc_margin_trigger", "triggers overflow when remaining space drops below this limit") + ")"
                        font.pixelSize: 10
                        color: "#64748B"
                        wrapMode: Text.WordWrap
                        width: parent.width
                    }
                }

                // Drive Capacity List
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: storagePoolCol.poolData.drives || []

                        delegate: Rectangle {
                            id: driveCard
                            required property var modelData
                            Layout.fillWidth: true
                            implicitHeight: 52
                            radius: 6
                            color: driveHover.hovered ? "#182233" : "#141A26"
                            border.color: modelData.is_low ? "#EF4444" : (driveHover.hovered ? "#38BDF8" : "#233147")
                            border.width: 1

                            HoverHandler { id: driveHover }

                            transform: Translate {
                                y: driveHover.hovered ? -2.0 : 0
                                Behavior on y {
                                    SpringAnimation { spring: 4.0; damping: 0.38; mass: 0.9; epsilon: 0.25 }
                                }
                            }

                            Behavior on color { ColorAnimation { duration: 160 } }
                            Behavior on border.color { ColorAnimation { duration: 160 } }

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 10

                                Text {
                                    text: modelData.is_primary ? "💾" : "💽"
                                    font.pixelSize: 14
                                    scale: driveHover.hovered ? 1.15 : 1.0
                                    Behavior on scale {
                                        SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.01 }
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 6
                                        Text {
                                            text: modelData.path
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: 600
                                            color: "#F1F5F9"
                                            elide: Text.ElideMiddle
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 40
                                        }

                                        Rectangle {
                                            visible: modelData.is_primary
                                            height: 16
                                            implicitWidth: primaryTag.implicitWidth + 8
                                            radius: 3
                                            color: "#0369A1"
                                            Text {
                                                id: primaryTag
                                                anchors.centerIn: parent
                                                text: "PRIMARY"
                                                font.pixelSize: 9
                                                font.weight: Font.Bold
                                                color: "#E0F2FE"
                                            }
                                        }

                                        Rectangle {
                                            visible: modelData.is_low
                                            height: 16
                                            implicitWidth: lowTag.implicitWidth + 8
                                            radius: 3
                                            color: "#7F1D1D"
                                            Text {
                                                id: lowTag
                                                anchors.centerIn: parent
                                                text: "LOW SPACE"
                                                font.pixelSize: 9
                                                font.weight: Font.Bold
                                                color: "#FEE2E2"
                                            }
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: driveCard.width > 340 ? (modelData.free_gb + " GB free / " + modelData.total_gb + " GB (" + modelData.used_percent + "% used)") : (modelData.free_gb + " GB free")
                                            font.pixelSize: 10
                                            color: modelData.is_low ? "#EF4444" : "#94A3B8"
                                            elide: Text.ElideRight
                                        }
                                    }

                                    // Simple capacity bar with smooth Newtonian filling
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 6
                                        radius: 3
                                        color: "#0F172A"

                                        Rectangle {
                                            width: parent.width * (Math.min(100, Math.max(0, modelData.used_percent)) / 100.0)
                                            height: parent.height
                                            radius: 3
                                            color: modelData.is_low ? "#EF4444" : (modelData.used_percent > 85 ? "#F59E0B" : "#10B981")

                                            Behavior on width {
                                                SpringAnimation {
                                                    spring: 2.8
                                                    damping: 0.4
                                                    mass: 1.0
                                                    epsilon: 0.5
                                                }
                                            }
                                        }
                                    }
                                }

                                // Remove button for secondary overflow drives with spring pop
                                Rectangle {
                                    visible: !modelData.is_primary
                                    width: 24; height: 24; radius: 4
                                    color: removePoolMouse.containsMouse ? "#3B181E" : "transparent"
                                    scale: removePoolMouse.pressed ? 0.85 : (removePoolMouse.containsMouse ? 1.25 : 1.0)
                                    transformOrigin: Item.Center
                                    Behavior on scale {
                                        SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.01 }
                                    }
                                    Behavior on color { ColorAnimation { duration: 100 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "✖"
                                        font.pixelSize: 11
                                        color: "#EF4444"
                                    }
                                    MouseArea {
                                        id: removePoolMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (root.bridge) root.bridge.removeStoragePoolDrive(modelData.path)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Add Overflow Drive Button
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    StyledButton {
                        text: tr("btn_add_storage_drive", "Add Overflow Drive / Folder...")
                        iconText: "➕"
                        variant: "outline"
                        onClicked: {
                            if (root.bridge) root.bridge.selectStoragePoolDirectory()
                        }
                    }

                    Item { Layout.fillWidth: true }
                }
            }
        }

        // Character & Franchise Recognition Engine (Master Database vs Auto-Learning)
        CardSection {
            Layout.fillWidth: true
            interactive: !root.isScrolling
            title: tr("section_known_engine", "Character & Franchise Recognition (Known Engine)")
            iconText: "🏷️"
            entranceOffsetY: root.entranceStage >= 5 ? 0 : 24
            entranceOpacity: root.entranceStage >= 5 ? 1.0 : 0.0

            ColumnLayout {
                width: parent.width
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 10

                Text {
                    text: tr("desc_known_engine", "Choose how the engine identifies characters and structures folders (Franchise ➔ Character):")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    wrapMode: Text.WordWrap
                }

                Flow {
                    width: parent.width
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 8

                    FilterCheckbox {
                        label: tr("mode_hybrid", "Master DB + Auto-Learn (Hybrid)")
                        iconText: "✨"
                        activeColor: "#38BDF8"
                        tooltip: tr("mode_hybrid_tip", "Combines the comprehensive 100k+ game & anime database with automatic learning of new tags into Known.txt (Recommended)")
                        checked: root.bridge ? (root.bridge.knownRecognitionMode === "hybrid" || root.bridge.knownRecognitionMode === "") : true
                        onClicked: if (root.bridge) root.bridge.knownRecognitionMode = "hybrid"
                    }

                    FilterCheckbox {
                        label: tr("mode_database_only", "Master Database Only")
                        iconText: "📚"
                        activeColor: "#818CF8"
                        tooltip: tr("mode_database_only_tip", "Only matches against the curated 100k+ video game/anime database (prevents modifying Known.txt)")
                        checked: root.bridge ? root.bridge.knownRecognitionMode === "database_only" : false
                        onClicked: if (root.bridge) root.bridge.knownRecognitionMode = "database_only"
                    }

                    FilterCheckbox {
                        label: tr("mode_learning_only", "Custom Known.txt Only")
                        iconText: "📝"
                        activeColor: "#34D399"
                        tooltip: tr("mode_learning_only_tip", "Only uses your custom Known.txt and learns new character tags as downloads run")
                        checked: root.bridge ? root.bridge.knownRecognitionMode === "learning_only" : false
                        onClicked: if (root.bridge) root.bridge.knownRecognitionMode = "learning_only"
                    }
                }

                Text {
                    text: tr("note_known_structure", "ℹ️ When 'Separate folders by Known' is enabled, downloads will automatically sort into: 'Franchise Name / Character Name / Post Folder'.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                // AI-Assisted Recognition & Archive Reasoning Sub-Card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    implicitHeight: aiCol.implicitHeight + 28
                    radius: 8
                    color: "#141A26"
                    border.color: aiBoxHover.hovered ? "#38BDF8" : "#233147"
                    border.width: 1
                    clip: true

                    HoverHandler { id: aiBoxHover }

                    transform: Translate {
                        y: aiBoxHover.hovered ? -1.5 : 0
                        Behavior on y {
                            SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.9; epsilon: 0.25 }
                        }
                    }

                    Behavior on border.color { ColorAnimation { duration: 160 } }

                    ColumnLayout {
                        id: aiCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 14
                        spacing: 12

                        // Header Row: Title, Hardware Badge, Switch
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 8

                            Text {
                                text: "🧠"
                                font.pixelSize: 15
                                Layout.alignment: Qt.AlignVCenter
                            }

                            Text {
                                text: tr("opt_ai_recognition_title", "AI Semantic Assistant & Archive Reasoning")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: 600
                                color: "#F1F5F9"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                elide: Text.ElideRight
                            }

                            // Hardware Acceleration Badge
                            Rectangle {
                                implicitHeight: 20
                                implicitWidth: hwBadgeText.implicitWidth + 12
                                radius: 10
                                color: (root.bridge && root.bridge.aiHardwareBadge.indexOf("GPU") !== -1) ? "#064E3B" : "#1E293B"
                                border.color: (root.bridge && root.bridge.aiHardwareBadge.indexOf("GPU") !== -1) ? "#10B981" : "#475569"
                                border.width: 1

                                Text {
                                    id: hwBadgeText
                                    anchors.centerIn: parent
                                    text: (root.bridge && root.bridge.aiHardwareBadge.indexOf("GPU") !== -1) ? ("⚡ " + root.bridge.aiHardwareBadge) : ("💻 " + (root.bridge ? root.bridge.aiHardwareBadge : "CPU"))
                                    font.pixelSize: 9
                                    font.weight: 600
                                    color: (root.bridge && root.bridge.aiHardwareBadge.indexOf("GPU") !== -1) ? "#34D399" : "#94A3B8"
                                }
                            }

                            StyledSwitch {
                                checked: root.bridge ? root.bridge.aiRecognitionEnabled : false
                                accentColor: "#38BDF8"
                                onToggled: function(isChecked) {
                                    if (root.bridge) root.bridge.aiRecognitionEnabled = isChecked
                                }
                            }
                        }

                        Text {
                            text: tr("desc_ai_recognition", "Uses vector semantic embeddings and creator archive patterns to identify obscure, unspaced, and misspelled character titles without manual rules. 100% offline, zero-handholding.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                        }

                        // Collapsible Drawer when enabled
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 12
                            visible: root.bridge ? root.bridge.aiRecognitionEnabled : false

                            // Engine Mode Selection: Semantic Matcher Only vs Full Hybrid
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 6

                                Text {
                                    text: tr("lbl_ai_engine_mode", "Recognition Engine Mode:")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: "#E2E8F0"
                                }

                                Flow {
                                    width: parent.width
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: 8

                                    FilterCheckbox {
                                        label: tr("ai_mode_minilm_only", "Semantic Only (MiniLM • Fast)")
                                        iconText: "⚡"
                                        activeColor: "#38BDF8"
                                        tooltip: tr("ai_mode_minilm_only_tip", "Runs fast vector embeddings only (~127 MB). Instant 1–3 ms inference on CPU with zero LLM RAM overhead. Best for potato PCs and pure speed.")
                                        checked: root.bridge ? (root.bridge.aiEngineMode === "semantic_only") : false
                                        onClicked: if (root.bridge) root.bridge.aiEngineMode = "semantic_only"
                                    }

                                    FilterCheckbox {
                                        label: tr("ai_mode_hybrid", "Full Hybrid (MiniLM + Reasoner)")
                                        iconText: "🧠"
                                        activeColor: "#818CF8"
                                        tooltip: tr("ai_mode_hybrid_tip", "Combines MiniLM vector search with offline SLM reasoning. Analyzes creator archive history to deduce obscure, unspaced, and cryptic titles.")
                                        checked: root.bridge ? (root.bridge.aiEngineMode === "hybrid" || root.bridge.aiEngineMode === "") : true
                                        onClicked: if (root.bridge) root.bridge.aiEngineMode = "hybrid"
                                    }
                                }

                                Text {
                                    text: (root.bridge && root.bridge.aiEngineMode === "semantic_only")
                                        ? tr("desc_ai_mode_minilm", "⚡ MiniLM-only mode active: Only the Fast Multilingual Matcher is needed. Deep Context Reasoner SLM will be completely bypassed.")
                                        : tr("desc_ai_mode_hybrid", "🧠 Full Hybrid mode active: Fast heuristics run first, followed by MiniLM embeddings, and finally Deep Reasoner SLM for ambiguous titles.")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: (root.bridge && root.bridge.aiEngineMode === "semantic_only") ? "#38BDF8" : "#818CF8"
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                }
                            }

                            // Tier 1 Model Card: Fast Multilingual Semantic Matcher
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                implicitHeight: t1Col.implicitHeight + 24
                                radius: 6
                                color: "#0B111E"
                                border.color: root.aiT1Status === "downloading" ? "#0284C7" : "#1E293B"
                                border.width: 1
                                clip: true

                                ColumnLayout {
                                    id: t1Col
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: 12
                                    spacing: 8

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: 8

                                        Text {
                                            text: "⚡"
                                            font.pixelSize: 13
                                        }

                                        Text {
                                            text: tr("model_t1_title", "Fast Multilingual Matcher (MiniLM INT8 • ~127 MB)")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: 600
                                            color: "#E2E8F0"
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            elide: Text.ElideRight
                                        }

                                        // Status Pill
                                        Rectangle {
                                            implicitHeight: 20
                                            implicitWidth: t1StatusText.implicitWidth + 12
                                            radius: 10
                                            color: root.aiT1Status === "downloading" ? "#082F49" : (root.aiT1Status === "error" ? "#450A0A" : ((root.bridge && root.bridge.aiFastSemanticReady) ? "#064E3B" : "#1E293B"))
                                            border.color: root.aiT1Status === "downloading" ? "#0284C7" : (root.aiT1Status === "error" ? "#EF4444" : ((root.bridge && root.bridge.aiFastSemanticReady) ? "#059669" : "#334155"))
                                            border.width: 1

                                            Text {
                                                id: t1StatusText
                                                anchors.centerIn: parent
                                                text: root.aiT1Status === "downloading" ? (root.aiT1Percent.toFixed(1) + "%") : (root.aiT1Status === "error" ? "Error" : ((root.bridge && root.bridge.aiFastSemanticReady) ? "Ready" : "Not Downloaded"))
                                                font.pixelSize: 9
                                                font.weight: 600
                                                color: root.aiT1Status === "downloading" ? "#38BDF8" : (root.aiT1Status === "error" ? "#F87171" : ((root.bridge && root.bridge.aiFastSemanticReady) ? "#34D399" : "#94A3B8"))
                                            }
                                        }

                                        // Action Button
                                        StyledButton {
                                            variant: root.aiT1Status === "downloading" ? "secondary" : ((root.bridge && root.bridge.aiFastSemanticReady) ? "danger" : "primary")
                                            text: root.aiT1Status === "downloading" ? tr("btn_cancel", "Cancel") : ((root.bridge && root.bridge.aiFastSemanticReady) ? tr("btn_remove_model", "Remove") : (root.aiT1Status === "error" ? tr("btn_retry", "Retry") : tr("btn_download_t1", "Download 127 MB")))
                                            implicitHeight: 26
                                            font.pixelSize: 10
                                            onClicked: {
                                                if (!root.bridge) return
                                                if (root.aiT1Status === "downloading") {
                                                    root.bridge.cancelAiModelDownload("fast_semantic")
                                                } else if (root.bridge.aiFastSemanticReady) {
                                                    root.bridge.deleteAiModel("fast_semantic")
                                                } else {
                                                    root.bridge.startAiModelDownload("fast_semantic")
                                                }
                                            }
                                        }
                                    }

                                    // Dedicated Download Progress Bar
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: 4
                                        visible: root.aiT1Status === "downloading"

                                        RowLayout {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0

                                            Text {
                                                text: tr("lbl_downloading_t1", "Downloading model & multilingual tokenizer...")
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 10
                                                font.weight: 600
                                                color: "#38BDF8"
                                                Layout.fillWidth: true
                                                Layout.minimumWidth: 0
                                                elide: Text.ElideRight
                                            }

                                            Text {
                                                text: root.aiT1Speed
                                                font.family: "Cascadia Code, Consolas, monospace"
                                                font.pixelSize: 10
                                                color: "#A78BFA"
                                                visible: root.aiT1Speed !== ""
                                            }

                                            Text {
                                                text: root.aiT1Percent.toFixed(1) + "%"
                                                font.family: "Cascadia Code, Consolas, monospace"
                                                font.pixelSize: 10
                                                font.weight: Font.DemiBold
                                                color: "#E2E8F0"
                                            }
                                        }

                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            height: 6
                                            radius: 3
                                            color: "#161E2E"
                                            border.color: "#1E293B"
                                            border.width: 1
                                            clip: true

                                            Rectangle {
                                                height: parent.height
                                                width: Math.max(0, Math.min(parent.width, parent.width * (root.aiT1Percent / 100.0)))
                                                radius: 3
                                                gradient: Gradient {
                                                    orientation: Gradient.Horizontal
                                                    GradientStop { position: 0.0; color: "#0284C7" }
                                                    GradientStop { position: 1.0; color: "#38BDF8" }
                                                }
                                                Behavior on width {
                                                    NumberAnimation { duration: 160; easing.type: Easing.OutQuad }
                                                }
                                            }
                                        }
                                    }

                                    // Error Notification Banner
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        implicitHeight: 28
                                        radius: 4
                                        color: "#450A0A"
                                        border.color: "#EF4444"
                                        border.width: 1
                                        visible: root.aiT1Status === "error"

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 6
                                            spacing: 6
                                            Text { text: "⚠️"; font.pixelSize: 11 }
                                            Text {
                                                text: root.aiT1Error !== "" ? root.aiT1Error : tr("err_download_failed", "Download failed. Please check your internet connection.")
                                                font.pixelSize: 10
                                                color: "#FCA5A5"
                                                Layout.fillWidth: true
                                                Layout.minimumWidth: 0
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }

                                    Text {
                                        text: tr("desc_model_t1", "Embeds title tokens into multi-dimensional vectors to recognize anime/game characters across Chinese, Japanese, Korean, Russian, and European languages in 1–3 ms.")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: "#64748B"
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                    }
                                }
                            }

                            // Tier 2 Model Card: Deep Context Reasoner (SLM + Archive)
                            Rectangle {
                                id: t2Card
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                implicitHeight: t2Col.implicitHeight + 24
                                radius: 6
                                color: "#0B111E"
                                border.color: currentT2Status === "downloading" ? "#6366F1" : "#1E293B"
                                border.width: 1
                                clip: true

                                readonly property string activeT2Key: (root.bridge && root.bridge.aiDeepReasonerVariant === "heavy") ? "deep_reasoner_heavy" : "deep_reasoner_light"
                                readonly property bool isCurrentT2Ready: (root.bridge && root.bridge.aiDeepReasonerVariant === "heavy") ? root.bridge.aiDeepReasonerHeavyReady : root.bridge.aiDeepReasonerLightReady
                                readonly property string currentT2Status: activeT2Key === "deep_reasoner_heavy" ? root.aiT2HeavyStatus : root.aiT2LightStatus
                                readonly property real currentT2Percent: activeT2Key === "deep_reasoner_heavy" ? root.aiT2HeavyPercent : root.aiT2LightPercent
                                readonly property string currentT2Speed: activeT2Key === "deep_reasoner_heavy" ? root.aiT2HeavySpeed : root.aiT2LightSpeed
                                readonly property string currentT2Error: activeT2Key === "deep_reasoner_heavy" ? root.aiT2HeavyError : root.aiT2LightError

                                ColumnLayout {
                                    id: t2Col
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: 12
                                    spacing: 8

                                    // Optional Notice when in Semantic Matcher Only mode
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        implicitHeight: 26
                                        radius: 4
                                        color: "#161E2E"
                                        border.color: "#1E293B"
                                        border.width: 1
                                        visible: root.bridge ? (root.bridge.aiEngineMode === "semantic_only") : false

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 6
                                            spacing: 6
                                            Text { text: "💡"; font.pixelSize: 11 }
                                            Text {
                                                text: tr("tip_t2_optional", "Optional in 'Semantic Matcher Only' mode. Deep Context Reasoner SLM is only used when 'Full Hybrid' mode is active.")
                                                font.pixelSize: 10
                                                color: "#94A3B8"
                                                font.italic: true
                                                Layout.fillWidth: true
                                                Layout.minimumWidth: 0
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: 8

                                        Text {
                                            text: "🧠"
                                            font.pixelSize: 13
                                        }

                                        Text {
                                            text: tr("model_t2_title", "Deep Context Reasoner (SLM + Archive)")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: 600
                                            color: "#E2E8F0"
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            elide: Text.ElideRight
                                        }

                                        // Status Pill
                                        Rectangle {
                                            implicitHeight: 20
                                            implicitWidth: t2StatusText.implicitWidth + 12
                                            radius: 10
                                            color: t2Card.currentT2Status === "downloading" ? "#312E81" : (t2Card.currentT2Status === "error" ? "#450A0A" : (t2Card.isCurrentT2Ready ? "#064E3B" : "#1E293B"))
                                            border.color: t2Card.currentT2Status === "downloading" ? "#6366F1" : (t2Card.currentT2Status === "error" ? "#EF4444" : (t2Card.isCurrentT2Ready ? "#059669" : "#334155"))
                                            border.width: 1

                                            Text {
                                                id: t2StatusText
                                                anchors.centerIn: parent
                                                text: t2Card.currentT2Status === "downloading" ? (t2Card.currentT2Percent.toFixed(1) + "%") : (t2Card.currentT2Status === "error" ? "Error" : (t2Card.isCurrentT2Ready ? "Ready" : "Not Downloaded"))
                                                font.pixelSize: 9
                                                font.weight: 600
                                                color: t2Card.currentT2Status === "downloading" ? "#A5B4FC" : (t2Card.currentT2Status === "error" ? "#F87171" : (t2Card.isCurrentT2Ready ? "#34D399" : "#94A3B8"))
                                            }
                                        }

                                        // Action Button
                                        StyledButton {
                                            variant: t2Card.currentT2Status === "downloading" ? "secondary" : (t2Card.isCurrentT2Ready ? "danger" : "primary")
                                            text: t2Card.currentT2Status === "downloading" ? tr("btn_cancel", "Cancel") : (t2Card.isCurrentT2Ready ? tr("btn_remove_model", "Remove") : (t2Card.currentT2Status === "error" ? tr("btn_retry", "Retry") : (root.bridge && root.bridge.aiDeepReasonerVariant === "heavy" ? tr("btn_download_t2_smart", "Download 1.0 GB") : tr("btn_download_t2_light", "Download 490 MB"))))
                                            implicitHeight: 26
                                            font.pixelSize: 10
                                            onClicked: {
                                                if (!root.bridge) return
                                                var key = t2Card.activeT2Key
                                                if (t2Card.currentT2Status === "downloading") {
                                                    root.bridge.cancelAiModelDownload(key)
                                                } else if (t2Card.isCurrentT2Ready) {
                                                    root.bridge.deleteAiModel(key)
                                                } else {
                                                    root.bridge.startAiModelDownload(key)
                                                }
                                            }
                                        }
                                    }

                                    // Dedicated Download Progress Bar
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: 4
                                        visible: t2Card.currentT2Status === "downloading"

                                        RowLayout {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0

                                            Text {
                                                text: tr("lbl_downloading_t2", "Downloading reasoning SLM weights...")
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 10
                                                font.weight: 600
                                                color: "#818CF8"
                                                Layout.fillWidth: true
                                                Layout.minimumWidth: 0
                                                elide: Text.ElideRight
                                            }

                                            Text {
                                                text: t2Card.currentT2Speed
                                                font.family: "Cascadia Code, Consolas, monospace"
                                                font.pixelSize: 10
                                                color: "#A78BFA"
                                                visible: t2Card.currentT2Speed !== ""
                                            }

                                            Text {
                                                text: t2Card.currentT2Percent.toFixed(1) + "%"
                                                font.family: "Cascadia Code, Consolas, monospace"
                                                font.pixelSize: 10
                                                font.weight: Font.DemiBold
                                                color: "#E2E8F0"
                                            }
                                        }

                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            height: 6
                                            radius: 3
                                            color: "#161E2E"
                                            border.color: "#1E293B"
                                            border.width: 1
                                            clip: true

                                            Rectangle {
                                                height: parent.height
                                                width: Math.max(0, Math.min(parent.width, parent.width * (t2Card.currentT2Percent / 100.0)))
                                                radius: 3
                                                gradient: Gradient {
                                                    orientation: Gradient.Horizontal
                                                    GradientStop { position: 0.0; color: "#4F46E5" }
                                                    GradientStop { position: 1.0; color: "#818CF8" }
                                                }
                                                Behavior on width {
                                                    NumberAnimation { duration: 160; easing.type: Easing.OutQuad }
                                                }
                                            }
                                        }
                                    }

                                    // Error Notification Banner
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        implicitHeight: 28
                                        radius: 4
                                        color: "#450A0A"
                                        border.color: "#EF4444"
                                        border.width: 1
                                        visible: t2Card.currentT2Status === "error"

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 6
                                            spacing: 6
                                            Text { text: "⚠️"; font.pixelSize: 11 }
                                            Text {
                                                text: t2Card.currentT2Error !== "" ? t2Card.currentT2Error : tr("err_download_failed", "Download failed. Please check your internet connection.")
                                                font.pixelSize: 10
                                                color: "#FCA5A5"
                                                Layout.fillWidth: true
                                                Layout.minimumWidth: 0
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }

                                    // Variant Selector: Light vs Smart
                                    Text {
                                        text: tr("lbl_llm_tier", "Model Size:")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: 600
                                        color: "#E2E8F0"
                                    }

                                    Flow {
                                        width: parent.width
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: 8

                                        FilterCheckbox {
                                            label: tr("llm_opt_light", "Light (Qwen 0.5B • ~490 MB)")
                                            iconText: "🪶"
                                            activeColor: "#34D399"
                                            tooltip: tr("llm_opt_light_tip", "Potato-friendly 0.5B model. Low memory (~450 MB RAM), quick deductions on CPU.")
                                            checked: root.bridge ? root.bridge.aiDeepReasonerVariant === "light" : true
                                            onClicked: if (root.bridge) root.bridge.aiDeepReasonerVariant = "light"
                                        }

                                        FilterCheckbox {
                                            label: tr("llm_opt_smart", "Smart (Qwen 1.5B • ~1.04 GB)")
                                            iconText: "✨"
                                            activeColor: "#818CF8"
                                            tooltip: tr("llm_opt_smart_tip", "Higher intelligence and deeper anime & pop culture knowledge. Best for modern GPUs/CPUs.")
                                            checked: root.bridge ? root.bridge.aiDeepReasonerVariant === "heavy" : false
                                            onClicked: if (root.bridge) root.bridge.aiDeepReasonerVariant = "heavy"
                                        }
                                    }

                                    Text {
                                        text: tr("desc_model_t2", "Deduces character and series names by cross-referencing subtle post tokens against the creator's historical download patterns from download_archive.db.")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: "#64748B"
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                    }
                                }
                            }

                            // Interactive Testing Sandbox Card
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                implicitHeight: sandboxCol.implicitHeight + 24
                                radius: 6
                                color: "#0B111E"
                                border.color: "#1E293B"
                                border.width: 1
                                clip: true

                                ColumnLayout {
                                    id: sandboxCol
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: 12
                                    spacing: 8

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: 6

                                        Text {
                                            text: "🧪"
                                            font.pixelSize: 12
                                        }

                                        Text {
                                            text: tr("sandbox_title", "Live AI Recognition Test Sandbox")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: 600
                                            color: "#E2E8F0"
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            elide: Text.ElideRight
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: 8

                                        StyledTextField {
                                            id: aiTestInput
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            placeholderText: tr("sandbox_placeholder", "Enter a messy title, e.g. 【五等分】水着 4K, 乃木坂, or Nino Nakano...")
                                            onAccepted: testAiBtn.clicked()
                                        }

                                        StyledButton {
                                            id: testAiBtn
                                            variant: "primary"
                                            text: tr("btn_test_ai", "Test Match")
                                            iconText: "🔍"
                                            implicitHeight: 34
                                            onClicked: {
                                                if (root.bridge && aiTestInput.text.trim().length > 0) {
                                                    var res = root.bridge.testAiRecognition(aiTestInput.text.trim())
                                                    aiResultText.text = "Heuristic: " + res.tier0 + "  |  AI Semantic: " + res.tier1 + "  ➔  Final Folder: " + res.final
                                                }
                                            }
                                        }
                                    }

                                    Text {
                                        id: aiResultText
                                        text: tr("sandbox_hint", "Type a post title above and click 'Test Match' to preview how Pawchive categorizes it in real time.")
                                        font.family: "Consolas, monospace"
                                        font.pixelSize: 10
                                        color: "#38BDF8"
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                    }
                                }
                            }
                        }
                    }
                }

            }
        }

        // Post-Download & System Actions (What to do after done)
        CardSection {
            Layout.fillWidth: true
            interactive: !root.isScrolling
            title: tr("section_post_actions", "Post-Download & System Actions")
            iconText: "⚡"
            entranceOffsetY: root.entranceStage >= 6 ? 0 : 24
            entranceOpacity: root.entranceStage >= 6 ? 1.0 : 0.0

            ColumnLayout {
                width: parent.width
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 12

                // Convenient checkboxes for notifications / folders
                Flow {
                    width: parent.width
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 16

                    StyledCheckBox {
                        text: tr("opt_open_complete", "Open download directory when complete")
                        tooltip: tr("opt_open_complete_tip", "Automatically open Windows File Explorer to the downloaded creator folder")
                        checked: root.bridge ? root.bridge.openFolderOnComplete : false
                        onCheckedChanged: if (root.bridge) root.bridge.openFolderOnComplete = checked
                    }

                    StyledCheckBox {
                        text: tr("opt_chime_complete", "Play chime sound when complete")
                        tooltip: tr("opt_chime_complete_tip", "Play an audible notification chime when all download tasks finish")
                        checked: root.bridge ? root.bridge.playCompletionSound : false
                        onCheckedChanged: if (root.bridge) root.bridge.playCompletionSound = checked
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: "#1E293B"
                }

                // Power/App Action Selector
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3
                        Text {
                            text: tr("label_what_to_do", "What to do after download finishes (one-time action):")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#94A3B8"
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            text: tr("note_what_to_do", "• Resets to 'Do Nothing' after each task. Can also be set directly in the bottom action bar.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#64748B"
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                    }

                    Flow {
                        width: parent.width
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 8

                        FilterCheckbox {
                            label: tr("action_none", "Do Nothing")
                            iconText: "⏸️"
                            tooltip: tr("action_none_tip", "Keep application open and system running normally")
                            checked: root.bridge ? (root.bridge.postDownloadAction === "none" || root.bridge.postDownloadAction === "") : true
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "none"
                        }

                        FilterCheckbox {
                            label: tr("action_close", "Close App")
                            iconText: "🚪"
                            activeColor: "#38BDF8"
                            tooltip: tr("action_close_tip", "Automatically exit Pawchive Downloader when all files finish downloading")
                            checked: root.bridge ? root.bridge.postDownloadAction === "close_app" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "close_app"
                        }

                        FilterCheckbox {
                            label: tr("action_sleep", "Sleep System")
                            iconText: "🌙"
                            activeColor: "#A78BFA"
                            tooltip: tr("action_sleep_tip", "Put the computer into sleep / suspend mode after download completes")
                            checked: root.bridge ? root.bridge.postDownloadAction === "sleep" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "sleep"
                        }

                        FilterCheckbox {
                            label: tr("action_hibernate", "Hibernate (-F Force)")
                            iconText: "💤"
                            activeColor: "#818CF8"
                            tooltip: tr("action_hibernate_tip", "Force save memory to disk and turn off power (Hibernate -F)")
                            checked: root.bridge ? root.bridge.postDownloadAction === "hibernate" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "hibernate"
                        }

                        FilterCheckbox {
                            label: tr("action_shutdown", "Shut Down (-F Force)")
                            iconText: "🔌"
                            activeColor: "#F43F5E"
                            tooltip: tr("action_shutdown_tip", "Force close running applications and safely shut down the computer (includes 10s cancel buffer)")
                            checked: root.bridge ? root.bridge.postDownloadAction === "shutdown" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "shutdown"
                        }

                        FilterCheckbox {
                            label: tr("action_restart", "Restart (-F Force)")
                            iconText: "🔄"
                            activeColor: "#F59E0B"
                            tooltip: tr("action_restart_tip", "Force close running applications and restart the operating system")
                            checked: root.bridge ? root.bridge.postDownloadAction === "restart" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "restart"
                        }
                    }
                }
            }
        }

        // Section: Telegram Integration
        CardSection {
            Layout.fillWidth: true
            interactive: !root.isScrolling
            title: tr("section_telegram", "Telegram Integration & Account Settings")
            iconText: "✈️"
            entranceOffsetY: root.entranceStage >= 6 ? 0 : 24
            entranceOpacity: root.entranceStage >= 6 ? 1.0 : 0.0

            ColumnLayout {
                width: parent.width
                spacing: 12

                // Status & Quick Connect Row
                RowLayout {
                    Layout.fillWidth: true
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
                        spacing: 2

                        Text {
                            text: (telegramBridge && telegramBridge.isLoggedIn)
                                  ? (tr("tg_connected_as", "Connected as @") + telegramBridge.currentUsername + (telegramBridge.currentPhone ? " (" + telegramBridge.currentPhone + ")" : ""))
                                  : tr("tg_not_connected", "Telegram Account Not Connected")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: (telegramBridge && telegramBridge.isLoggedIn) ? "#34D399" : "#94A3B8"
                        }

                        Text {
                            text: (telegramBridge && telegramBridge.isLoggedIn)
                                  ? tr("tg_ready_desc", "Ready to download media from public and private Telegram channels.")
                                  : tr("tg_connect_desc", "Connect via QR code, phone number, or bot token to enable downloads.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#64748B"
                        }
                    }

                    StyledButton {
                        text: (telegramBridge && telegramBridge.isLoggedIn) ? tr("tg_btn_manage", "Manage / Switch") : tr("tg_btn_connect", "Connect Telegram")
                        implicitWidth: 150
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
                    visible: telegramBridge && telegramBridge.isLoggedIn
                    spacing: 8

                    Text {
                        text: "🔄"
                        font.pixelSize: 12
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: tr("tg_reset_title", "Reset Telegram Session")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: "#F87171"
                        }

                        Text {
                            Layout.fillWidth: true
                            text: tr("tg_reset_desc", "Wipes the saved session and forces a clean re-login. Use this if you see auth errors or the account is acting unexpectedly.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#64748B"
                            wrapMode: Text.WordWrap
                        }
                    }

                    StyledButton {
                        text: tr("tg_btn_reset_login", "Reset Login")
                        implicitWidth: 110
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
                    implicitHeight: tgMiniNotice.implicitHeight + 12
                    radius: 6
                    color: "#251214"
                    border.color: "#EF4444"
                    border.width: 1

                    RowLayout {
                        id: tgMiniNotice
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Text {
                            text: "⚠️"
                            font.pixelSize: 13
                        }

                        Text {
                            Layout.fillWidth: true
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
                    visible: bridge ? (bridge.telegramSafetyAcknowledged || bridge.telegramLiabilityAcknowledged) : false
                    spacing: 8

                    Text {
                        text: tr("tg_warnings_dismissed", "⚠️ Telegram safety advisory / liability disclaimer has been dismissed.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        Layout.fillWidth: true
                    }

                    StyledButton {
                        text: tr("tg_btn_reset_warnings", "Reset Warning Prompts")
                        variant: "outline"
                        Layout.preferredHeight: 28
                        Layout.preferredWidth: 160
                        onClicked: {
                            if (bridge) bridge.resetTelegramWarnings()
                        }
                    }
                }

                // Advanced Custom Credentials Collapsible
                ColumnLayout {
                    Layout.fillWidth: true
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
                        spacing: 8
                        visible: false

                        Text {
                            Layout.fillWidth: true
                            text: tr("tg_custom_api_desc", "By default, Pawchive uses standard built-in credentials. If you experience connection limits, obtain your free api_id & api_hash from my.telegram.org and save them below:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#64748B"
                            wrapMode: Text.WordWrap
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            StyledTextField {
                                id: customApiIdInput
                                Layout.preferredWidth: 160
                                placeholderText: "API ID (e.g. 123456)"
                            }

                            StyledTextField {
                                id: customApiHashInput
                                Layout.fillWidth: true
                                placeholderText: "API Hash (32 characters)"
                            }

                            StyledButton {
                                text: tr("btn_save", "Save Keys")
                                implicitWidth: 90
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

        // Action Buttons & About
        Flow {
            width: parent.width
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8
            layoutDirection: Qt.RightToLeft
            opacity: root.entranceStage >= 7 ? 1.0 : 0.0
            transform: Translate {
                y: root.entranceStage >= 7 ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.0; damping: 0.38; mass: 1.0; epsilon: 0.25 }
                }
            }
            Behavior on opacity {
                NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
            }

            StyledButton {
                text: tr("btn_save_preferences", "Save Preferences")
                iconText: "💾"
                variant: "primary"
                onClicked: if (root.bridge) root.bridge.saveSettings()
            }

            StyledButton {
                text: tr("btn_export_console_logs", "Export Console Logs")
                iconText: "📄"
                variant: "outline"
                onClicked: if (root.bridge) root.bridge.exportLogs()
            }

            StyledButton {
                text: "☕ " + tr("btn_support_kofi", "Support on Ko-fi")
                variant: "outline"
                onClicked: Qt.openUrlExternally("https://ko-fi.com/whyamihere773")
            }

            StyledButton {
                text: "🔄 " + (typeof updaterBridge !== "undefined" && updaterBridge && updaterBridge.isChecking ? tr("btn_checking_update", "Checking...") : tr("btn_check_update", "Check for Updates"))
                variant: "outline"
                enabled: !(typeof updaterBridge !== "undefined" && updaterBridge && updaterBridge.isChecking)
                onClicked: {
                    if (typeof updaterBridge !== "undefined" && updaterBridge) {
                        updaterBridge.checkForUpdates(false)
                        appWindow.openUpdateModal()
                    }
                }
            }

            StyledButton {
                text: "📂 " + tr("btn_open_logs", "Logs Folder")
                variant: "outline"
                onClicked: if (root.bridge) root.bridge.openLogsFolder()
            }
        }
    }
}
