import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: searchBar
    required property var view

    function scrollServicesBy(deltaX) {
        var maxX = Math.max(0, svcFlickable.contentWidth - svcFlickable.width)
        if (maxX <= 0) {
            svcFlickable.contentX = 0
            return
        }
        svcFlickable.contentX = Math.max(0, Math.min(maxX, svcFlickable.contentX + Number(deltaX || 0)))
    }
    objectName: "browserSearchBar"
    Layout.fillWidth: true
    Layout.preferredHeight: searchBarCol.implicitHeight + 12
    visible: !searchBar.view.hasSelectedCreator
    radius: 10
    color: "#0F131C"
    border.color: "#1E2536"
    border.width: 1
    clip: true

    ColumnLayout {
        id: searchBarCol
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        anchors.topMargin: 6
        spacing: 6

        Flow {
            id: searchSortFlow
            Layout.fillWidth: true
            spacing: 8

            readonly property bool tagVisible: !searchBar.view.isLocalMode && !!searchBar.view.activeCaps.supportsTagFilter
            readonly property real minSearchTagW: tagVisible ? 318 : 180
            readonly property real remainingForSearch: width - sortPillsFlow.width - spacing
            readonly property bool sortFitsInline: sortPillsFlow.naturalWidth > 0 && remainingForSearch >= minSearchTagW && sortPillsFlow.naturalWidth <= width

            // Search + optional Tag input group (stretches to fill remaining row width when wide, wraps cleanly when narrow)
            Flow {
                id: searchTagFlow
                width: searchSortFlow.sortFitsInline ? searchSortFlow.remainingForSearch : searchSortFlow.width
                spacing: 8

                // Search Box
                Rectangle {
                    id: mainSearchBox
                    width: {
                        if (!searchSortFlow.tagVisible) return searchTagFlow.width
                        var rem = searchTagFlow.width - 150 - searchTagFlow.spacing
                        return rem >= 160 ? rem : searchTagFlow.width
                    }
                    height: 32
                    radius: 7
                    color: mainSearchInput.activeFocus ? "#0B0D12" : "#090C12"
                    border.color: mainSearchInput.activeFocus ? "#38BDF8" : (mainSearchBoxMouse.containsMouse ? "#475569" : "#1E293B")
                    border.width: mainSearchInput.activeFocus ? 1.5 : 1

                    TextBarContextArea {
                        id: mainSearchBoxMouse
                        target: mainSearchInput
                        focusOnLeftClick: true
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 6

                        Text { text: "🔍"; font.pixelSize: 12; color: "#64748B" }

                        TextField {
                            id: mainSearchInput
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            verticalAlignment: TextInput.AlignVCenter
                            leftPadding: 2
                            rightPadding: 2
                            placeholderText: searchBar.view.isLocalMode ? "Search local creators on disk…" : ("Search " + (searchBar.view.activeManifest.name || "creators") + "…")
                            placeholderTextColor: "#64748B"
                            color: "#F8FAFC"
                            selectionColor: "#0284C7"
                            selectedTextColor: "#FFFFFF"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            background: Item {}
                            clip: true
                            selectByMouse: true
                            onAccepted: if (searchBar.view.bBridge) searchBar.view.bBridge.search(text)
                            onTextChanged: searchDebounce.restart()
                            TextBarContextArea {}
                        }

                        Timer {
                            id: searchDebounce
                            interval: 340
                            repeat: false
                            onTriggered: if (searchBar.view.bBridge) searchBar.view.bBridge.search(mainSearchInput.text)
                        }

                        Text {
                            visible: mainSearchInput.text.length > 0
                            text: "✕"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    mainSearchInput.text = ""
                                    if (searchBar.view.bBridge) searchBar.view.bBridge.search("")
                                    mainSearchInput.forceActiveFocus()
                                }
                            }
                        }
                    }
                }

                // Tag Filter Input (shown when active provider supports tags, e.g. cum.st)
                Rectangle {
                    visible: searchSortFlow.tagVisible
                    width: Math.min(150, searchTagFlow.width)
                    height: 32
                    radius: 7
                    color: tagInput.activeFocus ? "#0B0D12" : "#090C12"
                    border.color: tagInput.activeFocus ? "#38BDF8" : (tagBoxMouse.containsMouse ? "#475569" : "#1E293B")
                    border.width: tagInput.activeFocus ? 1.5 : 1

                    TextBarContextArea {
                        id: tagBoxMouse
                        target: tagInput
                        focusOnLeftClick: true
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 4

                        Text { text: "🏷️"; font.pixelSize: 11 }
                        TextField {
                            id: tagInput
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            verticalAlignment: TextInput.AlignVCenter
                            leftPadding: 2
                            rightPadding: 2
                            placeholderText: "Tag (e.g. cosplay)"
                            placeholderTextColor: "#64748B"
                            color: "#38BDF8"
                            selectionColor: "#0284C7"
                            selectedTextColor: "#FFFFFF"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            background: Item {}
                            clip: true
                            selectByMouse: true
                            onAccepted: if (searchBar.view.bBridge) searchBar.view.bBridge.setTagFilter(text)
                            TextBarContextArea {}
                        }
                        Text {
                            visible: tagInput.text.length > 0
                            text: "✕"
                            font.pixelSize: 10
                            color: "#94A3B8"
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    tagInput.text = ""
                                    if (searchBar.view.bBridge) searchBar.view.bBridge.setTagFilter("")
                                    tagInput.forceActiveFocus()
                                }
                            }
                        }
                    }
                }
            }

            // Dynamic Sort Pills (inline on wide screens, wraps seamlessly when Console narrows pane)
            Flow {
                id: sortPillsFlow
                spacing: 4
                property real naturalWidth: 120
                width: Math.min(searchSortFlow.width, Math.max(1, naturalWidth))

                function recalcW() {
                    var w = 0
                    var vis = 0
                    for (var i = 0; i < sortRepeater.count; ++i) {
                        var it = sortRepeater.itemAt(i)
                        if (it) {
                            if (vis > 0) w += spacing
                            w += it.implicitWidth
                            vis++
                        }
                    }
                    naturalWidth = Math.max(1, w)
                }

                Repeater {
                    id: sortRepeater
                    model: searchBar.view.isLocalMode
                           ? [
                               {"id": "updated", "label": "Recent"},
                               {"id": "files_desc", "label": "Most Files"},
                               {"id": "size_desc", "label": "Disk Size"},
                               {"id": "name", "label": "A–Z"}
                             ]
                           : (searchBar.view.activeCaps.sortOptions || [{"id": "popular", "label": "Popular"}])

                    onCountChanged: Qt.callLater(sortPillsFlow.recalcW)
                    onItemAdded: Qt.callLater(sortPillsFlow.recalcW)
                    onItemRemoved: Qt.callLater(sortPillsFlow.recalcW)

                    delegate: Rectangle {
                        readonly property var srt: modelData || ({})
                        readonly property bool isSel: (searchBar.view.bBridge ? searchBar.view.bBridge.activeSort : "popular") === srt.id

                        height: 28
                        implicitWidth: srtTxt.implicitWidth + 14
                        width: Math.min(sortPillsFlow.width, implicitWidth)
                        radius: 6
                        color: isSel ? "#172554" : "#121722"
                        border.color: isSel ? "#38BDF8" : "#1E293B"
                        border.width: 1
                        Springy { hover: srtMouse.containsMouse; pressed: srtMouse.pressed }
                        onImplicitWidthChanged: Qt.callLater(sortPillsFlow.recalcW)
                        Component.onCompleted: Qt.callLater(sortPillsFlow.recalcW)

                        Text {
                            id: srtTxt
                            anchors.centerIn: parent
                            text: srt.label || srt.id
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: isSel ? Font.Bold : Font.Normal
                            color: isSel ? "#F8FAFC" : "#94A3B8"
                        }
                        MouseArea {
                            id: srtMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (searchBar.view.bBridge) searchBar.view.bBridge.setSortOrder(srt.id)
                        }
                    }
                }
            }
        }

        // Dynamic Service Filter Chips (Dedicated Full-Width Scrollable Bar)
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            spacing: 4

            Rectangle {
                id: svcLeftBtn
                objectName: "servicesScrollLeftBtn"
                visible: svcFlickable.canScrollLeft
                Layout.preferredWidth: visible ? 22 : 0
                Layout.preferredHeight: 28
                Layout.alignment: Qt.AlignVCenter
                radius: 6
                color: svcLeftMouse.containsMouse ? "#1E293B" : "#121722"
                border.color: svcLeftMouse.containsMouse ? "#38BDF8" : "#1E293B"
                border.width: 1
                Springy { hover: svcLeftMouse.containsMouse; pressed: svcLeftMouse.pressed }

                Text {
                    anchors.centerIn: parent
                    text: "‹"
                    font.pixelSize: 15
                    font.weight: Font.Bold
                    color: "#94A3B8"
                }
                MouseArea {
                    id: svcLeftMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: searchBar.view.scrollServicesBy(-180)
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 34

                Flickable {
                    id: svcFlickable
                    objectName: "servicesFlickable"
                    anchors.fill: parent
                    contentWidth: svcRow.implicitWidth
                    contentHeight: 34
                    flickableDirection: Flickable.HorizontalFlick
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    readonly property bool canScrollHoriz: contentWidth > width + 2
                    readonly property bool canScrollLeft: contentX > 2
                    readonly property bool canScrollRight: canScrollHoriz && (contentX < contentWidth - width - 2)

                    onContentWidthChanged: {
                        var maxX = Math.max(0, contentWidth - width)
                        if (contentX > maxX) contentX = maxX
                    }
                    onWidthChanged: {
                        var maxX = Math.max(0, contentWidth - width)
                        if (contentX > maxX) contentX = maxX
                    }

                    WheelHandler {
                        id: svcWheel
                        target: null
                        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                        onWheel: function(event) {
                            if (!svcFlickable.canScrollHoriz) {
                                event.accepted = false
                                return
                            }
                            var dx = Math.abs(event.pixelDelta.x) > 0
                                ? -event.pixelDelta.x
                                : (Math.abs(event.angleDelta.x) > 0
                                    ? -event.angleDelta.x * 0.5
                                    : -event.angleDelta.y * 0.5)
                            if (Math.abs(dx) < 0.5) {
                                event.accepted = false
                                return
                            }
                            searchBar.view.scrollServicesBy(dx)
                            event.accepted = true
                        }
                    }

                    ScrollBar.horizontal: ScrollBar {
                        id: svcHBar
                        objectName: "servicesScrollBar"
                        policy: svcFlickable.canScrollHoriz ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                        interactive: true
                        height: 4
                        contentItem: Rectangle {
                            implicitHeight: 3
                            radius: 1.5
                            color: svcHBar.pressed ? "#38BDF8" : (svcHBar.hovered ? "#64748B" : "#334155")
                        }
                        background: Rectangle {
                            implicitHeight: 3
                            radius: 1.5
                            color: "transparent"
                        }
                    }

                    Row {
                        id: svcRow
                        height: 30
                        spacing: 5

                        Repeater {
                            model: searchBar.view.isLocalMode
                                   ? [
                                       {"id": "all", "label": "All Services"},
                                       {"id": "onlyfans", "label": "OnlyFans"},
                                       {"id": "fansly", "label": "Fansly"},
                                       {"id": "patreon", "label": "Patreon"},
                                       {"id": "fanbox", "label": "Fanbox"},
                                       {"id": "fantia", "label": "Fantia"},
                                       {"id": "candfans", "label": "CandFans"}
                                     ]
                                   : (searchBar.view.activeCaps.services || [{"id": "all", "label": "All Services"}])

                            delegate: Rectangle {
                                readonly property var sItem: modelData || ({})
                                readonly property bool isAct: (searchBar.view.bBridge ? searchBar.view.bBridge.activeService : "all") === sItem.id
                                readonly property bool isFavChip: !searchBar.view.isLocalMode && (sItem.id === "favorites")

                                objectName: "serviceChip_" + (sItem.id || "")
                                height: 27
                                anchors.verticalCenter: parent.verticalCenter
                                implicitWidth: sLbl.implicitWidth + 16
                                radius: 6
                                color: isFavChip
                                       ? (isAct ? "#422006" : "#1C160C")
                                       : (isAct ? "#1E293B" : "#121722")
                                border.color: isFavChip
                                              ? (isAct ? "#F59E0B" : "#78350F")
                                              : (isAct ? "#38BDF8" : "#1E293B")
                                border.width: 1
                                Springy { hover: sMouse.containsMouse; pressed: sMouse.pressed }

                                Text {
                                    id: sLbl
                                    anchors.centerIn: parent
                                    text: (sItem.label || sItem.id || "") + (isFavChip && !searchBar.view.isActiveProviderLoggedIn ? " 🔒" : "")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: (isAct || isFavChip) ? Font.Bold : Font.Normal
                                    color: isFavChip
                                           ? (isAct ? "#FBBF24" : "#FCD34D")
                                           : (isAct ? "#38BDF8" : "#94A3B8")
                                }
                                MouseArea {
                                    id: sMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: if (searchBar.view.bBridge) searchBar.view.bBridge.setServiceFilter(sItem.id)
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                id: svcRightBtn
                objectName: "servicesScrollRightBtn"
                visible: svcFlickable.canScrollRight
                Layout.preferredWidth: visible ? 22 : 0
                Layout.preferredHeight: 28
                Layout.alignment: Qt.AlignVCenter
                radius: 6
                color: svcRightMouse.containsMouse ? "#1E293B" : "#121722"
                border.color: svcRightMouse.containsMouse ? "#38BDF8" : "#1E293B"
                border.width: 1
                Springy { hover: svcRightMouse.containsMouse; pressed: svcRightMouse.pressed }

                Text {
                    anchors.centerIn: parent
                    text: "›"
                    font.pixelSize: 15
                    font.weight: Font.Bold
                    color: "#94A3B8"
                }
                MouseArea {
                    id: svcRightMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: searchBar.view.scrollServicesBy(180)
                }
            }
        }
    }
}
