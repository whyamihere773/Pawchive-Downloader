import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "link_vault"

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

    function copyText(text) {
        clipHelper.text = text || ""
        clipHelper.selectAll()
        clipHelper.copy()
    }

    function openAddArtistModal() {
        addArtistModal.open()
    }

    function openEditPasswordModal(linkId, linkUrl, initialPasswords) {
        editPwModal.openForLink(linkId, linkUrl, initialPasswords)
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

    // Parsed tree data from bridge. Read again only while the tab is visible, at most every 150 ms:
    // the vault changes with every harvested link while downloading, and each read rebuilt it all
    // The creators: a model in Python (the whole vault as one JSON text, parsed here, froze big vaults)
    readonly property var vaultModel: bridge ? bridge.linkVaultCreatorsModel : null
    property bool _vaultStale: true
    property string _vaultRequest: ""
    function refreshVault() {
        _vaultStale = false
        if (!bridge) return
        // Built in the background; parsed when it arrives (onAsyncResultReady)
        _vaultRequest = "vault-tree-" + Date.now()
        bridge.linkVaultTreeJsonAsync(_vaultRequest)
    }
    Timer {
        id: vaultRefreshTimer
        interval: 150
        onTriggered: linkVaultRoot.refreshVault()
    }
    Connections {
        target: linkVaultRoot.bridge
        function onLinkVaultChanged() {
            if (linkVaultRoot.visible) vaultRefreshTimer.restart()
            else linkVaultRoot._vaultStale = true
        }
        function onAsyncResultReady(requestId, result) {
            if (requestId !== linkVaultRoot._vaultRequest) return
            linkVaultRoot._vaultRequest = ""
            if (linkVaultRoot.vaultModel) linkVaultRoot.vaultModel.applyPending()
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

    Component.onCompleted: { refreshVault(); triggerEntrance() }
    onVisibleChanged: {
        if (!visible) return
        if (_vaultStale) refreshVault()
        triggerEntrance()
    }

    // ── Newtonian Momentum Scrolling State ─────────────────────────────────────
    readonly property bool isScrolling: creatorsTree.isScrolling

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

        LinkVaultHeader {
            view: linkVaultRoot
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

                TextBarContextArea {
                    target: searchInput
                    focusOnLeftClick: true
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 8

                    Text { text: "🔍"; font.pixelSize: 12; color: "#64748B" }

                    TextInput {
                        id: searchInput
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        verticalAlignment: TextInput.AlignVCenter
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#F8FAFC"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true

                        Text {
                            text: linkVaultRoot.tr("vault_search_placeholder", "Filter by artist name, post title, cloud URL, or password...")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#475569"
                            visible: !searchInput.text && !searchInput.activeFocus
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            elide: Text.ElideRight
                        }

                        onTextChanged: {
                            linkVaultRoot.searchQuery = text
                            if (linkVaultRoot.bridge) linkVaultRoot.bridge.refreshLinkVault(linkVaultRoot.searchQuery, linkVaultRoot.activePlatform)
                        }

                        TextBarContextArea {}
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

        LinkVaultCreatorsTree {
            id: creatorsTree
            view: linkVaultRoot
        }
    }

    // Hidden text helper for copying to clipboard
    TextInput {
        id: clipHelper
        visible: false
    }


    LinkVaultAddArtistModal {
        id: addArtistModal
        view: linkVaultRoot
    }

    LinkVaultEditPasswordModal {
        id: editPwModal
        view: linkVaultRoot
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
