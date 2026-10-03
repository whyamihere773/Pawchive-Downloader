import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Storage (Gallery) ────────────────────────────────────────────────────────
// What takes up space in a folder: a breakdown by kind of file, the biggest folders
// (click to look inside) and the biggest files (jump to them in the gallery).
Item {
    id: root

    property var tools: null              // galleryTools
    property bool isOpen: false
    property string rootPath: ""          // where it was opened
    property string path: ""              // what is shown now (can drill into subfolders)
    property string stage: "idle"         // "scanning" | "result" | "error"
    property int token: -1
    property var result: ({})
    property var progress: ({})
    property string tab: "folders"        // "folders" | "files"

    signal openFolder(string path)        // show a folder in the gallery
    signal showFile(string path)          // reveal a file in the gallery

    anchors.fill: parent
    z: 9400
    opacity: isOpen ? 1 : 0
    visible: opacity > 0.005
    enabled: isOpen
    Behavior on opacity { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }

    readonly property var kindColors: ({ "Videos": "#8B5CF6", "Pictures": "#EC4899", "Archives": "#F59E0B", "Audio": "#10B981", "Other": "#64748B" })
    readonly property var kindIcons: ({ "Videos": "🎬", "Pictures": "🖼️", "Archives": "📦", "Audio": "🎵", "Other": "📄" })

    function open(p) {
        rootPath = p
        tab = "folders"
        isOpen = true
        root.forceActiveFocus()
        scan(p)
    }
    function close() {
        if (stage === "scanning" && tools) tools.cancelStorageScan()
        isOpen = false
    }
    function scan(p) {
        if (!tools) return
        path = p
        stage = "scanning"
        progress = ({})
        result = ({})
        token = tools.scanStorage(p)
    }
    function up() {
        var p = path.replace(/[\\\/]+$/, "")
        var i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"))
        if (i > 0) scan(p.substring(0, i + (p.charAt(i - 1) === ":" ? 1 : 0)))
    }
    function formatBytes(b) {
        if (!b || b <= 0) return "0 B"
        var u = ["B", "KB", "MB", "GB", "TB"], i = Math.min(u.length - 1, Math.floor(Math.log(b) / Math.log(1024)))
        return (b / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + " " + u[i]
    }
    function kindOf(ext) {
        var v = [".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".flv", ".wmv", ".mpg", ".mpeg", ".ts", ".3gp", ".ogv"]
        var p = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".heic", ".jxl", ".bmp", ".tif", ".tiff", ".psd", ".apng", ".jfif"]
        var a = [".zip", ".rar", ".7z", ".tar", ".gz", ".cbz", ".cbr"]
        var m = [".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus", ".wma"]
        if (v.indexOf(ext) >= 0) return "Videos"
        if (p.indexOf(ext) >= 0) return "Pictures"
        if (a.indexOf(ext) >= 0) return "Archives"
        if (m.indexOf(ext) >= 0) return "Audio"
        return "Other"
    }

    Connections {
        target: root.tools
        function onStorageProgress(t, p) { if (t === root.token) root.progress = p }
        function onStorageReady(t, r) {
            if (t !== root.token) return
            root.result = r
            root.stage = r.ok ? "result" : "error"
        }
    }

    Keys.onEscapePressed: root.close()
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Backspace && root.path !== root.rootPath) { root.up(); event.accepted = true }
    }

    // Backdrop: swallow clicks, hover and the wheel
    Rectangle {
        anchors.fill: parent
        color: "#060910"
        opacity: 0.88
        MouseArea { anchors.fill: parent; hoverEnabled: true; onClicked: root.close(); onWheel: (wheel) => wheel.accepted = true }
    }

    component SmallBtn: Rectangle {
        id: sb
        property string label: ""
        property string tip: ""
        signal clicked()
        implicitWidth: sbl.implicitWidth + 16
        implicitHeight: 24
        radius: 6
        color: sbm.containsMouse ? "#1E293B" : "#151B29"
        border.color: sbm.containsMouse ? "#38BDF8" : "#2E384D"
        Text { id: sbl; anchors.centerIn: parent; text: sb.label; font.family: "Segoe UI"; font.pixelSize: 11; font.weight: 600; color: "#E2E8F0" }
        Springy { hover: sbm.containsMouse; pressed: sbm.pressed }
        MouseArea {
            id: sbm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            onClicked: sb.clicked()
            ToolTip.visible: containsMouse && sb.tip.length > 0
            ToolTip.delay: 400
            ToolTip.text: sb.tip
        }
    }

    Rectangle {
        id: card
        scale: root.isOpen ? 1.0 : 0.9
        Behavior on scale { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.0008 } }
        anchors.centerIn: parent
        width: Math.min(780, parent.width - 32)
        height: Math.min(640, parent.height - 32)
        radius: 14
        color: "#101420"
        border.color: "#2A364E"
        MouseArea { anchors.fill: parent }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Text { text: "💾"; font.pixelSize: 22 }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1
                    Text {
                        text: "Storage" + (root.stage === "result" ? ":  " + root.formatBytes(root.result.totalBytes) + "  ·  " + root.result.totalFiles + " files" : "")
                        font.family: "Segoe UI"; font.pixelSize: 15; font.weight: 700; color: "#F1F5F9"
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.path
                        elide: Text.ElideMiddle
                        font.family: "Segoe UI"; font.pixelSize: 10; color: "#64748B"
                    }
                }
                SmallBtn { visible: root.path !== root.rootPath; label: "↑ Up"; tip: "Back to the parent folder (Backspace)"; onClicked: root.up() }
                SmallBtn { label: "↗ Open here"; tip: "Show this folder in the gallery"; onClicked: { root.openFolder(root.path); root.close() } }
                SmallBtn { label: "↻"; tip: "Count again"; onClicked: root.scan(root.path) }
                Rectangle {
                    width: 26; height: 26; radius: 6
                    color: stClose.containsMouse ? "#3A1620" : "transparent"
                    Text { anchors.centerIn: parent; text: "✕"; color: "#94A3B8"; font.pixelSize: 12 }
                    MouseArea { id: stClose; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.close() }
                }
            }

            // Scanning
            ColumnLayout {
                visible: root.stage === "scanning"
                Layout.fillWidth: true
                spacing: 8
                Text {
                    text: "Counting…  " + (root.progress.files || 0) + " files  ·  " + root.formatBytes(root.progress.bytes || 0)
                    font.family: "Segoe UI"; font.pixelSize: 12; color: "#CBD5E1"
                }
                Text {
                    visible: !!root.progress.folder
                    Layout.fillWidth: true
                    text: root.progress.folder || ""
                    elide: Text.ElideMiddle
                    font.family: "Segoe UI"; font.pixelSize: 10; color: "#64748B"
                }
                Rectangle {
                    Layout.fillWidth: true
                    height: 4; radius: 2; color: "#1E2536"; clip: true
                    Rectangle {
                        width: parent.width * 0.3; height: parent.height; radius: 2; color: "#38BDF8"
                        NumberAnimation on x { from: -parent.width * 0.3; to: parent.width; duration: 1100; loops: Animation.Infinite; running: root.stage === "scanning" }
                    }
                }
            }

            Text {
                visible: root.stage === "error"
                text: "⚠ " + (root.result.error || "Couldn't read this folder.")
                color: "#FCA5A5"; font.family: "Segoe UI"; font.pixelSize: 12
            }

            // Kind of files: one stacked bar + legend
            ColumnLayout {
                visible: root.stage === "result" && (root.result.totalBytes || 0) > 0
                Layout.fillWidth: true
                spacing: 6
                Row {
                    id: kindBar
                    Layout.fillWidth: true
                    height: 14
                    clip: true
                    Repeater {
                        model: root.result.kinds || []
                        delegate: Rectangle {
                            width: kindBar.width * modelData.share
                            height: 14
                            color: root.kindColors[modelData.name] || "#64748B"
                        }
                    }
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 14
                    Repeater {
                        model: root.result.kinds || []
                        delegate: Row {
                            spacing: 5
                            Rectangle { width: 9; height: 9; radius: 2; color: root.kindColors[modelData.name] || "#64748B"; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                text: root.kindIcons[modelData.name] + " " + modelData.name + "  " + root.formatBytes(modelData.bytes) + "  (" + Math.round(modelData.share * 100) + "%)"
                                font.family: "Segoe UI"; font.pixelSize: 11; color: "#CBD5E1"
                            }
                        }
                    }
                }
            }

            // Tabs
            Row {
                visible: root.stage === "result"
                spacing: 6
                Repeater {
                    model: [["folders", "📁 Biggest folders"], ["files", "📄 Biggest files"]]
                    delegate: Rectangle {
                        readonly property bool on: root.tab === modelData[0]
                        width: tabLabel.implicitWidth + 22
                        height: 28
                        radius: 14
                        color: on ? "#0F2A3A" : (tabMouse.containsMouse ? "#1A2234" : "transparent")
                        border.color: on ? "#38BDF8" : "#2A364E"
                        Text { id: tabLabel; anchors.centerIn: parent; text: modelData[1]; font.family: "Segoe UI"; font.pixelSize: 11; font.weight: on ? 700 : 500; color: on ? "#7DD3FC" : "#CBD5E1" }
                        MouseArea { id: tabMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.tab = modelData[0] }
                    }
                }
            }

            // Biggest folders
            ListView {
                id: folderList
                visible: root.stage === "result" && root.tab === "folders"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 3
                model: root.stage === "result" ? (root.result.folders || []) : []
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Rectangle {
                    width: folderList.width - 10
                    height: 40
                    radius: 7
                    color: rowMouse.containsMouse ? "#18202F" : "#121826"
                    border.color: rowMouse.containsMouse ? "#38BDF8" : "#1C2436"
                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: modelData.isLoose ? Qt.ArrowCursor : Qt.PointingHandCursor
                        onClicked: if (!modelData.isLoose) root.scan(modelData.path)
                        ToolTip.visible: containsMouse && !modelData.isLoose
                        ToolTip.delay: 600
                        ToolTip.text: "Click to see what's inside"
                    }
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 8
                        spacing: 10
                        Text { text: modelData.isLoose ? "📄" : "📁"; font.pixelSize: 14 }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            Text { Layout.fillWidth: true; text: modelData.name; elide: Text.ElideMiddle; font.family: "Segoe UI"; font.pixelSize: 12; font.weight: 600; color: "#E2E8F0" }
                            // Share of the total, as a bar that springs out
                            Rectangle {
                                Layout.fillWidth: true
                                height: 4; radius: 2; color: "#1E2536"
                                Rectangle {
                                    property real grow: 0
                                    Component.onCompleted: grow = 1
                                    Behavior on grow { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.002 } }
                                    width: parent.width * Math.max(0.005, modelData.share) * grow
                                    height: parent.height; radius: 2
                                    color: index === 0 ? "#38BDF8" : "#3B82F6"
                                }
                            }
                        }
                        Text { text: root.formatBytes(modelData.bytes); font.family: "Segoe UI"; font.pixelSize: 12; font.weight: 700; color: "#F1F5F9"; Layout.preferredWidth: 72; horizontalAlignment: Text.AlignRight }
                        Text { text: Math.round(modelData.share * 100) + "%"; font.family: "Segoe UI"; font.pixelSize: 11; color: "#94A3B8"; Layout.preferredWidth: 36; horizontalAlignment: Text.AlignRight }
                        Text { text: modelData.files + " files"; font.family: "Segoe UI"; font.pixelSize: 10; color: "#64748B"; Layout.preferredWidth: 64; horizontalAlignment: Text.AlignRight }
                        SmallBtn { label: "↗"; tip: "Open in the gallery"; onClicked: { root.openFolder(modelData.path); root.close() } }
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: folderList.count === 0
                    text: "This folder is empty."
                    color: "#64748B"; font.family: "Segoe UI"; font.pixelSize: 12
                }
            }

            // Biggest files
            ListView {
                id: fileList
                visible: root.stage === "result" && root.tab === "files"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 3
                model: root.stage === "result" ? (root.result.largest || []) : []
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Rectangle {
                    width: fileList.width - 10
                    height: 38
                    radius: 7
                    color: fRowMouse.containsMouse ? "#18202F" : "#121826"
                    border.color: fRowMouse.containsMouse ? "#38BDF8" : "#1C2436"
                    MouseArea { id: fRowMouse; anchors.fill: parent; hoverEnabled: true }
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 8
                        spacing: 10
                        Text { text: root.kindIcons[root.kindOf(modelData.ext)] || "📄"; font.pixelSize: 14 }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            Text { Layout.fillWidth: true; text: modelData.name; elide: Text.ElideMiddle; font.family: "Segoe UI"; font.pixelSize: 12; color: "#E2E8F0" }
                            Text { Layout.fillWidth: true; visible: !!modelData.folder; text: "📁 " + modelData.folder; elide: Text.ElideMiddle; font.family: "Segoe UI"; font.pixelSize: 10; color: "#64748B" }
                        }
                        Text { text: root.formatBytes(modelData.size); font.family: "Segoe UI"; font.pixelSize: 12; font.weight: 700; color: "#F1F5F9"; Layout.preferredWidth: 72; horizontalAlignment: Text.AlignRight }
                        SmallBtn { label: "Show"; tip: "Find this file in the gallery"; onClicked: { root.showFile(modelData.path); root.close() } }
                    }
                }
            }
        }
    }
}
