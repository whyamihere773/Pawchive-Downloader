import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "browser"

Rectangle {
    id: root

    property var bridge: null
    readonly property var bBridge: (typeof browserBridge !== "undefined" && browserBridge) ? browserBridge : null

    color: "#0B0E14"

    readonly property string browserMode: bBridge ? bBridge.browserMode : "online"
    readonly property bool isLocalMode: browserMode === "local"
    readonly property string activeProvider: bBridge ? bBridge.activeProvider : "cumst"
    readonly property var providersManifest: bBridge ? bBridge.providersManifest : []
    readonly property var activeManifest: bBridge ? bBridge.activeProviderManifest : ({})
    readonly property var activeCaps: (activeManifest && activeManifest.capabilities) ? activeManifest.capabilities : ({})

    readonly property bool hasSelectedCreator: bBridge ? bBridge.hasSelectedCreator : false
    readonly property var selectedCreator: bBridge ? bBridge.selectedCreator : ({})
    readonly property bool hasSelectedPost: bBridge ? bBridge.hasSelectedPost : false
    readonly property var selectedPost: bBridge ? bBridge.selectedPost : ({})

    // Relocation progress state
    property bool relocating: false
    property string relocatingKey: ""
    property int relocateDone: 0
    property int relocateTotal: 0
    property string relocateFile: ""

    // Drive relocation modal target creator
    property var creatorToRelocate: null

    // Post viewer drawer expansion + attachment sort + computed viewable media list
    property bool postViewerExpanded: false
    property string postAttSortMode: "default"
    readonly property var sortedPostAttachments: sortAttachmentsList((selectedPost && selectedPost.attachments) ? selectedPost.attachments : [], postAttSortMode)
    readonly property var postViewableMedia: buildPostMediaListFromAtts(selectedPost, sortedPostAttachments)

    function _naturalCompare(a, b) {
        var sa = String(a || "").toLowerCase()
        var sb = String(b || "").toLowerCase()
        if (sa === sb) return 0
        var re = /(\d+|\D+)/g
        var pa = sa.match(re) || []
        var pb = sb.match(re) || []
        var n = Math.min(pa.length, pb.length)
        for (var i = 0; i < n; i++) {
            var ca = pa[i], cb = pb[i]
            if (ca === cb) continue
            var da = /^\d+$/.test(ca)
            var db = /^\d+$/.test(cb)
            if (da && db) {
                var na = parseInt(ca, 10), nb = parseInt(cb, 10)
                if (na !== nb) return na - nb
            }
            return ca < cb ? -1 : 1
        }
        return pa.length - pb.length
    }

    function sortAttachmentsList(rawAtts, mode) {
        if (!rawAtts || !rawAtts.length) return []
        var m = (mode || "default").toLowerCase()
        var arr = rawAtts.slice()
        if (m === "default") return arr
        arr.sort(function(a, b) {
            var oa = a || ({}), ob = b || ({})
            var nameA = oa.name || "", nameB = ob.name || ""
            if (m === "name_asc") return _naturalCompare(nameA, nameB)
            if (m === "name_desc") return _naturalCompare(nameB, nameA)
            if (m === "newest") {
                var ma = Number(oa.modified_at || 0), mb = Number(ob.modified_at || 0)
                if (mb !== ma) return mb - ma
                return _naturalCompare(nameA, nameB)
            }
            if (m === "oldest") {
                var ma2 = Number(oa.modified_at || 0), mb2 = Number(ob.modified_at || 0)
                if (ma2 !== mb2) {
                    if (ma2 <= 0) return 1
                    if (mb2 <= 0) return -1
                    return ma2 - mb2
                }
                return _naturalCompare(nameA, nameB)
            }
            if (m === "size_desc") {
                var sa = Number(oa.file_size || 0), sb = Number(ob.file_size || 0)
                if (sb !== sa) return sb - sa
                return _naturalCompare(nameA, nameB)
            }
            if (m === "size_asc") {
                var sa2 = Number(oa.file_size || 0), sb2 = Number(ob.file_size || 0)
                if (sa2 !== sb2) {
                    if (sa2 <= 0 && sb2 > 0) return 1
                    if (sb2 <= 0 && sa2 > 0) return -1
                    return sa2 - sb2
                }
                return _naturalCompare(nameA, nameB)
            }
            if (m === "type") {
                var ka = attachmentKindLabel(oa) || ""
                var kb = attachmentKindLabel(ob) || ""
                if (ka !== kb) return ka < kb ? -1 : 1
                var ea = _attachmentExt(oa), eb = _attachmentExt(ob)
                if (ea !== eb) return ea < eb ? -1 : 1
                return _naturalCompare(nameA, nameB)
            }
            return 0
        })
        return arr
    }

    function handleRangeMarkClick(modelKind, gridView, index, itemData, shiftPressed) {
        if (!root.bBridge || !itemData) return
        var model = gridView.model
        var count = model && model.count !== undefined ? model.count : 0
        if (shiftPressed && gridView.markAnchor >= 0 && gridView.markAnchor < count && gridView.markAnchor !== index) {
            var anchorRec = model.get ? model.get(gridView.markAnchor) : null
            var anchorKey = anchorRec ? String(anchorRec.key || "") : ""
            if (anchorKey && anchorKey === gridView.markAnchorKey) {
                root.bBridge.markRangeInModel(modelKind, gridView.markAnchor, index, gridView.markAnchorState)
                return
            }
        }
        var nowMarked = root.bBridge.toggleMarkItem(itemData)
        gridView.markAnchor = index
        gridView.markAnchorKey = String(itemData.key || "")
        gridView.markAnchorState = nowMarked
    }

    function _attachmentExt(att) {
        if (!att) return ""
        var e = (att.ext || "").toLowerCase()
        if (e) return e
        var candidate = (att.name || att.local_path || att.url || "").split("#")[0].split("?")[0]
        var dot = candidate.lastIndexOf(".")
        return dot > 0 ? candidate.substring(dot).toLowerCase() : ""
    }

    function isViewableAttachment(att) {
        if (!att) return false
        var mt = (att.media_type || "").toLowerCase()
        if (mt === "image" || mt === "video" || mt === "audio") return true
        var ext = _attachmentExt(att)
        var viewableExts = [
            ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".apng", ".gif", ".webp", ".avif", ".heic", ".heif", ".bmp", ".svg",
            ".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".flv", ".wmv", ".m3u8", ".ts",
            ".mp3", ".flac", ".wav", ".ogg", ".oga", ".m4a", ".aac", ".opus", ".wma"
        ]
        return viewableExts.indexOf(ext) >= 0
    }

    function attachmentKindLabel(att) {
        if (!att) return "FILE"
        var ext = _attachmentExt(att)
        var mt = (att.media_type || "").toLowerCase()
        if (ext === ".gif" || !!att.is_loop) return "GIF"
        if (mt === "video" || [".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".m3u8"].indexOf(ext) >= 0) return "VIDEO"
        if (mt === "audio" || [".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus"].indexOf(ext) >= 0) return "AUDIO"
        if (mt === "image" || isViewableAttachment(att)) return "IMAGE"
        return (ext ? ext.replace(".", "").toUpperCase() : "FILE")
    }

    function buildPostMediaListFromAtts(postObj, allAtts) {
        if (!postObj || !allAtts) return []
        var mList = []
        var pid = postObj.provider_id || root.activeProvider || ""
        for (var i = 0; i < allAtts.length; i++) {
            var a = allAtts[i]
            if (!a || !isViewableAttachment(a)) continue
            var rawThumb = a.thumbnail_url || ""
            var target = a.local_path
                         ? a.local_path
                         : ((postObj.is_unimported && (a.media_type === "image") && rawThumb) ? rawThumb : (a.url || ""))
            if (!target) continue
            // Only supply a separate preview thumbnail when distinct from target and routed with provider headers
            var resolvedThumb = (!a.local_path && rawThumb && rawThumb !== target)
                                ? root.browserThumbUrl(rawThumb, pid)
                                : ""
            var itemLinkUrl = a.url || (root.bBridge ? root.bBridge.resolveAttachmentUrl(a, postObj) : "")
            var postLinkUrl = postObj.url || (root.bBridge ? root.bBridge.resolvePostUrl(postObj) : "")
            mList.push({
                "path": target,
                "url": itemLinkUrl,
                "name": a.name || ("media_" + (i + 1)),
                "ext": a.ext || _attachmentExt(a),
                "media_type": a.media_type || "",
                "thumbUrl": resolvedThumb,
                "size": Number(a.file_size || 0),
                "is_loop": !!a.is_loop,
                "provider_id": pid,
                "postUrl": postLinkUrl,
                "postId": postObj.post_id || ""
            })
        }
        return mList
    }

    function openPostMediaGallery(postObj, startIndex) {
        var pObj = postObj || root.selectedPost || ({})
        var mList = buildPostMediaList(pObj)
        if (!mList || mList.length === 0) return false
        var idx = Math.max(0, Math.min(Number(startIndex || 0), mList.length - 1))
        browserLightbox.open(mList[idx], mList)
        return true
    }

    function buildPostMediaList(postObj) {
        if (!postObj || !postObj.attachments) return []
        var src = (postObj === root.selectedPost) ? root.sortedPostAttachments : sortAttachmentsList(postObj.attachments || [], root.postAttSortMode)
        return buildPostMediaListFromAtts(postObj, src)
    }

    function openAttachmentInApp(att, postObj) {
        var pObj = postObj || root.selectedPost || ({})
        if (!att) return openPostMediaGallery(pObj, 0)
        if (isViewableAttachment(att) && (att.local_path || att.url)) {
            var mList = buildPostMediaList(pObj)
            var target = att.local_path ? att.local_path : (att.url || "")
            var matchItem = null
            for (var i = 0; i < mList.length; i++) {
                if (mList[i].path === target) {
                    matchItem = mList[i]
                    break
                }
            }
            if (!matchItem && mList.length > 0) matchItem = mList[0]
            if (matchItem) {
                browserLightbox.open(matchItem, mList)
                return true
            }
        }
        if (att.local_path && root.bridge && root.bridge.openPathInSystem) {
            root.bridge.openPathInSystem(att.local_path)
            return true
        }
        if (root.bBridge && pObj.url) {
            root.triggerItemDownload(pObj.url, true, pObj.title || pObj.creator_name || "")
            return true
        }
        root.showToast("Preview unavailable for this archive type.", "warning")
        return false
    }

    // Download dispatch feedback state (per-session URL badge tracking)
    property var queuedDownloadUrls: ({})
    property int downloadPulseTick: 0

    function markUrlDispatched(url) {
        if (!url) return
        var next = Object.assign({}, root.queuedDownloadUrls || {})
        next[url] = Date.now()
        root.queuedDownloadUrls = next
        root.downloadPulseTick += 1
    }

    function isUrlDispatched(url) {
        void root.downloadPulseTick
        return !!(url && root.queuedDownloadUrls && root.queuedDownloadUrls[url])
    }

    function triggerItemDownload(url, autoStart, label, itemMeta) {
        if (!root.bBridge) return
        if (!url) {
            root.bBridge.downloadSingleUrl("", autoStart, label || "")
            return
        }
        var meta = itemMeta || ({})
        var itemObj = {
            url: String(url),
            title: String(meta.title || label || meta.name || meta.creator_name || url),
            creator_name: String(meta.creator_name || meta.name || label || ""),
            creator_id: String(meta.creator_id || meta.id || ""),
            service: String(meta.service || ""),
            service_label: String(meta.service_label || meta.service || ""),
            item_type: String(meta.item_type || (meta.post_id ? "post" : "creator"))
        }
        var heading = label ? ("Download: " + label) : "Download Item"
        browserDownloadModal.openForItems([itemObj], heading, autoStart, "single")
    }

    function browserThumbUrl(rawUrl, providerId) {
        var u = (rawUrl || "").trim()
        if (!u) return ""
        if (u.indexOf("image://") === 0 || u.indexOf("file://") === 0) return u
        if (u.indexOf("http://") === 0 || u.indexOf("https://") === 0) {
            return "image://remotethumb/" + encodeURIComponent(providerId || "") + "/" + encodeURIComponent(u)
        }
        return u
    }

    // Toast banner state
    property string toastMessage: ""
    property string toastKind: "info"
    property string toastActionLabel: ""
    property int toastActionTab: -1
    property bool toastVisible: false

    Timer {
        id: toastTimer
        interval: 4800
        repeat: false
        onTriggered: root.toastVisible = false
    }

    function showToast(msg, kind, actionLabel, actionTab) {
        root.toastMessage = msg || ""
        root.toastKind = kind || "info"
        root.toastActionLabel = actionLabel || ""
        root.toastActionTab = (actionTab !== undefined && actionTab !== null) ? actionTab : -1
        root.toastVisible = true
        toastTimer.restart()
    }

    function openRelocateModal(creator) {
        root.creatorToRelocate = creator || null
        moveCreatorDriveModal.open()
    }

    function closeRelocateModal() {
        moveCreatorDriveModal.close()
    }

    function closeNewPostsModal() {
        newPostsModal.close()
    }

    property string loginModalProviderId: ""
    property string loginModalReason: ""
    property string loginModalError: ""
    readonly property bool isActiveProviderLoggedIn: root.bBridge
                                                   ? (root.bBridge.activeProvider, root.bBridge.activeProviderLoggedIn)
                                                   : false
    readonly property string activeProviderDisplayName: {
        var pid = root.bBridge ? (root.bBridge.activeProvider || "") : ""
        if (root.bBridge && root.bBridge.activeProviderManifest && root.bBridge.activeProviderManifest.display_name) {
            return String(root.bBridge.activeProviderManifest.display_name)
        }
        return pid ? (pid.charAt(0).toUpperCase() + pid.slice(1)) : "Site"
    }

    readonly property string creatorPostSearchText: (typeof creatorBanner !== "undefined" && creatorBanner) ? creatorBanner.postSearchText : ""

    function openAddLibraryRootDialog() {
        addLibraryRootDialog.open()
    }

    function openCustomRelocateFolderDialog() {
        customRelocateFolderDialog.open()
    }

    function openNewPostsModal() {
        newPostsModal.open()
    }

    function openDownloadModalForItems(items, heading, autoStart, sourceMode, initialSyncMode) {
        browserDownloadModal.openForItems(items, heading, autoStart, sourceMode, initialSyncMode || "all")
    }

    function triggerCreatorDiskSync(creatorObj, syncMode) {
        if (!root.bBridge) return
        var c = creatorObj || root.selectedCreator || ({})
        var mode = String(syncMode || "missing_or_mismatched")
        if (root.bBridge.prepareCreatorSyncItem) {
            var prep = root.bBridge.prepareCreatorSyncItem(c) || ({})
            if (prep.error === "unlinked") {
                root.bBridge.searchCreatorAcrossSites(c)
                root.openNewPostsModal()
                return
            }
            if (prep.url) {
                var cname = String(prep.creator_name || prep.title || "Creator")
                browserDownloadModal.openForItems(
                    [prep],
                    "Sync Missing & Mismatched — " + cname,
                    true,
                    "sync",
                    mode
                )
                return
            }
        }
        if (c.url) {
            var lbl = String(c.name || c.creator_name || "Creator")
            browserDownloadModal.openForItems([c], "Sync Missing & Mismatched — " + lbl, true, "sync", mode)
        }
    }

    function openProviderLoginModal(providerId, reason) {
        root.loginModalProviderId = providerId || (root.bBridge ? root.bBridge.activeProvider : "")
        root.loginModalReason = reason || ""
        root.loginModalError = ""
        if (typeof providerLoginModal !== "undefined" && providerLoginModal) {
            providerLoginModal.resetInputs()
        }
        providerLoginModal.open()
    }

    function closeProviderLoginModal() {
        providerLoginModal.close()
    }

    function scrollServicesBy(deltaX) {
        if (typeof searchBar !== "undefined" && searchBar) {
            searchBar.scrollServicesBy(deltaX)
        }
    }

    function formatBytes(bytes) {
        var b = Number(bytes || 0)
        if (b <= 0) return "0 B"
        if (b < 1024) return b + " B"
        if (b < 1024 * 1024) return (b / 1024).toFixed(1) + " KB"
        if (b < 1024 * 1024 * 1024) return (b / (1024 * 1024)).toFixed(1) + " MB"
        return (b / (1024 * 1024 * 1024)).toFixed(2) + " GB"
    }

    // Newtonian viewport entrance impulse on mode/provider switch
    property real viewportOffsetY: 0
    property real viewportScale: 1.0
    property real viewportOpacity: 1.0

    function triggerViewportImpulse() {
        viewportOffsetY = 12
        viewportScale = 0.985
        viewportOpacity = 0.45
        impulseResetTimer.restart()
    }

    Timer {
        id: impulseResetTimer
        interval: 16
        repeat: false
        onTriggered: {
            root.viewportOffsetY = 0
            root.viewportScale = 1.0
            root.viewportOpacity = 1.0
        }
    }

    Behavior on viewportOffsetY {
        NumberAnimation { duration: 110; easing.type: Easing.OutCubic }
    }
    Behavior on viewportScale {
        NumberAnimation { duration: 110; easing.type: Easing.OutCubic }
    }
    Behavior on viewportOpacity {
        NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
    }

    Connections {
        target: root.bBridge
        function onBrowserModeChanged() { root.triggerViewportImpulse() }
        function onActiveProviderChanged() { root.triggerViewportImpulse() }
        function onToastRequested(msg, kind) {
            var isDlToast = (kind === "success" || kind === "info") && msg && (msg.indexOf("Downloader") !== -1 || msg.indexOf("Queue") !== -1)
            root.showToast(msg, kind, isDlToast ? "Open Downloader →" : "", isDlToast ? 0 : -1)
        }
        function onNavigateToTabRequested(tabIdx) {
            if (typeof appWindow !== "undefined" && appWindow) {
                appWindow.currentTab = tabIdx
            }
        }
        function onSelectedPostChanged() {
            if (!root.hasSelectedPost) root.postViewerExpanded = false
        }
        function onRelocationProgress(creatorKey, done, total, currentFile) {
            root.relocating = true
            root.relocatingKey = creatorKey
            root.relocateDone = done
            root.relocateTotal = total
            root.relocateFile = currentFile
        }
        function onRelocationFinished(creatorKey, ok, message) {
            root.relocating = false
            root.relocatingKey = ""
        }
        function onLoginPromptRequested(providerId, reason) {
            root.openProviderLoginModal(providerId, reason)
        }
        function onProviderLoginFinished(providerId, ok, message) {
            if (ok) {
                root.loginModalError = ""
                if (providerLoginModal.opened) {
                    providerLoginModal.close()
                }
            } else {
                root.loginModalError = message || "Authentication failed."
            }
        }
    }

    Connections {
        target: typeof appBridge !== "undefined" ? appBridge : null
        function onProviderLoginFinished(providerId, ok, message) {
            if (root.bBridge) {
                root.bBridge.notifyProviderAuthChanged(providerId)
            }
        }
    }

    Component.onCompleted: {
        if (root.bBridge && root.bBridge.creatorsModel && root.bBridge.creatorsModel.count === 0) {
            root.bBridge.refresh(false)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8


        BrowserTopBar {
            id: topBar
            view: root
        }

        BrowserSearchBar {
            id: searchBar
            view: root
        }

        BrowserCreatorBanner {
            id: creatorBanner
            view: root
        }

        // ====================================================================
        // 4. NEWTONIAN PROGRESS / RELOCATION / AUTH BANNER STRIP
        // ====================================================================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: (root.relocating || (root.bBridge && (root.bBridge.isLoading || root.bBridge.authRequired))) ? 38 : 0
            visible: Layout.preferredHeight > 0.5
            clip: true
            radius: 8
            color: (root.bBridge && root.bBridge.authRequired) ? "#2A1215" : "#111827"
            border.color: (root.bBridge && root.bBridge.authRequired) ? "#F43F5E" : "#38BDF8"
            border.width: 1

            Behavior on Layout.preferredHeight {
                NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 10

                Text {
                    text: root.relocating
                          ? ("💽 Moving creator across drives (" + root.relocateDone + "/" + root.relocateTotal + "): " + root.relocateFile)
                          : (root.bBridge ? (root.bBridge.errorMessage || root.bBridge.statusText) : "")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: (root.bBridge && root.bBridge.authRequired) ? "#FDA4AF" : "#E2E8F0"
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }

                // Weighted Progress Bar when relocating files across drives
                Rectangle {
                    visible: root.relocating && root.relocateTotal > 0
                    Layout.preferredWidth: 180
                    Layout.preferredHeight: 8
                    radius: 4
                    color: "#1E293B"

                    Rectangle {
                        height: parent.height
                        radius: 4
                        color: "#10B981"
                        width: parent.width * Math.min(1.0, root.relocateDone / Math.max(1, root.relocateTotal))
                        Behavior on width {
                            NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
                        }
                    }
                }

                // 1-Click Open Inline Account Login / Session Modal when Auth Required
                Rectangle {
                    objectName: "bannerAuthLoginBtn"
                    visible: !!(root.bBridge && root.bBridge.authRequired)
                    Layout.preferredHeight: 26
                    implicitWidth: authBtnTxt.implicitWidth + 16
                    radius: 6
                    color: authBannerBtnMouse.containsMouse ? "#F43F5E" : "#E11D48"
                    Springy { hover: authBannerBtnMouse.containsMouse; pressed: authBannerBtnMouse.pressed }
                    Text {
                        id: authBtnTxt
                        anchors.centerIn: parent
                        text: "🔑 Log In to " + root.activeProviderDisplayName
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#FFFFFF"
                    }
                    MouseArea {
                        id: authBannerBtnMouse
                        objectName: "bannerAuthLoginMouse"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.bBridge) {
                                root.openProviderLoginModal(
                                    root.bBridge.activeProvider,
                                    root.bBridge.activeService === "favorites" ? "favorites" : ""
                                )
                            }
                        }
                    }
                }
            }
        }


        // ====================================================================
        // 5. MAIN VIEWPORT: CREATOR GRID / POST FEED + SLIDE-OVER POST DETAIL
        // ====================================================================
        Item {
            id: mainViewportContainer
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 120
            clip: true

            readonly property bool showingPostsGrid: root.hasSelectedCreator || (!root.isLocalMode && root.bBridge && root.bBridge.searchTarget === "posts")

            Item {
                id: mainGridViewport
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                width: root.hasSelectedPost ? Math.max(Math.min(parent.width, 240), parent.width - (root.postViewerExpanded ? 0 : Math.min(500, parent.width * 0.52))) : parent.width
                opacity: root.viewportOpacity
                scale: root.viewportScale
                transform: Translate { y: root.viewportOffsetY }

                Behavior on width {
                    NumberAnimation { duration: 135; easing.type: Easing.OutCubic }
                }

                BrowserCreatorsGrid {
                    id: creatorsGridPane
                    view: root
                    showingPostsGrid: mainViewportContainer.showingPostsGrid
                }

                BrowserPostsGrid {
                    id: postsGrid
                    view: root
                    showingPostsGrid: mainViewportContainer.showingPostsGrid
                }
            }

            BrowserPostDetailDrawer {
                id: postDetailDrawer
                view: root
            }
        }

        BrowserPaginationBar {
            id: paginationBar
            view: root
        }

        // ====================================================================
        // 7. PERSISTENT "MARKED FOR DOWNLOAD" SELECTION CART TRAY
        // ====================================================================
        BrowserMarkTray {
            id: markTray
            Layout.fillWidth: true
            browserBridge: root.bBridge
            useDownloadModal: true
            onDownloadRequested: (autoStart) => {
                browserDownloadModal.openForMarked(autoStart)
            }
        }
    }

    // ── Browser Download Destination & Full Settings Modal ──────────────────
    BrowserDownloadModal {
        id: browserDownloadModal
        objectName: "browserDownloadModal"
        appBridge: root.bridge
        browserBridge: root.bBridge
        onDownloadDispatched: (urls, autoStart, folder) => {
            var arr = urls || []
            for (var i = 0; i < arr.length; i++) {
                root.markUrlDispatched(arr[i])
            }
        }
    }

    // ── Floating Toast Notification Pill ────────────────────────────────────
    Rectangle {
        id: browserToastPill
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 72
        z: 50
        visible: opacity > 0.01
        opacity: root.toastVisible ? 1.0 : 0.0
        scale: root.toastVisible ? 1.0 : 0.92
        height: 38
        width: Math.min(Math.max(120, parent.width - 24), toastRow.implicitWidth + 28)
        clip: true
        radius: 19
        color: root.toastKind === "error" ? "#450A0A" : (root.toastKind === "warning" ? "#451A03" : "#064E3B")
        border.color: root.toastKind === "error" ? "#F43F5E" : (root.toastKind === "warning" ? "#F59E0B" : "#10B981")
        border.width: 1.5

        Behavior on opacity { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        Behavior on scale { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }

        RowLayout {
            id: toastRow
            anchors.centerIn: parent
            spacing: 10

            Text {
                id: toastTxt
                Layout.maximumWidth: Math.max(80, browserToastPill.width - 28 - (toastActRect.visible ? (toastActRect.implicitWidth + 10) : 0))
                text: root.toastMessage
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: Font.Bold
                color: "#FFFFFF"
                elide: Text.ElideRight
            }

            Rectangle {
                id: toastActRect
                objectName: "toastActionBtn"
                visible: root.toastActionLabel !== ""
                Layout.preferredHeight: 24
                Layout.preferredWidth: toastActTxt.implicitWidth + 14
                implicitHeight: 24
                implicitWidth: toastActTxt.implicitWidth + 14
                radius: 12
                color: toastActMouse.containsMouse ? "#10B981" : "#047857"
                border.color: "#6EE7B7"
                border.width: 1

                Text {
                    id: toastActTxt
                    anchors.centerIn: parent
                    text: root.toastActionLabel
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                }

                MouseArea {
                    id: toastActMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.toastVisible = false
                        if (root.toastActionTab === 0 && root.bBridge) {
                            root.bBridge.openDownloaderTab()
                        } else if (root.toastActionTab >= 0 && typeof appWindow !== "undefined" && appWindow) {
                            appWindow.currentTab = root.toastActionTab
                        }
                    }
                }
            }
        }
    }


    BrowserMoveDriveModal {
        id: moveCreatorDriveModal
        view: root
    }

    FolderDialog {
        id: addLibraryRootDialog
        title: "Select a Folder Containing Downloaded Creators on Another Drive"
        onAccepted: {
            if (root.bBridge && selectedFolder) {
                root.bBridge.addLocalLibraryRoot(selectedFolder.toString())
            }
        }
    }

    FolderDialog {
        id: customRelocateFolderDialog
        title: "Select Destination Root Folder for Creator"
        onAccepted: {
            if (root.bBridge && root.creatorToRelocate && selectedFolder) {
                root.bBridge.moveCreatorToDrive(root.creatorToRelocate.key, selectedFolder.toString())
                moveCreatorDriveModal.close()
            }
        }
    }


    BrowserNewPostsModal {
        id: newPostsModal
        view: root
    }

    BrowserProviderLoginModal {
        id: providerLoginModal
        view: root
    }

    // Reused Full-Screen Media Lightbox for both Online Streaming and Local Browser Modes
    MediaLightboxModal {
        id: browserLightbox
        anchors.fill: parent
        z: 100
        bridge: root.bridge
        browserBridge: root.bBridge
        hideExternalActions: true
    }
}
