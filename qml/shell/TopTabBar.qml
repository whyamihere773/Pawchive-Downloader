import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Browser Tab Header Strip with scrollable tab buttons and right utility actions.
Rectangle {
    id: topTabBar
    required property var window
    function ensureIndexVisible(tabIndex) { tabsFlickable.ensureIndexVisible(tabIndex) }
    Layout.fillWidth: true
    height: 38
    color: "#0B0D12"
    border.color: "#1E2330"
    border.width: 1

            // Left tabs scrollable strip
            Flickable {
id: tabsFlickable
anchors.left: parent.left
anchors.leftMargin: 8
anchors.right: rightActionRow.left
anchors.rightMargin: 8
anchors.top: parent.top
anchors.bottom: parent.bottom
contentWidth: tabsRow.implicitWidth
contentHeight: height
flickableDirection: Flickable.HorizontalFlick
boundsBehavior: Flickable.DragAndOvershootBounds
clip: true

WheelHandler {
    id: tabsWheel
    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
    onWheel: function(event) {
        var delta = event.angleDelta.y || event.angleDelta.x
        tabsFlickable.flick(delta * 10, 0)
    }
}

NumberAnimation {
    id: tabsScrollAnim
    target: tabsFlickable
    property: "contentX"
    duration: 220
    easing.type: Easing.OutCubic
}

function scrollBy(delta) {
    tabsScrollAnim.stop()
    var maxContentX = Math.max(0, contentWidth - width)
    var targetX = Math.max(0, Math.min(maxContentX, contentX + delta))
    tabsScrollAnim.to = targetX
    tabsScrollAnim.start()
}

function ensureIndexVisible(tabIndex) {
    if (contentWidth <= width) return
    var tabItem = null
    for (var i = 0; i < tabsRow.children.length; i++) {
        var ch = tabsRow.children[i]
        if (ch && ch.tabIdx !== undefined && ch.tabIdx === tabIndex) {
            tabItem = ch
            break
        }
    }
    if (!tabItem && tabIndex >= 0 && tabIndex < tabsRow.children.length) {
        tabItem = tabsRow.children[tabIndex]
    }
    if (!tabItem) return
    var pad = 36
    var tabLeft = tabItem.x
    var tabRight = tabItem.x + tabItem.width
    if (tabLeft < contentX + pad) {
        scrollBy(tabLeft - contentX - pad)
    } else if (tabRight > contentX + width - pad) {
        scrollBy(tabRight - (contentX + width) + pad)
    }
}

Row {
    id: tabsRow
    anchors.verticalCenter: parent.verticalCenter
    spacing: 4

            TopTabButton {
                window: topTabBar.window
                tabIdx: 0
                alwaysPermitted: true
                iconText: "📥"
                labelText: topTabBar.window.tr("tab_downloader", "Downloader")
                tipText: topTabBar.window.tr("tab_downloader_tip", "Downloader configuration and execution")
            }
            TopTabButton {
                id: browserTabCard
                window: topTabBar.window
                tabIdx: 1
                tabKey: "browser"
                iconText: "🌐"
                labelText: topTabBar.window.tr("tab_browser", "Browser")
                tipText: topTabBar.window.tr("tab_browser_tip", "Native In-App Browser (cum.st, pawchive.pw, coomerfans.com) + Multi-Drive On-Disk Local Browser")
                badgeCount: (typeof browserBridge !== "undefined" && browserBridge) ? browserBridge.markedCount : 0
                badgeColor: "#0284C7"
            }
            TopTabButton {
                window: topTabBar.window
                tabIdx: 2
                tabKey: "queue"
                iconText: "📋"
                labelText: topTabBar.window.tr("tab_queue", "Queue")
                tipText: topTabBar.window.tr("tab_queue_tip", "Task queue and file download monitoring")
            }
            TopTabButton {
                id: watchlistTabCard
                window: topTabBar.window
                tabIdx: 3
                tabKey: "watchlist"
                iconText: "📌"
                labelText: topTabBar.window.tr("tab_watchlist", "Watchlist")
                tipText: topTabBar.window.tr("tab_watchlist_tip", "Followed artists — track and download new posts automatically")
                activeBorderColor: "#A78BFA"
                badgeCount: appBridge && appBridge.watchlistModel ? appBridge.watchlistModel.updatedCount : 0
                badgeColor: "#7C3AED"
            }
            TopTabButton {
                window: topTabBar.window
                tabIdx: 4
                tabKey: "decompressor"
                iconText: "📦"
                labelText: topTabBar.window.tr("tab_bulk_decompressor", "Decompressor")
                tipText: topTabBar.window.tr("tab_decompressor_tip", "Bulk archive decompression with disk space pre-flight checks and parallel extraction")
            }
            TopTabButton {
                window: topTabBar.window
                tabIdx: 5
                tabKey: "link_vault"
                iconText: "🗝️"
                labelText: topTabBar.window.tr("tab_link_vault", "Link Vault")
                tipText: topTabBar.window.tr("tab_link_vault_tip", "Permanent archive of harvested cloud links, smart passwords, and dead link cleanup")
                activeBorderColor: "#F59E0B"
            }
            TopTabButton {
                window: topTabBar.window
                tabIdx: 6
                tabKey: "scheduler"
                iconText: "⏰"
                labelText: topTabBar.window.tr("tab_scheduler", "Scheduler")
                tipText: topTabBar.window.tr("tab_scheduler_tip", "Automated Watchlist delta sync, scheduled creator backups, and Night Owl windows")
                activeBorderColor: "#818CF8"
            }
            TopTabButton {
                window: topTabBar.window
                tabIdx: 7
                tabKey: "gallery"
                iconText: "🖼️"
                labelText: topTabBar.window.tr("tab_gallery", "Gallery")
                tipText: topTabBar.window.tr("tab_gallery_tip", "File Explorer & Media Gallery — browse downloads, preview media, and organize your collection")
                activeBorderColor: "#EC4899"
            }
            TopTabButton {
                window: topTabBar.window
                tabIdx: 8
                tabKey: "known"
                iconText: "🏷️"
                labelText: topTabBar.window.tr("tab_known", "Known Series")
                tipText: topTabBar.window.tr("tab_known_tip", "Known character and series directory rules (Known.txt)")
            }
            TopTabButton {
                window: topTabBar.window
                tabIdx: 9
                tabKey: "archive"
                iconText: "🗃️"
                labelText: topTabBar.window.tr("tab_archive", "Archive")
                tipText: topTabBar.window.tr("tab_archive_tip", "Download archive database — persistent record of all downloaded files")
                activeBorderColor: "#2DD4BF"
            }
            TopTabButton {
                window: topTabBar.window
                tabIdx: 10
                tabKey: "history"
                iconText: "📜"
                labelText: topTabBar.window.tr("tab_history", "History")
                tipText: topTabBar.window.tr("tab_history_tip", "Completed downloads and past batch sessions")
            }
            TopTabButton {
                window: topTabBar.window
                tabIdx: 11
                tabKey: "statistics"
                iconText: "📊"
                labelText: topTabBar.window.tr("tab_statistics", "Statistics")
                tipText: topTabBar.window.tr("tab_statistics_tip", "Raw network bandwidth, disk storage, artists, files & folders data")
            }
            TopTabButton {
                window: topTabBar.window
                tabIdx: 12
                alwaysPermitted: true
                iconText: "⚙️"
                labelText: topTabBar.window.tr("tab_settings", "Settings")
                tipText: topTabBar.window.tr("tab_settings_tip", "Global application and network configuration")
            }
    } // tabsRow
} // tabsFlickable

    // Left scroll edge hint & button
    Rectangle {
        id: tabsScrollLeftBtn
        anchors.left: tabsFlickable.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 28
        z: 4
        visible: tabsFlickable.contentWidth > tabsFlickable.width && tabsFlickable.contentX > 4
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "#0B0D12" }
            GradientStop { position: 0.65; color: "#D80B0D12" }
            GradientStop { position: 1.0; color: "transparent" }
        }

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            width: 20
            height: 24
            radius: 4
            color: tabsLeftMouse.containsMouse ? "#1E293B" : "#141720"
            border.color: tabsLeftMouse.containsMouse ? "#38BDF8" : "#334155"
            border.width: 1

            Text {
                anchors.centerIn: parent
                text: "‹"
                font.bold: true
                font.pixelSize: 15
                color: tabsLeftMouse.containsMouse ? "#38BDF8" : "#94A3B8"
            }

            MouseArea {
                id: tabsLeftMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: topTabBar.window.tr("tip_scroll_tabs_left", "Scroll tabs left (or use mouse wheel)")
                onClicked: tabsFlickable.scrollBy(-180)
            }
        }
    }

    // Right scroll edge hint & button
    Rectangle {
        id: tabsScrollRightBtn
        anchors.right: tabsFlickable.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 28
        z: 4
        visible: tabsFlickable.contentWidth > tabsFlickable.width && tabsFlickable.contentX < (tabsFlickable.contentWidth - tabsFlickable.width - 4)
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.35; color: "#D80B0D12" }
            GradientStop { position: 1.0; color: "#0B0D12" }
        }

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
            width: 20
            height: 24
            radius: 4
            color: tabsRightMouse.containsMouse ? "#1E293B" : "#141720"
            border.color: tabsRightMouse.containsMouse ? "#38BDF8" : "#334155"
            border.width: 1

            Text {
                anchors.centerIn: parent
                text: "›"
                font.bold: true
                font.pixelSize: 15
                color: tabsRightMouse.containsMouse ? "#38BDF8" : "#94A3B8"
            }

            MouseArea {
                id: tabsRightMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: topTabBar.window.tr("tip_scroll_tabs_right", "Scroll tabs right (or use mouse wheel)")
                onClicked: tabsFlickable.scrollBy(180)
            }
        }
    }

    // Micro-scrollbar track and indicator along bottom of tabs strip
    Rectangle {
        id: tabsScrollBarTrack
        anchors.left: tabsFlickable.left
        anchors.right: tabsFlickable.right
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 1
        height: 2
        color: "#161B26"
        visible: tabsFlickable.contentWidth > tabsFlickable.width
        z: 3
        radius: 1

        Rectangle {
            id: tabsScrollBarThumb
            height: 2
            radius: 1
            color: (tabsLeftMouse.containsMouse || tabsRightMouse.containsMouse || tabsFlickable.moving || tabsFlickable.flicking) ? "#38BDF8" : "#0284C7"
            opacity: tabsFlickable.contentWidth > tabsFlickable.width ? 0.85 : 0.0
            x: tabsFlickable.contentWidth > tabsFlickable.width ? Math.max(0, Math.min(tabsScrollBarTrack.width - width, (tabsFlickable.contentX / tabsFlickable.contentWidth) * tabsScrollBarTrack.width)) : 0
            width: tabsFlickable.contentWidth > 0 ? Math.max(28, (tabsFlickable.width / tabsFlickable.contentWidth) * tabsScrollBarTrack.width) : 0

            Behavior on color { ColorAnimation { duration: 150 } }
        }
    }

    // Right utility buttons: ALWAYS anchored to right edge, NEVER cut off
    RowLayout {
        id: rightActionRow
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 6
        z: 5

        // Update Available Notification Pill (Visible when updateAvailable is true)
        Rectangle {
            visible: (typeof updaterBridge !== "undefined" && updaterBridge && updaterBridge.updateAvailable)
            height: 28
            implicitWidth: upRow.implicitWidth + 18
            radius: 14
            color: upMouse.containsMouse ? "#0284C7" : "#0369A1"
            border.color: "#38BDF8"
            border.width: 1

            scale: upMouse.pressed ? 0.94 : (upMouse.containsMouse ? 1.05 : 1.0)
            transformOrigin: Item.Center

            Behavior on scale { NumberAnimation { duration: 160 } }
            Behavior on color { ColorAnimation { duration: 150 } }

            Row {
                id: upRow
                anchors.centerIn: parent
                spacing: 6
                Text { text: "✨"; font.pixelSize: 11 }
                Text {
                    text: topTabBar.window.tr("badge_update_avail", "Update Available")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                }
            }

            MouseArea {
                id: upMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: topTabBar.window.tr("tip_update_pill", "New version detected on GitHub — click to download and install")
                onClicked: topTabBar.window.openUpdateModal()
            }
        }

        // Tutorial / Help button
        Rectangle {
            height: 28
            implicitWidth: tutRow.implicitWidth + 16
            radius: 6
            color: tutMouse.containsMouse ? "#222C3D" : "#141923"
            border.color: tutMouse.containsMouse ? "#38BDF8" : "#242A38"
            border.width: 1

            scale: tutMouse.pressed ? 0.94 : (tutMouse.containsMouse ? 1.04 : 1.0)
            transformOrigin: Item.Center

            Behavior on scale { NumberAnimation { duration: 160 } }
            Behavior on color { ColorAnimation { duration: 150 } }

            Row {
                id: tutRow
                anchors.centerIn: parent
                spacing: 6
                Text { text: "❓"; font.pixelSize: 12 }
                Text {
                    text: topTabBar.window.tr("btn_tutorial", "Tutorial")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#E2E8F0"
                }
            }

            MouseArea {
                id: tutMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: topTabBar.window.tr("tip_tutorial", "Open interactive tutorial and feature manual")
                onClicked: topTabBar.window.openTutorialModal()
            }
        }

        // DEV DEBUGGING: Real-time FPS & Refresh Rate Counter Pill 
        /*
        Rectangle {
            id: fpsPill
            height: 24
            implicitWidth: fpsRow.implicitWidth + 14
            radius: 12
            color: fpsMouse.containsMouse ? "#182030" : "#111520"
            border.color: fpsPill.motionTestActive ? "#4ADE80" : (fpsMouse.containsMouse ? "#38BDF8" : "#1E2738")
            border.width: 1

            property int fps: appBridge ? appBridge.currentFps : 0
            property int hz: appBridge ? appBridge.screenHz : (topTabBar.window.screen ? Math.round(topTabBar.window.screen.refreshRate) : 60)
            property bool motionTestActive: false

            // Dummy hidden item that runs a continuous 60-165 FPS animation when fluid motion test is active
            Item {
                id: dummyMotionDriver
                width: 1; height: 1
                visible: fpsPill.motionTestActive
                NumberAnimation on x {
                    running: fpsPill.motionTestActive
                    from: 0; to: 1000; duration: 2000; loops: Animation.Infinite
                }
            }

            RowLayout {
                id: fpsRow
                anchors.centerIn: parent
                spacing: 4

                // Real-time status dot
                Rectangle {
                    width: 6
                    height: 6
                    radius: 3
                    color: {
                        if (fpsPill.motionTestActive) return "#4ADE80"
                        if (fpsPill.fps >= (fpsPill.hz - 8)) return "#4ADE80"
                        if (fpsPill.fps > 0) return "#38BDF8"
                        return "#64748B"
                    }
                    Behavior on color { ColorAnimation { duration: 180 } }
                }

                Text {
                    text: {
                        if (fpsPill.fps > 0) return fpsPill.fps + " FPS"
                        return fpsPill.hz + " Hz"
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: {
                        if (fpsPill.motionTestActive) return "#4ADE80"
                        if (fpsPill.fps >= (fpsPill.hz - 8)) return "#4ADE80"
                        if (fpsPill.fps > 0) return "#38BDF8"
                        return "#94A3B8"
                    }
                }
            }

            MouseArea {
                id: fpsMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: topTabBar.window.tr("tip_fps_pill", "Hardware Display: " + fpsPill.hz + "Hz. Click to " + (fpsPill.motionTestActive ? "stop" : "start") + " fluid " + fpsPill.hz + " FPS motion test.")
                onClicked: fpsPill.motionTestActive = !fpsPill.motionTestActive
            }
        }
        */

        // Version Badge
        Rectangle {
            height: 24
            implicitWidth: verRow.implicitWidth + 16
            radius: 12
            color: "#131722"
            border.color: "#222B3D"
            border.width: 1

            RowLayout {
                id: verRow
                anchors.centerIn: parent
                spacing: 1

                Text {
                    text: "v"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#64748B"
                }

                Text {
                    text: (typeof updaterBridge !== "undefined" && updaterBridge && updaterBridge.currentVersion) ? updaterBridge.currentVersion : ""
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 700
                    color: "#38BDF8"
                }
            }
        }

        // Privacy Mode toggle button (Eye: open when off, closed when enabled)
        Rectangle {
            width: 32
            height: 30
            radius: 6
            color: (appBridge && appBridge.privacyModeActive) ? "#1E2536" : (privacyBtnMouse.containsMouse ? "#181B22" : "transparent")
            border.color: (appBridge && appBridge.privacyModeActive) ? "#38BDF8" : (privacyBtnMouse.containsMouse ? "#38455E" : "#242A38")
            border.width: 1

            scale: privacyBtnMouse.pressed ? 0.90 : (privacyBtnMouse.containsMouse ? 1.08 : 1.0)
            transformOrigin: Item.Center

            Behavior on scale {
                NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
            }
            Behavior on color { ColorAnimation { duration: 150 } }
            Behavior on border.color { ColorAnimation { duration: 150 } }

            Image {
                anchors.centerIn: parent
                width: 16
                height: 16
                sourceSize: Qt.size(16, 16)
                source: (appBridge && appBridge.privacyModeActive)
                        ? "../../assets/icons/eye_closed.svg"
                        : (privacyBtnMouse.containsMouse ? "../../assets/icons/eye_open_hover.svg" : "../../assets/icons/eye_open.svg")
            }

            MouseArea {
                id: privacyBtnMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 400
                ToolTip.text: (appBridge && appBridge.privacyModeActive)
                              ? topTabBar.window.tr("tip_privacy_mode_on", "Privacy Mode is ON (Ctrl+P to unblur)")
                              : topTabBar.window.tr("tip_privacy_mode_off", "Privacy Mode — blur application content (Ctrl+P)")
                onClicked: {
                    if (appBridge) appBridge.togglePrivacyMode()
                }
            }
        }

        // Console toggle button
        Rectangle {
            width: 32
            height: 30
            radius: 6
            color: topTabBar.window.showConsole ? "#222C3D" : (consoleBtnMouse.containsMouse ? "#181B22" : "transparent")
            border.color: topTabBar.window.showConsole ? "#38BDF8" : "#242A38"
            border.width: 1

            scale: consoleBtnMouse.pressed ? 0.90 : (consoleBtnMouse.containsMouse ? 1.10 : 1.0)
            transformOrigin: Item.Center

            Behavior on scale {
                NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
            }
            Behavior on color { ColorAnimation { duration: 150 } }
            Behavior on border.color { ColorAnimation { duration: 150 } }

            Text {
                anchors.centerIn: parent
                text: "💻"
                font.pixelSize: 13
            }

            MouseArea {
                id: consoleBtnMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 400
                ToolTip.text: topTabBar.window.showConsole ? topTabBar.window.tr("console_hide_tip", "Hide Progress Log console") : topTabBar.window.tr("console_show_tip", "Show Progress Log console")
                onClicked: topTabBar.window.showConsole = !topTabBar.window.showConsole

            }
        }
    }
}
