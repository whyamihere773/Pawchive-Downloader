import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

ColumnLayout {
    id: pathShortcutsBar
    required property var view
    Layout.fillWidth: true
    spacing: 8

    Rectangle {
        Layout.fillWidth: true
        readonly property bool shown: pathShortcutsBar.view.showPathBar
        property real reveal: shown ? 1 : 0
        Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
        implicitHeight: 32
        Layout.preferredHeight: 32 * Math.max(0, reveal)
        visible: reveal > 0.01
        opacity: Math.max(0, Math.min(1, reveal))
        clip: true
        radius: 6
        color: "#121622"
        border.color: "#232A3B"
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            spacing: 6

            // Back / Forward (Alt+← / Alt+→, mouse side buttons)
            Repeater {
                model: [ { dir: -1, glyph: "◀", tip: "Back (Alt+←)" }, { dir: 1, glyph: "▶", tip: "Forward (Alt+→)" } ]
                delegate: Rectangle {
                    readonly property bool can: modelData.dir < 0 ? pathShortcutsBar.view.backStack.length > 0 : pathShortcutsBar.view.forwardStack.length > 0
                    width: 24
                    height: 24
                    radius: 4
                    color: (histMouse.containsMouse && can) ? "#1E273A" : "#161B29"
                    border.color: (histMouse.containsMouse && can) ? "#38BDF8" : "#2B354C"
                    border.width: 1
                    opacity: can ? 1.0 : 0.4
                    Text { anchors.centerIn: parent; text: modelData.glyph; font.pixelSize: 9; color: "#E2E8F0" }
                    Springy { hover: histMouse.containsMouse; pressed: histMouse.pressed }
                    MouseArea {
                        id: histMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: parent.can ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: if (parent.can) { if (modelData.dir < 0) pathShortcutsBar.view.goBack(); else pathShortcutsBar.view.goForward() }
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: modelData.tip
                    }
                }
            }

            // Parent directory button
            Rectangle {
                width: 24
                height: 24
                radius: 4
                color: (upBtnMouse.containsMouse && pathShortcutsBar.view.breadcrumbs.length > 1) ? "#1E273A" : "#161B29"
                border.color: (upBtnMouse.containsMouse && pathShortcutsBar.view.breadcrumbs.length > 1) ? "#38BDF8" : "#2B354C"
                border.width: 1
                opacity: pathShortcutsBar.view.breadcrumbs.length > 1 ? 1.0 : 0.4

                Text {
                    anchors.centerIn: parent
                    text: "⬆"
                    font.pixelSize: 11
                    color: "#E2E8F0"
                }
                Springy { hover: upBtnMouse.containsMouse; pressed: upBtnMouse.pressed }
                MouseArea {
                    id: upBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: pathShortcutsBar.view.breadcrumbs.length > 1 ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: pathShortcutsBar.view.navigateUp()
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: pathShortcutsBar.view.breadcrumbs.length > 1 ? ("Go up to: " + (pathShortcutsBar.view.breadcrumbs.length >= 2 ? pathShortcutsBar.view.breadcrumbs[pathShortcutsBar.view.breadcrumbs.length - 2].path : "parent directory")) : "Already at root level"
                }
            }

            // Breadcrumbs strip (scrolls; jumps to the current folder on navigation)
            GalleryHScrollStrip {
                id: crumbStrip
                Layout.fillWidth: true
                implicitHeight: 24
                contentWidth: crumbRow.implicitWidth
                arrowColor: "#161B29"
                onMaxXChanged: scrollToEnd()

                Row {
                    id: crumbRow
                    spacing: 4
                    anchors.verticalCenter: parent.verticalCenter

                    Repeater {
                        model: pathShortcutsBar.view.breadcrumbs
                        delegate: Row {
                            spacing: 4
                            anchors.verticalCenter: parent.verticalCenter

                            Rectangle {
                                implicitHeight: 22
                                implicitWidth: crumbText.implicitWidth + 10
                                radius: 4
                                color: (crumbMouse.containsMouse || index === (pathShortcutsBar.view.breadcrumbs.length - 1)) ? "#1E293D" : "transparent"
                                border.color: index === (pathShortcutsBar.view.breadcrumbs.length - 1) ? "#38BDF8" : "transparent"
                                border.width: 1

                                Text {
                                    id: crumbText
                                    anchors.centerIn: parent
                                    text: modelData.name || ""
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: index === (pathShortcutsBar.view.breadcrumbs.length - 1) ? 700 : Font.Normal
                                    color: index === (pathShortcutsBar.view.breadcrumbs.length - 1) ? "#F8FAFC" : "#94A3B8"
                                }
                                Springy { hover: crumbMouse.containsMouse; pressed: crumbMouse.pressed }
                                MouseArea {
                                    id: crumbMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: pathShortcutsBar.view.navigateTo(modelData.path)
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 250
                                    ToolTip.text: "Navigate to " + modelData.path
                                }
                            }

                            Text {
                                visible: index < (pathShortcutsBar.view.breadcrumbs.length - 1)
                                text: "›"
                                font.pixelSize: 11
                                color: "#475569"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }
                }
            }

            // Refresh this folder (path bar, like File Explorer)
            Rectangle {
                width: 24
                height: 24
                radius: 5
                color: refBtnMouse.containsMouse ? "#1E293B" : "#141720"
                border.color: refBtnMouse.containsMouse ? "#38BDF8" : "#2E384D"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "🔄"
                    font.pixelSize: 11
                }
                Springy { hover: refBtnMouse.containsMouse; pressed: refBtnMouse.pressed }
                MouseArea {
                    id: refBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (pathShortcutsBar.view.bridge && pathShortcutsBar.view.bridge.invalidateFolderCache) {
                            pathShortcutsBar.view.bridge.invalidateFolderCache(pathShortcutsBar.view.currentPath)
                        }
                        pathShortcutsBar.view.navigateTo(pathShortcutsBar.view.currentPath)
                    }
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Refresh current directory contents"
                }
            }

            // Check for new posts from the creator of this folder
            Rectangle {
                visible: !!pathShortcutsBar.view.updates && !pathShortcutsBar.view.inFavorites && (!!pathShortcutsBar.view.creatorInfo.found || !!pathShortcutsBar.view.creatorInfo.maybe)
                implicitHeight: 24
                implicitWidth: updRow.implicitWidth + 14
                radius: 12
                color: updMouse.containsMouse ? "#12324A" : "#0F2A3A"
                border.color: "#38BDF8"
                border.width: 1
                Row {
                    id: updRow
                    anchors.centerIn: parent
                    spacing: 4
                    Text { text: "🔄"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "Check for new posts"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 700
                        color: "#7DD3FC"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                Springy { hover: updMouse.containsMouse; pressed: updMouse.pressed }
                MouseArea {
                    id: updMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: pathShortcutsBar.view.checkForNewPosts()
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: pathShortcutsBar.view.creatorInfo.found
                        ? ("See if " + (pathShortcutsBar.view.creatorInfo.name || "this creator") + " posted anything you don't have yet,\nand download it straight into this folder.")
                        : "See if this creator posted anything you don't have yet.\n(You'll be asked for the creator's link once.)"
                }
            }

            // Star / Pin Current Folder Button (not for the virtual Favourites list)
            Rectangle {
                visible: !pathShortcutsBar.view.inFavorites
                implicitHeight: 24
                implicitWidth: bkmBtnRow.implicitWidth + 12
                radius: 4
                color: bkmBtnMouse.containsMouse ? "#1E293B" : (pathShortcutsBar.view.isCurrentFolderBookmarked ? "#241D12" : "#141824")
                border.color: pathShortcutsBar.view.isCurrentFolderBookmarked ? "#F59E0B" : (bkmBtnMouse.containsMouse ? "#38BDF8" : "#2E384D")
                border.width: 1

                Row {
                    id: bkmBtnRow
                    anchors.centerIn: parent
                    spacing: 4
                    Text {
                        text: pathShortcutsBar.view.isCurrentFolderBookmarked ? "⭐" : "☆"
                        font.pixelSize: 11
                    }
                    Text {
                        text: pathShortcutsBar.view.isCurrentFolderBookmarked ? "Bookmarked" : "Bookmark"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: pathShortcutsBar.view.isCurrentFolderBookmarked ? "#F59E0B" : "#E2E8F0"
                    }
                }
                Springy { hover: bkmBtnMouse.containsMouse; pressed: bkmBtnMouse.pressed }
                MouseArea {
                    id: bkmBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (!pathShortcutsBar.view.bridge) return
                        if (pathShortcutsBar.view.isCurrentFolderBookmarked) {
                            pathShortcutsBar.view.bridge.removeGalleryBookmark(pathShortcutsBar.view.currentPath)
                        } else {
                            pathShortcutsBar.view.bridge.addGalleryBookmark(pathShortcutsBar.view.currentPath, "")
                        }
                        pathShortcutsBar.view.refreshBookmarks()
                    }
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: pathShortcutsBar.view.isCurrentFolderBookmarked ? ("Bookmarked!\nClick to remove '" + pathShortcutsBar.view.currentPath + "' from Quick Shortcuts") : ("Bookmark Folder\nPin '" + pathShortcutsBar.view.currentPath + "' as a Quick Shortcut")
                }
            }
        }
    }

    // 3. QUICK SHORTCUTS / BOOKMARKS BAR (can be hidden from the view options menu)
    Rectangle {
        Layout.fillWidth: true
        readonly property bool shown: pathShortcutsBar.view.showShortcutsBar
        property real reveal: shown ? 1 : 0
        Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
        implicitHeight: 28
        Layout.preferredHeight: 28 * Math.max(0, reveal)
        visible: reveal > 0.01
        opacity: Math.max(0, Math.min(1, reveal))
        clip: true
        radius: 5
        color: "#0E121B"
        border.color: "#1C2333"
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 8

            // Label
            Row {
                spacing: 4
                Layout.alignment: Qt.AlignVCenter
                Text { text: "🔖"; font.pixelSize: 11 }
                Text {
                    text: "Shortcuts:"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 700
                    color: "#64748B"
                }
            }

            // Favourites: every starred file and folder, from any creator
            Rectangle {
                implicitHeight: 22
                implicitWidth: favChipRow.implicitWidth + 14
                radius: 11
                Layout.alignment: Qt.AlignVCenter
                color: pathShortcutsBar.view.inFavorites ? "#2A2210" : (favChipMouse.containsMouse ? "#1E293D" : "#131722")
                border.color: pathShortcutsBar.view.inFavorites ? "#F59E0B" : (favChipMouse.containsMouse ? "#475569" : "#222B3D")
                border.width: 1
                Row {
                    id: favChipRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text { text: "⭐"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "Favourites"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: pathShortcutsBar.view.inFavorites ? 700 : Font.Normal
                        color: pathShortcutsBar.view.inFavorites ? "#FCD34D" : "#CBD5E1"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                Springy { hover: favChipMouse.containsMouse; pressed: favChipMouse.pressed }
                MouseArea {
                    id: favChipMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: pathShortcutsBar.view.openFavorites()
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Favourites: everything you starred, from any folder (Ctrl+D stars the selection)"
                }
            }
            Rectangle { width: 1; height: 14; color: "#222B3D"; Layout.alignment: Qt.AlignVCenter; visible: pathShortcutsBar.view.shortcutChips.length > 0 }

            // Scrollable row of bookmark chips (wheel, drag, or ‹ › arrows)
            GalleryHScrollStrip {
                Layout.fillWidth: true
                implicitHeight: 24
                contentWidth: bookmarksRow.implicitWidth
                arrowColor: "#131722"

                Row {
                    id: bookmarksRow
                    spacing: 6
                    anchors.verticalCenter: parent.verticalCenter

                    Repeater {
                        model: pathShortcutsBar.view.shortcutChips
                        delegate: Rectangle {
                            id: bChip
                            property var gRoot: pathShortcutsBar.view
                            readonly property bool isSearch: modelData.kind === "search"
                            function removeChip() {
                                if (isSearch) { bChip.gRoot.removeSavedSearch(modelData); return }
                                if (bChip.gRoot && bChip.gRoot.bridge && bChip.gRoot.bridge.removeGalleryBookmark) {
                                    bChip.gRoot.bridge.removeGalleryBookmark(modelData.path)
                                    bChip.gRoot.refreshBookmarks()
                                }
                            }
                            property bool isCurrent: {
                                if (isSearch) return pathShortcutsBar.view.isCurrentSavedSearch(modelData)
                                if (!pathShortcutsBar.view.currentPath || !modelData.path) return false
                                var cp = (pathShortcutsBar.view.currentPath || "").toUpperCase().replace(/\\/g, "/").replace(/\/+$/, "")
                                var mp = (modelData.path || "").toUpperCase().replace(/\\/g, "/").replace(/\/+$/, "")
                                return cp === mp
                            }
                            implicitHeight: 22
                            implicitWidth: bChipRow.implicitWidth + 14
                            radius: 11
                            color: (bChipMouse.containsMouse || bDelMouse.containsMouse) ? "#1E293D" : (isCurrent ? "#1E273A" : "#131722")
                            border.color: isCurrent ? "#38BDF8" : ((bChipMouse.containsMouse || bDelMouse.containsMouse) ? "#475569" : "#222B3D")
                            border.width: 1

                            // Main chip mouse area (declared before bChipRow so delete button sits on top)
                            MouseArea {
                                id: bChipMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                onClicked: (mouse) => {
                                    if (mouse.button === Qt.RightButton) bChip.removeChip()
                                    else if (bChip.isSearch) bChip.gRoot.runSavedSearch(modelData)
                                    else if (bChip.gRoot && bChip.gRoot.navigateTo) bChip.gRoot.navigateTo(modelData.path)
                                }
                                ToolTip.visible: containsMouse && !bDelMouse.containsMouse
                                ToolTip.delay: 300
                                ToolTip.text: bChip.isSearch
                                    ? ("Saved search: \u201c" + modelData.query + "\u201d" + (modelData.recursive ? " (with subfolders)" : "") + "\nin " + modelData.path + "\n• Click to run it\n• Right-click or '×' to remove")
                                    : ("Quick Shortcut: " + (modelData.name || "") + "\n" + (modelData.path || "") + "\n• Left-click to navigate\n• Right-click or '×' to unpin")
                            }

                            Row {
                                id: bChipRow
                                anchors.centerIn: parent
                                spacing: 5

                                Text {
                                    text: modelData.icon || "⭐"
                                    font.pixelSize: 10
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: modelData.name || ""
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: isCurrent ? 700 : Font.Normal
                                    color: isCurrent ? "#38BDF8" : ((bChipMouse.containsMouse || bDelMouse.containsMouse) ? "#F8FAFC" : "#94A3B8")
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                // Remove button (appears on hover)
                                Rectangle {
                                    id: bDelBtn
                                    width: 14
                                    height: 14
                                    radius: 7
                                    color: bDelMouse.containsMouse ? "#EF4444" : "#1E2536"
                                    visible: bChipMouse.containsMouse || bDelMouse.containsMouse
                                    anchors.verticalCenter: parent.verticalCenter

                                    Text {
                                        anchors.centerIn: parent
                                        text: "×"
                                        font.pixelSize: 11
                                        font.bold: true
                                        color: bDelMouse.containsMouse ? "#FFFFFF" : "#E2E8F0"
                                    }

                                    MouseArea {
                                        id: bDelMouse
                                        anchors.fill: parent
                                        anchors.margins: -4
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: bChip.removeChip()
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 200
                                        ToolTip.text: bChip.isSearch ? ("Remove the saved search \u201c" + modelData.query + "\u201d") : ("Remove bookmark '" + (modelData.name || "") + "'")
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
