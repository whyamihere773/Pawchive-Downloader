import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "settings"

SmoothFlickable {
    id: root

    property var bridge: null

    // Cookie importer state
    property bool importingCookies: false
    property string cookieStatusText: ""
    property string cookieStatusColor: "#94A3B8"

    // AI Model download states
    property string aiT1Status: (root.bridge && root.bridge.aiFastSemanticReady) ? "ready" : "not_downloaded"
    property real aiT1Percent: (root.bridge && root.bridge.aiFastSemanticReady) ? 100 : 0
    property string aiT1Speed: ""
    property string aiT1Error: ""

    property string aiT2LightStatus: (root.bridge && root.bridge.aiDeepReasonerLightReady) ? "ready" : "not_downloaded"
    property real aiT2LightPercent: (root.bridge && root.bridge.aiDeepReasonerLightReady) ? 100 : 0
    property string aiT2LightSpeed: ""
    property string aiT2LightError: ""

    property string aiT2HeavyStatus: (root.bridge && root.bridge.aiDeepReasonerHeavyReady) ? "ready" : "not_downloaded"
    property real aiT2HeavyPercent: (root.bridge && root.bridge.aiDeepReasonerHeavyReady) ? 100 : 0
    property string aiT2HeavySpeed: ""
    property string aiT2HeavyError: ""

    property string aiClipStatus: "not_downloaded"
    property real aiClipPercent: 0
    property string aiClipSpeed: ""
    property string aiClipError: ""

    // Provider vault state
    property var providersList: []
    property var validationResults: ({})
    property string highlightedProviderId: ""
    property bool highlightAccountsSection: false

    NumberAnimation {
        id: scrollAnim
        target: root
        property: "contentY"
        duration: 380
        easing.type: Easing.OutCubic
    }

    Timer {
        id: highlightResetTimer
        interval: 7000
        repeat: false
        onTriggered: {
            root.highlightedProviderId = ""
            root.highlightAccountsSection = false
        }
    }

    function highlightProvider(provName) {
        root.currentSubTab = 0
        var raw = (provName || "").trim().toLowerCase()
        var pId = ""
        if (raw.indexOf("kemono") >= 0) pId = "kemono"
        else if (raw.indexOf("coomer") >= 0) pId = "coomer"
        else if (raw.indexOf("pawchive") >= 0) pId = "pawchive"
        else if (raw.indexOf("cumst") >= 0 || raw.indexOf("cum.st") >= 0) pId = "cumst"
        else pId = raw

        root.highlightedProviderId = pId
        root.highlightAccountsSection = true
        highlightResetTimer.restart()

        if (typeof accountsSection !== "undefined" && accountsSection) {
            var targetY = Math.max(0, Math.min(root.contentHeight - root.height, (subTab0Content ? subTab0Content.y : 0) + accountsSection.y - 10))
            scrollAnim.to = targetY
            scrollAnim.restart()
        }
    }

    function reloadProviders() {
        if (root.bridge && root.bridge.getProvidersList) {
            providersList = root.bridge.getProvidersList()
        }
    }

    function syncAiModelStatuses() {
        if (!root.bridge) return
        var s1 = root.bridge.getAiModelStatus("fast_semantic")
        if (s1) {
            aiT1Status = s1.status || (root.bridge.aiFastSemanticReady ? "ready" : "not_downloaded")
            aiT1Percent = (s1.percent !== undefined) ? s1.percent : (aiT1Status === "ready" ? 100 : 0)
            aiT1Speed = s1.speed_mbps ? (s1.speed_mbps.toFixed(1) + " MB/s") : ""
            aiT1Error = s1.error || ""
        }
        var s2l = root.bridge.getAiModelStatus("deep_reasoner_light")
        if (s2l) {
            aiT2LightStatus = s2l.status || (root.bridge.aiDeepReasonerLightReady ? "ready" : "not_downloaded")
            aiT2LightPercent = (s2l.percent !== undefined) ? s2l.percent : (aiT2LightStatus === "ready" ? 100 : 0)
            aiT2LightSpeed = s2l.speed_mbps ? (s2l.speed_mbps.toFixed(1) + " MB/s") : ""
            aiT2LightError = s2l.error || ""
        }
        var s2h = root.bridge.getAiModelStatus("deep_reasoner_heavy")
        if (s2h) {
            aiT2HeavyStatus = s2h.status || (root.bridge.aiDeepReasonerHeavyReady ? "ready" : "not_downloaded")
            aiT2HeavyPercent = (s2h.percent !== undefined) ? s2h.percent : (aiT2HeavyStatus === "ready" ? 100 : 0)
            aiT2HeavySpeed = s2h.speed_mbps ? (s2h.speed_mbps.toFixed(1) + " MB/s") : ""
            aiT2HeavyError = s2h.error || ""
        }
        var sClip = root.bridge.getAiModelStatus("visual_clip_vit")
        if (sClip) {
            aiClipStatus = sClip.status || (sClip.is_ready ? "ready" : "not_downloaded")
            aiClipPercent = (sClip.percent !== undefined) ? sClip.percent : (aiClipStatus === "ready" ? 100 : 0)
            aiClipSpeed = sClip.speed_mbps ? (sClip.speed_mbps.toFixed(1) + " MB/s") : ""
            aiClipError = sClip.error || ""
        }
    }

    Connections {
        target: root.bridge
        function onAiModelProgressChanged(modelKey, status, percent, speedStr, error) {
            if (modelKey === "fast_semantic") {
                root.aiT1Status = status
                root.aiT1Percent = percent
                root.aiT1Speed = speedStr
                root.aiT1Error = error
            } else if (modelKey === "deep_reasoner_light") {
                root.aiT2LightStatus = status
                root.aiT2LightPercent = percent
                root.aiT2LightSpeed = speedStr
                root.aiT2LightError = error
            } else if (modelKey === "deep_reasoner_heavy") {
                root.aiT2HeavyStatus = status
                root.aiT2HeavyPercent = percent
                root.aiT2HeavySpeed = speedStr
                root.aiT2HeavyError = error
            } else if (modelKey === "visual_clip_vit") {
                root.aiClipStatus = status
                root.aiClipPercent = percent
                root.aiClipSpeed = speedStr
                root.aiClipError = error
            }
        }
        function onProvidersChanged() {
            root.reloadProviders()
        }
        function onProviderValidationFinished(providerId, success, message) {
            var res = Object.assign({}, root.validationResults)
            res[providerId] = { "success": success, "message": message }
            root.validationResults = res
        }
        function onProviderLoginFinished(providerId, success, message) {
            var res = Object.assign({}, root.validationResults)
            res[providerId] = { "success": success, "message": message }
            root.validationResults = res
        }
    }

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }


    property int currentSubTab: 0

    // Fluid Newtonian Entrance parameters triggered on sub-tab switch
    property real tabEntranceOffsetY: 0
    property real tabEntranceOpacity: 1.0

    onCurrentSubTabChanged: {
        root.contentY = 0
        tabEntranceOffsetY = 14.0
        tabEntranceOpacity = 0.45
        tabEntranceTimer.restart()
    }

    Timer {
        id: tabEntranceTimer
        interval: 16
        repeat: false
        onTriggered: {
            root.tabEntranceOffsetY = 0.0
            root.tabEntranceOpacity = 1.0
        }
    }

    Behavior on tabEntranceOffsetY {
        SpringAnimation {
            spring: 4.2
            damping: 0.38
            mass: 1.15
            epsilon: 0.1
        }
    }

    Behavior on tabEntranceOpacity {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    // Reactive badges for sub-tabs
    readonly property int connectedAccountsCount: {
        var count = 0
        if (root.providersList) {
            for (var i = 0; i < root.providersList.length; i++) {
                if (root.providersList[i].is_logged_in) count++
            }
        }
        if (typeof telegramBridge !== "undefined" && telegramBridge && telegramBridge.isLoggedIn) count++
        return count
    }

    // (these used to read properties the bridge doesn't have, so both badges never showed)
    readonly property bool proxyActive: {
        return (root.bridge && (root.bridge.proxyUrl || "").trim().length > 0) ? true : false
    }

    readonly property int storagePoolDriveCount: {
        if (!root.bridge || !root.bridge.storagePoolEnabled) return 0
        try {
            var st = JSON.parse(root.bridge.storagePoolStatusJson || "{}")
            return (st.primary_dir ? 1 : 0) + (st.overflow_dirs ? st.overflow_dirs.length : 0)
        } catch (e) {
            return 0
        }
    }

    readonly property bool aiModelsReady: {
        return (root.bridge && (root.bridge.aiFastSemanticReady || root.bridge.aiDeepReasonerLightReady || root.bridge.aiDeepReasonerHeavyReady)) ? true : false
    }

    contentWidth: width
    contentHeight: settingsCol.implicitHeight + 36

    // Cascading Newtonian entrance animation stage
    property int entranceStage: 0

    function triggerEntrance() {
        entranceStage = 0
        staggerTimer.restart()
    }

    Timer {
        id: staggerTimer
        interval: 35
        repeat: true
        running: false
        onTriggered: {
            entranceStage++
            if (entranceStage >= 7) stop()
        }
    }

    Component.onCompleted: {
        triggerEntrance()
        syncAiModelStatuses()
        reloadProviders()
    }
    onVisibleChanged: {
        if (visible) {
            triggerEntrance()
            syncAiModelStatuses()
            reloadProviders()
        }
    }

    ColumnLayout {
        id: settingsCol
        width: root.width - (root.verticalScrollBar && root.verticalScrollBar.visible ? 10 : 0)
        spacing: 12

        PendingSettingsBanner {
            Layout.fillWidth: true
            bridge: root.bridge
        }


        SettingsSubTabDock {
            id: subTabDock
            view: root
        }

        // ====================================================================
        // SUB-TAB 0: ACCOUNTS & SERVICES (Language, Privacy, Vault, Telegram)
        // ====================================================================
        ColumnLayout {
            id: subTab0Content
            visible: root.currentSubTab === 0
            Layout.fillWidth: true
            spacing: 12

            SettingsLanguageCard {
                view: root
            }

            SettingsPrivacyCard {
                view: root
            }

            SettingsAccountsCard {
                id: accountsSection
                view: root
            }

            SettingsTelegramCard {
                view: root
            }
        }

        // ====================================================================
        // SUB-TAB 1: NETWORK & CONNECTION (Cloudflare, Proxy, Headers)
        // ====================================================================
        Loader {
            id: subTab1Loader
            Layout.fillWidth: true
            visible: root.currentSubTab === 1
            active: root.currentSubTab === 1
            onLoaded: active = true
            sourceComponent: Component {
                SettingsNetworkTab {
                    view: root
                }
            }
        }

        // ====================================================================
        // SUB-TAB 2: STORAGE & SYSTEM (File processing, Pools, Post-actions)
        // ====================================================================
        Loader {
            id: subTab2Loader
            Layout.fillWidth: true
            visible: root.currentSubTab === 2
            active: root.currentSubTab === 2
            onLoaded: active = true
            sourceComponent: Component {
                SettingsStorageTab {
                    view: root
                }
            }
        }

        // ====================================================================
        // SUB-TAB 3: AI & RECOGNITION (Known Engine & Local AI Models)
        // ====================================================================
        Loader {
            id: subTab3Loader
            Layout.fillWidth: true
            visible: root.currentSubTab === 3
            active: root.currentSubTab === 3
            onLoaded: active = true
            sourceComponent: Component {
                SettingsAiTab {
                    view: root
                }
            }
        }

        // Action Buttons & About
        Flow {
            width: settingsCol.width
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8
            layoutDirection: Qt.RightToLeft
            opacity: root.entranceStage >= 7 ? 1.0 : 0.0
            transform: Translate {
                y: root.entranceStage >= 7 ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.0; damping: 0.38; mass: 1.0; epsilon: 0.25 }
                }
            }
            Behavior on opacity {
                NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
            }

            StyledButton {
                text: tr("btn_save_preferences", "Save Preferences")
                iconText: "💾"
                variant: "primary"
                onClicked: if (root.bridge) root.bridge.saveSettings(true)
            }

            StyledButton {
                text: tr("btn_export_console_logs", "Export Console Logs")
                iconText: "📄"
                variant: "outline"
                onClicked: if (root.bridge) root.bridge.exportLogs()
            }

            StyledButton {
                text: "☕ " + tr("btn_support_kofi", "Support on Ko-fi")
                variant: "outline"
                onClicked: Qt.openUrlExternally("https://ko-fi.com/whyamihere773")
            }

            StyledButton {
                text: "🔄 " + (typeof updaterBridge !== "undefined" && updaterBridge && updaterBridge.isChecking ? tr("btn_checking_update", "Checking...") : tr("btn_check_update", "Check for Updates"))
                variant: "outline"
                enabled: !(typeof updaterBridge !== "undefined" && updaterBridge && updaterBridge.isChecking)
                onClicked: {
                    if (typeof updaterBridge !== "undefined" && updaterBridge) {
                        updaterBridge.checkForUpdates(false)
                        appWindow.openUpdateModal()
                    }
                }
            }

            StyledButton {
                text: "📂 " + tr("btn_open_logs", "Logs Folder")
                variant: "outline"
                onClicked: if (root.bridge) root.bridge.openLogsFolder()
            }
        }
    }
}
