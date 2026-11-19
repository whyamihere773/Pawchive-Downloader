import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "gallery_cleaner"

// ── Gallery Cleaner & Deduplicator Modal ───────────────────────────────────
// Identifies duplicate downloads, broken zero-byte files, and auto-sorts folders into clean hierarchies.
Item {
    id: root

    property var bridge: null
    property bool isOpen: false
    property string folderPath: ""

    signal cleaned()
    signal organized()

    property string activeTab: "broken" // "broken" | "duplicates" | "sort"
    property bool recursiveScan: false
    readonly property bool isBrokenScanning: _brokenRequest.length > 0
    readonly property bool isDupScanning: _dupRequest.length > 0
    readonly property bool isScanning: isBrokenScanning || isDupScanning
    property bool isDeleting: false

    // Broken files state
    property var brokenItems: []
    property var selectedBrokenPaths: ({})
    property int selectedBrokenCount: 0

    // Duplicate files state
    property var duplicateGroups: []
    property var selectedDupPaths: ({})
    property int selectedDupCount: 0
    property real totalWastedBytes: 0

    // Auto sort state
    property string sortMode: "type" // "type" | "date" | "extension"
    property string sortResultMsg: ""
    property bool sortRecursive: false
    property bool isSorting: false
    property bool canUndoFlatten: false

    // Scans and sorting run in the background (big folders froze the window); answers arrive here
    property int _requestSeq: 0
    property string _brokenRequest: ""
    property string _dupRequest: ""
    property string _sortRequest: ""
    function _newRequest(kind) { _requestSeq += 1; return "cleaner-" + kind + "-" + _requestSeq }

    Connections {
        target: root.bridge
        ignoreUnknownSignals: true
        function onAsyncResultReady(requestId, result) {
            if (requestId === root._brokenRequest) {
                root._brokenRequest = ""
                root._applyBrokenResult(result || [])
            } else if (requestId === root._dupRequest) {
                root._dupRequest = ""
                root._applyDuplicateResult(result || [])
            } else if (requestId === root._sortRequest) {
                root._sortRequest = ""
                root._applySortResult(result)
            }
        }
    }

    // Safety checks
    property var pathSafety: (bridge && bridge.getPathSafetyInfo) ? bridge.getPathSafetyInfo(folderPath) : null
    readonly property bool isPathBlocked: pathSafety ? pathSafety.is_blocked : false
    readonly property bool isOtherRoot: pathSafety ? pathSafety.is_other_root : false

    anchors.fill: parent
    z: 9998
    // Fades in / out (weight-based motion); no input while closing
    opacity: isOpen ? 1 : 0
    visible: opacity > 0.005
    enabled: isOpen
    Behavior on opacity { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "0 B"
        var k = 1024
        var sizes = ["B", "KB", "MB", "GB", "TB"]
        var i = Math.floor(Math.log(bytes) / Math.log(k))
        if (i < 0) i = 0
        if (i >= sizes.length) i = sizes.length - 1
        return (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1) + " " + sizes[i]
    }

    function open(currentFolder) {
        _brokenRequest = ""
        _dupRequest = ""
        _sortRequest = ""
        folderPath = currentFolder || ""
        activeTab = "broken"
        recursiveScan = false
        sortRecursive = false
        brokenItems = []
        selectedBrokenPaths = {}
        selectedBrokenCount = 0
        duplicateGroups = []
        selectedDupPaths = {}
        selectedDupCount = 0
        totalWastedBytes = 0
        sortResultMsg = ""
        isSorting = false
        canUndoFlatten = (bridge && bridge.hasFlattenUndo) ? bridge.hasFlattenUndo(folderPath) : false
        isOpen = true
        if (!isPathBlocked) {
            scanBroken()
        }
    }

    function close() {
        _brokenRequest = ""
        _dupRequest = ""
        _sortRequest = ""
        isOpen = false
    }

    // ── Tab 1: Broken Files ─────────────────────────────────────────────────
    function scanBroken() {
        if (!bridge || !bridge.scanBrokenFilesAsync || root.isPathBlocked) return
        brokenItems = []
        _brokenRequest = _newRequest("broken")
        bridge.scanBrokenFilesAsync(_brokenRequest, folderPath, recursiveScan)
    }

    function _applyBrokenResult(items) {
        brokenItems = items

        var sel = {}
        var cnt = 0
        for (var i = 0; i < items.length; i++) {
            sel[items[i].path] = true
            cnt++
        }
        selectedBrokenPaths = sel
        selectedBrokenCount = cnt
    }

    function toggleBrokenSelection(path) {
        var sel = Object.assign({}, selectedBrokenPaths)
        if (sel[path]) {
            delete sel[path]
        } else {
            sel[path] = true
        }
        selectedBrokenPaths = sel
        selectedBrokenCount = Object.keys(sel).length
    }

    function selectAllBroken(enable) {
        var sel = {}
        if (enable) {
            for (var i = 0; i < brokenItems.length; i++) {
                sel[brokenItems[i].path] = true
            }
        }
        selectedBrokenPaths = sel
        selectedBrokenCount = Object.keys(sel).length
    }

    function deleteBrokenItems() {
        if (!bridge || !bridge.deleteItems || selectedBrokenCount === 0 || root.isPathBlocked) return
        isDeleting = true
        var paths = Object.keys(selectedBrokenPaths)
        bridge.deleteItems(paths)
        isDeleting = false
        root.cleaned()
        scanBroken()
    }

    // ── Tab 2: Duplicate Files ──────────────────────────────────────────────
    function scanDuplicates() {
        if (!bridge || !bridge.scanDuplicatesAsync || root.isPathBlocked) return
        duplicateGroups = []
        totalWastedBytes = 0
        _dupRequest = _newRequest("dup")
        bridge.scanDuplicatesAsync(_dupRequest, folderPath, recursiveScan)
    }

    function _applyDuplicateResult(groups) {
        duplicateGroups = groups

        var totalWasted = 0
        for (var i = 0; i < groups.length; i++) {
            totalWasted += (groups[i].wasted_size || 0)
        }
        totalWastedBytes = totalWasted

        // Default selection: select all copies except the oldest one
        selectDuplicatesStrategy("keep_oldest")
    }

    function selectDuplicatesStrategy(strategy) {
        var sel = {}
        for (var i = 0; i < duplicateGroups.length; i++) {
            var files = duplicateGroups[i].files || []
            if (files.length <= 1) continue

            if (strategy === "keep_oldest") {
                // files are sorted oldest first in backend, so skip files[0]
                for (var j = 1; j < files.length; j++) {
                    sel[files[j].path] = true
                }
            } else if (strategy === "keep_newest") {
                // skip last file
                for (var j = 0; j < files.length - 1; j++) {
                    sel[files[j].path] = true
                }
            }
        }
        selectedDupPaths = sel
        selectedDupCount = Object.keys(sel).length
    }

    function toggleDupSelection(path) {
        var sel = Object.assign({}, selectedDupPaths)
        if (sel[path]) {
            delete sel[path]
        } else {
            sel[path] = true
        }
        selectedDupPaths = sel
        selectedDupCount = Object.keys(sel).length
    }

    function deleteDuplicateItems() {
        if (!bridge || !bridge.deleteItems || selectedDupCount === 0 || root.isPathBlocked) return
        isDeleting = true
        var paths = Object.keys(selectedDupPaths)
        bridge.deleteItems(paths)
        isDeleting = false
        root.cleaned()
        scanDuplicates()
    }

    // ── Tab 3: Auto-Sort ────────────────────────────────────────────────────
    function executeAutoSort() {
        if (!bridge || !bridge.autoSortFolderAsync || root.isPathBlocked || root.isSorting) return
        isSorting = true
        sortResultMsg = root.sortMode === "flatten" ? "Moving files…" : "Sorting…"
        _sortRequest = _newRequest("sort")
        bridge.autoSortFolderAsync(_sortRequest, folderPath, sortMode, root.sortRecursive)
    }

    function undoFlatten() {
        if (!bridge || !bridge.undoFlattenAsync || root.isSorting) return
        isSorting = true
        sortResultMsg = "Moving files back…"
        _sortRequest = _newRequest("undo")
        bridge.undoFlattenAsync(_sortRequest, folderPath)
    }

    function _applySortResult(res) {
        isSorting = false
        if (!res) {
            sortResultMsg = "Something went wrong — see the log for details."
            return
        }
        var moved = res.moved || 0
        var warn = (res.errors && res.errors.length > 0) ? (" Warning: " + res.errors.join(", ")) : ""
        if (res.mode === "undo") {
            sortResultMsg = "Moved " + moved + " files back into their folders." + warn
            canUndoFlatten = false
        } else if (res.mode === "flatten") {
            sortResultMsg = "Moved " + moved + " files into this folder." + warn
            canUndoFlatten = !!res.undo_available || canUndoFlatten
        } else {
            sortResultMsg = "Sorted " + moved + " files into subfolders." + warn
        }
        root.organized()
    }

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#080B11"
        opacity: root.isOpen ? 0.88 : 0.0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        // Swallow clicks, hover (card tooltips behind) and the wheel
        MouseArea { anchors.fill: parent; hoverEnabled: true; onWheel: (wheel) => wheel.accepted = true }
    }

    // Modal Card
    Rectangle {
        // Heavy panel: settles in on a soft spring
        scale: root.isOpen ? 1.0 : 0.9
        Behavior on scale { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.0008 } }
        width: Math.min(840, parent.width - 40)
        height: Math.min(680, parent.height - 40)
        anchors.centerIn: parent
        radius: 12
        color: "#111520"
        border.color: "#273349"
        border.width: 1
        clip: true

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text { text: "🧹"; font.pixelSize: 22 }

                ColumnLayout {
                    spacing: 2
                    Text {
                        text: "Cleaner & Deduplicator"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 16
                        font.weight: 700
                        color: "#F8FAFC"
                    }
                    Text {
                        text: "Identifies duplicate downloads, broken zero-byte files, and auto-sorts folders into clean hierarchies"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    width: 28; height: 28; radius: 5
                    color: closeBtnMouse.containsMouse ? "#EF4444" : "#1A2234"
                    border.color: closeBtnMouse.containsMouse ? "#DC2626" : "#2E3A52"
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "✕"; font.pixelSize: 12; font.weight: Font.Bold; color: "#FFFFFF" }
                    Springy { hover: closeBtnMouse.containsMouse; pressed: closeBtnMouse.pressed }
                    MouseArea {
                        id: closeBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.close()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Close cleaner dialog without making changes"
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: "#1F283B" }

            // Safety Warning Banner (Operating System or Root Drive)
            Rectangle {
                visible: root.isPathBlocked || root.isOtherRoot
                Layout.fillWidth: true
                implicitHeight: 34
                radius: 6
                color: root.isPathBlocked ? "#380D12" : "#38230B"
                border.color: root.isPathBlocked ? "#EF4444" : "#F59E0B"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 8

                    Text {
                        text: root.isPathBlocked ? "🛡️" : "⚠️"
                        font.pixelSize: 14
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.isPathBlocked ?
                              ((root.pathSafety && root.pathSafety.message) ? ("Operating System Protection: " + root.pathSafety.message) : "Operating System Protection: Operations are permanently disabled on this path.") :
                              ("Root Drive Selected (" + (root.pathSafety ? root.pathSafety.drive_letter : "") + "\\): Operations will affect files across the entire drive volume. Exercise extreme caution.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: root.isPathBlocked ? "#FCA5A5" : "#FDE68A"
                        elide: Text.ElideRight
                    }
                }
            }

            // Tab Navigation & Recursive Checkbox
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                // Tab buttons
                Row {
                    spacing: 4

                    Rectangle {
                        implicitHeight: 30
                        implicitWidth: bTabRow.implicitWidth + 16
                        radius: 6
                        color: root.activeTab === "broken" ? "#1E2A40" : "#121722"
                        border.color: root.activeTab === "broken" ? "#EF4444" : "#253147"
                        border.width: 1

                        Row {
                            id: bTabRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: "🗑️"; font.pixelSize: 12 }
                            Text {
                                text: "Broken & 0-Byte (" + root.brokenItems.length + ")"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: root.activeTab === "broken" ? 700 : Font.Normal
                                color: root.activeTab === "broken" ? "#FCA5A5" : "#94A3B8"
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.activeTab = "broken"
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Broken & 0-Byte Scanner\nScan for corrupt 0-byte downloads, truncated files, and empty files"
                        }
                    }

                    Rectangle {
                        implicitHeight: 30
                        implicitWidth: dTabRow.implicitWidth + 16
                        radius: 6
                        color: root.activeTab === "duplicates" ? "#1E2A40" : "#121722"
                        border.color: root.activeTab === "duplicates" ? "#F59E0B" : "#253147"
                        border.width: 1

                        Row {
                            id: dTabRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: "👥"; font.pixelSize: 12 }
                            Text {
                                text: "Duplicate Finder (" + root.duplicateGroups.length + ")"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: root.activeTab === "duplicates" ? 700 : Font.Normal
                                color: root.activeTab === "duplicates" ? "#FCD34D" : "#94A3B8"
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.activeTab = "duplicates"
                                if (root.duplicateGroups.length === 0) {
                                    root.scanDuplicates()
                                }
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Duplicate File Finder\nDetect identical duplicate files across downloads by computing SHA-256 content hashes"
                        }
                    }

                    Rectangle {
                        implicitHeight: 30
                        implicitWidth: sTabRow.implicitWidth + 16
                        radius: 6
                        color: root.activeTab === "sort" ? "#1E2A40" : "#121722"
                        border.color: root.activeTab === "sort" ? "#10B981" : "#253147"
                        border.width: 1

                        Row {
                            id: sTabRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: "📂"; font.pixelSize: 12 }
                            Text {
                                text: "Auto-Sort Hierarchies"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: root.activeTab === "sort" ? 700 : Font.Normal
                                color: root.activeTab === "sort" ? "#6EE7B7" : "#94A3B8"
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.activeTab = "sort"
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Auto-Sort Hierarchies\nAutomatically organize loose files into structured subfolders by type, date, or extension"
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // Recursive Checkbox (for tabs 1 & 2)
                RowLayout {
                    visible: root.activeTab !== "sort"
                    spacing: 6
                    Layout.alignment: Qt.AlignVCenter

                    Rectangle {
                        width: 16; height: 16; radius: 3
                        color: root.recursiveScan ? "#38BDF8" : "#0D111A"
                        border.color: "#27344D"; border.width: 1
                        Text { visible: root.recursiveScan; anchors.centerIn: parent; text: "✓"; font.pixelSize: 10; font.weight: Font.Bold; color: "#0B0E14" }
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.recursiveScan = !root.recursiveScan
                                if (root.activeTab === "broken") root.scanBroken()
                                else if (root.activeTab === "duplicates") root.scanDuplicates()
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Scan subfolders recursively\nWhen checked, scans all nested subfolders instead of only the top-level directory."
                        }
                    }

                    Text {
                        text: "Scan subfolders recursively"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.recursiveScan = !root.recursiveScan
                                if (root.activeTab === "broken") root.scanBroken()
                                else if (root.activeTab === "duplicates") root.scanDuplicates()
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Scan subfolders recursively\nWhen checked, scans all nested subfolders instead of only the top-level directory."
                        }
                    }
                }
            }

            // ── TAB CONTENT ─────────────────────────────────────────────────

            // TAB 1: BROKEN & ZERO-BYTE FILES
            CleanerBrokenTab { modal: root }

            // TAB 2: DUPLICATE FINDER
            CleanerDuplicatesTab { modal: root }

            // TAB 3: AUTO-SORT HIERARCHIES
            CleanerAutoSortTab { modal: root }
        }
    }
}
