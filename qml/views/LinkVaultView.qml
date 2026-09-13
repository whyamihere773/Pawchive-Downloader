import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: linkVaultRoot
    property var bridge: null

    // ── Helpers ────────────────────────────────────────────────────────────────
    function tr(key, fallback) {
        if (typeof appWindow !== "undefined") return appWindow.tr(key, fallback)
        return fallback !== undefined ? fallback : key
    }

    function showToast(msg) {
        if (statusToast) {
            statusToast.show(msg)
        }
    }

    function serviceColor(svc) {
        var s = (svc || "").toLowerCase()
        if (s === "onlyfans")      return "#00AFF0"
        if (s === "fansly")        return "#FF6B9D"
        if (s === "patreon")       return "#FF424D"
        if (s === "fanbox")        return "#007AFF"
        if (s === "gumroad")       return "#36C5AB"
        if (s === "subscribestar") return "#5C9DFF"
        if (s === "fantia")        return "#E84393"
        if (s === "boosty")        return "#F76A23"
        return "#64748B"
    }

    function platformColor(p) {
        var s = (p || "").toLowerCase()
        if (s === "mega")       return "#D9272E"
        if (s === "gdrive")     return "#34A853"
        if (s === "pixeldrain") return "#F59E0B"
        if (s === "dropbox")    return "#0061FF"
        if (s === "gofile")     return "#2563EB"
        if (s === "catbox")     return "#8B5CF6"
        if (s === "mediafire")  return "#0070FF"
        if (s === "bunkr")      return "#10B981"
        return "#64748B"
    }

    function healthColor(h) {
        var s = (h || "").toLowerCase()
        if (s === "alive") return "#10B981"
        if (s === "dead")  return "#EF4444"
        return "#F59E0B"
    }

    function healthLabel(h) {
        var s = (h || "").toLowerCase()
        if (s === "alive") return linkVaultRoot.tr("vault_health_alive", "Alive")
        if (s === "dead")  return linkVaultRoot.tr("vault_health_dead", "Dead")
        return linkVaultRoot.tr("vault_health_unknown", "Unchecked")
    }

    function cleanHtml(raw) {
        if (!raw) return "(No text content)"
        var t = String(raw)
        // Convert breaks and paragraphs
        t = t.replace(/<br\s*\/?>/gi, "\n")
        t = t.replace(/<\/p\s*>/gi, "\n\n")
        t = t.replace(/<\/div\s*>/gi, "\n")
        t = t.replace(/<li\s*>/gi, "\n• ")
        // Remove remaining HTML tags
        t = t.replace(/<[^>]+>/g, "")
        // Unescape entities
        t = t.replace(/&#x27;/g, "'")
             .replace(/&#39;/g, "'")
             .replace(/&quot;/g, '"')
             .replace(/&amp;/g, '&')
             .replace(/&lt;/g, '<')
             .replace(/&gt;/g, '>')
             .replace(/&nbsp;/g, ' ')
        // Collapse 3+ consecutive newlines to 2
        t = t.replace(/\n{3,}/g, "\n\n")
        return t.trim() || "(No text content)"
    }

    // ── Filter State ───────────────────────────────────────────────────────────
    property string searchQuery: ""
    property string activePlatform: "all"
    property var expandedCreators: ({})
    property var expandedPostTexts: ({})

    function toggleCreator(key) {
        var copy = Object.assign({}, expandedCreators)
        copy[key] = !copy[key]
        expandedCreators = copy
    }

    function togglePostText(pid) {
        var copy = Object.assign({}, expandedPostTexts)
        copy[pid] = !copy[pid]
        expandedPostTexts = copy
    }

    // Parsed tree data from bridge
    readonly property var vaultData: {
        if (!bridge || !bridge.linkVaultTreeJson) return []
        try {
            return JSON.parse(bridge.linkVaultTreeJson)
        } catch (e) {
            return []
        }
    }

    // ── Cascading Newtonian Entrance Animation ─────────────────────────────────
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
            if (entranceStage >= 4) stop()
        }
    }

    Component.onCompleted: triggerEntrance()
    onVisibleChanged: if (visible) triggerEntrance()

    // ── Newtonian Momentum Scrolling State ─────────────────────────────────────
    readonly property bool isScrolling: creatorFlickable.isScrolling

    // ── Bridge Telemetry & Notification Connections ────────────────────────────
    Connections {
        target: linkVaultRoot.bridge
        function onVaultHarvestStarted(creatorName) {
            linkVaultRoot.showToast(linkVaultRoot.tr("toast_harvest_started", "Harvesting links for ") + creatorName + "...")
        }
        function onVaultHarvestFinished(success, creatorName, newLinks, totalPosts) {
            if (success) {
                linkVaultRoot.showToast(linkVaultRoot.tr("toast_harvest_success", "Harvested ") + newLinks + linkVaultRoot.tr("toast_harvest_success_links", " new links from ") + creatorName)
            } else {
                linkVaultRoot.showToast(linkVaultRoot.tr("toast_harvest_failed", "Harvest failed: ") + creatorName)
            }
        }
        function onLinkVaultProbingFinished() {
            linkVaultRoot.showToast(linkVaultRoot.tr("toast_probing_finished", "Link health verification finished."))
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // ── 1. Top Header Banner & Actions (Console Log Aware) ────────────────
        Rectangle {
            id: headerSection
            Layout.fillWidth: true
            implicitHeight: headerCol.implicitHeight + 24
            color: "#141720"
            radius: 10
            border.color: "#1E2430"
            border.width: 1

            opacity: linkVaultRoot.entranceStage >= 1 ? 1.0 : 0.0
            transform: Translate {
                y: linkVaultRoot.entranceStage >= 1 ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 1.0; epsilon: 0.25 }
                }
            }
            Behavior on opacity { NumberAnimation { duration: 180 } }

            ColumnLayout {
                id: headerCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 12
                spacing: 10

                // Title + Subtitle Row (+ Actions on Wide View)
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Rectangle {
                        width: 40; height: 40; radius: 8
                        color: "#0C4A6E"
                        border.color: "#38BDF8"; border.width: 1.2
                        Text { anchors.centerIn: parent; text: "🗝️"; font.pixelSize: 20 }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        RowLayout {
                            spacing: 8
                            Text {
                                text: linkVaultRoot.tr("vault_title", "Permanent Link Vault")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 17
                                font.weight: Font.Bold
                                color: "#F8FAFC"
                            }

                            Rectangle {
                                height: 20
                                implicitWidth: totalPillText.implicitWidth + 14
                                radius: 10
                                color: "#0369A1"
                                border.color: "#38BDF8"
                                border.width: 1
                                Text {
                                    id: totalPillText
                                    anchors.centerIn: parent
                                    text: (linkVaultRoot.bridge ? linkVaultRoot.bridge.linkVaultTotalLinks : 0) + " " + linkVaultRoot.tr("vault_links_pill", "Links")
                                    font.pixelSize: 10
                                    font.weight: Font.DemiBold
                                    color: "#FFFFFF"
                                }
                            }
                        }

                        Text {
                            text: linkVaultRoot.tr("vault_subtitle", "Permanent cloud harvest repository with smart proximity passwords and live health verification.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }

                    // Action Buttons (Wide View: > 780px)
                    RowLayout {
                        visible: linkVaultRoot.width > 780
                        spacing: 8
                        Layout.alignment: Qt.AlignVCenter

                        // Action: Add / Harvest Artist
                        Rectangle {
                            implicitWidth: addArtistRow1.implicitWidth + 20
                            height: 32
                            radius: 6
                            color: addArtistMouse1.containsMouse ? "#047857" : "#065F46"
                            border.color: addArtistMouse1.containsMouse ? "#34D399" : "#10B981"
                            border.width: 1
                            scale: addArtistMouse1.pressed ? 0.92 : (addArtistMouse1.containsMouse ? 1.04 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }

                            Row {
                                id: addArtistRow1
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "➕"; font.pixelSize: 12 }
                                Text {
                                    text: linkVaultRoot.tr("btn_harvest_artist", "Harvest Artist")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: "#FFFFFF"
                                }
                            }

                            MouseArea {
                                id: addArtistMouse1
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 300
                                ToolTip.text: linkVaultRoot.tr("tip_harvest_artist", "Harvest all links & passwords from an artist into the vault without downloading files")
                                onClicked: {
                                    addArtistModal.open()
                                }
                            }
                        }

                        // Action: Probe All Health
                        Rectangle {
                            implicitWidth: probeRow1.implicitWidth + 20
                            height: 32
                            radius: 6
                            color: probeMouse1.containsMouse ? "#0284C7" : "#0369A1"
                            border.color: probeMouse1.containsMouse ? "#7DD3FC" : "#38BDF8"
                            border.width: 1
                            scale: probeMouse1.pressed ? 0.92 : (probeMouse1.containsMouse ? 1.04 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }

                            Row {
                                id: probeRow1
                                anchors.centerIn: parent
                                spacing: 6
                                Text {
                                    text: linkVaultRoot.bridge && linkVaultRoot.bridge.linkVaultProbingActive ? "⏳" : "⚡"
                                    font.pixelSize: 12
                                }
                                Text {
                                    text: linkVaultRoot.bridge && linkVaultRoot.bridge.linkVaultProbingActive ? linkVaultRoot.tr("btn_probing", "Probing...") : linkVaultRoot.tr("btn_probe_all", "Probe Health")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: "#FFFFFF"
                                }
                            }

                            MouseArea {
                                id: probeMouse1
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 300
                                ToolTip.text: linkVaultRoot.tr("tip_probe_health", "Checks link status (Mega, Pixeldrain, GoFile, Catbox) asynchronously in background")
                                onClicked: {
                                    if (linkVaultRoot.bridge) linkVaultRoot.bridge.probeVaultHealth()
                                }
                            }
                        }

                        // Action: Clean Dead Links
                        Rectangle {
                            implicitWidth: cleanRow1.implicitWidth + 20
                            height: 32
                            radius: 6
                            color: cleanMouse1.containsMouse ? "#3B181E" : "#1A202C"
                            border.color: cleanMouse1.containsMouse ? "#F87171" : "#EF4444"
                            border.width: 1
                            scale: cleanMouse1.pressed ? 0.92 : (cleanMouse1.containsMouse ? 1.04 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }

                            Row {
                                id: cleanRow1
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "🧹"; font.pixelSize: 12 }
                                Text {
                                    text: linkVaultRoot.tr("btn_clean_dead", "Clean Dead")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: "#FCA5A5"
                                }
                            }

                            MouseArea {
                                id: cleanMouse1
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 300
                                ToolTip.text: linkVaultRoot.tr("tip_clean_dead", "Removes verified 404 dead links from the vault")
                                onClicked: {
                                    if (linkVaultRoot.bridge) {
                                        var removed = linkVaultRoot.bridge.cleanDeadVaultLinks()
                                        linkVaultRoot.showToast(linkVaultRoot.tr("toast_cleaned_dead", "Cleaned dead links: ") + removed)
                                    }
                                }
                            }
                        }

                        // Action: Copy Passwords to Decompressor
                        Rectangle {
                            implicitWidth: decompressorRow1.implicitWidth + 20
                            height: 32
                            radius: 6
                            color: decompMouse1.containsMouse ? "#1E293B" : "#141720"
                            border.color: decompMouse1.containsMouse ? "#C4B5FD" : "#A78BFA"
                            border.width: 1
                            scale: decompMouse1.pressed ? 0.92 : (decompMouse1.containsMouse ? 1.04 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }

                            Row {
                                id: decompressorRow1
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "📦"; font.pixelSize: 12 }
                                Text {
                                    text: linkVaultRoot.tr("btn_feed_decompressor", "Send Passwords to Decompressor")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: "#C4B5FD"
                                }
                            }

                            MouseArea {
                                id: decompMouse1
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 300
                                ToolTip.text: linkVaultRoot.tr("tip_send_passwords", "Adds all extracted passwords to Bulk Decompressor archive dictionary")
                                onClicked: {
                                    if (linkVaultRoot.bridge) {
                                        var count = linkVaultRoot.bridge.copyPasswordsToDecompressor()
                                        linkVaultRoot.showToast(linkVaultRoot.tr("toast_passwords_copied", "Sent to Decompressor: ") + count + " " + linkVaultRoot.tr("vault_passwords_label", "passwords"))
                                    }
                                }
                            }
                        }
                    }
                }

                // Action Buttons (Narrow View: <= 780px, stacks neatly so never cut off)
                Flow {
                    visible: linkVaultRoot.width <= 780
                    Layout.fillWidth: true
                    spacing: 8

                    // Action: Add / Harvest Artist
                    Rectangle {
                        implicitWidth: addArtistRow2.implicitWidth + 18
                        height: 30
                        radius: 6
                        color: addArtistMouse2.containsMouse ? "#047857" : "#065F46"
                        border.color: addArtistMouse2.containsMouse ? "#34D399" : "#10B981"
                        border.width: 1
                        scale: addArtistMouse2.pressed ? 0.92 : (addArtistMouse2.containsMouse ? 1.04 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                        Row {
                            id: addArtistRow2
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: "➕"; font.pixelSize: 11 }
                            Text {
                                text: linkVaultRoot.tr("btn_harvest_artist", "Harvest Artist")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: 600
                                color: "#FFFFFF"
                            }
                        }

                        MouseArea {
                            id: addArtistMouse2
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                addArtistModal.open()
                            }
                        }
                    }

                    // Action: Probe All Health
                    Rectangle {
                        implicitWidth: probeRow2.implicitWidth + 18
                        height: 30
                        radius: 6
                        color: probeMouse2.containsMouse ? "#0284C7" : "#0369A1"
                        border.color: probeMouse2.containsMouse ? "#7DD3FC" : "#38BDF8"
                        border.width: 1
                        scale: probeMouse2.pressed ? 0.92 : (probeMouse2.containsMouse ? 1.04 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                        Row {
                            id: probeRow2
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                text: linkVaultRoot.bridge && linkVaultRoot.bridge.linkVaultProbingActive ? "⏳" : "⚡"
                                font.pixelSize: 11
                            }
                            Text {
                                text: linkVaultRoot.bridge && linkVaultRoot.bridge.linkVaultProbingActive ? linkVaultRoot.tr("btn_probing", "Probing...") : linkVaultRoot.tr("btn_probe_all", "Probe Health")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: 600
                                color: "#FFFFFF"
                            }
                        }

                        MouseArea {
                            id: probeMouse2
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (linkVaultRoot.bridge) linkVaultRoot.bridge.probeVaultHealth()
                            }
                        }
                    }

                    // Action: Clean Dead Links
                    Rectangle {
                        implicitWidth: cleanRow2.implicitWidth + 18
                        height: 30
                        radius: 6
                        color: cleanMouse2.containsMouse ? "#3B181E" : "#1A202C"
                        border.color: cleanMouse2.containsMouse ? "#F87171" : "#EF4444"
                        border.width: 1
                        scale: cleanMouse2.pressed ? 0.92 : (cleanMouse2.containsMouse ? 1.04 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                        Row {
                            id: cleanRow2
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: "🧹"; font.pixelSize: 11 }
                            Text {
                                text: linkVaultRoot.tr("btn_clean_dead", "Clean Dead")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: 600
                                color: "#FCA5A5"
                            }
                        }

                        MouseArea {
                            id: cleanMouse2
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (linkVaultRoot.bridge) {
                                    var removed = linkVaultRoot.bridge.cleanDeadVaultLinks()
                                    linkVaultRoot.showToast(linkVaultRoot.tr("toast_cleaned_dead", "Cleaned dead links: ") + removed)
                                }
                            }
                        }
                    }

                    // Action: Copy Passwords to Decompressor
                    Rectangle {
                        implicitWidth: decompressorRow2.implicitWidth + 18
                        height: 30
                        radius: 6
                        color: decompMouse2.containsMouse ? "#1E293B" : "#141720"
                        border.color: decompMouse2.containsMouse ? "#C4B5FD" : "#A78BFA"
                        border.width: 1
                        scale: decompMouse2.pressed ? 0.92 : (decompMouse2.containsMouse ? 1.04 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                        Row {
                            id: decompressorRow2
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: "📦"; font.pixelSize: 11 }
                            Text {
                                text: linkVaultRoot.tr("btn_feed_decompressor", "Send Passwords to Decompressor")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: 600
                                color: "#C4B5FD"
                            }
                        }

                        MouseArea {
                            id: decompMouse2
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (linkVaultRoot.bridge) {
                                    var count = linkVaultRoot.bridge.copyPasswordsToDecompressor()
                                    linkVaultRoot.showToast(linkVaultRoot.tr("toast_passwords_copied", "Sent to Decompressor: ") + count + " " + linkVaultRoot.tr("vault_passwords_label", "passwords"))
                                }
                            }
                        }
                    }
                }
            }
        }

        // ── Active Harvest Progress Banner ──────────────────────────────────
        Rectangle {
            id: activeHarvestBanner
            visible: linkVaultRoot.bridge && linkVaultRoot.bridge.linkVaultHarvestingActive
            Layout.fillWidth: true
            implicitHeight: harvestRow.implicitHeight + 16
            color: "#064E3B"
            radius: 8
            border.color: "#10B981"
            border.width: 1

            RowLayout {
                id: harvestRow
                anchors.fill: parent
                anchors.margins: 10
                spacing: 10

                // Animated pulsing dot
                Rectangle {
                    width: 10
                    height: 10
                    radius: 5
                    color: "#34D399"
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: activeHarvestBanner.visible
                        NumberAnimation { from: 1.0; to: 0.3; duration: 600; easing.type: Easing.InOutQuad }
                        NumberAnimation { from: 0.3; to: 1.0; duration: 600; easing.type: Easing.InOutQuad }
                    }
                }

                Text {
                    text: linkVaultRoot.bridge ? linkVaultRoot.bridge.linkVaultHarvestingStatus : ""
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: 600
                    color: "#ECFDF5"
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }

                Rectangle {
                    implicitWidth: cancelHarvestText.implicitWidth + 16
                    height: 26
                    radius: 5
                    color: cancelHarvestMouse.containsMouse ? "#7F1D1D" : "#450A0A"
                    border.color: "#EF4444"
                    border.width: 1
                    scale: cancelHarvestMouse.pressed ? 0.92 : 1.0
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.4 } }

                    Text {
                        id: cancelHarvestText
                        anchors.centerIn: parent
                        text: linkVaultRoot.tr("btn_cancel", "Cancel")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#FCA5A5"
                    }

                    MouseArea {
                        id: cancelHarvestMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (linkVaultRoot.bridge) linkVaultRoot.bridge.cancelVaultHarvest()
                        }
                    }
                }
            }
        }

        // ── 2. Search & Platform Filter Bar (Flow Auto-Wrapping) ───────────────
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            opacity: linkVaultRoot.entranceStage >= 2 ? 1.0 : 0.0
            transform: Translate {
                y: linkVaultRoot.entranceStage >= 2 ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 1.0; epsilon: 0.25 }
                }
            }
            Behavior on opacity { NumberAnimation { duration: 180 } }

            // Search Bar Input
            Rectangle {
                Layout.fillWidth: true
                height: 36
                color: "#141720"
                radius: 8
                border.color: searchInput.activeFocus ? "#38BDF8" : "#1E2430"
                border.width: 1
                Behavior on border.color { ColorAnimation { duration: 140 } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 8

                    Text { text: "🔍"; font.pixelSize: 12; color: "#64748B" }

                    TextInput {
                        id: searchInput
                        Layout.fillWidth: true
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#F8FAFC"
                        selectByMouse: true
                        clip: true

                        Text {
                            text: linkVaultRoot.tr("vault_search_placeholder", "Filter by artist name, post title, cloud URL, or password...")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#475569"
                            visible: !searchInput.text && !searchInput.activeFocus
                        }

                        onTextChanged: {
                            linkVaultRoot.searchQuery = text
                            if (linkVaultRoot.bridge) linkVaultRoot.bridge.refreshLinkVault(linkVaultRoot.searchQuery, linkVaultRoot.activePlatform)
                        }
                    }

                    Text {
                        visible: searchInput.text.length > 0
                        text: "✖"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: searchInput.text = ""
                        }
                    }
                }
            }

            // Platform Filter Chips (Flow allows clean auto-wrapping on narrow width / console open)
            Flow {
                Layout.fillWidth: true
                spacing: 6

                Repeater {
                    model: [
                        { key: "all", label: "All" },
                        { key: "mega", label: "Mega.nz" },
                        { key: "gdrive", label: "Google Drive" },
                        { key: "pixeldrain", label: "Pixeldrain" },
                        { key: "gofile", label: "GoFile" },
                        { key: "dropbox", label: "Dropbox" },
                        { key: "catbox", label: "Catbox" },
                        { key: "other", label: "Other" }
                    ]

                    delegate: Rectangle {
                        id: pillRect
                        height: 28
                        implicitWidth: pillText.implicitWidth + 16
                        radius: 14
                        property bool isSelected: linkVaultRoot.activePlatform === modelData.key
                        color: isSelected ? "#0284C7" : (pillMouse.containsMouse ? "#1E2430" : "#141720")
                        border.color: isSelected ? "#38BDF8" : (pillMouse.containsMouse ? "#334155" : "#1E2430")
                        border.width: 1

                        scale: pillMouse.pressed ? 0.92 : (pillMouse.containsMouse ? 1.05 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 120 } }

                        Text {
                            id: pillText
                            anchors.centerIn: parent
                            text: modelData.label
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: pillRect.isSelected ? Font.Bold : Font.Normal
                            color: pillRect.isSelected ? "#FFFFFF" : "#94A3B8"
                        }

                        MouseArea {
                            id: pillMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                linkVaultRoot.activePlatform = modelData.key
                                if (linkVaultRoot.bridge) linkVaultRoot.bridge.refreshLinkVault(linkVaultRoot.searchQuery, linkVaultRoot.activePlatform)
                            }
                        }
                    }
                }
            }
        }

        // ── 3. Tree View of Creators > Posts > Links ───────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            opacity: linkVaultRoot.entranceStage >= 3 ? 1.0 : 0.0
            transform: Translate {
                y: linkVaultRoot.entranceStage >= 3 ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 1.0; epsilon: 0.25 }
                }
            }
            Behavior on opacity { NumberAnimation { duration: 180 } }

            // Empty State Graphic
            Rectangle {
                anchors.centerIn: parent
                visible: linkVaultRoot.vaultData.length === 0
                width: Math.min(parent.width - 40, 380)
                height: 200
                color: "#141720"
                radius: 10
                border.color: "#1E2430"
                border.width: 1

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 8

                    Text { text: "🔗"; font.pixelSize: 32; Layout.alignment: Qt.AlignHCenter }
                    Text {
                        text: linkVaultRoot.tr("vault_empty_title", "Link Vault is Empty")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                        Layout.alignment: Qt.AlignHCenter
                    }
                    Text {
                        text: linkVaultRoot.tr("vault_empty_desc", "When you scrape creators or posts, all cloud links (Mega, Drive, Pixeldrain, etc.) and passwords are automatically saved here permanently.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                        wrapMode: Text.Wrap
                        horizontalAlignment: Text.AlignHCenter
                        Layout.preferredWidth: Math.min(parent.parent.width - 40, 320)
                    }
                }
            }

            // High-Performance Momentum Scrollable List of Creators (SettingsView scroll tech)
            SmoothFlickable {
                id: creatorFlickable
                anchors.fill: parent
                visible: linkVaultRoot.vaultData.length > 0
                contentWidth: width
                contentHeight: creatorListCol.implicitHeight + 24

                ColumnLayout {
                    id: creatorListCol
                    width: creatorFlickable.width - (creatorFlickable.verticalScrollBar && creatorFlickable.verticalScrollBar.visible ? 10 : 0)
                    spacing: 10

                    Repeater {
                        model: linkVaultRoot.vaultData

                        delegate: Rectangle {
                            id: creatorCard
                            Layout.fillWidth: true
                            implicitHeight: creatorCol.implicitHeight + 20
                    radius: 8
                    color: creatorHover.hovered ? "#181D2A" : "#141720"
                    border.color: isExpanded ? "#38BDF8" : (creatorHover.hovered ? "#334155" : "#1E2430")
                    border.width: 1

                    readonly property var creatorItem: modelData
                    readonly property bool isExpanded: !!linkVaultRoot.expandedCreators[creatorItem.creator_key]

                    transform: Translate {
                        y: creatorHover.hovered && !linkVaultRoot.isScrolling ? -2.5 : 0
                        Behavior on y {
                            SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                        }
                    }
                    Behavior on color { ColorAnimation { duration: 140 } }
                    Behavior on border.color { ColorAnimation { duration: 140 } }

                    HoverHandler { id: creatorHover }

                    ColumnLayout {
                        id: creatorCol
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8

                        // ── Level 1: Creator Header Row ────────────────────────
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Rectangle {
                                id: expandBtn
                                width: 24
                                height: 24
                                radius: 4
                                color: expMouse.containsMouse ? "#334155" : "#1E2430"
                                // Use NumberAnimation instead of SpringAnimation to avoid
                                // restarting the animation from 0 every time the delegate is reused
                                scale: expMouse.pressed ? 0.88 : (expMouse.containsMouse ? 1.1 : 1.0)
                                Behavior on scale {
                                    NumberAnimation { duration: 110; easing.type: Easing.OutBack; easing.overshoot: 1.4 }
                                }
                                Behavior on color { ColorAnimation { duration: 110 } }
                                Text {
                                    anchors.centerIn: parent
                                    text: creatorCard.isExpanded ? "▼" : "▶"
                                    font.pixelSize: 10
                                    color: "#94A3B8"
                                }
                                MouseArea {
                                    id: expMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: linkVaultRoot.toggleCreator(creatorItem.creator_key)
                                }
                            }

                            // Service Badge
                            Rectangle {
                                height: 20
                                implicitWidth: serviceText.implicitWidth + 14
                                radius: 4
                                color: linkVaultRoot.serviceColor(creatorItem.service)
                                Text {
                                    id: serviceText
                                    anchors.left: parent.left
                                    anchors.leftMargin: 7
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: (creatorItem.service || "").toUpperCase()
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: "#FFFFFF"
                                }
                            }

                            // Creator Name
                            Text {
                                text: creatorItem.creator_name || "Unknown"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 13
                                font.weight: Font.Bold
                                color: "#F8FAFC"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            // User ID Pill
                            Text {
                                text: "#" + creatorItem.user_id
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#64748B"
                            }

                            // Post Count Badge
                            Rectangle {
                                height: 20
                                implicitWidth: postCountText.implicitWidth + 16
                                radius: 10
                                color: "#1E293B"
                                border.color: "#334155"
                                border.width: 1
                                Text {
                                    id: postCountText
                                    anchors.left: parent.left
                                    anchors.leftMargin: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: creatorItem.post_count + " " + linkVaultRoot.tr("vault_posts_badge", "Posts")
                                    font.pixelSize: 10
                                    color: "#94A3B8"
                                }
                            }

                            // Link Count Badge
                            Rectangle {
                                height: 20
                                implicitWidth: linkCountText.implicitWidth + 16
                                radius: 10
                                color: "#0C4A6E"
                                border.color: "#0284C7"
                                border.width: 1
                                Text {
                                    id: linkCountText
                                    anchors.left: parent.left
                                    anchors.leftMargin: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: creatorItem.link_count + " " + linkVaultRoot.tr("vault_links_badge", "Links")
                                    font.pixelSize: 10
                                    font.weight: Font.Bold
                                    color: "#38BDF8"
                                }
                            }

                            // Delete Creator Button
                            Rectangle {
                                width: 24
                                height: 24
                                radius: 4
                                color: delCreatorMouse.containsMouse ? "#3B181E" : "transparent"
                                scale: delCreatorMouse.pressed ? 0.86 : (delCreatorMouse.containsMouse ? 1.12 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                Text {
                                    anchors.centerIn: parent
                                    text: "🗑️"
                                    font.pixelSize: 11
                                }
                                MouseArea {
                                    id: delCreatorMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: linkVaultRoot.tr("tip_delete_creator", "Delete this artist and all their harvested links")
                                    onClicked: {
                                        if (linkVaultRoot.bridge) linkVaultRoot.bridge.deleteVaultCreator(creatorItem.creator_key)
                                    }
                                }
                            }
                        }

                        // ── Level 2: Posts List (Visible when Creator is expanded) ────
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: creatorCard.isExpanded
                            spacing: 8
                            Layout.leftMargin: 16

                            Repeater {
                                model: creatorItem.posts

                                delegate: Rectangle {
                                    id: postBox
                                    Layout.fillWidth: true
                                    implicitHeight: postCol.implicitHeight + 14
                                    color: "#0F1219"
                                    radius: 6
                                    border.color: "#1E2430"
                                    border.width: 1

                                    readonly property var postItem: modelData
                                    readonly property bool isTextExpanded: !!linkVaultRoot.expandedPostTexts[postItem.post_id]

                                    ColumnLayout {
                                        id: postCol
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        spacing: 6

                                        // Post Header
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 8

                                            Text { text: "📝"; font.pixelSize: 12 }
                                            Text {
                                                text: postItem.title || "Untitled Post"
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 12
                                                font.weight: 600
                                                color: "#E2E8F0"
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }

                                            // Date pill
                                            Text {
                                                visible: postItem.published ? true : false
                                                text: (postItem.published || "").substring(0, 10)
                                                font.pixelSize: 10
                                                color: "#64748B"
                                            }

                                            // Toggle Full Text Drawer Button
                                            Rectangle {
                                                height: 22
                                                implicitWidth: txtBtnText.implicitWidth + 16
                                                radius: 4
                                                color: txtBtnMouse.containsMouse ? "#1E293B" : "#141720"
                                                border.color: "#334155"
                                                border.width: 1
                                                scale: txtBtnMouse.pressed ? 0.90 : (txtBtnMouse.containsMouse ? 1.05 : 1.0)
                                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                                Text {
                                                    id: txtBtnText
                                                    anchors.centerIn: parent
                                                    text: postBox.isTextExpanded ? linkVaultRoot.tr("vault_hide_text", "Hide Text") : linkVaultRoot.tr("vault_view_text", "View Text")
                                                    font.pixelSize: 9
                                                    color: "#94A3B8"
                                                }
                                                MouseArea {
                                                    id: txtBtnMouse
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: linkVaultRoot.togglePostText(postItem.post_id)
                                                }
                                            }

                                            // Delete Post Button
                                            Rectangle {
                                                width: 22
                                                height: 22
                                                radius: 4
                                                color: delPostMouse.containsMouse ? "#3B181E" : "transparent"
                                                scale: delPostMouse.pressed ? 0.86 : (delPostMouse.containsMouse ? 1.12 : 1.0)
                                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                                Text { anchors.centerIn: parent; text: "✖"; font.pixelSize: 10; color: "#EF4444" }
                                                MouseArea {
                                                    id: delPostMouse
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    ToolTip.visible: containsMouse
                                                    ToolTip.delay: 300
                                                    ToolTip.text: linkVaultRoot.tr("tip_delete_post", "Delete this post and its links from vault")
                                                    onClicked: {
                                                        if (linkVaultRoot.bridge) linkVaultRoot.bridge.deleteVaultPost(postItem.post_id)
                                                    }
                                                }
                                            }
                                        }

                                        // Full Uncapped Text Preview Drawer
                                        Rectangle {
                                            Layout.fillWidth: true
                                            visible: postBox.isTextExpanded
                                            implicitHeight: fullTextArea.implicitHeight + 16
                                            color: "#080A0F"
                                            radius: 4
                                            border.color: "#1E2430"
                                            border.width: 1

                                            TextEdit {
                                                id: fullTextArea
                                                anchors.fill: parent
                                                anchors.margins: 8
                                                text: linkVaultRoot.cleanHtml(postItem.full_text)
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 12
                                                color: "#CBD5E1"
                                                readOnly: true
                                                selectByMouse: true
                                                wrapMode: TextEdit.Wrap
                                            }
                                        }

                                        // ── Level 3: Links Rows ────────────────────────────────
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 4
                                            Layout.leftMargin: 8

                                            Repeater {
                                                model: postItem.links

                                                delegate: Rectangle {
                                                    id: linkRowRect
                                                    Layout.fillWidth: true
                                                    implicitHeight: Math.max(34, linkInnerRow.implicitHeight + 8)
                                                    color: linkHover.hovered ? "#141A26" : "#0D1017"
                                                    radius: 4
                                                    border.color: linkHover.hovered ? "#38BDF8" : "#1E2430"
                                                    border.width: 1

                                                    readonly property var linkItem: modelData

                                                    transform: Translate {
                                                        y: linkHover.hovered && !linkVaultRoot.isScrolling ? -1.5 : 0
                                                        Behavior on y {
                                                             SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                                                        }
                                                    }
                                                    Behavior on border.color { ColorAnimation { duration: 120 } }
                                                    Behavior on color { ColorAnimation { duration: 120 } }

                                                    HoverHandler { id: linkHover }

                                                    RowLayout {
                                                        id: linkInnerRow
                                                        anchors.fill: parent
                                                        anchors.leftMargin: 8
                                                        anchors.rightMargin: 8
                                                        spacing: 8

                                                        // Host Platform Badge
                                                        Rectangle {
                                                            height: 20
                                                            implicitWidth: hostText.implicitWidth + 14
                                                            radius: 4
                                                            color: linkVaultRoot.platformColor(linkItem.platform)
                                                            Text {
                                                                id: hostText
                                                                anchors.left: parent.left
                                                                anchors.leftMargin: 7
                                                                anchors.verticalCenter: parent.verticalCenter
                                                                text: (linkItem.platform || "URL").toUpperCase()
                                                                font.pixelSize: 9
                                                                font.weight: Font.Bold
                                                                color: "#FFFFFF"
                                                            }
                                                        }

                                                        // Health Status Badge Pill
                                                        Rectangle {
                                                            id: healthPillRect
                                                            height: 20
                                                            implicitWidth: healthDot.width + healthText.implicitWidth + 19
                                                            radius: 4
                                                            color: "#141720"
                                                            border.color: linkVaultRoot.healthColor(linkItem.health)
                                                            border.width: 1

                                                            Rectangle {
                                                                id: healthDot
                                                                width: 6; height: 6; radius: 3
                                                                color: linkVaultRoot.healthColor(linkItem.health)
                                                                anchors.left: parent.left
                                                                anchors.leftMargin: 7
                                                                anchors.verticalCenter: parent.verticalCenter
                                                            }
                                                            Text {
                                                                id: healthText
                                                                anchors.left: healthDot.right
                                                                anchors.leftMargin: 4
                                                                anchors.verticalCenter: parent.verticalCenter
                                                                text: linkVaultRoot.healthLabel(linkItem.health)
                                                                font.pixelSize: 9
                                                                font.weight: Font.Bold
                                                                color: linkVaultRoot.healthColor(linkItem.health)
                                                            }
                                                        }

                                                        // URL text
                                                        Text {
                                                            text: linkItem.url || ""
                                                            font.family: "Segoe UI, sans-serif"
                                                            font.pixelSize: 11
                                                            color: "#38BDF8"
                                                            elide: Text.ElideMiddle
                                                            Layout.fillWidth: true
                                                        }

                                                        // Password Pills
                                                        Flow {
                                                            spacing: 4
                                                            Repeater {
                                                                model: linkItem.passwords || []

                                                                delegate: Rectangle {
                                                                    id: pwPill
                                                                    height: 22
                                                                    implicitWidth: pwInnerRow.implicitWidth + 14
                                                                    radius: 4
                                                                    color: pwMouse.containsMouse ? "#2E1065" : "#1E1B4B"
                                                                    border.color: "#818CF8"
                                                                    border.width: 1

                                                                    scale: pwMouse.pressed ? 0.90 : (pwMouse.containsMouse ? 1.08 : 1.0)
                                                                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }

                                                                    Row {
                                                                        id: pwInnerRow
                                                                        anchors.centerIn: parent
                                                                        spacing: 4
                                                                        Text { text: "🔑"; font.pixelSize: 9 }
                                                                        Text {
                                                                            id: pwText
                                                                            text: modelData
                                                                            font.family: "Segoe UI, sans-serif"
                                                                            font.pixelSize: 10
                                                                            font.weight: Font.Bold
                                                                            color: "#E0E7FF"
                                                                        }
                                                                    }

                                                                    MouseArea {
                                                                        id: pwMouse
                                                                        anchors.fill: parent
                                                                        hoverEnabled: true
                                                                        cursorShape: Qt.PointingHandCursor
                                                                        ToolTip.visible: containsMouse
                                                                        ToolTip.delay: 200
                                                                        ToolTip.text: linkVaultRoot.tr("tip_copy_pw", "Click to copy password: ") + modelData
                                                                        onClicked: {
                                                                            clipHelper.text = modelData
                                                                            clipHelper.selectAll()
                                                                            clipHelper.copy()
                                                                            linkVaultRoot.showToast(linkVaultRoot.tr("toast_pw_copied", "Password copied: ") + modelData)
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }

                                                        // Password Source Indicator Pill
                                                        Rectangle {
                                                            visible: linkItem.password_source && linkItem.password_source !== "post"
                                                            height: 18
                                                            implicitWidth: srcText.implicitWidth + 10
                                                            radius: 3
                                                            color: "#1E293B"
                                                            border.color: "#334155"
                                                            border.width: 1
                                                            Text {
                                                                id: srcText
                                                                anchors.left: parent.left
                                                                anchors.leftMargin: 5
                                                                anchors.verticalCenter: parent.verticalCenter
                                                                text: linkItem.password_source === "proximity" ? "📍 Near" : "🔗 Cross"
                                                                font.pixelSize: 8
                                                                color: "#94A3B8"
                                                            }
                                                        }

                                                        // Open URL in Browser Button
                                                        Rectangle {
                                                            width: 24; height: 24; radius: 4
                                                            color: openBtnMouse.containsMouse ? "#1E293B" : "transparent"
                                                            scale: openBtnMouse.pressed ? 0.86 : (openBtnMouse.containsMouse ? 1.12 : 1.0)
                                                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                                            Text { anchors.centerIn: parent; text: "🌐"; font.pixelSize: 11 }
                                                            MouseArea {
                                                                id: openBtnMouse
                                                                anchors.fill: parent
                                                                hoverEnabled: true
                                                                cursorShape: Qt.PointingHandCursor
                                                                ToolTip.visible: containsMouse
                                                                ToolTip.delay: 200
                                                                ToolTip.text: linkVaultRoot.tr("tip_open_browser", "Open in Web Browser")
                                                                onClicked: Qt.openUrlExternally(linkItem.url)
                                                            }
                                                        }

                                                        // Copy URL Button
                                                        Rectangle {
                                                            width: 24; height: 24; radius: 4
                                                            color: copyBtnMouse.containsMouse ? "#1E293B" : "transparent"
                                                            scale: copyBtnMouse.pressed ? 0.86 : (copyBtnMouse.containsMouse ? 1.12 : 1.0)
                                                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                                            Text { anchors.centerIn: parent; text: "📋"; font.pixelSize: 11 }
                                                            MouseArea {
                                                                id: copyBtnMouse
                                                                anchors.fill: parent
                                                                hoverEnabled: true
                                                                cursorShape: Qt.PointingHandCursor
                                                                ToolTip.visible: containsMouse
                                                                ToolTip.delay: 200
                                                                ToolTip.text: linkVaultRoot.tr("tip_copy_link", "Copy link URL")
                                                                onClicked: {
                                                                    clipHelper.text = linkItem.url
                                                                    clipHelper.selectAll()
                                                                    clipHelper.copy()
                                                                    linkVaultRoot.showToast(linkVaultRoot.tr("toast_link_copied", "URL copied to clipboard!"))
                                                                }
                                                            }
                                                        }

                                                        // Delete Link Button
                                                        Rectangle {
                                                            width: 24; height: 24; radius: 4
                                                            color: delLinkMouse.containsMouse ? "#3B181E" : "transparent"
                                                            scale: delLinkMouse.pressed ? 0.86 : (delLinkMouse.containsMouse ? 1.12 : 1.0)
                                                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                                            Text { anchors.centerIn: parent; text: "✖"; font.pixelSize: 10; color: "#EF4444" }
                                                            MouseArea {
                                                                id: delLinkMouse
                                                                anchors.fill: parent
                                                                hoverEnabled: true
                                                                cursorShape: Qt.PointingHandCursor
                                                                ToolTip.visible: containsMouse
                                                                ToolTip.delay: 200
                                                                ToolTip.text: linkVaultRoot.tr("tip_delete_link", "Delete link from vault")
                                                                onClicked: {
                                                                    if (linkVaultRoot.bridge) linkVaultRoot.bridge.deleteVaultLink(linkItem.id)
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
        }
    }

    // Hidden text helper for copying to clipboard
    TextInput {
        id: clipHelper
        visible: false
    }

    // ── Add / Harvest Artist Modal ─────────────────────────────────────────────
    Item {
        id: addArtistModal
        anchors.fill: parent
        z: 1000
        visible: opacity > 0
        opacity: isOpen ? 1.0 : 0.0
        Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        property bool isOpen: false
        property bool probeImmediately: true
        property bool allPages: true

        function open() {
            isOpen = true
            artistUrlField.forceActiveFocus()
        }

        function close() {
            isOpen = false
        }

        // Dim backdrop
        Rectangle {
            anchors.fill: parent
            color: "#B0060910"
            MouseArea {
                anchors.fill: parent
                onClicked: {} // Prevent click-through to underlying views
            }
        }

        // Modal Content Card
        Rectangle {
            id: modalCard
            width: Math.min(520, parent.width - 32)
            implicitHeight: modalCardCol.implicitHeight + 36
            anchors.centerIn: parent
            radius: 14
            color: "#131722"
            border.color: "#2D3748"
            border.width: 1.5

            transform: Translate {
                y: addArtistModal.isOpen ? 0 : -22
                Behavior on y {
                    SpringAnimation { spring: 4.8; damping: 0.38; mass: 0.85 }
                }
            }
            scale: addArtistModal.isOpen ? 1.0 : 0.92
            Behavior on scale {
                SpringAnimation { spring: 4.8; damping: 0.38; mass: 0.85 }
            }

            // Absorb unhandled clicks inside the card so nothing passes through
            MouseArea {
                anchors.fill: parent
            }

            ColumnLayout {
                id: modalCardCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 20
                spacing: 16

                // Modal Header
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Rectangle {
                        width: 32
                        height: 32
                        radius: 8
                        color: "#065F46"
                        border.color: "#10B981"
                        border.width: 1
                        Text { anchors.centerIn: parent; text: "🌾"; font.pixelSize: 16 }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: linkVaultRoot.tr("modal_harvest_artist_title", "Harvest Artist to Vault")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 16
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                        }
                        Text {
                            text: linkVaultRoot.tr("modal_harvest_artist_sub", "Extract all cloud links and passwords into Link Vault without downloading files.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }

                    // Close (X) button
                    Rectangle {
                        width: 28
                        height: 28
                        radius: 14
                        color: closeBtnMouse.containsMouse ? "#1E293B" : "transparent"
                        scale: closeBtnMouse.pressed ? 0.9 : 1.0
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.4 } }
                        Text {
                            anchors.centerIn: parent
                            text: "✕"
                            font.pixelSize: 13
                            color: closeBtnMouse.containsMouse ? "#FFFFFF" : "#64748B"
                        }
                        MouseArea {
                            id: closeBtnMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: addArtistModal.close()
                        }
                    }
                }

                // URL Input Field
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: linkVaultRoot.tr("label_artist_url", "Artist or Post URL")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: "#CBD5E1"
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 38
                        radius: 8
                        color: "#0F172A"
                        border.color: artistUrlField.activeFocus ? "#10B981" : "#334155"
                        border.width: 1.2
                        Behavior on border.color { ColorAnimation { duration: 120 } }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 10
                            spacing: 8

                            TextInput {
                                id: artistUrlField
                                Layout.fillWidth: true
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                color: "#F8FAFC"
                                selectByMouse: true
                                clip: true

                                Text {
                                    text: linkVaultRoot.tr("placeholder_artist_url", "https://kemono.cr/fanbox/user/1234567...")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    color: "#475569"
                                    visible: !artistUrlField.text && !artistUrlField.activeFocus
                                }
                            }

                            // Clear button
                            Text {
                                text: "✕"
                                font.pixelSize: 12
                                color: "#64748B"
                                visible: artistUrlField.text.length > 0
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: artistUrlField.text = ""
                                }
                            }
                        }
                    }
                }

                // Options Section
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    // Option 1: Probe health immediately
                    StyledSwitch {
                        label: linkVaultRoot.tr("opt_probe_health_now", "Probe link health immediately after harvest")
                        accentColor: "#10B981"
                        checked: addArtistModal.probeImmediately
                        onToggled: function(val) { addArtistModal.probeImmediately = val }
                    }

                    // Option 2: Page Range (All pages vs Custom Range)
                    StyledSwitch {
                        label: linkVaultRoot.tr("opt_harvest_all_posts", "Harvest all posts (entire creator history)")
                        accentColor: "#10B981"
                        checked: addArtistModal.allPages
                        onToggled: function(val) { addArtistModal.allPages = val }
                    }

                    // Page range inputs (if not all pages)
                    RowLayout {
                        visible: !addArtistModal.allPages
                        spacing: 12
                        Layout.leftMargin: 24

                        Text {
                            text: linkVaultRoot.tr("label_pages_from", "From page:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }

                        StyledSpinBox {
                            id: startPageSpin
                            from: 1
                            to: 9999
                            value: 1
                            accentColor: "#10B981"
                        }

                        Text {
                            text: linkVaultRoot.tr("label_pages_to", "To page:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }

                        StyledSpinBox {
                            id: endPageSpin
                            from: 1
                            to: 9999
                            value: 10
                            accentColor: "#10B981"
                        }
                    }
                }

                // In-Progress Harvest Status Card (visible when bridge is harvesting)
                Rectangle {
                    visible: linkVaultRoot.bridge && linkVaultRoot.bridge.linkVaultHarvestingActive
                    Layout.fillWidth: true
                    implicitHeight: modalStatusCol.implicitHeight + 18
                    radius: 8
                    color: "#064E3B"
                    border.color: "#34D399"
                    border.width: 1

                    ColumnLayout {
                        id: modalStatusCol
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 6

                        RowLayout {
                            spacing: 8
                            Rectangle {
                                width: 8
                                height: 8
                                radius: 4
                                color: "#34D399"
                                SequentialAnimation on opacity {
                                    loops: Animation.Infinite
                                    NumberAnimation { from: 1.0; to: 0.2; duration: 500 }
                                    NumberAnimation { from: 0.2; to: 1.0; duration: 500 }
                                }
                            }
                            Text {
                                text: linkVaultRoot.tr("label_harvest_in_progress", "Harvesting in progress...")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                color: "#A7F3D0"
                            }
                        }

                        Text {
                            text: linkVaultRoot.bridge ? linkVaultRoot.bridge.linkVaultHarvestingStatus : ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#ECFDF5"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }

                // Action Buttons Row (Cancel / Start Harvest)
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Layout.topMargin: 4

                    Item { Layout.fillWidth: true }

                    // Cancel / Close
                    Rectangle {
                        implicitWidth: cancelBtnText.implicitWidth + 24
                        height: 34
                        radius: 8
                        color: cancelModalMouse.containsMouse ? "#334155" : "#1E293B"
                        border.color: "#475569"
                        border.width: 1
                        scale: cancelModalMouse.pressed ? 0.94 : (cancelModalMouse.containsMouse ? 1.03 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38 } }

                        Text {
                            id: cancelBtnText
                            anchors.centerIn: parent
                            text: linkVaultRoot.tr("btn_close", "Close")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: "#CBD5E1"
                        }

                        MouseArea {
                            id: cancelModalMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: addArtistModal.close()
                        }
                    }

                    // Start Harvest Button
                    Rectangle {
                        id: startBtnRect
                        property bool isRunning: linkVaultRoot.bridge && linkVaultRoot.bridge.linkVaultHarvestingActive
                        property bool canStart: artistUrlField.text.trim().length > 0 && !startBtnRect.isRunning

                        implicitWidth: startBtnRow.implicitWidth + 28
                        height: 34
                        radius: 8
                        color: startBtnRect.canStart
                               ? (startModalMouse.containsMouse ? "#059669" : "#10B981")
                               : (startBtnRect.isRunning ? "#065F46" : "#1F2937")
                        border.color: startBtnRect.canStart ? "#34D399" : (startBtnRect.isRunning ? "#10B981" : "#374151")
                        border.width: 1
                        opacity: (startBtnRect.canStart || startBtnRect.isRunning) ? 1.0 : 0.6
                        scale: startModalMouse.pressed && startBtnRect.canStart ? 0.94 : (startModalMouse.containsMouse && startBtnRect.canStart ? 1.03 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38 } }
                        Behavior on color { ColorAnimation { duration: 120 } }

                        Row {
                            id: startBtnRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                text: startBtnRect.isRunning ? "⏳" : "🌾"
                                font.pixelSize: 12
                            }
                            Text {
                                text: startBtnRect.isRunning
                                      ? linkVaultRoot.tr("btn_harvesting", "Harvesting...")
                                      : linkVaultRoot.tr("btn_start_harvest", "Start Harvest")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                            }
                        }

                        MouseArea {
                            id: startModalMouse
                            anchors.fill: parent
                            hoverEnabled: startBtnRect.canStart
                            cursorShape: startBtnRect.canStart ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                if (startBtnRect.canStart && linkVaultRoot.bridge) {
                                    var pStart = addArtistModal.allPages ? 1 : startPageSpin.value
                                    var pEnd = addArtistModal.allPages ? 999999 : endPageSpin.value
                                    linkVaultRoot.bridge.harvestArtistToVault(
                                        artistUrlField.text.trim(),
                                        addArtistModal.probeImmediately,
                                        pStart,
                                        pEnd
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ── Toast Banner (Spring Recoil Entrance) ──────────────────────────────────
    Rectangle {
        id: statusToast
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 24
        implicitWidth: toastLabel.implicitWidth + 36
        height: 36
        radius: 18
        color: "#1E293B"
        border.color: "#38BDF8"
        border.width: 1
        opacity: 0.0
        z: 999

        property real offsetY: 20
        transform: Translate {
            y: statusToast.offsetY
            Behavior on y {
                SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85 }
            }
        }

        function show(msg) {
            toastLabel.text = msg
            toastAnim.restart()
        }

        Row {
            anchors.centerIn: parent
            spacing: 8
            Text { text: "✔"; font.pixelSize: 12; color: "#38BDF8" }
            Text {
                id: toastLabel
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: "#F8FAFC"
            }
        }

        SequentialAnimation {
            id: toastAnim
            ParallelAnimation {
                NumberAnimation { target: statusToast; property: "opacity"; to: 1.0; duration: 180; easing.type: Easing.OutCubic }
                PropertyAction { target: statusToast; property: "offsetY"; value: 0 }
            }
            PauseAnimation { duration: 2400 }
            ParallelAnimation {
                NumberAnimation { target: statusToast; property: "opacity"; to: 0.0; duration: 240; easing.type: Easing.InCubic }
                PropertyAction { target: statusToast; property: "offsetY"; value: 20 }
            }
        }
    }
}
