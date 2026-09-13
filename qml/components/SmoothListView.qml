import QtQuick
import QtQuick.Controls

ListView {
    id: listRoot

    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick
    flickDeceleration: 1500
    maximumFlickVelocity: 4500

    property real targetContentY: contentY
    property real lastWheelTime: 0
    property real wheelVelocityFactor: 1.0
    readonly property bool isScrolling: moving || flicking || wheelAnim.running
    property alias verticalScrollBar: vScrollBar

    onMovingChanged: {
        if (moving) {
            wheelAnim.stop()
            targetContentY = contentY
        }
    }

    NumberAnimation {
        id: wheelAnim
        target: listRoot
        property: "contentY"
        duration: 170
        easing.type: Easing.OutQuad
    }

    ScrollBar.vertical: ScrollBar {
        id: vScrollBar
        active: listRoot.moving || listRoot.flicking || wheelAnim.running || vScrollHover.hovered
        policy: ScrollBar.AsNeeded
        width: 8
        onPressedChanged: {
            if (pressed) {
                wheelAnim.stop()
                listRoot.targetContentY = listRoot.contentY
            }
        }
        HoverHandler { id: vScrollHover }
    }

    WheelHandler {
        id: wheelHandler
        target: null
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: function(event) {
            var now = Date.now()
            var dt = now - listRoot.lastWheelTime
            listRoot.lastWheelTime = now

            // Accelerate velocity if scrolled rapidly (Newtonian momentum)
            if (dt < 130) {
                listRoot.wheelVelocityFactor = Math.min(2.8, listRoot.wheelVelocityFactor + 0.4)
            } else {
                listRoot.wheelVelocityFactor = 1.0
            }

            var delta = event.angleDelta.y
            if (delta === 0) return

            var baseStep = 120 * listRoot.wheelVelocityFactor
            var step = (delta / 120.0) * baseStep
            var maxY = Math.max(0, listRoot.contentHeight - listRoot.height)

            if (!wheelAnim.running) {
                listRoot.targetContentY = listRoot.contentY
            }

            listRoot.targetContentY = Math.max(0, Math.min(maxY, listRoot.targetContentY - step))

            wheelAnim.stop()
            wheelAnim.from = listRoot.contentY
            wheelAnim.to = listRoot.targetContentY
            wheelAnim.start()
        }
    }
}
