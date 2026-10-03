import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

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
    property bool isScanning: false
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
        isOpen = false
    }

    // ── Tab 1: Broken Files ─────────────────────────────────────────────────
    function scanBroken() {
        if (!bridge || !bridge.scanBrokenFilesAsync) return
        isScanning = true
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
        isScanning = false
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
        if (!bridge || !bridge.scanDuplicatesAsync) return
        isScanning = true
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
        isScanning = false
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
            Item {
                visible: root.activeTab === "broken"
                Layout.fillWidth: true
                Layout.fillHeight: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 6
                        color: "#0A0D15"
                        border.color: "#1E273A"
                        border.width: 1
                        clip: true

                        // Empty State
                        Text {
                            anchors.centerIn: parent
                            visible: root.isScanning && root.activeTab === "broken"
                            text: "Scanning…"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#94A3B8"
                        }
                        Item {
                            anchors.centerIn: parent
                            visible: root.brokenItems.length === 0 && !root.isScanning
                            ColumnLayout {
                                spacing: 6
                                anchors.centerIn: parent
                                Text { text: "✨"; font.pixelSize: 28; Layout.alignment: Qt.AlignHCenter }
                                Text {
                                    text: "No broken or 0-byte files found in this folder!"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    font.weight: 600
                                    color: "#10B981"
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }

                        ListView {
                            id: brokenListView
                            visible: root.brokenItems.length > 0
                            anchors.fill: parent
                            anchors.margins: 4
                            spacing: 2
                            model: root.brokenItems
                            clip: true

                            delegate: Rectangle {
                                width: brokenListView.width
                                height: 32
                                radius: 4
                                color: root.selectedBrokenPaths[modelData.path] ? "#1F1A26" : (index % 2 === 0 ? "#111623" : "#0D111C")
                                border.color: root.selectedBrokenPaths[modelData.path] ? "#EF4444" : "transparent"
                                border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 8

                                    // Checkbox
                                    Rectangle {
                                        width: 16; height: 16; radius: 3
                                        color: root.selectedBrokenPaths[modelData.path] ? "#EF4444" : "#161D2B"
                                        border.color: "#374151"; border.width: 1
                                        Text { visible: Boolean(root.selectedBrokenPaths && root.selectedBrokenPaths[modelData.path]); anchors.centerIn: parent; text: "✓"; font.pixelSize: 10; font.weight: Font.Bold; color: "#FFFFFF" }
                                    }

                                    Text {
                                        text: modelData.name
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: "#F8FAFC"
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }

                                    Rectangle {
                                        implicitHeight: 20
                                        implicitWidth: bTypeTxt.implicitWidth + 10
                                        radius: 4
                                        color: "#3B1219"
                                        border.color: "#EF4444"
                                        border.width: 1
                                        Text {
                                            id: bTypeTxt
                                            anchors.centerIn: parent
                                            text: modelData.type_label || modelData.type
                                            font.pixelSize: 9
                                            font.weight: 600
                                            color: "#FCA5A5"
                                        }
                                    }

                                    Text {
                                        text: modelData.size > 0 ? root.formatBytes(modelData.size) : "0 B"
                                        font.family: "Segoe UI, monospace"
                                        font.pixelSize: 10
                                        color: "#94A3B8"
                                        Layout.preferredWidth: 60
                                        horizontalAlignment: Text.AlignRight
                                    }
                                }

                                Springy { hover: bItemMouse.containsMouse; pressed: bItemMouse.pressed }
                                MouseArea {
                                    id: bItemMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.toggleBrokenSelection(modelData.path)
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 350
                                    ToolTip.text: (root.selectedBrokenPaths[modelData.path] ? "☑ Marked for deletion: " : "☐ Click to select: ") + modelData.path + "\nSize: " + (modelData.size > 0 ? root.formatBytes(modelData.size) : "0 B")
                                }
                            }
                        }
                    }

                    // Broken items actions bar
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Rectangle {
                            implicitHeight: 26; implicitWidth: 72; radius: 4
                            color: "#182030"; border.color: "#28354E"; border.width: 1
                            Text { anchors.centerIn: parent; text: "Select All"; font.pixelSize: 10; color: "#94A3B8" }
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.selectAllBroken(true)
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Select all detected broken and 0-byte files for cleanup"
                            }
                        }
                        Rectangle {
                            implicitHeight: 26; implicitWidth: 80; radius: 4
                            color: "#182030"; border.color: "#28354E"; border.width: 1
                            Text { anchors.centerIn: parent; text: "Deselect All"; font.pixelSize: 10; color: "#94A3B8" }
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.selectAllBroken(false)
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Uncheck all files in the broken files list"
                            }
                        }

                        Item { Layout.fillWidth: true }

                        Rectangle {
                            implicitHeight: 32
                            implicitWidth: cleanBtnText.implicitWidth + 20
                            radius: 6
                            color: root.selectedBrokenCount > 0 ? "#DC2626" : "#222634"
                            border.color: root.selectedBrokenCount > 0 ? "#EF4444" : "#323747"
                            border.width: 1
                            opacity: root.selectedBrokenCount > 0 ? 1.0 : 0.5

                            Text {
                                id: cleanBtnText
                                anchors.centerIn: parent
                                text: "Clean Selected (" + root.selectedBrokenCount + ")"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 700
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: root.selectedBrokenCount > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: root.deleteBrokenItems()
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: root.selectedBrokenCount > 0 ? ("Move " + root.selectedBrokenCount + " selected broken file(s) to the Recycle Bin.") : "No broken files selected for deletion. Check files above to enable cleanup."
                            }
                        }
                    }
                }
            }

            // TAB 2: DUPLICATE FINDER
            Item {
                visible: root.activeTab === "duplicates"
                Layout.fillWidth: true
                Layout.fillHeight: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    // Wasted Storage Alert Banner
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 34
                        radius: 6
                        color: root.totalWastedBytes > 0 ? "#2B1D0E" : "#131A28"
                        border.color: root.totalWastedBytes > 0 ? "#F59E0B" : "#243248"
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 8

                            Text { text: root.isScanning ? "⏳" : (root.totalWastedBytes > 0 ? "⚠️" : "✨"); font.pixelSize: 14 }
                            Text {
                                text: root.isScanning ? "Scanning for duplicates…" : (root.totalWastedBytes > 0 ?
                                      ("Found " + root.duplicateGroups.length + " duplicate groups — Reclaim " + root.formatBytes(root.totalWastedBytes) + " of disk space") :
                                      "No duplicate files detected in this folder!")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: root.totalWastedBytes > 0 ? "#FCD34D" : "#38BDF8"
                                Layout.fillWidth: true
                            }

                            // Strategy buttons
                            Rectangle {
                                visible: root.duplicateGroups.length > 0
                                implicitHeight: 22; implicitWidth: 84; radius: 4
                                color: "#1E273A"; border.color: "#38BDF8"; border.width: 1
                                Text { anchors.centerIn: parent; text: "Keep Oldest"; font.pixelSize: 9; font.weight: 600; color: "#38BDF8" }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.selectDuplicatesStrategy("keep_oldest")
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 250
                                    ToolTip.text: "Keep Oldest Copies\nAutomatically marks newer duplicates for deletion, keeping the earliest downloaded file in each set."
                                }
                            }

                            Rectangle {
                                visible: root.duplicateGroups.length > 0
                                implicitHeight: 22; implicitWidth: 84; radius: 4
                                color: "#1E273A"; border.color: "#38BDF8"; border.width: 1
                                Text { anchors.centerIn: parent; text: "Keep Newest"; font.pixelSize: 9; font.weight: 600; color: "#38BDF8" }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.selectDuplicatesStrategy("keep_newest")
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 250
                                    ToolTip.text: "Keep Newest Copies\nAutomatically marks older duplicates for deletion, keeping the most recently downloaded file in each set."
                                }
                            }
                        }
                    }

                    // Duplicates List
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 6
                        color: "#0A0D15"
                        border.color: "#1E273A"
                        border.width: 1
                        clip: true

                        ListView {
                            id: dupListView
                            anchors.fill: parent
                            anchors.margins: 4
                            spacing: 6
                            model: root.duplicateGroups
                            clip: true

                            delegate: Rectangle {
                                width: dupListView.width
                                implicitHeight: dupCol.implicitHeight + 12
                                radius: 6
                                color: "#121724"
                                border.color: "#222D42"
                                border.width: 1

                                ColumnLayout {
                                    id: dupCol
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 4

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text {
                                            text: "Duplicate Set #" + (index + 1) + " (SHA: " + modelData.hash + ")"
                                            font.family: "Segoe UI, monospace"
                                            font.pixelSize: 10
                                            font.weight: 700
                                            color: "#F59E0B"
                                        }
                                        Item { Layout.fillWidth: true }
                                        Text {
                                            text: root.formatBytes(modelData.size) + " each • " + modelData.count + " copies"
                                            font.family: "Segoe UI, monospace"
                                            font.pixelSize: 10
                                            color: "#94A3B8"
                                        }
                                    }

                                    Repeater {
                                        model: modelData.files
                                        delegate: Rectangle {
                                            Layout.fillWidth: true
                                            height: 24
                                            radius: 3
                                            color: root.selectedDupPaths[modelData.path] ? "#2A181C" : "#0A0E17"
                                            border.color: root.selectedDupPaths[modelData.path] ? "#EF4444" : "#1A2234"
                                            border.width: 1

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.leftMargin: 6
                                                anchors.rightMargin: 6
                                                spacing: 6

                                                Rectangle {
                                                    width: 14; height: 14; radius: 3
                                                    color: root.selectedDupPaths[modelData.path] ? "#EF4444" : "#161D2B"
                                                    border.color: "#374151"; border.width: 1
                                                    Text { visible: Boolean(root.selectedDupPaths && root.selectedDupPaths[modelData.path]); anchors.centerIn: parent; text: "✓"; font.pixelSize: 9; font.weight: Font.Bold; color: "#FFFFFF" }
                                                }

                                                Text {
                                                    text: modelData.rel_path || modelData.name
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 10
                                                    color: root.selectedDupPaths[modelData.path] ? "#FCA5A5" : "#E2E8F0"
                                                    elide: Text.ElideMiddle
                                                    Layout.fillWidth: true
                                                }
                                            }

                                            Springy { hover: dupFileMouse.containsMouse; pressed: dupFileMouse.pressed }
                                            MouseArea {
                                                id: dupFileMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: root.toggleDupSelection(modelData.path)
                                                ToolTip.visible: containsMouse
                                                ToolTip.delay: 350
                                                ToolTip.text: (root.selectedDupPaths[modelData.path] ? "🗑️ Marked for deletion:\n" : "💾 Keeping file:\n") + modelData.path + "\nClick to toggle keep/delete"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Duplicates Action Bar
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: root.selectedDupCount + " duplicate files selected for deletion"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }

                        Item { Layout.fillWidth: true }

                        Rectangle {
                            implicitHeight: 32
                            implicitWidth: delDupBtnText.implicitWidth + 20
                            radius: 6
                            color: root.selectedDupCount > 0 ? "#DC2626" : "#222634"
                            border.color: root.selectedDupCount > 0 ? "#EF4444" : "#323747"
                            border.width: 1
                            opacity: root.selectedDupCount > 0 ? 1.0 : 0.5

                            Text {
                                id: delDupBtnText
                                anchors.centerIn: parent
                                text: "Delete Selected Duplicates (" + root.selectedDupCount + ")"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 700
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: root.selectedDupCount > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: root.deleteDuplicateItems()
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: root.selectedDupCount > 0 ? ("Move " + root.selectedDupCount + " selected duplicate file(s) to the Recycle Bin. Empty the Recycle Bin to reclaim the disk space.") : "No duplicates selected for deletion. Choose a strategy or click items above."
                            }
                        }
                    }
                }
            }

            // TAB 3: AUTO-SORT HIERARCHIES
            Item {
                visible: root.activeTab === "sort"
                Layout.fillWidth: true
                Layout.fillHeight: true

                Flickable {
                    anchors.fill: parent
                    contentHeight: sortColumn.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    ColumnLayout {
                        id: sortColumn
                        width: parent.width
                        spacing: 8

                        Text {
                            text: "Choose how to automatically organize loose files in this folder into clean subfolders:"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#E2E8F0"
                        }

                        // Mode 1: By Type
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 48
                            radius: 8
                            color: root.sortMode === "type" ? "#1B2A40" : "#111622"
                            border.color: root.sortMode === "type" ? "#38BDF8" : "#232F45"
                            border.width: 1

                            Text {
                                id: sortIcon1
                                anchors.left: parent.left
                                anchors.leftMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                text: "🖼️"
                                font.pixelSize: 18
                            }

                            Rectangle {
                                id: sortCircle1
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                width: 18; height: 18; radius: 9
                                color: root.sortMode === "type" ? "#38BDF8" : "transparent"
                                border.color: "#38BDF8"; border.width: 1.5
                            }

                            ColumnLayout {
                                anchors.left: sortIcon1.right
                                anchors.leftMargin: 10
                                anchors.right: sortCircle1.left
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 1
                                Text { text: "Sort by File Type"; font.bold: true; font.pixelSize: 11; color: "#F8FAFC" }
                                Text { text: "Groups into Images/, Videos/, Audio/, Archives/, Documents/, and Other/"; font.pixelSize: 10; color: "#94A3B8"; elide: Text.ElideRight; Layout.fillWidth: true }
                            }

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.sortMode = "type"
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Sort by File Type\nAutomatically creates Images/, Videos/, Audio/, Archives/, and Documents/ folders and sorts loose files into them."
                            }
                        }

                        // Mode 2: By Date
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 48
                            radius: 8
                            color: root.sortMode === "date" ? "#1B2A40" : "#111622"
                            border.color: root.sortMode === "date" ? "#38BDF8" : "#232F45"
                            border.width: 1

                            Text {
                                id: sortIcon2
                                anchors.left: parent.left
                                anchors.leftMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                text: "📅"
                                font.pixelSize: 18
                            }

                            Rectangle {
                                id: sortCircle2
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                width: 18; height: 18; radius: 9
                                color: root.sortMode === "date" ? "#38BDF8" : "transparent"
                                border.color: "#38BDF8"; border.width: 1.5
                            }

                            ColumnLayout {
                                anchors.left: sortIcon2.right
                                anchors.leftMargin: 10
                                anchors.right: sortCircle2.left
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 1
                                Text { text: "Sort by Date Modified"; font.bold: true; font.pixelSize: 11; color: "#F8FAFC" }
                                Text { text: "Groups files into YYYY-MM/ subfolders based on file modification timestamps"; font.pixelSize: 10; color: "#94A3B8"; elide: Text.ElideRight; Layout.fillWidth: true }
                            }

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.sortMode = "date"
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Sort by Date Modified\nGroups files into YYYY-MM subfolders (e.g. 2026-09/, 2026-10/) based on file modification timestamps."
                            }
                        }

                        // Mode 3: By Extension
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 48
                            radius: 8
                            color: root.sortMode === "extension" ? "#1B2A40" : "#111622"
                            border.color: root.sortMode === "extension" ? "#38BDF8" : "#232F45"
                            border.width: 1

                            Text {
                                id: sortIcon3
                                anchors.left: parent.left
                                anchors.leftMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                text: "🏷️"
                                font.pixelSize: 18
                            }

                            Rectangle {
                                id: sortCircle3
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                width: 18; height: 18; radius: 9
                                color: root.sortMode === "extension" ? "#38BDF8" : "transparent"
                                border.color: "#38BDF8"; border.width: 1.5
                            }

                            ColumnLayout {
                                anchors.left: sortIcon3.right
                                anchors.leftMargin: 10
                                anchors.right: sortCircle3.left
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 1
                                Text { text: "Sort by Extension"; font.bold: true; font.pixelSize: 11; color: "#F8FAFC" }
                                Text { text: "Groups files into PNG/, JPG/, MP4/, etc. based on file extension"; font.pixelSize: 10; color: "#94A3B8"; elide: Text.ElideRight; Layout.fillWidth: true }
                            }

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.sortMode = "extension"
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Sort by Extension\nGroups files into subfolders named after their extension (e.g. PNG/, JPG/, MP4/, ZIP/)."
                            }
                        }

                        // Option 4: Dump / Flatten Everything into Single Folder
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 48
                            radius: 8
                            color: root.sortMode === "flatten" ? "#1B2234" : "#0F1420"
                            border.color: root.sortMode === "flatten" ? "#F59E0B" : "#212B3D"
                            border.width: 1

                            Text {
                                id: sortIcon4
                                anchors.left: parent.left
                                anchors.leftMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                text: "📦"
                                font.pixelSize: 18
                            }

                            Rectangle {
                                id: sortCircle4
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                width: 18; height: 18; radius: 9
                                color: root.sortMode === "flatten" ? "#F59E0B" : "transparent"
                                border.color: "#F59E0B"; border.width: 1.5
                            }

                            ColumnLayout {
                                anchors.left: sortIcon4.right
                                anchors.leftMargin: 10
                                anchors.right: sortCircle4.left
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 1
                                Text { text: "Dump Everything into Single Folder (Flatten)"; font.bold: true; font.pixelSize: 11; color: "#F8FAFC" }
                                Text { text: "Extracts all files from subfolders into this main folder and cleans up empty folders"; font.pixelSize: 10; color: "#94A3B8"; elide: Text.ElideRight; Layout.fillWidth: true }
                            }

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.sortMode = "flatten"
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Dump Everything into Single Folder\nMoves all files nested in any subfolder directly into this main folder. Automatically appends (1), (2) to duplicate names and cleans up empty subfolders."
                            }
                        }

                        // Recursive Subfolders Option (relevant for categorization modes)
                        Rectangle {
                            visible: root.sortMode !== "flatten"
                            Layout.fillWidth: true
                            implicitHeight: 38
                            radius: 8
                            color: root.sortRecursive ? "#16253B" : "#0F1420"
                            border.color: root.sortRecursive ? "#38BDF8" : "#212B3D"
                            border.width: 1

                            Rectangle {
                                id: recCheckbox
                                anchors.left: parent.left
                                anchors.leftMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                width: 16
                                height: 16
                                radius: 4
                                color: root.sortRecursive ? "#38BDF8" : "transparent"
                                border.color: root.sortRecursive ? "#38BDF8" : "#475569"
                                border.width: 1.5

                                Text {
                                    anchors.centerIn: parent
                                    text: "✓"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: "#0F172A"
                                    visible: root.sortRecursive
                                }
                            }

                            ColumnLayout {
                                anchors.left: recCheckbox.right
                                anchors.leftMargin: 10
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 1

                                Text {
                                    text: "Apply recursively to all post subfolders"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: "#F8FAFC"
                                }
                                Text {
                                    text: "Sorts attachments inside each individual post folder (e.g. Creator/[Post 1]/Images/, Creator/[Post 2]/Videos/)"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 9
                                    color: "#94A3B8"
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.sortRecursive = !root.sortRecursive
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Recursive Subfolder Sorting\nWhen enabled, iterates through all post subfolders and categorizes loose attachments into Images/, Videos/, etc. inside each post folder."
                            }
                        }

                        // Spacing before organize action
                        Item { Layout.preferredHeight: 4 }

                        // Organize Button
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 38
                            radius: 6
                            color: root.isPathBlocked ? "#1E2433" : (root.sortMode === "flatten" ? (orgBtnMouse.containsMouse ? "#D97706" : "#B45309") : (orgBtnMouse.containsMouse ? "#059669" : "#047857"))
                            border.color: root.isPathBlocked ? "#2D3748" : (root.sortMode === "flatten" ? "#F59E0B" : "#10B981")
                            border.width: 1
                            opacity: root.isPathBlocked ? 0.35 : 1.0

                            Text {
                                anchors.centerIn: parent
                                text: root.isPathBlocked ? "Organizing Disabled on System Root" : (root.isSorting ? "Working…" : (root.sortMode === "flatten" ? "Dump & Flatten All Files Now" : "Organize Folder Now"))
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: 700
                                color: "#FFFFFF"
                            }
                            Springy { hover: orgBtnMouse.containsMouse; pressed: orgBtnMouse.pressed }
                            MouseArea {
                                id: orgBtnMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: root.isPathBlocked ? Qt.ForbiddenCursor : Qt.PointingHandCursor
                                onClicked: {
                                    if (!root.isPathBlocked) {
                                        root.executeAutoSort()
                                    }
                                }
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: root.isPathBlocked ?
                                    ("Action Blocked: Cannot execute Auto-Sort on Windows system drive root (" + (root.pathSafety ? root.pathSafety.drive_letter : "C:") + "\\)") :
                                    (root.sortMode === "flatten" ?
                                        "Dump & Flatten All Files Now\nMoves all files from subfolders into this main folder and removes empty subfolders." :
                                        ("Organize Folder Now\nMove loose files in this folder into clean subfolders using the '" + (root.sortMode === "type" ? "File Type" : (root.sortMode === "date" ? "Date Modified" : "Extension")) + "' strategy." + (root.sortRecursive ? " (Recursive: enabled)" : "")))
                            }
                        }

                        // Sort Result Feedback
                        Text {
                            visible: root.sortResultMsg.length > 0
                            text: root.sortResultMsg
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#10B981"
                            wrapMode: Text.Wrap
                            horizontalAlignment: Text.AlignHCenter
                            Layout.fillWidth: true
                        }

                        // Undo the last Flatten of this folder
                        Rectangle {
                            visible: root.canUndoFlatten
                            Layout.alignment: Qt.AlignHCenter
                            implicitHeight: 28
                            implicitWidth: undoFlattenLabel.implicitWidth + 28
                            radius: 6
                            color: undoFlattenMouse.containsMouse ? "#1E273A" : "transparent"
                            border.color: "#F59E0B"
                            border.width: 1
                            opacity: root.isSorting ? 0.5 : 1.0
                            Text {
                                id: undoFlattenLabel
                                anchors.centerIn: parent
                                text: "Undo flatten"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: "#FCD34D"
                            }
                            MouseArea {
                                id: undoFlattenMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.undoFlatten()
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Move the files of the last flatten back into the folders they came from."
                            }
                        }

                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }
}
