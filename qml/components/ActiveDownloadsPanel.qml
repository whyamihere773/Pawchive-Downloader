import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../"

Rectangle {
    id: panelRoot

    property var bridge: null
    property bool isCollapsed: false

    readonly property int activeCount: (bridge && bridge.activeQueueModel) ? bridge.activeQueueModel.count : 0

    // Live refresh timer: prompts active rows to refresh speed, ETA, and progress smoothly in-place
    Timer {
        id: liveRefreshTimer
        interval: 1000
        repeat: true
        running: bridge && bridge.isDownloading && panelRoot.activeCount > 0
        onTriggered: {
            if (bridge && bridge.activeQueueModel) {
                var model = bridge.activeQueueModel
                var c = model.rowCount()
                if (c > 0) {
                    model.dataChanged(model.index(0, 0), model.index(c - 1, 0))
                }
            }
        }
    }

    color: "#0B0D13"
    border.color: "#1E2435"
    border.width: 1
    radius: 8
    clip: true

    implicitHeight: isCollapsed ? 36 : (panelRoot.activeCount > 0 ? Math.min(panelRoot.activeCount * 54 + 44, 250) : 0)

    Behavior on implicitHeight {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 6
        spacing: 6

        // ── 1. Header Toolbar ────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 24
            spacing: 8

            // Pulsing live indicator dot
            Rectangle {
                width: 8
                height: 8
                radius: 4
                color: panelRoot.activeCount > 0 ? "#38BDF8" : "#64748B"
                Layout.alignment: Qt.AlignVCenter

                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    running: panelRoot.activeCount > 0 && bridge && bridge.isDownloading
                    NumberAnimation { from: 0.35; to: 1.0; duration: 800; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 1.0; to: 0.35; duration: 800; easing.type: Easing.InOutSine }
                }
            }

            // Title
            Text {
                text: "⚡ Active Downloads"
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                font.weight: Font.Bold
                color: "#F8FAFC"
                Layout.alignment: Qt.AlignVCenter
            }

            // Active count pill badge
            Rectangle {
                implicitHeight: 18
                implicitWidth: countText.implicitWidth + 12
                radius: 9
                color: "#162032"
                border.color: "#25344D"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Text {
                    id: countText
                    anchors.centerIn: parent
                    text: panelRoot.activeCount + " active"
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    color: "#38BDF8"
                }
            }

            // Spacer
            Item { Layout.fillWidth: true }

            // Aggregate speed pill if available
            Rectangle {
                implicitHeight: 18
                implicitWidth: speedTextLabel.implicitWidth + 12
                radius: 9
                color: "#0F231D"
                border.color: "#164E3D"
                border.width: 1
                visible: bridge && bridge.isDownloading && bridge.speedText && bridge.speedText !== "0 KB/s"
                Layout.alignment: Qt.AlignVCenter

                Text {
                    id: speedTextLabel
                    anchors.centerIn: parent
                    text: bridge ? bridge.speedText : ""
                    font.family: "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    color: "#34D399"
                }
            }

            // Collapse / Expand toggle button
            Rectangle {
                implicitWidth: 20
                implicitHeight: 20
                radius: 4
                color: collapseBtnMouse.containsMouse ? "#1E2435" : "transparent"
                border.color: collapseBtnMouse.containsMouse ? "#334155" : "transparent"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                Text {
                    anchors.centerIn: parent
                    text: panelRoot.isCollapsed ? "▼" : "▲"
                    font.pixelSize: 9
                    color: collapseBtnMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                }

                MouseArea {
                    id: collapseBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: panelRoot.isCollapsed ? "Expand active downloads panel" : "Collapse panel"
                    onClicked: panelRoot.isCollapsed = !panelRoot.isCollapsed
                }
            }
        }

        // Divider
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#181D29"
            visible: !panelRoot.isCollapsed && panelRoot.activeCount > 0
        }

        // ── 2. Active Downloads List ─────────────────────────────────────────
        ListView {
            id: activeListView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            spacing: 4
            visible: !panelRoot.isCollapsed && panelRoot.activeCount > 0

            model: (bridge && bridge.activeQueueModel) ? bridge.activeQueueModel : null

            delegate: Rectangle {
                id: rowRect
                width: activeListView.width
                height: 48
                radius: 6
                color: rowMouse.containsMouse ? "#171B26" : "#11141D"
                border.color: rowMouse.containsMouse ? "#2A3245" : "#191E2B"
                border.width: 1

                Behavior on color {
                    ColorAnimation { duration: 120 }
                }

                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.ArrowCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 500
                    ToolTip.text: {
                        var title = model.postTitle ? ("[" + model.postTitle + "]\n") : ""
                        var creator = model.creatorName ? ("Creator: " + model.creatorName + "\n") : ""
                        return title + creator + model.filename
                    }
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    anchors.topMargin: 5
                    anchors.bottomMargin: 5
                    spacing: 4

                    // Line 1: Filename (left) + Size (right)
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            Layout.fillWidth: true
                            text: model.filename || ""
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: "#E2E8F0"
                            elide: Text.ElideMiddle
                        }

                        Text {
                            text: (model.downloadedBytes || "0 B") + " / " + (model.fileSize || "-")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 10
                            color: "#94A3B8"
                            Layout.alignment: Qt.AlignRight
                        }
                    }

                    // Line 2: Progress Bar + Percent + Speed + ETA
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        // Mini progress bar track
                        Rectangle {
                            Layout.fillWidth: true
                            height: 5
                            radius: 2.5
                            color: "#1E2435"
                            clip: true

                            // Progress fill
                            Rectangle {
                                height: parent.height
                                radius: 2.5
                                width: {
                                    var p = model.progress || 0.0
                                    var clamped = Math.max(0.0, Math.min(1.0, p))
                                    return Math.max(clamped * parent.width, (model.percentage > 0 ? 4 : 0))
                                }
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0.0; color: "#0284C7" }
                                    GradientStop { position: 1.0; color: "#38BDF8" }
                                }

                                Behavior on width {
                                    NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                                }
                            }
                        }

                        // Percentage
                        Text {
                            text: (model.percentage !== undefined ? model.percentage : 0) + "%"
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            color: "#38BDF8"
                            Layout.preferredWidth: 34
                            horizontalAlignment: Text.AlignRight
                        }

                        // Speed
                        Text {
                            text: model.speed || "0 KB/s"
                            font.family: "Cascadia Code, Consolas, monospace"
                            font.pixelSize: 10
                            color: "#34D399"
                            Layout.preferredWidth: 64
                            horizontalAlignment: Text.AlignRight
                        }

                        // ETA
                        Text {
                            text: "ETA: " + (model.eta || "--")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 10
                            color: "#94A3B8"
                            Layout.preferredWidth: 70
                            horizontalAlignment: Text.AlignRight
                        }
                    }
                }
            }
        }
    }
}
