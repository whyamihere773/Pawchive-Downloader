import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Effects
import "components"
import "views"
import "shell"

ApplicationWindow {
    id: appWindow
    width: 1200
    height: 780
    minimumWidth: 900
    minimumHeight: 600
    visible: true
    title: (appBridge && (appBridge.privacyModeActive || appBridge.safeModeActive))
           ? "Downloads"
           : ("Pawchive Downloader" + ((typeof updaterBridge !== "undefined" && updaterBridge && updaterBridge.currentVersion) ? (" v" + updaterBridge.currentVersion) : ""))
    color: "#0F1117"

    // Stop active downloads and persist session gracefully when user closes the app
    onClosing: {
        if (appBridge) {
            appBridge.onAppClosing()
        }
    }

    Component.onCompleted: {
        if (appBridge) {
            appBridge.checkRecoverySession()
        }
    }

    readonly property var ctxBrowserBridge: (typeof browserBridge !== "undefined" && browserBridge) ? browserBridge : null
    property bool showConsole: true
    property int currentTab: 0 // 0: Downloader, 1: Browser, 2: Queue, 3: Watchlist, 4: Decompressor, 5: Link Vault, 6: Scheduler, 7: Gallery, 8: Known, 9: Archive, 10: History, 11: Statistics, 12: Settings
    // The Gallery and Browser have no use for the download controls, so they step aside to give them room
    readonly property bool hideDownloadChrome: currentTab === 1 || currentTab === 7

    // Safe Mode Tab Vaulting & User-Configurable Tab Visibility
    readonly property bool tabsVaulted: appBridge ? appBridge.safeModeActive : false
    readonly property var disabledTabsList: appBridge ? appBridge.disabledTabs : []
    readonly property bool tabPermitted: !tabsVaulted

    function isTabDisabled(tabKey) {
        if (!disabledTabsList) return false
        return disabledTabsList.indexOf(tabKey) >= 0
    }

    function tabKeyForIndex(idx) {
        if (idx === 1) return "browser"
        if (idx === 2) return "queue"
        if (idx === 3) return "watchlist"
        if (idx === 4) return "decompressor"
        if (idx === 5) return "link_vault"
        if (idx === 6) return "scheduler"
        if (idx === 7) return "gallery"
        if (idx === 8) return "known"
        if (idx === 9) return "archive"
        if (idx === 10) return "history"
        if (idx === 11) return "statistics"
        return ""
    }

    onDisabledTabsListChanged: {
        var curKey = tabKeyForIndex(currentTab)
        if (curKey !== "" && isTabDisabled(curKey)) {
            currentTab = 0
        }
    }

    onTabsVaultedChanged: {
        if (tabsVaulted && currentTab !== 0 && currentTab !== 12) {
            currentTab = 0
        }
    }

    // Inactivity / Auto-lock Idle Timer (5 minutes by default, customizable up to 30 min)
    Timer {
        id: privacyIdleTimer
        interval: 1000
        repeat: true
        running: appBridge && appBridge.privacyIdleMinutes > 0 && !appBridge.privacyModeActive && !appBridge.safeModeActive
        property int elapsedSeconds: 0

        onTriggered: {
            if (!appBridge || appBridge.privacyIdleMinutes <= 0) return
            elapsedSeconds += 1
            if (elapsedSeconds >= appBridge.privacyIdleMinutes * 60) {
                elapsedSeconds = 0
                appBridge.privacyModeActive = true
            }
        }

        function resetTimer() {
            elapsedSeconds = 0
        }
    }

    HoverHandler {
        acceptedDevices: PointerDevice.AllDevices
        onPointChanged: privacyIdleTimer.resetTimer()
    }
    WheelHandler {
        acceptedDevices: PointerDevice.AllDevices
        onWheel: privacyIdleTimer.resetTimer()
    }

    // They step aside with the same motion as the Progress Log: opening grows the height (320 ms),
    // fades in (260 ms) and slides into place (380 ms, small overshoot), all starting together.
    // Closing is that motion backwards over 380 ms: the slide starts first, the height 60 ms later
    // and the fade 120 ms later, so all three end together.
    property real chromeProgress: 1     // 0 = hidden, 1 = shown (height)
    property real chromeOpacity: 1
    property real chromeSlide: 0        // 0 = in place, 1 = slid out
    readonly property bool chromeMoving: chromeShowAnim.running || chromeHideAnim.running

    ParallelAnimation {
        id: chromeShowAnim
        NumberAnimation { target: appWindow; property: "chromeProgress"; to: 1; duration: 320; easing.type: Easing.OutCubic }
        NumberAnimation { target: appWindow; property: "chromeOpacity"; to: 1; duration: 260; easing.type: Easing.OutCubic }
        NumberAnimation { target: appWindow; property: "chromeSlide"; to: 0; duration: 380; easing.type: Easing.OutBack; easing.overshoot: 1.25 }
    }
    ParallelAnimation {
        id: chromeHideAnim
        SequentialAnimation {
            PauseAnimation { duration: 60 }
            NumberAnimation { target: appWindow; property: "chromeProgress"; to: 0; duration: 320; easing.type: Easing.InCubic }
        }
        SequentialAnimation {
            PauseAnimation { duration: 120 }
            NumberAnimation { target: appWindow; property: "chromeOpacity"; to: 0; duration: 260; easing.type: Easing.InCubic }
        }
        NumberAnimation { target: appWindow; property: "chromeSlide"; to: 1; duration: 380; easing.type: Easing.InBack; easing.overshoot: 1.25 }
    }
    onHideDownloadChromeChanged: {
        if (hideDownloadChrome) { chromeShowAnim.stop(); chromeHideAnim.restart() }
        else { chromeHideAnim.stop(); chromeShowAnim.restart() }
    }

    onCurrentTabChanged: {
        if (typeof topTabBar !== "undefined" && topTabBar && topTabBar.ensureIndexVisible) {
            topTabBar.ensureIndexVisible(currentTab)
        }
    }

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    function openUpdateModal() {
        updateModal.isOpen = true;
    }

    function openTutorialModal() {
        tutorialModal.isOpen = true;
    }

    function openArchiveRebuildModal() {
        archiveRebuildModal.isOpen = true;
    }

    function openRetryModal() {
        mainRetryModal.isOpen = true;
    }

    function openCloudModal() {
        mainCloudModal.isOpen = true;
    }

    function openImportModal() {
        importConfirmModal.isOpen = true;
    }

    function openTextContextMenu(item, mouseX, mouseY) {
        globalTextContextMenu.showAt(item, mouseX, mouseY)
    }

    // Settings and Gallery are built in the background the first time they open, so a request
    // made before they exist is kept here and applied once they're ready (see their onLoaded)
    property int pendingSettingsSubTab: -1
    property string pendingProviderHighlight: ""
    property var pendingGalleryShow: null       // { path, isDir }

    function openSettingsTab(subTabIndex) {
        var idx = (subTabIndex !== undefined ? subTabIndex : 0)
        appWindow.currentTab = 12;      // builds the Settings tab if it wasn't opened yet
        if (settingsLoader.item) settingsLoader.item.currentSubTab = idx
        else appWindow.pendingSettingsSubTab = idx
    }

    function openTelegramWarningModal() {
        telegramWarningModal.open()
    }

    function openSessionRecoveryModal() {
        if (appBridge) {
            sessionRecoveryModal.sessionSummary = appBridge.recoverySummary
            sessionRecoveryModal.isOpen = true
        }
    }

    function showToast(msg, callback) {
        if (typeof discardWarningToast !== "undefined" && discardWarningToast && typeof discardWarningToast.showMessage === "function") {
            discardWarningToast.showMessage(msg, callback)
        }
    }


    ColumnLayout {
        id: rootWindowLayout
        anchors.fill: parent
        spacing: 0

        // Main Application Content Area (blurred when Privacy Shield is active)
        Item {
            id: mainAppContentArea
            Layout.fillWidth: true
            Layout.fillHeight: true

            property real targetBlur: (appBridge && appBridge.privacyModeActive) ? 2.5 : 0.0
            property real animatedBlur: 0.0
            onTargetBlurChanged: animatedBlur = targetBlur

            Behavior on animatedBlur {
                NumberAnimation {
                    duration: (appBridge && appBridge.privacyModeActive) ? 300 : 180
                    easing.type: (appBridge && appBridge.privacyModeActive) ? Easing.OutBack : Easing.OutCubic
                    easing.overshoot: 1.15
                }
            }

            layer.enabled: animatedBlur > 0.02
            layer.effect: MultiEffect {
                blurEnabled: true
                blur: 1.0
                blurMax: 64
                blurMultiplier: mainAppContentArea.animatedBlur
            }

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                TopTabBar {
                    id: topTabBar
                    window: appWindow
                }

        // Safe Mode Action & Reset Banner (shown when previous session requested PIN reset or 5 failed attempts)
        SafeModeResetBanner {
            id: safeModeBanner
            bridge: appBridge
        }

        // 2. Omnibox Browser Navigation Bar (the slot shrinks while the bar slides up out of it)
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: navBar.implicitHeight * appWindow.chromeProgress
            visible: appWindow.chromeProgress > 0
            opacity: appWindow.chromeOpacity
            clip: appWindow.chromeMoving

            BrowserNavBar {
                id: navBar
                width: parent.width
                height: implicitHeight
                anchors.bottom: parent.bottom
                transform: Translate { y: -16 * appWindow.chromeSlide }
                bridge: appBridge
                onStartRequested: {
                    if (appBridge) appBridge.startDownload()
                }
                onQueueRequested: {
                    if (appBridge) appBridge.addToQueue()
                }
                onSettingsRequested: {
                    appWindow.currentTab = 12
                }
            }
        }


        CreatorBanner {
            window: appWindow
        }

        DownloadActionBar {
            window: appWindow
        }

        // 3. Main Split Content Area
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true


            SplitView {
                id: mainSplitView
                anchors.fill: parent
                orientation: Qt.Horizontal
                property bool isHandleDragging: false

                // Custom drag handle — visible, glows on hover
                handle: Rectangle {
                    id: splitHandle
                    implicitWidth: 6
                    property bool isHovered: SplitHandle.hovered || SplitHandle.pressed
                    color: isHovered ? "#38BDF8" : "#1E2330"
                    visible: appWindow.showConsole && consoleContainer.width > 20

                    Behavior on color { ColorAnimation { duration: 150 } }

                    property bool wasPressed: false
                    Connections {
                        target: SplitHandle
                        function onPressedChanged() {
                            mainSplitView.isHandleDragging = SplitHandle.pressed
                            if (!SplitHandle.pressed && splitHandle.wasPressed) {
                                if (consoleContainer.visible && consoleContainer.width >= 320 && appBridge) {
                                    var clampedW = Math.round(Math.min(consoleContainer.maxAllowedConsoleWidth, consoleContainer.width))
                                    appBridge.consoleWidth = clampedW
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
                    SplitView.minimumWidth: 380
                    color: "#0F1117"

                    StackLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        currentIndex: appWindow.currentTab

                        TabTransitionWrapper {
                            active: appWindow.currentTab === 0
                            DownloaderView { id: downloaderView; anchors.fill: parent; bridge: appBridge }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 1
                            LazyTab {
                                id: browserLoader
                                anchors.fill: parent
                                wanted: appWindow.currentTab === 1
                                loadingText: appWindow.tr("tab_loading", "Loading…")
                                sourceComponent: Component { BrowserView { bridge: appBridge } }
                            }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 2
                            LazyTab {
                                anchors.fill: parent
                                wanted: appWindow.currentTab === 2
                                loadingText: appWindow.tr("tab_loading", "Loading…")
                                sourceComponent: Component { QueueView { bridge: appBridge } }
                            }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 3
                            LazyTab {
                                anchors.fill: parent
                                wanted: appWindow.currentTab === 3
                                loadingText: appWindow.tr("tab_loading", "Loading…")
                                sourceComponent: Component { WatchlistView { bridge: appBridge } }
                            }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 4
                            DecompressorView { anchors.fill: parent; bridge: appBridge }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 5
                            LazyTab {
                                anchors.fill: parent
                                wanted: appWindow.currentTab === 5
                                loadingText: appWindow.tr("tab_loading", "Loading…")
                                sourceComponent: Component { LinkVaultView { bridge: appBridge } }
                            }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 6
                            LazyTab {
                                anchors.fill: parent
                                wanted: appWindow.currentTab === 6
                                loadingText: appWindow.tr("tab_loading", "Loading…")
                                sourceComponent: Component { SchedulerView { bridge: appBridge } }
                            }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 7
                            LazyTab {
                                id: galleryLoader
                                anchors.fill: parent
                                wanted: appWindow.currentTab === 7
                                loadingText: appWindow.tr("tab_loading", "Loading…")
                                sourceComponent: Component { GalleryView { bridge: appBridge } }
                                onLoaded: {
                                    var req = appWindow.pendingGalleryShow
                                    appWindow.pendingGalleryShow = null
                                    if (req) {
                                        if (req.isDir) item.navigateTo(req.path)
                                        else item.revealInGallery(req.path)
                                    }
                                }
                            }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 8
                            LazyTab {
                                anchors.fill: parent
                                wanted: appWindow.currentTab === 8
                                loadingText: appWindow.tr("tab_loading", "Loading…")
                                sourceComponent: Component { KnownManagerView { bridge: appBridge } }
                            }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 9
                            LazyTab {
                                id: archiveLoader
                                anchors.fill: parent
                                wanted: appWindow.currentTab === 9
                                loadingText: appWindow.tr("tab_loading", "Loading…")
                                sourceComponent: Component { ArchiveView { bridge: appBridge } }
                            }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 10
                            LazyTab {
                                anchors.fill: parent
                                wanted: appWindow.currentTab === 10
                                loadingText: appWindow.tr("tab_loading", "Loading…")
                                sourceComponent: Component { HistoryView { bridge: appBridge } }
                            }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 11
                            LazyTab {
                                id: statisticsLoader
                                anchors.fill: parent
                                wanted: appWindow.currentTab === 11
                                loadingText: appWindow.tr("tab_loading", "Loading…")
                                sourceComponent: Component { StatisticsView { bridge: appBridge } }
                            }
                        }
                        TabTransitionWrapper {
                            active: appWindow.currentTab === 12
                            LazyTab {
                                id: settingsLoader
                                anchors.fill: parent
                                wanted: appWindow.currentTab === 12
                                loadingText: appWindow.tr("tab_loading", "Loading…")
                                sourceComponent: Component { SettingsView { objectName: "settingsViewTab"; bridge: appBridge } }
                                onLoaded: {
                                    if (appWindow.pendingSettingsSubTab >= 0) {
                                        item.currentSubTab = appWindow.pendingSettingsSubTab
                                        appWindow.pendingSettingsSubTab = -1
                                    }
                                    if (appWindow.pendingProviderHighlight !== "") {
                                        var prov = appWindow.pendingProviderHighlight
                                        appWindow.pendingProviderHighlight = ""
                                        item.highlightProvider(prov === "*" ? "" : prov)
                                    }
                                }
                            }
                        }
                    }
                }

                ConsolePanelContainer {
                    id: consoleContainer
                    window: appWindow
                    splitView: mainSplitView
                }
            } // SplitView
        } // Item 3: Main Split Content Area
        } // inner ColumnLayout
        } // mainAppContentArea

        // 3b. Persistent Background Archive Rebuild Progress Bar (visible across all tabs when minimized)
        ArchiveRebuildBar {
            id: archiveRebuildBar
            objectName: "archiveRebuildBar"
            Layout.fillWidth: true
            modal: archiveRebuildModal
        }


        StatusFooterBar {
            id: footerProgressArea
            window: appWindow
        }
    }

    // Keyboard shortcut for instant Privacy Shield toggle
    Shortcut {
        sequence: "Ctrl+P"
        onActivated: {
            if (appBridge) appBridge.togglePrivacyMode()
        }
    }

    // Global Privacy Shield Overlay — covers entire app view above the bottom progress footer
    PrivacyShieldOverlay {
        id: privacyShieldOverlay
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.bottomMargin: (footerProgressArea.visible && footerProgressArea.height > 0) ? footerProgressArea.height : 0
        z: 999999
        bridge: appBridge
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

    // Queue State Export Confirmation Modal
    ExportConfirmModal {
        id: exportConfirmModal
        bridge: appBridge
    }

    // Queue State Import Confirmation Modal
    ImportConfirmModal {
        id: importConfirmModal
        bridge: appBridge
    }

    // In-App Update Modal
    UpdateModal {
        id: updateModal
        updater: (typeof updaterBridge !== "undefined" ? updaterBridge : null)
    }

    // Comprehensive In-Depth Tutorial Modal
    TutorialModal {
        id: tutorialModal
    }

    // Global Right-Click Text Context Menu
    TextContextMenu {
        id: globalTextContextMenu
    }

    // Unfinished Crash Recovery Modal
    // Kemono / Coomer are switched off: tells the user where to go instead
    ProviderNoticeModal {
        id: providerNoticeModal
        bridge: appBridge
        onUseAlternative: (url) => { appBridge.currentUrl = url; appWindow.currentTab = 0 }
    }

    // Pawchive posts not yet imported onto Pawchive's storage nodes
    UnimportedNoticeModal {
        id: unimportedNoticeModal
        bridge: appBridge
        onOpenSettingsRequested: {
            appWindow.currentTab = 0
            if (typeof downloaderView !== "undefined" && downloaderView && typeof downloaderView.focusFallbackToThumbnailsSetting === "function") {
                downloaderView.focusFallbackToThumbnailsSetting()
            }
        }
    }

    SessionRecoveryModal {
        id: sessionRecoveryModal
        bridge: appBridge
        isOpen: false
    }

    // Global Archive Rebuild Modal
    ArchiveRebuildModal {
        id: archiveRebuildModal
        bridge: appBridge
        onRebuildCompleted: {
            if (archiveLoader.item && typeof archiveRebuildModal !== "undefined" && typeof archiveLoader.item.scheduleReload === "function") {
                archiveLoader.item.scheduleReload();
            }
        }
    }

    // Mid-Download Settings Change Confirmation Modal
    MidDownloadSettingsModal {
        id: midDownloadSettingsModal
        bridge: appBridge
    }


    MidDownloadBusyOverlay {
        id: midDownloadBusyOverlay
        window: appWindow
    }

    // Wire: when bridge emits postActionCountdownStarted, open the modal with the action label
    Connections {
        target: appBridge
        function onPostActionCountdownStarted(actionLabel) {
            countdownModal.actionLabel = actionLabel
            countdownModal.isOpen = true
        }
        function onExportCompleted(filePath, wasDownloading) {
            exportConfirmModal.exportedFilePath = filePath
            exportConfirmModal.wasDownloading = wasDownloading
            exportConfirmModal.isOpen = true
        }
        function onRecoverySessionDetected(summary) {
            sessionRecoveryModal.sessionSummary = summary
            sessionRecoveryModal.isOpen = true
        }
        function onSessionDiscardedWarning(oldDesc) {
            discardWarningToast.show(oldDesc)
        }
        function onMidDownloadSettingsPromptRequested(scope, payload) {
            midDownloadSettingsModal.openWithPayload(scope, payload)
        }
        function onMidDownloadApplyFinished(ok, message) {
            if (message && message.length > 0) {
                appWindow.showToast((ok ? "✅ " : "⚠️ ") + message)
            }
        }
        function onFavoriteAuthRequired(provName) {
            appWindow.currentTab = 12      // Settings (10 History, 11 Statistics)
            var cleanName = (provName || "").trim()
            var msg = cleanName.length > 0
                ? ("⭐ " + appWindow.tr("msg_fav_auth_required", "Favorite Mode requires account login for " + cleanName + ". Please connect below."))
                : ("⭐ " + appWindow.tr("msg_fav_login_hint", "Favorite Mode requires a connected account. Please log in below."))
            appWindow.showToast(msg)
            if (settingsLoader.item && typeof settingsLoader.item.highlightProvider === "function") {
                settingsLoader.item.highlightProvider(cleanName)
            } else {
                appWindow.pendingProviderHighlight = cleanName || "*"     // applied once Settings is built
            }
        }
        function onProviderDisabled(message, alternativeUrl, context) {
            providerNoticeModal.show(message, alternativeUrl, context)
        }
        function onUnimportedNotice(title, message, showModal) {
            if (showModal) {
                unimportedNoticeModal.show(title, message)
            } else if (message && message.length > 0) {
                appWindow.showToast("⚠️ " + message)
            }
        }
        function onGalleryShowRequested(path, isDir) {
            // An open Gallery handles this itself; otherwise build it first, then show the place
            if (galleryLoader.item) return
            appWindow.currentTab = 7
            if (galleryLoader.item) {
                if (isDir) galleryLoader.item.navigateTo(path)
                else galleryLoader.item.revealInGallery(path)
            } else {
                appWindow.pendingGalleryShow = { path: path, isDir: isDir }    // applied once it's built
            }
        }
    }


    GlobalWarningToast {
        id: discardWarningToast
    }

    // ── Interactive Creator Post Selection Modal ──────────────────────────────
    PostSelectionModal {
        id: postSelectionModal
        bridge: appBridge
        browserBridge: appWindow.ctxBrowserBridge
        onBackToFavoritesRequested: {
            if (favoritesBrowserModal.allArtists && favoritesBrowserModal.allArtists.length > 0) {
                favoritesBrowserModal.isOpen = true
            } else if (appBridge) {
                appBridge.fetchFavoriteArtists()
            }
        }
    }

    // ── Pawchive Favorite Artists Browser Modal ────────────────────────────────
    FavoritesBrowserModal {
        id: favoritesBrowserModal
        bridge: appBridge
        onBrowseArtistPosts: function(userId, service, creatorName) {
            postSelectionModal.fromFavoritesBrowser = true
        }
    }

    // ── Telegram Authentication Modal ─────────────────────────────────────────
    TelegramAuthModal {
        id: telegramAuthModal
        bridge: appBridge
        onContinued: {
            if (appBridge) {
                if (appBridge.isTelegramUrl) {
                    if (!appBridge.telegramSafetyAcknowledged || !appBridge.telegramLiabilityAcknowledged) {
                        telegramWarningModal.open()
                        return
                    }
                }
                if (typeof appBridge.resumeTelegramAction === "function") {
                    appBridge.resumeTelegramAction()
                } else {
                    appBridge.fetchPostsForSelection()
                }
            }
        }
    }

    // ── Telegram Channel Scope / Options Modal ────────────────────────────────
    TelegramScopeModal {
        id: telegramScopeModal
    }

    // ── Telegram Safety & Liability Warning Modal ─────────────────────────────
    TelegramWarningModal {
        id: telegramWarningModal
        bridge: appBridge
        onAccepted: {
            if (appBridge) appBridge.fetchPostsForSelection()
        }
    }

    function openTelegramAuthModal(isPrivate) {
        telegramAuthModal.isPrivateChannel = isPrivate
        telegramAuthModal.isOpen = true
    }

    function openTelegramScopeModal(channelId, rawUrl, isPrivate, defaultAction) {
        telegramScopeModal.targetChannelId = channelId
        telegramScopeModal.targetRawUrl = rawUrl
        telegramScopeModal.isPrivateChannel = isPrivate
        telegramScopeModal.channelTitle = (channelId && channelId.length > 0) ? channelId : "Telegram Channel"
        telegramScopeModal.defaultAction = (defaultAction === "select") ? "select" : "download"
        telegramScopeModal.isOpen = true
        if (typeof telegramBridge !== "undefined" && telegramBridge) {
            telegramBridge.resolveTarget(channelId, isPrivate)
        }
    }

    Connections {
        target: appBridge
        function onFavoriteArtistsReady(artists) {
            favoritesBrowserModal.openModal(artists)
        }
        function onFavoriteArtistsError(msg) {
            if (appBridge) {
                appBridge.lastErrorMessage = msg
                appBridge.hasError = true
            }
        }
        function onPostSelectionReady(posts, creator, totalCount) {
            if (favoritesBrowserModal.isBrowsingArtist) {
                favoritesBrowserModal.isBrowsingArtist = false
                favoritesBrowserModal.closeModal()
            }
            postSelectionModal.openModal(posts, creator, totalCount)
        }
        function onPostSelectionError(msg) {
            if (favoritesBrowserModal.isBrowsingArtist) {
                favoritesBrowserModal.isBrowsingArtist = false
            }
            if (appBridge) {
                appBridge.lastErrorMessage = msg
                appBridge.hasError = true
            }
        }
        function onTelegramAuthRequested(isPrivate) {
            openTelegramAuthModal(isPrivate)
        }
        function onTelegramScopeRequested(channelId, rawUrl, isPrivate, defaultAction) {
            openTelegramScopeModal(channelId, rawUrl, isPrivate, defaultAction)
        }
    }

    Connections {
        target: (typeof telegramBridge !== "undefined" && telegramBridge) ? telegramBridge : null
        function onChannelMetadataReady(meta) {
            if (meta && meta.title) {
                telegramScopeModal.channelTitle = meta.title
            }
        }
    }
}
