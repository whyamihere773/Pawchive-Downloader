import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// ── BrowserMarkTray: Persistent "Marked for Download" Selection Cart Drawer ──
// Docked at the bottom of BrowserView.qml with Newtonian fluid weight-based
// spring physics so users can mark creators and posts across multiple searches
// and providers, then dispatch them to the normal Downloader or Queue in 1 click.
Rectangle {
    id: trayRoot

    property var browserBridge: null
    property bool expanded: false
    property string filterKind: "all" // "all" | "creator" | "post"

    readonly property int markedCount: browserBridge ? browserBridge.markedCount : 0
    readonly property int creatorsCount: browserBridge ? browserBridge.markedCreatorsCount : 0
    readonly property int postsCount: browserBridge ? browserBridge.markedPostsCount : 0
    readonly property var markedModel: browserBridge ? browserBridge.markedItemsModel : null

    readonly property int collapsedHeight: Math.max(54, trayTopFlow.implicitHeight + 20)
    readonly property int expandedHeight: Math.min(320, Math.max(collapsedHeight + 100, Math.floor((parent ? parent.height : 720) * 0.34)))

    visible: height > 0.5
    clip: true
    height: markedCount > 0 ? (expanded ? expandedHeight : collapsedHeight) : 0
    implicitHeight: height
    Layout.preferredHeight: height
    Layout.minimumHeight: 0
    Layout.maximumHeight: height
    opacity: markedCount > 0 ? 1.0 : 0.0
    radius: 12
    color: "#111622"
    border.color: expanded ? "#38BDF8" : "#243049"
    border.width: expanded ? 1.5 : 1

    // Newtonian Fluid Weight-Based Drawer Physics (Heavy Drawer Mass = 1.55)
    Behavior on height {
        NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
    }
    Behavior on opacity {
        NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
    }
    Behavior on border.color {
        ColorAnimation { duration: 180; easing.type: Easing.OutCubic }
    }

    // Badge scale impulse when a new item is marked
    property real badgePulse: 1.0
    onMarkedCountChanged: {
        if (markedCount > 0) {
            badgePulse = 1.24
            pulseResetTimer.restart()
        } else {
            expanded = false
        }
    }
    Timer {
        id: pulseResetTimer
        interval: 45
        repeat: false
        onTriggered: trayRoot.badgePulse = 1.0
    }
    Behavior on badgePulse {
        NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // ── Top Summary Bar (Always Visible When Cart Has Items; Wraps Cleanly When Narrow) ──
        Flow {
            id: trayTopFlow
            Layout.fillWidth: true
            spacing: 8

            // Expand / Collapse Handle + Cart Counter Badge
            Rectangle {
                id: cartTogglePill
                height: 34
                width: Math.min(trayTopFlow.width, toggleRow.implicitWidth + 20)
                clip: true
                radius: 8
                color: toggleMouse.containsMouse ? "#1B2438" : "#161D2E"
                border.color: "#38BDF8"
                border.width: 1
                scale: trayRoot.badgePulse

                Springy { hover: toggleMouse.containsMouse; pressed: toggleMouse.pressed }

                Row {
                    id: toggleRow
                    anchors.centerIn: parent
                    spacing: 8

                    Text {
                        text: "🛒"
                        font.pixelSize: 13
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: "Marked for Download (" + trayRoot.markedCount + ")"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: trayRoot.expanded ? "▾" : "▴"
                        font.pixelSize: 11
                        color: "#38BDF8"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: toggleMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: trayRoot.expanded ? "Collapse marked selection cart" : "Expand to inspect or remove marked creators & posts"
                    onClicked: trayRoot.expanded = !trayRoot.expanded
                }
            }

            // Breakdown Chips (Creators vs Posts)
            Rectangle {
                visible: trayRoot.creatorsCount > 0
                height: 32
                width: Math.min(trayTopFlow.width, cChipRow.implicitWidth + 16)
                clip: true
                radius: 6
                color: trayRoot.filterKind === "creator" ? "#2E1065" : "#161E2E"
                border.color: trayRoot.filterKind === "creator" ? "#A78BFA" : "#26324B"
                border.width: 1
                Springy { hover: cChipMouse.containsMouse; pressed: cChipMouse.pressed }

                Row {
                    id: cChipRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text { text: "👤"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: trayRoot.creatorsCount + (trayRoot.creatorsCount === 1 ? " Creator" : " Creators")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#C4B5FD"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: cChipMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        trayRoot.expanded = true
                        trayRoot.filterKind = (trayRoot.filterKind === "creator") ? "all" : "creator"
                    }
                }
            }

            Rectangle {
                visible: trayRoot.postsCount > 0
                height: 32
                width: Math.min(trayTopFlow.width, pChipRow.implicitWidth + 16)
                clip: true
                radius: 6
                color: trayRoot.filterKind === "post" ? "#0C4A6E" : "#161E2E"
                border.color: trayRoot.filterKind === "post" ? "#38BDF8" : "#26324B"
                border.width: 1
                Springy { hover: pChipMouse.containsMouse; pressed: pChipMouse.pressed }

                Row {
                    id: pChipRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text { text: "🖼️"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: trayRoot.postsCount + (trayRoot.postsCount === 1 ? " Post" : " Posts")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#7DD3FC"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: pChipMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        trayRoot.expanded = true
                        trayRoot.filterKind = (trayRoot.filterKind === "post") ? "all" : "post"
                    }
                }
            }

            // ── Action: Follow Marked Creators in Watchlist ──────────────────
            Rectangle {
                visible: trayRoot.creatorsCount > 0
                height: 32
                width: Math.min(trayTopFlow.width, wlBtnRow.implicitWidth + 18)
                clip: true
                radius: 7
                color: wlMouse.containsMouse ? "#251B42" : "#1A1430"
                border.color: "#8B5CF6"
                border.width: 1
                Springy { hover: wlMouse.containsMouse; pressed: wlMouse.pressed }

                Row {
                    id: wlBtnRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "📌"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "Follow in Watchlist"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#DDD6FE"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: wlMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Add all marked creators to your Watchlist for automatic new-post tracking"
                    onClicked: if (trayRoot.browserBridge) trayRoot.browserBridge.addMarkedCreatorsToWatchlist()
                }
            }

            // ── Action: Add All to Queue (Keep Browsing) ─────────────────────
            Rectangle {
                height: 32
                width: Math.min(trayTopFlow.width, qBtnRow.implicitWidth + 18)
                clip: true
                radius: 7
                color: qMouse.containsMouse ? "#1B2538" : "#151C2B"
                border.color: "#38BDF8"
                border.width: 1
                Springy { hover: qMouse.containsMouse; pressed: qMouse.pressed }

                Row {
                    id: qBtnRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "➕"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "Add to Queue"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#E2E8F0"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: qMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Send all marked items into the normal Downloader Queue without starting immediately"
                    onClicked: if (trayRoot.browserBridge) trayRoot.browserBridge.dispatchMarkedToDownloader(false, false)
                }
            }

            // ── Action: Download Marked Now (Starts Normal Downloader) ───────
            Rectangle {
                height: 32
                width: Math.min(trayTopFlow.width, dlBtnRow.implicitWidth + 22)
                clip: true
                radius: 7
                color: dlMouse.containsMouse ? "#059669" : "#047857"
                border.color: "#34D399"
                border.width: 1
                Springy { hover: dlMouse.containsMouse; pressed: dlMouse.pressed }

                Row {
                    id: dlBtnRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "🚀"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "Download Marked Now"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: "#FFFFFF"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: dlMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Pass all marked creators & posts to the normal Downloader and start downloading immediately"
                    onClicked: if (trayRoot.browserBridge) trayRoot.browserBridge.dispatchMarkedToDownloader(true, false)
                }
            }

            // ── Action: Clear All Marks ──────────────────────────────────────
            Rectangle {
                height: 32
                width: Math.min(trayTopFlow.width, clrRow.implicitWidth + 16)
                clip: true
                radius: 7
                color: clrMouse.containsMouse ? "#351318" : "#221015"
                border.color: "#F43F5E"
                border.width: 1
                Springy { hover: clrMouse.containsMouse; pressed: clrMouse.pressed }

                Row {
                    id: clrRow
                    anchors.centerIn: parent
                    spacing: 4
                    Text { text: "🗑️"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "Clear"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#FDA4AF"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: clrMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (trayRoot.browserBridge) trayRoot.browserBridge.clearMarkedItems()
                }
            }
        }

        // ── Expanded List of Marked Creators & Posts ─────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: trayRoot.expanded
            radius: 8
            color: "#0B0E17"
            border.color: "#1E293B"
            border.width: 1
            clip: true

            SmoothListView {
                id: markedList
                anchors.fill: parent
                anchors.margins: 6
                spacing: 5
                model: trayRoot.markedModel

                delegate: Rectangle {
                    id: rowCard
                    readonly property var itemData: model.creator || modelData || ({})
                    readonly property bool matchesFilter: trayRoot.filterKind === "all" || itemData.item_type === trayRoot.filterKind
                    readonly property bool isCreator: itemData.item_type === "creator"
                    readonly property bool rowHovered: rowMouse.containsMouse || rowHover.hovered

                    width: markedList.width - 10
                    height: matchesFilter ? 42 : 0
                    visible: matchesFilter
                    clip: true
                    radius: 7
                    color: rowHovered ? "#1A263D" : "#121826"
                    border.color: rowHovered ? (isCreator ? "#8B5CF6" : "#38BDF8") : (isCreator ? "#6D28D9" : "#1E3A5F")
                    border.width: 1

                    HoverHandler { id: rowHover }
                    MouseArea {
                        id: rowMouse
                        objectName: "markTrayItemMouse"
                        anchors.fill: parent
                        anchors.rightMargin: 42
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        z: 0
                        onClicked: {
                            if (trayRoot.browserBridge) {
                                trayRoot.browserBridge.openMarkedItem(rowCard.itemData)
                            }
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 10
                        z: 1

                        // Type badge
                        Rectangle {
                            Layout.preferredWidth: 72
                            Layout.preferredHeight: 22
                            radius: 5
                            color: rowCard.itemData.item_type === "creator" ? "#2E1065" : "#0C4A6E"
                            Text {
                                anchors.centerIn: parent
                                text: rowCard.itemData.item_type === "creator" ? "👤 Creator" : "🖼️ Post"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                color: rowCard.itemData.item_type === "creator" ? "#C4B5FD" : "#7DD3FC"
                            }
                        }

                        // Service pill
                        Rectangle {
                            Layout.preferredHeight: 22
                            implicitWidth: svcTxt.implicitWidth + 12
                            radius: 5
                            color: "#1E293B"
                            Text {
                                id: svcTxt
                                anchors.centerIn: parent
                                text: (rowCard.itemData.service_label || rowCard.itemData.service || "").toUpperCase()
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.weight: Font.Bold
                                color: "#94A3B8"
                            }
                        }

                        // Title & Creator
                        Text {
                            Layout.fillWidth: true
                            text: rowCard.itemData.item_type === "creator"
                                  ? (rowCard.itemData.creator_name || rowCard.itemData.title || "")
                                  : ((rowCard.itemData.creator_name ? (rowCard.itemData.creator_name + " — ") : "") + (rowCard.itemData.title || ""))
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: "#F1F5F9"
                            elide: Text.ElideRight
                        }

                        // URL hint
                        Text {
                            Layout.preferredWidth: 220
                            visible: rowCard.width > 620
                            text: rowCard.itemData.url || ""
                            font.family: "Cascadia Code, Consolas, monospace"
                            font.pixelSize: 10
                            color: "#64748B"
                            elide: Text.ElideMiddle
                        }

                        // Navigation hint cue
                        Text {
                            text: rowCard.isCreator ? "Profile →" : "View Post →"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            color: rowCard.rowHovered ? (rowCard.isCreator ? "#C4B5FD" : "#38BDF8") : "#64748B"
                        }

                        // Remove single item button
                        Rectangle {
                            z: 2
                            Layout.preferredWidth: 26
                            Layout.preferredHeight: 26
                            radius: 6
                            color: rmMouse.containsMouse ? "#3F151D" : "#1E293B"
                            border.color: rmMouse.containsMouse ? "#F43F5E" : "transparent"
                            border.width: 1
                            Springy { hover: rmMouse.containsMouse; pressed: rmMouse.pressed }

                            Text {
                                anchors.centerIn: parent
                                text: "✕"
                                font.pixelSize: 11
                                font.bold: true
                                color: rmMouse.containsMouse ? "#FDA4AF" : "#94A3B8"
                            }
                            MouseArea {
                                id: rmMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (trayRoot.browserBridge && rowCard.itemData.key) {
                                        trayRoot.browserBridge.removeMarkedItem(rowCard.itemData.key)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
