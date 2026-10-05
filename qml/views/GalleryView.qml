import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import QtMultimedia
import "../components"

Item {
    id: root
    property var bridge: null
    // Compress / Extract backend (registered in main.py)
    readonly property var archiver: (typeof galleryArchiveBridge !== "undefined") ? galleryArchiveBridge : null
    // Search, source post, undo-able move / rename / new folder (registered in main.py)
    readonly property var tools: (typeof galleryTools !== "undefined") ? galleryTools : null

    // Search in subfolders
    // Search the whole folder tree. Always on at start (not remembered); 🗂 turns it off for this session.
    property bool searchSubfolders: true
    property var searchResults: []
    property int searchToken: -1
    property bool searchRunning: false
    property int searchScanned: 0
    readonly property bool recursiveActive: searchSubfolders && !!tools && (searchFilter || "").trim().length >= 2
    // Same check for imperative code: change handlers can run before the binding above updates
    function isRecursiveSearch() {
        return root.searchSubfolders && !!root.tools && (root.searchFilter || "").trim().length >= 2
    }

    // Toast "Undo" button
    property bool toastCanUndo: false
    property bool toastShown: false

    // Grid / list flow-in plays when a folder opens, not when the same folder refreshes in place
    property bool animatePopulate: true
    function quietly(fn) {
        root.animatePopulate = false
        fn()
        Qt.callLater(function() { root.animatePopulate = true })
    }

    // Back / Forward history
    property var backStack: []
    property var forwardStack: []

    // Favourites & ratings ({markKey(path): {fav, rating}}) and the virtual "Favourites" place
    readonly property string favoritesPath: "::favorites"
    readonly property bool inFavorites: currentPath === favoritesPath
    property var marks: ({})
    property int favoritesMissing: 0

    // Character / series filter (names come from the Known list matcher)
    property var charTags: ({})          // path -> [names]
    property int tagsToken: -1
    property bool tagging: false
    property string characterFilter: ""

    // Group by post: files sharing a post ID prefix ("169913374_…") collapse into one stack
    property bool groupByPost: false
    property string openGroupKey: ""
    property string openGroupTitle: ""

    function tr(key, fallback) {
        if (typeof appWindow !== "undefined") return appWindow.tr(key, fallback)
        return fallback !== undefined ? fallback : key
    }

    // ── Reactive Explorer State ──────────────────────────────────────────────
    property string currentPath: ""
    property var rawItems: []
    property var filteredItems: []
    property var breadcrumbs: []
    property var drives: []
    property var bookmarks: []
    property string activeCategory: "all"
    property string searchFilter: ""
    property string viewMode: "grid" // "grid" | "list"
    property bool pathEditMode: false
    property bool isLoading: false

    // ── Sorting, listing cap & multi-selection ───────────────────────────────
    property var sortedItems: []
    property string sortKey: "name"      // "name" | "date" | "size" | "type"
    property int thumbSize: 168          // target grid card width; Ctrl+wheel or the slider changes it
    property bool showPathBar: true       // view options: hide the path bar / shortcuts bar for more room
    property bool showShortcutsBar: true

    // Privacy blur (Ctrl+H): every thumbnail and preview hidden at once. Remembered across restarts.
    property bool privacyBlur: false
    property bool privacyHintSeen: false   // the toolbar button shows a "NEW" dot until first used
    // Group by date: sections such as Today / This week / March 2025
    property bool groupByDate: false
    property int shownItemCount: 0         // visible files / folders (date tiles and fillers don't count)
    // Saved searches, shown as chips in the Shortcuts bar ([{query, path, recursive, name}])
    property string savedSearchesJson: "[]"
    readonly property var savedSearches: { try { return JSON.parse(root.savedSearchesJson) || [] } catch (e) { return [] } }
    property var pendingSearch: null
    // Check for new posts: who the open folder belongs to (galleryUpdates.creatorForFolder)
    readonly property var updates: (typeof galleryUpdates !== "undefined") ? galleryUpdates : null
    property var creatorInfo: ({ found: false, maybe: false })
    property bool sortAscending: true
    readonly property int listingCap: 20000

    // ── Responsive layout ───────────────────────────────────────────────────
    // The gallery shares space with the Progress Log panel. Each toolbar measures
    // its labels (FontMetrics works whether or not a label is currently shown, so
    // there are no binding loops) and only collapses what doesn't fit.
    readonly property bool compact: width < 1000          // status bar wording
    readonly property bool veryCompact: width < 700        // status bar disk label
    readonly property bool showTypeColumn: width >= 760    // list view ITEMS / TYPE column
    readonly property real _fitSlack: 16

    FontMetrics { id: fmButton; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; font.weight: 600 }
    FontMetrics { id: fmDriveName; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; font.weight: 700 }
    FontMetrics { id: fmDriveSpace; font.family: "Segoe UI, monospace"; font.pixelSize: 9 }
    FontMetrics { id: fmPill; font.pixelSize: 11; font.weight: 600 }
    FontMetrics { id: fmSort; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.weight: 600 }
    FontMetrics { id: fmSelCount; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.weight: 700 }

    // Row 1: drives + action buttons. Button labels win over drive free-space labels.
    readonly property real _row1Avail: width - 20 - 8
    readonly property real _drivesCompactW: {
        var w = 0
        var ds = root.drives || []
        for (var i = 0; i < ds.length; i++) w += fmDriveName.advanceWidth("💽 " + (ds[i].name || "")) + 16 + 6
        return w
    }
    readonly property real _drivesLabelsW: {
        var w = 0
        var ds = root.drives || []
        for (var i = 0; i < ds.length; i++) {
            if (ds[i].space_label) w += fmDriveSpace.advanceWidth(ds[i].space_label) + 5
        }
        return w
    }
    readonly property real _actionsIconOnlyW: 216 - 31 + 2 * 11 + 31   // icon-only buttons + view toggle + view options, plus the two group dividers
        + fmButton.advanceWidth("Blurred") + 40 + 11                   // the always-labelled Privacy button and its divider
    readonly property real _actionsLabelsW: {
        var labels = ["New folder", root.tr("gallery_btn_open_system", "Open in Explorer"), "Batch Rename", "Clean & Organize"]
        var w = 0
        for (var i = 0; i < labels.length; i++) w += fmButton.advanceWidth(labels[i]) + 4
        return w
    }
    readonly property bool showActionLabels: _drivesCompactW + _actionsIconOnlyW + _actionsLabelsW + _fitSlack <= _row1Avail
    readonly property bool showDriveLabels: showActionLabels
        && _drivesCompactW + _drivesLabelsW + _actionsIconOnlyW + _actionsLabelsW + _fitSlack <= _row1Avail

    // Row 3: category pills + sort + search
    readonly property real _row3Avail: width - 20 - 16
    function _pillsWidth(full) {
        var allCount = root.recursiveActive ? root.searchResults.length : root.rawItems.length
        var texts = full
            ? ["All (" + allCount + ")", "📁 Folders (" + root.folderCount + ")", "🖼️ Images (" + root.imageCount + ")",
               "🎬 Videos (" + root.videoCount + ")", "📦 Archives (" + root.archiveCount + ")", "🎵 Audio (" + root.audioCount + ")"]
            : ["All (" + allCount + ")", "📁 " + root.folderCount, "🖼️ " + root.imageCount,
               "🎬 " + root.videoCount, "📦 " + root.archiveCount, "🎵 " + root.audioCount]
        var w = 0
        for (var i = 0; i < texts.length; i++) w += fmPill.advanceWidth(texts[i]) + 14 + 6
        return w
    }
    readonly property real _pillsFullW: _pillsWidth(true)
    readonly property real _pillsCompactW: _pillsWidth(false)
    readonly property real _sortFullW: fmSort.advanceWidth(sortLabel(root.sortKey) + "  ▲") + 16 + 18
    readonly property real _sortArrowW: 48
    readonly property bool showZoomSlider: root.viewMode === "grid" && _pillsCompactW + _sortArrowW + 120 + 112 + _fitSlack <= _row3Avail
    readonly property real _zoomW: (showZoomSlider ? 112 : 0) + 34 + 34   // + group-by-post and character buttons
    readonly property bool showPillLabels: _pillsFullW + _zoomW + _sortFullW + 150 + _fitSlack <= _row3Avail
    readonly property bool showSortLabel: _pillsCompactW + _zoomW + _sortFullW + 120 + _fitSlack <= _row3Avail
    readonly property int searchBoxWidth: {
        var pills = (showPillLabels ? _pillsFullW : _pillsCompactW) + _zoomW
        var sort = showSortLabel ? _sortFullW : _sortArrowW
        if (pills + sort + 200 + _fitSlack <= _row3Avail) return 200
        if (pills + sort + 150 + _fitSlack <= _row3Avail) return 150
        return 120
    }

    // Selection bar: chip labels, then the word "selected", then the size
    readonly property real _selBarAvail: width - 20 - 16
    readonly property bool selectionHasArchive: root.selectionCount > 0 && root.archivesIn(root.selectedItems()).length > 0
    // Bar buttons, left to right: organize | archive | More, Delete
    readonly property var _selChipLabels: {
        var labels = ["Move to…"]
        if (root.archiver) {
            labels.push("Copy to…")
            if (root.selectionHasArchive) labels.push("Extract")
            labels.push("Compress")
        }
        return labels.concat(["More", "Delete"])
    }
    readonly property real _selDividersW: (root.archiver ? 2 : 1) * 13
    readonly property real _selChipsFullW: {
        var w = 0
        for (var i = 0; i < _selChipLabels.length; i++) w += 14 + 4 + fmButton.advanceWidth(_selChipLabels[i]) + 14 + 6
        return w + _selDividersW
    }
    readonly property real _selChipsIconW: _selChipLabels.length * (26 + 6) + _selDividersW
    readonly property real _selCountFullW: fmSelCount.advanceWidth("☑ " + root.selectionCount + " selected") + 6
    readonly property real _selLinksW: fmButton.advanceWidth("Select all") + fmButton.advanceWidth("Clear") + 44
    readonly property real _selSizeW: 80
    // Collapse order when space runs out: labels -> size -> Select all/Clear links -> the word "selected"
    readonly property bool showChipLabels: _selCountFullW + _selLinksW + _selChipsFullW + _fitSlack <= _selBarAvail
    readonly property real _selChipsW: showChipLabels ? _selChipsFullW : _selChipsIconW
    readonly property bool showSelLinks: _selChipsW + _selCountFullW + _selLinksW + _fitSlack <= _selBarAvail
    readonly property bool showSelectedWord: _selChipsW + _selCountFullW + (showSelLinks ? _selLinksW : 0) + _fitSlack <= _selBarAvail
    readonly property bool showSelSize: showSelectedWord
        && _selChipsW + _selCountFullW + (showSelLinks ? _selLinksW : 0) + _selSizeW + _fitSlack <= _selBarAvail
    property int listingTotal: 0
    property var selectedPaths: ({})
    property int selectionCount: 0
    property int selectionAnchor: -1
    property var contextItems: []

    // Transient status-bar message after file operations
    property string toastText: ""
    property bool toastIsError: false

    readonly property bool shortcutsEnabled: (typeof appWindow !== "undefined" ? appWindow.currentTab === 6 : root.visible)
        && !isModalOpen(lightboxLoader) && !isModalOpen(batchRenameLoader) && !isModalOpen(galleryCleanerLoader)
        && !isModalOpen(rootDiskSafetyLoader) && !deleteConfirm.isOpen && !renameDialog.isOpen && !archiveModal.isOpen && !isModalOpen(archiveViewerLoader)
        && !isModalOpen(creatorUpdatesLoader) && !isModalOpen(storageLoader)
        && !contextMenu.visible && !sortMenu.visible && !moreMenu.visible && !viewMenu.visible && !charMenu.visible
    // Favourite key: needs the marks store (the image viewer has its own F)
    readonly property bool markShortcutsEnabled: shortcutsEnabled && !!root.tools

    Settings {
        category: "gallery"
        property alias sortKey: root.sortKey
        property alias sortAscending: root.sortAscending
        property alias thumbSize: root.thumbSize
        property alias showPathBar: root.showPathBar
        property alias showShortcutsBar: root.showShortcutsBar
        property alias privacyBlur: root.privacyBlur
        property alias privacyHintSeen: root.privacyHintSeen
        property alias groupByDate: root.groupByDate
        property alias savedSearchesJson: root.savedSearchesJson
        property alias groupByPost: root.groupByPost
    }

    function setThumbSize(v) {
        root.thumbSize = Math.max(120, Math.min(320, Math.round(v / 8) * 8))
    }

    // ── Keyboard navigation helpers ─────────────────────────────────────────
    readonly property var activeView: root.viewMode === "grid" ? explorerGridView : explorerListView

    function focusBrowser() {
        if (root.activeView) root.activeView.forceActiveFocus()
    }

    // ── Accelerated wheel scrolling ─────────────────────────────────────────
    // A single notch always moves one row. Spinning the wheel quickly builds up speed
    // (each quick notch ~25% faster than the last), capped by folder size so small folders
    // never overshoot (≈3x) while huge ones can fly (up to 40x). Touchpads stay pixel-precise.
    property real _lastWheelMs: 0
    property int _wheelStreak: 0

    function scrollTo(view, anim, y) {
        var top = view.originY
        var bottom = view.originY + Math.max(0, view.contentHeight - view.height)
        var target = Math.max(top, Math.min(bottom, y))
        anim.stop()
        anim.from = view.contentY
        anim.to = target
        anim.start()
    }

    function wheelScroll(view, anim, event, rowH, rowsPerNotch) {
        var current = anim.running ? anim.to : view.contentY
        if (event.pixelDelta.y !== 0 && event.angleDelta.y % 120 !== 0) {
            // Touchpad / high-resolution wheel: follow the fingers 1:1 (no acceleration)
            view.contentY = Math.max(view.originY, Math.min(view.originY + Math.max(0, view.contentHeight - view.height), view.contentY - event.pixelDelta.y))
            return
        }
        var now = Date.now()
        root._wheelStreak = (now - root._lastWheelMs < 160) ? root._wheelStreak + 1 : 0
        root._lastWheelMs = now
        var totalRows = view.contentHeight / Math.max(1, rowH)
        var cap = Math.max(3, Math.min(40, totalRows / 25))
        var speed = Math.min(cap, Math.pow(1.25, root._wheelStreak))
        var notches = event.angleDelta.y / 120
        scrollTo(view, anim, current - notches * rowsPerNotch * rowH * speed)
    }

    // The focus ring only shows once the keyboard is used (models reset currentIndex to 0)
    property bool keyboardNav: false

    // Explorer-style keys on the focused grid or list:
    //   arrows move the selection (Shift extends it, Ctrl only moves the focus ring),
    //   Enter opens, Space toggles, Backspace goes up, and typing a name jumps to it.
    function handleBrowserKey(view, event) {
        var list = root.filteredItems || []
        var isArrow = event.key === Qt.Key_Right || event.key === Qt.Key_Down || event.key === Qt.Key_Left || event.key === Qt.Key_Up
        var ctrl = (event.modifiers & Qt.ControlModifier) !== 0
        var shift = (event.modifiers & Qt.ShiftModifier) !== 0
        var alt = (event.modifiers & Qt.AltModifier) !== 0
        root.keyboardNav = true

        if (isArrow || event.key === Qt.Key_Home || event.key === Qt.Key_End) {
            root._typeBuffer = ""   // moving around starts a fresh name search
            if (!list.length) { event.accepted = true; return }
            if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                view.currentIndex = event.key === Qt.Key_Home ? 0 : list.length - 1
                event.accepted = true
            } else if (view.currentIndex < 0 || view.currentIndex >= list.length || root.selectionCount === 0) {
                // Nothing picked yet: the first arrow lands on the current (or first) item instead of skipping it
                if (view.currentIndex < 0 || view.currentIndex >= list.length) view.currentIndex = 0
                event.accepted = true
            }
            // Otherwise the view moves currentIndex itself right after this handler; follow it with the selection
            var from = root.selectionAnchor >= 0 ? root.selectionAnchor : view.currentIndex
            var before = view.currentIndex
            Qt.callLater(function() { root._followKeyboard(view, shift ? from : -1, ctrl, before) })
            return
        }

        var cur = view.currentIndex
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (cur >= 0 && cur < list.length) root.openItem(list[cur])
            event.accepted = true
        } else if (event.key === Qt.Key_Space && !root._typeAheadActive()) {
            if (cur >= 0 && cur < list.length) {
                root.toggleSelection(list[cur].path)
                root.selectionAnchor = cur
            }
            event.accepted = true
        } else if (event.key === Qt.Key_Backspace) {
            if (root.openGroupKey) root.closeGroup()
            else root.navigateUp()
            event.accepted = true
        } else if (event.key === Qt.Key_PageDown || event.key === Qt.Key_PageUp) {
            var anim = view === explorerGridView ? gridScrollAnim : listScrollAnim
            var dir = event.key === Qt.Key_PageDown ? 1 : -1
            scrollTo(view, anim, (anim.running ? anim.to : view.contentY) + dir * view.height * 0.9)
            event.accepted = true
        } else if (!ctrl && !alt && event.text.length === 1 && event.text.charCodeAt(0) >= 32 && event.text.charCodeAt(0) !== 127) {
            root.typeAhead(view, event.text)
            event.accepted = true
        }
    }

    // After an arrow move: select the new item (or extend the range with Shift; Ctrl leaves the selection alone)
    function _followKeyboard(view, rangeFrom, focusOnly, fromIndex) {
        var list = root.filteredItems || []
        var i = view.currentIndex
        // Landed on an empty filler cell (group by date): keep going the same way, else step back
        if (i >= 0 && i < list.length && list[i].is_filler) {
            var dir = (fromIndex !== undefined && fromIndex > i) ? -1 : 1
            var j = i
            while (j >= 0 && j < list.length && list[j].is_filler) j += dir
            if (j < 0 || j >= list.length) { j = i; while (j >= 0 && list[j].is_filler) j-- }
            if (j >= 0) view.currentIndex = j
            i = view.currentIndex
        }
        if (focusOnly || i < 0 || i >= list.length || isSpacer(list[i])) return
        if (rangeFrom >= 0) {
            selectRange(rangeFrom, i, false)
            root.selectionAnchor = rangeFrom
        } else {
            selectOnly(list[i].path, i)
        }
    }

    // ── Type to jump (like File Explorer) ───────────────────────────────────
    // Typing quickly builds a name prefix ("kim" -> KimKai_Drawings); pressing the same letter
    // again cycles through every item starting with it. The prefix resets after a short pause.
    property string _typeBuffer: ""
    property real _typeLastMs: 0
    readonly property int typeAheadResetMs: 1000

    function _typeAheadActive() {
        return root._typeBuffer.length > 0 && Date.now() - root._typeLastMs < root.typeAheadResetMs
    }

    function typeAhead(view, ch) {
        var list = root.filteredItems || []
        if (!list.length) return
        var c = ch.toLowerCase()
        var fresh = !root._typeAheadActive()
        var buf = fresh ? c : root._typeBuffer + c
        root._typeBuffer = buf
        root._typeLastMs = Date.now()

        var sameLetter = true
        for (var k = 0; k < buf.length; k++) if (buf.charAt(k) !== c) { sameLetter = false; break }
        var prefix = sameLetter ? c : buf
        var cur = view.currentIndex
        // A new letter (or a repeated one) moves on to the next match; a longer prefix may stay on the current one
        if (_jumpTo(view, list, prefix, (fresh || sameLetter) ? cur + 1 : Math.max(0, cur))) return
        // Nothing starts with the whole typed text ("ok"): start over from the key just pressed ("k")
        if (prefix !== c) {
            root._typeBuffer = c
            _jumpTo(view, list, c, cur + 1)
        }
    }

    function _jumpTo(view, list, prefix, start) {
        for (var n = 0; n < list.length; n++) {
            var i = ((start + n) % list.length + list.length) % list.length
            if (!isSpacer(list[i]) && (list[i].name || "").toLowerCase().indexOf(prefix) === 0) {
                view.currentIndex = i
                selectOnly(list[i].path, i)
                return true
            }
        }
        return false
    }

    // ── Root Disk & Operating System Safety Status ────────────────────────────
    property var currentPathSafety: (root.bridge && root.bridge.getPathSafetyInfo && root.currentPath !== "::favorites") ? root.bridge.getPathSafetyInfo(root.currentPath) : null
    readonly property bool isCurrentPathBlocked: currentPathSafety ? currentPathSafety.is_blocked : false
    readonly property bool isCurrentPathOtherRoot: currentPathSafety ? currentPathSafety.is_other_root : false

    // Pop-up windows are built the first time they're needed (see the loaders at the bottom)
    function modal(loader) {
        if (!loader.active) loader.active = true
        return loader.item
    }
    function isModalOpen(loader) {
        return !!(loader.item && loader.item.isOpen)
    }

    function requestSafeAction(actionName, actionCallback) {
        if (root.inFavorites) {
            // Folder-wide tools don't apply to a mixed list; per-item actions are still checked by the backend
            if (actionName === "Batch Rename" || actionName === "Clean & Organize") {
                showToast(actionName + " works on a folder: open one first", true)
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
            modal(rootDiskSafetyLoader).showBlocked(actionName, safety.drive_letter, safety.path, safety.message)
            return
        }
        if (safety && safety.is_other_root) {
            modal(rootDiskSafetyLoader).showRootWarning(actionName, safety.drive_letter, safety.path, actionCallback)
            return
        }
        actionCallback()
    }

    readonly property bool isCurrentFolderBookmarked: {
        if (!root.currentPath || !root.bookmarks) return false
        var cp = (root.currentPath || "").toUpperCase().replace(/\\/g, "/").replace(/\/+$/, "")
        for (var i = 0; i < root.bookmarks.length; i++) {
            var bp = (root.bookmarks[i].path || "").toUpperCase().replace(/\\/g, "/").replace(/\/+$/, "")
            if (bp === cp) return true
        }
        return false
    }

    // Counts
    property int folderCount: 0
    property int fileCount: 0
    property real currentFolderFilesSize: 0
    property int imageCount: 0
    property int videoCount: 0
    property int archiveCount: 0
    property int audioCount: 0
    property int otherCount: 0

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

    // ── Helper formatters ───────────────────────────────────────────────────
    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "0 B"
        var k = 1024
        var sizes = ["B", "KB", "MB", "GB", "TB"]
        var i = Math.floor(Math.log(bytes) / Math.log(k))
        if (i < 0) i = 0
        if (i >= sizes.length) i = sizes.length - 1
        return (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1) + " " + sizes[i]
    }

    function formatDate(ts) {
        if (!ts || ts <= 0) return ""
        var d = new Date(ts * 1000)
        var yr = d.getFullYear()
        var mo = ("0" + (d.getMonth() + 1)).slice(-2)
        var da = ("0" + d.getDate()).slice(-2)
        var hr = ("0" + d.getHours()).slice(-2)
        var mn = ("0" + d.getMinutes()).slice(-2)
        return yr + "-" + mo + "-" + da + "  " + hr + ":" + mn
    }

    // Shared with the Lightbox and Archive viewer lists (keep them in sync)
    readonly property var imageExts: [".jpg", ".jpeg", ".jpe", ".jfif", ".pjpeg", ".pjp", ".png", ".apng", ".gif", ".webp", ".avif", ".heic", ".heif", ".jxl", ".bmp", ".dib", ".svg", ".svgz", ".ico", ".cur", ".tif", ".tiff", ".tga", ".psd", ".jp2", ".j2k", ".dds", ".qoi", ".pcx", ".ppm", ".pgm", ".pbm", ".xbm", ".xpm", ".icns", ".wbmp"]
    readonly property var videoExts: [".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".flv", ".f4v", ".wmv", ".asf", ".mpg", ".mpeg", ".m2v", ".ts", ".mts", ".m2ts", ".3gp", ".3g2", ".ogv", ".vob", ".divx"]
    readonly property var audioExts: [".mp3", ".flac", ".wav", ".ogg", ".oga", ".m4a", ".aac", ".opus", ".wma", ".aiff", ".aif", ".alac", ".mka"]

    function getCategory(ext) {
        if (!ext) return "other"
        ext = ext.toLowerCase()
        if (imageExts.indexOf(ext) >= 0) return "image"
        if (videoExts.indexOf(ext) >= 0) return "video"
        if ([".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst", ".tgz", ".cab", ".iso"].indexOf(ext) >= 0) return "archive"
        if (audioExts.indexOf(ext) >= 0) return "audio"
        return "other"
    }

    function getItemIcon(item) {
        if (item.is_group) return "🗂"
        if (item.is_dir) return "📁"
        var cat = getCategory(item.ext)
        if (cat === "image") return "🖼️"
        if (cat === "video") return "🎬"
        if (cat === "archive") return "📦"
        if (cat === "audio") return "🎵"
        return "📄"
    }

    function getItemColor(item) {
        if (item.is_dir) return "#38BDF8"
        var cat = getCategory(item.ext)
        if (cat === "image") return "#EC4899"
        if (cat === "video") return "#8B5CF6"
        if (cat === "archive") return "#F59E0B"
        if (cat === "audio") return "#10B981"
        return "#94A3B8"
    }

    function formatFolderSize(item) {
        if (!item) return ""
        if (item.is_group) return formatBytes(item.size)
        if (!item.is_dir) return formatBytes(item.size)
        if (item.size >= 0) return formatBytes(item.size)
        if (item.child_count >= 0) return item.child_count + (item.child_count === 1 ? " item" : " items")
        return "Calculating…"
    }

    function formatFolderSubtitle(item) {
        if (!item) return ""
        if (!item.is_dir) return formatDate(item.mtime)
        if (item.file_count >= 0) {
            var txt = item.file_count + (item.file_count === 1 ? " file" : " files")
            if (item.folder_count > 0) {
                txt += " • " + item.folder_count + (item.folder_count === 1 ? " dir" : " dirs")
            }
            if (item.size >= 0) {
                txt += " • " + formatBytes(item.size)
            }
            return txt
        }
        if (item.child_count >= 0) {
            return item.child_count + (item.child_count === 1 ? " item" : " items") + " • Calculating size…"
        }
        return "Folder • Calculating size…"
    }

    // ── Live background folder stats & bookmarks updates ────────────────────
    Connections {
        target: root.bridge
        function onFolderStatsCalculated(path, size, fileCount, folderCount) {
            updateFolderStats(path, size, fileCount, folderCount)
        }
        function onGalleryBookmarksChanged() {
            root.refreshBookmarks()
        }
        function onDrivesUpdated(list) {
            root.drives = list      // free space, measured in the background
        }
        function onGalleryShowRequested(path, isDir) {
            if (typeof appWindow !== "undefined") appWindow.currentTab = 6
            if (isDir) root.navigateTo(path)
            else root.revealInGallery(path)
        }
    }

    function refreshBookmarks() {
        Qt.callLater(function() {
            if (root.bridge && root.bridge.getGalleryBookmarks) {
                root.bookmarks = root.bridge.getGalleryBookmarks()
            }
        })
    }

    // Folder sizes arrive one by one in the background. Labels read them from folderStats (bumped via
    // statsRev), so the grid isn't rebuilt (and doesn't replay its flow-in) for every subfolder.
    property var folderStats: ({})
    property int statsRev: 0
    function withFolderStats(item, st) {
        var out = {}
        for (var k in item) out[k] = item[k]
        out.size = st.size
        out.file_count = st.file_count
        out.folder_count = st.folder_count
        return out
    }

    function updateFolderStats(path, size, fileCount, folderCount) {
        var raw = root.rawItems || []
        for (var i = 0; i < raw.length; i++) {
            if (raw[i].path === path) {
                // Keep the source items current too, for sorting and later filters
                raw[i].size = size
                raw[i].file_count = fileCount
                raw[i].folder_count = folderCount
                root.folderStats[path] = { size: size, file_count: fileCount, folder_count: folderCount }
                statsFlushTimer.start()                       // no-op while already pending: batches results
                if (root.sortKey === "size") statsResortTimer.start()
                return
            }
        }
    }

    Timer {
        id: statsFlushTimer
        interval: 120
        onTriggered: root.statsRev++
    }

    // Sorting by size has to reorder, so do that rarely and without the flow-in
    Timer {
        id: statsResortTimer
        interval: 700
        onTriggered: root.resortInPlace()
    }

    function resortInPlace() {
        var gridY = explorerGridView.contentY
        var listY = explorerListView.contentY
        root.quietly(resort)
        Qt.callLater(function() {
            explorerGridView.contentY = Math.min(gridY, Math.max(0, explorerGridView.contentHeight - explorerGridView.height))
            explorerListView.contentY = Math.min(listY, Math.max(0, explorerListView.contentHeight - explorerListView.height))
        })
    }

    function getAllMediaItems() {
        var media = []
        var list = root.filteredItems || []
        for (var i = 0; i < list.length; i++) {
            var it = list[i]
            if (!it.is_dir) {
                var cat = getCategory(it.ext)
                if (cat === "image" || cat === "video" || cat === "audio") {
                    media.push(it)
                }
            }
        }
        return media
    }

    function openLightbox(item) {
        var allMedia = getAllMediaItems()
        modal(lightboxLoader).open(item, allMedia)
    }

    // ── Directory Navigation ────────────────────────────────────────────────
    function navigateTo(path) {
        if (!root.bridge) return
        var targetPath = path || (root.bridge.getDownloadDir ? root.bridge.getDownloadDir() : "")
        Qt.callLater(function() {
            root._doNavigateTo(targetPath, false)
        })
    }

    function _samePlace(a, b) {
        var na = (a || "").replace(/[\\\/]+$/, "").toLowerCase()
        var nb = (b || "").replace(/[\\\/]+$/, "").toLowerCase()
        return na === nb
    }

    // ── Back / Forward ──────────────────────────────────────────────────────
    function goBack() {
        if (!root.backStack.length) return
        var b = root.backStack.slice()
        var target = b.pop()
        root.backStack = b
        root.forwardStack = root.forwardStack.concat([root.currentPath])
        _doNavigateTo(target, true)
    }

    function goForward() {
        if (!root.forwardStack.length) return
        var f = root.forwardStack.slice()
        var target = f.pop()
        root.forwardStack = f
        root.backStack = root.backStack.concat([root.currentPath])
        _doNavigateTo(target, true)
    }

    // ── Favourites & ratings ────────────────────────────────────────────────
    function markKey(path) {
        var p = path || ""
        return Qt.platform.os === "windows" ? p.toLowerCase() : p
    }
    function reloadMarks() {
        root.marks = root.tools ? root.tools.allMarks() : ({})
    }
    function isFavorite(item) {
        if (!item || item.is_group) return false
        var m = root.marks[markKey(item.path)]
        return !!m && m.fav
    }
    function ratingOf(item) {
        if (!item || item.is_group) return 0
        var m = root.marks[markKey(item.path)]
        return m ? (m.rating || 0) : 0
    }
    function starText(n) {
        var t = ""
        for (var i = 0; i < 5; i++) t += i < n ? "★" : "☆"
        return t
    }
    // Targets for favourite / rating shortcuts: the selection, else the keyboard item
    function markTargets() {
        var items = selectedItems()
        if (!items.length && root.activeView.currentIndex >= 0 && root.keyboardNav) {
            var cur = root.filteredItems[root.activeView.currentIndex]
            if (cur) items = cur.is_group ? cur.members : [cur]
        }
        return items
    }
    function toggleFavorite(items) {
        if (!root.tools || !items.length) return
        var allFav = true
        for (var i = 0; i < items.length; i++) if (!isFavorite(items[i])) { allFav = false; break }
        root.tools.setFavorite(_pathsOf(items), !allFav)
        showToast((allFav ? "Removed from" : "Added to") + " favourites" + (items.length > 1 ? " (" + items.length + " items)" : ""), false)
    }
    function setRating(items, n) {
        if (!root.tools || !items.length) return
        root.tools.setRating(_pathsOf(items), n)
        showToast(n > 0 ? ("Rated " + starText(n)) : "Rating cleared", false)
    }
    // ── Character / series filter ──────────────────────────────────────────
    function startTagging() {
        if (!root.tools) return
        var list = root.sortedItems || []
        var work = []
        for (var i = 0; i < list.length; i++) {
            var it = list[i]
            if (it.is_dir || root.charTags[it.path] !== undefined) continue
            work.push({ path: it.path, title: postTitleFromName(it.name) })
        }
        if (!work.length) return
        root.tagging = true
        root.tagsToken = root.tools.tagItems(work)
    }

    // [{ name, count }] for the files currently listed, most common first
    function characterCounts() {
        var counts = {}, display = {}
        var list = root.sortedItems || []
        for (var i = 0; i < list.length; i++) {
            var tags = root.charTags[list[i].path]
            if (!tags || list[i].is_dir) continue
            for (var j = 0; j < tags.length; j++) {
                var k = tags[j].toLowerCase()
                counts[k] = (counts[k] || 0) + 1
                if (!display[k]) display[k] = tags[j]
            }
        }
        var out = []
        for (var key in counts) out.push({ name: display[key], count: counts[key] })
        out.sort(function(a, b) { return b.count - a.count || a.name.localeCompare(b.name) })
        return out
    }

    function hasCharacter(item, name) {
        var tags = root.charTags[item.path]
        if (!tags) return false
        var n = name.toLowerCase()
        for (var i = 0; i < tags.length; i++) if (tags[i].toLowerCase() === n) return true
        return false
    }

    function setCharacterFilter(name) {
        root.characterFilter = name
        clearSelection()
        applyFilter()
        root.activeView.positionViewAtBeginning()
    }

    function openFavorites() {
        navigateTo(root.favoritesPath)
    }

    // Real folder to use for dialogs while in the virtual Favourites view
    function workingFolder(items) {
        if (!root.inFavorites) return root.currentPath
        var first = (items && items.length) ? items[0] : null
        if (!first) return root.bridge && root.bridge.getDownloadDir ? root.bridge.getDownloadDir() : ""
        var p = first.path
        return p.substring(0, Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/")))
    }

    function _doNavigateTo(targetPath, fromHistory) {
        if (!root.bridge) return
        // History: remember where we came from (not for refreshes or Back/Forward themselves)
        if (!fromHistory && root.currentPath && !_samePlace(root.currentPath, targetPath)) {
            root.backStack = root.backStack.concat([root.currentPath]).slice(-50)
            root.forwardStack = []
        }
        root.isLoading = true
        root.pathEditMode = false
        searchInput.text = ""
        root.searchFilter = ""
        root.openGroupKey = ""
        root.openGroupTitle = ""
        root.characterFilter = ""
        root.charTags = ({})
        root.folderStats = ({})
        statsResortTimer.stop()
        root.tagging = false
        root.clearSelection()

        root.currentPath = targetPath

        // Query drives & breadcrumbs
        if (root.bridge.getSystemDrives) {
            root.drives = root.bridge.getSystemDrives()
        }
        if (targetPath === root.favoritesPath) {
            root.breadcrumbs = [{ name: "⭐ Favourites", path: root.favoritesPath }]
        } else if (root.bridge.getBreadcrumbs) {
            root.breadcrumbs = root.bridge.getBreadcrumbs(targetPath)
        }
        root.refreshBookmarks()
        // Live refresh: watch the open folder (nothing to watch for Favourites)
        if (root.tools) root.tools.watchFolder(targetPath === root.favoritesPath ? "" : targetPath)
        root.creatorInfo = (root.updates && targetPath !== root.favoritesPath) ? root.updates.creatorForFolder(targetPath) : ({ found: false, maybe: false })

        // On-demand lazy directory list
        explorerGridView.currentIndex = -1
        explorerListView.currentIndex = -1
        root.keyboardNav = false
        if (targetPath === root.favoritesPath) {
            var fav = root.tools ? root.tools.favoriteItems() : ({ items: [], missing: 0 })
            root.favoritesMissing = fav.missing
            root.listingTotal = fav.items.length
            root.rawItems = fav.items
            updateCounts(fav.items)
            resort()
        } else if (root.bridge.listDirectory) {
            var items = root.bridge.listDirectory(targetPath, root.listingCap) || []
            root.listingTotal = root.bridge.getLastListingTotal ? root.bridge.getLastListingTotal() : items.length
            root.rawItems = items
            updateCounts(items)
            resort()
        }
        root.isLoading = false
        Qt.callLater(root.focusBrowser)
        Qt.callLater(root._applyPendingReveal)
        if (root.pendingSearch && _samePlace(root.pendingSearch.path, targetPath)) {
            var ps = root.pendingSearch
            root.pendingSearch = null
            root.searchSubfolders = !!ps.recursive
            searchInput.text = ps.query
        }
    }

    // Reload the current folder after a file operation without jumping back to the top.
    function refreshPreservingScroll() {
        var gridY = explorerGridView.contentY
        var listY = explorerListView.contentY
        root.quietly(function() { _doNavigateTo(root.currentPath, true) })
        Qt.callLater(function() {
            explorerGridView.contentY = Math.min(gridY, Math.max(0, explorerGridView.contentHeight - explorerGridView.height))
            explorerListView.contentY = Math.min(listY, Math.max(0, explorerListView.contentHeight - explorerListView.height))
        })
    }

    // ── Live refresh (new downloads appear without pressing Refresh) ─────────
    Timer {
        id: liveRefreshTimer
        interval: 700
        onTriggered: root.liveRefresh()
    }

    function liveRefresh() {
        if (!root.bridge || root.inFavorites || root.internalDragActive || !root.currentPath) return
        var gridY = explorerGridView.contentY
        var listY = explorerListView.contentY
        var items = root.bridge.listDirectory(root.currentPath, root.listingCap) || []
        root.listingTotal = root.bridge.getLastListingTotal ? root.bridge.getLastListingTotal() : items.length
        root.rawItems = items
        // Keep only selected items that still exist
        var exists = {}
        for (var i = 0; i < items.length; i++) exists[items[i].path] = true
        var sel = {}
        for (var k in root.selectedPaths) if (exists[k] || k.indexOf("post:") === 0) sel[k] = true
        _setSelection(sel)
        root.quietly(resort)
        if (root.characterFilter) startTagging()
        Qt.callLater(function() {
            explorerGridView.contentY = Math.min(gridY, Math.max(0, explorerGridView.contentHeight - explorerGridView.height))
            explorerListView.contentY = Math.min(listY, Math.max(0, explorerListView.contentHeight - explorerListView.height))
        })
    }

    function navigateUp() {
        if (!root.currentPath || root.breadcrumbs.length <= 1) return
        var parentCrumb = root.breadcrumbs[root.breadcrumbs.length - 2]
        if (parentCrumb && parentCrumb.path) {
            navigateTo(parentCrumb.path)
        }
    }

    function updateCounts(items) {
        var fc = 0, ic = 0, vc = 0, ac = 0, auc = 0, oc = 0
        var totalFilesSize = 0
        for (var i = 0; i < items.length; i++) {
            var it = items[i]
            if (it.is_dir) {
                fc++
            } else {
                if (it.size > 0) totalFilesSize += it.size
                var cat = getCategory(it.ext)
                if (cat === "image") ic++
                else if (cat === "video") vc++
                else if (cat === "archive") ac++
                else if (cat === "audio") auc++
                else oc++
            }
        }
        root.folderCount = fc
        root.fileCount = Math.max(0, items.length - fc)
        root.currentFolderFilesSize = totalFilesSize
        root.imageCount = ic
        root.videoCount = vc
        root.archiveCount = ac
        root.audioCount = auc
        root.otherCount = oc
    }

    // ── Sorting (folders always first, natural number order for names) ───────
    function _naturalKey(name) {
        return (name || "").toLowerCase().match(/\d+|\D+/g) || []
    }

    function _isDigitChunk(s) {
        var c = s.charCodeAt(0)
        return c >= 48 && c <= 57
    }

    function _compareNatural(ka, kb) {
        var n = Math.min(ka.length, kb.length)
        for (var i = 0; i < n; i++) {
            var a = ka[i], b = kb[i]
            if (a === b) continue
            if (_isDigitChunk(a) && _isDigitChunk(b)) {
                var d = parseFloat(a) - parseFloat(b)
                if (d !== 0) return d < 0 ? -1 : 1
                if (a.length !== b.length) return a.length - b.length
                continue
            }
            return a < b ? -1 : 1
        }
        return ka.length - kb.length
    }

    function resort() {
        var recursive = root.isRecursiveSearch()
        var list = recursive ? (root.searchResults || []) : (root.rawItems || [])
        if (recursive) updateCounts(list)
        else updateCounts(root.rawItems || [])
        var key = root.sortKey
        var dir = root.sortAscending ? 1 : -1
        var decorated = new Array(list.length)
        for (var i = 0; i < list.length; i++) {
            decorated[i] = { it: list[i], nk: _naturalKey(list[i].name), i: i }
        }
        decorated.sort(function(a, b) {
            if (a.it.is_dir !== b.it.is_dir) return a.it.is_dir ? -1 : 1
            var c = 0
            if (key === "date") c = (a.it.mtime || 0) - (b.it.mtime || 0)
            else if (key === "rating") c = ratingOf(a.it) - ratingOf(b.it)
            else if (key === "size") c = (a.it.size || 0) - (b.it.size || 0)
            else if (key === "type") {
                var ea = a.it.ext || "", eb = b.it.ext || ""
                c = ea < eb ? -1 : (ea > eb ? 1 : 0)
            }
            if (c === 0) c = _compareNatural(a.nk, b.nk)
            if (c === 0) c = a.i - b.i
            return c * dir
        })
        var out = new Array(decorated.length)
        for (var j = 0; j < decorated.length; j++) out[j] = decorated[j].it
        root.sortedItems = out
        applyFilter()
    }

    function sortBy(key) {
        if (root.sortKey === key) {
            root.sortAscending = !root.sortAscending
        } else {
            root.sortKey = key
            // Newest / largest / best-rated first is the more useful default
            root.sortAscending = !(key === "date" || key === "size" || key === "rating")
        }
        resort()
    }

    function sortLabel(key) {
        if (key === "date") return "Date modified"
        if (key === "size") return "Size"
        if (key === "type") return "Type"
        if (key === "rating") return "Rating"
        return "Name"
    }

    function postKey(item) {
        if (!item || item.is_dir || item.is_group) return ""
        var m = /^(\d{5,})_/.exec(item.name || "")
        return m ? m[1] : ""
    }

    // "169913374_Soon!_32c848.png" -> "Soon!"
    function postTitleFromName(name) {
        var t = (name || "").replace(/^\d{5,}_/, "")
        var dot = t.lastIndexOf(".")
        if (dot > 0) t = t.substring(0, dot)
        // Drop the duplicate-variant suffix, then undo the downloader's ':' -> '_' substitution
        t = t.replace(/_[0-9a-f]{4,8}(_\d+)?$/i, "").replace(/ \(\d+\)$/, "")
        t = t.replace(/_ /g, ": ").replace(/_/g, " ").replace(/\s+/g, " ").trim()
        return t || "Untitled post"
    }

    // Name a stack after a real file of the post, not an embedded-video placeholder
    function _stackTitle(members) {
        for (var i = 0; i < members.length; i++) {
            if (!/^\d{5,}_embed_\d+_/i.test(members[i].name)) return postTitleFromName(members[i].name)
        }
        return postTitleFromName(members[0].name)
    }

    function openGroup(item) {
        root.openGroupKey = item.group_key
        root.openGroupTitle = item.name
        clearSelection()
        root.activeView.currentIndex = -1
        applyFilter()
        root.activeView.positionViewAtBeginning()
        focusBrowser()
    }

    function closeGroup() {
        if (!root.openGroupKey) return
        root.openGroupKey = ""
        root.openGroupTitle = ""
        clearSelection()
        applyFilter()
        focusBrowser()
    }

    onGroupByPostChanged: { if (root.groupByPost) root.groupByDate = false; root.openGroupKey = ""; clearSelection(); applyFilter() }

    // Collapse files with the same post ID into stack items (keeps the sorted order)
    function _groupByPost(list) {
        var groups = {}
        var order = []
        for (var i = 0; i < list.length; i++) {
            var it = list[i]
            var key = postKey(it)
            if (!key) { order.push(it); continue }
            if (!groups[key]) {
                groups[key] = { key: key, members: [] }
                order.push(groups[key])
            }
            groups[key].members.push(it)
        }
        var out = []
        for (var j = 0; j < order.length; j++) {
            var g = order[j]
            if (!g.members) { out.push(g); continue }
            if (g.members.length === 1) { out.push(g.members[0]); continue }
            var size = 0, mtime = 0, cover = null
            for (var k = 0; k < g.members.length; k++) {
                var m = g.members[k]
                if (m.size > 0) size += m.size
                if (m.mtime > mtime) mtime = m.mtime
                var cat = getCategory(m.ext)
                if (!cover && (cat === "image" || cat === "video")) cover = m
            }
            out.push({
                is_group: true, is_dir: false, group_key: g.key,
                name: _stackTitle(g.members),
                path: "post:" + g.key, ext: "", size: size, mtime: mtime,
                members: g.members, cover: cover || g.members[0],
                file_count: g.members.length, folder_count: 0, child_count: g.members.length,
                rel_dir: g.members[0].rel_dir || ""
            })
        }
        return out
    }

    // Search results carry a relative folder; Favourites carry a full one: show its last two levels
    function displayDir(d) {
        if (!d) return ""
        var parts = d.split(/[\\/]+/).filter(function(x) { return x.length > 0 })
        var absolute = d.indexOf(":") === 1 || d.indexOf("\\\\") === 0 || d.charAt(0) === "/"
        return (absolute && parts.length > 2) ? ("…\\" + parts.slice(-2).join("\\")) : d
    }

    function thumbUrl(item) {
        return "image://thumb/" + encodeURIComponent(item.path) + "?m=" + Math.round(item.mtime || 0)
    }

    // ── Privacy blur ────────────────────────────────────────────────────────
    function togglePrivacy() {
        root.privacyBlur = !root.privacyBlur
        root.privacyHintSeen = true
        if (root.privacyBlur) {
            // Anything showing a full picture closes too
            if (isModalOpen(lightboxLoader)) lightboxLoader.item.close()
            if (isModalOpen(archiveViewerLoader)) archiveViewerLoader.item.close()
            showToast("Privacy blur on: thumbnails and previews are hidden (Ctrl+H to show them)", false)
        } else {
            showToast("Privacy blur off", false)
        }
    }

    // ── Saved searches ──────────────────────────────────────────────────────
    function _folderName(p) {
        var t = (p || "").replace(/[\\\/]+$/, "")
        return t.substring(Math.max(t.lastIndexOf("\\"), t.lastIndexOf("/")) + 1) || t
    }
    function savedSearchIndex(query, path) {
        var list = root.savedSearches
        for (var i = 0; i < list.length; i++) if (list[i].query === query && _samePlace(list[i].path, path)) return i
        return -1
    }
    readonly property bool currentSearchSaved: root.searchFilter.trim().length > 0 && savedSearchIndex(root.searchFilter.trim(), root.currentPath) >= 0
    function toggleSaveSearch() {
        var q = root.searchFilter.trim()
        if (!q || root.inFavorites) return
        var list = root.savedSearches.slice()
        var i = savedSearchIndex(q, root.currentPath)
        if (i >= 0) {
            list.splice(i, 1)
            showToast("Removed the saved search \u201c" + q + "\u201d", false)
        } else {
            list.push({ query: q, path: root.currentPath, recursive: root.searchSubfolders, name: q + "  \u00b7  " + _folderName(root.currentPath) })
            showToast("Saved \u201c" + q + "\u201d to your Shortcuts bar", false)
            root.showShortcutsBar = true
        }
        root.savedSearchesJson = JSON.stringify(list)
    }
    function removeSavedSearch(entry) {
        var i = savedSearchIndex(entry.query, entry.path)
        if (i < 0) return
        var list = root.savedSearches.slice()
        list.splice(i, 1)
        root.savedSearchesJson = JSON.stringify(list)
    }
    function runSavedSearch(entry) {
        if (_samePlace(root.currentPath, entry.path)) {
            root.searchSubfolders = !!entry.recursive
            searchInput.text = entry.query
            return
        }
        root.pendingSearch = entry
        navigateTo(entry.path)
    }
    function isCurrentSavedSearch(entry) {
        return _samePlace(root.currentPath, entry.path) && root.searchFilter.trim() === entry.query
    }
    // Folder bookmarks and saved searches share one row of chips
    readonly property var shortcutChips: {
        var out = []
        var b = root.bookmarks || []
        for (var i = 0; i < b.length; i++) out.push({ kind: "folder", name: b[i].name, path: b[i].path, icon: b[i].icon })
        var ss = root.savedSearches
        for (var j = 0; j < ss.length; j++) out.push({ kind: "search", name: ss[j].name || ss[j].query, path: ss[j].path, query: ss[j].query, recursive: !!ss[j].recursive, icon: "🔎" })
        return out
    }

    // ── Group by date ───────────────────────────────────────────────────────
    // Each section starts on a new grid row with a date tile in its first cell (empty "filler"
    // cells finish the previous row). In the list view the tile is a header row.
    readonly property int gridColumns: Math.max(1, Math.floor(explorerGridView.width / Math.max(1, root.thumbSize)))
    onGridColumnsChanged: if (root.groupByDate && root.viewMode === "grid") Qt.callLater(root.applyFilter)
    onViewModeChanged: if (root.groupByDate) Qt.callLater(root.applyFilter)
    onGroupByDateChanged: {
        if (root.groupByDate) root.groupByPost = false
        root.openGroupKey = ""
        clearSelection()
        applyFilter()
    }
    function isSpacer(it) { return !!it && (!!it.is_header || !!it.is_filler) }
    function dateBucket(ts) {
        if (!ts || ts <= 0) return { key: "unknown", label: "Unknown date" }
        var now = new Date()
        var today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000
        if (ts >= today) return { key: "today", label: "Today" }
        if (ts >= today - 86400) return { key: "yesterday", label: "Yesterday" }
        var weekStart = today - ((now.getDay() + 6) % 7) * 86400
        if (ts >= weekStart) return { key: "week", label: "Earlier this week" }
        var monthStart = new Date(now.getFullYear(), now.getMonth(), 1).getTime() / 1000
        if (ts >= monthStart) return { key: "month", label: "Earlier this month" }
        var d = new Date(ts * 1000)
        if (now.getFullYear() - d.getFullYear() <= 1)
            return { key: "m" + d.getFullYear() + "-" + d.getMonth(), label: Qt.formatDate(d, "MMMM yyyy") }
        return { key: "y" + d.getFullYear(), label: "" + d.getFullYear() }
    }
    function _groupByDate(list) {
        var folders = [], sections = {}, order = []
        for (var i = 0; i < list.length; i++) {
            var it = list[i]
            if (it.is_dir) { folders.push(it); continue }
            var b = dateBucket(it.mtime)
            if (!sections[b.key]) { sections[b.key] = { label: b.label, items: [], newest: 0 }; order.push(b.key) }
            sections[b.key].items.push(it)
            sections[b.key].newest = Math.max(sections[b.key].newest, it.mtime || 0)
        }
        var oldestFirst = root.sortKey === "date" && root.sortAscending
        order.sort(function(a, b) { var d = sections[b].newest - sections[a].newest; return oldestFirst ? -d : d })
        var grid = root.viewMode === "grid"
        var cols = root.gridColumns
        var out = []
        function addSection(key, label, icon, items) {
            if (!items.length) return
            var paths = []
            for (var k = 0; k < items.length; k++) paths.push(items[k].path)
            out.push({ is_header: true, path: "::section:" + key, name: label, icon: icon, count: items.length,
                       sectionPaths: paths, ext: "", is_dir: false, size: 0, mtime: 0 })
            for (var m = 0; m < items.length; m++) out.push(items[m])
            if (grid) {
                var pad = (cols - ((items.length + 1) % cols)) % cols
                for (var f = 0; f < pad; f++) out.push({ is_filler: true, path: "::filler:" + key + ":" + f, name: "", ext: "", is_dir: false, size: 0, mtime: 0 })
            }
        }
        addSection("folders", "Folders", "📁", folders)
        for (var o = 0; o < order.length; o++) addSection(order[o], sections[order[o]].label, "📅", sections[order[o]].items)
        return out
    }
    // A date tile was clicked: select everything in its section
    function selectSection(header, index, mouse) {
        var add = mouse && ((mouse.modifiers & Qt.ControlModifier) !== 0)
        var sel = {}
        if (add) for (var k in root.selectedPaths) sel[k] = true
        var paths = header.sectionPaths || []
        for (var i = 0; i < paths.length; i++) sel[paths[i]] = true
        _setSelection(sel)
        root.selectionAnchor = index
        root.activeView.currentIndex = index
        root.focusBrowser()
    }

    // ── Storage / new posts entry points ────────────────────────────────────
    function openStorage() {
        if (!root.tools || root.inFavorites || !root.currentPath) return
        modal(storageLoader).open(root.currentPath)
    }
    function checkForNewPosts() {
        if (!root.updates || root.inFavorites) return
        modal(creatorUpdatesLoader).open(root.currentPath, root.creatorInfo)
    }

    // ── Multi-selection ─────────────────────────────────────────────────────
    function _setSelection(sel) {
        root.selectedPaths = sel
        root.selectionCount = Object.keys(sel).length
    }

    function clearSelection() {
        _setSelection({})
        root.selectionAnchor = -1
    }

    function selectOnly(path, index) {
        var sel = {}
        sel[path] = true
        _setSelection(sel)
        root.selectionAnchor = index
    }

    function toggleSelection(path) {
        var sel = {}
        for (var k in root.selectedPaths) sel[k] = true
        if (sel[path]) delete sel[path]
        else sel[path] = true
        _setSelection(sel)
    }

    function selectRange(fromIndex, toIndex, additive) {
        var list = root.filteredItems || []
        var sel = {}
        if (additive) {
            for (var k in root.selectedPaths) sel[k] = true
        }
        var lo = Math.max(0, Math.min(fromIndex, toIndex))
        var hi = Math.min(list.length - 1, Math.max(fromIndex, toIndex))
        for (var i = lo; i <= hi; i++) if (!isSpacer(list[i])) sel[list[i].path] = true
        _setSelection(sel)
    }

    function selectAll() {
        var list = root.filteredItems || []
        var sel = {}
        for (var i = 0; i < list.length; i++) if (!isSpacer(list[i])) sel[list[i].path] = true
        _setSelection(sel)
    }

    function selectedItems() {
        var out = []
        var list = root.filteredItems || []
        for (var i = 0; i < list.length; i++) {
            if (root.selectedPaths[list[i].path] !== true || isSpacer(list[i])) continue
            if (list[i].is_group) out = out.concat(list[i].members)
            else out.push(list[i])
        }
        return out
    }

    function totalSize(items) {
        var s = 0
        for (var i = 0; i < items.length; i++) {
            if (items[i].size > 0) s += items[i].size
        }
        return s
    }

    function isMedia(item) {
        if (!item || item.is_dir) return false
        var cat = getCategory(item.ext)
        return cat === "image" || cat === "video" || cat === "audio"
    }

    // Like File Explorer: a click selects, Ctrl+click adds / removes, Shift+click selects a range,
    // and a double-click (or Enter) opens.
    function handleItemClick(item, index, mouse) {
        if (item.is_filler) return
        if (item.is_header) { selectSection(item, index, mouse); return }
        root.keyboardNav = false
        root._typeBuffer = ""
        root.activeView.currentIndex = index
        root.focusBrowser()
        var ctrl = (mouse.modifiers & Qt.ControlModifier) !== 0
        var shift = (mouse.modifiers & Qt.ShiftModifier) !== 0
        if (shift) {
            selectRange(root.selectionAnchor >= 0 ? root.selectionAnchor : index, index, ctrl)
            return
        }
        if (ctrl) {
            toggleSelection(item.path)
            root.selectionAnchor = index
            return
        }
        selectOnly(item.path, index)
    }

    function handleItemDoubleClick(item) {
        openItem(item)
    }

    function openItem(item) {
        if (item.is_filler) return
        if (item.is_header) { selectSection(item, root.activeView.currentIndex, null); return }
        if (item.is_group) openGroup(item)
        else if (item.is_dir) navigateTo(item.path)
        else if (isArchive(item) && root.archiver) modal(archiveViewerLoader).open(item)
        else if (isMedia(item)) openLightbox(item)
        else if (root.bridge && root.bridge.openPathInSystem) root.bridge.openPathInSystem(item.path)
    }

    function showContextMenu(item, index, sourceItem, mx, my) {
        if (root.selectedPaths[item.path] !== true) {
            var sel = {}
            sel[item.path] = true
            _setSelection(sel)
            root.selectionAnchor = index
        }
        root.contextItems = selectedItems()
        contextMenu.sourceUrl = (root.tools && root.contextItems.length === 1 && !root.contextItems[0].is_dir)
            ? (root.tools.sourcePost(root.contextItems[0].path).url || "") : ""
        var p = sourceItem.mapToItem(root, mx, my)
        contextMenu.x = Math.max(4, Math.min(p.x, root.width - contextMenu.width - 4))
        contextMenu.y = Math.max(4, Math.min(p.y, root.height - contextMenu.implicitHeight - 4))
        contextMenu.open()
    }

    // ── File actions ────────────────────────────────────────────────────────
    function showToast(text, isError, canUndo) {
        root.toastText = text
        root.toastShown = true
        root.toastIsError = !!isError
        root.toastCanUndo = !!canUndo && !!root.tools && root.tools.canUndo
        toastTimer.restart()
    }

    function undoLast() {
        if (!root.tools || !root.tools.canUndo) {
            showToast("Nothing to undo", false)
            return
        }
        var res = root.tools.undoLast()
        showToast(res.message, !res.success)
        refreshPreservingScroll()
    }

    function _pathsOf(items) {
        var out = []
        for (var i = 0; i < items.length; i++) out.push(items[i].path)
        return out
    }

    function copyPaths(items) {
        if (!root.bridge || !items.length) return
        root.bridge.copyToClipboard(_pathsOf(items).join("\n"))
        showToast(items.length === 1 ? "Copied path to clipboard" : ("Copied " + items.length + " paths to clipboard"), false)
    }

    // Open the item's folder in the gallery and highlight it
    property string pendingRevealPath: ""
    function revealInGallery(path) {
        if (!path) return
        var norm = path.replace(/[\\\/]+$/, "")
        var idx = Math.max(norm.lastIndexOf("\\"), norm.lastIndexOf("/"))
        if (idx <= 0) return
        var parent = norm.substring(0, idx)
        if (parent.length === 2 && parent.charAt(1) === ":") parent += "\\"
        root.pendingRevealPath = norm
        navigateTo(parent)
    }

    function _applyPendingReveal() {
        if (!root.pendingRevealPath) return
        var target = root.pendingRevealPath.toLowerCase()
        root.pendingRevealPath = ""
        var list = root.filteredItems || []
        for (var i = 0; i < list.length; i++) {
            if ((list[i].path || "").toLowerCase() === target) {
                var sel = {}
                sel[list[i].path] = true
                _setSelection(sel)
                root.selectionAnchor = i
                root.activeView.currentIndex = i
                root.activeView.positionViewAtIndex(i, root.viewMode === "grid" ? GridView.Center : ListView.Center)
                return
            }
        }
    }

    function revealItem(item) {
        if (root.bridge && root.bridge.revealFileInExplorer) root.bridge.revealFileInExplorer(item.path)
    }

    function moveItemsToFolder(items) {
        if (!root.bridge || !items.length) return
        root.requestSafeAction("Move", function() {
            var dest = root.bridge.browseFolderDialog("Move " + items.length + (items.length === 1 ? " item" : " items") + " to…", root.workingFolder(items))
            if (!dest) return
            var res = root.tools ? root.tools.moveItems(_pathsOf(items), dest) : root.bridge.moveItems(_pathsOf(items), dest)
            if (res.failed > 0) {
                showToast("Moved " + res.moved + ", " + res.failed + " failed: " + (res.errors.length ? res.errors[0] : ""), true, res.moved > 0)
            } else {
                showToast("Moved " + res.moved + (res.moved === 1 ? " item" : " items") + " to " + dest, false, true)
            }
            refreshPreservingScroll()
        })
    }

    function copyItemsToFolder(items) {
        if (!root.bridge || !items.length || !root.archiver || jobBusy()) return
        root.requestSafeAction("Copy", function() {
            var dest = root.bridge.browseFolderDialog("Copy " + items.length + (items.length === 1 ? " item" : " items") + " to…", root.workingFolder(items))
            if (!dest) return
            var err = archiveModal.startCopy(_pathsOf(items), dest)
            if (err) showToast(err, true)
        })
    }

    function newFolder() {
        if (!root.tools || !root.currentPath || root.inFavorites) return
        root.requestSafeAction("New folder", function() {
            renameDialog.showCreate()
        })
    }

    // ── Drag and drop ───────────────────────────────────────────────────────
    property bool internalDragActive: false
    property var dragPaths: []

    // file:///C:/a%20b/c.png -> C:\a b\c.png  (and file://server/share -> \\server\share)
    function urlToPath(u) {
        var s = u.toString()
        if (s.indexOf("file:///") === 0) s = s.substring(8)
        else if (s.indexOf("file://") === 0) s = "//" + s.substring(7)
        else return ""
        s = decodeURIComponent(s)
        if (Qt.platform.os === "windows") s = s.replace(/\//g, "\\")
        else if (s.charAt(0) !== "/") s = "/" + s
        return s
    }

    function _urlFor(path) {
        return (root.bridge && root.bridge.pathToUrl) ? root.bridge.pathToUrl(path) : ("file:///" + path.replace(/\\/g, "/"))
    }

    // Files a drag carries: the whole selection when dragging a selected item
    function dragItemsFor(item) {
        if (root.selectedPaths[item.path] === true) return selectedItems()
        return item.is_group ? item.members : [item]
    }

    function mimeForItems(items) {
        var urls = []
        for (var i = 0; i < items.length; i++) urls.push(_urlFor(items[i].path))
        return { "text/uri-list": urls.join("\r\n") }
    }

    // Built once per selection change (not per card) to keep big folders fast
    readonly property var selectionMime: selectionCount > 0 ? mimeForItems(selectedItems()) : ({})

    function dragImageFor(item) {
        var preview = item.is_group ? item.cover : item
        if (!preview) return ""
        var cat = getCategory(preview.ext)
        return (cat === "image" || cat === "video") ? thumbUrl(preview) : ""
    }

    function beginDrag(item) {
        root.dragPaths = _pathsOf(dragItemsFor(item))
        root.internalDragActive = true
    }

    function endDrag() {
        root.internalDragActive = false
        root.dragPaths = []
    }

    // Drops: from inside the gallery = move (into a folder); from Explorer etc. = copy
    function handleDrop(drop, destDir) {
        if (!destDir) return
        if (root.internalDragActive) {
            var paths = root.dragPaths.filter(function(p) {
                var parent = p.substring(0, Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/")))
                return p.toLowerCase() !== destDir.toLowerCase() && parent.toLowerCase() !== destDir.toLowerCase()
            })
            if (!paths.length) return
            drop.accept(Qt.CopyAction)  // the only action offered; the gallery itself moves the files
            Qt.callLater(function() {
                root.requestSafeAction("Move", function() {
                    var res = root.tools ? root.tools.moveItems(paths, destDir) : root.bridge.moveItems(paths, destDir)
                    if (res.failed > 0) showToast("Moved " + res.moved + ", " + res.failed + " failed: " + (res.errors.length ? res.errors[0] : ""), true, res.moved > 0)
                    else showToast("Moved " + res.moved + (res.moved === 1 ? " item" : " items") + " into " + destDir, false, true)
                    refreshPreservingScroll()
                })
            })
            return
        }
        if (!drop.hasUrls) return
        var external = []
        for (var i = 0; i < drop.urls.length; i++) {
            var lp = urlToPath(drop.urls[i])
            if (lp) external.push(lp)
        }
        if (!external.length || jobBusy()) return
        drop.accept(Qt.CopyAction)
        Qt.callLater(function() {
            root.requestSafeAction("Copy", function() {
                var err = archiveModal.startCopy(external, destDir)
                if (err) showToast(err, true)
            })
        })
    }

    function renameItem(item) {
        if (!item) return
        root.requestSafeAction("Rename", function() {
            renameDialog.show(item)
        })
    }

    function deleteItems(items) {
        if (!items.length) return
        root.requestSafeAction("Delete", function() {
            deleteConfirm.show(items)
        })
    }

    // ── Archives (compress / extract) ───────────────────────────────────────
    readonly property var archiveExtensions: [".7z", ".zip", ".zipx", ".rar", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".tbz",
                                              ".xz", ".txz", ".zst", ".tzst", ".cab", ".lzma", ".iso"]

    function isArchive(item) {
        if (!item || item.is_dir) return false
        var lower = (item.name || "").toLowerCase()
        if (lower.length > 4 && lower.substring(lower.length - 4) === ".001") return true
        return archiveExtensions.indexOf((item.ext || "").toLowerCase()) >= 0
    }

    function archivesIn(items) {
        var out = []
        for (var i = 0; i < items.length; i++) if (isArchive(items[i])) out.push(items[i])
        return out
    }

    // Only one compress / extract / copy job runs at a time
    function jobBusy() {
        if (root.archiver && root.archiver.busy) {
            showToast("Another file job is still running; its progress is in the status bar", true)
            return true
        }
        return false
    }

    function compressItems(items) {
        if (!items.length || !root.archiver || jobBusy()) return
        root.requestSafeAction("Compress", function() {
            archiveModal.openCompress(items, root.workingFolder(items))
        })
    }

    function extractItems(items, quick) {
        var arcs = archivesIn(items)
        if (!arcs.length || !root.archiver || jobBusy()) return
        root.requestSafeAction("Extract", function() {
            if (quick) archiveModal.quickExtract(arcs, root.workingFolder(arcs))
            else archiveModal.openExtract(arcs, root.workingFolder(arcs))
        })
    }

    // Same rules as the subfolder search (gallery_tools_bridge.parse_search_query):
    // ".png", "*.png" or "ext:png" filter by type (any of several); other words must be in the name.
    function parseQuery(text) {
        var words = [], exts = []
        var toks = (text || "").toLowerCase().split(/\s+/)
        for (var i = 0; i < toks.length; i++) {
            var t = toks[i]
            if (!t) continue
            if (t.indexOf("ext:") === 0) t = "." + t.substring(4).replace(/^\.+/, "")
            else if (t.indexOf("*.") === 0) t = t.substring(1)
            if (t.charAt(0) === "." && t.length > 1) exts.push(t)
            else words.push(t)
        }
        return { words: words, exts: exts }
    }

    function matchesQuery(item, pq) {
        if (!pq.words.length && !pq.exts.length) return true
        var lower = (item.name || "").toLowerCase()
        if (pq.exts.length) {
            if (item.is_dir) return false
            var ok = false
            for (var i = 0; i < pq.exts.length; i++) {
                var e = pq.exts[i]
                if (lower.length >= e.length && lower.substring(lower.length - e.length) === e) { ok = true; break }
            }
            if (!ok) return false
        }
        for (var j = 0; j < pq.words.length; j++) if (lower.indexOf(pq.words[j]) === -1) return false
        return true
    }

    function applyFilter() {
        var recursive = root.isRecursiveSearch()
        var list = root.sortedItems || []
        var cat = root.activeCategory
        var pq = parseQuery(root.searchFilter)

        var filtered = []
        for (var i = 0; i < list.length; i++) {
            var it = list[i]
            // Category filter
            if (cat === "folders" && !it.is_dir) continue
            if (cat === "images" && (it.is_dir || getCategory(it.ext) !== "image")) continue
            if (cat === "videos" && (it.is_dir || getCategory(it.ext) !== "video")) continue
            if (cat === "archives" && (it.is_dir || getCategory(it.ext) !== "archive")) continue
            if (cat === "audio" && (it.is_dir || getCategory(it.ext) !== "audio")) continue

            // Character / series filter (files only)
            if (root.characterFilter && (it.is_dir || !hasCharacter(it, root.characterFilter))) continue

            // Search query filter (subfolder results already match)
            if (!recursive && !matchesQuery(it, pq)) continue

            filtered.push(it)
        }
        if (root.openGroupKey) {
            var inside = []
            for (var g = 0; g < filtered.length; g++) if (postKey(filtered[g]) === root.openGroupKey) inside.push(filtered[g])
            filtered = inside
        } else if (root.groupByPost) {
            filtered = _groupByPost(filtered)
        } else if (root.groupByDate) {
            filtered = _groupByDate(filtered)
        }
        var shown = 0
        for (var c = 0; c < filtered.length; c++) if (!isSpacer(filtered[c])) shown++
        root.shownItemCount = shown
        root.filteredItems = filtered
    }

    // Selections are cleared whenever the visible set changes, so hidden items are never acted on.
    onActiveCategoryChanged: { clearSelection(); applyFilter() }
    onSearchFilterChanged: { clearSelection(); restartSubfolderSearch() }
    onSearchSubfoldersChanged: { clearSelection(); restartSubfolderSearch() }

    // Re-run (debounced) when the query or the toggle changes; plain filtering is instant
    function restartSubfolderSearch() {
        if (root.isRecursiveSearch()) {
            searchDebounce.restart()
        } else {
            searchDebounce.stop()
            if (root.tools && root.searchRunning) root.tools.cancelSearch()
            root.searchRunning = false
            root.searchResults = []
            root.searchToken = -1
        }
        resort()
    }

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
        target: root.tools
        function onWatchedFolderChanged(path) {
            if (root._samePlace(path, root.currentPath)) liveRefreshTimer.restart()
        }
        function onMarksChanged() {
            root.reloadMarks()
            if (root.inFavorites) root.refreshPreservingScroll()
            else if (root.sortKey === "rating") root.resort()
        }
        function onTagsReady(token, map) {
            if (token !== root.tagsToken) return
            var merged = {}
            for (var k in root.charTags) merged[k] = root.charTags[k]
            for (var p in map) merged[p] = map[p]
            // Files with no recognised name are remembered too, so they aren't re-scanned
            var list = root.sortedItems || []
            for (var i = 0; i < list.length; i++) if (!list[i].is_dir && merged[list[i].path] === undefined) merged[list[i].path] = []
            root.charTags = merged
            root.tagging = false
            if (charMenu.visible) charMenu.entries = root.characterCounts()
            if (root.characterFilter) root.applyFilter()
        }
        function onSearchBatch(token, items, done, scanned) {
            if (token !== root.searchToken) return
            if (items.length) root.searchResults = root.searchResults.concat(items)
            root.searchScanned = scanned
            root.searchRunning = !done
            root.quietly(root.resort)
        }
    }

    // Mouse back / forward buttons (cards only take left / right clicks, so these fall through to here)
    MouseArea {
        anchors.fill: parent
        z: -1
        acceptedButtons: Qt.BackButton | Qt.ForwardButton
        onClicked: (mouse) => {
            if (mouse.button === Qt.BackButton) root.goBack()
            else root.goForward()
        }
    }

    Timer {
        id: toastTimer
        interval: 8000
        onTriggered: { root.toastShown = false; root.toastCanUndo = false }
    }

    // ── Keyboard shortcuts (only while the gallery tab is active) ───────────
    Shortcut {
        sequences: [StandardKey.SelectAll]
        enabled: root.shortcutsEnabled
        onActivated: root.selectAll()
    }
    Shortcut {
        sequence: "Escape"
        enabled: root.shortcutsEnabled && root.selectionCount > 0
        onActivated: root.clearSelection()
    }
    Shortcut {
        sequences: [StandardKey.Delete]
        enabled: root.shortcutsEnabled && root.selectionCount > 0
        onActivated: root.deleteItems(root.selectedItems())
    }
    Shortcut {
        sequence: "F2"
        enabled: root.shortcutsEnabled && root.selectionCount === 1
        onActivated: root.renameItem(root.selectedItems()[0])
    }
    Shortcut {
        sequences: [StandardKey.Back, "Alt+Left"]
        enabled: root.shortcutsEnabled && root.backStack.length > 0
        onActivated: root.goBack()
    }
    Shortcut {
        sequences: [StandardKey.Forward, "Alt+Right"]
        enabled: root.shortcutsEnabled && root.forwardStack.length > 0
        onActivated: root.goForward()
    }
    Shortcut {
        sequence: "Ctrl+D"   // letters jump to names; the Lightbox keeps F
        enabled: root.markShortcutsEnabled
        onActivated: root.toggleFavorite(root.markTargets())
    }
    Shortcut {
        sequence: "Ctrl+H"
        enabled: (typeof appWindow !== "undefined" ? appWindow.currentTab === 6 : root.visible)
        onActivated: root.togglePrivacy()
    }
    Shortcut {
        sequence: "Ctrl+Shift+N"
        enabled: root.shortcutsEnabled && !!root.tools
        onActivated: root.newFolder()
    }
    Shortcut {
        sequences: [StandardKey.Undo]
        enabled: root.shortcutsEnabled && !!root.tools && root.tools.canUndo
        onActivated: root.undoLast()
    }

    // Reusable dark menu row used by the context and sort menus
    component MenuRow: Rectangle {
        id: menuRow
        property string icon: ""
        property string label: ""
        property string hint: ""
        property bool danger: false
        property bool checked: false
        signal triggered()
        width: parent ? parent.width : 200
        height: 26
        radius: 4
        color: rowMouse.containsMouse ? (danger ? "#3A1620" : "#1E293D") : "transparent"

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            transform: Translate {
                x: rowMouse.containsMouse ? 3 : 0
                Behavior on x { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.001 } }
            }
            // Color only affects plain symbols (☑ ✕ ▲); color emoji keep their own colors
            Text {
                text: menuRow.icon
                font.pixelSize: 11
                width: 16
                horizontalAlignment: Text.AlignHCenter
                color: menuRow.danger ? "#F87171" : (menuRow.checked ? "#38BDF8" : "#CBD5E1")
            }
            Text {
                text: menuRow.label
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: menuRow.checked ? 700 : Font.Normal
                color: menuRow.danger ? "#F87171" : (menuRow.checked ? "#38BDF8" : "#E2E8F0")
            }
        }
        Text {
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            text: menuRow.hint
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 9
            color: "#64748B"
        }
        MouseArea {
            id: rowMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: menuRow.triggered()
        }
    }

    // Clickable list-view column header; reads/writes the sort state through `gallery`
    component SortHeader: Item {
        id: sh
        property string label: ""
        property string sortKeyName: ""
        property bool alignRight: true
        property var gallery: null
        readonly property bool active: !!gallery && gallery.sortKey === sortKeyName
        height: 18
        Text {
            anchors.fill: parent
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: sh.alignRight ? Text.AlignRight : Text.AlignLeft
            text: sh.label + ((sh.active && sh.gallery) ? (sh.gallery.sortAscending ? "  ▲" : "  ▼") : "")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 9
            font.weight: 700
            color: sh.active ? "#38BDF8" : (shMouse.containsMouse ? "#CBD5E1" : "#64748B")
        }
        MouseArea {
            id: shMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: if (sh.gallery) sh.gallery.sortBy(sh.sortKeyName)
            ToolTip.visible: containsMouse
            ToolTip.delay: 300
            ToolTip.text: "Sort by " + sh.label.toLowerCase() + (sh.active ? " (click to reverse)" : "")
        }
    }

    // Horizontal strip that scrolls with the mouse wheel, by dragging, or with
    // ‹ › arrows that appear only when the content overflows.
    component HScrollStrip: Item {
        id: strip
        default property alias content: flick.flickableData
        property real contentWidth: 0
        property color arrowColor: "#141824"
        readonly property bool overflowing: contentWidth > width + 1
        readonly property real maxX: Math.max(0, flick.contentWidth - flick.width)
        clip: true

        function scrollBy(dx) {
            scrollAnim.stop()
            scrollAnim.to = Math.max(0, Math.min(strip.maxX, flick.contentX + dx))
            scrollAnim.start()
        }
        function scrollToEnd() {
            scrollAnim.stop()
            flick.contentX = strip.maxX
        }

        Flickable {
            id: flick
            anchors.fill: parent
            anchors.leftMargin: strip.overflowing ? 20 : 0
            anchors.rightMargin: strip.overflowing ? 20 : 0
            contentWidth: strip.contentWidth
            contentHeight: height
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            NumberAnimation { id: scrollAnim; target: flick; property: "contentX"; duration: 180; easing.type: Easing.OutCubic }
        }

        // Vertical wheel (or touchpad swipe) scrolls the strip sideways
        WheelHandler {
            target: null
            enabled: strip.overflowing
            onWheel: (event) => {
                var d = event.angleDelta.y !== 0 ? event.angleDelta.y : event.angleDelta.x
                scrollAnim.stop()
                flick.contentX = Math.max(0, Math.min(strip.maxX, flick.contentX - d * 0.6))
            }
        }

        Rectangle {
            visible: strip.overflowing
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: 18; height: Math.min(22, strip.height); radius: 4
            color: leftArrowMouse.containsMouse && flick.contentX > 0 ? "#1E293B" : strip.arrowColor
            opacity: flick.contentX > 0 ? 1.0 : 0.35
            Text { anchors.centerIn: parent; text: "‹"; font.pixelSize: 14; font.weight: 700; color: "#CBD5E1" }
            Springy { hover: leftArrowMouse.containsMouse; pressed: leftArrowMouse.pressed }
            MouseArea {
                id: leftArrowMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: flick.contentX > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: strip.scrollBy(-flick.width * 0.7)
            }
        }
        Rectangle {
            visible: strip.overflowing
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: 18; height: Math.min(22, strip.height); radius: 4
            color: rightArrowMouse.containsMouse && flick.contentX < strip.maxX - 1 ? "#1E293B" : strip.arrowColor
            opacity: flick.contentX < strip.maxX - 1 ? 1.0 : 0.35
            Text { anchors.centerIn: parent; text: "›"; font.pixelSize: 14; font.weight: 700; color: "#CBD5E1" }
            Springy { hover: rightArrowMouse.containsMouse; pressed: rightArrowMouse.pressed }
            MouseArea {
                id: rightArrowMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: flick.contentX < strip.maxX - 1 ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: strip.scrollBy(flick.width * 0.7)
            }
        }
    }

    component RatingRow: Rectangle {
        id: rr
        property int current: 0
        property int hovered: 0
        signal rated(int n)
        width: parent ? parent.width : 200
        height: 26
        radius: 4
        color: "transparent"
        Row {
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            Text { text: "★"; width: 16; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 11; color: "#CBD5E1" }
            Text { text: "Rate"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; color: "#E2E8F0"; width: 34 }
            Repeater {
                model: 5
                delegate: Text {
                    readonly property int n: index + 1
                    text: (rr.hovered ? n <= rr.hovered : n <= rr.current) ? "★" : "☆"
                    font.pixelSize: 14
                    color: (rr.hovered ? n <= rr.hovered : n <= rr.current) ? "#FBBF24" : "#64748B"
                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -2
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: rr.hovered = parent.n
                        onExited: rr.hovered = 0
                        onClicked: rr.rated(parent.n === rr.current ? 0 : parent.n)
                    }
                }
            }
        }
    }

    component MenuDivider: Rectangle {
        width: parent ? parent.width : 200
        height: 9
        color: "transparent"
        Rectangle { anchors.centerIn: parent; width: parent.width - 8; height: 1; color: "#232B3D" }
    }

    // Text link used next to the selection count
    component SelLink: Text {
        id: link
        property string label: ""
        property string tip: ""
        signal triggered()
        text: label
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 10
        font.weight: 600
        font.underline: linkMouse.containsMouse
        color: linkMouse.containsMouse ? "#BAE6FD" : "#7DD3FC"
        Springy { hover: linkMouse.containsMouse; pressed: linkMouse.pressed }
        MouseArea {
            id: linkMouse
            anchors.fill: parent
            anchors.margins: -3
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: link.triggered()
            ToolTip.visible: containsMouse && link.tip.length > 0
            ToolTip.delay: 300
            ToolTip.text: link.tip
        }
    }

    // Thin separator between button groups
    component BarDivider: Rectangle {
        implicitWidth: 1
        implicitHeight: 18
        Layout.leftMargin: 3
        Layout.rightMargin: 3
        color: "#2A3A52"
    }

    // Compact button used in the selection action bar
    component ActionChip: Rectangle {
        id: chip
        property string icon: ""
        property string label: ""
        property string tip: ""
        property bool danger: false
        property bool compact: false   // icon-only (label moves to the tooltip)
        signal triggered()
        implicitHeight: 24
        implicitWidth: chipRow.implicitWidth + (compact ? 12 : 14)
        radius: 5
        color: chipMouse.containsMouse ? (danger ? "#3A1620" : "#1E293B") : "#141720"
        border.color: chipMouse.containsMouse ? (danger ? "#EF4444" : "#38BDF8") : "#2E384D"
        border.width: 1
        Row {
            id: chipRow
            anchors.centerIn: parent
            spacing: 4
            Text {
                text: chip.icon
                font.pixelSize: 13          // symbol glyphs (⊞ ⋯ ⧉) read too small at text size
                anchors.verticalCenter: parent.verticalCenter
                visible: chip.icon.length > 0
                color: chip.danger ? "#F87171" : "#CBD5E1"
            }
            Text {
                text: chip.label
                anchors.verticalCenter: parent.verticalCenter
                visible: !(chip.compact && chip.icon.length > 0)
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                font.weight: 600
                color: chip.danger ? "#F87171" : "#E2E8F0"
            }
        }
        Springy { hover: chipMouse.containsMouse; pressed: chipMouse.pressed }
        MouseArea {
            id: chipMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: chip.triggered()
            ToolTip.visible: containsMouse && (chip.tip.length > 0 || chip.compact)
            ToolTip.delay: 300
            ToolTip.text: (chip.compact && chip.icon.length > 0) ? (chip.label + (chip.tip ? "
" + chip.tip : "")) : chip.tip
        }
    }

    Component.onCompleted: {
        reloadMarks()
        navigateTo("")
    }

    // ── Main UI Layout ──────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // 1. DRIVES & TOOLBAR ACTIONS
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            // Drive quick selectors with live storage space (scrolls sideways if they don't fit)
            HScrollStrip {
                Layout.fillWidth: true
                Layout.minimumWidth: 40
                implicitHeight: 26
                contentWidth: drivesRow.implicitWidth

                Row {
                    id: drivesRow
                    spacing: 6

                    Repeater {
                        model: root.drives
                        delegate: Rectangle {
                            readonly property bool isCurrentDrive: {
                                if (!root.currentPath || !modelData.name) return false
                                var cp = root.currentPath.toUpperCase().replace(/\\/g, "/")
                                var dn = modelData.name.toUpperCase().replace(/\\/g, "/")
                                return cp.indexOf(dn) === 0
                            }

                            implicitHeight: 26
                            implicitWidth: driveRow.implicitWidth + 16
                            radius: 5
                            color: isCurrentDrive ? "#1B283D" : (driveMouse.containsMouse ? "#182030" : "#111520")
                            border.color: isCurrentDrive ? "#38BDF8" : (driveMouse.containsMouse ? "#60A5FA" : "#243046")
                            border.width: 1
                            clip: true

                            Row {
                                id: driveRow
                                anchors.centerIn: parent
                                spacing: 5

                                Text {
                                    id: driveNameText
                                    text: "💽 " + modelData.name
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: 700
                                    color: isCurrentDrive ? "#38BDF8" : "#E2E8F0"
                                }

                                // Free / total space, sitting on the same baseline as the drive letter
                                Text {
                                    anchors.baseline: driveNameText.baseline
                                    visible: !!modelData.space_label && root.showDriveLabels
                                    text: modelData.space_label
                                    font.family: "Segoe UI, monospace"
                                    font.pixelSize: 9
                                    color: isCurrentDrive ? "#7DD3FC" : ((modelData.percent_free < 10) ? "#F87171" : "#94A3B8")
                                }
                            }

                            // Storage mini progress bar at bottom
                            Rectangle {
                                anchors.bottom: parent.bottom
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 1
                                height: 2
                                radius: 1
                                color: "#1E2536"
                                visible: !!modelData.total_bytes && modelData.total_bytes > 0

                                Rectangle {
                                    height: parent.height
                                    width: Math.min(parent.width, parent.width * Math.max(0.02, 1.0 - (modelData.percent_free || 0) / 100.0))
                                    radius: 1
                                    color: (modelData.percent_free < 10) ? "#EF4444" : ((modelData.percent_free < 20) ? "#F59E0B" : (isCurrentDrive ? "#38BDF8" : "#64748B"))
                                }
                            }

                            Springy { hover: driveMouse.containsMouse; pressed: driveMouse.pressed }
                            MouseArea {
                                id: driveMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: navigateTo(modelData.path)
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Drive " + (modelData.name || modelData.path) + (modelData.free_str ? ("\n" + modelData.free_str + " free of " + modelData.total_str + " (" + (100 - Math.round(modelData.percent_free)) + "% used)") : "")
                            }
                        }
                    }
                }
            }

            // Compact Action Buttons on Right
            Row {
                spacing: 5
                Layout.alignment: Qt.AlignVCenter

                // ── Privacy blur: one obvious button (Ctrl+H) ──
                Rectangle {
                    id: privacyBtn
                    implicitWidth: privacyRow.implicitWidth + 16
                    implicitHeight: 26
                    radius: 13
                    color: root.privacyBlur ? "#F59E0B" : (privacyMouse.containsMouse ? "#2A2210" : "#1A1710")
                    border.color: root.privacyBlur ? "#FCD34D" : "#F59E0B"
                    border.width: 1
                    Row {
                        id: privacyRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: root.privacyBlur ? "🙈" : "👁"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: root.privacyBlur ? "Blurred" : "Privacy"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 700
                            color: root.privacyBlur ? "#1C1404" : "#FCD34D"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    // "New" dot until the first use
                    Rectangle {
                        visible: !root.privacyHintSeen
                        width: 9; height: 9; radius: 4.5
                        color: "#EF4444"
                        border.color: "#0B0E14"; border.width: 1.5
                        anchors.right: parent.right; anchors.top: parent.top
                        anchors.rightMargin: -2; anchors.topMargin: -2
                        SequentialAnimation on scale {
                            running: !root.privacyHintSeen
                            loops: Animation.Infinite
                            NumberAnimation { to: 1.35; duration: 600; easing.type: Easing.OutCubic }
                            NumberAnimation { to: 1.0; duration: 600; easing.type: Easing.InCubic }
                        }
                    }
                    Springy { hover: privacyMouse.containsMouse; pressed: privacyMouse.pressed }
                    MouseArea {
                        id: privacyMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.togglePrivacy()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 200
                        ToolTip.text: root.privacyBlur
                            ? "Privacy blur is ON: thumbnails and previews are hidden.\nClick or press Ctrl+H to show them again."
                            : "Privacy blur: instantly hide every thumbnail and preview,\nfor when someone walks by. Shortcut: Ctrl+H (works anywhere in the Gallery)."
                    }
                }
                BarDivider {}

                // ── This folder ──
                // Action: New folder
                Rectangle {
                    visible: !!root.tools
                    implicitWidth: newFolderRow.implicitWidth + 12
                    implicitHeight: 26
                    radius: 5
                    color: newFolderMouse.containsMouse ? "#1E293B" : "#141720"
                    border.color: newFolderMouse.containsMouse ? "#38BDF8" : "#2E384D"
                    border.width: 1
                    Row {
                        id: newFolderRow
                        anchors.centerIn: parent
                        spacing: 4
                        Item {
                            width: 15
                            height: 14
                            anchors.verticalCenter: parent.verticalCenter
                            Text { anchors.centerIn: parent; text: "📁"; font.pixelSize: 11 }
                            Text { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.rightMargin: -2; anchors.bottomMargin: -3; text: "+"; font.pixelSize: 10; font.weight: 800; color: "#34D399" }
                        }
                        Text {
                            visible: root.showActionLabels
                            anchors.verticalCenter: parent.verticalCenter
                            text: "New folder"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#E2E8F0"
                        }
                    }
                    Springy { hover: newFolderMouse.containsMouse; pressed: newFolderMouse.pressed }
                    MouseArea {
                        id: newFolderMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.newFolder()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "New folder (Ctrl+Shift+N)"
                    }
                }

                // Action: Open in OS Explorer
                Rectangle {
                    implicitHeight: 26
                    implicitWidth: openBtnRow.implicitWidth + 12
                    radius: 5
                    color: openBtnMouse.containsMouse ? "#1E293B" : "#141720"
                    border.color: openBtnMouse.containsMouse ? "#38BDF8" : "#2E384D"
                    border.width: 1

                    Row {
                        id: openBtnRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "📂"; font.pixelSize: 11 }
                        Text {
                            text: root.tr("gallery_btn_open_system", "Open in Explorer")
                            visible: root.showActionLabels
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#E2E8F0"
                        }
                    }
                    Springy { hover: openBtnMouse.containsMouse; pressed: openBtnMouse.pressed }
                    MouseArea {
                        id: openBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.bridge && root.bridge.openFolder) {
                                if (root.inFavorites) root.showToast("Favourites isn't a real folder: right-click a file → Show in File Explorer", true)
                                else root.bridge.openFolder(root.currentPath)
                            }
                        }
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Open current folder in File Explorer / OS file manager"
                    }
                }

                // ── group divider ──
                Rectangle { width: 1; height: 18; color: "#2A3A52"; anchors.verticalCenter: parent.verticalCenter }

                // ── Tools ──
                // Action: Smart Batch Renamer
                Rectangle {
                    implicitHeight: 26
                    implicitWidth: renameBtnRow.implicitWidth + 12
                    radius: 5
                    color: root.isCurrentPathBlocked ? "#161922" : (renameBtnMouse.containsMouse ? "#1E293D" : "#141720")
                    border.color: root.isCurrentPathBlocked ? "#283042" : (root.isCurrentPathOtherRoot ? "#F59E0B" : (renameBtnMouse.containsMouse ? "#F59E0B" : "#2E384D"))
                    border.width: 1
                    opacity: root.isCurrentPathBlocked ? 0.38 : 1.0

                    Row {
                        id: renameBtnRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "🏷️"; font.pixelSize: 11 }
                        Text {
                            text: "Batch Rename"
                            visible: root.showActionLabels
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: root.isCurrentPathBlocked ? "#64748B" : "#E2E8F0"
                        }
                    }
                    Springy { hover: renameBtnMouse.containsMouse; pressed: renameBtnMouse.pressed }
                    MouseArea {
                        id: renameBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: root.isCurrentPathBlocked ? Qt.ForbiddenCursor : Qt.PointingHandCursor
                        onClicked: {
                            root.requestSafeAction("Batch Rename", function() {
                                modal(batchRenameLoader).open(root.currentPath, root.filteredItems)
                            })
                        }
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: root.isCurrentPathBlocked ?
                            ("🛡️ Operation Disabled on Protected Path\n" + (root.currentPathSafety && root.currentPathSafety.message ? root.currentPathSafety.message : "Operations on this system or protected path are permanently disabled.")) :
                            (root.isCurrentPathOtherRoot ?
                                ("⚠️ Root Drive Selected (" + (root.currentPathSafety ? root.currentPathSafety.drive_letter : "") + "\\)\nBatch Rename on root drives requires double-confirmation.") :
                                "Smart Batch Renamer\nBulk rename and organize files with metadata variables, sequential numbering, and flattening")
                    }
                }

                // Action: Cleaner & Deduplicator
                Rectangle {
                    implicitHeight: 26
                    implicitWidth: cleanBtnRow.implicitWidth + 12
                    radius: 5
                    color: root.isCurrentPathBlocked ? "#161922" : (cleanBtnMouse.containsMouse ? "#1E293D" : "#141720")
                    border.color: root.isCurrentPathBlocked ? "#283042" : (root.isCurrentPathOtherRoot ? "#F59E0B" : (cleanBtnMouse.containsMouse ? "#10B981" : "#2E384D"))
                    border.width: 1
                    opacity: root.isCurrentPathBlocked ? 0.38 : 1.0

                    Row {
                        id: cleanBtnRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "🧹"; font.pixelSize: 11 }
                        Text {
                            text: "Clean & Organize"
                            visible: root.showActionLabels
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: root.isCurrentPathBlocked ? "#64748B" : "#E2E8F0"
                        }
                    }
                    Springy { hover: cleanBtnMouse.containsMouse; pressed: cleanBtnMouse.pressed }
                    MouseArea {
                        id: cleanBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: root.isCurrentPathBlocked ? Qt.ForbiddenCursor : Qt.PointingHandCursor
                        onClicked: {
                            root.requestSafeAction("Clean & Organize", function() {
                                modal(galleryCleanerLoader).open(root.currentPath)
                            })
                        }
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: root.isCurrentPathBlocked ?
                            ("🛡️ Operation Disabled on Protected Path\n" + (root.currentPathSafety && root.currentPathSafety.message ? root.currentPathSafety.message : "Operations on this system or protected path are permanently disabled.")) :
                            (root.isCurrentPathOtherRoot ?
                                ("⚠️ Root Drive Selected (" + (root.currentPathSafety ? root.currentPathSafety.drive_letter : "") + "\\)\nClean & Organize on root drives requires double-confirmation.") :
                                "Clean & Organize\nFind 0-byte broken files, detect duplicate downloads by SHA-256 hash, and auto-sort media into folders")
                    }
                }

                // ── group divider · View ──
                Rectangle { width: 1; height: 18; color: "#2A3A52"; anchors.verticalCenter: parent.verticalCenter }

                // View Mode Toggle (Grid vs List)
                Rectangle {
                    implicitHeight: 26
                    implicitWidth: 54
                    radius: 5
                    color: "#12151E"
                    border.color: "#252C3D"
                    border.width: 1

                    Row {
                        anchors.centerIn: parent
                        spacing: 2

                        Rectangle {
                            width: 24
                            height: 20
                            radius: 3
                            color: root.viewMode === "grid" ? "#222D42" : "transparent"
                            border.color: root.viewMode === "grid" ? "#38BDF8" : "transparent"
                            border.width: 1
                            Text { anchors.centerIn: parent; text: "⊞"; font.pixelSize: 11; color: root.viewMode === "grid" ? "#38BDF8" : "#64748B" }
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.viewMode = "grid"
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Grid View\nDisplay files and folders as visual cards with thumbnails"
                            }
                        }
                        Rectangle {
                            width: 24
                            height: 20
                            radius: 3
                            color: root.viewMode === "list" ? "#222D42" : "transparent"
                            border.color: root.viewMode === "list" ? "#38BDF8" : "transparent"
                            border.width: 1
                            Text { anchors.centerIn: parent; text: "📑"; font.pixelSize: 10; color: root.viewMode === "list" ? "#38BDF8" : "#64748B" }
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.viewMode = "list"
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "List View\nDisplay detailed file information: names, item counts, sizes, and modified dates"
                            }
                        }
                    }
                }

                // View options: show / hide the path bar and shortcuts bar
                Rectangle {
                    id: viewOptionsButton
                    width: 26
                    height: 26
                    radius: 5
                    color: (viewOptsMouse.containsMouse || viewMenu.visible) ? "#1E293B" : "#141720"
                    border.color: (viewOptsMouse.containsMouse || viewMenu.visible) ? "#38BDF8" : "#2E384D"
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "⋮"; font.pixelSize: 14; font.weight: 800; color: "#CBD5E1" }
                    Springy { hover: viewOptsMouse.containsMouse; pressed: viewOptsMouse.pressed }
                    MouseArea {
                        id: viewOptsMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var p = viewOptionsButton.mapToItem(root, viewOptionsButton.width - viewMenu.width, viewOptionsButton.height + 4)
                            viewMenu.x = Math.max(4, p.x)
                            viewMenu.y = p.y
                            viewMenu.open()
                        }
                        ToolTip.visible: containsMouse && !viewMenu.visible
                        ToolTip.delay: 300
                        ToolTip.text: "View options: show or hide the path bar and shortcuts bar"
                    }
                }
            }
        }

        // 2. BREADCRUMBS BAR (can be hidden from the view options menu)
        Rectangle {
            Layout.fillWidth: true
            readonly property bool shown: root.showPathBar
            property real reveal: shown ? 1 : 0
            Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
            implicitHeight: 32
            Layout.preferredHeight: 32 * Math.max(0, reveal)
            visible: reveal > 0.01
            opacity: Math.max(0, Math.min(1, reveal))
            clip: true
            radius: 6
            color: "#121622"
            border.color: "#232A3B"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                spacing: 6

                // Back / Forward (Alt+← / Alt+→, mouse side buttons)
                Repeater {
                    model: [ { dir: -1, glyph: "◀", tip: "Back (Alt+←)" }, { dir: 1, glyph: "▶", tip: "Forward (Alt+→)" } ]
                    delegate: Rectangle {
                        readonly property bool can: modelData.dir < 0 ? root.backStack.length > 0 : root.forwardStack.length > 0
                        width: 24
                        height: 24
                        radius: 4
                        color: (histMouse.containsMouse && can) ? "#1E273A" : "#161B29"
                        border.color: (histMouse.containsMouse && can) ? "#38BDF8" : "#2B354C"
                        border.width: 1
                        opacity: can ? 1.0 : 0.4
                        Text { anchors.centerIn: parent; text: modelData.glyph; font.pixelSize: 9; color: "#E2E8F0" }
                        Springy { hover: histMouse.containsMouse; pressed: histMouse.pressed }
                        MouseArea {
                            id: histMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: parent.can ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: if (parent.can) { if (modelData.dir < 0) root.goBack(); else root.goForward() }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: modelData.tip
                        }
                    }
                }

                // Parent directory button
                Rectangle {
                    width: 24
                    height: 24
                    radius: 4
                    color: (upBtnMouse.containsMouse && root.breadcrumbs.length > 1) ? "#1E273A" : "#161B29"
                    border.color: (upBtnMouse.containsMouse && root.breadcrumbs.length > 1) ? "#38BDF8" : "#2B354C"
                    border.width: 1
                    opacity: root.breadcrumbs.length > 1 ? 1.0 : 0.4

                    Text {
                        anchors.centerIn: parent
                        text: "⬆"
                        font.pixelSize: 11
                        color: "#E2E8F0"
                    }
                    Springy { hover: upBtnMouse.containsMouse; pressed: upBtnMouse.pressed }
                    MouseArea {
                        id: upBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: root.breadcrumbs.length > 1 ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: navigateUp()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: root.breadcrumbs.length > 1 ? ("Go up to: " + (root.breadcrumbs.length >= 2 ? root.breadcrumbs[root.breadcrumbs.length - 2].path : "parent directory")) : "Already at root level"
                    }
                }

                // Breadcrumbs strip (scrolls; jumps to the current folder on navigation)
                HScrollStrip {
                    id: crumbStrip
                    Layout.fillWidth: true
                    implicitHeight: 24
                    contentWidth: crumbRow.implicitWidth
                    arrowColor: "#161B29"
                    onMaxXChanged: scrollToEnd()

                    Row {
                        id: crumbRow
                        spacing: 4
                        anchors.verticalCenter: parent.verticalCenter

                        Repeater {
                            model: root.breadcrumbs
                            delegate: Row {
                                spacing: 4
                                anchors.verticalCenter: parent.verticalCenter

                                Rectangle {
                                    implicitHeight: 22
                                    implicitWidth: crumbText.implicitWidth + 10
                                    radius: 4
                                    color: (crumbMouse.containsMouse || index === (root.breadcrumbs.length - 1)) ? "#1E293D" : "transparent"
                                    border.color: index === (root.breadcrumbs.length - 1) ? "#38BDF8" : "transparent"
                                    border.width: 1

                                    Text {
                                        id: crumbText
                                        anchors.centerIn: parent
                                        text: modelData.name || ""
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: index === (root.breadcrumbs.length - 1) ? 700 : Font.Normal
                                        color: index === (root.breadcrumbs.length - 1) ? "#F8FAFC" : "#94A3B8"
                                    }
                                    Springy { hover: crumbMouse.containsMouse; pressed: crumbMouse.pressed }
                                    MouseArea {
                                        id: crumbMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: navigateTo(modelData.path)
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 250
                                        ToolTip.text: "Navigate to " + modelData.path
                                    }
                                }

                                Text {
                                    visible: index < (root.breadcrumbs.length - 1)
                                    text: "›"
                                    font.pixelSize: 11
                                    color: "#475569"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                    }
                }

                // Refresh this folder (path bar, like File Explorer)
                Rectangle {
                    width: 24
                    height: 24
                    radius: 5
                    color: refBtnMouse.containsMouse ? "#1E293B" : "#141720"
                    border.color: refBtnMouse.containsMouse ? "#38BDF8" : "#2E384D"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "🔄"
                        font.pixelSize: 11
                    }
                    Springy { hover: refBtnMouse.containsMouse; pressed: refBtnMouse.pressed }
                    MouseArea {
                        id: refBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: navigateTo(root.currentPath)
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "Refresh current directory contents"
                    }
                }

                // Check for new posts from the creator of this folder
                Rectangle {
                    visible: !!root.updates && !root.inFavorites && (!!root.creatorInfo.found || !!root.creatorInfo.maybe)
                    implicitHeight: 24
                    implicitWidth: updRow.implicitWidth + 14
                    radius: 12
                    color: updMouse.containsMouse ? "#12324A" : "#0F2A3A"
                    border.color: "#38BDF8"
                    border.width: 1
                    Row {
                        id: updRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "🔄"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Check for new posts"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 700
                            color: "#7DD3FC"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    Springy { hover: updMouse.containsMouse; pressed: updMouse.pressed }
                    MouseArea {
                        id: updMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.checkForNewPosts()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: root.creatorInfo.found
                            ? ("See if " + (root.creatorInfo.name || "this creator") + " posted anything you don't have yet,\nand download it straight into this folder.")
                            : "See if this creator posted anything you don't have yet.\n(You'll be asked for the creator's link once.)"
                    }
                }

                // Star / Pin Current Folder Button (not for the virtual Favourites list)
                Rectangle {
                    visible: !root.inFavorites
                    implicitHeight: 24
                    implicitWidth: bkmBtnRow.implicitWidth + 12
                    radius: 4
                    color: bkmBtnMouse.containsMouse ? "#1E293B" : (root.isCurrentFolderBookmarked ? "#241D12" : "#141824")
                    border.color: root.isCurrentFolderBookmarked ? "#F59E0B" : (bkmBtnMouse.containsMouse ? "#38BDF8" : "#2E384D")
                    border.width: 1

                    Row {
                        id: bkmBtnRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            text: root.isCurrentFolderBookmarked ? "⭐" : "☆"
                            font.pixelSize: 11
                        }
                        Text {
                            text: root.isCurrentFolderBookmarked ? "Bookmarked" : "Bookmark"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: root.isCurrentFolderBookmarked ? "#F59E0B" : "#E2E8F0"
                        }
                    }
                    Springy { hover: bkmBtnMouse.containsMouse; pressed: bkmBtnMouse.pressed }
                    MouseArea {
                        id: bkmBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (!root.bridge) return
                            if (root.isCurrentFolderBookmarked) {
                                root.bridge.removeGalleryBookmark(root.currentPath)
                            } else {
                                root.bridge.addGalleryBookmark(root.currentPath, "")
                            }
                            root.refreshBookmarks()
                        }
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: root.isCurrentFolderBookmarked ? ("Bookmarked!\nClick to remove '" + root.currentPath + "' from Quick Shortcuts") : ("Bookmark Folder\nPin '" + root.currentPath + "' as a Quick Shortcut")
                    }
                }
            }
        }

        // 3. QUICK SHORTCUTS / BOOKMARKS BAR (can be hidden from the view options menu)
        Rectangle {
            Layout.fillWidth: true
            readonly property bool shown: root.showShortcutsBar
            property real reveal: shown ? 1 : 0
            Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
            implicitHeight: 28
            Layout.preferredHeight: 28 * Math.max(0, reveal)
            visible: reveal > 0.01
            opacity: Math.max(0, Math.min(1, reveal))
            clip: true
            radius: 5
            color: "#0E121B"
            border.color: "#1C2333"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                // Label
                Row {
                    spacing: 4
                    Layout.alignment: Qt.AlignVCenter
                    Text { text: "🔖"; font.pixelSize: 11 }
                    Text {
                        text: "Shortcuts:"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 700
                        color: "#64748B"
                    }
                }

                // Favourites: every starred file and folder, from any creator
                Rectangle {
                    implicitHeight: 22
                    implicitWidth: favChipRow.implicitWidth + 14
                    radius: 11
                    Layout.alignment: Qt.AlignVCenter
                    color: root.inFavorites ? "#2A2210" : (favChipMouse.containsMouse ? "#1E293D" : "#131722")
                    border.color: root.inFavorites ? "#F59E0B" : (favChipMouse.containsMouse ? "#475569" : "#222B3D")
                    border.width: 1
                    Row {
                        id: favChipRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "⭐"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Favourites"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: root.inFavorites ? 700 : Font.Normal
                            color: root.inFavorites ? "#FCD34D" : "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    Springy { hover: favChipMouse.containsMouse; pressed: favChipMouse.pressed }
                    MouseArea {
                        id: favChipMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.openFavorites()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "Favourites: everything you starred, from any folder (Ctrl+D stars the selection)"
                    }
                }
                Rectangle { width: 1; height: 14; color: "#222B3D"; Layout.alignment: Qt.AlignVCenter; visible: root.shortcutChips.length > 0 }

                // Scrollable row of bookmark chips (wheel, drag, or ‹ › arrows)
                HScrollStrip {
                    Layout.fillWidth: true
                    implicitHeight: 24
                    contentWidth: bookmarksRow.implicitWidth
                    arrowColor: "#131722"

                    Row {
                        id: bookmarksRow
                        spacing: 6
                        anchors.verticalCenter: parent.verticalCenter

                        Repeater {
                            model: root.shortcutChips
                            delegate: Rectangle {
                                id: bChip
                                property var gRoot: root
                                readonly property bool isSearch: modelData.kind === "search"
                                function removeChip() {
                                    if (isSearch) { bChip.gRoot.removeSavedSearch(modelData); return }
                                    if (bChip.gRoot && bChip.gRoot.bridge && bChip.gRoot.bridge.removeGalleryBookmark) {
                                        bChip.gRoot.bridge.removeGalleryBookmark(modelData.path)
                                        bChip.gRoot.refreshBookmarks()
                                    }
                                }
                                property bool isCurrent: {
                                    if (isSearch) return root.isCurrentSavedSearch(modelData)
                                    if (!root.currentPath || !modelData.path) return false
                                    var cp = (root.currentPath || "").toUpperCase().replace(/\\/g, "/").replace(/\/+$/, "")
                                    var mp = (modelData.path || "").toUpperCase().replace(/\\/g, "/").replace(/\/+$/, "")
                                    return cp === mp
                                }
                                implicitHeight: 22
                                implicitWidth: bChipRow.implicitWidth + 14
                                radius: 11
                                color: (bChipMouse.containsMouse || bDelMouse.containsMouse) ? "#1E293D" : (isCurrent ? "#1E273A" : "#131722")
                                border.color: isCurrent ? "#38BDF8" : ((bChipMouse.containsMouse || bDelMouse.containsMouse) ? "#475569" : "#222B3D")
                                border.width: 1

                                // Main chip mouse area (declared before bChipRow so delete button sits on top)
                                MouseArea {
                                    id: bChipMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onClicked: (mouse) => {
                                        if (mouse.button === Qt.RightButton) bChip.removeChip()
                                        else if (bChip.isSearch) bChip.gRoot.runSavedSearch(modelData)
                                        else if (bChip.gRoot && bChip.gRoot.navigateTo) bChip.gRoot.navigateTo(modelData.path)
                                    }
                                    ToolTip.visible: containsMouse && !bDelMouse.containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: bChip.isSearch
                                        ? ("Saved search: \u201c" + modelData.query + "\u201d" + (modelData.recursive ? " (with subfolders)" : "") + "\nin " + modelData.path + "\n• Click to run it\n• Right-click or '×' to remove")
                                        : ("Quick Shortcut: " + (modelData.name || "") + "\n" + (modelData.path || "") + "\n• Left-click to navigate\n• Right-click or '×' to unpin")
                                }

                                Row {
                                    id: bChipRow
                                    anchors.centerIn: parent
                                    spacing: 5

                                    Text {
                                        text: modelData.icon || "⭐"
                                        font.pixelSize: 10
                                        anchors.verticalCenter: parent.verticalCenter
                                    }

                                    Text {
                                        text: modelData.name || ""
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        font.weight: isCurrent ? 700 : Font.Normal
                                        color: isCurrent ? "#38BDF8" : ((bChipMouse.containsMouse || bDelMouse.containsMouse) ? "#F8FAFC" : "#94A3B8")
                                        anchors.verticalCenter: parent.verticalCenter
                                    }

                                    // Remove button (appears on hover)
                                    Rectangle {
                                        id: bDelBtn
                                        width: 14
                                        height: 14
                                        radius: 7
                                        color: bDelMouse.containsMouse ? "#EF4444" : "#1E2536"
                                        visible: bChipMouse.containsMouse || bDelMouse.containsMouse
                                        anchors.verticalCenter: parent.verticalCenter

                                        Text {
                                            anchors.centerIn: parent
                                            text: "×"
                                            font.pixelSize: 11
                                            font.bold: true
                                            color: bDelMouse.containsMouse ? "#FFFFFF" : "#E2E8F0"
                                        }

                                        MouseArea {
                                            id: bDelMouse
                                            anchors.fill: parent
                                            anchors.margins: -4
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: bChip.removeChip()
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 200
                                            ToolTip.text: bChip.isSearch ? ("Remove the saved search \u201c" + modelData.query + "\u201d") : ("Remove bookmark '" + (modelData.name || "") + "'")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // 4. CATEGORY PILLS & REAL-TIME SEARCH TOOLBAR
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            // Filter Pills (scroll sideways if they don't fit)
            HScrollStrip {
                Layout.fillWidth: true
                Layout.minimumWidth: 60
                implicitHeight: 26
                contentWidth: pillsRow.implicitWidth

                Row {
                    id: pillsRow
                    spacing: 6

                    // All
                    Rectangle {
                        implicitHeight: 26
                        implicitWidth: pillAllText.implicitWidth + 14
                        radius: 13
                        color: root.activeCategory === "all" ? "#38BDF8" : "#161B28"
                        Text {
                            id: pillAllText
                            anchors.centerIn: parent
                            text: "All (" + (root.recursiveActive ? root.searchResults.length : root.rawItems.length) + ")"
                            font.pixelSize: 11
                            font.weight: 600
                            color: root.activeCategory === "all" ? "#0F172A" : "#94A3B8"
                        }
                        Springy { hover: pill_allMouse.containsMouse; pressed: pill_allMouse.pressed }
                        MouseArea {

                            id: pill_allMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.activeCategory = "all"
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Show all items in this folder (" + root.rawItems.length + " total)"
                        }
                    }

                    // Folders
                    Rectangle {
                        implicitHeight: 26
                        implicitWidth: pillFoldersText.implicitWidth + 14
                        radius: 13
                        color: root.activeCategory === "folders" ? "#38BDF8" : "#161B28"
                        Text {
                            id: pillFoldersText
                            anchors.centerIn: parent
                            text: !root.showPillLabels ? ("📁 " + root.folderCount) : ("📁 Folders (" + root.folderCount + ")")
                            font.pixelSize: 11
                            font.weight: 600
                            color: root.activeCategory === "folders" ? "#0F172A" : "#94A3B8"
                        }
                        Springy { hover: pill_foldersMouse.containsMouse; pressed: pill_foldersMouse.pressed }
                        MouseArea {

                            id: pill_foldersMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.activeCategory = "folders"
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Show only subdirectories (" + root.folderCount + " folders)"
                        }
                    }

                    // Images
                    Rectangle {
                        implicitHeight: 26
                        implicitWidth: pillImgText.implicitWidth + 14
                        radius: 13
                        color: root.activeCategory === "images" ? "#EC4899" : "#161B28"
                        Text {
                            id: pillImgText
                            anchors.centerIn: parent
                            text: !root.showPillLabels ? ("🖼️ " + root.imageCount) : ("🖼️ Images (" + root.imageCount + ")")
                            font.pixelSize: 11
                            font.weight: 600
                            color: root.activeCategory === "images" ? "#FFFFFF" : "#94A3B8"
                        }
                        Springy { hover: pill_imagesMouse.containsMouse; pressed: pill_imagesMouse.pressed }
                        MouseArea {

                            id: pill_imagesMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.activeCategory = "images"
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Show only images: JPG, PNG, GIF, WebP, SVG, BMP (" + root.imageCount + " images)"
                        }
                    }

                    // Videos
                    Rectangle {
                        implicitHeight: 26
                        implicitWidth: pillVidText.implicitWidth + 14
                        radius: 13
                        color: root.activeCategory === "videos" ? "#8B5CF6" : "#161B28"
                        Text {
                            id: pillVidText
                            anchors.centerIn: parent
                            text: !root.showPillLabels ? ("🎬 " + root.videoCount) : ("🎬 Videos (" + root.videoCount + ")")
                            font.pixelSize: 11
                            font.weight: 600
                            color: root.activeCategory === "videos" ? "#FFFFFF" : "#94A3B8"
                        }
                        Springy { hover: pill_videosMouse.containsMouse; pressed: pill_videosMouse.pressed }
                        MouseArea {

                            id: pill_videosMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.activeCategory = "videos"
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Show only videos: MP4, MKV, WebM, MOV, AVI (" + root.videoCount + " videos)"
                        }
                    }

                    // Archives
                    Rectangle {
                        implicitHeight: 26
                        implicitWidth: pillArcText.implicitWidth + 14
                        radius: 13
                        color: root.activeCategory === "archives" ? "#F59E0B" : "#161B28"
                        Text {
                            id: pillArcText
                            anchors.centerIn: parent
                            text: !root.showPillLabels ? ("📦 " + root.archiveCount) : ("📦 Archives (" + root.archiveCount + ")")
                            font.pixelSize: 11
                            font.weight: 600
                            color: root.activeCategory === "archives" ? "#0F172A" : "#94A3B8"
                        }
                        Springy { hover: pill_archivesMouse.containsMouse; pressed: pill_archivesMouse.pressed }
                        MouseArea {

                            id: pill_archivesMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.activeCategory = "archives"
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Show only compressed archives: ZIP, RAR, 7Z, TAR, GZ (" + root.archiveCount + " archives)"
                        }
                    }

                    // Audio
                    Rectangle {
                        implicitHeight: 26
                        implicitWidth: pillAudText.implicitWidth + 14
                        radius: 13
                        color: root.activeCategory === "audio" ? "#10B981" : "#161B28"
                        Text {
                            id: pillAudText
                            anchors.centerIn: parent
                            text: !root.showPillLabels ? ("🎵 " + root.audioCount) : ("🎵 Audio (" + root.audioCount + ")")
                            font.pixelSize: 11
                            font.weight: 600
                            color: root.activeCategory === "audio" ? "#0F172A" : "#94A3B8"
                        }
                        Springy { hover: pill_audioMouse.containsMouse; pressed: pill_audioMouse.pressed }
                        MouseArea {

                            id: pill_audioMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.activeCategory = "audio"
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Show only audio tracks: MP3, FLAC, WAV, OGG, M4A (" + root.audioCount + " audio files)"
                        }
                    }
                }
            }

            // Group files of the same post into one stack
            Rectangle {
                implicitWidth: 28
                implicitHeight: 26
                radius: 6
                Layout.alignment: Qt.AlignVCenter
                color: root.groupByPost ? "#2E1F55" : (groupBtnMouse.containsMouse ? "#1E293B" : "#121622")
                border.color: root.groupByPost ? "#A78BFA" : (groupBtnMouse.containsMouse ? "#38BDF8" : "#252D3E")
                border.width: 1
                Text { anchors.centerIn: parent; text: "🗂"; font.pixelSize: 12; color: "#CBD5E1"; opacity: root.groupByPost ? 1.0 : 0.7 }
                Springy { hover: groupBtnMouse.containsMouse; pressed: groupBtnMouse.pressed }
                MouseArea {
                    id: groupBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.groupByPost = !root.groupByPost
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: root.groupByPost ? "Grouping files by post (click to show every file)" : "Group by post: show each post's files as one stack"
                }
            }

            // Group files by date: Today, This week, March 2025…
            Rectangle {
                implicitWidth: 28
                implicitHeight: 26
                radius: 6
                Layout.alignment: Qt.AlignVCenter
                color: root.groupByDate ? "#0F2A3A" : (dateGroupMouse.containsMouse ? "#1E293B" : "#121622")
                border.color: root.groupByDate ? "#38BDF8" : (dateGroupMouse.containsMouse ? "#38BDF8" : "#252D3E")
                border.width: 1
                Text { anchors.centerIn: parent; text: "📅"; font.pixelSize: 12; opacity: root.groupByDate ? 1.0 : 0.7 }
                Springy { hover: dateGroupMouse.containsMouse; pressed: dateGroupMouse.pressed }
                MouseArea {
                    id: dateGroupMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.groupByDate = !root.groupByDate
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: root.groupByDate ? "Grouping by date (click to turn off)" : "Group by date: Today, This week, This month, then by month"
                }
            }

            // Filter by character / series from the Known list
            Rectangle {
                id: charButton
                implicitWidth: 28
                implicitHeight: 26
                radius: 6
                Layout.alignment: Qt.AlignVCenter
                color: root.characterFilter ? "#12302A" : (charBtnMouse.containsMouse ? "#1E293B" : "#121622")
                border.color: root.characterFilter ? "#34D399" : ((charBtnMouse.containsMouse || charMenu.visible) ? "#38BDF8" : "#252D3E")
                border.width: 1
                Text { anchors.centerIn: parent; text: "👤"; font.pixelSize: 12; opacity: root.characterFilter ? 1.0 : 0.75 }
                Springy { hover: charBtnMouse.containsMouse; pressed: charBtnMouse.pressed }
                MouseArea {
                    id: charBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.startTagging()
                        var p = charButton.mapToItem(root, 0, charButton.height + 4)
                        charMenu.x = Math.max(4, Math.min(p.x, root.width - charMenu.width - 4))
                        charMenu.y = p.y
                        charMenu.open()
                    }
                    ToolTip.visible: containsMouse && !charMenu.visible
                    ToolTip.delay: 250
                    ToolTip.text: root.characterFilter ? ("Showing only " + root.characterFilter + " (click to change)") : "Filter by character or series (names from your Known list)"
                }
            }

            // Thumbnail size (grid view only); Ctrl + mouse wheel does the same
            Row {
                visible: root.showZoomSlider
                spacing: 4
                Layout.alignment: Qt.AlignVCenter
                Text { text: "▫"; font.pixelSize: 12; color: "#64748B"; anchors.verticalCenter: parent.verticalCenter }
                Slider {
                    id: zoomSlider
                    width: 80
                    height: 20
                    anchors.verticalCenter: parent.verticalCenter
                    from: 120
                    to: 320
                    stepSize: 8
                    value: root.thumbSize
                    onMoved: root.setThumbSize(value)
                    background: Rectangle {
                        x: zoomSlider.leftPadding
                        y: zoomSlider.topPadding + zoomSlider.availableHeight / 2 - height / 2
                        width: zoomSlider.availableWidth
                        height: 4
                        radius: 2
                        color: "#1E2536"
                        Rectangle {
                            width: zoomSlider.visualPosition * parent.width
                            height: parent.height
                            radius: 2
                            color: "#38BDF8"
                        }
                    }
                    handle: Rectangle {
                        x: zoomSlider.leftPadding + zoomSlider.visualPosition * (zoomSlider.availableWidth - width)
                        y: zoomSlider.topPadding + zoomSlider.availableHeight / 2 - height / 2
                        width: 12
                        height: 12
                        radius: 6
                        color: zoomSlider.pressed ? "#7DD3FC" : "#E2E8F0"
                        border.color: "#38BDF8"
                    }
                    ToolTip.visible: hovered || pressed
                    ToolTip.delay: 300
                    ToolTip.text: "Thumbnail size (Ctrl + mouse wheel works too)"
                }
                Text { text: "◻"; font.pixelSize: 14; color: "#64748B"; anchors.verticalCenter: parent.verticalCenter }
            }

            // Sort control
            Rectangle {
                id: sortButton
                implicitHeight: 28
                implicitWidth: sortBtnRow.implicitWidth + 16
                radius: 6
                color: sortBtnMouse.containsMouse ? "#1E293B" : "#121622"
                border.color: (sortBtnMouse.containsMouse || sortMenu.visible) ? "#38BDF8" : "#252D3E"
                border.width: 1

                Row {
                    id: sortBtnRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text { text: "⇅"; font.pixelSize: 11; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: (root.showSortLabel ? root.sortLabel(root.sortKey) + "  " : "") + (root.sortAscending ? "▲" : "▼")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#E2E8F0"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                Springy { hover: sortBtnMouse.containsMouse; pressed: sortBtnMouse.pressed }
                MouseArea {
                    id: sortBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        var p = sortButton.mapToItem(root, 0, sortButton.height + 4)
                        sortMenu.x = Math.max(4, Math.min(p.x, root.width - sortMenu.width - 4))
                        sortMenu.y = p.y
                        sortMenu.open()
                    }
                    ToolTip.visible: containsMouse && !sortMenu.visible
                    ToolTip.delay: 300
                    ToolTip.text: "Sort Order\nSorted by " + root.sortLabel(root.sortKey).toLowerCase() + (root.sortAscending ? " (ascending)" : " (descending)") + ".\nFolders always stay on top. Click to change."
                }
            }

            // Search input
            Rectangle {
                implicitHeight: 28
                implicitWidth: root.searchBoxWidth
                radius: 6
                color: "#121622"
                border.color: searchInput.activeFocus ? "#38BDF8" : "#252D3E"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 6

                    Text { text: "🔍"; font.pixelSize: 11 }
                    TextInput {
                        id: searchInput
                        Layout.fillWidth: true
                        color: "#F8FAFC"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        selectByMouse: true
                        clip: true
                        onTextChanged: root.searchFilter = text
                        Keys.onDownPressed: root.focusBrowser()
                        Keys.onEscapePressed: root.focusBrowser()

                        Text {
                            visible: !searchInput.text && !searchInput.activeFocus
                            text: root.searchSubfolders ? "Search all subfolders…  (.png, .mp4)" : "Search this folder…  (.png, .mp4)"
                            color: "#64748B"
                            font.pixelSize: 11
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    // Toggle: also search inside subfolders
                    Rectangle {
                        visible: !!root.tools
                        implicitWidth: 22
                        implicitHeight: 18
                        radius: 4
                        color: root.searchSubfolders ? "#2E1F55" : (subToggleMouse.containsMouse ? "#1E293B" : "transparent")
                        border.color: root.searchSubfolders ? "#A78BFA" : "transparent"
                        border.width: 1
                        Text { anchors.centerIn: parent; text: "🗂"; font.pixelSize: 10; color: "#CBD5E1"; opacity: root.searchSubfolders ? 1.0 : 0.6 }
                        MouseArea {
                            id: subToggleMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.searchSubfolders = !root.searchSubfolders
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: root.searchSubfolders ? "Searching subfolders too (click to search only this folder)" : "Also search inside all subfolders"
                        }
                    }
                    // Save this search to the Shortcuts bar
                    Rectangle {
                        visible: searchInput.text.trim().length > 0 && !root.inFavorites
                        implicitWidth: 22
                        implicitHeight: 18
                        radius: 4
                        color: root.currentSearchSaved ? "#2A2210" : (pinMouse.containsMouse ? "#1E293B" : "transparent")
                        border.color: root.currentSearchSaved ? "#F59E0B" : (pinMouse.containsMouse ? "#475569" : "transparent")
                        Text { anchors.centerIn: parent; text: "📌"; font.pixelSize: 10; opacity: root.currentSearchSaved ? 1.0 : 0.75 }
                        MouseArea {
                            id: pinMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.toggleSaveSearch()
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: root.currentSearchSaved ? "Saved in your Shortcuts bar (click to remove)" : "Save this search to the Shortcuts bar"
                        }
                    }
                    Text {
                        visible: searchInput.text.length > 0
                        text: "✕"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                searchInput.text = ""
                                root.searchFilter = ""
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Clear search filter"
                        }
                    }
                }
            }
        }

        // PRIVACY BANNER (while the blur is on)
        Rectangle {
            Layout.fillWidth: true
            readonly property bool shown: root.privacyBlur
            property real reveal: shown ? 1 : 0
            Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
            implicitHeight: 30
            Layout.preferredHeight: 30 * Math.max(0, reveal)
            visible: reveal > 0.01
            opacity: Math.max(0, Math.min(1, reveal))
            clip: true
            radius: 6
            color: "#2A2210"
            border.color: "#F59E0B"
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 6
                spacing: 8
                Text { text: "🙈"; font.pixelSize: 13 }
                Text {
                    Layout.fillWidth: true
                    text: "Privacy blur is on: thumbnails and previews are hidden."
                    elide: Text.ElideRight
                    font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.weight: 600; color: "#FDE68A"
                }
                ActionChip {
                    icon: "👁"; label: "Show them"
                    tip: "Turn the privacy blur off (Ctrl+H)"
                    onTriggered: root.togglePrivacy()
                }
            }
        }

        // 4a. OPEN POST BAR (while looking inside a grouped post)
        Rectangle {
            Layout.fillWidth: true
            readonly property bool shown: root.openGroupKey.length > 0
            property real reveal: shown ? 1 : 0
            Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
            implicitHeight: 30
            Layout.preferredHeight: 30 * Math.max(0, reveal)
            visible: reveal > 0.01
            opacity: Math.max(0, Math.min(1, reveal))
            clip: true
            radius: 6
            color: "#1A1430"
            border.color: "#A78BFA"
            border.width: 1
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 6
                anchors.rightMargin: 10
                spacing: 8
                ActionChip {
                    icon: "◂"; label: "All posts"
                    tip: "Back to all posts (Backspace)"
                    onTriggered: root.closeGroup()
                }
                Text {
                    Layout.fillWidth: true
                    text: "🗂 " + root.openGroupTitle + "  •  " + root.filteredItems.length + " files  •  post " + root.openGroupKey
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#DDD6FE"
                    elide: Text.ElideRight
                }
            }
        }

        // 4a2. CHARACTER FILTER BAR
        Rectangle {
            Layout.fillWidth: true
            readonly property bool shown: root.characterFilter.length > 0
            property real reveal: shown ? 1 : 0
            Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
            implicitHeight: 30
            Layout.preferredHeight: 30 * Math.max(0, reveal)
            visible: reveal > 0.01
            opacity: Math.max(0, Math.min(1, reveal))
            clip: true
            radius: 6
            color: "#0F2A22"
            border.color: "#34D399"
            border.width: 1
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 6
                spacing: 8
                Text {
                    Layout.fillWidth: true
                    text: "👤 " + root.characterFilter + "  •  " + root.shownItemCount + (root.shownItemCount === 1 ? " file" : " files")
                          + (root.tagging ? "  •  still scanning names…" : "")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#A7F3D0"
                    elide: Text.ElideRight
                }
                ActionChip {
                    icon: "✕"; label: "Clear filter"
                    tip: "Show every file again"
                    onTriggered: root.setCharacterFilter("")
                }
            }
        }

        // 4b. SELECTION ACTION BAR (visible while items are selected)
        // Left: what's selected + selection links. Right, grouped: organize | archive | More, Delete.
        Rectangle {
            Layout.fillWidth: true
            readonly property bool shown: root.selectionCount > 0
            property real reveal: shown ? 1 : 0
            Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
            implicitHeight: 34
            Layout.preferredHeight: 34 * Math.max(0, reveal)
            visible: reveal > 0.01
            opacity: Math.max(0, Math.min(1, reveal))
            clip: true
            radius: 6
            color: "#112033"
            border.color: "#38BDF8"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 6
                spacing: 6

                Text {
                    text: "☑ " + root.selectionCount + (root.showSelectedWord ? " selected" : "")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 700
                    color: "#38BDF8"
                }
                Text {
                    readonly property real selSize: root.selectionCount > 0 ? root.totalSize(root.selectedItems()) : 0
                    visible: selSize > 0 && root.showSelSize
                    text: "·  " + root.formatBytes(selSize)
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#94A3B8"
                }

                // Selection links sit with the count they change
                Row {
                    visible: root.showSelLinks
                    spacing: 12
                    Layout.leftMargin: 8
                    SelLink { label: "Select all"; tip: "Select every item shown (Ctrl+A)"; onTriggered: root.selectAll() }
                    SelLink { label: "Clear"; tip: "Clear the selection (Esc)"; onTriggered: root.clearSelection() }
                }

                Item { Layout.fillWidth: true }

                // Organize
                ActionChip {
                    compact: !root.showChipLabels
                    icon: "→"; label: "Move to…"
                    tip: "Move the selected items into another folder. Existing files are never overwritten."
                    onTriggered: root.moveItemsToFolder(root.selectedItems())
                }
                ActionChip {
                    compact: !root.showChipLabels
                    visible: !!root.archiver
                    icon: "⧉"; label: "Copy to…"
                    tip: "Copy the selected items into another folder. Existing files are never overwritten."
                    onTriggered: root.copyItemsToFolder(root.selectedItems())
                }

                BarDivider { visible: !!root.archiver }

                // Archive
                ActionChip {
                    compact: !root.showChipLabels
                    visible: !!root.archiver && root.selectionHasArchive
                    icon: "⊟"; label: "Extract"
                    tip: "Extract the selected archives (ZIP, 7Z, RAR, TAR…), each into its own folder"
                    onTriggered: root.extractItems(root.selectedItems(), false)
                }
                ActionChip {
                    compact: !root.showChipLabels
                    visible: !!root.archiver
                    icon: "⊞"; label: "Compress"
                    tip: "Pack the selected files and folders into a ZIP or 7Z archive, or one archive per item"
                    onTriggered: root.compressItems(root.selectedItems())
                }

                BarDivider {}

                // Everything else, then the one destructive action on its own
                ActionChip {
                    id: moreChip
                    compact: !root.showChipLabels
                    icon: "⋯"; label: "More"
                    tip: "Open, show in Explorer, copy path, rename…"
                    onTriggered: root.openMoreMenu(moreChip)
                }
                ActionChip {
                    compact: !root.showChipLabels
                    icon: "🗑"; label: "Delete"; danger: true
                    tip: "Move the selected items to the Recycle Bin (Delete key). You can restore them from there."
                    onTriggered: root.deleteItems(root.selectedItems())
                }
            }
        }

        // 5. VIRTUALIZED FILE & FOLDER BROWSER
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 8
            color: "#0D1018"
            border.color: "#1E2536"
            border.width: 1
            clip: true

            // Files dropped from Explorer onto empty space are copied into this folder
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

            // Empty state placeholder
            Item {
                anchors.centerIn: parent
                visible: root.filteredItems.length === 0
                ColumnLayout {
                    spacing: 8
                    anchors.centerIn: parent
                    Text {
                        text: "📭"
                        font.pixelSize: 32
                        Layout.alignment: Qt.AlignHCenter
                    }
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

            // GRID VIEW
            GridView {
                id: explorerGridView
                visible: root.viewMode === "grid"
                anchors.fill: parent
                anchors.margins: 10
                // Stretch cells so each row fills the full width (target = thumbSize per card)
                cellWidth: Math.floor(width / Math.max(1, Math.floor(width / root.thumbSize)))
                readonly property int previewHeight: Math.max(70, Math.round((cellWidth - 18) * 0.62))
                cellHeight: previewHeight + 68
                model: root.filteredItems
                clip: true
                cacheBuffer: 600
                focus: root.viewMode === "grid"
                keyNavigationEnabled: true
                currentIndex: -1
                highlightFollowsCurrentItem: false
                onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, GridView.Contain)
                Keys.onPressed: (event) => root.handleBrowserKey(explorerGridView, event)
                // Clicking empty space clears the selection (like File Explorer). Cards take their own
                // clicks, so this only sees presses that land between or below them.
                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    onTapped: { root.clearSelection(); root.focusBrowser() }
                }

                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                // Cards flow in with a short stagger when a folder opens
                property Transition flowIn: Transition { id: gridFlowIn
                    SequentialAnimation {
                        PropertyAction { property: "opacity"; value: 0 }
                        PauseAnimation { duration: Math.max(0, Math.min(gridFlowIn.ViewTransition.index, 28)) * 14 }   // per-item stagger (index is -1 outside a run)
                        ParallelAnimation {
                            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 230; easing.type: Easing.OutCubic }
                            SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 }
                        }
                    }
                }
                populate: root.animatePopulate ? flowIn : null

                // Ctrl + mouse wheel resizes thumbnails
                WheelHandler {
                    acceptedModifiers: Qt.ControlModifier
                    onWheel: (event) => root.setThumbSize(root.thumbSize + (event.angleDelta.y > 0 ? 16 : -16))
                }
                // Plain wheel: accelerated, size-aware scrolling
                WheelHandler {
                    acceptedModifiers: Qt.NoModifier
                    onWheel: (event) => root.wheelScroll(explorerGridView, gridScrollAnim, event, explorerGridView.cellHeight, 1)
                }
                NumberAnimation { id: gridScrollAnim; target: explorerGridView; property: "contentY"; duration: 160; easing.type: Easing.OutCubic }

                delegate: Item {
                    id: gridCell
                    readonly property var info: { root.statsRev; var st = modelData.is_dir ? root.folderStats[modelData.path] : undefined; return st ? root.withFolderStats(modelData, st) : modelData }   // folder sizes update in place
                    width: explorerGridView.cellWidth
                    height: explorerGridView.cellHeight
                    readonly property bool isSel: root.selectedPaths[modelData.path] === true
                    readonly property bool isKeyFocus: root.keyboardNav && GridView.isCurrentItem && explorerGridView.activeFocus
                    readonly property bool spacer: !!modelData.is_header || !!modelData.is_filler
                    readonly property bool dropHover: gridFolderDrop.containsDrag
                    readonly property string cat: modelData.is_dir ? "folder" : root.getCategory(modelData.ext)
                    // Images via Qt; videos via the Windows thumbnail cache (falls back to the icon)
                    readonly property bool hasThumb: cat === "image" || cat === "video" || (!!modelData.is_group && !!modelData.cover)
                    // Post stacks fan out a little when hovered
                    property real spread: (modelData.is_group && gridCardMouse.containsMouse) ? 1.8 : 1.0
                    Behavior on spread { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }

                    // Two offset "cards" behind a post stack
                    Repeater {
                        model: modelData.is_group ? 2 : 0
                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 4
                            anchors.leftMargin: 4 + (2 - index) * 4 * gridCell.spread
                            anchors.topMargin: 4 - (2 - index) * 3 * gridCell.spread
                            anchors.rightMargin: 4 - (2 - index) * 4 * gridCell.spread
                            anchors.bottomMargin: 4 + (2 - index) * 3 * gridCell.spread
                            radius: 8
                            color: index === 0 ? "#1A1430" : "#211A3A"
                            border.color: "#3B2F66"
                            border.width: 1
                        }
                    }

                    Rectangle {
                        visible: !gridCell.spacer
                        id: gridCard
                        anchors.fill: parent
                        anchors.margins: 4
                        radius: 8
                        color: gridCell.isSel ? "#16243A" : (gridCardMouse.containsMouse ? "#1A2234" : "#131824")
                        border.color: gridCell.dropHover ? "#34D399" : (gridCell.isKeyFocus ? "#F8FAFC" : (gridCell.isSel ? "#38BDF8" : (gridCardMouse.containsMouse ? getItemColor(modelData) : "#20283A")))
                        border.width: (gridCell.isSel || gridCell.isKeyFocus || gridCell.dropHover) ? 2 : 1

                        Springy { hover: gridCardMouse.containsMouse; pressed: gridCardMouse.pressed }
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 120 } }

                        // Preview area: real thumbnail for images, large icon otherwise
                        Rectangle {
                            id: previewArea
                            anchors.top: parent.top
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.margins: 5
                            height: explorerGridView.previewHeight
                            radius: 6
                            color: "#0D121C"
                            clip: true

                            Image {
                                id: thumbImage
                                anchors.fill: parent
                                // The provider returns a 1x1 placeholder when there's no thumbnail
                                visible: status === Image.Ready && implicitWidth > 1
                                opacity: visible ? 1 : 0
                                Behavior on opacity { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
                                source: gridCell.hasThumb ? root.thumbUrl(modelData.is_group ? modelData.cover : modelData) : ""
                                asynchronous: true
                                cache: true
                                smooth: true
                                fillMode: Image.PreserveAspectCrop
                                // Privacy blur: drawn through a tiny texture, so only soft colours remain
                                layer.enabled: root.privacyBlur
                                layer.textureSize: Qt.size(12, 9)
                                layer.smooth: true
                            }
                            Rectangle {
                                anchors.fill: parent
                                visible: root.privacyBlur && gridCell.hasThumb
                                color: "#59101622"
                                Text { anchors.centerIn: parent; text: "🙈"; font.pixelSize: 22; opacity: 0.8 }
                            }

                            // Animated pictures play while hovered (stills show nothing extra)
                            Loader {
                                anchors.fill: parent
                                active: gridCell.cat === "image" && gridCardMouse.containsMouse && !hoverPlayDelay.running && !root.internalDragActive && !root.privacyBlur
                                sourceComponent: AnimatedMedia {
                                    path: modelData.path
                                    tools: root.tools
                                    fillMode: Image.PreserveAspectCrop
                                }
                            }

                            // Muted looping preview while a video card is hovered (only the hovered card plays)
                            Timer {
                                id: hoverPlayDelay
                                interval: 450
                                running: (gridCell.cat === "video" || gridCell.cat === "image") && gridCardMouse.containsMouse && !root.internalDragActive
                            }
                            Loader {
                                id: hoverVideo
                                anchors.fill: parent
                                active: gridCell.cat === "video" && gridCardMouse.containsMouse && !hoverPlayDelay.running && !root.internalDragActive && !root.privacyBlur
                                sourceComponent: Item {
                                    MediaPlayer {
                                        id: previewPlayer
                                        source: root._urlFor(modelData.path)
                                        videoOutput: previewOutput
                                        loops: MediaPlayer.Infinite
                                        Component.onCompleted: play()
                                        Component.onDestruction: stop()
                                    }
                                    VideoOutput {
                                        id: previewOutput
                                        anchors.fill: parent
                                        fillMode: VideoOutput.PreserveAspectCrop
                                    }
                                }
                            }

                            Text {
                                anchors.centerIn: parent
                                visible: !thumbImage.visible
                                text: getItemIcon(modelData)
                                font.pixelSize: 34
                                opacity: thumbImage.status === Image.Loading ? 0.35 : 0.9
                            }

                            // Favourite star
                            Rectangle {
                                readonly property bool on: root.isFavorite(modelData)
                                visible: opacity > 0.01
                                opacity: on ? 1 : 0
                                scale: on ? 1 : 0.2
                                Behavior on opacity { NumberAnimation { duration: 120 } }
                                Behavior on scale { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.001 } }
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.topMargin: 5
                                anchors.leftMargin: 30
                                width: 20; height: 20; radius: 10
                                color: "#CC0B0E17"
                                border.color: "#F59E0B"
                                border.width: 1
                                Text { anchors.centerIn: parent; text: "★"; font.pixelSize: 11; color: "#FBBF24" }
                            }

                            // File count badge on post stacks
                            Rectangle {
                                visible: !!modelData.is_group
                                anchors.left: parent.left
                                anchors.bottom: parent.bottom
                                anchors.margins: 5
                                implicitHeight: 18
                                implicitWidth: stackCount.implicitWidth + 12
                                radius: 4
                                color: "#E6241B44"
                                border.color: "#A78BFA"
                                border.width: 1
                                Text {
                                    id: stackCount
                                    anchors.centerIn: parent
                                    text: "🗂 " + (gridCell.info.file_count || 0)
                                    font.pixelSize: 9
                                    font.weight: 700
                                    color: "#EDE9FE"
                                }
                            }

                            // Play badge for videos
                            Rectangle {
                                visible: gridCell.cat === "video"
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.margins: 5
                                width: 20; height: 20; radius: 10
                                color: "#CC0B0E17"
                                Text { anchors.centerIn: parent; anchors.horizontalCenterOffset: 1; text: "▶"; font.pixelSize: 9; color: "#E2E8F0" }
                            }

                            // Size / item-count badge
                            Rectangle {
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: 5
                                implicitHeight: 16
                                implicitWidth: sizeText.implicitWidth + 10
                                radius: 4
                                color: "#CC0B0E17"
                                border.color: modelData.is_dir ? (gridCell.info.size >= 0 ? "#38BDF8" : "#25334D") : "transparent"
                                border.width: modelData.is_dir ? 1 : 0
                                Text {
                                    id: sizeText
                                    anchors.centerIn: parent
                                    text: formatFolderSize(gridCell.info)
                                    font.pixelSize: 9
                                    font.weight: modelData.is_dir ? 600 : Font.Normal
                                    color: modelData.is_dir ? (gridCell.info.size >= 0 ? "#38BDF8" : "#94A3B8") : "#CBD5E1"
                                }
                            }
                        }

                        Text {
                            id: gridName
                            anchors.top: previewArea.bottom
                            anchors.topMargin: 5
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            text: modelData.name || ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: modelData.is_dir ? 600 : Font.Normal
                            color: modelData.is_dir ? "#38BDF8" : "#E2E8F0"
                            elide: Text.ElideMiddle
                            maximumLineCount: 2
                            wrapMode: Text.WrapAnywhere
                        }

                        Text {
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 6
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            text: (root.ratingOf(modelData) > 0 ? root.starText(root.ratingOf(modelData)) + "  " : "")
                                  + (modelData.is_group ? (gridCell.info.file_count + " files • post " + modelData.group_key)
                                  : (modelData.rel_dir ? ("📁 " + root.displayDir(modelData.rel_dir)) : formatFolderSubtitle(gridCell.info)))
                            font.pixelSize: 9
                            color: modelData.is_dir ? (gridCell.info.size >= 0 ? "#38BDF8" : "#818CF8") : "#64748B"
                            elide: Text.ElideRight
                        }
                    }

                    // Invisible handle the MouseArea drags; Qt turns it into a system file drag
                    Item {
                        id: gridDragItem
                        width: 1
                        height: 1
                        Drag.dragType: Drag.Automatic
                        // Copy only: other apps (Explorer, Discord…) get copies and can never move files out
                        // behind the gallery's back. Drops onto gallery folders are moved by handleDrop().
                        Drag.supportedActions: Qt.CopyAction
                        Drag.proposedAction: Qt.CopyAction
                        Drag.mimeData: gridCell.isSel ? root.selectionMime : root.mimeForItems(modelData.is_group ? modelData.members : [modelData])
                        Drag.imageSource: root.dragImageFor(modelData)
                        Drag.active: gridCardMouse.drag.active
                        Drag.onDragStarted: root.beginDrag(modelData)
                        Drag.onDragFinished: { root.endDrag(); x = 0; y = 0 }
                    }

                    // Folders accept drops: gallery items are moved in, files from Explorer are copied in
                    DropArea {
                        id: gridFolderDrop
                        anchors.fill: parent
                        enabled: !!modelData.is_dir
                        keys: ["text/uri-list"]
                        onDropped: (drop) => root.handleDrop(drop, modelData.path)
                    }

                    MouseArea {
                        enabled: !gridCell.spacer
                        id: gridCardMouse
                        anchors.fill: parent
                        anchors.margins: 4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        drag.target: gridDragItem
                        drag.threshold: 12
                        preventStealing: true
                        onClicked: (mouse) => {
                            if (mouse.button === Qt.RightButton) {
                                root.showContextMenu(modelData, index, gridCardMouse, mouse.x, mouse.y)
                            } else {
                                root.handleItemClick(modelData, index, mouse)
                            }
                        }
                        onDoubleClicked: (mouse) => {
                            if (mouse.button === Qt.LeftButton) root.handleItemDoubleClick(modelData)
                        }
                        ToolTip.visible: containsMouse && !gridCheckMouse.containsMouse
                        ToolTip.delay: 450
                        ToolTip.text: {
                            if (modelData.is_group)
                                return "🗂 " + modelData.name + "\n" + gridCell.info.file_count + " files from post " + modelData.group_key
                                    + "\n• Double-click to open the post's files\n• Right-click for actions on all its files"
                            var tip = (modelData.is_dir ? "📁 " : "📄 ") + (modelData.name || "")
                            if (modelData.is_dir) {
                                tip += "\n" + root.formatFolderSubtitle(gridCell.info)
                                tip += "\n• Double-click to open folder"
                            } else {
                                tip += "\nSize: " + root.formatBytes(gridCell.info.size) + "\nModified: " + root.formatDate(modelData.mtime)
                                if (root.isMedia(modelData)) {
                                    tip += "\n• Double-click to preview in Lightbox"
                                } else {
                                    tip += "\n• Double-click to open in default app"
                                }
                            }
                            tip += "\n• Click to select, Ctrl+click or tick the box to add more, Shift+click for a range\n• Type a name to jump to it"
                            tip += "\n• Right-click for more actions"
                            return tip
                        }
                    }

                    // Selection checkbox (declared after the card MouseArea so it receives clicks first)
                    Rectangle {
                        id: gridCheck
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.topMargin: 12
                        anchors.leftMargin: 12
                        width: 18; height: 18; radius: 4
                        readonly property bool shown: gridCell.isSel || gridCardMouse.containsMouse || gridCheckMouse.containsMouse || root.selectionCount > 0
                        visible: (!gridCell.spacer) && (opacity > 0.01)
                        opacity: shown ? 1 : 0
                        scale: gridCell.isSel ? 1.0 : (gridCheckMouse.containsMouse ? 1.12 : (shown ? 0.92 : 0.6))
                        Behavior on opacity { NumberAnimation { duration: 120 } }
                        Behavior on scale { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.001 } }
                        color: gridCell.isSel ? "#38BDF8" : "#CC0B0E17"
                        border.color: gridCell.isSel ? "#38BDF8" : (gridCheckMouse.containsMouse ? "#38BDF8" : "#94A3B8")
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            opacity: gridCell.isSel ? 1 : 0
                            scale: gridCell.isSel ? 1 : 0.2
                            Behavior on scale { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.001 } }
                            Behavior on opacity { NumberAnimation { duration: 90 } }
                            text: "✓"
                            font.pixelSize: 12
                            font.weight: 800
                            color: "#0F172A"
                        }
                        MouseArea {
                            id: gridCheckMouse
                            anchors.fill: parent
                            anchors.margins: -3
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: (mouse) => {
                                if ((mouse.modifiers & Qt.ShiftModifier) !== 0) {
                                    root.selectRange(root.selectionAnchor >= 0 ? root.selectionAnchor : index, index, true)
                                } else {
                                    root.toggleSelection(modelData.path)
                                    root.selectionAnchor = index
                                }
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: gridCell.isSel ? "Deselect" : "Select"
                        }
                    }

                    // Group by date: the tile that opens each section (click = select the section)
                    Rectangle {
                        visible: !!modelData.is_header
                        anchors.fill: parent
                        anchors.margins: 4
                        radius: 10
                        color: tileMouse.containsMouse ? "#16233A" : "#0F1726"
                        border.color: gridCell.isKeyFocus ? "#F8FAFC" : (tileMouse.containsMouse ? "#38BDF8" : "#24324A")
                        border.width: gridCell.isKeyFocus ? 2 : 1
                        Springy { hover: tileMouse.containsMouse; pressed: tileMouse.pressed }
                        Column {
                            anchors.centerIn: parent
                            width: parent.width - 20
                            spacing: 6
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.icon || "📅"; font.pixelSize: 26 }
                            Text {
                                width: parent.width
                                horizontalAlignment: Text.AlignHCenter
                                text: modelData.name || ""
                                wrapMode: Text.WordWrap
                                font.family: "Segoe UI, sans-serif"; font.pixelSize: 16; font.weight: 700; color: "#F1F5F9"
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: (modelData.count || 0) + ((modelData.count || 0) === 1 ? " item" : " items")
                                font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; color: "#94A3B8"
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: "Click to select all"
                                opacity: tileMouse.containsMouse ? 1 : 0
                                Behavior on opacity { NumberAnimation { duration: 150 } }
                                font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; color: "#38BDF8"
                            }
                        }
                        MouseArea {
                            id: tileMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: (mouse) => root.handleItemClick(modelData, index, mouse)
                        }
                    }
                }
            }

            // LIST VIEW CONTAINER
            Item {
                id: listContainer
                visible: root.viewMode === "list"
                anchors.fill: parent
                anchors.margins: 6

                // Column Header
                Rectangle {
                    id: listHeader
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 22
                    color: "transparent"

                    SortHeader {
                        anchors.left: parent.left
                        anchors.leftMargin: 52
                        anchors.verticalCenter: parent.verticalCenter
                        width: 200
                        gallery: root
                        label: "NAME"
                        sortKeyName: "name"
                        alignRight: false
                    }

                    Row {
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 12

                        SortHeader { gallery: root; width: 130; visible: root.showTypeColumn; label: "ITEMS / TYPE"; sortKeyName: "type" }
                        SortHeader { gallery: root; width: 85; label: "SIZE"; sortKeyName: "size" }
                        SortHeader { gallery: root; width: 140; label: "DATE MODIFIED"; sortKeyName: "date" }
                    }

                    Rectangle {
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 1
                        color: "#1E2536"
                    }
                }

                ListView {
                    id: explorerListView
                    focus: root.viewMode === "list"
                    keyNavigationEnabled: true
                    currentIndex: -1
                    highlightFollowsCurrentItem: false
                    onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)
                    Keys.onPressed: (event) => root.handleBrowserKey(explorerListView, event)
                    // Clicking empty space clears the selection (like File Explorer). Cards take their own
                    // clicks, so this only sees presses that land between or below them.
                    TapHandler {
                        acceptedButtons: Qt.LeftButton
                        onTapped: { root.clearSelection(); root.focusBrowser() }
                    }
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    property Transition flowIn: Transition { id: listFlowIn
                    SequentialAnimation {
                        PropertyAction { property: "opacity"; value: 0 }
                        PauseAnimation { duration: Math.max(0, Math.min(listFlowIn.ViewTransition.index, 28)) * 14 }   // per-item stagger (index is -1 outside a run)
                        ParallelAnimation {
                            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 230; easing.type: Easing.OutCubic }
                            SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 }
                        }
                    }
                }
                    populate: root.animatePopulate ? flowIn : null
                    WheelHandler {
                        acceptedModifiers: Qt.NoModifier
                        onWheel: (event) => root.wheelScroll(explorerListView, listScrollAnim, event, 34, 3)
                    }
                    NumberAnimation { id: listScrollAnim; target: explorerListView; property: "contentY"; duration: 160; easing.type: Easing.OutCubic }
                    anchors.top: listHeader.bottom
                    anchors.topMargin: 4
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    spacing: 2
                    model: root.filteredItems
                    clip: true

                    delegate: Rectangle {
                        id: listRow
                        readonly property var info: { root.statsRev; var st = modelData.is_dir ? root.folderStats[modelData.path] : undefined; return st ? root.withFolderStats(modelData, st) : modelData }   // folder sizes update in place
                        readonly property bool isSel: root.selectedPaths[modelData.path] === true
                        readonly property bool isKeyFocus: root.keyboardNav && ListView.isCurrentItem && explorerListView.activeFocus
                        readonly property bool spacer: !!modelData.is_header || !!modelData.is_filler
                        readonly property bool dropHover: listFolderDrop.containsDrag
                        transform: Translate {
                            x: listRowMouse.containsMouse ? 3 : 0
                            Behavior on x { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
                        }
                        width: explorerListView.width
                        height: 32
                        radius: 5
                        color: isSel ? "#16243A" : (listRowMouse.containsMouse ? "#1B2336" : (index % 2 === 0 ? "#111622" : "#0E121B"))
                        border.color: dropHover ? "#34D399" : (isKeyFocus ? "#F8FAFC" : ((isSel || listRowMouse.containsMouse) ? "#38BDF8" : "transparent"))
                        border.width: 1

                        Text {
                            visible: !listRow.spacer
                            id: rowIcon
                            anchors.left: parent.left
                            anchors.leftMargin: 30
                            anchors.verticalCenter: parent.verticalCenter
                            text: getItemIcon(modelData)
                            font.pixelSize: 14
                        }

                        // Right-side columns (Fixed width, right aligned, strict spacing)
                        Row {
                            visible: !listRow.spacer
                            id: rightCols
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 12

                            // Files / Child count column
                            Text {
                                width: 130
                                visible: root.showTypeColumn
                                anchors.verticalCenter: parent.verticalCenter
                                text: {
                                    if (modelData.is_dir) {
                                        if (listRow.info.file_count >= 0) {
                                            var cnt = listRow.info.file_count + (listRow.info.file_count === 1 ? " file" : " files")
                                            if (listRow.info.folder_count > 0) {
                                                cnt += " (" + listRow.info.folder_count + " dirs)"
                                            }
                                            return cnt
                                        }
                                        return modelData.child_count + (modelData.child_count === 1 ? " item" : " items")
                                    }
                                    if (modelData.is_group) return listRow.info.file_count + " files (post)"
                                    return modelData.ext ? modelData.ext.toUpperCase() : "FILE"
                                }
                                font.family: "Segoe UI, monospace"
                                font.pixelSize: 10
                                font.weight: modelData.is_dir ? 600 : Font.Normal
                                color: modelData.is_dir ? "#A78BFA" : "#64748B"
                                horizontalAlignment: Text.AlignRight
                                elide: Text.ElideRight
                            }

                            // Size column
                            Text {
                                width: 85
                                anchors.verticalCenter: parent.verticalCenter
                                text: formatFolderSize(listRow.info)
                                font.family: "Segoe UI, monospace"
                                font.pixelSize: 10
                                font.weight: (modelData.is_dir && listRow.info.size >= 0) ? 600 : Font.Normal
                                color: modelData.is_dir ? (listRow.info.size >= 0 ? "#38BDF8" : "#818CF8") : "#94A3B8"
                                horizontalAlignment: Text.AlignRight
                                elide: Text.ElideRight
                            }

                            // Date Modified column
                            Text {
                                width: 140
                                anchors.verticalCenter: parent.verticalCenter
                                text: formatDate(modelData.mtime)
                                font.family: "Segoe UI, monospace"
                                font.pixelSize: 10
                                color: "#64748B"
                                horizontalAlignment: Text.AlignRight
                                elide: Text.ElideRight
                            }
                        }

                        // Filename fills between icon and right columns
                        Text {
                            visible: !listRow.spacer
                            anchors.left: rowIcon.right
                            anchors.leftMargin: 10
                            anchors.right: rightCols.left
                            anchors.rightMargin: 16
                            anchors.verticalCenter: parent.verticalCenter
                            text: (root.isFavorite(modelData) ? "★ " : "") + (root.ratingOf(modelData) > 0 ? "[" + root.ratingOf(modelData) + "★] " : "")
                                  + (modelData.rel_dir ? (root.displayDir(modelData.rel_dir) + "  ›  " + modelData.name) : (modelData.name || ""))
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: modelData.is_dir ? 600 : Font.Normal
                            color: modelData.is_dir ? "#38BDF8" : "#E2E8F0"
                            elide: Text.ElideMiddle
                        }

                        Item {
                            id: listDragItem
                            width: 1
                            height: 1
                            Drag.dragType: Drag.Automatic
                            Drag.supportedActions: Qt.CopyAction
                            Drag.proposedAction: Qt.CopyAction
                            Drag.mimeData: listRow.isSel ? root.selectionMime : root.mimeForItems(modelData.is_group ? modelData.members : [modelData])
                            Drag.imageSource: root.dragImageFor(modelData)
                            Drag.active: listRowMouse.drag.active
                            Drag.onDragStarted: root.beginDrag(modelData)
                            Drag.onDragFinished: { root.endDrag(); x = 0; y = 0 }
                        }

                        DropArea {
                            id: listFolderDrop
                            anchors.fill: parent
                            enabled: !!modelData.is_dir
                            keys: ["text/uri-list"]
                            onDropped: (drop) => root.handleDrop(drop, modelData.path)
                        }

                        MouseArea {
                            enabled: !listRow.spacer
                            id: listRowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            drag.target: listDragItem
                            drag.threshold: 12
                            preventStealing: true
                            onClicked: (mouse) => {
                                if (mouse.button === Qt.RightButton) {
                                    root.showContextMenu(modelData, index, listRowMouse, mouse.x, mouse.y)
                                } else {
                                    root.handleItemClick(modelData, index, mouse)
                                }
                            }
                            onDoubleClicked: (mouse) => {
                                if (mouse.button === Qt.LeftButton) root.handleItemDoubleClick(modelData)
                            }
                            ToolTip.visible: containsMouse && !listCheckMouse.containsMouse
                            ToolTip.delay: 450
                            ToolTip.text: {
                                var tip = (modelData.is_dir ? "📁 " : "📄 ") + (modelData.name || "")
                                if (modelData.is_dir) {
                                    tip += "\n" + root.formatFolderSubtitle(listRow.info)
                                    tip += "\n• Double-click to open folder"
                                } else {
                                    tip += "\nSize: " + root.formatBytes(listRow.info.size) + "\nModified: " + root.formatDate(modelData.mtime)
                                    if (root.isMedia(modelData)) {
                                        tip += "\n• Double-click to preview in Lightbox"
                                    } else {
                                        tip += "\n• Double-click to open in default app"
                                    }
                                }
                                tip += "\n• Click to select, Ctrl+click or tick the box to add more, Shift+click for a range\n• Type a name to jump to it"
                                tip += "\n• Right-click for more actions"
                                return tip
                            }
                        }

                        // Selection checkbox (after the row MouseArea so it receives clicks first)
                        Rectangle {
                            visible: !listRow.spacer
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            width: 14; height: 14; radius: 3
                            opacity: (listRow.isSel || listRowMouse.containsMouse || listCheckMouse.containsMouse || root.selectionCount > 0) ? 1.0 : 0.0
                            color: listRow.isSel ? "#38BDF8" : "transparent"
                            border.color: listRow.isSel ? "#38BDF8" : (listCheckMouse.containsMouse ? "#38BDF8" : "#64748B")
                            border.width: 1
                            Text {
                                anchors.centerIn: parent
                                visible: listRow.isSel
                                text: "✓"
                                font.pixelSize: 10
                                font.weight: 800
                                color: "#0F172A"
                            }
                            MouseArea {
                                id: listCheckMouse
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: (mouse) => {
                                    if ((mouse.modifiers & Qt.ShiftModifier) !== 0) {
                                        root.selectRange(root.selectionAnchor >= 0 ? root.selectionAnchor : index, index, true)
                                    } else {
                                        root.toggleSelection(modelData.path)
                                        root.selectionAnchor = index
                                    }
                                }
                            }
                        }
                        // Group by date: section header row (click = select the section)
                        Rectangle {
                            visible: !!modelData.is_header
                            anchors.fill: parent
                            radius: 5
                            color: listTileMouse.containsMouse ? "#16233A" : "#0F1726"
                            border.color: listRow.isKeyFocus ? "#F8FAFC" : (listTileMouse.containsMouse ? "#38BDF8" : "#24324A")
                            Row {
                                anchors.left: parent.left
                                anchors.leftMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 8
                                Text { text: modelData.icon || "📅"; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: modelData.name || ""; font.family: "Segoe UI, sans-serif"; font.pixelSize: 12; font.weight: 700; color: "#F1F5F9"; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: (modelData.count || 0) + ((modelData.count || 0) === 1 ? " item" : " items"); font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
                                Text { visible: listTileMouse.containsMouse; text: "·  click to select all"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                            }
                            MouseArea {
                                id: listTileMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: (mouse) => root.handleItemClick(modelData, index, mouse)
                            }
                        }
                    }
                }
            }
        }

        // 4. BOTTOM STATUS BAR
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            radius: 6
            color: "#0F121B"
            border.color: "#1E2536"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 12

                // Left: Counts of folders and files
                Row {
                    spacing: 8
                    Layout.alignment: Qt.AlignVCenter
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    clip: true

                    // Folders count
                    Row {
                        spacing: 4
                        Text { text: "📁"; font.pixelSize: 11 }
                        Text {
                            text: root.folderCount + (root.folderCount === 1 ? " folder" : " folders")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#38BDF8"
                        }
                    }

                    Text { text: "•"; font.pixelSize: 10; color: "#475569" }

                    // Files count + total file size
                    Row {
                        spacing: 4
                        Text { text: "📄"; font.pixelSize: 11 }
                        Text {
                            text: {
                                var txt = root.fileCount + (root.fileCount === 1 ? " file" : " files")
                                if (root.currentFolderFilesSize > 0) {
                                    txt += " (" + root.formatBytes(root.currentFolderFilesSize) + ")"
                                }
                                return txt
                            }
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#E2E8F0"
                        }
                    }

                    // Filtered count (if user searched or picked a category)
                    Text {
                        visible: !root.recursiveActive && root.shownItemCount !== root.rawItems.length
                        text: root.compact ? ("(" + root.shownItemCount + "/" + root.rawItems.length + ")") : ("— showing " + root.shownItemCount + " of " + root.rawItems.length)
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#94A3B8"
                    }

                    // Subfolder search progress
                    Text {
                        visible: root.recursiveActive
                        text: "🔎 " + root.searchResults.length + (root.searchResults.length === 1 ? " match" : " matches") + " in subfolders"
                              + (root.searchRunning ? "  (searching… " + root.searchScanned + " folders)" : "")
                              + (root.searchResults.length >= 5000 ? "  — showing the first 5,000" : "")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#A78BFA"
                    }

                    // Folder has more entries than the gallery loads at once
                    Text {
                        visible: root.listingTotal > root.rawItems.length
                        text: root.compact ? ("⚠ " + root.rawItems.length.toLocaleString(Qt.locale(), "f", 0) + " of " + root.listingTotal.toLocaleString(Qt.locale(), "f", 0) + " shown") : ("⚠ Only the first " + root.rawItems.length.toLocaleString(Qt.locale(), "f", 0) + " of " + root.listingTotal.toLocaleString(Qt.locale(), "f", 0) + " items are shown")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#F59E0B"
                    }
                }

                Item { Layout.fillWidth: true }

                // A download is running while the download controls are hidden: show it, click to go back
                Rectangle {
                    visible: !!root.bridge && !!root.bridge.isDownloading
                    implicitHeight: 20
                    implicitWidth: dlChipRow.implicitWidth + 16
                    radius: 10
                    clip: true
                    color: dlChipMouse.containsMouse ? "#1E293B" : "#121a2b"
                    border.color: "#38BDF8"
                    border.width: 1
                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: parent.width * Math.max(0, Math.min(1, (root.bridge ? root.bridge.overallProgress : 0) / 100))
                        radius: 10
                        color: "#1E3A5F"
                        opacity: 0.8
                    }
                    Row {
                        id: dlChipRow
                        anchors.left: parent.left
                        anchors.leftMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 5
                        Text { text: "⬇"; font.pixelSize: 10; font.weight: 800; color: "#7DD3FC" }
                        Text {
                            text: "Downloading " + (root.bridge ? root.bridge.overallProgress : 0) + "%"
                                  + ((root.bridge && root.bridge.currentSpeed && !root.compact) ? "  •  " + root.bridge.currentSpeed : "")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#E2E8F0"
                        }
                    }
                    Springy { hover: dlChipMouse.containsMouse; pressed: dlChipMouse.pressed }
                    MouseArea {
                        id: dlChipMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (typeof appWindow !== "undefined") appWindow.currentTab = 0
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: (root.bridge ? root.bridge.statusText : "") + "
Click to open the Downloader"
                    }
                }

                // Background job: live progress, or "done — view" once it finishes
                Rectangle {
                    readonly property bool runningHidden: archiveModal.ownsJob && !archiveModal.isOpen
                    visible: runningHidden || archiveModal.unseenResult
                    implicitHeight: 20
                    implicitWidth: Math.min(bgJobRow.implicitWidth + 16, root.compact ? 230 : 380)
                    radius: 10
                    clip: true
                    color: bgJobMouse.containsMouse ? "#1E293B" : "#121a2b"
                    border.color: archiveModal.unseenResult ? ((archiveModal.result.failed > 0 || archiveModal.result.cancelled) ? "#F59E0B" : "#34D399") : "#38BDF8"
                    border.width: 1

                    // Progress fill behind the text
                    Rectangle {
                        visible: parent.runningHidden
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: parent.width * Math.max(0, Math.min(1, archiveModal.progress / 100))
                        radius: 10
                        color: "#1E3A5F"
                        opacity: 0.8
                    }
                    Row {
                        id: bgJobRow
                        anchors.left: parent.left
                        anchors.leftMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 6
                        Text {
                            text: archiveModal.unseenResult ? ((archiveModal.result.failed > 0 || archiveModal.result.cancelled) ? "⚠" : "✔")
                                  : (archiveModal.mode === "compress" ? "📦" : (archiveModal.mode === "copy" ? "📋" : "📂"))
                            font.pixelSize: 10
                            color: "#CBD5E1"
                        }
                        Text {
                            text: {
                                if (archiveModal.unseenResult) return archiveModal.resultHeadline() + " — view"
                                var t = Math.floor(archiveModal.progress) + "%"
                                if (archiveModal.eta >= 0) t += " • " + (archiveModal.eta < 1.5 ? "almost done" : archiveModal.formatDuration(archiveModal.eta) + " left")
                                return (archiveModal.progressName || archiveModal.progressStatus) + "  " + t
                            }
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#E2E8F0"
                            elide: Text.ElideMiddle
                            width: Math.min(implicitWidth, root.compact ? 190 : 340)
                        }
                    }
                    Springy { hover: bgJobMouse.containsMouse; pressed: bgJobMouse.pressed }
                    MouseArea {
                        id: bgJobMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: archiveModal.reopen()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: parent.runningHidden ? (archiveModal.progressStatus + "\nClick to show the progress window") : "Click to see the details"
                    }
                }

                // Result of the last file operation
                Text {
                    visible: opacity > 0.01
                    opacity: root.toastShown ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                    transform: Translate {
                        x: root.toastShown ? 0 : 14
                        Behavior on x { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
                    }
                    Layout.maximumWidth: root.compact ? 200 : 420
                    text: (root.toastIsError ? "⚠ " : "✔ ") + root.toastText
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: root.toastIsError ? "#F87171" : "#34D399"
                    elide: Text.ElideMiddle
                }
                ActionChip {
                    visible: root.toastShown && root.toastCanUndo && !!root.tools && root.tools.canUndo
                    implicitHeight: 20
                    icon: "↶"; label: "Undo"
                    tip: root.tools ? (root.tools.undoLabel + " (Ctrl+Z)") : ""
                    onTriggered: root.undoLast()
                }

                // Storage breakdown of this folder
                Rectangle {
                    visible: !!root.tools && !root.inFavorites
                    implicitHeight: 20
                    implicitWidth: storRow.implicitWidth + 14
                    radius: 10
                    Layout.alignment: Qt.AlignVCenter
                    color: storMouse.containsMouse ? "#1E293B" : "#141A28"
                    border.color: storMouse.containsMouse ? "#38BDF8" : "#2A364E"
                    Row {
                        id: storRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "📊"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: "Storage"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; font.weight: 600; color: "#CBD5E1"; anchors.verticalCenter: parent.verticalCenter }
                    }
                    Springy { hover: storMouse.containsMouse; pressed: storMouse.pressed }
                    MouseArea {
                        id: storMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.openStorage()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "Storage: see which folders and files take up the most space here"
                    }
                }

                // Right: Space on current disk
                Row {
                    visible: !!root.currentDisk
                    spacing: 6
                    Layout.alignment: Qt.AlignVCenter

                    Text { text: "💽"; font.pixelSize: 11 }

                    Text {
                        visible: !root.veryCompact
                        text: {
                            if (!root.currentDisk) return ""
                            var dName = root.currentDisk.name || ""
                            var sLabel = root.currentDisk.space_label || (root.currentDisk.free_str ? (root.currentDisk.free_str + " free") : "")
                            return dName + (sLabel ? ("  " + sLabel) : "")
                        }
                        font.family: "Segoe UI, monospace"
                        font.pixelSize: 10
                        font.weight: 600
                        color: (root.currentDisk && root.currentDisk.percent_free < 10) ? "#F87171" : "#38BDF8"
                    }

                    // Mini disk usage bar
                    Rectangle {
                        visible: !!root.currentDisk && root.currentDisk.total_bytes > 0
                        width: 44
                        height: 6
                        radius: 3
                        color: "#1E2536"
                        anchors.verticalCenter: parent.verticalCenter

                        Rectangle {
                            height: parent.height
                            width: Math.min(parent.width, parent.width * Math.max(0.02, 1.0 - ((root.currentDisk ? root.currentDisk.percent_free : 0) / 100.0)))
                            radius: 3
                            color: (root.currentDisk && root.currentDisk.percent_free < 10) ? "#EF4444" : ((root.currentDisk && root.currentDisk.percent_free < 20) ? "#F59E0B" : "#38BDF8")
                        }
                    }
                }
            }

            // Hover tooltip on the entire status bar (underneath, so buttons keep their own hover)
            MouseArea {
                anchors.fill: parent
                z: -1
                hoverEnabled: true
                acceptedButtons: Qt.NoButton
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: {
                    var tip = "Current Directory:\n" + root.currentPath
                    tip += "\n• Folders: " + root.folderCount
                    tip += "\n• Files: " + root.fileCount + (root.currentFolderFilesSize > 0 ? (" (" + root.formatBytes(root.currentFolderFilesSize) + ")") : "")
                    if (root.listingTotal > root.rawItems.length) {
                        tip += "\n• This folder holds " + root.listingTotal + " items; only the first " + root.rawItems.length + " are loaded to keep the gallery responsive. Counts and sizes cover the loaded items only."
                    }
                    if (root.currentDisk) {
                        tip += "\n• Disk " + root.currentDisk.name + ": " + (root.currentDisk.free_str || "") + " free of " + (root.currentDisk.total_str || "")
                    }
                    return tip
                }
            }
        }
    }

    // ── Feature Modals ──────────────────────────────────────────────────────
    // ── Pop-up windows: each is built the first time it's opened (the Gallery used to build
    //    all of them up front, about 600 hidden items, and took longer to open) ───────────
    Loader {
        id: lightboxLoader
        anchors.fill: parent
        z: 9999
        active: false
        sourceComponent: Component {
            MediaLightboxModal {
                id: lightboxModal
                bridge: root.bridge
                tools: root.tools
                onItemDeleted: (path) => root.refreshPreservingScroll()
            }
        }
    }

    Loader {
        id: creatorUpdatesLoader
        anchors.fill: parent
        z: 9400
        active: false
        sourceComponent: Component {
            CreatorUpdatesModal {
                id: creatorUpdatesModal
                updates: root.updates
                onCreatorLinked: (info) => root.creatorInfo = info
                onDownloadStarted: (folder, message) => root.showToast(message, false)
            }
        }
    }

    Loader {
        id: storageLoader
        anchors.fill: parent
        z: 9400
        active: false
        sourceComponent: Component {
            StorageModal {
                id: storageModal
                tools: root.tools
                onOpenFolder: (path) => root.navigateTo(path)
                onShowFile: (path) => root.revealInGallery(path)
            }
        }
    }

    Loader {
        id: batchRenameLoader
        anchors.fill: parent
        z: 9998
        active: false
        sourceComponent: Component {
            BatchRenameModal {
                id: batchRenameModal
                bridge: root.bridge
                onRenamed: root.navigateTo(root.currentPath)
            }
        }
    }

    Loader {
        id: galleryCleanerLoader
        anchors.fill: parent
        z: 9998
        active: false
        sourceComponent: Component {
            GalleryCleanerModal {
                id: galleryCleanerModal
                bridge: root.bridge
                onCleaned: root.navigateTo(root.currentPath)
                onOrganized: root.navigateTo(root.currentPath)
            }
        }
    }

    Loader {
        id: rootDiskSafetyLoader
        anchors.fill: parent
        z: 99999
        active: false
        sourceComponent: Component {
            RootDiskSafetyModal {
                id: rootDiskSafetyModal
            }
        }
    }

    Loader {
        id: archiveViewerLoader
        anchors.fill: parent
        z: 9200
        active: false
        // The archive viewer opens pictures and videos in the image viewer
        onLoaded: item.lightbox = root.modal(lightboxLoader)
        sourceComponent: Component {
            ArchiveViewerModal {
                id: archiveViewer
                bridge: root.bridge
                archiver: root.archiver
                onExtractAllRequested: (item) => root.extractItems([item], false)
            }
        }
    }

    GalleryArchiveModal {
        id: archiveModal
        bridge: root.bridge
        archiver: root.archiver
        onFinished: root.refreshPreservingScroll()
        onBackgroundFinished: (headline, ok) => {
            root.showToast(headline, !ok)
            // Elsewhere in the app: the global toast, which jumps back to the result when clicked
            if (typeof appWindow !== "undefined" && appWindow.currentTab !== 6 && appWindow.showToast) {
                appWindow.showToast((ok ? "✔ " : "⚠ ") + "Gallery: " + headline + " (click to view)", function() {
                    appWindow.currentTab = 6
                    archiveModal.reopen()
                })
            }
        }
    }

    // ── Right-click context menu ────────────────────────────────────────────
    Popup {
        id: contextMenu
        // Springs open from its anchor, eases away
        transformOrigin: Popup.TopLeft
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 5.5; damping: 0.28; mass: 0.7; epsilon: 0.001 }
            }
        }
        exit: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: 110 }
                NumberAnimation { property: "scale"; to: 0.94; duration: 110; easing.type: Easing.InCubic }
            }
        }
        readonly property bool single: root.contextItems.length === 1
        readonly property var first: root.contextItems.length > 0 ? root.contextItems[0] : null
        // Web page of the post this file came from (looked up when the menu opens)
        property string sourceUrl: ""
        width: 230
        padding: 4
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: "#121725"
            radius: 7
            border.color: "#2B354C"
            border.width: 1
        }

        contentItem: Column {
            spacing: 0

            Text {
                width: parent.width
                leftPadding: 8; rightPadding: 8; topPadding: 4; bottomPadding: 4
                text: contextMenu.single ? (contextMenu.first ? contextMenu.first.name : "") : (root.contextItems.length + " items selected")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                font.weight: 700
                color: "#94A3B8"
                elide: Text.ElideMiddle
            }
            MenuDivider {}

            MenuRow {
                visible: contextMenu.single
                icon: "↗"; label: "Open"
                onTriggered: { contextMenu.close(); root.openItem(contextMenu.first) }
            }
            MenuRow {
                visible: contextMenu.single && !!contextMenu.first && !contextMenu.first.is_dir && root.isMedia(contextMenu.first)
                icon: "🖥️"; label: "Open in default app"
                onTriggered: { contextMenu.close(); if (root.bridge) root.bridge.openPathInSystem(contextMenu.first.path) }
            }
            MenuRow {
                visible: contextMenu.single
                icon: "📂"; label: "Show in File Explorer"
                onTriggered: { contextMenu.close(); root.revealItem(contextMenu.first) }
            }
            MenuRow {
                visible: contextMenu.single && !!contextMenu.first && !!contextMenu.first.rel_dir
                icon: "🗂"; label: "Go to its folder"
                onTriggered: { contextMenu.close(); root.revealInGallery(contextMenu.first.path) }
            }
            MenuRow {
                visible: contextMenu.sourceUrl.length > 0
                icon: "🌐"; label: "View source post"
                hint: "browser"
                onTriggered: { contextMenu.close(); Qt.openUrlExternally(contextMenu.sourceUrl) }
            }
            MenuRow {
                visible: contextMenu.sourceUrl.length > 0
                icon: "🔗"; label: "Copy post link"
                onTriggered: {
                    contextMenu.close()
                    if (root.bridge) root.bridge.copyToClipboard(contextMenu.sourceUrl)
                    root.showToast("Copied post link", false)
                }
            }
            MenuDivider { visible: contextMenu.single }

            MenuRow {
                visible: !!root.tools
                readonly property bool allFav: {
                    var list = root.contextItems
                    if (!list.length) return false
                    for (var i = 0; i < list.length; i++) if (!root.isFavorite(list[i])) return false
                    return true
                }
                icon: allFav ? "☆" : "⭐"; label: allFav ? "Remove from favourites" : "Add to favourites"; hint: "Ctrl+D"
                onTriggered: { contextMenu.close(); root.toggleFavorite(root.contextItems) }
            }
            RatingRow {
                visible: !!root.tools
                current: root.contextItems.length === 1 ? root.ratingOf(root.contextItems[0]) : 0
                onRated: (n) => { contextMenu.close(); root.setRating(root.contextItems, n) }
            }
            MenuDivider { visible: !!root.tools }
            MenuRow {
                icon: "📋"; label: contextMenu.single ? "Copy path" : ("Copy " + root.contextItems.length + " paths")
                onTriggered: { contextMenu.close(); root.copyPaths(root.contextItems) }
            }
            MenuRow {
                visible: contextMenu.single
                icon: "✏️"; label: "Rename…"; hint: "F2"
                onTriggered: { contextMenu.close(); root.renameItem(contextMenu.first) }
            }
            MenuRow {
                icon: "📦"; label: "Move to folder…"
                onTriggered: { contextMenu.close(); root.moveItemsToFolder(root.contextItems) }
            }
            MenuRow {
                visible: !!root.archiver
                icon: "📋"; label: "Copy to folder…"
                onTriggered: { contextMenu.close(); root.copyItemsToFolder(root.contextItems) }
            }
            MenuDivider { visible: !!root.archiver }
            MenuRow {
                visible: !!root.archiver && contextMenu.single && root.isArchive(contextMenu.first)
                icon: "🔍"; label: "Look inside"
                hint: "double-click"
                onTriggered: { contextMenu.close(); modal(archiveViewerLoader).open(contextMenu.first) }
            }
            MenuRow {
                readonly property int arcCount: root.archivesIn(root.contextItems).length
                visible: !!root.archiver && arcCount > 0
                icon: "📂"; label: arcCount > 1 ? ("Extract " + arcCount + " archives here") : "Extract here"
                hint: "own folder"
                onTriggered: { contextMenu.close(); root.extractItems(root.contextItems, true) }
            }
            MenuRow {
                visible: !!root.archiver && root.archivesIn(root.contextItems).length > 0
                icon: "📂"; label: "Extract…"
                onTriggered: { contextMenu.close(); root.extractItems(root.contextItems, false) }
            }
            MenuRow {
                visible: !!root.archiver
                icon: "🗜️"; label: contextMenu.single ? "Compress…" : ("Compress " + root.contextItems.length + " items…")
                onTriggered: { contextMenu.close(); root.compressItems(root.contextItems) }
            }
            MenuDivider {}
            MenuRow {
                icon: "🗑️"; label: "Move to Recycle Bin"; hint: "Del"; danger: true
                onTriggered: { contextMenu.close(); root.deleteItems(root.contextItems) }
            }
            MenuDivider {}
            MenuRow {
                icon: "☑"; label: "Select all"; hint: "Ctrl+A"
                onTriggered: { contextMenu.close(); root.selectAll() }
            }
            MenuRow {
                visible: root.selectionCount > 0
                icon: "✕"; label: "Clear selection"; hint: "Esc"
                onTriggered: { contextMenu.close(); root.clearSelection() }
            }
            MenuRow {
                visible: !!root.tools && root.tools.canUndo
                icon: "↶"; label: root.tools ? root.tools.undoLabel : ""; hint: "Ctrl+Z"
                onTriggered: { contextMenu.close(); root.undoLast() }
            }
        }
    }

    // ── Character / series menu ────────────────────────────────────────────
    Popup {
        id: charMenu
        // Springs open from its anchor, eases away
        transformOrigin: Popup.TopLeft
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 5.5; damping: 0.28; mass: 0.7; epsilon: 0.001 }
            }
        }
        exit: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: 110 }
                NumberAnimation { property: "scale"; to: 0.94; duration: 110; easing.type: Easing.InCubic }
            }
        }
        width: 260
        padding: 4
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: "#121725"; radius: 7; border.color: "#2B354C"; border.width: 1 }
        // Filled when the menu opens (not bound to 'visible': closing must not destroy the
        // row whose click handler is still running)
        property var entries: []
        onAboutToShow: entries = root.characterCounts()

        contentItem: Column {
            spacing: 0
            Text {
                width: parent.width
                leftPadding: 8; topPadding: 4; bottomPadding: 4
                text: "CHARACTERS & SERIES HERE"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                font.weight: 700
                color: "#64748B"
            }
            MenuRow {
                visible: root.characterFilter.length > 0
                icon: "✕"; label: "Clear filter"
                onTriggered: { charMenu.close(); root.setCharacterFilter("") }
            }
            Text {
                visible: root.tagging
                width: parent.width
                leftPadding: 8; topPadding: 6; bottomPadding: 6
                text: "⏳ Recognising names…"
                font.pixelSize: 11
                color: "#F59E0B"
            }
            Text {
                visible: !root.tagging && charMenu.entries.length === 0
                width: parent.width
                leftPadding: 8; rightPadding: 8; topPadding: 6; bottomPadding: 6
                text: "No known characters or series found in these file names. Add names in the Known Series tab."
                font.pixelSize: 10
                color: "#94A3B8"
                wrapMode: Text.WordWrap
            }
            ListView {
                width: parent.width
                height: Math.min(360, charMenu.entries.length * 26)
                visible: charMenu.entries.length > 0
                clip: true
                model: charMenu.entries
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: MenuRow {
                    width: ListView.view ? ListView.view.width : 240
                    icon: "👤"
                    label: modelData.name
                    hint: modelData.count + (modelData.count === 1 ? " file" : " files")
                    checked: root.characterFilter.toLowerCase() === modelData.name.toLowerCase()
                    onTriggered: {
                        var picked = modelData.name
                        root.setCharacterFilter(picked)
                        charMenu.close()
                    }
                }
            }
        }
    }

    // ── View options menu ──────────────────────────────────────────────────
    Popup {
        id: viewMenu
        // Springs open from its anchor, eases away
        transformOrigin: Popup.TopRight
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 5.5; damping: 0.28; mass: 0.7; epsilon: 0.001 }
            }
        }
        exit: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: 110 }
                NumberAnimation { property: "scale"; to: 0.94; duration: 110; easing.type: Easing.InCubic }
            }
        }
        width: 240
        padding: 4
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: "#121725"; radius: 7; border.color: "#2B354C"; border.width: 1 }

        contentItem: Column {
            spacing: 0
            Text {
                width: parent.width
                leftPadding: 8; topPadding: 4; bottomPadding: 4
                text: "SHOW"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                font.weight: 700
                color: "#64748B"
            }
            MenuRow {
                icon: root.showPathBar ? "☑" : "☐"
                label: "Path bar"
                checked: root.showPathBar
                hint: "Up, Refresh, Bookmark"
                onTriggered: root.showPathBar = !root.showPathBar
            }
            MenuRow {
                icon: root.showShortcutsBar ? "☑" : "☐"
                label: "Shortcuts bar"
                checked: root.showShortcutsBar
                hint: root.shortcutChips.length === 0 ? "no shortcuts yet" : ""
                onTriggered: root.showShortcutsBar = !root.showShortcutsBar
            }
            MenuDivider {}
            MenuRow {
                icon: "📊"
                label: "Storage…"
                hint: "what takes up space"
                enabled: !!root.tools && !root.inFavorites
                onTriggered: { viewMenu.close(); root.openStorage() }
            }
            MenuRow {
                icon: root.privacyBlur ? "☑" : "☐"
                label: "Privacy blur"
                checked: root.privacyBlur
                hint: "Ctrl+H"
                onTriggered: { viewMenu.close(); root.togglePrivacy() }
            }
            MenuDivider {}
            Text {
                width: parent.width
                leftPadding: 8; rightPadding: 8; topPadding: 2; bottomPadding: 4
                text: root.showPathBar ? "Hidden bars can be brought back here." : "Path bar hidden: Backspace still goes up a folder."
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                color: "#64748B"
                wrapMode: Text.WordWrap
            }
        }
    }

    // ── Selection bar "More" menu ──────────────────────────────────────────
    function openMoreMenu(anchorItem) {
        var items = selectedItems()
        moreMenu.items = items
        moreMenu.sourceUrl = (root.tools && items.length === 1 && !items[0].is_dir) ? (root.tools.sourcePost(items[0].path).url || "") : ""
        var p = anchorItem.mapToItem(root, anchorItem.width - moreMenu.width, anchorItem.height + 4)
        moreMenu.x = Math.max(4, Math.min(p.x, root.width - moreMenu.width - 4))
        moreMenu.y = p.y
        moreMenu.open()
    }

    Popup {
        id: moreMenu
        // Springs open from its anchor, eases away
        transformOrigin: Popup.TopRight
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 5.5; damping: 0.28; mass: 0.7; epsilon: 0.001 }
            }
        }
        exit: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: 110 }
                NumberAnimation { property: "scale"; to: 0.94; duration: 110; easing.type: Easing.InCubic }
            }
        }
        property var items: []
        property string sourceUrl: ""
        readonly property bool single: items.length === 1
        readonly property var first: items.length > 0 ? items[0] : null
        width: 230
        padding: 4
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: "#121725"; radius: 7; border.color: "#2B354C"; border.width: 1 }

        contentItem: Column {
            spacing: 0
            MenuRow {
                visible: moreMenu.single
                icon: "↗"; label: "Open"; hint: "Enter"
                onTriggered: { moreMenu.close(); root.openItem(moreMenu.first) }
            }
            MenuRow {
                visible: moreMenu.single
                icon: "📂"; label: "Show in File Explorer"
                onTriggered: { moreMenu.close(); root.revealItem(moreMenu.first) }
            }
            MenuRow {
                visible: moreMenu.sourceUrl.length > 0
                icon: "🌐"; label: "View source post"
                onTriggered: { moreMenu.close(); Qt.openUrlExternally(moreMenu.sourceUrl) }
            }
            MenuDivider { visible: moreMenu.single }
            MenuRow {
                visible: !!root.tools
                readonly property bool allFav: {
                    var list = moreMenu.items
                    if (!list.length) return false
                    for (var i = 0; i < list.length; i++) if (!root.isFavorite(list[i])) return false
                    return true
                }
                icon: allFav ? "☆" : "⭐"; label: allFav ? "Remove from favourites" : "Add to favourites"; hint: "Ctrl+D"
                onTriggered: { moreMenu.close(); root.toggleFavorite(moreMenu.items) }
            }
            RatingRow {
                visible: !!root.tools
                current: moreMenu.items.length === 1 ? root.ratingOf(moreMenu.items[0]) : 0
                onRated: (n) => { moreMenu.close(); root.setRating(moreMenu.items, n) }
            }
            MenuDivider { visible: !!root.tools }
            MenuRow {
                icon: "📋"; label: moreMenu.single ? "Copy path" : ("Copy " + moreMenu.items.length + " paths")
                onTriggered: { moreMenu.close(); root.copyPaths(moreMenu.items) }
            }
            MenuRow {
                visible: moreMenu.single
                icon: "✏️"; label: "Rename…"; hint: "F2"
                onTriggered: { moreMenu.close(); root.renameItem(moreMenu.first) }
            }
            MenuDivider {}
            MenuRow {
                icon: "☑"; label: "Select all"; hint: "Ctrl+A"
                onTriggered: { moreMenu.close(); root.selectAll() }
            }
            MenuRow {
                icon: "✕"; label: "Clear selection"; hint: "Esc"
                onTriggered: { moreMenu.close(); root.clearSelection() }
            }
        }
    }

    // ── Sort menu ───────────────────────────────────────────────────────────
    Popup {
        id: sortMenu
        // Springs open from its anchor, eases away
        transformOrigin: Popup.TopLeft
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 5.5; damping: 0.28; mass: 0.7; epsilon: 0.001 }
            }
        }
        exit: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: 110 }
                NumberAnimation { property: "scale"; to: 0.94; duration: 110; easing.type: Easing.InCubic }
            }
        }
        width: 190
        padding: 4
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: "#121725"
            radius: 7
            border.color: "#2B354C"
            border.width: 1
        }

        contentItem: Column {
            spacing: 0
            Repeater {
                model: [
                    { key: "name", icon: "🔤", label: "Name" },
                    { key: "date", icon: "🕒", label: "Date modified" },
                    { key: "size", icon: "📏", label: "Size" },
                    { key: "type", icon: "🏷️", label: "Type" },
                    { key: "rating", icon: "★", label: "Rating" }
                ]
                delegate: MenuRow {
                    width: sortMenu.availableWidth
                    icon: modelData.icon
                    label: modelData.label
                    checked: root.sortKey === modelData.key
                    hint: checked ? (root.sortAscending ? "▲" : "▼") : ""
                    onTriggered: {
                        if (root.sortKey !== modelData.key) root.sortBy(modelData.key)
                        sortMenu.close()
                    }
                }
            }
            MenuDivider { width: sortMenu.availableWidth }
            MenuRow {
                width: sortMenu.availableWidth
                icon: "▲"; label: "Ascending"
                checked: root.sortAscending
                onTriggered: { if (!root.sortAscending) { root.sortAscending = true; root.resort() } sortMenu.close() }
            }
            MenuRow {
                width: sortMenu.availableWidth
                icon: "▼"; label: "Descending"
                checked: !root.sortAscending
                onTriggered: { if (root.sortAscending) { root.sortAscending = false; root.resort() } sortMenu.close() }
            }
        }
    }

    // ── Delete confirmation (Recycle Bin) ───────────────────────────────────
    Item {
        id: deleteConfirm
        property bool isOpen: false
        property var items: []
        anchors.fill: parent
        z: 9000
        // Fades in / out; no input while closing
        opacity: isOpen ? 1 : 0
        visible: opacity > 0.005
        enabled: isOpen
        Behavior on opacity { NumberAnimation { duration: 170; easing.type: Easing.OutCubic } }

        function show(list) {
            items = list
            isOpen = true
            deleteKeys.forceActiveFocus()
        }
        function close() {
            isOpen = false
            items = []
        }
        function confirm() {
            if (!root.bridge || !items.length) { close(); return }
            var paths = root._pathsOf(items)
            var res = root.bridge.deleteItems(paths)
            close()
            if (res.failed > 0) {
                root.showToast("Moved " + res.deleted + " to the Recycle Bin, " + res.failed + " failed: " + (res.errors.length ? res.errors[0] : ""), true)
            } else {
                root.showToast("Moved " + res.deleted + (res.deleted === 1 ? " item" : " items") + " to the Recycle Bin", false)
            }
            root.refreshPreservingScroll()
        }

        Item {
            id: deleteKeys
            focus: deleteConfirm.isOpen
            Keys.onEscapePressed: deleteConfirm.close()
            Keys.onReturnPressed: deleteConfirm.confirm()
            Keys.onEnterPressed: deleteConfirm.confirm()
        }

        Rectangle {
            anchors.fill: parent
            color: "#060910"
            opacity: 0.85
            MouseArea { anchors.fill: parent; hoverEnabled: true; onClicked: deleteConfirm.close() }
        }

        Rectangle {
            // Heavy panel: settles in on a soft spring
            scale: deleteConfirm.isOpen ? 1.0 : 0.9
            Behavior on scale { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.0008 } }
            anchors.centerIn: parent
            width: Math.min(440, parent.width - 40)
            height: delCol.implicitHeight + 32
            radius: 10
            color: "#121725"
            border.color: "#EF4444"
            border.width: 1
            MouseArea { anchors.fill: parent; hoverEnabled: true }

            ColumnLayout {
                id: delCol
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10

                Text {
                    text: "🗑️  Move " + deleteConfirm.items.length + (deleteConfirm.items.length === 1 ? " item" : " items") + " to the Recycle Bin?"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.weight: 700
                    color: "#F8FAFC"
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
                Text {
                    Layout.fillWidth: true
                    text: {
                        var list = deleteConfirm.items
                        var names = []
                        for (var i = 0; i < Math.min(5, list.length); i++) names.push((list[i].is_dir ? "📁 " : "• ") + list[i].name)
                        if (list.length > 5) names.push("…and " + (list.length - 5) + " more")
                        return names.join("\n")
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#CBD5E1"
                    elide: Text.ElideMiddle
                }
                Text {
                    Layout.fillWidth: true
                    readonly property real sz: root.totalSize(deleteConfirm.items)
                    text: (sz > 0 ? (root.formatBytes(sz) + " • ") : "") + "You can restore these from the Recycle Bin. Folders are moved with everything inside them."
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    ActionChip {
                        label: "Cancel"
                        implicitHeight: 28
                        onTriggered: deleteConfirm.close()
                    }
                    ActionChip {
                        icon: "🗑️"; label: "Move to Recycle Bin"; danger: true
                        implicitHeight: 28
                        onTriggered: deleteConfirm.confirm()
                    }
                }
            }
        }
    }

    // ── Rename dialog ───────────────────────────────────────────────────────
    Item {
        id: renameDialog
        property bool isOpen: false
        property var target: null
        property string errorText: ""
        property bool creating: false   // true = "New folder" mode
        anchors.fill: parent
        z: 9000
        opacity: isOpen ? 1 : 0
        visible: opacity > 0.005
        enabled: isOpen
        Behavior on opacity { NumberAnimation { duration: 170; easing.type: Easing.OutCubic } }

        function showCreate() {
            creating = true
            target = null
            errorText = ""
            renameField.text = "New folder"
            isOpen = true
            renameField.forceActiveFocus()
            renameField.selectAll()
        }
        function show(item) {
            creating = false
            target = item
            errorText = ""
            renameField.text = item.name
            isOpen = true
            renameField.forceActiveFocus()
            // Select the name without its extension, like Explorer
            var dot = item.is_dir ? -1 : item.name.lastIndexOf(".")
            renameField.select(0, dot > 0 ? dot : item.name.length)
        }
        function close() {
            isOpen = false
            target = null
        }
        function confirm() {
            if (creating) {
                var res0 = root.tools.createFolder(root.currentPath, renameField.text.trim())
                if (!res0.success) {
                    errorText = res0.error
                    return
                }
                close()
                root.showToast("Created folder " + renameField.text.trim(), false, true)
                root.pendingRevealPath = res0.path
                root.refreshPreservingScroll()
                return
            }
            if (!root.bridge || !target) { close(); return }
            var newName = renameField.text.trim()
            if (newName === target.name) { close(); return }
            var res = root.tools ? root.tools.renameItem(target.path, newName) : root.bridge.renameItem(target.path, newName)
            if (!res.success) {
                errorText = res.error
                return
            }
            close()
            root.showToast("Renamed to " + newName, false, true)
            root.refreshPreservingScroll()
        }

        Rectangle {
            anchors.fill: parent
            color: "#060910"
            opacity: 0.85
            MouseArea { anchors.fill: parent; hoverEnabled: true; onClicked: renameDialog.close() }
        }

        Rectangle {
            // Heavy panel: settles in on a soft spring
            scale: renameDialog.isOpen ? 1.0 : 0.9
            Behavior on scale { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.0008 } }
            anchors.centerIn: parent
            width: Math.min(460, parent.width - 40)
            height: renCol.implicitHeight + 32
            radius: 10
            color: "#121725"
            border.color: "#38BDF8"
            border.width: 1
            MouseArea { anchors.fill: parent; hoverEnabled: true }

            ColumnLayout {
                id: renCol
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10

                Text {
                    text: renameDialog.creating ? "📁  New folder" : ("✏️  Rename " + (renameDialog.target && renameDialog.target.is_dir ? "folder" : "file"))
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.weight: 700
                    color: "#F8FAFC"
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 32
                    radius: 6
                    color: "#0D1018"
                    border.color: renameDialog.errorText ? "#EF4444" : (renameField.activeFocus ? "#38BDF8" : "#252D3E")
                    border.width: 1

                    TextInput {
                        id: renameField
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        verticalAlignment: TextInput.AlignVCenter
                        color: "#F8FAFC"
                        selectionColor: "#2563EB"
                        selectedTextColor: "#FFFFFF"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        selectByMouse: true
                        clip: true
                        onTextChanged: renameDialog.errorText = ""
                        Keys.onReturnPressed: renameDialog.confirm()
                        Keys.onEnterPressed: renameDialog.confirm()
                        Keys.onEscapePressed: renameDialog.close()
                    }
                }

                Text {
                    visible: renameDialog.errorText.length > 0
                    Layout.fillWidth: true
                    text: "⚠ " + renameDialog.errorText
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#F87171"
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    ActionChip {
                        label: "Cancel"
                        implicitHeight: 28
                        onTriggered: renameDialog.close()
                    }
                    ActionChip {
                        icon: "✔"; label: renameDialog.creating ? "Create" : "Rename"
                        implicitHeight: 28
                        onTriggered: renameDialog.confirm()
                    }
                }
            }
        }
    }
}
