import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Sticky Download Action Bar (Start, Select Posts, Queue, Pause/Cancel, Retry, Cloud, Auto-Retry, When Done, Session).
Item {
    id: actionBar
    required property var window
    Layout.fillWidth: true
    Layout.preferredHeight: 52 * actionBar.window.chromeProgress
    visible: actionBar.window.chromeProgress > 0
    opacity: actionBar.window.chromeOpacity
    clip: actionBar.window.chromeMoving

    Rectangle {
        width: parent.width
        height: 52
        anchors.bottom: parent.bottom
        transform: Translate { y: -16 * actionBar.window.chromeSlide }
        color: "#0C0F16"
        border.color: "#1A2035"
        border.width: 1
        clip: true

        // Subtle gradient top accent line
        Rectangle {
            width: parent.width
            height: 1
            anchors.top: parent.top
            z: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.3; color: "#38BDF8" }
                GradientStop { position: 0.7; color: "#A78BFA" }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        Flickable {
            id: actionBarFlickable
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            contentWidth: actionBarRow.implicitWidth
            contentHeight: height
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            WheelHandler {
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: function(event) {
                    var delta = event.angleDelta.y || event.angleDelta.x
                    actionBarFlickable.flick(delta * 10, 0)
                }
            }

        RowLayout {
            id: actionBarRow
            height: parent.height
            spacing: 6

            // ── PRIMARY: Start Download / Extract Links / Queue at End / Downloading indicator ────
            Rectangle {
                id: mainStartBtn
                property bool isLinksMode: appBridge ? appBridge.filterType === "links" : false
                property bool isFavoritesMode: (appBridge && appBridge.favoriteMode && (!appBridge.currentUrl || appBridge.currentUrl.trim().length === 0))
                property bool isDownloading: appBridge ? appBridge.isDownloading : false
                property bool hasPendingQueue: (appBridge && appBridge.queueModel) ? (appBridge.queueModel.pendingCount > 0 || appBridge.queueModel.count > 0) : false
                property bool hasUrlInput: (appBridge && appBridge.currentUrl && appBridge.currentUrl.trim().length > 0)
                property bool isQueueAtEnd: mainStartBtn.isDownloading && mainStartBtn.hasUrlInput
                property bool isTelegramBlocked: (appBridge ? appBridge.isTelegramUrl : false) && !hasPendingQueue

                Layout.preferredWidth: Math.max(isQueueAtEnd ? 160 : (isFavoritesMode ? 175 : (isLinksMode ? 162 : 148)), startBtnRow.implicitWidth + 28)
                Layout.preferredHeight: 34
                radius: 7

                color: mainStartBtn.isTelegramBlocked
                    ? "#10131B"
                    : (mainStartBtn.isQueueAtEnd
                        ? (startBtnMouse.containsMouse ? "#1A2F45" : "#0E2235")
                        : (mainStartBtn.isDownloading
                            ? "#0F2A1A"
                            : (startBtnMouse.containsMouse
                                ? (mainStartBtn.isFavoritesMode ? "#2E2008" : (mainStartBtn.isLinksMode ? "#0D3330" : "#1a3a52"))
                                : (mainStartBtn.isFavoritesMode ? "#241905" : (mainStartBtn.isLinksMode ? "#0A2825" : "#0D2137")))))
                border.color: mainStartBtn.isTelegramBlocked
                    ? "#334155"
                    : (mainStartBtn.isQueueAtEnd
                        ? "#38BDF8"
                        : (mainStartBtn.isDownloading
                            ? "#10B981"
                            : (mainStartBtn.isFavoritesMode ? "#F59E0B" : (mainStartBtn.isLinksMode ? "#2DD4BF" : "#38BDF8"))))
                border.width: 1
                opacity: mainStartBtn.isTelegramBlocked ? 0.45 : (mainStartBtn.isDownloading && !mainStartBtn.hasUrlInput ? 0.7 : 1.0)

                scale: (!mainStartBtn.isTelegramBlocked && (!mainStartBtn.isDownloading || mainStartBtn.hasUrlInput) && startBtnMouse.pressed) ? 0.94 : ((!mainStartBtn.isTelegramBlocked && (!mainStartBtn.isDownloading || mainStartBtn.hasUrlInput) && startBtnMouse.containsMouse) ? 1.03 : 1.0)
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
                        text: mainStartBtn.isTelegramBlocked ? "🚫" : (mainStartBtn.isQueueAtEnd ? "➕" : (mainStartBtn.isDownloading ? "⏳" : (mainStartBtn.isFavoritesMode ? "⭐" : (mainStartBtn.isLinksMode ? "🔗" : "⚡"))))
                        font.pixelSize: 13
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: mainStartBtn.isTelegramBlocked ? actionBar.window.tr("action_select_required", "Use 'Select Posts'")
                            : (mainStartBtn.isQueueAtEnd ? actionBar.window.tr("action_queue_at_end", "Queue at End")
                            : (mainStartBtn.isDownloading ? actionBar.window.tr("action_downloading", "Downloading…")
                            : (mainStartBtn.isFavoritesMode ? actionBar.window.tr("action_download_favorites", "Download Favorites")
                            : (mainStartBtn.isLinksMode ? actionBar.window.tr("action_extract_links", "Extract Links") : actionBar.window.tr("action_start_download", "Start Download")))))
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: mainStartBtn.isTelegramBlocked ? "#64748B" : (mainStartBtn.isQueueAtEnd ? "#38BDF8" : (mainStartBtn.isDownloading ? "#34D399" : (mainStartBtn.isFavoritesMode ? "#FBBF24" : (mainStartBtn.isLinksMode ? "#2DD4BF" : "#38BDF8"))))
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: startBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: (mainStartBtn.isTelegramBlocked || (mainStartBtn.isDownloading && !mainStartBtn.hasUrlInput)) ? Qt.ArrowCursor : Qt.PointingHandCursor
                    enabled: (!mainStartBtn.isDownloading || mainStartBtn.hasUrlInput) && !mainStartBtn.isTelegramBlocked
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: mainStartBtn.isTelegramBlocked
                        ? actionBar.window.tr("tip_tg_disabled", "Direct download is disabled for Telegram links. Please click 'Select Posts…' to configure download scope and media filters.")
                        : (mainStartBtn.isQueueAtEnd
                            ? actionBar.window.tr("tip_queue_at_end", "Add this URL to the end of the active download queue with current filter settings")
                            : (mainStartBtn.isDownloading
                                ? actionBar.window.tr("tip_downloading_status", "Downloads are actively in progress. Enter a URL above to queue it at the end.")
                                : (mainStartBtn.isFavoritesMode
                                    ? actionBar.window.tr("tip_download_favorites", "Fetch and download all favorited posts from your connected account")
                                    : (mainStartBtn.isLinksMode
                                        ? actionBar.window.tr("tip_extract_links", "Scan posts for external cloud links (Mega.nz, Drive, Dropbox, etc.) — no files downloaded")
                                        : actionBar.window.tr("tip_start_download", "Fetch posts from the URL and start downloading immediately")))))
                    onClicked: if (appBridge) appBridge.startDownload()
                }
            }

            // ── Select Posts (Interactive Thumbnail Browser) ───────────
            Rectangle {
                id: selectPostsBtn
                property bool isLoading: appBridge ? appBridge.postSelectionLoading : false
                property bool isTelegram: appBridge ? appBridge.isTelegramUrl : false
                Layout.preferredWidth: Math.max(124, selectPostsRow.implicitWidth + 24)
                Layout.preferredHeight: 34
                radius: 7
                color: selectPostsBtn.isLoading
                    ? "#151F30"
                    : (selectPostsMouse.containsMouse ? "#1A263C" : "#111827")
                border.color: selectPostsBtn.isLoading ? "#38BDF8" : (isTelegram ? "#38BDF8" : (selectPostsMouse.containsMouse ? "#38BDF8" : "#2E3D59"))
                border.width: isTelegram ? 1.5 : 1

                // Newtonian fluid weight and hydraulic spring
                scale: selectPostsMouse.pressed ? 0.93 : (selectPostsMouse.containsMouse ? 1.03 : 1.0)
                transformOrigin: Item.Center
                Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.32; mass: 1.8 } }
                Behavior on color { ColorAnimation { duration: 140 } }
                Behavior on border.color { ColorAnimation { duration: 140 } }

                // Fluid surface tension aura wave for Telegram link
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: -3
                    radius: 10
                    color: "transparent"
                    border.color: "#38BDF8"
                    border.width: 1.5
                    visible: selectPostsBtn.isTelegram && !selectPostsBtn.isLoading
                    opacity: 0.2

                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: selectPostsBtn.isTelegram && !selectPostsBtn.isLoading
                        NumberAnimation { to: 0.85; duration: 1400; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.15; duration: 1400; easing.type: Easing.InOutSine }
                    }
                    SequentialAnimation on scale {
                        loops: Animation.Infinite
                        running: selectPostsBtn.isTelegram && !selectPostsBtn.isLoading
                        NumberAnimation { to: 1.03; duration: 1400; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.99; duration: 1400; easing.type: Easing.InOutSine }
                    }
                }

                Row {
                    id: selectPostsRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        text: selectPostsBtn.isLoading ? "⏳" : "🖼️"
                        font.pixelSize: 12
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: selectPostsBtn.isLoading
                            ? actionBar.window.tr("action_fetching_posts", "Fetching…")
                            : (mainStartBtn.isFavoritesMode
                                ? actionBar.window.tr("action_browse_favorites", "Browse Favorites…")
                                : ((!!appBridge && appBridge.hasCachedSelectionForCurrentUrl)
                                    ? actionBar.window.tr("action_select_posts_saved", "Select Posts (Saved)…")
                                    : actionBar.window.tr("action_select_posts", "Select Posts…")))
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: selectPostsBtn.isLoading ? "#38BDF8" : (mainStartBtn.isFavoritesMode ? "#FBBF24" : "#E2E8F0")
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: selectPostsMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: selectPostsBtn.isLoading ? Qt.ArrowCursor : Qt.PointingHandCursor
                    enabled: !selectPostsBtn.isLoading
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: (!!appBridge && appBridge.hasCachedSelectionForCurrentUrl && !mainStartBtn.isFavoritesMode)
                        ? actionBar.window.tr("tip_select_posts_saved", "Reopen cached posts and your saved selections instantly without re-fetching")
                        : actionBar.window.tr("tip_select_posts", "Fetch and visually select specific posts and thumbnails before downloading")
                    onClicked: {
                        if (!appBridge) return
                        if (appBridge.isTelegramUrl) {
                            if (!appBridge.telegramSafetyAcknowledged || !appBridge.telegramLiabilityAcknowledged) {
                                actionBar.window.openTelegramWarningModal()
                                return
                            }
                        }
                        appBridge.fetchPostsForSelection()
                    }
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
                        text: actionBar.window.tr("action_add_to_queue", "Add to Queue")
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
                    ToolTip.text: actionBar.window.tr("tip_add_to_queue", "Add all matched files to the queue without auto-starting download")
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
                        text: (appBridge && (appBridge.isPaused || appBridge.statusText.indexOf("Paused") >= 0)) ? "▶" : "⏸"
                        font.pixelSize: 12
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: (appBridge && (appBridge.isPaused || appBridge.statusText.indexOf("Paused") >= 0)) ? actionBar.window.tr("action_resume", "Resume") : actionBar.window.tr("action_pause", "Pause")
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
                    ToolTip.text: (appBridge && (appBridge.isPaused || appBridge.statusText.indexOf("Paused") >= 0))
                                  ? actionBar.window.tr("tip_resume_download", "Resume paused download") : actionBar.window.tr("tip_pause_download", "Pause the active download (can be resumed)")
                    onClicked: {
                        if (!appBridge) return
                        if (appBridge.isPaused || appBridge.statusText.indexOf("Paused") >= 0)
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
                        text: actionBar.window.tr("action_cancel", "Cancel")
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
                    ToolTip.text: actionBar.window.tr("tip_cancel_download", "Cancel the active download (session preserved for restore)")
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
                              ? actionBar.window.tr("action_retry_failed_count", "Retry Failed (%1)").replace("%1", retryFailedBtn.failedCount)
                              : actionBar.window.tr("action_retry_failed", "Retry Failed")
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
                    ToolTip.text: actionBar.window.tr("tip_retry_failed_dialog", "Open dialog to inspect and retry failed downloads")
                    onClicked: actionBar.window.openRetryModal()
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
                        text: actionBar.window.tr("action_download_links_count", "Download Links (%1)").replace("%1", cloudDownloadStickyBtn.count)
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
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
                    ToolTip.text: actionBar.window.tr("tip_cloud_download_dialog", "Open dialog to download harvested links via Mega, Google Drive, Dropbox, or GoFile")
                    onClicked: actionBar.window.openCloudModal()
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
                        text: actionBar.window.tr("action_auto_retry", "Auto-Retry")
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
                                  ? actionBar.window.tr("tip_auto_retry_on", "Auto-Retry is ON (automatically retries failed files at end of queue, or immediately if clicked with failed files)")
                                  : actionBar.window.tr("tip_auto_retry_off", "Auto-Retry is OFF (click to enable auto-retry for failed downloads)")
                    onClicked: if (appBridge) appBridge.toggleAutoRetry()
                }
            }


            PostDownloadActionButton {
                window: actionBar.window
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
                        text: actionBar.window.tr("action_restore_session", "Restore Session")
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
                    ToolTip.text: actionBar.window.tr("tip_restore_session", "Resume the previously saved incomplete download session")
                    onClicked: {
                        if (appBridge && appBridge.hasRecoverySession) {
                            actionBar.window.openSessionRecoveryModal()
                        } else if (appBridge) {
                            appBridge.restoreDownload()
                        }
                    }
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
                        text: actionBar.window.tr("action_discard", "Discard")
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
                    ToolTip.text: actionBar.window.tr("tip_discard_session", "Clear the saved session and queue (cannot be undone)")
                    onClicked: if (appBridge) appBridge.discardSession()
                }
            }
        }
        } // end Flickable (actionBarFlickable)
    }
}
