import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

ColumnLayout {
    id: subTab2Content
    required property var view
    function tr(key, fallback) { return view ? view.tr(key, fallback) : (fallback !== undefined ? fallback : key) }
    visible: subTab2Content.view.currentSubTab === 2
    Layout.fillWidth: true
    spacing: 12

SettingsStorageProcessingCard {
    view: subTab2Content.view
}
// Logs: where they are and how much space they take. They're never deleted automatically;
// this button is the only thing that removes them.
CardSection {
    id: logsCard
    Layout.fillWidth: true
    interactive: !subTab2Content.view.isScrolling
    title: tr("section_logs", "Logs")
    iconText: "📜"
    entranceOffsetY: subTab2Content.view.tabEntranceOffsetY
    entranceOpacity: subTab2Content.view.tabEntranceOpacity

    property var usage: ({ "files": 0, "text": tr("logs_measuring", "Measuring…"), "folder": "" })
    property bool confirmClear: false
    property string resultText: ""
    property string usageRequest: ""
    // Measured in the background: sizing every log file held up the page while it opened
    function refresh() {
        if (!subTab2Content.view.bridge) return
        usageRequest = "logs-usage-" + Date.now()
        subTab2Content.view.bridge.logsUsageAsync(usageRequest)
    }
    Component.onCompleted: refresh()

    Connections {
        target: subTab2Content.view
        function onCurrentSubTabChanged() {
            if (subTab2Content.view.currentSubTab === 2) { logsCard.refresh(); logsCard.confirmClear = false }
        }
    }
    Connections {
        target: subTab2Content.view.bridge
        function onAsyncResultReady(requestId, result) {
            if (requestId !== logsCard.usageRequest || !result) return
            logsCard.usageRequest = ""
            logsCard.usage = result
        }
    }
    Timer { id: logsConfirmTimer; interval: 4000; onTriggered: logsCard.confirmClear = false }

    ColumnLayout {
        width: parent.width
        spacing: 10

        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: tr("logs_explain", "Every session is saved in the logs folder next to the app, in a folder for each version (the updater has its own folder). Logs are never deleted automatically.")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 12
            color: "#94A3B8"
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Rectangle {
                Layout.preferredHeight: 26
                Layout.preferredWidth: logsSizeText.implicitWidth + 18
                radius: 5
                color: "#161E2E"
                border.color: "#1E293B"
                Text {
                    id: logsSizeText
                    anchors.centerIn: parent
                    text: logsCard.usage.text
                    font.family: "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 12
                    color: "#E2E8F0"
                }
            }

            Text {
                Layout.fillWidth: true
                text: logsCard.resultText
                visible: text.length > 0
                elide: Text.ElideRight
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: "#10B981"
            }
            Item { Layout.fillWidth: true; visible: logsCard.resultText.length === 0 }

            StyledButton {
                text: tr("btn_open_logs_folder", "Open folder")
                iconText: "📂"
                tooltip: logsCard.usage.folder
                onClicked: if (subTab2Content.view.bridge) subTab2Content.view.bridge.openLogsFolder()
            }

            StyledButton {
                variant: logsCard.confirmClear ? "danger" : "default"
                iconText: "🗑"
                text: logsCard.confirmClear ? tr("btn_clear_logs_confirm", "Click again to delete all logs")
                                            : tr("btn_clear_logs", "Clear logs…")
                tooltip: tr("btn_clear_logs_tip", "Deletes every log file except the one for this session")
                enabled: logsCard.usage.files > 1
                onClicked: {
                    if (!logsCard.confirmClear) {
                        logsCard.confirmClear = true
                        logsConfirmTimer.restart()
                        return
                    }
                    logsCard.confirmClear = false
                    if (subTab2Content.view.bridge) {
                        var r = subTab2Content.view.bridge.deleteAllLogs()
                        logsCard.resultText = r.text
                    }
                    logsCard.refresh()
                }
            }
        }
    }
}

// Multi-Drive Overflow & Auto-Spanning (Storage Pools)
CardSection {
    Layout.fillWidth: true
    interactive: !subTab2Content.view.isScrolling
    title: tr("section_storage_pools", "Multi-Drive Overflow & Auto-Spanning (Storage Pools)")
    iconText: "💽"
    entranceOffsetY: subTab2Content.view.tabEntranceOffsetY
    entranceOpacity: subTab2Content.view.tabEntranceOpacity

    ColumnLayout {
        id: storagePoolCol
        width: parent.width
        spacing: 12

        property var poolData: {
            try {
                return subTab2Content.view.bridge ? JSON.parse(subTab2Content.view.bridge.storagePoolStatusJson) : {}
            } catch(e) {
                return {}
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: tr("opt_enable_pools", "Enable Multi-Drive Storage Overflow")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: "#F1F5F9"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            StyledSwitch {
                checked: storagePoolCol.poolData.enabled !== undefined ? storagePoolCol.poolData.enabled : false
                accentColor: "#38BDF8"
                onToggled: function(isChecked) {
                    if (subTab2Content.view.bridge) subTab2Content.view.bridge.setStoragePoolEnabled(isChecked)
                }
            }
        }

        Text {
            text: tr("desc_storage_pools", "Prevents disk-full crashes ('No space left on device') by automatically spilling file downloads to secondary drives when your primary drive reaches its safety margin. Preserves creator and post directory hierarchy seamlessly.")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            Layout.preferredWidth: 0
            Layout.minimumWidth: 0
        }

        // Safety Margin Row
        Flow {
            width: parent.width
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            RowLayout {
                spacing: 8
                Text {
                    text: tr("label_safety_margin", "Safety Free Space Margin:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#CBD5E1"
                }

                StyledSpinBox {
                    id: marginSpin
                    from: 2
                    to: 100
                    value: storagePoolCol.poolData.safety_margin_gb || 10
                    stepSize: 1
                    suffix: " GB"
                    accentColor: "#38BDF8"
                    implicitWidth: 110
                    onValueModified: function(v) {
                        if (subTab2Content.view.bridge) subTab2Content.view.bridge.setStoragePoolMargin(v)
                    }
                }
            }

            Text {
                text: "(" + tr("desc_margin_trigger", "triggers overflow when remaining space drops below this limit") + ")"
                font.pixelSize: 10
                color: "#64748B"
                wrapMode: Text.WordWrap
                width: parent.width
            }
        }

        // Drive Capacity List
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            Repeater {
                model: storagePoolCol.poolData.drives || []

                delegate: Rectangle {
                    id: driveCard
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: 52
                    radius: 6
                    color: driveHover.hovered ? "#182233" : "#141A26"
                    border.color: modelData.is_low ? "#EF4444" : (driveHover.hovered ? "#38BDF8" : "#233147")
                    border.width: 1

                    HoverHandler { id: driveHover }

                    transform: Translate {
                        y: driveHover.hovered ? -2.0 : 0
                        Behavior on y {
                            SpringAnimation { spring: 4.0; damping: 0.38; mass: 0.9; epsilon: 0.25 }
                        }
                    }

                    Behavior on color { ColorAnimation { duration: 160 } }
                    Behavior on border.color { ColorAnimation { duration: 160 } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 10

                        Text {
                            text: modelData.is_primary ? "💾" : "💽"
                            font.pixelSize: 14
                            scale: driveHover.hovered ? 1.15 : 1.0
                            Behavior on scale {
                                SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.01 }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                Text {
                                    text: modelData.path
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: "#F1F5F9"
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 40
                                }

                                Rectangle {
                                    visible: modelData.is_primary
                                    height: 16
                                    implicitWidth: primaryTag.implicitWidth + 8
                                    radius: 3
                                    color: "#0369A1"
                                    Text {
                                        id: primaryTag
                                        anchors.centerIn: parent
                                        text: "PRIMARY"
                                        font.pixelSize: 9
                                        font.weight: Font.Bold
                                        color: "#E0F2FE"
                                    }
                                }

                                Rectangle {
                                    visible: modelData.is_low
                                    height: 16
                                    implicitWidth: lowTag.implicitWidth + 8
                                    radius: 3
                                    color: "#7F1D1D"
                                    Text {
                                        id: lowTag
                                        anchors.centerIn: parent
                                        text: "LOW SPACE"
                                        font.pixelSize: 9
                                        font.weight: Font.Bold
                                        color: "#FEE2E2"
                                    }
                                }

                                Item { Layout.fillWidth: true }

                                Text {
                                    text: driveCard.width > 340 ? (modelData.free_gb + " GB free / " + modelData.total_gb + " GB (" + modelData.used_percent + "% used)") : (modelData.free_gb + " GB free")
                                    font.pixelSize: 10
                                    color: modelData.is_low ? "#EF4444" : "#94A3B8"
                                    elide: Text.ElideRight
                                }
                            }

                            // Simple capacity bar with smooth Newtonian filling
                            Rectangle {
                                Layout.fillWidth: true
                                height: 6
                                radius: 3
                                color: "#0F172A"

                                Rectangle {
                                    width: parent.width * (Math.min(100, Math.max(0, modelData.used_percent)) / 100.0)
                                    height: parent.height
                                    radius: 3
                                    color: modelData.is_low ? "#EF4444" : (modelData.used_percent > 85 ? "#F59E0B" : "#10B981")

                                    Behavior on width {
                                        SpringAnimation {
                                            spring: 2.8
                                            damping: 0.4
                                            mass: 1.0
                                            epsilon: 0.5
                                        }
                                    }
                                }
                            }
                        }

                        // Remove button for secondary overflow drives with spring pop
                        Rectangle {
                            visible: !modelData.is_primary
                            width: 24; height: 24; radius: 4
                            color: removePoolMouse.containsMouse ? "#3B181E" : "transparent"
                            scale: removePoolMouse.pressed ? 0.85 : (removePoolMouse.containsMouse ? 1.25 : 1.0)
                            transformOrigin: Item.Center
                            Behavior on scale {
                                SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.01 }
                            }
                            Behavior on color { ColorAnimation { duration: 100 } }

                            Text {
                                anchors.centerIn: parent
                                text: "✖"
                                font.pixelSize: 11
                                color: "#EF4444"
                            }
                            MouseArea {
                                id: removePoolMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (subTab2Content.view.bridge) subTab2Content.view.bridge.removeStoragePoolDrive(modelData.path)
                                }
                            }
                        }
                    }
                }
            }
        }

        // Add Overflow Drive Button
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            StyledButton {
                text: tr("btn_add_storage_drive", "Add Overflow Drive / Folder...")
                iconText: "➕"
                variant: "outline"
                onClicked: {
                    if (subTab2Content.view.bridge) subTab2Content.view.bridge.selectStoragePoolDirectory()
                }
            }

            Item { Layout.fillWidth: true }
        }
    }
}


// Post-Download & System Actions (What to do after done)
CardSection {
    Layout.fillWidth: true
    interactive: !subTab2Content.view.isScrolling
    title: tr("section_post_actions", "Post-Download & System Actions")
    iconText: "⚡"
    entranceOffsetY: subTab2Content.view.tabEntranceOffsetY
    entranceOpacity: subTab2Content.view.tabEntranceOpacity

    ColumnLayout {
        width: parent.width
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        spacing: 12

        // Convenient checkboxes for notifications / folders
        Flow {
            width: parent.width
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 16

            StyledCheckBox {
                text: tr("opt_open_complete", "Open download directory when complete")
                tooltip: tr("opt_open_complete_tip", "Automatically open Windows File Explorer to the downloaded creator folder")
                checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.openFolderOnComplete : false
                onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.openFolderOnComplete = checked
            }

            StyledCheckBox {
                text: tr("opt_chime_complete", "Play chime sound when complete")
                tooltip: tr("opt_chime_complete_tip", "Play an audible notification chime when all download tasks finish")
                checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.playCompletionSound : false
                onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.playCompletionSound = checked
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#1E293B"
        }

        // Power/App Action Selector
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                Text {
                    text: tr("label_what_to_do", "What to do after download finishes (one-time action):")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#94A3B8"
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
                Text {
                    text: tr("note_what_to_do", "• Resets to 'Do Nothing' after each task. Can also be set directly in the bottom action bar.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
            }

            Flow {
                width: parent.width
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 8

                FilterCheckbox {
                    label: tr("action_none", "Do Nothing")
                    iconText: "⏸️"
                    tooltip: tr("action_none_tip", "Keep application open and system running normally")
                    checked: subTab2Content.view.bridge ? (subTab2Content.view.bridge.postDownloadAction === "none" || subTab2Content.view.bridge.postDownloadAction === "") : true
                    onClicked: if (subTab2Content.view.bridge) subTab2Content.view.bridge.postDownloadAction = "none"
                }

                FilterCheckbox {
                    label: tr("action_close", "Close App")
                    iconText: "🚪"
                    activeColor: "#38BDF8"
                    tooltip: tr("action_close_tip", "Automatically exit Pawchive Downloader when all files finish downloading")
                    checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.postDownloadAction === "close_app" : false
                    onClicked: if (subTab2Content.view.bridge) subTab2Content.view.bridge.postDownloadAction = "close_app"
                }

                FilterCheckbox {
                    label: tr("action_sleep", "Sleep System")
                    iconText: "🌙"
                    activeColor: "#A78BFA"
                    tooltip: tr("action_sleep_tip", "Put the computer into sleep / suspend mode after download completes")
                    checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.postDownloadAction === "sleep" : false
                    onClicked: if (subTab2Content.view.bridge) subTab2Content.view.bridge.postDownloadAction = "sleep"
                }

                FilterCheckbox {
                    label: tr("action_hibernate", "Hibernate (-F Force)")
                    iconText: "💤"
                    activeColor: "#818CF8"
                    tooltip: tr("action_hibernate_tip", "Force save memory to disk and turn off power (Hibernate -F)")
                    checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.postDownloadAction === "hibernate" : false
                    onClicked: if (subTab2Content.view.bridge) subTab2Content.view.bridge.postDownloadAction = "hibernate"
                }

                FilterCheckbox {
                    label: tr("action_shutdown", "Shut Down (-F Force)")
                    iconText: "🔌"
                    activeColor: "#F43F5E"
                    tooltip: tr("action_shutdown_tip", "Force close running applications and safely shut down the computer (includes 10s cancel buffer)")
                    checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.postDownloadAction === "shutdown" : false
                    onClicked: if (subTab2Content.view.bridge) subTab2Content.view.bridge.postDownloadAction = "shutdown"
                }

                FilterCheckbox {
                    label: tr("action_restart", "Restart (-F Force)")
                    iconText: "🔄"
                    activeColor: "#F59E0B"
                    tooltip: tr("action_restart_tip", "Force close running applications and restart the operating system")
                    checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.postDownloadAction === "restart" : false
                    onClicked: if (subTab2Content.view.bridge) subTab2Content.view.bridge.postDownloadAction = "restart"
                }
            }
        }
    }
}

// Workspace & Tab Bar Visibility (Customize Visible Top-Level Tabs)
CardSection {
    Layout.fillWidth: true
    interactive: !subTab2Content.view.isScrolling
    title: tr("section_tab_visibility", "Workspace & Tab Bar Visibility")
    iconText: "🗂️"
    entranceOffsetY: subTab2Content.view.tabEntranceOffsetY
    entranceOpacity: subTab2Content.view.tabEntranceOpacity

    readonly property var disabledList: subTab2Content.view.bridge ? subTab2Content.view.bridge.disabledTabs : []
    function isTabShown(tabKey) {
        if (!disabledList) return true
        return disabledList.indexOf(tabKey) < 0
    }

    ColumnLayout {
        id: tabVisCol
        width: parent.width
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: tr("desc_tab_visibility", "Show or hide optional top-level tabs to keep your workspace clean. 'Downloader' and 'Settings' are always pinned.")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#94A3B8"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            StyledButton {
                visible: subTab2Content.view.bridge ? (subTab2Content.view.bridge.disabledTabs && subTab2Content.view.bridge.disabledTabs.length > 0) : false
                text: tr("btn_restore_all_tabs", "Restore All Tabs")
                iconText: "↺"
                variant: "outline"
                implicitHeight: 28
                onClicked: {
                    if (subTab2Content.view.bridge) subTab2Content.view.bridge.resetDisabledTabs()
                }
            }
        }

        Flow {
            width: parent.width
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            Repeater {
                model: [
                    { key: "browser", label: "Browser", icon: "🌐", color: "#38BDF8", tip: "Native Online & On-Disk Local Browser" },
                    { key: "queue", label: "Queue", icon: "📋", color: "#38BDF8", tip: "Task queue and download monitoring" },
                    { key: "watchlist", label: "Watchlist", icon: "📌", color: "#A78BFA", tip: "Followed creators and update tracker" },
                    { key: "decompressor", label: "Decompressor", icon: "📦", color: "#38BDF8", tip: "Bulk archive decompression" },
                    { key: "link_vault", label: "Link Vault", icon: "🗝️", color: "#F59E0B", tip: "Harvested cloud links & password resolver" },
                    { key: "scheduler", label: "Scheduler", icon: "⏰", color: "#818CF8", tip: "Automated schedules & Night Owl windows" },
                    { key: "gallery", label: "Gallery", icon: "🖼️", color: "#EC4899", tip: "File Explorer, Media Gallery & Visual Sorter" },
                    { key: "known", label: "Known Series", icon: "🏷️", color: "#34D399", tip: "Known character & series directory rules" },
                    { key: "archive", label: "Archive", icon: "🗃️", color: "#2DD4BF", tip: "Persistent download archive database" },
                    { key: "history", label: "History", icon: "📜", color: "#38BDF8", tip: "Completed downloads & past batch sessions" },
                    { key: "statistics", label: "Statistics", icon: "📊", color: "#38BDF8", tip: "Raw bandwidth, disk size, artists, files & folders telemetry" }
                ]

                delegate: FilterCheckbox {
                    readonly property var tb: modelData || ({})
                    readonly property bool shown: subTab2Content.view.bridge ? (subTab2Content.view.bridge.disabledTabs.indexOf(tb.key) < 0) : true
                    label: tb.label
                    iconText: tb.icon
                    activeColor: tb.color || "#38BDF8"
                    tooltip: tb.tip + (shown ? " (Visible — click to hide)" : " (Hidden — click to show)")
                    checked: shown
                    onClicked: {
                        if (subTab2Content.view.bridge) {
                            subTab2Content.view.bridge.setTabDisabled(tb.key, shown)
                        }
                    }
                }
            }
        }
    }
}

}
