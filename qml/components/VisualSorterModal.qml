import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Visual + LLM Sorter Modal (Virtual-First -> Commit to Disk) ────────────
// Stage 1: Computes virtual sort buckets in memory with zero disk changes.
//          Users can inspect items, rename buckets, exclude items, or move items between buckets,
//          or filter the main Gallery view virtually by any bucket.
// Stage 2: Commits the virtual sort plan to disk, updates ArchiveManager & gallery_marks,
//          and registers a single batch Ctrl+Z Undo transaction.
Item {
    id: root

    property var bridge: null
    property var vsBridge: (typeof visualSorterBridge !== "undefined" && visualSorterBridge) ? visualSorterBridge : null
    property bool isOpen: false
    property string folderPath: ""

    signal sortCommitted(int movedCount, string message)
    signal virtualFilterRequested(string bucketName, var filePaths)

    property bool showModelsDrawer: false
    property string renamingBucketId: ""
    property string renameBuffer: ""
    property var selectedItemKeys: ({})
    property int selectedItemCount: 0
    property string customTargetBucket: ""

    anchors.fill: parent
    z: 9998

    opacity: isOpen ? 1.0 : 0.0
    visible: opacity > 0.005
    enabled: isOpen

    Behavior on opacity {
        NumberAnimation { duration: 190; easing.type: Easing.OutCubic }
    }

    function open(targetFolder) {
        root.folderPath = targetFolder || ""
        root.selectedItemKeys = ({})
        root.selectedItemCount = 0
        root.renamingBucketId = ""
        if (root.vsBridge) {
            root.vsBridge.setFolderPath(root.folderPath)
            root.vsBridge.refreshModelsStatus()
        }
        root.isOpen = true
    }

    function close() {
        root.isOpen = false
    }

    function toggleSelectItem(itemKey) {
        var copy = Object.assign({}, root.selectedItemKeys)
        if (copy[itemKey]) {
            delete copy[itemKey]
        } else {
            copy[itemKey] = true
        }
        root.selectedItemKeys = copy
        root.selectedItemCount = Object.keys(copy).length
    }

    function clearSelectedItems() {
        root.selectedItemKeys = ({})
        root.selectedItemCount = 0
    }

    function assignSelectedToBucket(bucketName) {
        if (!root.vsBridge || !bucketName) return
        var keys = Object.keys(root.selectedItemKeys)
        if (keys.length === 0) return
        root.vsBridge.moveItemsToBucket(keys, bucketName)
        root.clearSelectedItems()
    }

    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "0 B"
        var k = 1024
        var sizes = ["B", "KB", "MB", "GB", "TB"]
        var i = Math.floor(Math.log(bytes) / Math.log(k))
        if (i < 0) i = 0
        if (i >= sizes.length) i = sizes.length - 1
        return (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1) + " " + sizes[i]
    }

    function thumbUrlForPath(p) {
        if (!p) return ""
        var norm = String(p).replace(/\\/g, "/")
        return "image://thumb/" + encodeURIComponent(norm)
    }

    Connections {
        target: root.vsBridge
        ignoreUnknownSignals: true

        function onCommitFinished(ok, msg, movedCount) {
            if (ok) {
                root.sortCommitted(movedCount, msg)
                root.close()
            }
        }

        function onVirtualFilterApplied(bucketName, paths) {
            root.virtualFilterRequested(bucketName, paths)
            root.close()
        }
    }

    // ── Backdrop Scrim ────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#060911"
        opacity: 0.84
        MouseArea {
            anchors.fill: parent
            onClicked: {
                if (!root.vsBridge || !root.vsBridge.isRunning) {
                    root.close()
                }
            }
        }
    }

    // ── Main Modal Card (Newtonian Fluid Weight-Based Entry) ──────────────────
    Rectangle {
        id: modalCard
        width: Math.min(parent.width - 48, 1220)
        height: Math.min(parent.height - 44, 830)
        anchors.centerIn: parent
        radius: 14
        color: "#0C1018"
        border.color: "#26324B"
        border.width: 1
        clip: true

        scale: root.isOpen ? 1.0 : 0.93
        Behavior on scale {
            SpringAnimation { spring: 4.5; damping: 0.36; mass: 1.35 }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: {} // Prevent click-through to backdrop
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // ====================================================================
            // 1. HEADER BAR
            // ====================================================================
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    width: 40
                    height: 40
                    radius: 10
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#4F46E5" }
                        GradientStop { position: 1.0; color: "#7C3AED" }
                    }
                    border.color: "#A78BFA"
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "✨"
                        font.pixelSize: 18
                    }
                }

                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true

                    RowLayout {
                        spacing: 8
                        Text {
                            text: "Visual & Local AI Gallery Sorter"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 16
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                        }
                        Rectangle {
                            height: 20
                            implicitWidth: stageBadge.implicitWidth + 12
                            radius: 5
                            color: (root.vsBridge && root.vsBridge.hasVirtualPlan) ? "#064E3B" : "#1E1B4B"
                            border.color: (root.vsBridge && root.vsBridge.hasVirtualPlan) ? "#10B981" : "#818CF8"
                            border.width: 1
                            Text {
                                id: stageBadge
                                anchors.centerIn: parent
                                text: (root.vsBridge && root.vsBridge.hasVirtualPlan)
                                      ? "STAGE 1 READY — VIRTUAL PREVIEW (NO DISK CHANGES)"
                                      : "VIRTUAL-FIRST SANDBOX"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.weight: Font.Bold
                                color: (root.vsBridge && root.vsBridge.hasVirtualPlan) ? "#6EE7B7" : "#C7D2FE"
                            }
                        }
                    }

                    Text {
                        text: root.folderPath ? ("Target Folder: " + root.folderPath) : "Select a folder in Gallery to sort"
                        font.family: "Consolas, monospace"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                }

                // Hardware Acceleration & Optional AI Models Drawer Toggle
                Rectangle {
                    Layout.preferredHeight: 34
                    implicitWidth: hwRow.implicitWidth + 18
                    radius: 8
                    color: root.showModelsDrawer ? "#1E1B4B" : (hwMouse.containsMouse ? "#1E293B" : "#131926")
                    border.color: root.showModelsDrawer ? "#818CF8" : "#26324B"
                    border.width: 1
                    Springy { hover: hwMouse.containsMouse; pressed: hwMouse.pressed }

                    Row {
                        id: hwRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🧠"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Local AI Models (" + (root.vsBridge ? root.vsBridge.hardwareSummary : "CPU/GPU") + ")"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#E2E8F0"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: root.showModelsDrawer ? "▲" : "▼"
                            font.pixelSize: 9
                            color: "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: hwMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.showModelsDrawer = !root.showModelsDrawer
                            if (root.showModelsDrawer && root.vsBridge) {
                                root.vsBridge.refreshModelsStatus()
                            }
                        }
                    }
                }

                // Close Button
                Rectangle {
                    width: 34
                    height: 34
                    radius: 8
                    color: closeMouse.containsMouse ? "#2A1215" : "#131926"
                    border.color: closeMouse.containsMouse ? "#F43F5E" : "#26324B"
                    border.width: 1
                    Springy { hover: closeMouse.containsMouse; pressed: closeMouse.pressed }
                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 13
                        font.bold: true
                        color: closeMouse.containsMouse ? "#FDA4AF" : "#94A3B8"
                    }
                    MouseArea {
                        id: closeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.close()
                    }
                }
            }

            // ====================================================================
            // 2. COLLAPSIBLE LOCAL AI MODELS & HARDWARE DRAWER
            // ====================================================================
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: root.showModelsDrawer ? 132 : 0
                visible: Layout.preferredHeight > 0.5
                clip: true
                radius: 10
                color: "#111622"
                border.color: "#312E81"
                border.width: 1

                Behavior on Layout.preferredHeight {
                    SpringAnimation { spring: 4.5; damping: 0.38; mass: 1.15 }
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "⚡ Universal Local AI Vision & LLM Packs (Optional — Heuristic Vision Engine works immediately without downloads)"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#C4B5FD"
                            Layout.fillWidth: true
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 8

                        Repeater {
                            model: root.vsBridge ? root.vsBridge.visualModelsStatus : []

                            delegate: Rectangle {
                                readonly property var mdl: modelData || ({})
                                readonly property bool isReady: !!mdl.is_ready
                                readonly property bool isDownloading: mdl.status === "downloading"

                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: 8
                                color: "#0D111A"
                                border.color: isReady ? "#10B981" : (isDownloading ? "#38BDF8" : "#1E293B")
                                border.width: 1

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 4

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text {
                                            text: mdl.name || mdl.key || ""
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: Font.Bold
                                            color: "#F8FAFC"
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                        Text {
                                            text: (mdl.size_mb || 0) + " MB"
                                            font.family: "Consolas, monospace"
                                            font.pixelSize: 10
                                            color: "#64748B"
                                        }
                                    }

                                    Text {
                                        text: mdl.description || ""
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: "#94A3B8"
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 6

                                        // Download progress bar when downloading
                                        Rectangle {
                                            visible: isDownloading
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 6
                                            radius: 3
                                            color: "#1E293B"
                                            Rectangle {
                                                height: parent.height
                                                radius: 3
                                                color: "#38BDF8"
                                                width: parent.width * Math.min(1.0, (mdl.percent || 0) / 100.0)
                                                Behavior on width {
                                                    SpringAnimation { spring: 4.5; damping: 0.40; mass: 0.8 }
                                                }
                                            }
                                        }

                                        Item { visible: !isDownloading; Layout.fillWidth: true }

                                        Rectangle {
                                            Layout.preferredHeight: 22
                                            implicitWidth: mdlBtnTxt.implicitWidth + 12
                                            radius: 5
                                            color: isReady ? "#064E3B" : (isDownloading ? "#7F1D1D" : "#1E3A8A")
                                            border.color: isReady ? "#10B981" : (isDownloading ? "#F87171" : "#38BDF8")
                                            border.width: 1
                                            Text {
                                                id: mdlBtnTxt
                                                anchors.centerIn: parent
                                                text: isReady ? "✔ Ready" : (isDownloading ? ("Cancel (" + Math.round(mdl.percent || 0) + "%)") : "⬇ Download")
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 10
                                                font.weight: Font.Bold
                                                color: "#FFFFFF"
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                enabled: !isReady
                                                cursorShape: isReady ? Qt.ArrowCursor : Qt.PointingHandCursor
                                                onClicked: {
                                                    if (!root.vsBridge) return
                                                    if (isDownloading) {
                                                        root.vsBridge.cancelVisualModelDownload(mdl.key)
                                                    } else {
                                                        root.vsBridge.downloadVisualModel(mdl.key)
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

            // ====================================================================
            // 3. STRATEGY SELECTOR CARDS + CONTROLS
            // ====================================================================
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Repeater {
                    model: root.vsBridge ? root.vsBridge.strategiesList : []

                    delegate: Rectangle {
                        readonly property var st: modelData || ({})
                        readonly property bool isSel: (root.vsBridge ? root.vsBridge.activeStrategy : "visual_style") === st.id

                        Layout.fillWidth: true
                        Layout.preferredHeight: 62
                        radius: 9
                        color: isSel ? "#172554" : (stMouse.containsMouse ? "#151C2B" : "#101520")
                        border.color: isSel ? "#38BDF8" : "#1E293B"
                        border.width: isSel ? 1.5 : 1
                        Springy { hover: stMouse.containsMouse; pressed: stMouse.pressed }

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 2

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 5
                                Text {
                                    text: st.icon || "✨"
                                    font.pixelSize: 13
                                }
                                Text {
                                    text: st.label || st.id
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: Font.Bold
                                    color: isSel ? "#F8FAFC" : "#CBD5E1"
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            Text {
                                text: st.desc || ""
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: isSel ? "#93C5FD" : "#64748B"
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        MouseArea {
                            id: stMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.vsBridge) root.vsBridge.setActiveStrategy(st.id)
                            }
                        }
                    }
                }
            }

            // Custom Prompt / Options + Run Virtual Sort Bar
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Custom Prompt Input (visible when activeStrategy === "custom_llm")
                Rectangle {
                    visible: (root.vsBridge ? root.vsBridge.activeStrategy : "") === "custom_llm"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    radius: 8
                    color: "#111622"
                    border.color: promptInput.activeFocus ? "#A78BFA" : "#26324B"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 8

                        Text {
                            text: "💬 Target Buckets / Prompt:"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#C4B5FD"
                        }

                        TextInput {
                            id: promptInput
                            Layout.fillWidth: true
                            text: root.vsBridge ? root.vsBridge.customPrompt : "Photos & Cosplay, 2D Illustrations, Dark & Moody, Video Clips, Favorites"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#F8FAFC"
                            selectByMouse: true
                            clip: true
                            onTextEdited: {
                                if (root.vsBridge) root.vsBridge.setCustomPrompt(text)
                            }
                        }
                    }
                }

                Item {
                    visible: (root.vsBridge ? root.vsBridge.activeStrategy : "") !== "custom_llm"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.vsBridge ? root.vsBridge.statusText : "Ready for Virtual Sort"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: (root.vsBridge && root.vsBridge.errorMessage) ? "#FDA4AF" : "#94A3B8"
                        width: parent.width
                        elide: Text.ElideRight
                    }
                }

                // Include Subfolders Toggle
                Rectangle {
                    Layout.preferredHeight: 38
                    implicitWidth: recRow.implicitWidth + 16
                    radius: 8
                    color: (root.vsBridge && root.vsBridge.recursive) ? "#1E293B" : "#111622"
                    border.color: (root.vsBridge && root.vsBridge.recursive) ? "#38BDF8" : "#26324B"
                    border.width: 1
                    Springy { hover: recMouse.containsMouse; pressed: recMouse.pressed }

                    Row {
                        id: recRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: (root.vsBridge && root.vsBridge.recursive) ? "☑" : "☐"
                            font.pixelSize: 13
                            color: "#38BDF8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: "Include Subfolders"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#E2E8F0"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: recMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.vsBridge) root.vsBridge.setRecursive(!root.vsBridge.recursive)
                        }
                    }
                }

                // Run / Cancel Virtual Sort Button
                Rectangle {
                    Layout.preferredHeight: 38
                    implicitWidth: runRow.implicitWidth + 24
                    radius: 8
                    color: (root.vsBridge && root.vsBridge.isRunning)
                           ? "#991B1B"
                           : (runMouse.containsMouse ? "#4F46E5" : "#4338CA")
                    border.color: (root.vsBridge && root.vsBridge.isRunning) ? "#F87171" : "#818CF8"
                    border.width: 1
                    Springy { hover: runMouse.containsMouse; pressed: runMouse.pressed }

                    Row {
                        id: runRow
                        anchors.centerIn: parent
                        spacing: 8
                        Text {
                            text: (root.vsBridge && root.vsBridge.isRunning) ? "⏹" : "✨"
                            font.pixelSize: 13
                            color: "#FFFFFF"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: (root.vsBridge && root.vsBridge.isRunning)
                                  ? "Stop Scan"
                                  : "Run Virtual Sort (Preview Only)"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: runMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (!root.vsBridge) return
                            if (root.vsBridge.isRunning) {
                                root.vsBridge.cancelVirtualSort()
                            } else {
                                root.clearSelectedItems()
                                root.vsBridge.startVirtualSort(
                                    root.folderPath,
                                    root.vsBridge.activeStrategy,
                                    promptInput.text,
                                    root.vsBridge.recursive
                                )
                            }
                        }
                    }
                }
            }

            // ====================================================================
            // 4. NEWTONIAN WEIGHTED PROGRESS BAR (VISIBLE DURING SCAN)
            // ====================================================================
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: (root.vsBridge && root.vsBridge.isRunning) ? 44 : 0
                visible: Layout.preferredHeight > 0.5
                clip: true
                radius: 8
                color: "#111827"
                border.color: "#38BDF8"
                border.width: 1

                Behavior on Layout.preferredHeight {
                    SpringAnimation { spring: 4.5; damping: 0.38; mass: 1.0 }
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 4

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: root.vsBridge ? root.vsBridge.statusText : ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#E2E8F0"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Text {
                            text: root.vsBridge
                                  ? (root.vsBridge.progressSpeed + " • ETA " + root.vsBridge.progressEta + " (" + root.vsBridge.progressPercent + "%)")
                                  : ""
                            font.family: "Consolas, monospace"
                            font.pixelSize: 11
                            color: "#38BDF8"
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 7
                        radius: 3.5
                        color: "#1E293B"
                        Rectangle {
                            height: parent.height
                            radius: 3.5
                            color: "#38BDF8"
                            width: parent.width * Math.min(1.0, (root.vsBridge ? root.vsBridge.progressPercent : 0) / 100.0)
                            Behavior on width {
                                SpringAnimation { spring: 4.4; damping: 0.40; mass: 0.85 }
                            }
                        }
                    }
                }
            }

            // ====================================================================
            // 5. TWO-PANE VIRTUAL SANDBOX (BUCKETS SIDEBAR + ITEMS PREVIEW GRID)
            // ====================================================================
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                // ── Left Pane: Virtual Buckets List ──────────────────────────────
                Rectangle {
                    Layout.preferredWidth: 310
                    Layout.fillHeight: true
                    radius: 10
                    color: "#101520"
                    border.color: "#1E293B"
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: "📂 Virtual Buckets (" + (root.vsBridge ? root.vsBridge.totalBucketsCount : 0) + ")"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                color: "#F8FAFC"
                                Layout.fillWidth: true
                            }
                            Rectangle {
                                visible: !!(root.vsBridge && root.vsBridge.hasVirtualPlan)
                                height: 22
                                implicitWidth: allBktTxt.implicitWidth + 12
                                radius: 5
                                color: (root.vsBridge && root.vsBridge.selectedBucketId === "all") ? "#1E3A8A" : "#151C2B"
                                border.color: (root.vsBridge && root.vsBridge.selectedBucketId === "all") ? "#38BDF8" : "#26324B"
                                border.width: 1
                                Text {
                                    id: allBktTxt
                                    anchors.centerIn: parent
                                    text: "Show All (" + (root.vsBridge ? root.vsBridge.totalPlannedFiles : 0) + ")"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: Font.Bold
                                    color: "#E2E8F0"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: if (root.vsBridge) root.vsBridge.selectBucket("all")
                                }
                            }
                        }

                        ListView {
                            id: bucketsListView
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: 6
                            model: root.vsBridge ? root.vsBridge.bucketsModel : null

                            delegate: Rectangle {
                                readonly property var bkt: modelData || ({})
                                readonly property string bktId: bkt.key || ""
                                readonly property bool isSel: (root.vsBridge ? root.vsBridge.selectedBucketId : "all") === bktId
                                readonly property bool isRenaming: root.renamingBucketId === bktId

                                width: bucketsListView.width
                                height: isRenaming ? 86 : 62
                                radius: 8
                                color: isSel ? "#172554" : (bktMouse.containsMouse ? "#161E2E" : "#0D111A")
                                border.color: isSel ? "#38BDF8" : "#1E293B"
                                border.width: isSel ? 1.5 : 1

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 4

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8

                                        // Cover Thumbnail
                                        Rectangle {
                                            width: 42
                                            height: 42
                                            radius: 6
                                            color: "#1E293B"
                                            clip: true
                                            Image {
                                                anchors.fill: parent
                                                source: root.thumbUrlForPath(bkt.cover_path || "")
                                                fillMode: Image.PreserveAspectCrop
                                                asynchronous: true
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 2

                                            Text {
                                                text: bkt.bucket_name || bktId
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 12
                                                font.weight: Font.Bold
                                                color: "#F8FAFC"
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }

                                            Text {
                                                text: (bkt.count || 0) + " files • " + root.formatBytes(bkt.total_bytes || 0)
                                                      + ((bkt.excluded_count || 0) > 0 ? (" (" + bkt.excluded_count + " skipped)") : "")
                                                font.family: "Consolas, monospace"
                                                font.pixelSize: 10
                                                color: "#94A3B8"
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }
                                        }

                                        // Rename Bucket Button
                                        Rectangle {
                                            width: 24
                                            height: 24
                                            radius: 5
                                            color: "#151C2B"
                                            border.color: "#26324B"
                                            border.width: 1
                                            z: 2
                                            Text {
                                                anchors.centerIn: parent
                                                text: "✎"
                                                font.pixelSize: 11
                                                color: "#94A3B8"
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    if (isRenaming) {
                                                        root.renamingBucketId = ""
                                                    } else {
                                                        root.renamingBucketId = bktId
                                                        root.renameBuffer = bkt.bucket_name || ""
                                                    }
                                                }
                                            }
                                        }

                                        // Filter in Gallery Button
                                        Rectangle {
                                            width: 24
                                            height: 24
                                            radius: 5
                                            color: "#151C2B"
                                            border.color: "#38BDF8"
                                            border.width: 1
                                            z: 2
                                            Text {
                                                anchors.centerIn: parent
                                                text: "🔍"
                                                font.pixelSize: 10
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    if (root.vsBridge) root.vsBridge.applyBucketAsGalleryFilter(bktId)
                                                }
                                            }
                                        }
                                    }

                                    // Inline Rename Row
                                    RowLayout {
                                        visible: isRenaming
                                        Layout.fillWidth: true
                                        spacing: 4
                                        z: 3

                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 24
                                            radius: 4
                                            color: "#090D14"
                                            border.color: "#38BDF8"
                                            border.width: 1
                                            TextInput {
                                                id: renInput
                                                anchors.fill: parent
                                                anchors.leftMargin: 6
                                                anchors.rightMargin: 6
                                                verticalAlignment: TextInput.AlignVCenter
                                                text: root.renameBuffer
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 11
                                                color: "#F8FAFC"
                                                selectByMouse: true
                                                onAccepted: {
                                                    if (root.vsBridge && text.trim().length > 0) {
                                                        root.vsBridge.renameBucket(bktId, text.trim())
                                                    }
                                                    root.renamingBucketId = ""
                                                }
                                            }
                                        }

                                        Rectangle {
                                            Layout.preferredHeight: 24
                                            implicitWidth: 44
                                            radius: 4
                                            color: "#059669"
                                            Text {
                                                anchors.centerIn: parent
                                                text: "Save"
                                                font.pixelSize: 10
                                                font.bold: true
                                                color: "#FFFFFF"
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    if (root.vsBridge && renInput.text.trim().length > 0) {
                                                        root.vsBridge.renameBucket(bktId, renInput.text.trim())
                                                    }
                                                    root.renamingBucketId = ""
                                                }
                                            }
                                        }
                                    }
                                }

                                MouseArea {
                                    id: bktMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    z: 1
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (root.vsBridge) root.vsBridge.selectBucket(bktId)
                                    }
                                }
                            }
                        }
                    }
                }

                // ── Right Pane: Virtual Preview Items Grid + Reassignment Bar ────
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 10
                    color: "#101520"
                    border.color: "#1E293B"
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8

                        // Reassign Selected Items Bar
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.selectedItemCount > 0 ? 40 : 0
                            visible: Layout.preferredHeight > 0.5
                            clip: true
                            radius: 7
                            color: "#1E1B4B"
                            border.color: "#818CF8"
                            border.width: 1

                            Behavior on Layout.preferredHeight {
                                SpringAnimation { spring: 4.6; damping: 0.38; mass: 1.0 }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 8

                                Text {
                                    text: root.selectedItemCount + " selected — Move to bucket:"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: Font.Bold
                                    color: "#E0E7FF"
                                }

                                Rectangle {
                                    Layout.preferredWidth: 190
                                    Layout.preferredHeight: 26
                                    radius: 5
                                    color: "#0D111A"
                                    border.color: "#6366F1"
                                    border.width: 1
                                    TextInput {
                                        id: targetBktInput
                                        anchors.fill: parent
                                        anchors.leftMargin: 6
                                        anchors.rightMargin: 6
                                        verticalAlignment: TextInput.AlignVCenter
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: "#F8FAFC"
                                        selectByMouse: true
                                        Text {
                                            anchors.fill: parent
                                            verticalAlignment: Text.AlignVCenter
                                            text: "Type new or existing folder…"
                                            font.pixelSize: 11
                                            color: "#64748B"
                                            visible: !targetBktInput.text
                                        }
                                        onAccepted: {
                                            if (text.trim().length > 0) {
                                                root.assignSelectedToBucket(text.trim())
                                                text = ""
                                            }
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.preferredHeight: 26
                                    implicitWidth: applyMoveTxt.implicitWidth + 14
                                    radius: 5
                                    color: "#4F46E5"
                                    Text {
                                        id: applyMoveTxt
                                        anchors.centerIn: parent
                                        text: "Assign"
                                        font.pixelSize: 11
                                        font.bold: true
                                        color: "#FFFFFF"
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (targetBktInput.text.trim().length > 0) {
                                                root.assignSelectedToBucket(targetBktInput.text.trim())
                                                targetBktInput.text = ""
                                            }
                                        }
                                    }
                                }

                                Item { Layout.fillWidth: true }

                                Rectangle {
                                    Layout.preferredHeight: 26
                                    implicitWidth: clrSelTxt.implicitWidth + 12
                                    radius: 5
                                    color: "#1E293B"
                                    Text {
                                        id: clrSelTxt
                                        anchors.centerIn: parent
                                        text: "Clear Selection"
                                        font.pixelSize: 11
                                        color: "#CBD5E1"
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.clearSelectedItems()
                                    }
                                }
                            }
                        }

                        // Virtual Preview GridView
                        SmoothGridView {
                            id: previewGrid
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            cellWidth: 196
                            cellHeight: 212
                            model: root.vsBridge ? root.vsBridge.previewItemsModel : null

                            delegate: Item {
                                width: previewGrid.cellWidth
                                height: previewGrid.cellHeight

                                readonly property var itm: modelData || ({})
                                readonly property string itmKey: itm.key || ""
                                readonly property bool isExcluded: !!itm.excluded
                                readonly property bool isChecked: !!root.selectedItemKeys[itmKey]

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: 5
                                    radius: 9
                                    color: isExcluded ? "#090C12" : (isChecked ? "#1E1B4B" : "#0D111A")
                                    border.color: isChecked ? "#818CF8" : (isExcluded ? "#334155" : "#1E293B")
                                    border.width: isChecked ? 1.5 : 1
                                    opacity: isExcluded ? 0.52 : 1.0

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 6
                                        spacing: 4

                                        // Thumbnail Box
                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 118
                                            radius: 6
                                            color: "#070A10"
                                            clip: true

                                            Image {
                                                anchors.fill: parent
                                                source: root.thumbUrlForPath(itm.file_path || "")
                                                fillMode: Image.PreserveAspectCrop
                                                asynchronous: true
                                            }

                                            // Confidence Badge (Top-Left)
                                            Rectangle {
                                                anchors.top: parent.top
                                                anchors.left: parent.left
                                                anchors.margins: 5
                                                height: 18
                                                implicitWidth: confTxt.implicitWidth + 10
                                                radius: 4
                                                color: "#CC0F172A"
                                                border.color: "#38BDF8"
                                                border.width: 1
                                                Text {
                                                    id: confTxt
                                                    anchors.centerIn: parent
                                                    text: (itm.confidence_pct || 85) + "%"
                                                    font.family: "Consolas, monospace"
                                                    font.pixelSize: 10
                                                    font.bold: true
                                                    color: "#38BDF8"
                                                }
                                            }

                                            // Exclude / Skip Toggle (Top-Right)
                                            Rectangle {
                                                anchors.top: parent.top
                                                anchors.right: parent.right
                                                anchors.margins: 5
                                                height: 20
                                                implicitWidth: exclTxt.implicitWidth + 10
                                                radius: 4
                                                color: isExcluded ? "#7F1D1D" : "#CC0F172A"
                                                border.color: isExcluded ? "#F87171" : "#475569"
                                                border.width: 1
                                                z: 2
                                                Text {
                                                    id: exclTxt
                                                    anchors.centerIn: parent
                                                    text: isExcluded ? "Skipped" : "✔ Keep"
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 10
                                                    font.bold: true
                                                    color: isExcluded ? "#FECACA" : "#E2E8F0"
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: {
                                                        if (root.vsBridge) root.vsBridge.toggleExcludeItem(itmKey)
                                                    }
                                                }
                                            }

                                            // Target Bucket Pill (Bottom)
                                            Rectangle {
                                                anchors.bottom: parent.bottom
                                                anchors.left: parent.left
                                                anchors.right: parent.right
                                                height: 20
                                                color: "#D90F172A"
                                                Text {
                                                    anchors.fill: parent
                                                    anchors.leftMargin: 6
                                                    anchors.rightMargin: 6
                                                    verticalAlignment: Text.AlignVCenter
                                                    text: "📂 " + (itm.bucket_name || "")
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 10
                                                    font.weight: Font.Bold
                                                    color: "#A78BFA"
                                                    elide: Text.ElideRight
                                                }
                                            }
                                        }

                                        // Filename
                                        Text {
                                            text: itm.filename || ""
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: Font.Bold
                                            color: "#F8FAFC"
                                            elide: Text.ElideMiddle
                                            Layout.fillWidth: true
                                        }

                                        // Reason / Dimensions
                                        Text {
                                            text: (itm.reason || "") + ((itm.width > 0 && itm.height > 0) ? (" • " + itm.width + "×" + itm.height) : "")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            color: "#94A3B8"
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        z: 1
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.toggleSelectItem(itmKey)
                                    }
                                }
                            }

                            // Empty State Overlay
                            Column {
                                anchors.centerIn: parent
                                spacing: 10
                                visible: previewGrid.count === 0 && (!root.vsBridge || !root.vsBridge.isRunning)

                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: "🎨"
                                    font.pixelSize: 38
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: "Virtual Sandbox Ready"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 15
                                    font.weight: Font.Bold
                                    color: "#E2E8F0"
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: "Pick a sorting strategy above and click 'Run Virtual Sort'.\nNothing is written or moved on disk until you review the buckets and click Commit."
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    color: "#64748B"
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }
                        }
                    }
                }
            }

            // ====================================================================
            // 6. BOTTOM ACTION & STAGE 2 COMMIT BAR
            // ====================================================================
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Reset Virtual Plan
                Rectangle {
                    visible: !!(root.vsBridge && root.vsBridge.hasVirtualPlan)
                    Layout.preferredHeight: 38
                    implicitWidth: rstTxt.implicitWidth + 20
                    radius: 8
                    color: rstMouse.containsMouse ? "#1E293B" : "#131926"
                    border.color: "#334155"
                    border.width: 1
                    Springy { hover: rstMouse.containsMouse; pressed: rstMouse.pressed }

                    Text {
                        id: rstTxt
                        anchors.centerIn: parent
                        text: "↺ Discard Virtual Plan"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: "#CBD5E1"
                    }
                    MouseArea {
                        id: rstMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.clearSelectedItems()
                            if (root.vsBridge) root.vsBridge.clearVirtualPlan()
                        }
                    }
                }

                // Filter Main Gallery Virtually by Current Bucket (Zero Disk Moves)
                Rectangle {
                    visible: !!(root.vsBridge && root.vsBridge.hasVirtualPlan)
                    Layout.preferredHeight: 38
                    implicitWidth: fltGalTxt.implicitWidth + 22
                    radius: 8
                    color: fltGalMouse.containsMouse ? "#1E3A8A" : "#172554"
                    border.color: "#38BDF8"
                    border.width: 1
                    Springy { hover: fltGalMouse.containsMouse; pressed: fltGalMouse.pressed }

                    Text {
                        id: fltGalTxt
                        anchors.centerIn: parent
                        text: "🔍 Filter Gallery View by Current Bucket (Keep Virtual)"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: "#E0F2FE"
                    }
                    MouseArea {
                        id: fltGalMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.vsBridge) {
                                root.vsBridge.applyBucketAsGalleryFilter(root.vsBridge.selectedBucketId)
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                Text {
                    visible: !!(root.vsBridge && root.vsBridge.hasVirtualPlan)
                    text: "Full Ctrl+Z Undo & Archive DB sync included"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                }

                // Stage 2: Commit Virtual Plan to Disk
                Rectangle {
                    id: commitBtnRect
                    readonly property bool canCommit: !!(root.vsBridge && root.vsBridge.hasVirtualPlan && root.vsBridge.totalPlannedFiles > 0 && !root.vsBridge.isRunning)
                    Layout.preferredHeight: 40
                    implicitWidth: commitRow.implicitWidth + 28
                    radius: 8
                    color: !canCommit ? "#1E293B" : (commitMouse.containsMouse ? "#059669" : "#047857")
                    border.color: !canCommit ? "#334155" : "#34D399"
                    border.width: 1
                    opacity: canCommit ? 1.0 : 0.55
                    Springy { hover: commitMouse.containsMouse && commitBtnRect.canCommit; pressed: commitMouse.pressed && commitBtnRect.canCommit }

                    Row {
                        id: commitRow
                        anchors.centerIn: parent
                        spacing: 8
                        Text {
                            text: "💾"
                            font.pixelSize: 13
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: "Commit Sort to Disk (" + (root.vsBridge ? root.vsBridge.totalPlannedFiles : 0) + " Files)"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: commitMouse
                        anchors.fill: parent
                        enabled: parent.canCommit
                        hoverEnabled: true
                        cursorShape: parent.canCommit ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: {
                            if (root.vsBridge) root.vsBridge.commitVirtualSort()
                        }
                    }
                }
            }
        }
    }
}
