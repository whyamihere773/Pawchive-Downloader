import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "batch_rename"

// ── Smart Batch Renamer Modal ──────────────────────────────────────────────
// Rule-based bulk file renaming using metadata variables ({artist}, {title}, {captionText}, {post_id}, {date}).
Item {
    id: root

    property var bridge: null
    property bool isOpen: false
    property string folderPath: ""
    property var targetFiles: []

    signal renamed()

    // Form inputs
    property string renamePattern: "{name}.{ext}"
    property string findText: ""
    property string replaceText: ""
    property string prefixText: ""
    property string suffixText: ""
    property string caseMode: "keep"
    property bool filesOnly: true
    property int startIndex: 1
    property bool includeSubfolders: false
    property bool moveToFolder: false
    property string destinationFolder: ""

    // Live preview plan
    property var previewPlan: []
    property int readyCount: 0
    property bool isExecuting: false
    property bool isPreviewing: false

    // Preview, number detection and renaming run in the background (big folders froze the
    // window on every keystroke); only the newest answer is used
    property int _requestSeq: 0
    property string _previewRequest: ""
    property string _indexRequest: ""
    property string _renameRequest: ""
    property string _metaRequest: ""
    property bool isFetchingMetadata: false
    function _newRequest(kind) { _requestSeq += 1; return "rename-" + kind + "-" + _requestSeq }

    function fetchMetadata() {
        if (!bridge || !bridge.refreshPostMetadataAsync) return
        isFetchingMetadata = true
        _metaRequest = _newRequest("metadata")
        bridge.refreshPostMetadataAsync(_metaRequest, folderPath, targetFiles, false)
    }

    Timer {
        id: previewDebounce
        interval: 150
        repeat: false
        onTriggered: root._requestPreview()
    }

    Connections {
        target: root.bridge
        ignoreUnknownSignals: true
        function onAsyncResultReady(requestId, result) {
            if (requestId === root._previewRequest) {
                root._previewRequest = ""
                root.isPreviewing = false
                root._applyPreview(result || [])
            } else if (requestId === root._indexRequest) {
                root._indexRequest = ""
                var detected = (result === undefined || result === null) ? 1 : result
                startField.text = "" + detected
                root.startIndex = detected
                root.updatePreview()
            } else if (requestId === root._renameRequest) {
                root._renameRequest = ""
                root.isExecuting = false
                if (result && result.success) {
                    root.renamed()
                    root.close()
                } else {
                    root.updatePreview()      // show what's left / updated statuses
                }
            } else if (requestId === root._metaRequest) {
                root._metaRequest = ""
                root.isFetchingMetadata = false
                root.updatePreview()
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
    function open(currentFolder, files) {
        folderPath = currentFolder || ""
        destinationFolder = currentFolder || ""
        targetFiles = files || []
        renamePattern = "{name}.{ext}"
        findText = ""
        replaceText = ""
        prefixText = ""
        suffixText = ""
        caseMode = "keep"
        filesOnly = true
        startIndex = 1
        includeSubfolders = false
        moveToFolder = false
        if (patternField) patternField.text = "{name}.{ext}"
        if (findField) findField.text = ""
        if (replaceField) replaceField.text = ""
        if (prefixField) prefixField.text = ""
        if (suffixField) suffixField.text = ""
        if (startField) startField.text = "1"
        isOpen = true
        updatePreview()
    }

    function close() {
        isOpen = false
    }

    function insertToken(token) {
        patternField.text = patternField.text + token
        renamePattern = patternField.text
        updatePreview()
    }

    function updatePreview() {
        if (!isOpen) return
        previewDebounce.restart()
    }

    function detectNextIndex() {
        if (!bridge || !bridge.detectNextIndexAsync) return
        var scanTarget = (root.moveToFolder && root.destinationFolder) ? root.destinationFolder : root.folderPath
        _indexRequest = _newRequest("index")
        bridge.detectNextIndexAsync(_indexRequest, scanTarget)
    }

    function _requestPreview() {
        if (!isOpen || !bridge || !bridge.previewBatchRenameAsync) return
        var filteredList = targetFiles || []
        if (filesOnly && !includeSubfolders) {
            filteredList = filteredList.filter(function(it) {
                return it && !it.is_dir
            })
        }
        isPreviewing = true
        _previewRequest = _newRequest("preview")
        bridge.previewBatchRenameAsync(
            _previewRequest,
            folderPath,
            filteredList,
            renamePattern,
            findText,
            replaceText,
            prefixText,
            suffixText,
            caseMode,
            startIndex,
            includeSubfolders,
            moveToFolder,
            destinationFolder
        )
    }

    function _applyPreview(plan) {
        previewPlan = plan

        var ready = 0
        for (var i = 0; i < plan.length; i++) {
            if (plan[i].status === "ready") ready++
        }
        readyCount = ready
    }

    function executeRename() {
        if (!bridge || !bridge.executeBatchRenameAsync || readyCount === 0 || root.isPathBlocked || isExecuting) return
        isExecuting = true
        _renameRequest = _newRequest("run")
        bridge.executeBatchRenameAsync(_renameRequest, previewPlan)
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

                Text { text: "🏷️"; font.pixelSize: 22 }

                ColumnLayout {
                    spacing: 2
                    Text {
                        text: "Smart Batch Renamer"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 16
                        font.weight: 700
                        color: "#F8FAFC"
                    }
                    Text {
                        text: "Rule-based bulk file renaming using metadata variables ({artist}, {title}, {captionText}, {date})"
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
                        ToolTip.delay: 300
                        ToolTip.text: "Close batch renamer without applying changes"
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
                              ((root.pathSafety && root.pathSafety.message) ? ("Operating System Protection: " + root.pathSafety.message) : "Operating System Protection: Batch renaming is permanently disabled on this path.") :
                              ("Root Drive Selected (" + (root.pathSafety ? root.pathSafety.drive_letter : "") + "\\): Batch renaming here will affect root-level files. Exercise extreme caution.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: root.isPathBlocked ? "#FCA5A5" : "#FDE68A"
                        elide: Text.ElideRight
                    }
                }
            }

            // Unified Single-Row Controls Bar
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                // 1. Renaming Pattern
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 170
                    spacing: 3
                    Text { text: "Pattern:"; font.pixelSize: 10; font.weight: 600; color: "#38BDF8" }
                    TextField {
                        id: patternField
                        Layout.fillWidth: true
                        text: root.renamePattern
                        placeholderText: "{name}.{ext}"
                        placeholderTextColor: "#64748B"
                        font.family: "Segoe UI, monospace"
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        verticalAlignment: TextInput.AlignVCenter
                        background: Rectangle {
                            color: patternField.activeFocus ? "#0B0D12" : "#0B0E16"
                            radius: 5
                            border.color: patternField.activeFocus ? "#38BDF8" : (patternField.hovered ? "#475569" : "#273349")
                            border.width: patternField.activeFocus ? 1.5 : 1
                        }
                        onTextEdited: {
                            root.renamePattern = text
                            root.updatePreview()
                        }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Rename Pattern\nTemplate used to generate new filenames.\nInsert variables such as {name}, {ext}, {artist}, {index}, etc."
                        TextBarContextArea {}
                    }
                }

                // 2. Find
                ColumnLayout {
                    Layout.preferredWidth: 85
                    spacing: 3
                    Text { text: "Find:"; font.pixelSize: 10; font.weight: 600; color: "#94A3B8" }
                    TextField {
                        id: findField
                        Layout.fillWidth: true
                        placeholderText: "Find text..."
                        placeholderTextColor: "#64748B"
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        verticalAlignment: TextInput.AlignVCenter
                        background: Rectangle { color: findField.activeFocus ? "#0B0D12" : "#0B0E16"; radius: 5; border.color: findField.activeFocus ? "#38BDF8" : (findField.hovered ? "#475569" : "#273349"); border.width: findField.activeFocus ? 1.5 : 1 }
                        onTextEdited: { root.findText = text; root.updatePreview() }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Find Text\nSubstring to search for in filenames to replace."
                        TextBarContextArea {}
                    }
                }

                // 3. Replace
                ColumnLayout {
                    Layout.preferredWidth: 85
                    spacing: 3
                    Text { text: "Replace:"; font.pixelSize: 10; font.weight: 600; color: "#94A3B8" }
                    TextField {
                        id: replaceField
                        Layout.fillWidth: true
                        placeholderText: "Replace..."
                        placeholderTextColor: "#64748B"
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        verticalAlignment: TextInput.AlignVCenter
                        background: Rectangle { color: replaceField.activeFocus ? "#0B0D12" : "#0B0E16"; radius: 5; border.color: replaceField.activeFocus ? "#38BDF8" : (replaceField.hovered ? "#475569" : "#273349"); border.width: replaceField.activeFocus ? 1.5 : 1 }
                        onTextEdited: { root.replaceText = text; root.updatePreview() }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Replace Text\nNew text to insert in place of the matched find text."
                        TextBarContextArea {}
                    }
                }

                // 4. Prefix
                ColumnLayout {
                    Layout.preferredWidth: 70
                    spacing: 3
                    Text { text: "Prefix:"; font.pixelSize: 10; font.weight: 600; color: "#94A3B8" }
                    TextField {
                        id: prefixField
                        Layout.fillWidth: true
                        placeholderText: "Prefix..."
                        placeholderTextColor: "#64748B"
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        verticalAlignment: TextInput.AlignVCenter
                        background: Rectangle { color: prefixField.activeFocus ? "#0B0D12" : "#0B0E16"; radius: 5; border.color: prefixField.activeFocus ? "#38BDF8" : (prefixField.hovered ? "#475569" : "#273349"); border.width: prefixField.activeFocus ? 1.5 : 1 }
                        onTextEdited: { root.prefixText = text; root.updatePreview() }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Prefix\nText prepended to the start of each file or folder name."
                        TextBarContextArea {}
                    }
                }

                // 5. Suffix
                ColumnLayout {
                    Layout.preferredWidth: 70
                    spacing: 3
                    Text { text: "Suffix:"; font.pixelSize: 10; font.weight: 600; color: "#94A3B8" }
                    TextField {
                        id: suffixField
                        Layout.fillWidth: true
                        placeholderText: "Suffix..."
                        placeholderTextColor: "#64748B"
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        verticalAlignment: TextInput.AlignVCenter
                        background: Rectangle { color: suffixField.activeFocus ? "#0B0D12" : "#0B0E16"; radius: 5; border.color: suffixField.activeFocus ? "#38BDF8" : (suffixField.hovered ? "#475569" : "#273349"); border.width: suffixField.activeFocus ? 1.5 : 1 }
                        onTextEdited: { root.suffixText = text; root.updatePreview() }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Suffix\nText appended to the end of each name before the extension."
                        TextBarContextArea {}
                    }
                }

                // 6. Start # with ⚡ Auto Next button
                ColumnLayout {
                    Layout.preferredWidth: 90
                    spacing: 3
                    RowLayout {
                        spacing: 4
                        Text { text: "Start #:"; font.pixelSize: 10; font.weight: 600; color: "#A78BFA" }
                        Rectangle {
                            implicitHeight: 14
                            implicitWidth: autoTxt.implicitWidth + 8
                            radius: 3
                            color: autoMouse.containsMouse ? "#6366F1" : "#312E81"
                            border.color: autoMouse.containsMouse ? "#A5B4FC" : "#6366F1"
                            border.width: 1
                            Text {
                                id: autoTxt
                                anchors.centerIn: parent
                                text: "⚡ Auto"
                                font.pixelSize: 8
                                font.weight: 700
                                color: "#E0E7FF"
                            }
                            Springy { hover: autoMouse.containsMouse; pressed: autoMouse.pressed }
                            MouseArea {
                                id: autoMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.detectNextIndex()
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Auto-detect Next Number\nScans existing files in target folder or previous numbered volume (e.g. Folder 1 ending at 100) to continue numbering."
                            }
                        }
                    }
                    TextField {
                        id: startField
                        Layout.fillWidth: true
                        text: "" + root.startIndex
                        placeholderText: "1"
                        placeholderTextColor: "#64748B"
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        verticalAlignment: TextInput.AlignVCenter
                        validator: IntValidator { bottom: 0; top: 9999999 }
                        background: Rectangle {
                            color: startField.activeFocus ? "#0B0D12" : "#0B0E16"
                            radius: 5
                            border.color: startField.activeFocus ? "#A78BFA" : (startField.hovered ? "#475569" : "#273349")
                            border.width: startField.activeFocus ? 1.5 : 1
                        }
                        onTextEdited: {
                            var val = parseInt(text)
                            root.startIndex = isNaN(val) ? 1 : val
                            root.updatePreview()
                        }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Start Number\nStarting sequential index for {index}, {0index}, {00index}, and {000index}.\nIncrements by 1 for each file in sequence."
                        TextBarContextArea {}
                    }
                }

                // 7. Case Mode
                ColumnLayout {
                    spacing: 3
                    Text { text: "Case Mode:"; font.pixelSize: 10; font.weight: 600; color: "#94A3B8" }
                    Row {
                        spacing: 2
                        Repeater {
                            model: [
                                { mode: "keep", label: "Keep", tip: "Preserve original character casing as-is" },
                                { mode: "lower", label: "lower", tip: "Convert all characters to lowercase (e.g. photo.jpg)" },
                                { mode: "upper", label: "UPPER", tip: "Convert all characters to uppercase (e.g. PHOTO.JPG)" },
                                { mode: "title", label: "Title", tip: "Capitalize the first letter of each word (e.g. Photo Title.jpg)" }
                            ]
                            delegate: Rectangle {
                                implicitHeight: 28
                                implicitWidth: cmText.implicitWidth + 10
                                radius: 4
                                color: root.caseMode === modelData.mode ? "#202E47" : "#0E131E"
                                border.color: root.caseMode === modelData.mode ? "#38BDF8" : "#232F45"
                                border.width: 1
                                Text {
                                    id: cmText
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: root.caseMode === modelData.mode ? 700 : Font.Normal
                                    color: root.caseMode === modelData.mode ? "#38BDF8" : "#94A3B8"
                                }
                                Springy { hover: cmMouse.containsMouse; pressed: cmMouse.pressed }
                                MouseArea {
                                    id: cmMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.caseMode = modelData.mode
                                        root.updatePreview()
                                    }
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 250
                                    ToolTip.text: modelData.tip
                                }
                            }
                        }
                    }
                }
            }

            // Quick Insertion Tokens Row
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Text { text: "Tokens:"; font.pixelSize: 10; font.weight: 600; color: "#64748B" }

                Repeater {
                    model: [
                        { label: "{name}", tip: "Original filename without extension (e.g. 'preview_01')" },
                        { label: "{ext}", tip: "File extension without dot (e.g. 'jpg', 'png', 'mp4')" },
                        { label: "{artist}", tip: "Creator/artist name extracted from [Artist] tag or parent folder" },
                        { label: "{title}", tip: "Clean post or file title with IDs and brackets removed" },
                        { label: "{captionText}", tip: "Post caption or description text from post_info.txt or metadata" },
                        { label: "{post_id}", tip: "Numeric post ID (5-10 digits) if found in name or folder" },
                        { label: "{date}", tip: "File modification date formatted as YYYY-MM-DD" },
                        { label: "{index}", tip: "Sequential number starting from Start # (e.g. 1, 2, ..., 101)" },
                        { label: "{0index}", tip: "2-digit zero-padded index (e.g. 01, 02, ..., 99, 100)" },
                        { label: "{00index}", tip: "3-digit zero-padded index (e.g. 001, 002, ..., 100)" },
                        { label: "{000index}", tip: "4-digit zero-padded index (e.g. 0001, 0002, ..., 1000)" }
                    ]
                    delegate: Rectangle {
                        implicitHeight: 20
                        implicitWidth: chipTxt.implicitWidth + 10
                        radius: 4
                        color: chipMouse.containsMouse ? "#2A364E" : "#171F2F"
                        border.color: chipMouse.containsMouse ? "#38BDF8" : "#2B3852"
                        border.width: 1

                        Text {
                            id: chipTxt
                            anchors.centerIn: parent
                            text: modelData.label
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#38BDF8"
                        }
                        Springy { hover: chipMouse.containsMouse; pressed: chipMouse.pressed }
                        MouseArea {
                            id: chipMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: insertToken(modelData.label)
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: modelData.tip + "\nClick to insert into pattern"
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    implicitHeight: 20
                    implicitWidth: fetchMetaRow.implicitWidth + 12
                    radius: 4
                    color: fetchMetaMouse.containsMouse ? "#1E2A40" : "#131A26"
                    border.color: fetchMetaMouse.containsMouse ? "#38BDF8" : "#2B3852"
                    border.width: 1

                    RowLayout {
                        id: fetchMetaRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "🔄"; font.pixelSize: 9 }
                        Text {
                            text: root.isFetchingMetadata ? "Fetching…" : "Fetch Metadata"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: root.isFetchingMetadata ? "#F59E0B" : "#38BDF8"
                        }
                    }

                    MouseArea {
                        id: fetchMetaMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: !root.isFetchingMetadata
                        onClicked: root.fetchMetadata()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "Fetch post titles & captions from Pawchive/Kemono API\nSaves metadata to disk and populates {captionText}"
                    }
                }
            }

            // Advanced Options & Move-to-Folder Bar
            BatchRenameOptionsRow {
                modal: root
            }

            // Preview Table Header & Virtualized List
            BatchRenamePreviewTable {
                modal: root
            }

            // Bottom Actions Bar
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Text {
                    text: root.readyCount + " of " + root.previewPlan.length + " files ready to " + (root.moveToFolder ? "rename & move" : "rename")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: root.readyCount > 0 ? "#10B981" : "#94A3B8"
                }

                Item { Layout.fillWidth: true }

                // Cancel button
                Rectangle {
                    implicitHeight: 32
                    implicitWidth: 80
                    radius: 6
                    color: cancelMouse.containsMouse ? "#242D40" : "#161D2B"
                    border.color: "#2C374D"
                    border.width: 1

                    Text { anchors.centerIn: parent; text: "Cancel"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; color: "#E2E8F0" }
                    Springy { hover: cancelMouse.containsMouse; pressed: cancelMouse.pressed }
                    MouseArea {
                        id: cancelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.close()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "Close this dialog without making any changes"
                    }
                }

                // Apply Rename button
                Rectangle {
                    implicitHeight: 32
                    implicitWidth: applyText.implicitWidth + 24
                    radius: 6
                    color: root.isPathBlocked ? "#1E2433" : (root.readyCount > 0 ? (applyMouse.containsMouse ? "#4F46E5" : "#4338CA") : "#222634")
                    border.color: root.isPathBlocked ? "#2D3748" : (root.readyCount > 0 ? "#6366F1" : "#323747")
                    border.width: 1
                    opacity: root.isPathBlocked ? 0.35 : (root.readyCount > 0 ? 1.0 : 0.5)

                    Text {
                        id: applyText
                        anchors.centerIn: parent
                        text: root.isPathBlocked ? "Renaming Disabled on System Root" : (root.isExecuting ? (root.moveToFolder ? "Moving..." : "Renaming...") : ((root.moveToFolder ? "Apply Rename & Move (" : "Apply Rename (") + root.readyCount + ")"))
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 700
                        color: "#FFFFFF"
                    }
                    Springy { hover: applyMouse.containsMouse; pressed: applyMouse.pressed }
                    MouseArea {
                        id: applyMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: root.isPathBlocked ? Qt.ForbiddenCursor : (root.readyCount > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor)
                        onClicked: {
                            if (!root.isPathBlocked && root.readyCount > 0 && !root.isExecuting) {
                                executeRename()
                            }
                        }
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: root.isPathBlocked ?
                            ("Action Blocked: Cannot execute batch renaming on Windows system drive root (" + (root.pathSafety ? root.pathSafety.drive_letter : "C:") + "\\)") :
                            (root.readyCount > 0 ? ("Execute " + (root.moveToFolder ? "renaming and moving" : "renaming") + " for " + root.readyCount + " files.") : "No files are ready to rename. Adjust your rules or pattern.")
                    }
                }
            }
        }
    }
}
