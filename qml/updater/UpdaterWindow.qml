import QtQuick
import QtQuick.Window
import QtQuick.Layouts

// Looks like the app itself (same colours, cards, buttons and progress bar as Theme.qml).
Window {
    id: win
    visible: true
    width: 560
    height: 540
    minimumWidth: 480
    minimumHeight: 460
    title: "Pawchive Downloader Update"
    color: "#0F1117"

    readonly property string ff: "Segoe UI, Inter, Roboto, sans-serif"
    readonly property string mono: "Cascadia Code, Consolas, Fira Code, monospace"
    readonly property color primary: "#38BDF8"
    readonly property color success: "#10B981"
    readonly property color danger: "#EF4444"
    readonly property color warning: "#F59E0B"
    readonly property bool running: upd.phase === "running"
    readonly property color tone: upd.phase === "error" ? (upd.code === "cancelled" ? warning : danger)
                                : (running ? primary : success)

    function activeIndex() {
        var s = upd.stepStates
        for (var i = 0; i < s.length; i++)
            if (s[i] === "active" || s[i] === "failed") return i
        return -1
    }

    onClosing: (close) => {
        if (!upd.canClose()) { close.accepted = false; upd.nudge(); return }
        upd.windowClosing()
    }

    // ── Pieces shared with the app's look ──
    component Btn: Rectangle {
        id: btn
        property string label: ""
        property string variant: "default"        // default | primary | ghost
        property bool active: true
        signal clicked()
        implicitWidth: Math.max(80, btnText.implicitWidth + 24)
        implicitHeight: 34
        radius: 8
        color: !active ? "#1F232B"
             : variant === "primary" ? (btnMouse.pressed ? "#0284C7" : (btnMouse.containsMouse ? "#0EA5E9" : "#38BDF8"))
             : variant === "ghost" ? (btnMouse.containsMouse ? "#242B38" : "transparent")
             : (btnMouse.pressed ? "#1E222A" : (btnMouse.containsMouse ? "#2C3340" : "#222732"))
        border.color: !active ? "#2A303C" : variant === "ghost" ? "transparent"
                    : variant === "primary" ? "#38BDF8" : (btnMouse.containsMouse ? "#475569" : "#333A48")
        Behavior on color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }
        // light spring, same as StyledButton
        scale: btnMouse.pressed ? 0.945 : (btnMouse.containsMouse && active ? 1.025 : 1.0)
        Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.35; mass: 0.75; epsilon: 0.005 } }
        Text {
            id: btnText
            anchors.centerIn: parent
            text: btn.label
            font.family: win.ff; font.pixelSize: 12; font.weight: Font.Medium
            color: !btn.active ? "#64748B" : btn.variant === "primary" ? "#0F172A"
                 : (btn.variant === "ghost" && btnMouse.containsMouse ? "#38BDF8" : "#E2E8F0")
        }
        MouseArea {
            id: btnMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }
    }

    component Card: Rectangle {
        id: card
        property int delay: 0
        property real enter: 0
        color: "#181B22"
        border.color: "#282E3D"
        radius: 10
        // settles into place when the window opens (medium weight)
        opacity: enter
        transform: Translate { y: (1 - card.enter) * 14 }
        Behavior on enter { SpringAnimation { spring: 4.0; damping: 0.38; mass: 1.0; epsilon: 0.002 } }
        Timer { running: true; interval: card.delay + 40; onTriggered: card.enter = 1 }
    }

    // ── Header (like the app's top bar) ──
    Rectangle {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 64
        color: "#151820"
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: "#1E2330" }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 20
            anchors.rightMargin: 20
            spacing: 12

            Item {
                Layout.preferredWidth: 30
                Layout.preferredHeight: 30
                Image {
                    id: logo
                    anchors.fill: parent
                    source: upd.iconUrl
                    sourceSize: Qt.size(64, 64)
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    visible: status === Image.Ready
                }
                Rectangle {
                    anchors.fill: parent
                    visible: logo.status !== Image.Ready
                    radius: 8
                    color: "#1E293B"
                    border.color: "#2A303F"
                    Text { anchors.centerIn: parent; text: "P"; font.family: win.ff; font.pixelSize: 15; font.bold: true; color: win.primary }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1
                Text {
                    text: "Pawchive Downloader"
                    font.family: win.ff; font.pixelSize: 15; font.weight: Font.DemiBold
                    color: "#F1F5F9"
                }
                Row {
                    spacing: 6
                    Text {
                        text: upd.phase === "success" ? "Updated" : (upd.phase === "uptodate" ? "Up to date"
                            : (upd.phase === "error" ? "Update stopped" : "Updating"))
                        font.family: win.ff; font.pixelSize: 12; color: "#94A3B8"
                    }
                    Text {
                        visible: upd.fromVersion.length > 0
                        text: upd.fromVersion
                        font.family: win.mono; font.pixelSize: 11; color: "#94A3B8"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        visible: upd.fromVersion.length > 0 && upd.toVersion.length > 0
                        text: "→"
                        font.pixelSize: 12; color: "#64748B"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        visible: upd.toVersion.length > 0
                        text: upd.toVersion
                        font.family: win.mono; font.pixelSize: 11; color: win.primary
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    // Which edition is being updated: Windows build, Linux build or source code
                    Rectangle {
                        visible: upd.edition.length > 0
                        anchors.verticalCenter: parent.verticalCenter
                        width: editionText.implicitWidth + 12
                        height: 18
                        radius: 4
                        color: "#161E2E"
                        border.color: "#1E293B"
                        Text {
                            id: editionText
                            anchors.centerIn: parent
                            text: upd.edition
                            font.family: win.ff; font.pixelSize: 10; font.weight: Font.Medium
                            color: "#A78BFA"
                        }
                    }
                }
            }
            Item { Layout.fillWidth: true }

            // Status badge (like the inline badges next to the app's progress bar)
            Rectangle {
                Layout.preferredHeight: 22
                Layout.preferredWidth: badgeText.implicitWidth + 16
                radius: 5
                color: Qt.rgba(win.tone.r, win.tone.g, win.tone.b, 0.12)
                border.color: Qt.rgba(win.tone.r, win.tone.g, win.tone.b, 0.35)
                Behavior on color { ColorAnimation { duration: 220 } }
                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: win.running ? ("Step " + Math.max(1, win.activeIndex() + 1) + " of " + Math.max(1, upd.stepLabels.length))
                        : (upd.phase === "error" ? (upd.code === "cancelled" ? "Cancelled" : "Stopped") : "Done")
                    font.family: win.mono; font.pixelSize: 10; font.weight: Font.Medium
                    color: win.tone
                }
            }
        }
    }

    // ── Body ──
    Item {
        id: body
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: footer.top
        anchors.margins: 20

        // a short damped shake when something needs attention
        property real kick: 0
        transform: Translate { x: body.kick }
        Behavior on kick { SpringAnimation { spring: 9; damping: 0.2; mass: 0.5; epsilon: 0.05 } }
        property int shakes: upd.shake
        onShakesChanged: { kickTimer.restart(); body.kick = 10 }
        Timer { id: kickTimer; interval: 40; onTriggered: body.kick = 0 }

        ColumnLayout {
            anchors.fill: parent
            spacing: 12

            // Progress + steps
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: progressCol.implicitHeight + 28
                ColumnLayout {
                    id: progressCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 14
                    spacing: 10

                    // Current step + detail
                    RowLayout {
                        Layout.fillWidth: true
                        visible: win.running
                        spacing: 8
                        Text {
                            text: (upd.stepLabels[win.activeIndex()] || "Starting") + ":"
                            font.family: win.ff; font.pixelSize: 11; font.weight: Font.DemiBold
                            color: win.primary
                        }
                        Text {
                            Layout.fillWidth: true
                            text: upd.detail
                            elide: Text.ElideRight
                            font.family: win.mono; font.pixelSize: 11; color: "#94A3B8"
                        }
                        Text {
                            visible: upd.progress >= 0
                            text: Math.round(upd.progress * 100) + "%"
                            font.family: win.mono; font.pixelSize: 11; color: "#CBD5E1"
                        }
                    }

                    // Progress bar (spring fill; a sliding segment when the size isn't known)
                    Rectangle {
                        id: track
                        Layout.fillWidth: true
                        Layout.preferredHeight: 6
                        visible: win.running
                        radius: 3
                        color: "#1A2234"
                        clip: true
                        property real shown: upd.progress < 0 ? 0 : upd.progress
                        Behavior on shown { SpringAnimation { spring: 3.0; damping: 0.42; mass: 1.0; epsilon: 0.001 } }
                        Rectangle {
                            visible: upd.progress >= 0
                            width: track.width * Math.max(0, Math.min(1, track.shown))
                            height: parent.height
                            radius: 3
                            color: win.primary
                        }
                        Rectangle {
                            id: slider
                            visible: upd.progress < 0
                            width: track.width * 0.25
                            height: parent.height
                            radius: 3
                            color: win.primary
                            opacity: 0.8
                            SequentialAnimation on x {
                                running: slider.visible
                                loops: Animation.Infinite
                                NumberAnimation { from: -slider.width; to: track.width; duration: 1400; easing.type: Easing.InOutQuad }
                            }
                        }
                    }

                    // Result (drops in with weight when the update ends)
                    Rectangle {
                        id: result
                        Layout.fillWidth: true
                        Layout.preferredHeight: resultCol.implicitHeight + 22
                        visible: !win.running
                        radius: 8
                        color: "#0B0E14"
                        border.color: Qt.rgba(win.tone.r, win.tone.g, win.tone.b, 0.45)
                        property real drop: win.running ? 0 : 1
                        Behavior on drop { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.002 } }
                        opacity: drop
                        transform: Translate { y: (1 - result.drop) * -10 }
                        Rectangle { x: 0; y: 8; width: 3; height: parent.height - 16; radius: 1.5; color: win.tone }
                        ColumnLayout {
                            id: resultCol
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.leftMargin: 16
                            anchors.rightMargin: 12
                            anchors.topMargin: 11
                            spacing: 5
                            Text {
                                Layout.fillWidth: true
                                text: upd.title
                                wrapMode: Text.WordWrap
                                font.family: win.ff; font.pixelSize: 13; font.bold: true; color: "#F1F5F9"
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: text.length > 0
                                text: upd.text
                                wrapMode: Text.WordWrap
                                font.family: win.ff; font.pixelSize: 12; color: "#CBD5E1"
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: upd.warning.length > 0
                                text: "⚠ " + upd.warning
                                wrapMode: Text.WordWrap
                                font.family: win.ff; font.pixelSize: 12; color: "#FBBF24"
                            }
                            Text {
                                visible: upd.countdown > 0
                                text: "Opening Pawchive in " + upd.countdown + "s"
                                font.family: win.mono; font.pixelSize: 11; color: "#64748B"
                            }
                        }
                    }

                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: "#222A3A" }

                    // Steps
                    Column {
                        Layout.fillWidth: true
                        spacing: 4
                        Repeater {
                            model: upd.stepLabels
                            delegate: Item {
                                id: stepRow
                                width: parent.width
                                height: 22
                                readonly property string st: upd.stepStates[index] || "pending"

                                Item {
                                    id: mark
                                    width: 16; height: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 6; height: 6; radius: 3
                                        color: "#334155"
                                        visible: stepRow.st === "pending"
                                    }
                                    Canvas {
                                        id: spinner
                                        anchors.centerIn: parent
                                        width: 14; height: 14
                                        visible: stepRow.st === "active"
                                        onPaint: {
                                            var c = getContext("2d")
                                            c.reset()
                                            c.lineWidth = 2
                                            c.strokeStyle = "#38BDF8"
                                            c.lineCap = "round"
                                            c.beginPath()
                                            c.arc(7, 7, 5.5, 0, Math.PI * 1.5)
                                            c.stroke()
                                        }
                                        RotationAnimation on rotation {
                                            running: spinner.visible
                                            loops: Animation.Infinite
                                            from: 0; to: 360; duration: 900
                                        }
                                    }
                                    Text {
                                        anchors.centerIn: parent
                                        text: stepRow.st === "failed" ? "✕" : (stepRow.st === "skipped" ? "–" : "✓")
                                        visible: pop > 0.01
                                        font.family: win.ff; font.pixelSize: 13; font.bold: true
                                        color: stepRow.st === "failed" ? win.danger : (stepRow.st === "skipped" ? "#475569" : win.success)
                                        // light spring pop when a step finishes
                                        property real pop: (stepRow.st === "done" || stepRow.st === "failed" || stepRow.st === "skipped") ? 1 : 0
                                        Behavior on pop { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.002 } }
                                        scale: pop
                                    }
                                }
                                Text {
                                    anchors.left: mark.right
                                    anchors.leftMargin: 10
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    elide: Text.ElideRight
                                    text: modelData + (stepRow.st === "skipped" ? "  ·  not needed" : "")
                                    font.family: win.ff
                                    font.pixelSize: 12
                                    font.weight: stepRow.st === "active" ? Font.Medium : Font.Normal
                                    color: stepRow.st === "active" ? "#F1F5F9" : (stepRow.st === "done" ? "#94A3B8"
                                         : (stepRow.st === "failed" ? "#FCA5A5" : "#64748B"))
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                            }
                        }
                    }
                }
            }

            // What's new (CardSection style)
            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                delay: 70
                visible: upd.notes.length > 0
                clip: true
                Row {
                    id: notesHead
                    x: 14; y: 12
                    spacing: 8
                    Text { text: "📝"; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "What's new" + (upd.toVersion.length > 0 ? " in " + upd.toVersion : "")
                        font.family: win.ff; font.pixelSize: 12; font.weight: Font.DemiBold
                        color: "#CBD5E1"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                Flickable {
                    id: notesFlick
                    anchors.fill: parent
                    anchors.topMargin: 40
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    anchors.bottomMargin: 10
                    contentHeight: notesText.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    Text {
                        id: notesText
                        width: notesFlick.width - 8
                        text: upd.notes
                        textFormat: Text.MarkdownText
                        wrapMode: Text.WordWrap
                        font.family: win.ff; font.pixelSize: 12; color: "#CBD5E1"
                        linkColor: win.primary
                        onLinkActivated: (link) => Qt.openUrlExternally(link)
                    }
                }
                // thin scroll indicator
                Rectangle {
                    visible: notesFlick.contentHeight > notesFlick.height
                    x: parent.width - 6
                    y: notesFlick.y + notesFlick.visibleArea.yPosition * notesFlick.height
                    width: 3
                    height: notesFlick.visibleArea.heightRatio * notesFlick.height
                    radius: 1.5
                    color: "#334155"
                }
            }
            Item { Layout.fillHeight: true; visible: upd.notes.length === 0 }
        }
    }

    // ── Footer ──
    Rectangle {
        id: footer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 58
        color: "#151820"
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 1; color: "#1E2330" }

        Btn {
            anchors.left: parent.left
            anchors.leftMargin: 20
            anchors.verticalCenter: parent.verticalCenter
            visible: upd.hasLog && upd.phase === "error"
            variant: "ghost"
            label: "Show log"
            onClicked: upd.act("log")
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            Btn {
                visible: win.running
                label: "Cancel"
                active: upd.canCancel
                onClicked: upd.canCancel ? upd.cancel() : upd.nudge()
            }
            Repeater {
                model: upd.actions.slice().reverse()       // main action on the right
                delegate: Btn {
                    readonly property var names: ({
                        "open": "Open Pawchive", "close": "Close", "retry": "Try again",
                        "admin": "Try again as administrator", "stash": "Save my changes and update",
                        "keep": "Keep my changes", "archive": "Download the files instead"
                    })
                    label: names[modelData] || modelData
                    variant: index === upd.actions.length - 1 ? "primary" : "default"
                    onClicked: upd.act(modelData)
                }
            }
        }
    }
}
