import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia
import QtCore

// ── Media Lightbox Modal ───────────────────────────────────────────────────
// High-performance inline previews for Images, animated GIFs, Videos, and Audio.
Item {
    id: root

    property var bridge: null
    property bool isOpen: false
    property var mediaList: []
    property int currentIndex: 0

    readonly property var currentItem: (mediaList && currentIndex >= 0 && currentIndex < mediaList.length) ? mediaList[currentIndex] : null
    readonly property string itemPath: currentItem ? (currentItem.path || "") : ""
    readonly property string itemName: currentItem ? (currentItem.name || "") : ""
    readonly property string itemExt: currentItem ? ((currentItem.ext || "").toLowerCase()) : ""
    readonly property bool isImage: [".jpg", ".jpeg", ".jpe", ".jfif", ".pjpeg", ".pjp", ".png", ".apng", ".gif", ".webp", ".avif", ".heic", ".heif", ".jxl", ".bmp", ".dib", ".svg", ".svgz", ".ico", ".cur", ".tif", ".tiff", ".tga", ".psd", ".jp2", ".j2k", ".dds", ".qoi", ".pcx", ".ppm", ".pgm", ".pbm", ".xbm", ".xpm", ".icns", ".wbmp"].indexOf(itemExt) >= 0
    readonly property bool isVideo: [".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".flv", ".f4v", ".wmv", ".asf", ".mpg", ".mpeg", ".m2v", ".ts", ".mts", ".m2ts", ".3gp", ".3g2", ".ogv", ".vob", ".divx"].indexOf(itemExt) >= 0
    readonly property bool isAudio: [".mp3", ".flac", ".wav", ".ogg", ".oga", ".m4a", ".aac", ".opus", ".wma", ".aiff", ".aif", ".alac", ".mka"].indexOf(itemExt) >= 0
    property bool animPaused: false

    // ── Zoom (smooth, toward the cursor, like Photos / Movies & TV) ──────────
    // zoomFactor is where the zoom is heading; zoomShown springs after it. The point under the
    // cursor stays put: the picture's centre is kept at anchor - anchorOffset * zoomShown.
    property real zoomFactor: 1.0
    property real zoomShown: zoomFactor
    property bool zoomAnimated: true
    Behavior on zoomShown {
        enabled: root.zoomAnimated
        SpringAnimation { spring: 4.0; damping: 0.42; mass: 0.9; epsilon: 0.0005 }
    }
    readonly property real minZoom: 0.25
    readonly property real maxZoom: 8.0
    property real anchorX: 0
    property real anchorY: 0
    property real anchorOffsetX: 0     // from the picture's centre to the anchor, at zoom 1
    property real anchorOffsetY: 0

    // Pin the picture point under (px, py) so zooming / dragging keeps it there
    function pinAt(px, py) {
        var s = Math.max(0.0001, zoomShown)
        anchorOffsetX = (px - imageViewport.centerX) / s
        anchorOffsetY = (py - imageViewport.centerY) / s
        anchorX = px
        anchorY = py
    }
    function zoomAt(z, px, py) {
        pinAt(px, py)
        zoomFactor = Math.max(minZoom, Math.min(maxZoom, z))
    }
    // Buttons and + / - keys zoom around the middle of the view
    function zoomStep(dir) {
        zoomAt(zoomFactor * (dir > 0 ? 1.25 : 0.8), imageViewport.width / 2, imageViewport.height / 2)
    }
    // animated: ease back to fit (reset button / 0 key); otherwise snap (a new picture)
    function resetZoom(animated) {
        if (animated) {
            zoomAt(1.0, imageViewport.width / 2, imageViewport.height / 2)
            return
        }
        zoomAnimated = false
        zoomFactor = 1.0
        zoomShown = 1.0                                              // stop any zoom still in flight…
        zoomShown = Qt.binding(function() { return root.zoomFactor }) // …and follow zoomFactor again
        anchorOffsetX = 0
        anchorOffsetY = 0
        anchorX = imageViewport.width / 2
        anchorY = imageViewport.height / 2
        zoomAnimated = true
    }
    property bool isLooping: false

    // ── Player (video / audio) ─────────────────────────────────────────────
    readonly property bool isMedia: isVideo || isAudio
    readonly property bool mediaPlaying: mediaPlayer.playbackState === MediaPlayer.PlayingState
    readonly property bool mediaEnded: mediaPlayer.mediaStatus === MediaPlayer.EndOfMedia
    property real playbackSpeed: 1.0
    readonly property var speedSteps: [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
    property bool showShortcuts: false

    // Volume, mute, loop and speed are remembered between files and sessions
    Settings {
        category: "mediaPlayer"
        property alias volume: audioOutput.volume
        property alias muted: audioOutput.muted
        property alias looping: root.isLooping
        property alias speed: root.playbackSpeed
    }

    function rateLabel(r) { return (Math.round(r * 100) / 100) + "×" }
    // 1:05 for short clips, 1:02:05 once a file is an hour or longer
    function formatClock(ms, total) {
        var t = Math.max(0, Math.floor((ms || 0) / 1000))
        var h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60
        var ss = (sec < 10 ? "0" : "") + sec
        if (h > 0 || (total || 0) >= 3600000) return h + ":" + (m < 10 ? "0" : "") + m + ":" + ss
        return m + ":" + ss
    }
    function togglePlay() {
        if (!isMedia) return
        if (mediaEnded) {
            mediaPlayer.setPosition(0)
            mediaPlayer.play()
            osd("↻", "Replay")
        } else if (mediaPlaying) {
            mediaPlayer.pause()
            osd("❚❚", "")
        } else {
            mediaPlayer.play()
            osd("▶", "")
        }
    }
    function seekTo(ms) {
        if (!isMedia || mediaPlayer.duration <= 0) return
        mediaPlayer.setPosition(Math.max(0, Math.min(mediaPlayer.duration, ms)))
    }
    function seekBy(ms) {
        if (!isMedia || mediaPlayer.duration <= 0) return
        seekTo(mediaPlayer.position + ms)
        osd(ms < 0 ? "↺" : "↻", (ms < 0 ? "−" : "+") + Math.round(Math.abs(ms) / 1000) + " s")
    }
    function seekFraction(f) {
        if (!isMedia || mediaPlayer.duration <= 0) return
        seekTo(mediaPlayer.duration * f)
        osd("⇥", Math.round(f * 100) + "%")
    }
    function volumeIcon() {
        return (audioOutput.muted || audioOutput.volume === 0) ? "🔇" : (audioOutput.volume < 0.34 ? "🔈" : (audioOutput.volume < 0.67 ? "🔉" : "🔊"))
    }
    function setVolume(v, announce) {
        audioOutput.volume = Math.max(0, Math.min(1, v))
        audioOutput.muted = false
        if (announce) osd(volumeIcon(), Math.round(audioOutput.volume * 100) + "%")
    }
    function changeVolume(d) { setVolume(audioOutput.volume + d, true) }
    function toggleMute() {
        audioOutput.muted = !audioOutput.muted
        osd(volumeIcon(), audioOutput.muted ? "Muted" : Math.round(audioOutput.volume * 100) + "%")
    }
    function setSpeed(r) {
        playbackSpeed = r
        osd("⏱", rateLabel(r))
    }
    function changeSpeed(dir) {
        var i = 0
        for (var k = 0; k < speedSteps.length; k++) if (Math.abs(speedSteps[k] - playbackSpeed) < 0.001) i = k
        setSpeed(speedSteps[Math.max(0, Math.min(speedSteps.length - 1, i + dir))])
    }
    // , and . step one frame while paused (like most players)
    function stepFrame(dir) {
        if (!isVideo) return
        if (mediaPlaying) mediaPlayer.pause()
        var fps = Number(mediaPlayer.metaData.value(MediaMetaData.VideoFrameRate)) || 30
        seekTo(mediaPlayer.position + dir * 1000 / fps)
        osd(dir < 0 ? "◂" : "▸", "1 frame")
    }

    // ── Full screen (F): the viewer takes over the whole screen ─────────────
    property bool fullscreen: false
    property Item homeParent: null
    property int restoreVisibility: Window.Windowed
    function toggleFullscreen() { setFullscreen(!fullscreen) }
    function setFullscreen(on) {
        var win = root.Window.window
        if (!win || on === fullscreen) return
        if (on) {
            homeParent = root.parent
            restoreVisibility = win.visibility
            root.parent = win.contentItem
            fullscreen = true
            win.showFullScreen()
        } else {
            fullscreen = false
            if (homeParent) root.parent = homeParent
            if (restoreVisibility === Window.Maximized) win.showMaximized()
            else win.showNormal()
        }
        poke()
        root.forceActiveFocus()
    }

    // ── Auto-hiding controls: they fade while a video plays and the mouse rests ──
    property bool userActive: true
    Timer { id: idleTimer; interval: 2600; onTriggered: root.userActive = false }
    function poke() {
        userActive = true
        idleTimer.restart()
    }
    // Hover updates also arrive for a resting mouse (the video keeps repainting), so only real movement counts
    property real lastMouseX: -1
    property real lastMouseY: -1
    function pokeAt(x, y) {
        if (Math.abs(x - lastMouseX) < 1.5 && Math.abs(y - lastMouseY) < 1.5) return
        lastMouseX = x
        lastMouseY = y
        poke()
    }
    readonly property bool chromeShown: userActive || showShortcuts
        || (isVideo ? (!mediaPlaying || mediaControls.busy) : (isAudio || !fullscreen))

    // ── Centre bubble confirming an action ("+5 s", "🔊 65%", "1.5×", ❚❚ …) ──
    property string osdIcon: ""
    property string osdText: ""
    property bool osdShown: false
    property real osdScale: 1
    property bool osdSpring: true
    Behavior on osdScale { enabled: root.osdSpring; SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.002 } }
    Timer { id: osdTimer; interval: 650; onTriggered: root.osdShown = false }
    function osd(icon, text) {
        osdIcon = icon
        osdText = text
        osdSpring = false
        osdScale = 0.8
        osdSpring = true
        osdScale = 1
        osdShown = true
        osdTimer.restart()
    }

    // Extras: rotate, copy, favourite / rating, source post, info, delete
    property var tools: null            // galleryTools (marks, clipboard, source post)
    property int rotationSteps: 0       // quarter turns clockwise, reset per item
    property bool showInfo: false
    property bool confirmDelete: false
    property string sourceUrl: ""
    property string postId: ""
    property var marks: ({})
    property string flashText: ""
    signal itemDeleted(string path)

    function markKey(path) { return Qt.platform.os === "windows" ? (path || "").toLowerCase() : (path || "") }
    readonly property var currentMark: (currentItem && marks) ? (marks[markKey(itemPath)] || null) : null
    readonly property bool isFav: !!currentMark && !!currentMark.fav
    readonly property int rating: currentMark ? (currentMark.rating || 0) : 0
    readonly property bool sideways: rotationSteps % 2 === 1

    function flash(text) {
        flashText = text
        flashTimer.restart()
    }
    function rotate(dir) {
        rotationSteps = (rotationSteps + dir + 4) % 4
    }
    function copyCurrent() {
        if (!tools || !itemPath) return
        flash(tools.copyFileToClipboard(itemPath) ? (isImage ? "Copied picture (paste into chats, or as a file in Explorer)" : "Copied file (paste it in Explorer or a chat)") : "Couldn't copy this file")
    }
    function toggleFav() {
        if (!tools || !itemPath) return
        tools.setFavorite([itemPath], !isFav)
        flash(isFav ? "Removed from favourites" : "Added to favourites")
    }
    function rate(n) {
        if (!tools || !itemPath) return
        var value = (n === rating) ? 0 : n   // same number again clears it
        tools.setRating([itemPath], value)
        flash(value > 0 ? ("Rated " + "★★★★★".substring(0, value)) : "Rating cleared")
    }
    function deleteCurrent() {
        if (!bridge || !itemPath) return
        var path = itemPath
        // Let go of the file first: a playing video or animation keeps it open
        releaseMedia()
        holdFile = false
        var res = bridge.deleteItems([path])
        holdFile = true
        confirmDelete = false
        if (!res || res.deleted < 1) {
            loadCurrentItem()
            flash("Couldn't move it to the Recycle Bin" + (res && res.errors && res.errors.length ? ": " + res.errors[0] : ""))
            return
        }
        var list = mediaList.slice()
        list.splice(currentIndex, 1)
        itemDeleted(path)
        if (!list.length) {
            mediaList = []
            close()
            return
        }
        mediaList = list
        currentIndex = Math.min(currentIndex, list.length - 1)
        resetZoom(false)
        loadCurrentItem()
        flash("Moved to the Recycle Bin")
    }
    function formatDateTime(ts) {
        if (!ts || ts <= 0) return ""
        var d = new Date(ts * 1000)
        function z(n) { return (n < 10 ? "0" : "") + n }
        return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + "  " + z(d.getHours()) + ":" + z(d.getMinutes())
    }

    Timer { id: flashTimer; interval: 1800; onTriggered: root.flashText = "" }

    Connections {
        target: root.tools
        function onMarksChanged() { root.marks = root.tools.allMarks() }
    }

    anchors.fill: parent
    z: 9999
    // Fades in / out (weight-based motion); no input while closing
    opacity: isOpen ? 1 : 0
    visible: opacity > 0.005
    enabled: isOpen
    Behavior on opacity { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "0 B"
        var k = 1024
        var sizes = ["B", "KB", "MB", "GB", "TB"]
        var i = Math.floor(Math.log(bytes) / Math.log(k))
        if (i < 0) i = 0
        if (i >= sizes.length) i = sizes.length - 1
        return (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1) + " " + sizes[i]
    }

    function formatTime(ms) {
        if (!ms || ms <= 0) return "00:00"
        var totalSec = Math.floor(ms / 1000)
        var min = Math.floor(totalSec / 60)
        var sec = totalSec % 60
        var sMin = min < 10 ? "0" + min : "" + min
        var sSec = sec < 10 ? "0" + sec : "" + sec
        return sMin + ":" + sSec
    }

    function toUrl(path) {
        if (!path) return ""
        if (bridge && bridge.pathToUrl) {
            return bridge.pathToUrl(path)
        }
        var p = path.replace(/\\/g, "/")
        return p.indexOf("file://") === 0 ? p : ("file:///" + p)
    }

    function open(item, allMedia) {
        mediaList = allMedia || []
        var idx = 0
        if (item) {
            for (var i = 0; i < mediaList.length; i++) {
                if (mediaList[i].path === item.path) {
                    idx = i
                    break
                }
            }
        }
        currentIndex = idx
        resetZoom(false)
        if (tools) marks = tools.allMarks()
        isOpen = true
        root.forceActiveFocus()
        loadCurrentItem()
    }

    // False while the current file is being deleted, so nothing in the viewer keeps it open
    property bool holdFile: true

    // stop() alone keeps the file open (Windows then refuses to move, rename or delete it)
    function releaseMedia() {
        if (!mediaPlayer) return
        mediaPlayer.stop()
        mediaPlayer.source = ""
    }

    function close() {
        if (fullscreen) setFullscreen(false)
        showShortcuts = false
        releaseMedia()
        isOpen = false
    }

    // Slide-in offset for the next / previous item (springs back to 0)
    property real slideX: 0
    property bool slideSpring: true
    Behavior on slideX { enabled: root.slideSpring; SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
    function kick(dir) {
        slideSpring = false
        slideX = dir * 90
        slideSpring = true
        slideX = 0
    }

    function prevItem() {
        if (mediaList.length <= 1) return
        kick(-1)
        if (currentIndex > 0) currentIndex--
        else currentIndex = mediaList.length - 1
        resetZoom(false)
        loadCurrentItem()
    }

    function nextItem() {
        if (mediaList.length <= 1) return
        kick(1)
        if (currentIndex < mediaList.length - 1) currentIndex++
        else currentIndex = 0
        resetZoom(false)
        loadCurrentItem()
    }

    function loadCurrentItem() {
        if (!currentItem) return
        rotationSteps = 0
        confirmDelete = false
        animPaused = false
        if (tools) {
            var src = tools.sourcePost(itemPath)
            sourceUrl = src.url || ""
            postId = src.postId || ""
        }
        var url = toUrl(itemPath)
        poke()
        if (isVideo || isAudio) {
            if (mediaPlayer.source != url) {
                mediaPlayer.source = url
            }
            mediaPlayer.play()
        } else {
            releaseMedia()
        }
    }

    // Keyboard controls. Video / audio use the keys of common players (YouTube, Movies & TV);
    // pictures keep the viewer keys. "?" lists everything.
    Keys.onPressed: function(event) {
        if (!isOpen) return
        var ctrl = (event.modifiers & Qt.ControlModifier) !== 0
        var shift = (event.modifiers & Qt.ShiftModifier) !== 0
        var alt = (event.modifiers & Qt.AltModifier) !== 0
        var k = event.key
        var t = event.text
        if (confirmDelete) {
            if (k === Qt.Key_Return || k === Qt.Key_Enter) deleteCurrent()
            else if (k === Qt.Key_Escape) confirmDelete = false
            event.accepted = true
            return
        }
        event.accepted = true
        poke()

        // ── Everywhere ──
        if (k === Qt.Key_Escape) {
            if (showShortcuts) showShortcuts = false
            else if (fullscreen) setFullscreen(false)
            else if (showInfo) showInfo = false
            else close()
        } else if (t === "?" || k === Qt.Key_F1) {
            showShortcuts = !showShortcuts
        } else if (k === Qt.Key_F && !ctrl && !alt) {
            toggleFullscreen()
        } else if (k === Qt.Key_D && ctrl) {
            toggleFav()
        } else if (k === Qt.Key_C && ctrl) {
            copyCurrent()
        } else if (k === Qt.Key_R && !ctrl) {
            rotate(shift ? -1 : 1)
        } else if (k === Qt.Key_I && !ctrl) {
            showInfo = !showInfo
        } else if (k === Qt.Key_Delete) {
            confirmDelete = true
        } else if (k === Qt.Key_PageUp || ((k === Qt.Key_Left) && (ctrl || !isMedia))) {
            prevItem()
        } else if (k === Qt.Key_PageDown || ((k === Qt.Key_Right) && (ctrl || !isMedia))) {
            nextItem()
        } else if (isMedia) {
            // ── Video / audio ──
            if (k === Qt.Key_Space || k === Qt.Key_K || k === Qt.Key_MediaPlay || k === Qt.Key_MediaTogglePlayPause) togglePlay()
            else if (k === Qt.Key_Left) seekBy(-5000)
            else if (k === Qt.Key_Right) seekBy(5000)
            else if (k === Qt.Key_J) seekBy(-10000)
            else if (k === Qt.Key_L) seekBy(10000)
            else if (k === Qt.Key_Up) changeVolume(0.05)
            else if (k === Qt.Key_Down) changeVolume(-0.05)
            else if (k === Qt.Key_M) toggleMute()
            else if (k === Qt.Key_Home) { seekTo(0); osd("⇤", "Start") }
            else if (k === Qt.Key_End) { seekTo(mediaPlayer.duration - 500); osd("⇥", "End") }
            else if (t === "<") changeSpeed(-1)
            else if (t === ">") changeSpeed(1)
            else if (t === ",") stepFrame(-1)
            else if (t === ".") stepFrame(1)
            else if (k >= Qt.Key_0 && k <= Qt.Key_9 && !ctrl) seekFraction((k - Qt.Key_0) / 10)
            else event.accepted = false
        } else {
            // ── Pictures ──
            if (k === Qt.Key_Space) {
                if (isImage && animView.isAnimated) {
                    animPaused = !animPaused
                    flash(animPaused ? "Animation paused (Space)" : "Animation playing")
                }
            }
            else if (k >= Qt.Key_1 && k <= Qt.Key_5 && !ctrl) rate(k - Qt.Key_0)
            else if (k === Qt.Key_Plus || k === Qt.Key_Equal) zoomStep(1)
            else if (k === Qt.Key_Minus) zoomStep(-1)
            else if (k === Qt.Key_0) resetZoom(true)
            else event.accepted = false
        }
    }

    component LbButton: Rectangle {
        id: lbb
        property string glyph: ""
        property string tip: ""
        property bool active: false
        property bool danger: false
        property color activeColor: "#38BDF8"
        signal clicked()
        width: 28
        height: 28
        radius: 5
        color: lbbMouse.containsMouse ? (danger ? "#3A1620" : "#222D42") : "#141A28"
        border.color: active ? activeColor : (lbbMouse.containsMouse ? (danger ? "#EF4444" : "#38BDF8") : "#2A364E")
        border.width: 1
        Text {
            anchors.centerIn: parent
            text: lbb.glyph
            font.pixelSize: 13
            color: lbb.active ? lbb.activeColor : (lbb.danger ? "#F87171" : "#E2E8F0")
        }
        Springy { hover: lbbMouse.containsMouse; pressed: lbbMouse.pressed }
        MouseArea {
            id: lbbMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: lbb.clicked()
            ToolTip.visible: containsMouse && lbb.tip.length > 0
            ToolTip.delay: 250
            ToolTip.text: lbb.tip
        }
    }

    // Media Player backend
    AudioOutput {
        id: audioOutput
        volume: 0.85
        muted: false
    }

    MediaPlayer {
        id: mediaPlayer
        audioOutput: audioOutput
        videoOutput: videoOutput
        loops: root.isLooping ? MediaPlayer.Infinite : 1
        playbackRate: root.playbackSpeed
    }

    // Dark translucent backdrop
    Rectangle {
        anchors.fill: parent
        color: root.fullscreen ? "#000000" : "#080B11"
        opacity: root.isOpen ? (root.fullscreen ? 1.0 : 0.96) : 0.0

        Behavior on opacity {
            NumberAnimation { duration: 200 }
        }

        MouseArea {
            anchors.fill: parent
            // Swallow clicks, hover and the wheel so nothing behind the viewer reacts
            hoverEnabled: true
            onClicked: {}
            onWheel: (wheel) => wheel.accepted = true
        }
    }

    // Main Lightbox Container
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.fullscreen ? 0 : 14
        spacing: root.fullscreen ? 0 : 10
        // The viewer is the heaviest panel: it eases in on a soft spring
        scale: root.isOpen ? 1.0 : 0.94
        Behavior on scale { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.0008 } }

        // 1. TOP LIGHTBOX TOOLBAR (hidden in full screen)
        RowLayout {
            visible: !root.fullscreen
            Layout.fillWidth: true
            spacing: 12

            // Close button
            Rectangle {
                width: 32
                height: 32
                radius: 6
                color: closeMouse.containsMouse ? "#EF4444" : "#1A2234"
                border.color: closeMouse.containsMouse ? "#DC2626" : "#2E3A52"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                }

                Springy { hover: closeMouse.containsMouse; pressed: closeMouse.pressed }
                MouseArea {
                    id: closeMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.close()
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Close media viewer (Esc)"
                }
            }

            // Media Info Tag
            Rectangle {
                implicitHeight: 28
                implicitWidth: tagRow.implicitWidth + 16
                radius: 6
                color: "#131926"
                border.color: "#27344D"
                border.width: 1

                Row {
                    id: tagRow
                    anchors.centerIn: parent
                    spacing: 8

                    Text {
                        text: root.isVideo ? "🎬 VIDEO" : (root.isAudio ? "🎵 AUDIO" : "🖼️ IMAGE")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 700
                        color: root.isVideo ? "#8B5CF6" : (root.isAudio ? "#10B981" : "#EC4899")
                    }

                    Text {
                        text: (root.currentIndex + 1) + " / " + root.mediaList.length
                        font.family: "Segoe UI, monospace"
                        font.pixelSize: 10
                        color: "#94A3B8"
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Media item " + (root.currentIndex + 1) + " of " + root.mediaList.length + " in this folder"
                }
            }

            // Filename
            Text {
                text: root.itemName
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 13
                font.weight: 600
                color: "#F8FAFC"
                elide: Text.ElideMiddle
                Layout.fillWidth: true
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: root.itemPath
                }
            }

            // Image Dimensions pill (when viewing image)
            Rectangle {
                visible: root.isImage && imgViewer.status === Image.Ready && imgViewer.implicitWidth > 1
                implicitHeight: 28
                implicitWidth: dimText.implicitWidth + 14
                radius: 6
                color: "#131926"
                border.color: "#27344D"
                border.width: 1

                Text {
                    id: dimText
                    anchors.centerIn: parent
                    text: imgViewer.implicitWidth + " × " + imgViewer.implicitHeight
                    font.family: "Segoe UI, monospace"
                    font.pixelSize: 10
                    color: "#38BDF8"
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Image dimensions: " + imgViewer.implicitWidth + " × " + imgViewer.implicitHeight + " px"
                }
            }

            // File Size Pill
            Rectangle {
                visible: root.currentItem && root.currentItem.size > 0
                implicitHeight: 28
                implicitWidth: szText.implicitWidth + 14
                radius: 6
                color: "#131926"
                border.color: "#27344D"
                border.width: 1

                Text {
                    id: szText
                    anchors.centerIn: parent
                    text: root.currentItem ? formatBytes(root.currentItem.size) : ""
                    font.family: "Segoe UI, monospace"
                    font.pixelSize: 10
                    color: "#94A3B8"
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "File size on disk: " + (root.currentItem ? root.formatBytes(root.currentItem.size) : "0 B")
                }
            }

            // Image Zoom Controls
            Row {
                visible: root.isImage
                spacing: 4

                Rectangle {
                    width: 28; height: 28; radius: 5
                    color: zoomInMouse.containsMouse ? "#222D42" : "#141A28"
                    border.color: "#2A364E"; border.width: 1
                    Text { anchors.centerIn: parent; text: "➕"; font.pixelSize: 10; color: "#E2E8F0" }
                    Springy { hover: zoomInMouse.containsMouse; pressed: zoomInMouse.pressed }
                    MouseArea {
                        id: zoomInMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: root.zoomStep(1)
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Zoom In (+ or scroll up over the picture)\nCurrent zoom: " + Math.round(root.zoomFactor * 100) + "%"
                    }
                }
                Rectangle {
                    width: 28; height: 28; radius: 5
                    color: zoomOutMouse.containsMouse ? "#222D42" : "#141A28"
                    border.color: "#2A364E"; border.width: 1
                    Text { anchors.centerIn: parent; text: "➖"; font.pixelSize: 10; color: "#E2E8F0" }
                    Springy { hover: zoomOutMouse.containsMouse; pressed: zoomOutMouse.pressed }
                    MouseArea {
                        id: zoomOutMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: root.zoomStep(-1)
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Zoom Out (- or scroll down over the picture)\nCurrent zoom: " + Math.round(root.zoomFactor * 100) + "%"
                    }
                }
                Rectangle {
                    width: 28; height: 28; radius: 5
                    color: zoomResetMouse.containsMouse ? "#222D42" : "#141A28"
                    border.color: "#2A364E"; border.width: 1
                    Text { anchors.centerIn: parent; text: "1:1"; font.pixelSize: 10; font.weight: 600; color: "#38BDF8" }
                    Springy { hover: zoomResetMouse.containsMouse; pressed: zoomResetMouse.pressed }
                    MouseArea {
                        id: zoomResetMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: root.resetZoom(true)
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Fit the picture to the window (0 or double-click)"
                    }
                }
            }

            // Extras: rotate · copy · favourite · rating · source post · info · delete
            Row {
                spacing: 4
                Layout.alignment: Qt.AlignVCenter

                LbButton { visible: root.isImage || root.isVideo; glyph: "⟲"; tip: "Rotate left (Shift+R)"; onClicked: root.rotate(-1) }
                LbButton { visible: root.isImage || root.isVideo; glyph: "⟳"; tip: "Rotate right (R)"; onClicked: root.rotate(1) }
                LbButton { glyph: "⛶"; tip: "Full screen (F)"; onClicked: root.toggleFullscreen() }
                LbButton { glyph: "⌨"; active: root.showShortcuts; tip: "Keyboard shortcuts (?)"; onClicked: root.showShortcuts = !root.showShortcuts }
                LbButton { glyph: "⧉"; tip: root.isImage ? "Copy picture (Ctrl+C): paste into chats, or as a file in Explorer" : "Copy file (Ctrl+C)"; onClicked: root.copyCurrent() }
                LbButton { visible: !!root.tools; glyph: root.isFav ? "★" : "☆"; active: root.isFav; activeColor: "#FBBF24"; tip: root.isFav ? "Remove from favourites (Ctrl+D)" : "Add to favourites (Ctrl+D)"; onClicked: root.toggleFav() }

                // Rating: click a star, click it again to clear (keys 1–5)
                Rectangle {
                    visible: !!root.tools
                    width: lbStars.implicitWidth + 12
                    height: 28
                    radius: 5
                    color: "#141A28"
                    border.color: "#2A364E"
                    Row {
                        id: lbStars
                        anchors.centerIn: parent
                        spacing: 1
                        Repeater {
                            model: 5
                            delegate: Text {
                                readonly property int n: index + 1
                                text: n <= root.rating ? "★" : "☆"
                                font.pixelSize: 14
                                color: n <= root.rating ? "#FBBF24" : "#64748B"
                                MouseArea {
                                    anchors.fill: parent
                                    anchors.margins: -2
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.rate(parent.n)
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 400
                                    ToolTip.text: "Rate " + parent.n + " (key " + parent.n + ")"
                                }
                            }
                        }
                    }
                }

                LbButton { visible: root.sourceUrl.length > 0; glyph: "🌐"; tip: "View the source post in your browser"; onClicked: Qt.openUrlExternally(root.sourceUrl) }
                LbButton { glyph: "ⓘ"; active: root.showInfo; tip: "File info (I)"; onClicked: root.showInfo = !root.showInfo }
                LbButton { glyph: "🗑"; danger: true; tip: "Move to the Recycle Bin (Del)"; onClicked: root.confirmDelete = true }
            }

            // Open Externally Button
            Rectangle {
                implicitHeight: 28
                implicitWidth: extRow.implicitWidth + 14
                radius: 6
                color: extMouse.containsMouse ? "#1E273A" : "#141A28"
                border.color: extMouse.containsMouse ? "#38BDF8" : "#2A364E"
                border.width: 1

                Row {
                    id: extRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "↗"; font.pixelSize: 11; color: "#E2E8F0" }
                    Text { text: "Open Externally"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; font.weight: 600; color: "#E2E8F0" }
                }
                Springy { hover: extMouse.containsMouse; pressed: extMouse.pressed }
                MouseArea {
                    id: extMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (root.bridge && root.bridge.openPathInSystem) {
                            root.bridge.openPathInSystem(root.itemPath)
                        }
                    }
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Open file in your system's default media player / viewer"
                }
            }

            // Reveal in Folder Button
            Rectangle {
                width: 28; height: 28; radius: 5
                color: folderMouse.containsMouse ? "#1E273A" : "#141A28"
                border.color: folderMouse.containsMouse ? "#38BDF8" : "#2A364E"
                border.width: 1
                Text { anchors.centerIn: parent; text: "📂"; font.pixelSize: 12 }
                Springy { hover: folderMouse.containsMouse; pressed: folderMouse.pressed }
                MouseArea {
                    id: folderMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (root.bridge && root.bridge.openFolder) {
                            var dir = root.itemPath.substring(0, Math.max(root.itemPath.lastIndexOf("/"), root.itemPath.lastIndexOf("\\")))
                            root.bridge.openFolder(dir)
                        }
                    }
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Open containing folder in File Explorer / OS manager"
                }
            }
        }

        // 2. MAIN MEDIA DISPLAY AREA WITH CHEVRONS
        Item {
            id: mediaArea
            Layout.fillWidth: true
            Layout.fillHeight: true
            HoverHandler { onPointChanged: root.pokeAt(point.scenePosition.x, point.scenePosition.y) }
            transform: Translate { x: root.slideX }
            opacity: 1.0 - Math.min(0.6, Math.abs(root.slideX) / 150)

            // Image / GIF preview: scroll zooms toward the cursor, drag pans when zoomed in
            Item {
                id: imageViewport
                visible: root.isImage
                anchors.fill: parent
                clip: true

                // The picture's on-screen size at zoom 1 (a quarter turn swaps it)
                readonly property real fitW: {
                    var w = imgViewer.paintedWidth > 0 ? imgViewer.paintedWidth : imgStage.width
                    var h = imgViewer.paintedHeight > 0 ? imgViewer.paintedHeight : imgStage.height
                    return root.sideways ? h : w
                }
                readonly property real fitH: {
                    var w = imgViewer.paintedWidth > 0 ? imgViewer.paintedWidth : imgStage.width
                    var h = imgViewer.paintedHeight > 0 ? imgViewer.paintedHeight : imgStage.height
                    return root.sideways ? w : h
                }
                // Smaller than the view: centred. Bigger: may move, but never leaves a gap at an edge.
                function clampCenter(c, view, size) {
                    return size <= view ? view / 2 : Math.max(view - size / 2, Math.min(size / 2, c))
                }
                readonly property real centerX: clampCenter(root.anchorX - root.anchorOffsetX * root.zoomShown, width, fitW * root.zoomShown)
                readonly property real centerY: clampCenter(root.anchorY - root.anchorOffsetY * root.zoomShown, height, fitH * root.zoomShown)
                readonly property bool canPan: fitW * root.zoomShown > width + 0.5 || fitH * root.zoomShown > height + 0.5

                Item {
                    id: imgStage
                    // Turned sideways, the image fits the swapped box so it still fills the view
                    width: root.sideways ? imageViewport.height : imageViewport.width
                    height: root.sideways ? imageViewport.width : imageViewport.height
                    x: imageViewport.centerX - width / 2
                    y: imageViewport.centerY - height / 2
                    rotation: root.rotationSteps * 90
                    scale: root.zoomShown

                    Image {
                        id: imgViewer
                        anchors.fill: parent
                        // Decoded by the "full" provider: Qt, then Pillow (AVIF, files with the wrong extension)
                        source: (root.isImage && root.visible && root.holdFile) ? ("image://full/" + encodeURIComponent(root.itemPath)) : ""
                        // The provider keeps recent pictures for 5 minutes, so Qt doesn't need its own copy
                        cache: false
                        asynchronous: true
                        fillMode: Image.PreserveAspectFit
                        // Stays sharp when zoomed in (decoded at full size, smoothed when scaled)
                        smooth: true
                        mipmap: true
                        // Hidden (but still loaded, for its size) while the animated version plays on top
                        opacity: animView.isAnimated ? 0 : 1
                    }

                    // GIF / WebP / APNG / animated AVIF… (Space pauses)
                    AnimatedMedia {
                        id: animView
                        anchors.fill: parent
                        path: root.isImage && root.isOpen && root.holdFile ? root.itemPath : ""
                        tools: root.tools
                        playing: !root.animPaused
                    }
                }

                MouseArea {
                    id: panArea
                    anchors.fill: parent
                    cursorShape: !root.chromeShown ? Qt.BlankCursor : (imageViewport.canPan ? (pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor) : Qt.ArrowCursor)
                    property real pressX: 0
                    property real pressY: 0
                    property real startX: 0
                    property real startY: 0
                    onPressed: (mouse) => {
                        root.pinAt(mouse.x, mouse.y)
                        pressX = mouse.x; pressY = mouse.y
                        startX = root.anchorX; startY = root.anchorY
                    }
                    onPositionChanged: (mouse) => {
                        if (!pressed) return
                        root.anchorX = startX + mouse.x - pressX
                        root.anchorY = startY + mouse.y - pressY
                        // Past an edge the picture stops; keep the anchor with it so dragging back responds at once
                        var rawX = root.anchorX - root.anchorOffsetX * root.zoomShown
                        var rawY = root.anchorY - root.anchorOffsetY * root.zoomShown
                        var fixX = imageViewport.centerX - rawX
                        var fixY = imageViewport.centerY - rawY
                        if (fixX !== 0) { root.anchorX += fixX; startX += fixX }
                        if (fixY !== 0) { root.anchorY += fixY; startY += fixY }
                    }
                    onDoubleClicked: (mouse) => root.zoomAt(root.zoomFactor > 1.2 ? 1.0 : 2.5, mouse.x, mouse.y)
                    onWheel: (wheel) => {
                        var d = wheel.angleDelta.y !== 0 ? wheel.angleDelta.y : wheel.angleDelta.x
                        if (d === 0) return
                        // One notch ≈ 20%; quick spins and touchpads add up smoothly
                        root.zoomAt(root.zoomFactor * Math.pow(1.0015, d), wheel.x, wheel.y)
                    }
                }
            }

            // Animation frame counter / paused hint
            Rectangle {
                visible: root.isImage && animView.isAnimated
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                anchors.leftMargin: 56
                anchors.bottomMargin: 10
                width: animTag.implicitWidth + 16
                height: 22
                radius: 11
                color: "#CC0F172A"
                border.color: root.animPaused ? "#F59E0B" : "#2E3A52"
                z: 4
                Text {
                    id: animTag
                    anchors.centerIn: parent
                    text: (root.animPaused ? "⏸ paused" : "▶ animated") + (animView.frameCount > 0 ? "  •  " + animView.frameCount + " frames" : "") + "  •  Space"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#CBD5E1"
                }
            }

            // A video / audio file the player can't open
            Column {
                anchors.centerIn: parent
                spacing: 8
                z: 4
                visible: (root.isVideo || root.isAudio) && mediaPlayer.error !== MediaPlayer.NoError
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: root.isVideo ? "🎬" : "🎵"; font.pixelSize: 40; opacity: 0.5 }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "This " + (root.isVideo ? "video" : "audio file") + " can't be played here."
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 13
                    color: "#94A3B8"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: mediaPlayer.errorString + "  •  Try \"Open Externally\""
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                }
            }

            // Shown when a picture can't be decoded at all
            Column {
                anchors.centerIn: parent
                spacing: 8
                visible: root.isImage && imgViewer.status === Image.Ready && imgViewer.implicitWidth <= 1
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "🖼️"; font.pixelSize: 40; opacity: 0.5 }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "This picture can't be displayed (unknown or damaged format)."
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 13
                    color: "#94A3B8"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Try \"Open Externally\" to use another app."
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                }
            }

            // Video Preview
            Item {
                id: videoContainer
                visible: root.isVideo
                anchors.fill: parent

                VideoOutput {
                    id: videoOutput
                    anchors.fill: parent
                    fillMode: VideoOutput.PreserveAspectFit
                    orientation: root.rotationSteps * 90
                }

                // Click: play / pause · double-click: full screen · wheel: volume
                MouseArea {
                    id: videoMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: root.chromeShown ? Qt.ArrowCursor : Qt.BlankCursor
                    onPositionChanged: (mouse) => { var g = mapToItem(null, mouse.x, mouse.y); root.pokeAt(g.x, g.y) }
                    // A double-click shouldn't also pause: wait a moment before toggling
                    onClicked: clickTimer.restart()
                    onDoubleClicked: { clickTimer.stop(); root.toggleFullscreen() }
                    onWheel: (wheel) => root.changeVolume(wheel.angleDelta.y > 0 ? 0.05 : -0.05)
                    Timer { id: clickTimer; interval: 230; onTriggered: root.togglePlay() }
                }
            }

            // Audio Preview (Vinyl / Card aesthetic)
            Item {
                visible: root.isAudio
                anchors.fill: parent

                Rectangle {
                    width: Math.min(420, parent.width - 40)
                    implicitHeight: 240
                    anchors.centerIn: parent
                    radius: 16
                    color: "#121724"
                    border.color: "#253147"
                    border.width: 1.5

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 16

                        RowLayout {
                            spacing: 16
                            Rectangle {
                                width: 72
                                height: 72
                                radius: 36
                                color: "#0D111A"
                                border.color: "#10B981"
                                border.width: 2

                                Text {
                                    anchors.centerIn: parent
                                    text: "🎵"
                                    font.pixelSize: 32
                                }
                            }

                            ColumnLayout {
                                spacing: 4
                                Layout.fillWidth: true
                                Text {
                                    text: root.itemName
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 14
                                    font.weight: 700
                                    color: "#F8FAFC"
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: root.currentItem ? formatBytes(root.currentItem.size) : ""
                                    font.family: "Segoe UI, monospace"
                                    font.pixelSize: 11
                                    color: "#94A3B8"
                                }
                            }
                        }

                        Item { Layout.fillHeight: true }

                        Text {
                            text: formatClock(mediaPlayer.position, mediaPlayer.duration) + " / " + formatClock(mediaPlayer.duration, mediaPlayer.duration)
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 11
                            color: "#10B981"
                            Layout.alignment: Qt.AlignHCenter
                        }
                    }
                }
            }

            // Info panel (I)
            Rectangle {
                visible: root.showInfo && !!root.currentItem
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.rightMargin: 56
                width: Math.min(300, parent.width * 0.45)
                height: infoCol.implicitHeight + 24
                radius: 10
                color: "#E6111622"
                border.color: "#2E3A52"
                border.width: 1
                z: 5
                MouseArea { anchors.fill: parent }   // don't toggle video playback through the panel
                Column {
                    id: infoCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 12
                    spacing: 6
                    Text { text: "ⓘ  File info"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 12; font.weight: 700; color: "#F8FAFC" }
                    Repeater {
                        model: {
                            if (!root.currentItem) return []
                            var it = root.currentItem
                            var p = root.itemPath
                            var folder = p.substring(0, Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/")))
                            var rows = [
                                ["Name", it.name],
                                ["Folder", folder],
                                ["Type", (root.itemExt || "").replace(".", "").toUpperCase() + (root.isImage ? " image" : (root.isVideo ? " video" : (root.isAudio ? " audio" : "")))]
                            ]
                            if (it.size > 0) rows.push(["Size", root.formatBytes(it.size)])
                            if (it.mtime > 0) rows.push(["Modified", root.formatDateTime(it.mtime)])
                            if (root.isImage && imgViewer.status === Image.Ready) rows.push(["Resolution", imgViewer.implicitWidth + " × " + imgViewer.implicitHeight + " px"])
                            if (root.isVideo || root.isAudio) {
                                var res = mediaPlayer.metaData.value(MediaMetaData.Resolution)
                                if (res && res.width > 0) rows.push(["Resolution", res.width + " × " + res.height + " px"])
                                if (mediaPlayer.duration > 0) rows.push(["Length", root.formatClock(mediaPlayer.duration, mediaPlayer.duration)])
                            }
                            if (root.tools) {
                                rows.push(["Favourite", root.isFav ? "★ yes" : "no"])
                                rows.push(["Rating", root.rating > 0 ? "★★★★★".substring(0, root.rating) : "not rated"])
                            }
                            if (root.postId) rows.push(["Post ID", root.postId])
                            return rows
                        }
                        delegate: Row {
                            spacing: 8
                            width: infoCol.width
                            Text { text: modelData[0]; width: 72; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; color: "#64748B" }
                            Text {
                                text: modelData[1]
                                width: infoCol.width - 80
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#E2E8F0"
                                wrapMode: Text.WrapAnywhere
                            }
                        }
                    }
                }
            }

            // Delete confirmation (Enter confirms, Esc cancels)
            Rectangle {
                visible: root.confirmDelete
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 18
                width: confirmRow.implicitWidth + 28
                height: 46
                radius: 10
                color: "#F21A0F14"
                border.color: "#EF4444"
                border.width: 1
                z: 6
                MouseArea { anchors.fill: parent }
                Row {
                    id: confirmRow
                    anchors.centerIn: parent
                    spacing: 10
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Move \"" + root.itemName + "\" to the Recycle Bin?"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#FECACA"
                        elide: Text.ElideMiddle
                        width: Math.min(implicitWidth, 420)
                    }
                    Rectangle {
                        width: delText.implicitWidth + 20; height: 28; radius: 6
                        color: delMouse.containsMouse ? "#DC2626" : "#B91C1C"
                        Text { id: delText; anchors.centerIn: parent; text: "🗑 Move to Recycle Bin"; font.pixelSize: 11; font.weight: 700; color: "#FFFFFF" }
                        MouseArea { id: delMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.deleteCurrent() }
                    }
                    Rectangle {
                        width: cancelText.implicitWidth + 20; height: 28; radius: 6
                        color: cancelMouse.containsMouse ? "#1E293B" : "#141720"
                        border.color: "#2E384D"
                        Text { id: cancelText; anchors.centerIn: parent; text: "Cancel"; font.pixelSize: 11; font.weight: 700; color: "#E2E8F0" }
                        MouseArea { id: cancelMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.confirmDelete = false }
                    }
                }
            }

            // Short confirmation messages (copied, rated, …)
            Rectangle {
                visible: root.flashText.length > 0
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 12
                width: flashLabel.implicitWidth + 28
                height: 30
                radius: 15
                color: "#E60F172A"
                border.color: "#38BDF8"
                z: 6
                Text { id: flashLabel; anchors.centerIn: parent; text: root.flashText; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.weight: 600; color: "#E0F2FE" }
            }

            // Floating player controls (video / audio)
            MediaControls {
                id: mediaControls
                z: 6
                visible: root.isMedia && opacity > 0.01
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                lb: root
                player: mediaPlayer
                audio: audioOutput
                shown: root.chromeShown
            }

            // Action bubble ("+5 s", volume, speed, play / pause)
            Rectangle {
                z: 7
                anchors.centerIn: parent
                width: Math.max(76, osdRow.implicitWidth + 32)
                height: 58
                radius: 29
                color: "#D90B0F18"
                border.color: "#334155"
                opacity: root.osdShown ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                scale: root.osdScale
                Row {
                    id: osdRow
                    anchors.centerIn: parent
                    spacing: 8
                    Text { text: root.osdIcon; font.family: "Segoe UI Symbol"; font.pixelSize: 22; color: "#F8FAFC"; anchors.verticalCenter: parent.verticalCenter }
                    Text { visible: root.osdText.length > 0; text: root.osdText; font.family: "Segoe UI"; font.pixelSize: 15; font.weight: 700; color: "#F8FAFC"; anchors.verticalCenter: parent.verticalCenter }
                }
            }

            // Full screen: name + exit along the top, fading with the controls
            Rectangle {
                z: 6
                visible: root.fullscreen && opacity > 0.01
                opacity: root.chromeShown ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 220 } }
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 64
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#CC070A10" }
                    GradientStop { position: 1.0; color: "#00070A10" }
                }
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 18
                    anchors.right: fsExit.left
                    anchors.rightMargin: 12
                    anchors.top: parent.top
                    anchors.topMargin: 14
                    text: root.itemName + (root.mediaList.length > 1 ? "   ·   " + (root.currentIndex + 1) + " / " + root.mediaList.length : "")
                    elide: Text.ElideMiddle
                    font.family: "Segoe UI"
                    font.pixelSize: 14
                    font.weight: 600
                    color: "#F1F5F9"
                }
                Rectangle {
                    id: fsExit
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.top: parent.top
                    anchors.topMargin: 10
                    width: fsExitLabel.implicitWidth + 22
                    height: 28
                    radius: 14
                    color: fsExitMouse.containsMouse ? "#33FFFFFF" : "#1AFFFFFF"
                    border.color: "#44FFFFFF"
                    Text { id: fsExitLabel; anchors.centerIn: parent; text: "🗗  Exit full screen"; font.family: "Segoe UI"; font.pixelSize: 11; font.weight: 600; color: "#F8FAFC" }
                    Springy { hover: fsExitMouse.containsMouse; pressed: fsExitMouse.pressed }
                    MouseArea { id: fsExitMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.setFullscreen(false) }
                }
            }

            // Keyboard shortcut sheet (? or the ⌨ button)
            Rectangle {
                z: 8
                anchors.centerIn: parent
                width: Math.min(parent.width - 40, 520)
                height: Math.min(parent.height - 40, sheetCol.implicitHeight + 32)
                radius: 12
                color: "#F20F1422"
                border.color: "#2A364E"
                visible: root.showShortcuts && opacity > 0.01
                opacity: root.showShortcuts ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 160 } }
                scale: root.showShortcuts ? 1 : 0.94
                Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
                MouseArea { anchors.fill: parent; onClicked: root.showShortcuts = false }
                readonly property var rows: root.isMedia ? [
                    ["Space / K", "Play or pause"], ["← / →", "Back / forward 5 seconds"], ["J / L", "Back / forward 10 seconds"],
                    ["↑ / ↓", "Volume up / down"], ["M", "Mute"], ["0 – 9", "Jump to 0% … 90%"], ["Home / End", "Start / end"],
                    [", / .", "Previous / next frame"], ["< / >", "Slower / faster"], ["F  or double-click", "Full screen"],
                    ["Ctrl+← / Ctrl+→", "Previous / next file"], ["Ctrl+D", "Favourite"], ["R / Shift+R", "Rotate"],
                    ["I", "File info"], ["Delete", "Delete"], ["Esc", "Exit full screen / close"]
                ] : [
                    ["← / →", "Previous / next"], ["Scroll", "Zoom in where you point"], ["+ / − / 0", "Zoom in / out / fit"],
                    ["Drag", "Move around when zoomed"], ["1 – 5", "Rate"], ["Ctrl+D", "Favourite"], ["F", "Full screen"],
                    ["R / Shift+R", "Rotate"], ["Ctrl+C", "Copy picture"], ["Space", "Pause an animation"], ["I", "File info"],
                    ["Delete", "Delete"], ["Esc", "Close"]
                ]
                Column {
                    id: sheetCol
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10
                    Text { text: "⌨  Keyboard shortcuts"; font.family: "Segoe UI"; font.pixelSize: 15; font.weight: 700; color: "#F8FAFC" }
                    Grid {
                        columns: 2
                        columnSpacing: 18
                        rowSpacing: 6
                        Repeater {
                            model: parent.parent.parent.rows.length * 2
                            delegate: Text {
                                readonly property var row: sheetCol.parent.rows[Math.floor(index / 2)]
                                text: index % 2 === 0 ? row[0] : row[1]
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                                font.weight: index % 2 === 0 ? 700 : 400
                                color: index % 2 === 0 ? "#7DD3FC" : "#CBD5E1"
                            }
                        }
                    }
                    Text { text: "Press ? or Esc to close"; font.family: "Segoe UI"; font.pixelSize: 10; color: "#64748B" }
                }
            }

            // Floating Navigation Chevron: PREVIOUS (‹)
            Rectangle {
                width: 44
                height: 72
                radius: 8
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                color: prevChevMouse.containsMouse ? "#28354E" : "#161D2B"
                opacity: (prevChevMouse.containsMouse ? 0.95 : 0.6) * (root.chromeShown ? 1 : 0)
                enabled: root.chromeShown
                Behavior on opacity { NumberAnimation { duration: 200 } }
                border.color: prevChevMouse.containsMouse ? "#38BDF8" : "#243044"
                border.width: 1
                visible: root.mediaList.length > 1

                Text {
                    anchors.centerIn: parent
                    text: "‹"
                    font.pixelSize: 32
                    font.weight: 300
                    color: "#FFFFFF"
                }

                Springy { hover: prevChevMouse.containsMouse; pressed: prevChevMouse.pressed }
                MouseArea {
                    id: prevChevMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.prevItem()
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: root.isMedia ? "Previous file (Ctrl+← or Page Up)" : "Previous file (←)"
                }
            }

            // Floating Navigation Chevron: NEXT (›)
            Rectangle {
                width: 44
                height: 72
                radius: 8
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                color: nextChevMouse.containsMouse ? "#28354E" : "#161D2B"
                opacity: (nextChevMouse.containsMouse ? 0.95 : 0.6) * (root.chromeShown ? 1 : 0)
                enabled: root.chromeShown
                Behavior on opacity { NumberAnimation { duration: 200 } }
                border.color: nextChevMouse.containsMouse ? "#38BDF8" : "#243044"
                border.width: 1
                visible: root.mediaList.length > 1

                Text {
                    anchors.centerIn: parent
                    text: "›"
                    font.pixelSize: 32
                    font.weight: 300
                    color: "#FFFFFF"
                }

                Springy { hover: nextChevMouse.containsMouse; pressed: nextChevMouse.pressed }
                MouseArea {
                    id: nextChevMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.nextItem()
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: root.isMedia ? "Next file (Ctrl+→ or Page Down)" : "Next file (→)"
                }
            }
        }
    }
}
