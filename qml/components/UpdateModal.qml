import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Update dialog ────────────────────────────────────────────────────────────
// Shows what's new and hands over to the updater, which installs the update after the app
// has closed. Weight-based motion: the card settles heavily, chips and buttons are light.
Rectangle {
    id: root
    anchors.fill: parent
    z: 1100
    color: "#CC07090E"

    property var updater: null
    property bool isOpen: false
    property bool confirmStop: false       // second click needed while downloads are running

    readonly property bool hasUpdate: !!updater && updater.updateAvailable
    readonly property bool checking: !!updater && updater.isChecking
    readonly property bool downloadsRunning: (typeof appBridge !== "undefined") && !!appBridge && appBridge.isDownloading
    readonly property string ff: Qt.platform.os === "windows" ? "Segoe UI" : ""

    opacity: isOpen ? 1 : 0
    visible: opacity > 0.005
    enabled: isOpen
    Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
    onIsOpenChanged: if (!isOpen) confirmStop = false

    // Swallow clicks, hover and the wheel; clicking outside closes
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onClicked: root.isOpen = false
        onWheel: (wheel) => wheel.accepted = true
    }

    component Chip: Rectangle {
        property string label: ""
        property color tint: "#94A3B8"
        implicitWidth: chipText.implicitWidth + 16
        implicitHeight: 24
        radius: 5
        color: Qt.rgba(tint.r, tint.g, tint.b, 0.1)
        border.color: Qt.rgba(tint.r, tint.g, tint.b, 0.3)
        Text {
            id: chipText
            anchors.centerIn: parent
            text: parent.label
            font.family: "Cascadia Code, Consolas, monospace"; font.pixelSize: 12; font.weight: Font.Medium
            color: parent.tint
        }
    }

    component Btn: Rectangle {
        id: b
        property string label: ""
        property bool primary: false
        property bool warn: false
        signal clicked()
        // Same look and spring as StyledButton
        implicitWidth: Math.max(80, bt.implicitWidth + 24)
        implicitHeight: 34
        radius: 8
        color: primary ? (warn ? (bm.pressed ? "#B45309" : (bm.containsMouse ? "#D97706" : "#F59E0B"))
                               : (bm.pressed ? "#0284C7" : (bm.containsMouse ? "#0EA5E9" : "#38BDF8")))
                       : (bm.pressed ? "#1E222A" : (bm.containsMouse ? "#2C3340" : "#222732"))
        border.color: primary ? (warn ? "#F59E0B" : "#38BDF8") : (bm.containsMouse ? "#475569" : "#333A48")
        Behavior on color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }
        scale: bm.pressed ? 0.945 : (bm.containsMouse ? 1.025 : 1.0)
        Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.35; mass: 0.75; epsilon: 0.005 } }
        Text {
            id: bt
            anchors.centerIn: parent
            text: b.label
            font.family: root.ff; font.pixelSize: 12; font.weight: Font.Medium
            color: b.primary ? "#0F172A" : "#E2E8F0"
        }
        MouseArea { id: bm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: b.clicked() }
    }

    Rectangle {
        id: card
        anchors.centerIn: parent
        width: Math.min(root.width - 40, 560)
        height: Math.min(root.height - 40, body.implicitHeight + 44)
        radius: 16
        color: "#131722"
        border.color: "#2D3748"
        border.width: 1.5
        clip: true
        // heavy card: drops in and settles
        property real drop: root.isOpen ? 1 : 0
        Behavior on drop { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.002 } }
        scale: 0.9 + 0.1 * drop
        transform: Translate { y: (1 - card.drop) * 24 }
        MouseArea { anchors.fill: parent }   // clicks inside don't close it

        ColumnLayout {
            id: body
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 22
            spacing: 16

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                // Same flat icon circle as the app's other dialogs
                Rectangle {
                    width: 44; height: 44; radius: 22
                    color: "#1E293B"
                    border.color: root.hasUpdate ? "#38BDF8" : "#34D399"
                    border.width: 1.5
                    Behavior on border.color { ColorAnimation { duration: 200 } }
                    Text {
                        anchors.centerIn: parent
                        text: root.hasUpdate ? "↑" : "✓"
                        font.pixelSize: 19; font.bold: true
                        color: root.hasUpdate ? "#38BDF8" : "#34D399"
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: root.checking ? "Checking for updates…" : (root.hasUpdate ? "An update is ready" : "Pawchive is up to date")
                        font.family: root.ff; font.pixelSize: 18; font.weight: Font.Bold; color: "#F8FAFC"
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.updater ? root.updater.statusMessage : ""
                        visible: text.length > 0 && !root.checking
                        elide: Text.ElideRight
                        font.family: root.ff; font.pixelSize: 12; color: "#94A3B8"
                    }
                }
                Rectangle {
                    width: 28; height: 28; radius: 14
                    color: xm.containsMouse ? "#2A3346" : "transparent"
                    Text { anchors.centerIn: parent; text: "×"; font.pixelSize: 18; color: "#94A3B8" }
                    MouseArea { id: xm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.isOpen = false }
                }
            }

            // Checking shimmer
            Rectangle {
                Layout.fillWidth: true
                height: 4; radius: 2
                color: "#161B26"
                visible: root.checking
                clip: true
                Rectangle {
                    id: shim
                    width: parent.width * 0.3; height: parent.height; radius: 2
                    color: "#38BDF8"
                    SequentialAnimation on x {
                        running: root.checking; loops: Animation.Infinite
                        NumberAnimation { from: -shim.width; to: shim.parent.width; duration: 1200; easing.type: Easing.InOutQuad }
                    }
                }
            }

            // What you're running: version + edition (Windows build, Linux build or source code)
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                visible: !!root.updater
                radius: 10
                color: "#0D1119"
                border.color: "#1F2836"
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 8
                    Text {
                        text: "You're using"
                        font.family: root.ff; font.pixelSize: 12; color: "#64748B"
                    }
                    Text {
                        text: root.updater ? root.updater.currentVersion : ""
                        font.family: "Cascadia Code, Consolas, monospace"; font.pixelSize: 12; color: "#E2E8F0"
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        Layout.preferredHeight: 22
                        Layout.preferredWidth: editionLabel.implicitWidth + 16
                        radius: 5
                        color: "#161E2E"
                        border.color: "#1E293B"
                        Text {
                            id: editionLabel
                            anchors.centerIn: parent
                            text: root.updater ? root.updater.edition : ""
                            font.family: root.ff; font.pixelSize: 11; font.weight: Font.Medium
                            color: "#A78BFA"
                        }
                    }
                }
            }

            // Versions
            RowLayout {
                spacing: 10
                visible: root.hasUpdate
                Chip { label: "v" + (root.updater ? root.updater.currentVersion : ""); tint: "#94A3B8" }
                Text { visible: root.hasUpdate; text: "→"; font.pixelSize: 16; color: "#64748B" }
                Chip {
                    visible: root.hasUpdate
                    label: "v" + (root.updater ? root.updater.latestVersion : "")
                    tint: "#38BDF8"
                    property real pop: root.isOpen && root.hasUpdate ? 1 : 0
                    Behavior on pop { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.002 } }
                    scale: 0.7 + 0.3 * pop
                    opacity: pop
                }
                Text {
                    visible: root.hasUpdate && root.updater.releaseDate.length > 0
                    text: root.updater ? root.updater.releaseDate : ""
                    font.family: root.ff; font.pixelSize: 12; color: "#64748B"
                }
            }

            // What's new
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(180, notes.implicitHeight + 46)
                visible: root.hasUpdate && notes.text.length > 0
                radius: 12
                color: "#0D1119"
                border.color: "#1F2836"
                Text {
                    x: 14; y: 11
                    text: "WHAT'S NEW"
                    font.family: root.ff; font.pixelSize: 11; font.weight: Font.Bold; font.letterSpacing: 1
                    color: "#64748B"
                }
                Flickable {
                    anchors.fill: parent
                    anchors.topMargin: 32
                    anchors.margins: 14
                    contentHeight: notes.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    Text {
                        id: notes
                        width: parent.width
                        text: root.updater ? root.updater.releaseNotes : ""
                        textFormat: Text.MarkdownText
                        wrapMode: Text.WordWrap
                        font.family: root.ff; font.pixelSize: 12; color: "#CBD5E1"
                        onLinkActivated: (link) => Qt.openUrlExternally(link)
                    }
                }
            }

            // Running downloads: they stop, and Pawchive offers to resume them when it reopens
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: warnText.implicitHeight + 22
                visible: root.hasUpdate && root.downloadsRunning
                radius: 10
                color: root.confirmStop ? "#2A1F0A" : "#1A1710"
                border.color: root.confirmStop ? "#F59E0B" : "#5B4512"
                Behavior on color { ColorAnimation { duration: 160 } }
                Text {
                    id: warnText
                    anchors.fill: parent
                    anchors.margins: 11
                    wrapMode: Text.WordWrap
                    text: "Downloads are running. Updating stops them; Pawchive will offer to resume them when it opens again."
                    font.family: root.ff; font.pixelSize: 12; color: "#FDE68A"
                }
            }

            Text {
                Layout.fillWidth: true
                visible: root.hasUpdate
                wrapMode: Text.WordWrap
                text: "Pawchive closes, the updater installs the new version (your settings, downloads and logs are never touched), and Pawchive opens again."
                font.family: root.ff; font.pixelSize: 12; color: "#64748B"
            }

            // Buttons
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Btn { label: root.hasUpdate ? "Later" : "Close"; onClicked: root.isOpen = false }
                Text {
                    visible: !!root.updater && root.updater.releaseUrl.length > 0
                    text: "Release page"
                    font.family: root.ff; font.pixelSize: 12; font.underline: rpm.containsMouse
                    color: "#64748B"
                    MouseArea { id: rpm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.updater.openReleasePage() }
                }
                Item { Layout.fillWidth: true }
                Btn {
                    visible: !root.hasUpdate && !root.checking
                    label: "Check again"
                    onClicked: root.updater.checkForUpdates(false)
                }
                Btn {
                    visible: root.hasUpdate
                    primary: true
                    warn: root.confirmStop
                    label: root.updater && root.updater.isLaunching ? "Starting the updater…"
                         : (root.confirmStop ? "Stop downloads and update" : "Update now")
                    onClicked: {
                        if (root.downloadsRunning && !root.confirmStop) { root.confirmStop = true; return }
                        root.updater.startUpdate()
                    }
                }
            }
        }
    }
}
