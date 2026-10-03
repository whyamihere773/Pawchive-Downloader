import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia

// ── Floating video / audio controls (Movies & TV / YouTube style) ───────────
// Sits over the bottom of the video on a soft gradient. The lightbox decides when it shows
// (it fades away while a video plays and the mouse rests) and owns the player actions, so the
// buttons here and the keyboard shortcuts always do exactly the same thing.
Item {
    id: mc

    property var lb: null               // the MediaLightboxModal (actions + state)
    property MediaPlayer player: null
    property AudioOutput audio: null
    property bool shown: true

    // While the user works the controls they stay up
    readonly property bool busy: tlMouse.pressed || tlMouse.containsMouse || barHover.hovered || speedMenu.visible

    height: 92
    opacity: shown ? 1 : 0
    visible: opacity > 0.01
    Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    // Drops in a touch on a light spring as it appears
    property real drop: shown ? 0 : 10
    Behavior on drop { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.01 } }
    transform: Translate { y: mc.drop }

    readonly property bool playing: player && player.playbackState === MediaPlayer.PlayingState
    readonly property bool ended: player && player.mediaStatus === MediaPlayer.EndOfMedia
    readonly property real duration: player ? Math.max(0, player.duration) : 0

    function fmt(ms) { return lb ? lb.formatClock(ms, duration) : "" }

    HoverHandler { id: barHover }

    // Soft shade so white controls read on any video
    Rectangle {
        anchors.fill: parent
        anchors.topMargin: -36
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#00070A10" }
            GradientStop { position: 0.55; color: "#99070A10" }
            GradientStop { position: 1.0; color: "#E6070A10" }
        }
    }

    // ── Timeline ────────────────────────────────────────────────────────────
    Item {
        id: timeline
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        anchors.bottom: controls.top
        anchors.bottomMargin: 4
        height: 20

        readonly property bool hot: tlMouse.containsMouse || tlMouse.pressed
        property real hoverX: 0
        property real scrubPos: 0
        readonly property real shownPos: tlMouse.pressed ? scrubPos : (mc.player ? mc.player.position : 0)
        readonly property real frac: mc.duration > 0 ? Math.max(0, Math.min(1, shownPos / mc.duration)) : 0

        function posAt(x) { return Math.max(0, Math.min(1, x / Math.max(1, width))) * mc.duration }

        Rectangle {
            id: track
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            property real thick: timeline.hot ? 6 : 3
            Behavior on thick { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.01 } }
            height: thick
            radius: height / 2
            color: "#38FFFFFF"

            // Where a click would land
            Rectangle {
                visible: timeline.hot
                width: Math.max(0, Math.min(track.width, timeline.hoverX))
                height: parent.height
                radius: parent.radius
                color: "#33FFFFFF"
            }
            // Played part
            Rectangle {
                width: track.width * timeline.frac
                height: parent.height
                radius: parent.radius
                color: "#38BDF8"
            }
        }

        // Knob
        Rectangle {
            width: 14
            height: 14
            radius: 7
            color: "#F8FAFC"
            border.color: "#38BDF8"
            border.width: 2
            x: track.width * timeline.frac - width / 2
            anchors.verticalCenter: parent.verticalCenter
            property real pop: timeline.hot ? 1 : 0
            Behavior on pop { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.01 } }
            scale: pop
            visible: pop > 0.02
        }

        // Time under the cursor
        Rectangle {
            visible: timeline.hot && mc.duration > 0
            width: hoverTime.implicitWidth + 14
            height: 20
            radius: 5
            color: "#E60B0F18"
            border.color: "#334155"
            x: Math.max(0, Math.min(timeline.width - width, (tlMouse.pressed ? track.width * timeline.frac : timeline.hoverX) - width / 2))
            y: -height - 6
            Text {
                id: hoverTime
                anchors.centerIn: parent
                text: mc.fmt(tlMouse.pressed ? timeline.scrubPos : timeline.posAt(timeline.hoverX))
                font.family: "Segoe UI"
                font.pixelSize: 11
                font.weight: 600
                color: "#F8FAFC"
            }
        }

        MouseArea {
            id: tlMouse
            anchors.fill: parent
            anchors.topMargin: -4
            anchors.bottomMargin: -4
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onPressed: (mouse) => {
                timeline.hoverX = mouse.x
                timeline.scrubPos = timeline.posAt(mouse.x)
                if (mc.player) mc.player.setPosition(timeline.scrubPos)
            }
            onPositionChanged: (mouse) => {
                timeline.hoverX = Math.max(0, Math.min(width, mouse.x))
                if (pressed) {
                    timeline.scrubPos = timeline.posAt(mouse.x)
                    if (mc.player) mc.player.setPosition(timeline.scrubPos)
                }
            }
            onReleased: if (mc.player) mc.player.setPosition(timeline.scrubPos)
        }
    }

    // ── Buttons ─────────────────────────────────────────────────────────────
    component CtlButton: Rectangle {
        id: cb
        property string glyph: ""
        property string badge: ""          // small text under a glyph (the "10" on skip buttons)
        property string tip: ""
        property bool active: false
        property int glyphSize: 18
        signal clicked()
        implicitWidth: 34
        implicitHeight: 34
        radius: 8
        color: cbMouse.containsMouse ? "#2EFFFFFF" : (active ? "#2238BDF8" : "transparent")
        border.color: active ? "#38BDF8" : "transparent"
        border.width: 1
        Text {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: cb.badge ? -3 : 0
            text: cb.glyph
            font.family: "Segoe UI Symbol"
            font.pixelSize: cb.glyphSize
            color: cb.active ? "#7DD3FC" : "#F8FAFC"
        }
        Text {
            visible: cb.badge.length > 0
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 3
            text: cb.badge
            font.family: "Segoe UI"
            font.pixelSize: 8
            font.weight: 700
            color: "#CBD5E1"
        }
        Springy { hover: cbMouse.containsMouse; pressed: cbMouse.pressed }
        MouseArea {
            id: cbMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: cb.clicked()
            ToolTip.visible: containsMouse && cb.tip.length > 0
            ToolTip.delay: 400
            ToolTip.text: cb.tip
        }
    }

    RowLayout {
        id: controls
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        anchors.bottomMargin: 8
        height: 40
        spacing: 2

        CtlButton {
            implicitWidth: 40
            implicitHeight: 40
            radius: 20
            glyphSize: 20
            glyph: mc.ended ? "↻" : (mc.playing ? "❚❚" : "▶")
            tip: mc.ended ? "Replay (Space)" : (mc.playing ? "Pause (Space or K)" : "Play (Space or K)")
            onClicked: mc.lb.togglePlay()
        }
        CtlButton { glyph: "↺"; badge: "10"; tip: "Back 10 seconds (J)   ·   ← goes back 5"; onClicked: mc.lb.seekBy(-10000) }
        CtlButton { glyph: "↻"; badge: "10"; tip: "Forward 10 seconds (L)   ·   → goes forward 5"; onClicked: mc.lb.seekBy(10000) }

        // Volume: the slider slides out while hovered (or dragged)
        Item {
            id: volGroup
            implicitHeight: 34
            implicitWidth: volBtn.implicitWidth + volSlide.width + 4
            HoverHandler { id: volHover }
            CtlButton {
                id: volBtn
                anchors.verticalCenter: parent.verticalCenter
                glyph: (!mc.audio || mc.audio.muted || mc.audio.volume === 0) ? "🔇" : (mc.audio.volume < 0.34 ? "🔈" : (mc.audio.volume < 0.67 ? "🔉" : "🔊"))
                glyphSize: 17
                tip: (mc.audio && mc.audio.muted ? "Unmute (M)" : "Mute (M)") + "   ·   ↑ / ↓ change the volume"
                onClicked: mc.lb.toggleMute()
            }
            Item {
                id: volSlide
                anchors.left: volBtn.right
                anchors.leftMargin: 2
                anchors.verticalCenter: parent.verticalCenter
                property real open: (volHover.hovered || volMouse.pressed) ? 1 : 0
                Behavior on open { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.005 } }
                width: 84 * Math.max(0, open)
                height: 20
                clip: true
                readonly property real level: mc.audio ? (mc.audio.muted ? 0 : mc.audio.volume) : 0
                Rectangle {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 76
                    height: 4
                    radius: 2
                    color: "#38FFFFFF"
                    Rectangle { width: parent.width * volSlide.level; height: parent.height; radius: 2; color: "#F8FAFC" }
                    Rectangle {
                        width: 12; height: 12; radius: 6
                        color: "#F8FAFC"
                        anchors.verticalCenter: parent.verticalCenter
                        x: parent.width * volSlide.level - width / 2
                    }
                }
                MouseArea {
                    id: volMouse
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    function apply(x) { mc.lb.setVolume(Math.max(0, Math.min(1, x / 76)), false) }
                    onPressed: (mouse) => apply(mouse.x)
                    onPositionChanged: (mouse) => { if (pressed) apply(mouse.x) }
                    onWheel: (wheel) => mc.lb.changeVolume(wheel.angleDelta.y > 0 ? 0.05 : -0.05)
                }
            }
        }

        Text {
            Layout.leftMargin: 6
            text: mc.fmt(mc.player ? mc.player.position : 0) + "  /  " + mc.fmt(mc.duration)
            font.family: "Segoe UI"
            font.pixelSize: 12
            font.weight: 600
            color: "#E2E8F0"
        }

        Item { Layout.fillWidth: true }

        // Playback speed
        Rectangle {
            id: speedBtn
            implicitWidth: speedLabel.implicitWidth + 18
            implicitHeight: 26
            radius: 13
            readonly property real rate: mc.player ? mc.player.playbackRate : 1
            color: speedMouse.containsMouse || speedMenu.visible ? "#2EFFFFFF" : (Math.abs(rate - 1) > 0.001 ? "#2238BDF8" : "transparent")
            border.color: Math.abs(rate - 1) > 0.001 ? "#38BDF8" : "#44FFFFFF"
            Text {
                id: speedLabel
                anchors.centerIn: parent
                text: mc.lb ? mc.lb.rateLabel(speedBtn.rate) : "1×"
                font.family: "Segoe UI"
                font.pixelSize: 11
                font.weight: 700
                color: "#F8FAFC"
            }
            Springy { hover: speedMouse.containsMouse; pressed: speedMouse.pressed }
            MouseArea {
                id: speedMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: speedMenu.visible ? speedMenu.close() : speedMenu.open()
                ToolTip.visible: containsMouse && !speedMenu.visible
                ToolTip.delay: 400
                ToolTip.text: "Playback speed   ·   < slower, > faster"
            }

            Popup {
                id: speedMenu
                y: -implicitHeight - 8
                x: (speedBtn.width - implicitWidth) / 2
                padding: 4
                transformOrigin: Item.Bottom
                enter: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140 }
                    SpringAnimation { property: "scale"; from: 0.86; to: 1; spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 }
                }
                exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: 110 } }
                background: Rectangle { color: "#F0101624"; radius: 8; border.color: "#2A364E" }
                contentItem: Column {
                    spacing: 1
                    Repeater {
                        model: mc.lb ? mc.lb.speedSteps : []
                        delegate: Rectangle {
                            readonly property bool current: Math.abs(modelData - speedBtn.rate) < 0.001
                            width: 76
                            height: 26
                            radius: 5
                            color: rateMouse.containsMouse ? "#24324A" : (current ? "#1A2A44" : "transparent")
                            Text {
                                anchors.centerIn: parent
                                text: (current ? "✓ " : "") + (modelData === 1 ? "Normal" : mc.lb.rateLabel(modelData))
                                font.family: "Segoe UI"
                                font.pixelSize: 11
                                font.weight: current ? 700 : 500
                                color: current ? "#7DD3FC" : "#E2E8F0"
                            }
                            MouseArea {
                                id: rateMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: { mc.lb.setSpeed(modelData); speedMenu.close() }
                            }
                        }
                    }
                }
            }
        }

        CtlButton {
            glyph: "∞"
            glyphSize: 20
            active: !!mc.lb && mc.lb.isLooping
            tip: (mc.lb && mc.lb.isLooping) ? "Loop is on (click to play once)" : "Loop this " + (mc.lb && mc.lb.isAudio ? "track" : "video")
            onClicked: mc.lb.isLooping = !mc.lb.isLooping
        }
        CtlButton {
            glyph: "⌨"
            active: !!mc.lb && mc.lb.showShortcuts
            tip: "Keyboard shortcuts (?)"
            onClicked: mc.lb.showShortcuts = !mc.lb.showShortcuts
        }
        CtlButton {
            visible: !!mc.lb && mc.lb.isVideo
            glyph: (mc.lb && mc.lb.fullscreen) ? "🗗" : "⛶"
            tip: (mc.lb && mc.lb.fullscreen) ? "Exit full screen (F or Esc)" : "Full screen (F or double-click)"
            onClicked: mc.lb.toggleFullscreen()
        }
    }
}
