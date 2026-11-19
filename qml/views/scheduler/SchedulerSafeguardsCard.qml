import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// Automation Safeguards & Global Rules card (locked threads, Night Owl, sleep prevention, sweep retry).
Rectangle {
    id: safeguardsSection

    required property var view
    Layout.fillWidth: true
    implicitHeight: safeguardsLayout.implicitHeight + 24
    radius: 10
    color: "#0F172A"
    border.color: "#334155"
    border.width: 1

    opacity: view.entranceStage >= 2 ? 1.0 : 0.0
    transform: Translate {
        y: view.entranceStage >= 2 ? 0 : 20
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
                text: view.tr("scheduler_safeguards_title", "Automation Safeguards & Global Rules")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 13
                font.weight: Font.Bold
                color: "#E2E8F0"
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        // Responsive Grid of 4 safeguards (Collapses to 1 column when console is open)
        GridLayout {
            Layout.fillWidth: true
            columns: view.width > 680 ? 2 : 1
            rowSpacing: 10
            columnSpacing: 14

            // Safeguard 1: User-Locked Threads & Delay Mode (Shows Full Title + Uncut Badges)
            Rectangle {
                id: safe1Card
                Layout.fillWidth: true
                implicitHeight: Math.max(68, safe1Row.implicitHeight + 20)
                radius: 8
                clip: true
                color: (view.bridge && view.bridge.schedulerLockThreadsDelay) ? "#1E1B4B" : "#1E293B"
                border.color: safe1Hover.hovered ? "#A5B4FC" : ((view.bridge && view.bridge.schedulerLockThreadsDelay) ? "#818CF8" : "#334155")
                border.width: 1

                transform: Translate {
                    y: safe1Hover.hovered && !view.isScrolling ? -2.5 : 0
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
                        color: (view.bridge && view.bridge.schedulerLockThreadsDelay) ? "#312E81" : "#0F172A"
                        scale: safe1Hover.hovered && !view.isScrolling ? 1.12 : 1.0
                        Behavior on scale {
                            SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 }
                        }
                        Text { anchors.centerIn: parent; text: "🔒"; font.pixelSize: 17 }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 4

                        // Flow allows badges to wrap below title cleanly when space is tight
                        Flow {
                            Layout.fillWidth: true
                            spacing: 6

                            Text {
                                text: view.tr("scheduler_lock_threads_title", "Lock Custom Threads & Delay")
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
                                color: (view.bridge && view.bridge.schedulerLockThreadsDelay) ? "#312E81" : "#0F172A"
                                border.color: (view.bridge && view.bridge.schedulerLockThreadsDelay) ? "#818CF8" : "#334155"
                                border.width: 1

                                Row {
                                    id: threadsRow
                                    anchors.centerIn: parent
                                    spacing: 4
                                    Text { text: "⚡"; font.pixelSize: 9 }
                                    Text {
                                        id: threadsValText
                                        text: (view.bridge ? view.bridge.threadsCount : 4) + " threads"
                                        font.pixelSize: 10
                                        font.weight: 600
                                        color: (view.bridge && view.bridge.schedulerLockThreadsDelay) ? "#C7D2FE" : "#94A3B8"
                                    }
                                }
                            }

                            Rectangle {
                                height: 20
                                implicitWidth: delayRow.implicitWidth + 14
                                radius: 4
                                color: (view.bridge && view.bridge.schedulerLockThreadsDelay) ? "#312E81" : "#0F172A"
                                border.color: (view.bridge && view.bridge.schedulerLockThreadsDelay) ? "#818CF8" : "#334155"
                                border.width: 1

                                Row {
                                    id: delayRow
                                    anchors.centerIn: parent
                                    spacing: 4
                                    Text { text: "⏱️"; font.pixelSize: 9 }
                                    Text {
                                        id: delayValText
                                        text: (view.bridge ? view.bridge.downloadDelay : 0) + "s delay"
                                        font.pixelSize: 10
                                        font.weight: 600
                                        color: (view.bridge && view.bridge.schedulerLockThreadsDelay) ? "#C7D2FE" : "#94A3B8"
                                    }
                                }
                            }
                        }

                        Text {
                            text: (view.bridge && view.bridge.schedulerLockThreadsDelay) ?
                                  (view.tr("scheduler_locked_values_desc", "Locked at: ") + (view.bridge ? view.bridge.threadsCount : 4) + " threads • " + (view.bridge ? view.bridge.downloadDelay : 0) + "s delay") :
                                  view.tr("scheduler_lock_threads_desc", "Preserves your exact settings without auto-override")
                            font.pixelSize: 11
                            color: (view.bridge && view.bridge.schedulerLockThreadsDelay) ? "#A5B4FC" : "#94A3B8"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    StyledSwitch {
                        checked: view.bridge ? view.bridge.schedulerLockThreadsDelay : false
                        accentColor: "#F87171"
                        onToggled: function(isChecked) {
                            view.saveGlobalSettings(undefined, isChecked, undefined, undefined, undefined, undefined, undefined)
                            view.showToast(isChecked ? view.tr("toast_threads_locked", "Thread & delay settings locked") : view.tr("toast_threads_unlocked", "Adaptive concurrency allowed"))
                        }
                    }
                }
            }

            // Safeguard 2: Night Owl Off-Peak Window (Redesigned Responsive Window Layout)
            Rectangle {
                id: safe2Card
                Layout.fillWidth: true
                implicitHeight: Math.max(76, safe2Col.implicitHeight + 20)
                radius: 8
                clip: true
                color: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#042F2E" : "#1E293B"
                border.color: safe2Hover.hovered ? "#5EEAD4" : ((view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#14B8A6" : "#334155")
                border.width: 1

                transform: Translate {
                    y: safe2Hover.hovered && !view.isScrolling ? -2.5 : 0
                    Behavior on y {
                        SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                    }
                }
                Behavior on border.color { ColorAnimation { duration: 140 } }
                Behavior on color { ColorAnimation { duration: 140 } }

                HoverHandler { id: safe2Hover }

                ColumnLayout {
                    id: safe2Col
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    // Top Row: Icon + Title & Active Badge + StyledSwitch
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Rectangle {
                            width: 32; height: 32; radius: 6
                            color: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#134E4A" : "#0F172A"
                            scale: safe2Hover.hovered && !view.isScrolling ? 1.12 : 1.0
                            Behavior on scale {
                                SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 }
                            }
                            Text { anchors.centerIn: parent; text: "🌙"; font.pixelSize: 16 }
                        }

                        Flow {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 6
                            Layout.alignment: Qt.AlignVCenter

                            Text {
                                text: view.tr("scheduler_night_owl_title", "Night Owl Off-Peak Window")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                color: "#F8FAFC"
                            }

                            Rectangle {
                                height: 18
                                implicitWidth: nightOwlBadgeText.implicitWidth + 12
                                radius: 4
                                color: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#134E4A" : "#1E293B"
                                border.color: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#2DD4BF" : "#334155"
                                border.width: 1
                                Text {
                                    id: nightOwlBadgeText
                                    anchors.centerIn: parent
                                    text: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "Active" : "Disabled"
                                    font.pixelSize: 10
                                    font.weight: 600
                                    color: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#5EEAD4" : "#94A3B8"
                                }
                            }
                        }

                        StyledSwitch {
                            checked: view.bridge ? view.bridge.schedulerNightOwlEnabled : false
                            accentColor: "#14B8A6"
                            onToggled: function(isChecked) {
                                view.saveGlobalSettings(undefined, undefined, isChecked, nightStartInput.text, nightEndInput.text, undefined, undefined)
                                view.showToast(isChecked ? view.tr("toast_night_owl_on", "Night Owl window enabled") : view.tr("toast_night_owl_off", "Night Owl window disabled"))
                            }
                        }
                    }

                    // What the window does (it only gates when schedules may start)
                    Text {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: view.tr("scheduler_night_owl_hint", "Schedules only start inside this window. A download that's already running keeps going after the window ends.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        wrapMode: Text.WordWrap
                    }

                    // Bottom Row: Sleek Modern Time Window Pill (Spans full available width)
                    Rectangle {
                        height: 30
                        Layout.fillWidth: true
                        Layout.maximumWidth: timePillRow.implicitWidth + 20
                        radius: 6
                        color: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#042528" : "#0F172A"
                        border.color: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#14B8A6" : "#334155"
                        border.width: 1

                        RowLayout {
                            id: timePillRow
                            anchors.centerIn: parent
                            spacing: 6

                            Text {
                                text: "⏰ " + view.tr("scheduler_night_owl_window_label", "Window:")
                                font.pixelSize: 11
                                font.weight: 600
                                color: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#5EEAD4" : "#94A3B8"
                            }

                            TextField {
                                id: nightStartInput
                                text: view.bridge ? view.bridge.schedulerNightOwlStart : "01:00"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                Layout.preferredWidth: 48
                                Layout.preferredHeight: 22
                                verticalAlignment: TextInput.AlignVCenter
                                horizontalAlignment: TextInput.AlignHCenter
                                padding: 0
                                topPadding: 0
                                bottomPadding: 0
                                background: Rectangle {
                                    color: nightStartInput.activeFocus ? "#115E59" : ((view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#0A3B3E" : "#1E293B")
                                    radius: 4
                                    border.color: nightStartInput.activeFocus ? "#2DD4BF" : ((view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#14B8A6" : "#475569")
                                }
                                color: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#5EEAD4" : "#E2E8F0"
                                selectionColor: "#0284C7"
                                selectedTextColor: "#FFFFFF"
                                clip: true
                                selectByMouse: true
                                TextBarContextArea {}
                                onEditingFinished: {
                                    view.saveGlobalSettings(undefined, undefined, undefined, text, nightEndInput.text, undefined, undefined)
                                }
                            }

                            Text {
                                text: "→"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#2DD4BF" : "#64748B"
                            }

                            TextField {
                                id: nightEndInput
                                text: view.bridge ? view.bridge.schedulerNightOwlEnd : "07:00"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                Layout.preferredWidth: 48
                                Layout.preferredHeight: 22
                                verticalAlignment: TextInput.AlignVCenter
                                horizontalAlignment: TextInput.AlignHCenter
                                padding: 0
                                topPadding: 0
                                bottomPadding: 0
                                background: Rectangle {
                                    color: nightEndInput.activeFocus ? "#115E59" : ((view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#0A3B3E" : "#1E293B")
                                    radius: 4
                                    border.color: nightEndInput.activeFocus ? "#2DD4BF" : ((view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#14B8A6" : "#475569")
                                }
                                color: (view.bridge && view.bridge.schedulerNightOwlEnabled) ? "#5EEAD4" : "#E2E8F0"
                                selectionColor: "#0284C7"
                                selectedTextColor: "#FFFFFF"
                                clip: true
                                selectByMouse: true
                                TextBarContextArea {}
                                onEditingFinished: {
                                    view.saveGlobalSettings(undefined, undefined, undefined, nightStartInput.text, text, undefined, undefined)
                                }
                            }
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
                clip: true
                color: "#1E293B"
                border.color: safe3Hover.hovered ? "#7DD3FC" : ((view.bridge && view.bridge.schedulerPreventSleep) ? "#38BDF8" : "#334155")
                border.width: 1

                transform: Translate {
                    y: safe3Hover.hovered && !view.isScrolling ? -2.5 : 0
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
                        color: (view.bridge && view.bridge.schedulerPreventSleep) ? "#0369A1" : "#0F172A"
                        scale: safe3Hover.hovered && !view.isScrolling ? 1.12 : 1.0
                        Behavior on scale {
                            SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 }
                        }
                        Text { anchors.centerIn: parent; text: "⚡"; font.pixelSize: 17 }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 2
                        Text {
                            text: view.tr("scheduler_prevent_sleep_title", "Sleep Prevention")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Text {
                            text: view.tr("scheduler_prevent_sleep_desc", "Keeps the computer awake while downloads are running")
                            font.pixelSize: 11
                            color: "#94A3B8"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    StyledSwitch {
                        checked: view.bridge ? view.bridge.schedulerPreventSleep : true
                        accentColor: "#38BDF8"
                        onToggled: function(isChecked) {
                            view.saveGlobalSettings(undefined, undefined, undefined, undefined, undefined, isChecked, undefined)
                            view.showToast(isChecked ? view.tr("toast_sleep_prevent_on", "Sleep prevention enabled") : view.tr("toast_sleep_prevent_off", "Sleep prevention disabled"))
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
                clip: true
                color: "#1E293B"
                border.color: safe4Hover.hovered ? "#D8B4FE" : ((view.bridge && view.bridge.schedulerSweepRetry) ? "#A855F7" : "#334155")
                border.width: 1

                transform: Translate {
                    y: safe4Hover.hovered && !view.isScrolling ? -2.5 : 0
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
                        color: (view.bridge && view.bridge.schedulerSweepRetry) ? "#581C87" : "#0F172A"
                        scale: safe4Hover.hovered && !view.isScrolling ? 1.12 : 1.0
                        Behavior on scale {
                            SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 }
                        }
                        Text { anchors.centerIn: parent; text: "🔄"; font.pixelSize: 17 }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 2
                        Text {
                            text: view.tr("scheduler_sweep_retry_title", "Sweep Auto-Retry Pass")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Text {
                            text: view.tr("scheduler_sweep_retry_desc", "Scheduled downloads retry failed files once more at the end")
                            font.pixelSize: 11
                            color: "#94A3B8"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    StyledSwitch {
                        checked: view.bridge ? view.bridge.schedulerSweepRetry : true
                        accentColor: "#A855F7"
                        onToggled: function(isChecked) {
                            view.saveGlobalSettings(undefined, undefined, undefined, undefined, undefined, undefined, isChecked)
                            view.showToast(isChecked ? view.tr("toast_sweep_on", "Sweep retry enabled") : view.tr("toast_sweep_off", "Sweep retry disabled"))
                        }
                    }
                }
            }
        }
    }
}

