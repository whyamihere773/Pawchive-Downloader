import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "archive"

Rectangle {
    id: root

    property var bridge: null
    // The creators (a model in Python: a JavaScript array of every creator froze the window at
    // tens of thousands of creators). _creatorsRevision changes whenever a new list is shown.
    readonly property var creatorsModel: root.bridge ? root.bridge.archiveCreatorsModel : null
    property int _creatorsRevision: 0
    property var statistics: ({
        total_files: 0,
        total_creators: 0,
        total_posts: 0,
        db_size_str: "0 KB",
        category_counts: {},
        service_counts: {}
    })

    property string searchFilter: ""
    property string serviceFilter: "all"
    property string fileTypeFilter: "all"
    property string sortOrder: "creator_az"
    property var expandedCreators: ({})
    property var expandedPosts: ({})
    property bool headerCollapsed: false

    // Verification state map: key = service+":"+creatorId
    // value = { running: bool, current: int, total: int, present: int, missing: int, done: bool }
    property var verificationState: ({})

    function _verifyKey(service, creatorId) { return service + ":" + creatorId }
    function creatorVerifyState(service, creatorId) {
        return verificationState[_verifyKey(service, creatorId)] || null
    }

    color: "#0B0E14"

    function tr(key, fallback) {
        if (typeof Lang !== "undefined" && Lang) {
            var _ = Lang.activeLanguage
            var res = Lang.t(key)
            return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
        }
        return fallback !== undefined ? fallback : key
    }

    property bool _needsReload: false
    property int _reloadSeq: 0
    property string _reloadRequest: ""
    property bool _expandOnResult: false     // a search opens every creator it found

    // Posts (with their files) of the creators that are open. Only the creators come with a refresh;
    // a creator's posts are read when it's opened, one creator at a time (sending every file of a big
    // archive to the window on each refresh froze it, #28).
    property var loadedPosts: ({})           // creator key -> posts
    // One creator's posts arrived. The map is changed in place and only that creator's card takes
    // its posts: replacing the whole map rebuilt the posts of every open card on each arrival.
    signal postsArrived(string key)
    property var _stalePosts: ({})           // shown posts that are read again when their card is built
    property var _postsQueue: []
    property string _postsRequest: ""
    property string _postsRequestKey: ""
    property int _postsSeq: 0
    property string _postsFilter: ""
    property string _exportRequest: ""
    // Archive changes run in the background (seconds on big archives); their answers are matched here
    property var _jobCallbacks: ({})
    property int _jobSeq: 0
    property var _activeJobs: ({})
    property var _busyCreators: ({})
    property int _activeJobCount: 0
    property string _activeJobText: ""
    property bool _isReloadingCreators: false

    function _creatorBusyKey(service, creatorId) {
        return String(service || "") + ":" + String(creatorId || "")
    }
    function _hasGlobalJob() {
        for (var k in root._activeJobs) {
            if (root._activeJobs[k] && root._activeJobs[k].global) return true
        }
        return false
    }
    function isCreatorBusy(service, creatorId) {
        if (root._hasGlobalJob()) return true
        return Boolean(root._busyCreators[root._creatorBusyKey(service, creatorId)])
    }
    function _syncActiveJobTelemetry() {
        var cnt = 0
        var lastLabel = ""
        for (var k in root._activeJobs) {
            cnt += 1
            if (root._activeJobs[k] && root._activeJobs[k].label) {
                lastLabel = root._activeJobs[k].label
            }
        }
        root._activeJobCount = cnt
        root._activeJobText = lastLabel
    }
    function _startJob(id, label, creatorKey, isGlobal) {
        var nextJobs = Object.assign({}, root._activeJobs)
        nextJobs[id] = { label: label || "Working...", creatorKey: creatorKey || "", global: Boolean(isGlobal) }
        root._activeJobs = nextJobs
        if (creatorKey) {
            var nextBusy = Object.assign({}, root._busyCreators)
            nextBusy[creatorKey] = (nextBusy[creatorKey] || 0) + 1
            root._busyCreators = nextBusy
        }
        root._syncActiveJobTelemetry()
    }
    function _finishJob(id) {
        var meta = root._activeJobs[id]
        if (!meta) return
        var nextJobs = Object.assign({}, root._activeJobs)
        delete nextJobs[id]
        root._activeJobs = nextJobs
        if (meta.creatorKey) {
            var nextBusy = Object.assign({}, root._busyCreators)
            var nextCnt = (nextBusy[meta.creatorKey] || 1) - 1
            if (nextCnt <= 0) delete nextBusy[meta.creatorKey]
            else nextBusy[meta.creatorKey] = nextCnt
            root._busyCreators = nextBusy
        }
        root._syncActiveJobTelemetry()
    }
    function archiveJob(start, onDone, opts) {
        var o = opts || {}
        root._jobSeq += 1
        var id = "archive-job-" + root._jobSeq
        root._jobCallbacks[id] = onDone
        root._startJob(id, o.label || "", o.creatorKey || "", Boolean(o.global))
        try {
            start(id)
        } catch (e) {
            delete root._jobCallbacks[id]
            root._finishJob(id)
            throw e
        }
    }
    readonly property int pageSize: 50       // posts shown at a time when a creator is opened (files: 100)
    // While searching, every creator found is open with its posts and files showing: smaller first pages
    readonly property int postsPage: searchFilter.length > 0 ? 5 : pageSize
    readonly property int filesPage: searchFilter.length > 0 ? 5 : pageSize * 2

    function postsFor(creator) {
        var k = creator ? creator.key : ""
        return (k && root.loadedPosts[k]) ? root.loadedPosts[k] : []
    }
    function postsLoaded(creator) {
        return !!(creator && creator.key && root.loadedPosts[creator.key])
    }
    function requestPosts(creator) {
        if (!creator || !creator.key || !root.bridge) return
        if (root._postsQueue.indexOf(creator.key) >= 0 || root._postsRequestKey === creator.key) return
        root._postsQueue.push(creator.key)
        root._pumpPosts()
    }
    function _pumpPosts() {
        if (root._postsRequest !== "" || root._postsQueue.length === 0 || !root.bridge) return
        var key = root._postsQueue.shift()
        root._postsSeq += 1
        root._postsRequest = "archive-posts-" + root._postsSeq
        root._postsRequestKey = key
        root.bridge.getArchiveCreatorPostsAsync(root._postsRequest, key, root.searchFilter, root.serviceFilter, root.fileTypeFilter)
    }
    function _filterSignature() {
        return root.searchFilter + "\u0001" + root.serviceFilter + "\u0001" + root.fileTypeFilter
    }
    // Why an archive change failed, in words for the user
    function archiveErrorText() {
        var e = root.bridge ? root.bridge.archiveLastError() : ""
        if (/malformed|corrupt|not a database/i.test(e))
            return root.tr("toast_archive_damaged", "The archive database is damaged. It's being repaired now; try again in a moment.")
        return root.tr("toast_archive_error", "The archive couldn't be changed: %1").replace("%1", e || "?")
    }

    Timer {
        id: reloadDebounceTimer
        // At most one refresh per interval: every finished file asks for one while downloading
        interval: (root.bridge && root.bridge.isDownloading) ? 8000 : 800
        repeat: false
        onTriggered: {
            if (root.visible) {
                root._needsReload = false
                root.reload()
            } else {
                root._needsReload = true
            }
        }
    }

    function scheduleReload() {
        if (!root.visible) {
            root._needsReload = true
            return
        }
        if (!reloadDebounceTimer.running)
            reloadDebounceTimer.start()
    }

    onVisibleChanged: {
        if (visible && _needsReload) {
            _needsReload = false
            reload()
        }
    }

    // The data is read in the background; a reload asked for while one runs is done right after it
    function reload() {
        if (!root.bridge) return
        // A new request replaces one still running (the bridge stops the older read)
        root._reloadSeq += 1
        root._reloadRequest = "archive-" + root._reloadSeq
        root._isReloadingCreators = true
        root.bridge.getArchiveDataAsync(root._reloadRequest, root.searchFilter, root.serviceFilter, root.fileTypeFilter, root.sortOrder)
    }

    Connections {
        target: root.bridge
        function onAsyncResultReady(requestId, result) {
            var done = root._jobCallbacks[requestId]
            if (done) {
                delete root._jobCallbacks[requestId]
                try {
                    done(result)
                } finally {
                    root._finishJob(requestId)
                }
                return
            }
            if (requestId === root._postsRequest) {
                var arrivedKey = root._postsRequestKey
                root._postsRequest = ""
                root._postsRequestKey = ""
                // Ignore cancelled/stale post reads (null) instead of clobbering shown posts
                if (result !== null && result !== undefined) {
                    root.loadedPosts[arrivedKey] = result
                    if (root._stalePosts[arrivedKey])
                        delete root._stalePosts[arrivedKey]
                    root.postsArrived(arrivedKey)
                }
                root._pumpPosts()
                return
            }
            if (requestId === root._exportRequest) {
                var expReq = root._exportRequest
                root._exportRequest = ""
                root._finishJob(expReq)
                var n = (typeof result === "number") ? result : -1
                if (n < 0)
                    root.showToast(root.archiveErrorText())
                else
                    root.showToast(root.tr("toast_exported_count", "Exported %1 records to archive file.").replace("%1", n))
                return
            }
            if (requestId !== root._reloadRequest) return
            root._reloadRequest = ""
            root._isReloadingCreators = false
            if (result && root.creatorsModel) {
                if (root._expandOnResult) {
                    root._expandOnResult = false
                    root.expandedCreators = root.creatorsModel.allNamesMap()
                }
                // Open creators keep their posts on screen while they're read again; with other
                // filters (search, site, type) the old ones don't apply
                // Only cards that exist (on screen) read their posts: a search opens every creator
                // it found, and reading all of them right away kept the window busy
                var sig = root._filterSignature()
                var keep = {}
                var stale = {}
                if (sig === root._postsFilter) {
                    for (var k in root.loadedPosts) {
                        if (root.creatorsModel.pendingHasKey(k)) {
                            keep[k] = root.loadedPosts[k]
                            stale[k] = true
                        }
                    }
                }
                root._postsFilter = sig
                root._postsQueue = []
                root._stalePosts = stale
                root.loadedPosts = keep
                var keepY = creatorsListView.contentY
                root.creatorsModel.applyPending()
                root._creatorsRevision += 1
                if (keepY > 0)
                    creatorsListView.contentY = Math.min(keepY, Math.max(0, creatorsListView.contentHeight - creatorsListView.height))
                root.statistics = result.statistics
            }
        }
        function onArchiveRepairFinished(result) {
            if (result && result.ok)
                root.showToast(root.tr("toast_archive_repaired", "The archive database was damaged and has been repaired (%1 records kept). You can try again now.").replace("%1", result.kept))
            else
                root.showToast(root.tr("toast_archive_repair_failed", "The archive database is damaged and couldn't be repaired: %1").replace("%1", (result && result.error) ? result.error : "?"))
        }
        function onArchiveUpdated() {
            root.scheduleReload()
        }
        function onEnableDownloadArchiveChanged() {
            root.scheduleReload()
        }

        function onArchiveCreatorVerificationStarted(service, creatorId) {
            var key = root._verifyKey(service, creatorId)
            var newMap = Object.assign({}, root.verificationState)
            newMap[key] = { running: true, current: 0, total: 0, present: 0, missing: 0, done: false }
            root.verificationState = newMap
        }

        function onArchiveCreatorVerificationProgress(service, creatorId, current, total) {
            var key = root._verifyKey(service, creatorId)
            var newMap = Object.assign({}, root.verificationState)
            var prev = newMap[key] || { running: true, current: 0, total: 0, present: 0, missing: 0, done: false }
            newMap[key] = Object.assign({}, prev, { current: current, total: total })
            root.verificationState = newMap
        }

        function onArchiveCreatorVerificationFinished(service, creatorId, result) {
            var key = root._verifyKey(service, creatorId)
            var newMap = Object.assign({}, root.verificationState)
            newMap[key] = {
                running: false, done: true,
                current: result.total || 0, total: result.total || 0,
                present: result.present || 0, missing: result.missing || 0
            }
            root.verificationState = newMap
        }
    }

    Component.onCompleted: {
        if (root.visible) {
            root.reload()
        } else {
            root._needsReload = true
        }
    }

    // Status Toast notification overlay
    property string toastMessage: ""
    property bool toastVisible: false
    Timer {
        id: toastTimer
        interval: 3000
        onTriggered: root.toastVisible = false
    }
    function showToast(msg) {
        toastMessage = msg
        toastVisible = true
        toastTimer.restart()
    }


    property bool clearConfirmOpen: false
    property var deleteTargetCreator: null
    property var removeMissingTargetCreator: null
    property var deleteTargetPost: null

    function openFingerprintDialog() { archiveDialogs.openFingerprintDialog() }
    function openImportDialog() { archiveDialogs.openImportDialog() }
    function openExportDialog() { archiveDialogs.openExportDialog() }
    function openClearConfirm() { archiveDialogs.openClearConfirm() }
    function openDeleteCreatorConfirm(creator) { archiveDialogs.openDeleteCreatorConfirm(creator) }
    function openRemoveMissingConfirm(creator) { archiveDialogs.openRemoveMissingConfirm(creator) }
    function openDeletePostConfirm(post) { archiveDialogs.openDeletePostConfirm(post) }

    // Main Layout
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        ArchiveHeaderCard {
            view: root
        }

        ArchiveFilterBar {
            view: root
        }

        // ── 3. Hierarchical Accordion View (Creator ➔ Post ➔ Files) ────
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Empty State
            ColumnLayout {
                anchors.centerIn: parent
                spacing: 12
                visible: !root.creatorsModel || root.creatorsModel.count === 0

                Text {
                    text: "🗃️"
                    font.pixelSize: 42
                    Layout.alignment: Qt.AlignHCenter
                    opacity: 0.6
                }

                Text {
                    text: root.searchFilter.length > 0
                          ? root.tr("empty_archive_search", "No archived files match your search criteria.")
                          : root.tr("empty_archive_empty", "The download archive database is currently empty.")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 14
                    font.weight: 600
                    color: "#94A3B8"
                    Layout.alignment: Qt.AlignHCenter
                }

                Text {
                    text: root.searchFilter.length > 0
                          ? root.tr("empty_archive_search_sub", "Try searching for a different keyword, artist, post ID, or file extension.")
                          : root.tr("empty_archive_empty_sub", "When 'Active & Protecting' is toggled ON, every successfully downloaded file is indexed here so it won't be re-downloaded.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                    Layout.alignment: Qt.AlignHCenter
                }

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 10
                    visible: root.searchFilter.length === 0

                    StyledButton {
                        text: root.tr("btn_rebuild_archive", "Rebuild Archive from Local Files")
                        iconText: "🔨"
                        variant: "primary"
                        onClicked: {
                            if (typeof appWindow !== "undefined" && typeof appWindow.openArchiveRebuildModal === "function") {
                                appWindow.openArchiveRebuildModal()
                            }
                        }
                    }

                    StyledButton {
                        text: root.tr("btn_import_archive_empty", "Import archive file")
                        iconText: "📥"
                        variant: "outline"
                        onClicked: root.openImportDialog()
                    }
                }
            }

            ArchiveCreatorsList {
                id: creatorsListView
                view: root
            }
} // end content container Item
} // end main ColumnLayout

    // ── Toast Notification Banner ──────────────────────────────────────
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        anchors.horizontalCenter: parent.horizontalCenter
        implicitWidth: toastRow.implicitWidth + 24
        implicitHeight: 34
        radius: 17
        color: "#0F172A"
        border.color: "#38BDF8"
        border.width: 1
        z: 100
        visible: opacity > 0.001
        opacity: root.toastVisible ? 1.0 : 0.0

        scale: root.toastVisible ? 1.0 : 0.85
        Behavior on scale {
            SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8 }
        }

        transform: Translate {
            y: root.toastVisible ? 0 : 25
            Behavior on y {
                SpringAnimation { spring: 4.2; damping: 0.36; mass: 0.85; epsilon: 0.1 }
            }
        }

        Behavior on opacity { NumberAnimation { duration: 180 } }

        RowLayout {
            id: toastRow
            anchors.centerIn: parent
            spacing: 8
            Text { text: "ℹ️"; font.pixelSize: 12 }
            Text {
                text: root.toastMessage
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 600
                color: "#F8FAFC"
            }
        }
    }


    ArchiveDialogsAndModals {
        id: archiveDialogs
        view: root
    }
}
