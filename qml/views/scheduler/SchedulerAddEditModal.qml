import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// Add / Modify Automation Schedule dialog modal.
Rectangle {
    id: addDialogModal

    required property var view

    function populateFromTask(task) {
        if (task) {
            taskNameInput.text = task.name || ""
            addDialogModal.selectedTarget = task.target_type || "watchlist"
            taskUrlInput.text = task.target_url || ""
            addDialogModal.selectedTrigger = task.trigger_type || "interval"
            intervalSpin.value = task.interval_hours || 6
            timeOfDayInput.text = task.time_of_day || "03:00"
        } else {
            taskNameInput.text = ""
            addDialogModal.selectedTarget = "watchlist"
            taskUrlInput.text = ""
            addDialogModal.selectedTrigger = "interval"
            intervalSpin.value = 6
            timeOfDayInput.text = "03:00"
        }
    }

    visible: opacity > 0.001
    opacity: view.showAddDialog ? 1.0 : 0.0
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
        width: Math.min(Math.max(parent.width - 32, 260), 480)
        height: Math.min(addDialogCol.implicitHeight + 36, parent.height - 32)
        radius: 12
        color: "#0F172A"
        border.color: "#334155"
        border.width: 1.5
        clip: true

        scale: view.showAddDialog ? 1.0 : 0.90
        transform: Translate {
            y: view.showAddDialog ? 0 : -22
            Behavior on y {
                SpringAnimation { spring: 4.5; damping: 0.38; mass: 1.0 }
            }
        }
        Behavior on scale {
            SpringAnimation { spring: 4.5; damping: 0.38; mass: 1.0 }
        }

        Flickable {
            id: modalFlick
            anchors.fill: parent
            anchors.margins: 18
            contentWidth: width
            contentHeight: addDialogCol.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            ColumnLayout {
                id: addDialogCol
                width: modalFlick.width
                spacing: 14

                // Modal Header
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text { text: view.editingScheduleId ? "✏️" : "⏰"; font.pixelSize: 18 }
                    Text {
                        text: view.editingScheduleId ?
                              view.tr("scheduler_modal_edit_title", "Modify Automation Schedule") :
                              view.tr("scheduler_modal_title", "Create Automation Schedule")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
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
                            onClicked: view.showAddDialog = false
                        }
                    }
                }

                // Schedule Name Input
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text: view.tr("scheduler_modal_name_label", "Schedule Name")
                        font.pixelSize: 11; font.weight: 600; color: "#CBD5E1"
                    }
                    TextField {
                        id: taskNameInput
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: 34
                        placeholderText: view.tr("scheduler_modal_name_placeholder", "e.g., Nightly Watchlist Sync")
                        color: "#F8FAFC"
                        placeholderTextColor: "#64748B"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        verticalAlignment: TextInput.AlignVCenter
                        font.pixelSize: 12
                        background: Rectangle { color: taskNameInput.activeFocus ? "#0E1525" : "#1E293B"; radius: 6; border.color: taskNameInput.activeFocus ? "#818CF8" : (taskNameInput.hovered ? "#475569" : "#334155"); border.width: taskNameInput.activeFocus ? 1.5 : 1 }
                        TextBarContextArea {}
                    }
                }

                // Target Type Switcher
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Text {
                        text: view.tr("scheduler_modal_target_label", "Target Action")
                        font.pixelSize: 11; font.weight: 600; color: "#CBD5E1"
                    }

                    GridLayout {
                        columns: modalBox.width > 380 ? 2 : 1
                        Layout.fillWidth: true
                        rowSpacing: 8
                        columnSpacing: 10

                        // Watchlist Option
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            height: 38
                            radius: 6
                            color: addDialogModal.selectedTarget === "watchlist" ? "#2E1065" : "#1E293B"
                            border.color: addDialogModal.selectedTarget === "watchlist" ? "#A855F7" : "#334155"
                            border.width: 1

                            scale: watchOptMouse.pressed ? 0.96 : (watchOptMouse.containsMouse ? 1.02 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            RowLayout {
                                anchors.centerIn: parent
                                spacing: 8
                                Text { text: "⭐"; font.pixelSize: 12 }
                                Text {
                                    text: view.tr("scheduler_target_watchlist", "Watchlist: check & download new posts")
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: addDialogModal.selectedTarget === "watchlist" ? "#F8FAFC" : "#94A3B8"
                                    elide: Text.ElideRight
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
                            Layout.minimumWidth: 0
                            height: 38
                            radius: 6
                            color: addDialogModal.selectedTarget === "creator" ? "#0C4A6E" : "#1E293B"
                            border.color: addDialogModal.selectedTarget === "creator" ? "#0284C7" : "#334155"
                            border.width: 1

                            scale: creatOptMouse.pressed ? 0.96 : (creatOptMouse.containsMouse ? 1.02 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            RowLayout {
                                anchors.centerIn: parent
                                spacing: 8
                                Text { text: "🌐"; font.pixelSize: 12 }
                                Text {
                                    text: view.tr("scheduler_target_creator", "Specific Creator URL")
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: addDialogModal.selectedTarget === "creator" ? "#F8FAFC" : "#94A3B8"
                                    elide: Text.ElideRight
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
                        text: view.tr("scheduler_modal_url_label", "Creator Page URL")
                        font.pixelSize: 11; font.weight: 600; color: "#CBD5E1"
                    }
                    TextField {
                        id: taskUrlInput
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: 34
                        placeholderText: "https://kemono.cr/patreon/user/12345"
                        color: "#F8FAFC"
                        placeholderTextColor: "#64748B"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        verticalAlignment: TextInput.AlignVCenter
                        font.pixelSize: 12
                        background: Rectangle { color: taskUrlInput.activeFocus ? "#0E1525" : "#1E293B"; radius: 6; border.color: taskUrlInput.activeFocus ? "#38BDF8" : (taskUrlInput.hovered ? "#475569" : "#334155"); border.width: taskUrlInput.activeFocus ? 1.5 : 1 }
                        TextBarContextArea {}
                    }
                }

                // Cadence Trigger Type
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: view.tr("scheduler_modal_trigger_label", "Trigger Schedule")
                        font.pixelSize: 11; font.weight: 600; color: "#CBD5E1"
                    }

                    GridLayout {
                        columns: modalBox.width > 380 ? 2 : 1
                        Layout.fillWidth: true
                        rowSpacing: 8
                        columnSpacing: 10

                        // Interval Option
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            height: 34
                            radius: 6
                            color: addDialogModal.selectedTrigger === "interval" ? "#1E1B4B" : "#1E293B"
                            border.color: addDialogModal.selectedTrigger === "interval" ? "#818CF8" : "#334155"
                            border.width: 1

                            scale: intOptMouse.pressed ? 0.96 : (intOptMouse.containsMouse ? 1.02 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            RowLayout {
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "⏱️"; font.pixelSize: 11 }
                                Text {
                                    text: view.tr("scheduler_trigger_interval", "Repeating Interval")
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: addDialogModal.selectedTrigger === "interval" ? "#F8FAFC" : "#94A3B8"
                                    elide: Text.ElideRight
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
                            Layout.minimumWidth: 0
                            height: 34
                            radius: 6
                            color: addDialogModal.selectedTrigger === "time_of_day" ? "#1E1B4B" : "#1E293B"
                            border.color: addDialogModal.selectedTrigger === "time_of_day" ? "#818CF8" : "#334155"
                            border.width: 1

                            scale: timeOptMouse.pressed ? 0.96 : (timeOptMouse.containsMouse ? 1.02 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            RowLayout {
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "⏰"; font.pixelSize: 11 }
                                Text {
                                    text: view.tr("scheduler_trigger_fixed", "Daily Fixed Time")
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: addDialogModal.selectedTrigger === "time_of_day" ? "#F8FAFC" : "#94A3B8"
                                    elide: Text.ElideRight
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
                        Layout.minimumWidth: 0
                        spacing: 8

                        Text {
                            text: view.tr("scheduler_every_hours", "Run every:")
                            font.pixelSize: 12; color: "#CBD5E1"
                        }

                        StyledSpinBox {
                            id: intervalSpin
                            from: 1; to: 72; value: 6; stepSize: 1
                            suffix: " hrs"
                            accentColor: "#38BDF8"
                            implicitWidth: 120
                        }

                        Text {
                            text: view.tr("scheduler_hours_unit", "hours")
                            font.pixelSize: 12; color: "#94A3B8"
                        }
                    }

                    // Daily Fixed Time Selector
                    RowLayout {
                        visible: addDialogModal.selectedTrigger === "time_of_day"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 8

                        Text {
                            text: view.tr("scheduler_at_time", "Run daily at:")
                            font.pixelSize: 12; color: "#CBD5E1"
                        }

                        TextField {
                            id: timeOfDayInput
                            text: "03:00"
                            Layout.preferredWidth: 70
                            Layout.preferredHeight: 30
                            horizontalAlignment: TextInput.AlignHCenter
                            verticalAlignment: TextInput.AlignVCenter
                            font.pixelSize: 12
                            color: "#38BDF8"
                            selectionColor: "#0284C7"
                            selectedTextColor: "#FFFFFF"
                            selectByMouse: true
                            clip: true
                            background: Rectangle { color: timeOfDayInput.activeFocus ? "#0E1525" : "#1E293B"; radius: 4; border.color: timeOfDayInput.activeFocus ? "#38BDF8" : (timeOfDayInput.hovered ? "#475569" : "#334155"); border.width: timeOfDayInput.activeFocus ? 1.5 : 1 }
                            TextBarContextArea {}
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
                    spacing: 10

                    Item { Layout.fillWidth: true }

                    // Cancel Button
                    Rectangle {
                        height: 36
                        implicitWidth: modalBox.width < 340 ? 72 : 84
                        radius: 8
                        color: cancelMouse.containsMouse ? "#334155" : "#1E293B"
                        border.color: "#475569"; border.width: 1

                        scale: cancelMouse.pressed ? 0.94 : (cancelMouse.containsMouse ? 1.02 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                        Behavior on color { ColorAnimation { duration: 120 } }

                        Text {
                            anchors.centerIn: parent
                            text: view.tr("btn_cancel", "Cancel")
                            font.pixelSize: 12
                            color: "#E2E8F0"
                        }
                        MouseArea {
                            id: cancelMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: view.showAddDialog = false
                        }
                    }

                    // Save / Update Schedule Button
                    Rectangle {
                        height: 36
                        implicitWidth: modalBox.width < 340 ? 116 : 140
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
                            text: view.editingScheduleId ?
                                  view.tr("scheduler_modal_update_btn", "Update Schedule") :
                                  view.tr("scheduler_modal_create_btn", "Save Schedule")
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
                                var name = taskNameInput.text.trim() || (addDialogModal.selectedTarget === "watchlist" ? "Watchlist Sync" : "Creator Download")
                                var targetType = addDialogModal.selectedTarget
                                var targetUrl = targetType === "creator" ? taskUrlInput.text.trim() : ""
                                var triggerType = addDialogModal.selectedTrigger
                                var intervalH = intervalSpin.value
                                var timeVal = timeOfDayInput.text.trim() || "03:00"

                                if (view.bridge) {
                                    if (view.editingScheduleId) {
                                        view.bridge.updateSchedulerTask(view.editingScheduleId, name, targetType, targetUrl, triggerType, intervalH, timeVal)
                                        view.showToast(view.tr("toast_schedule_updated", "Schedule updated successfully!"))
                                    } else {
                                        view.bridge.addSchedulerTask(name, targetType, targetUrl, triggerType, intervalH, timeVal)
                                        view.showToast(view.tr("toast_schedule_created", "Schedule created successfully!"))
                                    }
                                }
                                view.showAddDialog = false
                                view.editingScheduleId = ""
                                taskNameInput.text = ""
                                taskUrlInput.text = ""
                            }
                        }
                    }
                }
            }
        }
    }
}

