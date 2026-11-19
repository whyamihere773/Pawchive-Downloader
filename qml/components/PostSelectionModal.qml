import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import "../components"
import "ScrollPhysics.js" as ScrollPhysics
import "post_selection"

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
        headerBar.setSearchText(restoredFilter)
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

            PostSelectionHeaderBar {
                id: headerBar
                modal: modalRoot
                filesModel: postFilesModel
            }

            // ── Main Content Area (Swap between Grid and Inspector View) ──
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                PostSelectionGridPanel {
                    modal: modalRoot
                    postsModel: postsModel
                }

                PostSelectionInspectorPanel {
                    modal: modalRoot
                    filesModel: postFilesModel
                }
            } // ── end Main Content Area Item ──────────────────────────


            PostSelectionFooterBar {
                modal: modalRoot
                filesModel: postFilesModel
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
