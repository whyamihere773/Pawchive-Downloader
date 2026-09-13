import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: root

    property var bridge: null
    property var decompressor: bridge ? bridge.decompressorBridge : null

    // Search filter
    property string searchText: ""

    // Disk check modal state
    property var diskCheckData: []
    property bool showDiskModal: false

    // Current live extraction state
    property real overallProgress: 0.0
    property string currentArchiveName: ""
    property real currentArchiveProgress: 0.0
    property string etaText: "--"
    property string speedText: "--"

    readonly property bool isNarrow: root.width < 760
    readonly property bool isVeryNarrow: root.width < 520

    // Custom themed stepper component matching the Pawchive dark cyber aesthetic
    component NumberStepper: Rectangle {
        id: stepper
        property int from: 1
        property int to: 10
        property int value: 1
        signal valueModified(int val)

        implicitWidth: 88
        implicitHeight: 26
        radius: 6
        color: "#111827"
        border.color: "#283042"
        border.width: 1

        RowLayout {
            anchors.fill: parent
            spacing: 0

            // Minus button
            Rectangle {
                Layout.preferredWidth: 26
                Layout.fillHeight: true
                radius: 5
                color: minusMouse.pressed ? "#1E293B" : (minusMouse.containsMouse ? "#1F293D" : "transparent")
                opacity: stepper.value > stepper.from ? 1.0 : 0.35

                Text {
                    anchors.centerIn: parent
                    text: "−"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    color: minusMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                }

                MouseArea {
                    id: minusMouse
                    anchors.fill: parent
                    hoverEnabled: stepper.value > stepper.from
                    cursorShape: stepper.value > stepper.from ? Qt.PointingHandCursor : Qt.ArrowCursor
                    enabled: stepper.value > stepper.from
                    onClicked: {
                        var v = Math.max(stepper.from, stepper.value - 1);
                        stepper.value = v;
                        stepper.valueModified(v);
                    }
                }
            }

            // Value text
            Text {
                Layout.fillWidth: true
                Layout.fillHeight: true
                text: stepper.value
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: "#F1F5F9"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            // Plus button
            Rectangle {
                Layout.preferredWidth: 26
                Layout.fillHeight: true
                radius: 5
                color: plusMouse.pressed ? "#1E293B" : (plusMouse.containsMouse ? "#1F293D" : "transparent")
                opacity: stepper.value < stepper.to ? 1.0 : 0.35

                Text {
                    anchors.centerIn: parent
                    text: "+"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: plusMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                }

                MouseArea {
                    id: plusMouse
                    anchors.fill: parent
                    hoverEnabled: stepper.value < stepper.to
                    cursorShape: stepper.value < stepper.to ? Qt.PointingHandCursor : Qt.ArrowCursor
                    enabled: stepper.value < stepper.to
                    onClicked: {
                        var v = Math.min(stepper.to, stepper.value + 1);
                        stepper.value = v;
                        stepper.valueModified(v);
                    }
                }
            }
        }
    }

    function tr(key, def) {
        if (bridge && typeof bridge.tr === "function") {
            var val = bridge.tr(key);
            if (val && val !== key) return val;
        }
        return def;
    }

    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "0 B";
        var k = 1024;
        var sizes = ["B", "KB", "MB", "GB", "TB"];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        if (i >= sizes.length) i = sizes.length - 1;
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    }

    property var collapsedCreators: ({})

    // Stable unique key per group — uses scan_root (exposed as 'directory' in groupedItemsJson)
    function groupKey(grp) {
        return (grp.creator || "") + "|" + (grp.directory || "");
    }

    function isCreatorCollapsed(grp) {
        return !!root.collapsedCreators[root.groupKey(grp)];
    }

    function toggleCreatorCollapse(grp) {
        var key = root.groupKey(grp);
        var copy = Object.assign({}, root.collapsedCreators);
        if (copy[key]) {
            delete copy[key];
        } else {
            copy[key] = true;
        }
        root.collapsedCreators = copy;
    }

    function expandAllCreators() {
        root.collapsedCreators = {};
    }

    function collapseAllCreators() {
        var copy = {};
        for (var i = 0; i < root.groupedItems.length; i++) {
            copy[root.groupKey(root.groupedItems[i])] = true;
        }
        root.collapsedCreators = copy;
    }

    function parseItems() {
        if (!decompressor || !decompressor.itemsJson) return [];
        try {
            var all = JSON.parse(decompressor.itemsJson);
            if (!root.searchText) return all;
            var q = root.searchText.toLowerCase();
            return all.filter(function(item) {
                return (item.filename && item.filename.toLowerCase().indexOf(q) !== -1) ||
                       (item.creator && item.creator.toLowerCase().indexOf(q) !== -1) ||
                       (item.directory && item.directory.toLowerCase().indexOf(q) !== -1);
            });
        } catch (e) {
            return [];
        }
    }

    function parseGroupedItems() {
        if (!decompressor || !decompressor.groupedItemsJson) return [];
        try {
            var rawGroups = JSON.parse(decompressor.groupedItemsJson);
            if (!root.searchText) return rawGroups;
            var q = root.searchText.toLowerCase();
            var filtered = [];
            for (var i = 0; i < rawGroups.length; i++) {
                var grp = rawGroups[i];
                var grpMatch = (grp.creator && grp.creator.toLowerCase().indexOf(q) !== -1);
                var matchedItems = [];
                for (var j = 0; j < grp.items.length; j++) {
                    var itm = grp.items[j];
                    if (grpMatch || (itm.filename && itm.filename.toLowerCase().indexOf(q) !== -1) ||
                        (itm.directory && itm.directory.toLowerCase().indexOf(q) !== -1)) {
                        matchedItems.push(itm);
                    }
                }
                if (matchedItems.length > 0) {
                    var newGrp = Object.assign({}, grp);
                    newGrp.items = matchedItems;
                    filtered.push(newGrp);
                }
            }
            return filtered;
        } catch (e) {
            return [];
        }
    }

    property var itemsList: parseItems()
    property var groupedItems: parseGroupedItems()

    Connections {
        target: decompressor
        function onItemsChanged() {
            root.itemsList = root.parseItems();
            root.groupedItems = root.parseGroupedItems();
        }
        function onDiskCheckCompleted(jsonResults) {
            try {
                root.diskCheckData = JSON.parse(jsonResults);
                root.showDiskModal = true;
            } catch (e) {
                console.error("Error parsing disk check data", e);
            }
        }
        function onExtractionStarted() {
            root.overallProgress = 0.0;
            root.currentArchiveName = "";
            root.currentArchiveProgress = 0.0;
            root.etaText = "--";
            root.speedText = "--";
        }
        function onExtractionProgress(overall, curName, curPct, eta, speed) {
            root.overallProgress = overall;
            root.currentArchiveName = curName;
            root.currentArchiveProgress = curPct;
            root.etaText = eta;
            root.speedText = speed;
        }
        function onItemUpdated(itemId, status, progress, errMsg) {
            root.itemsList = root.parseItems();
            root.groupedItems = root.parseGroupedItems();
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // ══════════════════════════════════════════════════════════════════════
        // ── TOP CONTROLS & HEADER CARD ────────────────────────────────────────
        // ══════════════════════════════════════════════════════════════════════
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: headerCol.implicitHeight + 24
            radius: 12
            color: "#0F141C"
            border.color: "#1E2638"
            border.width: 1

            // Cyber-styled option checkbox for "Delete archive after successful extraction"
            component DeleteArchiveOption: MouseArea {
                id: delMouse
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                implicitHeight: Math.max(22, delRow.implicitHeight)
                implicitWidth: delRow.implicitWidth
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: root.tr("decompressor_delete_tip", "Safe deletion: original archive is deleted ONLY if 7-Zip exits with 0 errors.")
                onClicked: {
                    if (decompressor) decompressor.deleteAfter = !decompressor.deleteAfter;
                }

                RowLayout {
                    id: delRow
                    anchors.fill: parent
                    spacing: 8

                    Rectangle {
                        width: 18
                        height: 18
                        radius: 4
                        color: (decompressor && decompressor.deleteAfter) ? "#EF4444" : "#111827"
                        border.color: (decompressor && decompressor.deleteAfter) ? "#F87171" : (delMouse.containsMouse ? "#64748B" : "#334155")
                        border.width: (decompressor && decompressor.deleteAfter) ? 1.5 : 1

                        Text {
                            anchors.centerIn: parent
                            text: "✓"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                            visible: decompressor && decompressor.deleteAfter
                        }
                    }

                    Text {
                        text: root.tr("decompressor_delete_opt", "Delete archive after successful extraction")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        color: decompressor && decompressor.deleteAfter ? "#FCA5A5" : (delMouse.containsMouse ? "#CBD5E1" : "#94A3B8")
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            ColumnLayout {
                id: headerCol
                anchors.fill: parent
                anchors.margins: 14
                spacing: 12

                // Row 1: Title and (when wide) Action Buttons
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: "📦"
                        font.pixelSize: 22
                        Layout.alignment: Qt.AlignVCenter
                    }

                    ColumnLayout {
                        spacing: 2
                        Layout.fillWidth: true

                        Text {
                            text: root.tr("tab_bulk_decompressor", "Bulk Decompressor")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 15
                            font.weight: 600
                            color: "#F1F5F9"
                        }
                        Text {
                            text: root.tr("decompressor_desc", "Auto-scan watchlist artists & folders for archives, verify disk space, and extract.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#64748B"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                            visible: !root.isNarrow
                        }
                    }

                    // Action buttons in title row ONLY when wide (>= 720px)
                    RowLayout {
                        spacing: 8
                        visible: !root.isNarrow

                        // Add Custom Folder Button
                        Rectangle {
                            height: 30
                            implicitWidth: addFolderRowWide.implicitWidth + 18
                            radius: 6
                            color: addFolderMouseWide.containsMouse ? "#1E293B" : "#141C2A"
                            border.color: addFolderMouseWide.containsMouse ? "#475569" : "#334155"
                            border.width: 1

                            Row {
                                id: addFolderRowWide
                                anchors.centerIn: parent
                                spacing: 5
                                Text { text: "📁+"; font.pixelSize: 11 }
                                Text {
                                    text: root.tr("decompressor_add_folder", "Add Folder")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: Font.Medium
                                    color: "#E2E8F0"
                                }
                            }

                            MouseArea {
                                id: addFolderMouseWide
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (decompressor) decompressor.browseCustomFolder()
                            }
                        }

                        // Scan Archives Button
                        Rectangle {
                            height: 30
                            implicitWidth: scanRowWide.implicitWidth + 20
                            radius: 6
                            color: scanMouseWide.containsMouse ? "#4338CA" : "#3730A3"
                            border.color: "#6366F1"
                            border.width: 1
                            opacity: decompressor && decompressor.isBusy ? 0.6 : 1.0

                            Row {
                                id: scanRowWide
                                anchors.centerIn: parent
                                spacing: 5
                                Text {
                                    text: decompressor && decompressor.isScanning ? "⏳" : "🔍"
                                    font.pixelSize: 11
                                }
                                Text {
                                    text: decompressor && decompressor.isScanning
                                          ? root.tr("decompressor_scanning", "Scanning...")
                                          : root.tr("decompressor_scan_btn", "Scan Archives")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: "#FFFFFF"
                                }
                            }

                            MouseArea {
                                id: scanMouseWide
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                enabled: !(decompressor && decompressor.isBusy)
                                onClicked: if (decompressor) decompressor.scanLocations()
                            }
                        }
                    }
                }

                // Action buttons on dedicated row when narrow (< 720px, e.g. when Progress Log is open)
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: root.isNarrow

                    // Add Custom Folder Button (50% width)
                    Rectangle {
                        Layout.fillWidth: true
                        height: 32
                        radius: 6
                        color: addFolderMouseNarrow.containsMouse ? "#1E293B" : "#141C2A"
                        border.color: addFolderMouseNarrow.containsMouse ? "#475569" : "#334155"
                        border.width: 1

                        Row {
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: "📁+"; font.pixelSize: 12 }
                            Text {
                                text: root.tr("decompressor_add_folder", "Add Folder")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Medium
                                color: "#E2E8F0"
                            }
                        }

                        MouseArea {
                            id: addFolderMouseNarrow
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (decompressor) decompressor.browseCustomFolder()
                        }
                    }

                    // Scan Archives Button (50% width)
                    Rectangle {
                        Layout.fillWidth: true
                        height: 32
                        radius: 6
                        color: scanMouseNarrow.containsMouse ? "#4338CA" : "#3730A3"
                        border.color: "#6366F1"
                        border.width: 1
                        opacity: decompressor && decompressor.isBusy ? 0.6 : 1.0

                        Row {
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                text: decompressor && decompressor.isScanning ? "⏳" : "🔍"
                                font.pixelSize: 12
                            }
                            Text {
                                text: decompressor && decompressor.isScanning
                                      ? root.tr("decompressor_scanning", "Scanning...")
                                      : root.tr("decompressor_scan_btn", "Scan Archives")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: "#FFFFFF"
                            }
                        }

                        MouseArea {
                            id: scanMouseNarrow
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            enabled: !(decompressor && decompressor.isBusy)
                            onClicked: if (decompressor) decompressor.scanLocations()
                        }
                    }
                }

                // Divider
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: "#1E2638"
                }

                // Configuration settings & Options (Responsive)
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 16

                        // Parallel extraction count
                        RowLayout {
                            spacing: 6
                            Text {
                                text: root.tr("decompressor_parallel", "Parallel:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                            NumberStepper {
                                from: 1
                                to: 8
                                value: decompressor ? decompressor.maxParallel : 2
                                onValueModified: function(val) {
                                    if (decompressor) decompressor.maxParallel = val;
                                }
                            }
                        }

                        // Threads per archive
                        RowLayout {
                            spacing: 6
                            Text {
                                text: root.tr("decompressor_threads", "Threads:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                            NumberStepper {
                                from: 1
                                to: 16
                                value: decompressor ? decompressor.threadsPerArchive : 2
                                onValueModified: function(val) {
                                    if (decompressor) decompressor.threadsPerArchive = val;
                                }
                            }
                        }

                        // When wide (>= 820px), show delete option on the same row
                        DeleteArchiveOption {
                            visible: root.width >= 820
                        }

                        Item { Layout.fillWidth: true }
                    }

                    // When narrow (< 820px), show delete option on its own full-width row below
                    DeleteArchiveOption {
                        Layout.fillWidth: true
                        visible: root.width < 820
                    }
                }
            }
        }

        // ══════════════════════════════════════════════════════════════════════
        // ── LIVE EXTRACTION DUAL PROGRESS BAR PANEL ───────────────────────────
        // ══════════════════════════════════════════════════════════════════════
        Rectangle {
            Layout.fillWidth: true
            visible: decompressor && (decompressor.isExtracting || root.overallProgress > 0)
            implicitHeight: progressCol.implicitHeight + 20
            radius: 10
            color: "#0B132B"
            border.color: "#1E3A8A"
            border.width: 1

            ColumnLayout {
                id: progressCol
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                // Total Progress Title Row
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "🚀 " + root.tr("decompressor_total_progress", "Total Extraction Progress")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#93C5FD"
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: root.speedText + "  •  ETA: " + root.etaText + "  •  " + Math.round(root.overallProgress) + "%"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#60A5FA"
                    }
                }

                // Total Progress Bar
                Rectangle {
                    Layout.fillWidth: true
                    height: 8
                    radius: 4
                    color: "#1E293B"
                    clip: true

                    Rectangle {
                        height: parent.height
                        radius: 4
                        width: parent.width * (Math.max(0, Math.min(100, root.overallProgress)) / 100.0)
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: "#3B82F6" }
                            GradientStop { position: 1.0; color: "#10B981" }
                        }
                        Behavior on width { NumberAnimation { duration: 150 } }
                    }
                }

                // Active archive progress bar
                RowLayout {
                    Layout.fillWidth: true
                    visible: !!root.currentArchiveName
                    Text {
                        text: "📄 " + (root.currentArchiveName || "")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#CBD5E1"
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                    Text {
                        text: Math.round(root.currentArchiveProgress) + "%"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#A78BFA"
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 5
                    radius: 3
                    color: "#1E293B"
                    visible: !!root.currentArchiveName
                    clip: true

                    Rectangle {
                        height: parent.height
                        radius: 3
                        width: parent.width * (Math.max(0, Math.min(100, root.currentArchiveProgress)) / 100.0)
                        color: "#8B5CF6"
                        Behavior on width { NumberAnimation { duration: 150 } }
                    }
                }
            }
        }

        // ══════════════════════════════════════════════════════════════════════
        // ── ACTION / FILTER TOOLBAR ───────────────────────────────────────────
        // ══════════════════════════════════════════════════════════════════════
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            // Row 1: Quick Actions & Search Input (Responsive)
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                // Select All
                Rectangle {
                    height: 28
                    implicitWidth: selAllTxt.implicitWidth + 18
                    radius: 5
                    color: selAllMouse.containsMouse ? "#1E293B" : "#111827"
                    border.color: "#334155"
                    border.width: 1

                    Text {
                        id: selAllTxt
                        anchors.centerIn: parent
                        text: root.tr("decompressor_select_all", "Select All")
                        font.pixelSize: 11
                        color: "#CBD5E1"
                    }
                    MouseArea {
                        id: selAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (decompressor) decompressor.selectAll(true)
                    }
                }

                // Deselect All
                Rectangle {
                    height: 28
                    implicitWidth: deselAllTxt.implicitWidth + 18
                    radius: 5
                    color: deselAllMouse.containsMouse ? "#1E293B" : "#111827"
                    border.color: "#334155"
                    border.width: 1

                    Text {
                        id: deselAllTxt
                        anchors.centerIn: parent
                        text: root.tr("decompressor_deselect_all", "Deselect All")
                        font.pixelSize: 11
                        color: "#CBD5E1"
                    }
                    MouseArea {
                        id: deselAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (decompressor) decompressor.selectAll(false)
                    }
                }

                // Clear Finished
                Rectangle {
                    height: 28
                    implicitWidth: clearFinTxt.implicitWidth + 16
                    radius: 5
                    color: clearFinMouse.containsMouse ? "#1E293B" : "#111827"
                    border.color: "#334155"
                    border.width: 1

                    Text {
                        id: clearFinTxt
                        anchors.centerIn: parent
                        text: root.tr("decompressor_clear_done", "Clear Finished")
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                    MouseArea {
                        id: clearFinMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (decompressor) decompressor.clearFinished()
                    }
                }

                // Expand / Collapse All Toggle
                Rectangle {
                    height: 28
                    implicitWidth: expTxt.implicitWidth + 16
                    radius: 5
                    color: expMouse.containsMouse ? "#1E293B" : "#111827"
                    border.color: "#334155"
                    border.width: 1

                    Text {
                        id: expTxt
                        anchors.centerIn: parent
                        text: Object.keys(root.collapsedCreators).length > 0
                              ? ("▼ " + root.tr("decompressor_expand_all", "Expand All"))
                              : ("▶ " + root.tr("decompressor_collapse_all", "Collapse All"))
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                    MouseArea {
                        id: expMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (Object.keys(root.collapsedCreators).length > 0) {
                                root.expandAllCreators();
                            } else {
                                root.collapseAllCreators();
                            }
                        }
                    }
                }

                // Search filter box (shown inline when wide >= 580px)
                Rectangle {
                    height: 28
                    visible: root.width >= 580
                    Layout.fillWidth: true
                    Layout.minimumWidth: 120
                    radius: 5
                    color: "#111827"
                    border.color: searchInputWide.activeFocus ? "#6366F1" : "#1E293B"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 4

                        Text { text: "🔍"; font.pixelSize: 10; color: "#64748B" }
                        TextInput {
                            id: searchInputWide
                            Layout.fillWidth: true
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#E2E8F0"
                            clip: true
                            text: root.searchText
                            onTextChanged: {
                                if (root.searchText !== text) {
                                    root.searchText = text;
                                    root.itemsList = root.parseItems();
                                    root.groupedItems = root.parseGroupedItems();
                                }
                            }
                        }
                    }
                }
            }

            // Search filter box (full-width dedicated line when narrow < 580px)
            Rectangle {
                height: 28
                visible: root.width < 580
                Layout.fillWidth: true
                radius: 5
                color: "#111827"
                border.color: searchInputNarrow.activeFocus ? "#6366F1" : "#1E293B"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 6

                    Text { text: "🔍"; font.pixelSize: 10; color: "#64748B" }
                    TextInput {
                        id: searchInputNarrow
                        Layout.fillWidth: true
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#E2E8F0"
                        clip: true
                        text: root.searchText
                        onTextChanged: {
                            if (root.searchText !== text) {
                                root.searchText = text;
                                root.itemsList = root.parseItems();
                                root.groupedItems = root.parseGroupedItems();
                            }
                        }
                    }
                }
            }

            // Row 2: Stats Summary & Primary Execution Action
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                // Stats Label
                Text {
                    text: (decompressor
                           ? (root.tr("decompressor_selected", "Selected:") + " " + decompressor.selectedCount + " / " + decompressor.totalCount +
                              " (" + root.formatBytes(decompressor.selectedBytes) + " / " + root.formatBytes(decompressor.totalBytes) + ") • " +
                              root.groupedItems.length + " " + (root.groupedItems.length === 1 ? "Creator" : "Creators"))
                           : "")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                // Cancel Button (visible when extracting)
                Rectangle {
                    height: 28
                    visible: decompressor && decompressor.isExtracting
                    implicitWidth: cancelTxt.implicitWidth + 18
                    radius: 5
                    color: cancelMouse.containsMouse ? "#7F1D1D" : "#5B1414"
                    border.color: "#EF4444"
                    border.width: 1

                    Text {
                        id: cancelTxt
                        anchors.centerIn: parent
                        text: root.tr("decompressor_cancel", "Cancel")
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#FCA5A5"
                    }
                    MouseArea {
                        id: cancelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (decompressor) decompressor.cancelDecompression()
                    }
                }

                // Start Decompression Button (Triggers Pre-flight Disk Check first!)
                Rectangle {
                    height: 30
                    implicitWidth: startBtnRow.implicitWidth + 24
                    radius: 6
                    color: decompressor && decompressor.selectedCount > 0 && !decompressor.isBusy
                           ? (startMouse.containsMouse ? "#059669" : "#10B981")
                           : "#1E293B"
                    border.color: decompressor && decompressor.selectedCount > 0 && !decompressor.isBusy ? "#34D399" : "#334155"
                    border.width: 1
                    enabled: decompressor && decompressor.selectedCount > 0 && !decompressor.isBusy

                    Row {
                        id: startBtnRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "⚡"; font.pixelSize: 12 }
                        Text {
                            text: root.tr("decompressor_start_btn", "Start Decompressing")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: decompressor && decompressor.selectedCount > 0 && !decompressor.isBusy ? "#FFFFFF" : "#64748B"
                        }
                    }

                    MouseArea {
                        id: startMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: parent.enabled
                        onClicked: {
                            if (decompressor) {
                                decompressor.checkDiskSpace();
                            }
                        }
                    }
                }
            }
        }

        // ══════════════════════════════════════════════════════════════════════
        // ── ARCHIVE ITEMS LIST VIEW ───────────────────────────────────────────
        // ══════════════════════════════════════════════════════════════════════
        // ══════════════════════════════════════════════════════════════════════
        // ── ARCHIVE ITEMS CREATOR TREE VIEW ───────────────────────────────────
        // ══════════════════════════════════════════════════════════════════════
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 10
            color: "#0B0E14"
            border.color: "#182030"
            border.width: 1
            clip: true

            // Empty state
            ColumnLayout {
                anchors.centerIn: parent
                visible: root.groupedItems.length === 0
                spacing: 8

                Text {
                    text: "📭"
                    font.pixelSize: 32
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: root.tr("decompressor_no_archives", "No archives found.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.weight: 600
                    color: "#64748B"
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: root.tr("decompressor_scan_hint", "Click 'Scan Archives' to search watchlist creators' folders, or 'Add Folder' for custom directories.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#475569"
                    Layout.alignment: Qt.AlignHCenter
                }
            }

            SmoothListView {
                id: archiveListView
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8
                clip: true
                visible: root.groupedItems.length > 0
                model: root.groupedItems

                delegate: Rectangle {
                    id: creatorGroupCard
                    width: archiveListView.width - 12
                    radius: 8
                    color: "#0D111A"
                    border.color: root.isCreatorCollapsed(modelData) ? "#1A2234" : "#28344E"
                    border.width: 1
                    clip: true

                    implicitHeight: groupCol.implicitHeight + 12

                    ColumnLayout {
                        id: groupCol
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 6
                        spacing: 4

                        // ── 1. Creator Group Header Row ───────────────────────
                        Rectangle {
                            Layout.fillWidth: true
                            height: 38
                            radius: 6
                            color: headerMouse.containsMouse ? "#161D2C" : "#111622"
                            border.color: headerMouse.containsMouse ? "#334155" : "transparent"
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 8

                                // Expand/Collapse Chevron
                                Text {
                                    text: root.isCreatorCollapsed(modelData) ? "▶" : "▼"
                                    font.pixelSize: 10
                                    color: "#94A3B8"
                                    Layout.alignment: Qt.AlignVCenter
                                }

                                // Creator Checkbox (Batch select/deselect all in this creator)
                                Rectangle {
                                    width: 18
                                    height: 18
                                    radius: 4
                                    color: modelData.allSelected ? "#38BDF8" : (modelData.someSelected ? "#1E293B" : "#111827")
                                    border.color: modelData.allSelected ? "#38BDF8" : (modelData.someSelected ? "#60A5FA" : (crCheckMouse.containsMouse ? "#64748B" : "#334155"))
                                    border.width: (modelData.allSelected || modelData.someSelected) ? 1.5 : 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.allSelected ? "✓" : (modelData.someSelected ? "−" : "")
                                        font.pixelSize: 11
                                        font.weight: Font.Bold
                                        color: modelData.allSelected ? "#0F172A" : "#60A5FA"
                                    }

                                    MouseArea {
                                        id: crCheckMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 300
                                        ToolTip.text: root.tr("decompressor_creator_toggle_tip", "Toggle all archives for this creator")
                                        onClicked: {
                                            if (decompressor)
                                                decompressor.toggleCreatorByScanRoot(modelData.creator, modelData.directory);
                                        }
                                    }
                                }

                                // Creator Icon & Name + folder path
                                Text { text: "🎨"; font.pixelSize: 12 }
                                Column {
                                    spacing: 1
                                    Layout.fillWidth: true
                                    Text {
                                        text: modelData.creator || "Unknown"
                                        font.family: "Segoe UI, Inter, sans-serif"
                                        font.pixelSize: 13
                                        font.weight: 600
                                        color: "#F8FAFC"
                                        elide: Text.ElideRight
                                        width: parent.width
                                    }
                                    Text {
                                        text: modelData.directory || ""
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        color: "#4B5563"
                                        elide: Text.ElideLeft
                                        width: parent.width
                                        visible: text !== ""
                                    }
                                }

                                // Archive count & total size badge
                                Rectangle {
                                    height: 20
                                    implicitWidth: crCountText.implicitWidth + 12
                                    radius: 10
                                    color: "#1E293B"
                                    border.color: "#334155"
                                    border.width: 1

                                    Text {
                                        id: crCountText
                                        anchors.centerIn: parent
                                        text: modelData.totalCount + " " + (modelData.totalCount === 1 ? "archive" : "archives") + " • " + root.formatBytes(modelData.totalBytes)
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        font.weight: Font.Medium
                                        color: "#94A3B8"
                                    }
                                }

                                // Selection counter badge
                                Rectangle {
                                    height: 20
                                    implicitWidth: crSelText.implicitWidth + 10
                                    radius: 10
                                    color: modelData.selectedCount > 0 ? "#064E3B" : "#181D26"
                                    border.color: modelData.selectedCount > 0 ? "#059669" : "#242C3B"
                                    border.width: 1
                                    visible: modelData.selectedCount > 0

                                    Text {
                                        id: crSelText
                                        anchors.centerIn: parent
                                        text: modelData.selectedCount + " selected"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        font.weight: 600
                                        color: "#34D399"
                                    }
                                }

                                Item { Layout.fillWidth: true }

                                // Open creator folder button
                                Rectangle {
                                    height: 24
                                    implicitWidth: 26
                                    radius: 4
                                    color: crFoldMouse.containsMouse ? "#1E293B" : "transparent"
                                    border.color: crFoldMouse.containsMouse ? "#475569" : "transparent"
                                    border.width: 1
                                    visible: !!modelData.directory

                                    Text {
                                        anchors.centerIn: parent
                                        text: "📂"
                                        font.pixelSize: 11
                                    }

                                    MouseArea {
                                        id: crFoldMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 300
                                        ToolTip.text: root.tr("tip_open_folder", "Open folder in File Explorer")
                                        onClicked: {
                                            if (decompressor) decompressor.openFolder(modelData.directory);
                                        }
                                    }
                                }
                            }

                            // Header click toggles expand/collapse
                            MouseArea {
                                id: headerMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                z: -1
                                onClicked: root.toggleCreatorCollapse(modelData)
                            }
                        }

                        // ── 2. Nested Child Archives Tree View ───────────────
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 12
                            Layout.rightMargin: 4
                            spacing: 3
                            visible: !root.isCreatorCollapsed(modelData)

                            Repeater {
                                model: modelData.items

                                delegate: Rectangle {
                                    id: archiveRow
                                    Layout.fillWidth: true
                                    height: 38
                                    radius: 5
                                    color: modelData.selected ? "#141C2B" : (rowMouse.containsMouse ? "#101622" : "#0A0E17")
                                    border.color: modelData.status === "error" ? "#7F1D1D" : (modelData.status === "done" ? "#14532D" : (modelData.selected ? "#1E3A5F" : "#141A26"))
                                    border.width: 1

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 8
                                        anchors.rightMargin: 8
                                        spacing: 8

                                        // Tree branch symbol
                                        Text {
                                            text: "└─"
                                            font.family: "Consolas, monospace"
                                            font.pixelSize: 11
                                            color: "#334155"
                                        }

                                        // Archive Checkbox
                                        Rectangle {
                                            width: 16
                                            height: 16
                                            radius: 3
                                            color: modelData.selected ? "#38BDF8" : "#111827"
                                            border.color: modelData.selected ? "#38BDF8" : (subCheckMouse.containsMouse ? "#64748B" : "#334155")
                                            border.width: modelData.selected ? 1.5 : 1

                                            Text {
                                                anchors.centerIn: parent
                                                text: "✓"
                                                font.pixelSize: 10
                                                font.weight: Font.Bold
                                                color: "#0F172A"
                                                visible: modelData.selected
                                            }

                                            MouseArea {
                                                id: subCheckMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: if (decompressor) decompressor.toggleItem(modelData.id)
                                            }
                                        }

                                        // Format badge (ZIP, RAR, 7Z, TAR)
                                        Rectangle {
                                            height: 18
                                            implicitWidth: 32
                                            radius: 4
                                            color: {
                                                var f = (modelData.filename || "").toLowerCase();
                                                if (f.indexOf(".zip") !== -1) return "#0284C7";
                                                if (f.indexOf(".rar") !== -1) return "#7C3AED";
                                                if (f.indexOf(".7z") !== -1) return "#DB2777";
                                                return "#475569";
                                            }
                                            Text {
                                                anchors.centerIn: parent
                                                text: {
                                                    var f = (modelData.filename || "").toLowerCase();
                                                    if (f.indexOf(".zip") !== -1) return "ZIP";
                                                    if (f.indexOf(".rar") !== -1) return "RAR";
                                                    if (f.indexOf(".7z") !== -1) return "7Z";
                                                    if (f.indexOf(".tar") !== -1) return "TAR";
                                                    return "ARC";
                                                }
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 9
                                                font.weight: Font.Bold
                                                color: "#FFFFFF"
                                            }
                                        }

                                        // Filename
                                        Text {
                                            text: modelData.filename || ""
                                            font.family: "Segoe UI, Inter, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: Font.Normal
                                            color: modelData.status === "error" ? "#FCA5A5" : (modelData.selected ? "#F1F5F9" : "#94A3B8")
                                            elide: Text.ElideMiddle
                                            Layout.fillWidth: true
                                        }

                                        // Size text
                                        Text {
                                            text: root.formatBytes(modelData.size)
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            color: "#64748B"
                                        }

                                        // Status / Progress indicator
                                        Item {
                                            width: root.isNarrow ? 90 : 120
                                            height: 22

                                            // Pending badge
                                            Text {
                                                anchors.centerIn: parent
                                                visible: modelData.status === "pending"
                                                text: root.tr("decompressor_pending", "Pending")
                                                font.pixelSize: 10
                                                color: "#64748B"
                                            }

                                            // Extracting progress bar
                                            RowLayout {
                                                anchors.fill: parent
                                                visible: modelData.status === "extracting"
                                                spacing: 4

                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    height: 5
                                                    radius: 2.5
                                                    color: "#1E293B"
                                                    clip: true
                                                    Rectangle {
                                                        height: parent.height
                                                        radius: 2.5
                                                        width: parent.width * (Math.max(0, Math.min(100, modelData.progress)) / 100.0)
                                                        color: "#8B5CF6"
                                                    }
                                                }
                                                Text {
                                                    text: Math.round(modelData.progress) + "%"
                                                    font.pixelSize: 10
                                                    color: "#A78BFA"
                                                }
                                            }

                                            // Done badge
                                            Rectangle {
                                                anchors.centerIn: parent
                                                visible: modelData.status === "done"
                                                height: 18
                                                implicitWidth: doneTxt.implicitWidth + 10
                                                radius: 9
                                                color: "#064E3B"
                                                border.color: "#10B981"
                                                border.width: 1
                                                Text {
                                                    id: doneTxt
                                                    anchors.centerIn: parent
                                                    text: "✓ " + root.tr("decompressor_done", "Extracted")
                                                    font.pixelSize: 9
                                                    font.weight: 600
                                                    color: "#34D399"
                                                }
                                            }

                                            // Error badge with tooltip
                                            Rectangle {
                                                anchors.centerIn: parent
                                                visible: modelData.status === "error"
                                                height: 18
                                                implicitWidth: errTxt.implicitWidth + 10
                                                radius: 9
                                                color: "#450A0A"
                                                border.color: "#EF4444"
                                                border.width: 1
                                                Text {
                                                    id: errTxt
                                                    anchors.centerIn: parent
                                                    text: "⚠️ " + root.tr("decompressor_error", "Error")
                                                    font.pixelSize: 9
                                                    font.weight: Font.Bold
                                                    color: "#FCA5A5"
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    ToolTip.visible: containsMouse
                                                    ToolTip.delay: 100
                                                    ToolTip.text: modelData.errorMessage || "Decompression error"
                                                }
                                            }
                                        }

                                        // Open single archive directory button
                                        Rectangle {
                                            height: 22
                                            implicitWidth: 22
                                            radius: 3
                                            color: singleFoldMouse.containsMouse ? "#1E293B" : "transparent"
                                            border.color: singleFoldMouse.containsMouse ? "#334155" : "transparent"
                                            border.width: 1

                                            Text {
                                                anchors.centerIn: parent
                                                text: "📂"
                                                font.pixelSize: 10
                                            }

                                            MouseArea {
                                                id: singleFoldMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                ToolTip.visible: containsMouse
                                                ToolTip.delay: 300
                                                ToolTip.text: root.tr("tip_open_folder", "Open folder in File Explorer")
                                                onClicked: if (decompressor) decompressor.openFolder(modelData.directory)
                                            }
                                        }
                                    }

                                    // Row click toggles selection
                                    MouseArea {
                                        id: rowMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        z: -1
                                        onClicked: if (decompressor) decompressor.toggleItem(modelData.id)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ══════════════════════════════════════════════════════════════════════
    // ── DISK SPACE PRE-FLIGHT CHECK MODAL ─────────────────────────────────
    // ══════════════════════════════════════════════════════════════════════
    Rectangle {
        id: diskModalBackdrop
        anchors.fill: parent
        visible: root.showDiskModal
        color: "#B3000000"
        z: 999

        MouseArea {
            anchors.fill: parent
            // Block clicks through
        }

        Rectangle {
            id: diskModalCard
            anchors.centerIn: parent
            width: Math.min(520, parent.width - 40)
            implicitHeight: modalCol.implicitHeight + 36
            radius: 14
            color: "#0F172A"
            border.color: "#334155"
            border.width: 1

            ColumnLayout {
                id: modalCol
                anchors.fill: parent
                anchors.margins: 20
                spacing: 16

                // Modal Header
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Text { text: "💾"; font.pixelSize: 22 }
                    ColumnLayout {
                        spacing: 2
                        Text {
                            text: root.tr("decompressor_disk_title", "Disk Space Pre-Flight Check")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                        }
                        Text {
                            text: root.tr("decompressor_disk_subtitle", "Verifying available disk space on target drives before decompressing.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                    }
                }

                // Drive Check Items
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: root.diskCheckData
                        delegate: Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 58
                            radius: 8
                            color: modelData.isSufficient ? "#0D1F17" : "#2B1111"
                            border.color: modelData.isSufficient ? "#10B981" : "#EF4444"
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 10

                                Text {
                                    text: modelData.isSufficient ? "✅" : "⚠️"
                                    font.pixelSize: 18
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    RowLayout {
                                        Text {
                                            text: "Drive " + modelData.drive
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 13
                                            font.weight: 600
                                            color: "#F1F5F9"
                                        }
                                        Text {
                                            text: "(" + modelData.archiveCount + " archives, " + root.formatBytes(modelData.totalArchiveSize) + ")"
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            color: "#94A3B8"
                                        }
                                    }
                                    Text {
                                        text: "Free: " + root.formatBytes(modelData.freeBytes) +
                                              "  |  Estimated Required: ~" + root.formatBytes(modelData.estimatedRequired)
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: modelData.isSufficient ? "#34D399" : "#FCA5A5"
                                    }
                                }
                            }
                        }
                    }
                }

                // Modal Buttons
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Item { Layout.fillWidth: true }

                    // Cancel
                    Rectangle {
                        height: 32
                        implicitWidth: modalCancelTxt.implicitWidth + 24
                        radius: 6
                        color: modalCancelMouse.containsMouse ? "#334155" : "#1E293B"
                        border.color: "#475569"
                        border.width: 1

                        Text {
                            id: modalCancelTxt
                            anchors.centerIn: parent
                            text: root.tr("dialog_cancel", "Cancel")
                            font.pixelSize: 12
                            color: "#E2E8F0"
                        }

                        MouseArea {
                            id: modalCancelMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.showDiskModal = false
                        }
                    }

                    // Proceed
                    Rectangle {
                        height: 32
                        implicitWidth: modalProceedTxt.implicitWidth + 24
                        radius: 6
                        color: modalProceedMouse.containsMouse ? "#059669" : "#10B981"
                        border.color: "#34D399"
                        border.width: 1

                        Text {
                            id: modalProceedTxt
                            anchors.centerIn: parent
                            text: root.tr("decompressor_proceed", "Proceed with Extraction")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }

                        MouseArea {
                            id: modalProceedMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.showDiskModal = false;
                                if (decompressor) decompressor.startDecompression();
                            }
                        }
                    }
                }
            }
        }
    }
}
