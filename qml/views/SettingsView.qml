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

    Component.onCompleted: triggerEntrance()
    onVisibleChanged: if (visible) triggerEntrance()

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
                        Layout.preferredWidth: 240
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
                            rightPadding: langCombo.indicator.width + 10
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

                    Item { Layout.fillWidth: true }
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
                spacing: 10

                Text {
                    text: tr("label_cookie", "Session Cookie (Useful for Patreon / Fanbox / Cloudflare bypass):")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
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
                            }

                            Item { Layout.fillWidth: true }

                            // Real-time Expiration Watchdog Badge
                            Rectangle {
                                height: 20
                                implicitWidth: watchdogLabel.implicitWidth + 16
                                radius: 10
                                color: "#0F172A"
                                border.color: root.bridge ? root.bridge.cookieWatchdogColor : "#64748B"
                                border.width: 1

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
                            Layout.fillWidth: true
                            spacing: 8

                            ComboBox {
                                id: browserSelector
                                Layout.preferredWidth: 190
                                Layout.preferredHeight: 30
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
                    text: tr("opt_desktop_report", "Generate completion report on Desktop (HTML & TXT)")
                    tooltip: tr("opt_desktop_report_tip", "Automatically save a visual summary report and failure log to your Desktop upon completion")
                    checked: root.bridge ? root.bridge.generateDesktopReport : false
                    onCheckedChanged: if (root.bridge) root.bridge.generateDesktopReport = checked
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
                    }

                    Item { Layout.fillWidth: true }

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
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

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
                        implicitWidth: 120
                        onValueModified: function(v) {
                            if (root.bridge) root.bridge.setStoragePoolMargin(v)
                        }
                    }

                    Text {
                        text: "(" + tr("desc_margin_trigger", "triggers overflow when remaining space drops below this limit") + ")"
                        font.pixelSize: 11
                        color: "#64748B"
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
                                            Layout.minimumWidth: 60
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
                                            text: modelData.free_gb + " GB free / " + modelData.total_gb + " GB (" + modelData.used_percent + "% used)"
                                            font.pixelSize: 10
                                            color: modelData.is_low ? "#EF4444" : "#94A3B8"
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
                spacing: 10

                Text {
                    text: tr("desc_known_engine", "Choose how the engine identifies characters and structures folders (Franchise ➔ Character):")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                Flow {
                    Layout.fillWidth: true
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
                spacing: 12

                // Convenient checkboxes for notifications / folders
                Flow {
                    Layout.fillWidth: true
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

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: tr("label_what_to_do", "What to do after download finishes (one-time action):")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#94A3B8"
                        }
                        Text {
                            text: tr("note_what_to_do", "• Resets to 'Do Nothing' after each task. Can also be set directly in the bottom action bar.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#64748B"
                            Layout.fillWidth: true
                        }
                    }

                    Flow {
                        Layout.fillWidth: true
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

        // Action Buttons & About
        Flow {
            Layout.fillWidth: true
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
