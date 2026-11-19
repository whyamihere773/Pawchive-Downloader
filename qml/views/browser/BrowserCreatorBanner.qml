import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: creatorBanner
    required property var view
    readonly property string postSearchText: creatorPostSearchInput ? creatorPostSearchInput.text : ""
    objectName: "browserCreatorBanner"
    Layout.fillWidth: true
    Layout.preferredHeight: creatorBanner.view.hasSelectedCreator ? Math.max(82, bannerMainLayout.implicitHeight + 20) : 0
    visible: creatorBanner.view.hasSelectedCreator
    clip: true
    radius: 10
    color: "#111622"
    border.color: "#26324B"
    border.width: 1

    Behavior on Layout.preferredHeight {
        NumberAnimation { duration: 130; easing.type: Easing.OutCubic }
    }

    ColumnLayout {
        id: bannerMainLayout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 10
        spacing: 8

        Flow {
            id: creatorHeaderFlow
            Layout.fillWidth: true
            spacing: 10

            readonly property bool searchFitsInline: width >= 540

            RowLayout {
                id: creatorHeaderIdentityRow
                width: creatorHeaderFlow.searchFitsInline
                       ? Math.max(200, creatorHeaderFlow.width - creatorPostSearchBox.width - creatorHeaderFlow.spacing)
                       : creatorHeaderFlow.width
                spacing: 10

                // Back to Creators Grid button
                Rectangle {
                    Layout.preferredHeight: 34
                    Layout.preferredWidth: backRow.implicitWidth + 18
                    Layout.alignment: Qt.AlignVCenter
                    radius: 7
                    color: backMouse.containsMouse ? "#1E293B" : "#151C2B"
                    border.color: "#38BDF8"
                    border.width: 1
                    Springy { hover: backMouse.containsMouse; pressed: backMouse.pressed }

                    Row {
                        id: backRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "←"; font.pixelSize: 13; font.bold: true; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "All Creators"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: backMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (creatorBanner.view.bBridge) creatorBanner.view.bBridge.closeCreator()
                    }
                }

                // Creator Avatar
                Rectangle {
                    Layout.preferredWidth: 44
                    Layout.preferredHeight: 44
                    Layout.alignment: Qt.AlignVCenter
                    radius: 22
                    color: "#1E293B"
                    border.color: "#38BDF8"
                    border.width: 1.5
                    clip: true

                    Text {
                        anchors.centerIn: parent
                        visible: hdrAvatarImg.status !== Image.Ready || hdrAvatarImg.implicitWidth <= 2
                        text: ((creatorBanner.view.selectedCreator.name || creatorBanner.view.selectedCreator.creator_name || "?").trim().charAt(0) || "?").toUpperCase()
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        color: "#7DD3FC"
                    }

                    Image {
                        id: hdrAvatarImg
                        anchors.fill: parent
                        opacity: (status === Image.Ready && implicitWidth > 2) ? 1.0 : 0.0
                        source: creatorBanner.view.browserThumbUrl(creatorBanner.view.selectedCreator.avatar_url, creatorBanner.view.selectedCreator.provider_id || creatorBanner.view.activeProvider)
                        sourceSize: Qt.size(96, 96)
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                    }
                }

                // Creator Name & Telemetry Badges
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3

                    Flow {
                        id: creatorNameBadgesFlow
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            width: Math.min(implicitWidth, Math.min(260, Math.max(80, creatorNameBadgesFlow.width)))
                            text: creatorBanner.view.selectedCreator.name || creatorBanner.view.selectedCreator.creator_name || ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                        }
                        Rectangle {
                            height: 20
                            width: Math.min(creatorNameBadgesFlow.width, hdrSvcTxt.implicitWidth + 12)
                            radius: 5
                            color: "#1E293B"
                            Text {
                                id: hdrSvcTxt
                                anchors.centerIn: parent
                                text: (creatorBanner.view.selectedCreator.service_label || creatorBanner.view.selectedCreator.service || "").toUpperCase()
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.weight: Font.Bold
                                color: "#38BDF8"
                            }
                        }
                        UnimportedTriangleBadge {
                            objectName: "bannerUnimportedBadge"
                            visible: !creatorBanner.view.isLocalMode && !!creatorBanner.view.selectedCreator.is_unimported
                            width: 22
                            height: 22
                            tooltipText: "Previews only (creator not yet imported)"
                        }
                        // Local Drive Badges
                        Repeater {
                            model: creatorBanner.view.selectedCreator.local_drives || []
                            delegate: Rectangle {
                                height: 20
                                width: Math.min(creatorNameBadgesFlow.width, drvBadgeTxt.implicitWidth + 12)
                                radius: 5
                                color: "#064E3B"
                                border.color: "#10B981"
                                border.width: 1
                                Text {
                                    id: drvBadgeTxt
                                    anchors.centerIn: parent
                                    text: "💽 " + modelData
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: "#A7F3D0"
                                }
                            }
                        }

                        // Online-mode On-Disk Post Completeness Summary Chips (current page)
                        Rectangle {
                            visible: !creatorBanner.view.isLocalMode && !!creatorBanner.view.selectedCreator.is_on_disk && Number(creatorBanner.view.selectedCreator.page_disk_complete || 0) > 0
                            height: 20
                            width: Math.min(creatorNameBadgesFlow.width, diskFullChipTxt.implicitWidth + 12)
                            radius: 5
                            color: "#064E3B"
                            border.color: "#10B981"
                            border.width: 1
                            Text {
                                id: diskFullChipTxt
                                anchors.centerIn: parent
                                text: "✓ " + Number(creatorBanner.view.selectedCreator.page_disk_complete || 0) + " Complete"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.weight: Font.Bold
                                color: "#6EE7B7"
                            }
                            HoverHandler { id: diskFullChipHover }
                            ToolTip.visible: diskFullChipHover.hovered
                            ToolTip.delay: 250
                            ToolTip.text: "Green-outlined posts have all files physically present on disk"
                        }

                        Rectangle {
                            visible: !creatorBanner.view.isLocalMode && !!creatorBanner.view.selectedCreator.is_on_disk && Number(creatorBanner.view.selectedCreator.page_disk_partial || 0) > 0
                            height: 20
                            width: Math.min(creatorNameBadgesFlow.width, diskPartChipTxt.implicitWidth + 12)
                            radius: 5
                            color: "#451A03"
                            border.color: "#F59E0B"
                            border.width: 1
                            Text {
                                id: diskPartChipTxt
                                anchors.centerIn: parent
                                text: "◐ " + Number(creatorBanner.view.selectedCreator.page_disk_partial || 0) + " Partial"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.weight: Font.Bold
                                color: "#FCD34D"
                            }
                            HoverHandler { id: diskPartChipHover }
                            ToolTip.visible: diskPartChipHover.hovered
                            ToolTip.delay: 250
                            ToolTip.text: "Yellow-outlined posts have some files on disk (others were pruned or skipped)"
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: creatorBanner.view.isLocalMode
                              ? (Number(creatorBanner.view.bBridge ? creatorBanner.view.bBridge.creatorPostsTotal : 0) + " local posts • " + Number(creatorBanner.view.selectedCreator.local_file_count || 0) + " files on disk (" + creatorBanner.view.formatBytes(creatorBanner.view.selectedCreator.local_size_bytes) + ")")
                              : (creatorBanner.view.bBridge && creatorBanner.view.bBridge.creatorSection === "dms"
                                 ? (Number(creatorBanner.view.bBridge.creatorPostsTotal || 0) + " DM(s) available")
                                 : (Number(creatorBanner.view.bBridge ? creatorBanner.view.bBridge.creatorPostsTotal : 0) + " posts available"
                                    + (Number(creatorBanner.view.selectedCreator.dm_count || 0) > 0 ? (" • 💬 " + Number(creatorBanner.view.selectedCreator.dm_count || 0) + " DMs") : "")))
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                }
            }

            // Search within Creator's Posts / DMs (wraps seamlessly to own row when Console narrows pane)
            Rectangle {
                id: creatorPostSearchBox
                width: creatorHeaderFlow.searchFitsInline ? 195 : creatorHeaderFlow.width
                height: 32
                radius: 7
                color: creatorPostSearchInput.activeFocus ? "#0B0D12" : "#090C12"
                border.color: creatorPostSearchInput.activeFocus ? "#38BDF8" : (creatorPostSearchBoxMouse.containsMouse ? "#475569" : "#1E293B")
                border.width: creatorPostSearchInput.activeFocus ? 1.5 : 1

                TextBarContextArea {
                    id: creatorPostSearchBoxMouse
                    target: creatorPostSearchInput
                    focusOnLeftClick: true
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 5
                    Text { text: "🔍"; font.pixelSize: 11 }
                    TextField {
                        id: creatorPostSearchInput
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        verticalAlignment: TextInput.AlignVCenter
                        leftPadding: 2
                        rightPadding: 2
                        placeholderText: (creatorBanner.view.bBridge && creatorBanner.view.bBridge.creatorSection === "dms") ? "Filter creator's DMs…" : "Filter creator's posts…"
                        placeholderTextColor: "#64748B"
                        color: "#F8FAFC"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        background: Item {}
                        clip: true
                        selectByMouse: true
                        onAccepted: if (creatorBanner.view.bBridge) creatorBanner.view.bBridge.loadCreatorPosts(0, text)
                        TextBarContextArea {}
                    }
                    Text {
                        visible: creatorPostSearchInput.text.length > 0
                        text: "✕"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                creatorPostSearchInput.text = ""
                                if (creatorBanner.view.bBridge) creatorBanner.view.bBridge.loadCreatorPosts(0, "")
                                creatorPostSearchInput.forceActiveFocus()
                            }
                        }
                    }
                }
            }
        }

        // Responsive Action Toolbar (wraps cleanly on narrower panes so buttons never clip)
        Flow {
            id: creatorActionsFlow
            Layout.fillWidth: true
            spacing: 8

            // Creator Posts | DMs Section Toggle (when active provider supports DMs)
            Rectangle {
                id: creatorSectionToggle
                visible: !creatorBanner.view.isLocalMode && !!(creatorBanner.view.bBridge && creatorBanner.view.bBridge.creatorSupportsDms)
                height: 30
                width: sectionToggleRow.implicitWidth + 8
                radius: 7
                color: "#090C12"
                border.color: "#1E293B"
                border.width: 1

                Row {
                    id: sectionToggleRow
                    anchors.centerIn: parent
                    spacing: 3

                    Rectangle {
                        height: 24
                        width: postsSecTxt.implicitWidth + 14
                        radius: 5
                        color: (!creatorBanner.view.bBridge || creatorBanner.view.bBridge.creatorSection !== "dms") ? "#0284C7" : (postsSecMouse.containsMouse ? "#151E2E" : "transparent")
                        Text {
                            id: postsSecTxt
                            anchors.centerIn: parent
                            text: "Posts"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: (!creatorBanner.view.bBridge || creatorBanner.view.bBridge.creatorSection !== "dms") ? Font.Bold : Font.Normal
                            color: (!creatorBanner.view.bBridge || creatorBanner.view.bBridge.creatorSection !== "dms") ? "#FFFFFF" : "#94A3B8"
                        }
                        MouseArea {
                            id: postsSecMouse
                            objectName: "creatorSection_posts"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (creatorBanner.view.bBridge) {
                                    creatorPostSearchInput.text = ""
                                    creatorBanner.view.bBridge.setCreatorSection("posts")
                                }
                            }
                        }
                    }

                    Rectangle {
                        height: 24
                        width: dmsSecTxt.implicitWidth + 14
                        radius: 5
                        color: (creatorBanner.view.bBridge && creatorBanner.view.bBridge.creatorSection === "dms") ? "#7C3AED" : (dmsSecMouse.containsMouse ? "#151E2E" : "transparent")
                        Text {
                            id: dmsSecTxt
                            anchors.centerIn: parent
                            text: "💬 DMs" + (Number(creatorBanner.view.selectedCreator.dm_count || 0) > 0 ? (" (" + Number(creatorBanner.view.selectedCreator.dm_count || 0) + ")") : "")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: (creatorBanner.view.bBridge && creatorBanner.view.bBridge.creatorSection === "dms") ? Font.Bold : Font.Normal
                            color: (creatorBanner.view.bBridge && creatorBanner.view.bBridge.creatorSection === "dms") ? "#FFFFFF" : "#C4B5FD"
                        }
                        MouseArea {
                            id: dmsSecMouse
                            objectName: "creatorSection_dms"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (creatorBanner.view.bBridge) {
                                    creatorPostSearchInput.text = ""
                                    creatorBanner.view.bBridge.setCreatorSection("dms")
                                }
                            }
                        }
                    }
                }
            }

            // Queue All Creator DMs Button (visible when viewing DMs section)
            Rectangle {
                visible: !creatorBanner.view.isLocalMode && !!(creatorBanner.view.bBridge && creatorBanner.view.bBridge.creatorSection === "dms")
                height: 30
                width: dlDmsRow.implicitWidth + 16
                radius: 7
                color: dlDmsMouse.containsMouse ? "#8B5CF6" : "#6D28D9"
                border.color: "#A78BFA"
                border.width: 1
                Springy { hover: dlDmsMouse.containsMouse; pressed: dlDmsMouse.pressed }

                Row {
                    id: dlDmsRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text { text: "⬇"; font.pixelSize: 11; color: "#FFFFFF"; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "Download All DMs"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#FFFFFF"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: dlDmsMouse
                    objectName: "downloadAllDmsMouse"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (!creatorBanner.view.bBridge) return
                        var dmsUrl = creatorBanner.view.bBridge.getSelectedCreatorDmsUrl ? creatorBanner.view.bBridge.getSelectedCreatorDmsUrl() : ""
                        if (dmsUrl) {
                            var c = creatorBanner.view.selectedCreator || ({})
                            var cname = String(c.name || c.creator_name || "Creator")
                            creatorBanner.view.openDownloadModalForItems([{
                                url: dmsUrl,
                                title: cname + " — All DMs",
                                creator_name: cname,
                                creator_id: String(c.creator_id || c.id || ""),
                                service: String(c.service || ""),
                                service_label: String(c.service_label || c.service || ""),
                                item_type: "creator"
                            }], "Download All DMs (" + cname + ")", true, "dms")
                        } else {
                            creatorBanner.view.bBridge.queueAllCreatorDms()
                        }
                    }
                }
            }

            // LOCAL MODE: Move Creator to Another Drive Button
            Rectangle {
                visible: creatorBanner.view.isLocalMode
                height: 30
                width: mvHdrRow.implicitWidth + 18
                radius: 7
                color: mvHdrMouse.containsMouse ? "#065F46" : "#064E3B"
                border.color: "#10B981"
                border.width: 1
                Springy { hover: mvHdrMouse.containsMouse; pressed: mvHdrMouse.pressed }

                Row {
                    id: mvHdrRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "💽"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "Move Creator to Drive…"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#ECFDF5"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: mvHdrMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Relocate this artist's downloaded files to another disk while keeping Archive & Watchlist in sync"
                    onClicked: {
                        creatorBanner.view.openRelocateModal(creatorBanner.view.selectedCreator)
                    }
                }
            }

            // Check Newer Posts Online Button (Local & Online Modes)
            Rectangle {
                id: checkNewPostsBtn
                visible: !!(creatorBanner.view.selectedCreator && creatorBanner.view.selectedCreator.key && (creatorBanner.view.isLocalMode || creatorBanner.view.selectedCreator.url))
                height: 30
                width: chkNewRow.implicitWidth + 18
                radius: 7
                color: (creatorBanner.view.bBridge && creatorBanner.view.bBridge.newPostsCount > 0)
                       ? (chkNewMouse.containsMouse ? "#065F46" : "#064E3B")
                       : (chkNewMouse.containsMouse ? "#1E293B" : "#151C2B")
                border.color: (creatorBanner.view.bBridge && creatorBanner.view.bBridge.newPostsCount > 0) ? "#10B981" : "#38BDF8"
                border.width: 1
                Springy { hover: chkNewMouse.containsMouse; pressed: chkNewMouse.pressed }

                Row {
                    id: chkNewRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        text: (creatorBanner.view.bBridge && creatorBanner.view.bBridge.isCheckingNewPosts) ? "⌛" : "🔎"
                        font.pixelSize: 12
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: (creatorBanner.view.bBridge && creatorBanner.view.bBridge.isCheckingNewPosts)
                              ? "Checking…"
                              : ((creatorBanner.view.bBridge && creatorBanner.view.bBridge.newPostsCount > 0)
                                 ? ("Newer Posts (" + creatorBanner.view.bBridge.newPostsCount + ")")
                                 : "Check Newer Posts")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: (creatorBanner.view.bBridge && creatorBanner.view.bBridge.newPostsCount > 0) ? "#ECFDF5" : "#E0F2FE"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: chkNewMouse
                    objectName: "checkNewPostsBtnMouse"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Check online for newer posts by this creator not yet on disk"
                    onClicked: {
                        if (creatorBanner.view.bBridge) {
                            creatorBanner.view.bBridge.checkCreatorNewPosts(creatorBanner.view.selectedCreator)
                            creatorBanner.view.openNewPostsModal()
                        }
                    }
                }
            }

            // Favorite / Bookmark Creator on Account Button (Online Mode)
            Rectangle {
                objectName: "bannerCreatorFavBtn"
                visible: !creatorBanner.view.isLocalMode && !!creatorBanner.view.activeCaps.supportsFavorites
                readonly property bool isFav: !!creatorBanner.view.selectedCreator.is_favorited
                height: 30
                width: bannerFavRow.implicitWidth + 18
                radius: 7
                color: isFav
                       ? (bannerFavMouse.containsMouse ? "#92400E" : "#78350F")
                       : (bannerFavMouse.containsMouse ? "#1E293B" : "#151C2B")
                border.color: isFav ? "#F59E0B" : "#475569"
                border.width: 1
                Springy { hover: bannerFavMouse.containsMouse; pressed: bannerFavMouse.pressed }

                Row {
                    id: bannerFavRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text {
                        text: parent.parent.isFav ? "★" : "☆"
                        font.pixelSize: 13
                        color: parent.parent.isFav ? "#FBBF24" : "#94A3B8"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: parent.parent.isFav ? "Favorited" : "Favorite"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: parent.parent.isFav ? "#FDE68A" : "#CBD5E1"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: bannerFavMouse
                    objectName: "bannerCreatorFavMouse"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (creatorBanner.view.bBridge && creatorBanner.view.selectedCreator) creatorBanner.view.bBridge.toggleFavoriteCreator(creatorBanner.view.selectedCreator)
                }
            }

            // Mark Whole Creator Button
            Rectangle {
                visible: !creatorBanner.view.isLocalMode
                readonly property bool isMarked: !!creatorBanner.view.selectedCreator.is_marked
                height: 30
                width: mkCreatorRow.implicitWidth + 18
                radius: 7
                color: isMarked ? "#2E1065" : (mkCreatorMouse.containsMouse ? "#1E293B" : "#151C2B")
                border.color: isMarked ? "#A78BFA" : "#38BDF8"
                border.width: 1
                Springy { hover: mkCreatorMouse.containsMouse; pressed: mkCreatorMouse.pressed }

                Row {
                    id: mkCreatorRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: parent.parent.isMarked ? "✔" : "🛒"; font.pixelSize: 11; color: "#C4B5FD"; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: parent.parent.isMarked ? "Creator Marked" : "Mark Creator"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: mkCreatorMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (creatorBanner.view.bBridge) creatorBanner.view.bBridge.toggleMarkItem(creatorBanner.view.selectedCreator)
                }
            }

            // Download Entire Creator Immediately
            Rectangle {
                readonly property bool isDispatched: creatorBanner.view.isUrlDispatched(creatorBanner.view.selectedCreator.url)
                visible: !creatorBanner.view.isLocalMode && !!(creatorBanner.view.selectedCreator.url)
                height: 30
                width: dlCreatorRow.implicitWidth + 18
                radius: 7
                color: isDispatched
                       ? (dlCreatorMouse.containsMouse ? "#0F766E" : "#115E59")
                       : (dlCreatorMouse.containsMouse ? "#059669" : "#047857")
                border.color: isDispatched ? "#5EEAD4" : "#34D399"
                border.width: 1
                Springy { hover: dlCreatorMouse.containsMouse; pressed: dlCreatorMouse.pressed }

                Row {
                    id: dlCreatorRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: parent.parent.isDispatched ? "✓" : "🚀"; font.pixelSize: 11; color: "#FFFFFF"; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: parent.parent.isDispatched ? "Started" : "Download All"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#FFFFFF"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: dlCreatorMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: parent.isDispatched ? "Sent to Downloader — click again to queue another download" : "Send this creator directly to the Downloader"
                    onClicked: creatorBanner.view.triggerItemDownload(
                        creatorBanner.view.selectedCreator.url,
                        true,
                        creatorBanner.view.selectedCreator.name || creatorBanner.view.selectedCreator.creator_name || "",
                        creatorBanner.view.selectedCreator
                    )
                }
            }

            // Copy Creator Link Button (always available for active creator)
            Rectangle {
                id: creatorCopyLinkBtn
                objectName: "creatorCopyLinkBtn"
                property bool justCopied: false
                visible: !!creatorBanner.view.selectedCreator && !!(creatorBanner.view.selectedCreator.key || creatorBanner.view.selectedCreator.url || (creatorBanner.view.selectedCreator.local_dirs && creatorBanner.view.selectedCreator.local_dirs.length > 0))
                height: 30
                width: creatorCopyRow.implicitWidth + 16
                radius: 7
                color: justCopied
                       ? "#064E3B"
                       : (creatorCopyMouse.containsMouse ? "#1E293B" : "#151C2B")
                border.color: justCopied ? "#10B981" : (creatorCopyMouse.containsMouse ? "#38BDF8" : "#334155")
                border.width: 1
                Springy { hover: creatorCopyMouse.containsMouse; pressed: creatorCopyMouse.pressed }
                Timer {
                    id: creatorCopyResetTimer
                    interval: 1500
                    onTriggered: creatorCopyLinkBtn.justCopied = false
                }
                Row {
                    id: creatorCopyRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text {
                        text: creatorCopyLinkBtn.justCopied ? "✓" : "🔗"
                        font.pixelSize: 11
                        color: creatorCopyLinkBtn.justCopied ? "#6EE7B7" : "#7DD3FC"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: creatorCopyLinkBtn.justCopied ? "Copied" : "Copy Link"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: creatorCopyLinkBtn.justCopied ? "#A7F3D0" : "#E2E8F0"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: creatorCopyMouse
                    objectName: "creatorCopyLinkMouse"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Copy link to this creator"
                    onClicked: {
                        if (creatorBanner.view.bBridge && creatorBanner.view.bBridge.copyCreatorLink(creatorBanner.view.selectedCreator)) {
                            creatorCopyLinkBtn.justCopied = true
                            creatorCopyResetTimer.restart()
                        }
                    }
                }
            }
        }
    }
}
