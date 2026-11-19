import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import QtMultimedia
import "../components"
import "gallery"
import "gallery/GalleryHelpers.js" as H
import "gallery/GalleryActions.js" as A

Item {
    id: root
    property var bridge: null
    readonly property var archiver: (typeof galleryArchiveBridge !== "undefined") ? galleryArchiveBridge : null
    readonly property var tools: (typeof galleryTools !== "undefined") ? galleryTools : null

    // Search in subfolders
    property bool searchSubfolders: true
    property var searchResults: []
    property int searchToken: -1
    property bool searchRunning: false
    property int searchScanned: 0
    readonly property bool recursiveActive: searchSubfolders && !!tools && (searchFilter || "").trim().length >= 2
    function isRecursiveSearch() { return root.searchSubfolders && !!root.tools && (root.searchFilter || "").trim().length >= 2 }

    // Toast & animation state
    property bool toastCanUndo: false
    property bool toastShown: false
    property string toastText: ""
    property bool toastIsError: false
    property bool animatePopulate: true
    function quietly(fn) {
        root.animatePopulate = false
        fn()
        Qt.callLater(function() { root.animatePopulate = true })
    }

    // History, favourites, ratings & character tagging state
    property var backStack: []
    property var forwardStack: []
    readonly property string favoritesPath: "::favorites"
    readonly property bool inFavorites: currentPath === favoritesPath
    property var marks: ({})
    property int favoritesMissing: 0
    property var charTags: ({})
    property int tagsToken: -1
    property bool tagging: false
    property int taggingCurrent: 0
    property int taggingTotal: 0
    property real taggingProgress: taggingTotal > 0 ? (taggingCurrent / taggingTotal) : 0.0
    property string characterFilter: ""

    // Virtual Sort Bucket Filter
    property string virtualBucketName: ""
    property var virtualBucketPaths: ({})
    function setVirtualBucketFilter(bucketName, pathsList) { A.setVirtualBucketFilter(root, bucketName, pathsList) }
    function clearVirtualBucketFilter() { root.setVirtualBucketFilter("", []) }

    // Modal entry points
    function modal(loader) { if (!loader.active) loader.active = true; return loader.item }
    function isModalOpen(loader) { return !!(loader && loader.item && loader.item.isOpen) }
    function openVisualSorter() { var m = modal(modalHost.visualSorterLoader); if (m) m.open(root.currentPath); return m }
    function openBatchRename() { modal(modalHost.batchRenameLoader).open(root.currentPath, root.filteredItems) }
    function openGalleryCleaner() { modal(modalHost.galleryCleanerLoader).open(root.currentPath) }
    function openArchiveViewer(item) { modal(modalHost.archiveViewerLoader).open(item) }
    function openLightbox(item) { modal(modalHost.lightboxLoader).open(item, getAllMediaItems()) }
    function openStorage() { if (root.tools && !root.inFavorites && root.currentPath) modal(modalHost.storageLoader).open(root.currentPath) }
    function checkForNewPosts() { if (root.updates && !root.inFavorites) modal(modalHost.creatorUpdatesLoader).open(root.currentPath, root.creatorInfo) }

    // Group by post
    property bool groupByPost: false
    property string openGroupKey: ""
    property string openGroupTitle: ""

    function tr(key, fallback) {
        if (typeof appWindow !== "undefined") return appWindow.tr(key, fallback)
        return fallback !== undefined ? fallback : key
    }

    // Reactive Explorer State
    property string currentPath: ""
    property var rawItems: []
    property var filteredItems: []
    property var sortedItems: []
    property var breadcrumbs: []
    property var drives: []
    property var bookmarks: []
    property string activeCategory: "all"
    property string searchFilter: ""
    property string viewMode: "grid"
    property bool pathEditMode: false
    property bool isLoading: false
    property int _dirReqSeq: 0
    property string _pendingDirReqId: ""
    property var _pendingDirCtx: null

    // View preferences (persisted)
    property string sortKey: "name"
    property bool sortAscending: true
    property int thumbSize: 168
    property bool showPathBar: true
    property bool showShortcutsBar: true
    property bool showFolderPreviews: true
    property string thumbFitMode: "fit"
    property string thumbAspect: "square"
    property bool cleanThumbCards: false
    readonly property int resolvedImageFillMode: root.thumbFitMode === "fit" ? Image.PreserveAspectFit : Image.PreserveAspectCrop
    readonly property int resolvedVideoFillMode: root.thumbFitMode === "fit" ? VideoOutput.PreserveAspectFit : VideoOutput.PreserveAspectCrop
    readonly property real thumbAspectRatio: root.thumbAspect === "portrait" ? 1.33 : (root.thumbAspect === "square" ? 1.0 : 0.62)
    property bool privacyBlur: false
    property bool privacyHintSeen: false
    property bool groupByDate: false
    property int shownItemCount: 0
    property string savedSearchesJson: "[]"
    readonly property var savedSearches: { try { return JSON.parse(root.savedSearchesJson) || [] } catch (e) { return [] } }
    property var pendingSearch: null
    readonly property int listingCap: 20000

    readonly property var updates: (typeof galleryUpdates !== "undefined") ? galleryUpdates : null
    property var creatorInfo: ({ found: false, maybe: false })
    Connections {
        target: root.updates
        function onCreatorFolderReady(folder, info) { if (folder === root.currentPath) root.creatorInfo = info }
    }

    // Responsive layout metrics
    GalleryLayoutMetrics { id: metrics; view: root }
    readonly property bool compact: metrics.compact
    readonly property bool veryCompact: metrics.veryCompact
    readonly property bool showTypeColumn: metrics.showTypeColumn
    readonly property bool showActionLabels: metrics.showActionLabels
    readonly property bool showDriveLabels: metrics.showDriveLabels
    readonly property bool showZoomSlider: metrics.showZoomSlider
    readonly property bool showPillLabels: metrics.showPillLabels
    readonly property bool showSortLabel: metrics.showSortLabel
    readonly property int searchBoxWidth: metrics.searchBoxWidth
    readonly property bool selectionHasArchive: metrics.selectionHasArchive
    readonly property bool showChipLabels: metrics.showChipLabels
    readonly property bool showSelLinks: metrics.showSelLinks
    readonly property bool showSelectedWord: metrics.showSelectedWord
    readonly property bool showSelSize: metrics.showSelSize

    // Selection, listing & counts
    property int listingTotal: 0
    property var selectedPaths: ({})
    property int selectionCount: 0
    property int selectionAnchor: -1
    property var contextItems: []
    property int folderCount: 0
    property int fileCount: 0
    property real currentFolderFilesSize: 0
    property int imageCount: 0
    property int videoCount: 0
    property int archiveCount: 0
    property int audioCount: 0
    property int otherCount: 0

    // Child component bridges
    readonly property var explorerListView: listContainer.listView
    readonly property var searchInput: filterToolbar.searchInput
    readonly property var archiveModal: modalHost.archiveModal
    readonly property var mediaCompressLoader: modalHost.mediaCompressLoader
    readonly property var rootDiskSafetyLoader: modalHost.rootDiskSafetyLoader
    readonly property bool viewMenuVisible: menus.viewMenu.visible
    readonly property bool sortMenuVisible: menus.sortMenu.visible
    readonly property bool charMenuVisible: menus.charMenu.visible
    function openViewMenu(anchorItem) { menus.openViewMenu(anchorItem) }
    function openSortMenu(anchorItem) { menus.openSortMenu(anchorItem) }
    function openMoreMenu(anchorItem) { menus.openMoreMenu(anchorItem) }
    function openCharMenu(anchorItem) { menus.openCharMenu(anchorItem) }

    readonly property bool _textInputFocused: (
        (filterToolbar && filterToolbar.searchInput && filterToolbar.searchInput.activeFocus)
        || (dialogs && dialogs.renameField && dialogs.renameField.activeFocus)
        || (typeof appWindow !== "undefined" && appWindow && appWindow.activeFocusItem && typeof appWindow.activeFocusItem.selectAll === "function")
    )
    readonly property bool shortcutsEnabled: (typeof appWindow !== "undefined" ? appWindow.currentTab === 7 : root.visible)
        && !_textInputFocused && !modalHost.anyModalOpen
        && !dialogs.deleteConfirm.isOpen && !dialogs.renameDialog.isOpen && !menus.anyMenuOpen
    readonly property bool markShortcutsEnabled: shortcutsEnabled && !!root.tools

    Settings {
        category: "gallery"
        property alias sortKey: root.sortKey
        property alias sortAscending: root.sortAscending
        property alias thumbSize: root.thumbSize
        property alias showPathBar: root.showPathBar
        property alias showShortcutsBar: root.showShortcutsBar
        property alias showFolderPreviews: root.showFolderPreviews
        property alias thumbFitMode: root.thumbFitMode
        property alias thumbAspect: root.thumbAspect
        property alias cleanThumbCards: root.cleanThumbCards
        property alias privacyBlur: root.privacyBlur
        property alias privacyHintSeen: root.privacyHintSeen
        property alias groupByDate: root.groupByDate
        property alias savedSearchesJson: root.savedSearchesJson
        property alias groupByPost: root.groupByPost
    }

    function setThumbSize(v) { root.thumbSize = Math.max(120, Math.min(320, Math.round(v / 8) * 8)) }
    readonly property var activeView: root.viewMode === "grid" ? explorerGridView : explorerListView
    function focusBrowser() { if (root.activeView) root.activeView.forceActiveFocus() }

    // Wheel & keyboard navigation
    property real _lastWheelMs: 0
    property int _wheelStreak: 0
    property bool keyboardNav: false
    property string _typeBuffer: ""
    property real _typeLastMs: 0
    readonly property int typeAheadResetMs: 1000
    function _typeAheadActive() { return root._typeBuffer.length > 0 && Date.now() - root._typeLastMs < root.typeAheadResetMs }
    function scrollTo(view, anim, y) { H.scrollTo(view, anim, y) }
    function wheelScroll(view, anim, event, rowH, rowsPerNotch) { H.wheelScroll(root, view, anim, event, rowH, rowsPerNotch) }
    function handleBrowserKey(view, event) { H.handleBrowserKey(root, view, event, explorerGridView, explorerGridView.scrollAnim, listContainer.scrollAnim) }

    // Path safety & bookmark / disk telemetry
    property var currentPathSafety: (root.bridge && root.bridge.getPathSafetyInfo && root.currentPath !== "::favorites") ? root.bridge.getPathSafetyInfo(root.currentPath) : null
    readonly property bool isCurrentPathBlocked: currentPathSafety ? currentPathSafety.is_blocked : false
    readonly property bool isCurrentPathOtherRoot: currentPathSafety ? currentPathSafety.is_other_root : false
    function requestSafeAction(actionName, actionCallback) { A.requestSafeAction(root, actionName, actionCallback) }

    readonly property bool isCurrentFolderBookmarked: {
        if (!root.currentPath || !root.bookmarks) return false
        var cp = (root.currentPath || "").toUpperCase().replace(/\\/g, "/").replace(/\/+$/, "")
        for (var i = 0; i < root.bookmarks.length; i++) {
            var bp = (root.bookmarks[i].path || "").toUpperCase().replace(/\\/g, "/").replace(/\/+$/, "")
            if (bp === cp) return true
        }
        return false
    }
    readonly property var currentDisk: {
        if (!root.currentPath || !root.drives) return null
        var cp = root.currentPath.toUpperCase().replace(/\\/g, "/")
        for (var i = 0; i < root.drives.length; i++) {
            var d = root.drives[i]
            if (!d) continue
            var dp = (d.path || "").toUpperCase().replace(/\\/g, "/")
            var dn = (d.name || "").toUpperCase().replace(/\\/g, "/")
            if (dp && cp.indexOf(dp) === 0) return d
            if (dn && cp.indexOf(dn) === 0) return d
        }
        return root.drives.length > 0 ? root.drives[0] : null
    }

    // Pure helper delegates
    readonly property var imageExts: H.IMAGE_EXTS
    readonly property var videoExts: H.VIDEO_EXTS
    readonly property var audioExts: H.AUDIO_EXTS
    readonly property var archiveExtensions: H.ARCHIVE_EXTS
    function formatBytes(b) { return H.formatBytes(b) }
    function formatDate(ts) { return H.formatDate(ts) }
    function getCategory(ext) { return H.getCategory(ext) }
    function getItemIcon(item) { return H.getItemIcon(item) }
    function getItemColor(item) { return H.getItemColor(item) }
    function formatFolderSize(item) { return H.formatFolderSize(item) }
    function formatFolderSubtitle(item) { return H.formatFolderSubtitle(item) }
    function withFolderStats(item, st, pv) { return H.withFolderStats(item, st, pv) }
    function _samePlace(a, b) { return H.samePlace(a, b) }
    function markKey(path) { return H.markKey(path, Qt.platform.os === "windows") }
    function starText(n) { return H.starText(n) }
    function sortLabel(key) { return H.sortLabel(key) }
    function displayDir(d) { return H.displayDir(d) }
    function thumbUrl(item) { return H.thumbUrl(item) }
    function isSpacer(it) { return H.isSpacer(it) }
    function totalSize(items) { return H.totalSize(items) }
    function isMedia(item) { return H.isMedia(item) }
    function _pathsOf(items) { return H.pathsOf(items) }
    function urlToPath(u) { return H.urlToPath(u, Qt.platform.os === "windows") }
    function isArchive(item) { return H.isArchive(item) }
    function archivesIn(items) { return H.archivesIn(items) }
    function characterCounts() { return H.characterCounts(root.sortedItems, root.charTags) }

    // Background folder stats, bookmarks & bridge signals
    property var folderStats: ({})
    property var folderPreviews: ({})
    property int statsRev: 0
    Timer { id: statsFlushTimer; interval: 120; onTriggered: root.statsRev++ }
    Timer { id: statsResortTimer; interval: 700; onTriggered: root.resortInPlace() }
    Timer { id: liveRefreshTimer; interval: 700; onTriggered: root.liveRefresh() }
    Timer { id: toastTimer; interval: 8000; onTriggered: { root.toastShown = false; root.toastCanUndo = false } }
    Timer {
        id: searchDebounce
        interval: 350
        onTriggered: {
            if (!root.isRecursiveSearch()) return
            root.searchResults = []
            root.searchScanned = 0
            root.searchRunning = true
            root.searchToken = root.tools.startSearch(root.currentPath, root.searchFilter.trim(), 5000)
            resort()
        }
    }

    Connections {
        target: root.bridge
        ignoreUnknownSignals: true
        function onFolderStatsCalculated(path, size, fc, dc) { A.updateFolderStats(root, path, size, fc, dc, statsFlushTimer, statsResortTimer) }
        function onFolderPreviewsCalculated(path, previews) { A.updateFolderPreviews(root, path, previews, statsFlushTimer) }
        function onGalleryBookmarksChanged() { root.refreshBookmarks() }
        function onDrivesUpdated(list) { root.drives = list }
        function onGalleryShowRequested(path, isDir) {
            if (typeof appWindow !== "undefined") appWindow.currentTab = 7
            if (isDir) root.navigateTo(path)
            else root.revealInGallery(path)
        }
        function onAsyncResultReady(requestId, res) { A.handleAsyncResult(root, requestId, res, explorerGridView, explorerListView) }
    }

    Connections {
        target: root.tools
        function onMoveFinished(tag, res) { if (tag === "gallery") root.showMoveResult(res, root._moveDest, root._movePrep) }
        function onUndoFinished(res) { showToast(res.message, !res.success); refreshPreservingScroll() }
        function onWatchedFolderChanged(path) { if (root._samePlace(path, root.currentPath)) liveRefreshTimer.restart() }
        function onMarksChanged() {
            root.reloadMarks()
            if (root.inFavorites) root.refreshPreservingScroll()
            else if (root.sortKey === "rating") root.resort()
        }
        function onTagsProgress(token, current, total) { if (token === root.tagsToken) { root.taggingCurrent = current; root.taggingTotal = total } }
        function onTagsCancelled(token, map) { A.handleTagsCancelled(root, menus, token, map) }
        function onTagsReady(token, map) { A.handleTagsReady(root, menus, token, map) }
        function onSearchBatch(token, items, done, scanned) {
            if (token !== root.searchToken) return
            if (items.length) root.searchResults = root.searchResults.concat(items)
            root.searchScanned = scanned
            root.searchRunning = !done
            root.quietly(root.resort)
        }
    }

    function refreshBookmarks() {
        Qt.callLater(function() { if (root.bridge && root.bridge.getGalleryBookmarks) root.bookmarks = root.bridge.getGalleryBookmarks() })
    }
    function resortInPlace() { A.resortInPlace(root, explorerGridView, explorerListView) }
    function getAllMediaItems() {
        var media = [], list = root.filteredItems || []
        for (var i = 0; i < list.length; i++) if (!list[i].is_dir && H.isMedia(list[i])) media.push(list[i])
        return media
    }

    // Navigation & sorting
    function navigateTo(path) {
        if (!root.bridge) return
        var targetPath = path || (root.bridge.getDownloadDir ? root.bridge.getDownloadDir() : "")
        Qt.callLater(function() { root._doNavigateTo(targetPath, false) })
    }
    function _doNavigateTo(targetPath, fromHistory, preserveOpts) { A.doNavigateTo(root, targetPath, fromHistory, statsResortTimer, explorerGridView, explorerListView, preserveOpts) }
    function goBack() { A.goBack(root) }
    function goForward() { A.goForward(root) }
    function refreshPreservingScroll() { A.refreshPreservingScroll(root, explorerGridView, explorerListView) }
    function liveRefresh() { A.liveRefresh(root, explorerGridView, explorerListView) }
    function navigateUp() {
        if (!root.currentPath || root.breadcrumbs.length <= 1) return
        var parentCrumb = root.breadcrumbs[root.breadcrumbs.length - 2]
        if (parentCrumb && parentCrumb.path) navigateTo(parentCrumb.path)
    }
    function updateCounts(items) {
        var c = H.computeCounts(items)
        root.folderCount = c.folderCount; root.fileCount = c.fileCount; root.currentFolderFilesSize = c.currentFolderFilesSize
        root.imageCount = c.imageCount; root.videoCount = c.videoCount; root.archiveCount = c.archiveCount
        root.audioCount = c.audioCount; root.otherCount = c.otherCount
    }
    function resort() {
        var list = root.isRecursiveSearch() ? (root.searchResults || []) : (root.rawItems || [])
        updateCounts(list)
        root.sortedItems = H.sortItems(list, root.sortKey, root.sortAscending, root.ratingOf)
        applyFilter()
    }
    function sortBy(key) {
        if (root.sortKey === key) root.sortAscending = !root.sortAscending
        else { root.sortKey = key; root.sortAscending = !(key === "date" || key === "size" || key === "rating") }
        resort()
    }

    // Favourites, tagging, grouping, privacy & saved searches
    function reloadMarks() { root.marks = root.tools ? root.tools.allMarks() : ({}) }
    function isFavorite(item) { if (!item || item.is_group) return false; var m = root.marks[markKey(item.path)]; return !!m && m.fav }
    function ratingOf(item) { if (!item || item.is_group) return 0; var m = root.marks[markKey(item.path)]; return m ? (m.rating || 0) : 0 }
    function markTargets() { return A.markTargets(root) }
    function toggleFavorite(items) { A.toggleFavorite(root, items) }
    function setRating(items, n) { A.setRating(root, items, n) }
    function startTagging() { A.startTagging(root, H.postTitleFromName) }
    function cancelTagging() { A.cancelTagging(root) }
    function setCharacterFilter(name) { root.characterFilter = name; clearSelection(); applyFilter(); root.activeView.positionViewAtBeginning() }
    function openFavorites() { navigateTo(root.favoritesPath) }
    function workingFolder(items) { return A.workingFolder(root, items) }
    function openGroup(item) { root.openGroupKey = item.group_key; root.openGroupTitle = item.name; clearSelection(); root.activeView.currentIndex = -1; applyFilter(); root.activeView.positionViewAtBeginning(); focusBrowser() }
    function closeGroup() { if (!root.openGroupKey) return; root.openGroupKey = ""; root.openGroupTitle = ""; clearSelection(); applyFilter(); focusBrowser() }
    onGroupByPostChanged: { if (root.groupByPost) root.groupByDate = false; root.openGroupKey = ""; clearSelection(); applyFilter() }
    function togglePrivacy() { A.togglePrivacy(root, modalHost) }

    function savedSearchIndex(query, path) {
        var list = root.savedSearches
        for (var i = 0; i < list.length; i++) if (list[i].query === query && _samePlace(list[i].path, path)) return i
        return -1
    }
    readonly property bool currentSearchSaved: root.searchFilter.trim().length > 0 && savedSearchIndex(root.searchFilter.trim(), root.currentPath) >= 0
    function toggleSaveSearch() { A.toggleSaveSearch(root, H.folderName) }
    function removeSavedSearch(entry) { A.removeSavedSearch(root, entry) }
    function runSavedSearch(entry) { A.runSavedSearch(root, entry) }
    function isCurrentSavedSearch(entry) { return _samePlace(root.currentPath, entry.path) && root.searchFilter.trim() === entry.query }
    readonly property var shortcutChips: {
        var out = [], b = root.bookmarks || [], ss = root.savedSearches
        for (var i = 0; i < b.length; i++) out.push({ kind: "folder", name: b[i].name, path: b[i].path, icon: b[i].icon })
        for (var j = 0; j < ss.length; j++) out.push({ kind: "search", name: ss[j].name || ss[j].query, path: ss[j].path, query: ss[j].query, recursive: !!ss[j].recursive, icon: "🔎" })
        return out
    }

    readonly property int gridColumns: Math.max(1, Math.floor(explorerGridView.width / Math.max(1, root.thumbSize)))
    onGridColumnsChanged: if (root.groupByDate && root.viewMode === "grid") Qt.callLater(root.applyFilter)
    onViewModeChanged: if (root.groupByDate) Qt.callLater(root.applyFilter)
    onGroupByDateChanged: { if (root.groupByDate) root.groupByPost = false; root.openGroupKey = ""; clearSelection(); applyFilter() }
    function selectSection(header, index, mouse) { A.selectSection(root, header, index, mouse) }

    // Selection, click & file operations
    function _setSelection(sel) { root.selectedPaths = sel; root.selectionCount = Object.keys(sel).length }
    function clearSelection() { _setSelection({}); root.selectionAnchor = -1 }
    function selectOnly(path, index) { var sel = {}; sel[path] = true; _setSelection(sel); root.selectionAnchor = index }
    function toggleSelection(path) { A.toggleSelection(root, path) }
    function selectRange(fromIndex, toIndex, additive) { A.selectRange(root, fromIndex, toIndex, additive) }
    function selectAll() { A.selectAll(root) }
    function selectedItems() { return A.selectedItems(root) }
    function handleItemClick(item, index, mouse) { A.handleItemClick(root, item, index, mouse) }
    function handleItemDoubleClick(item) { openItem(item) }
    function openItem(item) { A.openItem(root, item, modalHost) }
    function showContextMenu(item, index, sourceItem, mx, my) { A.showContextMenu(root, menus, item, index, sourceItem, mx, my) }

    function showToast(text, isError, canUndo) {
        root.toastText = text; root.toastShown = true; root.toastIsError = !!isError
        root.toastCanUndo = !!canUndo && !!root.tools && root.tools.canUndo
        toastTimer.restart()
    }
    function undoLast() {
        if (!root.tools || !root.tools.canUndo) { showToast("Nothing to undo", false); return }
        if (root.tools.undoLastAsync) { root.tools.undoLastAsync(); return }
        var res = root.tools.undoLast(); showToast(res.message, !res.success); refreshPreservingScroll()
    }
    function copyPaths(items) {
        if (!root.bridge || !items.length) return
        root.bridge.copyToClipboard(_pathsOf(items).join("\n"))
        showToast(items.length === 1 ? "Copied path to clipboard" : ("Copied " + items.length + " paths to clipboard"), false)
    }

    property string pendingRevealPath: ""
    function revealInGallery(path) { A.revealInGallery(root, path) }
    function _applyPendingReveal() { A.applyPendingReveal(root, root.viewMode === "grid" ? GridView.Center : ListView.Center) }
    function revealItem(item) { if (root.bridge && root.bridge.revealFileInExplorer) root.bridge.revealFileInExplorer(item.path) }

    property string _moveDest: ""
    property string _movePrep: " to "
    function moveItemsToFolder(items) {
        if (!root.bridge || !items.length) return
        root.requestSafeAction("Move", function() {
            var dest = root.bridge.browseFolderDialog("Move " + items.length + (items.length === 1 ? " item" : " items") + " to…", root.workingFolder(items))
            if (dest) root.startMove(_pathsOf(items), dest, " to ")
        })
    }
    function startMove(paths, dest, prep) {
        if (root.tools && root.tools.moveItemsAsync) {
            root._moveDest = dest; root._movePrep = prep
            showToast("Moving " + paths.length + (paths.length === 1 ? " item" : " items") + "…", false)
            root.tools.moveItemsAsync(paths, dest, "gallery")
        } else {
            root.showMoveResult(root.bridge.moveItems(paths, dest), dest, prep)
        }
    }
    function showMoveResult(res, dest, prep) {
        if (res.failed > 0) showToast("Moved " + res.moved + ", " + res.failed + " failed: " + (res.errors.length ? res.errors[0] : ""), true, res.moved > 0)
        else showToast("Moved " + res.moved + (res.moved === 1 ? " item" : " items") + prep + dest, false, true)
        refreshPreservingScroll()
    }
    function copyItemsToFolder(items) {
        if (!root.bridge || !items.length || !root.archiver || jobBusy()) return
        root.requestSafeAction("Copy", function() {
            var dest = root.bridge.browseFolderDialog("Copy " + items.length + (items.length === 1 ? " item" : " items") + " to…", root.workingFolder(items))
            if (!dest) return
            var err = modalHost.archiveModal.startCopy(_pathsOf(items), dest)
            if (err) showToast(err, true)
        })
    }
    function newFolder() { if (root.tools && root.currentPath && !root.inFavorites) root.requestSafeAction("New folder", function() { dialogs.renameDialog.showCreate() }) }
    function renameItem(item) { if (item) root.requestSafeAction("Rename", function() { dialogs.renameDialog.show(item) }) }
    function deleteItems(items) { if (items.length) root.requestSafeAction("Delete", function() { dialogs.deleteConfirm.show(items) }) }

    // Drag and drop
    property bool internalDragActive: false
    property var dragPaths: []
    function _urlFor(path) { return (root.bridge && root.bridge.pathToUrl) ? root.bridge.pathToUrl(path) : ("file:///" + path.replace(/\\/g, "/")) }
    function dragItemsFor(item) { return root.selectedPaths[item.path] === true ? selectedItems() : (item.is_group ? item.members : [item]) }
    function mimeForItems(items) {
        var urls = []; for (var i = 0; i < items.length; i++) urls.push(_urlFor(items[i].path))
        return { "text/uri-list": urls.join("\r\n") }
    }
    readonly property var selectionMime: selectionCount > 0 ? mimeForItems(selectedItems()) : ({})
    function dragImageFor(item) {
        var preview = item.is_group ? item.cover : item
        if (!preview) return ""
        var cat = getCategory(preview.ext)
        return (cat === "image" || cat === "video") ? thumbUrl(preview) : ""
    }
    function beginDrag(item) { root.dragPaths = _pathsOf(dragItemsFor(item)); root.internalDragActive = true }
    function endDrag() { root.internalDragActive = false; root.dragPaths = [] }
    function handleDrop(drop, destDir) { A.handleDrop(root, modalHost, drop, destDir) }

    // Archives & Media Compression
    function jobBusy() {
        if (root.archiver && root.archiver.busy) { showToast("Another file job is still running; its progress is in the status bar", true); return true }
        return false
    }
    function compressItems(items) { if (items.length && root.archiver && !jobBusy()) root.requestSafeAction("Compress", function() { modalHost.archiveModal.openCompress(items, root.workingFolder(items)) }) }
    function compressibleOf(items) {
        var dzb = root.bridge ? root.bridge.decompressorBridge : null
        if (!dzb || !items || !items.length) return []
        return dzb.compressibleFiles(_pathsOf(items.filter(function(it) { return !it.is_dir })))
    }
    function compressMedia(paths) { if (paths && paths.length) root.requestSafeAction("Compress", function() { modal(modalHost.mediaCompressLoader).open(paths) }) }
    function mediaTr(key, fallback) {
        if (typeof Lang === "undefined" || !Lang) return fallback
        var _ = Lang.activeLanguage; var res = Lang.t(key)
        return (res && res !== key) ? res : fallback
    }
    function extractItems(items, quick) {
        var arcs = archivesIn(items)
        if (!arcs.length || !root.archiver || jobBusy()) return
        root.requestSafeAction("Extract", function() {
            if (quick) modalHost.archiveModal.quickExtract(arcs, root.workingFolder(arcs))
            else modalHost.archiveModal.openExtract(arcs, root.workingFolder(arcs))
        })
    }

    function applyFilter() {
        var res = H.filterAndGroupItems(root.sortedItems, {
            activeCategory: root.activeCategory, searchFilter: root.searchFilter,
            characterFilter: root.characterFilter, charTags: root.charTags,
            virtualBucketName: root.virtualBucketName, virtualBucketPaths: root.virtualBucketPaths,
            recursive: root.isRecursiveSearch(), openGroupKey: root.openGroupKey,
            groupByPost: root.groupByPost, groupByDate: root.groupByDate,
            sortKey: root.sortKey, sortAscending: root.sortAscending,
            isGrid: root.viewMode === "grid", gridColumns: root.gridColumns
        })
        root.shownItemCount = res.shown
        root.filteredItems = res.filtered
    }

    onActiveCategoryChanged: { clearSelection(); applyFilter() }
    onSearchFilterChanged: { clearSelection(); restartSubfolderSearch() }
    onSearchSubfoldersChanged: { clearSelection(); restartSubfolderSearch() }

    function restartSubfolderSearch() {
        if (root.isRecursiveSearch()) {
            searchDebounce.restart()
        } else {
            searchDebounce.stop()
            if (root.tools && root.searchRunning) root.tools.cancelSearch()
            root.searchRunning = false; root.searchResults = []; root.searchToken = -1
        }
        resort()
    }

    MouseArea {
        anchors.fill: parent
        z: -1
        acceptedButtons: Qt.BackButton | Qt.ForwardButton
        onClicked: (mouse) => { if (mouse.button === Qt.BackButton) root.goBack(); else root.goForward() }
    }

    GalleryShortcuts { view: root }

    Component.onCompleted: {
        reloadMarks()
        navigateTo("")
    }

    // Main UI Layout
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        GalleryTopToolbar { view: root }
        GalleryPathAndShortcutsBar { view: root }
        GalleryFilterToolbar { id: filterToolbar; view: root }
        GalleryContextBanners { view: root }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 8
            color: "#0D1018"
            border.color: "#1E2536"
            border.width: 1
            clip: true

            DropArea {
                id: browserDrop
                anchors.fill: parent
                keys: ["text/uri-list"]
                enabled: !root.recursiveActive && !root.openGroupKey && !root.inFavorites
                onDropped: (drop) => root.handleDrop(drop, root.currentPath)
            }
            Rectangle {
                anchors.fill: parent
                radius: 8
                color: "transparent"
                border.color: "#34D399"
                border.width: 2
                visible: browserDrop.containsDrag && !root.internalDragActive
                z: 5
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottomMargin: 12
                    width: dropHint.implicitWidth + 24
                    height: 26
                    radius: 13
                    color: "#0F2A22"
                    border.color: "#34D399"
                    Text { id: dropHint; anchors.centerIn: parent; text: "Drop to copy into this folder"; font.pixelSize: 11; font.weight: 600; color: "#A7F3D0" }
                }
            }

            Item {
                anchors.centerIn: parent
                visible: root.filteredItems.length === 0
                ColumnLayout {
                    spacing: 8
                    anchors.centerIn: parent
                    Text { text: "📭"; font.pixelSize: 32; Layout.alignment: Qt.AlignHCenter }
                    Text {
                        text: root.inFavorites && root.searchFilter.length === 0 ? "No favourites yet: star files with Ctrl+D or the right-click menu"
                              : (root.recursiveActive ? (root.searchRunning ? "Searching subfolders…" : "Nothing in this folder or its subfolders matches") : (root.searchFilter.length > 0 ? "No files match your filter" : "This folder is empty"))
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 13
                        font.weight: 600
                        color: "#64748B"
                        Layout.alignment: Qt.AlignHCenter
                    }
                }
            }

            GalleryGridView { id: explorerGridView; view: root }
            GalleryListView { id: listContainer; view: root }
        }

        GalleryStatusBar { view: root }
    }

    GalleryDialogs { id: dialogs; view: root }
    GalleryModalHost { id: modalHost; view: root }
    GalleryMenus { id: menus; view: root }
}
