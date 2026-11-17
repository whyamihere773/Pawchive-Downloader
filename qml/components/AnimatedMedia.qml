import QtQuick

// ── Animated picture player ─────────────────────────────────────────────────
// GIF and WebP play through Qt's own AnimatedImage (streams frames, light on memory).
// Anything else Pillow can animate (APNG, animated AVIF, a GIF saved as .png…) is decoded
// in the background by galleryTools.prepareAnimation and stepped through frame by frame.
// For still pictures nothing is shown (isAnimated stays false), so callers can keep their
// normal image underneath.
Item {
    id: am

    property string path: ""
    property var tools: null
    property bool playing: true
    property real speed: 1.0
    property int fillMode: Image.PreserveAspectFit

    function _cleanExt(p) {
        if (!p) return ""
        var clean = p.split("#")[0].split("?")[0]
        var dot = clean.lastIndexOf(".")
        return dot > 0 ? clean.substring(dot).toLowerCase() : ""
    }
    function isRemoteUrl(p) {
        return !!p && (p.indexOf("http://") === 0 || p.indexOf("https://") === 0)
    }
    function seekFrame(idx) {
        var total = frameCount
        if (total <= 0) return
        var clamped = Math.max(0, Math.min(total - 1, Math.round(idx)))
        if (framesMode) {
            am.frame = clamped
        } else if (movie.visible) {
            if (!movie.playing && am.movieType && am.path !== "") {
                movie.playing = Qt.binding(function() { return am.movieType && am.path !== "" })
            }
            movie.currentFrame = clamped
        }
    }
    function stepFrame(dir) {
        var total = frameCount
        if (total <= 1) return
        var next = (currentFrame + (dir >= 0 ? 1 : -1) + total) % total
        seekFrame(next)
    }

    readonly property string ext: _cleanExt(path)
    readonly property bool movieType: ext === ".gif" || ext === ".webp"
    readonly property bool isAnimated: movie.visible || framesMode
    readonly property int frameCount: framesMode ? frames : (movie.visible ? movie.frameCount : 0)
    readonly property int currentFrame: framesMode ? frame : (movie.visible ? movie.currentFrame : 0)

    property bool framesMode: false
    property int frames: 0
    property var durations: []
    property int frame: 0

    function fileUrl(p) {
        if (!p) return ""
        if (p.indexOf("http://") === 0 || p.indexOf("https://") === 0 || p.indexOf("file://") === 0 || p.indexOf("image://") === 0) {
            return p
        }
        var u = p.replace(/\\/g, "/")
        return u.indexOf("/") === 0 ? "file://" + u : "file:///" + u
    }

    function reset() {
        framesMode = false
        frames = 0
        durations = []
        frame = 0
        // Work out the type from the new path here: the movieType binding can still hold the
        // previous file's value while this change handler runs.
        var e = _cleanExt(path)
        var nativeMovie = e === ".gif" || e === ".webp"
        if (path && !nativeMovie && !isRemoteUrl(path) && tools) tools.prepareAnimation(path)
    }

    onPathChanged: reset()
    onPlayingChanged: {
        if (playing && !framesMode && movie.visible && !movie.playing && movieType && path !== "") {
            var cur = movie.currentFrame
            movie.playing = Qt.binding(function() { return am.movieType && am.path !== "" })
            if (cur > 0 && cur < movie.frameCount) movie.currentFrame = cur
        }
    }
    Component.onCompleted: reset()

    // GIF / WebP
    AnimatedImage {
        id: movie
        anchors.fill: parent
        source: (am.movieType && am.path) ? am.fileUrl(am.path) : ""
        fillMode: am.fillMode
        playing: am.movieType && am.path !== ""
        paused: !am.playing
        speed: am.speed
        cache: true
        asynchronous: true
        visible: am.movieType && status === AnimatedImage.Ready && frameCount > 1
        // Mis-named or unusual file: let Pillow try
        onStatusChanged: if (status === AnimatedImage.Error && am.tools) am.tools.prepareAnimation(am.path)
    }

    // Everything else, frame by frame (frames are already in memory, so this never flickers)
    Image {
        id: frameImage
        anchors.fill: parent
        visible: am.framesMode
        fillMode: am.fillMode
        asynchronous: false
        cache: false
        smooth: true
        source: am.framesMode ? ("image://frame/" + encodeURIComponent(am.path) + "?frame=" + am.frame) : ""
    }

    Timer {
        running: am.framesMode && am.playing && am.frames > 1
        repeat: true
        interval: Math.max(16, Math.round(((am.durations && am.durations.length > am.frame) ? am.durations[am.frame] : 100) / Math.max(0.1, am.speed)))
        onTriggered: am.frame = (am.frame + 1) % am.frames
    }

    Connections {
        target: am.tools
        function onAnimationReady(p, info) {
            if (p !== am.path) return
            if (info.frames > 1) {
                am.durations = info.durations
                am.frames = info.frames
                am.frame = 0
                am.framesMode = true
            }
        }
    }
}
