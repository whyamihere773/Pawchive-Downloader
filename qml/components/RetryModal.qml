import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Rectangle {
    id: modalRoot

    property var bridge: null
    property bool isOpen: false

    visible: opacity > 0
    anchors.fill: parent
    color: "#CC0B0D12" // Semi-transparent overlay backdrop
    z: 1000

    opacity: isOpen ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 240; easing.type: Easing.OutCubic }
    }

    // Prevent clicks from falling through to background views
    MouseArea {
        anchors.fill: parent
        onClicked: {} // consume click
    }

    // Local model for failed items selection
    ListModel {
        id: failedItemsModel

        function populate() {
            clear()
            if (!modalRoot.bridge || !modalRoot.bridge.queueModel) return
            var list = modalRoot.bridge.queueModel.getFailedTasksList()
            for (var i = 0; i < list.length; i++) {
                var item = list[i]
                failedItemsModel.append({
                    fileId: item.fileId || "",
                    filename: item.filename || "",
                    postTitle: item.postTitle || "",
                    creatorName: item.creatorName || "",
                    service: item.service || "",
                    url: item.url || "",
                    errorMsg: item.errorMsg || "",
                    fileSize: item.fileSize || "-",
                    isSelected: true // default selected
                })
            }
        }

        function getSelectedIds() {
            var res = []
            for (var i = 0; i < count; i++) {
                var item = get(i)
                if (item.isSelected) {
                    res.push(item.fileId || item.url || item.filename)
                }
            }
            return res
        }

        function countSelected() {
            var c = 0
            for (var i = 0; i < count; i++) {
                if (get(i).isSelected) c++
            }
            return c
        }

        function selectAll(val) {
            for (var i = 0; i < count; i++) {
                setProperty(i, "isSelected", val)
            }
        }
    }

    onIsOpenChanged: {
        if (isOpen) {
            failedItemsModel.populate()
        }
    }

    // Centered Dialog Window with Newtonian Spring Entrance
    Rectangle {
        id: dialogBox
        width: Math.min(modalRoot.width - 40, 720)
        height: Math.min(modalRoot.height - 40, 560)
        anchors.centerIn: parent
        radius: 10
        color: "#131722"
        border.color: "#2A3346"
        border.width: 1

        scale: modalRoot.isOpen ? 1.0 : 0.88
        transformOrigin: Item.Center

        Behavior on scale {
            NumberAnimation {
                duration: modalRoot.isOpen ? 340 : 200
                easing.type: modalRoot.isOpen ? Easing.OutBack : Easing.InCubic
                easing.overshoot: 1.3
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            // Header Row
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: "🔁 Retry Failed Downloads"
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 16
                    font.weight: Font.Bold
                    color: "#F8FAFC"
                }

                Rectangle {
                    height: 22
                    width: Math.max(24, failedCntBadge.implicitWidth + 12)
                    radius: 11
                    color: "#3B181E"
                    border.color: "#EF4444"
                    border.width: 1

                    Text {
                        id: failedCntBadge
                        anchors.centerIn: parent
                        text: failedItemsModel.count.toString() + " Failed"
                        font.pixelSize: 10
                        font.bold: true
                        color: "#FCA5A5"
                    }
                }

                Item { Layout.fillWidth: true }

                // Close X button
                Rectangle {
                    width: 24; height: 24; radius: 12
                    color: closeMouse.containsMouse ? "#374151" : "#1E2430"
                    Text { anchors.centerIn: parent; text: "×"; font.pixelSize: 14; font.bold: true; color: "#94A3B8" }
                    MouseArea {
                        id: closeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.isOpen = false
                    }
                }
            }

            Text {
                text: "Select the specific failed files you wish to re-attempt. Files that failed will only be retried if selected below or if 'Auto retry at the end' is active."
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#94A3B8"
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }

            // Quick Selection Toolbar
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                StyledButton {
                    text: "Select All"
                    iconText: "☑"
                    variant: "outline"
                    implicitHeight: 26
                    onClicked: failedItemsModel.selectAll(true)
                }

                StyledButton {
                    text: "Deselect All"
                    iconText: "☐"
                    variant: "ghost"
                    implicitHeight: 26
                    onClicked: failedItemsModel.selectAll(false)
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: failedItemsModel.countSelected() + " of " + failedItemsModel.count + " selected"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#38BDF8"
                }
            }

            // Scrollable List of Failed Tasks
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#0D1019"
                border.color: "#1E2433"
                border.width: 1
                radius: 6
                clip: true

                ListView {
                    id: failedList
                    anchors.fill: parent
                    anchors.margins: 6
                    spacing: 6
                    model: failedItemsModel
                    ScrollBar.vertical: ScrollBar { active: true; policy: ScrollBar.AsNeeded }

                    delegate: Rectangle {
                        width: failedList.width - 12
                        implicitHeight: itemCol.implicitHeight + 16
                        radius: 6
                        color: model.isSelected ? "#1F1A24" : "#141722"
                        border.color: model.isSelected ? "#EF4444" : "#242A38"
                        border.width: 1

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                failedItemsModel.setProperty(index, "isSelected", !model.isSelected)
                            }
                        }

                        ColumnLayout {
                            id: itemCol
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 5

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                // Checkbox Indicator
                                Rectangle {
                                    width: 18; height: 18; radius: 4
                                    color: model.isSelected ? "#EF4444" : "#1A1F2C"
                                    border.color: model.isSelected ? "#EF4444" : "#475569"
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: "✔"
                                        font.pixelSize: 10
                                        font.bold: true
                                        color: "#FFFFFF"
                                        visible: model.isSelected
                                    }
                                }

                                // Service Pill
                                Rectangle {
                                    width: Math.max(50, svcLabelText.implicitWidth + 8)
                                    height: 18
                                    radius: 3
                                    color: "#242A38"
                                    Text {
                                        id: svcLabelText
                                        anchors.centerIn: parent
                                        text: (model.service || "FILE").toUpperCase()
                                        font.pixelSize: 9
                                        font.bold: true
                                        color: "#38BDF8"
                                    }
                                }

                                // Filename
                                Text {
                                    text: model.filename
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    color: "#F1F5F9"
                                    Layout.fillWidth: true
                                    elide: Text.ElideMiddle
                                }

                                // Size
                                Text {
                                    text: model.fileSize
                                    font.family: "Cascadia Code, monospace"
                                    font.pixelSize: 10
                                    color: "#94A3B8"
                                }
                            }

                            // Post Title / Creator
                            Text {
                                text: "📌 Post: " + model.postTitle + " (" + model.creatorName + ")"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }

                            // Error Callout Banner
                            Rectangle {
                                Layout.fillWidth: true
                                height: 22
                                radius: 4
                                color: "#2B1318"
                                border.color: "#5C1D24"
                                border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 6
                                    anchors.rightMargin: 6
                                    spacing: 4

                                    Text { text: "⚠️"; font.pixelSize: 10 }
                                    Text {
                                        text: model.errorMsg
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: "#FCA5A5"
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }

                    // Empty state in modal
                    Text {
                        anchors.centerIn: parent
                        text: "No failed tasks found."
                        color: "#64748B"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 13
                        visible: failedList.count === 0
                    }
                }
            }

            // Bottom Settings & Action Row
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                // Physical "Auto retry at the end" Toggle Button
                StyledButton {
                    text: modalRoot.bridge && modalRoot.bridge.autoRetryAtEnd ? "Auto-Retry at End: ON" : "Auto-Retry at End: OFF"
                    iconText: "🔄"
                    variant: modalRoot.bridge && modalRoot.bridge.autoRetryAtEnd ? "success" : "outline"
                    implicitHeight: 32
                    onClicked: {
                        if (modalRoot.bridge) modalRoot.bridge.autoRetryAtEnd = !modalRoot.bridge.autoRetryAtEnd
                    }
                }

                Item { Layout.fillWidth: true }

                StyledButton {
                    text: "Cancel"
                    variant: "ghost"
                    implicitHeight: 32
                    onClicked: modalRoot.isOpen = false
                }

                StyledButton {
                    id: retrySubmitBtn
                    text: "Retry Selected (" + failedItemsModel.countSelected() + ")"
                    iconText: "🔁"
                    variant: "danger"
                    implicitHeight: 32
                    enabled: failedItemsModel.countSelected() > 0
                    onClicked: {
                        var ids = failedItemsModel.getSelectedIds()
                        if (modalRoot.bridge && ids.length > 0) {
                            modalRoot.bridge.retrySelectedTasks(ids)
                        }
                        modalRoot.isOpen = false
                    }
                }
            }
        }
    }
}
