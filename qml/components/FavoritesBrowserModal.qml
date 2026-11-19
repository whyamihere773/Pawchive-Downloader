import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "favorites"

Item {
    id: modalRoot

    property var bridge: null
    property bool isOpen: false
    property var allArtists: []
    property var filteredArtists: []
    property string searchFilter: ""

    // Download Options Dialog State
    property bool downloadDialogVisible: false
    property bool downloadDialogIsBatch: false
    property string downloadDialogArtistId: ""
    property string downloadDialogService: ""
    property string downloadDialogArtistName: ""
    property string downloadDialogLocation: ""
    property string downloadDialogStartPage: "1"
    property string downloadDialogEndPage: ""
    property int downloadDialogNewPostCount: 0
    property string downloadDialogLastPostDate: ""

    // Artist Browsing / Loading State
    property bool isBrowsingArtist: false
    property string browsingArtistId: ""
    property string browsingArtistName: ""
    property string browsingArtistService: ""
    property string browsingArtistAvatar: ""
    property string browsingArtistProvider: ""
    property string browsingArtistDomain: ""
    property string browsingArtistUrl: ""

    readonly property int browsePage: modalRoot.bridge ? modalRoot.bridge.postSelectionProgressPage : 0
    readonly property int browseCount: modalRoot.bridge ? modalRoot.bridge.postSelectionProgressCount : 0
    readonly property int browseTotal: modalRoot.bridge ? modalRoot.bridge.postSelectionProgressTotal : 0
    readonly property string browseStatus: modalRoot.bridge ? modalRoot.bridge.postSelectionProgressStatus : ""
    readonly property real browseProgressFraction: {
        if (browseTotal > 0 && browseCount > 0) {
            return Math.min(1.0, Math.max(0.0, browseCount / browseTotal))
        }
        return 0.0
    }

    readonly property int totalNewPosts: {
        var count = 0
        for (var i = 0; i < allArtists.length; i++) {
            count += (allArtists[i].newPostCount || 0)
        }
        return count
    }

    signal browseArtistPosts(string userId, string service, string creatorName)

    anchors.fill: parent
    visible: opacity > 0.001
    opacity: isOpen ? 1.0 : 0.0
    z: 9998
    focus: true

    Behavior on opacity {
        NumberAnimation {
            duration: modalRoot.isOpen ? 220 : 160
            easing.type: Easing.OutCubic
        }
    }

    Keys.onEscapePressed: function(event) {
        if (modalRoot.isBrowsingArtist) {
            modalRoot.cancelBrowsingArtist()
            event.accepted = true
        } else if (modalRoot.downloadDialogVisible) {
            modalRoot.downloadDialogVisible = false
            event.accepted = true
        } else if (modalRoot.isOpen) {
            modalRoot.closeModal()
            event.accepted = true
        }
    }

    function tr(key, fallback) {
        if (typeof Lang === "undefined" || !Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    function openModal(artists) {
        allArtists = artists || []
        searchFilter = ""
        downloadDialogVisible = false
        isBrowsingArtist = false
        if (searchInput) searchInput.text = ""
        updateFilteredArtists()
        isOpen = true
    }

    function closeModal() {
        if (isBrowsingArtist) {
            cancelBrowsingArtist()
        }
        downloadDialogVisible = false
        isOpen = false
    }

    function providerDisplayName(artistOrProvider) {
        if (!artistOrProvider) return "Pawchive"
        var p = ""
        var d = ""
        if (typeof artistOrProvider === "string") {
            p = artistOrProvider.toLowerCase().trim()
            d = p
        } else {
            p = (artistOrProvider.provider || "").toLowerCase().trim()
            d = (artistOrProvider.domain || "").toLowerCase()
        }
        if (p === "cumst" || d.indexOf("cum.st") !== -1 || d.indexOf("cumst") !== -1) return "cum.st"
        if (p === "kemono" || d.indexOf("kemono") !== -1) return "Kemono"
        if (p === "coomer" || d.indexOf("coomer") !== -1) return "Coomer"
        return "Pawchive"
    }

    function startBrowsingArtist(artist) {
        if (!artist || !modalRoot.bridge) return
        var uid = artist.userId || artist.id || ""
        var svc = artist.service || ""
        var name = artist.name || uid || "Artist"
        browsingArtistId = uid
        browsingArtistName = name
        browsingArtistService = svc
        browsingArtistAvatar = artist.avatar || ""
        browsingArtistProvider = artist.provider || "pawchive"
        browsingArtistDomain = artist.domain || ""
        browsingArtistUrl = artist.url || ""
        isBrowsingArtist = true

        modalRoot.browseArtistPosts(uid, svc, name)
        if (typeof modalRoot.bridge.fetchArtistPostsForSelection === "function") {
            modalRoot.bridge.fetchArtistPostsForSelection(uid, svc, name, browsingArtistUrl)
        }
    }

    function cancelBrowsingArtist() {
        isBrowsingArtist = false
        if (modalRoot.bridge && modalRoot.bridge.cancelPostSelection) {
            modalRoot.bridge.cancelPostSelection()
        }
    }

    function openDownloadDialogForArtist(artist) {
        downloadDialogIsBatch = false
        downloadDialogArtistId = artist.userId || artist.id || ""
        downloadDialogService = artist.service || ""
        downloadDialogArtistName = artist.name || artist.userId || "Artist"
        downloadDialogNewPostCount = artist.newPostCount || 0
        downloadDialogLastPostDate = artist.lastPostDate || ""
        var defaultLoc = ""
        if (modalRoot.bridge && modalRoot.bridge.getArtistDownloadDir) {
            defaultLoc = modalRoot.bridge.getArtistDownloadDir(downloadDialogArtistId, downloadDialogService) || modalRoot.bridge.downloadDir || ""
        } else if (modalRoot.bridge) {
            defaultLoc = modalRoot.bridge.downloadDir || ""
        }
        downloadDialogLocation = defaultLoc
        downloadDialogStartPage = "1"
        downloadDialogEndPage = ""
        if (downloadOptionsOverlay.startPageInput) downloadOptionsOverlay.startPageInput.text = "1"
        if (downloadOptionsOverlay.endPageInput) downloadOptionsOverlay.endPageInput.text = ""
        if (downloadOptionsOverlay.locInput) downloadOptionsOverlay.locInput.text = defaultLoc
        downloadDialogVisible = true
    }

    function openDownloadDialogForAll() {
        downloadDialogIsBatch = true
        downloadDialogArtistId = ""
        downloadDialogService = ""
        downloadDialogArtistName = ""
        downloadDialogNewPostCount = modalRoot.totalNewPosts
        downloadDialogLastPostDate = ""
        var defaultLoc = modalRoot.bridge ? (modalRoot.bridge.downloadDir || "") : ""
        downloadDialogLocation = defaultLoc
        downloadDialogStartPage = "1"
        downloadDialogEndPage = ""
        if (downloadOptionsOverlay.startPageInput) downloadOptionsOverlay.startPageInput.text = "1"
        if (downloadOptionsOverlay.endPageInput) downloadOptionsOverlay.endPageInput.text = ""
        if (downloadOptionsOverlay.locInput) downloadOptionsOverlay.locInput.text = defaultLoc
        downloadDialogVisible = true
    }

    function confirmDownload() {
        var startP = parseInt(downloadDialogStartPage) || 1
        if (startP < 1) startP = 1
        var endPStr = (downloadDialogEndPage || "").trim()
        var endP = endPStr === "" ? 999999 : (parseInt(endPStr) || 999999)
        if (endP < startP) endP = startP
        var loc = (downloadDialogLocation || "").trim()

        if (downloadDialogIsBatch) {
            if (modalRoot.bridge) {
                modalRoot.bridge.downloadAllFavoriteArtists(startP, endP, loc)
                modalRoot.closeModal()
            }
        } else {
            if (modalRoot.bridge) {
                modalRoot.bridge.downloadFavoriteArtist(downloadDialogArtistId, downloadDialogService, startP, endP, loc)
            }
        }
        downloadDialogVisible = false
    }

    function browseDownloadFolder() {
        if (modalRoot.bridge && modalRoot.bridge.browseFolderDialog) {
            var chosen = modalRoot.bridge.browseFolderDialog(
                modalRoot.tr("dlg_select_dl_dir", "Select Download Directory"),
                downloadDialogLocation
            )
            if (chosen && chosen.length > 0) {
                downloadDialogLocation = chosen
                if (downloadOptionsOverlay.locInput) downloadOptionsOverlay.locInput.text = chosen
            }
        }
    }

    function updateFilteredArtists() {
        var query = (searchFilter || "").trim().toLowerCase()
        if (!query) {
            filteredArtists = allArtists
            return
        }
        var filtered = []
        for (var i = 0; i < allArtists.length; i++) {
            var a = allArtists[i]
            var name = (a.name || "").toLowerCase()
            var svc = (a.service || "").toLowerCase()
            var uid = (a.userId || a.id || "").toLowerCase()
            if (name.indexOf(query) !== -1 || svc.indexOf(query) !== -1 || uid.indexOf(query) !== -1) {
                filtered.push(a)
            }
        }
        filteredArtists = filtered
    }

    // Semi-transparent backdrop overlay
    Rectangle {
        anchors.fill: parent
        color: "#05070B"
        opacity: 0.78

        MouseArea {
            anchors.fill: parent
            // Prevents outside clicks from dismissing the modal
        }

        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: function(event) { event.accepted = true }
        }
    }

    // Main Modal Dialog Card
    Rectangle {
        id: dialogCard
        width: Math.min(1040, modalRoot.width - 48)
        height: Math.min(740, modalRoot.height - 48)
        anchors.centerIn: parent
        radius: 12
        color: "#0F141F"
        border.color: "#242E44"
        border.width: 1
        clip: true

        // Soft outer shadow / glow
        Rectangle {
            anchors.fill: parent
            anchors.margins: -1
            radius: 13
            color: "transparent"
            border.color: Qt.rgba(245/255, 158/255, 11/255, 0.15)
            border.width: 1
            z: -1
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 14

            // ── Modal Header Bar ──────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                // Icon & Title
                Row {
                    spacing: 8
                    Layout.alignment: Qt.AlignVCenter

                    Text {
                        text: "⭐"
                        font.pixelSize: 18
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Text {
                        text: modalRoot.tr("fav_modal_title", "Favorite Artists")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 16
                        font.bold: true
                        color: "#F8FAFC"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                // Total count badge
                Rectangle {
                    implicitWidth: countText.implicitWidth + 16
                    implicitHeight: 24
                    radius: 12
                    color: "#2A2008"
                    border.color: "#F59E0B"
                    border.width: 1
                    Layout.alignment: Qt.AlignVCenter

                    Text {
                        id: countText
                        anchors.centerIn: parent
                        text: modalRoot.filteredArtists.length + " " + modalRoot.tr("lbl_artists", "Artists")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#FCD34D"
                    }
                }

                Item { Layout.fillWidth: true }

                // Search Bar
                Rectangle {
                    Layout.preferredWidth: 240
                    Layout.preferredHeight: 32
                    radius: 7
                    color: searchInput.activeFocus ? "#0B0D12" : "#182030"
                    border.color: searchInput.activeFocus ? "#38BDF8" : (favSearchBoxMouse.containsMouse ? "#475569" : "#2B354D")
                    border.width: searchInput.activeFocus ? 1.5 : 1

                    TextBarContextArea {
                        id: favSearchBoxMouse
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
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#F1F5F9"
                            selectionColor: "#0284C7"
                            selectedTextColor: "#FFFFFF"
                            selectByMouse: true
                            clip: true

                            TextBarContextArea {}

                            Text {
                                text: modalRoot.tr("ph_search_artists", "Search artists…")
                                font: parent.font
                                color: "#64748B"
                                visible: !parent.text && !parent.activeFocus
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight
                            }

                            onTextChanged: {
                                modalRoot.searchFilter = text
                                modalRoot.updateFilteredArtists()
                            }
                        }

                        // Clear search
                        Rectangle {
                            visible: searchInput.text.length > 0
                            width: 16; height: 16; radius: 8
                            color: clearSearchMouse.containsMouse ? "#374151" : "transparent"
                            Text { anchors.centerIn: parent; text: "×"; font.bold: true; font.pixelSize: 11; color: "#94A3B8" }
                            MouseArea {
                                id: clearSearchMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: searchInput.text = ""
                            }
                        }
                    }
                }

                // Download All Updates Button
                Rectangle {
                    Layout.preferredHeight: 32
                    Layout.preferredWidth: dlAllRow.implicitWidth + 24
                    radius: 7
                    color: dlAllMouse.containsMouse ? "#D97706" : "#B45309"
                    border.color: "#F59E0B"
                    border.width: 1

                    Row {
                        id: dlAllRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "⬇️"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: modalRoot.totalNewPosts > 0
                                  ? (modalRoot.tr("btn_download_all_favorites", "Sync All Updates") + " (" + modalRoot.totalNewPosts + " new)")
                                  : modalRoot.tr("btn_download_all_favorites", "Sync All Updates")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: "#FFF"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: dlAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            modalRoot.openDownloadDialogForAll()
                        }
                    }
                }

                // Close Button
                Rectangle {
                    width: 30; height: 30; radius: 6
                    color: closeBtnMouse.containsMouse ? "#2A3449" : "#1A2234"
                    border.color: "#2D374D"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 13
                        font.bold: true
                        color: closeBtnMouse.containsMouse ? "#F87171" : "#94A3B8"
                    }

                    MouseArea {
                        id: closeBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.closeModal()
                    }
                }
            }

            // Divider
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1E273A"
            }

            // ── Grid Content Area ─────────────────────────────────────────
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                // Loading Indicator
                Column {
                    anchors.centerIn: parent
                    spacing: 12
                    visible: modalRoot.bridge ? modalRoot.bridge.favoriteArtistsLoading : false

                    Text {
                        text: "⏳"
                        font.pixelSize: 28
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Text {
                        text: modalRoot.tr("msg_loading_favorite_artists", "Fetching favorite creators…")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 13
                        color: "#94A3B8"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                // Empty State
                Column {
                    anchors.centerIn: parent
                    spacing: 10
                    visible: (!modalRoot.bridge || !modalRoot.bridge.favoriteArtistsLoading) && modalRoot.filteredArtists.length === 0

                    Text {
                        text: modalRoot.searchFilter.length > 0 ? "🔍" : "⭐"
                        font.pixelSize: 32
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Text {
                        text: modalRoot.searchFilter.length > 0
                              ? modalRoot.tr("msg_no_artists_matched", "No favorite creators matched your search.")
                              : modalRoot.tr("msg_no_favorite_artists", "No favorite artists found on your accounts.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 14
                        font.weight: 600
                        color: "#E2E8F0"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Text {
                        text: modalRoot.tr("hint_favorite_sync", "Follow artists on supported platforms with your account, then click Sync Favorites to see them here.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#64748B"
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: modalRoot.searchFilter.length === 0
                    }
                }

                // Artists Grid ScrollView
                ScrollView {
                    id: gridScroll
                    anchors.fill: parent
                    clip: true
                    visible: (!modalRoot.bridge || !modalRoot.bridge.favoriteArtistsLoading) && modalRoot.filteredArtists.length > 0

                    Flow {
                        id: artistsFlow
                        width: gridScroll.width - 12
                        spacing: 14

                        Repeater {
                            model: modalRoot.filteredArtists

                            delegate: Rectangle {
                                id: artistCard
                                width: Math.max(220, (artistsFlow.width - (Math.floor(artistsFlow.width / 234) - 1) * 14) / Math.floor(artistsFlow.width / 234))
                                height: 168
                                radius: 10
                                color: cardMouse.containsMouse ? "#182133" : "#131A29"
                                border.color: cardMouse.containsMouse ? "#F59E0B" : "#242E44"
                                border.width: 1

                                Behavior on color { ColorAnimation { duration: 120 } }
                                Behavior on border.color { ColorAnimation { duration: 120 } }

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 8

                                    // Top Row: Avatar + Name + Service + Star Badge
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 10

                                        // Avatar Container
                                        Rectangle {
                                            width: 44; height: 44; radius: 8
                                            color: "#1E273A"
                                            border.color: "#334155"
                                            border.width: 1
                                            clip: true

                                            Image {
                                                anchors.fill: parent
                                                source: modelData.avatar || ""
                                                fillMode: Image.PreserveAspectCrop
                                                visible: modelData.avatar && status === Image.Ready
                                            }

                                            Text {
                                                anchors.centerIn: parent
                                                text: (modelData.name && modelData.name.length > 0) ? modelData.name.charAt(0).toUpperCase() : "?"
                                                font.pixelSize: 18
                                                font.bold: true
                                                color: "#94A3B8"
                                                visible: !modelData.avatar || !parent.children[0].visible
                                            }
                                        }

                                        // Name and Service Badge
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 3

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 4

                                                Text {
                                                    text: modelData.name || modelData.userId || "Artist"
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 13
                                                    font.weight: 600
                                                    color: "#F1F5F9"
                                                    Layout.fillWidth: true
                                                    elide: Text.ElideRight
                                                }

                                                Text {
                                                    text: "⭐"
                                                    font.pixelSize: 12
                                                    ToolTip.visible: starMouse.containsMouse
                                                    ToolTip.text: modalRoot.tr("tip_favorited_platform", "Favorited on %1 & Watchlist").replace("%1", modalRoot.providerDisplayName(modelData))

                                                    MouseArea {
                                                        id: starMouse
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                    }
                                                }
                                            }

                                            // Provider & Service Badges
                                            RowLayout {
                                                spacing: 6
                                                Layout.fillWidth: true

                                                ProviderBadge {
                                                    provider: modelData.provider || "pawchive"
                                                    domain: modelData.domain || ""
                                                    badgeHeight: 18
                                                }

                                                ServiceBadge {
                                                    service: modelData.service || "patreon"
                                                    badgeHeight: 18
                                                }

                                                Item { Layout.fillWidth: true }
                                            }
                                        }
                                    }

                                    // Status info row
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 6

                                        Rectangle {
                                            implicitWidth: statusText.implicitWidth + 12
                                            implicitHeight: 20
                                            radius: 5
                                            color: (modelData.newPostCount && modelData.newPostCount > 0)
                                                   ? "#2E1E05"
                                                   : (modelData.status === "Synced" ? "#064E3B" : "#1E293B")
                                            border.color: (modelData.newPostCount && modelData.newPostCount > 0)
                                                   ? "#F59E0B"
                                                   : (modelData.status === "Synced" ? "#10B981" : "#334155")
                                            border.width: 1

                                            Text {
                                                id: statusText
                                                anchors.centerIn: parent
                                                text: {
                                                    if (modelData.newPostCount && modelData.newPostCount > 0) {
                                                        return "🔔 " + modelData.newPostCount + " new post" + (modelData.newPostCount > 1 ? "s" : "") + (modelData.lastPostDate ? " since " + modelData.lastPostDate : "")
                                                    } else if (modelData.status === "Synced") {
                                                        return modelData.lastPostDate ? "✓ Synced (" + modelData.lastPostDate + ")" : "✓ Synced"
                                                    } else {
                                                        return "✦ Not downloaded"
                                                    }
                                                }
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 10
                                                font.weight: 600
                                                color: (modelData.newPostCount && modelData.newPostCount > 0)
                                                       ? "#FCD34D"
                                                       : (modelData.status === "Synced" ? "#A7F3D0" : "#94A3B8")
                                            }
                                        }

                                        Item { Layout.fillWidth: true }
                                    }

                                    Item { Layout.fillHeight: true }

                                    // Actions Bottom Row
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8

                                        // Browse Posts Button
                                        Rectangle {
                                            Layout.fillWidth: true
                                            height: 28
                                            radius: 6
                                            color: browseBtnMouse.containsMouse ? "#2A364F" : "#1A2234"
                                            border.color: browseBtnMouse.containsMouse ? "#38BDF8" : "#2E3B56"
                                            border.width: 1

                                            Row {
                                                anchors.centerIn: parent
                                                spacing: 5
                                                Text { text: "👁️"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                                                Text {
                                                    text: modalRoot.tr("btn_browse_posts", "Browse Posts")
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 11
                                                    font.weight: 600
                                                    color: "#E2E8F0"
                                                    anchors.verticalCenter: parent.verticalCenter
                                                }
                                            }

                                            MouseArea {
                                                id: browseBtnMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    modalRoot.startBrowsingArtist(modelData)
                                                }
                                            }
                                        }

                                        // Download Button
                                        Rectangle {
                                            width: 32
                                            height: 28
                                            radius: 6
                                            color: dlBtnMouse.containsMouse ? "#D97706" : "#242010"
                                            border.color: "#F59E0B"
                                            border.width: 1
                                            ToolTip.visible: dlBtnMouse.containsMouse
                                            ToolTip.text: "Download updates for this creator"

                                            Text {
                                                anchors.centerIn: parent
                                                text: "⬇️"
                                                font.pixelSize: 12
                                            }

                                            MouseArea {
                                                id: dlBtnMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    modalRoot.openDownloadDialogForArtist(modelData)
                                                }
                                            }
                                        }
                                    }
                                }

                                MouseArea {
                                    id: cardMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    z: -1
                                    onClicked: {
                                        modalRoot.startBrowsingArtist(modelData)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ── Download Options Overlay Dialog ──────────────────────────────────
    FavoritesDownloadDialog {
        id: downloadOptionsOverlay
        modal: modalRoot
    }

    // ── Fetching Posts In-Modal Loading Screen ────────────────────────────
    FavoritesFetchingOverlay {
        id: fetchingPostsOverlay
        modal: modalRoot
    }
}

