import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Smart Batch Renamer Modal ──────────────────────────────────────────────
// Rule-based bulk file renaming using metadata variables ({artist}, {post_id}, {title}, {date}).
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
    function _newRequest(kind) { _requestSeq += 1; return "rename-" + kind + "-" + _requestSeq }

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
                        text: "Rule-based bulk file renaming using metadata variables ({artist}, {post_id}, {title}, {date})"
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
                        font.family: "Segoe UI, monospace"
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        background: Rectangle {
                            color: "#0B0E16"
                            radius: 5
                            border.color: patternField.activeFocus ? "#38BDF8" : "#273349"
                            border.width: 1
                        }
                        onTextEdited: {
                            root.renamePattern = text
                            root.updatePreview()
                        }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Rename Pattern\nTemplate used to generate new filenames.\nInsert variables such as {name}, {ext}, {artist}, {index}, etc."
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
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        background: Rectangle { color: "#0B0E16"; radius: 5; border.color: "#273349"; border.width: 1 }
                        onTextEdited: { root.findText = text; root.updatePreview() }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Find Text\nSubstring to search for in filenames to replace."
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
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        background: Rectangle { color: "#0B0E16"; radius: 5; border.color: "#273349"; border.width: 1 }
                        onTextEdited: { root.replaceText = text; root.updatePreview() }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Replace Text\nNew text to insert in place of the matched find text."
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
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        background: Rectangle { color: "#0B0E16"; radius: 5; border.color: "#273349"; border.width: 1 }
                        onTextEdited: { root.prefixText = text; root.updatePreview() }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Prefix\nText prepended to the start of each file or folder name."
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
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        background: Rectangle { color: "#0B0E16"; radius: 5; border.color: "#273349"; border.width: 1 }
                        onTextEdited: { root.suffixText = text; root.updatePreview() }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Suffix\nText appended to the end of each name before the extension."
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
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        validator: IntValidator { bottom: 0; top: 9999999 }
                        background: Rectangle {
                            color: "#0B0E16"
                            radius: 5
                            border.color: startField.activeFocus ? "#A78BFA" : "#273349"
                            border.width: 1
                        }
                        onTextEdited: {
                            var val = parseInt(text)
                            root.startIndex = isNaN(val) ? 1 : val
                            root.updatePreview()
                        }
                        ToolTip.visible: hovered
                        ToolTip.delay: 350
                        ToolTip.text: "Start Number\nStarting sequential index for {index}, {0index}, {00index}, and {000index}.\nIncrements by 1 for each file in sequence."
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
            }

            // Advanced Options & Move-to-Folder Bar
            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                // Option 1: Files only
                RowLayout {
                    spacing: 5
                    Layout.alignment: Qt.AlignVCenter
                    Rectangle {
                        width: 14; height: 14; radius: 3
                        color: root.filesOnly ? "#38BDF8" : "#161D2B"
                        border.color: "#374151"; border.width: 1
                        Text { visible: root.filesOnly; anchors.centerIn: parent; text: "✓"; font.pixelSize: 9; font.weight: Font.Bold; color: "#0B0E14" }
                        Springy { hover: filesOnlyMouse.containsMouse; pressed: filesOnlyMouse.pressed }
                        MouseArea {
                            id: filesOnlyMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.filesOnly = !root.filesOnly
                                root.updatePreview()
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "When checked, only renames individual files and skips modifying subfolder names."
                        }
                    }
                    Text {
                        text: "Files only (skip folders)"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.filesOnly = !root.filesOnly
                                root.updatePreview()
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "When checked, only renames individual files and skips modifying subfolder names."
                        }
                    }
                }

                // Option 2: Include subfolders (continuous numbering)
                RowLayout {
                    spacing: 5
                    Layout.alignment: Qt.AlignVCenter
                    Rectangle {
                        width: 14; height: 14; radius: 3
                        color: root.includeSubfolders ? "#818CF8" : "#161D2B"
                        border.color: "#374151"; border.width: 1
                        Text { visible: root.includeSubfolders; anchors.centerIn: parent; text: "✓"; font.pixelSize: 9; font.weight: Font.Bold; color: "#0B0E14" }
                        Springy { hover: subfoldersMouse.containsMouse; pressed: subfoldersMouse.pressed }
                        MouseArea {
                            id: subfoldersMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.includeSubfolders = !root.includeSubfolders
                                root.updatePreview()
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Recursively scans files in all subfolders and numbers them continuously across folders\n(e.g. Folder 1 gets 1-100, Folder 2 starts at 101)."
                        }
                    }
                    Text {
                        text: "Include subfolders (continuous sequence)"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: root.includeSubfolders ? "#C7D2FE" : "#94A3B8"
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.includeSubfolders = !root.includeSubfolders
                                root.updatePreview()
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Recursively scans files in all subfolders and numbers them continuously across folders\n(e.g. Folder 1 gets 1-100, Folder 2 starts at 101)."
                        }
                    }
                }

                // Option 3: Move all into folder
                RowLayout {
                    spacing: 5
                    Layout.alignment: Qt.AlignVCenter
                    Rectangle {
                        width: 14; height: 14; radius: 3
                        color: root.moveToFolder ? "#10B981" : "#161D2B"
                        border.color: "#374151"; border.width: 1
                        Text { visible: root.moveToFolder; anchors.centerIn: parent; text: "✓"; font.pixelSize: 9; font.weight: Font.Bold; color: "#0B0E14" }
                        Springy { hover: moveFolderMouse.containsMouse; pressed: moveFolderMouse.pressed }
                        MouseArea {
                            id: moveFolderMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.moveToFolder = !root.moveToFolder
                                root.updatePreview()
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Flattens and moves all renamed files into a single destination folder."
                        }
                    }
                    Text {
                        text: "Move all into folder"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: root.moveToFolder ? "#6EE7B7" : "#94A3B8"
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.moveToFolder = !root.moveToFolder
                                root.updatePreview()
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Flattens and moves all renamed files into a single destination folder."
                        }
                    }
                }

                // Destination Folder Indicator & Picker
                RowLayout {
                    visible: root.moveToFolder
                    spacing: 5
                    Layout.alignment: Qt.AlignVCenter

                    Rectangle {
                        implicitHeight: 22
                        implicitWidth: Math.min(220, destLabel.implicitWidth + 14)
                        radius: 4
                        color: "#0B1D15"
                        border.color: "#059669"
                        border.width: 1
                        clip: true
                        Text {
                            id: destLabel
                            anchors.centerIn: parent
                            text: "📁 " + (root.destinationFolder ? root.destinationFolder : "Current Folder")
                            elide: Text.ElideMiddle
                            maximumLineCount: 1
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 9
                            color: "#A7F3D0"
                        }
                        MouseArea {
                            id: destPillMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Target destination folder where renamed files will be moved:\n" + (root.destinationFolder || root.folderPath)
                        }
                    }

                    Rectangle {
                        implicitHeight: 22
                        implicitWidth: changeDestTxt.implicitWidth + 12
                        radius: 4
                        color: changeDestMouse.containsMouse ? "#10B981" : "#065F46"
                        border.color: "#059669"
                        border.width: 1
                        Text {
                            id: changeDestTxt
                            anchors.centerIn: parent
                            text: "Change..."
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 9
                            font.weight: 600
                            color: "#FFFFFF"
                        }
                        Springy { hover: changeDestMouse.containsMouse; pressed: changeDestMouse.pressed }
                        MouseArea {
                            id: changeDestMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.bridge && root.bridge.browseFolderDialog) {
                                    var chosen = root.bridge.browseFolderDialog("Select Target Destination Folder", root.destinationFolder || root.folderPath)
                                    if (chosen && chosen.length > 0) {
                                        root.destinationFolder = chosen
                                        root.updatePreview()
                                    }
                                }
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Browse and select a different target folder or drive to move renamed files into."
                        }
                    }
                }

                Item { Layout.fillWidth: true }
            }

            // Preview Table Header
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 26
                radius: 4
                color: "#161D2B"
                border.color: "#222C3E"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 8
                    Text { text: "Original Name"; font.pixelSize: 10; font.weight: 700; color: "#94A3B8"; Layout.fillWidth: true }
                    Text { text: "➔"; font.pixelSize: 10; color: "#64748B"; Layout.preferredWidth: 20; horizontalAlignment: Text.AlignHCenter }
                    Text { text: "New Name"; font.pixelSize: 10; font.weight: 700; color: "#94A3B8"; Layout.fillWidth: true }
                    Text { text: "Status"; font.pixelSize: 10; font.weight: 700; color: "#94A3B8"; Layout.preferredWidth: 70; horizontalAlignment: Text.AlignRight }
                }
            }

            // Preview Table List
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 6
                color: "#0A0D15"
                border.color: "#1E273A"
                border.width: 1
                clip: true

                ListView {
                    id: previewListView
                    anchors.fill: parent
                    anchors.margins: 4
                    spacing: 2
                    model: root.previewPlan
                    clip: true

                    delegate: Rectangle {
                        width: previewListView.width
                        height: 28
                        radius: 4
                        color: index % 2 === 0 ? "#111623" : "#0D111C"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 8

                            Text {
                                text: modelData.old_name
                                font.family: "Segoe UI, monospace"
                                font.pixelSize: 10
                                color: "#CBD5E1"
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }

                            Text {
                                text: "➔"
                                font.pixelSize: 10
                                color: "#64748B"
                                Layout.preferredWidth: 20
                                horizontalAlignment: Text.AlignHCenter
                            }

                            Text {
                                text: modelData.new_name
                                font.family: "Segoe UI, monospace"
                                font.pixelSize: 10
                                font.weight: 600
                                color: modelData.status === "ready" ? "#38BDF8" : (modelData.status === "collision" ? "#EF4444" : "#94A3B8")
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }

                            // Move badge
                            Rectangle {
                                visible: modelData.is_move === true
                                implicitHeight: 18
                                implicitWidth: moveBadgeTxt.implicitWidth + 8
                                radius: 4
                                color: "#064E3B"
                                border.color: "#10B981"
                                border.width: 1
                                Layout.preferredWidth: implicitWidth

                                Text {
                                    id: moveBadgeTxt
                                    anchors.centerIn: parent
                                    text: "MOVE"
                                    font.pixelSize: 8
                                    font.weight: 700
                                    color: "#6EE7B7"
                                }
                            }

                            Rectangle {
                                implicitHeight: 18
                                implicitWidth: statusTxt.implicitWidth + 10
                                radius: 4
                                color: modelData.status === "ready" ? "#064E3B" : (modelData.status === "collision" ? "#450A0A" : "#1E273A")
                                border.color: modelData.status === "ready" ? "#10B981" : (modelData.status === "collision" ? "#EF4444" : "#475569")
                                border.width: 1
                                Layout.preferredWidth: implicitWidth

                                Text {
                                    id: statusTxt
                                    anchors.centerIn: parent
                                    text: modelData.status === "ready" ? "READY" : (modelData.status === "collision" ? "COLLISION" : "UNCHANGED")
                                    font.pixelSize: 8
                                    font.weight: 700
                                    color: modelData.status === "ready" ? "#34D399" : (modelData.status === "collision" ? "#F87171" : "#94A3B8")
                                }
                            }
                        }

                        // ToolTip on hover for row
                        ToolTip.visible: itemMouse.containsMouse
                        ToolTip.delay: 350
                        ToolTip.text: {
                            var tip = "Original: " + modelData.old_path + "\n➔ Target: " + modelData.new_path
                            if (modelData.error) {
                                tip += "\n⚠️ " + modelData.error
                            } else if (modelData.is_move) {
                                tip += "\n📦 Move to destination folder"
                            } else if (modelData.status === "ready") {
                                tip += "\n✅ Ready to rename"
                            } else if (modelData.status === "unchanged") {
                                tip += "\nℹ️ Filename is unchanged"
                            }
                            return tip
                        }

                        MouseArea {
                            id: itemMouse
                            anchors.fill: parent
                            hoverEnabled: true
                        }
                    }
                }
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
