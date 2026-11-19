import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "console_log"

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

    function copyMessageOnly() {
        var indices = Object.keys(selectedIndicesMap).map(Number)
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

    function copyAllLogs() {
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

    // Full labels only when they really fit. The width is measured with the fonts actually in use:
    // on Linux "Segoe UI" is missing and the replacement font is wider, so a fixed width let the
    // last button slide off the edge (#23).
    FontMetrics { id: fmLogTitle; font.family: "Segoe UI, Inter, sans-serif"; font.pixelSize: 12; font.weight: 600 }
    FontMetrics { id: fmLogBtn; font.family: "Segoe UI, Inter, sans-serif"; font.pixelSize: 10; font.weight: 600 }
    FontMetrics { id: fmLogPill; font.pixelSize: 9; font.weight: Font.Bold }
    readonly property real fullHeaderWidth: {
        var pills = 0
        var levels = ["ALL", "INFO", "WARN", "ERR"]
        for (var i = 0; i < levels.length; i++) pills += Math.max(42, fmLogPill.advanceWidth(levels[i]) + 14) + 4
        var buttons = Math.max(120, fmLogBtn.advanceWidth(root.tr("btn_download_links", "Download Links")) + 38)
                    + Math.max(106, fmLogBtn.advanceWidth(root.tr("btn_export_links", "Export Links")) + 38)
                    + Math.max(90, fmLogBtn.advanceWidth(root.tr("btn_copy_selected", "Copy (%1)").replace("%1", "999")) + 36)
                    + Math.max(70, fmLogBtn.advanceWidth(root.tr("btn_reset", "Reset")) + 32)
        var title = 13 + 6 + fmLogTitle.advanceWidth(root.tr("title_progress_log", "Progress Log"))
        return 20 + title + pills + buttons + 8 * 6 + 24   // margins + gaps between items + safety room
    }
    readonly property bool isCompact: root.width < Math.max(780, fullHeaderWidth)
    readonly property bool isVeryNarrow: root.width < 440

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
        ConsoleLogHeader {
            consoleView: root
        }

        // Search bar
        Rectangle {
            Layout.fillWidth: true
            height: 26
            radius: 5
            color: searchInput.activeFocus ? "#0B0D12" : "#13161E"
            border.color: searchInput.activeFocus ? "#38BDF8" : (consoleSearchMouse.containsMouse ? "#475569" : "#242A38")
            border.width: searchInput.activeFocus ? 1.5 : 1

            TextBarContextArea {
                id: consoleSearchMouse
                target: searchInput
                focusOnLeftClick: true
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                Text { text: "🔍"; font.pixelSize: 10; color: "#64748B" }

                TextInput {
                    id: searchInput
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    verticalAlignment: TextInput.AlignVCenter
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#F1F5F9"
                    selectionColor: "#0284C7"
                    selectedTextColor: "#FFFFFF"
                    clip: true
                    selectByMouse: true

                    TextBarContextArea {}

                    Text {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
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

                Rectangle {
                    width: 16; height: 16; radius: 8
                    color: clearConsoleSearchMouse.containsMouse ? "#374151" : "#1F2430"
                    visible: searchInput.text.length > 0
                    Text { anchors.centerIn: parent; text: "×"; font.bold: true; font.pixelSize: 11; color: "#94A3B8" }
                    MouseArea {
                        id: clearConsoleSearchMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            searchInput.text = ""
                            searchInput.forceActiveFocus()
                        }
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
                    if (event.key === Qt.Key_C && (event.modifiers & Qt.ControlModifier) && (event.modifiers & Qt.ShiftModifier)) {
                        root.copyAllLogs()
                        event.accepted = true
                    } else if (event.key === Qt.Key_C && (event.modifiers & Qt.ShiftModifier) && !(event.modifiers & Qt.ControlModifier) && !(event.modifiers & Qt.AltModifier)) {
                        if (root.selectedCount === 1) {
                            root.copyMessageOnly()
                            event.accepted = true
                        }
                    } else if (event.matches(StandardKey.Copy) || (event.key === Qt.Key_C && (event.modifiers & Qt.ControlModifier))) {
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
                            border.color: (typeof model.levelColor !== "undefined" && model.levelColor) ? model.levelColor : "#38BDF8"
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                text: (typeof model.icon !== "undefined" && model.icon) ? model.icon : "•"
                                font.pixelSize: 9
                                font.bold: true
                                color: (typeof model.levelColor !== "undefined" && model.levelColor) ? model.levelColor : "#38BDF8"
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
                            color: rowItem.isSelected ? "#F1F5F9" : ((typeof model.levelColor !== "undefined" && model.levelColor) ? model.levelColor : "#CBD5E1")
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
    ConsoleLogContextMenu {
        id: logContextMenu
        consoleView: root
        totalCount: logList.count
        onCopyTextRequested: (textToCopy, toastMsg) => {
            if (typeof appBridge !== "undefined" && appBridge && appBridge.copyToClipboard) {
                appBridge.copyToClipboard(textToCopy)
            }
            clipHelper.text = textToCopy
            clipHelper.selectAll()
            clipHelper.copy()
            root.showToast(toastMsg)
        }
        onFilterCategoryRequested: (category) => {
            searchInput.text = category
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
