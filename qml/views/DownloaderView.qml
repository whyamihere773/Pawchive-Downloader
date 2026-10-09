import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

SmoothFlickable {
    id: root

    property var bridge: null
    property int currentSubTab: 0

    // Fluid Newtonian Entrance parameters triggered on sub-tab switch
    property real tabEntranceOffsetY: 0
    property real tabEntranceOpacity: 1.0

    // Buttons that cycle through labels are as wide as their longest one, so long translations
    // (Russian, German…) fit and the button doesn't change size when clicked. Same font as StyledButton.
    FontMetrics {
        id: buttonFontMetrics
        font.family: "Segoe UI, Inter, sans-serif"
        font.pixelSize: 12
        font.weight: Font.Medium
    }
    function widestLabel(labels) {
        var w = 0
        for (var i = 0; i < labels.length; i++)
            w = Math.max(w, buttonFontMetrics.advanceWidth(labels[i]))
        return Math.ceil(w)
    }

    onCurrentSubTabChanged: {
        tabEntranceOffsetY = 14.0
        tabEntranceOpacity = 0.45
        tabEntranceTimer.restart()
    }

    Timer {
        id: tabEntranceTimer
        interval: 16
        repeat: false
        onTriggered: {
            root.tabEntranceOffsetY = 0.0
            root.tabEntranceOpacity = 1.0
        }
    }

    Behavior on tabEntranceOffsetY {
        SpringAnimation {
            spring: 4.2
            damping: 0.38
            mass: 1.15
            epsilon: 0.1
        }
    }

    Behavior on tabEntranceOpacity {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    // Helper function to check if an extension is active in bridge.exactExtensions
    function isExtActive(ext) {
        if (!root.bridge || !root.bridge.exactExtensions) return false
        var exts = root.bridge.exactExtensions.toLowerCase().split(/[,;\s]+/)
        var target = ext.toLowerCase().trim()
        if (target.startsWith("*")) target = target.substring(1)
        if (!target.startsWith(".")) target = "." + target
        for (var i = 0; i < exts.length; i++) {
            var item = exts[i].trim()
            if (!item) continue
            if (item.startsWith("*")) item = item.substring(1)
            if (!item.startsWith(".")) item = "." + item
            if (item === target) return true
        }
        return false
    }

    // Helper function to count selected extensions
    function countActiveExtensions() {
        if (!root.bridge || !root.bridge.exactExtensions) return 0
        var tokens = root.bridge.exactExtensions.split(/[,;\s]+/)
        var count = 0
        for (var i = 0; i < tokens.length; i++) {
            if (tokens[i].trim().length > 0) count++
        }
        return count
    }

    // Active filters count for reactive badge on Tab 1
    readonly property int activeFilterCount: {
        if (!root.bridge) return 0
        var count = 0
        if (root.bridge.filterCharacters && root.bridge.filterCharacters.trim().length > 0) count++
        if (root.bridge.skipWords && root.bridge.skipWords.trim().length > 0) count++
        if (root.bridge.removeWords && root.bridge.removeWords.trim().length > 0) count++
        if (root.bridge.dateAfter && root.bridge.dateAfter.trim().length > 0) count++
        if (root.bridge.dateBefore && root.bridge.dateBefore.trim().length > 0) count++
        if (root.bridge.minFileSize && root.bridge.minFileSize.trim().length > 0) count++
        if (root.bridge.maxFileSize && root.bridge.maxFileSize.trim().length > 0) count++
        return count
    }

    // Concurrency thread chip label for Tab 2
    readonly property string threadChipText: {
        if (!root.bridge) return "4T"
        if (root.bridge.isTelegramUrl) return "2T 🔒"
        if (root.bridge.threadsLocked) return root.bridge.threadsCount + "T 🔒"
        if (root.bridge.adaptiveThreading) return root.bridge.threadsCount + "T ⚡"
        return root.bridge.threadsCount + "T"
    }

    // Batch URLs detected count for Tab 3
    readonly property int detectedBatchUrlCount: {
        if (!batchInput || !batchInput.text) return 0
        var lines = batchInput.text.split("\n")
        var count = 0
        for (var i = 0; i < lines.length; i++) {
            if (lines[i].trim().indexOf("http") === 0) count++
        }
        return count
    }

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    // Helper functions for file size normalization and parsing
    function normalizeSizeInput(s) {
        if (!s) return ""
        var str = s.trim()
        if (!str) return ""
        var m = str.match(/^([\d.]+)\s*([A-Za-z]+)?/)
        if (!m || !m[1]) return ""
        var val = parseFloat(m[1])
        if (isNaN(val) || val <= 0) return ""
        var rawUnit = (m[2] || "MB").toUpperCase()
        var unit = "MB"
        if (rawUnit === "B" || rawUnit === "BYTE" || rawUnit === "BYTES") unit = "B"
        else if (rawUnit.indexOf("K") === 0) unit = "KB"
        else if (rawUnit.indexOf("M") === 0) unit = "MB"
        else if (rawUnit.indexOf("G") === 0) unit = "GB"
        else if (rawUnit.indexOf("T") === 0) unit = "TB"
        else if (rawUnit.indexOf("P") === 0) unit = "PB"

        var numStr = (Math.round(val * 100) / 100).toString()
        return numStr + " " + unit
    }

    function parseBytes(s) {
        if (!s) return 0
        var str = s.trim().toUpperCase()
        var m = str.match(/^([\d.]+)\s*([A-Z]+)?$/)
        if (!m || !m[1]) return 0
        var val = parseFloat(m[1])
        if (isNaN(val) || val <= 0) return 0
        var unit = m[2] || "MB"
        if (unit.indexOf("K") === 0) return Math.round(val * 1024)
        if (unit.indexOf("M") === 0) return Math.round(val * 1048576)
        if (unit.indexOf("G") === 0) return Math.round(val * 1073741824)
        if (unit.indexOf("T") === 0) return Math.round(val * 1099511627776)
        if (unit.indexOf("P") === 0) return Math.round(val * 1125899906842624)
        if (unit.indexOf("B") === 0) return Math.round(val)
        return Math.round(val * 1048576)
    }

    contentWidth: width
    contentHeight: contentCol.implicitHeight + 16

    ColumnLayout {
        id: contentCol
        width: root.width - (root.verticalScrollBar && root.verticalScrollBar.visible ? 10 : 0)
        spacing: 12

        // ====================================================================
        // ALWAYS VISIBLE: Download Destination Card
        // ====================================================================
        CardSection {
            Layout.fillWidth: true
            title: root.tr("section_destination", "Download Destination")
            iconText: "📁"

            RowLayout {
                width: parent.width
                spacing: 8

                StyledTextField {
                    id: dirInput
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    text: root.bridge ? root.bridge.downloadDir : ""
                    leadingIcon: "💾"
                    showClearButton: false
                    onTextChanged: {
                        if (root.bridge && root.bridge.downloadDir !== text) {
                            root.bridge.downloadDir = text
                        }
                    }
                }

                StyledButton {
                    text: root.tr("btn_browse", "Browse...")
                    iconText: "📂"
                    variant: "outline"
                    tooltip: root.tr("btn_browse_tip", "Select destination folder for downloads")
                    onClicked: {
                        if (root.bridge) root.bridge.selectDownloadDirectory()
                    }
                }

                StyledButton {
                    text: root.tr("btn_open", "Open")
                    iconText: "↗"
                    variant: "ghost"
                    implicitWidth: Math.max(70, contentItem.implicitWidth + 20)
                    tooltip: root.tr("btn_open_tip", "Open current downloads directory in Windows File Explorer")
                    onClicked: {
                        if (root.bridge) root.bridge.openDownloadFolder()
                    }
                }

                StyledButton {
                    text: root.tr("btn_gallery", "Gallery")
                    iconText: "🖼"
                    variant: "ghost"
                    implicitWidth: Math.max(86, contentItem.implicitWidth + 20)
                    tooltip: root.tr("btn_gallery_tip", "Browse the current (or last) download's folder in the Gallery tab")
                    onClicked: {
                        if (root.bridge) root.bridge.showDownloadsInGallery()
                    }
                }
            }
        }

        // ====================================================================
        // SEGMENTED MODE SWITCHER BAR WITH NEWTONIAN FLUID GLIDER
        // ====================================================================
        Rectangle {
            id: subTabDock
            Layout.fillWidth: true
            implicitHeight: 46
            radius: 10
            color: "#0F131C"
            border.color: "#1E2536"
            border.width: 1

            readonly property bool isCompact: width < 660

            readonly property var activeBtn: {
                if (root.currentSubTab === 0) return tabBtn0
                if (root.currentSubTab === 1) return tabBtn1
                if (root.currentSubTab === 2) return tabBtn2
                return tabBtn3
            }

            // Liquid Gliding Active Indicator Pill
            Rectangle {
                id: tabGlider
                y: 5
                height: 36
                radius: 8
                color: "#1B2232"
                border.color: "#38BDF8"
                border.width: 1
                x: subTabDock.activeBtn ? (subTabDock.activeBtn.x + 4) : 4
                width: subTabDock.activeBtn ? subTabDock.activeBtn.width : 100

                // Liquid soft cyan aura
                Rectangle {
                    anchors.fill: parent
                    radius: 7
                    color: Qt.rgba(56/255, 189/255, 248/255, 0.08)
                }

                // Newtonian Fluid Spring Physics for gliding between tabs
                Behavior on x {
                    SpringAnimation {
                        spring: 4.8
                        damping: 0.35
                        mass: 0.85
                        epsilon: 0.2
                    }
                }
                Behavior on width {
                    SpringAnimation {
                        spring: 5.0
                        damping: 0.36
                        mass: 0.85
                        epsilon: 0.2
                    }
                }
            }

            RowLayout {
                id: tabRow
                anchors.fill: parent
                anchors.margins: 4
                spacing: 4

                // Tab 0: Quick Download
                Item {
                    id: tabBtn0
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    scale: tabMouse0.pressed ? 0.93 : (tabMouse0.containsMouse ? 1.025 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale {
                        SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.70; epsilon: 0.005 }
                    }

                    transform: Translate {
                        y: tabMouse0.containsMouse ? -1.0 : 0.0
                        Behavior on y {
                            SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 }
                        }
                    }

                    Row {
                        anchors.centerIn: parent
                        spacing: subTabDock.isCompact ? 4 : 6

                        Text {
                            text: "⚡"
                            font.pixelSize: subTabDock.isCompact ? 12 : 13
                            anchors.verticalCenter: parent.verticalCenter
                            scale: (root.currentSubTab === 0 || tabMouse0.containsMouse) ? 1.15 : 1.0
                            Behavior on scale {
                                SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7; epsilon: 0.01 }
                            }
                        }

                        Text {
                            text: subTabDock.isCompact ? root.tr("tab_quick_short", "Quick") : root.tr("tab_quick_download", "Quick Download")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: subTabDock.isCompact ? 11 : 12
                            font.weight: root.currentSubTab === 0 ? 600 : Font.Medium
                            color: root.currentSubTab === 0 ? "#F8FAFC" : (tabMouse0.containsMouse ? "#CBD5E1" : "#94A3B8")
                            elide: Text.ElideRight
                            width: Math.min(implicitWidth, tabBtn0.width - (subTabDock.isCompact ? 24 : 32))
                            anchors.verticalCenter: parent.verticalCenter
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }
                    }

                    MouseArea {
                        id: tabMouse0
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.currentSubTab = 0
                    }
                }

                // Tab 1: Filters & Dates
                Item {
                    id: tabBtn1
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    scale: tabMouse1.pressed ? 0.93 : (tabMouse1.containsMouse ? 1.025 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale {
                        SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.70; epsilon: 0.005 }
                    }

                    transform: Translate {
                        y: tabMouse1.containsMouse ? -1.0 : 0.0
                        Behavior on y {
                            SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 }
                        }
                    }

                    Row {
                        anchors.centerIn: parent
                        spacing: subTabDock.isCompact ? 4 : 5

                        Text {
                            text: "🎯"
                            font.pixelSize: subTabDock.isCompact ? 12 : 13
                            anchors.verticalCenter: parent.verticalCenter
                            scale: (root.currentSubTab === 1 || tabMouse1.containsMouse) ? 1.15 : 1.0
                            Behavior on scale {
                                SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7; epsilon: 0.01 }
                            }
                        }

                        Text {
                            text: subTabDock.isCompact ? root.tr("tab_filters_short", "Filters") : root.tr("tab_filters_dates", "Filters & Dates")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: subTabDock.isCompact ? 11 : 12
                            font.weight: root.currentSubTab === 1 ? 600 : Font.Medium
                            color: root.currentSubTab === 1 ? "#F8FAFC" : (tabMouse1.containsMouse ? "#CBD5E1" : "#94A3B8")
                            elide: Text.ElideRight
                            width: Math.min(implicitWidth, tabBtn1.width - (root.activeFilterCount > 0 ? 42 : 28))
                            anchors.verticalCenter: parent.verticalCenter
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }

                        // Active filter count mini-pill
                        Rectangle {
                            id: filterBadge
                            visible: root.activeFilterCount > 0
                            width: visible ? 16 : 0
                            height: 16
                            radius: 8
                            color: "#0369A1"
                            border.color: "#38BDF8"
                            border.width: 1
                            anchors.verticalCenter: parent.verticalCenter

                            scale: visible ? 1.0 : 0.0
                            Behavior on scale {
                                SpringAnimation { spring: 5.5; damping: 0.32; mass: 0.75; epsilon: 0.01 }
                            }

                            Text {
                                anchors.centerIn: parent
                                text: root.activeFilterCount.toString()
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.bold: true
                                color: "#F0F9FF"
                            }
                        }
                    }

                    MouseArea {
                        id: tabMouse1
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.currentSubTab = 1
                    }
                }

                // Tab 2: Structure & Engine
                Item {
                    id: tabBtn2
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    scale: tabMouse2.pressed ? 0.93 : (tabMouse2.containsMouse ? 1.025 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale {
                        SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.70; epsilon: 0.005 }
                    }

                    transform: Translate {
                        y: tabMouse2.containsMouse ? -1.0 : 0.0
                        Behavior on y {
                            SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 }
                        }
                    }

                    Row {
                        anchors.centerIn: parent
                        spacing: subTabDock.isCompact ? 4 : 6

                        Text {
                            text: "⚙️"
                            font.pixelSize: subTabDock.isCompact ? 12 : 13
                            anchors.verticalCenter: parent.verticalCenter
                            scale: (root.currentSubTab === 2 || tabMouse2.containsMouse) ? 1.15 : 1.0
                            Behavior on scale {
                                SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7; epsilon: 0.01 }
                            }
                        }

                        Text {
                            text: subTabDock.isCompact ? root.tr("tab_structure_short", "Engine") : root.tr("tab_structure_engine", "Structure & Engine")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: subTabDock.isCompact ? 11 : 12
                            font.weight: root.currentSubTab === 2 ? 600 : Font.Medium
                            color: root.currentSubTab === 2 ? "#F8FAFC" : (tabMouse2.containsMouse ? "#CBD5E1" : "#94A3B8")
                            elide: Text.ElideRight
                            width: Math.min(implicitWidth, tabBtn2.width - (subTabDock.isCompact ? 36 : 50))
                            anchors.verticalCenter: parent.verticalCenter
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }

                        // Concurrency & Adaptive thread chip mini-pill
                        Rectangle {
                            id: threadBadge
                            implicitWidth: threadBadgeText.implicitWidth + 10
                            height: 16
                            radius: 8
                            color: (root.bridge && root.bridge.threadsLocked) ? "#3A1A1C"
                                   : ((root.bridge && root.bridge.adaptiveThreading) ? "#291E0A" : "#0C1828")
                            border.color: (root.bridge && root.bridge.threadsLocked) ? "#EF4444"
                                          : ((root.bridge && root.bridge.adaptiveThreading) ? "#F59E0B" : "#164E63")
                            border.width: 1
                            anchors.verticalCenter: parent.verticalCenter

                            Text {
                                id: threadBadgeText
                                anchors.centerIn: parent
                                text: root.threadChipText
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.bold: true
                                color: (root.bridge && root.bridge.threadsLocked) ? "#FCA5A5"
                                       : ((root.bridge && root.bridge.adaptiveThreading) ? "#FCD34D" : "#7DD3FA")
                            }
                        }
                    }

                    MouseArea {
                        id: tabMouse2
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.currentSubTab = 2
                    }
                }

                // Tab 3: Batch Importer
                Item {
                    id: tabBtn3
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    scale: tabMouse3.pressed ? 0.93 : (tabMouse3.containsMouse ? 1.025 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale {
                        SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.70; epsilon: 0.005 }
                    }

                    transform: Translate {
                        y: tabMouse3.containsMouse ? -1.0 : 0.0
                        Behavior on y {
                            SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 }
                        }
                    }

                    Row {
                        anchors.centerIn: parent
                        spacing: subTabDock.isCompact ? 4 : 5

                        Text {
                            text: "📋"
                            font.pixelSize: subTabDock.isCompact ? 12 : 13
                            anchors.verticalCenter: parent.verticalCenter
                            scale: (root.currentSubTab === 3 || tabMouse3.containsMouse) ? 1.15 : 1.0
                            Behavior on scale {
                                SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7; epsilon: 0.01 }
                            }
                        }

                        Text {
                            text: subTabDock.isCompact ? root.tr("tab_batch_short", "Batch") : root.tr("tab_batch_import", "Batch Importer")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: subTabDock.isCompact ? 11 : 12
                            font.weight: root.currentSubTab === 3 ? 600 : Font.Medium
                            color: root.currentSubTab === 3 ? "#F8FAFC" : (tabMouse3.containsMouse ? "#CBD5E1" : "#94A3B8")
                            elide: Text.ElideRight
                            width: Math.min(implicitWidth, tabBtn3.width - (root.detectedBatchUrlCount > 0 ? 42 : 28))
                            anchors.verticalCenter: parent.verticalCenter
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }

                        // Batch URL count mini-pill
                        Rectangle {
                            id: batchUrlBadge
                            visible: root.detectedBatchUrlCount > 0
                            width: visible ? 16 : 0
                            height: 16
                            radius: 8
                            color: "#065F46"
                            border.color: "#10B981"
                            border.width: 1
                            anchors.verticalCenter: parent.verticalCenter

                            scale: visible ? 1.0 : 0.0
                            Behavior on scale {
                                SpringAnimation { spring: 5.5; damping: 0.32; mass: 0.75; epsilon: 0.01 }
                            }

                            Text {
                                anchors.centerIn: parent
                                text: root.detectedBatchUrlCount.toString()
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.bold: true
                                color: "#ECFDF5"
                            }
                        }
                    }

                    MouseArea {
                        id: tabMouse3
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.currentSubTab = 3
                    }
                }
            }
        }

        // ====================================================================
        // SUB-TAB 0: QUICK DOWNLOAD (File Types, Quality, Content)
        // ====================================================================
        ColumnLayout {
            id: subTab0Content
            visible: root.currentSubTab === 0
            Layout.fillWidth: true
            spacing: 12

            // Card 0.1: Media Categories & Core Formats
            CardSection {
                Layout.fillWidth: true
                title: root.tr("section_file_types", "Filter Files & Content Mode")
                iconText: "🗂️"
                entranceOffsetY: root.tabEntranceOffsetY
                entranceOpacity: root.tabEntranceOpacity

                ColumnLayout {
                    width: parent.width
                    spacing: 10

                    // Media type filter pills (Single-select category)
                    Flow {
                        width: parent.width
                        Layout.fillWidth: true
                        spacing: 6

                        FilterCheckbox {
                            label: root.tr("filter_all_files", "All Files")
                            iconText: "📁"
                            tooltip: root.tr("filter_all_files_tip", "Download all attachments and media files")
                            checked: root.bridge ? root.bridge.filterType === "all" : true
                            onClicked: if (root.bridge) root.bridge.filterType = "all"
                        }

                        FilterCheckbox {
                            label: root.tr("filter_images", "Images/GIFs")
                            iconText: "🖼️"
                            tooltip: root.tr("filter_images_tip", "Download image formats (PNG, JPG, GIF, WebP, BMP)")
                            checked: root.bridge ? root.bridge.filterType === "images" : false
                            onClicked: if (root.bridge) root.bridge.filterType = "images"
                        }

                        FilterCheckbox {
                            label: root.tr("filter_videos", "Videos")
                            iconText: "🎬"
                            tooltip: root.tr("filter_videos_tip", "Download video formats (MP4, MKV, WebM, MOV, M4V)")
                            checked: root.bridge ? root.bridge.filterType === "videos" : false
                            onClicked: if (root.bridge) root.bridge.filterType = "videos"
                        }

                        FilterCheckbox {
                            label: root.tr("filter_archives", "Archives")
                            iconText: "📦"
                            tooltip: root.tr("filter_archives_tip", "Download compressed archive packages (ZIP, RAR, 7Z, TAR)")
                            checked: root.bridge ? root.bridge.filterType === "archives" : false
                            onClicked: if (root.bridge) root.bridge.filterType = "archives"
                        }

                        FilterCheckbox {
                            label: root.tr("filter_audio", "Audio")
                            iconText: "🎵"
                            tooltip: root.tr("filter_audio_tip", "Download audio formats (MP3, FLAC, WAV, M4A, OGG)")
                            checked: root.bridge ? root.bridge.filterType === "audio" : false
                            onClicked: if (root.bridge) root.bridge.filterType = "audio"
                        }

                        FilterCheckbox {
                            label: root.tr("filter_links_only", "Links Only")
                            iconText: "🔗"
                            tooltip: root.tr("filter_links_only_tip", "Scan post descriptions & comments for external cloud links (Mega.nz, Google Drive, Dropbox, Pixeldrain, etc.) — no media files are downloaded. Use 'Export Links' in Queue tab to save results.")
                            checked: root.bridge ? root.bridge.filterType === "links" : false
                            onClicked: if (root.bridge) root.bridge.filterType = "links"
                        }
                    }

                    // Divider
                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: "#1E293B"
                    }

                    // Exact File Extensions Section
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        // Header with Title, Hint, and Clear Button
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                text: root.tr("label_exact_extensions", "Exact File Extensions")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.bold: true
                                color: "#E2E8F0"
                            }

                            Text {
                                text: root.tr("hint_exact_extensions", "Only download files matching selected or entered extensions (e.g. .zip, .png, .psd)")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#64748B"
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }

                            // Clear Extensions Button with Newtonian fluid hover
                            Text {
                                visible: root.bridge && root.bridge.exactExtensions.length > 0
                                text: root.tr("btn_clear_extensions", "Clear All ✕")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.bold: true
                                color: extClearMouse0.containsMouse ? "#F87171" : "#94A3B8"
                                scale: extClearMouse0.pressed ? 0.92 : (extClearMouse0.containsMouse ? 1.06 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.65; epsilon: 0.005 } }
                                Behavior on color { ColorAnimation { duration: 140 } }

                                MouseArea {
                                    id: extClearMouse0
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (root.bridge) {
                                            root.bridge.clearExactExtensions()
                                        }
                                    }
                                }
                            }
                        }

                        // ── 1. ACTIVE EXTENSIONS DISPLAY BANNER ──
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: activeContentCol0.implicitHeight + 16
                            radius: 8
                            color: (root.bridge && root.bridge.activeExtensionsList.length > 0) ? "#0B1120" : "#0F172A"
                            border.color: (root.bridge && root.bridge.activeExtensionsList.length > 0) ? "#3B82F6" : "#1E293B"
                            border.width: 1

                            Behavior on color { ColorAnimation { duration: 180 } }
                            Behavior on border.color { ColorAnimation { duration: 180 } }

                            ColumnLayout {
                                id: activeContentCol0
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Rectangle {
                                        implicitWidth: 8
                                        implicitHeight: 8
                                        radius: 4
                                        color: (root.bridge && root.bridge.activeExtensionsList.length > 0) ? "#38BDF8" : "#10B981"
                                    }

                                    Text {
                                        text: (root.bridge && root.bridge.activeExtensionsList.length > 0)
                                            ? (root.tr("label_active_extensions", "Active Extensions:") + " (" + root.bridge.activeExtensionsList.length + ")")
                                            : root.tr("msg_all_extensions_allowed", "All file extensions allowed (no filter active)")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.bold: (root.bridge && root.bridge.activeExtensionsList.length > 0)
                                        color: (root.bridge && root.bridge.activeExtensionsList.length > 0) ? "#93C5FD" : "#64748B"
                                        Layout.fillWidth: true
                                    }
                                }

                                // Interactive Active Chips
                                Flow {
                                    visible: root.bridge && root.bridge.activeExtensionsList.length > 0
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Repeater {
                                        model: root.bridge ? root.bridge.activeExtensionsList : []

                                        Item {
                                            id: activeChipItem0
                                            required property string modelData
                                            implicitHeight: 26
                                            implicitWidth: activeChipRow0.implicitWidth + 14

                                            scale: activeChipMouse0.pressed ? 0.92 : (activeChipMouse0.containsMouse ? 1.05 : 1.0)
                                            Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.35; mass: 0.7; epsilon: 0.005 } }

                                            Rectangle {
                                                anchors.fill: parent
                                                radius: 6
                                                color: activeChipMouse0.containsMouse ? "#1E293B" : "#172033"
                                                border.color: activeChipMouse0.containsMouse ? "#F87171" : "#60A5FA"
                                                border.width: 1

                                                Behavior on color { ColorAnimation { duration: 120 } }
                                                Behavior on border.color { ColorAnimation { duration: 120 } }

                                                RowLayout {
                                                    id: activeChipRow0
                                                    anchors.centerIn: parent
                                                    spacing: 5

                                                    Text {
                                                        text: activeChipItem0.modelData
                                                        font.family: "Segoe UI, sans-serif"
                                                        font.pixelSize: 11
                                                        font.bold: true
                                                        color: "#E0F2FE"
                                                    }

                                                    Text {
                                                        text: "✕"
                                                        font.pixelSize: 10
                                                        font.bold: true
                                                        color: activeChipMouse0.containsMouse ? "#F87171" : "#93C5FD"
                                                    }
                                                }

                                                MouseArea {
                                                    id: activeChipMouse0
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: {
                                                        if (root.bridge) root.bridge.toggleExactExtension(activeChipItem0.modelData)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ── 2. QUICK-PICK STANDARD EXTENSIONS FLOW ──
                        Flow {
                            width: parent.width
                            Layout.fillWidth: true
                            spacing: 6

                            // Archive types
                            FilterCheckbox {
                                label: ".zip"
                                activeColor: "#F59E0B"
                                tooltip: "Only download ZIP archives (.zip)"
                                checked: root.isExtActive(".zip")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".zip")
                            }
                            FilterCheckbox {
                                label: ".rar"
                                activeColor: "#F59E0B"
                                tooltip: "Only download RAR archives (.rar)"
                                checked: root.isExtActive(".rar")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".rar")
                            }
                            FilterCheckbox {
                                label: ".7z"
                                activeColor: "#F59E0B"
                                tooltip: "Only download 7-Zip archives (.7z)"
                                checked: root.isExtActive(".7z")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".7z")
                            }

                            // Image / Art types
                            FilterCheckbox {
                                label: ".png"
                                activeColor: "#38BDF8"
                                tooltip: "Only download PNG lossless images (.png)"
                                checked: root.isExtActive(".png")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".png")
                            }
                            FilterCheckbox {
                                label: ".jpg"
                                activeColor: "#38BDF8"
                                tooltip: "Only download JPG / JPEG images (.jpg, .jpeg)"
                                checked: root.isExtActive(".jpg")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".jpg")
                            }
                            FilterCheckbox {
                                label: ".gif"
                                activeColor: "#38BDF8"
                                tooltip: "Only download animated GIF images (.gif)"
                                checked: root.isExtActive(".gif")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".gif")
                            }
                            FilterCheckbox {
                                label: ".webp"
                                activeColor: "#38BDF8"
                                tooltip: "Only download WebP images (.webp)"
                                checked: root.isExtActive(".webp")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".webp")
                            }
                            FilterCheckbox {
                                label: ".psd"
                                activeColor: "#EC4899"
                                tooltip: "Only download Photoshop PSD project files (.psd)"
                                checked: root.isExtActive(".psd")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".psd")
                            }
                            FilterCheckbox {
                                label: ".clip"
                                activeColor: "#EC4899"
                                tooltip: "Only download Clip Studio Paint CLIP files (.clip)"
                                checked: root.isExtActive(".clip")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".clip")
                            }

                            // Video types
                            FilterCheckbox {
                                label: ".mp4"
                                activeColor: "#818CF8"
                                tooltip: "Only download MP4 videos (.mp4)"
                                checked: root.isExtActive(".mp4")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".mp4")
                            }
                            FilterCheckbox {
                                label: ".mkv"
                                activeColor: "#818CF8"
                                tooltip: "Only download Matroska MKV videos (.mkv)"
                                checked: root.isExtActive(".mkv")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".mkv")
                            }
                            FilterCheckbox {
                                label: ".webm"
                                activeColor: "#818CF8"
                                tooltip: "Only download WebM videos (.webm)"
                                checked: root.isExtActive(".webm")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".webm")
                            }

                            // Audio types
                            FilterCheckbox {
                                label: ".mp3"
                                activeColor: "#10B981"
                                tooltip: "Only download MP3 audio (.mp3)"
                                checked: root.isExtActive(".mp3")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".mp3")
                            }
                            FilterCheckbox {
                                label: ".flac"
                                activeColor: "#10B981"
                                tooltip: "Only download FLAC lossless audio (.flac)"
                                checked: root.isExtActive(".flac")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".flac")
                            }

                            // Document types
                            FilterCheckbox {
                                label: ".pdf"
                                activeColor: "#F87171"
                                tooltip: "Only download PDF documents (.pdf)"
                                checked: root.isExtActive(".pdf")
                                onClicked: if (root.bridge) root.bridge.toggleExactExtension(".pdf")
                            }
                        }

                        // ── 3. SAVED CUSTOM EXTENSIONS SECTION ──
                        ColumnLayout {
                            visible: root.bridge && root.bridge.savedCustomExtensions.length > 0
                            Layout.fillWidth: true
                            spacing: 4

                            Text {
                                text: root.tr("label_saved_custom_extensions", "Custom Extensions:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.bold: true
                                color: "#A5B4FC"
                            }

                            Flow {
                                Layout.fillWidth: true
                                spacing: 6

                                Repeater {
                                    model: root.bridge ? root.bridge.savedCustomExtensions : []

                                    Item {
                                        id: savedPillRoot0
                                        required property string modelData
                                        readonly property bool isChecked: root.isExtActive(modelData)
                                        implicitHeight: 28
                                        implicitWidth: savedPillRow0.implicitWidth + 14

                                        scale: savedPillMouse0.pressed ? 0.93 : (savedPillMouse0.containsMouse ? 1.04 : 1.0)
                                        Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.01 } }

                                        Rectangle {
                                            anchors.fill: parent
                                            radius: 6
                                            color: savedPillRoot0.isChecked ? "#312E81" : (savedPillMouse0.containsMouse ? "#222733" : "#181B24")
                                            border.color: savedPillRoot0.isChecked ? "#818CF8" : (savedPillMouse0.containsMouse ? "#475569" : "#2E3544")
                                            border.width: savedPillRoot0.isChecked ? 1.5 : 1
                                            Behavior on color { ColorAnimation { duration: 160 } }
                                            Behavior on border.color { ColorAnimation { duration: 160 } }

                                            RowLayout {
                                                id: savedPillRow0
                                                anchors.centerIn: parent
                                                spacing: 6

                                                Text {
                                                    text: "✨"
                                                    font.pixelSize: 10
                                                }

                                                Text {
                                                    text: savedPillRoot0.modelData
                                                    font.family: "Segoe UI, Inter, sans-serif"
                                                    font.pixelSize: 11
                                                    font.weight: savedPillRoot0.isChecked ? Font.Bold : Font.Medium
                                                    color: savedPillRoot0.isChecked ? "#EEF2FF" : "#94A3B8"
                                                }

                                                // Remove from saved (✕)
                                                Rectangle {
                                                    implicitWidth: 16
                                                    implicitHeight: 16
                                                    radius: 8
                                                    color: removeSavedMouse0.containsMouse ? "#EF4444" : "transparent"
                                                    Behavior on color { ColorAnimation { duration: 120 } }

                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "✕"
                                                        font.pixelSize: 9
                                                        color: removeSavedMouse0.containsMouse ? "#FFFFFF" : "#64748B"
                                                    }

                                                    MouseArea {
                                                        id: removeSavedMouse0
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: {
                                                            if (root.bridge) {
                                                                root.bridge.removeSavedCustomExtension(savedPillRoot0.modelData)
                                                            }
                                                        }
                                                    }
                                                }
                                            }

                                            MouseArea {
                                                id: savedPillMouse0
                                                anchors.fill: parent
                                                anchors.rightMargin: 20
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    if (root.bridge) {
                                                        root.bridge.toggleExactExtension(savedPillRoot0.modelData)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ── 4. ADD / SAVE CUSTOM EXTENSION INPUT ROW ──
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            StyledTextField {
                                id: exactExtInputTab0
                                Layout.fillWidth: true
                                placeholderText: root.tr("ph_save_custom_ext", "Add custom extension (e.g. .blend, .fbx, .cbr)")
                                tooltip: root.tr("hint_exact_extensions", "Only download files matching selected or entered extensions (e.g. .zip, .png, .psd)")
                                onAccepted: {
                                    if (text.trim().length > 0 && root.bridge) {
                                        root.bridge.addSavedCustomExtension(text.trim())
                                        text = ""
                                    }
                                }
                            }

                            StyledButton {
                                text: root.tr("btn_save_extension", "+ Save")
                                variant: "primary"
                                tooltip: "Save extension to your permanent custom extensions and activate it"
                                onClicked: {
                                    if (exactExtInputTab0.text.trim().length > 0 && root.bridge) {
                                        root.bridge.addSavedCustomExtension(exactExtInputTab0.text.trim())
                                        exactExtInputTab0.text = ""
                                    }
                                }
                            }

                            // Active Filter badge indicator with Newtonian fluid pop
                            Rectangle {
                                visible: root.bridge && root.bridge.activeExtensionsList.length > 0
                                implicitHeight: 34
                                implicitWidth: activeExtLabel0.implicitWidth + 20
                                radius: 8
                                color: "#1E1B4B"
                                border.color: "#6366F1"
                                border.width: 1

                                scale: visible ? 1.0 : 0.8
                                opacity: visible ? 1.0 : 0.0
                                Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.7; epsilon: 0.005 } }
                                Behavior on opacity { NumberAnimation { duration: 180 } }

                                RowLayout {
                                    anchors.centerIn: parent
                                    spacing: 4

                                    Text {
                                        id: activeExtLabel0
                                        text: (root.bridge ? root.bridge.activeExtensionsList.length : 0) + " " + root.tr("badge_exact_extensions", "Active")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.bold: true
                                        color: "#A5B4FC"
                                    }
                                }
                            }
                        }
                    }

                    // Key Format Modifiers
                    Flow {
                        width: parent.width
                        Layout.fillWidth: true
                        spacing: 12

                        FilterCheckbox {
                            label: root.tr("opt_favorite_mode", "Favorite Mode")
                            iconText: "⭐"
                            activeColor: "#FBBF24"
                            tooltip: root.tr("opt_favorite_mode_tip", "Download posts in your Kemono / Coomer account favorites (or filter creator posts to favorites only)")
                            checked: root.bridge ? root.bridge.favoriteMode : false
                            onClicked: {
                                if (root.bridge) {
                                    root.bridge.favoriteMode = !root.bridge.favoriteMode
                                    if (root.bridge.favoriteMode) {
                                        root.bridge.checkFavoriteModeAuth()
                                    }
                                }
                            }
                        }

                        StyledCheckBox {
                            text: root.tr("opt_skip_archives", "Skip Archives")
                            tooltip: root.tr("opt_skip_archives_tip", "Skip all archive files (.zip, .rar, .7z) regardless of active category")
                            checked: root.bridge ? root.bridge.skipArchives : false
                            onCheckedChanged: if (root.bridge) root.bridge.skipArchives = checked
                        }

                        Row {
                            spacing: 8

                            StyledCheckBox {
                                id: webpCheck
                                text: root.tr("opt_compress_webp", "Compress to WebP")
                                tooltip: root.tr("opt_compress_webp_tip", "Convert downloaded PNG and JPG images to compressed WebP format")
                                checked: root.bridge ? root.bridge.compressWebp : false
                                onCheckedChanged: if (root.bridge) root.bridge.compressWebp = checked
                            }

                            // How strongly (only while compressing)
                            StyledComboBox {
                                visible: webpCheck.checked
                                implicitHeight: 26
                                implicitWidth: 120
                                anchors.verticalCenter: webpCheck.verticalCenter
                                model: [
                                        { text: root.tr("webp_q_lossless", "Lossless"), value: "lossless" },
                                        { text: root.tr("webp_q_high", "High"), value: "high" },
                                        { text: root.tr("webp_q_balanced", "Balanced"), value: "balanced" },
                                        { text: root.tr("webp_q_small", "Small"), value: "small" },
                                        { text: root.tr("webp_q_smallest", "Smallest"), value: "smallest" }
                                    ]
                                value: root.bridge ? root.bridge.webpQuality : "balanced"
                                tooltip: root.tr("webp_quality_tip", "How strongly pictures are compressed. Lossless keeps every pixel; Balanced is barely visible and much smaller; Small and Smallest save the most space. A picture is kept as it was if the WebP wouldn't be smaller.")
                                onValuePicked: function(v) { if (root.bridge) root.bridge.webpQuality = v }
                            }
                        }
                    }
                }
            }

            // Card 0.2: Quality & Thumbnails
            CardSection {
                Layout.fillWidth: true
                title: root.tr("card_quality_thumbnails", "Download Quality & Thumbnails")
                iconText: "💎"
                entranceOffsetY: root.tabEntranceOffsetY * 1.25
                entranceOpacity: root.tabEntranceOpacity

                Flow {
                    width: parent.width
                    Layout.fillWidth: true
                    spacing: 14

                    StyledCheckBox {
                        text: root.tr("opt_thumbnails_only", "Download thumbnails only")
                        tooltip: root.tr("opt_thumbnails_only_tip", "Download lightweight preview thumbnails instead of full original files")
                        checked: root.bridge ? root.bridge.downloadThumbnailsOnly : false
                        onCheckedChanged: if (root.bridge) root.bridge.downloadThumbnailsOnly = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_fallback_to_thumbnails", "Fallback to thumbnails if full-size missing")
                        tooltip: root.tr("opt_fallback_to_thumbnails_tip", "If the original full-resolution file is missing on the server (404), allow downloading the preview thumbnail instead")
                        checked: root.bridge ? root.bridge.fallbackToThumbnails : false
                        onCheckedChanged: if (root.bridge) root.bridge.fallbackToThumbnails = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_redownload_small_files", "Re-download small / thumbnail files")
                        tooltip: root.tr("opt_redownload_small_files_tip", "Re-download existing files that appear to be low-quality thumbnails to upgrade them to full resolution")
                        checked: root.bridge ? root.bridge.redownloadSmallFiles : false
                        onCheckedChanged: if (root.bridge) root.bridge.redownloadSmallFiles = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_skip_post_covers", "Skip Post Cover Images")
                        tooltip: root.tr("opt_skip_post_covers_tip", "Do not download the post's featured cover/thumbnail image when attachments or content are present")
                        checked: root.bridge ? root.bridge.skipPostCovers : false
                        onCheckedChanged: if (root.bridge) root.bridge.skipPostCovers = checked
                    }
                }
            }

            // Card 0.3: Post Content & Media Extraction
            CardSection {
                Layout.fillWidth: true
                title: root.tr("card_content_extraction", "Content Scanning & Embedded Media")
                iconText: "🔍"
                entranceOffsetY: root.tabEntranceOffsetY * 1.5
                entranceOpacity: root.tabEntranceOpacity

                Flow {
                    width: parent.width
                    Layout.fillWidth: true
                    spacing: 14

                    StyledCheckBox {
                        text: root.tr("opt_scan_content_images", "Scan content for images")
                        tooltip: root.tr("opt_scan_content_images_tip", "Scan HTML post descriptions for embedded inline artwork")
                        checked: root.bridge ? root.bridge.scanContentImages : true
                        onCheckedChanged: if (root.bridge) root.bridge.scanContentImages = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_download_embeds", "Download Embedded Media (yt-dlp)")
                        tooltip: root.tr("opt_download_embeds_tip", "Download embedded video players (Vimeo, YouTube, Streamable, RedGifs, etc.) via standalone yt-dlp")
                        checked: root.bridge ? root.bridge.downloadEmbeds : true
                        onCheckedChanged: if (root.bridge) root.bridge.downloadEmbeds = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_tag_audio_files", "Tag Audio Metadata (Artist/Title)")
                        tooltip: root.tr("opt_tag_audio_files_tip", "Embed creator name into Artist tag and post title into Title tag for MP3, FLAC, M4A, and audio files")
                        checked: root.bridge ? root.bridge.writeAudioMetadata : false
                        onCheckedChanged: if (root.bridge) root.bridge.writeAudioMetadata = checked
                    }
                }
            }
        }

        // ====================================================================
        // SUB-TAB 1: FILTERS & DATES (Character, Keywords, Dates, File Sizes)
        // ====================================================================
        ColumnLayout {
            id: subTab1Content
            visible: root.currentSubTab === 1
            Layout.fillWidth: true
            spacing: 12

            // Card 1.1: Character & Keyword Rules
            CardSection {
                Layout.fillWidth: true
                title: root.tr("section_filters", "Filters & Keyword Rules")
                iconText: "🎯"
                entranceOffsetY: root.tabEntranceOffsetY
                entranceOpacity: root.tabEntranceOpacity

                ColumnLayout {
                    width: parent.width
                    spacing: 10

                    // Filter by Characters
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 4
                            Text {
                                text: root.tr("label_filter_characters", "Filter by Character(s) (comma-separated):")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                            StyledTextField {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                placeholderText: root.tr("placeholder_characters", "e.g., Tifa, Aerith, (Cloud, Zack)")
                                text: root.bridge ? root.bridge.filterCharacters : ""
                                onTextChanged: {
                                    if (root.bridge && root.bridge.filterCharacters !== text) {
                                        root.bridge.filterCharacters = text
                                    }
                                }
                            }
                        }

                        // Scope selector
                        ColumnLayout {
                            spacing: 4
                            Text {
                                text: root.tr("label_scope", "Scope:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                            StyledButton {
                                implicitWidth: Math.max(100, root.widestLabel([
                                    root.tr("scope_filter_title", "Filter: Title"),
                                    root.tr("scope_filter_content", "Filter: Content"),
                                    root.tr("scope_filter_both", "Filter: Both")]) + 24)
                                text: {
                                    if (!root.bridge) return root.tr("scope_filter_title", "Filter: Title")
                                    var s = root.bridge.characterScope
                                    if (s === "content") return root.tr("scope_filter_content", "Filter: Content")
                                    if (s === "both") return root.tr("scope_filter_both", "Filter: Both")
                                    return root.tr("scope_filter_title", "Filter: Title")
                                }
                                variant: "outline"
                                tooltip: root.tr("tooltip_scope_character", "Switch character filtering scope (Title, Content, or Both)")
                                onClicked: {
                                    if (!root.bridge) return
                                    if (root.bridge.characterScope === "title") root.bridge.characterScope = "content"
                                    else if (root.bridge.characterScope === "content") root.bridge.characterScope = "both"
                                    else root.bridge.characterScope = "title"
                                }
                            }
                        }
                    }

                    // Skip words & Remove words grid
                    GridLayout {
                        columns: root.width > 540 ? 2 : 1
                        Layout.fillWidth: true
                        rowSpacing: 10
                        columnSpacing: 12

                        // Skip words
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 4

                            Text {
                                text: root.tr("label_skip_words", "🚫 Skip with words (comma-separated):")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6

                                StyledTextField {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    placeholderText: root.tr("placeholder_skip_words", "e.g., WIP, preview, [1GB-2GB]")
                                    tooltip: root.tr("tooltip_skip_words_size", "Skip specific words or filter by file size! Use [1GB-2GB], [>=1GB], [<500MB], or [1024-2048] (in MB)")
                                    text: root.bridge ? root.bridge.skipWords : ""
                                    onTextChanged: {
                                        if (root.bridge && root.bridge.skipWords !== text) {
                                            root.bridge.skipWords = text
                                        }
                                    }
                                }

                                StyledButton {
                                    implicitWidth: Math.max(100, root.widestLabel([
                                        root.tr("scope_skip_posts", "Scope: Posts"),
                                        root.tr("scope_skip_files", "Scope: Files")]) + 24)
                                    text: {
                                        if (!root.bridge) return root.tr("scope_skip_posts", "Scope: Posts")
                                        return (root.bridge.skipScope === "files")
                                            ? root.tr("scope_skip_files", "Scope: Files")
                                            : root.tr("scope_skip_posts", "Scope: Posts")
                                    }
                                    variant: "outline"
                                    tooltip: root.tr("tooltip_skip_scope", "Switch skip filter scope between Post Titles and Filenames")
                                    onClicked: {
                                        if (!root.bridge) return
                                        root.bridge.skipScope = (root.bridge.skipScope === "posts") ? "files" : "posts"
                                    }
                                }
                            }
                        }

                        // Remove words
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 4

                            Text {
                                text: root.tr("label_remove_words", "✂️ Remove words from name:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }

                            StyledTextField {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                placeholderText: root.tr("placeholder_remove_words", "e.g., patreon, HD, [sample]")
                                text: root.bridge ? root.bridge.removeWords : ""
                                onTextChanged: {
                                    if (root.bridge && root.bridge.removeWords !== text) {
                                        root.bridge.removeWords = text
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Card 1.2: Post Publication Date Range
            CardSection {
                Layout.fillWidth: true
                title: root.tr("card_date_filtering", "Post Publication Date Range")
                iconText: "📅"
                entranceOffsetY: root.tabEntranceOffsetY * 1.25
                entranceOpacity: root.tabEntranceOpacity

                ColumnLayout {
                    width: parent.width
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: root.tr("hint_date_formats", "Accepts full dates (2024-06-15), year & month (2024-06), or year only (2024)")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#64748B"
                            Layout.fillWidth: true
                        }

                        // Clear dates with fluid spring hover
                        Text {
                            visible: (root.bridge && ((root.bridge.dateAfter && root.bridge.dateAfter.length > 0) || (root.bridge.dateBefore && root.bridge.dateBefore.length > 0)))
                            text: root.tr("btn_clear_dates", "Clear Range ✕")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.bold: true
                            color: dateClearMouse.containsMouse ? "#F87171" : "#94A3B8"
                            scale: dateClearMouse.pressed ? 0.92 : (dateClearMouse.containsMouse ? 1.06 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.65; epsilon: 0.005 } }
                            Behavior on color { ColorAnimation { duration: 140 } }

                            MouseArea {
                                id: dateClearMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (root.bridge) {
                                        root.bridge.dateAfter = ""
                                        root.bridge.dateBefore = ""
                                    }
                                }
                            }
                        }
                    }

                    GridLayout {
                        columns: root.width > 540 ? 2 : 1
                        Layout.fillWidth: true
                        rowSpacing: 6
                        columnSpacing: 12

                        // Date After (From)
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 8

                            Text {
                                text: root.tr("label_date_from", "From:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#64748B"
                            }

                            StyledTextField {
                                id: dateAfterInput
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                placeholderText: root.tr("ph_date_from", "e.g. 2024, 2024-06, 2024-06-15")
                                tooltip: root.tr("tip_date_from", "Earliest date to include. Supports a full year (e.g. 2024 starts Jan 1), month (2024-06 starts 1st), or exact day.")
                                text: root.bridge ? root.bridge.dateAfter : ""
                                onTextChanged: {
                                    if (root.bridge && root.bridge.dateAfter !== text) {
                                        root.bridge.dateAfter = text
                                    }
                                }
                            }
                        }

                        // Date Before (To)
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 8

                            Text {
                                text: root.tr("label_date_to", "To:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#64748B"
                            }

                            StyledTextField {
                                id: dateBeforeInput
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                placeholderText: root.tr("ph_date_to", "e.g. 2024, 2024-12, 2024-12-31")
                                tooltip: root.tr("tip_date_to", "Latest date to include. Supports a full year (e.g. 2024 ends Dec 31), month (2024-06 ends June 30), or exact day.")
                                text: root.bridge ? root.bridge.dateBefore : ""
                                onTextChanged: {
                                    if (root.bridge && root.bridge.dateBefore !== text) {
                                        root.bridge.dateBefore = text
                                    }
                                }
                            }
                        }
                    }

                    // Live interpreted range badge with fluid spring pop-in
                    Rectangle {
                        id: dateRangeBadge
                        property string afterText: root.bridge ? (root.bridge.dateAfter || "").trim() : ""
                        property string beforeText: root.bridge ? (root.bridge.dateBefore || "").trim() : ""
                        visible: afterText.length > 0 || beforeText.length > 0
                        Layout.fillWidth: true
                        implicitHeight: 24
                        radius: 5
                        color: "#0F172A"
                        border.color: "#1E293B"
                        border.width: 1

                        scale: visible ? 1.0 : 0.8
                        Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.8; epsilon: 0.01 } }

                        function describeRange() {
                            if (afterText.length > 0 && beforeText.length > 0) {
                                if (afterText === beforeText) {
                                    if (afterText.length === 4) return "Entire year " + afterText + " (Jan 1, " + afterText + " - Dec 31, " + afterText + ")"
                                    if (afterText.length === 7) return "Entire month of " + afterText
                                }
                                return "Filtering posts: " + afterText + "  →  " + beforeText
                            } else if (afterText.length > 0) {
                                if (afterText.length === 4) return "Filtering posts from " + afterText + " onwards (Jan 1, " + afterText + " +)"
                                if (afterText.length === 7) return "Filtering posts from " + afterText + " onwards"
                                return "Filtering posts from " + afterText + " onwards"
                            } else if (beforeText.length > 0) {
                                if (beforeText.length === 4) return "Filtering posts up through end of " + beforeText + " (Dec 31, " + beforeText + ")"
                                if (beforeText.length === 7) return "Filtering posts up through end of " + beforeText
                                return "Filtering posts up to " + beforeText
                            }
                            return ""
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 6

                            Text {
                                text: "🗓️"
                                font.pixelSize: 10
                            }
                            Text {
                                text: dateRangeBadge.describeRange()
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#38BDF8"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                    }

                    // Auto-scan pages checkbox
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        visible: root.bridge ? ((root.bridge.dateAfter && root.bridge.dateAfter.length > 0) || (root.bridge.dateBefore && root.bridge.dateBefore.length > 0)) : false

                        StyledCheckBox {
                            id: dateAutoScanCheck
                            text: root.tr("opt_date_auto_scan", "Auto-scan all pages for this range")
                            tooltip: root.tr("opt_date_auto_scan_tip", "Automatically scan past the Page End limit to find all posts within the selected date range. Uncheck to strictly respect your Page Start / End settings.")
                            checked: root.bridge ? root.bridge.dateAutoScanPages : true
                            onCheckedChanged: if (root.bridge) root.bridge.dateAutoScanPages = checked
                        }
                    }
                }
            }

            // Card 1.3: File Size Range Limits
            CardSection {
                Layout.fillWidth: true
                title: root.tr("card_size_filtering", "File Size Range Limits")
                iconText: "📦"
                entranceOffsetY: root.tabEntranceOffsetY * 1.5
                entranceOpacity: root.tabEntranceOpacity

                ColumnLayout {
                    width: parent.width
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: root.tr("hint_size_formats", "Only download files within a size window (e.g. 500MB, 1GB, 2.5GB). Leave blank for any size.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#64748B"
                            Layout.fillWidth: true
                        }

                        // Clear size range with fluid spring hover
                        Text {
                            visible: (root.bridge && ((root.bridge.minFileSize && root.bridge.minFileSize.length > 0) || (root.bridge.maxFileSize && root.bridge.maxFileSize.length > 0)))
                            text: root.tr("btn_clear_size_range", "Clear Range ✕")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.bold: true
                            color: sizeClearMouse.containsMouse ? "#F87171" : "#94A3B8"
                            scale: sizeClearMouse.pressed ? 0.92 : (sizeClearMouse.containsMouse ? 1.06 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.65; epsilon: 0.005 } }
                            Behavior on color { ColorAnimation { duration: 140 } }

                            MouseArea {
                                id: sizeClearMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (root.bridge) {
                                        root.bridge.minFileSize = ""
                                        root.bridge.maxFileSize = ""
                                    }
                                }
                            }
                        }
                    }

                    GridLayout {
                        columns: root.width > 540 ? 2 : 1
                        Layout.fillWidth: true
                        rowSpacing: 6
                        columnSpacing: 12

                        // Min File Size
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 8

                            Text {
                                text: root.tr("label_size_min", "Min:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#64748B"
                            }

                            StyledTextField {
                                id: minFileSizeInput
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                placeholderText: root.tr("ph_size_min", "e.g. 1GB or 500MB")
                                tooltip: root.tr("tip_size_min", "Minimum file size. Files smaller than this will be skipped before downloading.")
                                text: root.bridge ? root.bridge.minFileSize : ""
                                validator: RegularExpressionValidator {
                                    regularExpression: /^\s*(\d+(\.\d*)?|\.\d+)?\s*([KMGTP]B?|B)?\s*$/i
                                }
                                onTextChanged: {
                                    if (root.bridge && root.bridge.minFileSize !== text) {
                                        root.bridge.minFileSize = text
                                    }
                                }
                                onEditingFinished: {
                                    var norm = root.normalizeSizeInput(text)
                                    if (text !== norm) text = norm
                                    if (root.bridge && root.bridge.minFileSize !== norm) root.bridge.minFileSize = norm
                                }
                            }
                        }

                        // Max File Size
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 8

                            Text {
                                text: root.tr("label_size_max", "Max:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#64748B"
                            }

                            StyledTextField {
                                id: maxFileSizeInput
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                placeholderText: root.tr("ph_size_max", "e.g. 2GB or 2048MB")
                                tooltip: root.tr("tip_size_max", "Maximum file size. Files larger than this will be skipped before downloading.")
                                text: root.bridge ? root.bridge.maxFileSize : ""
                                validator: RegularExpressionValidator {
                                    regularExpression: /^\s*(\d+(\.\d*)?|\.\d+)?\s*([KMGTP]B?|B)?\s*$/i
                                }
                                onTextChanged: {
                                    if (root.bridge && root.bridge.maxFileSize !== text) {
                                        root.bridge.maxFileSize = text
                                    }
                                }
                                onEditingFinished: {
                                    var norm = root.normalizeSizeInput(text)
                                    if (text !== norm) text = norm
                                    if (root.bridge && root.bridge.maxFileSize !== norm) root.bridge.maxFileSize = norm
                                }
                            }
                        }
                    }

                    // Live interpreted range badge with fluid spring pop-in
                    Rectangle {
                        id: sizeRangeBadge
                        property string minText: root.bridge ? (root.bridge.minFileSize || "").trim() : ""
                        property string maxText: root.bridge ? (root.bridge.maxFileSize || "").trim() : ""
                        readonly property bool isMinInvalid: minText.length > 0 && root.parseBytes(minText) === 0
                        readonly property bool isMaxInvalid: maxText.length > 0 && root.parseBytes(maxText) === 0
                        readonly property bool hasInvalid: isMinInvalid || isMaxInvalid
                        readonly property bool isInverted: {
                            if (hasInvalid || !minText || !maxText) return false
                            var minB = root.parseBytes(minText)
                            var maxB = root.parseBytes(maxText)
                            return minB > 0 && maxB > 0 && minB > maxB
                        }
                        visible: minText.length > 0 || maxText.length > 0
                        Layout.fillWidth: true
                        implicitHeight: 24
                        radius: 5
                        color: (hasInvalid || isInverted) ? "#221C11" : "#0F172A"
                        border.color: (hasInvalid || isInverted) ? "#F59E0B" : "#1E293B"
                        border.width: 1

                        scale: visible ? 1.0 : 0.8
                        Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.8; epsilon: 0.01 } }

                        function describeSizeRange() {
                            if (hasInvalid) {
                                var invalidVal = isMinInvalid ? minText : maxText
                                return root.tr("notice_invalid_size", "⚠️ Invalid size format: \"") + invalidVal + root.tr("notice_invalid_size_hint", "\" — use e.g. 500MB, 1.5GB")
                            }
                            var normMin = root.normalizeSizeInput(minText)
                            var normMax = root.normalizeSizeInput(maxText)
                            if (minText.length > 0 && maxText.length > 0) {
                                if (isInverted) {
                                    return root.tr("notice_inverted_size", "⚠️ Min exceeds Max — auto-correcting to: ") + normMax + " to " + normMin
                                }
                                return root.tr("notice_range_size", "Filtering files between ") + normMin + " and " + normMax
                            } else if (minText.length > 0) {
                                return root.tr("notice_min_size", "Filtering files at least ") + normMin + root.tr("notice_min_size_end", " (skipping smaller files)")
                            } else if (maxText.length > 0) {
                                return root.tr("notice_max_size", "Filtering files up to ") + normMax + root.tr("notice_max_size_end", " (skipping larger files)")
                            }
                            return ""
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 6

                            Text {
                                text: (sizeRangeBadge.hasInvalid || sizeRangeBadge.isInverted) ? "⚠️" : "📦"
                                font.pixelSize: 10
                            }
                            Text {
                                text: sizeRangeBadge.describeSizeRange()
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: (sizeRangeBadge.hasInvalid || sizeRangeBadge.isInverted) ? "#FCD34D" : "#38BDF8"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
        }

        // ====================================================================
        // SUB-TAB 2: STRUCTURE & ENGINE (Folders, Concurrency, Delay, Automation)
        // ====================================================================
        ColumnLayout {
            id: subTab2Content
            visible: root.currentSubTab === 2
            Layout.fillWidth: true
            spacing: 12

            // Card 2.1: Folder Organization & Naming
            CardSection {
                Layout.fillWidth: true
                title: root.tr("card_folder_structure", "Folder Organization & Naming")
                iconText: "📁"
                entranceOffsetY: root.tabEntranceOffsetY
                entranceOpacity: root.tabEntranceOpacity

                Flow {
                    width: parent.width
                    Layout.fillWidth: true
                    spacing: 14

                    StyledCheckBox {
                        text: root.tr("opt_subfolder_per_post", "Subfolder per post")
                        tooltip: root.tr("opt_subfolder_per_post_tip", "Organize downloads into subfolders named after each post")
                        checked: root.bridge ? root.bridge.subfolderPerPost : true
                        onCheckedChanged: if (root.bridge) root.bridge.subfolderPerPost = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_site_in_folder_name", "Site in Folder Name")
                        tooltip: root.tr("opt_site_in_folder_name_tip", "Name creator folders \"Artist [onlyfans]\". Turn off for just \"Artist\". Folders made either way are still found.")
                        checked: root.bridge ? root.bridge.siteInFolderName : true
                        onCheckedChanged: if (root.bridge) root.bridge.siteInFolderName = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_date_prefix", "Date Prefix")
                        tooltip: root.tr("opt_date_prefix_tip", "Prefix subfolder names with the post publication date [YYYY-MM-DD]")
                        checked: root.bridge ? root.bridge.datePrefix : true
                        onCheckedChanged: if (root.bridge) root.bridge.datePrefix = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_file_index_prefix", "Index Prefix (001_...)")
                        tooltip: root.tr("opt_file_index_prefix_tip", "Prefix downloaded filenames with sequential index numbers (001_, 002_, ...) so they can be browsed in order without relying on time sorting")
                        checked: root.bridge ? root.bridge.fileIndexPrefix : false
                        onCheckedChanged: if (root.bridge) root.bridge.fileIndexPrefix = checked
                    }

                    // Which file of a post is #1 (index prefix, numbered names, download order)
                    Row {
                        spacing: 8
                        height: 28

                        Text {
                            text: root.tr("opt_file_order", "File order in posts:")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 12
                            color: fileOrderCombo.value !== "posted" ? "#F1F5F9" : "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        StyledComboBox {
                            id: fileOrderCombo
                            implicitHeight: 28
                            implicitWidth: 150
                            anchors.verticalCenter: parent.verticalCenter
                            model: [
                                { text: root.tr("file_order_posted", "As posted"), value: "posted" },
                                { text: root.tr("file_order_reversed", "Reversed"), value: "reversed" },
                                { text: root.tr("file_order_name", "By file name"), value: "name" }
                            ]
                            value: root.bridge ? root.bridge.fileOrder : "posted"
                            tooltip: root.tr("opt_file_order_tip", "Which file of a post comes first: it is downloaded first and gets #1 with the index prefix and numbered file names.\n\nAs posted: the order the site shows.\nReversed: for creators who upload the newest version first.\nBy file name: sorted by name with numbers counted properly (2 before 10), in any language.")
                            onValuePicked: function(v) { if (root.bridge) root.bridge.fileOrder = v }
                        }
                    }

                    // Same switch as in the Quick tab (they stay in sync), with its quality level
                    Row {
                        spacing: 8
                        height: 28

                        StyledCheckBox {
                            id: webpCheckEngine
                            text: root.tr("opt_compress_webp", "Compress to WebP")
                            tooltip: root.tr("opt_compress_webp_tip", "Convert downloaded PNG and JPG images to compressed WebP format")
                            checked: root.bridge ? root.bridge.compressWebp : false
                            onCheckedChanged: if (root.bridge) root.bridge.compressWebp = checked
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        StyledComboBox {
                            visible: webpCheckEngine.checked
                            implicitHeight: 28
                            implicitWidth: 120
                            anchors.verticalCenter: parent.verticalCenter
                            model: [
                                { text: root.tr("webp_q_lossless", "Lossless"), value: "lossless" },
                                { text: root.tr("webp_q_high", "High"), value: "high" },
                                { text: root.tr("webp_q_balanced", "Balanced"), value: "balanced" },
                                { text: root.tr("webp_q_small", "Small"), value: "small" },
                                { text: root.tr("webp_q_smallest", "Smallest"), value: "smallest" }
                            ]
                            value: root.bridge ? root.bridge.webpQuality : "balanced"
                            tooltip: root.tr("webp_quality_tip", "How strongly pictures are compressed. Lossless keeps every pixel; Balanced is barely visible and much smaller; Small and Smallest save the most space. A picture is kept as it was if the WebP wouldn't be smaller.")
                            onValuePicked: function(v) { if (root.bridge) root.bridge.webpQuality = v }
                        }
                    }

                    Row {
                        spacing: 8

                        StyledCheckBox {
                            id: groupTypeCheck
                            text: root.tr("opt_group_file_type", "Group by File Type")
                            tooltip: root.tr("opt_group_file_type_tip", "Organize attachments into /Images, /Video, /Archive, /Audio, /Other folders")
                            checked: root.bridge ? (root.bridge.groupFileType !== "none") : false
                            onCheckedChanged: {
                                if (root.bridge) {
                                    root.bridge.groupFileType = checked ? (root.bridge.groupFileType !== "none" ? root.bridge.groupFileType : "post") : "none"
                                }
                            }
                        }

                        Rectangle {
                            id: groupScopePill
                            visible: groupTypeCheck.checked
                            y: Math.round((groupTypeCheck.height - height) / 2)
                            implicitHeight: 22
                            implicitWidth: groupScopeRow.implicitWidth + 14
                            radius: 11
                            color: groupScopeMouse.containsMouse ? "#2A364E" : "#1B2232"
                            border.color: groupScopeMouse.containsMouse ? "#38BDF8" : "#334155"
                            border.width: 1

                            scale: groupScopeMouse.pressed ? 0.94 : (groupScopeMouse.containsMouse ? 1.04 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.8; epsilon: 0.005 } }

                            RowLayout {
                                id: groupScopeRow
                                anchors.centerIn: parent
                                spacing: 4

                                Text {
                                    text: root.bridge && root.bridge.groupFileType === "creator" ? "📁" : "📂"
                                    font.pixelSize: 10
                                }

                                Text {
                                    text: root.bridge && root.bridge.groupFileType === "creator"
                                          ? root.tr("opt_group_scope_creator", "Creator Root")
                                          : root.tr("opt_group_scope_post", "Inside Post")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: Font.Medium
                                    color: "#38BDF8"
                                }
                            }

                            MouseArea {
                                id: groupScopeMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (root.bridge) {
                                        root.bridge.groupFileType = (root.bridge.groupFileType === "creator" ? "post" : "creator")
                                    }
                                }
                            }

                            ToolTip {
                                visible: groupScopeMouse.containsMouse
                                delay: 400
                                timeout: 5000
                                text: root.bridge && root.bridge.groupFileType === "creator"
                                      ? root.tr("tip_group_scope_creator", "Files grouped by type at creator level: Creator/Images/Post/... (click to switch)")
                                      : root.tr("tip_group_scope_post", "Files grouped inside post folders: Creator/Post/Images/... (click to switch)")
                            }
                        }
                    }

                    Row {
                        spacing: 6
                        StyledCheckBox {
                            id: tagFolderCheck
                            text: root.tr("opt_tag_folder_mode", "Sort by Tag Folder")
                            tooltip: root.tr("opt_tag_folder_mode_tip", "(Pawchive & cum.st only) Groups downloaded files into subfolders named after the post's primary tag")
                            checked: root.bridge ? root.bridge.tagFolderMode : false
                            onCheckedChanged: if (root.bridge) root.bridge.tagFolderMode = checked
                        }

                        Rectangle {
                            readonly property string curUrl: root.bridge ? (root.bridge.currentUrl || "").toLowerCase() : ""
                            readonly property bool isNonTagDomain: curUrl.length > 0 && curUrl.indexOf("pawchive.pw") === -1 && curUrl.indexOf("cum.st") === -1
                            visible: isNonTagDomain
                            y: Math.round((tagFolderCheck.height - height) / 2)
                            implicitHeight: 20
                            implicitWidth: tagWarnText.implicitWidth + 10
                            radius: 4
                            color: "#1E1B18"
                            border.color: "#854D0E"
                            border.width: 1

                            Text {
                                id: tagWarnText
                                anchors.centerIn: parent
                                text: "⚠ Pawchive/cum.st only"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#FBBF24"
                            }
                        }
                    }

                    StyledCheckBox {
                        text: root.tr("opt_separate_known", "Separate folders by Known.txt")
                        tooltip: root.tr("opt_separate_known_tip", "Sort files into subfolders corresponding to matched characters/series from Known.txt")
                        checked: root.bridge ? root.bridge.separateFoldersByKnown : false
                        onCheckedChanged: if (root.bridge) root.bridge.separateFoldersByKnown = checked
                        onToggled: {
                            if (checked) {
                                var isAiOn = root.bridge && root.bridge.aiRecognitionEnabled && (root.bridge.aiFastSemanticReady || root.bridge.aiDeepReasonerReady)
                                if (!isAiOn && typeof appWindow !== "undefined" && typeof appWindow.showToast === "function") {
                                    appWindow.showToast(
                                        "💡 " + root.tr("toast_known_ai_hint", "Tip: Enable offline AI in Settings → AI to deduce obscure & misspelled characters! (Click to open)"),
                                        function() {
                                            if (typeof appWindow.openSettingsTab === "function") {
                                                appWindow.openSettingsTab(3)
                                            }
                                        }
                                    )
                                } else if (isAiOn && typeof appWindow !== "undefined" && typeof appWindow.showToast === "function") {
                                    appWindow.showToast("✨ " + root.tr("toast_known_ai_active", "Folder separation active with Offline AI engine"))
                                }
                            }
                        }
                    }

                    StyledCheckBox {
                        text: root.tr("opt_manga_mode", "Manga Mode (Oldest First)")
                        tooltip: root.tr("opt_manga_mode_tip", "Sort posts chronologically (oldest first) so chapters and pages download in reading order")
                        checked: root.bridge ? root.bridge.mangaMode : false
                        onCheckedChanged: if (root.bridge) root.bridge.mangaMode = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_download_revisions", "Download Revisions")
                        tooltip: root.tr("opt_download_revisions_tip", "Download older superseded revisions of edited posts")
                        checked: root.bridge ? root.bridge.downloadRevisions : false
                        onCheckedChanged: if (root.bridge) root.bridge.downloadRevisions = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_keep_duplicates", "Keep Duplicates")
                        tooltip: root.tr("opt_keep_duplicates_tip", "Re-download files even if identical files already exist in destination")
                        checked: root.bridge ? root.bridge.keepDuplicates : false
                        onCheckedChanged: if (root.bridge) root.bridge.keepDuplicates = checked
                    }
                }
            }

            // Card 2.2: Concurrency & Performance Engine
            CardSection {
                Layout.fillWidth: true
                title: root.tr("card_concurrency_engine", "Concurrency & Threading Engine")
                iconText: "⚡"
                entranceOffsetY: root.tabEntranceOffsetY * 1.25
                entranceOpacity: root.tabEntranceOpacity

                ColumnLayout {
                    width: parent.width
                    spacing: 12

                    // Worker threads row
                    Flow {
                        width: parent.width
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: root.tr("label_concurrent_workers", "Concurrent Workers:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#94A3B8"
                            height: 32
                            verticalAlignment: Text.AlignVCenter
                        }

                        RowLayout {
                            height: 32
                            spacing: 8
                            opacity: (root.bridge && root.bridge.isTelegramUrl) ? 0.45 : ((root.bridge && root.bridge.adaptiveThreading) ? 0.38 : 1.0)
                            Behavior on opacity { NumberAnimation { duration: 180 } }

                            Slider {
                                id: threadSlider
                                from: 1
                                to: root.bridge ? root.bridge.maxCpuThreads : 24
                                stepSize: 1
                                value: (root.bridge && root.bridge.isTelegramUrl) ? 2 : (root.bridge ? root.bridge.threadsCount : 4)
                                implicitWidth: root.width > 540 ? 160 : 110
                                implicitHeight: 32
                                enabled: (root.bridge && root.bridge.isTelegramUrl) ? false : (root.bridge ? !root.bridge.adaptiveThreading : true)
                                onMoved: if (root.bridge && enabled) root.bridge.threadsCount = Math.round(value)

                                background: Item {
                                    x: threadSlider.leftPadding
                                    y: threadSlider.topPadding + threadSlider.availableHeight / 2 - height / 2
                                    width: threadSlider.availableWidth
                                    implicitHeight: 6
                                    height: 6

                                    Rectangle {
                                        width: parent.width; height: parent.height
                                        radius: 3
                                        color: "#101827"
                                        border.color: "#1E2D42"
                                        border.width: 1
                                    }
                                    Rectangle {
                                        width: Math.max(6, threadSlider.visualPosition * parent.width)
                                        height: parent.height
                                        radius: 3
                                        color: "#38BDF8"
                                        opacity: threadSlider.enabled ? 1.0 : 0.35
                                    }
                                }

                                handle: Item {
                                    x: threadSlider.leftPadding + threadSlider.visualPosition * (threadSlider.availableWidth - width)
                                    y: threadSlider.topPadding + threadSlider.availableHeight / 2 - height / 2
                                    width: 28; height: 28

                                    scale: threadSlider.pressed ? 1.25 : (threadSlider.hovered ? 1.12 : 1.0)
                                    Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.30; mass: 0.6; epsilon: 0.005 } }

                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 28; height: 28; radius: 14
                                        color: "transparent"
                                        border.color: "#38BDF8"
                                        border.width: 1
                                        opacity: (threadSlider.pressed || threadSlider.hovered) ? 0.5 : 0.0
                                        Behavior on opacity { NumberAnimation { duration: 160 } }
                                    }
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 16; height: 16; radius: 8
                                        color: "#38BDF8"
                                        opacity: threadSlider.enabled ? 1.0 : 0.3
                                    }
                                }
                            }

                            // Value chip with spring hover
                            Rectangle {
                                implicitWidth: workerVal.implicitWidth + 18
                                height: 24; radius: 12
                                color: "#0C1828"
                                border.color: (root.bridge && root.bridge.isTelegramUrl) ? "#92400E"
                                              : ((root.bridge && root.bridge.threadsLocked) ? "#7F1D1D" : "#164E63")
                                border.width: 1

                                scale: workerChipMouse.containsMouse ? 1.08 : 1.0
                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.65; epsilon: 0.005 } }

                                Text {
                                    id: workerVal
                                    anchors.centerIn: parent
                                    text: (root.bridge && root.bridge.isTelegramUrl) ? "2"
                                          : (root.bridge && root.bridge.adaptiveThreading
                                             ? root.bridge.threadsCount.toString()
                                             : Math.round(threadSlider.value).toString())
                                    font.family: "Segoe UI, sans-serif"
                                    font.bold: true
                                    font.pixelSize: 11
                                    color: (root.bridge && root.bridge.isTelegramUrl) ? "#FCD34D"
                                           : ((root.bridge && root.bridge.threadsLocked) ? "#FCA5A5" : "#7DD3FA")
                                }

                                MouseArea {
                                    id: workerChipMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                }
                            }
                        }

                        RowLayout {
                            height: 32
                            spacing: 8

                            // Thread Lock Button with Newtonian Fluid squash-stretch and buoyant hover
                            Rectangle {
                                id: lockBtn
                                height: 24
                                radius: 5
                                opacity: (root.bridge && root.bridge.isTelegramUrl) ? 0.35 : 1.0
                                Behavior on opacity { NumberAnimation { duration: 180 } }
                                implicitWidth: lockRow.implicitWidth + 16
                                color: (root.bridge && root.bridge.threadsLocked)
                                       ? (lockMouse.containsMouse ? "#3A1A1C" : "#2D1517")
                                       : (lockMouse.containsMouse ? "#1E293B" : "#161E2E")
                                border.color: (root.bridge && root.bridge.threadsLocked)
                                              ? (lockMouse.containsMouse ? "#F87171" : "#EF4444")
                                              : (lockMouse.containsMouse ? "#475569" : "#242A38")
                                border.width: 1

                                scale: lockMouse.pressed ? 0.94 : (lockMouse.containsMouse ? 1.04 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.32; mass: 0.8; epsilon: 0.005 } }

                                transform: Translate {
                                    y: lockMouse.containsMouse ? -1.5 : 0
                                    Behavior on y { SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.1 } }
                                }

                                RowLayout {
                                    id: lockRow
                                    anchors.centerIn: parent
                                    spacing: 4

                                    Text {
                                        text: (root.bridge && root.bridge.threadsLocked) ? "🔒" : "🔓"
                                        font.pixelSize: 11
                                    }

                                    Text {
                                        text: (root.bridge && root.bridge.threadsLocked)
                                              ? root.tr("btn_thread_locked", "Locked")
                                              : root.tr("btn_thread_lock", "Lock")
                                        font.family: "Segoe UI, sans-serif"
                                        font.bold: true
                                        font.pixelSize: 11
                                        color: (root.bridge && root.bridge.threadsLocked) ? "#F87171" : "#94A3B8"
                                    }
                                }

                                MouseArea {
                                    id: lockMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: (root.bridge && root.bridge.isTelegramUrl) ? Qt.ArrowCursor : Qt.PointingHandCursor
                                    onClicked: {
                                        if (root.bridge && !(root.bridge.isTelegramUrl)) {
                                            root.bridge.threadsLocked = !root.bridge.threadsLocked
                                        }
                                    }
                                }

                                ToolTip {
                                    id: lockToolTip
                                    visible: lockMouse.containsMouse
                                    delay: 400
                                    timeout: 5000
                                    text: (root.bridge && root.bridge.isTelegramUrl)
                                          ? root.tr("tip_thread_tg_locked", "Telegram Lock: Concurrency is locked to 2 threads to prevent FloodWait bans and connection drops.")
                                          : ((root.bridge && root.bridge.threadsLocked)
                                             ? (root.tr("tip_thread_locked_active", "Thread Lock Active: Worker concurrency is locked. Adaptive scaling is disabled and HTTP 429 cooldown is 30s."))
                                             : (root.tr("tip_thread_lock", "Lock Thread Sweetspot: Lock current concurrency. Disables adaptive scaling and prevents rate limits from altering your thread count.")))
                                    contentItem: Text {
                                        text: lockToolTip.text
                                        font.family: "Segoe UI, Inter, sans-serif"
                                        font.pixelSize: 11
                                        color: "#F1F5F9"
                                        wrapMode: Text.WordWrap
                                    }
                                    background: Rectangle {
                                        color: "#141924"
                                        border.color: (root.bridge && root.bridge.threadsLocked) ? "#EF4444" : "#38BDF8"
                                        border.width: 1
                                        radius: 6
                                    }
                                }
                            }

                            // Adaptive Threading Toggle Button with Newtonian Fluid squash-stretch and buoyant hover
                            Rectangle {
                                id: adaptiveBtn
                                height: 24
                                radius: 5
                                readonly property bool isTg: root.bridge && root.bridge.isTelegramUrl
                                readonly property bool isLocked: root.bridge && root.bridge.threadsLocked
                                readonly property bool isAdaptive: !isTg && !isLocked && (root.bridge && root.bridge.adaptiveThreading)
                                readonly property bool canToggle: !isTg && !isLocked

                                opacity: canToggle ? 1.0 : 0.38
                                Behavior on opacity { NumberAnimation { duration: 180 } }

                                implicitWidth: adaptiveRow.implicitWidth + 16
                                color: isAdaptive
                                       ? (adaptiveMouse.containsMouse ? "#3A2908" : "#2A1D05")
                                       : (adaptiveMouse.containsMouse ? "#1E293B" : "#161E2E")
                                border.color: isAdaptive
                                              ? (adaptiveMouse.containsMouse ? "#FCD34D" : "#F59E0B")
                                              : (adaptiveMouse.containsMouse ? "#475569" : "#242A38")
                                border.width: 1

                                scale: (canToggle && adaptiveMouse.pressed) ? 0.94 : ((canToggle && adaptiveMouse.containsMouse) ? 1.04 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.32; mass: 0.8; epsilon: 0.005 } }

                                transform: Translate {
                                    y: (adaptiveBtn.canToggle && adaptiveMouse.containsMouse) ? -1.5 : 0
                                    Behavior on y { SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.1 } }
                                }

                                RowLayout {
                                    id: adaptiveRow
                                    anchors.centerIn: parent
                                    spacing: 5

                                    Text {
                                        text: "⚡"
                                        font.pixelSize: 11
                                        scale: adaptiveBtn.isAdaptive ? 1.15 : 1.0
                                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7; epsilon: 0.01 } }
                                    }

                                    Text {
                                        text: root.tr("opt_adaptive_threading", "Adaptive Threading")
                                        font.family: "Segoe UI, sans-serif"
                                        font.bold: true
                                        font.pixelSize: 11
                                        color: adaptiveBtn.isAdaptive ? "#FCD34D" : "#94A3B8"
                                    }
                                }

                                MouseArea {
                                    id: adaptiveMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: adaptiveBtn.canToggle ? Qt.PointingHandCursor : Qt.ArrowCursor
                                    onClicked: {
                                        if (root.bridge && adaptiveBtn.canToggle) {
                                            root.bridge.adaptiveThreading = !root.bridge.adaptiveThreading
                                        }
                                    }
                                }

                                ToolTip {
                                    id: adaptiveToolTip
                                    visible: adaptiveMouse.containsMouse
                                    delay: 400
                                    timeout: 5000
                                    text: adaptiveBtn.isTg
                                          ? root.tr("opt_adaptive_telegram_tip", "Adaptive Threading is disabled for Telegram downloads (locked strictly to 2 threads to prevent account bans)")
                                          : (adaptiveBtn.isLocked
                                             ? root.tr("opt_adaptive_disabled_tip", "Adaptive Threading is disabled because Thread Lock is active")
                                             : root.tr("opt_adaptive_threading_tip", "Automatically scale worker thread count based on network conditions and 429 rate limits"))
                                    contentItem: Text {
                                        text: adaptiveToolTip.text
                                        font.family: "Segoe UI, Inter, sans-serif"
                                        font.pixelSize: 11
                                        color: "#F1F5F9"
                                        wrapMode: Text.WordWrap
                                    }
                                    background: Rectangle {
                                        color: "#141924"
                                        border.color: adaptiveBtn.isAdaptive ? "#F59E0B" : "#38BDF8"
                                        border.width: 1
                                        radius: 6
                                    }
                                }
                            }

                            // Telegram thread lock reason badge
                            Rectangle {
                                id: tgLockBadge
                                visible: root.bridge && root.bridge.isTelegramUrl
                                height: 24; radius: 5
                                implicitWidth: tgLockRow.implicitWidth + 14
                                color: "#2E1A11"; border.color: "#F59E0B"; border.width: 1

                                scale: tgLockMouse.pressed ? 0.95 : (tgLockMouse.containsMouse ? 1.03 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.32; mass: 1.8 } }

                                transform: Translate {
                                    y: tgLockMouse.containsMouse ? -2 : 0
                                    Behavior on y { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.8 } }
                                }

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: -3
                                    radius: 8
                                    color: "transparent"
                                    border.color: "#F59E0B"
                                    border.width: 1
                                    opacity: 0.25

                                    SequentialAnimation on opacity {
                                        loops: Animation.Infinite
                                        running: tgLockBadge.visible
                                        NumberAnimation { to: 0.75; duration: 1500; easing.type: Easing.InOutSine }
                                        NumberAnimation { to: 0.15; duration: 1500; easing.type: Easing.InOutSine }
                                    }
                                }

                                RowLayout {
                                    id: tgLockRow
                                    anchors.centerIn: parent; spacing: 5
                                    Text { text: "🔒"; font.pixelSize: 10 }
                                    Text {
                                        text: root.tr("tg_threads_locked_reason", "Telegram: Locked to 2 threads (anti-ban)")
                                        font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.bold: true; color: "#FCD34D"
                                    }
                                }

                                MouseArea {
                                    id: tgLockMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                }

                                ToolTip {
                                    id: tgLockTooltip
                                    visible: tgLockMouse.containsMouse
                                    delay: 200
                                    timeout: 8000
                                    text: root.tr("tg_threads_locked_tooltip", "Telegram limits simultaneous connections per account. Concurrency is locked to 2 worker threads to prevent FloodWait temporary bans and connection drops.")
                                    contentItem: Text {
                                        text: tgLockTooltip.text
                                        font.family: "Segoe UI, Inter, sans-serif"
                                        font.pixelSize: 11
                                        color: "#F1F5F9"
                                        wrapMode: Text.WordWrap
                                    }
                                    background: Rectangle {
                                        color: "#141924"
                                        border.color: "#F59E0B"
                                        border.width: 1
                                        radius: 6
                                    }
                                }
                            }

                            // CPU detection chip
                            Rectangle {
                                height: 22
                                radius: 4
                                color: "#161E2E"
                                border.color: "#1E293B"
                                border.width: 1
                                implicitWidth: cpuBadgeText.implicitWidth + 12

                                Text {
                                    id: cpuBadgeText
                                    anchors.centerIn: parent
                                    text: (root.bridge && root.bridge.threadsLocked)
                                          ? ("🔒 " + root.tr("badge_locked", "Locked:") + " " + root.bridge.threadsCount + "T")
                                          : (root.bridge && root.bridge.adaptiveThreading
                                             ? root.tr("badge_adaptive", "⚡ Adaptive")
                                             : (root.bridge ? (root.tr("badge_cpu_cores", "⚡ CPU Cores:") + " " + root.bridge.maxCpuThreads) : root.tr("badge_cpu_auto", "⚡ CPU Auto")))
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: (root.bridge && root.bridge.threadsLocked)
                                           ? "#F87171"
                                           : (root.bridge && root.bridge.adaptiveThreading ? "#FBBF24" : "#38BDF8")
                                }
                            }
                        }
                    }

                    // Thread Delay After Download
                    Flow {
                        width: parent.width
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: root.tr("label_thread_delay", "⏱️ Thread Delay After Download:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#94A3B8"
                            height: 32
                            verticalAlignment: Text.AlignVCenter
                        }

                        RowLayout {
                            height: 32
                            spacing: 8

                            Slider {
                                id: delaySlider
                                from: 0.0
                                to: 10.0
                                stepSize: 0.5
                                value: root.bridge ? root.bridge.downloadDelay : 2.0
                                implicitWidth: root.width > 540 ? 160 : 110
                                implicitHeight: 32
                                onMoved: if (root.bridge) root.bridge.downloadDelay = value

                                background: Item {
                                    x: delaySlider.leftPadding
                                    y: delaySlider.topPadding + delaySlider.availableHeight / 2 - height / 2
                                    width: delaySlider.availableWidth
                                    implicitHeight: 6
                                    height: 6

                                    Rectangle {
                                        width: parent.width; height: parent.height
                                        radius: 3
                                        color: "#100D1E"
                                        border.color: "#231A40"
                                        border.width: 1
                                    }
                                    Rectangle {
                                        width: Math.max(6, delaySlider.visualPosition * parent.width)
                                        height: parent.height
                                        radius: 3
                                        color: "#A78BFA"
                                    }
                                }

                                handle: Item {
                                    x: delaySlider.leftPadding + delaySlider.visualPosition * (delaySlider.availableWidth - width)
                                    y: delaySlider.topPadding + delaySlider.availableHeight / 2 - height / 2
                                    width: 28; height: 28

                                    scale: delaySlider.pressed ? 1.25 : (delaySlider.hovered ? 1.12 : 1.0)
                                    Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.30; mass: 0.6; epsilon: 0.005 } }

                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 28; height: 28; radius: 14
                                        color: "transparent"
                                        border.color: "#A78BFA"
                                        border.width: 1
                                        opacity: (delaySlider.pressed || delaySlider.hovered) ? 0.5 : 0.0
                                        Behavior on opacity { NumberAnimation { duration: 160 } }
                                    }
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 16; height: 16; radius: 8
                                        color: "#A78BFA"
                                    }
                                }
                            }

                            // Value chip
                            Rectangle {
                                implicitWidth: delayVal.implicitWidth + 18
                                height: 24; radius: 12
                                color: "#0D0A1E"
                                border.color: "#3B2A6B"
                                border.width: 1

                                scale: delayChipMouse.containsMouse ? 1.08 : 1.0
                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.65; epsilon: 0.005 } }

                                Text {
                                    id: delayVal
                                    anchors.centerIn: parent
                                    text: (root.bridge ? root.bridge.downloadDelay.toFixed(1) : "2.0") + "s"
                                    font.family: "Segoe UI, sans-serif"
                                    font.bold: true
                                    font.pixelSize: 11
                                    color: "#C4B5FD"
                                }

                                MouseArea {
                                    id: delayChipMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                }
                            }
                        }

                        Text {
                            text: root.tr("label_anti_429", "(anti-429 cooldown)")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#64748B"
                            height: 32
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }

            // Card 2.3: Post-Download Automation
            CardSection {
                Layout.fillWidth: true
                title: root.tr("card_post_automation", "Post-Download Automation")
                iconText: "✨"
                entranceOffsetY: root.tabEntranceOffsetY * 1.5
                entranceOpacity: root.tabEntranceOpacity

                Flow {
                    width: parent.width
                    Layout.fillWidth: true
                    spacing: 10

                    // Save post_info.txt toggle
                    Rectangle {
                        id: saveMetaToggle
                        property bool active: root.bridge ? root.bridge.savePostMetadata : true
                        // as wide as its text (long translations used to spill out of the card)
                        implicitWidth: Math.min(parent.width, Math.max(230, metaTexts.implicitWidth + 66))
                        implicitHeight: 36
                        radius: 10
                        color: active ? "#1E1B35" : "#141922"
                        border.color: active ? "#7C3AED" : "#1E2433"
                        border.width: 1

                        scale: metaMouse.pressed ? 0.95 : (metaMouse.containsMouse ? 1.025 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.34; mass: 0.75; epsilon: 0.005 } }

                        transform: Translate {
                            y: metaMouse.containsMouse ? -1.5 : 0
                            Behavior on y { SpringAnimation { spring: 4.5; damping: 0.36; mass: 0.85; epsilon: 0.1 } }
                        }

                        Behavior on color { ColorAnimation { duration: 180 } }
                        Behavior on border.color { ColorAnimation { duration: 180 } }

                        Rectangle {
                            width: 3
                            height: parent.height - 10
                            radius: 2
                            anchors { left: parent.left; leftMargin: 0; verticalCenter: parent.verticalCenter }
                            color: saveMetaToggle.active ? "#7C3AED" : "#2D3748"
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }

                        RowLayout {
                            anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                            spacing: 8

                            Rectangle {
                                id: metaTrack
                                width: 32; height: 18; radius: 9
                                color: saveMetaToggle.active ? "#7C3AED" : "#2D3748"
                                Behavior on color { ColorAnimation { duration: 180 } }

                                Rectangle {
                                    id: metaThumb
                                    width: 12; height: 12; radius: 6
                                    color: "white"
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: saveMetaToggle.active ? parent.width - width - 3 : 3
                                    Behavior on x { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 } }
                                }
                            }

                            ColumnLayout {
                                id: metaTexts
                                spacing: 1
                                Layout.fillWidth: true
                                Text {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    text: root.tr("toggle_save_post_info", "Save post_info.txt")
                                    color: saveMetaToggle.active ? "#E2E8F0" : "#64748B"
                                    font.pixelSize: 12
                                    font.family: "Segoe UI, sans-serif"
                                    font.weight: Font.Medium
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    text: root.tr("toggle_save_post_info_sub", "caption, tags & comments")
                                    color: saveMetaToggle.active ? "#7C3AED" : "#374151"
                                    font.pixelSize: 9
                                    font.family: "Segoe UI, sans-serif"
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                            }
                        }

                        MouseArea {
                            id: metaMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.bridge) root.bridge.savePostMetadata = !saveMetaToggle.active
                            }
                        }

                        Connections {
                            target: root.bridge
                            function onSavePostMetadataChanged() {
                                saveMetaToggle.active = root.bridge.savePostMetadata
                            }
                        }
                    }

                    // Open folder when done toggle
                    Rectangle {
                        id: openFolderToggle
                        property bool active: root.bridge ? root.bridge.openFolderOnComplete : false
                        // as wide as its text (long translations used to spill out of the card)
                        implicitWidth: Math.min(parent.width, Math.max(210, folderTexts.implicitWidth + 66))
                        implicitHeight: 36
                        radius: 10
                        color: active ? "#0D1F1A" : "#141922"
                        border.color: active ? "#10B981" : "#1E2433"
                        border.width: 1

                        scale: folderMouse.pressed ? 0.95 : (folderMouse.containsMouse ? 1.025 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.34; mass: 0.75; epsilon: 0.005 } }

                        transform: Translate {
                            y: folderMouse.containsMouse ? -1.5 : 0
                            Behavior on y { SpringAnimation { spring: 4.5; damping: 0.36; mass: 0.85; epsilon: 0.1 } }
                        }

                        Behavior on color { ColorAnimation { duration: 180 } }
                        Behavior on border.color { ColorAnimation { duration: 180 } }

                        Rectangle {
                            width: 3
                            height: parent.height - 10
                            radius: 2
                            anchors { left: parent.left; leftMargin: 0; verticalCenter: parent.verticalCenter }
                            color: openFolderToggle.active ? "#10B981" : "#2D3748"
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }

                        RowLayout {
                            anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                            spacing: 8

                            Rectangle {
                                id: folderTrack
                                width: 32; height: 18; radius: 9
                                color: openFolderToggle.active ? "#10B981" : "#2D3748"
                                Behavior on color { ColorAnimation { duration: 180 } }

                                Rectangle {
                                    width: 12; height: 12; radius: 6
                                    color: "white"
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: openFolderToggle.active ? parent.width - width - 3 : 3
                                    Behavior on x { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 } }
                                }
                            }

                            ColumnLayout {
                                id: folderTexts
                                spacing: 1
                                Layout.fillWidth: true
                                Text {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    text: root.tr("toggle_open_folder", "Open folder when done")
                                    color: openFolderToggle.active ? "#E2E8F0" : "#64748B"
                                    font.pixelSize: 12
                                    font.family: "Segoe UI, sans-serif"
                                    font.weight: Font.Medium
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    text: root.tr("toggle_open_folder_sub", "auto-opens on completion")
                                    color: openFolderToggle.active ? "#10B981" : "#374151"
                                    font.pixelSize: 9
                                    font.family: "Segoe UI, sans-serif"
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                            }
                        }

                        MouseArea {
                            id: folderMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.bridge) root.bridge.openFolderOnComplete = !openFolderToggle.active
                            }
                        }

                        Connections {
                            target: root.bridge
                            function onOpenFolderOnCompleteChanged() {
                                openFolderToggle.active = root.bridge.openFolderOnComplete
                            }
                        }
                    }

                    // Desktop report toggle
                    Rectangle {
                        id: desktopReportToggle
                        property bool active: root.bridge ? root.bridge.saveDesktopReport : false
                        // as wide as its text (long translations used to spill out of the card)
                        implicitWidth: Math.min(parent.width, Math.max(210, reportTexts.implicitWidth + 66))
                        implicitHeight: 36
                        radius: 10
                        color: active ? "#0C202F" : "#141922"
                        border.color: active ? "#0284C7" : "#1E2433"
                        border.width: 1

                        scale: reportMouse.pressed ? 0.95 : (reportMouse.containsMouse ? 1.025 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.34; mass: 0.75; epsilon: 0.005 } }

                        transform: Translate {
                            y: reportMouse.containsMouse ? -1.5 : 0
                            Behavior on y { SpringAnimation { spring: 4.5; damping: 0.36; mass: 0.85; epsilon: 0.1 } }
                        }

                        Behavior on color { ColorAnimation { duration: 180 } }
                        Behavior on border.color { ColorAnimation { duration: 180 } }

                        Rectangle {
                            width: 3
                            height: parent.height - 10
                            radius: 2
                            anchors { left: parent.left; leftMargin: 0; verticalCenter: parent.verticalCenter }
                            color: desktopReportToggle.active ? "#38BDF8" : "#2D3748"
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }

                        RowLayout {
                            anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                            spacing: 8

                            Rectangle {
                                id: reportTrack
                                width: 32; height: 18; radius: 9
                                color: desktopReportToggle.active ? "#0284C7" : "#2D3748"
                                Behavior on color { ColorAnimation { duration: 180 } }

                                Rectangle {
                                    width: 12; height: 12; radius: 6
                                    color: "white"
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: desktopReportToggle.active ? parent.width - width - 3 : 3
                                    Behavior on x { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 } }
                                }
                            }

                            ColumnLayout {
                                id: reportTexts
                                spacing: 1
                                Layout.fillWidth: true
                                Text {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    text: root.tr("toggle_desktop_report", "Desktop report")
                                    color: desktopReportToggle.active ? "#E2E8F0" : "#64748B"
                                    font.pixelSize: 12
                                    font.family: "Segoe UI, sans-serif"
                                    font.weight: Font.Medium
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    text: root.tr("toggle_desktop_report_sub", "summary log on desktop")
                                    color: desktopReportToggle.active ? "#38BDF8" : "#374151"
                                    font.pixelSize: 9
                                    font.family: "Segoe UI, sans-serif"
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                            }
                        }

                        MouseArea {
                            id: reportMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.bridge) root.bridge.saveDesktopReport = !desktopReportToggle.active
                            }
                        }

                        Connections {
                            target: root.bridge
                            function onSaveDesktopReportChanged() {
                                desktopReportToggle.active = root.bridge.saveDesktopReport
                            }
                        }
                    }
                }
            }
        }

        // ====================================================================
        // SUB-TAB 3: BATCH IMPORTER (Multi-URL Paste & Queue)
        // ====================================================================
        ColumnLayout {
            id: subTab3Content
            visible: root.currentSubTab === 3
            Layout.fillWidth: true
            spacing: 12

            CardSection {
                Layout.fillWidth: true
                title: root.tr("section_batch_queue", "Batch Download Queue")
                iconText: "📋"
                entranceOffsetY: root.tabEntranceOffsetY
                entranceOpacity: root.tabEntranceOpacity

                ColumnLayout {
                    width: parent.width
                    spacing: 12

                    Text {
                        text: root.tr("desc_batch_queue", "Paste multiple creator / album URLs below, one per line. Each URL uses its own folder inside the download destination.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    ScrollView {
                        Layout.fillWidth: true
                        implicitHeight: 140
                        clip: true

                        TextArea {
                            id: batchInput
                            placeholderText: "https://kemono.cr/patreon/user/12345\nhttps://coomer.st/onlyfans/user/67890\nhttps://cum.st/creators/onlyfans/32696630\nhttps://bunkr.cr/a/example"
                            background: Rectangle {
                                color: "#141922"
                                border.color: batchInput.activeFocus ? "#7C3AED" : "#1E2433"
                                border.width: 1
                                radius: 6
                            }
                            color: "#E2E8F0"
                            font.family: "Consolas, monospace"
                            font.pixelSize: 11
                            wrapMode: TextArea.Wrap
                            padding: 10
                        }
                    }

                    RowLayout {
                        spacing: 8

                        StyledButton {
                            text: root.tr("btn_add_all_queue", "Add All to Queue")
                            iconText: "▶"
                            variant: "primary"
                            tooltip: root.tr("btn_add_all_queue_tip", "Parse and start downloading all URLs above")
                            enabled: batchInput.text.trim().length > 0 && root.bridge && !root.bridge.isDownloading
                            onClicked: {
                                if (root.bridge) {
                                    var count = root.bridge.batchLoadUrls(batchInput.text)
                                    if (count > 0) {
                                        batchInput.text = ""
                                    }
                                }
                            }
                        }

                        StyledButton {
                            text: root.tr("btn_clear", "Clear")
                            iconText: "✕"
                            variant: "ghost"
                            onClicked: batchInput.text = ""
                        }

                        // URL detection badge with Newtonian spring pop
                        Rectangle {
                            visible: root.detectedBatchUrlCount > 0
                            implicitHeight: 24
                            implicitWidth: batchCountLabel.implicitWidth + 16
                            radius: 12
                            color: "#064E3B"
                            border.color: "#10B981"
                            border.width: 1

                            scale: visible ? 1.0 : 0.4
                            Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.65; epsilon: 0.005 } }

                            Text {
                                id: batchCountLabel
                                anchors.centerIn: parent
                                text: root.detectedBatchUrlCount + " " + root.tr("label_urls_detected", "URL(s) detected")
                                color: "#A7F3D0"
                                font.pixelSize: 11
                                font.bold: true
                                font.family: "Segoe UI, sans-serif"
                            }
                        }
                    }
                }
            }
        }
    }

    // Modal popup dialog for selecting failed downloads to retry
    RetryModal {
        id: retryModal
        bridge: root.bridge
    }
}
