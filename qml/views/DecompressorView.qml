import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "decompressor"

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
    property var pwBankTree: []          // filled when the Password Bank opens (and while it is open)

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

    // End of a run with "Compress after extracting": keep or remove the originals
    property bool showCompressReview: false
    property int compressedCount: 0
    property real compressedBefore: 0
    property real compressedAfter: 0
    property int compressFailed: 0
    property string compressNote: ""

    // Redecompress confirm modal state
    property bool showRedecompressModal: false
    property int redecompressAlreadyDoneCount: 0
    property int redecompressTotalCount: 0

    // The archive rows' texts, looked up once (and again when the language changes): each row asked for
    // ~15 translations through Python, which made building rows while scrolling a long list stall
    readonly property var rowText: ({
        btn_try_extract: tr("btn_try_extract", "Try & Extract"),
        decompressor_already_extracted: tr("decompressor_already_extracted", "Already Extracted"),
        decompressor_compressing: tr("decompressor_compressing", "Compressing pictures and videos…"),
        decompressor_creator_toggle_tip: tr("decompressor_creator_toggle_tip", "Toggle all archives for this creator"),
        decompressor_done: tr("decompressor_done", "Extracted"),
        decompressor_error: tr("decompressor_error", "Error"),
        decompressor_pending: tr("decompressor_pending", "Pending"),
        decompressor_pre_extracted: tr("decompressor_pre_extracted", "Pre-extracted"),
        status_password_required: tr("status_password_required", "Password Required"),
        tip_already_extracted: tr("tip_already_extracted", "Files from this archive are already present on disk. Selecting it will re-extract and overwrite them."),
        tip_enter_password: tr("tip_enter_password", "Enter password to decrypt this archive"),
        tip_open_folder: tr("tip_open_folder", "Open folder in File Explorer"),
        tip_pre_extracted: tr("tip_pre_extracted", "This archive was already extracted before scanning. Select it and re-run to overwrite.")
    })

    readonly property bool optionsOpen: !(decompressor && decompressor.headerCollapsed)
    readonly property bool isNarrow: root.width < 760
    readonly property bool isVeryNarrow: root.width < 520


    // Same as every other view (this used to ask the bridge, which has no translations, so the tab
    // always stayed in English)
    function tr(key, def) {
        if (typeof Lang === "undefined" || !Lang) return def !== undefined ? def : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (def !== undefined ? def : res)
    }

    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "0 B";
        var k = 1024;
        var sizes = ["B", "KB", "MB", "GB", "TB"];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        if (i >= sizes.length) i = sizes.length - 1;
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    }

    // Folding a creator's group is kept in Python: the list only holds the rows of open groups
    function isCreatorCollapsed(grp) {
        return !!grp.collapsed;
    }

    function toggleCreatorCollapse(grp) {
        if (decompressor) decompressor.toggleGroupCollapsed(grp.groupKey);
    }

    function expandAllCreators() {
        if (decompressor) decompressor.setAllCollapsed(false);
    }

    function collapseAllCreators() {
        if (decompressor) decompressor.setAllCollapsed(true);
    }

    // The groups shown (one per creator and folder), kept in Python: only the groups that change are redrawn
    readonly property var groupsModel: decompressor ? decompressor.groupsModel : null
    readonly property int groupCount: decompressor ? decompressor.groupCount : 0

    Connections {
        target: decompressor
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
        function onCompressionReviewRequested(count, before, after, failed) {
            root.compressedCount = count;
            root.compressedBefore = before;
            root.compressedAfter = after;
            root.compressFailed = failed;
            root.compressNote = "";
            root.showCompressReview = true;
        }
        function onOriginalsHandled(message) {
            root.compressNote = message;
        }
        function onPasswordBankChanged() {
            // (only while the Password Bank is open: it's rebuilt for every archive, and this fires at
            // every selection change; opening it reads it fresh)
            if (root.showPasswordBank) root.pwBankTree = root.parsePasswordBankTree();
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
                passwordPromptOverlay.handleWrongPassword();
            }
        }
        function onRedecompressConfirmRequested(alreadyDone, total) {
            root.redecompressAlreadyDoneCount = alreadyDone;
            root.redecompressTotalCount = total;
            root.showRedecompressModal = true;
        }
    }

    // The whole page scrolls once its parts don't fit (smooth, speed-scaled flicks); the archive list
    // keeps at least a usable height and hands the wheel on to the page at its top / bottom
    SmoothFlickable {
        id: pageFlick
        objectName: "decompressorPage"
        anchors.fill: parent
        contentWidth: width
        contentHeight: pageCol.implicitHeight + 32
    }

    ColumnLayout {
        id: pageCol
        parent: pageFlick.contentItem
        x: 16
        y: 16
        width: pageFlick.width - 32
        height: Math.max(pageFlick.height - 32, implicitHeight)
        spacing: 12

        DecompressorHeaderCard {
            view: root
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

                Text {
                    Layout.fillWidth: true
                    visible: root.compressNote.length > 0
                    text: "🗜 " + root.compressNote
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#7DD3FC"
                    wrapMode: Text.WordWrap
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
                        text: (decompressor && decompressor.anyCollapsed)
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
                            if (decompressor && decompressor.anyCollapsed) {
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
                    color: searchInputWide.activeFocus ? "#0B0D12" : "#111827"
                    border.color: searchInputWide.activeFocus ? "#6366F1" : (searchWideBoxMouse.containsMouse ? "#475569" : "#1E293B")
                    border.width: searchInputWide.activeFocus ? 1.5 : 1

                    TextBarContextArea {
                        id: searchWideBoxMouse
                        target: searchInputWide
                        focusOnLeftClick: true
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 4

                        Text { text: "🔍"; font.pixelSize: 10; color: "#64748B" }
                        TextInput {
                            id: searchInputWide
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#E2E8F0"
                            selectionColor: "#0284C7"
                            selectedTextColor: "#FFFFFF"
                            selectByMouse: true
                            clip: true
                            text: root.searchText
                            TextBarContextArea {}
                            Text {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight
                                text: root.tr("placeholder_decompressor_search", "Filter archives or creators...")
                                font: parent.font
                                color: "#475569"
                                visible: !searchInputWide.text && !searchInputWide.activeFocus
                            }
                            onTextChanged: {
                                if (root.searchText !== text) {
                                    root.searchText = text;
                                    if (decompressor) decompressor.setSearch(text);
                                }
                            }
                        }
                        Rectangle {
                            width: 16; height: 16; radius: 8
                            color: clearDecWideMouse.containsMouse ? "#374151" : "#1F2430"
                            visible: searchInputWide.text.length > 0
                            Text { anchors.centerIn: parent; text: "×"; font.bold: true; font.pixelSize: 11; color: "#94A3B8" }
                            MouseArea {
                                id: clearDecWideMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    searchInputWide.text = ""
                                    searchInputWide.forceActiveFocus()
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
                color: searchInputNarrow.activeFocus ? "#0B0D12" : "#111827"
                border.color: searchInputNarrow.activeFocus ? "#6366F1" : (searchNarrowBoxMouse.containsMouse ? "#475569" : "#1E293B")
                border.width: searchInputNarrow.activeFocus ? 1.5 : 1

                TextBarContextArea {
                    id: searchNarrowBoxMouse
                    target: searchInputNarrow
                    focusOnLeftClick: true
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 6

                    Text { text: "🔍"; font.pixelSize: 10; color: "#64748B" }
                    TextInput {
                        id: searchInputNarrow
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        verticalAlignment: TextInput.AlignVCenter
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#E2E8F0"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        text: root.searchText
                        TextBarContextArea {}
                        Text {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            elide: Text.ElideRight
                            text: root.tr("placeholder_decompressor_search", "Filter archives or creators...")
                            font: parent.font
                            color: "#475569"
                            visible: !searchInputNarrow.text && !searchInputNarrow.activeFocus
                        }
                        onTextChanged: {
                            if (root.searchText !== text) {
                                root.searchText = text;
                                if (decompressor) decompressor.setSearch(text);
                            }
                        }
                    }
                    Rectangle {
                        width: 16; height: 16; radius: 8
                        color: clearDecNarrowMouse.containsMouse ? "#374151" : "#1F2430"
                        visible: searchInputNarrow.text.length > 0
                        Text { anchors.centerIn: parent; text: "×"; font.bold: true; font.pixelSize: 11; color: "#94A3B8" }
                        MouseArea {
                            id: clearDecNarrowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                searchInputNarrow.text = ""
                                searchInputNarrow.forceActiveFocus()
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
                              root.groupCount + " " + (root.groupCount === 1 ? "Creator" : "Creators"))
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

        DecompressorArchiveList {
            view: root
            pageFlick: pageFlick
        }
    }


    DecompressorDiskCheckModal {
        view: root
    }

    DecompressorRedecompressModal {
        view: root
    }

    DecompressorCompressReviewModal {
        view: root
    }

    DecompressorPasswordPromptModal {
        id: passwordPromptOverlay
        view: root
    }

    DecompressorPasswordBankModal {
        id: passwordBankOverlay
        view: root
    }
}
