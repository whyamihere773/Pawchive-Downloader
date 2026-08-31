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
    title: "Pawchive Downloader v1.0.1"
    color: "#0F1117"

    // Stop active downloads and persist session gracefully when user closes the app
    onClosing: {
        if (appBridge) {
            appBridge.onAppClosing()
        }
    }

    property bool showConsole: true
    property int currentTab: 0 // 0: Downloader, 1: Queue, 2: Known, 3: History, 4: Settings

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
                    width: 130
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
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "📥"; font.pixelSize: 12 }
                        Text {
                            text: "Downloader"
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
                        ToolTip.text: "Downloader configuration and execution"
                        onClicked: appWindow.currentTab = 0
                    }
                }

                // Tab: Queue
                Rectangle {
                    width: 110
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
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "📋"; font.pixelSize: 12 }
                        Text {
                            text: "Queue"
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
                        ToolTip.text: "Task queue and file download monitoring"
                        onClicked: appWindow.currentTab = 1
                    }
                }

                // Tab: Known Characters
                Rectangle {
                    width: 140
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
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🏷️"; font.pixelSize: 12 }
                        Text {
                            text: "Known Series"
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
                        ToolTip.text: "Known character and series directory rules (Known.txt)"
                        onClicked: appWindow.currentTab = 2
                    }
                }

                // Tab: History
                Rectangle {
                    width: 100
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
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "📜"; font.pixelSize: 12 }
                        Text {
                            text: "History"
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
                        ToolTip.text: "Completed downloads and past batch sessions"
                        onClicked: appWindow.currentTab = 3
                    }
                }

                // Tab: Settings
                Rectangle {
                    width: 100
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
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "⚙️"; font.pixelSize: 12 }
                        Text {
                            text: "Settings"
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
                        ToolTip.text: "Global application and network configuration"
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
                        text: "v1.0.1"
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
                        ToolTip.text: appWindow.showConsole ? "Hide Progress Log console" : "Show Progress Log console"
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
                    text: "Creator:"
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

                    Layout.preferredWidth: isLinksMode ? 162 : 148
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
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: mainStartBtn.isDownloading ? "⏳" : (mainStartBtn.isLinksMode ? "🔗" : "⚡")
                            font.pixelSize: 13
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: mainStartBtn.isDownloading ? "Downloading…"
                                : (mainStartBtn.isLinksMode ? "Extract Links" : "Start Download")
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
                            ? "Scan posts for external cloud links (Mega.nz, Drive, Dropbox, etc.) — no files downloaded"
                            : "Fetch posts from the URL and start downloading immediately"
                        onClicked: if (appBridge) appBridge.startDownload()
                    }
                }

                // ── Add to Queue ────────────────────────────────────────────
                Rectangle {
                    Layout.preferredWidth: 116
                    Layout.preferredHeight: 34
                    radius: 7
                    color: queueBtnMouse.containsMouse ? "#1A1F2E" : "#131722"
                    border.color: "#2E3A56"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "➕"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Add to Queue"
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
                        ToolTip.text: "Add all matched files to the queue without auto-starting download"
                        onClicked: if (appBridge) appBridge.addToQueue()
                    }
                }

                // ── Thin separator ──────────────────────────────────────────
                Rectangle { width: 1; height: 28; color: "#1E293B"; Layout.alignment: Qt.AlignVCenter }

                // ── Pause / Resume (shown only while downloading) ───────────
                Rectangle {
                    Layout.preferredWidth: 100
                    Layout.preferredHeight: 34
                    radius: 7
                    visible: appBridge ? appBridge.isDownloading : false
                    color: pauseBtnMouse.containsMouse ? "#1C1A08" : "#141208"
                    border.color: "#FBBF24"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: (appBridge && appBridge.statusText.indexOf("Paused") >= 0) ? "▶" : "⏸"
                            font.pixelSize: 12
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: (appBridge && appBridge.statusText.indexOf("Paused") >= 0) ? "Resume" : "Pause"
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
                                      ? "Resume paused download" : "Pause the active download (can be resumed)"
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
                    Layout.preferredWidth: 86
                    Layout.preferredHeight: 34
                    radius: 7
                    visible: appBridge ? appBridge.isDownloading : false
                    color: cancelBtnMouse.containsMouse ? "#2A0D0D" : "#1C0808"
                    border.color: "#EF4444"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "⏹"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Cancel"
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
                        ToolTip.text: "Cancel the active download (session preserved for restore)"
                        onClicked: if (appBridge) appBridge.cancelDownload()
                    }
                }

                // ── Thin separator ──────────────────────────────────────────
                Rectangle { width: 1; height: 28; color: "#1E293B"; Layout.alignment: Qt.AlignVCenter }

                // ── Retry Failed ────────────────────────────────────────────
                Rectangle {
                    id: retryFailedBtn
                    property int failedCount: (appBridge && appBridge.queueModel) ? appBridge.queueModel.failedCount : 0
                    Layout.preferredWidth: failedCount > 0 ? (retryFailedRow.implicitWidth + 20) : 106
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
                                  ? "Retry Failed (" + retryFailedBtn.failedCount + ")"
                                  : "Retry Failed"
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
                        ToolTip.text: "Open dialog to inspect and retry failed downloads"
                        onClicked: mainRetryModal.isOpen = true
                    }
                }

                // ── Download Cloud Links button (visible when harvested links exist) ──
                Rectangle {
                    id: cloudDownloadStickyBtn
                    property int count: appBridge ? appBridge.harvestedLinksCount : 0
                    visible: count > 0
                    Layout.preferredWidth: 165
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
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "☁️"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Download Links (" + cloudDownloadStickyBtn.count + ")"
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
                        ToolTip.text: "Open dialog to download harvested links via Mega, Google Drive, Dropbox, or GoFile"
                        onClicked: mainCloudModal.isOpen = true
                    }
                }

                // ── Auto-Retry toggle ───────────────────────────────────────
                Rectangle {
                    Layout.preferredWidth: 118
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
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: (appBridge && appBridge.autoRetryAtEnd) ? "✔" : "○"
                            font.pixelSize: 10
                            color: (appBridge && appBridge.autoRetryAtEnd) ? "#34D399" : "#64748B"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: "Auto-Retry"
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
                        ToolTip.delay: 400
                        ToolTip.text: "Automatically retry all failed downloads once the queue finishes"
                        onClicked: if (appBridge) appBridge.autoRetryAtEnd = !appBridge.autoRetryAtEnd
                    }
                }

                Item { Layout.fillWidth: true }

                // ── Restore Session ─────────────────────────────────────────
                Rectangle {
                    Layout.preferredWidth: 120
                    Layout.preferredHeight: 34
                    radius: 7
                    visible: appBridge ? appBridge.hasSavedSession : false
                    color: restoreBtnMouse.containsMouse ? "#0D2820" : "#071A14"
                    border.color: "#10B981"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🔄"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Restore Session"
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
                        ToolTip.text: "Resume the previously saved incomplete download session"
                        onClicked: if (appBridge) appBridge.restoreDownload()
                    }
                }

                // ── Discard Session ─────────────────────────────────────────
                Rectangle {
                    Layout.preferredWidth: 88
                    Layout.preferredHeight: 34
                    radius: 7
                    visible: appBridge ? appBridge.hasSavedSession : false
                    color: discardBtnMouse.containsMouse ? "#2A0D0D" : "#1C0808"
                    border.color: "#7F1D1D"
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🗑"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Discard"
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
                        ToolTip.text: "Clear the saved session and queue (cannot be undone)"
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

                // Right Panel: Live Console Log View
                Rectangle {
                    id: consoleContainer
                    SplitView.preferredWidth: appBridge ? appBridge.consoleWidth : 680
                    SplitView.minimumWidth: 320
                    visible: appWindow.showConsole
                    color: "#0B0D12"

                    ConsoleLogView {
                        anchors.fill: parent
                        anchors.margins: 8
                        logModel: appBridge ? appBridge.logModel : null
                        onExportLogsRequested: if (appBridge) appBridge.exportLogs()
                        onClearLogsRequested: if (appBridge) appBridge.clearLogs()
                        onExportLinksRequested: if (appBridge) appBridge.exportAllLinks()
                        onDownloadLinksRequested: mainCloudModal.isOpen = true
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
                            text: "Session Active"
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
}
