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

    // Password Bank modal state
    property bool showPasswordBank: false
    property var collapsedBankCreators: ({})
    property string selectedBankCreator: "Global"
    property bool isCreatorMenuOpen: false
    property var pwBankTree: parsePasswordBankTree()

    function parsePasswordBankTree() {
        if (!decompressor || !decompressor.passwordBankTreeJson) return [];
        try {
            return JSON.parse(decompressor.passwordBankTreeJson);
        } catch (e) {
            return [];
        }
    }

    onShowPasswordBankChanged: {
        if (root.showPasswordBank) {
            root.pwBankTree = root.parsePasswordBankTree();
        } else {
            root.isCreatorMenuOpen = false;
        }
    }

    onDecompressorChanged: {
        root.pwBankTree = root.parsePasswordBankTree();
    }

    function isBankCreatorCollapsed(creatorName) {
        return !!root.collapsedBankCreators[creatorName];
    }

    function toggleBankCreatorCollapse(creatorName) {
        var copy = Object.assign({}, root.collapsedBankCreators);
        if (copy[creatorName]) {
            delete copy[creatorName];
        } else {
            copy[creatorName] = true;
        }
        root.collapsedBankCreators = copy;
    }

    // Password Prompt modal state
    property bool showPasswordPrompt: false
    property string promptItemId: ""
    property string promptFilename: ""
    property string promptCreator: ""
    property string promptDirectory: ""
    property string promptErrorMsg: ""
    property real promptArchiveSize: 0
    property bool promptRemember: true
    property bool promptWrongPw: false
    property bool promptTesting: false   // true while background thread is verifying

    // Current live extraction state
    property real overallProgress: 0.0
    property string currentArchiveName: ""
    property real currentArchiveProgress: 0.0
    property string etaText: "--"
    property string speedText: "--"

    // Redecompress confirm modal state
    property bool showRedecompressModal: false
    property int redecompressAlreadyDoneCount: 0
    property int redecompressTotalCount: 0

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
        function onPasswordBankChanged() {
            root.itemsList = root.parseItems();
            root.pwBankTree = root.parsePasswordBankTree();
        }
        function onPasswordPromptRequested(itemId, filename, creator, directory, errorMsg, size) {
            root.promptItemId = itemId;
            root.promptFilename = filename;
            root.promptCreator = creator;
            root.promptDirectory = directory;
            root.promptErrorMsg = errorMsg;
            root.promptArchiveSize = size;
            root.promptRemember = true;
            root.promptWrongPw = false;
            root.promptTesting = false;
            root.showPasswordPrompt = true;
        }
        function onPasswordPromptDismissed(itemId) {
            if (root.promptItemId === itemId) {
                root.promptTesting = false;
                root.showPasswordPrompt = false;
            }
        }
        function onPasswordWrong(itemId) {
            if (root.promptItemId === itemId) {
                root.promptTesting = false;
                root.promptWrongPw = true;
                pwInput.text = "";
                pwPromptCard.inputText = "";
                pwShakeAnim.restart();
            }
        }
        function onRedecompressConfirmRequested(alreadyDone, total) {
            root.redecompressAlreadyDoneCount = alreadyDone;
            root.redecompressTotalCount = total;
            root.showRedecompressModal = true;
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

                        // Password Bank Button
                        Rectangle {
                            height: 30
                            implicitWidth: pwBankRowWide.implicitWidth + 18
                            radius: 6
                            color: pwBankMouseWide.containsMouse ? "#15293D" : "#0F1F2E"
                            border.color: pwBankMouseWide.containsMouse ? "#38BDF8" : "#1E3A5F"
                            border.width: 1
                            ToolTip.visible: pwBankMouseWide.containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: root.tr("tip_password_bank", "Manage remembered passwords for automatic archive extraction")

                            Row {
                                id: pwBankRowWide
                                anchors.centerIn: parent
                                spacing: 5
                                Text { text: "🔑"; font.pixelSize: 11 }
                                Text {
                                    text: root.tr("btn_password_bank", "Password Bank")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: Font.Medium
                                    color: "#38BDF8"
                                }
                                Rectangle {
                                    width: pwBankCountTxt.implicitWidth + 8
                                    height: 14
                                    radius: 7
                                    color: "#1E3A5F"
                                    visible: decompressor && decompressor.savedPasswordsCount > 0
                                    Text {
                                        id: pwBankCountTxt
                                        anchors.centerIn: parent
                                        text: decompressor ? decompressor.savedPasswordsCount : 0
                                        font.pixelSize: 8
                                        font.weight: Font.Bold
                                        color: "#7DD3FC"
                                    }
                                }
                            }

                            MouseArea {
                                id: pwBankMouseWide
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.showPasswordBank = true
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

                    // Scan Archives Button
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

                    // Password Bank Button (Narrow)
                    Rectangle {
                        Layout.fillWidth: true
                        height: 32
                        radius: 6
                        color: pwBankMouseNarrow.containsMouse ? "#15293D" : "#0F1F2E"
                        border.color: pwBankMouseNarrow.containsMouse ? "#38BDF8" : "#1E3A5F"
                        border.width: 1

                        Row {
                            anchors.centerIn: parent
                            spacing: 5
                            Text { text: "🔑"; font.pixelSize: 11 }
                            Text {
                                text: root.tr("btn_password_bank", "Password Bank")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Medium
                                color: "#38BDF8"
                            }
                            Rectangle {
                                width: pwBankCountTxtNarrow.implicitWidth + 8
                                height: 14
                                radius: 7
                                color: "#1E3A5F"
                                visible: decompressor && decompressor.savedPasswordsCount > 0
                                Text {
                                    id: pwBankCountTxtNarrow
                                    anchors.centerIn: parent
                                    text: decompressor ? decompressor.savedPasswordsCount : 0
                                    font.pixelSize: 8
                                    font.weight: Font.Bold
                                    color: "#7DD3FC"
                                }
                            }
                        }

                        MouseArea {
                            id: pwBankMouseNarrow
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.showPasswordBank = true
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
                                    // Color coding:
                                    //  - already extracted (extractedPresent): warm amber tint
                                    //  - selected: dark blue
                                    //  - hovered: very dark
                                    //  - default: near black
                                    color: {
                                        if (modelData.extractedPresent && modelData.status !== "extracting")
                                            return modelData.selected ? "#1C1500" : (rowMouse.containsMouse ? "#161000" : "#100C00");
                                        return modelData.selected ? "#141C2B" : (rowMouse.containsMouse ? "#101622" : "#0A0E17");
                                    }
                                    border.color: {
                                        if (modelData.status === "error") return "#7F1D1D";
                                        if (modelData.status === "done" && modelData.extractedPresent) return "#78350F";  // amber for already-extracted
                                        if (modelData.status === "done") return "#14532D";
                                        if (modelData.extractedPresent) return "#92400E";  // amber border when known-extracted but not yet done in this session
                                        return modelData.selected ? "#1E3A5F" : "#141A26";
                                    }
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
                                            color: modelData.status === "error" ? "#FCA5A5"
                                                 : modelData.extractedPresent && modelData.status !== "extracting" ? "#D97706"
                                                 : (modelData.selected ? "#F1F5F9" : "#94A3B8")
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

                                            // Pending / Already Extracted badge
                                            Rectangle {
                                                anchors.centerIn: parent
                                                visible: modelData.status === "pending"
                                                height: modelData.extractedPresent ? 18 : 0
                                                implicitWidth: modelData.extractedPresent ? (alreadyExtractedTxt.implicitWidth + 10) : 0
                                                radius: 9
                                                color: modelData.extractedPresent ? "#451A00" : "transparent"
                                                border.color: modelData.extractedPresent ? "#D97706" : "transparent"
                                                border.width: modelData.extractedPresent ? 1 : 0

                                                Text {
                                                    id: alreadyExtractedTxt
                                                    anchors.centerIn: parent
                                                    text: modelData.extractedPresent ? ("🗂 " + root.tr("decompressor_already_extracted", "Already Extracted")) : root.tr("decompressor_pending", "Pending")
                                                    font.pixelSize: 9
                                                    font.weight: modelData.extractedPresent ? Font.Bold : Font.Normal
                                                    color: modelData.extractedPresent ? "#FBB040" : "#64748B"
                                                }

                                                MouseArea {
                                                    anchors.fill: parent
                                                    hoverEnabled: modelData.extractedPresent
                                                    ToolTip.visible: containsMouse && modelData.extractedPresent
                                                    ToolTip.delay: 300
                                                    ToolTip.text: root.tr("tip_already_extracted", "Files from this archive are already present on disk. Selecting it will re-extract and overwrite them.")
                                                }
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
                                                // Amber = was already extracted before this session; Green = freshly extracted now
                                                color: modelData.extractedPresent && modelData.progress < 100.0 ? "#451A00" : "#064E3B"
                                                border.color: modelData.extractedPresent && modelData.progress < 100.0 ? "#D97706" : "#10B981"
                                                border.width: 1
                                                Text {
                                                    id: doneTxt
                                                    anchors.centerIn: parent
                                                    text: (modelData.extractedPresent && modelData.progress < 100.0)
                                                          ? ("🗂 " + root.tr("decompressor_pre_extracted", "Pre-extracted"))
                                                          : ("✓ " + root.tr("decompressor_done", "Extracted"))
                                                    font.pixelSize: 9
                                                    font.weight: 600
                                                    color: modelData.extractedPresent && modelData.progress < 100.0 ? "#FBB040" : "#34D399"
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    hoverEnabled: modelData.extractedPresent && modelData.progress < 100.0
                                                    ToolTip.visible: containsMouse && modelData.extractedPresent && modelData.progress < 100.0
                                                    ToolTip.delay: 300
                                                    ToolTip.text: root.tr("tip_pre_extracted", "This archive was already extracted before scanning. Select it and re-run to overwrite.")
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

                                            // 🔐 Password Required badge
                                            Rectangle {
                                                id: pwReqBadge
                                                anchors.centerIn: parent
                                                visible: modelData.status === "password_required"
                                                height: 18
                                                implicitWidth: pwReqTxt.implicitWidth + 10
                                                radius: 9
                                                color: "#451A03"
                                                border.color: "#F59E0B"
                                                border.width: 1
                                                Text {
                                                    id: pwReqTxt
                                                    anchors.centerIn: parent
                                                    text: "🔐 " + root.tr("status_password_required", "Password Required")
                                                    font.pixelSize: 9
                                                    font.weight: Font.Bold
                                                    color: "#FCD34D"
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    ToolTip.visible: containsMouse
                                                    ToolTip.delay: 100
                                                    ToolTip.text: root.tr("tip_enter_password", "Enter password to decrypt this archive")
                                                }
                                            }
                                        }

                                        // 🔑 Enter Password inline button (password_required only)
                                        Rectangle {
                                            height: 22
                                            implicitWidth: enterPwRow.implicitWidth + 10
                                            radius: 4
                                            visible: modelData.status === "password_required"
                                            color: enterPwMouse.containsMouse ? "#1C3A52" : "#0F2237"
                                            border.color: enterPwMouse.containsMouse ? "#38BDF8" : "#1E3A5F"
                                            border.width: 1

                                            Row {
                                                id: enterPwRow
                                                anchors.centerIn: parent
                                                spacing: 4
                                                Text { text: "🔑"; font.pixelSize: 9 }
                                                Text {
                                                    text: root.tr("btn_try_extract", "Try & Extract")
                                                    font.pixelSize: 9
                                                    font.weight: Font.Medium
                                                    color: "#38BDF8"
                                                }
                                            }

                                            MouseArea {
                                                id: enterPwMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                ToolTip.visible: containsMouse
                                                ToolTip.delay: 300
                                                ToolTip.text: root.tr("tip_enter_password", "Enter password to decrypt this archive")
                                                onClicked: {
                                                    root.promptItemId = modelData.id;
                                                    root.promptFilename = modelData.filename;
                                                    root.promptCreator = modelData.creator;
                                                    root.promptDirectory = modelData.directory;
                                                    root.promptErrorMsg = "";
                                                    root.promptArchiveSize = modelData.size;
                                                    root.promptRemember = true;
                                                    root.promptWrongPw = false;
                                                    root.showPasswordPrompt = true;
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
    // ── Disk space modal with spring-physics animation ──────────────────────
    Rectangle {
        id: diskModalBackdrop
        anchors.fill: parent
        // Use opacity > 0 as the visibility gate so the fade-out animation
        // completes before the element is removed from the scene.
        visible: opacity > 0
        opacity: root.showDiskModal ? 1.0 : 0.0
        color: "#B3000000"
        z: 999

        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutQuad }
        }

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

            // Spring entrance: weighted mass bounces in from slightly below
            scale: root.showDiskModal ? 1.0 : 0.82
            opacity: root.showDiskModal ? 1.0 : 0.0
            transformOrigin: Item.Center

            Behavior on scale {
                SpringAnimation {
                    spring: 5.5
                    damping: 0.52
                    mass: 1.4
                    epsilon: 0.001
                }
            }
            Behavior on opacity {
                NumberAnimation { duration: 180; easing.type: Easing.OutQuad }
            }
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

    // ═══════════════════════════════════════════════════════════════════════════
    // ── 🔄 REDECOMPRESS CONFIRMATION MODAL ───────────────────────────────────
    // ═══════════════════════════════════════════════════════════════════════════
    // ── Redecompress confirm modal with spring-physics animation ─────────────
    Rectangle {
        id: redecompressModalBackdrop
        anchors.fill: parent
        visible: opacity > 0
        opacity: root.showRedecompressModal ? 1.0 : 0.0
        color: "#B3000000"
        z: 998

        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutQuad }
        }

        MouseArea { anchors.fill: parent }

        Rectangle {
            id: redecompressCard
            anchors.centerIn: parent
            width: Math.min(460, parent.width - 40)
            implicitHeight: redecompressCol.implicitHeight + 36
            radius: 14
            color: "#0F172A"
            border.color: "#D97706"
            border.width: 1

            // Slightly heavier feel — amber modal has more visual weight
            scale: root.showRedecompressModal ? 1.0 : 0.80
            opacity: root.showRedecompressModal ? 1.0 : 0.0
            transformOrigin: Item.Center

            Behavior on scale {
                SpringAnimation {
                    spring: 4.8
                    damping: 0.48
                    mass: 1.7
                    epsilon: 0.001
                }
            }
            Behavior on opacity {
                NumberAnimation { duration: 180; easing.type: Easing.OutQuad }
            }
            ColumnLayout {
                id: redecompressCol
                anchors.fill: parent
                anchors.margins: 22
                spacing: 16

                // Header
                RowLayout {
                    spacing: 12
                    Text { text: "🔄"; font.pixelSize: 22 }
                    ColumnLayout {
                        spacing: 3
                        Layout.fillWidth: true
                        Text {
                            text: root.tr("modal_redecompress_title", "Already Extracted")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#FBB040"
                        }
                        Text {
                            text: root.tr("modal_redecompress_desc", "The selected archives have already been extracted. Do you want to re-extract them and overwrite the existing files?")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }

                // Info badge
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: redecompressInfoCol.implicitHeight + 18
                    radius: 8
                    color: "#1C1200"
                    border.color: "#78350F"
                    border.width: 1

                    ColumnLayout {
                        id: redecompressInfoCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 12
                        spacing: 4

                        Text {
                            text: root.redecompressAlreadyDoneCount + " " +
                                  (root.redecompressAlreadyDoneCount === 1
                                   ? root.tr("modal_redecompress_archive_singular", "archive already has extracted files on disk.")
                                   : root.tr("modal_redecompress_archive_plural", "archives already have extracted files on disk."))
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: "#FBB040"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Text {
                            text: "⚠️ " + root.tr("modal_redecompress_overwrite_warn", "Existing files in the output folder will be overwritten.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#F87171"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }

                // Buttons
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Item { Layout.fillWidth: true }

                    // Cancel
                    Rectangle {
                        height: 32
                        implicitWidth: redecompressCancelTxt.implicitWidth + 24
                        radius: 6
                        color: redecompressCancelMouse.containsMouse ? "#334155" : "#1E293B"
                        border.color: "#475569"
                        border.width: 1

                        Text {
                            id: redecompressCancelTxt
                            anchors.centerIn: parent
                            text: root.tr("dialog_cancel", "Cancel")
                            font.pixelSize: 12
                            color: "#E2E8F0"
                        }
                        MouseArea {
                            id: redecompressCancelMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.showRedecompressModal = false
                        }
                    }

                    // Re-extract button
                    Rectangle {
                        height: 32
                        implicitWidth: redecompressProceedTxt.implicitWidth + 24
                        radius: 6
                        color: redecompressProceedMouse.containsMouse ? "#B45309" : "#D97706"
                        border.color: "#FBB040"
                        border.width: 1

                        Text {
                            id: redecompressProceedTxt
                            anchors.centerIn: parent
                            text: "🔄 " + root.tr("modal_redecompress_proceed", "Re-extract & Overwrite")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }
                        MouseArea {
                            id: redecompressProceedMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.showRedecompressModal = false;
                                if (decompressor) decompressor.confirmRedecompress();
                            }
                        }
                    }
                }
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // ── 🔐 PASSWORD PROMPT MODAL ─────────────────────────────────────────────
    // ═══════════════════════════════════════════════════════════════════════════
    Item {
        id: passwordPromptOverlay
        anchors.fill: parent
        // Visibility gate driven by opacity so exit animation runs before hide
        visible: opacity > 0
        opacity: root.showPasswordPrompt ? 1.0 : 0.0
        z: 1000

        Behavior on opacity {
            NumberAnimation { duration: 200; easing.type: Easing.OutQuad }
        }

        // Backdrop
        Rectangle {
            anchors.fill: parent
            color: "#000000"
            opacity: 0.72
            MouseArea { anchors.fill: parent; hoverEnabled: true }
        }

        // Modal card
        Rectangle {
            id: pwPromptCard
            anchors.centerIn: parent
            width: Math.min(480, parent.width - 40)
            implicitHeight: promptCol.implicitHeight + 40
            height: implicitHeight
            radius: 14
            color: "#0F141C"
            border.color: "#F59E0B"
            border.width: 1

            // Password modal feels like a firm heavy dialog — tight spring, less bounce
            scale: root.showPasswordPrompt ? 1.0 : 0.84
            opacity: root.showPasswordPrompt ? 1.0 : 0.0
            transformOrigin: Item.Center

            Behavior on scale {
                SpringAnimation {
                    spring: 6.5
                    damping: 0.58
                    mass: 1.1
                    epsilon: 0.001
                }
            }
            Behavior on opacity {
                NumberAnimation { duration: 160; easing.type: Easing.OutQuad }
            }
            property string inputText: ""
            property bool showPlain: false

            function tryExtract() {
                var pw = inputText.trim();
                if (!pw || root.promptTesting) return;
                if (decompressor) {
                    root.promptWrongPw = false;
                    root.promptTesting = true;
                    var ok = decompressor.retryItemWithPassword(root.promptItemId, pw, root.promptRemember);
                    if (!ok) {
                        root.promptTesting = false;
                        root.promptWrongPw = true;
                        pwInput.text = "";
                        inputText = "";
                        pwShakeAnim.restart();
                    }
                }
            }
            onVisibleChanged: {
                if (visible) {
                    inputText = "";
                    showPlain = false;
                }
            }

            ColumnLayout {
                id: promptCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 20
                spacing: 14

                // Title row
                RowLayout {
                    spacing: 10
                    Text { text: "🔐"; font.pixelSize: 20 }
                    ColumnLayout {
                        spacing: 2
                        Layout.fillWidth: true
                        Text {
                            text: root.tr("modal_pw_prompt_title", "Password Required")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 14
                            font.weight: 700
                            color: "#FCD34D"
                        }
                        Text {
                            text: root.tr("modal_pw_prompt_desc", "This archive is encrypted. No matching password was found in your saved list.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                    // Close
                    Text {
                        text: "✕"
                        font.pixelSize: 14
                        color: closePwPromptMouse.containsMouse ? "#F1F5F9" : "#64748B"
                        MouseArea {
                            id: closePwPromptMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (decompressor) decompressor.skipPasswordPrompt(root.promptItemId);
                                root.showPasswordPrompt = false;
                            }
                        }
                    }
                }

                // Archive context box
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: archiveInfoCol.implicitHeight + 20
                    implicitHeight: Layout.preferredHeight
                    radius: 8
                    color: "#131924"
                    border.color: "#1E2D42"
                    border.width: 1
                    ColumnLayout {
                        id: archiveInfoCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                        spacing: 3
                        Row {
                            spacing: 6
                            Text { text: "📦"; font.pixelSize: 11 }
                            Text {
                                text: root.promptFilename
                                font.family: "Segoe UI, Inter, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#38BDF8"
                                elide: Text.ElideMiddle
                                width: pwPromptCard.width - 80
                            }
                        }
                        Row {
                            spacing: 6
                            Text { text: "🎨"; font.pixelSize: 10 }
                            Text {
                                text: root.promptCreator
                                font.pixelSize: 10
                                color: "#94A3B8"
                            }
                            Text { text: "•"; font.pixelSize: 10; color: "#475569" }
                            Text {
                                text: root.promptDirectory
                                font.pixelSize: 9
                                color: "#475569"
                                elide: Text.ElideLeft
                                width: pwPromptCard.width - 120
                            }
                        }
                    }
                }

                // Wrong password banner
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.promptWrongPw ? (wrongPwTxt.implicitHeight + 16) : 0
                    implicitHeight: Layout.preferredHeight
                    radius: 6
                    color: "#3B0A0A"
                    border.color: "#EF4444"
                    border.width: 1
                    visible: root.promptWrongPw
                    Text {
                        id: wrongPwTxt
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 8 }
                        text: "⚠️  Incorrect password — 7-Zip reported 'Wrong password'. Try again."
                        font.pixelSize: 10
                        color: "#FCA5A5"
                        wrapMode: Text.WordWrap
                    }
                }

                // Password input
                Text {
                    text: "Archive Password"
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    color: "#94A3B8"
                }
                Rectangle {
                    id: pwInputRect
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    implicitHeight: 36
                    radius: 7
                    color: pwInput.activeFocus ? "#0B1420" : "#0B0E14"
                    border.color: root.promptWrongPw ? "#F87171" : (pwInput.activeFocus ? "#38BDF8" : "#334155")
                    border.width: pwInput.activeFocus || root.promptWrongPw ? 1.5 : 1

                    SequentialAnimation {
                        id: pwShakeAnim
                        loops: 1
                        PropertyAnimation { target: pwInputRect; property: "x"; to: -6; duration: 40 }
                        PropertyAnimation { target: pwInputRect; property: "x"; to:  6; duration: 40 }
                        PropertyAnimation { target: pwInputRect; property: "x"; to: -4; duration: 40 }
                        PropertyAnimation { target: pwInputRect; property: "x"; to:  4; duration: 40 }
                        PropertyAnimation { target: pwInputRect; property: "x"; to:  0; duration: 40 }
                    }

                    Item {
                        anchors { left: parent.left; right: parent.right; top: parent.top; bottom: parent.bottom; leftMargin: 10; rightMargin: 6 }

                        Text {
                            id: pwInputIcon
                            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                            text: "🔑"
                            font.pixelSize: 12
                        }

                        Text {
                            id: eyeToggle
                            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                            text: pwPromptCard.showPlain ? "🔒" : "👁️"
                            font.pixelSize: 12
                            color: eyeMouse.containsMouse ? "#F1F5F9" : "#64748B"
                            MouseArea {
                                id: eyeMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: pwPromptCard.showPlain = !pwPromptCard.showPlain
                            }
                        }

                        TextInput {
                            id: pwInput
                            anchors {
                                left: pwInputIcon.right; leftMargin: 6
                                right: eyeToggle.left; rightMargin: 6
                                verticalCenter: parent.verticalCenter
                            }
                            height: 32
                            verticalAlignment: TextInput.AlignVCenter
                            font.pixelSize: 12
                            font.family: "Segoe UI, Inter, sans-serif"
                            color: "#E2E8F0"
                            echoMode: pwPromptCard.showPlain ? TextInput.Normal : TextInput.Password
                            onTextChanged: pwPromptCard.inputText = text
                            onAccepted: pwPromptCard.tryExtract()
                            Component.onCompleted: forceActiveFocus()
                        }

                        // Placeholder overlay
                        Text {
                            anchors { left: pwInput.left; verticalCenter: parent.verticalCenter }
                            text: root.tr("placeholder_archive_pw", "Enter archive password...")
                            font.pixelSize: 12
                            font.family: "Segoe UI, Inter, sans-serif"
                            color: "#475569"
                            visible: pwInput.text.length === 0 && !pwInput.activeFocus
                            MouseArea { anchors.fill: parent; onClicked: pwInput.forceActiveFocus() }
                        }
                    }
                }
                Text {
                    text: "Press Enter to test and extract"
                    font.pixelSize: 9
                    color: "#475569"
                }

                // Remember checkbox
                MouseArea {
                    id: rememberMouse
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    Layout.preferredHeight: rememberRow.implicitHeight
                    implicitHeight: rememberRow.implicitHeight
                    Layout.fillWidth: true
                    onClicked: root.promptRemember = !root.promptRemember
                    Row {
                        id: rememberRow
                        spacing: 8
                        Rectangle {
                            width: 16; height: 16; radius: 4
                            color: root.promptRemember ? "#38BDF8" : "#111827"
                            border.color: root.promptRemember ? "#38BDF8" : "#334155"
                            border.width: 1
                            Text { anchors.centerIn: parent; text: "✓"; font.pixelSize: 10; font.weight: Font.Bold; color: "#0F172A"; visible: root.promptRemember }
                        }
                        Text {
                            text: root.tr("chk_remember_archive_pw", "Remember password in Password Bank for future archives")
                            font.pixelSize: 10
                            color: rememberMouse.containsMouse ? "#CBD5E1" : "#94A3B8"
                        }
                    }
                }

                // Action buttons
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    implicitHeight: 34
                    spacing: 8

                    // Skip All Encrypted
                    Rectangle {
                        height: 32
                        implicitWidth: skipAllTxt.implicitWidth + 20
                        radius: 6
                        color: skipAllMouse.containsMouse ? "#1E293B" : "#141C2A"
                        border.color: skipAllMouse.containsMouse ? "#475569" : "#334155"
                        border.width: 1
                        Text {
                            id: skipAllTxt
                            anchors.centerIn: parent
                            text: root.tr("btn_skip_all_encrypted", "Skip All Encrypted")
                            font.pixelSize: 10
                            color: "#94A3B8"
                        }
                        MouseArea {
                            id: skipAllMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (decompressor) decompressor.skipAllPasswordPrompts();
                                root.showPasswordPrompt = false;
                            }
                        }
                    }

                    // Skip this one
                    Rectangle {
                        height: 32
                        implicitWidth: skipOneTxt.implicitWidth + 20
                        radius: 6
                        color: skipOneMouse.containsMouse ? "#1E293B" : "#141C2A"
                        border.color: skipOneMouse.containsMouse ? "#475569" : "#334155"
                        border.width: 1
                        Text {
                            id: skipOneTxt
                            anchors.centerIn: parent
                            text: root.tr("dialog_skip", "Skip")
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                        MouseArea {
                            id: skipOneMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (decompressor) decompressor.skipPasswordPrompt(root.promptItemId);
                                root.showPasswordPrompt = false;
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }

                    // Try & Extract (primary)
                    Rectangle {
                        id: tryExtractBtn
                        height: 32
                        implicitWidth: tryTxt.implicitWidth + 28
                        radius: 6
                        color: (root.promptTesting || pwPromptCard.inputText.length === 0) ? "#0F2A3F"
                             : (tryMouse.containsMouse ? "#0369A1" : "#0284C7")
                        border.color: root.promptTesting ? "#475569" : "#38BDF8"
                        border.width: 1
                        opacity: (root.promptTesting || pwPromptCard.inputText.length === 0) ? 0.7 : 1.0

                        Row {
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                text: root.promptTesting ? "⏳" : "🔓"
                                font.pixelSize: 11
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                id: tryTxt
                                text: root.promptTesting
                                    ? root.tr("btn_testing_pw", "Testing...")
                                    : root.tr("btn_try_extract", "Try & Extract")
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: root.promptTesting ? "#94A3B8" : "#FFFFFF"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: tryMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: (root.promptTesting || pwPromptCard.inputText.length === 0) ? Qt.ArrowCursor : Qt.PointingHandCursor
                            enabled: pwPromptCard.inputText.length > 0 && !root.promptTesting
                            onClicked: pwPromptCard.tryExtract()
                        }
                    }

                }
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // ── 🔑 PASSWORD BANK MODAL ────────────────────────────────────────────────
    // ═══════════════════════════════════════════════════════════════════════════
    Item {
        id: passwordBankOverlay
        anchors.fill: parent
        // Visibility gate: element stays rendered while fading out
        visible: opacity > 0
        opacity: root.showPasswordBank ? 1.0 : 0.0
        z: 999

        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutQuad }
        }

        Rectangle {
            anchors.fill: parent
            color: "#000000"
            opacity: 0.70
            MouseArea { anchors.fill: parent; onClicked: root.showPasswordBank = false }
        }

        Rectangle {
            id: pwBankCard
            anchors.centerIn: parent
            width: Math.min(520, parent.width - 40)
            height: Math.min(620, parent.height - 50)
            radius: 14
            color: "#0F141C"
            border.color: "#38BDF8"
            border.width: 1

            // Absorb mouse clicks so clicking inside the modal dialog never propagates to the backdrop
            MouseArea {
                anchors.fill: parent
            }

            // Newtonian spring animation on modal entry
            scale: root.showPasswordBank ? 1.0 : 0.86
            opacity: root.showPasswordBank ? 1.0 : 0.0
            transformOrigin: Item.Center

            Behavior on scale {
                SpringAnimation {
                    spring: 6.0
                    damping: 0.55
                    mass: 1.0
                    epsilon: 0.001
                }
            }
            Behavior on opacity {
                NumberAnimation { duration: 170; easing.type: Easing.OutQuad }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                // Header
                RowLayout {
                    spacing: 10
                    Text { text: "🔑"; font.pixelSize: 20 }
                    ColumnLayout {
                        spacing: 2
                        Layout.fillWidth: true
                        Text {
                            text: root.tr("title_password_bank", "Decompressor Password Bank")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 14
                            font.weight: 700
                            color: "#38BDF8"
                        }
                        Text {
                            text: root.tr("desc_password_bank", "Passwords saved here are automatically tested when extracting password-protected archives.")
                            font.pixelSize: 10
                            color: "#64748B"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                    Rectangle {
                        implicitWidth: 26
                        implicitHeight: 26
                        radius: 6
                        color: closeBankMouse.containsMouse ? "#1E293B" : "transparent"
                        border.color: closeBankMouse.containsMouse ? "#334155" : "transparent"
                        scale: closeBankMouse.pressed ? 0.85 : (closeBankMouse.containsMouse ? 1.15 : 1.0)
                        transformOrigin: Item.Center

                        Behavior on scale {
                            SpringAnimation { spring: 5.5; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                        }

                        Text {
                            anchors.centerIn: parent
                            text: "✕"
                            font.pixelSize: 14
                            color: closeBankMouse.containsMouse ? "#F1F5F9" : "#64748B"
                        }

                        MouseArea {
                            id: closeBankMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.showPasswordBank = false
                        }
                    }
                }

                // Sync from Link Vault button
                Rectangle {
                    Layout.fillWidth: true
                    height: 30
                    radius: 6
                    color: syncVaultMouse.containsMouse ? "#1E293B" : "#141C2A"
                    border.color: syncVaultMouse.containsMouse ? "#8B5CF6" : "#4C1D95"
                    border.width: 1
                    scale: syncVaultMouse.pressed ? 0.97 : (syncVaultMouse.containsMouse ? 1.015 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                    }

                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🔄"; font.pixelSize: 11 }
                        Text {
                            text: root.tr("btn_sync_vault_pw", "Sync from Link Vault")
                            font.pixelSize: 11
                            font.weight: Font.Medium
                            color: syncVaultMouse.containsMouse ? "#C4B5FD" : "#A78BFA"
                        }
                    }
                    MouseArea {
                        id: syncVaultMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (decompressor) {
                                decompressor.syncFromLinkVault();
                            }
                        }
                    }
                }

                // Passwords tree list
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 8
                    color: "#080C12"
                    border.color: "#1E2638"
                    border.width: 1
                    clip: true

                    // Absorb clicks on empty list areas so they never close the modal
                    MouseArea {
                        anchors.fill: parent
                    }

                    // Empty state
                    Text {
                        anchors.centerIn: parent
                        visible: root.pwBankTree.length === 0
                        text: "No saved passwords yet."
                        font.pixelSize: 12
                        color: "#334155"
                    }

                    ListView {
                        id: bankListView
                        objectName: "bankListView"
                        anchors.fill: parent
                        anchors.margins: 8
                        clip: true
                        spacing: 8
                        model: root.pwBankTree
                        visible: root.pwBankTree.length > 0

                        delegate: Rectangle {
                            id: creatorSectionCard
                            property var creatorData: modelData
                            property bool isCollapsed: root.isBankCreatorCollapsed(creatorData.creator)
                            width: bankListView.width
                            radius: 7
                            // Special Emerald/Teal color highlight if matched to active archives!
                            color: creatorData.isMatched ? "#05261C" : "#0D131F"
                            border.color: creatorData.isMatched ? "#10B981" : "#1E2638"
                            border.width: creatorData.isMatched ? 1.5 : 1
                            clip: true

                            // Physical spring height response for entire card when expanded/collapsed
                            implicitHeight: sectionCol.implicitHeight + 12

                            Behavior on implicitHeight {
                                SpringAnimation {
                                    spring: 4.8
                                    damping: 0.45
                                    mass: 0.9
                                    epsilon: 0.2
                                }
                            }

                            ColumnLayout {
                                id: sectionCol
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 6
                                spacing: 6

                                // Header row
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 32
                                    radius: 5
                                    color: groupHdrMouse.containsMouse 
                                        ? (creatorData.isMatched ? "#065F46" : "#1A2234") 
                                        : (creatorData.isMatched ? "#064E3B" : "#141C2B")
                                    scale: groupHdrMouse.pressed ? 0.985 : (groupHdrMouse.containsMouse ? 1.006 : 1.0)
                                    transformOrigin: Item.Center

                                    Behavior on scale {
                                        SpringAnimation { spring: 5.5; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                                    }

                                    // Background mouse area for header row to toggle collapse
                                    MouseArea {
                                        id: groupHdrMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.toggleBankCreatorCollapse(creatorData.creator)
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 8
                                        anchors.rightMargin: 8
                                        spacing: 8

                                        // Chevron icon with Newtonian rotational inertia
                                        Text {
                                            text: "▼"
                                            font.pixelSize: 10
                                            color: creatorData.isMatched ? "#A7F3D0" : "#64748B"
                                            transformOrigin: Item.Center
                                            rotation: creatorSectionCard.isCollapsed ? -90 : 0

                                            Behavior on rotation {
                                                SpringAnimation {
                                                    spring: 4.5
                                                    damping: 0.36
                                                    mass: 0.85
                                                    epsilon: 0.1
                                                }
                                            }
                                        }

                                        Text {
                                            text: creatorData.isGlobal ? "🌐" : "👤"
                                            font.pixelSize: 12
                                        }

                                        Text {
                                            text: creatorData.creator
                                            font.pixelSize: 12
                                            font.weight: Font.DemiBold
                                            color: creatorData.isMatched ? "#ECFDF5" : "#E2E8F0"
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }

                                        // Special Match Badge
                                        Rectangle {
                                            visible: creatorData.isMatched
                                            height: 18
                                            width: matchBadgeTxt.implicitWidth + 10
                                            radius: 4
                                            color: "#065F46"
                                            border.color: "#10B981"
                                            border.width: 1
                                            Text {
                                                id: matchBadgeTxt
                                                anchors.centerIn: parent
                                                text: "🎯 ACTIVE TARGET"
                                                font.pixelSize: 9
                                                font.weight: Font.Bold
                                                color: "#34D399"
                                            }
                                        }

                                        // Count badge
                                        Rectangle {
                                            height: 18
                                            width: Math.max(18, countBadgeTxt.implicitWidth + 8)
                                            radius: 9
                                            color: creatorData.isMatched ? "#047857" : "#1E293B"
                                            Text {
                                                id: countBadgeTxt
                                                anchors.centerIn: parent
                                                text: creatorData.count
                                                font.pixelSize: 10
                                                font.weight: Font.Bold
                                                color: creatorData.isMatched ? "#D1FAE5" : "#94A3B8"
                                            }
                                        }

                                        // Quick '+' button with Newtonian spring bounce
                                        Rectangle {
                                            id: quickAddBtn
                                            objectName: "quickAddBtn"
                                            z: 2
                                            height: 20
                                            width: 20
                                            radius: 4
                                            color: quickAddMouse.containsMouse ? (creatorData.isMatched ? "#10B981" : "#38BDF8") : "transparent"
                                            scale: quickAddMouse.pressed ? 0.82 : (quickAddMouse.containsMouse ? 1.18 : 1.0)
                                            transformOrigin: Item.Center

                                            Behavior on scale {
                                                SpringAnimation { spring: 6.0; damping: 0.35; mass: 0.75; epsilon: 0.005 }
                                            }

                                            Text {
                                                anchors.centerIn: parent
                                                text: "+"
                                                font.pixelSize: 12
                                                font.weight: Font.Bold
                                                color: quickAddMouse.containsMouse ? "#FFFFFF" : (creatorData.isMatched ? "#A7F3D0" : "#64748B")
                                            }
                                            MouseArea {
                                                id: quickAddMouse
                                                objectName: "quickAddMouse"
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                ToolTip.visible: containsMouse
                                                ToolTip.text: "Add password for " + creatorData.creator
                                                onClicked: {
                                                    root.selectedBankCreator = creatorData.creator;
                                                    root.isCreatorMenuOpen = false;
                                                    addPwInput.forceActiveFocus();
                                                }
                                            }
                                        }
                                    }
                                }

                                // Passwords container with Newtonian physical height expansion & collapse
                                Item {
                                    id: passwordsContainer
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 6
                                    Layout.rightMargin: 6
                                    clip: true
                                    implicitHeight: creatorSectionCard.isCollapsed ? 0 : passwordsInnerCol.implicitHeight
                                    opacity: creatorSectionCard.isCollapsed ? 0.0 : 1.0
                                    visible: implicitHeight > 0

                                    Behavior on implicitHeight {
                                        SpringAnimation {
                                            spring: 4.8
                                            damping: 0.45
                                            mass: 0.9
                                            epsilon: 0.2
                                        }
                                    }
                                    Behavior on opacity {
                                        NumberAnimation { duration: 180; easing.type: Easing.OutQuad }
                                    }

                                    ColumnLayout {
                                        id: passwordsInnerCol
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        spacing: 4

                                        Repeater {
                                            model: creatorData.passwords
                                            delegate: Rectangle {
                                                id: pwRow
                                                property var pwObj: modelData
                                                property string groupCreator: creatorSectionCard.creatorData.creator
                                                Layout.fillWidth: true
                                                height: 28
                                                radius: 5
                                                // Special highlight for matched password
                                                color: pwObj.isMatched ? (pwRowHover.containsMouse ? "#064E3B" : "#062C22")
                                                                       : (pwRowHover.containsMouse ? "#131C2A" : "#0A0E15")
                                                border.color: pwObj.isMatched ? "#059669" : (pwRowHover.containsMouse ? "#28344E" : "#1A2234")
                                                border.width: 1
                                                scale: pwRowHover.pressed ? 0.985 : (pwRowHover.containsMouse ? 1.015 : 1.0)
                                                transformOrigin: Item.Center

                                                Behavior on scale {
                                                    SpringAnimation { spring: 5.5; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                                                }

                                                // Background hover and click-absorber for row
                                                MouseArea {
                                                    id: pwRowHover
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                }

                                                RowLayout {
                                                    anchors.fill: parent
                                                    anchors.leftMargin: 8
                                                    anchors.rightMargin: 8
                                                    spacing: 8

                                                    Text {
                                                        text: pwObj.isMatched ? "🎯" : "🔑"
                                                        font.pixelSize: 10
                                                    }

                                                    Text {
                                                        text: pwObj.password
                                                        font.family: "Consolas, monospace"
                                                        font.pixelSize: 11
                                                        color: pwObj.isMatched ? "#A7F3D0" : "#CBD5E1"
                                                        elide: Text.ElideRight
                                                        Layout.fillWidth: true
                                                    }

                                                    Text {
                                                        text: "Matched"
                                                        font.pixelSize: 9
                                                        font.weight: Font.DemiBold
                                                        color: "#34D399"
                                                        visible: pwObj.isMatched
                                                    }

                                                    // Delete button with spring scale
                                                    Rectangle {
                                                        implicitWidth: 18
                                                        implicitHeight: 18
                                                        radius: 4
                                                        color: delPwRowMouse.containsMouse ? "#2D1515" : "transparent"
                                                        scale: delPwRowMouse.pressed ? 0.80 : (delPwRowMouse.containsMouse ? 1.2 : 1.0)
                                                        transformOrigin: Item.Center

                                                        Behavior on scale {
                                                            SpringAnimation { spring: 6.0; damping: 0.35; mass: 0.75; epsilon: 0.005 }
                                                        }

                                                        Text {
                                                            anchors.centerIn: parent
                                                            text: "✕"
                                                            font.pixelSize: 10
                                                            color: delPwRowMouse.containsMouse ? "#EF4444" : "#475569"
                                                        }

                                                        MouseArea {
                                                            id: delPwRowMouse
                                                            anchors.fill: parent
                                                            hoverEnabled: true
                                                            cursorShape: Qt.PointingHandCursor
                                                            onClicked: {
                                                                if (decompressor) {
                                                                    decompressor.removePassword(pwObj.password, groupCreator);
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
                }

                // Add new password row with creator selector
                RowLayout {
                    id: addPasswordRow
                    Layout.fillWidth: true
                    spacing: 8

                    // Creator Selector Pill Button
                    Rectangle {
                        id: creatorSelectorBtn
                        objectName: "creatorSelectorBtn"
                        height: 34
                        implicitWidth: 135
                        radius: 6
                        color: root.isCreatorMenuOpen ? "#162032" : (creatorBtnMouse.containsMouse ? "#111A29" : "#0B1420")
                        border.color: root.isCreatorMenuOpen ? "#38BDF8" : (creatorBtnMouse.containsMouse ? "#475569" : "#334155")
                        border.width: root.isCreatorMenuOpen ? 1.5 : 1
                        scale: creatorBtnMouse.pressed ? 0.96 : (creatorBtnMouse.containsMouse ? 1.015 : 1.0)
                        transformOrigin: Item.Center

                        Behavior on scale {
                            SpringAnimation { spring: 5.5; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 5

                            Text {
                                text: root.selectedBankCreator === "Global" ? "🌐" : "👤"
                                font.pixelSize: 11
                            }

                            Text {
                                text: root.selectedBankCreator
                                font.pixelSize: 11
                                font.weight: Font.Medium
                                color: root.isCreatorMenuOpen ? "#38BDF8" : "#E2E8F0"
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            Text {
                                text: "▾"
                                font.pixelSize: 10
                                color: root.isCreatorMenuOpen ? "#38BDF8" : "#94A3B8"
                                rotation: root.isCreatorMenuOpen ? 180 : 0
                                transformOrigin: Item.Center

                                Behavior on rotation {
                                    SpringAnimation { spring: 4.5; damping: 0.36; mass: 0.85; epsilon: 0.1 }
                                }
                            }
                        }

                        MouseArea {
                            id: creatorBtnMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.isCreatorMenuOpen = !root.isCreatorMenuOpen;
                                if (root.isCreatorMenuOpen) {
                                    creatorDropdownMenu.forceActiveFocus();
                                    var names = decompressor ? decompressor.bankCreatorNames : ["Global"];
                                    var idx = names.indexOf(root.selectedBankCreator);
                                    if (idx >= 0) {
                                        creatorListView.currentIndex = idx;
                                        creatorListView.positionViewAtIndex(idx, ListView.Center);
                                    }
                                }
                            }
                        }
                    }

                    // Input field
                    Rectangle {
                        Layout.fillWidth: true
                        height: 34
                        radius: 7
                        color: addPwInput.activeFocus ? "#0B1420" : "#0B0E14"
                        border.color: addPwInput.activeFocus ? "#38BDF8" : "#334155"
                        border.width: addPwInput.activeFocus ? 1.5 : 1

                        TextInput {
                            id: addPwInput
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 10; rightMargin: 10 }
                            font.pixelSize: 12
                            font.family: "Segoe UI, Inter, sans-serif"
                            color: "#E2E8F0"
                            onAccepted: {
                                if (text.trim() && decompressor) {
                                    decompressor.addPassword(text.trim(), root.selectedBankCreator);
                                    text = "";
                                }
                            }
                        }
                        // Placeholder overlay
                        Text {
                            anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                            text: "Add password for " + root.selectedBankCreator + "..."
                            font.pixelSize: 12
                            font.family: "Segoe UI, Inter, sans-serif"
                            color: "#475569"
                            visible: addPwInput.text.length === 0 && !addPwInput.activeFocus
                            MouseArea { anchors.fill: parent; onClicked: addPwInput.forceActiveFocus() }
                        }
                    }

                    // Add Button with Newtonian spring feedback
                    Rectangle {
                        id: addPwBtn
                        height: 34
                        implicitWidth: addPwBtnTxt.implicitWidth + 18
                        radius: 6
                        color: addPwBtnMouse.containsMouse ? "#0369A1" : "#0284C7"
                        border.color: "#38BDF8"
                        border.width: 1
                        scale: addPwBtnMouse.pressed ? 0.93 : (addPwBtnMouse.containsMouse ? 1.04 : 1.0)
                        transformOrigin: Item.Center

                        Behavior on scale {
                            SpringAnimation { spring: 5.5; damping: 0.35; mass: 0.75; epsilon: 0.005 }
                        }

                        Text {
                            id: addPwBtnTxt
                            anchors.centerIn: parent
                            text: root.tr("btn_add_pw", "Add")
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }
                        MouseArea {
                            id: addPwBtnMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (addPwInput.text.trim() && decompressor) {
                                    decompressor.addPassword(addPwInput.text.trim(), root.selectedBankCreator);
                                    addPwInput.text = "";
                                }
                            }
                        }
                    }
                }

                // Clear all button with Newtonian spring feedback
                Rectangle {
                    id: clearAllBtn
                    Layout.fillWidth: true
                    height: 30
                    radius: 6
                    color: clearAllMouse.containsMouse ? "#450A0A" : "transparent"
                    border.color: clearAllMouse.containsMouse ? "#EF4444" : "#334155"
                    border.width: 1
                    visible: decompressor && decompressor.savedPasswordsCount > 0
                    scale: clearAllMouse.pressed ? 0.97 : (clearAllMouse.containsMouse ? 1.015 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: "🗑️ Clear All Passwords"
                        font.pixelSize: 10
                        color: clearAllMouse.containsMouse ? "#FCA5A5" : "#64748B"
                    }
                    MouseArea {
                        id: clearAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (decompressor) decompressor.clearSavedPasswords()
                    }
                }

            }

            // Transparent backdrop for creator dropdown: closes dropdown when clicking anywhere else in the modal
            MouseArea {
                anchors.fill: parent
                z: 98
                visible: root.isCreatorMenuOpen
                onClicked: root.isCreatorMenuOpen = false
            }

            // Floating Artist Selector Dropdown Menu
            Rectangle {
                id: creatorDropdownMenu
                objectName: "creatorDropdownMenu"
                z: 99
                visible: opacity > 0
                opacity: root.isCreatorMenuOpen ? 1.0 : 0.0
                scale: root.isCreatorMenuOpen ? 1.0 : 0.93
                transformOrigin: Item.BottomLeft
                focus: root.isCreatorMenuOpen

                Behavior on opacity { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }
                Behavior on scale { SpringAnimation { spring: 5.5; damping: 0.45; mass: 0.85; epsilon: 0.005 } }

                x: 18
                y: (pwBankCard.height - 18 - (clearAllBtn.visible ? 42 : 0) - 34) - height - 6
                width: 230
                height: Math.min(creatorListView.contentHeight + 12, 220)
                radius: 8
                color: "#0C1017"
                border.color: "#38BDF8"
                border.width: 1
                clip: true

                // Keyboard navigation and instant letter-jump (e.g. Press 'E' -> jumps to creators starting with 'E')
                Keys.onPressed: function(event) {
                    if (event.key === Qt.Key_Escape) {
                        root.isCreatorMenuOpen = false;
                        event.accepted = true;
                        return;
                    }
                    if (event.key === Qt.Key_Down) {
                        if (creatorListView.currentIndex < creatorListView.count - 1) {
                            creatorListView.currentIndex++;
                            creatorListView.positionViewAtIndex(creatorListView.currentIndex, ListView.Contain);
                        }
                        event.accepted = true;
                        return;
                    }
                    if (event.key === Qt.Key_Up) {
                        if (creatorListView.currentIndex > 0) {
                            creatorListView.currentIndex--;
                            creatorListView.positionViewAtIndex(creatorListView.currentIndex, ListView.Contain);
                        }
                        event.accepted = true;
                        return;
                    }
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        var names = decompressor ? decompressor.bankCreatorNames : ["Global"];
                        if (creatorListView.currentIndex >= 0 && creatorListView.currentIndex < names.length) {
                            root.selectedBankCreator = names[creatorListView.currentIndex];
                            root.isCreatorMenuOpen = false;
                            addPwInput.forceActiveFocus();
                        }
                        event.accepted = true;
                        return;
                    }

                    var text = event.text;
                    if (text && text.length === 1) {
                        var ch = text.toLowerCase();
                        var names = decompressor ? decompressor.bankCreatorNames : ["Global"];
                        for (var i = 0; i < names.length; i++) {
                            var cName = names[i];
                            if (cName.length > 0 && cName[0].toLowerCase() === ch) {
                                creatorListView.currentIndex = i;
                                creatorListView.positionViewAtIndex(i, ListView.Beginning);
                                event.accepted = true;
                                return;
                            }
                        }
                    }
                }

                ListView {
                    id: creatorListView
                    objectName: "creatorListView"
                    anchors.fill: parent
                    anchors.margins: 6
                    clip: true
                    model: decompressor ? decompressor.bankCreatorNames : ["Global"]
                    currentIndex: {
                        var names = decompressor ? decompressor.bankCreatorNames : ["Global"];
                        var idx = names.indexOf(root.selectedBankCreator);
                        return idx >= 0 ? idx : 0;
                    }
                    spacing: 2

                    ScrollBar.vertical: ScrollBar {
                        id: menuScroll
                        active: true
                        policy: ScrollBar.AsNeeded
                        width: 6
                    }

                    delegate: Rectangle {
                        id: creatorItemDelegate
                        width: creatorListView.width - (menuScroll.visible ? 8 : 0)
                        height: 28
                        radius: 5
                        color: (creatorListView.currentIndex === index || itemMouse.containsMouse) ? "#1E293B" : "transparent"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 6

                            Text {
                                text: modelData === "Global" ? "🌐" : "👤"
                                font.pixelSize: 11
                            }

                            Text {
                                text: modelData
                                font.pixelSize: 11
                                font.family: "Segoe UI, Inter, sans-serif"
                                font.weight: root.selectedBankCreator === modelData ? Font.Bold : Font.Normal
                                color: root.selectedBankCreator === modelData ? "#38BDF8" : (itemMouse.containsMouse ? "#F1F5F9" : "#CBD5E1")
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            Text {
                                text: "✓"
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                color: "#38BDF8"
                                visible: root.selectedBankCreator === modelData
                            }
                        }

                        MouseArea {
                            id: itemMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.selectedBankCreator = modelData;
                                creatorListView.currentIndex = index;
                                root.isCreatorMenuOpen = false;
                                addPwInput.forceActiveFocus();
                            }
                        }
                    }
                }
            }
        }
    }
}
