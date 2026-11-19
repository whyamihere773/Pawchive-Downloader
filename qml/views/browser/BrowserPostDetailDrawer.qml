import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: postDetailDrawer
    required property var view
    objectName: "postDetailDrawer"
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    anchors.right: parent.right
    width: postDetailDrawer.view.hasSelectedPost ? (postDetailDrawer.view.postViewerExpanded ? Math.min(920, parent.width * 0.92) : Math.min(500, Math.max(Math.min(parent.width, 320), parent.width * 0.52))) : 0
    visible: width > 1
    clip: true
    radius: 10
    color: "#111622"
    border.color: "#38BDF8"
    border.width: 1

    // Heavy Newtonian Slide-Over Physics (Mass = 1.85)
    Behavior on width {
        NumberAnimation { duration: 135; easing.type: Easing.OutCubic }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // Drawer Header (Title + Window Controls)
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            UnimportedTriangleBadge {
                objectName: "drawerUnimportedBadge"
                visible: !postDetailDrawer.view.isLocalMode && !!postDetailDrawer.view.selectedPost.is_unimported
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
                width: 24
                height: 24
                tooltipText: "Haven't archived this post yet (previews only)"
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 80
                spacing: 2

                Text {
                    Layout.fillWidth: true
                    text: postDetailDrawer.view.selectedPost.title || "Post Details"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    color: "#F8FAFC"
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    visible: !!(postDetailDrawer.view.selectedPost.creator_name || postDetailDrawer.view.selectedPost.service_label || postDetailDrawer.view.selectedPost.is_dm)
                    text: (postDetailDrawer.view.selectedPost.is_dm ? "💬 DM  •  " : "")
                          + (postDetailDrawer.view.selectedPost.creator_name || "")
                          + (postDetailDrawer.view.selectedPost.service_label ? ("  •  " + postDetailDrawer.view.selectedPost.service_label) : "")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: postDetailDrawer.view.selectedPost.is_dm ? "#C4B5FD" : "#7DD3FC"
                    elide: Text.ElideRight
                }
            }

            // Expand / Compact Post Viewer Toggle
            Rectangle {
                Layout.preferredHeight: 28
                Layout.preferredWidth: Math.max(28, dExpTxt.implicitWidth + 12)
                radius: 6
                color: dExpMouse.containsMouse ? "#28354E" : "#1E293B"
                border.color: postDetailDrawer.view.postViewerExpanded ? "#38BDF8" : "#334155"
                border.width: 1
                Springy { hover: dExpMouse.containsMouse; pressed: dExpMouse.pressed }

                Text {
                    id: dExpTxt
                    anchors.centerIn: parent
                    text: postDetailDrawer.view.postViewerExpanded ? "↙" : "⛶"
                    font.pixelSize: 12
                    color: "#E2E8F0"
                }
                MouseArea {
                    id: dExpMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: postDetailDrawer.view.postViewerExpanded ? "Compact post drawer" : "Expand post viewer"
                    onClicked: postDetailDrawer.view.postViewerExpanded = !postDetailDrawer.view.postViewerExpanded
                }
            }

            // Close Drawer Button
            Rectangle {
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                radius: 6
                color: "#1E293B"
                Text { anchors.centerIn: parent; text: "✕"; font.pixelSize: 12; color: "#94A3B8" }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (postDetailDrawer.view.bBridge) postDetailDrawer.view.bBridge.closePostDetail()
                }
            }
        }

        // Responsive Drawer Actions Toolbar (wraps cleanly on narrower drawer / Console ON)
        Flow {
            id: drawerActionsFlow
            Layout.fillWidth: true
            spacing: 6

            // Open In-App Lightbox Gallery Button
            Rectangle {
                visible: postDetailDrawer.view.postViewableMedia.length > 0
                height: 28
                width: Math.min(drawerActionsFlow.width, dGalTxt.implicitWidth + 14)
                radius: 6
                color: dGalMouse.containsMouse ? "#0EA5E9" : "#0369A1"
                Springy { hover: dGalMouse.containsMouse; pressed: dGalMouse.pressed }

                Text {
                    id: dGalTxt
                    anchors.centerIn: parent
                    text: "👁 View Media (" + postDetailDrawer.view.postViewableMedia.length + ")"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                }
                MouseArea {
                    id: dGalMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: postDetailDrawer.view.openPostMediaGallery(postDetailDrawer.view.selectedPost, 0)
                }
            }

            // Mark Post Button
            Rectangle {
                visible: !postDetailDrawer.view.isLocalMode
                readonly property bool isM: !!postDetailDrawer.view.selectedPost.is_marked
                height: 28
                width: Math.min(drawerActionsFlow.width, dMkTxt.implicitWidth + 14)
                radius: 6
                color: isM ? "#0284C7" : "#1E293B"
                Springy { hover: dMkMouse.containsMouse; pressed: dMkMouse.pressed }

                Text {
                    id: dMkTxt
                    anchors.centerIn: parent
                    text: parent.isM ? "✔ Marked" : "🛒 Mark"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                }
                MouseArea {
                    id: dMkMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (postDetailDrawer.view.bBridge) postDetailDrawer.view.bBridge.toggleMarkItem(postDetailDrawer.view.selectedPost)
                }
            }

            // Direct Download Post Button
            Rectangle {
                id: dDlBtn
                readonly property bool isDispatched: postDetailDrawer.view.isUrlDispatched(postDetailDrawer.view.selectedPost.url)
                visible: !postDetailDrawer.view.isLocalMode && !!(postDetailDrawer.view.selectedPost.url)
                height: 28
                width: Math.min(drawerActionsFlow.width, dDlTxt.implicitWidth + 16)
                radius: 6
                color: isDispatched
                       ? (dDlMouse.containsMouse ? "#0F766E" : "#115E59")
                       : (dDlMouse.containsMouse ? "#10B981" : "#059669")
                border.color: isDispatched ? "#5EEAD4" : "transparent"
                border.width: isDispatched ? 1 : 0
                Springy { hover: dDlMouse.containsMouse; pressed: dDlMouse.pressed }

                Text {
                    id: dDlTxt
                    anchors.centerIn: parent
                    text: dDlBtn.isDispatched ? "✓ Sent" : "🚀 Download"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                }
                MouseArea {
                    id: dDlMouse
                    objectName: "postDownloadBtnMouse"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: dDlBtn.isDispatched ? "Sent to Downloader — click again to queue another download" : "Send this post directly to the Downloader"
                    onClicked: postDetailDrawer.view.triggerItemDownload(
                        postDetailDrawer.view.selectedPost.url,
                        true,
                        postDetailDrawer.view.selectedPost.title || postDetailDrawer.view.selectedPost.creator_name || "",
                        postDetailDrawer.view.selectedPost
                    )
                }
            }

            // Force Redownload Post Button (works in both Local & Online Modes)
            Rectangle {
                id: dRedlBtn
                visible: !!(postDetailDrawer.view.selectedPost.url || (postDetailDrawer.view.selectedPost.service && postDetailDrawer.view.selectedPost.service !== "local" && postDetailDrawer.view.selectedPost.creator_id && postDetailDrawer.view.selectedPost.post_id && postDetailDrawer.view.selectedPost.post_id !== "root_files"))
                height: 28
                width: Math.min(drawerActionsFlow.width, dRedlTxt.implicitWidth + 16)
                radius: 6
                color: dRedlMouse.containsMouse ? "#0369A1" : "#1E293B"
                border.color: "#38BDF8"
                border.width: 1
                Springy { hover: dRedlMouse.containsMouse; pressed: dRedlMouse.pressed }

                Text {
                    id: dRedlTxt
                    anchors.centerIn: parent
                    text: "↻ Redownload"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#E0F2FE"
                }
                MouseArea {
                    id: dRedlMouse
                    objectName: "postRedownloadBtnMouse"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Redownload all files for this post freshly (overwrites existing files & bypasses archive skip)"
                    onClicked: if (postDetailDrawer.view.bBridge) { if (postDetailDrawer.view.bBridge.redownloadPostAsync) postDetailDrawer.view.bBridge.redownloadPostAsync(postDetailDrawer.view.selectedPost); else postDetailDrawer.view.bBridge.redownloadPost(postDetailDrawer.view.selectedPost) }
                }
            }

            // Copy Current Post Link Button (always available inside drawer)
            Rectangle {
                id: dCopyLinkBtn
                objectName: "postCopyLinkBtn"
                property bool justCopied: false
                visible: !!postDetailDrawer.view.selectedPost && !!(postDetailDrawer.view.selectedPost.key || postDetailDrawer.view.selectedPost.post_id || postDetailDrawer.view.selectedPost.url || postDetailDrawer.view.selectedPost.local_folder)
                height: 28
                width: Math.min(drawerActionsFlow.width, dCopyTxt.implicitWidth + 16)
                radius: 6
                color: justCopied
                       ? "#064E3B"
                       : (dCopyMouse.containsMouse ? "#1E293B" : "#151C2B")
                border.color: justCopied ? "#10B981" : (dCopyMouse.containsMouse ? "#38BDF8" : "#334155")
                border.width: 1
                Springy { hover: dCopyMouse.containsMouse; pressed: dCopyMouse.pressed }
                Timer {
                    id: dCopyResetTimer
                    interval: 1500
                    onTriggered: dCopyLinkBtn.justCopied = false
                }

                Text {
                    id: dCopyTxt
                    anchors.centerIn: parent
                    text: dCopyLinkBtn.justCopied ? "✓ Copied" : "🔗 Copy Link"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: dCopyLinkBtn.justCopied ? "#A7F3D0" : "#E2E8F0"
                }
                MouseArea {
                    id: dCopyMouse
                    objectName: "postCopyLinkBtnMouse"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Copy link to the current post"
                    onClicked: {
                        if (postDetailDrawer.view.bBridge && postDetailDrawer.view.bBridge.copyPostLink(postDetailDrawer.view.selectedPost)) {
                            dCopyLinkBtn.justCopied = true
                            dCopyResetTimer.restart()
                        }
                    }
                }
            }
        }

        // Post Metadata & Tags
        Flow {
            Layout.fillWidth: true
            spacing: 5
            readonly property string postDiskStatus: (!postDetailDrawer.view.isLocalMode && postDetailDrawer.view.selectedPost && postDetailDrawer.view.selectedPost.disk_status) ? String(postDetailDrawer.view.selectedPost.disk_status) : "none"
            visible: (postDetailDrawer.view.selectedPost.tags && postDetailDrawer.view.selectedPost.tags.length > 0) || !!(postDetailDrawer.view.selectedPost.published_at) || postDiskStatus === "complete" || postDiskStatus === "partial"

            Rectangle {
                visible: parent.postDiskStatus === "complete" || parent.postDiskStatus === "partial"
                readonly property bool isFull: parent.postDiskStatus === "complete"
                readonly property int locCnt: Number(postDetailDrawer.view.selectedPost.local_file_count || 0)
                readonly property int expCnt: Number(postDetailDrawer.view.selectedPost.expected_file_count || postDetailDrawer.view.selectedPost.file_count || 0)
                height: 20
                width: detailDiskTxt.implicitWidth + 12
                radius: 4
                color: isFull ? "#064E3B" : "#451A03"
                border.color: isFull ? "#10B981" : "#F59E0B"
                border.width: 1
                Text {
                    id: detailDiskTxt
                    anchors.centerIn: parent
                    text: parent.isFull
                        ? (parent.expCnt > 0 ? ("✓ Complete on Disk (" + parent.locCnt + "/" + parent.expCnt + ")") : "✓ Complete on Disk")
                        : (parent.expCnt > 0 ? ("◐ Partial on Disk (" + parent.locCnt + "/" + parent.expCnt + ")") : "◐ Partial on Disk")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: Font.Bold
                    color: parent.isFull ? "#6EE7B7" : "#FCD34D"
                }
            }

            Rectangle {
                visible: !!(postDetailDrawer.view.selectedPost.published_at)
                height: 20
                width: pubTxt.implicitWidth + 12
                radius: 4
                color: "#1E293B"
                Text {
                    id: pubTxt
                    anchors.centerIn: parent
                    text: "📅 " + (postDetailDrawer.view.selectedPost.published_at || "")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#94A3B8"
                }
            }

            Repeater {
                model: postDetailDrawer.view.selectedPost.tags || []
                delegate: Rectangle {
                    height: 20
                    width: tgTxt.implicitWidth + 12
                    radius: 4
                    color: "#172554"
                    Text {
                        id: tgTxt
                        anchors.centerIn: parent
                        text: "#" + modelData
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#7DD3FC"
                    }
                }
            }
        }

        // Post Description Body (from API or local post_info.txt)
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(postDetailDrawer.view.postViewerExpanded ? 180 : 120, Math.max(48, descBodyTxt.implicitHeight + 18))
            visible: !!((postDetailDrawer.view.selectedPost.content_full || postDetailDrawer.view.selectedPost.content_snippet || "").trim())
            radius: 7
            color: "#090C12"
            border.color: "#1E293B"
            border.width: 1
            clip: true

            SmoothFlickable {
                anchors.fill: parent
                anchors.margins: 8
                contentWidth: width
                contentHeight: descBodyTxt.implicitHeight

                TextEdit {
                    id: descBodyTxt
                    width: parent.width
                    readOnly: true
                    selectByMouse: true
                    selectionColor: "#0284C7"
                    selectedTextColor: "#FFFFFF"
                    text: postDetailDrawer.view.selectedPost.content_full || postDetailDrawer.view.selectedPost.content_snippet || ""
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#CBD5E1"
                    wrapMode: TextEdit.Wrap
                    TextBarContextArea {}
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text {
                text: "Post Media & Files (" + ((postDetailDrawer.view.selectedPost.attachments || []).length) + ")"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: Font.Bold
                color: "#94A3B8"
            }
            Text {
                Layout.fillWidth: true
                visible: postDetailDrawer.view.postViewableMedia.length > 0
                text: "Click any picture, GIF, video, or audio to view in-app"
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideRight
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                color: "#64748B"
            }
        }

        // Post Attachments Sort Bar
        Flow {
            Layout.fillWidth: true
            spacing: 5
            visible: postDetailDrawer.view.sortedPostAttachments.length > 1

            Repeater {
                model: [
                    {"id": "default",   "label": "Default"},
                    {"id": "name_asc",  "label": "Name A–Z"},
                    {"id": "name_desc", "label": "Name Z–A"},
                    {"id": "newest",    "label": "Newest"},
                    {"id": "oldest",    "label": "Oldest"},
                    {"id": "size_desc", "label": "Largest"},
                    {"id": "size_asc",  "label": "Smallest"},
                    {"id": "type",      "label": "Type"}
                ]

                delegate: Rectangle {
                    readonly property var sItem: modelData || ({})
                    readonly property bool isSel: postDetailDrawer.view.postAttSortMode === sItem.id
                    height: 22
                    width: attSortLbl.implicitWidth + 14
                    radius: 5
                    color: isSel ? "#0E2239" : (attSortMouse.containsMouse ? "#1E293B" : "#151C2B")
                    border.color: isSel ? "#38BDF8" : "#273549"
                    border.width: 1

                    Text {
                        id: attSortLbl
                        anchors.centerIn: parent
                        text: sItem.label || ""
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: isSel ? Font.Bold : Font.Medium
                        color: isSel ? "#38BDF8" : "#94A3B8"
                    }
                    MouseArea {
                        id: attSortMouse
                        objectName: "postAttSort_" + (sItem.id || "")
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: postDetailDrawer.view.postAttSortMode = sItem.id
                    }
                }
            }
        }

        // Virtualized In-App Visual Media & Attachments Grid
        SmoothGridView {
            id: attsGridView
            Layout.fillWidth: true
            Layout.fillHeight: true
            readonly property int cols: Math.max(1, postDetailDrawer.view.postViewerExpanded ? Math.floor(width / 220) : Math.floor(width / 195))
            cellWidth: Math.floor((width - 8) / Math.max(1, cols))
            cellHeight: postDetailDrawer.view.postViewerExpanded ? 196 : 168
            cacheBuffer: 420
            model: postDetailDrawer.view.sortedPostAttachments

            delegate: Item {
                width: attsGridView.cellWidth
                height: attsGridView.cellHeight

                readonly property var att: modelData || ({})
                readonly property bool viewable: postDetailDrawer.view.isViewableAttachment(att)
                readonly property string kindLabel: postDetailDrawer.view.attachmentKindLabel(att)
                readonly property bool isVideoCard: kindLabel === "VIDEO"
                readonly property bool isGifCard: kindLabel === "GIF"
                readonly property bool isAudioCard: kindLabel === "AUDIO"

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 4
                    radius: 9
                    color: attHover.hovered ? "#172033" : "#0D121C"
                    border.color: attHover.hovered ? "#38BDF8" : "#1E293B"
                    border.width: 1
                    clip: true

                    HoverHandler { id: attHover }

                    ColumnLayout {
                        z: 1
                        anchors.fill: parent
                        spacing: 0

                        // Visual Preview Area
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            color: "#070A10"
                            clip: true

                            Image {
                                id: attThumbImg
                                anchors.fill: parent
                                opacity: (status === Image.Ready && implicitWidth > 2) ? 1.0 : 0.0
                                source: postDetailDrawer.view.browserThumbUrl(att.thumbnail_url, postDetailDrawer.view.selectedPost.provider_id || postDetailDrawer.view.activeProvider)
                                sourceSize: Qt.size(360, 260)
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                            }

                            // Non-thumbnail media / video / audio / archive center badge
                            Column {
                                anchors.centerIn: parent
                                spacing: 4
                                visible: attThumbImg.status !== Image.Ready || attThumbImg.implicitWidth <= 2 || isVideoCard
                                Rectangle {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: 44
                                    height: 44
                                    radius: 22
                                    color: isVideoCard ? "#CC0EA5E9" : (isAudioCard ? "#CC10B981" : "#AA1E293B")
                                    border.color: "#38BDF8"
                                    border.width: isVideoCard ? 1.5 : 0
                                    Text {
                                        anchors.centerIn: parent
                                        text: isVideoCard ? "▶" : (isAudioCard ? "🎵" : (viewable ? "🖼️" : "📦"))
                                        font.pixelSize: isVideoCard ? 16 : 20
                                        color: "#FFFFFF"
                                    }
                                }
                            }

                            // Media kind badge (top-left)
                            Rectangle {
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.margins: 6
                                height: 18
                                implicitWidth: kindBadgeTxt.implicitWidth + 10
                                radius: 4
                                color: isGifCard ? "#7E22CE" : (isVideoCard ? "#0369A1" : (isAudioCard ? "#047857" : "#D80B0E14"))
                                border.color: isGifCard ? "#C084FC" : (isVideoCard ? "#38BDF8" : "#334155")
                                border.width: 1

                                Text {
                                    id: kindBadgeTxt
                                    anchors.centerIn: parent
                                    text: kindLabel
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: "#F8FAFC"
                                }
                            }

                            // Local Disk badge (top-right)
                            Rectangle {
                                visible: !!(att.local_path)
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: 6
                                height: 18
                                implicitWidth: onDiskTxt.implicitWidth + 8
                                radius: 4
                                color: "#CC064E3B"
                                border.color: "#10B981"
                                border.width: 1
                                Text {
                                    id: onDiskTxt
                                    anchors.centerIn: parent
                                    text: "✓ DISK"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 8
                                    font.weight: Font.Bold
                                    color: "#A7F3D0"
                                }
                            }

                            // Subtle hover CTA pill
                            Rectangle {
                                visible: attHover.hovered
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.margins: 6
                                height: 20
                                implicitWidth: ctaBadgeTxt.implicitWidth + 10
                                radius: 5
                                color: "#E60F172A"
                                border.color: "#38BDF8"
                                border.width: 1
                                Text {
                                    id: ctaBadgeTxt
                                    anchors.centerIn: parent
                                    text: viewable ? (isVideoCard || isAudioCard ? "▶ Play In-App" : "🔍 View In-App") : (att.local_path ? "💾 Open File" : "📥 Queue Post")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: "#7DD3FC"
                                }
                            }
                        }

                        // Filename + Size Footer
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 30
                            Layout.leftMargin: 7
                            Layout.rightMargin: 7
                            spacing: 4

                            Text {
                                Layout.fillWidth: true
                                text: att.name || "attachment"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: 600
                                color: "#E2E8F0"
                                elide: Text.ElideMiddle
                            }

                            Text {
                                visible: Number(att.file_size || 0) > 0
                                text: postDetailDrawer.view.formatBytes(att.file_size)
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                color: "#64748B"
                            }

                            Rectangle {
                                id: attCopyBtn
                                objectName: "attCopyLinkBtn"
                                property bool justCopied: false
                                visible: !!(att && (att.url || att.local_path || att.thumbnail_url))
                                Layout.preferredWidth: 22
                                Layout.preferredHeight: 20
                                radius: 5
                                z: 3
                                color: justCopied
                                       ? "#064E3B"
                                       : (attCopyMouse.containsMouse ? "#1E293B" : "#141B29")
                                border.color: justCopied ? "#10B981" : (attCopyMouse.containsMouse ? "#38BDF8" : "#283548")
                                border.width: 1
                                Springy { hover: attCopyMouse.containsMouse; pressed: attCopyMouse.pressed }
                                Timer {
                                    id: attCopyResetTimer
                                    interval: 1500
                                    onTriggered: attCopyBtn.justCopied = false
                                }
                                Text {
                                    anchors.centerIn: parent
                                    text: attCopyBtn.justCopied ? "✓" : "🔗"
                                    font.pixelSize: 9
                                    color: attCopyBtn.justCopied ? "#6EE7B7" : (attCopyMouse.containsMouse ? "#7DD3FC" : "#94A3B8")
                                }
                                MouseArea {
                                    id: attCopyMouse
                                    objectName: "attCopyLinkMouse"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 250
                                    ToolTip.text: "Copy link to this file"
                                    onClicked: (mouse) => {
                                        mouse.accepted = true
                                        if (postDetailDrawer.view.bBridge && postDetailDrawer.view.bBridge.copyAttachmentLink(att, postDetailDrawer.view.selectedPost)) {
                                            attCopyBtn.justCopied = true
                                            attCopyResetTimer.restart()
                                        }
                                    }
                                }
                            }
                        }
                    }

                    MouseArea {
                        id: attClick
                        anchors.fill: parent
                        z: 0
                        cursorShape: Qt.PointingHandCursor
                        onClicked: postDetailDrawer.view.openAttachmentInApp(att, postDetailDrawer.view.selectedPost)
                    }
                }
            }
        }
    }
}
