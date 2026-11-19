import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "visual_sorter"

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
            VisualSorterModelsDrawer {
                modal: root
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
                    color: promptInput.activeFocus ? "#0B0D12" : "#111622"
                    border.color: promptInput.activeFocus ? "#A78BFA" : (promptBoxMouse.containsMouse ? "#475569" : "#26324B")
                    border.width: promptInput.activeFocus ? 1.5 : 1

                    TextBarContextArea {
                        id: promptBoxMouse
                        target: promptInput
                        focusOnLeftClick: true
                    }

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
                            Layout.fillHeight: true
                            verticalAlignment: TextInput.AlignVCenter
                            text: root.vsBridge ? root.vsBridge.customPrompt : "Photos & Cosplay, 2D Illustrations, Dark & Moody, Video Clips, Favorites"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#F8FAFC"
                            selectionColor: "#0284C7"
                            selectedTextColor: "#FFFFFF"
                            selectByMouse: true
                            clip: true
                            TextBarContextArea {}
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
                VisualSorterBucketsPane {
                    modal: root
                }

                // ── Right Pane: Virtual Preview Items Grid + Reassignment Bar ────
                VisualSorterPreviewPane {
                    modal: root
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
