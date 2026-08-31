import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Rectangle {
    id: root

    property var bridge: null
    color: "#0F1117"

    // Reload history whenever something changes
    Connections {
        target: root.bridge
        function onDownloadHistoryChanged() {
            historyListModel.reload()
        }
    }

    // Local JS model wrapper
    ListModel {
        id: historyListModel

        function reload() {
            clear()
            if (!root.bridge) return
            var entries = root.bridge.getDownloadHistory()
            for (var i = 0; i < entries.length; i++) {
                var e = entries[i]
                historyListModel.append({
                    creator: e.creator || "Unknown",
                    url:     e.url || "",
                    service: (e.service || "").toUpperCase(),
                    files:   e.files || 0,
                    date:    e.date || ""
                })
            }
        }
    }

    Component.onCompleted: historyListModel.reload()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "📜 Download History"
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 14
                font.weight: Font.Bold
                color: "#F8FAFC"
            }

            Rectangle {
                width: Math.max(24, countBadge.implicitWidth + 12)
                height: 20; radius: 10; color: "#242A38"
                Text {
                    id: countBadge
                    anchors.centerIn: parent
                    text: historyListModel.count.toString()
                    font.pixelSize: 10; font.bold: true; color: "#38BDF8"
                }
            }

            Item { Layout.fillWidth: true }

            StyledButton {
                text: "Refresh"
                iconText: "🔄"
                variant: "outline"
                implicitHeight: 28
                onClicked: historyListModel.reload()
            }

            StyledButton {
                text: "Clear History"
                iconText: "🗑"
                variant: "ghost"
                implicitHeight: 28
                onClicked: {
                    // Clear is not destructive to downloads, only the history list
                    historyListModel.clear()
                }
            }
        }

        // History list
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#141720"
            border.color: "#242A38"
            border.width: 1
            radius: 8
            clip: true

            ListView {
                id: historyList
                anchors.fill: parent
                anchors.margins: 6
                spacing: 6
                model: historyListModel
                ScrollBar.vertical: ScrollBar { active: true; policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    width: historyList.width - 12
                    height: 64
                    radius: 6
                    color: hoverArea.pressed ? "#161B28" : (hoverArea.containsMouse ? "#1E2436" : "#1A1E29")
                    border.color: hoverArea.containsMouse ? "#38BDF8" : "#282E3D"
                    border.width: 1

                    scale: hoverArea.pressed ? 0.98 : (hoverArea.containsMouse ? 1.012 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.4 }
                    }
                    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
                    Behavior on border.color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }

                    MouseArea {
                        id: hoverArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            // Set URL in bridge and switch to Downloader tab
                            if (root.bridge) {
                                root.bridge.currentUrl = model.url
                            }
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        anchors.topMargin: 8
                        anchors.bottomMargin: 8
                        spacing: 12

                        // Service pill
                        Rectangle {
                            width: Math.max(58, svcLabel.implicitWidth + 10)
                            height: 22
                            radius: 4
                            color: {
                                var s = model.service.toLowerCase()
                                if (s === "fanbox") return "#1A3247"
                                if (s === "patreon") return "#2A1B30"
                                if (s === "onlyfans") return "#2A2010"
                                return "#242A38"
                            }
                            Text {
                                id: svcLabel
                                anchors.centerIn: parent
                                text: model.service
                                font.pixelSize: 9
                                font.bold: true
                                color: {
                                    var s = model.service.toLowerCase()
                                    if (s === "fanbox") return "#38BDF8"
                                    if (s === "patreon") return "#C084FC"
                                    if (s === "onlyfans") return "#FBBF24"
                                    return "#94A3B8"
                                }
                            }
                        }

                        // Creator info
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3

                            Text {
                                text: model.creator
                                font.family: "Segoe UI, Inter, sans-serif"
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: "#F1F5F9"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            Text {
                                text: model.url
                                font.family: "Cascadia Code, monospace"
                                font.pixelSize: 10
                                color: "#38BDF8"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                                opacity: 0.75
                            }
                        }

                        // Stats
                        ColumnLayout {
                            spacing: 3
                            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter

                            Row {
                                spacing: 4
                                Layout.alignment: Qt.AlignRight
                                Text { text: "📦"; font.pixelSize: 10 }
                                Text {
                                    text: model.files + " files"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    color: "#94A3B8"
                                }
                            }

                            Row {
                                spacing: 4
                                Layout.alignment: Qt.AlignRight
                                Text { text: "🕐"; font.pixelSize: 10 }
                                Text {
                                    text: model.date
                                    font.family: "Cascadia Code, monospace"
                                    font.pixelSize: 10
                                    color: "#64748B"
                                }
                            }
                        }

                        // Re-download button
                        Rectangle {
                            width: 28; height: 28; radius: 6
                            color: reDownBtn.containsMouse ? "#0EA5E9" : "#1E2A38"
                            border.color: "#38BDF8"
                            border.width: 1

                            Text { anchors.centerIn: parent; text: "↩"; font.pixelSize: 13; color: "#38BDF8" }

                            MouseArea {
                                id: reDownBtn
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (root.bridge) {
                                        root.bridge.currentUrl = model.url
                                    }
                                }
                            }
                        }
                    }
                }

                // Empty state
                Text {
                    anchors.centerIn: parent
                    text: "No download history yet.\nStart downloading a creator to see entries here."
                    color: "#475569"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 13
                    horizontalAlignment: Text.AlignHCenter
                    visible: historyList.count === 0
                }
            }
        }
    }
}
