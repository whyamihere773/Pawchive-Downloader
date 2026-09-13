import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

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
        if (task) {
            schedViewRoot.editingScheduleId = task.id || ""
            taskNameInput.text = task.name || ""
            addDialogModal.selectedTarget = task.target_type || "watchlist"
            taskUrlInput.text = task.target_url || ""
            addDialogModal.selectedTrigger = task.trigger_type || "interval"
            intervalSpin.value = task.interval_hours || 6
            timeOfDayInput.text = task.time_of_day || "03:00"
        } else {
            schedViewRoot.editingScheduleId = ""
            taskNameInput.text = ""
            addDialogModal.selectedTarget = "watchlist"
            taskUrlInput.text = ""
            addDialogModal.selectedTrigger = "interval"
            intervalSpin.value = 6
            timeOfDayInput.text = "03:00"
        }
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
                            spacing: 4

                            RowLayout {
                                spacing: 10
                                Text {
                                    text: schedViewRoot.tr("scheduler_title", "Task Scheduler & Automation Hub")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 17
                                    font.weight: Font.Bold
                                    color: "#F8FAFC"
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
                                text: schedViewRoot.tr("scheduler_subtitle", "Automate Watchlist delta checks, creator backups, off-peak windows, and safeguard connection limits.")
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
                            implicitWidth: newBtnRow2.implicitWidth + 20
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
                                onClicked: schedViewRoot.openScheduleDialog(null)
                            }
                        }
                    }
                }
            }

            // ── 2. Automation Safeguards Card (Responsive Grid + Physics) ───────
            Rectangle {
                id: safeguardsSection
                Layout.fillWidth: true
                implicitHeight: safeguardsLayout.implicitHeight + 24
                radius: 10
                color: "#0F172A"
                border.color: "#334155"
                border.width: 1

                opacity: schedViewRoot.entranceStage >= 2 ? 1.0 : 0.0
                transform: Translate {
                    y: schedViewRoot.entranceStage >= 2 ? 0 : 20
                    Behavior on y {
                        SpringAnimation { spring: 4.2; damping: 0.38; mass: 1.0; epsilon: 0.25 }
                    }
                }
                Behavior on opacity { NumberAnimation { duration: 180 } }

                ColumnLayout {
                    id: safeguardsLayout
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text { text: "🛡️"; font.pixelSize: 15 }
                        Text {
                            text: schedViewRoot.tr("scheduler_safeguards_title", "Automation Safeguards & Global Rules")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 13
                            font.weight: Font.Bold
                            color: "#E2E8F0"
                        }
                    }

                    // Responsive Grid of 4 safeguards (Collapses to 1 column when console is open)
                    GridLayout {
                        Layout.fillWidth: true
                        columns: schedViewRoot.width > 680 ? 2 : 1
                        rowSpacing: 10
                        columnSpacing: 14

                        // Safeguard 1: User-Locked Threads & Delay Mode (Shows Full Title + Uncut Badges)
                        Rectangle {
                            id: safe1Card
                            Layout.fillWidth: true
                            implicitHeight: Math.max(68, safe1Row.implicitHeight + 20)
                            radius: 8
                            color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerLockThreadsDelay) ? "#1E1B4B" : "#1E293B"
                            border.color: safe1Hover.hovered ? "#A5B4FC" : ((schedViewRoot.bridge && schedViewRoot.bridge.schedulerLockThreadsDelay) ? "#818CF8" : "#334155")
                            border.width: 1

                            transform: Translate {
                                y: safe1Hover.hovered && !schedViewRoot.isScrolling ? -2.5 : 0
                                Behavior on y {
                                    SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                                }
                            }
                            Behavior on border.color { ColorAnimation { duration: 140 } }
                            Behavior on color { ColorAnimation { duration: 140 } }

                            HoverHandler { id: safe1Hover }

                            RowLayout {
                                id: safe1Row
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 10

                                Rectangle {
                                    width: 36; height: 36; radius: 6
                                    color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerLockThreadsDelay) ? "#312E81" : "#0F172A"
                                    scale: safe1Hover.hovered && !schedViewRoot.isScrolling ? 1.12 : 1.0
                                    Behavior on scale {
                                        SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 }
                                    }
                                    Text { anchors.centerIn: parent; text: "🔒"; font.pixelSize: 17 }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4

                                    // Flow allows badges to wrap below title cleanly when space is tight
                                    Flow {
                                        Layout.fillWidth: true
                                        spacing: 6

                                        Text {
                                            text: schedViewRoot.tr("scheduler_lock_threads_title", "Lock Custom Threads & Delay")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 12
                                            font.weight: Font.Bold
                                            color: "#F8FAFC"
                                        }

                                        // Values Badges: Sized to entire row with comfortable padding (never cut off!)
                                        Rectangle {
                                            height: 20
                                            implicitWidth: threadsRow.implicitWidth + 14
                                            radius: 4
                                            color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerLockThreadsDelay) ? "#312E81" : "#0F172A"
                                            border.color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerLockThreadsDelay) ? "#818CF8" : "#334155"
                                            border.width: 1

                                            Row {
                                                id: threadsRow
                                                anchors.centerIn: parent
                                                spacing: 4
                                                Text { text: "⚡"; font.pixelSize: 9 }
                                                Text {
                                                    id: threadsValText
                                                    text: (schedViewRoot.bridge ? schedViewRoot.bridge.threadsCount : 4) + " threads"
                                                    font.pixelSize: 10
                                                    font.weight: 600
                                                    color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerLockThreadsDelay) ? "#C7D2FE" : "#94A3B8"
                                                }
                                            }
                                        }

                                        Rectangle {
                                            height: 20
                                            implicitWidth: delayRow.implicitWidth + 14
                                            radius: 4
                                            color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerLockThreadsDelay) ? "#312E81" : "#0F172A"
                                            border.color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerLockThreadsDelay) ? "#818CF8" : "#334155"
                                            border.width: 1

                                            Row {
                                                id: delayRow
                                                anchors.centerIn: parent
                                                spacing: 4
                                                Text { text: "⏱️"; font.pixelSize: 9 }
                                                Text {
                                                    id: delayValText
                                                    text: (schedViewRoot.bridge ? schedViewRoot.bridge.downloadDelay : 0) + "s delay"
                                                    font.pixelSize: 10
                                                    font.weight: 600
                                                    color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerLockThreadsDelay) ? "#C7D2FE" : "#94A3B8"
                                                }
                                            }
                                        }
                                    }

                                    Text {
                                        text: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerLockThreadsDelay) ?
                                              (schedViewRoot.tr("scheduler_locked_values_desc", "Locked at: ") + (schedViewRoot.bridge ? schedViewRoot.bridge.threadsCount : 4) + " threads • " + (schedViewRoot.bridge ? schedViewRoot.bridge.downloadDelay : 0) + "s delay") :
                                              schedViewRoot.tr("scheduler_lock_threads_desc", "Preserves your exact settings without auto-override")
                                        font.pixelSize: 11
                                        color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerLockThreadsDelay) ? "#A5B4FC" : "#94A3B8"
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }

                                StyledSwitch {
                                    checked: schedViewRoot.bridge ? schedViewRoot.bridge.schedulerLockThreadsDelay : false
                                    accentColor: "#F87171"
                                    onToggled: function(isChecked) {
                                        schedViewRoot.saveGlobalSettings(undefined, isChecked, undefined, undefined, undefined, undefined, undefined)
                                        schedViewRoot.showToast(isChecked ? schedViewRoot.tr("toast_threads_locked", "Thread & delay settings locked") : schedViewRoot.tr("toast_threads_unlocked", "Adaptive concurrency allowed"))
                                    }
                                }
                            }
                        }

                        // Safeguard 2: Night Owl Off-Peak Window (Redesigned Active Window Pill)
                        Rectangle {
                            id: safe2Card
                            Layout.fillWidth: true
                            implicitHeight: Math.max(76, safe2Row.implicitHeight + 24)
                            radius: 8
                            color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#042F2E" : "#1E293B"
                            border.color: safe2Hover.hovered ? "#5EEAD4" : ((schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#14B8A6" : "#334155")
                            border.width: 1

                            transform: Translate {
                                y: safe2Hover.hovered && !schedViewRoot.isScrolling ? -2.5 : 0
                                Behavior on y {
                                    SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                                }
                            }
                            Behavior on border.color { ColorAnimation { duration: 140 } }
                            Behavior on color { ColorAnimation { duration: 140 } }

                            HoverHandler { id: safe2Hover }

                            RowLayout {
                                id: safe2Row
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 10

                                Rectangle {
                                    width: 36; height: 36; radius: 6
                                    color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#134E4A" : "#0F172A"
                                    scale: safe2Hover.hovered && !schedViewRoot.isScrolling ? 1.12 : 1.0
                                    Behavior on scale {
                                        SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 }
                                    }
                                    Text { anchors.centerIn: parent; text: "🌙"; font.pixelSize: 17 }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    RowLayout {
                                        spacing: 8
                                        Text {
                                            text: schedViewRoot.tr("scheduler_night_owl_title", "Night Owl Off-Peak Window")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 12
                                            font.weight: Font.Bold
                                            color: "#F8FAFC"
                                        }

                                        Rectangle {
                                            height: 18
                                            implicitWidth: nightOwlBadgeText.implicitWidth + 12
                                            radius: 4
                                            color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#134E4A" : "#1E293B"
                                            border.color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#2DD4BF" : "#334155"
                                            border.width: 1
                                            Text {
                                                id: nightOwlBadgeText
                                                anchors.centerIn: parent
                                                text: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "Active" : "Disabled"
                                                font.pixelSize: 10
                                                font.weight: 600
                                                color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#5EEAD4" : "#94A3B8"
                                            }
                                        }
                                    }

                                    // Sleek Modern Time Window Pill with Taller Inputs (Never Cut Off)
                                    Rectangle {
                                        height: 32
                                        implicitWidth: timePillRow.implicitWidth + 20
                                        radius: 6
                                        color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#042528" : "#0F172A"
                                        border.color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#14B8A6" : "#334155"
                                        border.width: 1

                                        RowLayout {
                                            id: timePillRow
                                            anchors.centerIn: parent
                                            spacing: 8

                                            Text {
                                                text: "⏰ " + schedViewRoot.tr("scheduler_night_owl_window_label", "Window:")
                                                font.pixelSize: 11
                                                font.weight: 600
                                                color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#5EEAD4" : "#94A3B8"
                                            }

                                            TextField {
                                                id: nightStartInput
                                                text: schedViewRoot.bridge ? schedViewRoot.bridge.schedulerNightOwlStart : "01:00"
                                                font.pixelSize: 12
                                                font.weight: Font.Bold
                                                Layout.preferredWidth: 56
                                                Layout.preferredHeight: 24
                                                verticalAlignment: TextInput.AlignVCenter
                                                horizontalAlignment: TextInput.AlignHCenter
                                                padding: 0
                                                topPadding: 0
                                                bottomPadding: 0
                                                background: Rectangle {
                                                    color: nightStartInput.activeFocus ? "#115E59" : ((schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#0A3B3E" : "#1E293B")
                                                    radius: 4
                                                    border.color: nightStartInput.activeFocus ? "#2DD4BF" : ((schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#14B8A6" : "#475569")
                                                }
                                                color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#5EEAD4" : "#E2E8F0"
                                                selectByMouse: true
                                                onEditingFinished: {
                                                    schedViewRoot.saveGlobalSettings(undefined, undefined, undefined, text, nightEndInput.text, undefined, undefined)
                                                }
                                            }

                                            Text {
                                                text: "→"
                                                font.pixelSize: 12
                                                font.weight: Font.Bold
                                                color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#2DD4BF" : "#64748B"
                                            }

                                            TextField {
                                                id: nightEndInput
                                                text: schedViewRoot.bridge ? schedViewRoot.bridge.schedulerNightOwlEnd : "07:00"
                                                font.pixelSize: 12
                                                font.weight: Font.Bold
                                                Layout.preferredWidth: 56
                                                Layout.preferredHeight: 24
                                                verticalAlignment: TextInput.AlignVCenter
                                                horizontalAlignment: TextInput.AlignHCenter
                                                padding: 0
                                                topPadding: 0
                                                bottomPadding: 0
                                                background: Rectangle {
                                                    color: nightEndInput.activeFocus ? "#115E59" : ((schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#0A3B3E" : "#1E293B")
                                                    radius: 4
                                                    border.color: nightEndInput.activeFocus ? "#2DD4BF" : ((schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#14B8A6" : "#475569")
                                                }
                                                color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerNightOwlEnabled) ? "#5EEAD4" : "#E2E8F0"
                                                selectByMouse: true
                                                onEditingFinished: {
                                                    schedViewRoot.saveGlobalSettings(undefined, undefined, undefined, nightStartInput.text, text, undefined, undefined)
                                                }
                                            }
                                        }
                                    }
                                }


                                StyledSwitch {
                                    checked: schedViewRoot.bridge ? schedViewRoot.bridge.schedulerNightOwlEnabled : false
                                    accentColor: "#14B8A6"
                                    onToggled: function(isChecked) {
                                        schedViewRoot.saveGlobalSettings(undefined, undefined, isChecked, nightStartInput.text, nightEndInput.text, undefined, undefined)
                                        schedViewRoot.showToast(isChecked ? schedViewRoot.tr("toast_night_owl_on", "Night Owl window enabled") : schedViewRoot.tr("toast_night_owl_off", "Night Owl window disabled"))
                                    }
                                }
                            }
                        }

                        // Safeguard 3: Windows Sleep Prevention
                        Rectangle {
                            id: safe3Card
                            Layout.fillWidth: true
                            implicitHeight: Math.max(68, safe3Row.implicitHeight + 20)
                            radius: 8
                            color: "#1E293B"
                            border.color: safe3Hover.hovered ? "#7DD3FC" : ((schedViewRoot.bridge && schedViewRoot.bridge.schedulerPreventSleep) ? "#38BDF8" : "#334155")
                            border.width: 1

                            transform: Translate {
                                y: safe3Hover.hovered && !schedViewRoot.isScrolling ? -2.5 : 0
                                Behavior on y {
                                    SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                                }
                            }
                            Behavior on border.color { ColorAnimation { duration: 140 } }

                            HoverHandler { id: safe3Hover }

                            RowLayout {
                                id: safe3Row
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 10

                                Rectangle {
                                    width: 36; height: 36; radius: 6
                                    color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerPreventSleep) ? "#0369A1" : "#0F172A"
                                    scale: safe3Hover.hovered && !schedViewRoot.isScrolling ? 1.12 : 1.0
                                    Behavior on scale {
                                        SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 }
                                    }
                                    Text { anchors.centerIn: parent; text: "⚡"; font.pixelSize: 17 }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: schedViewRoot.tr("scheduler_prevent_sleep_title", "Windows Sleep Prevention")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 12
                                        font.weight: Font.Bold
                                        color: "#F8FAFC"
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: schedViewRoot.tr("scheduler_prevent_sleep_desc", "Keeps PC awake via Windows kernel while downloading")
                                        font.pixelSize: 11
                                        color: "#94A3B8"
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }

                                StyledSwitch {
                                    checked: schedViewRoot.bridge ? schedViewRoot.bridge.schedulerPreventSleep : true
                                    accentColor: "#38BDF8"
                                    onToggled: function(isChecked) {
                                        schedViewRoot.saveGlobalSettings(undefined, undefined, undefined, undefined, undefined, isChecked, undefined)
                                        schedViewRoot.showToast(isChecked ? schedViewRoot.tr("toast_sleep_prevent_on", "Sleep prevention enabled") : schedViewRoot.tr("toast_sleep_prevent_off", "Sleep prevention disabled"))
                                    }
                                }
                            }
                        }

                        // Safeguard 4: Post-Run Sweep Auto-Retry
                        Rectangle {
                            id: safe4Card
                            Layout.fillWidth: true
                            implicitHeight: Math.max(68, safe4Row.implicitHeight + 20)
                            radius: 8
                            color: "#1E293B"
                            border.color: safe4Hover.hovered ? "#D8B4FE" : ((schedViewRoot.bridge && schedViewRoot.bridge.schedulerSweepRetry) ? "#A855F7" : "#334155")
                            border.width: 1

                            transform: Translate {
                                y: safe4Hover.hovered && !schedViewRoot.isScrolling ? -2.5 : 0
                                Behavior on y {
                                    SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                                }
                            }
                            Behavior on border.color { ColorAnimation { duration: 140 } }

                            HoverHandler { id: safe4Hover }

                            RowLayout {
                                id: safe4Row
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 10

                                Rectangle {
                                    width: 36; height: 36; radius: 6
                                    color: (schedViewRoot.bridge && schedViewRoot.bridge.schedulerSweepRetry) ? "#581C87" : "#0F172A"
                                    scale: safe4Hover.hovered && !schedViewRoot.isScrolling ? 1.12 : 1.0
                                    Behavior on scale {
                                        SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 }
                                    }
                                    Text { anchors.centerIn: parent; text: "🔄"; font.pixelSize: 17 }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: schedViewRoot.tr("scheduler_sweep_retry_title", "Sweep Auto-Retry Pass")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 12
                                        font.weight: Font.Bold
                                        color: "#F8FAFC"
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: schedViewRoot.tr("scheduler_sweep_retry_desc", "Automatically retries any missed 429/timeout files")
                                        font.pixelSize: 11
                                        color: "#94A3B8"
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }

                                StyledSwitch {
                                    checked: schedViewRoot.bridge ? schedViewRoot.bridge.schedulerSweepRetry : true
                                    accentColor: "#A855F7"
                                    onToggled: function(isChecked) {
                                        schedViewRoot.saveGlobalSettings(undefined, undefined, undefined, undefined, undefined, undefined, isChecked)
                                        schedViewRoot.showToast(isChecked ? schedViewRoot.tr("toast_sweep_on", "Sweep retry enabled") : schedViewRoot.tr("toast_sweep_off", "Sweep retry disabled"))
                                    }
                                }
                            }
                        }
                    }
                }
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
                    color: "#0F172A"
                    border.color: "#334155"
                    border.width: 1

                    ColumnLayout {
                        anchors.centerIn: parent
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
                        }

                        Text {
                            text: schedViewRoot.tr("scheduler_empty_desc", "Create recurring delta checks for your Watchlist or schedule automatic creator downloads.")
                            font.pixelSize: 12
                            color: "#94A3B8"
                            Layout.alignment: Qt.AlignHCenter
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
                                spacing: 4

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text {
                                        text: modelData.name || (modelData.target_type === "watchlist" ? "Watchlist Delta Sync" : "Creator Download")
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
    Rectangle {
        id: addDialogModal
        visible: opacity > 0.001
        opacity: schedViewRoot.showAddDialog ? 1.0 : 0.0
        anchors.fill: parent
        color: "#B3000000"
        z: 900

        property string selectedTarget: "watchlist"
        property string selectedTrigger: "interval"

        Behavior on opacity {
            NumberAnimation { duration: 180; easing.type: Easing.OutQuad }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: { /* block clicks outside */ }
        }

        Rectangle {
            id: modalBox
            anchors.centerIn: parent
            width: Math.min(parent.width - 40, 520)
            implicitHeight: addDialogCol.implicitHeight + 36
            radius: 12
            color: "#0F172A"
            border.color: "#334155"
            border.width: 1.5

            scale: schedViewRoot.showAddDialog ? 1.0 : 0.90
            transform: Translate {
                y: schedViewRoot.showAddDialog ? 0 : -22
                Behavior on y {
                    SpringAnimation { spring: 4.5; damping: 0.38; mass: 1.0 }
                }
            }
            Behavior on scale {
                SpringAnimation { spring: 4.5; damping: 0.38; mass: 1.0 }
            }

            ColumnLayout {
                id: addDialogCol
                anchors.fill: parent
                anchors.margins: 20
                spacing: 16

                // Modal Header
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text { text: schedViewRoot.editingScheduleId ? "✏️" : "⏰"; font.pixelSize: 18 }
                    Text {
                        text: schedViewRoot.editingScheduleId ?
                              schedViewRoot.tr("scheduler_modal_edit_title", "Modify Automation Schedule") :
                              schedViewRoot.tr("scheduler_modal_title", "Create Automation Schedule")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        width: 28; height: 28; radius: 14; color: closeMouse.containsMouse ? "#334155" : "transparent"
                        scale: closeMouse.pressed ? 0.88 : (closeMouse.containsMouse ? 1.1 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                        Text { anchors.centerIn: parent; text: "✖"; font.pixelSize: 12; color: "#94A3B8" }
                        MouseArea {
                            id: closeMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: schedViewRoot.showAddDialog = false
                        }
                    }
                }

                // Schedule Name Input
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text: schedViewRoot.tr("scheduler_modal_name_label", "Schedule Name")
                        font.pixelSize: 11; font.weight: 600; color: "#CBD5E1"
                    }
                    TextField {
                        id: taskNameInput
                        Layout.fillWidth: true
                        Layout.preferredHeight: 34
                        placeholderText: schedViewRoot.tr("scheduler_modal_name_placeholder", "e.g., Nightly Watchlist Sync")
                        color: "#F8FAFC"
                        placeholderTextColor: "#64748B"
                        font.pixelSize: 12
                        background: Rectangle { color: "#1E293B"; radius: 6; border.color: taskNameInput.activeFocus ? "#818CF8" : "#334155" }
                    }
                }

                // Target Type Switcher
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Text {
                        text: schedViewRoot.tr("scheduler_modal_target_label", "Target Action")
                        font.pixelSize: 11; font.weight: 600; color: "#CBD5E1"
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        // Watchlist Option
                        Rectangle {
                            Layout.fillWidth: true
                            height: 38
                            radius: 6
                            color: addDialogModal.selectedTarget === "watchlist" ? "#2E1065" : "#1E293B"
                            border.color: addDialogModal.selectedTarget === "watchlist" ? "#A855F7" : "#334155"
                            border.width: 1

                            scale: watchOptMouse.pressed ? 0.96 : (watchOptMouse.containsMouse ? 1.02 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            Row {
                                anchors.centerIn: parent
                                spacing: 8
                                Text { text: "⭐"; font.pixelSize: 12 }
                                Text {
                                    text: schedViewRoot.tr("scheduler_target_watchlist", "Watchlist Delta Check")
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: addDialogModal.selectedTarget === "watchlist" ? "#F8FAFC" : "#94A3B8"
                                }
                            }
                            MouseArea {
                                id: watchOptMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: addDialogModal.selectedTarget = "watchlist"
                            }
                        }

                        // Creator Option
                        Rectangle {
                            Layout.fillWidth: true
                            height: 38
                            radius: 6
                            color: addDialogModal.selectedTarget === "creator" ? "#0C4A6E" : "#1E293B"
                            border.color: addDialogModal.selectedTarget === "creator" ? "#0284C7" : "#334155"
                            border.width: 1

                            scale: creatOptMouse.pressed ? 0.96 : (creatOptMouse.containsMouse ? 1.02 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            Row {
                                anchors.centerIn: parent
                                spacing: 8
                                Text { text: "🌐"; font.pixelSize: 12 }
                                Text {
                                    text: schedViewRoot.tr("scheduler_target_creator", "Specific Creator URL")
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: addDialogModal.selectedTarget === "creator" ? "#F8FAFC" : "#94A3B8"
                                }
                            }
                            MouseArea {
                                id: creatOptMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: addDialogModal.selectedTarget = "creator"
                            }
                        }
                    }
                }

                // Creator URL Input (Visible only if creator target chosen)
                ColumnLayout {
                    id: creatorUrlSection
                    visible: addDialogModal.selectedTarget === "creator"
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text: schedViewRoot.tr("scheduler_modal_url_label", "Creator Page URL")
                        font.pixelSize: 11; font.weight: 600; color: "#CBD5E1"
                    }
                    TextField {
                        id: taskUrlInput
                        Layout.fillWidth: true
                        Layout.preferredHeight: 34
                        placeholderText: "https://kemono.su/patreon/user/12345"
                        color: "#F8FAFC"
                        placeholderTextColor: "#64748B"
                        font.pixelSize: 12
                        background: Rectangle { color: "#1E293B"; radius: 6; border.color: taskUrlInput.activeFocus ? "#38BDF8" : "#334155" }
                    }
                }

                // Cadence Trigger Type
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: schedViewRoot.tr("scheduler_modal_trigger_label", "Trigger Schedule")
                        font.pixelSize: 11; font.weight: 600; color: "#CBD5E1"
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        // Interval Option
                        Rectangle {
                            Layout.fillWidth: true
                            height: 34
                            radius: 6
                            color: addDialogModal.selectedTrigger === "interval" ? "#1E1B4B" : "#1E293B"
                            border.color: addDialogModal.selectedTrigger === "interval" ? "#818CF8" : "#334155"
                            border.width: 1

                            scale: intOptMouse.pressed ? 0.96 : (intOptMouse.containsMouse ? 1.02 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "⏱️"; font.pixelSize: 11 }
                                Text {
                                    text: schedViewRoot.tr("scheduler_trigger_interval", "Repeating Interval")
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: addDialogModal.selectedTrigger === "interval" ? "#F8FAFC" : "#94A3B8"
                                }
                            }
                            MouseArea {
                                id: intOptMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: addDialogModal.selectedTrigger = "interval"
                            }
                        }

                        // Time of Day Option
                        Rectangle {
                            Layout.fillWidth: true
                            height: 34
                            radius: 6
                            color: addDialogModal.selectedTrigger === "time_of_day" ? "#1E1B4B" : "#1E293B"
                            border.color: addDialogModal.selectedTrigger === "time_of_day" ? "#818CF8" : "#334155"
                            border.width: 1

                            scale: timeOptMouse.pressed ? 0.96 : (timeOptMouse.containsMouse ? 1.02 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "⏰"; font.pixelSize: 11 }
                                Text {
                                    text: schedViewRoot.tr("scheduler_trigger_fixed", "Daily Fixed Time")
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: addDialogModal.selectedTrigger === "time_of_day" ? "#F8FAFC" : "#94A3B8"
                                }
                            }
                            MouseArea {
                                id: timeOptMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: addDialogModal.selectedTrigger = "time_of_day"
                            }
                        }
                    }

                    // Interval Hours Selector
                    RowLayout {
                        visible: addDialogModal.selectedTrigger === "interval"
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: schedViewRoot.tr("scheduler_every_hours", "Run every:")
                            font.pixelSize: 12; color: "#CBD5E1"
                        }

                        StyledSpinBox {
                            id: intervalSpin
                            from: 1; to: 72; value: 6; stepSize: 1
                            suffix: " hrs"
                            accentColor: "#38BDF8"
                            implicitWidth: 130
                        }

                        Text {
                            text: schedViewRoot.tr("scheduler_hours_unit", "hours")
                            font.pixelSize: 12; color: "#94A3B8"
                        }
                    }

                    // Daily Fixed Time Selector
                    RowLayout {
                        visible: addDialogModal.selectedTrigger === "time_of_day"
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: schedViewRoot.tr("scheduler_at_time", "Run daily at:")
                            font.pixelSize: 12; color: "#CBD5E1"
                        }

                        TextField {
                            id: timeOfDayInput
                            text: "03:00"
                            Layout.preferredWidth: 70
                            Layout.preferredHeight: 30
                            horizontalAlignment: TextInput.AlignHCenter
                            font.pixelSize: 12
                            color: "#38BDF8"
                            background: Rectangle { color: "#1E293B"; radius: 4; border.color: "#334155" }
                        }

                        Text {
                            text: "(24h format HH:MM)"
                            font.pixelSize: 11; color: "#64748B"
                        }
                    }
                }

                // Modal Action Buttons
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Item { Layout.fillWidth: true }

                    // Cancel Button
                    Rectangle {
                        height: 36
                        implicitWidth: 84
                        radius: 8
                        color: cancelMouse.containsMouse ? "#334155" : "#1E293B"
                        border.color: "#475569"; border.width: 1

                        scale: cancelMouse.pressed ? 0.94 : (cancelMouse.containsMouse ? 1.02 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                        Behavior on color { ColorAnimation { duration: 120 } }

                        Text {
                            anchors.centerIn: parent
                            text: schedViewRoot.tr("btn_cancel", "Cancel")
                            font.pixelSize: 12
                            color: "#E2E8F0"
                        }
                        MouseArea {
                            id: cancelMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: schedViewRoot.showAddDialog = false
                        }
                    }

                    // Save / Update Schedule Button
                    Rectangle {
                        height: 36
                        implicitWidth: 140
                        radius: 8
                        color: createBtnMouse.containsMouse ? "#4338CA" : "#4F46E5"
                        border.color: createBtnMouse.containsMouse ? "#A5B4FC" : "#818CF8"
                        border.width: 1

                        scale: createBtnMouse.pressed ? 0.94 : (createBtnMouse.containsMouse ? 1.04 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 120 } }

                        Text {
                            anchors.centerIn: parent
                            text: schedViewRoot.editingScheduleId ?
                                  schedViewRoot.tr("scheduler_modal_update_btn", "Update Schedule") :
                                  schedViewRoot.tr("scheduler_modal_create_btn", "Save Schedule")
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }

                        MouseArea {
                            id: createBtnMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var name = taskNameInput.text.trim() || (addDialogModal.selectedTarget === "watchlist" ? "Watchlist Delta Sync" : "Creator Download")
                                var targetType = addDialogModal.selectedTarget
                                var targetUrl = targetType === "creator" ? taskUrlInput.text.trim() : ""
                                var triggerType = addDialogModal.selectedTrigger
                                var intervalH = intervalSpin.value
                                var timeVal = timeOfDayInput.text.trim() || "03:00"

                                if (schedViewRoot.bridge) {
                                    if (schedViewRoot.editingScheduleId) {
                                        schedViewRoot.bridge.updateSchedulerTask(schedViewRoot.editingScheduleId, name, targetType, targetUrl, triggerType, intervalH, timeVal)
                                        schedViewRoot.showToast(schedViewRoot.tr("toast_schedule_updated", "Schedule updated successfully!"))
                                    } else {
                                        schedViewRoot.bridge.addSchedulerTask(name, targetType, targetUrl, triggerType, intervalH, timeVal)
                                        schedViewRoot.showToast(schedViewRoot.tr("toast_schedule_created", "Schedule created successfully!"))
                                    }
                                }
                                schedViewRoot.showAddDialog = false
                                schedViewRoot.editingScheduleId = ""
                                taskNameInput.text = ""
                                taskUrlInput.text = ""
                            }
                        }
                    }
                }
            }
        }
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
