import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var logModel: null
    property bool autoScroll: true
    property string activeLevel: "ALL"
    property bool statusOnlyMode: false

    signal exportLogsRequested()
    signal clearLogsRequested()
    signal exportLinksRequested()
    signal downloadLinksRequested()

    color: "#0D0F14"
    border.color: "#242A38"
    border.width: 1
    radius: 10

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // Header toolbar
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            // Title & Icon
            Row {
                spacing: 6
                Text {
                    text: "💻"
                    font.pixelSize: 13
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: "Progress Log"
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: "#F1F5F9"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            Item { Layout.fillWidth: true }

            // Level filters (Highlights active level)
            Row {
                spacing: 4
                Repeater {
                    model: ["ALL", "INFO", "WARN", "ERR"]
                    delegate: Rectangle {
                        width: 38
                        height: 22
                        radius: 4
                        property bool selected: root.activeLevel === modelData

                        color: selected ? "#38BDF8" : (mArea.containsMouse ? "#2A303F" : "#1A1E29")
                        border.color: selected ? "#38BDF8" : "#2E3547"
                        border.width: 1

                        Behavior on color { ColorAnimation { duration: 100 } }
                        Behavior on border.color { ColorAnimation { duration: 100 } }

                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            font.pixelSize: 9
                            font.weight: Font.Bold
                            color: selected ? "#0F172A" : "#94A3B8"
                        }

                        MouseArea {
                            id: mArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 400
                            ToolTip.text: modelData === "ALL" ? "Show all log messages" : (modelData === "INFO" ? "Filter by Info level" : (modelData === "WARN" ? "Filter by Warnings" : "Filter by Errors"))
                            onClicked: {
                                root.activeLevel = modelData
                                var lvl = modelData === "WARN" ? "WARNING" : (modelData === "ERR" ? "ERROR" : modelData)
                                if (root.logModel) root.logModel.setFilterLevel(lvl)
                            }
                        }
                    }
                }
            }

            // Download links button (Cloud Download)
            Rectangle {
                width: 108
                height: 24
                radius: 5
                color: dlLinkMouse.containsMouse ? "#113832" : "#0A2521"
                border.color: "#2DD4BF"
                border.width: 1

                Row {
                    anchors.centerIn: parent
                    spacing: 4
                    Text { text: "☁️"; font.pixelSize: 10 }
                    Text {
                        text: "Download Links"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#2DD4BF"
                        font.weight: Font.DemiBold
                    }
                }

                MouseArea {
                    id: dlLinkMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: "Open dialog to download harvested links via Mega.nz, Google Drive, Dropbox, or GoFile"
                    onClicked: root.downloadLinksRequested()
                }
            }

            // Export links button
            Rectangle {
                width: 96
                height: 24
                radius: 5
                color: exLinkMouse.containsMouse ? "#1E2D2A" : "#13211E"
                border.color: "#10B981"
                border.width: 1

                Row {
                    anchors.centerIn: parent
                    spacing: 4
                    Text { text: "🔗"; font.pixelSize: 10 }
                    Text {
                        text: "Export Links"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#34D399"
                        font.weight: Font.Medium
                    }
                }

                MouseArea {
                    id: exLinkMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: "Extract and export all external cloud links to a text file"
                    onClicked: root.exportLinksRequested()
                }
            }

            // Eye Button: Status / Summary mode toggle (Filters out individual file names)
            Rectangle {
                width: 28
                height: 24
                radius: 5
                color: root.statusOnlyMode ? "#1E2A3A" : (eyeMouse.containsMouse ? "#222734" : "#1A1E29")
                border.color: root.statusOnlyMode ? "#38BDF8" : "#2E3547"
                border.width: 1

                Behavior on color { ColorAnimation { duration: 100 } }
                Behavior on border.color { ColorAnimation { duration: 100 } }

                Text {
                    anchors.centerIn: parent
                    text: root.statusOnlyMode ? "🙈" : "👁"
                    font.pixelSize: 12
                    color: root.statusOnlyMode ? "#38BDF8" : "#64748B"
                }

                MouseArea {
                    id: eyeMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: root.statusOnlyMode ? "Status-Only mode active (click to show all file details)" : "Click to hide individual file names and show status only"
                    onClicked: {
                        root.statusOnlyMode = !root.statusOnlyMode
                        if (root.logModel) root.logModel.setStatusOnly(root.statusOnlyMode)
                    }
                }
            }

            // Reset/Clear button
            Rectangle {
                width: 58
                height: 24
                radius: 5
                color: resetMouse.containsMouse ? "#2C1D24" : "#1F161C"
                border.color: "#EF4444"
                border.width: 1

                Row {
                    anchors.centerIn: parent
                    spacing: 3
                    Text { text: "↻"; font.pixelSize: 11; color: "#F87171" }
                    Text {
                        text: "Reset"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#F87171"
                        font.weight: Font.Medium
                    }
                }

                MouseArea {
                    id: resetMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: "Clear all progress console logs"
                    onClicked: root.clearLogsRequested()
                }
            }
        }

        // Search bar
        Rectangle {
            Layout.fillWidth: true
            height: 26
            radius: 5
            color: "#13161E"
            border.color: searchInput.activeFocus ? "#38BDF8" : "#242A38"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                Text { text: "🔍"; font.pixelSize: 10; color: "#64748B" }

                TextInput {
                    id: searchInput
                    Layout.fillWidth: true
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#F1F5F9"
                    clip: true
                    selectByMouse: true

                    Text {
                        anchors.fill: parent
                        text: "Filter console output..."
                        color: "#475569"
                        font.pixelSize: 11
                        visible: !searchInput.text && !searchInput.activeFocus
                    }

                    onTextChanged: {
                        if (root.logModel) root.logModel.setSearchQuery(text)
                    }
                }
            }
        }

        // Log Console ListView
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#08090C"
            radius: 6
            border.color: "#1E2330"
            border.width: 1
            clip: true

            ListView {
                id: logList
                anchors.fill: parent
                anchors.margins: 6
                model: root.logModel
                spacing: 3
                boundsBehavior: Flickable.StopAtBounds

                property bool programmaticScroll: false

                ScrollBar.vertical: ScrollBar {
                    id: logScrollBar
                    active: true
                    policy: ScrollBar.AsNeeded
                    onPositionChanged: {
                        if (pressed) {
                            // User is actively dragging the scrollbar thumb
                            root.autoScroll = (position + size >= 0.98)
                        }
                    }
                }

                onMovingChanged: {
                    if (!moving && !programmaticScroll) {
                        root.autoScroll = atYEnd
                    }
                }

                onContentYChanged: {
                    if (!programmaticScroll) {
                        root.autoScroll = atYEnd
                    }
                }

                delegate: RowLayout {
                    width: logList.width - 12
                    spacing: 6

                    // Timestamp
                    Text {
                        text: model.timestamp
                        font.family: "Cascadia Code, Consolas, monospace"
                        font.pixelSize: 10
                        color: "#64748B"
                    }

                    // Level Badge (Vibrant colored icon with matching tinted border)
                    Rectangle {
                        width: 18
                        height: 18
                        radius: 4
                        color: Qt.rgba(0.12, 0.16, 0.22, 0.9)
                        border.color: model.levelColor
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: model.icon
                            font.pixelSize: 9
                            font.bold: true
                            color: model.levelColor
                        }
                    }

                    // Message — URLs are rendered as clickable links
                    TextEdit {
                        Layout.fillWidth: true
                        text: {
                            var raw = model.message
                            var escaped = raw.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                            var linked = escaped.replace(/(https?:\/\/[^\s<>"]+)/g, '<a href="$1" style="color:#38BDF8; text-decoration:underline;">$1</a>')
                            return linked
                        }
                        font.family: "Cascadia Code, Consolas, monospace"
                        font.pixelSize: 11
                        color: model.levelColor
                        wrapMode: TextEdit.WrapAnywhere
                        readOnly: true
                        selectByMouse: true
                        textFormat: TextEdit.RichText
                        selectedTextColor: "#FFFFFF"
                        selectionColor: "#2563EB"
                        onLinkActivated: (link) => Qt.openUrlExternally(link)
                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.NoButton
                            cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.IBeamCursor
                        }
                    }
                }

                onCountChanged: {
                    if (root.autoScroll) {
                        programmaticScroll = true
                        Qt.callLater(function() {
                            logList.positionViewAtEnd()
                            Qt.callLater(function() {
                                programmaticScroll = false
                            })
                        })
                    }
                }
            }

            // Floating "Jump to latest" button when user is scrolled up
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottomMargin: 10
                visible: !root.autoScroll && !logList.atYEnd
                height: 24
                width: jumpLatestRow.implicitWidth + 18
                radius: 12
                color: jumpMouse.containsMouse ? "#0284C7" : Qt.rgba(0.06, 0.10, 0.18, 0.95)
                border.color: "#38BDF8"
                border.width: 1
                z: 10

                Behavior on color { ColorAnimation { duration: 120 } }

                Row {
                    id: jumpLatestRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text {
                        text: "⬇"
                        font.pixelSize: 10
                        color: jumpMouse.containsMouse ? "#FFFFFF" : "#38BDF8"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: "Jump to latest"
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        color: jumpMouse.containsMouse ? "#FFFFFF" : "#F1F5F9"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: jumpMouse
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: {
                        logList.programmaticScroll = true
                        root.autoScroll = true
                        logList.positionViewAtEnd()
                        Qt.callLater(function() {
                            logList.programmaticScroll = false
                        })
                    }
                }
            }
        }
    }
}
