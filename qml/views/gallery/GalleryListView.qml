import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Item {
    id: listContainer
    required property var view
    property alias listView: explorerListView
    property alias scrollAnim: listScrollAnim
    visible: listContainer.view.viewMode === "list"
    anchors.fill: parent
    anchors.margins: 6

    // Column Header
    Rectangle {
        id: listHeader
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 22
        color: "transparent"

        GallerySortHeader {
            anchors.left: parent.left
            anchors.leftMargin: 52
            anchors.verticalCenter: parent.verticalCenter
            width: 200
            gallery: listContainer.view
            label: "NAME"
            sortKeyName: "name"
            alignRight: false
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12

            GallerySortHeader { gallery: listContainer.view; width: 130; visible: listContainer.view.showTypeColumn; label: "ITEMS / TYPE"; sortKeyName: "type" }
            GallerySortHeader { gallery: listContainer.view; width: 85; label: "SIZE"; sortKeyName: "size" }
            GallerySortHeader { gallery: listContainer.view; width: 140; label: "DATE MODIFIED"; sortKeyName: "date" }
        }

        Rectangle {
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            height: 1
            color: "#1E2536"
        }
    }

    ListView {
        id: explorerListView
        focus: listContainer.view.viewMode === "list"
        keyNavigationEnabled: true
        currentIndex: -1
        highlightFollowsCurrentItem: false
        onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)
        Keys.onPressed: (event) => listContainer.view.handleBrowserKey(explorerListView, event)
        // Clicking empty space clears the selection (like File Explorer). Cards take their own
        // clicks, so this only sees presses that land between or below them.
        TapHandler {
            acceptedButtons: Qt.LeftButton
            onTapped: { listContainer.view.clearSelection(); listContainer.view.focusBrowser() }
        }
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        property Transition flowIn: Transition { id: listFlowIn
        SequentialAnimation {
            PropertyAction { property: "opacity"; value: 0 }
            PauseAnimation { duration: Math.max(0, Math.min(listFlowIn.ViewTransition.index, 28)) * 14 }   // per-item stagger (index is -1 outside a run)
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 230; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 }
            }
        }
    }
        populate: listContainer.view.animatePopulate ? flowIn : null
        WheelHandler {
            acceptedModifiers: Qt.NoModifier
            onWheel: (event) => listContainer.view.wheelScroll(explorerListView, listScrollAnim, event, 34, 3)
        }
        NumberAnimation { id: listScrollAnim; target: explorerListView; property: "contentY"; duration: 160; easing.type: Easing.OutCubic }
        anchors.top: listHeader.bottom
        anchors.topMargin: 4
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 2
        model: listContainer.view.filteredItems
        clip: true

        delegate: Rectangle {
            id: listRow
            readonly property var info: { listContainer.view.statsRev; var st = modelData.is_dir ? listContainer.view.folderStats[modelData.path] : undefined; return st ? listContainer.view.withFolderStats(modelData, st) : modelData }   // folder sizes update in place
            readonly property bool isSel: listContainer.view.selectedPaths[modelData.path] === true
            readonly property bool isKeyFocus: listContainer.view.keyboardNav && ListView.isCurrentItem && explorerListView.activeFocus
            readonly property bool spacer: !!modelData.is_header || !!modelData.is_filler
            readonly property bool dropHover: listFolderDrop.containsDrag
            transform: Translate {
                x: listRowMouse.containsMouse ? 3 : 0
                Behavior on x { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
            }
            width: explorerListView.width
            height: 32
            radius: 5
            color: isSel ? "#16243A" : (listRowMouse.containsMouse ? "#1B2336" : (index % 2 === 0 ? "#111622" : "#0E121B"))
            border.color: dropHover ? "#34D399" : (isKeyFocus ? "#F8FAFC" : ((isSel || listRowMouse.containsMouse) ? "#38BDF8" : "transparent"))
            border.width: 1

            Text {
                visible: !listRow.spacer
                id: rowIcon
                anchors.left: parent.left
                anchors.leftMargin: 30
                anchors.verticalCenter: parent.verticalCenter
                text: listContainer.view.getItemIcon(modelData)
                font.pixelSize: 14
            }

            // Right-side columns (Fixed width, right aligned, strict spacing)
            Row {
                visible: !listRow.spacer
                id: rightCols
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 12

                // Files / Child count column
                Text {
                    width: 130
                    visible: listContainer.view.showTypeColumn
                    anchors.verticalCenter: parent.verticalCenter
                    text: {
                        if (modelData.is_dir) {
                            if (listRow.info.file_count >= 0) {
                                var cnt = listRow.info.file_count + (listRow.info.file_count === 1 ? " file" : " files")
                                if (listRow.info.folder_count > 0) {
                                    cnt += " (" + listRow.info.folder_count + " dirs)"
                                }
                                return cnt
                            }
                            return modelData.child_count + (modelData.child_count === 1 ? " item" : " items")
                        }
                        if (modelData.is_group) return listRow.info.file_count + " files (post)"
                        return modelData.ext ? modelData.ext.toUpperCase() : "FILE"
                    }
                    font.family: "Segoe UI, monospace"
                    font.pixelSize: 10
                    font.weight: modelData.is_dir ? 600 : Font.Normal
                    color: modelData.is_dir ? "#A78BFA" : "#64748B"
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideRight
                }

                // Size column
                Text {
                    width: 85
                    anchors.verticalCenter: parent.verticalCenter
                    text: listContainer.view.formatFolderSize(listRow.info)
                    font.family: "Segoe UI, monospace"
                    font.pixelSize: 10
                    font.weight: (modelData.is_dir && listRow.info.size >= 0) ? 600 : Font.Normal
                    color: modelData.is_dir ? (listRow.info.size >= 0 ? "#38BDF8" : "#818CF8") : "#94A3B8"
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideRight
                }

                // Date Modified column
                Text {
                    width: 140
                    anchors.verticalCenter: parent.verticalCenter
                    text: listContainer.view.formatDate(modelData.mtime)
                    font.family: "Segoe UI, monospace"
                    font.pixelSize: 10
                    color: "#64748B"
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideRight
                }
            }

            // Filename fills between icon and right columns
            Text {
                visible: !listRow.spacer
                anchors.left: rowIcon.right
                anchors.leftMargin: 10
                anchors.right: rightCols.left
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                text: (listContainer.view.isFavorite(modelData) ? "★ " : "") + (listContainer.view.ratingOf(modelData) > 0 ? "[" + listContainer.view.ratingOf(modelData) + "★] " : "")
                      + (modelData.rel_dir ? (listContainer.view.displayDir(modelData.rel_dir) + "  ›  " + modelData.name) : (modelData.name || ""))
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: modelData.is_dir ? 600 : Font.Normal
                color: modelData.is_dir ? "#38BDF8" : "#E2E8F0"
                elide: Text.ElideMiddle
            }

            Item {
                id: listDragItem
                width: 1
                height: 1
                Drag.dragType: Drag.Automatic
                Drag.supportedActions: Qt.CopyAction
                Drag.proposedAction: Qt.CopyAction
                Drag.mimeData: listRow.isSel ? listContainer.view.selectionMime : listContainer.view.mimeForItems(modelData.is_group ? modelData.members : [modelData])
                Drag.imageSource: listContainer.view.dragImageFor(modelData)
                Drag.active: listRowMouse.drag.active
                Drag.onDragStarted: listContainer.view.beginDrag(modelData)
                Drag.onDragFinished: { listContainer.view.endDrag(); x = 0; y = 0 }
            }

            DropArea {
                id: listFolderDrop
                anchors.fill: parent
                enabled: !!modelData.is_dir
                keys: ["text/uri-list"]
                onDropped: (drop) => listContainer.view.handleDrop(drop, modelData.path)
            }

            MouseArea {
                enabled: !listRow.spacer
                id: listRowMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                drag.target: listDragItem
                drag.threshold: 12
                preventStealing: true
                onClicked: (mouse) => {
                    if (mouse.button === Qt.RightButton) {
                        listContainer.view.showContextMenu(modelData, index, listRowMouse, mouse.x, mouse.y)
                    } else {
                        listContainer.view.handleItemClick(modelData, index, mouse)
                    }
                }
                onDoubleClicked: (mouse) => {
                    if (mouse.button === Qt.LeftButton) listContainer.view.handleItemDoubleClick(modelData)
                }
                ToolTip.visible: containsMouse && !listCheckMouse.containsMouse
                ToolTip.delay: 450
                ToolTip.text: {
                    var tip = (modelData.is_dir ? "📁 " : "📄 ") + (modelData.name || "")
                    if (modelData.is_dir) {
                        tip += "\n" + listContainer.view.formatFolderSubtitle(listRow.info)
                        tip += "\n• Double-click to open folder"
                    } else {
                        tip += "\nSize: " + listContainer.view.formatBytes(listRow.info.size) + "\nModified: " + listContainer.view.formatDate(modelData.mtime)
                        if (listContainer.view.isMedia(modelData)) {
                            tip += "\n• Double-click to preview in Lightbox"
                        } else {
                            tip += "\n• Double-click to open in default app"
                        }
                    }
                    tip += "\n• Click to select, Ctrl+click or tick the box to add more, Shift+click for a range\n• Type a name to jump to it"
                    tip += "\n• Right-click for more actions"
                    return tip
                }
            }

            // Selection checkbox (after the row MouseArea so it receives clicks first)
            Rectangle {
                visible: !listRow.spacer
                anchors.left: parent.left
                anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                width: 14; height: 14; radius: 3
                opacity: (listRow.isSel || listRowMouse.containsMouse || listCheckMouse.containsMouse || listContainer.view.selectionCount > 0) ? 1.0 : 0.0
                color: listRow.isSel ? "#38BDF8" : "transparent"
                border.color: listRow.isSel ? "#38BDF8" : (listCheckMouse.containsMouse ? "#38BDF8" : "#64748B")
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    visible: listRow.isSel
                    text: "✓"
                    font.pixelSize: 10
                    font.weight: 800
                    color: "#0F172A"
                }
                MouseArea {
                    id: listCheckMouse
                    anchors.fill: parent
                    anchors.margins: -4
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: (mouse) => {
                        if ((mouse.modifiers & Qt.ShiftModifier) !== 0) {
                            listContainer.view.selectRange(listContainer.view.selectionAnchor >= 0 ? listContainer.view.selectionAnchor : index, index, true)
                        } else {
                            listContainer.view.toggleSelection(modelData.path)
                            listContainer.view.selectionAnchor = index
                        }
                    }
                }
            }
            // Group by date: section header row (click = select the section)
            Rectangle {
                visible: !!modelData.is_header
                anchors.fill: parent
                radius: 5
                color: listTileMouse.containsMouse ? "#16233A" : "#0F1726"
                border.color: listRow.isKeyFocus ? "#F8FAFC" : (listTileMouse.containsMouse ? "#38BDF8" : "#24324A")
                Row {
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8
                    Text { text: modelData.icon || "📅"; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: modelData.name || ""; font.family: "Segoe UI, sans-serif"; font.pixelSize: 12; font.weight: 700; color: "#F1F5F9"; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: (modelData.count || 0) + ((modelData.count || 0) === 1 ? " item" : " items"); font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
                    Text { visible: listTileMouse.containsMouse; text: "·  click to select all"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                }
                MouseArea {
                    id: listTileMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: (mouse) => listContainer.view.handleItemClick(modelData, index, mouse)
                }
            }
        }
    }
}
