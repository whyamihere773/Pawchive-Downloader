import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Gallery Archive Modal ───────────────────────────────────────────────────
// Compress selected files/folders into one archive or one archive per item,
// or extract selected archives. Shows live progress and a result summary,
// and asks for a password when an archive is locked.
Item {
    id: root

    property var bridge: null       // appBridge (folder picker, reveal in Explorer)
    property var archiver: null     // galleryArchiveBridge
    property bool isOpen: false
    property string mode: "compress"   // "compress" | "extract" | "copy"
    property string stage: "setup"     // "setup" | "running" | "result"
    property var items: []
    property string currentFolder: ""
    property bool ownsJob: false

    // Compress options
    property string packMode: "single"   // "single" | "each"
    property string archiveFormat: "zip"
    property string level: "normal"
    property string destDir: ""
    property bool deleteOriginals: false
    property bool showPassword: false

    // Extract options
    property var archives: []
    property bool rememberPassword: true
    property bool deleteArchives: false

    // Progress & result
    property real progress: 0
    property string progressName: ""
    property string progressStatus: ""
    property real speed: 0            // bytes per second
    property real eta: -1             // seconds, -1 while still estimating
    property real doneBytes: 0
    property real totalBytes: 0
    property int itemIndex: 0
    property int itemCount: 0
    property real jobStartedAt: 0     // ms timestamps, used for the ticking clock
    property real lastChangeAt: 0
    property real now: 0
    readonly property real elapsedSec: jobStartedAt > 0 ? Math.max(0, (now - jobStartedAt) / 1000) : 0
    readonly property bool looksQuiet: stage === "running" && lastChangeAt > 0 && (now - lastChangeAt) > 8000
    property var result: ({})
    property string startError: ""

    signal finished()
    // A job that was sent to the background has finished (headline, success)
    signal backgroundFinished(string headline, bool ok)

    // Finished while hidden and not looked at yet (the gallery shows a "view" chip)
    property bool unseenResult: false

    anchors.fill: parent
    z: 9500
    // Fades in / out (weight-based motion); no input while closing
    opacity: isOpen ? 1 : 0
    visible: opacity > 0.005
    enabled: isOpen
    Behavior on opacity { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
    // ── Helpers ─────────────────────────────────────────────────────────────
    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "0 B"
        var k = 1024
        var sizes = ["B", "KB", "MB", "GB", "TB"]
        var i = Math.floor(Math.log(bytes) / Math.log(k))
        i = Math.max(0, Math.min(sizes.length - 1, i))
        return (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1) + " " + sizes[i]
    }

    function formatDuration(sec) {
        sec = Math.max(0, Math.round(sec))
        var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60
        if (h > 0) return h + "h " + (m < 10 ? "0" : "") + m + "m"
        if (m > 0) return m + "m " + (s < 10 ? "0" : "") + s + "s"
        return s + "s"
    }

    function formatClock(sec) {
        sec = Math.max(0, Math.floor(sec))
        var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60
        var mm = (h > 0 && m < 10 ? "0" : "") + m
        return (h > 0 ? h + ":" : "") + mm + ":" + (s < 10 ? "0" : "") + s
    }

    function _paths(list) {
        var out = []
        for (var i = 0; i < list.length; i++) out.push(list[i].path)
        return out
    }

    function _baseName(item) {
        if (item.is_dir) return item.name
        var dot = item.name.lastIndexOf(".")
        return dot > 0 ? item.name.substring(0, dot) : item.name
    }

    function _folderName(path) {
        var p = (path || "").replace(/[\\\/]+$/, "")
        var idx = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"))
        var n = idx >= 0 ? p.substring(idx + 1) : p
        return (n && n.indexOf(":") < 0) ? n : "Archive"
    }

    readonly property string extension: archiveFormat === "7z" ? ".7z" : ".zip"

    // Total size of the selection; -1 when a folder's size is still being calculated
    readonly property real selectionBytes: {
        var total = 0
        for (var i = 0; i < items.length; i++) {
            if (items[i].size < 0) return -1
            total += items[i].size
        }
        return total
    }
    readonly property real archivesBytes: {
        var total = 0
        for (var i = 0; i < archives.length; i++) if (archives[i].supported) total += archives[i].size
        return total
    }
    readonly property int supportedArchiveCount: {
        var n = 0
        for (var i = 0; i < archives.length; i++) if (archives[i].supported) n++
        return n
    }
    readonly property string effectiveDest: destDir || currentFolder
    readonly property real freeBytes: (isOpen && archiver && effectiveDest) ? archiver.freeSpace(effectiveDest) : -1
    readonly property bool compressSpaceOk: selectionBytes < 0 || freeBytes < 0 || freeBytes >= selectionBytes * 1.02
    readonly property bool extractSpaceTight: freeBytes >= 0 && freeBytes < archivesBytes * 1.2
    readonly property string nameError: (mode === "compress" && packMode === "single" && archiver) ? archiver.validateName(nameField.text) : ""

    // ── Opening ─────────────────────────────────────────────────────────────
    function _reset() {
        stage = "setup"
        startError = ""
        result = ({})
        progress = 0
        progressName = ""
        progressStatus = ""
        jobStartedAt = 0
        lastChangeAt = 0
        destDir = ""
        passwordField.text = ""
        extractPasswordField.text = ""
        retryPasswordField.text = ""
        showPassword = false
    }

    function openCompress(list, folder) {
        items = list
        currentFolder = folder
        mode = "compress"
        _reset()
        packMode = "single"
        deleteOriginals = false
        nameField.text = list.length === 1 ? _baseName(list[0]) : _folderName(folder)
        isOpen = true
        nameField.forceActiveFocus()
        nameField.selectAll()
    }

    function openExtract(list, folder) {
        items = list
        currentFolder = folder
        mode = "extract"
        _reset()
        deleteArchives = false
        archives = archiver ? archiver.describeArchives(_paths(list)) : []
        isOpen = true
        keyCatcher.forceActiveFocus()
    }

    // Copy (Copy to…, drag and drop): no options, straight to progress
    function startCopy(paths, dest) {
        if (!archiver) return ""
        items = []
        archives = []
        mode = "copy"
        _reset()
        var err = archiver.startCopy(paths, dest)
        if (err) return err
        isOpen = true
        _enterRunning("Measuring files…")
        return ""
    }

    // "Extract here": skip the options and start right away
    function quickExtract(list, folder) {
        openExtract(list, folder)
        if (supportedArchiveCount > 0) startJob()
    }

    function close() {
        // Closing a running job just sends it to the background
        if (stage === "running") {
            hideToBackground()
            return
        }
        isOpen = false
        items = []
        archives = []
    }

    function hideToBackground() {
        if (stage === "running") isOpen = false
    }

    function reopen() {
        unseenResult = false
        isOpen = true
    }

    function resultHeadline() {
        var r = root.result || {}
        if (r.cancelled) return "Cancelled"
        if (root.mode === "copy")
            return r.failed > 0 ? ("Copied " + r.succeeded + " of " + r.total + " items") : ("Copied " + r.succeeded + (r.succeeded === 1 ? " item" : " items"))
        if (root.mode === "compress")
            return r.failed > 0 ? ("Created " + r.succeeded + " of " + r.total + " archives") : ("Created " + r.succeeded + (r.succeeded === 1 ? " archive" : " archives"))
        var locked = (r.needsPassword || []).length
        if (r.succeeded === r.total) return "Extracted " + r.succeeded + (r.succeeded === 1 ? " archive" : " archives")
        if (locked > 0 && r.failed === 0) return locked + (locked === 1 ? " archive needs" : " archives need") + " a password"
        return "Extracted " + r.succeeded + " of " + r.total + " archives"
    }

    function startJob(extraPasswords) {
        if (!archiver) return
        var err = ""
        if (mode === "compress") {
            if (nameError) return
            err = archiver.startCompress(_paths(items), {
                "mode": packMode,
                "name": nameField.text.trim(),
                "format": archiveFormat,
                "level": level,
                "password": passwordField.text,
                "destDir": effectiveDest,
                "deleteOriginals": deleteOriginals
            })
        } else {
            var paths = []
            for (var i = 0; i < archives.length; i++) if (archives[i].supported) paths.push(archives[i].path)
            err = archiver.startExtract(paths, {
                "destDir": destDir,
                "password": extraPasswords !== undefined ? extraPasswords : extractPasswordField.text,
                "rememberPassword": rememberPassword,
                "deleteArchives": deleteArchives
            })
        }
        if (err) {
            startError = err
            return
        }
        startError = ""
        _enterRunning(mode === "compress" ? "Preparing…" : "Opening archives…")
    }

    function _enterRunning(status) {
        ownsJob = true
        progress = 0
        progressName = ""
        progressStatus = status
        speed = 0
        eta = -1
        doneBytes = 0
        totalBytes = 0
        itemIndex = 0
        itemCount = 0
        jobStartedAt = Date.now()
        lastChangeAt = jobStartedAt
        now = jobStartedAt
        stage = "running"
    }

    function retryLocked() {
        var pw = retryPasswordField.text
        if (!pw) return
        var locked = result.needsPassword || []
        var keep = []
        for (var i = 0; i < archives.length; i++) {
            for (var j = 0; j < locked.length; j++) {
                if (archives[i].path === locked[j].path) keep.push(archives[i])
            }
        }
        archives = keep
        retryPasswordField.text = ""
        startJob(pw)
    }

    function chooseDestination() {
        if (!bridge || !bridge.browseFolderDialog) return
        var chosen = bridge.browseFolderDialog(mode === "compress" ? "Save archive to…" : "Extract to…", effectiveDest)
        if (chosen) destDir = chosen
    }

    Timer {
        interval: 1000
        repeat: true
        running: root.stage === "running"
        triggeredOnStart: true
        onTriggered: root.now = Date.now()
    }

    Connections {
        target: root.archiver
        enabled: root.ownsJob
        function onJobProgress(info) {
            if (Math.abs(info.percent - root.progress) >= 0.05 || info.status !== root.progressStatus)
                root.lastChangeAt = Date.now()
            root.progress = info.percent
            root.progressName = info.name
            root.progressStatus = info.status
            root.speed = info.speed
            root.eta = info.eta
            root.doneBytes = info.doneBytes
            root.totalBytes = info.totalBytes
            root.itemIndex = info.index
            root.itemCount = info.count
        }
        function onJobFinished(summary) {
            root.now = Date.now()
            root.ownsJob = false
            root.result = summary
            root.stage = "result"
            root.finished()
            if (!root.isOpen) {
                root.unseenResult = true
                var ok = !summary.cancelled && summary.failed === 0 && (summary.needsPassword || []).length === 0
                root.backgroundFinished(root.resultHeadline(), ok)
            }
        }
    }

    // ── Reusable bits ───────────────────────────────────────────────────────
    component Segmented: Rectangle {
        id: seg
        property var options: []     // [{ value, label, tip }]
        property string value: ""
        signal picked(string choice)
        implicitHeight: 26
        implicitWidth: segRow.implicitWidth + 4
        radius: 6
        color: "#0D1018"
        border.color: "#252D3E"
        border.width: 1
        Row {
            id: segRow
            anchors.centerIn: parent
            spacing: 2
            Repeater {
                model: seg.options
                delegate: Rectangle {
                    readonly property bool active: seg.value === modelData.value
                    implicitHeight: 22
                    implicitWidth: segText.implicitWidth + 18
                    radius: 4
                    color: active ? "#1E3A5F" : (segMouse.containsMouse ? "#182030" : "transparent")
                    border.color: active ? "#38BDF8" : "transparent"
                    border.width: 1
                    Text {
                        id: segText
                        anchors.centerIn: parent
                        text: modelData.label
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: active ? 700 : 600
                        color: active ? "#38BDF8" : "#94A3B8"
                    }
                    Springy { hover: segMouse.containsMouse; pressed: segMouse.pressed }
                    MouseArea {
                        id: segMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: seg.picked(modelData.value)
                        ToolTip.visible: containsMouse && !!modelData.tip
                        ToolTip.delay: 300
                        ToolTip.text: modelData.tip || ""
                    }
                }
            }
        }
    }

    component CheckRow: Item {
        id: chk
        property string label: ""
        property bool checked: false
        signal toggled()
        implicitHeight: 20
        implicitWidth: chkRow.implicitWidth
        Row {
            id: chkRow
            spacing: 8
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                width: 15; height: 15; radius: 3
                anchors.verticalCenter: parent.verticalCenter
                color: chk.checked ? "#38BDF8" : "transparent"
                border.color: chk.checked ? "#38BDF8" : (chkMouse.containsMouse ? "#38BDF8" : "#64748B")
                border.width: 1
                Text { anchors.centerIn: parent; visible: chk.checked; text: "✓"; font.pixelSize: 10; font.weight: 800; color: "#0F172A" }
            }
            Text {
                text: chk.label
                anchors.verticalCenter: parent.verticalCenter
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#CBD5E1"
            }
        }
        MouseArea {
            id: chkMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: chk.toggled()
        }
    }

    component DialogButton: Rectangle {
        id: btn
        property string label: ""
        property bool primary: false
        property bool danger: false
        property bool enabledState: true
        signal clicked()
        implicitHeight: 30
        implicitWidth: btnText.implicitWidth + 26
        radius: 6
        opacity: enabledState ? 1.0 : 0.45
        color: primary ? (btnMouse.containsMouse && enabledState ? "#0EA5E9" : "#0284C7")
                       : (btnMouse.containsMouse && enabledState ? (danger ? "#3A1620" : "#1E293B") : "#141720")
        border.color: primary ? "#38BDF8" : (danger ? "#EF4444" : "#2E384D")
        border.width: 1
        Text {
            id: btnText
            anchors.centerIn: parent
            text: btn.label
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            font.weight: 700
            color: primary ? "#FFFFFF" : (danger ? "#F87171" : "#E2E8F0")
        }
        Springy { hover: btnMouse.containsMouse; pressed: btnMouse.pressed }
        MouseArea {
            id: btnMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: btn.enabledState ? Qt.PointingHandCursor : Qt.ForbiddenCursor
            onClicked: if (btn.enabledState) btn.clicked()
        }
    }

    component FieldLabel: Text {
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 10
        font.weight: 700
        color: "#64748B"
    }

    component InputBox: Rectangle {
        id: box
        property alias text: inner.text
        property alias echoMode: inner.echoMode
        property string placeholder: ""
        property bool error: false
        signal accepted()
        function forceActiveFocus() { inner.forceActiveFocus() }
        function selectAll() { inner.selectAll() }
        implicitHeight: 30
        radius: 6
        color: "#0D1018"
        border.color: error ? "#EF4444" : (inner.activeFocus ? "#38BDF8" : "#252D3E")
        border.width: 1
        TextInput {
            id: inner
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            verticalAlignment: TextInput.AlignVCenter
            color: "#F8FAFC"
            selectionColor: "#2563EB"
            selectedTextColor: "#FFFFFF"
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 12
            selectByMouse: true
            clip: true
            onAccepted: box.accepted()
            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: !inner.text && !inner.activeFocus
                text: box.placeholder
                color: "#475569"
                font.pixelSize: 11
            }
        }
    }

    // ── Backdrop ────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#060910"
        opacity: 0.88
        // hoverEnabled also stops hover tooltips of gallery cards underneath
        MouseArea { anchors.fill: parent; hoverEnabled: true; onClicked: root.close(); onWheel: (wheel) => wheel.accepted = true }
    }

    Item {
        id: keyCatcher
        focus: root.isOpen
        Keys.onReturnPressed: if (root.stage === "setup") root.startJob()
        Keys.onEnterPressed: if (root.stage === "setup") root.startJob()
    }

    Shortcut {
        sequence: "Escape"
        enabled: root.isOpen
        onActivated: root.close()
    }

    Rectangle {
        id: card
        // Heavy panel: settles in on a soft spring
        scale: root.isOpen ? 1.0 : 0.9
        Behavior on scale { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.0008 } }
        anchors.centerIn: parent
        width: Math.min(520, parent.width - 32)
        height: Math.min(parent.height - 32, body.implicitHeight + 36)
        radius: 10
        color: "#121725"
        border.color: root.mode === "compress" ? "#A78BFA" : (root.mode === "copy" ? "#34D399" : "#38BDF8")
        border.width: 1
        MouseArea { anchors.fill: parent; hoverEnabled: true }

        Flickable {
            anchors.fill: parent
            anchors.margins: 18
            contentHeight: body.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            ColumnLayout {
                id: body
                width: parent.width
                spacing: 12

                // Title
                Text {
                    Layout.fillWidth: true
                    text: {
                        if (root.stage === "result") {
                            var r = root.result
                            if (r.cancelled) return "⏹  Cancelled"
                            if (root.mode === "copy")
                                return r.failed > 0 ? ("⚠  Copied " + r.succeeded + " of " + r.total + " items") : ("✔  Copied " + r.succeeded + (r.succeeded === 1 ? " item" : " items"))
                            if (root.mode === "compress")
                                return r.failed > 0 ? ("⚠  Created " + r.succeeded + " of " + r.total + " archives") : ("✔  Created " + r.succeeded + (r.succeeded === 1 ? " archive" : " archives"))
                            var locked = (r.needsPassword || []).length
                            if (r.succeeded === r.total) return "✔  Extracted " + r.succeeded + (r.succeeded === 1 ? " archive" : " archives")
                            if (locked > 0 && r.failed === 0) return "🔒  " + locked + (locked === 1 ? " archive needs" : " archives need") + " a password"
                            return "⚠  Extracted " + r.succeeded + " of " + r.total + " archives"
                        }
                        if (root.stage === "running") return root.mode === "compress" ? "📦  Creating archive…" : (root.mode === "copy" ? "📋  Copying…" : "📂  Extracting…")
                        if (root.mode === "compress")
                            return "📦  Compress " + root.items.length + (root.items.length === 1 ? " item" : " items")
                        return "📂  Extract " + root.supportedArchiveCount + (root.supportedArchiveCount === 1 ? " archive" : " archives")
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 15
                    font.weight: 700
                    color: "#F8FAFC"
                    wrapMode: Text.WordWrap
                }

                // ── COMPRESS SETUP ──────────────────────────────────────────
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    visible: root.stage === "setup" && root.mode === "compress"

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 5
                        visible: root.items.length > 1
                        FieldLabel { text: "HOW TO PACK" }
                        Segmented {
                            options: [
                                { value: "single", label: "One archive with everything", tip: "Put all selected files and folders into a single archive" },
                                { value: "each", label: "One archive per item", tip: "Make a separate archive for each selected file or folder, named after it" }
                            ]
                            value: root.packMode
                            onPicked: (v) => root.packMode = v
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 5
                        visible: root.packMode === "single" || root.items.length === 1
                        FieldLabel { text: "ARCHIVE NAME" }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            InputBox {
                                id: nameField
                                Layout.fillWidth: true
                                error: root.nameError.length > 0
                                placeholder: "Archive name"
                                onAccepted: root.startJob()
                            }
                            Text { text: root.extension; font.family: "Segoe UI, monospace"; font.pixelSize: 12; color: "#94A3B8" }
                        }
                        Text {
                            visible: root.nameError.length > 0
                            text: "⚠ " + root.nameError
                            font.pixelSize: 10
                            color: "#F87171"
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: root.packMode === "each" && root.items.length > 1
                        text: {
                            var names = []
                            for (var i = 0; i < Math.min(3, root.items.length); i++) names.push(root._baseName(root.items[i]) + root.extension)
                            return "Creates " + root.items.length + " archives: " + names.join(", ") + (root.items.length > 3 ? ", …" : "")
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#CBD5E1"
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 18
                        ColumnLayout {
                            spacing: 5
                            FieldLabel { text: "FORMAT" }
                            Segmented {
                                options: [
                                    { value: "zip", label: "ZIP", tip: "Opens everywhere, including Windows and phones without extra apps" },
                                    { value: "7z", label: "7Z", tip: "Usually smaller, needs 7-Zip or a similar app to open" }
                                ]
                                value: root.archiveFormat
                                onPicked: (v) => root.archiveFormat = v
                            }
                        }
                        ColumnLayout {
                            spacing: 5
                            FieldLabel { text: "COMPRESSION" }
                            Segmented {
                                options: [
                                    { value: "store", label: "None", tip: "Fastest, no size reduction" },
                                    { value: "fast", label: "Fast", tip: "Quick, slightly larger. Good for images and videos, which barely shrink anyway" },
                                    { value: "normal", label: "Normal", tip: "Balanced speed and size" },
                                    { value: "max", label: "Max", tip: "Smallest archive, slowest" }
                                ]
                                value: root.level
                                onPicked: (v) => root.level = v
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 5
                        FieldLabel { text: "PASSWORD (OPTIONAL)" }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            InputBox {
                                id: passwordField
                                Layout.fillWidth: true
                                placeholder: "Leave empty for no password"
                                echoMode: root.showPassword ? TextInput.Normal : TextInput.Password
                            }
                            DialogButton {
                                label: root.showPassword ? "Hide" : "Show"
                                implicitHeight: 30
                                onClicked: root.showPassword = !root.showPassword
                            }
                        }
                        Text {
                            visible: passwordField.text.length > 0
                            Layout.fillWidth: true
                            text: root.archiveFormat === "zip" ? "Encrypted with AES-256. File names inside a ZIP stay visible." : "Encrypted with AES-256, including the file names."
                            font.pixelSize: 10
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                // ── EXTRACT SETUP ───────────────────────────────────────────
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    visible: root.stage === "setup" && root.mode === "extract"

                    Text {
                        Layout.fillWidth: true
                        text: {
                            var lines = []
                            for (var i = 0; i < Math.min(6, root.archives.length); i++) {
                                var a = root.archives[i]
                                lines.push((a.supported ? "• " : "✖ ") + a.name + "  (" + root.formatBytes(a.size) + ")" + (a.supported ? "" : " — " + a.reason))
                            }
                            if (root.archives.length > 6) lines.push("…and " + (root.archives.length - 6) + " more")
                            if (root.archives.length === 0) lines.push("None of the selected items are archives.")
                            return lines.join("\n")
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#CBD5E1"
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Each archive is extracted into its own new folder named after it, so nothing gets overwritten."
                        font.pixelSize: 10
                        color: "#94A3B8"
                        wrapMode: Text.WordWrap
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 5
                        FieldLabel { text: "PASSWORD (ONLY IF THE ARCHIVE IS LOCKED)" }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            InputBox {
                                id: extractPasswordField
                                Layout.fillWidth: true
                                placeholder: "Saved passwords from the Password Bank are tried automatically"
                                echoMode: root.showPassword ? TextInput.Normal : TextInput.Password
                                onAccepted: root.startJob()
                            }
                            DialogButton {
                                label: root.showPassword ? "Hide" : "Show"
                                implicitHeight: 30
                                onClicked: root.showPassword = !root.showPassword
                            }
                        }
                        CheckRow {
                            visible: extractPasswordField.text.length > 0
                            label: "Save this password to the Password Bank if it works"
                            checked: root.rememberPassword
                            onToggled: root.rememberPassword = !root.rememberPassword
                        }
                    }
                }

                // ── SHARED: destination, cleanup option, disk space ─────────
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    visible: root.stage === "setup"

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 5
                        FieldLabel { text: root.mode === "compress" ? "SAVE TO" : "EXTRACT TO" }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Text {
                                Layout.fillWidth: true
                                text: root.destDir ? root.destDir : (root.mode === "compress" ? root.currentFolder + "  (this folder)" : "Next to each archive  (this folder)")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#E2E8F0"
                                elide: Text.ElideMiddle
                            }
                            DialogButton { label: "Change…"; implicitHeight: 26; onClicked: root.chooseDestination() }
                            DialogButton { visible: root.destDir.length > 0; label: "Reset"; implicitHeight: 26; onClicked: root.destDir = "" }
                        }
                    }

                    CheckRow {
                        label: root.mode === "compress" ? "Move the originals to the Recycle Bin after archiving" : "Move the archives to the Recycle Bin after extracting"
                        checked: root.mode === "compress" ? root.deleteOriginals : root.deleteArchives
                        onToggled: {
                            if (root.mode === "compress") root.deleteOriginals = !root.deleteOriginals
                            else root.deleteArchives = !root.deleteArchives
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: {
                            var free = root.freeBytes >= 0 ? (root.formatBytes(root.freeBytes) + " free") : "free space unknown"
                            if (root.mode === "compress") {
                                if (root.selectionBytes < 0) return "💽 " + free + " • folder sizes are still being calculated"
                                if (!root.compressSpaceOk) return "⚠ Not enough space: needs up to " + root.formatBytes(root.selectionBytes) + ", only " + free
                                return "💽 Up to " + root.formatBytes(root.selectionBytes) + " • " + free
                            }
                            if (root.extractSpaceTight) return "⚠ Space may run out: archives total " + root.formatBytes(root.archivesBytes) + " and unpack larger, only " + free
                            return "💽 Archives total " + root.formatBytes(root.archivesBytes) + " • " + free
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: (root.mode === "compress" && !root.compressSpaceOk) ? "#F87171" : ((root.mode === "extract" && root.extractSpaceTight) ? "#F59E0B" : "#64748B")
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: root.startError.length > 0
                        text: "⚠ " + root.startError
                        font.pixelSize: 11
                        color: "#F87171"
                        wrapMode: Text.WordWrap
                    }
                }

                // ── RUNNING ─────────────────────────────────────────────────
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: root.stage === "running"

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            Layout.fillWidth: true
                            text: root.progressStatus
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#CBD5E1"
                            elide: Text.ElideMiddle
                        }
                        Text {
                            visible: root.itemCount > 1
                            text: (root.itemIndex + 1) + " of " + root.itemCount
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#94A3B8"
                        }
                    }

                    // Progress bar with a moving shimmer, so it visibly keeps working
                    // even while 7-Zip is between percentage updates.
                    Rectangle {
                        id: track
                        Layout.fillWidth: true
                        implicitHeight: 10
                        radius: 5
                        color: "#1E2536"
                        clip: true
                        Rectangle {
                            id: fill
                            width: track.width * Math.max(0.02, Math.min(1, root.progress / 100))
                            height: parent.height
                            radius: 5
                            color: root.mode === "compress" ? "#A78BFA" : (root.mode === "copy" ? "#34D399" : "#38BDF8")
                            Behavior on width { NumberAnimation { duration: 250 } }
                        }
                        Rectangle {
                            id: shimmer
                            width: 60
                            height: parent.height
                            opacity: 0.55
                            gradient: Gradient {
                                orientation: Gradient.Horizontal
                                GradientStop { position: 0.0; color: "#00FFFFFF" }
                                GradientStop { position: 0.5; color: "#AAFFFFFF" }
                                GradientStop { position: 1.0; color: "#00FFFFFF" }
                            }
                            NumberAnimation on x {
                                running: root.stage === "running"
                                loops: Animation.Infinite
                                from: -60
                                to: Math.max(track.width, 60)
                                duration: 1400
                            }
                        }
                    }

                    // 45%  •  128 MB of 400 MB  •  23.4 MB/s  •  about 12s left        0:34
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Text {
                            text: Math.floor(root.progress) + "%"
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 12
                            font.weight: 700
                            color: "#F8FAFC"
                        }
                        Text {
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            text: {
                                var parts = []
                                if (root.totalBytes > 0) parts.push(root.formatBytes(root.doneBytes) + " of " + root.formatBytes(root.totalBytes))
                                if (root.speed > 0) parts.push(root.formatBytes(root.speed) + "/s")
                                if (root.eta >= 0) parts.push(root.eta < 1.5 ? "almost done" : ("about " + root.formatDuration(root.eta) + " left"))
                                else if (root.elapsedSec >= 1) parts.push("estimating time…")
                                return parts.length ? "•  " + parts.join("  •  ") : ""
                            }
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                        Text {
                            text: "⏱ " + root.formatClock(root.elapsedSec)
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 11
                            color: "#64748B"
                            ToolTip.visible: clockMouse.containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: "Time elapsed"
                            MouseArea { id: clockMouse; anchors.fill: parent; hoverEnabled: true }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "You can keep browsing: \"Run in background\" (or Esc) hides this window and shows the progress in the status bar."
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#475569"
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: root.looksQuiet
                        text: "Still working… 7-Zip reports progress in steps, so big files can sit on one number for a while."
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#F59E0B"
                        wrapMode: Text.WordWrap
                    }
                }

                // ── RESULT ──────────────────────────────────────────────────
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: root.stage === "result"

                    Text {
                        Layout.fillWidth: true
                        visible: (root.result.outputs || []).length > 0
                        text: {
                            var outs = root.result.outputs || []
                            var lines = []
                            for (var i = 0; i < Math.min(5, outs.length); i++) {
                                var p = outs[i]
                                lines.push("• " + p.substring(Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/")) + 1))
                            }
                            if (outs.length > 5) lines.push("…and " + (outs.length - 5) + " more")
                            return lines.join("\n")
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#CBD5E1"
                        wrapMode: Text.WordWrap
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.stage === "result" && root.elapsedSec >= 1
                        text: "Took " + root.formatDuration(root.elapsedSec) + (root.totalBytes > 0 && root.elapsedSec > 0 ? ("  •  average " + root.formatBytes(root.totalBytes / root.elapsedSec) + "/s") : "")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#64748B"
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: !!root.result.originalsTrashed
                        text: root.mode === "compress" ? "The originals were moved to the Recycle Bin." : "The archives were moved to the Recycle Bin."
                        font.pixelSize: 10
                        color: "#94A3B8"
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: (root.result.errors || []).length > 0 || (root.result.warnings || []).length > 0
                        text: ((root.result.errors || []).concat(root.result.warnings || [])).slice(0, 6).map(function(e) { return "⚠ " + e }).join("\n")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#F87171"
                        wrapMode: Text.WrapAnywhere
                        maximumLineCount: 12
                        elide: Text.ElideRight
                    }

                    // Locked archives: ask for a password and retry just those
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        visible: (root.result.needsPassword || []).length > 0 && !root.result.cancelled
                        Text {
                            Layout.fillWidth: true
                            text: {
                                var list = root.result.needsPassword || []
                                var wrong = false
                                var names = []
                                for (var i = 0; i < list.length; i++) {
                                    names.push("🔒 " + list[i].name)
                                    if (list[i].wrongPassword) wrong = true
                                }
                                return (wrong ? "That password didn't work, and none of the saved passwords matched:\n" : "None of the saved passwords matched:\n") + names.slice(0, 5).join("\n")
                            }
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#F59E0B"
                            wrapMode: Text.WordWrap
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            InputBox {
                                id: retryPasswordField
                                Layout.fillWidth: true
                                placeholder: "Enter the password"
                                echoMode: root.showPassword ? TextInput.Normal : TextInput.Password
                                onAccepted: root.retryLocked()
                            }
                            DialogButton { label: root.showPassword ? "Hide" : "Show"; onClicked: root.showPassword = !root.showPassword }
                            DialogButton { label: "Try password"; primary: true; enabledState: retryPasswordField.text.length > 0; onClicked: root.retryLocked() }
                        }
                        CheckRow {
                            label: "Save this password to the Password Bank if it works"
                            checked: root.rememberPassword
                            onToggled: root.rememberPassword = !root.rememberPassword
                        }
                    }
                }

                // ── Buttons ─────────────────────────────────────────────────
                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    spacing: 8
                    Item { Layout.fillWidth: true }

                    DialogButton {
                        visible: root.stage === "setup"
                        label: "Cancel"
                        onClicked: root.close()
                    }
                    DialogButton {
                        visible: root.stage === "setup"
                        primary: true
                        label: root.mode === "compress"
                            ? ((root.packMode === "each" && root.items.length > 1) ? "Create " + root.items.length + " archives" : "Create archive")
                            : (root.supportedArchiveCount > 1 ? "Extract " + root.supportedArchiveCount + " archives" : "Extract")
                        enabledState: root.archiver !== null && (root.mode === "compress"
                            ? (root.items.length > 0 && root.nameError.length === 0 && root.compressSpaceOk)
                            : root.supportedArchiveCount > 0)
                        onClicked: root.startJob()
                    }
                    DialogButton {
                        visible: root.stage === "running"
                        label: "Run in background"
                        onClicked: root.hideToBackground()
                    }
                    DialogButton {
                        visible: root.stage === "running"
                        danger: true
                        label: "Cancel"
                        onClicked: if (root.archiver) root.archiver.cancel()
                    }
                    DialogButton {
                        visible: root.stage === "result" && (root.result.outputs || []).length > 0
                        label: "Show in Explorer"
                        onClicked: if (root.bridge && root.bridge.revealFileInExplorer) root.bridge.revealFileInExplorer(root.result.outputs[0])
                    }
                    DialogButton {
                        visible: root.stage === "result"
                        primary: (root.result.needsPassword || []).length === 0
                        label: "Close"
                        onClicked: root.close()
                    }
                }
            }
        }
    }
}
