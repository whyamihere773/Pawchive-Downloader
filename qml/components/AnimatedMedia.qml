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
    property int fillMode: Image.PreserveAspectFit

    readonly property string ext: {
        var dot = path.lastIndexOf(".")
        return dot > 0 ? path.substring(dot).toLowerCase() : ""
    }
    readonly property bool movieType: ext === ".gif" || ext === ".webp"
    readonly property bool isAnimated: movie.visible || framesMode
    readonly property int frameCount: framesMode ? frames : (movie.visible ? movie.frameCount : 0)

    property bool framesMode: false
    property int frames: 0
    property var durations: []
    property int frame: 0

    function fileUrl(p) {
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
        var dot = path.lastIndexOf(".")
        var e = dot > 0 ? path.substring(dot).toLowerCase() : ""
        var nativeMovie = e === ".gif" || e === ".webp"
        if (path && !nativeMovie && tools) tools.prepareAnimation(path)
    }

    onPathChanged: reset()
    Component.onCompleted: reset()

    // GIF / WebP
    AnimatedImage {
        id: movie
        anchors.fill: parent
        source: (am.movieType && am.path) ? am.fileUrl(am.path) : ""
        fillMode: am.fillMode
        playing: am.playing
        cache: false
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
        interval: Math.max(20, (am.durations && am.durations.length > am.frame) ? am.durations[am.frame] : 100)
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
