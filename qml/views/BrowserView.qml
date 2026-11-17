import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"

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

    function triggerItemDownload(url, autoStart, label) {
        if (!root.bBridge) return
        if (!url) {
            root.bBridge.downloadSingleUrl("", autoStart, label || "")
            return
        }
        root.markUrlDispatched(url)
        root.bBridge.downloadSingleUrl(url, autoStart, label || "")
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

    function openProviderLoginModal(providerId, reason) {
        root.loginModalProviderId = providerId || (root.bBridge ? root.bBridge.activeProvider : "")
        root.loginModalReason = reason || ""
        root.loginModalError = ""
        if (typeof loginPassField !== "undefined") loginPassField.text = ""
        if (typeof loginCookieField !== "undefined") loginCookieField.text = ""
        providerLoginModal.open()
    }

    function closeProviderLoginModal() {
        providerLoginModal.close()
    }

    function scrollServicesBy(deltaX) {
        if (typeof svcFlickable === "undefined") return
        var maxX = Math.max(0, svcFlickable.contentWidth - svcFlickable.width)
        if (maxX <= 0) {
            svcFlickable.contentX = 0
            return
        }
        svcFlickable.contentX = Math.max(0, Math.min(maxX, svcFlickable.contentX + Number(deltaX || 0)))
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

        // ====================================================================
        // 1. TOP BAR: DUAL-MODE GLIDER + DYNAMIC PROVIDER / DRIVE SWITCHER
        // ====================================================================
        Rectangle {
            objectName: "browserTopBar"
            Layout.fillWidth: true
            Layout.preferredHeight: topBarFlow.implicitHeight + 12
            radius: 10
            color: "#0F131C"
            border.color: "#1E2536"
            border.width: 1
            clip: true

            Flow {
                id: topBarFlow
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 6
                spacing: 8

                // ── Dual-Mode Switcher (Online Mode <-> Local Disk Mode) ────
                Rectangle {
                    id: modeDock
                    height: 34
                    width: Math.min(276, Math.max(120, topBarFlow.width))
                    radius: 8
                    color: "#090C12"
                    border.color: "#1E293B"
                    border.width: 1
                    clip: true

                    // Newtonian Liquid Glider Pill
                    Rectangle {
                        id: modeGlider
                        readonly property real slotW: Math.max(40, (modeDock.width - 10) / 2)
                        y: 3
                        height: 28
                        width: slotW
                        radius: 6
                        x: root.isLocalMode ? (modeDock.width - 4 - slotW) : 4
                        color: root.isLocalMode ? "#064E3B" : "#172554"
                        border.color: root.isLocalMode ? "#10B981" : "#38BDF8"
                        border.width: 1

                        Behavior on x {
                            NumberAnimation { duration: 130; easing.type: Easing.OutCubic }
                        }
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 180 } }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 3
                        spacing: 4

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Springy { hover: onlineModeMouse.containsMouse; pressed: onlineModeMouse.pressed }

                            Row {
                                anchors.centerIn: parent
                                spacing: 5
                                Text { text: "🌐"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                                Text {
                                    text: "Online Browser"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: !root.isLocalMode ? Font.Bold : Font.Medium
                                    color: !root.isLocalMode ? "#F8FAFC" : "#94A3B8"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            MouseArea {
                                id: onlineModeMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 300
                                ToolTip.text: "Browse live creators & posts online and mark them into your Download Cart"
                                onClicked: if (root.bBridge) root.bBridge.setBrowserMode("online")
                            }
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Springy { hover: localModeMouse.containsMouse; pressed: localModeMouse.pressed }

                            Row {
                                anchors.centerIn: parent
                                spacing: 5
                                Text { text: "💾"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                                Text {
                                    text: "Local On-Disk"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: root.isLocalMode ? Font.Bold : Font.Medium
                                    color: root.isLocalMode ? "#ECFDF5" : "#94A3B8"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            MouseArea {
                                id: localModeMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 300
                                ToolTip.text: "Browse ONLY creators and posts present on your local drives — with multi-drive support"
                                onClicked: if (root.bBridge) root.bBridge.setBrowserMode("local")
                            }
                        }
                    }
                }

                // ── ONLINE MODE: Capability-Driven Modular Provider Switcher ─
                Repeater {
                    model: root.providersManifest

                    delegate: Rectangle {
                        readonly property var pData: modelData || ({})
                        readonly property bool isCurrent: root.activeProvider === pData.id
                        readonly property string accent: pData.accentColor || "#38BDF8"

                        visible: !root.isLocalMode
                        height: 34
                        width: Math.min(topBarFlow.width, provPillRow.implicitWidth + 20)
                        radius: 7
                        color: isCurrent ? "#182235" : (provMouse.containsMouse ? "#141A28" : "#0B0E16")
                        border.color: isCurrent ? accent : "#1E293B"
                        border.width: isCurrent ? 1.5 : 1

                        Springy { hover: provMouse.containsMouse; pressed: provMouse.pressed }
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Behavior on border.color { ColorAnimation { duration: 150 } }

                        Row {
                            id: provPillRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                text: pData.icon || "🌐"
                                font.pixelSize: 12
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: pData.name || pData.id || ""
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: isCurrent ? Font.Bold : Font.Medium
                                color: isCurrent ? "#F8FAFC" : "#94A3B8"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            id: provMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: "Switch provider to " + (pData.domain || pData.name || "")
                            onClicked: if (root.bBridge) root.bBridge.setActiveProvider(pData.id)
                        }
                    }
                }

                // ── LOCAL MODE: Multi-Drive Filter Pills & Folder Manager ───
                Rectangle {
                    id: allDrvChip
                    readonly property bool isAll: !root.bBridge || root.bBridge.activeDriveFilter === "all"
                    visible: root.isLocalMode
                    height: 34
                    width: Math.min(topBarFlow.width, allDrvRow.implicitWidth + 16)
                    radius: 6
                    color: isAll ? "#064E3B" : "#121824"
                    border.color: isAll ? "#10B981" : "#1E293B"
                    border.width: 1
                    Springy { hover: allDrvMouse.containsMouse; pressed: allDrvMouse.pressed }

                    Row {
                        id: allDrvRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "💽"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "All Drives"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: allDrvChip.isAll ? Font.Bold : Font.Medium
                            color: allDrvChip.isAll ? "#ECFDF5" : "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: allDrvMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (root.bBridge) root.bBridge.setDriveFilter("all")
                    }
                }

                Repeater {
                    model: root.bBridge ? root.bBridge.localDrives : []

                    delegate: Rectangle {
                        readonly property var dInfo: modelData || ({})
                        readonly property bool isSel: root.bBridge && root.bBridge.activeDriveFilter === dInfo.drive

                        visible: root.isLocalMode
                        height: 34
                        width: Math.min(topBarFlow.width, drvChipRow.implicitWidth + rmDrvBtn.width + 20)
                        radius: 6
                        color: isSel ? "#064E3B" : "#121824"
                        border.color: isSel ? "#10B981" : "#1E293B"
                        border.width: 1
                        clip: true
                        Springy { hover: drvChipMouse.containsMouse; pressed: drvChipMouse.pressed }

                        Row {
                            id: drvChipRow
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 5
                            Text { text: "💽"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                width: Math.min(implicitWidth, Math.max(60, topBarFlow.width - rmDrvBtn.width - 48))
                                text: (dInfo.drive || "") + " (" + Number(dInfo.free_gb || 0).toFixed(0) + " GB free)"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: isSel ? Font.Bold : Font.Medium
                                color: isSel ? "#ECFDF5" : "#CBD5E1"
                                elide: Text.ElideRight
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: drvChipMouse
                            z: 1
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.right: rmDrvBtn.left
                            anchors.rightMargin: 2
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: "Filter creators stored on drive " + (dInfo.drive || "") + " (" + (dInfo.root_path || "") + ")"
                            onClicked: if (root.bBridge) root.bBridge.setDriveFilter(dInfo.drive)
                        }
                        Rectangle {
                            id: rmDrvBtn
                            z: 2
                            width: 18
                            height: 18
                            radius: 4
                            anchors.right: parent.right
                            anchors.rightMargin: 5
                            anchors.verticalCenter: parent.verticalCenter
                            color: rmDrvMouse.containsMouse ? "#991B1B" : "#1E293B"
                            border.color: rmDrvMouse.containsMouse ? "#F87171" : "#334155"
                            border.width: 1
                            Text {
                                anchors.centerIn: parent
                                text: "✕"
                                font.pixelSize: 9
                                font.weight: Font.Bold
                                color: rmDrvMouse.containsMouse ? "#FEE2E2" : "#94A3B8"
                            }
                            MouseArea {
                                id: rmDrvMouse
                                objectName: "removeLocalDriveMouse"
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Hide drive " + (dInfo.drive || "") + " from Local Browser"
                                onClicked: if (root.bBridge) root.bBridge.removeLocalDrive(dInfo.drive || "", dInfo.root_path || "")
                            }
                        }
                    }
                }

                // Add Another Drive / Folder Root Button
                Rectangle {
                    visible: root.isLocalMode
                    height: 34
                    width: Math.min(topBarFlow.width, addRootRow.implicitWidth + 16)
                    radius: 6
                    color: addRootMouse.containsMouse ? "#1E293B" : "#131926"
                    border.color: "#38BDF8"
                    border.width: 1
                    Springy { hover: addRootMouse.containsMouse; pressed: addRootMouse.pressed }

                    Row {
                        id: addRootRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "📁+"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Add Drive Folder…"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#38BDF8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: addRootMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "Add another disk folder where you moved or stored downloaded artists"
                        onClicked: addLibraryRootDialog.open()
                    }
                }

                // Restore Hidden / Excluded Drives Button
                Rectangle {
                    id: restoreDrivesBtn
                    visible: root.isLocalMode && !!(root.bBridge && root.bBridge.excludedLocalDrives && root.bBridge.excludedLocalDrives.length > 0)
                    height: 34
                    width: Math.min(topBarFlow.width, restoreDrvRow.implicitWidth + 16)
                    radius: 6
                    color: restoreDrvMouse.containsMouse ? "#1E293B" : "#131926"
                    border.color: "#F59E0B"
                    border.width: 1
                    Springy { hover: restoreDrvMouse.containsMouse; pressed: restoreDrvMouse.pressed }

                    Row {
                        id: restoreDrvRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "↺"; font.pixelSize: 12; color: "#FBBF24"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Restore (" + ((root.bBridge && root.bBridge.excludedLocalDrives) ? root.bBridge.excludedLocalDrives.length : 0) + ")"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#FDE68A"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: restoreDrvMouse
                        objectName: "restoreDrivesBtnMouse"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "Restore previously removed default or system drives"
                        onClicked: if (root.bBridge) root.bBridge.restoreDefaultLocalDrives()
                    }
                }

                // ── Online Target Toggle: Creators vs Global Posts ──────────
                Rectangle {
                    visible: !root.isLocalMode && !root.hasSelectedCreator && !!root.activeCaps.supportsGlobalPostSearch
                    height: 34
                    width: Math.min(topBarFlow.width, targetRow.implicitWidth + 16)
                    radius: 7
                    color: "#121722"
                    border.color: "#263248"
                    border.width: 1

                    Row {
                        id: targetRow
                        anchors.centerIn: parent
                        spacing: 4

                        Rectangle {
                            id: cTgtChip
                            readonly property bool isC: !root.bBridge || root.bBridge.searchTarget === "creators"
                            height: 26
                            width: cTgtTxt.implicitWidth + 14
                            radius: 5
                            color: isC ? "#1E293B" : "transparent"
                            Text {
                                id: cTgtTxt
                                anchors.centerIn: parent
                                text: "👤 Creators"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: cTgtChip.isC ? Font.Bold : Font.Normal
                                color: cTgtChip.isC ? "#38BDF8" : "#94A3B8"
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (root.bBridge) root.bBridge.setSearchTarget("creators")
                            }
                        }

                        Rectangle {
                            id: pTgtChip
                            readonly property bool isP: root.bBridge && root.bBridge.searchTarget === "posts"
                            height: 26
                            width: pTgtTxt.implicitWidth + 14
                            radius: 5
                            color: isP ? "#1E293B" : "transparent"
                            Text {
                                id: pTgtTxt
                                anchors.centerIn: parent
                                text: "🖼️ Posts"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: pTgtChip.isP ? Font.Bold : Font.Normal
                                color: pTgtChip.isP ? "#38BDF8" : "#94A3B8"
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (root.bBridge) root.bBridge.setSearchTarget("posts")
                            }
                        }
                    }
                }

                // ── Live Downloader Status Pill (1-Click Jump to Downloader) ──
                Rectangle {
                    id: activeDlChip
                    visible: !!(root.bridge && root.bridge.isDownloading)
                    height: 34
                    width: Math.min(topBarFlow.width, activeDlRow.implicitWidth + 16)
                    radius: 7
                    color: activeDlMouse.containsMouse ? "#065F46" : "#064E3B"
                    border.color: "#34D399"
                    border.width: 1
                    Springy { hover: activeDlMouse.containsMouse; pressed: activeDlMouse.pressed }

                    Row {
                        id: activeDlRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "⬇"; font.pixelSize: 11; color: "#6EE7B7"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Downloading… · View"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#ECFDF5"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: activeDlMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "A download is running — click to switch to the Downloader tab"
                        onClicked: if (root.bBridge) root.bBridge.openDownloaderTab()
                    }
                }

                // ── Refresh Button ──────────────────────────────────────────
                Rectangle {
                    height: 34
                    width: 36
                    radius: 7
                    color: refMouse.containsMouse ? "#1E293B" : "#141926"
                    border.color: "#2E3A52"
                    border.width: 1
                    Springy { hover: refMouse.containsMouse; pressed: refMouse.pressed }

                    Text {
                        anchors.centerIn: parent
                        text: "🔄"
                        font.pixelSize: 13
                    }
                    MouseArea {
                        id: refMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: root.isLocalMode ? "Rescan all local drives & heal moved artist paths" : "Refresh current page"
                        onClicked: {
                            if (!root.bBridge) return
                            if (root.hasSelectedCreator) {
                                root.bBridge.loadCreatorPosts(root.bBridge.creatorPostsOffset, creatorPostSearchInput.text)
                            } else {
                                root.bBridge.refresh(root.isLocalMode)
                            }
                        }
                    }
                }
            }
        }

        // ====================================================================
        // 2. SEARCH, SERVICE FILTER, TAG FILTER & SORT BAR
        // ====================================================================
        Rectangle {
            objectName: "browserSearchBar"
            Layout.fillWidth: true
            Layout.preferredHeight: searchBarCol.implicitHeight + 12
            visible: !root.hasSelectedCreator
            radius: 10
            color: "#0F131C"
            border.color: "#1E2536"
            border.width: 1
            clip: true

            ColumnLayout {
                id: searchBarCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                anchors.topMargin: 6
                spacing: 6

                Flow {
                    id: searchSortFlow
                    Layout.fillWidth: true
                    spacing: 8

                    readonly property bool tagVisible: !root.isLocalMode && !!root.activeCaps.supportsTagFilter
                    readonly property real minSearchTagW: tagVisible ? 318 : 180
                    readonly property real remainingForSearch: width - sortPillsFlow.width - spacing
                    readonly property bool sortFitsInline: sortPillsFlow.naturalWidth > 0 && remainingForSearch >= minSearchTagW && sortPillsFlow.naturalWidth <= width

                    // Search + optional Tag input group (stretches to fill remaining row width when wide, wraps cleanly when narrow)
                    Flow {
                        id: searchTagFlow
                        width: searchSortFlow.sortFitsInline ? searchSortFlow.remainingForSearch : searchSortFlow.width
                        spacing: 8

                        // Search Box
                        Rectangle {
                            id: mainSearchBox
                            width: {
                                if (!searchSortFlow.tagVisible) return searchTagFlow.width
                                var rem = searchTagFlow.width - 150 - searchTagFlow.spacing
                                return rem >= 160 ? rem : searchTagFlow.width
                            }
                            height: 32
                            radius: 7
                            color: "#090C12"
                            border.color: mainSearchInput.activeFocus ? "#38BDF8" : "#1E293B"
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 6

                                Text { text: "🔍"; font.pixelSize: 12; color: "#64748B" }

                                TextField {
                                    id: mainSearchInput
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    placeholderText: root.isLocalMode ? "Search local creators on disk…" : ("Search " + (root.activeManifest.name || "creators") + "…")
                                    placeholderTextColor: "#64748B"
                                    color: "#F8FAFC"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    background: Item {}
                                    selectByMouse: true
                                    onAccepted: if (root.bBridge) root.bBridge.search(text)
                                    onTextChanged: searchDebounce.restart()
                                }

                                Timer {
                                    id: searchDebounce
                                    interval: 340
                                    repeat: false
                                    onTriggered: if (root.bBridge) root.bBridge.search(mainSearchInput.text)
                                }

                                Text {
                                    visible: mainSearchInput.text.length > 0
                                    text: "✕"
                                    font.pixelSize: 11
                                    color: "#94A3B8"
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            mainSearchInput.text = ""
                                            if (root.bBridge) root.bBridge.search("")
                                        }
                                    }
                                }
                            }
                        }

                        // Tag Filter Input (shown when active provider supports tags, e.g. cum.st)
                        Rectangle {
                            visible: searchSortFlow.tagVisible
                            width: Math.min(150, searchTagFlow.width)
                            height: 32
                            radius: 7
                            color: "#090C12"
                            border.color: tagInput.activeFocus ? "#38BDF8" : "#1E293B"
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 4

                                Text { text: "🏷️"; font.pixelSize: 11 }
                                TextField {
                                    id: tagInput
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    placeholderText: "Tag (e.g. cosplay)"
                                    placeholderTextColor: "#64748B"
                                    color: "#38BDF8"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    background: Item {}
                                    selectByMouse: true
                                    onAccepted: if (root.bBridge) root.bBridge.setTagFilter(text)
                                }
                                Text {
                                    visible: tagInput.text.length > 0
                                    text: "✕"
                                    font.pixelSize: 10
                                    color: "#94A3B8"
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            tagInput.text = ""
                                            if (root.bBridge) root.bBridge.setTagFilter("")
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Dynamic Sort Pills (inline on wide screens, wraps seamlessly when Console narrows pane)
                    Flow {
                        id: sortPillsFlow
                        spacing: 4
                        property real naturalWidth: 120
                        width: Math.min(searchSortFlow.width, Math.max(1, naturalWidth))

                        function recalcW() {
                            var w = 0
                            var vis = 0
                            for (var i = 0; i < sortRepeater.count; ++i) {
                                var it = sortRepeater.itemAt(i)
                                if (it) {
                                    if (vis > 0) w += spacing
                                    w += it.implicitWidth
                                    vis++
                                }
                            }
                            naturalWidth = Math.max(1, w)
                        }

                        Repeater {
                            id: sortRepeater
                            model: root.isLocalMode
                                   ? [
                                       {"id": "updated", "label": "Recent"},
                                       {"id": "files_desc", "label": "Most Files"},
                                       {"id": "size_desc", "label": "Disk Size"},
                                       {"id": "name", "label": "A–Z"}
                                     ]
                                   : (root.activeCaps.sortOptions || [{"id": "popular", "label": "Popular"}])

                            onCountChanged: Qt.callLater(sortPillsFlow.recalcW)
                            onItemAdded: Qt.callLater(sortPillsFlow.recalcW)
                            onItemRemoved: Qt.callLater(sortPillsFlow.recalcW)

                            delegate: Rectangle {
                                readonly property var srt: modelData || ({})
                                readonly property bool isSel: (root.bBridge ? root.bBridge.activeSort : "popular") === srt.id

                                height: 28
                                implicitWidth: srtTxt.implicitWidth + 14
                                width: Math.min(sortPillsFlow.width, implicitWidth)
                                radius: 6
                                color: isSel ? "#172554" : "#121722"
                                border.color: isSel ? "#38BDF8" : "#1E293B"
                                border.width: 1
                                Springy { hover: srtMouse.containsMouse; pressed: srtMouse.pressed }
                                onImplicitWidthChanged: Qt.callLater(sortPillsFlow.recalcW)
                                Component.onCompleted: Qt.callLater(sortPillsFlow.recalcW)

                                Text {
                                    id: srtTxt
                                    anchors.centerIn: parent
                                    text: srt.label || srt.id
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: isSel ? Font.Bold : Font.Normal
                                    color: isSel ? "#F8FAFC" : "#94A3B8"
                                }
                                MouseArea {
                                    id: srtMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: if (root.bBridge) root.bBridge.setSortOrder(srt.id)
                                }
                            }
                        }
                    }
                }

                // Dynamic Service Filter Chips (Dedicated Full-Width Scrollable Bar)
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    spacing: 4

                    Rectangle {
                        id: svcLeftBtn
                        objectName: "servicesScrollLeftBtn"
                        visible: svcFlickable.canScrollLeft
                        Layout.preferredWidth: visible ? 22 : 0
                        Layout.preferredHeight: 28
                        Layout.alignment: Qt.AlignVCenter
                        radius: 6
                        color: svcLeftMouse.containsMouse ? "#1E293B" : "#121722"
                        border.color: svcLeftMouse.containsMouse ? "#38BDF8" : "#1E293B"
                        border.width: 1
                        Springy { hover: svcLeftMouse.containsMouse; pressed: svcLeftMouse.pressed }

                        Text {
                            anchors.centerIn: parent
                            text: "‹"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#94A3B8"
                        }
                        MouseArea {
                            id: svcLeftMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.scrollServicesBy(-180)
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 34

                        Flickable {
                            id: svcFlickable
                            objectName: "servicesFlickable"
                            anchors.fill: parent
                            contentWidth: svcRow.implicitWidth
                            contentHeight: 34
                            flickableDirection: Flickable.HorizontalFlick
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            readonly property bool canScrollHoriz: contentWidth > width + 2
                            readonly property bool canScrollLeft: contentX > 2
                            readonly property bool canScrollRight: canScrollHoriz && (contentX < contentWidth - width - 2)

                            onContentWidthChanged: {
                                var maxX = Math.max(0, contentWidth - width)
                                if (contentX > maxX) contentX = maxX
                            }
                            onWidthChanged: {
                                var maxX = Math.max(0, contentWidth - width)
                                if (contentX > maxX) contentX = maxX
                            }

                            WheelHandler {
                                id: svcWheel
                                target: null
                                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                                onWheel: function(event) {
                                    if (!svcFlickable.canScrollHoriz) {
                                        event.accepted = false
                                        return
                                    }
                                    var dx = Math.abs(event.pixelDelta.x) > 0
                                        ? -event.pixelDelta.x
                                        : (Math.abs(event.angleDelta.x) > 0
                                            ? -event.angleDelta.x * 0.5
                                            : -event.angleDelta.y * 0.5)
                                    if (Math.abs(dx) < 0.5) {
                                        event.accepted = false
                                        return
                                    }
                                    root.scrollServicesBy(dx)
                                    event.accepted = true
                                }
                            }

                            ScrollBar.horizontal: ScrollBar {
                                id: svcHBar
                                objectName: "servicesScrollBar"
                                policy: svcFlickable.canScrollHoriz ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                                interactive: true
                                height: 4
                                contentItem: Rectangle {
                                    implicitHeight: 3
                                    radius: 1.5
                                    color: svcHBar.pressed ? "#38BDF8" : (svcHBar.hovered ? "#64748B" : "#334155")
                                }
                                background: Rectangle {
                                    implicitHeight: 3
                                    radius: 1.5
                                    color: "transparent"
                                }
                            }

                            Row {
                                id: svcRow
                                height: 30
                                spacing: 5

                                Repeater {
                                    model: root.isLocalMode
                                           ? [
                                               {"id": "all", "label": "All Services"},
                                               {"id": "onlyfans", "label": "OnlyFans"},
                                               {"id": "fansly", "label": "Fansly"},
                                               {"id": "patreon", "label": "Patreon"},
                                               {"id": "fanbox", "label": "Fanbox"},
                                               {"id": "fantia", "label": "Fantia"},
                                               {"id": "candfans", "label": "CandFans"}
                                             ]
                                           : (root.activeCaps.services || [{"id": "all", "label": "All Services"}])

                                    delegate: Rectangle {
                                        readonly property var sItem: modelData || ({})
                                        readonly property bool isAct: (root.bBridge ? root.bBridge.activeService : "all") === sItem.id
                                        readonly property bool isFavChip: !root.isLocalMode && (sItem.id === "favorites")

                                        objectName: "serviceChip_" + (sItem.id || "")
                                        height: 27
                                        anchors.verticalCenter: parent.verticalCenter
                                        implicitWidth: sLbl.implicitWidth + 16
                                        radius: 6
                                        color: isFavChip
                                               ? (isAct ? "#422006" : "#1C160C")
                                               : (isAct ? "#1E293B" : "#121722")
                                        border.color: isFavChip
                                                      ? (isAct ? "#F59E0B" : "#78350F")
                                                      : (isAct ? "#38BDF8" : "#1E293B")
                                        border.width: 1
                                        Springy { hover: sMouse.containsMouse; pressed: sMouse.pressed }

                                        Text {
                                            id: sLbl
                                            anchors.centerIn: parent
                                            text: (sItem.label || sItem.id || "") + (isFavChip && !root.isActiveProviderLoggedIn ? " 🔒" : "")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: (isAct || isFavChip) ? Font.Bold : Font.Normal
                                            color: isFavChip
                                                   ? (isAct ? "#FBBF24" : "#FCD34D")
                                                   : (isAct ? "#38BDF8" : "#94A3B8")
                                        }
                                        MouseArea {
                                            id: sMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (root.bBridge) root.bBridge.setServiceFilter(sItem.id)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        id: svcRightBtn
                        objectName: "servicesScrollRightBtn"
                        visible: svcFlickable.canScrollRight
                        Layout.preferredWidth: visible ? 22 : 0
                        Layout.preferredHeight: 28
                        Layout.alignment: Qt.AlignVCenter
                        radius: 6
                        color: svcRightMouse.containsMouse ? "#1E293B" : "#121722"
                        border.color: svcRightMouse.containsMouse ? "#38BDF8" : "#1E293B"
                        border.width: 1
                        Springy { hover: svcRightMouse.containsMouse; pressed: svcRightMouse.pressed }

                        Text {
                            anchors.centerIn: parent
                            text: "›"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#94A3B8"
                        }
                        MouseArea {
                            id: svcRightMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.scrollServicesBy(180)
                        }
                    }
                }
            }
        }

        // ====================================================================
        // 3. CREATOR PROFILE HEADER (VISIBLE WHEN A CREATOR IS OPENED)
        // ====================================================================
        Rectangle {
            objectName: "browserCreatorBanner"
            Layout.fillWidth: true
            Layout.preferredHeight: root.hasSelectedCreator ? Math.max(82, bannerMainLayout.implicitHeight + 20) : 0
            visible: root.hasSelectedCreator
            clip: true
            radius: 10
            color: "#111622"
            border.color: "#26324B"
            border.width: 1

            Behavior on Layout.preferredHeight {
                NumberAnimation { duration: 130; easing.type: Easing.OutCubic }
            }

            ColumnLayout {
                id: bannerMainLayout
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 10
                spacing: 8

                Flow {
                    id: creatorHeaderFlow
                    Layout.fillWidth: true
                    spacing: 10

                    readonly property bool searchFitsInline: width >= 540

                    RowLayout {
                        id: creatorHeaderIdentityRow
                        width: creatorHeaderFlow.searchFitsInline
                               ? Math.max(200, creatorHeaderFlow.width - creatorPostSearchBox.width - creatorHeaderFlow.spacing)
                               : creatorHeaderFlow.width
                        spacing: 10

                        // Back to Creators Grid button
                        Rectangle {
                            Layout.preferredHeight: 34
                            Layout.preferredWidth: backRow.implicitWidth + 18
                            Layout.alignment: Qt.AlignVCenter
                            radius: 7
                            color: backMouse.containsMouse ? "#1E293B" : "#151C2B"
                            border.color: "#38BDF8"
                            border.width: 1
                            Springy { hover: backMouse.containsMouse; pressed: backMouse.pressed }

                            Row {
                                id: backRow
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "←"; font.pixelSize: 13; font.bold: true; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                                Text {
                                    text: "All Creators"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    font.weight: Font.Bold
                                    color: "#F8FAFC"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            MouseArea {
                                id: backMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (root.bBridge) root.bBridge.closeCreator()
                            }
                        }

                        // Creator Avatar
                        Rectangle {
                            Layout.preferredWidth: 44
                            Layout.preferredHeight: 44
                            Layout.alignment: Qt.AlignVCenter
                            radius: 22
                            color: "#1E293B"
                            border.color: "#38BDF8"
                            border.width: 1.5
                            clip: true

                            Text {
                                anchors.centerIn: parent
                                visible: hdrAvatarImg.status !== Image.Ready || hdrAvatarImg.implicitWidth <= 2
                                text: ((root.selectedCreator.name || root.selectedCreator.creator_name || "?").trim().charAt(0) || "?").toUpperCase()
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 16
                                font.weight: Font.Bold
                                color: "#7DD3FC"
                            }

                            Image {
                                id: hdrAvatarImg
                                anchors.fill: parent
                                opacity: (status === Image.Ready && implicitWidth > 2) ? 1.0 : 0.0
                                source: root.browserThumbUrl(root.selectedCreator.avatar_url, root.selectedCreator.provider_id || root.activeProvider)
                                sourceSize: Qt.size(96, 96)
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                            }
                        }

                        // Creator Name & Telemetry Badges
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3

                            Flow {
                                id: creatorNameBadgesFlow
                                Layout.fillWidth: true
                                spacing: 6

                                Text {
                                    width: Math.min(implicitWidth, Math.min(260, Math.max(80, creatorNameBadgesFlow.width)))
                                    text: root.selectedCreator.name || root.selectedCreator.creator_name || ""
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 15
                                    font.weight: Font.Bold
                                    color: "#F8FAFC"
                                    elide: Text.ElideRight
                                }
                                Rectangle {
                                    height: 20
                                    width: Math.min(creatorNameBadgesFlow.width, hdrSvcTxt.implicitWidth + 12)
                                    radius: 5
                                    color: "#1E293B"
                                    Text {
                                        id: hdrSvcTxt
                                        anchors.centerIn: parent
                                        text: (root.selectedCreator.service_label || root.selectedCreator.service || "").toUpperCase()
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        font.weight: Font.Bold
                                        color: "#38BDF8"
                                    }
                                }
                                UnimportedTriangleBadge {
                                    objectName: "bannerUnimportedBadge"
                                    visible: !root.isLocalMode && !!root.selectedCreator.is_unimported
                                    width: 22
                                    height: 22
                                    tooltipText: "Previews only (creator not yet imported)"
                                }
                                // Local Drive Badges
                                Repeater {
                                    model: root.selectedCreator.local_drives || []
                                    delegate: Rectangle {
                                        height: 20
                                        width: Math.min(creatorNameBadgesFlow.width, drvBadgeTxt.implicitWidth + 12)
                                        radius: 5
                                        color: "#064E3B"
                                        border.color: "#10B981"
                                        border.width: 1
                                        Text {
                                            id: drvBadgeTxt
                                            anchors.centerIn: parent
                                            text: "💽 " + modelData
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            color: "#A7F3D0"
                                        }
                                    }
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: root.isLocalMode
                                      ? (Number(root.bBridge ? root.bBridge.creatorPostsTotal : 0) + " local posts • " + Number(root.selectedCreator.local_file_count || 0) + " files on disk (" + root.formatBytes(root.selectedCreator.local_size_bytes) + ")")
                                      : (root.bBridge && root.bBridge.creatorSection === "dms"
                                         ? (Number(root.bBridge.creatorPostsTotal || 0) + " DM(s) available")
                                         : (Number(root.bBridge ? root.bBridge.creatorPostsTotal : 0) + " posts available"
                                            + (Number(root.selectedCreator.dm_count || 0) > 0 ? (" • 💬 " + Number(root.selectedCreator.dm_count || 0) + " DMs") : "")))
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                        }
                    }

                    // Search within Creator's Posts / DMs (wraps seamlessly to own row when Console narrows pane)
                    Rectangle {
                        id: creatorPostSearchBox
                        width: creatorHeaderFlow.searchFitsInline ? 195 : creatorHeaderFlow.width
                        height: 32
                        radius: 7
                        color: "#090C12"
                        border.color: creatorPostSearchInput.activeFocus ? "#38BDF8" : "#1E293B"
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 5
                            Text { text: "🔍"; font.pixelSize: 11 }
                            TextField {
                                id: creatorPostSearchInput
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                placeholderText: (root.bBridge && root.bBridge.creatorSection === "dms") ? "Filter creator's DMs…" : "Filter creator's posts…"
                                placeholderTextColor: "#64748B"
                                color: "#F8FAFC"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                background: Item {}
                                selectByMouse: true
                                onAccepted: if (root.bBridge) root.bBridge.loadCreatorPosts(0, text)
                            }
                        }
                    }
                }

                // Responsive Action Toolbar (wraps cleanly on narrower panes so buttons never clip)
                Flow {
                    id: creatorActionsFlow
                    Layout.fillWidth: true
                    spacing: 8

                    // Creator Posts | DMs Section Toggle (when active provider supports DMs)
                    Rectangle {
                        id: creatorSectionToggle
                        visible: !root.isLocalMode && !!(root.bBridge && root.bBridge.creatorSupportsDms)
                        height: 30
                        width: sectionToggleRow.implicitWidth + 8
                        radius: 7
                        color: "#090C12"
                        border.color: "#1E293B"
                        border.width: 1

                        Row {
                            id: sectionToggleRow
                            anchors.centerIn: parent
                            spacing: 3

                            Rectangle {
                                height: 24
                                width: postsSecTxt.implicitWidth + 14
                                radius: 5
                                color: (!root.bBridge || root.bBridge.creatorSection !== "dms") ? "#0284C7" : (postsSecMouse.containsMouse ? "#151E2E" : "transparent")
                                Text {
                                    id: postsSecTxt
                                    anchors.centerIn: parent
                                    text: "Posts"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: (!root.bBridge || root.bBridge.creatorSection !== "dms") ? Font.Bold : Font.Normal
                                    color: (!root.bBridge || root.bBridge.creatorSection !== "dms") ? "#FFFFFF" : "#94A3B8"
                                }
                                MouseArea {
                                    id: postsSecMouse
                                    objectName: "creatorSection_posts"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (root.bBridge) {
                                            creatorPostSearchInput.text = ""
                                            root.bBridge.setCreatorSection("posts")
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                height: 24
                                width: dmsSecTxt.implicitWidth + 14
                                radius: 5
                                color: (root.bBridge && root.bBridge.creatorSection === "dms") ? "#7C3AED" : (dmsSecMouse.containsMouse ? "#151E2E" : "transparent")
                                Text {
                                    id: dmsSecTxt
                                    anchors.centerIn: parent
                                    text: "💬 DMs" + (Number(root.selectedCreator.dm_count || 0) > 0 ? (" (" + Number(root.selectedCreator.dm_count || 0) + ")") : "")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: (root.bBridge && root.bBridge.creatorSection === "dms") ? Font.Bold : Font.Normal
                                    color: (root.bBridge && root.bBridge.creatorSection === "dms") ? "#FFFFFF" : "#C4B5FD"
                                }
                                MouseArea {
                                    id: dmsSecMouse
                                    objectName: "creatorSection_dms"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (root.bBridge) {
                                            creatorPostSearchInput.text = ""
                                            root.bBridge.setCreatorSection("dms")
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Queue All Creator DMs Button (visible when viewing DMs section)
                    Rectangle {
                        visible: !root.isLocalMode && !!(root.bBridge && root.bBridge.creatorSection === "dms")
                        height: 30
                        width: dlDmsRow.implicitWidth + 16
                        radius: 7
                        color: dlDmsMouse.containsMouse ? "#8B5CF6" : "#6D28D9"
                        border.color: "#A78BFA"
                        border.width: 1
                        Springy { hover: dlDmsMouse.containsMouse; pressed: dlDmsMouse.pressed }

                        Row {
                            id: dlDmsRow
                            anchors.centerIn: parent
                            spacing: 5
                            Text { text: "⬇"; font.pixelSize: 11; color: "#FFFFFF"; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                text: "Download All DMs"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: dlDmsMouse
                            objectName: "downloadAllDmsMouse"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (root.bBridge) root.bBridge.queueAllCreatorDms()
                        }
                    }

                    // LOCAL MODE: Move Creator to Another Drive Button
                    Rectangle {
                        visible: root.isLocalMode
                        height: 30
                        width: mvHdrRow.implicitWidth + 18
                        radius: 7
                        color: mvHdrMouse.containsMouse ? "#065F46" : "#064E3B"
                        border.color: "#10B981"
                        border.width: 1
                        Springy { hover: mvHdrMouse.containsMouse; pressed: mvHdrMouse.pressed }

                        Row {
                            id: mvHdrRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: "💽"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                text: "Move Creator to Drive…"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#ECFDF5"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: mvHdrMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: "Relocate this artist's downloaded files to another disk while keeping Archive & Watchlist in sync"
                            onClicked: {
                                root.creatorToRelocate = root.selectedCreator
                                moveCreatorDriveModal.open()
                            }
                        }
                    }

                    // Check Newer Posts Online Button (Local & Online Modes)
                    Rectangle {
                        id: checkNewPostsBtn
                        visible: !!(root.selectedCreator && root.selectedCreator.key && (root.isLocalMode || root.selectedCreator.url))
                        height: 30
                        width: chkNewRow.implicitWidth + 18
                        radius: 7
                        color: (root.bBridge && root.bBridge.newPostsCount > 0)
                               ? (chkNewMouse.containsMouse ? "#065F46" : "#064E3B")
                               : (chkNewMouse.containsMouse ? "#1E293B" : "#151C2B")
                        border.color: (root.bBridge && root.bBridge.newPostsCount > 0) ? "#10B981" : "#38BDF8"
                        border.width: 1
                        Springy { hover: chkNewMouse.containsMouse; pressed: chkNewMouse.pressed }

                        Row {
                            id: chkNewRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                text: (root.bBridge && root.bBridge.isCheckingNewPosts) ? "⌛" : "🔎"
                                font.pixelSize: 12
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: (root.bBridge && root.bBridge.isCheckingNewPosts)
                                      ? "Checking…"
                                      : ((root.bBridge && root.bBridge.newPostsCount > 0)
                                         ? ("Newer Posts (" + root.bBridge.newPostsCount + ")")
                                         : "Check Newer Posts")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: (root.bBridge && root.bBridge.newPostsCount > 0) ? "#ECFDF5" : "#E0F2FE"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: chkNewMouse
                            objectName: "checkNewPostsBtnMouse"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: "Check online for newer posts by this creator not yet on disk"
                            onClicked: {
                                if (root.bBridge) {
                                    root.bBridge.checkCreatorNewPosts(root.selectedCreator)
                                    newPostsModal.open()
                                }
                            }
                        }
                    }

                    // Favorite / Bookmark Creator on Account Button (Online Mode)
                    Rectangle {
                        objectName: "bannerCreatorFavBtn"
                        visible: !root.isLocalMode && !!root.activeCaps.supportsFavorites
                        readonly property bool isFav: !!root.selectedCreator.is_favorited
                        height: 30
                        width: bannerFavRow.implicitWidth + 18
                        radius: 7
                        color: isFav
                               ? (bannerFavMouse.containsMouse ? "#92400E" : "#78350F")
                               : (bannerFavMouse.containsMouse ? "#1E293B" : "#151C2B")
                        border.color: isFav ? "#F59E0B" : "#475569"
                        border.width: 1
                        Springy { hover: bannerFavMouse.containsMouse; pressed: bannerFavMouse.pressed }

                        Row {
                            id: bannerFavRow
                            anchors.centerIn: parent
                            spacing: 5
                            Text {
                                text: parent.parent.isFav ? "★" : "☆"
                                font.pixelSize: 13
                                color: parent.parent.isFav ? "#FBBF24" : "#94A3B8"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: parent.parent.isFav ? "Favorited" : "Favorite"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: parent.parent.isFav ? "#FDE68A" : "#CBD5E1"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: bannerFavMouse
                            objectName: "bannerCreatorFavMouse"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (root.bBridge && root.selectedCreator) root.bBridge.toggleFavoriteCreator(root.selectedCreator)
                        }
                    }

                    // Mark Whole Creator Button
                    Rectangle {
                        visible: !root.isLocalMode
                        readonly property bool isMarked: !!root.selectedCreator.is_marked
                        height: 30
                        width: mkCreatorRow.implicitWidth + 18
                        radius: 7
                        color: isMarked ? "#2E1065" : (mkCreatorMouse.containsMouse ? "#1E293B" : "#151C2B")
                        border.color: isMarked ? "#A78BFA" : "#38BDF8"
                        border.width: 1
                        Springy { hover: mkCreatorMouse.containsMouse; pressed: mkCreatorMouse.pressed }

                        Row {
                            id: mkCreatorRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: parent.parent.isMarked ? "✔" : "🛒"; font.pixelSize: 11; color: "#C4B5FD"; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                text: parent.parent.isMarked ? "Creator Marked" : "Mark Creator"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#F8FAFC"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: mkCreatorMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (root.bBridge) root.bBridge.toggleMarkItem(root.selectedCreator)
                        }
                    }

                    // Download Entire Creator Immediately
                    Rectangle {
                        readonly property bool isDispatched: root.isUrlDispatched(root.selectedCreator.url)
                        visible: !root.isLocalMode && !!(root.selectedCreator.url)
                        height: 30
                        width: dlCreatorRow.implicitWidth + 18
                        radius: 7
                        color: isDispatched
                               ? (dlCreatorMouse.containsMouse ? "#0F766E" : "#115E59")
                               : (dlCreatorMouse.containsMouse ? "#059669" : "#047857")
                        border.color: isDispatched ? "#5EEAD4" : "#34D399"
                        border.width: 1
                        Springy { hover: dlCreatorMouse.containsMouse; pressed: dlCreatorMouse.pressed }

                        Row {
                            id: dlCreatorRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: parent.parent.isDispatched ? "✓" : "🚀"; font.pixelSize: 11; color: "#FFFFFF"; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                text: parent.parent.isDispatched ? "Started" : "Download All"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: dlCreatorMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: parent.isDispatched ? "Sent to Downloader — click again to queue another download" : "Send this creator directly to the Downloader"
                            onClicked: root.triggerItemDownload(
                                root.selectedCreator.url,
                                true,
                                root.selectedCreator.name || root.selectedCreator.creator_name || ""
                            )
                        }
                    }

                    // Copy Creator Link Button (always available for active creator)
                    Rectangle {
                        id: creatorCopyLinkBtn
                        objectName: "creatorCopyLinkBtn"
                        property bool justCopied: false
                        visible: !!root.selectedCreator && !!(root.selectedCreator.key || root.selectedCreator.url || (root.selectedCreator.local_dirs && root.selectedCreator.local_dirs.length > 0))
                        height: 30
                        width: creatorCopyRow.implicitWidth + 16
                        radius: 7
                        color: justCopied
                               ? "#064E3B"
                               : (creatorCopyMouse.containsMouse ? "#1E293B" : "#151C2B")
                        border.color: justCopied ? "#10B981" : (creatorCopyMouse.containsMouse ? "#38BDF8" : "#334155")
                        border.width: 1
                        Springy { hover: creatorCopyMouse.containsMouse; pressed: creatorCopyMouse.pressed }
                        Timer {
                            id: creatorCopyResetTimer
                            interval: 1500
                            onTriggered: creatorCopyLinkBtn.justCopied = false
                        }
                        Row {
                            id: creatorCopyRow
                            anchors.centerIn: parent
                            spacing: 5
                            Text {
                                text: creatorCopyLinkBtn.justCopied ? "✓" : "🔗"
                                font.pixelSize: 11
                                color: creatorCopyLinkBtn.justCopied ? "#6EE7B7" : "#7DD3FC"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: creatorCopyLinkBtn.justCopied ? "Copied" : "Copy Link"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: creatorCopyLinkBtn.justCopied ? "#A7F3D0" : "#E2E8F0"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: creatorCopyMouse
                            objectName: "creatorCopyLinkMouse"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Copy link to this creator"
                            onClicked: {
                                if (root.bBridge && root.bBridge.copyCreatorLink(root.selectedCreator)) {
                                    creatorCopyLinkBtn.justCopied = true
                                    creatorCopyResetTimer.restart()
                                }
                            }
                        }
                    }
                }
            }
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

                // ── A. VIRTUALIZED CREATORS GRID ─────────────────────────────
                SmoothGridView {
                    id: creatorsGrid
                    property int markAnchor: -1
                    property string markAnchorKey: ""
                    property bool markAnchorState: true
                    anchors.fill: parent
                    visible: !parent.parent.showingPostsGrid
                    cellWidth: width > 0 ? Math.min(width, Math.max(220, Math.floor(width / Math.max(1, Math.floor(width / 260))))) : 240
                    cellHeight: 164
                    cacheBuffer: 640
                    model: root.bBridge ? root.bBridge.creatorsModel : null

                    delegate: Item {
                        width: creatorsGrid.cellWidth
                        height: creatorsGrid.cellHeight

                        readonly property var cData: model.creator || modelData || ({})
                        readonly property bool isMarked: !!cData.is_marked
                        readonly property bool onDisk: !!cData.is_on_disk

                        Rectangle {
                            id: cCard
                            anchors.fill: parent
                            anchors.margins: 5
                            radius: 10
                            color: cCardHover.hovered ? "#161E2E" : "#111622"
                            border.color: isMarked ? "#A78BFA" : (onDisk ? "#10B981" : (cCardHover.hovered ? "#38BDF8" : "#1E293B"))
                            border.width: (isMarked || onDisk) ? 1.5 : 1
                            clip: true

                            HoverHandler { id: cCardHover }

                            ColumnLayout {
                                z: 1
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 8

                                // Top Row: Avatar + Name + Service + Mark Button
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10

                                    Rectangle {
                                        Layout.preferredWidth: 46
                                        Layout.preferredHeight: 46
                                        radius: 23
                                        color: "#1E293B"
                                        border.color: onDisk ? "#10B981" : "#334155"
                                        border.width: 1
                                        clip: true

                                        Text {
                                            anchors.centerIn: parent
                                            visible: cardAvatarImg.status !== Image.Ready || cardAvatarImg.implicitWidth <= 2
                                            text: ((cData.name || cData.creator_name || "?").trim().charAt(0) || "?").toUpperCase()
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 17
                                            font.weight: Font.Bold
                                            color: "#7DD3FC"
                                        }

                                        Image {
                                            id: cardAvatarImg
                                            anchors.fill: parent
                                            opacity: (status === Image.Ready && implicitWidth > 2) ? 1.0 : 0.0
                                            source: root.browserThumbUrl(cData.avatar_url, cData.provider_id || root.activeProvider)
                                            sourceSize: Qt.size(96, 96)
                                            fillMode: Image.PreserveAspectCrop
                                            asynchronous: true
                                            cache: true
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2

                                        Text {
                                            Layout.fillWidth: true
                                            text: cData.name || cData.creator_name || "Unknown"
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 13
                                            font.weight: Font.Bold
                                            color: "#F8FAFC"
                                            elide: Text.ElideRight
                                        }

                                        RowLayout {
                                            spacing: 5
                                            Rectangle {
                                                height: 18
                                                implicitWidth: svcBadgeTxt.implicitWidth + 10
                                                radius: 4
                                                color: "#1E293B"
                                                Text {
                                                    id: svcBadgeTxt
                                                    anchors.centerIn: parent
                                                    text: (cData.service_label || cData.service || "").toUpperCase()
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 9
                                                    font.weight: Font.Bold
                                                    color: "#38BDF8"
                                                }
                                            }
                                            Text {
                                                visible: !!(cData.updated_at)
                                                text: cData.updated_at || ""
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 10
                                                color: "#64748B"
                                            }
                                        }
                                    }

                                    UnimportedTriangleBadge {
                                        objectName: "creatorUnimportedBadge"
                                        visible: !root.isLocalMode && !!cData.is_unimported
                                        Layout.preferredWidth: 24
                                        Layout.preferredHeight: 24
                                        width: 24
                                        height: 24
                                        z: 3
                                        tooltipText: "Previews only (creator not yet imported)"
                                    }

                                    // Favorite / Unfavorite Creator Button (Online Mode)
                                    Rectangle {
                                        objectName: "creatorFavBtn"
                                        visible: !root.isLocalMode && !!root.activeCaps.supportsFavorites
                                        readonly property bool isFav: !!cData.is_favorited
                                        Layout.preferredWidth: 30
                                        Layout.preferredHeight: 30
                                        radius: 7
                                        z: 3
                                        color: isFav ? "#422006" : (creatorFavMouse.containsMouse ? "#1E293B" : "#151C2B")
                                        border.color: isFav ? "#F59E0B" : "#334155"
                                        border.width: 1
                                        Springy { hover: creatorFavMouse.containsMouse; pressed: creatorFavMouse.pressed }

                                        Text {
                                            id: creatorFavStarTxt
                                            objectName: "creatorFavStarTxt"
                                            anchors.centerIn: parent
                                            text: parent.isFav ? "★" : "☆"
                                            font.pixelSize: 14
                                            font.weight: Font.Bold
                                            color: parent.isFav ? "#FBBF24" : "#94A3B8"
                                        }
                                        MouseArea {
                                            id: creatorFavMouse
                                            objectName: "creatorFavMouse"
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            preventStealing: true
                                            cursorShape: Qt.PointingHandCursor
                                            ToolTip.visible: containsMouse
                                            ToolTip.text: parent.isFav
                                                          ? "Remove from " + root.activeProviderDisplayName + " favorites"
                                                          : "Add to " + root.activeProviderDisplayName + " favorites"
                                            onClicked: {
                                                if (root.bBridge && cData) {
                                                    root.bBridge.toggleFavoriteCreator(cData)
                                                }
                                            }
                                        }
                                    }

                                    // Mark / Unmark Creator Button (Online Mode)
                                    Rectangle {
                                        visible: !root.isLocalMode
                                        Layout.preferredWidth: 30
                                        Layout.preferredHeight: 30
                                        radius: 7
                                        z: 3
                                        color: isMarked ? "#4C1D95" : (mkMouse.containsMouse ? "#1E293B" : "#151C2B")
                                        border.color: isMarked ? "#A78BFA" : "#334155"
                                        border.width: 1
                                        Springy { hover: mkMouse.containsMouse; pressed: mkMouse.pressed }

                                        Text {
                                            anchors.centerIn: parent
                                            text: isMarked ? "✔" : "🛒"
                                            font.pixelSize: 12
                                            color: isMarked ? "#DDD6FE" : "#94A3B8"
                                        }
                                        MouseArea {
                                            id: mkMouse
                                            objectName: "creatorMarkMouse"
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 300
                                            ToolTip.text: (isMarked ? "Remove creator from Download Cart" : "Mark creator for Download Cart") + "\nShift+click to mark/unmark a range"
                                            onClicked: (mouse) => root.handleRangeMarkClick("creators", creatorsGrid, index, cData, (mouse.modifiers & Qt.ShiftModifier) !== 0)
                                        }
                                    }
                                }

                                // Middle Row: Telemetry Chips (Posts / Videos / Images / Disk Size / Drives)
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 5

                                    Rectangle {
                                        visible: Number(cData.post_count || 0) > 0
                                        height: 20
                                        width: pCntTxt.implicitWidth + 12
                                        radius: 5
                                        color: "#0F172A"
                                        Text {
                                            id: pCntTxt
                                            anchors.centerIn: parent
                                            text: "📄 " + Number(cData.post_count || 0) + " posts"
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            color: "#CBD5E1"
                                        }
                                    }

                                    Rectangle {
                                        visible: !root.isLocalMode && Number(cData.video_count || 0) > 0
                                        height: 20
                                        width: vCntTxt.implicitWidth + 12
                                        radius: 5
                                        color: "#0F172A"
                                        Text {
                                            id: vCntTxt
                                            anchors.centerIn: parent
                                            text: "🎬 " + Number(cData.video_count || 0)
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            color: "#38BDF8"
                                        }
                                    }

                                    Rectangle {
                                        visible: !root.isLocalMode && Number(cData.image_count || 0) > 0
                                        height: 20
                                        width: iCntTxt.implicitWidth + 12
                                        radius: 5
                                        color: "#0F172A"
                                        Text {
                                            id: iCntTxt
                                            anchors.centerIn: parent
                                            text: "🖼️ " + Number(cData.image_count || 0)
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            color: "#A78BFA"
                                        }
                                    }

                                    Rectangle {
                                        visible: !root.isLocalMode && Number(cData.dm_count || 0) > 0
                                        height: 20
                                        width: dmCntTxt.implicitWidth + 12
                                        radius: 5
                                        color: "#2E1065"
                                        Text {
                                            id: dmCntTxt
                                            anchors.centerIn: parent
                                            text: "💬 " + Number(cData.dm_count || 0)
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            font.weight: Font.Bold
                                            color: "#E9D5FF"
                                        }
                                    }

                                    // Local Mode: File count & Disk size chip
                                    Rectangle {
                                        visible: root.isLocalMode
                                        height: 20
                                        width: locSzTxt.implicitWidth + 12
                                        radius: 5
                                        color: "#0F172A"
                                        Text {
                                            id: locSzTxt
                                            anchors.centerIn: parent
                                            text: "📁 " + Number(cData.local_file_count || 0) + " files • " + root.formatBytes(cData.local_size_bytes)
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            color: "#94A3B8"
                                        }
                                    }

                                    // Drive Badges in Local Mode
                                    Repeater {
                                        model: cData.local_drives || []
                                        delegate: Rectangle {
                                            height: 20
                                            width: dTxt.implicitWidth + 10
                                            radius: 5
                                            color: "#064E3B"
                                            border.color: "#10B981"
                                            border.width: 1
                                            Text {
                                                id: dTxt
                                                anchors.centerIn: parent
                                                text: "💽 " + modelData
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 9
                                                font.weight: Font.Bold
                                                color: "#A7F3D0"
                                            }
                                        }
                                    }
                                }

                                Item { Layout.fillHeight: true }

                                // Bottom Row: Action Strip
                                RowLayout {
                                    id: cCardActionRow
                                    Layout.fillWidth: true
                                    spacing: 6

                                    TextMetrics {
                                        id: onDiskMetrics
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        font.weight: Font.Bold
                                        text: "On Disk (" + Number(cData.local_post_count || 1) + ") • Open Local"
                                    }

                                    // Online Mode: "Already on Disk" badge -> Click to open in Local Mode
                                    Rectangle {
                                        visible: !root.isLocalMode && onDisk
                                        Layout.preferredHeight: 24
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 64
                                        Layout.maximumWidth: onDiskMetrics.width + 32
                                        radius: 5
                                        z: 3
                                        clip: true
                                        color: onDiskMouse.containsMouse ? "#065F46" : "#064E3B"
                                        border.color: "#10B981"
                                        border.width: 1

                                        RowLayout {
                                            id: onDiskRow
                                            anchors.fill: parent
                                            anchors.leftMargin: 6
                                            anchors.rightMargin: 6
                                            spacing: 4
                                            Text { text: "💾"; font.pixelSize: 10 }
                                            Text {
                                                Layout.fillWidth: true
                                                text: onDiskMetrics.text
                                                font: onDiskMetrics.font
                                                color: "#A7F3D0"
                                                elide: Text.ElideRight
                                            }
                                        }
                                        MouseArea {
                                            id: onDiskMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (root.bBridge) root.bBridge.openCreatorInLocalMode(cData)
                                        }
                                    }

                                    TextMetrics {
                                        id: mvCardMetrics
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        font.weight: 600
                                        text: "Move Drive…"
                                    }

                                    // Local Mode: 1-Click Move to Another Drive button
                                    Rectangle {
                                        visible: root.isLocalMode
                                        Layout.preferredHeight: 24
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 64
                                        Layout.maximumWidth: mvCardMetrics.width + 32
                                        radius: 5
                                        z: 3
                                        clip: true
                                        color: mvCardMouse.containsMouse ? "#1E293B" : "#151C2B"
                                        border.color: "#38BDF8"
                                        border.width: 1
                                        Springy { hover: mvCardMouse.containsMouse; pressed: mvCardMouse.pressed }

                                        RowLayout {
                                            id: mvCardRow
                                            anchors.fill: parent
                                            anchors.leftMargin: 6
                                            anchors.rightMargin: 6
                                            spacing: 4
                                            Text { text: "💽"; font.pixelSize: 10 }
                                            Text {
                                                Layout.fillWidth: true
                                                text: mvCardMetrics.text
                                                font: mvCardMetrics.font
                                                color: "#7DD3FC"
                                                elide: Text.ElideRight
                                            }
                                        }
                                        MouseArea {
                                            id: mvCardMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                root.creatorToRelocate = cData
                                                moveCreatorDriveModal.open()
                                            }
                                        }
                                    }

                                    Item { Layout.fillWidth: true }

                                    Rectangle {
                                        id: cCardCopyBtn
                                        objectName: "creatorCardCopyLinkBtn"
                                        property bool justCopied: false
                                        Layout.preferredWidth: 24
                                        Layout.preferredHeight: 22
                                        radius: 5
                                        z: 3
                                        color: justCopied
                                               ? "#064E3B"
                                               : (cCardCopyMouse.containsMouse ? "#1E293B" : "#151C2B")
                                        border.color: justCopied ? "#10B981" : (cCardCopyMouse.containsMouse ? "#38BDF8" : "#334155")
                                        border.width: 1
                                        Springy { hover: cCardCopyMouse.containsMouse; pressed: cCardCopyMouse.pressed }
                                        Timer {
                                            id: cCardCopyTimer
                                            interval: 1500
                                            onTriggered: cCardCopyBtn.justCopied = false
                                        }
                                        Text {
                                            anchors.centerIn: parent
                                            text: cCardCopyBtn.justCopied ? "✓" : "🔗"
                                            font.pixelSize: 10
                                            color: cCardCopyBtn.justCopied ? "#6EE7B7" : "#7DD3FC"
                                        }
                                        MouseArea {
                                            id: cCardCopyMouse
                                            objectName: "creatorCardCopyLinkMouse"
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 250
                                            ToolTip.text: "Copy creator link"
                                            onClicked: (mouse) => {
                                                mouse.accepted = true
                                                if (root.bBridge && root.bBridge.copyCreatorLink(cData)) {
                                                    cCardCopyBtn.justCopied = true
                                                    cCardCopyTimer.restart()
                                                }
                                            }
                                        }
                                    }

                                    Text {
                                        id: browsePostsTxt
                                        text: "Browse Posts →"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: 600
                                        color: "#38BDF8"
                                    }
                                }
                            }

                            MouseArea {
                                id: cardBodyMouse
                                anchors.fill: parent
                                z: 0
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (root.bBridge) root.bBridge.openCreator(cData)
                            }
                        }
                    }
                }

                // Centered Auth / Favorites Login Prompt Card when grid is empty & login required
                Rectangle {
                    id: browserAuthPromptCard
                    objectName: "browserAuthPromptCard"
                    visible: !parent.parent.showingPostsGrid && root.bBridge && !root.bBridge.isLoading && creatorsGrid.count === 0 && root.bBridge.authRequired
                    anchors.centerIn: parent
                    width: Math.min(440, parent.width - 32)
                    implicitHeight: authPromptCol.implicitHeight + 36
                    radius: 12
                    color: "#0F1420"
                    border.color: "#F59E0B"
                    border.width: 1.5

                    ColumnLayout {
                        id: authPromptCol
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 12

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: "🔐"
                            font.pixelSize: 30
                        }
                        Text {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: (root.bBridge && root.bBridge.activeService === "favorites")
                                  ? ("Sign in to " + root.activeProviderDisplayName + " to view your favorited creators")
                                  : ("Sign in to " + root.activeProviderDisplayName + " required")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                        }
                        Text {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: (root.bBridge && root.bBridge.errorMessage)
                                  ? root.bBridge.errorMessage
                                  : ("Your " + root.activeProviderDisplayName + " account credentials or browser session cookies let you load and sync favorites.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#94A3B8"
                        }
                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter
                            spacing: 10

                            Rectangle {
                                Layout.preferredHeight: 34
                                implicitWidth: authPromptBtnTxt.implicitWidth + 24
                                radius: 7
                                color: authPromptLoginMouse.containsMouse ? "#D97706" : "#F59E0B"
                                Springy { hover: authPromptLoginMouse.containsMouse; pressed: authPromptLoginMouse.pressed }
                                Text {
                                    id: authPromptBtnTxt
                                    anchors.centerIn: parent
                                    text: "🔑 Log In to " + root.activeProviderDisplayName
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    font.weight: Font.Bold
                                    color: "#0F172A"
                                }
                                MouseArea {
                                    id: authPromptLoginMouse
                                    objectName: "authPromptLoginBtn"
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

                            Rectangle {
                                visible: !!(root.bBridge && root.bBridge.activeService === "favorites")
                                Layout.preferredHeight: 34
                                implicitWidth: authPromptBackTxt.implicitWidth + 20
                                radius: 7
                                color: authPromptBackMouse.containsMouse ? "#1E293B" : "#151C2B"
                                border.color: "#334155"
                                border.width: 1
                                Text {
                                    id: authPromptBackTxt
                                    anchors.centerIn: parent
                                    text: "Browse All Services"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    color: "#CBD5E1"
                                }
                                MouseArea {
                                    id: authPromptBackMouse
                                    objectName: "authPromptAllServicesBtn"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: if (root.bBridge) root.bBridge.setServiceFilter("all")
                                }
                            }
                        }
                    }
                }

                // ── B. VIRTUALIZED POSTS GRID (Creator Posts or Global Posts) ─
                SmoothGridView {
                    id: postsGrid
                    property int markAnchor: -1
                    property string markAnchorKey: ""
                    property bool markAnchorState: true
                    anchors.fill: parent
                    visible: parent.parent.showingPostsGrid
                    cellWidth: width > 0 ? Math.min(width, Math.max(210, Math.floor(width / Math.max(1, Math.floor(width / 250))))) : 230
                    cellHeight: 248
                    cacheBuffer: 640
                    model: root.bBridge ? root.bBridge.postsModel : null

                    delegate: Item {
                        width: postsGrid.cellWidth
                        height: postsGrid.cellHeight

                        readonly property var pData: model.creator || modelData || ({})
                        readonly property bool isMarked: !!pData.is_marked

                        Rectangle {
                            id: pCard
                            anchors.fill: parent
                            anchors.margins: 5
                            radius: 10
                            color: pCardHover.hovered ? "#161E2E" : "#111622"
                            border.color: isMarked ? "#38BDF8" : (pCardHover.hovered ? "#38BDF8" : "#1E293B")
                            border.width: isMarked ? 1.5 : 1
                            clip: true

                            HoverHandler { id: pCardHover }

                            ColumnLayout {
                                z: 1
                                anchors.fill: parent
                                spacing: 0

                                // Thumbnail Cover Area
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 138
                                    color: "#090C12"
                                    clip: true

                                    Image {
                                        id: pThumbImg
                                        anchors.fill: parent
                                        opacity: (status === Image.Ready && implicitWidth > 2) ? 1.0 : 0.0
                                        source: root.browserThumbUrl(pData.thumbnail_url, pData.provider_id || root.activeProvider)
                                        sourceSize: Qt.size(360, 260)
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        cache: true
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        visible: pThumbImg.status !== Image.Ready || pThumbImg.implicitWidth <= 2
                                        text: Number(pData.video_count || 0) > 0 ? "🎬" : "📄"
                                        font.pixelSize: 28
                                        color: "#334155"
                                    }

                                    // Attachment count & DM pills (top-left)
                                    Row {
                                        anchors.top: parent.top
                                        anchors.left: parent.left
                                        anchors.margins: 6
                                        spacing: 5

                                        Rectangle {
                                            height: 22
                                            implicitWidth: mediaBadgeRow.implicitWidth + 12
                                            radius: 5
                                            color: "#D80B0E14"

                                            Row {
                                                id: mediaBadgeRow
                                                anchors.centerIn: parent
                                                spacing: 4
                                                Text {
                                                    text: (Number(pData.video_count || 0) > 0 ? ("🎬 " + pData.video_count + " ") : "")
                                                          + (Number(pData.image_count || 0) > 0 ? ("🖼️ " + pData.image_count) : ("📎 " + Number(pData.file_count || 0)))
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 10
                                                    font.weight: Font.Bold
                                                    color: "#F8FAFC"
                                                }
                                            }
                                        }

                                        Rectangle {
                                            visible: !!pData.is_dm
                                            height: 22
                                            implicitWidth: dmBadgeTxt.implicitWidth + 10
                                            radius: 5
                                            color: "#6D28D9"
                                            Text {
                                                id: dmBadgeTxt
                                                anchors.centerIn: parent
                                                text: "💬 DM"
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 10
                                                font.weight: Font.Bold
                                                color: "#FFFFFF"
                                            }
                                        }
                                    }

                                    UnimportedTriangleBadge {
                                        objectName: "postUnimportedBadge"
                                        visible: !root.isLocalMode && !!pData.is_unimported
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.topMargin: 6
                                        anchors.rightMargin: 42
                                        width: 24
                                        height: 24
                                        z: 3
                                        tooltipText: "Haven't archived this post yet (previews only)"
                                    }

                                    // Mark Post Button (top-right, Online Mode)
                                    Rectangle {
                                        visible: !root.isLocalMode
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 6
                                        width: 30
                                        height: 30
                                        radius: 7
                                        z: 3
                                        color: isMarked ? "#0284C7" : "#D80F172A"
                                        border.color: isMarked ? "#38BDF8" : "#334155"
                                        border.width: 1
                                        Springy { hover: mkPostMouse.containsMouse; pressed: mkPostMouse.pressed }

                                        Text {
                                            anchors.centerIn: parent
                                            text: isMarked ? "✔" : "🛒"
                                            font.pixelSize: 12
                                            color: "#FFFFFF"
                                        }
                                        MouseArea {
                                            id: mkPostMouse
                                            objectName: "postMarkMouse"
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 300
                                            ToolTip.text: (isMarked ? "Unmark post" : "Mark post into Download Cart") + "\nShift+click to mark/unmark a range"
                                            onClicked: (mouse) => root.handleRangeMarkClick("posts", postsGrid, index, pData, (mouse.modifiers & Qt.ShiftModifier) !== 0)
                                        }
                                    }

                                    // Redownload Post Button (top-right, Local Mode)
                                    Rectangle {
                                        visible: root.isLocalMode && !!(pData.url || (pData.service && pData.service !== "local" && pData.creator_id && pData.post_id && pData.post_id !== "root_files"))
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 6
                                        width: 30
                                        height: 30
                                        radius: 7
                                        z: 3
                                        color: pRedlMouse.containsMouse ? "#0369A1" : "#D80F172A"
                                        border.color: pRedlMouse.containsMouse ? "#38BDF8" : "#334155"
                                        border.width: 1
                                        Springy { hover: pRedlMouse.containsMouse; pressed: pRedlMouse.pressed }

                                        Text {
                                            anchors.centerIn: parent
                                            text: "↻"
                                            font.pixelSize: 14
                                            font.weight: Font.Bold
                                            color: "#E0F2FE"
                                        }
                                        MouseArea {
                                            id: pRedlMouse
                                            objectName: "postCardRedownloadMouse"
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 300
                                            ToolTip.text: "Redownload this post freshly (overwrites existing files)"
                                            onClicked: if (root.bBridge) root.bBridge.redownloadPost(pData)
                                        }
                                    }
                                }

                                // Post Title, Date & Snippet
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Layout.margins: 8
                                    spacing: 4

                                    Text {
                                        Layout.fillWidth: true
                                        text: pData.title || "Untitled Post"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 12
                                        font.weight: Font.Bold
                                        color: "#F1F5F9"
                                        maximumLineCount: 2
                                        wrapMode: Text.Wrap
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        visible: !!(pData.content_snippet)
                                        text: pData.content_snippet || ""
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: "#94A3B8"
                                        maximumLineCount: 1
                                        elide: Text.ElideRight
                                    }

                                    Item { Layout.fillHeight: true }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 6
                                        Text {
                                            text: pData.published_at || ""
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            color: "#64748B"
                                        }
                                        Item { Layout.fillWidth: true }
                                        Rectangle {
                                            id: pCardCopyBtn
                                            objectName: "postCardCopyLinkBtn"
                                            property bool justCopied: false
                                            Layout.preferredWidth: 24
                                            Layout.preferredHeight: 20
                                            radius: 5
                                            z: 3
                                            color: justCopied
                                                   ? "#064E3B"
                                                   : (pCardCopyMouse.containsMouse ? "#1E293B" : "#151C2B")
                                            border.color: justCopied ? "#10B981" : (pCardCopyMouse.containsMouse ? "#38BDF8" : "#334155")
                                            border.width: 1
                                            Springy { hover: pCardCopyMouse.containsMouse; pressed: pCardCopyMouse.pressed }
                                            Timer {
                                                id: pCardCopyTimer
                                                interval: 1500
                                                onTriggered: pCardCopyBtn.justCopied = false
                                            }
                                            Text {
                                                anchors.centerIn: parent
                                                text: pCardCopyBtn.justCopied ? "✓" : "🔗"
                                                font.pixelSize: 9
                                                color: pCardCopyBtn.justCopied ? "#6EE7B7" : "#7DD3FC"
                                            }
                                            MouseArea {
                                                id: pCardCopyMouse
                                                objectName: "postCardCopyLinkMouse"
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                ToolTip.visible: containsMouse
                                                ToolTip.delay: 250
                                                ToolTip.text: "Copy link to this post"
                                                onClicked: (mouse) => {
                                                    mouse.accepted = true
                                                    if (root.bBridge && root.bBridge.copyPostLink(pData)) {
                                                        pCardCopyBtn.justCopied = true
                                                        pCardCopyTimer.restart()
                                                    }
                                                }
                                            }
                                        }
                                        Text {
                                            text: "View Media →"
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            font.weight: 600
                                            color: "#38BDF8"
                                        }
                                    }
                                }
                            }

                            MouseArea {
                                id: pBodyMouse
                                anchors.fill: parent
                                z: 0
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (root.bBridge) root.bBridge.openPostDetail(pData)
                            }
                        }
                    }
                }
            }

            // ── C. SLIDE-OVER IN-APP POST VIEWER & MEDIA GALLERY DRAWER ─────
            Rectangle {
                id: postDetailDrawer
                objectName: "postDetailDrawer"
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.right: parent.right
                width: root.hasSelectedPost ? (root.postViewerExpanded ? Math.min(920, parent.width * 0.92) : Math.min(500, Math.max(Math.min(parent.width, 320), parent.width * 0.52))) : 0
                visible: width > 1
                clip: true
                radius: 10
                color: "#111622"
                border.color: "#38BDF8"
                border.width: 1

                // Heavy Newtonian Slide-Over Physics (Mass = 1.85)
                Behavior on width {
                    NumberAnimation { duration: 135; easing.type: Easing.OutCubic }
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10

                    // Drawer Header (Title + Window Controls)
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        UnimportedTriangleBadge {
                            objectName: "drawerUnimportedBadge"
                            visible: !root.isLocalMode && !!root.selectedPost.is_unimported
                            Layout.preferredWidth: 24
                            Layout.preferredHeight: 24
                            width: 24
                            height: 24
                            tooltipText: "Haven't archived this post yet (previews only)"
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 80
                            spacing: 2

                            Text {
                                Layout.fillWidth: true
                                text: root.selectedPost.title || "Post Details"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 14
                                font.weight: Font.Bold
                                color: "#F8FAFC"
                                elide: Text.ElideRight
                            }

                            Text {
                                Layout.fillWidth: true
                                visible: !!(root.selectedPost.creator_name || root.selectedPost.service_label || root.selectedPost.is_dm)
                                text: (root.selectedPost.is_dm ? "💬 DM  •  " : "")
                                      + (root.selectedPost.creator_name || "")
                                      + (root.selectedPost.service_label ? ("  •  " + root.selectedPost.service_label) : "")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: root.selectedPost.is_dm ? "#C4B5FD" : "#7DD3FC"
                                elide: Text.ElideRight
                            }
                        }

                        // Expand / Compact Post Viewer Toggle
                        Rectangle {
                            Layout.preferredHeight: 28
                            Layout.preferredWidth: Math.max(28, dExpTxt.implicitWidth + 12)
                            radius: 6
                            color: dExpMouse.containsMouse ? "#28354E" : "#1E293B"
                            border.color: root.postViewerExpanded ? "#38BDF8" : "#334155"
                            border.width: 1
                            Springy { hover: dExpMouse.containsMouse; pressed: dExpMouse.pressed }

                            Text {
                                id: dExpTxt
                                anchors.centerIn: parent
                                text: root.postViewerExpanded ? "↙" : "⛶"
                                font.pixelSize: 12
                                color: "#E2E8F0"
                            }
                            MouseArea {
                                id: dExpMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: root.postViewerExpanded ? "Compact post drawer" : "Expand post viewer"
                                onClicked: root.postViewerExpanded = !root.postViewerExpanded
                            }
                        }

                        // Close Drawer Button
                        Rectangle {
                            Layout.preferredWidth: 28
                            Layout.preferredHeight: 28
                            radius: 6
                            color: "#1E293B"
                            Text { anchors.centerIn: parent; text: "✕"; font.pixelSize: 12; color: "#94A3B8" }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (root.bBridge) root.bBridge.closePostDetail()
                            }
                        }
                    }

                    // Responsive Drawer Actions Toolbar (wraps cleanly on narrower drawer / Console ON)
                    Flow {
                        id: drawerActionsFlow
                        Layout.fillWidth: true
                        spacing: 6

                        // Open In-App Lightbox Gallery Button
                        Rectangle {
                            visible: root.postViewableMedia.length > 0
                            height: 28
                            width: Math.min(drawerActionsFlow.width, dGalTxt.implicitWidth + 14)
                            radius: 6
                            color: dGalMouse.containsMouse ? "#0EA5E9" : "#0369A1"
                            Springy { hover: dGalMouse.containsMouse; pressed: dGalMouse.pressed }

                            Text {
                                id: dGalTxt
                                anchors.centerIn: parent
                                text: "👁 View Media (" + root.postViewableMedia.length + ")"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                id: dGalMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.openPostMediaGallery(root.selectedPost, 0)
                            }
                        }

                        // Mark Post Button
                        Rectangle {
                            visible: !root.isLocalMode
                            readonly property bool isM: !!root.selectedPost.is_marked
                            height: 28
                            width: Math.min(drawerActionsFlow.width, dMkTxt.implicitWidth + 14)
                            radius: 6
                            color: isM ? "#0284C7" : "#1E293B"
                            Springy { hover: dMkMouse.containsMouse; pressed: dMkMouse.pressed }

                            Text {
                                id: dMkTxt
                                anchors.centerIn: parent
                                text: parent.isM ? "✔ Marked" : "🛒 Mark"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                id: dMkMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (root.bBridge) root.bBridge.toggleMarkItem(root.selectedPost)
                            }
                        }

                        // Direct Download Post Button
                        Rectangle {
                            id: dDlBtn
                            readonly property bool isDispatched: root.isUrlDispatched(root.selectedPost.url)
                            visible: !root.isLocalMode && !!(root.selectedPost.url)
                            height: 28
                            width: Math.min(drawerActionsFlow.width, dDlTxt.implicitWidth + 16)
                            radius: 6
                            color: isDispatched
                                   ? (dDlMouse.containsMouse ? "#0F766E" : "#115E59")
                                   : (dDlMouse.containsMouse ? "#10B981" : "#059669")
                            border.color: isDispatched ? "#5EEAD4" : "transparent"
                            border.width: isDispatched ? 1 : 0
                            Springy { hover: dDlMouse.containsMouse; pressed: dDlMouse.pressed }

                            Text {
                                id: dDlTxt
                                anchors.centerIn: parent
                                text: dDlBtn.isDispatched ? "✓ Sent" : "🚀 Download"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                id: dDlMouse
                                objectName: "postDownloadBtnMouse"
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: dDlBtn.isDispatched ? "Sent to Downloader — click again to queue another download" : "Send this post directly to the Downloader"
                                onClicked: root.triggerItemDownload(
                                    root.selectedPost.url,
                                    true,
                                    root.selectedPost.title || root.selectedPost.creator_name || ""
                                )
                            }
                        }

                        // Force Redownload Post Button (works in both Local & Online Modes)
                        Rectangle {
                            id: dRedlBtn
                            visible: !!(root.selectedPost.url || (root.selectedPost.service && root.selectedPost.service !== "local" && root.selectedPost.creator_id && root.selectedPost.post_id && root.selectedPost.post_id !== "root_files"))
                            height: 28
                            width: Math.min(drawerActionsFlow.width, dRedlTxt.implicitWidth + 16)
                            radius: 6
                            color: dRedlMouse.containsMouse ? "#0369A1" : "#1E293B"
                            border.color: "#38BDF8"
                            border.width: 1
                            Springy { hover: dRedlMouse.containsMouse; pressed: dRedlMouse.pressed }

                            Text {
                                id: dRedlTxt
                                anchors.centerIn: parent
                                text: "↻ Redownload"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#E0F2FE"
                            }
                            MouseArea {
                                id: dRedlMouse
                                objectName: "postRedownloadBtnMouse"
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Redownload all files for this post freshly (overwrites existing files & bypasses archive skip)"
                                onClicked: if (root.bBridge) root.bBridge.redownloadPost(root.selectedPost)
                            }
                        }

                        // Copy Current Post Link Button (always available inside drawer)
                        Rectangle {
                            id: dCopyLinkBtn
                            objectName: "postCopyLinkBtn"
                            property bool justCopied: false
                            visible: !!root.selectedPost && !!(root.selectedPost.key || root.selectedPost.post_id || root.selectedPost.url || root.selectedPost.local_folder)
                            height: 28
                            width: Math.min(drawerActionsFlow.width, dCopyTxt.implicitWidth + 16)
                            radius: 6
                            color: justCopied
                                   ? "#064E3B"
                                   : (dCopyMouse.containsMouse ? "#1E293B" : "#151C2B")
                            border.color: justCopied ? "#10B981" : (dCopyMouse.containsMouse ? "#38BDF8" : "#334155")
                            border.width: 1
                            Springy { hover: dCopyMouse.containsMouse; pressed: dCopyMouse.pressed }
                            Timer {
                                id: dCopyResetTimer
                                interval: 1500
                                onTriggered: dCopyLinkBtn.justCopied = false
                            }

                            Text {
                                id: dCopyTxt
                                anchors.centerIn: parent
                                text: dCopyLinkBtn.justCopied ? "✓ Copied" : "🔗 Copy Link"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: dCopyLinkBtn.justCopied ? "#A7F3D0" : "#E2E8F0"
                            }
                            MouseArea {
                                id: dCopyMouse
                                objectName: "postCopyLinkBtnMouse"
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Copy link to the current post"
                                onClicked: {
                                    if (root.bBridge && root.bBridge.copyPostLink(root.selectedPost)) {
                                        dCopyLinkBtn.justCopied = true
                                        dCopyResetTimer.restart()
                                    }
                                }
                            }
                        }
                    }

                    // Post Metadata & Tags
                    Flow {
                        Layout.fillWidth: true
                        spacing: 5
                        visible: (root.selectedPost.tags && root.selectedPost.tags.length > 0) || !!(root.selectedPost.published_at)

                        Rectangle {
                            visible: !!(root.selectedPost.published_at)
                            height: 20
                            width: pubTxt.implicitWidth + 12
                            radius: 4
                            color: "#1E293B"
                            Text {
                                id: pubTxt
                                anchors.centerIn: parent
                                text: "📅 " + (root.selectedPost.published_at || "")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#94A3B8"
                            }
                        }

                        Repeater {
                            model: root.selectedPost.tags || []
                            delegate: Rectangle {
                                height: 20
                                width: tgTxt.implicitWidth + 12
                                radius: 4
                                color: "#172554"
                                Text {
                                    id: tgTxt
                                    anchors.centerIn: parent
                                    text: "#" + modelData
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: "#7DD3FC"
                                }
                            }
                        }
                    }

                    // Post Description Body (from API or local post_info.txt)
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(root.postViewerExpanded ? 180 : 120, Math.max(48, descBodyTxt.implicitHeight + 18))
                        visible: !!((root.selectedPost.content_full || root.selectedPost.content_snippet || "").trim())
                        radius: 7
                        color: "#090C12"
                        border.color: "#1E293B"
                        border.width: 1
                        clip: true

                        SmoothFlickable {
                            anchors.fill: parent
                            anchors.margins: 8
                            contentWidth: width
                            contentHeight: descBodyTxt.implicitHeight

                            TextEdit {
                                id: descBodyTxt
                                width: parent.width
                                readOnly: true
                                selectByMouse: true
                                text: root.selectedPost.content_full || root.selectedPost.content_snippet || ""
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                color: "#CBD5E1"
                                wrapMode: TextEdit.Wrap
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            text: "Post Media & Files (" + ((root.selectedPost.attachments || []).length) + ")"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#94A3B8"
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: root.postViewableMedia.length > 0
                            text: "Click any picture, GIF, video, or audio to view in-app"
                            horizontalAlignment: Text.AlignRight
                            elide: Text.ElideRight
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#64748B"
                        }
                    }

                    // Post Attachments Sort Bar
                    Flow {
                        Layout.fillWidth: true
                        spacing: 5
                        visible: root.sortedPostAttachments.length > 1

                        Repeater {
                            model: [
                                {"id": "default",   "label": "Default"},
                                {"id": "name_asc",  "label": "Name A–Z"},
                                {"id": "name_desc", "label": "Name Z–A"},
                                {"id": "newest",    "label": "Newest"},
                                {"id": "oldest",    "label": "Oldest"},
                                {"id": "size_desc", "label": "Largest"},
                                {"id": "size_asc",  "label": "Smallest"},
                                {"id": "type",      "label": "Type"}
                            ]

                            delegate: Rectangle {
                                readonly property var sItem: modelData || ({})
                                readonly property bool isSel: root.postAttSortMode === sItem.id
                                height: 22
                                width: attSortLbl.implicitWidth + 14
                                radius: 5
                                color: isSel ? "#0E2239" : (attSortMouse.containsMouse ? "#1E293B" : "#151C2B")
                                border.color: isSel ? "#38BDF8" : "#273549"
                                border.width: 1

                                Text {
                                    id: attSortLbl
                                    anchors.centerIn: parent
                                    text: sItem.label || ""
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: isSel ? Font.Bold : Font.Medium
                                    color: isSel ? "#38BDF8" : "#94A3B8"
                                }
                                MouseArea {
                                    id: attSortMouse
                                    objectName: "postAttSort_" + (sItem.id || "")
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.postAttSortMode = sItem.id
                                }
                            }
                        }
                    }

                    // Virtualized In-App Visual Media & Attachments Grid
                    SmoothGridView {
                        id: attsGridView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        readonly property int cols: Math.max(1, root.postViewerExpanded ? Math.floor(width / 220) : Math.floor(width / 195))
                        cellWidth: Math.floor((width - 8) / Math.max(1, cols))
                        cellHeight: root.postViewerExpanded ? 196 : 168
                        cacheBuffer: 420
                        model: root.sortedPostAttachments

                        delegate: Item {
                            width: attsGridView.cellWidth
                            height: attsGridView.cellHeight

                            readonly property var att: modelData || ({})
                            readonly property bool viewable: root.isViewableAttachment(att)
                            readonly property string kindLabel: root.attachmentKindLabel(att)
                            readonly property bool isVideoCard: kindLabel === "VIDEO"
                            readonly property bool isGifCard: kindLabel === "GIF"
                            readonly property bool isAudioCard: kindLabel === "AUDIO"

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: 4
                                radius: 9
                                color: attHover.hovered ? "#172033" : "#0D121C"
                                border.color: attHover.hovered ? "#38BDF8" : "#1E293B"
                                border.width: 1
                                clip: true

                                HoverHandler { id: attHover }

                                ColumnLayout {
                                    z: 1
                                    anchors.fill: parent
                                    spacing: 0

                                    // Visual Preview Area
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        color: "#070A10"
                                        clip: true

                                        Image {
                                            id: attThumbImg
                                            anchors.fill: parent
                                            opacity: (status === Image.Ready && implicitWidth > 2) ? 1.0 : 0.0
                                            source: root.browserThumbUrl(att.thumbnail_url, root.selectedPost.provider_id || root.activeProvider)
                                            sourceSize: Qt.size(360, 260)
                                            fillMode: Image.PreserveAspectCrop
                                            asynchronous: true
                                            cache: true
                                        }

                                        // Non-thumbnail media / video / audio / archive center badge
                                        Column {
                                            anchors.centerIn: parent
                                            spacing: 4
                                            visible: attThumbImg.status !== Image.Ready || attThumbImg.implicitWidth <= 2 || isVideoCard
                                            Rectangle {
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                width: 44
                                                height: 44
                                                radius: 22
                                                color: isVideoCard ? "#CC0EA5E9" : (isAudioCard ? "#CC10B981" : "#AA1E293B")
                                                border.color: "#38BDF8"
                                                border.width: isVideoCard ? 1.5 : 0
                                                Text {
                                                    anchors.centerIn: parent
                                                    text: isVideoCard ? "▶" : (isAudioCard ? "🎵" : (viewable ? "🖼️" : "📦"))
                                                    font.pixelSize: isVideoCard ? 16 : 20
                                                    color: "#FFFFFF"
                                                }
                                            }
                                        }

                                        // Media kind badge (top-left)
                                        Rectangle {
                                            anchors.top: parent.top
                                            anchors.left: parent.left
                                            anchors.margins: 6
                                            height: 18
                                            implicitWidth: kindBadgeTxt.implicitWidth + 10
                                            radius: 4
                                            color: isGifCard ? "#7E22CE" : (isVideoCard ? "#0369A1" : (isAudioCard ? "#047857" : "#D80B0E14"))
                                            border.color: isGifCard ? "#C084FC" : (isVideoCard ? "#38BDF8" : "#334155")
                                            border.width: 1

                                            Text {
                                                id: kindBadgeTxt
                                                anchors.centerIn: parent
                                                text: kindLabel
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 9
                                                font.weight: Font.Bold
                                                color: "#F8FAFC"
                                            }
                                        }

                                        // Local Disk badge (top-right)
                                        Rectangle {
                                            visible: !!(att.local_path)
                                            anchors.top: parent.top
                                            anchors.right: parent.right
                                            anchors.margins: 6
                                            height: 18
                                            implicitWidth: onDiskTxt.implicitWidth + 8
                                            radius: 4
                                            color: "#CC064E3B"
                                            border.color: "#10B981"
                                            border.width: 1
                                            Text {
                                                id: onDiskTxt
                                                anchors.centerIn: parent
                                                text: "✓ DISK"
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 8
                                                font.weight: Font.Bold
                                                color: "#A7F3D0"
                                            }
                                        }

                                        // Subtle hover CTA pill
                                        Rectangle {
                                            visible: attHover.hovered
                                            anchors.right: parent.right
                                            anchors.bottom: parent.bottom
                                            anchors.margins: 6
                                            height: 20
                                            implicitWidth: ctaBadgeTxt.implicitWidth + 10
                                            radius: 5
                                            color: "#E60F172A"
                                            border.color: "#38BDF8"
                                            border.width: 1
                                            Text {
                                                id: ctaBadgeTxt
                                                anchors.centerIn: parent
                                                text: viewable ? (isVideoCard || isAudioCard ? "▶ Play In-App" : "🔍 View In-App") : (att.local_path ? "💾 Open File" : "📥 Queue Post")
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 9
                                                font.weight: Font.Bold
                                                color: "#7DD3FC"
                                            }
                                        }
                                    }

                                    // Filename + Size Footer
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 30
                                        Layout.leftMargin: 7
                                        Layout.rightMargin: 7
                                        spacing: 4

                                        Text {
                                            Layout.fillWidth: true
                                            text: att.name || "attachment"
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            font.weight: 600
                                            color: "#E2E8F0"
                                            elide: Text.ElideMiddle
                                        }

                                        Text {
                                            visible: Number(att.file_size || 0) > 0
                                            text: root.formatBytes(att.file_size)
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 9
                                            color: "#64748B"
                                        }

                                        Rectangle {
                                            id: attCopyBtn
                                            objectName: "attCopyLinkBtn"
                                            property bool justCopied: false
                                            visible: !!(att && (att.url || att.local_path || att.thumbnail_url))
                                            Layout.preferredWidth: 22
                                            Layout.preferredHeight: 20
                                            radius: 5
                                            z: 3
                                            color: justCopied
                                                   ? "#064E3B"
                                                   : (attCopyMouse.containsMouse ? "#1E293B" : "#141B29")
                                            border.color: justCopied ? "#10B981" : (attCopyMouse.containsMouse ? "#38BDF8" : "#283548")
                                            border.width: 1
                                            Springy { hover: attCopyMouse.containsMouse; pressed: attCopyMouse.pressed }
                                            Timer {
                                                id: attCopyResetTimer
                                                interval: 1500
                                                onTriggered: attCopyBtn.justCopied = false
                                            }
                                            Text {
                                                anchors.centerIn: parent
                                                text: attCopyBtn.justCopied ? "✓" : "🔗"
                                                font.pixelSize: 9
                                                color: attCopyBtn.justCopied ? "#6EE7B7" : (attCopyMouse.containsMouse ? "#7DD3FC" : "#94A3B8")
                                            }
                                            MouseArea {
                                                id: attCopyMouse
                                                objectName: "attCopyLinkMouse"
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                ToolTip.visible: containsMouse
                                                ToolTip.delay: 250
                                                ToolTip.text: "Copy link to this file"
                                                onClicked: (mouse) => {
                                                    mouse.accepted = true
                                                    if (root.bBridge && root.bBridge.copyAttachmentLink(att, root.selectedPost)) {
                                                        attCopyBtn.justCopied = true
                                                        attCopyResetTimer.restart()
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                MouseArea {
                                    id: attClick
                                    anchors.fill: parent
                                    z: 0
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.openAttachmentInApp(att, root.selectedPost)
                                }
                            }
                        }
                    }
                }
            }
        }

        // ====================================================================
        // 6. PAGINATION BAR
        // ====================================================================
        Rectangle {
            objectName: "browserPaginationBar"
            Layout.fillWidth: true
            Layout.preferredHeight: 38
            radius: 8
            color: "#0F131C"
            border.color: "#1E2536"
            border.width: 1
            clip: true

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 10

                Text {
                    text: root.bBridge ? root.bBridge.statusText : ""
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 30
                    elide: Text.ElideRight
                }

                // Prev Page
                Rectangle {
                    readonly property bool canPrev: root.hasSelectedCreator
                                                    ? (root.bBridge && root.bBridge.creatorPostsOffset > 0)
                                                    : (root.bBridge && root.bBridge.currentOffset > 0)
                    Layout.preferredHeight: 28
                    implicitWidth: 78
                    radius: 6
                    color: canPrev ? "#1E293B" : "#111622"
                    opacity: canPrev ? 1.0 : 0.45
                    Springy { hover: prevMouse.containsMouse; pressed: prevMouse.pressed }

                    Text {
                        anchors.centerIn: parent
                        text: "‹ Previous"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#E2E8F0"
                    }
                    MouseArea {
                        id: prevMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: parent.canPrev
                        cursorShape: parent.canPrev ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: {
                            if (!root.bBridge) return
                            if (root.hasSelectedCreator) {
                                var stepPrev = root.bBridge.pageSize || 50
                                root.bBridge.loadCreatorPosts(Math.max(0, root.bBridge.creatorPostsOffset - stepPrev), creatorPostSearchInput.text)
                            } else {
                                root.bBridge.prevPage()
                            }
                        }
                    }
                }

                Text {
                    text: root.hasSelectedCreator
                          ? ("Offset " + (root.bBridge ? root.bBridge.creatorPostsOffset : 0))
                          : ("Page " + (root.bBridge ? root.bBridge.currentPage : 1) + " of " + (root.bBridge ? root.bBridge.totalPages : 1))
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#F8FAFC"
                }

                // Next Page
                Rectangle {
                    readonly property bool canNext: root.hasSelectedCreator
                                                    ? (root.bBridge && root.bBridge.creatorPostsHasMore)
                                                    : (root.bBridge && root.bBridge.hasMore)
                    Layout.preferredHeight: 28
                    implicitWidth: 68
                    radius: 6
                    color: canNext ? "#1E293B" : "#111622"
                    opacity: canNext ? 1.0 : 0.45
                    Springy { hover: nextMouse.containsMouse; pressed: nextMouse.pressed }

                    Text {
                        anchors.centerIn: parent
                        text: "Next ›"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#E2E8F0"
                    }
                    MouseArea {
                        id: nextMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: parent.canNext
                        cursorShape: parent.canNext ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: {
                            if (!root.bBridge) return
                            if (root.hasSelectedCreator) {
                                var stepNext = root.bBridge.pageSize || 50
                                root.bBridge.loadCreatorPosts(root.bBridge.creatorPostsOffset + stepNext, creatorPostSearchInput.text)
                            } else {
                                root.bBridge.nextPage()
                            }
                        }
                    }
                }
            }
        }

        // ====================================================================
        // 7. PERSISTENT "MARKED FOR DOWNLOAD" SELECTION CART TRAY
        // ====================================================================
        BrowserMarkTray {
            id: markTray
            Layout.fillWidth: true
            browserBridge: root.bBridge
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

    // ── Move Creator to Another Drive Modal ─────────────────────────────────
    Popup {
        id: moveCreatorDriveModal
        anchors.centerIn: Overlay.overlay
        width: 520
        height: 410
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            radius: 12
            color: "#0F1420"
            border.color: "#10B981"
            border.width: 1.5
        }

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: "💽 Move Creator to Another Drive"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 15
                    font.weight: Font.Bold
                    color: "#F8FAFC"
                }
                Rectangle {
                    width: 28; height: 28; radius: 6; color: "#1E293B"
                    Text { anchors.centerIn: parent; text: "✕"; color: "#94A3B8" }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: moveCreatorDriveModal.close() }
                }
            }

            Text {
                Layout.fillWidth: true
                text: root.creatorToRelocate
                      ? ("Relocate '" + (root.creatorToRelocate.name || "") + "' (" + Number(root.creatorToRelocate.local_file_count || 0) + " files • " + root.formatBytes(root.creatorToRelocate.local_size_bytes) + ") to another drive. Archive records and Watchlist paths will update automatically.")
                      : ""
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#94A3B8"
                wrapMode: Text.Wrap
            }

            SmoothListView {
                id: drivePickList
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 8
                model: root.bBridge ? root.bBridge.relocateTargetDrives : []

                delegate: Rectangle {
                    readonly property var dItem: modelData || ({})
                    width: drivePickList.width - 10
                    height: 64
                    radius: 8
                    color: dPickHover.hovered ? "#162235" : "#111827"
                    border.color: dPickHover.hovered ? "#10B981" : "#1E293B"
                    border.width: 1

                    HoverHandler { id: dPickHover }
                    Springy { hover: dPickHover.hovered; pressed: dPickMouse.pressed }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 6

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: "💽 Drive " + (dItem.drive || "") + "  —  " + (dItem.root_path || "")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                color: "#F8FAFC"
                                Layout.fillWidth: true
                                elide: Text.ElideMiddle
                            }
                            Text {
                                text: Number(dItem.free_gb || 0).toFixed(1) + " GB free / " + Number(dItem.total_gb || 0).toFixed(0) + " GB"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: "#34D399"
                            }
                        }

                        // Capacity bar
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 6
                            radius: 3
                            color: "#1E293B"
                            Rectangle {
                                height: parent.height
                                radius: 3
                                width: parent.width * Math.min(1.0, Number(dItem.percent_used || 0) / 100.0)
                                color: Number(dItem.percent_used || 0) > 90 ? "#EF4444" : "#38BDF8"
                            }
                        }
                    }

                    MouseArea {
                        id: dPickMouse
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.bBridge && root.creatorToRelocate && dItem.root_path) {
                                root.bBridge.moveCreatorToDrive(root.creatorToRelocate.key, dItem.root_path)
                                moveCreatorDriveModal.close()
                            }
                        }
                    }
                }
            }

            // Custom Folder Picker on Any Drive
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 36
                radius: 8
                color: customDestMouse.containsMouse ? "#1E293B" : "#151C2B"
                border.color: "#38BDF8"
                border.width: 1
                Springy { hover: customDestMouse.containsMouse; pressed: customDestMouse.pressed }

                Text {
                    anchors.centerIn: parent
                    text: "📂 Choose Custom Destination Folder on Any Disk…"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    color: "#38BDF8"
                }
                MouseArea {
                    id: customDestMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: customRelocateFolderDialog.open()
                }
            }
        }
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

    // Newer Posts Online Check Modal
    Popup {
        id: newPostsModal
        anchors.centerIn: Overlay.overlay
        width: Math.min(720, Math.max(460, root.width * 0.68))
        height: Math.min(600, Math.max(380, root.height * 0.72))
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            radius: 12
            color: "#0F1420"
            border.color: "#38BDF8"
            border.width: 1.5
        }

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Text {
                    Layout.fillWidth: true
                    text: "🔎 Newer Posts Check — " + (root.selectedCreator ? (root.selectedCreator.name || "Creator") : "Creator")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 15
                    font.weight: Font.Bold
                    color: "#F8FAFC"
                    elide: Text.ElideRight
                }
                Rectangle {
                    visible: !!(root.bBridge && root.selectedCreator && !root.bBridge.isCheckingNewPosts)
                    Layout.preferredHeight: 30
                    implicitWidth: findSiteTxt.implicitWidth + 16
                    radius: 7
                    color: findSiteMouse.containsMouse ? "#1E293B" : "#151C2B"
                    border.color: "#38BDF8"
                    border.width: 1
                    Springy { hover: findSiteMouse.containsMouse; pressed: findSiteMouse.pressed }
                    Text {
                        id: findSiteTxt
                        anchors.centerIn: parent
                        text: "🔎 Switch Site"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#38BDF8"
                    }
                    MouseArea {
                        id: findSiteMouse
                        objectName: "searchSitesBtnMouse"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.bBridge && root.selectedCreator) {
                                root.bBridge.searchCreatorAcrossSites(root.selectedCreator)
                            }
                        }
                    }
                }
                Rectangle {
                    visible: !!(root.bBridge && root.bBridge.newPostsCount > 0)
                    Layout.preferredHeight: 30
                    implicitWidth: dlAllNewTxt.implicitWidth + 18
                    radius: 7
                    color: dlAllNewMouse.containsMouse ? "#10B981" : "#059669"
                    Springy { hover: dlAllNewMouse.containsMouse; pressed: dlAllNewMouse.pressed }
                    Text {
                        id: dlAllNewTxt
                        anchors.centerIn: parent
                        text: "⬇ Download All (" + ((root.bBridge ? root.bBridge.newPostsCount : 0)) + ")"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#FFFFFF"
                    }
                    MouseArea {
                        id: dlAllNewMouse
                        objectName: "downloadAllNewPostsMouse"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.bBridge) {
                                root.bBridge.downloadNewPosts([], true)
                            }
                        }
                    }
                }
                Rectangle {
                    width: 28; height: 28; radius: 6; color: "#1E293B"
                    Text { anchors.centerIn: parent; text: "✕"; color: "#94A3B8" }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: newPostsModal.close() }
                }
            }

            Text {
                Layout.fillWidth: true
                text: (root.bBridge && root.bBridge.newPostsStatusText) ? root.bBridge.newPostsStatusText : "Comparing remote posts with your downloaded archive and local folders…"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: (root.bBridge && root.bBridge.isCheckingNewPosts) ? "#38BDF8" : "#94A3B8"
                wrapMode: Text.WordWrap
            }

            SmoothListView {
                id: newPostsListView
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 8
                visible: !!(root.bBridge && root.bBridge.newPostsCount > 0)
                model: root.bBridge ? root.bBridge.newPostsList : []

                delegate: Rectangle {
                    readonly property var npItem: modelData || ({})
                    width: newPostsListView.width - 8
                    height: 68
                    radius: 8
                    color: npHover.hovered ? "#162033" : "#111827"
                    border.color: npHover.hovered ? "#38BDF8" : "#1E293B"
                    border.width: 1
                    HoverHandler { id: npHover }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 10

                        Rectangle {
                            Layout.preferredWidth: 52
                            Layout.preferredHeight: 52
                            radius: 6
                            color: "#090C12"
                            clip: true
                            Image {
                                anchors.fill: parent
                                asynchronous: true
                                fillMode: Image.PreserveAspectCrop
                                source: root.browserThumbUrl(npItem.thumbnail_url, npItem.provider_id || root.activeProvider)
                                sourceSize: Qt.size(110, 110)
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            Text {
                                Layout.fillWidth: true
                                text: (npItem.is_dm ? "💬 DM  •  " : "") + (npItem.title || ("Post #" + (npItem.post_id || "")))
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                color: npItem.is_dm ? "#E9D5FF" : "#F1F5F9"
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                text: (npItem.published_at || "No date") + "  •  " + Number(npItem.file_count || 0) + " file(s)"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#94A3B8"
                                elide: Text.ElideRight
                            }
                        }

                        Rectangle {
                            Layout.preferredHeight: 28
                            implicitWidth: npViewTxt.implicitWidth + 14
                            radius: 6
                            color: npViewMouse.containsMouse ? "#1E293B" : "#151C2B"
                            border.color: "#38BDF8"
                            border.width: 1
                            Text {
                                id: npViewTxt
                                anchors.centerIn: parent
                                text: "🔍 Open"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: "#38BDF8"
                            }
                            MouseArea {
                                id: npViewMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (root.bBridge) {
                                        newPostsModal.close()
                                        root.bBridge.openPostDetail(npItem)
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.preferredHeight: 28
                            implicitWidth: npDlTxt.implicitWidth + 14
                            radius: 6
                            color: npDlMouse.containsMouse ? "#10B981" : "#059669"
                            Text {
                                id: npDlTxt
                                anchors.centerIn: parent
                                text: "🚀 Download"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                id: npDlMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (root.bBridge && npItem.url) {
                                        root.bBridge.downloadNewPosts([npItem.url], true)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Cross-Site Match Picker (when an unlinked local folder matched multiple profiles across sites, or user clicked Switch Site)
            SmoothListView {
                id: creatorMatchesListView
                objectName: "creatorMatchesListView"
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 8
                visible: !!(root.bBridge && root.bBridge.creatorSearchMatchCount > 0 && root.bBridge.newPostsCount === 0 && !root.bBridge.isCheckingNewPosts)
                model: root.bBridge ? root.bBridge.creatorSearchMatches : []

                delegate: Rectangle {
                    readonly property var mItem: modelData || ({})
                    width: creatorMatchesListView.width - 8
                    height: 64
                    radius: 8
                    color: mHover.hovered ? "#162033" : "#111827"
                    border.color: mHover.hovered ? "#38BDF8" : "#1E293B"
                    border.width: 1
                    HoverHandler { id: mHover }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 10

                        Rectangle {
                            Layout.preferredHeight: 26
                            implicitWidth: mSiteTxt.implicitWidth + 14
                            radius: 6
                            color: "#0F172A"
                            border.color: "#334155"
                            border.width: 1
                            Text {
                                id: mSiteTxt
                                anchors.centerIn: parent
                                text: (mItem.provider_icon ? (mItem.provider_icon + " ") : "") + (mItem.provider_name || mItem.provider_id || "Site")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#38BDF8"
                            }
                        }

                        Rectangle {
                            Layout.preferredHeight: 24
                            implicitWidth: mSvcTxt.implicitWidth + 12
                            radius: 5
                            color: "#1E293B"
                            Text {
                                id: mSvcTxt
                                anchors.centerIn: parent
                                text: mItem.service_label || mItem.service || "Creator"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                color: "#E2E8F0"
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                Layout.fillWidth: true
                                text: mItem.name || mItem.creator_id || "Creator"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 13
                                font.weight: Font.Bold
                                color: "#F8FAFC"
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                text: "id: " + (mItem.creator_id || "")
                                      + (Number(mItem.post_count || 0) > 0 ? ("  •  " + Number(mItem.post_count || 0) + " posts") : "")
                                      + (Number(mItem.dm_count || 0) > 0 ? ("  •  💬 " + Number(mItem.dm_count || 0) + " DMs") : "")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#94A3B8"
                                elide: Text.ElideRight
                            }
                        }

                        Rectangle {
                            Layout.preferredHeight: 30
                            implicitWidth: selMatchTxt.implicitWidth + 18
                            radius: 6
                            color: selMatchMouse.containsMouse ? "#10B981" : "#059669"
                            Springy { hover: selMatchMouse.containsMouse; pressed: selMatchMouse.pressed }
                            Text {
                                id: selMatchTxt
                                anchors.centerIn: parent
                                text: "✓ Select & Check"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                id: selMatchMouse
                                objectName: "selectCreatorMatchMouse"
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (root.bBridge) {
                                        root.bBridge.selectCreatorMatchAndCheck(mItem)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: !(root.bBridge && (root.bBridge.newPostsCount > 0 || (root.bBridge.creatorSearchMatchCount > 0 && !root.bBridge.isCheckingNewPosts)))
                radius: 8
                color: "#0B0F19"
                border.color: "#1E293B"
                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: (root.bBridge && root.bBridge.isCheckingNewPosts)
                              ? "⌛"
                              : ((root.bBridge && String(root.bBridge.newPostsStatusText || "").toLowerCase().indexOf("could not") >= 0) ? "🔎" : "✅")
                        font.pixelSize: 28
                    }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        width: 460
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: (root.bBridge && root.bBridge.isCheckingNewPosts)
                              ? "Searching sites / checking creator posts online…"
                              : ((root.bBridge && root.bBridge.newPostsStatusText) ? root.bBridge.newPostsStatusText : "All recent posts appear to be downloaded.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#CBD5E1"
                    }
                }
            }
        }
    }

    // Account Login / Session Verification Modal
    Popup {
        id: providerLoginModal
        objectName: "providerLoginModal"
        anchors.centerIn: Overlay.overlay
        width: Math.min(480, Math.max(360, root.width * 0.46))
        padding: 18
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        readonly property string targetPid: root.loginModalProviderId || (root.bBridge ? root.bBridge.activeProvider : "pawchive")
        readonly property string targetDisplayName: {
            if (targetPid === "pawchive") return "Pawchive"
            if (targetPid === "cumst") return "Cum.st"
            if (targetPid === "coomerfans") return "CoomerFans"
            return root.activeProviderDisplayName
        }

        background: Rectangle {
            radius: 12
            color: "#0F1420"
            border.color: "#F59E0B"
            border.width: 1.5
        }

        contentItem: ColumnLayout {
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: "🔐 Sign In to " + providerLoginModal.targetDisplayName
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 16
                    font.weight: Font.Bold
                    color: "#F8FAFC"
                }
                Text {
                    text: "✕"
                    font.pixelSize: 14
                    color: "#94A3B8"
                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -6
                        cursorShape: Qt.PointingHandCursor
                        onClicked: providerLoginModal.close()
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: "#94A3B8"
                text: {
                    if (root.loginModalReason === "favorites") {
                        return "Log in to your " + providerLoginModal.targetDisplayName + " account to browse your favorited creators."
                    }
                    if (root.loginModalReason === "favorite_creator") {
                        return "Log in to save or remove favorited creators directly on your " + providerLoginModal.targetDisplayName + " account."
                    }
                    return "Log in with your account credentials, import cookies from your browser, or paste your session cookie."
                }
            }

            Rectangle {
                visible: root.loginModalError.length > 0
                Layout.fillWidth: true
                implicitHeight: loginErrLbl.implicitHeight + 14
                radius: 7
                color: "#2A1215"
                border.color: "#F43F5E"
                border.width: 1
                Text {
                    id: loginErrLbl
                    anchors.fill: parent
                    anchors.margins: 7
                    wrapMode: Text.WordWrap
                    text: root.loginModalError
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#FDA4AF"
                }
            }

            // Username & Password Login
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: credCol.implicitHeight + 20
                radius: 8
                color: "#0B0F19"
                border.color: "#1E293B"
                border.width: 1

                ColumnLayout {
                    id: credCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    Text {
                        text: "Account Credentials"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#CBD5E1"
                    }

                    TextField {
                        id: loginUserField
                        objectName: "loginUsernameField"
                        Layout.fillWidth: true
                        placeholderText: "Username or email"
                        color: "#F8FAFC"
                        placeholderTextColor: "#64748B"
                        background: Rectangle {
                            radius: 6
                            color: "#121722"
                            border.color: loginUserField.activeFocus ? "#38BDF8" : "#1E293B"
                            border.width: 1
                        }
                    }

                    TextField {
                        id: loginPassField
                        objectName: "loginPasswordField"
                        Layout.fillWidth: true
                        echoMode: TextInput.Password
                        placeholderText: "Password"
                        color: "#F8FAFC"
                        placeholderTextColor: "#64748B"
                        background: Rectangle {
                            radius: 6
                            color: "#121722"
                            border.color: loginPassField.activeFocus ? "#38BDF8" : "#1E293B"
                            border.width: 1
                        }
                        onAccepted: {
                            if (root.bBridge && !(root.bBridge.isLoggingInProvider)) {
                                root.loginModalError = ""
                                root.bBridge.loginProvider(providerLoginModal.targetPid, loginUserField.text, loginPassField.text)
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 34
                        radius: 7
                        opacity: (root.bBridge && root.bBridge.isLoggingInProvider) ? 0.6 : 1.0
                        color: loginSubMouse.containsMouse ? "#D97706" : "#F59E0B"
                        Springy { hover: loginSubMouse.containsMouse; pressed: loginSubMouse.pressed }

                        Text {
                            anchors.centerIn: parent
                            text: (root.bBridge && root.bBridge.isLoggingInProvider) ? "Signing in…" : "Log In to " + providerLoginModal.targetDisplayName
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#0F172A"
                        }
                        MouseArea {
                            id: loginSubMouse
                            objectName: "loginSubmitBtn"
                            anchors.fill: parent
                            enabled: !(root.bBridge && root.bBridge.isLoggingInProvider)
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.bBridge) {
                                    root.loginModalError = ""
                                    root.bBridge.loginProvider(providerLoginModal.targetPid, loginUserField.text, loginPassField.text)
                                }
                            }
                        }
                    }
                }
            }

            // Browser Cookie Import / Paste Cookie
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: cookieCol.implicitHeight + 20
                radius: 8
                color: "#0B0F19"
                border.color: "#1E293B"
                border.width: 1

                ColumnLayout {
                    id: cookieCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 32
                        radius: 7
                        opacity: (root.bBridge && root.bBridge.isLoggingInProvider) ? 0.6 : 1.0
                        color: importCookieMouse.containsMouse ? "#1E293B" : "#121722"
                        border.color: "#38BDF8"
                        border.width: 1
                        Springy { hover: importCookieMouse.containsMouse; pressed: importCookieMouse.pressed }

                        Text {
                            anchors.centerIn: parent
                            text: "🌐 1-Click Import Session Cookies from Browser"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#38BDF8"
                        }
                        MouseArea {
                            id: importCookieMouse
                            objectName: "loginImportCookiesBtn"
                            anchors.fill: parent
                            enabled: !(root.bBridge && root.bBridge.isLoggingInProvider)
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.bBridge) {
                                    root.loginModalError = ""
                                    root.bBridge.importProviderCookies(providerLoginModal.targetPid, "")
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        TextField {
                            id: loginCookieField
                            objectName: "loginCookieField"
                            Layout.fillWidth: true
                            placeholderText: "Or paste Cookie header (e.g. session=...)"
                            color: "#F8FAFC"
                            placeholderTextColor: "#64748B"
                            font.pixelSize: 11
                            background: Rectangle {
                                radius: 6
                                color: "#121722"
                                border.color: loginCookieField.activeFocus ? "#38BDF8" : "#1E293B"
                                border.width: 1
                            }
                        }
                        Rectangle {
                            Layout.preferredHeight: 32
                            implicitWidth: verifyCBtnTxt.implicitWidth + 18
                            radius: 6
                            color: verifyCookieMouse.containsMouse ? "#0EA5E9" : "#0284C7"
                            Springy { hover: verifyCookieMouse.containsMouse; pressed: verifyCookieMouse.pressed }
                            Text {
                                id: verifyCBtnTxt
                                anchors.centerIn: parent
                                text: "Verify"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                id: verifyCookieMouse
                                objectName: "loginVerifyCookieBtn"
                                anchors.fill: parent
                                enabled: !(root.bBridge && root.bBridge.isLoggingInProvider)
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (root.bBridge) {
                                        root.loginModalError = ""
                                        root.bBridge.saveProviderCookie(providerLoginModal.targetPid, loginCookieField.text)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    Layout.preferredHeight: 28
                    implicitWidth: openSettingsAuthTxt.implicitWidth + 14
                    radius: 6
                    color: openSettingsAuthMouse.containsMouse ? "#1E293B" : "transparent"
                    border.color: "#334155"
                    border.width: 1
                    Text {
                        id: openSettingsAuthTxt
                        anchors.centerIn: parent
                        text: "⚙️ Accounts in Settings"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                    MouseArea {
                        id: openSettingsAuthMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            providerLoginModal.close()
                            if (root.bBridge) root.bBridge.navigateToTabRequested(11)
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    Layout.preferredHeight: 28
                    implicitWidth: 74
                    radius: 6
                    color: cancelAuthMouse.containsMouse ? "#1E293B" : "#121722"
                    border.color: "#334155"
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "Cancel"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#CBD5E1"
                    }
                    MouseArea {
                        id: cancelAuthMouse
                        objectName: "loginCancelBtn"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: providerLoginModal.close()
                    }
                }
            }
        }
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
