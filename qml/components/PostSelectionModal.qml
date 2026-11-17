import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import "../components"
import "ScrollPhysics.js" as ScrollPhysics

Item {
    id: modalRoot

    property var bridge: null
    property var browserBridge: null
    property bool isOpen: false
    property bool fromFavoritesBrowser: false
    signal backToFavoritesRequested()
    property string creatorName: ""
    property var allPosts: []
    property var filteredPosts: []
    property string searchFilter: ""
    property int selectedCount: 0
    property int totalFilesCount: 0
    property int totalSelectedFiles: 0
    property int _selectionTick: 0

    readonly property int unimportedCount: {
        var posts = allPosts || []
        var cnt = 0
        for (var i = 0; i < posts.length; i++) {
            if (posts[i] && posts[i].is_unimported) cnt++
        }
        return cnt
    }
    readonly property bool hasUnimportedCreator: (!!bridge && !!bridge.selectionCreatorUnimported) || (allPosts.length > 0 && unimportedCount === allPosts.length)

    // Inspector state
    property var inspectedPost: null
    readonly property bool isInspecting: inspectedPost !== null
    property int selectedFilesInPost: 0
    property bool visualGalleryMode: true
    property bool quickSelectClickMode: false
    property var _savedSessions: ({})
    property string activeSessionKey: ""

    Settings {
        category: "post_selector"
        property alias quickSelectClickMode: modalRoot.quickSelectClickMode
    }

    // Shift+click range selection anchors
    property int postSelectionAnchor: -1
    property bool postSelectionAnchorState: true
    property int fileSelectionAnchor: -1
    property bool fileSelectionAnchorState: true

    // Lightbox / Visualizer state (backed by MediaLightboxModal)
    readonly property bool lightboxVisible: selectionLightbox.isOpen
    readonly property int lightboxIndex: (selectionLightbox.isOpen && selectionLightbox.currentItem && selectionLightbox.currentItem.postFileIndex !== undefined)
                                         ? Number(selectionLightbox.currentItem.postFileIndex) : -1
    readonly property var lightboxItem: (lightboxIndex >= 0 && lightboxIndex < postFilesModel.count)
                                        ? postFilesModel.get(lightboxIndex) : null

    anchors.fill: parent
    visible: opacity > 0.001
    opacity: isOpen ? 1.0 : 0.0
    z: 9999
    focus: true

    Behavior on opacity {
        NumberAnimation {
            duration: modalRoot.isOpen ? 240 : 180
            easing.type: Easing.OutCubic
        }
    }

    Keys.onEscapePressed: function(event) {
        if (modalRoot.lightboxVisible) {
            modalRoot.closeLightbox()
            event.accepted = true
        } else if (modalRoot.isInspecting) {
            modalRoot.backToPosts()
            event.accepted = true
        } else if (modalRoot.isOpen) {
            modalRoot.closeModal()
            event.accepted = true
        }
    }

    Keys.onLeftPressed: function(event) {
        if (modalRoot.lightboxVisible) {
            modalRoot.prevLightboxItem()
            event.accepted = true
        }
    }

    Keys.onRightPressed: function(event) {
        if (modalRoot.lightboxVisible) {
            modalRoot.nextLightboxItem()
            event.accepted = true
        }
    }

    function tr(key, fallback) {
        if (typeof Lang === "undefined" || !Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage      // re-translate when the language changes
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    function _extractExt(s) {
        if (!s) return ""
        var clean = String(s).split("#")[0]
        var qIdx = clean.indexOf("?")
        var pathOnly = qIdx >= 0 ? clean.substring(0, qIdx) : clean
        var dot = pathOnly.lastIndexOf(".")
        if (dot > 0) {
            var ext = pathOnly.substring(dot).toLowerCase()
            if (ext.length <= 6 && ext.indexOf("/") < 0) return ext
        }
        if (qIdx >= 0) {
            var q = clean.substring(qIdx + 1)
            var m = q.match(/(?:^|&)(?:f|filename|file)=([^&]+)/)
            if (m && m[1]) {
                var fname = decodeURIComponent(m[1])
                var fd = fname.lastIndexOf(".")
                if (fd > 0) return fname.substring(fd).toLowerCase()
            }
        }
        return ""
    }

    function _fileExt(item) {
        if (!item) return ""
        if (item.ext) return String(item.ext).toLowerCase()
        return _extractExt(item.name) || _extractExt(item.url) || _extractExt(item.path)
    }

    function _mediaType(item) {
        if (!item) return ""
        var mt = String(item.media_type || "").toLowerCase()
        if (mt === "video" || mt === "audio" || mt === "image" || mt === "archive") return mt
        var ext = _fileExt(item)
        if ([".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".flv", ".wmv", ".m3u8", ".ts", ".3gp", ".ogv"].indexOf(ext) >= 0) return "video"
        if ([".mp3", ".wav", ".flac", ".ogg", ".oga", ".m4a", ".aac", ".opus", ".wma"].indexOf(ext) >= 0) return "audio"
        if ([".png", ".jpg", ".jpeg", ".jpe", ".jfif", ".webp", ".gif", ".bmp", ".avif", ".heic", ".heif", ".apng", ".svg"].indexOf(ext) >= 0) return "image"
        if ([".zip", ".rar", ".7z", ".tar", ".gz", ".cbz", ".cbr", ".pdf", ".psd"].indexOf(ext) >= 0) return "archive"
        return ""
    }

    function isVideoFile(item) {
        return _mediaType(item) === "video"
    }

    function isAudioFile(item) {
        return _mediaType(item) === "audio"
    }

    function isGifFile(item) {
        if (!item) return false
        return _fileExt(item) === ".gif" || !!item.is_loop
    }

    function isViewableFile(item) {
        var mt = _mediaType(item)
        return mt === "image" || mt === "video" || mt === "audio"
    }

    function fileKindLabel(item) {
        if (!item) return "FILE"
        if (isGifFile(item)) return "GIF"
        var mt = _mediaType(item)
        if (mt === "video") return "VIDEO"
        if (mt === "audio") return "AUDIO"
        var ext = _fileExt(item)
        if (mt === "image") return ext ? ext.replace(".", "").toUpperCase() : "IMAGE"
        return ext ? ext.replace(".", "").toUpperCase() : "FILE"
    }

    function thumbSrc(rawUrl, providerId) {
        var u = String(rawUrl || "").trim()
        if (!u) return ""
        if (u.indexOf("image://") === 0 || u.indexOf("file://") === 0) return u
        if (u.indexOf("http://") === 0 || u.indexOf("https://") === 0) {
            if (modalRoot.browserBridge) {
                return "image://remotethumb/" + encodeURIComponent(providerId || "") + "/" + encodeURIComponent(u)
            }
            return u
        }
        return u
    }

    function safeThumbUrl(rawUrl, providerId) {
        var u = String(rawUrl || "").trim()
        if (!u) return ""
        var mt = _mediaType({ "url": u })
        if (mt === "video" || mt === "audio" || mt === "archive") return ""
        return thumbSrc(u, providerId)
    }

    function isImageFile(name, path, url) {
        return _mediaType({ "name": name || "", "path": path || "", "url": url || "" }) === "image"
    }

    function _resolveSessionKey(creator) {
        if (bridge && bridge.getSelectionSessionKey) {
            var bKey = bridge.getSelectionSessionKey()
            if (bKey && bKey.length > 0) return bKey
        }
        return "local:" + (creator || "")
    }

    function _saveCurrentSessionState() {
        if (!allPosts || allPosts.length === 0) return
        var key = activeSessionKey || _resolveSessionKey(creatorName)
        if (!key) return

        var postStates = {}
        for (var i = 0; i < allPosts.length; i++) {
            var p = allPosts[i]
            var pid = String(p.id || "")
            if (!pid) continue
            var fileStates = {}
            var hasFiles = !!(p.files && p.files.length)
            if (hasFiles) {
                for (var f = 0; f < p.files.length; f++) {
                    var fp = String(p.files[f].path || f)
                    fileStates[fp] = !!p.files[f].selected
                }
            }
            postStates[pid] = {
                selected: !!p.selected,
                hasFiles: hasFiles,
                files: fileStates
            }
        }
        var nextSessions = Object.assign({}, _savedSessions)
        nextSessions[key] = {
            postStates: postStates,
            searchFilter: searchFilter || ""
        }
        _savedSessions = nextSessions
        activeSessionKey = key
    }

    function openModal(posts, creator, totalCount) {
        if (isOpen && allPosts && allPosts.length > 0) {
            _saveCurrentSessionState()
        }
        var sessionKey = _resolveSessionKey(creator || "")
        var savedSession = (sessionKey && _savedSessions[sessionKey]) ? _savedSessions[sessionKey] : null
        var savedPosts = savedSession ? savedSession.postStates : null
        activeSessionKey = sessionKey

        creatorName = creator || ""
        inspectedPost = null
        selectionLightbox.close()

        var list = []
        if (posts && posts.length) {
            for (var i = 0; i < posts.length; i++) {
                var p = posts[i]
                var pid = String(p.id || "")
                var pProv = String(p.provider_id || "")
                var pUrl = String(p.url || "")
                var pIsUnimp = !!p.is_unimported
                var savedPost = (savedPosts && pid && savedPosts.hasOwnProperty(pid)) ? savedPosts[pid] : null
                var filesList = []
                if (p.files && p.files.length) {
                    for (var f = 0; f < p.files.length; f++) {
                        var fileItem = p.files[f]
                        var fExt = _fileExt(fileItem)
                        var fType = _mediaType(fileItem)
                        var fLoop = isGifFile(fileItem)
                        var thumbUrl = String(fileItem.thumbnail || fileItem.thumbnail_url || "")
                        var prevUrl = String(fileItem.previewUrl || thumbUrl)
                        if (fType === "image") {
                            if (prevUrl && prevUrl.indexOf("/thumbnail/data/") === -1 && prevUrl.indexOf("/data/") !== -1) {
                                prevUrl = prevUrl.replace("/data/", "/thumbnail/data/")
                            }
                            if (thumbUrl && thumbUrl.indexOf("/thumbnail/data/") === -1 && thumbUrl.indexOf("/data/") !== -1) {
                                thumbUrl = thumbUrl.replace("/data/", "/thumbnail/data/")
                            }
                        }
                        var fp = String(fileItem.path || fileItem.url || f)
                        var fileSel = fileItem.selected !== undefined ? !!fileItem.selected : true
                        if (savedPost && savedPost.hasFiles && savedPost.files && savedPost.files.hasOwnProperty(fp)) {
                            fileSel = !!savedPost.files[fp]
                        }
                        filesList.push({
                            name: String(fileItem.name || "attachment"),
                            path: String(fileItem.path || ""),
                            url: String(fileItem.url || ""),
                            thumbnail: thumbUrl,
                            previewUrl: prevUrl,
                            thumbnail_url: thumbUrl,
                            ext: fExt,
                            media_type: fType,
                            is_loop: fLoop,
                            file_size: Number(fileItem.file_size || fileItem.size || 0),
                            provider_id: String(fileItem.provider_id || pProv),
                            postUrl: String(fileItem.postUrl || pUrl),
                            postId: String(fileItem.postId || pid),
                            is_main: !!fileItem.is_main,
                            selected: fileSel
                        })
                    }
                }
                var totalF = filesList.length || p.fileCount || 0
                var selF = 0
                if (filesList.length > 0) {
                    for (var sf = 0; sf < filesList.length; sf++) {
                        if (filesList[sf].selected) selF++
                    }
                } else {
                    selF = p.selected !== false ? totalF : 0
                }
                var defaultPostSel = (filesList.length > 0) ? ((selF > 0) && (p.selected !== false)) : (p.selected !== false)
                var isPostSel = savedPost ? (!!savedPost.selected && (filesList.length === 0 || selF > 0)) : defaultPostSel
                if (filesList.length === 0) {
                    selF = isPostSel ? totalF : 0
                }
                var pThumb = String(p.thumbnail || "")
                if (pThumb && pThumb.indexOf("/thumbnail/data/") === -1 && pThumb.indexOf("/data/") !== -1 && _extractExt(pThumb) !== ".mp4" && _extractExt(pThumb) !== ".webm") {
                    pThumb = pThumb.replace("/data/", "/thumbnail/data/")
                }
                var pHasVideo = !!p.hasVideo
                var pHasGif = !!p.hasGif
                if (!pHasVideo || !pHasGif) {
                    for (var pfIdx = 0; pfIdx < filesList.length; pfIdx++) {
                        if (filesList[pfIdx].media_type === "video") pHasVideo = true
                        if (filesList[pfIdx].is_loop || filesList[pfIdx].ext === ".gif") pHasGif = true
                    }
                }
                list.push({
                    id: pid,
                    title: p.title || "Untitled Post",
                    content: p.content || "",
                    published: p.published || "",
                    thumbnail: pThumb,
                    fileCount: totalF,
                    selectedFileCount: selF,
                    files: filesList,
                    selected: isPostSel,
                    provider_id: pProv,
                    url: pUrl,
                    is_dm: !!p.is_dm,
                    is_unimported: pIsUnimp,
                    hasVideo: pHasVideo,
                    hasGif: pHasGif
                })
            }
        }
        allPosts = list
        var restoredFilter = (savedSession && savedSession.searchFilter) ? savedSession.searchFilter : ""
        searchFilter = restoredFilter
        searchInput.text = restoredFilter
        postSelectionAnchor = -1
        fileSelectionAnchor = -1
        updateFilteredPosts()
        updateTotals()
        isOpen = true
    }

    function closeModal() {
        _saveCurrentSessionState()
        isOpen = false
        inspectedPost = null
        selectionLightbox.close()
        fromFavoritesBrowser = false
        postSelectionAnchor = -1
        fileSelectionAnchor = -1
    }

    function inspectPost(postId) {
        fileSelectionAnchor = -1
        for (var i = 0; i < allPosts.length; i++) {
            if (allPosts[i].id === postId) {
                // Listed in the order they'll be numbered ("File order in posts"); each file keeps
                // its own ticked state, so re-sorting never changes the selection
                if (bridge && allPosts[i].files && allPosts[i].files.length > 1) {
                    allPosts[i].files = bridge.orderPostFiles(allPosts[i].files)
                }
                inspectedPost = allPosts[i]
                postFilesModel.clear()
                var selInPost = 0
                for (var f = 0; f < allPosts[i].files.length; f++) {
                    var fitem = allPosts[i].files[f]
                    postFilesModel.append(fitem)
                    if (fitem.selected) selInPost++
                }
                selectedFilesInPost = selInPost
                break
            }
        }
    }

    function backToPosts() {
        inspectedPost = null
        selectionLightbox.close()
        fileSelectionAnchor = -1
    }

    function _handleWheelScroll(flickItem, anim, event, maxMomentum) {
        var delta = event.angleDelta.y
        if (delta === 0) return
        var mult = ScrollPhysics.stepWheelMomentum(flickItem, delta, maxMomentum || 3.0)
        var step = (delta / 120.0) * 120 * mult
        var maxY = Math.max(0, flickItem.contentHeight - flickItem.height)
        if (!anim.running) flickItem._targetY = flickItem.contentY
        flickItem._targetY = Math.max(0, Math.min(maxY, flickItem._targetY - step))
        anim.stop()
        anim.from = flickItem.contentY
        anim.to = flickItem._targetY
        anim.start()
        event.accepted = true
    }

    function updateTotals() {
        var selP = 0
        var totalF = 0
        var selF = 0
        for (var i = 0; i < allPosts.length; i++) {
            var p = allPosts[i]
            var nFiles = (p.files && p.files.length) ? p.files.length : (p.fileCount || 0)
            totalF += nFiles

            var pSelF = 0
            if (p.files && p.files.length) {
                for (var f = 0; f < p.files.length; f++) {
                    if (p.files[f].selected) pSelF++
                }
            } else if (p.selected) {
                pSelF = nFiles
            }

            selF += pSelF
            p.selectedFileCount = pSelF
            p.selected = (pSelF > 0)
            if (p.selected) selP++
        }

        selectedCount = selP
        totalFilesCount = totalF
        totalSelectedFiles = selF

        if (inspectedPost && inspectedPost.files) {
            var curSel = 0
            for (var k = 0; k < inspectedPost.files.length; k++) {
                if (inspectedPost.files[k].selected) curSel++
            }
            selectedFilesInPost = curSel
        }
    }

    function updateFilteredPosts() {
        var query = searchFilter.trim().toLowerCase()
        var out = []
        for (var i = 0; i < allPosts.length; i++) {
            var item = allPosts[i]
            if (!query) {
                out.push(item)
            } else {
                var matchTitle = item.title && item.title.toLowerCase().indexOf(query) !== -1
                var matchDate = item.published && item.published.toLowerCase().indexOf(query) !== -1
                if (matchTitle || matchDate) {
                    out.push(item)
                }
            }
        }
        filteredPosts = out
        postSelectionAnchor = -1
        postsModel.clear()
        for (var j = 0; j < out.length; j++) {
            postsModel.append(out[j])
        }
        updateTotals()
    }

    function _applyPostSelected(modelIndex, targetState) {
        postsModel.setProperty(modelIndex, "selected", targetState)
        var id = String(postsModel.get(modelIndex).id || "")
        for (var i = 0; i < allPosts.length; i++) {
            if (String(allPosts[i].id || "") === id) {
                allPosts[i].selected = targetState
                if (allPosts[i].files) {
                    for (var f = 0; f < allPosts[i].files.length; f++) {
                        allPosts[i].files[f].selected = targetState
                    }
                }
                var nFiles = (allPosts[i].files && allPosts[i].files.length)
                             ? allPosts[i].files.length
                             : (allPosts[i].fileCount || 0)
                var newSelF = targetState ? nFiles : 0
                allPosts[i].selectedFileCount = newSelF
                postsModel.setProperty(modelIndex, "selectedFileCount", newSelF)
                break
            }
        }
    }

    function toggleItem(index, shiftPressed) {
        if (index < 0 || index >= postsModel.count) return
        if (!!shiftPressed && postSelectionAnchor >= 0 && postSelectionAnchor < postsModel.count && postSelectionAnchor !== index) {
            var rangeState = postSelectionAnchorState
            var lo = Math.min(postSelectionAnchor, index)
            var hi = Math.max(postSelectionAnchor, index)
            for (var r = lo; r <= hi; r++) {
                _applyPostSelected(r, rangeState)
            }
            updateTotals()
            return
        }
        var current = postsModel.get(index).selected
        var targetState = !current
        _applyPostSelected(index, targetState)
        postSelectionAnchor = index
        postSelectionAnchorState = targetState
        updateTotals()
    }

    function _applyFileSelected(fileIndex, nextState) {
        postFilesModel.setProperty(fileIndex, "selected", nextState)
        if (inspectedPost && inspectedPost.files && inspectedPost.files[fileIndex]) {
            inspectedPost.files[fileIndex].selected = nextState
        }
        modalRoot._selectionTick += 1
    }

    function _syncInspectedPostSelection() {
        if (!inspectedPost) return
        var selFiles = 0
        var files = inspectedPost.files || []
        for (var f = 0; f < files.length; f++) {
            if (files[f].selected) selFiles++
        }
        inspectedPost.selectedFileCount = selFiles
        inspectedPost.selected = (selFiles > 0)
        selectedFilesInPost = selFiles

        for (var j = 0; j < postsModel.count; j++) {
            if (String(postsModel.get(j).id) === String(inspectedPost.id)) {
                postsModel.setProperty(j, "selected", inspectedPost.selected)
                postsModel.setProperty(j, "selectedFileCount", selFiles)
                break
            }
        }
        updateTotals()
    }

    function toggleFileItem(index, shiftPressed) {
        if (!inspectedPost || index < 0 || index >= postFilesModel.count) return
        if (!!shiftPressed && fileSelectionAnchor >= 0 && fileSelectionAnchor < postFilesModel.count && fileSelectionAnchor !== index) {
            var rangeState = fileSelectionAnchorState
            var lo = Math.min(fileSelectionAnchor, index)
            var hi = Math.max(fileSelectionAnchor, index)
            for (var r = lo; r <= hi; r++) {
                _applyFileSelected(r, rangeState)
            }
            _syncInspectedPostSelection()
            return
        }
        var cur = postFilesModel.get(index).selected
        var nextState = !cur
        _applyFileSelected(index, nextState)
        fileSelectionAnchor = index
        fileSelectionAnchorState = nextState
        _syncInspectedPostSelection()
    }

    function selectAllFilesInPost(val) {
        if (!inspectedPost) return
        fileSelectionAnchor = -1
        for (var i = 0; i < postFilesModel.count; i++) {
            _applyFileSelected(i, val)
        }
        _syncInspectedPostSelection()
    }

    function selectAll(val) {
        postSelectionAnchor = -1
        if (searchFilter.trim() !== "") {
            for (var j = 0; j < postsModel.count; j++) {
                _applyPostSelected(j, val)
            }
            updateTotals()
            return
        }
        for (var i = 0; i < allPosts.length; i++) {
            allPosts[i].selected = val
            if (allPosts[i].files) {
                for (var f = 0; f < allPosts[i].files.length; f++) {
                    allPosts[i].files[f].selected = val
                }
                allPosts[i].selectedFileCount = val ? allPosts[i].files.length : 0
            } else {
                allPosts[i].selectedFileCount = val ? (allPosts[i].fileCount || 0) : 0
            }
        }
        for (var k = 0; k < postsModel.count; k++) {
            postsModel.setProperty(k, "selected", val)
            var curF = postsModel.get(k).fileCount || 0
            postsModel.setProperty(k, "selectedFileCount", val ? curF : 0)
        }
        modalRoot._selectionTick += 1
        updateTotals()
    }

    function getSelectedPostIds() {
        var ids = []
        for (var i = 0; i < allPosts.length; i++) {
            if (allPosts[i].selected) {
                ids.push(String(allPosts[i].id))
            }
        }
        return ids
    }

    function getSelectedFilesMap() {
        var map = {}
        for (var i = 0; i < allPosts.length; i++) {
            var p = allPosts[i]
            if (p.selected && p.files && p.files.length) {
                var selectedFilePaths = []
                var allSelected = true
                for (var f = 0; f < p.files.length; f++) {
                    if (p.files[f].selected) {
                        selectedFilePaths.push(p.files[f].path)
                    } else {
                        allSelected = false
                    }
                }
                if (!allSelected) {
                    map[String(p.id)] = selectedFilePaths
                }
            }
        }
        return map
    }

    // ── Lightbox Visualizer Methods (via shared MediaLightboxModal) ─────────
    function openLightbox(index) {
        if (index < 0 || index >= postFilesModel.count) return
        var clickedItem = postFilesModel.get(index)
        if (!isViewableFile(clickedItem)) return

        var mList = []
        var targetEntry = null
        var postObj = inspectedPost || ({})
        var postUnimported = !!postObj.is_unimported
        var postProv = String(postObj.provider_id || "")
        var postLink = String(postObj.url || "")
        var postIdStr = String(postObj.id || "")

        for (var i = 0; i < postFilesModel.count; i++) {
            var f = postFilesModel.get(i)
            if (!f || !isViewableFile(f)) continue
            var mt = _mediaType(f)
            var rawThumb = String(f.previewUrl || f.thumbnail || "")
            var mediaUrl = String(f.url || f.path || "")
            var target = (postUnimported && mt === "image" && rawThumb) ? rawThumb : mediaUrl
            if (!target) continue
            var entry = {
                "path": target,
                "url": mediaUrl || target,
                "name": String(f.name || ("file_" + (i + 1))),
                "ext": _fileExt(f),
                "media_type": mt,
                "thumbUrl": (rawThumb && rawThumb !== target) ? rawThumb : "",
                "size": Number(f.file_size || 0),
                "is_loop": isGifFile(f),
                "provider_id": String(f.provider_id || postProv),
                "postUrl": String(f.postUrl || postLink),
                "postId": String(f.postId || postIdStr),
                "is_unimported": postUnimported,
                "postFileIndex": i
            }
            mList.push(entry)
            if (i === index) targetEntry = entry
        }
        if (!targetEntry || mList.length === 0) return
        selectionLightbox.open(targetEntry, mList)
    }

    function closeLightbox() {
        selectionLightbox.close()
    }

    function prevLightboxItem() {
        if (!selectionLightbox.isOpen) return
        selectionLightbox.prevItem()
    }

    function nextLightboxItem() {
        if (!selectionLightbox.isOpen) return
        selectionLightbox.nextItem()
    }

    ListModel {
        id: postsModel
    }

    ListModel {
        id: postFilesModel
    }

    Connections {
        target: modalRoot.bridge
        function onFileOrderChanged() {
            if (!modalRoot.inspectedPost) return
            selectionLightbox.close()
            modalRoot.inspectPost(modalRoot.inspectedPost.id)
        }
    }

    // Semi-transparent backdrop overlay
    Rectangle {
        anchors.fill: parent
        color: "#05070B"
        opacity: 0.75

        MouseArea {
            anchors.fill: parent
            onClicked: {
                if (modalRoot.lightboxVisible) modalRoot.closeLightbox()
            }
        }

        // Block wheel events from reaching background scrollables
        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: function(event) { event.accepted = true }
        }
    }

    // Centered Dialog Window with Newtonian Spring Entrance
    Rectangle {
        id: dialogBox
        objectName: "postSelectionDialogBox"
        width: Math.max(320, modalRoot.width - 36)
        height: Math.max(280, modalRoot.height - 36)
        anchors.centerIn: parent

        MouseArea {
            id: dialogClickCatcher
            anchors.fill: parent
            z: -1
            onPressed: function(mouse) { mouse.accepted = true }
            onClicked: function(mouse) { mouse.accepted = true }
        }
        radius: 12
        color: "#0F131C"
        border.color: "#222B3D"
        border.width: 1

        scale: modalRoot.isOpen ? 1.0 : 0.88
        transformOrigin: Item.Center

        Behavior on scale {
            NumberAnimation {
                duration: modalRoot.isOpen ? 340 : 200
                easing.type: modalRoot.isOpen ? Easing.OutBack : Easing.InCubic
                easing.overshoot: 1.3
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // ── Header Row ───────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Back Button (when inspecting a single post)
                Rectangle {
                    visible: modalRoot.isInspecting
                    height: 32
                    implicitWidth: backRow.implicitWidth + 16
                    radius: 6
                    color: backMouse.containsMouse ? "#1E293B" : "#161D2B"
                    border.color: backMouse.containsMouse ? "#38BDF8" : "#2D3748"
                    scale: backMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: backRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "←"; font.pixelSize: 13; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: modalRoot.tr("btn_back_to_posts", "Back to Posts")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#E2E8F0"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: backMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.backToPosts()
                    }
                }

                // Back to Favorite Artists Button (when opened from Favorites browser)
                Rectangle {
                    visible: !modalRoot.isInspecting && modalRoot.fromFavoritesBrowser
                    height: 32
                    implicitWidth: backFavRow.implicitWidth + 16
                    radius: 6
                    color: backFavMouse.containsMouse ? "#2A2008" : "#1A170C"
                    border.color: backFavMouse.containsMouse ? "#F59E0B" : "#B45309"
                    border.width: 1

                    Row {
                        id: backFavRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "←"; font.pixelSize: 13; color: "#FCD34D"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: modalRoot.tr("btn_back_to_artists", "Back to Favorite Artists")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#FCD34D"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: backFavMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            modalRoot.closeModal()
                            modalRoot.backToFavoritesRequested()
                        }
                    }
                }

                Text {
                    visible: !modalRoot.isInspecting
                    text: "🖼️"
                    font.pixelSize: 18
                }

                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true

                    RowLayout {
                        spacing: 8
                        Layout.fillWidth: true

                        UnimportedTriangleBadge {
                            id: inspectUnimportedBadge
                            objectName: "postSelectionInspectUnimportedBadge"
                            visible: modalRoot.isInspecting && !!(modalRoot.inspectedPost && modalRoot.inspectedPost.is_unimported)
                            showBackground: false
                            tooltipText: modalRoot.tr("warn_post_unimported", "This post has not been fully imported into Pawchive yet — only a preview thumbnail may be available for images.")
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Text {
                            text: modalRoot.isInspecting
                                ? (modalRoot.inspectedPost ? modalRoot.inspectedPost.title : "")
                                : modalRoot.tr("title_post_selector", "Select Posts to Download")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        UnimportedTriangleBadge {
                            id: creatorUnimportedBadge
                            objectName: "postSelectionCreatorUnimportedBadge"
                            visible: !modalRoot.isInspecting && (modalRoot.hasUnimportedCreator || modalRoot.unimportedCount > 0)
                            showBackground: false
                            tooltipText: modalRoot.hasUnimportedCreator
                                ? modalRoot.tr("warn_creator_unimported", "This creator has not been imported into Pawchive yet — only preview thumbnails may be available for images.")
                                : modalRoot.tr("warn_posts_unimported_some", "Some posts below have not been fully imported into Pawchive yet.")
                            Layout.alignment: Qt.AlignVCenter
                        }

                        // Creator name or date badge
                        Rectangle {
                            height: 20
                            radius: 4
                            color: "#1E293B"
                            border.color: "#334155"
                            implicitWidth: badgeRowText.implicitWidth + 12

                            Row {
                                id: badgeRowText
                                anchors.centerIn: parent
                                spacing: 4
                                Text {
                                    text: modalRoot.isInspecting
                                        ? ("📅 " + (modalRoot.inspectedPost ? modalRoot.inspectedPost.published : ""))
                                        : (modalRoot.creatorName.length > 0 ? modalRoot.creatorName : "Pawchive")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: 600
                                    color: "#38BDF8"
                                }
                            }
                        }

                        // Files in Post Selection Pill (when inspecting)
                        Rectangle {
                            visible: modalRoot.isInspecting
                            height: 20
                            radius: 4
                            color: modalRoot.selectedFilesInPost > 0 ? "#0C2A3D" : "#2A181A"
                            border.color: modalRoot.selectedFilesInPost > 0 ? "#0284C7" : "#DC2626"
                            implicitWidth: inspectSelPillText.implicitWidth + 12

                            Text {
                                id: inspectSelPillText
                                anchors.centerIn: parent
                                text: modalRoot.selectedFilesInPost + " / " + postFilesModel.count + " files selected"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                color: modalRoot.selectedFilesInPost > 0 ? "#38BDF8" : "#F87171"
                            }
                        }
                    }

                    Text {
                        text: modalRoot.isInspecting
                            ? modalRoot.tr("label_inspect_files_subtitle", "Inspect attachments and toggle individual files to download.")
                            : modalRoot.tr("post_selector_subtitle", "Choose specific posts to download or filter visually by thumbnail.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                }

                // Click Mode Toggle Pill (Preview vs Select)
                Rectangle {
                    id: clickModeBtn
                    objectName: "postClickModeBtn"
                    visible: !modalRoot.isInspecting
                    height: 28
                    radius: 6
                    implicitWidth: clickModeRow.implicitWidth + 16
                    color: modalRoot.quickSelectClickMode
                        ? (clickModeMouse.containsMouse ? "#075985" : "#0C2A3D")
                        : (clickModeMouse.containsMouse ? "#1E293B" : "#161D2B")
                    border.color: modalRoot.quickSelectClickMode ? "#0284C7" : (clickModeMouse.containsMouse ? "#475569" : "#2D3748")
                    scale: clickModeMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: clickModeRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text {
                            text: modalRoot.quickSelectClickMode ? "⚡" : "🔍"
                            font.pixelSize: 10
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: modalRoot.quickSelectClickMode ? "Click: Select" : "Click: Preview"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: modalRoot.quickSelectClickMode ? "#38BDF8" : "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: clickModeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.quickSelectClickMode = !modalRoot.quickSelectClickMode
                    }

                    ToolTip.visible: clickModeMouse.containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: modalRoot.quickSelectClickMode
                        ? "Click toggles selection • Ctrl+Click previews post • Shift+Click selects range"
                        : "Click previews post • Ctrl+Click toggles selection • Shift+Click selects range"
                }

                // Re-fetch Posts Button (bypasses cache while preserving saved selections)
                Rectangle {
                    id: refetchPostsBtn
                    objectName: "refetchPostsBtn"
                    visible: !modalRoot.isInspecting && !!modalRoot.bridge && !!modalRoot.bridge.refetchPostsForSelection && !modalRoot.fromFavoritesBrowser
                    height: 28
                    radius: 6
                    implicitWidth: refetchRow.implicitWidth + 16
                    color: refetchMouse.containsMouse ? "#1E293B" : "#161D2B"
                    border.color: refetchMouse.containsMouse ? "#38BDF8" : "#2D3748"
                    scale: refetchMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: refetchRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text {
                            text: "🔄"
                            font.pixelSize: 10
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: modalRoot.tr("action_refetch", "Re-fetch")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: refetchMouse.containsMouse ? "#38BDF8" : "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: refetchMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            modalRoot.closeModal()
                            if (modalRoot.bridge && modalRoot.bridge.refetchPostsForSelection) {
                                modalRoot.bridge.refetchPostsForSelection()
                            }
                        }
                    }

                    ToolTip.visible: refetchMouse.containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: "Re-fetch fresh post list from server (your current selections stay saved)"
                }

                // Close Button ✕
                Rectangle {
                    width: 28
                    height: 28
                    radius: 6
                    color: closeMouse.containsMouse ? "#1E293B" : "#161D2B"
                    border.color: "#2D3748"
                    scale: closeMouse.pressed ? 0.92 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 11
                        color: closeMouse.containsMouse ? "#F87171" : "#94A3B8"
                    }

                    MouseArea {
                        id: closeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.closeModal()
                    }
                }
            }

            // ── Search & Bulk Selection Bar (only when not inspecting) ─────
            RowLayout {
                visible: !modalRoot.isInspecting
                Layout.fillWidth: true
                spacing: 8

                // Search Input Field
                Rectangle {
                    Layout.fillWidth: true
                    height: 32
                    radius: 6
                    color: "#0B0E14"
                    border.color: searchInput.activeFocus ? "#38BDF8" : "#1E293B"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 6

                        Text { text: "🔍"; font.pixelSize: 11; color: "#64748B" }

                        TextInput {
                            id: searchInput
                            Layout.fillWidth: true
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#E2E8F0"
                            clip: true
                            selectByMouse: true

                            Text {
                                text: modalRoot.tr("placeholder_search_posts", "Search posts by title or date...")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                color: "#475569"
                                visible: !searchInput.text && !searchInput.activeFocus
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            onTextChanged: {
                                modalRoot.searchFilter = text
                                modalRoot.updateFilteredPosts()
                            }
                        }

                        Text {
                            visible: searchInput.text.length > 0
                            text: "✕"
                            font.pixelSize: 11
                            color: "#64748B"
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: searchInput.text = ""
                            }
                        }
                    }
                }

                // Select All Button
                Rectangle {
                    Layout.preferredHeight: 32
                    Layout.preferredWidth: Math.max(116, selAllRow.implicitWidth + 28)
                    radius: 6
                    color: selAllMouse.containsMouse ? "#1E293B" : "#161D2B"
                    border.color: "#2D3748"
                    scale: selAllMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: selAllRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "✓"; font.pixelSize: 11; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            id: selAllText
                            text: modalRoot.searchFilter.trim() !== ""
                                  ? "Select Filtered"
                                  : modalRoot.tr("btn_select_all", "Select All")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: selAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.selectAll(true)
                    }
                }

                // Deselect All Button
                Rectangle {
                    Layout.preferredHeight: 32
                    Layout.preferredWidth: Math.max(126, deselAllRow.implicitWidth + 28)
                    radius: 6
                    color: deselAllMouse.containsMouse ? "#1E293B" : "#161D2B"
                    border.color: "#2D3748"
                    scale: deselAllMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: deselAllRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "✕"; font.pixelSize: 11; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            id: deselAllText
                            text: modalRoot.searchFilter.trim() !== ""
                                  ? "Deselect Filtered"
                                  : modalRoot.tr("btn_deselect_all", "Deselect All")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: deselAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.selectAll(false)
                    }
                }
            }

            // Creator-level / unimported posts warning banner
            Rectangle {
                id: creatorUnimportedBanner
                objectName: "postSelectionCreatorUnimportedBanner"
                visible: !modalRoot.isInspecting && (modalRoot.hasUnimportedCreator || modalRoot.unimportedCount > 0)
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.topMargin: 10
                Layout.preferredHeight: visible ? (creatorBannerCol.implicitHeight + 14) : 0
                radius: 8
                color: "#291E0B"
                border.color: "#B45309"
                border.width: 1

                RowLayout {
                    id: creatorBannerCol
                    anchors {
                        left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter
                        leftMargin: 12; rightMargin: 12
                    }
                    spacing: 10

                    UnimportedTriangleBadge {
                        showBackground: false
                        tooltipText: ""
                        Layout.alignment: Qt.AlignVCenter
                    }

                    Text {
                        Layout.fillWidth: true
                        text: modalRoot.hasUnimportedCreator
                            ? modalRoot.tr("warn_creator_unimported", "This creator has not been imported into Pawchive yet — full-resolution media is only served directly from the origin service when available. Only thumbnails may be previewable.")
                            : modalRoot.tr("warn_posts_unimported_some", "Some posts below are not fully imported into Pawchive yet (marked with ⚠️) — full-resolution media may not be previewable until imported.")
                        color: "#FCD34D"
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // ── Main Content Area (Swap between Grid and Inspector View) ──
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                // 1. Grid of Post Cards (When not inspecting)
                Rectangle {
                    id: gridPanel
                    anchors.fill: parent
                    radius: 8
                    color: "#0B0E14"
                    border.color: "#1E293B"
                    clip: true
                    visible: !modalRoot.isInspecting
                    opacity: modalRoot.isInspecting ? 0.0 : 1.0
                    Behavior on opacity { NumberAnimation { duration: 180 } }

                    GridView {
                        id: postsGrid
                        anchors.fill: parent
                        anchors.margins: 10
                        clip: true
                        model: postsModel

                        readonly property int colCount: Math.max(1, Math.floor(width / 220))
                        cellWidth: Math.floor(width / colCount)
                        cellHeight: 224
                        boundsBehavior: Flickable.StopAtBounds

                        property real _targetY: 0
                        property real _lastWheelTime: 0
                        property real _wheelMomentum: 1.0
                        property real _scrollStreak: 0
                        property int _lastWheelDir: 0

                        NumberAnimation {
                            id: postsGridWheelAnim
                            target: postsGrid
                            property: "contentY"
                            duration: 170
                            easing.type: Easing.OutQuad
                        }

                        WheelHandler {
                            target: null
                            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                            onWheel: function(event) {
                                modalRoot._handleWheelScroll(postsGrid, postsGridWheelAnim, event, 3.0)
                            }
                        }

                        ScrollBar.vertical: ScrollBar {
                            id: postsGridScrollBar
                            active: postsGrid.moving || postsGrid.flicking || postsGridScrollHover.hovered
                            policy: ScrollBar.AsNeeded
                            width: 7
                            HoverHandler { id: postsGridScrollHover }
                            contentItem: Rectangle {
                                implicitWidth: 7
                                radius: 3
                                color: postsGridScrollBar.pressed ? "#38BDF8" : (postsGridScrollBar.hovered ? "#0EA5E9" : (postsGridScrollBar.active ? "#38BDF8" : "#64748B"))
                                opacity: postsGridScrollBar.active ? 0.85 : (postsGrid.contentHeight > postsGrid.height ? 0.35 : 0.0)
                                Behavior on opacity { NumberAnimation { duration: 180 } }
                                Behavior on color { ColorAnimation { duration: 150 } }
                            }
                            background: Rectangle {
                                implicitWidth: 7
                                radius: 3
                                color: "#0F172A"
                                opacity: postsGrid.contentHeight > postsGrid.height ? 0.25 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 180 } }
                            }
                        }

                        delegate: Item {
                            width: postsGrid.cellWidth
                            height: postsGrid.cellHeight

                            Rectangle {
                                id: postCard
                                anchors.fill: parent
                                anchors.margins: 6
                                radius: 8
                                color: model.selected ? "#141E2F" : "#10141D"
                                border.color: model.selected ? "#38BDF8" : (cardMouse.containsMouse ? "#334155" : "#1C2433")
                                border.width: model.selected ? 1.5 : 1

                                scale: cardMouse.pressed ? 0.96 : (cardMouse.containsMouse ? 1.02 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }
                                Behavior on color { ColorAnimation { duration: 140 } }
                                Behavior on border.color { ColorAnimation { duration: 140 } }

                                // Card Click: Preview or Toggle according to mode (Ctrl inverts, Shift toggles range)
                                MouseArea {
                                    id: cardMouse
                                    objectName: "postCardMouse"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: function(mouse) {
                                        if (mouse.modifiers & Qt.ShiftModifier) {
                                            modalRoot.toggleItem(index, true)
                                            return
                                        }
                                        var hasCtrl = (mouse.modifiers & Qt.ControlModifier) !== 0
                                        var shouldToggle = modalRoot.quickSelectClickMode ? !hasCtrl : hasCtrl
                                        if (shouldToggle) {
                                            modalRoot.toggleItem(index, false)
                                        } else {
                                            modalRoot.inspectPost(model.id)
                                        }
                                    }
                                }

                                ColumnLayout {
                                    anchors.fill: parent
                                    spacing: 0

                                    // Thumbnail Container
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        color: "#080B11"
                                        radius: 7
                                        clip: true

                                        // Fallback icon
                                        Rectangle {
                                            anchors.fill: parent
                                            color: "#0E131E"
                                            visible: postThumb.status !== Image.Ready
                                            Column {
                                                anchors.centerIn: parent
                                                spacing: 4
                                                Text {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    text: model.hasVideo ? "🎬" : (model.hasGif ? "🎞" : "🖼️")
                                                    font.pixelSize: 22
                                                }
                                                Text {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    text: (model.fileCount || 0) + " files"
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 10
                                                    color: "#475569"
                                                }
                                            }
                                        }

                                        Image {
                                            id: postThumb
                                            anchors.fill: parent
                                            source: modalRoot.safeThumbUrl(model.thumbnail, model.provider_id)
                                            fillMode: Image.PreserveAspectCrop
                                            asynchronous: true
                                            cache: true
                                            opacity: status === Image.Ready ? 1.0 : 0.0
                                            Behavior on opacity { NumberAnimation { duration: 180 } }
                                        }

                                        // Gradient shadow at bottom of image
                                        Rectangle {
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.bottom: parent.bottom
                                            height: 28
                                            gradient: Gradient {
                                                GradientStop { position: 0.0; color: "transparent" }
                                                GradientStop { position: 1.0; color: "#99000000" }
                                            }
                                        }

                                        // Bottom-left media kind pill for video / GIF posts
                                        Rectangle {
                                            visible: !!model.hasVideo || !!model.hasGif
                                            anchors.bottom: parent.bottom
                                            anchors.left: parent.left
                                            anchors.margins: 6
                                            height: 18
                                            implicitWidth: postMediaKindTxt.implicitWidth + 10
                                            radius: 4
                                            color: model.hasVideo ? "#CC0C2A3D" : "#CC1E1B4B"
                                            border.color: model.hasVideo ? "#38BDF8" : "#818CF8"
                                            border.width: 1
                                            z: 2

                                            Text {
                                                id: postMediaKindTxt
                                                anchors.centerIn: parent
                                                text: model.hasVideo ? "▶ VIDEO" : "🎞 GIF"
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 9
                                                font.weight: Font.Bold
                                                color: model.hasVideo ? "#38BDF8" : "#A5B4FC"
                                            }
                                        }

                                        // Unimported warning badge (top-right, beside checkbox)
                                        UnimportedTriangleBadge {
                                            objectName: "postSelectionUnimportedBadge"
                                            visible: !!model.is_unimported
                                            anchors.top: parent.top
                                            anchors.right: parent.right
                                            anchors.topMargin: 6
                                            anchors.rightMargin: 38
                                            z: 3
                                            showBackground: true
                                            tooltipText: modalRoot.tr("warn_post_unimported_short", "Not imported into Pawchive yet — full-resolution media may not be available.")
                                        }

                                        // Selected Files / Total Files Count Badge (top-left)
                                        Rectangle {
                                            anchors.top: parent.top
                                            anchors.left: parent.left
                                            anchors.margins: 6
                                            height: 20
                                            implicitWidth: fileBadgeText.implicitWidth + 10
                                            radius: 4
                                            color: {
                                                var selF = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                                var totF = model.fileCount || 0
                                                if (selF === totF && totF > 0) return "#CC0A2338"
                                                if (selF > 0) return "#CC341D09"
                                                return "#CC0A0E17"
                                            }
                                            border.color: {
                                                var selF2 = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                                var totF2 = model.fileCount || 0
                                                if (selF2 === totF2 && totF2 > 0) return "#0284C7"
                                                if (selF2 > 0) return "#D97706"
                                                return "#2D3748"
                                            }

                                            Row {
                                                id: fileBadgeText
                                                anchors.centerIn: parent
                                                spacing: 3
                                                Text { text: "📎"; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                                                Text {
                                                    text: {
                                                        var s = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                                        var t = model.fileCount || 0
                                                        return s + " / " + t + " files"
                                                    }
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 9
                                                    font.weight: Font.Bold
                                                    color: {
                                                        var s2 = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                                        var t2 = model.fileCount || 0
                                                        if (s2 === t2 && t2 > 0) return "#38BDF8"
                                                        if (s2 > 0) return "#FBBF24"
                                                        return "#94A3B8"
                                                    }
                                                    anchors.verticalCenter: parent.verticalCenter
                                                }
                                            }
                                        }

                                        // Selection checkbox badge (top-right) with Newtonian bounce
                                        Rectangle {
                                            id: checkBadge
                                            anchors.top: parent.top
                                            anchors.right: parent.right
                                            anchors.margins: 6
                                            width: 26
                                            height: 26
                                            radius: 6
                                            color: model.selected ? "#38BDF8" : (checkMouse.containsMouse ? "#1A3A58" : "#990A0E17")
                                            border.color: model.selected ? "#38BDF8" : (checkMouse.containsMouse ? "#38BDF8" : "#475569")
                                            border.width: 1.5

                                            scale: model.selected ? 1.0 : (checkMouse.containsMouse ? 1.0 : 0.9)
                                            Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35; mass: 1.0 } }
                                            Behavior on color { ColorAnimation { duration: 100 } }
                                            Behavior on border.color { ColorAnimation { duration: 100 } }

                                            Text {
                                                anchors.centerIn: parent
                                                text: "✓"
                                                font.pixelSize: 13
                                                font.weight: Font.Bold
                                                color: "#0A0E17"
                                                visible: model.selected
                                            }

                                            MouseArea {
                                                id: checkMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                ToolTip.visible: containsMouse
                                                ToolTip.delay: 300
                                                ToolTip.text: (model.selected ? "Deselect post" : "Select post") + "\nShift+click to select a range"
                                                onClicked: function(mouse) {
                                                    mouse.accepted = true
                                                    modalRoot.toggleItem(index, (mouse.modifiers & Qt.ShiftModifier) !== 0)
                                                }
                                            }
                                        }

                                        // Inspect hover badge (bottom-right of thumbnail)
                                        Rectangle {
                                            anchors.bottom: parent.bottom
                                            anchors.right: parent.right
                                            anchors.margins: 6
                                            height: 20
                                            implicitWidth: inspectPillText.implicitWidth + 10
                                            radius: 4
                                            color: cardMouse.containsMouse ? "#0284C7" : "#B30F172A"
                                            border.color: "#38BDF8"
                                            visible: cardMouse.containsMouse || (model.fileCount > 1)

                                            Row {
                                                id: inspectPillText
                                                anchors.centerIn: parent
                                                spacing: 3
                                                Text { text: "🔍"; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                                                Text {
                                                    text: modalRoot.tr("btn_inspect_card", "Inspect")
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 9
                                                    font.weight: Font.Bold
                                                    color: "#FFFFFF"
                                                    anchors.verticalCenter: parent.verticalCenter
                                                }
                                            }
                                        }
                                    }

                                    // Card Footer (Title & Published Date)
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 52
                                        color: "transparent"

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 6
                                            spacing: 2

                                            Text {
                                                text: model.title || "Untitled"
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 11
                                                font.weight: Font.DemiBold
                                                color: model.selected ? "#F1F5F9" : "#94A3B8"
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }

                                            RowLayout {
                                                spacing: 4
                                                Text { text: "📅"; font.pixelSize: 9; color: "#64748B" }
                                                Text {
                                                    text: model.published || "Unknown"
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 10
                                                    color: "#64748B"
                                                    Layout.fillWidth: true
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Empty state indicator
                    Column {
                        anchors.centerIn: parent
                        spacing: 8
                        visible: postsModel.count === 0

                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "🔍"; font.pixelSize: 28 }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modalRoot.tr("no_matching_posts", "No posts match your search.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 13
                            color: "#64748B"
                        }
                    }
                }

                // 2. Detail Inspector Panel (When inspecting a single post)
                Rectangle {
                    id: detailPanel
                    anchors.fill: parent
                    radius: 8
                    color: "#0B0E14"
                    border.color: "#1E293B"
                    clip: true
                    visible: modalRoot.isInspecting
                    opacity: modalRoot.isInspecting ? 1.0 : 0.0
                    Behavior on opacity { NumberAnimation { duration: 180 } }

                    Flickable {
                        id: inspectorFlickable
                        objectName: "postSelectionInspectorFlickable"
                        anchors.fill: parent
                        anchors.margins: 14
                        contentWidth: width
                        contentHeight: detailCol.implicitHeight + 30
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds

                        property real _targetY: 0
                        property real _lastWheelTime: 0
                        property real _wheelMomentum: 1.0
                        property real _scrollStreak: 0
                        property int _lastWheelDir: 0

                        onMovingChanged: {
                            if (moving) {
                                inspectorWheelAnim.stop()
                                _targetY = contentY
                            }
                        }

                        NumberAnimation {
                            id: inspectorWheelAnim
                            target: inspectorFlickable
                            property: "contentY"
                            duration: 170
                            easing.type: Easing.OutQuad
                        }

                        WheelHandler {
                            target: null
                            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                            onWheel: function(event) {
                                modalRoot._handleWheelScroll(inspectorFlickable, inspectorWheelAnim, event, 2.8)
                            }
                        }

                        ScrollBar.vertical: ScrollBar {
                            id: inspectorScrollBar
                            active: inspectorFlickable.moving || inspectorFlickable.flicking || inspectorWheelAnim.running || inspectorScrollHover.hovered
                            policy: ScrollBar.AsNeeded
                            width: 7
                            HoverHandler { id: inspectorScrollHover }
                            contentItem: Rectangle {
                                implicitWidth: 7
                                radius: 3
                                color: inspectorScrollBar.pressed ? "#38BDF8" : (inspectorScrollBar.hovered ? "#0EA5E9" : (inspectorScrollBar.active ? "#38BDF8" : "#64748B"))
                                opacity: inspectorScrollBar.active ? 0.85 : (inspectorFlickable.contentHeight > inspectorFlickable.height ? 0.35 : 0.0)
                                Behavior on opacity { NumberAnimation { duration: 180 } }
                                Behavior on color { ColorAnimation { duration: 150 } }
                            }
                            background: Rectangle {
                                implicitWidth: 7
                                radius: 3
                                color: "#0F172A"
                                opacity: inspectorFlickable.contentHeight > inspectorFlickable.height ? 0.25 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 180 } }
                            }
                        }

                        ColumnLayout {
                            id: detailCol
                            width: parent.width
                            spacing: 14

                            // Unimported post warning banner
                            Rectangle {
                                id: postUnimportedBanner
                                objectName: "postSelectionUnimportedBanner"
                                visible: !!(modalRoot.inspectedPost && modalRoot.inspectedPost.is_unimported)
                                Layout.fillWidth: true
                                Layout.preferredHeight: visible ? (postUnimpRow.implicitHeight + 16) : 0
                                radius: 8
                                color: "#291E0B"
                                border.color: "#B45309"
                                border.width: 1

                                RowLayout {
                                    id: postUnimpRow
                                    anchors {
                                        left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter
                                        leftMargin: 12; rightMargin: 12
                                    }
                                    spacing: 10

                                    UnimportedTriangleBadge {
                                        showBackground: false
                                        tooltipText: ""
                                        Layout.alignment: Qt.AlignVCenter
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: modalRoot.tr("warn_post_unimported", "This post has not been fully imported into Pawchive yet — only a preview thumbnail may be available for images.")
                                        color: "#FCD34D"
                                        font.pixelSize: 11
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }

                            // Description & Content Card (if available)
                            Rectangle {
                                visible: modalRoot.inspectedPost && modalRoot.inspectedPost.content && modalRoot.inspectedPost.content.length > 0
                                Layout.fillWidth: true
                                implicitHeight: descCol.implicitHeight + 20
                                radius: 8
                                color: "#10141D"
                                border.color: "#1E293B"
                                border.width: 1

                                ColumnLayout {
                                    id: descCol
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 6

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text { text: "📝"; font.pixelSize: 12 }
                                        Text {
                                            text: modalRoot.tr("label_post_description", "Post Description & Notes")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: Font.Bold
                                            color: "#94A3B8"
                                            Layout.fillWidth: true
                                        }
                                    }

                                    TextEdit {
                                        Layout.fillWidth: true
                                        text: modalRoot.inspectedPost ? modalRoot.inspectedPost.content : ""
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 12
                                        color: "#E2E8F0"
                                        wrapMode: TextEdit.Wrap
                                        readOnly: true
                                        selectByMouse: true
                                    }
                                }
                            }

                            // Attached Media & Files Header + Action Buttons + View Mode Switcher
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Text { text: "📎"; font.pixelSize: 13 }
                                Text {
                                    text: modalRoot.tr("label_attached_files", "Attached Media & Files") + " (" + postFilesModel.count + ")"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    font.weight: Font.Bold
                                    color: "#F1F5F9"
                                    Layout.fillWidth: true
                                }

                                // Which file is #1 (same setting as "File order in posts" in the Downloader tab)
                                StyledComboBox {
                                    implicitHeight: 28
                                    implicitWidth: 140
                                    model: [
                                        { text: modalRoot.tr("file_order_posted", "As posted"), value: "posted" },
                                        { text: modalRoot.tr("file_order_reversed", "Reversed"), value: "reversed" },
                                        { text: modalRoot.tr("file_order_name", "By file name"), value: "name" }
                                    ]
                                    value: modalRoot.bridge ? modalRoot.bridge.fileOrder : "posted"
                                    tooltip: modalRoot.tr("tip_file_order_modal", "Order of the files: #1 is downloaded first and numbered first. This is the \"File order in posts\" setting from the Downloader tab.")
                                    onValuePicked: function(v) { if (modalRoot.bridge) modalRoot.bridge.fileOrder = v }
                                }

                                // View Switcher: Gallery Mode vs List Mode (Physical Newtonian Spring Slider)
                                Rectangle {
                                    id: viewSwitchContainer
                                    height: 28
                                    width: 68
                                    radius: 6
                                    color: "#161D2B"
                                    border.color: "#2D3748"

                                    // Sliding Physical Indicator Pill (Newtonian spring glide)
                                    Rectangle {
                                        id: viewSwitchIndicator
                                        y: 3
                                        x: modalRoot.visualGalleryMode ? 3 : 35
                                        width: 30
                                        height: 22
                                        radius: 4
                                        color: "#0284C7"
                                        scale: (gridSwitchMouse.pressed || listSwitchMouse.pressed) ? 0.91 : 1.0

                                        Behavior on x {
                                            SpringAnimation {
                                                spring: 4.8
                                                damping: 0.40
                                                mass: 1.05
                                                epsilon: 0.2
                                            }
                                        }
                                        Behavior on scale {
                                            SpringAnimation {
                                                spring: 4.5
                                                damping: 0.35
                                                mass: 1.0
                                            }
                                        }
                                    }

                                    Row {
                                        anchors.fill: parent
                                        anchors.margins: 3
                                        spacing: 2

                                        // Grid Mode Option
                                        Item {
                                            width: 30
                                            height: 22
                                            Text {
                                                anchors.centerIn: parent
                                                text: "🖼️"
                                                font.pixelSize: 11
                                                scale: modalRoot.visualGalleryMode ? 1.08 : 0.95
                                                opacity: modalRoot.visualGalleryMode ? 1.0 : 0.65
                                                Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.35; mass: 1.0 } }
                                                Behavior on opacity { NumberAnimation { duration: 120 } }
                                            }
                                            MouseArea {
                                                id: gridSwitchMouse
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: modalRoot.visualGalleryMode = true
                                            }
                                        }

                                        // List Mode Option
                                        Item {
                                            width: 30
                                            height: 22
                                            Text {
                                                anchors.centerIn: parent
                                                text: "📋"
                                                font.pixelSize: 11
                                                scale: !modalRoot.visualGalleryMode ? 1.08 : 0.95
                                                opacity: !modalRoot.visualGalleryMode ? 1.0 : 0.65
                                                Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.35; mass: 1.0 } }
                                                Behavior on opacity { NumberAnimation { duration: 120 } }
                                            }
                                            MouseArea {
                                                id: listSwitchMouse
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: modalRoot.visualGalleryMode = false
                                            }
                                        }
                                    }
                                }

                                // Select All Files
                                Rectangle {
                                    Layout.preferredHeight: 30
                                    Layout.preferredWidth: Math.max(108, selAllFilesRow.implicitWidth + 26)
                                    radius: 6
                                    color: selAllFilesMouse.containsMouse ? "#1E293B" : "#161D2B"
                                    border.color: "#2D3748"
                                    scale: selAllFilesMouse.pressed ? 0.94 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                                    Row {
                                        id: selAllFilesRow
                                        anchors.centerIn: parent
                                        spacing: 6
                                        Text { text: "✓"; font.pixelSize: 11; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                                        Text {
                                            id: selAllFilesText
                                            text: modalRoot.tr("btn_select_all", "Select All")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: 600
                                            color: "#CBD5E1"
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                    MouseArea {
                                        id: selAllFilesMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: modalRoot.selectAllFilesInPost(true)
                                    }
                                }

                                // Deselect All Files
                                Rectangle {
                                    Layout.preferredHeight: 30
                                    Layout.preferredWidth: Math.max(118, deselAllFilesRow.implicitWidth + 26)
                                    radius: 6
                                    color: deselAllFilesMouse.containsMouse ? "#1E293B" : "#161D2B"
                                    border.color: "#2D3748"
                                    scale: deselAllFilesMouse.pressed ? 0.94 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                                    Row {
                                        id: deselAllFilesRow
                                        anchors.centerIn: parent
                                        spacing: 6
                                        Text { text: "✕"; font.pixelSize: 11; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
                                        Text {
                                            id: deselAllFilesText
                                            text: modalRoot.tr("btn_deselect_all", "Deselect All")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: 600
                                            color: "#CBD5E1"
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                    MouseArea {
                                        id: deselAllFilesMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: modalRoot.selectAllFilesInPost(false)
                                    }
                                }
                            }

                            // ── View Mode Container with Newtonian Weight-Based Transitions ──
                            Item {
                                id: viewModeContainer
                                Layout.fillWidth: true
                                implicitHeight: modalRoot.visualGalleryMode ? galleryViewWrap.implicitHeight : listViewWrap.implicitHeight

                                Behavior on implicitHeight {
                                    NumberAnimation {
                                        duration: 280
                                        easing.type: Easing.OutCubic
                                    }
                                }

                                // ── 1. Visual Gallery Mode (Responsive Grid with Physical Weight) ──
                                Item {
                                    id: galleryViewWrap
                                    width: parent.width
                                    implicitHeight: Math.max(40, galleryFlow.childrenRect.height)
                                    opacity: modalRoot.visualGalleryMode ? 1.0 : 0.0
                                    y: modalRoot.visualGalleryMode ? 0 : -14
                                    scale: modalRoot.visualGalleryMode ? 1.0 : 0.965
                                    transformOrigin: Item.Top
                                    visible: opacity > 0.001

                                    Behavior on opacity {
                                        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
                                    }
                                    Behavior on y {
                                        SpringAnimation {
                                            spring: 3.6
                                            damping: 0.38
                                            mass: 1.15
                                            epsilon: 0.25
                                        }
                                    }
                                    Behavior on scale {
                                        SpringAnimation {
                                            spring: 3.8
                                            damping: 0.36
                                            mass: 1.10
                                            epsilon: 0.005
                                        }
                                    }

                                    Flow {
                                        id: galleryFlow
                                        width: parent.width
                                        spacing: 10

                                        Repeater {
                                    model: postFilesModel

                                    delegate: Rectangle {
                                        id: galTile
                                        width: 175
                                        height: 185
                                        radius: 8
                                        color: model.selected ? "#141E2F" : "#10141D"
                                        border.color: model.selected ? "#38BDF8" : (galMouse.containsMouse ? "#334155" : "#1C2433")
                                        border.width: model.selected ? 1.5 : 1

                                        readonly property var _fMeta: ({
                                            "name": model.name || "",
                                            "path": model.path || "",
                                            "url": model.url || "",
                                            "ext": model.ext || "",
                                            "media_type": model.media_type || "",
                                            "is_loop": !!model.is_loop
                                        })
                                        readonly property bool isVideoItem: modalRoot.isVideoFile(_fMeta)
                                        readonly property bool isAudioItem: modalRoot.isAudioFile(_fMeta)
                                        readonly property bool isGifItem: modalRoot.isGifFile(_fMeta)
                                        readonly property bool isArchiveItem: modalRoot._mediaType(_fMeta) === "archive"
                                        readonly property bool isViewableItem: modalRoot.isViewableFile(_fMeta)
                                        readonly property string kindText: modalRoot.fileKindLabel(_fMeta)

                                        scale: galMouse.pressed ? 0.96 : (galMouse.containsMouse ? 1.03 : 1.0)
                                        transformOrigin: Item.Center
                                        Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.35; mass: 1.0 } }
                                        Behavior on color { ColorAnimation { duration: 120 } }
                                        Behavior on border.color { ColorAnimation { duration: 120 } }

                                        // Background click area (z:0, behind everything) - toggles selection (Ctrl+click previews)
                                        MouseArea {
                                            id: galMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            z: 0
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: function(mouse) {
                                                if (mouse.modifiers & Qt.ShiftModifier) {
                                                    modalRoot.toggleFileItem(index, true)
                                                    return
                                                }
                                                if (mouse.modifiers & Qt.ControlModifier) {
                                                    if (galTile.isViewableItem) modalRoot.openLightbox(index)
                                                    return
                                                }
                                                modalRoot.toggleFileItem(index, false)
                                            }
                                        }

                                        ColumnLayout {
                                            anchors.fill: parent
                                            spacing: 0
                                            z: 1

                                            // Large Image / Media Preview
                                            Rectangle {
                                                Layout.fillWidth: true
                                                Layout.fillHeight: true
                                                radius: 7
                                                color: "#080B11"
                                                clip: true

                                                // Media icon fallback
                                                Rectangle {
                                                    anchors.fill: parent
                                                    color: "#0D111A"
                                                    visible: galThumb.status !== Image.Ready
                                                    Column {
                                                        anchors.centerIn: parent
                                                        spacing: 4
                                                        Text {
                                                            anchors.horizontalCenter: parent.horizontalCenter
                                                            text: galTile.isArchiveItem ? "📦"
                                                                  : (galTile.isVideoItem ? "🎬"
                                                                  : (galTile.isAudioItem ? "🎵"
                                                                  : (galTile.isGifItem ? "🎞" : "🖼️")))
                                                            font.pixelSize: 28
                                                        }
                                                        Text {
                                                            anchors.horizontalCenter: parent.horizontalCenter
                                                            text: "File #" + (index + 1)
                                                            font.pixelSize: 9
                                                            color: "#64748B"
                                                        }
                                                    }
                                                }

                                                Image {
                                                    id: galThumb
                                                    anchors.fill: parent
                                                    source: modalRoot.safeThumbUrl(model.previewUrl || model.thumbnail, model.provider_id)
                                                    fillMode: Image.PreserveAspectCrop
                                                    asynchronous: true
                                                    cache: true
                                                    opacity: status === Image.Ready ? 1.0 : 0.0
                                                    Behavior on opacity { NumberAnimation { duration: 180 } }
                                                }

                                                // Play overlay indicator for videos/audio when thumbnail is visible
                                                Rectangle {
                                                    visible: (galTile.isVideoItem || galTile.isAudioItem) && galThumb.status === Image.Ready
                                                    anchors.centerIn: parent
                                                    width: 36
                                                    height: 36
                                                    radius: 18
                                                    color: "#B30A0E17"
                                                    border.color: "#38BDF8"
                                                    border.width: 1.5
                                                    z: 2
                                                    Text {
                                                        anchors.centerIn: parent
                                                        anchors.horizontalCenterOffset: 1
                                                        text: "▶"
                                                        font.pixelSize: 13
                                                        color: "#F8FAFC"
                                                    }
                                                }

                                                // Top-Left Format Pill
                                                Rectangle {
                                                    anchors.top: parent.top
                                                    anchors.left: parent.left
                                                    anchors.margins: 5
                                                    height: 18
                                                    implicitWidth: galFormatText.implicitWidth + 8
                                                    radius: 3
                                                    color: galTile.isGifItem ? "#CC1E1B4B"
                                                           : (galTile.isVideoItem ? "#CC0C2A3D"
                                                           : (galTile.isAudioItem ? "#CC042F2E" : "#CC080C14"))
                                                    border.color: galTile.isGifItem ? "#818CF8"
                                                                  : (galTile.isVideoItem ? "#38BDF8"
                                                                  : (galTile.isAudioItem ? "#2DD4BF" : "#334155"))

                                                    Text {
                                                        id: galFormatText
                                                        anchors.centerIn: parent
                                                        text: galTile.kindText
                                                        font.family: "Segoe UI, sans-serif"
                                                        font.pixelSize: 9
                                                        font.weight: Font.Bold
                                                        color: galTile.isGifItem ? "#A5B4FC"
                                                               : (galTile.isVideoItem ? "#38BDF8"
                                                               : (galTile.isAudioItem ? "#5EEAD4" : "#E2E8F0"))
                                                    }
                                                }

                                                // Top-Right Checkbox (Direct Toggle, z:3)
                                                Rectangle {
                                                    anchors.top: parent.top
                                                    anchors.right: parent.right
                                                    anchors.margins: 5
                                                    width: 24
                                                    height: 24
                                                    radius: 5
                                                    z: 3
                                                    color: model.selected ? "#38BDF8" : "#99080C14"
                                                    border.color: model.selected ? "#38BDF8" : "#475569"
                                                    border.width: 1

                                                    scale: model.selected ? 1.0 : 0.92
                                                    Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35; mass: 1.0 } }

                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "✓"
                                                        font.pixelSize: 13
                                                        font.weight: Font.Bold
                                                        color: "#0A0E17"
                                                        visible: model.selected
                                                    }

                                                    MouseArea {
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: function(mouse) {
                                                            mouse.accepted = true
                                                            modalRoot.toggleFileItem(index, (mouse.modifiers & Qt.ShiftModifier) !== 0)
                                                        }
                                                    }
                                                }

                                                // Hover Zoom / Play / Expand Badge (bottom-right, clickable for Lightbox)
                                                Rectangle {
                                                    id: expandBadgeRect
                                                    objectName: "expandBadgeRect"
                                                    anchors.bottom: parent.bottom
                                                    anchors.right: parent.right
                                                    anchors.margins: 5
                                                    height: 22
                                                    implicitWidth: expandPillText.implicitWidth + 12
                                                    radius: 4

                                                    color: !galTile.isViewableItem
                                                           ? "#1E293B"
                                                           : (expandMouse.containsMouse ? "#0284C7"
                                                              : ((galTile.isVideoItem || galTile.isAudioItem) ? "#CC0C2A3D" : "#B30A121F"))
                                                    border.color: !galTile.isViewableItem
                                                                  ? "#334155"
                                                                  : (expandMouse.containsMouse ? "#38BDF8"
                                                                     : ((galTile.isVideoItem || galTile.isAudioItem) ? "#0284C7" : "#334155"))
                                                    border.width: 1
                                                    opacity: (galMouse.containsMouse || expandMouse.containsMouse) ? 1.0 : 0.78
                                                    Behavior on opacity { NumberAnimation { duration: 120 } }
                                                    Behavior on color { ColorAnimation { duration: 100 } }
                                                    z: 3

                                                    Row {
                                                        id: expandPillText
                                                        anchors.centerIn: parent
                                                        spacing: 3
                                                        Text {
                                                            text: (galTile.isVideoItem || galTile.isAudioItem) ? "▶"
                                                                  : (galTile.isViewableItem ? "🔍" : "📦")
                                                            font.pixelSize: 9
                                                            anchors.verticalCenter: parent.verticalCenter
                                                        }
                                                        Text {
                                                            objectName: "expandBadgeLabel"
                                                            text: (galTile.isVideoItem || galTile.isAudioItem) ? "Play"
                                                                  : (galTile.isViewableItem ? "Preview" : "File")
                                                            font.family: "Segoe UI, sans-serif"
                                                            font.pixelSize: 9
                                                            font.weight: Font.Bold
                                                            color: !galTile.isViewableItem
                                                                   ? "#94A3B8"
                                                                   : (expandMouse.containsMouse ? "#FFFFFF"
                                                                      : ((galTile.isVideoItem || galTile.isAudioItem) ? "#38BDF8" : "#CBD5E1"))
                                                            anchors.verticalCenter: parent.verticalCenter
                                                        }
                                                    }

                                                    MouseArea {
                                                        id: expandMouse
                                                        objectName: "expandBadgeMouse"
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: galTile.isViewableItem ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                        enabled: galTile.isViewableItem
                                                        onClicked: function(mouse) {
                                                            mouse.accepted = true
                                                            modalRoot.openLightbox(index)
                                                        }
                                                    }
                                                }
                                            }

                                            // Filename & Details Bar
                                            Rectangle {
                                                Layout.fillWidth: true
                                                height: 38
                                                color: "transparent"

                                                ColumnLayout {
                                                    anchors.fill: parent
                                                    anchors.margins: 6
                                                    spacing: 1

                                                    RowLayout {
                                                        spacing: 4
                                                        Text {
                                                            text: model.name || "attachment"
                                                            font.family: "Segoe UI, sans-serif"
                                                            font.pixelSize: 10
                                                            font.weight: Font.DemiBold
                                                            color: model.selected ? "#F1F5F9" : "#64748B"
                                                            elide: Text.ElideMiddle
                                                            Layout.fillWidth: true
                                                        }

                                                        Rectangle {
                                                            visible: !!model.is_main
                                                            height: 14
                                                            implicitWidth: galMainText.implicitWidth + 6
                                                            radius: 2
                                                            color: "#0F2942"
                                                            border.color: "#0284C7"
                                                            Text {
                                                                id: galMainText
                                                                anchors.centerIn: parent
                                                                text: "MAIN"
                                                                font.pixelSize: 7
                                                                font.weight: Font.Bold
                                                                color: "#38BDF8"
                                                            }
                                                        }
                                                    }

                                                    Text {
                                                        text: "#" + (index + 1)
                                                        font.family: "Segoe UI, sans-serif"
                                                        font.pixelSize: 9
                                                        color: "#475569"
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ── 2. List Mode (Compact File Rows with Physical Settling) ──
                        Item {
                                    id: listViewWrap
                                    width: parent.width
                                    implicitHeight: Math.max(40, listCol.childrenRect.height)
                                    opacity: !modalRoot.visualGalleryMode ? 1.0 : 0.0
                                    y: !modalRoot.visualGalleryMode ? 0 : 14
                                    scale: !modalRoot.visualGalleryMode ? 1.0 : 0.965
                                    transformOrigin: Item.Top
                                    visible: opacity > 0.001

                                    Behavior on opacity {
                                        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
                                    }
                                    Behavior on y {
                                        SpringAnimation {
                                            spring: 3.6
                                            damping: 0.38
                                            mass: 1.15
                                            epsilon: 0.25
                                        }
                                    }
                                    Behavior on scale {
                                        SpringAnimation {
                                            spring: 3.8
                                            damping: 0.36
                                            mass: 1.10
                                            epsilon: 0.005
                                        }
                                    }

                                    ColumnLayout {
                                        id: listCol
                                        width: parent.width
                                        spacing: 6

                                        Repeater {
                                    model: postFilesModel

                                    delegate: Item {
                                        id: listRowItem
                                        Layout.fillWidth: true
                                        height: 52

                                        readonly property var _fMeta: ({
                                            "name": model.name || "",
                                            "path": model.path || "",
                                            "url": model.url || "",
                                            "ext": model.ext || "",
                                            "media_type": model.media_type || "",
                                            "is_loop": !!model.is_loop
                                        })
                                        readonly property bool isVideoItem: modalRoot.isVideoFile(_fMeta)
                                        readonly property bool isAudioItem: modalRoot.isAudioFile(_fMeta)
                                        readonly property bool isGifItem: modalRoot.isGifFile(_fMeta)
                                        readonly property bool isArchiveItem: modalRoot._mediaType(_fMeta) === "archive"
                                        readonly property bool isViewableItem: modalRoot.isViewableFile(_fMeta)
                                        readonly property string kindText: modalRoot.fileKindLabel(_fMeta)

                                        // Background rect (hover state driven by fileRowBg)
                                        Rectangle {
                                            id: listRowRect
                                            anchors.fill: parent
                                            radius: 7
                                            color: model.selected ? "#141E2F" : (fileRowHover.containsMouse ? "#0F1520" : "#10141D")
                                            border.color: model.selected ? "#38BDF8" : (fileRowHover.containsMouse ? "#334155" : "#1C2433")
                                            border.width: model.selected ? 1.5 : 1

                                            scale: fileRowHover.pressed ? 0.985 : (fileRowHover.containsMouse ? 1.008 : 1.0)
                                            Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35; mass: 1.0 } }
                                            Behavior on color { ColorAnimation { duration: 120 } }
                                            Behavior on border.color { ColorAnimation { duration: 120 } }
                                        }

                                        // Background hover/click (sits behind children via z)
                                        MouseArea {
                                            id: fileRowHover
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            z: 0
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: function(mouse) {
                                                if (mouse.modifiers & Qt.ShiftModifier) {
                                                    modalRoot.toggleFileItem(index, true)
                                                    return
                                                }
                                                if (mouse.modifiers & Qt.ControlModifier) {
                                                    if (listRowItem.isViewableItem) modalRoot.openLightbox(index)
                                                    return
                                                }
                                                modalRoot.toggleFileItem(index, false)
                                            }
                                        }

                                        // Content row (z:1 so it sits above the background MouseArea)
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 10
                                            anchors.rightMargin: 12
                                            anchors.topMargin: 0
                                            anchors.bottomMargin: 0
                                            spacing: 10
                                            z: 1

                                            // File type icon / thumbnail
                                            Rectangle {
                                                width: 36
                                                height: 36
                                                radius: 5
                                                color: "#0B0E14"
                                                border.color: "#222B3D"
                                                clip: true
                                                Layout.alignment: Qt.AlignVCenter

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: listRowItem.isArchiveItem ? "📦"
                                                          : (listRowItem.isVideoItem ? "🎬"
                                                          : (listRowItem.isAudioItem ? "🎵"
                                                          : (listRowItem.isGifItem ? "🎞" : "🖼️")))
                                                    font.pixelSize: 16
                                                }

                                                Image {
                                                    id: listRowThumbImg
                                                    anchors.fill: parent
                                                    source: modalRoot.safeThumbUrl(model.thumbnail, model.provider_id)
                                                    fillMode: Image.PreserveAspectCrop
                                                    visible: status === Image.Ready
                                                    cache: true
                                                }

                                                Rectangle {
                                                    visible: listRowItem.isVideoItem && listRowThumbImg.status === Image.Ready
                                                    anchors.right: parent.right
                                                    anchors.bottom: parent.bottom
                                                    anchors.margins: 2
                                                    width: 14
                                                    height: 14
                                                    radius: 7
                                                    color: "#CC0A0E17"
                                                    border.color: "#38BDF8"
                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "▶"
                                                        font.pixelSize: 7
                                                        color: "#38BDF8"
                                                    }
                                                }
                                            }

                                            // Filename column (fills available width)
                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 3
                                                Layout.alignment: Qt.AlignVCenter

                                                RowLayout {
                                                    spacing: 6
                                                    Layout.fillWidth: true
                                                    Text {
                                                        text: model.name || "attachment"
                                                        font.family: "Segoe UI, monospace, sans-serif"
                                                        font.pixelSize: 12
                                                        font.weight: Font.DemiBold
                                                        color: model.selected ? "#F1F5F9" : "#64748B"
                                                        elide: Text.ElideMiddle
                                                        Layout.fillWidth: true
                                                    }

                                                    // Main file badge
                                                    Rectangle {
                                                        visible: !!model.is_main
                                                        height: 16
                                                        Layout.preferredWidth: mainFileText2.implicitWidth + 10
                                                        radius: 3
                                                        color: "#0F2942"
                                                        border.color: "#0284C7"
                                                        Layout.alignment: Qt.AlignVCenter
                                                        Text {
                                                            id: mainFileText2
                                                            anchors.centerIn: parent
                                                            text: "MAIN"
                                                            font.pixelSize: 8
                                                            font.weight: Font.Bold
                                                            color: "#38BDF8"
                                                        }
                                                    }
                                                }

                                                Text {
                                                    text: listRowItem.kindText !== "FILE"
                                                          ? ("Format: " + listRowItem.kindText)
                                                          : ("File #" + (index + 1))
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 10
                                                    color: "#475569"
                                                }
                                            }

                                            // View / Play button (z:2 to capture clicks above fileRowHover)
                                            Rectangle {
                                                id: listViewBtn
                                                objectName: "listFileViewBtn"
                                                Layout.preferredHeight: 28
                                                Layout.preferredWidth: viewBtnRow.implicitWidth + 18
                                                radius: 4
                                                Layout.alignment: Qt.AlignVCenter
                                                z: 2

                                                color: !listRowItem.isViewableItem
                                                       ? "#141A26"
                                                       : (viewBtnMouse.containsMouse ? "#1E4A72" : "#141A26")
                                                border.color: !listRowItem.isViewableItem
                                                              ? "#222B3D"
                                                              : (viewBtnMouse.containsMouse ? "#38BDF8" : "#2D3748")

                                                Behavior on color { ColorAnimation { duration: 100 } }
                                                Behavior on border.color { ColorAnimation { duration: 100 } }

                                                Row {
                                                    id: viewBtnRow
                                                    anchors.centerIn: parent
                                                    spacing: 4
                                                    Text {
                                                        text: (listRowItem.isVideoItem || listRowItem.isAudioItem) ? "▶"
                                                              : (listRowItem.isViewableItem ? "🔍" : "📦")
                                                        font.pixelSize: 10
                                                        anchors.verticalCenter: parent.verticalCenter
                                                    }
                                                    Text {
                                                        text: (listRowItem.isVideoItem || listRowItem.isAudioItem) ? "Play"
                                                              : (listRowItem.isViewableItem ? "View" : "Archive")
                                                        font.family: "Segoe UI, sans-serif"
                                                        font.pixelSize: 10
                                                        font.weight: 600
                                                        color: !listRowItem.isViewableItem
                                                               ? "#64748B"
                                                               : (viewBtnMouse.containsMouse ? "#38BDF8"
                                                                  : ((listRowItem.isVideoItem || listRowItem.isAudioItem) ? "#38BDF8" : "#94A3B8"))
                                                        anchors.verticalCenter: parent.verticalCenter
                                                    }
                                                }

                                                MouseArea {
                                                    id: viewBtnMouse
                                                    objectName: "listFileViewMouse"
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: listRowItem.isViewableItem ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                    enabled: listRowItem.isViewableItem
                                                    // Consume click so it doesn't fall through to fileRowHover
                                                    onClicked: function(mouse) {
                                                        mouse.accepted = true
                                                        modalRoot.openLightbox(index)
                                                    }
                                                }
                                            }

                                            // Checkbox (z:2)
                                            Rectangle {
                                                width: 24
                                                height: 24
                                                radius: 5
                                                color: model.selected ? "#38BDF8" : "#1A2234"
                                                border.color: model.selected ? "#38BDF8" : "#334155"
                                                border.width: 1
                                                Layout.alignment: Qt.AlignVCenter
                                                z: 2

                                                scale: model.selected ? 1.0 : 0.88
                                                Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.35; mass: 1.0 } }
                                                Behavior on color { ColorAnimation { duration: 100 } }
                                                Behavior on border.color { ColorAnimation { duration: 100 } }

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: "✓"
                                                    font.pixelSize: 13
                                                    font.weight: Font.Bold
                                                    color: "#0A0E17"
                                                    visible: model.selected
                                                }

                                                MouseArea {
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: function(mouse) {
                                                        mouse.accepted = true
                                                        modalRoot.toggleFileItem(index, (mouse.modifiers & Qt.ShiftModifier) !== 0)
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

            } // ── end Main Content Area Item ──────────────────────────

            // ── Footer Row ───────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Comprehensive Selection Counter Pill (Files + Posts)
                Rectangle {
                    height: 30
                    implicitWidth: selCounterRow.implicitWidth + 20
                    radius: 6
                    color: "#161D2B"
                    border.color: "#2D3748"

                    Row {
                        id: selCounterRow
                        anchors.centerIn: parent
                        spacing: 6

                        Text {
                            text: modalRoot.tr("label_selected_counter", "Selected:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        // Files Count
                        Text {
                            text: modalRoot.totalSelectedFiles + " / " + modalRoot.totalFilesCount + " files"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: modalRoot.totalSelectedFiles > 0 ? "#38BDF8" : "#EF4444"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        // Divider
                        Text {
                            text: "•"
                            font.pixelSize: 10
                            color: "#475569"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        // Posts Count
                        Text {
                            text: modalRoot.selectedCount + " / " + modalRoot.allPosts.length + " posts"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                Text {
                    visible: !modalRoot.isInspecting || postFilesModel.count > 1
                    text: modalRoot.isInspecting
                        ? "Tip: Shift+click for range • Ctrl+click to preview/play"
                        : (modalRoot.quickSelectClickMode
                            ? "Tip: Click to select • Ctrl+click to preview/play • Shift+click for range"
                            : "Tip: Click to preview/play • Ctrl+click to select • Shift+click for range")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                }

                Item { Layout.fillWidth: true }

                // Cancel / Close Button
                Rectangle {
                    height: 34
                    implicitWidth: cancelText.implicitWidth + 20
                    radius: 7
                    color: cancelMouse.containsMouse ? "#1E293B" : "transparent"
                    border.color: cancelMouse.containsMouse ? "#334155" : "transparent"
                    scale: cancelMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Text {
                        id: cancelText
                        anchors.centerIn: parent
                        text: modalRoot.tr("btn_cancel", "Cancel")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#94A3B8"
                    }

                    MouseArea {
                        id: cancelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.closeModal()
                    }
                }

                // Add to Queue Selected Button
                Rectangle {
                    height: 34
                    implicitWidth: queueSelRow.implicitWidth + 24
                    radius: 7
                    color: queueSelMouse.containsMouse ? "#1E293B" : "#141A26"
                    border.color: "#2D3748"
                    border.width: 1
                    scale: queueSelMouse.pressed ? 0.94 : (queueSelMouse.containsMouse ? 1.02 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: queueSelRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "➕"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: modalRoot.tr("btn_queue_selected", "Queue Selected") + " (" + modalRoot.totalSelectedFiles + " files)"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: "#E2E8F0"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: queueSelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: modalRoot.totalSelectedFiles > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                        enabled: modalRoot.totalSelectedFiles > 0
                        opacity: modalRoot.totalSelectedFiles > 0 ? 1.0 : 0.5
                        onClicked: {
                            var ids = modalRoot.getSelectedPostIds()
                            var filesMap = modalRoot.getSelectedFilesMap()
                            if (modalRoot.bridge) {
                                modalRoot.bridge.startDownloadSelectedPosts(ids, false, filesMap)
                            }
                            modalRoot.closeModal()
                        }
                    }
                }

                // Download Selected Button
                Rectangle {
                    height: 34
                    implicitWidth: dlSelRow.implicitWidth + 28
                    radius: 7
                    color: dlSelMouse.containsMouse ? "#0284C7" : "#0369A1"
                    border.color: "#38BDF8"
                    border.width: 1
                    scale: dlSelMouse.pressed ? 0.94 : (dlSelMouse.containsMouse ? 1.03 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: dlSelRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "⚡"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: modalRoot.tr("btn_download_selected", "Download Selected") + " (" + modalRoot.totalSelectedFiles + " files)"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: dlSelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: modalRoot.totalSelectedFiles > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                        enabled: modalRoot.totalSelectedFiles > 0
                        opacity: modalRoot.totalSelectedFiles > 0 ? 1.0 : 0.5
                        onClicked: {
                            var ids = modalRoot.getSelectedPostIds()
                            var filesMap = modalRoot.getSelectedFilesMap()
                            if (modalRoot.bridge) {
                                modalRoot.bridge.startDownloadSelectedPosts(ids, true, filesMap)
                            }
                            modalRoot.closeModal()
                        }
                    }
                }
            }
        }
    }

    // ── Fullscreen Media Lightbox Modal (Images, GIFs, Video, Audio) ─────
    MediaLightboxModal {
        id: selectionLightbox
        anchors.fill: parent
        z: 10000
        bridge: modalRoot.bridge
        browserBridge: modalRoot.browserBridge
        hideExternalActions: true
        selectionMode: true
        currentItemSelected: (modalRoot._selectionTick >= 0 && modalRoot.lightboxIndex >= 0 && modalRoot.lightboxIndex < postFilesModel.count)
            ? !!postFilesModel.get(modalRoot.lightboxIndex).selected
            : false
        onSelectionToggled: {
            if (modalRoot.lightboxIndex >= 0) {
                modalRoot.toggleFileItem(modalRoot.lightboxIndex, false)
            }
        }
    }
}
