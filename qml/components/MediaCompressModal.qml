import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Gallery → right click → "Compress pictures & videos…" ───────────────────
// Compresses the chosen pictures, videos and animated pictures with the formats and qualities shared
// with the Decompressor. Copies are saved next to the originals and kept only when they're smaller; at the
// end the user chooses whether the originals go to the Recycle Bin.
// Motion has weight: the card's spring mass follows its size, so it settles in heavier when it's tall and
// glides between its steps (choose → progress → result) as its height changes.
Item {
    id: root

    property var bridge: null
    readonly property var dz: bridge ? bridge.decompressorBridge : null
    property bool isOpen: false
    property string stage: "setup"        // "setup" | "running" | "result"
    property var files: []

    // What the chosen files hold (counted in the background)
    property bool counted: false
    property int images: 0
    property int videos: 0
    property int animated: 0
    property real countBytes: 0
    readonly property int totalFiles: images + videos + animated

    // Progress and result
    property real progress: 0
    property string currentName: ""
    property int doneCount: 0
    property real bytesBefore: 0
    property real bytesAfter: 0
    property int failedCount: 0
    property int leftCount: 0
    property bool stopped: false
    property string originalsNote: ""

    signal finished()                     // files were written or removed: the Gallery reloads

    anchors.fill: parent
    z: 9500
    opacity: isOpen ? 1 : 0
    visible: opacity > 0.005
    enabled: isOpen
    focus: isOpen                         // (Esc closes it)
    Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

    function tr(key, fallback) {
        if (typeof Lang === "undefined" || !Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "0 B"
        var k = 1024, sizes = ["B", "KB", "MB", "GB", "TB"]
        var i = Math.max(0, Math.min(sizes.length - 1, Math.floor(Math.log(bytes) / Math.log(k))))
        return (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1) + " " + sizes[i]
    }

    function open(paths) {
        files = paths || []
        stage = "setup"
        counted = false
        progress = 0
        currentName = ""
        originalsNote = ""
        isOpen = true
        recount()
    }

    function recount() {
        counted = false
        if (dz) dz.countMediaPaths(files)
    }

    function close() {
        if (stage === "running") return            // Stop first
        isOpen = false
    }

    function start() {
        if (!dz || totalFiles === 0) return
        stage = "running"
        progress = 0
        currentName = ""
        dz.compressPaths(files)
    }

    Connections {
        target: root.dz
        function onMediaCountReady(images, videos, animated, bytes) {
            if (!root.isOpen || root.stage !== "setup") return
            root.images = images
            root.videos = videos
            root.animated = animated
            root.countBytes = bytes
            root.counted = true
        }
        function onSettingsChanged() {
            if (root.isOpen && root.stage === "setup") root.recount()   // a format set to "Don't compress"
        }
        function onFfmpegChanged() {
            if (root.isOpen && root.stage === "setup") root.recount()
        }
        function onCompressPathsProgress(pct, name) {
            if (root.stage !== "running") return
            root.progress = pct
            if (name) root.currentName = name
        }
        function onCompressPathsFinished(count, before, after, failed, left, stopped) {
            if (root.stage !== "running") return
            root.doneCount = count
            root.bytesBefore = before
            root.bytesAfter = after
            root.failedCount = failed
            root.leftCount = left
            root.stopped = stopped
            root.progress = 100
            root.stage = "result"
            if (count > 0) root.finished()
        }
        function onGalleryOriginalsHandled(message) {
            root.originalsNote = message
            root.finished()
        }
    }

    Keys.onEscapePressed: root.close()

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#B3000000"
        MouseArea {
            anchors.fill: parent
            onClicked: root.close()
        }
    }

    Rectangle {
        id: card
        objectName: "mediaCompressCard"
        anchors.centerIn: parent
        width: Math.min(620, parent.width - 32)
        readonly property real wanted: Math.min(parent.height - 32, body.implicitHeight + 40)
        // Weight from size: a tall card is heavier, so it swings in slower and settles softer
        readonly property real weight: Math.max(0.9, Math.min(2.4, Math.sqrt(width * wanted) / 260))
        height: wanted
        Behavior on height { SpringAnimation { spring: 3.0; damping: 0.42; mass: card.weight; epsilon: 0.3 } }
        scale: root.isOpen ? 1.0 : 0.88
        Behavior on scale { SpringAnimation { spring: 3.2; damping: 0.34; mass: card.weight; epsilon: 0.0008 } }
        radius: 10
        color: "#121725"
        border.color: "#0284C7"
        border.width: 1
        clip: true
        MouseArea { anchors.fill: parent; hoverEnabled: true }

        Flickable {
            anchors.fill: parent
            anchors.margins: 20
            contentHeight: body.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            ColumnLayout {
                id: body
                width: parent.width
                spacing: 14

                // Title
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    Text { text: "🗜"; font.pixelSize: 22 }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            Layout.fillWidth: true
                            text: root.stage === "result"
                                  ? (root.stopped ? root.tr("gc_title_stopped", "Compression stopped")
                                                  : root.tr("compress_review_title", "Compression finished"))
                                  : root.tr("gc_title", "Compress pictures & videos")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#7DD3FC"
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            text: root.tr("gc_selected", "%1 file(s) selected").replace("%1", root.files.length)
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                    }
                }

                // ── Choose ─────────────────────────────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    visible: root.stage === "setup"
                    implicitHeight: countText.implicitHeight + 18
                    radius: 8
                    color: "#0B1A2B"
                    border.color: "#164E63"
                    border.width: 1
                    Text {
                        id: countText
                        anchors.fill: parent
                        anchors.margins: 9
                        verticalAlignment: Text.AlignVCenter
                        text: !root.counted ? root.tr("gc_counting", "Looking at the files…")
                              : (root.totalFiles === 0
                                 ? root.tr("gc_nothing", "Nothing to compress with these settings (every type is set to \"Don't compress\", or videos need FFmpeg).")
                                 : root.tr("gc_counts", "%1 picture(s) · %2 video(s) · %3 animated · %4")
                                       .replace("%1", root.images).replace("%2", root.videos)
                                       .replace("%3", root.animated).replace("%4", root.formatBytes(root.countBytes)))
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: root.counted && root.totalFiles === 0 ? "#FBBF24" : "#E0F2FE"
                        wrapMode: Text.WordWrap
                    }
                }

                CompressAfterOptions {
                    Layout.fillWidth: true
                    visible: root.stage === "setup"
                    decompressor: root.dz
                    embedded: true
                }

                Text {
                    Layout.fillWidth: true
                    visible: root.stage === "setup"
                    text: root.tr("gc_note", "Copies are saved next to the originals and only kept when they're at least 5% smaller. When it's done you choose whether to keep the originals. These settings are shared with the Decompressor.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    wrapMode: Text.WordWrap
                }

                // ── Progress ───────────────────────────────────────────────
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: root.stage === "running"
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: root.currentName ? root.currentName : root.tr("gc_starting", "Starting…")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#CBD5E1"
                            elide: Text.ElideMiddle
                        }
                        Text {
                            text: Math.round(root.progress) + "%"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#7DD3FC"
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 8
                        radius: 4
                        color: "#1E293B"
                        clip: true
                        Rectangle {
                            height: parent.height
                            radius: 4
                            color: "#38BDF8"
                            width: parent.width * Math.max(0, Math.min(100, root.progress)) / 100
                            // light bar: quick, barely-damped spring
                            Behavior on width { SpringAnimation { spring: 5.0; damping: 0.6; mass: 0.5; epsilon: 0.3 } }
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.tr("gc_running_note", "Videos take a while. Stop keeps what's already done.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#64748B"
                        wrapMode: Text.WordWrap
                    }
                }

                // ── Result ─────────────────────────────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    visible: root.stage === "result"
                    implicitHeight: resultCol.implicitHeight + 18
                    radius: 8
                    color: "#0B1A2B"
                    border.color: "#164E63"
                    border.width: 1

                    ColumnLayout {
                        id: resultCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 12
                        spacing: 4
                        Text {
                            Layout.fillWidth: true
                            text: root.doneCount > 0
                                  ? root.tr("compress_review_count", "%1 file(s) compressed: %2 → %3 (%4% smaller)")
                                        .replace("%1", root.doneCount).replace("%2", root.formatBytes(root.bytesBefore))
                                        .replace("%3", root.formatBytes(root.bytesAfter))
                                        .replace("%4", root.bytesBefore > 0 ? Math.round((1 - root.bytesAfter / root.bytesBefore) * 100) : 0)
                                  : root.tr("gc_none_smaller", "Nothing was compressed: no copy came out smaller, so every file was left as it was.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: "#E0F2FE"
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: root.failedCount > 0
                            text: "⚠️ " + root.tr("compress_review_failed", "%1 file(s) couldn't be compressed and were left as they were (see the log).").replace("%1", root.failedCount)
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#FBBF24"
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: root.doneCount > 0 && !root.originalsNote
                            text: root.tr("compress_review_desc", "The compressed copies are saved next to the originals. Do you want to move the originals to the Recycle Bin?")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: root.originalsNote.length > 0
                            text: "✔ " + root.originalsNote
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#34D399"
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                // ── Buttons ────────────────────────────────────────────────
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Item { Layout.fillWidth: true }

                    StyledButton {
                        visible: root.stage === "setup"
                        text: root.tr("btn_cancel", "Cancel")
                        variant: "outline"
                        implicitHeight: 32
                        onClicked: root.close()
                    }
                    StyledButton {
                        objectName: "mediaCompressStart"
                        visible: root.stage === "setup"
                        enabled: root.counted && root.totalFiles > 0
                        text: root.tr("gc_compress", "Compress")
                        variant: "primary"
                        implicitHeight: 32
                        onClicked: root.start()
                    }
                    StyledButton {
                        visible: root.stage === "running"
                        text: root.tr("folder_change_stop", "Stop")
                        variant: "outline"
                        implicitHeight: 32
                        onClicked: if (root.dz) root.dz.cancelCompressPaths()
                    }
                    StyledButton {
                        visible: root.stage === "result" && root.doneCount > 0 && !root.originalsNote
                        text: root.tr("compress_keep_originals", "Keep originals")
                        variant: "outline"
                        implicitHeight: 32
                        onClicked: {
                            if (root.dz) root.dz.keepCompressedOriginals()
                            root.isOpen = false
                        }
                    }
                    StyledButton {
                        visible: root.stage === "result" && root.doneCount > 0 && !root.originalsNote
                        text: root.tr("compress_remove_originals", "Move originals to Recycle Bin")
                        variant: "primary"
                        implicitHeight: 32
                        onClicked: if (root.dz) root.dz.removeCompressedOriginals()
                    }
                    StyledButton {
                        visible: root.stage === "result" && (root.doneCount === 0 || root.originalsNote.length > 0)
                        text: root.tr("btn_close", "Close")
                        variant: "primary"
                        implicitHeight: 32
                        onClicked: root.isOpen = false
                    }
                }
            }
        }
    }
}
