import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

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
        if (startPageInput) startPageInput.text = "1"
        if (endPageInput) endPageInput.text = ""
        if (locInput) locInput.text = defaultLoc
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
        if (startPageInput) startPageInput.text = "1"
        if (endPageInput) endPageInput.text = ""
        if (locInput) locInput.text = defaultLoc
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
                if (locInput) locInput.text = chosen
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
                    color: "#182030"
                    border.color: searchInput.activeFocus ? "#38BDF8" : "#2B354D"
                    border.width: 1

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
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#F1F5F9"
                            selectByMouse: true
                            clip: true

                            Text {
                                text: modalRoot.tr("ph_search_artists", "Search artists…")
                                font: parent.font
                                color: "#64748B"
                                visible: !parent.text && !parent.activeFocus
                                anchors.verticalCenter: parent.verticalCenter
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
    Rectangle {
        id: downloadOptionsOverlay
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.70)
        visible: modalRoot.downloadDialogVisible
        z: 1000

        MouseArea {
            anchors.fill: parent
            // Absorb clicks so clicking backdrop inside the dialog doesn't close accidentally
        }

        Rectangle {
            id: downloadOptionsCard
            width: Math.min(560, modalRoot.width - 32)
            height: Math.min(530, modalRoot.height - 32)
            anchors.centerIn: parent
            radius: 12
            color: "#111827"
            border.color: "#374151"
            border.width: 1
            clip: true

            // Glowing amber accent border
            Rectangle {
                anchors.fill: parent
                anchors.margins: -1
                radius: 13
                color: "transparent"
                border.color: Qt.rgba(245/255, 158/255, 11/255, 0.3)
                border.width: 1
                z: -1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 12

                // Header row
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: "⬇️"
                        font.pixelSize: 20
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: modalRoot.downloadDialogIsBatch
                                  ? modalRoot.tr("title_dl_all_favorites", "Sync All Favorite Artists")
                                  : (modalRoot.tr("title_dl_artist", "Download Artist") + " — " + modalRoot.downloadDialogArtistName)
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 15
                            font.bold: true
                            color: "#F8FAFC"
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }

                        Text {
                            text: modalRoot.downloadDialogIsBatch
                                  ? modalRoot.tr("hint_dl_all_favorites", "Select page range and destination folder for all favorited creators.")
                                  : ((modalRoot.downloadDialogService ? modalRoot.downloadDialogService.toUpperCase() + " • " : "") + "ID: " + modalRoot.downloadDialogArtistId)
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                    }

                    // Dialog Close ✕
                    Rectangle {
                        width: 28; height: 28; radius: 6
                        color: dlCloseMouse.containsMouse ? "#374151" : "#1F2937"
                        Text { anchors.centerIn: parent; text: "✕"; font.bold: true; font.pixelSize: 12; color: "#94A3B8" }
                        MouseArea {
                            id: dlCloseMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: modalRoot.downloadDialogVisible = false
                        }
                    }
                }

                // Divider
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: "#1F2937"
                }

                // Update Status Callout Box
                Rectangle {
                    Layout.fillWidth: true
                    radius: 7
                    color: modalRoot.downloadDialogIsBatch
                           ? "#1A2234"
                           : (modalRoot.downloadDialogNewPostCount > 0 ? "#2E1E05" : (modalRoot.downloadDialogLastPostDate ? "#064E3B" : "#1A2234"))
                    border.color: modalRoot.downloadDialogIsBatch
                           ? "#2E3B56"
                           : (modalRoot.downloadDialogNewPostCount > 0 ? "#F59E0B" : (modalRoot.downloadDialogLastPostDate ? "#10B981" : "#2E3B56"))
                    border.width: 1
                    implicitHeight: statusCalloutRow.implicitHeight + 14

                    RowLayout {
                        id: statusCalloutRow
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 8

                        Text {
                            text: modalRoot.downloadDialogIsBatch
                                  ? (modalRoot.totalNewPosts > 0 ? "🔔" : "ℹ️")
                                  : (modalRoot.downloadDialogNewPostCount > 0 ? "🔔" : (modalRoot.downloadDialogLastPostDate ? "✓" : "✦"))
                            font.pixelSize: 14
                        }

                        Text {
                            Layout.fillWidth: true
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: modalRoot.downloadDialogIsBatch
                                   ? (modalRoot.totalNewPosts > 0 ? "#FCD34D" : "#94A3B8")
                                   : (modalRoot.downloadDialogNewPostCount > 0 ? "#FCD34D" : (modalRoot.downloadDialogLastPostDate ? "#A7F3D0" : "#94A3B8"))
                            wrapMode: Text.WordWrap
                            text: {
                                if (modalRoot.downloadDialogIsBatch) {
                                    if (modalRoot.totalNewPosts > 0) {
                                        return modalRoot.totalNewPosts + " total new post" + (modalRoot.totalNewPosts > 1 ? "s" : "") + " detected across your favorite creators. Incremental sync will download only missing posts."
                                    }
                                    return modalRoot.tr("msg_batch_sync_desc", "Incremental sync will check all favorited creators and download new posts published since their last sync.")
                                } else if (modalRoot.downloadDialogNewPostCount > 0) {
                                    return modalRoot.downloadDialogNewPostCount + " new post" + (modalRoot.downloadDialogNewPostCount > 1 ? "s" : "") + " available since last download (" + (modalRoot.downloadDialogLastPostDate || "previous sync") + ")."
                                } else if (modalRoot.downloadDialogLastPostDate) {
                                    return "Artist is up to date with last download (" + modalRoot.downloadDialogLastPostDate + "). Downloading again will check for any newly added files."
                                } else {
                                    return "First-time download for this creator. All posts will be downloaded."
                                }
                            }
                        }
                    }
                }

                // Page Range Configuration
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: modalRoot.tr("lbl_page_range", "Page Range")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#E2E8F0"
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        // Start Page
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4

                            Text {
                                text: modalRoot.tr("lbl_start_page", "Start Page:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                height: 34
                                radius: 6
                                color: "#1F2937"
                                border.color: startPageInput.activeFocus ? "#F59E0B" : "#374151"
                                border.width: 1

                                TextInput {
                                    id: startPageInput
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    verticalAlignment: TextInput.AlignVCenter
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    color: "#F8FAFC"
                                    selectByMouse: true
                                    text: modalRoot.downloadDialogStartPage
                                    validator: IntValidator { bottom: 1; top: 99999 }
                                    onTextChanged: modalRoot.downloadDialogStartPage = text
                                }
                            }
                        }

                        // End Page
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4

                            Text {
                                text: modalRoot.tr("lbl_end_page", "End Page (optional):")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                height: 34
                                radius: 6
                                color: "#1F2937"
                                border.color: endPageInput.activeFocus ? "#F59E0B" : "#374151"
                                border.width: 1

                                TextInput {
                                    id: endPageInput
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    verticalAlignment: TextInput.AlignVCenter
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    color: "#F8FAFC"
                                    selectByMouse: true
                                    text: modalRoot.downloadDialogEndPage
                                    validator: IntValidator { bottom: 1; top: 99999 }
                                    onTextChanged: modalRoot.downloadDialogEndPage = text

                                    Text {
                                        text: modalRoot.tr("ph_all_pages", "All pages (blank)")
                                        font: parent.font
                                        color: "#64748B"
                                        visible: !parent.text && !parent.activeFocus
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                            }
                        }
                    }

                    Text {
                        text: modalRoot.tr("hint_page_range", "Leave End Page blank to check all pages until already-downloaded posts are reached.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#64748B"
                    }
                }

                // Download Location Configuration
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: modalRoot.tr("lbl_download_location", "Download Folder")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#E2E8F0"
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Rectangle {
                            Layout.fillWidth: true
                            height: 34
                            radius: 6
                            color: "#1F2937"
                            border.color: locInput.activeFocus ? "#F59E0B" : "#374151"
                            border.width: 1

                            TextInput {
                                id: locInput
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                verticalAlignment: TextInput.AlignVCenter
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                color: "#F8FAFC"
                                selectByMouse: true
                                text: modalRoot.downloadDialogLocation
                                onTextChanged: modalRoot.downloadDialogLocation = text

                                Text {
                                    text: modalRoot.tr("ph_default_location", "Default downloads folder")
                                    font: parent.font
                                    color: "#64748B"
                                    visible: !parent.text && !parent.activeFocus
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }

                        // Browse Button
                        Rectangle {
                            Layout.preferredWidth: browseBtnText.implicitWidth + 24
                            height: 34
                            radius: 6
                            color: browseLocMouse.containsMouse ? "#374151" : "#1F2937"
                            border.color: "#4B5563"
                            border.width: 1

                            Row {
                                id: browseBtnText
                                anchors.centerIn: parent
                                spacing: 5
                                Text { text: "📁"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                                Text {
                                    text: modalRoot.tr("btn_browse", "Browse…")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: "#E2E8F0"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            MouseArea {
                                id: browseLocMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: modalRoot.browseDownloadFolder()
                            }
                        }
                    }
                }

                // Location Destination Structure Explanation Box
                Rectangle {
                    Layout.fillWidth: true
                    radius: 7
                    color: "#162032"
                    border.color: "#28354E"
                    border.width: 1
                    implicitHeight: folderExplCol.implicitHeight + 14

                    ColumnLayout {
                        id: folderExplCol
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 4

                        RowLayout {
                            spacing: 6
                            Text { text: modalRoot.downloadDialogIsBatch ? "📁" : "📂"; font.pixelSize: 11 }
                            Text {
                                text: modalRoot.downloadDialogIsBatch
                                      ? modalRoot.tr("lbl_batch_destination_header", "Where will artists be saved?")
                                      : modalRoot.tr("lbl_single_destination_header", "Artist Save Destination:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.bold: true
                                color: "#38BDF8"
                            }
                        }

                        Text {
                            text: modalRoot.downloadDialogIsBatch
                                  ? modalRoot.tr("msg_batch_destination_expl", "Each artist will download into their own subfolder inside this directory:")
                                  : modalRoot.tr("msg_single_destination_expl", "Files for this creator will be saved directly into:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#CBD5E1"
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            text: {
                                var base = modalRoot.downloadDialogLocation || "Downloads"
                                if (modalRoot.downloadDialogIsBatch) {
                                    return base + "/<Artist Name> [<Service>]/"
                                } else {
                                    return base
                                }
                            }
                            font.family: "Consolas, 'Courier New', monospace"
                            font.pixelSize: 11
                            font.bold: true
                            color: "#FCD34D"
                            Layout.fillWidth: true
                            elide: Text.ElideMiddle
                        }

                        Text {
                            visible: modalRoot.downloadDialogIsBatch
                            text: modalRoot.tr("hint_existing_watchlist_folders", "💡 Existing Watchlist artists with custom folder locations will continue using their assigned folders.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#94A3B8"
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                // Actions Bottom Bar
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Item { Layout.fillWidth: true }

                    // Cancel Button
                    Rectangle {
                        implicitWidth: cancelBtnText.implicitWidth + 24
                        implicitHeight: 34
                        radius: 6
                        color: cancelDlMouse.containsMouse ? "#374151" : "#1F2937"
                        border.color: "#4B5563"
                        border.width: 1

                        Text {
                            id: cancelBtnText
                            anchors.centerIn: parent
                            text: modalRoot.tr("btn_cancel", "Cancel")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: "#94A3B8"
                        }

                        MouseArea {
                            id: cancelDlMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: modalRoot.downloadDialogVisible = false
                        }
                    }

                    // Start Download Confirm Button
                    Rectangle {
                        implicitWidth: startDlBtnRow.implicitWidth + 26
                        implicitHeight: 34
                        radius: 6
                        color: startDlMouse.containsMouse ? "#D97706" : "#B45309"
                        border.color: "#F59E0B"
                        border.width: 1

                        Row {
                            id: startDlBtnRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: "⬇️"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                text: modalRoot.downloadDialogIsBatch
                                      ? modalRoot.tr("btn_start_sync_all", "Start Sync All")
                                      : modalRoot.tr("btn_start_download", "Start Download")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: 700
                                color: "#FFFFFF"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            id: startDlMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: modalRoot.confirmDownload()
                        }
                    }
                }
            }
        }
    }

    // ── Fetching Posts In-Modal Loading Screen ────────────────────────────
    Rectangle {
        id: fetchingPostsOverlay
        anchors.fill: parent
        color: Qt.rgba(5/255, 7/255, 11/255, 0.82)
        visible: opacity > 0.001
        opacity: modalRoot.isBrowsingArtist ? 1.0 : 0.0
        z: 1100

        Behavior on opacity {
            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
        }

        MouseArea {
            anchors.fill: parent
            // Absorb pointer events so user cannot interact with elements behind the overlay
        }

        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: function(event) { event.accepted = true }
        }

        Rectangle {
            id: loadingCard
            width: Math.min(460, modalRoot.width - 32)
            implicitHeight: loadingCol.implicitHeight + 48
            anchors.centerIn: parent
            radius: 16
            color: "#0F1422"
            border.color: "#24324D"
            border.width: 1
            clip: true

            // Glowing amber accent border
            Rectangle {
                anchors.fill: parent
                anchors.margins: -1
                radius: 17
                color: "transparent"
                border.color: Qt.rgba(245/255, 158/255, 11/255, 0.35)
                border.width: 1
                z: -1
            }

            // Top ambient gradient glow
            Rectangle {
                anchors.top: parent.top
                anchors.horizontalCenter: parent.horizontalCenter
                width: parent.width
                height: 130
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(245/255, 158/255, 11/255, 0.08) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }

            ColumnLayout {
                id: loadingCol
                anchors.fill: parent
                anchors.margins: 28
                spacing: 16

                // Avatar with Pulsing Amber Glow Rings
                Item {
                    Layout.alignment: Qt.AlignHCenter
                    width: 76
                    height: 76

                    // Outer expanding pulse ring 1 (Amber)
                    Rectangle {
                        id: pulseRing1
                        anchors.centerIn: parent
                        width: 76
                        height: 76
                        radius: 38
                        color: "transparent"
                        border.color: "#F59E0B"
                        border.width: 2

                        SequentialAnimation on scale {
                            running: modalRoot.isBrowsingArtist
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.95; to: 1.25; duration: 1400; easing.type: Easing.OutQuad }
                            NumberAnimation { from: 1.25; to: 0.95; duration: 1400; easing.type: Easing.InOutQuad }
                        }

                        SequentialAnimation on opacity {
                            running: modalRoot.isBrowsingArtist
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.7; to: 0.05; duration: 1400; easing.type: Easing.OutQuad }
                            NumberAnimation { from: 0.05; to: 0.7; duration: 1400; easing.type: Easing.InOutQuad }
                        }
                    }

                    // Outer pulse ring 2 (Sky blue accent)
                    Rectangle {
                        id: pulseRing2
                        anchors.centerIn: parent
                        width: 76
                        height: 76
                        radius: 38
                        color: "transparent"
                        border.color: "#38BDF8"
                        border.width: 1.5

                        SequentialAnimation on scale {
                            running: modalRoot.isBrowsingArtist
                            loops: Animation.Infinite
                            NumberAnimation { from: 1.18; to: 0.95; duration: 1400; easing.type: Easing.InOutQuad }
                            NumberAnimation { from: 0.95; to: 1.18; duration: 1400; easing.type: Easing.OutQuad }
                        }

                        SequentialAnimation on opacity {
                            running: modalRoot.isBrowsingArtist
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.15; to: 0.6; duration: 1400; easing.type: Easing.InOutQuad }
                            NumberAnimation { from: 0.6; to: 0.15; duration: 1400; easing.type: Easing.OutQuad }
                        }
                    }

                    // Avatar Circle Frame
                    Rectangle {
                        anchors.centerIn: parent
                        width: 60
                        height: 60
                        radius: 30
                        color: "#182236"
                        border.color: "#F59E0B"
                        border.width: 2
                        clip: true

                        Image {
                            id: loadingAvatarImg
                            anchors.fill: parent
                            source: modalRoot.browsingArtistAvatar
                            fillMode: Image.PreserveAspectCrop
                            visible: status === Image.Ready && modalRoot.browsingArtistAvatar.length > 0
                        }

                        Text {
                            anchors.centerIn: parent
                            text: (modalRoot.browsingArtistName && modalRoot.browsingArtistName.length > 0)
                                  ? modalRoot.browsingArtistName.charAt(0).toUpperCase()
                                  : "?"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 24
                            font.bold: true
                            color: "#FCD34D"
                            visible: !loadingAvatarImg.visible
                        }
                    }
                }

                // Creator Info Header
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 4

                    Text {
                        text: modalRoot.browsingArtistName || "Artist"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 17
                        font.bold: true
                        color: "#F8FAFC"
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    // Badges row (Provider & Service)
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 6

                        ProviderBadge {
                            provider: modalRoot.browsingArtistProvider || "pawchive"
                            domain: modalRoot.browsingArtistDomain || ""
                            badgeHeight: 20
                        }

                        ServiceBadge {
                            service: modalRoot.browsingArtistService || "patreon"
                            badgeHeight: 20
                        }
                    }
                }

                // Status Heading (Clean title — no duplicated page/post count)
                Text {
                    text: modalRoot.tr("msg_fetching_artist_posts", "Fetching creator posts…")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 13
                    font.weight: 600
                    color: "#94A3B8"
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }

                // Dedicated Progress Dashboard (Fixed width 380px — rock-steady, 0px jitter, within bounds)
                Item {
                    id: progressDashboard
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: Math.min(380, loadingCol.width)
                    Layout.preferredHeight: 64

                    // ── Upper Row: Fixed-position Badges (No resizing or horizontal shifting) ──
                    Item {
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 24

                        // Left Side Badges
                        Row {
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 8

                            // Page Pill (Fixed 74px width)
                            Rectangle {
                                width: 74
                                height: 24
                                radius: 6
                                color: "#0F263D"
                                border.color: "#38BDF8"
                                border.width: 1

                                Row {
                                    anchors.centerIn: parent
                                    spacing: 4
                                    Text { text: "📄"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                    Text {
                                        text: modalRoot.tr("lbl_page", "Page") + " " + Math.max(1, modalRoot.browsePage)
                                        font.family: "Consolas, 'Segoe UI', monospace"
                                        font.pixelSize: 11
                                        font.weight: 600
                                        color: "#7DD3FC"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                            }

                            // Posts Counter Pill (Fixed 172px width — plenty of room, never overflows or shifts)
                            Rectangle {
                                width: 172
                                height: 24
                                radius: 6
                                color: modalRoot.browseCount > 0 ? "#2A1F08" : "#1A2234"
                                border.color: modalRoot.browseCount > 0 ? "#F59E0B" : "#2E3B56"
                                border.width: 1
                                clip: true

                                Row {
                                    anchors.centerIn: parent
                                    spacing: 5
                                    Text { text: "📝"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                    Text {
                                        text: modalRoot.browseTotal > 0
                                              ? (modalRoot.browseCount + " / " + modalRoot.browseTotal + " " + modalRoot.tr("lbl_posts", "posts"))
                                              : (modalRoot.browseCount + " " + modalRoot.tr("lbl_posts_found", "posts"))
                                        font.family: "Consolas, 'Segoe UI', monospace"
                                        font.pixelSize: 11
                                        font.weight: 600
                                        color: modalRoot.browseCount > 0 ? "#FCD34D" : "#94A3B8"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                            }
                        }

                        // Right Side Badges (Anchored to right edge)
                        Row {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 8

                            // Percentage Pill (Fixed 52px width, visible when total is known)
                            Rectangle {
                                visible: modalRoot.browseTotal > 0
                                width: 52
                                height: 24
                                radius: 6
                                color: "#064E3B"
                                border.color: "#10B981"
                                border.width: 1

                                Text {
                                    anchors.centerIn: parent
                                    text: Math.round(modalRoot.browseProgressFraction * 100) + "%"
                                    font.family: "Consolas, 'Segoe UI', monospace"
                                    font.pixelSize: 11
                                    font.weight: 700
                                    color: "#6EE7B7"
                                }
                            }

                            // Active Glowing Pulse Dot
                            Rectangle {
                                width: 8
                                height: 8
                                radius: 4
                                color: "#10B981"
                                anchors.verticalCenter: parent.verticalCenter

                                SequentialAnimation on opacity {
                                    loops: Animation.Infinite
                                    running: modalRoot.isBrowsingArtist
                                    NumberAnimation { from: 1.0; to: 0.25; duration: 600; easing.type: Easing.InOutQuad }
                                    NumberAnimation { from: 0.25; to: 1.0; duration: 600; easing.type: Easing.InOutQuad }
                                }
                            }
                        }
                    }

                    // ── Middle: Dual-Mode Progress Bar (Fixed anchors to left/right of dashboard) ──
                    Rectangle {
                        id: progressBarTrack
                        anchors.top: parent.top
                        anchors.topMargin: 32
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 8
                        radius: 4
                        color: "#151E30"
                        border.color: "#27354E"
                        border.width: 1
                        clip: true

                        // 1. Determinate fill (When total is known)
                        Rectangle {
                            id: determinateFill
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            visible: modalRoot.browseTotal > 0
                            width: Math.max(modalRoot.browseCount > 0 ? 12 : 0, parent.width * modalRoot.browseProgressFraction)
                            radius: 3
                            gradient: Gradient {
                                orientation: Gradient.Horizontal
                                GradientStop { position: 0.0; color: "#D97706" }
                                GradientStop { position: 0.7; color: "#F59E0B" }
                                GradientStop { position: 1.0; color: "#FCD34D" }
                            }

                            Behavior on width {
                                NumberAnimation { duration: 100; easing.type: Easing.OutQuad }
                            }
                        }

                        // 2. Incremental Page Step Fill (When total is unknown, advances smoothly with pages)
                        Rectangle {
                            id: pageStepFill
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            visible: modalRoot.browseTotal === 0 && modalRoot.browseCount > 0
                            width: Math.min(parent.width * 0.88, Math.max(24, modalRoot.browsePage * 32))
                            radius: 3
                            color: Qt.rgba(245/255, 158/255, 11/255, 0.35)

                            Behavior on width {
                                NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
                            }
                        }

                        // 3. Shimmer wave runner (Smooth fluid loop across track)
                        Rectangle {
                            id: progressBarIndicator
                            width: modalRoot.browseTotal > 0 ? 80 : 120
                            height: parent.height
                            radius: 3
                            opacity: modalRoot.browseTotal > 0 ? 0.3 : 0.7
                            gradient: Gradient {
                                orientation: Gradient.Horizontal
                                GradientStop { position: 0.0; color: Qt.rgba(217/255, 119/255, 6/255, 0.0) }
                                GradientStop { position: 0.5; color: Qt.rgba(252/255, 211/255, 77/255, 0.35) }
                                GradientStop { position: 1.0; color: Qt.rgba(245/255, 158/255, 11/255, 0.0) }
                            }

                            NumberAnimation on x {
                                from: -120
                                to: progressBarTrack.width
                                duration: 1200
                                loops: Animation.Infinite
                                running: modalRoot.isBrowsingArtist
                                easing.type: Easing.InOutQuad
                            }
                        }
                    }

                    // ── Lower Line: Stable hint caption ──
                    Text {
                        anchors.top: progressBarTrack.bottom
                        anchors.topMargin: 8
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: modalRoot.tr("hint_fetching_posts_desc", "Connecting to server and retrieving post index…")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                    }
                }

                Item { Layout.preferredHeight: 4 }

                // Cancel Button
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    implicitWidth: 120
                    implicitHeight: 34
                    radius: 7
                    color: cancelLoadingMouse.containsMouse ? "#2A364F" : "#192233"
                    border.color: cancelLoadingMouse.containsMouse ? "#475569" : "#2E3B56"
                    border.width: 1

                    Row {
                        anchors.centerIn: parent
                        spacing: 6

                        Text {
                            text: "✕"
                            font.pixelSize: 11
                            font.bold: true
                            color: cancelLoadingMouse.containsMouse ? "#F87171" : "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            text: modalRoot.tr("btn_cancel", "Cancel")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: cancelLoadingMouse.containsMouse ? "#F1F5F9" : "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: cancelLoadingMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.cancelBrowsingArtist()
                    }
                }
            }
        }
    }
}

