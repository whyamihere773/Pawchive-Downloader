import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Archive Viewer ──────────────────────────────────────────────────────────
// Browse a ZIP / 7Z / RAR / TAR… without extracting it. Images and videos open
// in the Lightbox (just the current folder's media is unpacked to a temporary
// cache); other files open in their default app.
Item {
    id: root

    property var bridge: null       // appBridge (open in default app)
    property var archiver: null     // galleryArchiveBridge
    property var lightbox: null     // MediaLightboxModal
    property bool isOpen: false

    property var archive: null      // the gallery item of the archive file
    property string password: ""
    property var listing: ({})
    property var entries: []
    property string curDir: ""
    property string errorText: ""
    property bool needsPassword: false
    property bool preparing: false
    property string prepareText: ""
    property int previewToken: -1
    property var pendingOpen: null  // { entry, mediaPaths } waiting for previewReady

    signal extractAllRequested(var item)

    anchors.fill: parent
    z: 9200
    // Fades in / out (weight-based motion); no input while closing
    opacity: isOpen ? 1 : 0
    visible: opacity > 0.005
    enabled: isOpen
    Behavior on opacity { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
    readonly property var imageExts: [".jpg", ".jpeg", ".jpe", ".jfif", ".pjpeg", ".pjp", ".png", ".apng", ".gif", ".webp", ".avif", ".heic", ".heif", ".jxl", ".bmp", ".dib", ".svg", ".svgz", ".ico", ".cur", ".tif", ".tiff", ".tga", ".psd", ".jp2", ".j2k", ".dds", ".qoi", ".pcx", ".ppm", ".pgm", ".pbm", ".xbm", ".xpm", ".icns", ".wbmp"]
    readonly property var videoExts: [".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".flv", ".f4v", ".wmv", ".asf", ".mpg", ".mpeg", ".m2v", ".ts", ".mts", ".m2ts", ".3gp", ".3g2", ".ogv", ".vob", ".divx"]
    readonly property var audioExts: [".mp3", ".flac", ".wav", ".ogg", ".oga", ".m4a", ".aac", ".opus", ".wma", ".aiff", ".aif", ".alac", ".mka"]

    function extOf(name) {
        var dot = (name || "").lastIndexOf(".")
        return dot > 0 ? name.substring(dot).toLowerCase() : ""
    }
    function kindOf(e) {
        if (e.is_dir) return "folder"
        var x = extOf(e.name)
        if (imageExts.indexOf(x) >= 0) return "image"
        if (videoExts.indexOf(x) >= 0) return "video"
        if (audioExts.indexOf(x) >= 0) return "audio"
        return "other"
    }
    function iconOf(e) {
        var k = kindOf(e)
        return k === "folder" ? "📁" : (k === "image" ? "🖼️" : (k === "video" ? "🎬" : (k === "audio" ? "🎵" : "📄")))
    }
    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "0 B"
        var k = 1024, sizes = ["B", "KB", "MB", "GB", "TB"]
        var i = Math.max(0, Math.min(sizes.length - 1, Math.floor(Math.log(bytes) / Math.log(k))))
        return (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1) + " " + sizes[i]
    }

    // Entries directly inside curDir: folders first, then names in natural order
    readonly property var visibleEntries: {
        var out = []
        for (var i = 0; i < entries.length; i++) if (entries[i].dir === curDir) out.push(entries[i])
        out.sort(function(a, b) {
            if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1
            return a.name.localeCompare(b.name, undefined, { numeric: true })
        })
        return out
    }

    readonly property var crumbs: {
        var parts = curDir ? curDir.split("/") : []
        var out = [{ name: archive ? archive.name : "", path: "" }]
        for (var i = 0; i < parts.length; i++) out.push({ name: parts[i], path: parts.slice(0, i + 1).join("/") })
        return out
    }

    function open(item) {
        archive = item
        password = ""
        curDir = ""
        pendingOpen = null
        preparing = false
        passwordInput.text = ""
        isOpen = true
        load()
        listView.forceActiveFocus()
    }

    function close() {
        isOpen = false
        entries = []
        listing = ({})
        listingToken = -1
        pendingOpen = null
        preparing = false
    }

    // Read in the background (big archives used to freeze the window); onListingReady fills it in
    property int listingToken: -1
    function load() {
        if (!archiver || !archive) return
        errorText = ""
        preparing = true
        prepareText = "Reading the archive…"
        listingToken = archiver.listArchiveAsync(archive.path, password)
    }

    function goUp() {
        if (!curDir) return
        var idx = curDir.lastIndexOf("/")
        curDir = idx > 0 ? curDir.substring(0, idx) : ""
    }

    function openEntry(e) {
        if (e.is_dir) {
            curDir = e.path
            listView.currentIndex = -1
            return
        }
        var k = kindOf(e)
        var paths = []
        if (k === "image" || k === "video" || k === "audio") {
            // Unpack this folder's media so the Lightbox can step through it
            for (var i = 0; i < visibleEntries.length; i++) {
                var kk = kindOf(visibleEntries[i])
                if (kk === "image" || kk === "video" || kk === "audio") paths.push(visibleEntries[i].path)
            }
        } else {
            paths.push(e.path)
        }
        pendingOpen = { entry: e, paths: paths }
        preparing = true
        prepareText = paths.length > 1 ? ("Preparing " + paths.length + " files for preview…") : ("Opening " + e.name + "…")
        errorText = ""
        previewToken = archiver.extractForPreview(archive.path, paths, password)
    }

    function submitPassword() {
        password = passwordInput.text
        if (pendingOpen) {
            var p = pendingOpen
            needsPassword = false
            openEntry(p.entry)
        } else {
            load()
        }
    }

    Connections {
        target: root.archiver
        function onListingReady(token, res) {
            if (token !== root.listingToken || !root.isOpen) return
            root.listingToken = -1
            if (!root.pendingOpen) root.preparing = false
            root.listing = res
            root.needsPassword = !!res.needsPassword
            root.errorText = res.error || ""
            root.entries = res.ok ? res.entries : []
        }
        function onPreviewReady(token, res) {
            if (token !== root.previewToken || !root.pendingOpen) return
            root.preparing = false
            var p = root.pendingOpen
            if (res.needsPassword) {
                root.needsPassword = true
                root.errorText = res.error
                passwordInput.forceActiveFocus()
                return
            }
            root.pendingOpen = null
            var files = res.files || {}
            var target = files[p.entry.path]
            if (!target) {
                root.errorText = res.error || "Couldn't unpack this file."
                return
            }
            var k = root.kindOf(p.entry)
            if (k === "other") {
                if (root.bridge) root.bridge.openPathInSystem(target)
                return
            }
            var media = []
            var clicked = null
            for (var i = 0; i < p.paths.length; i++) {
                var local = files[p.paths[i]]
                if (!local) continue
                var nm = p.paths[i].substring(p.paths[i].lastIndexOf("/") + 1)
                var it = { name: nm, path: local, ext: root.extOf(nm), is_dir: false, size: 0, mtime: 0 }
                media.push(it)
                if (p.paths[i] === p.entry.path) clicked = it
            }
            if (root.lightbox && clicked) root.lightbox.open(clicked, media)
        }
    }

    Shortcut {
        sequence: "Escape"
        enabled: root.isOpen && !(root.lightbox && root.lightbox.isOpen)
        onActivated: root.close()
    }

    // ── Backdrop ────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#060910"
        opacity: 0.9
        MouseArea { anchors.fill: parent; hoverEnabled: true; onClicked: root.close(); onWheel: (wheel) => wheel.accepted = true }
    }

    Rectangle {
        // Heavy panel: settles in on a soft spring
        scale: root.isOpen ? 1.0 : 0.9
        Behavior on scale { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.0008 } }
        anchors.centerIn: parent
        width: Math.min(780, parent.width - 32)
        height: Math.min(parent.height - 32, 660)
        radius: 10
        color: "#121725"
        border.color: "#F59E0B"
        border.width: 1
        MouseArea { anchors.fill: parent; hoverEnabled: true }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        Layout.fillWidth: true
                        text: "📦  " + (root.archive ? root.archive.name : "")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 15
                        font.weight: 700
                        color: "#F8FAFC"
                        elide: Text.ElideMiddle
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: !!root.listing.ok
                        text: root.listing.fileCount + (root.listing.fileCount === 1 ? " file" : " files") + "  •  "
                              + root.formatBytes(root.listing.totalSize) + " unpacked"
                              + (root.listing.packedSize > 0 ? ("  •  " + root.formatBytes(root.listing.packedSize) + " packed") : "")
                              + (root.listing.encrypted ? "  •  🔒 password-protected files" : "")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        elide: Text.ElideRight
                    }
                }
                Rectangle {
                    implicitHeight: 28
                    implicitWidth: extractAllRow.implicitWidth + 18
                    radius: 6
                    color: extractAllMouse.containsMouse ? "#0EA5E9" : "#0284C7"
                    border.color: "#38BDF8"
                    Row {
                        id: extractAllRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "📂"; font.pixelSize: 11 }
                        Text { text: "Extract all…"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.weight: 700; color: "#FFFFFF" }
                    }
                    Springy { hover: extractAllMouse.containsMouse; pressed: extractAllMouse.pressed }
                    MouseArea {
                        id: extractAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var item = root.archive
                            root.close()
                            root.extractAllRequested(item)
                        }
                    }
                }
                Rectangle {
                    implicitWidth: 28
                    implicitHeight: 28
                    radius: 6
                    color: closeMouse.containsMouse ? "#3A1620" : "#141720"
                    border.color: closeMouse.containsMouse ? "#EF4444" : "#2E384D"
                    Text { anchors.centerIn: parent; text: "✕"; font.pixelSize: 12; color: "#E2E8F0" }
                    Springy { hover: closeMouse.containsMouse; pressed: closeMouse.pressed }
                    MouseArea {
                        id: closeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.close()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "Close (Esc)"
                    }
                }
            }

            // Breadcrumbs inside the archive
            Flow {
                Layout.fillWidth: true
                spacing: 4
                visible: !!root.listing.ok
                Repeater {
                    model: root.crumbs
                    delegate: Row {
                        spacing: 4
                        Rectangle {
                            implicitHeight: 22
                            implicitWidth: crumbLabel.implicitWidth + 12
                            radius: 4
                            color: crumbMouse.containsMouse ? "#1E293D" : (index === root.crumbs.length - 1 ? "#1B2234" : "transparent")
                            border.color: index === root.crumbs.length - 1 ? "#F59E0B" : "transparent"
                            Text {
                                id: crumbLabel
                                anchors.centerIn: parent
                                text: (index === 0 ? "📦 " : "") + modelData.name
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: index === root.crumbs.length - 1 ? 700 : Font.Normal
                                color: index === root.crumbs.length - 1 ? "#F8FAFC" : "#94A3B8"
                            }
                            Springy { hover: crumbMouse.containsMouse; pressed: crumbMouse.pressed }
                            MouseArea {
                                id: crumbMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.curDir = modelData.path
                            }
                        }
                        Text { visible: index < root.crumbs.length - 1; text: "›"; color: "#475569"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                    }
                }
            }

            // Password prompt (locked listing or locked files)
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                visible: root.needsPassword
                Text {
                    Layout.fillWidth: true
                    text: "🔒 " + (root.errorText || "This archive is password-protected.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#F59E0B"
                    wrapMode: Text.WordWrap
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 30
                        radius: 6
                        color: "#0D1018"
                        border.color: passwordInput.activeFocus ? "#38BDF8" : "#252D3E"
                        TextInput {
                            id: passwordInput
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            verticalAlignment: TextInput.AlignVCenter
                            echoMode: TextInput.Password
                            color: "#F8FAFC"
                            font.pixelSize: 12
                            selectByMouse: true
                            clip: true
                            onAccepted: root.submitPassword()
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: !passwordInput.text && !passwordInput.activeFocus
                                text: "Enter the archive password"
                                color: "#475569"
                                font.pixelSize: 11
                            }
                        }
                    }
                    Rectangle {
                        implicitHeight: 30
                        implicitWidth: unlockText.implicitWidth + 24
                        radius: 6
                        color: unlockMouse.containsMouse ? "#0EA5E9" : "#0284C7"
                        Text { id: unlockText; anchors.centerIn: parent; text: "Unlock"; font.pixelSize: 11; font.weight: 700; color: "#FFFFFF" }
                        MouseArea { id: unlockMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.submitPassword() }
                    }
                }
            }

            // Error (not password related)
            Text {
                Layout.fillWidth: true
                visible: !root.needsPassword && root.errorText.length > 0
                text: "⚠ " + root.errorText
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#F87171"
                wrapMode: Text.WordWrap
            }

            // Contents
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 8
                color: "#0D1018"
                border.color: "#1E2536"
                clip: true

                ListView {
                    id: listView
                    anchors.fill: parent
                    anchors.margins: 6
                    spacing: 2
                    clip: true
                    model: root.visibleEntries
                    currentIndex: -1
                    keyNavigationEnabled: true
                    highlightFollowsCurrentItem: false
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    Keys.onPressed: (event) => {
                        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && currentIndex >= 0) {
                            root.openEntry(root.visibleEntries[currentIndex]); event.accepted = true
                        } else if (event.key === Qt.Key_Backspace) {
                            root.goUp(); event.accepted = true
                        }
                    }

                    delegate: Rectangle {
                        width: listView.width
                        height: 30
                        radius: 5
                        readonly property bool isCur: ListView.isCurrentItem && listView.activeFocus
                        color: rowMouse.containsMouse ? "#1B2336" : (index % 2 === 0 ? "#111622" : "#0E121B")
                        border.color: isCur ? "#F8FAFC" : (rowMouse.containsMouse ? "#F59E0B" : "transparent")
                        border.width: 1

                        Text {
                            id: rowIcon
                            anchors.left: parent.left
                            anchors.leftMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.iconOf(modelData)
                            font.pixelSize: 13
                        }
                        Text {
                            id: rowDate
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            width: 130
                            horizontalAlignment: Text.AlignRight
                            text: (modelData.mtime || "").substring(0, 16)
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 10
                            color: "#64748B"
                        }
                        Text {
                            id: rowSize
                            anchors.right: rowDate.left
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            width: 80
                            horizontalAlignment: Text.AlignRight
                            text: modelData.is_dir ? "" : root.formatBytes(modelData.size)
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 10
                            color: "#94A3B8"
                        }
                        Text {
                            anchors.left: rowIcon.right
                            anchors.leftMargin: 10
                            anchors.right: rowSize.left
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.name
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: modelData.is_dir ? 600 : Font.Normal
                            color: modelData.is_dir ? "#38BDF8" : "#E2E8F0"
                            elide: Text.ElideMiddle
                        }
                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                listView.currentIndex = index
                                root.openEntry(modelData)
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 450
                            ToolTip.text: modelData.is_dir ? ("📁 " + modelData.path + "\n• Click to open")
                                : (modelData.path + "\n" + root.formatBytes(modelData.size)
                                   + ((root.kindOf(modelData) === "other") ? "\n• Click to open in its default app" : "\n• Click to view in the Lightbox"))
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: !!root.listing.ok && root.visibleEntries.length === 0
                    text: "This folder is empty"
                    font.pixelSize: 12
                    color: "#64748B"
                }
            }

            // Footer: preparing previews / hint
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Text {
                    Layout.fillWidth: true
                    text: root.preparing ? ("⏳ " + root.prepareText) : (root.curDir ? "Backspace: up a folder  •  Esc: close" : "Click an image or video to view it  •  Esc: close")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: root.preparing ? "#F59E0B" : "#475569"
                    elide: Text.ElideRight
                }
            }
        }
    }
}
