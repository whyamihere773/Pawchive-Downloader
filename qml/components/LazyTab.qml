import QtQuick

// A tab that's built in the background the first time it's opened, then kept.
// Building a big tab in one go froze the window for up to a second; here the window keeps
// responding, a small spinner appears if it takes a moment, and the tab fades in when ready.
Item {
    id: lazyTab

    property bool wanted: false                 // e.g. appWindow.currentTab === 6
    property Component sourceComponent: null
    property string loadingText: "Loading…"
    readonly property alias item: loader.item
    readonly property bool ready: loader.status === Loader.Ready
    // Requested but not built yet (while a Component is built in the background the loader
    // doesn't report Loader.Loading, so this is what the spinner follows)
    readonly property bool building: (wanted || loader.active) && !ready
    signal loaded()

    Loader {
        id: loader
        anchors.fill: parent
        asynchronous: true
        active: lazyTab.wanted
        sourceComponent: lazyTab.sourceComponent
        onLoaded: {
            active = true                       // keep it once built
            lazyTab.loaded()
        }
        opacity: status === Loader.Ready ? 1.0 : 0.0
        Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
    }

    // Shown only when building takes longer than a blink, so quick tabs don't flicker
    Item {
        id: busy
        anchors.centerIn: parent
        width: Math.max(ring.width, busyText.implicitWidth)
        height: ring.height + 10 + busyText.implicitHeight
        property bool slow: false
        opacity: (slow && lazyTab.building) ? 1.0 : 0.0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

        Timer {
            interval: 120
            running: lazyTab.building
            onTriggered: busy.slow = true
        }
        // (reset when building ends: a one-shot Timer reports running = false right after it fires)
        Connections {
            target: lazyTab
            function onBuildingChanged() { if (!lazyTab.building) busy.slow = false }
        }

        Item {
            id: ring
            width: 28
            height: 28
            anchors.horizontalCenter: parent.horizontalCenter

            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: "transparent"
                border.color: "#283042"
                border.width: 3
            }

            Canvas {
                id: arc
                anchors.fill: parent
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    ctx.lineWidth = 3
                    ctx.lineCap = "round"
                    ctx.strokeStyle = "#38BDF8"
                    ctx.beginPath()
                    ctx.arc(width / 2, height / 2, width / 2 - 1.5, -Math.PI / 2, Math.PI / 6)
                    ctx.stroke()
                }
                // An animator turns on the render thread, so it keeps spinning while the tab is built
                RotationAnimator on rotation {
                    from: 0
                    to: 360
                    duration: 900
                    loops: Animation.Infinite
                    running: busy.visible
                }
            }
        }

        Text {
            id: busyText
            anchors.top: ring.bottom
            anchors.topMargin: 10
            anchors.horizontalCenter: parent.horizontalCenter
            text: lazyTab.loadingText
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 12
            color: "#94A3B8"
        }
    }
}
