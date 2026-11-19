import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── Header ──────────────────────────────────────────────────────────────
// ── Header (Responsive layout: single row on wide screens, dual row on compact) ──
Rectangle {
    id: headerRect
    required property var view
    Layout.fillWidth: true
    readonly property bool isCompact: headerRect.view.width < 960
    height: isCompact ? 86 : 52
    color: "#0C0F18"
    border.color: "#1A2035"
    border.width: 1
    radius: 8
    clip: true

    Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

    // Gradient accent line
    Rectangle {
        width: parent.width * 0.6
        height: 1
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.3; color: "#A78BFA" }
            GradientStop { position: 0.7; color: "#38BDF8" }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 12
        anchors.topMargin: headerRect.isCompact ? 8 : 10
        anchors.bottomMargin: headerRect.isCompact ? 8 : 10
        spacing: 6

        // Row 1: Title + Subtitle + Badge + (Wide action holder)
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            // Icon + Title
            Text { text: "\uD83D\uDCCC"; font.pixelSize: 18; Layout.alignment: Qt.AlignVCenter }
            Text {
                text: headerRect.view.tr("tab_watchlist", "Watchlist")
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 15
                font.weight: 600
                color: "#E2E8F0"
                Layout.alignment: Qt.AlignVCenter
            }

            // Subtitle / entry count
            Text {
                text: {
                    if (!headerRect.view.bridge || !headerRect.view.bridge.watchlistModel) return ""
                    var c = headerRect.view.bridge.watchlistModel.count
                    var tot = headerRect.view.bridge.watchlistModel.totalCount
                    var u = headerRect.view.bridge.watchlistModel.updatedCount
                    var base = c + " " + headerRect.view.tr("watchlist_artists", "artist(s)")
                    if (headerRect.view.searchText || headerRect.view.activeServiceFilter !== "all") {
                        base = c + " of " + tot + " " + headerRect.view.tr("watchlist_artists", "artist(s)")
                    }
                    if (u > 0) {
                        return base + " • " + u + " updated"
                    }
                    return base
                }
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: (headerRect.view.bridge && headerRect.view.bridge.watchlistModel && headerRect.view.bridge.watchlistModel.updatedCount > 0) ? 600 : Font.Normal
                color: (headerRect.view.bridge && headerRect.view.bridge.watchlistModel && headerRect.view.bridge.watchlistModel.updatedCount > 0) ? "#22D3EE" : "#4B5563"
                Layout.alignment: Qt.AlignVCenter
                elide: Text.ElideRight
            }

            // High-visibility update counter badge (cleanly placed next to subtitle)
            Rectangle {
                id: resultBadge
                readonly property int updArtists: headerRect.view.bridge && headerRect.view.bridge.watchlistModel ? headerRect.view.bridge.watchlistModel.updatedCount : 0
                readonly property int totalNew: headerRect.view.bridge && headerRect.view.bridge.watchlistModel ? headerRect.view.bridge.watchlistModel.totalNewPosts : (headerRect.view.lastNewCount > 0 ? headerRect.view.lastNewCount : 0)
                visible: updArtists > 0 || headerRect.view.lastNewCount > 0
                height: 24
                implicitWidth: resultBadgeRow.implicitWidth + 14
                radius: 12
                color: "#071E26"
                border.color: "#22D3EE"
                border.width: 1.2
                Layout.alignment: Qt.AlignVCenter

                scale: resultBadgeMouse.containsMouse ? 1.04 : 1.0
                Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutBack } }

                Row {
                    id: resultBadgeRow
                    anchors.centerIn: parent
                    spacing: 5

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "✦"
                        font.pixelSize: 10
                        color: "#22D3EE"
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: {
                            var count = resultBadge.totalNew > 0 ? resultBadge.totalNew : headerRect.view.lastNewCount
                            var art = resultBadge.updArtists
                            if (count <= 0 && headerRect.view.lastNewCount > 0) count = headerRect.view.lastNewCount
                            if (headerRect.view.width < 900) {
                                return count + " new"
                            }
                            if (art > 1) {
                                return count + " new " + (count === 1 ? "post" : "posts") + " · " + art + " creators"
                            } else {
                                return count + " new " + (count === 1 ? "post" : "posts")
                            }
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#A5F3FC"
                    }
                }

                MouseArea {
                    id: resultBadgeMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: {
                        var count = resultBadge.totalNew > 0 ? resultBadge.totalNew : headerRect.view.lastNewCount
                        var art = resultBadge.updArtists
                        return count + " new post(s) found across " + art + " creator(s). Updated creators are pinned at the top."
                    }
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 4
            }

            // On wide screens (>= 960), action buttons dock here
            Item {
                id: wideActionHolder
                visible: !headerRect.isCompact
                Layout.preferredWidth: visible ? actionButtonsRow.implicitWidth : 0
                Layout.preferredHeight: visible ? 32 : 0
            }
        }

        // Row 2: (Only visible when compact < 960)
        RowLayout {
            id: compactRow
            visible: headerRect.isCompact
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            spacing: 0

            Flickable {
                id: compactFlickable
                Layout.fillWidth: true
                Layout.preferredHeight: 32
                contentWidth: actionButtonsRow.implicitWidth
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Item {
                    id: compactActionHolder
                    width: actionButtonsRow.implicitWidth
                    height: 32
                }
            }
        }
    }

    // Shared Action Buttons Row: docks to wideActionHolder or compactActionHolder
    Row {
        id: actionButtonsRow
        parent: headerRect.isCompact ? compactActionHolder : wideActionHolder
        spacing: 6
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined

        // Download All Updates button
        Rectangle {
            id: downloadAllBtn
            readonly property int totalNew: headerRect.view.bridge && headerRect.view.bridge.watchlistModel ? headerRect.view.bridge.watchlistModel.totalNewPosts : 0
            visible: totalNew > 0
            height: 32
            implicitWidth: downloadAllRow.implicitWidth + 14
            radius: 7
            color: downloadAllMouse.pressed ? "#072019" : (downloadAllMouse.containsMouse ? "#0F382E" : "#07241C")
            border.color: downloadAllMouse.containsMouse ? "#34D399" : "#10B981"
            border.width: 1.2

            Behavior on color { ColorAnimation { duration: 120 } }
            Behavior on border.color { ColorAnimation { duration: 120 } }
            scale: downloadAllMouse.pressed ? 0.94 : (downloadAllMouse.containsMouse ? 1.035 : 1.0)
            transformOrigin: Item.Center
            Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

            Row {
                id: downloadAllRow
                anchors.centerIn: parent
                spacing: 5

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "↓"
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: "#34D399"
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: headerRect.isCompact
                          ? ("Updates (" + downloadAllBtn.totalNew + ")")
                          : (headerRect.view.tr("watchlist_download_all_btn", "Download All Updates") + " (" + downloadAllBtn.totalNew + ")")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#6EE7B7"
                }
            }

            MouseArea {
                id: downloadAllMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: headerRect.view.tr("watchlist_download_all_tip", "Download all newly discovered posts for all creators in your watchlist")
                onClicked: if (headerRect.view.bridge) headerRect.view.bridge.downloadAllNewPosts()
            }
        }

        // Add Artist button
        Rectangle {
            id: addArtistBtn
            height: 32
            implicitWidth: addArtistRow.implicitWidth + 14
            radius: 7
            color: addArtistMouse.pressed ? "#16122C" : (addArtistMouse.containsMouse ? "#201840" : "#141026")
            border.color: addArtistMouse.containsMouse ? "#A78BFA" : "#7C3AED"
            border.width: 1

            Behavior on color { ColorAnimation { duration: 120 } }
            Behavior on border.color { ColorAnimation { duration: 120 } }
            scale: addArtistMouse.pressed ? 0.94 : (addArtistMouse.containsMouse ? 1.035 : 1.0)
            transformOrigin: Item.Center
            Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

            Row {
                id: addArtistRow
                anchors.centerIn: parent
                spacing: 5

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "➕"
                    font.pixelSize: 11
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: headerRect.isCompact
                          ? headerRect.view.tr("watchlist_add_artist_short", "Add")
                          : headerRect.view.tr("watchlist_add_artist_btn", "Add Artist")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#C4B5FD"
                }
            }

            MouseArea {
                id: addArtistMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: headerRect.view.tr("watchlist_add_artist_tip", "Track an artist by URL without downloading past posts")
                onClicked: headerRect.view.showAddDialog = true
            }
        }

        // Sync Pawchive Favorites button
        Rectangle {
            id: syncFavBtn
            height: 32
            implicitWidth: syncFavRow.implicitWidth + 14
            radius: 7
            color: syncFavMouse.containsMouse ? "#2A2008" : "#1A170C"
            border.color: syncFavMouse.containsMouse ? "#F59E0B" : "#B45309"
            border.width: 1

            Behavior on color { ColorAnimation { duration: 120 } }
            Behavior on border.color { ColorAnimation { duration: 120 } }
            scale: syncFavMouse.pressed ? 0.94 : (syncFavMouse.containsMouse ? 1.035 : 1.0)
            transformOrigin: Item.Center
            Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

            Row {
                id: syncFavRow
                anchors.centerIn: parent
                spacing: 5

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: (headerRect.view.bridge && headerRect.view.bridge.favoriteArtistsLoading) ? "⏳" : "⭐"
                    font.pixelSize: 11
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: (headerRect.view.bridge && headerRect.view.bridge.favoriteArtistsLoading)
                          ? headerRect.view.tr("watchlist_syncing_favs", "Syncing…")
                          : (headerRect.isCompact
                             ? headerRect.view.tr("watchlist_sync_favs_short", "Favorites")
                             : headerRect.view.tr("watchlist_sync_favorites", "Sync Favorites"))
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#FCD34D"
                }
            }

            MouseArea {
                id: syncFavMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: headerRect.view.tr("watchlist_sync_favorites_tip", "Import and sync followed creators from your connected accounts into Watchlist")
                onClicked: {
                    if (headerRect.view.bridge) headerRect.view.bridge.syncPawchiveFavorites()
                }
            }
        }

        // Disable / Enable Auto-Check for all artists
        Rectangle {
            id: autoCheckAllBtn
            readonly property int totalArtists: headerRect.view.bridge && headerRect.view.bridge.watchlistModel ? headerRect.view.bridge.watchlistModel.totalCount : 0
            readonly property int autoCheckArtists: headerRect.view.bridge && headerRect.view.bridge.watchlistModel ? headerRect.view.bridge.watchlistModel.autoCheckCount : 0
            readonly property bool anyAutoCheckEnabled: autoCheckArtists > 0
            visible: totalArtists > 0
            height: 32
            implicitWidth: autoCheckAllRow.implicitWidth + 14
            radius: 7
            color: autoCheckMouse.pressed
                   ? (anyAutoCheckEnabled ? "#2A1418" : "#0E2417")
                   : (autoCheckMouse.containsMouse
                      ? (anyAutoCheckEnabled ? "#221115" : "#0C1F14")
                      : (anyAutoCheckEnabled ? "#180C10" : "#08160E"))
            border.color: autoCheckMouse.containsMouse
                          ? (anyAutoCheckEnabled ? "#F87171" : "#34D399")
                          : (anyAutoCheckEnabled ? "#991B1B" : "#065F46")
            border.width: 1

            Behavior on color { ColorAnimation { duration: 120 } }
            Behavior on border.color { ColorAnimation { duration: 120 } }
            scale: autoCheckMouse.pressed ? 0.94 : (autoCheckMouse.containsMouse ? 1.035 : 1.0)
            transformOrigin: Item.Center
            Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

            Row {
                id: autoCheckAllRow
                anchors.centerIn: parent
                spacing: 5

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: autoCheckAllBtn.anyAutoCheckEnabled ? "🔕" : "🔔"
                    font.pixelSize: 11
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: {
                        if (autoCheckAllBtn.anyAutoCheckEnabled) {
                            return headerRect.isCompact
                                   ? headerRect.view.tr("watchlist_disable_autocheck_short", "No Auto-Check")
                                   : headerRect.view.tr("watchlist_disable_autocheck", "Disable Auto-Check (All)")
                        } else {
                            return headerRect.isCompact
                                   ? headerRect.view.tr("watchlist_enable_autocheck_short", "Auto-Check")
                                   : headerRect.view.tr("watchlist_enable_autocheck", "Enable Auto-Check (All)")
                        }
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: autoCheckAllBtn.anyAutoCheckEnabled ? "#FCA5A5" : "#6EE7B7"
                }
            }

            MouseArea {
                id: autoCheckMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: {
                    if (autoCheckAllBtn.anyAutoCheckEnabled) {
                        return headerRect.view.tr("watchlist_disable_autocheck_tip", "Disable automatic startup check for all artists in the watchlist (" + autoCheckAllBtn.autoCheckArtists + " currently enabled)")
                    } else {
                        return headerRect.view.tr("watchlist_enable_autocheck_tip", "Enable automatic startup check for all artists in the watchlist")
                    }
                }
                onClicked: {
                    if (headerRect.view.bridge) {
                        headerRect.view.bridge.setAllWatchlistAutoCheck(!autoCheckAllBtn.anyAutoCheckEnabled)
                    }
                }
            }
        }

        // Check All button
        Rectangle {
            id: checkAllBtn
            height: 32
            implicitWidth: checkAllRow.implicitWidth + 14
            radius: 7
            color: checkAllMouse.containsMouse ? "#1E1B3D" : "#141228"
            border.color: headerRect.view.isChecking ? "#6D28D9" : "#4C1D95"
            border.width: 1

            Behavior on color { ColorAnimation { duration: 120 } }
            Behavior on border.color { ColorAnimation { duration: 120 } }
            scale: checkAllMouse.pressed ? 0.94 : (checkAllMouse.containsMouse ? 1.035 : 1.0)
            transformOrigin: Item.Center
            Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

            Row {
                id: checkAllRow
                anchors.centerIn: parent
                spacing: 5

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: headerRect.view.isChecking ? "\u21BB" : "\uD83D\uDD0D"
                    font.pixelSize: headerRect.view.isChecking ? 13 : 11
                    color: "#A78BFA"

                    RotationAnimator on rotation {
                        from: 0; to: 360
                        duration: 900
                        loops: Animation.Infinite
                        running: headerRect.view.isChecking
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: {
                        if (headerRect.view.isChecking) {
                            return headerRect.view.tr("watchlist_checking", "Checking…") + (headerRect.view.checkTotal > 0 ? "  " + headerRect.view.checkDone + " / " + headerRect.view.checkTotal : "")
                        }
                        if (headerRect.isCompact) {
                            return headerRect.view.tr("watchlist_check_artist", "Check")
                        }
                        var isFiltered = (headerRect.view.activeServiceFilter !== "all" || headerRect.view.searchText !== "")
                        if (isFiltered) {
                            var count = (headerRect.view.bridge && headerRect.view.bridge.watchlistModel) ? headerRect.view.bridge.watchlistModel.count : 0
                            return headerRect.view.tr("watchlist_check_filtered", "Check Filtered") + " (" + count + ")"
                        }
                        return headerRect.view.tr("watchlist_check_all", "Check All")
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#A78BFA"
                }
            }

            MouseArea {
                id: checkAllMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: {
                    if (headerRect.view.isChecking) {
                        return headerRect.view.tr("watchlist_stop_check_tip", "Stop checking (the next check continues from here)")
                    }
                    if (headerRect.view.activeServiceFilter !== "all" || headerRect.view.searchText !== "") {
                        return headerRect.view.tr("watchlist_check_filtered_tip", "Check visible artists matching the active filter for new posts")
                    }
                    return headerRect.view.tr("watchlist_check_all_tip", "Check all followed artists for new posts")
                }
                onClicked: {
                    if (headerRect.view.bridge) {
                        var isFiltered = (headerRect.view.activeServiceFilter !== "all" || headerRect.view.searchText !== "")
                        headerRect.view.bridge.checkWatchlist(isFiltered)
                    }
                }
            }
        }
    }
}
