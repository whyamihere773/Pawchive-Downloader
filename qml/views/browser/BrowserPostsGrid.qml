import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

SmoothGridView {
    id: postsGrid
    required property var view
    required property bool showingPostsGrid
    property int markAnchor: -1
    property string markAnchorKey: ""
    property bool markAnchorState: true
    anchors.fill: parent
    visible: postsGrid.showingPostsGrid
    cellWidth: width > 0 ? Math.min(width, Math.max(210, Math.floor(width / Math.max(1, Math.floor(width / 250))))) : 230
    cellHeight: 248
    cacheBuffer: 640
    model: postsGrid.view.bBridge ? postsGrid.view.bBridge.postsModel : null

    delegate: Item {
        width: postsGrid.cellWidth
        height: postsGrid.cellHeight

        readonly property var pData: model.creator || modelData || ({})
        readonly property bool isMarked: !!pData.is_marked
        readonly property string diskStatus: (!postsGrid.view.isLocalMode && pData.disk_status) ? String(pData.disk_status) : "none"
        readonly property bool isDiskComplete: diskStatus === "complete"
        readonly property bool isDiskPartial: diskStatus === "partial"
        readonly property int localFileCnt: Number(pData.local_file_count || 0)
        readonly property int expectedFileCnt: Number(pData.expected_file_count || pData.file_count || 0)

        Rectangle {
            id: pCard
            objectName: "postCardRect"
            anchors.fill: parent
            anchors.margins: 5
            radius: 10
            color: pCardHover.hovered ? "#161E2E" : "#111622"
            border.color: isMarked
                ? "#38BDF8"
                : (isDiskComplete
                    ? "#10B981"
                    : (isDiskPartial
                        ? "#F59E0B"
                        : (pCardHover.hovered ? "#38BDF8" : "#1E293B")))
            border.width: (isMarked || isDiskComplete || isDiskPartial) ? (pCardHover.hovered ? 2 : 1.75) : 1
            clip: true

            HoverHandler { id: pCardHover }

            ColumnLayout {
                z: 1
                anchors.fill: parent
                spacing: 0

                // Thumbnail Cover Area
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 138
                    color: "#090C12"
                    clip: true

                    Image {
                        id: pThumbImg
                        anchors.fill: parent
                        opacity: (status === Image.Ready && implicitWidth > 2) ? 1.0 : 0.0
                        source: postsGrid.view.browserThumbUrl(pData.thumbnail_url, pData.provider_id || postsGrid.view.activeProvider)
                        sourceSize: Qt.size(360, 260)
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: pThumbImg.status !== Image.Ready || pThumbImg.implicitWidth <= 2
                        text: Number(pData.video_count || 0) > 0 ? "🎬" : "📄"
                        font.pixelSize: 28
                        color: "#334155"
                    }

                    // Attachment count & DM pills (top-left, clipped before right-side buttons)
                    Row {
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.topMargin: 6
                        anchors.leftMargin: 6
                        anchors.rightMargin: (!postsGrid.view.isLocalMode && !!pData.is_unimported) ? 72 : 42
                        spacing: 5
                        clip: true

                        Rectangle {
                            height: 22
                            implicitWidth: mediaBadgeRow.implicitWidth + 12
                            radius: 5
                            color: "#D80B0E14"

                            Row {
                                id: mediaBadgeRow
                                anchors.centerIn: parent
                                spacing: 4
                                Text {
                                    text: (Number(pData.video_count || 0) > 0 ? ("🎬 " + pData.video_count + " ") : "")
                                          + (Number(pData.image_count || 0) > 0 ? ("🖼️ " + pData.image_count) : ("📎 " + Number(pData.file_count || 0)))
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: Font.Bold
                                    color: "#F8FAFC"
                                }
                            }
                        }

                        Rectangle {
                            visible: !!pData.is_dm
                            height: 22
                            implicitWidth: dmBadgeTxt.implicitWidth + 10
                            radius: 5
                            color: "#6D28D9"
                            Text {
                                id: dmBadgeTxt
                                anchors.centerIn: parent
                                text: "💬 DM"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                            }
                        }
                    }

                    // Local Disk Completeness Pill (bottom-left of thumbnail, Online Mode only)
                    Rectangle {
                        id: diskStatusBadge
                        objectName: "postDiskStatusBadge"
                        visible: !postsGrid.view.isLocalMode && (isDiskComplete || isDiskPartial)
                        anchors.left: parent.left
                        anchors.bottom: parent.bottom
                        anchors.margins: 6
                        height: 20
                        width: Math.min(parent.width - 12, diskBadgeTxt.implicitWidth + 12)
                        radius: 5
                        z: 2
                        color: isDiskComplete ? "#E6064E3B" : "#E6451A03"
                        border.color: isDiskComplete ? "#10B981" : "#F59E0B"
                        border.width: 1

                        Text {
                            id: diskBadgeTxt
                            anchors.centerIn: parent
                            width: parent.width - 10
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                            text: isDiskComplete
                                ? (expectedFileCnt > 0 ? ("✓ " + localFileCnt + "/" + expectedFileCnt) : "✓ On Disk")
                                : (expectedFileCnt > 0 ? ("◐ " + localFileCnt + "/" + expectedFileCnt) : "◐ Partial")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            color: isDiskComplete ? "#6EE7B7" : "#FCD34D"
                        }

                        HoverHandler { id: diskBadgeHover }
                        ToolTip.visible: diskBadgeHover.hovered
                        ToolTip.delay: 250
                        ToolTip.text: isDiskComplete
                            ? (expectedFileCnt > 0
                                ? ("Complete on disk (" + localFileCnt + " of " + expectedFileCnt + " files present)")
                                : "Complete on disk")
                            : (expectedFileCnt > 0
                                ? ("Partial on disk (" + localFileCnt + " of " + expectedFileCnt + " files present — some files pruned or deselected)")
                                : "Partial on disk — some files missing or pruned")
                    }

                    UnimportedTriangleBadge {
                        objectName: "postUnimportedBadge"
                        visible: !postsGrid.view.isLocalMode && !!pData.is_unimported
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.topMargin: 6
                        anchors.rightMargin: 42
                        width: 24
                        height: 24
                        z: 3
                        tooltipText: "Haven't archived this post yet (previews only)"
                    }

                    // Mark Post Button (top-right, Online Mode)
                    Rectangle {
                        visible: !postsGrid.view.isLocalMode
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.margins: 6
                        width: 30
                        height: 30
                        radius: 7
                        z: 3
                        color: isMarked ? "#0284C7" : "#D80F172A"
                        border.color: isMarked ? "#38BDF8" : "#334155"
                        border.width: 1
                        Springy { hover: mkPostMouse.containsMouse; pressed: mkPostMouse.pressed }

                        Text {
                            anchors.centerIn: parent
                            text: isMarked ? "✔" : "🛒"
                            font.pixelSize: 12
                            color: "#FFFFFF"
                        }
                        MouseArea {
                            id: mkPostMouse
                            objectName: "postMarkMouse"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: (isMarked ? "Unmark post" : "Mark post into Download Cart") + "\nShift+click to mark/unmark a range"
                            onClicked: (mouse) => postsGrid.view.handleRangeMarkClick("posts", postsGrid, index, pData, (mouse.modifiers & Qt.ShiftModifier) !== 0)
                        }
                    }

                    // Redownload Post Button (top-right, Local Mode)
                    Rectangle {
                        visible: postsGrid.view.isLocalMode && !!(pData.url || (pData.service && pData.service !== "local" && pData.creator_id && pData.post_id && pData.post_id !== "root_files"))
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.margins: 6
                        width: 30
                        height: 30
                        radius: 7
                        z: 3
                        color: pRedlMouse.containsMouse ? "#0369A1" : "#D80F172A"
                        border.color: pRedlMouse.containsMouse ? "#38BDF8" : "#334155"
                        border.width: 1
                        Springy { hover: pRedlMouse.containsMouse; pressed: pRedlMouse.pressed }

                        Text {
                            anchors.centerIn: parent
                            text: "↻"
                            font.pixelSize: 14
                            font.weight: Font.Bold
                            color: "#E0F2FE"
                        }
                        MouseArea {
                            id: pRedlMouse
                            objectName: "postCardRedownloadMouse"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: "Redownload this post freshly (overwrites existing files)"
                            onClicked: if (postsGrid.view.bBridge) { if (postsGrid.view.bBridge.redownloadPostAsync) postsGrid.view.bBridge.redownloadPostAsync(pData); else postsGrid.view.bBridge.redownloadPost(pData) }
                        }
                    }
                }

                // Post Title, Date & Snippet
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.margins: 8
                    spacing: 4

                    Text {
                        Layout.fillWidth: true
                        text: pData.title || "Untitled Post"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: "#F1F5F9"
                        maximumLineCount: 2
                        wrapMode: Text.Wrap
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: !!(pData.content_snippet)
                        text: pData.content_snippet || ""
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        maximumLineCount: 1
                        elide: Text.ElideRight
                    }

                    Item { Layout.fillHeight: true }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 6
                        Text {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: pData.published_at || ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#64748B"
                            elide: Text.ElideRight
                        }
                        Rectangle {
                            id: pCardCopyBtn
                            objectName: "postCardCopyLinkBtn"
                            property bool justCopied: false
                            Layout.preferredWidth: 24
                            Layout.preferredHeight: 20
                            Layout.minimumWidth: 24
                            radius: 5
                            z: 3
                            color: justCopied
                                   ? "#064E3B"
                                   : (pCardCopyMouse.containsMouse ? "#1E293B" : "#151C2B")
                            border.color: justCopied ? "#10B981" : (pCardCopyMouse.containsMouse ? "#38BDF8" : "#334155")
                            border.width: 1
                            Springy { hover: pCardCopyMouse.containsMouse; pressed: pCardCopyMouse.pressed }
                            Timer {
                                id: pCardCopyTimer
                                interval: 1500
                                onTriggered: pCardCopyBtn.justCopied = false
                            }
                            Text {
                                anchors.centerIn: parent
                                text: pCardCopyBtn.justCopied ? "✓" : "🔗"
                                font.pixelSize: 9
                                color: pCardCopyBtn.justCopied ? "#6EE7B7" : "#7DD3FC"
                            }
                            MouseArea {
                                id: pCardCopyMouse
                                objectName: "postCardCopyLinkMouse"
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Copy link to this post"
                                onClicked: (mouse) => {
                                    mouse.accepted = true
                                    if (postsGrid.view.bBridge && postsGrid.view.bBridge.copyPostLink(pData)) {
                                        pCardCopyBtn.justCopied = true
                                        pCardCopyTimer.restart()
                                    }
                                }
                            }
                        }
                        Text {
                            Layout.minimumWidth: 0
                            text: "View Media →"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#38BDF8"
                            elide: Text.ElideRight
                        }
                    }
                }
            }

            MouseArea {
                id: pBodyMouse
                anchors.fill: parent
                z: 0
                cursorShape: Qt.PointingHandCursor
                onClicked: if (postsGrid.view.bBridge) postsGrid.view.bBridge.openPostDetail(pData)
            }
        }
    }
}
