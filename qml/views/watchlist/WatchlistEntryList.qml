import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── Entry list ────────────────────────────────────────────────────
SmoothListView {
    id: watchListView
    required property var view
    anchors.fill: parent
    anchors.margins: 10
    spacing: 8
    clip: true
    visible: watchListView.view.bridge && watchListView.view.bridge.watchlistModel && watchListView.view.bridge.watchlistModel.count > 0
    model: watchListView.view.bridge ? watchListView.view.bridge.watchlistModel : null

    delegate: Rectangle {
        id: entryCard
        width: watchListView.width
        radius: 10

        // ── Safe Model Property Accessors (Guards against model being undefined on reset)
        readonly property var currentModel: (typeof model !== "undefined") ? model : null
        readonly property bool hasUpdates: !!(currentModel && currentModel.newPostCount > 0)
        readonly property bool isFavorite: currentModel ? !!currentModel.isFavorite : false
        readonly property string artistUserId: currentModel ? (currentModel.userId || "") : ""
        readonly property string artistService: currentModel ? (currentModel.service || "") : ""
        readonly property string artistCreatorName: currentModel ? (currentModel.creatorName || "") : ""
        readonly property string artistUrl: currentModel ? (currentModel.url || "") : ""
        readonly property string artistDomain: currentModel ? (currentModel.domain || "") : ""
        readonly property string artistProvider: currentModel ? (currentModel.provider || "") : ""
        readonly property string artistDownloadDir: currentModel ? (currentModel.downloadDir || "") : ""
        readonly property var artistDownloadDirs: currentModel ? (currentModel.downloadDirs || (currentModel.downloadDir ? [currentModel.downloadDir] : [])) : []
        readonly property string artistLastPostDate: currentModel ? (currentModel.lastPostDate || "") : ""
        readonly property bool artistAutoCheck: currentModel ? !!currentModel.autoCheck : false
        readonly property int currentNewPostCount: currentModel ? (currentModel.newPostCount || 0) : 0
        readonly property int currentIgnoredCount: currentModel ? (currentModel.ignoredCount || 0) : 0
        readonly property var currentCachedPosts: (currentModel && currentModel.cachedNewPosts) ? currentModel.cachedNewPosts : []
        property int drawerShown: 50

        readonly property string artistKey: artistUserId + "_" + artistService
        readonly property bool isArtistChecking: !!(watchListView.view.checkingArtists[artistKey])
        readonly property bool isExpanded: !!watchListView.view.expandedArtists[artistKey]

        // Date editing state
        property bool isEditingDate: false

        // Safe reference to view root for use inside deeply nested functions/delegates
        readonly property var viewRoot: watchListView.view

        // Smooth dynamic height adapting to content, date editor, and post review with Newtonian spring physics
        height: cardCol.implicitHeight + 24
        Behavior on height {
            SpringAnimation {
                spring: 3.2
                damping: 0.35
                mass: 1.0
                epsilon: 0.5
            }
        }

        // Updated cards get a subtle cyan-tinted dark background, favorites get a subtle warm amber tint
        color: hasUpdates 
               ? (cardMouse.containsMouse ? "#071E26" : "#050F14") 
               : (isFavorite
                  ? (cardMouse.containsMouse ? "#18140B" : "#120F08")
                  : (cardMouse.containsMouse ? "#111827" : "#0D1117"))

        border.color: hasUpdates 
                      ? (cardMouse.containsMouse ? "#38BDF8" : "#22D3EE") 
                      : (isFavorite
                         ? (cardMouse.containsMouse ? "#F59E0B" : "#B45309")
                         : "#1E2330")
        border.width: (hasUpdates || isFavorite) ? 1.5 : 1
        clip: true

        Behavior on color { ColorAnimation { duration: 140 } }
        Behavior on border.color { ColorAnimation { duration: 140 } }

        // Subtle top accent line on updated cards or favorites
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 2
            color: hasUpdates ? "#22D3EE" : "#F59E0B"
            opacity: 0.8
            visible: hasUpdates || isFavorite
        }

        // Left accent bar
        Rectangle {
            width: (hasUpdates || isFavorite) ? 5 : 3
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            radius: 3
            color: hasUpdates 
                   ? "#22D3EE" 
                   : (isFavorite
                      ? "#F59E0B"
                      : (isArtistChecking ? "#8B5CF6" : watchListView.view.serviceColor(entryCard.artistService)))
            opacity: (hasUpdates || isFavorite) ? 0.95 : 0.8
        }

        MouseArea {
            id: cardMouse
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.NoButton
        }

        Column {
            id: cardCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 14
            anchors.leftMargin: 18
            spacing: 9

            // ── Row 1: Name + Profile link + service badge + favorite badge + star toggle + new badge
            RowLayout {
                width: parent.width
                spacing: 8

                Text {
                    text: (entryCard.hasUpdates ? "✦ " : "") + (entryCard.artistCreatorName || entryCard.artistUserId)
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 14
                    font.weight: entryCard.hasUpdates ? Font.Bold : 600
                    color: entryCard.hasUpdates ? "#A5F3FC" : (entryCard.isFavorite ? "#FEF08A" : "#E2E8F0")
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                // Profile Link Button (↗)
                Rectangle {
                    height: 22
                    width: 24
                    radius: 5
                    color: profileLinkMouse.containsMouse ? "#1E293B" : "#0F172A"
                    border.color: profileLinkMouse.containsMouse ? "#64748B" : "#334155"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "↗"
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: profileLinkMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                    }

                    MouseArea {
                        id: profileLinkMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: watchListView.view.tr("watchlist_open_profile_tip", "Open creator page in browser\n") + entryCard.artistUrl
                        onClicked: {
                            if (entryCard.artistUrl) Qt.openUrlExternally(entryCard.artistUrl)
                        }
                    }
                }

                // Provider pill
                ProviderBadge {
                    provider: entryCard.artistProvider
                    domain: entryCard.artistDomain
                    badgeHeight: 20
                }

                // Service pill
                ServiceBadge {
                    service: entryCard.artistService
                    badgeHeight: 20
                }

                // Golden Star Favorite Badge
                Rectangle {
                    visible: entryCard.isFavorite
                    height: 20
                    implicitWidth: favBadgeRow.implicitWidth + 12
                    radius: 10
                    color: "#2A2008"
                    border.color: "#F59E0B"
                    border.width: 1

                    Row {
                        id: favBadgeRow
                        anchors.centerIn: parent
                        spacing: 3
                        Text { text: "⭐"; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: watchListView.view.tr("lbl_favorite_badge", "Favorite")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 9
                            font.weight: Font.Bold
                            color: "#FCD34D"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                // 1-Click Star Toggle Button
                Rectangle {
                    height: 22
                    width: 24
                    radius: 5
                    color: starToggleMouse.containsMouse ? "#2A2008" : (entryCard.isFavorite ? "#1E1807" : "#0F172A")
                    border.color: entryCard.isFavorite ? "#F59E0B" : (starToggleMouse.containsMouse ? "#64748B" : "#334155")
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: entryCard.isFavorite ? "⭐" : "☆"
                        font.pixelSize: entryCard.isFavorite ? 11 : 13
                        color: entryCard.isFavorite ? "#FBBF24" : (starToggleMouse.containsMouse ? "#FCD34D" : "#94A3B8")
                    }

                    MouseArea {
                        id: starToggleMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: entryCard.isFavorite ? watchListView.view.tr("tip_unfavorite", "Remove from Favorites") : watchListView.view.tr("tip_favorite", "Mark as Favorite")
                        onClicked: {
                            if (watchListView.view.bridge && watchListView.view.bridge.watchlistModel) {
                                watchListView.view.bridge.watchlistModel.toggleFavorite(entryCard.artistUserId, entryCard.artistService, !entryCard.isFavorite)
                            }
                        }
                    }
                }

                // New post count badge — interactive toggle for review
                Rectangle {
                    visible: entryCard.hasUpdates
                    height: 20
                    implicitWidth: newBadgeRow.implicitWidth + 16
                    radius: 10
                    color: newBadgeMouse.containsMouse ? "#0C3342" : "#071E26"
                    border.color: "#22D3EE"
                    border.width: 1

                    Row {
                        id: newBadgeRow
                        anchors.centerIn: parent
                        spacing: 4

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "✦"
                            font.pixelSize: 9
                            color: "#22D3EE"
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: entryCard.currentNewPostCount + " new post" + (entryCard.currentNewPostCount === 1 ? "" : "s")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 9
                            font.weight: Font.Bold
                            color: "#A5F3FC"
                        }
                    }

                    MouseArea {
                        id: newBadgeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: watchListView.view.tr("watchlist_toggle_review_tip", "Click to review individual new posts")
                        onClicked: {
                            var copy = Object.assign({}, watchListView.view.expandedArtists)
                            copy[entryCard.artistKey] = !copy[entryCard.artistKey]
                            watchListView.view.expandedArtists = copy
                        }
                    }
                }
            }

            // ── Row 2: Last download date (interactive badge) + ignored count + auto-check toggle
            RowLayout {
                width: parent.width
                spacing: 10

                // Interactive Last Downloaded Date Badge with edit pencil
                Rectangle {
                    id: dateBadge
                    height: 22
                    implicitWidth: dateBadgeRow.implicitWidth + 16
                    radius: 6
                    color: dateBadgeMouse.containsMouse ? "#182638" : "#0F1A28"
                    border.color: entryCard.isEditingDate ? "#38BDF8" : (dateBadgeMouse.containsMouse ? "#38BDF8" : "#243B55")
                    border.width: 1

                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                    scale: dateBadgeMouse.pressed ? 0.95 : (dateBadgeMouse.containsMouse ? 1.03 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack } }

                    Row {
                        id: dateBadgeRow
                        anchors.centerIn: parent
                        spacing: 5

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "\uD83D\uDCC5"
                            font.pixelSize: 10
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: watchListView.view.tr("watchlist_last_dl", "Last downloaded:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#64748B"
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: entryCard.artistLastPostDate || watchListView.view.tr("watchlist_never", "Never")
                            font.family: "Consolas, Segoe UI, monospace"
                            font.pixelSize: 11
                            font.weight: entryCard.artistLastPostDate ? Font.DemiBold : Font.Normal
                            color: entryCard.artistLastPostDate ? "#93C5FD" : "#64748B"
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: entryCard.isEditingDate ? "▲" : "✏️"
                            font.pixelSize: 9
                            opacity: dateBadgeMouse.containsMouse ? 1.0 : 0.6
                        }
                    }

                    MouseArea {
                        id: dateBadgeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: watchListView.view.tr("watchlist_edit_date_tip", "Click to modify last downloaded cutoff date\nEnforces/converts to YYYY-MM-DD for Pawchive and cum.st")
                        onClicked: {
                            entryCard.isEditingDate = !entryCard.isEditingDate
                            if (entryCard.isEditingDate) {
                                dateEditorContainer.focusEditor(entryCard.artistLastPostDate || "")
                            }
                        }
                    }
                }

                // Ignored posts chip (with reset button)
                Rectangle {
                    visible: entryCard.currentIgnoredCount > 0
                    height: 20
                    implicitWidth: ignoredRow.implicitWidth + 14
                    radius: 10
                    color: ignoredMouse.containsMouse ? "#2A1115" : "#190B0E"
                    border.color: ignoredMouse.containsMouse ? "#F87171" : "#EF4444"
                    border.width: 1

                    Row {
                        id: ignoredRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "🚫 " + entryCard.currentIgnoredCount + " ignored"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 9
                            font.weight: 600
                            color: "#FCA5A5"
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "↻"
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            color: "#F87171"
                        }
                    }

                    MouseArea {
                        id: ignoredMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: watchListView.view.tr("watchlist_unignore_tip", "Click to reset ignored posts and re-check for updates")
                        onClicked: {
                            if (watchListView.view.bridge) watchListView.view.bridge.unignoreAllWatchlistPosts(entryCard.artistUserId, entryCard.artistService)
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // Auto-check toggle with fluid animations
                Row {
                    spacing: 6
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: watchListView.view.tr("watchlist_auto_check", "Auto-check")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: toggleMouse.containsMouse ? "#94A3B8" : "#64748B"
                        Behavior on color { ColorAnimation { duration: 150 } }
                    }
                    Rectangle {
                        id: autoCheckToggle
                        width: 38; height: 20
                        radius: 10
                        color: entryCard.artistAutoCheck 
                               ? (toggleMouse.containsMouse ? "#105C38" : "#0D4C2F") 
                               : (toggleMouse.containsMouse ? "#263047" : "#1C2233")
                        border.color: entryCard.artistAutoCheck 
                                      ? (toggleMouse.containsMouse ? "#34D399" : "#10B981") 
                                      : (toggleMouse.containsMouse ? "#475569" : "#2E3A56")
                        border.width: 1
                        anchors.verticalCenter: parent.verticalCenter
                        scale: toggleMouse.pressed ? 0.88 : (toggleMouse.containsMouse ? 1.08 : 1.0)
                        transformOrigin: Item.Center

                        Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.4 } }
                        Behavior on color { ColorAnimation { duration: 180 } }
                        Behavior on border.color { ColorAnimation { duration: 180 } }

                        Rectangle {
                            id: toggleKnob
                            width: toggleMouse.pressed ? 18 : 14
                            height: 14
                            radius: 7
                            anchors.verticalCenter: parent.verticalCenter
                            x: entryCard.artistAutoCheck ? parent.width - width - 3 : 3
                            color: entryCard.artistAutoCheck 
                                   ? (toggleMouse.containsMouse ? "#6EE7B7" : "#34D399") 
                                   : (toggleMouse.containsMouse ? "#94A3B8" : "#64748B")

                            Behavior on x { NumberAnimation { duration: 220; easing.type: Easing.OutBack; easing.overshoot: 1.6 } }
                            Behavior on width { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }

                        MouseArea {
                            id: toggleMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 350
                            ToolTip.text: entryCard.artistAutoCheck
                                          ? watchListView.view.tr("watchlist_autocheck_on", "Auto-check enabled on launch")
                                          : watchListView.view.tr("watchlist_autocheck_off", "Auto-check disabled")
                            onClicked: {
                                if (watchListView.view.bridge) watchListView.view.bridge.setWatchlistAutoCheck(entryCard.artistUserId, entryCard.artistService, !entryCard.artistAutoCheck)
                            }
                        }
                    }
                }
            }

            WatchlistDateEditorDrawer {
                id: dateEditorContainer
                card: entryCard
                view: watchListView.view
            }

            WatchlistFoldersSection {
                card: entryCard
                view: watchListView.view
            }

            // ── Row 3: Action buttons (Flow layout wraps responsively on narrow widths)
            Flow {
                width: parent.width
                spacing: 8
                bottomPadding: 2

                // Check Single Artist Button
                Rectangle {
                    height: 28
                    implicitWidth: checkArtistRow.implicitWidth + 20
                    radius: 6
                    color: checkArtistMouse.containsMouse ? "#1E1B3D" : "#121024"
                    border.color: entryCard.isArtistChecking ? "#8B5CF6" : (checkArtistMouse.containsMouse ? "#6D28D9" : "#4C1D95")
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Behavior on border.color { ColorAnimation { duration: 100 } }
                    scale: checkArtistMouse.pressed ? 0.94 : (checkArtistMouse.containsMouse ? 1.04 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: checkArtistRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text {
                            text: entryCard.isArtistChecking ? "\u21BB" : "\uD83D\uDD0D"
                            font.pixelSize: entryCard.isArtistChecking ? 12 : 10
                            color: entryCard.isArtistChecking ? "#C4B5FD" : "#A78BFA"
                            anchors.verticalCenter: parent.verticalCenter
                            RotationAnimator on rotation {
                                from: 0; to: 360
                                duration: 800
                                loops: Animation.Infinite
                                running: entryCard.isArtistChecking
                            }
                        }
                        Text {
                            text: entryCard.isArtistChecking
                                  ? watchListView.view.tr("watchlist_checking", "Checking…")
                                  : watchListView.view.tr("watchlist_check_artist", "Check")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: entryCard.isArtistChecking ? "#DDD6FE" : "#C4B5FD"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: checkArtistMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: !entryCard.isArtistChecking && !watchListView.view.isChecking
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: watchListView.view.tr("watchlist_check_artist_tip", "Check only this artist for new posts")
                        onClicked: {
                            if (watchListView.view.bridge) watchListView.view.bridge.checkWatchlistArtist(entryCard.artistUserId, entryCard.artistService)
                        }
                    }
                }

                // Download New Posts Button
                Rectangle {
                    height: 28
                    implicitWidth: dlNewRow.implicitWidth + 20
                    radius: 6
                    visible: entryCard.hasUpdates
                    color: dlNewMouse.containsMouse ? "#0C2D3A" : "#071E26"
                    border.color: dlNewMouse.containsMouse ? "#38BDF8" : "#22D3EE"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Behavior on border.color { ColorAnimation { duration: 100 } }
                    scale: dlNewMouse.pressed ? 0.94 : (dlNewMouse.containsMouse ? 1.04 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: dlNewRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text {
                            text: "↓"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#22D3EE"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: "Download " + entryCard.currentNewPostCount + " New Post" + (entryCard.currentNewPostCount === 1 ? "" : "s")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#A5F3FC"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: dlNewMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "Download all " + entryCard.currentNewPostCount + " new post(s) published by " + (entryCard.artistCreatorName || entryCard.artistUserId)
                        onClicked: {
                            if (watchListView.view.bridge) watchListView.view.bridge.downloadNewPosts(entryCard.artistUserId, entryCard.artistService)
                        }
                    }
                }

                // Review Posts Button
                Rectangle {
                    height: 28
                    implicitWidth: reviewBtnRow.implicitWidth + 18
                    radius: 6
                    visible: entryCard.hasUpdates || entryCard.currentCachedPosts.length > 0
                    color: reviewBtnMouse.containsMouse ? "#182638" : "#0F1A28"
                    border.color: entryCard.isExpanded ? "#38BDF8" : "#243B55"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Behavior on border.color { ColorAnimation { duration: 100 } }
                    scale: reviewBtnMouse.pressed ? 0.94 : (reviewBtnMouse.containsMouse ? 1.04 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack } }

                    Row {
                        id: reviewBtnRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text {
                            text: "▼"
                            font.pixelSize: 9
                            color: "#38BDF8"
                            anchors.verticalCenter: parent.verticalCenter
                            rotation: entryCard.isExpanded ? 180 : 0
                            transformOrigin: Item.Center
                            Behavior on rotation {
                                SpringAnimation {
                                    spring: 3.5
                                    damping: 0.3
                                    mass: 0.9
                                    epsilon: 0.25
                                }
                            }
                        }
                        Text {
                            text: entryCard.isExpanded ? "Hide Review" : "Review Posts"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#BAE6FD"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: reviewBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: watchListView.view.tr("watchlist_review_tip", "Review, selectively download, or ignore specific new posts")
                        onClicked: {
                            var copy = Object.assign({}, watchListView.view.expandedArtists)
                            copy[entryCard.artistKey] = !copy[entryCard.artistKey]
                            watchListView.view.expandedArtists = copy
                        }
                    }
                }

                // Settings (per-creator folder & options)
                Rectangle {
                    objectName: "watchlistSettingsBtn"
                    height: 28
                    implicitWidth: wlSettingsRow.implicitWidth + 20
                    radius: 6
                    color: wlSettingsMouse.containsMouse ? "#151D2E" : "#0D121F"
                    border.color: "#334155"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 100 } }
                    scale: wlSettingsMouse.pressed ? 0.94 : (wlSettingsMouse.containsMouse ? 1.04 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: wlSettingsRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "\u2699"; font.pixelSize: 11; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: watchListView.view.tr("watchlist_entry_settings", "Settings")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: wlSettingsMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: watchListView.view.tr("watchlist_entry_settings_tip", "Edit folder, cutoff date, and creator download settings")
                        onClicked: watchListView.view.openSettingsModal(entryCard.artistUserId, entryCard.artistService)
                    }
                }

                // Re-download All
                Rectangle {
                    objectName: "watchlistRedownloadBtn"
                    height: 28
                    implicitWidth: redownloadRow.implicitWidth + 20
                    radius: 6
                    color: redownloadMouse.containsMouse ? "#1A1430" : "#100E22"
                    border.color: "#4C1D95"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 100 } }
                    scale: redownloadMouse.pressed ? 0.94 : (redownloadMouse.containsMouse ? 1.04 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: redownloadRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "\uD83D\uDD04"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: watchListView.view.tr("watchlist_redownload", "Re-download All")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#A78BFA"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: redownloadMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: watchListView.view.tr("watchlist_redownload_tip", "Delete existing files for this creator and re-download everything with current Watchlist settings")
                        onClicked: watchListView.view.openRedownloadModal(entryCard.artistUserId, entryCard.artistService)
                    }
                }

                // Remove
                Rectangle {
                    height: 28
                    implicitWidth: removeRow.implicitWidth + 20
                    radius: 6
                    color: removeMouse.containsMouse ? "#2A0D0D" : "#1A0808"
                    border.color: "#7F1D1D"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 100 } }
                    scale: removeMouse.pressed ? 0.94 : (removeMouse.containsMouse ? 1.04 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    Row {
                        id: removeRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "\uD83D\uDDD1"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: watchListView.view.tr("watchlist_remove", "Remove")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#FCA5A5"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: removeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: watchListView.view.tr("watchlist_remove_tip", "Stop tracking this artist and remove from watchlist")
                        onClicked: if (watchListView.view.bridge) watchListView.view.bridge.removeFromWatchlist(entryCard.artistUserId, entryCard.artistService)
                    }
                }
            }


            WatchlistReviewDrawer {
                card: entryCard
                view: watchListView.view
            }
        }
    }
}
