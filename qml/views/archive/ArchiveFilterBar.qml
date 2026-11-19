import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── 2. Filter, Search & Category Strip ─────────────────────────
Rectangle {
    id: filterBar
    required property var view
    Layout.fillWidth: true
    implicitHeight: filterStripCol.implicitHeight + 16
    radius: 8
    color: "#0F131C"
    border.color: "#1B2232"
    border.width: 1

    ColumnLayout {
        id: filterStripCol
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        // Search & Sort Row
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            // Search input with debouncer
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 32
                radius: 6
                color: searchInput.activeFocus ? "#1B2232" : (searchBoxHover.hovered ? "#19202E" : "#161B26")
                border.color: searchInput.activeFocus ? "#38BDF8" : (searchBoxHover.hovered ? "#334155" : "#242E42")
                border.width: 1

                Behavior on border.color { ColorAnimation { duration: 150 } }
                Behavior on color { ColorAnimation { duration: 150 } }

                HoverHandler { id: searchBoxHover }

                TextBarContextArea {
                    target: searchInput
                    focusOnLeftClick: true
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 8
                    spacing: 6

                    Text {
                        text: "🔍"
                        font.pixelSize: 11
                        color: "#64748B"
                        scale: searchBoxHover.hovered ? 1.15 : 1.0
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                    }

                    TextInput {
                        id: searchInput
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        verticalAlignment: TextInput.AlignVCenter
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#F8FAFC"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        clip: true
                        selectByMouse: true
                        text: filterBar.view.searchFilter

                        TextBarContextArea {}

                        Text {
                            text: filterBar.view.tr("placeholder_archive_search", "Search files, links, creators, posts, hashes...")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#475569"
                            visible: !searchInput.text && !searchInput.activeFocus
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.right: parent.right
                            elide: Text.ElideRight
                        }

                        onTextChanged: {
                            searchDebounceTimer.restart()
                        }
                    }

                    Timer {
                        id: searchDebounceTimer
                        interval: 250
                        onTriggered: {
                            filterBar.view.searchFilter = searchInput.text
                            filterBar.view._expandOnResult = filterBar.view.searchFilter.trim().length > 0
                            if (!filterBar.view._expandOnResult)
                                filterBar.view.expandedCreators = {}
                            filterBar.view.reload()
                        }
                    }

                    // Clear button
                    Text {
                        text: "✕"
                        font.pixelSize: 10
                        color: clearSearchMouse.containsMouse ? "#F8FAFC" : "#64748B"
                        visible: searchInput.text.length > 0
                        scale: clearSearchMouse.pressed ? 0.82 : (clearSearchMouse.containsMouse ? 1.25 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }

                        MouseArea {
                            id: clearSearchMouse
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            hoverEnabled: true
                            onClicked: {
                                searchInput.text = ""
                                filterBar.view.searchFilter = ""
                                filterBar.view.expandedCreators = {}
                                filterBar.view.expandedPosts = {}
                                filterBar.view.reload()
                            }
                        }
                    }
                }
            }

            // Sort Order selector
            Rectangle {
                id: sortSelectorBtn
                Layout.preferredWidth: 160
                Layout.preferredHeight: 32
                radius: 6
                color: sortPopup.visible ? "#1E2A3F" : (sortMouse.containsMouse ? "#1C2333" : "#161B26")
                border.color: sortPopup.visible ? "#38BDF8" : (sortMouse.containsMouse ? "#38BDF8" : "#242E42")
                border.width: sortPopup.visible ? 1.5 : 1
                scale: sortMouse.pressed ? 0.96 : (sortMouse.containsMouse ? 1.02 : 1.0)

                transform: Translate {
                    y: (sortMouse.containsMouse && !sortPopup.visible) ? -1.5 : 0
                    Behavior on y {
                        SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                    }
                }

                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                Behavior on color { ColorAnimation { duration: 140 } }
                Behavior on border.color { ColorAnimation { duration: 140 } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 9
                    anchors.rightMargin: 9
                    spacing: 6

                    Text {
                        text: {
                            if (filterBar.view.sortOrder === "creator_az") return "🔤"
                            if (filterBar.view.sortOrder === "creator_za") return "🔤"
                            if (filterBar.view.sortOrder === "files_desc") return "📦"
                            if (filterBar.view.sortOrder === "newest") return "🕒"
                            if (filterBar.view.sortOrder === "oldest") return "📅"
                            return "↕"
                        }
                        font.pixelSize: 11
                        scale: sortMouse.containsMouse ? 1.15 : 1.0
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: {
                            if (filterBar.view.sortOrder === "creator_az") return filterBar.view.tr("sort_creator_az", "Creator A-Z")
                            if (filterBar.view.sortOrder === "creator_za") return filterBar.view.tr("sort_creator_za", "Creator Z-A")
                            if (filterBar.view.sortOrder === "files_desc") return filterBar.view.tr("sort_files_desc", "Most Files")
                            if (filterBar.view.sortOrder === "newest") return filterBar.view.tr("sort_newest", "Newest Added")
                            if (filterBar.view.sortOrder === "oldest") return filterBar.view.tr("sort_oldest", "Oldest Added")
                            return filterBar.view.tr("sort_creator_az", "Creator A-Z")
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        color: sortPopup.visible ? "#38BDF8" : "#E2E8F0"
                        elide: Text.ElideRight
                    }

                    Text {
                        text: "▾"
                        font.pixelSize: 10
                        color: sortPopup.visible ? "#38BDF8" : "#64748B"
                        rotation: sortPopup.visible ? 180 : 0
                        transformOrigin: Item.Center
                        Behavior on rotation {
                            SpringAnimation { spring: 5.0; damping: 0.4; mass: 0.8 }
                        }
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                }

                MouseArea {
                    id: sortMouse
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: {
                        if (sortPopup.visible) {
                            sortPopup.close()
                        } else {
                            sortPopup.open()
                        }
                    }
                }

                Popup {
                    id: sortPopup
                    objectName: "sortPopup"
                    y: parent.height + 4
                    width: 175
                    padding: 5
                    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
                    transformOrigin: Popup.Top

                    enter: Transition {
                        NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 140; easing.type: Easing.OutCubic }
                        NumberAnimation { property: "scale"; from: 0.94; to: 1.0; duration: 140; easing.type: Easing.OutCubic }
                    }
                    exit: Transition {
                        NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 100; easing.type: Easing.InCubic }
                        NumberAnimation { property: "scale"; from: 1.0; to: 0.96; duration: 100; easing.type: Easing.InCubic }
                    }

                    background: Rectangle {
                        color: "#0E1422"
                        border.color: "#1E293B"
                        border.width: 1.5
                        radius: 8
                    }

                    contentItem: ColumnLayout {
                        spacing: 3

                        Repeater {
                            model: [
                                { key: "creator_az", label: filterBar.view.tr("sort_creator_az", "Creator A-Z"), icon: "🔤", tag: "A → Z" },
                                { key: "creator_za", label: filterBar.view.tr("sort_creator_za", "Creator Z-A"), icon: "🔤", tag: "Z → A" },
                                { key: "files_desc", label: filterBar.view.tr("sort_files_desc", "Most Files"), icon: "📦", tag: "Count" },
                                { key: "newest", label: filterBar.view.tr("sort_newest", "Newest Added"), icon: "🕒", tag: "Recent" },
                                { key: "oldest", label: filterBar.view.tr("sort_oldest", "Oldest Added"), icon: "📅", tag: "Earliest" }
                            ]

                            delegate: Rectangle {
                                id: sortItemRect
                                Layout.fillWidth: true
                                implicitHeight: 32
                                radius: 6

                                readonly property bool isSelected: filterBar.view.sortOrder === modelData.key
                                readonly property bool isHovered: itemMouseArea.containsMouse

                                color: isSelected ? "#162234" : (isHovered ? "#151D2C" : "transparent")
                                border.color: isSelected ? "#1E3A5F" : (isHovered ? "#1E293B" : "transparent")
                                border.width: 1
                                clip: true

                                Behavior on color { ColorAnimation { duration: 100 } }
                                Behavior on border.color { ColorAnimation { duration: 100 } }

                                // Left accent bar
                                Rectangle {
                                    width: 3
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.bottom: parent.bottom
                                    anchors.topMargin: 4
                                    anchors.bottomMargin: 4
                                    radius: 1.5
                                    color: "#38BDF8"
                                    visible: sortItemRect.isSelected
                                }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: sortItemRect.isSelected ? 10 : 8
                                    anchors.rightMargin: 8
                                    spacing: 7

                                    Text {
                                        text: modelData.icon
                                        font.pixelSize: 11
                                        opacity: sortItemRect.isSelected ? 1.0 : 0.75
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.label
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: sortItemRect.isSelected ? Font.DemiBold : Font.Normal
                                        color: sortItemRect.isSelected ? "#38BDF8" : (sortItemRect.isHovered ? "#F1F5F9" : "#CBD5E1")
                                        elide: Text.ElideRight
                                    }

                                    // Sub-tag badge
                                    Rectangle {
                                        implicitHeight: 16
                                        implicitWidth: tagTxt.implicitWidth + 8
                                        radius: 4
                                        color: sortItemRect.isSelected ? "#0F2942" : "#131A26"
                                        border.color: sortItemRect.isSelected ? "#0369A1" : "#1E293B"
                                        border.width: 1

                                        Text {
                                            id: tagTxt
                                            anchors.centerIn: parent
                                            text: modelData.tag
                                            font.pixelSize: 9
                                            font.weight: Font.DemiBold
                                            color: sortItemRect.isSelected ? "#7DD3FC" : "#64748B"
                                        }
                                    }

                                    Text {
                                        text: "✓"
                                        font.pixelSize: 11
                                        font.bold: true
                                        color: "#38BDF8"
                                        visible: sortItemRect.isSelected
                                    }
                                }

                                MouseArea {
                                    id: itemMouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        filterBar.view.sortOrder = modelData.key
                                        filterBar.view.reload()
                                        sortPopup.close()
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Expand / Collapse All toggle
            StyledButton {
                property bool allExpanded: {
                    var rev = filterBar.view._creatorsRevision       // (a new list is checked again)
                    if (!filterBar.view.creatorsModel || filterBar.view.creatorsModel.count === 0) return false
                    return filterBar.view.creatorsModel.allIn(filterBar.view.expandedCreators || {})
                }
                text: allExpanded ? filterBar.view.tr("btn_collapse_all", "Collapse All") : filterBar.view.tr("btn_expand_all", "Expand All")
                iconText: allExpanded ? "🔼" : "🔽"
                variant: "outline"
                implicitHeight: 32
                onClicked: {
                    if (allExpanded) {
                        filterBar.view.expandedCreators = {}
                    } else {
                        filterBar.view.expandedCreators = filterBar.view.creatorsModel ? filterBar.view.creatorsModel.allNamesMap() : ({})
                    }
                }
            }
        }

        // File Type Category Pills Container with Smooth Scroll & Navigation Arrows
        Item {
            id: catContainer
            Layout.fillWidth: true
            implicitHeight: 34

            readonly property bool canScrollLeft: catFlickable.contentX > 2
            readonly property bool canScrollRight: catFlickable.contentX < (catFlickable.contentWidth - catFlickable.width - 2)
            readonly property bool isOverflowing: catFlickable.contentWidth > catFlickable.width

            function scrollBy(delta) {
                var targetX = catFlickable.contentX + delta
                var maxX = Math.max(0, catFlickable.contentWidth - catFlickable.width)
                catScrollAnim.to = Math.max(0, Math.min(maxX, targetX))
                catScrollAnim.restart()
            }

            NumberAnimation {
                id: catScrollAnim
                target: catFlickable
                property: "contentX"
                duration: 180
                easing.type: Easing.OutCubic
            }

            RowLayout {
                anchors.fill: parent
                spacing: 4

                // Left Arrow Button
                Rectangle {
                    id: leftScrollBtn
                    Layout.preferredWidth: (catContainer.isOverflowing && catContainer.canScrollLeft) ? 24 : 0
                    Layout.preferredHeight: 26
                    visible: catContainer.isOverflowing
                    opacity: catContainer.canScrollLeft ? 1.0 : 0.0
                    radius: 6
                    color: leftScrollMouse.containsMouse ? "#1E293B" : "#131824"
                    border.color: leftScrollMouse.containsMouse ? "#38BDF8" : "#1F293D"
                    border.width: 1
                    clip: true

                    Behavior on Layout.preferredWidth { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }
                    Behavior on opacity { NumberAnimation { duration: 150 } }
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    Text {
                        anchors.centerIn: parent
                        text: "◀"
                        font.pixelSize: 10
                        color: leftScrollMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                    }

                    MouseArea {
                        id: leftScrollMouse
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        hoverEnabled: true
                        onClicked: catContainer.scrollBy(-180)
                    }
                }

                // Flickable
                Flickable {
                    id: catFlickable
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentWidth: catPillsRow.implicitWidth + 8
                    contentHeight: height
                    flickableDirection: Flickable.HorizontalFlick
                    boundsBehavior: Flickable.StopAtBounds
                    clip: true

                    onWidthChanged: {
                        var maxX = Math.max(0, contentWidth - width)
                        if (contentX > maxX) contentX = maxX
                    }
                    onContentWidthChanged: {
                        var maxX = Math.max(0, contentWidth - width)
                        if (contentX > maxX) contentX = maxX
                    }

                    WheelHandler {
                        id: catWheelHandler
                        target: catFlickable
                        orientation: Qt.Horizontal | Qt.Vertical
                        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                        onWheel: function(event) {
                            var delta = event.angleDelta.y !== 0 ? event.angleDelta.y : event.angleDelta.x
                            catContainer.scrollBy(-delta)
                        }
                    }

                    RowLayout {
                        id: catPillsRow
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 6

                        // Helper component for category pill
                        component CategoryPill: Rectangle {
                            property string catId: ""
                            property string catLabel: ""
                            property string catIcon: ""
                            property int catCount: 0
                            property string activeColor: "#38BDF8"

                            property bool isSelected: filterBar.view.fileTypeFilter === catId
                            implicitHeight: 24
                            implicitWidth: pillInnerRow.implicitWidth + 16
                            radius: 12

                            color: isSelected ? activeColor : (pillMouse.containsMouse ? "#1E2638" : "#131824")
                            border.color: isSelected ? activeColor : (pillMouse.containsMouse ? "#334155" : "#1F293D")
                            border.width: 1

                            scale: pillMouse.pressed ? 0.93 : (pillMouse.containsMouse ? 1.05 : 1.0)
                            transformOrigin: Item.Center
                            transform: Translate {
                                y: pillMouse.containsMouse ? -1.5 : 0
                                Behavior on y { SpringAnimation { spring: 4.8; damping: 0.38; mass: 0.8; epsilon: 0.1 } }
                            }

                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 } }
                            Behavior on color { ColorAnimation { duration: 140 } }
                            Behavior on border.color { ColorAnimation { duration: 140 } }

                            RowLayout {
                                id: pillInnerRow
                                anchors.centerIn: parent
                                spacing: 5

                                Text {
                                    text: catIcon
                                    font.pixelSize: 10
                                    visible: catIcon.length > 0
                                    scale: pillMouse.containsMouse ? 1.2 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                                }

                                Text {
                                    text: catLabel
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: isSelected ? 600 : Font.Normal
                                    color: isSelected ? "#0F172A" : "#E2E8F0"
                                }

                                Rectangle {
                                    visible: catCount > 0
                                    implicitHeight: 14
                                    implicitWidth: countTxt.implicitWidth + 6
                                    radius: 7
                                    color: isSelected ? "#0F172A" : "#1E293B"
                                    scale: isSelected ? 1.08 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8 } }

                                    Text {
                                        id: countTxt
                                        anchors.centerIn: parent
                                        text: catCount.toString()
                                        font.pixelSize: 8
                                        font.bold: true
                                        color: isSelected ? activeColor : "#94A3B8"
                                    }
                                }
                            }

                            MouseArea {
                                id: pillMouse
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                onClicked: {
                                    filterBar.view.fileTypeFilter = catId
                                    filterBar.view.reload()
                                }
                            }
                        }

                        CategoryPill {
                            catId: "all"
                            catLabel: filterBar.view.tr("pill_all_files", "All Files")
                            catCount: filterBar.view.statistics ? filterBar.view.statistics.total_files : 0
                            activeColor: "#38BDF8"
                        }

                        CategoryPill {
                            catId: "archives"
                            catIcon: "📦"
                            catLabel: filterBar.view.tr("pill_archives", "Archives (.zip, .rar)")
                            catCount: (filterBar.view.statistics && filterBar.view.statistics.category_counts) ? filterBar.view.statistics.category_counts.archives || 0 : 0
                            activeColor: "#F59E0B"
                        }

                        CategoryPill {
                            catId: "graphics"
                            catIcon: "🎨"
                            catLabel: filterBar.view.tr("pill_graphics", "Graphics (.psd, .clip)")
                            catCount: (filterBar.view.statistics && filterBar.view.statistics.category_counts) ? filterBar.view.statistics.category_counts.graphics || 0 : 0
                            activeColor: "#38BDF8"
                        }

                        CategoryPill {
                            catId: "images"
                            catIcon: "🖼️"
                            catLabel: filterBar.view.tr("pill_images", "Images (.png, .jpg)")
                            catCount: (filterBar.view.statistics && filterBar.view.statistics.category_counts) ? filterBar.view.statistics.category_counts.images || 0 : 0
                            activeColor: "#10B981"
                        }

                        CategoryPill {
                            catId: "videos"
                            catIcon: "🎬"
                            catLabel: filterBar.view.tr("pill_videos", "Videos (.mp4, .mkv)")
                            catCount: (filterBar.view.statistics && filterBar.view.statistics.category_counts) ? filterBar.view.statistics.category_counts.videos || 0 : 0
                            activeColor: "#EC4899"
                        }

                        CategoryPill {
                            catId: "audio"
                            catIcon: "🎵"
                            catLabel: filterBar.view.tr("pill_audio", "Audio (.mp3, .wav)")
                            catCount: (filterBar.view.statistics && filterBar.view.statistics.category_counts) ? filterBar.view.statistics.category_counts.audio || 0 : 0
                            activeColor: "#A855F7"
                        }

                        CategoryPill {
                            catId: "documents"
                            catIcon: "📄"
                            catLabel: filterBar.view.tr("pill_documents", "Documents (.pdf, .txt)")
                            catCount: (filterBar.view.statistics && filterBar.view.statistics.category_counts) ? filterBar.view.statistics.category_counts.documents || 0 : 0
                            activeColor: "#94A3B8"
                        }

                        CategoryPill {
                            catId: "links"
                            catIcon: "🔗"
                            catLabel: filterBar.view.tr("pill_links", "Links & Embeds")
                            catCount: (filterBar.view.statistics && filterBar.view.statistics.category_counts) ? filterBar.view.statistics.category_counts.links || 0 : 0
                            activeColor: "#06B6D4"
                        }
                    }
                }

                // Right Arrow Button
                Rectangle {
                    id: rightScrollBtn
                    Layout.preferredWidth: (catContainer.isOverflowing && catContainer.canScrollRight) ? 24 : 0
                    Layout.preferredHeight: 26
                    visible: catContainer.isOverflowing
                    opacity: catContainer.canScrollRight ? 1.0 : 0.0
                    radius: 6
                    color: rightScrollMouse.containsMouse ? "#1E293B" : "#131824"
                    border.color: rightScrollMouse.containsMouse ? "#38BDF8" : "#1F293D"
                    border.width: 1
                    clip: true

                    Behavior on Layout.preferredWidth { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }
                    Behavior on opacity { NumberAnimation { duration: 150 } }
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    Text {
                        anchors.centerIn: parent
                        text: "▶"
                        font.pixelSize: 10
                        color: rightScrollMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                    }

                    MouseArea {
                        id: rightScrollMouse
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        hoverEnabled: true
                        onClicked: catContainer.scrollBy(180)
                    }
                }
            }
        }
    }
}
