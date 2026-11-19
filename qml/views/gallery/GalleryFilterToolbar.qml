import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

RowLayout {
    id: filterToolbar
    required property var view
    property alias searchInput: searchInput
    Layout.fillWidth: true
    spacing: 8

    // Filter Pills (scroll sideways if they don't fit)
    GalleryHScrollStrip {
        Layout.fillWidth: true
        Layout.minimumWidth: 60
        implicitHeight: 26
        contentWidth: pillsRow.implicitWidth

        Row {
            id: pillsRow
            spacing: 6

            // All
            Rectangle {
                implicitHeight: 26
                implicitWidth: pillAllText.implicitWidth + 14
                radius: 13
                color: filterToolbar.view.activeCategory === "all" ? "#38BDF8" : "#161B28"
                Text {
                    id: pillAllText
                    anchors.centerIn: parent
                    text: "All (" + (filterToolbar.view.recursiveActive ? filterToolbar.view.searchResults.length : filterToolbar.view.rawItems.length) + ")"
                    font.pixelSize: 11
                    font.weight: 600
                    color: filterToolbar.view.activeCategory === "all" ? "#0F172A" : "#94A3B8"
                }
                Springy { hover: pill_allMouse.containsMouse; pressed: pill_allMouse.pressed }
                MouseArea {

                    id: pill_allMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: filterToolbar.view.activeCategory = "all"
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Show all items in this folder (" + filterToolbar.view.rawItems.length + " total)"
                }
            }

            // Folders
            Rectangle {
                implicitHeight: 26
                implicitWidth: pillFoldersText.implicitWidth + 14
                radius: 13
                color: filterToolbar.view.activeCategory === "folders" ? "#38BDF8" : "#161B28"
                Text {
                    id: pillFoldersText
                    anchors.centerIn: parent
                    text: !filterToolbar.view.showPillLabels ? ("📁 " + filterToolbar.view.folderCount) : ("📁 Folders (" + filterToolbar.view.folderCount + ")")
                    font.pixelSize: 11
                    font.weight: 600
                    color: filterToolbar.view.activeCategory === "folders" ? "#0F172A" : "#94A3B8"
                }
                Springy { hover: pill_foldersMouse.containsMouse; pressed: pill_foldersMouse.pressed }
                MouseArea {

                    id: pill_foldersMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: filterToolbar.view.activeCategory = "folders"
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Show only subdirectories (" + filterToolbar.view.folderCount + " folders)"
                }
            }

            // Images
            Rectangle {
                implicitHeight: 26
                implicitWidth: pillImgText.implicitWidth + 14
                radius: 13
                color: filterToolbar.view.activeCategory === "images" ? "#EC4899" : "#161B28"
                Text {
                    id: pillImgText
                    anchors.centerIn: parent
                    text: !filterToolbar.view.showPillLabels ? ("🖼️ " + filterToolbar.view.imageCount) : ("🖼️ Images (" + filterToolbar.view.imageCount + ")")
                    font.pixelSize: 11
                    font.weight: 600
                    color: filterToolbar.view.activeCategory === "images" ? "#FFFFFF" : "#94A3B8"
                }
                Springy { hover: pill_imagesMouse.containsMouse; pressed: pill_imagesMouse.pressed }
                MouseArea {

                    id: pill_imagesMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: filterToolbar.view.activeCategory = "images"
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Show only images: JPG, PNG, GIF, WebP, SVG, BMP (" + filterToolbar.view.imageCount + " images)"
                }
            }

            // Videos
            Rectangle {
                implicitHeight: 26
                implicitWidth: pillVidText.implicitWidth + 14
                radius: 13
                color: filterToolbar.view.activeCategory === "videos" ? "#8B5CF6" : "#161B28"
                Text {
                    id: pillVidText
                    anchors.centerIn: parent
                    text: !filterToolbar.view.showPillLabels ? ("🎬 " + filterToolbar.view.videoCount) : ("🎬 Videos (" + filterToolbar.view.videoCount + ")")
                    font.pixelSize: 11
                    font.weight: 600
                    color: filterToolbar.view.activeCategory === "videos" ? "#FFFFFF" : "#94A3B8"
                }
                Springy { hover: pill_videosMouse.containsMouse; pressed: pill_videosMouse.pressed }
                MouseArea {

                    id: pill_videosMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: filterToolbar.view.activeCategory = "videos"
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Show only videos: MP4, MKV, WebM, MOV, AVI (" + filterToolbar.view.videoCount + " videos)"
                }
            }

            // Archives
            Rectangle {
                implicitHeight: 26
                implicitWidth: pillArcText.implicitWidth + 14
                radius: 13
                color: filterToolbar.view.activeCategory === "archives" ? "#F59E0B" : "#161B28"
                Text {
                    id: pillArcText
                    anchors.centerIn: parent
                    text: !filterToolbar.view.showPillLabels ? ("📦 " + filterToolbar.view.archiveCount) : ("📦 Archives (" + filterToolbar.view.archiveCount + ")")
                    font.pixelSize: 11
                    font.weight: 600
                    color: filterToolbar.view.activeCategory === "archives" ? "#0F172A" : "#94A3B8"
                }
                Springy { hover: pill_archivesMouse.containsMouse; pressed: pill_archivesMouse.pressed }
                MouseArea {

                    id: pill_archivesMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: filterToolbar.view.activeCategory = "archives"
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Show only compressed archives: ZIP, RAR, 7Z, TAR, GZ (" + filterToolbar.view.archiveCount + " archives)"
                }
            }

            // Audio
            Rectangle {
                implicitHeight: 26
                implicitWidth: pillAudText.implicitWidth + 14
                radius: 13
                color: filterToolbar.view.activeCategory === "audio" ? "#10B981" : "#161B28"
                Text {
                    id: pillAudText
                    anchors.centerIn: parent
                    text: !filterToolbar.view.showPillLabels ? ("🎵 " + filterToolbar.view.audioCount) : ("🎵 Audio (" + filterToolbar.view.audioCount + ")")
                    font.pixelSize: 11
                    font.weight: 600
                    color: filterToolbar.view.activeCategory === "audio" ? "#0F172A" : "#94A3B8"
                }
                Springy { hover: pill_audioMouse.containsMouse; pressed: pill_audioMouse.pressed }
                MouseArea {

                    id: pill_audioMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: filterToolbar.view.activeCategory = "audio"
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Show only audio tracks: MP3, FLAC, WAV, OGG, M4A (" + filterToolbar.view.audioCount + " audio files)"
                }
            }
        }
    }

    // Group files of the same post into one stack
    Rectangle {
        implicitWidth: 28
        implicitHeight: 26
        radius: 6
        Layout.alignment: Qt.AlignVCenter
        color: filterToolbar.view.groupByPost ? "#2E1F55" : (groupBtnMouse.containsMouse ? "#1E293B" : "#121622")
        border.color: filterToolbar.view.groupByPost ? "#A78BFA" : (groupBtnMouse.containsMouse ? "#38BDF8" : "#252D3E")
        border.width: 1
        Text { anchors.centerIn: parent; text: "🗂"; font.pixelSize: 12; color: "#CBD5E1"; opacity: filterToolbar.view.groupByPost ? 1.0 : 0.7 }
        Springy { hover: groupBtnMouse.containsMouse; pressed: groupBtnMouse.pressed }
        MouseArea {
            id: groupBtnMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: filterToolbar.view.groupByPost = !filterToolbar.view.groupByPost
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: filterToolbar.view.groupByPost ? "Grouping files by post (click to show every file)" : "Group by post: show each post's files as one stack"
        }
    }

    // Group files by date: Today, This week, March 2025…
    Rectangle {
        implicitWidth: 28
        implicitHeight: 26
        radius: 6
        Layout.alignment: Qt.AlignVCenter
        color: filterToolbar.view.groupByDate ? "#0F2A3A" : (dateGroupMouse.containsMouse ? "#1E293B" : "#121622")
        border.color: filterToolbar.view.groupByDate ? "#38BDF8" : (dateGroupMouse.containsMouse ? "#38BDF8" : "#252D3E")
        border.width: 1
        Text { anchors.centerIn: parent; text: "📅"; font.pixelSize: 12; opacity: filterToolbar.view.groupByDate ? 1.0 : 0.7 }
        Springy { hover: dateGroupMouse.containsMouse; pressed: dateGroupMouse.pressed }
        MouseArea {
            id: dateGroupMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: filterToolbar.view.groupByDate = !filterToolbar.view.groupByDate
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: filterToolbar.view.groupByDate ? "Grouping by date (click to turn off)" : "Group by date: Today, This week, This month, then by month"
        }
    }


    // Thumbnail size (grid view only); Ctrl + mouse wheel does the same
    Row {
        visible: filterToolbar.view.showZoomSlider
        spacing: 4
        Layout.alignment: Qt.AlignVCenter
        Text { text: "▫"; font.pixelSize: 12; color: "#64748B"; anchors.verticalCenter: parent.verticalCenter }
        Slider {
            id: zoomSlider
            width: 80
            height: 20
            anchors.verticalCenter: parent.verticalCenter
            from: 120
            to: 320
            stepSize: 8
            value: filterToolbar.view.thumbSize
            onMoved: filterToolbar.view.setThumbSize(value)
            background: Rectangle {
                x: zoomSlider.leftPadding
                y: zoomSlider.topPadding + zoomSlider.availableHeight / 2 - height / 2
                width: zoomSlider.availableWidth
                height: 4
                radius: 2
                color: "#1E2536"
                Rectangle {
                    width: zoomSlider.visualPosition * parent.width
                    height: parent.height
                    radius: 2
                    color: "#38BDF8"
                }
            }
            handle: Rectangle {
                x: zoomSlider.leftPadding + zoomSlider.visualPosition * (zoomSlider.availableWidth - width)
                y: zoomSlider.topPadding + zoomSlider.availableHeight / 2 - height / 2
                width: 12
                height: 12
                radius: 6
                color: zoomSlider.pressed ? "#7DD3FC" : "#E2E8F0"
                border.color: "#38BDF8"
            }
            ToolTip.visible: hovered || pressed
            ToolTip.delay: 300
            ToolTip.text: "Thumbnail size (Ctrl + mouse wheel works too)"
        }
        Text { text: "◻"; font.pixelSize: 14; color: "#64748B"; anchors.verticalCenter: parent.verticalCenter }
    }

    // Sort control
    Rectangle {
        id: sortButton
        implicitHeight: 28
        implicitWidth: sortBtnRow.implicitWidth + 16
        radius: 6
        color: sortBtnMouse.containsMouse ? "#1E293B" : "#121622"
        border.color: (sortBtnMouse.containsMouse || filterToolbar.view.sortMenuVisible) ? "#38BDF8" : "#252D3E"
        border.width: 1

        Row {
            id: sortBtnRow
            anchors.centerIn: parent
            spacing: 5
            Text { text: "⇅"; font.pixelSize: 11; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
            Text {
                text: (filterToolbar.view.showSortLabel ? filterToolbar.view.sortLabel(filterToolbar.view.sortKey) + "  " : "") + (filterToolbar.view.sortAscending ? "▲" : "▼")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 600
                color: "#E2E8F0"
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        Springy { hover: sortBtnMouse.containsMouse; pressed: sortBtnMouse.pressed }
        MouseArea {
            id: sortBtnMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                filterToolbar.view.openSortMenu(sortButton)
            }
            ToolTip.visible: containsMouse && !filterToolbar.view.sortMenuVisible
            ToolTip.delay: 300
            ToolTip.text: "Sort Order\nSorted by " + filterToolbar.view.sortLabel(filterToolbar.view.sortKey).toLowerCase() + (filterToolbar.view.sortAscending ? " (ascending)" : " (descending)") + ".\nFolders always stay on top. Click to change."
        }
    }

    // Search input
    Rectangle {
        implicitHeight: 28
        implicitWidth: filterToolbar.view.searchBoxWidth
        radius: 6
        color: searchInput.activeFocus ? "#0B0D12" : "#121622"
        border.color: searchInput.activeFocus ? "#38BDF8" : (gallerySearchBoxMouse.containsMouse ? "#475569" : "#252D3E")
        border.width: searchInput.activeFocus ? 1.5 : 1

        TextBarContextArea {
            id: gallerySearchBoxMouse
            target: searchInput
            focusOnLeftClick: true
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 6

            Text { text: "🔍"; font.pixelSize: 11 }
            TextInput {
                id: searchInput
                Layout.fillWidth: true
                Layout.fillHeight: true
                verticalAlignment: TextInput.AlignVCenter
                color: "#F8FAFC"
                selectionColor: "#0284C7"
                selectedTextColor: "#FFFFFF"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                selectByMouse: true
                clip: true
                TextBarContextArea {}
                onTextChanged: filterToolbar.view.searchFilter = text
                Keys.onDownPressed: filterToolbar.view.focusBrowser()
                Keys.onEscapePressed: filterToolbar.view.focusBrowser()

                Text {
                    visible: !searchInput.text && !searchInput.activeFocus
                    text: filterToolbar.view.searchSubfolders ? "Search all subfolders…  (.png, .mp4)" : "Search this folder…  (.png, .mp4)"
                    color: "#64748B"
                    font.pixelSize: 11
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                }
            }
            // Toggle: also search inside subfolders
            Rectangle {
                visible: !!filterToolbar.view.tools
                implicitWidth: 22
                implicitHeight: 18
                radius: 4
                color: filterToolbar.view.searchSubfolders ? "#2E1F55" : (subToggleMouse.containsMouse ? "#1E293B" : "transparent")
                border.color: filterToolbar.view.searchSubfolders ? "#A78BFA" : "transparent"
                border.width: 1
                Text { anchors.centerIn: parent; text: "🗂"; font.pixelSize: 10; color: "#CBD5E1"; opacity: filterToolbar.view.searchSubfolders ? 1.0 : 0.6 }
                MouseArea {
                    id: subToggleMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: filterToolbar.view.searchSubfolders = !filterToolbar.view.searchSubfolders
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: filterToolbar.view.searchSubfolders ? "Searching subfolders too (click to search only this folder)" : "Also search inside all subfolders"
                }
            }
            // Save this search to the Shortcuts bar
            Rectangle {
                visible: searchInput.text.trim().length > 0 && !filterToolbar.view.inFavorites
                implicitWidth: 22
                implicitHeight: 18
                radius: 4
                color: filterToolbar.view.currentSearchSaved ? "#2A2210" : (pinMouse.containsMouse ? "#1E293B" : "transparent")
                border.color: filterToolbar.view.currentSearchSaved ? "#F59E0B" : (pinMouse.containsMouse ? "#475569" : "transparent")
                Text { anchors.centerIn: parent; text: "📌"; font.pixelSize: 10; opacity: filterToolbar.view.currentSearchSaved ? 1.0 : 0.75 }
                MouseArea {
                    id: pinMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: filterToolbar.view.toggleSaveSearch()
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: filterToolbar.view.currentSearchSaved ? "Saved in your Shortcuts bar (click to remove)" : "Save this search to the Shortcuts bar"
                }
            }
            Text {
                visible: searchInput.text.length > 0
                text: "✕"
                font.pixelSize: 10
                color: "#94A3B8"
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        searchInput.text = ""
                        filterToolbar.view.searchFilter = ""
                    }
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Clear search filter"
                }
            }
        }
    }
}
