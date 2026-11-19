import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

RowLayout {
    id: topBar
    required property var view
    Layout.fillWidth: true
    spacing: 8

    // Drive quick selectors with live storage space (scrolls sideways if they don't fit)
    GalleryHScrollStrip {
        Layout.fillWidth: true
        Layout.minimumWidth: 40
        implicitHeight: 26
        contentWidth: drivesRow.implicitWidth

        Row {
            id: drivesRow
            spacing: 6

            Repeater {
                model: topBar.view.drives
                delegate: Rectangle {
                    readonly property bool isCurrentDrive: {
                        if (!topBar.view.currentPath || !modelData.name) return false
                        var cp = topBar.view.currentPath.toUpperCase().replace(/\\/g, "/")
                        var dn = modelData.name.toUpperCase().replace(/\\/g, "/")
                        return cp.indexOf(dn) === 0
                    }

                    implicitHeight: 26
                    implicitWidth: driveRow.implicitWidth + 16
                    radius: 5
                    color: isCurrentDrive ? "#1B283D" : (driveMouse.containsMouse ? "#182030" : "#111520")
                    border.color: isCurrentDrive ? "#38BDF8" : (driveMouse.containsMouse ? "#60A5FA" : "#243046")
                    border.width: 1
                    clip: true

                    Row {
                        id: driveRow
                        anchors.centerIn: parent
                        spacing: 5

                        Text {
                            id: driveNameText
                            text: "💽 " + modelData.name
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 700
                            color: isCurrentDrive ? "#38BDF8" : "#E2E8F0"
                        }

                        // Free / total space, sitting on the same baseline as the drive letter
                        Text {
                            anchors.baseline: driveNameText.baseline
                            visible: !!modelData.space_label && topBar.view.showDriveLabels
                            text: modelData.space_label
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 9
                            color: isCurrentDrive ? "#7DD3FC" : ((modelData.percent_free < 10) ? "#F87171" : "#94A3B8")
                        }
                    }

                    // Storage mini progress bar at bottom
                    Rectangle {
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 1
                        height: 2
                        radius: 1
                        color: "#1E2536"
                        visible: !!modelData.total_bytes && modelData.total_bytes > 0

                        Rectangle {
                            height: parent.height
                            width: Math.min(parent.width, parent.width * Math.max(0.02, 1.0 - (modelData.percent_free || 0) / 100.0))
                            radius: 1
                            color: (modelData.percent_free < 10) ? "#EF4444" : ((modelData.percent_free < 20) ? "#F59E0B" : (isCurrentDrive ? "#38BDF8" : "#64748B"))
                        }
                    }

                    Springy { hover: driveMouse.containsMouse; pressed: driveMouse.pressed }
                    MouseArea {
                        id: driveMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: topBar.view.navigateTo(modelData.path)
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Drive " + (modelData.name || modelData.path) + (modelData.free_str ? ("\n" + modelData.free_str + " free of " + modelData.total_str + " (" + (100 - Math.round(modelData.percent_free)) + "% used)") : "")
                    }
                }
            }
        }
    }

    // Compact Action Buttons on Right
    Row {
        spacing: 5
        Layout.alignment: Qt.AlignVCenter

        // ── Privacy blur: one obvious button (Ctrl+H) ──
        Rectangle {
            id: privacyBtn
            implicitWidth: privacyRow.implicitWidth + 16
            implicitHeight: 26
            radius: 13
            color: topBar.view.privacyBlur ? "#F59E0B" : (privacyMouse.containsMouse ? "#2A2210" : "#1A1710")
            border.color: topBar.view.privacyBlur ? "#FCD34D" : "#F59E0B"
            border.width: 1
            Row {
                id: privacyRow
                anchors.centerIn: parent
                spacing: 5
                Text { text: topBar.view.privacyBlur ? "🙈" : "👁"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: topBar.view.privacyBlur ? "Blurred" : "Privacy"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 700
                    color: topBar.view.privacyBlur ? "#1C1404" : "#FCD34D"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            // "New" dot until the first use
            Rectangle {
                visible: !topBar.view.privacyHintSeen
                width: 9; height: 9; radius: 4.5
                color: "#EF4444"
                border.color: "#0B0E14"; border.width: 1.5
                anchors.right: parent.right; anchors.top: parent.top
                anchors.rightMargin: -2; anchors.topMargin: -2
                SequentialAnimation on scale {
                    running: !topBar.view.privacyHintSeen
                    loops: Animation.Infinite
                    NumberAnimation { to: 1.35; duration: 600; easing.type: Easing.OutCubic }
                    NumberAnimation { to: 1.0; duration: 600; easing.type: Easing.InCubic }
                }
            }
            Springy { hover: privacyMouse.containsMouse; pressed: privacyMouse.pressed }
            MouseArea {
                id: privacyMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: topBar.view.togglePrivacy()
                ToolTip.visible: containsMouse
                ToolTip.delay: 200
                ToolTip.text: topBar.view.privacyBlur
                    ? "Privacy blur is ON: thumbnails and previews are hidden.\nClick or press Ctrl+H to show them again."
                    : "Privacy blur: instantly hide every thumbnail and preview,\nfor when someone walks by. Shortcut: Ctrl+H (works anywhere in the Gallery)."
            }
        }
        GalleryBarDivider {}

        // ── This folder ──
        // Action: New folder
        Rectangle {
            visible: !!topBar.view.tools
            implicitWidth: newFolderRow.implicitWidth + 12
            implicitHeight: 26
            radius: 5
            color: newFolderMouse.containsMouse ? "#1E293B" : "#141720"
            border.color: newFolderMouse.containsMouse ? "#38BDF8" : "#2E384D"
            border.width: 1
            Row {
                id: newFolderRow
                anchors.centerIn: parent
                spacing: 4
                Item {
                    width: 15
                    height: 14
                    anchors.verticalCenter: parent.verticalCenter
                    Text { anchors.centerIn: parent; text: "📁"; font.pixelSize: 11 }
                    Text { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.rightMargin: -2; anchors.bottomMargin: -3; text: "+"; font.pixelSize: 10; font.weight: 800; color: "#34D399" }
                }
                Text {
                    visible: topBar.view.showActionLabels
                    anchors.verticalCenter: parent.verticalCenter
                    text: "New folder"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: "#E2E8F0"
                }
            }
            Springy { hover: newFolderMouse.containsMouse; pressed: newFolderMouse.pressed }
            MouseArea {
                id: newFolderMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: topBar.view.newFolder()
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: "New folder (Ctrl+Shift+N)"
            }
        }

        // Action: Open in OS Explorer
        Rectangle {
            implicitHeight: 26
            implicitWidth: openBtnRow.implicitWidth + 12
            radius: 5
            color: openBtnMouse.containsMouse ? "#1E293B" : "#141720"
            border.color: openBtnMouse.containsMouse ? "#38BDF8" : "#2E384D"
            border.width: 1

            Row {
                id: openBtnRow
                anchors.centerIn: parent
                spacing: 4
                Text { text: "📂"; font.pixelSize: 11 }
                Text {
                    text: topBar.view.tr("gallery_btn_open_system", "Open in Explorer")
                    visible: topBar.view.showActionLabels
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: "#E2E8F0"
                }
            }
            Springy { hover: openBtnMouse.containsMouse; pressed: openBtnMouse.pressed }
            MouseArea {
                id: openBtnMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (topBar.view.bridge && topBar.view.bridge.openFolder) {
                        if (topBar.view.inFavorites) topBar.view.showToast("Favourites isn't a real folder: right-click a file → Show in File Explorer", true)
                        else topBar.view.bridge.openFolder(topBar.view.currentPath)
                    }
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "Open current folder in File Explorer / OS file manager"
            }
        }

        // ── group divider ──
        Rectangle { width: 1; height: 18; color: "#2A3A52"; anchors.verticalCenter: parent.verticalCenter }

        // ── Tools ──
        // Action: Smart Batch Renamer
        Rectangle {
            implicitHeight: 26
            implicitWidth: renameBtnRow.implicitWidth + 12
            radius: 5
            color: topBar.view.isCurrentPathBlocked ? "#161922" : (renameBtnMouse.containsMouse ? "#1E293D" : "#141720")
            border.color: topBar.view.isCurrentPathBlocked ? "#283042" : (topBar.view.isCurrentPathOtherRoot ? "#F59E0B" : (renameBtnMouse.containsMouse ? "#F59E0B" : "#2E384D"))
            border.width: 1
            opacity: topBar.view.isCurrentPathBlocked ? 0.38 : 1.0

            Row {
                id: renameBtnRow
                anchors.centerIn: parent
                spacing: 4
                Text { text: "🏷️"; font.pixelSize: 11 }
                Text {
                    text: "Batch Rename"
                    visible: topBar.view.showActionLabels
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: topBar.view.isCurrentPathBlocked ? "#64748B" : "#E2E8F0"
                }
            }
            Springy { hover: renameBtnMouse.containsMouse; pressed: renameBtnMouse.pressed }
            MouseArea {
                id: renameBtnMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: topBar.view.isCurrentPathBlocked ? Qt.ForbiddenCursor : Qt.PointingHandCursor
                onClicked: {
                    topBar.view.requestSafeAction("Batch Rename", function() {
                        topBar.view.openBatchRename()
                    })
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: topBar.view.isCurrentPathBlocked ?
                    ("🛡️ Operation Disabled on Protected Path\n" + (topBar.view.currentPathSafety && topBar.view.currentPathSafety.message ? topBar.view.currentPathSafety.message : "Operations on this system or protected path are permanently disabled.")) :
                    (topBar.view.isCurrentPathOtherRoot ?
                        ("⚠️ Root Drive Selected (" + (topBar.view.currentPathSafety ? topBar.view.currentPathSafety.drive_letter : "") + "\\)\nBatch Rename on root drives requires double-confirmation.") :
                        "Smart Batch Renamer\nBulk rename and organize files with metadata variables, sequential numbering, and flattening")
            }
        }

        // Action: Cleaner & Deduplicator
        Rectangle {
            implicitHeight: 26
            implicitWidth: cleanBtnRow.implicitWidth + 12
            radius: 5
            color: topBar.view.isCurrentPathBlocked ? "#161922" : (cleanBtnMouse.containsMouse ? "#1E293D" : "#141720")
            border.color: topBar.view.isCurrentPathBlocked ? "#283042" : (topBar.view.isCurrentPathOtherRoot ? "#F59E0B" : (cleanBtnMouse.containsMouse ? "#10B981" : "#2E384D"))
            border.width: 1
            opacity: topBar.view.isCurrentPathBlocked ? 0.38 : 1.0

            Row {
                id: cleanBtnRow
                anchors.centerIn: parent
                spacing: 4
                Text { text: "🧹"; font.pixelSize: 11 }
                Text {
                    text: "Clean & Organize"
                    visible: topBar.view.showActionLabels
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: topBar.view.isCurrentPathBlocked ? "#64748B" : "#E2E8F0"
                }
            }
            Springy { hover: cleanBtnMouse.containsMouse; pressed: cleanBtnMouse.pressed }
            MouseArea {
                id: cleanBtnMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: topBar.view.isCurrentPathBlocked ? Qt.ForbiddenCursor : Qt.PointingHandCursor
                onClicked: {
                    topBar.view.requestSafeAction("Clean & Organize", function() {
                        topBar.view.openGalleryCleaner()
                    })
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: topBar.view.isCurrentPathBlocked ?
                    ("🛡️ Operation Disabled on Protected Path\n" + (topBar.view.currentPathSafety && topBar.view.currentPathSafety.message ? topBar.view.currentPathSafety.message : "Operations on this system or protected path are permanently disabled.")) :
                    (topBar.view.isCurrentPathOtherRoot ?
                        ("⚠️ Root Drive Selected (" + (topBar.view.currentPathSafety ? topBar.view.currentPathSafety.drive_letter : "") + "\\)\nClean & Organize on root drives requires double-confirmation.") :
                        "Clean & Organize\nFind 0-byte broken files, detect duplicate downloads by SHA-256 hash, and auto-sort media into folders")
            }
        }

        // Action: Visual & Local AI Sorter (Virtual-First -> Commit to Disk)
        Rectangle {
            implicitHeight: 26
            implicitWidth: visualSortBtnRow.implicitWidth + 12
            radius: 5
            color: topBar.view.isCurrentPathBlocked ? "#161922" : (visualSortBtnMouse.containsMouse ? "#2E1065" : "#1A1430")
            border.color: topBar.view.isCurrentPathBlocked ? "#283042" : (visualSortBtnMouse.containsMouse ? "#C4B5FD" : "#7C3AED")
            border.width: 1
            opacity: topBar.view.isCurrentPathBlocked ? 0.38 : 1.0

            Row {
                id: visualSortBtnRow
                anchors.centerIn: parent
                spacing: 4
                Text { text: "✨"; font.pixelSize: 11 }
                Text {
                    text: "Visual Sort"
                    visible: topBar.view.showActionLabels
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: topBar.view.isCurrentPathBlocked ? "#64748B" : "#EDE9FE"
                }
            }
            Springy { hover: visualSortBtnMouse.containsMouse; pressed: visualSortBtnMouse.pressed }
            MouseArea {
                id: visualSortBtnMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: topBar.view.isCurrentPathBlocked ? Qt.ForbiddenCursor : Qt.PointingHandCursor
                onClicked: {
                    topBar.view.requestSafeAction("Visual Sort", function() {
                        topBar.view.openVisualSorter()
                    })
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: "Visual & Local AI Sorter (Virtual Sandbox)\nGroup media by visual style, resolution, color mood, character tags, or custom AI prompt — preview buckets in memory before moving anything on disk"
            }
        }

        // Action: Refresh Post Metadata
        Rectangle {
            implicitHeight: 26
            implicitWidth: refreshMetaBtnRow.implicitWidth + 12
            radius: 5
            color: topBar.view.isCurrentPathBlocked ? "#161922" : (refreshMetaBtnMouse.containsMouse ? "#1E293D" : "#141720")
            border.color: topBar.view.isCurrentPathBlocked ? "#283042" : (refreshMetaBtnMouse.containsMouse ? "#38BDF8" : "#2E384D")
            border.width: 1
            opacity: topBar.view.isCurrentPathBlocked ? 0.38 : 1.0

            Row {
                id: refreshMetaBtnRow
                anchors.centerIn: parent
                spacing: 4
                Text { text: "🔄"; font.pixelSize: 11 }
                Text {
                    text: "Refresh Metadata"
                    visible: topBar.view.showActionLabels
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: topBar.view.isCurrentPathBlocked ? "#64748B" : "#E2E8F0"
                }
            }
            Springy { hover: refreshMetaBtnMouse.containsMouse; pressed: refreshMetaBtnMouse.pressed }
            MouseArea {
                id: refreshMetaBtnMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: topBar.view.isCurrentPathBlocked ? Qt.ForbiddenCursor : Qt.PointingHandCursor
                onClicked: {
                    if (topBar.view.bridge && topBar.view.bridge.refreshPostMetadataAsync) {
                        topBar.view.showToast("Fetching post metadata from Pawchive…")
                        var req = "gallery-meta-" + Date.now()
                        topBar.view.bridge.refreshPostMetadataAsync(req, topBar.view.currentPath, topBar.view.filteredItems, false)
                    }
                }
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: "Refresh Post Metadata\nFetch titles, captions, and tags from Pawchive/Kemono API and save locally as JSON and post_info.txt"
            }
        }

        // ── group divider · View ──
        Rectangle { width: 1; height: 18; color: "#2A3A52"; anchors.verticalCenter: parent.verticalCenter }

        // View Mode Toggle (Grid vs List)
        Rectangle {
            implicitHeight: 26
            implicitWidth: 54
            radius: 5
            color: "#12151E"
            border.color: "#252C3D"
            border.width: 1

            Row {
                anchors.centerIn: parent
                spacing: 2

                Rectangle {
                    width: 24
                    height: 20
                    radius: 3
                    color: topBar.view.viewMode === "grid" ? "#222D42" : "transparent"
                    border.color: topBar.view.viewMode === "grid" ? "#38BDF8" : "transparent"
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "⊞"; font.pixelSize: 11; color: topBar.view.viewMode === "grid" ? "#38BDF8" : "#64748B" }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: topBar.view.viewMode = "grid"
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Grid View\nDisplay files and folders as visual cards with thumbnails"
                    }
                }
                Rectangle {
                    width: 24
                    height: 20
                    radius: 3
                    color: topBar.view.viewMode === "list" ? "#222D42" : "transparent"
                    border.color: topBar.view.viewMode === "list" ? "#38BDF8" : "transparent"
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "📑"; font.pixelSize: 10; color: topBar.view.viewMode === "list" ? "#38BDF8" : "#64748B" }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: topBar.view.viewMode = "list"
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "List View\nDisplay detailed file information: names, item counts, sizes, and modified dates"
                    }
                }
            }
        }

        // View options: show / hide the path bar and shortcuts bar
        Rectangle {
            id: viewOptionsButton
            width: 26
            height: 26
            radius: 5
            color: (viewOptsMouse.containsMouse || topBar.view.viewMenuVisible) ? "#1E293B" : "#141720"
            border.color: (viewOptsMouse.containsMouse || topBar.view.viewMenuVisible) ? "#38BDF8" : "#2E384D"
            border.width: 1
            Text { anchors.centerIn: parent; text: "⋮"; font.pixelSize: 14; font.weight: 800; color: "#CBD5E1" }
            Springy { hover: viewOptsMouse.containsMouse; pressed: viewOptsMouse.pressed }
            MouseArea {
                id: viewOptsMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    topBar.view.openViewMenu(viewOptionsButton)
                }
                ToolTip.visible: containsMouse && !topBar.view.viewMenuVisible
                ToolTip.delay: 300
                ToolTip.text: "View options: show or hide the path bar and shortcuts bar"
            }
        }
    }
}
