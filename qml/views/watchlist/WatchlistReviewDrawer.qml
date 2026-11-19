import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── Row 4: Post Review Drawer (Newtonian weight-centered fluid animation)
Item {
    id: reviewDrawerContainer
    required property var card
    required property var view
    width: parent.width
    readonly property bool shouldShow: reviewDrawerContainer.card.isExpanded && (reviewDrawerContainer.card.hasUpdates || reviewDrawerContainer.card.currentCachedPosts.length > 0)
    readonly property real targetHeight: reviewDrawerBg.implicitHeight
    height: shouldShow ? targetHeight : 0
    clip: true
    visible: height > 0.5
    opacity: shouldShow ? 1.0 : 0.0

    Behavior on height {
        SpringAnimation {
            spring: 3.2
            damping: 0.35
            mass: 1.0
            epsilon: 0.5
        }
    }

    Behavior on opacity {
        NumberAnimation {
            duration: 220
            easing.type: Easing.OutCubic
        }
    }

    Rectangle {
        id: reviewDrawerBg
        width: parent.width
        implicitHeight: reviewCol.implicitHeight + 16
        radius: 8
        color: "#05080E"
        border.color: "#1E293B"
        border.width: 1
        y: reviewDrawerContainer.shouldShow ? 0 : -8
        scale: reviewDrawerContainer.shouldShow ? 1.0 : 0.97
        transformOrigin: Item.Top

        Behavior on y {
            SpringAnimation {
                spring: 3.5
                damping: 0.35
                mass: 1.0
                epsilon: 0.5
            }
        }
        Behavior on scale {
            SpringAnimation {
                spring: 3.5
                damping: 0.35
                mass: 1.0
                epsilon: 0.01
            }
        }

        Column {
            id: reviewCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 10
            spacing: 6

            // Drawer Header
            RowLayout {
                width: parent.width

                Text {
                    text: "📋 " + reviewDrawerContainer.view.tr("watchlist_pending_updates", "Discovered Updates") + " (" + reviewDrawerContainer.card.currentCachedPosts.length + ")"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#A5F3FC"
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                // Dismiss / Ignore all current updates
                Rectangle {
                    height: 22
                    implicitWidth: ignoreAllText.implicitWidth + 14
                    radius: 4
                    color: ignoreAllMouse.containsMouse ? "#2B1115" : "#1A0B0E"
                    border.color: "#7F1D1D"
                    border.width: 1

                    Text {
                        id: ignoreAllText
                        anchors.centerIn: parent
                        text: reviewDrawerContainer.view.width < 500 ? "🚫 Dismiss" : ("🚫 " + reviewDrawerContainer.view.tr("watchlist_ignore_all_updates", "Dismiss / Ignore All"))
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#FCA5A5"
                    }

                    MouseArea {
                        id: ignoreAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: reviewDrawerContainer.view.tr("watchlist_ignore_all_tip", "Permanently skip all currently discovered posts (future new posts will still be detected)")
                        onClicked: {
                            if (reviewDrawerContainer.view.bridge) reviewDrawerContainer.view.bridge.ignoreCurrentNewPosts(reviewDrawerContainer.card.artistUserId, reviewDrawerContainer.card.artistService)
                        }
                    }
                }

                // Download all remaining button
                Rectangle {
                    height: 22
                    implicitWidth: dlRemainingText.implicitWidth + 14
                    radius: 4
                    color: dlRemainingMouse.containsMouse ? "#0C2D3A" : "#071E26"
                    border.color: "#22D3EE"
                    border.width: 1

                    Text {
                        id: dlRemainingText
                        anchors.centerIn: parent
                        text: reviewDrawerContainer.view.width < 500 ? "↓ Get All" : ("↓ " + reviewDrawerContainer.view.tr("watchlist_download_all", "Download All"))
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#A5F3FC"
                    }

                    MouseArea {
                        id: dlRemainingMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: reviewDrawerContainer.view.tr("watchlist_download_all_tip", "Download all remaining new posts for this artist")
                        onClicked: {
                            if (reviewDrawerContainer.view.bridge) reviewDrawerContainer.view.bridge.downloadNewPosts(reviewDrawerContainer.card.artistUserId, reviewDrawerContainer.card.artistService)
                        }
                    }
                }
            }

            // Post items repeater (Uses safely guarded reviewDrawerContainer.card.currentCachedPosts)
            Repeater {
                model: reviewDrawerContainer.shouldShow ? reviewDrawerContainer.card.currentCachedPosts.slice(0, reviewDrawerContainer.card.drawerShown) : null

                Rectangle {
                    width: reviewCol.width
                    height: 28
                    radius: 5
                    color: postItemMouse.containsMouse ? "#0D1524" : "#090D18"
                    border.color: postItemMouse.containsMouse ? "#1E293B" : "#131A29"
                    border.width: 1

                    MouseArea {
                        id: postItemMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 8

                        // Date pill
                        Text {
                            text: (modelData && modelData.published) ? modelData.published : "----/--/--"
                            font.family: "Consolas, Segoe UI, monospace"
                            font.pixelSize: 10
                            color: "#64748B"
                        }

                        // Post title
                        Text {
                            text: (modelData && modelData.title) ? modelData.title : ("Post " + (modelData ? modelData.id : ""))
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 500
                            color: "#E2E8F0"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        // Single post ignore button
                        Rectangle {
                            height: 20
                            implicitWidth: ignPostText.implicitWidth + 10
                            radius: 4
                            color: ignPostMouse.containsMouse ? "#3B1419" : "#220C10"
                            border.color: "#991B1B"
                            border.width: 1

                            Text {
                                id: ignPostText
                                anchors.centerIn: parent
                                text: "🚫 Skip"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.weight: 600
                                color: "#FCA5A5"
                            }

                            MouseArea {
                                id: ignPostMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: reviewDrawerContainer.view.tr("watchlist_skip_post_tip", "Permanently ignore this post (won't be downloaded)")
                                onClicked: {
                                    if (reviewDrawerContainer.view.bridge && modelData && modelData.id) {
                                        reviewDrawerContainer.view.bridge.ignoreWatchlistPost(reviewDrawerContainer.card.artistUserId, reviewDrawerContainer.card.artistService, modelData.id)
                                    }
                                }
                            }
                        }

                        // Single post download button
                        Rectangle {
                            height: 20
                            implicitWidth: dlPostText.implicitWidth + 10
                            radius: 4
                            color: dlPostMouse.containsMouse ? "#0A3B4C" : "#072633"
                            border.color: "#0284C7"
                            border.width: 1

                            Text {
                                id: dlPostText
                                anchors.centerIn: parent
                                text: "↓ Get"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.weight: 600
                                color: "#38BDF8"
                            }

                            MouseArea {
                                id: dlPostMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: reviewDrawerContainer.view.tr("watchlist_get_post_tip", "Download only this post")
                                onClicked: {
                                    if (reviewDrawerContainer.view.bridge && modelData && modelData.id) {
                                        reviewDrawerContainer.view.bridge.downloadNewPosts(reviewDrawerContainer.card.artistUserId, reviewDrawerContainer.card.artistService, [modelData.id])
                                    }
                                }
                            }
                        }
                    }
                }
            }
            // Long update lists open a page at a time (hundreds of rows at once stalled the window)
            Text {
                visible: reviewDrawerContainer.shouldShow && reviewDrawerContainer.card.currentCachedPosts.length > reviewDrawerContainer.card.drawerShown
                text: reviewDrawerContainer.view.tr("archive_show_more_posts", "Show %1 more posts (%2 left)").replace("%1", Math.min(50, reviewDrawerContainer.card.currentCachedPosts.length - reviewDrawerContainer.card.drawerShown)).replace("%2", reviewDrawerContainer.card.currentCachedPosts.length - reviewDrawerContainer.card.drawerShown)
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: drawerMoreMouse.containsMouse ? "#5EEAD4" : "#2DD4BF"
                MouseArea {
                    id: drawerMoreMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: reviewDrawerContainer.card.drawerShown += 50
                }
            }
        }
    }
}
