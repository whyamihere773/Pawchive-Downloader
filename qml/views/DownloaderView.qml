import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "downloader"

SmoothFlickable {
    id: root

    property var bridge: null
    property int currentSubTab: 0
    property bool embeddedInModal: false

    // Fluid Newtonian Entrance parameters triggered on sub-tab switch
    property real tabEntranceOffsetY: 0
    property real tabEntranceOpacity: 1.0
    property real fallbackThumbGlowAlpha: 0.0

    function focusFallbackToThumbnailsSetting() {
        root.currentSubTab = 0
        focusFallbackThumbTimer.restart()
    }

    NumberAnimation {
        id: scrollToFallbackThumbAnim
        target: root
        property: "contentY"
        duration: 340
        easing.type: Easing.OutCubic
    }

    SequentialAnimation {
        id: fallbackThumbGlowAnim
        loops: 1
        NumberAnimation { target: root; property: "fallbackThumbGlowAlpha"; from: 0.0; to: 1.0; duration: 220; easing.type: Easing.OutCubic }
        NumberAnimation { target: root; property: "fallbackThumbGlowAlpha"; from: 1.0; to: 0.32; duration: 360; easing.type: Easing.InOutSine }
        NumberAnimation { target: root; property: "fallbackThumbGlowAlpha"; from: 0.32; to: 1.0; duration: 320; easing.type: Easing.InOutSine }
        NumberAnimation { target: root; property: "fallbackThumbGlowAlpha"; from: 1.0; to: 0.32; duration: 360; easing.type: Easing.InOutSine }
        NumberAnimation { target: root; property: "fallbackThumbGlowAlpha"; from: 0.32; to: 1.0; duration: 320; easing.type: Easing.InOutSine }
        PauseAnimation { duration: 260 }
        NumberAnimation { target: root; property: "fallbackThumbGlowAlpha"; from: 1.0; to: 0.0; duration: 750; easing.type: Easing.OutCubic }
    }

    Timer {
        id: focusFallbackThumbTimer
        interval: 75
        repeat: false
        onTriggered: {
            var target = (typeof subTab0Content !== "undefined" && subTab0Content) ? subTab0Content.fallbackThumbTarget : null
            if (!target)
                return
            var pt = target.mapToItem(root.contentItem, 0, 0)
            var itemTop = pt.y
            var itemBottom = pt.y + target.height
            var maxScroll = Math.max(0, root.contentHeight - root.height)
            if (maxScroll > 0 && (itemTop < root.contentY + 24 || itemBottom > root.contentY + root.height - 24)) {
                var targetY = Math.max(0, Math.min(maxScroll, itemTop - Math.max(24, (root.height - target.height) * 0.42)))
                root.cancelFlick()
                scrollToFallbackThumbAnim.stop()
                scrollToFallbackThumbAnim.from = root.contentY
                scrollToFallbackThumbAnim.to = targetY
                scrollToFallbackThumbAnim.start()
            }
            fallbackThumbGlowAnim.restart()
        }
    }

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
        if (root.bridge.videoDurationFilterEnabled) count++
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
        if (!subTab3Content || !subTab3Content.batchText) return 0
        var lines = subTab3Content.batchText.split("\n")
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

        PendingSettingsBanner {
            suppressed: root.embeddedInModal
            Layout.fillWidth: true
            bridge: root.bridge
        }

        // Live Large-Creator Scan Progress Banner
        Rectangle {
            id: liveScanBanner
            readonly property bool scanningActive: !root.embeddedInModal && Boolean(root.bridge && root.bridge.isScanning)
            readonly property int progCurrent: (root.bridge && root.bridge.scanProgressCurrent !== undefined) ? root.bridge.scanProgressCurrent : 0
            readonly property int progTotal: (root.bridge && root.bridge.scanProgressTotal !== undefined) ? root.bridge.scanProgressTotal : 0
            Layout.fillWidth: true
            Layout.fillHeight: false
            visible: scanningActive
            clip: true
            implicitHeight: scanningActive ? scanBannerCol.implicitHeight + 18 : 0
            Layout.preferredHeight: implicitHeight
            radius: 10
            color: "#111A2B"
            border.color: "#38BDF8"
            border.width: 1

            ColumnLayout {
                id: scanBannerCol
                anchors {
                    left: parent.left
                    right: parent.right
                    verticalCenter: parent.verticalCenter
                    leftMargin: 12
                    rightMargin: 12
                }
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: "🔎"
                        font.pixelSize: 14
                    }

                    Text {
                        Layout.fillWidth: true
                        text: (root.bridge && root.bridge.scanPhaseText && root.bridge.scanPhaseText.length > 0)
                            ? root.bridge.scanPhaseText
                            : root.tr("msg_scanning_creator", "Scanning creator posts...")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 12
                        font.bold: true
                        color: "#E0F2FE"
                        elide: Text.ElideRight
                    }

                    Text {
                        visible: liveScanBanner.progTotal > 0 || liveScanBanner.progCurrent > 0
                        text: liveScanBanner.progTotal > 0
                            ? (liveScanBanner.progCurrent + " / " + liveScanBanner.progTotal)
                            : (liveScanBanner.progCurrent + " fetched")
                        font.family: "Consolas, monospace"
                        font.pixelSize: 11
                        color: "#7DD3FC"
                    }

                    StyledButton {
                        text: root.tr("btn_cancel_scan", "Cancel Scan")
                        variant: "outline"
                        implicitHeight: 28
                        onClicked: if (root.bridge && root.bridge.cancelScan) root.bridge.cancelScan()
                    }
                }

                // Determinate / Indeterminate Slim Progress Track
                Rectangle {
                    id: scanTrack
                    Layout.fillWidth: true
                    height: 5
                    radius: 2.5
                    color: "#0A101C"
                    clip: true

                    Rectangle {
                        id: scanIndetBar
                        visible: liveScanBanner.progTotal <= 0
                        height: parent.height
                        width: parent.width * 0.28
                        radius: 2.5
                        color: "#38BDF8"

                        SequentialAnimation on x {
                            running: liveScanBanner.visible && liveScanBanner.progTotal <= 0
                            loops: Animation.Infinite
                            NumberAnimation { from: -scanTrack.width * 0.28; to: scanTrack.width; duration: 1100; easing.type: Easing.InOutQuad }
                        }
                    }

                    Rectangle {
                        visible: liveScanBanner.progTotal > 0
                        height: parent.height
                        radius: 2.5
                        color: "#38BDF8"
                        width: parent.width * Math.max(0.0, Math.min(1.0, liveScanBanner.progTotal > 0 ? (liveScanBanner.progCurrent / liveScanBanner.progTotal) : 0.0))

                        Behavior on width {
                            NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
                        }
                    }
                }
            }
        }

        // ====================================================================
        // ALWAYS VISIBLE: Download Destination Card
        // ====================================================================
        CardSection {
            visible: !root.embeddedInModal
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
        DownloaderSubTabDock {
            id: subTabDock
            view: root
        }

        DownloaderQuickTab {
            id: subTab0Content
            view: root
        }

        DownloaderFiltersTab {
            id: subTab1Content
            view: root
        }

        DownloaderStructureTab {
            id: subTab2Content
            view: root
        }

        DownloaderBatchTab {
            id: subTab3Content
            view: root
        }
    }
}
