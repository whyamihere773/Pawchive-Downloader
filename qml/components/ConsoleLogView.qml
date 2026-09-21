import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var logModel: null
    property bool autoScroll: true
    property string activeLevel: "ALL"
    property bool statusOnlyMode: false

    // Multi-row selection state
    property var selectedIndicesMap: ({})
    property int selectedCount: 0
    property int selectionAnchor: -1
    property int selectionLead: -1
    property int dragStartIndex: -1
    property bool isDragging: false

    // Context menu row info
    property int contextRowIndex: -1
    property string contextRowLevel: ""
    property string contextRowCategory: ""
    property string contextRowMessage: ""

    function openContextMenu(mouseX, mouseY, rowIndex, level, category, message) {
        contextRowIndex = (rowIndex !== undefined ? rowIndex : -1)
        contextRowLevel = (level || "")
        contextRowCategory = (category || "")
        contextRowMessage = (message || "")

        var menuW = 252
        var menuH = 290
        var clampedX = Math.max(8, Math.min(root.width - menuW - 8, mouseX))
        var clampedY = Math.max(8, Math.min(root.height - menuH - 8, mouseY))
        logContextMenu.x = clampedX
        logContextMenu.y = clampedY
        logContextMenu.open()
    }

    function isRowSelected(index) {
        return !!selectedIndicesMap[index]
    }

    function selectSingleRow(index) {
        var m = {}
        m[index] = true
        selectedIndicesMap = m
        selectedCount = 1
        selectionAnchor = index
        selectionLead = index
    }

    function toggleRow(index) {
        var m = Object.assign({}, selectedIndicesMap)
        if (m[index]) {
            delete m[index]
        } else {
            m[index] = true
        }
        selectedIndicesMap = m
        selectedCount = Object.keys(m).length
        selectionAnchor = index
        selectionLead = index
    }

    function selectRange(fromIdx, toIdx) {
        var m = {}
        var start = Math.max(0, Math.min(fromIdx, toIdx))
        var end = Math.min(logList.count - 1, Math.max(fromIdx, toIdx))
        for (var i = start; i <= end; i++) {
            m[i] = true
        }
        selectedIndicesMap = m
        selectedCount = Object.keys(m).length
        selectionAnchor = fromIdx
        selectionLead = toIdx
    }

    function selectAllRows() {
        var m = {}
        for (var i = 0; i < logList.count; i++) {
            m[i] = true
        }
        selectedIndicesMap = m
        selectedCount = logList.count
        selectionAnchor = 0
        selectionLead = logList.count - 1
    }

    function clearSelection() {
        selectedIndicesMap = ({})
        selectedCount = 0
        selectionAnchor = -1
        selectionLead = -1
        dragStartIndex = -1
        isDragging = false
        if (autoScrollTimer.running) autoScrollTimer.stop()
    }

    function copySelectedLogs() {
        var indices = Object.keys(selectedIndicesMap).map(Number)
        var textToCopy = ""
        if (indices.length > 0 && root.logModel) {
            textToCopy = root.logModel.getSelectedText(indices)
        } else if (root.logModel) {
            textToCopy = root.logModel.getAllText()
        }
        if (textToCopy) {
            if (typeof appBridge !== "undefined" && appBridge && appBridge.copyToClipboard) {
                appBridge.copyToClipboard(textToCopy)
            }
            clipHelper.text = textToCopy
            clipHelper.selectAll()
            clipHelper.copy()
            root.showToast(indices.length > 0 ? root.tr("toast_copied_rows", "Copied %1 row(s) to clipboard!").replace("%1", indices.length) : root.tr("toast_copied_all", "Copied all logs to clipboard!"))
        }
    }

    function tr(key, fallback) {
        if (typeof Lang === "undefined" || !Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    signal exportLogsRequested()
    signal clearLogsRequested()
    signal exportLinksRequested()
    signal downloadLinksRequested()

    readonly property bool isCompact: root.width < 660
    readonly property bool isVeryNarrow: root.width < 420

    color: "#0D0F14"

    border.color: "#242A38"
    border.width: 1
    radius: 10
    clip: true

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // Header toolbar
        RowLayout {
            Layout.fillWidth: true
            spacing: root.isVeryNarrow ? 4 : (root.isCompact ? 6 : 8)

            // Title & Icon
            Row {
                spacing: root.isVeryNarrow ? 0 : 6
                Layout.alignment: Qt.AlignVCenter
                Text {
                    text: "💻"
                    font.pixelSize: 13
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: root.tr("title_progress_log", "Progress Log")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 12
                    font.weight: 600
                    color: "#F1F5F9"
                    visible: !root.isVeryNarrow
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            Item { Layout.fillWidth: true }

            // Level filters (Highlights active level)
            Row {
                spacing: root.isVeryNarrow ? 2 : 4
                Layout.alignment: Qt.AlignVCenter
                Repeater {
                    model: ["ALL", "INFO", "WARN", "ERR"]
                    delegate: Rectangle {
                        id: filterPill
                        implicitHeight: 22
                        implicitWidth: root.isVeryNarrow ? 28 : Math.max(42, filterText.implicitWidth + 14)
                        width: implicitWidth
                        height: 22
                        radius: 4
                        property bool selected: root.activeLevel === modelData

                        color: selected ? "#38BDF8" : (mArea.containsMouse ? "#2A303F" : "#1A1E29")
                        border.color: selected ? "#38BDF8" : "#2E3547"
                        border.width: 1

                        Behavior on implicitWidth { NumberAnimation { duration: 120 } }
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Behavior on border.color { ColorAnimation { duration: 100 } }

                        Text {
                            id: filterText
                            anchors.centerIn: parent
                            text: root.isVeryNarrow && modelData === "INFO" ? "INF" : (root.isVeryNarrow && modelData === "WARN" ? "WRN" : modelData)
                            font.pixelSize: root.isVeryNarrow ? 8 : 9
                            font.weight: Font.Bold
                            color: selected ? "#0F172A" : "#94A3B8"
                        }

                        MouseArea {
                            id: mArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 400
                            ToolTip.text: modelData === "ALL" ? root.tr("tip_log_all", "Show all log messages") : (modelData === "INFO" ? root.tr("tip_log_info", "Filter by Info level") : (modelData === "WARN" ? root.tr("tip_log_warn", "Filter by Warnings") : root.tr("tip_log_err", "Filter by Errors")))
                            onClicked: {
                                root.activeLevel = modelData
                                var lvl = modelData === "WARN" ? "WARNING" : (modelData === "ERR" ? "ERROR" : modelData)
                                if (root.logModel) root.logModel.setFilterLevel(lvl)
                            }
                        }
                    }
                }
            }

            // Download links button (Cloud Download)
            Rectangle {
                id: dlBtn
                implicitHeight: 24
                implicitWidth: root.isCompact ? 28 : Math.max(120, dlText.implicitWidth + 38)
                Layout.preferredHeight: 24
                Layout.preferredWidth: implicitWidth
                Layout.minimumWidth: implicitWidth
                radius: 5
                clip: true
                color: dlLinkMouse.containsMouse ? "#113832" : "#0A2521"
                border.color: "#2DD4BF"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Behavior on implicitWidth { NumberAnimation { duration: 120 } }

                Row {
                    anchors.centerIn: parent
                    spacing: 5
                    Text { text: "☁️"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        id: dlText
                        text: root.tr("btn_download_links", "Download Links")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 10
                        color: "#2DD4BF"
                        font.weight: 600
                        visible: !root.isCompact
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: dlLinkMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: root.tr("tip_download_links", "Open dialog to download harvested links via Mega.nz, Google Drive, Dropbox, or GoFile")
                    onClicked: root.downloadLinksRequested()
                }
            }

            // Export links button
            Rectangle {
                id: exBtn
                implicitHeight: 24
                implicitWidth: root.isCompact ? 28 : Math.max(106, exText.implicitWidth + 38)
                Layout.preferredHeight: 24
                Layout.preferredWidth: implicitWidth
                Layout.minimumWidth: implicitWidth
                radius: 5
                clip: true
                color: exLinkMouse.containsMouse ? "#1E2D2A" : "#13211E"
                border.color: "#10B981"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Behavior on implicitWidth { NumberAnimation { duration: 120 } }

                Row {
                    anchors.centerIn: parent
                    spacing: 5
                    Text { text: "🔗"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        id: exText
                        text: root.tr("btn_export_links", "Export Links")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 10
                        color: "#34D399"
                        font.weight: Font.Medium
                        visible: !root.isCompact
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: exLinkMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: root.tr("tip_export_links", "Extract and export all external cloud links to a text file")
                    onClicked: root.exportLinksRequested()
                }
            }

            // Eye Button: Status / Summary mode toggle (Filters out individual file names)
            Rectangle {
                implicitHeight: 24
                implicitWidth: 28
                Layout.preferredHeight: 24
                Layout.preferredWidth: 28
                Layout.minimumWidth: 28
                radius: 5
                color: root.statusOnlyMode ? "#1E2A3A" : (eyeMouse.containsMouse ? "#222734" : "#1A1E29")
                border.color: root.statusOnlyMode ? "#38BDF8" : "#2E3547"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Behavior on color { ColorAnimation { duration: 100 } }
                Behavior on border.color { ColorAnimation { duration: 100 } }

                Text {
                    anchors.centerIn: parent
                    text: root.statusOnlyMode ? "🙈" : "👁"
                    font.pixelSize: 12
                    color: root.statusOnlyMode ? "#38BDF8" : "#64748B"
                }

                MouseArea {
                    id: eyeMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: root.statusOnlyMode ? root.tr("tip_status_only_active", "Status-Only mode active (click to show all file details)") : root.tr("tip_status_only", "Click to hide individual file names and show status only")
                    onClicked: {
                        root.statusOnlyMode = !root.statusOnlyMode
                        if (root.logModel) root.logModel.setStatusOnly(root.statusOnlyMode)
                    }
                }
            }

            // Copy Logs button (Copies selected rows, or all visible logs if none selected)
            Rectangle {
                id: copyBtn
                implicitHeight: 24
                implicitWidth: root.isCompact ? 28 : (root.selectedCount > 0 ? Math.max(90, copyText.implicitWidth + 36) : Math.max(80, copyText.implicitWidth + 36))
                Layout.preferredHeight: 24
                Layout.preferredWidth: implicitWidth
                Layout.minimumWidth: implicitWidth
                radius: 5
                clip: true
                color: copyMouse.containsMouse ? "#1E3A5F" : (root.selectedCount > 0 ? "#172A45" : "#131C2E")
                border.color: root.selectedCount > 0 ? "#38BDF8" : "#2563EB"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Behavior on implicitWidth { NumberAnimation { duration: 120 } }
                Behavior on color { ColorAnimation { duration: 100 } }
                Behavior on border.color { ColorAnimation { duration: 100 } }

                Row {
                    anchors.centerIn: parent
                    spacing: 4
                    Text { text: "📋"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        id: copyText
                        text: root.selectedCount > 0 ? root.tr("btn_copy_selected", "Copy (%1)").replace("%1", root.selectedCount) : root.tr("btn_copy_all", "Copy All")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 10
                        color: "#38BDF8"
                        font.weight: 600
                        visible: !root.isCompact
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: copyMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: root.selectedCount > 0 ? root.tr("tip_copy_selected", "Copy %1 selected log row(s) to clipboard (Ctrl+C)").replace("%1", root.selectedCount) : root.tr("tip_copy_all", "Copy all visible console logs to clipboard (Ctrl+C)")
                    onClicked: root.copySelectedLogs()
                }
            }

            // Reset/Clear button
            Rectangle {
                id: resetBtn
                implicitHeight: 24
                implicitWidth: root.isCompact ? 28 : Math.max(70, resetText.implicitWidth + 32)
                Layout.preferredHeight: 24
                Layout.preferredWidth: implicitWidth
                Layout.minimumWidth: implicitWidth
                radius: 5
                clip: true
                color: resetMouse.containsMouse ? "#2C1D24" : "#1F161C"
                border.color: "#EF4444"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Behavior on implicitWidth { NumberAnimation { duration: 120 } }

                Row {
                    anchors.centerIn: parent
                    spacing: 4
                    Text { text: "↻"; font.pixelSize: 11; color: "#F87171"; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        id: resetText
                        text: root.tr("btn_reset", "Reset")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 10
                        color: "#F87171"
                        font.weight: Font.Medium
                        visible: !root.isCompact
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: resetMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: root.tr("tip_reset_logs", "Clear all progress console logs")
                    onClicked: {
                        root.clearSelection()
                        root.clearLogsRequested()
                    }
                }
            }
        }

        // Search bar
        Rectangle {
            Layout.fillWidth: true
            height: 26
            radius: 5
            color: "#13161E"
            border.color: searchInput.activeFocus ? "#38BDF8" : "#242A38"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                Text { text: "🔍"; font.pixelSize: 10; color: "#64748B" }

                TextInput {
                    id: searchInput
                    Layout.fillWidth: true
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#F1F5F9"
                    clip: true
                    selectByMouse: true

                    Text {
                        anchors.fill: parent
                        text: root.tr("placeholder_search_logs", "Filter console output...")
                        color: "#475569"
                        font.pixelSize: 11
                        visible: !searchInput.text && !searchInput.activeFocus
                    }


                    onTextChanged: {
                        root.clearSelection()
                        if (root.logModel) root.logModel.setSearchQuery(text)
                    }
                }
            }
        }

        // Log Console ListView
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#08090C"
            radius: 6
            border.color: "#1E2330"
            border.width: 1
            clip: true

            Timer {
                id: autoScrollTimer
                interval: 35
                repeat: true
                running: false
                property int step: 0

                onTriggered: {
                    if (!root.isDragging || root.dragStartIndex < 0) {
                        stop()
                        return
                    }
                    var nextY = logList.contentY + step
                    if (nextY < 0) nextY = 0
                    var maxY = Math.max(0, logList.contentHeight - logList.height)
                    if (nextY > maxY) nextY = maxY
                    logList.contentY = nextY

                    var checkY = step > 0 ? (logList.contentY + logList.height - 8) : (logList.contentY + 8)
                    var edgeIdx = logList.indexAt(logList.width / 2, checkY)
                    if (edgeIdx >= 0 && root.dragStartIndex >= 0) {
                        root.selectRange(root.dragStartIndex, edgeIdx)
                    }
                }
            }

            // Click empty area to clear selection or open context menu
            MouseArea {
                anchors.fill: parent
                z: 0
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onPressed: (mouse) => {
                    logList.forceActiveFocus()
                    if (mouse.button === Qt.RightButton) {
                        var menuPt = mapToItem(root, mouse.x, mouse.y)
                        root.openContextMenu(menuPt.x, menuPt.y, -1, "", "", "")
                    } else {
                        root.clearSelection()
                    }
                }
            }

            ListView {
                id: logList
                z: 1
                anchors.fill: parent
                anchors.margins: 6
                model: root.logModel
                spacing: 3
                boundsBehavior: Flickable.StopAtBounds
                focus: true

                Keys.onPressed: (event) => {
                    if (event.matches(StandardKey.Copy) || (event.key === Qt.Key_C && (event.modifiers & Qt.ControlModifier))) {
                        root.copySelectedLogs()
                        event.accepted = true
                    } else if (event.matches(StandardKey.SelectAll) || (event.key === Qt.Key_A && (event.modifiers & Qt.ControlModifier))) {
                        root.selectAllRows()
                        event.accepted = true
                    } else if (event.key === Qt.Key_Escape) {
                        root.clearSelection()
                        event.accepted = true
                    } else if (event.key === Qt.Key_Down) {
                        var curr = root.selectionLead >= 0 ? root.selectionLead : (root.selectionAnchor >= 0 ? root.selectionAnchor : -1)
                        var next = Math.min(logList.count - 1, curr + 1)
                        if (next >= 0) {
                            if (event.modifiers & Qt.ShiftModifier) {
                                root.selectRange(root.selectionAnchor >= 0 ? root.selectionAnchor : 0, next)
                            } else {
                                root.selectSingleRow(next)
                            }
                            logList.positionViewAtIndex(next, ListView.Contain)
                        }
                        event.accepted = true
                    } else if (event.key === Qt.Key_Up) {
                        var curr = root.selectionLead >= 0 ? root.selectionLead : (root.selectionAnchor >= 0 ? root.selectionAnchor : logList.count)
                        var prev = Math.max(0, curr - 1)
                        if (prev >= 0 && prev < logList.count) {
                            if (event.modifiers & Qt.ShiftModifier) {
                                root.selectRange(root.selectionAnchor >= 0 ? root.selectionAnchor : logList.count - 1, prev)
                            } else {
                                root.selectSingleRow(prev)
                            }
                            logList.positionViewAtIndex(prev, ListView.Contain)
                        }
                        event.accepted = true
                    }
                }

                property bool programmaticScroll: false

                ScrollBar.vertical: ScrollBar {
                    id: logScrollBar
                    active: true
                    policy: ScrollBar.AsNeeded
                    onPositionChanged: {
                        if (pressed) {
                            // User is actively dragging the scrollbar thumb
                            root.autoScroll = (position + size >= 0.98)
                        }
                    }
                }

                onMovingChanged: {
                    if (!moving && !programmaticScroll) {
                        root.autoScroll = atYEnd
                    }
                }

                onContentYChanged: {
                    if (!programmaticScroll) {
                        root.autoScroll = atYEnd
                    }
                }

                delegate: Item {
                    id: rowItem
                    width: logList.width - 12
                    implicitHeight: rowLayout.implicitHeight + 4
                    height: implicitHeight

                    readonly property bool isSelected: root.isRowSelected(index)

                    Rectangle {
                        anchors.fill: parent
                        radius: 4
                        color: rowItem.isSelected ? "#1D3A5F" : (rowHoverMouse.containsMouse ? "#131722" : "transparent")
                        border.color: rowItem.isSelected ? "#38BDF8" : "transparent"
                        border.width: 1

                        // Accent line on left edge of selected row
                        Rectangle {
                            width: 3
                            height: parent.height - 4
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            color: "#38BDF8"
                            radius: 1.5
                            visible: rowItem.isSelected
                        }
                    }

                    RowLayout {
                        id: rowLayout
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: 6
                        anchors.rightMargin: 6
                        spacing: 6

                        // Timestamp
                        Text {
                            text: model.timestamp
                            font.family: "Cascadia Code, Consolas, monospace"
                            font.pixelSize: 10
                            color: rowItem.isSelected ? "#94A3B8" : "#64748B"
                        }

                        // Level Badge (Vibrant colored icon with matching tinted border)
                        Rectangle {
                            width: 18
                            height: 18
                            radius: 4
                            color: Qt.rgba(0.12, 0.16, 0.22, 0.9)
                            border.color: model.levelColor
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                text: model.icon
                                font.pixelSize: 9
                                font.bold: true
                                color: model.levelColor
                            }
                        }

                        // Message — URLs are rendered as clickable links
                        Text {
                            id: msgText
                            Layout.fillWidth: true
                            text: {
                                var _ = (typeof Lang !== "undefined" && Lang) ? Lang.activeLanguage : ""
                                var raw = (typeof Lang !== "undefined" && Lang) ? Lang.translateLog(model.message, model.level || "") : model.message
                                var escaped = raw.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                                var linked = escaped.replace(/(https?:\/\/[^\s<>"']+?)([.,;:!?)]*(?=\s|$))/g, function(match, url, punct) {
                                    return '<a href="' + url + '" style="color:#38BDF8; text-decoration:underline;">' + url + '</a>' + punct;
                                })
                                return linked
                            }
                            font.family: "Cascadia Code, Consolas, monospace"
                            font.pixelSize: 11
                            color: rowItem.isSelected ? "#F1F5F9" : model.levelColor
                            wrapMode: Text.WrapAnywhere
                            textFormat: Text.RichText
                        }
                    }

                    MouseArea {
                        id: rowHoverMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.RightButton

                        cursorShape: {
                            var pt = mapToItem(msgText, mouseX, mouseY)
                            return (msgText.linkAt(pt.x, pt.y) ? Qt.PointingHandCursor : Qt.ArrowCursor)
                        }

                        onPressed: (mouse) => {
                            logList.forceActiveFocus()
                            if (mouse.button === Qt.RightButton) {
                                if (!rowItem.isSelected) {
                                    root.selectSingleRow(index)
                                }
                                var menuPt = mapToItem(root, mouse.x, mouse.y)
                                root.openContextMenu(menuPt.x, menuPt.y, index, model.level, model.category, model.message)
                                return
                            }

                            // Check if a link was clicked
                            var pt = mapToItem(msgText, mouse.x, mouse.y)
                            var link = msgText.linkAt(pt.x, pt.y)
                            if (link) {
                                Qt.openUrlExternally(link)
                                return
                            }

                            if (mouse.modifiers & Qt.ShiftModifier) {
                                root.selectRange(root.selectionAnchor >= 0 ? root.selectionAnchor : index, index)
                            } else if (mouse.modifiers & Qt.ControlModifier) {
                                root.toggleRow(index)
                            } else {
                                root.selectSingleRow(index)
                                root.dragStartIndex = index
                                root.isDragging = true
                            }
                        }

                        onPositionChanged: (mouse) => {
                            if (root.isDragging) {
                                if (mouse.buttons & Qt.LeftButton) {
                                    if (root.dragStartIndex >= 0) {
                                        root.selectRange(root.dragStartIndex, index)
                                    }
                                    // Auto-scroll near list boundaries
                                    var ptInList = mapToItem(logList, mouse.x, mouse.y)
                                    if (ptInList.y < 30) {
                                        autoScrollTimer.step = -18
                                        if (!autoScrollTimer.running) autoScrollTimer.start()
                                    } else if (ptInList.y > logList.height - 30) {
                                        autoScrollTimer.step = 18
                                        if (!autoScrollTimer.running) autoScrollTimer.start()
                                    } else {
                                        if (autoScrollTimer.running) autoScrollTimer.stop()
                                    }
                                } else {
                                    root.isDragging = false
                                    root.dragStartIndex = -1
                                    if (autoScrollTimer.running) autoScrollTimer.stop()
                                }
                            }
                        }

                        onReleased: (mouse) => {
                            if (mouse.button === Qt.LeftButton) {
                                root.isDragging = false
                                root.dragStartIndex = -1
                                if (autoScrollTimer.running) autoScrollTimer.stop()
                            }
                        }
                    }
                }

                onCountChanged: {
                    if (root.autoScroll) {
                        programmaticScroll = true
                        Qt.callLater(function() {
                            logList.positionViewAtEnd()
                            Qt.callLater(function() {
                                programmaticScroll = false
                            })
                        })
                    }
                }
            }

            // Floating "Jump to latest" button when user is scrolled up
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottomMargin: 10
                visible: !root.autoScroll && !logList.atYEnd
                height: 24
                width: jumpLatestRow.implicitWidth + 18
                radius: 12
                color: jumpMouse.containsMouse ? "#0284C7" : Qt.rgba(0.06, 0.10, 0.18, 0.95)
                border.color: "#38BDF8"
                border.width: 1
                z: 10

                Behavior on color { ColorAnimation { duration: 120 } }

                Row {
                    id: jumpLatestRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text {
                        text: "⬇"
                        font.pixelSize: 10
                        color: jumpMouse.containsMouse ? "#FFFFFF" : "#38BDF8"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: root.tr("btn_jump_to_latest", "Jump to latest")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: jumpMouse.containsMouse ? "#FFFFFF" : "#F1F5F9"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: jumpMouse
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: {
                        logList.programmaticScroll = true
                        root.autoScroll = true
                        logList.positionViewAtEnd()
                        Qt.callLater(function() {
                            logList.programmaticScroll = false
                        })
                    }
                }
            }
        }
    }

    // Redesigned Context Menu Popup for right-click on log rows
    Popup {
        id: logContextMenu
        width: 256
        padding: 6
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        transformOrigin: Popup.TopLeft

        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 120; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.94; to: 1.0; duration: 120; easing.type: Easing.OutCubic }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 90; easing.type: Easing.InCubic }
            NumberAnimation { property: "scale"; from: 1.0; to: 0.96; duration: 90; easing.type: Easing.InCubic }
        }

        background: Rectangle {
            color: "#0B0F19"
            border.color: "#232E42"
            border.width: 1.2
            radius: 9

            // Top accent indicator
            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 2
                radius: 1
                color: root.contextRowLevel === "ERROR" ? "#EF4444" : (root.contextRowLevel === "WARNING" ? "#F59E0B" : "#38BDF8")
                opacity: 0.7
            }
        }

        contentItem: ColumnLayout {
            spacing: 2

            // Component for modern context menu items
            component ContextMenuItem: Rectangle {
                id: cItem
                Layout.fillWidth: true
                height: 29
                radius: 5

                property string icon: ""
                property string label: ""
                property string shortcut: ""
                property bool danger: false
                property bool active: true
                signal clicked()

                opacity: active ? 1.0 : 0.45
                color: !active ? "transparent" : (cMouse.containsMouse ? (danger ? "#2E151E" : "#162236") : "transparent")
                border.color: !active ? "transparent" : (cMouse.containsMouse ? (danger ? "#7F1D1D" : "#253B5E") : "transparent")
                border.width: 1

                Behavior on color { ColorAnimation { duration: 80 } }
                Behavior on border.color { ColorAnimation { duration: 80 } }

                // Hover indicator bar on left
                Rectangle {
                    width: 3
                    height: 16
                    radius: 1.5
                    color: cItem.danger ? "#EF4444" : "#38BDF8"
                    anchors.left: parent.left
                    anchors.leftMargin: 2
                    anchors.verticalCenter: parent.verticalCenter
                    visible: cMouse.containsMouse && cItem.active
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 9
                    anchors.rightMargin: 8
                    spacing: 7

                    Text {
                        text: cItem.icon
                        font.pixelSize: 12
                        Layout.alignment: Qt.AlignVCenter
                    }

                    Text {
                        text: cItem.label
                        color: cItem.danger ? (cMouse.containsMouse ? "#FCA5A5" : "#F87171") : (cMouse.containsMouse ? "#FFFFFF" : "#E2E8F0")
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        font.family: "Segoe UI, Inter, sans-serif"
                        Layout.alignment: Qt.AlignVCenter
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    Rectangle {
                        visible: !!cItem.shortcut
                        height: 18
                        width: scTxt.implicitWidth + 10
                        radius: 4
                        color: cMouse.containsMouse ? "#1A2234" : "#121824"
                        border.color: cMouse.containsMouse ? "#2C3B56" : "#1F293D"
                        border.width: 1
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            id: scTxt
                            anchors.centerIn: parent
                            text: cItem.shortcut
                            color: cMouse.containsMouse ? "#38BDF8" : "#64748B"
                            font.pixelSize: 9
                            font.family: "Cascadia Code, Consolas, monospace"
                        }
                    }
                }

                MouseArea {
                    id: cMouse
                    anchors.fill: parent
                    hoverEnabled: cItem.active
                    cursorShape: cItem.active ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: {
                        if (cItem.active) {
                            logContextMenu.close()
                            cItem.clicked()
                        }
                    }
                }
            }

            // Header Banner with selection badge
            Rectangle {
                Layout.fillWidth: true
                height: 26
                color: "#111726"
                radius: 6
                border.color: "#1A2436"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8

                    Row {
                        spacing: 6
                        Layout.alignment: Qt.AlignVCenter
                        Text {
                            text: root.selectedCount > 1 ? "📋" : (root.selectedCount === 1 ? "📄" : "💻")
                            font.pixelSize: 11
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: {
                                if (root.selectedCount > 1) return root.tr("menu_hdr_multi", "Multi-Row Selection")
                                if (root.selectedCount === 1 && root.contextRowLevel) return "Log Entry  ·  " + root.contextRowLevel
                                if (root.selectedCount === 1) return root.tr("menu_hdr_single", "Selected Log Entry")
                                return root.tr("menu_hdr_console", "Console Output")
                            }
                            color: root.contextRowLevel === "ERROR" ? "#F87171" : (root.contextRowLevel === "WARNING" ? "#FBBF24" : "#38BDF8")
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            font.family: "Segoe UI, Inter, sans-serif"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Rectangle {
                        height: 16
                        width: badgeTxt.implicitWidth + 10
                        radius: 8
                        color: "#172338"
                        border.color: "#253B5E"
                        border.width: 1
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            id: badgeTxt
                            anchors.centerIn: parent
                            text: root.selectedCount > 0 ? (root.selectedCount + " " + root.tr("lbl_selected", "selected")) : (logList.count + " " + root.tr("lbl_total", "total"))
                            color: "#38BDF8"
                            font.pixelSize: 9
                            font.weight: Font.Bold
                            font.family: "Segoe UI, sans-serif"
                        }
                    }
                }
            }

            Item { height: 2 }

            // 1. Copy Selected / Copy All
            ContextMenuItem {
                icon: "📋"
                label: root.selectedCount > 0 ? (root.selectedCount > 1 ? root.tr("menu_copy_selected_plural", "Copy %1 Selected Rows").replace("%1", root.selectedCount) : root.tr("menu_copy_selected_one", "Copy Selected Row")) : root.tr("menu_copy_all", "Copy All Logs")
                shortcut: "Ctrl+C"
                onClicked: root.copySelectedLogs()
            }

            // 2. Copy Message Text Only (when 1 row selected)
            ContextMenuItem {
                visible: root.selectedCount === 1
                icon: "💬"
                label: root.tr("menu_copy_message_only", "Copy Message Only")
                shortcut: "Shift+C"
                onClicked: {
                    var indices = Object.keys(root.selectedIndicesMap).map(Number)
                    if (indices.length === 1 && root.logModel) {
                        var idx = indices[0]
                        var full = root.logModel.getSelectedText([idx])
                        var parts = full.split("] ")
                        var msgOnly = parts.length >= 3 ? parts.slice(2).join("] ") : (root.contextRowMessage || full)
                        if (typeof appBridge !== "undefined" && appBridge && appBridge.copyToClipboard) {
                            appBridge.copyToClipboard(msgOnly)
                        }
                        clipHelper.text = msgOnly
                        clipHelper.selectAll()
                        clipHelper.copy()
                        root.showToast(root.tr("toast_copied_message", "Copied message to clipboard!"))
                    }
                }
            }

            // 3. Copy All Visible Logs (when multi-row selection active)
            ContextMenuItem {
                visible: root.selectedCount > 0
                icon: "📑"
                label: root.tr("menu_copy_all_logs", "Copy All Logs") + " (" + logList.count + ")"
                shortcut: "Ctrl+Shift+C"
                onClicked: {
                    if (root.logModel) {
                        var textToCopy = root.logModel.getAllText()
                        if (textToCopy) {
                            if (typeof appBridge !== "undefined" && appBridge && appBridge.copyToClipboard) {
                                appBridge.copyToClipboard(textToCopy)
                            }
                            clipHelper.text = textToCopy
                            clipHelper.selectAll()
                            clipHelper.copy()
                            root.showToast(root.tr("toast_copied_all", "Copied all logs to clipboard!"))
                        }
                    }
                }
            }

            // Divider
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#182030"
                Layout.topMargin: 2
                Layout.bottomMargin: 2
            }

            // 4. Select All Rows
            ContextMenuItem {
                icon: "☑️"
                label: root.tr("menu_select_all", "Select All Rows")
                shortcut: "Ctrl+A"
                onClicked: root.selectAllRows()
            }

            // 5. Clear Selection
            ContextMenuItem {
                icon: "✖"
                label: root.tr("menu_clear_selection", "Clear Selection")
                shortcut: "Esc"
                active: root.selectedCount > 0
                onClicked: root.clearSelection()
            }

            // Divider
            Rectangle {
                visible: (!!root.contextRowCategory && root.contextRowCategory !== "general") || true
                Layout.fillWidth: true
                height: 1
                color: "#182030"
                Layout.topMargin: 2
                Layout.bottomMargin: 2
            }

            // 6. Filter by category
            ContextMenuItem {
                visible: !!root.contextRowCategory && root.contextRowCategory !== "general"
                icon: "🔍"
                label: root.tr("menu_filter_category", "Filter by '[cat]'").replace("[cat]", root.contextRowCategory)
                onClicked: searchInput.text = root.contextRowCategory
            }

            // 7. Export Logs to File
            ContextMenuItem {
                icon: "💾"
                label: root.tr("menu_export_logs", "Export Logs to File...")
                onClicked: root.exportLogsRequested()
            }

            // 8. Clear Console Logs
            ContextMenuItem {
                icon: "↻"
                danger: true
                label: root.tr("menu_clear_console", "Clear Console Output")
                onClicked: {
                    root.clearSelection()
                    root.clearLogsRequested()
                }
            }
        }
    }

    // Hidden text helper for copying to clipboard
    TextInput {
        id: clipHelper
        visible: false
    }

    // Floating toast feedback notification
    Rectangle {
        id: toastPill
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 24
        height: 28
        width: toastText.implicitWidth + 24
        radius: 14
        color: "#0F172A"
        border.color: "#38BDF8"
        border.width: 1
        opacity: 0.0
        visible: opacity > 0
        z: 30

        Behavior on opacity { NumberAnimation { duration: 150 } }

        Text {
            id: toastText
            anchors.centerIn: parent
            font.family: "Segoe UI, Inter, sans-serif"
            font.pixelSize: 11
            font.weight: 600
            color: "#38BDF8"
        }

        Timer {
            id: toastTimer
            interval: 1600
            onTriggered: toastPill.opacity = 0.0
        }
    }

    function showToast(msg) {
        toastText.text = msg
        toastPill.opacity = 1.0
        toastTimer.restart()
    }
}
