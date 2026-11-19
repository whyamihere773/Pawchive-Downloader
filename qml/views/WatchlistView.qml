import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "watchlist"

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
    property int  checkDone: 0      // progress of "Check All"
    property int  checkTotal: 0
    property int  lastNewCount: -1  // -1 = never checked
    property var  checkingArtists: ({})
    property string searchText: ""
    property string activeServiceFilter: "all"
    property bool showAddDialog: false
    property var  expandedArtists: ({})
    property string _addRequest: ""     // set while "Add to Watchlist" is looking the creator up

    Connections {
        target: bridge
        function onAsyncResultReady(requestId, result) {
            if (requestId !== root._addRequest) return
            root._addRequest = ""
            if (result === true) {
                addArtistModal.clearInputs()
                root.showAddDialog = false
                resultToast.showCustom("✅ Added creator to watchlist!")
            } else {
                addArtistModal.setError(root.tr("watchlist_error_invalid_url", "Invalid URL or creator could not be resolved."))
            }
        }
        function onWatchlistCheckStarted() { root.isChecking = true; root.checkDone = 0; root.checkTotal = 0 }
        function onWatchlistCheckProgress(done, total) { root.checkDone = done; root.checkTotal = total }
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
        function onWatchlistFolderChangeRequested(uid, svc, name, oldDirs, newDir, count, sizeText) {
            folderChangeModal.open(uid, svc, name, oldDirs, newDir, count, sizeText)
        }
        function onWatchlistFolderChanged(uid, svc, message) {
            resultToast.showCustom(message !== "" ? "⚠️ " + message
                                                  : "✅ " + root.tr("folder_change_done", "Download folder changed"))
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


    function openSettingsModal(uid, svc) {
        watchlistSettingsModal.open(uid, svc)
    }

    function openRedownloadModal(uid, svc) {
        watchlistRedownloadModal.open(uid, svc)
    }

    // ── Layout ─────────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        WatchlistHeader {
            view: root
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
                    color: searchInput.activeFocus ? "#0B0D12" : "#0F1422"
                    border.color: searchInput.activeFocus ? "#38BDF8" : (searchMouse.containsMouse ? "#475569" : "#1E2638")
                    border.width: searchInput.activeFocus ? 1.5 : 1

                    Behavior on border.color { ColorAnimation { duration: 150 } }

                    TextBarContextArea {
                        id: searchMouse
                        target: searchInput
                        focusOnLeftClick: true
                    }

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
                            Layout.fillHeight: true
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 11
                            color: "#E2E8F0"
                            selectionColor: "#0284C7"
                            selectedTextColor: "#FFFFFF"
                            selectByMouse: true
                            clip: true

                            TextBarContextArea {}

                            Text {
                                text: root.tr("watchlist_search_placeholder", "Search creator or ID…")
                                font: parent.font
                                color: "#475569"
                                visible: !searchInput.text && !searchInput.activeFocus
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight
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
                                onClicked: {
                                    searchInput.text = ""
                                    searchInput.forceActiveFocus()
                                }
                            }
                        }
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
                                { id: "favorites",     label: "⭐ " + root.tr("filter_favorites", "Favorites") },
                                { id: "synced",        label: "💾 " + root.tr("filter_on_disk", "On Disk") },
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
                                       ? (modelData.id === "updates" ? "#0C2D3A" : (modelData.id === "favorites" ? "#2A2008" : (modelData.id === "synced" ? "#064E3B" : "#1E1B3D")))
                                       : (chipMouse.containsMouse ? "#161D2E" : "#0D111A")
                                border.color: isSelected 
                                              ? (modelData.id === "updates" ? "#22D3EE" : (modelData.id === "favorites" ? "#F59E0B" : (modelData.id === "synced" ? "#10B981" : "#8B5CF6")))
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
                                           ? (modelData.id === "updates" ? "#A5F3FC" : (modelData.id === "favorites" ? "#FCD34D" : (modelData.id === "synced" ? "#6EE7B7" : "#DDD6FE")))
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

            WatchlistEntryList {
                view: root
            }
        }
    }


    WatchlistAddArtistModal {
        id: addArtistModal
        view: root
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

    FolderChangeModal {
        id: folderChangeModal
        objectName: "folderChangeModal"
        bridge: root.bridge
    }

    WatchlistSettingsModal {
        id: watchlistSettingsModal
        objectName: "watchlistSettingsModal"
        bridge: root.bridge
        onSettingsSaved: function(msg) {
            resultToast.showCustom("\u2705 " + msg)
        }
        onRedownloadRequested: function(uid, svc) {
            watchlistRedownloadModal.open(uid, svc)
        }
    }

    WatchlistRedownloadModal {
        id: watchlistRedownloadModal
        objectName: "watchlistRedownloadModal"
        bridge: root.bridge
        onOpenSettingsRequested: function(uid, svc) {
            watchlistSettingsModal.open(uid, svc)
        }
    }
}
