.pragma library

function setVirtualBucketFilter(root, bucketName, pathsList) {
    if (!bucketName || !pathsList || !pathsList.length) {
        root.virtualBucketName = ""
        root.virtualBucketPaths = ({})
        root.clearSelection()
        root.applyFilter()
        return
    }
    var map = {}
    for (var i = 0; i < pathsList.length; i++) {
        var norm = String(pathsList[i] || "").replace(/\\/g, "/").toLowerCase()
        if (norm) map[norm] = true
    }
    root.virtualBucketName = bucketName
    root.virtualBucketPaths = map
    root.clearSelection()
    root.applyFilter()
}

function requestSafeAction(root, actionName, actionCallback) {
    if (root.inFavorites) {
        if (actionName === "Batch Rename" || actionName === "Clean & Organize") {
            root.showToast(actionName + " works on a folder: open one first", true)
            return
        }
        actionCallback()
        return
    }
    if (!root.bridge || !root.bridge.getPathSafetyInfo) {
        actionCallback()
        return
    }
    var safety = root.bridge.getPathSafetyInfo(root.currentPath)
    if (safety && safety.is_blocked) {
        root.modal(root.rootDiskSafetyLoader).showBlocked(actionName, safety.drive_letter, safety.path, safety.message)
        return
    }
    if (safety && safety.is_other_root) {
        root.modal(root.rootDiskSafetyLoader).showRootWarning(actionName, safety.drive_letter, safety.path, actionCallback)
        return
    }
    actionCallback()
}

function updateFolderPreviews(root, path, previews, statsFlushTimer) {
    var pv = previews ? Array.prototype.slice.call(previews) : []
    var raw = root.rawItems || []
    for (var i = 0; i < raw.length; i++) {
        if (raw[i].path === path) {
            raw[i].previews = pv
            root.folderPreviews[path] = pv
            statsFlushTimer.start()
            return
        }
    }
}

function updateFolderStats(root, path, size, fileCount, folderCount, statsFlushTimer, statsResortTimer) {
    var raw = root.rawItems || []
    for (var i = 0; i < raw.length; i++) {
        if (raw[i].path === path) {
            raw[i].size = size
            raw[i].file_count = fileCount
            raw[i].folder_count = folderCount
            root.folderStats[path] = { size: size, file_count: fileCount, folder_count: folderCount }
            statsFlushTimer.start()
            if (root.sortKey === "size") statsResortTimer.start()
            return
        }
    }
}

function resortInPlace(root, gridView, listView) {
    var gridY = gridView.contentY
    var listY = listView.contentY
    root.quietly(root.resort)
    Qt.callLater(function() {
        gridView.contentY = Math.min(gridY, Math.max(0, gridView.contentHeight - gridView.height))
        listView.contentY = Math.min(listY, Math.max(0, listView.contentHeight - listView.height))
    })
}

function goBack(root) {
    if (!root.backStack.length) return
    var b = root.backStack.slice()
    var target = b.pop()
    root.backStack = b
    root.forwardStack = root.forwardStack.concat([root.currentPath])
    root._doNavigateTo(target, true)
}

function goForward(root) {
    if (!root.forwardStack.length) return
    var f = root.forwardStack.slice()
    var target = f.pop()
    root.forwardStack = f
    root.backStack = root.backStack.concat([root.currentPath])
    root._doNavigateTo(target, true)
}

function markTargets(root) {
    var items = root.selectedItems()
    if (!items.length && root.activeView.currentIndex >= 0 && root.keyboardNav) {
        var cur = root.filteredItems[root.activeView.currentIndex]
        if (cur) items = cur.is_group ? cur.members : [cur]
    }
    return items
}

function toggleFavorite(root, items) {
    if (!root.tools || !items.length) return
    var allFav = true
    for (var i = 0; i < items.length; i++) if (!root.isFavorite(items[i])) { allFav = false; break }
    root.tools.setFavorite(root._pathsOf(items), !allFav)
    root.showToast((allFav ? "Removed from" : "Added to") + " favourites" + (items.length > 1 ? " (" + items.length + " items)" : ""), false)
}

function setRating(root, items, n) {
    if (!root.tools || !items.length) return
    root.tools.setRating(root._pathsOf(items), n)
    root.showToast(n > 0 ? ("Rated " + root.starText(n)) : "Rating cleared", false)
}

function startTagging(root, postTitleFromNameFn) {
    if (!root.tools) return
    var list = root.sortedItems || []
    var work = []
    for (var i = 0; i < list.length; i++) {
        var it = list[i]
        if (it.is_dir || root.charTags[it.path] !== undefined) continue
        work.push({ path: it.path, title: postTitleFromNameFn(it.name) })
    }
    if (!work.length) return
    root.tagging = true
    root.taggingCurrent = 0
    root.taggingTotal = work.length
    root.tagsToken = root.tools.tagItems(work)
}

function cancelTagging(root) {
    if (!root.tools) return
    root.tools.cancelTagging()
    root.tagging = false
    root.taggingCurrent = 0
    root.taggingTotal = 0
    root.showToast("Character scanning stopped • AI model unloaded from VRAM", false)
}

function workingFolder(root, items) {
    if (!root.inFavorites) return root.currentPath
    var first = (items && items.length) ? items[0] : null
    if (!first) return root.bridge && root.bridge.getDownloadDir ? root.bridge.getDownloadDir() : ""
    var p = first.path
    return p.substring(0, Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/")))
}

function _applyNavListing(root, targetPath, items, total, preserveOpts, gridView, listView) {
    root.listingTotal = total
    root.rawItems = items
    root.updateCounts(items)
    if (preserveOpts && preserveOpts.quiet) {
        root.quietly(root.resort)
    } else {
        root.resort()
    }
    root.isLoading = false
    if (preserveOpts && preserveOpts.preserveScroll) {
        var gridY = preserveOpts.gridY || 0
        var listY = preserveOpts.listY || 0
        Qt.callLater(function() {
            gridView.contentY = Math.min(gridY, Math.max(0, gridView.contentHeight - gridView.height))
            listView.contentY = Math.min(listY, Math.max(0, listView.contentHeight - listView.height))
        })
    } else {
        Qt.callLater(root.focusBrowser)
        Qt.callLater(root._applyPendingReveal)
    }
    if (root.charMenuVisible) {
        root.startTagging()
    }
    if (root.pendingSearch && root._samePlace(root.pendingSearch.path, targetPath)) {
        var ps = root.pendingSearch
        root.pendingSearch = null
        root.searchSubfolders = !!ps.recursive
        root.searchInput.text = ps.query
    }
}

function _applyLiveListing(root, targetPath, items, total, gridY, listY, gridView, listView) {
    if (!root._samePlace(root.currentPath, targetPath) || root.inFavorites) return
    root.listingTotal = total
    root.rawItems = items
    var exists = {}
    for (var i = 0; i < items.length; i++) exists[items[i].path] = true
    var sel = {}
    for (var k in root.selectedPaths) if (exists[k] || k.indexOf("post:") === 0) sel[k] = true
    root._setSelection(sel)
    root.quietly(root.resort)
    if (root.characterFilter || root.charMenuVisible) root.startTagging()
    Qt.callLater(function() {
        gridView.contentY = Math.min(gridY, Math.max(0, gridView.contentHeight - gridView.height))
        listView.contentY = Math.min(listY, Math.max(0, listView.contentHeight - listView.height))
    })
}

function doNavigateTo(root, targetPath, fromHistory, statsResortTimer, gridView, listView, preserveOpts) {
    if (!root.bridge) return
    if (!fromHistory && root.currentPath && !root._samePlace(root.currentPath, targetPath)) {
        root.backStack = root.backStack.concat([root.currentPath]).slice(-50)
        root.forwardStack = []
    }
    root._pendingDirReqId = ""
    root._pendingDirCtx = null
    root.isLoading = true
    root.pathEditMode = false
    root.searchInput.text = ""
    root.searchFilter = ""
    root.openGroupKey = ""
    root.openGroupTitle = ""
    root.characterFilter = ""
    if (!fromHistory && !root._samePlace(root.currentPath, targetPath)) {
        root.virtualBucketName = ""
        root.virtualBucketPaths = ({})
    }
    root.charTags = ({})
    root.folderStats = ({})
    root.folderPreviews = ({})
    statsResortTimer.stop()
    if (root.tagging) root.cancelTagging()
    else { root.tagging = false; root.taggingCurrent = 0; root.taggingTotal = 0 }
    root.clearSelection()

    root.currentPath = targetPath
    if (root.bridge.getSystemDrives) root.drives = root.bridge.getSystemDrives()
    if (targetPath === root.favoritesPath) {
        root.breadcrumbs = [{ name: "⭐ Favourites", path: root.favoritesPath }]
    } else if (root.bridge.getBreadcrumbs) {
        root.breadcrumbs = root.bridge.getBreadcrumbs(targetPath)
    }
    root.refreshBookmarks()
    if (root.tools) root.tools.watchFolder(targetPath === root.favoritesPath ? "" : targetPath)
    root.creatorInfo = ({ found: false, maybe: false })
    if (root.updates && targetPath !== root.favoritesPath) root.updates.creatorForFolderAsync(targetPath)

    gridView.currentIndex = -1
    listView.currentIndex = -1
    root.keyboardNav = false
    if (targetPath === root.favoritesPath) {
        var fav = root.tools ? root.tools.favoriteItems() : ({ items: [], missing: 0 })
        root.favoritesMissing = fav.missing
        _applyNavListing(root, targetPath, fav.items, fav.items.length, preserveOpts, gridView, listView)
        return
    }
    if (root.bridge.listDirectoryAsync) {
        root._dirReqSeq += 1
        var reqId = "gallery-dir-" + root._dirReqSeq
        root._pendingDirReqId = reqId
        root._pendingDirCtx = {
            mode: "nav",
            targetPath: targetPath,
            preserveOpts: preserveOpts || null
        }
        root.bridge.listDirectoryAsync(reqId, targetPath, root.listingCap)
        return
    }
    if (root.bridge.listDirectory) {
        var items = root.bridge.listDirectory(targetPath, root.listingCap) || []
        var total = root.bridge.getLastListingTotal ? root.bridge.getLastListingTotal() : items.length
        _applyNavListing(root, targetPath, items, total, preserveOpts, gridView, listView)
    } else {
        root.isLoading = false
    }
}

function refreshPreservingScroll(root, gridView, listView) {
    var opts = {
        preserveScroll: true,
        gridY: gridView.contentY,
        listY: listView.contentY,
        quiet: true
    }
    root._doNavigateTo(root.currentPath, true, opts)
}

function liveRefresh(root, gridView, listView) {
    if (!root.bridge || root.inFavorites || root.internalDragActive || !root.currentPath) return
    var gridY = gridView.contentY
    var listY = listView.contentY
    if (root.bridge.listDirectoryAsync) {
        root._dirReqSeq += 1
        var reqId = "gallery-dir-" + root._dirReqSeq
        root._pendingDirReqId = reqId
        root._pendingDirCtx = {
            mode: "live",
            targetPath: root.currentPath,
            gridY: gridY,
            listY: listY
        }
        root.bridge.listDirectoryAsync(reqId, root.currentPath, root.listingCap)
        return
    }
    var items = root.bridge.listDirectory(root.currentPath, root.listingCap) || []
    var total = root.bridge.getLastListingTotal ? root.bridge.getLastListingTotal() : items.length
    _applyLiveListing(root, root.currentPath, items, total, gridY, listY, gridView, listView)
}

function togglePrivacy(root, modalHost) {
    root.privacyBlur = !root.privacyBlur
    root.privacyHintSeen = true
    if (root.privacyBlur) {
        if (root.isModalOpen(modalHost.lightboxLoader)) modalHost.lightboxLoader.item.close()
        if (root.isModalOpen(modalHost.archiveViewerLoader)) modalHost.archiveViewerLoader.item.close()
        root.showToast("Privacy blur on: thumbnails and previews are hidden (Ctrl+H to show them)", false)
    } else {
        root.showToast("Privacy blur off", false)
    }
}

function toggleSaveSearch(root, folderNameFn) {
    var q = root.searchFilter.trim()
    if (!q || root.inFavorites) return
    var list = root.savedSearches.slice()
    var i = root.savedSearchIndex(q, root.currentPath)
    if (i >= 0) {
        list.splice(i, 1)
        root.showToast("Removed the saved search \u201c" + q + "\u201d", false)
    } else {
        list.push({ query: q, path: root.currentPath, recursive: root.searchSubfolders, name: q + "  \u00b7  " + folderNameFn(root.currentPath) })
        root.showToast("Saved \u201c" + q + "\u201d to your Shortcuts bar", false)
        root.showShortcutsBar = true
    }
    root.savedSearchesJson = JSON.stringify(list)
}

function removeSavedSearch(root, entry) {
    var i = root.savedSearchIndex(entry.query, entry.path)
    if (i < 0) return
    var list = root.savedSearches.slice()
    list.splice(i, 1)
    root.savedSearchesJson = JSON.stringify(list)
}

function runSavedSearch(root, entry) {
    if (root._samePlace(root.currentPath, entry.path)) {
        root.searchSubfolders = !!entry.recursive
        root.searchInput.text = entry.query
        return
    }
    root.pendingSearch = entry
    root.navigateTo(entry.path)
}

function selectSection(root, header, index, mouse) {
    var add = mouse && ((mouse.modifiers & Qt.ControlModifier) !== 0)
    var sel = {}
    if (add) for (var k in root.selectedPaths) sel[k] = true
    var paths = header.sectionPaths || []
    for (var i = 0; i < paths.length; i++) sel[paths[i]] = true
    root._setSelection(sel)
    root.selectionAnchor = index
    root.activeView.currentIndex = index
    root.focusBrowser()
}

function toggleSelection(root, path) {
    var sel = {}
    for (var k in root.selectedPaths) sel[k] = true
    if (sel[path]) delete sel[path]
    else sel[path] = true
    root._setSelection(sel)
}

function selectRange(root, fromIndex, toIndex, additive) {
    var list = root.filteredItems || []
    var sel = {}
    if (additive) for (var k in root.selectedPaths) sel[k] = true
    var lo = Math.max(0, Math.min(fromIndex, toIndex))
    var hi = Math.min(list.length - 1, Math.max(fromIndex, toIndex))
    for (var i = lo; i <= hi; i++) if (!root.isSpacer(list[i])) sel[list[i].path] = true
    root._setSelection(sel)
}

function selectAll(root) {
    var list = root.filteredItems || []
    var sel = {}
    for (var i = 0; i < list.length; i++) if (!root.isSpacer(list[i])) sel[list[i].path] = true
    root._setSelection(sel)
}

function selectedItems(root) {
    var out = []
    var list = root.filteredItems || []
    for (var i = 0; i < list.length; i++) {
        if (root.selectedPaths[list[i].path] !== true || root.isSpacer(list[i])) continue
        if (list[i].is_group) out = out.concat(list[i].members)
        else out.push(list[i])
    }
    return out
}

function handleItemClick(root, item, index, mouse) {
    if (item.is_filler) return
    if (item.is_header) { root.selectSection(item, index, mouse); return }
    root.keyboardNav = false
    root._typeBuffer = ""
    root.activeView.currentIndex = index
    root.focusBrowser()
    var ctrl = (mouse.modifiers & Qt.ControlModifier) !== 0
    var shift = (mouse.modifiers & Qt.ShiftModifier) !== 0
    if (shift) { root.selectRange(root.selectionAnchor >= 0 ? root.selectionAnchor : index, index, ctrl); return }
    if (ctrl) { root.toggleSelection(item.path); root.selectionAnchor = index; return }
    root.selectOnly(item.path, index)
}

function openItem(root, item, modalHost) {
    if (item.is_filler) return
    if (item.is_header) { root.selectSection(item, root.activeView.currentIndex, null); return }
    if (item.is_group) root.openGroup(item)
    else if (item.is_dir) root.navigateTo(item.path)
    else if (root.isArchive(item) && root.archiver) root.modal(modalHost.archiveViewerLoader).open(item)
    else if (root.isMedia(item)) root.openLightbox(item)
    else if (root.bridge && root.bridge.openPathInSystem) root.bridge.openPathInSystem(item.path)
}

function showContextMenu(root, menus, item, index, sourceItem, mx, my) {
    if (root.selectedPaths[item.path] !== true) {
        var sel = {}
        sel[item.path] = true
        root._setSelection(sel)
        root.selectionAnchor = index
    }
    root.contextItems = root.selectedItems()
    menus.contextMenu.compressible = root.compressibleOf(root.contextItems)
    menus.contextMenu.sourceUrl = (root.tools && root.contextItems.length === 1 && !root.contextItems[0].is_dir)
        ? (root.tools.sourcePost(root.contextItems[0].path).url || "") : ""
    var p = sourceItem.mapToItem(root, mx, my)
    menus.contextMenu.x = Math.max(4, Math.min(p.x, root.width - menus.contextMenu.width - 4))
    menus.contextMenu.y = Math.max(4, Math.min(p.y, root.height - menus.contextMenu.implicitHeight - 4))
    menus.contextMenu.open()
}

function revealInGallery(root, path) {
    if (!path) return
    var norm = path.replace(/[\\\/]+$/, "")
    var idx = Math.max(norm.lastIndexOf("\\"), norm.lastIndexOf("/"))
    if (idx <= 0) return
    var parent = norm.substring(0, idx)
    if (parent.length === 2 && parent.charAt(1) === ":") parent += "\\"
    root.pendingRevealPath = norm
    root.navigateTo(parent)
}

function applyPendingReveal(root, centerMode) {
    if (!root.pendingRevealPath) return
    var target = root.pendingRevealPath.toLowerCase()
    root.pendingRevealPath = ""
    var list = root.filteredItems || []
    for (var i = 0; i < list.length; i++) {
        if ((list[i].path || "").toLowerCase() === target) {
            var sel = {}
            sel[list[i].path] = true
            root._setSelection(sel)
            root.selectionAnchor = i
            root.activeView.currentIndex = i
            root.activeView.positionViewAtIndex(i, centerMode)
            return
        }
    }
}

function handleDrop(root, modalHost, drop, destDir) {
    if (!destDir) return
    if (root.internalDragActive) {
        var paths = root.dragPaths.filter(function(p) {
            var parent = p.substring(0, Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/")))
            return p.toLowerCase() !== destDir.toLowerCase() && parent.toLowerCase() !== destDir.toLowerCase()
        })
        if (!paths.length) return
        drop.accept(Qt.CopyAction)
        Qt.callLater(function() {
            root.requestSafeAction("Move", function() { root.startMove(paths, destDir, " into ") })
        })
        return
    }
    if (!drop.hasUrls) return
    var external = []
    for (var i = 0; i < drop.urls.length; i++) {
        var lp = root.urlToPath(drop.urls[i])
        if (lp) external.push(lp)
    }
    if (!external.length || root.jobBusy()) return
    drop.accept(Qt.CopyAction)
    Qt.callLater(function() {
        root.requestSafeAction("Copy", function() {
            var err = modalHost.archiveModal.startCopy(external, destDir)
            if (err) root.showToast(err, true)
        })
    })
}

function handleTagsCancelled(root, menus, token, map) {
    if (token !== root.tagsToken) return
    root.tagging = false; root.taggingCurrent = 0; root.taggingTotal = 0
    if (map) {
        var merged = {}
        for (var k in root.charTags) merged[k] = root.charTags[k]
        for (var p in map) merged[p] = map[p]
        root.charTags = merged
    }
    if (menus.charMenu.visible) menus.charMenu.entries = root.characterCounts()
    if (root.characterFilter) root.applyFilter()
}

function handleTagsReady(root, menus, token, map) {
    if (token !== root.tagsToken) return
    var merged = {}
    for (var k in root.charTags) merged[k] = root.charTags[k]
    for (var p in map) merged[p] = map[p]
    var list = root.sortedItems || []
    for (var i = 0; i < list.length; i++) if (!list[i].is_dir && merged[list[i].path] === undefined) merged[list[i].path] = []
    root.charTags = merged
    root.tagging = false; root.taggingCurrent = 0; root.taggingTotal = 0
    if (menus.charMenu.visible) menus.charMenu.entries = root.characterCounts()
    if (root.characterFilter) root.applyFilter()
}

function handleAsyncResult(root, requestId, res, gridView, listView) {
    if (requestId && requestId === root._pendingDirReqId) {
        var ctx = root._pendingDirCtx
        root._pendingDirReqId = ""
        root._pendingDirCtx = null
        if (!ctx) return
        var items = (res && res.items) ? res.items : []
        var total = (res && typeof res.total === "number") ? res.total : items.length
        if (ctx.mode === "live") {
            _applyLiveListing(root, ctx.targetPath, items, total, ctx.gridY, ctx.listY, gridView, listView)
        } else {
            _applyNavListing(root, ctx.targetPath, items, total, ctx.preserveOpts, gridView, listView)
        }
        return
    }
    handleMetaAsyncResult(root, requestId, res)
}

function handleMetaAsyncResult(root, requestId, res) {
    if (requestId && requestId.indexOf("gallery-meta-") === 0) {
        if (res && res.posts_fetched > 0) {
            root.showToast("Metadata refreshed: " + res.posts_fetched + " post(s) saved.")
            root.refreshPreservingScroll()
        } else if (res && res.errors && res.errors.length) {
            root.showToast("Metadata fetch: " + res.errors[0])
        } else {
            root.showToast("No posts found to refresh.")
        }
    }
}
