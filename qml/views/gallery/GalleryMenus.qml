import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Item {
    id: galleryMenus
    required property var view
    anchors.fill: parent
    z: 9100

    property alias contextMenu: contextMenu
    property alias charMenu: charMenu
    property alias viewMenu: viewMenu
    property alias moreMenu: moreMenu
    property alias sortMenu: sortMenu
    readonly property bool anyMenuOpen: contextMenu.visible || sortMenu.visible || moreMenu.visible || viewMenu.visible || charMenu.visible

    function openViewMenu(anchorItem) {
        var p = anchorItem.mapToItem(galleryMenus.view, anchorItem.width - viewMenu.width, anchorItem.height + 4)
        viewMenu.x = Math.max(4, p.x)
        viewMenu.y = p.y
        viewMenu.open()
    }

    function openSortMenu(anchorItem) {
        var p = anchorItem.mapToItem(galleryMenus.view, 0, anchorItem.height + 4)
        sortMenu.x = Math.max(4, Math.min(p.x, galleryMenus.view.width - sortMenu.width - 4))
        sortMenu.y = p.y
        sortMenu.open()
    }

    function openCharMenu(anchorItem) {
        var p = anchorItem.mapToItem(galleryMenus.view, 0, anchorItem.height + 4)
        charMenu.x = Math.max(4, Math.min(p.x, galleryMenus.view.width - charMenu.width - 4))
        charMenu.y = p.y
        charMenu.open()
    }

    Popup {
        id: contextMenu
        // Springs open from its anchor, eases away
        transformOrigin: Popup.TopLeft
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 5.5; damping: 0.28; mass: 0.7; epsilon: 0.001 }
            }
        }
        exit: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: 110 }
                NumberAnimation { property: "scale"; to: 0.94; duration: 110; easing.type: Easing.InCubic }
            }
        }
        readonly property bool single: galleryMenus.view.contextItems.length === 1
        readonly property var first: galleryMenus.view.contextItems.length > 0 ? galleryMenus.view.contextItems[0] : null
        // Web page of the post this file came from (looked up when the menu opens)
        property string sourceUrl: ""
        // The selected files "Compress pictures & videos…" can compress (looked up when the menu opens)
        property var compressible: []
        width: 230
        padding: 4
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: "#121725"
            radius: 7
            border.color: "#2B354C"
            border.width: 1
        }

        contentItem: Column {
            spacing: 0

            Text {
                width: parent.width
                leftPadding: 8; rightPadding: 8; topPadding: 4; bottomPadding: 4
                text: contextMenu.single ? (contextMenu.first ? contextMenu.first.name : "") : (galleryMenus.view.contextItems.length + " items selected")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                font.weight: 700
                color: "#94A3B8"
                elide: Text.ElideMiddle
            }
            GalleryMenuDivider {}

            GalleryMenuRow {
                visible: contextMenu.single
                icon: "↗"; label: "Open"
                onTriggered: { contextMenu.close(); galleryMenus.view.openItem(contextMenu.first) }
            }
            GalleryMenuRow {
                visible: contextMenu.single && !!contextMenu.first && !contextMenu.first.is_dir && galleryMenus.view.isMedia(contextMenu.first)
                icon: "🖥️"; label: "Open in default app"
                onTriggered: { contextMenu.close(); if (galleryMenus.view.bridge) galleryMenus.view.bridge.openPathInSystem(contextMenu.first.path) }
            }
            GalleryMenuRow {
                visible: contextMenu.single
                icon: "📂"; label: "Show in File Explorer"
                onTriggered: { contextMenu.close(); galleryMenus.view.revealItem(contextMenu.first) }
            }
            GalleryMenuRow {
                visible: contextMenu.single && !!contextMenu.first && !!contextMenu.first.rel_dir
                icon: "🗂"; label: "Go to its folder"
                onTriggered: { contextMenu.close(); galleryMenus.view.revealInGallery(contextMenu.first.path) }
            }
            GalleryMenuRow {
                visible: contextMenu.sourceUrl.length > 0
                icon: "🌐"; label: "View source post"
                hint: "browser"
                onTriggered: { contextMenu.close(); Qt.openUrlExternally(contextMenu.sourceUrl) }
            }
            GalleryMenuRow {
                visible: contextMenu.sourceUrl.length > 0
                icon: "🔗"; label: "Copy post link"
                onTriggered: {
                    contextMenu.close()
                    if (galleryMenus.view.bridge) galleryMenus.view.bridge.copyToClipboard(contextMenu.sourceUrl)
                    galleryMenus.view.showToast("Copied post link", false)
                }
            }
            GalleryMenuDivider { visible: contextMenu.single }

            GalleryMenuRow {
                visible: !!galleryMenus.view.tools
                readonly property bool allFav: {
                    var list = galleryMenus.view.contextItems
                    if (!list.length) return false
                    for (var i = 0; i < list.length; i++) if (!galleryMenus.view.isFavorite(list[i])) return false
                    return true
                }
                icon: allFav ? "☆" : "⭐"; label: allFav ? "Remove from favourites" : "Add to favourites"; hint: "Ctrl+D"
                onTriggered: { contextMenu.close(); galleryMenus.view.toggleFavorite(galleryMenus.view.contextItems) }
            }
            GalleryRatingRow {
                visible: !!galleryMenus.view.tools
                current: galleryMenus.view.contextItems.length === 1 ? galleryMenus.view.ratingOf(galleryMenus.view.contextItems[0]) : 0
                onRated: (n) => { contextMenu.close(); galleryMenus.view.setRating(galleryMenus.view.contextItems, n) }
            }
            GalleryMenuDivider { visible: !!galleryMenus.view.tools }
            GalleryMenuRow {
                icon: "📋"; label: contextMenu.single ? "Copy path" : ("Copy " + galleryMenus.view.contextItems.length + " paths")
                onTriggered: { contextMenu.close(); galleryMenus.view.copyPaths(galleryMenus.view.contextItems) }
            }
            GalleryMenuRow {
                visible: contextMenu.single
                icon: "✏️"; label: "Rename…"; hint: "F2"
                onTriggered: { contextMenu.close(); galleryMenus.view.renameItem(contextMenu.first) }
            }
            GalleryMenuRow {
                icon: "📦"; label: "Move to folder…"
                onTriggered: { contextMenu.close(); galleryMenus.view.moveItemsToFolder(galleryMenus.view.contextItems) }
            }
            GalleryMenuRow {
                visible: !!galleryMenus.view.archiver
                icon: "📋"; label: "Copy to folder…"
                onTriggered: { contextMenu.close(); galleryMenus.view.copyItemsToFolder(galleryMenus.view.contextItems) }
            }
            GalleryMenuDivider { visible: !!galleryMenus.view.archiver }
            GalleryMenuRow {
                visible: !!galleryMenus.view.archiver && contextMenu.single && galleryMenus.view.isArchive(contextMenu.first)
                icon: "🔍"; label: "Look inside"
                hint: "double-click"
                onTriggered: { contextMenu.close(); galleryMenus.view.openArchiveViewer(contextMenu.first) }
            }
            GalleryMenuRow {
                readonly property int arcCount: galleryMenus.view.archivesIn(galleryMenus.view.contextItems).length
                visible: !!galleryMenus.view.archiver && arcCount > 0
                icon: "📂"; label: arcCount > 1 ? ("Extract " + arcCount + " archives here") : "Extract here"
                hint: "own folder"
                onTriggered: { contextMenu.close(); galleryMenus.view.extractItems(galleryMenus.view.contextItems, true) }
            }
            GalleryMenuRow {
                visible: !!galleryMenus.view.archiver && galleryMenus.view.archivesIn(galleryMenus.view.contextItems).length > 0
                icon: "📂"; label: "Extract…"
                onTriggered: { contextMenu.close(); galleryMenus.view.extractItems(galleryMenus.view.contextItems, false) }
            }
            GalleryMenuRow {
                visible: !!galleryMenus.view.archiver
                icon: "🗜️"; label: contextMenu.single ? "Compress…" : ("Compress " + galleryMenus.view.contextItems.length + " items…")
                onTriggered: { contextMenu.close(); galleryMenus.view.compressItems(galleryMenus.view.contextItems) }
            }
            GalleryMenuRow {
                objectName: "galleryCompressMedia"
                visible: contextMenu.compressible.length > 0
                icon: "📉"
                label: contextMenu.compressible.length === 1
                       ? galleryMenus.view.mediaTr("gc_menu_one", "Compress picture / video…")
                       : galleryMenus.view.mediaTr("gc_menu_many", "Compress %1 pictures & videos…").replace("%1", contextMenu.compressible.length)
                hint: galleryMenus.view.mediaTr("gc_menu_hint", "smaller files")
                onTriggered: { contextMenu.close(); galleryMenus.view.compressMedia(contextMenu.compressible) }
            }
            GalleryMenuDivider {}
            GalleryMenuRow {
                icon: "🗑️"; label: "Move to Recycle Bin"; hint: "Del"; danger: true
                onTriggered: { contextMenu.close(); galleryMenus.view.deleteItems(galleryMenus.view.contextItems) }
            }
            GalleryMenuDivider {}
            GalleryMenuRow {
                icon: "☑"; label: "Select all"; hint: "Ctrl+A"
                onTriggered: { contextMenu.close(); galleryMenus.view.selectAll() }
            }
            GalleryMenuRow {
                visible: galleryMenus.view.selectionCount > 0
                icon: "✕"; label: "Clear selection"; hint: "Esc"
                onTriggered: { contextMenu.close(); galleryMenus.view.clearSelection() }
            }
            GalleryMenuRow {
                visible: !!galleryMenus.view.tools && galleryMenus.view.tools.canUndo
                icon: "↶"; label: galleryMenus.view.tools ? galleryMenus.view.tools.undoLabel : ""; hint: "Ctrl+Z"
                onTriggered: { contextMenu.close(); galleryMenus.view.undoLast() }
            }
        }
    }

    // ── Character / series menu ────────────────────────────────────────────
    Popup {
        id: charMenu
        // Springs open from its anchor, eases away
        transformOrigin: Popup.TopLeft
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 5.5; damping: 0.28; mass: 0.7; epsilon: 0.001 }
            }
        }
        exit: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: 110 }
                NumberAnimation { property: "scale"; to: 0.94; duration: 110; easing.type: Easing.InCubic }
            }
        }
        width: 260
        padding: 4
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: "#121725"; radius: 7; border.color: "#2B354C"; border.width: 1 }
        // Filled when the menu opens (not bound to 'visible': closing must not destroy the
        // row whose click handler is still running)
        property var entries: []
        onAboutToShow: entries = galleryMenus.view.characterCounts()

        contentItem: Column {
            spacing: 0
            Text {
                width: parent.width
                leftPadding: 8; topPadding: 4; bottomPadding: 4
                text: "CHARACTERS & SERIES HERE"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                font.weight: 700
                color: "#64748B"
            }
            GalleryMenuRow {
                visible: galleryMenus.view.characterFilter.length > 0
                icon: "✕"; label: "Clear filter"
                onTriggered: { charMenu.close(); galleryMenus.view.setCharacterFilter("") }
            }
            // Tagging Progress & Cancel Container
            Rectangle {
                visible: galleryMenus.view.tagging
                width: parent.width
                implicitHeight: tagMenuProgCol.implicitHeight + 14
                radius: 6
                color: "#182030"
                border.color: "#2C3D5A"
                border.width: 1

                ColumnLayout {
                    id: tagMenuProgCol
                    anchors.fill: parent
                    anchors.margins: 6
                    spacing: 5

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: "⏳"
                            font.pixelSize: 11
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Text {
                            Layout.fillWidth: true
                            text: galleryMenus.view.taggingTotal > 0
                                  ? ("Scanning " + galleryMenus.view.taggingCurrent + "/" + galleryMenus.view.taggingTotal + " (" + Math.round(galleryMenus.view.taggingProgress * 100) + "%)")
                                  : "Scanning names…"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: "#38BDF8"
                            elide: Text.ElideRight
                        }

                        // Cancel button inside menu
                        Rectangle {
                            id: cancelTagBtn
                            implicitWidth: cancelTagText.implicitWidth + 12
                            height: 20
                            radius: 4
                            color: cancelTagMouse.containsMouse ? "#7F1D1D" : "#3B181E"
                            border.color: cancelTagMouse.containsMouse ? "#F87171" : "#EF4444"
                            border.width: 1
                            scale: cancelTagMouse.pressed ? 0.92 : (cancelTagMouse.containsMouse ? 1.05 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                            Text {
                                id: cancelTagText
                                anchors.centerIn: parent
                                text: "✕ Stop"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                color: "#FCA5A5"
                            }

                            MouseArea {
                                id: cancelTagMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Stop scanning and unload AI model from VRAM"
                                onClicked: galleryMenus.view.cancelTagging()
                            }
                        }
                    }

                    // Progress bar
                    Rectangle {
                        Layout.fillWidth: true
                        height: 4
                        radius: 2
                        color: "#0F1420"

                        Rectangle {
                            height: parent.height
                            radius: 2
                            width: Math.max(0, Math.min(parent.width, parent.width * galleryMenus.view.taggingProgress))
                            color: "#38BDF8"
                            Behavior on width { NumberAnimation { duration: 100 } }
                        }
                    }
                }
            }

            // Free AI model from VRAM row (when not actively scanning and AI model is loaded)
            GalleryMenuRow {
                visible: !galleryMenus.view.tagging && galleryMenus.view.tools && galleryMenus.view.tools.isAiModelLoaded
                icon: "🧹"
                label: "Free AI model from VRAM"
                onTriggered: {
                    if (galleryMenus.view.tools) galleryMenus.view.tools.unloadAiModel()
                    galleryMenus.view.showToast("AI model unloaded from VRAM", false)
                }
            }
            Text {
                visible: !galleryMenus.view.tagging && charMenu.entries.length === 0
                width: parent.width
                leftPadding: 8; rightPadding: 8; topPadding: 6; bottomPadding: 6
                text: "No known characters or series found in these file names. Add names in the Known Series tab."
                font.pixelSize: 10
                color: "#94A3B8"
                wrapMode: Text.WordWrap
            }
            ListView {
                width: parent.width
                height: Math.min(360, charMenu.entries.length * 26)
                visible: charMenu.entries.length > 0
                clip: true
                model: charMenu.entries
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: GalleryMenuRow {
                    width: ListView.view ? ListView.view.width : 240
                    icon: "👤"
                    label: modelData.name
                    hint: modelData.count + (modelData.count === 1 ? " file" : " files")
                    checked: galleryMenus.view.characterFilter.toLowerCase() === modelData.name.toLowerCase()
                    onTriggered: {
                        var picked = modelData.name
                        galleryMenus.view.setCharacterFilter(picked)
                        charMenu.close()
                    }
                }
            }
        }
    }

    // ── View options menu ──────────────────────────────────────────────────
    Popup {
        id: viewMenu
        // Springs open from its anchor, eases away
        transformOrigin: Popup.TopRight
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 5.5; damping: 0.28; mass: 0.7; epsilon: 0.001 }
            }
        }
        exit: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: 110 }
                NumberAnimation { property: "scale"; to: 0.94; duration: 110; easing.type: Easing.InCubic }
            }
        }
        width: 268
        padding: 4
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: "#121725"; radius: 7; border.color: "#2B354C"; border.width: 1 }

        contentItem: Column {
            spacing: 0
            Text {
                width: parent.width
                leftPadding: 8; topPadding: 4; bottomPadding: 4
                text: "SHOW"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                font.weight: 700
                color: "#64748B"
            }
            GalleryMenuRow {
                icon: galleryMenus.view.showFolderPreviews ? "☑" : "☐"
                label: "Folder previews"
                checked: galleryMenus.view.showFolderPreviews
                hint: "up to 4 thumbs"
                onTriggered: galleryMenus.view.showFolderPreviews = !galleryMenus.view.showFolderPreviews
            }
            GalleryMenuRow {
                icon: galleryMenus.view.cleanThumbCards ? "☑" : "☐"
                label: "Clean thumbnails"
                checked: galleryMenus.view.cleanThumbCards
                hint: "badges on hover"
                onTriggered: galleryMenus.view.cleanThumbCards = !galleryMenus.view.cleanThumbCards
            }
            GalleryMenuRow {
                icon: galleryMenus.view.showPathBar ? "☑" : "☐"
                label: "Path bar"
                checked: galleryMenus.view.showPathBar
                hint: "Up, Refresh, Bookmark"
                onTriggered: galleryMenus.view.showPathBar = !galleryMenus.view.showPathBar
            }
            GalleryMenuRow {
                icon: galleryMenus.view.showShortcutsBar ? "☑" : "☐"
                label: "Shortcuts bar"
                checked: galleryMenus.view.showShortcutsBar
                hint: galleryMenus.view.shortcutChips.length === 0 ? "no shortcuts yet" : ""
                onTriggered: galleryMenus.view.showShortcutsBar = !galleryMenus.view.showShortcutsBar
            }
            GalleryMenuDivider {}
            Text {
                width: parent.width
                leftPadding: 8; topPadding: 4; bottomPadding: 4
                text: "THUMBNAIL FIT"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                font.weight: 700
                color: "#64748B"
            }
            GalleryMenuRow {
                icon: galleryMenus.view.thumbFitMode === "fit" ? "●" : "○"
                label: "Fit whole image"
                checked: galleryMenus.view.thumbFitMode === "fit"
                hint: "Explorer style"
                onTriggered: galleryMenus.view.thumbFitMode = "fit"
            }
            GalleryMenuRow {
                icon: galleryMenus.view.thumbFitMode === "crop" ? "●" : "○"
                label: "Fill frame (crop)"
                checked: galleryMenus.view.thumbFitMode === "crop"
                hint: "edge to edge"
                onTriggered: galleryMenus.view.thumbFitMode = "crop"
            }
            GalleryMenuDivider {}
            Text {
                width: parent.width
                leftPadding: 8; topPadding: 4; bottomPadding: 4
                text: "FRAME RATIO"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                font.weight: 700
                color: "#64748B"
            }
            GalleryMenuRow {
                icon: galleryMenus.view.thumbAspect === "square" ? "●" : "○"
                label: "1:1 Square"
                checked: galleryMenus.view.thumbAspect === "square"
                hint: "Explorer"
                onTriggered: galleryMenus.view.thumbAspect = "square"
            }
            GalleryMenuRow {
                icon: galleryMenus.view.thumbAspect === "landscape" ? "●" : "○"
                label: "16:10 Landscape"
                checked: galleryMenus.view.thumbAspect === "landscape"
                hint: "wide"
                onTriggered: galleryMenus.view.thumbAspect = "landscape"
            }
            GalleryMenuRow {
                icon: galleryMenus.view.thumbAspect === "portrait" ? "●" : "○"
                label: "3:4 Portrait"
                checked: galleryMenus.view.thumbAspect === "portrait"
                hint: "tall"
                onTriggered: galleryMenus.view.thumbAspect = "portrait"
            }
            GalleryMenuDivider {}
            GalleryMenuRow {
                icon: "📊"
                label: "Storage…"
                hint: "what takes up space"
                enabled: !!galleryMenus.view.tools && !galleryMenus.view.inFavorites
                onTriggered: { viewMenu.close(); galleryMenus.view.openStorage() }
            }
            GalleryMenuRow {
                icon: galleryMenus.view.privacyBlur ? "☑" : "☐"
                label: "Privacy blur"
                checked: galleryMenus.view.privacyBlur
                hint: "Ctrl+H"
                onTriggered: { viewMenu.close(); galleryMenus.view.togglePrivacy() }
            }
            GalleryMenuDivider {}
            Text {
                width: parent.width
                leftPadding: 8; rightPadding: 8; topPadding: 2; bottomPadding: 4
                text: galleryMenus.view.showPathBar ? "Hidden bars can be brought back here." : "Path bar hidden: Backspace still goes up a folder."
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                color: "#64748B"
                wrapMode: Text.WordWrap
            }
        }
    }

    // ── Selection bar "More" menu ──────────────────────────────────────────
    function openMoreMenu(anchorItem) {
        var items = galleryMenus.view.selectedItems()
        moreMenu.items = items
        moreMenu.sourceUrl = (galleryMenus.view.tools && items.length === 1 && !items[0].is_dir) ? (galleryMenus.view.tools.sourcePost(items[0].path).url || "") : ""
        var p = anchorItem.mapToItem(galleryMenus.view, anchorItem.width - moreMenu.width, anchorItem.height + 4)
        moreMenu.x = Math.max(4, Math.min(p.x, galleryMenus.view.width - moreMenu.width - 4))
        moreMenu.y = p.y
        moreMenu.open()
    }

    Popup {
        id: moreMenu
        // Springs open from its anchor, eases away
        transformOrigin: Popup.TopRight
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 5.5; damping: 0.28; mass: 0.7; epsilon: 0.001 }
            }
        }
        exit: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: 110 }
                NumberAnimation { property: "scale"; to: 0.94; duration: 110; easing.type: Easing.InCubic }
            }
        }
        property var items: []
        property string sourceUrl: ""
        readonly property bool single: items.length === 1
        readonly property var first: items.length > 0 ? items[0] : null
        width: 230
        padding: 4
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: "#121725"; radius: 7; border.color: "#2B354C"; border.width: 1 }

        contentItem: Column {
            spacing: 0
            GalleryMenuRow {
                visible: moreMenu.single
                icon: "↗"; label: "Open"; hint: "Enter"
                onTriggered: { moreMenu.close(); galleryMenus.view.openItem(moreMenu.first) }
            }
            GalleryMenuRow {
                visible: moreMenu.single
                icon: "📂"; label: "Show in File Explorer"
                onTriggered: { moreMenu.close(); galleryMenus.view.revealItem(moreMenu.first) }
            }
            GalleryMenuRow {
                visible: moreMenu.sourceUrl.length > 0
                icon: "🌐"; label: "View source post"
                onTriggered: { moreMenu.close(); Qt.openUrlExternally(moreMenu.sourceUrl) }
            }
            GalleryMenuDivider { visible: moreMenu.single }
            GalleryMenuRow {
                visible: !!galleryMenus.view.tools
                readonly property bool allFav: {
                    var list = moreMenu.items
                    if (!list.length) return false
                    for (var i = 0; i < list.length; i++) if (!galleryMenus.view.isFavorite(list[i])) return false
                    return true
                }
                icon: allFav ? "☆" : "⭐"; label: allFav ? "Remove from favourites" : "Add to favourites"; hint: "Ctrl+D"
                onTriggered: { moreMenu.close(); galleryMenus.view.toggleFavorite(moreMenu.items) }
            }
            GalleryRatingRow {
                visible: !!galleryMenus.view.tools
                current: moreMenu.items.length === 1 ? galleryMenus.view.ratingOf(moreMenu.items[0]) : 0
                onRated: (n) => { moreMenu.close(); galleryMenus.view.setRating(moreMenu.items, n) }
            }
            GalleryMenuDivider { visible: !!galleryMenus.view.tools }
            GalleryMenuRow {
                icon: "📋"; label: moreMenu.single ? "Copy path" : ("Copy " + moreMenu.items.length + " paths")
                onTriggered: { moreMenu.close(); galleryMenus.view.copyPaths(moreMenu.items) }
            }
            GalleryMenuRow {
                visible: moreMenu.single
                icon: "✏️"; label: "Rename…"; hint: "F2"
                onTriggered: { moreMenu.close(); galleryMenus.view.renameItem(moreMenu.first) }
            }
            GalleryMenuDivider {}
            GalleryMenuRow {
                icon: "☑"; label: "Select all"; hint: "Ctrl+A"
                onTriggered: { moreMenu.close(); galleryMenus.view.selectAll() }
            }
            GalleryMenuRow {
                icon: "✕"; label: "Clear selection"; hint: "Esc"
                onTriggered: { moreMenu.close(); galleryMenus.view.clearSelection() }
            }
        }
    }

    // ── Sort menu ───────────────────────────────────────────────────────────
    Popup {
        id: sortMenu
        // Springs open from its anchor, eases away
        transformOrigin: Popup.TopLeft
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140; easing.type: Easing.OutCubic }
                SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 5.5; damping: 0.28; mass: 0.7; epsilon: 0.001 }
            }
        }
        exit: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: 110 }
                NumberAnimation { property: "scale"; to: 0.94; duration: 110; easing.type: Easing.InCubic }
            }
        }
        width: 190
        padding: 4
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: "#121725"
            radius: 7
            border.color: "#2B354C"
            border.width: 1
        }

        contentItem: Column {
            spacing: 0
            Repeater {
                model: [
                    { key: "name", icon: "🔤", label: "Name" },
                    { key: "date", icon: "🕒", label: "Date modified" },
                    { key: "size", icon: "📏", label: "Size" },
                    { key: "type", icon: "🏷️", label: "Type" },
                    { key: "rating", icon: "★", label: "Rating" }
                ]
                delegate: GalleryMenuRow {
                    width: sortMenu.availableWidth
                    icon: modelData.icon
                    label: modelData.label
                    checked: galleryMenus.view.sortKey === modelData.key
                    hint: checked ? (galleryMenus.view.sortAscending ? "▲" : "▼") : ""
                    onTriggered: {
                        if (galleryMenus.view.sortKey !== modelData.key) galleryMenus.view.sortBy(modelData.key)
                        sortMenu.close()
                    }
                }
            }
            GalleryMenuDivider { width: sortMenu.availableWidth }
            GalleryMenuRow {
                width: sortMenu.availableWidth
                icon: "▲"; label: "Ascending"
                checked: galleryMenus.view.sortAscending
                onTriggered: { if (!galleryMenus.view.sortAscending) { galleryMenus.view.sortAscending = true; galleryMenus.view.resort() } sortMenu.close() }
            }
            GalleryMenuRow {
                width: sortMenu.availableWidth
                icon: "▼"; label: "Descending"
                checked: !galleryMenus.view.sortAscending
                onTriggered: { if (galleryMenus.view.sortAscending) { galleryMenus.view.sortAscending = false; galleryMenus.view.resort() } sortMenu.close() }
            }
        }
    }
}
