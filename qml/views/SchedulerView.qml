import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "scheduler"

Item {
    id: schedViewRoot
    property var bridge: null

    // ── Helpers ────────────────────────────────────────────────────────────────
    function tr(key, fallback) {
        if (typeof appWindow !== "undefined") return appWindow.tr(key, fallback)
        return fallback !== undefined ? fallback : key
    }

    function showToast(msg) {
        if (statusToast) {
            statusToast.show(msg)
        }
    }

    // ── Schedule State ─────────────────────────────────────────────────────────
    property var schedulesList: []
    property bool showAddDialog: false
    property string editingScheduleId: ""

    function refreshSchedules() {
        if (!schedViewRoot.bridge) return
        try {
            var raw = schedViewRoot.bridge.schedulerSchedulesJson
            schedViewRoot.schedulesList = raw ? JSON.parse(raw) : []
        } catch (e) {
            schedViewRoot.schedulesList = []
        }
    }

    function openScheduleDialog(task) {
        schedViewRoot.editingScheduleId = task ? (task.id || "") : ""
        addDialogModal.populateFromTask(task)
        schedViewRoot.showAddDialog = true
    }

    Component.onCompleted: {
        refreshSchedules()
        triggerEntrance()
    }

    onVisibleChanged: {
        if (visible) {
            refreshSchedules()
            triggerEntrance()
        }
    }

    Connections {
        target: schedViewRoot.bridge
        function onSchedulerChanged() {
            schedViewRoot.refreshSchedules()
        }
    }

    // ── Save Global Settings Helper ───────────────────────────────────────────
    function saveGlobalSettings(enabled, lockThreads, nightOwl, start, end, preventSleep, sweepRetry) {
        if (!schedViewRoot.bridge) return
        schedViewRoot.bridge.setSchedulerSettings(
            enabled !== undefined ? enabled : schedViewRoot.bridge.schedulerEnabled,
            lockThreads !== undefined ? lockThreads : schedViewRoot.bridge.schedulerLockThreadsDelay,
            nightOwl !== undefined ? nightOwl : schedViewRoot.bridge.schedulerNightOwlEnabled,
            start !== undefined ? start : schedViewRoot.bridge.schedulerNightOwlStart,
            end !== undefined ? end : schedViewRoot.bridge.schedulerNightOwlEnd,
            preventSleep !== undefined ? preventSleep : schedViewRoot.bridge.schedulerPreventSleep,
            sweepRetry !== undefined ? sweepRetry : schedViewRoot.bridge.schedulerSweepRetry
        )
    }

    // ── Cascading Newtonian Entrance Animation ─────────────────────────────────
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
            if (entranceStage >= 4) stop()
        }
    }

    // ── Newtonian Momentum Scrolling State ─────────────────────────────────────
    readonly property bool isScrolling: mainFlickable.isScrolling

    // ── Scrollable Viewport ────────────────────────────────────────────────────
    SmoothFlickable {
        id: mainFlickable
        anchors.fill: parent
        contentWidth: width
        contentHeight: mainCol.implicitHeight + 40

        ColumnLayout {
            id: mainCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 20
            anchors.rightMargin: (mainFlickable.verticalScrollBar && mainFlickable.verticalScrollBar.visible ? 24 : 20)
            spacing: 16

            // ── 1. Top Header Bar (Uncut Responsive Layout) ────────────────────
            Rectangle {
                id: headerSection
                Layout.fillWidth: true
                implicitHeight: headerContentCol.implicitHeight + 24
                radius: 10
                color: "#141722"
                border.color: "#283044"
                border.width: 1

                opacity: schedViewRoot.entranceStage >= 1 ? 1.0 : 0.0
                transform: Translate {
                    y: schedViewRoot.entranceStage >= 1 ? 0 : 20
                    Behavior on y {
                        SpringAnimation { spring: 4.2; damping: 0.38; mass: 1.0; epsilon: 0.25 }
                    }
                }
                Behavior on opacity { NumberAnimation { duration: 180 } }

                ColumnLayout {
                    id: headerContentCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 14
                    spacing: 12

                    // Top Row: Icon + Title + Status Badge (+ Actions on Wide Screens)
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 14

                        Rectangle {
                            width: 42; height: 42; radius: 8
                            color: "#1E1B4B"
                            border.color: "#818CF8"; border.width: 1.2
                            Text { anchors.centerIn: parent; text: "⏰"; font.pixelSize: 22 }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 4

                            Flow {
                                Layout.fillWidth: true
                                spacing: 8

                                Text {
                                    text: schedViewRoot.tr("scheduler_title", "Task Scheduler & Automation Hub")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 17
                                    font.weight: Font.Bold
                                    color: "#F8FAFC"
                                    wrapMode: Text.WordWrap
                                    width: Math.min(implicitWidth, parent.width)
                                }

                                // Master active badge
                                Rectangle {
                                    height: 22
                                    implicitWidth: schedStatusText.implicitWidth + 18
                                    radius: 11
                                    color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerEnabled) ? "#064E3B" : "#334155"
                                    border.color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerEnabled) ? "#10B981" : "#64748B"
                                    border.width: 1
                                    Row {
                                        anchors.centerIn: parent
                                        spacing: 6
                                        Rectangle {
                                            width: 7; height: 7; radius: 3.5
                                            color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerEnabled) ? "#34D399" : "#94A3B8"
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            id: schedStatusText
                                            text: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerEnabled) ?
                                                  schedViewRoot.tr("scheduler_status_active", "Running") :
                                                  schedViewRoot.tr("scheduler_status_paused", "Disabled")
                                            font.pixelSize: 11
                                            font.weight: 600
                                            color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerEnabled) ? "#6EE7B7" : "#CBD5E1"
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }
                            }

                            Text {
                                text: schedViewRoot.tr("scheduler_subtitle", "Download new Watchlist posts and creators automatically, at times you choose.")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                color: "#94A3B8"
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }

                        // Wide View Actions (When space is ample > 740px)
                        RowLayout {
                            visible: schedViewRoot.width > 740
                            spacing: 14
                            Layout.alignment: Qt.AlignVCenter

                            RowLayout {
                                spacing: 8
                                Text {
                                    text: schedViewRoot.tr("scheduler_master_toggle", "Master Automation")
                                    font.pixelSize: 12
                                    font.weight: 600
                                    color: "#E2E8F0"
                                }
                                StyledSwitch {
                                    checked: schedViewRoot.bridge ? schedViewRoot.bridge.schedulerEnabled : false
                                    accentColor: "#38BDF8"
                                    onToggled: function(isChecked) {
                                        schedViewRoot.saveGlobalSettings(isChecked, undefined, undefined, undefined, undefined, undefined, undefined)
                                        schedViewRoot.showToast(isChecked ? schedViewRoot.tr("toast_scheduler_enabled", "Scheduler enabled") : schedViewRoot.tr("toast_scheduler_disabled", "Scheduler disabled"))
                                    }
                                }
                            }

                            Rectangle {
                                height: 36
                                implicitWidth: newBtnRow1.implicitWidth + 24
                                radius: 8
                                color: newSchedMouse1.containsMouse ? "#4338CA" : "#4F46E5"
                                border.color: newSchedMouse1.containsMouse ? "#A5B4FC" : "#818CF8"
                                border.width: 1
                                scale: newSchedMouse1.pressed ? 0.92 : (newSchedMouse1.containsMouse ? 1.04 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                                Row {
                                    id: newBtnRow1
                                    anchors.centerIn: parent
                                    spacing: 8
                                    Text { text: "➕"; font.pixelSize: 12; color: "#FFFFFF"; anchors.verticalCenter: parent.verticalCenter }
                                    Text {
                                        text: schedViewRoot.tr("scheduler_btn_new", "New Schedule")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 12
                                        font.weight: Font.Bold
                                        color: "#FFFFFF"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea {
                                    id: newSchedMouse1
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: schedViewRoot.openScheduleDialog(null)
                                }
                            }
                        }
                    }

                    // Narrow View Actions Row (Smoothly positions below on narrow widths / wide console)
                    RowLayout {
                        visible: schedViewRoot.width <= 740
                        Layout.fillWidth: true
                        spacing: 12

                        RowLayout {
                            spacing: 8
                            Text {
                                text: schedViewRoot.tr("scheduler_master_toggle", "Master Automation")
                                font.pixelSize: 12
                                font.weight: 600
                                color: "#E2E8F0"
                            }
                            StyledSwitch {
                                checked: schedViewRoot.bridge ? schedViewRoot.bridge.schedulerEnabled : false
                                accentColor: "#38BDF8"
                                onToggled: function(isChecked) {
                                    schedViewRoot.saveGlobalSettings(isChecked, undefined, undefined, undefined, undefined, undefined, undefined)
                                    schedViewRoot.showToast(isChecked ? schedViewRoot.tr("toast_scheduler_enabled", "Scheduler enabled") : schedViewRoot.tr("toast_scheduler_disabled", "Scheduler disabled"))
                                }
                            }
                        }

                        Item { Layout.fillWidth: true }

                        Rectangle {
                            height: 34
                            implicitWidth: schedViewRoot.width < 450 ? 34 : (newBtnRow2.implicitWidth + 20)
                            radius: 8
                            color: newSchedMouse2.containsMouse ? "#4338CA" : "#4F46E5"
                            border.color: newSchedMouse2.containsMouse ? "#A5B4FC" : "#818CF8"
                            border.width: 1
                            scale: newSchedMouse2.pressed ? 0.92 : (newSchedMouse2.containsMouse ? 1.04 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                            Row {
                                id: newBtnRow2
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "➕"; font.pixelSize: 11; color: "#FFFFFF"; anchors.verticalCenter: parent.verticalCenter }
                                Text {
                                    visible: schedViewRoot.width >= 450
                                    text: schedViewRoot.tr("scheduler_btn_new", "New Schedule")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: Font.Bold
                                    color: "#FFFFFF"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            MouseArea {
                                id: newSchedMouse2
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse && schedViewRoot.width < 450
                                ToolTip.delay: 200
                                ToolTip.text: schedViewRoot.tr("scheduler_btn_new", "New Schedule")
                                onClicked: schedViewRoot.openScheduleDialog(null)
                            }
                        }
                    }
                }
            }

            // ── 2. Automation Safeguards Card (Responsive Grid + Physics) ───────
            SchedulerSafeguardsCard {
                id: safeguardsSection
                view: schedViewRoot
            }

            // ── 3. Active Schedules Section Header ─────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                opacity: schedViewRoot.entranceStage >= 3 ? 1.0 : 0.0
                transform: Translate {
                    y: schedViewRoot.entranceStage >= 3 ? 0 : 20
                    Behavior on y {
                        SpringAnimation { spring: 4.2; damping: 0.38; mass: 1.0; epsilon: 0.25 }
                    }
                }
                Behavior on opacity { NumberAnimation { duration: 180 } }

                Text {
                    text: schedViewRoot.tr("scheduler_schedules_list_title", "Configured Automation Schedules")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    color: "#E2E8F0"
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Rectangle {
                    height: 18
                    implicitWidth: schedCountText.implicitWidth + 12
                    radius: 9
                    color: "#334155"
                    Text {
                        id: schedCountText
                        anchors.centerIn: parent
                        text: schedViewRoot.schedulesList.length.toString()
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        color: "#94A3B8"
                    }
                }

                Item { Layout.fillWidth: true }
            }

            // ── 4. Schedules Cards List / Empty State ──────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 10

                opacity: schedViewRoot.entranceStage >= 3 ? 1.0 : 0.0
                transform: Translate {
                    y: schedViewRoot.entranceStage >= 3 ? 0 : 20
                    Behavior on y {
                        SpringAnimation { spring: 4.2; damping: 0.38; mass: 1.0; epsilon: 0.25 }
                    }
                }
                Behavior on opacity { NumberAnimation { duration: 180 } }

                // Empty State Card
                Rectangle {
                    visible: schedViewRoot.schedulesList.length === 0
                    Layout.fillWidth: true
                    implicitHeight: 200
                    radius: 10
                    clip: true
                    color: "#0F172A"
                    border.color: "#334155"
                    border.width: 1

                    ColumnLayout {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.margins: 20
                        spacing: 12

                        Text {
                            text: "🕒"
                            font.pixelSize: 36
                            Layout.alignment: Qt.AlignHCenter
                        }

                        Text {
                            text: schedViewRoot.tr("scheduler_empty_title", "No Active Schedules")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#E2E8F0"
                            Layout.alignment: Qt.AlignHCenter
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                        }

                        Text {
                            text: schedViewRoot.tr("scheduler_empty_desc", "Schedule Watchlist syncs (new posts are downloaded) or automatic creator downloads.")
                            font.pixelSize: 12
                            color: "#94A3B8"
                            Layout.alignment: Qt.AlignHCenter
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                        }

                        Rectangle {
                            Layout.alignment: Qt.AlignHCenter
                            height: 34
                            implicitWidth: 140
                            radius: 8
                            color: firstBtnMouse.containsMouse ? "#4338CA" : "#4F46E5"
                            scale: firstBtnMouse.pressed ? 0.93 : (firstBtnMouse.containsMouse ? 1.04 : 1.0)
                            Behavior on scale {
                                SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 }
                            }
                            Behavior on color { ColorAnimation { duration: 120 } }

                            Text {
                                anchors.centerIn: parent
                                text: schedViewRoot.tr("scheduler_btn_create_first", "Add Schedule")
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                id: firstBtnMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: schedViewRoot.openScheduleDialog(null)
                            }
                        }
                    }
                }

                // Schedule Cards Repeater
                Repeater {
                    model: schedViewRoot.schedulesList

                    delegate: Rectangle {
                        id: schedCard
                        required property var modelData
                        required property int index
                        readonly property var view: schedViewRoot
                        Layout.fillWidth: true
                        implicitHeight: Math.max(76, cardRow.implicitHeight + 24)
                        radius: 10
                        clip: true
                        color: modelData.enabled ? (cardHover.hovered ? "#243044" : "#1E293B") : "#0F172A"
                        border.color: cardHover.hovered ? "#818CF8" : (modelData.enabled ? "#334155" : "#1E293B")
                        border.width: 1

                        transform: Translate {
                            y: cardHover.hovered && !schedViewRoot.isScrolling ? -3.0 : 0
                            Behavior on y {
                                SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.9; epsilon: 0.1 }
                            }
                        }
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        HoverHandler { id: cardHover }

                        RowLayout {
                            id: cardRow
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 12

                            // Target Type Icon Badge with Spring Scale
                            Rectangle {
                                width: 42; height: 42; radius: 8
                                color: modelData.target_type === "watchlist" ? "#2E1065" : "#0C4A6E"
                                border.color: modelData.target_type === "watchlist" ? "#A855F7" : "#0284C7"
                                border.width: 1.2

                                scale: cardHover.hovered && !schedViewRoot.isScrolling ? 1.08 : 1.0
                                Behavior on scale {
                                    SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 }
                                }

                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.target_type === "watchlist" ? "⭐" : "🌐"
                                    font.pixelSize: 18
                                }
                            }

                            // Details Column (Responsive Flow for Metadata Tags)
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 4

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: 8

                                    Text {
                                        text: modelData.name || (modelData.target_type === "watchlist" ? "Watchlist Sync" : "Creator Download")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 13
                                        font.weight: Font.Bold
                                        color: modelData.enabled ? "#F8FAFC" : "#94A3B8"
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }

                                    // Target pill
                                    Rectangle {
                                        height: 18
                                        implicitWidth: targetLabel.implicitWidth + 12
                                        radius: 4
                                        color: modelData.target_type === "watchlist" ? "#3B0764" : "#082F49"
                                        Text {
                                            id: targetLabel
                                            anchors.centerIn: parent
                                            text: modelData.target_type === "watchlist" ? "Watchlist" : "Creator"
                                            font.pixelSize: 10
                                            font.weight: 600
                                            color: modelData.target_type === "watchlist" ? "#C084FC" : "#38BDF8"
                                        }
                                    }
                                }

                                // Flow wraps metadata items cleanly on narrow widths / expanded console
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text {
                                        text: modelData.trigger_type === "time_of_day" ?
                                              ("⏰ " + schedViewRoot.tr("scheduler_daily_at", "Daily at") + " " + modelData.time_of_day) :
                                              ("⏱️ " + schedViewRoot.tr("scheduler_every", "Every") + " " + modelData.interval_hours + " " + schedViewRoot.tr("scheduler_hours", "hours"))
                                        font.pixelSize: 11
                                        color: "#CBD5E1"
                                    }

                                    Text { text: "•"; font.pixelSize: 11; color: "#475569" }

                                    Text {
                                        text: modelData.next_run ?
                                              (schedViewRoot.tr("scheduler_next_run", "Next:") + " " + modelData.next_run) :
                                              schedViewRoot.tr("scheduler_next_run_pending", "Next: Pending")
                                        font.pixelSize: 11
                                        color: "#38BDF8"
                                    }

                                    Text { text: "•"; font.pixelSize: 11; color: "#475569" }

                                    Text {
                                        text: modelData.last_run ?
                                              (schedViewRoot.tr("scheduler_last_run", "Last:") + " " + modelData.last_run) :
                                              schedViewRoot.tr("scheduler_never_run", "Never run")
                                        font.pixelSize: 11
                                        color: "#64748B"
                                    }
                                }
                            }

                            // Action Buttons with Newtonian Press-Squish
                            RowLayout {
                                spacing: 8

                                // Immediate Run Button
                                Rectangle {
                                    id: runBtn
                                    width: 32; height: 32; radius: 6
                                    color: runMouse.containsMouse ? "#1E293B" : "#0F172A"
                                    border.color: runMouse.containsMouse ? "#10B981" : "#475569"
                                    border.width: 1

                                    scale: runMouse.pressed ? 0.86 : (runMouse.containsMouse ? 1.12 : 1.0)
                                    Behavior on scale {
                                        SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 }
                                    }
                                    Behavior on border.color { ColorAnimation { duration: 120 } }
                                    Behavior on color { ColorAnimation { duration: 120 } }

                                    Text { anchors.centerIn: parent; text: "▶"; font.pixelSize: 12; color: "#10B981" }

                                    MouseArea {
                                        id: runMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 200
                                        ToolTip.text: schedViewRoot.tr("scheduler_run_now", "Run schedule immediately")
                                        onClicked: {
                                            if (modelData.target_type === "watchlist") {
                                                if (schedViewRoot.bridge) schedViewRoot.bridge.checkWatchlist()
                                                schedViewRoot.showToast(schedViewRoot.tr("toast_running_watchlist", "Checking Watchlist..."))
                                            } else if (modelData.target_url) {
                                                if (schedViewRoot.bridge) {
                                                    schedViewRoot.bridge.currentUrl = modelData.target_url
                                                    schedViewRoot.bridge.startDownload()
                                                }
                                                schedViewRoot.showToast(schedViewRoot.tr("toast_running_creator", "Starting creator download..."))
                                            }
                                        }
                                    }
                                }

                                // Modify / Edit Schedule Button
                                Rectangle {
                                    id: editBtn
                                    width: 32; height: 32; radius: 6
                                    color: editMouse.containsMouse ? "#1E293B" : "#0F172A"
                                    border.color: editMouse.containsMouse ? "#818CF8" : "#475569"
                                    border.width: 1

                                    scale: editMouse.pressed ? 0.86 : (editMouse.containsMouse ? 1.12 : 1.0)
                                    Behavior on scale {
                                        SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 }
                                    }
                                    Behavior on border.color { ColorAnimation { duration: 120 } }
                                    Behavior on color { ColorAnimation { duration: 120 } }

                                    Text { anchors.centerIn: parent; text: "✏️"; font.pixelSize: 12 }

                                    MouseArea {
                                        id: editMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 200
                                        ToolTip.text: schedViewRoot.tr("scheduler_edit_task", "Modify schedule settings")
                                        onClicked: schedViewRoot.openScheduleDialog(modelData)
                                    }
                                }

                                // Toggle Switch
                                StyledSwitch {
                                    checked: modelData.enabled
                                    accentColor: "#38BDF8"
                                    onToggled: function(isChecked) {
                                        if (schedViewRoot.bridge) schedViewRoot.bridge.toggleSchedulerTask(modelData.id, isChecked)
                                    }
                                }

                                // Delete Button
                                Rectangle {
                                    id: delBtn
                                    width: 32; height: 32; radius: 6
                                    color: delMouse.containsMouse ? "#3B181E" : "transparent"
                                    border.color: delMouse.containsMouse ? "#EF4444" : "transparent"
                                    border.width: 1

                                    scale: delMouse.pressed ? 0.86 : (delMouse.containsMouse ? 1.12 : 1.0)
                                    Behavior on scale {
                                        SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 }
                                    }
                                    Behavior on color { ColorAnimation { duration: 120 } }

                                    Text { anchors.centerIn: parent; text: "✖"; font.pixelSize: 12; color: "#EF4444" }

                                    MouseArea {
                                        id: delMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 200
                                        ToolTip.text: schedViewRoot.tr("scheduler_delete_task", "Delete schedule")
                                        onClicked: {
                                            if (schedViewRoot.bridge) {
                                                schedViewRoot.bridge.deleteSchedulerTask(modelData.id)
                                                schedViewRoot.showToast(schedViewRoot.tr("toast_schedule_deleted", "Schedule deleted"))
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
    }

    // ── 5. Add / Modify Schedule Dialog Modal ──────────────────────────────────
    SchedulerAddEditModal {
        id: addDialogModal
        view: schedViewRoot
    }

    // ── Toast Banner (Spring Recoil Entrance) ──────────────────────────────────
    Rectangle {
        id: statusToast
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 24
        implicitWidth: toastLabel.implicitWidth + 36
        height: 36
        radius: 18
        color: "#1E293B"
        border.color: "#818CF8"
        border.width: 1
        opacity: 0.0
        z: 999

        property real offsetY: 20
        transform: Translate {
            y: statusToast.offsetY
            Behavior on y {
                SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85 }
            }
        }

        function show(msg) {
            toastLabel.text = msg
            toastAnim.restart()
        }

        Row {
            anchors.centerIn: parent
            spacing: 8
            Text { text: "✔"; font.pixelSize: 12; color: "#818CF8" }
            Text {
                id: toastLabel
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: "#F8FAFC"
            }
        }

        SequentialAnimation {
            id: toastAnim
            ParallelAnimation {
                NumberAnimation { target: statusToast; property: "opacity"; to: 1.0; duration: 180; easing.type: Easing.OutCubic }
                PropertyAction { target: statusToast; property: "offsetY"; value: 0 }
            }
            PauseAnimation { duration: 2400 }
            ParallelAnimation {
                NumberAnimation { target: statusToast; property: "opacity"; to: 0.0; duration: 240; easing.type: Easing.InCubic }
                PropertyAction { target: statusToast; property: "offsetY"; value: 20 }
            }
        }
    }
}
