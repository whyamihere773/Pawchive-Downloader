import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: root
    property var bridge: null

    // ── Helpers ────────────────────────────────────────────────────────────────
    function tr(key, fallback) {
        if (typeof appWindow !== "undefined") return appWindow.tr(key, fallback)
        return fallback !== undefined ? fallback : key
    }

    function serviceColor(svc) {
        var s = (svc || "").toLowerCase()
        if (s === "onlyfans")    return "#00AFF0"
        if (s === "fansly")      return "#FF6B9D"
        if (s === "patreon")     return "#FF424D"
        if (s === "fanbox")      return "#007AFF"
        if (s === "gumroad")     return "#36C5AB"
        if (s === "subscribestar") return "#5C9DFF"
        if (s === "fantia")      return "#E84393"
        if (s === "boosty")      return "#F76A23"
        return "#64748B"
    }

    // ── Watchlist check & filter state ─────────────────────────────────────────
    property bool isChecking: false
    property int  lastNewCount: -1  // -1 = never checked
    property var  checkingArtists: ({})
    property string searchText: ""
    property string activeServiceFilter: "all"
    property bool showAddDialog: false
    property var  expandedArtists: ({})

    Connections {
        target: bridge
        function onWatchlistCheckStarted() { root.isChecking = true }
        function onWatchlistCheckFinished(n) {
            root.isChecking = false
            root.lastNewCount = n
            if (n > 0) resultToast.show(n)
        }
        function onWatchlistArtistChecking(uid, svc, checking) {
            var key = uid + "_" + svc
            var copy = Object.assign({}, root.checkingArtists)
            if (checking) {
                copy[key] = true
            } else {
                delete copy[key]
            }
            root.checkingArtists = copy
        }
        function onWatchlistArtistChecked(uid, svc, count) {
            if (count > 0) {
                resultToast.show(count)
            }
        }
        function onWatchlistChanged() {
            if (bridge && bridge.watchlistModel) {
                bridge.watchlistModel.refresh()
            }
        }
    }

    function showToast(msg) {
        if (typeof resultToast !== "undefined" && resultToast) {
            resultToast.showCustom(msg)
        }
    }

    // ── Layout ─────────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ──────────────────────────────────────────────────────────────
        // ── Header (Responsive layout: single row on wide screens, dual row on compact) ──
        Rectangle {
            id: headerRect
            Layout.fillWidth: true
            readonly property bool isCompact: root.width < 740
            height: isCompact ? 86 : 52
            color: "#0C0F18"
            border.color: "#1A2035"
            border.width: 1
            radius: 8
            clip: true

            Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

            // Gradient accent line
            Rectangle {
                width: parent.width * 0.6
                height: 1
                anchors.top: parent.top
                anchors.horizontalCenter: parent.horizontalCenter
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.3; color: "#A78BFA" }
                    GradientStop { position: 0.7; color: "#38BDF8" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 12
                anchors.topMargin: headerRect.isCompact ? 8 : 10
                anchors.bottomMargin: headerRect.isCompact ? 8 : 10
                spacing: 6

                // Row 1: Title + Subtitle + Badge + (Wide action holder)
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    // Icon + Title
                    Text { text: "\uD83D\uDCCC"; font.pixelSize: 18; Layout.alignment: Qt.AlignVCenter }
                    Text {
                        text: root.tr("tab_watchlist", "Watchlist")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 15
                        font.weight: 600
                        color: "#E2E8F0"
                        Layout.alignment: Qt.AlignVCenter
                    }

                    // Subtitle / entry count
                    Text {
                        text: {
                            if (!bridge || !bridge.watchlistModel) return ""
                            var c = bridge.watchlistModel.count
                            var tot = bridge.watchlistModel.totalCount
                            var u = bridge.watchlistModel.updatedCount
                            var base = c + " " + root.tr("watchlist_artists", "artist(s)")
                            if (root.searchText || root.activeServiceFilter !== "all") {
                                base = c + " of " + tot + " " + root.tr("watchlist_artists", "artist(s)")
                            }
                            if (u > 0) {
                                return base + "  •  " + u + " updated"
                            }
                            return base
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: (bridge && bridge.watchlistModel && bridge.watchlistModel.updatedCount > 0) ? 600 : Font.Normal
                        color: (bridge && bridge.watchlistModel && bridge.watchlistModel.updatedCount > 0) ? "#22D3EE" : "#4B5563"
                        Layout.alignment: Qt.AlignVCenter
                        elide: Text.ElideRight
                        Layout.maximumWidth: root.width < 860 ? 110 : (root.width < 1000 ? 180 : 300)
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 4
                    }

                    // High-visibility update counter badge
                    Rectangle {
                        id: resultBadge
                        readonly property int updArtists: bridge && bridge.watchlistModel ? bridge.watchlistModel.updatedCount : 0
                        readonly property int totalNew: bridge && bridge.watchlistModel ? bridge.watchlistModel.totalNewPosts : (root.lastNewCount > 0 ? root.lastNewCount : 0)
                        visible: updArtists > 0 || root.lastNewCount > 0
                        height: 28
                        implicitWidth: resultBadgeRow.implicitWidth + 20
                        radius: 14
                        color: "#071E26"
                        border.color: "#22D3EE"
                        border.width: 1.5

                        scale: resultBadgeMouse.containsMouse ? 1.04 : 1.0
                        Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutBack } }

                        Row {
                            id: resultBadgeRow
                            anchors.centerIn: parent
                            spacing: 6

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "✦"
                                font.pixelSize: 11
                                color: "#22D3EE"
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: {
                                    var count = resultBadge.totalNew > 0 ? resultBadge.totalNew : root.lastNewCount
                                    var art = resultBadge.updArtists
                                    if (count <= 0 && root.lastNewCount > 0) count = root.lastNewCount
                                    if (headerRect.isCompact && root.width < 550) {
                                        return count + " new"
                                    }
                                    if (root.width < 860) {
                                        return art > 1 ? (count + " new · " + art) : (count + " new")
                                    }
                                    if (art > 1) {
                                        return count + " new " + (count === 1 ? "post" : "posts") + " · " + art + " creators"
                                    } else {
                                        return count + " new " + (count === 1 ? "post" : "posts")
                                    }
                                }
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#A5F3FC"
                            }
                        }

                        MouseArea {
                            id: resultBadgeMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: {
                                var count = resultBadge.totalNew > 0 ? resultBadge.totalNew : root.lastNewCount
                                var art = resultBadge.updArtists
                                return count + " new post(s) found across " + art + " creator(s). Updated creators are pinned at the top."
                            }
                        }
                    }

                    // On wide screens (>= 760), action buttons dock here
                    Item {
                        id: wideActionHolder
                        visible: !headerRect.isCompact
                        Layout.preferredWidth: actionButtonsRow.implicitWidth
                        Layout.preferredHeight: 32
                    }
                }

                // Row 2: (Only visible when compact < 760)
                RowLayout {
                    id: compactRow
                    visible: headerRect.isCompact
                    Layout.fillWidth: true
                    spacing: 8

                    Item { Layout.fillWidth: true }

                    Item {
                        id: compactActionHolder
                        Layout.preferredWidth: actionButtonsRow.implicitWidth
                        Layout.preferredHeight: 32
                    }
                }
            }

            // Shared Action Buttons Row: docks to wideActionHolder or compactActionHolder
            Row {
                id: actionButtonsRow
                parent: headerRect.isCompact ? compactActionHolder : wideActionHolder
                spacing: 8
                anchors.verticalCenter: parent ? parent.verticalCenter : undefined

                // Download All Updates button
                Rectangle {
                    id: downloadAllBtn
                    readonly property int totalNew: bridge && bridge.watchlistModel ? bridge.watchlistModel.totalNewPosts : 0
                    visible: totalNew > 0
                    height: 32
                    implicitWidth: downloadAllRow.implicitWidth + 22
                    radius: 7
                    color: downloadAllMouse.pressed ? "#072019" : (downloadAllMouse.containsMouse ? "#0F382E" : "#07241C")
                    border.color: downloadAllMouse.containsMouse ? "#34D399" : "#10B981"
                    border.width: 1.2

                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                    scale: downloadAllMouse.pressed ? 0.94 : (downloadAllMouse.containsMouse ? 1.035 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: downloadAllRow
                        anchors.centerIn: parent
                        spacing: 6

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "↓"
                            font.pixelSize: 13
                            font.weight: Font.Bold
                            color: "#34D399"
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.width < 920
                                  ? ("Updates (" + downloadAllBtn.totalNew + ")")
                                  : (root.tr("watchlist_download_all_btn", "Download All Updates") + " (" + downloadAllBtn.totalNew + ")")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#6EE7B7"
                        }
                    }

                    MouseArea {
                        id: downloadAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: root.tr("watchlist_download_all_tip", "Download all newly discovered posts for all creators in your watchlist")
                        onClicked: if (bridge) bridge.downloadAllNewPosts()
                    }
                }

                // Add Artist button
                Rectangle {
                    id: addArtistBtn
                    height: 32
                    implicitWidth: addArtistRow.implicitWidth + 20
                    radius: 7
                    color: addArtistMouse.pressed ? "#16122C" : (addArtistMouse.containsMouse ? "#201840" : "#141026")
                    border.color: addArtistMouse.containsMouse ? "#A78BFA" : "#7C3AED"
                    border.width: 1

                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                    scale: addArtistMouse.pressed ? 0.94 : (addArtistMouse.containsMouse ? 1.035 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: addArtistRow
                        anchors.centerIn: parent
                        spacing: 5

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "➕"
                            font.pixelSize: 11
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.width < 820 ? "+ Artist" : root.tr("watchlist_add_artist_btn", "Add Artist")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#C4B5FD"
                        }
                    }

                    MouseArea {
                        id: addArtistMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: root.tr("watchlist_add_artist_tip", "Track an artist by URL without downloading past posts")
                        onClicked: root.showAddDialog = true
                    }
                }

                // Check All button
                Rectangle {
                    id: checkAllBtn
                    height: 32
                    implicitWidth: checkAllRow.implicitWidth + 20
                    radius: 7
                    color: checkAllMouse.containsMouse ? "#1E1B3D" : "#141228"
                    border.color: root.isChecking ? "#6D28D9" : "#4C1D95"
                    border.width: 1

                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                    scale: checkAllMouse.pressed ? 0.94 : (checkAllMouse.containsMouse ? 1.035 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: checkAllRow
                        anchors.centerIn: parent
                        spacing: 6

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.isChecking ? "\u21BB" : "\uD83D\uDD0D"
                            font.pixelSize: root.isChecking ? 13 : 11
                            color: "#A78BFA"

                            RotationAnimator on rotation {
                                from: 0; to: 360
                                duration: 900
                                loops: Animation.Infinite
                                running: root.isChecking
                            }
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.isChecking
                                  ? root.tr("watchlist_checking", "Checking…")
                                  : (root.width < 820 ? root.tr("watchlist_check_artist", "Check") : root.tr("watchlist_check_all", "Check All"))
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#A78BFA"
                        }
                    }

                    MouseArea {
                        id: checkAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: !root.isChecking
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: root.tr("watchlist_check_all_tip", "Check all followed artists for new posts")
                        onClicked: if (bridge) bridge.checkWatchlist()
                    }
                }
            }
        }

        // ── Search & Filter Toolbar (Feature 1.3) ─────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 46
            color: "#080B12"
            border.color: "#161B2A"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 12

                // Search Bar
                Rectangle {
                    Layout.preferredWidth: Math.min(260, parent.width * 0.35)
                    Layout.preferredHeight: 30
                    radius: 6
                    color: "#0F1422"
                    border.color: searchInput.activeFocus ? "#38BDF8" : (searchMouse.containsMouse ? "#2A364F" : "#1E2638")
                    border.width: 1

                    Behavior on border.color { ColorAnimation { duration: 150 } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 6

                        Text {
                            text: "🔍"
                            font.pixelSize: 11
                            color: "#64748B"
                        }

                        TextInput {
                            id: searchInput
                            Layout.fillWidth: true
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 11
                            color: "#E2E8F0"
                            selectionColor: "#0284C7"
                            selectedTextColor: "#FFFFFF"
                            clip: true

                            Text {
                                text: root.tr("watchlist_search_placeholder", "Search creator or ID…")
                                font: parent.font
                                color: "#475569"
                                visible: !searchInput.text && !searchInput.activeFocus
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            onTextChanged: {
                                root.searchText = text
                                if (bridge && bridge.watchlistModel) {
                                    bridge.watchlistModel.setFilter(text, root.activeServiceFilter)
                                }
                            }
                        }

                        Text {
                            text: "✕"
                            font.pixelSize: 11
                            color: clearMouse.containsMouse ? "#E2E8F0" : "#64748B"
                            visible: searchInput.text.length > 0
                            MouseArea {
                                id: clearMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: searchInput.text = ""
                            }
                        }
                    }

                    MouseArea {
                        id: searchMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                    }
                }

                // Divider
                Rectangle {
                    width: 1
                    height: 18
                    color: "#1E2638"
                }

                // Service Filter Chips (Flickable)
                Flickable {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32
                    contentWidth: chipsRow.implicitWidth
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    Row {
                        id: chipsRow
                        spacing: 6
                        anchors.verticalCenter: parent.verticalCenter

                        Repeater {
                            model: [
                                { id: "all",           label: root.tr("filter_all", "All") },
                                { id: "updates",       label: "✦ " + root.tr("filter_updates", "Updates") },
                                { id: "patreon",       label: "Patreon" },
                                { id: "fanbox",        label: "Fanbox" },
                                { id: "fansly",        label: "Fansly" },
                                { id: "onlyfans",      label: "OnlyFans" },
                                { id: "subscribestar", label: "SubscribeStar" },
                                { id: "boosty",        label: "Boosty" },
                                { id: "fantia",        label: "Fantia" },
                                { id: "gumroad",       label: "Gumroad" }
                            ]

                            Rectangle {
                                id: chipRect
                                height: 24
                                implicitWidth: chipText.implicitWidth + 16
                                radius: 12
                                readonly property bool isSelected: root.activeServiceFilter === modelData.id
                                color: isSelected 
                                       ? (modelData.id === "updates" ? "#0C2D3A" : "#1E1B3D")
                                       : (chipMouse.containsMouse ? "#161D2E" : "#0D111A")
                                border.color: isSelected 
                                              ? (modelData.id === "updates" ? "#22D3EE" : "#8B5CF6")
                                              : (chipMouse.containsMouse ? "#2E3A52" : "#1A2234")
                                border.width: 1

                                Behavior on color { ColorAnimation { duration: 120 } }
                                Behavior on border.color { ColorAnimation { duration: 120 } }

                                Text {
                                    id: chipText
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: chipRect.isSelected ? Font.Bold : 600
                                    color: chipRect.isSelected
                                           ? (modelData.id === "updates" ? "#A5F3FC" : "#DDD6FE")
                                           : (chipMouse.containsMouse ? "#94A3B8" : "#64748B")
                                }

                                MouseArea {
                                    id: chipMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.activeServiceFilter = modelData.id
                                        if (bridge && bridge.watchlistModel) {
                                            bridge.watchlistModel.setFilter(root.searchText, modelData.id)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ── Content: empty state OR entry list ────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // ── Empty state: no artists tracked at all ────────────────────────
            Column {
                anchors.centerIn: parent
                spacing: 14
                visible: (!bridge || !bridge.watchlistModel || bridge.watchlistModel.totalCount === 0)

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "\uD83D\uDCCC"
                    font.pixelSize: 52
                    color: "#2D3748"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.tr("watchlist_empty_title", "No artists tracked yet")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 15
                    font.weight: 600
                    color: "#4B5563"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 340
                    horizontalAlignment: Text.AlignHCenter
                    text: root.tr("watchlist_empty", "Artists you download will appear here automatically.\nOr click 'Add Artist' above to track any creator.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#374151"
                    wrapMode: Text.WordWrap
                    lineHeight: 1.5
                }
            }

            // ── Empty state: search/filter yielded 0 results ───────────────────
            Column {
                anchors.centerIn: parent
                spacing: 12
                visible: (bridge && bridge.watchlistModel && bridge.watchlistModel.totalCount > 0 && bridge.watchlistModel.count === 0)

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "🔍"
                    font.pixelSize: 42
                    opacity: 0.5
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.tr("watchlist_no_matches", "No artists match your search or filter")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 14
                    font.weight: 600
                    color: "#64748B"
                }
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    height: 28
                    implicitWidth: clearFiltersText.implicitWidth + 20
                    radius: 6
                    color: "#1E2538"
                    border.color: "#334155"
                    border.width: 1

                    Text {
                        id: clearFiltersText
                        anchors.centerIn: parent
                        text: root.tr("watchlist_clear_filters", "Clear Filters")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#94A3B8"
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            searchInput.text = ""
                            root.activeServiceFilter = "all"
                            if (bridge && bridge.watchlistModel) {
                                bridge.watchlistModel.setFilter("", "all")
                            }
                        }
                    }
                }
            }

            // ── Entry list ────────────────────────────────────────────────────
            SmoothListView {
                id: watchListView
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8
                clip: true
                visible: bridge && bridge.watchlistModel && bridge.watchlistModel.count > 0
                model: bridge ? bridge.watchlistModel : null

                delegate: Rectangle {
                    id: entryCard
                    width: watchListView.width
                    radius: 10

                    // ── Safe Model Property Accessors (Guards against model being undefined on reset)
                    readonly property var currentModel: (typeof model !== "undefined") ? model : null
                    readonly property bool hasUpdates: !!(currentModel && currentModel.newPostCount > 0)
                    readonly property string artistUserId: currentModel ? (currentModel.userId || "") : ""
                    readonly property string artistService: currentModel ? (currentModel.service || "") : ""
                    readonly property string artistCreatorName: currentModel ? (currentModel.creatorName || "") : ""
                    readonly property string artistUrl: currentModel ? (currentModel.url || "") : ""
                    readonly property string artistDownloadDir: currentModel ? (currentModel.downloadDir || "") : ""
                    readonly property string artistLastPostDate: currentModel ? (currentModel.lastPostDate || "") : ""
                    readonly property bool artistAutoCheck: currentModel ? !!currentModel.autoCheck : false
                    readonly property int currentNewPostCount: currentModel ? (currentModel.newPostCount || 0) : 0
                    readonly property int currentIgnoredCount: currentModel ? (currentModel.ignoredCount || 0) : 0
                    readonly property var currentCachedPosts: (currentModel && currentModel.cachedNewPosts) ? currentModel.cachedNewPosts : []

                    readonly property string artistKey: artistUserId + "_" + artistService
                    readonly property bool isArtistChecking: !!(root.checkingArtists[artistKey])
                    readonly property bool isExpanded: !!root.expandedArtists[artistKey]

                    // Date editing state
                    property bool isEditingDate: false

                    // Safe reference to view root for use inside deeply nested functions/delegates
                    readonly property var viewRoot: root

                    // Smooth dynamic height adapting to content, date editor, and post review with Newtonian spring physics
                    height: cardCol.implicitHeight + 24
                    Behavior on height {
                        SpringAnimation {
                            spring: 3.2
                            damping: 0.35
                            mass: 1.0
                            epsilon: 0.5
                        }
                    }

                    // Updated cards get a subtle cyan-tinted dark background
                    color: hasUpdates 
                           ? (cardMouse.containsMouse ? "#071E26" : "#050F14") 
                           : (cardMouse.containsMouse ? "#111827" : "#0D1117")

                    border.color: hasUpdates 
                                  ? (cardMouse.containsMouse ? "#38BDF8" : "#22D3EE") 
                                  : "#1E2330"
                    border.width: hasUpdates ? 1.5 : 1
                    clip: true

                    Behavior on color { ColorAnimation { duration: 140 } }
                    Behavior on border.color { ColorAnimation { duration: 140 } }

                    // Subtle top accent line on updated cards
                    Rectangle {
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 2
                        color: "#22D3EE"
                        opacity: 0.75
                        visible: hasUpdates
                    }

                    // Left accent bar
                    Rectangle {
                        width: hasUpdates ? 5 : 3
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        radius: 3
                        color: hasUpdates 
                               ? "#22D3EE" 
                               : (isArtistChecking ? "#8B5CF6" : root.serviceColor(entryCard.artistService))
                        opacity: hasUpdates ? 0.9 : 0.8
                    }

                    MouseArea {
                        id: cardMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                    }

                    Column {
                        id: cardCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 14
                        anchors.leftMargin: 18
                        spacing: 9

                        // ── Row 1: Name + Profile link + service badge + new badge
                        RowLayout {
                            width: parent.width
                            spacing: 8

                            Text {
                                text: (entryCard.hasUpdates ? "✦ " : "") + (entryCard.artistCreatorName || entryCard.artistUserId)
                                font.family: "Segoe UI, Inter, sans-serif"
                                font.pixelSize: 14
                                font.weight: entryCard.hasUpdates ? Font.Bold : 600
                                color: entryCard.hasUpdates ? "#A5F3FC" : "#E2E8F0"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            // Profile Link Button (↗)
                            Rectangle {
                                height: 22
                                width: 24
                                radius: 5
                                color: profileLinkMouse.containsMouse ? "#1E293B" : "#0F172A"
                                border.color: profileLinkMouse.containsMouse ? "#64748B" : "#334155"
                                border.width: 1

                                Text {
                                    anchors.centerIn: parent
                                    text: "↗"
                                    font.pixelSize: 12
                                    font.weight: Font.Bold
                                    color: profileLinkMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                                }

                                MouseArea {
                                    id: profileLinkMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 250
                                    ToolTip.text: root.tr("watchlist_open_profile_tip", "Open creator page in browser\n") + entryCard.artistUrl
                                    onClicked: {
                                        if (entryCard.artistUrl) Qt.openUrlExternally(entryCard.artistUrl)
                                    }
                                }
                            }

                            // Service pill
                            Rectangle {
                                height: 20
                                implicitWidth: svcPillText.implicitWidth + 14
                                radius: 10
                                color: Qt.rgba(
                                    parseInt(root.serviceColor(entryCard.artistService).substring(1,3),16)/255,
                                    parseInt(root.serviceColor(entryCard.artistService).substring(3,5),16)/255,
                                    parseInt(root.serviceColor(entryCard.artistService).substring(5,7),16)/255,
                                    0.15
                                )
                                border.color: root.serviceColor(entryCard.artistService)
                                border.width: 1

                                Text {
                                    id: svcPillText
                                    anchors.centerIn: parent
                                    text: entryCard.artistService.toUpperCase()
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: root.serviceColor(entryCard.artistService)
                                }
                            }

                            // New post count badge — interactive toggle for review
                            Rectangle {
                                visible: entryCard.hasUpdates
                                height: 20
                                implicitWidth: newBadgeRow.implicitWidth + 16
                                radius: 10
                                color: newBadgeMouse.containsMouse ? "#0C3342" : "#071E26"
                                border.color: "#22D3EE"
                                border.width: 1

                                Row {
                                    id: newBadgeRow
                                    anchors.centerIn: parent
                                    spacing: 4

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "✦"
                                        font.pixelSize: 9
                                        color: "#22D3EE"
                                    }
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: entryCard.currentNewPostCount + " new post" + (entryCard.currentNewPostCount === 1 ? "" : "s")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        font.weight: Font.Bold
                                        color: "#A5F3FC"
                                    }
                                }

                                MouseArea {
                                    id: newBadgeMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 250
                                    ToolTip.text: root.tr("watchlist_toggle_review_tip", "Click to review individual new posts")
                                    onClicked: {
                                        var copy = Object.assign({}, root.expandedArtists)
                                        copy[entryCard.artistKey] = !copy[entryCard.artistKey]
                                        root.expandedArtists = copy
                                    }
                                }
                            }
                        }

                        // ── Row 2: Last download date (interactive badge) + ignored count + auto-check toggle
                        RowLayout {
                            width: parent.width
                            spacing: 10

                            // Interactive Last Downloaded Date Badge with edit pencil
                            Rectangle {
                                id: dateBadge
                                height: 22
                                implicitWidth: dateBadgeRow.implicitWidth + 16
                                radius: 6
                                color: dateBadgeMouse.containsMouse ? "#182638" : "#0F1A28"
                                border.color: entryCard.isEditingDate ? "#38BDF8" : (dateBadgeMouse.containsMouse ? "#38BDF8" : "#243B55")
                                border.width: 1

                                Behavior on color { ColorAnimation { duration: 120 } }
                                Behavior on border.color { ColorAnimation { duration: 120 } }
                                scale: dateBadgeMouse.pressed ? 0.95 : (dateBadgeMouse.containsMouse ? 1.03 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack } }

                                Row {
                                    id: dateBadgeRow
                                    anchors.centerIn: parent
                                    spacing: 5

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "\uD83D\uDCC5"
                                        font.pixelSize: 10
                                    }
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: root.tr("watchlist_last_dl", "Last downloaded:")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: "#64748B"
                                    }
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: entryCard.artistLastPostDate || root.tr("watchlist_never", "Never")
                                        font.family: "Consolas, Segoe UI, monospace"
                                        font.pixelSize: 11
                                        font.weight: entryCard.artistLastPostDate ? Font.DemiBold : Font.Normal
                                        color: entryCard.artistLastPostDate ? "#93C5FD" : "#64748B"
                                    }
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: entryCard.isEditingDate ? "▲" : "✏️"
                                        font.pixelSize: 9
                                        opacity: dateBadgeMouse.containsMouse ? 1.0 : 0.6
                                    }
                                }

                                MouseArea {
                                    id: dateBadgeMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 250
                                    ToolTip.text: root.tr("watchlist_edit_date_tip", "Click to modify last downloaded cutoff date\nEnforces/converts to YYYY-MM-DD for Pawchive and Kemono")
                                    onClicked: {
                                        entryCard.isEditingDate = !entryCard.isEditingDate
                                        if (entryCard.isEditingDate) {
                                            dateInput.text = entryCard.artistLastPostDate || ""
                                            dateInput.forceActiveFocus()
                                        }
                                    }
                                }
                            }

                            // Ignored posts chip (with reset button)
                            Rectangle {
                                visible: entryCard.currentIgnoredCount > 0
                                height: 20
                                implicitWidth: ignoredRow.implicitWidth + 14
                                radius: 10
                                color: ignoredMouse.containsMouse ? "#2A1115" : "#190B0E"
                                border.color: ignoredMouse.containsMouse ? "#F87171" : "#EF4444"
                                border.width: 1

                                Row {
                                    id: ignoredRow
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "🚫 " + entryCard.currentIgnoredCount + " ignored"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        font.weight: 600
                                        color: "#FCA5A5"
                                    }
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "↻"
                                        font.pixelSize: 10
                                        font.weight: Font.Bold
                                        color: "#F87171"
                                    }
                                }

                                MouseArea {
                                    id: ignoredMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 250
                                    ToolTip.text: root.tr("watchlist_unignore_tip", "Click to reset ignored posts and re-check for updates")
                                    onClicked: {
                                        if (bridge) bridge.unignoreAllWatchlistPosts(entryCard.artistUserId, entryCard.artistService)
                                    }
                                }
                            }

                            Item { Layout.fillWidth: true }

                            // Auto-check toggle with fluid animations
                            Row {
                                spacing: 6
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: root.tr("watchlist_auto_check", "Auto-check")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: toggleMouse.containsMouse ? "#94A3B8" : "#64748B"
                                    Behavior on color { ColorAnimation { duration: 150 } }
                                }
                                Rectangle {
                                    id: autoCheckToggle
                                    width: 38; height: 20
                                    radius: 10
                                    color: entryCard.artistAutoCheck 
                                           ? (toggleMouse.containsMouse ? "#105C38" : "#0D4C2F") 
                                           : (toggleMouse.containsMouse ? "#263047" : "#1C2233")
                                    border.color: entryCard.artistAutoCheck 
                                                  ? (toggleMouse.containsMouse ? "#34D399" : "#10B981") 
                                                  : (toggleMouse.containsMouse ? "#475569" : "#2E3A56")
                                    border.width: 1
                                    anchors.verticalCenter: parent.verticalCenter
                                    scale: toggleMouse.pressed ? 0.88 : (toggleMouse.containsMouse ? 1.08 : 1.0)
                                    transformOrigin: Item.Center

                                    Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.4 } }
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                    Behavior on border.color { ColorAnimation { duration: 180 } }

                                    Rectangle {
                                        id: toggleKnob
                                        width: toggleMouse.pressed ? 18 : 14
                                        height: 14
                                        radius: 7
                                        anchors.verticalCenter: parent.verticalCenter
                                        x: entryCard.artistAutoCheck ? parent.width - width - 3 : 3
                                        color: entryCard.artistAutoCheck 
                                               ? (toggleMouse.containsMouse ? "#6EE7B7" : "#34D399") 
                                               : (toggleMouse.containsMouse ? "#94A3B8" : "#64748B")

                                        Behavior on x { NumberAnimation { duration: 220; easing.type: Easing.OutBack; easing.overshoot: 1.6 } }
                                        Behavior on width { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
                                        Behavior on color { ColorAnimation { duration: 180 } }
                                    }

                                    MouseArea {
                                        id: toggleMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 350
                                        ToolTip.text: entryCard.artistAutoCheck
                                                      ? root.tr("watchlist_autocheck_on", "Auto-check enabled on launch")
                                                      : root.tr("watchlist_autocheck_off", "Auto-check disabled")
                                        onClicked: {
                                            if (bridge) bridge.setWatchlistAutoCheck(entryCard.artistUserId, entryCard.artistService, !entryCard.artistAutoCheck)
                                        }
                                    }
                                }
                            }
                        }

                        // ── Inline Date Editor Drawer (Enforces / Converts to YYYY-MM-DD for Pawchive & Kemono)
                        Item {
                            id: dateEditorContainer
                            width: parent.width
                            height: entryCard.isEditingDate ? dateEditorBg.implicitHeight : 0
                            clip: true
                            visible: height > 0.5
                            opacity: entryCard.isEditingDate ? 1.0 : 0.0

                            Behavior on height {
                                SpringAnimation {
                                    spring: 3.2
                                    damping: 0.35
                                    mass: 1.0
                                    epsilon: 0.5
                                }
                            }
                            Behavior on opacity {
                                NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
                            }

                            Rectangle {
                                id: dateEditorBg
                                width: parent.width
                                implicitHeight: dateEditorCol.implicitHeight + 16
                                radius: 8
                                color: "#080E1B"
                                border.color: "#0284C7"
                                border.width: 1.2
                                y: entryCard.isEditingDate ? 0 : -6
                                transformOrigin: Item.Top
                                Behavior on y {
                                    SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0; epsilon: 0.5 }
                                }

                                ColumnLayout {
                                    id: dateEditorCol
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: 10
                                    spacing: 8

                                    readonly property string validationResult: {
                                        if (!entryCard.isEditingDate) return ""
                                        var t = (dateInput.text || "").trim()
                                        if (!t) return "EMPTY"
                                        return (bridge && typeof bridge.normalizeWatchlistDate === "function")
                                            ? bridge.normalizeWatchlistDate(t)
                                            : t
                                    }
                                    readonly property bool isDateValid: validationResult !== "INVALID"

                                    // Header & quick shortcut chips
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8

                                        Text {
                                            text: "📅 " + root.tr("watchlist_edit_cutoff_title", "Set Last Downloaded Cutoff Date:")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: Font.Bold
                                            color: "#BAE6FD"
                                        }

                                        Item { Layout.fillWidth: true }

                                        // Today quick chip
                                        Rectangle {
                                            height: 20
                                            implicitWidth: todayText.implicitWidth + 12
                                            radius: 4
                                            color: todayMouse.containsMouse ? "#1E293B" : "#0F172A"
                                            border.color: "#334155"
                                            border.width: 1

                                            Text {
                                                id: todayText
                                                anchors.centerIn: parent
                                                text: "Today"
                                                font.pixelSize: 10
                                                font.weight: 600
                                                color: "#94A3B8"
                                            }
                                            MouseArea {
                                                id: todayMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    dateInput.text = Qt.formatDate(new Date(), "yyyy-MM-dd")
                                                }
                                            }
                                        }

                                        // Reset to Never quick chip
                                        Rectangle {
                                            height: 20
                                            implicitWidth: clearDateText.implicitWidth + 12
                                            radius: 4
                                            color: clearDateMouse.containsMouse ? "#2A1215" : "#190B0E"
                                            border.color: "#7F1D1D"
                                            border.width: 1

                                            Text {
                                                id: clearDateText
                                                anchors.centerIn: parent
                                                text: "Reset (Never)"
                                                font.pixelSize: 10
                                                font.weight: 600
                                                color: "#FCA5A5"
                                            }
                                            MouseArea {
                                                id: clearDateMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                ToolTip.visible: containsMouse
                                                ToolTip.delay: 250
                                                ToolTip.text: "Clear cutoff date so all artist posts are eligible as updates"
                                                onClicked: {
                                                    dateInput.text = ""
                                                }
                                            }
                                        }
                                    }

                                    // Input row & Save / Cancel buttons
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8

                                        Rectangle {
                                            Layout.fillWidth: true
                                            height: 32
                                            radius: 5
                                            color: "#050811"
                                            border.color: dateInput.activeFocus ? "#38BDF8" : (dateEditorCol.isDateValid ? "#1E293B" : "#EF4444")
                                            border.width: 1

                                            TextInput {
                                                id: dateInput
                                                anchors.fill: parent
                                                anchors.leftMargin: 10
                                                anchors.rightMargin: 10
                                                verticalAlignment: TextInput.AlignVCenter
                                                font.family: "Consolas, Segoe UI, monospace"
                                                font.pixelSize: 12
                                                color: "#F1F5F9"
                                                text: entryCard.artistLastPostDate || ""
                                                selectByMouse: true

                                                Text {
                                                    text: "YYYY-MM-DD (e.g. 2024-05-18, 18/05/2024, Aug 19 2024)"
                                                    font: parent.font
                                                    color: "#475569"
                                                    visible: !dateInput.text && !dateInput.activeFocus
                                                    anchors.verticalCenter: parent.verticalCenter
                                                }

                                                Keys.onReturnPressed: saveDateBtn.doSave()
                                                Keys.onEnterPressed: saveDateBtn.doSave()
                                                Keys.onEscapePressed: entryCard.isEditingDate = false
                                            }
                                        }

                                        // Save button
                                        Rectangle {
                                            id: saveDateBtn
                                            height: 32
                                            implicitWidth: saveDateText.implicitWidth + 20
                                            radius: 5
                                            opacity: dateEditorCol.isDateValid ? 1.0 : 0.4
                                            color: saveDateMouse.containsMouse ? "#0C382E" : "#07241C"
                                            border.color: "#10B981"
                                            border.width: 1

                                            function doSave() {
                                                if (!dateEditorCol.isDateValid) return
                                                if (bridge) {
                                                    var res = bridge.setWatchlistLastDownloadDate(entryCard.artistUserId, entryCard.artistService, dateInput.text)
                                                    entryCard.isEditingDate = false
                                                    entryCard.viewRoot.showToast("✅ Saved cutoff date: " + (res || "Never"))
                                                }
                                            }

                                            Text {
                                                id: saveDateText
                                                anchors.centerIn: parent
                                                text: "✓ Save"
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 11
                                                font.weight: Font.Bold
                                                color: "#6EE7B7"
                                            }

                                            MouseArea {
                                                id: saveDateMouse
                                                anchors.fill: parent
                                                hoverEnabled: dateEditorCol.isDateValid
                                                cursorShape: dateEditorCol.isDateValid ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                onClicked: saveDateBtn.doSave()
                                            }
                                        }

                                        // Cancel button
                                        Rectangle {
                                            height: 32
                                            implicitWidth: cancelDateText.implicitWidth + 18
                                            radius: 5
                                            color: cancelDateMouse.containsMouse ? "#1E2536" : "#131826"
                                            border.color: "#2E3A52"
                                            border.width: 1

                                            Text {
                                                id: cancelDateText
                                                anchors.centerIn: parent
                                                text: "✕ Cancel"
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 11
                                                font.weight: 600
                                                color: "#94A3B8"
                                            }

                                            MouseArea {
                                                id: cancelDateMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: entryCard.isEditingDate = false
                                            }
                                        }
                                    }

                                    // Live conversion guidance
                                    Text {
                                        text: {
                                            if (!entryCard.isEditingDate) return ""
                                            if (dateEditorCol.validationResult === "INVALID") {
                                                return "⚠️ Unrecognized date. Please use YYYY-MM-DD or DD/MM/YYYY, Month DD YYYY"
                                            }
                                            if (dateEditorCol.validationResult === "EMPTY" || !dateInput.text.trim()) {
                                                return "ℹ️ Will reset cutoff to 'Never' (checks will consider all posts as new)"
                                            }
                                            return "✓ Converted to: " + dateEditorCol.validationResult + " (enforced Pawchive & Kemono format)"
                                        }
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        font.weight: 500
                                        color: !dateEditorCol.isDateValid ? "#F87171" : (dateInput.text.trim() ? "#34D399" : "#64748B")
                                        Layout.fillWidth: true
                                    }
                                }
                            }
                        }

                        // ── Row 2.5: Download folder info & Clickable Explorer Link (Feature 1.2)
                        RowLayout {
                            width: parent.width
                            spacing: 6

                            // Clickable folder path box
                            Rectangle {
                                Layout.fillWidth: true
                                height: 24
                                radius: 5
                                color: folderPathMouse.containsMouse ? "#111A2B" : "#0A0F1A"
                                border.color: folderPathMouse.containsMouse ? "#38BDF8" : "#1C2436"
                                border.width: 1

                                Behavior on color { ColorAnimation { duration: 120 } }
                                Behavior on border.color { ColorAnimation { duration: 120 } }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 6
                                    anchors.rightMargin: 6
                                    spacing: 6

                                    Text {
                                        text: "📁"
                                        font.pixelSize: 11
                                    }
                                    Text {
                                        text: entryCard.artistDownloadDir || root.tr("watchlist_no_folder", "Default download folder")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: folderPathMouse.containsMouse ? "#38BDF8" : (entryCard.artistDownloadDir ? "#94A3B8" : "#4B5563")
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                        Behavior on color { ColorAnimation { duration: 120 } }
                                    }
                                }

                                MouseArea {
                                    id: folderPathMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 250
                                    ToolTip.text: root.tr("watchlist_open_folder_tip", "Click to open folder in File Explorer\n") + (entryCard.artistDownloadDir || "Default download folder")
                                    onClicked: {
                                        if (bridge) bridge.openFolder(entryCard.artistDownloadDir)
                                    }
                                }
                            }

                            // Browse button (📂)
                            Rectangle {
                                height: 24
                                width: 28
                                radius: 5
                                color: browseFolderMouse.containsMouse ? "#1E293B" : "#0F172A"
                                border.color: browseFolderMouse.containsMouse ? "#64748B" : "#334155"
                                border.width: 1

                                Text {
                                    anchors.centerIn: parent
                                    text: "📂"
                                    font.pixelSize: 11
                                }
                                MouseArea {
                                    id: browseFolderMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: root.tr("watchlist_browse_tip", "Change download folder for this artist")
                                    onClicked: {
                                        if (bridge) bridge.browseWatchlistDownloadDir(entryCard.artistUserId, entryCard.artistService)
                                    }
                                }
                            }
                        }

                        // ── Row 3: Action buttons (Flow layout wraps responsively on narrow widths)
                        Flow {
                            width: parent.width
                            spacing: 8
                            bottomPadding: 2

                            // Check Single Artist Button
                            Rectangle {
                                height: 28
                                implicitWidth: checkArtistRow.implicitWidth + 20
                                radius: 6
                                color: checkArtistMouse.containsMouse ? "#1E1B3D" : "#121024"
                                border.color: entryCard.isArtistChecking ? "#8B5CF6" : (checkArtistMouse.containsMouse ? "#6D28D9" : "#4C1D95")
                                border.width: 1
                                Behavior on color { ColorAnimation { duration: 100 } }
                                Behavior on border.color { ColorAnimation { duration: 100 } }
                                scale: checkArtistMouse.pressed ? 0.94 : (checkArtistMouse.containsMouse ? 1.04 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                                Row {
                                    id: checkArtistRow
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Text {
                                        text: entryCard.isArtistChecking ? "\u21BB" : "\uD83D\uDD0D"
                                        font.pixelSize: entryCard.isArtistChecking ? 12 : 10
                                        color: entryCard.isArtistChecking ? "#C4B5FD" : "#A78BFA"
                                        anchors.verticalCenter: parent.verticalCenter
                                        RotationAnimator on rotation {
                                            from: 0; to: 360
                                            duration: 800
                                            loops: Animation.Infinite
                                            running: entryCard.isArtistChecking
                                        }
                                    }
                                    Text {
                                        text: entryCard.isArtistChecking
                                              ? root.tr("watchlist_checking", "Checking…")
                                              : root.tr("watchlist_check_artist", "Check")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: 600
                                        color: entryCard.isArtistChecking ? "#DDD6FE" : "#C4B5FD"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: checkArtistMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: !entryCard.isArtistChecking && !root.isChecking
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: root.tr("watchlist_check_artist_tip", "Check only this artist for new posts")
                                    onClicked: {
                                        if (bridge) bridge.checkWatchlistArtist(entryCard.artistUserId, entryCard.artistService)
                                    }
                                }
                            }

                            // Download New Posts Button
                            Rectangle {
                                height: 28
                                implicitWidth: dlNewRow.implicitWidth + 20
                                radius: 6
                                visible: entryCard.hasUpdates
                                color: dlNewMouse.containsMouse ? "#0C2D3A" : "#071E26"
                                border.color: dlNewMouse.containsMouse ? "#38BDF8" : "#22D3EE"
                                border.width: 1
                                Behavior on color { ColorAnimation { duration: 100 } }
                                Behavior on border.color { ColorAnimation { duration: 100 } }
                                scale: dlNewMouse.pressed ? 0.94 : (dlNewMouse.containsMouse ? 1.04 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                                Row {
                                    id: dlNewRow
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Text {
                                        text: "↓"
                                        font.pixelSize: 12
                                        font.weight: Font.Bold
                                        color: "#22D3EE"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Text {
                                        text: "Download " + entryCard.currentNewPostCount + " New Post" + (entryCard.currentNewPostCount === 1 ? "" : "s")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: 600
                                        color: "#A5F3FC"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: dlNewMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: "Download all " + entryCard.currentNewPostCount + " new post(s) published by " + (entryCard.artistCreatorName || entryCard.artistUserId)
                                    onClicked: {
                                        if (bridge) bridge.downloadNewPosts(entryCard.artistUserId, entryCard.artistService)
                                    }
                                }
                            }

                            // Review Posts Button
                            Rectangle {
                                height: 28
                                implicitWidth: reviewBtnRow.implicitWidth + 18
                                radius: 6
                                visible: entryCard.hasUpdates || entryCard.currentCachedPosts.length > 0
                                color: reviewBtnMouse.containsMouse ? "#182638" : "#0F1A28"
                                border.color: entryCard.isExpanded ? "#38BDF8" : "#243B55"
                                border.width: 1
                                Behavior on color { ColorAnimation { duration: 100 } }
                                Behavior on border.color { ColorAnimation { duration: 100 } }
                                scale: reviewBtnMouse.pressed ? 0.94 : (reviewBtnMouse.containsMouse ? 1.04 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack } }

                                Row {
                                    id: reviewBtnRow
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Text {
                                        text: "▼"
                                        font.pixelSize: 9
                                        color: "#38BDF8"
                                        anchors.verticalCenter: parent.verticalCenter
                                        rotation: entryCard.isExpanded ? 180 : 0
                                        transformOrigin: Item.Center
                                        Behavior on rotation {
                                            SpringAnimation {
                                                spring: 3.5
                                                damping: 0.3
                                                mass: 0.9
                                                epsilon: 0.25
                                            }
                                        }
                                    }
                                    Text {
                                        text: entryCard.isExpanded ? "Hide Review" : "Review Posts"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: 600
                                        color: "#BAE6FD"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: reviewBtnMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 250
                                    ToolTip.text: root.tr("watchlist_review_tip", "Review, selectively download, or ignore specific new posts")
                                    onClicked: {
                                        var copy = Object.assign({}, root.expandedArtists)
                                        copy[entryCard.artistKey] = !copy[entryCard.artistKey]
                                        root.expandedArtists = copy
                                    }
                                }
                            }

                            // Re-download All
                            Rectangle {
                                height: 28
                                implicitWidth: redownloadRow.implicitWidth + 20
                                radius: 6
                                color: redownloadMouse.containsMouse ? "#1A1430" : "#100E22"
                                border.color: "#4C1D95"
                                border.width: 1
                                Behavior on color { ColorAnimation { duration: 100 } }
                                scale: redownloadMouse.pressed ? 0.94 : (redownloadMouse.containsMouse ? 1.04 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                                Row {
                                    id: redownloadRow
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Text { text: "\uD83D\uDD04"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                    Text {
                                        text: root.tr("watchlist_redownload", "Re-download All")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: 600
                                        color: "#A78BFA"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: redownloadMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: root.tr("watchlist_redownload_tip", "Re-queue the entire artist's catalog for download")
                                    onClicked: if (bridge) bridge.redownloadWatchlistEntry(entryCard.artistUserId, entryCard.artistService)
                                }
                            }

                            // Remove
                            Rectangle {
                                height: 28
                                implicitWidth: removeRow.implicitWidth + 20
                                radius: 6
                                color: removeMouse.containsMouse ? "#2A0D0D" : "#1A0808"
                                border.color: "#7F1D1D"
                                border.width: 1
                                Behavior on color { ColorAnimation { duration: 100 } }
                                scale: removeMouse.pressed ? 0.94 : (removeMouse.containsMouse ? 1.04 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                                Row {
                                    id: removeRow
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Text { text: "\uD83D\uDDD1"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                    Text {
                                        text: root.tr("watchlist_remove", "Remove")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: 600
                                        color: "#FCA5A5"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: removeMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: root.tr("watchlist_remove_tip", "Stop tracking this artist and remove from watchlist")
                                    onClicked: if (bridge) bridge.removeFromWatchlist(entryCard.artistUserId, entryCard.artistService)
                                }
                            }
                        }

                        // ── Row 4: Post Review Drawer (Newtonian weight-centered fluid animation)
                        Item {
                            id: reviewDrawerContainer
                            width: parent.width
                            readonly property bool shouldShow: entryCard.isExpanded && (entryCard.hasUpdates || entryCard.currentCachedPosts.length > 0)
                            readonly property real targetHeight: reviewDrawerBg.implicitHeight
                            height: shouldShow ? targetHeight : 0
                            clip: true
                            visible: height > 0.5
                            opacity: shouldShow ? 1.0 : 0.0

                            Behavior on height {
                                SpringAnimation {
                                    spring: 3.2
                                    damping: 0.35
                                    mass: 1.0
                                    epsilon: 0.5
                                }
                            }

                            Behavior on opacity {
                                NumberAnimation {
                                    duration: 220
                                    easing.type: Easing.OutCubic
                                }
                            }

                            Rectangle {
                                id: reviewDrawerBg
                                width: parent.width
                                implicitHeight: reviewCol.implicitHeight + 16
                                radius: 8
                                color: "#05080E"
                                border.color: "#1E293B"
                                border.width: 1
                                y: reviewDrawerContainer.shouldShow ? 0 : -8
                                scale: reviewDrawerContainer.shouldShow ? 1.0 : 0.97
                                transformOrigin: Item.Top

                                Behavior on y {
                                    SpringAnimation {
                                        spring: 3.5
                                        damping: 0.35
                                        mass: 1.0
                                        epsilon: 0.5
                                    }
                                }
                                Behavior on scale {
                                    SpringAnimation {
                                        spring: 3.5
                                        damping: 0.35
                                        mass: 1.0
                                        epsilon: 0.01
                                    }
                                }

                                Column {
                                    id: reviewCol
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: 10
                                    spacing: 6

                                    // Drawer Header
                                    RowLayout {
                                        width: parent.width

                                        Text {
                                            text: "📋 " + root.tr("watchlist_pending_updates", "Discovered Updates") + " (" + entryCard.currentCachedPosts.length + ")"
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: Font.Bold
                                            color: "#A5F3FC"
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }

                                        // Dismiss / Ignore all current updates
                                        Rectangle {
                                            height: 22
                                            implicitWidth: ignoreAllText.implicitWidth + 14
                                            radius: 4
                                            color: ignoreAllMouse.containsMouse ? "#2B1115" : "#1A0B0E"
                                            border.color: "#7F1D1D"
                                            border.width: 1

                                            Text {
                                                id: ignoreAllText
                                                anchors.centerIn: parent
                                                text: root.width < 500 ? "🚫 Dismiss" : ("🚫 " + root.tr("watchlist_ignore_all_updates", "Dismiss / Ignore All"))
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 10
                                                font.weight: 600
                                                color: "#FCA5A5"
                                            }

                                            MouseArea {
                                                id: ignoreAllMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                ToolTip.visible: containsMouse
                                                ToolTip.delay: 250
                                                ToolTip.text: root.tr("watchlist_ignore_all_tip", "Permanently skip all currently discovered posts (future new posts will still be detected)")
                                                onClicked: {
                                                    if (bridge) bridge.ignoreCurrentNewPosts(entryCard.artistUserId, entryCard.artistService)
                                                }
                                            }
                                        }

                                        // Download all remaining button
                                        Rectangle {
                                            height: 22
                                            implicitWidth: dlRemainingText.implicitWidth + 14
                                            radius: 4
                                            color: dlRemainingMouse.containsMouse ? "#0C2D3A" : "#071E26"
                                            border.color: "#22D3EE"
                                            border.width: 1

                                            Text {
                                                id: dlRemainingText
                                                anchors.centerIn: parent
                                                text: root.width < 500 ? "↓ Get All" : ("↓ " + root.tr("watchlist_download_all", "Download All"))
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 10
                                                font.weight: 600
                                                color: "#A5F3FC"
                                            }

                                            MouseArea {
                                                id: dlRemainingMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                ToolTip.visible: containsMouse
                                                ToolTip.delay: 250
                                                ToolTip.text: root.tr("watchlist_download_all_tip", "Download all remaining new posts for this artist")
                                                onClicked: {
                                                    if (bridge) bridge.downloadNewPosts(entryCard.artistUserId, entryCard.artistService)
                                                }
                                            }
                                        }
                                    }

                                    // Post items repeater (Uses safely guarded entryCard.currentCachedPosts)
                                    Repeater {
                                        model: entryCard.currentCachedPosts

                                        Rectangle {
                                            width: reviewCol.width
                                            height: 28
                                            radius: 5
                                            color: postItemMouse.containsMouse ? "#0D1524" : "#090D18"
                                            border.color: postItemMouse.containsMouse ? "#1E293B" : "#131A29"
                                            border.width: 1

                                            MouseArea {
                                                id: postItemMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                acceptedButtons: Qt.NoButton
                                            }

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.leftMargin: 8
                                                anchors.rightMargin: 8
                                                spacing: 8

                                                // Date pill
                                                Text {
                                                    text: (modelData && modelData.published) ? modelData.published : "----/--/--"
                                                    font.family: "Consolas, Segoe UI, monospace"
                                                    font.pixelSize: 10
                                                    color: "#64748B"
                                                }

                                                // Post title
                                                Text {
                                                    text: (modelData && modelData.title) ? modelData.title : ("Post " + (modelData ? modelData.id : ""))
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 11
                                                    font.weight: 500
                                                    color: "#E2E8F0"
                                                    elide: Text.ElideRight
                                                    Layout.fillWidth: true
                                                }

                                                // Single post ignore button
                                                Rectangle {
                                                    height: 20
                                                    implicitWidth: ignPostText.implicitWidth + 10
                                                    radius: 4
                                                    color: ignPostMouse.containsMouse ? "#3B1419" : "#220C10"
                                                    border.color: "#991B1B"
                                                    border.width: 1

                                                    Text {
                                                        id: ignPostText
                                                        anchors.centerIn: parent
                                                        text: "🚫 Skip"
                                                        font.family: "Segoe UI, sans-serif"
                                                        font.pixelSize: 9
                                                        font.weight: 600
                                                        color: "#FCA5A5"
                                                    }

                                                    MouseArea {
                                                        id: ignPostMouse
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        ToolTip.visible: containsMouse
                                                        ToolTip.delay: 250
                                                        ToolTip.text: root.tr("watchlist_skip_post_tip", "Permanently ignore this post (won't be downloaded)")
                                                        onClicked: {
                                                            if (bridge && modelData && modelData.id) {
                                                                bridge.ignoreWatchlistPost(entryCard.artistUserId, entryCard.artistService, modelData.id)
                                                            }
                                                        }
                                                    }
                                                }

                                                // Single post download button
                                                Rectangle {
                                                    height: 20
                                                    implicitWidth: dlPostText.implicitWidth + 10
                                                    radius: 4
                                                    color: dlPostMouse.containsMouse ? "#0A3B4C" : "#072633"
                                                    border.color: "#0284C7"
                                                    border.width: 1

                                                    Text {
                                                        id: dlPostText
                                                        anchors.centerIn: parent
                                                        text: "↓ Get"
                                                        font.family: "Segoe UI, sans-serif"
                                                        font.pixelSize: 9
                                                        font.weight: 600
                                                        color: "#38BDF8"
                                                    }

                                                    MouseArea {
                                                        id: dlPostMouse
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        ToolTip.visible: containsMouse
                                                        ToolTip.delay: 250
                                                        ToolTip.text: root.tr("watchlist_get_post_tip", "Download only this post")
                                                        onClicked: {
                                                            if (bridge && modelData && modelData.id) {
                                                                bridge.downloadNewPosts(entryCard.artistUserId, entryCard.artistService, [modelData.id])
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

    // ── Add Artist Modal Dialog (Responsive, scrollable & perfectly contained) ──
    Item {
        id: addArtistModal
        anchors.fill: parent
        z: 9999
        visible: root.showAddDialog
        opacity: visible ? 1.0 : 0.0
        Behavior on opacity { NumberAnimation { duration: 180 } }

        // Backdrop
        Rectangle {
            anchors.fill: parent
            color: "#B0030712"

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    addErrorText.text = ""
                    root.showAddDialog = false
                }
            }
        }

        // Modal Card — Explicit width and height with responsive limits
        Rectangle {
            id: addArtistCard
            width: Math.min(500, Math.max(280, root.width - 32))
            height: Math.min(root.height - 40, modalContentCol.implicitHeight + 44)
            anchors.centerIn: parent
            radius: 12
            color: "#0D111E"
            border.color: "#2D3748"
            border.width: 1
            clip: true
            scale: root.showAddDialog ? 1.0 : 0.94
            Behavior on scale { NumberAnimation { duration: 200; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }

            // Subtle glowing top accent line
            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 2
                radius: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: "#8B5CF6" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }

            // Scrollable contents to ensure it shrinks and scrolls on any window height
            SmoothFlickable {
                id: modalFlickable
                anchors.fill: parent
                anchors.margins: 18
                contentWidth: width
                contentHeight: modalContentCol.implicitHeight
                clip: true

                ColumnLayout {
                    id: modalContentCol
                    width: modalFlickable.width
                    spacing: 13

                    // Header
                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "➕ " + root.tr("watchlist_add_title", "Add Artist to Watchlist")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#E2E8F0"
                        }

                        Item { Layout.fillWidth: true }

                        Text {
                            text: "✕"
                            font.pixelSize: 14
                            color: closeAddMouse.containsMouse ? "#E2E8F0" : "#64748B"
                            MouseArea {
                                id: closeAddMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    addErrorText.text = ""
                                    root.showAddDialog = false
                                }
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.tr("watchlist_add_desc", "Track an artist to automatically check for future posts without downloading their full past catalog.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        wrapMode: Text.WordWrap
                        lineHeight: 1.4
                    }

                    // URL Input Label
                    Text {
                        text: root.tr("watchlist_add_url_label", "Artist URL (Kemono / Coomer):")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#CBD5E1"
                    }

                    // URL Input Box
                    Rectangle {
                        Layout.fillWidth: true
                        height: 36
                        radius: 6
                        color: "#080B14"
                        border.color: addUrlInput.activeFocus ? "#8B5CF6" : "#242C40"
                        border.width: 1

                        TextInput {
                            id: addUrlInput
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#E2E8F0"
                            selectByMouse: true

                            Text {
                                text: "https://kemono.cr/patreon/user/12345678"
                                font: parent.font
                                color: "#475569"
                                visible: !addUrlInput.text && !addUrlInput.activeFocus
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }

                    // Download Folder Label
                    Text {
                        text: root.tr("watchlist_add_folder_label", "Download Folder (Optional):")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#CBD5E1"
                    }

                    // Download Folder Input Box
                    Rectangle {
                        Layout.fillWidth: true
                        height: 36
                        radius: 6
                        color: "#080B14"
                        border.color: addFolderInput.activeFocus ? "#8B5CF6" : "#242C40"
                        border.width: 1

                        TextInput {
                            id: addFolderInput
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#E2E8F0"
                            selectByMouse: true

                            Text {
                                text: root.tr("watchlist_add_folder_ph", "Leave empty for default download folder")
                                font: parent.font
                                color: "#475569"
                                visible: !addFolderInput.text && !addFolderInput.activeFocus
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }

                    // Error text if any
                    Text {
                        id: addErrorText
                        Layout.fillWidth: true
                        text: ""
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#F87171"
                        visible: text.length > 0
                        wrapMode: Text.WordWrap
                    }

                    // Spacing before buttons
                    Item { Layout.preferredHeight: 4 }

                    // Action buttons — responsive, shrink and fill width together with modal
                    RowLayout {
                        Layout.fillWidth: true
                        width: parent.width
                        spacing: 10

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.minimumWidth: 80
                            height: 34
                            radius: 6
                            color: cancelAddMouse.containsMouse ? "#1E2536" : "#131826"
                            border.color: "#2E3A52"
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                width: parent.width - 16
                                horizontalAlignment: Text.AlignHCenter
                                text: root.tr("common_cancel", "Cancel")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: "#94A3B8"
                                elide: Text.ElideRight
                            }

                            MouseArea {
                                id: cancelAddMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    addErrorText.text = ""
                                    root.showAddDialog = false
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.minimumWidth: 100
                            height: 34
                            radius: 6
                            color: confirmAddMouse.containsMouse ? "#6D28D9" : "#5B21B6"
                            border.color: "#7C3AED"
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                width: parent.width - 16
                                horizontalAlignment: Text.AlignHCenter
                                text: root.tr("watchlist_add_confirm", "Add to Watchlist")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                                elide: Text.ElideRight
                            }

                            MouseArea {
                                id: confirmAddMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var url = addUrlInput.text.trim()
                                    if (!url) {
                                        addErrorText.text = root.tr("watchlist_error_no_url", "Please enter an artist URL")
                                        return
                                    }
                                    addErrorText.text = ""
                                    var customDir = addFolderInput.text.trim()
                                    var ok = false
                                    if (bridge) {
                                        ok = bridge.addArtistToWatchlist(url, customDir)
                                    }
                                    if (ok) {
                                        addUrlInput.text = ""
                                        addFolderInput.text = ""
                                        root.showAddDialog = false
                                        resultToast.showCustom("✅ Added creator to watchlist!")
                                    } else {
                                        addErrorText.text = root.tr("watchlist_error_invalid_url", "Invalid URL or creator could not be resolved.")
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ── Toast notification ────────────────────────────────────────────────────
    Item {
        id: resultToast
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 24
        width: toastText.implicitWidth + 40
        height: 40
        visible: opacity > 0
        opacity: 0

        function show(n) {
            toastText.text = "✅ " + n + " new " + (n === 1 ? "post" : "posts") + " found!"
            opacity = 1.0
            toastTimer.restart()
        }

        function showCustom(msg) {
            toastText.text = msg
            opacity = 1.0
            toastTimer.restart()
        }

        Behavior on opacity { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }

        Timer {
            id: toastTimer
            interval: 4000
            onTriggered: resultToast.opacity = 0
        }

        Rectangle {
            anchors.fill: parent
            radius: 20
            color: "#0D2A1A"
            border.color: "#10B981"
            border.width: 1

            Text {
                id: toastText
                anchors.centerIn: parent
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: "#34D399"
            }
        }
    }
}
