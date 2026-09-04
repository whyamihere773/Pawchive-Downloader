import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "components"
import "views"

ApplicationWindow {
    id: appWindow
    width: 1200
    height: 780
    minimumWidth: 900
    minimumHeight: 600
    visible: true
    title: "Pawchive Downloader v1.0.5"
    color: "#0F1117"

    // Stop active downloads and persist session gracefully when user closes the app
    onClosing: {
        if (appBridge) {
            appBridge.onAppClosing()
        }
    }

    property bool showConsole: true
    property int currentTab: 0 // 0: Downloader, 1: Queue, 2: Known, 3: History, 4: Settings

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }


    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // 1. Browser Tab Header Strip
        Rectangle {
            Layout.fillWidth: true
            height: 38
            color: "#0B0D12"
            border.color: "#1E2330"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 4

                // Tab: Downloader
                Rectangle {
                    width: Math.max(110, tab0Row.implicitWidth + 24)
                    height: 30
                    radius: 6
                    color: appWindow.currentTab === 0 ? "#181B22" : (tab0Mouse.containsMouse ? "#141720" : "transparent")
                    border.color: appWindow.currentTab === 0 ? "#38BDF8" : "transparent"
                    border.width: 1

                    scale: tab0Mouse.pressed ? 0.94 : (tab0Mouse.containsMouse ? 1.035 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
                    }
                    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                    Behavior on border.color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }

                    Row {
                        id: tab0Row
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "📥"; font.pixelSize: 12 }
                        Text {
                            text: appWindow.tr("tab_downloader", "Downloader")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: appWindow.currentTab === 0 ? Font.DemiBold : Font.Normal
                            color: appWindow.currentTab === 0 ? "#F8FAFC" : "#94A3B8"
                        }
                    }

                    MouseArea {
                        id: tab0Mouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: appWindow.tr("tab_downloader_tip", "Downloader configuration and execution")
                        onClicked: appWindow.currentTab = 0
                    }
                }

                // Tab: Queue
                Rectangle {
                    width: Math.max(90, tab1Row.implicitWidth + 24)
                    height: 30
                    radius: 6
                    color: appWindow.currentTab === 1 ? "#181B22" : (tab1Mouse.containsMouse ? "#141720" : "transparent")
                    border.color: appWindow.currentTab === 1 ? "#38BDF8" : "transparent"
                    border.width: 1

                    scale: tab1Mouse.pressed ? 0.94 : (tab1Mouse.containsMouse ? 1.035 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
                    }
                    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                    Behavior on border.color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }

                    Row {
                        id: tab1Row
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "📋"; font.pixelSize: 12 }
                        Text {
                            text: appWindow.tr("tab_queue", "Queue")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: appWindow.currentTab === 1 ? Font.DemiBold : Font.Normal
                            color: appWindow.currentTab === 1 ? "#F8FAFC" : "#94A3B8"
                        }
                    }

                    MouseArea {
                        id: tab1Mouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: appWindow.tr("tab_queue_tip", "Task queue and file download monitoring")
                        onClicked: appWindow.currentTab = 1
                    }
                }

                // Tab: Known Characters
                Rectangle {
                    width: Math.max(120, tab2Row.implicitWidth + 24)
                    height: 30
                    radius: 6
                    color: appWindow.currentTab === 2 ? "#181B22" : (tab2Mouse.containsMouse ? "#141720" : "transparent")
                    border.color: appWindow.currentTab === 2 ? "#38BDF8" : "transparent"
                    border.width: 1

                    scale: tab2Mouse.pressed ? 0.94 : (tab2Mouse.containsMouse ? 1.035 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
                    }
                    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                    Behavior on border.color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }

                    Row {
                        id: tab2Row
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🏷️"; font.pixelSize: 12 }
                        Text {
                            text: appWindow.tr("tab_known", "Known Series")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: appWindow.currentTab === 2 ? Font.DemiBold : Font.Normal
                            color: appWindow.currentTab === 2 ? "#F8FAFC" : "#94A3B8"
                        }
                    }

                    MouseArea {
                        id: tab2Mouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: appWindow.tr("tab_known_tip", "Known character and series directory rules (Known.txt)")
                        onClicked: appWindow.currentTab = 2
                    }
                }

                // Tab: History
                Rectangle {
                    width: Math.max(90, tab3Row.implicitWidth + 24)
                    height: 30
                    radius: 6
                    color: appWindow.currentTab === 3 ? "#181B22" : (tab3Mouse.containsMouse ? "#141720" : "transparent")
                    border.color: appWindow.currentTab === 3 ? "#38BDF8" : "transparent"
                    border.width: 1

                    scale: tab3Mouse.pressed ? 0.94 : (tab3Mouse.containsMouse ? 1.035 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
                    }
                    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                    Behavior on border.color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }

                    Row {
                        id: tab3Row
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "📜"; font.pixelSize: 12 }
                        Text {
                            text: appWindow.tr("tab_history", "History")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: appWindow.currentTab === 3 ? Font.DemiBold : Font.Normal
                            color: appWindow.currentTab === 3 ? "#F8FAFC" : "#94A3B8"
                        }
                    }

                    MouseArea {
                        id: tab3Mouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: appWindow.tr("tab_history_tip", "Completed downloads and past batch sessions")
                        onClicked: appWindow.currentTab = 3
                    }
                }

                // Tab: Settings
                Rectangle {
                    width: Math.max(90, tab4Row.implicitWidth + 24)
                    height: 30
                    radius: 6
                    color: appWindow.currentTab === 4 ? "#181B22" : (tab4Mouse.containsMouse ? "#141720" : "transparent")
                    border.color: appWindow.currentTab === 4 ? "#38BDF8" : "transparent"
                    border.width: 1

                    scale: tab4Mouse.pressed ? 0.94 : (tab4Mouse.containsMouse ? 1.035 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
                    }
                    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                    Behavior on border.color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }

                    Row {
                        id: tab4Row
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "⚙️"; font.pixelSize: 12 }
                        Text {
                            text: appWindow.tr("tab_settings", "Settings")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: appWindow.currentTab === 4 ? Font.DemiBold : Font.Normal
                            color: appWindow.currentTab === 4 ? "#F8FAFC" : "#94A3B8"
                        }
                    }

                    MouseArea {
                        id: tab4Mouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: appWindow.tr("tab_settings_tip", "Global application and network configuration")
                        onClicked: appWindow.currentTab = 4
                    }
                }

                Item { Layout.fillWidth: true }

                // Version Badge
                Rectangle {
                    height: 24
                    implicitWidth: verText.implicitWidth + 14
                    radius: 12
                    color: "#131722"
                    border.color: "#222B3D"
                    border.width: 1

                    Text {
                        id: verText
                        anchors.centerIn: parent
                        text: "v1.0.5"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        color: "#64748B"
                    }
                }

                // Console toggle button
                Rectangle {
                    width: 32
                    height: 30
                    radius: 6
                    color: appWindow.showConsole ? "#222C3D" : (consoleBtnMouse.containsMouse ? "#181B22" : "transparent")
                    border.color: appWindow.showConsole ? "#38BDF8" : "#242A38"
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
                        ToolTip.text: appWindow.showConsole ? appWindow.tr("console_hide_tip", "Hide Progress Log console") : appWindow.tr("console_show_tip", "Show Progress Log console")
                        onClicked: appWindow.showConsole = !appWindow.showConsole

                    }
                }
            }
        }

        // 2. Omnibox Browser Navigation Bar
        BrowserNavBar {
            id: navBar
            Layout.fillWidth: true
            bridge: appBridge
            onQueueRequested: {
                if (appBridge) appBridge.addToQueue()
            }
            onSettingsRequested: {
                appWindow.currentTab = 4
            }
        }

        // 2b. Creator Name Banner (shown with fluid Newtonian spring entrance after URL resolves)
        Rectangle {
            id: creatorBanner
            Layout.fillWidth: true
            property bool hasCreator: appBridge ? appBridge.creatorName.length > 0 : false
            visible: hasCreator
            implicitHeight: 28
            Layout.preferredHeight: 28
            color: "#0D1019"
            border.color: "#25334D"
            border.width: 1
            radius: 6
            clip: true

            opacity: hasCreator ? 1.0 : 0.0
            scale: hasCreator ? 1.0 : 0.95
            transformOrigin: Item.Center

            Behavior on opacity {
                NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
            }
            Behavior on scale {
                NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.3 }
            }
            Behavior on border.color {
                ColorAnimation { duration: 200 }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 8

                Text {
                    text: "👤"
                    font.pixelSize: 12
                    scale: (appBridge && appBridge.creatorName.length > 0) ? 1.0 : 0.2
                    Behavior on scale {
                        NumberAnimation { duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.8 }
                    }
                }

                Text {
                    text: tr("label_creator", "Creator:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                }

                Text {
                    text: appBridge ? appBridge.creatorName : ""
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: "#38BDF8"
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                // Service tag if in URL
                Rectangle {
                    implicitHeight: 20
                    implicitWidth: svcTag.implicitWidth + 14
                    Layout.preferredHeight: 20
                    Layout.preferredWidth: svcTag.implicitWidth + 14
                    Layout.alignment: Qt.AlignVCenter
                    radius: 4
                    color: "#1A2030"
                    border.color: "#2D3748"
                    border.width: 1
                    visible: appBridge ? (appBridge.currentUrl.length > 0 && svcTag.text.length > 0) : false

                    Text {
                        id: svcTag
                        anchors.centerIn: parent
                        text: {
                            if (!appBridge) return ""
                            var u = appBridge.currentUrl.toLowerCase()
                            if (u.indexOf("/fanbox/") >= 0) return "Fanbox"
                            if (u.indexOf("/patreon/") >= 0) return "Patreon"
                            if (u.indexOf("/onlyfans/") >= 0) return "OnlyFans"
                            if (u.indexOf("/fansly/") >= 0) return "Fansly"
                            if (u.indexOf("/gumroad/") >= 0) return "Gumroad"
                            if (u.indexOf("/subscribestar/") >= 0) return "SubscribeStar"
                            if (u.indexOf("/fantia/") >= 0) return "Fantia"
                            if (u.indexOf("/boosty/") >= 0) return "Boosty"
                            if (u.indexOf("/dlsite/") >= 0) return "DLsite"
                            if (u.indexOf("/discord/") >= 0) return "Discord"
                            if (u.indexOf("bunkr") >= 0) return "Bunkr"
                            if (u.indexOf("erome") >= 0) return "Erome"
                            if (u.indexOf("nhentai") >= 0) return "nHentai"
                            if (u.indexOf("saint2") >= 0) return "Saint2"
                            return ""
                        }
                        font.pixelSize: 9
                        font.bold: true
                        color: "#94A3B8"
                    }
                }
            }
        }

        // ── Sticky Download Action Bar ─────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 52
            color: "#0C0F16"
            border.color: "#1A2035"
            border.width: 1

            // Subtle gradient top accent line
            Rectangle {
                width: parent.width
                height: 1
                anchors.top: parent.top
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.3; color: "#38BDF8" }
                    GradientStop { position: 0.7; color: "#A78BFA" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 6

                // ── PRIMARY: Start Download / Extract Links / Downloading indicator ────
                Rectangle {
                    id: mainStartBtn
                    property bool isLinksMode: appBridge ? appBridge.filterType === "links" : false
                    property bool isDownloading: appBridge ? appBridge.isDownloading : false

                    Layout.preferredWidth: Math.max(isLinksMode ? 162 : 148, startBtnRow.implicitWidth + 28)
                    Layout.preferredHeight: 34
                    radius: 7

                    color: mainStartBtn.isDownloading
                        ? "#0F2A1A"
                        : (startBtnMouse.containsMouse
                            ? (mainStartBtn.isLinksMode ? "#0D3330" : "#1a3a52")
                            : (mainStartBtn.isLinksMode ? "#0A2825" : "#0D2137"))
                    border.color: mainStartBtn.isDownloading ? "#10B981" : (mainStartBtn.isLinksMode ? "#2DD4BF" : "#38BDF8")
                    border.width: 1
                    opacity: mainStartBtn.isDownloading ? 0.7 : 1.0

                    scale: startBtnMouse.pressed ? 0.94 : (startBtnMouse.containsMouse ? 1.03 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }
                    Behavior on color { ColorAnimation { duration: 150 } }
                    Behavior on border.color { ColorAnimation { duration: 150 } }
                    Behavior on Layout.preferredWidth { NumberAnimation { duration: 200; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }

                    Row {
                        id: startBtnRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: mainStartBtn.isDownloading ? "⏳" : (mainStartBtn.isLinksMode ? "🔗" : "⚡")
                            font.pixelSize: 13
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: mainStartBtn.isDownloading ? appWindow.tr("action_downloading", "Downloading…")
                                : (mainStartBtn.isLinksMode ? appWindow.tr("action_extract_links", "Extract Links") : appWindow.tr("action_start_download", "Start Download"))
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: mainStartBtn.isDownloading ? "#34D399" : (mainStartBtn.isLinksMode ? "#2DD4BF" : "#38BDF8")
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: startBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: mainStartBtn.isDownloading ? Qt.ArrowCursor : Qt.PointingHandCursor
                        enabled: !mainStartBtn.isDownloading
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: mainStartBtn.isLinksMode
                            ? appWindow.tr("tip_extract_links", "Scan posts for external cloud links (Mega.nz, Drive, Dropbox, etc.) — no files downloaded")
                            : appWindow.tr("tip_start_download", "Fetch posts from the URL and start downloading immediately")
                        onClicked: if (appBridge) appBridge.startDownload()
                    }
                }

                // ── Add to Queue ────────────────────────────────────────────
                Rectangle {
                    Layout.preferredWidth: Math.max(116, queueRow.implicitWidth + 24)
                    Layout.preferredHeight: 34
                    radius: 7
                    color: queueBtnMouse.containsMouse ? "#1A1F2E" : "#131722"
                    border.color: "#2E3A56"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: queueRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "➕"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: appWindow.tr("action_add_to_queue", "Add to Queue")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: queueBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: appWindow.tr("tip_add_to_queue", "Add all matched files to the queue without auto-starting download")
                        onClicked: if (appBridge) appBridge.addToQueue()
                    }
                }

                // ── Thin separator ──────────────────────────────────────────
                Rectangle { width: 1; height: 28; color: "#1E293B"; Layout.alignment: Qt.AlignVCenter }

                // ── Pause / Resume (shown only while downloading) ───────────
                Rectangle {
                    Layout.preferredWidth: Math.max(100, pauseRow.implicitWidth + 24)
                    Layout.preferredHeight: 34
                    radius: 7
                    visible: appBridge ? appBridge.isDownloading : false
                    color: pauseBtnMouse.containsMouse ? "#1C1A08" : "#141208"
                    border.color: "#FBBF24"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: pauseRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: (appBridge && appBridge.statusText.indexOf("Paused") >= 0) ? "▶" : "⏸"
                            font.pixelSize: 12
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: (appBridge && appBridge.statusText.indexOf("Paused") >= 0) ? appWindow.tr("action_resume", "Resume") : appWindow.tr("action_pause", "Pause")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#FBBF24"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: pauseBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: (appBridge && appBridge.statusText.indexOf("Paused") >= 0)
                                      ? appWindow.tr("tip_resume_download", "Resume paused download") : appWindow.tr("tip_pause_download", "Pause the active download (can be resumed)")
                        onClicked: {
                            if (!appBridge) return
                            if (appBridge.statusText.indexOf("Paused") >= 0)
                                appBridge.resumeDownload()
                            else
                                appBridge.pauseDownload()
                        }
                    }
                }

                // ── Cancel (shown only while downloading) ───────────────────
                Rectangle {
                    Layout.preferredWidth: Math.max(86, cancelRow.implicitWidth + 24)
                    Layout.preferredHeight: 34
                    radius: 7
                    visible: appBridge ? appBridge.isDownloading : false
                    color: cancelBtnMouse.containsMouse ? "#2A0D0D" : "#1C0808"
                    border.color: "#EF4444"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: cancelRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "⏹"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: appWindow.tr("action_cancel", "Cancel")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#F87171"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: cancelBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: appWindow.tr("tip_cancel_download", "Cancel the active download (session preserved for restore)")
                        onClicked: if (appBridge) appBridge.cancelDownload()
                    }
                }

                // ── Thin separator ──────────────────────────────────────────
                Rectangle { width: 1; height: 28; color: "#1E293B"; Layout.alignment: Qt.AlignVCenter }

                // ── Retry Failed ────────────────────────────────────────────
                Rectangle {
                    id: retryFailedBtn
                    property int failedCount: (appBridge && appBridge.queueModel) ? appBridge.queueModel.failedCount : 0
                    Layout.preferredWidth: Math.max(106, retryFailedRow.implicitWidth + 22)
                    Layout.preferredHeight: 34
                    radius: 7
                    color: failedCount > 0
                           ? (retryBtnMouse.containsMouse ? "#2A1010" : "#1E0A0A")
                           : (retryBtnMouse.containsMouse ? "#181B28" : "#111420")
                    border.color: failedCount > 0 ? "#EF4444" : "#2E3A56"
                    border.width: 1
                    opacity: failedCount > 0 ? 1.0 : 0.5
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on opacity { NumberAnimation { duration: 180 } }

                    Row {
                        id: retryFailedRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🔁"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: retryFailedBtn.failedCount > 0
                                  ? appWindow.tr("action_retry_failed_count", "Retry Failed (%1)").replace("%1", retryFailedBtn.failedCount)
                                  : appWindow.tr("action_retry_failed", "Retry Failed")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: retryFailedBtn.failedCount > 0 ? "#FCA5A5" : "#64748B"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: retryBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: appWindow.tr("tip_retry_failed_dialog", "Open dialog to inspect and retry failed downloads")
                        onClicked: mainRetryModal.isOpen = true
                    }
                }

                // ── Download Cloud Links button (visible when harvested links exist) ──
                Rectangle {
                    id: cloudDownloadStickyBtn
                    property int count: appBridge ? appBridge.harvestedLinksCount : 0
                    visible: count > 0
                    Layout.preferredWidth: Math.max(165, cloudRow.implicitWidth + 24)
                    Layout.preferredHeight: 34
                    radius: 7
                    color: cloudBtnMouse.containsMouse ? "#0D3330" : "#0A2825"
                    border.color: "#2DD4BF"
                    border.width: 1
                    scale: cloudBtnMouse.pressed ? 0.95 : (cloudBtnMouse.containsMouse ? 1.03 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: cloudRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "☁️"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: appWindow.tr("action_download_links_count", "Download Links (%1)").replace("%1", cloudDownloadStickyBtn.count)
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: "#2DD4BF"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: cloudBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: appWindow.tr("tip_cloud_download_dialog", "Open dialog to download harvested links via Mega, Google Drive, Dropbox, or GoFile")
                        onClicked: mainCloudModal.isOpen = true
                    }
                }

                // ── Auto-Retry toggle ───────────────────────────────────────
                Rectangle {
                    Layout.preferredWidth: Math.max(118, autoRetryRow.implicitWidth + 24)
                    Layout.preferredHeight: 34
                    radius: 7
                    color: autoRetryMouse.containsMouse
                           ? (appBridge && appBridge.autoRetryAtEnd ? "#0A2118" : "#181B28")
                           : (appBridge && appBridge.autoRetryAtEnd ? "#071812" : "#111420")
                    border.color: (appBridge && appBridge.autoRetryAtEnd) ? "#10B981" : "#2E3A56"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    Row {
                        id: autoRetryRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: (appBridge && appBridge.autoRetryAtEnd) ? "✔" : "○"
                            font.pixelSize: 10
                            color: (appBridge && appBridge.autoRetryAtEnd) ? "#34D399" : "#64748B"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: appWindow.tr("action_auto_retry", "Auto-Retry")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: (appBridge && appBridge.autoRetryAtEnd) ? "#34D399" : "#64748B"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: autoRetryMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: (appBridge && appBridge.autoRetryAtEnd)
                                      ? appWindow.tr("tip_auto_retry_on", "Auto-Retry is ON (automatically retries failed files at end of queue, or immediately if clicked with failed files)")
                                      : appWindow.tr("tip_auto_retry_off", "Auto-Retry is OFF (click to enable auto-retry for failed downloads)")
                        onClicked: if (appBridge) appBridge.toggleAutoRetry()
                    }
                }

                // ── When Done (Post-Download Action) Selector ───────────────
                Rectangle {
                    id: postActionBtn
                    property string currentAction: appBridge ? appBridge.postDownloadAction : "none"

                    function getActionLabel(act) {
                        if (act === "close_app") return appWindow.tr("post_action_close", "Close App")
                        if (act === "sleep") return appWindow.tr("post_action_sleep_short", "Sleep")
                        if (act === "hibernate") return appWindow.tr("post_action_hibernate_short", "Hibernate (-F)")
                        if (act === "shutdown") return appWindow.tr("post_action_shutdown_short", "Shut Down (-F)")
                        if (act === "restart") return appWindow.tr("post_action_restart_short", "Restart (-F)")
                        return appWindow.tr("post_action_none_short", "Do Nothing")
                    }

                    function getOptionLabel(actId) {
                        if (actId === "close_app") return appWindow.tr("post_action_close", "Close App")
                        if (actId === "sleep") return appWindow.tr("post_action_sleep", "Sleep System")
                        if (actId === "hibernate") return appWindow.tr("post_action_hibernate", "Hibernate (-F Force)")
                        if (actId === "shutdown") return appWindow.tr("post_action_shutdown", "Shut Down (-F Force)")
                        if (actId === "restart") return appWindow.tr("post_action_restart", "Restart (-F Force)")
                        return appWindow.tr("post_action_none", "Do Nothing (Default)")
                    }

                    function getOptionDesc(actId) {
                        if (actId === "close_app") return appWindow.tr("post_action_close_desc", "Exit Pawchive Downloader")
                        if (actId === "sleep") return appWindow.tr("post_action_sleep_desc", "Suspend / sleep computer")
                        if (actId === "hibernate") return appWindow.tr("post_action_hibernate_desc", "Force save to disk and power down")
                        if (actId === "shutdown") return appWindow.tr("post_action_shutdown_desc", "Force close apps & turn off (10s buffer)")
                        if (actId === "restart") return appWindow.tr("post_action_restart_desc", "Force close apps & reboot computer")
                        return appWindow.tr("post_action_none_desc", "Keep app & system running")
                    }

                    function getActionIcon(act) {
                        if (act === "close_app") return "🚪"
                        if (act === "sleep") return "🌙"
                        if (act === "hibernate") return "💤"
                        if (act === "shutdown") return "🔌"
                        if (act === "restart") return "🔄"
                        return "⏸️"
                    }

                    function getActionColor(act) {
                        if (act === "close_app") return "#38BDF8"
                        if (act === "sleep") return "#A78BFA"
                        if (act === "hibernate") return "#818CF8"
                        if (act === "shutdown") return "#F43F5E"
                        if (act === "restart") return "#F59E0B"
                        return "#64748B"
                    }

                    function getActionBorderColor(act) {
                        if (act === "close_app") return "#0284C7"
                        if (act === "sleep") return "#7C3AED"
                        if (act === "hibernate") return "#4F46E5"
                        if (act === "shutdown") return "#E11D48"
                        if (act === "restart") return "#D97706"
                        return "#2E3A56"
                    }

                    function getActionBg(act, hovered) {
                        if (act === "close_app") return hovered ? "#0E2A3E" : "#0A1D2B"
                        if (act === "sleep") return hovered ? "#241E3A" : "#191528"
                        if (act === "hibernate") return hovered ? "#22203A" : "#171628"
                        if (act === "shutdown") return hovered ? "#361014" : "#260B0E"
                        if (act === "restart") return hovered ? "#35220A" : "#241707"
                        return hovered ? "#181B28" : "#111420"
                    }

                    Layout.preferredWidth: postActionRow.implicitWidth + 24
                    Layout.preferredHeight: 34
                    radius: 7
                    color: getActionBg(currentAction, postActionMouse.containsMouse)
                    border.color: getActionBorderColor(currentAction)
                    border.width: currentAction !== "none" ? 1.5 : 1

                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    Row {
                        id: postActionRow
                        anchors.centerIn: parent
                        spacing: 6

                        Text {
                            text: postActionBtn.getActionIcon(postActionBtn.currentAction)
                            font.pixelSize: 11
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: appWindow.tr("action_when_done", "When Done: %1").replace("%1", postActionBtn.getActionLabel(postActionBtn.currentAction))
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: postActionBtn.currentAction !== "none" ? Font.DemiBold : Font.Normal
                            color: postActionBtn.getActionColor(postActionBtn.currentAction)
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: postActionPopup.opened ? "▴" : "▾"
                            font.pixelSize: 10
                            color: postActionBtn.getActionColor(postActionBtn.currentAction)
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: postActionMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse && !postActionPopup.opened
                        ToolTip.delay: 300
                        ToolTip.text: appWindow.tr("tip_when_done", "Choose what action to execute when downloads finish (resets to 'Do Nothing' after execution)")
                        onClicked: {
                            if (postActionPopup.opened) {
                                postActionPopup.close()
                            } else {
                                postActionPopup.open()
                            }
                        }
                    }

                    // Dropdown Menu for selecting post-download action (opens downwards)
                    Popup {
                        id: postActionPopup
                        y: postActionBtn.height + 6
                        x: 0
                        width: 256
                        padding: 8
                        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent | Popup.CloseOnPressOutside

                        background: Rectangle {
                            color: "#111420"
                            border.color: "#2E3A56"
                            border.width: 1
                            radius: 8
                        }

                        contentItem: ColumnLayout {
                            spacing: 4

                            Text {
                                text: appWindow.tr("post_action_header", "ACTION WHEN COMPLETED")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.weight: Font.Bold
                                color: "#64748B"
                                Layout.leftMargin: 6
                                Layout.topMargin: 2
                                Layout.bottomMargin: 2
                            }

                            ListModel {
                                id: postActionOptionsModel
                                ListElement { actionId: "none"; actionIcon: "⏸️"; actionColor: "#94A3B8" }
                                ListElement { actionId: "close_app"; actionIcon: "🚪"; actionColor: "#38BDF8" }
                                ListElement { actionId: "sleep"; actionIcon: "🌙"; actionColor: "#A78BFA" }
                                ListElement { actionId: "hibernate"; actionIcon: "💤"; actionColor: "#818CF8" }
                                ListElement { actionId: "shutdown"; actionIcon: "🔌"; actionColor: "#F43F5E" }
                                ListElement { actionId: "restart"; actionIcon: "🔄"; actionColor: "#F59E0B" }
                            }

                            Repeater {
                                model: postActionOptionsModel
                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 34
                                    radius: 6
                                    property bool isCurrent: (appBridge ? appBridge.postDownloadAction : "none") === model.actionId
                                    color: optMouse.containsMouse ? "#1E2436" : (isCurrent ? "#161B2E" : "transparent")
                                    border.color: isCurrent ? model.actionColor : "transparent"
                                    border.width: 1

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 8
                                        anchors.rightMargin: 8
                                        spacing: 8

                                        Text {
                                            text: model.actionIcon
                                            font.pixelSize: 13
                                            Layout.alignment: Qt.AlignVCenter
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 1
                                            Text {
                                                text: postActionBtn.getOptionLabel(model.actionId)
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 11
                                                font.weight: isCurrent ? Font.DemiBold : Font.Normal
                                                color: isCurrent ? model.actionColor : "#E2E8F0"
                                            }
                                            Text {
                                                text: postActionBtn.getOptionDesc(model.actionId)
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 9
                                                color: "#64748B"
                                            }
                                        }

                                        Text {
                                            text: "✔"
                                            font.pixelSize: 11
                                            color: model.actionColor
                                            visible: isCurrent
                                            Layout.alignment: Qt.AlignVCenter
                                        }
                                    }

                                    MouseArea {
                                        id: optMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (appBridge) {
                                                appBridge.postDownloadAction = model.actionId
                                            }
                                            postActionPopup.close()
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                height: 1
                                color: "#1E293B"
                                Layout.topMargin: 2
                                Layout.bottomMargin: 2
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 6
                                Layout.rightMargin: 6
                                Layout.bottomMargin: 2
                                spacing: 4
                                Text {
                                    text: "ℹ️"
                                    font.pixelSize: 10
                                }
                                Text {
                                    text: appWindow.tr("post_action_footer", "Automatically resets to 'Do Nothing' after each task.")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 9
                                    color: "#64748B"
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // ── Restore Session ─────────────────────────────────────────
                Rectangle {
                    Layout.preferredWidth: Math.max(120, restoreRow.implicitWidth + 24)
                    Layout.preferredHeight: 34
                    radius: 7
                    visible: appBridge ? appBridge.hasSavedSession : false
                    color: restoreBtnMouse.containsMouse ? "#0D2820" : "#071A14"
                    border.color: "#10B981"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: restoreRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🔄"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: appWindow.tr("action_restore_session", "Restore Session")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#34D399"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: restoreBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: appWindow.tr("tip_restore_session", "Resume the previously saved incomplete download session")
                        onClicked: if (appBridge) appBridge.restoreDownload()
                    }
                }

                // ── Discard Session ─────────────────────────────────────────
                Rectangle {
                    Layout.preferredWidth: Math.max(88, discardRow.implicitWidth + 24)
                    Layout.preferredHeight: 34
                    radius: 7
                    visible: appBridge ? appBridge.hasSavedSession : false
                    color: discardBtnMouse.containsMouse ? "#2A0D0D" : "#1C0808"
                    border.color: "#7F1D1D"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: discardRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🗑"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: appWindow.tr("action_discard", "Discard")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#FCA5A5"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: discardBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: appWindow.tr("tip_discard_session", "Clear the saved session and queue (cannot be undone)")
                        onClicked: if (appBridge) appBridge.discardSession()
                    }
                }
            }
        }

        // 3. Main Split Content Area
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true


            SplitView {
                anchors.fill: parent
                orientation: Qt.Horizontal

                // Custom drag handle — visible, glows on hover
                handle: Rectangle {
                    id: splitHandle
                    implicitWidth: 6
                    property bool isHovered: SplitHandle.hovered || SplitHandle.pressed
                    color: isHovered ? "#38BDF8" : "#1E2330"

                    Behavior on color { ColorAnimation { duration: 150 } }

                    property bool wasPressed: false
                    Connections {
                        target: SplitHandle
                        function onPressedChanged() {
                            if (!SplitHandle.pressed && splitHandle.wasPressed) {
                                if (consoleContainer.visible && consoleContainer.width >= 320 && appBridge) {
                                    appBridge.consoleWidth = Math.round(consoleContainer.width)
                                }
                            }
                            splitHandle.wasPressed = SplitHandle.pressed
                        }
                    }

                    // Dotted grip indicator in the middle
                    Column {
                        anchors.centerIn: parent
                        spacing: 3
                        Repeater {
                            model: 5
                            delegate: Rectangle {
                                width: 2
                                height: 2
                                radius: 1
                                color: splitHandle.isHovered ? "#0F172A" : "#374151"
                            }
                        }
                    }
                }

                // Left Panel: Active Tab View
                Rectangle {
                    SplitView.fillWidth: true
                    SplitView.minimumWidth: 340
                    color: "#0F1117"

                    StackLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        currentIndex: appWindow.currentTab

                        // Tab 0: Downloader View with Newtonian slide & fade transition
                        Item {
                            opacity: appWindow.currentTab === 0 ? 1.0 : 0.0
                            y: appWindow.currentTab === 0 ? 0 : 10
                            scale: appWindow.currentTab === 0 ? 1.0 : 0.985
                            transformOrigin: Item.Center
                            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                            Behavior on y { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
                            Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }

                            DownloaderView { anchors.fill: parent; bridge: appBridge }
                        }

                        // Tab 1: Queue View with Newtonian slide & fade transition
                        Item {
                            opacity: appWindow.currentTab === 1 ? 1.0 : 0.0
                            y: appWindow.currentTab === 1 ? 0 : 10
                            scale: appWindow.currentTab === 1 ? 1.0 : 0.985
                            transformOrigin: Item.Center
                            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                            Behavior on y { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
                            Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }

                            QueueView { anchors.fill: parent; bridge: appBridge }
                        }

                        // Tab 2: Known Manager View with Newtonian slide & fade transition
                        Item {
                            opacity: appWindow.currentTab === 2 ? 1.0 : 0.0
                            y: appWindow.currentTab === 2 ? 0 : 10
                            scale: appWindow.currentTab === 2 ? 1.0 : 0.985
                            transformOrigin: Item.Center
                            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                            Behavior on y { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
                            Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }

                            KnownManagerView { anchors.fill: parent; bridge: appBridge }
                        }

                        // Tab 3: History View with Newtonian slide & fade transition
                        Item {
                            opacity: appWindow.currentTab === 3 ? 1.0 : 0.0
                            y: appWindow.currentTab === 3 ? 0 : 10
                            scale: appWindow.currentTab === 3 ? 1.0 : 0.985
                            transformOrigin: Item.Center
                            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                            Behavior on y { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
                            Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }

                            HistoryView { anchors.fill: parent; bridge: appBridge }
                        }

                        // Tab 4: Settings View with Newtonian slide & fade transition
                        Item {
                            opacity: appWindow.currentTab === 4 ? 1.0 : 0.0
                            y: appWindow.currentTab === 4 ? 0 : 10
                            scale: appWindow.currentTab === 4 ? 1.0 : 0.985
                            transformOrigin: Item.Center
                            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                            Behavior on y { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
                            Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }

                            SettingsView { anchors.fill: parent; bridge: appBridge }
                        }
                    }
                }

                // Right Panel: Live Console Log View & Active Downloads Panel
                Rectangle {
                    id: consoleContainer
                    SplitView.preferredWidth: appBridge ? appBridge.consoleWidth : 680
                    SplitView.minimumWidth: 320
                    visible: appWindow.showConsole
                    color: "#0B0D12"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        ActiveDownloadsPanel {
                            id: activeDownloadsPanel
                            Layout.fillWidth: true
                            bridge: appBridge
                            visible: implicitHeight > 0.5 || (appBridge && appBridge.activeQueueModel && appBridge.activeQueueModel.count > 0)
                        }

                        ConsoleLogView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            logModel: appBridge ? appBridge.logModel : null
                            onExportLogsRequested: if (appBridge) appBridge.exportLogs()
                            onClearLogsRequested: if (appBridge) appBridge.clearLogs()
                            onExportLinksRequested: if (appBridge) appBridge.exportAllLinks()
                            onDownloadLinksRequested: mainCloudModal.isOpen = true
                        }
                    }
                }
            }
        }

        // 4. Bottom Status & Progress Footer
        Rectangle {
            Layout.fillWidth: true
            height: 44
            color: "#0B0D12"
            border.color: "#1E2330"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 12

                // Error Indicator if any
                Rectangle {
                    width: 20; height: 20; radius: 10
                    color: "#EF4444"
                    visible: appBridge ? appBridge.hasError : false
                    Text { anchors.centerIn: parent; text: "!"; color: "#FFFFFF"; font.bold: true }
                }

                // Overall Progress Bar (Full-Width with Inline Telemetry Badges)
                ProgressBarFancy {
                    Layout.fillWidth: true
                    progressPercent: appBridge ? appBridge.overallProgress : 0
                    statusText: appBridge ? appBridge.statusText : "Progress: Idle"
                    filesText: appBridge ? appBridge.filesCountText : ""
                    speedText: appBridge ? appBridge.currentSpeed : "0 KB/s"
                    etaText: appBridge ? appBridge.etaText : "--"
                    elapsedText: appBridge ? appBridge.elapsedTimeText : "0s"
                    savedText: appBridge ? appBridge.savedBytesText : "0 MB"
                    active: appBridge ? appBridge.isDownloading : false
                }

                // Live Adaptive Health & Scaling Pill (Feature 5) with Spring Entrance
                Rectangle {
                    id: adaptivePill
                    implicitHeight: 24
                    implicitWidth: adaptiveRow.implicitWidth + 24
                    radius: 6
                    visible: opacity > 0
                    opacity: (appBridge && appBridge.isDownloading && appBridge.adaptiveThreading && appBridge.adaptiveStatusText.length > 0) ? 1.0 : 0.0
                    scale: opacity > 0 ? 1.0 : 0.6
                    transformOrigin: Item.Center

                    Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: 240; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

                    color: {
                        if (!appBridge) return "#161E2E"
                        if (appBridge.adaptiveState === "cooldown") return "#2E1418"
                        if (appBridge.adaptiveState === "scaling") return "#2E2414"
                        return "#122820"
                    }
                    border.color: {
                        if (!appBridge) return "#1E293B"
                        if (appBridge.adaptiveState === "cooldown") return "#EF4444"
                        if (appBridge.adaptiveState === "scaling") return "#FBBF24"
                        return "#10B981"
                    }
                    border.width: 1

                    Behavior on color { ColorAnimation { duration: 150 } }
                    Behavior on border.color { ColorAnimation { duration: 150 } }

                    Row {
                        id: adaptiveRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: {
                                if (!appBridge) return "⚡"
                                if (appBridge.adaptiveState === "cooldown") return "⏳"
                                if (appBridge.adaptiveState === "scaling") return "⚡"
                                return "✔"
                            }
                            font.pixelSize: 10
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            id: adaptivePillText
                            text: appBridge ? appBridge.adaptiveStatusText : ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Medium
                            anchors.verticalCenter: parent.verticalCenter
                            color: {
                                if (!appBridge) return "#38BDF8"
                                if (appBridge.adaptiveState === "cooldown") return "#FCA5A5"
                                if (appBridge.adaptiveState === "scaling") return "#FCD34D"
                                return "#6EE7B7"
                            }
                        }
                    }
                }

                // Quick session state badge
                Rectangle {
                    height: 22
                    width: Math.max(90, sessStateText.implicitWidth + 12)
                    radius: 4
                    color: "#181B22"
                    border.color: "#282E3D"
                    border.width: 1
                    visible: appBridge ? appBridge.hasSavedSession : false

                    Row {
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "📁"; font.pixelSize: 10 }
                        Text {
                            id: sessStateText
                            text: appWindow.tr("badge_session_active", "Session Active")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#FBBF24"
                        }
                    }
                }
            }
        }
    }

    // Global Retry Modal — used by the sticky action bar
    RetryModal {
        id: mainRetryModal
        bridge: appBridge
    }

    // Global Cloud Download Modal — used by the sticky action bar and console log
    CloudDownloadModal {
        id: mainCloudModal
        bridge: appBridge
    }

    // Post-download action countdown modal — 15s to cancel shutdown/restart/hibernate/etc.
    CountdownModal {
        id: countdownModal
        bridge: appBridge
    }

    // Wire: when bridge emits postActionCountdownStarted, open the modal with the action label
    Connections {
        target: appBridge
        function onPostActionCountdownStarted(actionLabel) {
            countdownModal.actionLabel = actionLabel
            countdownModal.isOpen = true
        }
    }
}
