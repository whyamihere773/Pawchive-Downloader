import QtQuick

MouseArea {
    id: ctxArea

    // Target TextInput / TextField / TextArea / TextEdit.
    // Defaults to parent so dropping `TextBarContextArea {}` inside any text
    // control immediately adds I-beam cursor, browser-bar first-focus selectAll(),
    // and right-click context menu.
    property var target: parent

    // Set true when placed behind a padded wrapper Rectangle/RowLayout so
    // left-clicking anywhere inside the bar focuses the text input and
    // right-clicking anywhere inside the bar opens the context menu.
    property bool focusOnLeftClick: false

    // AGENTS.md Rule 6: Browser-bar click-to-select-all on first focus for single-line fields.
    // TextInput & TextField do not expose `textFormat`, while multi-line TextEdit & TextArea do.
    property bool selectAllOnFirstFocus: !!(target && typeof target.textFormat === "undefined")

    anchors.fill: parent
    acceptedButtons: focusOnLeftClick ? (Qt.LeftButton | Qt.RightButton) : Qt.RightButton
    hoverEnabled: focusOnLeftClick
    cursorShape: Qt.IBeamCursor

    // First-focus left-click catcher for direct children of TextInput / TextField:
    // active ONLY while the input is unfocused so the very first click focuses & selects all,
    // then immediately disables itself so all subsequent clicks/drags go natively to the input.
    MouseArea {
        id: firstFocusCatcher
        anchors.fill: parent
        enabled: !ctxArea.focusOnLeftClick
                 && ctxArea.selectAllOnFirstFocus
                 && !!ctxArea.target
                 && !ctxArea.target.activeFocus
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.IBeamCursor
        onClicked: {
            if (!ctxArea.target) return
            if (typeof ctxArea.target.forceActiveFocus === "function") {
                ctxArea.target.forceActiveFocus()
            }
            if (typeof ctxArea.target.selectAll === "function") {
                ctxArea.target.selectAll()
            }
        }
    }

    onClicked: function(mouse) {
        if (!ctxArea.target) return
        if (mouse.button === Qt.RightButton) {
            var pt = ctxArea.mapToItem(ctxArea.target, mouse.x, mouse.y)
            if (typeof appWindow !== "undefined" && appWindow && typeof appWindow.openTextContextMenu === "function") {
                appWindow.openTextContextMenu(ctxArea.target, pt.x, pt.y)
            } else if (typeof globalTextContextMenu !== "undefined" && globalTextContextMenu) {
                globalTextContextMenu.showAt(ctxArea.target, pt.x, pt.y)
            }
        } else if (ctxArea.focusOnLeftClick) {
            var wasFocused = !!ctxArea.target.activeFocus
            if (typeof ctxArea.target.forceActiveFocus === "function") {
                ctxArea.target.forceActiveFocus()
            }
            if (!wasFocused && ctxArea.selectAllOnFirstFocus && typeof ctxArea.target.selectAll === "function") {
                ctxArea.target.selectAll()
            } else if (typeof ctxArea.target.cursorPosition === "number" && typeof ctxArea.target.text === "string") {
                var localPt = ctxArea.mapToItem(ctxArea.target, mouse.x, mouse.y)
                if (localPt.x >= ctxArea.target.width) {
                    ctxArea.target.cursorPosition = ctxArea.target.text.length
                } else if (localPt.x <= 0) {
                    ctxArea.target.cursorPosition = 0
                }
            }
        }
    }
}
