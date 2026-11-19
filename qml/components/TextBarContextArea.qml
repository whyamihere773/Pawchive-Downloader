import QtQuick

MouseArea {
    id: ctxArea

    // Target TextInput / TextField / TextArea / TextEdit.
    // Defaults to parent so dropping `TextBarContextArea {}` inside any text
    // control immediately adds I-beam cursor + right-click context menu.
    property var target: parent

    // Set true when placed behind a padded wrapper Rectangle/RowLayout so
    // left-clicking anywhere inside the bar focuses the text input and
    // right-clicking anywhere inside the bar opens the context menu.
    property bool focusOnLeftClick: false

    anchors.fill: parent
    acceptedButtons: focusOnLeftClick ? (Qt.LeftButton | Qt.RightButton) : Qt.RightButton
    hoverEnabled: focusOnLeftClick
    cursorShape: Qt.IBeamCursor

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
            if (typeof ctxArea.target.forceActiveFocus === "function") {
                ctxArea.target.forceActiveFocus()
            }
            if (typeof ctxArea.target.cursorPosition === "number" && typeof ctxArea.target.text === "string") {
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
