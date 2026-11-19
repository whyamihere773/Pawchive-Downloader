import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia
import "../../components"

GridView {
    id: explorerGridView
    required property var view
    property alias scrollAnim: gridScrollAnim
    visible: explorerGridView.view.viewMode === "grid"
    anchors.fill: parent
    anchors.margins: 10
    // Stretch cells so each row fills the full width (target = thumbSize per card)
    cellWidth: Math.floor(width / Math.max(1, Math.floor(width / explorerGridView.view.thumbSize)))
    readonly property int previewHeight: Math.max(70, Math.round((cellWidth - 18) * explorerGridView.view.thumbAspectRatio))
    cellHeight: previewHeight + 68
    model: explorerGridView.view.filteredItems
    clip: true
    cacheBuffer: 600
    focus: explorerGridView.view.viewMode === "grid"
    keyNavigationEnabled: true
    currentIndex: -1
    highlightFollowsCurrentItem: false
    onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, GridView.Contain)
    Keys.onPressed: (event) => explorerGridView.view.handleBrowserKey(explorerGridView, event)
    // Clicking empty space clears the selection (like File Explorer). Cards take their own
    // clicks, so this only sees presses that land between or below them.
    TapHandler {
        acceptedButtons: Qt.LeftButton
        onTapped: { explorerGridView.view.clearSelection(); explorerGridView.view.focusBrowser() }
    }

    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

    // Cards flow in with a short stagger when a folder opens
    property Transition flowIn: Transition { id: gridFlowIn
        SequentialAnimation {
            PropertyAction { property: "opacity"; value: 0 }
            PauseAnimation { duration: Math.max(0, Math.min(gridFlowIn.ViewTransition.index, 28)) * 14 }   // per-item stagger (index is -1 outside a run)
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 230; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 }
            }
        }
    }
    populate: explorerGridView.view.animatePopulate ? flowIn : null

    // Ctrl + mouse wheel resizes thumbnails
    WheelHandler {
        acceptedModifiers: Qt.ControlModifier
        onWheel: (event) => explorerGridView.view.setThumbSize(explorerGridView.view.thumbSize + (event.angleDelta.y > 0 ? 16 : -16))
    }
    // Plain wheel: accelerated, size-aware scrolling
    WheelHandler {
        acceptedModifiers: Qt.NoModifier
        onWheel: (event) => explorerGridView.view.wheelScroll(explorerGridView, gridScrollAnim, event, explorerGridView.cellHeight, 1)
    }
    NumberAnimation { id: gridScrollAnim; target: explorerGridView; property: "contentY"; duration: 160; easing.type: Easing.OutCubic }

    delegate: Item {
        id: gridCell
        readonly property var info: {
            explorerGridView.view.statsRev;
            var st = modelData.is_dir ? explorerGridView.view.folderStats[modelData.path] : undefined;
            var pv = modelData.is_dir ? explorerGridView.view.folderPreviews[modelData.path] : undefined;
            return (st || pv !== undefined) ? explorerGridView.view.withFolderStats(modelData, st, pv) : modelData
        }   // folder sizes and previews update in place
        readonly property var dirPreviews: (modelData.is_dir && explorerGridView.view.showFolderPreviews && gridCell.info.previews) ? gridCell.info.previews : []
        readonly property bool hasFolderPreviews: dirPreviews.length > 0
        width: explorerGridView.cellWidth
        height: explorerGridView.cellHeight
        readonly property bool isSel: explorerGridView.view.selectedPaths[modelData.path] === true
        readonly property bool isKeyFocus: explorerGridView.view.keyboardNav && GridView.isCurrentItem && explorerGridView.activeFocus
        readonly property bool spacer: !!modelData.is_header || !!modelData.is_filler
        readonly property bool dropHover: gridFolderDrop.containsDrag
        readonly property bool showCardBadges: !explorerGridView.view.cleanThumbCards || gridCardMouse.containsMouse || gridCell.isSel
        readonly property string cat: modelData.is_dir ? "folder" : explorerGridView.view.getCategory(modelData.ext)
        // Images via Qt; videos via the Windows thumbnail cache (single-preview folders reuse thumbImage)
        readonly property bool hasThumb: cat === "image" || cat === "video" || (!!modelData.is_group && !!modelData.cover) || gridCell.dirPreviews.length === 1
        // Post stacks fan out a little when hovered
        property real spread: (modelData.is_group && gridCardMouse.containsMouse) ? 1.8 : 1.0
        Behavior on spread { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }

        // Two offset "cards" behind a post stack
        Repeater {
            model: modelData.is_group ? 2 : 0
            Rectangle {
                anchors.fill: parent
                anchors.margins: 4
                anchors.leftMargin: 4 + (2 - index) * 4 * gridCell.spread
                anchors.topMargin: 4 - (2 - index) * 3 * gridCell.spread
                anchors.rightMargin: 4 - (2 - index) * 4 * gridCell.spread
                anchors.bottomMargin: 4 + (2 - index) * 3 * gridCell.spread
                radius: 8
                color: index === 0 ? "#1A1430" : "#211A3A"
                border.color: "#3B2F66"
                border.width: 1
            }
        }

        Rectangle {
            visible: !gridCell.spacer
            id: gridCard
            anchors.fill: parent
            anchors.margins: 4
            radius: 8
            color: gridCell.isSel ? "#16243A" : (gridCardMouse.containsMouse ? "#1A2234" : "#131824")
            border.color: gridCell.dropHover ? "#34D399" : (gridCell.isKeyFocus ? "#F8FAFC" : (gridCell.isSel ? "#38BDF8" : (gridCardMouse.containsMouse ? explorerGridView.view.getItemColor(modelData) : "#20283A")))
            border.width: (gridCell.isSel || gridCell.isKeyFocus || gridCell.dropHover) ? 2 : 1

            Springy { hover: gridCardMouse.containsMouse; pressed: gridCardMouse.pressed }
            Behavior on color { ColorAnimation { duration: 120 } }
            Behavior on border.color { ColorAnimation { duration: 120 } }

            // Preview area: real thumbnail for images, large icon otherwise
            Rectangle {
                id: previewArea
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 5
                height: explorerGridView.previewHeight
                radius: 6
                color: "#0D121C"
                clip: true

                Image {
                    id: thumbImage
                    anchors.fill: parent
                    // The provider returns a 1x1 placeholder when there's no thumbnail
                    visible: status === Image.Ready && implicitWidth > 1
                    opacity: visible ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
                    source: gridCell.hasThumb ? explorerGridView.view.thumbUrl(modelData.is_group ? modelData.cover : (gridCell.dirPreviews.length === 1 ? gridCell.dirPreviews[0] : modelData)) : ""
                    asynchronous: true
                    cache: true
                    smooth: true
                    fillMode: explorerGridView.view.resolvedImageFillMode
                    // Privacy blur: drawn through a tiny texture, so only soft colours remain
                    layer.enabled: explorerGridView.view.privacyBlur
                    layer.textureSize: Qt.size(12, 9)
                    layer.smooth: true
                }

                // 2x2 / 2x1 folder preview contact sheet when a folder has 2..4 images
                Item {
                    id: folderCollage
                    objectName: "folderPreviewCollage"
                    anchors.fill: parent
                    anchors.margins: 3
                    visible: gridCell.dirPreviews.length > 1
                    readonly property int gap: 3
                    readonly property int gridRows: gridCell.dirPreviews.length > 2 ? 2 : 1
                    layer.enabled: explorerGridView.view.privacyBlur
                    layer.textureSize: Qt.size(12, 9)
                    layer.smooth: true

                    Grid {
                        anchors.fill: parent
                        columns: 2
                        rows: folderCollage.gridRows
                        spacing: folderCollage.gap
                        Repeater {
                            model: gridCell.dirPreviews.length > 1 ? gridCell.dirPreviews : []
                            Rectangle {
                                width: Math.max(10, Math.floor((folderCollage.width - folderCollage.gap) / 2))
                                height: Math.max(10, Math.floor((folderCollage.height - (folderCollage.gridRows > 1 ? folderCollage.gap : 0)) / folderCollage.gridRows))
                                radius: 3
                                color: "#111827"
                                clip: true
                                Image {
                                    anchors.fill: parent
                                    source: explorerGridView.view.thumbUrl(modelData)
                                    asynchronous: true
                                    cache: true
                                    smooth: true
                                    fillMode: explorerGridView.view.resolvedImageFillMode
                                    visible: status === Image.Ready && implicitWidth > 1
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    visible: explorerGridView.view.privacyBlur && (gridCell.hasThumb || gridCell.hasFolderPreviews)
                    color: "#59101622"
                    Text { anchors.centerIn: parent; text: "🙈"; font.pixelSize: 22; opacity: 0.8 }
                }

                // Animated pictures play while hovered (stills show nothing extra)
                Loader {
                    anchors.fill: parent
                    active: gridCell.cat === "image" && gridCardMouse.containsMouse && !hoverPlayDelay.running && !explorerGridView.view.internalDragActive && !explorerGridView.view.privacyBlur
                    sourceComponent: AnimatedMedia {
                        path: modelData.path
                        tools: explorerGridView.view.tools
                        fillMode: explorerGridView.view.resolvedImageFillMode
                    }
                }

                // Muted looping preview while a video card is hovered (only the hovered card plays)
                Timer {
                    id: hoverPlayDelay
                    interval: 450
                    running: (gridCell.cat === "video" || gridCell.cat === "image") && gridCardMouse.containsMouse && !explorerGridView.view.internalDragActive
                }
                Loader {
                    id: hoverVideo
                    anchors.fill: parent
                    active: gridCell.cat === "video" && gridCardMouse.containsMouse && !hoverPlayDelay.running && !explorerGridView.view.internalDragActive && !explorerGridView.view.privacyBlur
                    sourceComponent: Item {
                        MediaPlayer {
                            id: previewPlayer
                            source: explorerGridView.view._urlFor(modelData.path)
                            videoOutput: previewOutput
                            loops: MediaPlayer.Infinite
                            Component.onCompleted: play()
                            Component.onDestruction: stop()
                        }
                        VideoOutput {
                            id: previewOutput
                            anchors.fill: parent
                            fillMode: explorerGridView.view.resolvedVideoFillMode
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: !thumbImage.visible && gridCell.dirPreviews.length <= 1
                    text: explorerGridView.view.getItemIcon(modelData)
                    font.pixelSize: 34
                    opacity: thumbImage.status === Image.Loading ? 0.35 : 0.9
                }

                // Favourite star
                Rectangle {
                    readonly property bool on: explorerGridView.view.isFavorite(modelData) && gridCell.showCardBadges
                    visible: opacity > 0.01
                    opacity: on ? 1 : 0
                    scale: on ? 1 : 0.2
                    Behavior on opacity { NumberAnimation { duration: 120 } }
                    Behavior on scale { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.001 } }
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.topMargin: 5
                    anchors.leftMargin: 30
                    width: 20; height: 20; radius: 10
                    color: "#CC0B0E17"
                    border.color: "#F59E0B"
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "★"; font.pixelSize: 11; color: "#FBBF24" }
                }

                // Folder corner pill so previewed folders stay unmistakably identifiable as folders
                Rectangle {
                    objectName: "folderPreviewBadge"
                    visible: modelData.is_dir && gridCell.hasFolderPreviews && gridCell.showCardBadges
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    anchors.margins: 5
                    implicitHeight: 18
                    implicitWidth: folderCornerLabel.implicitWidth + 10
                    radius: 4
                    color: "#D90B0E17"
                    border.color: "#38BDF8"
                    border.width: 1
                    Text {
                        id: folderCornerLabel
                        anchors.centerIn: parent
                        text: "📁"
                        font.pixelSize: 10
                    }
                }

                // File count badge on post stacks
                Rectangle {
                    visible: !!modelData.is_group && gridCell.showCardBadges
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    anchors.margins: 5
                    implicitHeight: 18
                    implicitWidth: stackCount.implicitWidth + 12
                    radius: 4
                    color: "#E6241B44"
                    border.color: "#A78BFA"
                    border.width: 1
                    Text {
                        id: stackCount
                        anchors.centerIn: parent
                        text: "🗂 " + (gridCell.info.file_count || 0)
                        font.pixelSize: 9
                        font.weight: 700
                        color: "#EDE9FE"
                    }
                }

                // Play badge for videos
                Rectangle {
                    visible: gridCell.cat === "video" && gridCell.showCardBadges
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 5
                    width: 20; height: 20; radius: 10
                    color: "#CC0B0E17"
                    Text { anchors.centerIn: parent; anchors.horizontalCenterOffset: 1; text: "▶"; font.pixelSize: 9; color: "#E2E8F0" }
                }

                // Size / item-count badge
                Rectangle {
                    visible: gridCell.showCardBadges
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: 5
                    implicitHeight: 16
                    implicitWidth: sizeText.implicitWidth + 10
                    radius: 4
                    color: "#CC0B0E17"
                    border.color: modelData.is_dir ? (gridCell.info.size >= 0 ? "#38BDF8" : "#25334D") : "transparent"
                    border.width: modelData.is_dir ? 1 : 0
                    Text {
                        id: sizeText
                        anchors.centerIn: parent
                        text: explorerGridView.view.formatFolderSize(gridCell.info)
                        font.pixelSize: 9
                        font.weight: modelData.is_dir ? 600 : Font.Normal
                        color: modelData.is_dir ? (gridCell.info.size >= 0 ? "#38BDF8" : "#94A3B8") : "#CBD5E1"
                    }
                }
            }

            Text {
                id: gridName
                anchors.top: previewArea.bottom
                anchors.topMargin: 5
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                text: modelData.name || ""
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: modelData.is_dir ? 600 : Font.Normal
                color: modelData.is_dir ? "#38BDF8" : "#E2E8F0"
                elide: Text.ElideMiddle
                maximumLineCount: 2
                wrapMode: Text.WrapAnywhere
            }

            Text {
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 6
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                text: (explorerGridView.view.ratingOf(modelData) > 0 ? explorerGridView.view.starText(explorerGridView.view.ratingOf(modelData)) + "  " : "")
                      + (modelData.is_group ? (gridCell.info.file_count + " files • post " + modelData.group_key)
                      : (modelData.rel_dir ? ("📁 " + explorerGridView.view.displayDir(modelData.rel_dir)) : explorerGridView.view.formatFolderSubtitle(gridCell.info)))
                font.pixelSize: 9
                color: modelData.is_dir ? (gridCell.info.size >= 0 ? "#38BDF8" : "#818CF8") : "#64748B"
                elide: Text.ElideRight
            }
        }

        // Invisible handle the MouseArea drags; Qt turns it into a system file drag
        Item {
            id: gridDragItem
            width: 1
            height: 1
            Drag.dragType: Drag.Automatic
            // Copy only: other apps (Explorer, Discord…) get copies and can never move files out
            // behind the gallery's back. Drops onto gallery folders are moved by handleDrop().
            Drag.supportedActions: Qt.CopyAction
            Drag.proposedAction: Qt.CopyAction
            Drag.mimeData: gridCell.isSel ? explorerGridView.view.selectionMime : explorerGridView.view.mimeForItems(modelData.is_group ? modelData.members : [modelData])
            Drag.imageSource: explorerGridView.view.dragImageFor(modelData)
            Drag.active: gridCardMouse.drag.active
            Drag.onDragStarted: explorerGridView.view.beginDrag(modelData)
            Drag.onDragFinished: { explorerGridView.view.endDrag(); x = 0; y = 0 }
        }

        // Folders accept drops: gallery items are moved in, files from Explorer are copied in
        DropArea {
            id: gridFolderDrop
            anchors.fill: parent
            enabled: !!modelData.is_dir
            keys: ["text/uri-list"]
            onDropped: (drop) => explorerGridView.view.handleDrop(drop, modelData.path)
        }

        MouseArea {
            enabled: !gridCell.spacer
            id: gridCardMouse
            anchors.fill: parent
            anchors.margins: 4
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            drag.target: gridDragItem
            drag.threshold: 12
            preventStealing: true
            onClicked: (mouse) => {
                if (mouse.button === Qt.RightButton) {
                    explorerGridView.view.showContextMenu(modelData, index, gridCardMouse, mouse.x, mouse.y)
                } else {
                    explorerGridView.view.handleItemClick(modelData, index, mouse)
                }
            }
            onDoubleClicked: (mouse) => {
                if (mouse.button === Qt.LeftButton) explorerGridView.view.handleItemDoubleClick(modelData)
            }
            ToolTip.visible: containsMouse && !gridCheckMouse.containsMouse
            ToolTip.delay: 450
            ToolTip.text: {
                if (modelData.is_group)
                    return "🗂 " + modelData.name + "\n" + gridCell.info.file_count + " files from post " + modelData.group_key
                        + "\n• Double-click to open the post's files\n• Right-click for actions on all its files"
                var tip = (modelData.is_dir ? "📁 " : "📄 ") + (modelData.name || "")
                if (modelData.is_dir) {
                    tip += "\n" + explorerGridView.view.formatFolderSubtitle(gridCell.info)
                    tip += "\n• Double-click to open folder"
                } else {
                    tip += "\nSize: " + explorerGridView.view.formatBytes(gridCell.info.size) + "\nModified: " + explorerGridView.view.formatDate(modelData.mtime)
                    if (explorerGridView.view.isMedia(modelData)) {
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

        // Selection checkbox (declared after the card MouseArea so it receives clicks first)
        Rectangle {
            id: gridCheck
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.topMargin: 12
            anchors.leftMargin: 12
            width: 18; height: 18; radius: 4
            readonly property bool shown: gridCell.isSel || gridCardMouse.containsMouse || gridCheckMouse.containsMouse || explorerGridView.view.selectionCount > 0
            visible: (!gridCell.spacer) && (opacity > 0.01)
            opacity: shown ? 1 : 0
            scale: gridCell.isSel ? 1.0 : (gridCheckMouse.containsMouse ? 1.12 : (shown ? 0.92 : 0.6))
            Behavior on opacity { NumberAnimation { duration: 120 } }
            Behavior on scale { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.001 } }
            color: gridCell.isSel ? "#38BDF8" : "#CC0B0E17"
            border.color: gridCell.isSel ? "#38BDF8" : (gridCheckMouse.containsMouse ? "#38BDF8" : "#94A3B8")
            border.width: 1
            Text {
                anchors.centerIn: parent
                opacity: gridCell.isSel ? 1 : 0
                scale: gridCell.isSel ? 1 : 0.2
                Behavior on scale { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.001 } }
                Behavior on opacity { NumberAnimation { duration: 90 } }
                text: "✓"
                font.pixelSize: 12
                font.weight: 800
                color: "#0F172A"
            }
            MouseArea {
                id: gridCheckMouse
                anchors.fill: parent
                anchors.margins: -3
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: (mouse) => {
                    if ((mouse.modifiers & Qt.ShiftModifier) !== 0) {
                        explorerGridView.view.selectRange(explorerGridView.view.selectionAnchor >= 0 ? explorerGridView.view.selectionAnchor : index, index, true)
                    } else {
                        explorerGridView.view.toggleSelection(modelData.path)
                        explorerGridView.view.selectionAnchor = index
                    }
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: gridCell.isSel ? "Deselect" : "Select"
            }
        }

        // Group by date: the tile that opens each section (click = select the section)
        Rectangle {
            visible: !!modelData.is_header
            anchors.fill: parent
            anchors.margins: 4
            radius: 10
            color: tileMouse.containsMouse ? "#16233A" : "#0F1726"
            border.color: gridCell.isKeyFocus ? "#F8FAFC" : (tileMouse.containsMouse ? "#38BDF8" : "#24324A")
            border.width: gridCell.isKeyFocus ? 2 : 1
            Springy { hover: tileMouse.containsMouse; pressed: tileMouse.pressed }
            Column {
                anchors.centerIn: parent
                width: parent.width - 20
                spacing: 6
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.icon || "📅"; font.pixelSize: 26 }
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: modelData.name || ""
                    wrapMode: Text.WordWrap
                    font.family: "Segoe UI, sans-serif"; font.pixelSize: 16; font.weight: 700; color: "#F1F5F9"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: (modelData.count || 0) + ((modelData.count || 0) === 1 ? " item" : " items")
                    font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; color: "#94A3B8"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Click to select all"
                    opacity: tileMouse.containsMouse ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 150 } }
                    font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; color: "#38BDF8"
                }
            }
            MouseArea {
                id: tileMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: (mouse) => explorerGridView.view.handleItemClick(modelData, index, mouse)
            }
        }
    }
}
