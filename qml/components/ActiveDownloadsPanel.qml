import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../"

Rectangle {
    id: panelRoot

    property var bridge: null
    property bool isCollapsed: false

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

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

    readonly property bool shouldBeOpen: panelRoot.activeCount > 0
    property real targetHeight: isCollapsed ? 36 : (shouldBeOpen ? Math.min(panelRoot.activeCount * 54 + 44, 250) : 0)

    // Newtonian physical height expansion & fluid collapse for disappearance
    implicitHeight: targetHeight

    Behavior on implicitHeight {
        NumberAnimation {
            duration: panelRoot.shouldBeOpen ? 340 : 380
            easing.type: panelRoot.shouldBeOpen ? Easing.OutBack : Easing.InOutCubic
            easing.overshoot: 1.15
        }
    }

    opacity: (panelRoot.shouldBeOpen && implicitHeight > 4) ? 1.0 : 0.0

    Behavior on opacity {
        NumberAnimation {
            duration: panelRoot.shouldBeOpen ? 240 : 300
            easing.type: Easing.InOutCubic
        }
    }

    visible: implicitHeight > 0.5 || shouldBeOpen

    Behavior on border.color {
        ColorAnimation { duration: 240 }
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

            // Pulsing live indicator dot with physical breathing elasticity
            Item {
                width: 14
                height: 14
                Layout.alignment: Qt.AlignVCenter

                Rectangle {
                    id: pulseHalo
                    anchors.centerIn: parent
                    width: 14
                    height: 14
                    radius: 7
                    color: "#38BDF8"
                    opacity: 0.0
                    visible: panelRoot.activeCount > 0 && bridge && bridge.isDownloading

                    SequentialAnimation on scale {
                        loops: Animation.Infinite
                        running: panelRoot.activeCount > 0 && bridge && bridge.isDownloading
                        NumberAnimation { from: 0.6; to: 1.4; duration: 1200; easing.type: Easing.OutCubic }
                        NumberAnimation { from: 1.4; to: 0.6; duration: 800; easing.type: Easing.InCubic }
                    }
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: panelRoot.activeCount > 0 && bridge && bridge.isDownloading
                        NumberAnimation { from: 0.45; to: 0.0; duration: 1200; easing.type: Easing.OutCubic }
                        NumberAnimation { from: 0.0; to: 0.45; duration: 800; easing.type: Easing.InCubic }
                    }
                }

                Rectangle {
                    id: centerDot
                    anchors.centerIn: parent
                    width: 8
                    height: 8
                    radius: 4
                    color: panelRoot.activeCount > 0 ? "#38BDF8" : "#64748B"

                    SequentialAnimation on scale {
                        loops: Animation.Infinite
                        running: panelRoot.activeCount > 0 && bridge && bridge.isDownloading
                        NumberAnimation { from: 0.9; to: 1.15; duration: 900; easing.type: Easing.InOutSine }
                        NumberAnimation { from: 1.15; to: 0.9; duration: 900; easing.type: Easing.InOutSine }
                    }
                }
            }

            // Title
            Text {
                text: panelRoot.tr("title_active_downloads", "⚡ Active Downloads")
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                font.weight: Font.Bold
                color: "#F8FAFC"
                Layout.alignment: Qt.AlignVCenter
            }

            // Active count pill badge with spring scale response
            Rectangle {
                id: countPill
                implicitHeight: 18
                implicitWidth: countText.implicitWidth + 14
                radius: 9
                color: "#162032"
                border.color: "#25344D"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                scale: 1.0
                Behavior on scale {
                    NumberAnimation { duration: 220; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
                }

                Text {
                    id: countText
                    anchors.centerIn: parent
                    text: panelRoot.activeCount + " " + (panelRoot.tr("qtab_active", "Active")).toLowerCase()
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    color: "#38BDF8"

                    onTextChanged: {
                        countPill.scale = 1.18
                        pillBounceTimer.restart()
                    }
                }

                Timer {
                    id: pillBounceTimer
                    interval: 120
                    onTriggered: countPill.scale = 1.0
                }
            }

            // Spacer
            Item { Layout.fillWidth: true }

            // Aggregate speed pill with fluid elasticity
            Rectangle {
                id: speedPill
                implicitHeight: 18
                implicitWidth: speedTextLabel.implicitWidth + 14
                radius: 9
                color: "#0F231D"
                border.color: "#164E3D"
                border.width: 1
                visible: bridge && bridge.isDownloading && bridge.currentSpeed && bridge.currentSpeed !== "0 KB/s"
                Layout.alignment: Qt.AlignVCenter
                opacity: visible ? 1.0 : 0.0
                scale: visible ? 1.0 : 0.8

                Behavior on opacity { NumberAnimation { duration: 200 } }
                Behavior on scale { NumberAnimation { duration: 240; easing.type: Easing.OutBack; easing.overshoot: 1.4 } }

                Text {
                    id: speedTextLabel
                    anchors.centerIn: parent
                    text: (bridge && bridge.currentSpeed) ? bridge.currentSpeed : ""
                    font.family: "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    color: "#34D399"
                }
            }

            // Collapse / Expand toggle button with rotational inertia and spring scale
            Rectangle {
                id: collapseBtn
                implicitWidth: 22
                implicitHeight: 22
                radius: 5
                color: collapseBtnMouse.containsMouse ? "#1E2435" : "transparent"
                border.color: collapseBtnMouse.containsMouse ? "#334155" : "transparent"
                border.width: 1
                Layout.alignment: Qt.AlignVCenter

                scale: collapseBtnMouse.pressed ? 0.88 : (collapseBtnMouse.containsMouse ? 1.15 : 1.0)
                Behavior on scale {
                    NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.6 }
                }

                Text {
                    anchors.centerIn: parent
                    text: "▲"
                    font.pixelSize: 9
                    color: collapseBtnMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                    rotation: panelRoot.isCollapsed ? 180 : 0

                    Behavior on rotation {
                        NumberAnimation { duration: 300; easing.type: Easing.OutBack; easing.overshoot: 1.45 }
                    }
                }

                MouseArea {
                    id: collapseBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: panelRoot.isCollapsed ? panelRoot.tr("tip_expand_panel", "Expand active downloads panel") : panelRoot.tr("tip_collapse_panel", "Collapse panel")
                    onClicked: panelRoot.isCollapsed = !panelRoot.isCollapsed
                }
            }

        }

        // Fluid divider
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#181D29"
            visible: !panelRoot.isCollapsed && panelRoot.activeCount > 0
            opacity: visible ? 1.0 : 0.0
            Behavior on opacity { NumberAnimation { duration: 200 } }
        }

        // ── 2. Active Downloads List (Newtonian Physics & Fluid Staggering) ──
        ListView {
            id: activeListView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            spacing: 4
            visible: !panelRoot.isCollapsed && panelRoot.activeCount > 0

            model: (bridge && bridge.activeQueueModel) ? bridge.activeQueueModel : null

            // Staggered Newtonian populate transition when panel mounts
            populate: Transition {
                NumberAnimation { properties: "y"; from: -14; duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.35 }
                NumberAnimation { properties: "scale"; from: 0.90; to: 1.0; duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.35 }
                NumberAnimation { properties: "opacity"; from: 0.0; to: 1.0; duration: 240; easing.type: Easing.OutCubic }
            }

            // Fluid spring drop-in when a new worker begins downloading
            add: Transition {
                NumberAnimation { properties: "y"; from: -20; duration: 360; easing.type: Easing.OutBack; easing.overshoot: 1.4 }
                NumberAnimation { properties: "scale"; from: 0.88; to: 1.0; duration: 360; easing.type: Easing.OutBack; easing.overshoot: 1.4 }
                NumberAnimation { properties: "opacity"; from: 0.0; to: 1.0; duration: 260 }
            }

            // Weightless fluid fade & collapse when a file completes
            remove: Transition {
                ParallelAnimation {
                    NumberAnimation { property: "opacity"; to: 0.0; duration: 180; easing.type: Easing.InCubic }
                    NumberAnimation { property: "scale"; to: 0.85; duration: 200; easing.type: Easing.InBack; easing.overshoot: 1.2 }
                }
            }

            // Physical momentum settling when siblings shift
            displaced: Transition {
                NumberAnimation { properties: "y"; duration: 280; easing.type: Easing.OutBack; easing.overshoot: 1.25 }
            }

            delegate: Rectangle {
                id: rowRect
                width: activeListView.width
                height: 48
                radius: 6
                color: rowMouse.containsMouse ? "#181D2A" : "#11141D"
                border.color: rowMouse.containsMouse ? "#38BDF8" : "#191E2B"
                border.width: 1
                transformOrigin: Item.Center

                // Newtonian physical spring hover reaction with inertia
                scale: rowMouse.pressed ? 0.98 : (rowMouse.containsMouse ? 1.012 : 1.0)
                Behavior on scale {
                    NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
                }

                Behavior on color {
                    ColorAnimation { duration: 160 }
                }
                Behavior on border.color {
                    ColorAnimation { duration: 160 }
                }

                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.ArrowCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 450
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
                            color: rowMouse.containsMouse ? "#FFFFFF" : "#E2E8F0"
                            elide: Text.ElideMiddle

                            Behavior on color { ColorAnimation { duration: 140 } }
                        }

                        Text {
                            text: (model.downloadedBytes || "0 B") + " / " + (model.fileSize || "-")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 10
                            color: rowMouse.containsMouse ? "#CBD5E1" : "#94A3B8"
                            Layout.alignment: Qt.AlignRight

                            Behavior on color { ColorAnimation { duration: 140 } }
                        }
                    }

                    // Line 2: Fluid Liquid Progress Bar + Percent + Speed + ETA
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        // Liquid progress track
                        Rectangle {
                            Layout.fillWidth: true
                            height: 6
                            radius: 3
                            color: "#1A2030"
                            clip: true

                            // Viscous progress fill
                            Rectangle {
                                id: progressFill
                                height: parent.height
                                radius: 3
                                width: {
                                    var p = model.progress || 0.0
                                    var clamped = Math.max(0.0, Math.min(1.0, p))
                                    return Math.max(clamped * parent.width, (model.percentage > 0 ? 5 : 0))
                                }
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0.0; color: "#0284C7" }
                                    GradientStop { position: 0.85; color: "#38BDF8" }
                                    GradientStop { position: 1.0; color: "#7DD3FC" }
                                }

                                // Fluid viscous easing with physical momentum
                                Behavior on width {
                                    NumberAnimation {
                                        duration: 380
                                        easing.type: Easing.OutCubic
                                    }
                                }

                                // Fluid leading-edge liquid glow
                                Rectangle {
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.bottom: parent.bottom
                                    width: 12
                                    radius: 3
                                    opacity: 0.65
                                    gradient: Gradient {
                                        orientation: Gradient.Horizontal
                                        GradientStop { position: 0.0; color: "transparent" }
                                        GradientStop { position: 1.0; color: "#FFFFFF" }
                                    }
                                    visible: progressFill.width > 12
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
                            text: tr("label_eta", "ETA") + ": " + (model.eta || "--")
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
