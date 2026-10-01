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

    anchors.fill: parent
    z: 9998
    visible: isOpen

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
        brokenItems = []
        selectedBrokenPaths = {}
        selectedBrokenCount = 0
        duplicateGroups = []
        selectedDupPaths = {}
        selectedDupCount = 0
        totalWastedBytes = 0
        sortResultMsg = ""
        isOpen = true
        scanBroken()
    }

    function close() {
        isOpen = false
    }

    // ── Tab 1: Broken Files ─────────────────────────────────────────────────
    function scanBroken() {
        if (!bridge || !bridge.scanBrokenFiles) return
        isScanning = true
        var items = bridge.scanBrokenFiles(folderPath, recursiveScan) || []
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
        if (!bridge || !bridge.deleteItems || selectedBrokenCount === 0) return
        isDeleting = true
        var paths = Object.keys(selectedBrokenPaths)
        bridge.deleteItems(paths)
        isDeleting = false
        root.cleaned()
        scanBroken()
    }

    // ── Tab 2: Duplicate Files ──────────────────────────────────────────────
    function scanDuplicates() {
        if (!bridge || !bridge.scanDuplicates) return
        isScanning = true
        var groups = bridge.scanDuplicates(folderPath, recursiveScan) || []
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
        if (!bridge || !bridge.deleteItems || selectedDupCount === 0) return
        isDeleting = true
        var paths = Object.keys(selectedDupPaths)
        bridge.deleteItems(paths)
        isDeleting = false
        root.cleaned()
        scanDuplicates()
    }

    // ── Tab 3: Auto-Sort ────────────────────────────────────────────────────
    function executeAutoSort() {
        if (!bridge || !bridge.autoSortFolder) return
        var res = bridge.autoSortFolder(folderPath, sortMode)
        if (res) {
            sortResultMsg = "Successfully sorted " + (res.moved || 0) + " files into clean subfolders!"
            root.organized()
        }
    }

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#080B11"
        opacity: root.isOpen ? 0.88 : 0.0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        MouseArea { anchors.fill: parent }
    }

    // Modal Card
    Rectangle {
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
                        Item {
                            anchors.centerIn: parent
                            visible: root.brokenItems.length === 0
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
                                        Text { visible: root.selectedBrokenPaths[modelData.path]; anchors.centerIn: parent; text: "✓"; font.pixelSize: 10; font.weight: Font.Bold; color: "#FFFFFF" }
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
                                ToolTip.text: root.selectedBrokenCount > 0 ? ("Permanently delete " + root.selectedBrokenCount + " selected broken file(s) from disk.") : "No broken files selected for deletion. Check files above to enable cleanup."
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

                            Text { text: root.totalWastedBytes > 0 ? "⚠️" : "✨"; font.pixelSize: 14 }
                            Text {
                                text: root.totalWastedBytes > 0 ?
                                      ("Found " + root.duplicateGroups.length + " duplicate groups — Reclaim " + root.formatBytes(root.totalWastedBytes) + " of disk space") :
                                      "No duplicate files detected in this folder!"
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
                                                    Text { visible: root.selectedDupPaths[modelData.path]; anchors.centerIn: parent; text: "✓"; font.pixelSize: 9; font.weight: Font.Bold; color: "#FFFFFF" }
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
                                ToolTip.text: root.selectedDupCount > 0 ? ("Permanently delete " + root.selectedDupCount + " selected duplicate file(s) to reclaim disk space.") : "No duplicates selected for deletion. Choose a strategy or click items above."
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

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 14

                    Text {
                        text: "Choose how to automatically organize loose files in this folder into clean subfolders:"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#E2E8F0"
                    }

                    // Mode 1: By Type
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 56
                        radius: 8
                        color: root.sortMode === "type" ? "#1B2A40" : "#111622"
                        border.color: root.sortMode === "type" ? "#38BDF8" : "#232F45"
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 12

                            Text { text: "🖼️"; font.pixelSize: 20 }
                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Text { text: "Sort by File Type"; font.bold: true; font.pixelSize: 12; color: "#F8FAFC" }
                                Text { text: "Groups into Images/, Videos/, Audio/, Archives/, Documents/, and Other/"; font.pixelSize: 10; color: "#94A3B8" }
                            }
                            Rectangle {
                                width: 18; height: 18; radius: 9
                                color: root.sortMode === "type" ? "#38BDF8" : "transparent"
                                border.color: "#38BDF8"; border.width: 1.5
                            }
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
                        implicitHeight: 56
                        radius: 8
                        color: root.sortMode === "date" ? "#1B2A40" : "#111622"
                        border.color: root.sortMode === "date" ? "#38BDF8" : "#232F45"
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 12

                            Text { text: "📅"; font.pixelSize: 20 }
                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Text { text: "Sort by Date Modified"; font.bold: true; font.pixelSize: 12; color: "#F8FAFC" }
                                Text { text: "Groups files into YYYY-MM/ subfolders based on file modification timestamps"; font.pixelSize: 10; color: "#94A3B8" }
                            }
                            Rectangle {
                                width: 18; height: 18; radius: 9
                                color: root.sortMode === "date" ? "#38BDF8" : "transparent"
                                border.color: "#38BDF8"; border.width: 1.5
                            }
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
                        implicitHeight: 56
                        radius: 8
                        color: root.sortMode === "extension" ? "#1B2A40" : "#111622"
                        border.color: root.sortMode === "extension" ? "#38BDF8" : "#232F45"
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 12

                            Text { text: "🏷️"; font.pixelSize: 20 }
                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Text { text: "Sort by Extension"; font.bold: true; font.pixelSize: 12; color: "#F8FAFC" }
                                Text { text: "Groups files into PNG/, JPG/, MP4/, etc. based on file extension"; font.pixelSize: 10; color: "#94A3B8" }
                            }
                            Rectangle {
                                width: 18; height: 18; radius: 9
                                color: root.sortMode === "extension" ? "#38BDF8" : "transparent"
                                border.color: "#38BDF8"; border.width: 1.5
                            }
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

                    Item { Layout.fillHeight: true }

                    // Sort Result Feedback
                    Text {
                        visible: root.sortResultMsg.length > 0
                        text: root.sortResultMsg
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#10B981"
                        Layout.alignment: Qt.AlignHCenter
                    }

                    // Organize Button
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 38
                        radius: 6
                        color: orgBtnMouse.containsMouse ? "#059669" : "#047857"
                        border.color: "#10B981"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "Organize Folder Now"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 700
                            color: "#FFFFFF"
                        }
                        MouseArea {
                            id: orgBtnMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.executeAutoSort()
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Organize Folder Now\nMove loose files in this folder into clean subfolders using the '" + (root.sortMode === "type" ? "File Type" : (root.sortMode === "date" ? "Date Modified" : "Extension")) + "' strategy."
                        }
                    }
                }
            }
        }
    }
}
